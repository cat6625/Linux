# Linux 健保卡讀卡機安裝與設定手冊

適用設備：EZ100PU 晶片讀卡機  
適用環境：Linux 64-bit（Ubuntu / Debian 系列）  
瀏覽器：Google Chrome、Mozilla Firefox

---

## 目錄

1. [安裝前準備](#1-安裝前準備)
2. [EZ100PU 讀卡機驅動程式安裝](#2-ez100pu-讀卡機驅動程式安裝)
3. [安裝 PCSC 與相關套件](#3-安裝-pcsc-與相關套件)
4. [測試讀卡機是否正常](#4-測試讀卡機是否正常)
5. [安裝健保卡網路服務元件](#5-安裝健保卡網路服務元件)
6. [Chrome 憑證設定](#6-chrome-憑證設定)
7. [Firefox 憑證設定](#7-firefox-憑證設定)
8. [健保卡憑證移除](#8-健保卡憑證移除)
9. [確認憑證是否移除](#9-確認憑證是否移除)
10. [常用指令整理](#10-常用指令整理)

---

## 1. 安裝前準備

安裝前請確認：

- Linux 系統為 64-bit。
- 已具備 sudo 管理員權限。
- 已連接 EZ100PU 晶片讀卡機。
- 已安裝 Firefox 或 Google Chrome。
- 電腦可以正常連接網際網路。

本安裝流程分成三個部分：

1. 安裝讀卡機驅動程式。
2. 安裝健保卡網路服務元件。
3. 設定瀏覽器憑證。

---

## 2. EZ100PU 讀卡機驅動程式安裝

### 步驟 1：下載驅動程式

開啟終端機（Ctrl + Alt + T），執行：

```bash
git clone https://github.com/chihchun/ez100pu
```

### 步驟 2：進入驅動程式目錄

```bash
cd ez100pu/driver_ezusb_v1.5.3_for_64_bit/
```

### 步驟 3：設定安裝檔案執行權限

```bash
chmod +x install check_env
```

### 步驟 4：執行安裝程式

```bash
sudo ./install
```

### 步驟 5：重新啟動讀卡機服務

```bash
sudo systemctl restart pcscd
```

---

## 3. 安裝 PCSC 與相關套件

系統必須具備處理晶片卡讀取（PC/SC）、安全加密通訊（OpenSSL）及憑證管理所需的套件。

### 步驟 1：更新套件清單

```bash
sudo apt update
```

### 步驟 2：安裝必要套件

```bash
sudo apt install pcscd libpcsclite1 pcsc-tools openssl libnss3-tools
```

套件用途：

| 套件 | 用途 |
|---|---|
| pcscd | 晶片卡讀取服務 |
| libpcsclite1 | PC/SC 函式庫 |
| pcsc-tools | 晶片卡測試工具 |
| openssl | SSL/TLS 與憑證相關工具 |
| libnss3-tools | 瀏覽器 NSS 憑證管理工具 |

### 步驟 3：啟用 PCSC 服務

```bash
sudo systemctl enable --now pcscd
```

---

## 4. 測試讀卡機是否正常

### 步驟 1：執行讀卡機測試

```bash
pcsc_scan
```

### 步驟 2：確認讀卡機狀態

將健保卡插入讀卡機，觀察終端機是否出現讀卡機及卡片相關資訊。

若能正常偵測讀卡機與晶片卡，表示 PC/SC 讀卡服務已能正常運作。

### 步驟 3：結束測試

按下：

```text
Ctrl + C
```

即可退出測試。

---

## 5. 安裝健保卡網路服務元件

### 官方網站

衛生福利部中央健康保險署－個人健保資料網路服務作業：

https://eservice.nhi.gov.tw/personal1/system/HealthCard.aspx

### 步驟 1：下載 Linux 安裝檔

```bash
wget https://cloudicweb.nhi.gov.tw/cloudic/System/SMC/CMS_mNHIICC_Setup.Linux_112.zip
```

### 步驟 2：解壓縮 ZIP 檔案

```bash
unzip CMS_mNHIICC_Setup.Linux_112.zip
```

### 步驟 3：解壓縮 TAR.XZ 檔案

```bash
tar -xvf mLNHIICC_Setup.*.tar.xz
```

### 步驟 4：進入安裝目錄

```bash
cd mLNHIICC_Setup/
```

### 步驟 5：執行安裝程式

```bash
sudo ./Install
```

依照安裝程式提示完成安裝。

### 步驟 6：開啟元件測試網頁

請在 Firefox 或 Chrome 的網址列輸入：

```text
file:///usr/local/share/NHIICC/web/ESample.html
```

確認健保卡元件是否能正常運作。

---

## 6. Google Chrome 憑證設定

### 6.1 安裝憑證管理工具

若尚未安裝 libnss3-tools，請執行：

```bash
sudo apt update
sudo apt install libnss3-tools
```

### 6.2 進入健保卡憑證目錄

```bash
cd /usr/local/share/NHIICC/cert/
```

### 6.3 將健保署根憑證匯入 Chrome

使用以下指令，將 NHIRootCA.crt 匯入 Chrome 預設的 NSS 憑證資料庫：

```bash
certutil -d sql:$HOME/.pki/nssdb -A -t "C,," -n "NHIICC CA" -i NHIRootCA.crt
```

憑證資訊：

| 項目 | 內容 |
|---|---|
| 憑證名稱 | NHIRootCA.crt |
| 憑證暱稱 | NHIICC CA |
| 憑證資料庫 | $HOME/.pki/nssdb |
| 信任設定 | C,, |

---

## 7. Mozilla Firefox 憑證設定

Firefox 可以透過終端機指令或圖形介面匯入憑證。

### 方法一：使用終端機匯入

執行以下指令，搜尋 Firefox 所有設定檔中的 cert9.db，並匯入健保署根憑證：

```bash
find $HOME/.mozilla/firefox/ -name "cert9.db" -execdir certutil -A -n "NHIICC CA" -t "C,," -i /usr/local/share/NHIICC/cert/NHIRootCA.crt -d . \;
```

### 方法二：使用 Firefox 圖形介面匯入

#### 步驟 1：開啟憑證管理員

1. 開啟 Firefox。
2. 點擊右上角「選單（三條橫線）」。
3. 選擇「設定」（Settings）。
4. 左側選擇「隱私與安全」（Privacy & Security）。
5. 向下找到「憑證」（Certificates）。
6. 點擊「檢視憑證」（View Certificates）。

#### 步驟 2：匯入健保署根憑證

1. 切換到「憑證機構」（Authorities）分頁。
2. 點擊「匯入」（Import）。
3. 開啟以下資料夾：

```text
/usr/local/share/NHIICC/cert/
```

4. 找到以下憑證檔案：

```text
NHIRootCA.crt
```

5. 選取檔案並點擊「開啟」。

#### 步驟 3：設定憑證信任權限

匯入時，Firefox 會顯示憑證信任設定。

請勾選：

```text
信任此憑證機構以識別網站
(Trust this CA to identify websites)
```

最後點擊確定，完成憑證匯入。

---

## 8. 健保卡憑證移除

如果日後不再使用健保卡元件，或需要重新安裝憑證，可以將先前匯入的 NHIICC CA 憑證移除。

提供兩種方式：

- 方法一：透過終端機指令移除。
- 方法二：透過瀏覽器圖形介面移除。

### 8.1 使用終端機移除 Chrome 憑證

執行：

```bash
certutil -d sql:$HOME/.pki/nssdb -D -n "NHIICC CA"
```

說明：

- `-D`：刪除指定憑證。
- `-n`：指定憑證暱稱。
- `NHIICC CA`：先前匯入時使用的憑證名稱。

執行後若沒有錯誤訊息，通常代表指令已執行完成。

### 8.2 使用終端機移除 Firefox 憑證

執行：

```bash
find $HOME/.mozilla/firefox/ -name "cert9.db" -execdir certutil -D -n "NHIICC CA" -d . \;
```

此指令會搜尋使用者目錄下的 Firefox 憑證資料庫，並刪除名稱為 NHIICC CA 的憑證。

### 8.3 使用 Chrome 圖形介面移除憑證

1. 開啟 Google Chrome。
2. 點擊右上角「三個點」。
3. 選擇「設定」。
4. 點選「隱私權和安全性」（Privacy and security）。
5. 點選「安全性」（Security）。
6. 找到「管理憑證」（Manage certificates）。
7. 切換至「憑證機構」（Authorities）分頁。
8. 尋找 NHIICC CA 或健保署相關憑證。
9. 點擊憑證旁的更多動作。
10. 選擇「刪除」或「不信任」。

### 8.4 使用 Firefox 圖形介面移除憑證

1. 開啟 Firefox。
2. 點擊右上角「三條橫線」。
3. 選擇「設定」。
4. 點選「隱私與安全」（Privacy & Security）。
5. 向下找到「憑證」。
6. 點擊「檢視憑證」（View Certificates）。
7. 切換至「憑證機構」（Authorities）。
8. 找到 NHIICC CA。
9. 選取憑證。
10. 點擊「刪除或撤銷信任」（Delete or Distrust）。
11. 在確認視窗中點擊「確定」。

---

## 9. 確認憑證是否移除

### 9.1 檢查 Chrome 憑證資料庫

執行：

```bash
certutil -d sql:$HOME/.pki/nssdb -L
```

查看憑證清單。

如果清單中不再出現：

```text
NHIICC CA
```

表示該憑證已從 Chrome 使用的 NSS 資料庫移除。

### 9.2 檢查健保卡測試網頁

重新開啟 Chrome 或 Firefox，前往：

```text
file:///usr/local/share/NHIICC/web/ESample.html
```

確認測試頁面狀態。

依原始操作說明，憑證移除後，狀態應重新顯示紅色的：

```text
Not connected
```

---

## 10. 常用指令整理

以下整理安裝與維護時常用的指令，方便日後快速查閱。

### 10.1 系統套件

```bash
sudo apt update

sudo apt install pcscd libpcsclite1 pcsc-tools openssl libnss3-tools
```

### 10.2 PCSC 服務管理

啟用服務：

```bash
sudo systemctl enable --now pcscd
```

重新啟動服務：

```bash
sudo systemctl restart pcscd
```

### 10.3 讀卡機測試

```bash
pcsc_scan
```

結束測試：

```text
Ctrl + C
```

### 10.4 Chrome 憑證管理

匯入：

```bash
certutil -d sql:$HOME/.pki/nssdb -A -t "C,," -n "NHIICC CA" -i NHIRootCA.crt
```

移除：

```bash
certutil -d sql:$HOME/.pki/nssdb -D -n "NHIICC CA"
```

檢查：

```bash
certutil -d sql:$HOME/.pki/nssdb -L
```

### 10.5 Firefox 憑證管理

匯入：

```bash
find $HOME/.mozilla/firefox/ -name "cert9.db" -execdir certutil -A -n "NHIICC CA" -t "C,," -i /usr/local/share/NHIICC/cert/NHIRootCA.crt -d . \;
```

移除：

```bash
find $HOME/.mozilla/firefox/ -name "cert9.db" -execdir certutil -D -n "NHIICC CA" -d . \;
```

---

## 附錄：重要檔案與網址

### 健保卡相關網址

- 健保署個人健保資料網路服務：

  https://eservice.nhi.gov.tw/personal1/system/HealthCard.aspx

- EZ100PU 驅動程式：

  https://github.com/chihchun/ez100pu

- Linux 健保卡元件下載：

  https://cloudicweb.nhi.gov.tw/cloudic/System/SMC/CMS_mNHIICC_Setup.Linux_112.zip

### 重要系統路徑

| 路徑 | 用途 |
|---|---|
| `/usr/local/share/NHIICC/` | 健保卡元件安裝目錄 |
| `/usr/local/share/NHIICC/cert/` | 健保卡憑證目錄 |
| `/usr/local/share/NHIICC/web/ESample.html` | 健保卡測試網頁 |
| `$HOME/.pki/nssdb` | Chrome NSS 憑證資料庫 |
| `$HOME/.mozilla/firefox/` | Firefox 使用者設定檔 |

---

**文件備註**

1. 本文件依據原始安裝筆記重新編排。
2. 原始安裝指令與操作流程予以保留。
3. 不同 Linux 發行版、瀏覽器版本及健保署元件版本，可能存在操作差異。
4. 執行憑證匯入或刪除指令前，請先確認憑證檔案及憑證名稱。
5. 本文件所列安裝流程尚未逐一進行實機驗證。
