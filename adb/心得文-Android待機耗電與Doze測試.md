# Android 待機耗電與 Doze 測試心得:從「換桌面會不會省電」到「系統是否正常」

> **測試機**:Samsung Galaxy M14 5G(SM-M146B、Exynos 1330、Android 15 / One UI),另用紅米 10(MIUI)做對照。
> **時間**:2026-11-13 ~ 11-17。**環境**:家用 mesh 路由器(無法調整參數)、預設桌面在 One UI Home 與 Lawnchair 之間切換。
> **聲明**:所有數據都來自這一支手機、每個條件只有 1–2 次樣本;「證實」與「推論」我會分開標示。文中沒有收錄裝置序號、IP 等個人資訊。

---

## 一句話結論

1. **launcher(One UI Home 或 Lawnchair)不是待機耗電的原因**:Lawnchair 3 小時的 UID 耗電 0.035 mAh、沒有任何喚醒紀錄。
2. **這支手機以前要約 3 小時才進得了 deep idle,元兇是 Samsung「尋找我的手機」的 `OfflineFindingService` 一直在背景執行**:設定頁的三個開關都是關的,服務卻已經跑了 40 小時。手動「停止」後,第一次 deep idle 在 **1h02m**,之後 1h → 2h → 4h 的維護窗口完全正常。
3. **正常待機的基準**(深夜 7h45m、Lawnchair 為預設、拔掉 USB):deep idle **86.4%**、放電 **85.5 mAh(約 11.0 mAh/h)**,以每 1% ≈ 45 mAh 換算約 0.24%/小時。
4. **WiFi kernel active 約 51–66% 是常態,不是問題**:有線、無線、哪個 launcher、深夜白天都差不多;模型估算 WiFi 只占約 1% 的耗電。
5. **無線 adb 的代價取決於電腦**:電腦睡眠時看不出影響;電腦醒著並連線時手機約多耗 40 mAh/h(約 52 mAh/h)。
6. **換桌面不會省記憶體**:Lawnchair 為預設時,One UI Home 仍常駐;等於多了一個 Lawnchair(約 140 MB)。
7. **用這套方法能回答「系統待機是否正常」,不能回答「哪個 launcher 比較省電」。**
8. **AI 能幫忙,但要給它「過濾後的摘要」與「已驗證的事實」**;它們最常犯的錯是把相關說成因果、把模型估算當實測、用絕對語氣。

---

## 1. 緣起:原本想回答的問題

一開始是 ChatGPT 幫我設計的實驗:**換桌面(One UI Home → Lawnchair)後,會不會省記憶體、省電?** 做法是各測 2 小時,比較放電量。

卡關的地方:

- **變數太多**:尋找我的手機、adb 連線、亮屏秒數、Play 商店下載、網路環境,任何一個都能讓數字差十倍。第一組 2 小時的放電是 13.5 對 94.5 mAh,但其實不能歸因到 launcher。
- **資料太大**:一份 `dumpsys batterystats` 約 600 KB–1 MB,不能全部貼給 AI;貼了常常得到離題的回答(我以前把整份丟給 Gemini 就是這樣)。
- **各個 AI 的回答互相矛盾**:有的叫我關 WiFi、有的叫我限制 GMS、有的說 adb 是主因。

於是問題改成:**換桌面後,系統是否正常?如果不正常,能不能把原因找出來?** 這個問題用這套方法是答得出來的;「誰比較省電」則不是(見第 4 節)。

---

## 2. 測試方法的演進

