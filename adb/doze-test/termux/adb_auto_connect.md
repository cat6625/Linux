# 自動連接 ADB 腳本 + 安裝/設定說明

## 1️⃣ 前置作業：安裝必要套件
在 Termux 中執行以下指令即可取得腳本執行所需的工具（`adb`、`nmap`、`coreutils` 等）：

```bash
# 安裝 ADB、nmap 以及基本工具
pkg update && pkg upgrade -y
pkg install -y adb nmap coreutils
```

> **說明**  
> - `adb` 為 Android Debug Bridge 本體。  
> - `nmap` 用於掃描本機端口，若不想安裝也可以省略自動偵測步驟，腳本會直接使用預設埠號。  
> - `coreutils` 提供 `date`、`cut`、`awk` 等常用指令，已在大多數 Termux 環境中預裝。

---

## 2️⃣ 複製腳本至 `$HOME/doze/adb.sh`


# 建立目錄（若已存在可跳過）
```bash
mkdir -p "$HOME/doze"
```
# 將下面完整腳本寫入 $HOME/doze/adb.sh
```bash
cat > "$HOME/doze/adb.sh" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

# -------------------------------------------------
# 參數說明
#   $1 (optional)  手動指定的 ADB port
# -------------------------------------------------

# ------------- 設定項目 -------------
DEFAULT_PORT=5555          # 無法偵測時的備用埠號
MAX_RETRIES=5              # 連線失敗的最大重試次數
RETRY_INTERVAL=2           # 重試間隔（秒）
LOG_FILE="${HOME}/adb_auto_connect.log"
# -----------------------------------

# -------------- 日誌函式 --------------
log() {
    local level="$1"
    local msg="$2"
    local ts
    ts=$(date +"%Y-%m-%d %H:%M:%S")
    echo "[$ts] [$level] $msg" | tee -a "$LOG_FILE"
}
# ---------------------------------------

# ---------- 自動偵測 / 決定 Port ----------
detect_adb_port() {
    local connected
    # 1. 先看已有的無線除錯連線
    connected=$(adb devices 2>/dev/null |
        awk '/^127\.0\.0\.1:[0-9]+[[:space:]]+device$/ {print $1}' |
        cut -d: -f2 |
        head -n1 || true)

    if [ -n "$connected" ]; then
        echo "$connected"
        return 0
    fi

    # 2. 若有 nmap，掃描常見的 30000~49999 範圍
    if command -v nmap >/dev/null 2>&1; then
        local scanned
        scanned=$(nmap -T4 -p 30000-49999 127.0.0.1 2>/dev/null |
            awk '/^[0-9]+\/tcp[[:space:]]+open/ {print $1}' |
            cut -d/ -f1 |
            head -n1 || true)

        if [ -n "$scanned" ]; then
            echo "$scanned"
            return 0
        fi
    fi

    return 1
}
# -----------------------------------------

# ---------- 取得 Port ----------
if [ -n "${1:-}" ]; then
    PORT="$1"
    log INFO "使用手動指定的 Port：$PORT"
else
    log INFO "未指定 Port，正在自動偵測無線除錯端點..."
    if PORT=$(detect_adb_port); then
        log INFO "自動偵測成功：$PORT"
    else
        PORT="$DEFAULT_PORT"
        log WARN "無法自動偵測（建議執行 pkg install nmap），改用預設 Port：$PORT"
    fi
fi
# --------------------------------

ADB_ADDR="127.0.0.1:${PORT}"

# ---------- 連線函式 ----------
adb_connect() {
    local attempt=1
    while (( attempt <= MAX_RETRIES )); do
        log INFO "嘗試連線 ADB (${ADB_ADDR})，第 $attempt 次..."
        if adb connect "$ADB_ADDR" >/dev/null 2>&1; then
            # 確認已列出為 device
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
# --------------------------------

# ---------- 斷線函式 ----------
adb_disconnect() {
    if adb disconnect "$ADB_ADDR" >/dev/null 2>&1; then
        log INFO "已斷開與 $ADB_ADDR 的連線"
    else
        log WARN "斷開連線失敗或本身未連線"
    fi
}
# --------------------------------

# ---------- 主流程 ----------
log INFO "=== ADB 自動連接腳本啟動 ==="
if adb_connect; then
    # 範例：取得裝置型號
    log INFO "執行示例指令：adb shell getprop ro.product.model"
    adb shell getprop ro.product.model | tee -a "$LOG_FILE"
else
    log ERROR "連線失敗，腳本即將結束"
    exit 1
fi

# 若想結束後自動斷開，可取消註解下行
# adb_disconnect

log INFO "=== 腳本執行完畢 ==="
EOF
```

---

## 3️⃣ 設定執行權限與建立符號鏈結

```bash
# 讓腳本可執行
chmod +x "$HOME/doze/adb.sh"

# 在 $PREFIX/bin（Termux 的 PATH）內建立全域指令
ln -sf "$HOME/doze/adb.sh" "$PREFIX/bin/adb"
```

> 現在只要在 Termux 中輸入 `adb`（或 `adb <port>`）即可執行上述自動偵測與連線流程。

---

## 4️⃣ 使用方式

```bash
# 使用自動偵測（推薦）
adb

# 若已知埠號，直接帶入
adb 5555
```

執行後會在 `~/adb_auto_connect.log` 中留下時間戳記與操作紀錄，方便排錯。

---

## 5️⃣ 可能的改進點（供參考）

| 項目 | 為何值得改進 | 建議方向 |
|------|--------------|----------|
| **斷線自動化** | 有時需要在腳本結束後保證斷開，以免佔用資源 | 解除註解 `adb_disconnect` 或在腳本最後加入條件判斷 |
| **語系支援** | 目前所有訊息皆為中文，若在多語系環境使用可能不易閱讀 | 使用環境變數或 `gettext` 方式切換語系 |
| **自訂掃描範圍** | 有些裝置使用不同的 ADB 端口（如 8000） | 把 `30000-49999` 改為可由參數或環境變數設定 |
| **平行偵測** | 若同時有多台裝置，`detect_adb_port` 只回傳第一個 | 改寫成回傳陣列，讓使用者自行選擇 |

如果上述內容有任何不符合您需求的地方，請告訴我，我會再調整。祝使用順利！
