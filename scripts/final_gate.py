#!/usr/bin/env python3
# AFTER-EDIT: docs/workflows/FINAL_GATE_WORKFLOW.md
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
    --stage-all  Legacy blanket `git add -A` (UNSAFE on shared tree)
    --sync       Sync-only mode (manual utility - no quality checks)
    --post-kilo  Log issues to .droid/gate_issues.jsonl

Checks:
1. AUTO-FIX: trailing whitespace, EOF, ruff-format, ruff --fix
2. STATIC: ruff, mypy, bandit, semgrep, yaml, json, sqlfluff, vulture
3. CONSISTENCY: structure, conventions, rule size, models, changelog, kilo health

Iterates up to 3 times until clean. On success, re-stages ONLY the files that
were already staged when the gate started (shared-tree safety: 3 agents + the
daily pipeline share one master). Stage your files before running the gate, or
use --stage-all for the legacy blanket behaviour.

Workflow Doc: docs/workflows/FINAL_GATE_WORKFLOW.md
  ⚠️  Update the workflow doc when modifying this script.
"""

import argparse
import contextlib
import io
import os
import re
import subprocess
import sys
from pathlib import Path

# Kaizen M1 sensor (T04) — OBSERVATION ONLY. Additive, idempotent path append + a
# defensive import: a project that never receives the box-local module behaves exactly
# as before (proven by the byte-compare in tests/test_kaizen_sensor_emitters.py).
_KAIZEN_DIR = str(Path(__file__).resolve().parent / "sysadmin")
if _KAIZEN_DIR not in sys.path:
    sys.path.append(_KAIZEN_DIR)
try:
    import kaizen_events  # noqa: E402
except Exception:  # pragma: no cover - absence is the normal case in a project
    kaizen_events = None  # type: ignore[assignment]

# The gate had no stderr channel of its own before T04, so the emitter's `_warn` (its
# ONLY failure channel) would have made a broken event store visible in the gate's
# output. Muted at the call site, never in `kaizen_events`: every other caller keeps
# the honest warning. `2.0` bounds exposure()'s git probes — the sensor fires after the
# verdict is settled, so an `unknown` field beats making the fleet's gate wait on git.
_KAIZEN_PROBE_TIMEOUT_S = 2.0

# Paths
PROJECT_ROOT = Path.cwd()  # Use current working directory, not script location
VENV_PYTHON = PROJECT_ROOT / ".venv" / "bin" / "python"
VENV_RUFF = PROJECT_ROOT / ".venv" / "bin" / "ruff"
# Use venv python only if it has the required tools (ruff) installed
PYTHON = str(VENV_PYTHON) if (VENV_PYTHON.exists() and VENV_RUFF.exists()) else sys.executable


# The tools the gate SHELLS OUT to with the selected interpreter. A module constant
# so a test can prove the probe actually fires (this box happens to have ruff on both
# interpreters, so transdoc's exact divergence is not reproducible here).
REQUIRED_TOOLS = ("ruff", "pytest")


def _toolchain_missing(python: str) -> str:
    """Which required tool the SELECTED interpreter cannot run — "" when fine.

    transdoc finding 1.2 (2026-08-23): the line above silently falls back to
    whatever interpreter invoked the gate when the venv has no ruff. Observed live
    on their tree, same second, same files:

        .venv/bin/python scripts/final_gate.py --json -> "failure" (No module named ruff)
        python3          scripts/final_gate.py --json -> "success"

    `status:"failure"` must mean "your tree is bad", NEVER "your toolchain is
    missing" — otherwise an agent learns to prefer whichever invocation passes,
    which is the single worst thing a completion gate can teach. Probe the chosen
    interpreter for the tools we are about to run and say SETUP out loud instead.
    """
    import subprocess as _sp

    for mod in REQUIRED_TOOLS:
        try:
            r = _sp.run(
                [python, "-c", f"import {mod}"], capture_output=True, timeout=30, check=False
            )
        except (OSError, _sp.SubprocessError):
            return mod
        if r.returncode != 0:
            return mod
    return ""


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
    "pytest": 900,
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


def clip_output(output: str, head: int = 1400, tail: int = 600) -> dict[str, object]:
    """Head+TAIL clip with a machine-readable marker, for every --json output field.

    A bare ``[:500]`` dropped exactly the line every tool puts its totals on
    (mypy/ruff/pytest all end with "Found N errors ..."), so the JSON showed "3 errors"
    indistinguishably from "the first 3 of 83" — consumers built a false cascade model
    and argued for reverting correct fixes (job-agent 01M10DYMRG; same class as a
    4-finding check surfacing 1, transdoc 01M12A2D90). The tail SURVIVES, the omission
    is stated in-band AND as fields, and an untruncated output keeps a stable schema.
    """
    if len(output) <= head + tail:
        return {"output": output, "truncated": False, "omitted_lines": 0}
    kept_head, kept_tail = output[:head], output[-tail:]
    omitted = output[len(kept_head) : len(output) - len(kept_tail)].count("\n")
    return {
        "output": f"{kept_head}\n… [truncated: ~{omitted} line(s) omitted — tail follows] …\n{kept_tail}",
        "truncated": True,
        "omitted_lines": omitted,
    }


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


# Rows whose check has NO failing exit path — declared at registration with
# `warn_only=True`. They can never turn the gate red, and until 2026-08-16 they printed
# the SAME `[PASS]` as a check that genuinely blocks, so a green gate could not be read:
# eight registered checks were each handed a real violation, each PRINTED it, and each
# exited 0. The set is the display layer's source of truth — `print_step` marks these rows
# `[ADVISORY]` and `--json` reports them under `advisory`, so "which rows can never fail"
# is answerable at a glance instead of by reading eight enforcement scripts.
#
# NOT the same flag as `advisory=`: that one only preserves stdout on exit 0, and several
# checks carrying it (check_docker, check_env_contract, check_doc_sprawl --strict,
# check_lint_ratchet, check_subagent_flywheel) DO fail the gate on a real defect. Blocking
# is about the exit code; `warn_only` is a claim about the check's contract.
WARN_ONLY_CHECKS: set[str] = {
    # transdoc finding 1.3 (2026-08-23): a SKIPPED pytest printed `[PASS] pytest`. In a repo
    # with no .github/workflows/ that meant the ENTIRE suite sat outside the completion gate
    # while the gate affirmed a green row — transdoc had 123 tests, including its whole RLS
    # conformance suite, in exactly that position. A row that never ran must never read as a
    # row that passed. These names are the NOT-RUN variants; a pytest that actually executes
    # still reports under the plain "pytest" name and can still turn the gate red.
    "pytest (NOT RUN)",
    "pytest (NO TESTS COLLECTED)",
}


def run_optional_check(
    script_path: str,
    check_name: str,
    *args: str,
    module: str | None = None,
    advisory: bool = False,
    warn_only: bool = False,
) -> tuple[str, bool, str]:
    """Run an optional enforcement check, skipping if script doesn't exist.

    Args:
        script_path: Relative path to script from PROJECT_ROOT
        check_name: Display name for the check
        *args: Additional command arguments
        module: If provided, run as 'python -m <module>' instead of direct script
        advisory: If True, preserve stdout even on exit 0 (for warning-level checks)
        warn_only: If True, this check has no failing exit path by contract. Implies
            `advisory` (its stdout IS its whole product) and marks the row non-blocking
            in every output mode. It never weakens enforcement: a warn_only check that
            somehow exits non-zero still FAILS the gate, and says so — a broken contract
            is a louder finding than a quiet one, not a quieter one.

    Returns:
        (check_name, passed, message) tuple
    """
    if warn_only:
        WARN_ONLY_CHECKS.add(check_name)
        advisory = True
    full_path = PROJECT_ROOT / script_path
    if not full_path.exists():
        # VISIBLE, not silently green (fabrik-lib finding 2026-08-14): a deleted or
        # un-refreshed check used to vanish from enforcement with NO change to the gate's
        # green count. It still must not RED a project that legitimately lacks an optional
        # check — so it stays passed=True, but carries the ⚠ prefix the --json layer
        # collects into `warnings`, where an operator (and CI) can actually see it.
        return (check_name, True, f"⚠ check not present, skipping: {script_path}")

    if module:
        code, out = run_cmd([PYTHON, "-m", module] + list(args))
    else:
        code, out = run_cmd([PYTHON, str(full_path)] + list(args))
    if code != 0:
        if warn_only:
            # The declaration is now false. Fail (never weaken enforcement) and name the
            # broken contract, so the fix is "drop the warn_only flag", not "hunt the row".
            out = (
                f"{check_name} is registered warn_only=True but exited {code} — its "
                f"contract changed; drop `warn_only=True` at its registration.\n{out}"
            )
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
    cmd_base = [PYTHON, "-m", "mypy", "--config-file=pyproject.toml"]
    # Flat-layout fallback (target "."): exclude synced infra dirs so mypy checks only the
    # project's own code, never a synced enforcement script or data/ file it cannot fix.
    if target == ".":
        cmd_base += ["--exclude", _MYPY_EXCLUDE_RE]
    # An empty target means "let [tool.mypy] files= drive discovery" — pass no path at all.
    if target:
        cmd_base.append(target)

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
    """Print step result.

    A row whose check was registered `warn_only=True` prints `[ADVISORY]`, not `[PASS]`.
    Both are exit-0 rows, but only one of them COULD have been red — and an operator
    reading a green gate has no other way to tell them apart.
    """
    if passed and name in WARN_ONLY_CHECKS:
        status = f"{YELLOW}ADVISORY{RESET}"
    else:
        status = f"{GREEN}PASS{RESET}" if passed else f"{RED}FAIL{RESET}"
    print(f"  [{status}] {name}")
    if not passed and output:
        for line in output.split("\n")[:10]:  # Limit output
            print(f"       {line}")
    elif passed and output and "check not present, skipping" not in output:
        # Advisory output (warnings from non-blocking checks)
        for line in output.split("\n")[:10]:
            print(f"       {YELLOW}{line}{RESET}")


def fix_trailing_whitespace(files: list[str]) -> tuple[bool, str, int]:
    """Fix trailing whitespace in the given (changed) text files. Preserves LF/CRLF.

    Operates ONLY on the files the current change touched — never a whole-tree
    sweep, which on shared master churns a sibling's or a Fabrik-synced file.
    """
    files_fixed = 0
    errors = []
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


def fix_end_of_files(files: list[str]) -> tuple[bool, str, int]:
    """Ensure the given (changed) text files end with a newline. Preserves LF/CRLF.

    Scoped to the current change's files only (see fix_trailing_whitespace).
    """
    files_fixed = 0
    errors = []
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


def run_formatting_fixes(
    tier: int = 2, changed_files: set[str] | None = None
) -> list[tuple[str, bool, str]]:
    """Run auto-fix formatting steps, SCOPED to the current change's files.

    Every auto-fixer here mutates the working tree, so it must only ever touch files
    the change touched — a whole-tree `ruff format scripts/` or a `git ls-files`
    whitespace sweep reformats a sibling's or a Fabrik-synced file that merely had
    non-canonical formatting sitting in the tree, manufacturing phantom churn (and,
    on shared master, risking clobbering concurrent work). Empty change set → nothing
    to fix.
    """
    # Tier 3 (systemic): Skip formatting - systemic checks don't auto-fix
    if tier == 3:
        return []

    changed = changed_files or set()
    text_files = _changed_text(changed)
    ruff_py = _changed_python(changed)

    results = []

    # Trim trailing whitespace (changed text files only)
    ok, msg, _ = fix_trailing_whitespace(text_files)
    results.append(("trim trailing whitespace", ok, msg if not ok else ""))

    # Fix end of files (changed text files only)
    ok, msg, _ = fix_end_of_files(text_files)
    results.append(("fix end of files", ok, msg if not ok else ""))

    # Ruff format + fix — changed .py only; skip entirely when none changed.
    if ruff_py:
        code, out = run_cmd(
            [PYTHON, "-m", "ruff", "format", *ruff_py],
            timeout=TIMEOUTS["ruff"],
        )
        results.append(("ruff-format", code == 0, out if code != 0 else ""))

        code, out = run_cmd(
            [PYTHON, "-m", "ruff", "check", "--fix", *ruff_py],
            timeout=TIMEOUTS["ruff"],
        )
        # returncode 0 = clean, 1 = issues found (some fixed), other = error
        # We treat 0 and 1 as acceptable (remaining issues caught by ruff check)
        if code in (0, 1):
            results.append(("ruff --fix", True, ""))
        else:
            results.append(("ruff --fix", False, out))

    return results


# Infra/scaffold dirs that are never the project's own type-checked source. A src-layout
# target only ever checks src/, so these are implicitly excluded there; for a flat-layout
# fallback (target ".") we exclude them explicitly so mypy never fails on a SYNCED enforcement
# script or a data/ file the project cannot fix.
_MYPY_EXCLUDE_RE = (
    r"(^|/)(scripts|tests|docs|config|db|data|logs|backups|output|libs|templates|"
    r"node_modules|migrations|\.venv|\.git)(/|$)"
)


def _import_load_spec():
    """Import fabrik.spec_loader's load_spec WITHOUT leaking its env side effects.

    Importing the hub settings chain SETS os.environ["DATABASE_URL"] inside the gate
    process; every later run_cmd child inherited it, un-skipping env-keyed tests into a
    connect against the leaked DSN — the gate's pytest red while the identical command
    passed standalone (trade-intelligence, proven end-to-end 2026-08-16, finding
    01M0CT0GDXWTB3Y6XXPVXJFN14). The settings object keeps whatever it captured at
    import; only the PROCESS env is restored, so children see the env the operator ran
    the gate with. Returns None when fabrik isn't importable (gate outside the hub)."""
    import sys as _sys

    _src = str(PROJECT_ROOT / "src")
    if _src not in _sys.path:
        _sys.path.insert(0, _src)
    env_before = dict(os.environ)
    try:
        from fabrik.spec_loader import (
            load_spec as _load_spec,  # type: ignore[import-not-found,unused-ignore]
        )

        return _load_spec
    except ImportError:
        return None  # outside fabrik repo; caller falls back to yaml.safe_load
    finally:
        for k in set(os.environ) - set(env_before):
            del os.environ[k]
        for k, v in env_before.items():
            if os.environ.get(k) != v:
                os.environ[k] = v


