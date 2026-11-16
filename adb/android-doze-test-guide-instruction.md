測試方法 (關尋找手機，ubuntu adb wifi) 
做完 batterystats --reset後 ， ubuntu 立刻  suspend  
測試時間 完成 後 ，打開電腦 立刻紀錄 
ubuntu有時候會動喚醒，電腦自動suspend為15分

## 我的初步預想
```js
#!/bin/bash

TIMESTAMP=$(date +"%Y%m%d_%H%M")

OUT_DIR="$TIMESTAMP"
mkdir -p "$OUT_DIR"

# 準備工作
adb shell cmd role get-role-holders android.app.role.HOME
adb shell dumpsys deviceidle unforce
adb shell dumpsys batterystats --enable full-wake-history
adb shell dumpsys batterystats --reset
adb shell dumpsys meminfo com.sec.android.app.launcher > $OUT_DIR/mem_start.txt
adb shell dumpsys meminfo ch.deletescape.lawnchair.plah >> $OUT_DIR/mem_start.txt
adb shell dumpsys battery > $OUT_DIR/battery_start.txt



# ubuntu 立刻  suspend
systemctl suspend


# 連接 adb ( ip:port  不一樣要修正 ) 
adb  devices
adb  connect 192.168.1.142:44055

# 會遇到 adb: device offline
adb  devices
adb  connect 192.168.1.142:44055


# 紀錄
adb shell dumpsys batterystats --checkin  > $OUT_DIR/checkin.txt
adb shell dumpsys batterystats --history  > $OUT_DIR/history.txt
adb shell dumpsys deviceidle              > $OUT_DIR/deviceidle.txt
adb shell dumpsys batterystats            > $OUT_DIR/full.txt
adb shell cmd role get-role-holders android.app.role.HOME
adb shell dumpsys battery > $OUT_DIR/battery_end.txt 
adb shell dumpsys meminfo com.sec.android.app.launcher > $OUT_DIR/mem_end.txt
adb shell dumpsys meminfo ch.deletescape.lawnchair.plah >> $OUT_DIR/mem_end.txt

# 需要看網路時:
adb shell dumpsys netstats detail         > $OUT_DIR/netstats.txt

# 處理緩慢 排在後面 
journalctl -b | grep -iE "suspend|resume|sleep|PM: " > $OUT_DIR/suspend.txt


# 摘要處理
python3 doze_summary.py $OUT_DIR/full.txt \
  --checkin $OUT_DIR/checkin.txt \
  --pkg ch.deletescape.lawnchair.plah,com.sec.android.app.launcher \
  --suspend $OUT_DIR/suspend.txt --deviceidle $OUT_DIR/deviceidle.txt \
  --mem $OUT_DIR/mem_start.txt $OUT_DIR/mem_end.txt --battery $OUT_DIR/battery_start.txt $OUT_DIR/battery_end.txt | tee $OUT_DIR/summary-$TIMESTAMP.txt > /dev/null

```
---

`doze-test.sh` 的記憶體指令確實有一處寫錯,另外還有幾個會讓資料缺失或失真的地方。我已改成 v2,並一併更新摘要腳本與指南。

## 指令格式的檢查結果

| 項目 | 結果 |
|---|---|
| `adb shell dumpsys meminfo com.sec.android.app.launcher > mem_start.txt` | ✓ 格式對 |
| `adb shell dumpsys meminfo ch.deletescape.lawnchair.plah >> mem_start.txt` | ✓ 指令對,但檔案裡有兩個進程,而摘要腳本 v2 初版**只解析第一個**,所以 Lawnchair 被漏掉 |
| `adb shell dumpsys ch.deletescape.lawnchair.plah >> mem_end.txt` | ✗ **漏了 `meminfo`**。輸出只會是 `Can't find service`,沒有記憶體資料 |
| `battery_start.txt` / `battery_end.txt` 沒有時間資訊 | ✗ 摘要算不出「區間放電」(你的 `summary.txt` 確實沒有那一行) |
| `adb devices` 失敗後繼續執行 | ✗ 後面全部抓到空檔 |
| `batterystats` 的 `full` / `checkin` / `history` / `deviceidle` | ✓ 格式對 |
| `netstats`、`journalctl ... \| grep` | ✓ 對 |
| `python3 doze_summary.py ...` 的參數 | ✓ 對(你這次有帶 `--checkin`,所以 UID 名稱正常) |

