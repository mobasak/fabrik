#!/usr/bin/env python3
# AFTER-EDIT: docs/orchestrator/mega-epic-breakdown/EPIC-ARTIFACT-SCHEMA.md
"""epic_order.py — deterministic epic integrity + phased-ordering over the epic
artifacts written by mega-epic-breakdown/03-expand-epic-files-fabrik.

This is the CODE that replaces 05-dispatch's two prose jobs (north-star R8/D4:
control flow in code, not prose):
  1. Ticket-set integrity  (was 05 Step 1)  -> --check
  2. Phased execution order (was 05 Step 2)  -> default / --json
  3. Epic assignment (round-robin owner:)     -> --assign; owner-set check -> --check --owners

Reads docs/development/epics/*.md frontmatter (see EPIC-ARTIFACT-SCHEMA.md):
  epic_n, slug, title, depends_on[], parallel_with[], owned_paths[], owner, status.

Pure stdlib. Project-agnostic: operates on --epics-dir under the current repo.

Exit codes: 0 = ok; 1 = integrity failure; 2 = usage/parse error.
"""
from __future__ import annotations

import argparse
import glob
import itertools
import json
import os
import re
import subprocess
import sys

MIGRATION_GLOBS = ("alembic/versions/**", "db/schema.sql")


def _strip_unquoted_comment(s: str) -> str:
    """Cuts a trailing " #comment" that is NOT inside a quoted value — a `#`
    reached while inside a quote is part of the value, never a comment start.
    The `#` must be at position 0 or preceded by whitespace (the YAML "a bare
    # only starts a comment after a space" convention) so an unquoted value
    that happens to contain a bare `#` mid-token is left alone.

    A quote character only OPENS a quoted value at position 0 of `s` — this
    flat parser's convention is "the whole value is quoted, or none of it
    is." An apostrophe or double-quote appearing mid-value in an unquoted
    string (`Bob's API`) is a literal character, never a quote-open; treating
    it as one used to trap the scanner in "still inside a quote" for the
    rest of the string, so a genuinely unquoted value's trailing comment
    never got cut."""
    in_quote: str | None = None
    for idx, ch in enumerate(s):
        if in_quote:
            if ch == in_quote:
                in_quote = None
        elif idx == 0 and ch in ("'", '"'):
            in_quote = ch
        elif ch == "#" and (idx == 0 or s[idx - 1].isspace()):
            return s[:idx]
    return s


# The three frontmatter fields the schema actually declares as LISTS. A
# multi-line YAML block ("key:" then "  - item" lines) is only ever a real
# value for one of these — the same shape under a SCALAR key (title, owner,
# slug, kind, status, scaffold, port, target_vps) is a malformed frontmatter,
# never silently promoted to a list (every consumer of those fields assumes
# a string: `re.match` on `title`, `owner in a set`, an f-string with `slug`
# — a list there is a crash or a silent wrong-typed value, not a clean
# integrity finding).
_LIST_KEYS = frozenset({"depends_on", "parallel_with", "owned_paths"})


# Every boundary str.splitlines() itself splits on (checked in this order so
# the 2-char "\r\n" is recognised before its own bare "\r"/"\n" suffixes
# would otherwise match first): CR+LF, CR, LF, vertical tab, form feed, the
# three C1 separators, NEL, and the two Unicode line/paragraph separators.
_LINE_TERMINATORS = (
    "\r\n", "\r", "\n", "\v", "\f", "\x1c", "\x1d", "\x1e", "\x85", "\u2028", "\u2029",
)


def _line_terminator(line: str) -> str:
    """The line-ending substring of ONE element from `str.splitlines(keepends=True)`
    — any of `_LINE_TERMINATORS`, or "" (only the text's last line, if it has
    no trailing terminator at all). Recognising only the ASCII \r\n/\r/\n
    trio here — while `splitlines()` itself (used by both `_parse_frontmatter`
    and `_write_owner` to cut lines in the first place) splits on the full
    set below — meant a line ending in, say, "\x0c" read as terminator-less:
    the writer's replacement/insertion then glued it directly onto the next
    physical line with no separator at all, destroying data at rc 0."""
    for term in _LINE_TERMINATORS:
        if line.endswith(term):
            return term
    return ""


def _line_content(line: str) -> str:
    """`line` (from `splitlines(keepends=True)`) with its own terminator
    removed — never a blind `.rstrip()`, which would also eat trailing
    whitespace that is part of the line's actual content."""
    term = _line_terminator(line)
    return line[: len(line) - len(term)] if term else line


