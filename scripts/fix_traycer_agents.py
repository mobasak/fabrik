#!/usr/bin/env python3
"""
Fix Traycer CLI Free Tier Agents

Fixes applied:
1. Replace shared task.md with unique timestamped files
2. Add session ID export for review continuity
3. Add optional auto-review hook integration

Usage:
    python scripts/fix_traycer_agents.py --input ~/.traycer/cli-agents --output scripts/traycer_agents_fixed
"""

import re
from pathlib import Path
from typing import Any


def extract_agent_metadata(content: str) -> dict[str, Any]:
    """Extract agent metadata from shell script."""
    metadata = {}

    # Extract model
    if match := re.search(r"--model\s+(\S+)", content):
        metadata["model"] = match.group(1)

    # Extract variant
    if match := re.search(r"--variant\s+(\S+)", content):
        metadata["variant"] = match.group(1)

    # Extract agent role
    if match := re.search(r"--agent\s+(\S+)", content):
        metadata["role"] = match.group(1)

    # Extract from filename
    # Format: Free01-minimax21-code-medium-i000-o000.sh
    if match := re.search(r"(Free\d+)-([^-]+)-([^-]+)-([^-]+)-i(\d+)-o(\d+)\.sh", content):
        metadata["tier"] = match.group(1)
        metadata["model_short"] = match.group(2)
        metadata["role_short"] = match.group(3)
        metadata["variant_short"] = match.group(4)
        metadata["input_cost"] = match.group(5)
        metadata["output_cost"] = match.group(6)

    return metadata


def apply_fixes(content: str, filename: str) -> str:
    """Apply all fixes to agent script."""

    # Extract metadata
    metadata = extract_agent_metadata(content)
    tier = metadata.get("tier", "Free01")

    # Fix 1: Replace shared task.md with unique timestamped file
    old_task_save = """# Save task context for Step 4 (kilo_code_review.py needs it)
mkdir -p .droid/review-context
printf '%s\\n' "$PROMPT" > .droid/review-context/task.md"""

    new_task_save = """# FIXED: Use unique timestamped task file instead of shared task.md
TIMESTAMP=$(date +%Y-%m-%d-%H%M%S)
TASK_SLUG="${TRAYCER_TASK_ID:-task}"
TASK_FILE=".droid/review-context/${TIMESTAMP}-${TASK_SLUG}.md"

mkdir -p .droid/review-context
printf '%s\\n' "$PROMPT" > "$TASK_FILE"

# Export for Step 4 (kilo_code_review.py)
export TRAYCER_TASK_FILE="$TASK_FILE"

[ "$KILO_DEBUG" = "1" ] && echo "[DEBUG] Task saved to: $TASK_FILE" >&2"""

    content = content.replace(old_task_save, new_task_save)

    # Fix 2: Add session ID export (before kilo run command)
    kilo_run_pattern = r"(# Run Kilo agent with timeout)"
    session_id_export = f"""# Generate session ID for this execution
SESSION_ID="ses_{tier.lower()}_${{TIMESTAMP}}_$$"
export TRAYCER_SESSION_ID="$SESSION_ID"

[ "$KILO_DEBUG" = "1" ] && echo "[DEBUG] Session ID: $SESSION_ID" >&2

\\1"""

    content = re.sub(kilo_run_pattern, session_id_export, content)

    # Fix 3: Update cost tracking to include session_id
    old_cost_log = r'"task_id":"$TRAYCER_TASK_ID","exit_code"'
    new_cost_log = '"task_id":"$TRAYCER_TASK_ID","session_id":"$SESSION_ID","exit_code"'

    content = content.replace(old_cost_log, new_cost_log)

    # Fix 4: Add session ID to debug summary
    old_debug = """if [ "$KILO_DEBUG" = "1" ]; then
    echo "[DEBUG] Exit code: $EXIT_CODE" >&2
    echo "[DEBUG] Duration: $DURATION seconds" >&2
fi"""

    new_debug = """if [ "$KILO_DEBUG" = "1" ]; then
    echo "[DEBUG] Exit code: $EXIT_CODE" >&2
    echo "[DEBUG] Duration: $DURATION seconds" >&2
    echo "[DEBUG] Task file: $TASK_FILE" >&2
    echo "[DEBUG] Session ID: $SESSION_ID" >&2
fi"""

    content = content.replace(old_debug, new_debug)

    # Fix 5: Add auto-review hook (before final exit)
    old_exit = """# Capture exit code and exit explicitly
exit $EXIT_CODE"""

    new_exit = """# OPTIONAL: Auto-review hook (if TRAYCER_AUTO_REVIEW=1)
if [ "$TRAYCER_AUTO_REVIEW" = "1" ] && [ $EXIT_CODE -eq 0 ]; then
    [ "$KILO_DEBUG" = "1" ] && echo "[DEBUG] Running auto-review workflow..." >&2

    # Detect changed files
    CHANGED_FILES=$(git diff --name-only --diff-filter=ACMR HEAD 2>/dev/null | tr '\\n' ' ')

    if [ -n "$CHANGED_FILES" ]; then
        python /opt/fabrik/scripts/traycer_agent_review.py \\
            --task "$PROMPT" \\
            --files $CHANGED_FILES \\
            --self-review "Agent completed implementation" \\
            --session-id "$SESSION_ID" \\
            --output json

        REVIEW_EXIT=$?
        [ "$KILO_DEBUG" = "1" ] && echo "[DEBUG] Auto-review exit code: $REVIEW_EXIT" >&2

        # Override exit code if review failed
        if [ $REVIEW_EXIT -ne 0 ]; then
            EXIT_CODE=$REVIEW_EXIT
        fi
    else
        [ "$KILO_DEBUG" = "1" ] && echo "[DEBUG] No changed files, skipping auto-review" >&2
    fi
fi

exit $EXIT_CODE"""

    content = content.replace(old_exit, new_exit)

    # Fix 6: Update header to indicate fixes applied
    header_pattern = r"(# Kilo Code Agent - Free Tier #\d+)"
    new_header = "\\1 (FIXED)\n# ════════════════════════════════════════════════════════════════════════════\n#\n# FIXES APPLIED (2026-03-06):\n#   - Use unique timestamped task files instead of shared task.md\n#   - Export session ID for review continuity\n#   - Optional auto-review hook integration\n#"

    content = re.sub(header_pattern, new_header, content)

    return content


