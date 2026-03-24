#!/usr/bin/env python3
"""
Generate Kilo CLI Agent Scripts from kilo_agents.db

Reads agent role assignments from kilo_agents.db (coding and fixing roles)
and generates self-documenting shell scripts in ~/.traycer/cli-agents/

Naming format: code&fix-{priority}-{model}-{variant}-o{OUT}-ppd{PPD}.sh
Example: code&fix-1-opus46-max-o2500-ppd077.sh

Features:
    - Reads from SQLite database (kilo_agents.db)
    - Only generates coding and fixing role agents (70%+ TBench)
    - Deduplicates agents that appear in both roles with same variant
    - Sequential mtime setting for Traycer sorting
    - Atomic writes with backup rotation

Usage:
    python generate_kilo_agents.py [-h] [-d]

Options:
    -h, --help     Show this help message and exit
    -d, --dry-run  Dry-run mode (do not write files)
"""

import argparse
import os
import shutil
import sqlite3
import sys
import tempfile
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "kilo-benchmarks" / "kilo_agents.db"
OUTPUT_DIR = Path.home() / ".traycer" / "cli-agents"
DISABLED_DIR = Path.home() / ".traycer" / "disabled-cli-agents"

# Model name normalization for filenames
MODEL_NORMALIZE = {
    "claude-opus-4.6": "opus46",
    "claude-opus-4.5": "opus45",
    "claude-sonnet-4.6": "sonnet46",
    "claude-sonnet-4.5": "sonnet45",
    "gpt-5.4": "gpt54",
    "gpt-5.3-codex": "gpt53codex",
    "gpt-5.3-chat": "gpt53chat",
    "gpt-5.2": "gpt52",
    "gpt-5.2-codex": "gpt52codex",
    "gemini-3.1-pro-preview": "gemini31pro",
    "gemini-3-pro-preview": "gemini3pro",
    "gemini-2.5-pro": "gemini25pro",
    "o4-mini": "o4mini",
    "o3-mini-high": "o3minihigh",
}

# Variant assignment by priority (coding/fixing are high-stakes tasks)
VARIANT_BY_PRIORITY = {
    1: "max",  # Top agent: full reasoning
    2: "max",  # Premium: maximize accuracy
    3: "high",  # Fallback: good balance
    4: "high",  # Budget fallback: still solid
    5: "high",  # Extended fallback
}


def normalize_model_name(model_id: str) -> str:
    """Normalize model ID to short filename-safe string."""
    # Try direct lookup first
    if model_id in MODEL_NORMALIZE:
        return MODEL_NORMALIZE[model_id]

    # Extract model part from full kilo path (e.g., kilo/anthropic/claude-opus-4.6)
    if "/" in model_id:
        model_id = model_id.split("/")[-1]

    if model_id in MODEL_NORMALIZE:
        return MODEL_NORMALIZE[model_id]

    # Fallback: clean up the name
    return model_id.replace(".", "").replace("-", "").replace(":", "")[:12]


def encode_price(price: float) -> str:
    """Encode price as integer cents (multiply by 100)."""
    return f"{int(price * 100):04d}"


def get_agents_from_db() -> list[dict]:
    """
    Read coding and fixing role assignments from kilo_agents.db.
    Returns list of agent dicts with role, priority, and agent details.
    """
    if not DB_PATH.exists():
        print(f"❌ Database not found: {DB_PATH}")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Get coding and fixing agents with their details
    query = """
        SELECT
            r.role,
            r.priority,
            a.id as agent_id,
            a.name,
            a.api_id,
            a.provider,
            a.input_cost_per_m,
            a.output_cost_per_m,
            a.arena_elo,
            a.tbench_accuracy,
            a.has_vision,
            a.has_reasoning,
            a.perf_per_dollar
        FROM agent_roles r
        JOIN agents a ON a.id = r.agent_id
        WHERE r.role IN ('coding', 'fixing')
        ORDER BY r.role, r.priority
    """

    cursor.execute(query)
    rows = cursor.fetchall()
    conn.close()

    agents = []
    for row in rows:
        agents.append(
            {
                "role": row["role"],
                "priority": row["priority"],
                "agent_id": row["agent_id"],
                "name": row["name"],
                "api_id": row["api_id"],
                "provider": row["provider"],
                "input_price": row["input_cost_per_m"] or 0.0,
                "output_price": row["output_cost_per_m"] or 0.0,
                "arena_elo": row["arena_elo"],
                "tbench_accuracy": row["tbench_accuracy"],
                "has_vision": row["has_vision"],
                "has_thinking": row["has_reasoning"],
                "ppd": row["perf_per_dollar"],
            }
        )

    return agents


