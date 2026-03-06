#!/usr/bin/env python3
"""
Apply Self-Review Workflow to Balanced Tier Agents

Applies the same fixes as free/economy tier agents:
1. Real self-review (separate Kilo call, not placeholder)
2. Mandatory workflow (always runs)
3. Self-review validation

Usage:
    python scripts/fix_balanced_tier_agents.py
"""

import re
from pathlib import Path


def generate_self_review_section() -> str:
    """Generate the self-review implementation for agent scripts."""
    return """# ==============================================================================
# STEP 2.5: SELF-REVIEW (MANDATORY)
# ==============================================================================
# Agent performs structured self-review before running gates.
# This catches obvious issues early and provides context for Kilo review.
# ==============================================================================

if [ $EXIT_CODE -eq 0 ]; then
    # Detect changed files
    CHANGED_FILES=$(git diff --name-only --diff-filter=ACMR HEAD 2>/dev/null | tr '\\n' ' ')

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

        python /opt/fabrik/scripts/traycer_agent_review.py \\
            --task "$PROMPT" \\
            --files $CHANGED_FILES \\
            --self-review "$SELF_REVIEW_OUTPUT" \\
            --session-id "$SESSION_ID" \\
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
fi"""


def extract_model_from_agent(content: str) -> str:
    """Extract model name from agent script."""
    match = re.search(r"--model\s+(\S+)", content)
    return match.group(1) if match else "kilo/auto"


def update_agent_script(agent_file: Path, output_dir: Path) -> bool:
    """Copy and update agent script with self-review implementation."""

    content = agent_file.read_text()

    # Extract model for self-review
    model = extract_model_from_agent(content)

    # Check if already has modern structure
    if "STEP 2.5: SELF-REVIEW" in content:
        return False  # Already updated

    # Find insertion point (before final exit)
    exit_match = re.search(r"# Capture exit code and exit explicitly\nexit \$EXIT_CODE", content)
    if not exit_match:
        # Try alternate pattern
        exit_match = re.search(r"exit \$EXIT_CODE\s*$", content)

    if not exit_match:
        print(f"  ⚠️  Could not find exit point in {agent_file.name}")
        return False

    # Insert model environment variable at top of self-review section
    self_review_code = (
        f'# Store model for self-review\nKILO_MODEL="{model}"\n\n' + generate_self_review_section()
    )

    # Replace exit with self-review + exit
    new_content = content[: exit_match.start()] + self_review_code + "\n\nexit $EXIT_CODE\n"

    # Write to output directory
    output_file = output_dir / agent_file.name
    output_file.write_text(new_content)
    output_file.chmod(0o755)

    return True


def main():
    """Fix all balanced tier agents."""

    source_dir = Path.home() / ".traycer" / "cli-agents"
    output_dir = Path("/opt/fabrik/scripts/traycer_agents_fixed")

    if not source_dir.exists():
        print("❌ Error: Source agents directory not found")
        return 1

    # Find balanced tier agents
    balanced_agents = sorted(source_dir.glob("Balanced*.sh"))

    if not balanced_agents:
        print("❌ Error: No balanced tier agents found")
        return 1

    print(f"Found {len(balanced_agents)} balanced tier agents")
    print()

    output_dir.mkdir(parents=True, exist_ok=True)

    updated_count = 0
    skipped_count = 0

    # Process each agent
    for agent_file in balanced_agents:
        print(f"Processing: {agent_file.name}")

        if update_agent_script(agent_file, output_dir):
            print("  ✅ Updated with self-review workflow")
            updated_count += 1
        else:
            print("  ⏭️  Already updated or couldn't update")
            skipped_count += 1

    print()
    print("=" * 60)
    print(f"✅ Updated: {updated_count} agents")
    print(f"⏭️  Skipped: {skipped_count} agents")
    print()
    print(f"Output: {output_dir}")
    print()
    print("Balanced tier agents ready for testing")

    return 0


if __name__ == "__main__":
    exit(main())
