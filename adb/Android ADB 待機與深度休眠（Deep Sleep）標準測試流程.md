# Android ADB 待機與深度休眠（Deep Sleep）標準測試流程

本流程整合了 `batterystats`（精準計算掉電率與喚醒鎖）與 `deviceidle`（追蹤進入深度休眠時間點），用於排查特定時段的異常待機耗電。

---

## 階段一：測試前準備（歸零與基準點）

建議在睡前或準備長時間靜置手機前執行。**全程強烈建議使用無線 ADB（Wireless Debugging）**，避免插拔 USB 傳輸線觸發充電狀態而影響數據統計。

1. **將手機充至固定電量**（建議 90% 以上）。
2. **重置電池統計數據**：
   ```bash
   adb shell dumpsys batterystats --reset
   ```
   * **說明**：將所有 App 的耗電與喚醒次數歸零，從這一刻重新計算。
3. **匯出測試前的 Doze 歷史紀錄（建立基準點）**：
   ```bash
   adb shell dumpsys deviceidle > idle_before.txt
   ```
4. **關閉螢幕並開始靜置**：
   * 拔除所有充電線與傳輸線。
   * 將手機平放在桌面（避免移動觸發動態感測器喚醒）。
   * 靜置至少 **2～4 小時**（建議測試一整晚睡眠時段）。

---

## 階段二：測試結束（收集數據）

靜置時間結束後，點亮螢幕並**立刻**執行以下指令（先不要滑動其他 App，以免混入操作耗電）：

1. **匯出完整的電池統計報告**：
   ```bash
   adb shell dumpsys batterystats > battery_after.txt
   ```
2. **匯出測試後的 Doze 歷史紀錄**：
   ```bash
   adb shell dumpsys deviceidle > idle_after.txt
   ```
3. **快速查看核心 Deep Sleep 總時間（可選）**：
   ```bash
   adb shell dumpsys batterystats | grep -iE "deep sleep|uptime|realtime"
   ```

---

## 階段三：快速判讀數據指標

取得輸出檔案後，檢查以下三個關鍵指標即可評估待機表現：

### 1. 實際進入深度休眠的時間點
* **查看方式**：打開 `idle_after.txt`，拉到最底部的 `Idling history:` 區塊，對照 `idle_before.txt` 的最後一行。
* **判讀標準**：多出來的紀錄即為本次測試的完整過程。正常情況下，裝置應在關閉螢幕後 **30～45 分鐘內**進入 `deep-idle`。

### 2. 螢幕關閉後的每小時掉電率
* **查看方式**：在 `battery_after.txt` 中搜尋關鍵字 `Screen off discharge rate`。
* **判讀標準**：
  * **正常健康**：約 **0.3% ～ 0.8% / 小時**（視 5G/Wi-Fi 訊號強弱而定）。
  * **異常偏高**：若超過 **1.5% / 小時**，代表存在異常耗電。

### 3. 抓出阻止休眠的 App（Wakelock）
* **查看方式**：在 `battery_after.txt` 中搜尋關鍵字 `All partial wake locks:`。
* **判讀標準**：此區塊會依「喚醒時間長短」由上往下排列。若前幾名出現第三方 App（如社群、通訊軟體）累積喚醒長達數分鐘以上，即為阻止手機進入深度休眠的元兇。



---

這是一支專為 Mac/Linux 設計的一鍵執行 Shell Script（.sh）。它內建了互動式選單、ADB 連線自動檢查、自動建立獨立時間戳記資料夾，甚至在測試結束時會自動幫你把關鍵指標（Deep Sleep 時間、每小時掉電率、前 10 名喚醒鎖）直接萃取成一份精簡的摘要報告。

>>腳本程式碼（儲存 adb_sleep_test.sh）
   

