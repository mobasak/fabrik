#!/usr/bin/env python3
# AFTER-EDIT: none
"""Default-deny policy for new .md files - systematic anti-sprawl enforcement.

Enforcement timing: Step 3 (pre-kilo) and Step 5 (post-kilo) via final_gate.py

Policy:

- ALLOW: Edits to tracked .md files (git tracked)
- ALLOW: New files matching exact allowlists (root + docs scaffold)
- ALLOW: New files matching strict patterns (plans, archive)
- BLOCK: All other new .md files

Philosophy: Systematic default-deny prevents sprawl. All legitimate new docs
must match explicit allowlist or pattern.
"""

import re
import subprocess
from pathlib import Path

# Works whether invoked as a package import (e.g. by pytest) OR as a
# standalone script (e.g. final_gate.py `python scripts/enforcement/...`).
# Mirrors the dual-path pattern in check_vps_docs.py / check_env_vars.py.
try:
    from .validate_conventions import CheckResult, Severity
except ImportError:
    from validate_conventions import CheckResult, Severity  # type: ignore[no-redef]

# Root level - CLOSED allowlist
ALLOWED_NEW_ROOT_DOCS = frozenset(
    {
        "INDEX.md",
        "README.md",
        "CHANGELOG.md",
        "AGENTS.md",
    }
)

# Docs scaffold-created files - CLOSED allowlist
ALLOWED_NEW_DOCS_SCAFFOLD = frozenset(
    {
        "docs/.doc-policy.md",
        "docs/README.md",
        "docs/QUICKSTART.md",
        "docs/CONFIGURATION.md",
        "docs/TROUBLESHOOTING.md",
        "docs/SERVICES.md",
        "docs/OPERATIONS.md",
        "docs/BUSINESS_MODEL.md",
        "docs/FEATURES.md",
        "docs/development/PLANS.md",
        "docs/archive/README.md",
        "docs/data-contract.md",  # frozen field dict (scaffold-seeded; /fabrik-data-contract)
        "docs/ui-design.md",  # frozen screen+flow contract (/fabrik-ui-design, on demand)
    }
)

