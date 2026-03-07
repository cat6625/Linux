#!/system/bin/sh

echo "=========================================="
echo "   LINE Push / VoIP Delay Diagnostic v3"
echo "=========================================="
echo "Waiting for events..."
echo ""

logcat -d -t 1 > /dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "[ERROR] logcat permission denied"
    exit 1
fi

LOG="/sdcard/line_diag.txt"
> "$LOG"

out() {
    echo "$1"
    echo "$1" >> "$LOG"
}

fcm_ts=""
last_tcp_ts=""

logcat -v time 2>/dev/null | while IFS= read -r line; do

    # 擷取時間 (前兩欄: MM-DD HH:MM:SS.mmm)
    set -- $line
    ts="$1 $2"

    case "$line" in

        *"Start proc"*"jp.naver.line.android"*)
            out ""
            out "[LINE-COLDSTART] $ts"
            out "  $line"
            out ""
            ;;

        *"FirebaseInstanceIdReceiver"*)
            fcm_ts="$ts"
            out ""
            out "[FCM] Push arrived @ $ts"
            out "  $line"
            out ""
            ;;

        *"Adding new incoming call"*"jp.naver.line"*)
            out ""
            out "[CALL] Incoming call @ $ts"
            if [ -n "$fcm_ts" ]; then
                out "  ** FCM was @ $fcm_ts => check delay manually **"
                fcm_ts=""
            fi
            out "  $line"
            out ""
            ;;

        *"Destroyed live tcp sockets"*)
            out ""
            out "[TCP-RESET] $ts"
            if [ -n "$last_tcp_ts" ]; then
                out "  (prev TCP reset was @ $last_tcp_ts)"
            fi
            last_tcp_ts="$ts"
            out "  $line"
            out ""
            ;;

        *"lmkd"*"kill"*|*"am_kill"*|*"proc died"*)
            out ""
            out "[KILL] $ts"
            out "  $line"
            out ""
            ;;

        *"DeviceIdleController"*)
            case "$line" in
                *"become idle"*|*"become active"*|*"step to"*)
                    out "[DOZE] $ts | $line"
                    ;;
            esac
            ;;

        *"mobilewips"*|*"CarrierWifi"*|*"carrierwifi"*)
            out "[WIPS/CW] $ts | $line"
            ;;

        *"ConnectivityService"*)
            case "$line" in
                *"Removing from current network"*|\
                *"releasing NetworkRequest"*"jp.naver.line"*|\
                *"null"*"→"*|\
                *"NetworkReassignment"*)
                    out "[NET-WARN] $ts | $line"
                    ;;
            esac
            ;;

        *"SemWifiOptimizer"*)
            out "[WIFI-OPT] $ts | $line"
            ;;

        *"SemWifiServiceDetector"*"NSD results"*)
            out "[WIFI-NSD] $ts | $line"
            ;;

    esac
done