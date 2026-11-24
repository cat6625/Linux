#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
battery.py - Android dumpsys batterystats 耗電與喚醒分析工具
版本：v1.1.9
日期：2026-11-25

v1.1.9：
- 修正「估計容量 = 設定檔容量（比值 100%）卻說容量來源不一致」的自相矛盾說明；
  容量一致時改說明差距約為幾個 1% 級距，並提示可能是『放電計數與顯示電量起點不同』
- 背景喚醒新增「實際持有」（actual=，牆上時間）：累計時間在多個鎖同時持有時會被攤分，
  所以累計可以小於單次最長，兩者不是同一種時間

v1.1.8（對照四機 v1.1.7 輸出後）：
- 新增 Wi‑Fi 統計區段（Wifi kernel active / Rx / Tx / 流量 / 封包 / 訊號 / 連線狀態）
- 喚醒鎖若仍在持有（"running for"），標示「⚠ 目前仍在持有」
- 功耗模型說明改寫：Android 13+ 的 Discharge 與模型估算相同，不再誤判為「模型只解釋 74%」；
  改列「估計 / 學習 / 設定檔」三種容量對照
- actual drain 為 0 時顯示「無資料」，不再印「0 mAh」
- 亮屏或熄屏樣本不足、放電以 1% 級距換算時加註可信度說明
- 小於 1 mAh 的項目改用較多小數顯示（不再顯示 0.0）

v1.1.7：Android 15（如 SM-M146B）UID 明細位於下一行，原本讀不到 → 補上延續行解析

v1.1.6：背景喚醒排行新增「單次最長」（取自 max=，30 秒以上才顯示）

v1.1.5 修正（對照 battery_extract 原始內容後）：
- UID 明細改列出佔比最大的前 4 項元件（screen / cpu / audio / video / mobile_radio / sensors / gnss ...），
  不再只看 screen / cpu / wake，避免 u0a366 這類 audio+video 約 200 mAh 被漏掉
- 功耗模型只解釋實際放電的 80% 以下（或高估 120% 以上）時加註警示
- 新增 --strict-mask：信箱完整遮成 [EMAIL]（預設保留首尾字元與網域）

v1.1.4 修正（依 v1.1.3 重跑結果）：
- 總覽排行拆成「UID / 系統項目」與「元件耗電」兩份，避免 [全域] cpu/screen 與各 UID 重疊混排
- 新增「功耗模型估算 vs 系統實際」一行；Unaccounted / Over-counted 標示為模型差額
- 舊格式分攤後數值加註「不可與 Screen 等元件相加」
- 學習容量略高於估計容量（>100.5%）即不顯示健康度
- 信箱遮蔽不再誤改 @SyncManager@com.xxx 這類同步標籤

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

__version__ = "v1.1.9"
__date__ = "2026-11-25"

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


STRICT_MASK = False


