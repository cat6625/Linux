#!/bin/bash

echo "=== 檢查裝置連線 ==="
adb devices

echo ""
echo "=== 開始卸載（已移除的套件會顯示 Failure，可忽略）==="

# Facebook 全家桶
adb shell pm uninstall --user 0 com.facebook.katana          # Facebook
adb shell pm uninstall --user 0 com.facebook.appmanager      # Facebook 安裝器
adb shell pm uninstall --user 0 com.facebook.system          # Facebook 系統服務
adb shell pm uninstall --user 0 com.facebook.services        # Facebook 服務

# Amazon
adb shell pm uninstall --user 0 com.amazon.mShop.android.shopping  # Amazon 購物
adb shell pm uninstall --user 0 com.amazon.appmanager              # Amazon 安裝器

# 旅遊預訂
adb shell pm uninstall --user 0 com.booking                  # Booking.com
adb shell pm uninstall --user 0 com.agoda.mobile.consumer    # Agoda

# 其他第三方
adb shell pm uninstall --user 0 com.linkedin.android         # LinkedIn
adb shell pm uninstall --user 0 com.netflix.mediaclient      # Netflix
adb shell pm uninstall --user 0 com.spotify.music            # Spotify
adb shell pm uninstall --user 0 com.microsoft.skydrive       # OneDrive

# 辦公
adb shell pm uninstall --user 0 cn.wps.moffice_eng           # WPS Office
adb shell pm uninstall --user 0 cn.wps.xiaomi.abroad.lite    # WPS 輕量版

# 小米預裝內容與廣告服務
adb shell pm uninstall --user 0 com.mi.globalbrowser         # 小米瀏覽器
adb shell pm uninstall --user 0 com.mi.global.bbs            # 小米社區
adb shell pm uninstall --user 0 com.mi.global.shop           # 小米商城（國際）
adb shell pm uninstall --user 0 com.mi.globalminusscreen     # 負一屏（國際版）
adb shell pm uninstall --user 0 com.miui.android.fashiongallery  # 鎖屏畫報／時尚畫廊
adb shell pm uninstall --user 0 com.miui.player              # 小米音樂
adb shell pm uninstall --user 0 com.xiaomi.mipicks           # 小米應用推薦／精選
adb shell pm uninstall --user 0 com.miui.msa.global          # 小米廣告服務（MSA）
adb shell pm uninstall --user 0 com.miui.analytics           # 小米數據分析
adb shell pm uninstall --user 0 com.miui.securityadd         # 安全附加元件
# adb shell pm uninstall --user 0 com.miui.guardprovider   # 系統安全元件（已確認會影響檔案上傳，建議保留）
adb shell pm uninstall --user 0 com.miui.yellowpage          # 黃頁
adb shell pm uninstall --user 0 com.xiaomi.glgm              # 遊戲中心
adb shell pm uninstall --user 0 com.xiaomi.smarthome         # 米家（Mi Home）

# 掃一掃（系統保護，只能禁用）
adb shell pm disable-user --user 0 com.xiaomi.scanner        # 掃一掃

# Google 附加應用
adb shell pm uninstall --user 0 com.google.android.apps.youtube.music  # YouTube Music
adb shell pm uninstall --user 0 com.google.android.videos              # Google 影片／Movies

echo ""
echo "=== 檢查剩餘相關套件 ==="
adb shell pm list packages | grep -E "facebook|amazon|booking|agoda|linkedin|netflix|spotify|skydrive|wps|globalbrowser|global.bbs|global.shop|minusscreen|fashiongallery|miui.player|mipicks|msa|analytics|securityadd|guardprovider|yellowpage|glgm|smarthome|scanner|youtube.music|videos" || true

echo ""
echo "完成。"
