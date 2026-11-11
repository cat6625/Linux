```js
# 連線檢查
adb devices

# Facebook 全家桶
adb shell pm uninstall -k --user 0 com.facebook.katana
adb shell pm uninstall -k --user 0 com.facebook.appmanager
adb shell pm uninstall -k --user 0 com.facebook.system
adb shell pm uninstall -k --user 0 com.facebook.services

# Amazon
adb shell pm uninstall -k --user 0 com.amazon.mShop.android.shopping
adb shell pm uninstall -k --user 0 com.amazon.appmanager

# 旅遊預訂
adb shell pm uninstall -k --user 0 com.booking
adb shell pm uninstall -k --user 0 com.agoda.mobile.consumer

# 其他第三方
adb shell pm uninstall -k --user 0 com.linkedin.android
adb shell pm uninstall -k --user 0 com.netflix.mediaclient
adb shell pm uninstall -k --user 0 com.spotify.music
adb shell pm uninstall -k --user 0 com.microsoft.skydrive

# 辦公
adb shell pm uninstall -k --user 0 cn.wps.moffice_eng
adb shell pm uninstall -k --user 0 cn.wps.xiaomi.abroad.lite

# 小米預裝內容與廣告服務
adb shell pm uninstall -k --user 0 com.mi.globalbrowser
adb shell pm uninstall -k --user 0 com.mi.global.bbs
adb shell pm uninstall -k --user 0 com.mi.global.shop
adb shell pm uninstall -k --user 0 com.mi.globalminusscreen
adb shell pm uninstall -k --user 0 com.miui.android.fashiongallery
adb shell pm uninstall -k --user 0 com.miui.player
adb shell pm uninstall -k --user 0 com.xiaomi.mipicks
adb shell pm uninstall -k --user 0 com.miui.msa.global
adb shell pm uninstall -k --user 0 com.miui.analytics

# Google 附加應用
adb shell pm uninstall -k --user 0 com.google.android.apps.youtube.music
adb shell pm uninstall -k --user 0 com.google.android.videos

```
