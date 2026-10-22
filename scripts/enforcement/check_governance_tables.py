#!/usr/bin/env python3
# AFTER-EDIT: CLAUDE.md | templates/governance/CLAUDE.md | .windsurf/rules/ | tests/enforcement/test_check_governance_tables.py
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
  * Scope today (W-80ffca68, 2026-10-22): the two governance contracts PLUS every `.windsurf/rules/**/*.md`
    file (57 packs at 778bf73f7, synced to ~46 repos; EVERY markdown file under that directory, pack or
    not — a table row there meets the same two readers) — the packs measured 0 width fires over 2096
    row-shaped lines (each starts and ends with a pipe, fences skipped: 218 headers + 218 delimiter rows +
    1660 body rows — a plain leading-pipe grep also counts two TypeScript union lines and says 2098), so
    widening the width rule to them is free; `docs/` and `commands/` stay out (the 128 wallpaper
    fires above). The packs joined for the SECOND rule below.

THE SECOND RULE — a pipe spelled to survive a table, inside a CODE SPAN (`_piped_spans`). Inside a table
row GFM un-escapes `\\|` to `|` even inside a code span (markdown_it: `` `str \\| None` `` → `str | None`),
but a rule pack reaches an agent RAW, where `str \\| None` is invalid Python, `process.env.X \\|\\| 'default'`
invalid JS and `invalid\\|wrong-browser` a non-URL — the two readers disagree, exactly and only inside a
table row (outside, GFM leaves `\\|` literal and both agree; a GNU BRE `grep 'a\\|b'` there is legitimate,
and `commands/` carries five such spans, which is why this rule is scoped to delimiter-confirmed table
rows and the commands stay out). Measured before the fix: 13 of 13 backslash-pipes in the packs sat in
row code spans (`app-audit-log.md` 9, `10-python.md`, `12-node.md`, `self-healing.md`, `60-saas-ui.md`
one each); 0 in prose; 0 in the two contracts. The remedy is in `SPAN_REMEDY`.
  * COBRA (D-253): the cheapest way to silence a `\\|` finding is `&#124;` — and GFM does NOT decode an
    entity inside a code span (`str &amp;#124; None` rendered), so it is wrong for BOTH readers: the same
    defect, caught by the same regex (decimal and hex forms with leading zeros, the three named entities).
    The known gaps of both walks — shapes GFM renders as a table or as text that this stdlib walk reads
    otherwise — are ENUMERATED with their probe inputs, their fail direction and their live count (each 0 over
    the 57 packs + 2 contracts on 2026-10-22) in work item W-76c49aa8, the one owner of that list; this
    docstring does not restate it. Unicode pipe look-alikes stay out by design: the regex names the GFM
    escape and the HTML entity spellings, nothing else.

Fail direction: ADVISORY on landing, per the standing rollout law (advisory first, fire rate
measured, promoted on evidence). Expected rate is zero; one fire is a real regression.

⚠️ THE EXIT CODE IS THE CONTRACT, and it is easy to get backwards. `final_gate.run_optional_check`
documents `warn_only` as "this check has no failing exit path BY CONTRACT … a warn_only check that
somehow exits non-zero still FAILS the gate" — so an advisory check that returns 1 on a finding does
not warn, it HARD-FAILS every gate in ~46 synced repos the first time it fires, which is exactly the
run it exists for. Every one of the other 21 warn_only checks returns 0 on every path (see
`check_routing_policy.py`, six `return 0`); the stdout IS the product. ⚠️ Derive that figure with
`grep -cE '^\\s+warn_only=True,\\s*$' scripts/final_gate.py` → 22 REGISTRATIONS, of which this check is
one. A bare `grep -c 'warn_only=True'` returns 33 because eleven of those lines are comments and one is
the f-string that PRINTS the phrase — a structural line counted as a data row, which is the SIXTH shape
of the very HARD STOP this check guards, and it is how an earlier draft of this sentence said 32. So: `main()` returns 0 always,
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
# A code span — single or double backticks, the closer the same run as the opener.
_SPAN = re.compile(r"(`+)(.+?)\1")
# A fence marker: three or more backticks or tildes at the line start (GFM closes a fence only with the
# same character in a run at least as long — `_piped_spans` carries the opening run to compare).
_FENCE = re.compile(r"^(`{3,}|~{3,})")
# A pipe spelled to survive a table: the GFM escape, or an HTML entity (decimal or hex, leading zeros
# allowed by CommonMark, or one of the three named forms) — see THE SECOND RULE in the module docstring.
_SPAN_PIPE = re.compile(r"\\\||&#0*124;|&#[xX]0*7[cC];|&(?:vert|verbar|VerticalLine);")

