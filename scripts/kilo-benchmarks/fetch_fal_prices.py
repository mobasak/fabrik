#!/usr/bin/env python3
"""Fetch per-model pricing from fal.ai's catalog API and merge into
`agents.gateway_prices`.

Why API consumer (not scrape): Pass 2 of plan-2-aggregator-pricing.md proved
`GET https://fal.ai/api/models` with `Authorization: Key $FAL_KEY` returns
paginated catalog. Each model carries a `pricingInfoOverride` Markdown
field with vendor-quoted pricing (`**$0.08** per image`, etc.).

Parser handles 5 canonical pricing-info shapes per the Pass-2 spec:

  per-image:     "**$0.08** per image"
  per-megapixel: "**$0.03** for first megapixel"
  per-second:    "**$0.10/second**"  or  "**$0.05** per second"
  per-minute:    "**$3** per minute"
  per-token:     "Text tokens (per 1M): **$5.00** input"  # noqa: docstring example

A 6th case — null `pricingInfoOverride` — is recorded with confidence=0
so Phase 3 (derive_cheapest_gateway) excludes it from the price comparison.

Output shape (merged into `agents.gateway_prices`):

  {
    "fal_ai": {
      "price": 80000,             # normalized to $/M billable units
      "unit": "image",            # canonical billing unit
      "slug": "fal-ai/flux-pro/v1.1",
      "url": "https://fal.run/fal-ai/flux-pro/v1.1",
      "last_seen": "2026-06-29",
      "raw_text": "**$0.08** per image",
      "confidence": 1.0
    }
  }

Idempotent: re-running overwrites the `fal_ai` key; sibling gateway
entries are preserved.

Resilience contract: explicit httpx timeout, 3 retries with exponential
backoff on transient errors, throttle 0.3s between pages.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx
import yaml

SCRIPT_DIR = Path(__file__).parent
DB_PATH = SCRIPT_DIR / "kilo_agents.db"
MIRROR_MAP_PATH = SCRIPT_DIR / "fal_mirrors.yaml"
CACHE_PATH = SCRIPT_DIR / "cache" / "fal_catalog.json"

FAL_CATALOG_URL = "https://fal.ai/api/models?page={page}"
FAL_MODEL_URL_TPL = "https://fal.run/{slug}"
FAL_MODEL_PAGE_TPL = "https://fal.ai/models/{slug}"

# Pattern observed on fal.ai model pages when pricingInfoOverride is null:
#   `cost<!-- --> <span class="...">$<!-- -->0.003</span> <!-- -->per <!-- --> <!-- -->megapixel<!-- -->.`
# We extract the price ± unit pair from that HTML fragment.
_HTML_COST_RE = re.compile(
    r"cost<!--\s*-->\s*<span[^>]*>\$<!--\s*-->([\d.]+)</span>\s*<!--\s*-->per\s*<!--\s*-->\s*<!--\s*-->(\w+)",
    re.I,
)

# Resilience tuning
HTTP_TIMEOUT = httpx.Timeout(connect=5.0, read=30.0, write=10.0, pool=5.0)
RETRY_DELAYS_SEC = (2, 4, 8)
PAGE_DELAY_SEC = 0.3


def _log(msg: str) -> None:
    print(f"[fetch_fal_prices] {msg}")


def _today() -> str:
    return datetime.now(UTC).date().isoformat()


def _get_fal_key() -> str:
    key = os.environ.get("FAL_KEY", "").strip()
    if not key:
        env_path = SCRIPT_DIR.parent.parent / ".env"
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                if line.startswith("FAL_KEY="):
                    key = line.split("=", 1)[1].strip()
                    break
    return key


def load_mirrors(path: Path = MIRROR_MAP_PATH) -> dict[str, str]:
    if not path.exists():
        _log(f"WARN: {path} missing — no mirrors to fetch")
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data.get("mirrors", {})


def _fetch_page(client: httpx.Client, page: int, fal_key: str) -> list[dict] | None:
    url = FAL_CATALOG_URL.format(page=page)
    headers = {"Authorization": f"Key {fal_key}"}
    last_exc: Exception | None = None
    for attempt, delay in enumerate([0, *RETRY_DELAYS_SEC]):
        if delay:
            time.sleep(delay)
        try:
            resp = client.get(url, headers=headers)
            if resp.status_code == 200:
                return resp.json().get("items") or []
            if 400 <= resp.status_code < 500:
                # Pass 2 Finding F3: distinguish auth failures from "end of pages".
                # Empty catalog with no loud signal previously made stale FAL_KEY
                # look like "fal has no models". Now: explicit auth-error log.
                if resp.status_code in (401, 403):
                    _log(
                        f"  AUTH FAIL page {page}: HTTP {resp.status_code} — check FAL_KEY"
                        f" (will return empty catalog, downstream will skip fal entries)"
                    )
                else:
                    _log(f"  FAIL page {page}: HTTP {resp.status_code} (permanent)")
                return None
            _log(f"  retry {attempt + 1}/3 page {page}: HTTP {resp.status_code}")
        except (httpx.TimeoutException, httpx.NetworkError, json.JSONDecodeError) as e:
            last_exc = e
            _log(f"  retry {attempt + 1}/3 page {page}: {type(e).__name__}")
    _log(f"  FAIL page {page}: exhausted retries — {last_exc}")
    return None


def fetch_catalog(fal_key: str, max_pages: int | None = None) -> dict[str, str | None]:
    """Returns {fal_id: pricingInfoOverride}. None means the vendor hasn't filled it in."""
    out: dict[str, str | None] = {}
    with httpx.Client(timeout=HTTP_TIMEOUT, follow_redirects=True) as client:
        page = 1
        while True:
            items = _fetch_page(client, page, fal_key)
            if items is None or not items:
                break
            for item in items:
                out[item["id"]] = item.get("pricingInfoOverride")
            if max_pages is not None and page >= max_pages:
                break
            page += 1
            time.sleep(PAGE_DELAY_SEC)
    return out


