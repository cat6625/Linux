#!/usr/bin/env bash
# -------------------------------------------------------------
# Termux 版 Doze 測試 – 完整流程（含手動「下一步」）
# -------------------------------------------------------------
set -euo pipefail          # 只在變數已宣告時才會拋錯

# -------------------- 設定區 --------------------
ADB_ADDR="127.0.0.1:41077"                 # Termux 本機的 ADB 端點
PKGS=("com.sec.android.app.launcher" "ch.deletescape.lawnchair.plah")
RECONNECT_TRIES=24
MIN_ALARM_MIN=125
WANT_NETSTATS=0
SLEEP_SCREEN=1                # 1 = 立刻讓螢幕關閉，讓 Doze 計時從此開始
#TEST_WAIT=300                # 等待 (秒) 讓手機自行進入 deep idle（可自行調整）#無效
# ------------------------------------------------

# ---------- 建立輸出目錄 ----------
TIMESTAMP="$(date +"%Y%m%d_%H%M")"
OUT_DIR="${HOME}/storage/downloads/doze-test/${TIMESTAMP}"
mkdir -p "$OUT_DIR"

# ---------- 日誌 ----------
log() { echo "[TERMUX] $(date +%H:%M:%S) $*" | tee -a "$OUT_DIR/timeline.txt"; }
stamp() { date +"# captured: %Y-%m-%d %H:%M:%S"; }

# ---------- ADB 連線 ----------
connect_adb() {
  for i in $(seq 1 "$RECONNECT_TRIES"); do
    adb connect "$ADB_ADDR" >/dev/null 2>&1
    if [ "$(adb -s "$ADB_ADDR" get-state 2>/dev/null)" = "device" ]; then
      log "ADB 已連線（第 $i 次嘗試）"
      return 0
    fi
    sleep 5
  done
  return 1
}

# ---------- 輔助函式 ----------
capture() {
  local f="$1"; shift
  "$@" > "$OUT_DIR/$f" 2>&1
  if [ ! -s "$OUT_DIR/$f" ]; then
    log "⚠ $f 為空（可能是 ADB 斷線）"
  fi
}
snapshot_battery() { { stamp; adb -s "$ADB_ADDR" shell dumpsys battery; } > "$OUT_DIR/$1"; }
snapshot_mem() {
  { stamp; } > "$OUT_DIR/$1"
  for p in "${PKGS[@]}"; do
    adb -s "$ADB_ADDR" shell dumpsys meminfo "$p" >> "$OUT_DIR/$1"
  done
}

# ---------- 主流程 ----------
log "=== Doze 測試開始 ==="
connect_adb || { echo "無法連線到本機 ADB，請確認 Termux 已開啟「無線除錯」"; exit 1; }

# 1️⃣ 先檢查未來的喚醒鬧鐘
{ stamp; adb -s "$ADB_ADDR" shell dumpsys alarm; } > "$OUT_DIR/alarm_start_full.txt"
NEXT=$(grep -A8 "Next wake from idle" "$OUT_DIR/alarm_start_full.txt" |
       grep -m1 -oE "triggerTime=[0-9-]+ [0-9:]+" | cut -d= -f2 || true)

if [ -n "$NEXT" ]; then
  PHONE_NOW=$(adb -s "$ADB_ADDR" shell date +"%Y-%m-%d %H:%M:%S" | tr -d '\r')
  NEXT_MIN=$(( ( $(date -d "$NEXT" +%s) - $(date -d "$PHONE_NOW" +%s) ) / 60 ))
  log "下一個喚醒鬧鐘在 $NEXT（約 ${NEXT_MIN} 分鐘後）"
  if [ "$NEXT_MIN" -lt "$MIN_ALARM_MIN" ]; then
    echo "⚠ 鬧鐘距離現在不到 $MIN_ALARM_MIN 分鐘，Doze 可能無法進入 deep idle"
    read -p "仍然要繼續嗎？[y/N] " ans
    [[ "$ans" =~ ^[Yy]$ ]] || { log "使用者取消測試"; exit 0; }
  fi
