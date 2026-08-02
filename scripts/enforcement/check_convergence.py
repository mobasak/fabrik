#!/usr/bin/env python3
# AFTER-EDIT: tests/test_check_convergence.py, commands/_sources/fabrik-execute-plan.md | none
"""Convergence-evidence gate — run by final_gate via run_optional_check (non-zero = fail).

A markdown artifact that CLAIMS convergence must PROVE it. Inspects only
changed/untracked files under the plans/ and reviews/ dirs (cheap — git status
+ regex; safe to run every tier).

  docs/development/plans/*.md   '**Status:** CONVERGED' (or 'zero unknowns')
      -> requires a '## Evidence' section, a self-audit / convergence-floor
         block, >=1 `path:line` citation per Phase/Step, and >=1 non-trivial
         fenced command-output block.
  docs/development/plans/*.md   '**Status:** EXECUTED'  (incl. plans/archived/)
      -> must CITE a persisted whole-plan review artifact
         (docs/development/reviews/*.md) that EXISTS on disk and shows a
         coverage-adjudicated exit (a 'Coverage Checklist' + a final 'found: 0'
         pass). Closes the hole where an agent flips Status: EXECUTED (and
         archives) without the whole-plan /fabrik-review the execute-plan Finish
         mandates ever having run — check_review_coverage.py is INERT when no
         review file exists, so this is what forces one to exist.
  docs/development/reviews/*.md 'reviewed' / 'converged' / 'sign-off'
      -> requires an embedded fenced block containing '"status": "success"'
         (a real `final_gate --json` run) and >=1 per-phase verdict.

Ceiling (by design): this enforces evidence *presence* and mechanical green —
never truth. It makes an unproven convergence claim fail the gate and leaves an
audit trail; whether the cited evidence is *correct* still rests with the
reviewer. The DEPTH of a cited review's checklist adjudication (no UNCHECKED
rows, every class CLEAN/FIXED/REFUTED) is check_review_coverage.py's job when
that review is staged; here we require the review to EXIST and to carry the
adjudicated-exit signature. Direct edits that ship no plan/review artifact are
not covered here — they rely on the rest of final_gate.

Docs convergence is enforced separately by check_doc_sync.py ("Doc Sync Matrix")
+ docs_updater.py --check ("Documentation Drift").
"""

from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path

PLANS_DIR = "docs/development/plans/"
REVIEWS_DIR = "docs/development/reviews/"

CONVERGED = re.compile(r"^\s*\*\*Status:\*\*.*\b(converged|zero unknowns)\b", re.I | re.M)
# EXECUTED must be the status VALUE (right after `Status:`), not the word
# "executed" appearing in prose — else a `Status: CLOSED … never executed
# directly` / `Status: Done … was executed unauthorized` line false-positives.
# An optional leading list/quote marker tolerates `- **Status:** EXECUTED`.
EXECUTED = re.compile(
    r"^\s*(?:[-*>]\s+)?\*{0,2}Status:?\*{0,2}\s*(?:✅\s*)?\*{0,2}\s*EXECUTED\b", re.I | re.M
)
REVIEW_CITE = re.compile(r"docs/development/reviews/[\w./-]+\.md")
# The /fabrik-review termination signature (term-coverage): a quiet round
# ``found: 0 … fixed: 0``. We require this PAIR to appear *somewhere* — a
# deliberately ZERO-FALSE-POSITIVE signal: a genuinely-converged review ALWAYS
# has one, so this never cries wolf (the failure mode that gets a fleet gate
# ``# noqa``'d — worse than a false-accept). It rejects a prose-only "found:0"
# (no adjacent ``fixed:0``) and a cited review with no quiet round at all. It does
# NOT try to prove the quiet round was the FINAL one — that DEPTH (no UNCHECKED
# rows, every class adjudicated, the loop truly converged) is
# check_review_coverage.py's job when the review is staged. This gate's ceiling
# is evidence PRESENCE, not truth (see module docstring).
QUIET_PASS = re.compile(r"found:\s*0\b[^\n]{0,40}?fixed:\s*0\b", re.I)
REVIEWED = re.compile(r"\b(reviewed|converged|sign[- ]?off)\b", re.I)
PHASE = re.compile(r"^#{2,}\s*(Phase|Step)\b", re.I | re.M)
PROOF = re.compile(r"[\w./-]+\.(?:py|ts|tsx|js|sql|md|csv|ya?ml|sh|json):\d+")
EVIDENCE = re.compile(r"^#{2,}\s*Evidence\b", re.I | re.M)
AUDIT = re.compile(r"self[- ]?audit|convergence floor", re.I)
GATE_OK = re.compile(r'"status"\s*:\s*"success"')
# Fenced code blocks — capture inner content so we can demand non-trivial output
# (an empty ``` ``` pair must not satisfy the "show the command output" rule).
FENCE_BLOCK = re.compile(r"```[^\n]*\n(.*?)```", re.S)