def deduplicate_agents(agents: list[dict]) -> list[dict]:
    """
    Deduplicate agents that appear in both coding and fixing with same variant.
    Returns list with combined role 'code&fix' for duplicates.
    """
    # Group by (api_id, variant)
    seen = {}
    result = []

    for agent in agents:
        variant = VARIANT_BY_PRIORITY.get(agent["priority"], "high")
        key = (agent["api_id"], variant)

        if key in seen:
            # Already seen - mark as code&fix if different role
            existing = seen[key]
            if existing["role"] != agent["role"]:
                existing["role"] = "code&fix"
            # Keep the lower priority number (higher ranking)
            if agent["priority"] < existing["priority"]:
                existing["priority"] = agent["priority"]
        else:
            agent_copy = agent.copy()
            agent_copy["variant"] = variant
            seen[key] = agent_copy
            result.append(agent_copy)

    # Sort by priority
    result.sort(key=lambda x: x["priority"])
    return result


def generate_script_content(agent: dict) -> str:
    """Generate shell script content for a Kilo agent."""
    role = agent["role"]
    priority = agent["priority"]
    api_id = agent["api_id"]
    model_normalized = normalize_model_name(api_id)
    variant = agent["variant"]
    output_encoded = encode_price(agent["output_price"])
    ppd = agent["ppd"] or 0
    ppd_str = f"{int(ppd):03d}" if ppd else "---"

    # Build filename
    script_name = (
        f"{role}-{priority}-{model_normalized}-{variant}-o{output_encoded}-ppd{ppd_str}.sh"
    )

    # Format display values
    elo_display = str(int(agent["arena_elo"])) if agent["arena_elo"] else "—"
    tbench_display = f"{agent['tbench_accuracy']:.1f}%" if agent["tbench_accuracy"] else "—"
    vision_display = "✅" if agent["has_vision"] else "—"
    thinking_display = "✅" if agent["has_thinking"] else "—"

    return f'''#!/bin/bash
# ════════════════════════════════════════════════════════════════════════════
# Kilo Agent - {role.upper()} (Priority #{priority})
# ════════════════════════════════════════════════════════════════════════════
#
# 📛 SCRIPT NAME: {script_name}
#
# 📋 NAMING CONVENTION:
#   Format: <role>-<priority>-<model>-<variant>-o<OUT>-ppd<PPD>.sh
#
#   <role>     = Agent role (code&fix = coding + fixing combined)
#   <priority> = Rank within role (1 = best, 4 = fallback)
#   <model>    = Normalized model name
#   <variant>  = Thinking mode (max = full reasoning, high = balanced)
#   o<OUT>     = Output cost per 1M tokens × 100 (e.g., o2500 = $25.00/1M)
#   ppd<PPD>   = Performance Per Dollar score (higher = better value)
#
# ════════════════════════════════════════════════════════════════════════════
# AGENT DETAILS
# ════════════════════════════════════════════════════════════════════════════
# Role: {role} (Priority #{priority})
# Model: {agent["name"]} ({agent["provider"]})
# Model ID: {api_id}
# Variant: {variant}
#
# BENCHMARKS:
#   Arena ELO: {elo_display}
#   TBench Accuracy: {tbench_display}
#   Vision: {vision_display}
#   Thinking: {thinking_display}
#
# PRICING:
#   Input: ${agent["input_price"]:.2f}/1M tokens
#   Output: ${agent["output_price"]:.2f}/1M tokens
#   PPD: {ppd_str}
# ════════════════════════════════════════════════════════════════════════════

# Error logging - captures errors to file for debugging when terminal closes
AGENT_LOG="${{HOME}}/.traycer/agent-debug.log"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" >> "$AGENT_LOG"
echo "[$(date -Iseconds)] Agent started: {role}-{priority}-{model_normalized}-{variant}" >> "$AGENT_LOG"

# Always log Traycer context for workflow analysis
echo "[$(date -Iseconds)] TRAYCER_TASK_ID=$TRAYCER_TASK_ID" >> "$AGENT_LOG"
echo "[$(date -Iseconds)] TRAYCER_PHASE_ID=$TRAYCER_PHASE_ID" >> "$AGENT_LOG"
echo "[$(date -Iseconds)] TRAYCER_WORKFLOW=$TRAYCER_WORKFLOW" >> "$AGENT_LOG"
echo "[$(date -Iseconds)] TRAYCER_HANDOFF_TYPE=$TRAYCER_HANDOFF_TYPE" >> "$AGENT_LOG"
echo "[$(date -Iseconds)] PROMPT_LENGTH=${{#TRAYCER_PROMPT}}" >> "$AGENT_LOG"
env | grep -E "^TRAYCER_" >> "$AGENT_LOG" 2>/dev/null || true

# Debug mode (KILO_DEBUG=1)
if [ "$KILO_DEBUG" = "1" ]; then
    set -x
    echo "[DEBUG] Agent: {role}-{priority}-{model_normalized}-{variant}" >&2
    echo "[DEBUG] Model: {agent["name"]}" >&2
    echo "[DEBUG] TRAYCER_PROMPT length: ${{#TRAYCER_PROMPT}}" >&2
    echo "[DEBUG] TRAYCER_TASK_ID: $TRAYCER_TASK_ID" >&2
    echo "[DEBUG] TRAYCER_PHASE_ID: $TRAYCER_PHASE_ID" >&2
fi

# Handle both regular and large prompts
if [ -n "$TRAYCER_PROMPT_TMP_FILE" ] && [ -f "$TRAYCER_PROMPT_TMP_FILE" ]; then
    PROMPT=$(cat "$TRAYCER_PROMPT_TMP_FILE")
    [ "$KILO_DEBUG" = "1" ] && echo "[DEBUG] Using TRAYCER_PROMPT_TMP_FILE: $TRAYCER_PROMPT_TMP_FILE" >&2
else
    PROMPT="$TRAYCER_PROMPT"
    [ "$KILO_DEBUG" = "1" ] && echo "[DEBUG] Using TRAYCER_PROMPT environment variable" >&2
fi

# Fix tilde expansion: Traycer (Windows) sends ~/.traycer/ but Kilo may run as different user
PROMPT="${{PROMPT//\\~\\/.traycer\\//${{HOME}}/.traycer/}}"
[ "$KILO_DEBUG" = "1" ] && echo "[DEBUG] Fixed tilde paths in prompt" >&2

# CRITICAL: Append Traycer report requirement to prompt
REPORT_REQUIREMENT='

---
## MANDATORY: Output Report Block (Traycer Integration)

After completing your task, you MUST output this exact block at the end:

```
BEGIN_TRAYCER_REPORT_MD
STATUS: COMPLETE | PARTIAL | FAILED
FILES: <comma-separated changed files or "none">
FOLLOWED: <comma-separated rule IDs or "all">
DEVIATED: <ID:reason; or "none">
ENV: <new vars added to .env.example or "none">
DB: <schema/migration changes or "none">
CHECKS: FG_PRE=PASS|FAIL|SKIP, SELF_REVIEW=DONE|SKIP, KILO=PASS|SKIP, FG_POST=PASS|FAIL|SKIP
VERIFY: <1-2 verification commands>
END_TRAYCER_REPORT_MD
```

This report block is REQUIRED for Traycer integration. The task will fail without it.
---
'
PROMPT="$PROMPT$REPORT_REQUIREMENT"
[ "$KILO_DEBUG" = "1" ] && echo "[DEBUG] Appended Traycer report requirement to prompt" >&2

# Save task context for Step 4 (kilo_code_review.py needs it)
mkdir -p .droid/review-context
TASK_FILE=".droid/review-context/task-${{TRAYCER_TASK_ID:-${{TRAYCER_PHASE_ID:-$(date +%s)}}}}.md"
printf '%s\\n' "$PROMPT" > "$TASK_FILE"
[ "$KILO_DEBUG" = "1" ] && echo "[DEBUG] Task saved to: $TASK_FILE" >&2

# Timeout protection (default 120 minutes)
TIMEOUT="${{KILO_TIMEOUT:-7200}}"
[ "$KILO_DEBUG" = "1" ] && echo "[DEBUG] Timeout: $TIMEOUT seconds" >&2

# Cost tracking setup
USAGE_LOG="${{KILO_USAGE_LOG:-.droid/kilo_usage.jsonl}}"
START_TIME=$(date +%s)

# Temp file for capturing output while streaming
OUTPUT_FILE=$(mktemp)
trap "rm -f $OUTPUT_FILE" EXIT

# Session title for Kilo (uses PHASE_ID for continuity within same phase)
SESSION_TITLE="${{TRAYCER_PHASE_ID:-${{TRAYCER_TASK_ID:-kilo-session}}}}"
[ "$KILO_DEBUG" = "1" ] && echo "[DEBUG] Kilo session title: $SESSION_TITLE" >&2

# Run Kilo agent with streaming output
RUNNER_SCRIPT="/opt/fabrik/scripts/kilo_terminal_runner.py"
RUNNER_PYTHON="/opt/fabrik/.venv/bin/python3"
KILO_RICH_UI="${{KILO_RICH_UI:-1}}"

# Fall back to system python3 if venv not available
if [ ! -x "$RUNNER_PYTHON" ]; then
    RUNNER_PYTHON="python3"
fi

# Shell-side preflight: check env var, runner exists, python available, TTY
USE_RICH_UI=0
if [ "$KILO_RICH_UI" = "1" ] && \\
   [ -f "$RUNNER_SCRIPT" ] && \\
   command -v "$RUNNER_PYTHON" >/dev/null 2>&1 && \\
   [ -t 1 ]; then
    USE_RICH_UI=1
fi

if [ "$USE_RICH_UI" = "1" ]; then
    [ "$KILO_DEBUG" = "1" ] && echo "[DEBUG] Using kilo_terminal_runner.py with $RUNNER_PYTHON" >&2
    "$RUNNER_PYTHON" "$RUNNER_SCRIPT" \\
        --output "$OUTPUT_FILE" \\
        --agent "{role}-{priority}-{model_normalized}" \\
        --model "{agent["name"]}" \\
        --role "{role}" \\
        --variant "{variant}" \\
        --session-title "$SESSION_TITLE" \\
        --timeout "$TIMEOUT" \\
        -- timeout "$TIMEOUT" kilo run --format default --auto --thinking \\
            --model {api_id} \\
            --variant {variant} \\
            --title "$SESSION_TITLE" \\
            "$PROMPT"
    EXIT_CODE=$?
else
    [ "$KILO_DEBUG" = "1" ] && echo "[DEBUG] Plain mode (KILO_RICH_UI=$KILO_RICH_UI, tty=$([ -t 1 ] && echo yes || echo no))" >&2
    timeout "$TIMEOUT" kilo run --format default --auto --thinking \\
        --model {api_id} \\
        --variant {variant} \\
        --title "$SESSION_TITLE" \\
        "$PROMPT" 2>&1 | tee "$OUTPUT_FILE"
    EXIT_CODE=${{PIPESTATUS[0]}}
fi
END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

# Read captured output for report extraction
OUTPUT=$(cat "$OUTPUT_FILE")

# MANDATORY: Extract and write Traycer report (fail if missing)
REPORT_FOUND=0
if echo "$OUTPUT" | grep -q "BEGIN_TRAYCER_REPORT_MD"; then
    REPORT_FOUND=1
    REPORT_WRITER="/opt/fabrik/scripts/traycer_write_report.py"
    REPORT_PYTHON="$RUNNER_PYTHON"
    if [ ! -x "$REPORT_PYTHON" ]; then
        REPORT_PYTHON="python3"
    fi
    if [ -f "$REPORT_WRITER" ]; then
        echo "$OUTPUT" | "$REPORT_PYTHON" "$REPORT_WRITER" --slug "${{TRAYCER_TASK_ID:-traycer-task}}" 2>&1 | grep "📝" >&2 || true
        [ "$KILO_DEBUG" = "1" ] && echo "[DEBUG] Report delimiters found, report writer executed" >&2
    else
        echo "ERROR: Report writer not found at $REPORT_WRITER" >&2
        echo "[$(date -Iseconds)] EXIT 1: Report writer not found" >> "$AGENT_LOG"
        exit 1
    fi
else
    if [ $EXIT_CODE -eq 0 ]; then
        echo "⚠️  Warning: Report block missing but Kilo succeeded (exit 0)" >&2
        echo "[$(date -Iseconds)] WARNING: Missing report block. Kilo exit code was: 0 (success)" >> "$AGENT_LOG"
    else
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" >&2
        echo "ERROR: Agent failed and did not output report block" >&2
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" >&2
        echo "Kilo exit code: $EXIT_CODE" >&2
        echo "[$(date -Iseconds)] EXIT $EXIT_CODE: Missing report block. Kilo exit code was: $EXIT_CODE" >> "$AGENT_LOG"
    fi
fi

# Handle timeout
if [ $EXIT_CODE -eq 124 ]; then
    echo '{{"error": "timeout", "duration": '$TIMEOUT', "agent": "{role}-{priority}-{model_normalized}-{variant}"}}' >&2
    [ "$KILO_DEBUG" = "1" ] && echo "[DEBUG] Task timed out after $TIMEOUT seconds" >&2
fi

# Cost tracking (if enabled)
if [ -n "$KILO_TRACK_COST" ]; then
    mkdir -p "$(dirname "$USAGE_LOG")"
    echo '{{"timestamp":"$(date -Iseconds)","agent":"{role}-{priority}-{model_normalized}-{variant}","model":"{api_id}","task_id":"$TRAYCER_TASK_ID","exit_code":$EXIT_CODE,"duration":$DURATION}}' >> "$USAGE_LOG"
    [ "$KILO_DEBUG" = "1" ] && echo "[DEBUG] Usage logged to $USAGE_LOG" >&2
fi

# Debug summary
if [ "$KILO_DEBUG" = "1" ]; then
    echo "[DEBUG] Exit code: $EXIT_CODE" >&2
    echo "[DEBUG] Duration: $DURATION seconds" >&2
fi

# Exit logic: success if report found, otherwise use kilo's exit code
if [ $REPORT_FOUND -eq 1 ]; then
    exit 0
else
    exit $EXIT_CODE
fi
'''


