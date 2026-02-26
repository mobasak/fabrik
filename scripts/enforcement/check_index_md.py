#!/usr/bin/env python3
"""Enforce INDEX.md existence and updates.

INDEX.md is the master file index - AI agents must read it first.
Every new file should be documented in INDEX.md.
"""

import sys
from pathlib import Path


def check_index_md(repo_root: Path) -> tuple[bool, list[str]]:
    """Check if INDEX.md exists and is up to date."""
    index_path = repo_root / "INDEX.md"
    errors = []

    # Check existence
    if not index_path.exists():
        errors.append("ERROR: INDEX.md missing - create from PROJECT_INDEX_TEMPLATE.md")
        return False, errors

    content = index_path.read_text()

    # Check if it has the required sections
    required_sections = [
        "# Project File Index",
        "## Root Files",
        "## docs/ Files",
        "## Project Structure",
        "## Enforcement Gates",
        "## Update Protocol for AI Agents",
    ]

    missing_sections = []
    for section in required_sections:
        if section not in content:
            missing_sections.append(section)

    if missing_sections:
        errors.append(f"ERROR: INDEX.md missing required sections: {', '.join(missing_sections)}")
        return False, errors

    # Check if commonly added files are documented
    root_files = [
        "README.md",
        "CHANGELOG.md",
        ".env.example",
        "requirements.txt",
        "pyproject.toml",
        "Dockerfile",
        "compose.yaml",
    ]

    undocumented = []
    for file in root_files:
        file_path = repo_root / file
        if file_path.exists() and f"**{file}**" not in content:
            undocumented.append(file)

    if undocumented:
        errors.append(
            f"WARNING: These files exist but not documented in INDEX.md: {', '.join(undocumented)}"
        )
        # Warning only - don't fail

    return True, errors


def main() -> int:
    """Run INDEX.md check."""
    repo_root = Path.cwd()

    success, messages = check_index_md(repo_root)

    for msg in messages:
        print(msg)

    if not success:
        print("\n❌ INDEX.md check FAILED")
        print("Fix: Update INDEX.md to document all project files")
        return 1

    if messages:
        print("\n⚠️  INDEX.md has warnings (non-blocking)")
        return 0

    print("✅ INDEX.md check PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
