#!/usr/bin/env python3
"""
Tier 2 enforcement: verifies docs/user-guide/ exists and contains at least one
.md file when project.yaml has has_user_guide: true.

Exit codes:
    0 - Pass (guide present, or has_user_guide is false/absent)
    1 - Fail (has_user_guide: true but docs/user-guide/ missing or empty)
"""

import os
import re
import sys
from pathlib import Path


def has_user_guide_enabled(repo_root: Path) -> bool:
    """Check if project.yaml has 'has_user_guide: true' using stdlib only.

    Parses with a simple regex to avoid requiring PyYAML in synced projects.
    Returns False if the file is missing, unreadable, or the key is absent/false.
    """
    project_yaml = repo_root / "project.yaml"
    if not project_yaml.exists():
        return False
    try:
        content = project_yaml.read_text(encoding="utf-8")
    except OSError:
        return False
    # Match 'has_user_guide: true' (YAML boolean) at line start, case-insensitive value
    match = re.search(r"^has_user_guide:\s+(true|yes)\s*$", content, re.MULTILINE | re.IGNORECASE)
    return match is not None


def main() -> int:
    """Check that docs/user-guide/ exists when project.yaml requires it."""
    repo_root = Path(os.environ.get("FABRIK_ROOT", Path.cwd()))

    if not has_user_guide_enabled(repo_root):
        return 0

    guide_dir = repo_root / "docs" / "user-guide"
    if not guide_dir.is_dir():
        print("ERROR: docs/user-guide/ missing but project.yaml has has_user_guide: true")
        return 1

    md_files = list(guide_dir.glob("*.md"))
    if not md_files:
        print(
            "ERROR: docs/user-guide/ is empty (no .md files)"
            " but project.yaml has has_user_guide: true"
        )
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
