#!/usr/bin/env python3
"""
Export the current `agent_roles` assignments as a JSON registry consumed by
Traycer's orchestrator.

Output path is intentionally kept at `scripts/kilo_47_agents_final.json` to
avoid touching every consumer (scaffold.py, kilo_model_sync.py, the
pre-commit hook, Traycer's own reference statement). The "47" in the
filename is historical — the file now reflects whatever the selector
produced in the most recent `role_mapper.py` run.

Schema (per role):
    {
      "priority": int,
      "api_id": "provider/model",
      "kilo_id": "kilo/provider/model",     # what Kilo CLI accepts as --model
      "name": "Human-readable name",
      "provider": "qwen|google|...",
      "input_per_1m": float,
      "output_per_1m": float,
      "total_per_1m": float,
      "output_tokens_per_sec": float | null,
      "arena_elo": int | null,
      "tbench_accuracy": float | null,
      "weighted_coding": float | null,
      "has_vision": bool,
      "has_reasoning": bool,
      "context_window_k": int | null
    }

Run after `role_mapper.py` so the JSON reflects the freshly-assigned fleet.
The WSL startup hook chains them: role_mapper → export_traycer_registry →
generate_kilo_agents.

Usage:
    python scripts/kilo-benchmarks/export_traycer_registry.py
    python scripts/kilo-benchmarks/export_traycer_registry.py --output PATH
    python scripts/kilo-benchmarks/export_traycer_registry.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
DB_PATH = SCRIPT_DIR / "kilo_agents.db"
DEFAULT_OUTPUT = SCRIPT_DIR.parent / "kilo_47_agents_final.json"


def log(msg: str) -> None:
    print(f"[traycer-export] {msg}")


def fetch_assignments(conn: sqlite3.Connection) -> list[dict]:
    """Read every current agent_roles row joined with agent capabilities."""
    cur = conn.execute(
        """
        SELECT
            r.role,
            r.priority,
            a.id            AS api_id,
            a.name,
            a.provider,
            a.input_cost_per_m,
            a.output_cost_per_m,
            a.output_tokens_per_sec,
            a.arena_elo,
            a.tbench_accuracy,
            a.weighted_coding,
            a.has_vision,
            a.has_reasoning,
            a.context_window_k
        FROM agent_roles r
        JOIN agents a ON a.id = r.agent_id
        WHERE a.blocked = 0
        ORDER BY r.role, r.priority
        """
    )
    return [dict(row) for row in cur.fetchall()]


def build_registry(rows: list[dict]) -> dict:
    """Group rows by role; emit a stable schema ready for Traycer to consume."""
    roles: dict[str, list[dict]] = {}
    for r in rows:
        cost_in = r["input_cost_per_m"] or 0.0
        cost_out = r["output_cost_per_m"] or 0.0
        entry = {
            "priority": r["priority"],
            "api_id": r["api_id"],
            "kilo_id": f"kilo/{r['api_id']}",
            "name": r["name"],
            "provider": r["provider"],
            "input_per_1m": round(cost_in, 4),
            "output_per_1m": round(cost_out, 4),
            "total_per_1m": round(cost_in + cost_out, 4),
            "output_tokens_per_sec": r["output_tokens_per_sec"],
            "arena_elo": r["arena_elo"],
            "tbench_accuracy": r["tbench_accuracy"],
            "weighted_coding": r["weighted_coding"],
            "has_vision": bool(r["has_vision"]),
            "has_reasoning": bool(r["has_reasoning"]),
            "context_window_k": r["context_window_k"],
        }
        roles.setdefault(r["role"], []).append(entry)

    fleet_sizes = {role: len(entries) for role, entries in roles.items()}

    return {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "source": "kilo_agents.db.agent_roles",
        "assignment_method": "cheapest-above-floors deterministic selector",
        "classifier": "scripts/kilo-benchmarks/classify_ticket.py",
        "selector_config": "scripts/kilo-benchmarks/role_configs.yaml",
        "priority_semantics": (
            "P1 = cheapest qualified agent meeting all floors; "
            "P5 = most expensive qualified (= highest quality among survivors). "
            "Every priority slot satisfies the role's quality + speed floors."
        ),
        "fleet_size_summary": fleet_sizes,
        "total_assignments": len(rows),
        "roles": roles,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Export agent_roles to Traycer JSON registry")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Output JSON path")
    parser.add_argument("--dry-run", action="store_true", help="Print to stdout instead of writing")
    args = parser.parse_args()

    if not DB_PATH.exists():
        log(f"ERROR: DB not found at {DB_PATH}")
        return 1

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = fetch_assignments(conn)
    conn.close()

    if not rows:
        log("ERROR: no rows in agent_roles — run role_mapper.py first")
        return 1

    registry = build_registry(rows)

    if args.dry_run:
        print(json.dumps(registry, indent=2, default=str))
        return 0

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(registry, indent=2, default=str) + "\n")

    log(f"Wrote {len(rows)} assignments across {len(registry['roles'])} roles")
    log(f"  → {out_path}")
    for role, n in sorted(registry["fleet_size_summary"].items()):
        log(f"    {role}: {n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