def _classify_fm_line(raw: str) -> tuple:
    """Classifies ONE frontmatter line (its terminator already stripped) —
    the SINGLE place that answers "what kind of line is this", used by BOTH
    `_parse_frontmatter`'s block collector and `_write_owner`'s placement
    and replacement. Before this existed, the parser and the writer each
    answered the question independently (a hand-rolled loop vs. a pair of
    regexes) and disagreed on real fixtures: a whitespace-only interior line
    inside a block (the parser's `not raw.strip()` calls it blank; a regex
    anchored on a byte-empty line did not, so `owner:` landed INSIDE the
    block and an item was lost); `owner : x` or an indented `  owner: x`
    (the parser's `key.strip()` reads the key fine; `^owner:` anchored at
    column 0 with no space before the colon did not, so a SECOND owner:
    line got written at rc 0, breaking idempotency and pre-write dup
    detection alike).

    Returns one of:
      ("fence",)               — the line, once trailing whitespace is
                                   trimmed, is exactly "---" (no leading
                                   whitespace tolerated: an indented
                                   "  ---" is NOT a fence, nor is "----"
                                   four dashes, nor "--- trailing text" —
                                   see `_find_fences`)
      ("blank",)                — empty or all-whitespace
      ("comment",)               — a full-line comment: optional leading
                                   whitespace, then "#"
      ("item", text)             — an indented "- item" list-continuation
                                   line; `text` has its own trailing comment
                                   cut and surrounding quotes stripped
      ("key", key, value)        — a "key: value" line; `key` is
                                   whitespace-tolerant on both sides of the
                                   colon (`owner : x`, `  owner: x`, and
                                   `owner: x` all normalise to key="owner"
                                   — the EXACT normalisation
                                   `_parse_frontmatter` applies); `value`
                                   has its trailing comment cut and is
                                   stripped, and — unless it is an inline
                                   `[a, b]` list — has its surrounding
                                   quotes stripped too
      ("other",)                 — none of the above (no ":" and not
                                   blank/comment/item) — never raises on a
                                   line that doesn't fit any known shape
    """
    if raw.rstrip() == "---":
        return ("fence",)
    if not raw.strip():
        return ("blank",)
    stripped = raw.lstrip()
    if stripped.startswith("#"):
        return ("comment",)
    if stripped.startswith("- "):
        text = _strip_unquoted_comment(stripped[2:].strip()).strip()
        return ("item", text.strip("\"'"))
    if ":" in raw:
        key, _, val = raw.partition(":")
        key = key.strip()
        val = _strip_unquoted_comment(val.strip()).strip()
        if not (val.startswith("[") and val.endswith("]")):
            val = val.strip("\"'")
        return ("key", key, val)
    return ("other",)


def _find_fences(lines: list[str]) -> tuple[int, int] | None:
    """Given `lines` (from `text.splitlines(keepends=True)`), locates the
    frontmatter's opening and closing fence lines by classifying each one
    with `_classify_fm_line` — THE ONE place both `_parse_frontmatter` and
    `_write_owner` decide where the frontmatter starts and ends, so a line
    that is a fence to one is a fence to the other, always (previously the
    parser used `text.startswith("---")` + `text.find("\n---", 3)` — a
    PREFIX match that accepted "----" as an opening fence and closed on the
    first line merely STARTING with "---" — while the writer's classifier
    required the whole trimmed line to equal "---"; the two could locate
    different boundaries in the same file).

    Returns `(open_idx, close_idx)`, or `None` if the file doesn't open
    with a fence or has no matching close. A line the classifier does not
    accept as a fence — "----" (four dashes), an indented "  ---", or
    "--- trailing text" — is not a fence for EITHER consumer: a file that
    OPENS with one has no frontmatter at all (both `--check` and `--assign`
    now refuse it, matching what `load_epics` already reports), and an
    INTERIOR one is ordinary content, never a premature close."""
    if not lines or _classify_fm_line(_line_content(lines[0]))[0] != "fence":
        return None
    close_idx = next(
        (idx for idx in range(1, len(lines))
         if _classify_fm_line(_line_content(lines[idx]))[0] == "fence"),
        None,
    )
    if close_idx is None:
        return None
    return 0, close_idx


def _collect_block_items(lines: list[str], start: int) -> tuple[list[str], int]:
    """From `lines[start]` (one line PAST a `key:` with an empty value),
    collects "  - item" continuation lines via `_classify_fm_line` —
    tolerating interior blank lines and full-line comments (indented or
    not), which are skipped rather than treated as block-enders. The block
    ends at the first line that classifies as anything other than blank,
    comment, or item. Returns `([], start)` when there is no such block."""
    items: list[str] = []
    j = start
    while j < len(lines):
        kind, *rest = _classify_fm_line(lines[j])
        if kind == "item":
            items.append(rest[0])
            j += 1
            continue
        if kind in ("blank", "comment"):
            j += 1
            continue
        break
    return items, j


