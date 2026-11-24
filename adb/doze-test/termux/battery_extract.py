#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
battery_extract.py - 從 dumpsys batterystats 擷取精華並遮蔽識別資訊，方便分享給 AI 分析
版本：v2.2.0
日期：2026-11-24

v2.2.0：新增第 5 節 Wi‑Fi 統計（Wifi Statistics：kernel active / Rx / Tx / 流量 / 封包 / 狀態 / RSSI）

用法：
    python battery_extract.py m12.txt                 # 讀檔，安全分享模式
    python battery_extract.py m12.txt -o m12_safe.txt # 輸出到檔案
    python battery_extract.py                         # 無檔案時改用 adb 直接讀取
    python battery_extract.py m12.txt --raw           # 不遮蔽（僅自己看）
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

__version__ = "v2.2.0"
__date__ = "2026-11-24"

STATS_HEADER = "Statistics since last charge:"
STATS_END_MARKERS = ("Statistics since last unplugged:",)

# 第 1 節要保留的欄位（以冒號前的完整標籤比對，每個標籤只取第一筆）
SUMMARY_LABELS = (
    "System starts",
    "Estimated battery capacity",
    "Last learned battery capacity",
    "Min learned battery capacity",
    "Max learned battery capacity",
    "Time on battery",
    "Time on battery screen off",
    "Time on battery screen doze",
    "Total run time",
    "Battery time remaining",
    "Discharge",
    "Screen off discharge",
    "Screen doze discharge",
    "Screen on discharge",
    "Device light doze discharge",
    "Device deep doze discharge",
    "Start clock time",
    "Screen on",
    "Screen brightnesses",
    "Screen refresh rate",
    "Device light idling",
    "Idle mode light time",
    "Device full idling",
    "Device deep idling",
    "Idle mode full time",
    "Connectivity changes",
    "Total full wakelock time",
    "Total partial wakelock time",
    "Total WiFi Multicast wakelock Count",
    "Total WiFi Multicast wakelock time",
)
BLOCK_LABELS = {"Screen brightnesses", "Screen refresh rate"}  # 後面縮排更深的子行一併保留

POWER_HEADER_RE = re.compile(r"^\s*Estimated power use\s*(?:\(mAh\))?\s*:\s*$", re.IGNORECASE)
PARTIAL_HEADER_RE = re.compile(r"^\s*All partial wake locks?:\s*$", re.IGNORECASE)
KERNEL_HEADER_RE = re.compile(r"^\s*All kernel wake locks?:\s*$", re.IGNORECASE)
PARTIAL_LINE_RE = re.compile(r"^\s*Wake lock\s", re.IGNORECASE)
KERNEL_LINE_RE = re.compile(r"^\s*Kernel Wake lock\b", re.IGNORECASE)
OTHER_SECTION_RE = re.compile(
    r"^\s*(?:All (?:kernel|partial) wake locks?|Per-app |Battery History|All wakeup reasons)",
    re.IGNORECASE,
)


# ---------------------------------------------------------------- 遮蔽 ----

class Masker:
    """依序遮蔽 account -> email -> timestamp -> package，並統計替換次數。"""

    ACCOUNT_RE = re.compile(r"@[^\s/@:]+@(?=[A-Za-z0-9_.]+)")
    EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
    TIMESTAMP_RE = re.compile(
        r"\b\d{4}-\d{2}-\d{2}(?:[-\sT]\d{2}[-:]\d{2}(?:[-:]\d{2})?(?:\.\d+)?)?\b"
    )
    # 至少兩個點的 Java 風格識別字（com.foo.bar），前面不能是 [ . 或字元
    PKG_RE = re.compile(r"(?<![\[\w])(?:[A-Za-z_]\w*\.){2,}[A-Za-z_][\w$]*")

    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled
        self.counts: Counter[str] = Counter()

    def _sub(self, key: str, pattern: re.Pattern, repl: str, text: str) -> str:
        text, n = pattern.subn(repl, text)
        self.counts[key] += n
        return text

    def __call__(self, text: str) -> str:
        if not self.enabled:
            return text
        text = self._sub("account", self.ACCOUNT_RE, "[ACCOUNT]@", text)
        text = self._sub("email", self.EMAIL_RE, "[EMAIL]", text)
        text = self._sub("timestamp", self.TIMESTAMP_RE, "[TIMESTAMP]", text)
        text = self._sub("pkg", self.PKG_RE, "[PKG]", text)
        return text


# ---------------------------------------------------------------- 讀取 ----

