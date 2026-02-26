#!/bin/bash
echo "開始精確監控... (按 Ctrl+C 結束)"
echo "------------------------------------------------"

while true; do
    # 使用 grep -oE 直接抓取 IDLE/INACTIVE 等關鍵字
    STATE=$(adb shell dumpsys deviceidle | grep -m 1 "mState=" | grep -oE "IDLE|INACTIVE|IDLE_MAINTENANCE|IDLE_PENDING|ACTIVE")
    
    # 統計目前的活躍 TCP 連線數
    CONNS=$(adb shell netstat -nt | grep "ESTABLISHED" | wc -l)
    
    # 檢查無線 ADB 狀態
    ADB_STATUS=$(adb shell netstat -nt | grep ":5555" | grep "ESTABLISHED" > /dev/null && echo "穩定" || echo "斷開")
    
    echo "[$(date +%H:%M:%S)] 模式: $STATE | 活躍連線: $CONNS | ADB: $ADB_STATUS"
    
    sleep 5
done

