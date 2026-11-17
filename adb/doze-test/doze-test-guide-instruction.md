測試方法 (關尋找手機，ubuntu adb wifi) 
做完 batterystats --reset後 ， ubuntu 立刻  suspend  
測試時間 完成 後 ，打開電腦 立刻紀錄 
ubuntu有時候會動喚醒，電腦自動suspend為15分

## 我的初步預想
```js
#!/bin/bash

TIMESTAMP=$(date +"%Y%m%d_%H%M")

OUT_DIR="$TIMESTAMP"
mkdir -p "$OUT_DIR"

# 準備工作
adb shell cmd role get-role-holders android.app.role.HOME
adb shell dumpsys deviceidle unforce
adb shell dumpsys batterystats --enable full-wake-history
adb shell dumpsys batterystats --reset
adb shell dumpsys meminfo com.sec.android.app.launcher > $OUT_DIR/mem_start.txt
adb shell dumpsys meminfo ch.deletescape.lawnchair.plah >> $OUT_DIR/mem_start.txt
adb shell dumpsys battery > $OUT_DIR/battery_start.txt



# ubuntu 立刻  suspend
systemctl suspend


# 連接 adb ( ip:port  不一樣要修正 ) 
adb  devices
adb  connect 192.168.1.142:44055

# 會遇到 adb: device offline
adb  devices
adb  connect 192.168.1.142:44055


# 紀錄
adb shell dumpsys batterystats --checkin  > $OUT_DIR/checkin.txt
adb shell dumpsys batterystats --history  > $OUT_DIR/history.txt
adb shell dumpsys deviceidle              > $OUT_DIR/deviceidle.txt
adb shell dumpsys batterystats            > $OUT_DIR/full.txt
adb shell cmd role get-role-holders android.app.role.HOME
adb shell dumpsys battery > $OUT_DIR/battery_end.txt 
adb shell dumpsys meminfo com.sec.android.app.launcher > $OUT_DIR/mem_end.txt
adb shell dumpsys meminfo ch.deletescape.lawnchair.plah >> $OUT_DIR/mem_end.txt

# 需要看網路時:
adb shell dumpsys netstats detail         > $OUT_DIR/netstats.txt

# 處理緩慢 排在後面 
journalctl -b | grep -iE "suspend|resume|sleep|PM: " > $OUT_DIR/suspend.txt


# 摘要處理
python3 doze_summary.py $OUT_DIR/full.txt \
  --checkin $OUT_DIR/checkin.txt \
  --pkg ch.deletescape.lawnchair.plah,com.sec.android.app.launcher \
  --suspend $OUT_DIR/suspend.txt --deviceidle $OUT_DIR/deviceidle.txt \
  --mem $OUT_DIR/mem_start.txt $OUT_DIR/mem_end.txt --battery $OUT_DIR/battery_start.txt $OUT_DIR/battery_end.txt | tee $OUT_DIR/summary-$TIMESTAMP.txt > /dev/null

```
---

`doze-test.sh` 的記憶體指令確實有一處寫錯,另外還有幾個會讓資料缺失或失真的地方。我已改成 v2,並一併更新摘要腳本與指南。

## 指令格式的檢查結果

| 項目 | 結果 |
|---|---|
| `adb shell dumpsys meminfo com.sec.android.app.launcher > mem_start.txt` | ✓ 格式對 |
| `adb shell dumpsys meminfo ch.deletescape.lawnchair.plah >> mem_start.txt` | ✓ 指令對,但檔案裡有兩個進程,而摘要腳本 v2 初版**只解析第一個**,所以 Lawnchair 被漏掉 |
| `adb shell dumpsys ch.deletescape.lawnchair.plah >> mem_end.txt` | ✗ **漏了 `meminfo`**。輸出只會是 `Can't find service`,沒有記憶體資料 |
| `battery_start.txt` / `battery_end.txt` 沒有時間資訊 | ✗ 摘要算不出「區間放電」(你的 `summary.txt` 確實沒有那一行) |
| `adb devices` 失敗後繼續執行 | ✗ 後面全部抓到空檔 |
| `batterystats` 的 `full` / `checkin` / `history` / `deviceidle` | ✓ 格式對 |
| `netstats`、`journalctl ... \| grep` | ✓ 對 |
| `python3 doze_summary.py ...` 的參數 | ✓ 對(你這次有帶 `--checkin`,所以 UID 名稱正常) |

你的 `summary.txt` 也印證了第一點:`mem_start` 與 `mem_end` 都只有 One UI Home,沒有 Lawnchair。

## v2 做了什麼

1. 修正 `meminfo`,兩個 launcher 改用迴圈處理,不會漏。
2. 檔案開頭寫入 `# captured: 時間`,摘要才算得出區間放電;摘要腳本也改成能解析一個檔案裡的多個進程,遇到 `Can't find service` 會標 ⚠。
3. **adb 重連改成重試迴圈**(每 5 秒、共約 2 分鐘);仍連不上就提示你亮屏手機後按 Enter 重試。每個擷取檔都檢查是否為空。
4. 擷取順序改成時間敏感的先抓(`deviceidle`、電池、鬧鐘),體積大的 `batterystats` 後抓。
5. **事前檢查下一個會喚醒手機的鬧鐘**(FMM),不到 125 分鐘會提醒你。我用你貼的 `dumpsys alarm` 輸出實際測過這段解析,抓得到 `2026-11-16 08:04:40`。
6. 先拍快照、最後才 `reset`;並可用 `KEYCODE_SLEEP` 讓螢幕立刻關閉(`SLEEP_SCREEN=1`,我沒辦法在你的手機上驗證,可以改成 0)。
7. 其他:路徑用腳本所在資料夾、指令用 `-s` 指定裝置、變數加引號。

