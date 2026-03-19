#!/usr/bin/env python3
"""
Development Tracker - Track pre-kilo, kilo review, post-kilo workflow costs.

Usage:
    dev_tracker.py log <event_type> <json_data>
    dev_tracker.py import
    dev_tracker.py report [summary|costs|gates|workflow]
    dev_tracker.py query "<sql>"
"""

import json
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

FABRIK_ROOT = Path(os.getenv("FABRIK_ROOT", "/opt/fabrik"))
DB_PATH = FABRIK_ROOT / ".droid" / "dev_tracker.db"
DROID_DIR = FABRIK_ROOT / ".droid"

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT DEFAULT (datetime('now', 'localtime')),
    project TEXT,
    task_id TEXT,
    phase_id TEXT,
    event_type TEXT NOT NULL,
    data TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_ts ON events(ts);
CREATE INDEX IF NOT EXISTS idx_type ON events(event_type);
"""


def get_db() -> sqlite3.Connection:
    """Get database connection, create schema if needed."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def log_event(event_type: str, data: str) -> None:
    """Log a single event."""
    conn = get_db()
    try:
        json.loads(data)  # Validate JSON
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON - {e}", file=sys.stderr)
        sys.exit(1)

    conn.execute(
        """INSERT INTO events (project, task_id, phase_id, event_type, data)
           VALUES (?, ?, ?, ?, ?)""",
        (
            os.getenv("FABRIK_PROJECT", str(FABRIK_ROOT)),
            os.getenv("TRAYCER_TASK_ID"),
            os.getenv("TRAYCER_PHASE_ID"),
            event_type,
            data,
        ),
    )
    conn.commit()
    conn.close()
    print(f"✓ Logged {event_type}")


def import_jsonl(project_paths: list[Path] | None = None) -> None:
    """Import existing JSONL files from multiple projects."""
    conn = get_db()
    imported = 0

    # Default to fabrik + common project locations
    if project_paths is None:
        project_paths = [FABRIK_ROOT]
        # Add other known projects
        for p in Path("/opt").iterdir():
            if p.is_dir() and (p / ".droid").exists():
                project_paths.append(p)

    for project_root in project_paths:
        droid_dir = project_root / ".droid"
        if not droid_dir.exists():
            continue

        project_name = str(project_root)

        # Import kilo_usage.jsonl -> kilo_review events
        usage_file = droid_dir / "kilo_usage.jsonl"
        if usage_file.exists():
            for line in usage_file.read_text().splitlines():
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                    ts = data.get("timestamp", datetime.now().isoformat())
                    conn.execute(
                        """INSERT INTO events (ts, project, event_type, data) VALUES (?, ?, ?, ?)""",
                        (ts, project_name, "kilo_review", line),
                    )
                    imported += 1
                except (json.JSONDecodeError, sqlite3.Error):
                    continue

        # Import gate_issues.jsonl -> pre_kilo/post_kilo events
        gate_file = droid_dir / "gate_issues.jsonl"
        if gate_file.exists():
            for line in gate_file.read_text().splitlines():
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                    ts = data.get("timestamp", datetime.now().isoformat())
                    gate_type = data.get("gate_type", "pre_kilo")
                    event_type = "post_kilo" if "post" in gate_type.lower() else "pre_kilo"
                    conn.execute(
                        """INSERT INTO events (ts, project, event_type, data) VALUES (?, ?, ?, ?)""",
                        (ts, project_name, event_type, line),
                    )
                    imported += 1
                except (json.JSONDecodeError, sqlite3.Error):
                    continue

        # Import review_sessions.jsonl -> kilo_review events
        sessions_file = droid_dir / "review_sessions.jsonl"
        if sessions_file.exists():
            for line in sessions_file.read_text().splitlines():
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                    ts = data.get("completed_at", datetime.now().isoformat())
                    conn.execute(
                        """INSERT INTO events (ts, project, event_type, data) VALUES (?, ?, ?, ?)""",
                        (ts, project_name, "kilo_review", line),
                    )
                    imported += 1
                except (json.JSONDecodeError, sqlite3.Error):
                    continue

        # Import transcripts -> agent_run events
        transcripts_dir = droid_dir / "transcripts"
        if transcripts_dir.exists():
            for tf in transcripts_dir.glob("*.txt"):
                try:
                    # Parse filename: 20260318-213553-T4-Pro11-sonnet46-exit0.txt
                    parts = tf.stem.split("-")
                    if len(parts) >= 4:
                        date_str = parts[0]  # 20260318
                        time_str = parts[1]  # 213553
                        agent = "-".join(parts[2:-1])  # T4-Pro11-sonnet46
                        exit_code = parts[-1].replace("exit", "")  # 0
                        ts = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}T{time_str[:2]}:{time_str[2:4]}:{time_str[4:6]}"
                        data = json.dumps(
                            {
                                "agent": agent,
                                "exit_code": int(exit_code) if exit_code.isdigit() else -1,
                                "transcript_file": str(tf),
                            }
                        )
                        conn.execute(
                            """INSERT INTO events (ts, project, event_type, data) VALUES (?, ?, ?, ?)""",
                            (ts, project_name, "agent_run", data),
                        )
                        imported += 1
                except (ValueError, sqlite3.Error):
                    continue

    conn.commit()
    conn.close()
    print(f"✓ Imported {imported} events")


