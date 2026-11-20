#!/data/data/com.termux/files/usr/bin/bash
# -------------------------------------------------------------
# Termux Doze 測試工具  v1.1.0（2026-11-20）
#
# 用法：
#   doze
#   doze 41077
#   doze --reset-batterystats
#   doze 41077 --reset-batterystats
#   doze --type screen-off --design-cap 5000 --charge-limit 80% --note "文字"
#   doze --manual      只印出電腦端手動採集的 adb 指令，不執行測試
#   doze --version
#
# 測試條件（可選；未提供時摘要標示「未提供」，不會被猜測）：
#   --type daily|screen-off|ab   測試類型：日常混合／受控黑屏待機／A/B 對照
#   --design-cap <mAh>           設計容量（使用者提供）
#   --charge-limit <文字>        充電上限，例如 80% 或 100%
#   --note <文字>                其他條件，例如 "Wi-Fi 開、行動網路關"
#   --device <文字>              機型；未提供時自動由 getprop 組成
#   也可用環境變數 DOZE_TEST_TYPE / DOZE_DESIGN_CAP / DOZE_CHARGE_LIMIT /
#   DOZE_NOTE / DOZE_DEVICE 代替參數。
#
# 目標包（可選，逗號分隔）：
#   DOZE_PKGS="com.example.foo,com.example.bar" doze
#   或直接修改下方 PKGS=(...)
#
# BatteryStats 預設不重置。
#
# 修改內容：
#   v1.1.0（2026-11-20）
#     - 新增測試條件參數 --type / --design-cap / --charge-limit / --note /
#       --device（及對應環境變數），傳給 doze_summary-termux.py（需 v5.8 以上）。
#     - 新增 device_info.txt：擷取廠牌、機型、Android 版本、Build ID（不含序號），
#       並自動組成 --device。
#     - 新增 --manual：印出不依賴 Termux 的電腦端手動採集指令與摘要指令。
#     - 新增 --version；時間軸記錄 doze.sh 與摘要程式的版本。
#     - 參數解析改為 while 迴圈，並檢查選項值（類型、容量數字）。
#   v1.0.0
#     - 無線除錯 ADB 自動偵測／連線、Doze 與 batterystats 擷取、
#       呼叫 Python 產生摘要。
# -------------------------------------------------------------

set -Eeuo pipefail
umask 077

# -------------------- 設定區 --------------------

# ★ 目標包：預設留空（不指定），若要分析特定 App 請填入
if [[ -n "${DOZE_PKGS:-}" ]]; then
    IFS=',' read -r -a PKGS <<< "$DOZE_PKGS"
else
    PKGS=()
fi

RECONNECT_TRIES=24
RECONNECT_INTERVAL=5

WANT_NETSTATS=0
SLEEP_SCREEN=1

ENABLE_FULL_WAKE_HISTORY=1

SCAN_TIMEOUT=45
SCAN_RANGE="30000-65535"

RESET_BATTERYSTATS=0

DOZE_SH_VERSION="1.1.0"

TEST_TYPE="${DOZE_TEST_TYPE:-}"
DESIGN_CAP="${DOZE_DESIGN_CAP:-}"
CHARGE_LIMIT="${DOZE_CHARGE_LIMIT:-}"
TEST_NOTE="${DOZE_NOTE:-}"
DEVICE_NAME="${DOZE_DEVICE:-}"

# ------------------------------------------------

SOURCE_PATH="${BASH_SOURCE[0]}"

