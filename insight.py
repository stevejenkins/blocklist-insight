#!/usr/bin/env python3
import csv
import hashlib
import os
import pickle
import random
import re
import sys
import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
import urllib.error
import urllib.request

ADLIST_FILE = "adlists.txt"
CACHE_DIR = Path(".cache_lists")
PARSED_CACHE_DIR = Path(".cache_parsed")
CACHE_EXPIRY_HOURS = 24
RESULTS_MD = Path("results.md")
RESULTS_TXT = Path("results.txt")
MATRIX_CSV = Path("matrix.csv")
OPTIMAL_LISTS_MD = Path("optimal_lists.md")
ERRORS_TXT = Path("errors.txt")
USER_AGENTS_URL = "https://assets.staticnetcontent.com/extension/useragents.txt"

TARGET_COVERAGE_PERCENT = 99.5  # Stop when >= 99.5% of total universe is covered

# All regular expressions defined as raw string literals to eliminate Python 3.12+ SyntaxWarnings
RE_SPACES = re.compile(r"\s+")
RE_COMMENTS = re.compile(r"(^|\s)[#!].*")
RE_PREFIX_HOST = re.compile(r"^((host|domain)(-suffix)?),|,reject$", re.IGNORECASE)
RE_ADDRESS_PREFIX = re.compile(r"^(address|server)=/|/0\.0\.0\.0$", re.IGNORECASE)
RE_IP_PREFIX = re.compile(r"^(((0|127)\.(\d{1,3}\.){2}\d{1,3})|::|0)\s+")
RE_MODIFIERS_1 = re.compile(
    r"[\^$,](important|empty|first-party|1p|3p|popup|popunder|third-party|script)",
    re.IGNORECASE,
)
RE_MODIFIERS_2 = re.compile(
    r"[\^$,](~third-party|image|media|subdocument|document|doc|object|~object-subrequest|frame|all|domain=in-addr\.arpa)",
    re.IGNORECASE,
)
RE_RULE_PREFIX = re.compile(r"^(\|\|?|\*\.|\.|=|-d\s)?")
RE_TRAILING_CHARS = re.compile(r"[\*^\/\?\|]+$")
RE_ALLOWED_CHARS = re.compile(r"^[a-z0-9._-]+$")

DOMAIN_PATTERN = re.compile(
    r"\b((?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63})\b"
)

# Process pool global references
_WORKER_LISTS: Dict[str, Set[str]] = {}
_WORKER_ACTIVE_URLS: List[str] = []


def print_progress(
    current: int,
    total: int,
    start_time: float,
    prefix: str = "",
    bar_length: int = 25,
):
    if total == 0:
        return

    elapsed = time.time() - start_time
    fraction = min(max(current / total, 0.0), 1.0)
    filled = int(bar_length * fraction)
    bar = "█" * filled + "░" * (bar_length - filled)
    percent = fraction * 100

    if current > 0 and fraction < 1.0:
        rate = current / elapsed
        remaining_seconds = (total - current) / rate
        mins_rem, secs_rem = divmod(int(remaining_seconds), 60)
        eta_str = f"{mins_rem:02d}:{secs_rem:02d}"
    elif fraction >= 1.0:
        eta_str = "00:00"
    else:
        eta_str = "--:--"

    mins_elap, secs_elap = divmod(int(elapsed), 60)
    elapsed_str = f"{mins_elap:02d}:{secs_elap:02d}"

    sys.stdout.write(
        f"\r{prefix:<16} [{bar}] {current:>3}/{total:<3} "
        f"({percent:>5.1f}%) | {elapsed_str}<{eta_str}"
    )
    sys.stdout.flush()

    if current >= total:
        sys.stdout.write("\n")


