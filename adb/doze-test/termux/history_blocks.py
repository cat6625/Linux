#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
history_blocks.py - 把 dumpsys batterystats 的 Battery History 切成固定時間區塊，
並列出每個區塊的耗電（charge counter）、亮屏、CPU 醒著（+running）與最多的 wake_reason。
版本：v1.1.2
日期：2026-11-27

v1.1.2：
- 「持有聯集」欄直接列出：聯集分鐘／CPU 醒著分鐘／未對應分鐘（醒著 − 聯集）；聯集只含 job 與 wake_lock_in 兩種有名稱可配對的標籤，
  具名 wake_lock 的移除在 history 中是不帶名稱的 -wake_lock，無法配對，所以「未對應」可能包含具名 wake_lock
- 新增 --jobs N：每區塊列出持有時間前 N 名（預設 1）

v1.1.1：
v1.1.1（依 M146B 真實 raw 的輸出修正）：
- 「最久的 job/wake_lock_in」不再把 uid -1 的 "screen" 螢幕鎖算進去（亮屏時它永遠最久，蓋掉真正的 job）
- 「前景 top」只統計亮屏期間：熄屏時 top 仍是桌面（launcher），不代表有人在使用
- 新增「持有聯集」：job / wake_lock_in 持有時間的聯集（分），可與「CPU 醒著」比較：聯集遠小於醒著時間，代表醒著不是由這些標籤造成

v1.1.0：
v1.1.0：
- 起點自動判斷：RESET:TIME，或（history 被截斷、第一行是 TIME:）以 TIME 行的時間減去該行的偏移；多個 TIME 行互相差超過 60 秒會警告
- 新增每區塊「最久的 job / wake_lock_in」與「前景 top 應用」（只統計 +/- 都有名稱的標籤；bare 的 -wake_lock 無法配對，不列入）
- wake_reason 欄位加上最多原因占該區塊全部喚醒的比例

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

__version__ = "v1.1.2"

