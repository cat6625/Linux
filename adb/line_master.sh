#!/system/bin/sh
# LINE 終極監控整合版 - 適用於 Samsung M14
# 功能：自動檢測權限、抓取最近漏接紀錄、計算啟動延遲

echo "============================================="
echo "      Samsung M14 LINE 穩定性診斷工具"
echo "============================================="

# 1. 自動定位 UID
LINE_UID=$(pm list packages -U | grep jp.naver.line.android | sed 's/.*uid://')
echo "🔍 當前 LINE UID: $LINE_UID"

# 2. 環境權限快檢 (原 line5 邏輯)
echo "[1/3] 權限驗證:"
BUCKET=$(am get-standby-bucket jp.naver.line.android 2>/dev/null)
WHITELIST=$(dumpsys deviceidle whitelist | grep "jp.naver.line.android")

if [ "$BUCKET" -le 10 ]; then echo " ✅ 活躍等級: $BUCKET (最高)"; else echo " ⚠️ 等級偏低: $BUCKET"; fi
if [ ! -z "$WHITELIST" ]; then echo " ✅ Doze 白名單: 已加入"; else echo " ❌ 不在白名單內"; fi

# 3. 抓取最近 5 分鐘異常 (原 line6 邏輯)
echo ""
echo "[2/3] 最近 5 分鐘異常監控 (回溯模式):"
T_START=$(date -d "@$(($(date +%s) - 300))" "+%m-%d %H:%M:%S")
LOG_OUT="/sdcard/line_issue_report.txt"

# 增加 Chimera 與 Killing 關鍵字
logcat -d -t "$T_START.000" | grep -iE "Killing.*line|Chimera|Destroyed live tcp|mState=IDLE|BLOCKED|$LINE_UID" > $LOG_OUT

if [ -s "$LOG_OUT" ]; then
    echo " 🚩 偵測到異常紀錄！請查看: $LOG_OUT"
    grep -iE "Killing|Chimera|Destroyed" $LOG_OUT | tail -n 3
else
    echo " ✅ 過去 5 分鐘內無重大連線中斷或處決事件。"
fi

# 4. 歷史延遲分析 (針對 u0aXXXX 格式強化)
echo ""
echo "[3/3] 歷史冷啟動延遲分析 (FCM -> Top)"
# 修正 UID 匹配格式，將 11199 轉為 u0a1199
FORMAT_UID="u0a${LINE_UID#1}" 

dumpsys batterystats --history | awk -v target="$FORMAT_UID" '
function to_ms(t, a, n, ms) {
    ms=0;
    if (t ~ /h/) { split(t, a, "h"); ms += a[1]*3600000; t=a[2]; }
    if (t ~ /m/) { split(t, a, "m"); ms += a[1]*60000; t=a[2]; }
    if (t ~ /s/) { split(t, a, "s"); ms += a[1]*1000; t=a[2]; }
    if (t ~ /ms/) { split(t, a, "ms"); ms += a[1]; }
    return ms;
}
# 彈性匹配：只要包含 u0a1199 且含有白名單或啟動標記
$0 ~ "tmpwhitelist="target { 
    start = to_ms($1); 
    found_push = 1;
} 
$0 ~ "\\+top="target { 
    if (found_push) { 
        end = to_ms($1); 
        diff = end - start;
        if (diff > 0 && diff < 60000) {
            printf " 🚀 偵測到推播喚醒延遲: %.3f 秒\n", diff/1000;
        }
        found_push = 0; 
    }
}'
