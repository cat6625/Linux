#!/system/bin/sh

echo "=========================================="
echo "   LINE Push / VoIP Delay Diagnostic"
echo "=========================================="
echo "Waiting for events..."
echo ""

# 先測試 logcat 是否有權限
logcat -d -t 1 > /dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "[ERROR] logcat permission denied"
    echo "Please grant ADB logcat permission:"
    echo "  adb shell pm grant ... READ_LOGS"
    exit 1
fi

logcat -v time 2>/dev/null | while IFS= read -r line
do
    case "$line" in
        *"Start proc"*"jp.naver.line.android"*)
            echo ""
            echo "[LINE] Cold Start - process launched by system"
            echo "$line"
            echo ""
            ;;
        *"FirebaseInstanceIdReceiver"*)
            echo ""
            echo "[FCM] Push message arrived"
            echo "$line"
            echo ""
            ;;
        *"Destroyed live tcp sockets"*)
            echo ""
            echo "[TCP] Socket reset by system"
            echo "$line"
            echo ""
            ;;
        *"ConnectivityService"*)
            echo "[NET] Network event: $line"
            ;;
        *"SemWifi"*|*"OpenNetworkQos"*)
            echo "[WIFI] Samsung WiFi QoS event: $line"
            ;;
        *"Adding new incoming call"*)
            echo ""
            echo "[CALL] LINE incoming call established"
            echo "$line"
            echo ""
            ;;
        *"lmkd"*"kill"*|*"am_kill"*|*"proc died"*)
            echo ""
            echo "[KILL] System killed an APP"
            echo "$line"
            echo ""
            ;;
    esac
done