#!/usr/bin/env python3
"""Fabrik Convention Validator - Orchestrates all convention checks.

Called by:
    - Windsurf Cascade hooks
    - Kilo CLI PostToolUse hooks
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

    def to_dict(self) -> dict[str, object]:
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


def run_check_env_contract(file_path: Path) -> list[CheckResult]:
    """Check ENV contract across .env.example, compose.yaml, CONFIGURATION.md."""
    from .check_env_contract import check_file

    return check_file(file_path)


def run_check_watchdog(file_path: Path) -> list[CheckResult]:
    """Check that services have watchdog scripts."""
    from .check_watchdog import check_file

    return check_file(file_path)


def run_check_plans(file_path: Path) -> list[CheckResult]:
    """Check plan document conventions (location + naming only)."""
    from .check_plans import check_file

    return check_file(file_path)


def run_check_plan_quality(file_path: Path) -> list[CheckResult]:
    """Check plan document quality (required sections + content)."""
    from .check_plan_quality import check_file

    return check_file(file_path)


def run_check_plan_tickets(file_path: Path) -> list[CheckResult]:
    """Check the spine+ticket plan-set contract (dir-level, deduped per run)."""
    from .check_plan_tickets import check_file

    return check_file(file_path)


def _as_warnings(results: list[CheckResult]) -> list[CheckResult]:
    """Downgrade a check's findings to WARNING (pending-activation gate, F1)."""
    out = []
    for r in results:
        if getattr(r, "severity", None) is Severity.ERROR:
            r = CheckResult(
                check_name=r.check_name,
                severity=Severity.WARNING,
                message=r.message,
                file_path=r.file_path,
                fix_hint=r.fix_hint,
            )
        out.append(r)
    return out


def run_check_doc_sprawl(file_path: Path) -> list[CheckResult]:
    """Check documentation anti-sprawl (prevent new files in protected dirs).

    SEVERITY IS DOWNGRADED TO WARNING until the doc-sprawl activation lands (review finding
    F1, 2026-08-15): making ``check_file`` non-vacuous silently turned this path into a HARD
    Tier-3 failure fleet-wide, while the check's own STATUS comment, its ``--warn`` default
    and the plan all documented it as reporting-only. Behaviour must match the contract that
    is written down; the ERROR severity returns with the deliberate, separately-reviewed
    activation, not as a side effect of a bug fix.
    """
    from .check_doc_sprawl import check_file

    return check_file(file_path)


def run_check_deps_sync(file_path: Path) -> list[CheckResult]:
    """Check dependency sync between pyproject.toml and requirements.txt."""
    from .check_deps_sync import check_file

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
        results.extend(run_check_env_contract(file_path))

    # .env.example and CONFIGURATION.md - ENV contract
    if name == ".env.example" or name == "CONFIGURATION.md":
        results.extend(run_check_env_contract(file_path))

    # All files get port check if they contain port definitions
    if suffix in (".py", ".ts", ".tsx", ".js", ".yaml", ".yml"):
        results.extend(run_check_ports(file_path))

    # Markdown files - check plan conventions and doc sprawl
    if suffix == ".md":
        results.extend(run_check_plans(file_path))
        results.extend(run_check_plan_quality(file_path))
        results.extend(run_check_plan_tickets(file_path))  # Spine+ticket plan-set contract
        results.extend(
            _as_warnings(run_check_doc_sprawl(file_path))  # Anti-sprawl (WARN until activation)
        )
        # Check if tasks.md needs update when phase docs change
        if "phase" in name:
            try:
                from .check_tasks_updated import check_file as check_tasks

                results.extend(check_tasks(file_path))
            except ImportError:
                pass  # check_tasks_updated.py not yet implemented

    # Requirements files - check dependency sync
    if name == "requirements.txt":
        results.extend(run_check_deps_sync(file_path))

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

    # Determine exit code. Compare by .value, NOT identity: run via `python -m`,
    # the package __init__ imports this module once and runpy re-imports it as
    # __main__, so CheckResults built by sibling checks (check_secrets/env_vars/…)
    # carry a DIFFERENT Severity enum instance than this __main__ copy. Identity
    # comparison silently reported has_errors=False — the validator exited 0
    # despite real violations. .value ("error"/"warn") is instance-agnostic.
    has_errors = any(r.severity.value == Severity.ERROR.value for r in all_results)

    # Plan-shape WARNs are DESIGNED advisories (the legacy-plan grandfather, the
    # DRAFT-spine sibling-session downgrade, the IN-PROGRESS sizing downgrade,
    # File-Scope orphan notes). Promoting them under --strict would turn every
    # deliberate downgrade back into a hard failure — exactly the sibling-session
    # red the downgrades exist to prevent — so --strict exempts these three checks.
    # (Round-10 disposition: this also keeps legacy-NAME WARNs advisory under
    # --strict — accepted: the pre-change gate was INERT on these paths (the
    # relative-path bug), so no functioning guard was removed.)
    _strict_exempt = ("plan_naming", "plan_quality", "plan_tickets")
    if args.strict and any(
        r.severity.value == Severity.WARN.value and r.check_name not in _strict_exempt
        for r in all_results
    ):
        has_errors = True

    # Output results
    if args.json:
        output = {
            "results": [r.to_dict() for r in all_results],
            "summary": {
                "total": len(all_results),
                "errors": sum(1 for r in all_results if r.severity.value == Severity.ERROR.value),
                "warnings": sum(1 for r in all_results if r.severity.value == Severity.WARN.value),
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
    # Warnings are non-blocking - return 0 so pre-commit passes
    # (warnings are still printed for visibility)
    return 0


if __name__ == "__main__":
    sys.exit(main())
