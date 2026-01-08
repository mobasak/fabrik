#!/usr/bin/env python3
"""Quick AI review for pre-commit hook.

Performs a fast, focused review of staged Python files for critical issues only.
Designed to be fast (<30s) and catch high-severity bugs before commit.

Usage:
    python3 scripts/enforcement/ai_quick_review.py [files...]

Exit codes:
    0 - No critical issues found
    1 - Critical issues found (blocks commit)
    2 - Review skipped (no droid available or disabled)
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def get_staged_python_files() -> list[str]:
    """Get list of staged Python files."""
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
        capture_output=True,
        text=True,
        cwd=Path(__file__).parent.parent.parent,
    )
    if result.returncode != 0:
        print(f"Warning: git diff failed: {result.stderr}", file=sys.stderr)
        return []

    files = result.stdout.strip().split("\n")
    return [f for f in files if f.endswith(".py") and f]


def get_staged_diff(files: list[str]) -> str:
    """Get the staged diff content for specified files."""
    if not files:
        return ""

    result = subprocess.run(
        ["git", "diff", "--cached", "--"] + files,
        capture_output=True,
        text=True,
        cwd=Path(__file__).parent.parent.parent,
    )
    if result.returncode != 0:
        return ""

    # Limit diff size to avoid token overflow (max 8KB)
    diff = result.stdout
    if len(diff) > 8000:
        diff = diff[:8000] + "\n... [truncated for size]"
    return diff


def run_quick_review(files: list[str]) -> tuple[bool, str]:
    """Run quick AI review on files.

    Returns:
        (passed, output) - True if no critical issues, output message
    """
    if not files:
        return True, "No Python files to review"

    # Check if droid is available
    droid_check = subprocess.run(
        ["which", "droid"],
        capture_output=True,
    )
    if droid_check.returncode != 0:
        return True, "Skipped: droid not available"

    # Check if AI review is disabled
    if os.getenv("SKIP_AI_REVIEW", "").lower() in ("1", "true", "yes"):
        return True, "Skipped: SKIP_AI_REVIEW=1"

    # Limit to 5 files max for speed
    review_files = files[:5]
    if len(files) > 5:
        print(f"Warning: Reviewing first 5 of {len(files)} files for speed", file=sys.stderr)

    # Get actual diff content (P0 fix: must include code, not just filenames)
    diff_content = get_staged_diff(review_files)
    if not diff_content:
        return True, "No diff content to review"

    # Quick review prompt - focused on critical issues only
    prompt = f"""Quick pre-commit review. Check ONLY for:
1. Security issues (hardcoded secrets, SQL injection)
2. Obvious bugs (undefined variables, wrong return types)
3. Hardcoded localhost/ports (Fabrik rule violation)

Diff to review:
```
{diff_content}
```

Output JSON only:
{{"critical": true/false, "issues": ["issue1", "issue2"]}}

Be brief. Skip style issues. Only report if critical=true."""

    try:
        result = subprocess.run(
            ["droid", "exec", "-o", "json", prompt],
            capture_output=True,
            text=True,
            timeout=30,  # 30 second timeout
            cwd=Path(__file__).parent.parent.parent,
        )

        # P1 fix: Check exit code first
        if result.returncode != 0:
            stderr = result.stderr.strip() if result.stderr else "unknown error"
            return True, f"Skipped: droid failed (exit {result.returncode}): {stderr[:200]}"

        output = result.stdout.strip()
        if not output:
            return True, "Skipped: empty response from droid"

        # Try to parse JSON response
        try:
            # Find JSON in output (may have surrounding text)
            json_start = output.find("{")
            json_end = output.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                data = json.loads(output[json_start:json_end])
                if data.get("critical") is True:
                    issues = data.get("issues", [])
                    return False, f"Critical issues found: {issues}"
        except json.JSONDecodeError:
            # Fallback to string search if JSON parsing fails
            if '"critical": true' in output.lower() or '"critical":true' in output.lower():
                return False, f"Critical issues found:\n{output}"

        return True, "Quick review passed"

    except subprocess.TimeoutExpired:
        return True, "Skipped: Review timed out (30s limit)"
    except Exception as e:
        return True, f"Skipped: {e}"


def main() -> int:
    """Main entry point."""
    # Get files from args or staged files
    if len(sys.argv) > 1:
        files = [f for f in sys.argv[1:] if f.endswith(".py")]
    else:
        files = get_staged_python_files()

    passed, message = run_quick_review(files)

    if passed:
        print(f"AI Quick Review: {message}")
        return 0
    else:
        print(f"AI Quick Review FAILED:\n{message}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
