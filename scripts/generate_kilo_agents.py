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

Workflow Doc: docs/workflows/KILO_AGENT_MANAGEMENT.md
  ⚠️  Update the workflow doc when modifying this script.
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
OLLAMA_API = "http://localhost:11434"

# Model name normalization for filenames
MODEL_NORMALIZE = {
    # Cloud models
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
    # Local models (Ollama)
    "fabrik-coder-qwen2.5-32b:latest": "fabrik-coder-qwen32b",
    "fabrik-reviewer-llama3.1-70b:latest": "fabrik-reviewer-llama70b",
    "fabrik-fixer-deepseek-v2-16b:latest": "fabrik-fixer-ds16b",
    "fabrik-docs-llama3.1-8b:latest": "fabrik-docs-llama8b",
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
    Read agent role assignments from kilo_agents.db.
    Returns list of agent dicts with role, priority, and agent details.
    Includes both cloud agents (coding/fixing) and local agents (all roles).
    """
    if not DB_PATH.exists():
        print(f"❌ Database not found: {DB_PATH}")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    agents = []

    # Get cloud agents (coding and fixing roles only)
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
                "model_type": "cloud",
            }
        )

    # Get local agents (all roles)
    local_query = """
        SELECT
            name as agent_name,
            assigned_role as role,
            role_priority as priority,
            parameter_size as size,
            context_window_k,
            has_vision,
            has_tools,
            is_agentic,
            is_reasoning,
            arena_elo,
            tbench_accuracy,
            hardware
        FROM local_models
        WHERE assigned_role IS NOT NULL
        ORDER BY assigned_role, role_priority
    """

    cursor.execute(local_query)
    local_rows = cursor.fetchall()

    for row in local_rows:
        # Extract base model name from Ollama name
        base_name = row["agent_name"].replace(":latest", "")

        agents.append(
            {
                "role": row["role"],
                "priority": row["priority"],
                "agent_id": row["agent_name"],  # Use full Ollama name
                "name": base_name,
                "api_id": row["agent_name"],  # Same for local models
                "provider": "ollama",
                "input_price": 0.0,  # Local models are free
                "output_price": 0.0,
                "arena_elo": row["arena_elo"],
                "tbench_accuracy": row["tbench_accuracy"],
                "has_vision": row["has_vision"],
                "has_thinking": row["is_reasoning"],
                "ppd": 999,  # Max value for free models
                "model_type": "local",
                "size": row["size"],
                "context_window_k": row["context_window_k"],
                "hardware": row["hardware"],
            }
        )

    conn.close()
    return agents


def deduplicate_agents(agents: list[dict]) -> list[dict]:
    """
    Deduplicate agents that appear in both coding and fixing with same variant.
    Returns list with combined role 'code&fix' for duplicates.
    Note: Local models are never deduplicated as they have unique purposes.
    """
    # Separate local models (never deduplicate)
    local_agents = [a for a in agents if a.get("model_type") == "local"]
    cloud_agents = [a for a in agents if a.get("model_type") == "cloud"]

    # Group cloud agents by (api_id, variant)
    seen = {}
    result = []

    for agent in cloud_agents:
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

    # Sort cloud agents by priority
    result.sort(key=lambda x: x["priority"])

    # Add local agents (already sorted by role and priority from DB)
    result.extend(local_agents)

    return result


def generate_script_content(agent: dict) -> str:
    """Generate shell script content for a Kilo agent."""
    role = agent["role"]
    priority = agent["priority"]
    api_id = agent["api_id"]
    model_normalized = normalize_model_name(api_id)

    # Handle variant assignment
    if agent.get("model_type") == "local":
        variant = "local"  # All local models use "local" variant
    else:
        variant = agent.get("variant", VARIANT_BY_PRIORITY.get(priority, "high"))

    output_encoded = encode_price(agent["output_price"]) if agent.get("output_price") else "0000"
    ppd = agent["ppd"] or 0
    ppd_str = f"{int(ppd):03d}" if ppd else "---"

    # Build filename
    script_name = (
        f"{role}-{priority}-{model_normalized}-{variant}-o{output_encoded}-ppd{ppd_str}.sh"
    )

    # Format display values
    if agent.get("model_type") == "local":
        elo_display = str(int(agent["arena_elo"])) if agent["arena_elo"] else "—"
        tbench_display = f"{agent['tbench_accuracy']:.1f}%" if agent.get("tbench_accuracy") else "—"
        vision_display = "✅" if agent["has_vision"] else "—"
        thinking_display = "✅" if agent["has_thinking"] else "—"
        pricing_display = "FREE (Local)"
        size_display = agent.get("size", "—")
        hardware_display = agent.get("hardware", "—")
    else:
        elo_display = str(int(agent["arena_elo"])) if agent["arena_elo"] else "—"
        tbench_display = f"{agent['tbench_accuracy']:.1f}%" if agent.get("tbench_accuracy") else "—"
        vision_display = "✅" if agent["has_vision"] else "—"
        thinking_display = "✅" if agent["has_thinking"] else "—"
        pricing_display = f"${agent['output_price']:.2f}/1M tokens"
        size_display = "—"
        hardware_display = "—"

    # Build dynamic content based on model type
    if agent.get("model_type") == "local":
        agent_details = f"""# ════════════════════════════════════════════════════════════════════════════
# Kilo Agent - {role.upper()} (Priority #{priority})
# ════════════════════════════════════════════════════════════════════════════
#
# 📛 SCRIPT NAME: {script_name}
#
# 📋 NAMING CONVENTION:
#   Format: <role>-<priority>-<model>-<variant>-o<OUT>-ppd<PPD>.sh
#
#   <role>     = Agent role
#   <priority> = Rank within role (1 = best)
#   <model>    = Normalized model name
#   <variant>  = Model type (local = Ollama)
#   o<OUT>     = Output cost (0000 = free)
#   ppd<PPD>   = Performance Per Dollar (999 = max for free)
#
# ════════════════════════════════════════════════════════════════════════════
# AGENT DETAILS
# ════════════════════════════════════════════════════════════════════════════
# Role: {role} (Priority #{priority})
# Model: {agent["name"]} (Local Ollama)
# Model ID: {api_id}
# Variant: {variant}
# Size: {size_display}
# Hardware: {hardware_display}
#
# BENCHMARKS:
#   Arena ELO: {elo_display}
#   TBench Accuracy: {tbench_display}
#   Vision: {vision_display}
#   Thinking: {thinking_display}
#
# PRICING:
#   FREE (Local Model)
#   PPD: {ppd_str}
# ═══════════════════════════════════════════════════════════════════════════"""
    else:
        agent_details = f"""# ════════════════════════════════════════════════════════════════════════════
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
#   Output: {pricing_display}
#   PPD: {ppd_str}
# ═══════════════════════════════════════════════════════════════════════════"""

    return f'''#!/bin/bash
{agent_details}

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

# CRITICAL: Extract artifact ID from prompt, then STRIP the task_completion_requirement block.
# Traycer YOLO mode watches for artifact file creation. If agent creates it mid-task,
# Traycer thinks task is done prematurely. We create it in THIS script after kilo exits.
ARTIFACT_ID=""
if echo "$PROMPT" | grep -q "yolo_artifacts"; then
    ARTIFACT_ID=$(echo "$PROMPT" | grep -oP 'yolo_artifacts/\\K[a-f0-9-]+(?=\\.json)')
    [ "$KILO_DEBUG" = "1" ] && echo "[DEBUG] Extracted artifact ID: $ARTIFACT_ID" >&2
    # Strip the task_completion_requirement block so agent doesn't create artifact
    PROMPT=$(echo "$PROMPT" | sed '/<task_completion_requirement>/,/<\\/task_completion_requirement>/d')
    [ "$KILO_DEBUG" = "1" ] && echo "[DEBUG] Stripped task_completion_requirement from prompt" >&2
fi

# Log working directory for debugging (Traycer sets CWD to project directory)
echo "[$(date -Iseconds)] CWD=$(pwd)" >> "$AGENT_LOG"
[ "$KILO_DEBUG" = "1" ] && echo "[DEBUG] CWD: $(pwd)" >&2

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

# Run agent (Kilo for cloud, Ollama for local)
if [ "{agent.get("model_type", "cloud")}" = "local" ]; then
    # LOCAL MODEL: Use Ollama directly with Global Sequential Guard
    [ "$KILO_DEBUG" = "1" ] && echo "[DEBUG] Using Ollama for local model: {api_id}" >&2

    # Determine timeout based on model size
    MODEL_SIZE="{agent.get("size", "unknown")}"
    if [ "$MODEL_SIZE" = "70B" ] || [ "$MODEL_SIZE" = "42GB" ]; then
        TIMEOUT=600
    elif [ "$MODEL_SIZE" = "32B" ] || [ "$MODEL_SIZE" = "19GB" ]; then
        TIMEOUT=600
    else
        TIMEOUT=300
    fi
    [ "$KILO_DEBUG" = "1" ] && echo "[DEBUG] Timeout: $TIMEOUT seconds for model size $MODEL_SIZE" >&2

    # Documentator Fast-Path Check
    if [ "{role}" = "documentation" ]; then
        VRAM_REQ=5500  # 5GB + buffer
        CURRENT_VRAM=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | tr -d '[:space:]')
        GPU_UTIL=$(nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader,nounits | tr -d '[:space:]')
        VRAM_FREE=$((8192 - CURRENT_VRAM))

        if [ "$VRAM_FREE" -gt "$VRAM_REQ" ] && [ "$GPU_UTIL" -lt 5 ]; then
            echo "[FAST-PATH] Bypassing lock: Sufficient VRAM (${{VRAM_FREE}}MiB free)" >&2
            [ "$KILO_DEBUG" = "1" ] && echo "[DEBUG] Using fast-path execution" >&2
            OLLAMA_KEEP_ALIVE=0 timeout "$TIMEOUT" ollama run {api_id} \\
                    "$PROMPT" > "$OUTPUT_FILE" 2>&1
            EXIT_CODE=$?
            OUTPUT=$(cat "$OUTPUT_FILE")
        else
            [ "$KILO_DEBUG" = "1" ] && echo "[DEBUG] Falling back to global lock" >&2
            # Use Global Sequential Guard
            LOCKFILE="/opt/.fabrik_agent.lock"
            (
                flock -x 200

                VRAM_BASELINE=1500
                while true; do
                    LOADED_MODEL=$(ollama ps | tail -n +2 | awk '{{print $1}}')
                    if [ -z "$LOADED_MODEL" ]; then
                        CURRENT_VRAM=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | tr -d '[:space:]')
                        if [ "$CURRENT_VRAM" -lt "$VRAM_BASELINE" ]; then break; fi
                    else
                        GPU_UTIL=$(nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader,nounits | tr -d '[:space:]')
                        [ "$GPU_UTIL" -lt 2 ] && sleep 2 || sleep 5
                    fi
                    sleep 5
                done

            OLLAMA_KEEP_ALIVE=0 timeout "$TIMEOUT" ollama run {api_id} \\
                    "$PROMPT" > "$OUTPUT_FILE" 2>&1
        ) 200>"$LOCKFILE"
        EXIT_CODE=$?
        OUTPUT=$(cat "$OUTPUT_FILE")
        fi
    else
        # Non-documentator models always use Global Sequential Guard
        [ "$KILO_DEBUG" = "1" ] && echo "[DEBUG] Using global sequential guard" >&2
        LOCKFILE="/opt/.fabrik_agent.lock"
        (
            flock -x 200

            VRAM_BASELINE=1500
            while true; do
                LOADED_MODEL=$(ollama ps | tail -n +2 | awk '{{print $1}}')
                if [ -z "$LOADED_MODEL" ]; then
                    CURRENT_VRAM=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | tr -d '[:space:]')
                    if [ "$CURRENT_VRAM" -lt "$VRAM_BASELINE" ]; then break; fi
                else
                    GPU_UTIL=$(nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader,nounits | tr -d '[:space:]')
                    [ "$GPU_UTIL" -lt 2 ] && sleep 2 || sleep 5
                fi
                sleep 5
            done

            OLLAMA_KEEP_ALIVE=0 timeout "$TIMEOUT" ollama run {api_id} \\
                    "$PROMPT" > "$OUTPUT_FILE" 2>&1
        ) 200>"$LOCKFILE"
        EXIT_CODE=$?
        OUTPUT=$(cat "$OUTPUT_FILE")
    fi
else
    # CLOUD MODEL: Use Kilo CLI
    RUNNER_SCRIPT="/opt/fabrik/scripts/kilo_terminal_runner.py"
    RUNNER_PYTHON="/opt/fabrik/.venv/bin/python3"
    KILO_RICH_UI="${{KILO_RICH_UI:-1}}"

    # Fall back to system python3 if venv not available
    if [ ! -x "$RUNNER_PYTHON" ]; then
        RUNNER_PYTHON="python3"
    fi
    if [ -n "$TRAYCER_TASK_ID" ]; then
        # TRAYCER MODE: Background kilo + tail -f for real-time streaming
        # while preserving clean script exit for shell integration completion detection.
        # Key: kilo writes to file, tail streams it, script waits for kilo then exits cleanly.
        [ "$KILO_DEBUG" = "1" ] && echo "[DEBUG] Traycer mode — streaming via tail -f" >&2

        # Start kilo in background, writing directly to output file
        timeout "$TIMEOUT" kilo run --format default --auto --thinking \\
            --model kilo/{api_id} \\
            --variant {variant} \\
            --title "$SESSION_TITLE" \\
            "$PROMPT" > "$OUTPUT_FILE" 2>&1 &
        KILO_PID=$!

        # Stream output in real-time while kilo runs
        tail -f "$OUTPUT_FILE" &
        TAIL_PID=$!

        # Wait for kilo to finish (timeout or natural completion)
        wait "$KILO_PID" 2>/dev/null
        EXIT_CODE=$?

        # Stop tail, capture full output
        kill "$TAIL_PID" 2>/dev/null || true
        wait "$TAIL_PID" 2>/dev/null || true
        OUTPUT=$(cat "$OUTPUT_FILE")
    else
        # INTERACTIVE MODE: Use Rich TUI or tee for real-time streaming
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
                    --model kilo/{api_id} \\
                    --variant {variant} \\
                    --title "$SESSION_TITLE" \\
                    "$PROMPT"
            EXIT_CODE=$?
        else
            [ "$KILO_DEBUG" = "1" ] && echo "[DEBUG] Plain mode (KILO_RICH_UI=$KILO_RICH_UI, tty=$([ -t 1 ] && echo yes || echo no))" >&2
            timeout "$TIMEOUT" kilo run --format default --auto --thinking \\
                --model kilo/{api_id} \\
                --variant {variant} \\
                --title "$SESSION_TITLE" \\
                "$PROMPT" 2>&1 | tee "$OUTPUT_FILE"
            EXIT_CODE=${{PIPESTATUS[0]}}
        fi
    fi
fi
END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

# Preserve full session output for troubleshooting
mkdir -p .droid/transcripts
BACKUP_TRANSCRIPT=".droid/transcripts/$(date +%Y%m%d-%H%M%S)-{role}-{priority}-{model_normalized}-exit$EXIT_CODE-raw.txt"
cp "$OUTPUT_FILE" "$BACKUP_TRANSCRIPT" 2>/dev/null && \
    echo "[$(date -Iseconds)] Transcript backup: $BACKUP_TRANSCRIPT (${{#OUTPUT_FILE}} bytes)" >> "$AGENT_LOG"

# Read captured output for report extraction (interactive mode reads from file)
if [ -z "$TRAYCER_TASK_ID" ]; then
    OUTPUT=$(cat "$OUTPUT_FILE")
fi

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
        REPORT_ERR=$(echo "$OUTPUT" | "$REPORT_PYTHON" "$REPORT_WRITER" --slug "${{TRAYCER_TASK_ID:-traycer-task}}" 2>&1)
        REPORT_RC=$?
        if [ $REPORT_RC -ne 0 ] || ! echo "$REPORT_ERR" | grep -q "\U0001f4dd"; then
            echo "\u26a0\ufe0f  Report writer issue (exit=$REPORT_RC): $REPORT_ERR" >&2
            echo "[$(date -Iseconds)] REPORT_WRITER_ERROR: exit=$REPORT_RC output=$REPORT_ERR" >> "$AGENT_LOG"
        else
            echo "$REPORT_ERR" | grep "\U0001f4dd" >&2
        fi
        [ "$KILO_DEBUG" = "1" ] && echo "[DEBUG] Report writer exit=$REPORT_RC" >&2
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
    echo '{{"timestamp":"$(date -Iseconds)","agent":"{role}-{priority}-{model_normalized}-{variant}","model":"kilo/{api_id}","task_id":"$TRAYCER_TASK_ID","exit_code":$EXIT_CODE,"duration":$DURATION}}' >> "$USAGE_LOG"
    [ "$KILO_DEBUG" = "1" ] && echo "[DEBUG] Usage logged to $USAGE_LOG" >&2
fi

# Debug summary
if [ "$KILO_DEBUG" = "1" ]; then
    echo "[DEBUG] Exit code: $EXIT_CODE" >&2
    echo "[DEBUG] Duration: $DURATION seconds" >&2
fi

# CRITICAL: Create artifact file AFTER kilo exits (not inside kilo)
# This is what signals completion to Traycer YOLO mode
if [ -n "$ARTIFACT_ID" ] && [ $EXIT_CODE -eq 0 ]; then
    ARTIFACT_DIR="$HOME/.traycer/yolo_artifacts"
    mkdir -p "$ARTIFACT_DIR"
    echo '{{}}' > "$ARTIFACT_DIR/$ARTIFACT_ID.json"
    [ "$KILO_DEBUG" = "1" ] && echo "[DEBUG] Created artifact: $ARTIFACT_DIR/$ARTIFACT_ID.json" >&2
    echo "[$(date -Iseconds)] ARTIFACT_CREATED: $ARTIFACT_DIR/$ARTIFACT_ID.json" >> "$AGENT_LOG"
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

    result = subprocess.run(["bash", "-n", str(script_path)], capture_output=True, text=True)
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
            failed_count = 0
            for agent in agents:
                role = agent["role"]
                priority = agent["priority"]
                model_normalized = normalize_model_name(agent["api_id"])

                # Handle variant assignment
                if agent.get("model_type") == "local":
                    variant = "local"
                else:
                    variant = agent.get("variant", VARIANT_BY_PRIORITY.get(priority, "high"))

                output_encoded = (
                    encode_price(agent["output_price"]) if agent.get("output_price") else "0000"
                )
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
                    has_syntax_error = any(
                        "syntax error" in issue.lower() or "shell syntax" in issue.lower()
                        for issue in issues
                    )
                    if has_syntax_error:
                        print(f"   ❌ {filename} - Validation issues:")
                    else:
                        print(f"   ⚠ {filename} - Validation issues:")
                    for issue in issues:
                        print(f"      - {issue}")
                    failed_count += 1
                else:
                    print(f"   ✓ {filename}")

                generated_count += 1

            if failed_count > 0:
                print(f"❌ {failed_count} scripts failed validation — aborting")
                shutil.rmtree(tmp_dir, ignore_errors=True)
                sys.exit(1)

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
        for agent in agents:
            role = agent["role"]
            priority = agent["priority"]
            model_normalized = normalize_model_name(agent["api_id"])

            # Handle variant assignment
            if agent.get("model_type") == "local":
                variant = "local"
            else:
                variant = agent.get("variant", VARIANT_BY_PRIORITY.get(priority, "high"))

            output_encoded = (
                encode_price(agent["output_price"]) if agent.get("output_price") else "0000"
            )
            ppd = agent["ppd"] or 0
            ppd_str = f"{int(ppd):03d}" if ppd else "---"

            filename = (
                f"{role}-{priority}-{model_normalized}-{variant}-o{output_encoded}-ppd{ppd_str}.sh"
            )

            # Build display info based on model type
            if agent.get("model_type") == "local":
                model_info = f"{agent['name']} (Local Ollama)"
                extra_info = f"          Size: {agent.get('size', '—')}, Hardware: {agent.get('hardware', '—')}"
            else:
                model_info = f"{agent['name']} ({agent['provider']})"
                extra_info = ""

            print(f"[DRY-RUN] Would generate: {filename}")
            print(f"          Model: {model_info}")
            print(f"          Role: {role} (Priority #{priority})")
            print(f"          Variant: {variant}")
            print(
                f"          TBench: {agent['tbench_accuracy']:.1f}%"
                if agent.get("tbench_accuracy")
                else "          TBench: —"
            )
            if extra_info:
                print(extra_info)
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
