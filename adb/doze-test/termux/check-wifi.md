**Grok**
以下是一組精簡且針對你目前問題（Wi-Fi kernel active 過高、periodic scan 頻繁）的 **adb 指令**，可直接複製使用。

### 1. 基本 Wi-Fi 狀態與掃描設定
```bash
# 查看 Wi-Fi 掃描相關設定
adb shell settings get global wifi_scan_always_enabled
adb shell settings get global wifi_scan_throttle_enabled
adb shell cmd wifi get-scan-always-available

# 查看目前連線的 SSID 與狀態
adb shell dumpsys wifi | grep -E "mWifiInfo|SSID|Supplicant state|wifi_scan_always|firmware roaming"
```

### 2. 即時觀察 Periodic Scan / Connectivity Scan
```bash
# 即時追蹤 WifiConnectivityManager 的 scan timer（最重要）
adb shell dumpsys wifi | grep -E "schedulePeriodicScanTimer|periodicScanTimerHandler|startConnectivityScan|No partial scan"

# 更完整一點（包含最近 scan 行為）
adb shell dumpsys wifi | grep -A 50 -E "WifiConnectivityManager|periodicScan"
```

### 3. 確認 Kernel 層 Wi-Fi 活躍與 Wakeup
```bash
# 查看 Wi-Fi 相關 Kernel Wakelock
adb shell dumpsys batterystats | grep -A 20 "Kernel Wake lock" | grep -E "MT662x|wlan|wifi|PowerManagerService"

# 查看 Wakeup reason（重點看 wlan0）
adb shell dumpsys batterystats | grep -A 30 "Wakeup reason" | head -40

# 查看 Wi-Fi Kernel Active 時間
adb shell dumpsys batterystats | grep -E "Wi-Fi|wifi.*active|kernel active"
```

### 4. 快速確認目前是否有大量 NetworkRequest 維持連線
```bash
adb shell dumpsys connectivity | grep -E "NetworkAgentInfo|SSID|sweetwow|Requests:|TRACK_DEFAULT|LISTEN" | head -60
```

### 5. 一鍵打包常用資訊（建議使用）
把下面整段複製執行，會一次抓出最關鍵的資訊：

```bash
echo "===== Wi-Fi Scan Settings ====="
adb shell settings get global wifi_scan_always_enabled
adb shell settings get global wifi_scan_throttle_enabled

echo -e "\n===== Current Wi-Fi Connection ====="
adb shell dumpsys wifi | grep -E "mWifiInfo|SSID:|Supplicant state|wifi_scan_always_enabled|firmware roaming" | head -20

echo -e "\n===== Recent Periodic Scan ====="
adb shell dumpsys wifi | grep -E "schedulePeriodicScanTimer|periodicScanTimerHandler|startConnectivityScan|No partial scan because" | tail -30

echo -e "\n===== Wi-Fi Kernel Active & Wakeup ====="
adb shell dumpsys batterystats | grep -E "Wi-Fi kernel active|Wifi.*active|MT662x|wlan0" | head -20

echo -e "\n===== Top Wakeup Reasons ====="
adb shell dumpsys batterystats | grep -A 15 "Wakeup reason" | head -20
```

### 使用建議
- 先執行第 5 點的一鍵指令，把結果貼給我。
- 如果要觀察「螢幕關閉後」的行為，建議：
  1. 執行一次一鍵指令
  2. 關閉螢幕等待 5~10 分鐘
  3. 再執行一次，對比 periodic scan 是否還在持續排程

需要我再幫你加「關閉 Wi-Fi 後對比」或「強制停止某些服務」的指令也可以告訴我。

---

**Gemini**

要在 Termux 或透過 ADB 環境中精準擷取這些 Wi-Fi 診斷資料，您可以直接使用以下幾道指令。

這些指令假設您是透過 **ADB 連線**（或手機已 Root 直接在 Termux 執行）。如果是透過電腦連線手機，請在指令前方加上 `adb shell`；如果是在手機端 Termux 且已取得 root 權限，則可以直接執行。

---

### 1. 擷取 `dumpsys batterystats` 中的 Wi-Fi 專屬區段

您原本的 `full.txt` 已經包含了完整的 batterystats。如果只想快速抽取出裡面與 Wi-Fi 統計、封包、Kernel active 相關的段落，可以用 grep 過濾：

```bash
# 如果是透過電腦 ADB 連線：
adb shell dumpsys batterystats | grep -E -i "wifi|wakelock|kernel active" -A 5 -B 2 > wifi_batterystats.txt

# 如果是在手機端（已有 root）：
dumpsys batterystats | grep -E -i "wifi|wakelock|kernel active" -A 5 -B 2 > wifi_batterystats.txt

```

---

### 2. 擷取 `dumpsys wifi` 與 `dumpsys connectivity` 摘要

這兩個系統服務能看出 Wi-Fi 晶片的連線狀態、喚醒鎖定（WifiLock）、背景掃描頻率以及網路封包路由：

```bash
# 輸出 Wi-Fi 服務詳細狀態
adb shell dumpsys wifi > dumpsys_wifi.txt

# 輸出網路連線與連線管理服務狀態
adb shell dumpsys connectivity > dumpsys_connectivity.txt

```

*(註：這兩個檔案通常很大，若只想看重點，可以用 `grep -i "wakelock\|scan\|lock" dumpsys_wifi.txt` 過濾)*

---

### 3. 檢查「Wi-Fi 總是掃描 / 始終開啟」等關鍵設定

