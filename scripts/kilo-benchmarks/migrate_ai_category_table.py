#!/usr/bin/env python3
"""Idempotent migration: create `agent_categories` join table.

Phase 1 of the OpenRouter routing plan
(`docs/development/plans/2026-06-27-plan-openrouter-routing.md` §7.1).

Adds ONE new table + ONE new index to `kilo_agents.db`. No alterations
to existing tables. Re-running is a no-op (`CREATE TABLE IF NOT EXISTS`,
`CREATE INDEX IF NOT EXISTS`).

The table is a join: one row per (agent_id, category) pair. A model
that matches multiple categories (e.g. a coding model that's also a
general-purpose LLM) gets multiple rows — this is intentional per the
plan's multi-category-by-design contract.

`ON DELETE CASCADE` cleans up automatically if a model row is removed
from `agents` (OpenRouter occasionally discontinues model ids). The
CASCADE only fires when `PRAGMA foreign_keys = ON` is set on the
connection — the migration sets it AND verifies it AND emits the same
PRAGMA into the per-script test harness in §7.4 G1.6.

Run:
    python scripts/kilo-benchmarks/migrate_ai_category_table.py

Sibling to: migrate_selector_columns.py, classify_ai_category.py.
Conventions: stdlib sqlite3, sync, no settings/env. Match the
kilo-benchmarks script style.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
DB_PATH = SCRIPT_DIR / "kilo_agents.db"


def _log(msg: str) -> None:
    print(f"[migrate_ai_category] {msg}")


def migrate(db_path: Path | str = DB_PATH) -> dict[str, int]:
    """Apply the migration. Returns {table_created, index_created,
    foreign_keys_enabled}. Each value is 0 (already present) or 1 (created
    on this run)."""
    conn = sqlite3.connect(db_path)
    try:
        # Enable foreign keys for THIS connection so the CASCADE constraint
        # the table declares is actually enforced.
        conn.execute("PRAGMA foreign_keys = ON")
        fk_enabled = conn.execute("PRAGMA foreign_keys").fetchone()[0]
        if fk_enabled != 1:
            raise RuntimeError(
                "PRAGMA foreign_keys could not be enabled — SQLite build is "
                "missing FK support; ON DELETE CASCADE will silently no-op."
            )

        # Pre-state check (so the return-values are honest).
        table_exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='agent_categories'"
        ).fetchone()
        index_exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='index' "
            "AND name='idx_agent_categories_category'"
        ).fetchone()

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS agent_categories (
                agent_id       TEXT NOT NULL,
                category       TEXT NOT NULL,
                classified_at  TIMESTAMP DEFAULT (datetime('now')),
                PRIMARY KEY (agent_id, category),
                FOREIGN KEY (agent_id) REFERENCES agents(id) ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_agent_categories_category "
            "ON agent_categories(category)"
        )
        conn.commit()

        # Pass B Finding 5 defense: detect partial-create where CREATE TABLE
        # succeeded but CREATE INDEX silently failed (disk pressure, weird
        # SQLite build). Both `CREATE ... IF NOT EXISTS` are autocommit so
        # an error would raise above — but verifying post-commit state is
        # cheap insurance against a future refactor that bundles them in
        # an explicit transaction.
        table_after = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='agent_categories'"
        ).fetchone()
        index_after = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='index' "
            "AND name='idx_agent_categories_category'"
        ).fetchone()
        if not table_after or not index_after:
            raise RuntimeError(
                "Migration partial-success — "
                f"table_present={bool(table_after)} index_present={bool(index_after)}"
            )
    finally:
        conn.close()

    result = {
        "table_created": 0 if table_exists else 1,
        "index_created": 0 if index_exists else 1,
        "foreign_keys_enabled": 1,
    }
    _log(
        f"table_created={result['table_created']} "
        f"index_created={result['index_created']} "
        f"foreign_keys_enabled={result['foreign_keys_enabled']}"
    )
    return result


if __name__ == "__main__":
    if not DB_PATH.exists():
        _log(f"ERROR: {DB_PATH} does not exist. Run kilo_agents_db.py init first.")
        sys.exit(1)
    migrate()
