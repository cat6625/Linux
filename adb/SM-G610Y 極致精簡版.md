
# SM-G610Y 極致精簡版 只能 adb uninstall

## 斬草除根前：先備份/記錄原廠 APK 路徑

```text
adb shell pm list packages -f
```

>在還沒執行 uninstall 之前，先用這行指令把所有你想動刀的套件與它們的 /system 原始路徑整合成一張清單<br>

## 重新注入（安裝）恢復格式

```text
adb shell pm install -r --user 0 <原廠APK的絕對路徑>
```

>參數解析：-r 代表重新安裝並保留既有資料（Reinstall），--user 0 代表指定安裝回目前的主使用者帳戶。<br>

## 第一批：

```text
for pkg in com.google.android.youtube com.google.android.apps.maps com.google.android.apps.docs com.google.android.videos com.google.android.talk com.google.android.feedback com.samsung.android.themecenter com.samsung.android.themestore com.sec.android.app.sbrowser ; do adb shell pm uninstall --user 0 "$pkg"; done
```


> com.google.android.youtube：YouTube 主程式。<br>
> com.google.android.apps.maps：Google 地圖（Google Maps）。這是非常高頻率使用的導航與店家查詢工具，若移除會造成生活不便，建議從清單中刪除它再執行。<br>
> com.google.android.apps.docs：Google 雲端硬碟（Google Drive）。<br>
> com.google.android.videos：舊稱 Google Play 電影）。<br>
> com.google.android.talk：舊稱 Google Hangouts / Chat）。<br>
> com.google.android.feedback：Google 意見回饋服務（用於向 Google 回報系統錯誤的背景組件）。<br>
> com.samsung.android.themecenter：三星主題控制中心。<br>
> com.samsung.android.themestore：三星主題商店。<br>
> com.sec.android.app.sbrowser：三星網頁瀏覽器。<br>

