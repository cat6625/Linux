# Android 待機與 Deep Idle(Doze)測試指南

用 ADB 量測手機待機耗電,並確認是否能正常進入 Doze 的 deep idle。
內容整理自實測:Samsung(One UI / Android 15,6000 mAh)與 Redmi 10(MIUI)。
指令在 Android 11 以上通常可用,不同廠牌可能有差異。

> **目錄**
> 0. [名詞:deep idle、deep sleep、深度休眠](#0-名詞deep-idledeep-sleep深度休眠)
> 1. [調查摘要(時間線與結論)](#1-調查摘要時間線與結論)
> 2. [原理與時間估算](#2-原理與時間估算)
> 3. [測試前檢查](#3-測試前檢查)
> 4. [標準測試流程](#4-標準測試流程)
> 5. [要不要斷開無線偵錯?](#5-要不要斷開無線偵錯)
> 6. [判讀重點](#6-判讀重點)
> 7. [快速驗證](#7-快速驗證不用等數小時)
> 8. [案例:Samsung「尋找我的手機」擋住 deep idle](#8-案例samsung尋找我的手機擋住-deep-idle)
> 9. [常見陷阱](#9-常見陷阱)
> 10. [耗電量怎麼算](#10-耗電量怎麼算)
> 11. [記錄表](#11-記錄表)
> 12. [附錄:向 AI 提問的範本與常見誤讀](#12-附錄向-ai-提問的範本與常見誤讀)

---

## 0. 名詞:deep idle、deep sleep、深度休眠

「deep sleep」在 Android 上至少有三種意思,提問或寫報告時請先講清楚:

| 說法 | 實際指的是 | 在哪裡看 |
|---|---|---|
| **Doze 的 deep idle**(本文討論的) | 螢幕關閉、靜止一段時間後,系統限制 App 網路、job、alarm 的深度休眠 | `dumpsys deviceidle` 的 `deep-idle`;`batterystats` 的 `Device full idling` |
| **CPU deep sleep(suspend)** | CPU 進入 suspend 狀態(CPU Spy 之類 App 的 Deep Sleep) | `batterystats` 的 uptime 相對 realtime;例如 uptime 10.2% 約代表 CPU 有約 90% 時間在 suspend |
| **Samsung「深度休眠應用程式」** | One UI 電池設定中,對不常用 App 的背景限制(設定 → 電池 → 背景使用限制) | 設定畫面,和 Doze 是不同機制 |

建議用「**Doze 的 deep idle(`DeviceIdleController`)**」描述本文的問題,並附上 `deviceidle` 與 `batterystats` 的數據。

---

## 1. 調查摘要(時間線與結論)

**問題:**Samsung 手機要約 3 小時才第一次進入 deep idle,是不是 launcher(Lawnchair)或 adb 造成的?

| # | 測試 | 條件 | 第一次 deep idle | Deep idle 占比 | 實際放電(`Discharge`) |
|---|---|---|---|---|---|
| 1 | 初測 2h(One UI)| Termux 設鬧鐘、結尾亮屏、FMM 開 | 無(light idle 96.5%) | 0% | 13.5 mAh |
| 1 | 初測 2h(Lawnchair)| 同上,亮屏 54 秒(One UI 為 19 秒) | 無(light idle 96.1%) | 0% | 94.5 mAh |
| 2 | 6h(One UI 預設) | Ubuntu 無線 adb 全程連線、FMM 開 | 2h56m53 | 19.3% | 63.0 mAh(約 10.4 mAh/h) |
| 3 | 1h37m(One UI 預設) | 關閉無線偵錯、FMM 開 | 重置前已在 deep idle,無法比較 | 99.0% | 22.5 mAh |
| 3 | 3h10m(Lawnchair 預設)| 關閉無線偵錯、FMM 開;期間 Play 商店下載 20 MB | 3h01m01 | 4.6% | 63.0 mAh(約 19.9 mAh/h) |
| 4 | 2h17m(Lawnchair 預設)| 關閉無線偵錯、**FMM 整個關閉** | **0h58m13** | **43.7%** | 18.0 mAh(約 7.9 mAh/h) |
| — | Redmi 10(MIUI)| 同樣裝 Lawnchair | 約 27–31 分 | — | — |

**結論:**

1. **Lawnchair 與 launcher 都不是原因。** Lawnchair 預設與 One UI 預設進入 deep idle 的時間幾乎相同(3h01m 對 2h56m),Lawnchair 本身耗電可忽略(3h10m 內 0.0347 mAh,無任何喚醒紀錄)。
2. **adb 不是主因。** 6h(adb 全程連線)與 3h10m(關閉無線偵錯)都約 3 小時才進入。
3. **主因是 Samsung「尋找我的手機」(FMM)的週期鬧鐘**,加上 Samsung 的 `min_time_to_alarm=1h`。整個關閉後,第一次進入 deep idle 縮短到 58 分鐘(理論值:30 + 30 分 + 感測)。見[第 8 節](#8-案例samsung尋找我的手機擋住-deep-idle)。
4. **初測(1)** 的 Termux 影響很小,但**亮屏會重設 Doze 計時**,而且兩邊亮屏時間不同(54 秒對 19 秒),加上 ssidwidget 在背景、WiFi 活動不同,94.5 對 13.5 mAh 的差距不能歸因到 launcher。
5. **WiFi kernel active 約 53–63% 與 adb 無關。** 有 adb(59.2%)、無 adb(53.1%、54.2%)、無 adb 且 FMM 關(63.2%)都高。

---

## 2. 原理與時間估算

| 狀態 | 條件 | 特性 |
|---|---|---|
| Light idle(淺層) | 螢幕關閉、未充電後很快進入 | 限制 App 的網路與 job,週期性維護窗口(`light-maint`) |
| Deep idle(深度) | 螢幕關閉、未充電、**手機靜止**、**下一個會喚醒手機的鬧鐘夠遠** | 維護窗口(`deep-maint`)間隔指數放大:1h → 2h → 4h → 6h |

**預期進入時間** ≈ `inactive_to` + `idle_after_inactive_to` + 數分鐘感測。

```bash
adb shell dumpsys deviceidle        # 最上方 Settings 區塊
```

| 設定 | Samsung | Redmi 10 / MIUI |
|---|---|---|
| `inactive_to` | 30m | 15m |
| `idle_after_inactive_to` | 30m | 15m |
| `min_time_to_alarm` | **1h** | 10m |
| 實測進入 deep idle | 約 3h(FMM 開);**0h58m(FMM 關)** | 約 27–31 分(從 light idle 起算) |

---

## 3. 測試前檢查

```bash
# 1. 沒在充電,記下電量(只顯示必要行)
adb shell dumpsys battery | grep -E "^  (AC|USB|Wireless) powered|^  level"

# 2. Doze 開關正常、沒有被強制
adb shell dumpsys deviceidle | grep -E "mLightEnabled|mDeepEnabled|mForceIdle"
#   預期:mLightEnabled=true mDeepEnabled=true / mForceIdle=false

# 3. 預設桌面(測前、測後各記一次)
adb shell cmd role get-role-holders android.app.role.HOME

# 4. 下一個鬧鐘與「會喚醒手機的鬧鐘」(兩者都要看)
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
- [ ] 沒有 1 小時內會響的「會喚醒手機」的鬧鐘(Samsung 請先確認 FMM,見第 8 節)
- [ ] Wake Locks 沒有 `dream:doze`(有的話關閉 Always On Display 再測;`batterystats` 的 `Screen doze` 為 0 ms 才算沒影響)
- [ ] 背景下載與同步先停止(例如 Play 商店自動更新)
- [ ] 手機放在穩定平面,測試期間不移動、不碰
- [ ] 兩邊比較時,widget 與已安裝 App 完全一致
- [ ] 記錄 adb 狀態(全程連線 / 已斷開)

---

## 4. 標準測試流程

### 步驟 1:重置統計(手機亮屏、已連線 adb)

```bash
adb shell dumpsys deviceidle unforce                       # 一定要做,避免先前 force-idle 汙染
adb shell dumpsys batterystats --enable full-wake-history
adb shell dumpsys batterystats --reset
```

### 步驟 2:處理無線偵錯(二擇一,見[第 5 節](#5-要不要斷開無線偵錯))

**A. 斷開(基準測試建議)**

```bash
adb shell settings put global adb_wifi_enabled 0
```

這行會關掉無線偵錯,連線隨之中斷,不需碰手機。若無效,改為手動到「開發人員選項」關閉「無線偵錯」,關完立刻鎖屏。

**B. 不斷開(方便)**:什麼都不做,測試期間**不要在電腦端下任何 adb 指令**。

USB 連線通常會變成充電狀態,不適合做這個測試。

### 步驟 3:鎖屏靜置

- 記下開始時間,**不再碰手機**。
- 時長至少抓「預期進入 deep idle 時間的 2 倍」(FMM 關閉後的 Samsung 約 2 小時)。
- 測試中只要亮屏,Doze 狀態機就會重來。

### 步驟 4:重新連線(僅方案 A)

在手機打開「無線偵錯」。連接埠每次重開都會變,請看手機畫面上的 IP:埠號:

```bash
adb connect <IP>:<埠號>        # 第一次需先 adb pair <IP>:<配對埠號>
```

### 步驟 5:連上後立刻匯出

亮屏與重新連線的幾分鐘也會被記錄,要趕快匯出:

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

## 5. 要不要斷開無線偵錯?

不斷開比較方便。**但從模型估算的 WiFi 耗電看,adb 全程連線可能有不小的影響,而且還沒有做過乾淨的對照,所以不要假設它可以忽略。**

### 目前資料

| 測試 | adb 狀態 | UID 1051(netd)WiFi | UID 1020(mDNS)WiFi | UID 2000(shell / adbd)WiFi |
|---|---|---|---|---|
| 6h | 全程連線 | 2.56 mAh(2m03s) | 0.533 mAh(25s) | 0.267 mAh(12.8s) |
| 1h37m | 已斷開(結尾重連) | 0.433 mAh(20.8s) | 0.534 mAh(25.6s) | 0.006 mAh |
| 3h10m | 已斷開 | 0.036 mAh | 0.053 mAh | 0.0002 mAh |
| 2h17m(FMM 關) | 已斷開 | 0.046 mAh | 0.051 mAh | 0.0005 mAh |

- 全程連線那次,這三個 UID 的 WiFi 耗電合計約 3.4 mAh / 6 小時。
- 但**1h37m 那次沒有全程連線,數值也偏高**,可能包含結尾重連與匯出的成本,所以不能全算成 adb 連線本身的耗電。

**整機的 WiFi 估算耗電(`Estimated power use` 的 `wifi`,模型值)差距更大:**

| 測試 | adb 狀態 | WiFi 估算耗電 | 每小時 | 備註 |
|---|---|---|---|---|
| 6h | 全程連線 | 14.40 mAh(App 歸屬 8.96) | **2.38 mAh/h** | FMM 開 |
| 1h37m | 已斷開(結尾重連) | 2.23 mAh | 1.37 mAh/h | FMM 開 |
| 3h10m | 已斷開 | 0.57 mAh | **0.18 mAh/h** | FMM 開 |
| 2h17m | 已斷開 | 0.42 mAh | **0.18 mAh/h** | FMM 關 |

- 全程連線時的 WiFi 估算耗電約為乾淨無 adb 測試的 **13 倍**。FMM 開不開沒有差別(3h10m 與 2h17m 都是 0.18),所以這個差距比較像是 adb 連線造成的。
- 這是模型估算,且 6h 與其他測試的時長、環境不同,**不能直接當成實際耗電差**:實際放電(`Discharge`)並沒有顯示一致的差距(6h 約 10.4 mAh/h,2h17m 約 7.9 mAh/h,3h10m 因 Play 商店下載而偏高)。
- `wakeupap=1051` 的頻率在有 adb 和無 adb 的測試中沒有一致差異(約 22 / 11 / 21 / 6 次每小時),所以 netd 的喚醒不一定是 adb 造成的。
- **進入 deep idle 的時間沒有證據顯示受 adb 影響**:6h(有 adb)與 3h10m(無 adb)都約 3 小時,但這兩次都有 FMM,**「FMM 關 + adb 開」從來沒測過**。

### 可能的影響(理論)

- adbd 在監聽並廣播 mDNS(`_adb-tls-connect`),連線期間有 TCP 保活封包。
- 你在電腦端下的任何指令(包含定時輪詢)都會喚醒手機。
- 影響大小無法從現有資料確定:以 UID 歸屬看約 0.5 mAh/h,以整機 WiFi 估算看最多約 2 mAh/h(約占基礎耗電的 10–25%),而電池計數器的解析度只有 ±4.5 mAh,短時間測試難以分辨。

### 建議

1. **日常比較**:不斷開可以,但全程不要下指令,且**所有要比較的測試都用同樣的 adb 狀態**,並記在記錄表裡;不同 adb 狀態的耗電數字不要直接比較。
2. **要精確的基準**:用方案 A(斷開)。
3. **要確認影響**:做一次對照,條件與「2h17m(FMM 關、無 adb)」完全相同,只改成 adb 全程連線,測 2 小時、不下任何指令。比較:第一次 deep idle 時間(基準 58 分)、`wlan_mbox_irq` 每小時次數(基準約 232 次/h)、WiFi 估算耗電(基準 0.18 mAh/h)、`Discharge`。

---

## 6. 判讀重點

| 檔案 | 關鍵欄位 | 意義 |
|---|---|---|
| `deviceidle` | `Idling history` | `light-idle` / `deep-idle` / `deep-maint` / `normal (alarm / unlocked / screen)` 時間軸與退出原因 |
| `deviceidle` | `mState` / `mLightState` | 目前狀態 |
| `batterystats` 開頭 | `Device light idling`、`Device full idling`(= deep idle) | 兩種休眠的總時間與占比。**light + full 加起來才是休眠比例**(例如 54.4% + 43.7% ≈ 98%) |
| `batterystats` 開頭 | `Time on battery screen off`、uptime % | 螢幕關閉比例;uptime 以外的時間 CPU 在 suspend |
| `batterystats` 開頭 | `Discharge` | 實際放電 mAh(見第 10 節) |
| `batterystats` | `Wakeup reason`(如 `wlan_mbox_irq`) | 是誰把 SoC 喚醒;WiFi 中斷不受 Doze 影響 |
| `batterystats` | `Estimated power use` | 各硬體與各 UID 的**模型估算**,只看占比 |
| `history` | `device_idle=light / full / off` | 精確的狀態切換時間 |
| `history` | `DeviceIdleController.deep.progression` | Doze 往下一階段的計時,通常相隔約 `idle_after_inactive_to` + 1 分 |
| `history` | `active=1000:"alarm"` | Doze 因為「有鬧鐘太近」而被拉回 active |
| `history` | `wakeupap=<uid>` | 喚醒被歸屬到哪個 UID |
| `history` | `top=<package>` | 開頭與結尾拿起手機時的前景 App,可佐證預設桌面 |

**實用指標**:第一次進入 deep idle 的時間、deep idle 占比、維護窗口是否呈 1h → 2h → 4h、`wlan_mbox_irq` 每小時次數。

---

## 7. 快速驗證(不用等數小時)

```bash
adb shell dumpsys deviceidle force-idle    # 強制進入 deep idle
adb shell dumpsys deviceidle               # 看 mState=IDLE
adb shell dumpsys deviceidle step deep     # 手動推進一個階段
adb shell dumpsys deviceidle get deep      # 查詢目前 deep 狀態
adb shell dumpsys deviceidle unforce       # 一定要還原
```

這只證明「系統能進入 deep idle」,不代表自然進入的時間。

---

## 8. 案例:Samsung「尋找我的手機」擋住 deep idle

### 現象

Samsung(One UI,Android 15)不論預設桌面是 One UI Home 還是 Lawnchair,都要約 3 小時才進入第一次 deep idle;Redmi 10 約 30 分鐘就進入。

### 找出「不是你設的」鬧鐘

`Next alarm clock` 出現了你沒設的時間。時鐘 App 的鬧鐘會落在整分(例如 08:30:00.000),帶秒與毫秒的通常是計時器或其他 App 排程的。該時間戳會一直更新,所以不要用時間戳 `grep`:

```bash
adb shell dumpsys alarm | grep -A8 "Next wake from idle"
adb shell dumpsys alarm > alarm.txt     # 完整分析時,在 alarm.txt 搜尋 "Next alarm clock"
```

實測的擁有者:`com.samsung.android.fmm`(尋找我的手機 / SmartThings Find),標籤 `*walarm*:defaultScanStartTimer`,`RTC_WAKEUP` 精確鬧鐘並帶 alarm clock 資訊,所以被顯示成「下一個鬧鐘」。

### 為什麼會擋住

Samsung 的 `min_time_to_alarm=1h`。據 AOSP 的行為,Doze 推進下一階段時,如果下一個會喚醒手機的鬧鐘距離現在不到這個時間,就放棄進入 deep idle 並回到 active 重新計時(history 會出現 `active=1000:"alarm"`);鬧鐘響起也會讓 Doze 退出。

### 時間證據(FMM 開)

| 測試 | FMM 鬧鐘觸發 | 之後兩個 `deep.progression` | 進入 deep idle |
|---|---|---|---|
| 6h | 1h54m42 | 2h25m42、2h56m43 | 2h56m53 |
| 6h | 4h50m57 | 5h21m57、5h52m57 | 5h53m15 |
| 3h10m | 1h57m02 | 2h28m02、2h59m02 | 3h01m01 |

每次進入 deep idle 都是 **FMM 鬧鐘響起後約 62 分鐘**(31 + 31 分)。更早的失敗嘗試也對得上:6h 測試第二個 progression(1h00m40)距離下一次 FMM 的 1h54m42 只剩約 54 分;3h 測試第一個 progression(0h57m48)距離 FMM 的 1h57m02 只剩約 59 分,都不到 1 小時。

### 驗證(FMM 整個關閉)

| 項目 | FMM 開(3h10m) | FMM 關(2h17m) |
|---|---|---|
| FMM 鬧鐘 | 有 | **無** |
| `deep.progression` | 0h57m48(被中斷)、2h28m02、2h59m02 | **0h27m02、0h58m03**(連續) |
| 第一次 deep idle | 3h01m01 | **0h58m13** |
| Deep idle 占比 | 4.6% | **43.7%**(一次完整 1h0m0s) |
| `Discharge` | 63.0 mAh | 18.0 mAh(誤差 ±4.5) |

> 「放棄進入」的機制是依 AOSP 行為推論,日誌沒有直接記錄,但時間吻合得很完整。

### 處理方式

1. 在「尋找我的手機」設定中**整個關閉**。實測只留「搜尋此手機定位」仍會出現該鬧鐘(甚至幾秒後就響);完全關閉後 `Next alarm clock` 才變空白。選項名稱依 One UI 版本略有不同。
2. 確認:
   ```bash
   adb shell dumpsys alarm | grep -i -A2 "next alarm clock"
   ```
   底下應為空白(只顯示 `NNN pending alarms`)。
3. **測完請恢復。** 這是防盜與找回手機的功能,關閉期間手機遺失將無法被找到。
4. 進階(只在測試期間):`adb shell am force-stop com.samsung.android.fmm`(可能被系統重啟),或 `pm disable-user --user 0 com.samsung.android.fmm`(用 `pm enable com.samsung.android.fmm` 還原)。

### 還沒解決:deep idle 只有 1 小時

FMM 關閉後,deep idle 在 1h58m13 被系統維護窗口(`idle_to=1h`)結束,接著 history 出現 `active=1000:"alarm"`,Doze 被拉回 active,而不是像 Redmi 那樣進入 `deep-maint` 後繼續更長的 deep idle。可能還有其他「會喚醒手機」的鬧鐘(例如 `imsservice` 的 `*walarm*`、`*job.deadline*`),但沒有證實。測試只到 2h17m,需要 4 小時以上才能確認。

### 對 launcher 比較的結論

Lawnchair 預設與 One UI Home 預設進入 deep idle 的時間幾乎相同,延遲來自 FMM 鬧鐘,與 launcher 無關。

---

## 9. 常見陷阱

- **預設桌面和以為的不同。** 測前、測後各用 `role get-role-holders` 驗一次。整段螢幕關閉的測試,`history` 裡沒有 launcher 的 `top=` 事件,無法靠檔案本身判斷(本專案曾因此誤把 One UI 預設的測試當成 Lawnchair)。
- **重置時手機已在 deep idle。** 這樣量不到「進入時間」。先亮屏一次再鎖屏開始。
- **忘記 `unforce`。** 強制狀態會一直保留到還原或重開機。
- **有鬧鐘、計時器或不認得的「下一個鬧鐘」。** 太近會讓 Doze 放棄進入 deep idle;鬧鐘響也會讓 Doze 退出(`normal (alarm)`)。
- **Always On Display。** Wake Locks 出現 `dream:doze`;`batterystats` 的 `Screen doze` 大於 0 也是同一件事。
- **亮屏。** 任何亮屏都會重設 Doze 計時,兩邊比較時亮屏秒數要一致。
- **手機被碰到或震動。** deep idle 需要「靜止」(significant motion 感測器)。
- **背景下載、同步。** 例如 Play 商店 3 小時內下載 20 MB,會讓耗電明顯上升。
- **WiFi 中斷與 Doze 無關。** `wlan_mbox_irq` 在 deep idle 期間仍會發生,來源多半是網路環境,換 launcher 無法改善。
- **Termux 影響很小。** 實測前景服務 2 小時耗電不到 0.03 mAh、無 wakelock;adb 走 localhost 不用 WiFi 硬體。
- **無線偵錯重開後埠號會變。** 要看手機畫面;匯出要趕快。

---

## 10. 耗電量怎麼算

- **實際放電**以 `batterystats` 開頭的 `Discharge`(mAh)為準,它來自電池庫倫計數器 `cc`,此機型每階 4.5 mAh,精度約 ±4.5 mAh。
- 想看某段時間的放電,用電池變化 log 的 `cc` 相減(Samsung 的 `dumpsys battery` 輸出含這些 log):

  ```bash
  adb shell dumpsys battery | grep ACTION_BATTERY_CHANGED
  ```

  例如 `cc:2493000` → `cc:2430000`,差 63000 = 63.0 mAh。
- `Estimated power use` 各項加總是**模型估算**,可能與實際差很多(6h 那次加總約 116 mAh,實際 63.0 mAh),只看占比。
- 電量百分比解析度更粗(1% 約 60 mAh),短時間測試不要用。
- 每個條件至少測 2 小時並重複 2 次。

---

## 11. 記錄表

| 項目 | 填寫 |
|---|---|
| 機型 / 系統版本 / 日期時間 | |
| 預設桌面(測前 / 測後) | |
| adb 狀態(全程連線 / 已斷開) | |
| `inactive_to` / `idle_after_inactive_to` / `min_time_to_alarm` | |
| `Next alarm clock` 與 `Next wake from idle` 擁有者 | |
| 測試時長 / 亮屏秒數 / `Screen doze` | |
| 第一次進入 deep idle 的時間 | |
| Light idle / Deep idle 占比與次數 | |
| 維護窗口間隔 | |
| `Discharge`(mAh)與每小時 | |
| `wlan_mbox_irq` 次數與時間 | |
| `wakeupap` 前 3 名 | |
| `Estimated power use` 前 5 名 UID(僅看占比) | |
| 備註(下載、同步、是否移動手機) | |

---

## 12. 附錄:向 AI 提問的範本與常見誤讀

### 提問範本

AI 的回答只會和你給的資料一樣好。建議這樣問:

> 我在 Samsung(One UI,Android 15)上測試 **Doze 的 deep idle**(`dumpsys deviceidle` 的 `deep-idle`、`batterystats` 的 `Device full idling`)。
> 條件:預設桌面 Lawnchair、無線偵錯已關閉、尋找我的手機已關閉,測試 2h17m,螢幕關閉。
> 數據:第一次進入 deep idle 為 0h58m13,deep idle 占比 43.7%,`Discharge` 18.0 mAh。
> 問題:deep idle 只維持 1 小時,history 出現 `active=1000:"alarm"`,可能是哪些「會喚醒手機」的鬧鐘造成?請附上判斷依據,並說明哪些是推測。

要點:指明機型與版本、用 Doze 專用名詞、附上關鍵數據或檔案、一次問一件事、要求區分「資料證據」與「推測」。

### AI 回答常見誤讀(本專案實際遇到的)

| 常見說法 | 實際情況 |
|---|---|
| 「WiFi kernel active 50–60% 是 adb 心跳造成」 | 關閉 adb 後仍是 53–63%,與 adb 無關 |
| 「Light idle 比例越高越好」或「Light idle 只有一半,品質不好」 | 要看 light + full 的總和:四次測試都是 95–99%(96.4%、99.0%、95.2%、96.4%)。light 比例高通常是因為 deep idle 太少(3h10m:light 90.6% + deep 4.6%);比例低是因為有更深的 deep idle(2h17m:52.7% + 43.7%) |
| 「`Device deep doze discharge 4.50 mAh` 代表有進入 deep」 | 4.5 mAh 只是電池計數器的一個階距,沒有判斷意義 |
| 「UID 1000 sensors 5h25m 代表感測器一直開著」 | 那是多種感測器使用時間的加總 |
| 「限制 Google Play 服務背景可減少干擾」 | GMS 只占約 6%,而 LINE、Telegram、Gmail 的推播都靠它,不建議 |
| 「`findmydevice.spot` 是 Samsung FMM」 | 那是 Google 的「尋找我的裝置」(在 GMS 內),與 Samsung FMM 是不同服務 |
