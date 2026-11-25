#!/usr/bin/env bash
# ==============================================================================
# 腳本名稱：dump_battery.sh
# 版本資訊：v1.3.0
# 更新日期：2026-11-25
#
# 用法說明：
#   1. 批次抓取 batterystats 報告（預設模式）：
#        ./dump_battery.sh [all|a|<IP或Port關鍵字>]
#   2. 互動式裝置選單與單機下達 ADB 指令模式（含快捷指令選單）：
#        ./dump_battery.sh -i | --interactive
#   3. 顯示說明：
#        ./dump_battery.sh -h | --help
#
# 環境變數（可選）：
#   SCAN_RANGES="5555 30000-49999"   # offline 裝置重連時掃描的 port 範圍
#   SCAN_TIMEOUT=0.2                # 單一 port 連線逾時秒數
#   OUT_DIR="reports"               # 報告輸出資料夾
# ==============================================================================

set -u

SCRIPT_VERSION="v1.3.0"
SCRIPT_DATE="2026-11-25"
OUT_DIR="${OUT_DIR:-reports}"
SCAN_RANGES="${SCAN_RANGES:-5555 30000-49999}"
SCAN_TIMEOUT="${SCAN_TIMEOUT:-0.2}"

show_help() {
  cat <<EOF
ADB Doze 測試與裝置管理工具 (${SCRIPT_VERSION} | 更新日期: ${SCRIPT_DATE})

用法：
  $0 [選項 | 目標裝置關鍵字]

參數與選項：
  -h, --help          顯示此說明訊息
  -i, --interactive   列出裝置型號並選擇單一裝置，下達 ADB 指令或使用快捷指令選單
  all, a              批次抓取所有正常連線裝置的 batterystats
  <關鍵字>            批次抓取符合 IP 或 Port 關鍵字的單一裝置

範例：
  $0                  互動選擇抓取 batterystats（若 offline 會嘗試掃 port 重連）
  $0 all              一次抓取所有連線裝置的 batterystats
  $0 192.168.1.112    抓取包含 192.168.1.112 的裝置
  $0 -i               進入互動式裝置選擇與 ADB 指令模式
EOF
}