用之前要改的只有 `ADB_ADDR`(IP:埠號)與 `PKGS`。
---
```js
#!/bin/bash
# doze-test.sh v2 — 一鍵待機測試:重置統計 → 電腦睡眠 → 醒來後自動重連 adb 並紀錄 → 產生摘要
#
# 用法:   ./doze-test.sh            (在 doze_summary.py 所在的資料夾,或與它放在同一個資料夾)
# 需要:   手機已開啟無線偵錯並與電腦配對過;電腦可用 `systemctl suspend`
# 注意:   測試開始前請確認 FMM(尋找我的手機)狀態、手機未充電、預設桌面是你要測的那個。
#
# v2 改動(相對於 v1):
#   1. 修正:mem_end 的 Lawnchair 指令缺了 `meminfo`(v1 寫成 `dumpsys ch.deletescape.lawnchair.plah`,抓不到資料)
#   2. 兩個 launcher 的 meminfo 現在由迴圈處理,不會漏;摘要腳本也能在同一個檔案裡解析多個進程
#   3. battery / meminfo 檔案開頭寫入 `# captured:` 時間,摘要才算得出「區間放電」
#   4. adb 重連改成重試迴圈;失敗時不會繼續寫出一堆空檔案,而是提示你亮屏手機後再試
#   5. 資料擷取順序改為「時間敏感的先抓」(deviceidle、電池、鬧鐘),體積大的 batterystats 後抓
#   6. 事前檢查下一個「會喚醒手機的鬧鐘」(FMM)距離現在多久,太近會提醒
#   7. 每個擷取檔都檢查是否為空;指令改用 -s 指定裝置;變數加引號

set -u

# ===================== 設定 =====================
ADB_ADDR="192.168.1.142:44055"   # 無線偵錯的 IP:埠號(重開無線偵錯後埠號會變,要修正)
PKGS=("com.sec.android.app.launcher" "ch.deletescape.lawnchair.plah")   # 要量記憶體的 launcher 套件
RECONNECT_TRIES=24               # 每次間隔 5 秒,共約 2 分鐘
MIN_ALARM_MIN=125                # 下一個 wake-from-idle 鬧鐘至少要在幾分鐘之後
WANT_NETSTATS=0                  # 1 = 一併匯出 netstats(很大,通常不需要)
SLEEP_SCREEN=1                   # 1 = 重置後先用 KEYCODE_SLEEP 讓螢幕立刻關閉(未在所有機型驗證)
# =================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TIMESTAMP="$(date +"%Y%m%d_%H%M")"
OUT_DIR="$SCRIPT_DIR/$TIMESTAMP"
mkdir -p "$OUT_DIR"
A=(adb -s "$ADB_ADDR")

stamp() { date +"# captured: %Y-%m-%d %H:%M:%S"; }
log()   { echo "$(date +"%H:%M:%S") $*" | tee -a "$OUT_DIR/timeline.txt"; }

# capture <檔名> <指令...>:把指令輸出存檔,並檢查不是空的
capture() {
  local f="$1"; shift
  "$@" > "$OUT_DIR/$f" 2>&1
  if [ ! -s "$OUT_DIR/$f" ]; then
    log "⚠ $f 是空的(adb 連線可能中斷)"
  fi
}

snapshot_battery() { { stamp; "${A[@]}" shell dumpsys battery; } > "$OUT_DIR/$1"; }

snapshot_mem() {
  { stamp; } > "$OUT_DIR/$1"
  for p in "${PKGS[@]}"; do
    "${A[@]}" shell dumpsys meminfo "$p" >> "$OUT_DIR/$1"
  done
}

connect_adb() {
  local i
  for i in $(seq 1 "$RECONNECT_TRIES"); do
    adb connect "$ADB_ADDR" >/dev/null 2>&1
    if [ "$(adb -s "$ADB_ADDR" get-state 2>/dev/null)" = "device" ] && "${A[@]}" shell true >/dev/null 2>&1; then
      log "adb 已連線(第 $i 次嘗試)"
      return 0
    fi
    adb disconnect "$ADB_ADDR" >/dev/null 2>&1   # 清掉 offline 狀態再重試
    sleep 5
  done
  return 1
}

# ---------------------------------------------------------------- 開始前
log "開始前:連線 adb"
connect_adb || { echo "無法連線 $ADB_ADDR,請確認 IP:埠號(無線偵錯畫面上顯示的)"; exit 1; }

# 預設桌面與電量
"${A[@]}" shell cmd role get-role-holders android.app.role.HOME | tee "$OUT_DIR/home_start.txt"
"${A[@]}" shell dumpsys battery | grep -E "^  (AC|USB|Wireless) powered|^  level"