| 方式 | 優點 | 問題 | 結論 |
|---|---|---|---|
| 手機版 Termux + 鬧鐘 | 不用電腦 | 要開無線偵錯才能在手機上跑 `dumpsys`;設鬧鐘、結尾亮屏、Termux 本身都是變因;Termux 的長 `sleep` 在 Doze 下不可靠;MacroDroid 我也不會用 | 放棄 |
| 電腦 + 無線 adb | 手機不用接線,可以長時間放著 | 電腦要睡眠(否則手機約多耗 52 mAh/h);睡眠醒來後 adb 常是 `offline` / `No route to host`,需要重試甚至亮屏手機 | 可用,需自動重連 |
| 電腦 + USB(真的拔線、接回) | 不依賴 WiFi,拔線期間手機完全不被打擾 | 接回 USB 要解鎖授權;接回的瞬間手機開始充電,Doze 會退出,接回後的 `Charge counter` 會被充電污染 | **最乾淨** |

**越自動化,越不會犯錯,數據也越不失真。** 最後我做了兩支腳本(重置 → 待機 → 擷取 → 產生摘要),以及一支把完整檔濃縮成約 100–150 行的摘要腳本:

- `doze-test.sh`(無線 adb;電腦重置後立刻睡眠,醒來自動重連)
- `doze-test-usb.sh`(USB;提示「請拔除 USB」,接回後自動偵測並繼續,我不用輸入任何指令)
- `doze_summary.py`(把 `batterystats` 變成可以貼給 AI 的摘要)

幾個設計重點:最後才 `batterystats --reset`、事前檢查下一個「會喚醒手機」的鬧鐘、擷取檔是否為空、拔線 / 接線自動偵測、`Time on battery` 驗證、以及 `adb: more than one device/emulator` 的處理(關掉無線偵錯後,電腦的 adb 還留著舊的 `192.168.x.x:埠號 offline`,腳本一開始會 `adb disconnect` 並只選 USB 裝置)。

---

## 3. 重要發現

### 3.1 Doze 的時間表

- Samsung 的設定:`inactive_to` 30 分 + `idle_after_inactive_to` 30 分 → history 裡會有兩個相隔約 31 分的 `deep.progression`,**第一次 deep idle 約在 1h02m**;之後 deep idle 的維護窗口間隔是 **1h → 2h → 4h**(指數放大,上限 6h)。
- 紅米 10(15 + 15 分):約 27–31 分就進入,整夜連續約 7 小時的 deep idle,同樣是 46 分 → 2h → 4h。
- **`min_time_to_alarm=1h`**:Doze 每往下一階,都會檢查「下一個會喚醒手機的鬧鐘」;如果不到 1 小時,就放棄進入 deep idle、退回 active(history 會出現 `active=1000:"alarm"`)。紅米 10 的這個值只有 10 分鐘。

### 3.2 為什麼以前要約 3 小時才進 deep idle

一開始我也懷疑 launcher、懷疑 adb、懷疑 WiFi,最後是靠兩樣東西找到的:`dumpsys alarm` 與 `batterystats` 的 history。

- **`dumpsys alarm` 的「下一個會喚醒手機的鬧鐘」是 `com.samsung.android.fmm`(尋找我的手機)的 `defaultScanStartTimer`**,`flags=0x3`,是 Alarm clock;我沒有設任何鬧鐘。
- 時間對得很精確:每次進入 deep idle,都是 FMM 鬧鐘響後約 62 分鐘(31 + 31);更早的失敗嘗試,是第二個 `deep.progression` 時距離下一個 FMM 鬧鐘只剩約 54–59 分鐘,不到 1 小時。
- 設定頁(「允許搜尋此手機定位」「傳送最後位置」「離線搜尋」)全部關閉,但「使用中的應用程式」裡 `OfflineFindingService` 還顯示「已由應用程式啟動」,**運作了 40:04:11**——往回推,正好是我試各個開關的時候。**很可能不是它「自己又起來」,而是被啟動後就從沒停過**(這是推論)。
- **手動按「停止」之後**:4h17m + 2h27m + USB 的 1h09m + 7h45m,**沒有任何 `active=1000:"alarm"` 中止、也沒有 FMM 鬧鐘**;第一次 deep idle 在 1h02m,維護窗口完全是 1h → 2h → 4h。

