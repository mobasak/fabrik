#!/usr/bin/env python3
"""Coverage-checklist gate — run by final_gate via run_optional_check (non-zero = fail).

Companion to check_convergence.py for the coverage-adjudicated review commands
(/fabrik-review, /fabrik-repo-review). A review artifact that claims the exit must
prove FULL adjudication of its Coverage Checklist. Inspects only changed/untracked
files under docs/development/reviews/ (git status + regex; safe every tier).

A changed reviews/*.md containing a "Coverage Checklist" table:
  -> every checklist row must carry a verdict: CLEAN / FIXED / REFUTED.
  -> zero UNCHECKED rows. (There is NO cap-stop / "Declared residual" bypass —
     the Termination contract has no round ceiling; the only pause is a
     per-finding 3-attempts BLOCKED escalation. A prior docstring advertised a
     cap-stop the contract never allowed — a live run cited it to close a loop
     on a spot-verify round.)
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
BLOCKED_HEAD = re.compile(r"^#{2,4}\s*.*BLOCKED", re.M)
RECURRENCE = {
    "fail-open/fail-closed": re.compile(r"fail[- ]open", re.I),
    "cost/quota accounting": re.compile(r"\b(cost|quota|limit)\b", re.I),
    "boundary/sentinel/prefix": re.compile(r"\b(boundary|sentinel|prefix)\b", re.I),
    "behavior-without-a-test": re.compile(
        r"behavior[- ]without[- ]a[- ]test|untested behavior", re.I
    ),
}


def _changed_md(root: Path, prefix: str) -> list[Path]:
    """Changed/untracked .md under ``prefix`` (git status), excluding archived/."""
    try:
        out = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=all", "--", prefix],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []
    paths = []
    for line in out.splitlines():
        rel = line[3:].split(" -> ")[-1].strip().strip('"')
        if not (rel.endswith(".md") and "archived/" not in rel and (root / rel).is_file()):
            continue
        # Shared-master: '??' = untracked AND unstaged — a sibling session's (or a
        # not-yet-staged) in-flight draft. The checklist is enforced at the
        # staging/commit moment, never against another agent's mid-write scratch.
        if line[:2] == "??":
            print(f"NOTE: skip untracked in-flight draft (checked at staging): {rel}")
            continue
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
    return list(rows[2:]) if len(rows) >= 3 else []


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
    nxt = re.search(r"^#{2,4} ", text[m.end() :], re.M)
    return text[m.start() : m.end() + (nxt.start() if nxt else len(text))]


SURFACE = re.compile(r"^Surface:\s*\S+", re.M)
PASS2 = re.compile(r"\bPass\s*2\b")
RUBRIC_RUN = re.compile(r"review_rubric\.py")
_PATHISH = re.compile(r"[\w-]+[./][\w./-]+")


def check_file(p: Path) -> list[str]:
    errs: list[str] = []
    text = p.read_text(encoding="utf-8", errors="replace")
    section = _checklist_section(text)
    if section is None:
        if COMMAND_MARK.search(text):
            errs.append(
                "names /fabrik-review or /fabrik-repo-review but emits NO Coverage Checklist"
            )
        return errs
    # contract obligations recorded in the artifact itself
    if not SURFACE.search(text):
        errs.append(
            "no `Surface:` hash line (cross-run anchor) — record `git rev-parse HEAD` + diff md5"
        )
    if not RUBRIC_RUN.search(text):
        errs.append(
            "no review_rubric.py invocation recorded — checklist classes must derive from the rubric, not memory"
        )
    if not PASS2.search(text):
        errs.append(
            "no `Pass 2` in the ledger — minimum two rounds ALWAYS (a clean pass 1 still needs its confirming round)"
        )
    rows = _table_rows(section)
    if not rows:
        errs.append("Coverage Checklist has no table rows")
        return errs
    blocked_ok = bool(BLOCKED_HEAD.search(text)) and bool(
        re.search(r"3\b.{0,40}attempt|attempt.{0,40}\b3\b|three (?:consecutive|failed)", text, re.I)
    )
    unchecked = [r.strip() for r in rows if UNCHECKED.search(r)]
    noverdict = [r.strip() for r in rows if not UNCHECKED.search(r) and not VERDICT.search(r)]
    if unchecked and not blocked_ok:
        errs.append(
            f"{len(unchecked)} UNCHECKED row(s) with no ## BLOCKED escalation (finding + 3 failed attempts): {unchecked[:3]}"
        )
    if noverdict:
        errs.append(
            f"{len(noverdict)} row(s) without a CLEAN/FIXED/REFUTED verdict: {noverdict[:3]}"
        )
    bare = [
        r.strip()
        for r in rows
        if re.search(r"\bCLEAN\b", r) and not _PATHISH.search(r) and len(r.strip()) < 70
    ]
    if bare:
        errs.append(
            f"{len(bare)} CLEAN row(s) without evidence (name the files/paths hunted): {bare[:3]}"
        )
    founds = re.findall(r"found:\s*(\d+)", text)
    if founds and int(founds[-1]) != 0 and not blocked_ok:
        errs.append(
            f"final ledger round raised {founds[-1]} (refuted counts as found) — the exit round must be quiet, or the stuck finding must be BLOCKED-escalated (named + 3 failed attempts)"
        )
    body = "\n".join(rows)
    missing = [name for name, pat in RECURRENCE.items() if not pat.search(body)]
    if missing:
        errs.append(f"standing recurrence class(es) missing from checklist: {missing}")
    return errs


# --- Certification disposition gate (user-test / service-test reports) ---------
# Grammar (defined in the gauntlets' "Report + chain" sections):
#   HANDOFF P<0-3> OPEN <desc> — repro: <path> — route: <command>
#   HANDOFF P<0-3> CLOSED <desc> — repro: <path> — proof: <green-run one-liner>
#   DESIGN-GAP <desc> — brief: <path>            (operator decision; may stay open)
# Rules (zero-false-positive by design — only rows using the grammar are parsed):
#   CLOSED without an existing repro path or without proof:  FAIL
#   OPEN routed to /fabrik-review (code-wrong) without evidence:  FAIL
#   any OPEN row  -> report must carry NOT-QUIET marker AND a ## RESUME section
#   NOT-QUIET marker -> ## RESUME required
CERT_REPORT = re.compile(r"-(user|service)-test-.*\.md$")
HANDOFF_ROW = re.compile(r"^\s*[-*]?\s*HANDOFF\s+P([0-3])\s+(OPEN|CLOSED)\b(.*)$", re.M)
REPRO_IN_ROW = re.compile(r"repro:\s*([\w./-]+)")
PROOF_IN_ROW = re.compile(r"proof:\s*\S")
CODE_WRONG_ROUTE = re.compile(r"route:\s*/fabrik-review\b")
EVIDENCE_IN_ROW = re.compile(r"evidence:\s*\S")
NOT_QUIET = re.compile(r"NOT-QUIET")
RESUME_HEAD = re.compile(r"^##\s+RESUME\b", re.M)


def check_cert_dispositions(path: Path, root: Path) -> list[str]:
    """Disposition rows in a certification report must be provable, not prose."""
    text = path.read_text(encoding="utf-8", errors="replace")
    errs: list[str] = []
    rows = HANDOFF_ROW.findall(text)
    open_rows = [r for r in rows if r[1] == "OPEN"]
    for _sev, state, rest in rows:
        m = REPRO_IN_ROW.search(rest)
        if state == "CLOSED":
            if not m:
                errs.append(f"CLOSED HANDOFF row lacks a repro: path — {rest.strip()[:60]}")
            elif not (root / m.group(1)).is_file():
                errs.append(f"CLOSED HANDOFF cites a repro that does not exist: {m.group(1)}")
            if not PROOF_IN_ROW.search(rest):
                errs.append(f"CLOSED HANDOFF row lacks proof: — {rest.strip()[:60]}")
        elif CODE_WRONG_ROUTE.search(rest) and not EVIDENCE_IN_ROW.search(rest):
            errs.append(
                "OPEN code-wrong HANDOFF row lacks evidence: (wire/state proof of attribution — "
                f"a red repro alone can be rig-defective) — {rest.strip()[:60]}"
            )
    if open_rows:
        if not NOT_QUIET.search(text):
            errs.append(
                f"{len(open_rows)} OPEN HANDOFF row(s) but the ledger is not marked "
                "NOT-QUIET (routes outstanding) — a truncated run may never present itself as quiet"
            )
        if not RESUME_HEAD.search(text):
            errs.append(f"{len(open_rows)} OPEN HANDOFF row(s) but no ## RESUME section")
    if NOT_QUIET.search(text) and not RESUME_HEAD.search(text):
        errs.append("ledger marked NOT-QUIET but no ## RESUME section names the outstanding rows")
    return errs


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", default=".", help="repo root (default: cwd)")
    args = ap.parse_args()
    root = Path(args.root).resolve()
    failures: list[str] = []
    for p in _changed_md(root, REVIEWS_DIR):
        if CERT_REPORT.search(p.name):
            for e in check_cert_dispositions(p, root):
                failures.append(f"{p.relative_to(root)}: {e}")
            continue  # a certification report is disposition-gated, not checklist-gated
        for e in check_file(p):
            failures.append(f"{p.relative_to(root)}: {e}")
    if failures:
        print("Coverage-checklist gate FAILED:")
        for f in failures:
            print(f"  - {f}")
        print(
            "A coverage-adjudicated review exits only on a fully-adjudicated checklist "
            "— there is no cap-stop; a spot-verify of fixes is the re-check step, never the closing round."
        )
        return 1
    print("check_review_coverage: OK (no unproven coverage claims in changed review artifacts)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
