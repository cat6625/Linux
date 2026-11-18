#!/usr/bin/env bash
set -euo pipefail

DEFAULT_PORT=5555
MAX_RETRIES=5
RETRY_INTERVAL=2
LOG_FILE="${HOME}/adb_auto_connect.log"

log() {
    local level="$1"
    local msg="$2"
    local ts
    ts=$(date +"%Y-%m-%d %H:%M:%S")
    echo "[$ts] [$level] $msg" | tee -a "$LOG_FILE"
}

detect_adb_port() {
    local connected
    connected=$(adb devices 2>/dev/null |
        awk '/^127\.0\.0\.1:[0-9]+[[:space:]]+device$/ {print $1}' |
        cut -d: -f2 |
        head -n1 || true)

    if [ -n "$connected" ]; then
        echo "$connected"
        return 0
    fi

    if command -v nmap >/dev/null 2>&1; then
        local scanned
        scanned=$(nmap -sT -Pn -n --open -T4 -p 30000-65535 127.0.0.1 2>/dev/null |
            awk '/^[0-9]+\/tcp[[:space:]]+open/ {print $1}' |
            cut -d/ -f1)

        if [ -n "$scanned" ]; then
            for p in $scanned; do
                if adb connect "127.0.0.1:${p}" >/dev/null 2>&1; then
                    if adb devices 2>/dev/null | awk -v addr="127.0.0.1:${p}" '$1==addr && $2=="device"{found=1} END{exit !found}'; then
                        echo "$p"
                        return 0
                    fi
                fi
            done
        fi
    fi

    return 1
}

if [ -n "${1:-}" ]; then
    PORT="$1"
    log INFO "使用手動指定的 Port：$PORT"
else
    log INFO "未指定 Port，正在自動偵測無線除錯端點..."
    if PORT=$(detect_adb_port); then
        log INFO "自動偵測成功：$PORT"
    else
        PORT="$DEFAULT_PORT"
        log WARN "無法自動偵測（請確認已開啟「無線除錯」並安裝 nmap），改用預設 Port：$PORT"
    fi
fi

ADB_ADDR="127.0.0.1:${PORT}"

adb_connect() {
    local attempt=1
    while (( attempt <= MAX_RETRIES )); do
        log INFO "嘗試連線 ADB (${ADB_ADDR})，第 $attempt 次..."
        if adb connect "$ADB_ADDR" >/dev/null 2>&1; then
            if adb devices | awk -v addr="$ADB_ADDR" '$1==addr && $2=="device"{found=1} END{exit !found}'; then
                log INFO "ADB 已成功連線至 $ADB_ADDR"
                return 0
            fi
        fi
        log WARN "第 $attempt 次連線失敗，於 $RETRY_INTERVAL 秒後重試"
        ((attempt++))
        sleep "$RETRY_INTERVAL"
    done
    log ERROR "無法在 $MAX_RETRIES 次嘗試內連線至 $ADB_ADDR"
    return 1
}

log INFO "=== ADB 自動連接腳本啟動 ==="
if adb_connect; then
    log INFO "執行示例指令：adb -s $ADB_ADDR shell getprop ro.product.model"
    adb -s "$ADB_ADDR" shell getprop ro.product.model | tee -a "$LOG_FILE"
else
    log ERROR "連線失敗，腳本即將結束"
    exit 1
fi

log INFO "=== 腳本執行完畢 ==="
