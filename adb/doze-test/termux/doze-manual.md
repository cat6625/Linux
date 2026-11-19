# Termux Android Doze & ADB 自動化測試工具組

本專案提供一套運行於 **Termux（無需 Root）** 的 Android 待機耗電與 Doze 自動化測試工具。

透過 Android 本機無線除錯（Wireless Debugging），自動偵測 ADB 連接埠、建立連線、收集系統 `batterystats`、`deviceidle`、`meminfo`、`battery` 等資料，並透過 Python 分析程式產生易於判讀的待機耗電與深度睡眠摘要報告。

本工具的設計原則：

- 不需要 Root 權限。
- 優先使用已連線的 ADB 端點，必要時才使用 nmap 掃描。
- 自動掃描僅針對本機 `127.0.0.1`。
- 預設保留 Android 原有 BatteryStats 統計，不主動重置。
- 所有 ADB 裝置操作明確指定目標端點。
- 不強制進入 Deep Doze，不修改 Android 原有 Doze 系統設定。
- 保留原始資料，避免只依賴 Python 摘要判斷。
- Android 或廠牌輸出格式不支援時，顯示警告，不將未知資料當成 0。

---

## 目錄結構

本專案包含三個核心程式檔（`adb.sh`、`doze.sh`、`doze_summary-termux.py`）與說明文件。建議將可執行腳本存放於 Termux 內部私有目錄 `~/doze/`，利用 Android 應用程式沙盒保護；測試資料則存放於外部共享儲存空間。

```text
~/doze/
├── doze.sh
│   └── 主測試流程、ADB 偵測、測試前後快照及資料擷取
│
├── doze_summary-termux.py
│   └── BatteryStats、Doze、Alarm、Job、Wakelock、
│       CPU、電池及記憶體分析
│
└── adb.sh
    └── 獨立 ADB 無線除錯自動偵測及連線工具

~/storage/downloads/doze-test/
└── YYYYMMDD_HHMMSS/
    ├── timeline.txt
    ├── alarm_start_full.txt
    ├── battery_start.txt
    ├── battery_end.txt
    ├── mem_start.txt
    ├── mem_end.txt
    ├── deviceidle.txt
    ├── full.txt
    ├── checkin.txt
    ├── history.txt
    ├── home_end.txt
    └── summary-YYYYMMDD_HHMMSS.txt
```

若啟用 BatteryStats 重置功能，測試資料夾還會額外保存重置前的統計備份：

```text
batterystats_before_reset_full.txt
batterystats_before_reset_checkin.txt
batterystats_before_reset_history.txt
```

---

## 一、環境安裝與初始化

打開 Termux，依序執行以下指令。

### 1. 安裝必要套件

```bash
pkg update && pkg upgrade -y
pkg install -y android-tools python nmap coreutils
```

套件用途：

| 套件 | 用途 |
|---|---|
| `android-tools` | 提供 ADB 指令 |
| `python` | 執行 Python 摘要分析 |
| `nmap` | 掃描本機動態無線除錯 Port |
| `coreutils` | 提供 `timeout` 等常用工具 |

確認安裝：

```bash
adb version
python3 --version
nmap --version
timeout --version
```

Python 版本建議使用 3.8 或更新版本。

### 2. 授權外部儲存空間與建立腳本目錄

```bash
termux-setup-storage
mkdir -p ~/doze
```

執行 `termux-setup-storage` 後，依 Android 系統提示授予 Termux 儲存空間權限。

確認下載資料夾存在：

```bash
ls -ld ~/storage/downloads
```

### 3. 放入腳本及設定權限

將專案中的三支程式檔案放入 `~/doze/` 目錄中：

```text
~/doze/doze.sh
~/doze/doze_summary-termux.py
~/doze/adb.sh
```

設定執行權限：

```bash
chmod 700 ~/doze/doze.sh
chmod 700 ~/doze/adb.sh
chmod 600 ~/doze/doze_summary-termux.py
```

### 4. 建立全域快捷指令

```bash
ln -sf ~/doze/doze.sh "$PREFIX/bin/doze"
ln -sf ~/doze/adb.sh "$PREFIX/bin/adb-auto"
```

之後在 Termux 任何路徑下都可以直接執行：

```bash
doze

or

doze --reset-batterystats
```

或單獨測試 ADB 連線：

```bash
adb-auto
```