def _parse_frontmatter(text: str) -> dict | None:
    """Minimal flat-YAML frontmatter parser (scalars + inline [a, b] lists, PLUS
    multi-line block lists — `key:` on its own line followed by `  - item`
    lines, blank lines and full-line comments tolerated between items).
    Every physical line is classified once by `_classify_fm_line` — the
    SAME classifier `_write_owner` uses for placement/replacement, and the
    frontmatter's own boundary is found by the SAME `_find_fences` the
    writer uses too — so the two can never disagree about what a given
    line IS, or where the frontmatter starts and ends. Avoids a PyYAML
    dependency — the schema is intentionally flat.

    Last-wins on a DUPLICATE key — a second `owner:` line overwrites the
    first. `_write_owner` disagrees (it only ever updates the FIRST such
    line), so a duplicate key is recorded under `_dup_keys` (a list) rather
    than silently resolved one way or the other; the caller
    (`check_integrity`) turns `"owner" in fm["_dup_keys"]` into a finding
    that makes `--assign`/`--check --owners` refuse instead of the writer
    and reader each acting on a different one of the two values."""
    lines_with_ends = text.splitlines(keepends=True)
    fences = _find_fences(lines_with_ends)
    if fences is None:
        return None
    open_idx, close_idx = fences
    fm: dict = {}
    dup_keys: list[str] = []
    lines = [_line_content(ln) for ln in lines_with_ends[open_idx + 1 : close_idx]]
    i = 0
    while i < len(lines):
        kind, *rest = _classify_fm_line(lines[i])
        if kind != "key":
            i += 1
            continue
        key, val = rest
        if key in fm and key not in dup_keys:
            dup_keys.append(key)
        if val.startswith("[") and val.endswith("]"):
            inner = val[1:-1].strip()
            items = [x.strip().strip("\"'") for x in inner.split(",")] if inner else []
            fm[key] = [x for x in items if x != ""]
            i += 1
        elif val == "":
            # A block-style YAML list: "key:" alone, then indented "  - item"
            # continuation lines — valid ONLY for the three declared list
            # fields (_LIST_KEYS). The same shape under any other key is
            # recorded as `_malformed_keys` (never silently promoted to a
            # list) and the field falls back to "", matching what an
            # ordinary empty scalar already does.
            items, j = _collect_block_items(lines, i + 1)
            if key in _LIST_KEYS:
                if items:
                    fm[key] = items
                    i = j
                else:
                    fm[key] = ""
                    i += 1
            else:
                fm[key] = ""
                if items:
                    fm.setdefault("_malformed_keys", []).append(key)
                    i = j
                else:
                    i += 1
        else:
            fm[key] = val
            i += 1
    if dup_keys:
        fm["_dup_keys"] = dup_keys
    return fm


def load_epics(epics_dir: str) -> list[dict]:
    epics = []
    for path in sorted(glob.glob(os.path.join(epics_dir, "*.md"))):
        with open(path, encoding="utf-8") as fh:
            fm = _parse_frontmatter(fh.read())
        if fm is None:
            epics.append({"_path": path, "_no_frontmatter": True})
            continue
        def _ints(v):
            out = []
            for x in v if isinstance(v, list) else [v]:
                m = re.search(r"\d+", str(x))
                if m:
                    out.append(int(m.group()))
            return out
        epics.append({
            "_path": path,
            "epic_n": int(re.search(r"\d+", str(fm.get("epic_n", ""))).group())
                      if re.search(r"\d+", str(fm.get("epic_n", ""))) else None,
            "slug": fm.get("slug", ""),
            "title": fm.get("title", ""),
            "status": fm.get("status", "0"),
            "owner": fm.get("owner"),
            "_dup_owner": "owner" in fm.get("_dup_keys", []),
            "_malformed_keys": fm.get("_malformed_keys", []),
            "depends_on": _ints(fm.get("depends_on", [])),
            "parallel_with": _ints(fm.get("parallel_with", [])),
            # An empty/absent `owned_paths:` (bare key, `""`, or `[]`) is NO
            # paths — never the one-element list [''] the scalar branch used to
            # produce, which two parallel epics then "shared" as a finding.
            # A whitespace-only entry is dropped too: with no segments it
            # would read as the whole repo (`_forms` -> [[], ['**']]). `/` and
            # `./` survive as a DELIBERATE root-ownership entry.
            "owned_paths": [p for p in (fm.get("owned_paths", []) if isinstance(
                fm.get("owned_paths", []), list) else [fm.get("owned_paths")]) if str(p).strip()],
        })
    return epics


def _seg_matches(seg: str, s: str) -> bool:
    """Does ONE segment's wildcard pattern match this ONE segment of a path?

    `*` = any run of non-`/` characters, `?` = exactly one non-`/` character,
    every other character a LITERAL — no regex (parens, dots, `+`, brackets
    are just characters: `app/(admin)/**` is a live epic shape). Iterative
    two-pointer with a single backtrack point, O(len(seg) x len(s)), never
    exponential — the `[^/]*`-per-`*` regex form backtracks catastrophically
    on a non-match (74 s at 12 stars in one segment, measured for T05a).

    `s` may itself be a PATTERN segment (the subsumption use): a `*` in `s`
    is consumable only by a `*` in `seg` — the `*` branch is tried FIRST so
    the pattern's star is never spent as a literal on the target's — and
    `?` never matches a target `*` (one character vs. many)."""
    i = j = 0
    star = -1  # index in `seg` of the last `*` seen
    mark = 0  # how far in `s` that `*` has consumed
    while i < len(s):
        if j < len(seg) and seg[j] == "*":
            star, mark = j, i
            j += 1
        elif j < len(seg) and (seg[j] == s[i] or (seg[j] == "?" and s[i] not in "/*")):
            i += 1
            j += 1
        elif star >= 0:
            if s[mark] == "/":
                return False
            mark += 1
            i, j = mark, star + 1
        else:
            return False
    while j < len(seg) and seg[j] == "*":
        j += 1
    return j == len(seg)


