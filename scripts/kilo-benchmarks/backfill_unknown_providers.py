#!/usr/bin/env python3
"""Phase 4 of the direct-vendor pricing plan.

Backfill `provider` for `agents` rows where it's currently 'unknown'.

Pattern recognition:
  - claude-*           -> anthropic
  - corethink:*        -> corethink
  - Anything else with `/` separator -> first segment of the ID

Idempotent: re-running after a successful backfill is a no-op.

Per docs/development/plans/2026-06-29-plan-direct-vendor-pricing.md (Phase 4).
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
DB_PATH = SCRIPT_DIR / "kilo_agents.db"


def infer_provider(model_id: str) -> str | None:
    """Return the inferred provider for a model id, or None if unrecognized."""
    if not model_id:
        return None
    # Claude models from Anthropic — `claude-opus-4-7`, `claude-fable-5`, etc.
    if model_id.startswith("claude-"):
        return "anthropic"
    # Standard `<provider>/<model>` form
    if "/" in model_id:
        provider = model_id.split("/", 1)[0]
        if provider:
            return provider
    # `<provider>:tier` form, e.g. `corethink:free`
    if ":" in model_id:
        provider = model_id.split(":", 1)[0]
        if provider:
            return provider
    return None


def run(db_path: Path = DB_PATH, apply: bool = False) -> dict[str, int]:
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute("SELECT id FROM agents WHERE provider='unknown'").fetchall()
        plan: dict[str, str] = {}
        unmappable: list[str] = []
        for (model_id,) in rows:
            inferred = infer_provider(model_id)
            if inferred:
                plan[model_id] = inferred
            else:
                unmappable.append(model_id)

        if not plan and not unmappable:
            print("[backfill] no provider='unknown' rows found — nothing to do.")
            return {"matched": 0, "updated": 0, "unmappable": 0}

        print(f"[backfill] {len(plan)} rows can be inferred; {len(unmappable)} are unmappable.")
        for mid, prov in list(plan.items())[:10]:
            print(f"  {mid:40s} -> {prov}")
        if len(plan) > 10:
            print(f"  ... and {len(plan) - 10} more")
        for mid in unmappable[:5]:
            print(f"  UNMAPPED  {mid}")

        if not apply:
            print("[backfill] DRY-RUN — pass --apply to write.")
            return {"matched": len(plan), "updated": 0, "unmappable": len(unmappable)}

        conn.execute("BEGIN")
        try:
            updated = 0
            for model_id, provider in plan.items():
                cur = conn.execute(
                    "UPDATE agents SET provider=? WHERE id=? AND provider='unknown'",
                    (provider, model_id),
                )
                updated += cur.rowcount
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        print(f"[backfill] APPLIED — {updated} rows updated.")
        return {"matched": len(plan), "updated": updated, "unmappable": len(unmappable)}
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DB_PATH)
    parser.add_argument(
        "--apply", action="store_true", help="Write the UPDATE to the DB. Default is dry-run."
    )
    args = parser.parse_args()
    if not args.db.exists():
        print(f"ERROR: DB does not exist: {args.db}", file=sys.stderr)
        return 1
    run(args.db, apply=args.apply)
    return 0


if __name__ == "__main__":
    sys.exit(main())