> **重要：** 請勿將 `adb.sh` 軟連結命名為 `adb`，否則會覆蓋 `android-tools` 原生 ADB 指令，造成無窮遞迴呼叫錯誤。

---

## 二、疑難排解：ADB 指令被軟連結覆蓋

若曾誤執行 `ln -sf ~/doze/adb.sh "$PREFIX/bin/adb"` 導致原生 ADB 無法運作，請依下列步驟復原：

1. 移除錯誤軟連結：
   ```bash
   rm -f "$PREFIX/bin/adb"
   ```
2. 重新安裝 Android-tools：
   ```bash
   pkg reinstall -y android-tools
   ```
3. 驗證原生指令恢復正常：
   ```bash
   adb version
   ```
4. 重新建立正確快捷指令：
   ```bash
   ln -sf ~/doze/adb.sh "$PREFIX/bin/adb-auto"
   ```

---

## 三、透過 NMM File Manager 編輯內部目錄（選用）

若習慣在手機上使用圖形介面編輯 `~/doze/` 內的腳本，可透過 Android SAF 機制掛載：

1. 開啟 NMM File Manager。
2. 左上角選單 → 新增儲存空間／系統檔案選擇器（SAF）。
3. 在系統檔案選擇器左上角選單中，尋找 Termux。
4. 選擇 `doze` 資料夾。
5. 點擊「使用此資料夾」並允許存取。

編輯存檔時請注意：
- **編碼**：UTF-8。
- **換行**：LF（請勿使用 Windows CRLF，否則 Bash 腳本會執行失敗）。
- Shell 腳本第一行的 shebang（`#!/data/data/com.termux/files/usr/bin/bash`）必須保留。

---

## 四、日常測試執行流程

### 1. 初次配對

每台裝置通常只需要完成一次配對，除非重新配對或清除無線除錯配對資料。

1. 進入手機「設定 → 開發人員選項 → 無線除錯」。
2. 開啟無線除錯。
3. 點擊「使用配對碼配對裝置」。
4. 記下畫面顯示的配對 IP、配對 Port 及六位數配對碼。
5. 在 Termux 執行：
   ```bash
   adb pair 127.0.0.1:<配對Port>
   ```
6. 依提示輸入六位數配對碼。

> **提示：** 配對 Port 與日常連線 Port 是兩個不同的 Port。配對完成後，日常連線應使用無線除錯主畫面顯示的 Port，而不是配對畫面顯示的 Port。

### 2. 執行 Doze 待機測試

確認測試前狀態：
- 手機已拔除充電線。
- 無線除錯已開啟。
- Termux 已授權共享儲存空間。
- 手機電量足夠，且測試期間不會主動操作手機。

執行測試：

```bash
doze
```

若要手動指定連線 Port（例如 `39815`）：

```bash
doze 39815
```

**自動執行流程說明**：
1. 檢查目前已連線的本機 ADB 端點；若無，則使用 `nmap` 掃描 `30000–65535` 並驗證連線（若仍找不到則要求手動輸入 Port）。
2. 擷取測試前鬧鐘（`alarm_start_full.txt`）、電池及指定套件記憶體快照。
3. 啟用完整 wake history（若系統支援），且預設不重置既有 BatteryStats。
4. 送出 `KEYCODE_SLEEP` 關閉螢幕，進入手動等待狀態。
5. 使用者結束測試並按下 Enter 後，重新連線並擷取 `deviceidle`、`batterystats` 等完整數據。
6. 自動呼叫 Python 分析腳本產生摘要報告。

### 3. 測試時間建議

- 建議至少測試 **30 分鐘**；若要觀察完整的 Deep Doze 進入與維持行為，建議延長至 **1–3 小時或更久**。
- 實際是否進入 Deep Idle，仍受 Android 版本、廠牌省電政策、鬧鐘、動態感應（Motion）、網路及系統排程影響。
- `KEYCODE_SLEEP` 只會送出關閉螢幕指令，本工具**不會**執行 `dumpsys deviceidle force-idle`，也不會主動修改 Android Doze 設定，以免破壞自然待機測試條件。

### 4. 結束測試

1. 喚醒手機螢幕。
2. 回到 Termux 畫面，按下 `Enter`。
3. 等待 ADB 重新連線及資料擷取完成，畫面將直接印出分析摘要。
4. 完整原始資料與摘要報告存放於：`Download/doze-test/<日期_時間>/`。

### 5. 單獨測試 ADB 自動連線

```bash
adb-auto
# 或手動指定 Port
adb-auto 39815
```