def main() -> None:
    """Fix all free tier agents."""

    input_dir = Path.home() / ".traycer" / "cli-agents"
    output_dir = Path("/opt/fabrik/scripts/traycer_agents_fixed")

    output_dir.mkdir(parents=True, exist_ok=True)

    # Find all free tier agents (i000-o000)
    free_agents = list(input_dir.glob("Free*-i000-o000.sh"))

    print(f"Found {len(free_agents)} free tier agents")

    fixed_count = 0

    for agent_file in sorted(free_agents):
        print(f"Processing: {agent_file.name}")

        # Read original
        content = agent_file.read_text()

        # Apply fixes
        fixed_content = apply_fixes(content, agent_file.name)

        # Write fixed version
        output_file = output_dir / agent_file.name
        output_file.write_text(fixed_content)

        # Make executable
        output_file.chmod(0o755)

        fixed_count += 1
        print(f"  ✓ Fixed → {output_file}")

    print(f"\n✅ Fixed {fixed_count} agents")
    print(f"Output directory: {output_dir}")

    # Create README
    readme = output_dir / "README.md"
    readme.write_text(f"""# Fixed Traycer CLI Agents (Free Tier)

**Date:** 2026-03-06
**Fixed:** {fixed_count} agents

## Fixes Applied

1. **Unique Task Files** - Replace shared `task.md` with timestamped files
   - Format: `.droid/review-context/YYYY-MM-DD-HHMMSS-<task-id>.md`
   - Prevents concurrent execution conflicts
   - Preserves historical context

2. **Session ID Export** - Generate and export session ID
   - Format: `ses_<tier>_<timestamp>_<pid>`
   - Enables review continuity with `--session continue`
   - Tracked in cost logs

3. **Auto-Review Hook** - Optional workflow enforcement
   - Enabled via `TRAYCER_AUTO_REVIEW=1`
   - Runs Steps 3-5 automatically after coding
   - Prevents uncommitted code with issues

## Usage

Replace original agents with fixed versions:

```bash
cp scripts/traycer_agents_fixed/*.sh ~/.traycer/cli-agents/
```

Or use fixed versions directly:

```bash
export TRAYCER_PROMPT="Your task here"
export TRAYCER_TASK_ID="task-123"
export TRAYCER_AUTO_REVIEW=1  # Optional: enable auto-review

/opt/fabrik/scripts/traycer_agents_fixed/Free01-minimax21-code-medium-i000-o000.sh
```

## Testing

See `/opt/fabrik/tests/test_free_tier_agents.md` for test scenarios.
""")

    print(f"\n📄 README created: {readme}")


if __name__ == "__main__":
    main()
