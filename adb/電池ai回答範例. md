# Android BatteryStats 電池統計數據深度分析報告

> **📋 原始提問與分析需求**
> 
> 請幫我分析以下這段 Android 系統的 batterystats（電池統計數據）日誌檔。
> 
> 1. **核心數據總覽與換算**：
>    - 估計電池總容量是多少 mAh？
>    - 這次統計歷時多久？總共消耗多少 mAh？換算約扣除百分之幾的電量？
>    - 螢幕開啟時間（SoT）與螢幕關閉（待機）時間各是多少？
> 
> 2. **每小時耗電率（%/h）精算與評級**：
>    - 計算「螢幕開啟耗電率（%/h）」與「螢幕關閉待機耗電率（%/h）」。
>    - 簡評這個耗電數據屬於「極佳、正常、還是偏高」？
> 
> 3. **軟體與背景耗電黑手**：
>    - 點名背景活動最頻繁、最可能導致耗電的 App 或系統服務（如 com.google.android.gms），並解釋其可能行為。
> 
> 4. **系統與硬體環境影響**：
>    - 檢查「訊號強度（Cellular Signal Strength）」、「Wi-Fi / 行動網路切換」對耗電的影響。
>    - 檢查是否有異常的「GPS / 定位時間」或「感測器（Sensors）使用過度」。

---

> **分析結論摘要**[span_0](start_span)[span_0](end_span)  
> 本次電池數據統計歷時約 **25.7 小時**，總消耗 **4,066 mAh**（約 **81%** 電量）[span_1](start_span)[span_1](end_span)。  
> 核心結論：本次耗電主因為 **長螢幕開啟時間（SoT 達 8 小時 44 分）** 搭配 **高頻率 LTE/LTE-CA 行動網路傳輸**，待機機制（Doze）運作極佳（螢幕關閉耗電僅約 **0.41%/h**），並無待機漏電、GPS 或 Sensor 異常過載問題[span_2](start_span)[span_2](end_span)。

---

## 1. 核心數據總覽

| 分析項目 | 數據紀錄 | 判讀與說明 |
| :--- | :--- | :--- |
| **統計總時長** | 25 小時 44 分 06 秒 | 約 1.072 天[span_3](start_span)[span_3](end_span) |
| **系統標稱容量** | 5,020 mAh | 系統韌體預設標稱容量[span_4](start_span)[span_4](end_span) |
| **實際學習容量** | 4,354 – 4,439 mAh | 系統學習到的可用容量上限（約標稱值的 87~88%）[span_5](start_span)[span_5](end_span) |
| **總消耗電量** | 4,066 mAh | 約 4.07 Ah（BatteryStats 估計值為 4,000–4,050 mAh）[span_6](start_span)[span_6](end_span) |
| **電量消耗百分比** | 81.0% | 以 5,020 mAh 計算：$4066 \div 5020 \approx 81.0\%$（與日誌 80~81% 完全吻合）[span_7](start_span)[span_7](end_span) |
| **螢幕開啟時間 (SoT)** | 8 小時 44 分 34 秒 | 約佔總時長 34.0%，屬於高強度使用[span_8](start_span)[span_8](end_span) |
| **螢幕關閉時間 (待機)** | 16 小時 59 分 32 秒 | 約佔總時長 66.0%[span_9](start_span)[span_9](end_span) |
| **當下剩餘預估續航** | 5 小時 52 分 | 依當前狀態持續估計[span_10](start_span)[span_10](end_span) |

### 💡 電池容量與實際可用度解析
1. **標稱容量 vs. 學習容量**：
   - 系統認定容量：**5,020 mAh**[span_11](start_span)[span_11](end_span)
   - 實際可用容量（Learned Capacity）：約 **4,400 mAh**（4,354~4,439 mAh）[span_12](start_span)[span_12](end_span)
   - **判讀**：學習容量約為設計值的 **87~88%**，符合使用一段時間後正常的電池健康度老化或校準後狀態[span_13](start_span)[span_13](end_span)。