---

## 五、BatteryStats 重置政策

### 預設不重置

新版 `doze.sh` 預設**不執行** `dumpsys batterystats --reset`，以保留 Android 系統原有的累積統計，避免意外清除既有資料。

### 需要重置時

只有在明確需要乾淨的統計起點時才加上參數執行：

```bash
doze --reset-batterystats
# 或同時指定 Port
doze 39815 --reset-batterystats
```

執行時會先備份重置前的 `full`、`checkin` 及 `history` 輸出，並要求手動輸入大寫 `RESET` 確認後才會執行重置。

---

## 六、核心腳本功能架構說明

*(註：實際程式碼請直接參閱專案目錄中的對應檔案，本文件不內嵌完整原始碼以利手機閱讀)*

### 1. `adb.sh`（獨立 ADB 無線除錯自動連線工具）
- 優先沿用已連線的 `127.0.0.1` ADB 端點；無連線時使用 `nmap` 掃描本機高埠（含逾時保護）。
- 摒棄不可靠的 `5555` 預設值，支援手動輸入 Port 並檢查 `1–65535` 範圍有效性。
- 所有操作皆透過 `adb -s` 明確綁定目標裝置，並將連線過程寫入 `~/adb_auto_connect.log`。

### 2. `doze.sh`（Doze 自動化測試主程式）
- 整合 ADB 端點偵測與斷線自動重連機制（`RECONNECT_TRIES`）。
- 測試前自動檢查下一個 `wake-from-idle` 鬧鐘並提醒使用者。
- 負責執行測試前後的 `battery`、`meminfo` 快照，以及測試後的 `deviceidle`、`batterystats`（full / checkin / history）擷取。
- 擷取失敗時記錄錯誤碼但不中斷整體流程，確保已取得的資料完整留存。

### 3. `doze_summary-termux.py`（BatteryStats 與 Doze 摘要分析）
- 僅使用 Python 標準函式庫，無需額外安裝 `pip` 套件。
- 解析並計算 CPU 清醒/休眠比例、亮屏時間點與持續時間、Doze 狀態（Light / Deep Idle）轉換時間軸。
- 統計喚醒來源：Alarm、Job、Wakeup AP、Kernel Wakelock 與 Wakeup Reason。
- 繪製 Charge Counter 放電曲線、標記疑似突發耗電區段，並列出 UID 耗電排行與指定套件（`--pkg`）明細。
- 解析 `dumpsys meminfo` 記憶體指標（PSS、Private Dirty/Clean、RSS、Swap PSS）與電池快照容量估算。

---

## 七、版本演進與原版差異

| 項目 | 舊版 | 現行整合修正版 |
|---|---|---|
| ADB Port | 預設 41077／5555 | 優先既有連線，必要時掃描，失敗要求手動輸入 |
| nmap 掃描 | 全高埠無限制掃描 | 保留高埠掃描，加入逾時保護 |
| ADB 裝置選擇 | 部分指令未指定目標 | 全面使用 `adb -s "$ADB_ADDR"` 明確指定 |
| Port 驗證 | 未完整驗證 | 嚴格限制 1–65535 整數 |
| BatteryStats | 每次強制重置 | 預設不重置，保留原有統計 |
| 重置前備份 | 無 | 重置前自動保存 full、checkin、history |
| 重置確認 | 無 | 必須手動輸入 `RESET` 確認 |
| 輸出資料夾 | 精確到分鐘 | 精確到秒，避免同分鐘測試覆蓋 |
| Termux 儲存空間 | 未檢查 | 啟動時自動檢查 `~/storage/downloads` |
| 錯誤處理 | 遇錯可能直接中斷 | 擷取失敗留下錯誤紀錄並繼續保留其餘資料 |
| Python 路徑 | 寫死 `${HOME}/doze` | 動態依 `doze.sh` 所在目錄定位 |
| meminfo 解析 | 固定欄位順序假設 | 依表頭動態對應，格式不符時顯示警告 |
| CPU running | 可能漏算起訖區間 | 對無法確認的邊界區間顯示警告 |
| Doze 狀態判斷 | 易將單一事件當整段狀態 | 明確列出狀態轉換時間軸與可確認持續區間 |
| 突發耗電 | 直接列出門檻 | 標示為時間關聯的疑似事件，不直接武斷歸因 |

---

## 八、相容性與重要注意事項

