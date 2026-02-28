#!/usr/bin/env python3
"""
Generate Kilo CLI Agent Scripts with Tier-Based Naming

Reads agent definitions from kilo_18_agents_complete.json and generates
properly named scripts in ~/.traycer/cli-agents/

Naming format: <TIER><NN>-<model>-<role>-<effort>-i<IN>-o<OUT>.sh
Example: P01-opus46-review-max-i500-o2500.sh

Usage:
    python generate_kilo_agents.py [-h] [-d]

Options:
    -h, --help     Show this help message and exit
    -d, --dry-run  Dry-run mode (do not write files)
"""

import argparse
import json
import sys
from pathlib import Path

AGENTS_FILE = Path(__file__).parent / "kilo_18_agents_complete.json"
OUTPUT_DIR = Path.home() / ".traycer" / "cli-agents"

# Tier assignments (based on user specification)
TIER_ASSIGNMENTS = {
    # Auto Tier - Automatic mode-based routing (NEW)
    "A": [
        ("auto", "code", "auto"),
        ("auto", "review", "auto"),
    ],
    # Prime Tier - Mission critical
    "P": [
        ("claude-opus-4.6", "code", "max"),
        ("gpt-5.2-pro", "review", "max"),
        ("claude-opus-4.5", "review", "max"),
    ],
    # Strong Tier - Production grade
    "S": [
        ("gpt-5.3-codex", "code", "high"),
        ("gpt-5.2", "code", "high"),
        ("gemini-3.1-pro-preview", "code", "high"),
        ("claude-sonnet-4.6", "review", "max"),
        ("claude-sonnet-4.5", "review", "max"),
    ],
    # Balanced Tier - Good performance
    "B": [
        ("gpt-5.2-codex", "code", "high"),
        ("gemini-3.1-pro-preview-customtools", "code", "high"),
        ("glm-5", "review", "high"),
        ("grok-4.1-fast", "code", "high"),
        ("gpt-5.2-chat", "review", "max"),
        ("glm-4.7", "code", "medium"),
    ],
    # Economy Tier - Budget friendly
    "E": [
        ("gemini-3-flash-preview", "code", "minimal"),
        ("minimax-m2.5", "code", "low"),
        ("glm-4.7-flash", "code", "minimal"),
        ("seed-2.0-mini", "review", "max"),
    ],
}

# Model name normalization
MODEL_NORMALIZE = {
    "claude-opus-4.6": "opus46",
    "claude-opus-4.5": "opus45",
    "claude-sonnet-4.6": "sonnet46",
    "claude-sonnet-4.5": "sonnet45",
    "gpt-5.2-pro": "gpt52pro",
    "gpt-5.3-codex": "gpt53codex",
    "gpt-5.2": "gpt52",
    "gpt-5.2-chat": "gpt52chat",
    "gpt-5.2-codex": "gpt52codex",
    "gemini-3.1-pro-preview": "gemini31pro",
    "gemini-3.1-pro-preview-customtools": "gemini31tools",
    "gemini-3-flash-preview": "flash3",
    "minimax-m2.5": "m25",
    "glm-4.7": "glm47",
    "glm-4.7-flash": "glm47flash",
    "glm-5": "glm5",
    "grok-4.1-fast": "grok41fast",
    "seed-2.0-mini": "seed20mini",
}


def encode_price(price: float) -> str:
    """Encode price per 1M tokens (price × 100, no decimals)"""
    return f"{round(price * 100):03d}"


def normalize_model_name(model: str) -> str:
    """Normalize model name for filename"""
    return MODEL_NORMALIZE.get(model, model.replace("-", "").replace(".", ""))


