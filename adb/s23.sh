#!/system/bin/sh

# ======================================================================
# Samsung S23 Debloat Script (Fixed Version)
# ======================================================================

# 定義日誌路徑
LOGFILE="/sdcard/Download/S23_Debloat.log"

echo "------------------------------------------------"
echo ">> SAMSUNG S23 DEBLOAT <<"
echo "------------------------------------------------"

# 寫入標頭 (使用 >> 避免覆蓋)
echo "S23 DEBLOAT LOG - $(date)" > "$LOGFILE"

# 移除套件的函式
remove_pkg() {
    local PKG=$1
    # 先嘗試停用，再嘗試移除
    pm disable-user --user 0 "$PKG" > /dev/null 2>&1
    
    # 執行移除。注意：有些套件移除後回傳的是 "Success" 字串，
    # 但有些環境會帶有額外空格或換行，因此建議用 grep 判斷
    RES=$(pm uninstall -k --user 0 "$PKG" 2>&1)
    
    if echo "$RES" | grep -q "Success"; then
        echo "  - $PKG: REMOVED" >> "$LOGFILE"
        echo "[-] $PKG: [OK]"
    else
        # 即使失敗也記錄原因 (例如套件不存在)
        echo "  - $PKG: SKIPPED ($RES)" >> "$LOGFILE"
        echo "[!] $PKG: [SKIPPED]"
    fi
}

# 1. 系統動畫優化
settings put global window_animation_scale 0.5
settings put global transition_animation_scale 0.5
settings put global animator_duration_scale 0.5
echo "[SYSTEM] Animations set to 0.5x" >> "$LOGFILE"

# 2. Facebook 相關
for p in com.facebook.services com.facebook.system com.facebook.appmanager com.facebook.katana; do
    remove_pkg "$p"
done

# 3. Microsoft 相關
for p in com.microsoft.skydrive com.microsoft.onedrive com.touchtype.swiftkey \
com.swiftkey.swiftkeyconfigurator com.microsoft.swiftkey; do
    remove_pkg "$p"
done

# 4. 兒童模式
for p in com.samsung.android.kidsinstaller \
com.sec.android.app.kidshome; do
    remove_pkg "$p"
done

# 5. 電信商與廣告
for p in com.aura.oobe.samsung de.axelspringer.yana.zeropage \
com.android.providers.partnerbookmarks com.sec.android.app.chromecustomizations \
com.att.dh com.att.dtv.shaderemote com.att.tv com.samsung.attvvm \
com.att.myWireless com.vzw.hss.myverizon com.samsung.vvm \
com.samsung.android.app.spage; do
    remove_pkg "$p"
done

# 6. 其他擴充 (Rubin, Tips, AR)
for p in com.samsung.android.rubin.app \
com.samsung.android.app.tips com.samsung.android.aremoji \
com.samsung.android.aremojieditor \
com.samsung.android.app.camera.sticker.facearavatar.preload \
com.samsung.android.stickercenter com.samsung.android.vtcamerasettings \
com.samsung.android.arzone \
com.samsung.android.game.gamehome \
com.samsung.android.game.gametools; do
    remove_pkg "$p"
done

echo "------------------------------------------------"
echo ">> FINISHED. Please Reboot. <<"
echo "------------------------------------------------"
