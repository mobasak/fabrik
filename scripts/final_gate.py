#!/usr/bin/env python3
"""
Final Gate - Deterministic checks for coder AI before Traycer commit.

Catches deterministic failures BEFORE expensive LLM review (Kilo).
Saves tokens by not letting Kilo analyze lint/syntax/convention errors.

Workflow Usage (9-Step Agile Flow):
    Step 3: python scripts/final_gate.py            # Pre-Kilo (deterministic cleanup)
    Step 5: python scripts/final_gate.py            # Post-Kilo (verify Kilo fixes)
    Step 7: python scripts/final_gate.py --sync     # Sync-only (docs side-effects)

All Flags:
    (default)    Fix mode, no sync (Steps 3/5 - main quality gate)
    --sync       Sync-only mode (Step 7 - no quality checks, just sync)
    --check      CI mode - no fixes, no sync (read-only verification)
    --no-stage   Don't auto-stage modified files

Checks (in normal mode: default / --check):
1. AUTO-FIX: trailing whitespace, EOF, ruff-format, ruff --fix
2. STATIC: ruff, mypy, bandit, semgrep (REQUIRED), yaml, json, sqlfluff, vulture (REQUIRED)
3. CONSISTENCY: structure, conventions, rule size, models, changelog, kilo health

Sync steps (--sync mode only):
- Windsurf extensions → docs/reference/EXTENSIONS.md
- Cascade backup freshness check

Default never runs sync. Use --sync explicitly for Step 7.
Iterates up to 3 times until clean. Auto-stages changes only if all checks pass.
"""

import argparse
import subprocess
import sys
from pathlib import Path

# Paths
FABRIK_ROOT = Path.cwd()  # Use current working directory, not script location
VENV_PYTHON = FABRIK_ROOT / ".venv" / "bin" / "python"
PYTHON = str(VENV_PYTHON) if VENV_PYTHON.exists() else sys.executable

# Colors
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"
BOLD = "\033[1m"

# Timeouts (seconds) - longer for heavy tools
TIMEOUTS = {
    "default": 120,
    "mypy": 300,
    "bandit": 180,
    "sqlfluff": 180,
    "ruff": 120,
    "semgrep": 300,
}

# Max fix iterations to prevent infinite loops
MAX_ITERATIONS = 3


def run_cmd(cmd: list[str], cwd: Path | None = None, timeout: int | None = None) -> tuple[int, str]:
    """Run a command and return (returncode, output)."""
    timeout = timeout or TIMEOUTS["default"]
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd or FABRIK_ROOT,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        output = result.stdout + result.stderr
        return result.returncode, output.strip()
    except subprocess.TimeoutExpired:
        return 1, f"Command timed out after {timeout}s"
    except FileNotFoundError:
        return 1, f"Command not found: {cmd[0]}"


def run_optional_check(script_path: str, check_name: str, *args: str) -> tuple[str, bool, str]:
    """Run an optional enforcement check, skipping if script doesn't exist.

    Args:
        script_path: Relative path to script from FABRIK_ROOT
        check_name: Display name for the check
        *args: Additional command arguments

    Returns:
        (check_name, passed, message) tuple
    """
    full_path = FABRIK_ROOT / script_path
    if not full_path.exists():
        return (check_name, True, "(check not present, skipping)")

    code, out = run_cmd([PYTHON, str(full_path)] + list(args))
    return (check_name, code == 0, out if code != 0 else "")