# THE REMEDY, as its own constant — it is ADVICE that ships to ~46 repos, so it is the most
# consequential string in this file and it must be editable only deliberately. An earlier draft
# said "escape it as `\\|`, even inside a code span", which is the exact defect this change fixed:
# these contracts are read RAW as well as rendered, and `\\|` is alternation in GNU BRE, so escaping
# inside a code span silently changes what the example command does. `test_remediation_is_the_pinned_
# text` holds a byte-for-byte copy, so any rewording fails until it is changed in BOTH places.
REMEDY = (
    "an unescaped `|` truncates this rule for every rendered reader — escape it as `\\|` in PROSE, "
    "but inside a CODE SPAN rephrase the example so it carries no literal pipe: `\\|` is alternation "
    "in GNU BRE and these contracts are read RAW as well as rendered, so escaping there silently "
    "changes what the example command does."
)

# The second remedy — pinned byte-for-byte by `test_span_remediation_is_the_pinned_text` for the same reason.
SPAN_REMEDY = (
    "a table-escaped pipe inside a CODE SPAN is `|` to the rendered reader and a literal "
    "backslash-pipe to the RAW reader (invalid Python, JS or URL; alternation in GNU BRE) — rephrase so "
    "the span carries no pipe: move the alternation into prose beside the span, split the span in two, "
    "or lift the example into a fenced block; never an HTML entity (`&#124;` stays literal for BOTH "
    "readers)."
)

# The governance contracts: a rule truncated here is a rule the fleet cannot read.
_TARGETS = ("CLAUDE.md", "templates/governance/CLAUDE.md")
# The rule packs — the same contract, synced to ~46 repos (W-80ffca68); read by glob so a new pack joins
# without an edit here. An absent directory yields nothing: the roster line names both counts so a lost
# glob is visible.
_PACK_GLOB = ".windsurf/rules/**/*.md"


