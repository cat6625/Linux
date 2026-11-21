#!/data/data/com.termux/files/usr/bin/bash
# -------------------------------------------------------------
# Termux Doze 測試工具  v1.3.2（2026-11-21）
#
# 用法：
#   doze
#   doze 41077
#   doze --reset-batterystats
#   doze 41077 --reset-batterystats
#   doze --type screen-off --design-cap 5000 --charge-limit 80% --note "文字"
#   doze --manual      只印出電腦端手動採集的 adb 指令，不執行測試
#   doze --resume 20261120_183359   接續既有測試資料夾，只補擷取測試後資料與摘要
#   doze 40887 --resume 20261120_183359   同上，並指定新的無線偵錯 Port
#   doze --summary-only 20261120_183359   不連 ADB，用既有資料夾重新產生摘要
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
#   v1.3.2（2026-11-21）
#     - --charge-limit 輸入檢查：接受 50–100 的數字（可加 %，自動補成 80%）或 unknown，
#       其他值（例如誤打成 8 或 10）直接報錯，避免把錯誤條件寫進摘要。
#     - 摘要程式建議版本改為 v5.12 以上（容量反推、History 被截斷時的說明、
#       下降量過小時改報上限）。
#   v1.3.1（2026-11-21）
#     - 傳給摘要程式 --collector "doze.sh v<版本>"，摘要的測試條件會記錄採集工具版本。
#     - 摘要程式建議版本改為 v5.11 以上（測試時段的時間錨點改良，History 起點被截斷時
#       也能正確換算；舊版在跨日長時間統計窗可能把測試時段算錯）。
#   v1.3.0（2026-11-21）
#     - 測試起訖時間（TEST_START／TEST_END，本機時間）傳給摘要程式的
#       --test-start／--test-end，摘要可切出「測試時段」（需摘要程式 v5.10 以上）。
#     - 新增 --summary-only <資料夾>：不連 ADB，用既有資料夾重新產生摘要
#       （救回的資料、或升級摘要程式後重算；輸出為 summary-<時間>-re.txt，不覆蓋原摘要）。
#     - 舊版（v1.1.0 以前）建立、沒有 doze_args.txt 的資料夾：測試起訖改由
#       timeline.txt 推算並寫入 doze_args.txt（開始＝送出 KEYCODE_SLEEP；
#       結束＝其後第一筆時間軸紀錄，約略值，可能晚於實際結束數秒）。
#     - 摘要流程抽成函式 run_summary，--resume 與 --summary-only 共用。
#   v1.2.0（2026-11-21）
#     - 測試結束後若 ADB 連不上（例如 Redmi／HyperOS 長時間後自動關閉無線偵錯、
#       Port 已改變），不再兩分鐘後放棄；改為互動重連：Enter 重新掃描、直接輸入
#       新 Port、或 q 離開。掃描失敗時不再對舊 Port 空等重試。
#     - 新增 --resume <資料夾>：離開後可接續既有資料夾，只補擷取測試後資料與摘要
#       （測試條件與目標包由資料夾內的 doze_args.txt 還原；Port 可另外指定）。
#     - 新增 doze_args.txt：記錄測試條件、目標包、TEST_START／TEST_END（本機時間）。
#     - home_end.txt：role 指令失敗（例如 Android 11）時改用 package resolve-activity，
#       且不再列為擷取失敗。
#     - Python 摘要的錯誤訊息另存 summary-error.txt，不再混進摘要檔。
#     - 啟動時提示：長時間測試後可能需要重新開啟無線偵錯。
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
RECONNECT_INTERVAL="${DOZE_RECONNECT_INTERVAL:-5}"

WANT_NETSTATS=0
SLEEP_SCREEN=1

ENABLE_FULL_WAKE_HISTORY=1

SCAN_TIMEOUT=45
SCAN_RANGE="30000-65535"

RESET_BATTERYSTATS=0

DOZE_SH_VERSION="1.3.2"