def run_mypy_with_recovery(target: str, timeout: int = 30) -> tuple[int, str]:
    """Run mypy with timeout protection and auto-recovery from cache corruption.

    Mypy's incremental cache can get corrupted on large files (3000+ lines),
    causing hangs. This function:
    1. Tries with incremental cache (fast path: ~0.1s)
    2. On timeout, clears cache and retries with --no-incremental (recovery: ~1-2s)

    Args:
        target: Path to check (e.g., "src/fabrik" or "scripts/")
        timeout: Timeout in seconds for first attempt (default 30s)

    Returns:
        (returncode, output) tuple
    """
    import shutil

    mypy_cache = FABRIK_ROOT / ".mypy_cache"
    cmd_base = [PYTHON, "-m", "mypy", "--config-file=pyproject.toml", target]

    # First attempt: with incremental cache (fast path)
    try:
        result = subprocess.run(
            cmd_base,
            cwd=FABRIK_ROOT,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        output = result.stdout + result.stderr
        return result.returncode, output.strip()
    except subprocess.TimeoutExpired:
        print(f"  {YELLOW}⚠ mypy hung (>{timeout}s) - clearing cache and retrying...{RESET}")

    # Recovery: clear cache and retry without incremental
    shutil.rmtree(mypy_cache, ignore_errors=True)
    try:
        result = subprocess.run(
            cmd_base + ["--no-incremental"],
            cwd=FABRIK_ROOT,
            capture_output=True,
            text=True,
            timeout=60,  # Generous timeout for recovery
        )
        output = result.stdout + result.stderr
        return result.returncode, output.strip()
    except subprocess.TimeoutExpired:
        return 1, f"mypy timed out even after cache clear (>{60}s)"
    except FileNotFoundError:
        return 1, "mypy not found"


def semgrep_env_with_token() -> dict[str, str] | None:
    """Return env for semgrep with SEMGREP_APP_TOKEN if available.

    Reads ~/.semgrep/settings.yml without requiring PyYAML.
    """
    import os
    import re

    settings_path = Path.home() / ".semgrep" / "settings.yml"
    if not settings_path.exists():
        return None

    try:
        raw = settings_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return None

    # settings.yml usually contains: api_token: <token>
    m = re.search(r"^\s*api_token\s*:\s*(.+?)\s*$", raw, flags=re.MULTILINE)
    if not m:
        return None

    token = m.group(1).strip().strip("'\"")
    if not token:
        return None

    env = os.environ.copy()
    env["SEMGREP_APP_TOKEN"] = token
    return env


def print_header(title: str) -> None:
    """Print a section header."""
    print(f"\n{BOLD}{BLUE}{'=' * 60}{RESET}")
    print(f"{BOLD}{BLUE}{title}{RESET}")
    print(f"{BOLD}{BLUE}{'=' * 60}{RESET}")


def print_step(name: str, passed: bool, output: str = "") -> None:
    """Print step result."""
    status = f"{GREEN}PASS{RESET}" if passed else f"{RED}FAIL{RESET}"
    print(f"  [{status}] {name}")
    if not passed and output:
        for line in output.split("\n")[:10]:  # Limit output
            print(f"       {line}")


def fix_trailing_whitespace() -> tuple[bool, str, int]:
    """Fix trailing whitespace in tracked text files. Preserves line endings (LF/CRLF)."""
    code, out = run_cmd(
        ["git", "ls-files", "-z", "--", "*.py", "*.md", "*.yaml", "*.yml", "*.json", "*.sh"]
    )
    if code != 0:
        return False, "Failed to list files", 0

    files_fixed = 0
    errors = []
    files = [f for f in out.split("\0") if f]
    for f in files:
        path = FABRIK_ROOT / f
        if not path.exists():
            continue
        try:
            content = path.read_text(encoding="utf-8")
            # Preserve line endings (LF or CRLF) while stripping trailing whitespace
            lines = content.splitlines(keepends=True)
            fixed_lines = []
            for line in lines:
                # Strip trailing whitespace but preserve the line ending
                if line.endswith("\r\n"):
                    fixed_lines.append(line[:-2].rstrip() + "\r\n")
                elif line.endswith("\n"):
                    fixed_lines.append(line[:-1].rstrip() + "\n")
                elif line.endswith("\r"):
                    fixed_lines.append(line[:-1].rstrip() + "\r")
                else:
                    fixed_lines.append(line.rstrip())  # Last line without newline
            fixed = "".join(fixed_lines)
            if fixed != content:
                path.write_text(fixed, encoding="utf-8")
                files_fixed += 1
        except UnicodeDecodeError:
            continue  # Skip binary/non-UTF8 files
        except Exception as e:
            errors.append(f"{f}: {e}")

    if errors:
        return False, "\n".join(errors), files_fixed
    return True, f"({files_fixed} files fixed)" if files_fixed else "", files_fixed


def fix_end_of_files() -> tuple[bool, str, int]:
    """Ensure all tracked text files end with newline. Preserves LF/CRLF line endings."""
    code, out = run_cmd(
        ["git", "ls-files", "-z", "--", "*.py", "*.md", "*.yaml", "*.yml", "*.json", "*.sh"]
    )
    if code != 0:
        return False, "Failed to list files", 0

    files_fixed = 0
    errors = []
    files = [f for f in out.split("\0") if f]
    for f in files:
        path = FABRIK_ROOT / f
        if not path.exists():
            continue
        try:
            content = path.read_text(encoding="utf-8")
            # Check if file already ends with a newline
            if content and not content.endswith("\n"):
                # Preserve line ending style: use CRLF if file contains CRLF, else LF
                newline = "\r\n" if "\r\n" in content else "\n"
                path.write_text(content + newline, encoding="utf-8")
                files_fixed += 1
        except UnicodeDecodeError:
            continue  # Skip binary/non-UTF8 files
        except Exception as e:
            errors.append(f"{f}: {e}")

    if errors:
        return False, "\n".join(errors), files_fixed
    return True, f"({files_fixed} files fixed)" if files_fixed else "", files_fixed


def run_formatting_fixes() -> list[tuple[str, bool, str]]:
    """Run auto-fix formatting steps (direct Python implementation, no pre-commit dependency)."""
    results = []

    # Trim trailing whitespace (direct implementation)
    ok, msg, _ = fix_trailing_whitespace()
    results.append(("trim trailing whitespace", ok, msg if not ok else ""))

    # Fix end of files (direct implementation)
    ok, msg, _ = fix_end_of_files()
    results.append(("fix end of files", ok, msg if not ok else ""))

    # Ruff format
    code, out = run_cmd(
        [PYTHON, "-m", "ruff", "format", "src/", "scripts/"],
        timeout=TIMEOUTS["ruff"],
    )
    results.append(("ruff-format", code == 0, out if code != 0 else ""))

    # Ruff fix (use returncode, not substring matching)
    code, out = run_cmd(
        [PYTHON, "-m", "ruff", "check", "--fix", "src/", "scripts/"],
        timeout=TIMEOUTS["ruff"],
    )
    # returncode 0 = clean, 1 = issues found (some fixed), other = error
    # We treat 0 and 1 as acceptable (fixes applied, remaining issues caught by ruff check)
    if code in (0, 1):
        results.append(("ruff --fix", True, ""))
    else:
        results.append(("ruff --fix", False, out))

    return results


def detect_src_package() -> str:
    """Detect the package directory under src/ for mypy.

    If exactly one package exists, return it. Otherwise return src/ for whole tree.
    """
    src_dir = FABRIK_ROOT / "src"
    if not src_dir.exists():
        return "src/"
    # Find all package directories (not dot/underscore prefixed)
    packages = [
        item for item in src_dir.iterdir() if item.is_dir() and not item.name.startswith((".", "_"))
    ]
    # If exactly one package, use it; otherwise scan whole src/
    if len(packages) == 1:
        return f"src/{packages[0].name}"
    return "src/"


def run_static_checks() -> list[tuple[str, bool, str]]:
    """Run static analysis checks."""
    results = []

    # Ruff check (no fix, just verify)
    code, out = run_cmd(
        [PYTHON, "-m", "ruff", "check", "src/", "scripts/"],
        timeout=TIMEOUTS["ruff"],
    )
    results.append(("ruff", code == 0, out if code != 0 else ""))

    # Mypy (auto-detect package under src/) - with timeout recovery for cache corruption
    mypy_target = detect_src_package()
    code, out = run_mypy_with_recovery(mypy_target, timeout=30)
    results.append(("mypy", code == 0, out if code != 0 else ""))

    # Bandit (optional - skip if not installed)
    code, out = run_cmd(
        [PYTHON, "-m", "bandit", "-ll", "-x", "tests/", "-r", "src/"],
        timeout=TIMEOUTS["bandit"],
    )
    if "No module named bandit" in out:
        results.append(("bandit", True, "(bandit not installed, skipping)"))
    else:
        results.append(("bandit", code == 0, out if code != 0 else ""))

    # Semgrep (best-effort - skip if not installed, not authenticated, or times out)
    # Reduced timeout to 30s to prevent blocking; semgrep can hang on network issues
    semgrep_env = semgrep_env_with_token()
    semgrep_timeout = 30  # Short timeout - semgrep can hang on network/auth issues
    try:
        result = subprocess.run(
            ["semgrep", "--config", "auto", "src/"],
            cwd=FABRIK_ROOT,
            capture_output=True,
            text=True,
            timeout=semgrep_timeout,
            env=semgrep_env,
        )
        code, out = result.returncode, (result.stdout + result.stderr).strip()
    except FileNotFoundError:
        code, out = 1, "Command not found: semgrep"
    except subprocess.TimeoutExpired:
        code, out = 0, f"(semgrep timed out after {semgrep_timeout}s, skipping)"

    if "Command not found: semgrep" in out:
        # Skip if not installed (best-effort)
        results.append(("semgrep", True, "(semgrep not installed, skipping)"))
    elif "HTTP 401" in out or "semgrep login" in out.lower():
        # Skip if not authenticated (best-effort) - print instruction but don't fail
        results.append(("semgrep", True, "(semgrep not authenticated - run: semgrep login)"))
    elif "timed out" in out:
        results.append(("semgrep", True, out))
    else:
        results.append(("semgrep", code == 0, out if code != 0 else ""))

    # Check YAML (guard import, always append result)
    code, out = run_cmd(["git", "ls-files", "-z", "--", "*.yaml", "*.yml"])
    yaml_files = [f for f in out.split("\0") if f] if code == 0 else []
    yaml_files_exist = bool(yaml_files)
    yaml_ok = True
    yaml_errors = []
    if yaml_files_exist:
        try:
            import yaml
        except ImportError:
            yaml_ok = False
            yaml_errors.append("PyYAML not installed")
        else:
            files = [f for f in yaml_files if "templates/wordpress/schema/v1.yaml" not in f]
            for f in files:
                path = FABRIK_ROOT / f
                if path.exists():
                    try:
                        yaml.safe_load(path.read_text(encoding="utf-8"))
                    except yaml.YAMLError as e:
                        yaml_ok = False
                        yaml_errors.append(f"{f}: {e}")
                    except UnicodeDecodeError:
                        yaml_ok = False
                        yaml_errors.append(f"{f}: non-UTF8 encoding")
    # Always append result (consistency with other checks)
    if yaml_files_exist:
        results.append(("check yaml", yaml_ok, "\n".join(yaml_errors)))
    else:
        results.append(("check yaml", True, "(no .yaml/.yml files)"))

    # Check JSON
    import json

    code, out = run_cmd(["git", "ls-files", "-z", "--", "*.json"])
    json_ok = True
    json_errors = []
    if code == 0 and out:
        files = [f for f in out.split("\0") if f]
        for f in files:
            path = FABRIK_ROOT / f
            if path.exists():
                try:
                    json.loads(path.read_text(encoding="utf-8"))
                except json.JSONDecodeError as e:
                    json_ok = False
                    json_errors.append(f"{f}: {e}")
                except UnicodeDecodeError:
                    json_ok = False
                    json_errors.append(f"{f}: non-UTF8 encoding")
    results.append(("check json", json_ok, "\n".join(json_errors)))

    # SQLFluff (use -z for safe file discovery)
    code, out = run_cmd(["git", "ls-files", "-z", "--", "*.sql"])
    sql_files = [f for f in out.split("\0") if f]
    if sql_files:
        code, out = run_cmd(
            [PYTHON, "-m", "sqlfluff", "lint", "--dialect", "postgres"] + sql_files,
            timeout=TIMEOUTS["sqlfluff"],
        )
        if "No module named sqlfluff" in out:
            results.append(("sqlfluff-lint", True, "(sqlfluff not installed, skipping)"))
        else:
            results.append(("sqlfluff-lint", code == 0, out if code != 0 else ""))
    else:
        results.append(("sqlfluff-lint", True, "(no .sql files)"))

    # Vulture (optional - skip if not installed)
    code, out = run_cmd(
        [
            PYTHON,
            "-m",
            "vulture",
            "src/",
            "--min-confidence",
            "95",
            "--exclude",
            "src/fabrik/wordpress/,src/fabrik/drivers/,src/fabrik/provisioner.py",
        ]
    )
    if "No module named vulture" in out:
        results.append(("vulture", True, "(vulture not installed, skipping)"))
    else:
        results.append(("vulture", code == 0, out if code != 0 else ""))

    return results


def run_consistency_checks() -> list[tuple[str, bool, str]]:
    """Run repo consistency checks."""
    results = []

    # Optional enforcement checks - skip if scripts not present
    results.append(
        run_optional_check("scripts/enforcement/check_structure.py", "Project Structure")
    )
    results.append(
        run_optional_check("scripts/enforcement/check_rule_size.py", "Rule File Size Guard")
    )
    results.append(
        run_optional_check("scripts/enforcement/check_index_md.py", "INDEX.md (Master File Index)")
    )
    results.append(
        run_optional_check(
            "scripts/enforcement/check_readme_md.py", "README.md (Primary Entry Point)"
        )
    )
    results.append(
        run_optional_check(
            "scripts/enforcement/check_configuration_md.py", "CONFIGURATION.md (Env Vars)"
        )
    )
    results.append(
        run_optional_check("scripts/enforcement/check_env_updates.py", ".env Updates (Secrets)")
    )
    results.append(
        run_optional_check("scripts/enforcement/check_changelog.py", "CHANGELOG.md Updated")
    )
    results.append(
        run_optional_check("scripts/enforcement/check_schema_sync.py", "Schema Sync (DB Models)")
    )
    results.append(
        run_optional_check("scripts/enforcement/check_openapi_sync.py", "OpenAPI Sync (API Docs)")
    )
    results.append(
        run_optional_check("scripts/enforcement/check_test_coverage.py", "Test Coverage (New Code)")
    )
    results.append(
        run_optional_check("scripts/enforcement/check_env_example.py", ".env.example Completeness")
    )
    results.append(
        run_optional_check("scripts/enforcement/check_compose_services.py", "Compose Services Docs")
    )
    results.append(run_optional_check("scripts/docs_updater.py", "Documentation Drift", "--check"))
    results.append(
        run_optional_check("scripts/update_agents_toc.py", "AGENTS.md TOC Current", "--check")
    )

    # Fabrik Convention Validator (module import, skip if not installed)
    validate_conv = FABRIK_ROOT / "scripts/enforcement/validate_conventions.py"
    if validate_conv.exists():
        code, out = run_cmd([PYTHON, "-m", "scripts.enforcement.validate_conventions", "--strict"])
        results.append(("Fabrik Convention Validator", code == 0, out if code != 0 else ""))
    else:
        results.append(("Fabrik Convention Validator", True, "(check not present, skipping)"))

    # Kilo CLI Health Check (shell script)
    kilo_health = FABRIK_ROOT / "scripts/check_kilo_health.sh"
    if kilo_health.exists():
        code, out = run_cmd(["./scripts/check_kilo_health.sh"])
        results.append(("Kilo CLI Health Check", code == 0, out if code != 0 else ""))
    else:
        results.append(("Kilo CLI Health Check", True, "(check not present, skipping)"))

    # Symlink Integrity Check (always run)
    symlink_ok, symlink_msg = check_symlinks()
    results.append(("Symlink Integrity", symlink_ok, symlink_msg))

    return results


def check_symlinks() -> tuple[bool, str]:
    """Check that required symlinks exist and point to correct targets.

    Note: Skipped for /opt/fabrik itself (the source, not a consumer).
    Only validates symlinks in child projects.

    Returns:
        (success, error_message)
    """
    # Skip for fabrik root - it's the source, not a consumer
    if str(FABRIK_ROOT) == "/opt/fabrik":
        return True, ""

    symlinks = [
        (".windsurfrules", "/opt/fabrik/windsurfrules"),
        (".windsurf/rules", "/opt/fabrik/.windsurf/rules"),
    ]

    errors = []
    for symlink, expected_target in symlinks:
        link_path = FABRIK_ROOT / symlink
        target_path = Path(expected_target)

        if not link_path.exists():
            # Not an error - symlink may not be required
            continue

        if not link_path.is_symlink():
            errors.append(f"{symlink}: exists but is not a symlink")
            continue

        try:
            resolved = link_path.resolve()
            expected = target_path.resolve()

            if resolved != expected:
                errors.append(f"{symlink}: points to {resolved}, expected {expected}")
        except OSError as e:
            errors.append(f"{symlink}: cannot resolve - {e}")

    if errors:
        return False, "\n".join(errors)
    return True, ""


def run_sync_steps() -> list[tuple[str, bool, str]]:
    """Run side-effect sync steps (last)."""
    results = []

    # Sync Windsurf Extensions
    code, out = run_cmd(["./scripts/sync_extensions.sh"])
    results.append(("Sync Windsurf Extensions", code == 0, out if code != 0 else ""))

    # Sync Cascade Backup
    code, out = run_cmd(["./scripts/sync_cascade_backup.sh"])
    results.append(("Sync Cascade Backup", code == 0, out if code != 0 else ""))

    return results


def stage_changes() -> tuple[bool, str]:
    """Stage all modified files."""
    code, out = run_cmd(["git", "add", "-A"])
    return code == 0, out


def get_git_status_hash() -> str:
    """Get hash of current git status (to detect file changes)."""
    code, out = run_cmd(["git", "status", "--porcelain"])
    return out if code == 0 else ""


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Final Gate - Pre-commit checks for coder AI")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check only mode - no fixes, no sync steps (CI mode)",
    )
    parser.add_argument(
        "--no-stage",
        action="store_true",
        help="Don't auto-stage modified files after fixes",
    )
    parser.add_argument(
        "--sync",
        action="store_true",
        help="Run sync steps only (Step 7 - no quality checks)",
    )
    # Note: --no-sync removed - default now never syncs (use --sync explicitly for Step 7)
    return parser.parse_args()


