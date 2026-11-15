測試方法 (關尋找手機，ubuntu adb wifi) 
做完 batterystats --reset後 ， ubuntu 立刻  suspend  
測試時間 完成 後 ，打開電腦 立刻紀錄 
ubuntu有時候會動喚醒，電腦自動suspend為15分


# lawnchair 桌面

# 準備工作
```js
adb shell cmd role get-role-holders android.app.role.HOME
adb shell dumpsys deviceidle unforce
adb shell dumpsys batterystats --enable full-wake-history
adb shell dumpsys batterystats --reset
adb shell dumpsys meminfo ch.deletescape.lawnchair.plah > lawnchair_mem-$(date +%Y%m%d_%H%M%S).txt
adb shell dumpsys battery >  m14_battery-$(date +%Y%m%d_%H%M%S).txt
```

# ubuntu 立刻  suspend
```js
systemctl suspend
```

# 連接 adb
```js
adb  devices
adb  connect 192.168.1.142:44055
```

# 紀錄
```js
adb shell dumpsys deviceidle >  fmm_off_adb_on_deviceidle-lawnchair.txt
adb shell dumpsys batterystats --history > fmm_off_adb_on_history-lawnchair.txt
adb shell dumpsys batterystats        > fmm_off_adb_on_full-lawnchair.txt
adb shell dumpsys batterystats --checkin > fmm_off_adb_on_checkin-lawnchair.txt
adb shell dumpsys netstats detail > fmm_off_adb_on_netstats-lawnchair.txt
journalctl -b | grep -iE "suspend|resume|sleep|PM: " > suspend.txt
adb shell dumpsys meminfo ch.deletescape.lawnchair.plah > lawnchair_mem-$(date +%Y%m%d_%H%M%S).txt
adb shell dumpsys battery >  m14_battery-$(date +%Y%m%d_%H%M%S).txt
```

# 摘要處理
```js
python3 doze_summary.py fmm_off_adb_on_full-lawnchair.txt  |  tee summary-lawnchair.txt > /dev/null
python3 doze_summary.py fmm_off_adb_on_full-lawnchair.txt --uids u0a1361,u0a125 |  tee -a summary-lawnchair.txt > /dev/null
python3 doze_summary.py fmm_off_adb_on_full-lawnchair.txt --suspend suspend.txt  |  tee -a summary-lawnchair.txt > /dev/null   # 對照電腦的睡眠時間  
python3 doze_summary.py fmm_off_adb_on_full-lawnchair.txt --deviceidle fmm_off_adb_on_deviceidle-lawnchair.txt |  tee -a summary-lawnchair.txt > /dev/null
```


---

# oneui 桌面

# 準備工作
```js
adb shell cmd role get-role-holders android.app.role.HOME
adb shell dumpsys deviceidle unforce
adb shell dumpsys batterystats --enable full-wake-history
adb shell dumpsys batterystats --reset
adb shell dumpsys meminfo com.sec.android.app.launcher > oneui_mem-$(date +%Y%m%d_%H%M%S).txt
adb shell dumpsys battery >  m14_battery-$(date +%Y%m%d_%H%M%S).txt
```

# ubuntu 立刻  suspend
```js
systemctl suspend
```

# 連接 adb
```js
adb  devices
adb  connect 192.168.1.142:44055
```

# 紀錄
```js
adb shell dumpsys deviceidle >  fmm_off_adb_on_deviceidle-oneui.txt
adb shell dumpsys batterystats --history > fmm_off_adb_on_history-oneui.txt
adb shell dumpsys batterystats        > fmm_off_adb_on_full-oneui.txt
adb shell dumpsys batterystats --checkin > fmm_off_adb_on_checkin-oneui.txt
adb shell dumpsys netstats detail > fmm_off_adb_on_netstats-oneui.txt
journalctl -b | grep -iE "suspend|resume|sleep|PM: " > suspend.txt
adb shell dumpsys meminfo com.sec.android.app.launcher > oneui_mem-$(date +%Y%m%d_%H%M%S).txt
adb shell dumpsys battery >  m14_battery-$(date +%Y%m%d_%H%M%S).txt
```


# 摘要處理
```js
python3 doze_summary.py fmm_off_adb_on_full-oneui.txt  |  tee summary-oneui.txt > /dev/null
python3 doze_summary.py fmm_off_adb_on_full-oneui.txt --uids u0a1361,u0a125 |  tee -a summary-oneui.txt > /dev/null
python3 doze_summary.py fmm_off_adb_on_full-oneui.txt --suspend suspend.txt  |  tee -a summary-oneui.txt > /dev/null   # 對照電腦的睡眠時間  
python3 doze_summary.py fmm_off_adb_on_full-oneui.txt --deviceidle fmm_off_adb_on_deviceidle-oneui.txt |  tee -a summary-oneui.txt > /dev/null
```

---

# 唯一的影響是您無法在 Island 空間內使用 Google 語音輸入或直接開啟工作版的 Google 搜尋，但這在隔離空間中通常完全用不到。
```js
adb shell dumpsys meminfo | head -n 15
adb shell pm disable-user --user 10 com.google.android.googlequicksearchbox
adb shell pm enable --user 10 com.google.android.googlequicksearchbox
```


# 查詢特定 Linux UID（使用者識別碼） 所對應的 Android 應用程式套件名稱（Package Name）。
```js
adb shell pm list packages --uid 10203
```