很多時候 Wi-Fi Kernel 長時間活躍（例如您摘要中顯示 Wi-Fi kernel active 高達 5 小時以上），是因為系統或背景 App 持續進行定位掃描。您可以用以下指令檢查系統設定：

```bash
# 1. 檢查是否開啟「Wi-Fi 自動連線/掃描」（即使關閉 Wi-Fi 也可能在背景掃描）
adb shell settings get global wifi_scan_always_available

# 2. 檢查藍牙掃描是否也連帶常駐（常與 Wi-Fi 掃描綁定）
adb shell settings get global ble_scan_always_available

# 3. 檢查省電模式或連線策略設定
adb shell settings get global wifi_watchdog_poor_network_detection

```

* **傳回 `1**` 代表該項「隨時掃描」功能有開啟（這往往是導致 Wi-Fi Kernel Active 居高不下的元兇之一）；
* **傳回 `0**` 代表已關閉。

您可以執行上述指令，若抓取到了 `dumpsys_wifi.txt` 的重點片段或設定回傳值（例如 `wifi_scan_always_available` 的結果），隨時可以貼上來，我們就能精準判斷是哪個背景服務在頻繁喚醒 Wi-Fi 晶片！


---



**Grok**
以下是一個實用的 **Wi-Fi 開關對比測試腳本**，可直接使用。

### 使用方式
1. 把下面內容存成 `wifi-test.sh`
2. 執行：`sh wifi-test.sh`
3. 腳本會自動：
   - 記錄「目前狀態」
   - 關閉 Wi-Fi
   - 等待你指定的時間（預設 30 分鐘）
   - 再次記錄狀態
   - 最後把 Wi-Fi 重新打開
   - 輸出前後對比重點

---

```bash
#!/bin/bash

# ====================== 可調整參數 ======================
WAIT_MINUTES=30          # 關閉 Wi-Fi 後要等待的分鐘數（建議 30~60）
LOG_FILE="wifi_test_$(date +%Y%m%d_%H%M%S).log"
# =======================================================

echo "=== Wi-Fi 耗電對比測試 ===" | tee -a "$LOG_FILE"
echo "開始時間: $(date)" | tee -a "$LOG_FILE"
echo "等待時間: ${WAIT_MINUTES} 分鐘" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

# 記錄函式
record_status() {
    local label=$1
    echo "---------- $label ----------" | tee -a "$LOG_FILE"
    echo "時間: $(date)" | tee -a "$LOG_FILE"

    echo -e "\n[Wi-Fi 開關狀態]" | tee -a "$LOG_FILE"
    adb shell dumpsys wifi | grep -E "Wi-Fi is|mWifiEnabled|wifiEnabled" | head -5 | tee -a "$LOG_FILE"

    echo -e "\n[Top Wakeup Reasons]" | tee -a "$LOG_FILE"
    adb shell dumpsys batterystats | grep -A 12 "Wakeup reason" | head -15 | tee -a "$LOG_FILE"

    echo -e "\n[Wi-Fi 相關 Kernel Wakelock / Active]" | tee -a "$LOG_FILE"
    adb shell dumpsys batterystats | grep -E "MT662x|wlan0|wifi.*active|Wi-Fi kernel" | head -15 | tee -a "$LOG_FILE"

    echo -e "\n[目前連線 SSID]" | tee -a "$LOG_FILE"
    adb shell dumpsys wifi | grep -E "mWifiInfo SSID|SSID:" | head -3 | tee -a "$LOG_FILE"

    echo "" | tee -a "$LOG_FILE"
}

# 1. 記錄關閉前狀態
record_status "關閉 Wi-Fi 前"

# 2. 關閉 Wi-Fi
echo ">>> 正在關閉 Wi-Fi..." | tee -a "$LOG_FILE"
adb shell svc wifi disable
sleep 3

# 確認是否已關閉
echo "確認 Wi-Fi 狀態:" | tee -a "$LOG_FILE"
adb shell dumpsys wifi | grep -E "Wi-Fi is|mWifiEnabled" | head -3 | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

# 3. 等待
echo ">>> 開始等待 ${WAIT_MINUTES} 分鐘（請保持螢幕關閉）..." | tee -a "$LOG_FILE"
echo "（等待期間可手動關閉螢幕）" | tee -a "$LOG_FILE"
sleep $((WAIT_MINUTES * 60))

# 4. 記錄關閉後狀態
record_status "關閉 Wi-Fi ${WAIT_MINUTES} 分鐘後"

# 5. 重新開啟 Wi-Fi
echo ">>> 正在重新開啟 Wi-Fi..." | tee -a "$LOG_FILE"
adb shell svc wifi enable
sleep 5

echo "=== 測試結束 ===" | tee -a "$LOG_FILE"
echo "結束時間: $(date)" | tee -a "$LOG_FILE"
echo "完整日誌已儲存至: $LOG_FILE" | tee -a "$LOG_FILE"
echo ""
echo "請把 $LOG_FILE 的內容貼給我，我幫你分析前後差異。"
```

---

### 建議使用流程
1. 手機接上電腦，確認 `adb devices` 看得到裝置
2. 執行腳本：`sh wifi-test.sh`
3. 執行後**立刻關閉手機螢幕**
4. 等待結束後，把產生的 `.log` 檔內容貼給我

需要我把等待時間改成可互動輸入，或再加上「記錄電池百分比變化」的功能嗎？
