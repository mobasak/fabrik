#!/usr/bin/env python3
"""
Scan /opt/* project directories and report health status.

Checks each project for the presence of essential scaffold files.

Triggers:
- Manual: python scripts/health_summary.py
- CLI: fabrik scan --health

Outputs:
- stdout: aligned table (default) or JSON array (--json)

Workflow Doc: docs/workflows/HEALTH_SUMMARY_WORKFLOW.md
  ⚠️  Update the workflow doc when modifying this script.
"""

import argparse
import fnmatch
import json
import sys
from pathlib import Path

try:
    from scripts.sync_projects import _is_excluded
except ImportError:
    try:
        from sync_projects import _is_excluded
    except ImportError:
        DEFAULT_EXCLUDES = {"_*", ".*", "fabrik", "__pycache__", "venv", "google"}

        def _is_excluded(name: str) -> bool:
            return any(fnmatch.fnmatch(name, pattern) for pattern in DEFAULT_EXCLUDES)


ESSENTIAL_FILES: list[str] = [
    "AGENTS.md",
    ".env.example",
    "project.yaml",
    "compose.yaml",
    "Dockerfile",
    ".windsurf/rules/00-critical.md",
]

WARN_THRESHOLD = 1
MISSING_THRESHOLD = 3


def _determine_status(missing_count: int) -> str:
    if missing_count >= MISSING_THRESHOLD:
        return "missing"
    if missing_count >= WARN_THRESHOLD:
        return "warnings"
    return "healthy"


def scan_health(root: Path = Path("/opt")) -> list[dict[str, object]]:
    results: list[dict[str, object]] = []
    if not root.exists():
        return results

    for path in sorted(root.iterdir()):
        if not path.is_dir():
            continue
        if _is_excluded(path.name):
            continue

        missing = [required for required in ESSENTIAL_FILES if not (path / required).exists()]
        results.append(
            {
                "project": path.name,
                "path": str(path),
                "missing": missing,
                "status": _determine_status(len(missing)),
            }
        )

    return results


def print_table(results: list[dict[str, object]]) -> None:
    status_label = {
        "healthy": "✅ healthy",
        "warnings": "⚠️  warnings",
        "missing": "❌ missing",
    }

    rows: list[tuple[str, str, str]] = []
    for result in results:
        missing = result["missing"]
        missing_text = ", ".join(missing) if isinstance(missing, list) and missing else "-"
        rows.append(
            (
                str(result["project"]),
                status_label.get(str(result["status"]), str(result["status"])),
                missing_text,
            )
        )

    headers = ("Project", "Status", "Missing Files")
    widths = [
        max(len(headers[0]), *(len(row[0]) for row in rows)) if rows else len(headers[0]),
        max(len(headers[1]), *(len(row[1]) for row in rows)) if rows else len(headers[1]),
        max(len(headers[2]), *(len(row[2]) for row in rows)) if rows else len(headers[2]),
    ]

    def _line(values: tuple[str, str, str]) -> str:
        return f"{values[0]:<{widths[0]}} | {values[1]:<{widths[1]}} | {values[2]:<{widths[2]}}"

    print(_line(headers))
    print(f"{'-' * widths[0]}-+-{'-' * widths[1]}-+-{'-' * widths[2]}")
    for row in rows:
        print(_line(row))

    healthy_count = sum(1 for result in results if result.get("status") == "healthy")
    warnings_count = sum(1 for result in results if result.get("status") == "warnings")
    missing_count = sum(1 for result in results if result.get("status") == "missing")
    print(
        f"{len(results)} projects scanned — "
        f"{healthy_count} healthy, {warnings_count} warnings, {missing_count} missing"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Scan project scaffolds and report health status.")
    parser.add_argument("--json", action="store_true", help="Output JSON instead of a table.")
    parser.add_argument("--base", type=Path, default=Path("/opt"), help="Base directory to scan.")
    args = parser.parse_args()

    results = scan_health(root=args.base)

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print_table(results)

    has_issues = any(result.get("status") in {"warnings", "missing"} for result in results)
    return 1 if has_issues else 0


if __name__ == "__main__":
    sys.exit(main())
