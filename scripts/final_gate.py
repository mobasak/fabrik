#!/usr/bin/env python3
"""
Final Gate - Deterministic checks for coder AI before Traycer commit.

Catches deterministic failures BEFORE expensive LLM review (Kilo).
Saves tokens by not letting Kilo analyze lint/syntax/convention errors.

Usage:
    python scripts/final_gate.py              # Fix mode (default)
    python scripts/final_gate.py --lean       # Tier 1: Showstoppers only
    python scripts/final_gate.py --systemic   # Tier 3: Repo health only
    python scripts/final_gate.py --check      # CI mode - no fixes
    python scripts/final_gate.py --json       # JSON output for agents

Flags:
    --lean       Tier 1: Showstoppers only (syntax, secrets, schema sync)
    --systemic   Tier 3: Repo health only (docker, ports, docs sprawl, deps)
    --check      Check only mode - no fixes, no sync (CI mode)
    --json       Output results as JSON for agent parsing
    --no-stage   Don't auto-stage modified files after fixes
    --sync       Sync-only mode (manual utility - no quality checks)
    --post-kilo  Log issues to .droid/gate_issues.jsonl

Checks:
1. AUTO-FIX: trailing whitespace, EOF, ruff-format, ruff --fix
2. STATIC: ruff, mypy, bandit, semgrep, yaml, json, sqlfluff, vulture
3. CONSISTENCY: structure, conventions, rule size, models, changelog, kilo health

Iterates up to 3 times until clean. Auto-stages changes only if all checks pass.

Workflow Doc: docs/workflows/FINAL_GATE_WORKFLOW.md
  ⚠️  Update the workflow doc when modifying this script.
"""

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

# Paths
PROJECT_ROOT = Path.cwd()  # Use current working directory, not script location
VENV_PYTHON = PROJECT_ROOT / ".venv" / "bin" / "python"
VENV_RUFF = PROJECT_ROOT / ".venv" / "bin" / "ruff"
# Use venv python only if it has the required tools (ruff) installed
PYTHON = str(VENV_PYTHON) if (VENV_PYTHON.exists() and VENV_RUFF.exists()) else sys.executable

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

# AI fix agent (enabled via FINAL_GATE_AI_FIX=1)
CHEAP_FIX_AGENT = Path(__file__).parent / "cheap_fix_agent.py"


def run_ai_fixes(tool: str, tool_output: str | None = None) -> tuple[bool, str]:
    """Run cheap_fix_agent to fix issues from a tool (mypy/ruff).

    Args:
        tool: "mypy" or "ruff"
        tool_output: Pre-captured output (avoids re-running tool)

    Returns (success, message).
    """
    if not CHEAP_FIX_AGENT.exists():
        return False, f"cheap_fix_agent.py not found at {CHEAP_FIX_AGENT}"

    # Build command with optional --output flag
    cmd = [sys.executable, str(CHEAP_FIX_AGENT), "fix-from-output", "--tool", tool]

    # Pass tool output via environment variable (avoids re-running tool)
    env = os.environ.copy()
    env["PROJECT_ROOT"] = str(PROJECT_ROOT)
    if tool_output:
        env["TOOL_OUTPUT"] = tool_output

    try:
        result = subprocess.run(
            cmd,
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=120,
            env=env,
        )
        output = (result.stdout + result.stderr).strip()
        return result.returncode == 0, output
    except subprocess.TimeoutExpired:
        return False, "AI fix timed out"
    except Exception as e:
        return False, str(e)


def run_cmd(cmd: list[str], cwd: Path | None = None, timeout: int | None = None) -> tuple[int, str]:
    """Run a command and return (returncode, output)."""
    timeout = timeout or TIMEOUTS["default"]
    # Pass PROJECT_ROOT to enforcement scripts so they know the correct project root
    env = os.environ.copy()
    env["PROJECT_ROOT"] = str(PROJECT_ROOT)
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd or PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
        output = result.stdout + result.stderr
        return result.returncode, output.strip()
    except subprocess.TimeoutExpired:
        return 1, f"Command timed out after {timeout}s"
    except FileNotFoundError:
        return 1, f"Command not found: {cmd[0]}"


