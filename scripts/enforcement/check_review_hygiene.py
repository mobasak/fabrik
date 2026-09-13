#!/usr/bin/env python3
# AFTER-EDIT: tests/enforcement/test_check_review_hygiene.py docs/workflows/FINAL_GATE_WORKFLOW.md
"""Review hygiene — the grep-shaped classes every review re-sweeps. ADVISORY, ALWAYS exits 0.

The orchestrator runs this at the START of every review round on that round's surface, again at
the round's CLOSE, and at the flip (spec D4/DD6/DD13, docs/superpowers/specs/
2026-09-08-review-convergence-redesign-design.md). A hit is a CANDIDATE, not a verdict: the
orchestrator adjudicates each one into the receipt's ledger as FIXED or as
``RECORDED — hygiene false positive (<why>)`` — the verdict form the coverage gate's ``VERDICT``
accepts (``check_review_coverage.py``, D-206).

Three of the four classes — template-residue, fence-parity, table-parity — run only on surfaces
whose name ends in `.md` (the `path.endswith(".md")` gates in `_surface_hits`; `SURFACE_SUFFIXES`
is only the directory-walk filter); a pin copied to a non-.md name gets the stale-phrase, claim and
changelog classes alone, and the summary line reads the same — copy a pin as `<name>.md` (T4.7,
01M285X4H).

Classes (each hit is a `path:line` with its class name):
  template-residue   an unrendered fragment marker or parameter in an `.md` on the surface — the
                     renderer's own shapes only, anchored at both braces: `{{include:<name>}}` or
                     `{{UPPER_CASE}}` (a Go template such as `{{.Image}}` or a doc's literal
                     `{{…}}` is not residue). NOT covered by ``check_command_corpus.py``, whose
                     `{{` tests are PRESENCE tests for `{{include:run-record}}`, never residue tests.
  fence-parity       an unclosed code fence, by the CommonMark same-char-run rule.
  raw-pipe           a receipt table row whose cell count differs from its header's — an
                     unescaped `|` inside a cell (F280's class).
  table-parity       the same cell-count defect on ANY `.md` surface (a spec, a plan, a rendered
                     command) — one shared helper, named by where it was found; fenced and
                     commented lines are blanked first, as the receipt path already does.
  dual-verdict       a receipt table cell carrying more than one BARE verdict word (F314's class:
                     its cell carries `RECORDED` twice and matches ``VERDICT`` zero times, so a
                     VERDICT-based detector is blind to it).
  changelog-entry    ``check_changelog.py``'s ``check_changelog_quality()`` — called, not copied.
  dead-symbol        a `--symbol` the surface references 0 times.
  stale-phrase       a `--phrase` the brief named as stale — matched across a line wrap, never
                     across a blank line; one row per line (the same walk as `claim`).
  claim              a `--claim` term's mirror sites, LISTED for the pre-pin sweep (D10 rule 2) —
                     never a verdict; a `claim` row pasted into a receipt is dispositioned
                     ``RECORDED — measured (<n> mirrors read)`` — a verdict form
                     ``check_review_coverage.py`` already accepts — never FIXED or false positive.

CONTRACT: this script has NO failing exit path. It is registered ``warn_only=True`` in
``final_gate.py`` and invoked by the orchestrator; it is NOT a pre-commit hook and it writes to no
file. A non-zero exit from a ``warn_only`` check is a BLOCKING red across ~46 repos
(``check_retired_terms.py``'s contract), so every path here returns 0.

GRADUATION (DD6): it stays advisory until infra measures its false-positive rate below 5 % over
20 receipts, counted from the receipts' own ``RECORDED — hygiene false positive (…)`` rows. Do not
add a blocking mode before that measurement exists.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

_HERE = Path(__file__).resolve().parent

try:
    from .check_review_coverage import _table_rows  # type: ignore[import-not-found]
except ImportError:  # direct-script invocation
    sys.path.insert(0, str(_HERE))
    from check_review_coverage import _table_rows  # type: ignore[no-redef]

# Anchored at BOTH braces to the renderer's two shapes — a marker (`include:` + a name) or a
# parameter (an upper-case letter, then upper-case letters, digits, underscores). An unanchored
# upper-case-initial rule would still fire on `{{.Image}}`; this one cannot (it starts with a dot).
TEMPLATE_RESIDUE = re.compile(r"\{\{(?:include:[^{}\s]+|[A-Z][A-Z0-9_]*)\}\}")
# BARE verdict WORDS, deliberately not `VERDICT` (T02 → T08, spine § Interfaces): F314's cell
# reads `RECORDED — the F250 shape …`, which carries two bare RECORDEDs and satisfies the
# widened `VERDICT` zero times. Counting VERDICT matches here would miss the whole class.
VERDICT_WORD = re.compile(r"\b(?:CLEAN|FIXED|REFUTED|ROUTED|RECORDED)\b")
_TALLY = re.compile(r"\b(?:CLEAN|FIXED|REFUTED|ROUTED|RECORDED)\s+\d{1,3}(?![\w-])")
# ⚠️ A verdict word FOLLOWED BY A BOUNDED COUNT is a TALLY REFERENCE, not a disposition — `the
# round-14 tally reads FIXED 12 · RECORDED 2`. Structural (the word, then a short number that ends
# there), not a phrase list: the receipts write tallies in several spellings and a hand-listed set
# is one entry away from the next bypass. Round 1 measured this on the D-191 receipt's own
# remediation row (`:694`); round 2 narrowed it from "a digit on EITHER side", which also ate
# `F280 FIXED` and `round 14 FIXED`; round 3 BOUNDED the number, because an unbounded `\d` read a
# DATE or an ID as a count (`FIXED 2026-09-09`, `ROUTED 01M1K6A15M` — every hub mail id starts
# `01M`, so the whole disposition vanished). The lookahead is `(?![\w-])`, not `(?![\d-])`: `01M`
# ends its digit run at a LETTER, which a digits-only lookahead happily accepts.


def _verdict_words(cell: str) -> list[str]:
    r"""The verdict words in a cell that are DISPOSITIONS, tally references dropped.

    A TALLY is the verdict word FOLLOWED by a BOUNDED count — `FIXED 12 · RECORDED 2`. Two shapes
    are NOT tallies: a digit BEFORE the word (`F280 FIXED — escaped the pipe` is a finding id,
    `round 14 FIXED; round 15 REFUTED` is two real dispositions — both silently eaten by round 1's
    symmetric adjacency rule), and a long token AFTER it (`FIXED 2026-09-09` is a date,
    `ROUTED 01M1K6A15M to infra` a mail id — both eaten by round 2's unbounded `\d`).

    ⚠️ STATED COST, two shapes, both by design. (a) A cell that is nothing but a LEADING count —
    `6 FIXED · 1 REFUTED`, `5 FIXED / 16 REFUTED` — fires, because nothing structural separates it
    from two dispositions written side by side. (b) A tally with PUNCTUATION between the word and
    the number — `FIXED — 12 rows`, `RECORDED — 2 · FIXED — 3` — fires, because the same
    `<word> — <text>` shape is exactly how an honest single disposition is written. Both are
    Pass-Ledger/tally cells the orchestrator adjudicates
    `RECORDED — hygiene false positive (a tally, not a disposition)`; that adjudication is DD6's
    own measurement input.

    ⚠️ And the cost in the OTHER direction, a false NEGATIVE: the tally is DELETED before the words
    are counted, so a genuine disposition that opens with a small count is erased with it —
    `FIXED 12 of the rows and REFUTED 1` and `RECORDED 2 as false positives; FIXED 1` both score
    zero verdict words, not two. Measured at 8092e8a8: 0 of the 9 live tally fires are of that
    shape, so the rule stays as it is; the shape is named here so the next reader does not have to
    rediscover it.
    """
    return VERDICT_WORD.findall(_TALLY.sub("", cell))


REVIEWS_PREFIX = "docs/development/reviews/"
SURFACE_SUFFIXES = (".md", ".py")


@dataclass(frozen=True)
class Hit:
    cls: str
    path: str
    line: int
    what: str
    occurrences: int = 1  # T4.7: one row per (path, line, class, what); the count rides here

    def as_dict(self) -> dict[str, object]:
        return {
            "class": self.cls,
            "path": _display(self.path),
            "line": self.line,
            "what": self.what,
            "occurrences": self.occurrences,
        }

    def line_out(self) -> str:
        times = f" (×{self.occurrences})" if self.occurrences > 1 else ""
        return f"[ADVISORY] {self.cls} {_display(self.path)}:{self.line} — {self.what}{times}"


_LABEL: dict[str, str] = {}  # T4.7 (--label): the artifact name a scratch COPY stands for


def _display(path: str) -> str:
    """Repo-relative when the path is under the cwd, absolute otherwise. The gate's no-argument
    mode self-selects ABSOLUTE receipt paths; printing those raw makes every advisory line
    machine-specific and unclickable from the repo root. A `--label` names the artifact a
    scratch copy stands for (T4.7)."""
    if path in _LABEL:
        return _LABEL[path]
    try:
        rel = os.path.relpath(path)
    except (OSError, ValueError):  # different drive / unresolvable
        return path
    return path if rel.startswith("..") else rel


# --------------------------------------------------------------------------- fence parity
# COPIED from `_fence_step` in scripts/enforcement/check_command_corpus.py:832-851 (numbered at
# 8092e8a8) — a private helper of a sibling check, so it is copied with attribution rather than
# imported. Keep the two in step: the rule is CommonMark's, not ours.
def _fence_step(line: str, fence_char: str, fence_len: int) -> tuple[str, int, bool]:
    """CommonMark fence state after `line`: (char, length, this-line-is-a-fence). A fence closes
    only on a same-char run at least as long with NO info string — a bare toggle let one nested or
    info-string fence invert the state for the rest of the file."""
    fence = re.match(r"(`{3,}|~{3,})(.*)$", line.lstrip())
    if not fence:
        return fence_char, fence_len, False
    run, rest = fence.group(1), fence.group(2).strip()
    if run[0] == "`" and "`" in rest:
        # CommonMark 4.5: a backtick fence's info string may not hold a backtick — the line is text
        return fence_char, fence_len, False
    if not fence_char:
        return run[0], len(run), True
    if run[0] == fence_char and len(run) >= fence_len and not rest:
        return "", 0, True
    return fence_char, fence_len, False


def _fence_hits(path: str, lines: list[str]) -> list[Hit]:
    char, length, opened_at = "", 0, 0
    for i, ln in enumerate(lines, start=1):
        was_open = bool(char)
        char, length, is_fence = _fence_step(ln, char, length)
        if is_fence and not was_open:
            opened_at = i
    if char:
        return [
            Hit(
                "fence-parity",
                path,
                opened_at,
                f"a `{char * length}` fence opens here and never closes "
                "(CommonMark: a same-char run at least as long, no info string)",
            )
        ]
    return []


def _blank_quoted(lines: list[str]) -> list[str]:
    """Same-LENGTH copy with fenced blocks and HTML comments blanked to "".

    A receipt routinely QUOTES the very row it fixed (the F280 remediation quotes its own broken
    row inside a fence). Parsing raw text grades those quotations as live ledger rows — the class
    fires on the fix. Blanking keeps every index, so line numbers stay true.
    """
    out: list[str] = []
    char, length = "", 0
    in_comment = False
    for ln in lines:
        # the comment markers are read with code spans MASKED: a cell that quotes `<!-- POOL OFF`
        # (the D-181 convention) is prose, and an unmasked read blanked every later row of 9 of 805
        # fleet receipts — a real raw-pipe defect lost behind "0 hits" (2026-09-10)
        if in_comment:
            out.append("")
            if "-->" in _mask_code_spans(ln):
                in_comment = False
            continue
        # the FENCE state is decided first: a marker inside a fenced example is quoted text (with
        # the opener tested first, a fenced `<!--` blanked every later line of a probe copy; 0 live
        # files differ under the two orders — the shape is latent)
        was_open = bool(char)
        char, length, is_fence = _fence_step(ln, char, length)
        if was_open or is_fence:
            out.append("")
            continue
        masked = _mask_code_spans(ln)
        if "<!--" in masked and "-->" not in masked:
            in_comment = True
            out.append("")
            continue
        out.append(ln)
    return out


# --------------------------------------------------------------------------- table row shape
def _mask_code_spans(s: str) -> str:
    """Same-length copy with every code span (backticks included) blanked to NUL.

    STRUCTURAL, not a character list: a code span is a backtick run closed by a run of the same
    length (CommonMark 6.1). A hand-listed set of "things that hold a pipe" is one entry away from
    the next bypass, so the span itself is what is masked.
    """
    out = list(s)
    i, n = 0, len(s)
    while i < n:
        if s[i] != "`":
            i += 1
            continue
        j = i
        while j < n and s[j] == "`":
            j += 1
        run = j - i
        k, close = j, -1
        while k < n:
            if s[k] != "`":
                k += 1
                continue
            m = k
            while m < n and s[m] == "`":
                m += 1
            if m - k == run:
                close = m
                break
            k = m
        if close < 0:  # an unclosed run is literal text, not a span
            i = j
            continue
        for t in range(i, close):
            out[t] = "\x00"
        i = close
    return "".join(out)


def _split_cells(row: str) -> list[tuple[str, str]]:
    """[(raw cell, masked cell)] — ONE optional boundary pipe stripped per side (GFM).

    Both masks are length-preserving so the raw text can be sliced at the masked delimiters:
    `\\|` is an escaped pipe (content) and a pipe inside a code span is content too.
    """
    masked = re.sub(r"\\\|", "\x00\x00", _mask_code_spans(row))
    lo = len(row) - len(row.lstrip())
    hi = len(row.rstrip())
    if hi > lo and masked[lo:hi].startswith("|"):
        lo += 1
    if hi > lo and masked[lo:hi].endswith("|"):
        hi -= 1
    cells: list[tuple[str, str]] = []
    pos = lo
    for i in range(lo, hi):
        if masked[i] == "|":
            cells.append((row[pos:i], masked[pos:i]))
            pos = i + 1
    cells.append((row[pos:hi], masked[pos:hi]))
    return cells


def _is_separator(row: str) -> bool:
    """The GFM delimiter-row grammar, per cell — the rule `_table_rows` applies internally
    (check_review_coverage.py), re-stated here because only the header row carries the cell-count
    denominator the raw-pipe class needs, and `_table_rows` skips headers by contract."""
    cells = [m for _, m in _split_cells(row)]
    return bool(cells) and all(re.fullmatch(r"\s*:?-+:?\s*", c) for c in cells)


def _headers(lines: list[str]) -> dict[int, tuple[int, int | None]]:
    """{line index -> (header cell count, disposition column index or None)} per physical pipe-run.

    The DISPOSITION COLUMN is named by the header, never assumed to be the last cell: the receipt
    carries other tables whose final cell legitimately holds two verdict words (the Coverage
    Checklist's `Status` cell reads `CLEAN (… none FIXED; round 18: 0 findings)` on 30 rows). Only
    a table that declares a Disposition column has disposition cells to grade — the 366
    disposition-bearing rows of the D-191 receipt, not its 30 checklist rows.
    """
    out: dict[int, tuple[int, int | None]] = {}
    i = 0
    while i < len(lines):
        if not lines[i].lstrip().startswith("|"):
            i += 1
            continue
        j = i
        while j < len(lines) and lines[j].lstrip().startswith("|"):
            j += 1
        if j - i >= 2 and _is_separator(lines[i + 1]):
            cells = _split_cells(lines[i])
            if len(cells) == len(_split_cells(lines[i + 1])):
                col = next(
                    (
                        n
                        for n, (raw, _) in enumerate(cells)
                        if re.fullmatch(r"\s*\**\s*disposition\s*\**\s*", raw, re.I)
                    ),
                    None,
                )
                for k in range(i, j):
                    out[k] = (len(cells), col)
        i = j
    return out


def _table_parity_hits(
    path: str, lines: list[str], cls: str
) -> tuple[list[Hit], list[tuple[int, list[tuple[str, str]], int | None]], int]:
    """The cell-count comparison BOTH table classes share — `raw-pipe` on a receipt, `table-parity`
    on any `.md` surface: the same defect, named by where it was found. Returns (hits, aligned,
    headerless): `aligned` is every data row whose cells DO line up with its header, as (line
    index, cells, disposition column) for the receipt path's dual-verdict grading; `headerless`
    counts the rows no header pair claims — no denominator, graded by nothing. `lines` is the
    caller's BLANKED copy (`_blank_quoted`), so a quoted or fenced row is never graded."""
    headers = _headers(lines)
    hits: list[Hit] = []
    aligned: list[tuple[int, list[tuple[str, str]], int | None]] = []
    headerless = 0
    # `_table_rows` returns the visible DATA rows verbatim and in order (headers and separators
    # already skipped); walk the physical lines in step to recover each row's line number.
    cursor = 0
    for row in _table_rows("\n".join(lines)):
        while cursor < len(lines) and lines[cursor] != row:
            cursor += 1
        if cursor >= len(lines):
            break
        idx, cursor = cursor, cursor + 1
        cells = _split_cells(row)
        width, col = headers.get(idx, (None, None))
        if width is None:
            headerless += 1
            continue
        if len(cells) != width:
            # A row whose cells do not line up with its header has NO trustworthy disposition
            # cell — which column is which is exactly what the stray pipe destroyed. It is
            # reported once, as the shape defect it is, and not graded a second time.
            short = len(cells) < width
            hits.append(
                Hit(
                    cls,
                    path,
                    idx + 1,
                    f"{len(cells)} cells against the header's {width} — "
                    + (
                        "a MISSING cell (the row is short; add the empty cell)"
                        if short
                        else "an unescaped `|` inside a cell (write `\\|`)"
                    ),
                )
            )
            continue
        aligned.append((idx, cells, col))
    return hits, aligned, headerless


def _receipt_hits(path: str, text: str) -> tuple[list[Hit], int]:
    """(hits, rows graded by NEITHER class) — a row in a table with no header pair has no cell-count
    denominator and no named disposition column, so both classes decline it; so does a row in a
    HEADED table that declares no disposition column at all (the generated receipt grammar —
    `| Class | Status |`, `| Pass | Finders | Counters | Method |` — declares none, so the
    dual-verdict class grades zero of its rows). A bounded search states its bound: the count rides
    the summary line."""
    lines = _blank_quoted(text.splitlines())
    hits, aligned, ungraded = _table_parity_hits(path, lines, "raw-pipe")
    for idx, cells, col in aligned:
        if col is None or col >= len(cells):
            # A headed table that declares NO disposition column is UNGRADED, never clean — the
            # dual-verdict class swept nothing here and must say so. Skipping it silently made the
            # summary read `0 rows ungraded` over a template-generated receipt whose every table
            # is header-less of a `Disposition` column, i.e. a full denominator claimed while the
            # class graded nothing at all (D7 seam #3).
            ungraded += 1
            continue
        found = _verdict_words(cells[col][1])
        if len(found) > 1:
            hits.append(
                Hit(
                    "dual-verdict",
                    path,
                    idx + 1,
                    f"the disposition cell carries {len(found)} bare verdict words "
                    f"({', '.join(found)}) — one leading verdict per cell",
                )
            )
    hits.sort(key=lambda h: h.line)  # the parity pass runs first; the advisory lines read top-down
    return hits, ungraded


# --------------------------------------------------------------------------- surface classes
# `{{include:…}}` IS the authoring format under `commands/_sources/` and `commands/_fragments/` —
# the marker is residue only in a RENDERED command. Measured round 1: 127 hits over 36 source files,
# 100 % false. Keyed on an ANCESTOR DIRECTORY, not on the filename, because the renderer's input tree
# is what defines "source" (`commands/assemble_commands.py`).
_SOURCE_DIRS = frozenset({"_sources", "_fragments"})


def _is_template_source(path: str) -> bool:
    """Is this file part of the RENDERER'S INPUT TREE — `commands/_sources` or
    `commands/_fragments`?

    RESOLVED parts, never the parts as given: `cd commands/_sources && … --surface .` hands over
    bare basenames, which carry no `_sources` ancestor at all — the same 36 files produced 127 hits
    from inside the directory and 0 from the repo root (round 2).

    ⚠️ But resolving made the test ABSOLUTE, and a bare `_sources` ANYWHERE on the box then
    silenced the whole class beneath it, silently — `/anything/_fragments/proj/docs/rendered.md`
    carrying real residue scored 0 (round 3). The exemption belongs to the renderer's tree, so the
    test is the ADJACENT PAIR `commands/_sources` (or `commands/_fragments`): a directory pair no
    unrelated tree forms by accident, and the pair the assembler actually reads.
    """
    try:
        parts = Path(path).resolve().parts
    except (OSError, RuntimeError):
        # A path the OS refuses to resolve is judged AS WRITTEN. RuntimeError belongs here too:
        # non-strict `Path.resolve()` raises it — not OSError — on a symlink loop (3.12). Latent
        # today because the CLI's existence gate fires first, but this script's whole contract is
        # that no input reaches an uncaught raise, and a direct caller has no such gate.
        parts = Path(path).parts
    return any(
        parts[i] == "commands" and parts[i + 1] in _SOURCE_DIRS for i in range(len(parts) - 1)
    )


def _surface_hits(
    path: str,
    text: str,
    phrases: list[str],
    table: bool = True,
    claims: list[str] | None = None,
) -> tuple[list[Hit], int]:
    """(hits, rows graded by nothing) — `table=False` for a surface file that is ALSO a receipt of
    this sweep: the receipt path grades its tables as `raw-pipe`, and one broken row must never be
    reported twice at the same `path:line`."""
    lines = text.splitlines()
    hits: list[Hit] = []
    ungraded = 0
    if path.endswith(".md") and not _is_template_source(path):
        for i, ln in enumerate(lines, start=1):
            for m in TEMPLATE_RESIDUE.finditer(ln):
                hits.append(
                    Hit("template-residue", path, i, f"unrendered template residue `{m.group(0)}`")
                )
    if path.endswith(".md"):
        hits.extend(_fence_hits(path, lines))
        # the table scan alone runs over the blanked copy — `template-residue` reads raw lines and
        # `fence-parity` needs the fences themselves
        if table:
            thits, _aligned, ungraded = _table_parity_hits(
                path, _blank_quoted(lines), "table-parity"
            )
            hits.extend(thits)
    for phrase in phrases:
        for ln in _term_sites(text, phrase):
            # T4.7: the count of the phrase ON that line rides the one hit for it — counted with
            # the same case-insensitive pattern `_term_sites` matched by (review round 1)
            hits.append(
                Hit(
                    "stale-phrase",
                    path,
                    ln,
                    f"stale phrase {phrase!r} still present",
                    _line_occurrences(lines, ln, phrase),
                )
            )
    for term in claims or []:
        # D10 rule (2): a NEUTRAL listing of every site carrying the term — the SAME walk
        # `stale-phrase` uses; fences are NOT stripped, a mirror inside a fence is still a mirror
        # the orchestrator reads before the pin. Differs from `--phrase` ONLY in its label: a
        # `stale-phrase` hit is adjudicated as a defect, a `claim` row is read.
        for ln in _term_sites(text, term):
            hits.append(
                Hit(
                    "claim",
                    path,
                    ln,
                    f"claim {term!r} at this line",
                    _line_occurrences(lines, ln, term),
                )
            )
    if Path(path).name == "CHANGELOG.md":
        hits.extend(_changelog_hits(path, text))
    hits.sort(key=lambda h: h.line)  # residue, fences, tables and phrases are separate passes
    return hits, ungraded


def _term_sites(text: str, term: str) -> list[int]:
    """The LINES where `term` occurs — the one walk `stale-phrase` and `claim` share (they differ
    only in label). Whitespace-tolerant, so a term WRAPPED across a line is a site (two of the
    D-191 sentence's sites wrap; a substring-per-line walk missed a wrapped mirror — round 1);
    case-insensitive; never across a BLANK line (a paragraph break is not a wrap — round 2: the
    bare whitespace join listed the last word of one paragraph glued to the first of the next);
    ONE row per line (a term twice on one line is one site — the `· mirrors: <n> read` count is
    a count of lines); an EMPTY term names no site (the empty pattern matches every character
    offset)."""
    if not term.strip():
        return []
    pat = re.compile(r"\s+".join(re.escape(tok) for tok in term.split()), re.I)
    lines: list[int] = []
    pos = 0
    seen, ln = 0, 1  # newlines counted incrementally: a per-match count from 0 was O(n·matches)
    while (m := pat.search(text, pos)) is not None:
        if re.search(r"\n[ \t]*\n", m.group(0)):
            # a skipped match must NOT consume its span: a real site starting inside it (a term
            # whose first token repeats — `fresh\n\nfresh fresh seat`) was swallowed by a
            # `finditer` walk and never listed (round 3)
            pos = m.start() + 1
            continue
        pos = m.end()
        ln += text.count("\n", seen, m.start())
        seen = m.start()
        if not lines or lines[-1] != ln:
            lines.append(ln)
    return lines


def _changelog_hits(path: str, text: str) -> list[Hit]:
    """``check_changelog.py``'s own quality rule — CALLED, never copied."""
    try:
        try:
            from .check_changelog import check_changelog_quality  # type: ignore[import-not-found]
        except ImportError:
            sys.path.insert(0, str(_HERE))
            from check_changelog import check_changelog_quality  # type: ignore[no-redef]
    except ImportError as exc:  # the sibling check is absent from this repo's copy
        return [Hit("changelog-entry", path, 1, f"check_changelog unavailable ({exc})")]
    said = io.StringIO()
    with contextlib.chdir(Path(path).resolve().parent), contextlib.redirect_stdout(said):
        ok = check_changelog_quality()
    if ok:
        return []
    at = next(
        (i for i, ln in enumerate(text.splitlines(), start=1) if ln.startswith("## [Unreleased]")),
        1,
    )
    why = said.getvalue().strip().splitlines()
    return [
        Hit(
            "changelog-entry",
            path,
            at,
            why[-1] if why else "check_changelog_quality() refused the [Unreleased] entry",
        )
    ]


# --------------------------------------------------------------------------- driver
def _expand(paths: list[Path]) -> tuple[list[Path], list[str]]:
    """(files to read, notes for the paths that are neither). A caller-named path that simply
    vanishes from both the hits and the denominator is byte-identical to a clean sweep — the exact
    shape the unreadable-file NOTE exists to prevent, one branch earlier."""
    out: list[Path] = []
    missing: list[str] = []
    for p in paths:
        if not p.exists():
            missing.append(
                f"{_display(str(p))}: no such path — NOT scanned, not in the denominator"
            )
            continue
        if p.is_dir():
            out.extend(
                sorted(
                    f
                    for f in p.rglob("*")
                    if f.is_file() and f.suffix in SURFACE_SUFFIXES and ".git" not in f.parts
                )
            )
        elif p.is_file():
            out.append(p)
    # dedupe on the RESOLVED path (the original spelling is kept for display): one physical file
    # reached through a directory and again by name — or spelled relative and absolute — is
    # ONE file in the denominator and is scanned once
    seen: set[Path] = set()
    uniq = []
    for p in out:
        key = _resolved(p)
        if key not in seen:
            seen.add(key)
            uniq.append(p)
    return uniq, missing


def _resolved(p: Path) -> Path:
    """`Path.resolve()` under this script's no-raise contract — a path the OS refuses to resolve
    is keyed as written (the same guard `_is_template_source` carries)."""
    try:
        return p.resolve()
    except (OSError, RuntimeError):
        return p


def _read(p: Path) -> str | None:
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


@dataclass(frozen=True)
class Sweep:
    """What one run of the sweep saw. `notes` are NON-findings that change what the hit count
    means — a file that could not be read, a symbol query with no surface to answer it."""

    hits: list[Hit]
    files: int
    notes: list[str]
    ungraded: int


def _line_occurrences(lines: list[str], ln: int, term: str) -> int:
    """How many times ``term`` occurs on line ``ln`` (1-based), matched the way `_term_sites`
    matches it — case-insensitively, whitespace-tolerant — never below 1 for a reported site (an
    occurrence WRAPPED across two lines contributes that floor of 1: its tokens are not all on
    the site line, so a site line that also carries a whole occurrence reads 1 where there are 2)."""
    if not (0 < ln <= len(lines)):
        return 1
    pat = re.compile(r"\s+".join(re.escape(w) for w in term.split()), re.I)
    return max(1, len(pat.findall(lines[ln - 1])))


def _dedupe(hits: list[Hit]) -> list[Hit]:
    """T4.7 (01M2AC95X): `len(hits)` overstated distinct findings (15 raw vs 13 unique, measured
    every round) whenever two producers reported the same site — the same selector given twice
    (`--phrase x --phrase x`); one row per (class, path, line, what), the LINE's count kept
    (`max`), never summed over producers. A `--phrase` and a `--claim` walk carry different
    classes and never merge. A phrase repeated ON one line was never two hits: `_term_sites`
    reports one row per line and the count rides `occurrences` from the start."""
    out: dict[tuple[str, str, int, str], Hit] = {}
    for h in hits:
        k = (h.cls, h.path, h.line, h.what.lower())  # `the widget` and `The Widget` are one site
        if k in out:
            prev = out[k]
            # the SAME site reported twice (the same selector given twice) is one site — the
            # count is the line's, never the sum over producers (round 3)
            out[k] = Hit(
                prev.cls, prev.path, prev.line, prev.what, max(prev.occurrences, h.occurrences)
            )
        else:
            out[k] = h
    return list(out.values())


def _until_heading(text: str, heading: str | None) -> tuple[str, int]:
    """T4.7 (--stop-at-heading): a surface that carries its own Pass Ledger records every phrase a
    round retired; the lines from that heading on are history, not live claims — blanked (not
    cut) so line numbers stay true. Returns (text, blanked line count). The heading is matched
    as a markdown HEADING — a `#`-led line whose text equals the given one (case-insensitive,
    surrounding `#` and whitespace ignored), never a line inside a code fence and never a prose
    line that merely starts with the words (review round 1, Phase B)."""
    if not heading:
        return text, 0
    want = heading.strip().lstrip("#").strip().lower()
    if not want:
        return text, 0
    lines = text.splitlines()
    # the file's ONE quoting model (`_blank_quoted`: fences by `_fence_step`, HTML comments, code
    # spans) — a heading inside a fence OR an HTML comment is quoted text, never the stop
    # (round 3 tracked fences alone; round 4: a commented-out ledger heading was taken as live).
    # An UNTERMINATED `<!--` is literal text, not a comment that swallows the file (round 5) —
    # the opener with no closer below it is neutralised before blanking; a heading inside an
    # indented code block (4 spaces) is quoted too; a closed comment on the heading's own line
    # is not part of its text.
    quoted = list(lines)
    for i in range(len(quoted) - 1, -1, -1):
        if "<!--" in quoted[i]:
            if not any("-->" in q for q in quoted[i:]):
                quoted[i] = quoted[i].replace("<!--", "<!- -")
            break
    for i, ln in enumerate(_blank_quoted(quoted)):
        if ln.startswith("    ") or ln.startswith("\t"):
            continue
        st = re.sub(r"<!--.*?-->", "", ln).strip()
        if not st.startswith("#"):
            continue
        if st.lstrip("#").strip().rstrip("#").strip().lower() == want:
            return "\n".join(lines[:i] + [""] * (len(lines) - i)), len(lines) - i
    return text, 0


def _note_stop(notes: list[str], path: str, heading: str | None, blanked: int) -> None:
    """The `--stop-at-heading` note, one per graded file: how much was blanked, or that the heading
    was not found and the whole file was graded."""
    if not heading:
        return
    if blanked:
        notes.append(
            f"{_display(path)}: {blanked} line(s) from `{heading.strip()}` on are history — "
            "blanked, not graded"
        )
    else:
        notes.append(
            f"{_display(path)}: heading `{heading.strip()}` not found — the whole file was graded"
        )


def scan(
    surfaces: list[Path] | None = None,
    receipts: list[Path] | None = None,
    phrases: list[str] | None = None,
    symbols: list[str] | None = None,
    claims: list[str] | None = None,
    stop_at_heading: str | None = None,
) -> Sweep:
    """Never raises for a missing or unreadable file — it NOTES it instead."""
    phrases = phrases or []
    symbols = symbols or []
    claims = claims or []
    surface_files, surface_missing = _expand([Path(p) for p in (surfaces or [])])
    receipt_files, receipt_missing = _expand([Path(p) for p in (receipts or [])])
    receipt_set = {_resolved(p) for p in receipt_files}
    hits: list[Hit] = []
    notes: list[str] = [*surface_missing, *receipt_missing]
    ungraded = 0
    read: dict[Path, str] = {}  # keyed by RESOLVED path, like `receipt_set` — one file, one entry
    for p in surface_files:
        text = _read(p)
        if text is None:
            # A file that vanished from BOTH the hits and the denominator makes an unreadable
            # surface indistinguishable from a clean one — say it, every time.
            notes.append(f"{_display(str(p))}: unreadable — NOT scanned, not in the denominator")
            continue
        live, blanked = _until_heading(text, stop_at_heading)
        _note_stop(notes, str(p), stop_at_heading, blanked)
        # the blanked text is what every later reader sees too — the `--symbol` count over
        # `read` must not resurrect a symbol whose only mention is in the retired ledger
        read[_resolved(p)] = live
        shits, sungraded = _surface_hits(
            str(p),
            live,
            phrases,
            table=_resolved(p) not in receipt_set,
            claims=claims,
        )
        hits.extend(shits)
        ungraded += sungraded
    for p in receipt_files:
        text = _read(p)
        if text is None:
            notes.append(f"{_display(str(p))}: unreadable — NOT scanned, not in the denominator")
            continue
        # the receipt is the file that CARRIES a Pass Ledger — `--stop-at-heading` blanks it here
        # too, and says so (review round 2: it was a silent no-op on this path)
        live, blanked = _until_heading(text, stop_at_heading)
        if _resolved(p) not in read:
            _note_stop(notes, str(p), stop_at_heading, blanked)
        read.setdefault(_resolved(p), live)
        rhits, rungraded = _receipt_hits(str(p), live)
        hits.extend(rhits)
        ungraded += rungraded
    for symbol in symbols:
        if not read:
            # No surface = no evidence either way. Reporting "referenced 0 times" here asserts a
            # NEGATIVE with an empty denominator — the exact shape the denominator rule forbids.
            notes.append(
                f"symbol `{symbol}`: no readable file on the surface — nothing to count it in"
            )
            continue
        refs = sum(t.count(symbol) for t in read.values())
        if refs == 0:
            hits.append(
                Hit(
                    "dead-symbol",
                    "(surface)",
                    0,
                    f"symbol `{symbol}` is referenced 0 time(s) across "
                    f"{len(read)} file(s) on the surface",
                )
            )
    return Sweep(_dedupe(hits), len(read), notes, ungraded)


def _repo_root() -> Path:
    # `final_gate.py` EXPORTS `PROJECT_ROOT` to every enforcement check it runs (`:268-270`)
    # precisely so a check does not have to re-derive it; a git toplevel derived from cwd is the
    # fallback, not the first answer (they differ whenever the gate is invoked from a subdirectory).
    declared = os.environ.get("PROJECT_ROOT", "").strip()
    if declared and Path(declared).is_dir():
        return Path(declared)
    top = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=False,
    )
    if top.returncode == 0 and top.stdout.strip():
        return Path(top.stdout.strip())
    return _HERE.parents[1]


def _changed_receipts(root: Path) -> list[Path]:
    """Changed/untracked receipts under docs/development/reviews/ — the selection
    ``check_review_coverage.py``'s ``main()`` makes with ``_changed_md`` (rotated
    ``*-archive.md`` finding tables and ``archived/`` carry no ledger by design)."""
    try:
        out = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=all", "--", REVIEWS_PREFIX],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return []
    picked = []
    for line in out.splitlines():
        rel = line[3:].split(" -> ")[-1].strip().strip('"')
        if (
            rel.endswith(".md")
            and not rel.endswith("-archive.md")
            and "archived/" not in rel
            and (root / rel).is_file()
        ):
            picked.append(root / rel)
    return picked


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Advisory review-hygiene sweep — never blocks, always exits 0."
    )
    ap.add_argument(
        "--surface", action="append", default=[], help="file or dir on the surface (repeatable)"
    )
    ap.add_argument(
        "--receipt",
        action="append",
        default=[],
        help="a docs/development/reviews/ md (repeatable)",
    )
    ap.add_argument("--phrase", action="append", default=[], help="a stale phrase (repeatable)")
    ap.add_argument("--symbol", action="append", default=[], help="a live symbol (repeatable)")
    ap.add_argument(
        "--claim",
        action="append",
        default=[],
        help="a claim term whose mirror sites are LISTED — neutral, never a verdict (D10)",
    )
    ap.add_argument("--json", action="store_true", help="emit the hits as JSON")
    ap.add_argument(
        "--stop-at-heading",
        default=None,
        help="grade the surface only ABOVE this heading (e.g. '## Pass Ledger' — the rows below are history)",
    )
    ap.add_argument(
        "--label",
        default=None,
        help="the artifact path to echo in hits when --surface is a scratch copy",
    )
    args = ap.parse_args(argv)
    _LABEL.clear()  # a module global: an in-process second run must not inherit the first label

    surfaces = [Path(p) for p in args.surface]
    receipts = [Path(p) for p in args.receipt]

    def _refuse(why: str) -> int:
        # printed, never raised — every path here returns 0 (the CONTRACT); under `--json` the
        # refusal rides the envelope's `notes`, so a consumer parsing stdout is never handed prose;
        # the plain form is the refusal line ALONE (the graders pin that — a summary line beside it
        # was tried and refused in review round 3)
        if args.json:
            print(
                json.dumps({"hits": [], "files": 0, "notes": [why], "ungraded_rows": 0}, indent=2)
            )
        else:
            print(why)
        return 0

    if args.label and len(args.surface or []) != 1:
        # exit 0 with the refusal in the envelope — the file's CONTRACT (review round 2: an
        # argparse error exited 2 under a warn_only registration, prose on stderr under --json)
        return _refuse(
            "REFUSED — --label names the artifact ONE --surface stands for; give exactly one"
        )
    if args.label:
        _LABEL[str(Path(args.surface[0]))] = args.label
        _LABEL[str(Path(args.surface[0]).resolve())] = args.label
    for flag, terms in (
        ("--claim", args.claim),
        ("--phrase", args.phrase),
        ("--symbol", args.symbol),
    ):
        if any(not term.strip() for term in terms):
            # an empty term names no site (`_term_sites` skips it — the empty pattern would match
            # every character offset; `"".count` is len+1, so an empty symbol is always "live");
            # on the CLI the caller is told, aloud — a `--phrase "$OLD"` whose variable expanded
            # empty must never read as a clean sweep (rounds 3–4)
            return _refuse(f"REFUSED — {flag} needs a non-empty term")
    if args.claim and not surfaces:
        # a mirror sweep is over a PIN the caller names; without one the flag would inherit the
        # no-argument self-selection below and print a green over the changed receipts (the
        # spec's executed mutant)
        return _refuse("REFUSED — --claim needs --surface")
    self_selected = not (surfaces or receipts or args.phrase or args.symbol)
    if self_selected:
        # THE GATE REGISTRATION passes no arguments: self-select the changed receipts and stay
        # silent when there are none, so the check is inert on every unrelated commit.
        receipts = _changed_receipts(_repo_root())
        if not receipts and not args.json:
            # `--json` still emits its envelope: a consumer that parses stdout must never be
            # handed an empty string, which is not JSON.
            return 0

    sweep = scan(
        surfaces,
        receipts,
        args.phrase,
        args.symbol,
        args.claim,
        stop_at_heading=args.stop_at_heading,
    )
    if args.json:
        print(
            json.dumps(
                {
                    "hits": [h.as_dict() for h in sweep.hits],
                    "files": sweep.files,
                    "notes": sweep.notes,
                    "ungraded_rows": sweep.ungraded,
                },
                indent=2,
            )
        )
        return 0
    for note in sweep.notes:
        print(f"[NOTE] {note}")
    for h in sweep.hits:
        print(h.line_out())
    print(
        f"hygiene: {len(sweep.hits)} hit(s) over {sweep.files} file(s), "
        f"{sweep.ungraded} rows ungraded"
    )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001 — advisory contract: never block the gate
        print(f"check_review_hygiene: internal error ({exc}) — advisory check, not blocking")
        sys.exit(0)
