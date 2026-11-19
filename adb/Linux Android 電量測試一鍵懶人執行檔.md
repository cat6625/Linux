# Mac / Linux Android 電量測試一鍵懶人執行檔（`battery_test.sh`）

這個 Shell 腳本整合了**「重置電量統計」**、**「無聲匯出報告」**與**「自動過濾 4 大核心區塊」**功能，無需手動輸入一長串 ADB 指令或另外執行 Python 程式。

---

## 一、 完整 Shell 腳本原始碼（`battery_test.sh`）

將以下程式碼儲存為 `battery_test.sh`：

```bash
#!/bin/bash

# ==============================================================================
# Android 電量分析一鍵懶人執行腳本 (適用於 macOS / Linux)
# 功能：
#   模式 1 (--reset)  : 清空 batterystats 並開啟完整喚醒歷史，準備開始測試
#   模式 2 (--export) : 匯出報告並自動過濾出適合餵給 AI 的精華摘要 (battery_for_ai.txt)
# ==============================================================================

RAW_FILE="battery_summary.txt"
AI_FILE="battery_for_ai.txt"
MAX_LINES=35

# 檢查 ADB 是否已安裝
if ! command -v adb &> /dev/null; then
    echo "[錯誤] 系統找不到 adb 指令，請先安裝 Android Platform Tools。"
    exit 1
fi

# 檢查是否有連接中的裝置
DEVICE_COUNT=\$(adb devices | grep -w "device" | wc -l)
if [ "\$DEVICE_COUNT" -eq 0 ]; then
    echo "[錯誤] 未偵測到已連線的 Android 裝置。"
    echo "請確認已開啟 USB 偵錯，或先執行：adb connect <手機IP>:<埠號>"
    exit 1
fi

show_menu() {
    echo "=========================================="
    echo "   Android 電量分析自動化工具 (Mac/Linux)"
    echo "=========================================="
    echo "1) [測試開始前] 重置電量統計並開啟完整喚醒紀錄"
    echo "2) [測試結束後] 無聲匯出報告並自動過濾給 AI"
    echo "3) 退出"
    echo "------------------------------------------"
    read -p "請輸入選項 [1-3]: " choice

    case \$choice in
        1) run_reset ;;
        2) run_export ;;
        3) exit 0 ;;
        *) echo "[錯誤] 無效的選項，請重新執行。"; exit 1 ;;
    esac
}

run_reset() {
    echo ""
    echo "[執行中] 正在重置 batterystats 歷史紀錄..."
    adb shell dumpsys batterystats --reset
    adb shell dumpsys batterystats --enable full-wake-history
    echo ""
    echo "✅ [完成] 電量統計已歸零！"
    echo "👉 請立即鎖定手機螢幕（若為有線連接請拔除 USB 線），開始進行純待機或標準測試。"
}

run_export() {
    echo ""
    echo "[執行中] 正在從手機無聲匯出電量報告（請勿喚醒手機螢幕）..."
    adb shell dumpsys batterystats > "\$RAW_FILE"

    if [ ! -s "\$RAW_FILE" ]; then
        echo "[錯誤] 匯出失敗，檔案為空。"
        exit 1
    fi

    echo "[執行中] 正在過濾 4 大核心統計區塊（每個清單保留前 \$MAX_LINES 名）..."

    # 使用 Python 3 進行精準區塊擷取（macOS 與多數 Linux 皆內建 python3）
    python3 - <<EOF
import os, re

input_path = "\$RAW_FILE"
output_path = "\$AI_FILE"
max_lines = \$MAX_LINES

target_sections = [
    ("1. 整體放電概況 (Statistics since last charge)", [r"^Statistics since last charge:"]),
    ("2. 各硬體與 App 耗電排名 (Estimated power use)", [r"^Estimated power use mAh:"]),
    ("3. 背景程式喚醒鎖排名 (All partial wake locks)", [r"^All partial wake locks:"]),
    ("4. 底層硬體驅動喚醒鎖 (All kernel wake locks)", [r"^All kernel wake locks:"]),
]

extracted_data = {title: [] for title, _ in target_sections}
current_section = None

with open(input_path, "r", encoding="utf-8", errors="replace") as f:
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
                extracted_data[current_section].append(raw_line.rstrip())

output_lines = [
    "=== Android 電量分析精華摘要 (已自動過濾冗長歷史紀錄) ===",
    f"來源檔案：{os.path.basename(input_path)}\n"
]

for title, _ in target_sections:
    lines = extracted_data[title]
    output_lines.append(f"## {title}")
    if not lines:
        output_lines.append("  (此報告中未偵測到此區塊數據)\n")
    else:
        if "1." in title or len(lines) <= max_lines:
            output_lines.extend(lines)
        else:
            output_lines.extend(lines[:max_lines])
            output_lines.append(f"  ... (已自動省略後方 {len(lines) - max_lines} 筆微量耗電項目)")
        output_lines.append("")

with open(output_path, "w", encoding="utf-8") as out_f:
    out_f.write("\n".join(output_lines))
EOF

    ORIG_KB=(du -k "RAW_FILE" | cut -f1)
    NEW_KB=(du -k "AI_FILE" | cut -f1)

    echo ""
    echo "✅ [全部完成] 報告已自動瘦身並輸出！"
    echo "📊 檔案大小變化：\({ORIG_KB} KB  --->  \){NEW_KB} KB"
    echo "📄 AI 專用檔案：(pwd)/AI_FILE"
    
    # 若在 macOS 環境，自動將結果複製到系統剪貼簿
    if command -v pbcopy &> /dev/null; then
        cat "\$AI_FILE" | pbcopy
        echo "📋 [macOS 專屬貼心功能] 已自動將精簡報告內容複製到你的剪貼簿，直接前往 AI 網頁按 Command+V 貼上即可！"
    fi
}

# 支援直接帶參數執行，或顯示互動式選單
if [ "\$1" == "--reset" ]; then
    run_reset
elif [ "\$1" == "--export" ]; then
    run_export
else
    show_menu
fi
```

---

## 二、 首次設定與使用步驟

### 1. 賦予腳本執行權限（僅需執行一次）
打開 Mac 的「終端機（Terminal）」或 Linux Terminal，切換到存放 `battery_test.sh` 的資料夾並執行：
```bash
chmod +x battery_test.sh
```

### 2. 日常使用方式（兩種方式皆可）

* **方式 A：互動式選單（最直覺）**
  直接執行腳本，按照畫面提示輸入 `1` 或 `2`：
  ```bash
  ./battery_test.sh
  ```

* **方式 B：帶參數一鍵直達（最快速）**
  * **睡前 / 測試開始前執行：**
    ```bash
    ./battery_test.sh --reset
    ```
  * **起床 / 測試結束後執行：**
    ```bash
    ./battery_test.sh --export
    ```
    *(註：如果你使用的是 **macOS**，執行 `--export` 後腳本會透過內建的 `pbcopy` 自動把過濾後的報告存入剪貼簿，你連打開檔案複製都不用，直接切換到 Claude 或 ChatGPT 視窗按 `Command + V` 就能送出分析！)*