def _mypy_config_selects_files() -> bool:
    """True when pyproject's [tool.mypy] declares files=/packages=/modules= — i.e. the project
    tells mypy exactly what to check, so the gate passes NO target and lets mypy self-discover."""
    pp = PROJECT_ROOT / "pyproject.toml"
    if not pp.exists():
        return False
    try:
        import tomllib

        mypy_cfg = tomllib.loads(pp.read_text(encoding="utf-8")).get("tool", {}).get("mypy", {})
    except (OSError, ValueError):
        return False
    return bool(mypy_cfg.get("files") or mypy_cfg.get("packages") or mypy_cfg.get("modules"))


def detect_src_package() -> str:
    """The mypy target for this project.

    - src-layout: the single package under src/ (e.g. ``src/foo``), else ``src/`` for the tree.
    - flat-layout (no src/): ``""`` when the project's own [tool.mypy] declares files=/packages=
      (mypy self-discovers), otherwise ``"."`` (scoped by _MYPY_EXCLUDE_RE in run_mypy_with_recovery).

    NEVER returns a hardcoded ``src/`` for a flat project — that made mypy target a nonexistent path
    ("Cannot read file 'src'"), silently disabling type-checking for every flat-layout repo.
    """
    src_dir = PROJECT_ROOT / "src"
    if src_dir.exists():
        packages = [
            item
            for item in src_dir.iterdir()
            if item.is_dir() and not item.name.startswith((".", "_"))
        ]
        return f"src/{packages[0].name}" if len(packages) == 1 else "src/"
    return "" if _mypy_config_selects_files() else "."


def _uninvoked_test_dirs() -> list[str]:
    """Test directories the gate's `pytest tests/` leg never reaches.

    Same fail-silent-green shape as `_skip_note`, one level out: the leg invokes
    `pytest tests/` with an explicit path, and `pyproject.toml`'s
    ``testpaths = ["tests"]`` says the same thing — so a suite living anywhere else is
    never collected, and a green gate looks identical to one that ran it. Measured
    (intel, 2026-08-29): `scripts/kilo-benchmarks/tests/` holds the golden-parity ORACLE
    that `daily_refresh.sh:398` treats as a severity=critical production gate. A green
    Tier-2 asserted nothing about it; drift surfaced only via cron, days later.

    Naming them is the whole fix — the gate does not need to RUN them (an unowned suite
    could red every session), it needs to stop implying it did.
    """
    # `git ls-files` ONLY — never a filesystem walk. The first cut used
    # `Path(".").glob("*/**/tests")` and died with OSError(ENOMEM) walking a repo that
    # carries a large untracked `vault/`. Tracked files are also the right SET: an
    # untracked scratch suite is nobody's contract.
    try:
        res = subprocess.run(
            ["git", "ls-files", "*/test_*.py", "*/tests/*.py"],
            capture_output=True,
            text=True,
            timeout=20,
        )
    except Exception:
        return []
    if res.returncode != 0:
        return []
    dirs = set()
    for line in res.stdout.splitlines():
        d = str(Path(line).parent)
        if d == "tests" or d.startswith("tests/"):
            continue  # the leg DOES invoke this one
        if any(part in {".venv", "node_modules", "__pycache__"} for part in Path(d).parts):
            continue
        if d.startswith("templates/"):
            continue  # scaffold TEMPLATES — those tests run in the emitted project, not here
        dirs.add(d)
    return sorted(dirs)


def _skip_note(tool: str) -> str:
    """A tool that is not installed did not PASS — it was never asked.

    The diff-sensed skip below already says so; a tool-not-installed skip did not, and counted
    silently green. transdoc (2026-08-28) measured the consequence in a scaffolded project: the
    `.venv` had neither `ruff` nor `mypy`, while CLAUDE.md advertises `--json` as "the FULL Tier-2
    gate: mypy + bandit + semgrep". A green run there asserted nothing about the two headline
    static checks and looked identical to one that ran them — the fail-silent-green shape this
    corpus exists to remove, in the gate itself.
    """
    return (
        f"\u26a0 {tool} NOT INSTALLED — skipped, not passed; this green asserts nothing about "
        f"what {tool} checks. Install it in the interpreter running the gate."
    )


