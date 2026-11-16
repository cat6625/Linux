#!/bin/bash
# doze-test-usb.sh — USB 版一鍵待機測試
#
# 流程:偵測手機 → 事前檢查 → 快照並重置統計 → 提示「請拔除 USB」→ 待機
#       → 偵測到你把 USB 接回去 → 自動擷取資料 → 產生摘要
# 你只需要照畫面提示「拔掉 USB」「接回 USB」,不需要輸入任何 adb 指令。
#
# 為什麼要「真的拔掉」USB:USB 連著時手機在充電,Doze 的 deep idle 不會進入,而且 batterystats 的放電統計也無效。
#   MODE="unplug"(預設):實際拔掉 USB。耗電與 Doze 數據都有效。
#   MODE="sim":USB 一直連著,用 `dumpsys battery unplug` 模擬拔電。只適合看「Doze 能不能進去、何時進去」;
#              手機其實還在充電,耗電(mAh)數據無效。腳本結束時會自動 `dumpsys battery reset`。
#
# 用法:   ./doze-test-usb.sh      (與 doze_summary.py 放在同一個資料夾;手機先用 USB 接上並允許 USB 偵錯)
# 注意:   我無法在你的手機上實測 MODE="sim" 與 force-stop FMM 這兩項,請先短時間試跑確認。
#
# 解決 "adb: more than one device/emulator":
#   關掉手機的無線偵錯後,電腦的 adb 仍可能留著舊的 192.168.x.x:埠號(offline)。本腳本一開始會 `adb disconnect`
#   清掉殘留項目,並只選用 USB 裝置(設定 ANDROID_SERIAL),所以不會再出現這個錯誤。

set -u

# ===================== 設定 =====================
MODE="unplug"                    # unplug | sim
TEST_HOURS=3                     # 預計待機時數(只用來提醒與檢查,不會自動結束測試)
PKGS=("com.sec.android.app.launcher" "ch.deletescape.lawnchair.plah")   # 要量記憶體的 launcher 套件
MIN_ALARM_MIN=125                # 下一個 wake-from-idle 鬧鐘至少要在幾分鐘之後
STOP_FMM=0                       # 1 = 發現 OfflineFindingService 時直接嘗試 force-stop(不詢問)
WANT_NETSTATS=0                  # 1 = 一併匯出 netstats
SLEEP_SCREEN=1                   # 1 = 重置後先用 KEYCODE_SLEEP 讓螢幕立刻關閉
# =================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TIMESTAMP="$(date +"%Y%m%d_%H%M")"
OUT_DIR="$SCRIPT_DIR/${TIMESTAMP}-usb"
mkdir -p "$OUT_DIR"

stamp() { date +"# captured: %Y-%m-%d %H:%M:%S"; }
log()   { echo "$(date +"%H:%M:%S") $*" | tee -a "$OUT_DIR/timeline.txt"; }
beep()  { printf '\a'; command -v notify-send >/dev/null 2>&1 && notify-send "doze-test" "$*" 2>/dev/null; return 0; }

capture() {   # capture <檔名> <指令...>:輸出存檔,並檢查不是空的
  local f="$1"; shift
  "$@" > "$OUT_DIR/$f" 2>&1
  [ -s "$OUT_DIR/$f" ] || log "⚠ $f 是空的(adb 連線可能中斷)"
}
snapshot_battery() { { stamp; adb shell dumpsys battery; } > "$OUT_DIR/$1"; }
snapshot_mem() {
  { stamp; } > "$OUT_DIR/$1"
  local p
  for p in "${PKGS[@]}"; do adb shell dumpsys meminfo "$p" >> "$OUT_DIR/$1"; done
}

REM_PID=""
cleanup() {
  [ -n "$REM_PID" ] && kill "$REM_PID" 2>/dev/null
  if [ "$MODE" = "sim" ]; then
    adb shell dumpsys battery reset >/dev/null 2>&1
    log "已執行 dumpsys battery reset(結束模擬拔電)"
  fi
}
trap cleanup EXIT

