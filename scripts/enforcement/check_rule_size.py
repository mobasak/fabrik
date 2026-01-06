#!/usr/bin/env python3
"""Check that .windsurf/rules/*.md files stay under 12KB limit."""

import sys
from pathlib import Path

MAX_SIZE_BYTES = 12288  # 12KB


def main() -> int:
    """Check rule file sizes."""
    rules_dir = Path(__file__).parent.parent.parent / ".windsurf" / "rules"

    if not rules_dir.exists():
        return 0

    errors = []
    for rule_file in rules_dir.glob("*.md"):
        size = rule_file.stat().st_size
        if size > MAX_SIZE_BYTES:
            errors.append(f"ERROR: {rule_file.name} is {size} bytes (>{MAX_SIZE_BYTES})")

    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