# ⚠️ KNOWN-INERT in the two ENFORCEMENT call paths (pre-existing, verified
# 2026-08-04) — the script has no __main__ (final_gate's Tier-2 invocation
# always exits 0) and check_file() feeds a RELATIVE path into relative_to(abs)
# (ValueError → []) in the validate_conventions path. Activating it is a
# fleet-behavior change (every project with stray .md files would newly red) and
# needs its own plan — flagged to the operator; do not silently "fix" it here.
# Allowed patterns for new files - STRICT matchers
ALLOWED_PATTERNS = [
    # Dated plan documents: docs/development/plans/YYYY-MM-DD-plan-<name>.md —
    # FLAT only ([^/]+): nested paths are governed by the spine+ticket pattern
    # below, so junk like <plan-dir>/notes/scratch.md is no longer admitted by
    # `.` crossing `/` (the accidental-admission hole).
    re.compile(r"^docs/development/plans/\d{4}-\d{2}-\d{2}-plan-[^/]+\.md$"),
    # Spine+ticket plan sets: docs/development/plans/YYYY-MM-DD-plan-<slug>/ holding
    # the same-stem spine + T##[a-z]?-<slug>.md tickets. The pattern above already
    # admits these paths accidentally (`.` matches `/`); this matcher makes the
    # nested admission INTENTIONAL (stem-identity itself is check_plan_tickets' job).
    re.compile(
        r"^docs/development/plans/\d{4}-\d{2}-\d{2}-plan-[a-z0-9-]+/"
        r"(T\d{2}[a-z]?-[a-z0-9-]+|\d{4}-\d{2}-\d{2}-plan-[a-z0-9-]+)\.md$"
    ),
    # Review artifacts: docs/development/reviews/<name>-review.md
    # Paired with the convergence-evidence gate (check_convergence.py) — a code
    # review embeds its final_gate proof here as part of the review workflow.
    re.compile(r"^docs/development/reviews/.+-review\.md$"),
    # Archive at ANY depth: docs/archive/**/*.md (but not docs/archive.md itself)
    # Allows: docs/archive/foo.md, docs/archive/2026/03/foo.md
    # Blocks: docs/archive.md
    # Rationale: Agents may automatically archive completed plans
    re.compile(r"^docs/archive/(?!$).+\.md$"),
    # Superpowers spec/plan pipeline: /fabrik-spec writes designs to
    # docs/superpowers/specs/ and superpowers:writing-plans writes to
    # docs/superpowers/plans/. Both are in the CLAUDE.md new-.md allowlist
    # (docs/superpowers/plans/** · docs/superpowers/specs/**); this matcher keeps
    # the gate in lockstep with the contract so those artifacts don't red the gate.
    re.compile(r"^docs/superpowers/(plans|specs)/.+\.md$"),
    # Epic tickets: docs/development/epics/YYYY-MM-DD-epic-<n>-<slug>.md
    # Written by mega-epic-breakdown/03-expand-epic-files-fabrik, one file per epic.
    # Unlike Traycer (which has a native ticket store), our orchestrator has none —
    # disk IS the ticket store, so 05-dispatch and epic-to-ticket can read an epic
    # back on a fresh context instead of losing the whole breakdown with the window.
    # Same dated shape as the plans pattern above, deliberately: one artifact per file,
    # greppable, and unambiguously distinct from a plan.
    re.compile(r"^docs/development/epics/\d{4}-\d{2}-\d{2}-epic-\d+-.+\.md$"),
    # Orchestrator cockpit + our runnable workflow definitions: docs/orchestrator/**
    # The `-fabrik` command files, their EVALUATION_CHECKLISTs, the north-star, and the
    # cockpit design docs live here (moved out of docs/traycer/ 2026-07-17, which keeps
    # the Traycer `-command` twins). Hub-only path; harmless on projects (dir absent).
    re.compile(r"^docs/orchestrator/.+\.md$"),
]


