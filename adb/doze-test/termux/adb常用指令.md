## adb常用指令

**内存(pss)占用前 25 名**
```bash
adb shell dumpsys meminfo | sed -n '/Total PSS by process:/,$p' | grep -E "^ +[0-9,]+K: .*\(pid [0-9]+\)" | head -n 25
```

**綜合去識別化指令**
1. 所有 Email 地址 → 替換為 user@example.com
2. IPv4 位址（如區域網路或連線 IP）→ 替換為 0.0.0.0
3. MAC 位址（如藍牙或 Wi-Fi 路由器硬體位址）→ 替換為 00:00:00:00:00:00
4. 自訂關鍵字 → 替換為指定的遮罩字串（若有多個關鍵字，只要多加幾行 -e 's/關鍵字/HIDDEN/g' \ 即可）。
```bash
sed -E \
  -e 's#[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}#HIDDEN_EMAIL#g' \
  -e 's#\b([0-9]{1,3}\.){3}[0-9]{1,3}\b#0.0.0.0#g' \
  -e 's#([0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}#00:00:00:00:00:00#g' \
  -e 's#你的WiFi名稱#HIDDEN_WIFI#g' \
  -e 's#你的其他關鍵字#HIDDEN_TEXT#g' \
  -e 's#你的其他關鍵字#HIDDEN_TEXT#g' \
  -e 's#你的其他關鍵字#HIDDEN_TEXT#g' \
  full.txt > full_clean.txt
```
**Statistics since last charge:**

```bash
adb shell "dumpsys batterystats | tr -d '\r' | awk '/^Statistics since last charge:/{f=1; print; next} f{ if (/^$/ || /^[^[:space:]]/) exit; print }'"
```
**Estimated power use取前 40 行明細**
```bash
adb shell 'dumpsys batterystats | tr -d "\r" | awk '\''/^Statistics since last charge:/{f=1} f && /Estimated power use/{p=1; c=0} p{print; c++; if(c>40) exit} f && /^[^[:space:]]/ && !/^Statistics since last charge:/{exit}'\'''
```

**用數字 UID 反查套件名稱（Android 把 u0a 轉成 10000 + 編號)**
```bash
adb shell 'pm list packages -U | grep -E "10182|10194|10181|101178"'
```
---
# Batterystats 分析腳本 (`battery.py` & `battery_extract.py`) 用法指南

## 1. `battery.py`（耗電與喚醒排行榜分析）
直接透過 ADB 讀取手機當下狀態，或解析已存檔的 `batterystats.txt`。

### 常用指令範例
```bash
# 預設模式：透過 ADB 讀取，顯示前 10 名耗電與喚醒項目
python battery.py

# 顯示前 20 名，並合併同名耗電與背景喚醒鎖項目（推薦排查用）
python battery.py -n 20 -m --merge-wl

# 隱藏 WindowManager 項目，並嚴格遮蔽所有信箱資訊（適合分享 log）
python battery.py --hide-wm --strict-mask

# 改從本機已匯出的 batterystats 文字檔讀取分析
python battery.py -f batterystats_20261124.txt -n 15 -m
```

### 轉向輸出到含「目前日期時間」的檔案
```bash
# 輸出到 battery_report_YYYYMMDD_HHMMSS.txt
python battery.py -n 20 -m --merge-wl > "battery_report_\$(date +%Y%m%d_%H%M%S).txt"

# 同時在終端機畫面顯示，並寫入時間戳記檔案 (使用 tee)
python battery.py -n 20 -m --merge-wl | tee "battery_report_\$(date +%Y%m%d_%H%M%S).txt"
```

---

## 2. `battery_extract.py`（擷取精華與隱私遮蔽）
用於精簡龐大的 `batterystats` 輸出並自動遮蔽個人識別資訊（PII），內建 `-o` 參數可直接指定輸出檔名。

### 常用指令範例
```bash
# 透過 ADB 讀取並直接印在畫面上（預設遮蔽隱私、保留前 25 項耗電 / 35 筆喚醒鎖）
python battery_extract.py

# 讀取本機 batterystats 檔案，且不遮蔽隱私資訊（僅供自己本地排查）
python battery_extract.py batterystats.txt --raw

# 自訂保留筆數（例如：前 30 項耗電、前 50 筆 Partial & Kernel WakeLock）
python battery_extract.py --top-power 30 --top-wl 50 --top-kernel 50
```

### 輸出到含「目前日期時間」的檔案
```bash
# 使用內建的 -o 參數直接輸出到 extract_YYYYMMDD_HHMMSS.txt
python battery_extract.py -o "extract_\$(date +%Y%m%d_%H%M%S).txt"

# 讀取本機檔並加上時間戳記匯出（保留完整前 50 筆喚醒鎖）
python battery_extract.py raw_dump.txt --top-wl 50 -o "extract_\$(date +%Y%m%d_%H%M%S).txt"
```

