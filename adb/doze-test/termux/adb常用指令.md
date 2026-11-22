## adb常用指令

**内存(pss)占用前 25 名**
```bash
adb shell dumpsys meminfo | sed -n '/Total PSS by process:/,$p' | grep -E "^ +[0-9,]+K: .*\(pid [0-9]+\)" | head -n 25
```

**綜合去識別化指令**
1. 所有 Email 地址 → 替換為 user@example.com
2. IPv4 位址（如區域網路或連線 IP）→ 替換為 0.0.0.0
3. MAC 位址（如藍牙或 Wi-Fi 路由器硬體位址）→ 替換為 00:00:00:00:00:00
4. 自訂關鍵字 → 替換為指定的遮罩字串（若有多個關鍵字，只要多加幾行 -e 's/關鍵字/HIDDEN/g' \ 即可）。
```bash
sed -E \
  -e 's#[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}#HIDDEN_EMAIL#g' \
  -e 's#\b([0-9]{1,3}\.){3}[0-9]{1,3}\b#0.0.0.0#g' \
  -e 's#([0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}#00:00:00:00:00:00#g' \
  -e 's#你的WiFi名稱#HIDDEN_WIFI#g' \
  -e 's#你的其他關鍵字#HIDDEN_TEXT#g' \
  -e 's#你的其他關鍵字#HIDDEN_TEXT#g' \
  -e 's#你的其他關鍵字#HIDDEN_TEXT#g' \
  full.txt > full_clean.txt
```
**Statistics since last charge:**

```bash
adb shell "dumpsys batterystats | tr -d '\r' | awk '/^Statistics since last charge:/{f=1; print; next} f{ if (/^$/ || /^[^[:space:]]/) exit; print }'"
```
**Estimated power use取前 40 行明細**
```bash
adb shell 'dumpsys batterystats | tr -d "\r" | awk '\''/^Statistics since last charge:/{f=1} f && /Estimated power use/{p=1; c=0} p{print; c++; if(c>40) exit} f && /^[^[:space:]]/ && !/^Statistics since last charge:/{exit}'\'''
```

