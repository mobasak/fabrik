#!/usr/bin/env python3
"""Sync enforcement scripts to all /opt projects for Fabrik compliance.

Syncs to all /opt projects:
- Core scripts (6): final_gate.py, kilo_code_review.py, kilo_docs_enforcer.py,
  docs_updater.py, update_agents_toc.py, health_checker.py
- Enforcement directory (scripts/enforcement/*)
- Governance files (5): AGENTS.md, AGENTS-compact.md, opencode.json, .windsurfrules,
  .pre-commit-config.yaml
- Governance directories: .windsurf/rules/, .windsurf/workflows/, docs/reference/kilo/
- Reference docs: long-command-monitoring, technology-stack-decision-guide, etc. (REFERENCE_DOCS)

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
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

# Single source of truth for the synced set — shared with scaffold.py's .gitignore
# block and check_synced_unmodified.py (the gate teeth). Edit the manifest, not
# these lists. (`scripts/` is the script's own dir, so a plain import works.)
sys.path.insert(0, str(Path(__file__).resolve().parent))
from fabrik_synced_manifest import (  # noqa: E402
    AGENT_HOOK_FILES,
    CORE_SCRIPTS,
    GOVERNANCE_DIRS,
    GOVERNANCE_FILES,
    GOVERNANCE_TEMPLATES,
    REFERENCE_DOCS,
    RUN_SCRIPTS,
    RUN_SCRIPTS_SRC_DIR,
    VENDORED_DIRS,
    gitignore_block_text,
    iter_synced_pairs,
)

# Matches the existing "Fabrik-synced" block in a project's .gitignore (either the
# old "managed by" header or the new "DO NOT EDIT" one — anchored on the stable end
# marker) so we can replace just that block without touching project-own entries.
_GITIGNORE_BLOCK_RE = re.compile(
    r"# =+\n# Fabrik-synced files.*?# End Fabrik-synced block\n# =+\n",
    re.DOTALL,
)

# The safety FLOOR every project's .gitignore must cover — secrets, virtualenvs, bytecode.
# These are deliberately NOT part of the Fabrik-synced block: that block lists centrally-managed
# FILES, whereas this is project hygiene. But the sync enforces the floor anyway, because a
# .gitignore that has lost these rules is one `git add -A` away from committing a .env.
_ESSENTIAL_IGNORES = """# Essential safety rules — restored by sync_enforcement_to_projects.py.
# A .gitignore missing these is one `git add -A` away from committing secrets.
.env
.env.*
# Sibling templates stay committable — `.env.*` would otherwise silently make a NEW
# .env.sample / .env.template / .env.dist un-addable (`git add` no-ops, no error).
!.env.example
!.env.sample
!.env.template
!.env.dist
.venv/
venv/
__pycache__/
*.pyc
"""

# ⚠️ ACCEPTED TRADEOFF. The floor is appended LAST, so its `.env.*` becomes the final match for any
# `.env.<x>` a project deliberately tracks via its own negation (e.g. `!.env.ci`) — `git add .env.ci`
# would then silently no-op. We re-include the four conventional templates below, but we cannot know a
# project's bespoke ones. This is chosen knowingly: the floor only fires on a project that has ALREADY
# lost its `.env` protection, and in that state "a template briefly needs re-negating" is a far cheaper
# failure than "a secret is one `git add -A` from GitHub". Loud warning + non-zero exit tell the operator
# to look.
_ESSENTIAL_PATTERNS = (".env", ".venv/", "__pycache__/")

# Idempotency marker — if this string is already in the file, the floor is present; never re-append.
_ESSENTIAL_MARKER = "Essential safety rules"

# Projects where the safety floor was written but git STILL reports .env unignored. The sync must
# FAIL on these, not merely print: a mechanism that reports success while a secret stays committable
# buys false confidence, which is worse than no mechanism. One line in a 47-project log is not
# enforcement — the non-zero exit is.
_SAFETY_FLOOR_FAILURES: list[str] = []


def _covers_essentials(text: str) -> bool:
    """True iff ``text`` literally lists the safety floor. TEXT-only — used by the tests.

    ⚠️ Prefer :func:`_git_covers_essentials` for the real decision. This literal check cannot see
    that ``.env*`` or ``venv/`` already protect ``.env``, so using it to gate the repair would
    prepend redundant rules to healthy repos — churning 40 projects to fix 3. Git is the authority
    on what is actually ignored; a hand-rolled glob matcher is not.
    """
    lines = {
        ln.strip().rstrip("/")
        for ln in text.splitlines()
        if ln.strip() and not ln.lstrip().startswith("#")
    }
    return all(p.rstrip("/") in lines for p in _ESSENTIAL_PATTERNS)


def patched_gitignore(content: str, project_dir: Path) -> tuple[str, bool]:
    """Return ``(new_gitignore_text, repaired)`` for a project's .gitignore.

    THE single code path for this logic — the sync calls it and so do the tests. It is public and
    extracted precisely because the tests previously re-implemented it in a local helper: they
    validated a COPY, so the real code could drift and the suite would stay green. That is exactly
    how the append-vs-prepend defect below survived its own "passing" tests.

    Two jobs:

    1. Replace the marked "Fabrik-synced" block (leaving the project's own entries alone), or append
       it if absent.
    2. Enforce the SAFETY FLOOR — if git says the project does not ignore ``.env`` / ``.venv/`` /
       ``__pycache__/``, its own rules are missing or damaged, so add them back.

    ⚠️ The floor is APPENDED, not prepended, and that is load-bearing: in .gitignore the LAST
    matching rule wins. Prepending put the floor FIRST, so any later project rule (e.g. a stray
    ``!.env``) silently overrode it — the "floor" was merely a suggestion. Appending makes it
    actually win. (The caller still re-verifies with git afterwards, because a nested .gitignore
    deeper in the tree can defeat even a last rule.)
    """
    block = gitignore_block_text()
    if _GITIGNORE_BLOCK_RE.search(content):
        new = _GITIGNORE_BLOCK_RE.sub(lambda _m: block, content)
    else:
        new = content.rstrip("\n") + "\n\n" + block

    # A non-repo can never become "covered", so a fail-closed repair would fire on EVERY sync and the
    # floor would stack without bound. It also has nothing to protect (CI and the VPS both get code via
    # git). Skip it — see _is_git_repo.
    if not _is_git_repo(project_dir):
        return new, False

    # Belt-and-braces against stacking: never append a floor that is already there. `_git_covers_
    # essentials` should already prevent this, but it can legitimately still answer "not covered" after
    # a repair (e.g. a nested `sub/.gitignore` with `!.env` defeats even a last-wins rule) — and in
    # THAT case, appending again every sync would grow the file forever while never fixing anything.
    if _ESSENTIAL_MARKER in new:
        return new, False

    # Ask GIT (authoritative) whether the project ALREADY protects .env. Evaluating the CURRENT tree
    # is correct: swapping the Fabrik block never changes .env protection either way.
    repaired = not _git_covers_essentials(project_dir)
    if repaired:
        new = new.rstrip("\n") + "\n\n" + _ESSENTIAL_IGNORES
    return new, repaired


def _is_git_repo(project_dir: Path) -> bool:
    """Is this actually a git working tree?

    ⚠️ Load-bearing for IDEMPOTENCY. `_git_covers_essentials` fails CLOSED — a non-repo makes
    `check-ignore` return 128, which it reads as "not ignored" → repair. But a non-repo can never
    BECOME covered, so it repaired on EVERY run and the floor stacked without bound (reproduced:
    1 → 2 → 3 floors, the file growing each sync). `main()` discovers projects by `is_dir()` and does
    NOT require `.git`, so plain directories under /opt are in the sync set today.

    A non-repo also has nothing to protect: CI and the VPS both obtain code via `git`, so a directory
    with no git has no clone to leak a `.env` into. Skipping it is correct, not merely convenient.
    """
    try:
        return (
            subprocess.run(  # noqa: S603 — fixed argv, no shell
                ["git", "rev-parse", "--is-inside-work-tree"],
                cwd=project_dir,
                capture_output=True,
                check=False,
            ).returncode
            == 0
        )
    except (OSError, subprocess.SubprocessError):
        # git absent / not executable. Its sibling `_git_covers_essentials` guards this; without the
        # same guard here a FileNotFoundError escaped `patched_gitignore` (which is PUBLIC and called by
        # the tests) and every project got reported as failed.
        return False


def _git_covers_essentials(project_dir: Path) -> bool:
    """Ask GIT whether this project already ignores the safety floor. Authoritative.

    Uses the project's real .gitignore semantics (globs, negations, nested ignore files, precedence)
    instead of re-implementing them. Patching the Fabrik block never changes ``.env`` protection —
    it only swaps a marked region — so evaluating the CURRENT tree is the correct gate: if git says
    ``.env`` is already ignored, the project's own rules are intact and we must not touch them.

    Fails CLOSED (returns False → repair) if git is unavailable, so an error can never leave a
    ``.env`` exposed.
    """
    try:
        for pattern in _ESSENTIAL_PATTERNS:
            proc = subprocess.run(  # noqa: S603 — fixed argv, no shell
                ["git", "check-ignore", "-v", pattern],
                cwd=project_dir,
                capture_output=True,
                text=True,
                check=False,
            )
            if proc.returncode != 0:  # 0 = ignored; 1 = NOT ignored; 128 = not a repo
                return False
            # ⚠️ FAIL-OPEN TRAP: `check-ignore` also honours `.git/info/exclude` and the user's GLOBAL
            # `core.excludesFile` (~/.config/git/ignore). NEITHER travels with the repo. If a damaged
            # project's `.env` were ignored only by the operator's personal global ignore, this would
            # answer "safe", the repair would never fire, and every fresh clone — CI, a teammate, the
            # VPS — would be UNPROTECTED. The rule must hold for the REPO, not for this machine.
            #
            # `-v` prints `<source>:<line>:<pattern>\t<path>`. Only a `.gitignore` that is part of the
            # repo counts; a match sourced from `.git/info/exclude` or an absolute path outside the
            # tree is a local-only rule and must NOT be trusted.
            # Format: `<source>:<line>:<pattern>\t<pathname>`. The SOURCE path may itself contain
            # colons, so a naive split(":", 1) mis-parses it and triggers a spurious repair. Take the
            # left of the TAB, then strip the two rightmost `:`-delimited fields (line, pattern).
            left = proc.stdout.split("\t", 1)[0]
            source = left.rsplit(":", 2)[0].strip() if left.count(":") >= 2 else left.strip()
            if not source.endswith(".gitignore") or source.startswith((".git/", "/")):
                return False
        return True
    except (OSError, subprocess.SubprocessError):
        return False


FABRIK_ROOT = Path("/opt/fabrik")
OPT_ROOT = Path("/opt")


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


def _atomic_copy(source: Path, destination: Path) -> None:
    """Copy ``source`` onto ``destination`` ATOMICALLY: write to a temp file in the SAME directory
    (so it's on the same filesystem, a hard requirement for an atomic rename) then ``os.replace`` it
    into place. A concurrent reader (e.g. a project actively importing ``libs/subagents``) therefore
    sees EITHER the whole old file OR the whole new file — never a half-written one — and a process
    that already imported the module keeps the old inode alive until it exits (the rename only swaps
    the directory entry). This is what makes a mid-dispatch sync safe: no torn reads, no ImportError.
    Falls back to a plain copy only if the atomic path can't be used (cross-device temp, etc.)."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=str(destination.parent), prefix=".sync-tmp-")
    os.close(fd)
    tmp = Path(tmp_name)
    try:
        shutil.copy2(source, tmp)  # content + mode/mtime, into the dest dir (same filesystem)
        os.replace(tmp, destination)  # atomic on the same filesystem
    except Exception:
        tmp.unlink(missing_ok=True)
        raise


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
        _atomic_copy(source, destination)
        return SyncResult("COPY", source, destination, "replaced symlink with copy")

    # Destination doesn't exist - always copy
    if not destination.exists():
        if dry_run:
            return SyncResult("COPY", source, destination, "new file")
        _atomic_copy(source, destination)
        return SyncResult("COPY", source, destination, "new file")

    # --force: skip all checks, always overwrite
    if force:
        if dry_run:
            return SyncResult("COPY", source, destination, "forced overwrite")
        if backup:
            backup_path = create_backup(destination)
            _atomic_copy(source, destination)
            return SyncResult("COPY", source, destination, f"forced (backup: {backup_path.name})")
        _atomic_copy(source, destination)
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
        run_src_dir = FABRIK_ROOT / RUN_SCRIPTS_SRC_DIR
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
                # Never sync compiled bytecode — __pycache__/*.pyc is build noise,
                # not enforcement logic, and was bloating every project.
                if "__pycache__" in source.parts or source.suffix == ".pyc":
                    continue
                if source.is_file():
                    relative = source.relative_to(fabrik_enforcement)
                    destination = project_enforcement / relative

                    if not dry_run:
                        destination.parent.mkdir(parents=True, exist_ok=True)

                    result = sync_single_file(
                        source, destination, dry_run=dry_run, backup=backup, force=force
                    )
                    file_results.append(result)

        # Sync vendored fabrik-lib modules (libs/subagents pool) — recursive flat copy, bytecode
        # excluded (same rule as the enforcement dir), WITH orphan pruning: a Python module churns, so
        # a file REMOVED from the hub must be removed from every project too — else a stale
        # `from libs.subagents import <gone>` keeps resolving to dead code. Hub source is kept
        # byte-identical to canonical /opt/fabrik-lib/subagents by re-vendoring before a sync.
        for vendored_rel in VENDORED_DIRS:
            fabrik_vendored = FABRIK_ROOT / vendored_rel
            project_vendored = project_dir / vendored_rel
            if not fabrik_vendored.is_dir():
                continue  # missing or clobbered-to-a-file hub source → skip (never make an empty dir)
            if not dry_run:
                project_vendored.mkdir(parents=True, exist_ok=True)
            live_rel: set[Path] = set()
            for source in fabrik_vendored.rglob("*"):
                if "__pycache__" in source.parts or source.suffix == ".pyc":
                    continue
                if source.is_file():
                    relative = source.relative_to(fabrik_vendored)
                    live_rel.add(relative)
                    destination = project_vendored / relative
                    if not dry_run:
                        destination.parent.mkdir(parents=True, exist_ok=True)
                    result = sync_single_file(
                        source, destination, dry_run=dry_run, backup=backup, force=force
                    )
                    file_results.append(result)
            # Prune orphans: files in the project copy no longer present in the hub (skip project
            # bytecode so a stray .pyc never keeps a deleted source "alive" in the live set).
            if project_vendored.is_dir():
                for dest_file in list(project_vendored.rglob("*")):
                    if not dest_file.is_file():
                        continue
                    if "__pycache__" in dest_file.parts or dest_file.suffix == ".pyc":
                        continue
                    if dest_file.relative_to(project_vendored) not in live_rel:
                        if not dry_run:
                            dest_file.unlink()
                        file_results.append(
                            SyncResult("DELETE", dest_file, dest_file, "orphan removed")
                        )
                if not dry_run:  # remove empty dirs left after pruning
                    for dirpath in sorted(project_vendored.rglob("*"), reverse=True):
                        if dirpath.is_dir() and not any(dirpath.iterdir()):
                            dirpath.rmdir()

        # Sync governance files (AGENTS.md, opencode.json, .windsurfrules)
        for gov_file in GOVERNANCE_FILES:
            source = FABRIK_ROOT / gov_file
            if source.exists():
                destination = project_dir / gov_file
                result = sync_single_file(
                    source, destination, dry_run=dry_run, backup=backup, force=force
                )
                file_results.append(result)

        # Governance templates: src under templates/, dest at project root.
        # CLAUDE.md hub/project split — /opt/fabrik/CLAUDE.md is the HUB agents'
        # contract and is never distributed; projects receive the template copy.
        for src_rel, dest_rel in GOVERNANCE_TEMPLATES:
            source = FABRIK_ROOT / src_rel
            if source.exists():
                destination = project_dir / dest_rel
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

        # Sync reference docs (REFERENCE_DOCS list)
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

        # Sync agent "definition of done" hooks (.claude/ Stop hook, Cascade
        # .windsurf/hooks.json). Nested paths → mkdir parents like reference docs.
        # opencode.json (Kilo) rides GOVERNANCE_FILES above.
        for rel in AGENT_HOOK_FILES:
            source = FABRIK_ROOT / rel
            if source.exists():
                destination = project_dir / rel
                if not dry_run:
                    destination.parent.mkdir(parents=True, exist_ok=True)
                result = sync_single_file(
                    source, destination, dry_run=dry_run, backup=backup, force=force
                )
                file_results.append(result)
                # Preserve the hook script's executable bit.
                if not dry_run and destination.exists() and destination.suffix == ".py":
                    destination.chmod(0o755)

        # Patch the .gitignore "Fabrik-synced" block so every governance/synced file
        # is ignored in this project — existing projects too, not just fresh scaffolds.
        # Only the marked block is replaced; the project's own .gitignore entries are
        # left untouched. (.gitignore itself is never overwritten wholesale.)
        gitignore = project_dir / ".gitignore"
        # ⚠️ A repo with NO .gitignore is strictly MORE exposed than a block-only one, yet the net
        # used to be gated on the existence of the very file whose absence is the hazard. Treat a
        # missing file as empty content and create it.
        if gitignore.exists() or _is_git_repo(project_dir):
            try:
                content = gitignore.read_text() if gitignore.exists() else ""
                new, repaired = patched_gitignore(content, project_dir)
                if repaired:
                    print(
                        f"  ⚠️  {project_dir.name}: .gitignore did NOT ignore .env / .venv / "
                        f"__pycache__ — safety floor appended. The project's own ignore rules "
                        f"appear to have been lost; review .gitignore."
                    )
                if new != content:
                    if not dry_run:
                        if backup:
                            create_backup(gitignore)
                        gitignore.write_text(new)
                        # ⚠️ VERIFY THE REPAIR ACTUALLY HELD — do not merely assert it.
                        # The floor is appended so it wins (gitignore: LAST match wins), but a
                        # project could still defeat it (e.g. a trailing `!.env`, or a nested
                        # .gitignore deeper in the tree). A safety mechanism that PRINTS
                        # "restored" while .env is still exposed is worse than none — it buys
                        # false confidence. So we re-ask git after writing and escalate loudly.
                        # Verify UNCONDITIONALLY. Gating this on `repaired` made the escalation
                        # ONE-SHOT: on the next sync the floor marker is already present, so
                        # patched_gitignore early-returns `repaired=False`, this block never runs,
                        # _SAFETY_FLOOR_FAILURES stays empty and main() exits 0 — permanently GREEN
                        # over a still-exposed .env. The operator shrugs off one red run and the
                        # mechanism goes quiet forever: exactly the false confidence it exists to
                        # remove. The state of the tree, not what we happened to do this run, is
                        # what must be asserted.
                        if _is_git_repo(project_dir) and not _git_covers_essentials(project_dir):
                            _SAFETY_FLOOR_FAILURES.append(project_dir.name)
                            print(
                                f"  ❌ {project_dir.name}: SAFETY FLOOR FAILED — .env is STILL not "
                                f"ignored after repair. A project rule is overriding it (look for a "
                                f"`!.env` negation or a nested .gitignore). FIX THIS BY HAND: a "
                                f"`git add -A` here can commit secrets."
                            )
                    file_results.append(
                        SyncResult("COPY", gitignore, gitignore, ".gitignore Fabrik-synced block")
                    )
                else:
                    file_results.append(
                        SyncResult("SKIP", gitignore, gitignore, "gitignore block current")
                    )
            except PermissionError:
                pass

        # Remove orphans from prior renames (docs that moved/consolidated).
        # Safe to delete: these were synced artifacts, never authored in projects.
        for stale_rel in (
            "docs/reference/fabrik-lifecycle.md",  # moved to docs/operations/
            "docs/reference/fabrik-project-catalog.md",  # consolidated into docs/BUSINESS_MODEL.md
            "docs/reference/windsurf/cascade-models.md",  # Cascade retired 2026-07-19; doc archived, pipeline dismantled 2026-07-20
        ):
            stale_path = project_dir / stale_rel
            if stale_path.exists():
                if not dry_run:
                    stale_path.unlink()
                file_results.append(
                    SyncResult("DELETE", stale_path, stale_path, "stale rename orphan")
                )

        # Write the per-project synced-files lock: the md5 of every synced file AS
        # DISTRIBUTED to THIS project. check_synced_unmodified compares a project's copy
        # against this lock (what it was given) — NOT live /opt/fabrik — so a project
        # merely BEHIND the advancing hub is never false-flagged; only a genuine local
        # edit (a file that differs from its recorded hash) fails. Best-effort: the
        # check degrades gracefully (skips) when the lock is absent.
        if not dry_run:
            try:
                lock = {
                    dest.relative_to(project_dir).as_posix(): compute_file_hash(dest)
                    for _src, dest in iter_synced_pairs(project_dir, FABRIK_ROOT)
                    if dest.exists()
                }
                lock_path = project_dir / ".fabrik" / "synced.lock"
                lock_path.parent.mkdir(parents=True, exist_ok=True)
                lock_path.write_text(json.dumps(lock, indent=0, sort_keys=True))
                file_results.append(
                    SyncResult(
                        "COPY", lock_path, lock_path, f".fabrik/synced.lock ({len(lock)} files)"
                    )
                )
            except Exception:
                pass  # lock is best-effort; never fail a sync over it

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
    # Reset the module-level tally. It is a mutable global; without this a second in-process call (a
    # future test, a wrapper, a dry-run-then-real flow) inherits the previous run's failures and returns
    # 1 forever.
    _SAFETY_FLOOR_FAILURES.clear()
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
        "archived",  # Archived projects — no longer active
        "fabrik-lib",  # Reference implementation store (vendor, don't depend)
        "fabrik-libs",  # Legacy name, kept for safety
        "mt-router",  # Standalone copy at /opt/mt-router (reference already in fabrik-lib)
        "fabrik-mail",  # fabrik-mail DATA store (<repo>/{inbox,archive} mailboxes) — NOT a project;
        # syncing governance into it pollutes the mailbox root (the `is_dir()` discovery would
        # otherwise adopt it). It is the operator-sanctioned neutral mail path, code lives in the hub.
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
    if _SAFETY_FLOOR_FAILURES:
        # FAIL the run. The floor was written and git still says `.env` is exposed — a project rule or a
        # nested .gitignore is overriding it. Exiting 0 here would report success over a live secret-leak
        # path, which is precisely the false confidence this whole mechanism exists to remove.
        print(
            f"\n❌ SAFETY FLOOR FAILED in {len(_SAFETY_FLOOR_FAILURES)} project(s): "
            f"{', '.join(_SAFETY_FLOOR_FAILURES)} — .env is still committable there. Fix by hand."
        )

    summary = f"Results: {success_count} projects synced, {fail_count} failed"
    summary += f" | Files: {total_copied} copied, {total_skipped} skipped"
    if total_warnings > 0:
        summary += f", {total_warnings} warnings (use --force to overwrite)"
    print(summary)

    if args.dry_run:
        print("\nDRY-RUN: No files were modified")

    return 0 if (fail_count == 0 and not _SAFETY_FLOOR_FAILURES) else 1


if __name__ == "__main__":
    sys.exit(main())
