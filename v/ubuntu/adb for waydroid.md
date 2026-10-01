
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


---

在 Ubuntu 上透過無線網路（Wi-Fi） 使用 ADB 連接手機，可以讓你擺脫傳輸線的限制。
根據你的 Android 手機系統版本（Android 11 以上 或 Android 10 以下），操作步驟會有所不同。Android 11 之後的系統支援直接在手機上配對，完全不需要用到傳輸線。
以下為你整理兩種版本的操作指南：
------------------------------
## 方法一：Android 11（含）以上系統（最推薦，免傳輸線）
如果你的手機是 Android 11、12、13、14 或更新的版本，請確保電腦和手機連接在同一個 Wi-Fi 網路下，然後依照以下步驟操作：
## 1. 手機端開啟「無線偵錯」

   1. 進入手機的 「設定」 > 「開發者選項」。
   2. 找到 「無線偵錯（Wireless debugging）」 並將其開啟。
   3. 點擊進入「無線偵錯」設定畫面，你會看到手機的 IP 位址和通訊埠（例如：192.168.1.100:34567）。
   4. 點擊 「使用配對碼配對裝置」，畫面上會顯示：
   * Wi-Fi 配對碼（6 位數字，例如：123456）
      * IP 位址和通訊埠（注意：這個通訊埠跟步驟 3 的不同，例如：192.168.1.100:45678）
   
## 2. Ubuntu 終端機連線步驟
打開 Ubuntu 終端機，依序輸入以下指令：
步驟 A：配對裝置（只需做一次）
輸入剛剛在手機上看到「配對碼畫面」的 IP 與通訊埠：

adb pair 192.168.1.100:45678

終端機會提示你輸入配對碼，請輸入剛剛那 6 位數字：

Enter pairing code: 123456

成功後會顯示 Successfully paired to...。
步驟 B：正式連線
配對成功後，請退回到手機「無線偵錯」的主畫面，查看最上方的 IP 位址和通訊埠（例如步驟 3 的 34567），然後輸入：

adb connect 192.168.1.100:34567

看到顯示 connected to... 就代表大功告成！你可以輸入 adb devices 來確認。
------------------------------
## 方法二：Android 10（含）以下舊系統（首次需插線）
如果手機系統較舊，第一次設定時仍需要使用 USB 傳輸線。請確保電腦和手機連接同一個 Wi-Fi：

   1. 插上 USB 傳輸線連接手機與 Ubuntu 電腦。
   2. 開啟終端機，將 ADB 的切換為網路監聽模式（預設埠號為 5555）：
   
   adb tcpip 5555
   
   3. 查詢手機的 Wi-Fi IP 位址（可以到手機的「設定 > 關於手機 > 狀態資訊 > IP 位址」查看，例如 192.168.1.100）。
   4. 拔掉 USB 傳輸線。
   5. 在 Ubuntu 終端機輸入連線指令：
   
   adb connect 192.168.1.100:5555
   
   6. 驗證連線是否成功：
   
   adb devices
   
   
(注意：如果手機重開機，舊系統通常需要重新插線執行一次 adb tcpip 5555 才能再次無線連線。)
------------------------------
## 斷開無線連線
不使用時，如果你想斷開無線連線，可以在 Ubuntu 終端機輸入：

adb disconnect

。