另外觀察到:FMM 的計時會被「取消並重新排定 +2 小時」(例如 03:02:14 取消後,正好 2 小時後的 05:02:14 觸發)。初步推論是:重新排定發生在 Doze 計時起點附近時,第二個 progression(約 62 分)距離鬧鐘只剩約 58 分鐘,就被放棄。這個推論和 One UI 那組完全吻合,但我沒有證實是什麼事件會重新排定它。

### 3.3 無線 adb:代價看電腦醒不醒

把手機的耗電曲線和 Ubuntu 的睡眠 / 喚醒紀錄(`journalctl`)對時間:

| 手機時段 | 電腦睡眠比例 | 手機放電 |
|---|---|---|
| 14:53–17:10 | 96% | 7.9 mAh/h |
| 17:10–17:36 | 39% | **51.5 mAh/h** |
| 17:36–18:13 | 100% | 8.2 mAh/h |
| 18:23–19:25 | **0%** | **52.3 mAh/h** |
| 21:30–00:09 | 99% | 11.9 mAh/h |

電腦 18:22:40 喚醒,手機的異常 18:22:47 開始,只差 7 秒。所以**電腦睡眠時,無線偵錯開著也很安靜;電腦醒著並連線時,手機約多耗 40–45 mAh/h**。是 adb 連線本身,還是電腦醒著時在區網發出的廣播(mDNS 等),這份資料分不出來(推論)。

### 3.4 WiFi kernel active 50–60%:嚇人,但不是問題

| 測試 | 連線方式 | 時段 | kernel active | `wlan_mbox_irq` 每小時 |
|---|---|---|---|---|
| One UI 3h15m | 無線 adb | 深夜 | 66.2% | 約 79 |
| Lawnchair 6h07m | 無線 adb | 深夜 | 60.2% | 約 126 |
| **Lawnchair 7h45m** | **USB 拔線(沒有任何 adb 連線)** | **深夜** | **59.2%** | 約 149 |
| One UI 4h17m | 無線 adb | 早晨 | 62.4% | 約 233 |
| One UI 2h27m | 無線 adb | 下午 | 54.9% | 約 243 |
| Lawnchair 1h09m | USB 拔線 | 晚上 | 53.2% | 約 209 |

- 在所有條件下都是 **51–66%**,**完全不連 adb 的 USB 拔線(53.2%、59.2%)與無線 adb 沒有差別**,所以它和 adb、launcher 無關。
- 唯一看得出差別的是**時段**:深夜 `wlan_mbox_irq` 約 79–149 次/小時,白天與傍晚約 209–243 次。
- **它不是耗電比例**:7h45m 的模型估算 WiFi 只有 0.85 mAh(約 1%);`wlan_ma` 4m22 + `hip4_wake_lock_tx` 3m18 共 7.7 分鐘,只占 1.7% 的時間;CPU 深度睡眠仍有約 95%。它也不會擋住 deep idle(59.2% 的組別 deep idle 達 86.4%)。
- 路由器不能調,所以能做的只有接受它。

### 3.5 耗電怎麼量:百分比不是線性

- 實際放電以 `batterystats` 的 `Discharge`(來自電池計數器 `cc`)為準,**解析度約 4.5 mAh**。短時間的區段看到 0 或 14 mAh,往往只是差一個計數階距。
- **電量百分比不是固定的 mAh**:`dumpsys battery` 的 `Charge counter` ÷ `level` 都落在 45 mAh/%,推算滿電約 4500 mAh,而標示容量是 6000(Rated 5830)。原因我判斷不了;`cc` 近似是由電量換算的,所以不要拿「%/小時」算耗電,短測更是無意義。
- **`Estimated power use` 是模型估算**,只看占比;實際放電以 `Discharge` 為準。
- 同一個 mAh/h 在不同狀態差很大:deep idle 約 5–10、light idle 約 20–25、維護窗口突發可達數百(6h07m 那次 3 分鐘內約 14–18 mAh)。長時間 deep idle 不是免費的,維護窗口那一下會把延後的工作一次做完。