```js
#!/bin/bash

# 設定顏色輸出
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m' # 無顏色

echo -e "${CYAN}=================================================${NC}"
echo -e "${CYAN}   Android ADB 待機與深度休眠 (Deep Sleep) 測試工具  ${NC}"
echo -e "${CYAN}=================================================${NC}"

# 1. 檢查 ADB 是否已安裝
if ! command -v adb &> /dev/null; then
    echo -e "${RED}[錯誤] 找不到 adb 指令！請確認已安裝 Android Platform Tools 並加入環境變數。${NC}"
    exit 1
fi

# 2. 檢查是否有裝置連線
DEVICE_COUNT=$(adb devices | grep -w "device" | wc -l)
if [ "$DEVICE_COUNT" -eq 0 ]; then
    echo -e "${RED}[錯誤] 偵測不到任何已連線的 Android 裝置！${NC}"
    echo -e "請確認已開啟「USB 偵錯」或「無線偵錯 (Wireless Debugging)」，並允許此電腦存取。"
    exit 1
elif [ "$DEVICE_COUNT" -gt 1 ]; then
    echo -e "${YELLOW}[警告] 偵測到多台裝置，請確保只連接一台測試手機，否則指令可能會失敗。${NC}"
fi

# 3. 顯示功能選單
echo ""
echo "請選擇要執行的測試階段："
echo -e "  ${GREEN}1)${NC} 階段一：測試前準備 (重置電池統計 + 匯出基準點)"
echo -e "  ${GREEN}2)${NC} 階段二：測試結束   (匯出完整報告 + 自動產生關鍵摘要)"
echo -e "  ${GREEN}q)${NC} 離開"
echo ""
read -p "請輸入選項 [1/2/q]: " CHOICE

# 取得目前時間戳記 (格式：YYYYMMDD_HHMMSS)
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BASE_DIR="./adb_sleep_logs"
mkdir -p "$BASE_DIR"

case "$CHOICE" in
    1)
        echo ""
        echo -e "${YELLOW}>>> 正在執行階段一：測試前準備...${NC}"
        
        # 重置 batterystats
        adb shell dumpsys batterystats --reset > /dev/null
        echo -e "${GREEN}[✓] 已重置電池統計數據 (batterystats --reset)${NC}"
        
        # 匯出測試前 deviceidle 基準點
        BEFORE_FILE="$BASE_DIR/idle_before_${TIMESTAMP}.txt"
        adb shell dumpsys deviceidle > "$BEFORE_FILE"
        echo -e "${GREEN}[✓] 已匯出測試前 Doze 基準紀錄：$BEFORE_FILE${NC}"
        
        echo ""
        echo -e "${CYAN}【下一步操作建議】${NC}"
        echo "1. 請拔除所有 USB 充電線與傳輸線（若使用無線 ADB 則直接鎖定螢幕即可）。"
        echo "2. 將手機平放在桌上不要移動，靜置至少 2～4 小時（或一整晚）。"
        echo "3. 靜置結束後，點亮螢幕並立刻再次執行此腳本選擇「2」。"
        ;;
        
    2)
        echo ""
        echo -e "${YELLOW}>>> 正在執行階段二：收集與分析測試數據...${NC}"
        
        # 為本次測試建立專屬時間戳記資料夾
        REPORT_DIR="$BASE_DIR/Report_${TIMESTAMP}"
        mkdir -p "$REPORT_DIR"
        
        BATTERY_FILE="$REPORT_DIR/battery_after.txt"
        IDLE_FILE="$REPORT_DIR/idle_after.txt"
        SUMMARY_FILE="$REPORT_DIR/SUMMARY_重點摘要.txt"
        
        # 匯出完整日誌
        adb shell dumpsys batterystats > "$BATTERY_FILE"
        echo -e "${GREEN}[✓] 已匯出完整電池統計：$BATTERY_FILE${NC}"
        
        adb shell dumpsys deviceidle > "$IDLE_FILE"
        echo -e "${GREEN}[✓] 已匯出完整 Doze 紀錄：$IDLE_FILE${NC}"
        
        # 自動萃取關鍵指標到 SUMMARY_FILE
        echo "==========================================" > "$SUMMARY_FILE"
        echo "  Android 待機休眠測試 - 自動重點摘要" >> "$SUMMARY_FILE"
        echo "  匯出時間：$(date '+%Y-%m-%d %H:%M:%S')" >> "$SUMMARY_FILE"
        echo "==========================================" >> "$SUMMARY_FILE"
        
        echo -e "\n【1. Deep Sleep 總時間與螢幕關閉掉電率】" >> "$SUMMARY_FILE"
        grep -iE "Deep sleep time|Screen off discharge rate" "$BATTERY_FILE" >> "$SUMMARY_FILE"
        
        echo -e "\n【2. 前 15 名部分喚醒鎖 (All partial wake locks)】" >> "$SUMMARY_FILE"
        grep -A 15 "All partial wake locks:" "$BATTERY_FILE" >> "$SUMMARY_FILE"
        
        echo -e "\n【3. 最近 25 筆 Doze 狀態變化 (Idling history)】" >> "$SUMMARY_FILE"
        grep -A 25 "Idling history:" "$IDLE_FILE" | tail -n 25 >> "$SUMMARY_FILE"
        
        echo -e "${GREEN}[✓] 已自動產生重點摘要檔：$SUMMARY_FILE${NC}"
        echo ""
        echo -e "${CYAN}--- 摘要預覽 ---${NC}"
        cat "$SUMMARY_FILE"
        echo -e "${CYAN}----------------${NC}"
        ;;
        
    q|Q)
        echo "已取消並離開。"
        exit 0
        ;;
        
    *)
        echo -e "${RED}[錯誤] 無效的選項，請重新執行腳本。${NC}"
        exit 1
        ;;
esac
```