def _nontrivial_fences(text: str) -> int:
    """Count fenced blocks whose inner content carries real output (>=20 non-ws chars)."""
    return sum(1 for inner in FENCE_BLOCK.findall(text) if len(inner.strip()) >= 20)


def _changed_md(root: Path, prefix: str) -> list[Path]:
    """Changed/untracked .md files under ``prefix`` (per git status), excluding archived/."""

    def _keep(p: str) -> bool:
        return p.startswith(prefix) and p.endswith(".md") and "archived/" not in p

    try:
        # --untracked-files=all lists individual files even when the parent dir
        # is itself untracked (a fresh/sparse repo collapses to "?? docs/"
        # otherwise, hiding the artifact).
        out = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=all", "--", prefix],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=15,
        ).stdout
    except Exception:
        return []
    paths: list[Path] = []
    for line in out.splitlines():
        # Shared-master: '??' = untracked AND unstaged — another agent's (or a
        # not-yet-staged) in-flight draft. Convergence proof is enforced at the
        # staging/commit moment (the gate stages your files; the doc rides the
        # phase commit) — never against a sibling session's mid-write scratch.
        # Precedent family: specs/*.yaml.draft; check_synced_unmodified→HEAD.
        if line[:2] == "??":
            p = line[3:].strip()
            if _keep(p):
                print(f"NOTE: skip untracked in-flight draft (checked at staging): {p}")
            continue
        p = line[3:].strip()
        if " -> " in p:  # renamed: "old -> new"
            p = p.split(" -> ", 1)[1]
        if _keep(p):
            paths.append(root / p)
    return paths


def _check_plan(root: Path, path: Path) -> list[str]:
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8", errors="replace")
    if not CONVERGED.search(text):
        return []  # only artifacts that CLAIM convergence are held to proof
    rel = path.relative_to(root)
    fails: list[str] = []
    if not EVIDENCE.search(text):
        fails.append("claims CONVERGED but has no '## Evidence' section")
    if not AUDIT.search(text):
        fails.append("no self-audit / convergence-floor block")
    phases = len(PHASE.findall(text)) or 1
    if len(set(PROOF.findall(text))) < phases:
        fails.append(f"fewer than 1 `file:line` citation per phase (need >= {phases})")
    if _nontrivial_fences(text) < 1:
        fails.append("no non-trivial fenced command-output block (a column name != its values)")
    return [f"{rel}: {x}" for x in fails]


def _head_text(root: Path, relpath: str) -> str:
    """Content of ``relpath`` at HEAD, or "" if it did not exist there."""
    try:
        r = subprocess.run(
            ["git", "show", f"HEAD:{relpath}"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=15,
        )
        return r.stdout if r.returncode == 0 else ""
    except Exception:
        return ""


def _executed_targets(root: Path) -> list[Path]:
    """Plans whose EXECUTED claim is NEW this commit — those must carry the review citation.

    A plan is enforced when its staged/working content claims EXECUTED **and that claim is
    not already present at HEAD for the same path** — i.e. the EXECUTED transition is
    happening now. This catches the flip in ``plans/``, the flip-and-archive (whether git
    records the move as a rename OR as delete+add on a large body rewrite), and a plan
    freshly added as EXECUTED — while SKIPPING a settled plan (already EXECUTED at HEAD)
    that is merely re-touched (a bulk reformat / reorg must not re-fail dozens of archived
    plans — the 'cries wolf' failure that gets a gate ``# noqa``'d). Robust to git rename
    detection being off (``status.renames=false``): it compares content at HEAD, never
    rename similarity — closing the delete+add / renames-off escape.
    """
    try:
        out = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=all", "--", PLANS_DIR],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=15,
        ).stdout
    except Exception:
        return []
    seen: set[str] = set()
    targets: list[Path] = []
    for line in out.splitlines():
        if line[:2] == "??":
            continue  # untracked in-flight draft — checked at staging (see _changed_md)
        rest = line[3:].strip()
        if " -> " in rest:  # rename: "old -> new"
            src, dst = (s.strip().strip('"') for s in rest.split(" -> ", 1))
        else:
            src = dst = rest.strip().strip('"')
        if dst in seen or not (dst.startswith(PLANS_DIR) and dst.endswith(".md")):
            continue
        seen.add(dst)
        p = root / dst
        if not p.is_file():
            continue
        if not EXECUTED.search(p.read_text(encoding="utf-8", errors="replace")):
            continue  # not an EXECUTED claim now → nothing to enforce
        # SETTLED (skip) if the plan was ALREADY EXECUTED at HEAD — at the new path
        # (in-place re-touch) OR at the rename SOURCE (a relocation / dir reorg). Only
        # a genuinely NEW EXECUTED transition is enforced, so a bulk archive reorg that
        # *moves* pre-citation EXECUTED plans doesn't re-fail every one of them.
        if EXECUTED.search(_head_text(root, dst)) or EXECUTED.search(_head_text(root, src)):
            continue
        targets.append(p)
    return targets


