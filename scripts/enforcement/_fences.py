#!/usr/bin/env python3
# AFTER-EDIT: tests/enforcement/test_fences.py
"""One linear fence scanner for the gate's markdown readers (W-276255e7).

It has the EXACT match set of the regexes it replaced, so no reader sees a different fence — which text
counts as a fence is unchanged (a CommonMark model is W-2725ed54's question, and lands here once):

- the strip regex ``(?:^[ \\t]*(`{3,})[^\\n]*\\n.*?^[ \\t]*\\1[ \\t]*$|```[^`\\n]+```)`` (re.M | re.S), once
  copied into docs_updater and five checks, and its two extracting variants in check_convergence;
- check_convergence's ``FENCE_BLOCK`` (```` ```[^\\n]*\\n(.*?)``` ````, re.S) and ``_HTML_COMMENT`` (``<!--.*?-->``);
- plan_appetite's backtick and tilde strips and check_phase_tests' paired ```/~~~ strip (W-d2eef742:
  ``strip_marker_fences``, ``strip_three_marker_fences`` — check_phase_tests imports this module lazily, because its
  gate row is warn_only and must exit 0 where this file is missing). check_plan_lock_release keeps its own copy: its
  import allowlist admits the stdlib names it already uses and nothing else.

The regexes backtracked: for every line opening with a backtick run of length R the block alternative tried each
k = R, R-1, ... 3 and scanned to the end of the text for a closer of exactly k backticks (15.7 s on 81 KB of
distinct-length backtick lines, 10.2 s on one 200 KB run); FENCE_BLOCK and _HTML_COMMENT rescanned from every
start position. tests/enforcement/test_fences.py keeps the old regexes as the oracle.

``blank_code_spans`` blanks inline code spans for docs_updater and check_doc_links (W-b9af1d47) — one copy,
linear (W-16c00597), its quadratic original the oracle in tests/test_docs_updater.py. ``blank_code_examples``
(fence lines and bodies by ``fence_toggle``, then spans) is the one reading check_doc_links and check_doc_index
grade markdown links on (W-85bd72fa).

Every consumer imports it by its own name — ``scripts/enforcement`` inserted into ``sys.path`` once, then
``import _fences`` — so a package import, a by-path run and a ``spec_from_file_location`` load share one module.
"""

from __future__ import annotations

import re
from bisect import bisect_right
from typing import NamedTuple

_OPENER = re.compile(r"[ \t]*(`{3,})")
_CLOSER = re.compile(r"[ \t]*(`+)[ \t]*")
_INLINE = re.compile(r"```([^`\n]+)```")


class Block(NamedTuple):
    """A block fence: ``run`` the k backticks the regex settled on, ``info`` the opener line after them,
    ``body`` the text between the opener's newline and the closer line (the old ``_INFO_FENCE`` groups)."""

    start: int
    end: int
    run: str
    info: str
    body: str


def fence_blocks(text: str) -> list[Block]:
    """The block alternative's matches, in order. An opener is a line (with a newline after it) starting with
    ``[ \\t]*`` and 3+ backticks; its closer is the FIRST later line that is ``[ \\t]*`` + exactly k backticks +
    ``[ \\t]*``, k being the LARGEST length <= the opener's run (and >= 3) that still has a closer below — the
    length the regex's backtracking settles on. The walk resumes on the line after the closer."""
    lines = text.split("\n")
    starts: list[int] = []
    pos = 0
    for line in lines:
        starts.append(pos)
        pos += len(line) + 1
    closers: dict[int, list[int]] = {}
    for i, line in enumerate(lines):
        if "`" in line:
            m = _CLOSER.fullmatch(line)
            if m:
                closers.setdefault(len(m.group(1)), []).append(i)
    # the lengths that still have a closer BELOW the walk, sorted; one expires when the walk reaches its last closer
    expiry = sorted((rows[-1], k) for k, rows in closers.items() if k >= 3)
    live = sorted(k for _, k in expiry)
    e = 0
    blocks: list[Block] = []
    i, last = 0, len(lines) - 1  # the last segment has no newline after it, so it never opens
    while i < last:
        while e < len(expiry) and expiry[e][0] <= i:
            live.pop(bisect_right(live, expiry[e][1]) - 1)
            e += 1
        m = _OPENER.match(lines[i])
        if m:
            x = bisect_right(live, len(m.group(1)))
            if x:
                k = live[x - 1]
                rows = closers[k]
                j = rows[bisect_right(rows, i)]
                body_start = starts[i] + len(lines[i]) + 1
                info = lines[i][m.start(1) + k :]
                blocks.append(
                    Block(
                        starts[i],
                        starts[j] + len(lines[j]),
                        "`" * k,
                        info,
                        text[body_start : starts[j]],
                    )
                )
                i = j + 1
                continue
        i += 1
    return blocks


