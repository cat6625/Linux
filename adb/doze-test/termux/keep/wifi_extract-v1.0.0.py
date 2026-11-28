#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
wifi_extract.py - 從 dumpsys wifi（常有數 MB 且含 SSID／MAC／IP）擷取與耗電、喚醒相關的關鍵行，並遮蔽個資後再分享。
版本：v1.0.0
日期：2026-11-27

用法：
    python3 wifi_extract.py wifi.txt                    # 讀檔
    adb shell dumpsys wifi | python3 wifi_extract.py -  # 直接從 stdin
    python3 wifi_extract.py wifi.txt --max 300 -o wifi_safe.txt

說明與限制：
- 沒有針對特定機型的格式樣本，採「關鍵字白名單」：只留名稱含 power save / DTIM / link speed / rssi / tx / rx /
  multicast / roam / scan / keepalive / suspend ... 的行，其餘一律丟棄；各機型的欄位名稱不同，可能漏掉或多留。
- 遮蔽：MAC、IPv4／IPv6、SSID／BSSID 值、email、以雙引號包住的名稱（可能是網路名稱）。遮蔽規則無法涵蓋所有格式，分享前請人工確認。
- 每個關鍵字類別各自計數；超過 --max 行時只保留前面的行並標示省略數。
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter, OrderedDict
from pathlib import Path

__version__ = "v1.0.0"

FAMILIES: "OrderedDict[str, re.Pattern]" = OrderedDict(
    [
        ("省電／DTIM", re.compile(r"power ?save|dtim|listen ?interval|low.?power|wifi ?sleep|\bPS\b", re.I)),
        ("連線品質", re.compile(r"link ?speed|frequency|\brssi\b|signal|noise|channel width|wifi standard|max supported", re.I)),
        ("封包／計數", re.compile(r"\btx(ed)?[ _]?(packets|bytes|success|retries|bad)|\brx(ed)?[ _]?(packets|bytes|success)|link ?layer ?stat|packets|retries", re.I)),
        ("多播／過濾", re.compile(r"multicast|mdns|\bnsd\b|packet ?filter|\bapf\b|ra ?filter|broadcast", re.I)),
        ("漫遊／掃描", re.compile(r"roam|scan (throttl|interval|count)|periodic scan|autojoin|\bscanning\b", re.I)),
        ("維持連線", re.compile(r"keep.?alive|idle ?mode|suspend|wake ?lock|wakelock|screen ?(on|off|state)|\bmscreen", re.I)),
        ("狀態", re.compile(r"supplicant ?state|wi-?fi ?(state|is)|connected|disconnect|validated|network ?score|ip ?config", re.I)),
    ]
)

MAC_RE = re.compile(r"\b(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}\b")
IPV4_RE = re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}(?::\d{1,5})?\b")
IPV6_RE = re.compile(r"\b(?:[0-9A-Fa-f]{1,4}:){2,7}[0-9A-Fa-f]{1,4}\b")
EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+*-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
SSID_RE = re.compile(r"((?:SSID|BSSID|ssid|bssid)\s*[:=]\s*)(\"[^\"]*\"|[^\s,;]+)")
QUOTED_RE = re.compile(r'"[^"\n]{1,64}"')


def mask(line: str) -> str:
    line = SSID_RE.sub(r"\1[SSID]", line)
    line = MAC_RE.sub("[MAC]", line)
    line = EMAIL_RE.sub("[EMAIL]", line)
    line = IPV6_RE.sub("[IP6]", line)
    line = IPV4_RE.sub("[IP]", line)
    line = QUOTED_RE.sub('"[NAME]"', line)
    return line


def main() -> None:
    ap = argparse.ArgumentParser(description="dumpsys wifi 關鍵行擷取與遮蔽")
    ap.add_argument("file", help="dumpsys wifi 輸出檔；- 表示 stdin")
    ap.add_argument("--max", type=int, default=200, help="最多輸出幾行（預設 200）")
    ap.add_argument("-o", "--output", help="輸出到檔案（預設印到畫面）")
    ap.add_argument("-V", "--version", action="version", version=f"%(prog)s {__version__}")
    args = ap.parse_args()

    if args.file == "-":
        text = sys.stdin.read()
        src = "stdin"
    else:
        p = Path(args.file)
        if not p.is_file():
            sys.exit(f"找不到檔案：{args.file}")
        text = p.read_text(encoding="utf-8", errors="replace")
        src = p.name
    lines = text.replace("\r", "").splitlines()

    counts: Counter = Counter()
    kept: list[tuple[str, str]] = []
    seen: set[str] = set()
    for l in lines:
        s = l.strip()
        if not s or len(s) > 400:
            continue
        for fam, rx in FAMILIES.items():
            if rx.search(s):
                counts[fam] += 1
                m = mask(s)
                if m not in seen:
                    seen.add(m)
                    kept.append((fam, m))
                break

    out = [
        f"=== dumpsys wifi 關鍵行（{__version__}；來源 {'[已遮蔽]' if src != 'stdin' else 'stdin'}）===",
        f"原始行數：{len(lines)}｜符合關鍵字：{sum(counts.values())}｜去重後保留：{len(kept)}",
        "各類別符合行數：" + "｜".join(f"{k} {counts[k]}" for k in FAMILIES) if counts else "各類別符合行數：無",
        "注意：關鍵字白名單，可能漏掉或多留；遮蔽規則無法涵蓋所有格式，分享前請人工確認。",
        "",
    ]
    cur = None
    shown = 0
    for fam, m in kept:
        if shown >= args.max:
            break
        if fam != cur:
            out.append(f"## {fam}")
            cur = fam
        out.append("  " + m)
        shown += 1
    if len(kept) > shown:
        out.append(f"... 已省略 {len(kept) - shown} 行（--max {args.max}）")
    result = "\n".join(out) + "\n"
    if args.output:
        Path(args.output).write_text(result, encoding="utf-8")
        print(f"已輸出：{args.output}")
    else:
        sys.stdout.write(result)


if __name__ == "__main__":
    main()
