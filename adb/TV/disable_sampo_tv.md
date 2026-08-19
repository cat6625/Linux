# 聲寶電視 精簡

## 使用工具 Remote adb shell
https://play.google.com/store/apps/details?id=com.cgutman.androidremotedebugger


## 停用
```text
#① 商用功能（100% 可停）
pm disable-user --user 0 com.mk.tv.digitalsignage
pm disable-user --user 0 com.mk.tv.meeting
pm disable-user --user 0 com.mk.tv.timeclock
pm disable-user --user 0 com.mk.tv.meeting.service


#② 原廠附加功能
pm disable-user --user 0 com.apps.esticker
pm disable-user --user 0 com.apps.plugins
pm disable-user --user 0 com.apps.channels
pm disable-user --user 0 com.apps.tvmanager


#③ 投放功能（不用就停）
pm disable-user --user 0 com.apps.scast
pm disable-user --user 0 com.apps.eshow
pm disable-user --user 0 com.creative.fastscreen.tv


#④ 不使用時可停
pm disable-user --user 0 com.apps.wifihotspot
pm disable-user --user 0 com.apps.usbmediaplayer


#⑤ Google 附加程式
pm disable-user --user 0 com.google.android.feedback
pm disable-user --user 0 com.google.android.play.games
pm disable-user --user 0 com.google.android.videos
pm disable-user --user 0 com.android.printspooler



#⑥ Android 內建
pm disable-user --user 0 com.android.gallery3d


#⑦ 不使用串流時
pm disable-user --user 0 com.netflix.ninja
pm disable-user --user 0 com.amazon.amazonvideo.livingroom
pm disable-user --user 0 com.google.android.youtube.tvmusic
pm disable-user --user 0 com.google.android.youtube.tv
```


## 恢復
```text
#① 商用功能（100% 可停）
pm enable com.mk.tv.digitalsignage
pm enable com.mk.tv.meeting
pm enable com.mk.tv.timeclock
pm enable com.mk.tv.meeting.service


#② 原廠附加功能
pm enable com.apps.esticker
pm enable com.apps.plugins
pm enable com.apps.channels
pm enable com.apps.tvmanager


#③ 投放功能（不用就停）
pm enable com.apps.scast
pm enable com.apps.eshow
pm enable com.creative.fastscreen.tv


#④ 不使用時可停
pm enable com.apps.wifihotspot
pm enable com.apps.usbmediaplayer


#⑤ Google 附加程式
pm enable com.google.android.feedback
pm enable com.google.android.play.games
pm enable com.google.android.videos
pm enable com.android.printspooler



#⑥ Android 內建
pm enable com.android.gallery3d


#⑦ 不使用串流時
pm enable com.netflix.ninja
pm enable com.amazon.amazonvideo.livingroom
pm enable com.google.android.youtube.tvmusic
pm enable com.google.android.youtube.tv
```
