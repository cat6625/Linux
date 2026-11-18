# Termux Android Doze & ADB 自動化測試工具組

本專案提供一套運行於 **Termux（無需 Root）** 的自動化測試工具，透過本機無線除錯（Wireless Debugging）自動掃描連接埠、收集系統 `batterystats` / `deviceidle` / `meminfo` / `battery` 數據，並濃縮產出易於判讀的待機耗電與深度睡眠分析報告。

---

## 目錄結構

建議將可執行腳本存放於 Termux 內部私有目錄（`~/doze/`）以受 Android 沙盒保護，僅將產出的測試報告存放於外部儲存空間（`Download/doze-test/`）：

```text
~/doze/
├── doze.sh                  # 主測試流程腳本（含全高埠自動偵測與快照抓取）
├── doze_summary-termux.py   # 通用版 batterystats 摘要分析腳本
└── adb.sh                   # 獨立 ADB 無線除錯自動掃描連線工具

~/storage/downloads/doze-test/
└── YYYYMMDD_HHMM/           # 每次測試產生的原始數據與 summary 報告
```

---

## 一、 環境安裝與初始化

打開 Termux，依序執行以下指令完成環境建置：

### 1. 安裝必要套件
```bash
pkg update && pkg upgrade -y
pkg install -y android-tools python nmap coreutils
```
* **`android-tools`**：提供 `adb` 指令工具。
* **`python`**：執行 `doze_summary-termux.py` 產生摘要分析報告。
* **`nmap`**：用於無 Root 權限下掃描本機 `30000–65535` 動態無線除錯埠號。

### 2. 授權外部儲存空間與建立腳本目錄
```bash
termux-setup-storage
mkdir -p ~/doze
```

### 3. 設定執行權限與全域快捷指令
將 `doze.sh`、`doze_summary-termux.py` 與 `adb.sh` 放入 `~/doze/` 後，執行以下指令：

```bash
chmod +x ~/doze/doze.sh ~/doze/adb.sh
ln -sf ~/doze/doze.sh "$PREFIX/bin/doze"
ln -sf ~/doze/adb.sh "$PREFIX/bin/adb-auto"
```
> **注意**：請勿將 `adb.sh` 軟連結命名為 `adb`，否則會覆蓋系統原生的 `adb` 執行檔並造成遞迴呼叫錯誤。

---

## 二、 透過 NMM File Manager 掛載內部目錄（選用）

若習慣使用圖形化介面編輯 `~/doze/` 內的腳本，可透過 Android SAF 機制掛載：

1. 開啟 **NMM File Manager** → 左上角選單 → **新增儲存空間 / 系統檔案選擇器（SAF）**。
2. 在系統檔案選擇器左上角選單中，往下滑動並點擊 **Termux**。
3. 選擇 **`doze`** 資料夾 → 點擊 **「使用此資料夾」** → **「允許」**。
4. 編輯存檔時請確保換行符號為 **LF**、編碼為 **UTF-8**。

---

## 三、 日常測試執行流程

### 1. 初次配對（每台裝置僅需執行一次）
1. 進入手機 **設定 → 開發人員選項 → 無線除錯**，開啟開關。
2. 點擊 **「使用配對碼配對裝置」**，記下畫面顯示的 `IP:配對Port` 與 `6 位數配對碼`。
3. 在 Termux 執行：
   ```bash
   adb pair 127.0.0.1:<配對Port>
   ```
   依提示輸入 6 位數配對碼完成配對。

### 2. 執行 Doze 待機測試
1. 拔除手機充電線，確認「無線除錯」已開啟。
2. 在 Termux 執行（不帶參數即自動掃描 `30000–65535` 連接埠並驗證連線）：
   ```bash
   doze
   ```
   *(若需手動指定埠號，可執行 `doze <Port>`，例如 `doze 39815`)*
3. 腳本會自動送出 `KEYCODE_SLEEP` 關閉螢幕並開始計時，請靜置手機（建議 **30 分鐘以上** 以進入 Deep Idle）。
4. 測試結束時喚醒螢幕、回到 Termux 按下 **`Enter`** 鍵，系統將自動收集快照並輸出摘要至：
   ```text
   Download/doze-test/<日期_時間>/summary-<日期_時間>.txt
   ```
5. 測試完成後建議順手關閉「無線除錯」。

### 3. 單獨測試 ADB 自動連線
若僅需測試或建立本機無線除錯連線，可執行：
```bash
adb-auto
```

