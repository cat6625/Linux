這個 Python 腳本能自動過濾龐大的 battery_summary.txt（或解壓縮後的 bugreport.txt），精準擷取餵給 AI 所需的 4 大核心統計區塊，並自動限制過長清單的列數（避免成千上萬個微小的系統服務耗盡你的 AI 額度）。
本腳本僅使用 Python 內建標準函式庫，無需安裝任何額外套件即可直接執行。

一、 完整 Python 過濾腳本（extract_battery.py）

你可以點擊下方程式碼區塊右上角的 「複製（Copy）」 圖示，將程式碼存成 extract_battery.py：
```py
import sys
import os
import re

def extract_battery_summary(
    input_path: str = "battery_summary.txt",
    output_path: str = "battery_for_ai.txt",
    max_lines_per_section: int = 35
) -> None:
    """
    從 dumpsys batterystats 或 bugreport 輸出檔中，
    自動擷取核心電量統計區塊並輸出為適合餵給 AI 的精簡純文字檔。
    """
    if not os.path.exists(input_path):
        print(f"[錯誤] 找不到輸入檔案：{input_path}")
        print("請確認檔案路徑，或先執行：adb shell dumpsys batterystats > battery_summary.txt")
        sys.exit(1)

    # 定義要擷取的 4 個核心區塊起始關鍵字（支援不同 Android 版本的微幅命名差異）
    target_sections = [
        ("1. 整體放電概況 (Statistics since last charge)", [r"^Statistics since last charge:"]),
        ("2. 各硬體與 App 耗電排名 (Estimated power use)", [r"^Estimated power use \(mAh\):"]),
        ("3. 背景程式喚醒鎖排名 (All partial wake locks)", [r"^All partial wake locks:"]),
        ("4. 底層硬體驅動喚醒鎖 (All kernel wake locks)", [r"^All kernel wake locks:"]),
    ]

    extracted_data = {title: [] for title, _ in target_sections}
    current_section = None

    # 使用 errors='replace' 避免不同系統編碼或特殊字元導致讀取崩潰
    with open(input_path, "r", encoding="utf-8", errors="replace") as f:
        for raw_line in f:
            line_stripped = raw_line.strip()

            # 檢查是否進入新的目標區塊
            matched_new_section = False
            for title, patterns in target_sections:
                if any(re.match(p, line_stripped) for p in patterns):
                    current_section = title
                    matched_new_section = True
                    break

            if matched_new_section:
                continue

            # 若目前正在目標區塊內，判斷是否遇到下一個大標題（空行後接非縮排文字，或特定分隔線）
            if current_section is not None:
                # 遇到空行且該區塊已有資料，代表該段落結束
                if line_stripped == "" and len(extracted_data[current_section]) > 0:
                    current_section = None
                    continue

                # 遇到其他未縮排的系統大標題（例如 "Per-PID Stats:" 或 "u0a123:"）則停止擷取
                if raw_line and not raw_line[0].isspace() and line_stripped != "":
                    current_section = None
                    continue

                if line_stripped != "":
                    extracted_data[current_section].append(raw_line.rstrip())

    # 組合最終輸出內容，並針對過長列表進行前 N 名截斷
    output_lines = [
        "=== Android 電量分析精華摘要 (已自動過濾冗長歷史紀錄) ===",
        f"來源檔案：{os.path.basename(input_path)}\n"
    ]

    found_any = False
    for title, _ in target_sections:
        lines = extracted_data[title]
        output_lines.append(f"## {title}")
        if not lines:
            output_lines.append("  (此報告中未偵測到此區塊數據)\n")
        else:
            found_any = True
            # 整體放電概況通常不長，完整保留；其餘排名清單只取前 max_lines_per_section 筆（最耗電的前幾名）
            if "1." in title or len(lines) <= max_lines_per_section:
                output_lines.extend(lines)
            else:
                output_lines.extend(lines[:max_lines_per_section])
                omitted_count = len(lines) - max_lines_per_section
                output_lines.append(f"  ... (已自動省略後方 {omitted_count} 筆微量耗電項目以節省 AI 額度)")
            output_lines.append("")

    if not found_any:
        print("[警告] 未在檔案中找到標準的 batterystats 統計標題。")
        print("請確認匯出時沒有加上 --checkin 參數（本腳本適用於人類可讀格式）。")
        sys.exit(1)

    with open(output_path, "w", encoding="utf-8") as out_f:
        out_f.write("\n".join(output_lines))

    orig_kb = os.path.getsize(input_path) / 1024
    new_kb = os.path.getsize(output_path) / 1024
    print(f"[成功] 檔案過濾完成！")
    print(f"原始大小：{orig_kb:.1f} KB  --->  精簡後大小：{new_kb:.1f} KB")
    print(f"輸出檔案：{output_path}（可直接複製全部內容貼給 AI 分析）")

if __name__ == "__main__":
    # 支援命令列傳入自訂檔名，例如：python extract_battery.py bugreport-xxx.txt
    input_file = sys.argv[1] if len(sys.argv) > 1 else "battery_summary.txt"
    output_file = sys.argv[2] if len(sys.argv) > 2 else "battery_for_ai.txt"
    extract_battery_summary(input_file, output_file)
```

二、 使用方式與特色說明

1. 基本執行（預設讀取同資料夾下的 battery_summary.txt）
```bash
python extract_battery.py
```
執行後會在同目錄產生 battery_for_ai.txt（通常不到 10 KB），直接全選複製貼給 AI 即可。
3. 直接處理從 bugreport.zip 解壓出來的大型 .txt 檔
```bash
python extract_battery.py bugreport-pixel-2026-11-19.txt
```
(腳本同樣能從數十 MB 的完整系統除錯報告中，精準把這 4 個電池統計區塊挖出來。)
4. 內建防爆額度設計（Top 35 截斷）：
	• batterystats 裡的耗電排名與喚醒鎖清單是依照耗電量由高到低排序的。腳本預設只保留前 35 名（max_lines_per_section=35），自動過濾掉排在後面只消耗 0.001 mAh 的數百個系統背景服務，讓 AI 專注在真正的耗電元兇上。
