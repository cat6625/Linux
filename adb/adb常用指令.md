##adb常用指令

**内存占用前 25 名**
```js
adb shell "dumpsys meminfo | grep -E '^ +[0-9,]+K: .*\(pid [0-9]+\)' | tr -d ',' | sed 's/^ *//' | sort -u | sort -k1,1 -rn | head -25"
```
