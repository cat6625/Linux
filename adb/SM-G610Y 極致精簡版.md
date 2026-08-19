
# SM-G610Y 極致精簡版

## 第一批：通常可以直接停

```text
for pkg in com.google.android.youtube com.google.android.apps.docs com.google.android.videos com.google.android.talk com.google.android.feedback com.sec.android.app.voicenote com.sec.android.app.fm com.samsung.android.weather com.samsung.android.themestore com.samsung.android.themecenter com.samsung.android.app.galaxyfinder com.samsung.android.app.bikemode com.sec.android.easyonehand com.sec.android.app.dictionary com.sec.android.app.magnifier com.android.dreams.basic com.android.dreams.phototable com.samsung.android.video com.sec.android.mimage.photoretouching com.sec.android.app.easyMover.Agent; do adb shell pm disable-user --user 0 "$pkg"; done
```

> 這批主要是 Samsung/Google 附加功能，通常不會影響基本電話功能。

## 第二批：不用相關功能才停

```text
for pkg in com.samsung.android.scloud com.samsung.android.fmm com.samsung.android.app.FileShareClient com.samsung.android.app.FileShareServer com.samsung.android.allshare.service.mediashare com.sec.allsharecastplayer com.samsung.android.app.withtv com.samsung.android.app.watchmanagerstub com.sec.android.Kies com.samsung.android.sdk.professionalaudio.utility.jammonitor com.samsung.android.sdk.professionalaudio.app.audioconnectionservice com.samsung.android.app.colorblind com.samsung.android.app.assistantmenu ; do adb shell pm disable-user --user 0 "$pkg"; done
```


> 例如你沒有 Samsung Watch、Samsung TV、Samsung Cloud，就可以把相關項目一起停掉。
