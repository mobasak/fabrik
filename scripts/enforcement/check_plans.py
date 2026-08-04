# AFTER-EDIT: tests/enforcement/test_plan_shape_gates.py | scripts/enforcement/check_plan_quality.py
"""Check plan document conventions.

Enforces:
- Plan files must be in docs/development/plans/
- Plan filenames must match YYYY-MM-DD-plan-<name>.md pattern
- Ticket files (T01-<slug>.md, auto-split T01a-<slug>.md) are valid ONLY inside a
  dated plan directory (YYYY-MM-DD-plan-<slug>/ — the spine+ticket plan shape);
  anywhere else under plans/** they keep today's ERROR.

Note: Index completeness is enforced by docs_updater.py --check (single authority).
"""

import re
import subprocess
from pathlib import Path

from .validate_conventions import CheckResult, Severity

# Check project's own plans directory
PLAN_DIR = Path.cwd() / "docs" / "development" / "plans"
# New format: YYYY-MM-DD-plan-<name>.md (e.g., 2026-01-14-plan-feature-name.md)
# Also accept legacy format for backward compatibility: YYYY-MM-DD-<slug>.md
PLAN_NAME_NEW_RE = re.compile(r"\d{4}-\d{2}-\d{2}-plan-[a-z0-9-]+\.md$")
PLAN_NAME_LEGACY_RE = re.compile(r"\d{4}-\d{2}-\d{2}-[a-z0-9-]+\.md$")
# Spine+ticket shape: canonical ticket filename, valid only inside a dated plan dir
# (the parent-name test covers plans/<dir>/ AND plans/archived/<dir>/ — the
# whole-directory archive move must not red the gate).
TICKET_NAME_RE = re.compile(r"^T\d{2}[a-z]?-[a-z0-9-]+\.md$")
PLAN_DIR_NAME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-plan-[a-z0-9-]+$")
# Tooling-owned files with fixed non-dated names (never a naming violation):
# 00-research.md is the pre-research drop point (agents-fabrik.md) written by
# scripts/audit_all_projects.py into ~20 projects fleet-wide.
_TOOLING_NAMES = ("00-research.md", "plans.md")


def _tracked_at_head(file_path: Path) -> bool:
    """True when the file exists at HEAD — a PRE-EXISTING non-conforming name is
    someone's settled history (33 such files fleet-wide) and must WARN, not
    ERROR; only a NEW bad name is this change's violation. HEAD semantics, not
    the index — a freshly `git add`ed bad name is still NEW (the gate
    auto-stages, so index membership proves nothing); a no-HEAD repo (fresh
    scaffold) reads as NEW too — correct, the file was never committed. cwd =
    the file's own directory (correct across repos). Fail-soft only on
    PLUMBING exceptions (missing git binary, timeout) — those read as tracked."""
    try:
        out = subprocess.run(
            ["git", "ls-tree", "--name-only", "HEAD", "--", f":(literal){file_path.name}"],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=file_path.parent,
        )
        return out.returncode == 0 and bool(out.stdout.strip())
    except Exception:
        return True


def check_file(file_path: Path) -> list[CheckResult]:
    """Enforce: plans folder + YYYY-MM-DD-plan-<name>.md naming (or a ticket in a dated dir)."""
    results: list[CheckResult] = []

    if file_path.suffix != ".md":
        return results

    # validate_conventions feeds RELATIVE paths (git diff --name-only); PLAN_DIR is
    # absolute — without resolve() the is_relative_to test is always False and this
    # whole gate silently no-ops in the production caller.
    file_path = file_path.resolve()

    # Check if file is in plan folder - enforce naming convention
    try:
        if file_path.is_relative_to(PLAN_DIR):
            # plans/archived/** is settled history (free-named pre-convention files
            # live there); the resolve() fix above activates this gate for the
            # first time, so without this carve-out an archive move / link sweep
            # would newly ERROR ~40 files nobody edited.
            if "archived" in file_path.relative_to(PLAN_DIR).parts:
                return results
            # Skip README.md, index files, and tooling-owned fixed names
            if file_path.name.lower() in ("readme.md", "index.md", *_TOOLING_NAMES):
                return results
            # Ticket file inside a dated plan directory → valid (spine+ticket shape)
            if TICKET_NAME_RE.match(file_path.name) and PLAN_DIR_NAME_RE.match(
                file_path.parent.name
            ):
                return results
            # Check new format first, then legacy
            if not PLAN_NAME_NEW_RE.match(file_path.name):
                if PLAN_NAME_LEGACY_RE.match(file_path.name):
                    # Legacy format - warn but don't error
                    results.append(
                        CheckResult(
                            check_name="plan_naming",
                            severity=Severity.WARN,
                            message=f"Legacy plan filename: {file_path.name}",
                            file_path=str(file_path),
                            fix_hint="Consider renaming to YYYY-MM-DD-plan-<name>.md format",
                        )
                    )
                else:
                    results.append(
                        CheckResult(
                            check_name="plan_naming",
                            # Pre-existing (tracked) bad names are settled history
                            # fleet-wide → WARN; only a NEW bad name hard-ERRORs.
                            severity=(
                                Severity.WARN if _tracked_at_head(file_path) else Severity.ERROR
                            ),
                            message=f"Invalid plan filename: {file_path.name}",
                            file_path=str(file_path),
                            fix_hint=(
                                "Rename to YYYY-MM-DD-plan-<name>.md format"
                                " (e.g., 2026-01-14-plan-my-feature.md); ticket files"
                                " (T01-<slug>.md) are valid only inside a dated plan"
                                " directory (YYYY-MM-DD-plan-<slug>/)"
                            ),
                        )
                    )
    except ValueError:
        # Not relative to PLAN_DIR - that's fine, not a plan file
        pass

    return results
