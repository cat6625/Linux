#!/data/data/com.termux/files/usr/bin/bash
# -------------------------------------------------------------
# Termux Doze 測試工具
#
# 用法：
#   doze
#   doze 41077
#   doze --reset-batterystats
#   doze 41077 --reset-batterystats
#
# BatteryStats 預設不重置。
# -------------------------------------------------------------

set -Eeuo pipefail
umask 077

# -------------------- 設定區 --------------------

PKGS=("ch.deletescape.lawnchair.plah")

RECONNECT_TRIES=24
RECONNECT_INTERVAL=5

WANT_NETSTATS=0
SLEEP_SCREEN=1

ENABLE_FULL_WAKE_HISTORY=1

SCAN_TIMEOUT=45
SCAN_RANGE="30000-65535"

RESET_BATTERYSTATS=0

# ------------------------------------------------

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_SCRIPT="${SCRIPT_DIR}/doze_summary-termux.py"

DOWNLOAD_DIR="${HOME}/storage/downloads"

PORT=""
ADB_ADDR=""

# ------------------------------------------------
# 參數解析
# ------------------------------------------------

for arg in "$@"; do
    case "$arg" in
        --reset-batterystats)
            RESET_BATTERYSTATS=1
            ;;
        --help|-h)
            echo "用法：$0 [Port] [--reset-batterystats]"
            exit 0
            ;;
        *)
            if [[ -z "$PORT" ]]; then
                PORT="$arg"
            else
                echo "未知參數：$arg" >&2
                exit 2
            fi
            ;;
    esac
done

# ------------------------------------------------
# 基礎檢查
# ------------------------------------------------

check_port() {
    [[ "$1" =~ ^[0-9]+$ ]] || return 1
    (( 10#$1 >= 1 && 10#$1 <= 65535 ))
}

for cmd in adb python3 awk grep sed date timeout; do
    command -v "$cmd" >/dev/null 2>&1 || {
        echo "錯誤：缺少必要指令 ${cmd}" >&2
        exit 1
    }
done

[[ -f "$PYTHON_SCRIPT" ]] || {
    echo "錯誤：找不到 ${PYTHON_SCRIPT}" >&2
    exit 1
}

python3 -c 'import sys; assert sys.version_info >= (3, 8)' || {
    echo "錯誤：Python 版本至少需要 3.8。" >&2
    exit 1
}

[[ -d "$DOWNLOAD_DIR" ]] || {
    echo "錯誤：找不到 Termux 共享下載目錄。"
    echo "請先執行 termux-setup-storage"
    exit 1
}

# ------------------------------------------------
# 輸出目錄及日誌
# ------------------------------------------------

TIMESTAMP="$(date '+%Y%m%d_%H%M%S')"

OUT_DIR="${DOWNLOAD_DIR}/doze-test/${TIMESTAMP}"

mkdir -p "$OUT_DIR"
chmod 700 "$OUT_DIR"

log() {
    printf '[TERMUX] %s %s\n' \
        "$(date '+%H:%M:%S')" "$*" |
        tee -a "$OUT_DIR/timeline.txt" >&2
}

die() {
    log "ERROR：$*"
    exit 1
}

stamp() {
    date '+# captured: %Y-%m-%d %H:%M:%S'
}

log "輸出目錄：${OUT_DIR}"

# ------------------------------------------------
# ADB 函式
# ------------------------------------------------

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
        log "⚠ 找不到 nmap，無法自動掃描。"
        return 1
    }

    log "掃描 localhost ADB 高埠。"

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
    local attempt

    for ((attempt=1; attempt<=RECONNECT_TRIES; attempt++)); do
        adb connect "$ADB_ADDR" >/dev/null 2>&1 || true

        if adb -s "$ADB_ADDR" get-state 2>/dev/null |
            grep -qx 'device'; then

            log "ADB 已連線至 ${ADB_ADDR}（第 ${attempt} 次）"
            return 0
        fi

        log "ADB 尚未連線，第 ${attempt}/${RECONNECT_TRIES} 次重試。"

        sleep "$RECONNECT_INTERVAL"
    done

    return 1
}

# ------------------------------------------------
# 決定 Port
# ------------------------------------------------

if [[ -n "$PORT" ]]; then
    check_port "$PORT" ||
        die "Port 必須是 1–65535 的整數。"

    log "使用手動 Port：${PORT}"
