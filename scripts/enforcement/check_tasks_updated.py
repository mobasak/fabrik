#!/usr/bin/env python3
"""Check that tasks.md is updated when phase docs change."""

from pathlib import Path

from .validate_conventions import CheckResult, Severity


def check_file(file_path: Path) -> list[CheckResult]:
    """Check if tasks.md should be updated when phase docs change.

    Args:
        file_path: Path to check

    Returns:
        List of check results
    """
    results: list[CheckResult] = []

    # Only check phase doc changes
    if "docs/reference" not in str(file_path):
        return results

    if not file_path.name.lower().startswith("phase"):
        return results

    # Check if tasks.md was also modified in this commit
    tasks_md = Path("/opt/fabrik/tasks.md")
    if not tasks_md.exists():
        return results

    # Get tasks.md modification time vs phase doc
    # This is a heuristic - if phase doc is newer, tasks.md may need update
    tasks_mtime = tasks_md.stat().st_mtime
    phase_mtime = file_path.stat().st_mtime

    if phase_mtime > tasks_mtime + 60:  # 60 second buffer
        results.append(
            CheckResult(
                check_name="tasks_updated",
                severity=Severity.WARN,
                message=f"Phase doc '{file_path.name}' updated - check if tasks.md needs update",
                file_path=str(file_path),
                fix_hint="Update tasks.md phase status table if completion changed",
            )
        )

    return results