2. **放電比例校驗**：
   - 實際耗電 $4066 \text{ mAh} \div 5020 \text{ mAh} = 81.0\%$，與 Log 中的 `Amount discharged: 80-81` 完全符合[span_14](start_span)[span_14](end_span)。

---

## 2. 耗電率精算與評級

### 🔴 螢幕開啟耗電率 (Screen On Rate)
- **螢幕開啟時間**：8.743 小時 (8h 44m 34s)[span_15](start_span)[span_15](end_span)
- **螢幕開啟消耗電量**：3,715 mAh[span_16](start_span)[span_16](end_span)
- **平均電流**：$3715 \text{ mAh} \div 8.743 \text{ h} \approx 425 \text{ mA}$[span_17](start_span)[span_17](end_span)
- **每小時耗電率計算**：
  - **以標稱容量 (5,020 mAh) 計**：$425 \div 5020 \times 100\% \approx$ **8.47% / h**[span_18](start_span)[span_18](end_span)
  - **以實際容量 (4,400 mAh) 計**：$425 \div 4400 \times 100\% \approx$ **9.66% / h**[span_19](start_span)[span_19](end_span)
- **綜合評級**：🟡 **正常 ～ 稍高**[span_20](start_span)[span_20](end_span)
- **情境分析**：
  - Log 紀錄顯示螢幕亮度為 `dark 8h 44m 34s (100%)`[span_21](start_span)[span_21](end_span)。若實際環境包含 **5G/LTE CA、高刷新率、高效能 CPU/GPU 負載或影音串流**，耗電約 8.5%/h 屬於正常範圍；若僅為低亮度 Wi-Fi 純文字閱讀，則偏高[span_22](start_span)[span_22](end_span)。

### 🟢 螢幕關閉待機耗電率 (Screen Off Rate)
- **螢幕關閉時間**：16.992 小時 (16h 59m 32s)[span_23](start_span)[span_23](end_span)
- **螢幕關閉消耗電量**：351 mAh[span_24](start_span)[span_24](end_span)
- **平均電流**：$351 \text{ mAh} \div 16.992 \text{ h} \approx 20.65 \text{ mA}$[span_25](start_span)[span_25](end_span)
- **每小時耗電率計算**：
  - **以標稱容量 (5,020 mAh) 計**：$20.65 \div 5020 \times 100\% \approx$ **0.41% / h**[span_26](start_span)[span_26](end_span)
  - **以實際容量 (4,400 mAh) 計**：$20.65 \div 4400 \times 100\% \approx$ **0.47% / h**[span_27](start_span)[span_27](end_span)
- **綜合評級**：🟢 **極佳 ～ 正常偏優**[span_28](start_span)[span_28](end_span)
- **情境分析**：
  - 接近 17 小時的待機僅消耗約 7% 電量，無任何異常漏電現象[span_29](start_span)[span_29](end_span)。

### 📊 總耗電結構比例
$$\text{螢幕開啟耗電佔比} = \frac{3715 \text{ mAh}}{4066 \text{ mAh}} \approx 91.4\%$$[span_30](start_span)[span_30](end_span)
$$\text{螢幕關閉耗電佔比} = \frac{351 \text{ mAh}}{4066 \text{ mAh}} \approx 8.6\%$$[span_31](start_span)[span_31](end_span)
> **結論**：整天 **91.4% 的耗電皆發生於螢幕亮起使用期間**，待機耗電影響微乎其微[span_32](start_span)[span_32](end_span)。

---

## 3. 耗電黑手排行榜與 UID 分析

> ⚠️ **注意**：日誌中缺少 `packages:` 與 `Uid mapping` 對照表，故無法直接得出 UID 對應的 App 包名（如 `u0a274` 尚無法 100% 確定為 `com.google.android.gms`）[span_33](start_span)[span_33](end_span)。

### 🏆 耗電嫌疑犯排行榜

