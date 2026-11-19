# Android 電量報告雙檔自動過濾與隱私去識別化指南

本指南提供升級版的 `battery_extract.py` 腳本，支援直接讀取 `full.txt` 與 `checkin.txt`（或透過命令列參數指定路徑），自動將抽象的 UID 翻譯成真實 App 名稱，並嘗試遮蔽常見個人敏感資訊。

---

## 一、 升級版腳本核心功能

1. **雙檔聯動自動翻譯 App（`full.txt` + `checkin.txt`）**
   * 使用標準 `csv` 模組穩健解析 `checkin.txt` 內的 `uid` 紀錄行，並在 `full.txt` 的耗電與喚醒鎖清單後方自動標註真實 App 套件名稱（例如 `Uid u0a1178 ... --> [in.mfile]`）；若同一 UID 對應多個套件（Shared UID），會自動摘要顯示前 2 個並標註剩餘數量（如 `(+2 more)`），無需再連接手機查詢。
2. **智慧型隱私去識別化（保留網域判斷能力）**
   * **Email 智慧遮罩**：將 `user@yahoo.com.tw` 替換為 `[EMAIL_HIDDEN@yahoo.com.tw]`。隱藏個人帳號名稱，同時保留信箱服務商網域，便於判斷是否為傳統 IMAP/POP3 輪詢耗電。
   * **常見網路與身分資訊遮蔽**：自動過濾 IPv4 位址、MAC 位址、台灣手機號碼（`09xx`）與 Wi-Fi SSID 名稱。
   * **保守聲明提醒**：正則過濾僅涵蓋常見格式，產出摘要時會附上人工複檢提醒，避免將「部分遮蔽」誤認為「100% 匿名化」。
3. **防爆額度截斷與命令列參數（CLI）設計**
   * 耗電與喚醒鎖清單預設僅保留耗電量最高的 **前 35 名**，自動省略後方微量耗電項目，將報告體積壓縮至約 10–15 KB。
   * 支援 `-f` / `-c` / `-o` / `-m` 命令列參數，無需修改程式碼即可在不同測試資料夾中直接指定輸入與輸出檔名。

---

## 二、 完整 Python 腳本原始碼（`battery_extract.py`）

將以下程式碼儲存為 `battery_extract.py`（例如放在 Termux 的 `~/doze/battery_extract.py`），僅使用 Python 內建標準函式庫，無需安裝額外套件：

