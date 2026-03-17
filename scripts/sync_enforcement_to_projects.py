#!/usr/bin/env python3
"""Sync enforcement scripts to all /opt projects for Fabrik compliance."""

import shutil
import sys
from pathlib import Path

FABRIK_ROOT = Path("/opt/fabrik")
OPT_ROOT = Path("/opt")

# Scripts to copy
CORE_SCRIPTS = ["final_gate.py", "kilo_code_review.py", "docs_updater.py", "update_agents_toc.py"]


def sync_scripts_to_project(project_dir: Path) -> tuple[bool, str]:
    """Sync all enforcement scripts to a project."""
    scripts_dir = project_dir / "scripts"

    try:
        scripts_dir.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        return False, "SKIP (no write permission)"

    try:
        # Copy core scripts
        for script_name in CORE_SCRIPTS:
            fabrik_script = FABRIK_ROOT / "scripts" / script_name
            if fabrik_script.exists():
                shutil.copy(fabrik_script, scripts_dir / script_name)

        # Copy enforcement directory
        fabrik_enforcement = FABRIK_ROOT / "scripts" / "enforcement"
        project_enforcement = scripts_dir / "enforcement"
        if fabrik_enforcement.exists():
            shutil.copytree(fabrik_enforcement, project_enforcement, dirs_exist_ok=True)

        return True, "OK"
    except PermissionError:
        return False, "SKIP (no write permission)"
    except Exception as e:
        return False, str(e)


def main():
    """Sync scripts to all /opt projects (excluding _* folders)."""
    projects = []
    for project_dir in OPT_ROOT.iterdir():
        if not project_dir.is_dir():
            continue
        if project_dir.name.startswith("_"):
            continue
        if project_dir == FABRIK_ROOT:
            continue
        projects.append(project_dir)

    print(f"Found {len(projects)} projects to sync")
    print()

    success_count = 0
    fail_count = 0

    for project_dir in sorted(projects):
        success, msg = sync_scripts_to_project(project_dir)
        status = "✓" if success else "✗"
        print(f"{status} {project_dir.name:40} {msg}")

        if success:
            success_count += 1
        else:
            fail_count += 1

    print()
    print(f"Results: {success_count} synced, {fail_count} failed")

    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