def get_repo_root() -> Path:
    """Get git repository root directory."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            return Path(result.stdout.strip())
    except Exception:
        pass
    # Fallback to current directory if git fails
    return Path.cwd()


def is_tracked(rel_path: Path, repo_root: Path) -> bool:
    """Check if file is tracked in git (repo-relative path; INDEX lookup)."""
    try:
        result = subprocess.run(
            ["git", "ls-files", "--error-unmatch", str(rel_path)],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
        return result.returncode == 0
    except Exception:
        # If git fails (not a repo, etc.), treat as untracked
        return False


def path_is_existing(rel_path: Path, repo_root: Path) -> bool:
    """A path counts as an EXISTING doc (exempt from the new-file allowlist) only if:

    - it is present in HEAD (a committed doc being edited), OR
    - its staged status is a rename (``R*``) from a tracked path (``git mv`` — the
      content pre-existed under another name).

    A brand-new file that was merely ``git add``-ed is NOT existing — the old
    index-based ``is_tracked()`` early-allow let any staged addition bypass the
    default-deny allowlist entirely (docs-truth plan Phase F fix).
    """
    try:
        in_head = subprocess.run(
            ["git", "cat-file", "-e", f"HEAD:{rel_path}"],
            cwd=repo_root,
            capture_output=True,
            check=False,
        )
        if in_head.returncode == 0:
            return True
        # NOTE: no pathspec — limiting status to the new path makes git report a
        # staged rename as a plain "A" (it can't see both sides), hiding the R.
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
        rel_str = str(rel_path).replace("\\", "/")
        archive_prefixes = (
            "docs/archive/",
            "docs/infrastructure/archive/",
            "docs/development/plans/archived/",
            "docs/superpowers/specs/archived/",
            "docs/superpowers/plans/archived/",
        )
        for line in status.stdout.splitlines():
            if line[:1] != "R" or " -> " not in line:
                continue
            src_part = line[3:].split(" -> ", 1)[0].strip().strip('"')
            dst_part = line.split(" -> ", 1)[-1].strip().strip('"')
            if dst_part != rel_str:
                continue
            # A rename only counts as "existing" when its SOURCE was a live doc:
            # moving a file OUT of an archive (or any allowlist-only location)
            # into a default-denied dir is new content appearing there — run the
            # allowlist (closes the rename-smuggle hole, Phase-F review 1a).
            return not src_part.startswith(archive_prefixes)
        return False
    except Exception:
        # Git unavailable → fall back to the permissive legacy behavior so the
        # gate never hard-fails outside a repo.
        return is_tracked(rel_path, repo_root)


def get_suggestion(path_str: str) -> str:
    """Provide helpful suggestion based on blocked path."""
    if path_str.startswith("docs/development/plans/"):
        if not re.match(r"\d{4}-\d{2}-\d{2}|T\d{2}[a-z]?-", path_str.split("/")[-1]):
            return (
                "Use format: docs/development/plans/YYYY-MM-DD-plan-<name>.md, or a "
                "spine+ticket set: YYYY-MM-DD-plan-<slug>/ holding the same-stem spine "
                "+ T##-<slug>.md tickets"
            )
        return (
            "Plan filename must start with YYYY-MM-DD-plan- (tickets T##-<slug>.md are "
            "valid only inside a dated plan directory)"
        )

    if path_str.startswith("docs/traycer/"):
        return "UPDATE existing docs/traycer/*.md files instead. New files blocked."

    if path_str.startswith("docs/infrastructure/"):
        return "UPDATE docs/TROUBLESHOOTING.md instead. docs/infrastructure/ is blocked."

    if path_str.startswith("docs/operations/"):
        return "UPDATE docs/DEPLOYMENT.md instead. docs/operations/ is blocked."

    if path_str.startswith("docs/"):
        return (
            "UPDATE existing docs/*.md (see docs/.doc-policy.md)."
            " New docs files limited to scaffold set."
        )

    if path_str.startswith(".droid/review-context/"):
        return (
            "Review context files (.droid/review-context/*.md) are blocked."
            " Agent artifacts should not be auto-created."
        )

    if "/" not in path_str:  # root level
        root_list = ", ".join(sorted(ALLOWED_NEW_ROOT_DOCS))
        return f"Root .md files limited to: {root_list}"

    return (
        "New .md files blocked by default-deny policy."
        " Update existing docs or use allowed patterns."
    )


def check_file(file_path: Path) -> list[CheckResult]:
    """Default-deny policy: block all new .md except explicit allowlist/patterns."""
    results: list[CheckResult] = []

    # Normalize suffix case for cross-platform compatibility
    if file_path.suffix.lower() != ".md":
        return results

    # Cache repo root for efficiency
    repo_root = get_repo_root()

    try:
        rel_path = file_path.relative_to(repo_root)
    except ValueError:
        return results

    path_str = str(rel_path).replace("\\", "/")  # Normalize for Windows

    # ALLOW: Existing docs only — present in HEAD or a staged RENAME of a tracked
    # doc. A staged brand-new file is NOT existing (the old index-based check let
    # any `git add`-ed .md bypass the allowlist).
    if path_is_existing(rel_path, repo_root):
        return results

    # ALLOW: Root allowlist (exact match)
    if path_str in ALLOWED_NEW_ROOT_DOCS:
        return results

    # ALLOW: Docs scaffold files (exact match)
    if path_str in ALLOWED_NEW_DOCS_SCAFFOLD:
        return results

    # ALLOW: Pattern matches (strict)
    for pattern in ALLOWED_PATTERNS:
        if pattern.match(path_str):
            return results

    # BLOCK: Everything else (default-deny)
    results.append(
        CheckResult(
            check_name="doc_sprawl",
            severity=Severity.ERROR,
            message=(
                f"BLOCKED: New .md file '{file_path.name}' not in allowlist"
                " or allowed patterns (default-deny)"
            ),
            file_path=path_str,
            fix_hint=get_suggestion(path_str),
        )
    )

    return results