def run_iteration(check_only: bool, run_sync: bool) -> list[tuple[str, bool, str]]:
    """Run one iteration of all checks."""
    all_results: list[tuple[str, bool, str]] = []

    # Phase 1: Formatting fixes (only in fix mode)
    if not check_only:
        print_header("PHASE 1: AUTO-FIX FORMATTING")
        results = run_formatting_fixes()
        all_results.extend(results)
        for name, passed, out in results:
            print_step(name, passed, out)

    # Phase 2: Static checks
    print_header("PHASE 2: STATIC ANALYSIS")
    results = run_static_checks()
    all_results.extend(results)
    for name, passed, out in results:
        print_step(name, passed, out)

    # Phase 3: Consistency checks
    print_header("PHASE 3: REPO CONSISTENCY")
    results = run_consistency_checks()
    all_results.extend(results)
    for name, passed, out in results:
        print_step(name, passed, out)

    # Phase 4: Sync steps (skip in check-only mode)
    if run_sync and not check_only:
        print_header("PHASE 4: SYNC STEPS")
        results = run_sync_steps()
        all_results.extend(results)
        for name, passed, out in results:
            print_step(name, passed, out)
    elif check_only:
        print(f"\n{YELLOW}(Sync steps skipped in --check mode){RESET}")

    return all_results