def fence_spans(text: str) -> list[tuple[int, int, str | None, Block | None]]:
    """Every match of the strip regex, in text order: ``(start, end, inline body or None, Block or None)``. The
    inline alternative runs only between blocks: it holds no newline and a block starts at a line start, so the
    two never compete for one position."""
    out: list[tuple[int, int, str | None, Block | None]] = []
    prev = 0
    for block in [*fence_blocks(text), None]:
        stop = block.start if block else len(text)
        for m in _INLINE.finditer(text, prev, stop):
            out.append((m.start(), m.end(), m.group(1), None))
        if block:
            out.append((block.start, block.end, None, block))
            prev = block.end
    return out


def strip(text: str, repl: str = "") -> str:
    """The strip regex's ``.sub(repl, text)`` for a literal ``repl``."""
    parts: list[str] = []
    prev = 0
    for start, end, _, _ in fence_spans(text):
        parts.append(text[prev:start])
        parts.append(repl)
        prev = end
    parts.append(text[prev:])
    return "".join(parts)


class _FenceStrip:
    """Stands where a compiled strip regex stood, so every ``X.sub(repl, text)`` call site reads unchanged.
    ``re.Pattern.sub`` expands backslash escapes in ``repl``; this one does not, so it refuses them rather than
    diverge (today's callers pass "" and " FENCED "), and it takes no ``count``."""

    def sub(self, repl: str, text: str) -> str:
        if "\\" in repl:
            raise ValueError(
                "_fences.FENCE_STRIP.sub takes a literal replacement — no backslash escapes"
            )
        return strip(text, repl)


FENCE_STRIP = _FenceStrip()


def fence_block_bodies(text: str) -> list[str]:
    """``FENCE_BLOCK.findall(text)``: the leftmost ```` ``` ````, the rest of its line, then the body up to the
    first ```` ``` ```` after that newline. With no newline, or no ```` ``` ```` after it, no later start matches
    either, so the walk stops."""
    out: list[str] = []
    pos = 0
    while True:
        start = text.find("```", pos)
        if start < 0:
            return out
        nl = text.find("\n", start + 3)
        if nl < 0:
            return out
        end = text.find("```", nl + 1)
        if end < 0:
            return out
        out.append(text[nl + 1 : end])
        pos = end + 3


def strip_html_comments(text: str) -> str:
    """``_HTML_COMMENT.sub("", text)``: the leftmost ``<!--`` and the first ``-->`` after it."""
    parts: list[str] = []
    pos = 0
    while True:
        start = text.find("<!--", pos)
        if start < 0:
            break
        end = text.find("-->", start + 4)
        if end < 0:
            break
        parts.append(text[pos:start])
        pos = end + 3
    parts.append(text[pos:])
    return "".join(parts)


# W-d2eef742: the plan checks' fence strips, each the exact ``.sub("", text)`` of the regex it replaced.
_MARKER_OPENER = {c: re.compile(rf"[ \t]*{re.escape(c)}{{3,}}") for c in "`~"}
_MARKER_CLOSER = {c: re.compile(rf"[ \t]*{re.escape(c)}{{3,}}[ \t]*") for c in "`~"}
_THREE_CLOSER = re.compile(r"[ \t]*(```|~~~)[ \t]*")


