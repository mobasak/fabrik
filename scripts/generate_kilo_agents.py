#!/usr/bin/env python3
"""
Generate Kilo CLI Agent Scripts (Opus 4.6 Enhanced System)

Reads agent definitions from kilo_47_agents_final.json and generates
detailed, self-documenting scripts in ~/.traycer/cli-agents/

Naming format: {Tier}{NN}-{model}-{role}-{variant}-i{IN}-o{OUT}.sh
Example: Economy02-deepseek32-code-medium-i027-o081.sh

Features:
    - Routing policy integration: Reads ~/.traycer/routing-policy.yaml
      to determine which agents are active vs disabled
    - Active agents placed in ~/.traycer/cli-agents/
    - Disabled agents placed in ~/.traycer/disabled-cli-agents/
    - Sequential mtime setting for Traycer sorting
    - Auto-generates ~/.traycer/routing-policy.md from YAML source of truth

Usage:
    python generate_kilo_agents.py [-h] [-d]

Options:
    -h, --help     Show this help message and exit
    -d, --dry-run  Dry-run mode (do not write files)
"""

import argparse
import json
import os
import shutil
import sys
import tempfile
from datetime import datetime
from pathlib import Path

try:
    import yaml

    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

AGENTS_FILE = Path(__file__).parent / "kilo_47_agents_final.json"
ROUTING_POLICY_FILE = Path.home() / ".traycer" / "routing-policy.yaml"
ROUTING_POLICY_MD = Path.home() / ".traycer" / "routing-policy.md"
OUTPUT_DIR = Path.home() / ".traycer" / "cli-agents"
DISABLED_DIR = Path.home() / ".traycer" / "disabled-cli-agents"

# Tier system: Opus 4.6 Enhanced with numeric prefix for alphabetical sorting
# Traycer sorts alphabetically, so we prefix with T1-T7 to ensure correct order:
# T1-Free (least capable) → T7-Specialist (most specialized)
TIER_ORDER = [
    "T1-Free",
    "T2-Economy",
    "T3-Standard",
    "T4-Pro",
    "T5-Expert",
    "T6-Apex",
    "T7-Specialist",
]

# Map old tier names to new prefixed names
TIER_PREFIX_MAP = {
    "Free": "T1-Free",
    "Economy": "T2-Economy",
    "Standard": "T3-Standard",
    "Pro": "T4-Pro",
    "Expert": "T5-Expert",
    "Apex": "T6-Apex",
    "Specialist": "T7-Specialist",
}

# Model name normalization for filenames (keeps filenames readable)
MODEL_NORMALIZE = {
    "auto": "auto",
    "deepseek-r1": "deepseekr1",
    "minimax-m2.1": "minimax21",
    "glm-4.7-free": "glm47free",
    "glm-4.7": "glm47",
    "kimi-k2.5": "kimik25",
    "kimi-k2": "kimik2",
    "qwen3-coder": "qwen3coder",
    "trinity-large": "trinity",
    "glm-4.5-air": "glm45air",
    "giga-potato": "gigapotato",
    "gemini-3-flash-preview": "flash3",
    "gemini-2.5-flash": "flash25",
    "minimax-m2.5": "m25",
    "gpt-5.2": "gpt52",
    "gpt-5.2-codex": "gpt52codex",
    "gpt-5.3-codex": "gpt53codex",
    "seed-2.0-mini": "seed20mini",
    "glm-4.7-flash": "glm47flash",
    "devstral-small": "devstral",
    "grok-4.1-fast": "grok41fast",
    "codestral": "codestral",
    "grok-4-fast": "grok4fast",
    "deepseek-v3.2": "deepseek32",
    "llama-4-maverick": "llama4mav",
    "glm-5": "glm5",
    "qwen3-235b": "qwen3235b",
    "gpt-5.2-chat": "gpt52chat",
    "gemini-3.1-pro-preview": "gemini31pro",
    "qwen3.5-397b": "qwen35397b",
    "gemini-2.5-pro": "gemini25pro",
    "claude-sonnet-4.5": "sonnet45",
    "claude-sonnet-4.6": "sonnet46",
    "claude-3.7-sonnet": "sonnet37",
    "claude-3.7-sonnet:thinking": "sonnet37think",
    "claude-opus-4.5": "opus45",
    "claude-opus-4.6": "opus46",
    "o3-mini-high": "o3minihigh",
    "gpt-5.2-pro": "gpt52pro",
    "o1-pro": "o1pro",
    "o3-pro": "o3pro",
    "codestral-refactor": "codestralrefactor",
    "codestral-docs": "codestraldocs",
    "codestral-test": "codestraltest",
    "codestral-translate": "codestraltranslate",
    "codestral-review": "codestralreview",
    # GPT-5.x additions (2026-03-09)
    "gpt-5-nano": "gpt5nano",
    "gpt-5-mini": "gpt5mini",
    "gpt-5.1-codex-mini": "gpt51codexmini",
    "gpt-5.1-codex": "gpt51codex",
    "gpt-5.1-codex-max": "gpt51codexmax",
    "gpt-5.3-chat": "gpt53chat",
    "gpt-5.4": "gpt54",
    "gpt-5.4-pro": "gpt54pro",
    "o4-mini": "o4mini",
}


