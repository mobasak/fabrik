#!/usr/bin/env python3
"""
Scrape model throughput + TTFT from artificialanalysis.ai/leaderboards/models.

Mirrors the pattern in scrape_benchmarks.py:
- Cache raw HTML and parsed JSON under cache/
- Retry on network errors with exponential backoff
- Return canonical (provider, name, tps, ttft_ms) records

Match strategy:
- (canon_provider, canon_name) two-key lookup; multiple variants
  ("max", "high", "low") of the same base model collapse to median.
- canon_name strips "(...)" variants, drops noise suffixes
  (preview/experimental/exp/alpha/beta/rc/it), normalises to alphanum-hyphen.
- canon_provider routes AA's display name (e.g. "Alibaba", "Z AI") to the
  provider strings the agents table uses (qwen, z-ai).

Models without a match remain NULL in output_tokens_per_sec. The selector
treats NULL as "below floor" → excluded. Manual fixes go in
cache/speed_overrides.json keyed by agent id.

Usage:
    python scrape_artificial_analysis.py             # scrape and update DB
    python scrape_artificial_analysis.py --dry-run   # show match table only
"""

import argparse
import json
import re
import sqlite3
import sys
import time
from datetime import datetime
from functools import wraps
from pathlib import Path
from statistics import median

import requests
from bs4 import BeautifulSoup

SCRIPT_DIR = Path(__file__).parent
CACHE_DIR = SCRIPT_DIR / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = SCRIPT_DIR / "kilo_agents.db"

AA_URL = "https://artificialanalysis.ai/leaderboards/models"
RAW_HTML_PATH = CACHE_DIR / "aa_raw.html"
PARSED_JSON_PATH = CACHE_DIR / "aa_parsed.json"
OVERRIDES_PATH = CACHE_DIR / "speed_overrides.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}

# Map AA's "Creator" column to the provider string in agents.provider
PROVIDER_MAP = {
    "openai": "openai",
    "anthropic": "anthropic",
    "google": "google",
    "alibaba": "qwen",
    "qwen": "qwen",
    "kimi": "moonshotai",
    "moonshot": "moonshotai",
    "moonshotai": "moonshotai",
    "z ai": "z-ai",
    "z.ai": "z-ai",
    "zai": "z-ai",
    "minimax": "minimax",
    "deepseek": "deepseek",
    "xiaomi": "xiaomi",
    "meta": "meta",
    # Our DB stores llama-family provider as "meta-llama" (matches OR's
    # id prefix) but AA labels the creator as just "Meta". Same for
    # Mistral (mistralai/ in OR ids) and xAI (x-ai/ in OR ids). Without
    # these aliases, Llama and Mistral models had 0% Speed coverage
    # despite AA benchmarking all of them.
    "meta-llama": "meta",
    "mistralai": "mistral",
    "mistral": "mistral",
    "xai": "x-ai",
    "x ai": "x-ai",
    "meituan": "meituan",
    "perplexity": "perplexity",
    "mistral ai": "mistral",
    "mistral": "mistral",
    "amazon": "amazon",
    "nvidia": "nvidia",
    "cohere": "cohere",
    "stepfun": "stepfun",
    "microsoft": "microsoft",
    "baidu": "baidu",
    "inception": "inception",
}


def log(msg: str) -> None:
    print(f"[aa-scrape] {msg}")


def retry_on_network_error(max_attempts: int = 3, delay: int = 2, backoff: int = 2):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            attempt = 1
            current_delay = delay
            while attempt <= max_attempts:
                try:
                    return func(*args, **kwargs)
                except (requests.exceptions.RequestException, ConnectionError) as e:
                    if attempt == max_attempts:
                        log(f"  Error scraping {func.__name__}: {e}")
                        raise
                    log(
                        f"  Attempt {attempt}/{max_attempts} failed, retrying in {current_delay}s..."
                    )
                    time.sleep(current_delay)
                    current_delay *= backoff
                    attempt += 1
            return func(*args, **kwargs)

        return wrapper

    return decorator


