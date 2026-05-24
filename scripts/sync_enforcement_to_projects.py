#!/usr/bin/env python3
"""Sync enforcement scripts to all /opt projects for Fabrik compliance.

Syncs to all /opt projects:
- Core scripts (6): final_gate.py, kilo_code_review.py, kilo_docs_enforcer.py,
  docs_updater.py, update_agents_toc.py, health_checker.py
- Enforcement directory (scripts/enforcement/*)
- Governance files (5): AGENTS.md, AGENTS-compact.md, opencode.json, .windsurfrules,
  .pre-commit-config.yaml
- Governance directories: .windsurf/rules/, .windsurf/workflows/, docs/reference/kilo/
- Reference docs: docs/reference/windsurf/cascade-models.md

Supports:
- --dry-run: Report what would be copied without writing anything
- --backup: Create timestamped backups before overwriting
- --force: Skip hash comparison and always overwrite

Workflow Doc: docs/workflows/SYNC_ENFORCEMENT_WORKFLOW.md
  ⚠️  Update the workflow doc when modifying this script.
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

FABRIK_ROOT = Path("/opt/fabrik")
OPT_ROOT = Path("/opt")

# Scripts to copy
CORE_SCRIPTS = [
    "final_gate.py",
    "kilo_code_review.py",
    "kilo_docs_enforcer.py",
    "docs_updater.py",
    "update_agents_toc.py",
    "health_checker.py",
]

# Long Command Monitoring System v1.1.0 — see docs/reference/long-command-monitoring.md
# Sourced from templates/scaffold/scripts/ to keep templates and live projects in lockstep.
RUN_SCRIPTS = [
    "rund",
    "rundsh",
    "runc",
    "runk",
    "runls",
    "runlast",
    "runwait",
    "runtail",
    "runclean",
    "sync_cascade_backup.sh",
    "sync_extensions.sh",
]

# Governance files to sync (validated by final_gate.py check_symlinks())
# Note: AFCL.md is scaffolded as AFCL_TEMPLATE.md and customized per project, not synced
# Note: .pre-commit-config.yaml is project-specific based on tech stack, not synced
GOVERNANCE_FILES = [
    "AGENTS.md",
    "AGENTS-compact.md",
    "CLAUDE.md",
    "opencode.json",
    ".windsurfrules",
]
GOVERNANCE_DIRS = [
    ".windsurf/rules",
    ".windsurf/workflows",
    "docs/reference/kilo",
    "docs/reference/MD",
]

# Reference docs to sync to all projects
REFERENCE_DOCS = [
    ("docs/reference/windsurf/cascade-models.md", "docs/reference/windsurf/cascade-models.md"),
    ("docs/reference/long-command-monitoring.md", "docs/reference/long-command-monitoring.md"),
    (
        "docs/reference/technology-stack-decision-guide.md",
        "docs/reference/technology-stack-decision-guide.md",
    ),
    ("docs/reference/AI_TAXONOMY.md", "docs/reference/AI_TAXONOMY.md"),
    ("PORTS.md", "PORTS.md"),
    (
        "docs/reference/ai_agent_prompt_directives.md",
        "docs/reference/ai_agent_prompt_directives.md",
    ),
    ("docs/reference/fabrik-lifecycle.md", "docs/reference/fabrik-lifecycle.md"),
    ("docs/BUSINESS_MODEL.md", "docs/reference/fabrik-project-catalog.md"),
    (
        "docs/reference/mobile-responsive-testing-guide.md",
        "docs/reference/mobile-responsive-testing-guide.md",
    ),
]


@dataclass
class SyncResult:
    """Result of syncing a single file."""

    action: str  # COPY, SKIP, WARN, BACKUP, ERROR
    source: Path
    destination: Path
    reason: str = ""


@dataclass
class ProjectSyncResult:
    """Result of syncing all files to a project."""

    project: Path
    success: bool
    message: str
    files: list[SyncResult] = field(default_factory=list)


def compute_file_hash(path: Path) -> str:
    """Compute MD5 hash of a file."""
    hasher = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def create_backup(path: Path) -> Path:
    """Create timestamped backup of a file."""
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = path.with_suffix(f"{path.suffix}.backup.{timestamp}")
    shutil.copy2(path, backup_path)
    return backup_path


def sync_single_file(
    source: Path,
    destination: Path,
    *,
    dry_run: bool = False,
    backup: bool = False,
    force: bool = False,
) -> SyncResult:
    """Sync a single file with hash comparison and optional backup.

    Args:
        source: Source file path
        destination: Destination file path
        dry_run: If True, report only without writing
        backup: If True, create timestamped backup before overwriting
        force: If True, skip hash comparison and always overwrite

    Returns:
        SyncResult with action taken and details
    """
    # Replace symlinks with real copies (symlinks break workspace isolation)
    if destination.is_symlink():
        if dry_run:
            return SyncResult("COPY", source, destination, "replacing symlink with copy")
        destination.unlink()
        shutil.copy2(source, destination)
        return SyncResult("COPY", source, destination, "replaced symlink with copy")

    # Destination doesn't exist - always copy
    if not destination.exists():
        if dry_run:
            return SyncResult("COPY", source, destination, "new file")
        shutil.copy2(source, destination)
        return SyncResult("COPY", source, destination, "new file")

    # --force: skip all checks, always overwrite
    if force:
        if dry_run:
            return SyncResult("COPY", source, destination, "forced overwrite")
        if backup:
            backup_path = create_backup(destination)
            shutil.copy2(source, destination)
            return SyncResult("COPY", source, destination, f"forced (backup: {backup_path.name})")
        shutil.copy2(source, destination)
        return SyncResult("COPY", source, destination, "forced overwrite")

    # Compare hashes
    source_hash = compute_file_hash(source)
    dest_hash = compute_file_hash(destination)

    if source_hash == dest_hash:
        return SyncResult("SKIP", source, destination, "identical")

    # Hashes differ - check mtime
    source_mtime = source.stat().st_mtime
    dest_mtime = destination.stat().st_mtime

    if dest_mtime > source_mtime:
        return SyncResult("WARN", source, destination, "destination newer")

    # Source is newer - proceed with copy
    if dry_run:
        return SyncResult("COPY", source, destination, "will overwrite")

    if backup:
        backup_path = create_backup(destination)
        result = SyncResult(
            "COPY", source, destination, f"overwritten (backup: {backup_path.name})"
        )
    else:
        result = SyncResult("COPY", source, destination, "overwritten")

    shutil.copy2(source, destination)
    return result


def sync_scripts_to_project(
    project_dir: Path,
    *,
    dry_run: bool = False,
    backup: bool = False,
    force: bool = False,
) -> ProjectSyncResult:
    """Sync all enforcement scripts to a project.

    Args:
        project_dir: Target project directory
        dry_run: If True, report only without writing
        backup: If True, create timestamped backup before overwriting
        force: If True, skip hash comparison and always overwrite

    Returns:
        ProjectSyncResult with detailed file-level results
    """
    scripts_dir = project_dir / "scripts"
    file_results: list[SyncResult] = []

    # Create scripts directory if needed
    if not dry_run:
        try:
            scripts_dir.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            return ProjectSyncResult(project_dir, False, "SKIP (no write permission)")

    try:
        # Sync core scripts
        for script_name in CORE_SCRIPTS:
            source = FABRIK_ROOT / "scripts" / script_name
            if source.exists():
                destination = scripts_dir / script_name
                result = sync_single_file(
                    source, destination, dry_run=dry_run, backup=backup, force=force
                )
                file_results.append(result)

        # Sync run-system scripts (Long Command Monitoring System)
        # Source from templates/scaffold/scripts/ so the canonical path matches what
        # `fabrik scaffold` emits — keeps templates and live projects in lockstep.
        run_src_dir = FABRIK_ROOT / "templates" / "scaffold" / "scripts"
        for script_name in RUN_SCRIPTS:
            source = run_src_dir / script_name
            if source.exists():
                destination = scripts_dir / script_name
                result = sync_single_file(
                    source, destination, dry_run=dry_run, backup=backup, force=force
                )
                file_results.append(result)
                # Preserve executable bit (shutil.copy2 copies mode but be defensive)
                if not dry_run and destination.exists():
                    destination.chmod(0o755)

        # Sync enforcement directory
        fabrik_enforcement = FABRIK_ROOT / "scripts" / "enforcement"
        project_enforcement = scripts_dir / "enforcement"

        if fabrik_enforcement.exists():
            if not dry_run:
                project_enforcement.mkdir(parents=True, exist_ok=True)

            for source in fabrik_enforcement.rglob("*"):
                if source.is_file():
                    relative = source.relative_to(fabrik_enforcement)
                    destination = project_enforcement / relative

                    if not dry_run:
                        destination.parent.mkdir(parents=True, exist_ok=True)

                    result = sync_single_file(
                        source, destination, dry_run=dry_run, backup=backup, force=force
                    )
                    file_results.append(result)

        # Sync governance files (AGENTS.md, opencode.json, .windsurfrules)
        for gov_file in GOVERNANCE_FILES:
            source = FABRIK_ROOT / gov_file
            if source.exists():
                destination = project_dir / gov_file
                result = sync_single_file(
                    source, destination, dry_run=dry_run, backup=backup, force=force
                )
                file_results.append(result)

        # Sync governance directories (.windsurf/rules/)
        for gov_dir in GOVERNANCE_DIRS:
            source_dir = FABRIK_ROOT / gov_dir
            if source_dir.exists():
                dest_dir = project_dir / gov_dir
                # Replace directory symlinks with real directories
                if dest_dir.is_symlink():
                    if not dry_run:
                        dest_dir.unlink()
                        dest_dir.mkdir(parents=True, exist_ok=True)
                elif not dry_run:
                    dest_dir.mkdir(parents=True, exist_ok=True)

                for source in source_dir.rglob("*"):
                    if source.is_file():
                        relative = source.relative_to(source_dir)
                        destination = dest_dir / relative

                        if not dry_run:
                            destination.parent.mkdir(parents=True, exist_ok=True)

                        result = sync_single_file(
                            source, destination, dry_run=dry_run, backup=backup, force=force
                        )
                        file_results.append(result)

        # Delete orphan files in governance directories (files that exist in
        # project but no longer exist in fabrik source — stale from restructures)
        for gov_dir in GOVERNANCE_DIRS:
            source_dir = FABRIK_ROOT / gov_dir
            dest_dir = project_dir / gov_dir
            if not source_dir.exists() or not dest_dir.exists():
                continue
            source_files = {f.relative_to(source_dir) for f in source_dir.rglob("*") if f.is_file()}
            for dest_file in list(dest_dir.rglob("*")):
                if dest_file.is_file():
                    relative = dest_file.relative_to(dest_dir)
                    if relative not in source_files:
                        if not dry_run:
                            dest_file.unlink()
                        file_results.append(
                            SyncResult("DELETE", dest_file, dest_file, "orphan removed")
                        )
            # Remove empty directories left after orphan deletion
            if not dry_run:
                for dirpath in sorted(dest_dir.rglob("*"), reverse=True):
                    if dirpath.is_dir() and not any(dirpath.iterdir()):
                        dirpath.rmdir()

        # Sync reference docs (cascade-models.md, etc.)
        for source_rel, dest_rel in REFERENCE_DOCS:
            source = FABRIK_ROOT / source_rel
            if source.exists():
                destination = project_dir / dest_rel
                if not dry_run:
                    destination.parent.mkdir(parents=True, exist_ok=True)
                result = sync_single_file(
                    source, destination, dry_run=dry_run, backup=backup, force=force
                )
                file_results.append(result)

        # Summarize
        copy_count = sum(1 for r in file_results if r.action in ("COPY", "BACKUP"))
        skip_count = sum(1 for r in file_results if r.action == "SKIP")
        warn_count = sum(1 for r in file_results if r.action == "WARN")
        delete_count = sum(1 for r in file_results if r.action == "DELETE")

        parts = [f"{copy_count} copied", f"{skip_count} skipped"]
        if delete_count > 0:
            parts.append(f"{delete_count} orphans removed")
        if warn_count > 0:
            parts.append(f"{warn_count} warnings")
        msg = f"OK ({', '.join(parts)})"

        return ProjectSyncResult(project_dir, True, msg, file_results)

    except PermissionError:
        return ProjectSyncResult(project_dir, False, "SKIP (no write permission)", file_results)
    except Exception as e:
        return ProjectSyncResult(project_dir, False, str(e), file_results)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Sync enforcement scripts to all /opt projects for Fabrik compliance.",
        epilog="Examples:\n"
        "  %(prog)s --dry-run     # Report what would be copied\n"
        "  %(prog)s --backup      # Create backups before overwriting\n"
        "  %(prog)s --force       # Force overwrite even if destination is newer\n",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would be copied without writing anything",
    )
    parser.add_argument(
        "--backup",
        action="store_true",
        help="Create timestamped .backup.YYYYMMDD-HHMMSS copies before overwriting",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Skip hash comparison and always overwrite (for explicit full-sync)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show per-file details",
    )
    return parser.parse_args()


def main() -> int:
    """Sync scripts to all /opt projects (excluding _* folders)."""
    args = parse_args()

    if args.dry_run:
        print("DRY-RUN MODE: No files will be written\n")

    # Folders to exclude (not real projects)
    exclude_folders = {
        ".factory",
        ".ssh",
        "web_scraper",  # Deprecated, use web-scraper
        # System / non-project directories under /opt that the propagator
        # historically mistakenly targeted (no write permission or no Fabrik
        # project semantics):
        "containerd",  # Docker runtime artifact dir
        "google",  # Google Chrome install location
        "logs",  # Generic logs dir; not a Fabrik project
    }

    # Discover projects
    projects = []
    for project_dir in OPT_ROOT.iterdir():
        if not project_dir.is_dir():
            continue
        if project_dir.name.startswith("_"):
            continue
        if project_dir.name.startswith("."):
            continue  # Skip all hidden folders
        if project_dir.name in exclude_folders:
            continue
        if project_dir == FABRIK_ROOT:
            continue
        projects.append(project_dir)

    print(f"Found {len(projects)} projects to sync")
    print()

    success_count = 0
    fail_count = 0
    total_copied = 0
    total_skipped = 0
    total_warnings = 0

    for project_dir in sorted(projects):
        result = sync_scripts_to_project(
            project_dir,
            dry_run=args.dry_run,
            backup=args.backup,
            force=args.force,
        )

        status = "✓" if result.success else "✗"
        print(f"{status} {project_dir.name:40} {result.message}")

        # Always show safety decisions (SKIP/WARN), show all details in verbose mode
        if result.files:
            for fr in result.files:
                # Always print safety decisions with canonical phrases
                if fr.action == "WARN":
                    print(f"  WARN (destination newer): {fr.destination.name}")
                elif fr.action == "SKIP":
                    print(f"  SKIP (identical): {fr.destination.name}")
                elif args.verbose:
                    action_icon = {
                        "COPY": "  →",
                        "BACKUP": "  ↻",
                        "ERROR": "  ✗",
                    }.get(fr.action, "  ?")
                    print(f"{action_icon} {fr.destination.name}: {fr.reason}")

        if result.success:
            success_count += 1
            total_copied += sum(1 for r in result.files if r.action in ("COPY", "BACKUP"))
            total_skipped += sum(1 for r in result.files if r.action == "SKIP")
            total_warnings += sum(1 for r in result.files if r.action == "WARN")
        else:
            fail_count += 1

    print()
    summary = f"Results: {success_count} projects synced, {fail_count} failed"
    summary += f" | Files: {total_copied} copied, {total_skipped} skipped"
    if total_warnings > 0:
        summary += f", {total_warnings} warnings (use --force to overwrite)"
    print(summary)

    if args.dry_run:
        print("\nDRY-RUN: No files were modified")

    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
