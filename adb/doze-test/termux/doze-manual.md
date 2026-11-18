# Termux Android Doze & ADB 自動化測試工具組

本專案提供一套運行於 **Termux（無需 Root）** 的 Android 待機耗電與 Doze 自動化測試工具。

透過 Android 本機無線除錯（Wireless Debugging），自動偵測 ADB 連接埠、建立連線、收集系統 `batterystats`、`deviceidle`、`meminfo`、`battery` 等資料，並透過 Python 分析程式產生易於判讀的待機耗電與深度睡眠摘要報告。

本工具的設計原則：

- 不需要 Root 權限。
- 優先使用已連線的 ADB 端點，必要時才使用 nmap 掃描。
- 自動掃描僅針對本機 `127.0.0.1`。
- 預設保留 Android 原有 BatteryStats 統計，不主動重置。
- 所有 ADB 裝置操作明確指定目標端點。
- 不強制進入 Deep Doze，不修改 Android 原有 Doze 系統設定。
- 保留原始資料，避免只依賴 Python 摘要判斷。
- Android 或廠牌輸出格式不支援時，顯示警告，不將未知資料當成 0。

---

## 目錄結構

建議將可執行腳本存放於 Termux 內部私有目錄 `~/doze/`，利用 Android 應用程式沙盒保護；測試資料則存放於外部共享儲存空間。

```text
~/doze/
├── doze.sh
│   └── 主測試流程、ADB 偵測、測試前後快照及資料擷取
│
├── doze_summary-termux.py
│   └── BatteryStats、Doze、Alarm、Job、Wakelock、
│       CPU、電池及記憶體分析
│
└── adb.sh
    └── 獨立 ADB 無線除錯自動偵測及連線工具

~/storage/downloads/doze-test/
└── YYYYMMDD_HHMMSS/
    ├── timeline.txt
    ├── alarm_start_full.txt
    ├── battery_start.txt
    ├── battery_end.txt
    ├── mem_start.txt
    ├── mem_end.txt
    ├── deviceidle.txt
    ├── full.txt
    ├── checkin.txt
    ├── history.txt
    ├── home_end.txt
    └── summary-YYYYMMDD_HHMMSS.txt
```

若啟用 BatteryStats 重置功能，測試資料夾還會額外保存重置前的統計備份：

```text
batterystats_before_reset_full.txt
batterystats_before_reset_checkin.txt
batterystats_before_reset_history.txt
```

---

## 一、環境安裝與初始化

打開 Termux，依序執行以下指令。

### 1. 安裝必要套件

```bash
pkg update && pkg upgrade -y
pkg install -y android-tools python nmap coreutils
```

套件用途：

| 套件 | 用途 |
|---|---|
| `android-tools` | 提供 ADB 指令 |
| `python` | 執行 Python 摘要分析 |
| `nmap` | 掃描本機動態無線除錯 Port |
| `coreutils` | 提供 `timeout` 等常用工具 |

確認安裝：

```bash
adb version
python3 --version
nmap --version
timeout --version
```

Python 版本建議使用 3.8 或更新版本。

### 2. 授權外部儲存空間與建立腳本目錄

```bash
termux-setup-storage
mkdir -p ~/doze
```

執行 `termux-setup-storage` 後，依 Android 系統提示授予 Termux 儲存空間權限。

確認下載資料夾存在：

```bash
ls -ld ~/storage/downloads
```

### 3. 放入腳本及設定權限

將三份程式碼分別儲存為：

```text
~/doze/doze.sh
~/doze/doze_summary-termux.py
~/doze/adb.sh
```

設定權限：

```bash
chmod 700 ~/doze/doze.sh
chmod 700 ~/doze/adb.sh
chmod 600 ~/doze/doze_summary-termux.py
```

### 4. 建立全域快捷指令

```bash
ln -sf ~/doze/doze.sh "$PREFIX/bin/doze"
ln -sf ~/doze/adb.sh "$PREFIX/bin/adb-auto"
```

之後可以直接使用：

```bash
doze
```

或：

```bash
adb-auto
```

> **重要：** 請勿將 `adb.sh` 軟連結命名為 `adb`，否則可能覆蓋 Android-tools 原生 ADB 指令，造成遞迴呼叫錯誤。

---

## 二、疑難排解：ADB 指令被軟連結覆蓋

若曾執行：

```bash
ln -sf ~/doze/adb.sh "$PREFIX/bin/adb"
```

可能導致原生 ADB 被覆蓋。

復原方式：

1. 移除錯誤軟連結：

   ```bash
   rm -f "$PREFIX/bin/adb"
   ```

2. 重新安裝 Android-tools：

   ```bash
   pkg reinstall -y android-tools
   ```

3. 驗證：

   ```bash
   adb version
   ```

4. 重新建立正確快捷指令：

   ```bash
   ln -sf "$HOME/doze/adb.sh" "$PREFIX/bin/adb-auto"
   ```

---

## 三、透過 NMM File Manager 編輯內部目錄（選用）

若習慣使用圖形介面編輯 `~/doze/` 內的腳本，可透過 Android SAF 機制掛載：

1. 開啟 NMM File Manager。
2. 左上角選單 → 新增儲存空間／系統檔案選擇器（SAF）。
3. 在系統檔案選擇器左上角選單中，尋找 Termux。
4. 選擇 `doze` 資料夾。
5. 點擊「使用此資料夾」並允許存取。

編輯存檔時請注意：

- 編碼：UTF-8。
- 換行：LF。
- 不要使用 Windows CRLF。
- Shell 腳本第一行的 shebang 必須保留。

---

## 四、日常測試執行流程

### 1. 初次配對

每台裝置通常只需要完成一次配對，除非使用者重新配對或清除無線除錯配對資料。

1. 進入手機「設定 → 開發人員選項 → 無線除錯」。
2. 開啟無線除錯。
3. 點擊「使用配對碼配對裝置」。
4. 記下畫面顯示的配對 IP、配對 Port 及六位數配對碼。
5. 在 Termux 執行：

   ```bash
   adb pair 127.0.0.1:<配對Port>
   ```

6. 依提示輸入六位數配對碼。

