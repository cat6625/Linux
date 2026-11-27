#!/usr/bin/env bash
# ==============================================================================
# 腳本名稱：dump_battery.sh
# 版本資訊：v1.9.7
# 更新日期：2026-11-27
#
# v1.9.7：
#   - 固定 Port 優先（FIXED_PORT，預設 5555；m12/m14 這類會自動關閉無線偵錯的裝置，插一次 USB 執行 adb -s <序號> tcpip 5555 後拔線）
#   - 已連線的 IP 直接略過掃描；IP 無回應（裝置關機／離開區網）略過 20,000 port 掃描（FORCE_SCAN=1 可強制）
#   - 互動模式：含 | ; & < > $ ` 或引號的指令仍交給本機 shell（管線／awk／grep 在本機執行，與 v1.9.4 相同），單純指令才用陣列傳參
# v1.9.6：
#   - 新增 AUTO_SCAN_DEFAULT_IPS（預設 1）：執行 all / a 批次抓檔前自動掃描 DEFAULT_IPS 補連裝置
#   - 延續 v1.9.5 預設 IP 清單（192.168.1.112 192.168.1.113 192.168.1.142 192.168.1.167）、命中即停掃描與防呆修正

# v1.9.5：
#   - 預設 IP 更新為 192.168.1.112 192.168.1.113 192.168.1.142 192.168.1.167，提示改為「預設 IP」不限紅米
#   - scan_open_ports 改為併發命中即停（找到可用 port 立即取消其餘任務），加快連線速度
#   - connect_by_ip 支援先試指定 ip:port，失敗後再掃描，避免白等
#   - interactive_adb_loop 一般 ADB 指令改用陣列傳遞參數，降低 eval 風險
#   - get_model 增加短暫重試與型號 fallback，避免剛連上抓空值而整台跳過
#   - 關鍵字比對改為收集所有符合裝置；batch_jobhist 拆開執行與存檔判斷；暫存檔改用安全字元命名

# v1.9.4：輸出檔名不再含 IP:port（改為 dev+serial 雜湊，KEEP_SERIAL_IN_NAME=1 可還原）；
#         新增 _props.txt（機型/Android 版本）、_battery.txt（dumpsys battery）、_meta.txt（擷取時間；含序號，請勿分享）；
#         report 一律加 --strict-mask 並帶 --props；選單 1 不再於第一個空行截斷；選單 5/6 暫存檔不再殘留

# 用法說明：
#   1. 批次抓取 batterystats 報告（預設模式）：
#        ./dump_battery.sh [all|a|<IP或Port關鍵字>]
#   2. 互動式裝置選單與單機下達 ADB 指令模式（秒開，不自動慢速掃 port）：
#        ./dump_battery.sh -i | --interactive
#   3. 批次產生 battery.py 精簡報告（--merge-wl --hide-wm --strict-mask）：
#        ./dump_battery.sh -q | --quick-report
#   4. 批次執行 jobhist.py 長任務與逾時分析（--min 10 --top 10）：
#        ./dump_battery.sh -j | --jobhist
#   5. 顯示說明：
#        ./dump_battery.sh -h | --help
#
# 環境變數（可選）：
#   DEFAULT_IPS="192.168.1.112 192.168.1.113 192.168.1.142 192.168.1.167"  # 常用裝置固定 IP（按 c 時可直接選或一鍵全掃）
#   SCAN_RANGES="5555 30000-49999"             # 裝置重連時掃描的 port 範圍
#   SCAN_TIMEOUT=0.15                          # 單一 port 連線逾時秒數
#   SCAN_WORKERS=200                           # Python 併發掃描執行緒數
#   SKIP_PORT_SCAN=0                           # 設為 1 可跳過掃描（僅嘗試原 port）
#   OUT_DIR="reports"                          # 報告輸出資料夾
# ==============================================================================

set -u

SCRIPT_VERSION="v1.9.7"
SCRIPT_DATE="2026-11-27"
OUT_DIR="${OUT_DIR:-reports}"
DEFAULT_IPS="${DEFAULT_IPS:-192.168.1.112 192.168.1.113 192.168.1.142 192.168.1.167}"
AUTO_SCAN_DEFAULT_IPS="${AUTO_SCAN_DEFAULT_IPS:-1}"
FIXED_PORT="${FIXED_PORT:-5555}"   # 優先嘗試的固定 port；設為空字串可停用
FORCE_SCAN="${FORCE_SCAN:-0}"      # 1 = IP 無回應時仍強制掃描
SCAN_RANGES="${SCAN_RANGES:-5555 30000-49999}"
SCAN_TIMEOUT="${SCAN_TIMEOUT:-0.12}"
SCAN_WORKERS="${SCAN_WORKERS:-200}"
SKIP_PORT_SCAN="${SKIP_PORT_SCAN:-0}"
TMP_BSTATS=""
CREATED_FILES=()

if command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="python3"
elif command -v python >/dev/null 2>&1; then
  PYTHON_BIN="python"
else
  PYTHON_BIN=""
fi

cleanup() {
  if [ -n "${TMP_BSTATS:-}" ] && [ -f "$TMP_BSTATS" ]; then
    rm -f "$TMP_BSTATS"
  fi
}
trap cleanup EXIT