def run_static_checks(
    tier: int = 2, changed_files: set[str] | None = None
) -> list[tuple[str, bool, str]]:
    """Run static analysis checks, filtered by tier and changed files."""
    results: list[tuple[str, bool, str]] = []
    changed = changed_files or set()

    # Tier 3: Skip all static checks (systemic only runs consistency)
    if tier == 3:
        return results

    # Diff-sensing: if only .md files changed, skip all static checks — but SAY so.
    # A silently skipped tier made a green run indistinguishable from a verified one,
    # so a repo could carry a large mypy debt while every recorded gate read green
    # (job-agent 01M10DYMRG, secondary finding). The ⚠ prefix routes this row into
    # --json's `warnings`, so a green result carries its own scope.
    if changed and _only_md_changed(changed):
        results.append(
            (
                "static tier (diff-sensed skip)",
                True,
                "⚠ static checks skipped — only .md files in the diff; this green asserts "
                "nothing about lint/type debt",
            )
        )
        return results

    # --- Ruff check (Tier 1 + Tier 2) — scoped to the CHANGED python files ---
    # Whole-tree `ruff check scripts/` reds the gate on a pre-existing or Fabrik-synced
    # line the current change never touched (and, in a project, is forbidden to edit).
    # Bind it to the .py this change actually adds/edits under the lint roots; no
    # changed .py → nothing to lint.
    ruff_py = _changed_python(changed)
    if ruff_py:
        code, out = run_cmd(
            [PYTHON, "-m", "ruff", "check", *ruff_py],
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
            # T2-03 G-E2: pydantic Spec validation for spec files. Imported
            # lazily — if fabrik isn't installed (gate running outside
            # /opt/fabrik), skip spec validation gracefully rather than
            # failing the whole check.
            load_spec = _import_load_spec()
            for f in files:
                path = PROJECT_ROOT / f
                if path.exists():
                    try:
                        # safe_load_all validates EVERY document — multi-document YAML
                        # (e.g. Maestro flows: `appId:` config + `---` + flow) is valid
                        # YAML that plain safe_load rejects ("expected a single document").
                        list(yaml.safe_load_all(path.read_text(encoding="utf-8")))
                    except yaml.YAMLError as e:
                        yaml_ok = False
                        yaml_errors.append(f"{f}: {e}")
                        continue
                    except UnicodeDecodeError:
                        yaml_ok = False
                        yaml_errors.append(f"{f}: non-UTF8 encoding")
                        continue
                    # T2-03 G-E2: if the file is under specs/services/, run
                    # pydantic validation on top of plain yaml.safe_load.
                    # Catches missing required fields, shape-domain
                    # contradictions, and other Spec-model violations
                    # before they reach `fabrik apply`.
                    if load_spec is not None and "specs/services/" in f.replace("\\", "/"):
                        try:
                            load_spec(str(path))
                        except Exception as e:  # noqa: BLE001
                            yaml_ok = False
                            yaml_errors.append(f"{f}: Spec validation failed: {e}")
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
            results.append(("bandit (NOT INSTALLED — skipped)", True, _skip_note("bandit")))
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

    # Pytest — CI parity (only when THIS repo's CI runs pytest). Prevents the
    # #1 local-green/CI-red gap: an agent reaches "status: success" yet pushes
    # test-failing code because the gate never ran the suite CI runs (proven
    # live on trading-intelligence, 2026-07-24 — its CI runs ruff+pytest).
    # Scoped to CI-parity deliberately: a repo whose CI does NOT run pytest has
    # no CI red to prevent, and a hub-scale suite (fabrik: 2500 tests, ~3h)
    # would brick every completion gate. -x stops at the first failure.
    def _ci_runs_pytest() -> bool:
        """Does this repo expect its suite to pass, so the gate should run it?

        ⚠️ The name is historical: the ONLY signal used to be "a workflow file mentions pytest".
        That proxy INVERTS the moment a repo moves CI local — deleting `.github/workflows/`
        silently DISARMS local pytest, so a cutover meant to keep the same checks would remove
        one. Measured 2026-08-29 across /opt: **10 repos** (trade-intelligence, tryton-crm,
        job-agent, youtube, session-recall, trading-core, whatsapp-agent, longephedia-vault,
        gmail-account-creator, fabrik-claim-validator) run pytest locally TODAY for no reason
        other than the presence of that workflow text.

        So an explicit marker now wins, and the CI scan stays as the legacy fallback: no repo
        changes behaviour, and a repo retiring its workflows keeps its suite by touching
        `.fabrik/run-pytest`. Decoupling it entirely was measured and REJECTED for now — 29 repos
        have `tests/` without a CI mention (fabrik 224 files, seo 147, brand-identiy-creator 118),
        and switching them all on blind would red every repo with a stale suite on landing day.
        """
        if (PROJECT_ROOT / ".fabrik" / "run-pytest").exists():
            return True
        wf_dir = PROJECT_ROOT / ".github" / "workflows"
        if not wf_dir.is_dir():
            return False
        for wf in wf_dir.glob("*.y*ml"):
            try:
                if "pytest" in wf.read_text(encoding="utf-8", errors="ignore"):
                    return True
            except OSError:
                continue
        return False

    if (
        (PROJECT_ROOT / "tests").is_dir()
        and _ci_runs_pytest()
        and (
            not changed
            or _has_path_prefix(changed, "src/")
            or _has_path_prefix(changed, "tests/")
            or _has_path_prefix(changed, "scripts/")
        )
    ):
        code, out = run_cmd(
            [PYTHON, "-m", "pytest", "tests/", "-x", "-q", "--color=no", "-p", "no:cacheprovider"],
            timeout=TIMEOUTS["pytest"],
        )
        if "No module named pytest" in out:
            results.append(
                ("pytest (NOT RUN)", True, "pytest is not installed in this interpreter")
            )
        elif code == 5:  # pytest exit 5 = no tests collected
            results.append(
                ("pytest (NO TESTS COLLECTED)", True, "pytest ran and collected 0 tests")
            )
        else:
            tail = "\n".join(out.splitlines()[-30:])
            _uninvoked = _uninvoked_test_dirs()
            if code == 0 and _uninvoked:
                tail = (
                    f"\u26a0 this green covers `tests/` ONLY — {len(_uninvoked)} test dir(s) "
                    f"were never invoked and this run asserts nothing about them: "
                    f"{', '.join(_uninvoked)}. The leg passes an explicit `tests/` path (and "
                    f"pyproject's testpaths says the same), so a suite living elsewhere is not "
                    f"collected. Run it yourself if your change touches it."
                )
            results.append(("pytest", code == 0, tail))
    else:
        # SAY WHICH of the three conditions fired. The old message listed all three, so a
        # PERMANENT structural exclusion ("this repo's CI never runs pytest, so the gate
        # never will either") read identically to a TRANSIENT one ("nothing changed this
        # diff"). On the hub that exclusion is permanent — neither workflow mentions
        # pytest — which makes every green here silent about a 2500-test suite while
        # looking like an ordinary skip. Same fail-silent-green shape the NOT-INSTALLED
        # lines fixed (intel 01M153PX7G).
        if not (PROJECT_ROOT / "tests").is_dir():
            _why = "no tests/ directory in this repo"
        elif not _ci_runs_pytest():
            _why = (
                "this repo's CI does not invoke pytest, so the gate does not either — "
                "PERMANENT, not a per-diff skip. Deliberate (a CI that never reds has no "
                "red to prevent, and a hub-scale suite would brick every completion gate), "
                "but it means THIS GREEN ASSERTS NOTHING ABOUT THE TEST SUITE. Run it "
                "yourself: `python -m pytest tests/ -q`, or make the gate run it every time "
                "with `mkdir -p .fabrik && touch .fabrik/run-pytest` — required if this repo "
                "retires its GitHub workflows, since deleting them otherwise disarms this check"
            )
        else:
            _why = "no src/, tests/ or scripts/ changes in this diff"
        results.append(("pytest (NOT RUN)", True, f"{_why} — the suite is OUTSIDE this gate"))

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
                results.append(("sqlfluff (NOT INSTALLED — skipped)", True, _skip_note("sqlfluff")))
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
        results.append(("vulture (NOT INSTALLED — skipped)", True, _skip_note("vulture")))
    else:
        results.append(("vulture", code == 0, out if code != 0 else ""))

    return results


def run_consistency_checks(
    tier: int = 2, changed_files: set[str] | None = None, check_only: bool = False
) -> list[tuple[str, bool, str]]:
    """Run repo consistency checks, filtered by tier and changed files."""
    results = []
    changed = changed_files or set()

    # Convergence-evidence gate (every tier): a changed plans/ or reviews/ markdown
    # that CLAIMS convergence must embed its proof (Evidence section + file:line
    # citations + fenced command output; reviews embed a final_gate success). Inert
    # when no such artifact changed. See scripts/enforcement/check_convergence.py.
    results.append(
        run_optional_check(
            "scripts/enforcement/check_convergence.py",
            "Convergence Evidence (plans + reviews)",
        )
    )

    # Coverage-checklist gate (every tier): a changed reviews/ artifact from the
    # coverage-adjudicated commands (/fabrik-review, /fabrik-repo-review) must
    # embed a fully-adjudicated Coverage Checklist (or a Declared residual).
    # Inert when no such artifact changed. See scripts/enforcement/check_review_coverage.py.
    results.append(
        run_optional_check(
            "scripts/enforcement/check_review_coverage.py",
            "Coverage Checklist (reviews)",
            # round 23: without advisory=True the committed-scan lines (non-quiet exits,
            # standing IN-PROGRESS nags) were DISCARDED on success — the visibility feature
            # existed only for direct invocations, never for the documented gate path
            advisory=True,
        )
    )

    # Vendored-enforcement drift (hub-only; self-skips elsewhere): sync-EXCLUDED repos
    # PULL — nothing is pushed to them — and an undeclared divergence in their vendored
    # governance set is invisible debt (two undelivered-fix incidents in two days measured
    # it, 2026-08-16). Advisory by contract; the repo's own allowlist declares design.
    results.append(
        run_optional_check(
            "scripts/enforcement/check_vendored_drift.py",
            "Vendored Drift (sync-excluded repos)",
            warn_only=True,
        )
    )

    # Certification coverage: /fabrik-user-test and /fabrik-service-test graded their own
    # denominator. The inventory was PROSE WITH COUNTS authored by the agent later graded against it,
    # and NOTHING read it — there was no certification grader at all. On an inherited surface it
    # under-counts silently and the run terminates honestly and wrong. Coverage-quality findings are
    # advisory on landing so every project SEES its real fraction without a release freezing.
    # ⚠️ NOT warn_only, deliberately (corpus audit cmd 14/31, 2026-08-29): the anti-mix-up findings
    # (a cert board wearing `## Ticket Board`, a cert lock in `.fabrik/plan-locks/`) exit 1 and MUST
    # red the gate — a mis-headed board gets dispatched to CODING agents. Under warn_only that
    # verdict was typography: three files said BLOCKING while `return 0` + warn_only made blocking
    # impossible. `advisory=True` preserves the advisory stdout; the exit code carries the verdict.
    results.append(
        run_optional_check(
            "scripts/enforcement/check_certification_coverage.py",
            "Certification Coverage (advisory; board mix-up BLOCKS)",
            advisory=True,
        )
    )

    # Plan-lock release (advisory): a finished plan must not hold its scope lock. The protocol
    # has three readers and ZERO writers — the lock is created and released by PROSE, so the
    # omission is invisible until it surfaces days later as a hard BLOCKED halt at an unrelated
    # agent's /fabrik-execute-plan step 7 (measured: one lock held ten high-traffic hub paths
    # for thirteen days). Executable backing for fabrik-catchup probe 1.
    #
    # EVERY-TIER on purpose — registered here, ABOVE the `if tier in (1, 2):` marker below,
    # never inside it. `--lean` is the mode agents run DURING execution, which is exactly when
    # a lock is live; a tier-2-only registration would be absent precisely when the check
    # matters. Pinned by tests/enforcement/test_final_gate_registration.py, whose helper rejects
    # ANY `if tier …` ancestor (an Eq-only pin waves through `in (1, 2)` and `>= 2`).
    #
    # warn_only=True: the check always exits 0 by contract — a non-zero exit here would turn an
    # advisory row into a blocking red across ~46 governance-synced repos.
    results.append(
        run_optional_check(
            "scripts/enforcement/check_plan_lock_release.py",
            "Plan-lock release",
            warn_only=True,
        )
    )

    # Rivals-dossier contract. Registered for the same reason and on the same terms as the
    # plan-lock check above: it is tier-independent (a dossier's contract does not care which tier
    # the caller asked for), it always exits 0 by contract, and warn_only=True keeps it advisory —
    # a non-zero exit here would turn an advisory row into a blocking red across ~46 synced repos.
    # Silent in every repo that has no docs/reference/rivals/, which is most of the fleet.
    results.append(
        run_optional_check(
            "scripts/enforcement/check_rivals_dossier.py",
            "Rivals dossier",
            warn_only=True,
        )
    )

    # Spec convergence. Same terms and same reason as the two checks above: tier-independent (a
    # spec's contract does not care which tier the caller asked for), always exits 0 by contract,
    # warn_only so a finding never reddens ~46 synced repos. Silent in a repo with no CONVERGED
    # spec. NOT grandfathered — pre-existing CONVERGED specs are graded too, per the standing
    # rollout ruling (advisory on landing, promote after the fleet has run it once).
    results.append(
        run_optional_check(
            "scripts/enforcement/check_spec_convergence.py",
            "Spec convergence",
            warn_only=True,
        )
    )

    # Close-out feedback duty. Same terms as its three advisory siblings above: tier-independent,
    # always exits 0 by contract, warn_only so a finding never reddens ~46 synced repos. Silent when
    # no run closed in the window. Baseline at landing: 11 closes, 11 without a verdict — which is
    # exactly the number a grader exists to move, and which no agent would ever self-report.
    results.append(
        run_optional_check(
            "scripts/enforcement/check_feedback_duty.py",
            "Feedback duty",
            warn_only=True,
        )
    )

    # Trigger routing — a command's ADVERTISED phrase must not reach a DIFFERENT command. Measured
    # 2026-08-28: 5 of 71 did, and each landed on a command whose own SKIP clause disclaims the
    # phrase. ADVISORY, and deliberately blind to phrases that route NOWHERE — that is safe, and
    # grading it would push someone to close 42 gaps with loose patterns, which is how a router
    # starts hijacking unrelated prompts. Hub-only: silent wherever commands/_sources/ is absent.
    results.append(
        run_optional_check(
            "scripts/enforcement/check_trigger_routing.py",
            "Trigger routing (advertised phrase -> its own command)",
            warn_only=True,
        )
    )

    # ── Tier 1: Showstoppers only ──
    # Applied for Tier 1 and Tier 2. Tier 3 is systemic-only and skips these.
    if tier in (1, 2):
        results.append(
            run_optional_check("scripts/enforcement/check_secrets.py", "Secrets (Zero Hardcoding)")
        )
        results.append(
            # Named for what it CHECKS. It used to share the display name ".env Updates
            # (Secrets)" with check_env_updates.py — two rows, one label, different
            # severities: this one blocks on a hardcoded localhost DSN, that one could
            # not fail at all. (check_env_updates is unwired below.)
            run_optional_check(
                "scripts/enforcement/check_env_vars.py", "Hardcoded localhost/127.0.0.1 Ban"
            )
        )
        # Phantom imports — shipped code importing a module that is NOT IN THE REPO (gitignored, or vendored
        # but never `git add`ed). Green locally (the file sits on this disk), ModuleNotFoundError in CI and in
        # the deployed container (the VPS `git pull`s — an untracked file never reaches it). A SHOWSTOPPER,
        # and the reason this gate exists: a static check running in the developer's own .venv otherwise
        # models the WRONG universe. It must model the CLEAN CHECKOUT — git is what CI and Docker receive.
        results.append(
            run_optional_check(
                "scripts/enforcement/check_imports_resolvable.py",
                "Imports Resolvable (clean checkout)",
                # advisory=True preserves stdout on exit 0. Without it `run_optional_check` returns ""
                # for a passing check, which SILENTLY DISCARDED the entire WARN tier — every phantom in
                # `scripts/` printed a warning the operator never saw. The documented severity split
                # (src/app/tests = ERROR, scripts/ = WARN) was dead code. ERRORs still fail the gate
                # via the non-zero exit; this only stops the warnings evaporating.
                advisory=True,
            )
        )
        # Lint ratchet — repo-wide ruff count may only go DOWN. final_gate lints only the diff, so
        # accumulated repo-wide debt is invisible to it and surfaces as a red CI (`ruff check .`). The
        # ratchet seeds a per-repo baseline on first run (never blocks), then FAILS any run that raises
        # the count. `--check` (CI/read-only) still fails on a rise but never rewrites the baseline.
        ratchet_args = ("--check",) if check_only else ()
        results.append(
            run_optional_check(
                "scripts/enforcement/check_lint_ratchet.py",
                "Lint Ratchet (repo-wide, no new debt)",
                *ratchet_args,
                advisory=True,
            )
        )
        # Schema sync only if models or .sql changed
        if not changed or _has_extension(changed, ".py", ".sql"):
            results.append(
                run_optional_check(
                    "scripts/enforcement/check_schema_sync.py",
                    "Schema Sync (DB Models)",
                    advisory=True,  # preserve the data-contract-drift WARN on exit 0
                )
            )
        # Frozen-chain drift (transdoc upstream 2026-08-22): a consumer artifact's
        # version PIN must not predate its input (flows → data-contract → ui-design
        # → design-system). warn_only BY CONTRACT: the bump commit necessarily
        # holds the stale pin for its own duration — the WARN names the owed
        # re-freeze command. Tier 1+2 (<50ms text parse; the iteration tier is
        # where a mid-pipeline agent actually meets it).
        results.append(
            run_optional_check(
                "scripts/enforcement/check_frozen_chain.py",
                "Frozen Chain (contract pins)",
                warn_only=True,
            )
        )
        # Doc Sync Matrix — the single "update docs when code changes" gate
        # (consolidates CHANGELOG / INDEX / CONFIGURATION / schema / QUICKSTART /
        # FEATURES / PORTS touch-on-change). Tier 1+2 so it blocks in --lean.
        results.append(
            run_optional_check("scripts/enforcement/check_doc_sync.py", "Doc Sync Matrix")
        )
        # Subagent flywheel — WARN when a POOL run (run_agents) ran but was never scored+recorded
        # (ledger − receipts, reconciled locally since the subagent_runs writer role is INSERT-only).
        # BLOCKING (operator-approved 2026-07-10): Layer 1 "pool-or-declare" fails the gate when a
        # substantial CODE change ran ZERO pool subagent runs this cycle and carries no NO-POOL
        # declaration — the teeth for 62 § Dispatch policy's pool-default (advisory prose demonstrably
        # did not change behaviour). The check is fail-safe (any git/parse/exception → exit 0), and
        # native-only work escapes via `NO-POOL: <reason>` (commit msg) or `FABRIK_NO_POOL` (env).
        # Layer 2 (unrecorded-run reconciliation) stays advisory inside the same script.
        # advisory=True preserves the script's stdout on exit 0 so Layer 2's unrecorded-run WARNs stay
        # visible on a PASSING gate. It does NOT weaken blocking: run_optional_check returns passed=False
        # on ANY non-zero exit regardless of this flag, so Layer 1's exit 1 still fails the gate.
        results.append(
            run_optional_check(
                "scripts/enforcement/check_subagent_flywheel.py",
                "Subagent Flywheel (pool-or-declare — BLOCKING)",
                advisory=True,
            )
        )
        # Mutation testing (Behavior Contract substance-mechanical layer) — proves the new tests KILL
        # mutants, not just cover lines. Advisory + diff-scoped + OPT-IN (runs only when FABRIK_MUTMUT=1;
        # nightly/CI/on-demand, never per-PR blocking per 45-testing-strategy.md). Always exits 0.
        # The GATE is never the mutation invoker (the weekly cron / a direct call are) — strip a
        # leaked FABRIK_MUTMUT for this one child: the gate's 120s outer timeout would SIGKILL only
        # check_mutation.py itself while the session-detached `mutmut run` grandchild survives as an
        # unbounded orphan on the shared box (review finding, mechanism live-reproduced).
        _mutmut_leak = os.environ.pop("FABRIK_MUTMUT", None)
        try:
            results.append(
                run_optional_check(
                    "scripts/enforcement/check_mutation.py",
                    "Mutation (opt-in FABRIK_MUTMUT)",
                    # "Always exits 0" above is the contract; declare it so the row says so.
                    warn_only=True,
                )
            )
        finally:
            if _mutmut_leak is not None:
                os.environ["FABRIK_MUTMUT"] = _mutmut_leak
        # Doc stub force-fill — WARN when a seeded doc still carries template placeholders
        # AFTER its Doc-Sync trigger fired (a scaffolded stub that rotted past relevance).
        # ADVISORY (B, 2026-08-16 registration audit). Fail-safe by design — every path of
        # `main()` returns 0 — so `warn_only=True` is a statement of the check's real
        # contract, not a downgrade. Measured before deciding: 16 of 44 /opt repos still
        # ship a stub `docs/QUICKSTART.md`, so promoting it would red a third of the fleet
        # the next time any of them touches a route.
        results.append(
            run_optional_check(
                "scripts/enforcement/check_doc_stubs.py",
                "Doc stub fill",
                warn_only=True,
            )
        )
        # Script coupling header — each staged scripts/**/*.py declares (via a
        # `# AFTER-EDIT:` header) the files to update when it changes. Touch-on-change
        # (mirrors Doc Sync).
        # ADVISORY (B, 2026-08-16 registration audit). CLAUDE.md documents this row as
        # "Gate-enforced (WARN)" and the check's own docstring defers promotion until the
        # active scripts are headered — they are not: 427 headerless `scripts/**/*.py`
        # across 36 of 44 /opt repos, 107 in the hub alone. It was ALSO registered without
        # `advisory`, so `run_optional_check` discarded its stdout on exit 0 and the WARNs
        # it exists to emit reached nobody. `warn_only=True` restores the text and labels
        # the row for what it is.
        results.append(
            run_optional_check(
                "scripts/enforcement/check_script_headers.py",
                "Script Coupling Header",
                warn_only=True,
            )
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
        # tls.certresolver, loadbalancer.server.port). Historical lesson:
        # relying on Coolify-era runtime label auto-injection silently broke
        # admin-dashboard 2FA in production — see docs/LESSONS_LEARNT.md §8.7
        # (GlitchTip incident). Today's SSH+Compose deployer ships the
        # rendered compose verbatim; explicit labels are still mandatory.
        results.append(
            run_optional_check(
                "scripts/enforcement/check_traefik_labels.py",
                "Full Traefik Label Set (§7)",
            )
        )
        # Spec <-> project DB-name consistency (deploy-readiness-gaps Phase 1c).
        # The postgres registrar provisions (spec.depends.postgres or the derived
        # spec-id name); this catches drift vs the project's own PG_DATABASE /
        # DATABASE_URL — the bug class that left calendar pointed at an empty/wrong
        # DB (/api/health passed on SELECT 1 while real endpoints 500'd). Skips
        # cleanly where there's no specs/services/ dir (every non-fabrik project).
        results.append(
            run_optional_check(
                "scripts/enforcement/check_spec_db_match.py",
                "Spec <-> Project DB Name Match (Phase 1c)",
            )
        )
        # Undeclared-import guard (ci-parity): the app source imports a package
        # declared in NO manifest -> a fresh `pip install -r requirements.txt` (CI's
        # clean room, or a fresh `fabrik apply` deploy) crashes on import. check_deps_sync
        # only compares requirements.txt<->pyproject to each other and is blind to what
        # the code imports; this closes that gap. Runs in the project's own .venv, skips
        # cleanly where there's no requirements.txt. See the CI-parity plan (Fix B).
        results.append(
            run_optional_check(
                "scripts/enforcement/check_undeclared_imports.py",
                "Undeclared Imports (requirements.txt)",
            )
        )
        # Fabrik-synced files must match the /opt/fabrik canonical source — they
        # are centrally distributed and overwritten on sync, so a local edit is a
        # mistake (revert + change upstream). Self-exempts inside /opt/fabrik;
        # skips when /opt/fabrik isn't present (e.g. on a VPS).
        results.append(
            run_optional_check(
                "scripts/enforcement/check_synced_unmodified.py",
                "Fabrik-Synced Files Unmodified",
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
        # Hooks-index freshness (hub-only; projects self-skip inside the check):
        # every live hook must appear in docs/workstation/hooks-index.md.
        results.append(
            run_optional_check("scripts/enforcement/check_hooks_index.py", "Hooks Index Fresh")
        )
        # Sync-trigger coverage: a manifest surface whose edits fire NO governance-sync
        # ships nothing to the fleet (happened twice on 2026-08-09). Every synced path
        # must trigger, or be declared a deliberate non-trigger.
        results.append(
            run_optional_check(
                "scripts/enforcement/check_sync_trigger_coverage.py", "Sync Trigger Coverage"
            )
        )
        # Docs-truth durability gates (2026-07-20 convergence): links + index are
        # blocking (the tree was converged to zero drift and must stay there);
        # retired-terms is WARN-only — the SCRIPT always exits 0, advisory=True
        # just preserves its stdout.
        results.append(
            run_optional_check(
                "scripts/enforcement/check_doc_links.py",
                "Doc Link Integrity (live tree)",
            )
        )
        results.append(
            run_optional_check(
                "scripts/enforcement/check_doc_index.py",
                "INDEX.md ↔ docs tree drift",
            )
        )
        # ADVISORY (B, 2026-08-16 registration audit). The check is honest in its own source
        # (`return 0  # ALWAYS — WARN-only by contract`) and the hub currently carries 73
        # WARNs, so promoting it would red the hub on its own docs before any project saw
        # it. `warn_only=True` moves that contract into the gate's OUTPUT, where it was
        # previously invisible — `advisory=True` alone kept the text but still printed
        # `[PASS]`, indistinguishable from a check that can bite.
        results.append(
            run_optional_check(
                "scripts/enforcement/check_retired_terms.py",
                "Retired-Tech Tripwire",
                warn_only=True,
            )
        )
        results.append(
            run_optional_check("scripts/enforcement/check_rule_size.py", "Rule File Size Guard")
        )
        # Rule-pack reachability (advisory): a pack's declared `applies_to:` naming a
        # scaffold type its globs cannot reach — an INDEPENDENT signal from
        # select_rules.py's ACTIVE set (which derives from the very globs under test
        # and can never catch this class; see scripts/enforcement/check_pack_reachability.py's
        # module docstring). warn_only=True: 56 packs across ~46 repos with zero packs
        # yet annotated must never turn the fleet gate red; promoting this to blocking
        # is a deliberate operator decision once the corpus is clean.
        results.append(
            run_optional_check(
                "scripts/enforcement/check_pack_reachability.py",
                "Rule-pack reachability",
                warn_only=True,
            )
        )
        results.append(
            run_optional_check(
                "scripts/enforcement/check_opencode_json.py", "opencode.json (Kilo-Safe Rules)"
            )
        )
        # (INDEX.md touch-on-change is now folded into "Doc Sync Matrix"; the
        # auto-generated INDEX tree-map stays in docs_updater --check, tier 3.)
        results.append(
            run_optional_check(
                "scripts/enforcement/check_test_proposal.py", "Behavior Contract Proposal"
            )
        )
        results.append(
            run_optional_check(
                "scripts/enforcement/check_plan_tickets.py", "Plan-Set Contract (Spine+Tickets)"
            )
        )
        # Stage-skip artifact gate (Tier-2 only, unlike check_convergence.py which runs
        # every tier): a plan NEWLY claiming CONVERGED whose cited design spec is still
        # DRAFT (stage 1->3 skip), and a docs/data-contract.md or docs/ui-design.md
        # NEWLY claiming Status: FROZEN without the header fields + freeze-rule
        # sentence its own freezing command mandates. See
        # scripts/enforcement/check_stage_artifacts.py (module docstring records why
        # this is NOT the plan ticket's certification-report pre-analysis candidate --
        # that gap is already covered by check_review_coverage.py).
        results.append(
            run_optional_check(
                "scripts/enforcement/check_stage_artifacts.py",
                "Stage-Skip Artifact Gate (spec freshness + FROZEN header shape)",
            )
        )
        results.append(
            run_optional_check(
                "scripts/enforcement/check_readme_md.py", "README.md (Primary Entry Point)"
            )
        )
        # (CONFIGURATION.md ← .env.example and QUICKSTART ← API routes are now
        # folded into "Doc Sync Matrix".)
        # UNWIRED — check_env_updates.py (was ".env Updates (Secrets)", a display name it
        # SHARED with the blocking check_env_vars.py row above; two rows, one label).
        # Measured 2026-08-16: it compares `.env.example` against `.env`, and `.env` is
        # gitignored, machine-local and secret-bearing — it is not part of the change under
        # gate and legitimately omits every optional var, so the rule can never be a
        # property of the commit. 482 divergences across 17 of 44 /opt repos (seo=87,
        # trade-intelligence=56, brand-identiy-creator=56) confirm the convention was never
        # adopted; making it visible would have added 87 warning lines to one repo's every
        # gate run. Its second rule (".env.example updated but no .env exists") is a
        # workstation nudge, not a repo invariant. Runnable by hand:
        # `python scripts/enforcement/check_env_updates.py`.
        #
        # UNWIRED — check_test_coverage.py (was "Test Coverage (New Code)").
        # Measured 2026-08-16: 2063 findings across 20 of 44 /opt repos, 295 in the hub.
        # Its rule — every new public `def`/`class` under `src/` must have a test — is the
        # rule this codebase explicitly REJECTS: the Behavior Contract is "one test per
        # user-observable behavior, skip trivia … NOT 100%-coverage dogma". Its evidence is
        # a name-substring proxy too (`function_tested` greps `<name>(` anywhere under
        # `tests/`, so any collision with a test helper reads as covered), and it only sees
        # `src/`, which the hub's own logic — `scripts/`, `libs/` — never enters. The real
        # coverage gate is check_test_proposal + the phase-boundary review. Runnable by
        # hand: `python scripts/enforcement/check_test_coverage.py`.
        #
        # ADVISORY (B, 2026-08-16 registration audit) — .env.example completeness.
        # A real Doc Sync Matrix rule ("New env var → .env.example + CONFIGURATION.md") that
        # NO other check covers: check_doc_sync only fires .env.example → CONFIGURATION.md,
        # never code → .env.example. But 44 of 44 /opt repos already violate it — 2223
        # undeclared vars, 240 in the hub — so a promotion is a fleet incident, not a gate.
        # Decomposed by pattern before deciding: `os.getenv` 1720, `os.environ.get` 535,
        # `os.environ[...]` 88, `settings.X` 1 — the finding is genuine reads, not a loose
        # regex. It was registered without `advisory`, so its stdout was DISCARDED on exit
        # 0: a check that could neither fail nor speak.
        results.append(
            run_optional_check(
                "scripts/enforcement/check_env_example.py",
                ".env.example Completeness",
                warn_only=True,
            )
        )
        # UNWIRED — check_compose_services.py (was "Compose Services Docs").
        # Measured 2026-08-16, and unwired for its LOGIC, not its volume (30 findings across
        # 19 of 44 repos). Two independent structural faults: (1) `get_new_services` only
        # enters its services block when `services:` itself is an ADDED diff line, so it
        # sees a brand-new compose file and is BLIND to the actual case — a service added to
        # an existing compose, where `services:` is context; (2) `service_documented` is a
        # case-insensitive substring over 4 docs, so `app`/`api`/`db`/`web` match any README
        # trivially. The surviving intent (compose changed → SERVICES.md + OPERATIONS.md) is
        # already carried by check_doc_sync (scripts/enforcement/check_doc_sync.py:324-328).
        # Runnable by hand: `python scripts/enforcement/check_compose_services.py`.
        results.append(
            run_optional_check("scripts/enforcement/check_user_guide.py", "User Guide Presence")
        )
        # UNWIRED — check_reusable_modules.py (was "Reusable Module Tagging").
        # Measured 2026-08-16: 0 findings fleet-wide, because the UNIVERSE is empty — not
        # one of the 44 /opt repos has a `src/utils/` or `src/lib/` directory, the only two
        # the check looks in, so `main()` returns at its `if not modules` guard in every
        # repo on the box. The `[reusable]` INDEX.md tag it enforces IS a live convention
        # (apidoccreator, site-provisioner, trade-intelligence, fabrik-citation-verifier all
        # use it) — on `src/services/`, `src/api/`, `src/lib/*.ts`. It is the hardcoded
        # two-directory layout that was never adopted, the same shape as check_watchdog
        # above. Runnable by hand: `python scripts/enforcement/check_reusable_modules.py`.
        # Behavior-Contract test accompaniment — WARN when an ACTIVE plan-execution window
        # (lock baseline..HEAD) declares Given rows and touched source with ZERO test changes.
        # Whole-window by design; per-row coverage stays the phase-boundary review's. Always
        # exits 0. Tier-2-ONLY (a review finding moved it here — the first registration landed
        # in the shared tier-(1,2) block, polluting --lean and falsifying the doc's counts).
        results.append(
            run_optional_check(
                "scripts/enforcement/check_phase_tests.py",
                "Phase Tests (plan-window)",
                # No `return 1` exists in this script — both the warned and the fail-soft
                # branch return 0. Declared, so the row prints [ADVISORY] rather than a
                # [PASS] it could never have lost.
                warn_only=True,
            )
        )
        # Command-corpus integrity — the /fabrik-* commands must reference things that
        # EXIST (web-tool names against the live WEB_TOOL_NAMES, chain targets, script
        # paths, trailer models). BLOCKING: each is a true/false fact with no tolerance
        # band. Founding case 2026-08-16 — four commands passed PROVIDER names as
        # `web_tools`, so the loop advertised zero tools and every "grounded" research
        # fan-out ran blind while still returning confident prose. Nothing caught it.
        results.append(
            run_optional_check(
                "scripts/enforcement/check_command_corpus.py",
                "Command Corpus (references resolve — BLOCKING)",
            )
        )
        # Ticket breadth — WARN when a ticket in a CHANGED plan set exposes many
        # independent risk classes (top-level Touches areas + Behavior-Contract rows +
        # a code/governance-surface mix). Measured basis: review rounds track risk
        # classes, not line count (docs/reference/ticket-breadth.md). ADVISORY by
        # design — a heuristic that hard-failed would block planning on a guess, and
        # a blocked plan is worse than a broad one; it always exits 0 here (--strict
        # is the opt-in author-side ratchet, never wired to the gate). Tier-2-ONLY,
        # matching check_phase_tests — --lean's count must not move.
        # advisory=True preserves the warning text on exit 0; without it
        # run_optional_check discards stdout and the whole check would be invisible.
        # A MISSING script is NOT silently green: run_optional_check returns the
        # "⚠ check not present, skipping" message that --json collects into warnings.
        results.append(
            run_optional_check(
                "scripts/enforcement/check_ticket_breadth.py",
                "Ticket Breadth (plan sets)",
                # `--strict` is its only non-zero exit (check_ticket_breadth.py:516) and the
                # gate deliberately never passes it, so this ROW cannot fail even though the
                # check can. Declared here so the two are not confused.
                warn_only=True,
            )
        )

    # ── Tier 3: Full repo health (systemic-only) ──
    if tier == 3:
        # Systemic / infra-focused checks only. Showstoppers (secrets, schema sync, etc.)
        # are handled in Tier 1 / Tier 2 and are not repeated here.
        # ── ANTI-VACUITY NOTE (2026-08-16 liveness audit) ──────────────────────────
        # Six checks used to be registered here that could not fail: they defined
        # only `check_file()`, with no `__main__` and no top-level call, so running
        # them exited 0 with EMPTY output. Six green rows, zero assertions. Their
        # logic was reachable only through `validate_conventions.py`'s Cascade
        # `post_write_code` path, and Cascade is dormant.
        #
        # All six now have a real `__main__` (see `_check_runner.py`) and were RUN
        # against this repo and all 45 /opt repos before being wired. Two earned
        # their place; four are UNWIRED below with the measurement that retired them,
        # because an honest missing check beats a fake green one. The unwired four
        # keep their `__main__` and stay runnable by hand as diagnostics.
        results.append(
            run_optional_check(
                "scripts/enforcement/check_docker.py",
                "Docker (amd64 platform, No-Alpine builds, HEALTHCHECK)",
                # ACTIVATED. Fails on ERROR only. What it found on activation:
                # 5 of 45 fleet repos ship `platform: linux/arm64` in a production
                # compose deployed to an x86_64 VPS (candle, image-generation,
                # llm_batch_processor, trading-core, web-scraper) — a true defect
                # class that was invisible for as long as the check was vacuous.
                # Compose `image: *-alpine` was demoted ERROR→WARN in the check: the
                # No-Alpine invariant targets *built* images (musl), and
                # `redis:7-alpine`/`postgres:16-alpine` are vendor images running in
                # production on vps1. `advisory` keeps the WARN text visible on a pass.
                advisory=True,
            )
        )
        # UNWIRED — check_ports.py ("Port Registration (PORTS.md)").
        # Activated and measured 2026-08-16: 0 ERRORs possible (every finding is WARN,
        # so it could never fail), and 59 WARNs fleet-wide are dominated by two
        # structurally wrong rules. (1) The per-technology range rule keys on the
        # FILE's suffix, not the service's technology — it flags `port 3000` inside a
        # Python test and inside `scaffold.py` (which legitimately emits 3000 for
        # frontend scaffolds) as "outside Python services range". (2) The PORTS.md
        # registration rule cannot tell a service's own listening port from a CLIENT
        # connection port, so `5432` in a Postgres test reads as an unregistered port.
        # Fixing this needs a service-port model the checker does not have. Runnable
        # by hand: `python scripts/enforcement/check_ports.py`.
        results.append(
            run_optional_check(
                "scripts/enforcement/check_env_contract.py",
                ".env Contract Sync",
                module="scripts.enforcement.check_env_contract",
                # ACTIVATED. Fails on ERROR (a compose-required var missing from an
                # existing `.env.example`); doc-coverage findings stay WARN. Two
                # false-positive classes were fixed in the check first, both measured:
                # a missing `.env.example` used to make EVERY compose var an error
                # (13 in the hub alone, all from `infra/vps1/*` deploy units), and
                # YAML COMMENTS were parsed as references, so the scaffolder's
                # template boilerplate `${VAR:?}` made 17 of 45 repos "require" a
                # variable named VAR. After both fixes the fleet blast radius is
                # 2 of 45 repos / 12 errors, and the hub's single error was a real
                # defect (apps/example-api referenced ${POSTGRES_PASSWORD} without
                # declaring it), fixed in this same change.
                advisory=True,
            )
        )
        # UNWIRED — check_deps_sync.py ("Dependencies Sync").
        # Activated and measured 2026-08-16: 0 ERRORs possible, and 202 WARNs
        # fleet-wide. It compares requirements.txt against pyproject's
        # `project.dependencies` ONLY — it has no notion of optional-dependency
        # groups, dev extras, or pinned transitives, so a pip-compile-style
        # requirements.txt diverges by construction. The signal is real but the
        # model is too coarse to gate on. Runnable by hand:
        # `python -m scripts.enforcement.check_deps_sync`.
        # (check_docs.py removed — it was hardcoded to src/fabrik/ and dead in every
        # scaffolded project; "new module → doc" intent is covered by the Doc Sync
        # Matrix + INDEX.)
        results.append(
            run_optional_check(
                "scripts/enforcement/check_doc_sprawl.py",
                "Documentation Sprawl",
                # ACTIVATED 2026-08-15 (spec 2026-08-14-doc-sprawl-activation-design): the
                # check was inert since ≤2026-08-04, then WARN-only while the fleet was
                # cleaned. Fleet state at activation: 2 blocking files in ONE repo, and that
                # repo is already RED on check_structure for the identical files, so this adds
                # no new burden anywhere. Reverting = drop this one argument.
                "--strict",
                # advisory: keep the check's stdout on exit 0 — in WARN mode the report IS
                # the product, and run_optional_check discards it otherwise (F5)
                advisory=True,
            )
        )
        # UNWIRED — check_watchdog.py ("Watchdog Scripts").
        # Activated and measured 2026-08-16: 0 ERRORs possible, 62 WARNs fleet-wide,
        # 26 in the hub alone. It demands a per-project `scripts/watchdog.*` beside
        # every compose file — a scaffold-era convention that was never adopted and
        # is not how watchdogging actually works here (the real watchdog is the
        # box-level sidecar under `scripts/sysadmin/`, not a file per deploy unit).
        # Every infra compose in the repo "violates" it. Obsolete, not under-enforced.
        # Runnable by hand: `python scripts/enforcement/check_watchdog.py`.
        #
        # UNWIRED — check_health.py ("Health Endpoint Validation").
        # Activated and measured 2026-08-16: 0 ERRORs possible, 21 WARNs fleet-wide.
        # Its valuable rule ("health endpoint may not test dependencies") cannot tell
        # a service that HAS no dependencies from one that skips probing them — the
        # hub's only hit is `templates/mobile-app/server/.../health.py`, where the
        # module docstring explains that the project ships `needs_database: false`
        # and `{"status": "ok"}` IS the complete health signal. Its other rule fires
        # on repo layout (`tests/test_health.py` absent), not on health correctness.
        # The CLAUDE.md "health endpoint tests real deps" invariant stays enforced by
        # review, not by this heuristic. Runnable by hand:
        # `python scripts/enforcement/check_health.py`.
        results.append(
            run_optional_check(
                "scripts/enforcement/check_duplicates.py",
                "Duplicate Detection",
            )
        )
        results.append(
            run_optional_check("scripts/docs_updater.py", "Documentation Drift", "--check")
        )
        results.append(
            run_optional_check(
                "scripts/enforcement/check_vps_docs.py",
                "VPS Docs Freshness",
                module="scripts.enforcement.check_vps_docs",
                # Every finding this check can construct is Severity.WARN, yet its
                # `__main__` used to exit 1 on ANY finding — a warning-level condition
                # redding a blocking gate row (it is red on the hub right now purely
                # because two operations docs have not been regenerated). The exit code now
                # follows the severity, `--strict` is the activation switch, and the row is
                # declared for what it is. Promotion is a matter of the check growing an
                # ERROR severity, not of the gate re-reading a WARN as a failure.
                warn_only=True,
            )
        )
        validate_conv = PROJECT_ROOT / "scripts/enforcement/validate_conventions.py"
        if validate_conv.exists():
            code, out = run_cmd(
                # --git-diff is REQUIRED: without it (and no file args) the
                # validator has nothing to check and silently passes — the whole
                # tier-3 "Fabrik Convention Validator" was a no-op. Bound to the
                # changed-file set so it only gates new changes.
                [PYTHON, "-m", "scripts.enforcement.validate_conventions", "--strict", "--git-diff"]
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

    # transdoc finding 1.4 (2026-08-23): a project CANNOT add a check to its own
    # completion gate. The battery above is a hardcoded list of scripts/enforcement/
    # paths, and that directory is BOTH fleet-synced AND gitignored in every project —
    # so a project-specific invariant (their RLS rule) could only live in pre-commit,
    # which `--no-verify` bypasses and which this gate's own doc-sync failure message
    # suggests bypassing. Any executable `scripts/checks/check_*.py` in the PROJECT now
    # runs after the hub battery. Deliberately a separate directory from the synced
    # `scripts/enforcement/`: a project owns `scripts/checks/`, so nothing here can be
    # clobbered by the next sync, and the hub's own list stays the hub's.
    for local_check in sorted((PROJECT_ROOT / "scripts" / "checks").glob("check_*.py")):
        results.append(
            run_optional_check(
                f"scripts/checks/{local_check.name}",
                f"project check: {local_check.stem}",
            )
        )

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
        "agents-fabrik.md",  # canonical agents doc (synced 2026-07-19)
        "agents-fabrik-core.md",  # @import-ed platform core (synced 2026-07-19)
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


def get_staged_files() -> set[str]:
    """Paths currently in the index (staged).

    Snapshotted at gate start so auto-stage can re-stage ONLY the agent's own
    files (picking up gate autofixes) without sweeping unrelated, concurrently
    edited files into the commit. See stage_changes().
    """
    code, out = run_cmd(["git", "diff", "--name-only", "--cached"])
    if code != 0 or not out:
        return set()
    return {f for f in out.strip().split("\n") if f}


def stage_changes(paths: set[str] | None = None) -> tuple[bool, str]:
    """Re-stage files after autofixes.

    Shared-tree safety: ``/opt/fabrik`` is worked by 3 agents + the daily
    pipeline on one ``master``. A blanket ``git add -A`` here would sweep every
    other actor's in-progress files into whoever's gate ran last (the exact
    footgun the agent contracts ban). So by default we re-stage ONLY ``paths``
    — the set that was already staged when the gate started — which captures any
    autofixes the gate applied to the agent's own files and nothing else.

    ``paths=None`` restores the legacy blanket behaviour (``--stage-all``).
    """
    if paths is None:
        code, out = run_cmd(["git", "add", "-A"])
        return code == 0, out
    if not paths:
        return True, ""  # nothing was pre-staged → stage nothing
    # ``-A -- <paths>`` re-stages modifications AND deletions of exactly these files.
    code, out = run_cmd(["git", "add", "-A", "--", *sorted(paths)])
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
        "issues": [{"check": name, **clip_output(output)} for name, output in failed],
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


def _diff_base() -> str | None:
    """Ref to diff HEAD against for 'what this session will publish' — the tracking
    upstream if set, else origin/master|main. None when no remote base exists (fresh
    repo / detached HEAD) → callers fall back to the working tree only.

    Without this, a session that has COMMITTED its work leaves a clean working tree,
    get_changed_files() returns empty, and the gate falls back to whole-tree — which
    reds on Fabrik-synced lines the change never touched and auto-formats a sibling's
    unrelated files (phantom churn). Committed-but-unpushed IS the change.
    """
    for cmd in (
        ["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"],
        ["git", "rev-parse", "--verify", "--quiet", "origin/master"],
        ["git", "rev-parse", "--verify", "--quiet", "origin/main"],
    ):
        code, out = run_cmd(cmd)
        if code == 0 and out.strip():
            return out.strip().splitlines()[0]
    return None


def get_changed_files() -> set[str]:
    """Get set of changed file paths from git.

    The change set = everything this session will PUSH: committed-but-unpushed
    (`base...HEAD`) PLUS the working tree (staged + unstaged-modifications-to-tracked).
    Used to scope the fixers and static checks so the gate never touches or reds a file
    the change didn't touch — the shared-master invariant.

    ⚠️ Untracked-UNSTAGED files are deliberately EXCLUDED (2026-07-18): they cannot be
    pushed, so they are not part of "what this session will push" — and on a shared tree
    they are typically a SIBLING agent's in-progress work, which the gate must neither
    red-flag against this session nor (worse) auto-fix/auto-stage. Authorship = staging:
    `git add` a new file of YOURS to bring it into gate scope (the completion contract
    stages explicit paths anyway, so an authored file is always in scope by gate time).
    Live incident: a sibling's minutes-old untracked scratch red-flagged an unrelated
    session's gate and was one bare run away from being auto-staged into its commit.
    """
    changed: set[str] = set()
    # Committed but not yet pushed (the session's own commits) — see _diff_base.
    base = _diff_base()
    if base:
        code, out = run_cmd(["git", "diff", "--name-only", f"{base}...HEAD"])
        if code == 0 and out:
            changed.update(f for f in out.strip().split("\n") if f)
    # Staged changes (includes staged-NEW files — the authored path for new files)
    code, out = run_cmd(["git", "diff", "--name-only", "--cached"])
    if code == 0 and out:
        changed.update(f for f in out.strip().split("\n") if f)
    # Unstaged changes (modifications to tracked files)
    code, out = run_cmd(["git", "diff", "--name-only"])
    if code == 0 and out:
        changed.update(f for f in out.strip().split("\n") if f)
    return changed


def _warn_untracked_sources(emit: bool = True) -> str | None:
    """Advisory (never fails) about untracked source files outside gate scope.

    Untracked-unstaged files are excluded from the change set (they can't be pushed, and
    on a shared tree they're typically a sibling's WIP the gate must not touch). The
    fail-open corner of that rule: an agent's OWN new file, authored but never `git add`ed,
    would sail through a green gate unscanned and only red in CI after push. This advisory
    makes that corner impossible to miss: if any of these are YOURS, `git add` them and
    re-run the gate; if they're a sibling's, leave them alone.

    Returns the plain-text message (or None). Prints it only when `emit` — in --json mode
    the caller passes emit=False and routes the message into the JSON `warnings` array
    instead (a bare print there would corrupt the JSON stream agents parse).
    """
    code, out = run_cmd(["git", "ls-files", "--others", "--exclude-standard"])
    if code != 0 or not out:
        return None
    src = [
        f
        for f in out.strip().split("\n")
        # The gate's own scannable surface: lint/fix targets (_FIXABLE_TEXT_EXTS) + node/sql sources.
        if f.endswith((".py", ".js", ".ts", ".tsx", ".sql", ".sh", ".md", ".yaml", ".yml", ".json"))
    ]
    if not src:
        return None
    msg = (
        f"⚠ {len(src)} untracked source file(s) NOT in gate scope (unstaged → unscanned): "
        f"{', '.join(src[:6])}{' …' if len(src) > 6 else ''} — if yours: `git add` them and "
        f"RE-RUN the gate (they ship unlinted otherwise); if a sibling's: leave them."
    )
    if emit:
        print(f"  {YELLOW}{msg}{RESET}")
    return msg


# File extensions the whitespace/EOF fixers operate on (mirrors the git ls-files
# globs they used before scoping).
_FIXABLE_TEXT_EXTS = (".py", ".md", ".yaml", ".yml", ".json", ".sh")
# Roots ruff lints/formats.
_RUFF_ROOTS = ("scripts/", "src/")
_FABRIK_ROOT = Path("/opt/fabrik")


def _synced_paths() -> set[str]:
    """Fabrik-synced files (repo-relative) this repo must NOT lint or auto-fix.

    They are centrally distributed from /opt/fabrik and the synced-hash check
    (check_synced_unmodified) requires them to match the distributed BYTES exactly —
    so reformatting them to a consumer project's ruff style (which may differ from the
    hub's) rewrites them and self-fails that check, and the project can't legally edit
    them anyway. Empty in the hub (/opt/fabrik): there they ARE the source and get
    linted/formatted like any other file. In a consumer, read from the per-project
    lock (.fabrik/synced.lock) — the same source check_synced_unmodified trusts. Any
    failure → empty (fail-open: lint normally rather than silently skip everything).
    """
    try:
        if PROJECT_ROOT.resolve() == _FABRIK_ROOT.resolve():
            return set()
        lock = PROJECT_ROOT / ".fabrik" / "synced.lock"
        if not lock.exists():
            return set()
        import json

        return set(json.loads(lock.read_text()).keys())
    except Exception:
        return set()


def _changed_python(changed_files: set[str]) -> list[str]:
    """Changed .py under the ruff roots that exist on disk and are NOT Fabrik-synced."""
    synced = _synced_paths()
    return sorted(
        f
        for f in changed_files
        if f.endswith(".py")
        and f.startswith(_RUFF_ROOTS)
        and f not in synced
        and (PROJECT_ROOT / f).is_file()
    )


def _changed_text(changed_files: set[str]) -> list[str]:
    """Changed fixable text files that exist on disk and are NOT Fabrik-synced."""
    synced = _synced_paths()
    return sorted(
        f
        for f in changed_files
        if f.endswith(_FIXABLE_TEXT_EXTS) and f not in synced and (PROJECT_ROOT / f).is_file()
    )


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
        "--stage-all",
        action="store_true",
        help=(
            "Legacy blanket `git add -A` on success. UNSAFE on the shared "
            "/opt/fabrik tree (sweeps concurrent actors' files). Default re-stages "
            "only files that were already staged when the gate started."
        ),
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
        results = run_formatting_fixes(tier=tier, changed_files=changed_files)
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
    results = run_consistency_checks(tier=tier, changed_files=changed_files, check_only=check_only)
    all_results.extend(results)
    if not json_mode:
        for name, passed, out in results:
            print_step(name, passed, out)

    return all_results


def main() -> int:
    """Run the final gate checks with iteration loop."""
    args = parse_args()

    # transdoc 1.2: fail SETUP loudly instead of returning a tree verdict the
    # interpreter chose. A missing toolchain is not a dirty tree, and reporting it
    # as one teaches an agent to shop for the invocation that passes.
    missing = _toolchain_missing(PYTHON)
    if missing:
        import json  # local, matching this file's existing idiom at 3 other sites

        payload = {
            "status": "setup-error",
            "error": f"the selected interpreter ({PYTHON}) cannot import {missing!r}",
            "fix": f"install {missing} into that interpreter, or invoke the gate with one that has it",
            "note": "this is NOT a verdict on your tree — the gate refused to guess",
        }
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            print(f"{BOLD}{RED}SETUP ERROR{RESET} — {payload['error']}")
            print(f"  {payload['fix']}")
            print(f"  {payload['note']}")
        return 2

    # Determine tier
    if args.lean:
        tier = 1
    elif args.systemic:
        tier = 3
    else:
        tier = 2

    # Get changed files for diff-sensing
    changed_files = get_changed_files()
    untracked_warn = _warn_untracked_sources(emit=not args.json)

    # Snapshot the index NOW, before any fixers run, so auto-stage at the end
    # re-stages only the agent's own (already-staged) files — never a blanket
    # `git add -A` that would sweep a concurrent actor's work into this commit.
    staged_at_start = get_staged_files()

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
            # Default: re-stage only the files staged when the gate started
            # (shared-tree safety). --stage-all opts back into blanket `git add -A`.
            scope = None if args.stage_all else staged_at_start
            if not args.json:
                if args.stage_all:
                    print(f"\n{BLUE}Auto-staging ALL modified files (--stage-all)...{RESET}")
                elif staged_at_start:
                    print(
                        f"\n{BLUE}Re-staging {len(staged_at_start)} pre-staged "
                        f"file(s) (shared-tree safe)...{RESET}"
                    )
                else:
                    print(
                        f"\n{YELLOW}Nothing was pre-staged — staging nothing. "
                        f"Stage your files explicitly: git add <file>…{RESET}"
                    )
            ok, out = stage_changes(scope)
            if ok and not args.json and (args.stage_all or staged_at_start):
                print(f"  {GREEN}✓ Changes staged{RESET}")
            elif not ok and not args.json:
                print(f"  {RED}✗ Failed to stage: {out}{RESET}")

    # Kaizen sensor (T04) — OBSERVATION ONLY: ONE gate_run per invocation, at the single
    # point where every check has assembled and nothing downstream can still change one.
    # It reads `all_results`; it never writes it, and emit() never raises (fail-open).
    if kaizen_events:
        _mode = {k: bool(getattr(args, k)) for k in ("check", "lean", "systemic", "json")}
        _adv = WARN_ONLY_CHECKS  # rows that cannot fail — labelled, never counted as pass
        _checks = [
            {"name": n, "outcome": "fail" if not ok else "advisory" if n in _adv else "pass"}
            for n, ok, _ in all_results
        ]
        _status = "success" if not failed else "failure"
        with contextlib.redirect_stderr(io.StringIO()):  # not one byte on the gate's stderr
            kaizen_events.emit(
                "gate_run",
                tier=tier,
                mode=_mode,
                status=_status,
                checks=_checks,
                probe_timeout_s=_KAIZEN_PROBE_TIMEOUT_S,
            )

    # JSON output mode
    if args.json:
        import json

        # Rows that CANNOT fail, named. `passed` counts them like any other green row, so
        # without this an operator reading `"passed": 21` cannot tell how many of those 21
        # were ever at risk. Registered warn-only rows carry their whole product in stdout,
        # so it ships here too (the `warnings` list below only collects ⚠-prefixed output).
        advisory_rows = [
            {"check": name, **clip_output(output)}
            for name, ok, output in all_results
            if ok and name in WARN_ONLY_CHECKS
        ]
        result = {
            "status": "success" if not failed else "failure",
            "tier": tier,
            "passed": passed_count,
            "failed": len(failed),
            "advisory": advisory_rows,
            "blocking": passed_count - len(advisory_rows),
            "failures": [
                {"check": name, **clip_output(output)}  # tail-preserving, marker in-band
                for name, _, output in failed
            ],
            # Advisory warnings a check OPTS INTO by prefixing with ⚠ — surfaced in --json (the
            # mode CLAUDE.md mandates for schema gates), where passed-check output was otherwise
            # invisible. The ⚠ gate keeps benign chatter ("✅ …", "(bandit not installed,
            # skipping)") out; a check emitting a plain "WARNING:" (e.g. check_reusable_modules)
            # stays human-mode-only by design.
            "warnings": [
                {"check": name, **clip_output(output)}
                for name, ok, output in all_results
                if ok and output and output.lstrip().startswith("⚠")
            ]
            + (
                [{"check": "untracked sources (advisory)", **clip_output(untracked_warn)}]
                if untracked_warn
                else []
            ),
        }
        print(json.dumps(result, indent=2))
        return 0 if not failed else 1

    # Human-readable output mode
    advisory_names = [name for name, ok, _ in all_results if ok and name in WARN_ONLY_CHECKS]
    print_header("SUMMARY")
    print(f"  {GREEN}Passed:{RESET} {passed_count} ({passed_count - len(advisory_names)} blocking)")
    print(f"  {RED}Failed:{RESET} {len(failed)}")
    if advisory_names:
        print(
            f"  {YELLOW}Advisory:{RESET} {len(advisory_names)} "
            f"(non-blocking — these rows can never go red)"
        )
        for name in advisory_names:
            print(f"    - {name}")

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