> 配對 Port 與日常連線 Port 是兩個不同的 Port。配對完成後，日常連線應使用無線除錯主畫面顯示的 Port，而不是配對畫面顯示的 Port。

### 2. 執行 Doze 待機測試

確認：

- 手機已拔除充電線。
- 無線除錯已開啟。
- Termux 已授權共享儲存空間。
- 手機電量足夠。
- 測試期間不要主動使用手機。

執行：

```bash
doze
```

不帶參數時，腳本會：

1. 檢查目前已連線的本機 ADB 端點。
2. 若沒有已連線端點，才使用 nmap 掃描 `30000–65535`。
3. 對掃描結果逐一執行 ADB 連線驗證。
4. 若仍找不到，要求使用者輸入 Port。
5. 擷取測試前鬧鐘、電池及記憶體資料。
6. 啟用完整 wake history（若系統支援）。
7. 預設保留原有 BatteryStats，不重置。
8. 送出 `KEYCODE_SLEEP` 關閉螢幕。
9. 等待使用者手動結束測試。
10. 重新連線並擷取測試後資料。
11. 呼叫 Python 產生摘要。

手動指定 Port：

```bash
doze 39815
```

`39815` 僅為示範，請使用無線除錯主畫面顯示的實際連線 Port。

### 3. 測試時間建議

建議至少測試 30 分鐘；若要觀察較完整的 Deep Doze 行為，可以延長至 1–3 小時或更久。

實際是否進入 Deep Idle，仍受 Android 版本、廠牌省電政策、鬧鐘、Motion、網路及系統排程影響。

`KEYCODE_SLEEP` 只會送出關閉螢幕指令，不代表 Android 已立即進入 Deep Doze。

本工具不會執行：

```bash
dumpsys deviceidle force-idle
```

也不會主動修改 Android Doze 設定，以免破壞自然待機測試條件。

### 4. 結束測試

測試完成後：

1. 喚醒手機螢幕。
2. 回到 Termux。
3. 按下 Enter。
4. 等待 ADB 重新連線及資料擷取。
5. 查看 Python 摘要。

報告存放於：

```text
Download/doze-test/<日期_時間>/
```

### 5. 單獨測試 ADB 自動連線

```bash
adb-auto
```

手動指定 Port：

```bash
adb-auto 39815
```

---

## 五、BatteryStats 重置政策

### 預設不重置

新版 `doze.sh` 預設不執行：

```bash
dumpsys batterystats --reset
```

這是為了保留 Android 系統原有的累積統計，避免測試工具意外清除使用者既有資料。

### 需要重置時

只有在明確需要乾淨的統計起點時才執行：

```bash
doze --reset-batterystats
```

或：

```bash
doze 39815 --reset-batterystats
```

執行時會：

1. 先擷取重置前 BatteryStats 完整資料。
2. 保存 full、checkin 及 history 備份。
3. 顯示重置警告。
4. 要求使用者輸入 `RESET`。
5. 確認後才執行 `--reset`。

**注意：** BatteryStats 重置會清除系統既有的累積統計。雖然工具會先保存可取得的輸出，但這不等同完整備份 Android 內部所有統計狀態，也不保證可以還原。因此一般測試建議不重置。

---

# 六、核心腳本原始碼

## 1. `adb.sh`：獨立 ADB 無線除錯自動連線工具

功能：

- 優先使用已連線的 `127.0.0.1` ADB 端點。
- 沒有連線時使用 nmap 掃描本機高埠。
- 掃描加入逾時。
- 對每個候選 Port 進行 ADB 驗證。
- 支援手動指定 Port。
- 不使用不可靠的 `5555` 預設 Port。
- 加入 Port 數字及範圍檢查。
- 記錄連線日誌。
- 使用 `adb -s` 指定目標裝置。

```bash
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
        tee -a "$LOG_FILE"
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
```

---

## 2. `doze.sh`：Doze 自動化測試主程式

功能：

- 自動偵測 ADB Port。
- 優先使用既有連線。
- nmap 掃描加入逾時。
- 支援手動指定 Port。
- 測試前檢查 Alarm。
- 擷取 Battery、Memory 快照。
- 預設不重置 BatteryStats。
- 可選擇重置並先保存重置前資料。
- 保留 full-wake-history 功能。
- 送出 KEYCODE_SLEEP。
- 手動等待結束測試。
- 重新連線後擷取完整資料。
- 可選擇擷取 netstats。
- 呼叫 Python 摘要程式。

```bash
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
        tee -a "$OUT_DIR/timeline.txt"
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
```

---

## 3. `doze_summary-termux.py`：BatteryStats 與 Doze 摘要分析

功能：

- BatteryStats 電池使用時間與 CPU 清醒比例。
- Screen on、Discharge、Partial Wakelock。
- Device Idle 狀態時間軸。
- Deep Idle 進入事件。
- Alarm、Job、Wakeup AP。
- Kernel Wakelock。
- Charge Counter 放電曲線。
- 疑似突發耗電事件。
- CPU running 時間區間。
- Estimated power use。
- UID 與指定套件分析。
- deviceidle 狀態及參數。
- meminfo PSS、Private Dirty、Private Clean、RSS、Swap PSS。
- 電池 Charge Counter 與容量估算。
- 格式不支援或資料不足時顯示警告。

> 本分析程式只使用 Python 標準函式庫，不需要安裝額外 pip 套件。

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Termux Android Doze / BatteryStats 摘要工具

用法：

python3 doze_summary-termux.py full.txt \
  --checkin checkin.txt \
  --pkg ch.deletescape.lawnchair.plah \
  --deviceidle deviceidle.txt \
  --mem mem_start.txt mem_end.txt \
  --battery battery_start.txt battery_end.txt

只使用 Python 標準函式庫。

