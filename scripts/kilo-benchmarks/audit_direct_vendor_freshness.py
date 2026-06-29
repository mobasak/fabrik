#!/usr/bin/env python3
"""Quarterly-audit helper: which direct-vendor rows have fresh scraper coverage?

Reads `agents` and reports per-row freshness:
  - SCRAPED  — last_price_scraped is recent (within --max-age-days)
  - STALE    — last_price_scraped is older than --max-age-days
  - SEED-ONLY — last_price_scraped IS NULL (orchestrator has no parser for
                this vendor yet; the row's price is whatever
                seed_direct_vendors.py last wrote — may be months old)
  - URL_BROKEN — price_scrape_source carries the URL_BROKEN_<date> sentinel
                 from check_daily_refresh_freshness.py's SET rule

Use case: the operator wants to know "which of my 74 direct-vendor rows
have I scraped automatically vs which need a manual quarterly price check
against the vendor's pricing page?"

Per docs/development/plans/2026-06-29-plan-direct-vendor-pricing.md
(Phase 5 ops doc deferred deliverable — manual audit cadence support).

Usage
-----
  python audit_direct_vendor_freshness.py                       # summary + per-row
  python audit_direct_vendor_freshness.py --max-age-days 7      # tighter freshness
  python audit_direct_vendor_freshness.py --status seed-only    # only stale-seed rows
  python audit_direct_vendor_freshness.py --csv out.csv         # machine-readable
"""

from __future__ import annotations

import argparse
import csv
import sqlite3
import sys
from datetime import UTC, date, datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
DB_PATH = SCRIPT_DIR / "kilo_agents.db"
MAX_AGE_DAYS_DEFAULT = 3  # daily refresh + 2 days slack


def _today() -> date:
    return datetime.now(UTC).date()


def _parse_iso_date(s: str | None) -> date | None:
    if not s:
        return None
    try:
        return date.fromisoformat(s.strip())
    except (ValueError, AttributeError):
        return None


def classify(
    last_price_scraped: str | None,
    price_scrape_source: str | None,
    today: date | None = None,
    max_age_days: int = MAX_AGE_DAYS_DEFAULT,
) -> tuple[str, int | None]:
    """Return (status, age_days) for a row.

    status ∈ {'scraped', 'stale', 'seed-only', 'url-broken'}
    age_days is None for seed-only / url-broken or invalid timestamp.
    """
    today = today or _today()
    if (price_scrape_source or "").startswith("URL_BROKEN_"):
        return "url-broken", None
    last = _parse_iso_date(last_price_scraped)
    if last is None:
        return "seed-only", None
    age = (today - last).days
    if age <= max_age_days:
        return "scraped", age
    return "stale", age


def run(
    db_path: Path = DB_PATH,
    max_age_days: int = MAX_AGE_DAYS_DEFAULT,
    filter_status: str | None = None,
) -> list[dict]:
    """Return rows annotated with status + age_days, sorted: stale → seed-only → url-broken → scraped."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        # Direct-vendor rows only: NOT routed through OpenRouter / Kilo.
        rows = conn.execute(
            "SELECT id, provider, service_type, input_cost_per_m, pricing_unit, "
            "status, last_price_scraped, price_scrape_source, "
            "COALESCE(consecutive_pricing_misses, 0) as misses "
            "FROM agents "
            "WHERE via_openrouter=0 AND via_kilo=0 AND status='active' "
            "ORDER BY provider, id"
        ).fetchall()
    finally:
        conn.close()

    today = _today()
    annotated: list[dict] = []
    for r in rows:
        status, age = classify(
            r["last_price_scraped"],
            r["price_scrape_source"],
            today=today,
            max_age_days=max_age_days,
        )
        if filter_status and status != filter_status:
            continue
        annotated.append(
            {
                "id": r["id"],
                "provider": r["provider"],
                "service_type": r["service_type"],
                "input_cost_per_m": r["input_cost_per_m"],
                "pricing_unit": r["pricing_unit"],
                "last_price_scraped": r["last_price_scraped"],
                "price_scrape_source": r["price_scrape_source"],
                "consecutive_pricing_misses": r["misses"],
                "freshness_status": status,
                "age_days": age,
            }
        )

    # Sort: stale > url-broken > seed-only > scraped (most-attention-needed first)
    order = {"stale": 0, "url-broken": 1, "seed-only": 2, "scraped": 3}
    annotated.sort(key=lambda x: (order.get(x["freshness_status"], 9), x["id"]))
    return annotated


def emit_summary(annotated: list[dict]) -> None:
    counts: dict[str, int] = {}
    for row in annotated:
        counts[row["freshness_status"]] = counts.get(row["freshness_status"], 0) + 1
    print("=== Direct-vendor row freshness summary ===")
    total = len(annotated)
    for s in ("stale", "url-broken", "seed-only", "scraped"):
        n = counts.get(s, 0)
        pct = (n / total * 100) if total else 0
        print(f"  {s:12s} {n:4d} ({pct:5.1f}%)")
    print(f"  {'total':12s} {total:4d}")


def emit_table(annotated: list[dict]) -> None:
    print()
    print(f"{'status':12s} {'age':5s} {'id':40s} {'unit':12s} {'price':>11s} {'last_scraped':12s}")
    print("-" * 100)
    for r in annotated:
        age = f"{r['age_days']}d" if r["age_days"] is not None else "—"
        price = f"{r['input_cost_per_m']:.2f}" if r["input_cost_per_m"] is not None else "—"
        last = r["last_price_scraped"] or "—"
        print(
            f"{r['freshness_status']:12s} {age:5s} {r['id']:40s} "
            f"{r['pricing_unit'] or '—':12s} {price:>11s} {last:12s}"
        )


def emit_csv(annotated: list[dict], path: Path) -> None:
    if not annotated:
        path.write_text("id,provider,service_type,freshness_status,age_days\n")
        return
    fields = list(annotated[0].keys())
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(annotated)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DB_PATH)
    parser.add_argument("--max-age-days", type=int, default=MAX_AGE_DAYS_DEFAULT)
    parser.add_argument(
        "--status",
        choices=["scraped", "stale", "seed-only", "url-broken"],
        default=None,
        help="Filter to one freshness status.",
    )
    parser.add_argument("--csv", type=Path, default=None, help="Write machine-readable CSV.")
    parser.add_argument("--quiet", action="store_true", help="Skip the human table.")
    args = parser.parse_args()
    if not args.db.exists():
        print(f"ERROR: DB does not exist: {args.db}", file=sys.stderr)
        return 1
    annotated = run(args.db, args.max_age_days, args.status)
    if args.csv:
        emit_csv(annotated, args.csv)
        print(f"[audit] wrote {len(annotated)} rows to {args.csv}")
    if not args.quiet:
        emit_summary(annotated)
        emit_table(annotated)
    return 0


if __name__ == "__main__":
    sys.exit(main())
