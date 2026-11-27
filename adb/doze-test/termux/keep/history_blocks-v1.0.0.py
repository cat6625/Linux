#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
history_blocks.py - 把 dumpsys batterystats 的 Battery History 切成固定時間區塊，
並列出每個區塊的耗電（charge counter）、亮屏、CPU 醒著（+running）與最多的 wake_reason。
版本：v1.0.0
日期：2026-11-27

用法：
    python3 history_blocks.py raw.txt                 # 預設每 6 小時一區塊
    python3 history_blocks.py raw.txt --block 3
    python3 history_blocks.py raw.txt --start "2026-11-25 21:19:08"   # 沒有 RESET:TIME 時手動指定起點

限制：
- 只讀 Battery History 內的 charge=、+screen/-screen、+running/-running、wake_reason=；
  欄位缺少時該項顯示 N/A，不推測。
- charge= 只在 counter 變動時出現，區塊邊界以線性內插；單一區塊誤差約 ±1 個 counter 單位。
- 若 history 不含 RESET:TIME 且未指定 --start，只顯示「+N h」。
"""

from __future__ import annotations

import argparse
import bisect
import re
import sys
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

__version__ = "v1.0.0"

LINE_RE = re.compile(
    r"^\s*(0|\+?(?:\d+d)?(?:\d+h)?(?:\d+m)?(?:\d+s)?\d+ms)\s+\(\d+\)\s+(\d{3})\s+(.*)$"
)
TOK_RE = re.compile(r"\+?(?:(\d+)d)?(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?(\d+)ms")


def to_hours(tok: str) -> float:
    if tok == "0":
        return 0.0
    m = TOK_RE.match(tok)
    if not m:
        return 0.0
    d, h, mi, s, ms = (int(x or 0) for x in m.groups())
    return d * 24 + h + mi / 60 + s / 3600 + ms / 3600000


def parse(text: str):
    lines = text.replace("\r", "").splitlines()
    idx = next((i for i, l in enumerate(lines) if re.match(r"^\s*Battery History", l)), None)
    body = lines[idx + 1:] if idx is not None else lines
    reset = None
    events = []  # (hours, level, rest)
    for l in body:
        r = re.search(r"RESET:TIME:\s*(\d{4}-\d{2}-\d{2})-(\d{2})-(\d{2})-(\d{2})", l)
        if r and reset is None:
            reset = datetime.strptime(f"{r.group(1)} {r.group(2)}:{r.group(3)}:{r.group(4)}", "%Y-%m-%d %H:%M:%S")
        m = LINE_RE.match(l)
        if m:
            events.append((to_hours(m.group(1)), int(m.group(2)), m.group(3)))
    return events, reset


def main() -> None:
    ap = argparse.ArgumentParser(description="Battery History 依時間區塊統計")
    ap.add_argument("file")
    ap.add_argument("--block", type=float, default=6.0, help="區塊長度（小時，預設 6）")
    ap.add_argument("--start", default=None, help='起點時間 "YYYY-MM-DD HH:MM:SS"（沒有 RESET:TIME 時使用）')
    ap.add_argument("--top", type=int, default=1, help="每區塊列出前幾名 wake_reason（預設 1）")
    ap.add_argument("-V", "--version", action="version", version=f"%(prog)s {__version__}")
    args = ap.parse_args()

    p = Path(args.file)
    if not p.is_file():
        sys.exit(f"找不到檔案：{args.file}")
    events, reset = parse(p.read_text(encoding="utf-8", errors="replace"))
    if len(events) < 2:
        sys.exit("找不到可解析的 Battery History。")
    start = datetime.strptime(args.start, "%Y-%m-%d %H:%M:%S") if args.start else reset

    # charge 取樣
    cs: list[tuple[float, int]] = []
    for h, _lvl, rest in events:
        c = re.search(r"\bcharge=(\d+)", rest)
        if c:
            cs.append((h, int(c.group(1))))
    ch_t = [x[0] for x in cs]
    ch_v = [x[1] for x in cs]

    def charge_at(x: float) -> float | None:
        if len(cs) < 2:
            return None
        i = bisect.bisect_right(ch_t, x)
        if i == 0:
            return float(ch_v[0])
        if i >= len(cs):
            return float(ch_v[-1])
        t0, t1 = ch_t[i - 1], ch_t[i]
        return ch_v[i - 1] + (ch_v[i] - ch_v[i - 1]) * ((x - t0) / (t1 - t0) if t1 > t0 else 0.0)

    end = events[-1][0]
    screen = running = None  # 以第一次出現的旗標初始化
    # 區間積分：把事件序列轉成 (t0, t1, screen, running)
    segs = []
    prev_t = 0.0
    scr, run = False, False
    for h, _lvl, rest in events:
        if h > prev_t:
            segs.append((prev_t, h, scr, run))
            prev_t = h
        toks = rest.split()
        for tk in toks:
            if tk == "+screen":
                scr = True
            elif tk == "-screen":
                scr = False
            elif tk == "+running":
                run = True
            elif tk == "-running":
                run = False
    def seen_toggle(name: str) -> bool:  # 需同時出現 +name 與 -name，才代表 history 沒被 grep 之類濾掉
        return any(f"+{name}" in e[2].split() for e in events) and any(f"-{name}" in e[2].split() for e in events)

    has_screen = seen_toggle("screen")
    has_running = seen_toggle("running")

    wake_events = [(h, m.group(1)) for h, _l, rest in events for m in re.finditer(r'wake_reason=\d+:"([^"]+)"', rest)]

    print(f"=== Battery History 區塊統計（每 {args.block:g} h；{p.name}）===")
    if start:
        print(f"起點：{start:%Y-%m-%d %H:%M:%S}（{'RESET:TIME' if (reset and not args.start) else '--start'}）｜總長 {end:.2f} h｜charge 取樣 {len(cs)} 筆")
    else:
        print(f"起點：未知（無 RESET:TIME，可用 --start 指定）｜總長 {end:.2f} h｜charge 取樣 {len(cs)} 筆")
    print("區塊｜耗電 mAh/h｜亮屏占比｜CPU 醒著占比｜wake_reason 次數｜最多的 wake_reason")
    x = 0.0
    while x < end - 1e-6:
        y = min(x + args.block, end)
        span = y - x
        a, b = charge_at(x), charge_at(y)
        rate = f"{(a - b) / span:.1f}" if a is not None and b is not None else "N/A"
        scr_h = sum(max(0.0, min(s1, y) - max(s0, x)) for s0, s1, sc, _r in segs if sc)
        run_h = sum(max(0.0, min(s1, y) - max(s0, x)) for s0, s1, _s, rn in segs if rn)
        scr_txt = f"{scr_h / span * 100:.0f}%" if has_screen else "N/A"
        run_txt = f"{run_h / span * 100:.0f}%" if has_running else "N/A"
        wr = Counter(n for t, n in wake_events if x <= t < y)
        top = "；".join(f"{n}×{c}" for n, c in wr.most_common(args.top)) or "—"
        label = (start + timedelta(hours=x)).strftime("%m-%d %H:%M") if start else f"+{x:.1f} h"
        wr_cnt = str(sum(wr.values())) if wake_events else "N/A"
        print(f"{label}｜{rate}｜{scr_txt}｜{run_txt}｜{wr_cnt}｜{top if wake_events else 'N/A'}")
        x = y
    print("※ 耗電以 charge counter 內插，單位為該機回報單位（Samsung M14 為 4.5 mAh 一階，見 battery.py「電池服務狀態」）；"
          "亮屏／CPU 醒著由 +screen/-screen、+running/-running 積分；欄位缺少顯示 N/A。")


if __name__ == "__main__":
    main()
