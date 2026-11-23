# `battery.py` 使用手冊與名詞解釋

本手冊說明如何在 Termux 透過 `adb` 執行 `~/doze/battery.py` 查詢 Android 電池耗電率、Doze 待機、喚醒（Wakelock）排行與 `u0a` 套件反查，並示範如何以 `>` 或 `tee` 匯出帶時間戳記的純文字報告檔。

---

## 一、基本使用方式

### 1. 執行腳本（預設 Top 10）
```bash
python3 ~/doze/battery.py
```

### 2. 指定顯示前 N 名（例如 Top 15）
```bash
python3 ~/doze/battery.py 15
```

> 說明：腳本會先透過 `adb shell getprop` 讀取裝置與系統資訊，再抓取 `adb shell dumpsys batterystats` 進行解析，並針對前幾名涉及的 UID 查詢對應套件名稱，最後自動將電子信箱去識別化（例如 `s***w@yahoo.com.tw`）。

---

## 二、使用 `>` 或 `tee` 匯出帶時間檔名的報告檔

在 Termux（Bash / Zsh）中，可利用 `$(date +%Y%m%d_%H%M%S)` 動態產生時間檔名，方便做多次充放電或待機測試的對照紀錄。

### 1. 只存檔、不在螢幕顯示（使用 `>`）
```bash
mkdir -p ~/doze/reports
python3 ~/doze/battery.py > ~/doze/reports/battery_$(date +%Y%m%d_%H%M%S).txt
```

### 2. 同時顯示在螢幕並存成檔案（使用 `tee`）
```bash
mkdir -p ~/doze/reports
python3 ~/doze/battery.py | tee ~/doze/reports/battery_$(date +%Y%m%d_%H%M%S).txt
```

### 3. 搭配自訂 Top N 與 `tee` 匯出
```bash
mkdir -p ~/doze/reports
python3 ~/doze/battery.py 15 | tee ~/doze/reports/battery_$(date +%Y%m%d_%H%M%S)_top15.txt
```

### 4. 加上 `2>&1` 同時記錄錯誤訊息（排錯用）
```bash
mkdir -p ~/doze/reports
python3 ~/doze/battery.py 2>&1 | tee ~/doze/reports/battery_$(date +%Y%m%d_%H%M%S).log
```

### 5. 查看與比對已匯出的報告檔
```bash
ls -lh ~/doze/reports/
cat ~/doze/reports/battery_20261123_081500.txt
```

> 提醒：使用 `>` 覆蓋寫入新檔案時，若檔名相同會覆蓋原檔；加上 `%Y%m%d_%H%M%S` 可避免檔名衝突。若 `adb` 輸出尾端偶爾出現 `Broken pipe` 提示，通常不影響已產生的報告內容。

---

## 三、名詞解釋

### 1. 電池容量與健康度
* **估計電池容量（Estimated battery capacity）**：系統或電池設定檔記載的標稱／估計容量（mAh），例如 `5020 mAh`。
* **學習容量範圍（Min / Max learned battery capacity）**：系統根據實際充放電循環推算出的可用容量區間（mAh）。當電池老化或衰退時，學習容量常低於估計容量；腳本會以此估算「健康度」與更貼近實際的 `%/h` 耗電率。
* **累計放電（Discharge）**：自上次充電起算週期內的總放電量（mAh）。
* **亮屏 + 熄屏合計與差值**：將 `Screen on discharge` 與 `Screen off discharge` 相加後，與 `Discharge` 比對的差值；正常情況通常接近 `0` 或僅差數 mAh。

### 2. 亮屏與熄屏耗電率
* **亮屏耗電率（Screen on rate）**：螢幕開啟期間的平均每小時耗電量（`mAh/h` 與 `%/h`），受螢幕亮度、更新率、遊戲或影音播放影響最大。
* **熄屏耗電率（Screen off rate）**：螢幕關閉期間的平均每小時耗電量（`mAh/h` 與 `%/h`），主要反映待機、背景同步、通知推送與網路喚醒的表現。