---

## 3. 一鍵打包完整測試流程（Ubuntu Bash）
將 `timestamp` 存成變數，確保同一次測試產出的「原始 dump」、「精華檔」與「分析報告」檔名時間完全一致：

**1. 基本版（僅時間戳記）**
```bash
TS=$(date +%Y%m%d_%H%M%S)
adb shell dumpsys batterystats > "raw_batterystats_${TS}.txt"
python battery_extract.py "raw_batterystats_${TS}.txt" -o "extract_${TS}.txt"
python battery.py -f "raw_batterystats_${TS}.txt" -n 20 -m --merge-wl > "report_${TS}.txt"
echo "已完成匯出，時間戳記：${TS}"
```
**2. 進階版（自動帶入「手機型號 + 時間戳記」）**
```bash
MODEL=$(adb shell getprop ro.product.model | tr -d '\r' | tr ' /' '_')
TS=$(date +%Y%m%d_%H%M%S)
PREFIX="${MODEL}_${TS}"

adb shell dumpsys batterystats > "${PREFIX}_raw.txt"
python battery_extract.py "${PREFIX}_raw.txt" -o "${PREFIX}_extract.txt"
python battery.py -f "${PREFIX}_raw.txt" -n 20 -m --merge-wl > "${PREFIX}_report.txt"

echo "匯出完成！產生檔案前綴：${PREFIX}"
ls -lh "${PREFIX}"*
```

**3. 存成 dump_battery.sh 腳本（一勞永逸）**
```bash
cat << 'EOF' > dump_battery.sh
#!/bin/bash

if ! adb get-state 1>/dev/null 2>&1; then
  echo "錯誤：未偵測到 ADB 裝置，請確認 USB 連線或偵錯權限。"
  exit 1
fi

MODEL=$(adb shell getprop ro.product.model | tr -d '\r' | tr ' /' '_')
TS=$(date +%Y%m%d_%H%M%S)
PREFIX="${MODEL}_${TS}"

echo "正在從 [${MODEL}] 擷取 batterystats..."
adb shell dumpsys batterystats > "${PREFIX}_raw.txt"

echo "正在產生精華檔與分析報告..."
python battery_extract.py "${PREFIX}_raw.txt" -o "${PREFIX}_extract.txt"
python battery.py -f "${PREFIX}_raw.txt" -n 20 -m --merge-wl > "${PREFIX}_report.txt"

echo "全部完成！輸出檔案："
ls -lh "${PREFIX}"*
EOF

chmod +x dump_battery.sh

```
---

# Android Doze & User 10 (壺中界) 背景喚醒排查指令集

## 1. 使用者與套件確認
```bash
# 列出裝置上所有使用者與狀態 (確認 User 10 名稱與 running 狀態)
adb shell pm list users

# 列出 User 10 底下安裝的第三方 App
adb shell pm list packages --user 10 -3
```

---

## 2. Doze (DeviceIdle) 狀態查詢與控制
```bash
# 查看目前 Light Doze 與 Deep Doze 狀態
adb shell dumpsys deviceidle | grep -E "mState=|mLightState="

# 查看 Deep Doze 進入與離開的歷史紀錄
adb shell dumpsys deviceidle | grep -A 25 "Idling history:"

# 手動逐步推進 Doze 狀態 (模擬時間經過，直到進入 deep: IDLE)
adb shell dumpsys deviceidle step

# 直接強制進入 Deep Doze
adb shell dumpsys deviceidle force-idle

# 解除強制 Doze 狀態 (測試結束後務必執行以恢復正常)
adb shell dumpsys deviceidle unforce
```

---

## 3. 電源與 WakeLock 狀態檢查
```bash
# 查看所有活躍的 WakeLock 與核心休眠阻擋器 (Suspend Blockers)
adb shell dumpsys power | grep -A 15 "Wake Locks:"

# 檢查是否有阻止 CPU 休眠的 PARTIAL_WAKE_LOCK (前 10 筆)
adb shell dumpsys power | grep -n "PARTIAL_WAKE_LOCK" | head

# 只過濾出 User 10 底下 App 持有的 PARTIAL_WAKE_LOCK
adb shell dumpsys power | grep -E "PARTIAL_WAKE_LOCK.*(uid=10[0-9]{5}|u10)"
```

---

## 4. User 10 Play 商店 JobScheduler 查詢與觸發
```bash
# 抓出 User 10 Play 商店的完整 Job 區塊 (含前後 35 行)
adb shell dumpsys jobscheduler | grep -A 35 -E "JOB #u10.*com\.android\.vending"

# 只列出 User 10 Play 商店的 Job 標題與 ID
adb shell dumpsys jobscheduler | grep -E "#u10.*com\.android\.vending"

# 強制立即執行特定 Job (將最後的數字替換為目標 Job ID)
adb shell cmd jobscheduler run -u 10 -f com.android.vending 9909
```