### 3.6 launcher 本身與記憶體

- **耗電**:deep idle 運作良好的幾組(Lawnchair 11.0、11.9、15.4 mAh/h;One UI 12.8、13.6 mAh/h)互相重疊,差異小於測量誤差。launcher 的 UID 耗電都不在前列(Lawnchair 3h10m 只有 0.035 mAh)。
- **記憶體**:`dumpsys meminfo` 只是單一時間點,受換出(swap)狀態影響很大。One UI Home 的私有記憶體在 14.6–78.1 MB 之間跳動,Lawnchair 在 14.8–58.5 MB;PSS + Swap PSS 約 225–285 MB(One UI Home)對 155–224 MB(Lawnchair),方向上 Lawnchair 較小,但邊緣重疊,而且 USB 版接回後要解鎖,`mem_end` 是解鎖後量的,會被撐大。
- **更重要的是**:Lawnchair 為預設的整段測試中,One UI Home 與已下架的 Pear Launcher 都以前景服務常駐;「正在運作的服務」畫面也同時列出 One UI 首頁(243 MB)與 Lawnchair(139 MB)。**換桌面並不會讓 One UI Home 消失,比較像是多了一個 Lawnchair。**

### 3.7 DevCheck 的「深度睡眠」不是 Doze 的 deep idle

名詞很容易混淆:

| 說法 | 實際指的是 |
|---|---|
| Doze 的 deep idle | 軟體狀態,限制 App 的網路、job、alarm(`dumpsys deviceidle`) |
| CPU deep sleep(DevCheck 顯示的) | CPU 進入 suspend 的時間比例 = `1 − uptime ÷ realtime`,是開機至今的累計(我的手機是 73%,整夜測試是約 95%) |
| Samsung「深度休眠應用程式」 | 電池設定裡對不常用 App 的背景限制,另一回事 |

---

## 4. 這套方法能回答什麼、不能回答什麼

| 能回答 | 不能回答 |
|---|---|
| 能不能進 deep idle、何時進、占比多少 | One UI Home 與 Lawnchair **哪個比較省電**(待機時兩者的耗電都不到測量誤差的 1/50;launcher 的耗電主要在亮屏使用) |
| 為什麼被延遲或打斷(鬧鐘、`min_time_to_alarm`、FMM) | **記憶體**的可靠比較(單點量測、swap 影響太大) |
| 哪些服務在待機時喚醒手機 | **日常亮屏使用**是否正常 |
| 待機耗電哪一段異常,並對上外部事件 | 精確的 mAh/h、長期趨勢 |
| 測試方法本身有沒有影響(電腦醒著、亮屏) | 因果(很多只是相關) |

**這支手機的待機有沒有問題?** 在 FMM 服務停止、deep idle 正常運作的條件下:deep idle 86.4%、沒有 App 長時間持有 wakelock(最長是 Galaxy Store 的 2 分 7 秒)、沒有 kernel wakelock 風暴、約 11 mAh/h。我沒有別的手機當基準,所以只能說**沒有看到明顯異常**。

---

## 5. 和 AI 合作的心得

### 5.1 先給「摘要」,不要給整份檔

完整的 `dumpsys batterystats` 約 600 KB–1 MB,大半是無關的清單。我的經驗(Gemini 尤其明顯)是直接丟整份會離題;先過濾出關鍵欄位,回答品質好很多。摘要腳本輸出的內容:時長、放電、light / deep idle、第一次進入 deep idle、鬧鐘中止點、FMM 鬧鐘、分段放電曲線、喚醒來源(UID 換成套件名稱)、kernel wakelock、耗電前幾名 UID、指定 launcher 的細節、記憶體與電池摘要。

第一版摘要沒有把 UID 換成套件名稱,AI 就把 1051 猜成 `com.samsung.android.lool`(其實是 netd)、把 `u0a1204` 猜成 Chrome(其實是 LINE)。

### 5.2 附上「已驗證的事實」