def _pattern_segs(pattern: str) -> list[str]:
    """A glob's `/`-separated segments — a leading `./` and any trailing `/`
    dropped, empty segments (`a//b`) collapsed."""
    p = pattern.strip()
    if p == ".":
        p = ""  # the bare repo root — never a file literally named "."
    if p.startswith("./"):
        p = p[2:]
    return [s for s in p.split("/") if s]


def _match_segs(psegs: list[str], ssegs: list[str]) -> bool:
    """Segment-wise match of a glob's segments against a path's — `/`-aware
    by construction (`*`/`?` are only ever matched against ONE segment, so
    `src/a/*` can never swallow `src/a/b/deep.py` the way a bare `fnmatch`
    does). A whole-segment `**` spans any number of segments: zero included
    in the MIDDLE (`libs/**/x/**` matches `libs/x/y.py`), at least one when
    TRAILING (`src/a/**` matches `src/a/x.py`, never the bare `src/a`).

    `reach` is the frontier of path-segment indices the pattern's prefix
    can consume to — O(pattern segments x path segments), no backtracking
    across segments. A target segment that is itself `**` (the subsumption
    use, where `ssegs` come from another glob) is consumable ONLY by a
    pattern `**`: `src/*/x` must not be read as covering `src/**/x`."""
    m = len(ssegs)
    reach = {0}
    for i, seg in enumerate(psegs):
        if seg == "**":
            first = min(reach)
            reach = set(range(first + 1 if i == len(psegs) - 1 else first, m + 1))
        else:
            reach = {j + 1 for j in reach
                     if j < m and ssegs[j] != "**" and _seg_matches(seg, ssegs[j])}
        if not reach:
            return False
    return m in reach


def _forms(pattern: str) -> list[list[str]]:
    """The segment lists one owned_paths entry stands for: itself, plus — for
    a WILDCARD-FREE entry (`src/app`, `src/app/`, `alembic/versions`, `db`) —
    its subtree `<entry>/**`. A bare directory entry OWNS everything beneath
    it (the convention `check_plan_tickets` declares for the same field; a
    trailing slash is insignificant, `_pattern_segs` drops it). Read only as
    the literal file so named, `src/app` vs `src/app/**` in one phase over a
    tree holding `src/app/models/m.py` was invisible to BOTH overlap
    predicates and `_owns_migrations(['alembic/versions'])` was False. A glob
    is only ever itself: expanding every pattern's subtree false-fires 200 of
    495 hub-shaped pairs and lets `src/a/*` swallow `src/a/b/**`."""
    segs = _pattern_segs(pattern)
    if "*" in pattern or "?" in pattern:
        return [segs]
    return [segs, [*segs, "**"]]


def _glob_matches(pattern: str, path: str) -> bool:
    """Does the owned_paths entry `pattern` match this whole repo-relative file
    path? A wildcard-free entry also matches every file beneath it (`_forms`)."""
    ssegs = path.split("/")
    return any(_match_segs(psegs, ssegs) for psegs in _forms(pattern))


def _glob_subsumes(outer: str, inner: str) -> bool:
    """Does every path `inner` could ever match also match `outer`? Glob-vs-glob,
    `**`-aware — `src/app/**` subsumes `src/app/models/**` (and itself), while
    `libs/**/a/**` and `libs/**/b/**` subsume neither way; a wildcard-free
    entry is read as its subtree on either side (`_forms`): `src/app` subsumes
    `src/app/**`, but NOT the reverse — the glob does not contain the bare
    path `src/app` that the directory entry also stands for (overlap detection
    is unharmed: `check_integrity` ORs both directions). Quantified as EVERY
    form of `inner` covered by SOME form of `outer` — OR-ing over both sides'
    forms accepted an outer that covers only the BARE form (`docs/*` over
    `docs/reference`), a false-fire on epics whose realised sets are non-empty
    and permanently disjoint. This is the half of the overlap test that
    fires BEFORE any file exists: epics are authored ahead of the code, so two
    root epics both owning `src/app/**` on a fresh repo realise to the empty
    set and only this predicate can catch them.

    NOT caught here, by design: OVERLAP WITHOUT SUBSUMPTION — two globs that
    intersect while neither contains the other (`src/*/x.py` vs `src/a/*`
    both own `src/a/x.py`; 12.9% of random hub-shaped pairs — 515 of 4,000 —
    under THIS predicate with `_forms`, measured 2026-09-05 by the round-1
    soundness script). That class is caught by the REALISED predicate only,
    once a file under both exists — a glob-vs-glob intersection test would be
    the third predicate. Sound in the direction that matters: 0 false-fires
    across the 265 fires in those 4,000 pairs against a 3,021-path corpus (a
    target segment with wildcards is only covered by an identical one or a
    lone `*`; 6 corpus-bounded misses, the incompleteness side)."""
    return all(any(_match_segs(o, i) for o in _forms(outer)) for i in _forms(inner))


