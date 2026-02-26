#!/usr/bin/env python3
"""Enforce README.md updates when structure changes.

README.md is the primary entry point - must document:
- Features
- Quick start
- Tech stack
- Project structure
"""

import sys
from pathlib import Path


def check_readme_md(repo_root: Path, changed_files: list[str]) -> tuple[bool, list[str]]:
    """Check if README.md is up to date."""
    readme_path = repo_root / "README.md"
    errors = []

    if not readme_path.exists():
        errors.append("ERROR: README.md missing")
        return False, errors

    content = readme_path.read_text()

    # Required sections
    required_sections = [
        "# ",  # Title
        "## Overview",
        "## Quick Start",
        "## Documentation",
    ]

    missing_sections = []
    for section in required_sections:
        if section not in content:
            missing_sections.append(section)

    if missing_sections:
        errors.append(f"ERROR: README.md missing required sections: {', '.join(missing_sections)}")
        return False, errors

    # Check if Dockerfile changed but tech stack not mentioned
    if "Dockerfile" in changed_files and "Tech Stack" not in content and "## Stack" not in content:
        errors.append(
            "WARNING: Dockerfile changed but README.md has no Tech Stack section.\n"
            "Consider adding ## Tech Stack section to document technologies."
        )

    # Check if new source files added but structure not documented
    src_changed = any(f.startswith("src/") for f in changed_files)
    if src_changed and "Project Structure" not in content and "## Structure" not in content:
        errors.append(
            "WARNING: Source files changed but README.md has no structure documentation.\n"
            "Consider adding ## Project Structure section."
        )

    return True, errors


def main() -> int:
    """Run README.md check."""
    repo_root = Path.cwd()

    # Get changed files from git
    import subprocess

    result = subprocess.run(
        ["git", "diff", "--name-only", "--cached", "HEAD"],
        capture_output=True,
        text=True,
        cwd=repo_root,
    )
    # Handle repos without HEAD (initial commit)
    if result.returncode != 0:
        result = subprocess.run(
            ["git", "diff", "--name-only", "--cached"],
            capture_output=True,
            text=True,
            cwd=repo_root,
        )
    changed_files = result.stdout.strip().split("\n") if result.stdout.strip() else []

    success, messages = check_readme_md(repo_root, changed_files)

    for msg in messages:
        print(msg)

    if not success:
        print("\n❌ README.md check FAILED")
        print("Fix: Update README.md with required sections")
        return 1

    if messages:
        print("\n⚠️  README.md has warnings (non-blocking)")
        return 0

    print("✅ README.md check PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