### 3. 待機、Doze 與喚醒
* **淺睡（Light doze / Device light idling）**：螢幕關閉後較早進入的低功耗待機階段，仍允許部分定期維護或網路工作執行。
* **深睡（Deep doze / Device full idling）**：螢幕關閉且裝置靜置一段時間後進入的深度省電狀態，會進一步限制背景網路存取、喚醒鬧鐘與背景工作。深睡佔熄屏比例越高，通常代表待機越穩定。
* **Full wakelock**：要求保持螢幕或較高層級清醒狀態的喚醒鎖累計時間。
* **Partial wakelock**：允許螢幕保持關閉，但讓 CPU 維持清醒以執行背景運算、工作排程或同步的喚醒鎖累計時間。

### 4. 核心喚醒與背景喚醒排行
* **核心喚醒（Kernel Wake Lock）Top N**：Linux 核心與驅動程式層級的喚醒統計（如 `WLAN timeout`、`MT662x`、`WLAN hif_thread` 等）。**時間長**代表持續佔用喚醒較久；**次數高但時間短**則代表高頻短喚醒（例如 Wi-Fi 封包／中斷頻繁）。
* **背景喚醒（Partial Wake Lock）Top N**：應用程式、系統服務、工作排程（`*job*`）或同步任務（`*sync*`）持有的喚醒鎖排行，腳本會自動去除重複項目、反查 UID 對應套件名稱，並將電子信箱遮罩。

### 5. 耗電項目排行與 UID
* **最耗電項目 Top N（總覽估算）**：`Estimated power use (mAh)` 區塊中依估算耗電量排序的項目，除了 `Uid` 之外，也可能包含 `Screen`、`User activity`、`WiFi AP wakeups`、`Starts`、`Cell standby`、`Idle` 等系統或事件項目。
* **WiFi AP wakeups**：Wi-Fi 連線期間受無線基地台（AP）廣播或封包喚醒所估算的耗電量；若數值偏高，通常與網路環境、頻段（2.4GHz / 5GHz）或背景掃描設定有關。
* **Uid 與 `u0a...`**：Android 為每個應用程式或系統元件分配的使用者識別碼（UID）。一般第三方或使用者安裝的 App 常見 `u0a<編號>` 格式（對應 `10000 + <編號>`）；`Uid 1000` 則代表 Android 系統／核心服務群組。

