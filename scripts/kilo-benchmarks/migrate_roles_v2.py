#!/usr/bin/env python3
"""
Migration: Roles V2
- Add blocked/block_reason to agents
- Remove task_complexity from agent_roles and history
- Migrate existing data before schema changes
- Block known slow models
"""

import sqlite3
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
DB_PATH = SCRIPT_DIR / "kilo_agents.db"

# Models to block with reasons (from benchmark results)
BLOCKED_MODELS = {
    "deepseek/deepseek-v3.2": "Too slow (109s per review) - REMOVED from benchmarks",
}


def log(msg: str) -> None:
    print(f"[migrate] {msg}")


def run_migration() -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    log("Starting migration to Roles V2...")

    # Step 1: Add blocked columns to agents (if not exist)
    log("Step 1: Adding blocked/block_reason to agents table...")
    try:
        cursor.execute("ALTER TABLE agents ADD COLUMN blocked INTEGER DEFAULT 0")
        log("  Added 'blocked' column")
    except sqlite3.OperationalError as e:
        if "duplicate column" in str(e).lower():
            log("  'blocked' column already exists")
        else:
            raise

    try:
        cursor.execute("ALTER TABLE agents ADD COLUMN block_reason TEXT")
        log("  Added 'block_reason' column")
    except sqlite3.OperationalError as e:
        if "duplicate column" in str(e).lower():
            log("  'block_reason' column already exists")
        else:
            raise

    conn.commit()

    # Step 2: Archive current agent_roles to history (without task_complexity)
    log("Step 2: Archiving current assignments to history...")
    cursor.execute("SELECT COUNT(*) FROM agent_roles")
    current_count = cursor.fetchone()[0]

    if current_count > 0:
        cursor.execute("""
            INSERT INTO agent_roles_history (role, agent_id, priority, reason, min_elo, assigned_by, assigned_at, archived_at)
            SELECT role, agent_id, priority, reason, min_elo, assigned_by, assigned_at, CURRENT_TIMESTAMP
            FROM agent_roles
        """)
        log(f"  Archived {current_count} assignments")
    else:
        log("  No current assignments to archive")

    conn.commit()

    # Step 3: Recreate agent_roles without task_complexity
    log("Step 3: Recreating agent_roles table (clean schema)...")
    cursor.execute("DROP TABLE IF EXISTS agent_roles")
    cursor.execute("""
        CREATE TABLE agent_roles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role TEXT NOT NULL,
            agent_id TEXT NOT NULL REFERENCES agents(id),
            priority INTEGER NOT NULL,
            reason TEXT,
            min_elo INTEGER,
            assigned_by TEXT,
            assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(role, priority)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_roles_role ON agent_roles(role)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_roles_agent ON agent_roles(agent_id)")
    log("  Created clean agent_roles table")

    conn.commit()

    # Step 4: Recreate agent_roles_history without task_complexity
    log("Step 4: Migrating and recreating agent_roles_history...")

    # Backup existing history data
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS _agent_roles_history_backup AS
        SELECT role, agent_id, priority, reason, min_elo, assigned_by, assigned_at, archived_at
        FROM agent_roles_history
    """)
    backup_count = cursor.execute("SELECT COUNT(*) FROM _agent_roles_history_backup").fetchone()[0]
    log(f"  Backed up {backup_count} history records")

    cursor.execute("DROP TABLE IF EXISTS agent_roles_history")
    cursor.execute("""
        CREATE TABLE agent_roles_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role TEXT NOT NULL,
            agent_id TEXT NOT NULL,
            priority INTEGER NOT NULL,
            reason TEXT,
            min_elo INTEGER,
            assigned_by TEXT,
            assigned_at TIMESTAMP NOT NULL,
            archived_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (agent_id) REFERENCES agents(id)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_roles_history_role ON agent_roles_history(role)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_roles_history_date ON agent_roles_history(archived_at)")

    # Restore history data
    cursor.execute("""
        INSERT INTO agent_roles_history (role, agent_id, priority, reason, min_elo, assigned_by, assigned_at, archived_at)
        SELECT role, agent_id, priority, reason, min_elo, assigned_by, assigned_at, archived_at
        FROM _agent_roles_history_backup
    """)
    cursor.execute("DROP TABLE _agent_roles_history_backup")
    log(f"  Restored {backup_count} history records to clean schema")

    conn.commit()

    # Step 5: Block known slow models
    log("Step 5: Blocking known slow/problematic models...")
    for model_id, reason in BLOCKED_MODELS.items():
        cursor.execute(
            "UPDATE agents SET blocked = 1, block_reason = ? WHERE id = ?",
            (reason, model_id),
        )
        if cursor.rowcount > 0:
            log(f"  Blocked: {model_id} ({reason})")
        else:
            log(f"  Model not found: {model_id}")

    conn.commit()

    # Step 6: Update v_role_assignments view
    log("Step 6: Updating v_role_assignments view...")
    cursor.execute("DROP VIEW IF EXISTS v_role_assignments")
    cursor.execute("""
        CREATE VIEW v_role_assignments AS
        SELECT
            r.role,
            r.priority,
            a.id as agent_id,
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
            a.blocked,
            a.block_reason,
            r.reason,
            r.assigned_by,
            r.assigned_at
        FROM agent_roles r
        JOIN agents a ON a.id = r.agent_id
        WHERE a.status = 'active' AND a.blocked = 0
        ORDER BY r.role, r.priority
    """)
    log("  View updated to exclude blocked agents")

    conn.commit()

    # Summary
    log("\n=== Migration Complete ===")
    cursor.execute("SELECT COUNT(*) FROM agents WHERE blocked = 1")
    blocked_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM agent_roles_history")
    history_count = cursor.fetchone()[0]

    log(f"  Agents blocked: {blocked_count}")
    log(f"  History records: {history_count}")
    log("  Current assignments: 0 (ready for fresh role mapping)")

    conn.close()


if __name__ == "__main__":
    run_migration()
