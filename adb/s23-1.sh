#!/system/bin/sh

# ======================================================================
# Samsung S23 Debloat Script (Enhanced Version)
# ======================================================================

LOGFILE="/sdcard/Download/S23_Debloat.log"

echo "------------------------------------------------"
echo ">> SAMSUNG S23 DEBLOAT & DISABLE <<"
echo "------------------------------------------------"

echo "S23 DEBLOAT LOG - $(date)" > "$LOGFILE"

# 核心處理函式
process_pkg() {
    local PKG=$1
    echo "[-] Processing: $PKG"
    
    # 1. 先嘗試停用 (Disable) - 這對大多數系統組件最安全且有效
    DIS_RES=$(pm disable-user --user 0 "$PKG" 2>&1)
    
    # 2. 嘗試卸載 (Uninstall) - 徹底移除 (保留數據)
    UNI_RES=$(pm uninstall -k --user 0 "$PKG" 2>&1)
    
    if echo "$UNI_RES" | grep -q "Success" || echo "$DIS_RES" | grep -q "new state: disabled-user"; then
        echo "  - $PKG: DISABLED/REMOVED" >> "$LOGFILE"
        echo "    > [OK]"
    else
        echo "  - $PKG: SKIPPED ($UNI_RES)" >> "$LOGFILE"
        echo "    > [SKIPPED]"
    fi
}

# --- 1. 系統動畫與效能優化 ---
settings put global window_animation_scale 0.5
settings put global transition_animation_scale 0.5
settings put global animator_duration_scale 0.5
echo "[SYSTEM] Animations set to 0.5x" >> "$LOGFILE"

# --- 2. 你新增的指定套件 (快速共享、跨裝置通話、Android Auto 等) ---
# 包括: Fast (分享), MdecService (跨裝置通話), Gearhead (Android Auto), 
# Scribe (即時字幕), Billing (三星帳單), VisualARS (視覺辨識),voiceaccess
for p in com.samsung.android.mdecservice \
com.google.android.projection.gearhead com.google.audio.hearing.visualization.accessibility.scribe \
com.sec.android.app.billing com.samsung.android.visualars \ com.google.android.apps.accessibility.voiceaccess; do
    process_pkg "$p"
done

# --- 3. Facebook 相關 ---
for p in com.facebook.services com.facebook.system com.facebook.appmanager com.facebook.katana; do
    process_pkg "$p"
done

# --- 4. Microsoft 相關 ---
for p in com.microsoft.skydrive com.microsoft.onedrive com.touchtype.swiftkey \
com.swiftkey.swiftkeyconfigurator com.microsoft.swiftkey; do
    process_pkg "$p"
done

# --- 5. 兒童模式與電信商廣告 ---
for p in com.samsung.android.kidsinstaller com.sec.android.app.kidshome \
com.aura.oobe.samsung de.axelspringer.yana.zeropage com.android.providers.partnerbookmarks \
com.sec.android.app.chromecustomizations com.samsung.android.app.spage; do
    process_pkg "$p"
done

# --- 6. AR 與相機擴充 ---
for p in com.samsung.android.rubin.app com.samsung.android.app.tips \
com.samsung.android.aremoji com.samsung.android.aremojieditor \
com.samsung.android.app.camera.sticker.facearavatar.preload \
com.samsung.android.stickercenter com.samsung.android.arzone; do
    process_pkg "$p"
done


# --- 6. 遊戲 ---
for p in com.samsung.android.game.gamehome \
com.samsung.android.game.gametools; do
    process_pkg "$p"
done

echo "------------------------------------------------"
echo ">> FINISHED. Please Reboot your S23. <<"
echo "------------------------------------------------"

