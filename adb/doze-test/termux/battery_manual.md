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
