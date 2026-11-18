#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Termux Android Doze / BatteryStats 摘要工具

用法：

python3 doze_summary-termux.py full.txt \
  --checkin checkin.txt \
  --pkg ch.deletescape.lawnchair.plah \
  --deviceidle deviceidle.txt \
  --mem mem_start.txt mem_end.txt \
  --battery battery_start.txt battery_end.txt

只使用 Python 標準函式庫。

注意：
Android 不同版本與廠牌的 dumpsys 格式可能不同。
無法辨識的欄位會顯示警告，不會假裝成 0。
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
    2000: "shell(adbd)",
}

BURST_MINUTES = 6
BURST_MAH = 9.0
HIGH_DRAIN_MAH_H = 25.0


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
    units = {
        "d": 86400000,
        "h": 3600000,
        "m": 60000,
        "s": 1000,
        "ms": 1,
    }

    total = 0

    for number, unit in re.findall(
        r"(\d+)\s*(ms|d|h|m|s)", value
    ):
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


def unique(items):
    return list(dict.fromkeys(items))


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
        return (
            int(match.group(1)) * 100000
            + 10000
            + int(match.group(2))
        )

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


def per_uid_blocks(lines):
    current = None
    result = collections.defaultdict(list)

    for line in lines:
        match = re.match(
            r"^\s*(u\d+[a-z]\d+|\d+):\s*$",
            line
        )

        if match:
            current = match.group(1)
            continue

        if current and line.startswith("    "):
            result[current].append(line.strip())

        elif current and not line.startswith("    ") and line.strip():
            current = None

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
    unparsed = 0

    for line in lines:
        match = re.match(
            r"^\s*(\+[\dhdms]+|0)\s+\((\d+)\)\s+(\d{1,3})\s?(.*)$",
            line
        )

        if not match:
            if line.strip():
                unparsed += 1

            continue

        timestamp, _, level, rest = match.groups()

        elapsed = (
            0 if timestamp == "0"
            else parse_dur(timestamp)
        )

        events.append(
            (elapsed, int(level), rest)
        )

    events.sort(key=lambda item: item[0])

    return events, unparsed


def parse_idle(events):
    result = []

    for timestamp, _, rest in events:
        match = re.search(
            r"(?:^|\s)device_idle=([^\s]+)",
            rest
        )

        if match:
            result.append(
                (timestamp, match.group(1))
            )

    return result


def parse_alarm_events(events):
    result = []

    for timestamp, _, rest in events:
        if "+alarm" not in rest:
            continue

        match = re.search(
            r'\+alarm=(\S+?):"([^"]*)"',
            rest
        )

        if match:
            result.append(
                (timestamp, match.group(1), match.group(2))
            )

    return result


# ============================================================
# BatteryStats 統計
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
        print(
            f"- CPU suspend 推算比例："
            f"{100 - float(uptime_pct):.1f}%"
        )

        if float(realtime_pct) < 99.5:
            print(
                f"- 注意：統計期間只有 {realtime_pct}% "
                "屬於電池供電時間。"
            )
    else:
        print(
            "- ⚠ 找不到 Time on battery，"
            "無法計算 CPU 清醒比例。"
        )

    fields = [
        ("Screen on", r"^\s+Screen on:\s*(.*)"),
        ("Discharge", r"^\s+Discharge:\s*(.*)"),
        (
            "Light doze discharge",
            r"Device light doze discharge:\s*(.*)"
        ),
        (
            "Deep doze discharge",
            r"Device deep doze discharge:\s*(.*)"
        ),
        (
            "Light idle",
            r"^\s+Device light idling:\s*(.*)"
        ),
        (
            "Deep idle",
            r"^\s+Device full idling:\s*(.*)"
        ),
        (
            "Partial wakelock",
            r"Total partial wakelock time:\s*(.*)"
        ),
        (
            "Wi-Fi kernel active",
            r"Wifi kernel active time:\s*(.*)"
        ),
        (
            "Wi-Fi received",
            r"Wifi data received:\s*(.*)"
        ),
        (
            "Wi-Fi sent",
            r"Wifi data sent:\s*(.*)"
        ),
    ]

    for name, pattern in fields:
        value = grab(text, pattern)
        print(f"- {name}：{value or '未知／未提供'}")

    screen_on = [
        t for t, _, rest in events
        if re.search(r"(^|\s)\+screen", rest)
    ]

    screen_off = [
        t for t, _, rest in events
        if re.search(r"(^|\s)-screen", rest)
    ]

    for timestamp in screen_on:
        off = next(
            (t for t in screen_off if t > timestamp),
            None
        )

        duration = (
            (off - timestamp) / 1000
            if off is not None
            else None
        )

        if duration is not None and duration < 60:
            print(
                f"- ℹ 短暫亮屏：{fmt(timestamp)}，"
                f"約 {duration:.1f} 秒。"
            )
        else:
            print(
                f"- ⚠ 測試期間曾亮屏：{fmt(timestamp)}，"
                f"持續時間："
                f"{duration if duration is not None else '未知'} 秒。"
            )


