
**adb for waydroid**
```txt
echo "logcat -c" | sudo waydroid shell && sudo waydroid logcat | grep --line-buffered -i -E "uvod|QuickJS|com.fongmi" | tee fongmi.txt
```
```txt
echo "logcat -c" | sudo waydroid shell && sudo waydroid shell -- logcat -v time | grep --line-buffered -iE \
  'TV-category|TV-home|TV-detail|TV-search|TV-vg3|libvio|PoW|pow_debug|pageOK|stillChallenge|QuickJS|Spider|csp_' \
  | tee fongmi.txt
```
```txt
echo "logcat -c" | sudo waydroid shell && sudo waydroid shell -- logcat -v time | grep --line-buffered -iE \
'libvio|PoW|Challenge|QuickJS|Spider' \
| tee fongmi.txt
```
