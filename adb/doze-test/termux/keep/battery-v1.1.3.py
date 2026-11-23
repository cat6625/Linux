#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
battery.py - Android dumpsys batterystats 耗電與喚醒分析工具
版本：v1.1.3
日期：2026-11-23

v1.1.3 修正（依 4 份實機輸出）：
- 耗電排行不再誤抓 per-UID 區段（Cpu times per freq / Starts / WiFi AP wakeups / Wakeup reason / User activity）
- Partial / Kernel wakelock 只解析「All ... wake locks」那一個連續區塊，不再混入 per-UID 重複行
- Wake lock 名稱含冒號時不再被截斷（例如 soc:qcom,dsi-display-primary、SyncManager: Syncing）
- 支援多使用者 UID（u10a204 -> 1010204），UID 反查改為一次載入套件表並快取
- 熄屏 uptime 改為解析 "realtime, X (pct%) uptime" 格式
- 喚醒比例改以電池使用總時長為分母
- cpu / wake / screen 欄位只取數值；支援 wake= 與 wakelock= 兩種寫法
- 舊版輸出（Android 11 以前）改以「Including smearing」後的數值排序
- 學習容量高於估計容量時不再顯示「健康度」，改為警示
- 超過累計放電的項目改為標記而非直接丟棄
- 補上 adb 逾時處理與 UTF-8 解碼
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

__version__ = "v1.1.3"
__date__ = "2026-11-23"

STATS_HEADER = "Statistics since last charge:"
STATS_NEXT_HEADER = "Statistics since last unplugged:"

# 時長：1h 2m 3s 4ms（單位間可有空白）
DUR_PATTERN = r"(?:\d+(?:\.\d+)?\s*(?:ms|d|h|m|s)\s*)+"

PARTIAL_HEADER_RE = re.compile(r"^\s*All partial wake locks?:\s*$", re.IGNORECASE)
KERNEL_HEADER_RE = re.compile(r"^\s*All kernel wake locks?:\s*$", re.IGNORECASE)
PARTIAL_LINE_RE = re.compile(r"^\s*Wake\s+lock\s", re.IGNORECASE)
KERNEL_LINE_RE = re.compile(r"^\s*Kernel\s+Wake\s+lock\b", re.IGNORECASE)
PARTIAL_ROW_RE = re.compile(
    rf"^\s*Wake\s+lock\s+(.+?):\s+({DUR_PATTERN})\((\d+)\s*times?\)", re.IGNORECASE
)
KERNEL_ROW_RE = re.compile(
    rf"^\s*Kernel\s+Wake\s+lock\s+(.*?):\s+({DUR_PATTERN})\((\d+)\s*times?\)", re.IGNORECASE
)

POWER_HEADER_RE = re.compile(r"^\s*Estimated power use\s*(?:\(mAh\))?\s*:\s*$", re.IGNORECASE)
OTHER_SECTION_RE = re.compile(
    r"^\s*(?:All (?:kernel|partial) wake locks?|Per-app |Battery History|All wakeup reasons)",
    re.IGNORECASE,
)
POWER_ITEM_START_RE = re.compile(
    r"^\s*(?:UID|Uid)\s+\S+:|^\s*(?:Capacity|Global)\b|^\s*[A-Za-z][\w ./-]*:\s*-?[\d.]+"
)
POWER_ITEM_RE = re.compile(
    r"^\s*((?:UID|Uid)\s+[^\s:]+|[A-Za-z_][\w ./-]*?):\s*(-?\d+(?:\.\d+)?|-?\.\d+)(.*)$"
)
POWER_GLOBAL_ROW_RE = re.compile(
    r"^\s*([A-Za-z_][\w ./-]*?):\s*(-?\d+(?:\.\d+)?)\s+apps:\s*(-?\d+(?:\.\d+)?)(.*)$"
)

