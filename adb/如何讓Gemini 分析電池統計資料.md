可以。依照你這次測試 Gemini 的結果，我建議不要一開始就叫它「分析整份檔案」，而是採用四階段流程。這樣可以測出它到底能不能真正處理大型 dumpsys batterystats，而不只是抓摘要。

下面這份可以直接複製給 Gemini。


---

Gemini 分析 Samsung M14 dumpsys batterystats 流程

第 1 階段：先確認完整檔案範圍

先不要分析原因，也不要做健康度推論。

請完整讀取我上傳的 dumpsys batterystats 檔案，先確認以下資料：

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



重要要求

請確認這些數字是從整份檔案的 summary/statistics取得，而不是只分析 Battery History 開頭幾分鐘。

如果 Battery History 開頭只有幾分鐘，但 summary 顯示數十小時，請以 summary 的完整統計期間為準。

請先只輸出：

統計開始時間

統計結束時間

總統計時間

Screen-on/off

Discharge

Doze

Cellular

Wi-Fi

Battery capacity


此階段不要分析原因，也不要估算 SOH。


---

第 2 階段：分析夜間待機是否正常

確認第 1 階段資料後，再分析：

A. 待機

計算：

Screen-off discharge / Screen-off time

以及：

Deep Doze discharge

判斷：

螢幕關閉後是否能正常進入 Doze

是否存在長時間無法進入 idle 的情況

Full idle 占總電池時間比例

最長一次 idle 多久


B. 行動網路

確認：

Mobile active
Mobile active 5G
Cellular kernel active
Cellular Rx
Cellular Tx
Cellular estimated power

我的手機目前沒有 SIM 卡。

請不要因為看到 telephony-radio 就直接判定行動網路造成耗電。

只有在有 Mobile active、Cellular active、Rx/Tx 或其他明確證據時，才判斷其影響。

C. Wi-Fi

分析：

WiFi kernel active
WiFi Sleep
WiFi Idle
WiFi Rx
WiFi Tx
WiFi Scan
WiFi estimated power

請區分：

> Wi-Fi kernel active



與：

> 實際 Wi-Fi Rx/Tx 活動



不要把兩者直接等同。


---

第 3 階段：分析 Battery History 的喚醒時間軸

這是最重要的部分。

請從整份 Battery History 搜尋：

wlan_mbox_irq
wifi_radio
wifi-data
GCM
FCM
com.google.android.gms
Google Play Services
telephony-radio
wakelock
wake_reason
alarm
job
+running
-running

不要只統計出現次數

我要你分析時間上的前後關係。

對每一個重要的：

wlan_mbox_irq

請盡可能建立：

時間 T0
↓
Wake reason
↓
Wi-Fi 狀態
↓
Wakelock
↓
GCM / FCM / GMS
↓
Telephony
↓
App / Job / Alarm
↓
CPU / running
↓
Wi-Fi inactive
↓
重新進入 idle


---

第 4 階段：建立「喚醒事件案例」

不要把所有事件混成一團。

請挑出至少 10 個具有代表性的 WLAN wakeup，建立表格：

編號	時間	Wake reason	WLAN	GMS/FCM	Wakelock	App/Job	持續時間	結果

1								
2								
3								


每一個案例都要回答：

1. wlan_mbox_irq 是否真的造成 wakeup？


2. 喚醒後 Wi-Fi 是否變成 active？


3. GMS / FCM 是否在附近時間出現？


4. 是否出現 wakelock？


5. 是否有 App、Job 或 Alarm 接手？


6. 系統維持 awake 多久？


7. 最後是否回到 -running / idle？


8. 是否有明顯耗電跡象？




---

第 5 階段：區分「喚醒」與「耗電」

請特別注意：

> 一次 wakeup ≠ 一次明顯耗電。



請把事件分類成：

A 類：短暫正常喚醒

例如：

wlan_mbox_irq
↓
短暫 activity
↓
很快回到 idle

B 類：App 接手

例如：

wlan_mbox_irq
↓
GCM / FCM
↓
GMS
↓
wakelock
↓
CPU activity

C 類：疑似異常

例如：

wlan_mbox_irq
↓
wakelock
↓
長時間 running
↓
沒有回到 idle

請明確統計三種類型的數量。


---

第 6 階段：找出真正的「喚醒鏈」

最後請回答：

> 在這份 M14、無 SIM、Wi-Fi 開啟的 batterystats 中，最常見的 WLAN 喚醒模式是什麼？



請按照：

Wake reason
      ↓
Wi-Fi
      ↓
GMS / FCM
      ↓
Wakelock / Job / Alarm
      ↓
App
      ↓
CPU activity
      ↓
回到 idle

判斷誰是：

① 喚醒來源

② 喚醒後的活動來源

③ 真正延長 awake 時間的來源

④ 最終造成耗電的來源

不要把這四者混為同一個東西。


---

第 7 階段：電池健康度

最後才分析：

Estimated battery capacity
Last learned battery capacity
Min learned battery capacity
Max learned battery capacity

請不要使用：

單一電壓
+
當下 charge

直接反推 SOH。

尤其不要使用：

4.228V → 假定 80% SOC
3771mAh ÷ 80%

來計算電池健康度。

請分別回答：

1. Estimated capacity 是多少？


2. Learned capacity 是多少？


3. Estimated / Learned 比例是多少？


4. 這個比例是否可以直接稱為 SOH？


5. batterystats 是否有足夠資料判斷實際電池健康度？



如果不能，請明確說「無法從這份資料精確判斷」，不要自行補假設。


---

最終報告格式

最後請按照以下順序輸出：

1. 資料完整性

RESET

統計期間

是否完整讀取 summary

是否完整讀取 Battery History


2. 夜間待機

Screen-off

Discharge

Full idle

Deep Doze

是否正常


3. Cellular

Mobile active

Cellular kernel

Rx / Tx

是否是主要耗電來源


4. Wi-Fi

Wi-Fi activity

Rx / Tx

Scan

Estimated power

是否是主要耗電來源


5. WLAN Wakeup

列出至少 10 個代表性：

wlan_mbox_irq

事件。

6. GMS / FCM

判斷哪些 WLAN wakeup 後有：

GCM
FCM
Google Play Services

7. Wakelock

判斷哪些事件真的延長 awake 時間。

8. 異常判斷

分成：

正常

值得注意

疑似異常

無法從目前資料判斷


9. 電池容量

分析：

Estimated capacity
Learned capacity

不要用單一電壓反推 SOH。

10. 最終結論

請用一句話回答：

> 這台 Samsung M14 無 SIM 卡，在這段統計期間是否存在異常夜間待機耗電？如果有，最可能是哪一條喚醒鏈？




---

我特別建議你這樣測 Gemini

不要一次把上面全部貼給它。

先貼「第 1 階段」，看它能不能正確讀完整 summary。

如果正確，再貼「第 3～4 階段」，測它能不能真正處理 Battery History 的時間因果關係。

這樣你就能分辨 Gemini 到底是：

> 能讀大檔 → 能抓摘要 → 能找事件 → 能建立時間軸 → 能做因果分析



還是只能做到前兩步。

而以你這份 M14 batterystats 來說，真正有鑑別力的測試不是再叫它列一次 20 個統計數字，而是讓它找 wlan_mbox_irq 前後的事件鏈。
