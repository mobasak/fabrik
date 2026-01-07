"""Check plan document conventions.

Enforces:
- Plan files must be in docs/development/plans/
- Plan filenames must match YYYY-MM-DD-slug.md pattern

Note: Index completeness is enforced by docs_updater.py --check (single authority).
"""

import os
import re
from pathlib import Path

from .validate_conventions import CheckResult, Severity

FABRIK_ROOT = Path(os.getenv("FABRIK_ROOT", "/opt/fabrik"))
PLAN_DIR = FABRIK_ROOT / "docs" / "development" / "plans"
PLAN_NAME_RE = re.compile(r"\d{4}-\d{2}-\d{2}-[a-z0-9-]+\.md$")


def check_file(file_path: Path) -> list[CheckResult]:
    """Enforce: plans folder + YYYY-MM-DD-slug.md naming."""
    results: list[CheckResult] = []

    if file_path.suffix != ".md":
        return results

    # Check if file is in plan folder - enforce naming convention
    try:
        if file_path.is_relative_to(PLAN_DIR) and not PLAN_NAME_RE.match(file_path.name):
            results.append(
                CheckResult(
                    check_name="plan_naming",
                    severity=Severity.ERROR,
                    message=f"Invalid plan filename: {file_path.name}",
                    file_path=str(file_path),
                    fix_hint="Rename to YYYY-MM-DD-slug.md format (e.g., 2026-01-07-my-feature.md)",
                )
            )
    except ValueError:
        # Not relative to PLAN_DIR - that's fine, not a plan file
        pass

    return results
