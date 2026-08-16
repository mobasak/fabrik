#!/usr/bin/env python3
# AFTER-EDIT: tests/test_check_vps_docs_severity.py docs/workflows/FINAL_GATE_WORKFLOW.md
"""Check VPS documentation freshness.

Parses 'Last Updated:' dates from VPS ops docs and flags them if stale
(older than MAX_STALE_DAYS). Runs as part of the systemic gate (Tier 3).

SEVERITY CONTRACT (fixed 2026-08-16). Every finding this module can construct is
``Severity.WARN`` — a missing doc, an absent date header, a stale date. The entry point
nevertheless exited 1 on ANY finding, so a warning-level condition failed a blocking gate
row: the hub went red because this check pointed at ``docs/operations/`` where
``vps-status.md`` / ``vps-urls.md`` never lived — they are in ``docs/infrastructure/``.
A stale or absent VPS doc is a refresh chore (``fabrik vps-sync``), not a defect in the
change under gate.

The exit code now follows the severity, matching ``_check_runner.run_as_main``:

* ``ERROR`` findings fail (exit 1). None exist here today; the day one is added it bites.
* ``WARN`` findings are reported and exit 0.
* ``--strict`` promotes WARN to failing — the activation switch, used once the VPS docs
  are reliably regenerated.

Regenerating the docs is ``fabrik vps-sync``; this module only ever reads them.
"""

import argparse
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

try:
    from .validate_conventions import CheckResult, Severity
except ImportError:
    from validate_conventions import CheckResult, Severity  # type: ignore[no-redef]

FABRIK_ROOT = Path("/opt/fabrik")

VPS_DOCS = [
    FABRIK_ROOT / "docs" / "infrastructure" / "vps-status.md",
    FABRIK_ROOT / "docs" / "infrastructure" / "vps-urls.md",
    FABRIK_ROOT / "docs" / "infrastructure" / "vps-complete-inventory.md",
]

MAX_STALE_DAYS = 30

# Matches patterns like: **Last Updated:** 2026-05-03 or **Date:** 2026-05-03
DATE_PATTERN = re.compile(r"\*\*(?:Last Updated|Date):\*\*\s*(\d{4}-\d{2}-\d{2})")


def check_vps_doc_freshness(
    changed_files: list[Path] | None = None,  # noqa: ARG001
) -> list[CheckResult]:
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


def check_file(file_path: Path) -> list[CheckResult]:  # noqa: ARG001
    """Entry point for single-file enforcement (no-op for this check)."""
    return []


def main(argv: list[str] | None = None) -> int:
    """Report VPS doc freshness; fail only on ERROR (or on WARN under ``--strict``)."""
    parser = argparse.ArgumentParser(prog="check_vps_docs", description=__doc__)
    parser.add_argument(
        "--strict", action="store_true", help="fail on WARN findings too, not just ERROR"
    )
    args = parser.parse_args(argv)

    findings = check_vps_doc_freshness()
    errors = [f for f in findings if f.severity is Severity.ERROR]
    warns = [f for f in findings if f.severity is not Severity.ERROR]
    for f in findings:
        print(f"[{f.severity.name}] {f.message}")
        if f.fix_hint:
            print(f"  Fix: {f.fix_hint}")

    failing = bool(errors) or (args.strict and bool(warns))
    verdict = "FAIL" if failing else "PASS"
    scope = "errors+warns" if args.strict else "errors"
    print(
        f"{verdict}: check_vps_docs — {len(errors)} error(s), {len(warns)} warning(s)"
        f" [failing on: {scope}]"
    )
    return 1 if failing else 0


if __name__ == "__main__":
    sys.exit(main())