def normalize_model_name(model: str) -> str:
    """Normalize model name for filename."""
    return MODEL_NORMALIZE.get(model, model.replace(".", "").replace("-", "").replace(":", ""))


def encode_price(price: float) -> str:
    """Encode price as integer cents (multiply by 100)."""
    return f"{int(price * 100):03d}"


def parse_agent_id(agent_id: str) -> tuple[str, str]:
    """
    Parse agent_id into prefixed tier name and identifier.

    Examples:
        'free-1' -> ('T1-Free', '1')
        'econ-3' -> ('T2-Economy', '3')
        'spec-refactor' -> ('T7-Specialist', 'refactor')
    """
    tier_map = {
        "free": "T1-Free",
        "econ": "T2-Economy",
        "std": "T3-Standard",
        "pro": "T4-Pro",
        "expert": "T5-Expert",
        "apex": "T6-Apex",
        "spec": "T7-Specialist",
    }

    parts = agent_id.split("-", 1)
    if len(parts) != 2:
        return ("Unknown", agent_id)

    tier_abbrev, identifier = parts
    tier_name = tier_map.get(tier_abbrev, "Unknown")
    return (tier_name, identifier)


def get_tier_sort_key(agent_id: str) -> tuple[int, int | str]:
    """
    Generate sort key for agents to ensure tier-based ordering.

    Returns:
        (tier_index, identifier) where identifier is int for numbered agents, str for named
    """
    tier_name, identifier = parse_agent_id(agent_id)

    try:
        tier_index = TIER_ORDER.index(tier_name)
    except ValueError:
        tier_index = 999  # Unknown tiers go last

    # Try to parse identifier as int for proper numeric sorting
    try:
        identifier_key: int | str = int(identifier)
    except ValueError:
        identifier_key = identifier

    return (tier_index, identifier_key)