show_help() {
  cat <<EOF
ADB Doze 測試與裝置管理工具 (${SCRIPT_VERSION} | 更新日期: ${SCRIPT_DATE})

用法：
  $0 [選項 | 目標裝置關鍵字]

參數與選項：
  -h, --help          顯示此說明訊息
  -i, --interactive   列出裝置型號並選擇單一裝置，下達 ADB 指令或使用快捷指令選單
  -q, --quick-report  批次產生 battery.py 精簡報告（--merge-wl --hide-wm --strict-mask）
  -j, --jobhist       批次執行 jobhist.py 長任務/逾時檢查（--min 10 --top 10）
  all, a              批次抓取所有正常連線裝置的 batterystats（預設會先自動掃描預設 IP）
  <關鍵字>            批次抓取符合 IP 或 Port 關鍵字的裝置

環境變數（可選）：
  DEFAULT_IPS="192.168.1.112 192.168.1.113 192.168.1.142 192.168.1.167"
  AUTO_SCAN_DEFAULT_IPS=1   # 執行 all / a 時自動掃描 DEFAULT_IPS（設為 0 可停用）
  SCAN_RANGES="5555 30000-49999"
  SCAN_TIMEOUT=0.12
  SCAN_WORKERS=200
  SKIP_PORT_SCAN=0
  FIXED_PORT=5555           # 先試固定 port，成功就不掃描
  FORCE_SCAN=0              # 1 = IP 無回應時仍強制掃描
  OUT_DIR="reports"

範例：
  $0                  互動選擇抓取 batterystats（若 offline 會快速掃 port 重連）
  $0 all              自動掃描預設 IP 後一次抓取所有連線裝置的 batterystats
  AUTO_SCAN_DEFAULT_IPS=0 $0 all   跳過預設 IP 自動掃描，直接抓目前已連線裝置
  $0 -q               批次輸出所有連線裝置的 battery.py 精簡報告
  $0 -j               批次輸出所有連線裝置的 jobhist.py 分析
  $0 -i               進入互動式裝置選擇與 ADB 指令模式
EOF
}

require_python() {
  if [ -z "$PYTHON_BIN" ]; then
    echo "❌ 錯誤：找不到 python3 或 python 執行檔，無法執行分析腳本。"
    return 1
  fi
  return 0
}

sanitize_id() {
  printf '%s' "$1" | tr -c 'A-Za-z0-9_-' '_'
}

get_model() {
  local serial="$1"
  local attempt m
  for attempt in 1 2 3; do
    m=$(adb -s "$serial" shell getprop ro.product.model 2>/dev/null | tr -d '\r' | xargs)
    if [ -n "$m" ]; then
      printf '%s\n' "$m"
      return 0
    fi
    sleep 0.25
  done
  m=$(adb -s "$serial" shell getprop ro.product.device 2>/dev/null | tr -d '\r' | xargs)
  printf '%s\n' "$m"
}

anon_id() {
  local serial="$1"
  if [ "${KEEP_SERIAL_IN_NAME:-0}" = "1" ]; then
    sanitize_id "$serial"
    return
  fi
  printf 'dev%s' "$(printf '%s' "$serial" | cksum | cut -d' ' -f1 | cut -c1-6)"
}

check_tcp_port() {
  local ip="$1"
  local port="$2"
  if command -v timeout >/dev/null 2>&1; then
    timeout "$SCAN_TIMEOUT" bash -c "exec 3<>/dev/tcp/${ip}/${port}" 2>/dev/null
    return $?
  fi
  (echo >/dev/tcp/"$ip"/"$port") >/dev/null 2>&1
}

expand_ports() {
  local token start end p
  for token in $SCAN_RANGES; do
    if [[ "$token" =~ ^([0-9]+)-([0-9]+)$ ]]; then
      start="${BASH_REMATCH[1]}"
      end="${BASH_REMATCH[2]}"
      if [ "$start" -le "$end" ]; then
        for ((p=start; p<=end; p++)); do
          echo "$p"
        done
      fi
    elif [[ "$token" =~ ^[0-9]+$ ]]; then
      echo "$token"
    fi
  done
}

scan_and_connect_ports() {
  local ip="$1"
  if [ -z "$PYTHON_BIN" ]; then
    local p
    while read -r p; do
      [ -z "$p" ] && continue
      if check_tcp_port "$ip" "$p" && adb connect "${ip}:${p}" 2>/dev/null | grep -q "connected"; then
        echo "$p"
        return 0
      fi
    done < <(expand_ports)
    return 1
  fi

  "$PYTHON_BIN" - "$ip" "$SCAN_RANGES" "$SCAN_TIMEOUT" "$SCAN_WORKERS" <<'PY'
import socket
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

ip = sys.argv[1]
ranges = sys.argv[2].split()
timeout = float(sys.argv[3])
workers = int(sys.argv[4])

ports = []
for tok in ranges:
    if "-" in tok:
        a, b = tok.split("-", 1)
        if a.isdigit() and b.isdigit():
            s, e = int(a), int(b)
            if s <= e:
                ports.extend(range(s, e + 1))
    elif tok.isdigit():
        ports.append(int(tok))

def try_port(p: int):
    try:
        with socket.create_connection((ip, p), timeout=timeout):
            res = subprocess.run(
                ["adb", "connect", f"{ip}:{p}"],
                capture_output=True,
                text=True,
                timeout=2.0,
            )
            if "connected" in (res.stdout or ""):
                return p
    except OSError:
        pass
    return None

executor = ThreadPoolExecutor(max_workers=workers)
try:
    futures = [executor.submit(try_port, p) for p in ports]
    for fut in as_completed(futures):
        found = fut.result()
        if found is not None:
            print(found)
            sys.exit(0)
finally:
    executor.shutdown(wait=False, cancel_futures=True)

sys.exit(1)
PY
}

