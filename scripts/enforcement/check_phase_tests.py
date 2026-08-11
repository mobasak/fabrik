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

    # Fenced code blocks are illustrative prose — a fence-quoted contract label/row must
    # never mint a declared row (review findings, live-reproduced for ``` and for the
    # equally-valid CommonMark ~~~ form; the backreference pairs like with like). Paired
    # fences only; unbalanced markdown is left as-is (fail toward counting → the WARN).
    text = re.sub(r"(?ms)^[ \t]*(```|~~~).*?^[ \t]*\1[ \t]*$", "", text)
    regions: list[str] = []
    heading_spans: list[tuple[int, int]] = []  # absolute offsets of heading regions
    for m in re.finditer(r"(?im)^#{2,4}\s+Behavior Contract[^\n]*$", text):
        rest = text[m.end() :]
        stop = re.search(r"(?m)^#{2,4}\s", rest)
        end = m.end() + (stop.start() if stop else len(rest))
        heading_spans.append((m.start(), end))
        regions.append(text[m.end() : end])
    for m in re.finditer(r"(?im)^\*\*Behavior Contract[^\n]*$", text):
        # A bold label nested INSIDE a heading region is already captured above — scanning it
        # again would double-count its rows (review finding, live-reproduced: 2 rows printed 3).
        if any(s <= m.start() < e for s, e in heading_spans):
            continue
        lines: list[str] = []
        for line in text[m.end() :].splitlines():
            if not line.strip() or re.match(r"^\s*[-*]\s", line) or re.match(r"^\s{2,}\S", line):
                lines.append(line)
                continue
            break  # first prose/heading/label line ends the block
        regions.append("\n".join(lines))
    return "\n".join(regions)


def _window_files(baseline: str, *, exclude_deleted: bool = False) -> list[str]:
    """Window file list via `--name-status` with rename+copy detection. PURE renames and
    PURE copies (R100/C100) are no-ops in BOTH sets — as accompaniment they add zero
    coverage (review findings, live-reproduced: `git mv` alone, then a verbatim `cp` of an
    existing test, each silenced a real WARN), and as source they are refactors, not
    shipped behavior. An EDITED rename/copy (R/C below 100) carries new content and counts
    normally (the earlier exclude-all-renames form drew a false WARN against a renamed
    test that gained a genuinely new test function). `exclude_deleted` drops D rows — a
    DELETED test never satisfies accompaniment; source deletions DO count (removing
    behavior is a behavior change)."""
    # --find-copies-harder, not --find-copies: plain copy detection only considers
    # SOURCES MODIFIED in the same diff, so a verbatim copy of an untouched test still
    # reported as A (probe-verified). Harder scans all files as sources — bounded cost
    # on a plan window's modest diff, and the only form that actually catches the gaming.
    # -z (NUL records): git C-quotes/octal-escapes any path with a non-ASCII byte, tab,
    # quote, or backslash under default core.quotepath — a quoted path matches no real
    # file downstream, making it invisible to the gate in BOTH directions (review
    # finding, live-reproduced: a real tests/test_café.py drew a false WARN and a
    # src/wörker.py behavior window passed in false SILENCE). NUL output is never quoted.
    args = ["git", "diff", "--name-status", "--find-renames", "--find-copies-harder", "-z"]
    if exclude_deleted:
        args.append("--diff-filter=d")
    r = subprocess.run(
        [*args, f"{baseline}..HEAD"],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
    )
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip()[:200])
    out: list[str] = []
    toks = r.stdout.split("\0")
    i = 0
    while i < len(toks):
        status = toks[i].strip()
        if not status:
            i += 1
            continue
        n_paths = 2 if status[:1] in ("R", "C") else 1  # R/C records carry old + new
        paths = [p for p in toks[i + 1 : i + 1 + n_paths] if p]
        i += 1 + n_paths
        if status in ("R100", "C100"):
            continue  # pure rename/copy — no content change in the window
        if paths:
            out.append(paths[-1])  # the NEW path is the live one
    return out


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


_CODE_TEST_SUFFIXES = (".py", ".ts", ".tsx", ".js", ".jsx", ".sh")


def _in_tests_tree(path: str) -> bool:
    # Case-insensitive: a `Tests/` dir is the same convention (review finding — the
    # case-sensitive match produced a false WARN against a real accompanying test).
    return "tests" in (p.lower() for p in Path(path).parts[:-1])