get_model() {
  local serial="$1"
  adb -s "$serial" shell getprop ro.product.model 2>/dev/null | tr -d '\r' | xargs
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

recover_offline_devices() {
  local offline_list=()
  mapfile -t offline_list < <(adb devices | awk '$2 == "offline" {print $1}')

  if [ ${#offline_list[@]} -eq 0 ]; then
    return 0
  fi

  echo "⚠️  偵測到 ${#offline_list[@]} 台裝置處於 offline 狀態，開始嘗試重連..."
  local dev ip old_port found_port p

  for dev in "${offline_list[@]}"; do
    ip="${dev%%:*}"
    old_port="${dev##*:}"
    [ "$old_port" = "$dev" ] && old_port=""

    echo "------------------------------------------"
    echo "處理 offline 裝置：$dev (IP: $ip)"
    adb disconnect "$dev" >/dev/null 2>&1

    if [ -n "$old_port" ] && check_tcp_port "$ip" "$old_port"; then
      if adb connect "${ip}:${old_port}" 2>/dev/null | grep -q "connected"; then
        echo "✅ 原 port ${old_port} 可連通，已重新連線：${ip}:${old_port}"
        continue
      fi
    fi

    found_port=""
    echo "🔍 正在掃描 ${ip} 的 ADB port (${SCAN_RANGES})..."
    while read -r p; do
      if check_tcp_port "$ip" "$p"; then
        if adb connect "${ip}:${p}" 2>/dev/null | grep -q "connected"; then
          found_port="$p"
          break
        fi
      fi
    done < <(expand_ports)

    if [ -n "$found_port" ]; then
      echo "✅ 掃描成功！已連線至 ${ip}:${found_port}"
    else
      echo "❌ 無法自動連上 ${ip}（請確認手機無線偵錯/TCPADB 已開啟，或螢幕已喚醒）"
    fi
  done
  echo ""
}

refresh_online_devices() {
  mapfile -t DEVICES < <(adb devices | awk '$2 == "device" {print $1}')
}

print_device_table() {
  local i model
  printf "  %-4s %-22s %-24s\n" "編號" "ADB 位址/序號" "手機型號"
  echo "  --------------------------------------------------------"
  for i in "${!DEVICES[@]}"; do
    model=$(get_model "${DEVICES[$i]}")
    printf "  %-4d %-22s %-24s\n" "$((i+1))" "${DEVICES[$i]}" "${model:-無回應}"
  done
}

# 顯示互動式快捷指令選單
show_quick_menu() {
  echo "  ---------------- 快捷指令選單 ----------------"
  echo "  1) 查看 Total PSS 記憶體排行前 25 名 (meminfo)"
  echo "  2) 重置電池統計 (dumpsys batterystats --reset)"
  echo "  3) 查看電池即時狀態 (dumpsys battery)"
  echo "  4) 模擬拔線 (dumpsys battery unplug)"
  echo "  5) 還原電池狀態 (dumpsys battery reset)"
  echo "  6) 查看 Doze 狀態與歷史 (dumpsys deviceidle)"
  echo "  7) 強制進入 Doze (dumpsys deviceidle force-idle)"
  echo "  8) 解除強制 Doze (dumpsys deviceidle unforce)"
  echo "  9) 關閉/喚醒螢幕 (input keyevent 26)"
  echo "  ----------------------------------------------"
}

# 執行快捷指令編號
run_quick_command() {
  local target_dev="$1"
  local choice="$2"
  case "$choice" in
    1)
      echo "▶ 執行：dumpsys meminfo Total PSS 前 25 名"
      adb -s "$target_dev" shell dumpsys meminfo | tr -d '\r' | sed -n '/Total PSS by process:/,$p' | grep -E "^ +[0-9,]+K: .*\(pid [0-9]+\)" | head -n 25
      echo "(exit code: ${PIPESTATUS[0]})"
      ;;
    2)
      echo "▶ 執行：dumpsys batterystats --reset"
      adb -s "$target_dev" shell dumpsys batterystats --reset
      echo "(exit code: $?)"
      ;;
    3)
      echo "▶ 執行：dumpsys battery"
      adb -s "$target_dev" shell dumpsys battery
      echo "(exit code: $?)"
      ;;
    4)
      echo "▶ 執行：dumpsys battery unplug"
      adb -s "$target_dev" shell dumpsys battery unplug
      echo "(exit code: $?)"
      ;;
    5)
      echo "▶ 執行：dumpsys battery reset"
      adb -s "$target_dev" shell dumpsys battery reset
      echo "(exit code: $?)"
      ;;
    6)
      echo "▶ 執行：dumpsys deviceidle"
      adb -s "$target_dev" shell dumpsys deviceidle
      echo "(exit code: $?)"
      ;;
    7)
      echo "▶ 執行：dumpsys deviceidle force-idle"
      adb -s "$target_dev" shell dumpsys deviceidle force-idle
      echo "(exit code: $?)"
      ;;
    8)
      echo "▶ 執行：dumpsys deviceidle unforce"
      adb -s "$target_dev" shell dumpsys deviceidle unforce
      echo "(exit code: $?)"
      ;;
    9)
      echo "▶ 執行：input keyevent 26"
      adb -s "$target_dev" shell input keyevent 26
      echo "(exit code: $?)"
      ;;
    *)
      return 1
      ;;
  esac
  return 0
}

