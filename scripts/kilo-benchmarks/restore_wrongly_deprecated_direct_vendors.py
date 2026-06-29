#!/usr/bin/env python3
"""Restore direct-vendor rows wrongly deprecated by verify_openrouter_catalog.py.

Background
----------
[verify_openrouter_catalog.py:192](verify_openrouter_catalog.py) executed a
`SELECT * FROM agents WHERE status='active'` with NO `via_openrouter=1` filter.
Direct-vendor rows (Soniox, ElevenLabs, AssemblyAI, Coqui, etc.) — which are
NOT in OpenRouter's /api/v1/models response — got swept into `delisted[]` at
lines 201-203 and flipped to status='deprecated' by `apply_fixes()` at lines
486-492. Convergence Pass 6 caught the bug; Pass 7 measured 186 wrongly-
deprecated rows. Per Plan
docs/development/plans/2026-06-29-plan-direct-vendor-pricing.md (Phase 1
first sub-task).

The verifier itself has been patched (line 192 now filters on via_openrouter=1).
This script handles the historical cleanup: restore the 186 rows.

Selection criteria (intentionally narrow so we don't restore actually-EOL'd rows):
  - via_openrouter = 0
  - via_kilo = 0
  - status = 'deprecated'
  - discard_reason = 'delisted by OpenRouter (verifier)' (EXACT match)

Idempotent: re-running after a successful restore is a no-op (the
`discard_reason` is cleared on restore, so the WHERE no longer matches).

Usage
-----
  python restore_wrongly_deprecated_direct_vendors.py            # dry-run + counts
  python restore_wrongly_deprecated_direct_vendors.py --apply    # write to DB
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
DB_PATH = SCRIPT_DIR / "kilo_agents.db"

WHERE_CLAUSE = (
    "via_openrouter = 0 "
    "AND via_kilo = 0 "
    "AND status = 'deprecated' "
    "AND discard_reason = 'delisted by OpenRouter (verifier)'"
)


def run(db_path: Path = DB_PATH, apply: bool = False) -> dict[str, int]:
    conn = sqlite3.connect(db_path)
    try:
        match_count = conn.execute(f"SELECT COUNT(*) FROM agents WHERE {WHERE_CLAUSE}").fetchone()[
            0
        ]
        if match_count == 0:
            print("[restore] 0 rows match the wrongly-deprecated criteria — nothing to do.")
            return {"matched": 0, "restored": 0}

        print(f"[restore] {match_count} rows match the wrongly-deprecated criteria.")
        sample = conn.execute(
            f"SELECT id, provider, service_type FROM agents WHERE {WHERE_CLAUSE} "
            "ORDER BY provider, id LIMIT 10"
        ).fetchall()
        print("[restore] first 10 rows to restore:")
        for row_id, provider, service_type in sample:
            print(f"  - {row_id:50s} provider={provider:15s} type={service_type}")

        if not apply:
            print(
                "[restore] DRY-RUN — pass --apply to actually UPDATE the DB. "
                f"Would restore {match_count} rows."
            )
            return {"matched": match_count, "restored": 0}

        conn.execute("BEGIN")
        try:
            cursor = conn.execute(
                f"UPDATE agents SET status='active', discard_reason=NULL WHERE {WHERE_CLAUSE}"
            )
            updated = cursor.rowcount
            conn.commit()
        except Exception:
            conn.rollback()
            raise

        print(f"[restore] APPLIED — {updated} rows restored to status='active'.")
        return {"matched": match_count, "restored": updated}
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DB_PATH)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write the UPDATE to the DB. Default is dry-run.",
    )
    args = parser.parse_args()
    if not args.db.exists():
        print(f"ERROR: DB does not exist: {args.db}", file=sys.stderr)
        return 1
    counts = run(args.db, apply=args.apply)
    if args.apply and counts["matched"] != counts["restored"]:
        print(
            f"WARNING: matched={counts['matched']} != restored={counts['restored']} "
            "(some rows failed to update)",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
