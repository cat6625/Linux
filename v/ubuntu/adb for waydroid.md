
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
---

這個指令本身已經寫得非常完整且正確，它結合了 即時過濾（Grepping）、不區分大小寫（Case-insensitive）、正則表達式（Regex） 以及 同時輸出到螢幕與檔案（Teeing） 的進階技巧。
如果您要在 Ubuntu 上執行這個指令，請直接打開終端機（Terminal），並將該指令整合為一行執行（或使用反斜線換行）。以下是完整的執行方式與詳細拆解：
## 執行指令
請直接複製以下指令並在終端機貼上執行：

adb logcat -v time | grep --line-buffered -iE 'libvio|PoW|Challenge|QuickJS|Spider' | tee fongmi.txt

------------------------------
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

adb logcat -v time | grep --line-buffered -iE 'libvio|PoW|Challenge|QuickJS|Spider' | tee -a fongmi.txt

* 遇到無權限或找不到裝置？
如果執行後畫面動也不動，請先輸入 adb devices 確認裝置是否為 device 狀態。如果是 unauthorized，請記得看一眼手機螢幕並點選「允許 USB 偵錯」。