# 出現這些開頭代表已離開 Estimated power use 區塊（或不是耗電列）
NON_POWER_PREFIXES = (
    "cpu freqs",
    "total cpu time",
    "total screen-off",
    "screen-off cpu",
    "cpu times per freq",
    "starts",
    "wifi ap wakeups",
    "user activity",
    "wakeup reason",
    "screen brightnesses",
    "connectivity",
    "total full wakelock",
    "total partial wakelock",
    "device light",
    "device full",
    "idle mode",
    "time on battery",
    "per-app",
    "wifi multicast",
)
EXCLUDED_POWER_NAMES = {
    "capacity",
    "global",
    "computed drain",
    "actual drain",
    "rated",
    "typical",
}

UID_RE = re.compile(r"^\s*(?:Uid\s+)?(?:u(\d+)a(\d+)|(\d{1,7}))\b", re.IGNORECASE)
USER_APP_RE = re.compile(r"\bu\d+a\d+\b", re.IGNORECASE)


# ------------------------------------------------------------------ ADB ----

def run_adb_shell(args: list[str], timeout: int = 15, check: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["adb", "shell", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=check,
    )


def get_prop(prop_name: str) -> str | None:
    try:
        res = run_adb_shell(["getprop", prop_name], timeout=5)
        val = (res.stdout or "").strip()
        return val if val else None
    except Exception:
        return None


def get_device_info() -> dict[str, str | None]:
    brand = get_prop("ro.product.brand")
    model = get_prop("ro.product.model")
    device = get_prop("ro.product.device")
    android_ver = get_prop("ro.build.version.release")
    sdk_ver = get_prop("ro.build.version.sdk")
    build_id = get_prop("ro.build.display.id")

    if brand and model and not model.lower().startswith(brand.lower()):
        model_display = f"{brand.capitalize()} {model}"
    else:
        model_display = model or brand or device

    android_display = None
    if android_ver and sdk_ver:
        android_display = f"Android {android_ver} (API {sdk_ver})"
    elif android_ver:
        android_display = f"Android {android_ver}"

    return {"model": model_display, "android": android_display, "build": build_id}


def get_stats_from_adb() -> str:
    try:
        result = run_adb_shell(["dumpsys", "batterystats"], timeout=60, check=True)
        return result.stdout.replace("\r", "")
    except FileNotFoundError:
        sys.exit("找不到 adb。請在 Termux 安裝 android-tools，或改用 --file 讀取存檔。")
    except subprocess.TimeoutExpired:
        sys.exit("adb 讀取逾時，請確認連線狀態後再試。")
    except subprocess.CalledProcessError as e:
        err = (e.stderr or "").strip()
        sys.exit(f"讀取失敗：{err or e}")


def read_stats_from_file(file_path: str) -> str:
    p = Path(file_path)
    if not p.is_file():
        sys.exit(f"找不到指定的檔案：{file_path}")
    try:
        return p.read_text(encoding="utf-8", errors="replace").replace("\r", "")
    except Exception as e:
        sys.exit(f"讀取檔案失敗：{e}")


# ------------------------------------------------------------ 基本工具 ----

def indent_of(line: str) -> int:
    return len(line) - len(line.lstrip())


def extract_summary_section(text: str) -> str:
    """取 'Statistics since last charge:' 起算、下一個 'Statistics since' 之前的區段。"""
    start = text.find(STATS_HEADER)
    if start == -1:
        return text
    sub = text[start:]
    idx = sub.find(STATS_NEXT_HEADER, len(STATS_HEADER))
    return sub[:idx] if idx != -1 else sub


def mask_email_match(match: re.Match) -> str:
    local = match.group(1)
    domain = match.group(2)
    if not local:
        masked_local = "***"
    elif len(local) == 1:
        masked_local = f"{local}***"
    else:
        masked_local = f"{local[0]}***{local[-1]}"
    return f"{masked_local}@{domain}"


def mask_emails(text: str) -> str:
    """將電子信箱去識別化，例如 alice@gmail.com -> a***e@gmail.com。"""
    return re.sub(
        r"\b([A-Za-z0-9._%+-]+)@([A-Za-z0-9.-]+\.[A-Za-z]{2,})\b",
        mask_email_match,
        text,
    )


def parse_duration_to_hours(duration_str: str) -> float | None:
    units = {"d": 86400.0, "h": 3600.0, "m": 60.0, "s": 1.0, "ms": 0.001}
    tokens = re.findall(r"(\d+(?:\.\d+)?)\s*(ms|d|h|m|s)(?![A-Za-z])", duration_str)
    if not tokens:
        return None
    total_seconds = sum(float(amount) * units[unit] for amount, unit in tokens)
    return total_seconds / 3600.0


# ----------------------------------------------------------------- UID ----

def extract_uid_token(name: str) -> tuple[str | None, str | None]:
    """
    從項目名稱開頭擷取 UID。回傳 (raw_token, numeric_uid)。
    u0a182 -> ('u0a182', '10182')；u10a204 -> ('u10a204', '1010204')；1041 -> ('1041', '1041')
    """
    m = UID_RE.match(name)
    if not m:
        return None, None
    if m.group(2) is not None:
        user = int(m.group(1))
        app = int(m.group(2))
        return f"u{user}a{app}".lower(), str(user * 100000 + 10000 + app)
    return m.group(3), m.group(3)


_package_map: dict[int, list[str]] | None = None
_cmd_uid_supported: bool | None = None


def _load_package_map() -> dict[int, list[str]]:
    """只執行一次 dumpsys package，建立 appId -> [套件] 對照表（跨使用者共用 appId）。"""
    global _package_map
    if _package_map is not None:
        return _package_map
    mapping: dict[int, list[str]] = {}
    try:
        res = run_adb_shell(["dumpsys", "package"], timeout=60)
        current_pkg: str | None = None
        if res.returncode == 0 and res.stdout:
            for line in res.stdout.splitlines():
                if line and not line[0].isspace():
                    current_pkg = None
                    continue
                pkg_m = re.match(r"^\s*Package \[([^\]]+)\]", line)
                if pkg_m:
                    current_pkg = pkg_m.group(1).strip()
                    continue
                if re.match(r"^\s*SharedUser \[", line):
                    current_pkg = None
                    continue
                uid_m = re.match(r"^\s*(?:userId|appId)=(\d+)\b", line)
                if uid_m and current_pkg:
                    app_id = int(uid_m.group(1)) % 100000
                    lst = mapping.setdefault(app_id, [])
                    if current_pkg not in lst:
                        lst.append(current_pkg)
    except Exception:
        pass
    _package_map = mapping
    return mapping


def query_packages_by_uid(num_uid: str | None) -> list[str]:
    """先用 cmd package --uid 精準查詢；不支援或查無結果時用快取的套件表。"""
    global _cmd_uid_supported
    if not num_uid:
        return []

    if _cmd_uid_supported is not False:
        try:
            res = run_adb_shell(["cmd", "package", "list", "packages", "--uid", num_uid], timeout=8)
            if res.returncode != 0:
                _cmd_uid_supported = False
            else:
                _cmd_uid_supported = True
                pkgs: list[str] = []
                for line in (res.stdout or "").splitlines():
                    line = line.strip()
                    if line.startswith("package:"):
                        pkg = line.split(":", 1)[1].strip().split()[0]
                        if pkg and pkg not in pkgs:
                            pkgs.append(pkg)
                if pkgs:
                    return pkgs
        except Exception:
            _cmd_uid_supported = False

    try:
        return list(_load_package_map().get(int(num_uid) % 100000, []))
    except ValueError:
        return []


def resolve_uids_packages(rows: list[dict], offline: bool = False) -> dict[str, list[str]]:
    """只針對傳入項目涉及的 UID 反查套件；離線讀檔時跳過。"""
    if offline:
        return {}
    resolved: dict[str, list[str]] = {}
    for item in rows:
        _, num_uid = extract_uid_token(item["name"])
        if not num_uid or num_uid in resolved:
            continue
        resolved[num_uid] = query_packages_by_uid(num_uid)
    return resolved


def format_uid_label(name: str, uid_pkgs_map: dict[str, list[str]]) -> str:
    _, num_uid = extract_uid_token(name)
    pkgs = uid_pkgs_map.get(num_uid or "")
    if not pkgs:
        return name
    preview = ", ".join(pkgs[:2]) + (" 等" if len(pkgs) > 2 else "")
    return f"{name} [{preview}]"


# ------------------------------------------------------------- Wakelock ----

def _collect_wakelock_block(text: str, header_re: re.Pattern, line_re: re.Pattern) -> list[str]:
    """
    只取標題後面「連續」的 wake lock 行，且縮排需與第一筆相同；
    遇到第一個不符合的非空行就結束，避免混入 per-UID 區段的重複行。
    """
    lines = text.splitlines()
    idx = next((i for i, l in enumerate(lines) if header_re.match(l)), None)
    if idx is None:
        return []
    entries: list[str] = []
    entry_indent: int | None = None
    for l in lines[idx + 1:]:
        if not l.strip():
            continue
        if not line_re.match(l):
            break
        ind = indent_of(l)
        if entry_indent is None:
            entry_indent = ind
        elif ind != entry_indent:
            break
        entries.append(l)
    return entries


def _row_to_lock(row_m: re.Match) -> dict | None:
    name = re.sub(r"\s+", " ", row_m.group(1).strip()) or "(unnamed)"
    hours = parse_duration_to_hours(row_m.group(2).strip())
    if hours is None or hours <= 0:
        return None
    return {
        "name": name,
        "hours": hours,
        "minutes": hours * 60.0,
        "count": int(row_m.group(3)),
        "merged_count": 1,
    }


def parse_kernel_wakelocks(text: str, top_n: int = 10) -> list[dict]:
    locks: list[dict] = []
    for line in _collect_wakelock_block(text, KERNEL_HEADER_RE, KERNEL_LINE_RE):
        row_m = KERNEL_ROW_RE.match(line)
        if not row_m:
            continue
        lock = _row_to_lock(row_m)
        if lock:
            locks.append(lock)
    locks.sort(key=lambda item: item["hours"], reverse=True)
    return locks[:top_n]


def parse_partial_wakelocks(
    text: str,
    top_n: int = 10,
    hide_wm: bool = False,
    merge_wl: bool = False,
) -> list[dict]:
    raw_locks: list[dict] = []
    for line in _collect_wakelock_block(text, PARTIAL_HEADER_RE, PARTIAL_LINE_RE):
        row_m = PARTIAL_ROW_RE.match(line)
        if not row_m:
            continue
        lock = _row_to_lock(row_m)
        if not lock:
            continue
        if hide_wm and re.search(r"\bWindowManager\b", lock["name"], re.IGNORECASE):
            continue
        raw_locks.append(lock)

    deduped: list[dict] = []
    seen_keys: set[tuple[str, float, int]] = set()
    for item in sorted(raw_locks, key=lambda x: x["hours"], reverse=True):
        key = (item["name"].lower(), round(item["minutes"], 2), item["count"])
        if key in seen_keys:
            continue
        seen_keys.add(key)
        deduped.append(item)

    if merge_wl:
        merged_map: dict[str, dict] = {}
        for item in deduped:
            key = item["name"].lower()
            if key not in merged_map:
                merged_map[key] = dict(item)
            else:
                acc = merged_map[key]
                acc["hours"] += item["hours"]
                acc["minutes"] += item["minutes"]
                acc["count"] += item["count"]
                acc["merged_count"] += 1
        deduped = list(merged_map.values())

    deduped.sort(key=lambda item: item["hours"], reverse=True)
    return deduped[:top_n]


# ---------------------------------------------------------- 估算耗電 ----

def _item_name(line: str) -> str:
    s = line.strip()
    m = re.match(r"^((?:UID|Uid)\s+[^\s:]+|[^:]+?)(?:\s*:|$)", s)
    return m.group(1).strip() if m else s


def _power_block_lines(text: str) -> list[tuple[str, bool]]:
    """
    回傳 Estimated power use 區塊內的 (行, 是否為項目起始行)。
    不依賴標題縮排：
      - 縮排比上一個項目深 -> 該項目的延續行
      - 符合項目格式 -> 新項目
      - 項目名稱屬於非耗電列（Cpu times per freq / Starts / ...）或其他格式 -> 區塊結束
    """
    lines = text.splitlines()
    idx = next((i for i, l in enumerate(lines) if POWER_HEADER_RE.match(l)), None)
    if idx is None:
        return []

    out: list[tuple[str, bool]] = []
    last_indent = -1
    for l in lines[idx + 1:]:
        if not l.strip():
            continue
        if OTHER_SECTION_RE.match(l):
            break
        ind = indent_of(l)
        if out and ind > last_indent:
            out.append((l, False))
            continue
        if POWER_ITEM_START_RE.match(l):
            if _item_name(l).lower().startswith(NON_POWER_PREFIXES):
                break
            out.append((l, True))
            last_indent = ind
            continue
        break
    return out


def _num(pattern: str, extra: str) -> float | None:
    m = re.search(pattern, extra, re.IGNORECASE)
    if not m:
        return None
    try:
        return float(m.group(1))
    except ValueError:
        return None


def _format_num(val: float) -> str:
    s = f"{val:.6f}".rstrip("0").rstrip(".")
    return s if s else "0"


def parse_power_items(text: str, merge_same_name: bool = False) -> list[dict]:
    """解析 'Estimated power use' 區塊。舊版輸出以「Including smearing」後的數值為排序依據。"""
    items: list[dict] = []

    for line, is_start in _power_block_lines(text):
        g = POWER_GLOBAL_ROW_RE.match(line)
        if g:
            name = f"[全域] {g.group(1).strip()}"
            raw_mah = float(g.group(2))
            extra = g.group(4)
        elif is_start:
            m = POWER_ITEM_RE.match(line)
            if not m:
                continue
            name = re.sub(r"\s+", " ", m.group(1).strip())
            if name.lower() in EXCLUDED_POWER_NAMES:
                continue
            raw_mah = float(m.group(2))
            extra = m.group(3)
        else:
            continue

        if raw_mah <= 0:
            continue

        smeared = _num(r"Including smearing:\s*(-?[\d.]+)", extra)
        mah = smeared if (smeared is not None and smeared > 0) else raw_mah

        items.append({
            "name": name,
            "mah": mah,
            "raw": raw_mah,
            "smeared": smeared is not None and smeared > 0 and abs(smeared - raw_mah) > 1e-9,
            "cpu_num": _num(r"\bcpu=(-?[\d.]+)", extra),
            "wake_num": _num(r"\bwake(?:\s?lock)?=(-?[\d.]+)", extra),
            "screen_num": _num(r"\bscreen=(-?[\d.]+)", extra),
            "is_user_app": bool(USER_APP_RE.search(name)),
            "is_global": name.startswith("[全域]"),
            "merged_count": 1,
        })

    if merge_same_name:
        merged_map: dict[str, dict] = {}
        for item in items:
            key = item["name"].lower()
            if key not in merged_map:
                merged_map[key] = dict(item)
            else:
                acc = merged_map[key]
                acc["mah"] += item["mah"]
                acc["raw"] += item["raw"]
                acc["merged_count"] += 1
                for k in ("cpu_num", "wake_num", "screen_num"):
                    if item[k] is not None:
                        acc[k] = (acc[k] or 0.0) + item[k]
        items = list(merged_map.values())

    items.sort(key=lambda item: item["mah"], reverse=True)
    return items


# --------------------------------------------------------- 摘要欄位 ----

def find_value(text: str, label: str) -> float | None:
    match = re.search(rf"^\s*{re.escape(label)}:\s*([-\d.]+)\s*mAh\b", text, re.MULTILINE)
    return float(match.group(1)) if match else None


def find_raw_line(text: str, label: str) -> str | None:
    match = re.search(rf"^\s*{re.escape(label)}:\s*(.+)$", text, re.MULTILINE)
    return match.group(1).strip() if match else None


def find_duration_hours(text: str, label: str) -> float | None:
    raw = find_raw_line(text, label)
    if not raw:
        return None
    before_paren = raw.split("(", 1)[0].strip()
    hours = parse_duration_to_hours(before_paren)
    if hours is not None:
        return hours
    return parse_duration_to_hours(raw)


def find_screen_off_uptime_hours(summary: str) -> float | None:
    """格式：'X (95.0%) realtime, Y (1.4%) uptime'；Y 在 '(pct%) uptime' 之前。"""
    raw = find_raw_line(summary, "Time on battery screen off")
    if not raw:
        return None
    m = re.search(r"realtime,\s*(.+?)\s*\([\d.]+%\)\s*uptime", raw, re.IGNORECASE)
    if not m:
        return None
    return parse_duration_to_hours(m.group(1).strip())


def fmt_pct(part: float | None, whole: float | None) -> str:
    if part is None or whole is None or whole <= 0:
        return "N/A"
    return f"{part / whole * 100:.1f}%"


def fmt_rate(
    mah: float | None,
    hours: float | None,
    est_cap: float | None = None,
    learned_cap: float | None = None,
) -> str:
    if mah is None or hours is None or hours <= 0:
        return "N/A"
    rate = mah / hours
    parts: list[str] = []
    if est_cap and est_cap > 0:
        parts.append(f"標準 {rate / est_cap * 100:.2f}%/h")
    if learned_cap and learned_cap > 0 and learned_cap != est_cap:
        parts.append(f"學習 {rate / learned_cap * 100:.2f}%/h")
    if parts:
        return f"{rate:.1f} mAh/h（{'｜'.join(parts)}）"
    return f"{rate:.1f} mAh/h"


# ------------------------------------------------------------- 輸出 ----

def print_ranking(
    title: str,
    rows: list[dict],
    total_discharge: float | None,
    uid_pkgs_map: dict[str, list[str]],
) -> None:
    print(f"\n{title}")
    if not rows:
        print("  查無符合項目。")
        return

    for idx, item in enumerate(rows, start=1):
        label = mask_emails(format_uid_label(item["name"], uid_pkgs_map))
        if item.get("merged_count", 1) > 1:
            label = f"{label} [合併 {item['merged_count']} 筆]"
        share = fmt_pct(item["mah"], total_discharge)
        details = []
        if item.get("screen_num") is not None:
            details.append(f"screen={_format_num(item['screen_num'])}")
        if item.get("cpu_num") is not None:
            details.append(f"cpu={_format_num(item['cpu_num'])}")
        if item.get("wake_num") is not None:
            details.append(f"wake={_format_num(item['wake_num'])}")
        if item.get("smeared"):
            details.append(f"分攤前 {item['raw']:.1f}")
        extra_str = f"（{', '.join(details)}）" if details else ""
        flag = ""
        if total_discharge and total_discharge > 0 and item["mah"] > total_discharge:
            flag = " ⚠ 超過累計放電，請確認原始統計"
        print(f"{idx:>2}. {label}：{item['mah']:.1f} mAh（佔放電 {share}）{extra_str}{flag}")


def print_wakelock_ranking(
    title: str,
    locks: list[dict],
    total_hours: float | None,
    uid_pkgs_map: dict[str, list[str]] | None = None,
) -> None:
    print(f"\n{title}")
    if not locks:
        print("  查無喚醒明細。")
        return

    for idx, item in enumerate(locks, start=1):
        raw_label = format_uid_label(item["name"], uid_pkgs_map) if uid_pkgs_map else item["name"]
        label = mask_emails(raw_label)
        if item.get("merged_count", 1) > 1:
            label = f"{label} [合併 {item['merged_count']} 筆]"
        mins = item["minutes"]
        dur_str = f"{mins:.1f} 分鐘" if mins >= 1.0 else f"{mins * 60:.1f} 秒"
        share = f"｜佔使用時長 {fmt_pct(item['hours'], total_hours)}" if total_hours else ""
        print(f"{idx:>2}. {label}：{dur_str}（{item['count']} 次）{share}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="分析 Android dumpsys batterystats 耗電與喚醒資訊")
    parser.add_argument("top_n_pos", nargs="?", type=int, help="顯示前幾名項目（預設 10）")
    parser.add_argument("-n", "--top", type=int, default=10, help="顯示前幾名項目（預設 10）")
    parser.add_argument("-f", "--file", type=str, default=None, help="改從本機 batterystats 文字檔讀取")
    parser.add_argument("-m", "--merge", action="store_true", help="合併估算排行榜中的同名項目")
    parser.add_argument("--merge-wl", action="store_true", help="合併背景喚醒（Partial Wake Lock）中的同名項目")
    parser.add_argument("--hide-wm", action="store_true", help="背景喚醒排行隱藏 WindowManager 項目")
    parser.add_argument("-V", "--version", action="version", version=f"%(prog)s {__version__} ({__date__})")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    top_n = max(1, args.top_n_pos if args.top_n_pos is not None else args.top)

    offline = bool(args.file)
    device_info = {} if offline else get_device_info()
    raw_text = read_stats_from_file(args.file) if offline else get_stats_from_adb()

    if STATS_HEADER not in raw_text and "Estimated power use" not in raw_text:
        sys.exit("輸入內容看起來不是 dumpsys batterystats 輸出。")

    summary = extract_summary_section(raw_text)

    start_clock = find_raw_line(summary, "Start clock time")
    est_cap = find_value(summary, "Estimated battery capacity")
    min_learned = find_value(summary, "Min learned battery capacity")
    max_learned = find_value(summary, "Max learned battery capacity")

    battery_hours = find_duration_hours(summary, "Time on battery")
    screen_on_hours = find_duration_hours(summary, "Screen on")
    screen_off_hours = find_duration_hours(summary, "Time on battery screen off")
    screen_off_uptime_hours = find_screen_off_uptime_hours(summary)

    light_idle_hours = find_duration_hours(summary, "Device light idling")
    full_idle_hours = find_duration_hours(summary, "Device full idling")
    full_wake_hours = find_duration_hours(summary, "Total full wakelock time")
    partial_wake_hours = find_duration_hours(summary, "Total partial wakelock time")

    discharge = find_value(summary, "Discharge")
    screen_on_mah = find_value(summary, "Screen on discharge")
    screen_off_mah = find_value(summary, "Screen off discharge")
    light_doze_mah = find_value(summary, "Device light doze discharge")
    deep_doze_mah = find_value(summary, "Device deep doze discharge")

    print(f"=== 裝置與系統資訊（{__version__} / {__date__}）===")
    if offline:
        print(f"資料來源：離線檔案（{args.file}）")
    else:
        if device_info.get("model"):
            print(f"機型：{device_info['model']}")
        if device_info.get("android"):
            print(f"系統版本：{device_info['android']}")
        if device_info.get("build"):
            print(f"韌體版本：{device_info['build']}")

    print("\n=== 電池與統計週期資訊 ===")
    if start_clock:
        print(f"統計起算時間：{start_clock}")
    if est_cap:
        print(f"估計電池容量：{est_cap:.0f} mAh")
    if min_learned or max_learned:
        min_s = f"{min_learned:.0f}" if min_learned else "?"
        max_s = f"{max_learned:.0f}" if max_learned else "?"
        ratio_s = ""
        if max_learned and est_cap:
            ratio = max_learned / est_cap
            if ratio > 1.05:
                ratio_s = (
                    f"（學習/估計 = {ratio * 100:.1f}%，高於估計容量，"
                    "學習值可能是預設值，不代表電池健康度）"
                )
            else:
                ratio_s = f"（健康度約 {ratio * 100:.1f}%）"
        print(f"學習容量範圍：{min_s} ~ {max_s} mAh{ratio_s}")
    if battery_hours is not None:
        print(f"電池使用總時長：{battery_hours:.2f} 小時")

    print("\n=== 整體耗電摘要 ===")
    if discharge is not None:
        print(
            f"累計放電：{discharge:.0f} mAh"
            f"｜估計容量比：{fmt_pct(discharge, est_cap)}"
            f"｜學習容量比：{fmt_pct(discharge, max_learned)}"
        )
        if discharge == 0:
            print("※ 累計放電為 0：此檔沒有放電計數，mAh/h 與佔比皆不具意義，只能看時間分布與相對排名。")
        if screen_on_mah is not None and screen_off_mah is not None:
            diff = discharge - (screen_on_mah + screen_off_mah)
            print(f"亮屏 + 熄屏合計：{screen_on_mah + screen_off_mah:.0f} mAh（與 Discharge 差值：{diff:+.0f} mAh）")
    else:
        print("找不到累計放電（Discharge）資料。")

    print("\n=== 亮屏與熄屏耗電率 ===")
    if screen_on_mah is not None and screen_on_hours:
        print(
            f"亮屏（Screen on）：{screen_on_mah:.0f} mAh / {screen_on_hours:.2f} h"
            f" -> {fmt_rate(screen_on_mah, screen_on_hours, est_cap, max_learned)}"
        )
    if screen_off_mah is not None and screen_off_hours:
        print(
            f"熄屏（Screen off）：{screen_off_mah:.0f} mAh / {screen_off_hours:.2f} h"
            f" -> {fmt_rate(screen_off_mah, screen_off_hours, est_cap, max_learned)}"
        )
    if screen_off_hours and screen_off_uptime_hours is not None:
        print(
            f"熄屏期間 CPU 醒來（uptime）：{screen_off_uptime_hours:.2f} h"
            f"（佔熄屏 {fmt_pct(screen_off_uptime_hours, screen_off_hours)}）"
        )
    if (est_cap or max_learned) and (screen_on_mah is not None or screen_off_mah is not None):
        print("※ 註：若開啟充電上限（如 80% 保護）或學習容量偏移，實際體感掉電%會高於標準值，跨機型建議優先比對 mAh/h。")

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

    top_kernel_locks = parse_kernel_wakelocks(summary, top_n=top_n)
    top_partial_locks = parse_partial_wakelocks(
        summary,
        top_n=top_n,
        hide_wm=args.hide_wm,
        merge_wl=args.merge_wl,
    )

    all_items = parse_power_items(summary, merge_same_name=args.merge)
    top_all = all_items[:top_n]
    top_u0a = [item for item in all_items if item["is_user_app"]][:top_n]

    uid_pkgs_map = resolve_uids_packages(top_all + top_u0a + top_partial_locks, offline=offline)

    print_wakelock_ranking(
        f"=== 核心喚醒（Kernel Wake Lock）Top {top_n} ===",
        top_kernel_locks,
        battery_hours,
    )
    print_wakelock_ranking(
        f"=== 背景喚醒（Partial Wake Lock）Top {top_n} ===",
        top_partial_locks,
        battery_hours,
        uid_pkgs_map,
    )
    print_ranking(
        f"=== 最耗電項目 Top {top_n}（總覽估算）===",
        top_all,
        discharge,
        uid_pkgs_map,
    )
    print_ranking(
        f"=== 使用者 App（u0a）Top {top_n}（估算）===",
        top_u0a,
        discharge,
        uid_pkgs_map,
    )


if __name__ == "__main__":
    main()