摘要只有單次測試的數字,AI 看不到我之前累積的結論,所以每次都重新推測一遍。我現在會在摘要前面貼一段「已驗證的事實」(例如:電腦醒著才會耗電、netd 喚醒與 adb 無關、維護窗口是正常的、不建議限制 GMS、用 mAh 不看百分比),並要求 AI「區分資料證據與推測」。

### 5.3 提問要精確

「deep sleep」至少有三種意思(見 3.7)。我後來改成「**Doze 的 deep idle(`DeviceIdleController`)**」,並附上 `deviceidle` 與 `batterystats` 的數據。

### 5.4 AI 最常犯的錯(本專案實例)

| 類型 | 實例 |
|---|---|
| **把相關說成因果** | 「adb 讓 WiFi kernel active 變 60%」——不連 adb 也是 59%;「電腦醒著 = 手機耗電」在這裡倒是有時間對照支持,仍標為相關 |
| **看不懂某個指標** | 「Light idle 比例越高越好」——要和 deep idle 合起來看;「kernel active 50–60% 代表 CPU 沒睡」——CPU 深度睡眠是 92–96% |
| **把模型估算當實測** | 拿 `Estimated power use` 加總算每小時耗電;用 6000 mAh 換算百分比 |
| **過度解讀一個計數階距** | 「27.6 mAh/h 是異常」——只是比一般區段多一個 4.5 mAh 的計數 |
| **誤讀時間點** | 把維護窗口 `deep.maintenance` 說成「被打斷、進入較長的活躍期」(其實約 3 分鐘就回去) |
| **指令本身有問題** | `input keyevent 26` 是**切換**電源鍵,螢幕已關時反而會亮屏;應該用 `KEYCODE_SLEEP`(223) |
| **危險或不必要的建議** | 停用 FMM 套件、動 Knox「裝置服務」、限制 GMS(推播與定位依賴它)、路由器工程帳號與預設密碼規則 |
| **名詞混用** | 把 Qualcomm 的 wakelock 名稱(`qcom_rx_wakelock`、`ipa_ws`)套到 Exynos 的 M14 |

### 5.5 這批對 Google AI「待機測試腳本」的評論,哪些對、哪些不對

最後我把一份 Google AI 的自動化測試腳本(Termux + MacroDroid、有線 `battery unplug`、無線 adb)丟給多個 AI 評論,再對照自己的資料:

| 說法 | 判斷 | 依據 |
|---|---|---|
| `dumpsys battery unplug` 只是模擬,不能等同真實拔線 | ✓ | 手機實際仍在充電,mAh 數據無效,只適合看 Doze 狀態 |
| 「100% 準確」「零誤差」等絕對用語不可信 | ✓ | 同一支手機、類似條件,deep idle 比例在 75.9%–100% 之間、耗電 11–15 mAh/h 波動 |
| Termux 內的 `sleep 21600` 在 Deep Idle 下不可靠 | ✓ 合理(我沒有實測) | 這也是我不用 Termux 的原因之一 |
| 不應把 Qualcomm 的 wakelock 名稱套到 Exynos 機型 | ✓ | 這支手機的 dump 裡沒有 `wlan_rx_wake`、`ipa_ws`、`qcom_rx_wakelock`,出現的是 `wlan_ma`、`hip4_wake_lock_tx`、`NETLINK`、`umts_ipc1` |
| 路由器工程帳號、預設密碼規則不要嘗試 | ✓ | 風險高、也不是必要手段 |
| 「只要充電就絕對不能進 Deep Idle 說得太過頭」(GPT-5.4 mini) | ✗ 在這支手機上成立 | 接回 USB 的當下 Doze 立刻退出(`normal (charging)`),`mCharging=true` |
| 「用 `input keyevent 26` 關螢幕」(GPT-5.4 mini、Gemma 腳本) | ✗ | 26 是切換;用 223 |
| Gemma 的速查關鍵字 `All wakeup alarms` | ✗ | 這支手機的 dump 沒有這一段(0 筆);有的是 `All partial wake locks`、`All kernel wake locks`、`All wakeup reasons` |
| GPT-5.4 mini 的「電腦 + ADB」一鍵腳本 | △ | 缺 `unforce`、沒處理 USB 充電(Doze 進不去)與無線斷線、`set -e` 遇到 adb 失敗就直接結束 |
| DeepSeek:「你上一次插著線測,`mCharging = true`,Doze 報廢」 | ✗ | 那是接回 USB 之後的狀態;實際拔線的 7h45m 正常 |
| Grok:「無線 ADB 必須維持 Wi-Fi,所以才有高 wlan_* kernel active」 | ✗ | USB 完全拔線也是 53–59% |
| DeepSeek / Grok:「做飛航模式、訪客網路的 A/B 對照」 | △ 可做 | 但 `wlan_mbox_irq` 隨時段就差 2–3 倍(79–243 次/小時),對照一定要在同一個時段 |
| Mistral:「高度專業且實用」 | △ | 幾乎沒有批評絕對用語、未驗證細節、路由器工程帳號這些實質問題 |

