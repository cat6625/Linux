# Android 待機耗電與 Doze 深度檢測工具組

一套專為 Linux 桌面環境（Ubuntu）設計的 Android 待機耗電、Doze 深眠狀態與背景排程（JobScheduler）診斷工具集。支援 **多裝置無線 ADB（Wi-Fi Debugging）同步批次擷取**、**跨 Android 版本格式解析（Android 11 ~ 15）** 以及 **敏感資訊（PII）自動遮蔽**。

---

## 📁 目錄結構

```text
doze-test/
├── battery.py          # 核心分析腳本：計算熄屏耗電率 (mAh/h)、Doze 佔比、喚醒鎖與耗電排行
├── battery_extract.py  # 精華擷取腳本：從龐大 batterystats 過濾關鍵區塊並遮蔽隱私資訊
├── jobhist.py          # 排程分析腳本：計算 Job 實際執行時間並抓出 10 分鐘逾時 (Quota Session)
├── dump_battery.sh     # 互動式批次擷取腳本：支援單機選擇、IP 匹配與一鍵全部抓取
├── reports/            # 自動產出的報告存放目錄（不與腳本混雜）
└── README.md           # 本使用手冊
```

---

## 🛠️ 工具說明與常用指令

所有 Python 工具均支援 **無參數直接透過 ADB 讀取**，也支援透過環境變數 `ANDROID_SERIAL` 指定特定無線/有線裝置。

### 1. `battery.py`（耗電率與喚醒排行榜）
將 `dumpsys batterystats` 轉化為易讀的中文診斷報告，自動解析真實套件名稱並支援跨版本格式（含 Android 15 換行明細與舊版 Smearing 分攤）。

```bash
# 指定單台無線裝置直接產出精簡報告（推薦參數組合）
ANDROID_SERIAL=192.168.1.186:36387 python3 battery.py --merge-wl --hide-wm --strict-mask

# 顯示前 20 名，並合併同名耗電與喚醒鎖項目
ANDROID_SERIAL=192.168.1.186:36387 python3 battery.py -n 20 -m --merge-wl

# 從本機已存檔的 raw.txt 離線分析
python3 battery.py -f reports/SM-M146B_raw.txt -n 15 -m
```
* **常用參數**：
  * `-n <數量>`：顯示前幾名項目（預設 10）。
  * `-m` / `--merge-wl`：合併估算排行榜 / Partial Wake Lock 中的同名項目。
  * `--hide-wm`：隱藏 `WindowManager` 項目。
  * `--strict-mask`：將信箱完整遮蔽為 `[EMAIL]`（預設保留首尾字元如 `a***b@domain.com`）。

---

### 2. `battery_extract.py`（精華過濾與安全分享檔）
從數百 KB 的原始 `batterystats` 中萃取核心統計數據，適合保留關鍵原始片段或分享給他人檢視。

```bash
# 指定裝置直接輸出安全分享摘要檔
ANDROID_SERIAL=192.168.1.186:36387 python3 battery_extract.py -o reports/extract.txt

# 讀取本機原始檔且不遮蔽資訊（僅供本地自己排查）
python3 battery_extract.py reports/raw.txt --raw
```

---

### 3. `jobhist.py`（JobScheduler 執行時間與逾時偵測）
解析 `dumpsys jobscheduler`，抓出最近執行的任務耗時，並從 `Quota Saved sessions` 中找出**被歷史紀錄洗掉的 10 分鐘強制逾時（600,000 ms）元兇**。

```bash
# 掃描指定裝置中執行超過 10 秒的任務與逾時 Session
ANDROID_SERIAL=192.168.1.112:35903 python3 jobhist.py --min 10 --top 10

# 只過濾特定套件（例如 Play 商店）
ANDROID_SERIAL=192.168.1.112:35903 python3 jobhist.py --pkg vending

# 完整遮蔽信箱帳號
ANDROID_SERIAL=192.168.1.112:35903 python3 jobhist.py --min 10 --strict-mask
```

---

### 4. `dump_battery.sh`（多裝置互動式完整備份腳本）
自動偵測所有連線裝置、提醒 `offline` 斷線機器、過濾 0 KB 異常空檔，並將 `_raw.txt`、`_extract.txt`、`_report.txt` 統一輸出至 `reports/`。

