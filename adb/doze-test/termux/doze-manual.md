# Termux Doze 測試環境安裝與使用手冊

## 一、 Termux 套件與環境初始化（執行一次）

打開 Termux，依序貼上並執行以下指令：

1. **更新套件並安裝必要工具**（ADB 工具、Python、Port 自動掃描工具）：
   ```bash
   pkg update && pkg upgrade -y
   pkg install android-tools python nmap -y
   ```

2. **授權外部儲存空間**（僅用來存放測試輸出的報告）：
   ```bash
   termux-setup-storage
   ```
   *(跳出權限視窗時請按「允許」)*

3. **建立內部安全腳本目錄**：
   ```bash
   mkdir -p ~/doze
   ```

---

## 二、 檔案放置位置（安全隔離結構）

為了防止其他 App 竄改可執行腳本，**程式本體放 Termux 內部空間，只有測試結果放外部下載資料夾**：

| 檔案類型 | 存放路徑 | 說明 |
| :--- | :--- | :--- |
| **主執行腳本** | `~/doze/doze.sh` | 內部私有目錄，受 Android 沙盒保護 |
| **摘要分析程式** | `~/doze/doze_summary-termux.py` | 內部私有目錄，由主腳本呼叫 |
| **測試輸出報告** | `~/storage/downloads/doze-test/` | 對應手機內部儲存空間的 `Download/doze-test/`，方便查看與傳檔 |

---

## 三、 NMM File Manager 掛載內部目錄（方便日後修改）

透過 Android 原生的 SAF 機制，讓 NMM 直接編輯內部安全區的檔案：

1. 打開 **NMM File Manager** → 點左上角「三條線選單」→ 選擇 **「新增儲存空間 / 系統檔案選擇器（SAF）」**。
2. 在彈出的系統畫面左上角點「三條線選單」，往下滑找到並點擊 **Termux** 圖示。
3. 點選 **`doze`** 資料夾 → 按下方的 **「使用此資料夾」** → 按 **「允許」**。
4. 之後在 NMM 側邊欄點開 `doze`，就能直接將下載好的 `doze.sh` 與 `doze_summary-termux.py` 放入並編輯。

---

## 四、 建立快捷指令與執行權限（設定一次）

把 `doze.sh` 與 `doze_summary-termux.py` 放入 `~/doze/` 後，回到 Termux 執行以下指令，賦予執行權限並建立全域捷徑：

```bash
chmod +x ~/doze/doze.sh
ln -sf ~/doze/doze.sh $PREFIX/bin/doze
```

---

## 五、 日常測試執行流程

1. **開啟無線除錯**：
   * 拔除充電線，進入手機 **設定 → 開發人員選項 → 開啟「無線除錯」**。
   * *(若是第一次在此台手機使用，需先在無線除錯頁面點「使用配對碼配對裝置」，並在 Termux 執行 `adb pair 127.0.0.1:配對Port` 輸入 6 位數配對碼，只需配對一次。)*
2. **啟動測試**：
   * 打開 Termux，直接輸入指令（不需查 Port，會自動偵測）：
     ```bash
     doze
     ```
   * *(若自動偵測失敗，可手動加上無線除錯顯示的 Port，例如：`doze 39815`)*
3. **靜置與結束**：
   * 腳本會自動關閉螢幕並開始計時，請靜置手機（建議 **30 分鐘以上** 才會進入 Deep Idle）。
   * 測試結束時，喚醒螢幕回到 Termux，按 **`Enter`** 鍵即可自動收集數據並產生報告。
4. **查看結果**：
   * 報告會自動存放在手機的 **`Download/doze-test/日期_時間/summary-日期_時間.txt`**。
   * 測試完成後，建議順手關閉「無線除錯」以維持最佳安全性。