這支升級版的 Shell Script（adb_sleep_test.sh）新增了無線 ADB 智慧連線管理。
執行時若沒有偵測到已連線的裝置，它會自動讀取上次紀錄的 IP，讓你直接按 Enter 一鍵連線，或是輸入新的 IP:Port 並自動幫你記憶下來，完全省去手動敲打 adb connect 的麻煩。

>> 升級版腳本程式碼（儲存為adb_sleep_test.sh）
   

```js

#!/bin/bash

# 設定顏色輸出
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m' # 無顏色

BASE_DIR="./adb_sleep_logs"
mkdir -p "$BASE_DIR"
IP_CONFIG_FILE="$BASE_DIR/.last_adb_ip"

echo -e "${CYAN}=================================================${NC}"
echo -e "${CYAN}   Android ADB 待機與深度休眠測試工具 (無線支援版)  ${NC}"
echo -e "${CYAN}=================================================${NC}"

# 1. 檢查 ADB 是否已安裝
if ! command -v adb &> /dev/null; then
    echo -e "${RED}[錯誤] 找不到 adb 指令！請確認已安裝 Android Platform Tools 並加入環境變數。${NC}"
    exit 1
fi

# 2. 檢查裝置連線狀態（若無連線則啟動無線 ADB 輔助連線）
DEVICE_COUNT=$(adb devices | grep -w "device" | wc -l)

if [ "$DEVICE_COUNT" -eq 0 ]; then
    echo -e "${YELLOW}[提示] 目前沒有已連線的 Android 裝置。${NC}"
    
    LAST_IP=""
    if [ -f "$IP_CONFIG_FILE" ]; then
        LAST_IP=$(cat "$IP_CONFIG_FILE")
    fi

    echo ""
    if [ -n "$LAST_IP" ]; then
        echo -e "偵測到上次使用的無線 ADB 位址：${GREEN}$LAST_IP${NC}"
        read -p "請直接按 [Enter] 連線此位址，或輸入新的 IP:Port (直接輸入 q 離開): " INPUT_IP
        TARGET_IP=${INPUT_IP:-$LAST_IP}
    else
        read -p "請輸入手機「無線偵錯」顯示的 IP:Port (例如 192.168.1.100:38451，輸入 q 離開): " TARGET_IP
    fi

    if [[ "$TARGET_IP" == "q" || "$TARGET_IP" == "Q" || -z "$TARGET_IP" ]]; then
        echo "已取消連線並離開。"
        exit 0
    fi

    echo -e "${YELLOW}>>> 正在嘗試連線至 $TARGET_IP ...${NC}"
    CONNECT_OUT=$(adb connect "$TARGET_IP")
    echo "$CONNECT_OUT"

    # 再次確認連線是否成功
    DEVICE_COUNT=$(adb devices | grep -w "device" | wc -l)
    if [ "$DEVICE_COUNT" -eq 0 ]; then
        echo -e "${RED}[錯誤] 無線連線失敗！${NC}"
        echo "請檢查：1. 手機與電腦是否在同一個 Wi-Fi 下  2. 手機的無線偵錯 Port 是否已變更（重開無線偵錯會換 Port）。"
        exit 1
    else
        # 連線成功，將位址寫入設定檔記憶
        echo "$TARGET_IP" > "$IP_CONFIG_FILE"
        echo -e "${GREEN}[✓] 無線 ADB 連線成功！已自動記憶此位址。${NC}"
    fi
elif [ "$DEVICE_COUNT" -gt 1 ]; then
    echo -e "${YELLOW}[警告] 偵測到多台裝置，請確保只連接一台測試手機，否則指令可能會失敗。${NC}"
else
    echo -e "${GREEN}[✓] 已偵測到連線中的 Android 裝置。${NC}"
fi

# 3. 顯示功能選單
echo ""
echo "請選擇要執行的測試階段："
echo -e "  ${GREEN}1)${NC} 階段一：測試前準備 (重置電池統計 + 匯出基準點)"
echo -e "  ${GREEN}2)${NC} 階段二：測試結束   (匯出完整報告 + 自動產生關鍵摘要)"
echo -e "  ${GREEN}d)${NC} 斷開所有無線 ADB 連線 (adb disconnect)"
echo -e "  ${GREEN}q)${NC} 離開"
echo ""
read -p "請輸入選項 [1/2/d/q]: " CHOICE

# 取得目前時間戳記 (格式：YYYYMMDD_HHMMSS)
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

case "$CHOICE" in
    1)
        echo ""
        echo -e "${YELLOW}>>> 正在執行階段一：測試前準備...${NC}"
        
        # 重置 batterystats
        adb shell dumpsys batterystats --reset > /dev/null
        echo -e "${GREEN}[✓] 已重置電池統計數據 (batterystats --reset)${NC}"
        
        # 匯出測試前 deviceidle 基準點
        BEFORE_FILE="$BASE_DIR/idle_before_${TIMESTAMP}.txt"
        adb shell dumpsys deviceidle > "$BEFORE_FILE"
        echo -e "${GREEN}[✓] 已匯出測試前 Doze 基準紀錄：$BEFORE_FILE${NC}"
        
        echo ""
        echo -e "${CYAN}【下一步操作建議】${NC}"
        echo "1. 請直接按下手機電源鍵關閉螢幕（無需拔線）。"
        echo "2. 將手機平放在桌上不要移動，靜置至少 2～4 小時（或一整晚）。"
        echo "3. 靜置結束後，點亮螢幕並立刻再次執行此腳本選擇「2」。"
        ;;
        
    2)
        echo ""
        echo -e "${YELLOW}>>> 正在執行階段二：收集與分析測試數據...${NC}"
        
        # 為本次測試建立專屬時間戳記資料夾
        REPORT_DIR="$BASE_DIR/Report_${TIMESTAMP}"
        mkdir -p "$REPORT_DIR"
        
        BATTERY_FILE="$REPORT_DIR/battery_after.txt"
        IDLE_FILE="$REPORT_DIR/idle_after.txt"
        SUMMARY_FILE="$REPORT_DIR/SUMMARY_重點摘要.txt"
        
        # 匯出完整日誌
        adb shell dumpsys batterystats > "$BATTERY_FILE"
        echo -e "${GREEN}[✓] 已匯出完整電池統計：$BATTERY_FILE${NC}"
        
        adb shell dumpsys deviceidle > "$IDLE_FILE"
        echo -e "${GREEN}[✓] 已匯出完整 Doze 紀錄：$IDLE_FILE${NC}"
        
        # 自動萃取關鍵指標到 SUMMARY_FILE
        echo "==========================================" > "$SUMMARY_FILE"
        echo "  Android 待機休眠測試 - 自動重點摘要" >> "$SUMMARY_FILE"
        echo "  匯出時間：$(date '+%Y-%m-%d %H:%M:%S')" >> "$SUMMARY_FILE"
        echo "==========================================" >> "$SUMMARY_FILE"
        
        echo -e "\n【1. Deep Sleep 總時間與螢幕關閉掉電率】" >> "$SUMMARY_FILE"
        grep -iE "Deep sleep time|Screen off discharge rate" "$BATTERY_FILE" >> "$SUMMARY_FILE"
        
        echo -e "\n【2. 前 15 名部分喚醒鎖 (All partial wake locks)】" >> "$SUMMARY_FILE"
        grep -A 15 "All partial wake locks:" "$BATTERY_FILE" >> "$SUMMARY_FILE"
        
        echo -e "\n【3. 最近 25 筆 Doze 狀態變化 (Idling history)】" >> "$SUMMARY_FILE"
        grep -A 25 "Idling history:" "$IDLE_FILE" | tail -n 25 >> "$SUMMARY_FILE"
        
        echo -e "${GREEN}[✓] 已自動產生重點摘要檔：$SUMMARY_FILE${NC}"
        echo ""
        echo -e "${CYAN}--- 摘要預覽 ---${NC}"
        cat "$SUMMARY_FILE"
        echo -e "${CYAN}----------------${NC}"
        ;;

    d|D)
        adb disconnect
        echo -e "${GREEN}[✓] 已斷開所有無線 ADB 連線。${NC}"
        ;;
        
    q|Q)
        echo "已取消並離開。"
        exit 0
        ;;
        
    *)
        echo -e "${RED}[錯誤] 無效的選項，請重新執行腳本。${NC}"
        exit 1
        ;;
esac
```