你的 `summary.txt` 也印證了第一點:`mem_start` 與 `mem_end` 都只有 One UI Home,沒有 Lawnchair。

## v2 做了什麼

1. 修正 `meminfo`,兩個 launcher 改用迴圈處理,不會漏。
2. 檔案開頭寫入 `# captured: 時間`,摘要才算得出區間放電;摘要腳本也改成能解析一個檔案裡的多個進程,遇到 `Can't find service` 會標 ⚠。
3. **adb 重連改成重試迴圈**(每 5 秒、共約 2 分鐘);仍連不上就提示你亮屏手機後按 Enter 重試。每個擷取檔都檢查是否為空。
4. 擷取順序改成時間敏感的先抓(`deviceidle`、電池、鬧鐘),體積大的 `batterystats` 後抓。
5. **事前檢查下一個會喚醒手機的鬧鐘**(FMM),不到 125 分鐘會提醒你。我用你貼的 `dumpsys alarm` 輸出實際測過這段解析,抓得到 `2026-11-16 08:04:40`。
6. 先拍快照、最後才 `reset`;並可用 `KEYCODE_SLEEP` 讓螢幕立刻關閉(`SLEEP_SCREEN=1`,我沒辦法在你的手機上驗證,可以改成 0)。
7. 其他:路徑用腳本所在資料夾、指令用 `-s` 指定裝置、變數加引號。

用之前要改的只有 `ADB_ADDR`(IP:埠號)與 `PKGS`。
---
```js
#!/bin/bash
# doze-test.sh v2 — 一鍵待機測試:重置統計 → 電腦睡眠 → 醒來後自動重連 adb 並紀錄 → 產生摘要
#
# 用法:   ./doze-test.sh            (在 doze_summary.py 所在的資料夾,或與它放在同一個資料夾)
# 需要:   手機已開啟無線偵錯並與電腦配對過;電腦可用 `systemctl suspend`
# 注意:   測試開始前請確認 FMM(尋找我的手機)狀態、手機未充電、預設桌面是你要測的那個。
#
# v2 改動(相對於 v1):
#   1. 修正:mem_end 的 Lawnchair 指令缺了 `meminfo`(v1 寫成 `dumpsys ch.deletescape.lawnchair.plah`,抓不到資料)
#   2. 兩個 launcher 的 meminfo 現在由迴圈處理,不會漏;摘要腳本也能在同一個檔案裡解析多個進程
#   3. battery / meminfo 檔案開頭寫入 `# captured:` 時間,摘要才算得出「區間放電」
#   4. adb 重連改成重試迴圈;失敗時不會繼續寫出一堆空檔案,而是提示你亮屏手機後再試
#   5. 資料擷取順序改為「時間敏感的先抓」(deviceidle、電池、鬧鐘),體積大的 batterystats 後抓
#   6. 事前檢查下一個「會喚醒手機的鬧鐘」(FMM)距離現在多久,太近會提醒
#   7. 每個擷取檔都檢查是否為空;指令改用 -s 指定裝置;變數加引號

set -u

# ===================== 設定 =====================
ADB_ADDR="192.168.1.142:44055"   # 無線偵錯的 IP:埠號(重開無線偵錯後埠號會變,要修正)
PKGS=("com.sec.android.app.launcher" "ch.deletescape.lawnchair.plah")   # 要量記憶體的 launcher 套件
RECONNECT_TRIES=24               # 每次間隔 5 秒,共約 2 分鐘
MIN_ALARM_MIN=125                # 下一個 wake-from-idle 鬧鐘至少要在幾分鐘之後
WANT_NETSTATS=0                  # 1 = 一併匯出 netstats(很大,通常不需要)
SLEEP_SCREEN=1                   # 1 = 重置後先用 KEYCODE_SLEEP 讓螢幕立刻關閉(未在所有機型驗證)
# =================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TIMESTAMP="$(date +"%Y%m%d_%H%M")"
OUT_DIR="$SCRIPT_DIR/$TIMESTAMP"
mkdir -p "$OUT_DIR"
A=(adb -s "$ADB_ADDR")

