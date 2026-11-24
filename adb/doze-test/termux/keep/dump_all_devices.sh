#!/bin/bash

# 取得所有狀態為 "device" 的連線裝置（包含 USB 序列號與無線 IP:Port）
DEVICES=$(adb devices | awk '$2 == "device" {print $1}')

if [ -z "$DEVICES" ]; then
  echo "錯誤：目前沒有任何已連線的 ADB 裝置。"
  exit 1
fi

TS=$(date +%Y%m%d_%H%M%S)

for SERIAL in $DEVICES; do
  # 取得該裝置的型號並清理特殊字元
  MODEL=$(adb -s "$SERIAL" shell getprop ro.product.model | tr -d '\r' | tr ' /' '_')
  # 將 IP:Port 中的冒號與點替換為底線，避免檔名異常（若為 USB 則保留原序列號）
  SAFE_ID=$(echo "$SERIAL" | tr '.:' '_')
  PREFIX="${MODEL}_${SAFE_ID}_${TS}"

  echo "=========================================="
  echo "正在處理裝置: [$MODEL] ($SERIAL)"
  mkdir -p reports
  adb -s "$SERIAL" shell dumpsys batterystats > "reports/${PREFIX}_raw.txt"
  python battery_extract.py "reports/${PREFIX}_raw.txt" -o "reports/${PREFIX}_extract.txt"
  python battery.py -f "reports/${PREFIX}_raw.txt" -n 20 -m --merge-wl > "reports/${PREFIX}_report.txt"

  echo "完成輸出前綴: reports/${PREFIX}"
done

echo "=========================================="
echo "所有裝置匯出完畢！本次產出檔案："
ls -lh reports/*"_${TS}_"*