def generate_script_content(agent: dict, tier: str, rank: int) -> str:
    """Generate shell script content for agent"""
    full_name = agent["full_name"]
    role = agent["use_case"].lower()
    variant = agent["variant"]
    specialty = agent["specialty"]

    input_price = agent["input_per_1m"]
    output_price = agent["output_per_1m"]

    tier_name = {"A": "Auto", "P": "Prime", "S": "Strong", "B": "Balanced", "E": "Economy"}[tier]

    return f"""#!/bin/sh
# Kilo {role.capitalize()} Agent - {tier_name} Tier #{rank:02d}
# Model: {full_name}
# Role: {role} | Variant: {variant}
# Specialty: {specialty}
# Pricing: ${input_price:.2f}/1M input, ${output_price:.2f}/1M output

# Debug mode (KILO_DEBUG=1)
if [ "$KILO_DEBUG" = "1" ]; then
    set -x  # Print all commands
    echo "[DEBUG] Agent: {tier}{rank:02d}-{agent["model_name"].replace("/", "-").replace("kilo/", "")}-{role}-{variant}" >&2
    echo "[DEBUG] Model: {full_name}" >&2
    echo "[DEBUG] TRAYCER_PROMPT length: ${{#TRAYCER_PROMPT}}" >&2
    echo "[DEBUG] TRAYCER_TASK_ID: $TRAYCER_TASK_ID" >&2
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
mkdir -p .droid/review-context
printf '%s\\n' "$PROMPT" > .droid/review-context/task.md

# Timeout protection (default 10 minutes)
TIMEOUT="${{KILO_TIMEOUT:-600}}"
[ "$KILO_DEBUG" = "1" ] && echo "[DEBUG] Timeout: $TIMEOUT seconds" >&2

# Cost tracking setup
USAGE_LOG="${{KILO_USAGE_LOG:-.droid/kilo_usage.jsonl}}"
START_TIME=$(date +%s)

# Run Kilo agent with timeout
timeout "$TIMEOUT" kilo run --format json --auto \\
    --model {full_name} \\
    --variant {variant} \\
    --agent {role} \\
    "$PROMPT"

EXIT_CODE=$?
END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

# Handle timeout
if [ $EXIT_CODE -eq 124 ]; then
    echo '{{"error": "timeout", "duration": '$TIMEOUT', "agent": "{tier}{rank:02d}"}}' >&2
    [ "$KILO_DEBUG" = "1" ] && echo "[DEBUG] Task timed out after $TIMEOUT seconds" >&2
fi

# Cost tracking (if enabled)
if [ -n "$KILO_TRACK_COST" ]; then
    mkdir -p "$(dirname "$USAGE_LOG")"
    echo "{{\\"timestamp\\":\\"$(date -Iseconds)\\",\\"agent\\":\\"{tier}{rank:02d}-{role}-{variant}\\",\\"model\\":\\"{full_name}\\",\\"task_id\\":\\"$TRAYCER_TASK_ID\\",\\"exit_code\\":$EXIT_CODE,\\"duration\\":$DURATION}}" >> "$USAGE_LOG"
    [ "$KILO_DEBUG" = "1" ] && echo "[DEBUG] Usage logged to $USAGE_LOG" >&2
fi

# Debug summary
if [ "$KILO_DEBUG" = "1" ]; then
    echo "[DEBUG] Exit code: $EXIT_CODE" >&2
    echo "[DEBUG] Duration: $DURATION seconds" >&2
fi

# Capture exit code and exit explicitly
exit $EXIT_CODE
"""


def main(dry_run: bool = False):
    # Load agent definitions
    with open(AGENTS_FILE) as f:
        data = json.load(f)

    # Build lookup dict: (model_name, use_case, variant) -> agent
    # This supports multiple agents with same model_name but different use_case
    agents = {}
    for a in data["agents"]:
        key = (a["model_name"], a["use_case"].lower(), a["variant"])
        agents[key] = a

    # Create output directory (skip in dry-run)
    if not dry_run:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    generated = []

    # Generate scripts per tier
    for tier, assignments in TIER_ASSIGNMENTS.items():
        for rank, (model, role, effort) in enumerate(assignments, start=1):
            # Find agent by (model_name, use_case, variant) tuple
            key = (model, role, effort)
            agent = agents.get(key)
            if not agent:
                print(
                    f"⚠ Warning: {model}/{role}/{effort} not found in agents.json", file=sys.stderr
                )
                continue

            # Build filename
            model_norm = normalize_model_name(model)
            input_enc = encode_price(agent["input_per_1m"])
            output_enc = encode_price(agent["output_per_1m"])

            filename = (
                f"{tier}{rank:02d}-{model_norm}-{role}-{effort}-i{input_enc}-o{output_enc}.sh"
            )
            filepath = OUTPUT_DIR / filename

            if dry_run:
                # Dry-run: show what would be generated
                print(f"[DRY-RUN] Would generate: {filename}")
                print(f"          Model: {agent['full_name']}")
                print(f"          Tier: {tier} | Role: {role} | Variant: {effort}")
                print(f"          Output: {filepath}")
            else:
                # Generate script
                content = generate_script_content(agent, tier, rank)
                filepath.write_text(content)
                filepath.chmod(0o755)
                print(f"          Tier: {tier} | Role: {role} | Variant: {effort}")
                print(f"          Output: {filepath}")

                # Validate generated script
                validation_issues = validate_script(filepath)
                if validation_issues:
                    print(f"  ⚠ {filename} - Validation issues:")
                    for issue in validation_issues:
                        print(f"    - {issue}")
                else:
                    print(f"  ✓ {filename}")

                generated_count += 1

    if dry_run:
        print(f"\n[DRY-RUN] Would generate {generated_count} agent scripts in {OUTPUT_DIR}")
        print("[DRY-RUN] Run without --dry-run to actually create files")
    else:
        print(f"\n✅ Generated {generated_count} agent scripts in {OUTPUT_DIR}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate Kilo CLI Agent Scripts")
    parser.add_argument(
        "-d", "--dry-run", action="store_true", help="Dry-run mode (do not write files)"
    )
    args = parser.parse_args()
    main(dry_run=args.dry_run)
