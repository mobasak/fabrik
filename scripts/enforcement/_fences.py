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
