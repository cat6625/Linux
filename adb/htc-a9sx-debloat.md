# htc-a9sx-debloat


# Google Paly Service更新會導致手機無限重啟
```text
adb devices && adb shell am force-stop com.google.android.gms
```
>進入桌面馬上在ubuntu下達指令<br>



## 斬草除根前：先備份/記錄原廠 APK 路徑

```text
adb shell pm list packages -f -s > a9sx.txt

```

> 在還沒執行 uninstall 之前，先用這行指令把所有你想動刀的套件與它們的 /system 原始路徑整合成一張清單
> 
> 
> 

## 重新注入（安裝）恢復格式

```text
adb shell pm install -r --user 0 <原廠APK的絕對路徑>

```

> 參數解析：-r 代表重新安裝並保留既有資料（Reinstall），--user 0 代表指定安裝回目前的主使用者帳戶。
> 
> 
> 

## 第一批：Google 預載影音與雲端套件（安全精簡）

```text
for pkg in com.google.android.youtube com.google.android.apps.maps com.google.android.music com.google.android.videos com.google.android.apps.docs com.google.android.apps.docs.editors.docs com.google.android.apps.photos com.google.android.calendar com.google.android.gm com.google.android.talk com.google.android.apps.tachyon ; do adb shell pm uninstall --user 0 "$pkg"; done

```

> com.google.android.youtube：YouTube 主程式。
> 
>
>
> com.google.android.apps.maps：Google 地圖
> 
>
>

> com.google.android.music：Google Play 音樂（已停用服務，純佔用空間）。
> 
> 
> 
> 
> com.google.android.videos：Google Play 電影。
> 
> 
> 
> 
> com.google.android.apps.docs：Google 雲端硬碟 (Google Drive)。
> 
> 
> 
> 
> com.google.android.apps.docs.editors.docs：Google 文件 (Google Docs)。
> 
> 
> 
> 
> com.google.android.apps.photos：Google 相簿 (Google Photos)。
> 
> 
> 
> 
> com.google.android.calendar：Google 日曆。
> 
> 
> 
> 
> com.google.android.gm：Gmail 郵件客戶端。
> 
> 
> 
> 
> com.google.android.talk：Google Hangouts / Chat。
> 
> 
> 
> 
> com.google.android.apps.tachyon：Google Duo (視訊通話工具)。
> 
> 
> 

## 第二批：第三方軟體與社群 App 本體（安全精簡）

```text
for pkg in com.facebook.katana com.facebook.orca com.instagram.android com.mobilesrepublic.appy ; do adb shell pm uninstall --user 0 "$pkg"; done

```

> com.facebook.katana：Facebook 主程式（僅移除 App 本體，保留 FB 系統服務框架）。
> 
> 
> 
> 
> com.facebook.orca：Facebook Messenger 訊息主程式。
> 
> 
> 
> 
> com.instagram.android：Instagram 社群軟體。
> 
> 
> 
> 
> com.mobilesrepublic.appy：Appy Geek 新聞閱讀器預載應用。
> 
> 
> 
> 
 

## 第三批：HTC 廢棄社交與附加服務（安全精簡）

```text
for pkg in com.htc.community com.htc.guide com.htc.sense.socialnetwork.googleplus com.htc.sense.socialnetwork.plurk com.htc.sense.socialnetwork.twitter ; do adb shell pm uninstall --user 0 "$pkg"; done

```

> com.htc.community：HTC 社群與使用者論壇應用。
> 
> 
> 
> 
> com.htc.guide：HTC 使用指南與新手教學。
> 
> 
> 
> 
> com.htc.sense.socialnetwork.googleplus：HTC Sense 整合之 Google+ 外掛（服務已終止）。
> 
> 
> 
> 
> com.htc.sense.socialnetwork.plurk：HTC Sense 整合之 Plurk 噗浪外掛（服務已終止）。
> 
> 
> 
> 
> com.htc.sense.socialnetwork.twitter：HTC Sense 整合之 Twitter 外掛（服務已終止）。
> 
> 
>