def _lines(text: str) -> tuple[list[str], list[int]]:
    lines = text.split("\n")
    starts: list[int] = []
    pos = 0
    for line in lines:
        starts.append(pos)
        pos += len(line) + 1
    return lines, starts


def _cut(text: str, spans: list[tuple[int, int]]) -> str:
    parts: list[str] = []
    prev = 0
    for start, end in spans:
        parts.append(text[prev:start])
        prev = end
    parts.append(text[prev:])
    return "".join(parts)


def strip_marker_fences(text: str, char: str) -> str:
    """plan_appetite's ``^[ \\t]*X{3,}[^\\n]*\\n.*?^[ \\t]*X{3,}[ \\t]*$`` (re.M | re.S) ``.sub("", text)`` for X =
    ``char`` (a backtick or a tilde): an opener is a line with a newline after it starting ``[ \\t]*`` + 3+ ``char``;
    its closer is the FIRST later line that is ``[ \\t]*`` + 3+ ``char`` (any length) + ``[ \\t]*``. An unclosed
    opener matches nothing and stays."""
    lines, starts = _lines(text)
    opener, closer = _MARKER_OPENER[char], _MARKER_CLOSER[char]
    closers = [i for i, line in enumerate(lines) if char in line and closer.fullmatch(line)]
    spans: list[tuple[int, int]] = []
    i, last = 0, len(lines) - 1  # the last segment has no newline after it, so it never opens
    while i < last:
        if char in lines[i] and opener.match(lines[i]):
            k = bisect_right(closers, i)
            if k < len(closers):
                j = closers[k]
                spans.append((starts[i], starts[j] + len(lines[j])))
                i = j + 1
                continue
        i += 1
    return _cut(text, spans)


def strip_three_marker_fences(text: str) -> str:
    """check_phase_tests' ``(?ms)^[ \\t]*(```|~~~).*?^[ \\t]*\\1[ \\t]*$`` ``.sub("", text)``: an opener is any line
    starting ``[ \\t]*`` + ``` or ~~~ (no newline needed after it); its closer is the FIRST later line that is
    ``[ \\t]*`` + exactly those three characters + ``[ \\t]*``. An unclosed opener matches nothing and stays."""
    lines, starts = _lines(text)
    closers: dict[str, list[int]] = {"```": [], "~~~": []}
    for i, line in enumerate(lines):
        if "`" in line or "~" in line:
            m = _THREE_CLOSER.fullmatch(line)
            if m:
                closers[m.group(1)].append(i)
    spans: list[tuple[int, int]] = []
    i = 0
    while i < len(lines):
        head = lines[i].lstrip(" \t")[:3]
        if head in closers:
            rows = closers[head]
            k = bisect_right(rows, i)
            if k < len(rows):
                j = rows[k]
                spans.append((starts[i], starts[j] + len(lines[j])))
                i = j + 1
                continue
        i += 1
    return _cut(text, spans)


