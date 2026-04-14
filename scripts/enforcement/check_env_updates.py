#!/usr/bin/env python3
"""Enforce .env file population when secrets are mentioned.

When AI receives secrets/API keys from user, it must write to .env file.
This check verifies that pattern is followed.
"""

import re
import sys
from pathlib import Path


def check_env_updates(repo_root: Path, changed_files: list[str]) -> tuple[bool, list[str]]:
    """Check if .env needs updating based on .env.example changes."""
    env_example_path = repo_root / ".env.example"
    env_path = repo_root / ".env"
    errors = []

    if not env_example_path.exists():
        return True, []  # No .env.example = nothing to check

    # If .env.example was updated, check if .env exists
    if ".env.example" in changed_files and not env_path.exists():
        errors.append(
            "WARNING: .env.example updated but .env doesn't exist.\n"
            "If user provided secrets, AI should create .env file with actual values."
        )
        # Warning only - don't fail (user might provide secrets later)

    # Check if .env.example has new variables that aren't in .env
    if env_path.exists():
        example_content = env_example_path.read_text()
        env_content = env_path.read_text()

        # Extract variable names from .env.example
        example_vars = set(re.findall(r"^([A-Z_][A-Z0-9_]*)=", example_content, re.MULTILINE))
        env_vars = set(re.findall(r"^([A-Z_][A-Z0-9_]*)=", env_content, re.MULTILINE))

        missing_in_env = example_vars - env_vars
        if missing_in_env:
            errors.append(
                f"WARNING: These variables are in .env.example but not in .env:\n"
                f"{', '.join(sorted(missing_in_env))}\n"
                "If user provided values for these, add them to .env"
            )
            # Warning only - user might not have provided all secrets yet

    return True, errors  # Always pass - warnings only


def main() -> int:
    """Run .env updates check."""
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

    success, messages = check_env_updates(repo_root, changed_files)

    for msg in messages:
        print(msg)

    if messages:
        print("\n⚠️  .env update reminders (non-blocking)")
        return 0

    print("✅ .env check PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
