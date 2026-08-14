請重新完整讀取我上傳的「完整 dumpsys batterystats 檔案」。

這一次先不要做耗電原因分析，也不要推測哪個 App 造成耗電。

我的目的是確認你是否正確理解並讀取完整 BatteryStats 的資料結構。

【第一階段：先定位資料來源】

請先確認以下資料各自位於完整檔案的哪一個區段，例如：

1. Statistics since last charge
2. CONNECTIVITY POWER SUMMARY
3. Battery History / History timeline
4. 其他相關 Summary 區段

請明確區分：
- Summary 統計值
- Connectivity Summary 統計值
- Battery History 事件
- 不能由目前資料直接判定的數值

【第二階段：逐項確認以下 25 項資料】

請建立表格，逐項列出：

1. RESET:TIME
2. Start clock time
3. Time on battery
4. Realtime
5. Uptime
6. Screen on
7. Screen off
8. Discharge
9. Screen-off discharge
10. Device full idling
11. Idle mode full time
12. Mobile active
13. Mobile active 5G
14. Cellular kernel active
15. Cellular Sleep
16. Cellular Rx / Tx
17. WiFi kernel active
18. WiFi Sleep
19. WiFi Idle
20. WiFi Rx / Tx
21. WiFi estimated power
22. Estimated battery capacity
23. Last learned battery capacity
24. Min learned battery capacity
25. Max learned battery capacity

表格請使用以下欄位：

| 項目 | 原始值 | 資料來源區段 | 這個值代表什麼 | 是否可以直接使用 |
|---|---|---|---|---|

【第三階段：非常重要——不要混淆 Summary 與 History】

請特別檢查以下問題：

A.
如果 Battery History 最後一個事件時間只有例如：

+8m23s905ms

而 Statistics since last charge 中的 Time on battery 是更長的時間，

請明確說明這兩個數字為什麼不同。

禁止直接把 Battery History 的最後相對時間當成 Time on battery。

B.
如果 History 中出現：

charge=3771

請說明這個 charge=3771 到底代表什麼。

禁止直接把 charge=3771 解釋成：
- Estimated battery capacity
- Last learned battery capacity
- 電池最大容量

除非檔案中有明確證據支持。

C.
如果 History 中出現：

device_idle=light

請區分：
- light idle
- full idle
- Doze
- CPU suspend / kernel deep sleep

不要把這些概念直接視為完全相同。

D.
如果 Summary 中存在：

Device full idling
Idle mode full time

請以 Summary 的正式統計值為準，不要因為某一小段 History 沒看到 full-idle event，就推論整個 BatteryStats 統計期間沒有 full idle。

E.
如果存在：

WiFi kernel active
WiFi Sleep
WiFi Idle
+wifi_radio
-wifi_radio

請不要直接把它們視為同一個統計量。

請說明每一個欄位的實際統計意義，以及它們之間是否可以直接相加或互相等同。

F.
如果存在：

Cellular Sleep
Cellular Rx
Cellular Tx
Cellular kernel active
Mobile active

請同樣區分它們的統計層級，不要因為 Mobile active=0 就直接推論 modem 在整個期間完全沒有任何活動。

【第四階段：交叉驗證】

請使用完整檔案中的不同區段互相驗證。

例如：

Statistics since last charge
        ↓
Connectivity Power Summary
        ↓
Battery History

如果不同區段出現不同時間或不同數值：

1. 不要自行選擇其中一個。
2. 說明它們各自的統計範圍。
3. 說明哪一個數值才適合回答我指定的欄位。
4. 如果無法確定，請明確標記「無法由目前資料確定」。

【第五階段：禁止事項】

這次請不要：

- 不要猜測
- 不要用一般 Android 常識補足缺失資料
- 不要把 History event 當成 Summary statistic
- 不要把 charge=XXXX 當成電池容量
- 不要把 Uptime 直接說成 CPU 實際運算時間
- 不要把 screen off 直接等同於 Deep Sleep
- 不要把 Doze 直接等同於 Linux kernel suspend
- 不要把 WiFi kernel active 直接等同於 WiFi radio on
- 不要把 Mobile active=0 直接等同於 modem 完全沒有活動
- 不要根據一小段 History 推論整個 BatteryStats 統計期間
- 不要在尚未完成 25 項資料確認前進行耗電原因分析

最後只回答兩個部分：

第一部分：
「完整 BatteryStats 資料定位與 25 項確認表」

第二部分：
「我這份 BatteryStats 是否存在 Summary、Connectivity Summary、History 被混淆的風險」

暫時不要做耗電排行，也不要分析是哪個 App 造成耗電。
