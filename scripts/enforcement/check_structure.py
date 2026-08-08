#!/usr/bin/env python3
# AFTER-EDIT: none
"""Enforce project documentation structure.

Ensures documents are placed in the correct locations per Fabrik conventions.
"""

import subprocess
import sys
from pathlib import Path
from typing import Any

# Allowed .md files in project root
ALLOWED_ROOT_MD = {
    "INDEX.md",
    "README.md",
    "CHANGELOG.md",
    "tasks.md",
    "AGENTS.md",
    "AGENTS-compact.md",
    # agents-fabrik.md (2026-07-12): the autonomous-factory orientation file — a
    # direct peer of AGENTS.md (same infra map, reframed for our tool-capable
    # agents), read FIRST by the factory's planning/coding agents. Root by the
    # same architectural decision as AGENTS.md/CLAUDE.md below. Permissive entry:
    # projects without the file are unaffected.
    "agents-fabrik.md",
    # agents-fabrik-core.md (2026-07-19): the high-frequency platform core @import-ed by
    # CLAUDE.md — a root governance file synced fleet-wide (fabrik_synced_manifest GOVERNANCE_FILES).
    "agents-fabrik-core.md",
    "PORTS.md",
    "LICENSE.md",
    # T1-02 (2026-05-14): CLAUDE.md is Claude Code's per-project bootstrap;
    # AGENTS.md + .windsurfrules + AGENTS-compact.md + CLAUDE.md all live in
    # the project root by architectural decision (see CLAUDE.md HARD STOPS
    # allowlist row "new `.md` outside allowlist | root files · scaffold
    # docs · ..."). AFCL.md is the Agentic Friction & Constraint Log,
    # appended to as the operator hits silicon ceilings. PROOF.md and
    # FOLLOWUPS.md are project-state markers retained from prior live-deploy
    # proof harnesses (2026-04-27). All 4 belong in root.
    "CLAUDE.md",
    "AFCL.md",
    "PROOF.md",
    "FOLLOWUPS.md",
    # KILO_CLI_RULES.md removed 2026-06-13 — not used for any AI (operator
    # directive); the file does not exist in the repo, so the root allowance
    # was dead. opencode.json loads AGENTS-compact.md alone.
}

# Valid docs/ subdirectories
VALID_DOCS_SUBDIRS = {
    "guides",
    "reference",
    "operations",
    "development",
    "archive",
    "superpowers",  # brainstorming/writing-plans skills save specs/ + plans/ here
}

# Directories that should not contain .md files directly
NO_MD_DIRS = {
    "src",
    "tests",
    "config",
    "scripts",
    "logs",
    "data",
    "output",
    ".tmp",
    ".cache",
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
}

# Directories excluded from structure checks (backup/export folders)
EXCLUDED_DIRS = {
    "windsurf-memories",
    ".droid",
}

# Legacy directories to warn about (should be migrated)
LEGACY_DIRS = {
    "proposals",
}
# Note: specs/ is NOT legacy - it's the canonical location for Stage 0 pipeline
# outputs (specs/<project>/00-idea.md, 01-scope.md, 02-spec.md) per AGENTS.md