# ---------------------------------------------------------------- 1. 找到 USB 手機
pick_device() {
  adb disconnect >/dev/null 2>&1       # 清掉殘留的無線偵錯項目(避免 more than one device/emulator)
  adb start-server >/dev/null 2>&1
  local DEVS=() s
  while true; do
    mapfile -t DEVS < <(adb devices | awk 'NR>1 && $2=="device" && $1 !~ /:/ && $1 !~ /^adb-/ && $1 !~ /_tcp/ {print $1}')
    [ "${#DEVS[@]}" -ge 1 ] && break
    if adb devices | awk 'NR>1 && $2=="unauthorized"{f=1} END{exit !f}'; then
      echo "手機顯示 unauthorized:請解鎖手機,在跳出的視窗按「允許 USB 偵錯」(建議勾選「一律允許」)。"
    else
      echo "找不到 USB 裝置:請用 USB 線接上手機,並確認已開啟 USB 偵錯。"
    fi
    read -r -p "處理好後按 Enter 重試(Ctrl+C 結束):" _
  done
  if [ "${#DEVS[@]}" -gt 1 ]; then
    echo "偵測到多支手機,請輸入編號選擇:"
    select s in "${DEVS[@]}"; do
      [ -n "${s:-}" ] && SERIAL="$s" && break
    done
  else
    SERIAL="${DEVS[0]}"
  fi
  export ANDROID_SERIAL="$SERIAL"
}

log "尋找 USB 手機…"
pick_device
log "使用裝置 $ANDROID_SERIAL($(adb shell getprop ro.product.model | tr -d '\r'),Android $(adb shell getprop ro.build.version.release | tr -d '\r'))"

# ---------------------------------------------------------------- 2. 事前檢查
adb shell cmd role get-role-holders android.app.role.HOME | tr -d '\r' | tee "$OUT_DIR/home_start.txt"
adb shell dumpsys battery | grep -E "^  (AC|USB|Wireless) powered|^  level"

# 2a. Samsung:尋找我的手機的 OfflineFindingService 是否還在執行(只關設定開關不夠,見指南第 8 節)
check_fmm() {
  local n
  n="$(adb shell dumpsys activity services com.samsung.android.fmm 2>/dev/null | grep -c "OfflineFindingService")"
  if [ "${n:-0}" -gt 0 ]; then
    log "⚠ 偵測到 OfflineFindingService 正在執行(它會排定鬧鐘,擋住 deep idle)"
    local ans="s"
    if [ "$STOP_FMM" != "1" ]; then
      echo "  [s] 讓腳本嘗試 force-stop   [m] 我自己到手機上停止(開發人員選項 → 正在運作的服務 → 尋找我的手機 → 停止)   [i] 忽略"
      read -r -p "請選擇 [s/m/i]:" ans
    fi
    case "$ans" in
      s|S) adb shell am force-stop com.samsung.android.fmm; sleep 2; log "已嘗試 force-stop com.samsung.android.fmm" ;;
      m|M) read -r -p "停止後按 Enter:" _ ;;
      *) log "略過 FMM 檢查" ;;
    esac
  else
    log "未偵測到 OfflineFindingService(若不確定,仍建議在手機上看一次「正在運作的服務」)"
  fi
}
check_fmm

# 2b. 下一個「會喚醒手機」的鬧鐘(FMM 的 defaultScanStartTimer 之類),Samsung 的 min_time_to_alarm=1h
{ stamp; adb shell dumpsys alarm; } > "$OUT_DIR/alarm_start_full.txt"
{ stamp; grep -B2 -A8 "defaultScanStartTimer" "$OUT_DIR/alarm_start_full.txt"; } > "$OUT_DIR/alarm_start.txt"
NEXT="$(grep -A8 "Next wake from idle" "$OUT_DIR/alarm_start_full.txt" | grep -m1 -oE "triggerTime=[0-9-]+ [0-9:]+" | cut -d= -f2)"
if [ -n "$NEXT" ]; then
  PHONE_NOW="$(adb shell date +"%Y-%m-%d %H:%M:%S" | tr -d '\r')"
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

# ---------------------------------------------------------------- 3. 快照並重置(最後才 reset)
snapshot_mem mem_start.txt
snapshot_battery battery_start.txt
adb shell dumpsys deviceidle unforce
adb shell dumpsys batterystats --enable full-wake-history
adb shell dumpsys batterystats --reset
log "batterystats 已重置"
[ "$SLEEP_SCREEN" = "1" ] && adb shell input keyevent KEYCODE_SLEEP    # 讓螢幕關閉,Doze 計時才會開始

# ---------------------------------------------------------------- 4. 待機
T0=0
if [ "$MODE" = "unplug" ]; then
  echo
  echo "=============================================================="
  echo "  請現在「拔除 USB 線」。拔掉後不要碰手機,待機從拔線那一刻開始。"
  echo "=============================================================="
  beep "請拔除 USB 線"
  while [ "$(adb get-state 2>/dev/null)" = "device" ]; do sleep 2; done
  T0="$(date +%s)"
  log "偵測到 USB 已拔除,待機開始"
  echo "預計待機 ${TEST_HOURS} 小時,約 $(date -d "+${TEST_HOURS} hours" +%H:%M) 以後再接回 USB。"
  echo "時間到後,請把 USB 接回手機;偵測到後腳本會自動繼續,不需要按任何鍵。"
  ( sleep $((TEST_HOURS * 3600)); beep "待機時間到,可以接回 USB 了" ) &
  REM_PID=$!
  adb wait-for-device
  kill "$REM_PID" 2>/dev/null; REM_PID=""
  T1="$(date +%s)"
  sleep 3
  log "偵測到 USB 已接回(待機約 $(( (T1 - T0) / 60 )) 分鐘),開始擷取資料"
  if [ $(( T1 - T0 )) -lt $(( TEST_HOURS * 3600 * 8 / 10 )) ]; then
    log "⚠ 待機時間比預計的 ${TEST_HOURS} 小時短不少;這組數據可能不足以進入 deep idle(約需 1 小時以上)"
  fi
