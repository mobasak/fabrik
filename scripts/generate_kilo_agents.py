#!/usr/bin/env python3
"""
Generate Kilo CLI Agent Scripts with Tier-Based Naming

Reads agent definitions from kilo_18_agents_complete.json and generates
properly named scripts in ~/.traycer/cli-agents/

Naming format: <TIER><NN>-<model>-<role>-<effort>-i<IN>-o<OUT>.sh
Example: P01-opus46-review-max-i500-o2500.sh

Usage:
    python generate_kilo_agents.py
"""

import json
from pathlib import Path

AGENTS_FILE = Path(__file__).parent / "kilo_18_agents_complete.json"
OUTPUT_DIR = Path.home() / ".traycer" / "cli-agents"

# Tier assignments (based on user specification)
TIER_ASSIGNMENTS = {
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

    tier_name = {"P": "Prime", "S": "Strong", "B": "Balanced", "E": "Economy"}[tier]

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


def main():
    # Load agent definitions
    with open(AGENTS_FILE) as f:
        data = json.load(f)

    agents = {a["model_name"]: a for a in data["agents"]}

    # Create output directory
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    generated = []

    # Generate scripts for each tier
    for tier, tier_agents in TIER_ASSIGNMENTS.items():
        for rank, (model_name, role, variant) in enumerate(tier_agents, 1):
            if model_name not in agents:
                print(f"⚠ Warning: {model_name} not found in agents.json")
                continue

            agent = agents[model_name]

            # Verify role and variant match
            if agent["use_case"].lower() != role or agent["variant"] != variant:
                print(f"⚠ Warning: {model_name} role/variant mismatch")
                continue

            # Build filename
            model_norm = normalize_model_name(model_name)
            input_enc = encode_price(agent["input_per_1m"])
            output_enc = encode_price(agent["output_per_1m"])

            filename = (
                f"{tier}{rank:02d}-{model_norm}-{role}-{variant}-i{input_enc}-o{output_enc}.sh"
            )
            filepath = OUTPUT_DIR / filename

            # Generate script
            content = generate_script_content(agent, tier, rank)
            filepath.write_text(content)
            filepath.chmod(0o755)

            generated.append(filename)
            print(f"✓ Generated: {filename}")

    print(f"\n✅ Generated {len(generated)} agent scripts in {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