# 該 IP 是否已有 ip:port 形式、狀態為 device 的 ADB 連線
ip_already_connected() {
  local ip="$1"
  adb devices 2>/dev/null | tr -d '\r' | awk -v ip="$ip" '$2 == "device" && index($1, ip ":") == 1 { f = 1 } END { exit !f }'
}

# IP 是否有回應：TCP 連 5555，「連上」或「被拒絕（RST）」都代表主機在線；逾時才視為無回應
host_alive() {
  local ip="$1"
  [ "$FORCE_SCAN" = "1" ] && return 0
  if [ -n "$PYTHON_BIN" ]; then
    "$PYTHON_BIN" - "$ip" <<'PY'
import errno, socket, sys
ip = sys.argv[1]
for _ in range(2):
    s = socket.socket()
    s.settimeout(1.5)
    try:
        rc = s.connect_ex((ip, 5555))
    finally:
        s.close()
    if rc in (0, errno.ECONNREFUSED):
        sys.exit(0)
sys.exit(1)
PY
    return $?
  fi
  ping -c 1 -W 1 "$ip" >/dev/null 2>&1
}

connect_by_ip() {
  local target_input="$1"
  local force_scan="${2:-0}"
  local ip="${target_input%%:*}"
  local hint_port="${target_input##*:}"
  [ "$hint_port" = "$target_input" ] && hint_port=""

  if ! [[ "$ip" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]]; then
    echo "❌ IP 格式不正確：$ip"
    return 1
  fi

  if [ -n "$hint_port" ]; then
    adb disconnect "${ip}:${hint_port}" >/dev/null 2>&1
    if check_tcp_port "$ip" "$hint_port"; then
      if adb connect "${ip}:${hint_port}" 2>/dev/null | grep -q "connected"; then
        echo "✅ 已直接連線至 ${ip}:${hint_port}"
        return 0
      fi
    fi
    echo "⚠️  指定埠 ${ip}:${hint_port} 無法連線，改嘗試掃描 ${ip}..."
  fi

  if [ -z "$hint_port" ] && ip_already_connected "$ip"; then
    echo "✅ ${ip} 已有連線，略過掃描"
    return 0
  fi

  if [ -n "$FIXED_PORT" ] && [ "$FIXED_PORT" != "$hint_port" ]; then
    if check_tcp_port "$ip" "$FIXED_PORT" && adb connect "${ip}:${FIXED_PORT}" 2>/dev/null | grep -q "connected"; then
      echo "✅ 已連線至固定 port ${ip}:${FIXED_PORT}"
      return 0
    fi
  fi

  if ! host_alive "$ip"; then
    echo "❌ ${ip} 無回應（裝置未開機、離開區網或 Wi‑Fi 休眠），略過 port 掃描；FORCE_SCAN=1 可強制掃描"
    return 1
  fi

  if [ "$SKIP_PORT_SCAN" = "1" ] && [ "$force_scan" != "1" ]; then
    echo "⏭️  已設定 SKIP_PORT_SCAN=1，略過 port 掃描。"
    return 1
  fi

  local found_port=""
  echo "🔍 正在快速掃描 ${ip} 的 ADB port (${SCAN_RANGES})..."
  found_port=$(scan_and_connect_ports "$ip" 2>/dev/null | head -n 1 | xargs)

  if [ -n "$found_port" ]; then
    echo "✅ 掃描成功！已連線至 ${ip}:${found_port}"
    return 0
  else
    echo "❌ 無法自動連上 ${ip}（請確認裝置已開啟「無線偵錯」，且螢幕處於喚醒狀態）"
    return 1
  fi
}