| 排名 | 對象 / UID | 估算耗電量 | 主要特徵與耗電來源 |
| :---: | :--- | :--- | :--- |
| 🥇 | **Screen (螢幕)** | **1,116 mAh** | 螢幕顯示（Power model 分攤估算值）[span_34](start_span)[span_34](end_span) |
| 🥈 | **Uid 1051 / Cellular Radio** | **788 mAh** | 行動網路數據晶片硬體耗電[span_35](start_span)[span_35](end_span) |
| 🥉 | **u0a274** | **595 mAh** *(Direct)* | Radio 耗電 510 mAh（佔比 86%），Smearing 估算值 1,580 mAh[span_36](start_span)[span_36](end_span) |
| 4 | **Android System (UID 1000)** | **527 mAh** | CPU 耗電 516 mAh（系統服務總體計算）[span_37](start_span)[span_37](end_span) |
| 5 | **u0a182** | **343 mAh** *(Direct)* | Radio 耗電 296 mAh（佔比 86%）[span_38](start_span)[span_38](end_span) |
| 6 | **Cell Standby** | **283 mAh** | 行動網路待機維持[span_39](start_span)[span_39](end_span) |
| 7 | **u0a1176** | **182 mAh** *(Direct)* | Radio 耗電 154 mAh（佔比 85%）[span_40](start_span)[span_40](end_span) |
| 8 | **u0a181** | **174 mAh** *(Direct)* | Radio 耗電 147 mAh（佔比 84%）[span_41](start_span)[span_41](end_span) |
| 9 | **Device Idle** | **173 mAh** | 系統待機基礎消耗[span_42](start_span)[span_42](end_span) |

---

### 🔍 主要 UID 行為深入剖析

1. **`u0a274`（重點疑點）**
   - **直接耗電**：`595 mAh` （CPU: 85.3, Wake: 0.0005, Radio: **510 mAh**, GPS: 0.0295）[span_43](start_span)[span_43](end_span)
   - **分析**：高達 **86%** 的直接耗電來自 **Cellular Radio（行動網路傳輸）**，非 CPU 運算[span_44](start_span)[span_44](end_span)。Smearing 分攤後高達 1,580 mAh（包含螢幕與系統共享硬體分攤）[span_45](start_span)[span_45](end_span)。
2. **`u0a182`**
   - **直接耗電**：`343 mAh` （CPU: 46.5, Wake: 0.38, Radio: **296 mAh**）[span_46](start_span)[span_46](end_span)
   - **分析**：同樣有 **86%** 的耗電來自 Radio，屬於頻繁發送網路請求的應用或服務[span_47](start_span)[span_47](end_span)。
3. **`u0a1176` 與 `u0a181`**
   - **耗電**：分別為 `182 mAh` 與 `174 mAh`[span_48](start_span)[span_48](end_span)。
   - **分析**：耗電結構均為 **Radio 主導**（占比 > 84%），Wi-Fi、GPS 與 Sensor 耗電幾乎為 0[span_49](start_span)[span_49](end_span)。
4. **`UID 1000` (Android System)**
   - **直接耗電**：`527 mAh` （CPU: **516 mAh**）[span_50](start_span)[span_50](end_span)
   - **分析**：屬於 Android Framework / System Server 的整體運算消耗[span_51](start_span)[span_51](end_span)。考慮到長達 8.75 小時的 SoT，此 CPU 消耗屬於正常系統維運範圍[span_52](start_span)[span_52](end_span)。

---

## 4. 硬體與環境影響分析

### 📡 1. 行動網路與訊號強度 (Cellular Signal)
- **訊號品質分佈**：
  - **Good (良好)**：15 小時 01 分 (**58.4%**)[span_53](start_span)[span_53](end_span)
  - **Great (優良)**：9 小時 57 分 (**38.7%**)[span_54](start_span)[span_54](end_span)
  - **Moderate (中等)**：44 分 45 秒 (**2.9%**)[span_55](start_span)[span_55](end_span)
  - **Poor (差)**：0.55 秒 (**< 0.1%**)[span_56](start_span)[span_56](end_span)
