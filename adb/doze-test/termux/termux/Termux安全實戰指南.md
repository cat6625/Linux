# Termux 安全實戰指南與常見情境

## 一、核心觀念：了解 Termux 的權限邊界

1. **Android App 沙盒**  
   Termux 預設在 Android 的 App 沙盒中執行。一般 App 無法直接讀取 Termux 的私有家目錄（通常是 `$HOME`，例如 `/data/data/com.termux/files/home`），除非裝置已取得 root、系統有特殊設定，或使用者額外授權。

2. **Termux 內部的程序通常共用同一個 App 身分**  
   Termux 裡執行的指令、Python 套件和腳本多數以同一個 Android App UID 運行，彼此之間沒有傳統 Linux 多使用者的權限隔離。它們可使用 Termux 已取得的 Android 權限，但 **不會因此自動取得 Android root 權限**。

3. **共用儲存空間的授權範圍**  
   執行 `termux-setup-storage` 後，Termux 會在 `$HOME/storage` 建立指向 Android 共用儲存空間的連結（`shared`、`download`、`dcim`、`documents`），讓 Termux 內的程式透過這些路徑讀寫相簿、下載與文件資料夾。實際可存取的範圍仍受 Android 版本、系統權限與 Scoped Storage 限制影響。

---

## 二、五項安全守則與實作範例

### 1. 從可信管道安裝並保持更新

**建議做法**  
- 只從官方管道取得 Termux：  
  - **F‑Droid**（https://f-droid.org/packages/com.termux/）  
  - **GitHub Releases**（https://github.com/termux/termux-app/releases）  
  - 若使用 Google Play 版，先確認它是由 Termux 官方維護且與 F‑Droid 版本相容。  
- 外掛（如 Termux:API、Termux:Styling）必須與 Termux 本體使用相同簽章；混裝不同來源的 APK 會導致升級失敗或權限不一致。  

**避免**：下載不明來源、所謂「破解版」或「漢化版」APK，這些往往植入後門或惡意程式。  

**更新套件**（建議每日或每次開機後執行）：

```sh
pkg update && pkg upgrade
```

### 2. 程式與金鑰留在私有家目錄；結果寫入共用儲存

**原則**  
- **程式碼、腳本、設定檔** 放在 Termux 私有目錄（`~/`）或子目錄（如 `~/my_scripts`）。  
- **產出報告、日志、匯出檔** 若需要讓其他 App 查看，才寫入 `~/storage/shared`（或 `~/storage/downloads`）。  

**避免**：把重要腳本直接放在 `~/storage/shared/downloads` 並以 `bash ~/storage/shared/downloads/run.sh` 執行，因為任何取得「所有檔案存取權」的 App 都能修改此檔，增加被植入惡意程式的風險。  

**示範**：

```sh
# 建立私有腳本目錄
mkdir -p ~/my_scripts
# 編寫腳本（使用內建編輯器 nano、vim，或透過 SAF 的檔案管理器）
nano ~/my_scripts/run.sh
# 產生報告並寫入共用儲存
python3 ~/my_scripts/analyze.py > ~/storage/downloads/output/report.txt
```

> **提示**：若使用外部檔案管理器（如 **Acode**、**NMM File Manager**），必須先透過 Android 系統的檔案選擇器（SAF）授權才能直接編輯 Termux 私有目錄。不同 app 的支援度不一，請先測試是否能正常讀寫。

### 3. 小心刪除指令與外部腳本

**刪除指令安全化**  

```sh
# 檢查變數是否為空
if [ -z "$FOLDER_NAME" ]; then
    echo "錯誤：FOLDER_NAME 未設定"
    exit 1
fi
target="$HOME/storage/shared/$FOLDER_NAME"
echo "即將刪除：$target"
# 先顯示內容確認
ls -l "$target"
# 再使用互動式刪除或限制深度
rm -ri "$target"
```

**外部腳本執行前檢視**  

```sh
# 下載腳本
curl -fsSL https://example.com/install.sh -o install.sh
# 先檢視內容
less install.sh
# 確認無惡意指令後執行
bash install.sh
```

**避免**：直接 `curl … | bash`、`wget -O- … | sh`，因為您無法先審查程式碼。

### 4. 保護 SSH 金鑰與其他祕密

