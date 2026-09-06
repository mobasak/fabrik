#!/usr/bin/env python3
# AFTER-EDIT: docs/workflows/FINAL_GATE_WORKFLOW.md
"""Check that services have watchdog scripts."""

from __future__ import annotations

from pathlib import Path

try:
    from .validate_conventions import CheckResult, Severity
except ImportError:  # standalone run (final_gate executes `python <path>`)
    from validate_conventions import CheckResult, Severity  # type: ignore[no-redef]


def check_file(file_path: Path) -> list[CheckResult]:
    """Check if a service project has a watchdog script.

    Returns list of CheckResult objects.
    """
    results: list[CheckResult] = []

    # Only check compose.yaml files (indicates a service)
    if file_path.name not in ("compose.yaml", "compose.yml", "docker-compose.yaml"):
        return results

    project_root = file_path.parent
    scripts_dir = project_root / "scripts"

    # Check for watchdog script
    watchdog_patterns = ["watchdog*.sh", "watchdog*.py", "watchdog_*.sh", "watchdog_*.py"]
    has_watchdog = False

    if scripts_dir.exists():
        for pattern in watchdog_patterns:
            if list(scripts_dir.glob(pattern)):
                has_watchdog = True
                break

    if not has_watchdog:
        results.append(
            CheckResult(
                check_name="watchdog",
                severity=Severity.WARN,
                message="Service has no watchdog script",
                file_path=str(file_path),
                line_number=None,
                fix_hint="Create scripts/watchdog.sh using template from 30-ops.md",
            )
        )

    return results


if __name__ == "__main__":  # pragma: no cover — CLI entry (see _check_runner)
    try:
        from ._check_runner import main_for
    except ImportError:  # standalone run (final_gate executes `python <path>`)
        from _check_runner import main_for  # type: ignore[no-redef]

    main_for(
        check_file,
        check_name="check_watchdog",
        description="Every compose-bearing service ships a scripts/watchdog.* script",
    )
