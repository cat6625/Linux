
**在 Termux 掃描已安裝 App 的 APK 檔案（免 Root 最精準）**
1. 授權 Termux 讀取檔案與套件列表（若尚未執行過）：
```js
termux-setup-storage
```


2. 在 Android 裝置（透過 ADB Shell 或本地終端機）中，掃描所有使用者自行安裝的第三方 App，檢查它們是否內嵌了「穿山甲（Pangle）」廣告 SDK（網域包含 pangle.io）。
```js
adb shell 'for pkg in $(pm list packages -3 | cut -d":" -f2); do apk=$(pm path $pkg | head -n 1 | cut -d":" -f2); if unzip -p "$apk" classes*.dex 2>/dev/null | grep -q "pangle.io"; then echo "找到嫌疑 App: $pkg"; fi; done'

```
3. 連同 Split APKs 完整掃描的加強版指令
```js
adb shell 'for pkg in $(pm list packages -3 | cut -d":" -f2); do for apk in $(pm path $pkg | cut -d":" -f2); do if unzip -p "$apk" classes*.dex 2>/dev/null | grep -q "pangle.io"; then echo "找到嫌疑 App: $pkg"; break; fi; done; done'
```
