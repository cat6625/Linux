# `battery.py` 使用手冊與名詞解釋

本手冊說明如何在 Termux 透過 `adb` 執行 `~/doze/battery.py`（`v1.1.2`）查詢 Android 電池耗電率、Doze 待機、喚醒（Wakelock）排行與 `u0a` 套件反查，並示範如何以 `>` 或 `tee` 匯出帶時間戳記的純文字報告檔。

---

## CLI 參數與常見用法

目前 `battery.py` 支援以下 CLI 參數（可直接放位置參數，也可用具名旗標）：

| 參數 | 簡寫 | 型別 / 預設值 | 說明 |
|---|---|---|---|
| `top_n_pos` | （位置參數） | `int`（選填） | 直接在指令後方輸入數字，指定各排行榜顯示前幾名（例如 `battery.py 15`），優先度高於 `--top`。 |
| `--top` | `-n` | `int`，預設 `10` | 指定各排行榜顯示前幾名項目（最小為 `1`）。 |
| `--file` | `-f` | `str`，預設 `None` | 改從本機儲存的 `dumpsys batterystats` 文字檔讀取，不連線 ADB，也會跳過即時反查 UID 套件名稱。 |
| `--merge` | `-m` | `bool`（旗標），預設 `False` | 在「最耗電項目」與「使用者 App（u0a）」估算排行榜中，將同名項目合併加總 `mAh`、`cpu`、`wake`，並標註 `[合併 X 筆]`。 |
| `--merge-wl` | — | `bool`（旗標），預設 `False` | 在「背景喚醒（Partial Wake Lock）」排行榜中，將同名喚醒項目合併加總時長與次數，並標註 `[合併 X 筆]`。 |
| `--hide-wm` | — | `bool`（旗標），預設 `False` | 在「背景喚醒（Partial Wake Lock）」排行榜中隱藏包含 `WindowManager` 的項目，方便聚焦於背景服務／App／排程喚醒。 |
| `--version` | `-V` | — | 顯示目前腳本版本號與日期並結束程式。 |
| `--help` | `-h` | — | 顯示參數說明並結束程式。 |

### 常見組合範例

* **基本即時查看前 15 名**：
  ```bash
  python3 ~/doze/battery.py 15
  ```
* **合併同名耗電並隱藏 `WindowManager` 干擾**：
  ```bash
  python3 ~/doze/battery.py 15 --merge --hide-wm
  ```
* **離線分析存檔並合併同名背景喚醒**：
  ```bash
  python3 ~/doze/battery.py -n 15 -f stats.txt --merge --merge-wl --hide-wm
  ```

---

## 一、基本使用方式

### 1. 執行腳本（預設 Top 10）
```bash
python3 ~/doze/battery.py --merge --merge-wl --hide-wm
```

### 2. 指定顯示前 N 名（例如 Top 15）
```bash
python3 ~/doze/battery.py 15 --merge --merge-wl --hide-wm
```

> **說明**：腳本會先透過 `adb shell getprop` 讀取裝置與系統資訊，再抓取 `adb shell dumpsys batterystats` 進行解析，並針對前幾名涉及的 UID 查詢對應套件名稱，最後自動將電子信箱去識別化（例如 `s***w@yahoo.com.tw`）。

---

## 二、使用 `>` 或 `tee` 匯出帶時間檔名的報告檔

在 Termux（Bash / Zsh）中，可利用 `$(date +%Y%m%d_%H%M%S)` 動態產生時間檔名，方便做多次充放電或待機測試的對照紀錄。

### 1. 只存檔、不在螢幕顯示（使用 `>`）
```bash
mkdir -p ~/doze/reports && python3 ~/doze/battery.py --merge --merge-wl --hide-wm > ~/doze/reports/battery_$(date +%Y%m%d_%H%M%S).txt
```

### 2. 同時顯示在螢幕並存成檔案（使用 `tee`）
```bash
mkdir -p ~/doze/reports && python3 ~/doze/battery.py --merge --merge-wl --hide-wm | tee ~/doze/reports/battery_$(date +%Y%m%d_%H%M%S).txt
```

### 3. 搭配自訂 Top N 與 `tee` 匯出
```bash
mkdir -p ~/doze/reports && python3 ~/doze/battery.py 15 --merge --merge-wl --hide-wm | tee ~/doze/reports/battery_$(date +%Y%m%d_%H%M%S)_top15.txt
```

### 4. 加上 `2>&1` 同時記錄錯誤訊息（排錯用）
```bash
mkdir -p ~/doze/reports && python3 ~/doze/battery.py --merge --merge-wl --hide-wm 2>&1 | tee ~/doze/reports/battery_$(date +%Y%m%d_%H%M%S).log
```

