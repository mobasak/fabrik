#!/usr/bin/env python3
# AFTER-EDIT: docs/traycer/**  |  none
"""Semantic detectors for the Traycer command chain.

Three classes this review kept re-breaking, each guarded mechanically because
grep-by-hand failed four times:

  A. Epic Closure asserted as unconditional. It is OPTIONAL for Retrofit epics.
     Catches BOTH vocabularies: "Epic Closure" AND the bare "closure" stage.
  B. Watchdog default claimed opt-in / default-off / kind-derived. The resolver
     reads the raw dict (`watchdog_cfg.get("enabled", True)`) with NO kind test.
     Scans TABLE CELLS, not lines — a cell hid behind its neighbour's text once.
  C. Cross-file line anchors (`L<n>` / `file:NN`). They rot silently when the
     target file shifts; use section refs.
"""
import re, sys, glob

DIRS = ("docs/traycer/mega-epic-breakdown", "docs/traycer/epic-to-ticket-workflow")
FILES = sorted(f for d in DIRS for f in glob.glob(f"{d}/*.md"))

BRANCH = re.compile(r"retrofit|optional|delta-feature|always runs \*\*tier 3\*\*|always runs tier 3", re.I)
NEG = re.compile(r"\bno\b|\bnot\b|do not assume|operator discipline|never|except", re.I)

# A — closure asserted unconditionally, in EITHER vocabulary
A = re.compile(
    r"(epic closure[^.|\n]{0,50}?(always|mandatory|present as final|in final batch|last)"
    r"|(last batch|last ticket)[^.|\n]{0,30}?closure"
    r"|closure[^.|\n]{0,30}?(all covered|always)"
    r"|\|\s*1 \(always last\))", re.I)
# B — watchdog default misstated (per cell)
B = re.compile(r"watchdog[^|\n]{0,70}?(opt-in|default(s)? (to )?off|default per [`']?kind|derived from [`']?shape\.kind)", re.I)
# C — a line-number anchor pointing at a DIFFERENT file
C = re.compile(r"`([^`]*(?:command|\.md))`[^.\n]{0,60}?\bL(\d+)|`([a-z0-9-]+-command)`?:(\d+)", re.I)

fails = 0
for p in FILES:
    self_name = p.split("/")[-1].replace(".md", "")
    for i, line in enumerate(open(p), 1):
        if A.search(line) and not BRANCH.search(line):
            print(f"  [A] {p}:{i} — Epic Closure asserted unconditionally (OPTIONAL for Retrofit)"); fails += 1
        cells = line.split("|") if line.strip().startswith("|") else [line]
        for c in cells:
            if B.search(c) and not NEG.search(c):
                print(f"  [B] {p}:{i} — watchdog default misstated (it is opt-OUT, no kind test)"); fails += 1
        for m in C.finditer(line):
            tgt = m.group(1) or m.group(3) or ""
            if tgt and tgt not in self_name:
                print(f"  [C] {p}:{i} — cross-file line anchor into {tgt} (use a section ref)"); fails += 1

print(f"\ncheck_traycer_chain: {'PASS — all 3 classes clean' if not fails else f'FAIL — {fails} violation(s)'}")
sys.exit(1 if fails else 0)
