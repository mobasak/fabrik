#!/usr/bin/env python3
"""Convergence-evidence gate — run by final_gate via run_optional_check (non-zero = fail).

A markdown artifact that CLAIMS convergence must PROVE it. Inspects only
changed/untracked files under the plans/ and reviews/ dirs (cheap — git status
+ regex; safe to run every tier).

  docs/development/plans/*.md   '**Status:** CONVERGED' (or 'zero unknowns')
      -> requires a '## Evidence' section, a self-audit / convergence-floor
         block, >=1 `path:line` citation per Phase/Step, and >=1 non-trivial
         fenced command-output block.
  docs/development/reviews/*.md 'reviewed' / 'converged' / 'sign-off'
      -> requires an embedded fenced block containing '"status": "success"'
         (a real `final_gate --json` run) and >=1 per-phase verdict.

Ceiling (by design): this enforces evidence *presence* and mechanical green —
never truth. It makes an unproven convergence claim fail the gate and leaves an
audit trail; whether the cited evidence is *correct* still rests with the
reviewer. Direct edits that ship no plan/review artifact are not covered here —
they rely on the rest of final_gate.

Docs convergence is enforced separately by docs_updater.py --check
("Documentation Drift") + check_docs.py ("Documentation Completeness").
"""

from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path

PLANS_DIR = "docs/development/plans/"
REVIEWS_DIR = "docs/development/reviews/"

CONVERGED = re.compile(r"^\s*\*\*Status:\*\*.*\b(converged|zero unknowns)\b", re.I | re.M)
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
        p = line[3:].strip()
        if " -> " in p:  # renamed: "old -> new"
            p = p.split(" -> ", 1)[1]
        if p.startswith(prefix) and p.endswith(".md") and "archived/" not in p:
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
