#!/bin/sh
# ════════════════════════════════════════════════════════════════════════════
# Kilo Code Agent - Balanced Tier #02
# ════════════════════════════════════════════════════════════════════════════
#
# 📛 SCRIPT NAME: Balanced02-gemini31tools-code-high-i200-o1200.sh
#
# 📋 NAMING CONVENTION EXPLAINED:
#   Format: <TIER><NN>-<model>-<role>-<variant>-i<IN>-o<OUT>.sh
#
#   <TIER>    = Agent tier (quality/cost bracket)
#               Auto     = Automatic model routing (kilo/auto)
#               Prime    = Mission-critical, max reasoning (Opus, GPT-5.2 Pro)
#               Strong   = Production-grade (Sonnet, GPT-5.3, Gemini Pro)
#               Balanced = Cost-effective (GPT-5.2, Grok, GLM-5)
#               Economy  = Budget-friendly (Flash, Devstral, DeepSeek, Qwen)
#               Free     = Zero-cost development (MiniMax, GLM, Kimi, Trinity)
#               Ultra    = Codestral specialized agents (~$0.25/M, fast)
#
#   <NN>      = Rank within tier (01-99)
#
#   <model>   = Normalized model name (e.g., opus46, flash3, minimax21)
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
#   i<IN>     = Input cost per 1M tokens × 100 (e.g., i500 = $5.00/1M)
#   o<OUT>    = Output cost per 1M tokens × 100 (e.g., o2500 = $25.00/1M)
#
#
# ════════════════════════════════════════════════════════════════════════════
# AGENT DETAILS
# ════════════════════════════════════════════════════════════════════════════
# Model: kilo/google/gemini-3.1-pro-preview-customtools
# Role: code | Variant: high
# Specialty: Tool use, function calling
# Pricing: $2.00/1M input, $12.00/1M output
# ════════════════════════════════════════════════════════════════════════════

# Debug mode (KILO_DEBUG=1)
if [ "$KILO_DEBUG" = "1" ]; then
    set -x  # Print all commands
    echo "[DEBUG] Agent: Balanced02-gemini-3.1-pro-preview-customtools-code-high" >&2
    echo "[DEBUG] Model: kilo/google/gemini-3.1-pro-preview-customtools" >&2
    echo "[DEBUG] TRAYCER_PROMPT length: ${#TRAYCER_PROMPT}" >&2
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
printf '%s\n' "$PROMPT" > .droid/review-context/task.md

# Timeout protection (default 10 minutes)
TIMEOUT="${KILO_TIMEOUT:-600}"
[ "$KILO_DEBUG" = "1" ] && echo "[DEBUG] Timeout: $TIMEOUT seconds" >&2

# Cost tracking setup
USAGE_LOG="${KILO_USAGE_LOG:-.droid/kilo_usage.jsonl}"
START_TIME=$(date +%s)

# Run Kilo agent with timeout
timeout "$TIMEOUT" kilo run --format json --auto \
    --model kilo/google/gemini-3.1-pro-preview-customtools \
    --variant high \
    --agent code \
    "$PROMPT"

EXIT_CODE=$?
END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

# Handle timeout
if [ $EXIT_CODE -eq 124 ]; then
    echo '{"error": "timeout", "duration": '$TIMEOUT', "agent": "Balanced02"}' >&2
    [ "$KILO_DEBUG" = "1" ] && echo "[DEBUG] Task timed out after $TIMEOUT seconds" >&2
fi

# Cost tracking (if enabled)
if [ -n "$KILO_TRACK_COST" ]; then
    mkdir -p "$(dirname "$USAGE_LOG")"
    echo "{\"timestamp\":\"$(date -Iseconds)\",\"agent\":\"Balanced02-code-high\",\"model\":\"kilo/google/gemini-3.1-pro-preview-customtools\",\"task_id\":\"$TRAYCER_TASK_ID\",\"exit_code\":$EXIT_CODE,\"duration\":$DURATION}" >> "$USAGE_LOG"
    [ "$KILO_DEBUG" = "1" ] && echo "[DEBUG] Usage logged to $USAGE_LOG" >&2