```python
import argparse
import csv
import os
import re
import sys


def parse_uid_map_from_checkin(checkin_path="checkin.txt", max_pkgs_per_uid=2):
    uid_map = {}
    if not os.path.exists(checkin_path):
        return uid_map

    with open(checkin_path, "r", encoding="utf-8", errors="replace", newline="") as f:
        for parts in csv.reader(f):
            if len(parts) >= 6:
                record_type = parts[2].strip()
                entry_type = parts[3].strip()
                raw_uid = parts[4].strip()
                pkg_name = parts[5].strip()

                if record_type == "i" and entry_type == "uid" and pkg_name and raw_uid.isdigit():
                    uid_int = int(raw_uid)
                    formatted_uid = f"u0a{uid_int - 10000}" if uid_int >= 10000 else str(uid_int)

                    pkgs = uid_map.setdefault(formatted_uid, [])
                    if pkg_name not in pkgs:
                        pkgs.append(pkg_name)

    formatted_map = {}
    for uid, pkgs in uid_map.items():
        if max_pkgs_per_uid is not None and len(pkgs) > max_pkgs_per_uid:
            shown = " / ".join(pkgs[:max_pkgs_per_uid])
            formatted_map[uid] = f"{shown} (+{len(pkgs) - max_pkgs_per_uid} more)"
        else:
            formatted_map[uid] = " / ".join(pkgs)

    return formatted_map


def mask_sensitive_info(text):
    text = re.sub(r"\b[A-Za-z0-9._%+-]+@([A-Za-z0-9.-]+\.[A-Za-z]{2,})\b", r"[EMAIL_HIDDEN@\1]", text)
    text = re.sub(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", "[IP_HIDDEN]", text)
    text = re.sub(r"\b(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}\b", "[MAC_HIDDEN]", text)
    text = re.sub(r"\b09\d{2}-?\d{3}-?\d{3}\b", "[PHONE_HIDDEN]", text)
    text = re.sub(r'(SSID\s*[:=]\s*)"[^"]+"', r'\1"[WIFI_SSID_HIDDEN]"', text, flags=re.IGNORECASE)
    return text


def inject_app_names(line, uid_map):
    if not uid_map:
        return line
    match = re.search(r"\b(u0a\d+)\b", line)
    if match:
        uid_str = match.group(1)
        app_label = uid_map.get(uid_str)
        if app_label:
            primary_pkg = app_label.split(" / ")[0].split(" (+")[0]
            if primary_pkg not in line:
                return f"{line}  --> [{app_label}]"
    return line


def extract_battery_report(
    full_path="full.txt",
    checkin_path="checkin.txt",
    output_path="battery_for_ai.txt",
    max_lines=35,
):
    if not isinstance(max_lines, int) or isinstance(max_lines, bool) or max_lines < 0:
        raise ValueError("max_lines 必須是非負整數")

    if not os.path.exists(full_path):
        raise FileNotFoundError(f"找不到輸入檔案：{full_path}")

    uid_map = parse_uid_map_from_checkin(checkin_path)
    print(f"[資訊] 成功從 {checkin_path} 載入 {len(uid_map)} 筆 App 名稱對照表！")

    # (section_key, display_title, match_keyword, limit_lines)
    target_sections = [
        ("stats", "1. 整體放電概況 (Statistics since last charge)", "Statistics since last charge:", False),
        ("power_use", "2. 各硬體與 App 耗電排名 (Estimated power use)", "Estimated power use (mAh):", True),
        ("partial_wl", "3. 背景程式喚醒鎖排名 (All partial wake locks)", "All partial wake locks:", True),
        ("kernel_wl", "4. 底層硬體驅動喚醒鎖 (All kernel wake locks)", "All kernel wake locks:", True),
    ]
    all_section_keywords = [kw for _, _, kw, _ in target_sections]

    extracted_data = {key: [] for key, _, _, _ in target_sections}
    current_key = None

    with open(full_path, "r", encoding="utf-8", errors="replace") as f:
        for raw_line in f:
            line_stripped = raw_line.strip()

            # 檢查是否進入新的目標區塊
            matched_key = None
            for key, _, keyword, _ in target_sections:
                if keyword in line_stripped:
                    matched_key = key
                    break

            if matched_key is not None:
                current_key = matched_key
                continue

            if current_key is not None:
                # 遇到空行且該區塊已有資料，代表段落結束
                if line_stripped == "":
                    if len(extracted_data[current_key]) > 0:
                        current_key = None
                    continue

                # 若遇到其他已知區塊標題，提前結束目前區塊
                if any(kw in line_stripped for kw in all_section_keywords):
                    current_key = None
                    continue

                # 喚醒鎖區塊通常以 "Wake lock " 開頭；若遇到非此格式且已有資料，視作段落結束
                if current_key in ("partial_wl", "kernel_wl") and not line_stripped.startswith("Wake lock"):
                    if len(extracted_data[current_key]) > 0:
                        current_key = None
                        continue

                clean_line = raw_line.rstrip()
                clean_line = inject_app_names(clean_line, uid_map)
                clean_line = mask_sensitive_info(clean_line)
                extracted_data[current_key].append(clean_line)

    output_lines = [
        "=== Android 電量分析精華摘要 (已自動翻譯 App 名稱並嘗試遮蔽部分敏感資訊) ===",
        f"來源檔案：{os.path.basename(full_path)} (成功載入 {len(uid_map)} 筆 App 對照表)",
        "注意：敏感資訊遮蔽僅涵蓋常見格式，分享前仍建議人工確認。\n",
    ]

    for key, title, _, should_limit in target_sections:
        lines = extracted_data[key]
        output_lines.append(f"## {title}")
        if not lines:
            output_lines.append("  (此報告中未偵測到此區塊數據)\n")
        else:
            if not should_limit or len(lines) <= max_lines:
                output_lines.extend(lines)
            else:
                output_lines.extend(lines[:max_lines])
                output_lines.append(f"  ... (已自動省略後方 {len(lines) - max_lines} 筆微量耗電項目)")
            output_lines.append("")

    out_dir = os.path.dirname(os.path.abspath(output_path))
    if out_dir and not os.path.exists(out_dir):
        os.makedirs(out_dir, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as out_f:
        out_f.write("\n".join(output_lines))

    size_kb = os.path.getsize(output_path) / 1024
    print(f"✅ [處理完成] 精簡安全版已儲存至：{output_path} ({size_kb:.1f} KB)")
    return output_path


def build_arg_parser():
    parser = argparse.ArgumentParser(description="萃取 Android batterystats 報告精華")
    parser.add_argument("-f", "--full", default="full.txt", help="full.txt 路徑（預設：full.txt）")
    parser.add_argument("-c", "--checkin", default="checkin.txt", help="checkin.txt 路徑（預設：checkin.txt）")
    parser.add_argument("-o", "--output", default="battery_for_ai.txt", help="輸出檔案路徑（預設：battery_for_ai.txt）")
    parser.add_argument("-m", "--max-lines", type=int, default=35, help="各可截斷區塊最多保留行數（預設：35）")
    return parser


def main():
    args = build_arg_parser().parse_args()
    try:
        extract_battery_report(
            full_path=args.full,
            checkin_path=args.checkin,
            output_path=args.output,
            max_lines=args.max_lines,
        )
    except (FileNotFoundError, ValueError, OSError) as exc:
        print(f"[錯誤] {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
```

