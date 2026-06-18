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
    "update_agents_toc.py",
    "health_checker.py",
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
    "AGENTS-compact.md",
    "CLAUDE.md",
    "opencode.json",
    ".windsurfrules",
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

# Agent "definition of done" hooks → synced to project root verbatim (they are
# cwd/path-agnostic: the Claude Code hook resolves its project via ${CLAUDE_PROJECT_DIR}
# + stdin cwd; the Cascade hook commands self-locate via `git rev-parse`). This is
# what makes every project — existing and future — enforce `final_gate` green as the
# definition of done. (Kilo/opencode has no config-level hook surface — its schema
# is strict — so Kilo stays instruction-only via AGENTS-compact.md, which rides
# GOVERNANCE_FILES above.)
AGENT_HOOK_FILES = [
    ".claude/settings.json",
    ".claude/hooks/final_gate_stop.py",
    ".windsurf/hooks.json",
]

# Synced as an initial SEED but thereafter legitimately edited per-project
# (e.g. every project tracks its OWN ports in PORTS.md). Excluded from the
# "unmodified" gate check — the sync still WARN-skips these when the local copy
# is newer, so a project's edits survive.
SEEDED_NOT_ENFORCED = {"PORTS.md"}

# Reference docs → (source relpath, dest relpath). Path-preserved unless noted.
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
    ("docs/operations/fabrik-lifecycle.md", "docs/operations/fabrik-lifecycle.md"),
    ("docs/BUSINESS_MODEL.md", "docs/BUSINESS_MODEL.md"),
    (
        "docs/reference/mobile-responsive-testing-guide.md",
        "docs/reference/mobile-responsive-testing-guide.md",
    ),
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
        "Governance files": list(GOVERNANCE_FILES),
        "Agent definition-of-done hooks": list(AGENT_HOOK_FILES),
        "Rule packs, workflows and synced reference dirs": synced_dirs,
        "Reference docs (synced from fabrik)": [dest for _src, dest in REFERENCE_DOCS],
        "Synced scripts": (
            [f"scripts/{s}" for s in CORE_SCRIPTS]
            + [f"{ENFORCEMENT_DIR}/"]
            + [f"scripts/{s}" for s in RUN_SCRIPTS]
        ),
    }


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

    # Reference docs
    for src_rel, dest_rel in REFERENCE_DOCS:
        yield fabrik_root / src_rel, project_root / dest_rel

    # Recursive directories (governance + enforcement)
    for rel_dir in [*GOVERNANCE_DIRS, ENFORCEMENT_DIR]:
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
            rel = src_file.relative_to(fabrik_root)
            yield src_file, project_root / rel