def fetch_random_user_agent() -> str:
    fallback_ua = "Mozilla/5.0 (compatible; BlocklistChecker/1.0)"
    try:
        req = urllib.request.Request(
            USER_AGENTS_URL, headers={"User-Agent": fallback_ua}
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            lines = [
                line.decode("utf-8", errors="ignore").strip()
                for line in response.readlines()
            ]
            lines = [l for l in lines if l]
            return random.choice(lines) if lines else fallback_ua
    except Exception:
        return fallback_ua


def get_cache_path(url: str, base_dir: Path, ext: str = ".txt") -> Path:
    url_hash = hashlib.md5(url.encode("utf-8")).hexdigest()
    return base_dir / f"{url_hash}{ext}"


def read_cached_content(url: str, max_age_seconds: float) -> Optional[str]:
    cache_file = get_cache_path(url, CACHE_DIR, ".txt")
    if not cache_file.is_file():
        return None

    file_age = time.time() - cache_file.stat().st_mtime
    if file_age <= max_age_seconds:
        try:
            return cache_file.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return None
    return None


def fetch_and_cache_url(url: str, user_agent: str) -> Tuple[str, Optional[str]]:
    req = urllib.request.Request(url, headers={"User-Agent": user_agent})
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            content = response.read().decode("utf-8", errors="ignore")
            cache_file = get_cache_path(url, CACHE_DIR, ".txt")
            try:
                cache_file.write_text(content, encoding="utf-8")
            except Exception:
                pass
            return url, content
    except Exception:
        return url, None


def parse_list_content(url: str, content: str) -> Tuple[str, Set[str]]:
    parsed_cache_file = get_cache_path(url, PARSED_CACHE_DIR, ".bin")
    if parsed_cache_file.is_file():
        try:
            with open(parsed_cache_file, "rb") as f:
                return url, pickle.load(f)
        except Exception:
            pass

    valid_domains: Set[str] = set()
    content_lower = content.lower()
    for match in DOMAIN_PATTERN.finditer(content_lower):
        domain = match.group(1)
        if not domain.endswith(".localdomain") and "." in domain:
            valid_domains.add(domain)

    try:
        with open(parsed_cache_file, "wb") as f:
            pickle.dump(valid_domains, f, protocol=pickle.HIGHEST_PROTOCOL)
    except Exception:
        pass

    return url, valid_domains


def init_worker(cleaned: Dict[str, Set[str]], urls: List[str]):
    global _WORKER_LISTS, _WORKER_ACTIVE_URLS
    _WORKER_LISTS = cleaned
    _WORKER_ACTIVE_URLS = urls


def compare_target_list(target_url: str) -> Tuple[str, Dict[str, int]]:
    target_set = _WORKER_LISTS[target_url]
    results: Dict[str, int] = {}

    for match_url in _WORKER_ACTIVE_URLS:
        if match_url == target_url:
            results[match_url] = 100
            continue

        match_set = _WORKER_LISTS[match_url]
        total_entries = len(match_set)

        if total_entries == 0:
            percent = 0
        else:
            intersection_count = len(target_set.intersection(match_set))
            percent = round((intersection_count * 100) / total_entries)

        results[match_url] = percent

    return target_url, results


def solve_set_cover(
    cleaned_lists: Dict[str, Set[str]],
    target_coverage_pct: float = 99.5
) -> List[Dict[str, object]]:
    universe: Set[str] = set()
    for domain_set in cleaned_lists.values():
        universe.update(domain_set)

    total_universe_size = len(universe)
    if total_universe_size == 0:
        return []

    target_count = int(total_universe_size * (target_coverage_pct / 100.0))
    covered_domains: Set[str] = set()
    available_lists = {url: set(domains) for url, domains in cleaned_lists.items()}
    selected_steps: List[Dict[str, object]] = []

    while covered_domains != universe and len(covered_domains) < target_count:
        best_url: Optional[str] = None
        best_gain: int = 0
        best_new_domains: Set[str] = set()

        for url, domains in available_lists.items():
            new_domains = domains - covered_domains
            gain = len(new_domains)
            if gain > best_gain:
                best_gain = gain
                best_url = url
                best_new_domains = new_domains

        if not best_url or best_gain == 0:
            break

        total_list_size = len(cleaned_lists[best_url])
        redundant_count = total_list_size - best_gain
        redundancy_rate = (redundant_count / total_list_size * 100.0) if total_list_size else 0.0

        covered_domains.update(best_new_domains)
        cumulative_pct = (len(covered_domains) / total_universe_size) * 100.0

        selected_steps.append({
            "url": best_url,
            "total_domains": total_list_size,
            "unique_contribution": best_gain,
            "redundant_domains": redundant_count,
            "redundancy_pct": redundancy_rate,
            "cumulative_covered": len(covered_domains),
            "cumulative_pct": cumulative_pct
        })

        del available_lists[best_url]

    return selected_steps


def main():
    adlist_path = Path(ADLIST_FILE)
    if not adlist_path.is_file():
        print(f"Error: {ADLIST_FILE} not found!")
        return

    with open(adlist_path, "r", encoding="utf-8") as f:
        sources = [line.strip() for line in f if line.strip()]

    total_sources = len(sources)
    if total_sources == 0:
        print("No URLs found in adlists.txt")
        return

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    PARSED_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_ttl_sec = CACHE_EXPIRY_HOURS * 3600

    cpu_cores = os.cpu_count() or 4
    print(f"Loaded {total_sources} list URLs. Parallelizing across {cpu_cores} CPU cores.")

    # Stage 1: Download & Cache
    print("\n[1/4] Resolving raw blocklist files...")
    raw_data: Dict[str, Optional[str]] = {}
    urls_to_download: List[str] = []

    for url in sources:
        cached = read_cached_content(url, cache_ttl_sec)
        if cached is not None:
            raw_data[url] = cached
        else:
            urls_to_download.append(url)

    cached_count = len(sources) - len(urls_to_download)
    print(f"  -> Cache hits: {cached_count} list(s).")

    if urls_to_download:
        print(f"  -> Downloading {len(urls_to_download)} list(s)...")
        ua = fetch_random_user_agent()
        completed_downloads = 0
        t_stage1 = time.time()
        print_progress(0, len(urls_to_download), t_stage1, prefix="Downloading")

        with ThreadPoolExecutor(max_workers=min(16, len(urls_to_download))) as executor:
            futures = {
                executor.submit(fetch_and_cache_url, url, ua): url
                for url in urls_to_download
            }
            for future in as_completed(futures):
                url, content = future.result()
                raw_data[url] = content
                completed_downloads += 1
                print_progress(
                    completed_downloads,
                    len(urls_to_download),
                    t_stage1,
                    prefix="Downloading",
                )
    else:
        print("  -> Raw lists up to date in cache.")

    # Stage 2: Parallel Parsing & Deduplication
    print(f"\n[2/4] Parallel parsing and deduplicating ({cpu_cores} CPU cores)...")
    cleaned_lists: Dict[str, Set[str]] = {}
    valid_raw_sources = [(url, raw_data[url]) for url in sources if raw_data.get(url) is not None]
    offline_urls = [url for url in sources if raw_data.get(url) is None]

    t_stage2 = time.time()
    completed_parsed = 0
    print_progress(0, len(sources), t_stage2, prefix="Parsing")

    with ProcessPoolExecutor(max_workers=cpu_cores) as pool:
        futures = {
            pool.submit(parse_list_content, url, content): url
            for url, content in valid_raw_sources
        }
        for future in as_completed(futures):
            url, domain_set = future.result()
            cleaned_lists[url] = domain_set
            completed_parsed += 1
            print_progress(completed_parsed, len(sources), t_stage2, prefix="Parsing")

    if offline_urls:
        print_progress(len(sources), len(sources), t_stage2, prefix="Parsing")
        with open(ERRORS_TXT, "w", encoding="utf-8") as f_err:
            for bad_url in offline_urls:
                f_err.write(f"{bad_url} is offline.\n\n")
        print(f"  Note: {len(offline_urls)} lists offline (logged to {ERRORS_TXT.name}).")

    active_urls = [u for u in sources if u in cleaned_lists]
    total_active = len(active_urls)

    # Stage 3: Greedy Set-Cover Optimization
    print(f"\n[3/4] Running Greedy Set-Cover Solver (Target: {TARGET_COVERAGE_PERCENT}%)...")
    optimal_selection = solve_set_cover(cleaned_lists, TARGET_COVERAGE_PERCENT)
    total_global_domains = len(set().union(*cleaned_lists.values())) if cleaned_lists else 0

    print(f"  -> Total distinct domains across all lists: {total_global_domains:,}")
    print(f"  -> Selected {len(optimal_selection)} / {total_active} lists to achieve maximum coverage.\n")

    optimal_md: List[str] = [
        "# Optimal Blocklist Minimal Set-Cover",
        f"\n- **Total Global Universe:** {total_global_domains:,} unique domains across {total_active} blocklists",
        f"- **Optimal Subset Size:** {len(optimal_selection)} lists required",
        f"- **Target Threshold:** {TARGET_COVERAGE_PERCENT}%\n",
        "| Step | Selected Blocklist | Total Domains | New Unique Added | Redundant / Overlap | Redundancy % | Cumulative Coverage |",
        "|:---:|:---|:---:|:---:|:---:|:---:|:---:|"
    ]

    for idx, item in enumerate(optimal_selection, start=1):
        optimal_md.append(
            f"| {idx} | `{item['url']}` | {item['total_domains']:,} | +{item['unique_contribution']:,} | "
            f"{item['redundant_domains']:,} | {item['redundancy_pct']:.1f}% | **{item['cumulative_pct']:.2f}%** |"
        )

    with open(OPTIMAL_LISTS_MD, "w", encoding="utf-8") as f_opt:
        f_opt.write("\n".join(optimal_md) + "\n")

    # Stage 4: Complete NxN Crosscheck Matrix
    print(f"[4/4] Cross-comparing {total_active} lists across all pairs ({cpu_cores} workers)...")
    t_stage4 = time.time()
    completed_comparisons = 0
    matrix: Dict[str, Dict[str, int]] = {}

    print_progress(0, total_active, t_stage4, prefix="Comparing")
    with ProcessPoolExecutor(
        max_workers=cpu_cores,
        initializer=init_worker,
        initargs=(cleaned_lists, active_urls),
    ) as pool:
        futures = {pool.submit(compare_target_list, url): url for url in active_urls}
        for future in as_completed(futures):
            target_url, row_results = future.result()
            matrix[target_url] = row_results
            completed_comparisons += 1
            print_progress(completed_comparisons, total_active, t_stage4, prefix="Comparing")

    # Export Matrix CSV (Using forward slash to prevent invalid escape sequence warnings)
    with open(MATRIX_CSV, "w", newline="", encoding="utf-8") as f_csv:
        writer = csv.writer(f_csv)
        header = ["Target List (Row) / Coverage Over Col %"] + active_urls
        writer.writerow(header)
        for target_url in active_urls:
            row = [target_url] + [f"{matrix[target_url].get(m_url, 0)}%" for m_url in active_urls]
            writer.writerow(row)

    # Export Results MD & TXT
    results_md_lines: List[str] = []
    results_txt_lines: List[str] = []

    results_md_lines.append("# Overall Cross-Comparison Matrix\n")
    results_md_lines.append("> Cell `[Row][Col]` indicates what % of domains in **Col** are already covered by **Row**.\n")

    short_labels = {url: f"L{i+1}" for i, url in enumerate(active_urls)}
    md_header = "| Index | List URL | " + " | ".join([short_labels[u] for u in active_urls]) + " |"
    md_divider = "|:---:|:---| " + " | ".join([":---:" for _ in active_urls]) + " |"
    results_md_lines.append(md_header)
    results_md_lines.append(md_divider)

    for target_url in active_urls:
        row_vals = [f"{matrix[target_url].get(m_url, 0)}%" for m_url in active_urls]
        results_md_lines.append(f"| {short_labels[target_url]} | `{target_url}` | " + " | ".join(row_vals) + " |")

    results_md_lines.append("\n\n# Detailed Breakdown per List\n")
    for target_url in active_urls:
        results_md_lines.append(f"\n### {target_url}\n| % Coverage of Target | Compared Blocklist |\n|---|---|")
        results_txt_lines.append(f"\n\n# {target_url}\n-------------------------------------------------")

        comparisons = [
            (pct, m_url) for m_url, pct in matrix[target_url].items() if m_url != target_url
        ]
        comparisons.sort(key=lambda x: (-x[0], x[1]))

        for percent, match_url in comparisons:
            results_md_lines.append(f"| {percent}% | {match_url} |")
            results_txt_lines.append(f"{percent}%\t{match_url}")

    with open(RESULTS_MD, "w", encoding="utf-8") as f_md:
        f_md.write("\n".join(results_md_lines).strip() + "\n")

    with open(RESULTS_TXT, "w", encoding="utf-8") as f_txt:
        f_txt.write("\n".join(results_txt_lines).strip() + "\n")

    print(f"\nDone! Deliverables generated:")
    print(f" - {OPTIMAL_LISTS_MD.name}  <-- Minimal blocklist combination table")
    print(f" - {MATRIX_CSV.name}        <-- Full NxN cross-comparison spreadsheet")
    print(f" - {RESULTS_MD.name}        <-- Detailed per-list overlap breakdown")
    print(f" - {RESULTS_TXT.name}       <-- Plaintext crosscheck summary")


if __name__ == "__main__":
    main()
