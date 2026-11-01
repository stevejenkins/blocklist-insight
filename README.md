# Blocklist Insight
Compares a list of DNS blocklists, calculates overlap, then uses the Greedy Set-Cover Solver to recommend the smallest number of lists you can use to achieve the maximum coverage of blocked hosts.

This Python script is loosely based on the [badmojr/crosscheck](https://github.com/badmojr/crosscheck) Bash script.

I created this script to help maintain my own list of recommended Pi-hole "List of Lists" [here](https://github.com/stevejenkins/pi-hole-lists). The examples in this repository are not necessarily up to date with my recommended "List of Lists." [This link](https://github.com/stevejenkins/pi-hole-lists) will always contain my current blocklist recommendations.

## What `insight.py` it Looks Like
When you run `insight.py` it will generate a report that looks like this:

- **Total Lists Analyzed:** 20
- **Total Global Universe:** 3,332,279 unique domains across all reachable lists
- **Optimal Subset Size:** 9 lists required
- **Target Threshold:** 99.5%

## Selected Lists
| Step | Selected Blocklist | Total Domains | New Unique Added | Redundant / Overlap | Redundancy % | Cumulative Coverage |
|:---:|:---|:---:|:---:|:---:|:---:|:---:|
| 1 | `https://cdn.jsdelivr.net/gh/hagezi/dns-blocklists@latest/adblock/tif.txt` | 1,851,039 | +1,851,039 | 0 | 0.0% | **55.55%** |
| 2 | `https://raw.githubusercontent.com/RPiList/specials/master/Blocklisten/malware` | 667,695 | +568,335 | 99,360 | 14.9% | **72.60%** |
| 3 | `https://cdn.jsdelivr.net/gh/hagezi/dns-blocklists@latest/adblock/gambling.txt` | 627,355 | +511,562 | 115,793 | 18.5% | **87.96%** |
| 4 | `https://raw.githubusercontent.com/RPiList/specials/master/Blocklisten/easylist` | 183,656 | +160,169 | 23,487 | 12.8% | **92.76%** |
| 5 | `https://cdn.jsdelivr.net/gh/hagezi/dns-blocklists@latest/adblock/pro.plus.txt` | 225,090 | +112,416 | 112,674 | 50.1% | **96.14%** |
| 6 | `https://raw.githubusercontent.com/StevenBlack/hosts/master/hosts` | 79,238 | +49,503 | 29,735 | 37.5% | **97.62%** |
| 7 | `https://big.oisd.nl` | 231,712 | +33,152 | 198,560 | 85.7% | **98.62%** |
| 8 | `https://threatfox-api.abuse.ch/v2/files/exports/xxxxxxxx/hostfile.txt` | 33,103 | +21,140 | 11,963 | 36.1% | **99.25%** |
| 9 | `https://hostfiles.frogeye.fr/firstparty-trackers-hosts.txt` | 14,800 | +12,666 | 2,134 | 14.4% | **99.63%** |

## Redundant / Unselected Lists (Zero or Minimal Novel Contribution)
| Index | List URL | Total Domains | Redundancy Status |
|:---:|:---|:---:|:---|
| 1 | `https://raw.githubusercontent.com/StevenBlack/hosts/master/extensions/fakenews/hosts` | 2,193 | Covered by above selection |
| 2 | `https://cdn.jsdelivr.net/gh/hagezi/dns-blocklists@latest/adblock/spam-tlds-adblock.txt` | 15 | Covered by above selection |
| 3 | `https://gitlab.com/hagezi/mirror/-/raw/main/dns-blocklists/adblock/hoster.txt` | 1,076 | Covered by above selection |
| 4 | `https://urlhaus-api.abuse.ch/v2/files/exports/xxxxxxxx/hostfile.txt` | 462 | Covered by above selection |
| 5 | `https://adguardteam.github.io/HostlistsRegistry/assets/filter_50.txt` | 3,349 | Covered by above selection |
| 6 | `https://v.firebog.net/hosts/Prigent-Crypto.txt` | 11,493 | Covered by above selection |
| 7 | `https://s3.amazonaws.com/lists.disconnect.me/simple_ad.txt` | 2,701 | Covered by above selection |
| 8 | `https://raw.githubusercontent.com/blocklistproject/Lists/master/crypto.txt` | 1,274 | Covered by above selection |
| 9 | `https://adguardteam.github.io/HostlistsRegistry/assets/filter_7.txt` | 160 | Covered by above selection |
| 10 | `https://s3.amazonaws.com/lists.disconnect.me/simple_malvertising.txt` | 2,736 | Covered by above selection |
| 11 | `https://adaway.org/hosts.txt` | 7,914 | Covered by above selection |

## How To Run It
- Clone the repository
- Ensure the `insight.py` file is executable
- Include your blocklists in `adlists.txt`
- Run `insight.py`

## How to Use the Results
Use the results to help decide which blocklists are giving you the best coverage. Actual blocking success depends on which lists you use and what hosts your clients look up most. Pi-hole does a great job removing duplicates internally, but your `pihole -g` update process will run much faster if you're not feeding it multiple lists of duplicate hosts.
