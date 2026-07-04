#!/usr/bin/env python3
# AFTER-EDIT: none
"""Idempotent one-off schema addition: agents.perf_seconds REAL.

Plan 2026-07-03-plan-1-full-speed-coverage-close.md Phase B.1.

Runs safely N times. Also called from microbench_specialty.py's main()
so a fresh clone works without a manual migration step. sqlite has no
`IF NOT EXISTS` for columns, so we check PRAGMA table_info first.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "kilo_agents.db"


def ensure_perf_seconds_column(db_path: Path = DB_PATH) -> bool:
    """Return True if column was added, False if it already existed."""
    with sqlite3.connect(db_path) as conn:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(agents)")}
        if "perf_seconds" in cols:
            return False
        conn.execute("ALTER TABLE agents ADD COLUMN perf_seconds REAL")
    return True


if __name__ == "__main__":
    added = ensure_perf_seconds_column()
    print(f"perf_seconds column: {'added' if added else 'already present'}")
