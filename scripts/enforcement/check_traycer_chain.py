#!/usr/bin/env python3
# AFTER-EDIT: docs/traycer/** | none
"""Semantic detectors for the Traycer command chain.

Three defect classes that hand-grepping failed to eliminate four separate times.
Each failure was in *what got scanned*, not in how carefully it was read:

  A. Epic Closure asserted as unconditional. It is OPTIONAL for Retrofit epics
     (05 section Step 2b, 06 section Step 10). A grep for "Epic Closure" missed a
     line that said the "closure STAGE" instead, so this matches both vocabularies.
     A tier claim ("Epic Closure always runs Tier 3") is not an existence claim
     and is exempt.

  B. The watchdog default claimed as opt-in / default-off / kind-derived. The
     resolver reads the raw spec dict (watchdog_cfg.get("enabled", True),
     infrastructure.py:314) and has NO shape.kind test. A line-oriented grep
     missed a markdown TABLE CELL, so this splits rows into cells.

  C. Cross-file line anchors. They rot silently when the target shifts: a file I
     edited moved a citation in a file I never touched. Both spellings are caught
     (`L<n>` and `file:NN`); use section refs instead.
"""

import glob
import re
import sys

DIRS = ("docs/traycer/mega-epic-breakdown", "docs/traycer/epic-to-ticket-workflow")

BRANCH = re.compile(r"retrofit|optional|delta-feature|always runs \*{0,2}tier 3", re.I)
NEG = re.compile(r"\bno\b|\bnot\b|do not assume|operator discipline|never|except", re.I)

CLOSURE = re.compile(
    r"(epic closure[^.|\n]{0,50}?(always|mandatory|present as final|in final batch|last)"
    r"|(last batch|last ticket)[^.|\n]{0,30}?closure"
    r"|closure[^.|\n]{0,30}?(all covered|always)"
    r"|\|\s*1 \(always last\))",
    re.I,
)
WATCHDOG = re.compile(
    r"watchdog[^|\n]{0,70}?"
    r"(opt-in|default(s)? (to )?off|default per [`']?kind|derived from [`']?shape\.kind)",
    re.I,
)
ANCHOR = re.compile(
    r"`([^`]*(?:command|\.md))`[^.\n]{0,60}?\bL(\d+)|`([a-z0-9-]+-command)`?:(\d+)",
    re.I,
)


def scan(path):
    """Return one message per violation found in path."""
    hits = []
    own = path.split("/")[-1].replace(".md", "")
    with open(path, encoding="utf-8") as handle:
        lines = handle.readlines()
    for num, line in enumerate(lines, 1):
        if CLOSURE.search(line) and not BRANCH.search(line):
            hits.append(
                f"  [A] {path}:{num} - Epic Closure asserted unconditionally "
                "(it is OPTIONAL for Retrofit epics)"
            )
        cells = line.split("|") if line.strip().startswith("|") else [line]
        for cell in cells:
            if WATCHDOG.search(cell) and not NEG.search(cell):
                hits.append(
                    f"  [B] {path}:{num} - watchdog default misstated "
                    "(it is opt-OUT; the resolver has no shape.kind test)"
                )
        for match in ANCHOR.finditer(line):
            target = match.group(1) or match.group(3) or ""
            if target and target not in own:
                hits.append(
                    f"  [C] {path}:{num} - cross-file line anchor into {target} "
                    "(use a section ref; line numbers rot)"
                )
    return hits


def main():
    files = sorted(f for directory in DIRS for f in glob.glob(f"{directory}/*.md"))
    violations = [msg for path in files for msg in scan(path)]
    for msg in violations:
        print(msg)
    if violations:
        print(f"\ncheck_traycer_chain: FAIL - {len(violations)} violation(s)")
        return 1
    print(f"check_traycer_chain: PASS - {len(files)} files, all 3 classes clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
