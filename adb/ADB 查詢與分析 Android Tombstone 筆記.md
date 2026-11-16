# ADB 查詢與分析 Android Tombstone 筆記

## 1. 列出與排序 Tombstone 檔案

進入 ADB Shell：
```bash
adb shell
```

列出 `/data/tombstones/` 下的所有檔案（依時間由新到舊排序，排除 `.pb` 二進位檔即可看最新紀錄）：
```bash
ls -lt /data/tombstones/
```

---

## 2. 批次查詢所有 Tombstone 對應的崩潰程式

### 方法 A：包含時間與程式名稱（推薦，已去除重複行）
```bash
grep -E "^(Timestamp|Cmdline):" /data/tombstones/tombstone_[0-9][0-9] | sort -u
```

### 方法 B：最精簡列表（只顯示檔名與進程名稱）
```bash
grep ">>>" /data/tombstones/tombstone_[0-9][0-9]
```

### 方法 C：依照時間新舊排序並印出摘要
```bash
for f in \$(ls -t /data/tombstones/tombstone_[0-9][0-9]); do echo "=== \(f ==="; grep -E "^(Timestamp\vert{}Cmdline):" "\)f" | sort -u; done
```

---

## 3. 查看單一 Tombstone 關鍵崩潰原因

查看前 35 行（包含機型、Android 版本、時間、崩潰程式、Signal 與 Abort message）：
```bash
head -n 35 /data/tombstones/tombstone_00
```

只篩選 Backtrace（函式呼叫堆疊）關鍵段落：
```bash
grep -A 30 "backtrace:" /data/tombstones/tombstone_00
```

---

## 4. 匯出檔案至電腦本地端

> **注意**：需先輸入 `exit` 離開 `adb shell`，在電腦本機終端機執行。

### 方式一：直接拉取（需具備讀取 `/data/tombstones/` 權限）
```bash
# 拉取單一檔案
adb pull /data/tombstones/tombstone_00 .

# 拉取整個資料夾
adb pull /data/tombstones/ ./tombstones_log
```

### 方式二：透過 Bugreport 取得（適用於無 Root 的一般市售機）
```bash
adb bugreport bugreport.zip
# 解壓縮後，Tombstone 檔案位於：FS/data/tombstones/
```