def generate_script_content(
    tier_name: str,
    rank: int,
    model_name: str,
    full_name: str,
    provider: str,
    use_case: str,
    variant: str,
    specialty: str,
    input_cost: float,
    output_cost: float,
) -> str:
    """Generate shell script content for a Kilo agent."""
    role = use_case.lower()
    model_normalized = normalize_model_name(model_name)
    input_encoded = encode_price(input_cost)
    output_encoded = encode_price(output_cost)
    script_name = f"{tier_name}{rank:02d}-{model_normalized}-{role}-{variant}-i{input_encoded}-o{output_encoded}.sh"

    # Generate kilo/auto routing documentation if applicable
    auto_routing_docs = ""
    if model_name == "auto":
        auto_routing_docs = """#
# ⚙️  KILO/AUTO ROUTING MECHANISM:
# This agent uses kilo/auto which automatically routes to the best model based on mode:
#   - Review mode  → claude-opus-4.6   ($5.00/1M in, $25.00/1M out)
#   - Code mode    → claude-sonnet-4.5 ($3.00/1M in, $15.00/1M out)
#
# The routing happens server-side in Kilo CLI. This script just passes --model kilo/auto.
# The actual model selection is transparent to this script.
#
# ⚠️  PRICING NOTE:
# Filename shows i000-o000 because kilo/auto itself has no fixed price.
# ACTUAL COSTS depend on which model is selected (see above).
# Expect $3-5/1M input and $15-25/1M output depending on task complexity."""

    # Build pricing line
    if model_name == "auto":
        pricing_line = "# Pricing: VARIABLE (see routing above)"
    else:
        pricing_line = f"# Pricing: ${input_cost:.3f}/1M in, ${output_cost:.3f}/1M out"

    return f"""#!/bin/bash
# ════════════════════════════════════════════════════════════════════════════
# Kilo {role.capitalize()} Agent - {tier_name} Tier
# ════════════════════════════════════════════════════════════════════════════
#
# 📛 SCRIPT NAME: {script_name}
#
# 📋 NAMING CONVENTION EXPLAINED:
#   Format: <TIER><NN>-<model>-<role>-<variant>-i<IN>-o<OUT>.sh
#
#   <TIER>    = Agent tier (quality/cost bracket)
#               Free     = $0 - Zero-cost (sandbox, rapid iteration)
#               Economy  = $0.001-0.10 - Quick tasks (docs, tests, small edits)
#               Standard = $0.10-0.50 - Daily development (default implementation)
#               Pro      = $0.50-3.00 - Production code (code review, refactoring)
#               Expert   = $3.00-10.00 - Complex analysis (architecture, security)
#               Apex     = $20-40 - Mission-critical (Epic planning, critical decisions)
#               Specialist = Task-specific Codestral variants (refactor, docs, test)
#
#   <NN>      = Rank within tier (01-99, ordered by cost)
#
#   <model>   = Normalized model name
#               Examples: deepseek32, opus46, flash25, gpt52pro, o3pro
#
#   <role>    = Agent purpose
#               code   = Code generation, refactoring, implementation
#               review = Code review, security analysis, verification
#
#   <variant> = Effort level (affects token budget, not price per token)
#               auto    = Automatic mode-based selection
#               minimal = Quick tasks, simple code
#               low     = Basic functionality
#               medium  = Standard complexity
#               high    = Complex logic, edge cases
#               max     = Deep reasoning, security-critical
#
#   i<IN>     = Input cost per 1M tokens × 100 (e.g., i027 = $0.27/1M)
#   o<OUT>    = Output cost per 1M tokens × 100 (e.g., o081 = $0.81/1M)
#
#   Examples:
#     Free00-auto-code-auto-i000-o000.sh → Auto router
#     Economy02-deepseek32-code-medium-i027-o081.sh → DeepSeek v3.2
#     Expert06-opus46-code-max-i500-o2500.sh → Claude Opus 4.6
#     Apex03-o3pro-review-max-i4000-o16000.sh → OpenAI o3-pro
#{auto_routing_docs}
#
# ════════════════════════════════════════════════════════════════════════════
# AGENT DETAILS
# ════════════════════════════════════════════════════════════════════════════
# Tier: {tier_name} #{rank:02d}
# Model: {model_name} ({provider})
# Full Name: {full_name}
# Role: {role.capitalize()}
# Variant: {variant}
# Specialty: {specialty}
{pricing_line}
# ════════════════════════════════════════════════════════════════════════════

# Error logging - captures errors to file for debugging when terminal closes
AGENT_LOG="${{HOME}}/.traycer/agent-debug.log"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" >> "$AGENT_LOG"
echo "[$(date -Iseconds)] Agent started: {tier_name}{rank:02d}-{model_normalized}-{role}-{variant}" >> "$AGENT_LOG"

# Always log Traycer context for workflow analysis
echo "[$(date -Iseconds)] TRAYCER_TASK_ID=$TRAYCER_TASK_ID" >> "$AGENT_LOG"
echo "[$(date -Iseconds)] TRAYCER_PHASE_ID=$TRAYCER_PHASE_ID" >> "$AGENT_LOG"
echo "[$(date -Iseconds)] TRAYCER_WORKFLOW=$TRAYCER_WORKFLOW" >> "$AGENT_LOG"
echo "[$(date -Iseconds)] TRAYCER_HANDOFF_TYPE=$TRAYCER_HANDOFF_TYPE" >> "$AGENT_LOG"
echo "[$(date -Iseconds)] PROMPT_LENGTH=${{#TRAYCER_PROMPT}}" >> "$AGENT_LOG"
env | grep -E "^TRAYCER_" >> "$AGENT_LOG" 2>/dev/null || true

# Debug mode (KILO_DEBUG=1)
if [ "$KILO_DEBUG" = "1" ]; then
    set -x  # Print all commands
    echo "[DEBUG] Agent: {tier_name}{rank:02d}-{model_normalized}-{role}-{variant}" >&2
    echo "[DEBUG] Model: {full_name}" >&2
    echo "[DEBUG] TRAYCER_PROMPT length: ${{#TRAYCER_PROMPT}}" >&2
    echo "[DEBUG] TRAYCER_TASK_ID: $TRAYCER_TASK_ID" >&2
    echo "[DEBUG] TRAYCER_PHASE_ID: $TRAYCER_PHASE_ID" >&2
    echo "[DEBUG] TRAYCER_PHASE_BREAKDOWN_ID: $TRAYCER_PHASE_BREAKDOWN_ID" >&2
    echo "[DEBUG] All TRAYCER vars:" >&2
    env | grep TRAYCER >&2 || true
fi

# Handle both regular and large prompts
if [ -n "$TRAYCER_PROMPT_TMP_FILE" ] && [ -f "$TRAYCER_PROMPT_TMP_FILE" ]; then
    # For large prompts - read from temp file
    PROMPT=$(cat "$TRAYCER_PROMPT_TMP_FILE")
    [ "$KILO_DEBUG" = "1" ] && echo "[DEBUG] Using TRAYCER_PROMPT_TMP_FILE: $TRAYCER_PROMPT_TMP_FILE" >&2
else
    # For regular prompts - use environment variable
    PROMPT="$TRAYCER_PROMPT"
    [ "$KILO_DEBUG" = "1" ] && echo "[DEBUG] Using TRAYCER_PROMPT environment variable" >&2
fi

# Fix tilde expansion: Traycer (Windows) sends ~/.traycer/ but Kilo may run as different user
# Replace ~/ and ~/.traycer/ with $HOME equivalents so paths resolve correctly
PROMPT="${{PROMPT//\\~\\/.traycer\\//${{HOME}}/.traycer/}}"
[ "$KILO_DEBUG" = "1" ] && echo "[DEBUG] Fixed tilde paths in prompt" >&2

# CRITICAL: Append Traycer report requirement to prompt
# Without this, the LLM won't know to output the required report block
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
# Use unique filename per task to avoid conflicts with concurrent agents
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
# Use kilo_terminal_runner.py for rich TUI when conditions are met
# Fall back to tee-based streaming otherwise
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
    # Use rich terminal runner (handles ANSI stripping for capture, PTY for proper output)
    # Timeout wraps kilo run (not runner) for symmetric semantics with plain mode
    [ "$KILO_DEBUG" = "1" ] && echo "[DEBUG] Using kilo_terminal_runner.py with $RUNNER_PYTHON" >&2
    "$RUNNER_PYTHON" "$RUNNER_SCRIPT" \\
        --output "$OUTPUT_FILE" \\
        --agent "{tier_name}{rank:02d}-{model_normalized}" \\
        --model "{full_name}" \\
        --role "{role}" \\
        --variant "{variant}" \\
        --session-title "$SESSION_TITLE" \\
        --timeout "$TIMEOUT" \\
        -- timeout "$TIMEOUT" kilo run --format default --auto --thinking \\
            --model {full_name} \\
            --variant {variant} \\
            --agent {role} \\
            --title "$SESSION_TITLE" \\
            "$PROMPT"
    EXIT_CODE=$?
else
    # Fallback: tee-based streaming (shows real-time AND captures)
    [ "$KILO_DEBUG" = "1" ] && echo "[DEBUG] Plain mode (KILO_RICH_UI=$KILO_RICH_UI, tty=$([ -t 1 ] && echo yes || echo no))" >&2
    timeout "$TIMEOUT" kilo run --format default --auto --thinking \\
        --model {full_name} \\
        --variant {variant} \\
        --agent {role} \\
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
    # Reuse RUNNER_PYTHON for consistency (same venv as runner)
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
    # Report block missing - warn but don't fail if Kilo succeeded
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
    echo '{{"error": "timeout", "duration": '$TIMEOUT', "agent": "{tier_name}{rank:02d}-{model_normalized}-{role}-{variant}-i{input_encoded}-o{output_encoded}"}}' >&2
    [ "$KILO_DEBUG" = "1" ] && echo "[DEBUG] Task timed out after $TIMEOUT seconds" >&2
fi

# Cost tracking (if enabled)
if [ -n "$KILO_TRACK_COST" ]; then
    mkdir -p "$(dirname "$USAGE_LOG")"
    echo "{{\"timestamp\":\"$(date -Iseconds)\",\"agent\":\"{tier_name}{rank:02d}-{role}-{variant}-i{input_encoded}-o{output_encoded}\",\"model\":\"{full_name}\",\"task_id\":\"$TRAYCER_TASK_ID\",\"exit_code\":$EXIT_CODE,\"duration\":$DURATION}}" >> "$USAGE_LOG"
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
"""