def _check_executed_plan(root: Path, path: Path) -> list[str]:
    """A plan claiming EXECUTED must cite a persisted whole-plan review artifact
    that EXISTS on disk and carries a coverage-adjudicated exit signature.

    This is the enforcement backstop for /fabrik-execute-plan's Finish step,
    which mandates a whole-plan /fabrik-review run to a coverage-adjudicated exit
    before the status flip. check_review_coverage.py can only validate a review
    that EXISTS; if the agent skips the skill entirely it produces no artifact
    and that gate stays silent. This makes the artifact's existence a hard
    precondition of the EXECUTED claim itself.
    """
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8", errors="replace")
    if not EXECUTED.search(text):
        return []  # only plans that CLAIM EXECUTED are held to the review proof
    rel = path.relative_to(root)
    cited = REVIEW_CITE.findall(text)
    if not cited:
        return [
            f"{rel}: claims EXECUTED but cites no whole-plan review artifact "
            "(docs/development/reviews/*.md) — run /fabrik-review over the whole-plan diff "
            "to its coverage-adjudicated exit, cite it here, or revert Status"
        ]
    for c in dict.fromkeys(cited):  # dedupe, preserve order
        rp = root / c
        if not rp.is_file():
            continue
        rtext = rp.read_text(encoding="utf-8", errors="replace")
        # A quiet round (found: 0 … fixed: 0) appears somewhere → the cited review
        # ran the loop to (at least one) quiet pass. Zero-false-positive by design
        # (see QUIET_PASS); DEPTH is check_review_coverage.py's at staging time.
        if QUIET_PASS.search(rtext):
            return []  # a real whole-plan review with a quiet round exists → satisfied
    return [
        f"{rel}: claims EXECUTED but its cited whole-plan review is missing on disk or not "
        "coverage-adjudicated (needs a quiet final pass — a 'found: 0, fixed: 0' round) — "
        "finish the /fabrik-review loop to a quiet round, or revert Status"
    ]


def _check_review(root: Path, path: Path) -> list[str]:
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8", errors="replace")
    if not REVIEWED.search(text):
        return []
    rel = path.relative_to(root)
    fails: list[str] = []
    if not GATE_OK.search(text):
        fails.append('no embedded final_gate run showing "status": "success"')
    if not PHASE.search(text):
        fails.append("no per-phase verdict (no Phase/Step reference)")
    return [f"{rel}: {x}" for x in fails]


def main() -> int:
    parser = argparse.ArgumentParser(description="Convergence-evidence gate (plans + reviews).")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    root = args.project_root.resolve()

    fails: list[str] = []
    for p in _changed_md(root, PLANS_DIR):
        fails += _check_plan(root, p)
    for p in _executed_targets(root):
        fails += _check_executed_plan(root, p)
    for p in _changed_md(root, REVIEWS_DIR):
        fails += _check_review(root, p)

    if fails:
        print("Convergence gate FAILED — a convergence claim lacks its proof:")
        for x in fails:
            print(f"  - {x}")
        print(
            "Fix: supply the required evidence (Evidence section, file:line citations, a"
            " fenced command-output block, an embedded final_gate success), or drop the claim."
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
