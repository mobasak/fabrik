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
    Both rules read the SAME walk, `_tables` (W-76c49aa8): two walks with two notions of "inside a table"
    disagreed with GFM — a "``` info" line read as a fence closer, a header GFM rejects still read as a
    table by the span rule — and `_tables`' docstring carries the boundaries and the three shapes it
    RECORDS rather than reads, each with its live count. Unicode pipe look-alikes stay out by design: the
    regex names the GFM escape and the HTML entity spellings, nothing else.

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
# A fence marker: three or more backticks or tildes at the line start, and whatever follows the run
# (GFM closes a fence only with the same character in a run at least as long and NOTHING but
# whitespace after it — `_tables` carries the opening run to compare and reads the tail).
_FENCE = re.compile(r"^(`{3,}|~{3,})(.*)$")
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


# A list item's opener — the marker and the spaces after it; its length is the item's content column.
_LIST_ITEM = re.compile(r"^ {0,3}(?:[-*+]|\d{1,9}[.)]) +")
# An ATX heading (one to six `#` then a space or the line's end — `#tag` is text) and a thematic break
# (three or more of one of `-*_`, spaces between, up to three of indent): each ends a list item's lazy
# region, as a blank line does.
_ATX = re.compile(r"^#{1,6}(?:\s|$)")
_THEMATIC = re.compile(r"^ {0,3}([-*_])(?: *\1){2,} *$")


def _cells(row: str) -> int:
    """The number of cells GFM splits a `|…|` row into — one more than its unescaped inner pipes."""
    return len(_PIPE.findall(row[1:-1])) + 1


def _tables(text: str):
    r"""ONE walk for both rules — every table GFM renders, and every header it rejects.

    Yields `("table", header_cells, rows)` with `rows` the `(lineno, stripped_line)` pairs of the
    header and every body row (the delimiter row is never a row), and `("rejected", lineno,
    header_cells, delimiter_cells, line)` for a header whose cell count disagrees with its delimiter
    row — GFM renders NO table there, so the width rule reports it and the span rule never reads
    its rows. Two walks that each kept their own notion of "inside a table" disagreed with GFM on
    the shapes below (W-76c49aa8); this is the single notion, each boundary measured against
    markdown_it before it was written:

    * FENCES are tracked by CHARACTER and run LENGTH as GFM does — a ```` fence is closed only by
      four or more backticks, never by an inner ```; a `~~~` line inside a backtick fence closes
      nothing; a marker indented 4+ is code, not a fence; a closer carries NOTHING but whitespace
      after its run, so a "``` info" line opens or continues a fence and never closes one; and a
      backtick opener whose info string carries a backtick is a text line, not a fence.
    * A multi-line HTML COMMENT is skipped; an opener inside a fence is fence content.
    * INDENTATION — GFM accepts a table indented up to 3 spaces and treats 4+ as a code block (an
      `rstrip()`-only test once missed `CLAUDE.md`'s own 3-space-indented § Orient routing table);
      a TAB counts as four columns; a BOM before the first line is dropped.
    * LAZY CONTINUATION — a `|…|` line indented less than the content column of the list item above
      it, with no blank line between, continues that item's paragraph, and GFM renders no table; so
      does any line after a blockquote line until a blank one. A blank line, a heading or a fence
      ends the region; a table indented to the item's content column is list content and is read.
    * A run of `|…|` lines is a table only when its first line is followed by a `_DELIM` row whose
      cell count EQUALS the header's — a lone `| a | b |` paragraph line is not a table to GFM, and
      a header with an unescaped pipe inflates its width so that GFM renders no table at all (the
      rejected-header record is what the width rule reports there, once, strictly worse than an
      overflowing row; the rows under a rejected header are text to both rules). Any non-row line
      ends the table, so a document with several tables of different widths is read against each
      header in turn.

    RECORDED, not read — shapes where this walk and GFM still disagree, each live 0 over the 2
    contracts + 57 packs on 2026-10-23 and 0 over 50 fleet repos' CLAUDE.md and packs (2,900 files,
    the Opus critique seat's census; probe inputs in `tests/enforcement/test_check_governance_tables.py`).
    SILENT misses — GFM renders a table this walk never sees, so a rule in it is unchecked, never
    mis-reported: a table inside a BLOCKQUOTE (`> | a | b |`); rows with NO leading or trailing pipe
    (`a | b` over `---|---`, and a header with a leading pipe only, `| a | b`, which the width rule
    caught by accident before this walk — its delimiter row read as the header); a table nested in a
    LIST ITEM at indent 4, which GFM reads as list content and this walk as the code block it would
    be outside a list; and a prose line GLUED under a table row with no blank line, which GFM reads
    as a lazy ROW of that table (spec example 201) and this walk as the table's end — live once,
    `templates/governance/CLAUDE.md`'s "FIRST, ahead of every test below" paragraph renders as the
    Stage table's 10th row in the template and its 49 fleet copies (filed; the hub contract has the
    blank line), with no pipe in it, so no finding is lost today. One FALSE-POSITIVE shape — this
    walk reads a table GFM does not: a table inside an HTML BLOCK (`<details>` with no blank line
    before the rows), where a type-7 HTML-block rule would also misread a paragraph opening with an
    inline tag. A span whose closing run of backticks is unbalanced is read by `_SPAN`'s shortest
    match (D-1133's recorded gap). Each needs its own grammar for shapes no governance contract or
    pack has carried a pipe in; a census that finds one promotes it.
    """
    lines = text.lstrip("\ufeff").split("\n")
    fence: str | None = None  # the opening run (``` or ~~~~), None outside a fence
    commented = False
    # A list item or blockquote line opens a LAZY region: until a blank line (or a heading or fence),
    # a line indented less than the item's content column continues that paragraph, and GFM renders no
    # table from it — `lazy_below` is that column (a blockquote's is unbounded).
    lazy_below: int | None = None
    header_cells = 0
    rows: list[tuple[int, str]] | None = None
    idx = 0
    while idx < len(lines):
        expanded = lines[idx].expandtabs(4)
        stripped = expanded.strip()
        indent = len(expanded) - len(expanded.lstrip(" "))
        if commented:
            if "-->" in stripped:
                commented = False
            idx += 1
            continue
        marker = _FENCE.match(stripped) if indent < 4 else None
        if marker and marker.group(1)[0] == "`" and "`" in marker.group(2):
            marker = None  # a backtick fence's info string may not carry a backtick: a text line
        if fence is not None:
            if (
                marker
                and marker.group(1)[0] == fence[0]
                and len(marker.group(1)) >= len(fence)
                and not marker.group(2).strip()
            ):
                fence = None
            idx += 1
            continue
        if not stripped or marker or _ATX.match(stripped) or _THEMATIC.match(expanded):
            lazy_below = None  # a blank line, a fence, a heading or a thematic break ends the item
        is_row = (
            indent < 4 and stripped.startswith("|") and stripped.endswith("|") and len(stripped) > 1
        )
        if is_row and lazy_below is not None and indent < lazy_below:
            is_row = False  # a lazy continuation line of the item above, not a table to GFM
        opens_comment = stripped.startswith("<!--") and "-->" not in stripped
        if marker or opens_comment or not is_row:
            if rows is not None:
                yield ("table", header_cells, rows)
                rows = None
            if marker:
                fence = marker.group(1)
            elif opens_comment:
                commented = True
            elif indent < 4 and stripped.startswith(">"):
                lazy_below = 10**6  # a blockquote line; at indent 4 a `>` line is code or lazy text
            else:
                item = _LIST_ITEM.match(expanded)
                if item and not _THEMATIC.match(expanded):  # `* * *` is a break, not an item
                    lazy_below = len(item.group(0))
            idx += 1
            continue
        if rows is None:
            nxt = lines[idx + 1].expandtabs(4).strip() if idx + 1 < len(lines) else ""
            if not _DELIM.match(nxt):
                idx += 1  # a pipe-led paragraph line, not a table
                continue
            header_cells = _cells(stripped)
            delimiter_cells = _cells(nxt)
            if delimiter_cells != header_cells:
                yield ("rejected", idx + 1, header_cells, delimiter_cells, stripped)
                idx += 1
                continue
            rows = [(idx + 1, stripped)]
            idx += 2  # the delimiter row is proof, never a row
            continue
        rows.append((idx + 1, stripped))
        idx += 1
    if rows is not None:
        yield ("table", header_cells, rows)


