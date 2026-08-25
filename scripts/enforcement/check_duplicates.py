#!/usr/bin/env python3
"""Check for code duplication using jscpd.

This script wraps jscpd to detect copy-paste code across the codebase.
It's used in CI to prevent excessive duplication.
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


def run_jscpd(report_path: Path) -> dict[str, Any]:
    """Run jscpd and return the JSON report."""
    # Run jscpd with JSON reporter
    subprocess.run(
        [
            "jscpd",
            "--reporters",
            "json",
            "--output",
            str(report_path.parent),
            "--ignore",
            # Generated DATA (caches, scraped HTML, model dumps, sqlite) is not
            # hand-written code — excluding it keeps jscpd a copy-paste-CODE check.
            # Without this, kilo-benchmarks caches + model JSON dumps alone push
            # duplication ~3x over threshold (surfaced 2026-06-13 after an
            # unpinned jscpd version bump tipped CI red).
            "**/.venv/**,**/node_modules/**,**/__pycache__/**,**/dist/**,**/.git/**,"
            "**/.archive/**,**/archive/**,**/traycer_agents_fixed/**,"
            "**/kilo-benchmarks/**,scripts/*.json,scripts/.*.json,"
            # Backup/snapshot artifacts (a *_bckp copy of a live file is the
            # single biggest false-positive: 5768 dup lines on its own).
            "**/*_bckp.*,**/*.old,**/*.bak",
            "--min-lines",
            "10",
            "--min-tokens",
            "50",
            "src/",
            "scripts/",
        ],
        capture_output=True,
        text=True,
    )

    # jscpd returns exit code 0 even with duplicates found
    # The JSON report is written to the output directory
    json_report = report_path.parent / "jscpd-report.json"
    if json_report.exists():
        report: dict[str, Any] = json.loads(json_report.read_text())
        return report
    return {"statistics": {"total": {"duplicatedLines": 0, "percentage": 0}}, "duplicates": []}


def check_duplicates(report_path: Path, threshold: float = 5.0) -> int:
    """Check for code duplication and report results.

    Args:
        report_path: Path to write the report
        threshold: Maximum allowed duplication percentage

    Returns:
        Exit code (0 = pass, 1 = fail)
    """
    try:
        report = run_jscpd(report_path)
    except FileNotFoundError:
        print("WARNING: jscpd not installed, skipping duplicate check")
        # Write empty report
        report_path.write_text(json.dumps({"status": "skipped", "reason": "jscpd not installed"}))
        return 0

    stats = report.get("statistics", {}).get("total", {})
    duplicated_lines = stats.get("duplicatedLines", 0)
    percentage = stats.get("percentage", 0)
    duplicates = report.get("duplicates", [])

    # Write our simplified report
    our_report = {
        "status": "pass" if percentage <= threshold else "fail",
        "duplicated_lines": duplicated_lines,
        "percentage": round(percentage, 2),
        "threshold": threshold,
        "duplicate_count": len(duplicates),
        "duplicates": [
            {
                "lines": d.get("lines", 0),
                "tokens": d.get("tokens", 0),
                "firstFile": d.get("firstFile", {}).get("name", ""),
                "secondFile": d.get("secondFile", {}).get("name", ""),
            }
            for d in duplicates[:10]  # Limit to top 10
        ],
    }
    report_path.write_text(json.dumps(our_report, indent=2))

    # Print summary
    print(f"Duplicate check: {percentage:.1f}% duplication ({duplicated_lines} lines)")
    if duplicates:
        print(f"Found {len(duplicates)} duplicate blocks")
        for d in duplicates[:5]:
            first = d.get("firstFile", {}).get("name", "?")
            second = d.get("secondFile", {}).get("name", "?")
            lines = d.get("lines", 0)
            print(f"  - {first} <-> {second} ({lines} lines)")

    if percentage > threshold:
        print(f"FAIL: Duplication {percentage:.1f}% exceeds threshold {threshold}%")
        return 1

    # DENOMINATOR (enforcement-battery audit 2026-08-25): "within threshold" is true when the
    # analyser found 0.0% because it scanned nothing — jscpd absent, no source, or a failed
    # run — and that reads identically to a genuinely clean repo. Carry the measured figure.
    # See docs/reference/enforcement-battery-audit.md.
    print(
        f"PASS: Duplication within threshold — {percentage:.1f}% of {duplicated_lines} "
        f"duplicated line(s), {len(duplicates)} block(s), threshold {threshold}%"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Check for code duplication")
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("duplicate-report.json"),
        help="Path to write the report",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=7.0,
        help="Maximum allowed duplication percentage",
    )
    args = parser.parse_args()

    return check_duplicates(args.report, args.threshold)


if __name__ == "__main__":
    sys.exit(main())