def report_summary() -> None:
    """Show today's summary."""
    conn = get_db()
    today = datetime.now().strftime("%Y-%m-%d")

    # Count events (handle various timestamp formats)
    total = conn.execute("SELECT COUNT(*) FROM events WHERE ts LIKE ?", (f"{today}%",)).fetchone()[
        0
    ]

    # Calculate cost
    cost_rows = conn.execute(
        """SELECT json_extract(data, '$.cost_usd') as cost
           FROM events WHERE ts LIKE ? AND event_type IN ('kilo_review', 'agent_run')""",
        (f"{today}%",),
    ).fetchall()
    total_cost = sum(float(r["cost"] or 0) for r in cost_rows)

    # Gate pass rate
    gate_rows = conn.execute(
        """SELECT json_extract(data, '$.passed') as passed
           FROM events WHERE ts LIKE ? AND event_type IN ('pre_kilo', 'post_kilo')""",
        (f"{today}%",),
    ).fetchall()
    gate_total = len(gate_rows)
    gate_passed = sum(1 for r in gate_rows if r["passed"])
    gate_rate = (gate_passed / gate_total * 100) if gate_total > 0 else 0

    print(f"\n📊 Today ({today}):")
    print(f"   Events: {total}")
    print(f"   Cost: ${total_cost:.2f}")
    print(f"   Gate pass rate: {gate_rate:.0f}% ({gate_passed}/{gate_total})")
    conn.close()


def report_costs() -> None:
    """Show cost breakdown by model."""
    conn = get_db()
    rows = conn.execute(
        """SELECT json_extract(data, '$.model') as model,
             COUNT(*) as runs,
             SUM(json_extract(data, '$.cost_usd')) as total_cost
           FROM events
           WHERE event_type IN ('kilo_review', 'agent_run')
             AND json_extract(data, '$.model') IS NOT NULL
           GROUP BY model
           ORDER BY total_cost DESC"""
    ).fetchall()

    print("\n💰 Cost Breakdown:")
    print(f"{'Model':<25} {'Runs':>6} {'Cost':>10} {'Avg':>8}")
    print("-" * 51)
    for r in rows:
        model = r["model"] or "unknown"
        runs = r["runs"]
        cost = float(r["total_cost"] or 0)
        avg = cost / runs if runs > 0 else 0
        print(f"{model:<25} {runs:>6} ${cost:>8.2f} ${avg:>6.3f}")
    conn.close()


def report_gates() -> None:
    """Show gate pass rates."""
    conn = get_db()

    for gate_type in ["pre_kilo", "post_kilo"]:
        rows = conn.execute(
            """SELECT json_extract(data, '$.passed') as passed
               FROM events WHERE event_type = ?""",
            (gate_type,),
        ).fetchall()
        total = len(rows)
        passed = sum(1 for r in rows if r["passed"])
        rate = (passed / total * 100) if total > 0 else 0
        print(f"{gate_type}: {rate:.0f}% pass ({passed}/{total})")

    conn.close()


def report_workflow() -> None:
    """Show full workflow analysis."""
    report_summary()
    report_costs()
    report_gates()


def run_query(sql: str) -> None:
    """Run ad-hoc SQL query."""
    conn = get_db()
    try:
        rows = conn.execute(sql).fetchall()
        if rows:
            # Print header
            print("\t".join(rows[0].keys()))
            print("-" * 60)
            for r in rows:
                print("\t".join(str(v) for v in r))
        else:
            print("No results")
    except sqlite3.Error as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    conn.close()


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 1

    cmd = sys.argv[1]

    if cmd == "log" and len(sys.argv) >= 4:
        log_event(sys.argv[2], sys.argv[3])
    elif cmd == "import":
        import_jsonl()
    elif cmd == "report":
        report_type = sys.argv[2] if len(sys.argv) > 2 else "summary"
        if report_type == "summary":
            report_summary()
        elif report_type == "costs":
            report_costs()
        elif report_type == "gates":
            report_gates()
        elif report_type == "workflow":
            report_workflow()
        else:
            print(f"Unknown report: {report_type}")
            return 1
    elif cmd == "query" and len(sys.argv) >= 3:
        run_query(sys.argv[2])
    else:
        print(__doc__)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
