#!/usr/bin/env python3
"""Quick AI review for pre-commit hook.

Performs a focused review of staged code files for critical issues only.
Uses rund/runc for long command monitoring (no arbitrary timeouts).

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
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
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


def run_quick_review(files: list[str]) -> tuple[bool, str]:
    """Run quick AI review on files.

    Returns:
        (passed, output) - True if no critical issues, output message
    """
    if not files:
        return True, "No code files to review"

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

    # Use rund for detached execution with monitoring (no arbitrary timeouts)
    project_root = Path(__file__).parent.parent.parent
    rund_script = project_root / "scripts" / "rund"
    runc_script = project_root / "scripts" / "runc"

    if not rund_script.exists():
        # Fallback to direct execution if rund not available
        return _run_direct(prompt, project_root)

    try:
        # Start detached droid exec
        start_result = subprocess.run(
            [str(rund_script), "droid", "exec", "-o", "json", prompt],
            capture_output=True,
            text=True,
            cwd=project_root,
        )

        # Parse JOB path from output
        job_path = None
        for line in start_result.stdout.split("\n"):
            if line.startswith("JOB="):
                job_path = line.split("=", 1)[1].strip()
                break

        if not job_path:
            return True, "Skipped: Failed to start droid via rund"

        # Monitor with runc until complete (check every 2s, max 90s for stuck detection)
        import time

        max_checks = 45  # 45 * 2s = 90s max
        last_log_size = 0
        stuck_count = 0

        for _ in range(max_checks):
            time.sleep(2)

            check_result = subprocess.run(
                [str(runc_script), job_path],
                capture_output=True,
                text=True,
                cwd=project_root,
            )

            output = check_result.stdout

            # Check if done
            if "DONE" in output or "exit" in output.lower():
                # Read the log file for results
                log_file = Path(job_path + ".log")
                if log_file.exists():
                    log_content = log_file.read_text()
                    return _parse_review_result(log_content)
                return True, "Quick review passed"

            # Stuck detection: log size unchanged for 3 checks (6s)
            if "LOG=" in output:
                try:
                    log_size = int(output.split("LOG=")[1].split()[0])
                    if log_size == last_log_size:
                        stuck_count += 1
                    else:
                        stuck_count = 0
                    last_log_size = log_size
                except (ValueError, IndexError):
                    pass

            if stuck_count >= 3:
                # Kill stuck process
                subprocess.run(
                    [str(project_root / "scripts" / "runk"), job_path],
                    capture_output=True,
                    cwd=project_root,
                )
                return True, "Skipped: Review process stuck, killed"

        return True, "Skipped: Review did not complete in time"

    except Exception as e:
        return True, f"Skipped: {e}"


def _run_direct(prompt: str, cwd: Path) -> tuple[bool, str]:
    """Fallback direct execution without rund."""
    try:
        result = subprocess.run(
            ["droid", "exec", "-o", "json", prompt],
            capture_output=True,
            text=True,
            cwd=cwd,
        )
        if result.returncode != 0:
            return True, f"Skipped: droid failed (exit {result.returncode})"
        return _parse_review_result(result.stdout)
    except Exception as e:
        return True, f"Skipped: {e}"


def _parse_review_result(output: str) -> tuple[bool, str]:
    """Parse droid output for critical issues."""
    output = output.strip()
    if not output:
        return True, "Skipped: empty response"

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
    """Main entry point."""
    # Get files from args or staged files
    if len(sys.argv) > 1:
        files = [f for f in sys.argv[1:] if any(f.endswith(ext) for ext in CODE_EXTENSIONS)]
    else:
        files = get_staged_code_files()

    passed, message = run_quick_review(files)

    if passed:
        print(f"AI Quick Review: {message}")
        return 0
    else:
        print(f"AI Quick Review FAILED:\n{message}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