def run_optional_check(
    script_path: str,
    check_name: str,
    *args: str,
    module: str | None = None,
    advisory: bool = False,
) -> tuple[str, bool, str]:
    """Run an optional enforcement check, skipping if script doesn't exist.

    Args:
        script_path: Relative path to script from PROJECT_ROOT
        check_name: Display name for the check
        *args: Additional command arguments
        module: If provided, run as 'python -m <module>' instead of direct script
        advisory: If True, preserve stdout even on exit 0 (for warning-level checks)

    Returns:
        (check_name, passed, message) tuple
    """
    full_path = PROJECT_ROOT / script_path
    if not full_path.exists():
        return (check_name, True, "(check not present, skipping)")

    if module:
        code, out = run_cmd([PYTHON, "-m", module] + list(args))
    else:
        code, out = run_cmd([PYTHON, str(full_path)] + list(args))
    if code != 0:
        return (check_name, False, out)
    # Advisory checks: preserve stdout (warnings) even on success
    return (check_name, True, out.strip() if advisory else "")


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

    mypy_cache = PROJECT_ROOT / ".mypy_cache"
    cmd_base = [PYTHON, "-m", "mypy", "--config-file=pyproject.toml", target]

    # First attempt: with incremental cache (fast path)
    try:
        result = subprocess.run(
            cmd_base,
            cwd=PROJECT_ROOT,
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
            cwd=PROJECT_ROOT,
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
    elif passed and output and output != "(check not present, skipping)":
        # Advisory output (warnings from non-blocking checks)
        for line in output.split("\n")[:10]:
            print(f"       {YELLOW}{line}{RESET}")


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
        path = PROJECT_ROOT / f
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
        path = PROJECT_ROOT / f
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


def run_formatting_fixes(tier: int = 2) -> list[tuple[str, bool, str]]:
    """Run auto-fix formatting steps (direct Python implementation, no pre-commit dependency)."""
    # Tier 3 (systemic): Skip formatting - systemic checks don't auto-fix
    if tier == 3:
        return []

    results = []

    # Trim trailing whitespace (direct implementation)
    ok, msg, _ = fix_trailing_whitespace()
    results.append(("trim trailing whitespace", ok, msg if not ok else ""))

    # Fix end of files (direct implementation)
    ok, msg, _ = fix_end_of_files()
    results.append(("fix end of files", ok, msg if not ok else ""))

    # Ruff format (skip src/ if not present for non-Python projects)
    ruff_targets = ["scripts/"]
    if (PROJECT_ROOT / "src").exists():
        ruff_targets.append("src/")
    code, out = run_cmd(
        [PYTHON, "-m", "ruff", "format"] + ruff_targets,
        timeout=TIMEOUTS["ruff"],
    )
    results.append(("ruff-format", code == 0, out if code != 0 else ""))

    # Ruff fix (use returncode, not substring matching)
    ruff_targets = ["scripts/"]
    if (PROJECT_ROOT / "src").exists():
        ruff_targets.append("src/")
    code, out = run_cmd(
        [PYTHON, "-m", "ruff", "check", "--fix"] + ruff_targets,
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
    src_dir = PROJECT_ROOT / "src"
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


def run_static_checks(
    tier: int = 2, changed_files: set[str] | None = None
) -> list[tuple[str, bool, str]]:
    """Run static analysis checks, filtered by tier and changed files."""
    results = []
    changed = changed_files or set()

    # Tier 3: Skip all static checks (systemic only runs consistency)
    if tier == 3:
        return results

    # Diff-sensing: if only .md files changed, skip all static checks
    if changed and _only_md_changed(changed):
        return results

    # --- Ruff check (Tier 1 + Tier 2) ---
    ruff_targets = ["scripts/"]
    if (PROJECT_ROOT / "src").exists():
        ruff_targets.append("src/")
    code, out = run_cmd(
        [PYTHON, "-m", "ruff", "check"] + ruff_targets,
        timeout=TIMEOUTS["ruff"],
    )
    results.append(("ruff", code == 0, out if code != 0 else ""))

    # --- JSON validation (Tier 1 + Tier 2) ---
    import json

    code, out = run_cmd(["git", "ls-files", "-z", "--", "*.json"])
    json_ok = True
    json_errors = []
    if code == 0 and out:
        files = [f for f in out.split("\0") if f]
        for f in files:
            path = PROJECT_ROOT / f
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

    # --- YAML validation (Tier 1 + Tier 2) ---
    code, out = run_cmd(["git", "ls-files", "-z", "--", "*.yaml", "*.yml"])
    yaml_files = [f for f in out.split("\0") if f] if code == 0 else []
    yaml_ok = True
    yaml_errors = []
    if yaml_files:
        try:
            import yaml
        except ImportError:
            yaml_ok = False
            yaml_errors.append("PyYAML not installed")
        else:
            files = [f for f in yaml_files if "templates/wordpress/schema/v1.yaml" not in f]
            for f in files:
                path = PROJECT_ROOT / f
                if path.exists():
                    try:
                        yaml.safe_load(path.read_text(encoding="utf-8"))
                    except yaml.YAMLError as e:
                        yaml_ok = False
                        yaml_errors.append(f"{f}: {e}")
                    except UnicodeDecodeError:
                        yaml_ok = False
                        yaml_errors.append(f"{f}: non-UTF8 encoding")
        results.append(("check yaml", yaml_ok, "\n".join(yaml_errors)))
    else:
        results.append(("check yaml", True, "(no .yaml/.yml files)"))

    # --- Everything below is Tier 2 only ---
    if tier == 1:
        return results

    # Mypy (skip if pyproject.toml doesn't exist for non-Python projects)
    if (PROJECT_ROOT / "pyproject.toml").exists():
        mypy_target = detect_src_package()
        code, out = run_mypy_with_recovery(mypy_target, timeout=30)
        results.append(("mypy", code == 0, out if code != 0 else ""))
    else:
        results.append(("mypy", True, "(no pyproject.toml, skipping)"))

    # Bandit (skip if no src/ files changed)
    if not changed or _has_path_prefix(changed, "src/"):
        code, out = run_cmd(
            [PYTHON, "-m", "bandit", "-ll", "-x", "tests/", "-r", "src/"],
            timeout=TIMEOUTS["bandit"],
        )
        if "No module named bandit" in out:
            results.append(("bandit", True, "(bandit not installed, skipping)"))
        else:
            results.append(("bandit", code == 0, out if code != 0 else ""))
    else:
        results.append(("bandit", True, "(no src/ changes, skipping)"))

    # Semgrep (skip if no src/ files changed)
    if not changed or _has_path_prefix(changed, "src/"):
        semgrep_env = semgrep_env_with_token()
        semgrep_timeout = 30
        try:
            result = subprocess.run(
                ["semgrep", "--config", "auto", "src/"],
                cwd=PROJECT_ROOT,
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
            results.append(("semgrep", True, "(semgrep not installed, skipping)"))
        elif "HTTP 401" in out or "semgrep login" in out.lower():
            results.append(("semgrep", True, "(semgrep not authenticated - run: semgrep login)"))
        elif "timed out" in out:
            results.append(("semgrep", True, out))
        else:
            results.append(("semgrep", code == 0, out if code != 0 else ""))
    else:
        results.append(("semgrep", True, "(no src/ changes, skipping)"))

    # SQLFluff (skip if no .sql files changed)
    if not changed or _has_extension(changed, ".sql"):
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
    else:
        results.append(("sqlfluff-lint", True, "(no .sql changes, skipping)"))

    # Vulture
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


def run_consistency_checks(
    tier: int = 2, changed_files: set[str] | None = None
) -> list[tuple[str, bool, str]]:
    """Run repo consistency checks, filtered by tier and changed files."""
    results = []
    changed = changed_files or set()

    # ── Tier 1: Showstoppers only ──
    # Applied for Tier 1 and Tier 2. Tier 3 is systemic-only and skips these.
    if tier in (1, 2):
        results.append(
            run_optional_check("scripts/enforcement/check_secrets.py", "Secrets (Zero Hardcoding)")
        )
        results.append(
            run_optional_check("scripts/enforcement/check_env_vars.py", ".env Updates (Secrets)")
        )
        # Schema sync only if models or .sql changed
        if not changed or _has_extension(changed, ".py", ".sql"):
            results.append(
                run_optional_check(
                    "scripts/enforcement/check_schema_sync.py", "Schema Sync (DB Models)"
                )
            )
        # Changelog enforcement - prevents agents from forgetting across tasks 1-9
        results.append(
            run_optional_check("scripts/enforcement/check_changelog.py", "CHANGELOG.md Updated")
        )
        # Print/console.log ban in production code
        results.append(
            run_optional_check("scripts/enforcement/check_print_ban.py", "Print/Console.log Ban")
        )
        # Host-port ban for Traefik-routed compose templates (Phase 4l §5).
        # Scans templates/**/compose.yaml.j2 every run (fast — ~13 small files).
        # The check is stateless w.r.t. staged files: any template with a
        # Traefik router + host-bound ports: fails the gate regardless of
        # what changed in this commit, because it's a repo-invariant guard.
        results.append(
            run_optional_check(
                "scripts/enforcement/check_no_host_ports.py",
                "No Host Ports on Traefik Services",
            )
        )
        # Full Traefik label-set enforcement (Phase 4l §7). Every service
        # with traefik.enable=true in any templates/**/compose.yaml.j2 MUST
        # declare the full five-label set (rule, entrypoints, tls=true,
        # tls.certresolver, loadbalancer.server.port). Relying on Coolify's
        # runtime auto-inject has silently broken admin-dashboard 2FA in
        # production — see docs/LESSONS_LEARNT.md §8.7 (GlitchTip incident).
        results.append(
            run_optional_check(
                "scripts/enforcement/check_traefik_labels.py",
                "Full Traefik Label Set (§7)",
            )
        )

    # Tier 1 stops here
    if tier == 1:
        return results

    # ── Tier 2: Essential subset ──
    if tier == 2:
        results.append(
            run_optional_check("scripts/enforcement/check_structure.py", "Project Structure")
        )
        results.append(
            run_optional_check("scripts/enforcement/check_rule_size.py", "Rule File Size Guard")
        )
        results.append(
            run_optional_check(
                "scripts/enforcement/check_opencode_json.py", "opencode.json (Kilo-Safe Rules)"
            )
        )
        results.append(
            run_optional_check(
                "scripts/enforcement/check_index_md.py", "INDEX.md (Master File Index)"
            )
        )
        results.append(
            run_optional_check(
                "scripts/enforcement/check_test_proposal.py", "One-Test Rule Proposal"
            )
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
            run_optional_check(
                "scripts/enforcement/check_openapi_sync.py", "OpenAPI Sync (API Docs)"
            )
        )
        results.append(
            run_optional_check(
                "scripts/enforcement/check_test_coverage.py", "Test Coverage (New Code)"
            )
        )
        results.append(
            run_optional_check(
                "scripts/enforcement/check_env_example.py", ".env.example Completeness"
            )
        )
        results.append(
            run_optional_check(
                "scripts/enforcement/check_compose_services.py", "Compose Services Docs"
            )
        )
        results.append(
            run_optional_check("scripts/enforcement/check_user_guide.py", "User Guide Presence")
        )
        results.append(
            run_optional_check(
                "scripts/enforcement/check_reusable_modules.py",
                "Reusable Module Tagging",
                advisory=True,
            )
        )

    # ── Tier 3: Full repo health (systemic-only) ──
    if tier == 3:
        # Systemic / infra-focused checks only. Showstoppers (secrets, schema sync, etc.)
        # are handled in Tier 1 / Tier 2 and are not repeated here.
        results.append(
            run_optional_check(
                "scripts/enforcement/check_docker.py",
                "Docker (amd64, No-Alpine, HEALTHCHECK)",
            )
        )
        results.append(
            run_optional_check(
                "scripts/enforcement/check_ports.py",
                "Port Registration (PORTS.md)",
            )
        )
        results.append(
            run_optional_check(
                "scripts/enforcement/check_env_contract.py",
                ".env Contract Sync",
                module="scripts.enforcement.check_env_contract",
            )
        )
        results.append(
            run_optional_check(
                "scripts/enforcement/check_deps_sync.py",
                "Dependencies Sync",
                module="scripts.enforcement.check_deps_sync",
            )
        )
        results.append(
            run_optional_check(
                "scripts/enforcement/check_docs.py",
                "Documentation Completeness",
                module="scripts.enforcement.check_docs",
            )
        )
        results.append(
            run_optional_check(
                "scripts/enforcement/check_doc_sprawl.py",
                "Documentation Sprawl",
            )
        )
        results.append(
            run_optional_check(
                "scripts/enforcement/check_watchdog.py",
                "Watchdog Scripts",
            )
        )
        results.append(
            run_optional_check(
                "scripts/enforcement/check_health.py",
                "Health Endpoint Validation",
            )
        )
        results.append(
            run_optional_check(
                "scripts/enforcement/check_duplicates.py",
                "Duplicate Detection",
            )
        )
        results.append(
            run_optional_check("scripts/docs_updater.py", "Documentation Drift", "--check")
        )
        validate_conv = PROJECT_ROOT / "scripts/enforcement/validate_conventions.py"
        if validate_conv.exists():
            code, out = run_cmd(
                [PYTHON, "-m", "scripts.enforcement.validate_conventions", "--strict"]
            )
            results.append(("Fabrik Convention Validator", code == 0, out if code != 0 else ""))
        else:
            results.append(("Fabrik Convention Validator", True, "(check not present, skipping)"))

    # Kilo CLI Health Check (all tiers that reach here)
    if tier >= 2:
        kilo_health = PROJECT_ROOT / "scripts/check_kilo_health.sh"
        if kilo_health.exists():
            code, out = run_cmd(["./scripts/check_kilo_health.sh"])
            results.append(("Kilo CLI Health Check", code == 0, out if code != 0 else ""))
        else:
            results.append(("Kilo CLI Health Check", True, "(check not present, skipping)"))

    return results


def check_symlinks() -> tuple[bool, str]:
    """Validate governance files are local copies, not symlinks.

    Checks that critical governance artifacts (AGENTS.md, AGENTS-compact.md,
    opencode.json, .windsurfrules, .windsurf/rules/, .windsurf/workflows/)
    are copied files, not symlinks. This enforces workspace isolation for
    AI coding agents.

    Self-exemption: When running inside /opt/fabrik itself, check is skipped.

    Governance files checked:
    - AGENTS.md
    - AGENTS-compact.md
    - opencode.json
    - .windsurfrules
    - .windsurf/rules/ (directory, checked recursively)
    - .windsurf/workflows/ (directory, checked recursively)

    Returns:
        tuple: (is_valid, error_message)
            - (True, "") if all files are local copies or source repo
            - (False, "<failures>") with per-file failure messages
    """
    fabrik_master = Path("/opt/fabrik")

    # Self-exemption: skip check when running inside /opt/fabrik itself
    if PROJECT_ROOT.resolve() == fabrik_master.resolve():
        return True, "(source repo — isolation check skipped)"

    # Governance files to validate
    governance_files = [
        "AGENTS.md",
        "AGENTS-compact.md",
        "opencode.json",
        ".windsurfrules",
        ".windsurf/rules",
        ".windsurf/workflows",
    ]

    failures = []

    def is_under_fabrik(target_path: Path) -> bool:
        """Path-aware check if target is under /opt/fabrik."""
        try:
            target_path.resolve().relative_to(fabrik_master.resolve())
            return True
        except ValueError:
            return False

    for rel_path in governance_files:
        path = PROJECT_ROOT / rel_path

        # Check 1: File/directory exists
        if not path.exists():
            failures.append(f"{rel_path}: missing (governance file not found)")
            continue

        # Check 2: Is it a symlink? (FAIL on ANY symlink)
        if path.is_symlink():
            resolved = path.resolve()
            if is_under_fabrik(resolved):
                failures.append(
                    f"{rel_path}: symlink → {resolved} (points to /opt/fabrik — isolation broken)"
                )
            else:
                failures.append(
                    f"{rel_path}: symlink → {resolved}"
                    " (governance must be local copies, not symlinks)"
                )
            continue

        # Check 3: For governance directories, recursively check descendants for symlinks
        if rel_path in (".windsurf/rules", ".windsurf/workflows") and path.is_dir():
            for descendant in path.rglob("*"):
                if descendant.is_symlink():
                    resolved = descendant.resolve()
                    rel_descendant = descendant.relative_to(PROJECT_ROOT)
                    if is_under_fabrik(resolved):
                        failures.append(
                            f"{rel_descendant}: symlink → {resolved}"
                            " (points to /opt/fabrik — isolation broken)"
                        )
                    else:
                        failures.append(
                            f"{rel_descendant}: symlink → {resolved}"
                            " (governance must be local copies, not symlinks)"
                        )

    if failures:
        return False, "\n".join(failures)

    return True, ""


def run_sync_steps() -> list[tuple[str, bool, str]]:
    """Run side-effect sync steps (last)."""
    # DEPRECATED: Sync steps removed - use scripts directly if needed
    return []


def stage_changes() -> tuple[bool, str]:
    """Stage all modified files."""
    code, out = run_cmd(["git", "add", "-A"])
    return code == 0, out


def log_gate_issues(results: list[tuple[str, bool, str]], gate_type: str) -> None:
    """Log failed checks to .droid/gate_issues.jsonl for analysis.

    Args:
        results: List of (check_name, passed, output) tuples
        gate_type: 'pre_kilo' or 'post_kilo'
    """
    import json
    from datetime import datetime

    failed = [(name, output) for name, passed, output in results if not passed]
    if not failed:
        return

    log_dir = PROJECT_ROOT / ".droid"
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / "gate_issues.jsonl"

    entry = {
        "timestamp": datetime.now().isoformat(),
        "gate_type": gate_type,
        "project": str(PROJECT_ROOT),
        "issues": [{"check": name, "output": output[:500]} for name, output in failed],
    }

    with open(log_file, "a") as f:
        f.write(json.dumps(entry) + "\n")

    print(
        f"  {YELLOW}📝 Logged {len(failed)} issues to .droid/gate_issues.jsonl ({gate_type}){RESET}"
    )


def get_git_status_hash() -> str:
    """Get hash of current git status (to detect file changes)."""
    code, out = run_cmd(["git", "status", "--porcelain"])
    return out if code == 0 else ""


def get_changed_files() -> set[str]:
    """Get set of changed file paths from git diff.

    Used by tiered execution to skip checks whose relevant files haven't changed.
    Combines both staged and unstaged changes.
    """
    changed = set()
    # Staged changes
    code, out = run_cmd(["git", "diff", "--name-only", "--cached"])
    if code == 0 and out:
        changed.update(f for f in out.strip().split("\n") if f)
    # Unstaged changes
    code, out = run_cmd(["git", "diff", "--name-only"])
    if code == 0 and out:
        changed.update(f for f in out.strip().split("\n") if f)
    # Untracked files
    code, out = run_cmd(["git", "ls-files", "--others", "--exclude-standard"])
    if code == 0 and out:
        changed.update(f for f in out.strip().split("\n") if f)
    return changed


def _has_extension(changed_files: set[str], *extensions: str) -> bool:
    """Check if any changed file has one of the given extensions."""
    return any(f.endswith(ext) for f in changed_files for ext in extensions)


def _has_path_prefix(changed_files: set[str], prefix: str) -> bool:
    """Check if any changed file starts with the given path prefix."""
    return any(f.startswith(prefix) for f in changed_files)


def _only_md_changed(changed_files: set[str]) -> bool:
    """Check if only markdown files were changed."""
    return all(f.endswith(".md") for f in changed_files) if changed_files else False


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
    parser.add_argument(
        "--post-kilo",
        action="store_true",
        help="Log issues caught (for post-Kilo analysis). Logs to .droid/gate_issues.jsonl",
    )
    parser.add_argument(
        "--lean",
        action="store_true",
        help="Tier 1: Showstoppers only (syntax, secrets, schema sync). For agent self-review.",
    )
    parser.add_argument(
        "--systemic",
        action="store_true",
        help="Tier 3: Repo health only (docker, ports, docs sprawl, deps). On-demand maintenance.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON for agent parsing",
    )
    # Note: --no-sync removed - default now never syncs (use --sync explicitly)
    return parser.parse_args()


def run_iteration(
    check_only: bool,
    _run_sync: bool,
    tier: int = 2,
    changed_files: set[str] | None = None,
    json_mode: bool = False,
) -> list[tuple[str, bool, str]]:
    """Run one iteration of all checks."""
    all_results: list[tuple[str, bool, str]] = []

    if not json_mode:
        tier_label = {1: "TIER 1 (LEAN)", 2: "TIER 2 (FULL)", 3: "TIER 3 (SYSTEMIC)"}
        print(f"  Gate: {tier_label.get(tier, 'UNKNOWN')}")

    # Phase 1: Formatting fixes (only in fix mode, skip for Tier 3)
    if not check_only and tier != 3:
        if not json_mode:
            print_header("PHASE 1: AUTO-FIX FORMATTING")
        results = run_formatting_fixes(tier=tier)
        all_results.extend(results)
        if not json_mode:
            for name, passed, out in results:
                print_step(name, passed, out)

    # Phase 2: Static checks (skip for Tier 3)
    if tier != 3:
        if not json_mode:
            print_header("PHASE 2: STATIC ANALYSIS")
        results = run_static_checks(tier=tier, changed_files=changed_files)
        all_results.extend(results)
        if not json_mode:
            for name, passed, out in results:
                print_step(name, passed, out)

        # Phase 2.5: AI fixes for static check failures (if enabled)
        if not check_only and os.getenv("FINAL_GATE_AI_FIX") == "1" and not json_mode:
            failed_tools = [
                (name, out)
                for name, passed, out in results
                if not passed and name in ("mypy", "ruff")
            ]
            if failed_tools:
                tool_names = [t[0] for t in failed_tools]
                print(
                    f"\n{BLUE}[AI FIX] Attempting cheap_fix_agent for: "
                    f"{', '.join(tool_names)}{RESET}"
                )
                for tool, tool_output in failed_tools:
                    success, msg = run_ai_fixes(tool, tool_output)
                    if success:
                        print(f"  {GREEN}✓ {tool}: {msg[:80]}{RESET}")
                    else:
                        print(f"  {YELLOW}⚠ {tool}: {msg[:80]}{RESET}")

    # Phase 3: Consistency checks
    if not json_mode:
        print_header("PHASE 3: REPO CONSISTENCY")
    results = run_consistency_checks(tier=tier, changed_files=changed_files)
    all_results.extend(results)
    if not json_mode:
        for name, passed, out in results:
            print_step(name, passed, out)

    return all_results


def main() -> int:
    """Run the final gate checks with iteration loop."""
    args = parse_args()

    # Determine tier
    if args.lean:
        tier = 1
    elif args.systemic:
        tier = 3
    else:
        tier = 2

    # Get changed files for diff-sensing
    changed_files = get_changed_files()

    # JSON mode: suppress all output except final JSON
    if not args.json:
        tier_label = {1: "LEAN (Tier 1)", 2: "FULL (Tier 2)", 3: "SYSTEMIC (Tier 3)"}
        print(f"{BOLD}Final Gate - Pre-Traycer Commit Checks{RESET}")
        mode = "CHECK ONLY" if args.check else "FIX"
        print(f"Mode: {mode} | Tier: {tier_label[tier]} | Max iterations: {MAX_ITERATIONS}")
        if changed_files:
            exts = {Path(f).suffix for f in changed_files if Path(f).suffix}
            print(
                f"Changed files: {len(changed_files)}"
                f" ({', '.join(sorted(exts)) or 'no extensions'})"
            )
        else:
            print("Changed files: none detected (running all checks)")

    # Initialize before loop
    all_results: list[tuple[str, bool, str]] = []

    for iteration in range(1, MAX_ITERATIONS + 1):
        if not args.check and iteration > 1 and not args.json:
            print(
                f"\n{BOLD}{YELLOW}=== Iteration {iteration}/{MAX_ITERATIONS}"
                f" (convergence rerun) ==={RESET}"
            )

        status_before = get_git_status_hash()
        all_results = run_iteration(
            check_only=args.check,
            _run_sync=False,
            tier=tier,
            changed_files=changed_files,
            json_mode=args.json,
        )

        failed = [r for r in all_results if not r[1]]

        if args.check:
            break

        if not failed:
            break

        status_after = get_git_status_hash()
        if status_before == status_after:
            if not args.json:
                print(f"\n{YELLOW}No file changes - remaining failures need manual fixes{RESET}")
            break

        if iteration < MAX_ITERATIONS:
            if not args.json:
                print(f"\n{YELLOW}Changes detected, re-validating...{RESET}")
            # Refresh changed files after fixes
            changed_files = get_changed_files()

    # Summary
    passed_count = len([r for r in all_results if r[1]])
    failed = [r for r in all_results if not r[1]]

    if args.post_kilo and failed:
        log_gate_issues(all_results, "post_kilo")

    if not args.check and not args.no_stage and not failed:
        status = get_git_status_hash()
        if status:
            if not args.json:
                print(f"\n{BLUE}Auto-staging modified files...{RESET}")
            ok, out = stage_changes()
            if ok and not args.json:
                print(f"  {GREEN}✓ Changes staged{RESET}")
            elif not ok and not args.json:
                print(f"  {RED}✗ Failed to stage: {out}{RESET}")

    # JSON output mode
    if args.json:
        import json

        result = {
            "status": "success" if not failed else "failure",
            "tier": tier,
            "passed": passed_count,
            "failed": len(failed),
            "failures": [
                {"check": name, "output": output[:500]}  # Truncate long outputs
                for name, _, output in failed
            ],
        }
        print(json.dumps(result, indent=2))
        return 0 if not failed else 1

    # Human-readable output mode
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
