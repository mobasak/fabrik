#!/usr/bin/env python3
"""Add the OpenRouter "richer extraction" columns to `agents` (idempotent).

The verifier was only pulling 6 of 18 fields from OR's `/api/v1/models`
response. Operator asked: "are you sure we can extract all models with
all their columns?" — answer was no. This migration adds the high-value
missing columns so the verifier can populate them:

  canonical_slug              TEXT     — OR's authoritative slug, often
                                          longer than the route id and
                                          carries the date stamp (e.g.
                                          `anthropic/claude-sonnet-5-20260630`).
                                          Useful for second-pass dedup
                                          and shows the "real" model
                                          identity in the UI.

  knowledge_cutoff            TEXT     — ISO date of the model's
                                          training-data cutoff. Surfaces
                                          stale-knowledge risk.

  cache_read_cost_per_m       REAL     — USD per million tokens for cached
                                          prompt READS. Production-serving
                                          cost is typically 5-10x lower
                                          with caching vs without.

  cache_write_cost_per_m      REAL     — USD per million tokens for cache
                                          WRITES (storing a prompt to be
                                          cached). Usually similar to or
                                          slightly higher than base input
                                          cost.

  reasoning_mandatory         INTEGER  — 1 if OR flags the model as
                                          MANDATORY reasoning (you can't
                                          turn thinking off — affects
                                          first-token latency expectations).

  reasoning_supported_efforts TEXT     — JSON array of supported reasoning
                                          effort levels (e.g. ["low",
                                          "medium", "high"]). Empty/NULL
                                          if reasoning isn't supported.

  max_completion_tokens       INTEGER  — `top_provider.max_completion_tokens`
                                          — actual output cap.

  is_moderated                INTEGER  — `top_provider.is_moderated` —
                                          content-moderation flag.

Idempotency: re-running the script is a no-op. Same `PRAGMA table_info`
gate as migrate_aggregator_columns.py.

Wire-in: daily_refresh.sh runs this migration before `verify_openrouter
_catalog.py --apply`, so a fresh checkout boots cleanly + the verifier
sees the columns when it tries to write them.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).parent
DB_PATH = SCRIPT_DIR / "kilo_agents.db"

NEW_COLUMNS = (
    ("canonical_slug", "canonical_slug TEXT"),
    ("knowledge_cutoff", "knowledge_cutoff TEXT"),
    ("cache_read_cost_per_m", "cache_read_cost_per_m REAL"),
    ("cache_write_cost_per_m", "cache_write_cost_per_m REAL"),
    ("reasoning_mandatory", "reasoning_mandatory INTEGER DEFAULT 0"),
    ("reasoning_supported_efforts", "reasoning_supported_efforts TEXT"),
    ("max_completion_tokens", "max_completion_tokens INTEGER"),
    ("is_moderated", "is_moderated INTEGER DEFAULT 0"),
)


def _log(msg: str) -> None:
    print(f"[migrate_or_richer_extraction] {msg}")


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