@retry_on_network_error()
def fetch_html() -> str:
    log(f"GET {AA_URL}")
    resp = requests.get(AA_URL, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    RAW_HTML_PATH.write_text(resp.text)
    log(f"  cached → {RAW_HTML_PATH.name} ({len(resp.text)} bytes)")
    return resp.text


def parse_table(html: str) -> list[dict]:
    """Extract (name, creator, intelligence_index, tps, ttft_ms) per model
    from the AA leaderboard table.

    Column layout (verified 2026-06-28, 9 data cells per row):
      [0] Model name
      [1] Context Window
      [2] Creator
      [3] Artificial Analysis Intelligence Index   ← quality signal (NEW)
      [4] Blended USD/1M Tokens
      [5] Median Tokens/s                          ← throughput
      [6] Latency First Chunk (s)                  ← TTFT
      [7] Total Response (s)
      [8] Further Analysis

    A row may be missing ANY of intelligence_index, tps, or ttft_ms —
    don't drop the whole row if just one is missing. Intelligence
    coverage is roughly 80%+ of API-accessible models, much wider than
    the BENCHMARK_SOURCES.md WIRED set (Arena ~30%, TBench ~12%).
    """
    soup = BeautifulSoup(html, "html.parser")
    tables = soup.find_all("table")
    if not tables:
        raise RuntimeError("No table found in AA HTML — page structure changed?")

    rows = tables[0].find_all("tr")
    # Row 0: section header, Row 1: column labels, Row 2+: data
    out = []
    for row in rows[2:]:
        cells = row.find_all(["td", "th"])
        if len(cells) < 8:
            continue
        name = cells[0].get_text(strip=True)
        creator = cells[2].get_text(strip=True)
        intel_raw = cells[3].get_text(strip=True) if len(cells) > 3 else ""
        tps_raw = cells[5].get_text(strip=True)
        ttft_raw = cells[6].get_text(strip=True)

        try:
            intel = float(intel_raw)
        except ValueError:
            intel = None

        try:
            tps = float(tps_raw)
        except ValueError:
            tps = None

        try:
            ttft_ms = float(ttft_raw) * 1000.0
        except ValueError:
            ttft_ms = None

        # Keep the row if ANY signal is present.
        if tps is None and intel is None and ttft_ms is None:
            continue

        out.append(
            {
                "name": name,
                "creator": creator,
                "intelligence_index": intel,
                "tps": tps,
                "ttft_ms": ttft_ms,
            }
        )
    n_intel = sum(1 for r in out if r.get("intelligence_index") is not None)
    n_tps = sum(1 for r in out if r.get("tps") is not None)
    log(f"  parsed {len(out)} rows · intelligence={n_intel} · throughput={n_tps}")
    return out


def canon_provider(p: str) -> str:
    return PROVIDER_MAP.get(p.lower().strip(), p.lower().strip())


def canon_name(s: str) -> str:
    # Strip parenthetical suffix: "(max)", "(Non-reasoning, high)"
    s = re.sub(r"\s*\([^)]*\)\s*$", "", s).strip().lower()
    # Strip noise tokens that signal variant/state, not identity.
    # `instruct`/`chat`/`hf`/`latest`: variant labels that OR appends but
    # AA doesn't (AA had 0% Llama/Mistral coverage before this fix
    # because "Llama 3.1 70B Instruct" canonicalized to
    # "llama-3-1-70b-instruct" while AA had "llama-3-1-70b").
    s = re.sub(
        r"\b(preview|experimental|exp|alpha|beta|rc\d*|it|instruct|chat|hf|latest)\b",
        "",
        s,
    )
    # Strip trailing date/version suffixes: -YYYY, -YYYYMMDD, -MMDD,
    # or bare 4-digit year. Codestral "-2508" and Ministral "-2512" are
    # OR's date-of-release suffix; AA uses the bare family name.
    s = re.sub(r"[- ]\d{4,8}$", "", s)
    # Normalise to alphanum + single hyphen separator
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def build_index(aa_rows: list[dict]) -> dict[tuple[str, str], list[dict]]:
    index: dict[tuple[str, str], list[dict]] = {}
    for row in aa_rows:
        key = (canon_provider(row["creator"]), canon_name(row["name"]))
        index.setdefault(key, []).append(row)
    return index


def db_candidate_keys(agent_id: str, agent_name: str, provider: str) -> list[tuple[str, str]]:
    """
    Return all (provider, name) keys we'd try to match against AA.

    DB ids look like "anthropic/claude-opus-4.6"; names look like
    "Anthropic: Claude Opus 4.6". Both yield the same canonical name, but
    the id form is more reliable when name strings have decoration.
    """
    candidates = []
    cp = canon_provider(provider)

    # From the human name (strip "Provider: " prefix if present)
    if ":" in agent_name:
        candidates.append((cp, canon_name(agent_name.split(":", 1)[1].strip())))
    candidates.append((cp, canon_name(agent_name)))

    # From the id ("provider/name")
    if "/" in agent_id:
        id_name = agent_id.split("/", 1)[1]
        candidates.append((cp, canon_name(id_name)))

    # Dedupe while preserving order
    seen = set()
    unique = []
    for k in candidates:
        if k not in seen:
            seen.add(k)
            unique.append(k)
    return unique


def load_overrides() -> dict[str, dict]:
    """Manual overrides keyed by agent id, e.g. {"anthropic/claude-opus-4.6": {"tps": 72, "ttft_ms": 1500}}."""
    if not OVERRIDES_PATH.exists():
        return {}
    try:
        return json.loads(OVERRIDES_PATH.read_text())
    except (json.JSONDecodeError, OSError) as e:
        log(f"  WARNING: could not read {OVERRIDES_PATH.name}: {e}")
        return {}


def match_db_agents(aa_index: dict, db_agents: list[sqlite3.Row], overrides: dict) -> dict:
    """
    Return {agent_id: {tps, ttft_ms, source}} for every agent we can resolve.
    Agents not in result have no speed data and remain NULL in DB.
    """
    out = {}
    for a in db_agents:
        agent_id = a["id"]

        # Overrides take precedence
        if agent_id in overrides:
            ov = overrides[agent_id]
            out[agent_id] = {
                "tps": ov.get("tps"),
                "ttft_ms": ov.get("ttft_ms"),
                "intelligence_index": ov.get("intelligence_index"),
                "source": "manual_override",
            }
            continue

        for key in db_candidate_keys(agent_id, a["name"], a["provider"]):
            if key in aa_index:
                speeds = [d["tps"] for d in aa_index[key] if d.get("tps") is not None]
                ttfts = [d["ttft_ms"] for d in aa_index[key] if d.get("ttft_ms") is not None]
                intels = [
                    d["intelligence_index"]
                    for d in aa_index[key]
                    if d.get("intelligence_index") is not None
                ]
                out[agent_id] = {
                    "tps": median(speeds) if speeds else None,
                    "ttft_ms": median(ttfts) if ttfts else None,
                    "intelligence_index": median(intels) if intels else None,
                    "source": f"artificialanalysis.ai (n={len(aa_index[key])})",
                }
                break
    return out


def write_parsed_cache(aa_rows: list[dict], matches: dict) -> None:
    payload = {
        "fetched_at": datetime.now().isoformat(),
        "source": AA_URL,
        "row_count": len(aa_rows),
        "match_count": len(matches),
        "rows": aa_rows,
        "matches": matches,
    }
    PARSED_JSON_PATH.write_text(json.dumps(payload, indent=2, default=str))
    log(f"  cached → {PARSED_JSON_PATH.name} ({len(matches)} matches)")


def update_database(matches: dict) -> tuple[int, int, int]:
    """Returns (rows_updated_throughput, rows_updated_intelligence, skipped).

    A row with intelligence but no throughput still gets written (the
    `aa_intelligence_index` column populates even if speed columns
    stay NULL). Lets the quality scorer use AA's intelligence index
    independently of throughput coverage.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    updated_tput = 0
    updated_intel = 0
    skipped = 0
    for agent_id, m in matches.items():
        if m.get("tps") is None and m.get("intelligence_index") is None:
            skipped += 1
            continue
        if m.get("tps") is not None:
            cursor.execute(
                """
                UPDATE agents
                   SET output_tokens_per_sec = ?,
                       ttft_ms = ?,
                       speed_source = ?,
                       speed_updated_at = ?
                 WHERE id = ?
                """,
                (m["tps"], m.get("ttft_ms"), m.get("source"), now, agent_id),
            )
            if cursor.rowcount > 0:
                updated_tput += 1
        if m.get("intelligence_index") is not None:
            cursor.execute(
                "UPDATE agents SET aa_intelligence_index = ? WHERE id = ?",
                (m["intelligence_index"], agent_id),
            )
            if cursor.rowcount > 0:
                updated_intel += 1
    conn.commit()
    conn.close()
    return updated_tput, updated_intel, skipped


def main() -> int:
    parser = argparse.ArgumentParser(description="Scrape artificialanalysis.ai throughput data")
    parser.add_argument("--dry-run", action="store_true", help="Show matches without updating DB")
    parser.add_argument(
        "--use-cache", action="store_true", help="Reuse cached HTML instead of fetching"
    )
    args = parser.parse_args()

    if args.use_cache and RAW_HTML_PATH.exists():
        log(f"using cached {RAW_HTML_PATH.name}")
        html = RAW_HTML_PATH.read_text()
    else:
        html = fetch_html()

    aa_rows = parse_table(html)
    aa_index = build_index(aa_rows)
    log(f"  unique (provider, model) keys: {len(aa_index)}")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    db_agents = conn.execute(
        "SELECT id, name, provider FROM agents WHERE status='active' AND blocked=0"
    ).fetchall()
    conn.close()
    log(f"  active agents in DB: {len(db_agents)}")

    overrides = load_overrides()
    if overrides:
        log(f"  manual overrides loaded: {len(overrides)}")

    matches = match_db_agents(aa_index, db_agents, overrides)
    log(
        f"  matched {len(matches)} / {len(db_agents)} agents ({100 * len(matches) // len(db_agents)}%)"
    )

    write_parsed_cache(aa_rows, matches)

    if args.dry_run:
        log("--dry-run: not updating DB")
        # Show first 30 matches
        for _i, (agent_id, m) in enumerate(sorted(matches.items())[:30]):
            tps = m.get("tps")
            print(
                f"  {agent_id:50} tps={tps:>5.0f if tps else 'n/a'}  source={m.get('source', '')}"
            )
        return 0

    updated_tput, updated_intel, skipped = update_database(matches)
    log(
        f"DB updated: throughput={updated_tput} · intelligence_index={updated_intel} · "
        f"skipped={skipped}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
