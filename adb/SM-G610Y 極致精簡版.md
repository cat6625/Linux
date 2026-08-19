
# SM-G610Y 極致精簡版 只能 adb uninstall

## 第一批：

```text
for pkg in com.google.android.youtube com.google.android.apps.maps com.google.android.apps.docs com.google.android.videos com.google.android.talk com.google.android.feedback ; do adb shell pm uninstall --user 0 "$pkg"; done
```


> com.google.android.youtube：YouTube 主程式。<br>
> com.google.android.apps.maps：Google 地圖（Google Maps）。<br>
> com.google.android.apps.docs：Google 雲端硬碟（Google Drive）。<br>
> com.google.android.videos：Google TV（舊稱 Google Play 電影）。<br>
> com.google.android.talk：Google Meet（舊稱 Google Hangouts / Chat）。<br>
> com.google.android.feedback：Google 意見回饋服務（用於向 Google 回報系統錯誤的背景組件）。<br>
> Google 地圖（Maps）：這是非常高頻率使用的導航與店家查詢工具，若移除會造成生活不便，建議從清單中刪除它再執行。<br>