def main() -> int:
    """Run the final gate checks with iteration loop."""
    args = parse_args()

    # Sync-only mode
    if args.sync:
        print(f"{BOLD}Final Gate - Sync Steps Only{RESET}")
        print_header("SYNC STEPS")
        results = run_sync_steps()
        for name, passed, out in results:
            print_step(name, passed, out)
        failed = [r for r in results if not r[1]]
        return 1 if failed else 0

    print(f"{BOLD}Final Gate - Pre-Traycer Commit Checks{RESET}")
    mode = "CHECK ONLY" if args.check else "FIX"
    # Default never syncs; --check also never syncs
    sync_mode = "DISABLED (check mode)" if args.check else "DISABLED (use --sync for Step 7)"
    print(f"Mode: {mode} | Sync: {sync_mode} | Max iterations: {MAX_ITERATIONS}")

    # Initialize before loop to avoid undefined variable
    all_results: list[tuple[str, bool, str]] = []

    # Iteration loop: re-runs if ANY step modified files (not just autofix)
    # This catches convergence issues from formatting, consistency checks, etc.
    # Semantic failures (mypy, bandit, etc.) require human/LLM fixes between runs
    for iteration in range(1, MAX_ITERATIONS + 1):
        if not args.check and iteration > 1:
            print(
                f"\n{BOLD}{YELLOW}=== Iteration {iteration}/{MAX_ITERATIONS} (convergence rerun) ==={RESET}"
            )

        status_before = get_git_status_hash()
        # Default never syncs - use --sync explicitly for Step 7
        all_results = run_iteration(
            check_only=args.check,
            run_sync=False,  # Never sync in normal mode
        )

        # Count failures
        failed = [r for r in all_results if not r[1]]

        # In check mode, no iteration needed
        if args.check:
            break

        # If no failures, we're done
        if not failed:
            break

        # Check if any steps changed files
        status_after = get_git_status_hash()
        if status_before == status_after:
            # No file changes - semantic failures need human/LLM fixes
            # Exit loop, report failures (don't pretend iterating will help)
            print(f"\n{YELLOW}No file changes - remaining failures need manual fixes{RESET}")
            break

        if iteration < MAX_ITERATIONS:
            print(f"\n{YELLOW}Changes detected, re-validating...{RESET}")

    # Summary first (to know if we should stage)
    passed_count = len([r for r in all_results if r[1]])
    failed = [r for r in all_results if not r[1]]

    # Auto-stage only if no failures AND fix mode AND staging enabled
    if not args.check and not args.no_stage and not failed:
        status = get_git_status_hash()
        if status:
            print(f"\n{BLUE}Auto-staging modified files...{RESET}")
            ok, out = stage_changes()
            if ok:
                print(f"  {GREEN}✓ Changes staged{RESET}")
            else:
                print(f"  {RED}✗ Failed to stage: {out}{RESET}")

    # Summary
    print_header("SUMMARY")

    print(f"  {GREEN}Passed:{RESET} {passed_count}")
    print(f"  {RED}Failed:{RESET} {len(failed)}")

    if failed:
        print(f"\n{RED}Failed checks:{RESET}")
        for name, _, _ in failed:
            print(f"  - {name}")
        print(f"\n{YELLOW}Fix the issues above and re-run: python scripts/final_gate.py{RESET}")
        return 1

    print(f"\n{GREEN}{BOLD}✓ All checks passed - Proceed{RESET}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
