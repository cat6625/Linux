#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
doze_summary.py — 把 `dumpsys batterystats` 的完整輸出濃縮成約 100 行的摘要,
方便貼給 AI 分析(完整檔 600 KB–1 MB,絕大部分是和問題無關的清單)。

用法:
  python3 doze_summary.py run_full.txt
  python3 doze_summary.py run_full.txt --uids u0a1361,u0a125
  python3 doze_summary.py run_full.txt --suspend suspend.txt      # 對照電腦的睡眠時間
  python3 doze_summary.py run_full.txt --deviceidle run_deviceidle.txt

輸入:`adb shell dumpsys batterystats > run_full.txt`(含 history 與統計)。
注意:這只是摘要,原始檔請自己保留。
"""
import argparse
import collections
import datetime as dt
import re
import sys


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


# ---------------------------------------------------------------- parsing
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


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("full")
    ap.add_argument("--uids", default="", help="要特別列出的 UID,逗號分隔,例如 u0a1361,u0a125")
    ap.add_argument("--suspend", help="journalctl -b | grep -iE 'suspend|resume|sleep|PM: ' 的輸出")
    ap.add_argument("--deviceidle", help="adb shell dumpsys deviceidle 的輸出")
    a = ap.parse_args()

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
    print(f"- 統計起點:{start}")
    tob = grab(text, r"Time on battery: (.*?) \(100\.0%\) realtime, (.*?) \(([\d.]+)%\) uptime", 0)
    m = re.search(r"Time on battery: (.*?) \(100\.0%\) realtime, (.*?) \(([\d.]+)%\) uptime", text)
    dur_ms = parse_dur(m.group(1)) if m else 0
    if m:
        print(f"- 時長:{m.group(1)};CPU 清醒(uptime):{m.group(2)}({m.group(3)}%)")
    print(f"- 亮屏:{grab(text, r'^  Screen on: (.*)')}")
    print(f"- 放電 Discharge:{grab(text, r'^  Discharge: (.*)')}"
          f"(電池計數器 cc,解析度約 4.5 mAh)")
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
    print(f"- Doze 設定(若有 deviceidle 檔會列出):見下")

    # ------------------------------------------------ Doze timeline
    print("\n## Doze 狀態與計時(history)")
    idle = [(t, r.split("device_idle=")[1].split()[0]) for t, _, r in ev if "device_idle=" in r]
    print("- device_idle 轉換:", ", ".join(f"{fmt(t)}={s}" for t, s in idle) or "(無)")
    full = [t for t, s in idle if s == "full"]
    if full:
        note = "(重置時已在 deep idle,不能當進入時間)" if full[0] < 5000 else ""
        print(f"- 第一次進入 deep idle:{fmt(full[0])}{note}")
    else:
        print("- 本次沒有進入 deep idle")
    prog = [(t, re.search(r"DeviceIdleController\.(\w+\.?\w*)", r).group(1))
            for t, _, r in ev if "+alarm" in r and "DeviceIdleController" in r]
    print("- DeviceIdle 鬧鐘:", ", ".join(f"{fmt(t)} {n}" for t, n in prog) or "(無)")
    aborts = [t for t, _, r in ev if 'active=1000:"alarm"' in r]
    print("- 因鬧鐘太近被拉回 active(active=1000:\"alarm\"):", ", ".join(fmt(t) for t in aborts) or "(無)")
    fmm = [t for t, _, r in ev if "defaultScanStartTimer" in r and "+alarm" in r]
    print("- Samsung FMM(defaultScanStartTimer)鬧鐘觸發:", ", ".join(fmt(t) for t in fmm) or "(無)")
    for ta in aborts:
        nxt = [f for f in fmm if f >= ta]
        if nxt:
            print(f"  - 中止點 {fmt(ta)} 之後 {(nxt[0] - ta) / 60000:.1f} 分鐘有 FMM 鬧鐘(Doze 在鬧鐘 < min_time_to_alarm 時會放棄進入 deep idle)")
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
    if len(pts) >= 2:
        # 以約 30 分鐘為單位彙整
        seg, base = [], pts[0]
        for p in pts[1:]:
            if p[0] - base[0] >= 1800000 or p is pts[-1]:
                dh = (p[0] - base[0]) / 3600000
                if dh > 0:
                    seg.append((base[0], p[0], base[1] - p[1], (base[1] - p[1]) / dh))
                base = p
        for a0, b0, d, rate in seg:
            extra = ""
            if start_dt and a.suspend:
                iv = parse_suspend(a.suspend, start_dt.year)
                r = asleep_ratio(iv, start_dt + dt.timedelta(milliseconds=a0), start_dt + dt.timedelta(milliseconds=b0))
                extra = f" 電腦睡眠 {r * 100:3.0f}%"
            flag = "  <-- 偏高" if rate > 25 else ""
            print(f"  {fmt(a0)} – {fmt(b0)}  {d:4.1f} mAh  {rate:5.1f} mAh/h{extra}{flag}")
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
        for m in re.finditer(r"wakeupap=(\S+?):", r):
            own[m.group(1)] += 1
    print(f"- wakeupap(共 {sum(own.values())} 次):", ", ".join(f"{k} {v}" for k, v in own.most_common(8)))
    wr = [l.strip() for l in stats if l.startswith("  Wakeup reason")]
    for l in wr[:5]:
        print("- ", l[:150])
    kw = []
    for l in stats:
        m = re.match(r"^  Kernel Wake lock (\S+): (.*?) \((\d+) times\)", l)
        if m:
            kw.append((parse_dur(m.group(2)), m.group(1), m.group(2), m.group(3)))
    kw.sort(reverse=True)
    print("- Kernel wakelock 前 5:", "; ".join(f"{n} {d}({c}次)" for _, n, d, c in kw[:5]) or "(無)")
    tags = collections.Counter()
    for _, _, r in ev:
        m = re.search(r"\+alarm=(\S+?):\"([^\"]*)\"", r)
        if m and "DeviceIdle" not in m.group(2):
            tags[(m.group(1), m.group(2)[:55])] += 1
    print("- 鬧鐘觸發前 6:", "; ".join(f"{u} {n}×{c}" for (u, n), c in tags.most_common(6)))

    # ------------------------------------------------ power
    print("\n## 估算耗電(Estimated power use,模型值,只看占比)")
    pw = section(text, "Estimated power use (mAh):", 40)
    for l in pw[:10]:
        if l.strip():
            print("  ", l.strip()[:150])
    uid_lines = [(float(m.group(2)), m.group(1), l) for l in pw
                 for m in [re.match(r"^\s+UID (\S+): ([\d.]+)", l)] if m]
    uid_lines.sort(reverse=True)
    print("- 耗電前 8 名 UID:", ", ".join(f"{u} {v:.2f}" for v, u, _ in uid_lines[:8]))

    # ------------------------------------------------ uids of interest
    if a.uids:
        blocks = per_uid_blocks(stats)
        print("\n## 指定 UID")
        for u in [x.strip() for x in a.uids.split(",") if x.strip()]:
            row = [l for v, uu, l in uid_lines if uu == u]
            print(f"- {u}: 耗電 {row[0].split(':')[1].strip() if row else '不在前列'}")
            for l in blocks.get(u, [])[:8]:
                if re.search(r"(Top for|Fg Service|Foreground|Total cpu time|Wake lock|Job |Wi-Fi network|Background for)", l):
                    print("   ", l[:140])

    # ------------------------------------------------ deviceidle
    if a.deviceidle:
        d = open(a.deviceidle, encoding="utf-8", errors="ignore").read()
        print("\n## deviceidle(摘錄)")
        for k in ["inactive_to", "idle_after_inactive_to", "min_time_to_alarm", "idle_to", "max_idle_to"]:
            print(f"- {k} = {grab(d, r'(?:^|\s)' + k + r'=(\S+)')}")
        for k in ["mState", "mLightState", "mNextAlarmTime", "mNextIdleDelay", "mCharging", "mScreenOn"]:
            print(f"- {k} = {grab(d, r'(?:^|\s)' + k + r'=(\S+)')}")
        hist_i = d.find("Idling history:")
        if hist_i >= 0:
            h = [x.strip() for x in d[hist_i:].split("\n")[1:] if re.match(r"^\s+(normal|light|deep)", x)]
            print("- Idling history 最後 10 筆:", " | ".join(h[-10:]))

    print("\n(原始檔請自行保留;此摘要只含上述欄位。)")


if __name__ == "__main__":
    sys.exit(main())
