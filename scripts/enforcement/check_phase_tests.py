#!/usr/bin/env python3
# AFTER-EDIT: tests/enforcement/test_phase_tests_gate.py
"""Behavior-Contract test-accompaniment advisory — WARN when a plan-execution window
declares behaviors but has added no tests.

WHOLE-WINDOW by design (plan 2026-08-10-plan-2 Phase C; the per-phase form would require a
phase-boundary mechanism no plan lock carries): the range is the ACTIVE plan lock's
``baseline_commit..HEAD``; the rows are every bulleted ``- **Given**`` row in the locked plan
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
_TEST_MARKERS = ("tests/", "test_")


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
        if d.get("status") == "active" and d.get("baseline_commit") and d.get("plan"):
            out.append(d)
    return out


def _given_rows(plan_path: str) -> list[str]:
    from check_plan_tickets import GIVEN_ROW_RE  # the SSOT regex — reuse, never re-derive

    p = PROJECT_ROOT / plan_path
    if not p.is_file():
        return []
    return [m.group(1).strip() for m in GIVEN_ROW_RE.finditer(p.read_text(encoding="utf-8", errors="replace"))]


def _window_files(baseline: str) -> list[str]:
    r = subprocess.run(
        ["git", "diff", "--name-only", f"{baseline}..HEAD"],
        capture_output=True, text=True, cwd=PROJECT_ROOT,
    )
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip()[:200])
    return [f for f in r.stdout.splitlines() if f.strip()]


def _is_test(path: str) -> bool:
    return path.startswith("tests/") or "/tests/" in path or Path(path).name.startswith("test_")


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
            files = _window_files(str(lock["baseline_commit"]))
            source = [f for f in files if _is_source(f)]
            tests = [f for f in files if _is_test(f)]
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
            print("PHASE-TESTS (advisory): OK — no active plan window shipping behavior without tests.")
        return 0
    except Exception as e:  # noqa: BLE001 — advisory must never break a commit
        sys.stderr.write(f"PHASE-TESTS (advisory): fail-soft on error: {e}\n")
        return 0


if __name__ == "__main__":
    sys.exit(main())
