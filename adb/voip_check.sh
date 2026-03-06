#!/system/bin/sh

echo "--- 極簡監控模式啟動 ---"

# 使用 --line-buffered 強制每一行都立即輸出
logcat -v time | grep --line-buffered -iE "jp.naver.line.android|FCM|VoIP|Chimera|am_kill" | while read -r line
do
    case "$line" in
        *"jp.naver.line.android"*)
            echo "🔥 偵測到 LINE 活動: $line"
            ;;
        *"FCM"*|*"GCM"*)
            echo "📩 偵測到 推播訊息: $line"
            ;;
        *"Chimera"*|*"am_kill"*)
            echo "💀 系統正在清理程序: $line"
            ;;
        *)
            echo "🔍 其他相關事件: $line"
            ;;
    esac
done
