#!/usr/bin/env python3
"""Quick AI review for pre-commit hook.

Performs a focused review of staged code files for critical issues only.
Uses droid_core.py with ProcessMonitor for intelligent stuck detection.

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

# Add scripts directory to path for droid_core import
SCRIPTS_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))

from droid_core import TaskType, run_droid_exec  # noqa: E402

# Code file extensions to review
CODE_EXTENSIONS = {
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",  # Python, TypeScript, JavaScript
    ".sh",
    ".bash",  # Shell scripts
    ".yaml",
    ".yml",  # Config files
}


def get_staged_code_files() -> list[str]:
    """Get list of staged code files (all languages)."""
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
        capture_output=True,
        text=True,
        cwd=Path(__file__).parent.parent.parent,
    )
    if result.returncode != 0:
        print(f"Warning: git diff failed: {result.stderr}", file=sys.stderr)
        return []

    files = result.stdout.strip().split("\n")
    return [f for f in files if f and any(f.endswith(ext) for ext in CODE_EXTENSIONS)]


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


def run_quick_review(files: list[str]) -> tuple[bool | None, str]:
    """Run quick AI review on files using droid_core.py.

    Returns:
        (passed, output) - True=passed, False=failed, None=skipped
    """
    if not files:
        return None, "No code files to review"  # None = skip

    # Check if AI review is disabled
    if os.getenv("SKIP_AI_REVIEW", "").lower() in ("1", "true", "yes"):
        return None, "Skipped: SKIP_AI_REVIEW=1"  # None = skip

    # Limit to 5 files max for speed
    review_files = files[:5]
    if len(files) > 5:
        print(f"Warning: Reviewing first 5 of {len(files)} files", file=sys.stderr)

    # Get actual diff content
    diff_content = get_staged_diff(review_files)
    if not diff_content:
        return None, "No diff content to review"  # None = skip

    # Build prompt for precommit review
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
        # Use droid_core.py with PRECOMMIT task type
        # This leverages ProcessMonitor for stuck detection
        result = run_droid_exec(
            prompt=prompt,
            task_type=TaskType.PRECOMMIT,
            cwd=Path(__file__).parent.parent.parent,
        )

        if not result.success:
            return None, f"Skipped: {result.error}"  # None = skip

        return _parse_review_result(result.result)

    except Exception as e:
        return None, f"Skipped: {e}"  # None = skip


def _parse_review_result(output: str) -> tuple[bool | None, str]:
    """Parse droid output for critical issues."""
    output = output.strip() if output else ""
    if not output:
        return None, "Skipped: empty response"  # None = skip

    try:
        json_start = output.find("{")
        json_end = output.rfind("}") + 1
        if json_start >= 0 and json_end > json_start:
            data = json.loads(output[json_start:json_end])
            if data.get("critical") is True:
                issues = data.get("issues", [])
                return False, f"Critical issues found: {issues}"
    except json.JSONDecodeError:
        if '"critical": true' in output.lower() or '"critical":true' in output.lower():
            return False, f"Critical issues found:\n{output}"

    return True, "Quick review passed"


def main() -> int:
    """Main entry point.

    Returns:
        0 - No critical issues found OR skipped (allows commit)
        1 - Critical issues found (blocks commit)
    """
    # Get files from args or staged files
    if len(sys.argv) > 1:
        files = [f for f in sys.argv[1:] if any(f.endswith(ext) for ext in CODE_EXTENSIONS)]
    else:
        files = get_staged_code_files()

    passed, message = run_quick_review(files)

    if passed is None:
        # Skipped - allow commit to proceed
        print(f"AI Quick Review: {message}")
        return 0
    elif passed:
        print(f"AI Quick Review: {message}")
        return 0
    else:
        print(f"AI Quick Review FAILED:\n{message}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
