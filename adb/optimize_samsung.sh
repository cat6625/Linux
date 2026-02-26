#!/bin/bash

# ============================================================
# 三星安全優化腳本 (針對韌體 Bug 環境微調版)
# ============================================================

# 1. 絕對安全的垃圾套件 (FB、AR、冗餘工具)
SAFE_PKGS=(
    # Facebook 系列 (廣告追蹤元兇)
    com.facebook.system
    com.facebook.appmanager
    com.facebook.services
    # 三星 AR 與 貼圖 (佔用空間大)
    com.samsung.android.aremoji
    com.samsung.android.stickercenter
    com.samsung.android.aremojieditor
    com.sec.android.mimage.avatarstickers
    # 冗餘系統工具
    com.samsung.android.kidsinstaller       # 兒童模式安裝器
    com.samsung.android.app.spage           # Bixby Home
    com.samsung.android.game.gamehome       # 遊戲中心
    com.microsoft.skydrive                  # OneDrive
    com.google.android.apps.aiwallpapers    # AI 桌布
    com.snap.camerakit.plugin.v1            # Snapchat 插件
)

echo "--- [1/3] 開始停用安全清單內的套件 ---"
for PKG in "${SAFE_PKGS[@]}"; do
    echo "正在停用: $PKG"
    adb shell pm disable-user --user 0 "$PKG" > /dev/null 2>&1
done

# 2. 針對韌體 Bug 的特殊處理 (保持開啟，但限制背景活動)
# 這樣可以防止 Google 服務報錯更嚴重，同時達到省電效果
LIMIT_PKGS=(
    com.samsung.android.rubin.app           # 個人化服務 (與 Routine 報錯相關)
    com.samsung.android.app.omcagent        # 電信配置 (慎動套件)
)

echo -e "\n--- [2/3] 正在限制敏感套件的背景活動 (不直接停用以避免報錯) ---"
for PKG in "${LIMIT_PKGS[@]}"; do
    echo "正在限制: $PKG"
    adb shell cmd appops set "$PKG" RUN_IN_BACKGROUND ignore
done

# 3. 執行全系統效能優化
echo -e "\n--- [3/3] 正在執行強制編譯優化 (speed-profile) ---"
echo "這能幫助剩餘的 App 重新整理連結，請稍候約 2-5 分鐘..."
adb shell cmd package compile -m speed-profile -a

echo -e "\n==========================================================="
echo "優化完成！"
echo "請重新啟動手機 (adb reboot)，享受更乾淨的系統。"
echo "提示：若重啟後仍有日誌錯誤，請無視它，那是三星韌體的天生 Bug。"
echo "==========================================================="
