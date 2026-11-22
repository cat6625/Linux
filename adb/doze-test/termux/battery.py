#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import subprocess
import sys

def get_stats():
    try:
        result = subprocess.run(
            ["adb", "shell", "dumpsys", "batterystats"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.replace("\r", "")
    except FileNotFoundError:
        sys.exit("找不到 adb。請在 Termux 安裝 android-tools。")
    except subprocess.CalledProcessError as e:
        sys.exit(f"讀取失敗：{e.stderr.strip() or e}")

def find_value(text, label):
    match = re.search(
        rf"^\s*{re.escape(label)}:\s*([\d.]+)\s*mAh",
        text,
        re.MULTILINE,
    )
    return float(match.group(1)) if match else None

def find_duration_hours(text, label):
    match = re.search(
        rf"^\s*{re.escape(label)}:\s*(.*?)\s+\(",
        text,
        re.MULTILINE,
    )
    if not match:
        return None

    duration = match.group(1)
    units = {"d": 86400, "h": 3600, "m": 60, "s": 1, "ms": 0.001}
    seconds = sum(
        float(amount) * units[unit]
        for amount, unit in re.findall(r"([\d.]+)\s*(ms|d|h|m|s)\b", duration)
    )
    return seconds / 3600

text = get_stats()

capacity = find_value(text, "Estimated battery capacity")
discharge = find_value(text, "Discharge")
screen_off = find_value(text, "Screen off discharge")
screen_on = find_value(text, "Screen on discharge")
screen_off_hours = find_duration_hours(text, "Time on battery screen off")
screen_on_hours = find_duration_hours(text, "Screen on")

if capacity and discharge is not None:
    print(f"估計電池容量：{capacity:.0f} mAh")
    print(f"累計耗電：{discharge:.0f} mAh（約 {discharge / capacity * 100:.1f}%）")
else:
    print("找不到電池容量或累計耗電資料。")

if screen_on is not None and screen_on_hours:
    print(
        f"亮屏：{screen_on:.0f} mAh，"
        f"{screen_on_hours:.2f} 小時，"
        f"平均 {screen_on / screen_on_hours:.1f} mAh/小時"
    )

if screen_off is not None and screen_off_hours:
    print(
        f"熄屏：{screen_off:.0f} mAh，"
        f"{screen_off_hours:.2f} 小時，"
        f"平均 {screen_off / screen_off_hours:.1f} mAh/小時"
    )