fi

# Debug summary
if [ "$KILO_DEBUG" = "1" ]; then
    echo "[DEBUG] Exit code: $EXIT_CODE" >&2
    echo "[DEBUG] Duration: $DURATION seconds" >&2
fi

# Store model for self-review
KILO_MODEL="kilo/google/gemini-3.1-pro-preview-customtools"

# ==============================================================================
# STEP 2.5: SELF-REVIEW (MANDATORY)
# ==============================================================================
# Agent performs structured self-review before running gates.
# This catches obvious issues early and provides context for Kilo review.
# ==============================================================================

if [ $EXIT_CODE -eq 0 ]; then
    # Detect changed files
    CHANGED_FILES=$(git diff --name-only --diff-filter=ACMR HEAD 2>/dev/null | tr '\n' ' ')

    if [ -n "$CHANGED_FILES" ]; then
        echo "" >&2
        echo "============================================================" >&2
        echo "STEP 2.5: SELF-REVIEW" >&2
        echo "============================================================" >&2

        # Prepare self-review prompt
        SELF_REVIEW_PROMPT="You just implemented this task:

$PROMPT

Files you changed:
$CHANGED_FILES

Now perform a structured self-review. Re-read the task and check your implementation.

Output ONLY this exact format (no extra text):

SELF-REVIEW COMPLETE:
✓ All spec requirements implemented: [Yes/No + brief details]
✓ Edge cases handled: [list specific edge cases you considered, or 'N/A']
✓ Env vars documented: [list any new env vars added to .env.example, or 'N/A']
✓ DB changes documented: [list any schema/migration changes, or 'N/A']
⚠ Potential issues: [list any concerns you identified, or 'None identified']"

        [ "$KILO_DEBUG" = "1" ] && echo "[DEBUG] Running self-review with same model..." >&2

        # Run self-review with same model (fast, cheap)
        # Balanced agents use their own model for self-review
        SELF_REVIEW_OUTPUT=$(timeout 120 kilo run --format text --model "${KILO_MODEL}" --variant minimal "$SELF_REVIEW_PROMPT" 2>&1 || echo "SELF-REVIEW FAILED: Timeout or error")

        [ "$KILO_DEBUG" = "1" ] && echo "[DEBUG] Self-review complete" >&2
        echo "$SELF_REVIEW_OUTPUT" >&2

        # ==============================================================================
        # STEPS 3-5: AUTO-REVIEW WORKFLOW (MANDATORY)
        # ==============================================================================
        # Runs final_gate + kilo review + final_gate again
        # Agent fixes issues in loop until PASS
        # ==============================================================================

        echo "" >&2
        echo "============================================================" >&2
        echo "STEPS 3-5: AUTO-REVIEW WORKFLOW" >&2
        echo "============================================================" >&2

        python /opt/fabrik/scripts/traycer_agent_review.py \
            --task "$PROMPT" \
            --files $CHANGED_FILES \
            --self-review "$SELF_REVIEW_OUTPUT" \
            --session-id "$SESSION_ID" \
            --output json

        REVIEW_EXIT=$?

        if [ $REVIEW_EXIT -eq 0 ]; then
            echo "[SUCCESS] Auto-review workflow PASSED" >&2
        else
            echo "[FAILED] Auto-review workflow FAILED (exit code: $REVIEW_EXIT)" >&2
            echo "[ACTION] Review issues above and fix before committing" >&2
            EXIT_CODE=$REVIEW_EXIT
        fi
    else
        [ "$KILO_DEBUG" = "1" ] && echo "[DEBUG] No changed files, skipping self-review and auto-review" >&2
    fi
fi

exit $EXIT_CODE
