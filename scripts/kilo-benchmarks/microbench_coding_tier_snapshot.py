"""Snapshot every agents row's derived quality_tier from derive_quality_v2.

Used by Phase D's non-regression test: capture pre-edit tiers, apply the edit
that adds `humaneval_score` to the tier ladder, then verify no non-Seed row
flipped tier (blast-radius guard for a fleet-wide signal change).

Plan: docs/development/plans/2026-07-10-plan-2-coding-microbench-runner.md
"""
# AFTER-EDIT: none

from __future__ import annotations

import json
import pathlib
import sqlite3
import sys

SCRIPT_DIR = pathlib.Path(__file__).parent
DB_PATH = SCRIPT_DIR / "kilo_agents.db"
sys.path.insert(0, str(SCRIPT_DIR))

from derive_quality_v2 import derive_v2  # noqa: E402


def snapshot_tiers(db_path: pathlib.Path = DB_PATH) -> dict[str, dict]:
    """Return {model_id: {"tier": N, "evidence": [...]}} for every agents row."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute("SELECT * FROM agents").fetchall()
    finally:
        conn.close()
    result: dict[str, dict] = {}
    for row in rows:
        row_dict = dict(row)
        model_id = row_dict.get("id")
        if not model_id:
            continue
        tier, evidence = derive_v2(row_dict, or_record=None)
        result[model_id] = {"tier": tier, "evidence": evidence}
    return result


def main() -> int:
    snap = snapshot_tiers()
    json.dump(snap, sys.stdout, indent=2, sort_keys=True)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
