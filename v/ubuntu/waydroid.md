# Ubuntu Waydroid 完整安裝、GAPPS、Intel ARM 轉譯與移除指南

本指南適用於 Ubuntu / Debian 系列 Linux，主要針對：

* Wayland 桌面
* Waydroid
* GAPPS / Google Play 商店
* Intel x86_64 CPU
* ARM App / 遊戲支援
* libhoudini ARM 轉譯器
* Google Play「裝置未獲得認證」
* Waydroid 網路問題
* 完整移除與重新安裝

---

# 一、安裝前確認

## 1. 確認 Ubuntu 使用 Wayland

執行：

```bash
echo "$XDG_SESSION_TYPE"
```

應該看到：

```text
wayland
```

如果看到：

```text
x11
```

請先登出，在 Ubuntu 登入畫面選擇 Wayland Session 後再登入。

---

## 2. 確認 CPU 架構

執行：

```bash
uname -m
```

Intel / AMD 64 位元電腦通常會顯示：

```text
x86_64
```

本指南的 `libhoudini` 部分主要針對 x86_64。

---

# 二、如果之前安裝過 Waydroid：先完整移除

⚠️ **本區會刪除 Waydroid 的 Android 系統、App、設定及使用者資料。**

如果你是第一次安裝，可以直接跳到「第三部分」。

## 1. 停止 Waydroid

```bash
waydroid session stop 2>/dev/null || true
sudo waydroid container stop 2>/dev/null || true
sudo systemctl stop waydroid-container.service 2>/dev/null || true
```

---

## 2. 移除 Waydroid 套件

```bash
sudo apt purge waydroid -y
sudo apt autoremove -y
```

---

## 3. 刪除 Waydroid 資料

```bash
sudo rm -rf /var/lib/waydroid
sudo rm -rf /home/.waydroid
rm -rf "$HOME/waydroid"
rm -rf "$HOME/.share/waydroid"
rm -rf "$HOME/.local/share/waydroid"
rm -f "$HOME"/.local/share/applications/*waydroid* 2>/dev/null || true
```

---

## 4. 重新開機

```bash
sudo reboot
```

重新登入 Ubuntu 後再繼續。

---

# 三、安裝 Waydroid

## 1. 安裝基本工具

```bash
sudo apt update
sudo apt install curl ca-certificates -y
```

---

## 2. 加入 Waydroid 官方套件庫

```bash
curl -s https://repo.waydro.id | sudo bash
```

然後：

```bash
sudo apt update
```

---

## 3. 安裝 Waydroid

```bash
sudo apt install waydroid -y
```

確認版本：

```bash
waydroid --version
```

---

# 四、初始化 Waydroid + GAPPS

如果需要：

* Google Play 商店
* Google Play Services
* Google 帳號登入
* Google 相關 App

請使用 GAPPS。

第一次初始化直接執行：

```bash
sudo waydroid init -s GAPPS
```

等待下載及初始化完成。

---

## 如果之前初始化過，需要重新初始化

⚠️ `-f` 是強制重新初始化。

```bash
sudo waydroid init -f -s GAPPS
```

不要在正常第一次安裝時額外使用 `-f`。

---

# 五、安裝 Intel ARM 轉譯器 libhoudini

⚠️ 這一部分是第三方工具，不是 Waydroid 官方核心套件。

`waydroid_script` 目前提供：

* `libhoudini`
* `libndk`

其中專案本身將 `libhoudini` 定位為較適合 Intel 的 ARM translation。

⚠️ ARM 轉譯不代表所有 ARM App 都能正常執行。部分遊戲仍可能因圖形、DRM、CPU 指令集或 App 本身限制而無法運作。

---

## 1. 安裝必要套件

```bash
sudo apt update
sudo apt install git lzip python3 python3-pip python3-venv -y
```

---

## 2. 下載 waydroid_script

```bash
cd "$HOME"
rm -rf waydroid_script
git clone https://github.com/casualsnek/waydroid_script.git
cd waydroid_script
```

---

## 3. 建立 Python 虛擬環境

```bash
python3 -m venv venv
```

---

## 4. 安裝 Python 相依套件

```bash
venv/bin/pip install -r requirements.txt
```

---

## 5. 安裝 Intel ARM 轉譯器

```bash
sudo venv/bin/python3 main.py install libhoudini
```

等待安裝完成。

---

# 六、如果 libhoudini 安裝時出現 /tmp 空間不足

如果看到：

```text
OSError: [Errno 28] No space left on device
```

可以改用自己的硬碟暫存目錄。

```bash
mkdir -p "$HOME/waydroid_tmp"
```

然後：

```bash
sudo TMPDIR="$HOME/waydroid_tmp" \
venv/bin/python3 main.py install libhoudini
```

完成後：

```bash
rm -rf "$HOME/waydroid_tmp"
```

注意：