def validate_script(script_path: Path) -> list[str]:
    """Validate generated shell script"""
    issues = []

    if not script_path.exists():
        return ["File does not exist"]

    content = script_path.read_text()

    # Check shebang
    if not content.startswith("#!/bin/bash"):
        issues.append("Missing or incorrect shebang")

    # Check for exit statement
    if "exit $EXIT_CODE" not in content and "exit $?" not in content:
        issues.append("Missing explicit exit statement")

    # Check for required env var handling
    if "TRAYCER_PROMPT" not in content:
        issues.append("Missing TRAYCER_PROMPT handling")

    # Shell syntax check
    import subprocess

    result = subprocess.run(["sh", "-n", str(script_path)], capture_output=True, text=True)
    if result.returncode != 0:
        issues.append(f"Shell syntax error: {result.stderr.strip()[:100]}")

    return issues


def load_active_agents() -> set[str]:
    """
    Load active agent script names from routing-policy.yaml.
    Returns set of script filenames that should be in the active folder.
    """
    if not YAML_AVAILABLE:
        print("  ⚠ PyYAML not installed, all agents will be active")
        return set()  # Empty = all active

    if not ROUTING_POLICY_FILE.exists():
        print(f"  ⚠ {ROUTING_POLICY_FILE} not found, all agents will be active")
        return set()  # Empty = all active

    try:
        with open(ROUTING_POLICY_FILE) as f:
            policy = yaml.safe_load(f)

        active_scripts: set[str] = set()
        agents_config = policy.get("agents", {})

        for _role_name, agent_info in agents_config.items():
            if isinstance(agent_info, dict):
                script = agent_info.get("script", "")
                active_status = agent_info.get("active", "always")
                # Include both "always" and "conditional" as active
                if active_status in ("always", "conditional") and script:
                    active_scripts.add(script)

        print(f"  📋 Routing policy loaded: {len(active_scripts)} active agents")
        return active_scripts

    except Exception as e:
        print(f"  ⚠ Error loading routing policy: {e}")
        return set()  # Empty = all active


