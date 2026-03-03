#!/system/bin/sh
# LINE 網路與通訊隧道診斷工具 (Samsung M14 專用)

LINE_UID=$(pm list packages -U | grep jp.naver.line.android | sed 's/.*uid://' | tr -d '[:space:]')
FORMAT_UID="u0a${LINE_UID#1}"

echo "--- [網路隧道狀態檢查] ---"
# 檢查 LINE 是否有存活的長連線 Socket
NETSTAT_OUT=$(cat /proc/net/tcp | grep -i "$(printf '%X' $LINE_UID)")
if [ -z "$NETSTAT_OUT" ]; then
    echo " ⚠️ 偵測結果: LINE 目前無活躍 TCP 長連線 (已被系統回收)"
else
    echo " ✅ 偵測結果: LINE 長連線 Socket 存活中"
fi

echo ""
echo "--- [RRC/網路喚醒深度分析] ---"
dumpsys batterystats --history | awk -v target="$FORMAT_UID" '
function to_ms(t, a, n, ms) {
    ms=0;
    if (t ~ /h/) { split(t, a, "h"); ms += a[1]*3600000; t=a[2]; }
    if (t ~ /m/) { split(t, a, "m"); ms += a[1]*60000; t=a[2]; }
    if (t ~ /s/) { split(t, a, "s"); ms += a[1]*1000; t=a[2]; }
    if (t ~ /ms/) { split(t, a, "ms"); ms += a[1]; }
    return ms;
}
# 偵測推播進入 (信令起點)
/tmpwhitelist=/ && $0 ~ target { 
    push_start = to_ms($1); 
    active = 1;
} 
# 偵測網路同步 (關鍵：何時獲得網路傳輸權)
/connectivity/ && active {
    net_sync = to_ms($1);
    net_delay = net_sync - push_start;
}
# 偵測介面彈出 (UI 起點)
/\+top=/ && $0 ~ target { 
    if (active) { 
        ui_start = to_ms($1); 
        total_delay = ui_start - push_start;
        # 輸出分析：判斷是網路慢還是 UI 慢
        if (total_delay > 5000) {
            printf " 🚨 嚴重延遲偵測: %.2f 秒\n", total_delay/1000;
            if (net_delay > 0) printf "   └─ 網路恢復耗時: %.2f 秒\n", net_delay/1000;
            printf "   └─ UI 渲染等待: %.2f 秒\n", (total_delay - net_delay)/1000;
        }
        active = 0; net_delay = 0;
    }
}'