stamp() { date +"# captured: %Y-%m-%d %H:%M:%S"; }
log()   { echo "$(date +"%H:%M:%S") $*" | tee -a "$OUT_DIR/timeline.txt"; }

# capture <檔名> <指令...>:把指令輸出存檔,並檢查不是空的
capture() {
  local f="$1"; shift
  "$@" > "$OUT_DIR/$f" 2>&1
  if [ ! -s "$OUT_DIR/$f" ]; then
    log "⚠ $f 是空的(adb 連線可能中斷)"
  fi
}

snapshot_battery() { { stamp; "${A[@]}" shell dumpsys battery; } > "$OUT_DIR/$1"; }

snapshot_mem() {
  { stamp; } > "$OUT_DIR/$1"
  for p in "${PKGS[@]}"; do
    "${A[@]}" shell dumpsys meminfo "$p" >> "$OUT_DIR/$1"
  done
}

connect_adb() {
  local i
  for i in $(seq 1 "$RECONNECT_TRIES"); do
    adb connect "$ADB_ADDR" >/dev/null 2>&1
    if [ "$(adb -s "$ADB_ADDR" get-state 2>/dev/null)" = "device" ] && "${A[@]}" shell true >/dev/null 2>&1; then
      log "adb 已連線(第 $i 次嘗試)"
      return 0
    fi
    adb disconnect "$ADB_ADDR" >/dev/null 2>&1   # 清掉 offline 狀態再重試
    sleep 5
  done
  return 1
}

# ---------------------------------------------------------------- 開始前
log "開始前:連線 adb"
connect_adb || { echo "無法連線 $ADB_ADDR,請確認 IP:埠號(無線偵錯畫面上顯示的)"; exit 1; }

# 預設桌面與電量
"${A[@]}" shell cmd role get-role-holders android.app.role.HOME | tee "$OUT_DIR/home_start.txt"
"${A[@]}" shell dumpsys battery | grep -E "^  (AC|USB|Wireless) powered|^  level"

# 下一個「會喚醒手機」的鬧鐘(FMM 的 defaultScanStartTimer 之類),Samsung 的 min_time_to_alarm=1h
{ stamp; "${A[@]}" shell dumpsys alarm; } > "$OUT_DIR/alarm_start_full.txt"
{ stamp; grep -B2 -A8 "defaultScanStartTimer" "$OUT_DIR/alarm_start_full.txt"; } > "$OUT_DIR/alarm_start.txt"
NEXT="$(grep -A8 "Next wake from idle" "$OUT_DIR/alarm_start_full.txt" | grep -m1 -oE "triggerTime=[0-9-]+ [0-9:]+" | cut -d= -f2)"
if [ -n "$NEXT" ]; then
  PHONE_NOW="$("${A[@]}" shell date +"%Y-%m-%d %H:%M:%S" | tr -d '\r')"   # 用手機的「現在」,避免電腦與手機時鐘差
  NEXT_MIN=$(( ( $(date -d "$NEXT" +%s) - $(date -d "$PHONE_NOW" +%s) ) / 60 ))
  log "下一個會喚醒手機的鬧鐘:$NEXT(約 ${NEXT_MIN} 分鐘後)"
  if [ "$NEXT_MIN" -lt "$MIN_ALARM_MIN" ]; then
    echo "⚠ 這個鬧鐘距離現在不到 ${MIN_ALARM_MIN} 分鐘;Doze 很可能放棄進入 deep idle(min_time_to_alarm=1h)。"
    read -r -p "仍要開始測試嗎?[y/N] " ans
    [ "$ans" = "y" ] || [ "$ans" = "Y" ] || exit 0
  fi
