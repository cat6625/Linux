# Android 廣告與追蹤器 SDK 排查指南（Termux + ADB 版）

本指南適用於 **Android 11 以上**裝置，無需 Root 即可透過 Termux 搭配本機無線偵錯（Wireless Debugging），掃描手機內所有第三方 App 內嵌的廣告與追蹤器網域。

---

## 第一步：設定 Termux 檔案與套件權限

開啟 Termux 後，先執行以下指令授予儲存空間權限並更新套件庫：

```bash
# 1. 取得手機儲存空間讀寫權限（跳出系統視窗時請點選「允許」）
termux-setup-storage

# 2. 更新套件庫並安裝 ADB 工具與解壓縮工具
pkg update && pkg upgrade -y
pkg install android-tools unzip -y
```

---

## 第二步：開啟無線偵錯並連接本機 ADB

透過本機迴路連接 ADB，讓終端機取得讀取所有已安裝 APK 路徑的系統權限：

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

---

## 第三步：一鍵掃描所有第三方 App 的廣告與追蹤器 SDK

進入 `adb shell`（提示字元會變成類似 `device:/ $`）後，直接貼上並執行以下腳本。腳本會逐一檢查手機上所有第三方 App 的 `classes*.dex` 程式碼，比對常見的廣告聯播網與數據追蹤特徵：

```bash
for pkg in \$(pm list packages -3 | cut -d':' -f2); do
  apk=(pm path pkg | head -n 1 | cut -d':' -f2)
  found=(unzip -p "apk" classes*.dex 2>/dev/null | grep -oaE "pangle\.io|applovin\.com|unityads\.unity3d\.com|mbridge\.com|vungle\.com|ironsrc\.com|inmobi\.com|adcolony\.com|chartboost\.com|appsflyer\.com|adjust\.com" | sort -u | tr '\n' ' ')
  if [ -n "\$found" ]; then
    echo "📦 App: \$pkg"
    echo "   └── 偵測到網域: \$found"
  fi
done
```

### 常見偵測網域對照表

| 偵測到的網域 | 所屬平台 / 服務 | 主要用途 |
| :--- | :--- | :--- |
| `pangle.io` | TikTok / ByteDance Pangle | 行動廣告聯播網（常出現於免費手遊） |
| `applovin.com` | AppLovin | 廣告變現與行動行銷平台 |
| `://unity3d.com` | Unity Ads | Unity 引擎遊戲內建廣告服務 |
| `mbridge.com` | Mintegral (Mobvista) | 行動廣告與程式化競價平台 |
| `vungle.com` | Liftoff (Vungle) | 應用程式內影片廣告服務 |
| `ironsrc.com` | ironSource | 遊戲廣告聚合與變現平台 |
| `inmobi.com` | InMobi | 行動廣告與數據分析平台 |
| `appsflyer.com` | AppsFlyer | 行動歸因與使用者行為追蹤分析 |
| `adjust.com` | Adjust | 應用程式分析與廣告歸因追蹤 |

---

## 第四步：後續限制與阻擋處置

若掃描出特定遊戲或工具軟體包含不需要的廣告追蹤模組，可直接在 `adb shell` 中限制其背景執行與網路活動：

```bash
# 禁止指定 App 在背景執行（將 <套件名稱> 替換為掃描出的 pkg 名稱）
cmd appops set <套件名稱> RUN_ANY_IN_BACKGROUND ignore

# 退出 adb shell 回到 Termux
exit
```

* **DNS 層級全面防護**：建議在 **NextDNS** 或 **AdGuard Home** 的黑名單中，直接加入萬用字元規則（例如 `*.pangle.io`、`*.applovin.com`、`*.appsflyer.com`），即可在系統層級無痛過濾這類請求。


---

# Android 廣告與追蹤器 SDK 自動化掃描腳本（Termux 版）

本指南將帶你在 Termux 中建立一支名為 `scan_ads.sh` 的自動化腳本。執行後會自動透過本機 ADB 掃描所有第三方 App，並將結果輸出至手機的 **下載（Download）** 資料夾。

---

## 第一步：確認基礎權限與工具（已設定過可跳過）

開啟 Termux，確認已授權儲存空間並安裝 `android-tools`：

```bash
termux-setup-storage
pkg update && pkg install android-tools -y
```

---

## 第二步：建立自動化掃描腳本 `scan_ads.sh`

請將以下**整段指令**複製並貼入 Termux 中執行，系統會自動在你的家目錄建立 `scan_ads.sh` 並賦予執行權限：

