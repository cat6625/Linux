#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
jobhist.py - 從 dumpsys jobscheduler 算出每個 job 的實際執行時間，並列出配額（quota）裡的長 session
版本：v1.1.0 (支援無參數直接透過 adb 讀取與 ANDROID_SERIAL)
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

__version__ = "v1.1.0"

HIST_RE = re.compile(
    r"^\s*-(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?(\d+)ms\s+(START-P|START|STOP-P|STOP):\s+#(\S+)\s+(\S+)(?:\s+(.*))?$"
)
TIMER_RE = re.compile(r"Timer\{<(\d+)>([\w.]+)\}")
SESSION_RE = re.compile(r"^\s*(\d+)\s*->\s*(\d+)\s*\((\d+)\),\s*(\d+)\s*bg jobs")


def offset_ms(h: str | None, m: str | None, s: str | None, ms: str) -> int:
    return (int(h or 0) * 3600 + int(m or 0) * 60 + int(s or 0)) * 1000 + int(ms)


def fmt_ms(ms: int) -> str:
    if ms < 1000:
        return f"{ms} ms"
    sec = ms / 1000.0
    if sec < 90:
        return f"{sec:.1f} 秒"
    return f"{sec / 60:.1f} 分鐘"


def parse_history(lines: list[str]) -> list[dict]:
    start_idx = next((i for i, l in enumerate(lines) if re.match(r"^\s*Job history:\s*$", l)), None)
    if start_idx is None:
        return []
    open_starts: dict[str, tuple[int, str]] = {}
    runs: list[dict] = []
    for l in lines[start_idx + 1:]:
        if not l.strip():
            continue
        m = HIST_RE.match(l)
        if not m:
            if not l.startswith(" "):
                break
            continue
        off = offset_ms(m.group(1), m.group(2), m.group(3), m.group(4))
        kind, key, svc, reason = m.group(5), m.group(6), m.group(7), (m.group(8) or "").strip()
        if kind.startswith("START"):
            open_starts[key] = (off, svc)
        else:
            if key in open_starts:
                s_off, s_svc = open_starts.pop(key)
                runs.append({
                    "key": key,
                    "service": s_svc,
                    "start_ago_ms": s_off,
                    "duration_ms": max(0, s_off - off),
                    "reason": reason or "(無)",
                })
    for key, (s_off, svc) in open_starts.items():
        runs.append({"key": key, "service": svc, "start_ago_ms": s_off, "duration_ms": None, "reason": "（尚未看到 STOP：可能仍在執行）"})
    return runs


def parse_sessions(lines: list[str]) -> list[dict]:
    out: list[dict] = []
    cur: str | None = None
    for l in lines:
        t = TIMER_RE.search(l)
        if t:
            cur = f"<{t.group(1)}>{t.group(2)}"
            continue
        m = SESSION_RE.match(l)
        if m and cur:
            out.append({
                "pkg": cur,
                "start": int(m.group(1)),
                "end": int(m.group(2)),
                "duration_ms": int(m.group(3)),
                "jobs": int(m.group(4)),
            })
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="分析 dumpsys jobscheduler 的 job 執行時間與配額 session")
    ap.add_argument("file", nargs="?", default=None, help="dumpsys jobscheduler 的輸出檔；省略則透過 adb 直接讀取")
    ap.add_argument("--pkg", default=None, help="只列名稱含此字串的 job / 套件（不分大小寫）")
    ap.add_argument("--min", type=float, default=0.0, help="只列執行時間 >= N 秒的項目（預設全部）")
    ap.add_argument("--top", type=int, default=20, help="每一節最多列幾筆（預設 20）")
    ap.add_argument("-V", "--version", action="version", version=f"%(prog)s {__version__}")
    args = ap.parse_args()

    if args.file:
        p = Path(args.file)
        if not p.exists():
            sys.exit(f"找不到檔案：{args.file}")
        raw_text = p.read_text(encoding="utf-8", errors="replace")
    else:
        res = subprocess.run(["adb", "shell", "dumpsys", "jobscheduler"], capture_output=True, text=True, errors="replace")
        if res.returncode != 0 or not res.stdout.strip():
            sys.exit(f"ADB 讀取失敗：{res.stderr.strip() or '無輸出（多裝置時請指定 ANDROID_SERIAL）'}")
        raw_text = res.stdout

    lines = raw_text.replace("\r", "").splitlines()
    needle = args.pkg.lower() if args.pkg else None
    min_ms = int(args.min * 1000)

    runs = parse_history(lines)
    if needle:
        runs = [r for r in runs if needle in r["service"].lower()]
    runs = [r for r in runs if (r["duration_ms"] is None or r["duration_ms"] >= min_ms)]
    runs.sort(key=lambda r: (r["duration_ms"] is None, -(r["duration_ms"] or 0)))

    print(f"=== Job history：執行時間（共 {len(runs)} 筆，列前 {args.top}）===")
    if not runs:
        print("  查無符合項目（Job history 只保留最近一段時間，較舊的紀錄會被擠掉）。")
    for r in runs[: args.top]:
        dur = fmt_ms(r["duration_ms"]) if r["duration_ms"] is not None else "未結束"
        print(f"  {dur:>10}｜{fmt_ms(r['start_ago_ms'])} 前開始｜#{r['key']} {r['service']}｜{r['reason']}")

    sessions = parse_sessions(lines)
    if needle:
        sessions = [s for s in sessions if needle in s["pkg"].lower()]
    sessions = [s for s in sessions if s["duration_ms"] >= max(min_ms, 1)]
    sessions.sort(key=lambda s: -s["duration_ms"])
    print(f"\n=== Quota 的 Saved sessions（共 {len(sessions)} 筆，列前 {args.top}）===")
    if not sessions:
        print("  查無符合項目。")
    for s in sessions[: args.top]:
        flag = "  ← 約等於 10 分鐘（JobScheduler 執行逾時）" if 590_000 <= s["duration_ms"] <= 620_000 else ""
        print(f"  {fmt_ms(s['duration_ms']):>10}｜{s['pkg']}｜{s['jobs']} 個 bg job｜elapsed {s['start']}→{s['end']}{flag}")


if __name__ == "__main__":
    main()
