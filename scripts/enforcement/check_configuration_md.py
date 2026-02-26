#!/usr/bin/env python3
"""Enforce CONFIGURATION.md updates when env vars change.

CONFIGURATION.md is the complete config reference - must document all env vars.
"""

import re
import sys
from pathlib import Path


def check_configuration_md(repo_root: Path, changed_files: list[str]) -> tuple[bool, list[str]]:
    """Check if CONFIGURATION.md is in sync with .env.example."""
    config_path = repo_root / "docs" / "CONFIGURATION.md"
    env_example_path = repo_root / ".env.example"
    errors = []

    if not config_path.exists():
        errors.append("ERROR: docs/CONFIGURATION.md missing")
        return False, errors

    if not env_example_path.exists():
        return True, []  # No .env.example = nothing to check

    # If .env.example changed, verify CONFIGURATION.md documents the vars
    if ".env.example" in changed_files or "docs/CONFIGURATION.md" in changed_files:
        example_content = env_example_path.read_text()
        config_content = config_path.read_text()

        # Extract variable names from .env.example
        example_vars = set(re.findall(r"^([A-Z_][A-Z0-9_]*)=", example_content, re.MULTILINE))

        # Check if each var is documented in CONFIGURATION.md
        undocumented = []
        for var in sorted(example_vars):
            # Look for the var wrapped in backticks (markdown code)
            if f"`{var}`" not in config_content:
                undocumented.append(var)

        if undocumented:
            errors.append(
                f"ERROR: These env vars are in .env.example but not documented in CONFIGURATION.md:\n"
                f"{', '.join(undocumented)}\n\n"
                f"Add them to the Environment Variables section with:\n"
                f"| Variable | Required | Default | Description |\n"
                f"|----------|----------|---------|-------------|\n"
                f"| `{undocumented[0]}` | ... | ... | ... |"
            )
            return False, errors

    return True, errors


def main() -> int:
    """Run CONFIGURATION.md check."""
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

    success, messages = check_configuration_md(repo_root, changed_files)

    for msg in messages:
        print(msg)

    if not success:
        print("\n❌ CONFIGURATION.md check FAILED")
        print("Fix: Document new env vars in docs/CONFIGURATION.md")
        return 1

    print("✅ CONFIGURATION.md check PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
