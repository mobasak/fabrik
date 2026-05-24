#!/usr/bin/env python3
"""Check that .windsurf/rules/**/*.md files stay under 32KB limit."""

import sys
from pathlib import Path

MAX_SIZE_BYTES = 32768  # 32KB


def main() -> int:
    """Check rule file sizes (recursive — includes subdirectories)."""
    rules_dir = Path.cwd() / ".windsurf" / "rules"

    if not rules_dir.exists():
        return 0

    errors = []
    for rule_file in rules_dir.rglob("*.md"):
        size = rule_file.stat().st_size
        if size > MAX_SIZE_BYTES:
            relative = rule_file.relative_to(rules_dir)
            errors.append(f"ERROR: {relative} is {size} bytes (>{MAX_SIZE_BYTES})")

    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
