#!/usr/bin/env python3
"""Cheap Fix Agent - Uses Gemini 2.5 Flash for fast, low-cost MECHANICAL fixes only.

This script provides cheap automation for:
- Lint fixes that ruff can't auto-fix (e.g., unused imports, ambiguous names)
- Type hint fixes (e.g., missing return types, wrong annotations)
- Docstring additions for missing docstrings

SCOPE: Mechanical fixes ONLY. No logic changes, no TODO implementations, no refactoring.

Usage:
    # Fix a specific file
    python cheap_fix_agent.py fix myfile.py --issue "unused type:ignore comment"

    # Fix from ruff/mypy output
    python cheap_fix_agent.py fix-from-output --tool mypy

    # Batch fix all issues in a file
    python cheap_fix_agent.py batch myfile.py

Cost: ~$0.05-0.10 per fix (Gemini 2.5 Flash)
Speed: ~3-5 seconds per fix
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple

MODEL = "kilo/google/gemini-2.5-flash"
VARIANT = "minimal"


class Issue(NamedTuple):
    """Represents a code issue to fix."""

    file: str
    line: int
    code: str
    message: str


def run_kilo(prompt: str, timeout: int = 30) -> tuple[bool, str]:
    """Run Kilo with Gemini 2.5 Flash and return (success, output)."""
    cmd = [
        "kilo",
        "run",
        "--model",
        MODEL,
        "--agent",
        "code",
        "--variant",
        VARIANT,
        "--format",
        "default",
        prompt,
    ]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=Path.cwd(),
        )
        return result.returncode == 0, result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return False, "Timeout"
    except Exception as e:
        return False, str(e)


def parse_mypy_output(output: str) -> list[Issue]:
    """Parse mypy output into Issue objects."""
    issues = []
    # Pattern: file.py:line: error: message  [code]
    pattern = r"^(.+?):(\d+):\s*error:\s*(.+?)\s*\[(.+?)\]"
    for line in output.splitlines():
        match = re.match(pattern, line.strip())
        if match:
            issues.append(
                Issue(
                    file=match.group(1),
                    line=int(match.group(2)),
                    code=match.group(4),
                    message=match.group(3),
                )
            )
    return issues


def parse_ruff_output(output: str) -> list[Issue]:
    """Parse ruff output into Issue objects."""
    issues = []
    # Pattern: file.py:line:col: CODE message
    pattern = r"^(.+?):(\d+):\d+:\s*([A-Z]+\d+)\s+(.+)"
    for line in output.splitlines():
        match = re.match(pattern, line.strip())
        if match:
            issues.append(
                Issue(
                    file=match.group(1),
                    line=int(match.group(2)),
                    code=match.group(3),
                    message=match.group(4),
                )
            )
    return issues


def read_context(file_path: str, line: int, context: int = 5) -> str:
    """Read lines around the issue for context."""
    try:
        path = Path(file_path)
        if not path.exists():
            return ""
        lines = path.read_text().splitlines()
        start = max(0, line - context - 1)
        end = min(len(lines), line + context)
        numbered = [f"{i + 1}: {lines[i]}" for i in range(start, end)]
        return "\n".join(numbered)
    except Exception:
        return ""


def fix_issue(issue: Issue, dry_run: bool = False) -> tuple[bool, str]:
    """Fix a single issue using Gemini 2.5 Flash."""
    context = read_context(issue.file, issue.line)
    if not context:
        return False, f"Could not read {issue.file}"

    prompt = f"""Fix this {issue.code} error in {issue.file} at line {issue.line}.

Error: {issue.message}

Context (line numbers shown):
```
{context}
```

