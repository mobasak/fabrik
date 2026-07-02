#!/usr/bin/env python3
"""
Scrape Groq's LPU tokens-per-second table from https://groq.com/pricing.

Mirrors the pattern in `scrape_artificial_analysis.py`:
- Cache raw HTML + parsed JSON under cache/
- Retry on network errors with exponential backoff
- Reuse AA's `canon_provider`/`canon_name`/`db_candidate_keys`/`match_db_agents`
  normalizers (do not duplicate).

Design rationale:
- Groq's tps values reflect their LPU hardware — only realized when you pin
  `provider.only=["Groq"]` in the OpenRouter request. We tag such rows with
  `speed_source="groq_lpu (pin required)"` so operators know it's provider-
  specific.
- Authoritative-source ordering (higher wins):
    manual_override > own_microbench* > artificialanalysis.ai* > groq_lpu* > NULL
  We ONLY write to rows where `speed_source IS NULL` OR `speed_source LIKE
  'groq_lpu%'` (never clobber a higher-precedence source).

Usage:
    python scrape_groq_speeds.py             # scrape + update DB
    python scrape_groq_speeds.py --use-cache # reuse cached HTML
    python scrape_groq_speeds.py --dry-run   # show matches without writing
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from datetime import UTC, datetime
from functools import wraps
from pathlib import Path
from time import sleep

import requests
from bs4 import BeautifulSoup

SCRIPT_DIR = Path(__file__).parent
CACHE_DIR = SCRIPT_DIR / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = SCRIPT_DIR / "kilo_agents.db"

GROQ_URL = "https://groq.com/pricing"
RAW_HTML_PATH = CACHE_DIR / "groq_raw.html"
PARSED_JSON_PATH = CACHE_DIR / "groq_parsed.json"

# Verified 2026-07-02: the minimal fabrik-audit UA gets zero-hit content;
# Chrome-like UA returns the pricing table intact.
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

SPEED_SOURCE_TAG = "groq_lpu (pin required)"


def log(msg: str) -> None:
    print(f"[groq-scrape] {msg}")


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
                        log(f"  Error in {func.__name__}: {e}")
                        raise
                    log(
                        f"  Attempt {attempt}/{max_attempts} failed, retrying in {current_delay}s..."
                    )
                    sleep(current_delay)
                    current_delay *= backoff
                    attempt += 1
            return func(*args, **kwargs)

        return wrapper

    return decorator


@retry_on_network_error()
def fetch_html() -> str:
    log(f"GET {GROQ_URL}")
    resp = requests.get(GROQ_URL, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    RAW_HTML_PATH.write_text(resp.text)
    log(f"  cached → {RAW_HTML_PATH.name} ({len(resp.text)} bytes)")
    return resp.text


def parse_pricing_table(html: str) -> list[dict]:
    """Extract (name, tps) per row from the pricing HTML `<table>`.

    Groq's page is server-rendered HTML with a standard <table class="type-ui-1">.
    Header row: [AI Model | Current Speed (Tokens per Second) | Input Token
    Price | Output Token Price].

    Cell text carries a mobile-first-label prefix that must be stripped:
      Model cell: "AI Model GPT OSS 20B 128k"    → "GPT OSS 20B 128k"
      TPS cell:   "Current Speed 1,000 TPS"     → 1000
    """
    if not html:
        return []
    try:
        soup = BeautifulSoup(html, "html.parser")
    except Exception as e:  # noqa: BLE001 — total-parse-collapse is fail-soft here
        log(f"  parse error: {e} — returning empty")
        return []

    # Find the table whose text contains "Tokens per Second" — this is the
    # pricing/speed table (not the sibling pricing table for models Groq
    # doesn't yet serve or a marketing comparison table).
    target = None
    for tbl in soup.find_all("table"):
        if "Tokens per Second" in tbl.get_text():
            target = tbl
            break
    if target is None:
        log("  no pricing table found in HTML — returning empty")
        return []

    rows = []
    for tr in target.find_all("tr"):
        cells = tr.find_all("td")
        if len(cells) < 2:
            continue  # header row or malformed row
        model_raw = cells[0].get_text(" ", strip=True)
        tps_raw = cells[1].get_text(" ", strip=True)

        # Strip mobile-first-label prefixes
        model = re.sub(r"^\s*AI Model\s+", "", model_raw)
        tps_str = re.sub(r"^\s*Current Speed\s+", "", tps_raw)
        tps_str = re.sub(r"\s*TPS\s*$", "", tps_str)
        tps_str = tps_str.replace(",", "").strip()

        try:
            tps = int(tps_str)
        except ValueError:
            log(f"  skipping row with unparseable TPS: model={model!r} tps={tps_raw!r}")
            continue

        rows.append({"name": model, "tps": tps})

    log(f"  parsed {len(rows)} rows")
    return rows


# ---------- Model-name pre-normalization (Groq-local) ----------
# Groq uses variant tokens AA doesn't. Pre-normalize BEFORE calling AA's
# canon_name so AA's behavior stays untouched (safer than editing AA's
# noise-word list, which is shared with the AA scraper).

_TRAILING_CTX_RE = re.compile(r"\s*\d+k\s*$", re.I)
_SIZE_CODE_RE = re.compile(r"\s*\(17bx?16?e?\)\s*", re.I)
_VARIANT_LABEL_RE = re.compile(r"\b(versatile|instant)\b", re.I)


def normalize_groq_name(name: str) -> str:
    """Strip Groq-specific variant tokens + context markers before matching."""
    s = _TRAILING_CTX_RE.sub("", name)
    s = _SIZE_CODE_RE.sub(" ", s)
    s = _VARIANT_LABEL_RE.sub("", s)
    return re.sub(r"\s+", " ", s).strip()


# Explicit Groq-name → OR agent-id map for Groq's stable-name set.
# The AA canonicalizer can't bridge all of these because Groq spells
# names with different word-vs-digit spacing than OR/DB (e.g. Groq
# "Llama 4 Scout" ↔ OR `meta-llama/llama-4-scout`). This map is checked
# BEFORE the AA fuzzy matcher — it's an override, not a fallback.
#
# Keys are `normalize_groq_name(row["name"])` outputs (variant/context
# already stripped). Regen when Groq adds/renames models.
GROQ_TO_OR_ID = {
    "GPT OSS 20B": "openai/gpt-oss-20b",
    "GPT OSS Safeguard 20B": "openai/gpt-oss-safeguard-20b",
    "GPT OSS 120B": "openai/gpt-oss-120b",
    "Llama 4 Scout": "meta-llama/llama-4-scout",
    "Qwen3 32B": "qwen/qwen3-32b",
    "Llama 3.3 70B": "meta-llama/llama-3.3-70b-instruct",
    "Llama 3.1 8B": "meta-llama/llama-3.1-8b-instruct",
    "Qwen 3.6 27B": "qwen/qwen3.6-27b",
}


# ---------- Matcher ----------

# Groq's "Creator" column is implicit (they always host from a known set).
# We map by peeking at the model name prefix.
# Regex fragments intentionally use `\b<word>` (no trailing `\b`) so
# names like "qwen3" and "llama4" match — Python's `\b` doesn't fire
# between two word chars (letter→digit is not a word boundary).
_CREATOR_HEURISTICS = {
    r"\bllama": "meta",
    r"\bqwen": "qwen",
    r"\bgpt[ -]?oss": "openai",
    r"\bkimi": "moonshotai",
    r"\bdeepseek": "deepseek",
    r"\bgemma": "google",
}


def infer_creator(name: str) -> str:
    lc = name.lower()
    for pattern, creator in _CREATOR_HEURISTICS.items():
        if re.search(pattern, lc):
            return creator
    return "unknown"


def match_to_db(groq_rows: list[dict], conn: sqlite3.Connection) -> dict[str, dict]:
    """Match Groq rows to DB agent ids.

    Strategy (in order):
      1. `GROQ_TO_OR_ID` explicit map — checked against `normalize_groq_name(row["name"])`.
         This is the primary path — Groq's ~8-model catalog is stable enough
         to hand-map, and the explicit form avoids fuzzy-canon false-positives.
      2. AA `canon_name` fuzzy match — fallback for models added to Groq's
         catalog after this file's last update. Uses the same (canon_provider,
         canon_name) key set that AA's matcher uses.

    Returns `{agent_id: {"tps": int, "groq_name": str}}`.
    """
    sys.path.insert(0, str(SCRIPT_DIR))
    from scrape_artificial_analysis import canon_name, canon_provider, db_candidate_keys

    conn.row_factory = sqlite3.Row
    db_agents = conn.execute(
        "SELECT id, name, provider FROM agents WHERE status='active'"
    ).fetchall()
    db_ids = {a["id"] for a in db_agents}

    key_to_agent: dict[tuple[str, str], list[str]] = {}
    for a in db_agents:
        for k in db_candidate_keys(a["id"], a["name"] or "", a["provider"] or ""):
            key_to_agent.setdefault(k, []).append(a["id"])

    out: dict[str, dict] = {}
    for row in groq_rows:
        normalized = normalize_groq_name(row["name"])

        # Strategy 1: explicit map
        explicit_id = GROQ_TO_OR_ID.get(normalized)
        if explicit_id and explicit_id in db_ids:
            out[explicit_id] = {"tps": row["tps"], "groq_name": row["name"]}
            continue

        # Strategy 2: fuzzy canon match
        creator = infer_creator(row["name"])
        target_key = (canon_provider(creator), canon_name(normalized))
        hits = key_to_agent.get(target_key)
        if not hits:
            log(f"  no match for Groq name={row['name']!r} (canon={target_key})")
            continue
        chosen = next((h for h in hits if not h.endswith(":free")), hits[0])
        out[chosen] = {"tps": row["tps"], "groq_name": row["name"]}
    log(f"  matched {len(out)} / {len(groq_rows)} against DB")
    return out


# ---------- DB writer ----------


def update_database(matches: dict[str, dict], db_path: Path = DB_PATH) -> tuple[int, int, int]:
    """Write tps + speed_source for each matched agent.

    Returns (updated, skipped_precedence, skipped_no_change).

    Never clobbers higher-precedence sources — the WHERE guards it explicitly.
    """
    today = datetime.now(UTC).date().isoformat()
    conn = sqlite3.connect(db_path)
    updated = skipped_precedence = skipped_no_change = 0
    try:
        for agent_id, m in matches.items():
            # Only write if speed_source is NULL or already a groq_lpu row.
            cur = conn.execute(
                "UPDATE agents SET "
                "output_tokens_per_sec = ?, "
                "speed_source = ?, "
                "speed_updated_at = ? "
                "WHERE id = ? "
                "AND (speed_source IS NULL OR speed_source LIKE 'groq_lpu%')",
                (m["tps"], SPEED_SOURCE_TAG, today, agent_id),
            )
            if cur.rowcount == 1:
                updated += 1
            else:
                # Either the id doesn't exist (shouldn't happen — we just
                # matched it) or the precedence guard rejected the write.
                # Peek to distinguish.
                r = conn.execute(
                    "SELECT speed_source FROM agents WHERE id=?", (agent_id,)
                ).fetchone()
                if r and r[0] and not str(r[0]).startswith("groq_lpu"):
                    skipped_precedence += 1
                else:
                    skipped_no_change += 1
        conn.commit()
    finally:
        conn.close()
    log(f"  DB updated: {updated} rows · skipped_precedence: {skipped_precedence}")
    return updated, skipped_precedence, skipped_no_change


def write_parsed_cache(rows: list[dict], matches: dict[str, dict]) -> None:
    payload = {
        "scraped_at": datetime.now(UTC).isoformat(),
        "source": GROQ_URL,
        "row_count": len(rows),
        "match_count": len(matches),
        "rows": rows,
        "matches": matches,
    }
    PARSED_JSON_PATH.write_text(json.dumps(payload, indent=2, default=str))
    log(f"  cached → {PARSED_JSON_PATH.name} ({len(matches)} matches)")


# ---------- CLI ----------


def main() -> int:
    parser = argparse.ArgumentParser(description="Scrape Groq LPU tokens/sec data")
    parser.add_argument("--dry-run", action="store_true", help="Parse + match but do not touch DB")
    parser.add_argument(
        "--use-cache",
        action="store_true",
        help=f"Reuse cached HTML at {RAW_HTML_PATH.name}",
    )
    args = parser.parse_args()

    if args.use_cache and RAW_HTML_PATH.exists():
        log(f"using cached {RAW_HTML_PATH.name}")
        html = RAW_HTML_PATH.read_text()
    else:
        html = fetch_html()

    rows = parse_pricing_table(html)
    if not rows:
        log("  parsed 0 rows — check HTML shape (Groq may have redesigned)")
        return 1  # loud failure per the plan's fail-soft strategy

    conn = sqlite3.connect(DB_PATH)
    try:
        matches = match_to_db(rows, conn)
    finally:
        conn.close()

    if args.dry_run:
        log(f"  would write to DB (dry-run): {len(matches)} rows")
        write_parsed_cache(rows, matches)
        return 0

    updated, skipped_precedence, _ = update_database(matches)
    write_parsed_cache(rows, matches)
    log(f"  summary: updated={updated}, respected_precedence={skipped_precedence}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