def _overflowing_rows(text: str) -> list[tuple[int, int, int, str]]:
    """Rows GFM renders with fewer cells than they carry — i.e. rows losing content — and headers
    GFM rejects (reported in their own right: no table renders there at all). The walk is `_tables`."""
    out: list[tuple[int, int, int, str]] = []
    for token in _tables(text):
        if token[0] == "rejected":
            _, lineno, cells, delimiter_cells, line = token
            out.append(
                (
                    lineno,
                    cells,
                    delimiter_cells,
                    "HEADER width disagrees with its delimiter "
                    "row — GFM renders NO table here: " + line[:60],
                )
            )
            continue
        _, header, rows = token
        for lineno, line in rows[1:]:
            cells = _cells(line)
            if cells > header:
                out.append((lineno, cells, header, line[:70]))
    return out


def _piped_spans(text: str) -> list[tuple[int, str]]:
    r"""Code spans inside a delimiter-confirmed table row that carry a table-escaped pipe.

    The walk is `_tables`; here the row is split into CELLS on unescaped pipes before spans are
    read, as GFM does, so a span never crosses a cell, and a backslash-escaped backtick is text,
    never a delimiter. A `\|` in a row OUTSIDE any span is the sanctioned prose escape and never a
    finding here; outside a table GFM leaves a code span's `\|` literal for both readers, so a row
    GFM does not render as a table (a rejected header's) is never read.
    """
    out: list[tuple[int, str]] = []
    for token in _tables(text):
        if token[0] != "table":
            continue
        for lineno, line in token[2]:
            for cell in _PIPE.split(line[1:-1]):
                cell = cell.replace(
                    "\\`", "\x00"
                )  # an escaped backtick is text, not a span delimiter
                for m in _SPAN.finditer(cell):
                    if _SPAN_PIPE.search(m.group(2)):
                        out.append((lineno, m.group(0).replace("\x00", "\\`")))
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
