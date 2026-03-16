#!/usr/bin/env python3
"""Prevent documentation sprawl - update existing docs, don't create new ones.

Enforcement timing: Step 3 (pre-kilo) and Step 5 (post-kilo) via final_gate.py
NOT at commit time - pre-commit only runs 4 blockers.

Enforcement layers:
1. final_gate.py (Step 3 & 5) - Blocks new .md files in protected dirs
2. AI agent rules - Guides to correct file with topic mapping
3. Kilo review - Checks if update vs create was appropriate

Philosophy: Documentation consolidation prevents sprawl and keeps information findable.
"""

import re
from pathlib import Path

from .validate_conventions import CheckResult, Severity

# ENHANCED: Scan actual section headers + keywords + aliases
MASTER_DOCS = {
    "docs/TROUBLESHOOTING.md": {
        "keywords": [
            "infrastructure",
            "network",
            "dns",
            "ssh",
            "wsl",
            "wsl2",
            "connection",
            "timeout",
            "error",
            "fail",
            "resolve",
            "resolution",
            "nameserver",
            "ping",
            "curl",
            "socket",
            "port",
        ],
        "sections": [],  # Will be populated by scanning file
    },
    "docs/DEPLOYMENT.md": {
        "keywords": [
            "coolify",
            "docker",
            "vps",
            "deploy",
            "deployment",
            "container",
            "compose",
            "healthcheck",
            "dockerfile",
            "image",
            "build",
            "service",
        ],
        "sections": [],
    },
    "docs/CONFIGURATION.md": {
        "keywords": [
            "env",
            "config",
            "configuration",
            "credentials",
            "secrets",
            "api",
            "variable",
            "key",
            "token",
            "password",
        ],
        "sections": [],
    },
    "docs/traycer/TRAYCER-KILO-AGENTS-GUIDE.md": {
        "keywords": [
            "kilo",
            "agent",
            "timeout",
            "traycer",
            "cli",
            "review",
            "model",
            "gpt",
            "claude",
            "gemini",
        ],
        "sections": [],
    },
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


def _extract_sections(file_path: str) -> list[str]:
    """Extract markdown section headers from a file."""
    sections = []
    try:
        content = Path(file_path).read_text(encoding="utf-8")
        # Match ## Header or ### Header patterns
        pattern = r"^#{2,3}\s+(.+)$"
        for match in re.finditer(pattern, content, re.MULTILINE):
            sections.append(match.group(1).strip().lower())
    except Exception:
        pass
    return sections


def _fuzzy_score(keyword: str, text: str) -> float:
    """Calculate fuzzy match score (0.0-1.0).

    Scoring:
    - Exact match: 1.0
    - Word boundary match: 0.8
    - Substring match: 0.5
    - Partial match: 0.3
    """
    keyword = keyword.lower()
    text = text.lower()

    if keyword == text:
        return 1.0
    if f" {keyword} " in f" {text} " or text.startswith(keyword) or text.endswith(keyword):
        return 0.8
    if keyword in text:
        return 0.5
    # Partial match (at least 50% of keyword found)
    if len(keyword) >= 4:
        partial_len = len(keyword) // 2
        if keyword[:partial_len] in text or keyword[partial_len:] in text:
            return 0.3
    return 0.0


def find_best_match(new_filename: str) -> tuple[str | None, str]:
    """ENHANCED: Find best existing file using fuzzy matching + section analysis."""
    filename_lower = new_filename.lower().replace("-", " ").replace("_", " ")

    # Lazy load sections on first run
    for doc_path, doc_data in MASTER_DOCS.items():
        if not doc_data["sections"] and Path(doc_path).exists():
            doc_data["sections"] = _extract_sections(doc_path)

    best_match = None
    best_score = 0.0
    matched_items = []

    for master_doc, doc_data in MASTER_DOCS.items():
        score = 0.0
        matches = []

        # Score against keywords (weighted 2x)
        for keyword in doc_data["keywords"]:
            kw_score = _fuzzy_score(keyword, filename_lower)
            if kw_score > 0:
                score += kw_score * 2.0
                matches.append(f"kw:{keyword}")

        # Score against existing sections (weighted 1.5x)
        for section in doc_data["sections"]:
            sec_score = _fuzzy_score(section, filename_lower)
            if sec_score > 0:
                score += sec_score * 1.5
                matches.append(f"sec:{section}")

        if score > best_score:
            best_score = score
            best_match = master_doc
            matched_items = matches[:3]  # Top 3 matches

    if best_match and best_score >= 0.5:  # Minimum confidence threshold
        reason = f"Matched: {', '.join(matched_items)} (score: {best_score:.1f})"
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
