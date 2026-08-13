本文概括了透過 ADB 指令進行 Android 電池耗電測試與分析的完整流程。核心步驟包含開啟全紀錄、靜止待機測試，以及測試後的數據重設與功能關閉，以確保報告精準並維持系統效能。
## Android 電池耗電測試流程## 1. 測試前準備

* 
* 充飽手機電量。
* 保持平常網路連線（Wi-Fi 或行動網路）。
* 關閉 App 與系統自動更新。
* 

## 2. 啟動測試（連接電腦 ADB）

* 
* 重設統計：adb shell dumpsys batterystats --reset
* 啟用全副載追蹤：adb shell dumpsys batterystats --enable full-wake-history
* 開始測試：拔除充電線、關閉螢幕，將手機保持完全靜止（勿移動）。
* 

## 3. 靜止測試環境（二選一）

* 
* 情境 A（夜間待機測試）：靜止 6 ~ 8 小時（觀察基礎耗電率）。
* 情境 B（單一 App 測試）：靜止 1 ~ 2 小時（觀察特定背景行為）。
* 

## 4. 匯出與分析報告

* 
* 查詢耗電統計：adb shell dumpsys batterystats
* 

## 5. 結束與善後步驟

* 
* 關閉追蹤：adb shell dumpsys batterystats --disable full-wake-history
* 清除紀錄：adb shell dumpsys batterystats --reset
* 確認狀態：輸入 adb shell dumpsys batterystats，確認頂端顯示 Historical-wake-log: disabled。
* 



# 📱 Android 電池日誌 (Batterystats) 常用分析關鍵字指南

當使用文字編輯器（如 VS Code, Notepad++）打開數百 KB 的 Android Bugreport 或日誌時，可以直接使用 `Ctrl + F` 搜尋以下關鍵字來精準定位數據。

---

## 🔋 1. 核心續航與健康度 (Battery Summary)
用來評估電池整體的體質、容電量以及總體消耗。

*   `Estimated battery capacity`
    *   **說明**：系統目前估算的手機實際電池容量 (mAh)。
*   `Last learned battery capacity`
    *   **說明**：系統最新學習到的電池最大實際容量。將此數值除以設計容量可得知**電池健康度**。
*   `Discharge:`
    *   **說明**：自上次充滿電後的總放電量 (mAh)。
*   `Screen off discharge`
    *   **說明**：螢幕關閉（待機狀態）時的總放電量。
*   `Screen on discharge`
    *   **說明**：螢幕開啟（使用狀態）時的總放電量。

---

## 💤 2. 休眠與待機表現 (Sleep & Doze Mode)
用來檢查手機在沒有使用時，系統省電機制（Doze Mode）是否正常運作。

*   `Device full idling`
    *   **說明**：裝置進入「深度休眠 (Deep Doze)」的總時間。
*   `Device light idling`
    *   **說明**：裝置進入「淺度休眠 (Light Doze)」的總時間。
*   `Idle mode full time`
    *   **說明**：深層休眠的詳細統計。後面通常會附帶 `longest`（最長連續休眠時間）。如果最長休眠時間很短，代表手機待機時一直被驚醒。

---

## 🛑 3. 後台偷跑元兇 (Wakelocks)
**找出「後台耗電、發熱惡意軟體」的最關鍵指標**。Wakelock 會阻止 CPU 進入睡眠。

*   `Total partial wakelock time`
    *   **說明**：**核心關注點**。螢幕關閉時，所有後台程式持有喚醒鎖的總時間。若待機 2 小時此數值佔了 1.5 小時，代表後台有嚴重的異常耗電。
*   `All partial wakelocks:`
    *   **說明**：**抓兇手專用標題**。搜尋此字眼，下方會依序列出所有 App 的包名（如 `com.facebook.katana`）與它們各自持有的喚醒時間，時間最長的就是元兇。
*   `Total full wakelock time`
    *   **說明**：螢幕點亮或強制保持螢幕開啟的喚醒鎖時間（例如看影片、導航時）。

---

## 📺 4. 螢幕與顯示 (Screen Statistics)
評估螢幕耗電與使用者習慣。

*   `Screen on:`
    *   **說明**：螢幕點亮的總時間（即 SoT, Screen-on Time）以及點亮次數（例如 `1x` 代表點亮一次）。
*   `Screen brightnesses:`
    *   **說明**：螢幕亮度區間統計（dark, dim, medium, bright）。若 bright 佔比過高，代表常在強光下使用，這會導致電量消耗極快。

---

## 📶 5. 網路與通訊 (Connectivity)
無線訊號是待機耗電的第二大原因（尤其是 5G 或訊號不佳時）。

*   `CONNECTIVITY POWER SUMMARY START`
    *   **說明**：**網路耗電總覽起點**。直接搜尋此字眼可快速跳轉到網路耗電專區。
