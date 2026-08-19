# mixbox s 精簡

## 使用工具 Remote adb shell
https://play.google.com/store/apps/details?id=com.cgutman.androidremotedebugger


## 停用
```text

# 小米後台數據統計與分析追蹤（核心精簡目標）
pm disable-user --user 0 com.xiaomi.statistic
pm disable-user --user 0 com.miui.tv.analytics
pm disable-user --user 0 com.xiaomo.tv.milegal

# 小米內建的廣告/免費電視推薦版面（關閉可清空電視首頁雜亂內容）
pm disable-user --user 0 com.mitv.tvhome.oemtab
pm disable-user --user 0 com.mitv.tvhome.mitvplus
pm disable-user --user 0 com.mitv.tvhome.michannel
pm disable-user --user 0 com.xiaomi.android.tvsetup.partnercustomizer
pm disable-user --user 0 com.xm.webcontent
pm disable-user --user 0 com.xiaomi.tvqs.overseas.y24
pm disable-user --user 0 com.mitv.tvhome.atv


# Google 基本垃圾與列印服務
pm disable-user --user 0 com.google.android.feedback
pm disable-user --user 0 com.google.android.play.games
pm disable-user --user 0 com.android.printspooler

# 小米內建多媒體（已有替代播放器就可關閉）
pm disable-user --user 0 com.mitv.gallery
pm disable-user --user 0 com.xiaomi.mimusic2
pm disable-user --user 0 com.mitv.videoplayer
pm disable-user --user 0 com.xiaomi.mitv.mediaexplorer

# 小米原廠投屏與裝置互聯（若改用 Chromecast 或 AirScreen 即可關閉）
pm disable-user --user 0 com.xiaomi.mitv.smartshare
pm disable-user --user 0 com.xiaomi.wfdsinkhelperservice
pm disable-user --user 0 com.xiaomi.mi_connect_service

# 三大主流付費影音
pm disable-user --user 0 com.netflix.ninja
pm disable-user --user 0 com.amazon.amazonvideo.livingroom
pm disable-user --user 0 com.google.android.youtube.tv
```

## 恢復
```text

# 小米後台數據統計與分析追蹤（核心精簡目標）
pm enable com.xiaomi.statistic
pm enable com.miui.tv.analytics
pm enable com.xiaomo.tv.milegal

# 小米內建的廣告/免費電視推薦版面（關閉可清空電視首頁雜亂內容）
pm enable com.mitv.tvhome.oemtab
pm enable com.mitv.tvhome.mitvplus
pm enable com.mitv.tvhome.michannel
pm enable com.xiaomi.android.tvsetup.partnercustomizer
pm enable com.xm.webcontent
pm enable com.xiaomi.tvqs.overseas.y24
pm enable com.mitv.tvhome.atv


# Google 基本垃圾與列印服務
pm enable com.google.android.feedback
pm enable com.google.android.play.games
pm enable com.android.printspooler

# 小米內建多媒體（已有替代播放器就可關閉）
pm enable com.mitv.gallery
pm enable com.xiaomi.mimusic2
pm enable com.mitv.videoplayer
pm enable com.xiaomi.mitv.mediaexplorer

# 小米原廠投屏與裝置互聯（若改用 Chromecast 或 AirScreen 即可關閉）
pm enable com.xiaomi.mitv.smartshare
pm enable com.xiaomi.wfdsinkhelperservice
pm enable com.xiaomi.mi_connect_service

# 三大主流付費影音
pm enable com.netflix.ninja
pm enable com.amazon.amazonvideo.livingroom
pm enable com.google.android.youtube.tv
```