# --- docs/ allowlist: DERIVED from the canonical registry (SSOT), never hand-maintained ---
# The registry lives sibling-to-sibling in scripts/enforcement/ (synced fleet-wide), so a
# SAME-DIR import resolves both hub-side and project-side. Do NOT use the
# sys.path.insert(0, FABRIK_ROOT/"scripts") pattern (e.g. check_synced_unmodified.py) —
# FABRIK_ROOT is hardcoded /opt/fabrik, so a project would import the HUB's registry
# instead of its own synced copy. We call docs_allowlist() with NO argument: the permissive
# full union, so a recognized doc never false-WARNs regardless of the project's exact shape
# (that is where the grandfather / no-regression guarantee lives), then union LEGACY_TOLERATED
# for once-standard names older projects carry. Fail-safe: any import error falls back to the
# previous literal set so the gate can never crash.
# A no-regression SUPERSET: the old literal (pre-plan allowlist) PLUS the docs that became
# canonical when the registry landed — so even if _doc_registry is momentarily unimportable
# (corrupt file / stale .pyc / half-synced deploy) the gate does not suddenly WARN on
# RESILIENCE/data-contract/ui-design/design-system/LESSONS_LEARNT/STRATEGIC_BACKLOG. This is a
# deliberate belt-and-suspenders copy used ONLY on the fallback path; the real allowlist derives
# from the registry (docs_allowlist()). Keep loosely in sync with _doc_registry (permissive — a
# stray extra name here only ever suppresses an advisory WARN, never adds a false one).
_FALLBACK_DOCS_ALLOWLIST = frozenset(
    {
        # pre-plan literal
        "README.md",
        "QUICKSTART.md",
        "CONFIGURATION.md",
        "TROUBLESHOOTING.md",
        "BUSINESS_MODEL.md",
        "SERVICES.md",
        "OPERATIONS.md",
        "DEPLOYMENT.md",
        "EXTERNAL_SYSTEMS.md",
        "FAQ.md",
        "FEATURES.md",
        "TESTING.md",
        "owner_ozgur_basak.md",
        # docs that became canonical with the registry (no transient regression when it's down)
        "RESILIENCE.md",
        "data-contract.md",
        "ui-design.md",
        "design-system.md",
        "LESSONS_LEARNT.md",
        "STRATEGIC_BACKLOG.md",
    }
)
try:
    _enforce_dir = str(Path(__file__).resolve().parent)
    if _enforce_dir not in sys.path:  # dedup — avoid unbounded path pollution on re-import
        sys.path.insert(0, _enforce_dir)
    import _doc_registry  # noqa: E402  (same-dir sibling, synced fleet-wide)

    DOCS_ALLOWLIST = _doc_registry.docs_allowlist() | _doc_registry.LEGACY_TOLERATED
except Exception:  # noqa: BLE001 — a registry glitch must never crash the structure gate
    DOCS_ALLOWLIST = _FALLBACK_DOCS_ALLOWLIST


def _gitignored_files(root: Path) -> set[str]:
    """Posix-relative paths of gitignored (untracked-ignored) files under ``root``.

    Structure rules gate the REPO, not local artifacts git doesn't track — a gitignored
    file (e.g. a ``scripts/**/cache/*.md`` audit dump written by a benchmark run) must NOT
    fail the gate. Best-effort: empty set when git is unavailable, so the walk falls back
    to checking everything.
    """
    try:
        out = subprocess.run(
            # quotePath=false: git escapes non-ASCII paths by default ("\342\200\223"
            # for an en dash), which would never match real filesystem paths — the
            # ignore-set silently loses those entries and gates the very artifacts
            # this function exists to skip (trade-intelligence upstream, 2026-08-05).
            [
                "git",
                "-c",
                "core.quotePath=false",
                "-C",
                str(root),
                "ls-files",
                "--others",
                "--ignored",
                "--exclude-standard",
            ],
            capture_output=True,
            text=True,
            timeout=15,
            check=True,
        ).stdout
    except Exception:
        return set()
    return {line.strip() for line in out.splitlines() if line.strip()}