---

## 5. 控制變因實驗 (限制 User 10 Play 商店背景執行)
```bash
# 1. 關閉 User 10 Play 商店的背景執行豁免權
adb shell cmd appops set --user 10 com.android.vending RUN_ANY_IN_BACKGROUND ignore

# 2. 確認設定是否已生效 (預期輸出: ignore)
adb shell cmd appops get --user 10 com.android.vending RUN_ANY_IN_BACKGROUND

# 3. 清空系統電池統計數據，重新開始計時測試 (執行後請拔除 USB 線靜置)
adb shell dumpsys batterystats --reset

# 4. 實驗結束後還原預設權限
adb shell cmd appops set --user 10 com.android.vending RUN_ANY_IN_BACKGROUND allow
```

---

## 6. 進階：長持有喚醒鎖自動抓取腳本 (Ubuntu Bash)
```bash
# 每 60 秒檢查一次 uid=1010204 是否持有超過分鐘/小時等級的鎖，抓到即存檔並結束
while true; do
  adb shell dumpsys power | grep "uid=1010204" | grep -qE "ACQ=-([0-9]+h|[0-9]+m)" && {
    t=\$(date +%H%M%S)
    adb shell dumpsys power        > pw_\$t.txt
    adb shell dumpsys jobscheduler > js_\$t.txt
    adb shell dumpsys deviceidle   > idle_\$t.txt
    echo "captured \$t"; break
  }
  sleep 60
done
```

---
# Android `dumpsys batterystats` 指令與耗電分析筆記

## 1. 重置電池統計數據 (`--reset`)
* **指令：** `adb shell dumpsys batterystats --reset`
* **實際影響：** 
  * 僅清除系統內部的「耗電量歷史統計資料」，使「設定 > 電池」中的 App 耗電排行與曲線圖歸零重新計算。
  * **不會**對電池硬體造成損害、不影響電池健康度與循環次數，也無法「校正」電量顯示異常。
* **主要用途：** 進行 App 耗電測試前將數據歸零，以排除過去歷史紀錄的干擾。

---

## 2. 完整喚醒歷史紀錄 (`full-wake-history`)
* **開啟指令：** `adb shell dumpsys batterystats --enable full-wake-history`
* **關閉指令：** `adb shell dumpsys batterystats --disable full-wake-history`
* **出廠預設值：** **關閉 (Disabled)**

### 長期啟用的影響（不建議日常開啟）
* **佔用儲存空間：** 系統會鉅細靡遺地記錄每次喚醒鎖（Wakelock）與背景工作，導致日誌檔案持續膨脹。
* **增加微幅耗電與 I/O 負擔：** 頻繁寫入底層事件會消耗額外的 CPU 與電量。
* **日誌覆蓋變快：** 緩衝區容量固定，資料量暴增會導致舊紀錄更快被覆蓋，可回溯的總時間縮短。

### 查詢目前狀態與預設值
1. **檢視所有支援參數：** `adb shell dumpsys batterystats -h`
2. **反推目前開關狀態：** 執行 `adb shell dumpsys batterystats --history`
   * 若時間軸頻繁出現 `+wake_lock` / `-wake_lock` 標記，代表處於**開啟狀態**。
   * 若僅有基本螢幕開關與 `+running` 紀錄，代表處於**預設關閉狀態**。
3. **常見旗標預設值對照：**
   * `full-wake-history`：預設關閉
   * `no-auto-reset`：預設關閉
   * `pretend-screen-off`：預設關閉
   * *(註：多數裝置重新開機後，這類臨時除錯旗標也會自動恢復為關閉)*

---

## 3. 不開啟 `full-wake-history` 對分析的影響

| 分析維度 | 不開啟（預設關閉） | 開啟（完整紀錄） |
| :--- | :--- | :--- |
| **宏觀耗電數據** | **不受影響**（仍可看各 App 總耗電 mAh、總 CPU 與總喚醒時間） | 完整保留 |
| **系統狀態時間軸** | **不受影響**（仍可看螢幕開關、網路訊號、充電狀態） | 完整保留 |
| **精準時間點定位** | **無法對齊**（只知 CPU 何時醒來，不知是哪個 App 喚醒） | **可精準定位**特定時間點的喚醒兇手 |
| **短暫喚醒事件** | **容易遺漏**（系統會合併事件或只記首個來源） | 完整記錄頻繁「秒醒秒睡」的 App |

### 實務排查建議
* **初步排查與日常使用：** 維持**關閉**，直接匯出預設的 `bugreport` 檢視各 App 累計耗電與總喚醒時間即可。
* **抓出待機掉電兇手：** 測試前執行 `--enable full-wake-history` 並搭配 `--reset` 歸零，靜置待機數小時後匯出日誌，分析完畢後立刻執行 `--disable` 關閉。
