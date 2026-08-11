#!/usr/bin/env python3
# AFTER-EDIT: tests/enforcement/test_phase_tests_gate.py
"""Behavior-Contract test-accompaniment advisory — WARN when a plan-execution window
declares behaviors but has added no tests.

WHOLE-WINDOW by design (plan 2026-08-10-plan-2 Phase C; the per-phase form would require a
phase-boundary mechanism no plan lock carries): the range is the ACTIVE plan lock's
``baseline_commit..HEAD``; the rows are the bulleted ``- **Given**`` rows inside the locked
plan's Behavior-Contract regions — heading form and monolithic bold-label form both scoped
(``GIVEN_ROW_RE`` reused from ``check_plan_tickets`` — never a second regex to drift); the
assertion is the honest one a gate can prove — **if the locked plan declares >=1 Given row AND
the window touched source files, the window must include >=1 test change**. The WARN lists the
declared rows and the (empty) test set; PER-ROW coverage adjudication belongs to the
phase-boundary ``/fabrik-review``, never to this gate. Known transient: early in a phase (code
committed, its ``/fabrik-generate-tests`` step pending) the WARN can fire — WARN-only by design,
and the window that CLOSES with zero tests is exactly the measured fleet failure this exists to
catch (whole build phases shipping zero tests until review).

ADVISORY ONLY — always exits 0. Fail-soft: no active lock, no ``baseline_commit``, unreadable
plan, or ANY git/parse/IO error → exit 0 silently (ad-hoc work is not plan execution, and an
advisory must never break a commit).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:  # same-dir sibling import (the check_doc_stubs pattern)
    sys.path.insert(0, str(_HERE))

PROJECT_ROOT = Path.cwd()
LOCK_DIR = PROJECT_ROOT / ".fabrik" / "plan-locks"

_DOC_SUFFIXES = (".md", ".rst", ".txt")


def _active_locks() -> list[dict]:
    """Every lock with status=active AND a baseline_commit AND a readable plan path."""
    out: list[dict] = []
    if not LOCK_DIR.is_dir():
        return out
    for p in sorted(LOCK_DIR.glob("*.json")):
        try:
            d = json.loads(p.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            continue
        if not isinstance(d, dict):
            continue  # valid-JSON-but-not-a-dict must skip THIS file, never abort the enumeration
        if d.get("status") == "active" and d.get("baseline_commit") and d.get("plan"):
            out.append(d)
    return out


def _given_rows(plan_path: str) -> list[str]:
    from check_plan_tickets import GIVEN_ROW_RE  # the SSOT regex — reuse, never re-derive

    p = (PROJECT_ROOT / plan_path).resolve()
    root = PROJECT_ROOT.resolve()
    if not p.is_relative_to(root):  # confine: an absolute/.. plan path in a lock never escapes
        return []
    if not p.is_file():
        return []
    text = p.read_text(encoding="utf-8", errors="replace")
    scoped = _contract_regions(text)
    return [m.group(1).strip() for m in GIVEN_ROW_RE.finditer(scoped)]


def _contract_regions(text: str) -> str:
    """Behavior-Contract regions only — check_plan_tickets scopes GIVEN_ROW_RE to
    `_section(scan, "Behavior Contract")` and an unscoped scan here would drift from it
    (an illustrative Given bullet in prose would count as a declared row). Plans carry
    the contract in TWO real forms, both scoped: the `## Behavior Contract` heading
    section (ticket/spine form — region runs to the next heading) and the monolithic
    form's `**Behavior Contract (…):**` bold label (region = its contiguous
    bullet/continuation block)."""
    import re

    regions: list[str] = []
    for m in re.finditer(r"(?im)^#{2,4}\s+Behavior Contract[^\n]*$", text):
        rest = text[m.end() :]
        stop = re.search(r"(?m)^#{2,4}\s", rest)
        regions.append(rest[: stop.start()] if stop else rest)
    for m in re.finditer(r"(?im)^\*\*Behavior Contract[^\n]*$", text):
        lines: list[str] = []
        for line in text[m.end() :].splitlines():
            if not line.strip() or re.match(r"^\s*[-*]\s", line) or re.match(r"^\s{2,}\S", line):
                lines.append(line)
                continue
            break  # first prose/heading/label line ends the block
        regions.append("\n".join(lines))
    return "\n".join(regions)


def _window_files(baseline: str, *, exclude_deleted: bool = False) -> list[str]:
    args = ["git", "diff", "--name-only"]
    if exclude_deleted:
        args.append("--diff-filter=d")  # a DELETED test must never satisfy test-accompaniment
    r = subprocess.run(
        [*args, f"{baseline}..HEAD"],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
    )
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip()[:200])
    return [f for f in r.stdout.splitlines() if f.strip()]


def _owned(path: str, owned_paths: list[str]) -> bool:
    """Lock-scope filter — on the shared-master tree, SIBLING commits land inside the window
    (review finding, live-verified: three tryton-crm commits sat in this plan's own window).
    Without this filter a sibling's untested source misattributes a WARN to this plan, and a
    sibling's unrelated tests/ addition masks this plan's real zero-test gap. An entry owns
    exactly itself or, as a dir prefix, its subtree."""
    for o in owned_paths:
        o = o.rstrip("/")
        if path == o or path.startswith(o + "/"):
            return True
    return False


def _is_test(path: str) -> bool:
    # A tests/ dir anywhere on the path, or a root-level test_*.py. The bare-name clause is
    # root-only: `scripts/test_connectivity.py` is a diagnostic utility, and letting it count
    # as accompaniment would silently satisfy the WARN for an unrelated behavior change.
    parts = Path(path).parts
    return "tests" in parts[:-1] or (len(parts) == 1 and parts[0].startswith("test_"))


def _is_source(path: str) -> bool:
    if _is_test(path) or path.lower().endswith(_DOC_SUFFIXES):
        return False
    return path.endswith((".py", ".ts", ".tsx", ".js", ".jsx", ".sh", ".sql"))


def main() -> int:
    try:
        warned = False
        for lock in _active_locks():
            rows = _given_rows(str(lock["plan"]))
            if not rows:
                continue  # a plan with no declared behaviors is silent by construction
            raw_owned = lock.get("owned_paths") or []
            if isinstance(raw_owned, str):  # a hand-edited scalar must scope, not iterate chars
                raw_owned = [raw_owned]
            owned = [str(o) for o in raw_owned]
            files = _window_files(str(lock["baseline_commit"]))
            if owned:  # a lock without owned_paths falls back to the whole window
                files = [f for f in files if _owned(f, owned)]
            source = [f for f in files if _is_source(f)]
            # Tests count only when ADDED/MODIFIED — a window that DELETES its tests while
            # shipping behavior is exactly the failure this gate exists to catch (review finding,
            # live-reproduced: an unfiltered list let a test deletion silence the WARN).
            alive = _window_files(str(lock["baseline_commit"]), exclude_deleted=True)
            if owned:
                alive = [f for f in alive if _owned(f, owned)]
            tests = [f for f in alive if _is_test(f)]
            if not source:
                continue  # docs-only window — no false positive
            if tests:
                continue  # tests accompany the window — the gate's assertion holds
            warned = True
            print(
                f"WARNING: plan window {lock['baseline_commit'][:8]}..HEAD "
                f"({lock['plan']}) declares {len(rows)} Behavior-Contract row(s) and touched "
                f"{len(source)} source file(s) with ZERO test changes. Per-row coverage is the "
                "phase-boundary /fabrik-review's to adjudicate; a window that CLOSES like this "
                "shipped behavior without tests."
            )
            for row in rows[:12]:
                print(f"  declared: {row[:160]}")
            if len(rows) > 12:
                print(f"  … and {len(rows) - 12} more row(s)")
        if not warned:
            print(
                "PHASE-TESTS (advisory): OK — no active plan window shipping behavior without tests."
            )
        return 0
    except Exception as e:  # noqa: BLE001 — advisory must never break a commit
        sys.stderr.write(f"PHASE-TESTS (advisory): fail-soft on error: {e}\n")
        return 0


if __name__ == "__main__":
    sys.exit(main())