else
  adb shell dumpsys battery unplug
  log "已模擬拔電(MODE=sim):手機實際上仍在充電,耗電(mAh)數據無效,只看 Doze 狀態"
  echo "USB 保持連接,等待 ${TEST_HOURS} 小時(Ctrl+C 可中止,中止時會自動 dumpsys battery reset)…"
  T0="$(date +%s)"
  END=$(( T0 + TEST_HOURS * 3600 ))
  while [ "$(date +%s)" -lt "$END" ]; do sleep 30; done
  T1="$(date +%s)"
  log "待機時間到,開始擷取資料"
fi

# ---------------------------------------------------------------- 5. 擷取(時間敏感的先抓)
capture deviceidle.txt adb shell dumpsys deviceidle
snapshot_battery battery_end.txt
{ stamp; adb shell dumpsys alarm | grep -B2 -A8 "defaultScanStartTimer"; } > "$OUT_DIR/alarm_end.txt"
snapshot_mem mem_end.txt
adb shell cmd role get-role-holders android.app.role.HOME | tr -d '\r' | tee "$OUT_DIR/home_end.txt"

capture full.txt    adb shell dumpsys batterystats
capture checkin.txt adb shell dumpsys batterystats --checkin
capture history.txt adb shell dumpsys batterystats --history
[ "$WANT_NETSTATS" = "1" ] && capture netstats.txt adb shell dumpsys netstats detail

# 檢查 batterystats 的「Time on battery」是否與實際待機時間相符(不相符代表統計可能被自動重置)
TOB="$(python3 - "$OUT_DIR/full.txt" <<'PY'
import re, sys
t = open(sys.argv[1], encoding="utf-8", errors="ignore").read()
m = re.search(r"Time on battery: (.*?) \(100\.0%\) realtime", t)
def ms(s):
    return sum(int(v) * {"d": 86400000, "h": 3600000, "ms": 1, "m": 60000, "s": 1000}[u]
               for v, u in re.findall(r"(\d+)\s*(d|h|ms|m|s)", s))
print(ms(m.group(1)) // 1000 if m else -1)
PY
)"
ELAPSED=$(( T1 - T0 ))
if [ "${TOB:--1}" -gt 0 ] && [ "$ELAPSED" -gt 0 ]; then
  DIFF=$(( TOB > ELAPSED ? TOB - ELAPSED : ELAPSED - TOB ))
  LIMIT=$(( ELAPSED * 15 / 100 )); [ "$LIMIT" -lt 300 ] && LIMIT=300
  if [ "$DIFF" -gt "$LIMIT" ]; then
    log "⚠ batterystats 的 Time on battery(${TOB}s)與實際待機時間(${ELAPSED}s)相差 ${DIFF}s,統計可能在途中被重置,請小心使用這組數據"
  else
    log "Time on battery(${TOB}s)與實際待機時間(${ELAPSED}s)相符"
  fi
fi

# ---------------------------------------------------------------- 6. 摘要
# USB 版:接回 USB 後手機立刻開始充電,battery_end 的 Charge counter 會被充電污染,所以只傳 battery_start;
# 實際放電請看 batterystats 的 Discharge(只計算「在電池上」的時間)。
python3 "$SCRIPT_DIR/doze_summary.py" "$OUT_DIR/full.txt" \
  --checkin "$OUT_DIR/checkin.txt" \
  --pkg "$(IFS=,; echo "${PKGS[*]}")" \
  --deviceidle "$OUT_DIR/deviceidle.txt" \
  --mem "$OUT_DIR/mem_start.txt" "$OUT_DIR/mem_end.txt" \
  --battery "$OUT_DIR/battery_start.txt" \
  | tee "$OUT_DIR/summary-$TIMESTAMP.txt"

if [ "$MODE" = "unplug" ]; then
  log "完成:$OUT_DIR(deviceidle.txt 是接回 USB 之後才抓的,mState 會是 ACTIVE;請看其中的 Idling history 與 summary)"
else
  log "完成:$OUT_DIR(MODE=sim:耗電數據無效)"
fi
