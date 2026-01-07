#!/usr/bin/env python3
"""
Check that CHANGELOG.md is updated when code files change.

This pre-commit hook ensures that any commit touching code files
also includes an update to CHANGELOG.md.

Exit codes:
    0 - CHANGELOG.md is updated or no code files changed
    1 - Code files changed but CHANGELOG.md not updated
"""

import subprocess
import sys

# File patterns that require CHANGELOG.md update
CODE_PATTERNS = [
    "*.py",
    "*.ts",
    "*.tsx",
    "*.js",
    "*.jsx",
    "*.sh",
    "Dockerfile",
    "compose.yaml",
    "compose.yml",
]

# Files/patterns to exclude (docs, configs, etc.)
EXCLUDE_PATTERNS = [
    "tests/",
    "*.md",
    "*.yaml",
    "*.yml",
    "*.json",
    "*.toml",
    ".pre-commit-config.yaml",
]


def get_staged_files() -> list[str]:
    """Get list of staged files."""
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        capture_output=True,
        text=True,
    )
    return result.stdout.strip().split("\n") if result.stdout.strip() else []


def is_code_file(filepath: str) -> bool:
    """Check if file is a code file that requires CHANGELOG update."""
    # Check exclusions first
    for pattern in EXCLUDE_PATTERNS:
        if pattern.endswith("/"):
            if filepath.startswith(pattern) or f"/{pattern}" in filepath:
                return False
        elif pattern.startswith("*."):
            ext = pattern[1:]  # e.g., ".md"
            if filepath.endswith(ext):
                return False
        elif filepath == pattern:
            return False

    # Check if it matches code patterns
    for pattern in CODE_PATTERNS:
        if pattern.startswith("*."):
            ext = pattern[1:]  # e.g., ".py"
            if filepath.endswith(ext):
                return True
        elif filepath.endswith(pattern) or filepath == pattern:
            return True

    return False


def main() -> int:
    """Check CHANGELOG.md is updated when code changes."""
    staged_files = get_staged_files()

    if not staged_files:
        return 0

    # Check if any code files are staged
    code_files = [f for f in staged_files if is_code_file(f)]

    if not code_files:
        # No code files changed, no CHANGELOG update required
        return 0

    # Check if CHANGELOG.md is also staged
    if "CHANGELOG.md" in staged_files:
        return 0

    # Code files changed but CHANGELOG.md not updated
    print("ERROR: CHANGELOG.md must be updated when code files change.")
    print("")
    print("Code files in this commit:")
    for f in code_files[:10]:  # Show first 10
        print(f"  - {f}")
    if len(code_files) > 10:
        print(f"  ... and {len(code_files) - 10} more")
    print("")
    print("Add an entry to CHANGELOG.md under ## [Unreleased]:")
    print("")
    print("  ### Added/Changed/Fixed - <Brief Title> (YYYY-MM-DD)")
    print("")
    print("  **What:** One-line description")
    print("")
    print("  **Files:**")
    print("  - `path/to/file.py` - what changed")
    print("")
    print("To bypass (not recommended): git commit --no-verify")

    return 1


if __name__ == "__main__":
    sys.exit(main())