# 下一個「會喚醒手機」的鬧鐘(FMM 的 defaultScanStartTimer 之類),Samsung 的 min_time_to_alarm=1h
{ stamp; "${A[@]}" shell dumpsys alarm; } > "$OUT_DIR/alarm_start_full.txt"
{ stamp; grep -B2 -A8 "defaultScanStartTimer" "$OUT_DIR/alarm_start_full.txt"; } > "$OUT_DIR/alarm_start.txt"
NEXT="$(grep -A8 "Next wake from idle" "$OUT_DIR/alarm_start_full.txt" | grep -m1 -oE "triggerTime=[0-9-]+ [0-9:]+" | cut -d= -f2)"
if [ -n "$NEXT" ]; then
  PHONE_NOW="$("${A[@]}" shell date +"%Y-%m-%d %H:%M:%S" | tr -d '\r')"   # 用手機的「現在」,避免電腦與手機時鐘差
  NEXT_MIN=$(( ( $(date -d "$NEXT" +%s) - $(date -d "$PHONE_NOW" +%s) ) / 60 ))
  log "下一個會喚醒手機的鬧鐘:$NEXT(約 ${NEXT_MIN} 分鐘後)"
  if [ "$NEXT_MIN" -lt "$MIN_ALARM_MIN" ]; then
    echo "⚠ 這個鬧鐘距離現在不到 ${MIN_ALARM_MIN} 分鐘;Doze 很可能放棄進入 deep idle(min_time_to_alarm=1h)。"
    read -r -p "仍要開始測試嗎?[y/N] " ans
    [ "$ans" = "y" ] || [ "$ans" = "Y" ] || exit 0
  fi
else
  log "目前沒有排定的 wake-from-idle 鬧鐘"
fi

# 事前快照(先拍快照,最後才 reset,這樣統計起點就是電腦睡眠前的那一刻)
snapshot_mem mem_start.txt
snapshot_battery battery_start.txt
"${A[@]}" shell dumpsys deviceidle unforce
"${A[@]}" shell dumpsys batterystats --enable full-wake-history
"${A[@]}" shell dumpsys batterystats --reset
log "batterystats 已重置"

if [ "$SLEEP_SCREEN" = "1" ]; then
  "${A[@]}" shell input keyevent KEYCODE_SLEEP    # 讓螢幕立刻關閉;Doze 計時從這裡開始
fi

# ---------------------------------------------------------------- 電腦睡眠
log "電腦即將睡眠(醒來後會自動繼續)"
sleep 2
systemctl suspend
log "電腦已醒來"

# ---------------------------------------------------------------- 醒來後
if ! connect_adb; then
  echo
  echo "adb 連不上(常見是 No route to host)。請亮屏手機約 5 秒讓 adb 連線,然後按 Enter 重試。"
  echo "這幾秒的亮屏會被記進統計;摘要會標出「測試期間有亮屏」,請把有效待機區間算到那裡為止。"
  read -r -p "已亮屏?按 Enter 重試:" _
  log "使用者亮屏手機後重試"
  connect_adb || { echo "仍然連不上,結束。請手動執行 doze-test.sh 中「醒來後」的部分。"; exit 1; }
fi

# 時間敏感的先抓
capture deviceidle.txt "${A[@]}" shell dumpsys deviceidle
snapshot_battery battery_end.txt
{ stamp; "${A[@]}" shell dumpsys alarm | grep -B2 -A8 "defaultScanStartTimer"; } > "$OUT_DIR/alarm_end.txt"
snapshot_mem mem_end.txt
"${A[@]}" shell cmd role get-role-holders android.app.role.HOME | tee "$OUT_DIR/home_end.txt"

# 體積大的後抓
capture full.txt    "${A[@]}" shell dumpsys batterystats
capture checkin.txt "${A[@]}" shell dumpsys batterystats --checkin
capture history.txt "${A[@]}" shell dumpsys batterystats --history
if [ "$WANT_NETSTATS" = "1" ]; then
  capture netstats.txt "${A[@]}" shell dumpsys netstats detail
fi

# 電腦端的睡眠 / 喚醒紀錄(處理慢,放最後)
journalctl -b | grep -iE "suspend|resume|sleep|PM: " > "$OUT_DIR/suspend.txt"

# ---------------------------------------------------------------- 摘要
python3 "$SCRIPT_DIR/doze_summary.py" "$OUT_DIR/full.txt" \
  --checkin "$OUT_DIR/checkin.txt" \
  --pkg "$(IFS=,; echo "${PKGS[*]}")" \
  --suspend "$OUT_DIR/suspend.txt" --deviceidle "$OUT_DIR/deviceidle.txt" \
  --mem "$OUT_DIR/mem_start.txt" "$OUT_DIR/mem_end.txt" \
  --battery "$OUT_DIR/battery_start.txt" "$OUT_DIR/battery_end.txt" \
  | tee "$OUT_DIR/summary-$TIMESTAMP.txt"

log "完成:$OUT_DIR"
```
---
## doze_summary.py

```js
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
doze_summary.py (v2) — 把 `dumpsys batterystats` 的完整輸出濃縮成約 100–150 行的摘要,
方便貼給 AI 分析(完整檔 600 KB–1 MB,絕大部分是和問題無關的清單)。

用法:
  python3 doze_summary.py run_full.txt
  python3 doze_summary.py run_full.txt --checkin run_checkin.txt --pkg ch.deletescape.lawnchair.plah,com.sec.android.app.launcher
  python3 doze_summary.py run_full.txt --suspend suspend.txt          # 對照電腦的睡眠時間
  python3 doze_summary.py run_full.txt --deviceidle run_deviceidle.txt
  python3 doze_summary.py run_full.txt --mem lawnchair_mem.txt --battery battery.txt

輸入:
  run_full.txt   adb shell dumpsys batterystats > run_full.txt   (必要;含 history 與統計)
  run_checkin.txt adb shell dumpsys batterystats --checkin        (選用;用來把 UID 換成套件名稱)
  suspend.txt    journalctl -b | grep -iE "suspend|resume|sleep|PM: "  (選用)
  deviceidle     adb shell dumpsys deviceidle                      (選用)
  mem            adb shell dumpsys meminfo <套件名稱>               (選用)
  battery        adb shell dumpsys battery                         (選用)

