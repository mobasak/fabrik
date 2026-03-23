#!/usr/bin/env python3
"""
Manage blocked agents in the Kilo agents database.

Blocked agents are excluded from role assignments and selection.
The `agents.blocked` and `agents.block_reason` columns are the source of truth.

Usage:
    python manage_blocked.py list                    # List all blocked agents
    python manage_blocked.py block <agent_id> "reason"   # Block an agent
    python manage_blocked.py unblock <agent_id>      # Unblock an agent
    python manage_blocked.py check <agent_id>        # Check if agent is blocked
"""

import argparse
import sqlite3
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
DB_PATH = SCRIPT_DIR / "kilo_agents.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def list_blocked() -> None:
    """List all blocked agents."""
    conn = get_connection()
    cursor = conn.execute("""
        SELECT id, name, block_reason, updated_at
        FROM agents
        WHERE blocked = 1
        ORDER BY updated_at DESC
    """)
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        print("No blocked agents.")
        return

    print(f"\n{'ID':<40} {'Name':<35} {'Reason'}")
    print("-" * 120)
    for row in rows:
        print(f"{row['id']:<40} {row['name']:<35} {row['block_reason'] or 'No reason'}")
    print(f"\nTotal: {len(rows)} blocked agents")


def block_agent(agent_id: str, reason: str) -> bool:
    """Block an agent with a reason."""
    conn = get_connection()

    # Check if agent exists
    cursor = conn.execute("SELECT id, name, blocked FROM agents WHERE id = ?", (agent_id,))
    row = cursor.fetchone()

    if not row:
        print(f"ERROR: Agent not found: {agent_id}")
        conn.close()
        return False

    if row["blocked"]:
        print(f"Agent already blocked: {row['name']}")
        conn.close()
        return True

    conn.execute(
        "UPDATE agents SET blocked = 1, block_reason = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (reason, agent_id),
    )
    conn.commit()
    conn.close()

    print(f"Blocked: {row['name']} ({agent_id})")
    print(f"Reason: {reason}")
    return True


def unblock_agent(agent_id: str) -> bool:
    """Unblock an agent."""
    conn = get_connection()

    # Check if agent exists
    cursor = conn.execute("SELECT id, name, blocked FROM agents WHERE id = ?", (agent_id,))
    row = cursor.fetchone()

    if not row:
        print(f"ERROR: Agent not found: {agent_id}")
        conn.close()
        return False

    if not row["blocked"]:
        print(f"Agent not blocked: {row['name']}")
        conn.close()
        return True

    conn.execute(
        "UPDATE agents SET blocked = 0, block_reason = NULL, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (agent_id,),
    )
    conn.commit()
    conn.close()

    print(f"Unblocked: {row['name']} ({agent_id})")
    return True


def check_agent(agent_id: str) -> None:
    """Check if an agent is blocked."""
    conn = get_connection()
    cursor = conn.execute(
        "SELECT id, name, blocked, block_reason, status FROM agents WHERE id = ?",
        (agent_id,),
    )
    row = cursor.fetchone()
    conn.close()

    if not row:
        print(f"Agent not found: {agent_id}")
        return

    print(f"Agent: {row['name']} ({agent_id})")
    print(f"Status: {row['status']}")
    if row["blocked"]:
        print("Blocked: YES")
        print(f"Reason: {row['block_reason']}")
    else:
        print("Blocked: NO")


def main() -> int:
    parser = argparse.ArgumentParser(description="Manage blocked agents")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # list
    subparsers.add_parser("list", help="List all blocked agents")

    # block
    block_parser = subparsers.add_parser("block", help="Block an agent")
    block_parser.add_argument("agent_id", help="Agent ID to block")
    block_parser.add_argument("reason", help="Reason for blocking")

    # unblock
    unblock_parser = subparsers.add_parser("unblock", help="Unblock an agent")
    unblock_parser.add_argument("agent_id", help="Agent ID to unblock")

    # check
    check_parser = subparsers.add_parser("check", help="Check if agent is blocked")
    check_parser.add_argument("agent_id", help="Agent ID to check")

    args = parser.parse_args()

    if args.command == "list":
        list_blocked()
    elif args.command == "block":
        if not block_agent(args.agent_id, args.reason):
            return 1
    elif args.command == "unblock":
        if not unblock_agent(args.agent_id):
            return 1
    elif args.command == "check":
        check_agent(args.agent_id)

    return 0


if __name__ == "__main__":
    sys.exit(main())
