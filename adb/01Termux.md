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
adb -s emulator-5554 shell logcat -v time | grep -E 'PoW'
```
> libvio.js 除錯 無線（android TV）

```txt
adb -s 192.168.1.188:5555 shell logcat -v time | grep -E 'PoW'
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