else
    log "自動偵測 ADB Port。"

if PORT="$(detect_adb_port)"; then
    check_port "$PORT" ||
        die "自動偵測回傳了無效 Port：${PORT}"

    log "偵測到 Port：${PORT}"
else
        echo
        echo "自動偵測失敗。"

        read -r -p "請輸入無線除錯 Port（Enter 取消）： " PORT

        [[ -n "$PORT" ]] ||
            die "使用者取消。"

        check_port "$PORT" ||
            die "Port 格式錯誤。"
    fi
fi

ADB_ADDR="127.0.0.1:${PORT}"

# ------------------------------------------------
# 擷取函式
# ------------------------------------------------

capture() {
    local filename="$1"
    shift

    local output="${OUT_DIR}/${filename}"
    local rc=0

    log "擷取 ${filename}。"

    "$@" > "$output" 2>&1 || rc=$?

    if (( rc != 0 )); then
        log "⚠ ${filename} 擷取失敗，退出碼 ${rc}。"
        printf '\n[CAPTURE ERROR] exit_code=%s\n' "$rc" >> "$output"
    fi

    if [[ ! -s "$output" ]]; then
        log "⚠ ${filename} 是空檔。"
    fi

    return 0
}

snapshot_battery() {
    local filename="$1"
    local output="${OUT_DIR}/${filename}"
    local rc=0

    {
        stamp
        adb -s "$ADB_ADDR" shell dumpsys battery
    } > "$output" 2>&1 || rc=$?

    if (( rc != 0 )); then
        log "⚠ 電池快照失敗：${filename}"
    fi

    return 0
}

snapshot_mem() {
    local filename="$1"
    local output="${OUT_DIR}/${filename}"
    local p

    {
        stamp

        for p in "${PKGS[@]}"; do
            echo
            echo "===== PACKAGE: ${p} ====="

            adb -s "$ADB_ADDR" shell dumpsys meminfo "$p" || true
        done
    } > "$output" 2>&1

    return 0
}

# ------------------------------------------------
# 主流程
# ------------------------------------------------

log "=== Doze 測試開始，目標端點：${ADB_ADDR} ==="

connect_adb ||
    die "無法連線到 ${ADB_ADDR}，請確認無線除錯是否開啟。"

# ------------------------------------------------
# 1. 測試前鬧鐘檢查
# ------------------------------------------------

capture alarm_start_full.txt \
    adb -s "$ADB_ADDR" shell dumpsys alarm

NEXT="$(
    grep -A12 -m1 "Next wake from idle" \
        "$OUT_DIR/alarm_start_full.txt" |
    grep -m1 -oE 'triggerTime=[^,[:space:]]+[[:space:]][0-9:]+' |
    sed 's/^triggerTime=//' || true
)"

if [[ -n "$NEXT" ]]; then
    log "找到 Next wake from idle：${NEXT}"

    echo
    echo "找到下一個 wake-from-idle 鬧鐘：${NEXT}"
    echo "請自行確認該鬧鐘是否會影響測試。"

    read -r -p "仍要繼續測試嗎？[y/N] " ans

    [[ "$ans" =~ ^[Yy]$ ]] ||
        die "使用者取消測試。"
else
    log "無法從目前輸出可靠辨識下一個 wake-from-idle 鬧鐘。"
    log "這不代表系統一定沒有鬧鐘。"
fi

# ------------------------------------------------
# 2. 測試前快照
# ------------------------------------------------

snapshot_mem mem_start.txt
snapshot_battery battery_start.txt

adb -s "$ADB_ADDR" shell dumpsys deviceidle unforce ||
    log "⚠ deviceidle unforce 執行失敗。"

# ------------------------------------------------
# 3. BatteryStats 設定
# ------------------------------------------------

if (( ENABLE_FULL_WAKE_HISTORY )); then
    adb -s "$ADB_ADDR" shell \
        dumpsys batterystats --enable full-wake-history ||
        log "⚠ full-wake-history 不支援或執行失敗。"
fi