*   `Mobile active time`
    *   **說明**：行動網路（4G/5G）射頻晶片處於工作/發射狀態的總時間。
*   `Cellular Sleep time`
    *   **說明**：行動網路晶片處於完全睡眠的時間，比例越高越省電。
*   `Cellular Rx time` / `Cellular Tx time`
    *   **說明**：行動網路接收數據（Rx）與發送數據（Tx）的總時間。

---

## 💡 快速排查三步驟（SOP）
1. 搜尋 `Estimated battery capacity` 檢查**電池健康度**。
2. 搜尋 `Idle mode full time` 檢查**待機休眠是否正常**（看 longest 持續多久）。
3. 搜尋 `All partial wakelocks:` 往下拉，**直接抓出後台耗電時間最長的 App**。

# 🛠️ ADB 電池日誌關鍵字過濾與精簡指南

當你不想生成或閱讀數百 KB 的完整 Bugreport 時，可以使用以下指令，在導出或讀取日誌的當下直接完成關鍵字篩選，大幅縮短內容。

---

## 📱 1. 手機端專用 (aShell / Termux)
手機版終端機環境（如 `sh`、`mksh`）的 `grep` 版本與跳脫符號支援度不同，**請務必使用以下三種相容寫法**（指令前不需加 `adb shell`）：

### 💡 寫法 A：使用 `egrep` (最推薦，語法最乾淨)
```bash
dumpsys batterystats | egrep -i "capacity|discharge|idling|wakelock time|Screen on:"
```

### 💡 寫法 B：使用 `grep -E` (標準延伸正規表示式)
```bash
dumpsys batterystats | grep -Ei "capacity|discharge|idling|wakelock time|Screen on:"
```

### 💡 寫法 C：使用 `awk` (最古老、絕對通用的保險寫法)
```bash
dumpsys batterystats | awk 'tolower(\$0) ~ /capacity|discharge|idling|wakelock time|screen on:/'
```

---

## 💻 2. 電腦端專用 (透過 USB 連接手機)
請依據你電腦的作業系統，在終端機（Terminal / CMD）中輸入以下對應指令：

### 🍎 Mac / Linux 系統
使用 `\|` 來隔開並串聯多個你想保留的關鍵字：
```bash
adb shell dumpsys batterystats | grep -i "capacity\|discharge\|idling\|wakelock time\|Screen on:"
```

### 🪟 Windows 系統 (CMD)
使用 `findstr`，多個關鍵字之間直接用**空白鍵**隔開即可（`/I` 代表不區分大小寫）：
```cmd
adb shell dumpsys batterystats | findstr /I "capacity discharge idling wakelock Screen"
```

---

## 📂 3. 進階：直接輸出為「精簡版純文字檔」
如果你不想讓數據直接在畫面上閃過，想存成一個只有幾十行核心數據的小檔案，請在指令最後加上 `> 檔名.txt`：

*   **Mac / Linux 電腦端：**
    ```bash
    adb shell dumpsys batterystats | grep -i "capacity\|discharge\|idling\|wakelock time\|Screen on:" > mini_battery_report.txt
    ```
*   **Windows 電腦端：**
    ```cmd
    adb shell dumpsys batterystats | findstr /I "capacity discharge idling wakelock Screen" > mini_battery_report.txt
    ```
*   **手機端 aShell：**
    ```bash
    dumpsys batterystats | egrep -i "capacity|discharge|idling|wakelock time|Screen on:" > /sdcard/mini_battery_report.txt
    ```

---

## 🔍 4. 衍生排查：抓取音訊與後台 App 喚醒源
如果你從過濾後的日誌發現 `audio` 或 `wakelock` 有異常開關，可使用以下指令追查具體 App：

*   **查看是哪個 App 觸發了音訊晶片（如三星鍵盤按鍵音）：**
    ```bash
    dumpsys audio | grep -i "player"
    ```
*   **查看最近的音訊事件日誌（抓取觸發時間點）：**
    ```bash
    dumpsys audio | grep -A 10 "Events log"
    ```

# 🔍 Android 後台定位喚醒與休眠失敗排查指南

當 Android 裝置在「沒插 SIM 卡」或「重開機後」，常因 Google 服務無法順利取得基地台訊號，導致後台定位機制卡死，引發內核休眠失敗（Suspend Abort）與隱形耗電。

---

## 🛑 1. 核心問題診斷 (Top Alarms)
透過 ADB 抓取高頻率定時器時，若發現以下關鍵字，即為耗電元兇：

*   **異常欄位**：`*walarm*:NetworkLocationScanner` (來自 `com.google.android.gms`)
*   **現象**：在短時間內觸發數十次 **`wakeups`（強制喚醒）**。
*   **原因**：Google Play 服務在缺乏行動網路時，會瘋狂強制喚醒 Wi-Fi 與藍牙硬體進行掃描，進而打斷系統內核的深度休眠（錯誤碼：`platform_pm_suspend returned -16`）。

