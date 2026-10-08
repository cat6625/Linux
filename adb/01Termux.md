## Termux

**下載**
https://play.google.com/store/apps/details?id=com.termux

**安裝套件**
```txt
pkg update && pkg install android-tools
```

**無線連接**
```txt
adb tcpip 5555
```
```txt
adb connect 192.168.1.188:5555
```

**範例**
> libvio.js 除錯 （手機）
```txt
adb -s emulator-5554 shell logcat -v time | grep -E 'PoW偵測'
```
> libvio.js 除錯 無線（android TV）

```txt
adb -s 192.168.1.188:5555 shell logcat -v time | grep -E 'PoW偵測'
```

> 列出 指定 手機 emulator-5554 系統反安裝套件
```txt
for p in $(comm -13 \
  <(adb -s emulator-5554 shell pm list packages -s --user 0 | sed 's/^package://' | tr -d '\r' | sort) \
  <(adb -s emulator-5554 shell pm list packages -s -u --user 0 | sed 's/^package://' | tr -d '\r' | sort)); do
    echo "=== $p ==="
    adb -s emulator-5554 shell pm path "$p"
done


```
> 列出 指定裝置如 android tv 系統停用套件
```txt
adb -s 192.168.1.188:5555 shell pm list packages -s -d --user 0
```

---

紅米10需要使用小窗應用程式
無線調試配對

adb pair localhost:[配對連接埠]
adb connect localhost:37267

```txt
雖然連接埠號會變，但 「配對 (adb pair)」只需要成功做一次。
以後你只要發現斷線了，或隔天想再使用，步驟會變得很簡單：
1. 打開手機的 無線偵錯 畫面。
2. 直接看當下的連接埠號（例如今天變成 39871）。
3. 直接在 Termux 輸入：adb connect localhost:39871（不用再輸入配對碼）。
```
