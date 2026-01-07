#!/usr/bin/env python3
"""Sync documentation after code changes.

This script ensures all required documentation is updated after code changes:
1. CHANGELOG.md - Required for all significant changes
2. tasks.md - Phase status if implementation work
3. Phase docs - Checkboxes if completing tracked tasks
4. docs/INDEX.md - Structure map if files added/moved

Usage:
    python scripts/docs_sync.py              # Check what needs updating
    python scripts/docs_sync.py --apply      # Apply updates where possible
    python scripts/docs_sync.py --changed    # Show changed files since last commit
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import date
from pathlib import Path


def get_changed_files() -> list[Path]:
    """Get files changed since last commit (staged + unstaged)."""
    files: set[str] = set()

    # Staged changes
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        capture_output=True,
        text=True,
        cwd="/opt/fabrik",
    )
    files.update(result.stdout.strip().split("\n"))

    # Unstaged changes
    result = subprocess.run(
        ["git", "diff", "--name-only"], capture_output=True, text=True, cwd="/opt/fabrik"
    )
    files.update(result.stdout.strip().split("\n"))

    # Filter empty strings and return as Paths
    return [Path(f) for f in files if f.strip()]


def check_changelog_updated(changed_files: list[Path]) -> dict:
    """Check if CHANGELOG.md needs updating."""
    significant_files = [
        f
        for f in changed_files
        if f.suffix in (".py", ".ts", ".tsx", ".js", ".sh") and "test" not in str(f).lower()
    ]

    changelog_changed = any(f.name == "CHANGELOG.md" for f in changed_files)

    return {
        "name": "CHANGELOG.md",
        "needs_update": bool(significant_files) and not changelog_changed,
        "reason": f"{len(significant_files)} code files changed" if significant_files else None,
        "files": [str(f) for f in significant_files[:5]],
    }


def check_tasks_updated(changed_files: list[Path]) -> dict:
    """Check if tasks.md needs updating (phase docs changed)."""
    phase_files = [f for f in changed_files if "phase" in f.name.lower() and f.suffix == ".md"]
    tasks_changed = any(f.name == "tasks.md" for f in changed_files)

    return {
        "name": "tasks.md",
        "needs_update": bool(phase_files) and not tasks_changed,
        "reason": f"Phase docs changed: {', '.join(f.name for f in phase_files)}"
        if phase_files
        else None,
        "files": [str(f) for f in phase_files],
    }


def check_phase_docs(changed_files: list[Path]) -> dict:
    """Check if any phase docs should be updated for implementation work."""
    impl_files = [f for f in changed_files if f.suffix == ".py" and "src/fabrik" in str(f)]

    # This is a heuristic - can't auto-determine which phase
    return {
        "name": "Phase docs",
        "needs_update": bool(impl_files),
        "reason": f"{len(impl_files)} implementation files changed" if impl_files else None,
        "hint": "Check if any tracked tasks were completed and update relevant Phase*.md",
        "files": [str(f) for f in impl_files[:5]],
    }


def check_index_updated(changed_files: list[Path]) -> dict:
    """Check if docs/INDEX.md needs updating (new docs added)."""
    new_docs = [f for f in changed_files if f.suffix == ".md" and "docs/" in str(f)]
    index_changed = any("INDEX.md" in str(f) for f in changed_files)

    return {
        "name": "docs/INDEX.md",
        "needs_update": bool(new_docs) and not index_changed,
        "reason": f"New docs added: {', '.join(f.name for f in new_docs)}" if new_docs else None,
        "files": [str(f) for f in new_docs],
    }


def update_tasks_date() -> bool:
    """Update the Last Updated date in tasks.md."""
    tasks_path = Path("/opt/fabrik/tasks.md")
    if not tasks_path.exists():
        return False

    content = tasks_path.read_text()
    today = date.today().strftime("%Y-%m-%d")

    # Update the date
    import re

    new_content = re.sub(
        r"\*\*Last Updated:\*\* \d{4}-\d{2}-\d{2}", f"**Last Updated:** {today}", content
    )

    if new_content != content:
        tasks_path.write_text(new_content)
        return True
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync documentation after code changes")
    parser.add_argument("--apply", action="store_true", help="Apply automatic updates")
    parser.add_argument("--changed", action="store_true", help="Show changed files")
    args = parser.parse_args()

    changed_files = get_changed_files()

    if args.changed:
        print("Changed files:")
        for f in changed_files:
            print(f"  {f}")
        return 0

    if not changed_files:
        print("✅ No changed files detected")
        return 0

    # Run all checks
    checks = [
        check_changelog_updated(changed_files),
        check_tasks_updated(changed_files),
        check_phase_docs(changed_files),
        check_index_updated(changed_files),
    ]

    needs_attention = [c for c in checks if c.get("needs_update")]

    if not needs_attention:
        print("✅ All documentation appears up to date")
        return 0

    print("📝 Documentation updates needed:\n")

    for check in needs_attention:
        print(f"❌ {check['name']}")
        if check.get("reason"):
            print(f"   Reason: {check['reason']}")
        if check.get("hint"):
            print(f"   Hint: {check['hint']}")
        if check.get("files"):
            print(f"   Files: {', '.join(check['files'][:3])}")
        print()

    if args.apply:
        print("Applying automatic updates...\n")

        # Auto-update tasks.md date
        if any(c["name"] == "tasks.md" for c in needs_attention):
            if update_tasks_date():
                print("  ✅ Updated tasks.md Last Updated date")

        print("\n⚠️  Manual updates still needed for:")
        print("  - CHANGELOG.md entries")
        print("  - Phase doc checkboxes")
        print("  - docs/INDEX.md structure")

    return 1 if needs_attention else 0


if __name__ == "__main__":
    sys.exit(main())
