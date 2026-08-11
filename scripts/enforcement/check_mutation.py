#!/usr/bin/env python3
# AFTER-EDIT: docs/CONFIGURATION.md
"""
Advisory diff-scoped mutation-testing runner (mutmut) — the Behavior Contract's substance-mechanical layer.

Coverage proves a line ran; **mutation score** proves a test would FAIL if that line changed — the only
mechanical signal that generated/after-the-fact tests actually catch regressions. Per
`.windsurf/rules/core/45-testing-strategy.md` this is **advisory + diff-scoped, NOT a per-PR blocking gate**
(full mutmut runs take minutes–hours and carry equivalent-mutant noise). So in the per-commit `final_gate`
it is **opt-in**: it runs only when `FABRIK_MUTMUT=1` (nightly / CI / on-demand), mutates only the
**committed** changed Python (applied code — never the dirty worktree), leans on mutmut's incremental mode
for diff-scoping, and **ALWAYS exits 0** (advisory, never blocks).

Run it on changed code:  `FABRIK_MUTMUT=1 python scripts/enforcement/check_mutation.py`
"""

from __future__ import annotations

import os
import re
import shutil
import signal
import subprocess
import sys
from pathlib import Path


def changed_python(base: str | None = None) -> list[str]:
    """Committed changed ``.py`` (applied code) vs the merge-base with ``origin/master`` — excludes tests,
    deleted files, and the canonical-owned vendored ``libs/``. Never the dirty worktree.

    ``FABRIK_MUTMUT_SINCE`` (e.g. ``"7 days ago"`` — the weekly cron sets it) switches the window to
    committed history since that time instead of the merge-base diff."""
    since = os.getenv("FABRIK_MUTMUT_SINCE")
    if since:
        out = subprocess.run(
            [
                "git",
                "log",
                f"--since={since}",
                "--name-only",
                "--pretty=format:",
                "--diff-filter=d",
            ],
            capture_output=True,
            text=True,
        ).stdout
        return sorted(
            {
                f
                for f in out.splitlines()
                if f.endswith(".py") and Path(f).exists() and not f.startswith(("tests/", "libs/"))
            }
        )
    if base is None:
        base = (
            subprocess.run(
                ["git", "merge-base", "HEAD", "origin/master"], capture_output=True, text=True
            ).stdout.strip()
            or "HEAD~1"
        )
    out = subprocess.run(
        ["git", "diff", "--name-only", "--diff-filter=d", base, "HEAD"],
        capture_output=True,
        text=True,
    ).stdout
    return [
        f
        for f in out.splitlines()
        if f.endswith(".py") and Path(f).exists() and not f.startswith(("tests/", "libs/"))
    ]


def parse_survivors(results_text: str) -> int:
    """Surviving-mutant count from ``mutmut results`` output. The REAL mutmut 3.6 format
    (``mutmut/__main__.py`` ``results()``, read from the installed package — review finding:
    the aggregate-only regex was dead code against it) prints one ``    <mutant-id>: survived``
    line per survivor and never an aggregate — count those lines. Aggregate forms
    (`N survived` / `survived: N`) stay as a fallback for other versions. A colon-less
    ``no mutants survived`` matches neither arm — NEVER count mere word occurrences (a false
    advisory alarm); under-reporting is the safe failure mode for an advisory signal."""
    per_line = re.findall(r"(?m)^\s*\S+:\s*survived\s*$", results_text, re.IGNORECASE)
    if per_line:
        return len(per_line)
    m = re.search(r"(\d+)\s+survived|survived[:\s]+(\d+)", results_text, re.IGNORECASE)
    return int(m.group(1) or m.group(2)) if m else 0


def mutmut_bin() -> str | None:
    """Resolve mutmut NEXT TO the running interpreter first, PATH second. The Sunday cron
    pins ``.venv/bin/python`` but inherits cron's bare PATH (no ``.venv/bin``), so a
    ``shutil.which``-only lookup silently skipped every scheduled run (review finding,
    live-reproduced under ``env -i``) — the sibling binary is the deterministic choice,
    the same trap ``final_gate.py``'s absolute ``PYTHON`` reference already avoids."""
    sib = Path(sys.executable).parent / "mutmut"
    if sib.is_file() and os.access(sib, os.X_OK):
        return str(sib)
    return shutil.which("mutmut")


def main() -> int:
    mutmut = mutmut_bin()
    if mutmut is None:
        print("MUTATION (advisory): mutmut not installed — skipping (pip install 'mutmut>=3.6.0').")
        return 0
    if not os.getenv("FABRIK_MUTMUT"):
        print(
            "MUTATION (advisory): skipped in the per-commit gate — mutation testing is diff-scoped + "
            "nightly (45-testing-strategy.md), not per-PR blocking. Run it on changed code with:\n"
            "    FABRIK_MUTMUT=1 python scripts/enforcement/check_mutation.py"
        )
        return 0
    files = changed_python()
    if not files:
        print("MUTATION (advisory): no changed applied Python — nothing to mutate.")
        return 0
    try:
        cap_s = int(os.getenv("FABRIK_MUTMUT_WALL_CAP_S", "1200"))
    except ValueError:
        # A malformed cap must never flip an ALWAYS-exit-0 advisory into a gate failure
        # (review finding, live-reproduced: an uncaught ValueError exits non-zero and
        # run_optional_check marks the check failed regardless of advisory=True).
        print("MUTATION (advisory): malformed FABRIK_MUTMUT_WALL_CAP_S — using default 1200s.")
        cap_s = 1200
    print(
        f"MUTATION (advisory): running mutmut (incremental, diff-scoped) over {len(files)} changed "
        f"file(s), wall cap {cap_s}s… (mutmut 3.x has no --paths-to-mutate CLI; incremental mode is "
        "the diff-scoper — it re-tests only changed functions)"
    )
    # Own process group + group-kill on cap: subprocess.run's timeout kills only the DIRECT
    # child, orphaning mutmut's per-mutant test workers on the shared box (review finding —
    # the cap-heavy-local-jobs class). A group kill reaps the whole tree.
    proc = subprocess.Popen([mutmut, "run"], start_new_session=True)
    try:
        proc.wait(timeout=cap_s)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            try:
                proc.kill()
            except ProcessLookupError:
                pass  # exited inside the race window — already dead IS the goal state,
                # and an uncaught raise here would break the ALWAYS-exit-0 contract
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            pass
        print(
            f"MUTATION (advisory): wall cap {cap_s}s reached — process group reaped, partial "
            "results below (raise FABRIK_MUTMUT_WALL_CAP_S for a fuller run). Still advisory, "
            "still exit 0."
        )
    res = subprocess.run([mutmut, "results"], capture_output=True, text=True, check=False).stdout
    survivors = parse_survivors(res)
    if survivors:
        print(
            f"MUTATION (advisory): {survivors} surviving mutant(s) — a change to the code the new tests "
            "cover did NOT fail any test. Strengthen the assertions (or mark an equivalent mutant). "
            "`mutmut browse` to inspect."
        )
    else:
        print(
            "MUTATION (advisory): no surviving mutants in the changed code — tests kill their mutations."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