### 5. 查看與比對已匯出的報告檔
```bash
ls -lh ~/doze/reports/
cat ~/doze/reports/battery_20261123_081500.txt
```

> **提醒**：使用 `>` 覆蓋寫入新檔案時，若檔名相同會覆蓋原檔；加上 `%Y%m%d_%H%M%S` 可避免檔名衝突。若 `adb` 輸出尾端偶爾出現 `Broken pipe` 提示，通常不影響已產生的報告內容。

---

## 三、重點計算公式一覽

腳本中所有百分比與耗電率皆以 `dumpsys batterystats` 擷取的數值計算，公式如下：

### 1. 容量佔比與電池健康度
* **估計容量比**：
  $$\text{估計容量比 (\%)} = \frac{\text{Discharge}}{\text{Estimated battery capacity}} \times 100\%$$
* **學習容量比**：
  $$\text{學習容量比 (\%)} = \frac{\text{Discharge}}{\text{Max learned battery capacity}} \times 100\%$$
* **電池健康度（估算）**：
  $$\text{健康度 (\%)} = \frac{\text{Max learned battery capacity}}{\text{Estimated battery capacity}} \times 100\%$$

### 2. 亮屏與熄屏耗電率（`mAh/h` 與 `%/h`）
* **每小時耗電量（`mAh/h`）**：
  $$\text{亮屏耗電率 (mAh/h)} = \frac{\text{Screen on discharge}}{\text{Screen on 時長 (h)}}$$
  $$\text{熄屏耗電率 (mAh/h)} = \frac{\text{Screen off discharge}}{\text{Time on battery screen off 時長 (h)}}$$
* **每小時耗電百分比（`%/h`）**：`v1.1.2` 會以「估計容量（標準）」為主，若「學習容量」存在且與估計容量不同，會並列顯示「學習」百分比：
  $$\text{標準耗電率 (\%/h)} = \frac{\text{耗電率 (mAh/h)}}{\text{Estimated battery capacity}} \times 100\%$$
  $$\text{學習耗電率 (\%/h)} = \frac{\text{耗電率 (mAh/h)}}{\text{Max learned battery capacity}} \times 100\%$$

> **判讀提醒**：`Screen on discharge` 與 `Screen off discharge` 為該時段**整機總放電量**，並非單一硬體元件耗電；若開啟充電上限（如 80% 電池保護）或燃料計學習容量偏移，實際體感掉電速度會高於標準 `%/h`，跨機型比對建議優先看 `mAh/h`。

### 3. 待機時長佔比、喚醒佔熄屏比與項目佔放電比
* **淺睡／深睡佔熄屏比例**：
  $$\text{淺睡佔熄屏 (\%)} = \frac{\text{Device light idling}}{\text{Time on battery screen off}} \times 100\%$$
  $$\text{深睡佔熄屏 (\%)} = \frac{\text{Device full idling}}{\text{Time on battery screen off}} \times 100\%$$
* **喚醒佔熄屏比例（Kernel / Partial Wake Lock）**：
  $$\text{佔熄屏 (\%)} = \frac{\text{單項喚醒時長 (h)}}{\text{Time on battery screen off (h)}} \times 100\%$$
* **單項估算佔放電比例**：
  $$\text{佔放電 (\%)} = \frac{\text{項目估算 mAh}}{\text{Discharge (mAh)}} \times 100\%$$

---

## 四、耗電來源與排行榜判讀

### 1. 排行榜數值來自哪裡？
* **`Estimated power use (mAh)` 估算排行**：來自 `dumpsys batterystats` 的 `Estimated power use (mAh)` 區塊，是 Android 框架依據 CPU 時間、螢幕亮屏與亮度、Wi-Fi／行動網路傳輸、感測器、GNSS 與喚醒鎖等模型權重**估算**出來的數值，**不是硬體電流計的逐筆實測值**。
* 由於各子系統（如 `cpu`、`idle`、`screen`、`wifi`）與各 `UID` 在估算模型中存在權重或重疊計算，排行榜中各項目「佔放電 %」加總超過 `100%` 屬於正常現象；**重點在於看相對排序、趨勢變化與實際亮／熄屏放電（`Discharge`）**。

### 2. 實例解讀：`UID u0a1338` 與 `UID u0a280`
以這兩筆輸出為例：
```text
1. UID u0a1338 [com.brave.browser]：97.7 mAh（佔放電 17.9%）
2. UID u0a280 [in.mfile]：85.0 mAh（佔放電 15.6%）
```
* **`UID u0a1338 [com.brave.browser]`（`97.7 mAh`，佔放電 `17.9%`）**：
  * **來源**：使用者空間 App `com.brave.browser`（`u0a1338` 對應 `appId = 11338`）。
  * **主要耗電構成**：瀏覽器屬於高亮屏互動型 App，估算耗電通常由 **螢幕亮屏時長（`screen`）**、網頁渲染與 JS 執行的 **CPU（`cpu`）**（含前景 `fg` 與背景/快取 `cached` 進程）以及 **Wi-Fi / 網路傳輸（`wifi`）** 組成。若螢幕開啟時間長，螢幕與 CPU 往往佔大宗。