else
  log "目前沒有排定的 wake-from-idle 鬧鐘"
fi

# 事前快照(先拍快照,最後才 reset,這樣統計起點就是電腦睡眠前的那一刻)
snapshot_mem mem_start.txt
snapshot_battery battery_start.txt
"${A[@]}" shell dumpsys deviceidle unforce
"${A[@]}" shell dumpsys batterystats --enable full-wake-history
"${A[@]}" shell dumpsys batterystats --reset
log "batterystats 已重置"

if [ "$SLEEP_SCREEN" = "1" ]; then
  "${A[@]}" shell input keyevent KEYCODE_SLEEP    # 讓螢幕立刻關閉;Doze 計時從這裡開始
fi

# ---------------------------------------------------------------- 電腦睡眠
log "電腦即將睡眠(醒來後會自動繼續)"
sleep 2
systemctl suspend
log "電腦已醒來"

# ---------------------------------------------------------------- 醒來後
if ! connect_adb; then
  echo
  echo "adb 連不上(常見是 No route to host)。請亮屏手機約 5 秒讓 adb 連線,然後按 Enter 重試。"
  echo "這幾秒的亮屏會被記進統計;摘要會標出「測試期間有亮屏」,請把有效待機區間算到那裡為止。"
  read -r -p "已亮屏?按 Enter 重試:" _
  log "使用者亮屏手機後重試"
  connect_adb || { echo "仍然連不上,結束。請手動執行 doze-test.sh 中「醒來後」的部分。"; exit 1; }
fi

# 時間敏感的先抓
capture deviceidle.txt "${A[@]}" shell dumpsys deviceidle
snapshot_battery battery_end.txt
{ stamp; "${A[@]}" shell dumpsys alarm | grep -B2 -A8 "defaultScanStartTimer"; } > "$OUT_DIR/alarm_end.txt"
snapshot_mem mem_end.txt
"${A[@]}" shell cmd role get-role-holders android.app.role.HOME | tee "$OUT_DIR/home_end.txt"

# 體積大的後抓
capture full.txt    "${A[@]}" shell dumpsys batterystats
capture checkin.txt "${A[@]}" shell dumpsys batterystats --checkin
capture history.txt "${A[@]}" shell dumpsys batterystats --history
if [ "$WANT_NETSTATS" = "1" ]; then
  capture netstats.txt "${A[@]}" shell dumpsys netstats detail
fi

# 電腦端的睡眠 / 喚醒紀錄(處理慢,放最後)
journalctl -b | grep -iE "suspend|resume|sleep|PM: " > "$OUT_DIR/suspend.txt"

# ---------------------------------------------------------------- 摘要
python3 "$SCRIPT_DIR/doze_summary.py" "$OUT_DIR/full.txt" \
  --checkin "$OUT_DIR/checkin.txt" \
  --pkg "$(IFS=,; echo "${PKGS[*]}")" \
  --suspend "$OUT_DIR/suspend.txt" --deviceidle "$OUT_DIR/deviceidle.txt" \
  --mem "$OUT_DIR/mem_start.txt" "$OUT_DIR/mem_end.txt" \
  --battery "$OUT_DIR/battery_start.txt" "$OUT_DIR/battery_end.txt" \
  | tee "$OUT_DIR/summary-$TIMESTAMP.txt"

log "完成:$OUT_DIR"
```
---
## 補充


**唯一的影響是您無法在 Island 空間內使用 Google 語音輸入或直接開啟工作版的 Google 搜尋，但這在隔離空間中通常完全用不到。**
```js
adb shell dumpsys meminfo | head -n 15
adb shell pm disable-user --user 10 com.google.android.googlequicksearchbox
adb shell pm enable --user 10 com.google.android.googlequicksearchbox
```

**查詢特定 Linux UID（使用者識別碼） 所對應的 Android 應用程式套件名稱（Package Name）。**
```js
adb shell pm list packages --uid 10203
```
