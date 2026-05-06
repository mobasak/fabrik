#!/usr/bin/env python3
"""Check VPS documentation freshness.

Parses 'Last Updated:' dates from VPS ops docs and flags them if stale
(older than MAX_STALE_DAYS). Runs as part of the systemic gate (Tier 3).
"""

import re
from datetime import datetime, timedelta
from pathlib import Path

try:
    from .validate_conventions import CheckResult, Severity
except ImportError:
    from validate_conventions import CheckResult, Severity

FABRIK_ROOT = Path("/opt/fabrik")

VPS_DOCS = [
    FABRIK_ROOT / "docs" / "operations" / "vps-status.md",
    FABRIK_ROOT / "docs" / "operations" / "vps-urls.md",
    FABRIK_ROOT / "docs" / "infrastructure" / "vps-complete-inventory.md",
]

MAX_STALE_DAYS = 30

# Matches patterns like: **Last Updated:** 2026-05-03 or **Date:** 2026-05-03
DATE_PATTERN = re.compile(r"\*\*(?:Last Updated|Date):\*\*\s*(\d{4}-\d{2}-\d{2})")


def check_vps_doc_freshness(changed_files: list[Path] | None = None) -> list[CheckResult]:
    """Check that VPS docs have been updated within MAX_STALE_DAYS."""
    results: list[CheckResult] = []
    now = datetime.now()
    threshold = now - timedelta(days=MAX_STALE_DAYS)

    for doc_path in VPS_DOCS:
        if not doc_path.exists():
            results.append(
                CheckResult(
                    check_name="vps_doc_freshness",
                    severity=Severity.WARN,
                    message=f"VPS doc missing: {doc_path.name}",
                    file_path=str(doc_path),
                    fix_hint="Run `fabrik vps-sync` to regenerate VPS docs.",
                )
            )
            continue

        content = doc_path.read_text(errors="replace")
        match = DATE_PATTERN.search(content)
        if not match:
            results.append(
                CheckResult(
                    check_name="vps_doc_freshness",
                    severity=Severity.WARN,
                    message=f"No 'Last Updated' date found in {doc_path.name}",
                    file_path=str(doc_path),
                    fix_hint="Add **Last Updated:** YYYY-MM-DD to the file header.",
                )
            )
            continue

        try:
            updated = datetime.strptime(match.group(1), "%Y-%m-%d")
        except ValueError:
            continue

        age_days = (now - updated).days
        if updated < threshold:
            results.append(
                CheckResult(
                    check_name="vps_doc_freshness",
                    severity=Severity.WARN,
                    message=(
                        f"{doc_path.name} is {age_days} days old "
                        f"(last updated {match.group(1)}, threshold {MAX_STALE_DAYS}d)"
                    ),
                    file_path=str(doc_path),
                    fix_hint="Run `fabrik vps-sync` to refresh from live VPS state.",
                )
            )

    return results


def check_file(file_path: Path) -> list[CheckResult]:
    """Entry point for single-file enforcement (no-op for this check)."""
    return []


if __name__ == "__main__":
    findings = check_vps_doc_freshness()
    if findings:
        for f in findings:
            print(f"[{f.severity.name}] {f.message}")
            if f.fix_hint:
                print(f"  Fix: {f.fix_hint}")
        raise SystemExit(1)
    print("VPS docs are fresh.")
    raise SystemExit(0)