- **判讀**：Good + Great 占比高達 **97.1%**，訊號環境非常優良[span_57](start_span)[span_57](end_span)。
- **結論**：❌ **排除「因訊號差導致 Modem 提高功率搜訊而耗電」的可能性。**[span_58](start_span)[span_58](end_span)

### ⚙️ 2. Cellular Kernel Active 時間現象
- **Kernel Active 時間**：`12 小時 06 分` (佔總時間 **47.0%**)[span_59](start_span)[span_59](end_span)
- **LTE CA 啟用率**：`96.9%`[span_60](start_span)[span_60](end_span)
- **數據傳輸紀錄**：`Cellular Rx time: 3.298s` / `Tx time: 0`[span_61](start_span)[span_61](end_span)
- **分析**：Kernel active 長達 12 小時但 Rx/Tx 紀錄極低，反映出 Modem 長時間維持於 LTE 載波聚合 (CA) 的活躍/連線狀態，此為主要硬體耗電（788 mAh + 283 mAh = 1,071 mAh，約佔總耗電 26.3%）的原因[span_62](start_span)[span_62](end_span)。

### 📶 3. Wi-Fi 與網路切換
- **Wi-Fi 狀態**：幾乎全程處於 `Disconnected`（WiFi Active: 23.5s, 數據收發為 0 B）[span_63](start_span)[span_63](end_span)。
- **網路切換次數 (Connectivity changes)**：僅 **4 次**[span_64](start_span)[span_64](end_span)。
- **結論**：🟢 **無頻繁切換網路造成的耗電問題。**[span_65](start_span)[span_65](end_span)

### 📍 4. 定位 (GPS) 與感測器 (Sensors)
- **GPS 總使用時間**：約 5 分 40 秒（Poor: 5m 35s, Good: 5s）[span_66](start_span)[span_66](end_span)。
- **GPS / Sensor 耗電量**：各 App 分配的 GPS/Sensor 耗電均小於 `0.05 mAh`[span_67](start_span)[span_67](end_span)。
- **結論**：🟢 **GPS 與 Sensors 完全無異常耗電。**[span_68](start_span)[span_68](end_span)

### 🌙 5. 待機休眠 (Doze) 與 Wakelock 機制
- **Light Doze**：4 小時 39 分[span_69](start_span)[span_69](end_span)
- **Full Doze**：11 小時 18 分（Full Idle 時間佔比 **43.9%**，最長單次休眠 **3h 47m 45s**）[span_70](start_span)[span_70](end_span)
- **Wakelocks**：Full Wakelock 僅 19 分 20 秒，Partial Wakelock 僅 21 分 58 秒[span_71](start_span)[span_71](end_span)。
- **結論**：🟢 **Doze 機制運作非常完善，無異常 Wakelock 阻止 CPU 休眠。**[span_72](start_span)[span_72](end_span)

---

## 5. 總結與續追建議

### 📌 核心總結
1. **健康度與待機**：這台手機**沒有待機漏電問題**[span_73](start_span)[span_73](end_span)。待機耗電僅約 **0.41%/h**，Doze 深度休眠機制正常[span_74](start_span)[span_74](end_span)。
2. **耗電主因**：高達 81% 的電量消耗，主要來自 **8 小時 44 分鐘的長螢幕開啟使用**，以及全程依賴 **LTE/LTE-CA 行動網路**[span_75](start_span)[span_75](end_span)。
3. **軟體特徵**：主要的耗電 App（如 `u0a274`, `u0a182`）均呈現 **Radio-heavy（行動網路傳輸高）** 的特徵，而非 CPU 背景偷跑或背景鎖喚醒[span_76](start_span)[span_76](end_span)。

### 🔍 建議下一步（精確鎖定 App）
若要精確指出到底是哪幾個 App（例如確認 `u0a274` 是否為 Google Play Services 或特定的通訊/社群軟體），建議補充 BatteryStats Log 中的以下段落[span_77](start_span)[span_77](end_span)：
```text
packages:
