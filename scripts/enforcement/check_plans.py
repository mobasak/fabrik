"""Check plan document conventions.

Enforces:
- Plan files must be in docs/development/plans/
- Plan filenames must match YYYY-MM-DD-plan-<name>.md pattern

Note: Index completeness is enforced by docs_updater.py --check (single authority).
"""

import os
import re
from pathlib import Path

from .validate_conventions import CheckResult, Severity

FABRIK_ROOT = Path(os.getenv("FABRIK_ROOT", "/opt/fabrik"))
PLAN_DIR = FABRIK_ROOT / "docs" / "development" / "plans"
# New format: YYYY-MM-DD-plan-<name>.md (e.g., 2026-01-14-plan-feature-name.md)
# Also accept legacy format for backward compatibility: YYYY-MM-DD-<slug>.md
PLAN_NAME_NEW_RE = re.compile(r"\d{4}-\d{2}-\d{2}-plan-[a-z0-9-]+\.md$")
PLAN_NAME_LEGACY_RE = re.compile(r"\d{4}-\d{2}-\d{2}-[a-z0-9-]+\.md$")


def check_file(file_path: Path) -> list[CheckResult]:
    """Enforce: plans folder + YYYY-MM-DD-plan-<name>.md naming."""
    results: list[CheckResult] = []

    if file_path.suffix != ".md":
        return results

    # Check if file is in plan folder - enforce naming convention
    try:
        if file_path.is_relative_to(PLAN_DIR):
            # Skip README.md and index files
            if file_path.name.lower() in ("readme.md", "index.md"):
                return results
            # Check new format first, then legacy
            if not PLAN_NAME_NEW_RE.match(file_path.name):
                if PLAN_NAME_LEGACY_RE.match(file_path.name):
                    # Legacy format - warn but don't error
                    results.append(
                        CheckResult(
                            check_name="plan_naming",
                            severity=Severity.WARN,
                            message=f"Legacy plan filename: {file_path.name}",
                            file_path=str(file_path),
                            fix_hint="Consider renaming to YYYY-MM-DD-plan-<name>.md format",
                        )
                    )
                else:
                    results.append(
                        CheckResult(
                            check_name="plan_naming",
                            severity=Severity.ERROR,
                            message=f"Invalid plan filename: {file_path.name}",
                            file_path=str(file_path),
                            fix_hint="Rename to YYYY-MM-DD-plan-<name>.md format (e.g., 2026-01-14-plan-my-feature.md)",
                        )
                    )
    except ValueError:
        # Not relative to PLAN_DIR - that's fine, not a plan file
        pass

    return results