**用數字 UID 反查套件名稱（Android 把 u0a 轉成 10000 + 編號)**
```bash
adb shell 'pm list packages -U | grep -E "10182|10194|10181|101178"'
```
---
**Termux簡易耗電查詢**
> 使用 python3 battery.py
```py
import re
import subprocess
import sys

def get_stats():
    try:
        result = subprocess.run(
            ["adb", "shell", "dumpsys", "batterystats"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.replace("\r", "")
    except FileNotFoundError:
        sys.exit("找不到 adb。請在 Termux 安裝 android-tools。")
    except subprocess.CalledProcessError as e:
        sys.exit(f"讀取失敗：{e.stderr.strip() or e}")

def find_value(text, label):
    match = re.search(
        rf"^\s*{re.escape(label)}:\s*([\d.]+)\s*mAh",
        text,
        re.MULTILINE,
    )
    return float(match.group(1)) if match else None

def find_duration_hours(text, label):
    match = re.search(
        rf"^\s*{re.escape(label)}:\s*(.*?)\s+\(",
        text,
        re.MULTILINE,
    )
    if not match:
        return None

    duration = match.group(1)
    units = {"d": 86400, "h": 3600, "m": 60, "s": 1, "ms": 0.001}
    seconds = sum(
        float(amount) * units[unit]
        for amount, unit in re.findall(r"([\d.]+)\s*(ms|d|h|m|s)\b", duration)
    )
    return seconds / 3600

text = get_stats()

capacity = find_value(text, "Estimated battery capacity")
discharge = find_value(text, "Discharge")
screen_off = find_value(text, "Screen off discharge")
screen_on = find_value(text, "Screen on discharge")
screen_off_hours = find_duration_hours(text, "Time on battery screen off")
screen_on_hours = find_duration_hours(text, "Screen on")

if capacity and discharge is not None:
    print(f"估計電池容量：{capacity:.0f} mAh")
    print(f"累計耗電：{discharge:.0f} mAh（約 {discharge / capacity * 100:.1f}%）")
else:
    print("找不到電池容量或累計耗電資料。")

if screen_on is not None and screen_on_hours:
    print(
        f"亮屏：{screen_on:.0f} mAh，"
        f"{screen_on_hours:.2f} 小時，"
        f"平均 {screen_on / screen_on_hours:.1f} mAh/小時"
    )

if screen_off is not None and screen_off_hours:
    print(
        f"熄屏：{screen_off:.0f} mAh，"
        f"{screen_off_hours:.2f} 小時，"
        f"平均 {screen_off / screen_off_hours:.1f} mAh/小時"
    )
```
---
**Termux ADB 自動連線工具**
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
```

---
# Android `dumpsys batterystats` 指令與耗電分析筆記

## 1. 重置電池統計數據 (`--reset`)
* **指令：** `adb shell dumpsys batterystats --reset`
* **實際影響：** 
  * 僅清除系統內部的「耗電量歷史統計資料」，使「設定 > 電池」中的 App 耗電排行與曲線圖歸零重新計算。
  * **不會**對電池硬體造成損害、不影響電池健康度與循環次數，也無法「校正」電量顯示異常。
* **主要用途：** 進行 App 耗電測試前將數據歸零，以排除過去歷史紀錄的干擾。

---

## 2. 完整喚醒歷史紀錄 (`full-wake-history`)
* **開啟指令：** `adb shell dumpsys batterystats --enable full-wake-history`
* **關閉指令：** `adb shell dumpsys batterystats --disable full-wake-history`
* **出廠預設值：** **關閉 (Disabled)**

### 長期啟用的影響（不建議日常開啟）
* **佔用儲存空間：** 系統會鉅細靡遺地記錄每次喚醒鎖（Wakelock）與背景工作，導致日誌檔案持續膨脹。
* **增加微幅耗電與 I/O 負擔：** 頻繁寫入底層事件會消耗額外的 CPU 與電量。
* **日誌覆蓋變快：** 緩衝區容量固定，資料量暴增會導致舊紀錄更快被覆蓋，可回溯的總時間縮短。

### 查詢目前狀態與預設值
1. **檢視所有支援參數：** `adb shell dumpsys batterystats -h`
2. **反推目前開關狀態：** 執行 `adb shell dumpsys batterystats --history`
   * 若時間軸頻繁出現 `+wake_lock` / `-wake_lock` 標記，代表處於**開啟狀態**。
   * 若僅有基本螢幕開關與 `+running` 紀錄，代表處於**預設關閉狀態**。
3. **常見旗標預設值對照：**
   * `full-wake-history`：預設關閉
   * `no-auto-reset`：預設關閉
   * `pretend-screen-off`：預設關閉
   * *(註：多數裝置重新開機後，這類臨時除錯旗標也會自動恢復為關閉)*

---

## 3. 不開啟 `full-wake-history` 對分析的影響

| 分析維度 | 不開啟（預設關閉） | 開啟（完整紀錄） |
| :--- | :--- | :--- |
| **宏觀耗電數據** | **不受影響**（仍可看各 App 總耗電 mAh、總 CPU 與總喚醒時間） | 完整保留 |
| **系統狀態時間軸** | **不受影響**（仍可看螢幕開關、網路訊號、充電狀態） | 完整保留 |
| **精準時間點定位** | **無法對齊**（只知 CPU 何時醒來，不知是哪個 App 喚醒） | **可精準定位**特定時間點的喚醒兇手 |
| **短暫喚醒事件** | **容易遺漏**（系統會合併事件或只記首個來源） | 完整記錄頻繁「秒醒秒睡」的 App |

### 實務排查建議
* **初步排查與日常使用：** 維持**關閉**，直接匯出預設的 `bugreport` 檢視各 App 累計耗電與總喚醒時間即可。
* **抓出待機掉電兇手：** 測試前執行 `--enable full-wake-history` 並搭配 `--reset` 歸零，靜置待機數小時後匯出日誌，分析完畢後立刻執行 `--disable` 關閉。
