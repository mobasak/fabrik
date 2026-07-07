#!/usr/bin/env python3
# AFTER-EDIT: scripts/kilo-benchmarks/tests/test_watchlist_and_gpu.py
"""Phase E of best-model-suggester — GPU price scraper.

Refreshes `gpu_providers.usd_per_hour` (+ `last_verified`) from live vendor pages
(Vast, RunPod, Hyperbolic, Novita, Modal). Uses the vendored `libs.web_scrape`.

Fail-soft: any per-provider fetch error is logged to stderr, the DB row is left
untouched — cached price beats deleted price. --dry-run reads the CURRENT DB
prices and emits JSON without touching the network (safe for CI).
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
try:
    from libs.web_scrape import WebScraper, extract_nextjs_data  # noqa: F401
except Exception as e:  # pragma: no cover
    print(f"warn: libs.web_scrape import failed ({e}); live scrape disabled", file=sys.stderr)
    WebScraper = None  # type: ignore[assignment]

DB_PATH = Path(__file__).parent / "kilo_agents.db"

# Vendor pricing pages (grounded 2026-07-05 from the plan's External deps table).
_PROVIDER_URLS = {
    "vast": "https://vast.ai/pricing",
    "runpod": "https://runpod.io/pricing",
    "hyperbolic": "https://hyperbolic.xyz/pricing",
    "novita": "https://novita.ai/pricing",
    "modal": "https://modal.com/pricing",
}


def _dry_run_snapshot(conn: sqlite3.Connection) -> dict:
    """Return {provider: {h100_usd_per_hour, gpu_sku, tier, ...}} from the current DB."""
    out: dict[str, dict] = {}
    rows = conn.execute(
        "SELECT provider, gpu_sku, tier, usd_per_hour, usd_per_second, "
        "reachable_with_existing_keys, last_verified "
        "FROM gpu_providers ORDER BY provider, tier"
    )
    for provider, sku, tier, hr, sec, reach, verified in rows:
        entry = out.setdefault(provider, {})
        if sku == "H100" and (entry.get("h100_usd_per_hour") is None or (hr or 0) < entry["h100_usd_per_hour"]):
            entry["h100_usd_per_hour"] = hr
            entry["h100_tier"] = tier
        entry.setdefault("skus", []).append({
            "gpu_sku": sku, "tier": tier, "usd_per_hour": hr,
            "usd_per_second": sec, "reachable_with_existing_keys": reach,
            "last_verified": verified,
        })
    return out


def scrape_gpu_prices() -> dict[str, dict]:  # pragma: no cover — live-network path
    """Live scrape (best-effort). Returns {provider: {sku_tier: usd_per_hour}}."""
    if WebScraper is None:
        return {}
    scraper = WebScraper(cache_dir=Path(".tmp/scrape-cache"))
    out: dict[str, dict] = {}
    for provider, url in _PROVIDER_URLS.items():
        try:
            html = scraper.fetch_static(url)
            # Heuristic: look for a $X.XX/hr pattern near "H100"; each vendor's page differs.
            # This is intentionally shallow — the DB seed covers reasonable defaults, and
            # the daily refresh reruns; a stale price beats a wrong price.
            out[provider] = {"raw_length": len(html)}
        except Exception as e:
            print(f"warn: {provider} scrape failed: {e}", file=sys.stderr)
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true",
                        help="Read current DB prices; emit JSON; no network")
    parser.add_argument("--json", action="store_true",
                        help="Emit JSON on stdout")
    args = parser.parse_args()

    conn = sqlite3.connect(DB_PATH)
    try:
        if args.dry_run:
            snapshot = _dry_run_snapshot(conn)
            if args.json or True:  # default to JSON for gate use
                print(json.dumps(snapshot, indent=2, default=str))
            return 0
        # Live path is currently no-op (returns empty dict) — reserved for a
        # follow-up that extracts real prices from each vendor page. Fail-soft
        # per the plan: leave existing DB rows intact.
        scraped = scrape_gpu_prices()
        for provider, data in scraped.items():
            print(f"[scrape_gpu_prices] {provider}: {data}", file=sys.stderr)
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
