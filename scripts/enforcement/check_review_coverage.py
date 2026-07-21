#!/usr/bin/env python3
"""Coverage-checklist gate — run by final_gate via run_optional_check (non-zero = fail).

Companion to check_convergence.py for the coverage-adjudicated review commands
(/fabrik-review, /fabrik-repo-review). A review artifact that claims the exit must
prove FULL adjudication of its Coverage Checklist. Inspects only changed/untracked
files under docs/development/reviews/ (git status + regex; safe every tier).

A changed reviews/*.md containing a "Coverage Checklist" table:
  -> every checklist row must carry a verdict: CLEAN / FIXED / REFUTED.
  -> zero UNCHECKED rows — unless a "Declared residual" section names each
     leftover class (the honest cap-stop the Termination contract allows).
  -> the standing recurrence classes must appear as rows (fail-open,
     cost/quota accounting, boundary/sentinel, behavior-without-a-test).
A changed reviews/*.md that names /fabrik-review or /fabrik-repo-review as its
command but has NO Coverage Checklist -> fail (the contract requires emitting it).

Ceiling (by design): enforces checklist *presence and complete adjudication* —
never that the hunting behind a CLEAN verdict was good. Artifacts from the
edit-convergence commands (spec/plan/contract reviews) carry no Coverage
Checklist and are not this gate's subject (check_convergence.py covers them).
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

REVIEWS_DIR = "docs/development/reviews/"

CHECKLIST_HEAD = re.compile(r"coverage checklist", re.I)
COMMAND_MARK = re.compile(r"/fabrik-(?:repo-)?review\b")
VERDICT = re.compile(r"\b(CLEAN|FIXED\s*\(?\d*\)?|REFUTED)\b")
UNCHECKED = re.compile(r"\bUNCHECKED\b")
RESIDUAL_HEAD = re.compile(r"^#{2,4}\s*.*declared residual", re.I | re.M)
RECURRENCE = {
    "fail-open/fail-closed": re.compile(r"fail[- ]open", re.I),
    "cost/quota accounting": re.compile(r"\b(cost|quota|limit)\b", re.I),
    "boundary/sentinel/prefix": re.compile(r"\b(boundary|sentinel|prefix)\b", re.I),
    "behavior-without-a-test": re.compile(r"behavior[- ]without[- ]a[- ]test|untested behavior", re.I),
}


def _changed_md(root: Path, prefix: str) -> list[Path]:
    """Changed/untracked .md under ``prefix`` (git status), excluding archived/."""
    try:
        out = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=all", "--", prefix],
            cwd=root, capture_output=True, text=True, check=True,
        ).stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []
    paths = []
    for line in out.splitlines():
        rel = line[3:].split(" -> ")[-1].strip().strip('"')
        if rel.endswith(".md") and "archived/" not in rel and (root / rel).is_file():
            paths.append(root / rel)
    return paths


def _table_rows(section: str) -> list[str]:
    """Data rows of the FIRST contiguous markdown table in ``section`` (skips
    header + rule). Stops at the first non-table line so a Pass Ledger emitted
    under the same heading is never mistaken for checklist rows."""
    rows: list[str] = []
    in_table = False
    for line in section.splitlines():
        if line.lstrip().startswith("|"):
            rows.append(line)
            in_table = True
        elif in_table:
            break
    return [r for r in rows[2:]] if len(rows) >= 3 else []


def _checklist_section(text: str) -> str | None:
    m = None
    for h in re.finditer(r"^#{2,4} .*$", text, re.M):
        if CHECKLIST_HEAD.search(h.group(0)):
            m = h
            break
    if m is None:
        # table introduced without its own heading — fall back to the first
        # table that follows the phrase "Coverage Checklist" anywhere.
        i = text.lower().find("coverage checklist")
        return text[i:] if i != -1 else None
    nxt = re.search(r"^#{2,4} ", text[m.end():], re.M)
    return text[m.start(): m.end() + (nxt.start() if nxt else len(text))]


def check_file(p: Path) -> list[str]:
    errs: list[str] = []
    text = p.read_text(encoding="utf-8", errors="replace")
    section = _checklist_section(text)
    if section is None:
        if COMMAND_MARK.search(text):
            errs.append("names /fabrik-review or /fabrik-repo-review but emits NO Coverage Checklist")
        return errs
    rows = _table_rows(section)
    if not rows:
        errs.append("Coverage Checklist has no table rows")
        return errs
    residual_ok = bool(RESIDUAL_HEAD.search(text))
    unchecked = [r.strip() for r in rows if UNCHECKED.search(r)]
    noverdict = [r.strip() for r in rows if not UNCHECKED.search(r) and not VERDICT.search(r)]
    if unchecked and not residual_ok:
        errs.append(f"{len(unchecked)} UNCHECKED row(s) with no 'Declared residual' section: {unchecked[:3]}")
    if noverdict:
        errs.append(f"{len(noverdict)} row(s) without a CLEAN/FIXED/REFUTED verdict: {noverdict[:3]}")
    body = "\n".join(rows)
    missing = [name for name, pat in RECURRENCE.items() if not pat.search(body)]
    if missing:
        errs.append(f"standing recurrence class(es) missing from checklist: {missing}")
    return errs


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", default=".", help="repo root (default: cwd)")
    args = ap.parse_args()
    root = Path(args.root).resolve()
    failures: list[str] = []
    for p in _changed_md(root, REVIEWS_DIR):
        for e in check_file(p):
            failures.append(f"{p.relative_to(root)}: {e}")
    if failures:
        print("Coverage-checklist gate FAILED:")
        for f in failures:
            print(f"  - {f}")
        print("A coverage-adjudicated review exits only on a fully-adjudicated checklist "
              "(or a cap-stop with a Declared residual section naming the leftovers).")
        return 1
    print("check_review_coverage: OK (no unproven coverage claims in changed review artifacts)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