`TMPDIR` 只是 `/tmp` 空間不足時的 workaround，正常情況不需要。

---

# 七、啟動 Waydroid

## 1. 啟動 Container

```bash
sudo systemctl enable --now waydroid-container.service
```

確認服務：

```bash
systemctl is-active waydroid-container.service
```

正常應該顯示：

```text
active
```

---

## 2. 啟動 Android Session

⚠️ 這裡不要使用 sudo。

```bash
waydroid session start
```

等待看到類似：

```text
Android with user 0 is ready
```

---

## 3. 開啟完整 Android 介面

另開一個終端機：

```bash
waydroid show-full-ui
```

---

# 八、確認 Waydroid 是否正常

執行：

```bash
waydroid status
```

也可以查看：

```bash
sudo systemctl status waydroid-container.service
```

查看 Waydroid Log：

```bash
waydroid log
```

查看 Android Logcat：

```bash
sudo waydroid logcat
```

---

# 九、建立一個方便使用的啟動方式

如果不想每次手動啟動 Session，可以建立簡單指令：

```bash
mkdir -p "$HOME/.local/bin"

cat > "$HOME/.local/bin/start-waydroid" <<'EOF'
#!/bin/bash

sudo systemctl start waydroid-container.service
sleep 2
waydroid session start >/tmp/waydroid-session.log 2>&1 &
sleep 3
waydroid show-full-ui
EOF

chmod +x "$HOME/.local/bin/start-waydroid"
```

以後可以執行：

```bash
"$HOME/.local/bin/start-waydroid"
```

---

# 十、Android 沒有網路

先確認是否存在 `waydroid0`：

```bash
ip addr show waydroid0
```

如果看到 `waydroid0`，再檢查 UFW：

```bash
sudo ufw status
```

如果你有啟用 UFW，可以按照 Waydroid 官方網路排錯方式設定：

```bash
sudo ufw allow 53
sudo ufw allow 67
sudo ufw default allow FORWARD
```

然後：

```bash
sudo systemctl restart waydroid-container.service
```

再重新啟動 Session：

```bash
waydroid session stop
waydroid session start
```

---

## ⚠️ 不要隨便執行 ufw reset

不建議把：

```bash
sudo ufw reset
```

當成一般 Waydroid 修復步驟。

因為它會重設 UFW 規則，可能把你原本設定的防火牆規則全部清除。

---

# 十一、Google Play 顯示「裝置未獲得認證」

第一次使用 GAPPS 時，可能看到：

```text
裝置未獲得 Play Protect 認證
```

這通常需要把 Waydroid 的 Android ID 註冊到 Google。

---

## 方法 A：使用 waydroid_script

先進入之前下載的目錄：

```bash
cd "$HOME/waydroid_script"
```

執行：

```bash
sudo venv/bin/python3 main.py certified
```

它會取得 Google 裝置認證所需的 Android ID。

---

## 方法 B：使用 Waydroid Shell

如果方法 A 不方便，可以使用：

```bash
sudo waydroid shell -- sh -c "sqlite3 /data/data/*/*/gservices.db 'select value from main where name = \"android_id\";'"
```

複製輸出的 Android ID。

---

# 十二、向 Google 註冊 Android ID

使用瀏覽器前往：

Google Android 裝置認證頁面：

https://www.google.com/android/uncertified/

登入你的 Google 帳號。

將剛才取得的 Android ID 貼上並註冊。

---

# 十三、註冊後重新啟動 Waydroid

等待 Google 端更新後：

```bash
waydroid session stop
```

再：

```bash
waydroid session start
```

然後：

```bash
waydroid show-full-ui
```

如果 Play 商店仍顯示未認證，可以等待一段時間後再重新啟動。

---

# 十四、ARM App 無法啟動

如果：

* Waydroid 本身正常
* Google Play 正常
* x86 App 可以使用
* 但 ARM App 開啟後閃退

先確認 libhoudini：

```bash
cd "$HOME/waydroid_script"
sudo venv/bin/python3 main.py install libhoudini
```

然後重新啟動：

```bash
waydroid session stop
sudo systemctl restart waydroid-container.service
waydroid session start
```

---

# 十五、如果 ARM App 還是不能使用

查看 Log：

```bash
sudo waydroid logcat
```

或：

```bash
waydroid log
```

特別注意：

```text
SIGSEGV
SIGILL
native bridge
houdini
libhoudini
arm64
armeabi
```

等錯誤。

---

## 重要限制

即使 `libhoudini` 安裝成功，也不能保證所有 ARM App / 遊戲都可以執行。

可能造成問題的因素包括：

* App 只有 ARM64 原生程式
* App 使用特殊 ARM CPU 指令
* Google Play Integrity / SafetyNet
* DRM
* GPU / Vulkan
* 遊戲反作弊
* Waydroid Android 版本
* libhoudini 本身相容性

因此：

```text
libhoudini 安裝成功
```