def check_structure(project_root: Path, files: list[str] | None = None) -> list[dict[str, Any]]:
    """Check project structure for violations.

    Args:
        project_root: Root directory of the project
        files: Optional list of files to check (for pre-commit).
               If None, checks entire project.

    Returns:
        List of violation dicts with keys: file, severity, message, fix_hint
    """
    violations = []

    if files:
        # Check only specified files
        paths_to_check = [Path(f) for f in files if f.endswith(".md")]
    else:
        # Check all .md files in project
        paths_to_check = list(project_root.rglob("*.md"))

    # Gitignored files are local artifacts, not part of the repo — never gate them.
    # (When `files` is passed, pre-commit already scoped to tracked changes.)
    ignored = set() if files else _gitignored_files(project_root)

    for path in paths_to_check:
        # Make path relative to project root
        if path.is_absolute():
            try:
                rel_path = path.relative_to(project_root)
            except ValueError:
                continue  # File outside project
        else:
            rel_path = path

        if rel_path.as_posix() in ignored:
            continue  # gitignored local artifact — not part of the repo

        # Skip hidden directories (except .windsurf, .droid)
        parts = rel_path.parts
        if any(p.startswith(".") and p not in {".windsurf", ".droid"} for p in parts):
            continue
        if "node_modules" in parts or "__pycache__" in parts:
            continue
        # Skip excluded directories (backup/export folders)
        if any(p in EXCLUDED_DIRS for p in parts):
            continue

        # README.md is the universal "document this directory" convention —
        # allow it anywhere (scripts/bootstrap/, configs/<svc>/, etc.). The
        # NO_MD_DIRS / location rules target stray docs & plans, not the
        # directory-README that explains a code/config folder. (2026-06-13)
        if rel_path.name == "README.md":
            continue

        # scripts/sysadmin/ holds runtime-loaded sysadmin-pack assets — the
        # Claude system prompt + peer-protocol.md that bot.py and watchdog.py
        # vendor and read at runtime (watchdog.py: `sysadmin_source /
        # "peer-protocol.md"`). These are code-adjacent runtime assets, not
        # stray docs, so .md is allowed here. (2026-06-13)
        if len(parts) >= 2 and parts[0] == "scripts" and parts[1] == "sysadmin":
            continue

        # A directory literally named libs/ at ANY depth holds VENDORED fabrik-lib
        # modules — each owns its docs (README, VENDORING.md, CUSTOMIZATION.md,
        # UPSTREAM_FEEDBACK.md, examples/) that travel with the vendored code, not
        # stray project docs. Was root-libs/ + src/**/libs/ only; generalized
        # 2026-08-06 (trade-intelligence upstream): projects legitimately vendor
        # into web/libs/, app/libs/, etc. — the dir NAME is the contract.
        if "libs" in parts:
            continue

        # A directory named prompts/ at ANY depth holds prompt TEMPLATES the app
        # loads at runtime — markdown-as-DATA, not documentation (e.g.
        # services/bible.py reads prompts/bible/*.md; generators keep briefs
        # under data/prompts/). Same dir-name-is-the-contract decision as libs/;
        # was src/**/prompts/ only, which told projects storing prompt data
        # outside src/ to violate their own docs policy.
        if "prompts" in parts:
            continue

        # Flag forbidden directories as errors (not skip!)
        forbidden_dir = next((p for p in parts if p in NO_MD_DIRS), None)
        if forbidden_dir:
            violations.append(
                {
                    "file": str(rel_path),
                    "severity": "error",
                    "message": f"Markdown file forbidden in '{forbidden_dir}/' directory",
                    "fix_hint": "Move to docs/reference/ or docs/guides/",
                }
            )
            continue

        # Check root-level .md files
        if len(parts) == 1:
            filename = parts[0]
            if filename not in ALLOWED_ROOT_MD:
                violations.append(
                    {
                        "file": str(rel_path),
                        "severity": "error",
                        "message": f"Markdown file '{filename}' not allowed in project root",
                        "fix_hint": f"Move to docs/reference/{filename} or docs/guides/{filename}",
                    }
                )

        # Check docs/ structure
        elif parts[0] == "docs":
            if len(parts) == 2:
                # File directly in docs/ - only registry-recognized standard files allowed
                # (DOCS_ALLOWLIST is derived from _doc_registry — the SSOT, not a 2nd copy).
                filename = parts[1]
                if filename not in DOCS_ALLOWLIST:
                    violations.append(
                        {
                            "file": str(rel_path),
                            "severity": "warning",
                            "message": f"'{filename}' should be in a docs/ subdirectory",
                            "fix_hint": (
                                f"Move to docs/reference/{filename} or docs/guides/{filename}"
                            ),
                        }
                    )
            elif len(parts) >= 3:
                subdir = parts[1]
                if subdir not in VALID_DOCS_SUBDIRS:
                    violations.append(
                        {
                            "file": str(rel_path),
                            "severity": "warning",
                            "message": f"Non-standard docs subdirectory: docs/{subdir}/",
                            "fix_hint": f"Use one of: {', '.join(sorted(VALID_DOCS_SUBDIRS))}",
                        }
                    )

        # Check legacy directories
        elif parts[0] in LEGACY_DIRS:
            violations.append(
                {
                    "file": str(rel_path),
                    "severity": "warning",
                    "message": f"Legacy directory '{parts[0]}/' should be migrated",
                    "fix_hint": "Move to docs/development/plans/ or docs/archive/",
                }
            )

        # Check templates (allowed)
        elif parts[0] == "templates":
            pass  # Templates are allowed anywhere

        # Check .droid (allowed for task files)
        elif parts[0] == ".droid":
            pass  # Droid task files allowed

        # Check .windsurf (allowed for rule files)
        elif parts[0] == ".windsurf":
            pass  # Windsurf rule files allowed

        # Check specs/ (Stage 0 pipeline output - allowed)
        elif parts[0] == "specs":
            pass  # Spec pipeline files allowed

        # T1-02 (2026-05-14): ops/ subdirs hold systemd unit packages
        # (authelia-config-sync, coolify-alias-watcher); each has its own
        # README documenting the install/run procedure, which is the
        # standard pattern for self-contained ops packages and predates
        # T1-02 by months.
        elif parts[0] == "ops":
            pass  # ops/<package>/README.md allowed (operational unit docs)

        # commands/ is the hub's command corpus (hub-only dir; absent in
        # projects): _sources/*.md + _fragments/*.md are the canonical inputs
        # assemble_commands.py renders to ~/.claude/commands. They are command
        # source code, not misplaced docs.
        elif parts[0] == "commands":
            pass  # command-corpus sources/fragments allowed

        # docs-site/ is a Docusaurus site — `docusaurus` is a first-class
        # SCAFFOLD_TYPE and the scaffolder itself produces this layout; its
        # markdown MUST live under docs-site/ by Docusaurus's own contract
        # (trade-intelligence upstream, 2026-08-05).
        elif parts[0] == "docs-site":
            pass  # Docusaurus site content allowed

        # Other locations
        else:
            violations.append(
                {
                    "file": str(rel_path),
                    "severity": "error",
                    "message": f"Markdown file in unexpected location: {rel_path}",
                    "fix_hint": "Move to docs/ subdirectory or project root (if allowed)",
                }
            )

    return violations


