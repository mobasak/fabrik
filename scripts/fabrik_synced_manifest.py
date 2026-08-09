#!/usr/bin/env python3
"""Single source of truth for files Fabrik centrally distributes to every /opt project.

⚠️  FABRIK-MANAGED. These files are pushed from /opt/fabrik to every project by
`sync_enforcement_to_projects.py`. Editing a copy *inside a project* is futile —
the next sync overwrites it. To change one: edit the canonical copy under
/opt/fabrik and re-sync, and ONLY if the change is correct for ALL projects.

Consumed by (keep these in lockstep — that is the whole point of this module):
- ``scripts/sync_enforcement_to_projects.py``        — the distributor
- ``src/fabrik/scaffold.py``                          — the ``.gitignore`` "Fabrik-synced" block
- ``scripts/enforcement/check_synced_unmodified.py``  — gate teeth (detects local drift)
- ``docs/workflows/SYNC_ENFORCEMENT_WORKFLOW.md``     — the "What Gets Synced" table

Historically this list lived in three places that drifted apart (Lesson 44). It
now lives here once; the consumers import it.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

FABRIK_ROOT = Path("/opt/fabrik")

# Core enforcement scripts → project ``scripts/`` (sourced from FABRIK_ROOT/scripts/).
CORE_SCRIPTS = [
    "final_gate.py",
    "kilo_code_review.py",
    "kilo_docs_enforcer.py",
    "docs_updater.py",
    "doc_reconcile.py",  # Tier-1 doc-reconcile loop (pool author → verify → converge); agents run it per phase
    "update_agents_toc.py",
    "health_checker.py",
    "select_rules.py",  # plan-time: lists applicable .windsurf/rules packs
    "review_rubric.py",  # armed-review rubric extractor — /fabrik-review injects its output into finders
    "release_cut.py",  # /fabrik-release version cut: [Unreleased] -> semver section + tag + GitHub Release
]

# Long Command Monitoring System → project ``scripts/`` (sourced from
# templates/scaffold/scripts/ so templates and live projects stay in lockstep).
RUN_SCRIPTS_SRC_DIR = "templates/scaffold/scripts"
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

# Governance files → project root (sourced from FABRIK_ROOT/<file>).
# NOTE: AFCL.md is scaffolded as AFCL_TEMPLATE.md and customised per project (not synced);
# .pre-commit-config.yaml is tech-stack specific (not synced).
GOVERNANCE_FILES = [
    "AGENTS.md",
    "agents-fabrik.md",  # canonical agents doc (AGENTS.md is a stub pointing here)
    "agents-fabrik-core.md",  # high-frequency core @import-ed by CLAUDE.md — must exist fleet-wide
    "AGENTS-compact.md",
    "opencode.json",
    ".windsurfrules",
]

# Governance templates → (src_rel under templates/, dest_rel at project root).
# CLAUDE.md hub/project split (2026-08-08): /opt/fabrik/CLAUDE.md is the HUB
# agents' contract and is NEVER distributed; projects receive the template.
# Same (src, dest) pair shape as REFERENCE_DOCS; scaffold G-B5 seeds from the
# same template source.
GOVERNANCE_TEMPLATES = [
    ("templates/governance/CLAUDE.md", "CLAUDE.md"),
]

# Governance directories → synced recursively, with orphan pruning.
GOVERNANCE_DIRS = [
    ".windsurf/rules",
    ".windsurf/workflows",
    "docs/reference/kilo",
    "docs/reference/MD",
]

# Enforcement directory → synced recursively into project ``scripts/enforcement/``.
ENFORCEMENT_DIR = "scripts/enforcement"

# Vendored fabrik-lib modules → synced recursively (flat copy) into each project. The subagents pool is a
# DEV-TIME tool the /fabrik-* commands import as ``from libs.subagents import …``; making it a synced dir
# means a fix in the hub copy propagates fleet-wide on the next sync (no manual re-vendor), and new projects
# get it via the scaffold (which copies the synced dirs). Hub source: ``/opt/fabrik/libs/subagents`` (kept
# byte-identical to canonical ``/opt/fabrik-lib/subagents`` by re-vendoring before a sync).
VENDORED_DIRS = ["libs/subagents"]

# Agent "definition of done" + prompt-governance hooks → synced to project root
# verbatim (they are cwd/path-agnostic: the Claude Code hooks resolve their
# project via ${CLAUDE_PROJECT_DIR} + stdin cwd; the Cascade hook commands
# self-locate via `git rev-parse`). This is what makes every project — existing
# and future — enforce `final_gate` green as the definition of done, and route
# bare-prose prompts to the matching /fabrik-* skill. (Kilo/opencode has no
# config-level hook surface — its schema is strict — so Kilo stays
# instruction-only via AGENTS-compact.md, which rides GOVERNANCE_FILES above.)
AGENT_HOOK_FILES = [
    ".claude/settings.json",
    ".claude/hooks/final_gate_stop.py",
    ".claude/hooks/skill_router.py",
    ".claude/hooks/session_orient.py",  # SessionStart orientation: governance/memory/session-recall/mesh
    ".windsurf/hooks.json",
]

# Synced as an initial SEED but thereafter legitimately edited per-project
# (e.g. every project tracks its OWN ports in PORTS.md). Excluded from the
# "unmodified" gate check — the sync still WARN-skips these when the local copy
# is newer, so a project's edits survive.
SEEDED_NOT_ENFORCED = {"PORTS.md"}

# Reference docs → (source relpath, dest relpath). Path-preserved unless noted.
REFERENCE_DOCS = [
    ("docs/reference/long-command-monitoring.md", "docs/reference/long-command-monitoring.md"),
    (
        "docs/reference/technology-stack-decision-guide.md",
        "docs/reference/technology-stack-decision-guide.md",
    ),
    ("PORTS.md", "PORTS.md"),
    ("docs/operations/fabrik-lifecycle.md", "docs/operations/fabrik-lifecycle.md"),
    # The /opt project catalog (what exists, so a project can wire to a sibling instead of
    # rebuilding). Renamed 2026-07-11 from BUSINESS_MODEL.md — that path is the per-project
    # *monetization* doc and this fleet-synced catalog was overwriting it. Now its own doc,
    # synced to a reference path that never collides with a project's own docs.
    ("docs/PROJECT_CATALOG.md", "docs/reference/opt-project-catalog.md"),
    (
        "docs/reference/mobile-responsive-testing-guide.md",
        "docs/reference/mobile-responsive-testing-guide.md",
    ),
    # The 3 direct-agent convergence prompts (PLAN/CODE REVIEW/DOCS) — referenced by
    # the synced CLAUDE.md HARD-STOP row, so it must exist in every project too.
    ("docs/reference/convergence-prompts.md", "docs/reference/convergence-prompts.md"),
    # kilo-consult-workflow.md removed 2026-07-11 — `kilo consult` superseded by the OpenRouter
    # fabrik-lib consult module; no longer synced to projects (template archived, script dormant).
]


def gitignore_dest_paths() -> dict[str, list[str]]:
    """Dest paths grouped for the scaffold ``.gitignore`` "Fabrik-synced" block.

    Directories are emitted with a trailing slash (gitignore directory match).
    ``.windsurf/rules`` + ``.windsurf/workflows`` collapse to a single ``.windsurf/``
    (the broad ignore the scaffold has always emitted).
    """
    synced_dirs: list[str] = []
    seen_windsurf = False
    for d in GOVERNANCE_DIRS:
        if d.startswith(".windsurf/"):
            if not seen_windsurf:
                synced_dirs.append(".windsurf/")
                seen_windsurf = True
        else:
            synced_dirs.append(f"{d}/")
    return {
        # Template-sourced governance dests ride the same group — this dict is
        # built from NAME LISTS, not iter_synced_pairs, so every new leg must be
        # fed in here explicitly (live regression: dropping CLAUDE.md from
        # GOVERNANCE_FILES silently removed its ignore line fleet-wide).
        "Governance files": list(GOVERNANCE_FILES)
        + [dest for _src, dest in GOVERNANCE_TEMPLATES],
        "Agent definition-of-done hooks": list(AGENT_HOOK_FILES),
        "Rule packs, workflows and synced reference dirs": synced_dirs,
        "Reference docs (synced from fabrik)": [dest for _src, dest in REFERENCE_DOCS],
        "Synced scripts": (
            [f"scripts/{s}" for s in CORE_SCRIPTS]
            + [f"{ENFORCEMENT_DIR}/"]
            + [f"scripts/{s}" for s in RUN_SCRIPTS]
        ),
        "Vendored fabrik-lib modules (synced fleet-wide)": [f"{d}/" for d in VENDORED_DIRS],
    }


_GI_BAR = "# " + "=" * 60
GITIGNORE_BLOCK_END = "# End Fabrik-synced block"


def gitignore_block_text() -> str:
    """The full ``.gitignore`` "Fabrik-synced" block (with markers), from the manifest.

    Single source for both scaffold.py (new projects) and
    sync_enforcement_to_projects.py (patches existing projects' .gitignore so every
    governance/synced file is ignored fleet-wide). The header doubles as the
    "do not edit" warning. The ``GITIGNORE_BLOCK_END`` marker lets the sync find +
    replace an existing block without touching the project's own .gitignore entries.
    """
    lines = [
        _GI_BAR,
        "# Fabrik-synced files — DO NOT EDIT (centrally managed)",
        "# Pushed from /opt/fabrik by sync_enforcement_to_projects.py; local edits",
        "# are overwritten on the next sync. To change one: edit the canonical copy",
        "# in /opt/fabrik and re-sync — only if the change applies to ALL projects.",
        _GI_BAR,
        "",
    ]
    for group, paths in gitignore_dest_paths().items():
        lines.append(f"# {group}")
        lines.extend(paths)
        lines.append("")
    # Per-project synced-files lock — written by the sync (md5 of what was distributed);
    # local state, never committed. check_synced_unmodified compares against it.
    lines += ["# Synced-files lock", ".fabrik/synced.lock", ""]
    lines += [_GI_BAR, GITIGNORE_BLOCK_END, _GI_BAR]
    return "\n".join(lines) + "\n"


def iter_synced_pairs(
    project_root: Path, fabrik_root: Path = FABRIK_ROOT
) -> Iterator[tuple[Path, Path]]:
    """Yield concrete ``(fabrik_source_file, project_dest_file)`` pairs.

    Directories are expanded by walking the fabrik source, so the caller gets a
    flat list of files to compare/copy. Sources that don't exist are skipped.
    """
    # Core + run scripts
    for name in CORE_SCRIPTS:
        yield fabrik_root / "scripts" / name, project_root / "scripts" / name
    for name in RUN_SCRIPTS:
        yield fabrik_root / RUN_SCRIPTS_SRC_DIR / name, project_root / "scripts" / name

    # Governance files + agent hooks (verbatim, root-relative paths)
    for rel in [*GOVERNANCE_FILES, *AGENT_HOOK_FILES]:
        yield fabrik_root / rel, project_root / rel

    # Governance templates (src under templates/, dest at project root) —
    # unconditional yield like the leg above; the lock writer filters on
    # dest.exists(), so a project's copy stays lock-protected even if the
    # template source is momentarily absent.
    for src_rel, dest_rel in GOVERNANCE_TEMPLATES:
        yield fabrik_root / src_rel, project_root / dest_rel

    # Reference docs
    for src_rel, dest_rel in REFERENCE_DOCS:
        yield fabrik_root / src_rel, project_root / dest_rel

    # Recursive directories (governance + enforcement + vendored fabrik-lib modules)
    for rel_dir in [*GOVERNANCE_DIRS, ENFORCEMENT_DIR, *VENDORED_DIRS]:
        src_dir = fabrik_root / rel_dir
        if not src_dir.exists():
            continue
        for src_file in src_dir.rglob("*"):
            if not src_file.is_file():
                continue
            # Never track compiled bytecode — it's non-deterministic across
            # hosts/Python versions and would cause spurious drift in the check.
            if "__pycache__" in src_file.parts or src_file.suffix == ".pyc":
                continue
            rel_path = src_file.relative_to(fabrik_root)
            yield src_file, project_root / rel_path


# --------------------------------------------------------------------------- #
# Review scope — consumed by the /fabrik-*-review commands                     #
# --------------------------------------------------------------------------- #
# Reviews kept raising findings against centrally-distributed files. Inside a
# PROJECT those are read-only (check_synced_unmodified.py is the gate), so a
# finding there is unactionable — and an agent that "helpfully fixes" it creates
# the very drift the gate exists to catch. Reviews therefore need the set
# programmatically. Per this module's whole reason for existing (Lesson 44: the
# list drifted when it lived in three places), review commands DERIVE it here —
# they must never hand-copy a list into their own prose.


def synced_project_paths(fabrik_root: Path = FABRIK_ROOT) -> list[str]:
    """Project-relative paths of every centrally-distributed file.

    This is the set a project cannot edit. Reviews treat it as *context*
    (``.windsurf/rules`` still binds the code under review) but never as a
    *target*.
    """
    probe = Path("/__project__")
    return sorted(
        str(dst.relative_to(probe)) for _src, dst in iter_synced_pairs(probe, fabrik_root)
    )


def review_readonly_paths(fabrik_root: Path = FABRIK_ROOT) -> list[str]:
    """The synced set MINUS files a project is *allowed* to modify.

    ``SEEDED_NOT_ENFORCED`` (``PORTS.md``) is distributed once but projects may
    edit it, so it stays a normal review target. A naive "exclude everything
    synced" list would wrongly skip a file that SHOULD be reviewed — which is
    exactly why this is computed, not hand-written.
    """
    return [p for p in synced_project_paths(fabrik_root) if p not in SEEDED_NOT_ENFORCED]


if __name__ == "__main__":  # pragma: no cover - thin CLI
    import argparse

    ap = argparse.ArgumentParser(
        description="Fabrik synced-file manifest — the single source of truth."
    )
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument(
        "--list",
        action="store_true",
        help="every centrally-distributed project-relative path",
    )
    g.add_argument(
        "--review-readonly",
        action="store_true",
        help=(
            "paths a PROJECT review must treat as context-only, never as a target "
            "(synced set minus SEEDED_NOT_ENFORCED)"
        ),
    )
    args = ap.parse_args()
    paths = review_readonly_paths() if args.review_readonly else synced_project_paths()
    print("\n".join(paths))
