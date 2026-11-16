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
    scr_on = [t for t, _, r in ev if re.search(r"(^|\s)\+screen", r) and t > 60000]
    scr_off = [t for t, _, r in ev if re.search(r"(^|\s)-screen", r)]
    idle_changes = [(t, r.split("device_idle=")[1].split()[0]) for t, _, r in ev if "device_idle=" in r]
    for t_on in scr_on:
        t_off = next((x for x in scr_off if x > t_on), None)
        dur = (t_off - t_on) / 1000 if t_off else None
        left_doze = any(s in ("off",) and t_on - 1000 <= tt <= t_on + 60000 for tt, s in idle_changes)
        if dur is not None and dur < 60 and not left_doze:
            print(f"- ℹ 測試期間有短暫亮屏:{tw(t_on)},約 {dur:.1f} 秒,Doze 沒有因此退出(螢幕未解鎖;`wait_for_unlock=true` 時只有解鎖才會讓 Doze 退出),影響很小,不需要排除。")
        else:
            print(f"- ⚠ 測試期間有亮屏:{tw(t_on)}" + (f",約 {dur:.0f} 秒" if dur is not None else "")
                  + (",且 Doze 在亮屏後 1 分鐘內退出" if left_doze else "")
                  + f"。建議把「有效待機區間」當作 0 – {fmt(t_on)},之後(例如為了讓 adb 重新連線而喚醒手機)的耗電不要算進待機。")
            break
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
