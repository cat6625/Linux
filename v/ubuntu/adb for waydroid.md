
**adb for waydroid**
```txt
echo "logcat -c" | sudo waydroid shell && sudo waydroid logcat | grep --line-buffered -i -E "uvod|QuickJS|com.fongmi" | tee fongmi.txt
```