def validate_script(script_path: Path) -> list[str]:
    """Validate generated shell script."""
    issues = []

    if not script_path.exists():
        return ["File does not exist"]

    content = script_path.read_text()

    if not content.startswith("#!/bin/bash"):
        issues.append("Missing or incorrect shebang")

    if "TRAYCER_PROMPT" not in content:
        issues.append("Missing TRAYCER_PROMPT handling")

    # Shell syntax check
    import subprocess

    result = subprocess.run(["sh", "-n", str(script_path)], capture_output=True, text=True)
    if result.returncode != 0:
        issues.append(f"Shell syntax error: {result.stderr.strip()[:100]}")

    return issues


def main(dry_run: bool = False):
    print("🔄 Reading agents from kilo_agents.db...")

    # Get agents from database
    agents = get_agents_from_db()
    print(f"   Found {len(agents)} coding/fixing role assignments")

    # Deduplicate agents with same model and variant
    agents = deduplicate_agents(agents)
    print(f"   After deduplication: {len(agents)} unique agents")

    if not agents:
        print("❌ No coding/fixing agents found in database")
        sys.exit(1)

    # Track generated files
    generated_count = 0

    if not dry_run:
        # Ensure ~/.traycer exists
        traycer_dir = Path.home() / ".traycer"
        traycer_dir.mkdir(parents=True, exist_ok=True)

        # Backup existing OUTPUT_DIR with rotation (keep 3 newest)
        if OUTPUT_DIR.exists():
            ts = datetime.now().strftime("%Y%m%d-%H%M%S")
            backup_path = traycer_dir / f"cli-agents.backup.{ts}"
            shutil.copytree(OUTPUT_DIR, backup_path)
            print(f"   💾 Backed up to {backup_path}")

            # Rotate: keep only 3 newest backups
            backups = sorted(
                traycer_dir.glob("cli-agents.backup.*"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            for old_backup in backups[3:]:
                shutil.rmtree(old_backup)
                print(f"   🗑 Rotated old backup: {old_backup.name}")

        # Create temp directory for atomic writes
        tmp_dir = Path(tempfile.mkdtemp(dir=traycer_dir, prefix=".cli-agents-tmp-"))

        try:
            for agent in agents:
                role = agent["role"]
                priority = agent["priority"]
                model_normalized = normalize_model_name(agent["api_id"])
                variant = agent["variant"]
                output_encoded = encode_price(agent["output_price"])
                ppd = agent["ppd"] or 0
                ppd_str = f"{int(ppd):03d}" if ppd else "---"

                filename = f"{role}-{priority}-{model_normalized}-{variant}-o{output_encoded}-ppd{ppd_str}.sh"
                filepath = tmp_dir / filename

                content = generate_script_content(agent)
                filepath.write_text(content)
                filepath.chmod(0o755)

                # Validate
                issues = validate_script(filepath)
                if issues:
                    print(f"   ⚠ {filename} - Validation issues:")
                    for issue in issues:
                        print(f"      - {issue}")
                else:
                    print(f"   ✓ {filename}")

                generated_count += 1

            # Atomic rename
            if OUTPUT_DIR.exists():
                shutil.rmtree(OUTPUT_DIR)
            tmp_dir.rename(OUTPUT_DIR)

            # Set timestamps for Traycer sorting (priority 1 = newest)
            files = sorted(OUTPUT_DIR.glob("*.sh"))
            n = len(files)
            for i, f in enumerate(files):
                mtime = n - i
                os.utime(f, (mtime, mtime))

            print(f"\n✅ Generated {generated_count} agent scripts")
            print(f"   📁 Output: {OUTPUT_DIR}")

        except Exception as e:
            shutil.rmtree(tmp_dir, ignore_errors=True)
            print(f"\n❌ Write failed: {e}")
            raise

    else:
        # Dry-run mode
        for agent in agents:
            role = agent["role"]
            priority = agent["priority"]
            model_normalized = normalize_model_name(agent["api_id"])
            variant = agent["variant"]
            output_encoded = encode_price(agent["output_price"])
            ppd = agent["ppd"] or 0
            ppd_str = f"{int(ppd):03d}" if ppd else "---"

            filename = (
                f"{role}-{priority}-{model_normalized}-{variant}-o{output_encoded}-ppd{ppd_str}.sh"
            )

            print(f"[DRY-RUN] Would generate: {filename}")
            print(f"          Model: {agent['name']} ({agent['provider']})")
            print(f"          Role: {role} (Priority #{priority})")
            print(f"          Variant: {variant}")
            print(
                f"          TBench: {agent['tbench_accuracy']:.1f}%"
                if agent["tbench_accuracy"]
                else "          TBench: —"
            )
            generated_count += 1

        print(f"\n[DRY-RUN] Would generate {generated_count} agent scripts")
        print(f"[DRY-RUN] Output: {OUTPUT_DIR}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate Kilo CLI Agent Scripts from DB")
    parser.add_argument(
        "-d", "--dry-run", action="store_true", help="Dry-run mode (do not write files)"
    )
    args = parser.parse_args()
    main(dry_run=args.dry_run)
