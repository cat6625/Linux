##adb常用指令

**内存(pss)占用前 25 名**
```js
adb shell dumpsys meminfo | sed -n '/Total PSS by process:/,$p' | grep -E "^ +[0-9,]+K: .*\(pid [0-9]+\)" | head -n 25
```
