
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

---

在 Android 手機上使用 aShell（一個手機端的本地 ADB 外殼工具）執行此指令時，由於 aShell 本身就已經在 ADB 環境內，因此語法有兩個關鍵的調整：

   1. 不需要加上 adb 開頭：直接從 logcat 開始寫。
   2. 處理 Shizuku / aShell 的權限緩衝問題：有時手機端 grep 的 --line-buffered 在某些 Android 系統上支援度不佳，或者 aShell 的 UI 重新整理較慢。

以下是適合 aShell 的寫法與優化建議：
## 1. 標準寫法（最推薦）
直接在 aShell 的輸入框中貼上以下指令並執行：

logcat -v time | grep --line-buffered -iE 'libvio|PoW|Challenge|QuickJS|Spider' | tee /sdcard/Download/fongmi.txt

⚠️ 路徑非常重要：
原始指令中的 fongmi.txt 在電腦上會存到當前目錄。但在手機 aShell 內部，如果直接寫 fongmi.txt，檔案會被存在 aShell 的內部私有目錄，你用一般檔案瀏覽器會找不到。
將路徑改為 /sdcard/Download/fongmi.txt，檔案就會直接存入手機的 「下載（Download）」 資料夾，方便你後續查看或分享。

------------------------------
## 2. 進階：如果畫面上遲遲沒有出現 log（替代方案）
有時手機系統的 grep 機制會導致 tee 無法即時把文字推送到 aShell 的螢幕畫面上。如果你發現畫面卡住，請改用 logcat 自帶的過濾語法，效率更高且絕對不會卡快取：

logcat -v time | grep -iE 'libvio|PoW|Challenge|QuickJS|Spider' > /sdcard/Download/fongmi.txt

(注意：這個方法會全速把 log 寫入檔案，畫面上不會顯示任何東西。等你想結束時點擊 aShell 的停止按鈕，再用內建檔案瀏覽器去 Download 資料夾開 fongmi.txt 即可。)
------------------------------
## 💡 手機端執行的額外檢查

* 儲存權限：執行前，請確保 aShell 已經獲得檔案與媒體存取權限，否則會無法在 /sdcard/Download/ 建立文字檔（會跳出 Permission denied 錯誤）。
* 背景執行：logcat 是持續性的指令，在 aShell 中執行後，只要不按停止，它就會一直背景記錄。建議測試完特定操作後就手動停止，避免檔案過大佔用手機空間。