注意：
Android 不同版本與廠牌的 dumpsys 格式可能不同。
無法辨識的欄位會顯示警告，不會假裝成 0。
"""

import argparse
import collections
import datetime as dt
import os
import re
import sys


WELL_KNOWN = {
    0: "root/kernel",
    1000: "system",
    1001: "radio/phone",
    1020: "mdnsd",
    1051: "netd",
    2000: "shell(adbd)",
}

BURST_MINUTES = 6
BURST_MAH = 9.0
HIGH_DRAIN_MAH_H = 25.0


# ============================================================
# 基礎工具
# ============================================================

def read_text(path):
    if not path:
        return ""

    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return ""


def parse_dur(value):
    units = {
        "d": 86400000,
        "h": 3600000,
        "m": 60000,
        "s": 1000,
        "ms": 1,
    }

    total = 0

    for number, unit in re.findall(
        r"(\d+)\s*(ms|d|h|m|s)", value
    ):
        total += int(number) * units[unit]

    return total


def fmt(milliseconds):
    milliseconds = max(0, int(milliseconds))

    return (
        f"{milliseconds // 3600000}h"
        f"{milliseconds % 3600000 // 60000:02d}m"
        f"{milliseconds % 60000 // 1000:02d}s"
    )


def grab(text, pattern, group=1, flags=re.M):
    match = re.search(pattern, text, flags)

    return match.group(group).strip() if match else None


def section(text, header, limit=80):
    pos = text.find(header)

    if pos < 0:
        return []

    return text[pos:].splitlines()[1:limit + 1]


def unique(items):
    return list(dict.fromkeys(items))


# ============================================================
# UID / Checkin
# ============================================================

def load_uidmap(path):
    result = collections.defaultdict(list)

    if not path:
        return result

    for line in read_text(path).splitlines():
        fields = line.strip().split(",")

        if len(fields) < 6:
            continue

        if fields[2] == "i" and fields[3] == "uid":
            try:
                uid = int(fields[4])
                result[uid].append(fields[5])
            except ValueError:
                continue

    return result


def uid_to_int(value):
    if value.isdigit():
        return int(value)

    match = re.match(r"u(\d+)a(\d+)$", value)

    if match:
        return (
            int(match.group(1)) * 100000
            + 10000
            + int(match.group(2))
        )

    return None


def label(uid_string, uidmap):
    uid = uid_to_int(uid_string)

    if uid is None:
        return uid_string

    if uid < 10000:
        if uid in WELL_KNOWN:
            return f"{uid_string}({WELL_KNOWN[uid]})"

        return uid_string

    names = uidmap.get(uid)

    if names:
        return f"{uid_string}({names[0]})"

    return uid_string


def per_uid_blocks(lines):
    current = None
    result = collections.defaultdict(list)

    for line in lines:
        match = re.match(
            r"^  (u\d+[a-z]\d+|\d+):\s*$",
            line
        )

        if match:
            current = match.group(1)
            continue

        if current and line.startswith("    "):
            result[current].append(line.strip())

        elif current and line.startswith("  "):
            current = None

    return result


# ============================================================
# BatteryStats History
# ============================================================

def split_dump(lines):
    for index, line in enumerate(lines):
        if line.startswith("Statistics since last charge"):
            return lines[:index], lines[index:]

    return lines, []


def parse_history(lines):
    events = []
    unparsed = 0

    for line in lines:
        match = re.match(
            r"^\s+(\+[\dhdms]+|0)\s+\((\d+)\)\s+(\d{3})\s?(.*)$",
            line
        )

        if not match:
            if line.strip():
                unparsed += 1

            continue

        timestamp, _, level, rest = match.groups()

        elapsed = (
            0 if timestamp == "0"
            else parse_dur(timestamp)
        )

        events.append(
            (elapsed, int(level), rest)
        )

    events.sort(key=lambda item: item[0])

    return events, unparsed


def parse_idle(events):
    result = []

    for timestamp, _, rest in events:
        match = re.search(
            r"(?:^|\s)device_idle=([^\s]+)",
            rest
        )

        if match:
            result.append(
                (timestamp, match.group(1))
            )

    return result


def parse_alarm_events(events):
    result = []

    for timestamp, _, rest in events:
        if "+alarm" not in rest:
            continue

        match = re.search(
            r'\+alarm=(\S+?):"([^"]*)"',
            rest
        )

        if match:
            result.append(
                (timestamp, match.group(1), match.group(2))
            )

    return result


# ============================================================
# BatteryStats 統計
# ============================================================

def print_battery_stats(text, events):
    print("\n## 電池統計與 CPU 狀態")

    match = re.search(
        r"Time on battery:\s*(.*?)\s+\(([\d.]+)%\)\s+realtime,"
        r"\s*(.*?)\s+\(([\d.]+)%\)\s+uptime",
        text
    )

    if match:
        realtime, realtime_pct, uptime, uptime_pct = match.groups()

        print(f"- 電池使用時間：{realtime}")
        print(f"- CPU 清醒時間：{uptime}（{uptime_pct}%）")
        print(
            f"- CPU suspend 推算比例："
            f"{100 - float(uptime_pct):.1f}%"
        )

        if float(realtime_pct) < 99.5:
            print(
                f"- 注意：統計期間只有 {realtime_pct}% "
                "屬於電池供電時間。"
            )
    else:
        print(
            "- ⚠ 找不到 Time on battery，"
            "無法計算 CPU 清醒比例。"
        )

    fields = [
        ("Screen on", r"^\s+Screen on:\s*(.*)"),
        ("Discharge", r"^\s+Discharge:\s*(.*)"),
        (
            "Light doze discharge",
            r"Device light doze discharge:\s*(.*)"
        ),
        (
            "Deep doze discharge",
            r"Device deep doze discharge:\s*(.*)"
        ),
        (
            "Light idle",
            r"^\s+Device light idling:\s*(.*)"
        ),
        (
            "Deep idle",
            r"^\s+Device full idling:\s*(.*)"
        ),
        (
            "Partial wakelock",
            r"Total partial wakelock time:\s*(.*)"
        ),
        (
            "Wi-Fi kernel active",
            r"Wifi kernel active time:\s*(.*)"
        ),
        (
            "Wi-Fi received",
            r"Wifi data received:\s*(.*)"
        ),
        (
            "Wi-Fi sent",
            r"Wifi data sent:\s*(.*)"
        ),
    ]

    for name, pattern in fields:
        value = grab(text, pattern)
        print(f"- {name}：{value or '未知／未提供'}")

    screen_on = [
        t for t, _, rest in events
        if re.search(r"(^|\s)\+screen", rest)
    ]

    screen_off = [
        t for t, _, rest in events
        if re.search(r"(^|\s)-screen", rest)
    ]

    idle = parse_idle(events)

    for timestamp in screen_on:
        off = next(
            (t for t in screen_off if t > timestamp),
            None
        )

        duration = (
            (off - timestamp) / 1000
            if off is not None
            else None
        )

        if duration is not None and duration < 60:
            print(
                f"- ℹ 短暫亮屏：{fmt(timestamp)}，"
                f"約 {duration:.1f} 秒。"
            )
        else:
            print(
                f"- ⚠ 測試期間曾亮屏：{fmt(timestamp)}，"
                f"持續時間："
                f"{duration if duration is not None else '未知'} 秒。"
            )


# ============================================================
# Doze / Alarm / Job / Wakeup
# ============================================================

def print_doze(events, uidmap):
    print("\n## Doze 狀態與時間軸")

    idle = parse_idle(events)

    if not idle:
        print("- 沒有辨識到 device_idle 狀態事件。")
    else:
        print(
            "- device_idle 轉換：",
            ", ".join(
                f"{fmt(t)}={state}"
                for t, state in idle
            )
        )

        full = [
            t for t, state in idle
            if state == "full"
        ]

        if full:
            print(f"- 首次記錄 full：{fmt(full[0])}")

            if full[0] == 0:
                print(
                    "  ⚠ 統計起點已是 full，"
                    "不能確定本次測試何時進入。"
                )
        else:
            print("- 沒有記錄到 full（Deep Idle）事件。")

        totals = collections.Counter()

        for index, (timestamp, state) in enumerate(idle):
            if index + 1 >= len(idle):
                continue

            end = idle[index + 1][0]

            if end >= timestamp:
                totals[state] += end - timestamp

        if totals:
            print("- 可確認的狀態持續時間：")

            for state, duration in totals.items():
                print(f"  - {state}：{fmt(duration)}")

            print(
                "- 最後一個狀態若沒有退出事件，"
                "不會將未確認的尾端時間計入。"
            )

    alarms = parse_alarm_events(events)

    print("\n## Alarm / DeviceIdle 鬧鐘")

    deviceidle_alarms = [
        (t, name)
        for t, _, name in alarms
        if "DeviceIdleController" in name
    ]

    if deviceidle_alarms:
        for timestamp, name in deviceidle_alarms:
            print(f"- {fmt(timestamp)}：{name}")
    else:
        print("- 沒有辨識到 DeviceIdleController 鬧鐘。")

    progression = [
        t for t, name in deviceidle_alarms
        if "deep.progression" in name
    ]

    if progression:
        print(
            "- deep.progression：",
            ", ".join(fmt(t) for t in progression)
        )

    normal_alarms = [
        (t, uid, name)
        for t, uid, name in alarms
        if "DeviceIdle" not in name
    ]

    counter = collections.Counter(
        (uid, name[:55])
        for _, uid, name in normal_alarms
    )

    print("- 一般 Alarm 前 6 名：")

    for (uid, name), count in counter.most_common(6):
        print(
            f"  - {label(uid, uidmap)}：{name} × {count}"
        )

    print("\n## Job / 網路活動")

    jobs = collections.Counter()
    cellular = 0

    for _, _, rest in events:
        for match in re.finditer(
            r"\+job=(\S+?):",
            rest
        ):
            jobs[label(match.group(1), uidmap)] += 1

        if "cellular_high_tx_power" in rest:
            cellular += 1

    for name, count in jobs.most_common(10):
        print(f"- Job {name}：{count} 次")

    print(
        f"- cellular_high_tx_power 事件：{cellular} 次"
    )

    print("\n## Wakeup AP")

    wakeups = collections.Counter()

    for _, _, rest in events:
        for match in re.finditer(
            r"wakeupap=(\S+?):",
            rest
        ):
            wakeups[match.group(1)] += 1

    if wakeups:
        for uid, count in wakeups.most_common(8):
            print(
                f"- {label(uid, uidmap)}：{count} 次"
            )
    else:
        print("- 沒有辨識到 wakeupap。")


# ============================================================
# Kernel Wakelock
# ============================================================

def print_wakelocks(text):
    print("\n## Kernel Wakelock")

    rows = []

    for line in text.splitlines():
        match = re.match(
            r"^\s+Kernel Wake lock (\S+): (.*?) \((\d+) times\)",
            line
        )

        if match:
            name, duration, count = match.groups()

            rows.append(
                (
                    parse_dur(duration),
                    name,
                    duration,
                    count
                )
            )

    rows.sort(reverse=True)

    if not rows:
        print("- 沒有辨識到 Kernel Wakelock 資料。")
    else:
        for _, name, duration, count in rows[:8]:
            print(
                f"- {name}：{duration}（{count} 次）"
            )

    wake_reasons = [
        line.strip()
        for line in text.splitlines()
        if line.startswith("  Wakeup reason")
    ]

    print("\n## Wakeup reason")

    if wake_reasons:
        for line in wake_reasons[:8]:
            print("-", line[:180])
    else:
        print("- 沒有辨識到 Wakeup reason。")


# ============================================================
# Charge Counter 放電分析
# ============================================================

def print_discharge(events, uidmap):
    print("\n## 放電曲線（BatteryStats history charge）")

    points = []

    for timestamp, level, rest in events:
        match = re.search(
            r"(?:^|\s)charge=(\d+)",
            rest
        )

        if match:
            points.append(
                (timestamp, int(match.group(1)))
            )

    levels = []

    for timestamp, level, _ in events:
        if not levels or levels[-1][1] != level:
            levels.append((timestamp, level))

    print(
        "- 電量百分比變化：",
        ", ".join(
            f"{fmt(t)} → {level}%"
            for t, level in levels
        ) or "(無)"
    )

    if len(points) < 2:
        print(
            "- ⚠ charge 資料不足，"
            "無法建立放電曲線。"
        )
        return

    segments = []
    base = points[0]

    for index, point in enumerate(points[1:], start=1):
        elapsed = point[0] - base[0]

        if elapsed >= 1800000 or index == len(points) - 1:
            hours = elapsed / 3600000

            if hours > 0:
                delta = base[1] - point[1]

                if delta >= 0:
                    rate = delta / hours

                    segments.append(
                        (
                            base[0],
                            point[0],
                            delta,
                            rate
                        )
                    )

            base = point

    for start, end, delta, rate in segments:
        flag = (
            "（疑似偏高）"
            if rate > HIGH_DRAIN_MAH_H
            else ""
        )

        print(
            f"- {fmt(start)}–{fmt(end)}："
            f"{delta:.1f} mAh，"
            f"{rate:.1f} mAh/h {flag}"
        )

    print(
        f"- 疑似突發耗電門檻："
        f"{BURST_MINUTES} 分鐘內至少 "
        f"{BURST_MAH:.0f} mAh。"
    )

    bursts = []

    for index in range(len(points)):
        best = None

        for other in range(index + 1, len(points)):
            elapsed = (
                points[other][0] - points[index][0]
            )

            if elapsed > BURST_MINUTES * 60000:
                break

            delta = (
                points[index][1] - points[other][1]
            )

            if delta >= BURST_MAH:
                best = other

        if best is not None:
            bursts.append(
                (
                    points[index][0],
                    points[best][0],
                    points[index][1] - points[best][1]
                )
            )

    if not bursts:
        print("- 沒有符合門檻的突發耗電事件。")
        return

    for start, end, delta in bursts:
        lo = start - 60000
        hi = end + 60000

        idle = [
            f"{fmt(t)}={state}"
            for t, state in parse_idle(events)
            if lo <= t <= hi
        ]

        jobs = collections.Counter()

        for timestamp, _, rest in events:
            if lo <= timestamp <= hi:
                for match in re.finditer(
                    r"\+job=(\S+?):",
                    rest
                ):
                    jobs[label(match.group(1), uidmap)] += 1

        print(
            f"- 疑似突發耗電：{fmt(start)}–{fmt(end)}，"
            f"{delta:.1f} mAh"
        )

        print(
            "  同時段 Doze 狀態：",
            ", ".join(idle) or "(無)"
        )

        print(
            "  同時段 Job：",
            ", ".join(
                f"{name} × {count}"
                for name, count in jobs.most_common(4)
            ) or "(無)"
        )

        print(
            "  注意：這是時間上的關聯，"
            "不能直接認定耗電原因。"
        )


# ============================================================
# CPU running
# ============================================================

def print_cpu_running(events):
    print("\n## CPU running（每 30 分鐘）")

    if not events:
        print("- 沒有 History 事件。")
        return

    run = None
    last = None
    buckets = collections.Counter()

    for timestamp, _, rest in events:
        if last is not None and run is True:
            position = last

            while position < timestamp:
                end = min(
                    timestamp,
                    (position // 1800000 + 1) * 1800000
                )

                buckets[int(position // 1800000)] += (
                    end - position
                )

                position = end

        if re.search(r"(^|\s)\+running", rest):
            run = True

        if re.search(r"(^|\s)-running", rest):
            run = False

        last = timestamp

    if run is True:
        print(
            "- ⚠ History 結束時 CPU 仍為 running，"
            "未計入最後事件之後的時間。"
        )

    if run is None:
        print(
            "- ⚠ 無法確認 running 狀態，"
            "以下結果只代表可辨識的區間。"
        )

    hot = [
        (bucket, duration)
        for bucket, duration in sorted(buckets.items())
        if duration / 1800000 > 0.5
    ]

    if not hot:
        print("- 沒有可辨識的清醒時間超過 50% 區段。")
        return

    for bucket, duration in hot:
        print(
            f"- {fmt(bucket * 1800000)}："
            f"{duration / 1800000 * 100:.0f}%"
        )


# ============================================================
# Estimated power use / UID
# ============================================================

def print_power(text, uidmap, args):
    print("\n## 估算耗電（Estimated power use）")

    print(
        "注意：這是 Android 模型估算值，"
        "不等同實際電池放電量。"
    )

    lines = section(
        text,
        "Estimated power use (mAh):",
        80
    )

    for line in lines[:12]:
        if line.strip():
            print("-", line.strip()[:180])

    uid_rows = []

    for line in lines:
        match = re.match(
            r"^\s+[Uu][Ii][Dd] (\S+): ([\d.]+)",
            line
        )

        if match:
            uid_rows.append(
                (
                    float(match.group(2)),
                    match.group(1)
                )
            )

    uid_rows.sort(reverse=True)

    print("- UID 耗電前 8 名：")

    for value, uid in uid_rows[:8]:
        print(
            f"  - {label(uid, uidmap)}："
            f"{value:.2f} mAh"
        )

    wanted = [
        item.strip()
        for item in args.uids.split(",")
        if item.strip()
    ]

    if args.pkg:
        reverse = collections.defaultdict(list)

        for uid, names in uidmap.items():
            for name in names:
                reverse[name].append(uid)

        for package in args.pkg.split(","):
            package = package.strip()

            if not package:
                continue

            matches = reverse.get(package)

            if not matches:
                print(
                    f"- 找不到套件 {package} 的 UID，"
                    "請確認 checkin.txt 有 UID mapping。"
                )
                continue

            uid = matches[0]

            user, app = divmod(uid, 100000)

            if app >= 10000:
                wanted.append(
                    f"u{user}a{app - 10000}"
                )
            else:
                wanted.append(str(uid))

    if wanted:
        print("\n## 指定 UID / 套件")

        blocks = per_uid_blocks(text.splitlines())

        for uid in unique(wanted):
            row = next(
                (
                    value
                    for value, key in uid_rows
                    if key == uid
                ),
                None
            )

            if row is not None:
                print(
                    f"- {label(uid, uidmap)}："
                    f"{row:.2f} mAh"
                )
            else:
                print(
                    f"- {label(uid, uidmap)}："
                    "沒有可辨識的估算耗電資料"
                )

            shown = 0

            for line in blocks.get(uid, []):
                if re.search(
                    r"(Top for|Fg Service|Foreground|"
                    r"Total cpu time: u=|Wake lock|Job |"
                    r"Wi-Fi network|Background for|Cached)",
                    line,
                    re.I
                ):
                    print("   ", line[:160])

                    shown += 1

                    if shown >= 8:
                        break


# ============================================================
# deviceidle
# ============================================================

def print_deviceidle(path):
    if not path:
        return

    text = read_text(path)

    print("\n## deviceidle 摘錄")

    if not text:
        print("- 檔案不存在或內容為空。")
        return

    for key in [
        "inactive_to",
        "idle_after_inactive_to",
        "min_time_to_alarm",
        "idle_to",
        "max_idle_to",
    ]:
        print(
            f"- {key}：",
            grab(
                text,
                r"^\s*" + re.escape(key) + r"=(\S+)"
            )
        )

    for key in [
        "mState",
        "mLightState",
        "mNextAlarmTime",
        "mNextIdleDelay",
        "mCharging",
        "mScreenOn",
    ]:
        print(
            f"- {key}：",
            grab(
                text,
                r"(?:^|\s)" + re.escape(key) + r"=(\S+)"
            )
        )

    position = text.find("Idling history:")

    if position >= 0:
        history = text[position:].splitlines()[1:]

        rows = [
            line.strip()
            for line in history
            if re.match(
                r"^\s+(normal|light|deep)",
                line
            )
        ]

        print(
            "- Idling history 最後 10 筆：",
            " | ".join(rows[-10:]) or "(無)"
        )
    else:
        print("- 沒有辨識到 Idling history。")


# ============================================================
# meminfo
# ============================================================

def parse_mem_block(text):
    result = {}

    process = re.search(
        r"\*\* MEMINFO in pid (\d+) \[(.+?)\]",
        text
    )

    result["proc"] = (
        process.group(2)
        if process
        else "?"
    )

    lines = text.splitlines()

    total_index = None

    for index, line in enumerate(lines):
        if re.match(r"^\s*TOTAL(?:\s|$)", line):
            total_index = index
            break

    if total_index is None:
        result["error"] = "找不到 TOTAL 欄位。"
        return result

    # Android meminfo 表格通常以表頭列描述欄位。
    # 不同版本可能在表頭前有其他欄位，因此只在
    # 可明確對應時採用；無法對應時不猜測欄位順序。

    header = lines[total_index - 1] if total_index > 0 else ""

    header_tokens = re.findall(
        r"[A-Za-z][A-Za-z0-9_/-]*",
        header
    )

    total_line = lines[total_index]

    values = re.findall(
        r"\d+",
        total_line
    )

    if not header_tokens or len(header_tokens) != len(values):
        result["error"] = (
            "TOTAL 欄位與表頭無法可靠對應；"
            "此 Android 版本可能使用不同 meminfo 格式。"
        )
        return result

    mapping = {
        name.lower(): int(value)
        for name, value in zip(header_tokens, values)
    }

    aliases = {
        "pss": ("pss",),
        "pdirty": ("private_dirty", "privatedirty"),
        "pclean": ("private_clean", "privateclean"),
        "rss": ("rss",),
        "swap": ("swappss", "swap_pss"),
    }

    for key, names in aliases.items():
        for name in names:
            if name in mapping:
                result[key] = mapping[name]
                break

    if not all(
        key in result
        for key in ("pss", "pdirty", "pclean", "rss")
    ):
        result["error"] = (
            "表頭未包含可辨識的 PSS、Private Dirty、"
            "Private Clean 或 RSS 欄位。"
        )

    for title, key in [
        ("Java Heap", "java"),
        ("Native Heap", "native"),
        ("Graphics", "gfx"),
        ("System", "system"),
    ]:
        match = re.search(
            r"^\s*" + re.escape(title) + r":\s+(\d+)",
            text,
            re.M
        )

        if match:
            result[key] = int(match.group(1))

    return result


def parse_stamp(path):
    text = read_text(path)

    match = re.search(
        r"# captured: (\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)",
        text
    )

    if match:
        try:
            return dt.datetime.strptime(
                match.group(1),
                "%Y-%m-%d %H:%M:%S"
            )
        except ValueError:
            pass

    match = re.search(
        r"(\d{8})_(\d{6})",
        path
    )

    if match:
        try:
            return dt.datetime.strptime(
                match.group(1) + match.group(2),
                "%Y%m%d%H%M%S"
            )
        except ValueError:
            pass

    return None


def print_meminfo(paths):
    print("\n## 記憶體（dumpsys meminfo，單位 MB）")

    rows = []

    for path in paths:
        text = read_text(path)

        if not text:
            print(
                f"- ⚠ {path}：檔案不存在或為空。"
            )
            continue

        for block in re.split(
            r"(?=\*\* MEMINFO in pid)",
            text
        ):
            if not block.startswith("** MEMINFO in pid"):
                continue

            data = parse_mem_block(block)
            data["path"] = path
            data["stamp"] = parse_stamp(path)

            rows.append(data)

    if not rows:
        print("- 沒有可分析的 meminfo 區塊。")
        return

    for data in rows:
        if data.get("error"):
            print(
                f"- ⚠ {data['path']} ({data['proc']})："
                f"{data['error']}"
            )
            continue

        stamp = data["stamp"]

        when = (
            stamp.strftime("%m-%d %H:%M:%S")
            if stamp
            else data["path"]
        )

        mb = lambda value: f"{value / 1024:.1f} MB"

        private = (
            data["pdirty"] + data["pclean"]
        )

        print(
            f"- [{when}] {data['proc']}："
            f"PSS {mb(data['pss'])}，"
            f"Private {mb(private)}，"
            f"RSS {mb(data['rss'])}，"
            f"Swap PSS {mb(data.get('swap', 0))}"
        )

        print(
            "- 注意：PSS 包含按比例分攤的共用記憶體；"
            "不同 App 比較時，建議同時觀察 Private Dirty + Clean。"
        )


# ============================================================
# 電池快照
# ============================================================

def print_battery(paths):
    print("\n## 電池快照（dumpsys battery）")

    points = []

    for path in paths:
        text = read_text(path)

        level = grab(
            text,
            r"^\s*level:\s*(\d+)"
        )

        counter = grab(
            text,
            r"^\s*Charge counter:\s*(\d+)"
        )

        if level is None or counter is None:
            print(
                f"- ⚠ {path}：找不到 level 或 Charge counter。"
            )
            continue

        level = int(level)
        counter = int(counter)

        if level <= 0 or counter <= 0:
            print(
                f"- ⚠ {path}：電量或 Charge counter 不合理，"
                "不納入容量估算。"
            )
            continue

        timestamp = parse_stamp(path)

        # Android 常見 Charge counter 單位為 μAh。
        # 若 OEM 使用不同單位，需以實際裝置輸出確認。
        mah = counter / 1000.0

        per_percent = mah / level

        when = (
            timestamp.strftime("%m-%d %H:%M:%S")
            if timestamp
            else path
        )

        print(
            f"- [{when}] level {level}% / "
            f"Charge counter {mah:.1f} mAh"
        )

        print(
            f"  每 1% 約 {per_percent:.1f} mAh，"
            f"推算滿電容量約 {per_percent * 100:.0f} mAh"
        )

        points.append(
            (timestamp, level, mah)
        )

    if len(points) >= 2:
        first = points[0]
        last = points[-1]

        if first[0] and last[0]:
            hours = (
                last[0] - first[0]
            ).total_seconds() / 3600

            delta = first[2] - last[2]

            if hours > 0 and delta >= 0:
                print(
                    f"- 區間放電：{delta:.1f} mAh / "
                    f"{hours:.2f} 小時 = "
                    f"{delta / hours:.1f} mAh/h"
                )

            elif delta < 0:
                print(
                    "- ⚠ Charge counter 增加，"
                    "可能有充電、計數器重置或讀值波動，"
                    "不計算放電速率。"
                )


# ============================================================
# 主程式
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="Android Doze / BatteryStats 摘要工具"
    )

    parser.add_argument(
        "full",
        help="dumpsys batterystats 完整輸出"
    )

    parser.add_argument("--uids", default="")
    parser.add_argument("--pkg", default="")
    parser.add_argument("--checkin")
    parser.add_argument("--deviceidle")
    parser.add_argument("--mem", nargs="+")
    parser.add_argument("--battery", nargs="+")

    args = parser.parse_args()

    if not os.path.isfile(args.full):
        print(
            f"錯誤：找不到檔案 {args.full}",
            file=sys.stderr
        )
        return 2

    full_text = read_text(args.full)

    if not full_text:
        print(
            "錯誤：BatteryStats 檔案為空。",
            file=sys.stderr
        )
        return 2

    lines = full_text.splitlines()

    history_lines, stats_lines = split_dump(lines)

    stats_text = "\n".join(stats_lines)

    events, unparsed = parse_history(history_lines)

    uidmap = load_uidmap(args.checkin)

    print("# Android Doze / BatteryStats 摘要")

    print(f"- 原始檔案：{args.full}")
    print(f"- History 行數：{len(history_lines)}")
    print(f"- 成功解析事件：{len(events)}")
    print(f"- 未辨識 History 行：{unparsed}")

    if not events:
        print(
            "- ⚠ 沒有成功解析 History 事件。"
            "可能是 Android 版本或 OEM 格式不同。"
        )

    elif unparsed > len(events):
        print(
            "- ⚠ 未辨識行數偏高，"
            "時間軸結果可能不完整。"
        )

    start_dt = grab(
        stats_text,
        r"Start clock time:\s*(\S+)"
    )

    print(
        "- 統計起點：",
        start_dt or "未知"
    )

    print_battery_stats(
        stats_text,
        events
    )

    print_doze(
        events,
        uidmap
    )

    print_wakelocks(
        stats_text
    )

    print_discharge(
        events,
        uidmap
    )

    print_cpu_running(
        events
    )

    print_power(
        stats_text,
        uidmap,
        args
    )

    print_deviceidle(
        args.deviceidle
    )

    if args.mem:
        print_meminfo(args.mem)

    if args.battery:
        print_battery(args.battery)

    print("\n## 資料品質提醒")

    print(
        "- 本摘要只分析目前能辨識的 dumpsys 欄位。"
    )

    print(
        "- 沒有事件不代表系統沒有發生該事件。"
    )

    print(
        "- BatteryStats 模型耗電值不等同實際電池放電量。"
    )

    print(
        "- device_idle=full 代表記錄到 full 狀態，"
        "不代表整段測試都處於 Deep Idle。"
    )

    print(
        "- 疑似突發耗電只表示時間關聯，"
        "不能單憑此結果判定是哪個 App 或服務造成。"
    )

    print(
        "- 請保留 full.txt、checkin.txt、history.txt "
        "等原始資料供進一步核對。"
    )

    print("\n摘要分析完成。")

    return 0


if __name__ == "__main__":
    sys.exit(main())
```

---

## 七、修改內容與原版差異

| 項目 | 原版 | 整合修正版 |
|---|---|---|
| ADB Port | 預設 41077／5555 | 優先既有連線，必要時掃描，失敗要求手動輸入 |
| nmap | 全高埠掃描 | 保留掃描，加入逾時 |
| ADB 裝置選擇 | 部分指令未指定目標 | 使用 `adb -s "$ADB_ADDR"` |
| Port 驗證 | 未完整驗證 | 限制 1–65535 |
| BatteryStats | 直接重置 | 預設不重置 |
| 重置前備份 | 無 | 重置前保存可取得的 full、checkin、history |
| 重置確認 | 無 | 必須輸入 `RESET` |
| 輸出資料夾 | 精確到分鐘 | 精確到秒 |
| Termux 儲存空間 | 未檢查 | 啟動時檢查 |
| 錯誤處理 | `set -e` 可能提前退出 | 擷取失敗會留下錯誤紀錄 |
| Python 路徑 | 固定 `${HOME}/doze` | 依腳本所在目錄定位 |
| meminfo | 固定欄位假設 | 嘗試依表頭對應，不可靠時警告 |
| CPU running | 可能漏算起始及結束區間 | 對無法確認的區間顯示警告 |
| Doze 判斷 | 容易把事件當成整段狀態 | 顯示轉換及可確認區間 |
| 突發耗電 | 直接列出門檻 | 明確標示為疑似事件，不直接歸因 |

---

## 八、相容性與重要注意事項

### 1. Android 版本及廠牌差異

`dumpsys batterystats`、`dumpsys deviceidle` 及 `dumpsys meminfo` 並不是完全固定的資料格式。

Android 版本、廠牌及系統修改可能影響：

- History 時間格式。
- Alarm 輸出格式。
- UID 對應方式。
- Kernel Wakelock 名稱。
- DeviceIdle 狀態欄位。
- meminfo 表格欄位。

因此，若 Python 顯示解析警告，應先保留原始檔案，再針對實際裝置格式修正，不應直接將未知值視為 0。

### 2. Charge Counter

程式將常見 Android `Charge counter` 的 μAh 數值除以 1000，轉換成 mAh。

但不同裝置可能不提供該欄位，或使用不同計數器定義。

所以：

- Charge Counter 不存在時，無法計算該項數據。
- Charge Counter 增加時，不應直接判定電池放電。
- 以 Charge Counter 推算容量只能作為估算。
- BSOH 並非所有 Android 裝置都會提供。

### 3. full-wake-history

程式保留：

```bash
dumpsys batterystats --enable full-wake-history
```

此功能可能增加 BatteryStats 記錄量。

不同 Android 版本對此功能的支援程度不同。測試結束後若要恢復原設定，應先確認該裝置支援的停用方式，不要假設所有裝置都有相同指令。

### 4. 無線除錯 Port

Android Wireless Debugging 的連線 Port 通常是動態的。

配對 Port 與日常連線 Port 不同，因此：

- 配對時使用配對畫面顯示的 Port。
- 日常連線使用無線除錯主畫面顯示的 Port。
- Port 變動時，應重新偵測或手動指定。
- 不應把傳統 ADB TCP/IP 的 5555 當成 Wireless Debugging 的固定預設值。

### 5. Deep Doze

本工具不會強制進入 Deep Doze。

實際能否進入 Deep Idle，仍受以下條件影響：

- 螢幕是否關閉。
- 手機是否處於靜止狀態。
- 是否正在充電。
- 是否有喚醒鬧鐘。
- Android 版本及廠牌省電政策。
- 系統是否有其他活動或排程。

`device_idle=full` 是一個狀態事件，不代表整段測試都處於 Deep Idle。

### 6. BatteryStats 重置

預設不重置。

若啟用重置功能，雖然會先保存可取得的原始輸出，但仍不能保證完整還原 Android 內部統計。

一般測試建議使用預設模式。

---

## 九、第一次使用的驗證清單

建議先進行 5–10 分鐘的短時間測試，再進行正式長時間測試。

### ADB

- [ ] `adb version` 正常。
- [ ] `adb-auto` 能偵測已連線端點。
- [ ] 自動偵測失敗時會要求輸入 Port。
- [ ] 指定 Port 後能成功連線。
- [ ] `adb devices` 顯示目標端點為 `device`。

### Doze

- [ ] `doze` 能建立獨立測試資料夾。
- [ ] `alarm_start_full.txt` 有內容。
- [ ] `battery_start.txt` 有內容。
- [ ] `mem_start.txt` 有內容。
- [ ] 預設不執行 BatteryStats reset。
- [ ] 手動結束後能重新連線。
- [ ] `deviceidle.txt` 有內容。
- [ ] `full.txt` 有內容。
- [ ] `checkin.txt` 有內容。
- [ ] `history.txt` 有內容。

### Python

- [ ] Python 可以正常啟動。
- [ ] 能產生摘要檔案。
- [ ] 沒有未處理的例外。
- [ ] 若格式不支援，能顯示警告。
- [ ] 原始資料仍然完整保存。

---

## 十、重新分析既有測試資料

若已經完成測試，不需要重新執行 Doze。

可直接指定既有資料夾：

```bash
python3 ~/doze/doze_summary-termux.py \
  ~/storage/downloads/doze-test/測試資料夾/full.txt \
  --checkin ~/storage/downloads/doze-test/測試資料夾/checkin.txt \
  --pkg ch.deletescape.lawnchair.plah \
  --deviceidle ~/storage/downloads/doze-test/測試資料夾/deviceidle.txt \
  --mem \
    ~/storage/downloads/doze-test/測試資料夾/mem_start.txt \
    ~/storage/downloads/doze-test/測試資料夾/mem_end.txt \
  --battery \
    ~/storage/downloads/doze-test/測試資料夾/battery_start.txt \
    ~/storage/downloads/doze-test/測試資料夾/battery_end.txt
```

若要保存重新分析結果：

```bash
python3 ~/doze/doze_summary-termux.py \
  ~/storage/downloads/doze-test/測試資料夾/full.txt \
  --checkin ~/storage/downloads/doze-test/測試資料夾/checkin.txt \
  --deviceidle ~/storage/downloads/doze-test/測試資料夾/deviceidle.txt \
  > ~/storage/downloads/doze-test/測試資料夾/summary-recheck.txt
```

---

## 十一、目前功能範圍與後續可擴充方向

目前版本以保留原始資料、穩定擷取及保守分析為優先。

後續可以再增加：

1. **Alarm 時間解析強化：** 針對不同 Android／OEM 的 `dumpsys alarm` 格式建立多種解析器。
2. **History 格式辨識：** 支援更多 Android BatteryStats History 格式，並統計各類事件解析成功率。
3. **meminfo 動態欄位解析：** 根據不同 Android 版本的表格結構辨識欄位。
4. **測試品質報告：** 顯示 ADB 是否成功、BatteryStats 是否完整、History 是否可解析、是否有 Deep Idle 事件、是否曾亮屏。
5. **多次測試比較：** 比較不同測試日期的 mAh/h、CPU 清醒比例、Wakelock 及 Deep Idle 時間。
6. **指定套件深入分析：** 針對 Lawnchair 及其他指定 App 比較 CPU、Job、Alarm、Wakelock 和記憶體變化。
7. **測試前後狀態比對：** 將電池、記憶體、DeviceIdle 與 BatteryStats 的時間區間整合。

---

## 十二、使用聲明

本工具是 Android 系統資料的擷取與分析輔助工具，不會直接修改 Android 的省電政策，也不會保證手機一定進入 Deep Doze。

分析結果受到 Android 版本、廠牌輸出格式、電池計數器精度、系統排程及測試環境影響。

請保留原始 `full.txt`、`checkin.txt`、`history.txt`、`deviceidle.txt` 等檔案。摘要報告只作為分析參考，不應取代原始資料。

**建議正式長時間測試前，先完成短時間測試及原始資料檢查。**