# ============================================================
# Doze / Alarm / Job / Wakeup
# ============================================================

def print_doze(events, uidmap):
    print("\n## Doze 狀態與時間軸")

    idle = parse_idle(events)

    if not idle:
        print("- 沒有辨識到 device_idle 狀態事件。")
    else:
        print(
            "- device_idle 轉換：",
            ", ".join(
                f"{fmt(t)}={state}"
                for t, state in idle
            )
        )

        full = [
            t for t, state in idle
            if state == "full"
        ]

        if full:
            print(f"- 首次記錄 full：{fmt(full[0])}")

            if full[0] == 0:
                print(
                    "  ⚠ 統計起點已是 full，"
                    "不能確定本次測試何時進入。"
                )
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

            print(
                "- 最後一個狀態若沒有退出事件，"
                "不會將未確認的尾端時間計入。"
            )

    alarms = parse_alarm_events(events)

    print("\n## Alarm / DeviceIdle 鬧鐘")

    deviceidle_alarms = [
        (t, name)
        for t, _, name in alarms
        if "DeviceIdleController" in name
    ]

    if deviceidle_alarms:
        for timestamp, name in deviceidle_alarms:
            print(f"- {fmt(timestamp)}：{name}")
    else:
        print("- 沒有辨識到 DeviceIdleController 鬧鐘。")

    progression = [
        t for t, name in deviceidle_alarms
        if "deep.progression" in name
    ]

    if progression:
        print(
            "- deep.progression：",
            ", ".join(fmt(t) for t in progression)
        )

    normal_alarms = [
        (t, uid, name)
        for t, uid, name in alarms
        if "DeviceIdle" not in name
    ]

    counter = collections.Counter(
        (uid, name[:55])
        for _, uid, name in normal_alarms
    )

    print("- 一般 Alarm 前 6 名：")

    for (uid, name), count in counter.most_common(6):
        print(
            f"  - {label(uid, uidmap)}：{name} × {count}"
        )

    print("\n## Job / 網路活動")

    jobs = collections.Counter()
    cellular = 0

    for _, _, rest in events:
        for match in re.finditer(
            r"\+job=(\S+?):",
            rest
        ):
            jobs[label(match.group(1), uidmap)] += 1

        if "cellular_high_tx_power" in rest:
            cellular += 1

    for name, count in jobs.most_common(10):
        print(f"- Job {name}：{count} 次")

    print(
        f"- cellular_high_tx_power 事件：{cellular} 次"
    )

    print("\n## Wakeup AP")

    wakeups = collections.Counter()

    for _, _, rest in events:
        for match in re.finditer(
            r"wakeupap=(\S+?):",
            rest
        ):
            wakeups[match.group(1)] += 1

    if wakeups:
        for uid, count in wakeups.most_common(8):
            print(
                f"- {label(uid, uidmap)}：{count} 次"
            )
    else:
        print("- 沒有辨識到 wakeupap。")


# ============================================================
# Kernel Wakelock
# ============================================================

def print_wakelocks(text):
    print("\n## Kernel Wakelock")

    rows = []

    for line in text.splitlines():
        match = re.match(
            r"^\s+Kernel Wake lock (\S+): (.*?) \((\d+) times\)",
            line
        )

        if match:
            name, duration, count = match.groups()

            rows.append(
                (
                    parse_dur(duration),
                    name,
                    duration,
                    count
                )
            )

    rows.sort(reverse=True)

    if not rows:
        print("- 沒有辨識到 Kernel Wakelock 資料。")
    else:
        for _, name, duration, count in rows[:8]:
            print(
                f"- {name}：{duration}（{count} 次）"
            )

    wake_reasons = [
        line.strip()
        for line in text.splitlines()
        if line.startswith("  Wakeup reason")
    ]

    print("\n## Wakeup reason")

    if wake_reasons:
        for line in wake_reasons[:8]:
            print("-", line[:180])
    else:
        print("- 沒有辨識到 Wakeup reason。")