### 5.6 使用 AI 給的指令:先量測,再調整;一次只改一個;記下怎麼還原

我之前常常傻傻地照 AI 一步步輸入:沒改善還算好,最麻煩的是出問題時又忘記怎麼還原。這個專案的做法是先自動化量測、取得基準,再決定要不要動任何設定——因為這支手機的待機表現主要由 Samsung 自己的機制決定(Doze 設定與 FMM 服務),不是 AI 一直建議的 WiFi、GMS、launcher;而基準已經顯示手機待機正常,不需要再調。

- 唯讀指令(`dumpsys`、`cmd role get-role-holders`、`grep`)可以隨便跑;可還原的設定先備份原值;**會影響安全功能或系統元件的(`pm disable-user` 系統套件、Knox 裝置服務、清除資料)不要做**。
- 不確定一個設定改了什麼,就前後比對:`adb shell settings list global|secure|system` 改前改後各存一份再 `diff`。
- 常見還原:`deviceidle force-idle` ↔ `unforce`;`battery unplug` ↔ `battery reset`;`pm disable-user` ↔ `pm enable`;`settings put` 先 `settings get` 記原值。

---

## 6. 踩過的坑(精簡版)

- **設定開關關了,不代表服務停了**:要到「正在運作的服務 / 使用中的應用程式」確認 `OfflineFindingService` 沒有在跑。
- **預設桌面和以為的不同**:我有兩次以為是 Lawnchair 其實是 One UI;測前測後都要用 `cmd role get-role-holders android.app.role.HOME` 確認。
- **重置時手機已經在 deep idle**:這樣量不到「進入時間」。
- **有一個你不知道的鬧鐘**:`Next alarm clock` 空白不代表沒有;要看 `dumpsys alarm` 的 `Next wake from idle`。
- **解鎖才會讓 Doze 退出;只亮屏不解鎖不會**(Samsung 的 `wait_for_unlock=true`)。
- **USB 版**:接回 USB 就開始充電,Doze 在那一刻退出,不是 deep idle 不穩;`battery_end` 與 `deviceidle` 的目前狀態不能用,實際放電看 `batterystats` 的 `Discharge`。
- **`meminfo` 指令要寫 `dumpsys meminfo <套件>`**:我有一次漏了 `meminfo`,第二個 launcher 的資料就缺了一半。
- **netstats 是開機至今的累計**,不是測試區間。
- **電腦睡眠醒來後 adb 會 `offline`**:要重試,不要讓後面的指令抓到一堆空檔。
- **meminfo 是單一時間點**,而且解鎖後量會被撐大。

---

## 7. 如果重來一次