def _tracked_files(epics_dir: str) -> list[str]:
    """Every repo-relative file git knows about from the repo that holds
    `epics_dir` — tracked plus untracked-not-ignored (`--others
    --exclude-standard`), so code a window has written but not yet staged
    counts too. Not a git repo (or no git at all) => [] — the realised sets
    are then empty and the pattern-level predicate carries the check alone."""
    try:
        proc = subprocess.run(
            ["git", "-C", epics_dir, "ls-files", "-z", "--cached", "--others",
             "--exclude-standard", "--full-name", "--", ":/"],
            capture_output=True, check=False,
        )
    except OSError:
        return []
    if proc.returncode != 0:
        return []
    return [p.decode("utf-8", "surrogateescape") for p in proc.stdout.split(b"\0") if p]


def _realise(patterns: list[str], tree: list[str]) -> set[str]:
    """The set of files in `tree` that any of `patterns` matches."""
    return {f for f in tree for p in patterns if _glob_matches(p, f)}


def _owns_migrations(patterns: list[str]) -> bool:
    """Does this owned_paths set reach a migration surface? Equality with a
    MIGRATION_GLOB, or subsumption either way (`alembic/**` covers
    `alembic/versions/**`; `alembic/versions/0001_x.py` sits under it) — and,
    through `_forms`, a bare `alembic/versions` / `db` directory entry reads
    as its subtree, so it owns migrations too. Deliberately LOOSER than
    `_glob_subsumes` in the outward direction: ANY form of the entry reaching
    the migration glob counts (`db/*` covers the bare `db/schema.sql` though
    not `db/schema.sql/**`, and it plainly owns the file), where the strict
    all-forms quantifier would say False."""
    return any(any(_match_segs(o, _pattern_segs(g)) for o in _forms(p)) or _glob_subsumes(g, p)
               for p in patterns for g in MIGRATION_GLOBS)


