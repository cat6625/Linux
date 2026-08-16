# SAMPO EM-43JTD230 ADB 除錯指令大全

> 適用機型：**SAMPO EM-43JTD230**  
> 系統版本：**Android 11**  
> SoC：**Realtek RTD2851M**
>
> 本文件整理常用的 **ADB 除錯與診斷指令**，所有輸出皆使用 `tee` 儲存至 `/sdcard/adb_debug/`，方便日後一次執行、複製與保存分析結果。

---

## 📁 0. 建立診斷資料夾

建議開始前先建立資料夾：

```bash
mkdir -p /sdcard/adb_debug
```

---

# 1. 系統資訊

### 完整系統屬性

```bash
getprop | tee /sdcard/adb_debug/getprop.txt
```

### Build 資訊

```bash
getprop | grep build | tee /sdcard/adb_debug/build.txt
```

### Realtek 資訊

```bash
getprop | grep realtek | tee /sdcard/adb_debug/realtek.txt
```

### RTK 資訊

```bash
getprop | grep rtk | tee /sdcard/adb_debug/rtk.txt
```

---

# 2. Power Manager

### Power Manager 完整資訊

```bash
dumpsys power | tee /sdcard/adb_debug/power.txt
```

### Wake 相關資訊

```bash
dumpsys power | grep Wake | tee /sdcard/adb_debug/power_wake.txt
```

---

# 3. Device Idle

```bash
dumpsys deviceidle | tee /sdcard/adb_debug/deviceidle.txt
```

---

# 4. Alarm

```bash
dumpsys alarm | tee /sdcard/adb_debug/alarm.txt
```

---

# 5. Logcat

## 完整 Logcat

```bash
logcat -d | tee /sdcard/adb_debug/logcat.txt
```

## System Log

```bash
logcat -b system -d | tee /sdcard/adb_debug/systemlog.txt
```

## Power Manager

```bash
logcat -d | grep PowerManager | tee /sdcard/adb_debug/powerlog.txt
```

## Suspend

```bash
logcat -d | grep suspend | tee /sdcard/adb_debug/suspend.txt
```

## Wake

```bash
logcat -d | grep Wake | tee /sdcard/adb_debug/wake.txt
```

## Realtek

```bash
logcat -d | grep realtek | tee /sdcard/adb_debug/realteklog.txt
```

---

# 6. Package / 套件資訊

## 所有套件

```bash
pm list packages | tee /sdcard/adb_debug/packages.txt
```

## 套件及 APK 路徑

```bash
pm list packages -f | tee /sdcard/adb_debug/packages_f.txt
```

## 已停用套件

```bash
pm list packages -d | tee /sdcard/adb_debug/disabled.txt
```

## 系統套件

```bash
pm list packages -s | tee /sdcard/adb_debug/system_packages.txt
```

## 第三方套件

```bash
pm list packages -3 | tee /sdcard/adb_debug/user_packages.txt
```

---

# 7. Realtek

## Realtek Power 套件

```bash
dumpsys package com.realtek.power | tee /sdcard/adb_debug/realtek_power.txt
```

## Realtek Power APK 路徑

```bash
pm path com.realtek.power | tee /sdcard/adb_debug/realtek_power_path.txt
```

---

# 8. 記憶體

## RAM / Memory Info

```bash
dumpsys meminfo | tee /sdcard/adb_debug/meminfo.txt
```

## Procrank

```bash
procrank | tee /sdcard/adb_debug/procrank.txt
```

---

# 9. 程序（Process）

```bash
ps -A | tee /sdcard/adb_debug/ps.txt
```

---

# 10. 磁碟空間

```bash
df | tee /sdcard/adb_debug/df.txt
```

---

# 11. Android Settings

## Global

```bash
settings list global | tee /sdcard/adb_debug/global.txt
```

## System

```bash
settings list system | tee /sdcard/adb_debug/system.txt
```

## Secure

```bash
settings list secure | tee /sdcard/adb_debug/secure.txt
```

---

# 12. 待機相關設定

### `stay_on_while_plugged_in`

```bash
settings get global stay_on_while_plugged_in | tee /sdcard/adb_debug/stay_on.txt
```

---

# 13. 可能無權限，但可留作測試

> ⚠️ 以下指令在部分 Android TV 環境可能因權限不足而無法執行。  
> 即使無法取得結果，也可以保留作為後續測試用途。

### Kernel Message

```bash
dmesg | tee /sdcard/adb_debug/dmesg.txt
```

### Tombstones

```bash
ls /data/tombstones | tee /sdcard/adb_debug/tombstones.txt
```

### Realtek RTD Log

```bash
ls -l /mnt/vendor/rtdlog | tee /sdcard/adb_debug/rtdlog.txt
```

---

# 🚨 一鍵診斷：建議優先收集

如果電視之後再次發生**待機、無法喚醒、開機異常、ADB 異常或系統穩定性問題**，建議優先執行以下指令。

```bash
mkdir -p /sdcard/adb_debug

getprop | tee /sdcard/adb_debug/getprop.txt

dumpsys power | tee /sdcard/adb_debug/power.txt

dumpsys deviceidle | tee /sdcard/adb_debug/deviceidle.txt

dumpsys alarm | tee /sdcard/adb_debug/alarm.txt

dumpsys meminfo | tee /sdcard/adb_debug/meminfo.txt

procrank | tee /sdcard/adb_debug/procrank.txt

logcat -b system -d | tee /sdcard/adb_debug/systemlog.txt

logcat -d | tee /sdcard/adb_debug/logcat.txt

pm list packages -d | tee /sdcard/adb_debug/disabled.txt

pm list packages -f | tee /sdcard/adb_debug/packages_f.txt
```

---

## 📋 一鍵診斷輸出檔案

執行完成後，主要會得到以下檔案：

| 檔案 | 用途 |
|---|---|
| `getprop.txt` | 系統與硬體屬性 |
| `power.txt` | Power Manager 狀態 |
| `deviceidle.txt` | Android 待機／Idle 狀態 |
| `alarm.txt` | Alarm / 排程資訊 |
| `meminfo.txt` | RAM 使用狀況 |
| `procrank.txt` | 程序記憶體使用狀況 |
| `systemlog.txt` | System Log |
| `logcat.txt` | 完整 Logcat |
| `disabled.txt` | 已停用套件 |
| `packages_f.txt` | 套件及 APK 路徑 |

---

## 🎯 主要用途

這套指令主要用於分析 **Realtek RTD2851M** 平台上的：

- 🔋 待機異常
- ⚡ Power Manager 問題
- 🌙 Device Idle / Suspend 問題
- 🔔 Alarm 喚醒問題
- 🔆 Wake / 喚醒異常
- 🧠 RAM / Process 使用異常
- 📦 Android Package / APK 狀態
- 📜 Logcat / System Log
- 🔧 ADB 除錯
- 🖥️ 開機與系統穩定性問題

> **建議：** 發生異常後，盡量在重新開機或再次操作之前先保留 `/sdcard/adb_debug/` 內的診斷結果，避免關鍵 Log 被覆蓋或遺失。

---
### 📌 備註

這套指令是針對 **SAMPO EM-43JTD230（Android 11／Realtek RTD2851M）** 的實際除錯需求整理而成，尤其適合後續針對**「待機後無法喚醒」**等問題進行比對與分析。