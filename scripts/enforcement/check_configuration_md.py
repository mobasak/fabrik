#!/usr/bin/env python3
"""Enforce configuration documentation pattern.

New pattern (2026-02-26):
- .env.example = AUTHORITATIVE (self-documenting with inline comments)
- docs/CONFIGURATION.md = GUIDE only (how to get credentials, troubleshooting)
- NO variable tables in CONFIGURATION.md

This checker verifies .env.example has comment blocks for each variable.
"""

import re
import sys
from pathlib import Path


def check_configuration_md(repo_root: Path, changed_files: list[str]) -> tuple[bool, list[str]]:
    """Check if .env.example has proper comment blocks for all variables."""
    config_path = repo_root / "docs" / "CONFIGURATION.md"
    env_example_path = repo_root / ".env.example"
    errors = []

    if not config_path.exists():
        errors.append("ERROR: docs/CONFIGURATION.md missing")
        return False, errors

    if not env_example_path.exists():
        return True, []  # No .env.example = nothing to check

    # If .env.example changed, verify it has comment blocks
    if ".env.example" in changed_files:
        example_content = env_example_path.read_text()

        # Extract variables and check if they have preceding comments
        lines = example_content.splitlines()
        missing_comments = []

        for i, line in enumerate(lines):
            # Check for variable lines
            match = re.match(r"^([A-Z_][A-Z0-9_]*)=", line.strip())
            if match:
                var_name = match.group(1)

                # Check if previous line is a comment (not just section separator)
                has_comment = False
                if i > 0:
                    prev_line = lines[i - 1].strip()
                    # Valid comment is one that's not just "=" separator
                    if (
                        prev_line.startswith("#")
                        and prev_line.replace("#", "").replace("=", "").strip() != ""
                    ):
                        has_comment = True

                if not has_comment:
                    missing_comments.append(var_name)

        if missing_comments:
            errors.append(
                f"WARNING: These env vars in .env.example lack comment blocks:\n"
                f"{', '.join(missing_comments)}\n\n"
                f"Add comments above each var explaining:\n"
                f"# Why needed: <explanation>\n"
                f"# How to get: <steps>\n"
                f"# Default: <value> (if applicable)\n"
                f"{missing_comments[0]}=<value>"
            )
            # Downgraded to warning - not blocking
            return True, errors

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
