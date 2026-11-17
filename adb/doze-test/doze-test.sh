#!/bin/bash
# doze-test.sh v2 — 一鍵待機測試:重置統計 → 電腦睡眠 → 醒來後自動重連 adb 並紀錄 → 產生摘要
#
# 用法:   ./doze-test.sh            (在 doze_summary.py 所在的資料夾,或與它放在同一個資料夾)
# 需要:   手機已開啟無線偵錯並與電腦配對過;電腦可用 `systemctl suspend`
# 注意:   測試開始前請確認 FMM(尋找我的手機)狀態、手機未充電、預設桌面是你要測的那個。
#
# v2 改動(相對於 v1):
#   1. 修正:mem_end 的 Lawnchair 指令缺了 `meminfo`(v1 寫成 `dumpsys ch.deletescape.lawnchair.plah`,抓不到資料)
#   2. 兩個 launcher 的 meminfo 現在由迴圈處理,不會漏;摘要腳本也能在同一個檔案裡解析多個進程
#   3. battery / meminfo 檔案開頭寫入 `# captured:` 時間,摘要才算得出「區間放電」
#   4. adb 重連改成重試迴圈;失敗時不會繼續寫出一堆空檔案,而是提示你亮屏手機後再試
#   5. 資料擷取順序改為「時間敏感的先抓」(deviceidle、電池、鬧鐘),體積大的 batterystats 後抓
#   6. 事前檢查下一個「會喚醒手機的鬧鐘」(FMM)距離現在多久,太近會提醒
#   7. 每個擷取檔都檢查是否為空;指令改用 -s 指定裝置;變數加引號

set -u

# ===================== 設定 =====================
ADB_ADDR="192.168.1.142:41077"   # 無線偵錯的 IP:埠號(重開無線偵錯後埠號會變,要修正)
PKGS=("com.sec.android.app.launcher" "ch.deletescape.lawnchair.plah")   # 要量記憶體的 launcher 套件
RECONNECT_TRIES=24               # 每次間隔 5 秒,共約 2 分鐘
MIN_ALARM_MIN=125                # 下一個 wake-from-idle 鬧鐘至少要在幾分鐘之後
WANT_NETSTATS=0                  # 1 = 一併匯出 netstats(很大,通常不需要)
SLEEP_SCREEN=1                   # 1 = 重置後先用 KEYCODE_SLEEP 讓螢幕立刻關閉(未在所有機型驗證)
# =================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TIMESTAMP="$(date +"%Y%m%d_%H%M")"
OUT_DIR="$SCRIPT_DIR/$TIMESTAMP"
mkdir -p "$OUT_DIR"
A=(adb -s "$ADB_ADDR")

stamp() { date +"# captured: %Y-%m-%d %H:%M:%S"; }
log()   { echo "$(date +"%H:%M:%S") $*" | tee -a "$OUT_DIR/timeline.txt"; }

# capture <檔名> <指令...>:把指令輸出存檔,並檢查不是空的
capture() {
  local f="$1"; shift
  "$@" > "$OUT_DIR/$f" 2>&1
  if [ ! -s "$OUT_DIR/$f" ]; then
    log "⚠ $f 是空的(adb 連線可能中斷)"
  fi
}

snapshot_battery() { { stamp; "${A[@]}" shell dumpsys battery; } > "$OUT_DIR/$1"; }

snapshot_mem() {
  { stamp; } > "$OUT_DIR/$1"
  for p in "${PKGS[@]}"; do
    "${A[@]}" shell dumpsys meminfo "$p" >> "$OUT_DIR/$1"
  done
}

connect_adb() {
  local i
  for i in $(seq 1 "$RECONNECT_TRIES"); do
    adb connect "$ADB_ADDR" >/dev/null 2>&1
    if [ "$(adb -s "$ADB_ADDR" get-state 2>/dev/null)" = "device" ] && "${A[@]}" shell true >/dev/null 2>&1; then
      log "adb 已連線(第 $i 次嘗試)"
      return 0
    fi
    adb disconnect "$ADB_ADDR" >/dev/null 2>&1   # 清掉 offline 狀態再重試
    sleep 5
  done
  return 1
}

# 讓電腦睡眠。GNOME 桌面常有「user session inhibited」的阻擋型 inhibitor(例如播放影音的瀏覽器、遠端桌面、Caffeine 類延伸),
# 這時單純的 `systemctl suspend` 會失敗:Operation inhibited by "tdd" (PID … "gnome-session-b")。
# 所以先試一般的 suspend,被擋就改用 --ignore-inhibitors(這個選項需要 polkit 授權,本機實測可用)。
suspend_host() {
  if systemctl suspend 2>"$OUT_DIR/suspend_err.txt"; then
    return 0
  fi
  log "systemctl suspend 失敗($(head -n1 "$OUT_DIR/suspend_err.txt")),改用 --ignore-inhibitors"
  if systemctl --ignore-inhibitors suspend 2>>"$OUT_DIR/suspend_err.txt"; then
    return 0
  fi
  log "⚠ 仍無法讓電腦睡眠(詳見 suspend_err.txt)。請先確認誰擋住了睡眠:systemd-inhibit --list"
  return 1
}

# ---------------------------------------------------------------- 開始前
log "開始前:連線 adb"
connect_adb || { echo "無法連線 $ADB_ADDR,請確認 IP:埠號(無線偵錯畫面上顯示的)"; exit 1; }

