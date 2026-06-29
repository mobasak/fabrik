#!/usr/bin/env python3
"""Fetch per-model pricing from Replicate by scraping `billingConfig` blobs
out of the public model page HTML, and merge into `agents.gateway_prices`.

Why HTML scrape (not API): pass 2 of plan-2-aggregator-pricing.md PROVED
`GET https://api.replicate.com/v1/models/{slug}` does NOT return a price
field. The pricing data only exists in the model page's Next.js hydration
payload (`<script id="react-component-props-*">`), inside
`billingConfig.current_tiers[0].prices[]`. Each `prices` entry carries
`price` (formatted "$0.04"), `metric` ("image_output_count" etc.) and
`type` ("per-unit" / "per-second"). Pass 3a verified the legitimacy
(robots.txt /, ToS scoped to PII not pricing) and re-verified all 12
slugs return HTTP 200 + carry the JSON in the HTML.

Output shape (merged into `agents.gateway_prices` JSON):

  {
    "replicate": {
      "price": 40000,               # normalized to $/M billable units
      "unit": "image",              # canonical billing unit
      "slug": "black-forest-labs/flux-1.1-pro",
      "url": "https://replicate.com/black-forest-labs/flux-1.1-pro",
      "last_seen": "2026-06-29",
      "raw_metric": "image_output_count",
      "raw_price_text": "$0.04"
    }
  }

Idempotent: re-running overwrites the `replicate` key; other gateway
entries (fal_ai, etc.) are preserved.

Resilience contract (per `.windsurf/rules/core/58-resilience.md:45-86`):
explicit timeouts (connect=5, read=30), 3 retries with exponential
backoff (2s/4s/8s), retry only on transient errors (timeouts + 5xx).
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import yaml

SCRIPT_DIR = Path(__file__).parent
DB_PATH = SCRIPT_DIR / "kilo_agents.db"
MIRROR_MAP_PATH = SCRIPT_DIR / "replicate_mirrors.yaml"
CACHE_DIR = SCRIPT_DIR / "cache"

USER_AGENT = "fabrik-pricing-fetcher/1 (replicate-aggregator)"
MODEL_PAGE_URL = "https://replicate.com/{slug}"

# Per-pass-3a verification: pricing JSON lives in react-component-props blocks.
# Use a tolerant regex (capture inner JSON) — we don't need a strict HTML parser.
RC_BLOCK_RE = re.compile(
    r'<script[^>]*id="[^"]*react-component-props[^"]*"[^>]*type="application/json"[^>]*>(.*?)</script>',
    re.S,
)

# Resilience tuning
HTTP_TIMEOUT = httpx.Timeout(connect=5.0, read=30.0, write=10.0, pool=5.0)
RETRY_DELAYS_SEC = (2, 4, 8)  # exponential backoff


def _log(msg: str) -> None:
    print(f"[fetch_replicate_prices] {msg}")


def _today() -> str:
    return datetime.now(UTC).date().isoformat()


def load_mirrors(path: Path = MIRROR_MAP_PATH) -> dict[str, str]:
    if not path.exists():
        _log(f"WARN: {path} missing — no mirrors to fetch")
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data.get("mirrors", {})


def fetch_model_html(slug: str, client: httpx.Client) -> str | None:
    """Fetch model page HTML with retries. Returns None on permanent failure."""
    url = MODEL_PAGE_URL.format(slug=slug)
    last_exc: Exception | None = None
    for attempt, delay in enumerate([0, *RETRY_DELAYS_SEC]):
        if delay:
            time.sleep(delay)
        try:
            resp = client.get(url, headers={"User-Agent": USER_AGENT})
            if resp.status_code == 200:
                return resp.text
            if 400 <= resp.status_code < 500:
                # 4xx is permanent — don't retry
                _log(f"  FAIL {slug}: HTTP {resp.status_code} (permanent)")
                return None
            _log(f"  retry {attempt + 1}/3 {slug}: HTTP {resp.status_code}")
            last_exc = httpx.HTTPStatusError(
                f"status {resp.status_code}", request=resp.request, response=resp
            )
        except (httpx.TimeoutException, httpx.NetworkError) as e:
            last_exc = e
            _log(f"  retry {attempt + 1}/3 {slug}: {type(e).__name__}")
    _log(f"  FAIL {slug}: exhausted retries — {last_exc}")
    return None


# Metric → (canonical unit, multiplier to per-M-billable-units)
# `input_cost_per_m` is normalized to "$ per million billable units"
# matching seed_direct_vendors.py's encoding.
METRIC_NORMALIZE: dict[str, tuple[str, float]] = {
    "image_output_count": ("image", 1_000_000),  # $0.04/img × 1M = 40000
    "output_image_count": ("image", 1_000_000),
    "predict_time": ("video-sec", 1_000_000),  # $0.10/sec × 1M = 100000
    "predict_time_audio_second": (
        "audio-min",
        1_000_000 * 60,
    ),  # $/sec audio → $/M-audio-sec normalized
    "audio_input_seconds": ("audio-min", 1_000_000 * 60),
    "characters_output_count": ("M-chars", 1_000),  # $/1K-chars × 1000 = $/M
    "tokens_output": ("M-tokens", 1_000_000),
}

# Service-type hint per agent_id for flat-shape models (billingConfig=null).
# Drives which metric a flat-shape result gets tagged as so Phase 3 can
# compare apples-to-apples with direct-vendor pricing_unit.
FLAT_SHAPE_SERVICE_HINT: dict[str, str] = {
    "openai/whisper-large-v3": "predict_time_audio_second",
    "stability/stable-audio-2": "predict_time_audio_second",
    # Default for image gens (sdxl, etc.) is image_output_count via p50.
}


def _parse_price_string(s: str) -> float | None:
    """Extract leading dollar amount from strings like '$0.04', '$0.0001 per second'."""
    m = re.search(r"\$([\d.]+)", s or "")
    if not m:
        return None
    try:
        return float(m.group(1))
    except ValueError:
        return None


def _title_quantity(title: str) -> int:
    """A 'title' like 'per thousand output images' means the price is for
    1000 units, not 1. Return the divisor implied by the title (default 1)."""
    t = (title or "").lower()
    if "per thousand" in t or "per 1k" in t or "per 1,000" in t:
        return 1000
    if "per hundred" in t or "per 100" in t:
        return 100
    if "per million" in t or "per 1m" in t or "per 1,000,000" in t:
        return 1_000_000
    return 1


def _build_payload(slug: str, raw_price: float, metric: str, price_text: str) -> dict | None:
    """Normalize one Replicate (price, metric) pair into the agents.gateway_prices shape."""
    norm = METRIC_NORMALIZE.get(metric)
    if not norm:
        _log(f"  WARN {slug}: unknown metric {metric!r} — skipping normalize")
        return None
    canonical_unit, factor = norm
    return {
        "price": round(raw_price * factor, 4),
        "unit": canonical_unit,
        "slug": slug,
        "url": MODEL_PAGE_URL.format(slug=slug),
        "last_seen": _today(),
        "raw_metric": metric,
        "raw_price_text": price_text,
        # Adversarial Pass 1 Finding D: explicit confidence so derive_row
        # is consistent across Replicate/fal_ai instead of relying on
        # implicit default-1.0 fallback.
        "confidence": 1.0,
    }


def _extract_flat_pricing(data: Any, slug: str, agent_id: str) -> dict | None:
    """Some models (sdxl, whisper, community-ported) have billingConfig=null
    but expose pricing via a sibling shape: `{hardware: 'L40S', price: '$X/sec',
    p50price: '$Y'}`. Prefer p50price (median per-run cost) when present.

    `agent_id` (our agents.id) drives the metric hint so audio models get
    audio-second semantics and image models get image-output semantics.

    Returns the normalized payload, or None if no flat-shape pricing found.
    """
    found: list[dict] = []

    def _walk(o: Any) -> None:
        if isinstance(o, dict):
            if "price" in o and "hardware" in o:
                found.append(o)
            for v in o.values():
                _walk(v)
        elif isinstance(o, list):
            for v in o:
                _walk(v)

    _walk(data)
    if not found:
        return None
    rec = found[0]
    # Audio models: prefer runtime $/sec (p50 is per-run = whole-audio cost, ambiguous).
    audio_hint = FLAT_SHAPE_SERVICE_HINT.get(agent_id)
    if audio_hint:
        runtime = _parse_price_string(rec.get("price") or "")
        if runtime is not None:
            return _build_payload(slug, runtime, audio_hint, rec.get("price") or "")
        return None
    # Image models: prefer p50price (median per-run = per-image cost).
    p50 = _parse_price_string(rec.get("p50price") or "")
    if p50 is not None:
        return _build_payload(slug, p50, "image_output_count", rec.get("p50price") or "")
    # Fall back to runtime if p50 absent — assume image.
    runtime = _parse_price_string(rec.get("price") or "")
    if runtime is not None:
        return _build_payload(slug, runtime, "predict_time", rec.get("price") or "")
    return None


def extract_pricing(html: str, slug: str, agent_id: str = "") -> dict | None:
    """Parse the react-component-props JSON blocks and pull billingConfig
    out. Returns the normalized price dict OR None if no pricing found.

    Handles two shapes: nested (`billingConfig.current_tiers[].prices[]`)
    and flat (`{billingConfig: null, hardware, price, p50price}`).
    """
    for blob in RC_BLOCK_RE.findall(html):
        try:
            data = json.loads(blob)
        except json.JSONDecodeError:
            continue
        # Shape 1: nested tiers.
        bcfg = _find_billing_config(data)
        tiers = (bcfg or {}).get("current_tiers") or []
        if tiers:
            candidates = []
            for tier in tiers:
                for p in tier.get("prices") or []:
                    price_text = p.get("price") or ""
                    metric = p.get("metric") or ""
                    ptype = p.get("type") or ""
                    title = p.get("title") or ""
                    raw = _parse_price_string(price_text)
                    if raw is None:
                        continue
                    divisor = _title_quantity(title)
                    candidates.append(
                        {
                            "price_text": price_text,
                            "metric": metric,
                            "type": ptype,
                            "title": title,
                            "raw": raw / divisor,
                        }
                    )
            chosen = next(
                (c for c in candidates if c["type"] == "per-unit" and "output" in c["metric"]),
                candidates[0] if candidates else None,
            )
            if chosen:
                return _build_payload(slug, chosen["raw"], chosen["metric"], chosen["price_text"])
        # Shape 2: flat shape (billingConfig is null but pricing siblings exist).
        flat = _extract_flat_pricing(data, slug, agent_id)
        if flat:
            return flat
    return None


def _find_billing_config(obj: Any) -> dict | None:
    """Walk the Next.js hydration JSON to find billingConfig. The exact
    nesting path is brittle, so search."""
    if isinstance(obj, dict):
        if "current_tiers" in obj and isinstance(obj.get("current_tiers"), list):
            return obj
        if "billingConfig" in obj and isinstance(obj["billingConfig"], dict):
            return obj["billingConfig"]
        for v in obj.values():
            found = _find_billing_config(v)
            if found:
                return found
    elif isinstance(obj, list):
        for item in obj:
            found = _find_billing_config(item)
            if found:
                return found
    return None


def upsert_replicate_price(conn: sqlite3.Connection, agent_id: str, payload: dict) -> bool:
    """Merge {'replicate': payload} into agents.gateway_prices for this row.
    Returns True if the row exists and was updated; False if no such row."""
    row = conn.execute("SELECT id, gateway_prices FROM agents WHERE id = ?", (agent_id,)).fetchone()
    if not row:
        return False
    try:
        current = json.loads(row[1]) if row[1] else {}
    except (json.JSONDecodeError, TypeError):
        current = {}
    current["replicate"] = payload
    conn.execute(
        "UPDATE agents SET gateway_prices = ? WHERE id = ?",
        (json.dumps(current), agent_id),
    )
    return True


def run(
    db_path: Path = DB_PATH,
    mirror_path: Path = MIRROR_MAP_PATH,
    dry_run: bool = False,
) -> dict[str, int]:
    counts = {
        "attempted": 0,
        "fetched": 0,
        "parsed": 0,
        "written": 0,
        "missing_row": 0,
        "failed": 0,
    }
    mirrors = load_mirrors(mirror_path)
    if not mirrors:
        _log("nothing to do — empty mirror map")
        return counts

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        # Pass 2 Finding F4: explicit transaction so an exception mid-loop
        # rolls back atomically instead of leaving half the rows updated.
        if not dry_run:
            conn.execute("BEGIN")
        with httpx.Client(timeout=HTTP_TIMEOUT, follow_redirects=True) as client:
            for agent_id, slug in mirrors.items():
                counts["attempted"] += 1
                html = fetch_model_html(slug, client)
                if html is None:
                    counts["failed"] += 1
                    continue
                counts["fetched"] += 1
                # Cache for diff-detection on subsequent runs.
                cache_path = CACHE_DIR / f"replicate_{slug.replace('/', '__')}.html"
                cache_path.write_text(html, encoding="utf-8")
                payload = extract_pricing(html, slug, agent_id=agent_id)
                if not payload:
                    _log(f"  no pricing extracted for {slug}")
                    continue
                counts["parsed"] += 1
                if dry_run:
                    _log(
                        f"  DRY {agent_id}: {payload['raw_price_text']} → ${payload['price']:.2f}/M-{payload['unit']}"
                    )
                    continue
                if upsert_replicate_price(conn, agent_id, payload):
                    counts["written"] += 1
                    _log(
                        f"  OK  {agent_id}: ${payload['price']:.2f}/M-{payload['unit']} ({payload['raw_price_text']})"
                    )
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
    parser.add_argument(
        "--dry-run", action="store_true", help="Fetch + parse but don't write to DB."
    )
    args = parser.parse_args()
    counts = run(args.db, args.mirrors, args.dry_run)
    _log(f"summary: {counts}")
    return 0 if counts["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
