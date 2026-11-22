#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import subprocess
import sys


def get_stats() -> str:
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
        err = (e.stderr or "").strip()
        sys.exit(f"讀取失敗：{err or e}")


def extract_summary_section(text: str) -> str:
    """只擷取 'Statistics since last charge:' 到下一個大區塊前的摘要區段，避免誤抓。"""
    start = text.find("Statistics since last charge:")
    if start == -1:
        return text
    sub = text[start:]
    # 常見的下一個段落標記
    for marker in ("\nPer-app mobile", "\nEstimated power use", "\nBattery History"):
        idx = sub.find(marker)
        if idx != -1:
            sub = sub[:idx]
            break
    return sub


def find_value(text: str, label: str) -> float | None:
    match = re.search(
        rf"^\s*{re.escape(label)}:\s*([-\d.]+)\s*mAh\b",
        text,
        re.MULTILINE,
    )
    return float(match.group(1)) if match else None


def find_raw_line(text: str, label: str) -> str | None:
    match = re.search(
        rf"^\s*{re.escape(label)}:\s*(.+)$",
        text,
        re.MULTILINE,
    )
    return match.group(1).strip() if match else None


def parse_duration_to_hours(duration_str: str) -> float | None:
    """將 '9h 48m 42s 259ms' 或 '58m 49s 755ms' 等字串轉為小時。"""
    units = {
        "d": 86400.0,
        "h": 3600.0,
        "m": 60.0,
        "s": 1.0,
        "ms": 0.001,
    }
    tokens = re.findall(r"([\d.]+)\s*(ms|d|h|m|s)(?=\s|$)", duration_str)
    if not tokens:
        return None
    total_seconds = sum(float(amount) * units[unit] for amount, unit in tokens)
    return total_seconds / 3600.0


def find_duration_hours(text: str, label: str) -> float | None:
    raw = find_raw_line(text, label)
    if not raw:
        return None
    # 優先取括號前的時間片段；若無括號則整段解析
    before_paren = raw.split("(", 1)[0].strip()
    hours = parse_duration_to_hours(before_paren)
    if hours is not None:
        return hours
    return parse_duration_to_hours(raw)


def fmt_pct(part: float | None, whole: float | None) -> str:
    if part is None or whole is None or whole <= 0:
        return "N/A"
    return f"{part / whole * 100:.1f}%"


def fmt_rate(mah: float | None, hours: float | None, ref_cap: float | None = None) -> str:
    if mah is None or hours is None or hours <= 0:
        return "N/A"
    rate = mah / hours
    if ref_cap and ref_cap > 0:
        pct_hr = rate / ref_cap * 100
        return f"{rate:.1f} mAh/h（約 {pct_hr:.2f}%/h）"
    return f"{rate:.1f} mAh/h"


def main() -> None:
    raw_text = get_stats()
    summary = extract_summary_section(raw_text)

    start_clock = find_raw_line(summary, "Start clock time")
    est_cap = find_value(summary, "Estimated battery capacity")
    min_learned = find_value(summary, "Min learned battery capacity")
    max_learned = find_value(summary, "Max learned battery capacity")

    # 基準容量優先用 Max learned（若無則退回 Estimated）
    effective_cap = max_learned if (max_learned and max_learned > 0) else est_cap

    battery_hours = find_duration_hours(summary, "Time on battery")
    screen_on_hours = find_duration_hours(summary, "Screen on")
    screen_off_hours = find_duration_hours(summary, "Time on battery screen off")

    light_idle_hours = find_duration_hours(summary, "Device light idling")
    full_idle_hours = find_duration_hours(summary, "Device full idling")
    full_wake_hours = find_duration_hours(summary, "Total full wakelock time")
    partial_wake_hours = find_duration_hours(summary, "Total partial wakelock time")

    discharge = find_value(summary, "Discharge")
    screen_on_mah = find_value(summary, "Screen on discharge")
    screen_off_mah = find_value(summary, "Screen off discharge")
    light_doze_mah = find_value(summary, "Device light doze discharge")
    deep_doze_mah = find_value(summary, "Device deep doze discharge")

    print("=== 電池與統計週期資訊 ===")
    if start_clock:
        print(f"統計起算時間：{start_clock}")
    if est_cap:
        print(f"估計電池容量：{est_cap:.0f} mAh")
    if min_learned or max_learned:
        min_s = f"{min_learned:.0f}" if min_learned else "?"
        max_s = f"{max_learned:.0f}" if max_learned else "?"
        health_s = f"（健康度約 {max_learned / est_cap * 100:.1f}%）" if (max_learned and est_cap) else ""
        print(f"學習容量範圍：{min_s} ~ {max_s} mAh{health_s}")
    if battery_hours is not None:
        print(f"電池使用總時長：{battery_hours:.2f} 小時")

    print("\n=== 整體耗電摘要 ===")
    if discharge is not None:
        print(
            f"累計放電：{discharge:.0f} mAh"
            f"｜以估計容量計：{fmt_pct(discharge, est_cap)}"
            f"｜以學習容量計：{fmt_pct(discharge, max_learned)}"
        )
        if screen_on_mah is not None and screen_off_mah is not None:
            diff = discharge - (screen_on_mah + screen_off_mah)
            print(f"亮屏 + 熄屏合計：{screen_on_mah + screen_off_mah:.0f} mAh（與 Discharge 差值：{diff:+.0f} mAh）")
    else:
        print("找不到累計放電（Discharge）資料。")

    print("\n=== 亮屏與熄屏耗電率 ===")
    if screen_on_mah is not None and screen_on_hours:
        print(
            f"亮屏（Screen on）：{screen_on_mah:.0f} mAh / {screen_on_hours:.2f} h"
            f" -> {fmt_rate(screen_on_mah, screen_on_hours, effective_cap)}"
        )
    if screen_off_mah is not None and screen_off_hours:
        print(
            f"熄屏（Screen off）：{screen_off_mah:.0f} mAh / {screen_off_hours:.2f} h"
            f" -> {fmt_rate(screen_off_mah, screen_off_hours, effective_cap)}"
        )

    print("\n=== 待機、Doze 與喚醒細節 ===")
    if light_doze_mah is not None:
        print(f"淺睡耗電（Light doze）：{light_doze_mah:.1f} mAh")
    if deep_doze_mah is not None:
        print(f"深睡耗電（Deep doze）：{deep_doze_mah:.1f} mAh")
    if screen_off_hours and screen_off_hours > 0:
        if light_idle_hours is not None:
            print(f"淺睡待機時長：{light_idle_hours:.2f} h（佔熄屏 {fmt_pct(light_idle_hours, screen_off_hours)}）")
        if full_idle_hours is not None:
            print(f"深睡待機時長：{full_idle_hours:.2f} h（佔熄屏 {fmt_pct(full_idle_hours, screen_off_hours)}）")
    if full_wake_hours is not None:
        print(f"Full wakelock 累計：{full_wake_hours * 60:.1f} 分鐘")
    if partial_wake_hours is not None:
        print(f"Partial wakelock 累計：{partial_wake_hours * 60:.1f} 分鐘")


if __name__ == "__main__":
    main()
