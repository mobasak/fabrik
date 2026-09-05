#!/usr/bin/env python3
# AFTER-EDIT: docs/workflows/SYNC_ENFORCEMENT_WORKFLOW.md, tests/test_sync_worktree_adoption.py
"""Sync enforcement scripts to all /opt projects for Fabrik compliance.

Syncs to all /opt projects:
- Core scripts (6): final_gate.py, kilo_code_review.py, kilo_docs_enforcer.py,
  docs_updater.py, health_checker.py
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
import time
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
    RETIRED_CORE_SCRIPTS,
    RUN_SCRIPTS,
    RUN_SCRIPTS_SRC_DIR,
    SEED_IF_MISSING,
    VENDORED_DIRS,
    gitignore_block_text,
    iter_synced_pairs,
    worktreeinclude_text,
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

# Projects whose tracked .gitignore's "Fabrik-synced" block was (or, under --dry-run, would be)
# patched this run. Round 7, class 3: the REAL patch write touches every tracked .gitignore in
# ~45 projects and, before this, announced it nowhere the production wrapper's `tail -3` keeps —
# only a per-project stdout line existed, and only on the --dry-run branch. Rolled into the final
# `Results:` line for the same reason `_WORKTREE_TALLY` is (main()'s summary survives truncation;
# per-project prints do not).
_GITIGNORE_PATCHED: list[str] = []


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


def seed_git_workflow_config(project_dir: Path, dry_run: bool = False) -> None:
    """Seed `rerere.enabled` + `push.autoSetupRemote` LOCALLY on an EXISTING project —
    the SYNC half of D-114 (multi-agent-per-repo § Lifecycle "Adoption"). Scaffold owns
    fresh repos (`src/fabrik/scaffold.py:_configure_git_repo`, shipped `b7d7a727`); this
    is its twin for the ~46 repos that already exist and never ran the scaffolder's
    `git init` path.

    Same semantics, deliberately re-implemented rather than imported — `scaffold.py` is
    a hub-only module this project-writing script must never depend on:

    * LOCAL scope only — a `--global` write here would reach the hub and every worktree.
    * SEEDS, never enforces — a key the project already answered (on or off) is left
      alone; this sets a default, it does not overturn an operator's choice.
    * Best-effort — no git, no repo, unwritable: silently skip. A sync that otherwise
      succeeded must not fail over a config write.
    * Silent on a real run (this is a git-config write, not "a file" — it does not enter
      `file_results`, so it never perturbs the per-project COPY/SKIP tally). Under
      `--dry-run` it PRINTS what would change, since dry-run's whole job is to report.
    """
    if not _is_git_repo(project_dir):
        return
    # Same key order as scaffold.py:_configure_git_repo — kept identical so the two
    # config-seeding paths are indistinguishable in a `git config --list` dump.
    for key, value in (("push.autoSetupRemote", "true"), ("rerere.enabled", "true")):
        try:
            already = subprocess.run(
                ["git", "config", "--local", "--get", key],
                cwd=project_dir,
                capture_output=True,
            )
        except (OSError, subprocess.SubprocessError):
            return  # git absent / not executable — never fail a sync over config
        if already.returncode == 0:
            continue  # the project has answered this one — never overwrite it
        if dry_run:
            print(f"  Would set {key}={value}: {project_dir.name}")
            continue
        try:
            subprocess.run(
                ["git", "config", "--local", key, value],
                cwd=project_dir,
                capture_output=True,
            )
        except (OSError, subprocess.SubprocessError):
            return


def _project_worktree_dirs(project_dir: Path) -> list[Path]:
    """Linked worktrees this project currently has under `.claude/worktrees/` — the
    multi-agent-per-repo layout (design spec § Lifecycle "Adoption"). Discovered via
    `git worktree list --porcelain`, never a glob, so a worktree the operator moved,
    renamed, or already pruned is never double-counted or chased into a dangling path.
    """
    if not _is_git_repo(project_dir):
        return []
    try:
        out = subprocess.run(
            ["git", "worktree", "list", "--porcelain"],
            cwd=project_dir,
            capture_output=True,
            text=True,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    if out.returncode != 0:
        return []
    try:
        anchor = (project_dir / ".claude" / "worktrees").resolve()
        main = project_dir.resolve()
    except OSError:
        return []
    dirs: list[Path] = []
    for line in out.stdout.splitlines():
        if not line.startswith("worktree "):
            continue
        wt = Path(line[len("worktree ") :])
        try:
            wt = wt.resolve()
        except OSError:
            continue
        if wt == main:
            continue  # the main checkout itself — always the first porcelain entry
        try:
            wt.relative_to(anchor)
        except ValueError:
            continue  # a worktree living elsewhere is out of THIS project's layout
        if wt.is_dir():
            dirs.append(wt)
    return dirs


# The two secrets `.worktreeinclude` copies into a worktree — `worktreeinclude_text()`'s two
# `extra` patterns (`fabrik_synced_manifest.py`): a worktree needs both to run and neither is
# ever tracked in the MAIN checkout. `.env`/`.venv`/`__pycache__` are covered by
# `_ESSENTIAL_PATTERNS` on the MAIN checkout's tracked `.gitignore` (`patched_gitignore`); a
# linked worktree has its OWN tracked `.gitignore`, inherited from whatever branch it has
# checked out — often one cut before that protection existed. Measured 2026-09-05 across the
# 82 live worktrees on seo/trade-intelligence/web-ecommerce-factory (`git check-ignore -v` +
# `git ls-files --error-unmatch`, both read-only): `.mcp.json` is ignored in 0 of 82, TRACKED
# (already committed to that worktree's own branch — trade-intelligence, 23 of 23) in 23 of
# 82, and genuinely unprotected (unignored AND untracked — seo 28 + web-ecommerce-factory 31)
# in 59 of 82. `.env` is ignored in 82 of 82 — every one of those branches already carries its
# own `.env` rule; ONLY `.mcp.json` is at risk today. (Round-1 docstring wrongly generalized
# this to ".env is unignored there too" — corrected here, 2026-09-05 acceptance round 2.)
_WORKTREE_SECRET_PATTERNS = (".env", ".mcp.json")

_WORKTREE_EXCLUDE_MARKER = (
    "# Fabrik worktree secrets floor — DO NOT EDIT (seeded by sync_enforcement_to_projects.py)"
)
_WORKTREE_EXCLUDE_END = "# End Fabrik worktree secrets floor"

# The per-worktree ledger `resync_worktree_artifacts` writes AFTER copying — NOT the main
# checkout's `.fabrik/synced.lock` (which the worktree also receives a COPY of, listing
# every path the MAIN CHECKOUT manages, whether or not THIS worktree actually received it:
# a secret skipped by the check-ignore floor, a locally-modified file left alone without
# --force, or a copy that failed all show up in the main lock but were never written
# here). Reading the copied main lock as "proof this worktree received the file" is
# exactly the defect acceptance round 3 found: an agent's untracked edit to a synced
# path, left alone by the no-force rule, was deleted on the NEXT sync once the hub
# retired that path — because the copied main lock still named it. This ledger is the
# worktree's OWN record of what THIS resync actually wrote or verified byte-identical,
# keyed by project-root-relative path -> the hub's hash for that content, and only it is
# ever read as prune-authorization AND force-safety history (round 3, class 2: the hash
# lets `--force` distinguish "unmodified since the sync wrote it" from "an agent's live
# edit"). Defined here, ABOVE `_WORKTREE_SECRET_PATTERNS`'s old home, so both source
# tuples exist before `_WORKTREE_FLOOR_PATTERNS` below combines them (round 10, class 2:
# the combined tuple used to be re-typed as a literal at three call sites, with a FOURTH
# — `_worktree_would_ignore_after_seed` — silently using `_WORKTREE_SECRET_PATTERNS`
# alone, 2 of 3 patterns, latent only because its one caller never asks about the ledger
# path today).
_WORKTREE_LEDGER_REL = ".fabrik/worktree-synced.lock"

# The single combined floor — every pattern the shared `git-common-dir/info/exclude`
# protects, in EVERY worktree regardless of branch. One definition, four call sites
# (`_seed_worktree_secrets_exclude`, `_worktree_secrets_exclude_already_seeded`, the
# `Would seed …` disclosure in `resync_worktree_artifacts`, and
# `_worktree_would_ignore_after_seed`'s preview) — never re-typed as a literal tuple
# again.
#
# `.fabrik/synced.lock` (round 10, class 3 — a pool-filed item, reproduced live):
# `resync_worktree_artifacts` copies the MAIN checkout's fresh lock into every
# worktree unconditionally, but until this fix nothing seeded an ignore rule for
# it — a worktree cut from a branch whose OWN tracked `.gitignore` predates the
# manifest's addition of this path (round-something, main-checkout side) ended up
# with `?? .fabrik/` (untracked, unignored). Reproduced directly: a worktree built
# from a bare `AGENTS.md`-only commit (no `.gitignore` at all) received the lock
# via a full `sync_scripts_to_project` run, and `git status --porcelain` in that
# worktree showed `?? .fabrik/` with `git check-ignore -v .fabrik/synced.lock`
# returning exit 1 (not ignored) — a `git clean -fd` there would delete the lock,
# dropping that worktree's `check_synced_unmodified.py` to "not yet re-synced;
# skipped" instead of actually checking anything.
#
# `.fabrik/.ledger-tmp-*` (round 11, class 3): the round-10 age guard on
# `_write_worktree_ledger`'s reap (skip anything younger than 3600s, so a
# concurrent writer's still-live tempfile is never deleted out from under it —
# round 10, class 1) reopens the EXACT `?? .fabrik/` window this whole floor
# exists to close: for up to an hour after a SIGKILLed sync, its own
# `.ledger-tmp-*` sibling sits untracked AND unignored, and `git clean -fdn`
# names it. An anchored glob (valid `info/exclude` syntax) closes it without
# reopening the round-10 race — it ignores the FILE, never gates whether the
# reap is old enough to delete it.
_WORKTREE_FLOOR_PATTERNS = (
    *_WORKTREE_SECRET_PATTERNS,
    _WORKTREE_LEDGER_REL,
    ".fabrik/synced.lock",
    ".fabrik/.ledger-tmp-*",
)

# Cross-project tally for the worktree re-sync legs — module-level, the same pattern
# `_SAFETY_FLOOR_FAILURES` already uses for a cross-cutting concern `file_results`/
# `ProjectSyncResult` don't naturally carry. `main()` clears it at the start of a run and
# folds it into the final `Results:` summary line: the production wrapper
# (`scripts/governance_sync_postcommit.sh`) pipes the sync through `tail -3`, which drops
# every per-project worktree line (the count, the warnings) — only the LAST few lines of
# the whole run survive, and that final summary is one of them (class 5, round 2). Updated
# on BOTH real and dry-run calls (round 3, class 3): a single `main()` invocation is either
# entirely real or entirely `--dry-run` (one CLI flag for the whole run), so the numbers are
# never mixed — a `--dry-run` fire-rate sweep must show its would-be totals on the SAME
# final line the wrapper keeps, not just per-project prints that vanish under `tail -3`.
_WORKTREE_TALLY = {"projects": 0, "worktrees": 0, "files": 0, "warnings": 0, "deletions": 0}


def _seed_worktree_secrets_exclude(project_dir: Path) -> bool:
    """Idempotently seed `$(git rev-parse --git-common-dir)/info/exclude` with
    `_WORKTREE_SECRET_PATTERNS` plus `_WORKTREE_LEDGER_REL` (round 8, class 3),
    marker-guarded so a repeat sync never duplicates the block itself.

    `git-common-dir` is the ONE `.git` directory every worktree of a repo shares
    (`git worktree list` entries all point back to it) — unlike a worktree's own
    tracked `.gitignore`, which comes from whatever branch happens to be checked out
    there, `info/exclude` applies repo-wide: one write here protects the main checkout
    AND every worktree, present and future, regardless of branch. This is the
    mechanism the main-checkout safety floor (`patched_gitignore` / `_ESSENTIAL_PATTERNS`)
    cannot reach, because it patches a per-branch tracked file — and it is also the
    ONLY mechanism that can reach a worktree's own `_WORKTREE_LEDGER_REL`: the round-7
    fix added that path to the MAIN checkout's tracked `.gitignore` block, but a linked
    worktree evaluates its OWN branch's copy of that file, which a repo cut before the
    fix never has — measured live, 0 of 84 worktrees ignored the ledger (`?? .fabrik/`,
    `git clean -fdn` would remove it), while the SAME 84 all correctly ignored an older
    synced path seeded the same way, proving the shared-exclude mechanism itself is
    sound and the gap was purely "wrong file for this path".

    Called unconditionally on every real (non-dry-run) sync — including a project with
    NO worktrees today (class 7, round 2): seeding is cheap and idempotent, and a
    project's FIRST worktree, created between syncs, inherits protection immediately
    instead of waiting for the NEXT sync to seed it. Never called under `--dry-run`
    (it would write) — `_worktree_would_ignore_after_seed` previews the post-seed
    state read-only instead (round 3, class 4).

    The marker's mere PRESENCE used to be treated as "fully seeded, nothing left to
    do" (an early `return True`) — correct the day this function shipped, but it means
    a repo already seeded before a LATER pattern was added to `needed` would never
    pick it up on any future sync: the marker never changes, so it never re-fires
    (round 8, class 3 — caught before it could bite: 0 of 4 live sampled repos carry
    the marker yet, so today's landing is clean, but the next pattern this mechanism
    ever grows would have silently stranded every already-seeded repo forever). Now,
    when the marker IS present, each needed pattern is checked individually and any
    genuinely missing ones are appended as a small dated addendum — never duplicating
    the marker or END lines, which already exist.

    Best-effort, but no longer SILENT about failure (round 5, class 3 — the sibling of
    the c22bd91c safety-floor class: a write failure here left the per-file WARN
    telling the operator to "seed its checked-out branch's .gitignore", which cannot
    fix a permission failure on the SHARED `info/exclude` — naming the wrong cause
    sends the fix where it cannot land). A sync that otherwise succeeded still must
    not fail over this — `resync_worktree_artifacts` reports the failure itself and
    keeps going — and `_worktree_ignores` still verifies the result with a real
    `git check-ignore` before trusting it (a stale or overridden rule, e.g. a worktree
    branch's own negation, is caught there too).

    Returns True iff the floor is confirmed present after this call (already seeded,
    or freshly written/upgraded) — False iff git is unavailable or the write itself
    failed.
    """
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--git-common-dir"],
            cwd=project_dir,
            capture_output=True,
            text=True,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    if out.returncode != 0:
        return False
    common_dir = Path(out.stdout.strip())
    if not common_dir.is_absolute():
        common_dir = project_dir / common_dir
    exclude_path = common_dir / "info" / "exclude"
    # round 8, class 3: the ledger this whole worktree-safety design rests on
    # (`_WORKTREE_LEDGER_REL`) joins the secrets floor here — the shared exclude is
    # the only mechanism that reaches every worktree regardless of which branch it
    # has checked out. round 10, class 2: single-sourced from `_WORKTREE_FLOOR_PATTERNS`.
    needed = _WORKTREE_FLOOR_PATTERNS
    try:
        existing = exclude_path.read_text(encoding="utf-8") if exclude_path.exists() else ""
        if _WORKTREE_EXCLUDE_MARKER in existing:
            existing_lines = set(existing.splitlines())
            missing = [p for p in needed if p not in existing_lines]
            if not missing:
                return True  # every needed pattern already present — nothing to do
            prefix = "" if existing.endswith("\n") else "\n"
            # round 11, class 1: round 10 dropped the hardcoded "(round 8)" to stop
            # every future upgrade from wearing a stale round number — but an
            # UNDATED, UNVERSIONED header is the exact same defect from the other
            # side: two separate upgrades on the same repo (this pattern added
            # today, a DIFFERENT one added later) write byte-IDENTICAL header text,
            # so nothing distinguishes them (reproduced: two successive upgrades on
            # one fixture produced 2 occurrences of the same line). Stamp the
            # write-time DATE instead — unique per calendar day, and makes the
            # workflow doc's "a dated addendum" claim (SYNC_ENFORCEMENT_WORKFLOW.md)
            # actually true; the code never wrote a date before this.
            header = (
                f"# Fabrik worktree floor upgrade {datetime.now():%Y-%m-%d} — "
                f"pattern(s) added after this repo's first seed\n"
            )
            with exclude_path.open("a", encoding="utf-8") as f:
                f.write(prefix + header + "\n".join(missing) + "\n")
            return True
        block_lines = [
            _WORKTREE_EXCLUDE_MARKER,
            "# Every worktree of this repo shares this file (git-common-dir/info/exclude), so",
            "# this protects a worktree whose checked-out branch predates .env/.mcp.json rules,",
            "# a worktree whose branch predates the ledger-ignore fix too, the main checkout's",
            "# .fabrik/synced.lock (copied into every worktree), and the ledger writer's own",
            "# in-flight tempfile (left on disk for up to an hour by design — see the age guard).",
            *needed,
            _WORKTREE_EXCLUDE_END,
            "",
        ]
        prefix = "" if not existing or existing.endswith("\n") else "\n"
        exclude_path.parent.mkdir(parents=True, exist_ok=True)
        with exclude_path.open("a", encoding="utf-8") as f:
            f.write(prefix + "\n".join(block_lines))
        return True
    except OSError:
        return False


def _worktree_secrets_exclude_already_seeded(project_dir: Path) -> bool:
    """Read-only check: would `_seed_worktree_secrets_exclude` have NOTHING left to
    write for this project right now? Used ONLY under `--dry-run` (round 4, class 4)
    to print a `Would seed …` line exactly when a real run would actually write —
    `grep -ci exclude` over a live `--dry-run` transcript was 0 before this, so the
    first real run's write into every project's `git-common-dir/info/exclude` (45
    projects) was entirely undisclosed by the preview meant to show what a real run
    would do.

    round 8, class 3 mirror: the marker's mere PRESENCE is no longer sufficient proof
    of "nothing to do" — `_seed_worktree_secrets_exclude` now also upgrades an
    already-seeded repo missing a LATER pattern (e.g. `_WORKTREE_LEDGER_REL`, added
    after the marker mechanism first shipped). Treating marker-presence alone as
    "fully seeded" here, while the real function checks every needed pattern
    individually, would silently reintroduce the exact dry/real parity break round 8
    class 2 fixed elsewhere: a legacy-marker repo would get an undisclosed real
    upgrade write with no preceding `--dry-run` preview. Every needed pattern must
    already be present as its own line for this to report "nothing to do"."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--git-common-dir"],
            cwd=project_dir,
            capture_output=True,
            text=True,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return True  # can't tell — assume seeded so we never falsely promise a write
    if out.returncode != 0:
        return True
    common_dir = Path(out.stdout.strip())
    if not common_dir.is_absolute():
        common_dir = project_dir / common_dir
    exclude_path = common_dir / "info" / "exclude"
    try:
        if not exclude_path.exists():
            return False
        existing = exclude_path.read_text(encoding="utf-8")
        if _WORKTREE_EXCLUDE_MARKER not in existing:
            return False
        needed = _WORKTREE_FLOOR_PATTERNS  # round 10, class 2: single-sourced
        existing_lines = set(existing.splitlines())
        return all(p in existing_lines for p in needed)
    except OSError:
        return True


