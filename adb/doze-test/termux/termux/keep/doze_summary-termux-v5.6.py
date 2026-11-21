#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Termux Android Doze / BatteryStats 摘要工具 (v5.6)

v5.6 重點：讓摘要抗 AI 誤讀（手機自己估計的數字，不同 AI 會給出不同答案）
1. 新增「AI 讀取規則」與 [記錄]／[估算]／[推測] 標籤，區分事件、模型估算與推論。
2. 新增「測試條件」區塊：測試類型、機型、設計容量、充電上限（皆由使用者提供，未提供則標示未提供）。
3. 新增「容量與解析度檢查」：容量欄位互相矛盾時警示；檢查 Discharge 系列 mAh 是否為「整數百分比 × 容量」換算。
4. 新增「速率指標」以 %/h 為主，並附量化誤差範圍；新增 History charge= 電量計實測對照。
5. 新增「改善空間上限」，取代「✅ 結論」式用語；移除未經資料支持的原因猜測。
6. 新增追問模式 --section，full.txt 太大時只擷取需要的片段。
7. 保留 v5.5 的亮屏突發過濾、--reset 切片識別與 --mask 隱私遮罩。

用法：
python3 doze_summary-termux.py full.txt \
  --checkin checkin.txt --deviceidle deviceidle.txt \
  --mem mem_start.txt mem_end.txt --battery battery_start.txt battery_end.txt \
  --test-type screen-off --design-capacity 5000 --charge-limit 80% --device "機型" \
  --mask

追問模式（只輸出片段）：
python3 doze_summary-termux.py full.txt --section wakeups --top 20
python3 doze_summary-termux.py full.txt --section window --window 1h-2h --top 60

