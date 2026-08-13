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