```bash
cat << 'EOF' > ~/scan_ads.sh
#!/data/data/com.termux/files/usr/bin/bash

# 設定輸出報告路徑（存放在手機內部儲存空間的 Download 資料夾）
REPORT_DIR="$HOME/storage/downloads"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
REPORT_FILE="$REPORT_DIR/App_Tracker_Report_$TIMESTAMP.txt"

# 檢查 ADB 連線狀態
if ! adb get-state 1>/dev/null 2>&1; then
  echo "❌ 錯誤：尚未連接到本機 ADB！"
  echo "👉 請先開啟手機「無線偵錯」，並在 Termux 執行 adb connect 127.0.0.1:埠號"
  exit 1
fi

echo "🔍 開始掃描已安裝的第三方 App，請稍候..."
echo "==========================================" > "$REPORT_FILE"
echo "Android 第三方 App 廣告與追蹤器掃描報告" >> "$REPORT_FILE"
echo "掃描時間：$(date '+%Y-%m-%d %H:%M:%S')" >> "$REPORT_FILE"
echo "==========================================" >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"

# 透過 adb shell 執行掃描並將結果寫入報告
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

# 賦予腳本執行權限
chmod +x ~/scan_ads.sh
```

---

## 第三步：日常使用方式

日後每次安裝新 App 想定期檢查時，只需依照以下兩個步驟操作：

1. **連線本機 ADB**（開啟手機「開發人員選項」>「無線偵錯」查看目前埠號）：
   ```bash
   adb connect 127.0.0.1:連線埠號
   ```
2. **執行掃描腳本**：
   ```bash
   ./scan_ads.sh
   ```

執行完畢後，直接打開手機內建的 **「Files / 檔案管理」App >「下載（Download）」**，就能看到以 `App_Tracker_Report_日期時間.txt` 命名的完整清單。


---

# Android 廣告與追蹤器 SDK 自動化掃描腳本（含中文 App 名稱解析 + NextDNS 規則）

本升級版腳本透過 Termux 端的 `aapt` 工具解析 APK 標頭，讓掃描報告能直接顯示 **App 的中文名稱（例如：《Block Puzzle：Bloom Journey》）** 與對應的套件 ID，並自動儲存至手機的 **下載（Download）** 資料夾。

---

## 第一步：安裝必要套件（包含 `aapt` 解析工具）

開啟 Termux，執行以下指令安裝 ADB、解壓縮工具與 Android 資源解析工具（`aapt`）：

```bash
termux-setup-storage
pkg update && pkg upgrade -y
pkg install android-tools unzip aapt -y
```

---

## 第二步：建立升級版掃描腳本 `scan_ads.sh`

將以下**整段指令**複製並貼入 Termux 中執行，系統會自動建立支援中文名稱解析的 `scan_ads.sh`：

```bash
cat << 'EOF' > ~/scan_ads.sh
#!/data/data/com.termux/files/usr/bin/bash

# 設定輸出報告路徑（存放在手機內部儲存空間的 Download 資料夾）
REPORT_DIR="$HOME/storage/downloads"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
REPORT_FILE="$REPORT_DIR/App_Tracker_Report_$TIMESTAMP.txt"

# 檢查 ADB 連線狀態
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

# 定義要偵測的廣告與追蹤網域特徵
DOMAINS="pangle\.io|applovin\.com|unityads\.unity3d\.com|mbridge\.com|vungle\.com|ironsrc\.com|inmobi\.com|adcolony\.com|chartboost\.com|appsflyer\.com|adjust\.com|branch\.io|umeng\.com|doubleclick\.net|googlesyndication\.com"

count=0
# 透過 ADB 取得第三方 App 清單與 APK 路徑
while IFS='|' read -r pkg apk; do
  [ -z "$pkg" ] && continue
  # 在 Android 端直接檢查 dex 檔案是否包含目標網域
  found=$(adb shell "unzip -p '$apk' classes*.dex 2>/dev/null | grep -oaE '$DOMAINS' | sort -u | tr '\n' ' '" </dev/null)
  
  if [ -n "$found" ]; then
    count=$((count + 1))
    # 透過 ADB 讀取 APK 標頭給 Termux 的 aapt 解析中文 App 名稱（不需複製整支 APK）
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

# 賦予腳本執行權限
chmod +x ~/scan_ads.sh
```

---

## 第三步：執行腳本與檢視報告

1. **連線本機 ADB**（開啟手機「開發人員選項」>「無線偵錯」查看目前埠號）：
   ```bash
   adb connect 127.0.0.1:連線埠號
   ```
2. **執行掃描腳本**：
   ```bash
   ./scan_ads.sh
   ```
