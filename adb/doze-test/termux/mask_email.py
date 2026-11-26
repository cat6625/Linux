#!/usr/bin/env python3
import re
import sys
import os
import glob

def mask_email(match):
    user = match.group(1)
    domain = match.group(2)
    if len(user) > 2:
        masked_user = f"{user[0]}***{user[-1]}"
    else:
        masked_user = f"{user[0]}***"
    return f"{masked_user}@{domain}"

if len(sys.argv) < 2:
    print("用法: python3 mask_email.py <檔名或萬用字元...>")
    print("範例: python3 mask_email.py *_report.txt")
    sys.exit(1)

pattern = r'\b([a-zA-Z0-9._%+-]+)@([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})\b'

# 收集並展開所有萬用字元參數（同時去重並保持順序）
target_files = []
for arg in sys.argv[1:]:
    matched = glob.glob(arg)
    if matched:
        for f in matched:
            if f not in target_files:
                target_files.append(f)
    elif os.path.isfile(arg) and arg not in target_files:
        target_files.append(arg)

if not target_files:
    print("找不到符合條件的檔案。")
    sys.exit(1)

count = 0
for input_file in target_files:
    # 略過目錄或已經處理過的 _masked 檔案，避免重複產生 _masked_masked
    if not os.path.isfile(input_file) or "_masked" in os.path.basename(input_file):
        continue

    base, ext = os.path.splitext(input_file)
    output_file = f"{base}_masked{ext}"

    with open(input_file, "r", encoding="utf-8") as f:
        content = f.read()

    new_content = re.sub(pattern, mask_email, content)

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(new_content)

    print(f"[完成] {input_file} -> {output_file}")
    count += 1

print(f"\n總計處理了 {count} 個檔案。")

