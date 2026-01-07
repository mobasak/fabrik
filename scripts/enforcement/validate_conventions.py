#!/usr/bin/env python3
"""Fabrik Convention Validator - Orchestrates all convention checks.

Called by:
    - Windsurf Cascade hooks
    - droid exec PostToolUse hooks
    - CI/CD pipelines

Exit codes:
    0 = pass
    1 = warn (non-blocking)
    2 = block (critical violation)
"""

import argparse
import json
import subprocess
import sys
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path


class Severity(Enum):
    PASS = "pass"
    WARN = "warn"
    ERROR = "error"


@dataclass
class CheckResult:
    """Result of a single convention check."""

    check_name: str
    severity: Severity
    message: str
    file_path: str | None = None
    line_number: int | None = None
    fix_hint: str | None = None

    def to_dict(self) -> dict:
        result = asdict(self)
        result["severity"] = self.severity.value
        return result


def run_check_env_vars(file_path: Path) -> list[CheckResult]:
    """Check for hardcoded localhost/127.0.0.1."""
    from .check_env_vars import check_file

    return check_file(file_path)


def run_check_secrets(file_path: Path) -> list[CheckResult]:
    """Check for hardcoded secrets."""
    from .check_secrets import check_file

    return check_file(file_path)


def run_check_health(file_path: Path) -> list[CheckResult]:
    """Check health endpoint tests dependencies."""
    from .check_health import check_file

    return check_file(file_path)


def run_check_docker(file_path: Path) -> list[CheckResult]:
    """Check Docker conventions (base image, healthcheck)."""
    from .check_docker import check_file

    return check_file(file_path)


def run_check_ports(file_path: Path) -> list[CheckResult]:
    """Check port registration in PORTS.md."""
    from .check_ports import check_file

    return check_file(file_path)


def run_check_watchdog(file_path: Path) -> list[CheckResult]:
    """Check that services have watchdog scripts."""
    from .check_watchdog import check_file

    return check_file(file_path)


def run_check_plans(file_path: Path) -> list[CheckResult]:
    """Check plan document conventions (location + naming only)."""
    from .check_plans import check_file

    return check_file(file_path)


def run_all_checks(file_path: Path) -> list[CheckResult]:
    """Run all applicable checks for a file."""
    results: list[CheckResult] = []

    suffix = file_path.suffix.lower()
    name = file_path.name.lower()

    # Python files
    if suffix == ".py":
        results.extend(run_check_env_vars(file_path))
        results.extend(run_check_secrets(file_path))
        results.extend(run_check_health(file_path))
        # Check for docs on new modules
        if name == "__init__.py":
            from .check_docs import check_file as check_docs

            results.extend(check_docs(file_path))

    # TypeScript/JavaScript files
    if suffix in (".ts", ".tsx", ".js", ".jsx"):
        results.extend(run_check_env_vars(file_path))
        results.extend(run_check_secrets(file_path))

    # Docker files
    if name == "dockerfile" or suffix == ".dockerfile":
        results.extend(run_check_docker(file_path))
        results.extend(run_check_ports(file_path))  # Check EXPOSE ports

    # Compose files
    if name in ("compose.yaml", "compose.yml", "docker-compose.yaml", "docker-compose.yml"):
        results.extend(run_check_docker(file_path))
        results.extend(run_check_watchdog(file_path))

    # All files get port check if they contain port definitions
    if suffix in (".py", ".ts", ".tsx", ".js", ".yaml", ".yml"):
        results.extend(run_check_ports(file_path))

    # Markdown files - check plan conventions
    if suffix == ".md":
        results.extend(run_check_plans(file_path))
        # Check if tasks.md needs update when phase docs change
        if "phase" in name:
            from .check_tasks_updated import check_file as check_tasks

            results.extend(check_tasks(file_path))

    return results


def get_git_diff_files() -> list[str]:
    """Get list of files changed in git (staged, unstaged, AND untracked)."""
    files: set[str] = set()
    try:
        # Check unstaged changes (tracked files)
        unstaged = subprocess.run(
            ["git", "diff", "--name-only"], capture_output=True, text=True, check=True
        ).stdout.splitlines()
        files.update(unstaged)

        # Check staged changes
        staged = subprocess.run(
            ["git", "diff", "--staged", "--name-only"], capture_output=True, text=True, check=True
        ).stdout.splitlines()
        files.update(staged)

        # Check untracked files (NEW - fixes P0 bug)
        untracked = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.splitlines()
        files.update(untracked)

        return list(files)
    except subprocess.CalledProcessError:
        return []


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Fabrik Convention Validator")
    parser.add_argument("files", nargs="*", help="Files to check")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--strict", action="store_true", help="Treat warnings as errors")
    parser.add_argument("--git-diff", action="store_true", help="Check files changed in git")
    args = parser.parse_args()

    files_to_check = args.files

    if args.git_diff:
        git_files = get_git_diff_files()
        if git_files:
            files_to_check.extend(git_files)
        elif not files_to_check:
            # No files provided and no git diff - print warning but don't fail
            print("No changed files found to check.", file=sys.stderr)
            return 0

    # Deduplicate
    files_to_check = list(set(files_to_check))

    all_results: list[CheckResult] = []

    for file_arg in files_to_check:
        file_path = Path(file_arg)
        if file_path.exists() and file_path.is_file():
            all_results.extend(run_all_checks(file_path))

    # Determine exit code
    has_errors = any(r.severity == Severity.ERROR for r in all_results)
    has_warnings = any(r.severity == Severity.WARN for r in all_results)

    if args.strict and has_warnings:
        has_errors = True

    # Output results
    if args.json:
        output = {
            "results": [r.to_dict() for r in all_results],
            "summary": {
                "total": len(all_results),
                "errors": sum(1 for r in all_results if r.severity == Severity.ERROR),
                "warnings": sum(1 for r in all_results if r.severity == Severity.WARN),
            },
        }
        print(json.dumps(output, indent=2))
    else:
        for result in all_results:
            icon = {"pass": "✓", "warn": "⚠", "error": "✗"}[result.severity.value]
            location = (
                f"{result.file_path}:{result.line_number}"
                if result.line_number
                else result.file_path
            )
            print(f"{icon} [{result.check_name}] {location}: {result.message}")
            if result.fix_hint:
                print(f"  → Fix: {result.fix_hint}")

    if has_errors:
        return 2
    elif has_warnings:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
