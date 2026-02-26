#!/bin/bash

echo "==========================================================="
echo "       Android 系統耗電與穩定性診斷工具"
echo "==========================================================="

# 1. 檢查電池基本狀態與溫度
echo -e "\n[1. 電池狀態]"
adb shell dumpsys battery | grep -E "level|status|health|temperature" | sed 's/temperature: /溫度: /' | sed 's/$/ (0.1°C)/'

# 2. 檢查 CPU 佔用最高的 Top 5 進程
echo -e "\n[2. CPU 資源佔用前五名]"
# 使用相容性較高的指令格式
adb shell top -n 1 -m 5

# 3. 檢查「死循環」錯誤 (Logcat 錯誤過濾)
echo -e "\n[3. 正在即時監控系統錯誤 (請等待 5 秒)...]"
echo "--- 如果此處出現大量重複訊息，代表有套件停用後產生衝突 ---"
# 抓取最近 500 行並過濾關鍵錯誤
timeout 5 adb logcat *:E | grep -iE "ClassNotFound|ServiceNotFound|Permission denial|NullPointerException" || echo "未發現明顯衝突錯誤。"

# 4. 檢查喚醒次數 (Wakelocks)
echo -e "\n[4. 系統喚醒統計 (Wakelocks)]"
echo "--- 數字越大代表該 App 越常讓手機無法休眠 ---"
adb shell dumpsys batterystats --wakelocks | grep "Wake lock" | head -n 5

echo -e "\n==========================================================="
echo "診斷完成！"
echo "提示：若發現溫度過高 (>380) 或錯誤訊息刷屏，請考慮還原最近停用的套件。"
