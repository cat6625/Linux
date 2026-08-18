#!/usr/bin/env bash

set -u

echo "======================================================"
echo " ASUS ZenFone 2 Laser (ZE500KL) - Conservative Debloat"
echo " Target: Android 5.x / 6.x / ZenUI"
echo " Mode: SAFE / CONSERVATIVE"
echo "======================================================"
echo

# ============================================================
# 1. 檢查 ADB
# ============================================================

if ! command -v adb >/dev/null 2>&1; then
    echo "[ERROR] 找不到 adb，請先安裝 Android ADB 工具"
    exit 1
fi

adb start-server >/dev/null 2>&1

if ! adb get-state 2>/dev/null | grep -q '^device$'; then
    echo "[ERROR] 找不到已授權的 ASUS ZE500KL 裝置"
    echo
    adb devices
    exit 1
fi

SERIAL="$(adb get-serialno 2>/dev/null)"

BACKUP_DIR="$HOME/asus-ze500kl-backup-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BACKUP_DIR"

echo "[OK] 裝置序列號：$SERIAL"
echo "[OK] 備份目錄：$BACKUP_DIR"
echo

# ============================================================
# 2. 備份目前 Package 狀態
# ============================================================

echo "[BACKUP] 儲存目前套件清單..."

adb shell pm list packages > "$BACKUP_DIR/packages.txt"
adb shell pm list packages -s > "$BACKUP_DIR/system-packages.txt"
adb shell pm list packages -3 > "$BACKUP_DIR/third-party-packages.txt"
adb shell pm list packages -d > "$BACKUP_DIR/disabled-packages.txt"

echo "[OK] Package 清單備份完成"
echo

# ============================================================
# 3. 取得目前已安裝套件
# ============================================================

INSTALLED_PACKAGES="$(
    adb shell pm list packages 2>/dev/null |
    tr -d '\r' |
    sed 's/^package://'
)"

# ============================================================
# 4. 保守安全移除清單
#
# 原則：
#   - 不碰 Android 核心元件
#   - 不碰電話 / 通訊 / Wi-Fi / 藍牙
#   - 不碰顯示 / 音效 / 相機
#   - 不碰 ASUS 更新 / 裝置管理
#   - 不碰 Google 核心服務
#   - 不碰 TTS / Accessibility
#
# ============================================================

PACKAGES=(

    # --------------------------------------------------------
    # ASUS：明確屬於獨立功能 App
    # 不需要該功能時可移除
    # --------------------------------------------------------

    com.asus.quickmemo
    com.asus.quickmemoservice

    com.asus.laserruler

    com.asus.supernote

    com.asus.ephotoburst
    com.asus.collage
    com.asus.microfilm

    com.asus.zencircle

    com.asus.userfeedback

    com.asus.livedemoinstaller
    com.asus.livedemo
    com.asus.livedemoservice

    com.asus.DLNA
    com.asus.playto

    com.asus.sharerim
    com.asus.linkrim.service

    com.asus.fmradio
    com.asus.fmservice

    # --------------------------------------------------------
    # 第三方預載
    # --------------------------------------------------------

    com.zinio.android.settings

    com.ironsource.appcloud.oobe.asus

    com.cmcm.skey

    # --------------------------------------------------------
    # Facebook / Meta
    # 如果完全不用 Facebook / Messenger / Instagram
    # --------------------------------------------------------

    com.facebook.katana
    com.facebook.orca
    com.facebook.system
    com.facebook.appmanager
    com.instagram.android

    # --------------------------------------------------------
    # Google 使用者 App
    #
    # 這些不是 Google 核心服務。
    # 之後需要可以從 Play Store / APK 恢復。
    # --------------------------------------------------------

    com.google.android.youtube

    com.google.android.googlequicksearchbox

    com.google.android.music

    com.google.android.videos

    com.google.android.apps.docs

    com.google.android.apps.docs.oem

    com.google.android.apps.maps

    com.google.android.apps.photos

    com.google.android.calendar

    com.google.android.gm

    com.google.android.talk

    # --------------------------------------------------------
    # ANT+
    # 不使用 ANT+ 運動裝置時才移除
    # --------------------------------------------------------

    com.dsi.ant.server
)

# ============================================================
# 5. 移除函式
# ============================================================

remove_package() {

    local PKG="$1"

    if printf '%s\n' "$INSTALLED_PACKAGES" | grep -Fxq "$PKG"; then

        printf "[REMOVE] %-55s " "$PKG"

        RESULT="$(
            adb shell pm uninstall --user 0 "$PKG" 2>&1 |
            tr -d '\r'
        )"

        if echo "$RESULT" | grep -qi "success"; then
            echo "Success"
        else
            echo "${RESULT:-Unknown result}"
        fi

    else

        printf "[SKIP]   %-55s (未安裝)\n" "$PKG"

    fi
}

# ============================================================
# 6. 顯示即將處理的套件數量
# ============================================================

echo "======================================================"
echo " 即將處理 ${#PACKAGES[@]} 個套件"
echo "======================================================"
echo

for PKG in "${PACKAGES[@]}"; do
    printf '%s\n' "$PKG"
done

echo
echo "======================================================"
echo " 注意：本清單為保守版"
echo " 不包含 ASUS 核心系統服務"
echo " 不包含 Android 核心元件"
echo " 不包含 Google Play 核心服務"
echo "======================================================"
echo

read -r -p "確定開始移除？輸入 YES 才會繼續： " CONFIRM

if [[ "$CONFIRM" != "YES" ]]; then
    echo
    echo "[CANCEL] 使用者取消操作"
    exit 0
fi

echo
echo "========== 開始精簡 ASUS ZE500KL =========="
echo

# ============================================================
# 7. 開始移除
# ============================================================

for PKG in "${PACKAGES[@]}"; do
    remove_package "$PKG"
done

# ============================================================
# 8. 完成
# ============================================================

echo
echo "======================================================"
echo " Debloat 完成"
echo "======================================================"
echo
echo "[INFO] 備份資料："
echo "       $BACKUP_DIR"
echo
echo "[INFO] 建議重新開機："
echo "       adb reboot"
echo
echo "======================================================"


#  adb shell pm install -r --user 0 /system/app/AsusFlashLight/AsusFlashLight.apk
#  adb shell pm install -r --user 0 /system/priv-app/AsusCalculator/AsusCalculator.apk
#  adb shell pm install -r --user 0 /system/app/QuickMemo/QuickMemo.apk