def mask_email_match(match: re.Match) -> str:
    if STRICT_MASK:
        return "[EMAIL]"
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
        r"(?<![@\w.%+-])([A-Za-z0-9._%+-]+)@([A-Za-z0-9.-]+\.[A-Za-z]{2,})\b",
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
    mx = re.search(r"\bmax=(\d+)", row_m.string)
    rn = re.search(r"\(running for (\d+)ms\)", row_m.string)
    ac = re.search(r"\bactual=(\d+)", row_m.string)
    return {
        "name": name,
        "hours": hours,
        "minutes": hours * 60.0,
        "count": int(row_m.group(3)),
        "max_ms": int(mx.group(1)) if mx else None,
        "running_ms": int(rn.group(1)) if rn else None,
        "actual_ms": int(ac.group(1)) if ac else None,
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
                if item.get("max_ms") is not None:
                    acc["max_ms"] = max(acc.get("max_ms") or 0, item["max_ms"])
                if item.get("running_ms") is not None:
                    acc["running_ms"] = max(acc.get("running_ms") or 0, item["running_ms"])
                if item.get("actual_ms") is not None:
                    acc["actual_ms"] = (acc.get("actual_ms") or 0) + item["actual_ms"]
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

    # 第一階段：把「項目起始行 + 其縮排更深的延續行」合併成一筆
    # （Android 15 的 UID 明細在下一行，例如 "      cpu=185 mobile_radio=25.9 ..."）
    entries: list[dict] = []
    last: dict | None = None
    for line, is_start in _power_block_lines(text):
        g = POWER_GLOBAL_ROW_RE.match(line)
        if g:
            entries.append({
                "name": f"[全域] {g.group(1).strip()}",
                "raw": float(g.group(2)),
                "extra": g.group(4),
            })
            last = None
            continue
        if is_start:
            m = POWER_ITEM_RE.match(line)
            last = None
            if not m:
                continue
            name = re.sub(r"\s+", " ", m.group(1).strip())
            if name.lower() in EXCLUDED_POWER_NAMES:
                continue
            last = {"name": name, "raw": float(m.group(2)), "extra": m.group(3)}
            entries.append(last)
        elif last is not None:
            last["extra"] += " " + line.strip()

    for ent in entries:
        name = ent["name"]
        raw_mah = ent["raw"]
        extra = ent["extra"]

        if raw_mah <= 0:
            continue

        parts: dict[str, float] = {}
        for k, v in re.findall(r"(?<![:\w])([a-z_]+)=(-?\d+(?:\.\d+)?)", extra):
            if k in ("proportional", "reattributed"):
                continue
            k = {"wake": "wakelock", "sensor": "sensors", "gps": "gnss", "radio": "mobile_radio"}.get(k, k)
            parts.setdefault(k, float(v))

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
            "parts": parts,
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
                merged_parts = dict(acc.get("parts", {}))
                for pk, pv in item.get("parts", {}).items():
                    merged_parts[pk] = merged_parts.get(pk, 0.0) + pv
                acc["parts"] = merged_parts
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


def find_power_model(text: str) -> tuple[float, float, float] | None:
    """從 Capacity 列取 (computed drain, actual 下限, actual 上限)。"""
    m = re.search(
        r"Computed drain:\s*([\d.]+),\s*actual drain:\s*([\d.]+)(?:\s*-\s*([\d.]+))?",
        text,
    )
    if not m:
        return None
    lo = float(m.group(2))
    hi = float(m.group(3)) if m.group(3) else lo
    return float(m.group(1)), lo, hi


def is_component(item: dict) -> bool:
    """非 UID 列（Screen / Idle / Cell standby / Unaccounted / [全域] ...）視為元件。"""
    return item.get("is_global", False) or not re.match(r"^(?:UID|Uid)\s", item["name"])


def fmt_mah(v: float) -> str:
    """小於 1 mAh 時多顯示小數，避免出現 0.0。"""
    if v >= 1.0:
        return f"{v:.1f}"
    if v >= 0.01:
        return f"{v:.2f}"
    return "<0.01"


def find_profile_capacity(text: str) -> tuple[float, float | None, float | None] | None:
    """Capacity 列：'Capacity: 6000, Rated: 5830, Typical: 6000, ...'（電源設定檔容量）。"""
    m = re.search(
        r"Capacity:\s*([\d.]+)(?:,\s*Rated:\s*([\d.]+))?(?:,\s*Typical:\s*([\d.]+))?",
        text,
    )
    if not m:
        return None
    return (
        float(m.group(1)),
        float(m.group(2)) if m.group(2) else None,
        float(m.group(3)) if m.group(3) else None,
    )


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

def _size_to_bytes(num: str, unit: str) -> float:
    mult = {"B": 1.0, "KB": 1024.0, "MB": 1024.0**2, "GB": 1024.0**3}
    return float(num) * mult.get(unit.upper(), 1.0)


def _fmt_bytes(b: float) -> str:
    for unit, div in (("GB", 1024.0**3), ("MB", 1024.0**2), ("KB", 1024.0)):
        if b >= div:
            return f"{b / div:.2f} {unit}"
    return f"{b:.0f} B"


def parse_wifi_stats(text: str) -> dict | None:
    """解析 'Wifi Statistics:' 區塊（時間、流量、封包、狀態、RSSI）。"""
    lines = text.splitlines()
    idx = next((i for i, l in enumerate(lines) if re.match(r"^\s*Wifi Statistics:\s*$", l, re.IGNORECASE)), None)
    if idx is None:
        return None
    base = indent_of(lines[idx])
    block: list[str] = []
    for l in lines[idx + 1:]:
        if not l.strip():
            continue
        if indent_of(l) <= base:
            break
        block.append(l.strip())

    dur = rf"({DUR_PATTERN})\s*\(([\d.]+)%\)"
    d: dict = {"states": [], "supplicant": [], "rssi": []}
    section = None
    for l in block:
        m = re.match(rf"(?i)wifi kernel active time:\s*{dur}", l)
        if m:
            d["active_h"] = parse_duration_to_hours(m.group(1)); d["active_pct"] = float(m.group(2)); continue
        m = re.match(rf"(?i)wifi (scan|sleep|idle|rx|tx) time:\s*{dur}", l)
        if m:
            k = m.group(1).lower()
            d[f"{k}_h"] = parse_duration_to_hours(m.group(2)); d[f"{k}_pct"] = float(m.group(3)); continue
        m = re.match(r"(?i)wifi (?:battery|power) drain:\s*([\d.]+)\s*mAh", l)
        if m:
            d["drain_mah"] = float(m.group(1)); continue
        m = re.match(r"(?i)wifi data (received|sent):\s*([\d.]+)\s*(B|KB|MB|GB)", l)
        if m:
            d["data_" + m.group(1).lower()] = _size_to_bytes(m.group(2), m.group(3)); continue
        m = re.match(r"(?i)wifi packets (received|sent):\s*(\d+)", l)
        if m:
            d["pkts_" + m.group(1).lower()] = int(m.group(2)); continue
        if re.match(r"(?i)wifi states:", l):
            section = "states"; continue
        if re.match(r"(?i)wifi supplicant states:", l):
            section = "supplicant"; continue
        if re.match(r"(?i)wifi rx signal strength", l):
            section = "rssi"; continue
        if section in ("states", "supplicant"):
            m = re.match(rf"([\w-]+)\s+{dur}", l)
            if m:
                d[section].append((m.group(1), parse_duration_to_hours(m.group(2)), float(m.group(3))))
        elif section == "rssi":
            m = re.match(rf"(\w+)\s*\([^)]*\):\s*{dur}", l)
            if m:
                d["rssi"].append((m.group(1), parse_duration_to_hours(m.group(2)), float(m.group(3))))
    return d if len(d) > 3 else None


def print_wifi_stats(w: dict, battery_hours: float | None, discharge: float | None) -> None:
    print("\n=== Wi‑Fi 統計 ===")
    if "active_h" in w:
        print(f"Wi‑Fi 核心活躍（kernel active）：{w['active_h']:.2f} h（{w['active_pct']:.1f}%）")
    ctl = []
    for k, label in (("sleep", "睡眠"), ("idle", "閒置"), ("rx", "接收"), ("tx", "傳送"), ("scan", "掃描")):
        if f"{k}_h" in w:
            h = w[f"{k}_h"]
            t = f"{h * 60:.1f} 分" if h >= 1 / 60 else f"{h * 3600:.1f} 秒"
            ctl.append(f"{label} {t}（{w[f'{k}_pct']:.1f}%）")
    if ctl:
        print("控制器時間：" + "｜".join(ctl))
    rx, tx = w.get("data_received"), w.get("data_sent")
    if rx is not None and tx is not None:
        per_h = ""
        if battery_hours and battery_hours > 0:
            per_h = f"｜平均每小時 收 {_fmt_bytes(rx / battery_hours)} / 送 {_fmt_bytes(tx / battery_hours)}"
        print(f"流量：收 {_fmt_bytes(rx)} / 送 {_fmt_bytes(tx)}{per_h}")
    if "pkts_received" in w and "pkts_sent" in w:
        print(f"封包：收 {w['pkts_received']:,} / 送 {w['pkts_sent']:,}")
    if "drain_mah" in w:
        print(f"Wi‑Fi 耗電（驅動回報）：{w['drain_mah']:g} mAh（佔放電 {fmt_pct(w['drain_mah'], discharge)}）")
    def _dur(h: float) -> str:
        sec = h * 3600
        return f"{sec:.1f} 秒" if sec < 90 else (f"{sec / 60:.1f} 分" if sec < 5400 else f"{h:.2f} h")

    odd = [f"state {n} {_dur(h)}" for n, h, p in w["states"] if n.lower() != "sta" and h > 0]
    odd += [f"supplicant {n} {_dur(h)}" for n, h, p in w["supplicant"] if n.lower() != "completed" and h > 0]
    if odd:
        print("非穩定連線狀態：" + "｜".join(odd))
    if w["rssi"]:
        print("訊號分布：" + "｜".join(f"{n} {p:.1f}%" for n, _, p in w["rssi"] if p > 0))
    zero_ctl = all(w.get(k, 0) in (0, 0.0) for k in ("rx_h", "tx_h", "data_received", "data_sent"))
    if zero_ctl and "sleep_h" in w:
        print("※ Rx/Tx 時間與流量皆為 0：此機型驅動未回報控制器計數，只有 kernel active 可參考。")


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
        parts = item.get("parts") or {}
        floor = max(0.05, item["mah"] * 0.01)
        for k, v in sorted(parts.items(), key=lambda kv: kv[1], reverse=True):
            if v >= floor and len(details) < 4:
                details.append(f"{k}={_format_num(v)}")
        if item.get("smeared"):
            details.append(f"分攤前 {fmt_mah(item['raw'])}")
        extra_str = f"（{', '.join(details)}）" if details else ""
        flag = ""
        if total_discharge and total_discharge > 0 and item["mah"] > total_discharge:
            flag = " ⚠ 超過累計放電，請確認原始統計"
        if item["name"].lower() in ("unaccounted", "over-counted"):
            flag += "（功耗模型與實際放電的差額，不是某個 App）"
        print(f"{idx:>2}. {label}：{fmt_mah(item['mah'])} mAh（佔放電 {share}）{extra_str}{flag}")


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
    shared_note = [False]

    for idx, item in enumerate(locks, start=1):
        raw_label = format_uid_label(item["name"], uid_pkgs_map) if uid_pkgs_map else item["name"]
        label = mask_emails(raw_label)
        if item.get("merged_count", 1) > 1:
            label = f"{label} [合併 {item['merged_count']} 筆]"
        mins = item["minutes"]
        dur_str = f"{mins:.1f} 分鐘" if mins >= 1.0 else f"{mins * 60:.1f} 秒"
        share = f"｜佔使用時長 {fmt_pct(item['hours'], total_hours)}" if total_hours else ""
        mx_ms = item.get("max_ms")
        mx_str = ""
        if mx_ms is not None and mx_ms >= 30000:
            sec = mx_ms / 1000.0
            mx_str = f"，單次最長 {sec / 60:.1f} 分鐘" if sec >= 60 else f"，單次最長 {sec:.0f} 秒"
        act_ms = item.get("actual_ms")
        act_str = ""
        if act_ms is not None and act_ms >= 30000 and act_ms >= item["hours"] * 3600000 * 1.2:
            act_str = f"｜實際持有 {act_ms / 60000:.1f} 分鐘" if act_ms >= 90000 else f"｜實際持有 {act_ms / 1000:.0f} 秒"
            shared_note[0] = True
        run_ms = item.get("running_ms")
        run_str = ""
        if run_ms is not None and run_ms >= 30000:
            run_str = f" ⚠ 目前仍在持有（已 {run_ms / 60000:.1f} 分鐘）"
        print(f"{idx:>2}. {label}：{dur_str}（{item['count']} 次{mx_str}）{act_str}{share}{run_str}")
    if shared_note[0]:
        print("※ 累計時間在多個鎖同時持有時會被攤分；『實際持有』與『單次最長』是牆上時間，所以累計可以小於單次最長。")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="分析 Android dumpsys batterystats 耗電與喚醒資訊")
    parser.add_argument("top_n_pos", nargs="?", type=int, help="顯示前幾名項目（預設 10）")
    parser.add_argument("-n", "--top", type=int, default=10, help="顯示前幾名項目（預設 10）")
    parser.add_argument("-f", "--file", type=str, default=None, help="改從本機 batterystats 文字檔讀取")
    parser.add_argument("-m", "--merge", action="store_true", help="合併估算排行榜中的同名項目")
    parser.add_argument("--merge-wl", action="store_true", help="合併背景喚醒（Partial Wake Lock）中的同名項目")
    parser.add_argument("--hide-wm", action="store_true", help="背景喚醒排行隱藏 WindowManager 項目")
    parser.add_argument("--strict-mask", action="store_true", help="信箱完整遮成 [EMAIL]（預設保留首尾字元與網域）")
    parser.add_argument("-V", "--version", action="version", version=f"%(prog)s {__version__} ({__date__})")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    global STRICT_MASK
    STRICT_MASK = args.strict_mask
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
            if ratio > 1.005:
                ratio_s = (
                    f"（學習/估計 = {ratio * 100:.1f}%，兩者不一致，"
                    "不代表電池健康度；容量需以實測確認）"
                )
            else:
                ratio_s = f"（健康度約 {ratio * 100:.1f}%）"
        print(f"學習容量範圍：{min_s} ~ {max_s} mAh{ratio_s}")
    prof = find_profile_capacity(summary)
    if prof:
        extra_cap = "".join(
            [f"｜Rated {prof[1]:.0f}" if prof[1] else "", f"｜Typical {prof[2]:.0f}" if prof[2] else ""]
        )
        print(f"電源設定檔容量：{prof[0]:.0f} mAh{extra_cap}")
    if battery_hours is not None:
        print(f"電池使用總時長：{battery_hours:.2f} 小時")

    print("\n=== 整體耗電摘要 ===")
    if discharge is not None:
        print(
            f"累計放電：{discharge:.0f} mAh"
            f"｜估計容量比：{fmt_pct(discharge, est_cap)}"
            f"｜學習容量比：{fmt_pct(discharge, max_learned)}"
        )
        model = find_power_model(summary)
        if model and (model[0] > 0 or model[2] > 0):
            computed, act_lo, act_hi = model
            if act_hi <= 0:
                act_s = "無資料（電量級距尚未下降）"
            elif act_lo == act_hi:
                act_s = f"{act_lo:.0f} mAh"
            else:
                act_s = f"{act_lo:.0f}–{act_hi:.0f} mAh"
            print(f"功耗模型估算：{computed:.0f} mAh｜系統實際（電量級距 × 設定檔容量）：{act_s}")
            act_mid = (act_lo + act_hi) / 2
            aligned = discharge > 0 and abs(computed - discharge) <= max(1.0, discharge * 0.01)
            if aligned:
                print("※ Discharge 與功耗模型估算相同（Android 13+ 的放電值已與模型對齊，不是獨立量測）。")
            if computed > 0 and act_mid > 0:
                ratio = computed / act_mid
                if aligned and (ratio < 0.9 or ratio > 1.1):
                    gap_pct = abs(ratio - 1) * 100
                    gap_mah = abs(computed - act_mid)
                    cap_ratio = (est_cap / prof[0]) if (prof and est_cap and prof[0] > 0) else None
                    if cap_ratio is not None and abs(cap_ratio - 1) > 0.05:
                        print(
                            f"※ 與電量級距換算值相差 {gap_pct:.0f}%：估計容量 {est_cap:.0f} 與設定檔容量 {prof[0]:.0f} 的比值為 "
                            f"{cap_ratio * 100:.0f}%，這通常是容量來源不一致；絕對 mAh 可能整體偏低或偏高，相對排名不受影響。"
                        )
                    else:
                        cap_ref = est_cap or (prof[0] if prof else None)
                        step = cap_ref / 100.0 if cap_ref else None
                        steps = gap_mah / step if step else None
                        cap_txt = "估計容量與設定檔容量一致，" if cap_ratio is not None else ""
                        if steps is not None and steps <= 2.0:
                            print(
                                f"※ 與電量級距換算值相差 {gap_pct:.0f}%（約 {gap_mah:.0f} mAh）：{cap_txt}"
                                f"差距在 2 個 1% 級距以內，可能只是級距粒度。"
                            )
                        else:
                            steps_txt = f"，約 {steps:.1f} 個 1% 級距" if steps is not None else ""
                            print(
                                f"※ 與電量級距換算值相差 {gap_pct:.0f}%（約 {gap_mah:.0f} mAh{steps_txt}）：{cap_txt}"
                                f"所以不是容量來源問題，也不是單純的級距粒度；較可能是『放電計數』與『顯示電量』的起點不同"
                                f"（例如顯示 100% 時已先耗電），需要同時記錄起訖電量才能確認。"
                            )
                elif not aligned and ratio < 0.8:
                    print(f"※ 功耗模型只解釋實際放電的約 {ratio * 100:.0f}%，估算的絕對 mAh 偏低，只適合看相對排名。")
                elif not aligned and ratio > 1.2:
                    print(f"※ 功耗模型約為實際放電的 {ratio * 100:.0f}%，估算偏高，只適合看相對排名。")
        if est_cap and discharge > 0:
            step = est_cap / 100.0
            q = discharge / step
            if abs(q - round(q)) < 0.02 and round(q) >= 1:
                print(f"※ 放電值恰為 1% 級距的整數倍（每級約 {step:.1f} mAh，共 {round(q)} 級），短時間內的 mAh/h 誤差很大。")
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
    if screen_on_hours is not None and screen_on_hours < 0.5:
        print(f"※ 亮屏時間只有 {screen_on_hours * 60:.0f} 分鐘，亮屏耗電率不具代表性。")
    if screen_off_hours is not None and screen_off_hours < 1.0:
        print(f"※ 熄屏時間只有 {screen_off_hours * 60:.0f} 分鐘，熄屏耗電率不具代表性。")
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

    wifi = parse_wifi_stats(summary)
    if wifi:
        print_wifi_stats(wifi, battery_hours, discharge)

    top_kernel_locks = parse_kernel_wakelocks(summary, top_n=top_n)
    top_partial_locks = parse_partial_wakelocks(
        summary,
        top_n=top_n,
        hide_wm=args.hide_wm,
        merge_wl=args.merge_wl,
    )

    all_items = parse_power_items(summary, merge_same_name=args.merge)
    top_uid = [item for item in all_items if not is_component(item)][:top_n]
    top_comp = [item for item in all_items if is_component(item)][:top_n]
    top_u0a = [item for item in all_items if item["is_user_app"]][:top_n]
    any_smeared = any(item["smeared"] for item in all_items)

    uid_pkgs_map = resolve_uids_packages(top_uid + top_u0a + top_partial_locks, offline=offline)

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
        f"=== 最耗電 UID / 系統項目 Top {top_n}（估算）===",
        top_uid,
        discharge,
        uid_pkgs_map,
    )
    print_ranking(
        f"=== 元件耗電 Top {top_n}（估算）===",
        top_comp,
        discharge,
        uid_pkgs_map,
    )
    if any(item["is_global"] for item in top_comp):
        print("※ [全域] 各列是各 App 與系統的分攤合計，與上方 UID 排名重疊，且估算加總可能超過實際放電，請只看相對大小。")
    if any_smeared:
        print("※ 舊版輸出的 App 數值已含 Screen 等分攤，不可與 Screen / Cell standby 等元件相加。")
    print_ranking(
        f"=== 使用者 App（u0a）Top {top_n}（估算）===",
        top_u0a,
        discharge,
        uid_pkgs_map,
    )


if __name__ == "__main__":
    main()