---

## 三、 終端機執行方式（Termux / Linux / Mac）

### 1. 使用預設檔名（讀取當前目錄的 `full.txt`、`checkin.txt`，輸出 `battery_for_ai.txt`）

```bash
cd ~/storage/downloads/doze-test/20261119_111249
python3 ~/doze/battery_extract.py
```

### 2. 自訂輸出檔名與保留行數

```bash
python3 ~/doze/battery_extract.py \
  -f full.txt \
  -c checkin.txt \
  -o 20261119_summary.txt \
  -m 50
```

### 3. 查看所有參數說明

```bash
python3 ~/doze/battery_extract.py -h
```
---

以下是 **v2.0.0** 改寫版。預設改為安全分享模式（隱藏套件名稱並遮蔽更多格式），並修正前面提到的喚醒鎖判斷與多使用者 UID 問題。

```python
#!/usr/bin/env python3
"""
battery_extract.py v2.0.0
萃取 Android batterystats 報告的精華區段，產生可分享的精簡版。

預設為「安全分享模式」：隱藏套件名稱、遮蔽常見識別資訊。
加上 --keep-names 才會保留 App 名稱（輸出僅供自己分析，勿直接公開）。
"""
import argparse
import csv
import logging
import os
import re
import sys

VERSION = "2.0.0"
log = logging.getLogger("battery_extract")

# (section_key, 顯示標題, 比對關鍵字, 是否限制行數)
SECTIONS = [
    ("stats", "1. 整體放電概況 (Statistics since last charge)", "Statistics since last charge:", False),
    ("power_use", "2. 各硬體與 App 耗電排名 (Estimated power use)", "Estimated power use (mAh):", True),
    ("partial_wl", "3. 背景程式喚醒鎖排名 (All partial wake locks)", "All partial wake locks:", True),
    ("kernel_wl", "4. 底層硬體驅動喚醒鎖 (All kernel wake locks)", "All kernel wake locks:", True),
]
SECTION_KEYWORDS = {kw: key for key, _, kw, _ in SECTIONS}
WAKELOCK_PREFIXES = ("Wake lock", "Kernel Wake lock")
UID_RE = re.compile(r"\b(u\d+a\d+)\b")
PKG_RE = re.compile(r"\b[a-z][a-z0-9_]*(?:\.[A-Za-z0-9_]+){2,}\b")

# 遮蔽規則（順序重要：較具體的規則先執行）
MASK_RULES = [
    (re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"), "[EMAIL]"),
    (re.compile(r"\b(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}\b"), "[MAC]"),
    (re.compile(r"\b(?:[0-9A-Fa-f]{1,4}:){4,7}[0-9A-Fa-f]{1,4}\b"), "[IPV6]"),
    (re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"), "[IP]"),
    (re.compile(r"(?<!\d)(?:\+886[-\s]?|0)9\d{2}[-\s]?\d{3}[-\s]?\d{3}(?!\d)"), "[PHONE]"),
    (re.compile(r"\+\d{1,3}[-\s]?\d{6,12}\b"), "[PHONE]"),
    (re.compile(r"(?<!\d)\d{15}(?!\d)"), "[IMEI_OR_ID]"),
    (re.compile(r'(?i)(SSID\s*[:=]\s*)(?:"[^"]*"|\S+)'), r"\1[WIFI_HIDDEN]"),
    (re.compile(r"(?i)\b(serial|android_id|imei|bssid|account)(\s*[:=]\s*)\S+"), r"\1\2[HIDDEN]"),
]


def format_uid(uid_int):
    """將 Android UID 轉為 batterystats 常見格式，支援多使用者（user_id = uid // 100000）。"""
    user_id, app_id = divmod(uid_int, 100000)
    if app_id >= 10000:
        return f"u{user_id}a{app_id - 10000}"
    return str(uid_int)


def parse_uid_map(checkin_path, max_pkgs=2):
    if not os.path.isfile(checkin_path):
        log.warning("找不到 checkin 檔 %s，將不套用 App 名稱對照", checkin_path)
        return {}

    raw = {}
    with open(checkin_path, "r", encoding="utf-8", errors="replace", newline="") as f:
        for parts in csv.reader(f):
            if len(parts) < 6:
                continue
            record_type, entry_type = parts[2].strip(), parts[3].strip()
            raw_uid, pkg = parts[4].strip(), parts[5].strip()
            if record_type == "i" and entry_type == "uid" and pkg and raw_uid.isdigit():
                pkgs = raw.setdefault(format_uid(int(raw_uid)), [])
                if pkg not in pkgs:
                    pkgs.append(pkg)

    result = {}
    for uid, pkgs in raw.items():
        label = " / ".join(pkgs[:max_pkgs])
        if len(pkgs) > max_pkgs:
            label += f" (+{len(pkgs) - max_pkgs} more)"
        result[uid] = label

    log.info("載入 %d 筆 App 對照", len(result))
    return result


def mask_text(text):
    """回傳遮蔽後的文字與替換次數。"""
    total = 0
    for rx, repl in MASK_RULES:
        text, n = rx.subn(repl, text)
        total += n
    return text, total


def inject_app_names(line, uid_map):
    m = UID_RE.search(line)
    if not m:
        return line
    label = uid_map.get(m.group(1))
    if label:
        primary = label.split(" / ")[0].split(" (+")[0]
        if primary not in line:
            return f"{line}  --> [{label}]"
    return line


def clean_line(raw, uid_map, keep_names):
    """回傳 (清理後文字, 遮蔽次數)。"""
    line = raw.rstrip()
    if keep_names:
        line = inject_app_names(line, uid_map)
    else:
        line = PKG_RE.sub("[PKG]", line)
    return mask_text(line)


def extract_sections(full_path):
    data = {key: [] for key, _, _, _ in SECTIONS}
    current = None

    with open(full_path, "r", encoding="utf-8", errors="replace") as f:
        for raw in f:
            s = raw.strip()

            hit = next((key for kw, key in SECTION_KEYWORDS.items() if kw in s), None)
            if hit is not None:
                current = hit
                continue

            if current is None:
                continue

            if s == "":
                if data[current]:
                    current = None
                continue

            # 喚醒鎖區段：遇到非喚醒鎖格式的行，且已有資料時結束
            if current in ("partial_wl", "kernel_wl") and not s.startswith(WAKELOCK_PREFIXES):
                if data[current]:
                    current = None
                continue

            data[current].append(raw)

    return data


def find_leaks(text, keep_names):
    """回傳仍符合識別規則的行號，作為遮蔽後的最後檢查。"""
    hits = []
    for i, line in enumerate(text.splitlines(), 1):
        for rx, _ in MASK_RULES:
            if rx.search(line):
                hits.append(i)
                break
        else:
            if not keep_names and PKG_RE.search(line):
                hits.append(i)
    return hits


def build_report(data, uid_map, keep_names, max_lines, source_name):
    mode = "完整模式（含 App 名稱，請勿直接公開）" if keep_names else "安全分享模式（已隱藏 App 名稱並遮蔽識別資訊）"
    out = [
        "=== Android 電量分析精華摘要 ===",
        f"工具版本：battery_extract v{VERSION}",
        f"來源檔案：{source_name}",
        f"輸出模式：{mode}",
        "注意：遮蔽規則無法涵蓋所有格式，分享前仍建議人工確認。",
        "",
    ]
    total_masked = 0
    total_omitted = 0

    for key, title, _, limit in SECTIONS:
        out.append(f"## {title}")
        raw_lines = data[key]
        if not raw_lines:
            out.append("  (此報告中未偵測到此區塊數據)")
            out.append("")
            continue

        cleaned = []
        for raw in raw_lines:
            line, n = clean_line(raw, uid_map, keep_names)
            total_masked += n
            cleaned.append(line)

        if limit and len(cleaned) > max_lines:
            omitted = len(cleaned) - max_lines
            total_omitted += omitted
            cleaned = cleaned[:max_lines] + [f"  ... (已省略後方 {omitted} 筆項目)"]

        out.extend(cleaned)
        out.append("")

    out.append("## 處理統計")
    out.append(f"  遮蔽替換次數：{total_masked}")
    out.append(f"  省略行數：{total_omitted}")
    return out, total_masked, total_omitted


def run(full_path, checkin_path, output_path, max_lines, keep_names):
    if not isinstance(max_lines, int) or isinstance(max_lines, bool) or max_lines < 0:
        raise ValueError("max_lines 必須是非負整數")
    if not os.path.isfile(full_path):
        raise FileNotFoundError(f"找不到輸入檔案：{full_path}")

    uid_map = parse_uid_map(checkin_path) if keep_names else {}
    data = extract_sections(full_path)
    out_lines, masked, omitted = build_report(
        data, uid_map, keep_names, max_lines, os.path.basename(full_path)
    )
    text = "\n".join(out_lines)

    leaks = find_leaks(text, keep_names)
    if leaks:
        log.warning("最後檢查發現 %d 行可能仍含識別資訊（行號：%s），請人工確認", len(leaks), leaks[:20])

    out_abs = os.path.abspath(output_path)
    out_dir = os.path.dirname(out_abs)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(out_abs, "w", encoding="utf-8") as f:
        f.write(text)

    size_kb = os.path.getsize(out_abs) / 1024
    log.info("已儲存：%s（%.1f KB）", out_abs, size_kb)
    log.info("遮蔽替換 %d 次，省略 %d 行", masked, omitted)
    return out_abs


def build_arg_parser():
    p = argparse.ArgumentParser(description="萃取 Android batterystats 報告精華（安全分享版）")
    p.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    p.add_argument("-f", "--full", default="full.txt", help="full.txt 路徑（預設：full.txt）")
    p.add_argument("-c", "--checkin", default="checkin.txt", help="checkin.txt 路徑（預設：checkin.txt）")
    p.add_argument("-o", "--output", default="battery_for_ai.txt", help="輸出檔案路徑（預設：battery_for_ai.txt）")
    p.add_argument("-m", "--max-lines", type=int, default=35, help="各可截斷區塊最多保留行數（預設：35）")
    p.add_argument("--keep-names", action="store_true", help="保留 App 名稱（預設隱藏，僅供自行分析）")
    g = p.add_mutually_exclusive_group()
    g.add_argument("-q", "--quiet", action="store_true", help="只顯示錯誤")
    g.add_argument("-v", "--verbose", action="store_true", help="顯示除錯資訊")
    return p


def main(argv=None):
    args = build_arg_parser().parse_args(argv)
    level = logging.ERROR if args.quiet else logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=level, format="%(levelname)s: %(message)s")
    try:
        run(args.full, args.checkin, args.output, args.max_lines, args.keep_names)
    except (FileNotFoundError, ValueError, OSError) as exc:
        log.error(str(exc))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

## 主要變更

| 版本 | 變更 | 對應前次問題 |
|---|---|---|
| v2.0.0 | 預設隱藏套件名稱，需加 `--keep-names` 才保留 | 原版預設輸出 App 名稱，與「安全版」定位不符 |
| v2.0.0 | 遮蔽規則擴充：國際電話、IPv6、IMEI 格式、未加引號的 SSID、序號與帳號等欄位 | 原版僅涵蓋少數格式 |
| v2.0.0 | 輸出前再做一次最後檢查，發現可疑行會列出行號 | 原版沒有驗證機制 |
| v2.0.0 | 喚醒鎖區段同時接受 `Wake lock` 與 `Kernel Wake lock` 前綴 | 原版 kernel 區段會提早結束 |
| v2.0.0 | UID 依使用者編號計算，支援多使用者 | 原版只支援使用者 0 |
| v2.0.0 | 找不到 checkin 時明確警告，並印出輸出的絕對路徑 | 原版會誤報載入成功 |
| v2.0.0 | 加入 `--version`、`-q`、`-v`，統計區段列出遮蔽與省略數量 | 可維護性與可追蹤性 |

這版尚未用實際的 full.txt 測試。喚醒鎖的行首格式與 IPv6 規則需要對照你的實際報告確認，若誤判，可以先用 `-v` 檢查。分享前仍建議人工讀過輸出檔。