環境變數 DOZE_TEST_TYPE / DOZE_DEVICE / DOZE_DESIGN_CAP / DOZE_CHARGE_LIMIT / DOZE_NOTE 可代替參數。
只使用 Python 標準函式庫。
"""

import argparse
import collections
import datetime as dt
import io
import os
import re
import sys

WELL_KNOWN = {
    0: "root/kernel",
    1000: "system",
    1001: "radio/phone",
    1020: "mdnsd",
    1051: "netd",
    1082: "dns/clat",
    2000: "shell(adbd)",
}

BURST_MINUTES = 6
BURST_MAH = 9.0
LIGHT_DOZE_MAH_H_LIMIT = 50.0

RE_DUR = re.compile(r"(\d+)\s*(ms|d|h|m|s)")
RE_HISTORY = re.compile(
    r"^\s*(\+[\dhdms]+|0)\s+\((\d+)\)\s+(-?\d{1,3}|\?+)\s?(.*)$"
)
RE_IDLE = re.compile(r"(?:^|\s)device_idle=([^\s]+)")
RE_ALARM = re.compile(r'\+alarm=(\S+?):"([^"]*)"')
RE_CHARGE = re.compile(r"(?:^|\s)charge=(\d+)")
RE_MEM_TOTAL = re.compile(r"^\s+TOTAL\s+\d+", re.I)
RE_MEM_PID = re.compile(r"\*\* MEMINFO in pid (\d+) \[(.+?)\]")


# ============================================================
# 基礎工具與隱私遮罩
# ============================================================

def read_text(path):
    if not path:
        return ""
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return ""


def mask_sensitive_info(text):
    """自動遮蔽敏感個人資訊，同時保留網域供判斷信箱協定類型。"""
    text = re.sub(
        r"\b[A-Za-z0-9._%+-]+@([A-Za-z0-9.-]+\.[A-Za-z]{2,})\b",
        r"[EMAIL_HIDDEN@\1]",
        text,
    )
    text = re.sub(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", "[IP_HIDDEN]", text)
    text = re.sub(r"\b(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}\b", "[MAC_HIDDEN]", text)
    text = re.sub(r"\b09\d{2}-?\d{3}-?\d{3}\b", "[PHONE_HIDDEN]", text)
    text = re.sub(
        r'(SSID\s*[:=]\s*)"[^"]+"',
        r'\1"[WIFI_SSID_HIDDEN]"',
        text,
        flags=re.IGNORECASE,
    )
    return text


def parse_dur(value):
    units = {"d": 86400000, "h": 3600000, "m": 60000, "s": 1000, "ms": 1}
    total = 0
    for number, unit in RE_DUR.findall(value):
        total += int(number) * units[unit]
    return total


def fmt(milliseconds):
    milliseconds = max(0, int(milliseconds))
    return (
        f"{milliseconds // 3600000}h"
        f"{milliseconds % 3600000 // 60000:02d}m"
        f"{milliseconds % 60000 // 1000:02d}s"
    )


def grab(text, pattern, group=1, flags=re.M):
    match = re.search(pattern, text, flags)
    return match.group(group).strip() if match else None


def section(text, header, limit=80):
    pos = text.find(header)
    if pos < 0:
        return []
    return text[pos:].splitlines()[1:limit + 1]


# ============================================================
# UID / Checkin
# ============================================================

def load_uidmap(path):
    result = collections.defaultdict(list)
    if not path:
        return result
    for line in read_text(path).splitlines():
        fields = line.strip().split(",")
        if len(fields) < 6:
            continue
        if fields[2] == "i" and fields[3] == "uid":
            try:
                uid = int(fields[4])
                if fields[5] not in result[uid]:
                    result[uid].append(fields[5])
            except ValueError:
                continue
    return result


def uid_to_int(value):
    if value.isdigit():
        return int(value)
    match = re.match(r"u(\d+)a(\d+)$", value)
    if match:
        return int(match.group(1)) * 100000 + 10000 + int(match.group(2))
    return None


def label(uid_string, uidmap):
    uid = uid_to_int(uid_string)
    if uid is None:
        return uid_string
    if uid < 10000:
        if uid in WELL_KNOWN:
            return f"{uid_string}({WELL_KNOWN[uid]})"
        return uid_string
    names = uidmap.get(uid)
    if names:
        display_name = " / ".join(names[:2])
        return f"{uid_string}({display_name})"
    return uid_string


def resolve_pkg_uids(pkg_arg, uidmap):
    if not pkg_arg:
        return set()
    pkgs = [p.strip() for p in pkg_arg.split(",") if p.strip()]
    result = set()
    for uid, names in uidmap.items():
        for name in names:
            for pkg in pkgs:
                if name == pkg or name.startswith(pkg + ":"):
                    result.add(uid)
    return result


# ============================================================
# BatteryStats History
# ============================================================

def split_dump(lines):
    for index, line in enumerate(lines):
        if line.startswith("Statistics since last charge"):
            return lines[:index], lines[index:]
    return lines, []


def parse_history(lines):
    events = []
    stats = {
        "total": len(lines),
        "parsed_events": 0,
        "merged_details": 0,
        "ignored": 0,
        "unparsed": 0,
    }
    last_event = None

    for line in lines:
        stripped = line.strip()
        if not stripped:
            stats["ignored"] += 1
            continue

        match = RE_HISTORY.match(line)
        if match:
            timestamp, _, level_str, rest = match.groups()
            elapsed = 0 if timestamp == "0" else parse_dur(timestamp)
            try:
                level_int = int(level_str)
            except ValueError:
                level_int = -1
            event_data = [elapsed, level_int, [rest]]
            events.append(event_data)
            last_event = event_data
            stats["parsed_events"] += 1
        else:
            if stripped.startswith("Battery History") or "used of" in stripped:
                stats["ignored"] += 1
                continue
            if last_event is not None:
                last_event[2].append(stripped)
                stats["merged_details"] += 1
            else:
                stats["unparsed"] += 1

    formatted_events = []
    for elapsed, level, rest_parts in events:
        full_rest = " | ".join(rest_parts)
        formatted_events.append((elapsed, level, full_rest))

    formatted_events.sort(key=lambda item: item[0])
    return formatted_events, stats


def parse_idle(events):
    result = []
    for timestamp, _, rest in events:
        match = RE_IDLE.search(rest)
        if match:
            result.append((timestamp, match.group(1)))
    return result


def parse_alarm_events(events):
    result = []
    for timestamp, _, rest in events:
        if "+alarm" not in rest:
            continue
        match = RE_ALARM.search(rest)
        if match:
            result.append((timestamp, match.group(1), match.group(2)))
    return result


# ============================================================
# BatteryStats 統計（★ v5.5：動態比對亮屏誤差，避免制式註解矛盾）
# ============================================================

def print_battery_stats(text, events):
    print("\n## 電池統計與 CPU 狀態")

    match = re.search(
        r"Time on battery:\s*(.*?)\s+\(([\d.]+)%\)\s+realtime,"
        r"\s*(.*?)\s+\(([\d.]+)%\)\s+uptime",
        text
    )

    if match:
        realtime, realtime_pct, uptime, uptime_pct = match.groups()
        print(f"- 電池使用時間：{realtime}")
        print(f"- CPU 清醒時間：{uptime}（{uptime_pct}%）")
        print(f"- CPU suspend 推算比例：{100 - float(uptime_pct):.1f}%")
        if float(realtime_pct) < 99.5:
            print(f"- 注意：統計期間只有 {realtime_pct}% 屬於電池供電時間。")
    else:
        print("- ⚠ 找不到 Time on battery，無法計算 CPU 清醒比例。")

    fields = [
        ("Screen on", r"^\s+Screen on:\s*(.*)"),
        ("Discharge", r"^\s+Discharge:\s*(.*)"),
        ("Screen off discharge", r"^\s+Screen off discharge:\s*(.*)"),
        ("Screen on discharge", r"^\s+Screen on discharge:\s*(.*)"),
        ("Light doze discharge", r"Device light doze discharge:\s*(.*)"),
        ("Deep doze discharge", r"Device deep doze discharge:\s*(.*)"),
        ("Light idle", r"^\s+Device light idling:\s*(.*)"),
        ("Deep idle", r"^\s+Device full idling:\s*(.*)"),
        ("Partial wakelock", r"Total partial wakelock time:\s*(.*)"),
        ("Wi-Fi kernel active", r"Wifi kernel active time:\s*(.*)"),
        ("Wi-Fi received", r"Wifi data received:\s*(.*)"),
        ("Wi-Fi sent", r"Wifi data sent:\s*(.*)"),
    ]

    tags = {
        "Screen on": "[記錄]", "Light idle": "[記錄]", "Deep idle": "[記錄]",
        "Partial wakelock": "[記錄]", "Wi-Fi kernel active": "[記錄]",
        "Wi-Fi received": "[記錄]", "Wi-Fi sent": "[記錄]",
        "Idle mode light": "[記錄]", "Idle mode full": "[記錄]",
    }
    fields += [
        ("Idle mode light", r"^\s+Idle mode light time:\s*(.*)"),
        ("Idle mode full", r"^\s+Idle mode full time:\s*(.*)"),
    ]
    for name, pattern in fields:
        value = grab(text, pattern)
        tag = tags.get(name, "[估算·百分比換算]" if "ischarge" in name else "")
        print(f"- {tag} {name}：{value or '未知／未提供'}".replace("-  ", "- "))
    print("- ℹ Device light/full idling 與 Idle mode light/full 是不同統計口徑，"
          "次數不同不代表資料錯誤，也不能直接當成狀態切換總次數。")

    light_mah_str = grab(text, r"Device light doze discharge:\s*([\d.]+)")
    light_idle_str = grab(text, r"^\s+Device light idling:\s*(.*)")
    if light_mah_str and light_idle_str:
        try:
            light_mah = float(light_mah_str)
            light_dur_ms = parse_dur(light_idle_str)
            if light_dur_ms > 0:
                rate = light_mah / (light_dur_ms / 3600000)
                if rate > LIGHT_DOZE_MAH_H_LIMIT:
                    print(f"  ⚠ [估算] Light doze 換算 {rate:.0f} mAh/h，高於本工具的提示門檻 "
                          f"{LIGHT_DOZE_MAH_H_LIMIT:.0f}（樣本 {light_idle_str.strip()}）；"
                          f"此值由百分比步進換算，短區間不可靠，原因無法由此資料判定。")
        except ValueError:
            pass

    screen_intervals = []
    current_on = None
    for timestamp, _, rest in events:
        if re.search(r"(^|\s)\+screen", rest) and current_on is None:
            current_on = timestamp
        elif re.search(r"(^|\s)-screen", rest) and current_on is not None:
            if timestamp >= current_on:
                screen_intervals.append((current_on, timestamp))
            current_on = None
    if current_on is not None and events:
        screen_intervals.append((current_on, events[-1][0]))

    merged_screens = []
    for start, end in sorted(screen_intervals):
        if not merged_screens:
            merged_screens.append([start, end])
        else:
            prev_start, prev_end = merged_screens[-1]
            if start <= prev_end + 2000:
                merged_screens[-1][1] = max(prev_end, end)
            else:
                merged_screens.append([start, end])

    total_screen_derived_ms = 0
    for start, end in merged_screens:
        duration_ms = end - start
        total_screen_derived_ms += duration_ms
        duration = duration_ms / 1000
        if duration < 60:
            print(f"- ℹ 合併短暫亮屏區段：{fmt(start)}，持續約 {duration:.1f} 秒。")
        else:
            print(f"- ⚠ 合併有效亮屏區段：{fmt(start)}–{fmt(end)}，持續約 {duration:.1f} 秒。")

    # ★ v5.5：動態計算 History 推算亮屏與原生 Screen on 的差距
    native_screen_str = grab(text, r"^\s+Screen on:\s*(.*?)\s+\(")
    native_screen_ms = parse_dur(native_screen_str) if native_screen_str else 0
    if native_screen_ms > 0:
        diff_pct = abs(total_screen_derived_ms - native_screen_ms) / native_screen_ms * 100
        if diff_pct <= 3.0:
            note = f"兩種採樣口徑幾乎一致（誤差僅 {diff_pct:.1f}%）"
        else:
            note = f"與原生 Screen on 採樣口徑差異 {diff_pct:.1f}%"
    else:
        note = "無法取得原生 Screen on 時間，未比對"

    print(f"- ℹ History 推算亮屏區段總時長：{fmt(total_screen_derived_ms)}（{note}）")

    return merged_screens


# ============================================================
# Doze / Alarm / Job / Wakeup
# ============================================================

def print_doze(events, uidmap):
    print("\n## Doze 狀態與時間軸")

    idle = parse_idle(events)
    if not idle:
        print("- 沒有辨識到 device_idle 狀態事件。")
    else:
        print("- device_idle 轉換：", ", ".join(f"{fmt(t)}={state}" for t, state in idle))

        full = [t for t, state in idle if state == "full"]
        if full:
            print(f"- 首次記錄 full：{fmt(full[0])}")
            if full[0] == 0:
                print("  ⚠ 統計起點已是 full，不能確定本次測試何時進入。")
        else:
            print("- 沒有記錄到 full（Deep Idle）事件。")

        totals = collections.Counter()
        for index, (timestamp, state) in enumerate(idle):
            if index + 1 >= len(idle):
                continue
            end = idle[index + 1][0]
            if end >= timestamp:
                totals[state] += end - timestamp

        if totals:
            print("- 可確認的狀態持續時間（註：首個轉換事件前的初始區間未計入）：")
            for state, duration in totals.items():
                print(f"  - {state}：{fmt(duration)}")

    alarms = parse_alarm_events(events)
    print("\n## Alarm / DeviceIdle 鬧鐘")

    deviceidle_alarms = []
    for t, uid, name in alarms:
        if "DeviceIdleController" in uid or "DeviceIdleController" in name:
            deviceidle_alarms.append((t, uid, name))

    if deviceidle_alarms:
        for timestamp, _uid, name in deviceidle_alarms:
            print(f"- {fmt(timestamp)}：{name}")
    else:
        print("- 沒有辨識到 DeviceIdleController 鬧鐘。")

    progression = [t for t, _uid, name in deviceidle_alarms if "deep.progression" in name]
    if progression:
        print("- deep.progression：", ", ".join(fmt(t) for t in progression))

    normal_alarms = [(t, uid, name) for t, uid, name in alarms if "DeviceIdle" not in name]
    counter = collections.Counter((uid, name[:55]) for _, uid, name in normal_alarms)

    print("- 一般 Alarm 前 6 名：")
    for (uid, name), count in counter.most_common(6):
        print(f"  - {label(uid, uidmap)}：{name} × {count}")

    print("\n## Job / 網路活動")
    jobs = collections.Counter()
    cellular = 0

    for _, _, rest in events:
        for match in re.finditer(r"\+job=(\S+?):", rest):
            jobs[label(match.group(1), uidmap)] += 1
        if "cellular_high_tx_power" in rest:
            cellular += 1

    for name, count in jobs.most_common(10):
        print(f"- Job {name}：{count} 次")
    print(f"- cellular_high_tx_power 事件計數：{cellular} 次（基頻高功率發射狀態切換計數，非獨立喚醒次數）")

    print("\n## Wakeup AP")
    wakeups = collections.Counter()
    for _, _, rest in events:
        for match in re.finditer(r"wakeupap=(\S+?):", rest):
            wakeups[match.group(1)] += 1

    if wakeups:
        for uid, count in wakeups.most_common(8):
            print(f"- {label(uid, uidmap)}：{count} 次")
    else:
        print("- 沒有辨識到 wakeupap。")


# ============================================================
# Kernel Wakelock
# ============================================================

def print_wakelocks(text):
    print("\n## Kernel Wakelock")
    rows = []

    for line in text.splitlines():
        match = re.match(r"^\s+Kernel Wake lock (\S+): (.*?) \((\d+) times\)", line)
        if match:
            name, duration, count = match.groups()
            rows.append((parse_dur(duration), name, duration, count))

    rows.sort(reverse=True)

    if not rows:
        print("- 沒有辨識到 Kernel Wakelock 資料。")
    else:
        for _, name, duration, count in rows[:8]:
            print(f"- {name}：{duration}（{count} 次）")

    wake_reasons = [line.strip() for line in text.splitlines() if line.startswith("  Wakeup reason")]

    print("\n## Wakeup reason")
    if wake_reasons:
        for line in wake_reasons[:8]:
            print("-", line[:180])
    else:
        print("- 沒有辨識到 Wakeup reason。")


# ============================================================
# Partial Wakelock
# ============================================================

def print_partial_wakelocks(text, uidmap, top=8, width=60):
    print(f"\n## Partial Wakelock 前 {top} 名 [記錄]")
    pos = text.find("All partial wake locks:")
    if pos < 0:
        print("- 沒有辨識到 All partial wake locks 區段。")
        return

    rows = []
    for line in text[pos:].splitlines()[1:300]:
        if not line.strip():
            break
        m = re.match(r"^\s+Wake lock (\S+?) (.+?):\s*(.*)$", line)
        if not m:
            continue
        uid = m.group(1)
        name = m.group(2)
        rest = m.group(3)

        dur_ms = parse_dur(rest)
        times_match = re.search(r"\((\d+)\s+times\)", rest)
        times = int(times_match.group(1)) if times_match else 0

        if dur_ms == 0 and times == 0:
            continue

        rows.append((dur_ms, uid, name, times))

    if not rows:
        print("- 找到區段但無法解析任何 wakelock 行。")
        return

    rows.sort(reverse=True)
    for dur_ms, uid, name, times in rows[:top]:
        print(f"- {label(uid, uidmap)}：{fmt(dur_ms)}（{times} 次），{name[:width]}")


# ============================================================
# Charge Counter 放電分析（★ v5.5：修正結論用語並結合黑屏平均放電率）
# ============================================================

def _level_at(points, ts):
    level = None
    for t, lv in points:
        if t <= ts:
            level = lv
        else:
            break
    return level


def _overlaps_screen_on(start, end, merged_screens, buffer_ms=15000):
    """判斷區段是否與亮屏操作時間重疊（前後放寬 15 秒緩衝以涵蓋解鎖/鎖屏電流波動）。"""
    for s_start, s_end in merged_screens:
        if max(start, s_start - buffer_ms) <= min(end, s_end + buffer_ms):
            return True
    return False


def _find_window_culprits(events, start, end, uidmap):
    """找出在指定黑屏突發耗電時間窗內，活躍的 Job 與 Alarm 元兇。"""
    culprits = collections.Counter()
    for ts, _, rest in events:
        if start - 10000 <= ts <= end + 10000:
            for m in re.finditer(r"\+job=(\S+?):", rest):
                culprits[f"Job:{label(m.group(1), uidmap)}"] += 1
            for m in re.finditer(r'\+alarm=(\S+?):', rest):
                uid_str = m.group(1)
                if uid_str != "1000":
                    culprits[f"Alarm:{label(uid_str, uidmap)}"] += 1
    return [f"{k}({v}次)" for k, v in culprits.most_common(3)]


def print_discharge(text, events, uidmap, merged_screens=None):
    print(f"\n## 放電曲線與耗電分析（突發門檻：{BURST_MINUTES} 分鐘內 >= {BURST_MAH} mAh，已過濾開機前 5 分鐘校正期）")
    merged_screens = merged_screens or []

    # 讀取原生黑屏總放電量與黑屏總時間，計算基準待機耗電率
    screen_off_mah_str = grab(text, r"^\s+Screen off discharge:\s*([\d.]+)\s*mAh")
    screen_off_dur_str = grab(text, r"^\s+Time on battery screen off:\s*(.*?)\s+\(")
    screen_off_summary = ""
    if screen_off_mah_str and screen_off_dur_str:
        try:
            off_mah = float(screen_off_mah_str)
            off_hours = parse_dur(screen_off_dur_str) / 3600000.0
            if off_hours > 0:
                off_rate = off_mah / off_hours
                screen_off_summary = (f"黑屏期間累積耗電 {off_mah:.1f} mAh（平均 {off_rate:.1f} mAh/h）；"
                                      f"可信度見「容量與解析度檢查」")
        except ValueError:
            pass

    points = []
    for timestamp, level, rest in events:
        match = RE_CHARGE.search(rest)
        if match:
            points.append((timestamp, int(match.group(1))))

    if not points:
        print("- 沒有 charge counter 資料。")
        if screen_off_summary:
            print(f"- ℹ {screen_off_summary}。")
        return

    filtered_points = [p for p in points if p[0] >= 300000]
    if not filtered_points:
        filtered_points = points

    bursts = []
    for index in range(len(filtered_points)):
        best = None
        best_delta = 0
        for other in range(index + 1, len(filtered_points)):
            elapsed = filtered_points[other][0] - filtered_points[index][0]
            if elapsed > BURST_MINUTES * 60000:
                break
            delta = filtered_points[index][1] - filtered_points[other][1]
            if delta >= BURST_MAH and delta > best_delta:
                best = other
                best_delta = delta
        if best is not None:
            bursts.append((filtered_points[index][0], filtered_points[best][0]))

    merged = []
    for start, end in sorted(bursts):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))

    screen_off_bursts = 0
    for start, end in merged:
        lv_start = _level_at(filtered_points, start)
        lv_end = _level_at(filtered_points, end)
        if lv_start is None or lv_end is None:
            continue
        delta = lv_start - lv_end

        if _overlaps_screen_on(start, end, merged_screens):
            print(f"- ℹ 亮屏操作耗電區段（與亮屏時段重疊）：{fmt(start)}–{fmt(end)}，消耗約 {delta:.1f} mAh")
        else:
            screen_off_bursts += 1
            culprits = _find_window_culprits(events, start, end, uidmap)
            culprit_str = f" ｜ 活躍程式：{', '.join(culprits)}" if culprits else ""
            print(f"- ⚠ 純黑屏突發耗電區段：{fmt(start)}–{fmt(end)}，消耗約 {delta:.1f} mAh{culprit_str}")

    if screen_off_bursts == 0:
        print(f"- [記錄] 依門檻（{BURST_MINUTES} 分鐘內 >= {BURST_MAH} mAh，採 History charge= 欄位）"
              f"檢出的突發區段中，純黑屏時段為 0 段；這只代表「未超過門檻」，不代表黑屏待機正常。")
        if screen_off_summary:
            print(f"- [估算] {screen_off_summary}。")
    elif screen_off_summary:
        print(f"- [估算] 基準對照：{screen_off_summary}。")


# ============================================================
# CPU running
# ============================================================

def print_cpu_running(events):
    print("\n## CPU running（每 30 分鐘採樣窗口 > 50% 清醒區段）")
    if not events:
        print("- 沒有 History 事件。")
        return

    run = None
    last = None
    buckets = collections.Counter()

    for timestamp, _, rest in events:
        if last is not None and run is True:
            position = last
            while position < timestamp:
                end = min(timestamp, (position // 1800000 + 1) * 1800000)
                buckets[int(position // 1800000)] += (end - position)
                position = end

        if re.search(r"(^|\s)\+running", rest):
            run = True
        if re.search(r"(^|\s)-running", rest):
            run = False
        last = timestamp

    hot = [(b, d) for b, d in sorted(buckets.items()) if d / 1800000 > 0.5]
    if not hot:
        print("- 沒有可辨識的單一 30 分鐘窗口清醒時間超過 50% 區段。")
        return

    for bucket, duration in hot:
        start_ms = bucket * 1800000
        end_ms = (bucket + 1) * 1800000
        print(f"- {fmt(start_ms)}–{fmt(end_ms)}：{duration / 1800000 * 100:.0f}%")


# ============================================================
# Estimated power use / UID（★ v5.5：補充重複歸因與不可加總口徑說明）
# ============================================================

def print_power(text, uidmap, pkg_uids=None):
    print("\n## 估算耗電（Estimated power use）[估算]")
    lines = section(text, "Estimated power use (mAh):", 80)

    for line in lines[:12]:
        if line.strip():
            print("-", line.strip()[:180])

    discharge_str = grab(text, r"^\s+Discharge:\s*([\d.]+)\s*mAh")
    discharge_mah = float(discharge_str) if discharge_str else None

    summary_line = next((l for l in lines if "Computed drain" in l), None)
    if summary_line:
        m = re.search(
            r"Computed drain:\s*([\d.]+),\s*actual drain:\s*([\d.]+)-([\d.]+)",
            summary_line,
        )
        if m:
            computed = float(m.group(1))
            actual_low = float(m.group(2))
            actual_high = float(m.group(3))

            is_manual_reset_slice = (
                discharge_mah is not None
                and actual_low > discharge_mah * 1.8
                and abs(discharge_mah - computed) / max(discharge_mah, 1) < 0.35
            )

            if is_manual_reset_slice:
                print(f"  - ℹ [已排除假警報] Computed drain ({computed:.0f} mAh) 與本次實體放電 "
                      f"Discharge ({discharge_mah:.0f} mAh) 吻合；actual drain ({actual_low:.0f}–{actual_high:.0f} mAh) "
                      f"偏高；可能是測試前手動執行過 --reset 而該欄位仍保留較早的累計值（[推測]，未經驗證）。")
            elif computed > 0:
                ratio = actual_low / computed
                if ratio >= 3:
                    print(f"  - ⚠ [估算] Computed drain {computed:.1f} mAh 與 actual drain "
                          f"{actual_low:.0f}–{actual_high:.0f} mAh 不一致（{ratio:.1f} 倍）；"
                          f"原因無法由此資料判定，兩者都不是電流量測。")

    # ★ v5.5：明確標示電源模型歸因口徑，避免將 UID 總和與 Global 或 Discharge 直接相加比較
    print("  - 💡 [口徑說明] Estimated power use 為系統軟體估算模型（單位：mAh）；")
    print("    其中 UID 數值已包含螢幕（screen）與系統元件的分攤（smearing/proportional），")
    print("    與上方 Global 項目存在重複歸因，因此前幾名 UID 加總可能大於 Computed drain，")
    print("    僅供相對耗電排序參考，不可直接與 Global 項目相加。")

    uid_rows = []
    for line in lines:
        match = re.match(r"^\s+[Uu][Ii][Dd] (\S+): ([\d.]+)", line)
        if match:
            uid_rows.append((float(match.group(2)), match.group(1)))

    uid_rows.sort(reverse=True)
    print("- UID 耗電前 8 名 [估算·僅供相對排序]：")
    for value, uid in uid_rows[:8]:
        uid_int = uid_to_int(uid)
        marker = "  ★ 目標包" if pkg_uids and uid_int in pkg_uids else ""
        print(f"  - {label(uid, uidmap)}：{value:.2f} mAh{marker}")

    if pkg_uids:
        matched = [u for u in uid_rows if uid_to_int(u[1]) in pkg_uids]
        if not matched:
            print("  - ℹ 目標包未出現在前段 UID 耗電清單中（耗電量低於門檻，或本次統計未記錄）。")


# ============================================================
# deviceidle
# ============================================================

def print_deviceidle(path):
    if not path:
        return
    text = read_text(path)
    print("\n## deviceidle 摘錄")
    if not text:
        print("- 檔案不存在或內容為空。")
        return

    for key in ["inactive_to", "idle_after_inactive_to", "min_time_to_alarm",
                "idle_to", "max_idle_to"]:
        print(f"- {key}：", grab(text, r"^\s*" + re.escape(key) + r"=(\S+)"))

    inactive_to = grab(text, r"^\s*inactive_to=(\S+)")
    idle_to = grab(text, r"^\s*idle_to=(\S+)")
    if inactive_to in ("+1m0s0ms", "+0m30s0ms"):
        print(f"- ℹ inactive_to 為 {inactive_to}（非預設 30m–1h），可能是測試設定。")
    if idle_to in ("+15m0s0ms", "+10m0s0ms"):
        print(f"- ℹ idle_to 為 {idle_to}（非預設 1h），可能是測試設定。")

    position = text.find("Idling history:")
    if position >= 0:
        history = text[position:].splitlines()[1:]
        rows = [line.strip() for line in history if re.match(r"^\s+(normal|light|deep)", line)]
        print("- Idling history 最後 10 筆：", " | ".join(rows[-10:]) or "(無)")


# ============================================================
# meminfo
# ============================================================

def parse_mem_block(text):
    result = {}
    process = RE_MEM_PID.search(text)
    result["proc"] = process.group(2) if process else "?"

    total_line = None
    for line in text.splitlines():
        if RE_MEM_TOTAL.match(line):
            total_line = line
            break

    if not total_line:
        result["error"] = "找不到 TOTAL 欄位。"
        return result

    values = re.findall(r"\d+", total_line)
    if not values:
        result["error"] = "TOTAL 行找不到任何數字。"
        return result

    try:
        result["pss"] = int(values[0])
        result["pdirty"] = int(values[1]) if len(values) > 1 else 0
        result["pclean"] = int(values[2]) if len(values) > 2 else 0
        result["swap"] = int(values[3]) if len(values) > 3 else 0
    except ValueError:
        result["error"] = "解析 TOTAL 數值時發生數字轉換錯誤。"
        return result

    return result


def parse_stamp(path):
    text = read_text(path)
    match = re.search(r"# captured: (\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)", text)
    if match:
        try:
            return dt.datetime.strptime(match.group(1), "%Y-%m-%d %H:%M:%S")
        except ValueError:
            pass
    match = re.search(r"(\d{8})_(\d{6})", path)
    if match:
        try:
            return dt.datetime.strptime(match.group(1) + match.group(2), "%Y%m%d%H%M%S")
        except ValueError:
            pass
    return None


def print_meminfo(paths):
    print("\n## 記憶體（dumpsys meminfo，單位 MB）")
    rows = []

    for path in paths:
        text = read_text(path)
        if not text:
            print(f"- ⚠ {path}：檔案不存在或為空。")
            continue
        for block in re.split(r"(?=\*\* MEMINFO in pid)", text):
            if not block.startswith("** MEMINFO in pid"):
                continue
            data = parse_mem_block(block)
            data["path"] = path
            data["stamp"] = parse_stamp(path)
            rows.append(data)

    if not rows:
        print("- 沒有可分析的 meminfo 區塊。")
        return

    by_proc = collections.defaultdict(list)
    for data in rows:
        if not data.get("error"):
            by_proc[data["proc"]].append(data)

    for data in rows:
        if data.get("error"):
            print(f"- ⚠ {data['path']} ({data['proc']})：{data['error']}")
            continue
        stamp = data["stamp"]
        when = stamp.strftime("%m-%d %H:%M:%S") if stamp else data["path"]
        mb = lambda value: f"{value / 1024:.1f} MB"
        private = data["pdirty"] + data["pclean"]
        print(
            f"- [{when}] {data['proc']}："
            f"PSS {mb(data['pss'])}，"
            f"Private {mb(private)}，"
            f"Swap PSS {mb(data.get('swap', 0))}"
        )

    for proc, entries in by_proc.items():
        if len(entries) < 2:
            continue
        entries_sorted = sorted(entries, key=lambda d: d["stamp"] or dt.datetime.min)
        first = entries_sorted[0]
        last = entries_sorted[-1]
        if first["pss"] > 0 and last["pss"] < first["pss"] * 0.5:
            print(f"  ⚠ {proc} PSS 從 {first['pss'] / 1024:.1f} MB "
                  f"降至 {last['pss'] / 1024:.1f} MB（> 50%），"
                  f"可能被系統回收而非自然釋放。")


# ============================================================
# 電池快照對比（--battery）
# ============================================================

def parse_battery_snapshot(path):
    text = read_text(path)
    if not text:
        return None

    result = {}

    m = re.search(r"^\s*level:\s*(\d+)", text, re.M)
    if m:
        result["level"] = int(m.group(1))

    m = re.search(r"^\s*status:\s*(\d+)", text, re.M)
    if m:
        result["status"] = int(m.group(1))

    m = re.search(r"^\s*plugged:\s*(\d+)", text, re.M)
    if m:
        result["plugged"] = int(m.group(1))
    else:
        plugged = 0
        if re.search(r"^\s*AC powered:\s*true", text, re.M):
            plugged |= 1
        if re.search(r"^\s*USB powered:\s*true", text, re.M):
            plugged |= 2
        if re.search(r"^\s*Wireless powered:\s*true", text, re.M):
            plugged |= 4
        result["plugged"] = plugged

    m = re.search(r"^\s*voltage:\s*(\d+)", text, re.M)
    if m:
        result["voltage"] = int(m.group(1))

    m = re.search(r"^\s*temperature:\s*(\d+)", text, re.M)
    if m:
        result["temperature"] = int(m.group(1))

    return result or None


def print_battery_snapshots(paths, stats_ms=None):
    print("\n## 電池快照對比")
    if not paths:
        return

    snaps = []
    for path in paths:
        snap = parse_battery_snapshot(path)
        if snap:
            stamp = parse_stamp(path)
            snaps.append((path, snap, stamp))

    if not snaps:
        print("- 沒有可用的電池快照。")
        return

    for path, snap, stamp in snaps:
        when = stamp.strftime("%m-%d %H:%M:%S") if stamp else os.path.basename(path)
        parts = []
        if "level" in snap:
            parts.append(f"電量 {snap['level']}%")
        if "status" in snap:
            parts.append(f"status={snap['status']}")
        if "plugged" in snap:
            parts.append(f"plugged={snap['plugged']}")
        if "voltage" in snap:
            parts.append(f"電壓 {snap['voltage']}mV")
        if "temperature" in snap:
            parts.append(f"溫度 {snap['temperature'] / 10:.1f}°C")
        print(f"- [{when}] {os.path.basename(path)}: " + ", ".join(parts))

    if len(snaps) >= 2:
        first = snaps[0][1]
        last = snaps[-1][1]
        first_stamp = snaps[0][2]
        last_stamp = snaps[-1][2]

        if first_stamp and last_stamp:
            span = (last_stamp - first_stamp).total_seconds()
            print(f"- 快照覆蓋時長：{fmt(span * 1000)}"
                  f"（僅反映快照間隔，與 BatteryStats 累積統計口徑不同）")
            if stats_ms and span * 1000 < stats_ms * 0.9:
                print(f"  ⚠ 快照時間窗（{fmt(span * 1000)}）短於 BatteryStats 統計窗（{fmt(stats_ms)}），"
                      f"兩者不可互相換算。")
            if span < 60 and "level" in first and "level" in last:
                print(f"  ⚠ 快照間隔只有 {span:.0f} 秒，電量變化不足以反映耗電；"
                      f"請對照上方 BatteryStats 的 Discharge 值。")

        if "level" in first and "level" in last:
            diff = first["level"] - last["level"]
            print(f"- 電量變化：{first['level']}% → {last['level']}%（下降 {diff}%，註：整數百分比具取整誤差，不直接換算為精確 mAh）")

        if first.get("plugged", 0) or last.get("plugged", 0):
            print("  ⚠ 快照期間偵測到 plugged 非零（充電或 USB），"
                  "放電數據可能不純。")


# ============================================================
# v5.6 新增：讀取規則 / 測試條件 / 容量與解析度檢查 / 速率 / 實測 / 改善空間 / 追問清單
# ============================================================

TEST_TYPES = {
    "daily": "日常混合（含亮屏操作；不可當成待機速率）",
    "screen-off": "受控黑屏待機（測試期間應全程黑屏）",
    "ab": "A/B 對照（同流程只改一個變數）",
}

DISCHARGE_FIELDS = [
    ("整體 Discharge", r"^\s+Discharge:\s*([\d.]+)"),
    ("Screen off discharge", r"^\s+Screen off discharge:\s*([\d.]+)"),
    ("Screen on discharge", r"^\s+Screen on discharge:\s*([\d.]+)"),
    ("Light doze discharge", r"Device light doze discharge:\s*([\d.]+)"),
    ("Deep doze discharge", r"Device deep doze discharge:\s*([\d.]+)"),
]

CAPACITY_PRIORITY = [
    "Estimated", "Last learned", "Min learned", "Max learned",
    "Power-use Capacity", "Power-use Typical", "Power-use Rated",
    "使用者提供的設計容量",
]


def _dur_of(text, pattern):
    return parse_dur(grab(text, pattern) or "")


def _decimals(number_text):
    return len(number_text.split(".")[1]) if "." in number_text else 0


def print_reading_rules():
    print("\n## AI 讀取規則（請先讀）")
    print("- 標籤：[記錄]＝系統事件或時間，可直接引用；[估算]＝系統模型或百分比換算的 mAh，"
          "只能做相對比較，不是電流量測；[推測]＝本摘要的推論，需其他證據才能採信。")
    print("- 任何 mAh 數字都不要當成實際電流；容量欄位互相矛盾時，只使用 %/h 與電量計實測。")
    print("- 資料不足以支持的結論，請回答「資料不足」，並從文末「追問清單」選擇要補的資料；不要猜測原因。")
    print("- 不要提供一般性省電建議；只說明資料支持什麼、不支持什麼。")
    print("- 單一指標（例如 Wi-Fi kernel active 比例）不能單獨判定異常；需要基準值或同條件的開關對照。")


def print_test_conditions(args, text):
    print("\n## 測試條件")
    test_type = TEST_TYPES.get(args.test_type) if args.test_type else None
    print(f"- 測試類型：{test_type or '未提供'}")
    print(f"- 裝置：{args.device or '未提供'}")
    print(f"- 設計容量（使用者提供）：{args.design_capacity:.0f} mAh"
          if args.design_capacity else "- 設計容量（使用者提供）：未提供")
    print(f"- 充電上限（使用者提供）：{args.charge_limit or '未提供'}")
    if args.note:
        print(f"- 備註：{args.note}")

    start = grab(text, r"Start clock time:\s*(\S+)")
    total = grab(text, r"Time on battery:\s*(.*?)\s+\(")
    print(f"- [記錄] BatteryStats 統計窗：起點 {start or '未知'}，電池供電 {total or '未知'}")

    on_battery = grab(text, r"currently on battery:\s*(\w+)")
    if on_battery == "false":
        print("- [記錄] 擷取時 currently on battery: false（裝置接著電源）；"
              "此時拍攝的電量快照不屬於放電期間。")

    screen_on_ms = _dur_of(text, r"^\s+Screen on:\s*(.*?)\s+\(")
    if args.test_type == "screen-off" and screen_on_ms > 300000:
        print(f"- ⚠ 宣告為黑屏測試，但統計窗內亮屏 {fmt(screen_on_ms)}；"
              f"此份數據含亮屏耗電，不能直接當作黑屏待機結果。")


def read_capacities(text, design=None):
    caps = collections.OrderedDict()
    patterns = [
        ("Estimated", r"Estimated battery capacity:\s*([\d.]+)"),
        ("Last learned", r"Last learned battery capacity:\s*([\d.]+)"),
        ("Min learned", r"Min learned battery capacity:\s*([\d.]+)"),
        ("Max learned", r"Max learned battery capacity:\s*([\d.]+)"),
        ("Power-use Capacity", r"Capacity:\s*([\d.]+),\s*Rated:"),
        ("Power-use Rated", r"Rated:\s*([\d.]+)"),
        ("Power-use Typical", r"Typical:\s*([\d.]+)"),
    ]
    for name, pattern in patterns:
        value = grab(text, pattern)
        if value:
            try:
                number = float(value)
            except ValueError:
                continue
            if number > 0:
                caps[name] = number
    if design:
        caps["使用者提供的設計容量"] = float(design)
    return caps


def detect_percent_resolution(text, caps):
    """檢查 Discharge 系列 mAh 是否可由「整數百分比 × 某個容量」整除還原。"""
    values = []
    for name, pattern in DISCHARGE_FIELDS:
        match = re.search(pattern, text, re.M)
        if match and float(match.group(1)) > 0:
            values.append((name, float(match.group(1)), _decimals(match.group(1))))
    if len(values) < 3:
        return None

    ordered = [(n, caps[n]) for n in CAPACITY_PRIORITY if n in caps]
    for step_pct in (1.0, 0.1):
        for cap_name, cap in ordered:
            step = cap * step_pct / 100.0
            ok = True
            for _name, value, decimals in values:
                tol = 0.5 * 10 ** (-decimals) + value * 0.0004
                if step <= 2.5 * tol:
                    ok = False
                    break
                k = round(value / step)
                if abs(value - k * step) > tol:
                    ok = False
                    break
            if ok:
                fields = {name: (value, value / cap * 100.0) for name, value, _d in values}
                return {"capacity": cap, "source": cap_name,
                        "step_pct": step_pct, "fields": fields}
    return None


def print_capacity_check(text, args):
    print("\n## 容量與解析度檢查")
    caps = read_capacities(text, args.design_capacity)
    if not caps:
        print("- 沒有找到任何容量欄位。")
        return caps, None, False

    for name, value in caps.items():
        tag = "[使用者提供]" if name.startswith("使用者") else "[估算]"
        print(f"- {tag} {name}：{value:.0f} mAh")

    rounded = sorted(set(round(v) for v in caps.values()))
    conflict = rounded[-1] / rounded[0] > 1.15
    if conflict:
        print(f"- ⚠ 容量來源互相矛盾（最大／最小 = {rounded[-1] / rounded[0]:.2f} 倍）："
              f"不做「百分比 ↔ mAh」互相換算，請以 %/h 與電量計實測為準。")

    design = caps.get("使用者提供的設計容量")
    estimated = caps.get("Estimated")
    if design and estimated and estimated < design * 0.85:
        print(f"- ℹ Estimated 容量只有使用者提供設計容量的 {estimated / design * 100:.0f}%。"
              f"這是系統估算值，不等同電池健康度；原因無法由本資料判定。")
    if args.charge_limit:
        print(f"- ℹ 使用者標示充電上限為 {args.charge_limit}；"
              f"此設定對 Estimated／learned 容量的影響無法由本資料判定。")

    res = detect_percent_resolution(text, caps)
    if res:
        pieces = "、".join(f"{name} {pct:.1f}%" for name, (_mah, pct) in res["fields"].items())
        quant = res["capacity"] * res["step_pct"] / 100.0
        print(f"- [推測] Discharge 系列 mAh 可由「整數百分比 × {res['source']} 容量 "
              f"{res['capacity']:.0f}」整除還原，解析度 {res['step_pct']:g}%：{pieces}。")
        print(f"  這代表它們是百分比換算值而不是電流量測；每個欄位的量化誤差約 ±{quant:.0f} mAh"
              f"（±{res['step_pct']:g} 個百分點）。")
    else:
        print("- [推測] 未能把 Discharge 系列 mAh 還原為整齊的百分比步進；"
              "是否為百分比換算無法確認。")
    return caps, res, conflict


def print_rate_metrics(text, caps, res, conflict):
    print("\n## 速率指標（以 %/h 為主）")
    total_ms = _dur_of(text, r"Time on battery:\s*(.*?)\s+\(")
    rows = [
        ("整體", "整體 Discharge", total_ms),
        ("黑屏", "Screen off discharge", _dur_of(text, r"Time on battery screen off:\s*(.*?)\s+\(")),
        ("亮屏", "Screen on discharge", _dur_of(text, r"^\s+Screen on:\s*(.*?)\s+\(")),
        ("Light doze", "Light doze discharge", _dur_of(text, r"^\s+Device light idling:\s*(.*?)\s+\(")),
        ("Deep doze", "Deep doze discharge", _dur_of(text, r"^\s+Device full idling:\s*(.*?)\s+\(")),
    ]
    patterns = dict(DISCHARGE_FIELDS)

    fallback_cap = None
    for name in CAPACITY_PRIORITY:
        if name in caps:
            fallback_cap = (name, caps[name])
            break

    for label_text, field, duration_ms in rows:
        if duration_ms <= 0:
            continue
        hours = duration_ms / 3600000.0
        if res and field in res["fields"]:
            mah, pct = res["fields"][field]
            half = res["step_pct"]
            low = max(0.0, pct - half) / hours
            high = (pct + half) / hours
            print(f"- [推測·由百分比換算] {label_text}：{pct:.1f}% ÷ {hours:.2f}h ≈ {pct / hours:.2f} %/h"
                  f"（量化誤差範圍 {low:.2f}–{high:.2f} %/h）")
            continue
        match = re.search(patterns[field], text, re.M)
        if not match:
            continue
        mah = float(match.group(1))
        if not conflict and fallback_cap:
            pct = mah / fallback_cap[1] * 100.0
            print(f"- [推測] {label_text}：約 {pct:.1f}% ÷ {hours:.2f}h ≈ {pct / hours:.2f} %/h"
                  f"（以 {fallback_cap[0]} 容量換算，精度未知）")
        else:
            print(f"- [估算] {label_text}：{mah:.1f} mAh ÷ {hours:.2f}h ≈ {mah / hours:.1f} mAh/h"
                  f"（容量來源矛盾或無法換算為 %；僅供同裝置同流程對照）")


def print_measured_drain(events, merged_screens, text):
    print("\n## 電量計實測（History 的 charge= 欄位）")
    points = []
    for timestamp, _level, rest in events:
        match = RE_CHARGE.search(rest)
        if match:
            points.append((timestamp, int(match.group(1))))
    if len(points) < 2:
        print("- [記錄] History 中的 charge= 欄位少於 2 筆，無法做電量計實測。")
        return
    if points[0][1] > 50000:
        print(f"- ⚠ charge= 數值 {points[0][1]} 過大，可能不是 mAh 單位，已略過此項。")
        return

    first_t, first_c = points[0]
    last_t, last_c = points[-1]
    print(f"- [記錄] 電量計：{first_c} → {last_c} mAh，下降 {first_c - last_c} mAh，"
          f"涵蓋 {fmt(last_t - first_t)}（{fmt(first_t)}–{fmt(last_t)}）")

    drops = {"on": 0, "off": 0}
    hours = {"on": 0.0, "off": 0.0}
    rises = 0
    for (t1, c1), (t2, c2) in zip(points, points[1:]):
        delta = c1 - c2
        middle = (t1 + t2) / 2.0
        state = "on" if any(s <= middle <= e for s, e in merged_screens) else "off"
        hours[state] += (t2 - t1) / 3600000.0
        if delta >= 0:
            drops[state] += delta
        else:
            rises += -delta
    if rises:
        print(f"- ⚠ 期間電量計出現上升，合計 +{rises} mAh（可能有充電）；下方拆分只計下降。")
    for key, name in (("off", "黑屏"), ("on", "亮屏")):
        if hours[key] > 0:
            print(f"- [記錄·近似] {name}：{drops[key]} mAh ÷ {hours[key]:.2f}h ≈ "
                  f"{drops[key] / hours[key]:.1f} mAh/h（依事件間隔歸類，邊界有誤差）")

    discharge = grab(text, r"^\s+Discharge:\s*([\d.]+)")
    if discharge and float(discharge) > 0:
        ratio = (first_c - last_c) / float(discharge)
        verdict = "接近" if 0.8 <= ratio <= 1.25 else "明顯不同"
        print(f"- [記錄] 電量計下降 ÷ Discharge 估算 = {ratio:.2f}（{verdict}）；"
              f"charge= 的單位與解析度依裝置而異。")


def print_headroom(text, res):
    print("\n## 改善空間上限")
    fields = {}
    for name, pattern in DISCHARGE_FIELDS:
        match = re.search(pattern, text, re.M)
        if match:
            fields[name] = float(match.group(1))

    total = fields.get("整體 Discharge")
    off = fields.get("Screen off discharge")
    on = fields.get("Screen on discharge")
    if total and off is not None:
        share = off / total * 100
        extra = ""
        if res:
            half = res["step_pct"] / 100.0 * res["capacity"]
            low = max(0.0, off - half) / (total + half) * 100
            high = min(100.0, (off + half) / max(total - half, 1e-9) * 100)
            extra = f"（量化範圍 {low:.1f}–{high:.1f}%）"
        print(f"- [推測] 黑屏放電約占總放電 {share:.1f}%{extra}："
              f"即使黑屏耗電完全消除，總放電最多再少這個比例。")
        if on is not None:
            print(f"- [推測] 亮屏放電約占總放電 {on / total * 100:.1f}%。")
    light = fields.get("Light doze discharge")
    deep = fields.get("Deep doze discharge")
    if total and light is not None and deep is not None:
        print(f"- [推測] Light + Deep doze 期間放電合計約占總放電 {(light + deep) / total * 100:.1f}%"
              f"（與黑屏放電的包含關係未確認）。")

    wifi = grab(text, r"^\s+wifi:\s*([\d.]+)")
    computed = grab(text, r"Computed drain:\s*([\d.]+)")
    kernel_pct = grab(text, r"Wifi kernel active time:\s*.*?\(([\d.]+)%\)")
    if wifi and computed and float(computed) > 0:
        print(f"- [估算] Wi-Fi 模型估算耗電 {float(wifi):.2f} mAh，約占 Computed drain 的 "
              f"{float(wifi) / float(computed) * 100:.1f}%。")
    if kernel_pct:
        print(f"- [記錄] Wi-Fi kernel active 占比 {kernel_pct}%。上面兩項並列，"
              f"不能單獨證明 Wi-Fi 是或不是主因；需要同條件的 Wi-Fi 開／關對照。")

    multicast_ms = _dur_of(text, r"Total WiFi Multicast wakelock time:\s*(.*?)\s*$")
    screen_ms = _dur_of(text, r"^\s+Screen on:\s*(.*?)\s+\(")
    if multicast_ms and screen_ms:
        print(f"- [記錄] Wi-Fi Multicast wakelock 總時間 {fmt(multicast_ms)}，"
              f"亮屏時間 {fmt(screen_ms)}（比值 {multicast_ms / screen_ms:.2f}）；"
              f"是否與亮屏綁定需看分 UID 明細。")


def print_followups(args):
    script = os.path.basename(sys.argv[0])
    base = f"python3 {script} {args.full}"
    if args.checkin:
        base += f" --checkin {args.checkin}"
    print("\n## 追問清單（需要更多證據時，只從這裡點名；執行指令後貼回輸出）")
    print(f"- 喚醒來源：{base} --section wakeups --top 20")
    print(f"- 指定 App 的耗電拆解：{base} --section uid --pkg 套件名")
    print(f"- 某時段的事件：{base} --section window --window 1h-2h --top 60")
    print(f"- Partial wakelock 明細：{base} --section wakelocks --top 30")
    print(f"- Kernel wakelock：{base} --section kernel --top 20")
    print(f"- Alarm／Job 次數：{base} --section alarms --top 20（jobs 同理）")
    print(f"- 任意關鍵字（含所屬 UID）：{base} --section grep --grep \"Multicast\"")
    print(f"- 容量與放電原始欄位：{base} --section capacity")


def _uid_blocks(text):
    blocks = []
    current = None
    for line in section(text, "Estimated power use (mAh):", 800):
        match = re.match(r"^\s+[Uu][Ii][Dd] (\S+): ([\d.]+)", line)
        if match:
            current = [match.group(1), [line.rstrip()]]
            blocks.append(current)
        elif not line.strip():
            if blocks:
                break
        elif current is not None and line.startswith("      "):
            current[1].append(line.rstrip())
    return blocks


def run_section(args, stats_text, events, uidmap, pkg_uids):
    name = args.section
    top = max(1, args.top)
    print(f"# 追問資料：{name}")
    print(f"- 原始檔案：{args.full}（以下為擷取，非整份檔案）")

    if name == "capacity":
        pattern = re.compile(
            r"(?i)capacity|discharge|Time on battery|Screen on:|Computed drain|Start clock")
        count = 0
        for line in stats_text.splitlines():
            if pattern.search(line):
                print(line.rstrip()[:200])
                count += 1
                if count >= 40:
                    break

    elif name == "wakeups":
        reasons = [l.strip() for l in stats_text.splitlines() if l.startswith("  Wakeup reason")]
        print("## Wakeup reason")
        for line in reasons[:top]:
            print("-", line[:200])
        counter = collections.Counter()
        for _, _, rest in events:
            for match in re.finditer(r"wakeupap=(\S+?):", rest):
                counter[match.group(1)] += 1
        print("## Wakeup AP（History）")
        for uid, count in counter.most_common(top):
            print(f"- {label(uid, uidmap)}：{count} 次")

    elif name == "kernel":
        rows = []
        for line in stats_text.splitlines():
            match = re.match(r"^\s+Kernel Wake lock (\S+): (.*?) \((\d+) times\)", line)
            if match:
                n, duration, count = match.groups()
                rows.append((parse_dur(duration), n, duration, count))
        rows.sort(reverse=True)
        for _, n, duration, count in rows[:top]:
            print(f"- {n}：{duration}（{count} 次）")
        if not rows:
            print("- 沒有辨識到 Kernel Wakelock 資料。")

    elif name == "wakelocks":
        print_partial_wakelocks(stats_text, uidmap, top=top, width=200)

    elif name in ("alarms", "jobs"):
        counter = collections.Counter()
        if name == "alarms":
            for _, uid, n in parse_alarm_events(events):
                if "DeviceIdle" not in n:
                    counter[(label(uid, uidmap), n[:90])] += 1
            for (who, n), count in counter.most_common(top):
                print(f"- {who}：{n} × {count}")
        else:
            for _, _, rest in events:
                for match in re.finditer(r"\+job=(\S+?):([^\s,|]*)", rest):
                    counter[(label(match.group(1), uidmap), match.group(2)[:90])] += 1
            for (who, n), count in counter.most_common(top):
                print(f"- {who}：{n} × {count}")
        if not counter:
            print("- 沒有辨識到資料。")

    elif name == "uid":
        blocks = _uid_blocks(stats_text)
        if args.pkg and not pkg_uids:
            print(f"- 找不到 {args.pkg} 的 UID 映射（需要同時提供 --checkin checkin.txt）。")
            chosen = []
        elif pkg_uids:
            chosen = [b for b in blocks if uid_to_int(b[0]) in pkg_uids]
            if not chosen:
                print("- 指定套件不在 Estimated power use 清單中（耗電低於列出門檻或未記錄）。")
        else:
            chosen = blocks[:top]
        for uid, block_lines in chosen:
            print(f"## {label(uid, uidmap)}")
            for line in block_lines:
                print(line[:220])

    elif name == "window":
        if not args.window or "-" not in args.window:
            print("- 需要 --window，例如 --window 1h-2h 或 --window 30m-45m。")
        else:
            left, right = args.window.split("-", 1)
            start = 0 if left.strip() in ("", "0") else parse_dur(left)
            end = parse_dur(right)
            pattern = re.compile(args.grep, re.I) if args.grep else None
            count = 0
            for timestamp, level, rest in events:
                if start <= timestamp <= end and (pattern is None or pattern.search(rest)):
                    print(f"{fmt(timestamp)} L{level} {rest[:240]}")
                    count += 1
                    if count >= top:
                        print(f"... （已達 --top {top} 行上限）")
                        break
            if count == 0:
                print("- 該時段沒有符合的 History 事件。")

    elif name == "grep":
        if not args.grep:
            print("- 需要 --grep 關鍵字。")
        else:
            pattern = re.compile(args.grep, re.I)
            header = re.compile(r"^\s{2}(?:u\d+[as]\d+|\d+):\s*$")
            context = None
            count = 0
            for line in stats_text.splitlines():
                if header.match(line):
                    context = line.strip().rstrip(":")
                if pattern.search(line):
                    who = label(context, uidmap) if context else "-"
                    print(f"[{who}] {line.strip()[:220]}")
                    count += 1
                    if count >= max(top, 30):
                        break
            if count == 0:
                print("- 沒有符合的行。")
    else:
        print(f"- 未知的 --section：{name}")


# ============================================================
# 主程式
# ============================================================

def build_parser():
    env = os.environ.get
    parser = argparse.ArgumentParser(description="Android Doze / BatteryStats 摘要工具 (v5.6)")
    parser.add_argument("full", help="dumpsys batterystats 完整輸出")
    parser.add_argument("--pkg", default="")
    parser.add_argument("--checkin")
    parser.add_argument("--deviceidle")
    parser.add_argument("--mem", nargs="+")
    parser.add_argument("--battery", nargs="+")
    parser.add_argument("--mask", action="store_true", help="自動遮蔽 Email、IP、MAC 與手機號碼等敏感資訊")
    parser.add_argument("--test-type", choices=sorted(TEST_TYPES), default=env("DOZE_TEST_TYPE") or None,
                        help="測試類型：daily／screen-off／ab（也可用環境變數 DOZE_TEST_TYPE）")
    parser.add_argument("--device", default=env("DOZE_DEVICE") or None, help="機型（自由文字）")
    parser.add_argument("--design-capacity", type=float, default=float(env("DOZE_DESIGN_CAP") or 0) or None,
                        help="設計容量 mAh（使用者提供）")
    parser.add_argument("--charge-limit", default=env("DOZE_CHARGE_LIMIT") or None,
                        help="充電上限，例如 80%%、85%%、100%%、unknown")
    parser.add_argument("--note", default=env("DOZE_NOTE") or None, help="其他測試條件備註")
    parser.add_argument("--section", help="追問模式：capacity／wakeups／kernel／wakelocks／alarms／jobs／uid／window／grep")
    parser.add_argument("--top", type=int, default=10, help="追問模式的列數上限")
    parser.add_argument("--window", help="追問模式的時間窗，例如 1h-2h")
    parser.add_argument("--grep", help="追問模式的關鍵字（正規表示式）")
    return parser


def main():
    args = build_parser().parse_args()

    if not os.path.isfile(args.full):
        print(f"錯誤：找不到檔案 {args.full}", file=sys.stderr)
        return 2

    full_text = read_text(args.full)
    if not full_text:
        print("錯誤：BatteryStats 檔案為空。", file=sys.stderr)
        return 2

    buf = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = buf

    try:
        lines = full_text.splitlines()
        history_lines, stats_lines = split_dump(lines)
        stats_text = "\n".join(stats_lines)

        events, h_stats = parse_history(history_lines)
        uidmap = load_uidmap(args.checkin)
        pkg_uids = resolve_pkg_uids(args.pkg, uidmap)

        if args.section:
            run_section(args, stats_text, events, uidmap, pkg_uids)
        else:
            print("# Android Doze / BatteryStats 摘要 (v5.6)")
            print(f"- 原始檔案：{args.full}")
            print(f"- History 總行數：{h_stats['total']}")
            print(f"  - 成功解析事件行：{h_stats['parsed_events']}")
            print(f"  - 合併補充細節行：{h_stats['merged_details']}（Details / /proc/stat 等）")
            print(f"  - 忽略行數：{h_stats['ignored']}（空白行與標頭）")
            print(f"  - 未辨識殘存行：{h_stats['unparsed']}")

            if args.pkg and not pkg_uids:
                print(f"- ℹ 指定套件 {args.pkg} 未在 checkin.txt 中找到 UID 映射"
                      f"（可能未安裝、checkin.txt 不完整，或該 App 未出現在歷史記錄）。")

            print_reading_rules()
            print_test_conditions(args, stats_text)

            merged_screens = print_battery_stats(stats_text, events)
            caps, res, conflict = print_capacity_check(stats_text, args)
            print_rate_metrics(stats_text, caps, res, conflict)
            print_measured_drain(events, merged_screens, stats_text)
            print_headroom(stats_text, res)

            print_doze(events, uidmap)
            print_wakelocks(stats_text)
            print_partial_wakelocks(stats_text, uidmap)
            print_discharge(stats_text, events, uidmap, merged_screens)
            print_cpu_running(events)
            print_power(stats_text, uidmap, pkg_uids)
            print_deviceidle(args.deviceidle)

            if args.mem:
                print_meminfo(args.mem)

            if args.battery:
                stats_ms = _dur_of(stats_text, r"Time on battery:\s*(.*?)\s+\(")
                print_battery_snapshots(args.battery, stats_ms)

            print_followups(args)
            print("\n摘要分析完成。")
    finally:
        sys.stdout = old_stdout

    final_output = buf.getvalue()
    if args.mask:
        final_output = mask_sensitive_info(final_output)

    print(final_output, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
