#!/usr/bin/env python3
# AFTER-EDIT: docs/development/plans/2026-07-26-plan-1-ai-model-catalog-extraction.md
"""Compute the Phase-E KEEP / DELETE sets from the LIVE import graph, instead of enumerating them.

WHY THIS EXISTS. Ten `/fabrik-plan-review` passes over the extraction plan found 150 defects and did
not converge: passes 4-8 appended findings faster than steps were corrected (~20 defects/pass), and
the pass-9 rewrite that compressed 483 lines to 227 produced ~20 more — the *inverse* failure, losing
steps while keeping their gates. The counts never trended down: 43 → 11 → 30 → 13 → 22.

That is not a review-quality problem. It is the wrong ARTIFACT TYPE. Phase E deletes ~100 files
across two repos with ~50 live cross-references, and **prose cannot hold that invariant** — every
edit to a hand-written KEEP list has ~40 neighbours to reconcile, so each pass fixes its enumerated
set and breaks or strands another. Two findings proved it concretely:

  * The plan retained `rank_task_subagents.py` while deleting `build_task_baselines.py` and
    `derive_cost.py`, which it imports — both behind `try/except`, so post-excise it would exit 0 and
    publish a SILENTLY DEGRADED `TASK_SUBAGENT_SELECTION.md` to 47 project copies.
  * It retained `check_daily_refresh_freshness.py` while deleting the `alerting/` package it needs to
    raise the alarm — the alarm's own dependency.

Neither is visible by reading. Both are one graph traversal away. So the retained set is DERIVED here
and the plan points at this script; the plan states the ROOTS (a judgement) and this computes the
CLOSURE (a fact).

Usage:
    python scripts/kilo-benchmarks/tests/excise_manifest.py            # print KEEP / DELETE
    python scripts/kilo-benchmarks/tests/excise_manifest.py --check    # exit 1 if the sets are unsound
"""

from __future__ import annotations

import argparse
import ast
import json
import subprocess
import sys
from pathlib import Path

FABRIK = Path(__file__).resolve().parents[3]
KB = FABRIK / "scripts" / "kilo-benchmarks"

# ─── The ROOTS: a judgement about what fabrik still needs. Everything else is DERIVED. ───
# Each root is here because a RETAINED caller outside the engine invokes it. The comment is the
# evidence; if the evidence stops being true, the root leaves.
KEEP_ROOTS = {
    "daily_refresh.sh":                 "the shrunk consumer orchestrator + its 0 6 * * * cron",
    "rank_task_subagents.py":           "wsl_startup_hook.sh:232 (retained boot hook)",
    "check_daily_refresh_freshness.py": "wsl_startup_hook.sh:236 + daily_refresh.sh:163",
    "pipeline_alert.sh":                "wsl_startup_hook.sh:130/233/235 — the operator's alert path",
    "autocommit_pipeline_outputs.sh":   "wsl_startup_hook.sh:243",
    "tests/capture_golden.py":          "wsl_startup_hook.sh:234 + daily_refresh.sh — the contract oracle",
    "tests/test_golden_parity.py":      "the Phase-A oracle; C.3 gate (i) invokes it post-E",
    "tests/test_parallel_run_diff.py":  "the Phase-C window harness",
    "classify_ticket.py":               "scripts/kilo_auto_route.py:58 (live Traycer coding router)",
    "db_models.py":                     "scripts/kilo_auto_route.py:59-62",
    "kilo_telemetry.py":                "scripts/kilo_auto_route.py:63-67",
}
# Data files a retained consumer reads. Not reachable through the import graph, so stated.
KEEP_DATA = {
    "kilo_agents.db":            "scripts/generate_kilo_agents.py reads it directly via sqlite3",
    "models_browser.html":       "delivered artifact with a retained fabrik home",
    "claude_p_cost.json":        "scripts/claude_p_cost.py _find() fallback (rule 7)",
    "claude_price_ratios.json":  "scripts/claude_p_cost.py _find() fallback (rule 7)",
    "tests/golden/":             "the frozen contract the three retained tests read",
}


def _local_deps(path: Path) -> set[str]:
    """Engine-local modules this file imports — packages (`alerting/`) included.

    Package dirs are the class a `KB/f"{name}.py"`-only check misses, and `alerting/` is exactly
    that case: the alarm's own dependency.
    """
    try:
        tree = ast.parse(path.read_text(errors="replace"))
    except (SyntaxError, UnicodeDecodeError):
        return set()
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module.split(".")[0])
        elif isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value.endswith(".py"):
            names.add(node.value[:-3])          # importlib.spec_from_file_location("x.py")
    return {n for n in names if (KB / f"{n}.py").exists() or (KB / n / "__init__.py").exists()}


def _shell_deps(path: Path) -> set[str]:
    """Engine files a shell script invokes — `.py` AND `.sh`, at any depth.

    A `([A-Za-z_0-9]+)\\.py`-style pattern misses both `$KB/tests/capture_golden.py` (subdirectory)
    and `pipeline_alert.sh` (extension) — the two the plan calls critical.
    """
    import re
    src = path.read_text(errors="replace")
    return set(re.findall(r"(?:\$\{?KB\}?|kilo-benchmarks)/([A-Za-z_0-9./-]+\.(?:py|sh))", src))