scan_default_ips_batch() {
  local def_arr=() dip
  read -ra def_arr <<< "$DEFAULT_IPS"
  [ ${#def_arr[@]} -eq 0 ] && return 0

  echo "🔍 批次前自動掃描預設 IP（${DEFAULT_IPS}）..."
  for dip in "${def_arr[@]}"; do
    echo "------------------------------------------"
    connect_by_ip "$dip" 1
  done
  echo ""
}

prompt_manual_ip_connect() {
  local def_arr=()
  read -ra def_arr <<< "$DEFAULT_IPS"

  echo "------------------------------------------"
  if [ ${#def_arr[@]} -gt 0 ]; then
    echo "預設裝置 IP 清單："
    local idx
    for idx in "${!def_arr[@]}"; do
      echo "  $((idx+1))) ${def_arr[$idx]}"
    done
    echo "  a) 全部掃描並重連上述預設 IP（直接按 Enter 預設執行此項）"
    echo "  或直接輸入其他 IP / IP:Port（輸入 q 取消）"
    local choice
    read -rp "請選擇或輸入 IP: " choice
    choice=$(echo "$choice" | xargs)

    if [[ "$choice" == "q" || "$choice" == "Q" ]]; then
      echo "已取消。"
      return 1
    elif [[ -z "$choice" || "$choice" == "a" || "$choice" == "A" ]]; then
      local dip
      for dip in "${def_arr[@]}"; do
        echo "------------------------------------------"
        connect_by_ip "$dip" 1
      done
      return 0
    elif [[ "$choice" =~ ^[0-9]+$ ]] && [ "$choice" -ge 1 ] && [ "$choice" -le ${#def_arr[@]} ]; then
      connect_by_ip "${def_arr[$((choice-1))]}" 1
      return $?
    else
      connect_by_ip "$choice" 1
      return $?
    fi
  else
    local manual_ip
    read -rp "請輸入裝置區網 IP（例如 192.168.1.112，直接按 Enter 取消）: " manual_ip
    manual_ip=$(echo "$manual_ip" | xargs)
    if [ -z "$manual_ip" ]; then
      echo "已取消。"
      return 1
    fi
    connect_by_ip "$manual_ip" 1
  fi
}

recover_offline_devices() {
  local offline_list=()
  mapfile -t offline_list < <(adb devices | awk '$2 == "offline" {print $1}')

  if [ ${#offline_list[@]} -eq 0 ]; then
    echo "ℹ️  目前清單中沒有 offline 裝置（若裝置剛重開無線偵錯，請按 c 掃描預設 IP）。"
    return 0
  fi

  echo "⚠️  偵測到 ${#offline_list[@]} 台裝置處於 offline 狀態，開始嘗試重連..."
  local dev
  for dev in "${offline_list[@]}"; do
    echo "------------------------------------------"
    echo "處理 offline 裝置：$dev"
    connect_by_ip "$dev" 0
  done
  echo ""
}

refresh_online_devices() {
  mapfile -t DEVICES < <(adb devices | awk '$2 == "device" {print $1}')
  mapfile -t OFFLINE_DEVICES < <(adb devices | awk '$2 == "offline" {print $1}')
}

print_device_table() {
  local i model
  printf "  %-4s %-22s %-24s\n" "編號" "ADB 位址/序號" "裝置型號"
  echo "  --------------------------------------------------------"
  for i in "${!DEVICES[@]}"; do
    model=$(get_model "${DEVICES[$i]}")
    printf "  %-4d %-22s %-24s\n" "$((i+1))" "${DEVICES[$i]}" "${model:-無回應}"
  done
  if [ ${#OFFLINE_DEVICES[@]} -gt 0 ]; then
    echo "  --------------------------------------------------------"
    echo "  ⚠️  目前 offline 裝置：${OFFLINE_DEVICES[*]}（按 r 可嘗試重連）"
  fi
}

prepare_batch_devices() {
  mkdir -p "$OUT_DIR"
  recover_offline_devices
  refresh_online_devices

  if [ ${#DEVICES[@]} -eq 0 ]; then
    echo "錯誤：未偵測到任何正常連線 (device) 的 ADB 裝置。"
    return 1
  fi
  return 0
}

batch_quick_report() {
  require_python || exit 1
  prepare_batch_devices || exit 1
  local ts model safe_model safe_id out_file dev
  ts=$(date +%Y%m%d_%H%M%S)

  for dev in "${DEVICES[@]}"; do
    model=$(get_model "$dev")
    if [ -z "$model" ]; then
      echo "=========================================="
      echo "❌ 錯誤：裝置 ($dev) 回應逾時或已斷線，跳過。"
      continue
    fi
    safe_model=$(sanitize_id "$model")
    safe_id=$(anon_id "$dev")
    out_file="${OUT_DIR}/${safe_model}_${safe_id}_${ts}_quick.txt"

    echo "=========================================="
    echo "📱 裝置：[$model] ($dev)"
    if ANDROID_SERIAL="$dev" "$PYTHON_BIN" battery.py --merge-wl --hide-wm --strict-mask > "$out_file"; then
      echo "✅ 已產生：$out_file"
    else
      echo "❌ 產生失敗：$out_file"
      rm -f "$out_file"
    fi
  done
}

batch_jobhist() {
  require_python || exit 1
  prepare_batch_devices || exit 1
  local ts model safe_model safe_id out_file dev
  ts=$(date +%Y%m%d_%H%M%S)

  for dev in "${DEVICES[@]}"; do
    model=$(get_model "$dev")
    model="${model:-未知型號}"
    safe_model=$(sanitize_id "$model")
    safe_id=$(anon_id "$dev")
    out_file="${OUT_DIR}/${safe_model}_${safe_id}_${ts}_jobhist.txt"

    echo "=========================================="
    echo "📱 裝置：[$model] ($dev)"
    if ANDROID_SERIAL="$dev" "$PYTHON_BIN" jobhist.py --min 10 --top 10 > "$out_file"; then
      cat "$out_file"
      echo "✅ 已存檔：$out_file"
    else
      echo "❌ 執行失敗：$out_file"
      rm -f "$out_file"
    fi
  done
}

fetch_batterystats_cache() {
  local target_dev="$1"
  local safe_id
  safe_id=$(sanitize_id "$target_dev")
  if [ -n "${TMP_BSTATS:-}" ] && [ -f "$TMP_BSTATS" ]; then
    rm -f "$TMP_BSTATS"
  fi
  TMP_BSTATS="/tmp/bstats_${safe_id}_$$.txt"

  echo "正在擷取 batterystats 資料..."
  adb -s "$target_dev" shell dumpsys batterystats 2>/dev/null | tr -d '\r' > "$TMP_BSTATS"
  if [ ! -s "$TMP_BSTATS" ]; then
    echo "❌ 無法取得 batterystats 輸出。"
    rm -f "$TMP_BSTATS"
    TMP_BSTATS=""
    return 1
  fi
  return 0
}

show_wakelock_ranking() {
  local file="$1"
  require_python || return 1
  if [ ! -f "battery.py" ]; then
    echo "❌ 錯誤：目前目錄找不到 battery.py。"
    return 1
  fi

  echo "--- 1. WakeLock 總覽與排行 (Top 20) ---"
  local output
  if ! output=$("$PYTHON_BIN" battery.py -f "$file" -n 20 --merge-wl 2>&1); then
    echo "❌ battery.py 執行失敗："
    echo "$output"
    return 1
  fi

  echo "$output" | awk '
    /^=== 電池與統計週期資訊 ===/ { show=1 }
    /^=== 最耗電 UID \/ 系統項目/ { exit }
    show { print }
  '
  return 0
}

show_alarm_ranking() {
  local file="$1"
  echo "--- 2. Wakeup Alarm 喚醒次數排行 (Top 20) ---"
  awk '
  BEGIN { cur_uid = "unknown"; cur_apk = "" }
  /^[[:space:]]*(UID|Uid)[[:space:]]+/ {
    line = $0
    sub(/^[[:space:]]*(UID|Uid)[[:space:]]+/, "", line)
    sub(/:.*$/, "", line)
    gsub(/^[[:space:]]+|[[:space:]]+$/, "", line)
    if (line != "") {
      cur_uid = line
      cur_apk = ""
    }
  }
  /^[[:space:]]*Apk[[:space:]]+/ {
    line = $0
    sub(/^[[:space:]]*Apk[[:space:]]+/, "", line)
    sub(/:[[:space:]]*$/, "", line)
    gsub(/^[[:space:]]+|[[:space:]]+$/, "", line)
    if (line != "") cur_apk = line
  }
  /Wakeup alarm/ {
    src = (cur_apk != "" ? cur_apk : cur_uid)
    cnt = 0
    if (match($0, /[0-9]+ times/)) {
      s = substr($0, RSTART, RLENGTH)
      split(s, a, " ")
      cnt = a[1] + 0
    }
    if (cnt > 0) {
      alarm_cnt[src] += cnt
    }
  }
  END {
    n = 0
    for (k in alarm_cnt) {
      n++
      keys[n] = k
    }
    for (i = 1; i <= n; i++) {
      for (j = i + 1; j <= n; j++) {
        if (alarm_cnt[keys[j]] > alarm_cnt[keys[i]]) {
          tmp = keys[i]
          keys[i] = keys[j]
          keys[j] = tmp
        }
      }
    }
    limit = (n < 20 ? n : 20)
    printf "%-6s %-10s %s\n", "排名", "喚醒次數", "Package / 來源"
    for (i = 1; i <= limit; i++) {
      k = keys[i]
      printf "%-6d %-10d %s\n", i, alarm_cnt[k], k
    }
  }
  ' "$file"
}

run_jobhist_check() {
  local target_dev="$1"
  require_python || return 1
  echo "▶ 執行：jobhist.py --min 10 --top 10"
  ANDROID_SERIAL="$target_dev" "$PYTHON_BIN" jobhist.py --min 10 --top 10
  echo "(exit code: $?)"
}

confirm_action() {
  local prompt_msg="$1"
  local ans
  echo "$prompt_msg"
  read -rp "確定要執行嗎？輸入 y 確認，其他鍵取消: " ans
  ans=$(echo "$ans" | xargs)
  [[ "$ans" == "y" || "$ans" == "Y" ]]
}

show_quick_menu() {
  echo "  ---------------- 快捷指令選單（查看優先）----------------"
  echo "   [唯讀查看]"
  echo "    1) 快速檢查 Statistics since last charge 摘要"
  echo "    2) 查看電池即時狀態 (dumpsys battery)"
  echo "    3) 查看 Doze 狀態與歷史 (dumpsys deviceidle)"
  echo "    4) 查看 Total PSS 記憶體排行前 25 名 (meminfo)"
  echo "    5) 查看 WakeLock 總覽與排行 (Top 20)"
  echo "    6) 查看 Wakeup Alarm 喚醒次數排行 (Top 20)"
  echo "    7) 分析 JobScheduler 長任務/逾時 (jobhist.py --min 10 --top 10)"
  echo "   [螢幕與狀態變更 - 需防呆]"
  echo "    8) 關閉/喚醒螢幕 (input keyevent 26)"
  echo "    9) 模擬拔線 (dumpsys battery unplug)"
  echo "   10) 還原電池狀態 (dumpsys battery reset)"
  echo "   11) 強制進入 Doze (dumpsys deviceidle force-idle)"
  echo "   12) 解除強制 Doze (dumpsys deviceidle unforce)"
  echo "   [資料重置 - 需防呆]"
  echo "   13) 重置電池統計 (dumpsys batterystats --reset)"
  echo "  ----------------------------------------------------------"
}

run_quick_command() {
  local target_dev="$1"
  local choice="$2"
  case "$choice" in
    1)
      echo "▶ 執行：Statistics since last charge 摘要"
      adb -s "$target_dev" shell "dumpsys batterystats | tr -d '\r' | awk '/^Statistics since last charge:/{f=1; print; next} f{ if (/^[^[:space:]]/) exit; print }'" 2>/dev/null
      echo "(exit code: ${PIPESTATUS[0]})"
      ;;
    2)
      echo "▶ 執行：dumpsys battery"
      adb -s "$target_dev" shell dumpsys battery
      echo "(exit code: $?)"
      ;;
    3)
      echo "▶ 執行：dumpsys deviceidle"
      adb -s "$target_dev" shell dumpsys deviceidle
      echo "(exit code: $?)"
      ;;
    4)
      echo "▶ 執行：dumpsys meminfo Total PSS 前 25 名"
      adb -s "$target_dev" shell dumpsys meminfo | tr -d '\r' | sed -n '/Total PSS by process:/,$p' | grep -E "^ +[0-9,]+K: .*\(pid [0-9]+\)" | head -n 25
      echo "(exit code: ${PIPESTATUS[0]})"
      ;;
    5)
      echo "▶ 執行：WakeLock 排行"
      if fetch_batterystats_cache "$target_dev"; then
        show_wakelock_ranking "$TMP_BSTATS"
        echo "(exit code: $?)"
      else
        echo "(exit code: 1)"
      fi
      ;;
    6)
      echo "▶ 執行：Alarm 排行"
      if fetch_batterystats_cache "$target_dev"; then
        show_alarm_ranking "$TMP_BSTATS"
        echo "(exit code: $?)"
      else
        echo "(exit code: 1)"
      fi
      ;;
    7)
      run_jobhist_check "$target_dev"
      ;;
    8)
      if confirm_action "⚠️  即將對 [$target_dev] 送出電源鍵事件（關閉或喚醒螢幕）。"; then
        echo "▶ 執行：input keyevent 26"
        adb -s "$target_dev" shell input keyevent 26
        echo "(exit code: $?)"
      else
        echo "已取消。"
      fi
      ;;
    9)
      if confirm_action "⚠️  即將對 [$target_dev] 模擬拔線（dumpsys battery unplug）。"; then
        echo "▶ 執行：dumpsys battery unplug"
        adb -s "$target_dev" shell dumpsys battery unplug
        echo "(exit code: $?)"
      else
        echo "已取消。"
      fi
      ;;
    10)
      if confirm_action "⚠️  即將還原 [$target_dev] 的電池模擬狀態（dumpsys battery reset）。"; then
        echo "▶ 執行：dumpsys battery reset"
        adb -s "$target_dev" shell dumpsys battery reset
        echo "(exit code: $?)"
      else
        echo "已取消。"
      fi
      ;;
    11)
      if confirm_action "⚠️  即將強制 [$target_dev] 進入 Doze（dumpsys deviceidle force-idle）。"; then
        echo "▶ 執行：dumpsys deviceidle force-idle"
        adb -s "$target_dev" shell dumpsys deviceidle force-idle
        echo "(exit code: $?)"
      else
        echo "已取消。"
      fi
      ;;
    12)
      if confirm_action "⚠️  即將解除 [$target_dev] 的強制 Doze（dumpsys deviceidle unforce）。"; then
        echo "▶ 執行：dumpsys deviceidle unforce"
        adb -s "$target_dev" shell dumpsys deviceidle unforce
        echo "(exit code: $?)"
      else
        echo "已取消。"
      fi
      ;;
    13)
      if confirm_action "⚠️  即將清除 [$target_dev] 目前累積的 batterystats 統計資料（--reset）。"; then
        echo "▶ 執行：dumpsys batterystats --reset"
        adb -s "$target_dev" shell dumpsys batterystats --reset
        rm -f "${TMP_BSTATS:-}"
        TMP_BSTATS=""
        echo "(exit code: $?)"
      else
        echo "已取消重置。"
      fi
      ;;
    *)
      return 1
      ;;
  esac
  return 0
}

