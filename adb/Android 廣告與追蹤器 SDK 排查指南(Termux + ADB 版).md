
```js
adb shell 'for pkg in $(pm list packages -3 | cut -d":" -f2); do apk=$(pm path $pkg | head -n 1 | cut -d":" -f2); if unzip -p "$apk" classes*.dex 2>/dev/null | grep -q "pangle.io"; then echo "找到嫌疑 App: $pkg"; fi; done'

```