```bash
# 開啟互動式選單（自動列出 IP 與手機型號，輸入編號或 a 全部抓取）
./dump_battery.sh

# 免互動直接批次抓取全部連線裝置
./dump_battery.sh a

# 透過 IP 末三碼快速指定單台裝置
./dump_battery.sh 186
```

---

## ⚡ Ubuntu 終端機一鍵批次指令

### 一次產出所有連線裝置的 `battery.py` 精簡報告（免存大檔）
```bash
mkdir -p reports
TS=\$(date +%Y%m%d_%H%M%S)
for s in \$(adb devices | awk '\$2=="device"{print \$1}'); do
  m=(adb -s "s" shell getprop ro.product.model | tr -d \('\r' \vert{}\) tr ' /' '_')
  ANDROID_SERIAL="\$s" python3 battery.py --merge-wl --hide-wm --strict-mask > "reports/\({m}_\){TS}.txt"
  echo "✅ 已產生：reports/\({m}_\){TS}.txt"
done
```

### 一次掃描所有連線裝置的 `jobhist.py` 逾時排程
```bash
for s in \$(adb devices | awk '\$2=="device"{print \$1}'); do
  m=(adb -s "s" shell getprop ro.product.model | tr -d \('\r')\)
  echo "=========================================="
  echo "📱 裝置：[\(m] (\)s)"
  ANDROID_SERIAL="\$s" python3 jobhist.py --min 10 --top 10
done
```

---

## 🔍 常用 ADB 狀態檢查與控制指令

```bash
# 1. 重置電池統計數據（開始新一輪待機測試前執行，執行後請拔除 USB 並讓電腦休眠）
adb -s <SERIAL> shell dumpsys batterystats --reset

# 2. 查看目前 Light Doze 與 Deep Doze 狀態（mState=IDLE 代表已進入深眠）
adb -s <SERIAL> shell dumpsys deviceidle | grep -E "mState=|mLightState="

# 3. 查看活躍的 WakeLock 與核心休眠阻擋器 (Suspend Blockers)
adb -s <SERIAL> shell dumpsys power | grep -A 15 "Wake Locks:"

# 4. 列出裝置所有使用者（檢查是否有分身 / Island 工作資料夾等背景空間）
adb -s <SERIAL> shell pm list users

# 5. 限制特定 App（如異常喚醒的 Play 商店）在背景不受限執行
adb -s <SERIAL> shell cmd appops set --user 0 com.android.vending RUN_ANY_IN_BACKGROUND ignore
# （還原預設值：將 ignore 改為 allow）
```

---

## 📊 數據判讀基準與實測經驗法則

1. **跨機型請優先比對「熄屏耗電率（mAh/h）」而非百分比**：
   * 各廠牌電池標示容量（Typical / Rated）與學習容量常有偏移（例如標示 6000 實際換算為 4500 mAh），直接看 `mAh/h` 最客觀。
   * **健康基準**：一般智慧型手機在正常 Deep Doze 下，熄屏耗電率約落在 **10 ~ 20 mAh/h**（約 0.25% ~ 0.35%/h）；若超過 **40 mAh/h** 則屬於明顯異常。
2. **區分「真異常」與「晶片硬體特性」**：
   * **Kernel Wi-Fi 驅動鎖（如 `hip4_wake_lock_tx`、`wlan_ma`）**：在 Mesh Wi-Fi 環境下，部分晶片（如 Exynos 1330）底層處理區網封包會累積較高的驅動鎖時間，但只要實際 `mAh/h` 正常且 Deep Doze 佔比高（>75%），即屬正常現象，無須過度干預。
   * **真正的耗電殺手**：通常是 **弱訊號環境下的行動網路搜尋（`Cell standby`）**、**未停止的定位服務（如 `OfflineFindingService`）**，或是 **在 `jobhist.py` 中出現 10 分鐘強制逾時的背景任務**。
3. **無線 ADB 量測注意事項**：
   * 測試期間請讓 **測試電腦進入睡眠狀態**；若電腦持續醒著並連著無線 ADB 操作，密集的輪詢與網路傳輸會額外增加約 30~40 mAh/h 的消耗（反映在 `UID 2000 [com.android.shell]` 與 `UID 1020` 上）。
