#!/usr/bin/env bash

set -u

echo "=============================================="
echo " HTC A9s (htc_e36_ml_uhl) - Safe Debloat"
echo " Target: Android 6.0 / MRA58K"
echo "=============================================="
echo

if ! command -v adb >/dev/null 2>&1; then
    echo "[ERROR] 找不到 adb，請先安裝 adb 工具"
    exit 1
fi

adb start-server >/dev/null 2>&1

if ! adb get-state 2>/dev/null | grep -q '^device$'; then
    echo "[ERROR] 找不到已授權的 HTC A9s 裝置"
    adb devices
    exit 1
fi

SERIAL="$(adb get-serialno 2>/dev/null)"
BACKUP_DIR="$HOME/htc-a9s-backup-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BACKUP_DIR"

echo "[OK] 裝置序列號：$SERIAL"
echo "[OK] 清單備份至：$BACKUP_DIR"
echo

# 執行前備份原始 Package 清單
adb shell pm list packages > "$BACKUP_DIR/packages.txt"
adb shell pm list packages -s > "$BACKUP_DIR/system-packages.txt"

# ============================================================
# 安全可移除套件清單 (已剔除地雷元件)
# ============================================================

PACKAGES=(
    # Google 應用程式 (可依需求自行註解/取消註解)
    com.google.android.youtube
    com.google.android.music
    com.google.android.videos
    com.google.android.apps.docs
    com.google.android.apps.docs.editors.docs
    com.google.android.apps.maps
    com.google.android.apps.photos
    com.google.android.calendar
    com.google.android.gm
    com.google.android.talk
    com.google.android.apps.tachyon
    com.google.android.marvin.talkback

    # 社群 App 本體 (僅移除使用者介面，保留 FB 系統框架)
    com.facebook.katana
    com.facebook.orca
    com.instagram.android

    # 第三方新聞 / 廣告 / 預載 App
    com.mobilesrepublic.appy
    com.ironsource.appcloud.oobe.htc

    # HTC 額外服務 (不影響桌面運作)
    com.htc.community
    com.htc.guide
    com.htc.mirrorlinkserver
    com.htc.wifidisplay

    # HTC 社交整合 (已排除 Facebook，僅移除其他已停用服務)
    com.htc.sense.socialnetwork.googleplus
    com.htc.sense.socialnetwork.plurk
    com.htc.sense.socialnetwork.twitter

    # 同步與備份工具
    com.nero.android.htc.sync
    com.nero.android.htc.sync.installer
    com.futuredial.idevicecloud
)

# TouchPal 額外語言包 (保留 繁中/簡中/倉頡)
LANG_PACKAGES=(
    com.cootek.smartinputv5.language.oem.malayan
    com.cootek.smartinputv5.language.oem.spanishus
    com.cootek.smartinputv5.language.oem.russian
    com.cootek.smartinputv5.language.oem.portuguesept
    com.cootek.smartinputv5.language.oem.italian
    com.cootek.smartinputv5.language.oem.norwegian
    com.cootek.smartinputv5.language.oem.hungarian
    com.cootek.smartinputv5.language.oem.englishgb
    com.cootek.smartinputv5.language.oem.slovenian
    com.cootek.smartinputv5.language.oem.swedish
    com.cootek.smartinputv5.language.oem.estonian
    com.cootek.smartinputv5.language.oem.bulgarian
    com.cootek.smartinputv5.language.oem.armenian
    com.cootek.smartinputv5.language.oem.indonesian
    com.cootek.smartinputv5.language.oem.turkish
    com.cootek.smartinputv5.language.oem.arabic
    com.cootek.smartinputv5.language.oem.finnish
    com.cootek.smartinputv5.language.oem.ukrainian
    com.cootek.smartinputv5.language.oem.lithuanian
    com.cootek.smartinputv5.language.oem.danish
    com.cootek.smartinputv5.language.oem.french
    com.cootek.smartinputv5.language.oem.german
    com.cootek.smartinputv5.language.oem.persian
    com.cootek.smartinputv5.language.oem.hebrew
    com.cootek.smartinputv5.language.oem.kazakh
    com.cootek.smartinputv5.language.oem.polish
    com.cootek.smartinputv5.language.oem.slovak
    com.cootek.smartinputv5.language.oem.romanian
    com.cootek.smartinputv5.language.oem.latvian
    com.cootek.smartinputv5.language.oem.czech
    com.cootek.smartinputv5.language.oem.dutch
    com.cootek.smartinputv5.language.oem.greek
    com.cootek.smartinputv5.language.oem.serbianlatin
    com.cootek.smartinputv5.language.oem.catalan
)

remove_package() {
    local PKG="$1"
    # 加入 tr -d '\r' 清除 Windows 換行符號，避免 grep -x 判定失敗
    if adb shell pm list packages 2>/dev/null | tr -d '\r' | grep -qx "package:$PKG"; then
        printf "[REMOVE] %-60s " "$PKG"
        RESULT="$(adb shell pm uninstall --user 0 "$PKG" 2>/dev/null | tr -d '\r')"
        echo "${RESULT:-Success}"
    else
        printf "[SKIP]   %-60s (未安裝)\n" "$PKG"
    fi
}

echo "========== 開始移除預載 App =========="
for PKG in "${PACKAGES[@]}"; do
    remove_package "$PKG"
done

echo
echo "========== 開始移除 TouchPal 語言包 =========="
for PKG in "${LANG_PACKAGES[@]}"; do
    remove_package "$PKG"
done

echo
echo "=============================================="
echo " Debloat 完成！建議執行重新開機："
echo " adb reboot"
echo "=============================================="