def check_integrity(epics: list[dict], expected_count: int | None,
                     owners: set[str] | None = None,
                     epics_dir: str | None = None,
                     require_epics: bool = False,
                     tree: list[str] | None = None) -> list[str]:
    """Returns a list of finding strings; empty == PASS. (Was 05 Step 1.)

    Disjointness is keyed on the PHASE `phased_order()` assigns — that is
    what decides which epics are dispatched together — never on the
    author-declared `parallel_with` (which is instead checked for
    CONTRADICTING the computed order). Two same-phase epics overlap when
    the UNION of two predicates says so: their REALISED file sets (each
    glob expanded against `tree` — `git ls-files` of the repo holding
    `epics_dir` unless a `tree` is passed — with a `/`-aware matcher)
    intersect, OR one glob SUBSUMES the other (`**`-aware, glob-vs-glob —
    the predicate that fires before any file exists, since epics are
    authored ahead of the code; a wildcard-free entry such as `src/app` is
    read as its subtree by both predicates). An epic owning NO paths overlaps nothing
    and is not itself a finding (`owned_paths: []` has always been clean;
    the non-empty requirement is the dispatcher's contract, `62` § Parallelism).
    The single-migration-owner rule is keyed on the phase the same way. A
    `depends_on` cycle (or a `depends_on` naming an unknown epic) is a
    finding here rather than a `ValueError` escaping `phased_order()`.

    `owners`, when given (non-None), adds one finding class: an epic whose
    `owner` is missing or outside the named set — the `--check --owners`
    contract. `None` (the default) skips only THAT class.

    A plain `--check` is NOT byte-for-byte the pre-assignment behaviour —
    two structural checks run unconditionally, on `owners=None` too, because
    they are parser-level defects the pre-assignment code could not even
    see: a duplicate `owner:` key (`_dup_owner` — the writer updates only
    the first, the reader is last-wins) and a block-list ("  - item") value
    under a scalar field (`_malformed_keys` — every other check this
    function already ran, e.g. epic_n/title, is unaffected; confirmed by an
    md5-identical hub A/B with neither defect present in any real epic).

    `require_epics`, when True, adds a finding when `epics` is empty (unless
    `expected_count == 0` was explicitly passed) — both the `--check --owners`
    gate AND `--assign` set this: a check/assignment over ZERO epics is a
    vacuous no-op, exactly what an empty or misspelled --epics-dir produces.
    Plain `--check`/`--json` leave it False, unchanged from today.

    `epics_dir` is used only to NAME the directory in that finding; it
    changes no other check."""
    findings: list[str] = []
    if require_epics and not epics and expected_count != 0:
        where = f" in {epics_dir}" if epics_dir else ""
        findings.append(f"no epics found{where} — nothing to verify or assign "
                        f"(pass --expected-count 0 if this is deliberate).")
    for e in epics:
        if e.get("_no_frontmatter"):
            findings.append(f"{e['_path']}: no frontmatter — cannot map to a graph node "
                            f"(03 must emit the epic-artifact schema).")
    good = [e for e in epics if not e.get("_no_frontmatter")]
    for e in good:
        if e["epic_n"] is None:
            findings.append(f"{e['_path']}: missing/invalid epic_n.")
        if not re.match(r"^Epic \d+ — .+", e["title"]):
            findings.append(f"{e['_path']}: title {e['title']!r} != 'Epic N — [Name]'.")
        if e.get("_dup_owner"):
            # Unconditional (not gated on `owners`): `_write_owner` only ever
            # updates the FIRST `owner:` line (count=1) while the parser is
            # last-wins, so --assign and --check --owners would otherwise act
            # on two different values from the same file. Refuse instead of
            # guessing which one is real.
            findings.append(f"{e['_path']}: multiple owner: lines in frontmatter — "
                            f"the writer updates only the first, the reader takes the "
                            f"last; fix by hand to a single owner: line.")
        if e.get("_malformed_keys"):
            # Unconditional too: a "  - item" block under a SCALAR field
            # (title/owner/slug/kind/status/scaffold/port/target_vps) is a
            # malformed frontmatter, not a list — flagged here instead of
            # crashing every downstream consumer that assumes a string.
            findings.append(f"{e['_path']}: malformed value for "
                            f"{', '.join(sorted(e['_malformed_keys']))} — a block list "
                            f"('  - item' lines) is only valid for {sorted(_LIST_KEYS)}.")
        if owners is not None and e.get("owner") not in owners:
            findings.append(f"{e['_path']}: owner {e.get('owner')!r} is not in allowed "
                            f"set {sorted(owners)}.")
    nums = sorted(e["epic_n"] for e in good if e["epic_n"] is not None)
    if expected_count is not None and len(good) != expected_count:
        findings.append(f"count mismatch: {len(good)} epic files vs {expected_count} "
                        f"expected from 02's proposal (deficit or orphan).")
    dups = sorted({n for n in nums if nums.count(n) > 1})
    if dups:
        findings.append(f"duplicate epic numbers: {dups} (stale/redundant copy).")
    if nums:
        expect = list(range(1, max(nums) + 1))
        gaps = sorted(set(expect) - set(nums))
        if gaps:
            findings.append(f"non-contiguous epic numbers: missing {gaps} (deficit or mis-number).")
    # phase-keyed disjointness + single-migration-owner (was 02 gate 2/3 + 3/3; re-proved here)
    by_n = {e["epic_n"]: e for e in good if e["epic_n"] is not None}
    dangling = False
    for _n, e in sorted(by_n.items()):
        missing = sorted(set(e["depends_on"]) - set(by_n))
        if missing:
            # phased_order() would report this as a "cycle" (an unknown dep
            # is never placed, so its dependant is never ready) — name it.
            dangling = True
            findings.append(f"{e['_path']}: depends_on names unknown epic(s) {missing}.")
    phases: list[list[int]] = []
    if not dangling:
        try:
            phases = phased_order(good)
        except ValueError as exc:
            findings.append(f"{exc} — a depends_on cycle can never be phased; break it.")
    phase_of = {n: k for k, phase in enumerate(phases, 1) for n in phase}
    for n, e in sorted(by_n.items()):
        for other_n in e["parallel_with"]:
            if other_n == n:
                # `phase_of[n] != phase_of[n]` is never true — a self-reference
                # slipped through where every other malformed value is a finding.
                findings.append(f"epic {n}: parallel_with names itself — an epic is not its "
                                f"own co-phase peer.")
            elif other_n not in by_n:
                findings.append(f"epic {n}: parallel_with names unknown epic {other_n} — "
                                f"contradicts phased_order().")
            elif phases and phase_of[other_n] != phase_of[n]:
                findings.append(f"epic {n}: parallel_with [{other_n}] contradicts phased_order() "
                                f"— epic {n} is phase {phase_of[n]}, epic {other_n} is phase "
                                f"{phase_of[other_n]}; they never run concurrently.")
    tree_index: list[str] | None = tree
    for k, phase in enumerate(phases, 1):
        if len(phase) < 2:
            continue
        if tree_index is None:
            tree_index = _tracked_files(epics_dir or ".")
        realised = {n: _realise(by_n[n]["owned_paths"], tree_index) for n in phase}
        for a, b in itertools.combinations(phase, 2):
            pa, pb = by_n[a]["owned_paths"], by_n[b]["owned_paths"]
            shared = sorted(realised[a] & realised[b])
            if shared:
                findings.append(f"phase {k} epics {a} & {b} share owned_paths — {len(shared)} "
                                f"realised file(s), e.g. {shared[:3]} — concurrency-unsafe.")
            else:
                sub = [(x, y) for x in pa for y in pb if _glob_subsumes(x, y) or _glob_subsumes(y, x)]
                if sub:
                    x, y = sub[0]
                    findings.append(f"phase {k} epics {a} & {b} share owned_paths — glob {x!r} "
                                    f"(epic {a}) and {y!r} (epic {b}) cover the same paths "
                                    f"(no realised file in common yet) — concurrency-unsafe.")
            if _owns_migrations(pa) and _owns_migrations(pb):
                findings.append(f"phase {k} epics {a} & {b} both own migrations "
                                f"— at most one may.")
    return findings