* **`UID u0a280 [in.mfile]`（`85.0 mAh`，佔放電 `15.6%`）**：
  * **來源**：使用者空間 App `in.mfile`（`u0a280` 對應 `appId = 10280`）。
  * **主要耗電構成**：多半與前台操作時的**螢幕亮屏（`screen`）**、檔案掃描／索引／傳輸或背景任務帶來的 **CPU（`cpu`）** 估算有關。若亮屏時間不長卻有較高估算值，則需留意是否有背景掃描或持續處理檔案的行為。

---

## 五、名詞解釋

### 1. 電池容量與健康度
* **估計電池容量（Estimated battery capacity）**：系統或電池設定檔記載的標稱／估計容量（`mAh`）。
* **學習容量範圍（Min / Max learned battery capacity）**：系統根據實際充放電循環推算出的可用容量區間（`mAh`）。當電池老化或衰退時，學習容量常低於估計容量；但部分機型或長期啟用充電上限時，燃料計也可能出現高於標稱值的學習數值。
* **累計放電（Discharge）**：自上次充電起算週期內的總放電量（`mAh`）。
* **亮屏 + 熄屏合計與差值**：將 `Screen on discharge` 與 `Screen off discharge` 相加後，與 `Discharge` 比對的差值；正常情況通常接近 `0` 或僅差數 `mAh`。

### 2. 亮屏與熄屏耗電率
* **亮屏耗電率（Screen on rate）**：螢幕開啟期間的平均每小時耗電量（`mAh/h` 與 `%/h`），受螢幕亮度（如 `dark` / `dim` / 高亮）、更新率、遊戲或影音播放影響最大。
* **熄屏耗電率（Screen off rate）**：螢幕關閉期間的平均每小時耗電量（`mAh/h` 與 `%/h`），主要反映待機、背景同步、通知推送與網路喚醒的表現。

### 3. 待機、Doze 與喚醒
* **淺睡（Light doze / Device light idling）**：螢幕關閉後較早進入的低功耗待機階段，仍允許部分定期維護或網路工作執行。
* **深睡（Deep doze / Device full idling）**：螢幕關閉且裝置靜置一段時間後進入的深度省電狀態，會進一步限制背景網路存取、喚醒鬧鐘與背景工作。深睡佔熄屏比例越高，通常代表待機越穩定。
* **Full wakelock**：要求保持螢幕或較高層級清醒狀態的喚醒鎖累計時間。
* **Partial wakelock**：允許螢幕保持關閉，但讓 CPU 維持清醒以執行背景運算、工作排程或同步的喚醒鎖累計時間。

### 4. 核心喚醒與背景喚醒排行
* **核心喚醒（Kernel Wake Lock）Top N**：Linux 核心與驅動程式層級的喚醒統計（如 `PowerManagerService.WakeLocks`、`wlan_ma`、`hip4_wake_lock_tx`、`NETLINK` 等）。**時間長**代表持續佔用喚醒較久；**次數高但時間短**則代表高頻短喚醒（例如 Wi-Fi 或資料鏈路封包／中斷頻繁）。
* **背景喚醒（Partial Wake Lock）Top N**：應用程式、系統服務、工作排程（`*job*`）或同步任務（`*sync*`）持有的喚醒鎖排行，腳本會自動去除重複項目、反查 UID 對應套件名稱，並將電子信箱遮罩。

### 5. 耗電項目排行與 UID
* **最耗電項目 Top N（總覽估算）**：`Estimated power use (mAh)` 區塊中依估算耗電量排序的項目，除了 `UID` 之外，也可能包含 `screen`、`cpu`、`idle`、`wifi`、`mobile_radio`、`sensors`、`wakelock` 等硬體或系統估算項目。
* **WiFi AP wakeups**：Wi-Fi 連線期間受無線基地台（AP）廣播或封包喚醒所估算的耗電量；若數值偏高，通常與網路環境、頻段（2.4GHz / 5GHz）或背景掃描設定有關。
* **UID 與 `u0a...`**：Android 為每個應用程式或系統元件分配的使用者識別碼（UID）。一般第三方或使用者安裝的 App 常見 `u0a<編號>` 格式（對應 `10000 + <編號>`）；`UID 1000` 則代表 Android 系統／核心服務群組。
