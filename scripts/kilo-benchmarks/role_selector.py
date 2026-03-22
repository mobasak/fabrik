#!/usr/bin/env python3
"""
Role-based agent selector.

Returns the best available agent for a given role from the database.
Use this in Kilo CLI wrappers to dynamically select agents.

Usage:
    python role_selector.py --role coding
    python role_selector.py --role reviewing --require-vision
    python role_selector.py --role documentation --max-cost-out 5.0
    python role_selector.py --role testing --json

    # In shell scripts:
    AGENT=$(python role_selector.py --role coding)
    kilo run --model "$AGENT" --message "..."
"""

import argparse
import json
import sqlite3
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
DB_PATH = SCRIPT_DIR / "kilo_agents.db"
ROLES = ["coding", "reviewing", "fixing", "documentation", "testing"]


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def select_agent(
    role: str,
    require_vision: bool = False,
    require_agentic: bool = False,
    max_cost_out: float | None = None,
    fallback_priority: int = 1,
) -> dict | None:
    """Select the best agent for a role with optional filters."""
    conn = get_connection()

    query = """
        SELECT
            a.id,
            a.api_id,
            a.name,
            a.provider,
            a.arena_elo,
            a.tbench_accuracy,
            a.input_cost_per_m,
            a.output_cost_per_m,
            a.context_window_k,
            a.has_vision,
            a.has_tools,
            a.is_agentic,
            a.perf_per_dollar,
            r.priority,
            r.reason
        FROM agent_roles r
        JOIN agents a ON a.id = r.agent_id
        WHERE r.role = ?
          AND a.status = 'active'
          AND r.priority <= ?
    """
    params: list = [role, fallback_priority]

    if require_vision:
        query += " AND a.has_vision = 1"
    if require_agentic:
        query += " AND a.is_agentic = 1"
    if max_cost_out is not None:
        query += " AND a.output_cost_per_m <= ?"
        params.append(max_cost_out)

    query += " ORDER BY r.priority ASC LIMIT 1"

    cursor = conn.execute(query, params)
    row = cursor.fetchone()
    conn.close()

    return dict(row) if row else None


def list_role_agents(role: str) -> list[dict]:
    """List all agents assigned to a role."""
    conn = get_connection()

    cursor = conn.execute(
        """
        SELECT
            a.id,
            a.name,
            a.provider,
            a.arena_elo,
            a.tbench_accuracy,
            a.input_cost_per_m,
            a.output_cost_per_m,
            a.perf_per_dollar,
            r.priority,
            r.reason
        FROM agent_roles r
        JOIN agents a ON a.id = r.agent_id
        WHERE r.role = ?
          AND a.status = 'active'
        ORDER BY r.priority ASC
    """,
        (role,),
    )

    agents = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return agents


def main() -> int:
    parser = argparse.ArgumentParser(description="Select agent for a role")
    parser.add_argument(
        "--role",
        required=True,
        choices=ROLES,
        help="Role to select agent for",
    )
    parser.add_argument(
        "--require-vision",
        action="store_true",
        help="Require vision capability",
    )
    parser.add_argument(
        "--require-agentic",
        action="store_true",
        help="Require agentic/reasoning capability",
    )
    parser.add_argument(
        "--max-cost-out",
        type=float,
        help="Maximum output cost per 1M tokens",
    )
    parser.add_argument(
        "--fallback",
        type=int,
        default=3,
        choices=[1, 2, 3],
        help="Max fallback priority (1=primary only, 2=include fallback, 3=include emergency)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="Output full agent info as JSON",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List all agents for this role",
    )

    args = parser.parse_args()

    if args.list:
        agents = list_role_agents(args.role)
        if not agents:
            print(f"No agents assigned to role: {args.role}", file=sys.stderr)
            return 1
        if args.as_json:
            print(json.dumps(agents, indent=2))
        else:
            print(f"Agents for {args.role}:")
            for a in agents:
                elo = a["arena_elo"] or "n/a"
                print(f"  #{a['priority']} {a['id']} (elo={elo})")
                if a["reason"]:
                    print(f"       → {a['reason']}")
        return 0

    agent = select_agent(
        role=args.role,
        require_vision=args.require_vision,
        require_agentic=args.require_agentic,
        max_cost_out=args.max_cost_out,
        fallback_priority=args.fallback,
    )

    if not agent:
        print(f"No agent found for role: {args.role}", file=sys.stderr)
        return 1

    if args.as_json:
        print(json.dumps(agent, indent=2))
    else:
        # Just output the agent ID for shell scripts
        print(agent["id"])

    return 0


if __name__ == "__main__":
    sys.exit(main())
