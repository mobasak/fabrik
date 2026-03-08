#!/usr/bin/env python3
"""Enforce .env.example completeness.

When code references new environment variables via os.getenv() or os.environ,
those variables should be documented in .env.example.

Triggers on:
- Python files with os.getenv() or os.environ[] calls
- New env var names not in .env.example

Enforces (WARNING only):
- All os.getenv() variables documented in .env.example

Exit codes:
    0 - Pass (always - warnings only)
"""

import re
import subprocess
import sys
from pathlib import Path

ENV_VAR_PATTERNS = [
    r'os\.getenv\s*\(\s*["\']([A-Z][A-Z0-9_]*)["\']',
    r'os\.environ\s*\[\s*["\']([A-Z][A-Z0-9_]*)["\']',
    r'os\.environ\.get\s*\(\s*["\']([A-Z][A-Z0-9_]*)["\']',
    r"settings\.([A-Z][A-Z0-9_]*)",
]

EXCLUDED_VARS = {
    "PATH",
    "HOME",
    "USER",
    "SHELL",
    "PWD",
    "LANG",
    "TERM",
    "DISPLAY",
    "PYTHONPATH",
    "VIRTUAL_ENV",
}


def get_staged_files() -> list[str]:
    """Get list of staged files."""
    result = subprocess.run(
        ["git", "diff", "--name-only", "--cached", "HEAD"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        result = subprocess.run(
            ["git", "diff", "--name-only", "--cached"],
            capture_output=True,
            text=True,
        )
    return result.stdout.strip().split("\n") if result.stdout.strip() else []


def get_env_vars_from_diff(filepath: str) -> set[str]:
    """Extract new environment variable references from diff."""
    env_vars = set()
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", filepath],
            capture_output=True,
            text=True,
        )
        diff_content = result.stdout

        added_lines = [line for line in diff_content.split("\n") if line.startswith("+")]

        for line in added_lines:
            for pattern in ENV_VAR_PATTERNS:
                for match in re.finditer(pattern, line):
                    var_name = match.group(1)
                    if var_name not in EXCLUDED_VARS:
                        env_vars.add(var_name)
    except (OSError, subprocess.SubprocessError):
        pass
    return env_vars


def get_env_example_vars() -> set[str]:
    """Get all variable names from .env.example."""
    env_vars = set()
    env_example = Path(".env.example")

    if not env_example.exists():
        return env_vars

    try:
        content = env_example.read_text()
        pattern = r"^([A-Z][A-Z0-9_]*)="
        for match in re.finditer(pattern, content, re.MULTILINE):
            env_vars.add(match.group(1))
    except (OSError, UnicodeDecodeError):
        pass

    return env_vars


def main() -> int:
    """Check .env.example completeness."""
    staged_files = get_staged_files()

    if not staged_files or staged_files == [""]:
        return 0

    py_files = [f for f in staged_files if f.endswith(".py")]

    if not py_files:
        print("✅ .env.example check PASSED (no Python files)")
        return 0

    all_new_vars: set[str] = set()
    for py_file in py_files:
        new_vars = get_env_vars_from_diff(py_file)
        all_new_vars.update(new_vars)

    if not all_new_vars:
        print("✅ .env.example check PASSED (no new env vars)")
        return 0

    env_example_vars = get_env_example_vars()
    missing_vars = all_new_vars - env_example_vars

    if not missing_vars:
        print("✅ .env.example check PASSED (all vars documented)")
        return 0

    print("WARNING: New environment variables not in .env.example:")
    print("")
    for var in sorted(missing_vars):
        print(f"  - {var}")
    print("")
    print("Recommendation:")
    print("  Add these to .env.example with appropriate defaults/placeholders:")
    print("")
    for var in sorted(missing_vars):
        print(f"  {var}=")
    print("")
    print("(This is a WARNING - commit will proceed)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