RESUME_DIR=""
SUMMARY_ONLY=0
TEST_START=""
TEST_END=""

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
        --resume)
            need_value "$@"; RESUME_DIR="$2"; shift
            ;;
        --summary-only)
            need_value "$@"; RESUME_DIR="$2"; SUMMARY_ONLY=1; shift
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
            awk 'NR>1 && /^# -----/{c++; if(c==2) exit} NR>1{print}' "${BASH_SOURCE[0]}"
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

if [[ -n "$CHARGE_LIMIT" ]]; then
    case "$CHARGE_LIMIT" in
        unknown|未知)
            ;;
        *)
            limit_number="${CHARGE_LIMIT%\%}"
            if [[ "$limit_number" =~ ^[0-9]+$ ]] && (( limit_number >= 50 && limit_number <= 100 )); then
                CHARGE_LIMIT="${limit_number}%"
            else
                echo "--charge-limit 必須是 50–100 的百分比（例如 80% 或 100%）或 unknown；收到「${CHARGE_LIMIT}」。" >&2
                exit 2
            fi
            ;;
    esac
fi

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

REQUIRED_CMDS=(adb python3 awk grep sed date timeout)
if (( SUMMARY_ONLY )); then
    REQUIRED_CMDS=(python3 awk grep sed date)
fi

for cmd in "${REQUIRED_CMDS[@]}"; do
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

if [[ -n "$RESUME_DIR" ]]; then
    if [[ -d "$RESUME_DIR" ]]; then
        OUT_DIR="$(cd -P -- "$RESUME_DIR" && pwd)"
    elif [[ -d "${DOWNLOAD_DIR}/doze-test/${RESUME_DIR}" ]]; then
        OUT_DIR="${DOWNLOAD_DIR}/doze-test/${RESUME_DIR}"
    else
        echo "找不到要接續的資料夾：${RESUME_DIR}" >&2
        exit 1
    fi
    TIMESTAMP="$(basename "$OUT_DIR")"
else
    TIMESTAMP="$(date '+%Y%m%d_%H%M%S')"
    OUT_DIR="${DOWNLOAD_DIR}/doze-test/${TIMESTAMP}"
    mkdir -p "$OUT_DIR"
fi
chmod 700 "$OUT_DIR"

ARGS_FILE="${OUT_DIR}/doze_args.txt"

save_run_args() {
    {
        echo "TEST_TYPE=${TEST_TYPE}"
        echo "DESIGN_CAP=${DESIGN_CAP}"
        echo "CHARGE_LIMIT=${CHARGE_LIMIT}"
        echo "TEST_NOTE=${TEST_NOTE}"
        echo "DEVICE_NAME=${DEVICE_NAME}"
        echo "PKGS=$(IFS=,; echo "${PKGS[*]:-}")"
        echo "TEST_START=${TEST_START}"
    } > "$ARGS_FILE"
}

load_run_args() {
    local key value
    [[ -f "$ARGS_FILE" ]] || return 0
    while IFS='=' read -r key value; do
        case "$key" in
            TEST_TYPE)    [[ -n "$TEST_TYPE" ]] || TEST_TYPE="$value" ;;
            DESIGN_CAP)   [[ -n "$DESIGN_CAP" ]] || DESIGN_CAP="$value" ;;
            CHARGE_LIMIT) [[ -n "$CHARGE_LIMIT" ]] || CHARGE_LIMIT="$value" ;;
            TEST_NOTE)    [[ -n "$TEST_NOTE" ]] || TEST_NOTE="$value" ;;
            DEVICE_NAME)  [[ -n "$DEVICE_NAME" ]] || DEVICE_NAME="$value" ;;
            PKGS)
                if (( ${#PKGS[@]} == 0 )) && [[ -n "$value" ]]; then
                    IFS=',' read -r -a PKGS <<< "$value"
                fi
                ;;
            TEST_START)   [[ -z "$value" ]] || TEST_START="$value" ;;
            TEST_END)     [[ -z "$value" ]] || TEST_END="$value" ;;
        esac
    done < "$ARGS_FILE"
}

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
    PY_VERSION_TEXT="未知（建議更新摘要程式至 v5.12 以上）"