1. 先到「正在運作的服務」確認 `OfflineFindingService` 沒有在跑;用 `dumpsys alarm` 看 `Next wake from idle`。
2. 手機不在充電;確認預設桌面。
3. 用 `doze-test-usb.sh`(或 `doze-test.sh`):腳本會拍快照、重置統計、關螢幕。
4. **拔線(或讓電腦睡眠),至少放 3 小時,中途不要解鎖。**
5. 接回後解鎖授權,腳本自動擷取並產生摘要。
6. 把摘要加上「已驗證的事實」貼給 AI;要求它區分證據與推測。
7. **一次只改一個變因**再測;改前先記原值與還原方式。

---

## 附錄 A:測試總表

| # | 日期時段 | 預設桌面 | 條件 | 時長 | 第一次 deep idle | deep idle | 放電 |
|---|---|---|---|---|---|---|---|
| 1 | 11-13 夜 | One UI / Lawnchair | Termux + 鬧鐘、亮屏不同(19 秒對 54 秒)、ssidwidget | 各 2h | 無 | 0% | 13.5 / 94.5 mAh(不可比) |
| 2 | 11-14 00:10 | One UI | 無線 adb 全程連線、FMM 服務在跑 | 6h03m | 2h56m53 | 19.3% | 63.0 mAh(10.4/h) |
| 3 | 11-14 10:29 | Lawnchair | 無 adb、FMM 在跑;Play 商店下載 20 MB | 3h10m | 3h01m01 | 4.6% | 63.0 mAh(19.9/h) |
| 4 | 11-14 14:53 | Lawnchair | FMM 只關設定、服務在跑 | 2h17m | 58m13 | 43.7% | 18.0 mAh(7.9/h) |
| 5 | 11-15 00:36 | Lawnchair | 無線 adb、電腦睡眠 | 6h07m | 重置時已在 deep | 82.2% | 94.5 mAh(15.4/h,含 18 mAh 維護突發) |
| 6 | 11-15 19:35 | One UI | 無線 adb、FMM 在跑 | 2h25m | 未進入 | 0% | 13.5 mAh(有效區間約 4 mAh) |
| 7 | 11-16 01:00 | One UI | 無線 adb、FMM 在跑 | 3h15m | 重置時已在 deep | 14.4% | 40.5 mAh(12.4/h) |
| 8 | 11-16 06:44 | One UI | **停止 `OfflineFindingService`** | 4h17m | **1h02m03** | 75.9% | 58.5 mAh(13.6/h) |
| 9 | 11-16 12:42 | One UI | 同上 | 2h27m | 重置時已在 deep | 100% | 31.5 mAh(12.8/h) |
| 10 | 11-16 21:18 | Lawnchair | USB 拔線(第 69 分鐘就接回) | 1h09m | 1h02m17 | 9.4% | 13.5 mAh |
| 11 | 11-16 22:54 | Lawnchair | USB 拔線 | 7h45m | **1h02m58** | **86.4%** | **85.5 mAh(11.0/h)** |

## 附錄 B:工具

- `doze-test.sh`、`doze-test-usb.sh`、`doze_summary.py`:自動化測試與摘要。
- `android-doze-test-guide.md`:完整的測試指南(指令、判讀、陷阱、AI 誤讀對照、還原對照表)。

## 附錄 C:尚未證實或推論的部分

- `OfflineFindingService` 是「被啟動後一直沒停」還是「會自己重啟」(只有 40 小時運作時間的間接證據)。
- FMM 計時被「取消並重新排定 +2 小時」的觸發事件,以及它與「第二個 progression 距離鬧鐘 58 分」的關係。
- 無線 adb 且電腦醒著的耗電,來自 adb 連線本身還是電腦在區網的流量。
- 6h07m 無線 adb 那次約每 16 秒的 netd 喚醒節奏的原因。
- 為什麼 `cc` 換算的滿電容量約 4.5 Ah(標示 6000 mAh)。
- `doze-test-usb.sh` 的 `MODE="sim"` 與 `force-stop` FMM:沒有在實機上實測。
- 單一手機、單一環境、每個條件 1–2 次樣本;結論不應直接套用到其他機型。
