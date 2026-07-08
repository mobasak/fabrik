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
import subprocess
import sys
from pathlib import Path


def changed_python(base: str | None = None) -> list[str]:
    """Committed changed ``.py`` (applied code) vs the merge-base with ``origin/master`` — excludes tests,
    deleted files, and the canonical-owned vendored ``libs/``. Never the dirty worktree."""
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
    """Surviving-mutant count from ``mutmut results`` output (tolerant of format drift): prefer an
    explicit ``N survived`` summary, else count survived-marked mutant lines."""
    m = re.search(r"(\d+)\s+survived", results_text, re.IGNORECASE)
    if m:
        return int(m.group(1))
    return len(re.findall(r"^\s*\S+.*\bsurvived\b", results_text, re.IGNORECASE | re.MULTILINE))


def main() -> int:
    if shutil.which("mutmut") is None:
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
    print(
        f"MUTATION (advisory): running mutmut (incremental, diff-scoped) over {len(files)} changed file(s)…"
    )
    subprocess.run(["mutmut", "run"], check=False)  # incremental → re-tests only changed functions
    res = subprocess.run(["mutmut", "results"], capture_output=True, text=True, check=False).stdout
    survivors = parse_survivors(res)
    if survivors:
        print(
            f"MUTATION (advisory): {survivors} surviving mutant(s) — a change to the code the new tests "
            "cover did NOT fail any test. Strengthen the assertions (or mark an equivalent mutant). "
            "`mutmut browse` to inspect."
        )
    else:
        print("MUTATION (advisory): no surviving mutants in the changed code — tests kill their mutations.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