else
  log "目前沒有排定的 wake‑from‑idle 鬧鐘"
fi

# 2️⃣ 測試前快照
snapshot_mem mem_start.txt
snapshot_battery battery_start.txt
adb -s "$ADB_ADDR" shell dumpsys deviceidle unforce
adb -s "$ADB_ADDR" shell dumpsys batterystats --enable full-wake-history
adb -s "$ADB_ADDR" shell dumpsys batterystats --reset
log "batterystats 已重置"

# 3️⃣ 立即關螢幕（讓 Doze 計時從此開始）
if [ "$SLEEP_SCREEN" = "1" ]; then
  adb -s "$ADB_ADDR" shell input keyevent KEYCODE_SLEEP
  log "已送出 KEYCODE_SLEEP"
fi

# -------------------------------------------------
# 4️⃣ 手動一步：使用者在手機上按下 Enter 繼續
# -------------------------------------------------
echo -e "\n=== 手動步驟 ==="
echo "當你想正式結束測試時，請在 Termux 鍵盤（或藍牙鍵盤）敲 Enter。"
read -p "在手機上按 Enter 後繼續 → " _

#log "使用者確認，開始等待 ${TEST_WAIT}s 讓手機進入 deep idle"
#sleep "$TEST_WAIT"

# -------------------------------------------------
# 5️⃣ 醒來後確保 ADB 仍連線
# -------------------------------------------------
connect_adb || {
  echo "ADB 斷線，請亮屏約 5 秒再按 Enter 重試"
  read -p "已亮屏? 按 Enter 重試 → " _
  connect_adb || { log "仍無法連線，測試結束"; exit 1; }
}
log "ADB 重新連線成功"

# -------------------------------------------------
# 6️⃣ 立即抓取時間敏感資料
# -------------------------------------------------
capture deviceidle.txt adb -s "$ADB_ADDR" shell dumpsys deviceidle
snapshot_battery battery_end.txt
{ stamp; adb -s "$ADB_ADDR" shell dumpsys alarm | grep -B2 -A8 "defaultScanStartTimer"; } > "$OUT_DIR/alarm_end.txt"
snapshot_mem mem_end.txt
adb -s "$ADB_ADDR" shell cmd role get-role-holders android.app.role.HOME | tee "$OUT_DIR/home_end.txt"

# -------------------------------------------------
# 7️⃣ 抓取較大檔案（batterystats、optional netstats）
# -------------------------------------------------
capture full.txt    adb -s "$ADB_ADDR" shell dumpsys batterystats
capture checkin.txt adb -s "$ADB_ADDR" shell dumpsys batterystats --checkin
capture history.txt adb -s "$ADB_ADDR" shell dumpsys batterystats --history
if [ "$WANT_NETSTATS" = "1" ]; then
  capture netstats.txt adb -s "$ADB_ADDR" shell dumpsys netstats detail
fi

# -------------------------------------------------
# 8️⃣ 產生摘要（仍在手機端執行）
# -------------------------------------------------
log "呼叫 Python 產生摘要 …"
python3 "${HOME}/storage/downloads/doze-test/doze_summary-termux.py" "$OUT_DIR/full.txt" \
  --checkin "$OUT_DIR/checkin.txt" \
  --pkg "$(IFS=,; echo "${PKGS[*]}")" \
  --deviceidle "$OUT_DIR/deviceidle.txt" \
  --mem "$OUT_DIR/mem_start.txt" "$OUT_DIR/mem_end.txt" \
  --battery "$OUT_DIR/battery_start.txt" "$OUT_DIR/battery_end.txt" \
  | tee "$OUT_DIR/summary-${TIMESTAMP}.txt"

log "=== 測試完成，所有檔案位於 $OUT_DIR ==="