def _worktree_ignores(worktree_dir: Path, pattern: str) -> bool:
    """Ask git, from INSIDE the worktree, whether it actually ignores *pattern* — the
    only authority: a `.gitignore` rule, `info/exclude`, or a negation can each flip
    this, so seeding `info/exclude` is verified here rather than assumed."""
    try:
        proc = subprocess.run(
            ["git", "check-ignore", "-q", pattern],
            cwd=worktree_dir,
            capture_output=True,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return proc.returncode == 0


def _worktree_would_ignore_after_seed(worktree_dir: Path, pattern: str) -> bool:
    """Read-only preview of `_worktree_ignores` AS IF `_seed_worktree_secrets_exclude`
    had already run — used only under `--dry-run`, which must never write to the repo
    or worktree. Overlays `_WORKTREE_FLOOR_PATTERNS` (round 10, class 2: was
    `_WORKTREE_SECRET_PATTERNS` alone — 2 of 3 patterns, latent only because this
    function's one caller, `_worktree_secret_status`, never asks about the ledger path
    today) via `core.excludesFile` pointed at a THROWAWAY scratch file elsewhere on
    disk (never inside the repo/worktree, and removed immediately after) — git
    evaluates that file ALONGSIDE the worktree's real `.gitignore`/`info/exclude` with
    normal precedence, so a negation in the worktree's own rules still wins, exactly
    as it would after a real seed (round 3, class 4: without this, `--dry-run`
    reported all 59 genuinely-fixable `.mcp.json` cases as unfixable warnings the real
    run never emits, and never previewed the copies the real run makes once seeding
    protects them).
    """
    fd, scratch_path_str = tempfile.mkstemp(suffix=".exclude", text=True)
    try:
        with os.fdopen(fd, "w") as f:
            f.write("\n".join(_WORKTREE_FLOOR_PATTERNS) + "\n")
        proc = subprocess.run(
            ["git", "-c", f"core.excludesFile={scratch_path_str}", "check-ignore", "-q", pattern],
            cwd=worktree_dir,
            capture_output=True,
            check=False,
        )
        return proc.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False
    finally:
        try:
            os.unlink(scratch_path_str)
        except OSError:
            pass


def _worktree_secret_status(worktree_dir: Path, pattern: str, *, dry_run: bool = False) -> str:
    """Classify why *pattern* would land unprotected in *worktree_dir*, reusing the same
    tracked-vs-no-rule split `_uncovered_essentials` already established (c22bd91c):
    `git check-ignore` never reports a TRACKED path as ignored, however correct the
    rule is — so "seed an ignore rule" is not just unhelpful advice for a tracked
    secret, it is UNFIXABLE by that advice (measured: trade-intelligence has
    `.mcp.json` committed to 23 of 23 worktrees; the round-1 warning fired on every one
    of those every sync with no way to resolve it — class 2, round 2). Returns one of:
    - "ignored" — safe to copy, protected by a real ignore rule (or, under `dry_run`,
      by the rule the seed WOULD add — `_worktree_would_ignore_after_seed`).
    - "tracked" — already committed to this worktree's own branch history; copying our
      main checkout's current copy over it changes nothing about exposure (the secret
      is already IN that branch's git history regardless of what this sync does), so
      this is reported ONCE per project as an informational NOTE, never a per-worktree
      actionable WARN.
    - "unprotected" — genuinely unignored AND untracked: the real, fixable danger the
      WARN exists for.
    """
    ignored = (
        _worktree_would_ignore_after_seed(worktree_dir, pattern)
        if dry_run
        else _worktree_ignores(worktree_dir, pattern)
    )
    if ignored:
        return "ignored"
    try:
        tracked = subprocess.run(
            ["git", "ls-files", "--error-unmatch", "--", pattern],
            cwd=worktree_dir,
            capture_output=True,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return "unprotected"
    return "tracked" if tracked.returncode == 0 else "unprotected"


def _read_worktree_ledger(worktree_dir: Path) -> dict[str, str]:
    """THIS SPECIFIC worktree's OWN ledger (`_WORKTREE_LEDGER_REL`, written by a PRIOR
    resync — NEVER the copied main `.fabrik/synced.lock`), read BEFORE this run
    overwrites it: project-root-relative path -> the hash that path had when this
    resync last confirmed it present here.

    A worktree with no ledger yet (first-ever resync, or one from before this fix
    shipped) returns an EMPTY dict, so nothing is ever pruned or overwritten there —
    correct: there is no real history to prove the sync wrote or verified anything
    into THIS worktree at all. A legacy/list-shaped ledger (a bare list of paths, no
    hashes) is accepted for backward compatibility and treated as "known path, no
    verified hash" (empty-string sentinel) — membership alone is NEVER sufficient
    authorization for anything, on either the copy or the prune side (round 6, class
    1 correction: an earlier version of this comment said membership was enough to
    prune; it was not — a row's mere PRESENCE, without its hash matching what is
    actually on disk right now, could authorize deleting a file the sync last WARN'd
    about as a genuine edit, the instant the hub retired that path).
    """
    lock_path = worktree_dir / _WORKTREE_LEDGER_REL
    if not lock_path.exists():
        return {}
    try:
        data = json.loads(lock_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        # round 7, class 8: a corrupt ledger used to be read as an EMPTY history
        # completely silently — indistinguishable from a worktree's genuine
        # first-ever resync, so an operator had no way to tell "nothing here yet"
        # apart from "the ledger got corrupted and every row was just lost".
        print(f"  WARN: {lock_path} is not readable as a ledger ({e}) — treating as empty")
        # round 8, class 5: that print lives on a per-worktree line the production
        # wrapper's `tail -3` (scripts/governance_sync_postcommit.sh:82) discards,
        # and it never reached the module-level tally either, so it was also absent
        # from the `Results:` line that DOES survive truncation — a corrupt ledger
        # was invisible past the raw log. Bumped directly here (not via the
        # caller's `total_warned`, which does not exist yet at this point in the
        # per-worktree loop) so `main()`'s summary counts it exactly like every
        # other worktree WARN.
        _WORKTREE_TALLY["warnings"] += 1
        return {}
    if isinstance(data, list):
        return {p: "" for p in data if isinstance(p, str)}
    if isinstance(data, dict):
        return {k: v for k, v in data.items() if isinstance(k, str) and isinstance(v, str)}
    return {}


def _write_worktree_ledger(worktree_dir: Path, authored_rel: dict[str, str]) -> None:
    """Write THIS worktree's own ledger — every project-root-relative path this run
    actually confirmed present here (COPY/BACKUP, or already byte-identical), mapped
    to the hub's hash for that content — so the NEXT resync has real, worktree-
    specific, hash-verified proof of what it once wrote, never the broader
    main-checkout lock. Called ONLY on a real (non-dry-run) resync, after the copy
    loop.

    Written ATOMICALLY (round 6, class 3): a bare `write_text` truncates the file
    before writing the new content, so a process killed in between (OOM, SIGKILL, a
    host reboot) leaves invalid JSON on disk — `_read_worktree_ledger`'s
    `except (OSError, ValueError): return {}` then reads that as "no history at all",
    turning every path this worktree ever legitimately held into a permanent gap
    needing the manual bootstrap. Mirrors `_atomic_copy`: write to a temp file in the
    SAME directory (so the swap is atomic on the same filesystem), then `os.replace`
    it into place — the original ledger is either fully replaced or not touched at
    all, never partially. Best-effort: a ledger write that fails must not fail the
    whole sync.
    """
    try:
        lock_path = worktree_dir / _WORKTREE_LEDGER_REL
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        # round 9, class 5: a prior SIGKILL between `mkstemp()` and `os.replace()`/
        # `os.unlink()` below orphans a `.ledger-tmp-*` sibling nothing ever reaps —
        # it is not the ledger itself (`_read_worktree_ledger` never reads it) and
        # it carries no ignore rule either, so it sits forever as `?? .fabrik/` in
        # `git status` (`git clean -fdn` would remove it).
        #
        # round 10, class 1 CORRECTION: the round-9 comment's premise ("an orphan
        # has already lost its race") was wrong — this process is NOT the only
        # writer. `scripts/kilo-benchmarks/daily_refresh.sh` documents "the script
        # has no internal lock" (only the cron wrapper takes an flock);
        # `governance_sync_postcommit.sh`, fabrik-lib's `distribute_subagents.sh`
        # and `watch_enforcement_changes.sh` take none at all (`grep -c flock` = 0
        # in all three) — three hub sessions' post-commit hooks and the 06:00 cron
        # CAN run this concurrently. Reproduced live: process B's reap, run between
        # process A's `mkstemp()` (below) and A's `os.replace()`, deletes A's still-
        # live tempfile out from under it — `os.replace` then raises
        # `FileNotFoundError`, swallowed by the `except OSError: pass` below, and
        # A's entire ledger write silently vanishes: no row, no WARN, no tally
        # bump. A tempfile is stale BY AGE, never provably orphaned — only skip one
        # old enough that no legitimate writer could still be mid-swap on it.
        for stale in lock_path.parent.glob(".ledger-tmp-*"):
            try:
                if time.time() - stale.stat().st_mtime < 3600:
                    continue  # too young to be provably abandoned — a concurrent writer may own it
                stale.unlink()
            except OSError:
                pass
        payload = json.dumps(authored_rel, indent=0, sort_keys=True)
        fd, tmp_name = tempfile.mkstemp(dir=str(lock_path.parent), prefix=".ledger-tmp-")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(payload)
            os.replace(tmp_name, lock_path)
        except OSError:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
    except OSError:
        pass


def _worktree_file_is_tracked(worktree_dir: Path, rel: Path) -> bool:
    """Is *rel* (relative to *worktree_dir*) tracked by git in THIS worktree's own
    branch? A second, independent safety net alongside the ledger-membership check:
    even a path the sync's own ledger names is never pruned if the worktree's own
    branch has since committed it — that content is no longer the sync's to delete."""
    try:
        proc = subprocess.run(
            ["git", "ls-files", "--error-unmatch", "--", str(rel)],
            cwd=worktree_dir,
            capture_output=True,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return True  # fail closed — an unknown tracked-status file is never pruned
    return proc.returncode == 0


def _backup_worktree_file(path: Path, dst_root: Path, project_dir: Path) -> None:
    """Back up a worktree file — about to be pruned OR overwritten by a safe
    ledger-verified refresh — OUTSIDE the worktree's own tree. `create_backup` (used
    by every other copy/prune path in this script) writes `<name>.backup.<timestamp>`
    BESIDE the original — fine for the main checkout, but inside a live worktree that
    litter sits in the agent's own working directory forever: nothing ever cleans it
    (no ledger row records a `.backup.*` file, so it is never pruned either), and it
    dirties `git status` for content the agent never touched (round 4, class 6 fixed
    this for the PRUNE path only; round 6, class 2 extends it to the ledger-refresh
    COPY path in `_copy_into_worktree_safely`, which still called bare
    `create_backup` and produced exactly this litter). Written instead to
    `<project_dir>/.fabrik/backups/worktrees/<worktree-name>/<relative-path>.backup.<ts>`
    — outside the tree entirely, so the worktree stays exactly as clean as the
    operation left it. Best-effort: a backup that fails must not block the caller.
    """
    try:
        rel = path.relative_to(dst_root)
        backup_root = project_dir / ".fabrik" / "backups" / "worktrees" / dst_root.name
        # round 7, class 11: second-resolution timestamps collide when two backups
        # of the SAME path happen inside one run (e.g. a copy-refresh followed by a
        # later prune of the same file) — microseconds make that practically unique
        # without changing the naming convention.
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        backup_path = backup_root / f"{rel}.backup.{stamp}"
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, backup_path)
    except OSError:
        pass


def _copy_into_worktree_safely(
    src: Path,
    dst: Path,
    *,
    dry_run: bool,
    backup: bool,
    previously_authored_rel: dict[str, str],
    project_rel: str,
    dst_root: Path,
    project_dir: Path,
) -> SyncResult:
    """The ONLY way this script writes a file into a worktree — never a bare call to
    `sync_single_file`'s own comparison, whose ONLY protection against overwriting a
    locally-modified file is `dest_mtime > source_mtime`. That signal is DEFEATED in
    production (round 4, class 1, the fix superseding round 3's `_worktree_force_is_
    safe`): a governance commit rewrites the hub file, `shutil.copy2` propagates that
    FRESH mtime into the project's main checkout when the main-checkout leg re-syncs
    it, and `scripts/governance_sync_postcommit.sh` runs `--force` immediately after —
    so the agent's own edit, however recent, is almost always OLDER than the just-
    refreshed source. Measured live: 106 of 19,256 worktree file pairs are
    `exists_differ_older` (source newer than an agent-edited destination) and 0 are
    `mtime`-protected; a probe with an edit stamped 30 min old against a hub copy
    stamped now reported "Re-synced 8 file(s)", `AGENT EDIT LOST: True`, no WARN, no
    backup — identical with or without `--force`, because `sync_single_file`'s non-
    forced "source is newer" branch ALSO silently overwrites, mtime being the only
    gate either way.

    The gate here is a HASH comparison against THIS WORKTREE's OWN ledger
    (`previously_authored_rel`, from `_read_worktree_ledger`) — `--force` changes
    NOTHING about this decision, on either path:
    - *dst* missing → always safe, plain copy (nothing to clobber).
    - *dst* present, `hash(dst) == hash(src)` → already in sync, SKIP — this also
      closes round 3's class 8 (`--force` re-copying byte-identical files: ~19k
      needless writes fleet-wide per governance commit).
    - *dst* present, `hash(dst)` equals the ledger's RECORDED hash for this path
      (i.e. provably unmodified since a prior resync wrote it, even though the
      source has since changed) → safe to refresh; COPY, mtime never consulted.
    - *dst* present, hash differs from *src*, and THIS WORKTREE'S OWN ledger has NO
      row for this path at all → a LEDGER GAP, not necessarily an edit (round 5,
      class 2: measured live, 5 of 5 hash-sampled instances of this exact case on the
      first fleet run were stale copies from an older branch, not agent edits — the
      worktree's copy equalled the MAIN checkout at the time, just not the freshly-
      advanced hub). WARN, distinctly worded ("no ledger record … — left in place"),
      and left alone — the decision (never overwrite without proof) still stands, but
      the message must not claim an edit that was never made.
    - anything else (a hash matching neither the source nor a PRESENT ledger record)
      → a genuine, provable drift from what the sync last wrote: the agent's own
      edit. WARN, worded "differs from the ledger record — edit preserved", and left
      alone, unconditionally.

    **Bootstrapping a worktree stuck in the ledger-gap state:** this function will
    never overwrite it on its own — that decision does not change. An operator who
    has confirmed the worktree's copy carries no real edit clears the gap by hand:
    copy the MAIN CHECKOUT's current file over the worktree's copy at the same
    relative path (`cp <project>/<path> <worktree>/<path>`) and run the sync once —
    that resync's SKIP/COPY branch (hash now matches the fresh source) records a
    fresh ledger row, and the file converges normally on every run after.

    Mirror worth stating plainly (round 4, class 7): a file the agent deliberately
    DELETES from the worktree is recreated on the next resync — there is no ledger
    entry recording a delete, only ever "last known good content", so from this
    function's point of view a missing file is indistinguishable from one that was
    never there. This is the intentional mirror of the copy rule above (governed
    content always converges back to the hub's version), not a bug to route around.
    """
    if not dst.exists():
        return sync_single_file(src, dst, dry_run=dry_run, backup=backup, force=True)
    try:
        dst_hash = compute_file_hash(dst)
        src_hash = compute_file_hash(src)
    except OSError:
        return SyncResult("WARN", src, dst, "unreadable — left in place")
    if dst_hash == src_hash:
        return SyncResult("SKIP", src, dst, "identical")
    recorded_hash = previously_authored_rel.get(project_rel)
    if recorded_hash and recorded_hash == dst_hash:
        # Unmodified since the ledger recorded it — safe to refresh regardless of mtime.
        if dry_run:
            return SyncResult("COPY", src, dst, "worktree refresh (unmodified since ledger)")
        if backup:
            # round 6, class 2: was a bare `create_backup(dst)`, which litters
            # `<name>.backup.<ts>` BESIDE the file INSIDE the worktree — untracked,
            # no ledger row, never pruned, dirtying the agent's `git status` forever.
            # Route through the same outside-the-tree convention the prune path
            # already uses.
            _backup_worktree_file(dst, dst_root, project_dir)
        _atomic_copy(src, dst)
        return SyncResult("COPY", src, dst, "worktree refresh (unmodified since ledger)")
    if not recorded_hash:
        # round 7, class 6: a legacy list-shaped ledger's "" sentinel (no verified
        # hash — see _read_worktree_ledger) is NOT a `None`, so this branch used to
        # fall through to "differs from the ledger record — edit preserved", which
        # asserts a provable drift the sentinel can never actually prove. The prune
        # side already treats an empty sentinel as "no proof" (`if not recorded_
        # hash`); the copy side must use the same test.
        return SyncResult(
            "WARN",
            src,
            dst,
            "no ledger record (first sync, or a prior record was lost) — left in place",
        )
    return SyncResult("WARN", src, dst, "differs from the ledger record — edit preserved")


def _sync_dir_into_worktree(
    src_dir: Path,
    dst_dir: Path,
    *,
    dry_run: bool,
    backup: bool,
    dst_root: Path,
    previously_authored_rel: dict[str, str],
    project_dir: Path,
) -> tuple[int, list[SyncResult], list[SyncResult], dict[str, str]]:
    """Mirror *src_dir* (the MAIN CHECKOUT's own, already-current copy of a synced
    directory pattern) into *dst_dir* (that same pattern inside one worktree) file-by-
    file via `_copy_into_worktree_safely` — hash-vs-ledger, never mtime, `--force`
    irrelevant to the decision (round 4, class 1) — then prune *dst_dir* files with no
    counterpart left in *src_dir*, SAFELY. No `force` parameter here (round 5, class 6:
    it was threaded through from `resync_worktree_artifacts` but never referenced in
    this function's body — dead weight, dropped); the public
    `resync_worktree_artifacts` signature still accepts `force` for API symmetry with
    every other copy leg in this script, so callers need not special-case the
    worktree legs, but nothing below this point ever reads it.

    A destination FILE is pruned as an orphan ONLY when ALL of:
    - it has no counterpart at the same relative path in *src_dir* (the obvious part);
    - its project-root-relative path is a key in THIS WORKTREE's own ledger
      (`previously_authored_rel`, from `_read_worktree_ledger` — the worktree's OWN
      record of what a PRIOR resync actually wrote here, never the copied main lock);
    - **its CURRENT on-disk hash still equals the ledger's recorded hash for that
      path** (round 6, class 1 — REGRESSION FIX: round 5's ledger merge made rows
      survive forever, including a row for a path the sync last WARN'd about — i.e.
      genuinely edited by the agent. Membership alone was then enough to authorize a
      prune: once the hub retired that path, the file vanished — the agent's edit,
      not an orphan — with `--backup` never armed in production. A file whose disk
      content no longer matches its own ledger row is exactly as suspect as one with
      no row at all, and gets the SAME treatment: WARN, never delete);
    - it is NOT currently tracked by git in the worktree's own branch (a second,
      independent net — `_worktree_file_is_tracked`).
    A now-empty DIRECTORY is removed only when the ledger proves the sync populated
    it (at least one of its files was previously authored under that path) — a
    directory can never look "empty" while a hash-mismatched file inside it survives
    the check above, so no separate hash gate is needed at the directory level.

    Emptiness for BOTH files and directories is judged against the WOULD-BE state —
    files already queued for deletion this pass count as gone even under `--dry-run`,
    when nothing has actually been unlinked yet (round 4, class 5: checking the tree
    "as it stands" undercounted a directory that only becomes empty once its own
    child file is pruned in the SAME pass — 1 deletion reported under `--dry-run`
    where a real run performs 2).

    Every real or would-be deletion is backed up first when `backup=True`, written
    OUTSIDE the worktree via `_backup_worktree_file` (round 4, class 6 — litter
    beside the pruned file inside a live worktree is never cleaned), and returned as
    a `SyncResult("DELETE", ...)` so `--dry-run` can preview it without deleting.

    `__pycache__`/`.pyc` are skipped on both the copy and the prune side, mirroring
    the VENDORED_DIRS leg this function otherwise duplicates: those are build noise
    the sync never manages either way.

    BOTH loops isolate a per-item `OSError` to that one item (round 6, class 5): a
    transient failure (a locked subdir, a permission blip) used to propagate all the
    way out of this function, so the CALLER's outer `except OSError` discarded this
    function's entire `authored` map even for files ALREADY written to disk earlier
    in the SAME call — a file the copy loop had just successfully refreshed then kept
    its OLD ledger hash forever (never matching either the source or the disk), WARN-
    ing "differs from the ledger record" on the sync's OWN write, permanently. Now
    every file's outcome (COPY/SKIP/WARN, or an isolated error) is recorded as it
    happens, so a failure elsewhere never erases progress already made.

    Returns `(files copied, DELETE SyncResults — real or would-be, WARN SyncResults,
    the project-root-relative path -> hash map this run confirmed present here — for
    the caller to fold into the NEW ledger)`. A `WARN` (a locally modified
    destination, left alone) is surfaced rather than silently discarded and is
    deliberately NEVER added to the authored map: the resync did not actually touch
    that file this run, so it must not be treated as sync-owned history either.
    """
    copied = 0
    warnings: list[SyncResult] = []
    authored: dict[str, str] = {}
    live_source_rel: set[Path] = set()
    for src_file in src_dir.rglob("*"):
        if not src_file.is_file():
            continue
        if "__pycache__" in src_file.parts or src_file.suffix == ".pyc":
            continue
        rel = src_file.relative_to(src_dir)
        live_source_rel.add(rel)
        dst_file = dst_dir / rel
        project_rel = dst_file.relative_to(dst_root).as_posix()
        try:
            result = _copy_into_worktree_safely(
                src_file,
                dst_file,
                dry_run=dry_run,
                backup=backup,
                previously_authored_rel=previously_authored_rel,
                project_rel=project_rel,
                dst_root=dst_root,
                project_dir=project_dir,
            )
            if result.action in ("COPY", "BACKUP"):
                copied += 1
                authored[project_rel] = compute_file_hash(src_file)
            elif result.action == "SKIP":
                authored[project_rel] = compute_file_hash(src_file)
            elif result.action == "WARN":
                warnings.append(result)
        except OSError as e:
            # Isolated to THIS file — every file processed before this one keeps its
            # result (round 6, class 5). Never silently dropped either.
            warnings.append(SyncResult("WARN", src_file, dst_file, f"error copying: {e}"))
            continue

    deletions: list[SyncResult] = []
    removed_paths: set[Path] = set()
    if dst_dir.exists():
        for existing in sorted(dst_dir.rglob("*"), reverse=True):
            try:
                if existing.is_file():
                    if "__pycache__" in existing.parts or existing.suffix == ".pyc":
                        continue
                    rel = existing.relative_to(dst_dir)
                    if (src_dir / rel).exists():
                        continue  # still live in the main checkout
                    project_rel = existing.relative_to(dst_root).as_posix()
                    recorded_hash = previously_authored_rel.get(project_rel)
                    if not recorded_hash:
                        continue  # never proven (by THIS worktree's own ledger) to be sync-managed
                    if _worktree_file_is_tracked(dst_root, existing.relative_to(dst_root)):
                        continue  # committed to the worktree's own branch — not the sync's to remove
                    current_hash = compute_file_hash(existing)
                    if current_hash != recorded_hash:
                        # round 6, class 1: the row's mere presence is not proof —
                        # it must still match what is ACTUALLY on disk. A row
                        # surviving from before a genuine edit (the round-5 merge
                        # keeps unadjudicated rows on purpose) is not license to
                        # delete; treat it exactly like a copy-side drift.
                        warnings.append(
                            SyncResult(
                                "WARN",
                                existing,
                                existing,
                                "differs from the ledger record — left in place, not pruned",
                            )
                        )
                        continue
                    if backup and not dry_run:
                        _backup_worktree_file(existing, dst_root, project_dir)
                    # round 7, class 2: `unlink` used to run AFTER the DELETE result
                    # was already recorded — an EPERM here left the file on disk
                    # while the caller still printed "Deleted orphan", counted it
                    # removed, and popped its ledger row (the per-item try/except
                    # above catches the exception, but only the code UNDER it in
                    # THIS block is protected). Unlink first, inside the same guard:
                    # a failure here never reaches the report/pop below at all.
                    if not dry_run:
                        existing.unlink()
                    deletions.append(
                        SyncResult("DELETE", existing, existing, "orphan removed (worktree)")
                    )
                    removed_paths.add(existing)
                elif existing.is_dir():
                    rel_dir = existing.relative_to(dst_root).as_posix()
                    # Only remove a directory the ledger proves the sync once
                    # populated — never bulldoze one a coding agent created for its
                    # own reasons that merely happens to be empty right now.
                    # round 7, class 9: `p == rel_dir` accepted a FILE row as proof
                    # the sync owns a DIRECTORY at that exact path — a retired file
                    # row and a same-named directory an agent later created there
                    # are two different objects; only a row for a file UNDER this
                    # directory (a real prefix match) is ownership of the directory.
                    ledger_owns_dir = any(
                        p.startswith(rel_dir + "/") for p in previously_authored_rel
                    )
                    if not ledger_owns_dir:
                        continue
                    # Effective emptiness = every remaining child is itself
                    # something already being removed this pass (real: already
                    # unlinked from disk by this point anyway; dry-run: simulated
                    # via removed_paths, since nothing has actually been unlinked)
                    # — AND no live source file is expected to land under this
                    # directory. The second check matters ONLY under --dry-run: a
                    # brand-new file the copy loop above would have written is
                    # never physically materialized there (dry-run writes
                    # nothing), so a directory whose sole live content is such a
                    # not-yet-existing file would otherwise look empty on disk
                    # when a real run would keep it populated.
                    rel_from_dst_dir = existing.relative_to(dst_dir)
                    if any(
                        rel_from_dst_dir == p or rel_from_dst_dir in p.parents
                        for p in live_source_rel
                    ):
                        continue
                    children = list(existing.iterdir())
                    if any(child not in removed_paths for child in children):
                        continue
                    if dry_run:
                        deletions.append(
                            SyncResult("DELETE", existing, existing, "empty dir (worktree)")
                        )
                        removed_paths.add(existing)
                        continue
                    existing.rmdir()
                    deletions.append(
                        SyncResult("DELETE", existing, existing, "empty dir removed (worktree)")
                    )
                    removed_paths.add(existing)
            except OSError as e:
                # Isolated to THIS path — a transient failure here (round 6, class 5,
                # e.g. the exact class 1 reproduction's `.exists()` raising) must
                # never discard the copy loop's already-accumulated `authored` map
                # for every OTHER file in this pattern.
                warnings.append(SyncResult("WARN", existing, existing, f"error during prune: {e}"))
                continue
    return copied, deletions, warnings, authored


def resync_worktree_artifacts(
    project_dir: Path,
    dry_run: bool = False,
    *,
    backup: bool = False,
    force: bool = False,
) -> int:
    """R3 (design spec § Lifecycle "Synced-file drift inside a live worktree") —
    CORRECTED premise, round 1: `.fabrik/synced.lock` is NOT one of the ~55 patterns
    `worktreeinclude_text()` emits, so a worktree created before this function existed
    has NO lock at all, and `check_synced_unmodified.py` reports "not yet re-synced;
    skipped" — it is SKIPPED, never falsely green against a stale copy. This function
    closes that honestly: it is called (see `sync_scripts_to_project`) AFTER the main
    checkout's lock is freshly written, and copies that fresh lock into every worktree
    alongside the rest of the set, so the worktree's own `check_synced_unmodified.py`
    run has something real to compare against for the first time.

    `.worktreeinclude` copies its gitignored set into a linked worktree ONLY at Claude
    Code's own creation-time hook — a sync landing mid-epic otherwise updates the MAIN
    checkout alone. This re-copies the SAME set `.worktreeinclude` was built from
    (`fabrik_synced_manifest.worktreeinclude_text()`, not a second list) plus the lock,
    from the project's main checkout into every worktree it currently has under
    `.claude/worktrees/` (comment/header lines and blanks are skipped; a pattern with no
    live source is silently skipped, exactly like `.worktreeinclude`'s own creation-time
    copy skips a pattern that doesn't exist).

    SECURITY: `.env` and `.mcp.json` are copied only when `_worktree_secret_status`
    classifies THIS worktree's copy as "ignored" — a "tracked" secret (already
    committed to that worktree's own branch — no ignore rule can undo that) is noted
    ONCE per project, never a per-worktree WARN; a genuinely "unprotected" one
    (unignored AND untracked) is skipped and warned, never silently copied. Under
    `--dry-run`, classification simulates the post-seed state read-only instead of
    reading pre-seed reality, so the preview matches what a real run would actually
    do — and a `Would seed …` line is printed once per project when the shared
    `info/exclude` floor has not been seeded yet (round 4, class 4: this write into
    every project's `git-common-dir` was previously undisclosed by `--dry-run`).

    EVERY file copied into a worktree goes through `_copy_into_worktree_safely` — a
    HASH comparison against THIS WORKTREE's OWN ledger, identical whether `--force`
    is set or not (round 4, class 1, BINDING orchestrator decision, superseding round
    3's mtime-adjacent `_worktree_force_is_safe`): a destination is overwritten only
    when it is byte-identical to what the ledger recorded the sync writing there last
    time; anything else — including a modified destination that happens to be OLDER
    than the newly-synced source, the common production shape once a governance
    commit refreshes the hub file's mtime — is WARN'd and left alone. `--force`
    changes nothing about this; it exists for the OTHER synced legs in this script.

    ORPHAN PRUNING inside a worktree's directory-shaped patterns only removes a file
    (or a now-empty directory) THIS WORKTREE'S OWN ledger (`_WORKTREE_LEDGER_REL`,
    written by a prior resync — NEVER the copied main `.fabrik/synced.lock`, which
    lists every path the MAIN checkout manages, not what THIS worktree actually
    received) proves the sync itself wrote here AND that isn't tracked by that
    worktree's own git. Every deletion is backed up first under `--backup` — OUTSIDE
    the worktree tree, see `_backup_worktree_file` — and reported (real or,
    under `--dry-run`, would-be, with emptiness judged against the would-be state,
    not the tree as it stands — see `_sync_dir_into_worktree`). After the copy loop,
    THIS worktree's ledger is rewritten with exactly what was confirmed present this
    run (path -> hash), for the next resync. Mirror worth stating: a file the agent
    deliberately deletes from a synced directory is recreated on the next resync —
    defensible for governance content the sync exists to keep current, not a bug.

    A locally modified worktree file left alone is surfaced — printed and counted in
    the tally's warnings, under `--dry-run` too — never silently dropped.

    `--dry-run` runs the SAME enumeration as a real sync — every copy, prune
    candidate and secret classification is evaluated as realistically as a read-only
    pass allows — but writes nothing (`_seed_worktree_secrets_exclude` and
    `_write_worktree_ledger` are both skipped entirely; every other check reads
    current state or a throwaway scratch file elsewhere on disk).

    The real (or, under `--dry-run`, would-be) per-run file/deletion/warning totals
    are printed AFTER every worktree has been processed, never before, and are always
    folded into the module-level `_WORKTREE_TALLY`, which `main()` adds to its final
    `Results:` summary line — the one line that survives the production wrapper's
    `tail -3` (`scripts/governance_sync_postcommit.sh:82`) — and which
    `sync_scripts_to_project` diffs to fold the same numbers into the PER-PROJECT
    line too. See also `docs/workflows/SYNC_ENFORCEMENT_WORKFLOW.md` § Worktree
    re-sync, kept in lockstep with this function (round 4, class 3).

    Returns the worktree count.
    """
    worktrees = _project_worktree_dirs(project_dir)

    floor_seed_failed = False
    if not dry_run:
        # Seed unconditionally, even with no worktrees today — cheap, idempotent, and
        # it protects this project's very FIRST worktree the moment it exists rather
        # than leaving it exposed until the sync runs again. Never under --dry-run:
        # it would write.
        #
        # round 8, class 2: `_seed_worktree_secrets_exclude` also returns False for a
        # NON-GIT `/opt` directory (`git rev-parse --git-common-dir` fails, exactly
        # like a real permission failure would) — measured live: 4 of 45 projects
        # (emailgateway, logo-export, scratch_bhd, test-saas-for-epic-wf, the same 4
        # `--dry-run` never prints "Would seed" for) WARNed "the shared info/exclude
        # floor could not be written (permission)" on EVERY real sync, wrong cause —
        # there is no floor to write because there is no git repo at all, and no
        # worktree can ever exist there either. Guarded on `_is_git_repo` exactly like
        # `seed_git_workflow_config` and `_project_worktree_dirs` already are, so the
        # non-git leg is silent on both --dry-run and a real run — parity restored —
        # while a genuine permission failure on an actual git repo still WARNs.
        floor_seed_failed = _is_git_repo(project_dir) and not _seed_worktree_secrets_exclude(
            project_dir
        )
        if floor_seed_failed:
            print(
                f"  ⚠️  {project_dir.name}: the shared info/exclude floor could not be "
                f"written (permission) — secrets copied into any worktree this run may "
                f"be unprotected until this is fixed by hand."
            )
    elif not _worktree_secrets_exclude_already_seeded(project_dir):
        # round 9, class 1: this hardcoded "(.env, .mcp.json) — first real run only"
        # went false in TWO ways the moment round 8 landed — the real write now
        # seeds THREE patterns (the ledger too), and on a legacy-marker repo it is
        # no longer a first-ever write at all, but an UPGRADE appending the missing
        # pattern under an already-present marker. Render the actual pattern list
        # and name both possibilities. round 10, class 2: single-sourced.
        needed_patterns = ", ".join(_WORKTREE_FLOOR_PATTERNS)
        print(
            f"  Would seed {project_dir.name}'s shared git-common-dir/info/exclude "
            f"with the worktree floor ({needed_patterns}) — first real run, or an "
            f"upgrade of an already-seeded repo missing a newer pattern"
        )

    if not worktrees:
        return 0

    patterns = [
        line
        for line in worktreeinclude_text().splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    if ".fabrik/synced.lock" not in patterns:
        patterns = [*patterns, ".fabrik/synced.lock"]

    total_copied = 0
    total_deleted = 0
    total_warned = 0
    noted_tracked: set[str] = set()

    for wt in worktrees:
        # Read THIS worktree's OWN ledger — never the copied main lock — BEFORE
        # anything this run touches it. It is the only safe historical record of what
        # a PRIOR resync actually wrote into THIS worktree.
        previously_authored_rel = _read_worktree_ledger(wt)
        # MERGE, never rebuild (round 5, class 1): seed from the previous ledger so a
        # row this run never gets to re-adjudicate (a pattern that errors out midway,
        # e.g. a transient OSError on a locked subdir) SURVIVES rather than being
        # silently dropped when the ledger is rewritten below. A stale recorded hash
        # can never authorize overwriting an agent's genuinely different edit (the
        # hash comparison in `_copy_into_worktree_safely` still has to match), so
        # carrying old rows forward is safe — the prior version instead REBUILT the
        # ledger from only what THIS run touched, so one crashed pattern wiped every
        # row for every OTHER pattern too (measured: a 2-row ledger -> [] on the next
        # write, after which the worktree never converged to the hub again with no
        # visible cause).
        authored_this_run: dict[str, str] = dict(previously_authored_rel)

        for pattern in patterns:
            is_dir_pattern = pattern.endswith("/")
            rel = pattern.rstrip("/") if is_dir_pattern else pattern
            src = project_dir / rel
            if not src.exists():
                continue
            if rel in _WORKTREE_SECRET_PATTERNS:
                status = _worktree_secret_status(wt, rel, dry_run=dry_run)
                if status == "tracked":
                    if rel not in noted_tracked:
                        noted_tracked.add(rel)
                        print(
                            f"  NOTE {project_dir.name}: {rel} is committed to at least one "
                            f"worktree's own branch already — an ignore-rule fix cannot "
                            f"un-commit it, so this is not treated as a fixable warning."
                        )
                    continue
                if status == "unprotected":
                    total_warned += 1
                    if floor_seed_failed:
                        # The sibling of the c22bd91c safety-floor class: naming the
                        # wrong cause sends the operator where the fix cannot land
                        # (round 5, class 3). The correct rule IS a no-rule case
                        # here — the shared floor never got written — so pointing at
                        # the worktree's own branch .gitignore would be wrong advice.
                        print(
                            f"  ⚠️  {wt}: {rel} is NOT ignored in this worktree — "
                            f"skipping the copy (would expose a secret unprotected). "
                            f"CAUSE: the shared info/exclude floor could not be written "
                            f"(permission) — fix that, not this worktree's .gitignore."
                        )
                    else:
                        print(
                            f"  ⚠️  {wt}: {rel} is NOT ignored in this worktree — "
                            f"skipping the copy (would expose a secret unprotected). Seed "
                            f"its checked-out branch's .gitignore or resolve the "
                            f"overriding rule by hand."
                        )
                    continue
            dst = wt / rel
            try:
                if src.is_dir():
                    copied, deletions, dir_warnings, authored = _sync_dir_into_worktree(
                        src,
                        dst,
                        dry_run=dry_run,
                        backup=backup,
                        dst_root=wt,
                        previously_authored_rel=previously_authored_rel,
                        project_dir=project_dir,
                    )
                    total_copied += copied
                    authored_this_run.update(authored)
                    for deletion in deletions:
                        total_deleted += 1
                        verb = "Would delete" if dry_run else "Deleted"
                        # round 7, class 9: print the real reason (a directory
                        # deletion's is "empty dir removed (worktree)", never the
                        # file-pruning wording) instead of a hardcoded "orphan".
                        print(f"  {verb} ({deletion.reason}): {deletion.destination}")
                        # A pruned path is no longer sync-owned content — never leave
                        # a zombie ledger entry that could later authorize treating an
                        # unrelated future file at the same path as "already ours".
                        try:
                            pruned_rel = deletion.destination.relative_to(wt).as_posix()
                        except ValueError:
                            pruned_rel = None
                        if pruned_rel is not None:
                            authored_this_run.pop(pruned_rel, None)
                    for w in dir_warnings:
                        total_warned += 1
                        print(f"  WARN (worktree, {w.reason}): {w.destination}")
                else:
                    result = _copy_into_worktree_safely(
                        src,
                        dst,
                        dry_run=dry_run,
                        backup=backup,
                        previously_authored_rel=previously_authored_rel,
                        project_rel=rel,
                        dst_root=wt,
                        project_dir=project_dir,
                    )
                    if result.action in ("COPY", "BACKUP"):
                        total_copied += 1
                        authored_this_run[rel] = compute_file_hash(src)
                    elif result.action == "SKIP":
                        authored_this_run[rel] = compute_file_hash(src)
                    elif result.action == "WARN":
                        total_warned += 1
                        print(f"  WARN (worktree, {result.reason}): {dst}")
            except OSError as e:
                # round 5, class 1: this used to be a SILENT continue — nothing
                # printed, no counter moved, and whatever partial `authored` map the
                # crashed leg was building got discarded with it. Still best-effort
                # (one bad pattern must not abort the whole worktree), but now VISIBLE:
                # printed and counted like every other WARN, so an operator has a
                # trail instead of a worktree that quietly stops converging.
                total_warned += 1
                print(f"  WARN (worktree, error processing {rel}: {e}): {wt}")
                continue

        if not dry_run:
            # round 7, class 10: reap zombie rows — a path whose MAIN CHECKOUT
            # source has been retired AND whose worktree file the agent has
            # independently deleted is never iterated by the prune loop above (it
            # walks EXISTING destination files only), so its row would otherwise
            # survive the merge forever — the exact zombie the pop-on-delete
            # comment above says must not exist, just reached a different way.
            # Nothing left to copy (no source) and nothing left to protect (no
            # destination): the row asserts nothing true about this worktree
            # anymore.
            for zombie_rel in list(authored_this_run):
                try:
                    source_gone = not (project_dir / zombie_rel).exists()
                    dest_gone = not (wt / zombie_rel).exists()
                except OSError:
                    continue  # can't verify — never reap a row we're unsure about
                if source_gone and dest_gone:
                    del authored_this_run[zombie_rel]
            # THIS worktree's own record of what was actually confirmed present here
            # this run — never the copied main lock — for the NEXT resync's prune and
            # copy-safety checks.
            _write_worktree_ledger(wt, authored_this_run)

    verb = "Would re-sync" if dry_run else "Re-synced"
    orphan_word = "orphan(s) would be removed" if dry_run else "orphan(s) removed"
    print(
        f"  {verb} {total_copied} file(s) into {len(worktrees)} "
        f"linked worktree(s): {project_dir.name}"
        + (f", {total_deleted} {orphan_word}" if total_deleted else "")
        + (f", {total_warned} warning(s)" if total_warned else "")
    )
    _WORKTREE_TALLY["projects"] += 1
    _WORKTREE_TALLY["worktrees"] += len(worktrees)
    _WORKTREE_TALLY["files"] += total_copied
    _WORKTREE_TALLY["warnings"] += total_warned
    _WORKTREE_TALLY["deletions"] += total_deleted
    return len(worktrees)


def _uncovered_essentials(project_dir: Path) -> list[tuple[str, str]]:
    """Which floor patterns git does NOT ignore here — the names the failure message must carry."""
    missing: list[str] = []
    for pattern in _ESSENTIAL_PATTERNS:
        try:
            proc = subprocess.run(  # noqa: S603 — fixed argv, no shell
                ["git", "check-ignore", "-q", pattern],
                cwd=project_dir,
                capture_output=True,
                check=False,
            )
        except OSError:
            return [(pat, "no-rule") for pat in _ESSENTIAL_PATTERNS]
        if proc.returncode == 0:
            continue

        # WHY the pattern is uncovered decides the REMEDY, and the two causes need opposite
        # actions. `git check-ignore` consults the index: a TRACKED path is never reported as
        # ignored, however correct the rule is. So a failure here means either
        #   (a) no rule matches — a negation, a nested .gitignore, or a missing line; fix the
        #       .gitignore; or
        #   (b) a rule matches perfectly but the path is already COMMITTED — editing the
        #       .gitignore can never fix it; the path must leave the index.
        # `--no-index` evaluates the rules alone, which separates them. Measured 2026-09-05 on
        # /opt/proxy: 1,341 tracked files under `.venv/` with a correct `.venv/` rule at line 6
        # — this function reported it as uncovered and the caller told the operator to hunt for
        # an overriding rule that does not exist.
        try:
            rule_only = subprocess.run(  # noqa: S603 — fixed argv, no shell
                ["git", "check-ignore", "-q", "--no-index", pattern],
                cwd=project_dir,
                capture_output=True,
                check=False,
            )
        except OSError:
            missing.append((pattern, "no-rule"))
            continue
        missing.append((pattern, "tracked" if rule_only.returncode == 0 else "no-rule"))
    return missing


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


def prune_retired_scripts(scripts_dir: Path, dry_run: bool = False) -> list[SyncResult]:
    """Delete project copies of RETIRED_CORE_SCRIPTS (M0 shrink ruling mechanism).

    Delisting a script from CORE_SCRIPTS is not retirement by itself: the regenerated
    gitignore block stops covering the name, so a left-behind copy surfaces as
    untracked noise in every project. The hub keeps the canonical copy, revivable,
    under scripts/archived/.
    """
    results: list[SyncResult] = []
    for name in RETIRED_CORE_SCRIPTS:
        dest = scripts_dir / name
        if dest.is_file():
            if not dry_run:
                dest.unlink()
            results.append(SyncResult("DELETE", dest, dest, "retired core script pruned"))
    return results


def sync_single_file(
    source: Path,
    destination: Path,
    *,
    dry_run: bool = False,
    backup: bool = False,
    force: bool = False,
    seed_if_missing: bool = False,
) -> SyncResult:
    """Sync a single file with hash comparison and optional backup.

    Args:
        source: Source file path
        destination: Destination file path
        dry_run: If True, report only without writing
        backup: If True, create timestamped backup before overwriting
        force: If True, skip hash comparison and always overwrite — EXCEPT a
            seed_if_missing destination, which force never touches (see below)
        seed_if_missing: If True, an EXISTING destination is skipped unconditionally —
            including under --force. The dest is project-owned DATA the moment it exists
            (manifest SEED_IF_MISSING: the decision ledger holds per-repo rows; any
            overwrite is data loss). Copy happens only via the not-exists branch below.

    Returns:
        SyncResult with action taken and details
    """
    # Seed-class short-circuit BEFORE the symlink/force branches: an existing dest is
    # untouchable, whatever else the flags say.
    if seed_if_missing and destination.exists() and not destination.is_symlink():
        return SyncResult("SKIP", source, destination, "seed-if-missing: project-owned")
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

        # Prune RETIRED core scripts — delisting alone leaves an orphan copy that the
        # regenerated gitignore block no longer covers (untracked noise in ~46 repos).
        file_results.extend(prune_retired_scripts(scripts_dir, dry_run=dry_run))

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
                if not dry_run:
                    destination.parent.mkdir(parents=True, exist_ok=True)
                result = sync_single_file(
                    source,
                    destination,
                    dry_run=dry_run,
                    backup=backup,
                    force=force,
                    seed_if_missing=dest_rel in SEED_IF_MISSING,
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

        # Seed the two git config keys the multi-agent-per-repo workflow assumes
        # (design spec § Lifecycle "Adoption") — existing projects too, not just fresh
        # scaffolds (scaffold.py's `_configure_git_repo` covers ONLY repo creation).
        seed_git_workflow_config(project_dir, dry_run=dry_run)

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
                    if dry_run:
                        # round 6, class 7: this write reaches every project's
                        # TRACKED .gitignore on the next real run (45 dirty trees)
                        # and `check_synced_unmodified` never flags it (.gitignore
                        # is not itself in synced.lock) — the default `--dry-run`
                        # preview named it nowhere (`grep -c "Fabrik-synced block"`
                        # was 0 without `--verbose`). Named here, unconditionally,
                        # matching the round-4 precedent that a fleet-wide write
                        # earns its own preview line.
                        print(
                            f"  Would patch {project_dir.name}'s .gitignore "
                            f"(Fabrik-synced block) — the tracked block is stale"
                        )
                        _GITIGNORE_PATCHED.append(project_dir.name)
                    if not dry_run:
                        if backup:
                            create_backup(gitignore)
                        gitignore.write_text(new)
                        # round 7, class 3: the real write gets the same disclosure the
                        # --dry-run preview already had — previously silent on this path.
                        print(
                            f"  Patched {project_dir.name}'s .gitignore "
                            f"(Fabrik-synced block) — the tracked block was stale"
                        )
                        _GITIGNORE_PATCHED.append(project_dir.name)
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
                            missing = _uncovered_essentials(project_dir)
                            tracked = [pat for pat, why in missing if why == "tracked"]
                            unruled = [pat for pat, why in missing if why != "tracked"]
                            names = ", ".join(pat for pat, _ in missing) or "a floor pattern"
                            print(
                                f"  ❌ {project_dir.name}: SAFETY FLOOR FAILED — "
                                f"{names} is STILL not ignored after repair (the message names the "
                                f"FAILING pattern — it used to say `.env` whatever failed, 01M1H1V2). "
                                f"FIX THIS BY HAND: a `git add -A` here can commit what the floor "
                                f"exists to hide."
                            )
                            # The CAUSE decides the remedy, and naming the wrong one sends the
                            # operator somewhere the fix cannot be (01M1RFZE, /opt/proxy).
                            if tracked:
                                print(
                                    f"     ↳ ALREADY TRACKED: {', '.join(tracked)} — the ignore rule "
                                    f"is CORRECT and matches; git never ignores a committed path. "
                                    f"Editing .gitignore cannot fix this. Run: "
                                    f"git -C {project_dir} rm -r --cached {' '.join(tracked)} "
                                    f"&& git -C {project_dir} commit -m 'untrack ignored paths'"
                                )
                            if unruled:
                                print(
                                    f"     ↳ NO MATCHING RULE: {', '.join(unruled)} — a project rule "
                                    f"is overriding it (look for a negation or a nested .gitignore)."
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

        # R3: re-copy the manifest's gitignored set — PLUS the lock just written above —
        # into every worktree this project already has under .claude/worktrees/.
        # `.worktreeinclude` only fires at Claude Code's own worktree-creation moment, so
        # a sync landing mid-epic otherwise updates the main checkout alone (design spec
        # § Lifecycle "Synced-file drift inside a live worktree"). MUST run after the
        # lock write above, never before: `.fabrik/synced.lock` is not one of
        # `.worktreeinclude`'s own patterns, so a worktree has no lock at all until this
        # call copies the main checkout's FRESH one — copying a stale lock first (there
        # is none to copy) or running before the write would leave every worktree's
        # `check_synced_unmodified.py` either skipped or comparing against the wrong file.
        # Snapshot the module-level worktree tally before/after so THIS project's own
        # contribution can be reported on the per-project line below — the tally itself
        # is cumulative across the whole `main()` run and must stay that way for the
        # final `Results:` line, so a snapshot delta (not the running totals) is what
        # this one project's message needs.
        _wt_tally_before = dict(_WORKTREE_TALLY)
        resync_worktree_artifacts(project_dir, dry_run=dry_run, backup=backup, force=force)
        wt_files = _WORKTREE_TALLY["files"] - _wt_tally_before["files"]
        wt_worktrees = _WORKTREE_TALLY["worktrees"] - _wt_tally_before["worktrees"]
        wt_warnings = _WORKTREE_TALLY["warnings"] - _wt_tally_before["warnings"]
        wt_deletions = _WORKTREE_TALLY["deletions"] - _wt_tally_before["deletions"]

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
        # class 3, 2026-09-05 acceptance round 3: the per-project line excluded worktree
        # files while the final `Results:` line (main()) included them under a separate
        # `| Worktrees: ...` segment — the two disagreed on what "copied" meant for this
        # project. Add the same breakdown here so both lines agree.
        if wt_worktrees > 0:
            parts.append(f"{wt_files} worktree file(s) into {wt_worktrees} worktree(s)")
            if wt_deletions > 0:
                parts.append(f"{wt_deletions} worktree orphan(s) removed")
            if wt_warnings > 0:
                parts.append(f"{wt_warnings} worktree warning(s)")
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


# ".claude" (round 3, 2026-09-05 acceptance, class 1): `_unreachable_vendored_copies`'s
# os.walk otherwise descends into `.claude/worktrees/<agent>/<vendored_rel>` — every
# linked worktree carries its own re-synced copy of VENDORED_DIRS (libs/subagents/,
# libs/health_probe/, both with __init__.py), which is the sync's OWN reachable
# output, not a stray. Measured: 0 false hits before a worktree resync, 8 after on a
# 4-worktree fixture (2 vendored dirs × 4 worktrees) — 82 × 2 = 164 on the live fleet.
_PRUNE_DIRS = {
    ".git",
    ".venv",
    "node_modules",
    "__pycache__",
    ".tmp",
    "archived",
    "dist",
    "build",
    ".claude",
}


def _unreachable_vendored_copies(projects: list[Path]) -> list[str]:
    """Vendored-dir copies that exist OUTSIDE the sync's fixed target path.

    The sync writes `<repo>/<vendored_rel>` and never searches; a repo that vendors the module
    elsewhere (ai-model-catalog/engine/libs/subagents, whatsapp-agent/src/libs/subagents — both
    LOAD-BEARING, 01M1J0HN) receives nothing, forever, and every "does this repo have the module?"
    check answers YES against the unused standard copy. Report what the sync did not reach —
    the population of copies that EXIST, not just the files it WROTE."""
    from fabrik_synced_manifest import VENDORED_DIRS

    found: list[str] = []
    for project_dir in projects:
        for vendored_rel in VENDORED_DIRS:
            leaf = Path(vendored_rel).name
            target = project_dir / vendored_rel
            for dirpath, dirnames, filenames in os.walk(project_dir):
                dirnames[:] = [d for d in dirnames if d not in _PRUNE_DIRS]
                if (
                    Path(dirpath).name == leaf
                    and "__init__.py" in filenames
                    and Path(dirpath) != target
                ):
                    found.append(str(Path(dirpath).relative_to(project_dir.parent)))
    return sorted(found)


def main() -> int:
    # Reset the module-level tally. It is a mutable global; without this a second in-process call (a
    # future test, a wrapper, a dry-run-then-real flow) inherits the previous run's failures and returns
    # 1 forever.
    _SAFETY_FLOOR_FAILURES.clear()
    # Same reasoning for the worktree tally (class 5, 2026-09-05 acceptance round 2): a
    # second in-process call must not accumulate a previous run's worktree numbers into
    # this run's final summary line.
    _WORKTREE_TALLY.update(projects=0, worktrees=0, files=0, warnings=0, deletions=0)
    # Same reasoning again for the .gitignore-patch tally (round 7, class 3).
    _GITIGNORE_PATCHED.clear()
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
        "Traycer",  # Traycer tool install dir (root-owned) — the chronic "2 failed" on every sync
        "microsoft",  # vendor install dir (root-owned) — same class
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
        if (project_dir / ".git").is_file():
            # A git WORKTREE (`.git` is a file pointing at the main checkout). Its main repo is
            # the sync target — or, for a sync-EXCLUDED repo, deliberately not one; adopting the
            # worktree wrote hub governance into fabrik-lib branches and left `M .gitignore` in
            # three trees their owners never touched (01M1H1V2, 2026-09-02).
            print(f"SKIP (worktree, not a repo): {project_dir.name}")
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

    stray = _unreachable_vendored_copies(projects)
    if stray:
        print(
            f"\n⚠️  {len(stray)} vendored copy(ies) the sync CANNOT reach — a repo imports a copy at a "
            f"non-standard path, which receives nothing from any sync (01M1J0HN): "
            + ", ".join(stray)
            + ". Move the copy to the standard path or record the exception in the repo."
        )
    summary = f"Results: {success_count} projects synced, {fail_count} failed"
    summary += f" | Files: {total_copied} copied, {total_skipped} skipped"
    if total_warnings > 0:
        summary += f", {total_warnings} warnings (use --force to overwrite)"
    # round 7, class 3: name the .gitignore-patch fleet effect on the one line that survives
    # the production wrapper's `tail -3` (governance_sync_postcommit.sh:82) — a real run
    # rewrites every tracked .gitignore whose block is stale (a one-off ~45-repo dirty-tree
    # event on first adoption) and this was the only summary line silent about it.
    if _GITIGNORE_PATCHED:
        verb = "would be patched" if args.dry_run else "patched"
        summary += f" | gitignore {verb}: {len(_GITIGNORE_PATCHED)}"
    # Fold the worktree re-sync numbers into THIS line — the last few lines of the
    # whole run, which is all the production wrapper's `tail -3` keeps
    # (scripts/governance_sync_postcommit.sh:82). Every per-project worktree print
    # (the count, the NOTEs, the WARNs) is truncated away there; this line is not
    # (class 5, round 2). Under `--dry-run` the tally holds WOULD-be numbers (round 3,
    # class 3: without this, the ticket-mandated fire-rate sweep showed nothing on
    # the one line the wrapper keeps) — worded accordingly.
    if _WORKTREE_TALLY["worktrees"] > 0:
        if args.dry_run:
            summary += (
                f" | Worktrees: would re-sync {_WORKTREE_TALLY['files']} file(s) into "
                f"{_WORKTREE_TALLY['worktrees']} worktree(s) across "
                f"{_WORKTREE_TALLY['projects']} project(s)"
            )
        else:
            summary += (
                f" | Worktrees: {_WORKTREE_TALLY['files']} file(s) re-synced into "
                f"{_WORKTREE_TALLY['worktrees']} worktree(s) across "
                f"{_WORKTREE_TALLY['projects']} project(s)"
            )
        if _WORKTREE_TALLY["deletions"] > 0:
            summary += f", {_WORKTREE_TALLY['deletions']} orphan(s) " + (
                "would be removed" if args.dry_run else "removed"
            )
        if _WORKTREE_TALLY["warnings"] > 0:
            summary += f", {_WORKTREE_TALLY['warnings']} warning(s)"
    print(summary)

    if args.dry_run:
        print("\nDRY-RUN: No files were modified")

    return 0 if (fail_count == 0 and not _SAFETY_FLOOR_FAILURES) else 1


if __name__ == "__main__":
    sys.exit(main())
