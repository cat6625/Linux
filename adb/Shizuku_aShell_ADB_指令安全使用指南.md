# Shizuku + aShell：ADB 指令安全使用指南

> **適用環境：Android + Shizuku + aShell**
>
> 本文件整理常見 ADB / Android Shell 指令的安全程度、用途與使用注意事項，方便在執行網路上的指令前快速判斷風險。

---

## 目錄

1. [Shizuku 與 aShell 是什麼](#shizuku-與-ashell-是什麼)
2. [基本安全原則](#基本安全原則)
3. [🟢 基本安全：查詢類指令](#-基本安全查詢類指令)
4. [🟡 謹慎使用：修改類指令](#-謹慎使用修改類指令)
5. [🔴 高風險：不要隨便執行](#-高風險不要隨便執行)
6. [☠️ 特別危險的指令](#️-特別危險的指令)
7. [系統 App 操作注意事項](#系統-app-操作注意事項)
8. [使用網路上的 ADB 指令前](#使用網路上的-adb-指令前)
9. [Shizuku 權限建議](#shizuku-權限建議)
10. [快速判斷表](#快速判斷表)
11. [最重要的一條規則](#最重要的一條規則)
12. [Disclaimer](#disclaimer)

---

## Shizuku 與 aShell 是什麼

### Shizuku

Shizuku 是 Android 上的權限服務，可以讓其他 App 在不 Root 的情況下，透過 ADB 等方式取得部分較高權限的系統 API。

**Shizuku 本身並不是 Root。**

真正需要注意的是：

> **授權給 Shizuku 的 App，可以利用 Shizuku 執行什麼操作。**

因此，不應該看到 App 要求 Shizuku 權限就直接全部允許。

### aShell

aShell 是一個可以透過 Android Shell / ADB 指令操作手機的工具。

當 aShell 被授權使用 Shizuku 後，它可以執行一些普通 App 無法執行的系統操作。

因此請記住：

- aShell 本身是工具，不代表它會自動修改手機。
- 真正的風險主要來自「**執行了什麼指令**」。
- 不理解用途的指令，不要直接貼上執行。

---

## 基本安全原則

可以記住以下規則：

| 類型 | 基本判斷 |
|---|---|
| 🟢 查詢 | 通常安全 |
| 🟡 修改 | 先確認用途 |
| 🔴 停用 / 移除系統 App | 一定先確認 |
| ☠️ 修改系統檔案 / 低階操作 | 不要隨便執行 |

尤其不要因為網路文章寫著：

> 「這個 ADB 指令可以讓手機更省電 / 更快 / 更順」

就直接整串貼進 aShell。

不同手機品牌、Android 版本與系統 ROM，可能有不同結果。

---

## 🟢 基本安全：查詢類指令

以下指令主要用於**查看資訊**，一般不會修改系統。

### 查看 Android 系統屬性

```sh
getprop
```

查看 Android 系統的各種 Property。

### 查看 Android 版本

```sh
getprop ro.build.version.release
```

### 查看螢幕解析度

```sh
wm size
```

### 查看螢幕 DPI

```sh
wm density
```

### 列出所有已安裝套件

```sh
pm list packages
```

### 只列出第三方 App

```sh
pm list packages -3
```

這個指令在處理系統 App 時非常有用。

### 查看電池資訊

```sh
dumpsys battery
```

可以查看例如：

- 電池容量狀態
- 目前電量
- 充電狀態
- 電池溫度
- 電池健康相關資訊（視裝置而定）

### 查看記憶體資訊

```sh
dumpsys meminfo
```

### 查看 System Settings

```sh
settings list system
```

這個指令主要是「查看」，不會直接修改設定。

### 查看 Secure Settings

```sh
settings list secure
```

### 查看 Global Settings

```sh
settings list global
```

> **注意：**
> `settings list` 是查看資料；`settings put` 則是修改資料，兩者風險不同。

---

## 🟡 謹慎使用：修改類指令

這類指令通常不會直接造成手機變磚，但執行前應該知道自己正在修改什麼。

### 修改動畫速度

例如：

```sh
settings put global window_animation_scale 0.5
settings put global transition_animation_scale 0.5
settings put global animator_duration_scale 0.5
```

`0.5` 通常代表動畫時間縮短，也就是視覺上動畫變快。

### 恢復預設值

```sh
settings put global window_animation_scale 1
settings put global transition_animation_scale 1
settings put global animator_duration_scale 1
```

### 查詢特定 App 的套件名稱

例如搜尋 YouTube：

```sh
pm list packages | grep youtube
```

這比只看 App 顯示名稱更加可靠。

處理系統 App 時：

- 一定要確認完整 package name。
- 不要看到相似名稱就直接停用或移除。

### 強制停止 App

```sh
am force-stop <package_name>
```

例如：

```sh
am force-stop com.example.app
```

這通常相當於將指定 App 強制關閉。

---

## 🔴 高風險：不要隨便執行

以下操作可能造成系統功能異常。

### `pm uninstall`

例如：

```sh
pm uninstall --user 0 <package_name>
```

這不是普通的「關閉 App」，而是可能將 App 從目前使用者移除。

如果誤操作系統元件，可能導致：

- 系統功能失效
- 設定頁面異常
- 通知異常
- 桌面 / Launcher 異常
- Google 服務異常
- 系統元件無法正常運作
- 嚴重時可能造成開機問題

**不要把系統 App 當成一般 App 隨便 uninstall。**

### `pm disable-user`

例如：

```sh
pm disable-user --user 0 <package_name>
```

這會停用指定 App。

錯誤停用以下類型的元件可能造成嚴重問題：

- System UI
- Launcher
- Settings
- Google Play Services
- 電話相關服務
- 廠商核心服務
- 系統權限管理元件

因此，不要直接照著網路上的：

> 「停用 50 / 100 個系統 App」

之類教學操作。

### `settings put secure`

例如：

```sh
settings put secure <key> <value>
```

這個指令本身不一定危險，但 `secure` 裡面包含許多重要系統設定。

如果不知道：

- `key` 是什麼
- `value` 是什麼
- 修改後會造成什麼影響
- 如何恢復

就不要執行。

### `settings put global`

例如：

```sh
settings put global <key> <value>
```

同樣需要先確認用途。

一些單純的設定，例如動畫速度，通常問題不大；但不要一次貼上一大串自己不了解的 `settings put global` 指令。

### `cmd package`

例如：

```sh
cmd package ...
```

`cmd package` 包含很多與 App 管理相關的功能。

部分操作可能會：

- 修改 App 狀態
- 修改權限
- 修改安裝狀態
- 影響系統 App

因此看到網路上的 `cmd package` 指令時，不要直接複製執行。

---

## ☠️ 特別危險的指令

看到以下類型的指令，**不清楚用途時不要執行**。

### `rm -rf`

例如：

```sh
rm -rf ...
```

這是刪除檔案 / 目錄的高風險操作。

特別是涉及：

```text
/system
/vendor
/data
```

等系統路徑時，不要隨便執行。

### `dd`

例如：

```sh
dd ...
```

`dd` 可以直接對區塊裝置或檔案進行低階資料操作。

使用錯誤可能造成資料損毀。

### `format`

例如：

```sh
format ...
```

涉及格式化操作時尤其需要小心。

### Bootloader / Fastboot 操作

例如：

```sh
reboot bootloader
```

以及：

```sh
fastboot ...
```

這類操作涉及裝置啟動流程。

如果不知道自己正在做什麼，不要隨便執行。

### 其他需要特別小心的指令

```sh
chmod ...
chown ...
mount ...
setenforce ...
restorecon ...
```

這些指令可能涉及：

- 檔案權限
- 所有者
- 掛載
- SELinux
- 系統檔案上下文

一般使用者沒有明確需求時，不建議修改。

---

## 系統 App 操作注意事項

如果目的是：

> 「讓手機更省電」

不代表應該把大量系統 App 停用。

如果目的是：

> 「刪掉沒用的系統 App」

也不要直接執行：

```sh
pm uninstall --user 0 ...
```

應該先確認：

1. App 的完整 package name
2. 它是什麼系統元件
3. 是否被其他系統功能依賴
4. 是否可以安全停用
5. 是否有恢復方法

**原則：先確認，再修改；先保留恢復方案，再動系統 App。**

---

## 使用網路上的 ADB 指令前

看到一串 ADB 指令時，可以先按照以下方式判斷。

### 🟢 可以先執行

主要是查詢：

```sh
getprop
pm list packages
dumpsys ...
wm size
wm density
settings list ...
```

### 🟡 先確認

包含：

```sh
settings put ...
am ...
cmd ...
pm ...
```

尤其是會修改系統或 App 狀態的指令。

### 🔴 先不要執行

包含：

```sh
pm uninstall ...
pm disable-user ...
```

如果目標是系統 App，更要先確認。

### ☠️ 不懂就不要碰

包含：

```sh
rm -rf ...
dd ...
format ...
fastboot ...
chmod ...
chown ...
mount ...
setenforce ...
```

---

## Shizuku 權限建議

如果平常只是偶爾使用 aShell：

- 不使用時，可以關閉 aShell 的 Shizuku 授權。
- 需要使用時，再重新開啟。

這不是因為 aShell 本身一定不安全，而是為了降低：

> **具有較高權限能力的 App 長時間保持授權**

所帶來的風險。

---

## 快速判斷表

| 操作 | 風險 | 建議 |
|---|---|---|
| `getprop` | 🟢 低 | 可以 |
| `pm list packages` | 🟢 低 | 可以 |
| `dumpsys battery` | 🟢 低 | 可以 |
| `dumpsys meminfo` | 🟢 低 | 可以 |
| `wm size` | 🟢 低 | 可以 |
| `wm density` | 🟢 低 | 可以 |
| `settings list ...` | 🟢 低 | 可以 |
| 修改動畫速度 | 🟡 低～中 | 通常可以 |
| `am force-stop` | 🟡 低～中 | 通常可以 |
| `settings put ...` | 🟡 中 | 先確認 |
| `cmd package ...` | 🟡～🔴 | 先確認 |
| `pm disable-user` | 🔴 高 | 不要亂用 |
| `pm uninstall --user 0` | 🔴 高 | 先確認 |
| `rm -rf` | ☠️ 極高 | 不要亂用 |
| `dd` | ☠️ 極高 | 不要亂用 |
| `format` | ☠️ 極高 | 不要亂用 |
| `fastboot ...` | ☠️ 極高 | 不要亂用 |

---

## 最重要的一條規則

> # **不知道指令在做什麼，就不要執行。**

如果從網路、YouTube、論壇、GitHub 或其他地方看到 ADB 指令，可以先把**完整指令**貼出來確認。

可以先判斷它屬於：

- 🟢 **可以安全執行**
- 🟡 **有副作用但可以接受**
- 🔴 **不建議執行**
- ☠️ **可能造成資料或系統損壞**

之後再決定是否執行。

---

## 一頁式安全檢查

在 aShell 貼上任何網路找到的指令前，可以快速問自己：

- [ ] 這是查詢指令，還是修改指令？
- [ ] 我知道每個參數的用途嗎？
- [ ] 它會修改 App 狀態嗎？
- [ ] 它會停用或移除系統 App 嗎？
- [ ] 它會修改 `settings` 嗎？
- [ ] 它會刪除檔案嗎？
- [ ] 它是否涉及 `/system`、`/vendor`、`/data`？
- [ ] 我知道出問題後怎麼恢復嗎？
- [ ] 我是否已確認自己的 Android 版本與手機品牌？
- [ ] 如果不確定，我是否先詢問或查證，而不是直接執行？

---

## Disclaimer

本文件提供的是一般性的 Android / ADB 安全使用建議。

不同手機品牌、Android 版本、系統 ROM 及廠商客製化，可能造成指令行為不同。

涉及：

- 系統 App 移除
- 系統 App 停用
- 系統設定修改
- 檔案系統修改
- Bootloader / Fastboot 操作

時，請先確認裝置型號、Android 版本、系統 ROM，以及是否存在可靠的恢復方法。

> **安全原則：不確定，就先不要執行。**
