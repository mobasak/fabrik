#!/usr/bin/env python3
"""Category-route orchestrator — sibling to `embedding_role_mapper.py`.

Phase 3 of the OpenRouter routing plan
(`docs/development/plans/2026-06-27-plan-openrouter-routing.md` §9.2).

End-to-end daily flow:

  1. Load `ai_category_configs.yaml`.
  2. For each category, call `category_selector.select_for_category()`
     to get the top-N candidates per `slots`.
  3. Catch `NoEligibleCategoryError` per category (don't crash the
     whole run) — emit a graceful empty-routes entry per plan §9.2.
  4. Persist winners to `agent_roles` with `role = 'openrouter:{cat}'`
     and `assigned_by = 'category_route_mapper'`. Upsert today's
     snapshot in `agent_roles_history`.
  5. Emit two JSON files that mirror the embedding pipeline output:
       - `scripts/kilo-benchmarks/openrouter_routes.json` (full detail)
       - `scripts/kilo_openrouter_routes_final.json` (compact for
         Traycer / downstream consumers)

Idempotent: running twice on the same day overwrites `agent_roles`
for the openrouter:* keys and upserts today's history rows (UNIQUE on
snapshot_date). Determinism: same DB + same YAML → byte-identical JSON
output.

Pass B Finding 3 contract: PRAGMA foreign_keys = ON set on the DB
connection before any agent_roles writes.

Plan §9.2 zero-eligible contract: every category appears in the output
JSON with either `routes: [...]` or `routes: [], reason: "..."`.
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

from category_selector import (  # noqa: E402
    NoEligibleCategoryError,
    select_for_category,
)

DB_PATH = SCRIPT_DIR / "kilo_agents.db"
CONFIG_PATH = SCRIPT_DIR / "ai_category_configs.yaml"
ROUTES_JSON_PATH = SCRIPT_DIR / "openrouter_routes.json"
TRAYCER_EXPORT_PATH = SCRIPT_DIR.parent / "kilo_openrouter_routes_final.json"

ASSIGNED_BY = "category_route_mapper"
ROLE_PREFIX = "openrouter:"


def _log(msg: str) -> None:
    print(f"[category_route_mapper] {msg}")


def _utc_today_iso() -> str:
    """Today's UTC date in ISO format — matches SQLite's `DATE('now')`."""
    return datetime.now(UTC).date().isoformat()


def _persist_to_agent_roles(
    conn: sqlite3.Connection,
    routes: dict[str, list[dict[str, Any]]],
) -> None:
    """Overwrite openrouter:* rows in agent_roles + upsert today's history.

    Only touches roles that start with ROLE_PREFIX — chat-side rows
    (`assigned_by='cheapest-above-floors'`) are untouched (Pass 1D D5
    rollback safety). Verified by §16's pre-check that the DELETE
    cannot widen its scope.
    """
    # Wipe previous openrouter:* pins. Bare LIKE is safe because
    # ROLE_PREFIX is a hardcoded literal, not user input.
    conn.execute(
        "DELETE FROM agent_roles WHERE role LIKE ?",
        (f"{ROLE_PREFIX}%",),
    )

    for category, winners in routes.items():
        role = f"{ROLE_PREFIX}{category}"
        for priority, row in enumerate(winners, start=1):
            conn.execute(
                "INSERT INTO agent_roles "
                "(role, agent_id, priority, reason, score_used, score_type, assigned_by) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    role,
                    row["id"],
                    priority,
                    row.get("reason", ""),
                    row["score_used"],
                    row["score_type"],
                    ASSIGNED_BY,
                ),
            )
            # Today's history snapshot. snapshot_date set by SQLite (UTC)
            # so writer + reader agree across timezones.
            conn.execute(
                "INSERT OR REPLACE INTO agent_roles_history "
                "(role, agent_id, priority, reason, min_elo, "
                " score_used, score_type, assigned_by, assigned_at) "
                "VALUES (?, ?, ?, ?, NULL, ?, ?, ?, DATE('now'))",
                (
                    role,
                    row["id"],
                    priority,
                    row.get("reason", ""),
                    row["score_used"],
                    row["score_type"],
                    ASSIGNED_BY,
                ),
            )
    conn.commit()


def _emit_routes_json(
    routes: dict[str, list[dict[str, Any]]],
    skipped: dict[str, str],
) -> None:
    """Write the full-detail openrouter_routes.json."""
    today = _utc_today_iso()
    payload = {
        "generated_at": today,
        "assigned_by": ASSIGNED_BY,
        "categories": {},
    }
    # Every config'd category appears in the output — either with routes
    # or with an explicit zero-eligible explanation. Per plan §9.2.
    for category, winners in routes.items():
        payload["categories"][category] = {
            "routes": [
                {
                    "priority": idx + 1,
                    "id": row["id"],
                    "provider": row["provider"],
                    "input_cost_per_m": row["input_cost_per_m"],
                    "output_cost_per_m": row["output_cost_per_m"],
                    "context_window_k": row["context_window_k"],
                    "has_vision": bool(row.get("has_vision")),
                    "has_tools": bool(row.get("has_tools")),
                    "has_reasoning": bool(row.get("has_reasoning")),
                    "is_ga": bool(row.get("is_ga")),
                    "score_used": row["score_used"],
                    "score_type": row["score_type"],
                    "reason": row.get("reason", ""),
                }
                for idx, row in enumerate(winners)
            ],
            "reason": "",
        }
    for category, reason in skipped.items():
        payload["categories"][category] = {"routes": [], "reason": reason}
    ROUTES_JSON_PATH.write_text(json.dumps(payload, indent=2, default=str))
    _log(f"wrote {ROUTES_JSON_PATH}")


def _emit_traycer_export(
    routes: dict[str, list[dict[str, Any]]],
    skipped: dict[str, str],
) -> None:
    """Compact category → priority → model id mapping for downstream."""
    payload: dict[str, Any] = {
        "generated_at": _utc_today_iso(),
        "categories": {},
    }
    for category, winners in routes.items():
        payload["categories"][category] = {
            str(idx + 1): row["id"] for idx, row in enumerate(winners)
        }
    for category in skipped:
        payload["categories"][category] = {}
    TRAYCER_EXPORT_PATH.write_text(json.dumps(payload, indent=2, default=str))
    _log(f"wrote {TRAYCER_EXPORT_PATH}")


def run(
    db_path: Path | str = DB_PATH,
    config_path: Path | str = CONFIG_PATH,
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, str]]:
    """Run the full route mapping pipeline. Returns (routes, skipped)."""
    cfg = yaml.safe_load(Path(config_path).read_text())
    categories = cfg.get("categories", {})

    routes: dict[str, list[dict[str, Any]]] = {}
    skipped: dict[str, str] = {}

    for category, cat_cfg in categories.items():
        try:
            winners = select_for_category(category, cat_cfg, db_path=db_path)
        except NoEligibleCategoryError as e:
            _log(f"{category}: NO ELIGIBLE — {e}")
            skipped[category] = str(e)
            continue
        except ValueError as e:
            _log(f"{category}: CONFIG ERROR — {e}")
            skipped[category] = f"config error: {e}"
            continue

        reason = (cat_cfg.get("notes") or "").strip()
        for w in winners:
            w["reason"] = reason
        routes[category] = winners
        ids = [w["id"] for w in winners]
        _log(f"{category}: {len(winners)} routes → {ids}")

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    if conn.execute("PRAGMA foreign_keys").fetchone()[0] != 1:
        conn.close()
        raise RuntimeError("PRAGMA foreign_keys could not be enabled.")
    try:
        _persist_to_agent_roles(conn, routes)
    finally:
        conn.close()

    _emit_routes_json(routes, skipped)
    _emit_traycer_export(routes, skipped)

    total_routes = sum(len(v) for v in routes.values())
    _log(
        f"wrote {total_routes} pins across {len(routes)} categories "
        f"({len(skipped)} skipped)"
    )
    return routes, skipped


if __name__ == "__main__":
    if not DB_PATH.exists():
        _log(f"ERROR: {DB_PATH} does not exist. Run kilo_agents_db.py init first.")
        sys.exit(1)
    run()
