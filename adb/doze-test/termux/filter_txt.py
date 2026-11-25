#!/usr/bin/env python3
import argparse
import glob
import os
import re
import sys

def parse_args():
    p = argparse.ArgumentParser(description="批次過濾 .txt 關鍵字並輸出結果")
    p.add_argument("files", nargs="+", help="目標檔案或萬用字元，例如 *.txt 或 report.txt")
    p.add_argument("-k", "--keywords", nargs="+", required=True, help="要搜尋的關鍵字（任一符合即命中）")
    p.add_argument("-v", "--exclude", nargs="*", default=[], help="要排除的關鍵字")
    p.add_argument("-c", "--context", type=int, default=0, help="顯示命中行前後各 N 行（預設 0）")
    p.add_argument("-i", "--ignore-case", action="store_true", default=True, help="忽略大小寫（預設開啟）")
    p.add_argument("--case-sensitive", action="store_true", help="區分大小寫")
    p.add_argument("-o", "--output", help="將過濾結果存成指定的 .txt 檔案（不指定則直接印在螢幕）")
    return p.parse_args()

def main():
    args = parse_args()
    flags = 0 if args.case_sensitive else re.IGNORECASE

    inc_pattern = re.compile("|".join(re.escape(k) for k in args.keywords), flags)
    exc_pattern = re.compile("|".join(re.escape(k) for k in args.exclude), flags) if args.exclude else None

    matched_files = []
    for f in args.files:
        expanded = sorted(glob.glob(f))
        matched_files.extend(expanded if expanded else [f])

    out_lines = []
    total_hits = 0

    for filepath in matched_files:
        if not os.path.isfile(filepath):
            print(f"[略過] 找不到檔案：{filepath}", file=sys.stderr)
            continue

        with open(filepath, "r", encoding="utf-8", errors="replace") as fp:
            lines = fp.readlines()

        hit_indices = set()
        for idx, line in enumerate(lines):
            if inc_pattern.search(line):
                if exc_pattern and exc_pattern.search(line):
                    continue
                total_hits += 1
                start = max(0, idx - args.context)
                end = min(len(lines), idx + args.context + 1)
                for j in range(start, end):
                    hit_indices.add(j)

        if hit_indices:
            out_lines.append(f"=== {filepath} ===")
            prev = None
            for idx in sorted(hit_indices):
                if prev is not None and idx > prev + 1:
                    out_lines.append("  --")
                out_lines.append(f"{idx + 1:>5}: {lines[idx].rstrip()}")
                prev = idx
            out_lines.append("")

    summary = f"# 共掃描 {len(matched_files)} 個檔案，命中 {total_hits} 行（關鍵字：{', '.join(args.keywords)}）\n"
    result_text = summary + "\n".join(out_lines)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as out_fp:
            out_fp.write(result_text + "\n")
        print(f"已輸出至：{args.output}（共命中 {total_hits} 行）")
    else:
        print(result_text)

if __name__ == "__main__":
    main()
