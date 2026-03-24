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


def report_issues() -> None:
    """Show agent issues summary."""
    conn = get_db()
    today = datetime.now().strftime("%Y-%m-%d")

    # Get issue counts by type
    rows = conn.execute(
        """SELECT json_extract(data, '$.issue_type') as issue_type, COUNT(*) as cnt
           FROM events WHERE ts LIKE ? AND event_type = 'agent_issue'
           GROUP BY issue_type ORDER BY cnt DESC""",
        (f"{today}%",),
    ).fetchall()

    print(f"\n⚠️ Agent Issues ({today}):")
    if rows:
        for r in rows:
            print(f"   {r['issue_type']}: {r['cnt']}")
    else:
        print("   No issues recorded today")

    conn.close()


def report_savings() -> None:
    """Show token savings from deterministic fixes.

    Each auto-fix (whitespace, EOF, formatting) prevents ~500 tokens
    of LLM retry logic. This gamifies keeping the codebase clean.
    """
    conn = get_db()

    # Get total auto_fixed count from pre_kilo events
    rows = conn.execute(
        """SELECT
             COALESCE(SUM(json_extract(data, '$.auto_fixed')), 0) as total_fixes,
             COUNT(*) as gate_runs
           FROM events
           WHERE event_type = 'pre_kilo'
             AND json_extract(data, '$.auto_fixed') IS NOT NULL"""
    ).fetchone()

    total_fixes = int(rows["total_fixes"] or 0)
    gate_runs = int(rows["gate_runs"] or 0)

    # Estimate: 1 deterministic fix = ~500 tokens of prompt/response avoided
    tokens_saved = total_fixes * 500
    # Estimate cost at $0.01 per 1k tokens (Flash/Pro blend)
    cost_avoided = (tokens_saved / 1000) * 0.01

    print("\n💾 Token Savings (Deterministic Fixes):")
    print(f"   Gate runs analyzed: {gate_runs}")
    print(f"   Auto-fixes applied: {total_fixes}")
    print(f"   Estimated tokens saved: ~{tokens_saved:,}")
    print(f"   Estimated cost avoided: ${cost_avoided:.2f}")
    print()
    print("   Why: Each deterministic fix (whitespace, EOF, formatting)")
    print("   prevents ~500 tokens of LLM retry logic.")

    conn.close()


def report_workflow() -> None:
    """Show full workflow analysis."""
    report_summary()
    report_costs()
    report_gates()
    report_issues()
    report_savings()


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


def log_agent_issue(issue_type: str, message: str, agent: str | None = None) -> None:
    """Log an issue encountered by a Kilo CLI agent.

    Usage from agent scripts:
        python dev_tracker.py issue timeout "Model kilo/google/gemini-3-flash timed out"
        python dev_tracker.py issue model_not_found "kilo/mistral/devstral-small"
        python dev_tracker.py issue rate_limit "Plan generation rate limited"
    """
    data = json.dumps(
        {
            "issue_type": issue_type,
            "message": message,
            "agent": agent or os.getenv("TRAYCER_AGENT_NAME", "unknown"),
            "model": os.getenv("KILO_MODEL", "unknown"),
        }
    )
    log_event("agent_issue", data)


def check_cross_project_pollution() -> list[dict]:
    """Detect cross-project pollution in git status.

    Returns list of pollution issues found.
    """
    import subprocess

    cwd = Path.cwd()
    issues = []

    # Get git status
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return issues

        for line in result.stdout.splitlines():
            if not line.strip():
                continue
            # Parse git status line: XY filename
            status = line[:2]
            filepath = line[3:].strip()

            # Check if file belongs to another project
            full_path = cwd / filepath
            try:
                resolved = full_path.resolve()
                # Check if file is outside current project
                if not str(resolved).startswith(str(cwd.resolve())):
                    issues.append(
                        {
                            "type": "external_file",
                            "file": filepath,
                            "resolved": str(resolved),
                            "status": status,
                        }
                    )
                # Check for symlinks pointing outside
                if full_path.is_symlink():
                    target = full_path.readlink()
                    if not str(target).startswith(str(cwd)):
                        issues.append(
                            {
                                "type": "external_symlink",
                                "file": filepath,
                                "target": str(target),
                                "status": status,
                            }
                        )
            except (OSError, ValueError):
                continue

    except subprocess.TimeoutExpired:
        pass

    # Log pollution if found
    if issues:
        data = json.dumps(
            {
                "issue_type": "cross_project_pollution",
                "project": str(cwd),
                "polluted_files": issues,
            }
        )
        log_event("agent_issue", data)
        print(f"⚠️ Cross-project pollution detected: {len(issues)} files")
        for issue in issues:
            print(f"   {issue['type']}: {issue['file']}")

    return issues


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 1

    cmd = sys.argv[1]

    if cmd == "log" and len(sys.argv) >= 4:
        log_event(sys.argv[2], sys.argv[3])
    elif cmd == "issue" and len(sys.argv) >= 3:
        # Quick issue logging: python dev_tracker.py issue <type> [message]
        issue_type = sys.argv[2]
        message = sys.argv[3] if len(sys.argv) > 3 else ""
        log_agent_issue(issue_type, message)
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
        elif report_type == "issues":
            report_issues()
        elif report_type == "savings":
            report_savings()
        else:
            print(f"Unknown report: {report_type}")
            return 1
    elif cmd == "query" and len(sys.argv) >= 3:
        run_query(sys.argv[2])
    elif cmd == "pollution":
        issues = check_cross_project_pollution()
        if not issues:
            print("✓ No cross-project pollution detected")
        return 1 if issues else 0
    else:
        print(__doc__)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