def phased_order(epics: list[dict]) -> list[list[int]]:
    """Kahn topological sort into phases (was 05 Step 2). Epics in the same
    phase have no mutual dependency (rendered ⚡ / dispatchable together)."""
    good = [e for e in epics if not e.get("_no_frontmatter") and e["epic_n"] is not None]
    deps = {e["epic_n"]: set(e["depends_on"]) for e in good}
    placed: set[int] = set()
    phases: list[list[int]] = []
    remaining = set(deps)
    while remaining:
        ready = sorted(n for n in remaining if deps[n] <= placed)
        if not ready:  # cycle
            raise ValueError(f"dependency cycle among epics {sorted(remaining)}")
        phases.append(ready)
        placed |= set(ready)
        remaining -= set(ready)
    return phases


def render_phases(epics: list[dict], phases: list[list[int]]) -> str:
    by_n = {e["epic_n"]: e for e in epics if not e.get("_no_frontmatter")}
    lines = []
    for i, phase in enumerate(phases, 1):
        names = " ⚡ ".join(f"Epic {n} — {by_n[n]['slug']}" for n in phase)
        when = "root — no upstream dependencies" if i == 1 else f"after Phase {i-1} completes"
        lines.append(f"Phase {i} ({when}): {names}")
    return "\n".join(lines) if lines else "(no epics found)"


def _write_owner(path: str, owner: str) -> None:
    """Idempotently sets `owner: <name>` in one epic file's frontmatter.

    - An existing `owner:` line has its WHOLE LINE replaced by the new
      `owner: <name>` line — including any trailing comment the old line
      carried, which is discarded, not preserved. This is a whole-line
      replace, not an in-place edit of just the value.
    - A file with no `owner:` line yet gets one inserted directly after the
      WHOLE `owned_paths:` value (its key line, plus any "- item" / blank /
      comment continuation lines) — EPIC-ARTIFACT-SCHEMA.md's declared
      field order — or at the end of the frontmatter block if
      `owned_paths:` is absent too.
    - Placement and replacement both walk lines classified by
      `_classify_fm_line`, and the frontmatter's own boundary is found by
      `_find_fences` — the SAME two functions `_parse_frontmatter` uses —
      so the writer and the reader can never disagree about which line IS
      the `owner:` line, where the `owned_paths:` value ends, or where the
      frontmatter itself starts and stops.
    - Read and written with `newline=""`, and reconstructed by inserting or
      replacing exactly ONE element of `text.splitlines(keepends=True)` —
      every other line's bytes, including its own terminator, are carried
      through completely untouched. The inserted/replaced line's own
      terminator matches the line it follows (insertion) or its own
      previous terminator (replacement) — never a file-global scan.
    - No-op (no write, no mtime bump) when the file already reads this way,
      so a repeat `--assign` over the same phased order changes no byte.
    """
    with open(path, encoding="utf-8", newline="") as fh:
        text = fh.read()
    lines = text.splitlines(keepends=True)
    fences = _find_fences(lines)
    if fences is None:
        return  # no frontmatter fences — load_epics already flags this file
    _open_idx, close_idx = fences

    owner_idx = None
    owned_paths_end = None  # one past owned_paths' last physical line, if any
    i = 1
    while i < close_idx:
        kind, *rest = _classify_fm_line(_line_content(lines[i]))
        if kind == "key":
            key = rest[0]
            if key == "owner" and owner_idx is None:
                owner_idx = i
            if key == "owned_paths":
                j = i + 1
                while j < close_idx and _classify_fm_line(_line_content(lines[j]))[0] in (
                    "blank", "comment", "item",
                ):
                    j += 1
                owned_paths_end = j
        i += 1

    new_content = f"owner: {owner}"
    new_lines = list(lines)

    if owner_idx is not None:
        term = _line_terminator(new_lines[owner_idx])
        new_lines[owner_idx] = new_content + term
    else:
        insert_at = owned_paths_end if owned_paths_end is not None else close_idx
        term = _line_terminator(new_lines[insert_at - 1]) or "\n"
        new_lines.insert(insert_at, new_content + term)

    updated = "".join(new_lines)
    if updated != text:
        with open(path, "w", encoding="utf-8", newline="") as fh:
            fh.write(updated)