def generate_routing_policy_md(policy: dict) -> str:
    """
    Generate routing-policy.md content from routing-policy.yaml data.
    This keeps the MD in sync with the YAML source of truth.
    """
    from datetime import datetime

    agents = policy.get("agents", {})
    buckets = policy.get("buckets", {})
    guardrails = policy.get("guardrails", {})
    escalation = policy.get("escalation", {})
    defaults = policy.get("defaults", {})

    # Count active agents
    always_active = sum(
        1 for a in agents.values() if isinstance(a, dict) and a.get("active") == "always"
    )
    conditional = sum(
        1 for a in agents.values() if isinstance(a, dict) and a.get("active") == "conditional"
    )

    # Build agent roster table
    always_rows = []
    conditional_rows = []
    for role_name, agent_info in agents.items():
        if not isinstance(agent_info, dict):
            continue
        script = agent_info.get("script", "")
        role = agent_info.get("role", "")
        do_not = agent_info.get("do_not_use_for", "")
        active = agent_info.get("active", "always")
        row = f"| {role_name.replace('_', ' ').title()} | `{script}` | {role} | {do_not} |"
        if active == "always":
            always_rows.append(row)
        else:
            conditional_rows.append(
                f"| {role_name.replace('_', ' ').title()} | `{script}` | {agent_info.get('role', '')} |"
            )

    # Build bucket routing tables
    bucket_tables = []
    for bucket_name, bucket_info in buckets.items():
        if not isinstance(bucket_info, dict):
            continue
        desc = bucket_info.get("description", "")
        default_agent = bucket_info.get("default", "")
        escalate_list = bucket_info.get("escalate", [])
        debug_on = bucket_info.get("debug_on", False)

        table = f"### {bucket_name.upper()} ({desc})\n\n"
        table += "| Attempt | Agent | Why |\n|---------|-------|-----|\n"
        table += f"| 1 | `{default_agent}` | Default for {bucket_name} |\n"
        for i, agent in enumerate(escalate_list, start=2):
            table += f"| {i} | `{agent}` | Escalation |\n"
        if debug_on:
            table += "\n**Debug mode:** Enabled automatically"
        bucket_tables.append(table)

    # Build guardrails section
    never_default = guardrails.get("never_default_to", [])
    daily_workers = guardrails.get("daily_workers", [])
    premium_conditions = guardrails.get("premium_only_when", [])

    # Build escalation triggers
    triggers = escalation.get("triggers", [])
    do_not_escalate = escalation.get("do_not_escalate_for", [])

    today = datetime.now().strftime("%Y-%m-%d")

    md_content = f"""# Traycer Agent Routing Policy

**Last Updated:** {today}
**Source of Truth:** `routing-policy.yaml`

> ⚠️ **AUTO-GENERATED FILE** - Do not edit manually. Edit `routing-policy.yaml` and regenerate.

> Route each ticket to the **cheapest agent likely to finish it correctly**, then escalate only on clear failure signals.

---

## Quick Reference

```text
DEFAULTS
- patch/debug: devstral
- structured repo edit: gpt51codexmini
- clear general feature: gpt5mini
- cheap review: qwen3235b-review
- ambiguous debug: o4mini
- premium coding: sonnet46-code-high
- premium alt coder: gpt54-code-max
- deepest premium coding: sonnet46-code-max
- premium review: sonnet46-review
- final hardest escalation: opus46

ESCALATE WHEN
- 2 failed attempts
- unclear root cause
- security/auth/money/migration/concurrency risk
- repo-wide impact
- review finds correctness issues

NEVER DEFAULT TO
{chr(10).join("- " + a for a in never_default)}
```

---

## Agent Roster

### Always Active ({always_active})

| Role | Agent | Primary Use | Do NOT Use For |
|------|-------|-------------|----------------|
{chr(10).join(always_rows)}

### Conditional Active ({conditional})

| Role | Agent | Enable When |
|------|-------|-------------|
{chr(10).join(conditional_rows)}

---

## Ticket Classification

Before selecting a model, classify the ticket into one of {len(buckets)} buckets:

| Bucket | Description |
|--------|-------------|
{chr(10).join(f"| **{name.title()}** | {info.get('description', '')} |" for name, info in buckets.items() if isinstance(info, dict))}

---

## Routing Tables

{chr(10).join(bucket_tables)}

---

## Debug Mode Policy

Debug mode (`KILO_DEBUG=1`) is **OFF by default**.

### Enable automatically when:

{chr(10).join("- " + c for c in guardrails.get("enable_debug_when", []))}

### Why not global?

- Noisier logs
- Larger outputs
- Harder signal extraction

---

## Escalation Rules

### Escalate when:

{chr(10).join("- " + t for t in triggers)}

### Do NOT escalate for:

{chr(10).join("- " + d for d in do_not_escalate) if do_not_escalate else "- Imperfect but functional output → retry with tighter instructions first"}

---

## Retry Policy

| Attempt | Action |
|---------|--------|
| 1st | Cheap correct-fit model |
| 2nd | Same tier, different model (only if style mismatch) |
| 3rd+ | Escalate one tier |

### Max attempts before human review:

| Ticket Type | Max Attempts |
|-------------|--------------|
{chr(10).join(f"| {name.title()} | {defaults.get('max_attempts', {}).get(name, 3)} |" for name in buckets)}

---

## Cost Guardrails

### Never default to:

{chr(10).join("- `" + a + "`" for a in never_default)}

### Daily worker pool (use for majority):

{chr(10).join("- `" + a + "`" for a in daily_workers)}

### Premium only when:

{chr(10).join("- " + c for c in premium_conditions)}

---

## File Locations

| File | Purpose |
|------|---------|
| `~/.traycer/routing-policy.yaml` | Machine-readable source of truth |
| `~/.traycer/routing-policy.md` | Human documentation (auto-generated) |
| `~/.traycer/cli-agents/` | Active agents (visible to Traycer) |
| `~/.traycer/disabled-cli-agents/` | Disabled agents (hidden from Traycer) |
"""
    return md_content