---
```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import subprocess
import sys


def run_adb_shell(args: list[str], timeout: int = 15, check: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["adb", "shell", *args],
        capture_output=True,
        text=True,
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

    return {
        "model": model_display,
        "android": android_display,
        "build": build_id,
    }


def get_stats() -> str:
    try:
        result = run_adb_shell(["dumpsys", "batterystats"], timeout=30, check=True)
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
    for marker in ("\nPer-app mobile", "\nEstimated power use", "\nBattery History"):
        idx = sub.find(marker)
        if idx != -1:
            sub = sub[:idx]
            break
    return sub


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
    """將字串中的電子信箱去識別化，例如 alice@gmail.com -> a***e@gmail.com。"""
    return re.sub(
        r"\b([A-Za-z0-9._%+-]+)@([A-Za-z0-9.-]+\.[A-Za-z]{2,})\b",
        mask_email_match,
        text,
    )


def extract_uid_token(name: str) -> tuple[str | None, str | None]:
    """
    從項目名稱擷取 UID 資訊。
    回傳 (raw_token, numeric_uid)，例如 'u0a182 ...' -> ('u0a182', '10182')。
    """
    m = re.search(r"\b(u0a(\d+)|(\d+))\b", name, re.IGNORECASE)
    if not m:
        return None, None

    raw_token = m.group(1).lower()
    if m.group(2) is not None:
        try:
            num_uid = str(10000 + int(m.group(2)))
        except ValueError:
            num_uid = None
        return raw_token, num_uid

    return raw_token, m.group(3)


def query_packages_by_uid(num_uid: str | None, raw_token: str | None) -> list[str]:
    """針對單一 UID 精準反查對應的套件名稱。"""
    candidates: list[str] = []
    if num_uid:
        candidates.append(num_uid)
    if raw_token and raw_token not in candidates:
        candidates.append(raw_token)

    for uid_arg in candidates:
        try:
            res = run_adb_shell(["cmd", "package", "list", "packages", "--uid", uid_arg], timeout=8)
            if res.returncode == 0 and res.stdout:
                pkgs: list[str] = []
                for line in res.stdout.splitlines():
                    line = line.strip()
                    if line.startswith("package:"):
                        pkg = line.split(":", 1)[1].strip().split()[0]
                        if pkg and pkg not in pkgs:
                            pkgs.append(pkg)
                if pkgs:
                    return pkgs
        except Exception:
            pass

    if not num_uid:
        return []

    try:
        res = run_adb_shell(["dumpsys", "package"], timeout=15)
        if res.returncode != 0 or not res.stdout:
            return []

        pkgs: list[str] = []
        current_pkg: str | None = None
        target_pattern = re.compile(rf"\b(?:userId|appId)={re.escape(num_uid)}\b")

        for line in res.stdout.splitlines():
            pkg_m = re.match(r"^\s*Package \[([^\]]+)\]:", line)
            if pkg_m:
                current_pkg = pkg_m.group(1).strip()
                continue
            if current_pkg and target_pattern.search(line):
                if current_pkg not in pkgs:
                    pkgs.append(current_pkg)
        return pkgs
    except Exception:
        return []


def resolve_uids_packages(rows: list[dict]) -> dict[str, list[str]]:
    """只針對傳入項目涉及的 UID 進行精準反查。"""
    resolved: dict[str, list[str]] = {}
    for item in rows:
        raw_token, num_uid = extract_uid_token(item["name"])
        key = (raw_token or num_uid or "").lower()
        if not key or key in resolved:
            continue
        resolved[key] = query_packages_by_uid(num_uid, raw_token)
    return resolved


def format_uid_label(name: str, uid_pkgs_map: dict[str, list[str]]) -> str:
    """若名稱包含 UID 且已查到套件名稱，則附上套件名稱。"""
    raw_token, num_uid = extract_uid_token(name)
    key = (raw_token or num_uid or "").lower()
    pkgs = uid_pkgs_map.get(key)
    if not pkgs:
        return name
    preview = ", ".join(pkgs[:2]) + (" 等" if len(pkgs) > 2 else "")
    return f"{name} [{preview}]"


def parse_duration_to_hours(duration_str: str) -> float | None:
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


def parse_kernel_wakelocks(text: str, top_n: int = 10) -> list[dict]:
    """
    解析 'All kernel wake locks:' 區塊中以 'Kernel Wake lock' 開頭的核心喚醒項目。
    """
    m = re.search(r"^\s*All kernel wake locks?:\s*$", text, re.MULTILINE | re.IGNORECASE)
    if not m:
        return []

    block = text[m.end():]
    stop_m = re.search(r"^\s*All partial wake locks?:\s*$", block, re.MULTILINE | re.IGNORECASE)
    if stop_m:
        block = block[:stop_m.start()]
    else:
        stop_top = re.search(r"^\S", block, re.MULTILINE)
        if stop_top:
            block = block[:stop_top.start()]

    locks: list[dict] = []
    for line in block.splitlines():
        if not line.strip():
            continue
        row_m = re.match(
            r"^\s*Kernel\s+Wake\s+lock\s+(.+?):\s*(.+?)\s*\((\d+)\s*times?\)",
            line,
            re.IGNORECASE,
        )
        if not row_m:
            continue
        name = re.sub(r"\s+", " ", row_m.group(1).strip())
        dur_part = row_m.group(2).strip()
        times_int = int(row_m.group(3))

        hours = parse_duration_to_hours(dur_part)
        if hours is None or hours <= 0:
            continue

        locks.append({
            "name": name,
            "hours": hours,
            "minutes": hours * 60.0,
            "count": times_int,
        })

    locks.sort(key=lambda item: item["hours"], reverse=True)
    return locks[:top_n]


def parse_partial_wakelocks(text: str, top_n: int = 10) -> list[dict]:
    """
    嚴格解析 'All partial wake locks:' 區塊中以 'Wake lock ' 開頭的喚醒項目，
    排除 Sensor / Foreground services 等非 wakelock 行，並自動去除完全重複項目。
    """
    m = re.search(r"^\s*All partial wake locks?:\s*$", text, re.MULTILINE | re.IGNORECASE)
    if not m:
        return []

    block = text[m.end():]
    stop_m = re.search(r"^\S", block, re.MULTILINE)
    if stop_m:
        block = block[:stop_m.start()]

    raw_locks: list[dict] = []
    for line in block.splitlines():
        if not line.strip():
            continue
        row_m = re.match(
            r"^\s*Wake\s+lock\s+(.+?):\s*(.+?)\s*\((\d+)\s*times?\)",
            line,
            re.IGNORECASE,
        )
        if not row_m:
            continue
        name = re.sub(r"\s+", " ", row_m.group(1).strip())
        dur_part = row_m.group(2).strip()
        times_int = int(row_m.group(3))

        hours = parse_duration_to_hours(dur_part)
        if hours is None or hours <= 0:
            continue

        raw_locks.append({
            "name": name,
            "hours": hours,
            "minutes": hours * 60.0,
            "count": times_int,
        })

    raw_locks.sort(key=lambda item: item["hours"], reverse=True)

    deduped: list[dict] = []
    seen_keys: set[tuple[str, float, int]] = set()
    for item in raw_locks:
        norm_name = re.sub(r"^(?:u0a\d+|\d+)\s+", "", item["name"], flags=re.IGNORECASE).strip()
        dedup_key = (norm_name, round(item["minutes"], 2), item["count"])
        if dedup_key in seen_keys:
            continue
        seen_keys.add(dedup_key)
        deduped.append(item)
        if len(deduped) >= top_n:
            break

    return deduped


def parse_power_items(
    text: str,
    max_reasonable_mah: float | None = None,
) -> list[dict]:
    """
    解析 'Estimated power use (mAh):' 區塊中的估算項目，
    並排除 'Total cpu time per freq'、'CPU freqs' 等非耗電統計行。
    """
    start_match = re.search(r"^\s*Estimated power use\s*\(mAh\):\s*$", text, re.MULTILINE)
    if not start_match:
        return []

    block = text[start_match.end():]
    stop_match = re.search(
        r"^(?:Battery History|Per-app |All kernel wake ?locks|Wake lock |Kernel |CPU freqs|Total cpu time)\b",
        block,
        re.MULTILINE | re.IGNORECASE,
    )
    if stop_match:
        block = block[:stop_match.start()]

    excluded_exact = {
        "capacity",
        "computed drain",
        "actual drain",
        "unaccounted",
        "over-counted",
        "cpu freqs",
        "total cpu time per freq",
        "total screen-off cpu time per freq",
    }
    excluded_prefixes = (
        "total cpu time",
        "total screen-off cpu time",
        "cpu freqs",
        "screen brightnesses",
        "device light",
        "device full",
        "idle mode",
        "connectivity changes",
        "total full wakelock",
        "total partial wakelock",
    )

    items: list[dict] = []
    number_pattern = r"-?(?:\d+\.?\d*|\.\d+)"

    for line in block.splitlines():
        if not line.strip():
            continue

        m = re.match(
            rf"^\s+([^:\n]+?):\s*({number_pattern})\s*(?:mAh)?(?:\s|,|\(|$)(.*)$",
            line,
            re.IGNORECASE,
        )
        if not m:
            continue

        name = re.sub(r"\s+", " ", m.group(1).strip())
        name_lower = name.lower()

        if name_lower in excluded_exact or any(name_lower.startswith(p) for p in excluded_prefixes):
            continue

        if "cpu freq" in name_lower or "time per freq" in name_lower:
            continue

        try:
            mah = float(m.group(2))
        except ValueError:
            continue

        if mah <= 0:
            continue

        if max_reasonable_mah is not None and mah > max_reasonable_mah:
            continue

        extra = m.group(3).strip()
        wake_match = re.search(r"wake lock=([^,)]+)", extra, re.IGNORECASE)
        cpu_match = re.search(r"cpu=([^,)]+)", extra, re.IGNORECASE)

        is_user_app = bool(re.search(r"\bu0a\d+\b", name, re.IGNORECASE))

        items.append({
            "name": name,
            "mah": mah,
            "wake": wake_match.group(1).strip() if wake_match else None,
            "cpu": cpu_match.group(1).strip() if cpu_match else None,
            "is_user_app": is_user_app,
        })

    items.sort(key=lambda item: item["mah"], reverse=True)
    return items


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


def find_duration_hours(text: str, label: str) -> float | None:
    raw = find_raw_line(text, label)
    if not raw:
        return None
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
        share = fmt_pct(item["mah"], total_discharge)
        details = []
        if item["cpu"]:
            details.append(f"cpu={item['cpu']}")
        if item["wake"]:
            details.append(f"wake={item['wake']}")
        extra_str = f"（{', '.join(details)}）" if details else ""
        print(f"{idx:>2}. {label}：{item['mah']:.1f} mAh（佔放電 {share}）{extra_str}")


def print_wakelock_ranking(
    title: str,
    locks: list[dict],
    screen_off_hours: float | None,
    uid_pkgs_map: dict[str, list[str]] | None = None,
) -> None:
    print(f"\n{title}")
    if not locks:
        print("  查無喚醒明細。")
        return

    for idx, item in enumerate(locks, start=1):
        raw_label = format_uid_label(item["name"], uid_pkgs_map) if uid_pkgs_map else item["name"]
        label = mask_emails(raw_label)
        mins = item["minutes"]
        dur_str = f"{mins:.1f} 分鐘" if mins >= 1.0 else f"{mins * 60:.1f} 秒"
        off_share = f"｜佔熄屏 {fmt_pct(item['hours'], screen_off_hours)}" if screen_off_hours else ""
        cnt_str = f"（{item['count']} 次）" if item["count"] is not None else ""
        print(f"{idx:>2}. {label}：{dur_str}{cnt_str}{off_share}")


def main() -> None:
    top_n = 10
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        top_n = max(1, int(sys.argv[1]))

    device_info = get_device_info()
    raw_text = get_stats()
    summary = extract_summary_section(raw_text)

    start_clock = find_raw_line(summary, "Start clock time")
    est_cap = find_value(summary, "Estimated battery capacity")
    min_learned = find_value(summary, "Min learned battery capacity")
    max_learned = find_value(summary, "Max learned battery capacity")

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

    print("=== 裝置與系統資訊 ===")
    if device_info["model"]:
        print(f"機型：{device_info['model']}")
    if device_info["android"]:
        print(f"系統版本：{device_info['android']}")
    if device_info["build"]:
        print(f"韌體版本：{device_info['build']}")

    print("\n=== 電池與統計週期資訊 ===")
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
            f"｜估計容量比：{fmt_pct(discharge, est_cap)}"
            f"｜學習容量比：{fmt_pct(discharge, max_learned)}"
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

    top_kernel_locks = parse_kernel_wakelocks(raw_text, top_n=top_n)
    top_partial_locks = parse_partial_wakelocks(raw_text, top_n=top_n)

    max_reasonable_mah = discharge * 1.5 if discharge else None
    all_items = parse_power_items(raw_text, max_reasonable_mah=max_reasonable_mah)
    top_all = all_items[:top_n]
    top_u0a = [item for item in all_items if item["is_user_app"]][:top_n]

    target_rows = top_all + top_u0a + top_partial_locks
    uid_pkgs_map = resolve_uids_packages(target_rows)

    print_wakelock_ranking(
        f"=== 核心喚醒（Kernel Wake Lock）Top {top_n} ===",
        top_kernel_locks,
        screen_off_hours,
    )
    print_wakelock_ranking(
        f"=== 背景喚醒（Partial Wake Lock）Top {top_n} ===",
        top_partial_locks,
        screen_off_hours,
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
```