# ============================================================
# Parser — pricingInfoOverride Markdown → normalized payload
# ============================================================
# Bold price pattern: `**$X.YZ**` or bare `$X.YZ`.
_PRICE_RE = re.compile(r"\*?\*?\$([\d,]+(?:\.\d+)?)\*?\*?")
_PRICE_PER_UNIT_RE = re.compile(r"\*?\*?\$([\d,]+(?:\.\d+)?)\*?\*?\s*(?:per|/)\s*(\w+)", re.I)


def _to_float(s: str) -> float | None:
    try:
        return float(s.replace(",", ""))
    except ValueError:
        return None


def _per_image_match(text: str) -> tuple[float, str] | None:
    """Match '$0.08 per image' / '$0.04/image' patterns."""
    m = re.search(
        r"\*?\*?\$(\d+(?:\.\d+)?)\*?\*?\s*(?:per|/)\s*image\b",
        text,
        re.I,
    )
    if m:
        v = _to_float(m.group(1))
        if v is not None:
            return v, m.group(0)
    return None


def _per_megapixel_match(text: str) -> tuple[float, str] | None:
    m = re.search(
        r"\*?\*?\$(\d+(?:\.\d+)?)\*?\*?\s*(?:per|/|for)\s*(?:first\s+)?(?:mega\s*pixel|megapixel|MP)\b",
        text,
        re.I,
    )
    if m:
        v = _to_float(m.group(1))
        if v is not None:
            return v, m.group(0)
    return None


def _per_second_match(text: str) -> tuple[float, str] | None:
    m = re.search(
        r"\*?\*?\$(\d+(?:\.\d+)?)\*?\*?\s*(?:per|/)\s*(?:second|sec|s)\b",
        text,
        re.I,
    )
    if m:
        v = _to_float(m.group(1))
        if v is not None:
            return v, m.group(0)
    return None


def _per_minute_match(text: str) -> tuple[float, str] | None:
    m = re.search(
        r"\*?\*?\$(\d+(?:\.\d+)?)\*?\*?\s*(?:per|/)\s*minute\b",
        text,
        re.I,
    )
    if m:
        v = _to_float(m.group(1))
        if v is not None:
            return v, m.group(0)
    return None


