#!/usr/bin/env python3
"""
Smart CHANGELOG.md enforcement for meaningful code changes.

Only requires CHANGELOG.md update for:
- Production code in src/, scripts/ (not tests/)
- New files added
- Changes exceeding MIN_LINES_THRESHOLD

Skips:
- Test files only
- Documentation only
- Config files only
- Small changes (< MIN_LINES_THRESHOLD lines)

Also validates CHANGELOG.md entry is not empty/placeholder.

Exit codes:
    0 - Pass (CHANGELOG updated or not required)
    1 - Fail (significant code change without CHANGELOG)
"""

import os
import re
import subprocess
import sys
from pathlib import Path

# Minimum lines changed to require CHANGELOG (skip tiny fixes)
MIN_LINES_THRESHOLD = 10

# Directories that require CHANGELOG when modified
SIGNIFICANT_DIRS = [
    "src/",
    "scripts/",
    "templates/",
    ".factory/",
    ".github/",
]

# Patterns to always skip (never require CHANGELOG)
SKIP_PATTERNS = [
    "tests/",
    "test_",
    "_test.py",
    ".test.ts",
    ".spec.ts",
    "__pycache__/",
    ".pytest_cache/",
    "node_modules/",
    ".venv/",
]

# File extensions that are significant code
CODE_EXTENSIONS = {".py", ".ts", ".tsx", ".js", ".jsx", ".sh"}

# Files that are always significant (Docker, compose)
SIGNIFICANT_FILES = {"Dockerfile", "compose.yaml", "compose.yml"}


def get_staged_files() -> list[str]:
    """Get list of staged files."""
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        capture_output=True,
        text=True,
    )
    return result.stdout.strip().split("\n") if result.stdout.strip() else []


def get_staged_diff_stats() -> int:
    """Get total lines added/removed in staged changes."""
    result = subprocess.run(
        ["git", "diff", "--cached", "--numstat"],
        capture_output=True,
        text=True,
    )
    total_lines = 0
    for line in result.stdout.strip().split("\n"):
        if line and not line.startswith("-"):
            parts = line.split("\t")
            if len(parts) >= 2:
                try:
                    added = int(parts[0]) if parts[0] != "-" else 0
                    removed = int(parts[1]) if parts[1] != "-" else 0
                    total_lines += added + removed
                except ValueError:
                    pass
    return total_lines


def should_skip(filepath: str) -> bool:
    """Check if file should be skipped (tests, cache, etc.)."""
    return any(pattern in filepath for pattern in SKIP_PATTERNS)


def is_significant_code(filepath: str) -> bool:
    """Check if file is significant production code."""
    if should_skip(filepath):
        return False

    # Check if in significant directory
    in_significant_dir = any(filepath.startswith(d) for d in SIGNIFICANT_DIRS)

    # Check file extension
    ext = Path(filepath).suffix
    is_code = ext in CODE_EXTENSIONS

    # Check if significant file (Dockerfile, compose)
    filename = Path(filepath).name
    is_significant_file = filename in SIGNIFICANT_FILES

    return (in_significant_dir and is_code) or is_significant_file


def is_new_file(filepath: str) -> bool:
    """Check if file is newly added (not modified)."""
    result = subprocess.run(
        ["git", "diff", "--cached", "--diff-filter=A", "--name-only"],
        capture_output=True,
        text=True,
    )
    return filepath in result.stdout.strip().split("\n")


def check_changelog_quality() -> bool:
    """Check that CHANGELOG.md has a real entry, not just placeholder."""
    changelog_path = Path("CHANGELOG.md")
    if not changelog_path.exists():
        return False

    content = changelog_path.read_text()

    # Check for [Unreleased] section with actual content
    unreleased_match = re.search(r"## \[Unreleased\]\s*\n(.*?)(?=\n## \[|$)", content, re.DOTALL)
    if not unreleased_match:
        return False

    unreleased_content = unreleased_match.group(1).strip()

    # Check it's not empty or just placeholder
    if not unreleased_content:
        return False

    # Check for actual entry (### Added/Changed/Fixed/Removed/Security/Deprecated)
    if not re.search(
        r"###\s+(Added|Changed|Fixed|Removed|Security|Deprecated)", unreleased_content
    ):
        print("WARNING: CHANGELOG.md [Unreleased] section has no ### entry")
        return False

    # Check for placeholder text
    placeholders = ["<Brief Title>", "<description>", "TODO", "FIXME", "xxx", "..."]
    for placeholder in placeholders:
        if placeholder.lower() in unreleased_content.lower():
            print(f"WARNING: CHANGELOG.md contains placeholder: {placeholder}")
            return False

    return True


def main() -> int:
    """Smart CHANGELOG.md check for meaningful changes."""
    staged_files = get_staged_files()

    if not staged_files or staged_files == [""]:
        return 0

    # Filter to significant code files
    significant_files = [f for f in staged_files if is_significant_code(f)]

    if not significant_files:
        # No significant code files, skip CHANGELOG check
        return 0

    # Check if any are new files (always require CHANGELOG for new files)
    new_files = [f for f in significant_files if is_new_file(f)]

    # Check total diff size
    total_lines = get_staged_diff_stats()

    # Skip if small change AND no new files
    if total_lines < MIN_LINES_THRESHOLD and not new_files:
        return 0

    # Check if CHANGELOG.md is staged
    if "CHANGELOG.md" not in staged_files:
        print("ERROR: CHANGELOG.md must be updated for significant code changes.")
        print("")
        print(f"Significant files ({len(significant_files)}):")
        for f in significant_files[:5]:
            marker = " (NEW)" if f in new_files else ""
            print(f"  - {f}{marker}")
        if len(significant_files) > 5:
            print(f"  ... and {len(significant_files) - 5} more")
        print("")
        print(f"Total lines changed: {total_lines}")
        print(f"Threshold: {MIN_LINES_THRESHOLD} lines or new files")
        print("")
        print("Add entry to CHANGELOG.md under ## [Unreleased]:")
        print("  ### Added/Changed/Fixed - <Title> (YYYY-MM-DD)")
        print("  **What:** Description")
        print("  **Files:** - `path` - what changed")
        print("")
        print("To bypass: git commit --no-verify")
        return 1

    # CHANGELOG.md is staged, verify quality
    if not check_changelog_quality():
        print("ERROR: CHANGELOG.md entry appears empty or contains placeholders.")
        print("Please add a real entry under ## [Unreleased]")
        return 1

    return 0


if __name__ == "__main__":
    os.chdir(os.getenv("FABRIK_ROOT", "/opt/fabrik"))
    sys.exit(main())