---

## 四、 核心腳本原始碼

### 1. `doze.sh`（整合強化版全高埠掃描與逐一驗證）

```bash
#!/usr/bin/env bash
# -------------------------------------------------------------
# Termux 版 Doze 測試 – 完整流程（全高埠自動偵測 + 手動「下一步」）
# 用法: doze [無線除錯Port]  (不帶參數則自動偵測)
# -------------------------------------------------------------
set -euo pipefail

# -------------------- 設定區 --------------------
DEFAULT_PORT="41077"          # 備援預設 Port
PKGS=("ch.deletescape.lawnchair.plah")
RECONNECT_TRIES=24
MIN_ALARM_MIN=125
WANT_NETSTATS=0
SLEEP_SCREEN=1                # 1 = 立刻讓螢幕關閉，讓 Doze 計時從此開始
# ------------------------------------------------

# ---------- 自動偵測 / 決定 Port ----------
detect_adb_port() {
  local connected
  # 1. 先檢查目前已連線的本機 ADB 端點
  connected=$(adb devices 2>/dev/null | awk '/^127\.0\.0\.1:[0-9]+[[:space:]]+device$/ {print $1}' | cut -d: -f2 | head -n1 || true)
  if [ -n "$connected" ]; then
    echo "$connected"
    return 0
  fi

  # 2. 透過 nmap 掃描全高埠範圍 (30000-65535)，並逐一驗證是否為有效 ADB 服務
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
  echo "[INFO] 使用手動指定的 Port：$PORT"
else
  echo "[INFO] 未指定 Port，正在自動偵測無線除錯端點..."
  if PORT=$(detect_adb_port); then
    echo "[INFO] 自動偵測成功：$PORT"
  else
    PORT="$DEFAULT_PORT"
    echo "[WARN] 無法自動偵測（請確認已開啟無線除錯並安裝 nmap），改用預設 Port：$PORT"
  fi
fi

ADB_ADDR="127.0.0.1:${PORT}"

# ---------- 路徑設定 ----------
SCRIPT_DIR="${HOME}/doze"
TIMESTAMP="$(date +"%Y%m%d_%H%M")"
OUT_DIR="${HOME}/storage/downloads/doze-test/${TIMESTAMP}"
mkdir -p "$OUT_DIR"

# ---------- 日誌 ----------
log() { echo "[TERMUX] $(date +%H:%M:%S) $*" | tee -a "$OUT_DIR/timeline.txt"; }
stamp() { date +"# captured: %Y-%m-%d %H:%M:%S"; }

# ---------- ADB 連線 ----------
connect_adb() {
  for i in $(seq 1 "$RECONNECT_TRIES"); do
    adb connect "$ADB_ADDR" >/dev/null 2>&1
    if [ "$(adb -s "$ADB_ADDR" get-state 2>/dev/null)" = "device" ]; then
      log "ADB 已連線至 $ADB_ADDR（第 $i 次嘗試）"
      return 0
    fi
    sleep 5
  done
  return 1
}

# ---------- 輔助函式 ----------
capture() {
  local f="$1"; shift
  "$@" > "$OUT_DIR/$f" 2>&1
  if [ ! -s "$OUT_DIR/$f" ]; then
    log "⚠ $f 為空（可能是 ADB 斷線）"
  fi
}
snapshot_battery() { { stamp; adb -s "$ADB_ADDR" shell dumpsys battery; } > "$OUT_DIR/$1"; }
snapshot_mem() {
  { stamp; } > "$OUT_DIR/$1"
  for p in "${PKGS[@]}"; do
    adb -s "$ADB_ADDR" shell dumpsys meminfo "$p" >> "$OUT_DIR/$1" 2>&1 || true
  done
}

# ---------- 主流程 ----------
log "=== Doze 測試開始（目標端點：$ADB_ADDR） ==="
connect_adb || { echo "無法連線到 $ADB_ADDR，請確認「無線除錯」已開啟"; exit 1; }

# 1. 先檢查未來的喚醒鬧鐘
{ stamp; adb -s "$ADB_ADDR" shell dumpsys alarm; } > "$OUT_DIR/alarm_start_full.txt"
NEXT=$(grep -A8 "Next wake from idle" "$OUT_DIR/alarm_start_full.txt" |
       grep -m1 -oE "triggerTime=[0-9-]+ [0-9:]+" | cut -d= -f2 || true)

if [ -n "$NEXT" ]; then
  PHONE_NOW=$(adb -s "$ADB_ADDR" shell date +"%Y-%m-%d %H:%M:%S" | tr -d '\r')
  NEXT_MIN=$(( ( $(date -d "$NEXT" +%s) - $(date -d "$PHONE_NOW" +%s) ) / 60 ))
  log "下一個喚醒鬧鐘在 $NEXT（約 ${NEXT_MIN} 分鐘後）"
  if [ "$NEXT_MIN" -lt "$MIN_ALARM_MIN" ]; then
    echo "⚠ 鬧鐘距離現在不到 $MIN_ALARM_MIN 分鐘，Doze 可能無法進入 deep idle"
    read -p "仍然要繼續嗎？[y/N] " ans
    [[ "$ans" =~ ^[Yy]$ ]] || { log "使用者取消測試"; exit 0; }
  fi
else
  log "目前沒有排定的 wake-from-idle 鬧鐘"
fi

# 2. 測試前快照
snapshot_mem mem_start.txt
snapshot_battery battery_start.txt
adb -s "$ADB_ADDR" shell dumpsys deviceidle unforce
adb -s "$ADB_ADDR" shell dumpsys batterystats --enable full-wake-history
adb -s "$ADB_ADDR" shell dumpsys batterystats --reset
log "batterystats 已重置"

# 3. 立即關螢幕（讓 Doze 計時從此開始）
if [ "$SLEEP_SCREEN" = "1" ]; then
  adb -s "$ADB_ADDR" shell input keyevent KEYCODE_SLEEP
  log "已送出 KEYCODE_SLEEP"
fi

# 4. 手動一步：使用者在手機上按下 Enter 繼續
echo -e "\n=== 手動步驟 ==="
echo "當你想正式結束測試時，請在 Termux 鍵盤（或藍牙鍵盤）敲 Enter。"
read -p "在手機上按 Enter 後繼續 → " _

# 5. 醒來後確保 ADB 仍連線（若 Port 在休眠期間變動也會自動重掃）
if ! connect_adb; then
  echo "ADB 斷線，請亮屏約 5 秒再按 Enter 重試"
  read -p "已亮屏? 按 Enter 重試 → " _
  if NEW_PORT=$(detect_adb_port); then
    PORT="$NEW_PORT"
    ADB_ADDR="127.0.0.1:${PORT}"
    log "重新偵測到 ADB 端點：$ADB_ADDR"
  fi
  connect_adb || { log "仍無法連線，測試結束"; exit 1; }
fi
log "ADB 重新連線成功"

# 6. 立即抓取時間敏感資料
capture deviceidle.txt adb -s "$ADB_ADDR" shell dumpsys deviceidle
snapshot_battery battery_end.txt
snapshot_mem mem_end.txt
adb -s "$ADB_ADDR" shell cmd role get-role-holders android.app.role.HOME | tee "$OUT_DIR/home_end.txt" || true

# 7. 抓取較大檔案（batterystats、optional netstats）
capture full.txt    adb -s "$ADB_ADDR" shell dumpsys batterystats
capture checkin.txt adb -s "$ADB_ADDR" shell dumpsys batterystats --checkin
capture history.txt adb -s "$ADB_ADDR" shell dumpsys batterystats --history
if [ "$WANT_NETSTATS" = "1" ]; then
  capture netstats.txt adb -s "$ADB_ADDR" shell dumpsys netstats detail
fi

# 8. 產生摘要（從內部安全目錄呼叫 Python）
log "呼叫 Python 產生摘要 …"
python3 "${SCRIPT_DIR}/doze_summary-termux.py" "$OUT_DIR/full.txt" \
  --checkin "$OUT_DIR/checkin.txt" \
  --pkg "$(IFS=,; echo "${PKGS[*]}")" \
  --deviceidle "$OUT_DIR/deviceidle.txt" \
  --mem "$OUT_DIR/mem_start.txt" "$OUT_DIR/mem_end.txt" \
  --battery "$OUT_DIR/battery_start.txt" "$OUT_DIR/battery_end.txt" \
  | tee "$OUT_DIR/summary-${TIMESTAMP}.txt"

log "=== 測試完成，所有檔案位於 $OUT_DIR ==="
```

---

### 2. `adb.sh`（獨立無線除錯自動連線腳本）

```bash
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
```