def main() -> int:
    """CLI entry point for pre-commit hook."""
    import argparse

    parser = argparse.ArgumentParser(description="Check project structure")
    parser.add_argument("files", nargs="*", help="Files to check")
    parser.add_argument(
        "--project-root", type=Path, default=Path.cwd(), help="Project root directory"
    )
    parser.add_argument("--strict", action="store_true", help="Treat warnings as errors")
    args = parser.parse_args()

    project_root = args.project_root
    if not project_root.is_absolute():
        project_root = Path.cwd() / project_root

    violations = check_structure(project_root, args.files if args.files else None)

    if not violations:
        print("✓ Project structure OK")
        return 0

    errors = [v for v in violations if v["severity"] == "error"]
    warnings = [v for v in violations if v["severity"] == "warning"]

    if errors:
        print(f"\n❌ Structure errors ({len(errors)}):\n")
        for v in errors:
            print(f"  {v['file']}")
            print(f"    → {v['message']}")
            print(f"    Fix: {v['fix_hint']}\n")

    if warnings:
        print(f"\n⚠️  Structure warnings ({len(warnings)}):\n")
        for v in warnings:
            print(f"  {v['file']}")
            print(f"    → {v['message']}")
            print(f"    Fix: {v['fix_hint']}\n")

    if args.strict and (errors or warnings):
        return 1

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
