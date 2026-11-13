# 🛡️ Android 廣告與追蹤器 SDK 排查指南（Termux + ADB 完整版）

> **適用環境**：Android 11 以上裝置（無需 Root）  
> **核心工具**：Termux + Android 本機無線偵錯（Wireless Debugging）  
> **功能總覽**：本手冊由淺入深收錄四種實戰方案，協助您找出第三方 App 內嵌的廣告聯播網與追蹤器網域，並進行背景凍結與 DNS 阻擋。

---

## 📑 快速導覽目錄

* [一、 基礎入門：一鍵手動排查腳本](#一-基礎入門一鍵手動排查腳本)
* [二、 進階應用：基礎自動化掃描腳本 (`scan_ads.sh`)](#二-進階應用基礎自動化掃描腳本-scan_adssh)
* [三、 深度解析：支援中文 App 名稱與 NextDNS 規則](#三-深度解析支援中文-app-名稱與-nextdns-規則)
* [四、 終極管理：白名單過濾與批次背景權限凍結](#四-終極管理白名單過濾與批次背景權限凍結)

---

## 一、 基礎入門：一鍵手動排查腳本

適合初次測試，無需建立任何腳本檔案，直接透過指令掃描手機內所有第三方 App 的 `classes*.dex` 程式碼。

### 1. 設定 Termux 檔案與套件權限
開啟 Termux 後，依序執行以下指令：
```bash
# 1. 取得手機儲存空間讀寫權限（跳出系統視窗時請點選「允許」）
termux-setup-storage

# 2. 更新套件庫並安裝 ADB 工具與解壓縮工具
pkg update && pkg upgrade -y
pkg install android-tools unzip -y
```

### 2. 開啟無線偵錯並連接本機 ADB
1. 前往手機 **「設定」>「關於手機」**，連續點擊「版本號碼」7 次開啟開發人員模式。
2. 進入 **「設定」>「系統」>「開發人員選項」**，開啟 **「無線偵錯」**。
3. 點擊「無線偵錯」文字進入設定頁，選擇 **「使用配對碼配對裝置」**，記下畫面顯示的 **IP 埠號** 與 **6 位數配對碼**（建議使用分割畫面操作）。
4. 回到 Termux 輸入以下指令完成配對與連線：

```bash
# 配對裝置（將「配對埠號」替換為畫面上顯示的 5 位數字）
adb pair 127.0.0.1:配對埠號
# 輸入提示出現後，鍵入 6 位數配對碼並按 Enter

# 連線至本機 ADB（將「連線埠號」替換為無線偵錯主頁顯示的埠號）
adb connect 127.0.0.1:連線埠號

# 進入 Android 系統 Shell
adb shell
```

### 3. 執行一鍵掃描指令
進入 `adb shell`（提示字元變為 `device:/ $`）後，貼上並執行以下已修正語法的腳本：

```bash
for pkg in $(pm list packages -3 | cut -d':' -f2); do
  apk=$(pm path "$pkg" | head -n 1 | cut -d':' -f2)
  found=$(unzip -p "$apk" classes*.dex 2>/dev/null | grep -oaE "pangle\.io|applovin\.com|unityads\.unity3d\.com|mbridge\.com|vungle\.com|ironsrc\.com|inmobi\.com|adcolony\.com|chartboost\.com|appsflyer\.com|adjust\.com" | sort -u | tr '\n' ' ')
  if [ -n "$found" ]; then
    echo "📦 App: $pkg"
    echo "   └── 偵測到網域: $found"
  fi
done
```

### 4. 常見偵測網域對照表

| 偵測到的網域 | 所屬平台 / 服務 | 主要用途 |
| :--- | :--- | :--- |
| `pangle.io` | TikTok / ByteDance Pangle | 行動廣告聯播網（常出現於免費手遊） |
| `applovin.com` | AppLovin | 廣告變現與行動行銷平台 |
| `unity3d.com` | Unity Ads | Unity 引擎遊戲內建廣告服務 |
| `mbridge.com` | Mintegral (Mobvista) | 行動廣告與程式化競價平台 |
| `vungle.com` | Liftoff (Vungle) | 應用程式內影片廣告服務 |
| `ironsrc.com` | ironSource | 遊戲廣告聚合與變現平台 |
| `inmobi.com` | InMobi | 行動廣告與數據分析平台 |
| `appsflyer.com` | AppsFlyer | 行動歸因與使用者行為追蹤分析 |
| `adjust.com` | Adjust | 應用程式分析與廣告歸因追蹤 |

### 5. 單一 App 限制與退出
```bash
# 禁止指定 App 在背景執行（將 <套件名稱> 替換為掃描出的 pkg 名稱）
cmd appops set <套件名稱> RUN_ANY_IN_BACKGROUND ignore

# 退出 adb shell 回到 Termux
exit
```

---

## 二、 進階應用：基礎自動化掃描腳本 (`scan_ads.sh`)

將掃描指令封裝成自動化腳本，執行後自動將完整報告輸出至手機的 **下載（Download）** 資料夾。

### 1. 建立自動化腳本
在 Termux 主畫面中複製並貼入以下整段指令：

```bash
cat << 'EOF' > ~/scan_ads.sh
#!/data/data/com.termux/files/usr/bin/bash

REPORT_DIR="$HOME/storage/downloads"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
REPORT_FILE="$REPORT_DIR/App_Tracker_Report_$TIMESTAMP.txt"

if ! adb get-state 1>/dev/null 2>&1; then
  echo "❌ 錯誤：尚未連接到本機 ADB！"
  echo "👉 請先開啟手機「無線偵錯」，並在 Termux 執行 adb connect 127.0.0.1:埠號"
  exit 1
fi

echo "🔍 開始掃描已安裝的第三方 App，請稍候..."
{
  echo "=========================================="
  echo "Android 第三方 App 廣告與追蹤器掃描報告"
  echo "掃描時間：$(date '+%Y-%m-%d %H:%M:%S')"
  echo "=========================================="
  echo ""
} > "$REPORT_FILE"

adb shell '
  DOMAINS="pangle\.io|applovin\.com|unityads\.unity3d\.com|mbridge\.com|vungle\.com|ironsrc\.com|inmobi\.com|adcolony\.com|chartboost\.com|appsflyer\.com|adjust\.com|branch\.io|umeng\.com"
  count=0
  for pkg in $(pm list packages -3 | cut -d":" -f2); do
    apk=$(pm path "$pkg" | head -n 1 | cut -d":" -f2)
    found=$(unzip -p "$apk" classes*.dex 2>/dev/null | grep -oaE "$DOMAINS" | sort -u | tr "\n" " ")
    if [ -n "$found" ]; then
      count=$((count + 1))
      echo "📦 [$count] App 套件名稱: $pkg"
      echo "    └── 偵測到網域: $found"
      echo ""
    fi
  done
  echo "------------------------------------------"
  echo "掃描完成！共發現 $count 個包含廣告或追蹤 SDK 的應用程式。"
' | tee -a "$REPORT_FILE"

echo ""
echo "✅ 報告已成功儲存至手機下載資料夾："
echo "📂 Download/App_Tracker_Report_$TIMESTAMP.txt"
EOF

chmod +x ~/scan_ads.sh
```

### 2. 日常執行步驟
1. **連線本機 ADB**：`adb connect 127.0.0.1:連線埠號`
2. **執行掃描腳本**：`./scan_ads.sh`
3. 開啟手機 **「檔案管理」>「下載（Download）」** 檢視 `App_Tracker_Report_日期時間.txt`。

---

## 三、 深度解析：支援中文 App 名稱與 NextDNS 規則

透過 Termux 端的 `aapt` 工具直接解析 APK 標頭，讓報告顯示易讀的 **App 中文名稱**，免去逐一反查套件 ID 的麻煩。

### 1. 安裝 `aapt` 資源解析工具
```bash
pkg update && pkg upgrade -y
pkg install android-tools unzip aapt -y
```

### 2. 建立升級版掃描腳本
```bash
cat << 'EOF' > ~/scan_ads.sh
#!/data/data/com.termux/files/usr/bin/bash

REPORT_DIR="$HOME/storage/downloads"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
REPORT_FILE="$REPORT_DIR/App_Tracker_Report_$TIMESTAMP.txt"

if ! adb get-state 1>/dev/null 2>&1; then
  echo "❌ 錯誤：尚未連接到本機 ADB！"
  echo "👉 請先開啟手機「無線偵錯」，並在 Termux 執行 adb connect 127.0.0.1:埠號"
  exit 1
fi

echo "🔍 正在掃描所有第三方 App 並解析應用程式名稱，請稍候..."
{
  echo "=================================================="
  echo "Android 第三方 App 廣告與追蹤器深度掃描報告"
  echo "掃描時間：$(date '+%Y-%m-%d %H:%M:%S')"
  echo "=================================================="
  echo ""
} > "$REPORT_FILE"

DOMAINS="pangle\.io|applovin\.com|unityads\.unity3d\.com|mbridge\.com|vungle\.com|ironsrc\.com|inmobi\.com|adcolony\.com|chartboost\.com|appsflyer\.com|adjust\.com|branch\.io|umeng\.com|doubleclick\.net|googlesyndication\.com"

count=0
while IFS='|' read -r pkg apk; do
  [ -z "$pkg" ] && continue
  found=$(adb shell "unzip -p '$apk' classes*.dex 2>/dev/null | grep -oaE '$DOMAINS' | sort -u | tr '\n' ' '" </dev/null)
  
  if [ -n "$found" ]; then
    count=$((count + 1))
    app_name=$(adb shell "cat '$apk'" </dev/null | aapt dump badging /dev/stdin 2>/dev/null | grep -m 1 "application-label:" | cut -d"'" -f2)
    [ -z "$app_name" ] && app_name="（無法解析名稱）"
    
    {
      echo "📦 [$count] $app_name"
      echo "    ├── 套件名稱: $pkg"
      echo "    └── 偵測網域: $found"
      echo ""
    } | tee -a "$REPORT_FILE"
  fi
done < <(adb shell 'for p in $(pm list packages -3 | cut -d":" -f2); do echo "$p|$(pm path "$p" | head -n 1 | cut -d":" -f2)"; done')

{
  echo "--------------------------------------------------"
  echo "掃描完成！共發現 $count 個包含廣告或追蹤 SDK 的應用程式。"
} | tee -a "$REPORT_FILE"

echo ""
echo "✅ 報告已成功儲存至手機下載資料夾："
echo "📂 Download/App_Tracker_Report_$TIMESTAMP.txt"
EOF

chmod +x ~/scan_ads.sh
```

### 3. 附錄：NextDNS 黑名單批量阻擋清單
登入 **NextDNS 網頁後台** > **「黑名單（Denylist）」**，加入以下網域（NextDNS 會自動套用萬用字元阻擋所有子網域）：

```text
pangle.io
applovin.com
applvn.com
unity3d.com
mbridge.com
vungle.com
ironsrc.com
inmobi.com
adcolony.com
chartboost.com
appsflyer.com
appsflyersdk.com
adjust.com
branch.io
umeng.com
```

---

## 四、 終極管理：白名單過濾與批次背景權限凍結

最適合日常長期維護的完整工作流：
1. **`scan_ads.sh`**：自動略過信任白名單中的 App，大幅加速掃描。
2. **`limit_apps.sh`**：讀取管制清單，一鍵凍結指定 App 的背景執行與喚醒權限。

### 1. 建立信任白名單 (`whitelist.txt`)
將確定安全且不想重複掃描的 App 套件名稱加入此檔案：
```bash
cat << 'EOF' > ~/whitelist.txt
com.termux
com.whatsapp
jp.naver.line.android
com.google.android.youtube
EOF
```

### 2. 建立支援白名單的掃描腳本 (`scan_ads.sh`)
```bash
cat << 'EOF' > ~/scan_ads.sh
#!/data/data/com.termux/files/usr/bin/bash

REPORT_DIR="$HOME/storage/downloads"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
REPORT_FILE="$REPORT_DIR/App_Tracker_Report_$TIMESTAMP.txt"
WHITELIST="$HOME/whitelist.txt"

touch "$WHITELIST"

if ! adb get-state 1>/dev/null 2>&1; then
  echo "❌ 錯誤：尚未連接到本機 ADB！"
  echo "👉 請先開啟手機「無線偵錯」，並在 Termux 執行 adb connect 127.0.0.1:埠號"
  exit 1
fi

echo "🔍 正在掃描第三方 App（自動略過白名單項目），請稍候..."
{
  echo "=================================================="
  echo "Android 第三方 App 廣告與追蹤器深度掃描報告"
  echo "掃描時間：$(date '+%Y-%m-%d %H:%M:%S')"
  echo "=================================================="
  echo ""
} > "$REPORT_FILE"

DOMAINS="pangle\.io|applovin\.com|unityads\.unity3d\.com|mbridge\.com|vungle\.com|ironsrc\.com|inmobi\.com|adcolony\.com|chartboost\.com|appsflyer\.com|adjust\.com|branch\.io|umeng\.com|doubleclick\.net|googlesyndication\.com"

count=0
skipped=0

while IFS='|' read -r pkg apk; do
  [ -z "$pkg" ] && continue
  pkg=$(echo "$pkg" | tr -d '\r')
  apk=$(echo "$apk" | tr -d '\r')

  if grep -qx "$pkg" "$WHITELIST"; then
    skipped=$((skipped + 1))
    continue
  fi

  found=$(adb shell "unzip -p '$apk' classes*.dex 2>/dev/null | grep -oaE '$DOMAINS' | sort -u | tr '\n' ' '" </dev/null)
  
  if [ -n "$found" ]; then
    count=$((count + 1))
    app_name=$(adb shell "cat '$apk'" </dev/null | aapt dump badging /dev/stdin 2>/dev/null | grep -m 1 "application-label:" | cut -d"'" -f2)
    [ -z "$app_name" ] && app_name="（無法解析名稱）"
    
    {
      echo "📦 [$count] $app_name"
      echo "    ├── 套件名稱: $pkg"
      echo "    └── 偵測網域: $found"
      echo ""
    } | tee -a "$REPORT_FILE"
  fi
done < <(adb shell 'for p in $(pm list packages -3 | cut -d":" -f2); do echo "$p|$(pm path "$p" | head -n 1 | cut -d":" -f2)"; done')

{
  echo "--------------------------------------------------"
  echo "掃描完成！共發現 $count 個包含廣告/追蹤 SDK 的 App（已略過 $skipped 個白名單項目）。"
} | tee -a "$REPORT_FILE"

echo ""
echo "✅ 報告已儲存至：Download/App_Tracker_Report_$TIMESTAMP.txt"
EOF

chmod +x ~/scan_ads.sh
```

### 3. 建立背景管制名單與批次凍結腳本 (`limit_apps.sh`)
```bash
# 1. 建立要限制的 App 名單（範例）
cat << 'EOF' > ~/block_bg_apps.txt
com.andaman.games.block.puzzle.free
EOF

# 2. 建立批次凍結腳本
cat << 'EOF' > ~/limit_apps.sh
#!/data/data/com.termux/files/usr/bin/bash

TARGET_LIST="$HOME/block_bg_apps.txt"

if ! adb get-state 1>/dev/null 2>&1; then
  echo "❌ 錯誤：尚未連接到本機 ADB！"
  exit 1
fi

if [ ! -s "$TARGET_LIST" ]; then
  echo "⚠️ 名單 $TARGET_LIST 目前是空的，請先加入套件名稱。"
  exit 1
fi

echo "🔒 開始對名單內的 App 套件套用背景限制..."
while IFS= read -r pkg; do
  pkg=$(echo "$pkg" | tr -d '\r' | xargs)
  [ -z "$pkg" ] && continue

  echo "👉 正在限制：$pkg"
  adb shell "cmd appops set $pkg RUN_ANY_IN_BACKGROUND ignore" </dev/null
  adb shell "cmd appops set $pkg WAKE_LOCK ignore" </dev/null
  adb shell "am force-stop $pkg" </dev/null
done < "$TARGET_LIST"

echo "✅ 所有指定 App 的背景執行與喚醒權限皆已凍結！"
EOF

chmod +x ~/limit_apps.sh
```

### 4. 日常維護指令速查表

| 操作目的 | 執行指令 |
| :--- | :--- |
| **連接本機 ADB** | `adb connect 127.0.0.1:無線偵錯埠號` |
| **執行全機掃描並產生報告** | `./scan_ads.sh` |
| **編輯信任白名單（略過掃描）** | `nano ~/whitelist.txt` |
| **編輯背景限制名單** | `nano ~/block_bg_apps.txt` |
| **一鍵凍結名單內 App 背景活動** | `./limit_apps.sh` |
| **解除特定 App 的背景限制** | `adb shell cmd appops reset <套件名稱>` |
