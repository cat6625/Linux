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

WAIT_MINUTES=20          # 這次可以先測 20 分鐘就好
LOG_FILE="wifi_test_v2_$(date +%Y%m%d_%H%M%S).log"

echo "=== Wi-Fi 耗電對比測試 v2（含 reset）===" | tee -a "$LOG_FILE"
echo "開始時間: $(date)" | tee -a "$LOG_FILE"

record_status() {
    local label=$1
    echo -e "\n---------- $label ----------" | tee -a "$LOG_FILE"
    echo "時間: $(date)" | tee -a "$LOG_FILE"

    echo -e "\n[Top Wakeup Reasons]" | tee -a "$LOG_FILE"
    adb shell dumpsys batterystats | grep -A 10 "Wakeup reason" | head -12 | tee -a "$LOG_FILE"

    echo -e "\n[Wi-Fi 相關]" | tee -a "$LOG_FILE"
    adb shell dumpsys batterystats | grep -E "MT662x|wlan0|Wi-Fi kernel|wifi.*active" | head -10 | tee -a "$LOG_FILE"
}

# 1. 先重置 batterystats（重要！）
echo ">>> 重置 batterystats..." | tee -a "$LOG_FILE"
adb shell dumpsys batterystats --reset
sleep 2

# 2. 確認目前 Wi-Fi 是開啟的，記錄基準
echo ">>> 確保 Wi-Fi 開啟中..." | tee -a "$LOG_FILE"
adb shell svc wifi enable
sleep 5
record_status "重置後（Wi-Fi 開啟狀態）"

# 3. 關閉 Wi-Fi
echo ">>> 關閉 Wi-Fi 並等待 ${WAIT_MINUTES} 分鐘..." | tee -a "$LOG_FILE"
adb shell svc wifi disable
sleep 3
record_status "剛關閉 Wi-Fi 時"

# 4. 等待
echo "請關閉螢幕，等待中..."
sleep $((WAIT_MINUTES * 60))

# 5. 記錄關閉後的數據
record_status "關閉 Wi-Fi ${WAIT_MINUTES} 分鐘後"

# 6. 重開 Wi-Fi
adb shell svc wifi enable
echo -e "\n=== 測試結束 ===" | tee -a "$LOG_FILE"
echo "請把 $LOG_FILE 內容貼給我"
```

---

### 建議使用流程
1. 手機接上電腦，確認 `adb devices` 看得到裝置
2. 執行腳本：`sh wifi-test.sh`
3. 執行後**立刻關閉手機螢幕**
4. 等待結束後，把產生的 `.log` 檔內容貼給我

需要我把等待時間改成可互動輸入，或再加上「記錄電池百分比變化」的功能嗎？

---

```markdown
# Android Wi-Fi 耗電問題測試報告與結論

## 一、問題摘要

裝置在長時間待機時出現明顯耗電，主要特徵如下：

- Wi-Fi Kernel Active 時間高達 **58.8%**
- Wakeup Reason 第一名長期為 **`238:SPM:336:wlan0`**
- Deep Doze 期間仍有較高放電（約 402 mAh）
- 實際流量接近 0B，但 radio 仍頻繁活躍

初步判斷為 **Wi-Fi 開啟並連線時，驅動層（MT662x）無法有效進入低功耗狀態**。

---

## 二、測試方法

### 測試 1：基本狀態觀察
使用以下指令觀察 Wi-Fi 掃描行為與 wakeup 來源：

```bash
adb shell settings get global wifi_scan_always_enabled
adb shell dumpsys wifi | grep -E "schedulePeriodicScanTimer|No partial scan|startConnectivityScan"
adb shell dumpsys batterystats | grep -A 15 "Wakeup reason"
```

### 測試 2：關閉 Wi-Fi 前後對比（未重置）
- 記錄當前 batterystats
- 關閉 Wi-Fi
- 等待 30 分鐘
- 再次記錄 batterystats

### 測試 3：重置後精確對比（推薦方法）
```bash
# 重置計數器
adb shell dumpsys batterystats --reset

# 開啟 Wi-Fi → 記錄
# 關閉 Wi-Fi → 等待 20 分鐘 → 再次記錄
```

---

## 三、測試結果

### 測試 1 結果
- `wifi_scan_always_enabled = 0`（已關閉）
- 存在大量 `schedulePeriodicScanTimer`（20s / 40s）
- 頻繁出現「No partial scan because firmware roaming is supported」
- Wakeup 第一名穩定為 `wlan0`

### 測試 2 結果（未重置）
| 項目                  | 關閉前          | 關閉 30 分鐘後   |
|-----------------------|-----------------|------------------|
| wlan0 Wakeup 時間     | 13m 25s (1030次)| 13m 25s (1030次) |
| 其他主要 Wakeup       | 無明顯變化      | 無明顯變化       |

→ 數據未增加，代表關閉 Wi-Fi 後不再產生新的 wlan0 wakeup。

### 測試 3 結果（重置後）
- 重置後各項計數歸零
- 關閉 Wi-Fi 並等待 20 分鐘後，**未再出現 wlan0 相關 Wakeup**

---

## 四、結論

1. **主要耗電來源已確認**  
   Wi-Fi 開啟並連線時，wlan0（MT662x）會頻繁喚醒系統，即使幾乎沒有實際流量。

2. **關閉 Wi-Fi 效果明確**  
   關閉 Wi-Fi 後，wlan0 相關 wakeup 基本停止，證明問題與 Wi-Fi radio 直接相關。

3. **可能成因**
   - Firmware Roaming 開啟，導致 radio 需持續監聽
   - Framework 持續安排 Periodic Scan Timer
   - 部分系統服務（GMS、小米推送等）維持網路請求

4. **Doze 本身運作正常**  
   Deep Idle 時間比例不低，問題不在 Doze 機制失效，而是 Wi-Fi 底層無法配合進入低功耗。

---

## 五、建議改善方式

| 優先級 | 方法 | 說明 |
|--------|------|------|
| 高 | 長時間不用時關閉 Wi-Fi | 最直接有效的方式 |
| 高 | 使用自動化工具 | 螢幕關閉後延遲關閉 Wi-Fi，亮屏時自動開啟 |
| 中 | 檢查路由器 Power Save | 開啟 U-APSD / WMM Power Save |
| 中 | 限制高 wakeup 應用 | 小米推送（xmsf）、Brave、Termux 等 |
| 低 | 觀察其他系統設定 | 關閉「智慧連線」、「Wi-Fi 輔助」等功能 |

---

## 六、後續可進行的驗證

若需要更精確的數據，可進行以下測試：

- Wi-Fi 開啟狀態下待機 1 小時 vs 關閉狀態下待機 1 小時，比較放電量與 wakeup 次數
- 使用 `adb shell dumpsys batterystats --reset` 後分別記錄兩種狀態的完整數據

---

**報告結束**
```