while [[ -L "$SOURCE_PATH" ]]; do
    SOURCE_DIR="$(cd -P -- "$(dirname -- "$SOURCE_PATH")" && pwd)"
    LINK_TARGET="$(readlink "$SOURCE_PATH")"
    if [[ "$LINK_TARGET" == /* ]]; then
        SOURCE_PATH="$LINK_TARGET"
    else
        SOURCE_PATH="${SOURCE_DIR}/${LINK_TARGET}"
    fi
done

SCRIPT_DIR="$(cd -P -- "$(dirname -- "$SOURCE_PATH")" && pwd)"
PYTHON_SCRIPT="${SCRIPT_DIR}/doze_summary-termux.py"

DOWNLOAD_DIR="${HOME}/storage/downloads"

PORT=""
ADB_ADDR=""

FAILED_CAPTURES=()

# ------------------------------------------------
# 參數解析
# ------------------------------------------------

print_manual() {
    cat <<'MANUAL'
# 不依賴 Termux 的手動採集（電腦已用 adb 連上手機）
# 1) 測試前
adb shell dumpsys deviceidle unforce
adb shell dumpsys batterystats --enable full-wake-history
(echo "# captured: $(date '+%Y-%m-%d %H:%M:%S')"; adb shell dumpsys battery) > battery_start.txt
# 2) 關螢幕並等待測試時間（建議黑屏、不操作）
# 3) 測試後
(echo "# captured: $(date '+%Y-%m-%d %H:%M:%S')"; adb shell dumpsys battery) > battery_end.txt
adb shell dumpsys batterystats > full.txt
adb shell dumpsys batterystats --checkin > checkin.txt
adb shell dumpsys deviceidle > deviceidle.txt
for k in ro.product.manufacturer ro.product.model ro.build.version.release; do adb shell getprop $k; done
# 4) 摘要（測試條件請依實際填寫；不確定的項目可省略）
python3 doze_summary-termux.py full.txt --checkin checkin.txt --deviceidle deviceidle.txt   --battery battery_start.txt battery_end.txt   --test-type screen-off --design-capacity 5000 --charge-limit 80% --device "機型" --mask
MANUAL
}

need_value() {
    [[ $# -ge 2 && -n "$2" ]] || {
        echo "選項 $1 需要參數。" >&2
        exit 2
    }
}

while (( $# > 0 )); do
    case "$1" in
        --reset-batterystats)
            RESET_BATTERYSTATS=1
            ;;
        --type)
            need_value "$@"; TEST_TYPE="$2"; shift
            ;;
        --design-cap)
            need_value "$@"; DESIGN_CAP="$2"; shift
            ;;
        --charge-limit)
            need_value "$@"; CHARGE_LIMIT="$2"; shift
            ;;
        --note)
            need_value "$@"; TEST_NOTE="$2"; shift
            ;;
        --device)
            need_value "$@"; DEVICE_NAME="$2"; shift
            ;;
        --manual)
            print_manual
            exit 0
            ;;
        --version)
            echo "doze.sh v${DOZE_SH_VERSION}"
            exit 0
            ;;
        --help|-h)
            sed -n '2,/^# ------------------------------------------------------------\{1,\}$/p' "${BASH_SOURCE[0]}" | sed -n '1,45p'
            echo "環境變數：DOZE_PKGS=\"pkg1,pkg2\" 指定目標包"
            exit 0
            ;;
        -*)
            echo "未知選項：$1" >&2
            exit 2
            ;;
        *)
            if [[ -z "$PORT" ]]; then
                PORT="$1"
            else
                echo "未知參數：$1" >&2
                exit 2
            fi
            ;;
    esac
    shift
done

case "$TEST_TYPE" in
    ""|daily|screen-off|ab) ;;
    *) echo "--type 只能是 daily、screen-off 或 ab。" >&2; exit 2 ;;
esac

if [[ -n "$DESIGN_CAP" && ! "$DESIGN_CAP" =~ ^[0-9]+([.][0-9]+)?$ ]]; then
    echo "--design-cap 必須是數字（mAh）。" >&2
    exit 2
fi

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

echo "腳本位置：${SCRIPT_DIR}" >&2
echo "Python 摘要程式：${PYTHON_SCRIPT}" >&2

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
    printf '[TERMUX] %s %s\n' "$(date '+%H:%M:%S')" "$*" | tee -a "$OUT_DIR/timeline.txt" >&2
}

die() {
    log "ERROR：$*"
    exit 1
}

stamp() {
    date '+# captured: %Y-%m-%d %H:%M:%S'
}

log "輸出目錄：${OUT_DIR}"

PY_VERSION_TEXT="$(python3 "$PYTHON_SCRIPT" --version 2>&1 | head -n 1 || true)"
if [[ ! "$PY_VERSION_TEXT" =~ v5\.[0-9]+ ]]; then
    PY_VERSION_TEXT="未知（建議更新摘要程式至 v5.8 以上）"
fi
log "doze.sh v${DOZE_SH_VERSION}；摘要程式：${PY_VERSION_TEXT}"

if (( ${#PKGS[@]} > 0 )); then
    log "目標包：$(IFS=,; echo "${PKGS[*]}")"
else
    log "目標包：未指定（僅做全局摘要）"
fi

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
    local connected scanned p addr

    connected="$(find_connected_port || true)"
    if [[ -n "$connected" ]]; then
        printf '%s\n' "$connected"
        return 0
    fi

    command -v nmap >/dev/null 2>&1 || {
        log "⚠ 找不到 nmap，無法自動掃描（pkg install nmap 可啟用）。"
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
        if adb -s "$ADB_ADDR" get-state 2>/dev/null | grep -qx 'device'; then
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
    check_port "$PORT" || die "Port 必須是 1–65535 的整數。"
    log "使用手動 Port：${PORT}"
else
    log "自動偵測 ADB Port。"
    if PORT="$(detect_adb_port)"; then
        check_port "$PORT" || die "自動偵測回傳了無效 Port：${PORT}"
        log "偵測到 Port：${PORT}"
    else
        echo
        echo "自動偵測失敗。"
        read -r -p "請輸入無線除錯 Port（Enter 取消）： " PORT || die "使用者中斷"
        [[ -n "$PORT" ]] || die "使用者取消。"
        check_port "$PORT" || die "Port 格式錯誤。"
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
        FAILED_CAPTURES+=("${filename}(rc=${rc})")
    fi

    if [[ ! -s "$output" ]]; then
        log "⚠ ${filename} 是空檔。"
        FAILED_CAPTURES+=("${filename}(empty)")
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
        FAILED_CAPTURES+=("${filename}(rc=${rc})")
    fi
    return 0
}

snapshot_mem() {
    local filename="$1"
    local output="${OUT_DIR}/${filename}"
    local p

    {
        stamp
        if (( ${#PKGS[@]} == 0 )); then
            echo
            echo "# 未指定目標包；輸出全局 meminfo 摘要"
            adb -s "$ADB_ADDR" shell dumpsys meminfo || true
        else
            for p in "${PKGS[@]}"; do
                echo
                echo "===== PACKAGE: ${p} ====="
                adb -s "$ADB_ADDR" shell dumpsys meminfo "$p" || true
            done
        fi
    } > "$output" 2>&1

    return 0
}

# ------------------------------------------------
# 主流程
# ------------------------------------------------

log "=== Doze 測試開始，目標端點：${ADB_ADDR} ==="

connect_adb || die "無法連線到 ${ADB_ADDR}，請確認無線除錯是否開啟。"

# 0. 裝置資訊（不含序號）
get_prop() {
    adb -s "$ADB_ADDR" shell getprop "$1" 2>/dev/null | tr -d '\r' || true
}

DEV_MANUFACTURER="$(get_prop ro.product.manufacturer)"
DEV_MODEL="$(get_prop ro.product.model)"
DEV_RELEASE="$(get_prop ro.build.version.release)"
{
    stamp
    echo "ro.product.manufacturer=${DEV_MANUFACTURER}"
    echo "ro.product.model=${DEV_MODEL}"
    echo "ro.product.device=$(get_prop ro.product.device)"
    echo "ro.build.version.release=${DEV_RELEASE}"
    echo "ro.build.version.sdk=$(get_prop ro.build.version.sdk)"
    echo "ro.build.display.id=$(get_prop ro.build.display.id)"
} > "$OUT_DIR/device_info.txt" 2>&1 || true

if [[ -z "$DEVICE_NAME" && -n "${DEV_MODEL}${DEV_MANUFACTURER}" ]]; then
    DEVICE_NAME="${DEV_MANUFACTURER} ${DEV_MODEL} (Android ${DEV_RELEASE:-?})"
fi
log "裝置：${DEVICE_NAME:-未取得}"

COND_ARGS=()
[[ -n "$TEST_TYPE" ]] && COND_ARGS+=(--test-type "$TEST_TYPE")
[[ -n "$DESIGN_CAP" ]] && COND_ARGS+=(--design-capacity "$DESIGN_CAP")
[[ -n "$CHARGE_LIMIT" ]] && COND_ARGS+=(--charge-limit "$CHARGE_LIMIT")
[[ -n "$TEST_NOTE" ]] && COND_ARGS+=(--note "$TEST_NOTE")
[[ -n "$DEVICE_NAME" ]] && COND_ARGS+=(--device "$DEVICE_NAME")
if [[ -z "$TEST_TYPE" ]]; then
    log "測試類型未指定（摘要將標示「未提供」）。"
fi

# 1. 測試前鬧鐘檢查
capture alarm_start_full.txt adb -s "$ADB_ADDR" shell dumpsys alarm

NEXT="$(
    grep -A40 -m1 "Next wake from idle" "$OUT_DIR/alarm_start_full.txt" |
    grep -m1 -oE 'triggerTime=[^,[:space:]]+[[:space:]][0-9:]+' |
    sed 's/^triggerTime=//' || true
)"

if [[ -n "$NEXT" ]]; then
    log "找到 Next wake from idle：${NEXT}"
    echo
    echo "找到下一個 wake-from-idle 鬧鐘：${NEXT}"
    echo "請自行確認該鬧鐘是否會影響測試。"
    read -r -p "仍要繼續測試嗎？[y/N] " ans || die "使用者中斷"
    [[ "$ans" =~ ^[Yy]$ ]] || die "使用者取消測試。"
else
    log "無法從目前輸出可靠辨識下一個 wake-from-idle 鬧鐘。"
    log "這不代表系統一定沒有鬧鐘。"
fi

# 2. 測試前快照
snapshot_mem mem_start.txt
snapshot_battery battery_start.txt

adb -s "$ADB_ADDR" shell dumpsys deviceidle unforce ||
    log "⚠ deviceidle unforce 執行失敗。"

# 3. BatteryStats 設定
if (( ENABLE_FULL_WAKE_HISTORY )); then
    adb -s "$ADB_ADDR" shell dumpsys batterystats --enable full-wake-history ||
        log "⚠ full-wake-history 不支援或執行失敗。"
fi

if (( RESET_BATTERYSTATS )); then
    log "使用者要求重置 BatteryStats，先保存原始統計。"
    capture batterystats_before_reset_full.txt adb -s "$ADB_ADDR" shell dumpsys batterystats
    capture batterystats_before_reset_checkin.txt adb -s "$ADB_ADDR" shell dumpsys batterystats --checkin
    capture batterystats_before_reset_history.txt adb -s "$ADB_ADDR" shell dumpsys batterystats --history

    echo
    echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
    echo "警告：即將重置 Android BatteryStats。"
    echo "這會清除系統既有的累積統計資料。"
    echo "已將可取得的重置前輸出保存至測試資料夾。"
    echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
    read -r -p "輸入 RESET 才會執行： " confirm || die "使用者中斷"

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

# 4. 關閉螢幕
if [[ "$SLEEP_SCREEN" == "1" ]]; then
    adb -s "$ADB_ADDR" shell input keyevent KEYCODE_SLEEP ||
        log "⚠ KEYCODE_SLEEP 執行失敗。"
    log "已送出 KEYCODE_SLEEP。"
    log "關屏不代表已進入 Deep Doze。"
fi

# 5. 等待使用者手動結束
echo
echo "======================================"
echo "Doze 測試已開始。"
echo "請保持手機螢幕關閉並等待測試時間。"
echo "完成後回到 Termux，按 Enter 繼續。"
echo "======================================"
read -r -p "按 Enter 結束測試 → " _ || true

# 6. 重新連線
if ! connect_adb; then
    echo
    echo "ADB 目前無法連線。"
    echo "請確認手機已亮屏，且無線除錯仍開啟。"
    read -r -p "完成後按 Enter 重試 → " _ || die "使用者中斷"

    if NEW_PORT="$(detect_adb_port)"; then
        PORT="$NEW_PORT"
        ADB_ADDR="127.0.0.1:${PORT}"
        log "重新偵測到端點：${ADB_ADDR}"
    fi

    connect_adb ||
        die "重新連線失敗，原始資料保留於 ${OUT_DIR}"
fi

log "ADB 重新連線成功。"

# 7. 擷取測試後資料
capture deviceidle.txt adb -s "$ADB_ADDR" shell dumpsys deviceidle
snapshot_battery battery_end.txt
snapshot_mem mem_end.txt

capture home_end.txt adb -s "$ADB_ADDR" shell cmd role get-role-holders android.app.role.HOME
capture full.txt adb -s "$ADB_ADDR" shell dumpsys batterystats
capture checkin.txt adb -s "$ADB_ADDR" shell dumpsys batterystats --checkin
capture history.txt adb -s "$ADB_ADDR" shell dumpsys batterystats --history

if [[ "$WANT_NETSTATS" == "1" ]]; then
    capture netstats.txt adb -s "$ADB_ADDR" shell dumpsys netstats detail
fi

# 8. Python 摘要
log "開始產生 Python 摘要。"

SUMMARY="${OUT_DIR}/summary-${TIMESTAMP}.txt"

# 動態組裝 --pkg 參數（空陣列時不傳）
PKG_ARGS=()
if (( ${#PKGS[@]} > 0 )); then
    PKG_ARGS=(--pkg "$(IFS=,; echo "${PKGS[*]}")")
fi

python3 "$PYTHON_SCRIPT" "$OUT_DIR/full.txt" \
    --checkin "$OUT_DIR/checkin.txt" \
    "${PKG_ARGS[@]}" \
    "${COND_ARGS[@]}" \
    --deviceidle "$OUT_DIR/deviceidle.txt" \
    --mem "$OUT_DIR/mem_start.txt" "$OUT_DIR/mem_end.txt" \
    --battery "$OUT_DIR/battery_start.txt" "$OUT_DIR/battery_end.txt" \
    --mask \
    > "$SUMMARY" 2>&1 || {
        log "⚠ Python 摘要產生失敗，請檢查 ${SUMMARY}"
    }

if [[ -s "$SUMMARY" ]]; then
    cat "$SUMMARY"
fi

if (( ${#FAILED_CAPTURES[@]} > 0 )); then
    log "⚠ 以下擷取有問題："
    for f in "${FAILED_CAPTURES[@]}"; do
        log "  - ${f}"
    done
fi

log "=== Doze 測試完成 ==="
log "所有原始資料及摘要位於：${OUT_DIR}"