interactive_adb_loop() {
  refresh_online_devices

  while true; do
    if [ ${#DEVICES[@]} -eq 0 ]; then
      echo "=========================================="
      echo "❌ 目前沒有任何狀態為 device 的 ADB 裝置。"
      if [ ${#OFFLINE_DEVICES[@]} -gt 0 ]; then
        echo "⚠️  偵測到 offline 裝置：${OFFLINE_DEVICES[*]}"
      fi
      echo "  c) 掃描預設 IP (${DEFAULT_IPS}) 或手動輸入 IP/IP:Port 連線"
      echo "  r) 重新掃描並嘗試重連 offline 裝置"
      echo "  q) 離開程式"
      read -rp "請輸入選項 (c/r/q 或直接按 Enter 重新整理): " retry_ans
      if [[ "$retry_ans" == "q" || "$retry_ans" == "Q" ]]; then
        exit 0
      elif [[ "$retry_ans" == "c" || "$retry_ans" == "C" ]]; then
        prompt_manual_ip_connect
      elif [[ "$retry_ans" == "r" || "$retry_ans" == "R" ]]; then
        recover_offline_devices
      fi
      refresh_online_devices
      continue
    fi

    echo "=========================================="
    echo "請選擇要下達 ADB 指令的裝置（${SCRIPT_VERSION}）："
    print_device_table
    echo "  c) 掃描預設 IP (${DEFAULT_IPS}) 或手動輸入 IP/IP:Port 連線"
    echo "  r) 重新掃描並嘗試重連 offline 裝置"
    echo "  q) 離開程式"
    echo "------------------------------------------"

    local dev_choice=""
    while true; do
      read -rp "請輸入選項: " dev_choice
      if [[ -z "$dev_choice" ]]; then
        continue
      fi
      break
    done

    if [[ "$dev_choice" == "q" || "$dev_choice" == "Q" ]]; then
      echo "已離開。"
      exit 0
    elif [[ "$dev_choice" == "c" || "$dev_choice" == "C" ]]; then
      prompt_manual_ip_connect
      refresh_online_devices
      continue
    elif [[ "$dev_choice" == "r" || "$dev_choice" == "R" ]]; then
      recover_offline_devices
      refresh_online_devices
      continue
    elif ! [[ "$dev_choice" =~ ^[0-9]+$ ]] || [ "$dev_choice" -lt 1 ] || [ "$dev_choice" -gt ${#DEVICES[@]} ]; then
      echo "❌ 無效的選項，請重新輸入。"
      continue
    fi

    local target_dev="${DEVICES[$((dev_choice-1))]}"
    local target_model
    target_model=$(get_model "$target_dev")
    target_model="${target_model:-未知型號}"

    echo ""
    echo "已選定裝置：[$target_model] ($target_dev)"
    show_quick_menu
    echo "操作說明：輸入 1-13 執行快捷指令、輸入 m 重新顯示快捷選單、直接輸入 adb 參數執行、輸入 b 返回裝置選單、輸入 q 離開。"

    local cmd_input
    while true; do
      read -rp "adb ($target_model)> " cmd_input

      if [[ -z "$cmd_input" ]]; then
        continue
      elif [[ "$cmd_input" == "m" || "$cmd_input" == "M" || "$cmd_input" == "menu" ]]; then
        show_quick_menu
        continue
      elif [[ "$cmd_input" == "b" || "$cmd_input" == "B" || "$cmd_input" == "back" ]]; then
        echo "↩️  返回裝置選單..."
        echo ""
        refresh_online_devices
        break
      elif [[ "$cmd_input" == "q" || "$cmd_input" == "Q" || "$cmd_input" == "exit" ]]; then
        echo "已離開。"
        exit 0
      elif [[ "$cmd_input" =~ ^([1-9]|1[0-3])$ ]]; then
        run_quick_command "$target_dev" "$cmd_input"
        continue
      fi

      cmd_input="${cmd_input#adb }"
      case "$cmd_input" in
        *[\|\;\&\<\>\$\`\"\']*)
          # 含管線／重導向／引號：交給本機 shell 解析（grep、awk、head 在本機執行；只在你自己的終端使用）
          eval "adb -s \"$target_dev\" $cmd_input"
          ;;
        *)
          local adb_args=()
          read -ra adb_args <<< "$cmd_input"
          adb -s "$target_dev" "${adb_args[@]}"
          ;;
      esac
      echo "(exit code: $?)"
    done
  done
}

dump_device() {
  local SERIAL="$1"
  local TS="$2"
  local MODEL SAFE_MODEL SAFE_ID PREFIX T0 p

  MODEL=$(get_model "$SERIAL")
  if [ -z "$MODEL" ]; then
    echo "=========================================="
    echo "❌ 錯誤：裝置 ($SERIAL) 回應逾時或已斷線，跳過此裝置。"
    return 1
  fi

  SAFE_MODEL=$(sanitize_id "$MODEL")
  SAFE_ID=$(anon_id "$SERIAL")
  PREFIX="${OUT_DIR}/${SAFE_MODEL}_${SAFE_ID}_${TS}"

  echo "=========================================="
  echo "目標裝置：[${MODEL}] (${SERIAL})"
  T0=$(date '+%Y-%m-%d %H:%M:%S')
  echo "正在擷取 batterystats..."
  adb -s "$SERIAL" shell dumpsys batterystats > "${PREFIX}_raw.txt" 2>/dev/null

  if [ ! -s "${PREFIX}_raw.txt" ]; then
    echo "❌ 錯誤：[${MODEL}] 擷取失敗或中途斷線（檔案為空），已自動清理。"
    rm -f "${PREFIX}_raw.txt"
    return 1
  fi
  CREATED_FILES+=("${PREFIX}_raw.txt")

  : > "${PREFIX}_props.txt"
  for p in ro.product.brand ro.product.model ro.product.device ro.build.version.release ro.build.version.sdk ro.build.display.id; do
    echo "${p}=$(adb -s "$SERIAL" shell getprop "$p" 2>/dev/null | tr -d '\r')" >> "${PREFIX}_props.txt"
  done
  CREATED_FILES+=("${PREFIX}_props.txt")
  if adb -s "$SERIAL" shell dumpsys battery 2>/dev/null | tr -d '\r' > "${PREFIX}_battery.txt" && [ -s "${PREFIX}_battery.txt" ]; then
    CREATED_FILES+=("${PREFIX}_battery.txt")
  else
    rm -f "${PREFIX}_battery.txt"
  fi
  { echo "serial=$SERIAL"; echo "model=$MODEL"; echo "batterystats_start=$T0"; echo "batterystats_end=$(date '+%Y-%m-%d %H:%M:%S')"; } > "${PREFIX}_meta.txt"

  echo "正在同步擷取 jobscheduler 與 power 狀態..."
  if adb -s "$SERIAL" shell dumpsys jobscheduler > "${PREFIX}_js.txt" 2>/dev/null && [ -s "${PREFIX}_js.txt" ]; then
    CREATED_FILES+=("${PREFIX}_js.txt")
    if [ -n "$PYTHON_BIN" ] && [ -f "jobhist.py" ]; then
      if "$PYTHON_BIN" jobhist.py "${PREFIX}_js.txt" --min 10 --top 15 > "${PREFIX}_jobhist.txt" 2>/dev/null && [ -s "${PREFIX}_jobhist.txt" ]; then
        CREATED_FILES+=("${PREFIX}_jobhist.txt")
      else
        rm -f "${PREFIX}_jobhist.txt"
      fi
    fi
  else
    rm -f "${PREFIX}_js.txt"
  fi

  if adb -s "$SERIAL" shell dumpsys power > "${PREFIX}_power.txt" 2>/dev/null && [ -s "${PREFIX}_power.txt" ]; then
    CREATED_FILES+=("${PREFIX}_power.txt")
  else
    rm -f "${PREFIX}_power.txt"
  fi

  echo "正在產生精華檔與分析報告..."
  if [ -n "$PYTHON_BIN" ] && [ -f "battery_extract.py" ]; then
    if "$PYTHON_BIN" battery_extract.py "${PREFIX}_raw.txt" -o "${PREFIX}_extract.txt" && [ -s "${PREFIX}_extract.txt" ]; then
      CREATED_FILES+=("${PREFIX}_extract.txt")
    else
      rm -f "${PREFIX}_extract.txt"
    fi
  fi

  if [ -n "$PYTHON_BIN" ] && [ -f "battery.py" ]; then
    if "$PYTHON_BIN" battery.py -f "${PREFIX}_raw.txt" -n 20 -m --merge-wl --strict-mask --props "${PREFIX}_props.txt" > "${PREFIX}_report.txt" && [ -s "${PREFIX}_report.txt" ]; then
      CREATED_FILES+=("${PREFIX}_report.txt")
    else
      rm -f "${PREFIX}_report.txt"
    fi
  fi

  echo "✅ 完成輸出：${PREFIX}_*"
}

case "${1:-}" in
  -h|--help)
    show_help
    exit 0
    ;;
  -i|--interactive)
    interactive_adb_loop
    exit 0
    ;;
  -q|--quick-report)
    batch_quick_report
    exit 0
    ;;
  -j|--jobhist)
    batch_jobhist
    exit 0
    ;;
esac

mkdir -p "$OUT_DIR"

if [[ "${1:-}" == "a" || "${1:-}" == "A" || "${1:-}" == "all" ]]; then
  if [ "${AUTO_SCAN_DEFAULT_IPS:-1}" = "1" ]; then
    scan_default_ips_batch
  fi
fi

recover_offline_devices
refresh_online_devices

if [ ${#DEVICES[@]} -eq 0 ]; then
  echo "錯誤：未偵測到任何正常連線 (device) 的 ADB 裝置。"
  exit 1
fi

TARGETS=()
if [ -n "${1:-}" ]; then
  if [[ "$1" == "a" || "$1" == "A" || "$1" == "all" ]]; then
    TARGETS=("${DEVICES[@]}")
  else
    for dev in "${DEVICES[@]}"; do
      if [[ "$dev" == *"$1"* ]]; then
        TARGETS+=("$dev")
      fi
    done
    if [ ${#TARGETS[@]} -eq 0 ]; then
      echo "錯誤：找不到包含 '$1' 的正常連線裝置。"
      exit 1
    fi
  fi
elif [ ${#DEVICES[@]} -eq 1 ]; then
  TARGETS=("${DEVICES[0]}")
else
  while true; do
    echo "偵測到多台正常連線裝置，請選擇要擷取的目標（${SCRIPT_VERSION}）："
    print_device_table
    echo "  a) 全部抓取 (共 ${#DEVICES[@]} 台裝置)"
    echo "  c) 掃描預設 IP (${DEFAULT_IPS}) 或手動輸入 IP/IP:Port 連線"
    echo "  q) 離開程式"

    while true; do
      read -rp "請輸入編號 (1-${#DEVICES[@]})、a、c 或 q: " CHOICE
      [[ -z "$CHOICE" ]] && continue
      break
    done

    if [[ "$CHOICE" == "q" || "$CHOICE" == "Q" ]]; then
      echo "已離開。"
      exit 0
    elif [[ "$CHOICE" == "c" || "$CHOICE" == "C" ]]; then
      prompt_manual_ip_connect
      refresh_online_devices
      if [ ${#DEVICES[@]} -eq 0 ]; then
        echo "錯誤：目前沒有任何正常連線 (device) 的 ADB 裝置。"
        exit 1
      fi
      continue
    elif [[ "$CHOICE" == "a" || "$CHOICE" == "A" ]]; then
      TARGETS=("${DEVICES[@]}")
      break
    elif [[ "$CHOICE" =~ ^[0-9]+$ ]] && [ "$CHOICE" -ge 1 ] && [ "$CHOICE" -le ${#DEVICES[@]} ]; then
      TARGETS=("${DEVICES[$((CHOICE-1))]}")
      break
    else
      echo "錯誤：無效的選項，請重新輸入。"
    fi
  done
fi

BATCH_TS=$(date +%Y%m%d_%H%M%S)
for dev in "${TARGETS[@]}"; do
  dump_device "$dev" "$BATCH_TS"
done

echo "=========================================="
echo "作業結束！本次成功產出的檔案："
if [ ${#CREATED_FILES[@]} -gt 0 ]; then
  ls -lh "${CREATED_FILES[@]}"
else
  echo "(無產出檔案)"
fi