---

## 🛠️ 2. 手機端優化解決步驟 (SOP)
直接切斷 Google 服務在後台無故喚醒硬體的權限，可大幅改善待機續航：

1.  **進入設定**：開啟手機的 **「設定」** > **「位置」**（或隱私與定位）。
2.  **關閉硬體掃描**：點選 **「定位服務」**，將 **「Wi-Fi 掃描」** 與 **「藍牙掃描」** 全面 **關閉**。
    *   *註：此功能關閉後，可阻止 Google 在 Wi-Fi/藍牙關閉時仍強行喚醒硬體。*
3.  **降低定位精確度（選用）**：若該裝置無導航需求，可將 **「Google 定位精確度」關閉**，避免後台持續運算網路定位。

---

## 📊 3. aShell 驗證與監控指令

完成設定後，可使用手機端 aShell 執行以下指令，驗證優化效果：

### 🔄 驗證定位掃描是否已停止喚醒
```bash
dumpsys alarm | grep "NetworkLocationScanner"
```
*   **預期結果**：觀察其 `wakeups` 次數是否已經停止飆升。

### 🔄 檢查系統底層是否順利進入深度休眠
```bash
dumpsys batterystats | grep -Ei "idling|suspend"
```
*   **預期結果**：不應再密集出現 `Abort: Callback failed on alarmtimer...` 的錯誤訊息，且 `Device full idling` 的時間能持續延長。

# 🧩 Android 桌面小工具 (Widget) 後台耗電與喚醒排查指南

桌面小工具（Widget）為了即時更新畫面（如 Wi-Fi SSID、天氣、時鐘、系統監測），經常會在後台頻繁調用系統廣播或定時器。如果編寫不良或遇到特定環境（如沒插 SIM 卡），很容易成為隱形耗電元兇。

---

## 🔍 1. 核心關鍵字與排查重點

在分析 Android 日誌時，桌面小工具的行為通常伴隨著以下特徵：

*   **`AppWidgetService`**：Android 系統專門管理桌面小工具的核心服務。
*   **`ACTION_APPWIDGET_UPDATE`**：小工具觸發畫面更新時的系統廣播事件。
*   **`+proc` 與 `fg`**：小工具所屬的應用程序長期處於啟動（Process）或前台/常駐（Foreground）狀態。

---

## 🛠️ 2. aShell 實戰排查指令

你可以透過以下三條指令，直接抓出到底是哪個 Widget 在後台搞鬼：

### 📊 指令 A：抓出目前「所有已在桌面創建」的 Widget 資訊
這個指令可以列出目前桌面上到底存在哪些小工具，以及它們的更新頻率設定。
```bash
dumpsys appwidget | grep -Ei "provider|updatePeriodMillis"
```
*   **檢查重點**：注意 `updatePeriodMillis`（更新週期毫秒數）。如果數值設定得太小（例如小於 1800000 毫秒，即 30 分鐘），代表它在後台更新得太頻繁。

### 🚨 指令 B：抓出 Widget 觸發的後台定時器（Alarms）
Widget 通常會註冊定時器來強行喚醒 CPU 進行資料更新。
```bash
dumpsys alarm | grep -Ei "appwidget|update" -A 2
```
*   **檢查重點**：觀察是否有特定小工具包名（例如先前看到的 `jp.rallewll.siriuth.ssidwidget`）高頻率出現在 `wakeups` 欄位中。

### ⏳ 指令 C：查看特定 Widget 應用程式的後台總耗電與喚醒次數
直接鎖定特定小工具的應用程式包名（Package Name），查看它的歷史總帳。
```bash
dumpsys batterystats | grep -A 15 "你的小工具包名"
```
*   **檢查重點**：查看 `wakeups`（總喚醒次數）與 `mAh`（估算耗電）。如果待機期間喚醒次數破百，就是不正常的偷跑。

---

## 💡 3. Widget 耗電的優化建議

如果你發現某個桌面小工具是耗電元兇，可以採取以下步驟調整：

1.  **拉長更新間隔**：進入該小工具的 App 設定內，將「更新頻率」從即時或 1 分鐘，改為 30 分鐘或 1 小時。
2.  **移除不必要的 Widget**：長時間不需要監測的資訊（如沒插 SIM 卡時的行動訊號 Widget、不常看的天氣），直接從桌面長按並移除。
3.  **檢查權限限制**：有些小工具（如 SSID Wi-Fi 小工具）需要「精確位置權限」才能抓取資料，若定位掃描已被你關閉，該 Widget 可能會因抓不到資料而卡死在後台不斷重試，此時建議直接將其卸載或更換其他開源替代品。