fi
log "doze.sh v${DOZE_SH_VERSION}；摘要程式：${PY_VERSION_TEXT}"

if (( ${#PKGS[@]} > 0 )); then
    log "目標包：$(IFS=,; echo "${PKGS[*]}")"
else
    log "目標包：未指定（僅做全局摘要）"
fi

build_cond_args() {
    COND_ARGS=()
    [[ -z "$TEST_TYPE" ]] || COND_ARGS+=(--test-type "$TEST_TYPE")
    [[ -z "$DESIGN_CAP" ]] || COND_ARGS+=(--design-capacity "$DESIGN_CAP")
    [[ -z "$CHARGE_LIMIT" ]] || COND_ARGS+=(--charge-limit "$CHARGE_LIMIT")
    [[ -z "$TEST_NOTE" ]] || COND_ARGS+=(--note "$TEST_NOTE")
    [[ -z "$DEVICE_NAME" ]] || COND_ARGS+=(--device "$DEVICE_NAME")
    COND_ARGS+=(--collector "doze.sh v${DOZE_SH_VERSION}")
    [[ -z "$TEST_START" ]] || COND_ARGS+=(--test-start "$TEST_START")
    [[ -z "$TEST_END" ]] || COND_ARGS+=(--test-end "$TEST_END")
    return 0
}

# 舊版資料夾沒有 doze_args.txt 時，由 timeline.txt 推算測試起訖（約略值）
derive_window_from_timeline() {
    local tl="${OUT_DIR}/timeline.txt" base_day start_t end_t next_day
    [[ -f "$tl" ]] || return 0
    [[ -z "$TEST_START" || -z "$TEST_END" ]] || return 0
    base_day="${TIMESTAMP:0:4}-${TIMESTAMP:4:2}-${TIMESTAMP:6:2}"
    start_t="$(awk '/已送出 KEYCODE_SLEEP/{print $2; exit}' "$tl")"
    end_t="$(awk '/關屏不代表已進入 Deep Doze/{f=1; next} f && /^\[TERMUX\] [0-9]/{print $2; exit}' "$tl")"
    if [[ -z "$start_t" || -z "$end_t" ]]; then
        return 0
    fi
    [[ -n "$TEST_START" ]] || TEST_START="${base_day} ${start_t}"
    if [[ -z "$TEST_END" ]]; then
        if [[ "$end_t" < "$start_t" ]]; then
            next_day="$(date -d "${base_day} +1 day" '+%Y-%m-%d' 2>/dev/null || echo "$base_day")"
            TEST_END="${next_day} ${end_t}"
        else
            TEST_END="${base_day} ${end_t}"
        fi
    fi
    log "由 timeline.txt 推算測試起訖（約略值）：${TEST_START} – ${TEST_END}"
    {
        echo "TEST_START=${TEST_START}"
        echo "TEST_END=${TEST_END}"
    } >> "$ARGS_FILE"
}

SUMMARY_SUFFIX=""

run_summary() {
    build_cond_args
    log "開始產生 Python 摘要。"

    SUMMARY="${OUT_DIR}/summary-${TIMESTAMP}${SUMMARY_SUFFIX}.txt"

    # 動態組裝 --pkg 參數（空陣列時不傳）
    PKG_ARGS=()
    if (( ${#PKGS[@]} > 0 )); then
        PKG_ARGS=(--pkg "$(IFS=,; echo "${PKGS[*]}")")
    fi

    EXTRA_ARGS=()
    if [[ -s "$OUT_DIR/mem_start.txt" && -s "$OUT_DIR/mem_end.txt" ]]; then
        EXTRA_ARGS+=(--mem "$OUT_DIR/mem_start.txt" "$OUT_DIR/mem_end.txt")
    fi
    if [[ -s "$OUT_DIR/battery_start.txt" && -s "$OUT_DIR/battery_end.txt" ]]; then
        EXTRA_ARGS+=(--battery "$OUT_DIR/battery_start.txt" "$OUT_DIR/battery_end.txt")
    fi

    SUMMARY_ERR="${OUT_DIR}/summary-error.txt"

    python3 "$PYTHON_SCRIPT" "$OUT_DIR/full.txt" \
        --checkin "$OUT_DIR/checkin.txt" \
        "${PKG_ARGS[@]}" \
        "${COND_ARGS[@]}" \
        --deviceidle "$OUT_DIR/deviceidle.txt" \
        "${EXTRA_ARGS[@]}" \
        --mask \
        > "$SUMMARY" 2> "$SUMMARY_ERR" || {
            log "⚠ Python 摘要產生失敗，錯誤訊息見 ${SUMMARY_ERR}"
            tail -n 5 "$SUMMARY_ERR" >&2 || true
        }
    [[ -s "$SUMMARY_ERR" ]] || rm -f "$SUMMARY_ERR"

    if [[ -s "$SUMMARY" ]]; then
        cat "$SUMMARY"
    fi
}

if (( SUMMARY_ONLY )); then
    log "=== 只重新產生摘要（不連 ADB），資料夾：${OUT_DIR} ==="
    load_run_args
    if [[ -z "$DEVICE_NAME" && -f "$OUT_DIR/device_info.txt" ]]; then
        DEV_MANUFACTURER="$(sed -n 's/^ro.product.manufacturer=//p' "$OUT_DIR/device_info.txt" | head -n 1)"
        DEV_MODEL="$(sed -n 's/^ro.product.model=//p' "$OUT_DIR/device_info.txt" | head -n 1)"
        DEV_RELEASE="$(sed -n 's/^ro.build.version.release=//p' "$OUT_DIR/device_info.txt" | head -n 1)"
        if [[ -n "${DEV_MODEL}${DEV_MANUFACTURER}" ]]; then
            DEVICE_NAME="${DEV_MANUFACTURER} ${DEV_MODEL} (Android ${DEV_RELEASE:-?})"
        fi
    fi
    derive_window_from_timeline
    [[ -s "$OUT_DIR/full.txt" ]] || die "找不到 ${OUT_DIR}/full.txt，無法產生摘要。"
    SUMMARY_SUFFIX="-re"
    run_summary
    log "=== 摘要完成 ==="
    exit 0
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
    local tries="${1:-$RECONNECT_TRIES}" attempt
    for ((attempt=1; attempt<=tries; attempt++)); do
        adb connect "$ADB_ADDR" >/dev/null 2>&1 || true
        if adb -s "$ADB_ADDR" get-state 2>/dev/null | grep -qx 'device'; then
            log "ADB 已連線至 ${ADB_ADDR}（第 ${attempt} 次）"
            return 0
        fi
        log "ADB 尚未連線，第 ${attempt}/${tries} 次重試。"
        sleep "$RECONNECT_INTERVAL"
    done
    return 1
}

# 先對目前端點短暫重試；失敗後進入互動重連（無線偵錯可能被系統自動關閉、Port 可能已改變）
ensure_adb() {
    local quick_tries="${1:-6}" answer new_port
    if connect_adb "$quick_tries"; then
        return 0
    fi
    while true; do
        echo
        echo "ADB 無法連線：無線偵錯可能已被系統自動關閉，Port 也可能已改變。"
        echo "請在手機重新開啟「無線偵錯」（保持亮屏、同一個 Wi-Fi），然後："
        echo "  Enter     自動掃描 Port"
        echo "  <Port>    直接輸入「無線偵錯」主頁面顯示的連線 Port（不是配對 Port）"
        echo "  q         離開（已擷取的資料保留，之後可用 --resume 補抓）"
        read -r -p "> " answer || return 1
        new_port=""
        case "$answer" in
            q|Q)
                return 1
                ;;
            "")
                new_port="$(detect_adb_port || true)"
                ;;
            *)
                if check_port "$answer"; then
                    new_port="$answer"
                else
                    echo "Port 格式錯誤。"
                    continue
                fi
                ;;
        esac
        if [[ -z "$new_port" ]]; then
            log "未偵測到可用的無線偵錯 Port。"
            continue
        fi
        PORT="$new_port"
        ADB_ADDR="127.0.0.1:${PORT}"
        log "改用端點：${ADB_ADDR}"
        if connect_adb 6; then
            return 0
        fi
    done
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

if [[ -n "$RESUME_DIR" ]]; then
    log "=== 接續既有資料夾（只補擷取測試後資料與摘要），目標端點：${ADB_ADDR} ==="
    log "注意：接續模式的測試後資料擷取時間為現在，不等於測試結束時間（見 doze_args.txt 的 TEST_START／TEST_END）。"
    load_run_args
    derive_window_from_timeline
else
    log "=== Doze 測試開始，目標端點：${ADB_ADDR} ==="
    log "提示：部分機型（例如 Redmi／HyperOS）可能在長時間測試後自動關閉無線偵錯；結束時若連不上，可重新開啟後輸入新 Port，或離開後用 --resume 補抓。"
fi

ensure_adb 6 || die "無法連線到 ${ADB_ADDR}，請確認無線偵錯是否開啟。"

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

if [[ -z "$TEST_TYPE" ]]; then
    log "測試類型未指定（摘要將標示「未提供」）。"
fi

if [[ -z "$RESUME_DIR" ]]; then

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

TEST_START="$(date '+%Y-%m-%d %H:%M:%S')"
save_run_args

# 5. 等待使用者手動結束
echo
echo "======================================"
echo "Doze 測試已開始。"
echo "請保持手機螢幕關閉並等待測試時間。"
echo "完成後回到 Termux，按 Enter 繼續。"
echo "======================================"
read -r -p "按 Enter 結束測試 → " _ || true
TEST_END="$(date '+%Y-%m-%d %H:%M:%S')"
echo "TEST_END=${TEST_END}" >> "$ARGS_FILE"

fi   # 結束「非接續模式」的測試前流程

# 6. 重新連線
if ! ensure_adb 6; then
    log "ADB 未能重新連線；已擷取的資料保留於 ${OUT_DIR}"
    echo
    echo "尚未擷取測試後資料。若手機沒有充電或重開機，統計通常仍保留在手機上"
    echo "（充電或重開機可能使其重置）。重新開啟無線偵錯後可執行："
    echo "  doze <新Port> --resume ${TIMESTAMP}"
    exit 1
fi

log "ADB 重新連線成功。"

# 7. 擷取測試後資料
capture deviceidle.txt adb -s "$ADB_ADDR" shell dumpsys deviceidle
snapshot_battery battery_end.txt
snapshot_mem mem_end.txt

{
    adb -s "$ADB_ADDR" shell cmd role get-role-holders android.app.role.HOME 2>/dev/null ||
    adb -s "$ADB_ADDR" shell cmd package resolve-activity --brief \
        -a android.intent.action.MAIN -c android.intent.category.HOME
} > "$OUT_DIR/home_end.txt" 2>&1 || true
capture full.txt adb -s "$ADB_ADDR" shell dumpsys batterystats
capture checkin.txt adb -s "$ADB_ADDR" shell dumpsys batterystats --checkin
capture history.txt adb -s "$ADB_ADDR" shell dumpsys batterystats --history

if [[ "$WANT_NETSTATS" == "1" ]]; then
    capture netstats.txt adb -s "$ADB_ADDR" shell dumpsys netstats detail
fi

# 8. Python 摘要
run_summary

if (( ${#FAILED_CAPTURES[@]} > 0 )); then
    log "⚠ 以下擷取有問題："
    for f in "${FAILED_CAPTURES[@]}"; do
        log "  - ${f}"
    done
fi

log "=== Doze 測試完成 ==="
log "所有原始資料及摘要位於：${OUT_DIR}"
