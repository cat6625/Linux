# Redmi Note 15 5G（HyperOS）Debloat 心得（初版）

> 機型：Redmi Note 15 5G  
> 系統：HyperOS 2.0.201.0 → 後續有推 2.0.203.0  
> 目標：精簡預裝、減少資料收集，同時保留小米帳號（因 Shizuku 需要登入小米帳號 + SIM 認證）  
> 不使用：遊戲、米家、小米商城、負一屏、鎖屏畫報等  

---

## 一、執行原則

1. **優先使用** `adb shell pm uninstall --user 0 <package>`  
2. 遇到系統保護、無法卸載時，改用 `adb shell pm disable-user --user 0 <package>`  
3. 保留與小米帳號、系統核心功能高度相關的套件  
4. 高風險隱私元件優先處理，但要以「系統可用性」為前提

---

## 二、已成功移除／禁用的套件

### 第三方預裝
- Facebook 全家桶（katana、appmanager、system、services）
- Amazon 購物與安裝器
- Booking、Agoda
- LinkedIn、Netflix、Spotify、OneDrive
- WPS Office 與 WPS 輕量版

### 小米預裝與服務
- 小米瀏覽器（com.mi.globalbrowser）
- 小米社區、小米商城
- 負一屏（com.mi.globalminusscreen）
- 鎖屏畫報／時尚畫廊
- 小米音樂
- 小米應用推薦（mipicks）
- MSA 廣告服務（com.miui.msa.global）
- 小米數據分析（com.miui.analytics）
- 黃頁、遊戲中心、米家

### Google 附加
- YouTube Music
- Google 影片／Movies

### 其他
- 掃一掃（com.xiaomi.scanner）→ **僅能禁用**，無法卸載

---

## 三、重要發現：com.miui.guardprovider

### 爭議點
- 被指會收集第三方 App 清單、版本、簽名
- 疑似有短時間螢幕錄製上傳做反詐檢測
- 屬於近期討論較多的「系統安全元件」

### 實測結果
- 可以成功執行：
  ```bash
  adb uninstall --user 0 com.miui.guardprovider
  ```
- **移除後副作用**：部分 App（如 Brave、Gemini）無法正常上傳檔案
- 已重新安裝恢復：
  ```bash
  adb shell cmd package install-existing com.miui.guardprovider
  ```

### 結論
此元件目前**不建議移除**。  
雖然有隱私疑慮，但與系統檔案上傳、安全驗證機制有關聯，強制移除會影響實際使用體驗。

---

## 四、建議保留的核心套件

| 包名 | 說明 | 原因 |
|------|------|------|
| com.miui.securitycenter | 手機管家 | 系統安全核心 |
| com.miui.securitycore | 安全核心元件 | 與手機管家深度綁定 |
| com.miui.guardprovider | 系統安全元件 | 移除會導致檔案上傳異常 |
| 小米帳號相關服務 | - | Shizuku 需要 |

---

## 五、執行用腳本（精簡版）

```bash
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
```

---

## 六、其他觀察

- HyperOS 2.0.203.0 目前沒有明顯災情回報，屬於小幅度優化與安全性更新。
- 隱私授權與撤回頁面中，建議優先關閉「用戶回饋」、「System Daemon」、「下載管理」、「電量和性能」等項目。
- 系統保護較嚴格的套件（如 scanner、部分安全元件）無法用一般 uninstall 移除，只能 disable 或保留。

---

## 七、後續建議

1. 觀察檔案上傳、銀行 App、Shizuku 是否正常。
2. 定期檢查是否有被系統自動恢復的套件。
3. 若之後出現新的隱私爭議元件，再評估是否處理。

---

*初版整理日期：2026-11-12*  
*狀態：已實際執行並驗證 guardprovider 移除後的副作用*
