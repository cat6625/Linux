
**關鍵字**
'TV-category|TV-home|TV-detail|TV-search|TV-vg3|libvio|PoW|pow_debug|pageOK|stillChallenge|QuickJS|Spider|csp_|com.fongmi'

**adb for waydroid**
```txt
echo "logcat -c" | sudo waydroid shell && sudo waydroid shell -- logcat -v time | grep --line-buffered -iE \
'TV-quickjs|框架診斷|PoW偵測' \
| tee fongmi.txt
```
**aShell 的寫法**
```txt
logcat -v time | grep -E 'TV-quickjs|框架診斷|PoW偵測' | tee -a /sdcard/Download/fongmi.txt
```
**ubuntu 的寫法**
```txt
adb shell logcat -v time | grep --line-buffered -iE 'TV-quickjs|框架診斷|PoW偵測' | tee -a fongmi-u.txt
```

---

## 指令詳細拆解：它幫你做了什麼？

   1. adb logcat -v time
   * adb logcat：開始擷取 Android 手機的系統日誌。
      * -v time：將日誌格式設定為包含時間戳記（時:分:秒.毫秒），方便你追蹤事件發生的精確時間。
   2. | (管線 / Pipe)
   * 將前一個指令輸出的日誌，即時傳送給下一個指令處理。
   3. grep --line-buffered -iE '...'
   * --line-buffered：這是最關鍵的參數。強制 grep 每偵測到新的一行日誌就立刻吐出來，而不會把資料卡在快取區（Buffer）裡。這樣你才能「即時」在螢幕上看到重新整理的 log。
      * -i：忽略大小寫（例如：libvio、LibVio、LIBVIO 都會被抓到）。
      * -E：啟用延伸正則表達式（Extended Regex），這樣才能使用 |（代表「或 / OR」）來同時搜尋多個關鍵字。
      * 'libvio|PoW|Challenge|QuickJS|Spider'：你要篩選的 5 個特定關鍵字。
   4. | tee fongmi.txt
   * tee 指令就像一個水管的 T 型接頭。它會同時把過濾後的日誌「顯示在畫面上」，並且「寫入（儲存）到 fongmi.txt 檔案中」。
   
------------------------------
## 💡 執行時的實用小技巧

* 如何停止擷取？
當你想結束擷取時，請在終端機按下 Ctrl + C 即可停止。
* 檔案存哪裡去了？
fongmi.txt 會儲存在你目前終端機所在的工作目錄（預設通常是主資料夾 /home/你的帳號/）。你可以輸入 pwd 查看當前路徑。
* 想「追加」日誌而不是「覆蓋」？
如果之後想再次執行，且不想洗掉舊的 fongmi.txt 內容，請在 tee 後面加上 -a 參數（Append）：


---


## 在 Ubuntu 上透過無線網路（Wi-Fi） 使用 ADB 連接手機，可以讓你擺脫傳輸線的限制。

**Android 10（含）以下舊系統（首次需插線）**
如果手機系統較舊，第一次設定時仍需要使用 USB 傳輸線。請確保電腦和手機連接同一個 Wi-Fi：

   1. 插上 USB 傳輸線連接手機與 Ubuntu 電腦。
   2. 開啟終端機，將 ADB 的切換為網路監聽模式（預設埠號為 5555）：
   ```txt
   adb tcpip 5555
   ```
   
   3. 查詢手機的 Wi-Fi IP 位址（可以到手機的「設定 > 關於手機 > 狀態資訊 > IP 位址」查看，例如 192.168.1.100）。
   4. 拔掉 USB 傳輸線。
   5. 在 Ubuntu 終端機輸入連線指令：
   ```txt
   adb connect 192.168.1.100:5555
   ```
   6. 驗證連線是否成功：
   ```txt
   adb devices
   ```
   
(注意：如果手機重開機，舊系統通常需要重新插線執行一次 adb tcpip 5555 才能再次無線連線。)
------------------------------
## 斷開無線連線
不使用時，如果你想斷開無線連線，可以在 Ubuntu 終端機輸入：
  ```txt
  adb disconnect
  ```
---

## Termux

**下載**
https://play.google.com/store/apps/details?id=com.termux

**安裝套件**
```txt
pkg update && pkg install android-tools
```

**連接**
```txt
adb tcpip 5555
```
```txt
adb connect 192.168.1.188:5555
```



```txt
adb -s 192.168.1.188:5555 shell
```


```txt
adb -s emulator-5554 shell
```

```txt
logcat -v time | grep -E 'TV-quickjs|框架診斷|PoW偵測' | tee -a /sdcard/Download/fongmi.txt
'''