不等於：

```text
所有 ARM App 都能執行
```

目前 `waydroid_script` GitHub 仍有 libhoudini 在 Android 13 及部分 ARM App 上的相容性問題回報，因此遇到個別 App 無法執行時，不一定代表 Waydroid 安裝錯誤。

---

# 十六、停止 Waydroid

正常停止：

```bash
waydroid session stop
```

如果 Container 仍在運作：

```bash
sudo systemctl stop waydroid-container.service
```

---

# 十七、重新啟動 Waydroid

```bash
sudo systemctl restart waydroid-container.service
waydroid session start
```

然後：

```bash
waydroid show-full-ui
```

---

# 十八、完整移除 Waydroid

⚠️ **以下會刪除所有 Android App、帳號、設定、檔案及 Waydroid 系統資料。**

如果確定要全部刪除：

```bash
waydroid session stop 2>/dev/null || true
sudo waydroid container stop 2>/dev/null || true
sudo systemctl stop waydroid-container.service 2>/dev/null || true

sudo apt purge waydroid -y
sudo apt autoremove -y

sudo rm -rf /var/lib/waydroid
sudo rm -rf /home/.waydroid
rm -rf "$HOME/waydroid"
rm -rf "$HOME/.share/waydroid"
rm -rf "$HOME/.local/share/waydroid"
rm -f "$HOME"/.local/share/applications/*waydroid* 2>/dev/null || true
```

如果也不再需要 `waydroid_script`：

```bash
rm -rf "$HOME/waydroid_script"
rm -rf "$HOME/waydroid_tmp"
rm -f "$HOME/.local/bin/start-waydroid"
```

最後：

```bash
sudo reboot
```

---

# 十九、快速重新安裝版

如果 Ubuntu 已經是 Wayland，而且不需要先清除舊版，可以直接按照以下順序：

```bash
sudo apt update
sudo apt install curl ca-certificates -y

curl -s https://repo.waydro.id | sudo bash

sudo apt update
sudo apt install waydroid -y

sudo waydroid init -s GAPPS

sudo apt install git lzip python3 python3-pip python3-venv -y

cd "$HOME"
rm -rf waydroid_script
git clone https://github.com/casualsnek/waydroid_script.git

cd waydroid_script

python3 -m venv venv
venv/bin/pip install -r requirements.txt

sudo venv/bin/python3 main.py install libhoudini

sudo systemctl enable --now waydroid-container.service

waydroid session start
```

另開終端機：

```bash
waydroid show-full-ui
```

---

# 二十、安裝完成後的檢查清單

依序執行：

```bash
echo "$XDG_SESSION_TYPE"
```

應為：

```text
wayland
```

然後：

```bash
uname -m
```

Intel/AMD 64 位元通常為：

```text
x86_64
```

確認 Waydroid：

```bash
waydroid status
```

確認 Container：

```bash
systemctl is-active waydroid-container.service
```

確認網路介面：

```bash
ip addr show waydroid0
```

確認 ARM translation：

```bash
cd "$HOME/waydroid_script"
sudo venv/bin/python3 main.py certified
```

確認 Log：

```bash
waydroid log
```

確認 Android Logcat：

```bash
sudo waydroid logcat
```

---

# 二十一、最重要的注意事項

1. 第一次安裝 GAPPS 使用：

```bash
sudo waydroid init -s GAPPS
```

2. 只有重新初始化時才需要：

```bash
sudo waydroid init -f -s GAPPS
```

3. Waydroid Session 不要使用 sudo：

```bash
waydroid session start
```

4. Container 才使用 sudo：

```bash
sudo systemctl start waydroid-container.service
```

5. Intel x86_64 可以嘗試：

```bash
sudo venv/bin/python3 main.py install libhoudini
```

6. `libhoudini` 是第三方 ARM translation，不是 Waydroid 官方核心套件。

7. 不要把：

```bash
sudo ufw reset
```

當成一般網路修復方法。

8. Google Play 未認證時，取得 Android ID 後，需要到 Google Android 裝置認證頁面註冊。

9. 如果 ARM App 不能執行，不代表 Waydroid 一定安裝失敗；可能是 ARM translation、GPU、DRM、Play Integrity、遊戲反作弊或 App 相容性問題。

10. 完整移除前，確認沒有需要保留的 Android 資料。

---

# 二十二、最終結構

正常安裝完成後，大致為：

Ubuntu
↓
Wayland
↓
Waydroid Container
↓
Android
├── GAPPS
├── Google Play
└── ARM Translation
└── libhoudini

啟動：

```bash
sudo systemctl start waydroid-container.service
waydroid session start
waydroid show-full-ui
```

停止：

```bash
waydroid session stop
sudo systemctl stop waydroid-container.service
```

查看狀態：

```bash
waydroid status
```

查看 Log：

```bash
waydroid log
sudo waydroid logcat
```