def closure() -> tuple[set[str], set[str]]:
    """(keep, delete) as paths relative to `scripts/kilo-benchmarks/`."""
    keep: set[str] = set()
    todo = list(KEEP_ROOTS)
    while todo:
        rel = todo.pop()
        if rel in keep:
            continue
        keep.add(rel)
        p = KB / rel
        if not p.exists():
            continue
        if p.is_dir():
            # A package root (e.g. `alerting/`): walk its modules, and retain the whole package.
            deps = set()
            for mod in p.rglob("*.py"):
                deps |= _local_deps(mod)
        else:
            deps = _shell_deps(p) if p.suffix == ".sh" else _local_deps(p)
        for d in deps:
            cand = f"{d}.py" if (KB / f"{d}.py").exists() else d
            if (KB / cand).exists() and cand not in keep:
                todo.append(cand)

    everything = {
        str(p.relative_to(KB))
        for p in KB.rglob("*")
        if p.is_file() and not (
            {".venv", "__pycache__", ".lcb-venv", ".microbench_cache", "backups", "cache", "out"}
            & set(p.relative_to(KB).parts)
        )
    }
    expanded = set()
    for k in keep:
        if (KB / k).is_dir():
            expanded |= {str(f.relative_to(KB)) for f in (KB / k).rglob("*") if f.is_file()}
    keep |= expanded
    keep_data = {d for d in KEEP_DATA if (KB / d).exists()}
    keep_data |= {e for e in everything if e.startswith("tests/golden/")}
    return keep | keep_data, everything - (keep | keep_data)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="exit 1 if the computed sets are unsound")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    keep, delete = closure()
    derived = sorted(keep - set(KEEP_ROOTS) - set(KEEP_DATA) - {k for k in keep if k.startswith("tests/golden/")})

    if a.json:
        print(json.dumps({"keep": sorted(keep), "delete": sorted(delete), "derived": derived}, indent=1))
        return 0

    print(f"KEEP    {len(keep)} files  ({len(KEEP_ROOTS)} roots + {len(derived)} derived + data)")
    for r, why in sorted(KEEP_ROOTS.items()):
        print(f"  root     {r:38} {why}")
    for d in derived:
        print(f"  DERIVED  {d:38} (pulled in by a root — NOT hand-listed)")
    print(f"DELETE  {len(delete)} files")

    if a.check:
        problems: list[str] = []
        # ⚠️ ORDERING. `daily_refresh.sh` is a KEEP root, and the closure follows what it INVOKES —
        # so run against today's un-shrunk orchestrator (55 engine steps) it retains 156 files, i.e.
        # most of the engine. That is not a bug in the graph; it is the honest answer to "what does
        # fabrik still need?" while fabrik still runs the engine. **This manifest is only meaningful
        # AFTER D.1 shrinks daily_refresh.sh and wsl_startup_hook.sh.** Running it before and acting
        # on the result would keep the thing Phase E exists to delete. The plan asserted a 16-file
        # remnant; measured against the current tree the closure is 156 — a 10x gap that no prose
        # pass caught, because the number depends on an ordering the prose never stated.
        remaining = subprocess.run(
            ["bash", "-c",
             "grep -vE '^[[:space:]]*#' scripts/kilo-benchmarks/daily_refresh.sh "
             "| grep -hoE '_step \"[a-z_0-9]+\"' | sort -u | wc -l"],
            cwd=FABRIK, capture_output=True, text=True).stdout.strip()
        if remaining.isdigit() and int(remaining) > 6:
            problems.append(
                f"ORDERING: daily_refresh.sh still has {remaining} distinct _step names (allow-list is 6). "
                "Run D.1 FIRST — the KEEP closure follows what the orchestrator invokes, so this "
                "currently retains most of the engine.")
        for r in KEEP_ROOTS:
            if not (KB / r).exists():
                problems.append(f"KEEP root does not exist: {r}")
        # the invariant the plan could not hold by hand
        for k in sorted(keep):
            p = KB / k
            if not p.exists() or (p.is_file() and p.suffix not in {".py", ".sh"}):
                continue
            if p.is_dir():
                deps = set()
                for mod in p.rglob("*.py"):
                    deps |= _local_deps(mod)
            else:
                deps = _shell_deps(p) if p.suffix == ".sh" else _local_deps(p)
            for d in deps:
                cand = f"{d}.py" if (KB / f"{d}.py").exists() else d
                if (KB / cand).exists() and cand in delete:
                    problems.append(f"RETAINED {k} depends on DELETED {cand}")
        if problems:
            print("\nUNSOUND:", file=sys.stderr)
            for pr in problems:
                print(f"  {pr}", file=sys.stderr)
            return 1
        print("\nSOUND: every retained file's engine-local dependencies are also retained.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
