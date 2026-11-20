#!/usr/bin/env python3
"""
battery_extract.py v2.1.0
萃取 Android batterystats 報告的精華區段，產生可分享的精簡版。

預設為「安全分享模式」：隱藏套件名稱、遮蔽常見識別資訊，保留 UID。
加上 --keep-names 才會保留 App 名稱（輸出僅供自己分析，勿直接公開）。
"""
import argparse
import csv
import logging
import os
import re
import sys
from collections import Counter

VERSION = "2.1.0"
log = logging.getLogger("battery_extract")

# (section_key, 顯示標題, 比對關鍵字, 是否限制行數)
SECTIONS = [
    ("stats", "1. 整體放電概況 (Statistics since last charge)", "Statistics since last charge:", False),
    ("power_use", "2. 各硬體與 App 耗電排名 (Estimated power use)", "Estimated power use (mAh):", True),
    ("partial_wl", "3. 背景程式喚醒鎖排名 (All partial wake locks)", "All partial wake locks:", True),
    ("kernel_wl", "4. 底層硬體驅動喚醒鎖 (All kernel wake locks)", "All kernel wake locks:", True),
]
SECTION_KEYWORDS = {kw: key for key, _, kw, _ in SECTIONS}
WAKELOCK_PREFIXES = ("Wake lock", "Kernel Wake lock")
UID_RE = re.compile(r"\b(u\d+a\d+)\b")
PKG_RE = re.compile(r"\b[a-z][a-z0-9_]*(?:\.[A-Za-z0-9_]+){2,}\b")