# W-16c00597 / W-b9af1d47: inline code spans, blanked length-preserving — docs_updater's link scan and plan
# header reads, and check_doc_links' link reader. A span opener is a whole backtick run (finditer's greedy `+`
# never starts mid-run), not escaped; it closes on the next run of the same length.
_BACKTICK_RUN_RE = re.compile(r"`+")
# A link's `](dest "title")` tail is raw text: a backtick in it opens no span (it may still CLOSE
# one opened before the link's `[`, as CommonMark reads it). Only a tail after `[text]` counts, so a
# stray `](` cannot shield a real code span from blanking. W-f365c610 (F1): the tail must parse as a
# CommonMark destination — `<…>`, or no space and parentheses nested one level — then an optional
# `"…"`, `'…'` or `(…)` title; `[r](u `x`)` is no link, so its backticks open a span, as markdown-it
# renders it; a title may hold backslash escapes. STATED COST: a destination nested two levels deep, a
# title on the next line, and a title with no destination read otherwise than markdown-it (0 of 762 real
# `](` lines under /opt/fabrik/docs, the W-f365c610 design critique's count).
_LINK_TAIL_RE = re.compile(
    r"\[(?:[^\[\]\n]|\[[^\[\]\n]*\])*(\]\([ \t]*(?:<[^<>\n]*>|(?:[^\s()\\]|\\.|\((?:[^\s()\\]|\\.)*\))*)"
    r"(?:[ \t]+(?:\"(?:[^\"\\\n]|\\.)*\"|'(?:[^'\\\n]|\\.)*'|\((?:[^()\\\n]|\\.)*\)))?[ \t]*\))"
)
# A line a span never crosses into: blank, or one that starts another block (a setext underline
# and a thematic break end the paragraph too). A line-start `<!--` opens an HTML block, which interrupts
# a paragraph (W-f365c610, D4). STATED COST: the other HTML block starts (`<div>`, `<details>`, `<pre>` …)
# are not modelled, so a span may still wrap across one (named by the W-f365c610 design critique; its
# live count is unmeasured).
_BLOCK_START_RE = re.compile(
    r"[ \t]*(?:\r?$|[-*+>|][ \t]|\d+[.)][ \t]|#{1,6}(?:[ \t]|\r?$)|```|~~~|<!--"
    r"|(?:=+|-+)[ \t]*\r?$|(?:[*_][ \t]*){3,}\r?$)",
    re.M,
)
# A line a span never leaves: an ATX heading or a table row.
_ONE_LINE_BLOCK_RE = re.compile(r"[ \t]*(?:#{1,6}(?:[ \t]|\r?$)|\|)", re.M)


def _blank_span(text: str) -> str:
    return re.sub(r"[^\r\n]", " ", text)


def blank_code_spans(content: str) -> str:
    """Each unescaped opener, outside a link tail, pairs with the next run of its length unless a line break first
    ends the span (any break on a heading or table line, else one that starts a block); the runs between are consumed.
    Linear (W-16c00597): every gap between two runs is examined once, each run's line start comes from one forward
    walk, and an opener finds its closer by bisect in the list of runs of its length — the scan-forward-per-opener
    original was quadratic on unmatched runs (1.7 s on one 2 MB line) and is kept verbatim in tests/test_docs_updater.py
    as the oracle. Moved here from docs_updater (W-b9af1d47) so check_doc_links blanks spans with the same copy."""
    runs = list(_BACKTICK_RUN_RE.finditer(content))
    n = len(runs)
    tails = [(m.start(1), m.end(1)) for m in _LINK_TAIL_RE.finditer(content)]
    tail_starts = [start for start, _ in tails]
    # gap g lies between runs[g] and runs[g + 1]: does it hold a newline, and does any line it starts open a block?
    nl_gap = [False] * n
    block_gap = [False] * n
    for g in range(n - 1):
        end = runs[g + 1].start()
        p = content.find("\n", runs[g].end(), end)
        if p < 0:
            continue
        nl_gap[g] = True
        while p >= 0:
            if _BLOCK_START_RE.match(content, p + 1):
                block_gap[g] = True
                break
            p = content.find("\n", p + 1, end)
    # the first gap at or after g that holds a newline / opens a block (n: none) — an opener's closer lies before it
    next_nl = [n] * (n + 1)
    next_block = [n] * (n + 1)
    for g in range(n - 1, -1, -1):
        next_nl[g] = g if nl_gap[g] else next_nl[g + 1]
        next_block[g] = g if block_gap[g] else next_block[g + 1]
    by_len: dict[int, list[int]] = {}
    line_of: list[int] = []  # each run's line start, by one forward walk
    line_start, prev = 0, 0
    for j, m in enumerate(runs):
        by_len.setdefault(len(m.group()), []).append(j)
        p = content.rfind("\n", prev, m.start())
        if p >= 0:
            line_start = p + 1
        line_of.append(line_start)
        prev = m.start()
    one_line_at: dict[int, bool] = {}
    out, kept, i = [], 0, 0
    while i < n:
        opener = runs[i]
        i += 1
        if opener.start() and content[opener.start() - 1] == "\\":
            continue
        t = bisect_right(tail_starts, opener.start()) - 1
        if t >= 0 and opener.start() < tails[t][1]:
            continue
        start = line_of[i - 1]
        if start not in one_line_at:
            one_line_at[start] = _ONE_LINE_BLOCK_RE.match(content, start) is not None
        limit = (next_nl if one_line_at[start] else next_block)[i - 1]
        same = by_len[len(opener.group())]
        k = bisect_right(same, i - 1)
        if k < len(same) and same[k] <= limit:
            j = same[k]
            out += [
                content[kept : opener.start()],
                _blank_span(content[opener.start() : runs[j].end()]),
            ]
            kept, i = runs[j].end(), j + 1
    return "".join(out) + content[kept:]


