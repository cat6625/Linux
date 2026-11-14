# Android ADB 待機與深度休眠(Doze)標準測試流程

用 ADB 量測 Android 手機的待機耗電,並確認是否能正常進入深度休眠(Deep Doze)。
內容整理自實測(Samsung Galaxy / Android 15 與 Redmi 10 / MIUI),指令在 Android 11 以上通常可用,不同廠牌可能有差異。

> 目錄
> 1. [原理與時間估算](#1-原理與時間估算)
> 2. [測試前檢查](#2-測試前檢查)
> 3. [標準測試流程](#3-標準測試流程)
> 4. [判讀重點](#4-判讀重點)
> 5. [快速驗證(不用等數小時)](#5-快速驗證不用等數小時)
> 6. [常見陷阱](#6-常見陷阱)
> 7. [案例:Samsung「尋找我的手機」擋住 Deep Doze](#7-案例samsung尋找我的手機擋住-deep-doze)
> 8. [耗電量怎麼算](#8-耗電量怎麼算)
> 9. [記錄表](#9-記錄表)

---

## 1. 原理與時間估算

| 狀態 | 條件 | 特性 |
|---|---|---|
| Light idle(淺層休眠) | 螢幕關閉、未充電後很快進入 | 限制 App 的網路與 job,週期性維護窗口(`light-maint`) |
| Deep idle(深度休眠) | 螢幕關閉、未充電、**手機靜止**、且**下一個會喚醒手機的鬧鐘夠遠** | 維護窗口(`deep-maint`)間隔呈指數放大:1h → 2h → 4h → 6h |

**進入 Deep idle 的預期時間** ≈ `inactive_to` + `idle_after_inactive_to` + 數分鐘感測。
先看自己機型的設定值:

```bash
adb shell dumpsys deviceidle        # 最上方的 Settings 區塊
```

| 設定 | Samsung(實測) | Redmi 10 / MIUI(實測) |
|---|---|---|
| `inactive_to` | 30m | 15m |
| `idle_after_inactive_to` | 30m | 15m |
| `min_time_to_alarm` | **1h** | 10m |
| 實測進入 Deep idle | 約 3h(受 FMM 鬧鐘影響,見第 7 節) | 約 27–31 分(從 light idle 起算) |

---

## 2. 測試前檢查

```bash
# 1. 沒在充電,記下電量(只顯示必要行,避免整串 log)
adb shell dumpsys battery | grep -E "^  (AC|USB|Wireless) powered|^  level"

# 2. Doze 開關正常、沒有被強制
adb shell dumpsys deviceidle | grep -E "mLightEnabled|mDeepEnabled|mForceIdle"
#   預期:mLightEnabled=true mDeepEnabled=true / mForceIdle=false

# 3. 預設桌面(測前、測後各記一次)
adb shell cmd role get-role-holders android.app.role.HOME

# 4. 下一個鬧鐘與「下一個會喚醒手機的鬧鐘」(兩者都要看)
adb shell dumpsys alarm | grep -i -A2 "next alarm clock"
adb shell dumpsys alarm | grep -A8 "Next wake from idle"
#   預期:Next alarm clock 底下為空白

# 5. 沒有 App 長期持有 wakelock
adb shell dumpsys power | grep -i -A8 "Wake Locks"

# 6. 系統版本(記錄用)
adb shell getprop ro.build.version.release
```

**檢查清單**

- [ ] 未充電,WiFi 環境固定
- [ ] 預設桌面與預期相同
- [ ] `Next alarm clock` 空白(鬧鐘、計時器、睡眠計時器都已關閉)
- [ ] `Next wake from idle` 沒有 1 小時內會響的鬧鐘(Samsung 請看第 7 節)
- [ ] Wake Locks 沒有 `dream:doze`(若有,關閉 Always On Display 再測)
- [ ] 背景下載與同步先停止(例如 Play 商店自動更新)
- [ ] 手機放在穩定平面,測試期間不移動、不碰
- [ ] 兩邊比較時,widget 與已安裝 App 完全一致

---

## 3. 標準測試流程

### 步驟 1:重置統計(手機亮屏、已連線 adb)

```bash
adb shell dumpsys deviceidle unforce                       # 一定要做,避免先前 force-idle 汙染
adb shell dumpsys batterystats --enable full-wake-history
adb shell dumpsys batterystats --reset
```

### 步驟 2:關閉無線偵錯(避免測試期間 adb 干擾)

```bash
adb shell settings put global adb_wifi_enabled 0
```

這行會直接關掉無線偵錯,連線隨之中斷,不需要碰手機。
若無效,改為:手動到「開發人員選項」關閉「無線偵錯」,關完立刻鎖屏。
USB 連線通常會變成充電狀態,不適合做這個測試。

### 步驟 3:鎖屏靜置

- 記下開始時間,**不再碰手機**。
- 時長至少抓「預期進入 Deep idle 時間的 2 倍」。
- 測試中只要亮屏,Doze 狀態機就會重來。

### 步驟 4:重新連線

在手機打開「無線偵錯」。連接埠每次重開都會變,請看手機畫面上的 IP:埠號:

```bash
adb connect <IP>:<埠號>        # 第一次需先 adb pair <IP>:<配對埠號>
```

### 步驟 5:連上後立刻匯出

亮屏與重新連線的幾分鐘也會被記錄,所以要趕快匯出:

```bash
adb shell dumpsys batterystats            > run_full.txt
adb shell dumpsys batterystats --checkin  > run_checkin.txt
adb shell dumpsys batterystats --history  > run_history.txt
adb shell dumpsys deviceidle              > run_deviceidle.txt
adb shell cmd role get-role-holders android.app.role.HOME
# 需要看網路時:
adb shell dumpsys netstats detail         > run_netstats.txt
```

---

## 4. 判讀重點

| 檔案 | 關鍵欄位 | 意義 |
|---|---|---|
| `deviceidle` | `Idling history` | `light-idle` / `deep-idle` / `deep-maint` / `normal (alarm / unlocked / screen)` 時間軸與退出原因 |
| `deviceidle` | `mState` / `mLightState` | 目前狀態 |
| `batterystats` 開頭 | `Device light idling`、`Device full idling`(= deep) | 兩種休眠的總時間與占比 |
| `batterystats` 開頭 | `Time on battery screen off`、uptime % | 螢幕關閉比例、系統實際清醒比例 |
| `batterystats` 開頭 | `Discharge` | 實際放電 mAh(見第 8 節) |
| `batterystats` | `Wakeup reason`(如 `wlan_mbox_irq`) | 是誰把 SoC 喚醒;WiFi 中斷不受 Doze 影響 |
| `batterystats` | `Estimated power use` | 各硬體與各 UID 的**模型估算**,只用來看占比 |
| `history` | `device_idle=light / full / off` | 精確的狀態切換時間 |
| `history` | `DeviceIdleController.deep.progression` | Doze 往下一階段的計時,相隔約 `idle_after_inactive_to` + 1 分 |
| `history` | `wakeupap=<uid>` | 喚醒被歸屬到哪個 UID |
| `history` | `top=<package>` | 開頭與結尾拿起手機時的前景 App(可佐證預設桌面) |

**實用指標**:第一次進入 Deep idle 的時間、Deep idle 占比、維護窗口是否呈 1h → 2h → 4h、`wlan_mbox_irq` 每小時次數。

---

## 5. 快速驗證(不用等數小時)

```bash
adb shell dumpsys deviceidle force-idle    # 強制進入 deep idle
adb shell dumpsys deviceidle               # 看 mState=IDLE
adb shell dumpsys deviceidle step deep     # 手動推進一個階段
adb shell dumpsys deviceidle get deep      # 查詢目前 deep 狀態
adb shell dumpsys deviceidle unforce       # 一定要還原
```

這只證明「系統能進入 Deep idle」,不代表自然進入的時間。

---

## 6. 常見陷阱

- **預設桌面和以為的不同。** 測前、測後各用 `role get-role-holders` 驗一次;`history` 裡的 `top=` 事件也能佐證。整段螢幕關閉的測試,`history` 裡沒有 launcher 的 `top=` 事件,無法靠檔案本身判斷。
- **重置時手機已在 Deep idle。** 這樣量不到「進入時間」。先亮屏一次再鎖屏開始。
- **忘記 `unforce`。** 強制狀態會一直保留到還原或重開機。
- **有鬧鐘或計時器。** 下一個會喚醒手機的鬧鐘太近,Doze 會放棄進入 Deep idle;鬧鐘響也會讓 Doze 退出(`normal (alarm)`)。
- **Always On Display。** Wake Locks 出現 `dream:doze` 代表顯示處於休眠顯示狀態;`batterystats` 的 `Screen doze` 大於 0 也是同一件事。
- **手機被碰到或震動。** Deep idle 需要「靜止」(significant motion 感測器),偵測到動作會重新計時。
- **背景下載、同步。** 例如 Play 商店在 3 小時內下載 20 MB,會讓耗電和 WiFi 活動明顯上升。
- **WiFi 中斷與 Doze 無關。** `wlan_mbox_irq` 這類喚醒在 Deep idle 期間仍會發生,來源多半是網路環境(路由器廣播、mDNS 等),換 launcher 無法改善。
- **無線偵錯重開後埠號會變。** 要看手機畫面;匯出要趕快。
- **Termux / 本機 adb 影響很小。** 實測 Termux 前景服務 2 小時耗電不到 0.03 mAh,且沒有 wakelock;adb 走 localhost 不用 WiFi 硬體。真正要注意的是測試中有沒有亮屏。

---

## 7. 案例:Samsung「尋找我的手機」擋住 Deep Doze

### 現象

Samsung(One UI,Android 15)不論預設桌面是 One UI Home 還是 Lawnchair,都要約 3 小時才進入第一次 Deep idle;同樣的測試在 Redmi 10 約 30 分鐘就進入。

### 找出「不是你設的」鬧鐘

`Next alarm clock` 出現了你沒設的時間。該時間戳會一直更新,所以不要用時間戳去 `grep`,改用:

```bash
adb shell dumpsys alarm | grep -A8 "Next wake from idle"
adb shell dumpsys alarm > alarm.txt     # 要完整分析時,在 alarm.txt 搜尋 "Next alarm clock"
```

實測輸出的擁有者:

- 套件:`com.samsung.android.fmm`(尋找我的手機 / SmartThings Find)
- 標籤:`*walarm*:defaultScanStartTimer`
- 類型:`RTC_WAKEUP` 精確鬧鐘,帶 alarm clock 資訊,所以被顯示成「下一個鬧鐘」

> 時鐘 App 的鬧鐘會落在整分(例如 08:30:00.000);帶秒與毫秒的時間通常是計時器或其他 App 排程的。

### 為什麼會擋住

Samsung 的 `min_time_to_alarm=1h`。據 AOSP 的行為,Doze 在推進下一階段時,如果下一個會喚醒手機的鬧鐘距離現在不到這個時間,就放棄進入 Deep idle 並回到 active 重新計時;鬧鐘響起也會讓 Doze 退出。

### 時間證據

`history` 裡 FMM 鬧鐘實際觸發的時間,與 `deep.progression` 及 Deep idle 進入時間的對應:

| 測試 | FMM 鬧鐘觸發 | 之後兩個 `deep.progression` | 進入 Deep idle |
|---|---|---|---|
| 6h | 1h54m42 | 2h25m42、2h56m43 | 2h56m53 |
| 6h | 4h50m57 | 5h21m57、5h52m57 | 5h53m15 |
| 3h10m | 1h57m02 | 2h28m02、2h59m02 | 3h01m01 |

每次進入 Deep idle 都是 **FMM 鬧鐘響起後約 62 分鐘**(31 + 31 分鐘),而且 Doze 計時就在鬧鐘響的那一刻重新開始。

更早的失敗嘗試也對得上:6h 測試第二個 progression(1h00m40)距離 FMM 的 1h54m42 只剩約 54 分;3h 測試第一個 progression(0h57m48)距離 FMM 的 1h57m02 只剩約 59 分,都不到 1 小時。

> 注意:「放棄進入」的原因是依 AOSP 行為推論,日誌沒有直接記錄,但時間吻合得很完整。

### 處理方式

1. 在「尋找我的手機」設定中**整個關閉**。實測只留「搜尋此手機定位」仍然會出現該鬧鐘(甚至幾秒後就響);完全關閉後 `Next alarm clock` 才變空白。選項名稱依 One UI 版本略有不同。
2. 確認:

   ```bash
   adb shell dumpsys alarm | grep -i -A2 "next alarm clock"
   ```

   底下應為空白(例如只顯示 `105 pending alarms`)。
3. 重測,預期約 1 小時(30 + 30 分鐘,加感測)就進入 Deep idle。
4. **測完請恢復。** 這是防盜與找回手機的功能,關閉期間手機遺失將無法被找到。

進階(測試期間才用):`adb shell am force-stop com.samsung.android.fmm`(可能被系統重啟),或 `adb shell pm disable-user --user 0 com.samsung.android.fmm`(用 `pm enable com.samsung.android.fmm` 還原)。

### 對 launcher 比較的結論

- Lawnchair 預設與 One UI Home 預設進入 Deep idle 的時間幾乎相同(3h01m 對 2h56m),延遲來自 FMM 鬧鐘,與 launcher 無關。
- Lawnchair 本身耗電可以忽略(3h10m 內 0.0347 mAh,Top 時間 4.1 秒),也沒有任何喚醒紀錄。

---

## 8. 耗電量怎麼算

- **實際放電**以 `batterystats` 開頭的 `Discharge`(mAh)為準,它來自電池的庫倫計數器 `cc`。此機型每階 4.5 mAh,所以精度約 ±4.5 mAh。
- 想看某一段時間的放電,直接用電池變化 log 的 `cc` 相減(Samsung 的 `dumpsys battery` 輸出含這些 log):

  ```bash
  adb shell dumpsys battery | grep ACTION_BATTERY_CHANGED
  ```

  例如 `cc:2493000` → `cc:2430000`,差 63000 = 63.0 mAh。
- `Estimated power use` 各項加總是**模型估算**,可能與實際差很多(實測 6h 加總約 116 mAh,實際 63.0 mAh),只適合看各項的占比,不要拿來算每小時耗電。
- 短時間測試(幾十分鐘)解析度不足,建議每個條件至少測 2 小時並重複 2 次。

---

## 9. 記錄表

每次測試都填一份:

| 項目 | 填寫 |
|---|---|
| 機型 / 系統版本 / 日期時間 | |
| 預設桌面(測前 / 測後) | |
| `inactive_to` / `idle_after_inactive_to` / `min_time_to_alarm` | |
| `Next alarm clock` / `Next wake from idle` 擁有者 | |
| 測試時長 / 亮屏秒數 | |
| 第一次進入 Deep idle 的時間 | |
| Deep idle 占比 / 次數 | |
| 維護窗口間隔 | |
| `Discharge`(mAh)與每小時 | |
| `wlan_mbox_irq` 次數與時間 | |
| 被歸屬的喚醒來源前 3 名(`wakeupap`) | |
| `Estimated power use` 前 5 名 UID(僅看占比) | |
| 備註(下載、同步、是否移動手機) | |
