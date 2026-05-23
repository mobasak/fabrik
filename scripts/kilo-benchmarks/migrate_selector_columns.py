#!/usr/bin/env python3
"""
Idempotent migration: add quality_tier + is_ga columns to `agents` and
populate them deterministically from existing benchmark / id data.

Reuses the existing `has_vision` column for vision routing — no new
supports_vision column is created.

Re-running is safe: ALTER TABLE statements are guarded by PRAGMA
table_info, and the population step always recomputes from current values.

Run:
    python scripts/kilo-benchmarks/migrate_selector_columns.py

Sibling to: pre_filter.py, role_mapper.py, post_filter.py, classify_ticket.py
Conventions: stdlib sqlite3, sync, no settings/env. Match the kilo-benchmarks
script style — this is a local tool, not a deployed service.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).parent
DB_PATH = SCRIPT_DIR / "kilo_agents.db"

# Quality tier auto-derivation thresholds.
# Pure quality signal — does NOT mix in cost. Cost is the selector's objective;
# tier is a constraint floor.
#   tier 3 (frontier): arena_elo >= 1500 OR tbench >= 80
#   tier 2 (mid)     : arena_elo >= 1430 OR tbench >= 65
#   tier 1 (bulk)    : everything else (or unbenchmarked)
TIER3_ELO = 1500
TIER3_TBENCH = 80.0
TIER2_ELO = 1430
TIER2_TBENCH = 65.0

# Substrings in the model id that mark a non-GA / preview / experimental release.
# Case-insensitive match. Free-tier IDs always count as non-GA because their
# rate limits make them unsuitable for stable production traffic.
NON_GA_MARKERS = (
    ":free",
    "preview",
    "alpha",
    "beta",
    "experimental",
    "-exp-",
    ":thinking",
    "-rc",
)


def _column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    cursor = conn.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cursor.fetchall())


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, ddl: str) -> bool:
    """Add column if missing. Returns True if it was added, False if already present."""
    if _column_exists(conn, table, column):
        return False
    conn.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")
    return True


def derive_quality_tier(arena_elo: int | None, tbench_accuracy: float | None) -> int:
    """Pure function. Same inputs → same output. Used by tests and by the migration."""
    elo = arena_elo or 0
    tb = tbench_accuracy or 0.0
    if elo >= TIER3_ELO or tb >= TIER3_TBENCH:
        return 3
    if elo >= TIER2_ELO or tb >= TIER2_TBENCH:
        return 2
    return 1


def derive_is_ga(model_id: str) -> int:
    """1 if generally available, 0 if preview/free/experimental."""
    lower = model_id.lower()
    return 0 if any(marker in lower for marker in NON_GA_MARKERS) else 1


def migrate(db_path: Path = DB_PATH) -> dict[str, Any]:
    """
    Apply the migration. Returns a counts dict for logging:
        {"added_columns": int, "rows_updated": int, "tier_counts": {1: ..., 2: ..., 3: ...}}
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        added = 0
        if _ensure_column(conn, "agents", "quality_tier", "quality_tier INTEGER"):
            added += 1
        if _ensure_column(conn, "agents", "is_ga", "is_ga INTEGER"):
            added += 1

        cursor = conn.execute("SELECT id, arena_elo, tbench_accuracy FROM agents")
        rows = cursor.fetchall()
        tier_counts = {1: 0, 2: 0, 3: 0}
        for row in rows:
            qt = derive_quality_tier(row["arena_elo"], row["tbench_accuracy"])
            ga = derive_is_ga(row["id"])
            tier_counts[qt] += 1
            conn.execute(
                "UPDATE agents SET quality_tier = ?, is_ga = ? WHERE id = ?",
                (qt, ga, row["id"]),
            )
        conn.commit()

        return {
            "added_columns": added,
            "rows_updated": len(rows),
            "tier_counts": tier_counts,
        }
    finally:
        conn.close()


if __name__ == "__main__":
    result = migrate()
    print(f"[migrate] columns added this run: {result['added_columns']}")
    print(f"[migrate] rows updated: {result['rows_updated']}")
    tc = result["tier_counts"]
    print(f"[migrate] tier distribution: tier1={tc[1]}, tier2={tc[2]}, tier3={tc[3]}")
