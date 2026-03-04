#!/system/bin/sh

PKG="jp.naver.line.android"
ACT="VoIPServiceActivity"

echo "=== 終極體感延遲監控 (修正 30 秒消失問題) ==="

logcat -v time | grep -E "Start proc.*$PKG|Telecom.*CreateConnectionProcessor|setFocusedWindow:.*$ACT" | while read -r line; do
    
    ts=$(echo "$line" | grep -oE "[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{3}")
    now_s=$(date -d "1970-$ts" +%s.%3N)
    
    if echo "$line" | grep -q "Start proc"; then
        # 只要看到啟動，就紀錄為最早可能的起點
        first_start_s=$now_s
        echo ">>> [背景喚醒] $ts"

    elif echo "$line" | grep -q "Telecom"; then
        tele_s=$now_s
        # 如果 60 秒內有啟動過，就以啟動時間為準
        is_cold=$(awk "BEGIN {print ($first_start_s > 0 && ($tele_s - $first_start_s) < 60)}")
        if [ "$is_cold" = "1" ]; then
            start_point_s=$first_start_s
            mode="冷啟動 (含背景初始化)"
        else
            start_point_s=$tele_s
            mode="熱啟動 (直接建立)"
        fi

    elif echo "$line" | grep -q "setFocusedWindow"; then
        if [ ! -z "$start_point_s" ]; then
            diff=$(awk "BEGIN {print $now_s - $start_point_s}")
            echo "-----------------------------------------------"
            echo "✅ 偵測到通話畫面！"
            echo "模式: $mode"
            echo "🔥 體感總延遲: ${diff} 秒"
            echo "-----------------------------------------------"
            unset first_start_s
            unset start_point_s
        fi
    fi
done