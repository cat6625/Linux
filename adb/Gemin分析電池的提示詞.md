可以。下面我整理成一份可以直接存成 Android_Gemini_BatteryStats_分析流程.md 的版本。重點是以**手機端操作 Gemini + dumpsys batterystats**為主，並採用「先完整摘要 → 再時間軸 → 最後因果分析」的流程。

# Android 手機使用 Gemini 分析 dumpsys batterystats 流程

適用於：

- Samsung Galaxy M14 / Android 手機
- Android 15
- 使用 ADB、aShell、Shizuku 等方式取得 `dumpsys batterystats`
- 分析夜間待機耗電
- 分析 Doze / Deep Sleep
- 分析 Wi-Fi 喚醒
- 分析 Wakelock
- 分析 GMS / GCM / FCM
- 分析 Telephony / Cellular
- 評估電池容量
- 找出「誰把系統叫醒、誰讓系統繼續醒著」

---

# 一、整體分析原則

不要一開始就把大型 `dumpsys batterystats` 拆成大量關鍵字。

推薦使用：

```text
完整檔案
   ↓
第一階段：確認完整統計範圍
   ↓
第二階段：分析總體耗電
   ↓
第三階段：分析 Battery History
   ↓
第四階段：建立喚醒時間軸
   ↓
第五階段：分析 GMS / FCM / Wakelock
   ↓
第六階段：判斷真正耗電來源
   ↓
第七階段：分析電池容量

核心原則：

> 先確認 Gemini 有沒有讀完整檔案，再讓它分析事件因果關係。




---

二、Android 手機取得 batterystats

方式 A：直接取得完整檔案

使用 ADB：

adb shell dumpsys batterystats > batterystats.txt

如果手機端使用 aShell：

dumpsys batterystats > /sdcard/batterystats.txt

再把檔案傳到可以上傳給 Gemini 的位置。


---

三、不要先用 grep 把原始資料破壞

不建議一開始只做：

dumpsys batterystats | grep wlan_mbox_irq

也不建議一開始把：

GCM
FCM
Wi-Fi
wakelock
telephony

全部拆成完全獨立的小檔。

原因：

wlan_mbox_irq
      ↓
Wi-Fi
      ↓
GCM / FCM
      ↓
Wakelock
      ↓
App
      ↓
回到 Idle

這些事件的價值在於「時間關係」。

如果完全拆開，Gemini 可能失去因果關係。


---

四、第一階段：先測試 Gemini 是否完整讀取檔案

將完整 dumpsys batterystats 上傳給 Gemini。

不要一開始要求它找原因。

先輸入：


---

Gemini 提示詞 1：完整性檢查

請完整讀取我上傳的 dumpsys batterystats 檔案。

現在不要分析耗電原因，也不要推測。

請只確認整份檔案的統計範圍與 summary。

請找出：

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
16. Cellular Rx
17. Cellular Tx
18. WiFi kernel active
19. WiFi Sleep
20. WiFi Idle
21. WiFi Rx
22. WiFi Tx
23. WiFi Scan
24. WiFi estimated power
25. Estimated battery capacity
26. Last learned battery capacity
27. Min learned battery capacity
28. Max learned battery capacity

非常重要：

請以整份檔案的 summary/statistics 為準。

不要把 Battery History 開頭的幾分鐘誤認為整份檔案的統計期間。

如果 History 開頭只有幾分鐘，但 summary 顯示數十小時，請明確指出兩者差異。

這一步只做「資料完整性確認」，不要分析原因。


---

五、第一階段通過標準

Gemini 應該能回答類似：

RESET: 2026-08-13 09:04:52
Time on battery: 23h36m
Screen off: 20h08m
Screen on: 3h27m
Discharge: 1184mAh
Full idle: 15h24m
Mobile active: 0ms
Cellular kernel active: 0ms
Estimated capacity: 5830mAh
Learned capacity: 6000mAh

如果 Gemini 又回答：

整份檔案只有 4 分鐘

但是 summary 明明有：

23h36m

代表它沒有正確理解整份檔案。

此時不要進入後續分析。


---

六、第二階段：分析整體夜間待機

如果第一階段正確，再輸入：

Gemini 提示詞 2：夜間待機

現在進行第二階段分析。

請根據上一階段確認的完整 summary，分析這台 Android 手機的待機狀態。

請分析：

1. Screen-off 總時間
2. Screen-off discharge
3. 每小時 Screen-off 平均耗電
4. Device full idling
5. Idle mode full time
6. 最長一次 idle
7. Deep Doze discharge
8. Light Doze discharge
9. 是否能正常進入 Deep Doze
10. 是否存在長時間無法進入 idle 的證據

請特別回答：

「這台手機在螢幕關閉期間是否存在明顯異常待機耗電？」

不要只根據單一事件下結論。


---

七、第三階段：分析 Cellular

如果手機沒有 SIM：

Gemini 提示詞 3

我的 Android 手機目前沒有 SIM 卡。

請分析 batterystats 中的 Cellular / Mobile 數據：

1. Mobile active
2. Mobile active 5G
3. Cellular kernel active
4. Cellular Sleep
5. Cellular Idle
6. Cellular Rx
7. Cellular Tx
8. Cellular estimated power

請判斷：

「行動網路是否是這段統計期間的主要耗電來源？」

注意：

不要因為 Battery History 出現 telephony-radio 就直接判定行動網路造成耗電。

請區分：

telephony-radio 事件

與

實際 Mobile active / Cellular activity。


---

八、第四階段：分析 Wi-Fi

Gemini 提示詞 4

請分析 batterystats 中的 Wi-Fi 數據：

1. Wifi kernel active
2. WiFi Sleep
3. WiFi Idle
4. WiFi Rx
5. WiFi Tx
6. WiFi Scan
7. WiFi estimated power
8. Wi-Fi traffic

請特別區分：

「WiFi kernel active」

與

「實際 WiFi Rx / Tx」。

不要把 WiFi kernel active 直接等同於 Wi-Fi 大量傳輸或大量耗電。

最後回答：

「Wi-Fi 是否是這段統計期間的主要耗電來源？」

請提供數據依據。


---

九、第五階段：開始分析 Battery History

這是最重要的階段。

Gemini 提示詞 5

現在開始分析完整 Battery History。

不要只統計關鍵字出現次數。

我要分析的是「時間上的事件關係」。

請從完整 Battery History 搜尋：

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

請找出 wlan_mbox_irq 發生的時間。

對每個重要 WLAN wakeup，查看前後時間的相關事件。

請保留事件的原始時間順序。


---

十、第六階段：建立 WLAN 喚醒案例

Gemini 提示詞 6

請從完整 Battery History 中選出至少 10 個具有代表性的 wlan_mbox_irq 喚醒事件。

每個事件請建立以下表格：

| 編號 | 時間 | Wake reason | Wi-Fi 狀態 | GMS/FCM | Wakelock | App/Job/Alarm | Awake 持續時間 | 是否回到 Idle |
|---|---|---|---|---|---|---|---|---|

請不要只列出 wlan_mbox_irq 本身。

我要看到它前後幾秒或幾個事件的時間關係。

對每個案例回答：

1. 是否真的發生系統喚醒？
2. Wi-Fi 是否變成 active？
3. GMS 是否在附近時間活動？
4. GCM / FCM 是否出現？
5. 是否出現 wakelock？
6. 是否有 App、Job 或 Alarm 接手？
7. 系統維持 awake 多久？
8. 最後是否重新進入 idle？


---

十一、第七階段：分析 GMS / FCM

Gemini 提示詞 7

現在專門分析 Google Play Services / GMS / GCM / FCM。

請找出 wlan_mbox_irq 後附近時間是否出現：

GCM
FCM
GCM_READ
GCM_WORK
com.google.android.gms
Google Play Services

請把相關事件按照時間排列。

重要：

不要直接把：

wlan_mbox_irq

與

GCM

的同時出現判定為因果關係。

請區分：

1. 只是時間重疊
2. WLAN wakeup 後 GMS 接著活動
3. 有明確 wakelock / running activity
4. 無法判斷因果關係

最後統計不同類型的事件。


---

十二、第八階段：分析 Wakelock

Gemini 提示詞 8

現在分析 Battery History 中的 wakelock。

請找出：

1. Partial wakelock
2. Wi-Fi wakelock
3. hip4_wake_lock_data
4. hip4_wake_lock_tx
5. 其他與 wlan_mbox_irq 附近出現的 wake lock

請回答：

哪些 wakelock 只是短暫存在？

哪些 wakelock 可能讓系統保持 awake？

哪些事件最後仍然成功回到 idle？

不要因為看到 wakelock 就直接判定異常。


---

十三、第九階段：區分「喚醒」和「耗電」

Gemini 提示詞 9

請把 WLAN 喚醒事件分成三類：

A 類：正常短暫喚醒

例如：

wlan_mbox_irq
↓
短暫活動
↓
很快回到 idle


B 類：App / GMS 接手

例如：

wlan_mbox_irq
↓
GMS / GCM / FCM
↓
wakelock
↓
CPU activity
↓
一段時間後回到 idle


C 類：疑似異常

例如：

wlan_mbox_irq
↓
wakelock
↓
長時間 running
↓
長時間沒有回到 idle

請統計每一類的代表性案例。

特別注意：

「Wakeup 次數多」

不等於

「耗電一定很多」。

請以持續時間、CPU activity、wakelock、Wi-Fi activity 和最終回到 idle 的情況綜合判斷。


---

十四、第十階段：建立真正的「喚醒鏈」

Gemini 提示詞 10

請根據完整 Battery History 建立最常見的 WLAN 喚醒鏈。

請嘗試按照以下結構：

Wake reason
↓
WLAN / Wi-Fi
↓
GMS / GCM / FCM
↓
Wakelock / Job / Alarm
↓
App
↓
CPU / running
↓
回到 idle

請分別指出：

① 誰是喚醒來源？
② 誰是喚醒後活動來源？
③ 誰讓系統保持 awake？
④ 誰可能造成實際耗電？

不要把這四個角色混為同一個來源。

如果資料不足以建立因果關係，請明確標記：

「無法由 batterystats 證明因果關係」。


---

十五、第十一階段：分析電池容量

Gemini 提示詞 11

最後才分析電池容量。

請使用：

Estimated battery capacity
Last learned battery capacity
Min learned battery capacity
Max learned battery capacity

分析目前 batterystats 對電池容量的估算。

請計算：

Estimated capacity / Last learned capacity

但不要直接把這個比例稱為實際 SOH。

重要：

不要使用：

單一電壓
+
當下 charge

直接反推出電池健康度。

例如不要使用：

4.228V → 假設 80% SOC
3771mAh ÷ 80%
→ 推算滿容量
→ 再推算 SOH

因為這種方法沒有足夠資料支持。

請明確區分：

1. batterystats 的 Estimated capacity
2. learned capacity
3. 真正的電池 SOH
4. 是否需要其他測試才能確認實際容量


---

十六、第十二階段：最終報告

Gemini 提示詞 12

現在整合前面所有分析，產生最終報告。

請按照以下結構：

# 1. 資料完整性

- RESET
- 統計期間
- 是否完整讀取 summary
- 是否完整讀取 Battery History

# 2. 夜間待機

- Screen-off
- Screen-off discharge
- Full idle
- Deep Doze
- 最長 idle
- 是否正常

# 3. Cellular

- Mobile active
- Cellular kernel
- Rx / Tx
- 是否為主要耗電來源

# 4. Wi-Fi

- Wi-Fi activity
- Rx / Tx
- Scan
- Estimated power
- 是否為主要耗電來源

# 5. WLAN Wakeup

列出至少 10 個代表性 wlan_mbox_irq 事件。

# 6. GMS / FCM

分析哪些 WLAN wakeup 附近出現 GMS / GCM / FCM。

# 7. Wakelock

分析哪些事件真正延長 awake 時間。

# 8. 異常判斷

分成：

- 正常
- 值得注意
- 疑似異常
- 無法判斷

# 9. 電池容量

分析：

Estimated capacity
Learned capacity

不要用單一電壓反推 SOH。

# 10. 最終結論

請直接回答：

「這台 Android 手機在這段統計期間是否存在異常待機耗電？」

如果有：

「最可能是哪一條喚醒鏈？」

如果沒有：

「哪些資料支持待機正常？」

請區分：

「資料直接證明」

「高度可能」

「合理推測」

「無法判斷」


---

十七、如果 Gemini 無法處理完整 History

如果 Gemini 在分析完整 Battery History 時開始出現：

漏掉大量事件

時間順序錯亂

把幾分鐘當成整份資料

只分析檔案開頭

找不到明明存在的關鍵字

無法建立事件前後關係


這時才進行第二種方法：局部切片。


---

切片原則

不要單純：

wlan.txt
gcm.txt
wakelock.txt

而是以事件時間切片。

例如：

WLAN Event 001
WLAN Event 002
WLAN Event 003
...

每個事件保留：

wlan_mbox_irq
前後數秒/數十秒
Wi-Fi
GMS
GCM
FCM
wakelock
alarm
job
running

這樣仍然保留時間因果關係。


---

十八、最簡單的手機端流程

如果不想做複雜處理，可以直接照這個順序：

① Android 手機取得 batterystats
        ↓
② 上傳完整檔案給 Gemini
        ↓
③ 提示詞 1：確認完整統計範圍
        ↓
④ 提示詞 2：分析夜間待機
        ↓
⑤ 提示詞 3：分析 Cellular
        ↓
⑥ 提示詞 4：分析 Wi-Fi
        ↓
⑦ 提示詞 5：分析 Battery History
        ↓
⑧ 提示詞 6：找 10 個 wlan_mbox_irq
        ↓
⑨ 提示詞 7：分析 GMS / FCM
        ↓
⑩ 提示詞 8：分析 Wakelock
        ↓
⑪ 提示詞 9：區分喚醒與耗電
        ↓
⑫ 提示詞 10：建立完整喚醒鏈
        ↓
⑬ 提示詞 11：分析電池容量
        ↓
⑭ 提示詞 12：最終報告


---

十九、最重要的判斷原則

不要看到事件就直接判定原因

錯誤：

wlan_mbox_irq
→ Wi-Fi 耗電

錯誤：

GCM
→ Google Play Services 耗電

錯誤：

telephony-radio
→ 行動網路耗電

錯誤：

wakelock
→ App 異常


---

正確方式

必須分析：

事件
+
時間
+
持續時間
+
CPU
+
Wakelock
+
Wi-Fi
+
GMS / FCM
+
Doze
+
電池放電

最後才能判斷。


---

二十、最終分析目標

真正想找的不是：

> 「哪個關鍵字出現最多？」



而是：

誰把手機叫醒？
        ↓
誰讓 Wi-Fi 活動？
        ↓
誰取得 wakelock？
        ↓
誰執行 CPU？
        ↓
維持多久？
        ↓
是否真的增加耗電？
        ↓
最後有沒有重新進入 Deep Doze？

最終要得到：

Wake source
      ↓
Activity source
      ↓
Wakelock holder
      ↓
CPU / App
      ↓
Duration
      ↓
Battery impact
      ↓
Return to Doze

這才是 dumpsys batterystats 真正有價值的分析方式。

**建議你實際使用時，先只把「第 1 階段」貼給 Gemini。**它確認 `23h36m`、`20h08m`、`15h24m` 等完整統計後，再進第 2 階段。這樣可以很清楚測試 Gemini 是不是「真的讀完整大檔」，而不是只讀到檔案前面的一小段。