| 類型 | 建議儲存位置 | 權限設定 |
|------|--------------|----------|
| SSH 私鑰 | `~/.ssh/` | `chmod 700 ~/.ssh && chmod 600 ~/.ssh/id_*` |
| API / Token | `~/.env`（或 `~/my_secrets/`） | `chmod 600 ~/.env` |
| 敏感腳本 | 私有目錄下子資料夾 | 同上，避免放在共用儲存空間 |

**範例**：

```sh
# 建立 SSH 目錄
mkdir -p ~/.ssh
chmod 700 ~/.ssh
# 移動私鑰
mv ~/downloads/id_ed25519 ~/.ssh/
chmod 600 ~/.ssh/id_ed25519
# 建立環境變數檔案
cat > ~/.env <<EOF
API_KEY=your_api_key_here
SECRET=your_secret_here
EOF
chmod 600 ~/.env
```

> **提醒**：即使檔案權限已受限制，也請避免將祕密內容推送至 Git、雲端同步或備份至不安全的外部儲存空間。

### 5. 控管本機網路服務與無線除錯（ADB）

| 服務 | 啟動方式 | 建議安全措施 |
|------|----------|--------------|
| **SSH (sshd)** | `sshd`（在 Termux 中安裝 `openssh`） | 使用 **公鑰驗證**，關閉密碼登入；僅在需要時啟動，結束後 `pkill sshd`。 |
| **HTTP 文件分享** | `python -m http.server 8000` | 若僅供本機使用，加入 `--bind 127.0.0.1` 限制只接受本機連線；若要允許局域網，使用強密碼或簡易認證。 |
| **ADB 無線除錯** | `adb tcpip 5555`、`adb connect <IP>` | 完成測試後立即在 Android 「開發者選項」中關閉 **無線除錯**，或使用 `adb disconnect`。 |

**示範**：

```sh
# 啟動 SSH（僅允許公鑰）
sshd -p 2222 -D &
# 停止 SSH
pkill sshd

# 本機 HTTP 服務（僅本機可訪問）
python -m http.server 8000 --bind 127.0.0.1

# 解除 ADB 無線連線
adb disconnect
# 然後在系統設定中關閉無線除錯
```

> **注意**：即使服務僅綁定 `127.0.0.1`，同一台手機上其他 App 仍可透過本機迴路介面連線；因此在公開網路環境中仍建議關閉不必要的服務。

---

## 三、日常安全檢查清單（可直接複製貼上）

- [ ] **安裝來源**：只從 F‑Droid、GitHub Release 或官方說明的渠道安裝 Termux 與外掛。  
- [ ] **授權存取**：僅在需要讀寫相簿、下載或文件時執行 `termux-setup-storage`，完成後視需求在 Android 設定中撤銷「檔案與媒體」權限。  
- [ ] **檔案位置**：所有腳本、程式碼、金鑰與設定檔都放在 `~/`（私有目錄）內；輸出報告、圖像或分享檔案才放在 `~/storage/shared`（或 `~/storage/downloads`）。  
- [ ] **編輯工具**：使用內建編輯器（`nano`、`vim`）或已證實支援 SAF 的檔案管理器；確保授權後才能編輯私有檔案。  
- [ ] **刪除前檢查**：檢查變數、路徑與最終刪除範圍；必要時使用 `rm -i` 或手動確認 `ls` 後再執行。  
- [ ] **外部腳本**：下載後先檢視內容，確認安全才執行；絕不使用 `curl … | bash` 直接執行。  
- [ ] **金鑰與密碼**：放在 `~/.ssh`、`~/.env` 或其他私有子目錄，並設定 `chmod 600`（或更嚴格）。不要把它們放在共用儲存或上傳至雲端同步。  
- [ ] **網路服務**：使用完 SSH、HTTP、ADB 等服務立即關閉；關閉無線除錯，僅在受信任網路下啟用。  
- [ ] **系統更新**：定期執行 `pkg update && pkg upgrade`，尤其是 OpenSSL、OpenSSH、Python 等核心套件。  

---  

**結語**  
遵循上述原則與檢查清單，能在 Android 手機上安全地使用 Termux，減少因共用儲存權限、外部腳本或未受控網路服務而導致的風險。適時檢視權限、更新套件、以及將敏感資料嚴格保留在私有目錄，是維護 Termux 環境安全的關鍵。祝使用愉快、安心！