# 互動式模式：選裝置 -> 快捷指令或自訂 ADB 指令 -> 返回選單
interactive_adb_loop() {
  while true; do
    recover_offline_devices
    refresh_online_devices

    if [ ${#DEVICES[@]} -eq 0 ]; then
      echo "❌ 目前沒有任何狀態為 device 的 ADB 裝置。"
      read -rp "按 Enter 重新掃描，或輸入 q 離開: " retry_ans
      [[ "$retry_ans" == "q" || "$retry_ans" == "Q" ]] && exit 0
      continue
    fi

    echo "=========================================="
    echo "請選擇要下達 ADB 指令的裝置（${SCRIPT_VERSION}）："
    print_device_table
    echo "  r) 重新掃描 offline/連線裝置"
    echo "  q) 離開程式"
    echo "------------------------------------------"
    read -rp "請輸入選項: " dev_choice

    if [[ "$dev_choice" == "q" || "$dev_choice" == "Q" ]]; then
      echo "已離開。"
      exit 0
    elif [[ "$dev_choice" == "r" || "$dev_choice" == "R" ]]; then
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
    echo "操作說明：輸入 1-9 執行快捷指令、輸入 m 重新顯示快捷選單、直接輸入 adb 參數執行、輸入 b 返回裝置選單、輸入 q 離開。"

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
        break
      elif [[ "$cmd_input" == "q" || "$cmd_input" == "Q" || "$cmd_input" == "exit" ]]; then
        echo "已離開。"
        exit 0
      elif [[ "$cmd_input" =~ ^[1-9]$ ]]; then
        run_quick_command "$target_dev" "$cmd_input"
        continue
      fi

      # 允許使用者直接輸入任意 adb 指令（支援管線與重導向）
      cmd_input="${cmd_input#adb }"
      eval "adb -s \"$target_dev\" $cmd_input"
      echo "(exit code: $?)"
    done
  done
}

dump_device() {
  local SERIAL="$1"
  local TS="$2"
  local MODEL SAFE_MODEL SAFE_ID PREFIX

  MODEL=$(get_model "$SERIAL")
  if [ -z "$MODEL" ]; then
    echo "=========================================="
    echo "❌ 錯誤：裝置 ($SERIAL) 回應逾時或已斷線，跳過此裝置。"
    return 1
  fi

  SAFE_MODEL=$(echo "$MODEL" | tr ' /' '_')
  SAFE_ID=$(echo "$SERIAL" | tr '.:' '_')
  PREFIX="${OUT_DIR}/${SAFE_MODEL}_${SAFE_ID}_${TS}"

  echo "=========================================="
  echo "目標裝置：[${MODEL}] (${SERIAL})"
  echo "正在擷取 batterystats..."
  adb -s "$SERIAL" shell dumpsys batterystats > "${PREFIX}_raw.txt" 2>/dev/null

  if [ ! -s "${PREFIX}_raw.txt" ]; then
    echo "❌ 錯誤：[${MODEL}] 擷取失敗或中途斷線（檔案為空），已自動清理。"
    rm -f "${PREFIX}_raw.txt"
    return 1
  fi

  echo "正在產生精華檔與分析報告..."
  python battery_extract.py "${PREFIX}_raw.txt" -o "${PREFIX}_extract.txt"
  python battery.py -f "${PREFIX}_raw.txt" -n 20 -m --merge-wl > "${PREFIX}_report.txt"

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
esac

mkdir -p "$OUT_DIR"
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
        break
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
  echo "偵測到多台正常連線裝置，請選擇要擷取的目標（${SCRIPT_VERSION}）："
  print_device_table
  echo "  a) 全部抓取 (共 ${#DEVICES[@]} 台裝置)"

  read -rp "請輸入編號 (1-${#DEVICES[@]}) 或 a: " CHOICE
  if [[ "$CHOICE" == "a" || "$CHOICE" == "A" ]]; then
    TARGETS=("${DEVICES[@]}")
  elif [[ "$CHOICE" =~ ^[0-9]+$ ]] && [ "$CHOICE" -ge 1 ] && [ "$CHOICE" -le ${#DEVICES[@]} ]; then
    TARGETS=("${DEVICES[$((CHOICE-1))]}")
  else
    echo "錯誤：無效的選項。"
    exit 1
  fi
fi

BATCH_TS=$(date +%Y%m%d_%H%M%S)
for dev in "${TARGETS[@]}"; do
  dump_device "$dev" "$BATCH_TS"
done

echo "=========================================="
echo "作業結束！本次成功產出的檔案："
ls -lh "${OUT_DIR}/"*"_${BATCH_TS}_"* 2>/dev/null || echo "(無產出檔案)"
