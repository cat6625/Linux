#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Termux Android Doze / BatteryStats 摘要工具 (v5.2 fixed)

用法：
python3 doze_summary-termux.py full.txt \
  --checkin checkin.txt \
  --deviceidle deviceidle.txt \
  --mem mem_start.txt mem_end.txt \
  --battery battery_start.txt battery_end.txt

可選：--pkg com.example.foo,com.example.bar

只使用 Python 標準函式庫。
"""

import argparse
import collections
import datetime as dt
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
HIGH_DRAIN_MAH_H = 25.0

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
# 基礎工具
# ============================================================

def read_text(path):
    if not path:
        return ""
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return ""


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
        return f"{uid_string}({names[0]})"
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
# BatteryStats 統計
# ============================================================

def print_battery_stats(text, events):
    print("\n## 電池統計與 CPU 状態")

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
        ("Light doze discharge", r"Device light doze discharge:\s*(.*)"),
        ("Deep doze discharge", r"Device deep doze discharge:\s*(.*)"),
        ("Light idle", r"^\s+Device light idling:\s*(.*)"),
        ("Deep idle", r"^\s+Device full idling:\s*(.*)"),
        ("Partial wakelock", r"Total partial wakelock time:\s*(.*)"),
        ("Wi-Fi kernel active", r"Wifi kernel active time:\s*(.*)"),
        ("Wi-Fi received", r"Wifi data received:\s*(.*)"),
        ("Wi-Fi sent", r"Wifi data sent:\s*(.*)"),
    ]

    for name, pattern in fields:
        value = grab(text, pattern)
        print(f"- {name}：{value or '未知／未提供'}")

    print("\n  🔍 [原始欄位對照] Discharge 區段原始文字：")
    for line in text.splitlines():
        if "Discharge:" in line or "Discharge screen" in line:
            print(f"    > {line.strip()}")

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

    print(f"- ℹ History 推算亮屏區段總時長：{fmt(total_screen_derived_ms)}"
          f"（註：與 BatteryStats 原生 Screen on 採樣口徑不同）")


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
            print("- 可確認的狀態持續時間：")
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
    print(f"- cellular_high_tx_power 事件：{cellular} 次")

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
# Charge Counter 放電分析
# ============================================================

def _level_at(points, ts):
    level = None
    for t, lv in points:
        if t <= ts:
            level = lv
        else:
            break
    return level


def print_discharge(events, uidmap):
    print("\n## 放電曲線與耗電分析（已過濾開機校正期）")

    points = []
    for timestamp, level, rest in events:
        match = RE_CHARGE.search(rest)
        if match:
            points.append((timestamp, int(match.group(1))))

    if not points:
        print("- 沒有 charge counter 資料。")
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

    if not bursts:
        print("- 經防誤判過濾後：沒有符合門檻的異常突發耗電事件。")
        return

    merged = []
    for start, end in sorted(bursts):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))

    for start, end in merged:
        lv_start = _level_at(filtered_points, start)
        lv_end = _level_at(filtered_points, end)
        if lv_start is None or lv_end is None:
            continue
        delta = lv_start - lv_end
        print(f"- ⚠ 疑似突發耗電區段：{fmt(start)}–{fmt(end)}，消耗約 {delta:.1f} mAh")


# ============================================================
# CPU running
# ============================================================

def print_cpu_running(events):
    print("\n## CPU running（每 30 分鐘）")
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
        print("- 沒有可辨識的清醒時間超過 50% 區段。")
        return

    for bucket, duration in hot:
        print(f"- {fmt(bucket * 1800000)}：{duration / 1800000 * 100:.0f}%")


# ============================================================
# Estimated power use / UID
# ============================================================

def print_power(text, uidmap, pkg_uids=None):
    print("\n## 估算耗電（Estimated power use）")
    lines = section(text, "Estimated power use (mAh):", 80)

    for line in lines[:12]:
        if line.strip():
            print("-", line.strip()[:180])

    # Computed vs actual drain 警告（MIUI powerkeeper 干擾的典型症狀）
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
            if computed > 0 and actual_low / computed >= 3:
                print(f"  - ⚠ BatteryStats 模型只記錄到 {computed:.1f} mAh，"
                      f"但依電量推算實際放電 {actual_low:.0f}–{actual_high:.0f} mAh"
                      f"（差 {actual_low / computed:.1f} 倍）。")
                print("    常見原因：MIUI powerkeeper 或廠商電源管理器覆寫了 BatteryStats；"
                      "請以 actual drain 為準。")

    print("  - 💡 [說明] Discharge 為 BatteryStats 記錄的放電量；")
    print("    若此欄位取自 UAh 紀錄且裝置支援 coulomb counter，則基於電量計讀數，")
    print("    與 actual drain 的軟體模型估算範圍可能存在口徑或區間上的差異。")

    uid_rows = []
    for line in lines:
        match = re.match(r"^\s+[Uu][Ii][Dd] (\S+): ([\d.]+)", line)
        if match:
            uid_rows.append((float(match.group(2)), match.group(1)))

    uid_rows.sort(reverse=True)
    print("- UID 耗電前 8 名：")
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


def print_battery_snapshots(paths):
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
            if span < 60 and "level" in first and "level" in last:
                print(f"  ⚠ 快照間隔只有 {span:.0f} 秒，電量變化不足以反映耗電；"
                      f"請對照上方 BatteryStats 的 Discharge 值。")

        if "level" in first and "level" in last:
            diff = first["level"] - last["level"]
            print(f"- 電量變化：{first['level']}% → {last['level']}%（下降 {diff}%）")


# ============================================================
# 主程式
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="Android Doze / BatteryStats 摘要工具 (v5.2)")
    parser.add_argument("full", help="dumpsys batterystats 完整輸出")
    parser.add_argument("--pkg", default="")
    parser.add_argument("--checkin")
    parser.add_argument("--deviceidle")
    parser.add_argument("--mem", nargs="+")
    parser.add_argument("--battery", nargs="+")

    args = parser.parse_args()

    if not os.path.isfile(args.full):
        print(f"錯誤：找不到檔案 {args.full}", file=sys.stderr)
        return 2

    full_text = read_text(args.full)
    if not full_text:
        print("錯誤：BatteryStats 檔案為空。", file=sys.stderr)
        return 2

    lines = full_text.splitlines()
    history_lines, stats_lines = split_dump(lines)
    stats_text = "\n".join(stats_lines)

    events, h_stats = parse_history(history_lines)
    uidmap = load_uidmap(args.checkin)
    pkg_uids = resolve_pkg_uids(args.pkg, uidmap)

    print("# Android Doze / BatteryStats 摘要")
    print(f"- 原始檔案：{args.full}")
    print(f"- History 總行數：{h_stats['total']}")
    print(f"  - 成功解析事件行：{h_stats['parsed_events']}")
    print(f"  - 合併補充細節行：{h_stats['merged_details']}（Details / /proc/stat 等）")
    print(f"  - 忽略行數：{h_stats['ignored']}（空白行與標頭）")
    print(f"  - 未辨識殘存行：{h_stats['unparsed']}")

    if args.pkg and not pkg_uids:
        print(f"- ℹ 指定套件 {args.pkg} 未在 checkin.txt 中找到 UID 映射"
              f"（可能未安裝、checkin.txt 不完整，或該 App 未出現在歷史記錄）。")

    start_dt = grab(stats_text, r"Start clock time:\s*(\S+)")
    print("- 統計起點：", start_dt or "未知")

    print_battery_stats(stats_text, events)
    print_doze(events, uidmap)
    print_wakelocks(stats_text)
    print_discharge(events, uidmap)
    print_cpu_running(events)
    print_power(stats_text, uidmap, pkg_uids)
    print_deviceidle(args.deviceidle)

    if args.mem:
        print_meminfo(args.mem)

    if args.battery:
        print_battery_snapshots(args.battery)

    print("\n摘要分析完成。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
