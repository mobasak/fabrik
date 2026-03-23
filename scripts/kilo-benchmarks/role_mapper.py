#!/usr/bin/env python3
"""
AI-Powered Agent Role Mapper.

Uses Kilo CLI with Gemini-3.1-Pro (max thinking) to analyze agents
and assign them to roles based on their capabilities and benchmarks.

Pattern adapted from kilo_code_review.py for proper Kilo CLI interaction.

Roles:
- coding: Write/edit code, implement features
- reviewing: Code review, find bugs, security analysis
- fixing: Debug, fix issues, refactor
- documentation: Write docs, comments, READMEs
- testing: Write tests, test plans, QA

Usage:
    python role_mapper.py                    # Run full assignment
    python role_mapper.py --dry-run          # Preview without saving
    python role_mapper.py --show             # Show current assignments
"""

import json
import shutil
import sqlite3
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).parent
DB_PATH = SCRIPT_DIR / "kilo_agents.db"

# Use Gemini 3.1 Pro with max thinking variant for deep analysis
# Kilo CLI format: kilo/provider/model
# Thinking mode: --variant max (extended reasoning)
KILO_MODEL = "kilo/google/gemini-3.1-pro-preview"
KILO_VARIANT = "max"
ROLES = ["coding", "reviewing", "fixing", "documentation", "testing"]

SYSTEM_PROMPT = """You are an expert AI model selector for a software development workflow.
You will receive a JSON list of AI models with specifications and benchmark scores.
Your task: Assign each role exactly 5 agents (priority 1-5).

## Priority Scale
- Priority 1: best capability, cost irrelevant — for hardest tasks
- Priority 2: high capability, cost secondary
- Priority 3: balanced capability and cost (perf_per_dollar matters)
- Priority 4: cost-efficient, adequate capability
- Priority 5: cheapest adequate model — must still meet min_elo floor

## Roles and Criteria

### coding (implement features, write new code)
- Primary: tbench_accuracy
- Secondary: arena_elo
- Required: has_tools=1 AND is_agentic=1
- Priority 4-5: perf_per_dollar > 500, still needs has_tools=1

### reviewing (code review, bugs, security)
- Primary: arena_elo
- Secondary: has_vision=1
- Required: has_reasoning=1 (models without reasoning capability cannot do code review)
- Prefer: is_agentic=1
- Priority 1-2: highest elo available, cost irrelevant

### fixing (debug, fix issues, refactor)
- Primary: tbench_accuracy + arena_elo combined
- Required: has_tools=1 AND is_agentic=1
- Priority 4-5: perf_per_dollar > 300

### documentation (docs, comments, READMEs)
- Primary: perf_per_dollar
- Required: arena_elo >= 1350
- Prefer: high context_window_k
- Priority 1-2 still cost-optimized — no expensive models here

### testing (write tests, test plans, QA)
- Primary: tbench_accuracy
- Required: has_tools=1 AND is_agentic=1
- Secondary: perf_per_dollar (tests run frequently)
- Priority 3-5: perf_per_dollar > 500

## Hard Rules
1. SKIP any agent where both arena_elo AND tbench_accuracy are null.
2. Each role gets exactly 5 agents, one per priority level.
3. Only status='active' agents.
4. No provider may appear more than once per role.
5. No single agent_id may appear more than 3 times across ALL roles combined.
6. Set min_elo as your recommended runtime floor for that role.

## Output
Return ONLY valid JSON, no markdown fences:
{"assignments": [{"role": "...", "agent_id": "...", "priority": 1, "min_elo": 1400, "reason": "..."}]}"""


def log(msg: str) -> None:
    print(f"[role-mapper] {msg}")


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def find_kilo_executable() -> str | None:
    """Find kilo executable in PATH."""
    return shutil.which("kilo")


def ensure_roles_table() -> None:
    """Create agent_roles table if it doesn't exist."""
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS agent_roles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role TEXT NOT NULL,
            agent_id TEXT NOT NULL,
            priority INTEGER DEFAULT 1,
            reason TEXT,
            min_elo INTEGER,
            assigned_by TEXT,
            assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (agent_id) REFERENCES agents(id),
            UNIQUE(role, priority)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_roles_role ON agent_roles(role)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_roles_agent ON agent_roles(agent_id)")
    conn.commit()
    conn.close()


def get_candidates() -> list[dict[str, Any]]:
    """Get candidate agents for role assignment."""
    conn = get_connection()
    cursor = conn.execute("""
        SELECT
            id, name, provider,
            input_cost_per_m, output_cost_per_m,
            context_window_k, has_vision, has_tools, is_agentic, has_reasoning,
            arena_elo, tbench_accuracy, task_tier, perf_per_dollar, status
        FROM agents
        WHERE status = 'active'
          AND blocked = 0
          AND (arena_elo IS NOT NULL OR tbench_accuracy IS NOT NULL OR task_tier >= 2)
          AND input_cost_per_m >= 0
        ORDER BY
            COALESCE(arena_elo, 0) DESC,
            COALESCE(tbench_accuracy, 0) DESC
        LIMIT 60
    """)

    cols = [d[0] for d in cursor.description]
    candidates = [dict(zip(cols, row, strict=False)) for row in cursor.fetchall()]
    conn.close()

    return candidates


