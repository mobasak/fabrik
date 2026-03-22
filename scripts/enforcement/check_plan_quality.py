"""Check plan document quality - required sections and content.

Enforces that plan files in docs/development/plans/ contain:
- **Status:** line (NOT_STARTED, IN_PROGRESS, PARTIAL, COMPLETE, NOT_DONE)
- ## Goal section
- ## DONE WHEN section with checkboxes
- ## Out of Scope section
- ## Steps section

This complements check_plans.py which only validates naming convention.
"""

import re
from pathlib import Path

from .validate_conventions import CheckResult, Severity

# Check project's own plans directory
PLAN_DIR = Path.cwd() / "docs" / "development" / "plans"

# Required sections for plan documents
REQUIRED_SECTIONS = [
    ("Status", r"\*\*Status:\*\*\s*(NOT_STARTED|IN_PROGRESS|PARTIAL|COMPLETE|NOT_DONE)"),
    ("Goal", r"^##\s+Goal\b"),
    ("DONE WHEN", r"^##\s+DONE WHEN\b"),
    ("Out of Scope", r"^##\s+Out of Scope\b"),
    ("Steps", r"^##\s+Steps\b"),
]

# DONE WHEN must have at least one checkbox
CHECKBOX_PATTERN = re.compile(r"^\s*-\s*\[[ x]\]", re.MULTILINE)


def check_file(file_path: Path) -> list[CheckResult]:
    """Validate plan document has required sections and content."""
    results: list[CheckResult] = []

    if file_path.suffix != ".md":
        return results

    # Only check files in the plans directory
    try:
        if not file_path.is_relative_to(PLAN_DIR):
            return results
    except ValueError:
        return results

    # Skip index files
    if file_path.name.lower() in ("readme.md", "index.md", "plans.md"):
        return results

    # Read file content
    try:
        content = file_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        results.append(
            CheckResult(
                check_name="plan_quality",
                severity=Severity.ERROR,
                message=f"Cannot read plan file: {e}",
                file_path=str(file_path),
            )
        )
        return results

    # Check each required section
    for section_name, pattern in REQUIRED_SECTIONS:
        regex = re.compile(pattern, re.MULTILINE | re.IGNORECASE)
        if not regex.search(content):
            results.append(
                CheckResult(
                    check_name="plan_quality",
                    severity=Severity.ERROR,
                    message=f"Missing required section: {section_name}",
                    file_path=str(file_path),
                    fix_hint=f"Add '{section_name}' section to the plan document",
                )
            )

    # Check DONE WHEN has checkboxes
    done_when_match = re.search(
        r"^##\s+DONE WHEN\b.*?(?=^##|\Z)", content, re.MULTILINE | re.DOTALL
    )
    if done_when_match:
        done_when_section = done_when_match.group(0)
        if not CHECKBOX_PATTERN.search(done_when_section):
            results.append(
                CheckResult(
                    check_name="plan_quality",
                    severity=Severity.WARN,
                    message="DONE WHEN section has no checkboxes",
                    file_path=str(file_path),
                    fix_hint="Add checkbox items: - [ ] criterion",
                )
            )

    # Check Steps section has content
    steps_match = re.search(r"^##\s+Steps\b.*?(?=^##|\Z)", content, re.MULTILINE | re.DOTALL)
    if steps_match:
        steps_section = steps_match.group(0)
        # Should have at least one numbered or bulleted item
        if not re.search(r"^\s*(\d+\.|[-*])\s+\S", steps_section, re.MULTILINE):
            results.append(
                CheckResult(
                    check_name="plan_quality",
                    severity=Severity.WARN,
                    message="Steps section appears empty",
                    file_path=str(file_path),
                    fix_hint="Add implementation steps as numbered or bulleted list",
                )
            )

    return results
