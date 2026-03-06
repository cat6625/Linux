#!/system/bin/sh

# 檢查權限
if [ "$(id -u)" -ne 0 ]; then
    echo "⚠️ 警告: 目前非 Root 身份，可能無法讀取所有系統日誌。"
fi

echo "=========================================="
echo "   LINE VoIP 延遲診斷 (即時監控版)"
echo "=========================================="
echo "正在掃描事件... (若無輸出請嘗試切換至 Root)"

# 清除舊日誌快取，從現在開始監控
logcat -c

# 核心修正：
# 1. 使用 --line-buffered 確保 grep 每一行都即時噴出
# 2. 將邏輯簡化，減少 Shell 運算負擔
logcat -v time | grep --line-buffered -iE "jp.naver.line.android|VoIP|FCM|GCM|Chimera|am_kill|Telecom|ConnectivityService" | while read -r line
do
    # 取得當前時間
    now_ts=$(date +%s)

    # 根據關鍵字加上顏色標籤 (如果終端機支持)
    case "$line" in
        *"FCM"*|*"GCM"*)
            echo -e "\033[1;32m[📩 推播接收]\033[0m $line"
            ;;
        *"Start proc"*|"activity"*)
            echo -e "\033[1;36m[🚀 程序啟動]\033[0m $line"
            ;;
        *"VoIP"*|*"voip"*)
            echo -e "\033[1;33m[📞 語音引擎]\033[0m $line"
            ;;
        *"Chimera"*|*"am_kill"*)
            echo -e "\033[1;31m[💀 系統殺進程]\033[0m $line"
            ;;
        *)
            echo "[🔍 事件] $line"
            ;;
    esac
done
