可以。你現在的目標就是確認：

> 為什麼 NextDNS 會反覆出現「私人 DNS 無法存取」，但換成 AdGuard DNS 就正常。



目前最重要的證據是：NextDNS 曾反覆出現 PrivateDnsConfig{true:.../[]}，而切換 AdGuard 後能正常取得 IP 並持續運作。

測試方法

① 測試前

先用：

中華 4G + 原本 VPN 設定 + NextDNS

不要先改其他東西。

② 一出現「私人 DNS 無法存取」

立刻在 aShell 執行：

echo "===== PRIVATE DNS ====="
settings get global private_dns_mode
settings get global private_dns_specifier

echo "===== DNS MANAGER / VALIDATION ====="
logcat -d -t 20000 | grep -i -E "DnsManager|PrivateDns|DnsResolver|PrivateDnsValidation|validation|nextdns|853|TLS|connect"

③ 再抓 Connectivity

echo "===== CONNECTIVITY ====="
dumpsys connectivity | grep -i -E "dns|vpn|validated|network"

④ 抓當下 BatteryStats

echo "===== BATTERY ====="
dumpsys batterystats | sed -n '/Statistics since last charge:/,/CONNECTIVITY POWER SUMMARY END/p'


---

然後做 A/B 測試

A：NextDNS

中華 4G
+
同一個 VPN
+
NextDNS

記錄：

是否出現「私人 DNS 無法存取」

並抓上面 4 組資料。

B：AdGuard

其他條件完全不變，只把 Private DNS 改成：

dns.adguard-dns.com

觀察至少 30～60 分鐘。

如果：

NextDNS     → ❌ 反覆 Private DNS error
AdGuard     → ✅ 持續正常

這就是非常有價值的 A/B 證據。


---

我們主要看這幾種結果

NextDNS → hostname 有 IP → 但 validation fail

→ 懷疑 DoT / TCP 853 / VPN / endpoint

NextDNS → hostname 變成 []

→ 懷疑 DNS resolution / endpoint / routing

NextDNS + VPN OFF → 正常
NextDNS + VPN ON  → FAIL

→ 強烈懷疑 VPN routing / DNS interception

NextDNS + 4G → FAIL
NextDNS + Wi-Fi → OK

→ 強烈懷疑 4G / ISP / IPv4/IPv6 path

NextDNS → FAIL
AdGuard → OK

→ 問題高度集中在 NextDNS endpoint / path / Private DNS validation

但還不能直接證明「中華電信封鎖 853」。


---

最重要的一點

現在先不要再用 dumpsys netd 或 dumpsys dnsresolver。

你的 aShell 權限已經證明：

Can't find service: netd
Can't find service: dnsresolver

這些在你的手機上沒有分析價值。

下次故障時，只要把上面 4 組輸出完整貼給我，我就可以直接跟你之前的 log 對照，判斷問題是在：

DNS → Private DNS validation → VPN → 4G/ISP → NextDNS endpoint

哪一層。
