#!/usr/bin/env python3
# AFTER-EDIT: CLAUDE.md | templates/governance/CLAUDE.md
"""A governance RULE that lives in a markdown table row must survive rendering.

GFM splits a table row on every `|` — inside a code span too — and DISCARDS the cells past the
header's width. So one unescaped pipe in a rule's own text silently truncates that rule for every
rendered reader (GitHub, an IDE preview, any table parser), while the raw file still reads fine.
Nothing else catches it: no gate parses these tables into cells, and the file is valid markdown.

MEASURED, which is why this check exists at all (CLAUDE.md § THE FIX DIRECTIVE 5 — a detector is
justified by its fire rate, not by the idea):
  * The denominator HARD STOP row carried THREE unescaped pipes from 2026-09-03 to 2026-09-10 — two
    with the FIFTH shape's `git diff | grep …` example (adce3017) and the third with the SIXTH
    shape's `grep -c` table example (66aa32a5). Rendered with markdown_it-py, the 5-cell row produced
    2 cells: the FIFTH shape was cut mid-sentence at the first stray pipe and the SIXTH was gone
    entirely — a week of governance no rendered reader could see, in the hub's own contract AND in
    `templates/governance/CLAUDE.md`, the one of the two that actually ships to ~46 repos (the hub
    contract is never distributed — `fabrik_synced_manifest.py`'s hub/project split).
  * Scope discipline: the same rule over every markdown table under `CLAUDE.md`, `templates/governance/`,
    `.windsurf/rules/`, `docs/`, `commands/_sources/` and `commands/_fragments/` — all of each, archives
    included — fired 128 times over 41,115 rows in 1,301 files when measured 2026-09-10: archived
    plans, specs, ledger rows whose extra pipes sit harmlessly in prose. That is wallpaper, and
    wallpaper is how enforcement dies, so this check is scoped to the GOVERNANCE CONTRACTS only,
    where a truncated row is a truncated RULE. On that scope it fires 0 times clean and exactly once
    per file against the defect it was written for. (An earlier draft of that figure was
    127/34,415/1,117 — the same scan with `*/archive/*` silently excluded, a bound nobody declared,
    on the check that guards the denominator rule. A reviewer could not reproduce it, which is how it
    was caught. Re-derive it before quoting it: the tree moves.)

Fail direction: ADVISORY on landing, per the standing rollout law (advisory first, fire rate
measured, promoted on evidence). Expected rate is zero; one fire is a real regression.

⚠️ THE EXIT CODE IS THE CONTRACT, and it is easy to get backwards. `final_gate.run_optional_check`
documents `warn_only` as "this check has no failing exit path BY CONTRACT … a warn_only check that
somehow exits non-zero still FAILS the gate" — so an advisory check that returns 1 on a finding does
not warn, it HARD-FAILS every gate in ~46 synced repos the first time it fires, which is exactly the
run it exists for. Every one of the other 32 warn_only checks returns 0 on every path (see
`check_routing_policy.py`, six `return 0`); the stdout IS the product. So: `main()` returns 0 always,
and `--strict` (never used by the gate) returns 1 on findings, which is what a regression test binds
to and what a future promotion to blocking would flip.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# An unescaped pipe — the cell separator GFM splits on.
_PIPE = re.compile(r"(?<!\\)\|")
# A GFM delimiter row: the line under a header that makes a table a table.
_DELIM = re.compile(r"^\|(?:\s*:?-+:?\s*\|)+$")

# The governance contracts: a rule truncated here is a rule the fleet cannot read.
_TARGETS = ("CLAUDE.md", "templates/governance/CLAUDE.md")


def _root() -> Path:
    """The repo this script belongs to — resolved from __file__, never the cwd.

    A hub `git worktree` carries the full tree and must resolve to itself; a synced project copy
    lands at <project>/scripts/enforcement/ and resolves to the project, where the only target is
    its own CLAUDE.md (the template's destination).
    """
    return Path(__file__).resolve().parent.parent.parent


def _overflowing_rows(text: str) -> list[tuple[int, int, int, str]]:
    """Rows GFM renders with fewer cells than they carry — i.e. rows losing content.

    Header width is re-established at every table (any non-row line ends the current table), so a
    document with several tables of different widths is read correctly rather than against the
    first header in the file.

    Three boundaries, each measured against `markdown_it` rather than assumed (an author-blind seat
    found all three by building fixtures and rendering them):

    * INDENTATION — GFM accepts a table indented up to 3 spaces and treats 4+ as a code block. An
      `rstrip()`-only test missed `CLAUDE.md`'s own 3-space-indented § Orient routing table, so the
      check reported OK while GFM discarded that table's rule text. Live in the guarded file, not
      hypothetical.
    * FENCES — a fenced block of pipe-leading lines is not a table, and a rule ABOUT bad table rows
      is exactly the document that grows a fenced example of one. Firing there is a false positive,
      and a false positive is how enforcement becomes wallpaper.
    * THE HEADER ROW ITSELF — an unescaped pipe in the header inflates the width, so no body row can
      ever exceed it and the check is silent while GFM renders no table AT ALL: strictly worse than
      the defect this exists for. The delimiter row is what proves a table is a table, so a header
      whose width disagrees with its delimiter is reported in its own right.
    """
    out: list[tuple[int, int, int, str]] = []
    header: int | None = None
    fenced = False
    lines = text.split("\n")
    for idx, raw in enumerate(lines):
        lineno = idx + 1
        stripped = raw.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            fenced = not fenced
            header = None
            continue
        if fenced:
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        line = stripped
        if indent < 4 and line.startswith("|") and line.endswith("|") and len(line) > 1:
            cells = len(_PIPE.findall(line[1:-1])) + 1
            if header is None:
                header = cells  # first row of this table sets the width
                nxt = lines[idx + 1].strip() if idx + 1 < len(lines) else ""
                if _DELIM.match(nxt):
                    delim_cells = len(_PIPE.findall(nxt[1:-1])) + 1
                    if delim_cells != cells:
                        out.append(
                            (
                                lineno,
                                cells,
                                delim_cells,
                                "HEADER width disagrees with its delimiter "
                                "row — GFM renders NO table here: " + line[:60],
                            )
                        )
            elif cells > header:
                out.append((lineno, cells, header, line[:70]))
        else:
            header = None
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=(__doc__ or "governance table integrity").splitlines()[0]
    )
    ap.add_argument(
        "--strict",
        action="store_true",
        help="exit 1 when a row overflows (regression tests and a future promotion to blocking; "
        "the gate never passes this — see the exit-code contract in the module docstring)",
    )
    opts = ap.parse_args(argv)
    root = _root()
    checked = 0
    findings: list[str] = []
    for rel in _TARGETS:
        path = root / rel
        if not path.is_file():
            continue  # a project copy has no templates/ tree — absence is not a defect
        checked += 1
        for lineno, cells, header, preview in _overflowing_rows(
            path.read_text(encoding="utf-8", errors="replace")
        ):
            findings.append(
                f"  ⚠ {rel}:{lineno}: table row renders {cells} cells against a {header}-cell header — "
                f"an unescaped `|` (escape it as `\\|`, even inside a code span) truncates this rule "
                f"for every rendered reader: {preview}…"
            )
    if not checked:
        print("check_governance_tables: SKIPPED — no governance contract found under this root")
        return 0
    if findings:
        print(
            "⚠ check_governance_tables ADVISORY — a rule that does not render is a rule nobody reads:"
        )
        print("\n".join(findings))
        return 1 if opts.strict else 0
    print(
        f"check_governance_tables: OK — every table row renders at its header width across {checked} contract(s)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
