#!/usr/bin/env python3
"""
Embedding-side orchestrator — sibling to chat's `role_mapper.py`.

End-to-end daily flow:

  1. Load `embedding_role_configs.yaml`.
  2. For each role, call `embedding_selector.select_for_role` to get the
     top-N candidates (one per priority slot).
  3. Persist winners to `embedding_roles` (overwriting yesterday's pins;
     UNIQUE(role, priority) keeps the table at exactly slots-per-role rows).
  4. Append a snapshot row per (role, priority, today) to
     `embedding_roles_history` for audit.
  5. Emit diagnostic JSON files that mirror the chat pipeline's output
     locations:
       - embedding_assignments.json  (today's winners)
       - kilo_embeddings_final.json  (compact role → priority → model mapping
                                      for Traycer / downstream tools)

Idempotent: running twice on the same day overwrites `embedding_roles` and
upserts today's `embedding_roles_history` rows (UNIQUE on snapshot_date).

Usage:
    python scripts/kilo-benchmarks/embedding_role_mapper.py
"""

from __future__ import annotations

import json
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

from embedding_selector import (  # noqa: E402
    NoEligibleEmbeddingError,
    select_for_role,
)


def _utc_today_iso() -> str:
    """Today's UTC date in ISO format — matches SQLite's `DATE('now')`."""
    return datetime.now(UTC).date().isoformat()


DB_PATH = SCRIPT_DIR / "kilo_agents.db"
CONFIG_PATH = SCRIPT_DIR / "embedding_role_configs.yaml"
ASSIGNMENTS_PATH = SCRIPT_DIR / "embedding_assignments.json"
TRAYCER_EXPORT_PATH = SCRIPT_DIR.parent / "kilo_embeddings_final.json"

ASSIGNED_BY = "embedding_role_mapper"


def _persist_assignments(
    conn: sqlite3.Connection, assignments: dict[str, list[dict[str, Any]]]
) -> None:
    """Overwrite embedding_roles + append today's snapshot to history.

    Snapshot date uses SQLite's `DATE('now')` (UTC) for consistency with the
    DB-side queries in tests and downstream reports. Mixing Python's local
    `date.today()` with SQLite's UTC would cause off-by-one rows around
    midnight in timezones east of UTC.
    """
    # Wipe current pins for the roles we're about to write — leaves untouched
    # roles alone (forward-compatible when new roles ship).
    roles_in_scope = list(assignments.keys())
    if roles_in_scope:
        placeholders = ",".join("?" * len(roles_in_scope))
        conn.execute(
            f"DELETE FROM embedding_roles WHERE role IN ({placeholders})",
            roles_in_scope,
        )

    for role, winners in assignments.items():
        for idx, row in enumerate(winners, start=1):
            conn.execute(
                """
                INSERT INTO embedding_roles
                    (role, model_id, priority, reason, score_used, score_type, assigned_by)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    role,
                    row["id"],
                    idx,
                    row.get("reason", ""),
                    row["score_used"],
                    row["score_type"],
                    ASSIGNED_BY,
                ),
            )
            # Upsert today's history snapshot. snapshot_date set by SQLite
            # (UTC) so both writer and reader agree across timezones.
            conn.execute(
                """
                INSERT OR REPLACE INTO embedding_roles_history
                    (role, priority, model_id, snapshot_date,
                     score_used, input_cost_per_m, assigned_by)
                VALUES (?, ?, ?, DATE('now'), ?, ?, ?)
                """,
                (
                    role,
                    idx,
                    row["id"],
                    row["score_used"],
                    row["input_cost_per_m"],
                    ASSIGNED_BY,
                ),
            )
    conn.commit()


def _emit_assignments_json(assignments: dict[str, list[dict[str, Any]]]) -> None:
    # JSON files use UTC date to stay in lockstep with the snapshot_date
    # written into embedding_roles_history.
    payload = {
        "generated_at": _utc_today_iso(),
        "assigned_by": ASSIGNED_BY,
        "roles": {
            role: [
                {
                    "priority": idx + 1,
                    "id": row["id"],
                    "provider": row["provider"],
                    "input_cost_per_m": row["input_cost_per_m"],
                    "context_window_k": row["context_window_k"],
                    "dimensions": row["dimensions"],
                    "quality_tier": row["quality_tier"],
                    "is_multilingual": row["is_multilingual"],
                    "is_code_tuned": row["is_code_tuned"],
                    "score_used": row["score_used"],
                    "score_type": row["score_type"],
                    "reason": row.get("reason", ""),
                }
                for idx, row in enumerate(winners)
            ]
            for role, winners in assignments.items()
        },
    }
    ASSIGNMENTS_PATH.write_text(json.dumps(payload, indent=2, default=str))
    print(f"[embedding_role_mapper] wrote {ASSIGNMENTS_PATH}")


def _emit_traycer_export(assignments: dict[str, list[dict[str, Any]]]) -> None:
    """Compact role → priority → model id mapping for Traycer / downstream."""
    payload = {
        "generated_at": _utc_today_iso(),
        "roles": {
            role: {str(idx + 1): row["id"] for idx, row in enumerate(winners)}
            for role, winners in assignments.items()
        },
    }
    TRAYCER_EXPORT_PATH.write_text(json.dumps(payload, indent=2, default=str))
    print(f"[embedding_role_mapper] wrote {TRAYCER_EXPORT_PATH}")


def run(db_path: Path | str = DB_PATH) -> dict[str, list[dict[str, Any]]]:
    """Run the full pipeline. Returns the assignments dict for tests."""
    cfg = yaml.safe_load(CONFIG_PATH.read_text())
    roles = cfg.get("roles", {})

    assignments: dict[str, list[dict[str, Any]]] = {}
    for role_name, role_cfg in roles.items():
        try:
            winners = select_for_role(role_cfg)
        except NoEligibleEmbeddingError as e:
            print(f"[embedding_role_mapper] {role_name}: NO ELIGIBLE — {e}")
            assignments[role_name] = []
            continue

        # Decorate with the role's notes as the row's reason. Trim YAML
        # multi-line block-scalar whitespace.
        reason = (role_cfg.get("notes") or "").strip()
        for w in winners:
            w["reason"] = reason
        assignments[role_name] = winners
        ids = [w["id"] for w in winners]
        print(f"[embedding_role_mapper] {role_name}: {len(winners)} winners → {ids}")

    conn = sqlite3.connect(db_path)
    try:
        _persist_assignments(conn, assignments)
    finally:
        conn.close()

    _emit_assignments_json(assignments)
    _emit_traycer_export(assignments)
    return assignments


if __name__ == "__main__":
    run()
