#!/usr/bin/env python3
"""Add 3 columns to `agents` for the direct-vendor pricing scraper.

Idempotent — uses PRAGMA table_info() to skip columns that already exist.
Matches the existing pattern at kilo_agents_db.py:205. Per
docs/development/plans/2026-06-29-plan-direct-vendor-pricing.md (Phase 1
DB schema additions).

Columns added:
- `last_price_scraped TEXT`             — ISO date the orchestrator last
                                          successfully scraped this row's price
- `consecutive_pricing_misses INT DEFAULT 0`
                                        — bumped when a vendor returns a parsed
                                          set that does NOT include this row's id
                                          even though the vendor responded OK;
                                          at 7 the row flips to status='deprecated'
- `price_scrape_source TEXT`            — vendor URL on success, OR sentinel
                                          `URL_BROKEN_<YYYY-MM-DD>` for vendors
                                          whose URL is unreachable AND no
                                          alternative has been hand-resolved.
                                          Cleared by the orchestrator whenever
                                          a non-NULL `last_price_scraped` is
                                          written for the same row.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
DB_PATH = SCRIPT_DIR / "kilo_agents.db"

# (column_name, column_type_with_default) — keep order stable for the audit log.
NEW_COLUMNS: list[tuple[str, str]] = [
    ("last_price_scraped", "TEXT"),
    ("consecutive_pricing_misses", "INTEGER DEFAULT 0"),
    ("price_scrape_source", "TEXT"),
]


def _existing_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}


def run(db_path: Path = DB_PATH) -> dict[str, list[str]]:
    """Apply pending column additions. Returns {'added': [...], 'skipped': [...]}.

    Atomic: wrapped in a BEGIN/COMMIT so a mid-flight failure leaves the schema
    unchanged. SQLite serializes ALTER TABLE on a single connection so concurrency
    is not a concern here.
    """
    conn = sqlite3.connect(db_path)
    added: list[str] = []
    skipped: list[str] = []
    try:
        conn.execute("BEGIN")
        existing = _existing_columns(conn, "agents")
        for name, type_def in NEW_COLUMNS:
            if name in existing:
                skipped.append(name)
                continue
            conn.execute(f"ALTER TABLE agents ADD COLUMN {name} {type_def}")
            added.append(name)
        conn.commit()
    except Exception:
        try:
            conn.execute("ROLLBACK")
        except sqlite3.OperationalError:
            pass
        raise
    finally:
        conn.close()
    return {"added": added, "skipped": skipped}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DB_PATH)
    args = parser.parse_args()
    if not args.db.exists():
        print(f"ERROR: DB does not exist: {args.db}", file=sys.stderr)
        return 1
    result = run(args.db)
    if result["added"]:
        print(f"[migrate_direct_vendor_pricing] added: {result['added']}")
    if result["skipped"]:
        print(f"[migrate_direct_vendor_pricing] skipped (already present): {result['skipped']}")
    if not result["added"] and not result["skipped"]:
        print("[migrate_direct_vendor_pricing] no changes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