# A backtick run, text, then the same run: an inline code span on one line, not a fence opener.
_INLINE_SPAN_RE = re.compile(r"(`{3,})[^`]+\1(?!`)")


def fence_toggle(line: str) -> bool:
    """The link checks' fence toggle: any line whose left-stripped text starts with ``` opens or closes a
    fence — no run length, no ~~~, a closer may carry text (a CommonMark model is W-2725ed54's) — except a
    line-leading inline span that closes on its own line (```` ```x``` ````), which is code, not a fence."""
    stripped = line.lstrip()
    return stripped.startswith("```") and not _INLINE_SPAN_RE.match(stripped)


def blank_code_examples(text: str) -> str:
    """`text` with every fence line and fence body (by `fence_toggle`) and then every inline code span blanked,
    length-preserving — the reading check_doc_links and check_doc_index grade links on (W-b9af1d47, W-85bd72fa).
    Fences go first, so a fence's ``` never pairs with an inline ``` run after it and a body's backticks never
    pair with an opener above the fence; the toggle splits lines on every boundary str.splitlines() uses (\\r,
    \\f, \\v, \\x1c-\\x1e, NEL, U+2028 and U+2029 too), while the span blanker breaks lines only on \\n, so
    masking per line before the span pass is load-bearing.
    Every offset in the output is the input's, so a caller cuts it at its own raw line offsets."""
    masked = list(text)
    in_fence, pos = False, 0
    for raw in text.splitlines(keepends=True):
        line = raw.splitlines()[0]
        toggle = fence_toggle(line)
        if toggle or in_fence:
            masked[pos : pos + len(line)] = " " * len(line)
        in_fence ^= toggle
        pos += len(raw)
    return blank_code_spans("".join(masked))


def status_candidates(
    text: str, pattern: re.Pattern[str], endpos: int | None = None
) -> list[tuple[re.Match[str], bool]]:
    """Every `pattern` match in the ORIGINAL text, paired with whether an inline code span hides its `Status` key.

    W-a7cff030 (panel verdict, both seats): match on the original text, never on a blanked copy. Matching a blanked
    copy let a stray backtick pair across lines and erase a REAL Status line, let a value's tail cross into the next
    line, and let a line that only starts with a span count as a Status line. A hidden match is a REJECTED candidate,
    not an invisible one: each reader takes the first match that is not hidden, and when only hidden ones exist it
    falls to its own strict branch (its stated fail direction). `endpos` bounds where a match may start, as a slice
    would."""
    blanked = blank_code_spans(text)
    out: list[tuple[re.Match[str], bool]] = []
    for m in pattern.finditer(text, 0, len(text) if endpos is None else endpos):
        at = m.group(0).lower().find("status")
        key = m.start() + (at if at >= 0 else 0)
        out.append((m, blanked[key] != text[key]))
    return out