def parse_kilo_jsonl(output: str) -> dict[str, Any]:
    """
    Parse Kilo JSONL output (pattern from kilo_code_review.py).

    Kilo outputs events as concatenated JSON objects.
    Extract text from "text" type events.
    """
    result_text: list[str] = []
    session_id: str | None = None
    input_tokens = 0
    output_tokens = 0
    cost = 0.0
    has_step_finish = False

    decoder = json.JSONDecoder()
    idx = 0
    output_stripped = output.strip()

    while idx < len(output_stripped):
        # Skip whitespace
        while idx < len(output_stripped) and output_stripped[idx] in " \t\n\r":
            idx += 1
        if idx >= len(output_stripped):
            break

        try:
            obj, end_idx = decoder.raw_decode(output_stripped, idx)
            if end_idx <= idx:
                idx += 1
                continue
            idx = end_idx
        except json.JSONDecodeError:
            idx += 1
            continue

        if not isinstance(obj, dict):
            continue

        # Extract session ID
        if "sessionID" in obj:
            session_id = obj["sessionID"]

        event_type = obj.get("type", "")

        # Handle error events
        if event_type == "error":
            error_data = obj.get("error", {})
            error_name = error_data.get("name", "UnknownError")
            error_msg = error_data.get("data", {}).get("message", str(error_data))
            raise RuntimeError(f"Kilo API error ({error_name}): {error_msg}")

        if event_type == "text":
            text = obj.get("text", "")
            if not text and "part" in obj:
                text = obj["part"].get("text", "")
            if text:
                result_text.append(text)

        elif event_type == "step_finish":
            has_step_finish = True
            part = obj.get("part", {})
            tokens = obj.get("tokens") or part.get("tokens", {})
            input_tokens += tokens.get("input", 0)
            output_tokens += tokens.get("output", 0)
            cost += obj.get("cost") or part.get("cost", 0.0)

    if not has_step_finish:
        raise RuntimeError("Kilo run incomplete - no step_finish event received")

    return {
        "result": "".join(result_text),
        "session_id": session_id,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost": cost,
    }


def call_kilo(candidates: list[dict]) -> dict[str, Any]:
    """Call Kilo CLI with Gemini 3.1 Pro (max thinking) to analyze and assign roles."""
    kilo_path = find_kilo_executable()
    if not kilo_path:
        raise RuntimeError("Kilo executable not found. Is it installed?")

    # Build prompt
    prompt = f"""{SYSTEM_PROMPT}

---

Here are {len(candidates)} AI models to analyze:

{json.dumps(candidates, indent=2)}

Assign each of the 5 roles exactly 5 agents (priority 1, 2, 3, 4, 5).
Return valid JSON only - no markdown, no explanation."""

    log(f"Calling Kilo with model: {KILO_MODEL} (variant: {KILO_VARIANT})")
    log(f"Analyzing {len(candidates)} candidate agents...")

    # Build command (pattern from kilo_code_review.py)
    cmd = [
        kilo_path,
        "run",
        "--format",
        "json",
        "--auto",
        "--model",
        KILO_MODEL,
        "--variant",
        KILO_VARIANT,
    ]

    # Execute with stdin prompt using communicate() which handles stdin properly
    try:
        process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
        )
        stdout, stderr = process.communicate(
            input=prompt.encode("utf-8"),
            timeout=300,  # 5 min for thinking
        )
    except subprocess.TimeoutExpired:
        process.kill()
        process.communicate()  # Clean up
        raise RuntimeError("Kilo CLI timed out after 300 seconds")

    if process.returncode != 0:
        error_msg = stderr.decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"Kilo failed (exit {process.returncode}): {error_msg}")

    output = stdout.decode("utf-8", errors="replace")
    log(f"Received {len(output)} chars from Kilo")

    # Parse JSONL output
    parsed = parse_kilo_jsonl(output)
    log(f"Cost: ${parsed['cost']:.4f} ({parsed['input_tokens']} in, {parsed['output_tokens']} out)")

    # Extract JSON from result
    full_text = parsed["result"]

    # Strip markdown fences if present
    if "```" in full_text:
        parts = full_text.split("```")
        for part in parts:
            part = part.strip()
            if part.startswith("json"):
                part = part[4:].strip()
            if part.startswith("{"):
                full_text = part
                break

    # Find JSON object
    start = full_text.find("{")
    end = full_text.rfind("}") + 1
    if start == -1 or end == 0:
        raise ValueError(f"No JSON found in response: {full_text[:500]}")

    return json.loads(full_text[start:end])


