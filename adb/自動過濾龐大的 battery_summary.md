# Android 電量報告雙檔自動過濾與隱私去識別化指南

本指南提供全面升級的 `battery_extract.py` 腳本，支援直接讀取同資料夾下的 `full.txt` 與 `checkin.txt`，自動將抽象的 UID 翻譯成真實 App 名稱，並同步遮蔽個人敏感資訊。

---

## 一、 升級版腳本 3 大核心功能

1. **雙檔聯動自動翻譯 App（`full.txt` + `checkin.txt`）**
   * 自動解析 `checkin.txt` 內建的 `uid` 紀錄行，並在 `full.txt` 的耗電與喚醒鎖清單後方自動標註真實 App 套件名稱（例如 `Uid u0a1178 ... --> [com.instagram.android]`），無需再連接手機查詢。
2. **智慧型隱私去識別化（保留網域判斷能力）**
   * **Email 智慧遮罩**：將 `user@yahoo.com.tw` 替換為 `[EMAIL_HIDDEN@yahoo.com.tw]`。完整隱藏個人帳號名稱，同時保留信箱服務商網域，讓 AI 依然能精準判斷是否為傳統 IMAP/POP3 輪詢耗電。
   * **網路與身分資訊遮蔽**：自動過濾 IPv4 位址、MAC 位址、台灣手機號碼（`09xx`）與 Wi-Fi SSID 名稱。
3. **防爆額度截斷設計**
   * 耗電與喚醒鎖清單預設僅保留耗電量最高的 **前 35 名**，自動省略後方微量耗電項目，將報告體積壓縮至 15 KB 以內。

---

## 二、 完整 Python 腳本原始碼（`battery_extract.py`）

