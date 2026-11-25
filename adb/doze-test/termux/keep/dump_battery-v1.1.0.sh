#!/bin/bash
# ==============================================================================
# 腳本名稱：dump_battery.sh
# 版本資訊：v1.1.0
# 更新日期：2026-11-25
# ==============================================================================

OUT_DIR="reports"
mkdir -p "$OUT_DIR"

# 1. 檢查並提醒是否有 offline 的裝置
OFFLINE_DEVS=$(adb devices | awk '$2 == "offline" {print $1}')
if [ -n "$OFFLINE_DEVS" ]; then
  echo "⚠️  警告：偵測到以下裝置處於 offline 狀態（本次將會跳過）："
  echo "$OFFLINE_DEVS" | sed 's/^/   - /'
  echo "   (提示：若需抓取請先點亮該手機螢幕或重新 adb connect)"
  echo ""
fi

# 2. 取得所有正常連線 (device) 的裝置
mapfile -t DEVICES < <(adb devices | awk '$2 == "device" {print $1}')

if [ ${#DEVICES[@]} -eq 0 ]; then
  echo "錯誤：未偵測到任何正常連線 (device) 的 ADB 裝置。"
  exit 1
fi

dump_device() {
  local SERIAL="$1"
  local TS="$2"
  local MODEL
  local SAFE_ID
  local PREFIX

  MODEL=$(adb -s "$SERIAL" shell getprop ro.product.model 2>/dev/null | tr -d '\r' | tr ' /' '_')
  # 若連 getprop 都抓不到，代表剛斷線
  if [ -z "$MODEL" ]; then
    echo "=========================================="
    echo "❌ 錯誤：裝置 ($SERIAL) 回應逾時或已斷線，跳過此裝置。"
    return 1
  fi

  SAFE_ID=$(echo "$SERIAL" | tr '.:' '_')
  PREFIX="${OUT_DIR}/${MODEL}_${SAFE_ID}_${TS}"

  echo "=========================================="
  echo "目標裝置：[${MODEL}] (${SERIAL})"
  echo "正在擷取 batterystats..."
  adb -s "$SERIAL" shell dumpsys batterystats > "${PREFIX}_raw.txt" 2>/dev/null

  # 檢查抓下來的檔案是否為空（防止中途斷線產生 0 byte 檔案）
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

TARGETS=()

if [ -n "$1" ]; then
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
  echo "偵測到多台正常連線裝置，請選擇要擷取的目標："
  for i in "${!DEVICES[@]}"; do
    DEV_MODEL=$(adb -s "${DEVICES[$i]}" shell getprop ro.product.model 2>/dev/null | tr -d '\r')
    printf "  %d) %-22s [%s]\n" $((i+1)) "${DEVICES[$i]}" "${DEV_MODEL:-無回應}"
  done
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
