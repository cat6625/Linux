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