將以下程式碼儲存為 `battery_extract.py`，並與 `full.txt`、`checkin.txt` 放在同一個資料夾中（僅使用 Python 內建標準函式庫，無需安裝額外套件）：

    import os
    import re
    import sys
    from typing import Dict


    def parse_uid_map_from_checkin(checkin_path: str) -> Dict[str, str]:
        """
        從 checkin.txt 自動解析 UID 與真實 App 套件名稱的對照表。
        checkin 格式範例: 9,0,i,uid,10198,com.google.android.gm
        """
        uid_map: Dict[str, str] = {}
        if not os.path.exists(checkin_path):
            return uid_map

        with open(checkin_path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                parts = line.strip().split(",")
                if len(parts) >= 6 and parts[2] == "i" and parts[3] == "uid":
                    raw_uid = parts[4]
                    pkg_name = parts[5]
                    if raw_uid.isdigit():
                        uid_int = int(raw_uid)
                        if uid_int >= 10000:
                            formatted_uid = f"u0a{uid_int - 10000}"
                        else:
                            formatted_uid = str(uid_int)

                        if formatted_uid in uid_map:
                            if pkg_name not in uid_map[formatted_uid]:
                                existing = uid_map[formatted_uid].split(" / ")
                                if len(existing) < 2:
                                    uid_map[formatted_uid] += f" / {pkg_name}"
                        else:
                            uid_map[formatted_uid] = pkg_name
        return uid_map


    def mask_sensitive_info(text: str) -> str:
        """
        自動偵測並遮蔽敏感個人資訊（Email、IPv4、MAC 位址、手機號碼、Wi-Fi SSID）。
        """
        # 1. 遮蔽 Email 地址（保留網域類型供判斷）
        text = re.sub(
            r"\b[A-Za-z0-9._%+-]+@([A-Za-z0-9.-]+\.[A-Za-z]{2,})\b",
            r"[EMAIL_HIDDEN@\1]",
            text,
        )
        # 2. 遮蔽 IPv4 位址
        text = re.sub(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", "[IP_HIDDEN]", text)
        # 3. 遮蔽 MAC 位址
        text = re.sub(r"\b(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}\b", "[MAC_HIDDEN]", text)
        # 4. 遮蔽台灣手機號碼
        text = re.sub(r"\b09\d{2}-?\d{3}-?\d{3}\b", "[PHONE_HIDDEN]", text)
        # 5. 遮蔽 Wi-Fi SSID 名稱
        text = re.sub(
            r'(SSID\s*[:=]\s*)"[^"]+"',
            r'\1"[WIFI_SSID_HIDDEN]"',
            text,
            flags=re.IGNORECASE,
        )
        return text


    def inject_app_names(line: str, uid_map: Dict[str, str]) -> str:
        """
        在包含 u0aXXX 的行中，自動附加真實 App 套件名稱。
        """
        if not uid_map:
            return line

        match = re.search(r"\b(u0a\d+)\b", line)
        if match:
            uid_str = match.group(1)
            if uid_str in uid_map:
                app_name = uid_map[uid_str]
                if app_name.split(" / ")[0] not in line:
                    return f"{line}  --> [{app_name}]"
        return line


    def extract_battery_report(
        full_path: str = "full.txt",
        checkin_path: str = "checkin.txt",
        output_path: str = "battery_for_ai.txt",
        max_lines_per_section: int = 35,
    ) -> None:
        if not os.path.exists(full_path):
            print(f"[錯誤] 找不到主要報告檔案：{full_path}")
            sys.exit(1)

        uid_map = parse_uid_map_from_checkin(checkin_path)
        if uid_map:
            print(f"[資訊] 成功從 {checkin_path} 載入 {len(uid_map)} 筆 App 名稱對照表！")
        else:
            print(f"[提示] 未找到 {checkin_path} 或無 UID 資料，將保留原始 UID 編號。")

        target_sections = [
            ("1. 整體放電概況 (Statistics since last charge)", [r"^Statistics since last charge:"]),
            ("2. 各硬體與 App 耗電排名 (Estimated power use)", [r"^Estimated power use \(mAh\):"]),
            ("3. 背景程式喚醒鎖排名 (All partial wake locks)", [r"^All partial wake locks:"]),
            ("4. 底層硬體驅動喚醒鎖 (All kernel wake locks)", [r"^All kernel wake locks:"]),
        ]

        extracted_data = {title: [] for title, _ in target_sections}
        current_section = None

        with open(full_path, "r", encoding="utf-8", errors="replace") as f:
            for raw_line in f:
                line_stripped = raw_line.strip()

                matched_new = False
                for title, patterns in target_sections:
                    if any(re.match(p, line_stripped) for p in patterns):
                        current_section = title
                        matched_new = True
                        break

                if matched_new:
                    continue

                if current_section is not None:
                    if line_stripped == "" and len(extracted_data[current_section]) > 0:
                        current_section = None
                        continue

                    if raw_line and not raw_line.isspace() and line_stripped != "":
                        current_section = None
                        continue

                    if line_stripped != "":
                        clean_line = raw_line.rstrip()
                        clean_line = inject_app_names(clean_line, uid_map)
                        clean_line = mask_sensitive_info(clean_line)
                        extracted_data[current_section].append(clean_line)

        output_lines = [
            "=== Android 電量分析精華摘要 (已自動翻譯 App 名稱並遮蔽敏感個資) ===",
            f"來源檔案：{os.path.basename(full_path)} (搭配 {os.path.basename(checkin_path) if uid_map else '無對照表'})\n",
        ]

        for title, _ in target_sections:
            lines = extracted_data[title]
            output_lines.append(f"## {title}")
            if not lines:
                output_lines.append("  (此報告中未偵測到此區塊數據)\n")
            else:
                if "1." in title or len(lines) <= max_lines_per_section:
                    output_lines.extend(lines)
                else:
                    output_lines.extend(lines[:max_lines_per_section])
                    omitted = len(lines) - max_lines_per_section
                    output_lines.append(f"  ... (已自動省略後方 {omitted} 筆微量耗電項目以節省 AI 額度)")
                output_lines.append("")

        with open(output_path, "w", encoding="utf-8") as out_f:
            out_f.write("\n".join(output_lines))

        orig_kb = os.path.getsize(full_path) / 1024
        new_kb = os.path.getsize(output_path) / 1024
        print(f"✅ [處理完成] 原始大小：{orig_kb:.1f} KB ---> 精簡安全版：{new_kb:.1f} KB")
        print(f"📄 輸出檔案：{output_path}")


    if __name__ == "__main__":
        full_file = sys.argv[1] if len(sys.argv) > 1 else "full.txt"
        checkin_file = sys.argv[2] if len(sys.argv) > 2 else "checkin.txt"
        extract_battery_report(full_file, checkin_file)

---

## 三、 終端機執行方式

在 Mac / Linux 終端機切換到存放檔案的資料夾後，輸入以下指令即可產出 `battery_for_ai.txt`：

    python3 battery_extract.py