# ============================================================
# Charge Counter 放電分析
# ============================================================

def print_discharge(events, uidmap):
    print("\n## 放電曲線（BatteryStats history charge）")

    points = []

    for timestamp, level, rest in events:
        match = re.search(
            r"(?:^|\s)charge=(\d+)",
            rest
        )

        if match:
            points.append(
                (timestamp, int(match.group(1)))
            )

    levels = []

    for timestamp, level, _ in events:
        if not levels or levels[-1][1] != level:
            levels.append((timestamp, level))

    print(
        "- 電量百分比變化：",
        ", ".join(
            f"{fmt(t)} → {level}%"
            for t, level in levels
        ) or "(無)"
    )

    if len(points) < 2:
        print(
            "- ⚠ charge 資料不足，"
            "無法建立放電曲線。"
        )
        return

    segments = []
    base = points[0]

    for index, point in enumerate(points[1:], start=1):
        elapsed = point[0] - base[0]

        if elapsed >= 1800000 or index == len(points) - 1:
            hours = elapsed / 3600000

            if hours > 0:
                delta = base[1] - point[1]

                if delta >= 0:
                    rate = delta / hours

                    segments.append(
                        (
                            base[0],
                            point[0],
                            delta,
                            rate
                        )
                    )

            base = point

    for start, end, delta, rate in segments:
        flag = (
            "（疑似偏高）"
            if rate > HIGH_DRAIN_MAH_H
            else ""
        )

        print(
            f"- {fmt(start)}–{fmt(end)}："
            f"{delta:.1f} mAh，"
            f"{rate:.1f} mAh/h {flag}"
        )

    print(
        f"- 疑似突發耗電門檻："
        f"{BURST_MINUTES} 分鐘內至少 "
        f"{BURST_MAH:.0f} mAh。"
    )

    bursts = []

    for index in range(len(points)):
        best = None

        for other in range(index + 1, len(points)):
            elapsed = (
                points[other][0] - points[index][0]
            )

            if elapsed > BURST_MINUTES * 60000:
                break

            delta = (
                points[index][1] - points[other][1]
            )

            if delta >= BURST_MAH:
                best = other

        if best is not None:
            bursts.append(
                (
                    points[index][0],
                    points[best][0],
                    points[index][1] - points[best][1]
                )
            )

    if not bursts:
        print("- 沒有符合門檻的突發耗電事件。")
        return

    for start, end, delta in bursts:
        lo = start - 60000
        hi = end + 60000

        idle = [
            f"{fmt(t)}={state}"
            for t, state in parse_idle(events)
            if lo <= t <= hi
        ]

        jobs = collections.Counter()

        for timestamp, _, rest in events:
            if lo <= timestamp <= hi:
                for match in re.finditer(
                    r"\+job=(\S+?):",
                    rest
                ):
                    jobs[label(match.group(1), uidmap)] += 1

        print(
            f"- 疑似突發耗電：{fmt(start)}–{fmt(end)}，"
            f"{delta:.1f} mAh"
        )

        print(
            "  同時段 Doze 狀態：",
            ", ".join(idle) or "(無)"
        )

        print(
            "  同時段 Job：",
            ", ".join(
                f"{name} × {count}"
                for name, count in jobs.most_common(4)
            ) or "(無)"
        )

        print(
            "  注意：這是時間上的關聯，"
            "不能直接認定耗電原因。"
        )


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
                end = min(
                    timestamp,
                    (position // 1800000 + 1) * 1800000
                )

                buckets[int(position // 1800000)] += (
                    end - position
                )

                position = end

        if re.search(r"(^|\s)\+running", rest):
            run = True

        if re.search(r"(^|\s)-running", rest):
            run = False

        last = timestamp

    if run is True:
        print(
            "- ⚠ History 結束時 CPU 仍為 running，"
            "未計入最後事件之後的時間。"
        )

    if run is None:
        print(
            "- ⚠ 無法確認 running 狀態，"
            "以下結果只代表可辨識的區間。"
        )

    hot = [
        (bucket, duration)
        for bucket, duration in sorted(buckets.items())
        if duration / 1800000 > 0.5
    ]

    if not hot:
        print("- 沒有可辨識的清醒時間超過 50% 區段。")
        return

    for bucket, duration in hot:
        print(
            f"- {fmt(bucket * 1800000)}："
            f"{duration / 1800000 * 100:.0f}%"
        )


# ============================================================
# Estimated power use / UID
# ============================================================

def print_power(text, uidmap, args):
    print("\n## 估算耗電（Estimated power use）")

    print(
        "注意：這是 Android 模型估算值，"
        "不等同實際電池放電量。"
    )

    lines = section(
        text,
        "Estimated power use (mAh):",
        80
    )

    for line in lines[:12]:
        if line.strip():
            print("-", line.strip()[:180])

    uid_rows = []

    for line in lines:
        match = re.match(
            r"^\s+[Uu][Ii][Dd] (\S+): ([\d.]+)",
            line
        )

        if match:
            uid_rows.append(
                (
                    float(match.group(2)),
                    match.group(1)
                )
            )

    uid_rows.sort(reverse=True)

    print("- UID 耗電前 8 名：")

    for value, uid in uid_rows[:8]:
        print(
            f"  - {label(uid, uidmap)}："
            f"{value:.2f} mAh"
        )

    wanted = [
        item.strip()
        for item in args.uids.split(",")
        if item.strip()
    ]

    if args.pkg:
        reverse = collections.defaultdict(list)

        for uid, names in uidmap.items():
            for name in names:
                reverse[name].append(uid)

        for package in args.pkg.split(","):
            package = package.strip()

            if not package:
                continue

            matches = reverse.get(package)

            if not matches:
                print(
                    f"- 找不到套件 {package} 的 UID，"
                    "請確認 checkin.txt 有 UID mapping。"
                )
                continue

            uid = matches[0]

            user, app = divmod(uid, 100000)

            if app >= 10000:
                wanted.append(
                    f"u{user}a{app - 10000}"
                )
            else:
                wanted.append(str(uid))

    if wanted:
        print("\n## 指定 UID / 套件")

        blocks = per_uid_blocks(text.splitlines())

        for uid in unique(wanted):
            row = next(
                (
                    value
                    for value, key in uid_rows
                    if key == uid
                ),
                None
            )

            if row is not None:
                print(
                    f"- {label(uid, uidmap)}："
                    f"{row:.2f} mAh"
                )
            else:
                print(
                    f"- {label(uid, uidmap)}："
                    "沒有可辨識的估算耗電資料"
                )

            shown = 0

            for line in blocks.get(uid, []):
                if re.search(
                    r"(Top for|Fg Service|Foreground|"
                    r"Total cpu time: u=|Wake lock|Job |"
                    r"Wi-Fi network|Background for|Cached)",
                    line,
                    re.I
                ):
                    print("   ", line[:160])

                    shown += 1

                    if shown >= 8:
                        break


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

    for key in [
        "inactive_to",
        "idle_after_inactive_to",
        "min_time_to_alarm",
        "idle_to",
        "max_idle_to",
    ]:
        print(
            f"- {key}：",
            grab(
                text,
                r"^\s*" + re.escape(key) + r"=(\S+)"
            )
        )

    for key in [
        "mState",
        "mLightState",
        "mNextAlarmTime",
        "mNextIdleDelay",
        "mCharging",
        "mScreenOn",
    ]:
        print(
            f"- {key}：",
            grab(
                text,
                r"(?:^|\s)" + re.escape(key) + r"=(\S+)"
            )
        )

    position = text.find("Idling history:")

    if position >= 0:
        history = text[position:].splitlines()[1:]

        rows = [
            line.strip()
            for line in history
            if re.match(
                r"^\s+(normal|light|deep)",
                line
            )
        ]

        print(
            "- Idling history 最後 10 筆：",
            " | ".join(rows[-10:]) or "(無)"
        )
    else:
        print("- 沒有辨識到 Idling history。")


# ============================================================
# meminfo
# ============================================================

def parse_mem_block(text):
    result = {}

    process = re.search(
        r"\*\* MEMINFO in pid (\d+) \[(.+?)\]",
        text
    )

    result["proc"] = (
        process.group(2)
        if process
        else "?"
    )

    lines = text.splitlines()

    total_index = None

    for index, line in enumerate(lines):
        if re.match(r"^\s*TOTAL(?:\s|$)", line):
            total_index = index
            break

    if total_index is None:
        result["error"] = "找不到 TOTAL 欄位。"
        return result

    header = lines[total_index - 1] if total_index > 0 else ""

    header_tokens = re.findall(
        r"[A-Za-z][A-Za-z0-9_/-]*",
        header
    )

    total_line = lines[total_index]

    values = re.findall(
        r"\d+",
        total_line
    )

    if not header_tokens or len(header_tokens) != len(values):
        result["error"] = (
            "TOTAL 欄位與表頭無法可靠對應；"
            "此 Android 版本可能使用不同 meminfo 格式。"
        )
        return result

    mapping = {
        name.lower(): int(value)
        for name, value in zip(header_tokens, values)
    }

    aliases = {
        "pss": ("pss",),
        "pdirty": ("private_dirty", "privatedirty"),
        "pclean": ("private_clean", "privateclean"),
        "rss": ("rss",),
        "swap": ("swappss", "swap_pss"),
    }

    for key, names in aliases.items():
        for name in names:
            if name in mapping:
                result[key] = mapping[name]
                break

    if not all(
        key in result
        for key in ("pss", "pdirty", "pclean", "rss")
    ):
        result["error"] = (
            "表頭未包含可辨識的 PSS、Private Dirty、"
            "Private Clean 或 RSS 欄位。"
        )

    for title, key in [
        ("Java Heap", "java"),
        ("Native Heap", "native"),
        ("Graphics", "gfx"),
        ("System", "system"),
    ]:
        match = re.search(
            r"^\s*" + re.escape(title) + r":\s+(\d+)",
            text,
            re.M
        )

        if match:
            result[key] = int(match.group(1))

    return result


def parse_stamp(path):
    text = read_text(path)

    match = re.search(
        r"# captured: (\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)",
        text
    )

    if match:
        try:
            return dt.datetime.strptime(
                match.group(1),
                "%Y-%m-%d %H:%M:%S"
            )
        except ValueError:
            pass

    match = re.search(
        r"(\d{8})_(\d{6})",
        path
    )

    if match:
        try:
            return dt.datetime.strptime(
                match.group(1) + match.group(2),
                "%Y%m%d%H%M%S"
            )
        except ValueError:
            pass

    return None


def print_meminfo(paths):
    print("\n## 記憶體（dumpsys meminfo，單位 MB）")

    rows = []

    for path in paths:
        text = read_text(path)

        if not text:
            print(
                f"- ⚠ {path}：檔案不存在或為空。"
            )
            continue

        for block in re.split(
            r"(?=\*\* MEMINFO in pid)",
            text
        ):
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
            print(
                f"- ⚠ {data['path']} ({data['proc']})："
                f"{data['error']}"
            )
            continue

        stamp = data["stamp"]

        when = (
            stamp.strftime("%m-%d %H:%M:%S")
            if stamp
            else data["path"]
        )

        mb = lambda value: f"{value / 1024:.1f} MB"

        private = (
            data["pdirty"] + data["pclean"]
        )

        print(
            f"- [{when}] {data['proc']}："
            f"PSS {mb(data['pss'])}，"
            f"Private {mb(private)}，"
            f"RSS {mb(data['rss'])}，"
            f"Swap PSS {mb(data.get('swap', 0))}"
        )

        print(
            "- 注意：PSS 包含按比例分攤的共用記憶體；"
            "不同 App 比較時，建議同時觀察 Private Dirty + Clean。"
        )


# ============================================================
# 電池快照
# ============================================================

def print_battery(paths):
    print("\n## 電池快照（dumpsys battery）")

    points = []

    for path in paths:
        text = read_text(path)

        level = grab(
            text,
            r"^\s*level:\s*(\d+)"
        )

        counter = grab(
            text,
            r"^\s*Charge counter:\s*(\d+)"
        )

        if level is None or counter is None:
            print(
                f"- ⚠ {path}：找不到 level 或 Charge counter。"
            )
            continue

        level = int(level)
        counter = int(counter)

        if level <= 0 or counter <= 0:
            print(
                f"- ⚠ {path}：電量或 Charge counter 不合理，"
                "不納入容量估算。"
            )
            continue

        timestamp = parse_stamp(path)

        mah = counter / 1000.0

        per_percent = mah / level

        when = (
            timestamp.strftime("%m-%d %H:%M:%S")
            if timestamp
            else path
        )

        print(
            f"- [{when}] level {level}% / "
            f"Charge counter {mah:.1f} mAh"
        )

        print(
            f"  每 1% 約 {per_percent:.1f} mAh，"
            f"推算滿電容量約 {per_percent * 100:.0f} mAh"
        )

        points.append(
            (timestamp, level, mah)
        )

    if len(points) >= 2:
        first = points[0]
        last = points[-1]

        if first[0] and last[0]:
            hours = (
                last[0] - first[0]
            ).total_seconds() / 3600

            delta = first[2] - last[2]

            if hours > 0 and delta >= 0:
                print(
                    f"- 區間放電：{delta:.1f} mAh / "
                    f"{hours:.2f} 小時 = "
                    f"{delta / hours:.1f} mAh/h"
                )

            elif delta < 0:
                print(
                    "- ⚠ Charge counter 增加，"
                    "可能有充電、計數器重置或讀值波動，"
                    "不計算放電速率。"
                )


# ============================================================
# 主程式
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="Android Doze / BatteryStats 摘要工具"
    )

    parser.add_argument(
        "full",
        help="dumpsys batterystats 完整輸出"
    )

    parser.add_argument("--uids", default="")
    parser.add_argument("--pkg", default="")
    parser.add_argument("--checkin")
    parser.add_argument("--deviceidle")
    parser.add_argument("--mem", nargs="+")
    parser.add_argument("--battery", nargs="+")

    args = parser.parse_args()

    if not os.path.isfile(args.full):
        print(
            f"錯誤：找不到檔案 {args.full}",
            file=sys.stderr
        )
        return 2

    full_text = read_text(args.full)

    if not full_text:
        print(
            "錯誤：BatteryStats 檔案為空。",
            file=sys.stderr
        )
        return 2

    lines = full_text.splitlines()

    history_lines, stats_lines = split_dump(lines)

    stats_text = "\n".join(stats_lines)

    events, unparsed = parse_history(history_lines)

    uidmap = load_uidmap(args.checkin)

    print("# Android Doze / BatteryStats 摘要")

    print(f"- 原始檔案：{args.full}")
    print(f"- History 行數：{len(history_lines)}")
    print(f"- 成功解析事件：{len(events)}")
    print(f"- 未辨識 History 行：{unparsed}")

    if not events:
        print(
            "- ⚠ 沒有成功解析 History 事件。"
            "可能是 Android 版本或 OEM 格式不同。"
        )

    elif unparsed > len(events):
        print(
            "- ⚠ 未辨識行數偏高，"
            "時間軸結果可能不完整。"
        )

    start_dt = grab(
        stats_text,
        r"Start clock time:\s*(\S+)"
    )

    print(
        "- 統計起點：",
        start_dt or "未知"
    )

    print_battery_stats(
        stats_text,
        events
    )

    print_doze(
        events,
        uidmap
    )

    print_wakelocks(
        stats_text
    )

    print_discharge(
        events,
        uidmap
    )

    print_cpu_running(
        events
    )

    print_power(
        stats_text,
        uidmap,
        args
    )

    print_deviceidle(
        args.deviceidle
    )

    if args.mem:
        print_meminfo(args.mem)

    if args.battery:
        print_battery(args.battery)

    print("\n## 資料品質提醒")

    print(
        "- 本摘要只分析目前能辨識的 dumpsys 欄位。"
    )

    print(
        "- 沒有事件不代表系統沒有發生該事件。"
    )

    print(
        "- BatteryStats 模型耗電值不等同實際電池放電量。"
    )

    print(
        "- device_idle=full 代表記錄到 full 狀態，"
        "不代表整段測試都處於 Deep Idle。"
    )

    print(
        "- 疑似突發耗電只表示時間關聯，"
        "不能單憑此結果判定是哪個 App 或服務造成。"
    )

    print(
        "- 請保留 full.txt、checkin.txt、history.txt "
        "等原始資料供進一步核對。"
    )

    print("\n摘要分析完成。")

    return 0


if __name__ == "__main__":
    sys.exit(main())