def _per_million_tokens_match(text: str) -> tuple[float, str] | None:
    """For LLM-style pricing on fal.ai (e.g. openai/gpt-image-2 text inputs).
    Pattern: `Text tokens (per 1M): **$5.00** input` — capture the first input price.

    Adversarial Pass 1 Finding C: also handle bare-numeric denominators
    like "per 1000 tokens" / "per 1000000 tokens" where the vendor didn't
    use the M/K shorthand. Previously these were silently dropped.
    """
    # Pattern: "per <num>[MK]? [optional 'tokens' word][punct]* $<price> input"
    # Examples:
    #   "Text tokens (per 1M): **$5.00** input"
    #   "per 1000 tokens, **$5** input"
    #   "per 1K tokens: **$0.005** input"
    m = re.search(
        r"per\s+(\d+)\s*([MK])?\s*(?:tokens?)?\s*\)?\s*[:\-,]?\s*\*?\*?\$(\d+(?:\.\d+)?)\*?\*?\s*input",
        text,
        re.I,
    )
    if not m:
        return None
    denom_num = int(m.group(1))
    denom_suffix = (m.group(2) or "").upper()
    v = _to_float(m.group(3))
    if v is None:
        return None
    # Resolve denominator → multiplier from $/X-tokens to $/M-tokens.
    if denom_suffix == "M":
        return v, m.group(0)
    if denom_suffix == "K":
        return v * 1000, m.group(0)
    # Bare-numeric (no suffix). Common values: 1M = 1_000_000, 1K = 1000.
    if denom_num >= 100_000:
        # Treat ≥100K as million-scale (1_000_000 or close).
        return v * (1_000_000 / denom_num), m.group(0)
    if denom_num >= 100:
        # 100..99_999 → treat as K-scale (e.g. "per 1000" → ×1000).
        return v * (1_000_000 / denom_num), m.group(0)
    # < 100: too small to disambiguate safely (could be "per 1 thousand" without commas etc).
    return None


def _fetch_model_page_pricing(
    client: httpx.Client, slug: str
) -> tuple[float, str, float, str] | None:
    """Fallback for null pricingInfoOverride: scrape the model's public
    HTML page for `cost $X per Y` (the visible UI).

    Returns (normalized_price, unit, confidence, raw_match) or None.

    Pass 5 Finding F5-1 fix: retry on transient errors (timeouts, 5xx).
    Previously single-attempt → transient 5xx silently dropped pricing
    for the day. Now matches the 3-retry pattern of the catalog API.
    """
    url = FAL_MODEL_PAGE_TPL.format(slug=slug)
    resp = None
    for delay in [0, *RETRY_DELAYS_SEC]:
        if delay:
            time.sleep(delay)
        try:
            resp = client.get(url)
        except (httpx.TimeoutException, httpx.NetworkError):
            continue
        if resp.status_code == 200:
            break
        if 400 <= resp.status_code < 500:
            return None  # permanent 4xx — don't retry
        # Else 5xx: fall through, retry
    if resp is None or resp.status_code != 200:
        return None
    m = _HTML_COST_RE.search(resp.text)
    if not m:
        return None
    try:
        v = float(m.group(1))
    except ValueError:
        return None
    raw_unit = m.group(2).lower()
    raw_match = m.group(0)
    if raw_unit in ("image", "images"):
        return v * 1_000_000, "image", 1.0, raw_match
    if raw_unit in ("megapixel", "megapixels", "mp"):
        # MP ≠ strictly image; flag confidence 0.7 (matches text-parsed per-MP).
        return v * 1_000_000, "image", 0.7, raw_match
    if raw_unit in ("second", "seconds", "s"):
        return v * 1_000_000, "video-sec", 1.0, raw_match
    if raw_unit in ("minute", "minutes"):
        return v * 1_000_000 / 60, "audio-min", 1.0, raw_match
    return None


def parse_pricing(text: str | None) -> tuple[float, str, float, str] | None:
    """Parse a fal pricingInfoOverride into (normalized_price, canonical_unit, confidence, raw_match).

    `normalized_price` is on the same $/M-billable-units axis as
    seed_direct_vendors.py. `canonical_unit` is `image`, `audio-min`,
    `video-sec`, `M-tokens`, etc.

    Returns None when the text is null or no recognized pattern matched
    (caller stores confidence=0 in that case).
    """
    if not text:
        return None

    # Order matters: prefer per-image > per-megapixel > per-second > per-minute > per-token.
    # (Multi-resolution shapes like "720p $0.30/s, 1080p $0.68/s" still hit per-second.)
    r = _per_image_match(text)
    if r:
        v, raw = r
        return v * 1_000_000, "image", 1.0, raw

    r = _per_megapixel_match(text)
    if r:
        # 1 MP = 1M pixels. Use "image" semantics with a note that this is per-MP.
        v, raw = r
        return v * 1_000_000, "image", 0.7, raw  # confidence 0.7: MP ≠ image strictly

    r = _per_second_match(text)
    if r:
        v, raw = r
        return v * 1_000_000, "video-sec", 1.0, raw

    r = _per_minute_match(text)
    if r:
        v, raw = r
        # $/min × 60 → $/M-audio-sec normalization (matches Replicate audio convention)
        return v * 1_000_000 / 60, "audio-min", 1.0, raw

    r = _per_million_tokens_match(text)
    if r:
        v, raw = r
        return v, "M-tokens", 1.0, raw

    return None