Rules:
1. Output ONLY the fixed line(s), nothing else
2. Keep the same indentation
3. Do not add explanations
4. If removing a line, output: DELETE_LINE {issue.line}
5. MECHANICAL FIXES ONLY - no logic changes, no refactoring, no TODO implementations
6. Only fix the specific error mentioned, nothing else"""

    if dry_run:
        print(f"Would fix: {issue.file}:{issue.line} [{issue.code}] {issue.message}")
        return True, "dry-run"

    success, output = run_kilo(prompt)
    if success:
        # Parse and apply the fix
        return apply_fix(issue, output)
    return False, output


def apply_fix(issue: Issue, kilo_output: str) -> tuple[bool, str]:
    """Apply the fix from Kilo output to the file."""
    # Extract code block if present
    code_match = re.search(r"```(?:python)?\n?(.*?)\n?```", kilo_output, re.DOTALL)
    if code_match:
        fix = code_match.group(1).strip()
    else:
        # Try to extract just the relevant line
        lines = [ln for ln in kilo_output.splitlines() if ln.strip() and not ln.startswith(">")]
        fix = "\n".join(lines[-3:]) if lines else ""

    if not fix:
        return False, "No fix extracted from output"

    # Check for DELETE_LINE instruction (case-insensitive, handle variations)
    fix_lower = fix.lower().strip()
    if fix_lower.startswith("delete_line") or fix_lower.startswith("# delete_line"):
        return delete_line(issue.file, issue.line)

    # Apply the fix
    try:
        path = Path(issue.file)
        lines = path.read_text().splitlines()

        # Replace the line(s)
        if 0 < issue.line <= len(lines):
            # Preserve original indentation
            original = lines[issue.line - 1]
            indent = len(original) - len(original.lstrip())
            fix_lines = fix.splitlines()
            if fix_lines:
                # Apply indentation to all fix lines
                indented_fixes = []
                for i, fl in enumerate(fix_lines):
                    if i == 0:
                        indented_fixes.append(" " * indent + fl.lstrip())
                    else:
                        # Preserve relative indentation for subsequent lines
                        indented_fixes.append(" " * indent + fl.lstrip())
                # Replace original line with all fix lines
                lines[issue.line - 1 : issue.line] = indented_fixes

            path.write_text("\n".join(lines) + "\n")
            return True, f"Fixed line {issue.line} ({len(fix_lines)} lines)"
        return False, f"Line {issue.line} out of range"
    except Exception as e:
        return False, str(e)


def delete_line(file_path: str, line_num: int) -> tuple[bool, str]:
    """Delete a line from a file."""
    try:
        path = Path(file_path)
        lines = path.read_text().splitlines()
        if 0 < line_num <= len(lines):
            del lines[line_num - 1]
            path.write_text("\n".join(lines) + "\n")
            return True, f"Deleted line {line_num}"
        return False, f"Line {line_num} out of range"
    except Exception as e:
        return False, str(e)


def fix_from_tool_output(tool: str, dry_run: bool = False) -> int:
    """Run a tool and fix all issues it reports."""
    if tool == "mypy":
        cmd = ["mypy", ".", "--no-error-summary"]
        parser = parse_mypy_output
    elif tool == "ruff":
        cmd = ["ruff", "check", ".", "--output-format=text"]
        parser = parse_ruff_output
    else:
        print(f"Unknown tool: {tool}")
        return 1

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=Path.cwd())
        issues = parser(result.stdout + result.stderr)
    except Exception as e:
        print(f"Error running {tool}: {e}")
        return 1

    if not issues:
        print(f"No issues found by {tool}")
        return 0

    print(f"Found {len(issues)} issues from {tool}")

    fixed = 0
    failed = 0
    for issue in issues[:10]:  # Limit to 10 issues per run
        success, msg = fix_issue(issue, dry_run)
        if success:
            print(f"  ✓ {issue.file}:{issue.line} [{issue.code}]")
            fixed += 1
        else:
            print(f"  ✗ {issue.file}:{issue.line} [{issue.code}]: {msg}")
            failed += 1

    print(f"\nFixed: {fixed}, Failed: {failed}")
    return 0 if failed == 0 else 1


def fix_single(file_path: str, issue_desc: str, line: int | None = None) -> int:
    """Fix a single described issue in a file."""
    if line is None:
        line = 1

    issue = Issue(file=file_path, line=line, code="manual", message=issue_desc)
    success, msg = fix_issue(issue)
    if success:
        print(f"✓ Fixed: {msg}")
        return 0
    else:
        print(f"✗ Failed: {msg}")
        return 1


def batch_fix(file_path: str, dry_run: bool = False) -> int:
    """Run mypy and ruff on a file and fix all issues."""
    path = Path(file_path)
    if not path.exists():
        print(f"File not found: {file_path}")
        return 1

    all_issues: list[Issue] = []

    # Get mypy issues
    try:
        result = subprocess.run(
            ["mypy", str(path), "--no-error-summary"],
            capture_output=True,
            text=True,
        )
        all_issues.extend(parse_mypy_output(result.stdout + result.stderr))
    except Exception:
        pass

    # Get ruff issues (unfixable only)
    try:
        result = subprocess.run(
            ["ruff", "check", str(path), "--output-format=text"],
            capture_output=True,
            text=True,
        )
        all_issues.extend(parse_ruff_output(result.stdout + result.stderr))
    except Exception:
        pass

    if not all_issues:
        print(f"No issues found in {file_path}")
        return 0

    print(f"Found {len(all_issues)} issues in {file_path}")

    fixed = 0
    failed = 0
    for issue in all_issues:
        success, msg = fix_issue(issue, dry_run)
        if success:
            print(f"  ✓ Line {issue.line} [{issue.code}]")
            fixed += 1
        else:
            print(f"  ✗ Line {issue.line} [{issue.code}]: {msg}")
            failed += 1

    print(f"\nFixed: {fixed}, Failed: {failed}")
    return 0 if failed == 0 else 1


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Cheap Fix Agent - Gemini 2.5 Flash")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # fix command
    fix_parser = subparsers.add_parser("fix", help="Fix a specific issue")
    fix_parser.add_argument("file", help="File to fix")
    fix_parser.add_argument("--issue", "-i", required=True, help="Issue description")
    fix_parser.add_argument("--line", "-l", type=int, help="Line number")

    # fix-from-output command
    ffo_parser = subparsers.add_parser("fix-from-output", help="Fix from tool output")
    ffo_parser.add_argument("--tool", "-t", choices=["mypy", "ruff"], required=True)
    ffo_parser.add_argument("--dry-run", "-n", action="store_true")

    # batch command
    batch_parser = subparsers.add_parser("batch", help="Batch fix a file")
    batch_parser.add_argument("file", help="File to fix")
    batch_parser.add_argument("--dry-run", "-n", action="store_true")

    # test command
    subparsers.add_parser("test", help="Test the agent")

    args = parser.parse_args()

    if args.command == "fix":
        return fix_single(args.file, args.issue, args.line)
    elif args.command == "fix-from-output":
        return fix_from_tool_output(args.tool, args.dry_run)
    elif args.command == "batch":
        return batch_fix(args.file, args.dry_run)
    elif args.command == "test":
        # Quick test
        success, output = run_kilo("Say 'OK' if you can hear me.")
        if success and "OK" in output:
            print("✓ Agent is working")
            return 0
        print(f"✗ Agent test failed: {output[:100]}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
