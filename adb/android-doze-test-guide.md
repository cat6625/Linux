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
> 13. [這套方法能回答什麼、不能回答什麼](#13-這套方法能回答什麼不能回答什麼)
> 14. [給 AI 分析:先過濾,不要丟完整檔](#14-給-ai-分析先過濾不要丟完整檔)

---

## 0. 名詞:deep idle、deep sleep、深度休眠

「deep sleep」在 Android 上至少有三種意思,提問或寫報告時請先講清楚:

| 說法 | 實際指的是 | 在哪裡看 |
|---|---|---|
| **Doze 的 deep idle**(本文討論的) | 螢幕關閉、靜止一段時間後,系統限制 App 網路、job、alarm 的深度休眠 | `dumpsys deviceidle` 的 `deep-idle`;`batterystats` 的 `Device full idling` |
| **CPU deep sleep(suspend)** | CPU 進入 suspend 狀態(DevCheck、CPU Spy 之類 App 顯示的「深度睡眠」) | `batterystats` 的 uptime 相對 realtime;例如 uptime 4.6% 代表 CPU 有約 95.4% 時間在 suspend |
| **Samsung「深度休眠應用程式」** | One UI 電池設定中,對不常用 App 的背景限制(設定 → 電池 → 背景使用限制) | 設定畫面,和 Doze 是不同機制 |

建議用「**Doze 的 deep idle(`DeviceIdleController`)**」描述本文的問題,並附上 `deviceidle` 與 `batterystats` 的數據。

### DevCheck 的「深度睡眠」和 light-idle / deep-idle 有關係嗎?

**有關聯,但不是同一件事。**

- DevCheck 的「深度睡眠」= CPU 在 suspend 的時間 ÷ 開機至今的時間,也就是 `1 − uptime ÷ realtime`。實例(Galaxy M14 5G):`dumpsys meminfo` 顯示 Uptime 11h15m、Realtime 44h45m → 約 75%;同一時段 DevCheck 截圖顯示 73%(運作 1 天 21 小時 40 分,深度睡眠 1 天 9 小時 31 分),兩者吻合。
- Doze 的 light idle / deep idle 是**軟體**狀態:限制 App 的網路、job、alarm。它讓 CPU 更容易進入 suspend,但兩者不能互換:
  - 整夜測試(6h07m):Doze deep idle 82.2%,CPU 深度睡眠 95.4%。
  - 電腦醒著並連線的異常時段:Doze 仍在 deep idle,但 CPU 清醒約 98%,DevCheck 的深度睡眠會明顯下降。
  - 反過來,Doze 沒進 deep idle(只在 light idle)時,CPU 也可能睡得很多。
- DevCheck 的數字是**開機至今**的累計,包含白天使用,所以只有 73%。要用它檢查待機:睡前與起床各截一張圖,用差值算 `Δ深度睡眠 ÷ Δ運作時間`,整夜靜置通常應該在 90% 以上(我們的測試是 95.4%)。
- 沒有電腦的人要看 Doze 狀態:需要在手機上執行 `dumpsys deviceidle`(例如用 aShell / Termux 搭配無線偵錯);DevCheck 本身看不到 light / deep idle。

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
| 5 | 6h07m(Lawnchair 預設)| FMM 關、無線偵錯**開**、Ubuntu 全程睡眠 | 重置時已在 deep idle | **82.2%**(最長一段 3h44m) | 94.5 mAh(約 15.4 mAh/h) |
| — | Redmi 10(MIUI)| 同樣裝 Lawnchair | 約 27–31 分 | — | — |

**結論:**

1. **Lawnchair 與 launcher 都不是原因。** Lawnchair 預設與 One UI 預設進入 deep idle 的時間幾乎相同(3h01m 對 2h56m),Lawnchair 本身耗電可忽略(3h10m 內 0.0347 mAh,無任何喚醒紀錄)。
2. **adb 不是延遲進入的主因。** 6h(adb 全程連線)與 3h10m(關閉無線偵錯)都約 3 小時才進入。無線偵錯開著、電腦睡眠時,也沒有看到額外耗電;約 52 mAh/h 的持續高耗電只出現在「電腦醒著並連線」的期間(用 `journalctl` 對時間,見[第 5 節](#5-要不要斷開無線偵錯))。
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

不斷開比較方便。**實測結果:無線偵錯開著、但電腦端安靜(例如電腦睡眠)時,看不出明顯影響;出現過一次持續高耗電,發生在電腦持續使用的期間(見下方「實測更新」)。**

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

### 實測更新:adb 開著,但電腦端安靜 / 活躍

三組 FMM 關閉的測試(同一支手機、同一個 Lawnchair 預設):

| 測試 | 無線偵錯 | 電腦端狀態 | 結果 |
|---|---|---|---|
| A. 2h17m | 已斷開 | — | 第一次 deep idle 0h58m13;uptime 約 10%;約 7.9 mAh/h |
| B. 約 2h21m 區段(統計未重置,與 A 相減得出) | **開** | **約 18:22 起持續使用**(15 分鐘無操作才自動睡眠) | 前 36 分鐘正常(約 8 mAh/h);3h29m(約 18:22:47)起 CPU 清醒約 98%、WiFi 驅動 wakelock 持續、suspend 被中止、**約 52 mAh/h**,持續至少 1h09m;deep idle 仍在 |
| C. 2h38m | **開** | **重置後立刻 `systemctl suspend`** | deep idle 100%、uptime 6.3%、無異常;31.5 mAh(約 11.9 mAh/h,±4.5 mAh);`wlan_mbox_irq` 562 次(約 212 次/h) |
| D. 6h07m | **開** | **重置後立刻睡眠,整段約 100% 睡眠**(`journalctl`:00:36:55 → 06:43:12) | deep idle **82.2%**、light 17.5%、uptime 4.6%;無持續異常;94.5 mAh(約 15.4 mAh/h);`wlan_mbox_irq` 772 次(約 126 次/h);WiFi kernel active 60.2% |

- **用 Ubuntu 的睡眠紀錄(`journalctl`)對時間,相關性很強。** 電腦 17:26:20 睡眠、**18:22:40 喚醒**,而手機的異常從 **18:22:47** 開始,只差 7 秒;電腦睡眠的時段手機都很安靜。同樣的規律在兩段獨立的時間窗各出現一次:

  | 手機時段 | 電腦睡眠比例 | 手機放電 | 每小時 |
  |---|---|---|---|
  | 14:53–17:10(A) | 96% | 18 mAh | 7.9 mAh/h |
  | 17:10–17:36 | 39%(17:26 前醒著、匯出檔案) | 22 mAh | **51.5 mAh/h** |
  | 17:36–18:13 | 100% | 5 mAh | 8.2 mAh/h |
  | 18:23–19:25 | **0%** | 54 mAh | **52.3 mAh/h** |
  | 21:30–00:09(C) | 99% | 31.5 mAh | 11.9 mAh/h |

  所以「**電腦醒著、並且與手機的無線 adb 連線**」時,手機約多耗 **40–45 mAh/h**(約 6 倍);電腦睡眠時,無線偵錯開著也很安靜。
- 輔助證據:mDNS(UID 1020)接收封包,電腦活躍的 B 約 540 個/小時,電腦睡眠的 C 約 190 個/小時(約 2.8 倍)。UID 2000(adbd)在 B 的流量(約 1.6 MB)與匯出 `run_*` 檔案的大小相當,屬於匯出,不是持續連線。
- **C 的放電(約 11.9 mAh/h)略高於 A(約 7.9 mAh/h)**,但兩者誤差範圍(±4.5 mAh)幾乎重疊,且測試時段、手機電量不同,不能歸因於 adb。
- C 重置時手機**已經在 deep idle**,所以不能比較「進入時間」;但它顯示 deep idle 的維護窗口正常指數放大:1h → 2h → 4h(`deviceidle` 紀錄),沒有 `active=1000:"alarm"` 的中止。
- **還沒分離的部分:** 是 adb 連線本身(host 的連線活動),還是電腦醒著時的區網流量(桌面 / mDNS 等),目前資料分不出來。
- **6h 那次不能用同一個理由解釋。** 那次電腦 99% 在睡眠,但仍有每約 16 秒的 netd 喚醒與較高的 WiFi 估算耗電,原因還沒找到(那次 FMM 是開的,可能相關,但未驗證)。
- **D(6h07m)的結構**:重置時手機已在第 4 段 deep idle;0h38m01 維護窗口後 3 分鐘進入下一段 deep idle,持續 3h44m36s,在 4h25m41 被 `active=1000:"alarm"` 中止(沒有撐到 6 小時的上限)。**3 分鐘後(4h28m42)就有一次 FMM 的 `defaultScanStartTimer` 鬧鐘**:即使尋找手機已「關閉」,這次 6 小時仍觸發了 1 次。接著重新計時,4h28m42 + 31 分 + 31 分 = 5h30m43,deep idle 於 5h30m53 恢復,和先前的規律完全一致。電腦全程睡眠時,deep idle 占比是各次測試最高(82.2%)。
- **D 的耗電分布**(用電池 `cc` 拆):0h38–0h41 的維護窗口約 18 mAh(約 3 分鐘內,伴隨 `cellular_high_tx_power`);deep idle 約 9.8 mAh/h(`Device deep doze discharge` 49.5 mAh / 5h02m);light idle 約 25 mAh/h(27.0 mAh / 1h04m)。所以**長時間 deep idle 之後的維護窗口會有一次突發耗電,light idle 比 deep idle 貴**;light idle 比例低是好事,不是壞事。
- **D 與 One UI 6h(FMM 開,00:10–06:13)是同一段夜間、電腦也都在睡眠**,可以直接比:`Discharge` 94.5 對 63.0 mAh,但 deep idle 占比是 82.2% 對 19.3%。**不能因此說「FMM 關比較省電」或「比較耗電」**:One UI 6h 的模型估算加總(約 116 mAh)與它的 `Discharge` 不一致,兩邊還差了預設桌面與 FMM 兩個變因。FMM 關閉確定的好處是**大幅縮短進入 deep idle 的時間**。

### 可能的影響(理論)

- adbd 在監聽並廣播 mDNS(`_adb-tls-connect`),連線期間有 TCP 保活封包。
- 你在電腦端下的任何指令(包含定時輪詢)都會喚醒手機。
- 影響大小無法從現有資料確定:以 UID 歸屬看約 0.5 mAh/h,以整機 WiFi 估算看最多約 2 mAh/h(約占基礎耗電的 10–25%),而電池計數器的解析度只有 ±4.5 mAh,短時間測試難以分辨。

### 建議

1. **測試期間讓電腦睡眠**(例如重置後立刻 `systemctl suspend`),或在電腦端 `adb disconnect`。電腦睡眠時,無線偵錯開著看不出影響;不要在測試期間使用電腦或下 adb 指令。
2. **記錄電腦的睡眠 / 喚醒時間**,事後用來對照異常區段(Ubuntu):

   ```bash
   journalctl -b | grep -E "systemd-sleep|PM: suspend"
   ```

   以 `Performing sleep operation 'suspend'`(開始睡眠)與 `System returned from sleep operation 'suspend'`(喚醒)為準;`Suspending console(s)` 之類的 kernel 行是喚醒後才補印的,時間不準。

3. **所有要比較的測試用同樣的 adb 與電腦狀態**,並記在記錄表裡;不同狀態的耗電數字不要直接比較。
4. **電腦睡眠後再喚醒時 adb 會離線**,需重新 `adb connect <IP>:<埠號>`(曾先顯示 `offline` 或 `No route to host`,稍等再試即可);匯出要趕快。
5. **要精確的基準**:仍用方案 A(斷開無線偵錯)。
6. **要分離原因**(各測 30–60 分鐘就夠,因為差距約 44 mAh/h,30 分鐘約 22 mAh,遠大於 ±4.5 mAh 的誤差;每組開始前先 `batterystats --reset`):
   1. 電腦醒著 + adb 連線中(不下指令)。
   2. 電腦醒著 + 在電腦端 `adb disconnect`(手機的無線偵錯仍開著)。
   3. 電腦醒著 + 手機關閉無線偵錯。
   比較三組的放電與 `wlan_mbox_irq` / suspend 中止次數,即可知道代價來自連線本身還是電腦醒著。

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
>
> **注意:「整個關閉」不等於 FMM 鬧鐘完全消失。** FMM 關閉後的累計約 13 小時測試中,仍觀察到 1 次 `defaultScanStartTimer`(第 5 組 6h07m 的 4h28m42),並造成同樣的「中止 → 約 62 分鐘後才回到 deep idle」。頻率比開啟時低很多(開啟時約每 3 小時 1 次),所以要用摘要腳本(第 14 節)檢查每次測試有沒有出現。

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
- **電量百分比不是線性、也不是固定的 mAh。** 本機實測:`level` 每掉 1% 的兩次跳變之間,電池 `cc` 只差約 **45–47 mAh**(例如 02:49:43 → 06:13:50 為 45 mAh;42% → 40% 共 94.5 mAh;47 → 44% 共約 3 級,每級約 45 mAh),而標示容量 6000 mAh 的 1% 應是 60 mAh。可能是電池老化、容量估計值(`Estimated battery capacity` 5830)不準,或百分比對電壓曲線的對應並非線性,這裡無法判斷原因。重點是:
  - 不要用「百分比 / 小時」算耗電,短時間測試(< 2 小時)百分比通常只變 0–1 級,毫無意義。
  - 同一個 `mAh/h` 在不同狀態差很大:deep idle 約 5–10、light idle 約 20–25、維護窗口突發可達數百(例如 3 分鐘內 18 mAh),所以平均值會隨測試長度與狀態比例改變。
  - 請用 `Discharge` / `cc` 的 mAh,並看分段曲線(摘要腳本會輸出)。
  - 再加一個證據(`dumpsys battery`):`Charge counter` 1593 mAh、level 35% → 每 1% 約 45.5 mAh,推算滿電約 4550 mAh;電池變化 log 20 筆的 `cc ÷ level` 都落在 45.2–46.3 mAh/%。也就是說 `cc` 近似是以約 4.55 Ah 滿電換算的電量(解析度約 0.1%),**不要假設容量就是標示的 6000 mAh**(用 6000 算會把「%/小時」低估約 25%)。
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
| 「UID 1051 是 `com.samsung.android.lool`」「`u0a1204` 可能是 Chrome」 | 1051 是 **netd**(系統網路服務),`u0a1204`(uid 11204)是 **LINE**。UID 一定要用 `--checkin` 換成套件名稱再判讀,不要憑印象猜 |
| 「維護窗口 `deep.maintenance` 時 deep idle 被中斷,之後進入較長的活躍期」 | 維護窗口是 Doze 的正常設計:長時間 deep idle 後讓 App 把延後的 job 一次做完,實測約 3 分鐘(0h38m01 → 0h41m05)就回到 deep idle,並不是「較長的活躍期」 |
| 「測試矩陣:Wi-Fi 關 + ADB 開」 | 無線 adb 需要 WiFi,這個組合不可能成立 |
| 「`pm disable-user com.google.android.gms/.findmydevice…`」 | `pm disable-user` 只能用在套件,不能用在元件;而且停用 GMS 元件可能影響推播與定位,不建議 |
| 「以 6000 mAh 估算,約每小時 0.26%」 | 實測每 1% 約 45 mAh(約 4550 mAh),同樣 15.4 mAh/h 應是約 0.34%/小時 |
| 「Java Heap Alloc 約 80.2 MB」 | 80.2 MB 是 native heap(70.4 MB)與 Dalvik heap(9.9 MB)的**合計**,Java heap 配置只有約 9.9 MB |

---

## 13. 這套方法能回答什麼、不能回答什麼

### 原本的問題與演變

最初的問題是「換桌面後,會不會省記憶體、省電?」,實驗設計是 One UI Home 對 Lawnchair 各測 2 小時。實際做下來發現變因太多(尋找我的手機的鬧鐘、adb 與電腦狀態、亮屏秒數、Play 商店下載、網路環境),**無法準確比較兩個 launcher**。於是問題改成:**換桌面後系統是否正常?如果不正常,能不能找出原因?**

### 能回答

| 問題 | 能否 | 依據 |
|---|---|---|
| 能不能進入 deep idle、何時進入、占比多少 | ✓ | `device_idle=full`、`Device full idling` |
| 為什麼延遲或被打斷 | ✓ | `deep.progression`、`active=1000:"alarm"`、會喚醒手機的鬧鐘擁有者(例如 FMM) |
| 待機時哪些 App / 服務在喚醒手機 | ✓(相對排名) | `wakeupap`、`Wakeup reason`;注意 `wlan_mbox_irq` 多數無法歸屬 |
| 某個 App(含 launcher)待機時有沒有異常 | ✓ | UID 耗電、wakelock、alarm、job、CPU、網路 |
| 待機耗電是否異常、異常出現在哪一段 | ✓ | 用 `cc` 分段看 mAh/h,再和外部事件對時間(例如電腦醒著時約 52 mAh/h) |
| 測試方法本身有沒有影響結果 | ✓ | 電腦睡眠 / 喚醒紀錄對時間 |

### 不能回答

| 問題 | 原因 |
|---|---|
| One UI Home 與 Lawnchair **哪個比較省電** | 待機時兩者的 UID 耗電都只有 0.01–0.09 mAh(2–6 小時),不到電池計數器解析度(4.5 mAh)的 1/50;測試之間的雜訊可達數十 mAh。launcher 的耗電主要發生在**亮屏使用**,這套方法沒有測 |
| **記憶體**有沒有省 | 完全沒測 |
| **日常使用**(亮屏)是否正常 | 只測了螢幕關閉的待機 |
| 精確的 mAh/h | 解析度 ±4.5 mAh,短時間測試不夠 |
| 長期趨勢 | 每個條件只測 1–2 次 |
| 因果(而不只是相關) | 例如「電腦醒著 + adb 連線」只是高度相關,還沒分離 |

### 這支手機的待機是否正常?

在「FMM 關、電腦睡眠、Lawnchair 預設」的測試下:

- deep idle 進得去,約 1 小時內(FMM 關)或維持 82%(6h07m);Lawnchair 本身沒有任何喚醒紀錄。
- 沒有看到 App 長時間持有 wakelock(最長是 Galaxy Store 的 `PollJobService`,2 分 7 秒);沒有 kernel wakelock 風暴(除了「電腦醒著並連線」的測試干擾)。
- 待機耗電約 5–15 mAh/h(含維護窗口突發),以實測每 1% 約 45 mAh 換算約 0.1–0.35%/小時。這是單一樣本,我沒有其他手機的基準可以比,所以只能說**沒有看到明顯異常**。
- 唯一的大異常(約 52 mAh/h)是測試方法造成的(電腦醒著並連線),不是手機日常。

### 要回答原本的問題,需要另外做什麼

**記憶體(省不省):**

```bash
# 啟動的 launcher 進程 PSS / RSS(請在相同使用情境下量,重複 3 次)
adb shell dumpsys meminfo ch.deletescape.lawnchair.plah | head -40
adb shell dumpsys meminfo com.sec.android.app.launcher | head -40
# 系統整體(Free RAM 不重要,Android 會把空閒記憶體拿來當快取)
adb shell dumpsys meminfo | grep -E "Total RAM|Free RAM|Used RAM|Lost RAM"
```

比較的是**launcher 進程自己的 PSS**,不是系統的可用記憶體。三個 launcher 同時常駐時各自都會佔用記憶體,要一起列出。

**日常耗電(亮屏使用):**

1. 早上 `batterystats --reset`,晚上匯出一整天;用 `Screen on discharge ÷ 亮屏時數` 與 launcher UID 的耗電、`Top for` 時間比較。
2. 兩個 launcher 輪流用 ABAB 各 2–3 天,盡量讓使用習慣相同,可降低「某一天特別忙」的影響。
3. 尋找我的手機狀態、adb 狀態每天都要一致,並且全程斷開 adb。

---

## 14. 給 AI 分析:先過濾,不要丟完整檔

完整的 `dumpsys batterystats` 約 600 KB–1 MB,絕大部分是與問題無關的清單(白名單、每個 UID 的細節等)。實務上直接丟整份給 AI 常得到離題或錯誤的回答;**先過濾出關鍵欄位,回答品質明顯較好**(使用者的經驗:Gemini 需要過濾後的關鍵字檔才能回答得比較好)。

### 方法 1:用摘要腳本(推薦)

`doze_summary.py`(與本文件放在一起)會把完整檔濃縮成約 100 行,包含:時長、放電、light / deep idle、第一次進入 deep idle、`deep.progression` 與被鬧鐘中止的時間、FMM 鬧鐘、**分段放電曲線**、CPU 清醒區段、喚醒來源、kernel wakelock、耗電前幾名 UID、指定 UID(例如 launcher)的細節。

```bash
python3 doze_summary.py run_full.txt
python3 doze_summary.py run_full.txt --uids u0a1361,u0a125                 # 指定 launcher UID
python3 doze_summary.py run_full.txt --suspend suspend.txt                 # 對照電腦睡眠比例
python3 doze_summary.py run_full.txt --deviceidle run_deviceidle.txt       # 附上 Doze 設定與最後狀態
```

v2 的額外選項:`--checkin run_checkin.txt`(把 UID 換成套件名稱)、`--pkg 套件1,套件2`(列出 launcher 等指定 App 的耗電與 CPU)、`--mem meminfo.txt`(記憶體摘要,換算成 MB)、`--battery battery.txt`(每 1% 約幾 mAh)。摘要也會列出時鐘時間、**突發耗電**(6 分鐘內掉 ≥ 9 mAh,並附上同時間的 Doze 事件與 job 前幾名),以及「CPU 深度睡眠比例」(DevCheck 的概念)。

### 方法 2:手動 grep 關鍵字

```bash
grep -E "Time on battery|Discharge|doze discharge|Device (light|full) idling|Idle mode|Screen on|Wifi kernel active|Total partial wakelock" run_full.txt
grep -E "Wakeup reason|Kernel Wake lock" run_full.txt | head -20
grep -E "device_idle=|DeviceIdleController\.(deep|light)|active=1000:\"alarm\"|defaultScanStartTimer|charge=" run_history.txt
```

### 提問時一併附上

- 機型 / 系統版本、**測試條件**(預設桌面、尋找我的手機狀態、adb 與電腦狀態、有沒有亮屏、測試時長)。
- 摘要(或過濾後的檔案),**不要附原始大檔**,除非 AI 要求。
- 你要回答的問題,以及「請區分資料證據與推測」。
- 提醒 AI 避開常見誤讀(見第 12 節):電量百分比不是線性、light idle 比例要和 deep idle 合起來看、`Discharge` 以電池計數器為準。
