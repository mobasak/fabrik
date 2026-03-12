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

Usage:
    python generate_kilo_agents.py [-h] [-d]

Options:
    -h, --help     Show this help message and exit
    -d, --dry-run  Dry-run mode (do not write files)
"""

import argparse
import json
import os
import time
from pathlib import Path

try:
    import yaml

    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

AGENTS_FILE = Path(__file__).parent / "kilo_47_agents_final.json"
ROUTING_POLICY_FILE = Path.home() / ".traycer" / "routing-policy.yaml"
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

# Save task context for Step 4 (kilo_code_review.py needs it)
# Use unique filename per task to avoid conflicts with concurrent agents
mkdir -p .droid/review-context
TASK_FILE=".droid/review-context/task-${{TRAYCER_TASK_ID:-${{TRAYCER_PHASE_ID:-$(date +%s)}}}}.md"
printf '%s\\n' "$PROMPT" > "$TASK_FILE"
[ "$KILO_DEBUG" = "1" ] && echo "[DEBUG] Task saved to: $TASK_FILE" >&2

# Timeout protection (default 10 minutes)
TIMEOUT="${{KILO_TIMEOUT:-600}}"
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

# Run Kilo agent with streaming output (tee shows real-time AND captures)
# Use --format default for readable streaming, not JSON
# --title sets session name for potential continuation
timeout "$TIMEOUT" kilo run --format default --auto \\
    --model {full_name} \\
    --variant {variant} \\
    --agent {role} \\
    --title "$SESSION_TITLE" \\
    "$PROMPT" 2>&1 | tee "$OUTPUT_FILE"

EXIT_CODE=${{PIPESTATUS[0]}}
END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

# Read captured output for report extraction
OUTPUT=$(cat "$OUTPUT_FILE")

# MANDATORY: Extract and write Traycer report (fail if missing)
REPORT_FOUND=0
if echo "$OUTPUT" | grep -q "BEGIN_TRAYCER_REPORT_MD"; then
    REPORT_FOUND=1
    REPORT_WRITER="/opt/fabrik/scripts/traycer_write_report.py"
    if [ -f "$REPORT_WRITER" ]; then
        echo "$OUTPUT" | python3 "$REPORT_WRITER" --slug "${{TRAYCER_TASK_ID:-traycer-task}}" 2>&1 | grep "📝" >&2 || true
        [ "$KILO_DEBUG" = "1" ] && echo "[DEBUG] Report delimiters found, report writer executed" >&2
    else
        echo "ERROR: Report writer not found at $REPORT_WRITER" >&2
        exit 1
    fi
else
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" >&2
    echo "ERROR: Agent did not output required report block" >&2
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" >&2
    echo "" >&2
    echo "The agent completed execution but failed to output the mandatory" >&2
    echo "BEGIN_TRAYCER_REPORT_MD...END_TRAYCER_REPORT_MD block." >&2
    echo "" >&2
    echo "This indicates the LLM ignored template instructions." >&2
    echo "" >&2
    echo "Solutions:" >&2
    echo "  1. Try a different agent tier (higher-tier models follow instructions better)" >&2
    echo "  2. Enable KILO_DEBUG=1 to see full output" >&2
    echo "  3. Check template at ~/.traycer/prompt-templates/" >&2
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" >&2
    exit 1
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


def main(dry_run: bool = False):
    # Load agent definitions
    with open(AGENTS_FILE) as f:
        data = json.load(f)

    # Load routing policy to determine active vs disabled
    active_scripts = load_active_agents()
    use_routing = len(active_scripts) > 0

    # Create output directories (skip in dry-run)
    if not dry_run:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        DISABLED_DIR.mkdir(parents=True, exist_ok=True)

    # Sort agents by tier order using the sort key function
    # Order: Free (least capable) → Economy → Standard → Pro → Expert → Apex (most capable)
    agents_sorted = sorted(data["agents"], key=lambda a: get_tier_sort_key(a["agent_id"]))

    # Track which files we generate
    generated_files: set[str] = set()
    active_count = 0
    disabled_count = 0

    # Delete and recreate directories for clean ext4 hash table
    # ext4 uses hash-based directory entries; only a fresh dir guarantees order
    if not dry_run:
        import shutil

        # Recreate both directories (active and disabled are separate)
        if OUTPUT_DIR.exists():
            shutil.rmtree(OUTPUT_DIR)
        if DISABLED_DIR.exists():
            shutil.rmtree(DISABLED_DIR)

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        DISABLED_DIR.mkdir(parents=True, exist_ok=True)
        print(f"  🗑 Recreated {OUTPUT_DIR} and {DISABLED_DIR}")

    # Track rank within each tier
    tier_ranks = {}

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
        target_dir = OUTPUT_DIR if is_active else DISABLED_DIR
        filepath = target_dir / filename

        # Track this file for orphan cleanup
        generated_files.add(filename)

        if dry_run:
            # Dry-run: show what would be generated
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
        else:
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

            # Write file with 1 second delay for Traycer timestamp ordering (active only)
            if is_active:
                time.sleep(1)
            filepath.write_text(content)
            filepath.chmod(0o755)

            status_icon = "✓" if is_active else "○"
            status_label = "" if is_active else " [disabled]"
            print(f"          Tier: {tier_name} #{rank:02d} | Role: {role} | Variant: {variant}")
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

    if dry_run:
        print(
            f"\n[DRY-RUN] Would generate {active_count} active + {disabled_count} disabled agents"
        )
        print(f"[DRY-RUN] Active: {OUTPUT_DIR}")
        print(f"[DRY-RUN] Disabled: {DISABLED_DIR}")
        print("[DRY-RUN] Run without --dry-run to actually create files")
    else:
        # Set timestamps for Traycer sorting (newest-first = T1-Free first)
        # Only for active agents
        files = sorted(OUTPUT_DIR.glob("*.sh"))
        n = len(files)
        for i, f in enumerate(files):
            ts = n - i  # T1-Free00 gets highest timestamp (newest)
            os.utime(f, (ts, ts))
        print(f"\n✅ Generated {active_count} active + {disabled_count} disabled agents")
        print(f"   📁 Active: {OUTPUT_DIR}")
        print(f"   📁 Disabled: {DISABLED_DIR}")
        print("   📋 Timestamps set: T1-Free=newest → T7-Specialist=oldest (Traycer sort)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate Kilo CLI Agent Scripts")
    parser.add_argument(
        "-d", "--dry-run", action="store_true", help="Dry-run mode (do not write files)"
    )
    args = parser.parse_args()
    main(dry_run=args.dry_run)