def archive_current_assignments(cursor: sqlite3.Cursor) -> int:
    """Archive current role assignments to history before overwriting."""
    cursor.execute("""
        INSERT INTO agent_roles_history (role, agent_id, priority, reason, min_elo, assigned_by, assigned_at)
        SELECT role, agent_id, priority, reason, min_elo, assigned_by, assigned_at
        FROM agent_roles
    """)
    return cursor.rowcount


def apply_assignments(assignments: list[dict], assigned_by: str) -> tuple[int, int, int]:
    """Apply role assignments to database, archiving previous assignments."""
    conn = get_connection()
    cursor = conn.cursor()

    # Archive existing assignments before clearing
    archived = archive_current_assignments(cursor)
    if archived > 0:
        log(f"Archived {archived} previous assignments to history")

    # Clear existing assignments
    cursor.execute("DELETE FROM agent_roles")

    inserted = 0
    skipped = 0

    for a in assignments:
        role = a.get("role")
        agent_id = a.get("agent_id")
        priority = a.get("priority", 1)
        reason = a.get("reason", "")
        min_elo = a.get("min_elo")

        if role not in ROLES:
            log(f"  SKIP: Unknown role '{role}'")
            skipped += 1
            continue

        # Verify agent exists
        cursor.execute("SELECT 1 FROM agents WHERE id = ?", (agent_id,))
        if not cursor.fetchone():
            log(f"  SKIP: Agent not found: {agent_id}")
            skipped += 1
            continue

        cursor.execute(
            """
            INSERT OR REPLACE INTO agent_roles
            (role, agent_id, priority, reason, min_elo, assigned_by)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (role, agent_id, priority, reason, min_elo, assigned_by),
        )
        inserted += 1

    conn.commit()
    conn.close()

    return inserted, skipped, archived


def show_assignments() -> None:
    """Display current role assignments."""
    conn = get_connection()

    try:
        cursor = conn.execute("""
            SELECT
                r.role, r.priority, a.id, a.name, a.arena_elo,
                a.tbench_accuracy, a.input_cost_per_m, a.output_cost_per_m,
                a.perf_per_dollar, a.has_vision, a.blocked, r.reason, r.assigned_by
            FROM agent_roles r
            JOIN agents a ON a.id = r.agent_id
            WHERE a.blocked = 0
            ORDER BY r.role, r.priority
        """)
    except sqlite3.OperationalError:
        log("No role assignments found")
        conn.close()
        return

    print("\n" + "=" * 80)
    print("AGENT ROLE ASSIGNMENTS")
    print("=" * 80)

    current_role = None
    assigned_by = None
    for row in cursor.fetchall():
        role, pri, agent_id, name, elo, tbench, cin, cout, ppd, has_vision, blocked, reason, by = (
            row
        )

        if role != current_role:
            print(f"\n[{role.upper()}]")
            current_role = role

        assigned_by = by
        vision_str = " [vision]" if has_vision else ""
        elo_str = str(elo) if elo else "n/a"
        tbench_str = f"{tbench:.1f}%" if tbench else "n/a"
        ppd_str = f"{ppd:.0f}" if ppd else "n/a"

        print(f"  #{pri} {name}{vision_str}")
        print(
            f"      elo={elo_str} | tbench={tbench_str} | ${cin}/${cout} per 1M | perf/$={ppd_str}"
        )
        if reason:
            print(f"      → {reason}")

    print("\n" + "=" * 80)
    if assigned_by:
        print(f"Assigned by: {assigned_by}")
    conn.close()


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="AI-powered agent role mapper")
    parser.add_argument("--dry-run", action="store_true", help="Preview without saving")
    parser.add_argument("--show", action="store_true", help="Show current assignments")
    args = parser.parse_args()

    if args.show:
        ensure_roles_table()
        show_assignments()
        return 0

    log(f"Starting role mapper ({datetime.now().isoformat()})")
    ensure_roles_table()

    # Get candidates
    candidates = get_candidates()
    log(f"Found {len(candidates)} candidate agents")

    if not candidates:
        log("ERROR: No candidate agents found")
        return 1

    # Call AI for analysis
    try:
        result = call_kilo(candidates)
    except Exception as e:
        log(f"ERROR: {e}")
        return 1

    # Extract assignments
    assignments = result.get("assignments", [])
    analysis = result.get("analysis", "")

    log(f"AI returned {len(assignments)} assignments")
    if analysis:
        log(f"Analysis: {analysis[:200]}...")

    if args.dry_run:
        print("\n=== DRY RUN - Would assign: ===")
        for a in assignments:
            print(f"  {a['role']}#{a['priority']}: {a['agent_id']}")
            if a.get("reason"):
                print(f"    → {a['reason']}")
        return 0

    # Apply to database
    inserted, skipped, archived = apply_assignments(assignments, KILO_MODEL)
    log(f"Applied {inserted} assignments, skipped {skipped}, archived {archived}")

    # Show results
    show_assignments()

    log(f"Done ({datetime.now().isoformat()})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
