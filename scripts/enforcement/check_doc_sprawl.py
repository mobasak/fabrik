#!/usr/bin/env python3
"""Prevent documentation sprawl - update existing docs, don't create new ones.

Enforcement layers:
1. final_gate.py - Blocks new .md files in protected dirs
2. AI agent rules - Guides to correct file
3. Kilo review - Checks if update vs create was appropriate

Philosophy: Documentation consolidation prevents sprawl and keeps information findable.
"""

from pathlib import Path

from .validate_conventions import CheckResult, Severity

# AUTO-DETECT: Scan these files for section headers to build topic map
MASTER_DOCS = {
    "docs/TROUBLESHOOTING.md": [
        "infrastructure",
        "network",
        "dns",
        "ssh",
        "wsl",
        "connection",
        "timeout",
        "error",
    ],
    "docs/DEPLOYMENT.md": [
        "coolify",
        "docker",
        "vps",
        "deploy",
        "container",
        "compose",
        "healthcheck",
    ],
    "docs/CONFIGURATION.md": ["env", "config", "credentials", "secrets", "api", "variable", "key"],
    "docs/traycer/TRAYCER-KILO-AGENTS-GUIDE.md": [
        "kilo",
        "agent",
        "timeout",
        "traycer",
        "cli",
        "review",
        "model",
    ],
}

# Completely blocked directories (use parent doc instead)
BLOCKED_DIRS = {
    "docs/infrastructure/",
    "docs/operations/",
}

# Allowed files in docs/ root
ALLOWED_DOCS_ROOT = {
    "README.md",
    "QUICKSTART.md",
    "CONFIGURATION.md",
    "TROUBLESHOOTING.md",
    "BUSINESS_MODEL.md",
    "SERVICES.md",
    "DEPLOYMENT.md",
    "EXTERNAL_SYSTEMS.md",
    "FAQ.md",
    "FEATURES.md",
    "TESTING.md",
}


def find_best_match(new_filename: str) -> tuple[str | None, str]:
    """Find best existing file to update based on filename and content analysis."""
    filename_lower = new_filename.lower().replace("-", " ").replace("_", " ")

    best_match = None
    best_score = 0
    matched_keywords = []

    for master_doc, keywords in MASTER_DOCS.items():
        score = sum(1 for kw in keywords if kw in filename_lower)

        if score > best_score:
            best_score = score
            best_match = master_doc
            matched_keywords = [kw for kw in keywords if kw in filename_lower]

    if best_match and matched_keywords:
        reason = f"Matched keywords: {', '.join(matched_keywords)}"
        return best_match, reason

    return None, ""


def check_file(file_path: Path) -> list[CheckResult]:
    """Block new docs in protected directories, suggest existing files."""
    results = []

    if file_path.suffix != ".md":
        return results

    try:
        rel_path = file_path.relative_to(Path.cwd())
    except ValueError:
        return results

    path_str = str(rel_path)

    # Check completely blocked directories
    for blocked_dir in BLOCKED_DIRS:
        if path_str.startswith(blocked_dir):
            parent_doc = (
                "docs/TROUBLESHOOTING.md"
                if "infrastructure" in blocked_dir
                else "docs/DEPLOYMENT.md"
            )

            results.append(
                CheckResult(
                    check_name="doc_sprawl",
                    severity=Severity.ERROR,
                    message=f"BLOCKED: Directory '{blocked_dir}' does not allow new files",
                    file_path=str(rel_path),
                    fix_hint=f"UPDATE {parent_doc} instead. Add a new section for your content.",
                )
            )
            return results

    # Check docs/ root - only allowed files
    if path_str.startswith("docs/") and "/" not in path_str[5:]:  # File directly in docs/
        if file_path.name not in ALLOWED_DOCS_ROOT:
            results.append(
                CheckResult(
                    check_name="doc_sprawl",
                    severity=Severity.ERROR,
                    message=f"BLOCKED: '{file_path.name}' not in allowed docs/ root files",
                    file_path=str(rel_path),
                    fix_hint=f"Update one of: {', '.join(sorted(ALLOWED_DOCS_ROOT)[:3])}...",
                )
            )
            return results

    # Auto-detect best match for other protected areas
    if path_str.startswith("docs/traycer/"):
        # Check if new file (not in git or empty)
        is_new = not file_path.exists() or file_path.stat().st_size == 0

        if is_new:
            best_match, reason = find_best_match(file_path.stem)

            if best_match:
                fix_hint = f"UPDATE {best_match} instead. {reason}"
            else:
                fix_hint = (
                    "Update docs/traycer/TRAYCER-KILO-AGENTS-GUIDE.md or docs/traycer/README.md"
                )

            results.append(
                CheckResult(
                    check_name="doc_sprawl",
                    severity=Severity.ERROR,
                    message=f"BLOCKED: New doc '{file_path.name}' in protected traycer/ directory",
                    file_path=str(rel_path),
                    fix_hint=fix_hint,
                )
            )

    return results