# (規則名稱, 正則, 替換字串)；順序重要：較具體的規則先執行
MASK_RULES = [
    ("email", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"), "[EMAIL]"),
    ("timestamp", re.compile(r"\b\d{4}-\d{2}-\d{2}-\d{2}-\d{2}-\d{2}\b"), "[TIMESTAMP]"),
    ("account", re.compile(r"\b[A-Za-z0-9_.+-]+(?=@)"), "[ACCOUNT]"),
    ("mac", re.compile(r"\b(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}\b"), "[MAC]"),
    ("ipv6", re.compile(r"\b(?:[0-9A-Fa-f]{1,4}:){4,7}[0-9A-Fa-f]{1,4}\b"), "[IPV6]"),
    ("ip", re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"), "[IP]"),
    ("phone_tw", re.compile(r"(?<!\d)(?:\+886[-\s]?|0)9\d{2}[-\s]?\d{3}[-\s]?\d{3}(?!\d)"), "[PHONE]"),
    ("phone_intl", re.compile(r"\+\d{1,3}[-\s]?\d{6,12}\b"), "[PHONE]"),
    ("imei", re.compile(r"(?<!\d)\d{15}(?!\d)"), "[IMEI_OR_ID]"),
    ("ssid", re.compile(r'(?i)(SSID\s*[:=]\s*)(?:"[^"]*"|\S+)'), r"\1[WIFI_HIDDEN]"),
    ("hidden_field", re.compile(r"(?i)\b(serial|android_id|imei|bssid|account)(\s*[:=]\s*)\S+"), r"\1\2[HIDDEN]"),
]


def format_uid(uid_int):
    """將 Android UID 轉為 batterystats 常見格式，支援多使用者（user_id = uid // 100000）。"""
    user_id, app_id = divmod(uid_int, 100000)
    if app_id >= 10000:
        return f"u{user_id}a{app_id - 10000}"
    return str(uid_int)


def parse_uid_map(checkin_path, max_pkgs=2):
    if not os.path.isfile(checkin_path):
        log.warning("找不到 checkin 檔 %s，將不套用 App 名稱對照", checkin_path)
        return {}

    raw = {}
    with open(checkin_path, "r", encoding="utf-8", errors="replace", newline="") as f:
        for parts in csv.reader(f):
            if len(parts) < 6:
                continue
            record_type, entry_type = parts[2].strip(), parts[3].strip()
            raw_uid, pkg = parts[4].strip(), parts[5].strip()
            if record_type == "i" and entry_type == "uid" and pkg and raw_uid.isdigit():
                pkgs = raw.setdefault(format_uid(int(raw_uid)), [])
                if pkg not in pkgs:
                    pkgs.append(pkg)

    result = {}
    for uid, pkgs in raw.items():
        label = " / ".join(pkgs[:max_pkgs])
        if len(pkgs) > max_pkgs:
            label += f" (+{len(pkgs) - max_pkgs} more)"
        result[uid] = label

    log.info("載入 %d 筆 App 對照", len(result))
    return result


def mask_text(text):
    """依規則遮蔽文字，回傳 (遮蔽後文字, 各規則替換次數 Counter)。"""
    counts = Counter()
    for name, rx, repl in MASK_RULES:
        text, n = rx.subn(repl, text)
        if n:
            counts[name] += n
    return text, counts


def inject_app_names(line, uid_map):
    m = UID_RE.search(line)
    if not m:
        return line
    label = uid_map.get(m.group(1))
    if label:
        primary = label.split(" / ")[0].split(" (+")[0]
        if primary not in line:
            return f"{line}  --> [{label}]"
    return line


def clean_line(raw, uid_map, keep_names):
    """回傳 (清理後文字, 各規則替換次數 Counter)。"""
    counts = Counter()
    line = raw.rstrip()
    if keep_names:
        line = inject_app_names(line, uid_map)
    else:
        line, n = PKG_RE.subn("[PKG]", line)
        if n:
            counts["pkg"] += n
    line, mask_counts = mask_text(line)
    counts.update(mask_counts)
    return line, counts


def extract_sections(full_path):
    data = {key: [] for key, _, _, _ in SECTIONS}
    current = None

    with open(full_path, "r", encoding="utf-8", errors="replace") as f:
        for raw in f:
            s = raw.strip()

            hit = next((key for kw, key in SECTION_KEYWORDS.items() if kw in s), None)
            if hit is not None:
                current = hit
                continue

            if current is None:
                continue

            if s == "":
                if data[current]:
                    current = None
                continue

            # 喚醒鎖區段：遇到非喚醒鎖格式的行，且已有資料時結束
            if current in ("partial_wl", "kernel_wl") and not s.startswith(WAKELOCK_PREFIXES):
                if data[current]:
                    current = None
                continue

            data[current].append(raw)

    return data


def find_leaks(text, keep_names):
    """回傳仍符合識別規則的行號，作為遮蔽後的最後檢查。"""
    hits = []
    for i, line in enumerate(text.splitlines(), 1):
        if any(rx.search(line) for _, rx, _ in MASK_RULES):
            hits.append(i)
        elif not keep_names and PKG_RE.search(line):
            hits.append(i)
    return hits


def build_report(data, uid_map, keep_names, max_lines, source_name):
    if keep_names:
        mode = "完整模式（含 App 名稱，請勿直接公開）"
    else:
        mode = "安全分享模式（已隱藏 App 名稱並遮蔽部分識別資訊，仍須人工確認）"

    out = [
        "=== Android 電量分析精華摘要 ===",
        f"工具版本：battery_extract v{VERSION}",
        f"來源檔案：{source_name}",
        f"輸出模式：{mode}",
        "注意：遮蔽規則無法涵蓋所有格式，分享前仍建議人工確認。",
        "",
    ]
    total = Counter()
    omitted_total = 0

    for key, title, _, limit in SECTIONS:
        out.append(f"## {title}")
        raw_lines = data[key]
        if not raw_lines:
            out.append("  (此報告中未偵測到此區塊數據)")
            out.append("")
            continue

        cleaned = []
        for raw in raw_lines:
            line, counts = clean_line(raw, uid_map, keep_names)
            total.update(counts)
            cleaned.append(line)

        if limit and len(cleaned) > max_lines:
            omitted = len(cleaned) - max_lines
            omitted_total += omitted
            cleaned = cleaned[:max_lines] + [f"  ... (已省略後方 {omitted} 筆項目)"]

        out.extend(cleaned)
        out.append("")

    out.append("## 處理統計")
    out.append(f"  遮蔽替換總次數：{sum(total.values())}")
    if total:
        for name, n in total.most_common():
            out.append(f"    - {name}：{n}")
    out.append(f"  省略行數：{omitted_total}")
    return out, total, omitted_total


def run(full_path, checkin_path, output_path, max_lines, keep_names):
    if not isinstance(max_lines, int) or isinstance(max_lines, bool) or max_lines < 0:
        raise ValueError("max_lines 必須是非負整數")
    if not os.path.isfile(full_path):
        raise FileNotFoundError(f"找不到輸入檔案：{full_path}")

    uid_map = parse_uid_map(checkin_path) if keep_names else {}
    data = extract_sections(full_path)
    out_lines, total, omitted = build_report(
        data, uid_map, keep_names, max_lines, os.path.basename(full_path)
    )
    text = "\n".join(out_lines)

    leaks = find_leaks(text, keep_names)
    if leaks:
        log.warning("最後檢查發現 %d 行可能仍含識別資訊（行號：%s），請人工確認", len(leaks), leaks[:20])

    out_abs = os.path.abspath(output_path)
    out_dir = os.path.dirname(out_abs)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(out_abs, "w", encoding="utf-8") as f:
        f.write(text)

    size_kb = os.path.getsize(out_abs) / 1024
    log.info("已儲存：%s（%.1f KB）", out_abs, size_kb)
    log.info("遮蔽替換 %d 次，省略 %d 行", sum(total.values()), omitted)
    return out_abs


def build_arg_parser():
    p = argparse.ArgumentParser(description="萃取 Android batterystats 報告精華（安全分享版）")
    p.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    p.add_argument("-f", "--full", default="full.txt", help="full.txt 路徑（預設：full.txt）")
    p.add_argument("-c", "--checkin", default="checkin.txt", help="checkin.txt 路徑（預設：checkin.txt）")
    p.add_argument("-o", "--output", default="battery_for_ai.txt", help="輸出檔案路徑（預設：battery_for_ai.txt）")
    p.add_argument("-m", "--max-lines", type=int, default=35, help="各可截斷區塊最多保留行數（預設：35）")
    p.add_argument("--keep-names", action="store_true", help="保留 App 名稱（預設隱藏，僅供自行分析）")
    g = p.add_mutually_exclusive_group()
    g.add_argument("-q", "--quiet", action="store_true", help="只顯示錯誤")
    g.add_argument("-v", "--verbose", action="store_true", help="顯示除錯資訊")
    return p


def main(argv=None):
    args = build_arg_parser().parse_args(argv)
    level = logging.ERROR if args.quiet else logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=level, format="%(levelname)s: %(message)s")
    try:
        run(args.full, args.checkin, args.output, args.max_lines, args.keep_names)
    except (FileNotFoundError, ValueError, OSError) as exc:
        log.error(str(exc))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