# The fleet agent-name rule (mirrors the T02a hook's bound: [a-z0-9-]{1,32}).
# Enforced BEFORE any file is touched: `_write_owner` interpolates the name
# VERBATIM into a frontmatter line (f"owner: {owner}") with no escaping at
# all — a name carrying a newline injects extra frontmatter lines (a
# forged key, or a second file corrupted mid-block); one carrying a quote
# or leading/trailing whitespace round-trips wrong, since the reader
# (`_classify_fm_line`) strips surrounding quotes/whitespace from a value
# on read while the writer never added or escaped either. Restricting the
# alphabet closes both: no accepted name can carry a newline, a quote, or
# whitespace for the writer/reader asymmetry to bite on.
_OWNER_NAME_RE = re.compile(r"^[a-z0-9-]{1,32}$")


def _split_names(raw: str) -> list[str]:
    return [x.strip() for x in raw.split(",") if x.strip()]


def _validate_names(names: list[str], ap: argparse.ArgumentParser, flag: str) -> None:
    for n in names:
        if not _OWNER_NAME_RE.fullmatch(n):
            ap.error(f"{flag}: invalid agent name {n!r} — must match [a-z0-9-]{{1,32}}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--epics-dir", default="docs/development/epics")
    ap.add_argument("--expected-count", type=int, default=None,
                    help="epic count from 02's proposal (enables the count-match check)")
    ap.add_argument("--check", action="store_true", help="integrity only; exit 1 on any finding")
    ap.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    ap.add_argument("--assign", metavar="NAMES",
                    help="round-robin assign the phased epics to these comma-separated "
                         "agent names, writing owner: into each epic's frontmatter "
                         "(epic_n order within each phase); refuses to write (exit 1, "
                         "no file touched) when the --check --owners grade of integrity "
                         "(including the empty-dir refusal) would report a finding")
    ap.add_argument("--owners", metavar="NAMES",
                    help="with --check: comma-separated allowed owners — adds a finding "
                         "for any epic whose owner is missing or outside this set")
    args = ap.parse_args(argv)
    if args.owners is not None and not args.check:
        ap.error("--owners requires --check")
    if args.assign is not None and (args.check or args.json):
        # --assign is its own action (ASSIGN: OK/REFUSED, not INTEGRITY:
        # PASS/FAIL or the --json envelope) — silently discarding --check or
        # --json here used to mean "the assignment ran, but so did a flag
        # that implies a totally different report format", with rc 0 and
        # plain ASSIGN: stdout regardless of --json.
        ap.error("--assign cannot be combined with --check or --json")

    # Parse + validate BOTH name lists (usage errors) before any file I/O.
    assign_names: list[str] | None = None
    if args.assign is not None:
        assign_names = _split_names(args.assign)
        if not assign_names:
            ap.error("--assign requires at least one name")
        _validate_names(assign_names, ap, "--assign")

    owners: set[str] | None = None
    if args.owners is not None:
        owner_names = _split_names(args.owners)
        if not owner_names:
            ap.error("--owners requires at least one name")
        _validate_names(owner_names, ap, "--owners")
        owners = set(owner_names)

    if not os.path.isdir(args.epics_dir):
        print(f"epic_order: no such dir: {args.epics_dir}", file=sys.stderr)
        return 2
    epics = load_epics(args.epics_dir)

    if assign_names is not None:
        assign_findings = check_integrity(epics, args.expected_count, epics_dir=args.epics_dir,
                                           require_epics=True)
        if assign_findings:
            print("ASSIGN: REFUSED (integrity failure)")
            for f in assign_findings:
                print(f"  - {f}")
            return 1
        by_n = {e["epic_n"]: e for e in epics if not e.get("_no_frontmatter")}
        try:
            phases = phased_order(epics)
        except ValueError as exc:
            # A depends_on CYCLE — phased_order() raises before returning
            # anything, so nothing is written either way; this only turns an
            # uncaught traceback into the same ASSIGN: REFUSED / rc 1 contract
            # every other pre-write refusal uses. Converting the cycle into an
            # integrity FINDING (so --check also sees it) is T03b's scope, not
            # this ticket's scope — DO NOT do that here.
            print(f"ASSIGN: REFUSED — {exc}")
            return 1
        i = 0
        for phase in phases:
            for n in phase:
                _write_owner(by_n[n]["_path"], assign_names[i % len(assign_names)])
                i += 1
        print("ASSIGN: OK")
        return 0

    findings = check_integrity(epics, args.expected_count, owners if args.check else None,
                                epics_dir=args.epics_dir, require_epics=owners is not None)

    if args.check:
        if args.json:
            print(json.dumps({"ok": not findings, "findings": findings}, indent=2))
        else:
            print("INTEGRITY: PASS" if not findings else "INTEGRITY: FAIL")
            for f in findings:
                print(f"  - {f}")
        return 1 if findings else 0

    phases = phased_order(epics) if not findings else []
    if args.json:
        print(json.dumps({"ok": not findings, "findings": findings, "phases": phases}, indent=2))
    else:
        if findings:
            print("INTEGRITY: FAIL (fix before ordering)")
            for f in findings:
                print(f"  - {f}")
            return 1
        print(render_phases(epics, phases))
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
