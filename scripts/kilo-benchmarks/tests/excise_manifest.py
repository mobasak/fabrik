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
import re
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
    "rank_task_subagents.py":           "wsl_startup_hook.sh:184 (retained boot hook)",
    "check_daily_refresh_freshness.py": "wsl_startup_hook.sh:188 + daily_refresh.sh:163",
    "pipeline_alert.sh":                "wsl_startup_hook.sh:112/185/187 — the operator's alert path",
    "autocommit_pipeline_outputs.sh":   "wsl_startup_hook.sh:195",
    "tests/capture_golden.py":          "wsl_startup_hook.sh:186 + daily_refresh.sh — the contract oracle",
    # Found by this script's OWN boundary scan after the excise had already taken it:
    # scripts/kilo_docs_enforcer.py:66-70 needs it and exits 2 without it. That script is
    # fleet-synced CORE_SCRIPTS on 47 project copies, and nothing inside KB references
    # agent_selector, so the inside-only closure never saw the edge.
    "agent_selector.py":                "scripts/kilo_docs_enforcer.py:66-70 (fleet-synced CORE_SCRIPTS)",
    "tests/test_golden_parity.py":      "the Phase-A oracle; C.3 gate (i) invokes it post-E",
    "tests/test_parallel_run_diff.py":  "the Phase-C window harness",
    # ⚠️ THIS FILE. It deleted ITSELF on the first excise run: it lives under tests/ and was not a
    # root, so it landed in its own DELETE set — and the plan called it "throwaway, deleted with the
    # engine tree". But gate (c) is manifest-aware, so without this tool the post-excise residue
    # check cannot run at all. The thing that computes the delete set has to survive it.
    "tests/excise_manifest.py":         "computes KEEP/DELETE; gate (c) reads it post-excise",
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
    ap.add_argument("--against", metavar="REF",
                    help="verify against files ALREADY deleted since REF — the only form that is not "
                         "a tautology once the excise has run (e.g. --against 73bde59a~1)")
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
        # ⚠️ POST-EXCISE THIS CHECK WAS A TAUTOLOGY, and the claim it backed ("SOUND") was hollow.
        # `closure()` computes `delete = everything - keep` by scanning the CURRENT tree, so once the
        # files are gone they are not in `everything`, cannot be in `delete`, and the
        # "RETAINED depends on DELETED" rule below can never fire. Worse, `_local_deps` only keeps a
        # candidate when `KB/<name>.py` still EXISTS, so a dependency on a deleted module is dropped
        # from `deps` entirely — the edge disappears rather than being flagged.
        #
        # The real question is not "does anything depend on a file I am about to delete" (answerable
        # from the live tree) but "does anything depend on a file I ALREADY deleted" — which is only
        # answerable from git. `--against <ref>` reconstructs the pre-excise file set and checks the
        # retained files' dependencies against it.
        # ⚠️ THE BOUNDARY. The closure only traverses files UNDER scripts/kilo-benchmarks/, so a
        # FABRIK-SIDE consumer of an engine module is invisible to it — the outside-in edges lived only
        # in the hand-written KEEP_ROOTS. That blind spot is what shipped a broken
        # kilo_docs_enforcer.py: it needs agent_selector.py, nothing in KB referenced it, so the graph
        # never saw the edge and the excise took it. It is fleet-synced CORE_SCRIPTS on 47 project
        # copies and it exited 2. Scan the consumers directly.
        #
        # The membership test must be "was this a KB module BEFORE the excise", not "is it missing
        # now" — the naive form flagged every stdlib import in any file that merely mentions
        # kilo-benchmarks (argparse, json, pathlib...), which is noise that gets a check switched off.
        import ast as _a
        was_kb = set()
        if a.against:
            was_kb = {
                line.split("/")[-1]
                for line in subprocess.run(
                    ["git", "ls-tree", "-r", "--name-only", a.against, "--", str(KB.relative_to(FABRIK))],
                    cwd=FABRIK, capture_output=True, text=True).stdout.split()
                if line.endswith((".py", ".sh"))
            }
        for q in list((FABRIK / "scripts").glob("*.py")) + list((FABRIK / "scripts").glob("*.sh")):
            src = q.read_text(errors="replace")
            if "kilo-benchmarks" not in src:
                continue
            named = set(re.findall(r"kilo-benchmarks/([A-Za-z_0-9-]+\.(?:py|sh))", src))
            if q.suffix == ".py":
                try:
                    for node in _a.walk(_a.parse(src)):
                        if isinstance(node, _a.Import):
                            named |= {f"{x.name.split('.')[0]}.py" for x in node.names}
                        elif isinstance(node, _a.ImportFrom) and node.level == 0 and node.module:
                            named.add(f"{node.module.split('.')[0]}.py")
                except SyntaxError:
                    pass
            for n in sorted(named & was_kb):          # only names that really were KB modules
                if not (KB / n).exists():
                    problems.append(f"CONSUMER {q.relative_to(FABRIK)} needs DELETED {n}")
                elif n not in keep:
                    problems.append(f"CONSUMER {q.relative_to(FABRIK)} needs {n}, not in the KEEP set")

        if a.against:
            gone = {
                line[len(f"{KB.relative_to(FABRIK)}/"):]
                for line in subprocess.run(
                    ["git", "diff", "--name-only", "--diff-filter=D", f"{a.against}..HEAD", "--",
                     str(KB.relative_to(FABRIK))],
                    cwd=FABRIK, capture_output=True, text=True).stdout.split()
            }
            print(f"[--against {a.against}] {len(gone)} files were deleted from the engine tree")
            import ast as _ast
            for k in sorted(keep):
                f = KB / k
                if not f.is_file() or f.suffix not in {".py", ".sh"}:
                    continue
                src = f.read_text(errors="replace")
                if f.suffix == ".sh":
                    names = set(_shell_deps(f))
                else:
                    names = set()
                    try:
                        for node in _ast.walk(_ast.parse(src)):
                            if isinstance(node, _ast.Import):
                                names |= {x.name.split(".")[0] for x in node.names}
                            elif isinstance(node, _ast.ImportFrom) and node.level == 0 and node.module:
                                names.add(node.module.split(".")[0])
                    except SyntaxError:
                        pass
                for n in names:
                    for cand in (f"{n}.py", f"{n}/__init__.py", n):
                        if cand in gone:
                            problems.append(f"RETAINED {k} references DELETED {cand}")
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