v2 新增:UID 換成套件名稱(避免 AI 亂猜)、--pkg 依套件名稱列出 launcher 等指定 App、
突發耗電偵測、--mem、--battery、時鐘時間、「CPU 深度睡眠比例」(= DevCheck 的深度睡眠)。
注意:這只是摘要,原始檔請自己保留。
"""
import argparse
import collections
import datetime as dt
import re
import sys

WELL_KNOWN = {0: "root/kernel", 1000: "system", 1001: "radio/phone", 1020: "mdnsd(multicast DNS)",
              1051: "netd", 2000: "shell(adbd)"}


# ---------------------------------------------------------------- helpers
def parse_dur(s):
    """'1h 4m 12s 31ms' / '+1h4m12s31ms' -> milliseconds"""
    t = 0
    for v, u in re.findall(r"(\d+)\s*(d|h|ms|m|s)", s):
        t += int(v) * {"d": 86400000, "h": 3600000, "m": 60000, "s": 1000, "ms": 1}[u]
    return t


def fmt(ms):
    ms = int(ms)
    return f"{ms // 3600000}h{ms % 3600000 // 60000:02d}m{ms % 60000 // 1000:02d}s"


def grab(text, pattern, group=1, flags=re.M):
    m = re.search(pattern, text, flags)
    return m.group(group).strip() if m else None


def load_uidmap(path):
    m = {}
    if not path:
        return m
    for l in open(path, encoding="utf-8", errors="ignore"):
        p = l.strip().split(",")
        if len(p) >= 6 and p[2] == "i" and p[3] == "uid":
            try:
                m.setdefault(int(p[4]), []).append(p[5])
            except ValueError:
                pass
    return m


def uid_to_int(s):
    if s.isdigit():
        return int(s)
    m = re.match(r"u(\d+)a(\d+)$", s)
    if m:
        return int(m.group(1)) * 100000 + 10000 + int(m.group(2))
    return None


def label(uid_s, uidmap):
    u = uid_to_int(uid_s)
    if u is None:
        return uid_s
    if u < 10000:
        # 共用 UID(例如 1000 有上百個套件),不要隨便挑一個套件名稱
        return f"{uid_s}({WELL_KNOWN[u]})" if u in WELL_KNOWN else uid_s
    names = uidmap.get(u)
    if names:
        return f"{uid_s}({names[0]})"
    user, app = divmod(u, 100000)
    if user > 0:
        base = uidmap.get(app)
        if base:
            return f"{uid_s}(≈{base[0]},第二使用者/工作資料夾)"
    return uid_s


def split_dump(lines):
    for i, l in enumerate(lines):
        if l.startswith("Statistics since last charge"):
            return lines[:i], lines[i:]
    return lines, []


def parse_history(hist):
    ev = []
    for l in hist:
        m = re.match(r"^\s+(\+[\dhdms]+|0) \((\d+)\) (\d{3}) ?(.*)$", l)
        if not m:
            continue
        ts, _, lvl, rest = m.groups()
        t = 0 if ts == "0" else parse_dur(ts)
        ev.append((t, int(lvl), rest))
    return ev


def section(stats_text, header, n=14):
    i = stats_text.find(header)
    if i < 0:
        return []
    return stats_text[i:].split("\n")[1:n + 1]


def per_uid_blocks(stats_lines):
    cur, out = None, collections.defaultdict(list)
    for l in stats_lines:
        m = re.match(r"^  (u\d+[a-z]\d+|\d+):\s*$", l)
        if m:
            cur = m.group(1)
            continue
        if cur and l.startswith("    "):
            out[cur].append(l.strip())
        elif cur and l.startswith("  ") and not l.startswith("    "):
            cur = None
    return out


def parse_suspend(path, year):
    S, E = [], []
    for l in open(path, encoding="utf-8", errors="ignore"):
        m = re.match(r"^(\w{3} +\d+ \d\d:\d\d:\d\d) \S+ systemd-sleep\[\d+\]: "
                     r"(Performing sleep operation|System returned from sleep operation) '(\w+)'", l)
        if m:
            t = dt.datetime.strptime(f"{year} " + re.sub(r" +", " ", m.group(1)), "%Y %b %d %H:%M:%S")
            (S if m.group(2).startswith("Performing") else E).append(t)
    iv = []
    for a in S:
        nxt = [b for b in E if b >= a]
        if nxt:
            iv.append((a, min(nxt)))
    return sorted(set(iv))


def asleep_ratio(iv, a, b):
    tot = (b - a).total_seconds()
    if tot <= 0:
        return 0.0
    s = 0.0
    for x, y in iv:
        lo, hi = max(a, x), min(b, y)
        if hi > lo:
            s += (hi - lo).total_seconds()
    return s / tot


def mb(kb):
    return f"{int(kb) / 1024:.1f} MB"


# ---------------------------------------------------------------- optional sections
def _stamp(path):
    """時間來源:檔案開頭的 `# captured: YYYY-MM-DD HH:MM:SS`(doze-test.sh 會寫入),否則用檔名裡的 YYYYMMDD_HHMMSS"""
    try:
        with open(path, encoding="utf-8", errors="ignore") as f:
            head = "".join(f.readline() for _ in range(5))
        m = re.search(r"# captured: (\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)", head)
        if m:
            return dt.datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S")
    except OSError:
        pass
    m = re.search(r"(\d{8})_(\d{6})", path)
    if not m:
        return None
    try:
        return dt.datetime.strptime(m.group(1) + m.group(2), "%Y%m%d%H%M%S")
    except ValueError:
        return None


def _mem_parse(txt):
    d = {}
    m = re.search(r"\*\* MEMINFO in pid (\d+) \[(.+?)\]", txt)
    d["proc"] = m.group(2) if m else "?"
    mm = re.search(r"^\s+TOTAL\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)", txt, re.M)
    if mm:
        v = [int(x) for x in mm.groups()]
        d.update(pss=v[0], pdirty=v[1], pclean=v[2], swap=v[3], rss=v[4], heap_alloc=v[6])
    for k, key in (("Java Heap", "java"), ("Native Heap", "native"), ("Graphics", "gfx"), ("System", "system")):
        m2 = re.search(r"^\s+" + re.escape(k) + r":\s+(\d+)", txt, re.M)
        if m2:
            d[key] = int(m2.group(1))
    m2 = re.search(r"Views:\s+(\d+).*?Activities:\s+(\d+)", txt, re.S)
    if m2:
        d["views"], d["acts"] = int(m2.group(1)), int(m2.group(2))
    return d


def _mem_blocks(path):
    """一個檔案可以含多個進程(例如把 One UI Home 與 Lawnchair 的 meminfo 寫在同一個檔);全部解析"""
    txt = open(path, encoding="utf-8", errors="ignore").read()
    up = re.search(r"Uptime: (\d+) Realtime: (\d+)", txt)
    out = []
    for part in re.split(r"(?=\*\* MEMINFO in pid)", txt):
        if not part.startswith("** MEMINFO in pid"):
            continue
        d = _mem_parse(part)
        d["path"], d["stamp"] = path, _stamp(path)
        if up:
            d["up"], d["rt"] = int(up.group(1)), int(up.group(2))
        out.append(d)
    if not out:
        first = txt.strip().split("\n")[0][:80] if txt.strip() else "(空檔)"
        out.append({"path": path, "error": f"沒有 meminfo 資料(檔案第一行:{first}) — 請確認指令是 `dumpsys meminfo <套件名稱>`"})
    elif "Can't find service" in txt or "No process found" in txt:
        out[-1]["warn"] = "檔案裡另有錯誤訊息(Can't find service / No process found),可能有某個指令寫錯或進程沒在執行"
    return out


def summarize_meminfo(paths):
    print("\n## 記憶體(dumpsys meminfo,單位 MB;1024 KB = 1 MB;單一時間點,請多量幾次)")
    rows = [d for p in paths for d in _mem_blocks(p)]
    for d in rows:
        if "error" in d:
            print(f"- ⚠ {d['path']}: {d['error']}")
            continue
        if "pss" not in d:
            print(f"- ⚠ {d['path']}({d.get('proc')}): 解析失敗")
            continue
        priv = d["pdirty"] + d["pclean"]
        when = d["stamp"].strftime("%m-%d %H:%M") if d["stamp"] else d["path"]
        print(f"- [{when}] {d['proc']}: PSS {mb(d['pss'])} | 私有記憶體(Private Dirty+Clean){mb(priv)} | RSS {mb(d['rss'])} | "
              f"Swap PSS {mb(d['swap'])} | Java {mb(d.get('java', 0))} Native {mb(d.get('native', 0))} 圖形 {mb(d.get('gfx', 0))} 系統共用 {mb(d.get('system', 0))}"
              f" | Views {d.get('views')} Activities {d.get('acts')}")
        if d.get("warn"):
            print(f"    ⚠ {d['warn']}")
        if "up" in d and d["rt"]:
            print(f"    開機至今 Realtime {fmt(d['rt'])},Uptime {fmt(d['up'])} → CPU 深度睡眠(suspend)累計約 {100 - d['up'] / d['rt'] * 100:.0f}%(= DevCheck 的「深度睡眠」)")
    groups = collections.defaultdict(list)
    for d in rows:
        if "pss" in d:
            groups[d["proc"]].append(d)
    for proc, g in groups.items():
        if len(g) >= 2:
            a, b = g[0], g[-1]
            print(f"- {proc} 第一次 → 最後一次:PSS {(b['pss'] - a['pss']) / 1024:+.1f} MB,"
                  f"私有記憶體 {((b['pdirty'] + b['pclean']) - (a['pdirty'] + a['pclean'])) / 1024:+.1f} MB,"
                  f"Swap PSS {(b['swap'] - a['swap']) / 1024:+.1f} MB(同一進程在數小時內的自然波動)")
    print("- 註:PSS 含按比例分攤的共用記憶體(「系統」那一欄),不同 App 之間比較請優先看「私有記憶體」;"
          "Heap Alloc 是 native + dalvik 合計,不要當成 Java Heap。")


def summarize_battery(paths):
    print("\n## 電池(dumpsys battery)")
    pts = []
    for p in paths:
        txt = open(p, encoding="utf-8", errors="ignore").read()
        lv = grab(txt, r"^\s+level: (\d+)")
        cc = grab(txt, r"^\s+Charge counter: (\d+)")
        if not (lv and cc):
            print(f"- {p}: 解析失敗")
            continue
        st = _stamp(p)
        pts.append((st, int(lv), int(cc) / 1000))
        per = int(cc) / 1000 / int(lv)
        when = st.strftime("%m-%d %H:%M:%S") if st else p
        print(f"- [{when}] level {lv}%、Charge counter {int(cc) / 1000:.1f} mAh → 每 1% 約 {per:.1f} mAh,推算滿電約 {per * 100:.0f} mAh"
              f"(標示 6000 mAh 的 1% 應為 60 mAh);電池保護 mProtectBatteryMode={grab(txt, r'mProtectBatteryMode: (\d+)')}"
              f"({grab(txt, r'mProtectionThreshold: (\d+)')}%)")
    if len(pts) >= 2 and pts[0][0] and pts[-1][0]:
        hrs = (pts[-1][0] - pts[0][0]).total_seconds() / 3600
        d = pts[0][2] - pts[-1][2]
        if hrs > 0:
            print(f"- 區間放電:{d:.1f} mAh / {hrs:.2f} 小時 = {d / hrs:.1f} mAh/h(解析度 4.5 mAh;含這段時間內任何亮屏與 adb 重連)")
    txt = open(paths[-1], encoding="utf-8", errors="ignore").read()
    pairs = []
    for l in txt.split("\n"):
        m = re.search(r"level:(\d+),.*? cc:(\d+),", l)
        if m:
            pairs.append((int(m.group(1)), int(m.group(2)) / 1000))
    if pairs:
        ratios = [c / lv_ for lv_, c in pairs if lv_]
        print(f"- 電池變化 log:{len(pairs)} 筆,cc ÷ level = {min(ratios):.1f}–{max(ratios):.1f} mAh/%"
              "(cc 近似由 SOC 換算:高電量時 log 的 cc 可連續數小時不變,請以 dumpsys 的 Charge counter 與 batterystats 為準)")
    print(f"- 健康:BSOH={grab(txt, r'mSavedBatteryBsoh: (\S+)')}")


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("full")
    ap.add_argument("--uids", default="", help="要特別列出的 UID,逗號分隔,例如 u0a1361,u0a125")
    ap.add_argument("--pkg", default="", help="要特別列出的套件名稱,逗號分隔(需要 --checkin)")
    ap.add_argument("--checkin", help="adb shell dumpsys batterystats --checkin 的輸出,用來把 UID 換成套件名稱")
    ap.add_argument("--suspend", help="journalctl -b | grep -iE 'suspend|resume|sleep|PM: ' 的輸出")
    ap.add_argument("--deviceidle", help="adb shell dumpsys deviceidle 的輸出")
    ap.add_argument("--mem", nargs="+", help="adb shell dumpsys meminfo <套件> 的輸出(可給多個檔案,例如測試前、後)")
    ap.add_argument("--battery", nargs="+", help="adb shell dumpsys battery 的輸出(可給多個檔案,例如測試前、後;檔名含 YYYYMMDD_HHMMSS 時會算區間放電)")
    a = ap.parse_args()

    uidmap = load_uidmap(a.checkin)
    lines = open(a.full, encoding="utf-8", errors="ignore").read().split("\n")
    hist, stats = split_dump(lines)
    text = "\n".join(stats)
    ev = parse_history(hist)

    print("# 摘要:", a.full)
    start = grab(text, r"Start clock time: (\S+)")
    start_dt = None
    if start:
        try:
            start_dt = dt.datetime.strptime(start, "%Y-%m-%d-%H-%M-%S")
        except ValueError:
            pass

    def wall(t):
        return (start_dt + dt.timedelta(milliseconds=t)).strftime("%H:%M:%S") if start_dt else ""

    def tw(t):
        w = wall(t)
        return f"{fmt(t)}({w})" if w else fmt(t)

    print(f"- 統計起點:{start}(以下括號內為時鐘時間)")
    m = re.search(r"Time on battery: (.*?) \(100\.0%\) realtime, (.*?) \(([\d.]+)%\) uptime", text)
    if m:
        up = float(m.group(3))
        print(f"- 時長:{m.group(1)};CPU 清醒(uptime):{m.group(2)}({up}%)"
              f" → **CPU 深度睡眠(suspend)約 {100 - up:.1f}%**(= DevCheck 的「深度睡眠」概念,"
              "和 Doze 的 deep idle 是不同的東西)")
    print(f"- 亮屏:{grab(text, r'^  Screen on: (.*)')}")
    scr = [t for t, _, r in ev if re.search(r"(^|\s)\+screen", r) and t > 60000]
    if scr:
        print(f"- ⚠ 測試期間有亮屏:第一次在 {tw(scr[0])}。建議把「有效待機區間」當作 0 – {fmt(scr[0])},"
              "之後(例如為了讓 adb 重新連線而喚醒手機)的耗電不要算進待機。")
    print(f"- 放電 Discharge:{grab(text, r'^  Discharge: (.*)')}"
          "(電池計數器 cc,解析度約 4.5 mAh;百分比不是線性,請以 mAh 為準)")
    print(f"- Light doze 放電:{grab(text, r'Device light doze discharge: (.*)')};"
          f"Deep doze 放電:{grab(text, r'Device deep doze discharge: (.*)')}")
    print(f"- Light idle:{grab(text, r'^  Device light idling: (.*)')}")
    print(f"- Deep idle(full):{grab(text, r'^  Device full idling: (.*)')}")
    print(f"- Idle mode light:{grab(text, r'^  Idle mode light time: (.*)')}")
    print(f"- Idle mode full:{grab(text, r'^  Idle mode full time: (.*)')}")
    print(f"- Partial wakelock 總時間:{grab(text, r'Total partial wakelock time: (.*)')}")
    print(f"- WiFi kernel active:{grab(text, r'Wifi kernel active time: (.*)')};"
          f"WiFi 收 {grab(text, r'Wifi data received: (.*)')},"
          f"封包收 {grab(text, r'Wifi packets received: (.*)')} / 送 {grab(text, r'Wifi packets sent: (.*)')}")

    # ------------------------------------------------ Doze timeline
    print("\n## Doze 狀態與計時(history)")
    idle = [(t, r.split("device_idle=")[1].split()[0]) for t, _, r in ev if "device_idle=" in r]
    print("- device_idle 轉換:", ", ".join(f"{fmt(t)}={s}" for t, s in idle) or "(無)")
    full = [t for t, s in idle if s == "full"]
    if full:
        note = "(重置時已在 deep idle,不能當進入時間)" if full[0] < 5000 else ""
        print(f"- 第一次進入 deep idle:{tw(full[0])}{note}")
    else:
        print("- 本次沒有進入 deep idle")
    prog = [(t, re.search(r"DeviceIdleController\.(\w+\.?\w*)", r).group(1))
            for t, _, r in ev if "+alarm" in r and "DeviceIdleController" in r]
    print("- DeviceIdle 鬧鐘:", ", ".join(f"{fmt(t)} {n}" for t, n in prog) or "(無)")
    aborts = [t for t, _, r in ev if 'active=1000:"alarm"' in r]
    print("- 因鬧鐘太近被拉回 active(active=1000:\"alarm\"):", ", ".join(tw(t) for t in aborts) or "(無)")
    fmm = [t for t, _, r in ev if "defaultScanStartTimer" in r and "+alarm" in r]
    print("- Samsung FMM(defaultScanStartTimer)鬧鐘觸發:", ", ".join(tw(t) for t in fmm) or "(無)")
    for ta in aborts:
        nxt = [f for f in fmm if f >= ta]
        if nxt:
            print(f"  - 中止點 {fmt(ta)} 之後 {(nxt[0] - ta) / 60000:.1f} 分鐘有 FMM 鬧鐘"
                  "(Doze 在鬧鐘 < min_time_to_alarm 時會放棄進入 deep idle)")
    chain = [t for t, n in prog if n == "deep.progression"]
    if chain:
        print("- deep.progression 時間:", ", ".join(fmt(t) for t in chain),
              "(成功進入前通常是相隔約 31 分的兩個)")

    # ------------------------------------------------ discharge curve
    print("\n## 放電曲線(用電池 cc;百分比不是線性,請看 mAh)")
    pts = []
    for t, _, r in ev:
        c = re.search(r"(?:^|\s)charge=(\d+)", r)
        if c:
            pts.append((t, int(c.group(1))))
    levels = []
    for t, lv, _ in ev:
        if not levels or levels[-1][1] != lv:
            levels.append((t, lv))
    print("- 電量百分比變化:", ", ".join(f"{fmt(t)}→{lv}%" for t, lv in levels))
    iv = parse_suspend(a.suspend, start_dt.year) if (a.suspend and start_dt) else None
    if len(pts) >= 2:
        seg, base = [], pts[0]
        for p in pts[1:]:
            if p[0] - base[0] >= 1800000 or p is pts[-1]:
                dh = (p[0] - base[0]) / 3600000
                if dh > 0:
                    seg.append((base[0], p[0], base[1] - p[1], (base[1] - p[1]) / dh))
                base = p
        for a0, b0, d, rate in seg:
            extra = ""
            if iv is not None:
                r = asleep_ratio(iv, start_dt + dt.timedelta(milliseconds=a0), start_dt + dt.timedelta(milliseconds=b0))
                extra = f" 電腦睡眠 {r * 100:3.0f}%"
            flag = "  <-- 偏高" if rate > 25 else ""
            print(f"  {fmt(a0)} – {fmt(b0)}  ({wall(a0)}–{wall(b0)})  {d:4.1f} mAh  {rate:5.1f} mAh/h{extra}{flag}")

        # burst detection
        bursts, i = [], 0
        while i < len(pts):
            j = i + 1
            best = None
            while j < len(pts) and pts[j][0] - pts[i][0] <= 360000:
                if pts[i][1] - pts[j][1] >= 9:
                    best = j
                j += 1
            if best:
                bursts.append((pts[i][0], pts[best][0], pts[i][1] - pts[best][1]))
                i = best
            else:
                i += 1
        print("- 突發耗電(6 分鐘內掉 ≥ 9 mAh):")
        if not bursts:
            print("  (無)")
        for t0, t1, d in bursts:
            lo, hi = t0 - 60000, t1 + 60000
            near_idle = [f"{fmt(t)}={s}" for t, s in idle if lo <= t <= hi]
            near_alarm = [f"{fmt(t)} {n}" for t, n in prog if lo <= t <= hi]
            jobs = collections.Counter()
            for t, _, r in ev:
                if lo <= t <= hi:
                    for mm in re.finditer(r"\+job=(\S+?):", r):
                        jobs[label(mm.group(1), uidmap)] += 1
            cell = any("cellular_high_tx_power" in r for t, _, r in ev if lo <= t <= hi)
            print(f"  - {tw(t0)} → {fmt(t1)}:{d:.1f} mAh;同時段:{', '.join(near_idle + near_alarm) or '無 Doze 事件'}"
                  f";job 前幾名:{', '.join(f'{k}×{v}' for k, v in jobs.most_common(4)) or '無'}"
                  f"{';有 cellular_high_tx_power' if cell else ''}")
    else:
        print("- 沒有足夠的 charge= 點")

    # ------------------------------------------------ CPU awake
    run, last, buck = False, 0, collections.Counter()
    for t, _, r in ev:
        if run:
            x = last
            while x < t:
                y = min(t, (x // 1800000 + 1) * 1800000)
                buck[int(x // 1800000)] += y - x
                x = y
        last = t
        if re.search(r"(^|\s)\+running", r):
            run = True
        if re.search(r"(^|\s)-running", r):
            run = False
    hot = [(k, v) for k, v in sorted(buck.items()) if v / 1800000 > 0.5]
    print("\n## CPU 清醒時間(每 30 分鐘)")
    print("- 清醒超過 50% 的區段:",
          ", ".join(f"{fmt(k * 1800000)}({v / 1800000 * 100:.0f}%)" for k, v in hot) or "(無)")

    # ------------------------------------------------ wake sources
    print("\n## 喚醒來源")
    own = collections.Counter()
    for _, _, r in ev:
        for m2 in re.finditer(r"wakeupap=(\S+?):", r):
            own[m2.group(1)] += 1
    print(f"- wakeupap(共 {sum(own.values())} 次):",
          ", ".join(f"{label(k, uidmap)} {v}" for k, v in own.most_common(8)))
    wr = [l.strip() for l in stats if l.startswith("  Wakeup reason")]
    for l in wr[:5]:
        print("- ", l[:150])
    kw = []
    for l in stats:
        m2 = re.match(r"^  Kernel Wake lock (\S+): (.*?) \((\d+) times\)", l)
        if m2:
            kw.append((parse_dur(m2.group(2)), m2.group(1), m2.group(2), m2.group(3)))
    kw.sort(reverse=True)
    print("- Kernel wakelock 前 5:", "; ".join(f"{n} {d}({c}次)" for _, n, d, c in kw[:5]) or "(無)")
    tags = collections.Counter()
    for _, _, r in ev:
        m2 = re.search(r"\+alarm=(\S+?):\"([^\"]*)\"", r)
        if m2 and "DeviceIdle" not in m2.group(2):
            tags[(m2.group(1), m2.group(2)[:55])] += 1
    print("- 鬧鐘觸發前 6:", "; ".join(f"{label(u, uidmap)} {n}×{c}" for (u, n), c in tags.most_common(6)))

    # ------------------------------------------------ power
    print("\n## 估算耗電(Estimated power use,模型值,只看占比;實際放電以 Discharge 為準)")
    pw = section(text, "Estimated power use (mAh):", 40)
    for l in pw[:10]:
        if l.strip():
            print("  ", l.strip()[:150])
    uid_lines = [(float(m2.group(2)), m2.group(1), l) for l in pw
                 for m2 in [re.match(r"^\s+UID (\S+): ([\d.]+)", l)] if m2]
    uid_lines.sort(reverse=True)
    print("- 耗電前 8 名 UID:", ", ".join(f"{label(u, uidmap)} {v:.2f}" for v, u, _ in uid_lines[:8]))

    # ------------------------------------------------ uids / packages of interest
    want = [x.strip() for x in a.uids.split(",") if x.strip()]
    if a.pkg:
        rev = collections.defaultdict(list)
        for u, names in uidmap.items():
            for n in names:
                rev[n].append(u)
        for p in [x.strip() for x in a.pkg.split(",") if x.strip()]:
            if p in rev:
                u = rev[p][0]
                user, app = divmod(u, 100000)
                want.append(f"u{user}a{app - 10000}" if app >= 10000 else str(u))
            else:
                print(f"(找不到套件 {p};請確認有給 --checkin)")
    if want:
        blocks = per_uid_blocks(stats)
        print("\n## 指定 UID / 套件")
        for u in dict.fromkeys(want):
            row = [l for v, uu, l in uid_lines if uu == u]
            print(f"- {label(u, uidmap)}: 估算耗電 {row[0].split(':')[1].strip() if row else '不在前列'}")
            shown = 0
            for l in blocks.get(u, []):
                if re.search(r"(Top for|Fg Service|Foreground|Total cpu time: u=|Wake lock|Job |Wi-Fi network|Background for|Cached)", l):
                    print("   ", l[:140])
                    shown += 1
                    if shown >= 8:
                        break

    # ------------------------------------------------ deviceidle
    if a.deviceidle:
        d = open(a.deviceidle, encoding="utf-8", errors="ignore").read()
        print("\n## deviceidle(摘錄)")
        for k in ["inactive_to", "idle_after_inactive_to", "min_time_to_alarm", "idle_to", "max_idle_to"]:
            print(f"- {k} = {grab(d, r'^\s+' + k + r'=(\S+)')}")
        for k in ["mState", "mLightState", "mNextAlarmTime", "mNextIdleDelay", "mCharging", "mScreenOn"]:
            print(f"- {k} = {grab(d, r'(?:^|\s)' + k + r'=(\S+)')}")
        hist_i = d.find("Idling history:")
        if hist_i >= 0:
            h = [x.strip() for x in d[hist_i:].split("\n")[1:] if re.match(r"^\s+(normal|light|deep)", x)]
            print("- Idling history 最後 10 筆:", " | ".join(h[-10:]))

    if a.mem:
        summarize_meminfo(a.mem)
    if a.battery:
        summarize_battery(a.battery)

    print("\n(原始檔請自行保留;此摘要只含上述欄位。)")


if __name__ == "__main__":
    sys.exit(main())
```
---
## 補充


**唯一的影響是您無法在 Island 空間內使用 Google 語音輸入或直接開啟工作版的 Google 搜尋，但這在隔離空間中通常完全用不到。**
```js
adb shell dumpsys meminfo | head -n 15
adb shell pm disable-user --user 10 com.google.android.googlequicksearchbox
adb shell pm enable --user 10 com.google.android.googlequicksearchbox
```

**查詢特定 Linux UID（使用者識別碼） 所對應的 Android 應用程式套件名稱（Package Name）。**
```js
adb shell pm list packages --uid 10203
```
