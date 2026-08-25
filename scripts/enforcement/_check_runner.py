#!/usr/bin/env python3
# AFTER-EDIT: scripts/final_gate.py | tests/test_check_runner_activation.py
"""Shared repo-walking `__main__` for the per-file enforcement checks.

WHY THIS EXISTS (2026-08-16 liveness audit). Six Tier-3 checks — `check_docker`,
`check_ports`, `check_env_contract`, `check_deps_sync`, `check_watchdog`,
`check_health` — defined only a `check_file(Path) -> list[CheckResult]` function.
They had no `__main__` and no top-level call, so `python <path>` (and `python -m
<module>`) exited 0 with empty output. `final_gate.py` registered all six and
counted six PASSes that asserted **nothing**. Their logic was live only through
`validate_conventions.py`'s Cascade `post_write_code` path, and Cascade is dormant.

A check that cannot fail is worse than a missing one: it buys the same green with
none of the coverage. This module gives each of them a real entry point — walk the
repo, run the check's own `check_file` over every tracked candidate, print what it
found, and exit non-zero on genuine violations.

Severity contract (deliberate, and the reason this is not just `sys.exit(len(results))`):

* ``ERROR`` findings fail the run (exit 1). These are defects — an Alpine base image,
  a compose var absent from `.env.example`.
* ``WARN`` findings are reported but do **not** fail, because these checks are
  fleet-synced to ~46 repos and a stylistic finding that suddenly reds every project
  is its own incident.
* ``--strict`` promotes WARN to failing. That is the activation switch: once a
  finding class is measured clean fleet-wide, the gate registration adds `--strict`
  (same pattern `check_doc_sprawl.py` used for its 2026-08-15 activation).

The runner never imports `Severity` — it reads `result.severity.value` as a string,
so it works identically under `python <path>` and `python -m scripts.enforcement.<mod>`.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Callable, Iterable, Iterator
from pathlib import Path
from typing import Any

# Directories never worth walking. `.claude/worktrees` matters most: the hub keeps
# per-agent git worktrees there, and walking them would scan the whole repo N+1
# times and report every finding N+1 times.
EXCLUDE_DIRS = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        ".venv",
        "venv",
        "env",
        "node_modules",
        "__pycache__",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".tox",
        "site-packages",
        "dist",
        "build",
        ".next",
        ".nuxt",
        "vendor",
        "backups",
        "mutants",
        "worktrees",
        ".terraform",
        "htmlcov",
        ".eggs",
    }
)

# Cap per-severity output. A first activation against an unmeasured fleet can find
# hundreds; an unbounded dump buries the gate's own verdict.
MAX_SHOWN = 40


def iter_repo_files(root: Path) -> Iterator[Path]:
    """Yield every candidate file under `root`, skipping vendored/generated trees.

    Each check self-filters by name/suffix inside its own `check_file`, so the
    walker stays deliberately dumb — it only prunes directories that can never
    hold project-authored source.
    """
    for dirpath, dirnames, filenames in os.walk(root):
        # Prune in place so os.walk never descends. Also drop dot-dirs wholesale
        # except the handful projects genuinely keep source in.
        dirnames[:] = [
            d
            for d in dirnames
            if d not in EXCLUDE_DIRS and not (d.startswith(".") and d not in {".github"})
        ]
        base = Path(dirpath)
        for fn in filenames:
            yield base / fn


def _format(result: Any) -> str:
    loc = result.file_path or "?"
    if result.line_number:
        loc = f"{loc}:{result.line_number}"
    line = f"  {loc} — {result.message}"
    if result.fix_hint:
        line += f"\n      fix: {result.fix_hint}"
    return line


def run_as_main(
    check_file: Callable[[Path], Iterable[Any]],
    *,
    check_name: str,
    description: str,
    argv: list[str] | None = None,
) -> int:
    """Walk the repo with `check_file` and return a process exit code.

    Returns 1 when there is at least one ERROR finding (or, under `--strict`, at
    least one finding of any severity); 0 otherwise. Always prints a one-line
    verdict, so a green run is still *evidence* that the check ran — the exact
    thing the vacuous registration could never provide.
    """
    parser = argparse.ArgumentParser(prog=check_name, description=description)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="Repository root to scan (default: cwd)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail on WARN findings too, not just ERROR",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Print only the verdict line, not the individual findings",
    )
    args = parser.parse_args(argv)

    root: Path = args.root.resolve()
    if not root.is_dir():
        print(f"{check_name}: --root {root} is not a directory")
        return 2

    # Some checks resolve project-level companions through the CURRENT DIRECTORY rather
    # than the scanned path — `check_ports` reads `Path.cwd() / "PORTS.md"`. Without this,
    # `--root /opt/other` would scan one repo's files against THIS repo's PORTS.md and
    # report confident nonsense. Restored in the `finally` below: this is normally a
    # process entry point, but `run_as_main` is importable and must not strand a caller
    # (or a second check in the same process) in someone else's directory.
    previous_cwd = Path.cwd()
    os.chdir(root)
    try:
        return _scan(check_file, check_name, root, args)
    finally:
        os.chdir(previous_cwd)


def _scan(
    check_file: Callable[[Path], Iterable[Any]],
    check_name: str,
    root: Path,
    args: argparse.Namespace,
) -> int:
    """The walk itself. Split out so `run_as_main` can guarantee cwd restoration."""

    errors: list[Any] = []
    warns: list[Any] = []
    # Several trigger files can resolve to the SAME project-level finding — e.g.
    # `check_env_contract` fires for `.env.example`, `compose.yaml` AND
    # `CONFIGURATION.md`, each re-deriving the same project root and re-reporting
    # every var. Dedup on the finding's identity, not on the file that triggered it,
    # so a count is a count of problems rather than of entry points.
    seen: set[tuple[str, str, str | None, int | None]] = set()
    # DENOMINATOR. `0 error(s), 0 warning(s)` cannot distinguish "walked the tree and found
    # nothing" from "walked nothing" — and the second is how a check that has quietly stopped
    # working passes for one that is healthy. Measured 2026-08-25 across all 59 checks in a
    # subject-free repo: 17 emitted an affirmative success claim and exactly ONE stated how much it
    # had looked at. Say WALKED, not "examined": this runner hands every repo file to check_file
    # and each check's own dispatch decides what applies, so the walk size is what this layer can
    # honestly attest. See docs/reference/enforcement-battery-audit.md.
    walked = 0
    for path in iter_repo_files(root):
        walked += 1
        try:
            found = check_file(path)
        except Exception as exc:  # noqa: BLE001 — one unreadable file must never
            # abort the whole sweep; a check that dies halfway is a vacuous check
            # wearing a different mask.
            print(f"{check_name}: skipped {path}: {type(exc).__name__}: {exc}")
            continue
        for result in found or ():
            severity = getattr(result.severity, "value", str(result.severity))
            identity = (severity, result.message, result.file_path, result.line_number)
            if identity in seen:
                continue
            seen.add(identity)
            if severity == "error":
                errors.append(result)
            elif severity == "warn":
                warns.append(result)

    if not args.quiet:
        for label, bucket in (("ERROR", errors), ("WARN", warns)):
            if not bucket:
                continue
            print(f"{check_name}: {len(bucket)} {label} finding(s)")
            for result in bucket[:MAX_SHOWN]:
                print(_format(result))
            if len(bucket) > MAX_SHOWN:
                print(f"  … {len(bucket) - MAX_SHOWN} more {label} finding(s) not shown")

    failing = bool(errors) or (args.strict and bool(warns))
    verdict = "FAIL" if failing else "PASS"
    scope = "errors+warns" if args.strict else "errors"
    print(
        f"{verdict}: {check_name} — {len(errors)} error(s), {len(warns)} warning(s)"
        f" across {walked} file(s) walked [failing on: {scope}]"
    )
    return 1 if failing else 0


def main_for(
    check_file: Callable[[Path], Iterable[Any]], *, check_name: str, description: str
) -> None:
    """Convenience wrapper: run and `sys.exit` with the resulting code."""
    sys.exit(run_as_main(check_file, check_name=check_name, description=description))