def _root() -> Path:
    """The repo this script belongs to — resolved from __file__, never the cwd.

    A hub `git worktree` carries the full tree and must resolve to itself; a synced project copy
    lands at <project>/scripts/enforcement/ and resolves to the project, where the targets are its
    own CLAUDE.md (the template's destination) and its synced `.windsurf/rules/` packs.
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


def _piped_spans(text: str) -> list[tuple[int, str]]:
    r"""Code spans inside a delimiter-confirmed table row that carry a table-escaped pipe.

    Its own walk, deliberately: `_overflowing_rows`' state machine (header reset on every non-row
    line, next-line delimiter read) is load-bearing for the width rule and is not refactored here.
    The boundaries, each one measured against markdown_it by a review seat before it was written:
    FENCES are skipped and tracked by CHARACTER and LENGTH as GFM does (a ```` fence is closed only
    by four or more backticks, never by an inner ```; a `~~~` line inside a backtick fence closes
    nothing; a marker indented 4+ is code, not a fence); a multi-line HTML COMMENT is skipped, and an
    opener inside a fence is fence content, not a comment; a TAB counts as four columns, so a
    tab-indented table is the code block GFM makes of it; a BOM before the first line is dropped; a
    run of `|…|` lines counts only when its first line is followed by a `_DELIM` row — a lone
    `| a | b |` paragraph line is not a table to GFM, so its `\|` stays literal for both readers and
    is left alone; the row is split into CELLS on unescaped pipes before spans are read, as GFM does,
    so a span never crosses a cell; and a backslash-escaped backtick is text, never a delimiter. A
    `\|` in a row OUTSIDE any span is the sanctioned prose escape and never a finding here.
    """
    out: list[tuple[int, str]] = []
    lines = text.lstrip("\ufeff").split("\n")
    fence: str | None = None  # the opening run (``` or ~~~~), None outside a fence
    commented = False
    in_table = False
    for idx, raw in enumerate(lines):
        expanded = raw.expandtabs(4)
        stripped = expanded.strip()
        indent = len(expanded) - len(expanded.lstrip(" "))
        if commented:
            if "-->" in stripped:
                commented = False
            continue
        marker = _FENCE.match(stripped) if indent < 4 else None
        if fence is not None:
            if marker and marker.group(1)[0] == fence[0] and len(marker.group(1)) >= len(fence):
                fence = None
            continue
        if marker:
            fence = marker.group(1)
            in_table = False
            continue
        if stripped.startswith("<!--") and "-->" not in stripped:
            commented = True
            in_table = False
            continue
        is_row = (
            indent < 4 and stripped.startswith("|") and stripped.endswith("|") and len(stripped) > 1
        )
        if not is_row:
            in_table = False
            continue
        if not in_table:
            nxt = lines[idx + 1].expandtabs(4).strip() if idx + 1 < len(lines) else ""
            if not _DELIM.match(nxt):
                continue  # a pipe-led paragraph line, not a table
            in_table = True
        for cell in _PIPE.split(stripped[1:-1]):
            cell = cell.replace("\\`", "\x00")  # an escaped backtick is text, not a span delimiter
            for m in _SPAN.finditer(cell):
                if _SPAN_PIPE.search(m.group(2)):
                    out.append((idx + 1, m.group(0).replace("\x00", "\\`")))
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=(__doc__ or "governance table integrity").splitlines()[0]
    )
    ap.add_argument(
        "--strict",
        action="store_true",
        help="exit 1 on a finding — a row that overflows, or a code span carrying a table-escaped pipe "
        "(regression tests and a future promotion to blocking; the gate never passes this — see the "
        "exit-code contract in the module docstring)",
    )
    opts = ap.parse_args(argv)
    root = _root()
    contracts = [root / rel for rel in _TARGETS if (root / rel).is_file()]
    packs = sorted(p for p in root.glob(_PACK_GLOB) if p.is_file())
    checked = len(contracts) + len(
        packs
    )  # a project copy has no templates/ tree — absence is not a defect
    findings: list[str] = []
    for path in contracts + packs:
        rel = path.relative_to(root).as_posix()
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            # `main()` returns 0 ALWAYS (see the exit-code contract above) — and an OSError is the one
            # door that reached a non-zero exit anyway, which `run_optional_check` promotes to a gate
            # FAILURE in every synced repo while blaming the registration. Report it as what it is.
            findings.append(
                f"  ⚠ {rel}: could not be read ({exc.__class__.__name__}) — not checked"
            )
            continue
        for lineno, cells, header, preview in _overflowing_rows(text):
            findings.append(
                f"  ⚠ {rel}:{lineno}: table row renders {cells} cells against a "
                f"{header}-cell header — {REMEDY} The row: {preview}…"
            )
        for lineno, span in _piped_spans(text):
            findings.append(
                f"  ⚠ {rel}:{lineno}: code span carries a table-escaped pipe — {SPAN_REMEDY} "
                f"The span: {span}"
            )
    if not checked:
        print(
            "check_governance_tables: SKIPPED — no governance contract or rule pack found under this root"
        )
        return 0
    if findings:
        print(
            "⚠ check_governance_tables ADVISORY — a rule that does not render is a rule nobody reads:"
        )
        print("\n".join(findings))
        return 1 if opts.strict else 0
    print(
        "check_governance_tables: OK — every table row renders at its header width and no code span "
        f"carries a table-escaped pipe across {len(contracts)} contract(s) + {len(packs)} pack(s)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
