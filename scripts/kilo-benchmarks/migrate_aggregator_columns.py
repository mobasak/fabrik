#!/usr/bin/env python3
"""Add aggregator-pricing columns to `agents` (idempotent).

Three columns enable the cross-aggregator price comparison flow described in
docs/development/plans/2026-06-29-plan-2-aggregator-pricing.md (Phase 0):

  gateway_prices         TEXT   — JSON map: {gateway: {price, unit, slug, url, last_seen, confidence}}.
                                  Populated by Phase 1 (Replicate HTML scraper) and Phase 2 (fal.ai API consumer).
  cheapest_gateway       TEXT   — name of the gateway with the lowest price across gateway_prices.
                                  Derived from gateway_prices by Phase 3 derive_cheapest_gateway.py.
  cheapest_gateway_price REAL   — the lowest price on the same input_cost_per_m axis (sortable).

Idempotency contract: re-running the script is a no-op. Same pattern as
migrate_selector_columns.py:55-65.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).parent
DB_PATH = SCRIPT_DIR / "kilo_agents.db"

NEW_COLUMNS = (
    ("gateway_prices", "gateway_prices TEXT"),
    ("cheapest_gateway", "cheapest_gateway TEXT"),
    ("cheapest_gateway_price", "cheapest_gateway_price REAL"),
)


def _log(msg: str) -> None:
    print(f"[migrate_aggregator_columns] {msg}")


def _column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    return any(row[1] == column for row in conn.execute(f"PRAGMA table_info({table})").fetchall())


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, ddl: str) -> bool:
    if _column_exists(conn, table, column):
        return False
    conn.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")
    return True


def migrate(db_path: Path = DB_PATH) -> dict[str, Any]:
    conn = sqlite3.connect(db_path)
    try:
        added = []
        already = []
        for col, ddl in NEW_COLUMNS:
            if _ensure_column(conn, "agents", col, ddl):
                added.append(col)
            else:
                already.append(col)
        conn.commit()
        return {"added": added, "already_present": already}
    finally:
        conn.close()


def main() -> int:
    result = migrate()
    _log(f"added: {result['added']}")
    _log(f"already present: {result['already_present']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