# 預設桌面與電量
"${A[@]}" shell cmd role get-role-holders android.app.role.HOME | tee "$OUT_DIR/home_start.txt"
"${A[@]}" shell dumpsys battery | grep -E "^  (AC|USB|Wireless) powered|^  level"

# 下一個「會喚醒手機」的鬧鐘(FMM 的 defaultScanStartTimer 之類),Samsung 的 min_time_to_alarm=1h
{ stamp; "${A[@]}" shell dumpsys alarm; } > "$OUT_DIR/alarm_start_full.txt"
{ stamp; grep -B2 -A8 "defaultScanStartTimer" "$OUT_DIR/alarm_start_full.txt"; } > "$OUT_DIR/alarm_start.txt"
NEXT="$(grep -A8 "Next wake from idle" "$OUT_DIR/alarm_start_full.txt" | grep -m1 -oE "triggerTime=[0-9-]+ [0-9:]+" | cut -d= -f2)"
if [ -n "$NEXT" ]; then
  PHONE_NOW="$("${A[@]}" shell date +"%Y-%m-%d %H:%M:%S" | tr -d '\r')"   # 用手機的「現在」,避免電腦與手機時鐘差
  NEXT_MIN=$(( ( $(date -d "$NEXT" +%s) - $(date -d "$PHONE_NOW" +%s) ) / 60 ))
  log "下一個會喚醒手機的鬧鐘:$NEXT(約 ${NEXT_MIN} 分鐘後)"
  if [ "$NEXT_MIN" -lt "$MIN_ALARM_MIN" ]; then
    echo "⚠ 這個鬧鐘距離現在不到 ${MIN_ALARM_MIN} 分鐘;Doze 很可能放棄進入 deep idle(min_time_to_alarm=1h)。"
    read -r -p "仍要開始測試嗎?[y/N] " ans
    [ "$ans" = "y" ] || [ "$ans" = "Y" ] || exit 0
  fi
else
  log "目前沒有排定的 wake-from-idle 鬧鐘"
fi

# 事前快照(先拍快照,最後才 reset,這樣統計起點就是電腦睡眠前的那一刻)
snapshot_mem mem_start.txt
snapshot_battery battery_start.txt
"${A[@]}" shell dumpsys deviceidle unforce
"${A[@]}" shell dumpsys batterystats --enable full-wake-history
"${A[@]}" shell dumpsys batterystats --reset
log "batterystats 已重置"

if [ "$SLEEP_SCREEN" = "1" ]; then
  "${A[@]}" shell input keyevent KEYCODE_SLEEP    # 讓螢幕立刻關閉;Doze 計時從這裡開始
fi

# ---------------------------------------------------------------- 電腦睡眠
log "電腦即將睡眠(醒來後會自動繼續)"
sleep 2
if ! suspend_host; then
  echo "電腦無法睡眠。測試仍在進行,但電腦醒著會讓手機多耗電(實測約 +40 mAh/h),請手動讓電腦睡眠,或按 Ctrl+C 結束。"
  read -r -p "已手動睡眠並醒來後,按 Enter 繼續擷取:" _
fi
log "電腦已醒來"

# ---------------------------------------------------------------- 醒來後
if ! connect_adb; then
  echo
  echo "adb 連不上(常見是 No route to host)。請亮屏手機約 5 秒讓 adb 連線,然後按 Enter 重試。"
  echo "這幾秒的亮屏會被記進統計;摘要會標出「測試期間有亮屏」,請把有效待機區間算到那裡為止。"
  read -r -p "已亮屏?按 Enter 重試:" _
  log "使用者亮屏手機後重試"
  connect_adb || { echo "仍然連不上,結束。請手動執行 doze-test.sh 中「醒來後」的部分。"; exit 1; }
fi

# 時間敏感的先抓
capture deviceidle.txt "${A[@]}" shell dumpsys deviceidle
snapshot_battery battery_end.txt
{ stamp; "${A[@]}" shell dumpsys alarm | grep -B2 -A8 "defaultScanStartTimer"; } > "$OUT_DIR/alarm_end.txt"
snapshot_mem mem_end.txt
"${A[@]}" shell cmd role get-role-holders android.app.role.HOME | tee "$OUT_DIR/home_end.txt"

# 體積大的後抓
capture full.txt    "${A[@]}" shell dumpsys batterystats
capture checkin.txt "${A[@]}" shell dumpsys batterystats --checkin
capture history.txt "${A[@]}" shell dumpsys batterystats --history
if [ "$WANT_NETSTATS" = "1" ]; then
  capture netstats.txt "${A[@]}" shell dumpsys netstats detail
fi

# 電腦端的睡眠 / 喚醒紀錄(處理慢,放最後)
journalctl -b | grep -iE "suspend|resume|sleep|PM: " > "$OUT_DIR/suspend.txt"

# ---------------------------------------------------------------- 摘要
python3 "$SCRIPT_DIR/doze_summary.py" "$OUT_DIR/full.txt" \
  --checkin "$OUT_DIR/checkin.txt" \
  --pkg "$(IFS=,; echo "${PKGS[*]}")" \
  --suspend "$OUT_DIR/suspend.txt" --deviceidle "$OUT_DIR/deviceidle.txt" \
  --mem "$OUT_DIR/mem_start.txt" "$OUT_DIR/mem_end.txt" \
  --battery "$OUT_DIR/battery_start.txt" "$OUT_DIR/battery_end.txt" \
  | tee "$OUT_DIR/summary-$TIMESTAMP.txt"

log "完成:$OUT_DIR"
