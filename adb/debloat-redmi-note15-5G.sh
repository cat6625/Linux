#!/bin/bash

# 連線檢查
adb devices

# Facebook 全家桶
adb shell pm uninstall -k --user 0 com.facebook.katana #Facebook
adb shell pm uninstall -k --user 0 com.facebook.appmanager #Facebook 安装器
adb shell pm uninstall -k --user 0 com.facebook.system #Facebook 系统服务 
adb shell pm uninstall -k --user 0 com.facebook.services #Facebook 服务

# Amazon
adb shell pm uninstall -k --user 0 com.amazon.mShop.android.shopping #Amazon 购物
adb shell pm uninstall -k --user 0 com.amazon.appmanager #Amazon 安装器

# 旅遊預訂
adb shell pm uninstall -k --user 0 com.booking #Booking.com
adb shell pm uninstall -k --user 0 com.agoda.mobile.consumer #Agoda

# 其他第三方
adb shell pm uninstall -k --user 0 com.linkedin.android #LinkedIn
adb shell pm uninstall -k --user 0 com.netflix.mediaclient #Netflix
adb shell pm uninstall -k --user 0 com.spotify.music #Spotify
adb shell pm uninstall -k --user 0 com.microsoft.skydrive #OneDrive

# 辦公
adb shell pm uninstall -k --user 0 cn.wps.moffice_eng #WPS Office
adb shell pm uninstall -k --user 0 cn.wps.xiaomi.abroad.lite #WPS 轻量版

# 小米預裝內容與廣告服務
adb shell pm uninstall -k --user 0 com.mi.globalbrowser #小米浏览器
adb shell pm uninstall -k --user 0 com.mi.global.bbs #小米社区
adb shell pm uninstall -k --user 0 com.mi.global.shop #小米商城（国际）
adb shell pm uninstall -k --user 0 com.mi.globalminusscreen #负一屏（国际版）
adb shell pm uninstall -k --user 0 com.miui.android.fashiongallery #锁屏画报/时尚画廊
adb shell pm uninstall -k --user 0 com.miui.player #小米音乐（有自己播放器可卸）
adb shell pm uninstall -k --user 0 com.xiaomi.mipicks #小米应用推荐/精选
adb shell pm uninstall -k --user 0 com.miui.msa.global #小米广告服务（MSA） 强烈推荐卸
adb shell pm uninstall -k --user 0 com.miui.analytics #小米数据分析 推荐卸

# Google 附加應用
adb shell pm uninstall -k --user 0 com.google.android.apps.youtube.music #YouTube Music
adb shell pm uninstall -k --user 0 com.google.android.videos #Google 视频/Movies