1. **Android 版本及廠牌差異**：不同 OEM 系統修改可能影響 History 時間格式、Alarm 輸出或 `meminfo` 表格欄位。若 Python 顯示解析警告，請保留原始檔案供人工核對，切勿將未知值視為 0。
2. **Charge Counter 單位**：程式預設將 Android 常見的 μAh 數值除以 1000 換算為 mAh。若電池在測試期間發生計數器波動或回升，程式會略過該區段放電速率計算。
3. **full-wake-history**：測試時啟用 `--enable full-wake-history` 會增加系統日誌記錄量；不同 Android 版本支援度不同，若不支援會自動顯示警告並繼續測試。
4. **無線除錯 Port 變動**：每次重新開啟無線除錯或重開機，連線 Port 皆可能改變，交由腳本自動掃描或手動查看主畫面 Port 輸入即可。

---

## 九、第一次使用的驗證清單

建議先進行 5–10 分鐘的短時間測試，確認環境運作正常後再進行長時間待機測試：

### ADB 連線驗證
- [ ] `adb version` 正常輸出版本資訊。
- [ ] `adb-auto` 能自動偵測已連線端點，或在失敗時提示輸入 Port。
- [ ] `adb devices` 顯示目標端點狀態為 `device`。

### Doze 測試流程驗證
- [ ] `doze` 能建立獨立的 `YYYYMMDD_HHMMSS` 測試資料夾。
- [ ] 測試前成功產生 `alarm_start_full.txt`、`battery_start.txt`、`mem_start.txt`。
- [ ] 預設情況下未執行 BatteryStats reset。
- [ ] 手動按 Enter 結束後能順利重連並擷取 `deviceidle.txt`、`full.txt`、`checkin.txt`、`history.txt`。

### Python 摘要驗證
- [ ] Python 腳本正常啟動且無未處理的程式例外。
- [ ] 成功產生 `summary-YYYYMMDD_HHMMSS.txt` 報告。
- [ ] 格式不支援時有正確顯示警告，且所有原始資料完整保留。

---

## 十、重新分析既有測試資料

若已經完成測試並保留了原始資料夾，無需重新執行待機測試，可直接呼叫 Python 腳本重新產生分析報告：

```bash
python3 ~/doze/doze_summary-termux.py \
  ~/storage/downloads/doze-test/測試資料夾/full.txt \
  --checkin ~/storage/downloads/doze-test/測試資料夾/checkin.txt \
  --pkg ch.deletescape.lawnchair.plah \
  --deviceidle ~/storage/downloads/doze-test/測試資料夾/deviceidle.txt \
  --mem \
    ~/storage/downloads/doze-test/測試資料夾/mem_start.txt \
    ~/storage/downloads/doze-test/測試資料夾/mem_end.txt \
  --battery \
    ~/storage/downloads/doze-test/測試資料夾/battery_start.txt \
    ~/storage/downloads/doze-test/測試資料夾/battery_end.txt
```

若要將重新分析的結果存成新檔案：

```bash
python3 ~/doze/doze_summary-termux.py \
  ~/storage/downloads/doze-test/測試資料夾/full.txt \
  --checkin ~/storage/downloads/doze-test/測試資料夾/checkin.txt \
  --deviceidle ~/storage/downloads/doze-test/測試資料夾/deviceidle.txt \
  > ~/storage/downloads/doze-test/測試資料夾/summary-recheck.txt
```

---

## 十一、後續可擴充方向

1. **Alarm 時間解析強化**：針對不同 OEM 廠牌的 `dumpsys alarm` 格式建立專屬解析器。
2. **History 格式辨識擴充**：支援更多客製化 ROM 的 BatteryStats History 格式並統計解析成功率。
3. **meminfo 動態欄位解析**：針對不同 Android 版本的記憶體表格結構進行更精細的欄位對應。
4. **測試品質總評**：在報告開頭自動給出本次測試的有效性評級（如是否曾亮屏干擾、是否成功進入 Deep Idle）。
5. **多次測試橫向比較**：支援輸入多個測試資料夾，自動比較不同設定下的 `mAh/h` 耗電速率與 Deep Idle 佔比。

---

## 十二、使用聲明

本工具僅作為 Android 系統資料的擷取與分析輔助工具，不會修改系統省電政策，也不保證裝置必定進入 Deep Doze。分析結果受 Android 版本、廠牌客製化、電池計數器精度及測試環境影響，摘要報告僅供參考，請務必保留原始擷取檔案以供核對。
