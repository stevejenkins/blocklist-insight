# blocklist-compare
Compares a list of DNS blocklists, calculates overlap, and recommends the smallest number of lists for the maximum coverage

# Optimal Blocklist Minimal Set-Cover

- **Total Global Universe:** 3,332,279 unique domains across 20 blocklists
- **Optimal Subset Size:** 9 lists required
- **Target Threshold:** 99.5%

| Step | Selected Blocklist | Total Domains | New Unique Added | Redundant / Overlap | Redundancy % | Cumulative Coverage |
|:---:|:---|:---:|:---:|:---:|:---:|:---:|
| 1 | `https://cdn.jsdelivr.net/gh/hagezi/dns-blocklists@latest/adblock/tif.txt` | 1,851,039 | +1,851,039 | 0 | 0.0% | **55.55%** |
| 2 | `https://raw.githubusercontent.com/RPiList/specials/master/Blocklisten/malware` | 667,695 | +568,335 | 99,360 | 14.9% | **72.60%** |
| 3 | `https://cdn.jsdelivr.net/gh/hagezi/dns-blocklists@latest/adblock/gambling.txt` | 627,355 | +511,562 | 115,793 | 18.5% | **87.96%** |
| 4 | `https://raw.githubusercontent.com/RPiList/specials/master/Blocklisten/easylist` | 183,656 | +160,169 | 23,487 | 12.8% | **92.76%** |
| 5 | `https://cdn.jsdelivr.net/gh/hagezi/dns-blocklists@latest/adblock/pro.plus.txt` | 225,090 | +112,416 | 112,674 | 50.1% | **96.14%** |
| 6 | `https://raw.githubusercontent.com/StevenBlack/hosts/master/hosts` | 79,238 | +49,503 | 29,735 | 37.5% | **97.62%** |
| 7 | `https://big.oisd.nl` | 231,712 | +33,152 | 198,560 | 85.7% | **98.62%** |
| 8 | `https://threatfox-api.abuse.ch/v2/files/exports/AUTHKEY/hostfile.txt` | 33,103 | +21,140 | 11,963 | 36.1% | **99.25%** |
| 9 | `https://hostfiles.frogeye.fr/firstparty-trackers-hosts.txt` | 14,800 | +12,666 | 2,134 | 14.4% | **99.63%** |
