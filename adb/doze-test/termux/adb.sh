#!/data/data/com.termux/files/usr/bin/bash
# -------------------------------------------------------------
# Termux ADB 自動連線工具
#
# 用法：
#   ./adb.sh
#   ./adb.sh 41077
#
# 自動偵測失敗時會要求手動輸入 Port。
# -------------------------------------------------------------

set -Eeuo pipefail
umask 077

MAX_RETRIES=8
RETRY_INTERVAL=3

SCAN_TIMEOUT=45
SCAN_RANGE="30000-65535"

LOG_FILE="${HOME}/adb_auto_connect.log"

log() {
    local level="$1"
    shift

    local ts
    ts="$(date '+%Y-%m-%d %H:%M:%S')"

    printf '[%s] [%s] %s\n' "$ts" "$level" "$*" |
        tee -a "$LOG_FILE" >&2
}

die() {
    log ERROR "$*"
    exit 1
}

check_port() {
    [[ "$1" =~ ^[0-9]+$ ]] || return 1
    (( 10#$1 >= 1 && 10#$1 <= 65535 ))
}

adb_is_connected() {
    local addr="$1"

    adb devices 2>/dev/null |
        awk -v addr="$addr" '
            $1 == addr && $2 == "device" { found=1 }
            END { exit !found }
        '
}

find_connected_port() {
    adb devices 2>/dev/null |
        awk '
            /^127\.0\.0\.1:[0-9]+[[:space:]]+device$/ {
                sub(/^127\.0\.0\.1:/, "", $1)
                print $1
                exit
            }
        '
}

detect_adb_port() {
    local connected
    local scanned
    local p
    local addr

    connected="$(find_connected_port || true)"

    if [[ -n "$connected" ]]; then
        printf '%s\n' "$connected"
        return 0
    fi

    command -v nmap >/dev/null 2>&1 || {
        log WARN "找不到 nmap，無法自動掃描。"
        return 1
    }

    command -v timeout >/dev/null 2>&1 || {
        log WARN "找不到 timeout，無法執行有逾時保護的掃描。"
        return 1
    }

    log INFO "掃描 localhost TCP ${SCAN_RANGE}，逾時 ${SCAN_TIMEOUT} 秒。"

    scanned="$(
        timeout "${SCAN_TIMEOUT}s" nmap \
            -sT -Pn -n --open -T4 \
            --host-timeout "${SCAN_TIMEOUT}s" \
            -p "$SCAN_RANGE" 127.0.0.1 2>/dev/null |
        awk '
            /^[0-9]+\/tcp[[:space:]]+open/ {
                sub(/\/tcp/, "", $1)
                print $1
            }
        ' || true
    )"

    [[ -n "$scanned" ]] || return 1

    while IFS= read -r p; do
        [[ -n "$p" ]] || continue
        check_port "$p" || continue

        addr="127.0.0.1:${p}"

        adb connect "$addr" >/dev/null 2>&1 || true

        if adb_is_connected "$addr"; then
            printf '%s\n' "$p"
            return 0
        fi
    done <<< "$scanned"

    return 1
}

connect_adb() {
    local addr="$1"
    local attempt

    for ((attempt=1; attempt<=MAX_RETRIES; attempt++)); do
        log INFO "ADB 連線 ${addr}，第 ${attempt}/${MAX_RETRIES} 次。"

        adb connect "$addr" >/dev/null 2>&1 || true

        if adb_is_connected "$addr"; then
            log INFO "ADB 連線成功：${addr}"
            return 0
        fi

        sleep "$RETRY_INTERVAL"
    done

    return 1
}

# -------------------------------------------------------------
# 主流程
# -------------------------------------------------------------

command -v adb >/dev/null 2>&1 ||
    die "找不到 adb，請先安裝 android-tools。"

if [[ -n "${1:-}" ]]; then
    PORT="$1"

    check_port "$PORT" ||
        die "Port 必須是 1–65535 的整數。"

    log INFO "使用手動指定 Port：${PORT}"
else
    log INFO "開始自動偵測 ADB 端點。"

if PORT="$(detect_adb_port)"; then
    check_port "$PORT" ||
        die "自動偵測回傳了無效 Port：${PORT}"

    log INFO "偵測到 Port：${PORT}"
else
        echo
        echo "無法自動偵測 ADB 端點。"
        echo "請確認手機已開啟「開發人員選項 → 無線除錯」。"

        read -r -p "請輸入無線除錯畫面顯示的 Port（Enter 取消）： " PORT

        [[ -n "$PORT" ]] ||
            die "使用者取消。"

        check_port "$PORT" ||
            die "Port 必須是 1–65535 的整數。"
    fi
fi

ADB_ADDR="127.0.0.1:${PORT}"

log INFO "=== ADB 自動連線工具啟動 ==="

if ! connect_adb "$ADB_ADDR"; then
    die "無法連線至 ${ADB_ADDR}，請確認無線除錯配對及 Port。"
fi

log INFO "裝置型號："

adb -s "$ADB_ADDR" shell getprop ro.product.model |
    tee -a "$LOG_FILE"

log INFO "Android 版本："

adb -s "$ADB_ADDR" shell getprop ro.build.version.release |
    tee -a "$LOG_FILE"

log INFO "ADB 工具執行完成。"
