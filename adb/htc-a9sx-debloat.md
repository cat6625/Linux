## 斬草除根前：先備份/記錄原廠 APK 路徑

```text
adb shell pm list packages -f

```

> 在還沒執行 uninstall 之前，先用這行指令把所有你想動刀的套件與它們的 /system 原始路徑整合成一張清單
> 
> 
> 

## 重新注入（安裝）恢復格式

```text
adb shell pm install-existing <套件名稱>

```

> 說明：當套件僅被 --user 0 移除時，實體 APK 仍保留在 /system 中，使用此指令可直接將指定套件重新安裝回主使用者帳戶。
> 
> 
> 

## 第一批：Google 預載影音與雲端套件（安全精簡）

```text
for pkg in com.google.android.youtube com.google.android.music com.google.android.videos com.google.android.apps.docs com.google.android.apps.docs.editors.docs com.google.android.apps.photos com.google.android.calendar com.google.android.gm com.google.android.talk com.google.android.apps.tachyon ; do adb shell pm uninstall --user 0 "$pkg"; done

```

> com.google.android.youtube：YouTube 主程式。
> 
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
for pkg in com.facebook.katana com.facebook.orca com.instagram.android com.mobilesrepublic.appy com.nero.android.htc.sync com.nero.android.htc.sync.installer com.futuredial.idevicecloud ; do adb shell pm uninstall --user 0 "$pkg"; done

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
> com.nero.android.htc.sync：Nero 提供的 HTC Sync 多媒體同步工具。
> 
> 
> 
> 
> com.nero.android.htc.sync.installer：HTC Sync 安裝程式背景組件。
> 
> 
> 
> 
> com.futuredial.idevicecloud：舊版 iOS 轉移與雲端備份輔助工具。
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