def update_routing_policy_md(dry_run: bool = False) -> bool:
    """
    Update routing-policy.md from routing-policy.yaml.
    Returns True if successful, False otherwise.
    """
    if not YAML_AVAILABLE:
        print("  ⚠ PyYAML not installed, cannot generate routing-policy.md")
        return False

    if not ROUTING_POLICY_FILE.exists():
        print(f"  ⚠ {ROUTING_POLICY_FILE} not found, cannot generate routing-policy.md")
        return False

    try:
        with open(ROUTING_POLICY_FILE) as f:
            policy = yaml.safe_load(f)

        md_content = generate_routing_policy_md(policy)

        if dry_run:
            print(f"[DRY-RUN] Would update {ROUTING_POLICY_MD}")
        else:
            ROUTING_POLICY_MD.write_text(md_content)
            print(f"  📝 Updated {ROUTING_POLICY_MD} from YAML")

        return True

    except Exception as e:
        print(f"  ⚠ Error generating routing-policy.md: {e}")
        return False


def main(dry_run: bool = False):
    # Load agent definitions
    with open(AGENTS_FILE) as f:
        data = json.load(f)

    # Load routing policy to determine active vs disabled
    active_scripts = load_active_agents()
    use_routing = len(active_scripts) > 0

    # Sort agents by tier order using the sort key function
    # Order: Free (least capable) → Economy → Standard → Pro → Expert → Apex (most capable)
    agents_sorted = sorted(data["agents"], key=lambda a: get_tier_sort_key(a["agent_id"]))

    # Track which files we generate
    generated_files: set[str] = set()
    active_count = 0
    disabled_count = 0

    # Atomic write pattern: backup, write to temp, validate, rename
    # Initialize temp dir variables for exception handling
    tmp_active: Path | None = None
    tmp_disabled: Path | None = None

    if not dry_run:
        # Ensure ~/.traycer exists for mkdtemp (but NOT OUTPUT_DIR/DISABLED_DIR yet)
        traycer_dir = Path.home() / ".traycer"
        traycer_dir.mkdir(parents=True, exist_ok=True)

        # Step 1: Backup existing OUTPUT_DIR with rotation (keep 3 newest)
        # Only backup if OUTPUT_DIR already exists (skip on first run)
        if OUTPUT_DIR.exists():
            ts = datetime.now().strftime("%Y%m%d-%H%M%S")
            backup_path = traycer_dir / f"cli-agents.backup.{ts}"
            shutil.copytree(OUTPUT_DIR, backup_path)
            print(f"  💾 Backed up to {backup_path}")

            # Rotate: keep only 3 newest backups
            backups = sorted(
                traycer_dir.glob("cli-agents.backup.*"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            for old_backup in backups[3:]:
                shutil.rmtree(old_backup)
                print(f"  🗑 Rotated old backup: {old_backup.name}")
        else:
            print("  ℹ First run - no existing agents to backup")

        # Step 2: Create temp directories and write atomically
        # Entire block wrapped in try/except to cleanup temp dirs on any failure
        try:
            tmp_active = Path(tempfile.mkdtemp(dir=traycer_dir, prefix=".cli-agents-tmp-"))
            tmp_disabled = Path(tempfile.mkdtemp(dir=traycer_dir, prefix=".disabled-agents-tmp-"))
            print(f"  📝 Writing to temp dirs: {tmp_active.name}, {tmp_disabled.name}")

            # Track rank within each tier
            tier_ranks: dict[str, int] = {}

            for agent in agents_sorted:
                agent_id = agent["agent_id"]
                tier_name, identifier = parse_agent_id(agent_id)

                # Increment rank for this tier
                if tier_name not in tier_ranks:
                    tier_ranks[tier_name] = 0
                tier_ranks[tier_name] += 1
                rank = tier_ranks[tier_name] - 1  # 0-indexed for first agent

                # Build detailed filename
                model_normalized = normalize_model_name(agent["model_name"])
                input_encoded = encode_price(agent["input_per_1m"])
                output_encoded = encode_price(agent["output_per_1m"])
                role = agent["use_case"].lower()
                variant = agent["variant"]

                filename = f"{tier_name}{rank:02d}-{model_normalized}-{role}-{variant}-i{input_encoded}-o{output_encoded}.sh"

                # Determine if agent is active or disabled
                is_active = not use_routing or filename in active_scripts
                target_dir = tmp_active if is_active else tmp_disabled
                filepath = target_dir / filename

                # Track this file for orphan cleanup
                generated_files.add(filename)

                # Generate script content
                content = generate_script_content(
                    tier_name=tier_name,
                    rank=rank,
                    model_name=agent["model_name"],
                    full_name=agent["full_name"],
                    provider=agent["provider"],
                    use_case=agent["use_case"],
                    variant=agent["variant"],
                    specialty=agent["specialty"],
                    input_cost=agent["input_per_1m"],
                    output_cost=agent["output_per_1m"],
                )

                filepath.write_text(content)
                filepath.chmod(0o755)

                status_icon = "✓" if is_active else "○"
                status_label = "" if is_active else " [disabled]"
                print(
                    f"          Tier: {tier_name} #{rank:02d} | Role: {role} | Variant: {variant}"
                )
                print(f"          Output: {filepath}")

                # Validate generated script
                validation_issues = validate_script(filepath)
                if validation_issues:
                    print(f"  ⚠ {filename} - Validation issues:")
                    for issue in validation_issues:
                        print(f"    - {issue}")
                else:
                    print(f"  {status_icon} {filename}{status_label}")

                if is_active:
                    active_count += 1
                else:
                    disabled_count += 1

            # Step 3: Pre-rename validation gate
            validation_failures = []
            for tmp_dir in [tmp_active, tmp_disabled]:
                for script_path in tmp_dir.glob("*.sh"):
                    issues = validate_script(script_path)
                    if issues:
                        validation_failures.append((script_path.name, issues))

            if validation_failures:
                print("\n❌ Validation failed - aborting atomic rename:")
                for name, issues in validation_failures:
                    print(f"  {name}:")
                    for issue in issues:
                        print(f"    - {issue}")
                # Cleanup temp dirs, leave original untouched
                shutil.rmtree(tmp_active, ignore_errors=True)
                shutil.rmtree(tmp_disabled, ignore_errors=True)
                sys.exit(1)

            # Step 4: Atomic rename (original dirs untouched until this point)
            if OUTPUT_DIR.exists():
                shutil.rmtree(OUTPUT_DIR)
            tmp_active.rename(OUTPUT_DIR)

            if DISABLED_DIR.exists():
                shutil.rmtree(DISABLED_DIR)
            tmp_disabled.rename(DISABLED_DIR)

            # Set timestamps for Traycer sorting (newest-first = T1-Free first)
            files = sorted(OUTPUT_DIR.glob("*.sh"))
            n = len(files)
            for i, f in enumerate(files):
                mtime = n - i  # T1-Free00 gets highest timestamp (newest)
                os.utime(f, (mtime, mtime))
            print(f"\n✅ Generated {active_count} active + {disabled_count} disabled agents")
            print(f"   📁 Active: {OUTPUT_DIR}")
            print(f"   📁 Disabled: {DISABLED_DIR}")
            print("   📋 Timestamps set: T1-Free=newest → T7-Specialist=oldest (Traycer sort)")

        except Exception as e:
            # Cleanup temp dirs on any failure, backup remains for recovery
            if tmp_active is not None:
                shutil.rmtree(tmp_active, ignore_errors=True)
            if tmp_disabled is not None:
                shutil.rmtree(tmp_disabled, ignore_errors=True)
            print(f"\n❌ Write/rename failed: {e}")
            print("   Backup preserved for manual recovery.")
            raise

    else:
        # Dry-run path: no file writes
        tier_ranks: dict[str, int] = {}

        for agent in agents_sorted:
            agent_id = agent["agent_id"]
            tier_name, identifier = parse_agent_id(agent_id)

            if tier_name not in tier_ranks:
                tier_ranks[tier_name] = 0
            tier_ranks[tier_name] += 1
            rank = tier_ranks[tier_name] - 1

            model_normalized = normalize_model_name(agent["model_name"])
            input_encoded = encode_price(agent["input_per_1m"])
            output_encoded = encode_price(agent["output_per_1m"])
            role = agent["use_case"].lower()
            variant = agent["variant"]

            filename = f"{tier_name}{rank:02d}-{model_normalized}-{role}-{variant}-i{input_encoded}-o{output_encoded}.sh"

            is_active = not use_routing or filename in active_scripts
            target_dir = OUTPUT_DIR if is_active else DISABLED_DIR
            filepath = target_dir / filename

            generated_files.add(filename)

            status = "ACTIVE" if is_active else "disabled"
            print(f"[DRY-RUN] Would generate ({status}): {filename}")
            print(f"          Model: {agent['full_name']}")
            print(f"          Tier: {tier_name} #{rank:02d} | Role: {role} | Variant: {variant}")
            print(
                f"          Pricing: ${agent['input_per_1m']:.3f}/1M in, ${agent['output_per_1m']:.3f}/1M out"
            )
            print(f"          Output: {filepath}")
            if is_active:
                active_count += 1
            else:
                disabled_count += 1

        print(
            f"\n[DRY-RUN] Would generate {active_count} active + {disabled_count} disabled agents"
        )
        print(f"[DRY-RUN] Active: {OUTPUT_DIR}")
        print(f"[DRY-RUN] Disabled: {DISABLED_DIR}")
        print("[DRY-RUN] Run without --dry-run to actually create files")

    # Update routing-policy.md from YAML (keeps documentation in sync)
    update_routing_policy_md(dry_run=dry_run)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate Kilo CLI Agent Scripts")
    parser.add_argument(
        "-d", "--dry-run", action="store_true", help="Dry-run mode (do not write files)"
    )
    args = parser.parse_args()
    main(dry_run=args.dry_run)
