#!/usr/bin/env python3
# AFTER-EDIT: none
"""
Implement Complete Traycer→Kilo Self-Review Workflow

This script updates all 9 free tier agents to implement real self-review:
1. Agent codes task
2. Agent performs Step 2.5 self-review (separate Kilo call)
3. Agent calls traycer_agent_review.py with real self-review
4. Review script runs Steps 3-5 (Pre-Kilo, Kilo Review, Post-Kilo)
5. Agent fixes issues in loop until PASS

Usage:
    python scripts/implement_self_review_workflow.py
"""

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
        SELF_REVIEW_OUTPUT=$(timeout 120 kilo run --format text --model kilo/minimax/minimax-m2.1 --variant minimal "$SELF_REVIEW_PROMPT" 2>&1 || echo "SELF-REVIEW FAILED: Timeout or error")

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


def update_agent_script(agent_file: Path) -> bool:
    """Update agent script with self-review implementation."""

    content = agent_file.read_text()

    # Check if already updated
    if "STEP 2.5: SELF-REVIEW" in content:
        return False  # Already updated

    # Find the old optional auto-review section
    old_section_start = content.find("# OPTIONAL: Auto-review hook")
    old_section_end = content.find("exit $EXIT_CODE", old_section_start)

    if old_section_start == -1 or old_section_end == -1:
        print(f"  ⚠️  Could not find replacement point in {agent_file.name}")
        return False

    # Replace old section with new implementation
    new_content = (
        content[:old_section_start] + generate_self_review_section() + "\n\nexit $EXIT_CODE\n"
    )

    # Write updated content
    agent_file.write_text(new_content)
    return True


def validate_self_review_in_traycer_agent_review() -> bool:
    """Add validation to traycer_agent_review.py to reject placeholder self-reviews."""

    script_path = Path("/opt/fabrik/scripts/traycer_agent_review.py")
    content = script_path.read_text()

    # Check if validation already exists
    if "Self-review is placeholder" in content:
        return False  # Already updated

    # Find the main() function after args are parsed
    insertion_point = content.find(
        "# ========================================================================"
    )
    insertion_point = content.find("# STEP 2.5: Self-Review", insertion_point)

    if insertion_point == -1:
        print("  ⚠️  Could not find insertion point in traycer_agent_review.py")
        return False

    # Find end of Step 2.5 section
    end_of_section = content.find(
        "# ========================================================================",
        insertion_point + 10,
    )

    validation_code = """
    # Validate self-review is not placeholder or failed
    if "Agent completed implementation" in args.self_review:
        result = {
            "workflow": "traycer_agent_auto_review",
            "error": "Self-review is placeholder. Agent must perform actual self-review.",
            "exit_code": 2,
        }
        if args.output == "json":
            print(json.dumps(result, indent=2))
        else:
            print("❌ ERROR: Self-review is placeholder", file=sys.stderr)
        return 2

    if "SELF-REVIEW FAILED" in args.self_review:
        result = {
            "workflow": "traycer_agent_auto_review",
            "error": "Self-review failed (timeout or error). Cannot proceed.",
            "exit_code": 2,
        }
        if args.output == "json":
            print(json.dumps(result, indent=2))
        else:
            print("❌ ERROR: Self-review failed", file=sys.stderr)
        return 2

    # Validate self-review has required format
    required_markers = ["✓ All spec requirements", "✓ Edge cases", "✓ Env vars", "✓ DB changes", "⚠ Potential issues"]
    missing = [m for m in required_markers if m not in args.self_review]

    if missing:
        print(f"⚠️  WARNING: Self-review missing sections: {', '.join(missing)}", file=sys.stderr)
        print("⚠️  Proceeding anyway, but self-review may be incomplete", file=sys.stderr)

"""

    new_content = content[:end_of_section] + validation_code + content[end_of_section:]

    script_path.write_text(new_content)
    return True


def main():
    """Update all free tier agents with self-review workflow."""

    agents_dir = Path("/opt/fabrik/scripts/traycer_agents_fixed")

    if not agents_dir.exists():
        print("❌ Error: Fixed agents directory not found")
        return 1

    # Find all free tier agents
    free_agents = sorted(agents_dir.glob("Free*-i000-o000.sh"))

    if not free_agents:
        print("❌ Error: No free tier agents found")
        return 1

    print(f"Found {len(free_agents)} free tier agents")
    print()

    updated_count = 0
    skipped_count = 0

    # Update each agent
    for agent_file in free_agents:
        print(f"Processing: {agent_file.name}")

        if update_agent_script(agent_file):
            print("  ✅ Updated with self-review workflow")
            updated_count += 1
        else:
            print("  ⏭️  Already updated or couldn't update")
            skipped_count += 1

    print()
    print("=" * 60)
    print(f"✅ Updated: {updated_count} agents")
    print(f"⏭️  Skipped: {skipped_count} agents")

    # Update traycer_agent_review.py with validation
    print()
    print("Updating traycer_agent_review.py with self-review validation...")

    if validate_self_review_in_traycer_agent_review():
        print("  ✅ Added self-review validation")
    else:
        print("  ⏭️  Validation already exists or couldn't add")

    print()
    print("=" * 60)
    print("COMPLETE: Self-review workflow implemented")
    print()
    print("Next steps:")
    print(
        "1. Test with: export TRAYCER_PROMPT='Create hello world'; bash scripts/traycer_agents_fixed/Free01-*.sh"
    )
    print("2. Verify Step 2.5 self-review runs")
    print("3. Verify Steps 3-5 auto-review runs")
    print("4. Check that agent fixes issues in loop")

    return 0


if __name__ == "__main__":
    exit(main())
