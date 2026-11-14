以下是整理好的流程,內容來自我們這幾輪測試的經驗。指令在 Android 11 以上通常可用,不同廠牌可能有差異,我標了需要注意的地方。

## 一、先理解:Doze 兩層與進入時間

- **Light idle(淺層休眠):** 螢幕關閉、未充電後很快進入,限制 App 的網路與 job,每隔一段時間有維護窗口(light-maint)。
- **Deep idle(深度休眠):** 要螢幕關閉、未充電,而且手機**靜止**才會進入。維護窗口(deep-maint)間隔會指數放大,例如 1h → 2h → 4h → 6h。
- **進入時間的估算:** 約等於 `inactive_to + idle_after_inactive_to + 數分鐘感測`。
  - 紅米 10(15m + 15m)實測約 30 分鐘。
  - Samsung(30m + 30m)預期約 1 小時,但我們實測約 3 小時,這是機型表現,不是流程錯誤。
- 先看自己機型的設定值:`adb shell dumpsys deviceidle`,最上面的 Settings 區塊。

## 二、測試前檢查

```
adb shell dumpsys battery | grep -E "^  (AC|USB|Wireless) powered|^  level"   # 確認沒在充電
adb shell dumpsys deviceidle | grep -E "mLightEnabled|mDeepEnabled|mForceIdle"       # 兩者應為 true,ForceIdle 應為 false
adb shell cmd role get-role-holders android.app.role.HOME                             # 確認預設桌面(測前、測後都記錄)
adb shell dumpsys alarm | grep -i -A2 "next alarm clock"                              # 空白=沒有鬧鐘,不會被 min_time_to_alarm 擋住
adb shell dumpsys power | grep -i -A8 "Wake Locks"                                    # 確認沒有 App 長期持有 wakelock
adb shell getprop ro.build.version.release                                            # 記錄系統版本
```

另外:關掉會干擾的 App 活動(Play 商店自動更新、同步)、widget 兩邊要一致、手機放在**穩定平面不要移動**、同一個 WiFi。

## 三、標準流程

1. 手機亮屏、解鎖,連上 adb,然後執行:
```
adb shell dumpsys deviceidle unforce
adb shell dumpsys batterystats --enable full-wake-history
adb shell dumpsys batterystats --reset
```
`unforce` 一定要做,否則先前 `force-idle` 的強制狀態會汙染測試。

2. 關閉無線偵錯,避免測試期間 adb 干擾(連線會中斷,不需碰手機):
```
adb shell settings put global adb_wifi_enabled 0
```
這行在部分機型可能無效,那就改手動關閉開發人員選項裡的「無線偵錯」,並且立刻鎖屏。如果是 USB 連線,通常會變成充電狀態,不適合做這個測試。

3. **鎖屏、不再碰手機。** 記下開始時間。時間至少抓「預估進入 deep idle 時間的 2 倍」,Samsung 建議 3 小時以上。

4. 時間到後,先在手機打開無線偵錯,連線埠號每次都會變,要看手機畫面:
```
adb connect <IP>:<埠號>
```
(第一次需 `adb pair <IP>:<配對埠號>`。)

5. **連上就馬上匯出**,因為亮屏和重新連線也會被記進去:
```
adb shell dumpsys batterystats > run_full.txt
adb shell dumpsys batterystats --checkin > run_checkin.txt
adb shell dumpsys batterystats --history > run_history.txt
adb shell dumpsys deviceidle > run_deviceidle.txt
adb shell cmd role get-role-holders android.app.role.HOME
```
需要看網路時再加 `adb shell dumpsys netstats detail > run_netstats.txt`。

## 四、判讀重點

| 檔案 | 關鍵欄位 | 意義 |
|---|---|---|
| `deviceidle` | Idling history | 看 `light-idle`、`deep-idle`、`deep-maint`、`normal (alarm/unlocked/screen)` 的時間軸與退出原因 |
| `deviceidle` | `mState` / `mLightState` | 目前狀態 |
| `batterystats` 開頭 | `Device light idling`、`Device full idling`(= deep) | 兩種休眠的總時間與占比 |
| `batterystats` 開頭 | `Time on battery screen off`、uptime % | 螢幕關閉比例、系統實際清醒比例 |
| `batterystats` | `Wakeup reason`(如 `wlan_mbox_irq`) | 是誰把 SoC 喚醒,WiFi 中斷不受 Doze 影響 |
| `batterystats` | `Estimated power use` | 各硬體與各 UID 的估算耗電 |
| `history` | `device_idle=light/full/off` | 精確的狀態切換時間 |
| `history` | `DeviceIdleController.deep.progression` | Doze 往下一階段的計時,每次相隔約 `idle_after_inactive_to` |
| `history` | `wakeupap=<uid>` | 喚醒被歸屬到哪個 UID |

**實用指標:** 第一次進入 deep idle 的時間、deep idle 占比、維護窗口是否呈 1h → 2h → 4h、`wlan_mbox_irq` 喚醒次數(每小時)。

## 五、快速驗證(不用等數小時)

```
adb shell dumpsys deviceidle force-idle      # 強制進入 deep idle
adb shell dumpsys deviceidle                 # 看 mState=IDLE
adb shell dumpsys deviceidle unforce         # 一定要還原
adb shell dumpsys deviceidle step deep       # 手動推進一個階段,可逐步觀察
adb shell dumpsys deviceidle get deep        # 查詢目前 deep 狀態
```

這只證明「系統能進入 deep idle」,不代表自然進入的時間。

## 六、常見陷阱(我們實際踩過的)

- **預設桌面和以為的不同。** 一定要用 `role get-role-holders` 在測前和測後各驗一次;`history` 裡的 `top=` 事件(開頭和結尾拿起手機時)也能佐證。
- **`Discharge` 欄位解析度很粗**(約 1% 一階,6000 mAh 約 60 mAh),短時間測試不要拿它算每小時耗電,改看 `Estimated power use` 的各項加總,並且重複測。
- **重置時手機已在 deep idle。** 這樣量不到「進入時間」。要先亮屏一次再鎖屏開始。
- **忘記 `unforce`。** 強制狀態會一直保留到還原或重開機。
- **亮屏時間要一致。** 過程中只要亮屏,Doze 狀態機就會重來。
- **手機被碰到或震動。** Doze 的「靜止」判斷由 significant motion 感測器負責;AOSP 的行為是在 `IDLE_PENDING`/`SENSING` 階段偵測到動作會退回 `INACTIVE` 重新計時,所以放穩很重要。
- **背景下載、同步。** 例如 Play 商店 3 小時內下載 20 MB,會讓耗電和 WiFi 活動變大,測前先確認。
- **WiFi 中斷與 Doze 無關。** `wlan_mbox_irq` 這類喚醒在 deep idle 期間仍然發生,而且主要來自網路環境,無法靠換 launcher 改善。
- **無線偵錯重開後埠號會變,** 要看手機畫面;匯出要趕快。

## 七、記錄表(建議每次測試都填)

| 項目 | 填寫 |
|---|---|
| 機型 / 系統版本 / 日期時間 | |
| 預設桌面(測前 / 測後) | |
| `inactive_to` / `idle_after_inactive_to` | |
| 測試時長 / 亮屏秒數 | |
| 第一次進入 deep idle 的時間 | |
| deep idle 占比 / 次數 | |
| 維護窗口間隔 | |
| `wlan_mbox_irq` 次數與時間 | |
| 被歸屬的喚醒來源前 3 名 | |
| `Estimated power use` 總和 / 前 5 名 UID | |

需要的話,我可以把這份整理成一份可以下載或分享的文件(Word 或 PDF)。