3. 執行結束後，打開手機 **「檔案管理」>「下載（Download）」**，開啟 `App_Tracker_Report_日期時間.txt` 即可檢視包含中文 App 名稱的完整報告。

---

## 附錄：NextDNS 黑名單批量阻擋清單

針對上述腳本常抓出的廣告與追蹤器網域，你可以直接登入 **NextDNS 網頁後台** > 切換至 **「黑名單（Denylist）」** 分頁，將以下網域逐一加入（NextDNS 會自動套用包含所有子網域的萬用字元阻擋規則）：

```text
pangle.io
applovin.com
applvn.com
://unity3d.com
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


# Android 廣告與追蹤器 SDK 終極管理手冊（含白名單掃描 + 批次權限凍結）

本手冊包含兩支自動化工具：
1. **`scan_ads.sh`**：支援「排除信任白名單」與「中文 App 名稱解析」，掃描速度更快並自動輸出報告至下載資料夾。
2. **`limit_apps.sh`**：讀取名單並透過 ADB 一鍵限制指定 App 的背景執行與背景喚醒權限，徹底杜絕偷跑流量。

---

## 第一步：建立「排除白名單」與升級版掃描腳本 `scan_ads.sh`

### 1. 建立信任白名單檔案（`whitelist.txt`）
將你信任且不想每次花時間掃描的 App 套件名稱（例如銀行、通訊軟體、Termux 本身）寫入白名單，可大幅縮短掃描時間：

```bash
cat << 'EOF' > ~/whitelist.txt
com.termux
com.whatsapp
jp.naver.line.android
com.google.android.youtube
EOF
```
*(日後想新增跳過的 App，只需執行 `nano ~/whitelist.txt` 換行加入套件名稱即可)*

### 2. 建立支援白名單的掃描腳本 `scan_ads.sh`
複製以下整段指令貼入 Termux 執行：

```bash
cat << 'EOF' > ~/scan_ads.sh
#!/data/data/com.termux/files/usr/bin/bash

REPORT_DIR="$HOME/storage/downloads"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
REPORT_FILE="$REPORT_DIR/App_Tracker_Report_$TIMESTAMP.txt"
WHITELIST="$HOME/whitelist.txt"

# 確保白名單檔案存在
touch "$WHITELIST"

# 檢查 ADB 連線狀態
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
  # 去除可能殘留的換行符號
  pkg=$(echo "$pkg" | tr -d '\r')
  apk=$(echo "$apk" | tr -d '\r')

  # 檢查是否在白名單內
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

---

## 第二步：建立「批次背景網路與追蹤凍結」腳本 `limit_apps.sh`

當你在報告中抓出不需要背景連網的遊戲或工具（例如 `com.andaman.games.block.puzzle.free`），可以將它們列入管制名單，用腳本一鍵限制其背景活動：

### 1. 建立要限制的 App 名單（`block_bg_apps.txt`）
```bash
cat << 'EOF' > ~/block_bg_apps.txt
com.andaman.games.block.puzzle.free
EOF
```

### 2. 建立批次凍結腳本 `limit_apps.sh`
```bash
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

echo "🔒 開始對名單內的 App 套用背景限制..."
while IFS= read -r pkg; do
  pkg=$(echo "$pkg" | tr -d '\r' | xargs)
  [ -z "$pkg" ] && continue

  echo "👉 正在限制：$pkg"
  # 1. 禁止任何形式的背景執行
  adb shell "cmd appops set $pkg RUN_ANY_IN_BACKGROUND ignore" </dev/null
  # 2. 禁止背景喚醒（防止定時醒來回傳追蹤數據）
  adb shell "cmd appops set $pkg WAKE_LOCK ignore" </dev/null
  # 3. 強制立即停止目前背景程序
  adb shell "am force-stop $pkg" </dev/null
done < "$TARGET_LIST"

echo "✅ 所有指定 App 的背景執行與喚醒權限皆已凍結！"
EOF

chmod +x ~/limit_apps.sh
```

---

## 第三步：日常維護指令速查

| 操作目的 | 執行指令 |
| :--- | :--- |
| **連接本機 ADB** | `adb connect 127.0.0.1:無線偵錯埠號` |
| **執行全機掃描並產生報告** | `./scan_ads.sh` |
| **編輯信任白名單（略過掃描）** | `nano ~/whitelist.txt` |
| **編輯背景限制名單** | `nano ~/block_bg_apps.txt` |
| **一鍵凍結名單內 App 背景活動** | `./limit_apps.sh` |
| **解除特定 App 的背景限制** | `adb shell cmd appops reset <套件名稱>` |


---