LINE_RE = re.compile(
    r"^\s*(0|\+?(?:\d+d)?(?:\d+h)?(?:\d+m)?(?:\d+s)?\d+ms)\s+\(\d+\)\s+(\d{3})\s+(.*)$"
)
ANCHOR_RE = re.compile(
    r"^\s*(0|\+?(?:\d+d)?(?:\d+h)?(?:\d+m)?(?:\d+s)?\d+ms)\s+\(\d+\)\s+(RESET:TIME|TIME):\s*(\d{4}-\d{2}-\d{2})-(\d{2})-(\d{2})-(\d{2})"
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
    anchors: list[tuple[float, datetime, bool]] = []  # (偏移小時, 該行時間, 是否 RESET:TIME)
    events = []  # (hours, level, rest)
    for l in body:
        m = LINE_RE.match(l)
        if m:
            events.append((to_hours(m.group(1)), int(m.group(2)), m.group(3)))
            continue
        # RESET:TIME / TIME 行沒有電量欄位：「0 (20) RESET:TIME: 2026-11-25-21-19-06-970」
        a = ANCHOR_RE.match(l)
        if a:
            ts = datetime.strptime(f"{a.group(3)} {a.group(4)}:{a.group(5)}:{a.group(6)}", "%Y-%m-%d %H:%M:%S")
            anchors.append((to_hours(a.group(1)), ts, a.group(2) == "RESET:TIME"))
    drift = None
    if anchors:
        reset_a = next((a for a in anchors if a[2]), anchors[0])
        reset = reset_a[1] - timedelta(hours=reset_a[0])
        offs = [(a[1] - timedelta(hours=a[0])) for a in anchors]
        drift = max(abs((o - reset).total_seconds()) for o in offs)
    return events, reset, drift, bool(anchors and anchors[0][2])


def main() -> None:
    ap = argparse.ArgumentParser(description="Battery History 依時間區塊統計")
    ap.add_argument("file")
    ap.add_argument("--block", type=float, default=6.0, help="區塊長度（小時，預設 6）")
    ap.add_argument("--start", default=None, help='起點時間 "YYYY-MM-DD HH:MM:SS"（沒有 RESET:TIME 時使用）')
    ap.add_argument("--jobs", type=int, default=1, help="每區塊列出持有時間前幾名 job / wake_lock_in（預設 1）")
    ap.add_argument("--top", type=int, default=1, help="每區塊列出前幾名 wake_reason（預設 1）")
    ap.add_argument("-V", "--version", action="version", version=f"%(prog)s {__version__}")
    args = ap.parse_args()

    p = Path(args.file)
    if not p.is_file():
        sys.exit(f"找不到檔案：{args.file}")
    events, reset, drift, from_reset = parse(p.read_text(encoding="utf-8", errors="replace"))
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

    # 帶名稱的標籤：job / wake_lock_in（持有時間）與 top（前景應用）；兩端都要有名稱才配對
    TAG_RE = re.compile(r'([+-])(job|wake_lock_in|top)=([^:\s]+):"([^"]*)"')
    open_tags: dict[tuple[str, str, str], float] = {}
    hold: list[tuple[float, float, str]] = []
    fg: list[tuple[float, float, str]] = []
    for h, _l, rest in events:
        for m in TAG_RE.finditer(rest):
            sign, kind, uid, name = m.groups()
            key = (kind, uid, name)
            if kind == "wake_lock_in" and (uid == "-1" or name == "screen"):
                continue  # 螢幕鎖：亮屏期間持續持有，不是工作
            if sign == "+":
                open_tags.setdefault(key, h)
            elif key in open_tags:
                t0 = open_tags.pop(key)
                (fg if kind == "top" else hold).append((t0, h, f"{uid} {name}"))
    for (kind, uid, name), t0 in open_tags.items():
        (fg if kind == "top" else hold).append((t0, end, f"{uid} {name}"))

    screen_iv = [(s0, s1) for s0, s1, sc, _r in segs if sc]

    def screen_overlap(t0: float, t1: float) -> float:
        return sum(max(0.0, min(t1, b) - max(t0, a)) for a, b in screen_iv)

    def union_minutes(items: list[tuple[float, float, str]], x: float, y: float) -> float:
        iv = sorted((max(t0, x), min(t1, y)) for t0, t1, _n in items if min(t1, y) > max(t0, x))
        total, cur_s, cur_e = 0.0, None, None
        for a, b in iv:
            if cur_e is None or a > cur_e:
                if cur_e is not None:
                    total += cur_e - cur_s
                cur_s, cur_e = a, b
            else:
                cur_e = max(cur_e, b)
        if cur_e is not None:
            total += cur_e - cur_s
        return total * 60

    def top_overlap(items: list[tuple[float, float, str]], x: float, y: float, only_screen_on: bool = False, n: int = 1) -> str:
        acc: Counter = Counter()
        for t0, t1, nm in items:
            a, b = max(t0, x), min(t1, y)
            if b <= a:
                continue
            acc[nm] += screen_overlap(a, b) if only_screen_on else (b - a)
        acc = Counter({k: v for k, v in acc.items() if v > 0})
        if not acc:
            return "—"
        parts = []
        for nm, hrs in acc.most_common(n):
            short = nm if len(nm) <= 70 else nm[:67] + "..."
            parts.append(f"{short}（{hrs * 60:.0f} 分）")
        return "；".join(parts)

    wake_events = [(h, m.group(1)) for h, _l, rest in events for m in re.finditer(r'wake_reason=\d+:"([^"]+)"', rest)]

    print(f"=== Battery History 區塊統計（每 {args.block:g} h；{p.name}）===")
    if start:
        src = "--start" if args.start else ("RESET:TIME" if from_reset else "TIME 行（history 已被截斷，起點為保留下來的最舊紀錄）")
        print(f"起點：{start:%Y-%m-%d %H:%M:%S}（{src}）｜總長 {end:.2f} h｜charge 取樣 {len(cs)} 筆")
        if drift and drift > 60 and not args.start:
            print(f"※ 警告：history 內各 TIME 行推得的起點彼此差 {drift:.0f} 秒（可能調過系統時間），區塊時間標籤僅供參考。")
    else:
        print(f"起點：未知（無 RESET:TIME，可用 --start 指定）｜總長 {end:.2f} h｜charge 取樣 {len(cs)} 筆")
    print("區塊｜耗電 mAh/h｜亮屏占比｜CPU 醒著占比｜wake_reason 次數｜最多的 wake_reason｜最久的 job/wake_lock_in｜持有聯集｜亮屏時的前景 top")
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
        tot_wr = sum(wr.values())
        top = "；".join(f"{n}×{c}（{c / tot_wr * 100:.0f}%）" for n, c in wr.most_common(args.top)) or "—"
        label = (start + timedelta(hours=x)).strftime("%m-%d %H:%M") if start else f"+{x:.1f} h"
        wr_cnt = str(sum(wr.values())) if wake_events else "N/A"
        job_txt = top_overlap(hold, x, y, n=args.jobs) if hold else "N/A"
        if hold:
            uni = union_minutes(hold, x, y)
            awake = run_h * 60
            uni_txt = f"聯集 {uni:.0f} 分／醒著 {awake:.0f} 分／未對應 {max(0.0, awake - uni):.0f} 分" if has_running else f"聯集 {uni:.0f} 分"
        else:
            uni_txt = "N/A"
        fg_txt = top_overlap(fg, x, y, only_screen_on=True) if fg else "N/A"
        print(f"{label}｜{rate}｜{scr_txt}｜{run_txt}｜{wr_cnt}｜{top if wake_events else 'N/A'}｜{job_txt}｜{uni_txt}｜{fg_txt}")
        x = y
    print("※ 耗電以 charge counter 內插，單位為該機回報單位（Samsung M14 為 4.5 mAh 一階，見 battery.py「電池服務狀態」）；"
          "亮屏／CPU 醒著由 +screen/-screen、+running/-running 積分；欄位缺少顯示 N/A。")


if __name__ == "__main__":
    main()