def upsert_fal_price(conn: sqlite3.Connection, agent_id: str, payload: dict) -> bool:
    """Merge {'fal_ai': payload} into agents.gateway_prices for this row."""
    row = conn.execute("SELECT id, gateway_prices FROM agents WHERE id = ?", (agent_id,)).fetchone()
    if not row:
        return False
    try:
        current = json.loads(row[1]) if row[1] else {}
    except (json.JSONDecodeError, TypeError):
        current = {}
    current["fal_ai"] = payload
    conn.execute(
        "UPDATE agents SET gateway_prices = ? WHERE id = ?",
        (json.dumps(current), agent_id),
    )
    return True


def run(
    db_path: Path = DB_PATH,
    mirror_path: Path = MIRROR_MAP_PATH,
    dry_run: bool = False,
    max_pages: int | None = None,
) -> dict[str, int]:
    counts = {
        "catalog_models": 0,
        "mirror_hits": 0,
        "parsed": 0,
        "written": 0,
        "null_pricing": 0,
        "missing_row": 0,
    }
    mirrors = load_mirrors(mirror_path)
    if not mirrors:
        _log("nothing to do — empty mirror map")
        return counts

    fal_key = _get_fal_key()
    if not fal_key:
        _log("FAL_KEY not configured (env or /opt/fabrik/.env) — aborting")
        return counts

    catalog = fetch_catalog(fal_key, max_pages=max_pages)
    counts["catalog_models"] = len(catalog)
    _log(f"catalog: {len(catalog)} models")

    # Cache for diff-detection on next run
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps({"_fetched": _today(), "items": catalog}, indent=2))

    conn = sqlite3.connect(db_path)
    try:
        # Pass 2 Finding F4: explicit transaction for atomicity.
        if not dry_run:
            conn.execute("BEGIN")
        # Reuse one httpx client for both catalog-already-fetched models
        # AND for HTML fallback on null-override entries.
        with httpx.Client(timeout=HTTP_TIMEOUT, follow_redirects=True) as page_client:
            for agent_id, fal_id in mirrors.items():
                raw = catalog.get(fal_id)
                if fal_id not in catalog:
                    _log(f"  MISS {agent_id}: '{fal_id}' not in catalog")
                    continue
                counts["mirror_hits"] += 1
                parsed = parse_pricing(raw)
                # Fallback: try to scrape pricing from the model's public HTML
                # page when the API-side pricingInfoOverride is null.
                if parsed is None:
                    parsed = _fetch_model_page_pricing(page_client, fal_id)
                url = FAL_MODEL_URL_TPL.format(slug=fal_id)
                if parsed is None:
                    counts["null_pricing"] += 1
                    payload = {
                        "price": None,
                        "unit": None,
                        "slug": fal_id,
                        "url": url,
                        "last_seen": _today(),
                        "raw_text": raw,
                        "confidence": 0.0,
                    }
                    if dry_run:
                        _log(f"  DRY {agent_id}: NULL pricing (confidence=0)")
                        continue
                    if upsert_fal_price(conn, agent_id, payload):
                        counts["written"] += 1
                    else:
                        counts["missing_row"] += 1
                    continue
                price, unit, conf, raw_match = parsed
                counts["parsed"] += 1
                payload = {
                    "price": round(price, 4),
                    "unit": unit,
                    "slug": fal_id,
                    "url": url,
                    "last_seen": _today(),
                    "raw_text": raw,
                    "raw_match": raw_match,
                    "confidence": conf,
                }
                if dry_run:
                    _log(
                        f"  DRY {agent_id}: ${price:.2f}/M-{unit} (raw: {raw_match!r}, conf={conf})"
                    )
                    continue
                if upsert_fal_price(conn, agent_id, payload):
                    counts["written"] += 1
                    _log(f"  OK  {agent_id}: ${price:.2f}/M-{unit} ({raw_match})")
                else:
                    counts["missing_row"] += 1
                    _log(f"  SKIP {agent_id}: no such row in agents table")
            if not dry_run:
                conn.commit()
    except Exception:
        try:
            conn.execute("ROLLBACK")
        except Exception:
            pass
        raise
    finally:
        conn.close()
    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DB_PATH)
    parser.add_argument("--mirrors", type=Path, default=MIRROR_MAP_PATH)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--max-pages", type=int, default=None, help="Cap pages for fast testing (default: all 35)"
    )
    args = parser.parse_args()
    counts = run(args.db, args.mirrors, args.dry_run, args.max_pages)
    _log(f"summary: {counts}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