if (( RESET_BATTERYSTATS )); then
    log "使用者要求重置 BatteryStats，先保存原始統計。"

    capture batterystats_before_reset_full.txt \
        adb -s "$ADB_ADDR" shell dumpsys batterystats

    capture batterystats_before_reset_checkin.txt \
        adb -s "$ADB_ADDR" shell dumpsys batterystats --checkin

    capture batterystats_before_reset_history.txt \
        adb -s "$ADB_ADDR" shell dumpsys batterystats --history

    echo
    echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
    echo "警告：即將重置 Android BatteryStats。"
    echo "這會清除系統既有的累積統計資料。"
    echo "已將可取得的重置前輸出保存至測試資料夾。"
    echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"

    read -r -p "輸入 RESET 才會執行： " confirm

    if [[ "$confirm" == "RESET" ]]; then
        adb -s "$ADB_ADDR" shell dumpsys batterystats --reset ||
            die "BatteryStats 重置失敗。"

        log "BatteryStats 已依使用者確認重置。"
    else
        log "未確認重置，保留原有 BatteryStats。"
    fi
else
    log "BatteryStats 保留原有統計，不執行 --reset。"
fi

# ------------------------------------------------
# 4. 關閉螢幕
# ------------------------------------------------

if [[ "$SLEEP_SCREEN" == "1" ]]; then
    adb -s "$ADB_ADDR" shell input keyevent KEYCODE_SLEEP ||
        log "⚠ KEYCODE_SLEEP 執行失敗。"

    log "已送出 KEYCODE_SLEEP。"
    log "關屏不代表已進入 Deep Doze。"
fi

# ------------------------------------------------
# 5. 等待使用者手動結束
# ------------------------------------------------

echo
echo "======================================"
echo "Doze 測試已開始。"
echo "請保持手機螢幕關閉並等待測試時間。"
echo "完成後回到 Termux，按 Enter 繼續。"
echo "======================================"

read -r -p "按 Enter 結束測試 → " _

# ------------------------------------------------
# 6. 重新連線
# ------------------------------------------------

if ! connect_adb; then
    echo
    echo "ADB 目前無法連線。"
    echo "請確認手機已亮屏，且無線除錯仍開啟。"

    read -r -p "完成後按 Enter 重試 → " _

    if NEW_PORT="$(detect_adb_port)"; then
        PORT="$NEW_PORT"
        ADB_ADDR="127.0.0.1:${PORT}"

        log "重新偵測到端點：${ADB_ADDR}"
    fi

    connect_adb ||
        die "重新連線失敗，原始資料保留於 ${OUT_DIR}"
fi

log "ADB 重新連線成功。"

# ------------------------------------------------
# 7. 擷取測試後資料
# ------------------------------------------------

capture deviceidle.txt \
    adb -s "$ADB_ADDR" shell dumpsys deviceidle

snapshot_battery battery_end.txt
snapshot_mem mem_end.txt

capture home_end.txt \
    adb -s "$ADB_ADDR" shell cmd role \
    get-role-holders android.app.role.HOME

capture full.txt \
    adb -s "$ADB_ADDR" shell dumpsys batterystats

capture checkin.txt \
    adb -s "$ADB_ADDR" shell dumpsys batterystats --checkin

capture history.txt \
    adb -s "$ADB_ADDR" shell dumpsys batterystats --history

if [[ "$WANT_NETSTATS" == "1" ]]; then
    capture netstats.txt \
        adb -s "$ADB_ADDR" shell dumpsys netstats detail
fi

# ------------------------------------------------
# 8. Python 摘要
# ------------------------------------------------

log "開始產生 Python 摘要。"

SUMMARY="${OUT_DIR}/summary-${TIMESTAMP}.txt"

python3 "$PYTHON_SCRIPT" "$OUT_DIR/full.txt" \
    --checkin "$OUT_DIR/checkin.txt" \
    --pkg "$(IFS=,; echo "${PKGS[*]}")" \
    --deviceidle "$OUT_DIR/deviceidle.txt" \
    --mem "$OUT_DIR/mem_start.txt" "$OUT_DIR/mem_end.txt" \
    --battery "$OUT_DIR/battery_start.txt" "$OUT_DIR/battery_end.txt" \
    > "$SUMMARY" 2>&1 || {
        log "⚠ Python 摘要產生失敗，請檢查 ${SUMMARY}"
    }

if [[ -s "$SUMMARY" ]]; then
    cat "$SUMMARY"
fi

log "=== Doze 測試完成 ==="
log "所有原始資料及摘要位於：${OUT_DIR}"
