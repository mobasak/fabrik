#!/usr/bin/env python3
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

from .validate_conventions import CheckResult, Severity

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
        "docs/BUSINESS_MODEL.md",
        "docs/FEATURES.md",
        "docs/development/PLANS.md",
        "docs/archive/README.md",
    }
)

# Allowed patterns for new files - STRICT matchers
ALLOWED_PATTERNS = [
    # Dated plan documents: docs/development/plans/YYYY-MM-DD-plan-<name>.md
    # New dated plan files are allowed as part of the planning workflow
    re.compile(r"^docs/development/plans/\d{4}-\d{2}-\d{2}-plan-.+\.md$"),
    # Archive at ANY depth: docs/archive/**/*.md (but not docs/archive.md itself)
    # Allows: docs/archive/foo.md, docs/archive/2026/03/foo.md
    # Blocks: docs/archive.md
    # Rationale: Agents may automatically archive completed plans
    re.compile(r"^docs/archive/(?!$).+\.md$"),
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
    """Check if file is tracked in git (repo-relative path)."""
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


def get_suggestion(path_str: str) -> str:
    """Provide helpful suggestion based on blocked path."""
    if path_str.startswith("docs/development/plans/"):
        if not re.match(r"\d{4}-\d{2}-\d{2}", path_str.split("/")[-1]):
            return "Use format: docs/development/plans/YYYY-MM-DD-plan-<name>.md (zero-padded date)"
        return "Plan filename must start with YYYY-MM-DD-plan-"

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
    results = []

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

    # ALLOW: Tracked files (edits to existing docs)
    if is_tracked(rel_path, repo_root):
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
