# Android ADB 待機與深度休眠（Deep Sleep）標準測試流程

本流程整合了 `batterystats`（精準計算掉電率與喚醒鎖）與 `deviceidle`（追蹤進入深度休眠時間點），用於排查特定時段的異常待機耗電。

---

## 階段一：測試前準備（歸零與基準點）

建議在睡前或準備長時間靜置手機前執行。**全程強烈建議使用無線 ADB（Wireless Debugging）**，避免插拔 USB 傳輸線觸發充電狀態而影響數據統計。

1. **將手機充至固定電量**（建議 90% 以上）。
2. **重置電池統計數據**：
   ```bash
   adb shell dumpsys batterystats --reset
   ```
   * **說明**：將所有 App 的耗電與喚醒次數歸零，從這一刻重新計算。
3. **匯出測試前的 Doze 歷史紀錄（建立基準點）**：
   ```bash
   adb shell dumpsys deviceidle > idle_before.txt
   ```
4. **關閉螢幕並開始靜置**：
   * 拔除所有充電線與傳輸線。
   * 將手機平放在桌面（避免移動觸發動態感測器喚醒）。
   * 靜置至少 **2～4 小時**（建議測試一整晚睡眠時段）。

---

## 階段二：測試結束（收集數據）

靜置時間結束後，點亮螢幕並**立刻**執行以下指令（先不要滑動其他 App，以免混入操作耗電）：

1. **匯出完整的電池統計報告**：
   ```bash
   adb shell dumpsys batterystats > battery_after.txt
   ```
2. **匯出測試後的 Doze 歷史紀錄**：
   ```bash
   adb shell dumpsys deviceidle > idle_after.txt
   ```
3. **快速查看核心 Deep Sleep 總時間（可選）**：
   ```bash
   adb shell dumpsys batterystats | grep -i "Deep sleep time"
   ```

---

## 階段三：快速判讀數據指標

取得輸出檔案後，檢查以下三個關鍵指標即可評估待機表現：

### 1. 實際進入深度休眠的時間點
* **查看方式**：打開 `idle_after.txt`，拉到最底部的 `Idling history:` 區塊，對照 `idle_before.txt` 的最後一行。
* **判讀標準**：多出來的紀錄即為本次測試的完整過程。正常情況下，裝置應在關閉螢幕後 **30～45 分鐘內**進入 `deep-idle`。

### 2. 螢幕關閉後的每小時掉電率
* **查看方式**：在 `battery_after.txt` 中搜尋關鍵字 `Screen off discharge rate`。
* **判讀標準**：
  * **正常健康**：約 **0.3% ～ 0.8% / 小時**（視 5G/Wi-Fi 訊號強弱而定）。
  * **異常偏高**：若超過 **1.5% / 小時**，代表存在異常耗電。

### 3. 抓出阻止休眠的 App（Wakelock）
* **查看方式**：在 `battery_after.txt` 中搜尋關鍵字 `All partial wake locks:`。
* **判讀標準**：此區塊會依「喚醒時間長短」由上往下排列。若前幾名出現第三方 App（如社群、通訊軟體）累積喚醒長達數分鐘以上，即為阻止手機進入深度休眠的元兇。