def _is_test(path: str) -> bool:
    """Counts as test ACCOMPANIMENT: a code-test-named CODE file in a tests/ dir, at repo
    root, or a `.spec./.test.`-infixed file anywhere (the JS/TS co-location convention).
    Three-way split (review findings, all live-reproduced): code tests COUNT; test-adjacent
    files (conftest, fixtures, data — including test-NAMED non-code like
    `tests/test_report.json`, which silenced a real WARN) neither count nor WARN;
    `scripts/test_connectivity.py`-style diagnostic utilities are ordinary source. The
    bare-name clause is root-only."""
    name = Path(path).name.lower()
    if not name.endswith(_CODE_TEST_SUFFIXES):
        return False  # a test-named data/report artifact is not accompaniment
    if ".spec." in name or ".test." in name:
        return True  # co-located Jest-style tests are tests wherever they live
    is_test_named = name.startswith("test_") or name.rsplit(".", 1)[0].endswith("_test")
    parts = Path(path).parts
    return is_test_named and (_in_tests_tree(path) or len(parts) == 1)


def _is_source(path: str) -> bool:
    # The whole tests/ tree is excluded from "source" — test-adjacent files (conftest,
    # fixtures, data) are neither accompaniment nor shipped behavior.
    if _is_test(path) or _in_tests_tree(path) or path.lower().endswith(_DOC_SUFFIXES):
        return False
    return path.endswith((".py", ".ts", ".tsx", ".js", ".jsx", ".sh", ".sql"))


def _check_lock(lock: dict) -> bool:
    """One lock's whole-window check; True if it WARNed. Raises on hostile field types —
    the caller isolates per lock."""
    rows = _given_rows(str(lock["plan"]))
    if not rows:
        return False  # a plan with no declared behaviors is silent by construction
    raw_owned = lock.get("owned_paths") or []
    if isinstance(raw_owned, str):  # a hand-edited scalar must scope, not iterate chars
        raw_owned = [raw_owned]
    if not isinstance(raw_owned, (list, tuple)):
        # Any other type (int, dict, …) falls back to the whole window — toward warning,
        # never toward silence (review finding: an int aborted the WHOLE run pre-isolation).
        raw_owned = []
    # Empty / slash-only entries are dropped: `[""]` would match NOTHING and silence the
    # whole window (review finding — false silence); an all-dropped list degrades to the
    # whole-window fallback, toward warning.
    owned = [str(o) for o in raw_owned if str(o).strip().strip("/")]
    baseline = str(lock["baseline_commit"])
    files = _window_files(baseline)
    if owned:  # a lock without owned_paths falls back to the whole window
        files = [f for f in files if _owned(f, owned)]
    source = [f for f in files if _is_source(f)]
    # Tests count only when ADDED/MODIFIED — a window that DELETES its tests while
    # shipping behavior is exactly the failure this gate exists to catch (review finding,
    # live-reproduced: an unfiltered list let a test deletion silence the WARN).
    alive = _window_files(baseline, exclude_deleted=True)
    if owned:
        alive = [f for f in alive if _owned(f, owned)]
    tests = [f for f in alive if _is_test(f)]
    if not source:
        return False  # docs-only window — no false positive
    if tests:
        return False  # tests accompany the window — the gate's assertion holds
    print(
        f"WARNING: plan window {baseline[:8]}..HEAD "
        f"({lock['plan']}) declares {len(rows)} Behavior-Contract row(s) and touched "
        f"{len(source)} source file(s) with ZERO test changes. Per-row coverage is the "
        "phase-boundary /fabrik-review's to adjudicate; a window that CLOSES like this "
        "shipped behavior without tests."
    )
    for row in rows[:12]:
        print(f"  declared: {row[:160]}")
    if len(rows) > 12:
        print(f"  … and {len(rows) - 12} more row(s)")
    return True


def main() -> int:
    try:
        warned = False
        for lock in _active_locks():
            try:
                warned = _check_lock(lock) or warned
            except Exception as e:  # noqa: BLE001 — ONE hostile lock must never suppress
                # the WARN of every OTHER active lock (review finding, live-reproduced:
                # `"owned_paths": 5` aborted the whole run and a sibling's WARN never fired)
                sys.stderr.write(
                    f"PHASE-TESTS (advisory): skipping malformed lock "
                    f"({lock.get('plan', '?')}): {e}\n"
                )
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