def read_input(path: str | None) -> tuple[str, str]:
    if path:
        p = Path(path)
        if not p.is_file():
            sys.exit(f"找不到檔案：{path}")
        text = p.read_text(encoding="utf-8", errors="replace")
        return text.replace("\r", ""), p.name
    try:
        res = subprocess.run(
            ["adb", "shell", "dumpsys", "batterystats"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=60, check=True,
        )
    except FileNotFoundError:
        sys.exit("找不到 adb；請指定檔案，或先安裝 android-tools。")
    except subprocess.TimeoutExpired:
        sys.exit("adb 讀取逾時。")
    except subprocess.CalledProcessError as e:
        sys.exit(f"adb 讀取失敗：{(e.stderr or '').strip() or e}")
    return res.stdout.replace("\r", ""), "adb:dumpsys batterystats"


def indent_of(line: str) -> int:
    return len(line) - len(line.lstrip())


def get_region(text: str) -> str:
    """取 'Statistics since last charge:' 起算的區段；沒有則回傳全文。"""
    start = text.find(STATS_HEADER)
    if start == -1:
        return text
    region = text[start:]
    for marker in STATS_END_MARKERS:
        idx = region.find(marker, len(STATS_HEADER))
        if idx != -1:
            region = region[:idx]
    return region


# ---------------------------------------------------------------- 各節 ----

def extract_summary(lines: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    i = 0
    while i < len(lines):
        line = lines[i]
        m = re.match(r"^\s*([^:]+?):", line)
        label = m.group(1).strip() if m else None
        if label in SUMMARY_LABELS and label not in seen:
            seen.add(label)
            out.append("  " + line.strip())
            if label in BLOCK_LABELS:
                base = indent_of(line)
                j = i + 1
                while j < len(lines) and (not lines[j].strip() or indent_of(lines[j]) > base):
                    if lines[j].strip():
                        out.append("    " + lines[j].strip())
                    j += 1
                i = j
                continue
        i += 1
    return out


POWER_ITEM_RE = re.compile(
    r"^\s*(?:UID|Uid)\s+\S+:|^\s*(?:Capacity|Global)\b|^\s*[A-Za-z][\w ./-]*:\s*-?[\d.]+"
)
POWER_GLOBAL_ROW_RE = re.compile(r"\bapps:\s*-?[\d.]+")


def extract_power(lines: list[str], top_n: int) -> tuple[list[str], int, int]:
    """回傳 (輸出行, 省略項目數, 省略行數)。

    不依賴標題縮排（部分輸出的 UID 行與標題同縮排）：
    - 符合 POWER_ITEM_RE 且縮排不深於上一個項目 -> 新項目
    - 縮排比上一個項目深 -> 該項目的延續行
    - 其他 -> 區塊結束
    Capacity / Global / Global 底下的 'xxx: n apps: n' 為標題，不計入 top_n。
    """
    idx = next((i for i, l in enumerate(lines) if POWER_HEADER_RE.match(l)), None)
    if idx is None:
        return [], 0, 0

    items: list[list[str]] = []
    last_indent = -1
    for l in lines[idx + 1:]:
        if not l.strip():
            continue
        if OTHER_SECTION_RE.match(l):
            break
        ind = indent_of(l)
        if items and ind > last_indent:
            items[-1].append(l)
        elif POWER_ITEM_RE.match(l):
            items.append([l])
            last_indent = ind
        else:
            break
    if not items:
        return [], 0, 0

    out: list[str] = []
    counted = 0
    omitted_items = omitted_lines = 0
    for it in items:
        first = it[0].strip()
        is_header = (
            first.lower().startswith("capacity:")
            or first.lower() == "global"
            or bool(POWER_GLOBAL_ROW_RE.search(first))
        )
        if not is_header:
            if counted >= top_n:
                omitted_items += 1
                omitted_lines += len(it)
                continue
            counted += 1
        out.append("    " + first)
        out.extend("      " + c.strip() for c in it[1:])
    return out, omitted_items, omitted_lines


def extract_wifi(lines: list[str]) -> list[str]:
    """擷取 'Wifi Statistics:' 區塊，保留相對縮排。"""
    idx = next((i for i, l in enumerate(lines) if re.match(r"^\s*Wifi Statistics:\s*$", l, re.IGNORECASE)), None)
    if idx is None:
        return []
    base = indent_of(lines[idx])
    out: list[str] = []
    first: int | None = None
    for l in lines[idx + 1:]:
        if not l.strip():
            continue
        ind = indent_of(l)
        if ind <= base:
            break
        if first is None:
            first = ind
        out.append("  " + " " * max(0, ind - first) + l.strip())
    return out


def extract_wakelocks(
    lines: list[str], header_re: re.Pattern, line_re: re.Pattern, top_n: int
) -> tuple[list[str], int]:
    idx = next((i for i, l in enumerate(lines) if header_re.match(l)), None)
    if idx is None:
        return [], 0

    entries: list[str] = []
    entry_indent: int | None = None
    for l in lines[idx + 1:]:
        if not l.strip():
            continue
        if not line_re.match(l):
            break
        if entry_indent is None:
            entry_indent = indent_of(l)
        elif indent_of(l) != entry_indent:
            break
        entries.append("  " + l.strip())
    omitted = max(0, len(entries) - top_n)
    return entries[:top_n], omitted


# ---------------------------------------------------------------- 主程式 ----

def build_report(text: str, source: str, mask: Masker, args: argparse.Namespace) -> str:
    region = get_region(text)
    lines = region.splitlines()

    summary = extract_summary(lines)
    power, power_omit_items, power_omit_lines = extract_power(lines, args.top_power)
    partial, partial_omit = extract_wakelocks(lines, PARTIAL_HEADER_RE, PARTIAL_LINE_RE, args.top_wl)
    kernel, kernel_omit = extract_wakelocks(lines, KERNEL_HEADER_RE, KERNEL_LINE_RE, args.top_kernel)
    wifi = extract_wifi(lines)

    mode = (
        "安全分享模式（已隱藏 App 名稱並遮蔽部分識別資訊，仍須人工確認）"
        if mask.enabled else "原始模式（未遮蔽，請勿直接分享）"
    )
    out: list[str] = [
        "=== Android 電量分析精華摘要 ===",
        f"工具版本：battery_extract {__version__}",
        f"來源檔案：{source}",
        f"輸出模式：{mode}",
    ]
    if mask.enabled:
        out.append("注意：遮蔽規則無法涵蓋所有格式，分享前仍建議人工確認。")

    def section(title: str, body: list[str], omitted: int = 0, empty_msg: str = "  （查無資料）") -> None:
        out.append("")
        out.append(title)
        if not body:
            out.append(empty_msg)
            return
        out.extend(mask(l) for l in body)
        if omitted:
            out.append(f"  ... (已省略後方 {omitted} 筆項目)")

    section("## 1. 整體放電概況 (Statistics since last charge)", summary)
    section("## 2. 各硬體與 App 耗電排名 (Estimated power use)", power, power_omit_items)
    section("## 3. 背景程式喚醒鎖排名 (All partial wake locks)", partial, partial_omit)
    section("## 4. 底層硬體驅動喚醒鎖 (All kernel wake locks)", kernel, kernel_omit)
    section("## 5. Wi‑Fi 統計 (Wifi Statistics)", wifi, 0, "  （查無 Wi‑Fi 統計）")

    total_omit_lines = power_omit_lines + partial_omit + kernel_omit
    out.append("")
    out.append("## 處理統計")
    if mask.enabled:
        out.append(f"  遮蔽替換總次數：{sum(mask.counts.values())}")
        for key in ("pkg", "email", "account", "timestamp"):
            if mask.counts[key]:
                out.append(f"    - {key}：{mask.counts[key]}")
    out.append(f"  省略行數：{total_omit_lines}")
    return "\n".join(out) + "\n"


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="擷取 batterystats 精華並遮蔽識別資訊")
    ap.add_argument("file", nargs="?", help="batterystats 文字檔；省略則用 adb 讀取")
    ap.add_argument("-o", "--output", help="輸出到檔案（預設印到畫面）")
    ap.add_argument("--raw", action="store_true", help="不遮蔽（僅供自己查看）")
    ap.add_argument("--top-power", type=int, default=25, help="耗電排名保留項目數（預設 25）")
    ap.add_argument("--top-wl", type=int, default=35, help="Partial wakelock 保留筆數（預設 35）")
    ap.add_argument("--top-kernel", type=int, default=35, help="Kernel wakelock 保留筆數（預設 35）")
    ap.add_argument("-V", "--version", action="version", version=f"%(prog)s {__version__} ({__date__})")
    return ap.parse_args()


def main() -> None:
    args = parse_args()
    text, source = read_input(args.file)
    if "batterystats" not in text.lower() and STATS_HEADER not in text:
        sys.exit("輸入內容看起來不是 dumpsys batterystats 輸出。")
    report = build_report(text, source, Masker(enabled=not args.raw), args)
    if args.output:
        Path(args.output).write_text(report, encoding="utf-8")
        print(f"已輸出：{args.output}")
    else:
        sys.stdout.write(report)


if __name__ == "__main__":
    main()
