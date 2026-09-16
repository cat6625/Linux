------------------------------
## Ubuntu Waydroid 完整安裝與移除指南
本指南包含 Waydroid 的乾淨安裝（含 GAPPS 與 Intel ARM 轉譯器）以及徹底移除（不留殘留檔案）的完整步驟。
------------------------------
## 🛑 第一部分：徹底移除 Waydroid（全新重置）
如果您先前安裝過 Waydroid 且有殘留設定，請先執行此部分以確保系統乾淨。
## 1. 停止所有 Waydroid 服務

sudo waydroid session stop
sudo waydroid container stop
sudo systemctl stop waydroid-container.service

## 2. 移除系統套件

sudo apt purge waydroid -y
sudo apt autoremove -y

## 3. 刪除所有殘留的資料與設定檔
(此步驟會清除所有 Android 內的資料與應用程式)

sudo rm -rf /var/lib/waydroid /home/.waydroid ~/waydroid ~/.share/waydroid ~/.local/share/waydroid

## 4. 清除應用程式選單的圖志捷徑

rm -f ~/.local/share/applications/*waydroid*

------------------------------
## 🚀 第二部分：全新安裝 Waydroid (含 Intel ARM 轉譯器)

⚠️ 注意：請確保您的 Ubuntu 目前處於 Wayland 顯示環境下（可在終端機輸入 echo $XDG_SESSION_TYPE 檢查）。

## 1. 新增官方儲存庫並安裝 Waydroid

sudo apt update

sudo apt install curl ca-certificates -y

curl -s https://waydroid.tech | sudo bash

sudo apt update

sudo apt install waydroid -y

## 2. 初始化 Waydroid（下載 GAPPS 版本）
若您需要使用 Google Play 商店與服務，請指定下載 GAPPS 映像檔：

sudo waydroid init -f -s GAPPS

## 3. 安裝 Intel 專用 ARM 轉譯器 (libhoudini)
此步驟使用社群腳本安裝轉譯器，並加入 TMPDIR 環境變數以防止 /tmp 記憶體空間不足（OSError 28）的問題。

# 1. 安裝相依套件
sudo apt install git lzip python3 python3-pip python3-venv -y
# 2. 下載轉譯器腳本專案
cd ~

git clone https://github.com/casualsnek/waydroid_script

cd waydroid_script
# 3. 建立並設定 Python 虛擬環境
python3 -m venv venv

sudo venv/bin/pip install -r requirements.txt
# 4. 建立硬碟暫存資料夾並執行安裝 (Intel 專用 libhoudini)
mkdir -p ~/waydroid_tmp

sudo TMPDIR=/home/$USER/waydroid_tmp venv/bin/python3 main.py install libhoudini
# 5. 清理硬碟暫存資料夾
rm -rf ~/waydroid_tmp

## 4. 啟動服務並運行

# 啟動並開機隨啟背景服務
sudo systemctl enable --now waydroid-container.service

現在您可以從 Ubuntu 的應用程式選單點擊 Waydroid 圖示，或在終端機輸入以下指令啟動 Android 介面：

waydroid show-full-ui

------------------------------
## 🛠️ 第三部分：常見問題微調## Q1. Android 顯示沒有網路連線？
在 Ubuntu 終端機重啟防火牆即可解決：

sudo systemctl restart ufw

## Q2. 開啟 Google Play 商店提示「裝置未獲得認證」？
因為是模擬器，必須手動向 Google 註冊您的 Android ID：

   1. 在 Ubuntu 終端機執行以下指令獲取 ID：
   
   sudo waydroid shell getprop ro.com.google.clientidbase.amzn
   
   (如果上述無輸出，可嘗試 sudo waydroid shell settings get secure android_id)
   2. 複製畫面上出現的一串數字/字母 ID。
   3. 前往 [Google 裝置註冊網頁](https://www.google.com/android/uncertified/)，登入您的 Google 帳號並貼上該 ID 進行註冊。
   4. 註冊後，等待約 5~20 分鐘，將 Waydroid 重啟或清除 Play 商店快取即可正常登入。
