"""Graders for `commands/_sources/fabrik-task.md` — the `/fabrik-task` command source.

Three facts about the source, each mechanically decidable (spec
`docs/superpowers/specs/2026-09-17-fabrik-task-lane-design.md` § Constraints C2, § Chosen approach;
ticket T03 Behavior Contract), plus (T07, plan 2026-10-02-plan-1) the Revision-2 prose content:

1. SIZE + INCLUDES — the source is at most `SIZE_CAP` bytes (D-296 raised it to 8980 above C2's
   original 8,847; T07 raises it again to 11672 for D3/D6/D7/D8's required prose plus the v1/v2
   scope tags and the O7 fix review round 1 found missing — D-501; D-657 raises it to 11974 for
   phase 2's path-naming rule, see the comment above `SIZE_CAP`) and its only `{{include:}}` is
   `run-record`. The include half
   is C2's cobra counter (cobra 8): the cheapest way to satisfy a source-byte cap is to move the
   prose into a fragment, so a second include is refused whatever the byte count says.
2. RENDER — the source renders: a temp-dir `render()` (never the installed corpus — the renderer
   PRUNES, and this suite runs from worktrees) emits `fabrik-task.md`, and the source carries the
   frontmatter the corpus check and the skill wrapper read: `description:` with a `TRIGGER —`
   clause and a `Stage:`, plus `argument-hint:`.
3. RUNNABLE LINES — every fenced `python3 scripts/command_run.py …` line in the source is ACCEPTED
   by that script's own argparse, AND every printed close carries the flags the lane refuses without
   (`--feedback` on all three close verbs, `--commit` on `fabrik-task`'s `done`). A line an agent
   cannot paste is a line nobody runs; a close the tool refuses leaves the record `running` and the
   Stop hook holding the turn open.
4. T07's CONTENT — spec D3/D6/D7/D8's required prose is present, each assertion anchored on the
   WHOLE governing sentence (never a bare keyword, which a negated rewording would still satisfy):
   the Behaviours cap, `--design-amend`, the close's REFUSAL of an undeclared or close-time
   contract/new-source hit, the review flavour by surface and the D8 nested stop, the ten UPGRADE
   tokens, independent slices (D6); plus the protocol doc's flag/field coverage, the scope-growth
   fragment's lane variant, and the 2026-09-17 spec's SUPERSEDED-IN-PART banner.

⚠️ The cheapest way to satisfy grader 1 without producing the outcome is to move prose into a
reference doc the source points at — UNCOUNTERED by machinery (spec C3 cobra 8), named here so the
next reader greps it rather than discovering it. The same trap binds grader 4's new checks: moving
the required sentence into `command-run-protocol.md` (already "the reference") would starve the
*source*, which is why each T07 check reads the FILE the ticket's Scope actually names.
"""

from __future__ import annotations

import importlib.util
import re
import shlex
import sys
import tempfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SOURCE = REPO / "commands" / "_sources" / "fabrik-task.md"
PROTOCOL_DOC = REPO / "docs" / "reference" / "command-run-protocol.md"
SCOPE_GROWTH_FRAGMENT = REPO / "commands" / "_fragments" / "scope-growth-exit.md"
OLD_LANE_SPEC = REPO / "docs" / "superpowers" / "specs" / "2026-09-17-fabrik-task-lane-design.md"
# D-296: re-based above C2's 8,847 for T03's correctness fixes. May FALL, never rise, without a row.
# T07 (plan 2026-10-02-plan-1) re-bases again for D3/D6/D7/D8's required prose (Behaviours list,
# multi-commit build, --design-amend, the review flavour by surface, the close refusal, the four
# new UPGRADE tokens), then again after review round 1 for the v1/v2 scope tags every one of
# those needed (D2/D7's full-review-by-surface and D1's module tests apply at lane v2 ONLY; v1
# keeps today's gate, so the text has to say which) plus the O7 contradiction fix — D-501.
# D-517 (operator ruling 2026-10-03, two independent design critiques before design approval) added the
# phase-2 `design-critique` include inside this cap — the cap did not move.
# D-657 (kaizen, 2026-10-08): 11672 -> 11974 for phase 2's path-naming rule (the label form, one
# bare repo-relative path per backtick pair, a field ends at a field-word or `#` line, tests/deletions/renames
# included, only the --review receipt exempt — ~15 feedback rows), after retiring phase 5's
# restatement of the same rule.
SIZE_CAP = 11974
_INCLUDE_RE = re.compile(r"\{\{include:([\w-]+)\}\}")
_FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})")
_RUN_LINE_RE = re.compile(r"command_run\.py\s")


def _load(path: Path, name: str):
    """Import a repo script by path — neither `commands/` nor `scripts/` is a package."""
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader, f"cannot load {path}"
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _parse(line: str):
    """One printed `command_run.py` line, through the REAL parser. `None` if argparse refuses it.

    Shared by the graders that ask what a line SAYS rather than merely whether it parses — the
    phase-count agreement and the mandatory-verb set both need the parsed object, and asserting on
    the raw text instead is what let a prose decoy satisfy the first of them.
    """
    import shlex

    mod = _load(REPO / "scripts" / "command_run.py", "command_run_for_parse")
    argv = shlex.split(line)
    while argv and not argv[0].endswith("command_run.py"):
        argv.pop(0)
    if not argv:
        return None
    try:
        return mod._build_parser().parse_args(argv[1:])
    except SystemExit:
        return None


def _source_text() -> str:
    assert SOURCE.exists(), f"{SOURCE} does not exist — T03's primary path"
    return SOURCE.read_text(encoding="utf-8")


def _run_lines(text: str) -> list[str]:
    """Every fenced `command_run.py …` logical line, backslash continuations joined."""
    out: list[str] = []
    fence = ""
    pending = ""
    for raw in text.splitlines():
        m = _FENCE_RE.match(raw)
        if m:
            token = m.group(1)
            if not fence:
                fence = token
            elif raw.strip().startswith(fence):
                fence = ""
            continue
        if not fence:
            continue
        line = raw.strip()
        if pending:
            pending = pending + " " + line.rstrip("\\").strip()
        elif _RUN_LINE_RE.search(line):
            pending = line.rstrip("\\").strip()
        else:
            continue
        if raw.rstrip().endswith("\\"):
            continue
        out.append(pending)
        pending = ""
    if pending:
        out.append(pending)
    return out


_HARD = "\x00"  # a sentinel for a true STRUCTURAL start — never appears in real markdown


def _norm(text: str) -> str:
    """Blockquote markers (`>`) stripped per line, then whitespace-collapsed to single
    spaces — EXCEPT that a `_HARD` sentinel is inserted at every real structural start (the
    very beginning, a line right after a blank line, or a line opening a heading/bullet/
    numbered item/table row) BEFORE collapsing, so it survives as a literal character
    `_asserted` can key on. A plain mid-paragraph line WRAP (no blank line, no marker) is NOT
    marked — it collapses to an ordinary space, keeping a sentence this plan wrapped across
    source lines as ONE sentence (T07's original note; T07 review O8 added the sentinel so a
    genuine paragraph/heading/bullet/row start is still told apart from that wrap once
    everything is single-spaced)."""
    stripped = "\n".join(re.sub(r"^\s*>\s*", "", line) for line in text.splitlines())
    lines = stripped.splitlines()
    marked = [
        (_HARD + line)
        if (
            i == 0
            or re.match(r"[-*]\s|\d+\.\s|#|\|", line) is not None
            or (i > 0 and lines[i - 1].strip() == "")
        )
        else line
        for i, line in enumerate(lines)
    ]
    return re.sub(r"\s+", " ", "\n".join(marked))


# T07 review round 1 (O8, ruling): a bare `in text` / unanchored `re.search` is satisfied by
# its own negation — "It is false that: <the exact sentence>" still CONTAINS that sentence
# verbatim, so a substring check reads it as present, and a suffix glued BEFORE the sentence's
# own terminator (", which is not true.") changes nothing a loose check reads. The ruling:
# anchor each governing sentence on sentence boundaries at BOTH ends — it must start at a line
# start, after a bullet/row marker, or after a terminator (`.`/`;`) plus whitespace, and it
# must run to ITS OWN terminator, so no clause can be glued before or after it within its
# sentence. `false`/`untrue`/`incorrect` join the negation words.
_NEGATION = re.compile(
    r"\b(not|never|n't|without|no longer|neither|nor|isn't|doesn't|false|untrue|incorrect|"
    r"drop(?:s|ped)?|remove(?:s|d)?|lack(?:s|ing)?|fail(?:s|ed)?\s+to|"
    r"refuses?\s+to\s+(?:name|state))\b",
    re.I,
)


def _boundaries(text: str) -> tuple[set[int], set[int]]:
    """(true-terminator indices, hard-start indices) in `text`. A terminator is a literal
    `.`/`;` OUTSIDE a backtick span and outside parens — a period inside a backtick-quoted
    filename (`design.md`) or a semicolon inside a parenthetical aside is not a sentence end."""
    terms: set[int] = set()
    backtick = False
    depth = 0
    for i, ch in enumerate(text):
        if ch == "`":
            backtick = not backtick
        elif not backtick and ch == "(":
            depth += 1
        elif not backtick and ch == ")":
            depth = max(0, depth - 1)
        elif not backtick and depth == 0 and ch in ".;":
            terms.add(i)
    hards = {m.start() for m in re.finditer(re.escape(_HARD), text)}
    return terms, hards


def _starts(text: str, terms: set[int], hards: set[int]) -> set[int]:
    """Every legitimate sentence/clause START position: the document start, right after a
    `_HARD` sentinel, or right after a terminator plus any run of spaces."""
    starts = {0}
    for b in (*hards, *terms):
        j = b + 1
        while j < len(text) and text[j] == " ":
            j += 1
        starts.add(j)
    return starts


def _reaches_boundary(text: str, pos: int, terms: set[int], hards: set[int]) -> bool:
    """Does `pos` (a match's end) land AT its own terminator or a hard start, so nothing is
    glued between the matched content and where its sentence/clause really ends? A run of
    bare table syntax (` `, `\\t`, `|`) immediately after `pos` is skipped first — the closing
    `|` of a table cell sits between the content and the next row's `_HARD` start."""
    if (pos - 1) in terms or pos in terms or pos in hards or pos >= len(text):
        return True
    j = pos
    while j < len(text) and text[j] in " \t|":
        j += 1
    return j >= len(text) or j in hards


def _asserted(text: str, pattern: str) -> bool:
    """True iff `pattern` matches `text` starting at a legitimate boundary (`_starts`) with no
    `_NEGATION` word in the gap between that boundary and the match (catches "It is false
    that: <sentence>" — the gap is non-empty and carries "false"), AND ending at the
    sentence's OWN terminator or a hard start (`_reaches_boundary` — catches a clause glued in
    before the terminator, since the literal text no longer matches at all once one is: the
    pattern must therefore be written to include, or stop exactly at, that terminator).

    ⚠️ RESIDUAL (reviewer judgement, never mechanical): a SEPARATE sentence placed immediately
    AFTER the matched one that negates it in prose ("<sentence>. This claim is not true.") is
    INVISIBLE here — the matched sentence is byte-identical and properly terminated, and
    judging whether a later, grammatically independent sentence negates an earlier one is a
    reading-comprehension task, not a regex. A human (or review) pass must still read the
    surrounding paragraph for that case."""
    terms, hards = _boundaries(text)
    starts = _starts(text, terms, hards)
    for m in re.finditer(pattern, text):
        s, e = m.span()
        cands = [b for b in starts if b <= s]
        if not cands:
            continue
        gap = text[max(cands) : s]
        if _NEGATION.search(gap) is not None:
            continue
        if not _reaches_boundary(text, e, terms, hards):
            continue
        return True
    return False


def test_source_size_and_single_include() -> None:
    """The byte ceiling, and `run-record` + `orient` + `design-critique` as the only includes.

    ⚠️ The cap is `SIZE_CAP` (11974 B since D-657's phase-2 path-naming rule), NOT the spec's C2
    figure of 8,847 nor D-296's 8980 (the latter stood until T07, plan 2026-10-02-plan-1, which
    gained the Behaviours cap, multi-commit build, `--design-amend`, the review flavour by
    surface, the close refusal, the four new UPGRADE tokens, and (review round 1) the v1/v2 scope
    tags every one of those needed plus the O7 contradiction fix — all REQUIRED prose, not
    padding; D-501, see the `SIZE_CAP` comment above). Before T07: the three HIGH findings of T03's delta round cost more bytes than the
    compression that funded them: a polarity-INVERTED cobra counter (it fired on the honest run and
    was silent on the padded one), a pointer 42 of 43 repos could not follow, and a capture window
    that recorded a SIBLING's commit as this run's measurement — plus closing a fail-open on the
    plan-lock collision guard. Cutting a correctness fix to hit a byte number is optimising the
    measure over the outcome, which is D-253's cobra aimed at this lane's own leanness rule. The
    ratchet still BINDS: this number may go down and never up without a new row.
    """
    data = SOURCE.read_bytes() if SOURCE.exists() else b""
    assert SOURCE.exists(), f"{SOURCE} does not exist — T03's primary path"
    assert len(data) <= SIZE_CAP, (
        f"{SOURCE.name} is {len(data)} B, over the {SIZE_CAP} B cap "
        f"(D-296) by {len(data) - SIZE_CAP} B"
    )
    includes = set(_INCLUDE_RE.findall(data.decode("utf-8")))
    assert includes == {"run-record", "orient", "design-critique"}, (
        f"includes are {sorted(includes)}; C2 allows exactly ['run-record'] plus `orient` "
        "(D-342 — the four executed opening lines every command carries, 19 B in the source) "
        "and `design-critique` (D-517 — the operator's two critiques before BUILD) — "
        "`close-feedback` is auto-appended by the assembler and `term-coverage`/`term-edit` "
        "are the weight this cap exists to keep out"
    )


def test_source_renders_with_the_frontmatter_the_corpus_reads() -> None:
    """The source renders to `fabrik-task.md` and carries its frontmatter contract."""
    text = _source_text()
    head = text.split("\n---", 1)[0] if text.startswith("---") else ""
    assert head.startswith("---"), (
        "no frontmatter — the renderer and the skill wrapper both read it"
    )
    desc = re.search(r"^description:\s*(.+)$", head, flags=re.M)
    assert desc, "frontmatter declares no `description:` — the skill router selects on it"
    value = desc.group(1)
    assert "TRIGGER —" in value, "the `description:` carries no `TRIGGER —` clause"
    assert "SKIP" in value, "the `description:` carries no SKIP clause"
    assert "Stage:" in value, "the `description:` names no Stage"
    assert re.search(r"^argument-hint:", head, flags=re.M), (
        "frontmatter declares no `argument-hint:`"
    )

    asm = _load(REPO / "commands" / "assemble_commands.py", "assemble_commands_under_test")
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        asm.render(tmp, tmp / "_skills", agents_dest=tmp / "_agents")
        rendered = tmp / "fabrik-task.md"
        assert rendered.exists(), "the render emitted no fabrik-task.md"
        body = rendered.read_text(encoding="utf-8")
        assert "{{include:" not in body, "an unresolved include survived the render"
        assert (tmp / "_skills" / "fabrik-task" / "SKILL.md").exists(), "no SKILL.md wrapper"


def test_every_command_run_line_is_accepted_by_the_real_parser(monkeypatch, tmp_path) -> None:
    """Spec § Chosen approach: a printed line the tool refuses is a line nobody runs."""
    monkeypatch.setenv("COMMAND_RUN_DIR", str(tmp_path / "command-runs"))
    text = _source_text()
    lines = _run_lines(text)
    assert lines, "the source prints no `command_run.py` line — it opens no run record"
    # ⚠️ The mandatory verbs must be PRESENT. Byte pressure is the standing force on this file, and
    # cutting a fence is the cheapest way to buy bytes — deleting the `done` and `handoff` blocks
    # entirely left every grader green, which also made the `--commit` assertion below vacuous.
    printed = {a.cmd for a in (_parse(line) for line in lines) if a}
    assert {"start", "step", "done", "handoff"} <= printed, (
        f"the source prints only {sorted(printed)} — a lane that cannot be opened, advanced, "
        "closed or upgraded from its own text"
    )
    mod = _load(REPO / "scripts" / "command_run.py", "command_run_under_test")
    parser = mod._build_parser()
    for line in lines:
        argv = shlex.split(line)
        while argv and not argv[0].endswith("command_run.py"):
            argv.pop(0)
        assert argv, f"no script token in: {line}"
        argv = argv[1:]
        try:
            args = parser.parse_args(argv)
        except SystemExit as exc:  # argparse exits 2 on an unknown or malformed flag
            pytest.fail(f"the parser REFUSED (rc {exc.code}): {line}")
        # argparse acceptance is not the whole contract: the lane REFUSES a close at RUNTIME
        # for flags the parser is happy with (`command_run.py` `_task_close_fields`). A printed
        # close the tool refuses leaves the record `running` and the Stop hook holding the turn.
        # EVERY line must name THIS lane. Without this, replacing `--command fabrik-task` with
        # another command's name on all four lines left the grader green — and the `--commit`
        # assertion below is keyed on that literal, so the typo would disable the very refusal
        # this test exists to catch (T03 review, seat C).
        if args.cmd in {"start", "done", "blocked", "handoff"}:
            assert getattr(args, "command", "") == "fabrik-task", (
                f"a printed line names another command: {line}"
            )
        if args.cmd in {"done", "blocked", "handoff"}:
            assert getattr(args, "feedback", None), f"close without --feedback: {line}"
            if args.cmd == "done" and getattr(args, "command", "") == "fabrik-task":
                assert getattr(args, "commit", None), (
                    "`done --command fabrik-task` is REFUSED without --commit "
                    f"(scripts/command_run.py `_task_close_fields`): {line}"
                )


def test_the_printed_phase_count_matches_the_headings() -> None:
    """The source PRINTS `--phases 5` and the assembler DERIVES a phase count from the headings;
    nothing tied the two together, so mutating the printed number to 3 left every grader green.
    The sibling `fabrik-deploy-checklist` has exactly this cross-check
    (`tests/test_check_command_corpus.py`, "8 phases derived from the headings") — this is that
    precedent applied here.

    The agreement is not cosmetic: `command_run.py` renders `phase <c>/<t>` from `--phases` into
    the pinned RUN line every response carries, so a wrong total misreports progress for the whole
    run. Found by T03's review, seat C."""
    import importlib.util

    text = _source_text()
    spec = importlib.util.spec_from_file_location(
        "assemble_under_test", REPO / "commands" / "assemble_commands.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    derived = mod._phase_count(text)
    # ⚠️ Assert on the PARSED value of the printed `start` line, never a substring over the whole
    # source: the first cut did the latter, and a single line of prose mentioning the right number
    # satisfied it while the fenced line printed the wrong one (executed).
    starts = [a for a in (_parse(line) for line in _run_lines(text)) if a and a.cmd == "start"]
    assert starts, "the source prints no `start` line"
    for args in starts:
        assert args.phases == derived, (
            f"the printed `--phases {args.phases}` disagrees with the {derived} derived from the "
            f"source's own headings — the RUN line would misreport progress for the whole run"
        )


# ── T07: spec D3/D6/D7/D8's prose, each row anchored on the WHOLE governing sentence — a bare
# keyword is satisfied by its own negation (Addendum; the T05c review found 15 such). ───────────


def _prefix_false(sentence: str) -> str:
    """Mutant (a), the ruling's own example: wrap the exact governing sentence in a same-
    sentence prefix carrying a negation word (`false`) — "It is false that: <sentence>" —
    byte-identical content a bare substring/`re.search` check cannot distinguish from the real
    thing (T07 review O8)."""
    return f"It is false that: {sentence}"


def _glued_suffix(sentence: str) -> str:
    """Mutant (b), the ruling's other example: glue a negating clause onto the SAME sentence,
    immediately before whatever ends it (", which is not true") — pushing the real ending
    (a literal terminator baked into `sentence`, or just the text that follows it) further
    out, so the exact-sentence pattern no longer matches at all once this is done."""
    if sentence[-1] in ".;":
        return f"{sentence[:-1]}, which is not true{sentence[-1]}"
    return f"{sentence}, which is not true"


def _mutated(text: str, sentence: str, mutate) -> str:
    """`text` with the ONE occurrence of `sentence` replaced by `mutate(sentence)` — the
    document `_asserted` must then reject at the same (unmutated) `pattern`."""
    assert text.count(sentence) >= 1, f"{sentence!r} not found verbatim in the text to mutate"
    return text.replace(sentence, mutate(sentence), 1)


def _assert_governs(text: str, sentence: str, why: str) -> None:
    """One governing-sentence claim, both ruling mutants included: the real text states it
    (anchored, `_asserted`), and BOTH the "It is false that: " prefix and the glued ", which
    is not true" suffix are rejected when applied to the SAME sentence in the SAME document."""
    pat = re.escape(sentence)
    assert _asserted(text, pat), f"the source no longer states {why}: {sentence!r}"
    assert not _asserted(_mutated(text, sentence, _prefix_false), pat), (
        f"'It is false that:' mutant wrongly passed for {why}"
    )
    assert not _asserted(_mutated(text, sentence, _glued_suffix), pat), (
        f"suffix-glue mutant wrongly passed for {why}"
    )


def test_design_note_names_behaviours_cap_and_the_design_amend_remedy() -> None:
    """Behavior Contract row 1 (part): the Behaviours cap (v2 UPGRADE), the v2 undeclared-path
    REFUSAL (v1 only records), and the `--design-amend` remedy — each a FULL clause, bounded at
    both ends by a real terminator (T07 review O8's ruling), not an arbitrary mid-sentence cut."""
    text = _norm(_source_text())
    cap_refuse = (
        "Add a `## Behaviours` list — each naming its test, at most 7 (an 8th is the "
        "`behaviours` UPGRADE, *(v2)*) — and name every file the build will touch, the "
        "Behaviours' tests, deletions and a rename's both paths included, under line-start "
        "UPPERCASE `APPROACH:`/`MIRROR:` labels, before any line opening with a field word or a "
        "`#` (fenced or not), one bare repo-relative path per backtick pair (`a.py::f`, "
        "`a.py:120` and `a.py, b.py` match nothing; of receipts, only a `--review` one is "
        "exempt): *(v2)* a committed path missing from both "
        "REFUSES `done` at close (v1 measures `--file` instead and only RECORDS);"
    )
    amend = (
        "the remedy is `step --phase 2 --design-amend <path>` *(v2)*, append-only — it never "
        "overwrites a recorded field — and counted on the close as `design_amends`."
    )
    for sentence, why in (
        (cap_refuse, "the Behaviours cap / v2 REFUSAL"),
        (amend, "the --design-amend remedy"),
    ):
        _assert_governs(text, sentence, why)


def test_build_and_review_sections_name_multicommit_sync_commit_and_full_review() -> None:
    """Behavior Contract row 1 (part): the v1-single/v2-multi commit build, the sync-path single
    commit (D7), and the review flavour by surface (v1 always scoped; v2 by surface) incl. the
    D8 nested stop — each a full clause/sentence."""
    text = _norm(_source_text())
    multicommit = (
        "One commit carries it at v1; *(v2)* several may, SPACE-separated — `done --commit shaA "
        "shaB …` measures each in order; a sync-path run (D7) commits ONCE, after phase 4, in "
        "the main checkout (`done` refuses more outside a worktree; `blocked`/`handoff` only "
        "note it)."
    )
    review = (
        "Invoke the review phase 0 already picked — at v1 always `/fabrik-review-scoped` (a v1 "
        "sync/heavy surface never reaches the lane — it routes right-now instead); *(v2)* "
        "`/fabrik-review-scoped`, or the full `/fabrik-review` for a sync, heavy, migration or "
        ">5-file surface (D2, D7) — unchanged, never from memory; nested here, its own "
        "scope-growth stop fires at the FIRST own-fix-only round, not the third (D8), still "
        "closing only on a confirmed-zero pass."
    )
    for sentence, why in (
        (multicommit, "the multi-commit/sync-once rule"),
        (review, "the review flavour by surface"),
    ):
        _assert_governs(text, sentence, why)
    # the comma-joined form this ticket's review found and REMOVED — never resurfaces; T07-S3
    # (a parser-level test of this syntax) belongs to T08, where the space-separated parser
    # lives, and is deliberately NOT added here.
    assert "sha1,sha2" not in text, (
        'a comma-joined --commit example returned (nargs="+" is SPACE-separated)'
    )


def test_close_section_refuses_undeclared_and_close_time_contract_hits() -> None:
    """Behavior Contract row 1 (part): the v2 close REFUSES (v1 still only records)."""
    text = _norm(_source_text())
    undeclared = (
        "*(v2)* a path missing from APPROACH/MIRROR/an amendment REFUSES `done` (phase 2's rule "
        "and remedy); "
        "`blocked`/`handoff` record it as `oversized_mini` instead, "
        "never refusing a sanctioned halt."
    )
    contract = (
        "*(v2)* a contract or new-source hit found only here REFUSES `done` and `handoff` too, "
        "until `--review <a full /fabrik-review receipt>` names one — `blocked` needs none."
    )
    v1_records = "At v1 an undeclared path is RECORDED as `oversized_mini`, never refused."
    for sentence, why in (
        (undeclared, "the v2 undeclared-path REFUSAL"),
        (contract, "the v2 contract/new-source REFUSAL"),
        (v1_records, "the v1 record-only behaviour"),
    ):
        _assert_governs(text, sentence, why)


def test_upgrade_section_gains_the_four_close_raised_tokens() -> None:
    """Behavior Contract row 1 (part): the UPGRADE token list gains `contract`, `new-source`,
    `behaviours`, `appetite` (tagged v2), and the close raises them WHETHER OR NOT typed by hand
    — ONE consistent rule, never "never typed by hand" (T07 review O7: the lead sentence used to
    cite "a contract path" as a hand-typed example while the close paragraph claimed the close-
    raised four are "never typed by hand" — self-contradicting; fixed to the single rule below)."""
    text = _norm(_source_text())
    token_list = (
        "lead with `files` · `oneway` · `tradeoffs` · `seat` · `sync` · `heavy` (v1 and v2) · "
        "*(v2)* `contract` · `new-source` · `behaviours` · `appetite`, then a dash and the detail."
    )
    close_raised = (
        "*(v2)* The last four — `contract` · `new-source` · `behaviours` · `appetite` — the "
        "close ALSO raises itself, from the commit, WHETHER OR NOT you typed them: "
        "`contract`/`new-source` REFUSE `done`/ `handoff` until `--review <receipt>` names one;"
    )
    for sentence, why in (
        (token_list, "the ten-token list"),
        (close_raised, "the close-raised rule"),
    ):
        _assert_governs(text, sentence, why)
    # O7's contradiction, as an executable refusal: "never typed by hand" must NOT recur anywhere
    # near the four close-raised tokens — the single rule is "whether or not you typed them".
    assert "never typed by hand" not in text, (
        "O7's contradiction returned — the close-raised tokens are no longer described with the "
        "single 'whether or not you typed them' rule"
    )
    # The UPGRADE section's OWN text (its heading to the next `## `) — the slice used to be the
    # text BEFORE the heading, which read the frontmatter instead and passed only while nothing
    # there said "a contract path".
    start = text.index("UPGRADE — the one-way ratchet")
    nxt = text.find("\n## ", start)
    upgrade = text[start : nxt if nxt != -1 else len(text)]
    assert "a contract path" not in _norm(upgrade), (
        "the lead sentence resumed citing a contract path as something typed by hand pre-commit"
    )


def test_independent_slices_are_several_task_runs() -> None:
    """Spec § The delta D6, named in this ticket's Scope."""
    text = _norm(_source_text())
    sentence = (
        "A feature splitting into independently shippable slices is several of these runs, "
        "never one bundling them (D6)."
    )
    _assert_governs(text, sentence, "D6")


def test_protocol_doc_documents_every_flag_and_feedback_field_this_ticket_scopes() -> None:
    """Behavior Contract row 2: every flag and feedback field named in T07's Scope is documented
    in `docs/reference/command-run-protocol.md`, matching T08's actual writer at `e6944534f`
    (`scripts/command_run.py`, read via `git show`, never checked out) — grounded, not guessed:
    `--commit`/`--review` are SPACE-separated (`nargs="+"`); `step --appetite` is accepted on ANY
    command at lane v2, refused if non-positive regardless of version, ignored-with-note at v1;
    the `start` line matches the exact printed format. The Revision-2 field names (`parent`,
    `size`, `from_downgrade`, `design_amends`, `loc_added`, `over_appetite`, `upgrades`,
    `phase_marks`, `over_appetite_phases`) sit in ONE long enumeration sentence in the source —
    tested WHOLE below (one governing claim), plus a bare-presence check per token (no
    independent claim to negate there, so no `_assert_governs` is owed)."""
    assert PROTOCOL_DOC.exists(), f"{PROTOCOL_DOC} does not exist"
    text = _norm(PROTOCOL_DOC.read_text(encoding="utf-8"))
    for sentence, why in [
        (
            "Lane v2 (D12) adds a sixth declare key, `consumers=external\\|internal`;",
            "the sixth declare key `consumers`",
        ),
        (
            "`--appetite <min>` (default 240; past it routes `chain: appetite`);",
            "`--appetite` on `start`",
        ),
        (
            '`--why "<reason>"` (required with `oneway=yes`/`tradeoffs=yes`, else refused — '
            "the text lands in the refusal ledger, D9);",
            "`--why`",
        ),
        (
            "`--from-downgrade <refusal id>` (a `/fabrik-spec` DOWNGRADE restart, recorded as "
            "`from_downgrade`).",
            "`--from-downgrade`",
        ),
        (
            "A v2 start prints `lane: v2 (switch <sha\\|uncommitted>) · review: <scoped\\|full> "
            "· appetite: <n> min` (the exact line);",
            "the exact v2 `start` print line",
        ),
        (
            "`--design-amend <path>` (`fabrik-task` only, lane v2 — REFUSED on any other "
            "command or an unstamped record) APPENDS one path to the design's declared "
            "surface — never overwriting a recorded field — counted at close as "
            "`design_amends` (D3.3).",
            "`step --design-amend`",
        ),
        (
            "`--appetite <min>` is accepted on `step` for ANY command, not `fabrik-task`-only "
            "(D11): a non-positive value is REFUSED regardless of lane version;",
            "`step --appetite` on any command, refused if non-positive",
        ),
        (
            "at lane v1 it is accepted and IGNORED with a stderr note (`--appetite ignored — "
            "this repo runs lane v1`)",
            "`step --appetite` ignored-with-note at v1",
        ),
        (
            "`--commit` is the `fabrik-task` lane's flag on the three close verbs "
            '(`nargs="+"` — SPACE-separated, never comma-joined) — REQUIRED on `done` there, '
            "optional on `blocked`/`handoff` (which may close before any commit exists), "
            "REFUSED on every other command;",
            "`done --commit` SPACE-separated, never comma-joined",
        ),
        (
            "at lane v1 more than one is REFUSED (pass ONE).",
            "the v1 one-commit rule",
        ),
        (
            "`--review <receipt>` is REQUIRED on `done`/`handoff` when the re-measure finds a "
            "contract or new-source hit (`needs_full_review`): `check_review_receipt` grades "
            "it (a), (b), (c), (d);",
            "`done`/`handoff --review`",
        ),
        (
            "the close ALSO raises `contract`/`new-source`/`behaviours`/`appetite` itself, "
            "straight from the commit, WHETHER OR NOT the agent typed them — typing one early "
            "only changes which proof text `upgrade` records, never whether "
            "`contract`/`new-source` REFUSE `done`/`handoff` until `--review <receipt>` names "
            "a full-review receipt (`needs_full_review`), which the close's own re-measure "
            "decides independently.",
            "the close-raised tokens, consistent with O7's single rule",
        ),
        (
            "Fields: `ts sid repo command state wall_s rounds findings confirmed phases "
            "phase_reached agent surface account confusion waste change filed cost cost_usd "
            "tok_in tok_out tok_cache_read tok_cache_create tok_msgs models tok_partial "
            "tok_seat_in tok_seat_out tok_seat_cache_read tok_seat_cache_create seats_seen "
            "seats_declared seats_partial seats_skipped`, plus `oversized_mini` and `upgrade` "
            "on a `fabrik-task` close, and (Revision 2, D7–D11, lane v2 only) `parent` (the "
            "enclosing record's `command`, so a lane-nested review is countable), `size` (the "
            "bare word `small` on a `/fabrik-spec` close whose surface spec carries "
            "`Size: small` in its header — empty otherwise), `from_downgrade` (the refusal "
            "id, written EITHER on a v2 `fabrik-task` close started `--from-downgrade <id>`, "
            "OR on a `/fabrik-spec` `handoff` whose `--reason` opens "
            "`DOWNGRADE: LR-xxxxxxxx`), `design_amends` (count, string), `loc_added` (count, "
            "string), `over_appetite` (`yes`/`no`), `upgrades` (every token the CLOSE itself "
            "raised — `contract`/`new-source`/`behaviours`/`appetite` only, space-joined; "
            "`upgrade` keeps the single-token string: the agent-typed one when present, else "
            "the first of those four), and `phase_marks`/`over_appetite_phases` (both COUNTS, "
            "as strings — how many phases were marked with `step --appetite`, and how many of "
            "those ran past 2×) — see the paragraph below.",
            "the Revision-2 field-name enumeration (parent/size/from_downgrade/design_amends/"
            "loc_added/over_appetite/upgrades/phase_marks/over_appetite_phases)",
        ),
    ]:
        _assert_governs(text, sentence, why)
    for field in (
        "`parent`",
        "`size`",
        "`from_downgrade`",
        "`design_amends`",
        "`loc_added`",
        "`over_appetite`",
        "`upgrades`",
        "`over_appetite_phases`",
        "`phase_marks`",
    ):
        assert field in text, f"the protocol doc's feedback-field list drops {field}"
    assert "sha>[,<sha>" not in text, "a comma-joined --commit/--review example returned"


def test_scope_growth_fragment_names_the_lane_variant() -> None:
    """Behavior Contract row 3 (spec § The delta D8; D-355): the fragment names the lane variant
    of the scope-growth stop and that the review still closes only on a confirmed-zero pass."""
    assert SCOPE_GROWTH_FRAGMENT.exists(), f"{SCOPE_GROWTH_FRAGMENT} does not exist"
    text = _norm(SCOPE_GROWTH_FRAGMENT.read_text(encoding="utf-8"))
    sentence = (
        "**Nested under a `fabrik-task` run at lane v2** (the receipt's header carries "
        "`**Lane:** fabrik-task`), the own-fix bar drops to ONE round, not two of three — the "
        "FIRST own-fix-only round after round 1's full pass (so round 2 at the earliest) stops "
        "the hunt — but the exit is unchanged: it still closes only on a round that CONFIRMS "
        "zero (D8; D-355)."
    )
    _assert_governs(text, sentence, "the fabrik-task lane variant and its confirmed-zero exit")


def test_old_lane_spec_carries_a_superseded_in_part_banner() -> None:
    """Behavior Contract row 4 (spec § Documentation landing sites): the 2026-09-17 lane spec's
    header carries a SUPERSEDED-IN-PART banner pointing at the 2026-10-02 spec. Read in the first
    15 lines only — a banner buried in the body is not a HEADER banner.

    Mutant (T07 review O8, the concrete case): `"> NOT **SUPERSEDED-IN-PART** by …"` still
    CONTAINS the substring "SUPERSEDED-IN-PART" verbatim — a bare `in head` check (the pre-fix
    shape of this test) would wrongly pass it. The bare marker alone has no terminator of its
    own, so it is tested as part of the WHOLE banner sentence below, never standalone."""
    assert OLD_LANE_SPEC.exists(), f"{OLD_LANE_SPEC} does not exist"
    head = _norm("\n".join(OLD_LANE_SPEC.read_text(encoding="utf-8").splitlines()[:15]))
    sentence = (
        "**SUPERSEDED-IN-PART** by "
        "`docs/superpowers/specs/2026-10-02-fabrik-task-feature-lane-design.md` "
        "(D-490, D-491, D-492): the file-count SIZE test (§ Why this exists), row 1b's "
        "heavy-surface disposition, and the UPGRADE token list are replaced there (D1, D2, D3);"
    )
    _assert_governs(head, sentence, "the SUPERSEDED-IN-PART banner and its pointer")
    # O8's exact finding, kept as its own explicit case: "NOT" glued directly onto the bare
    # marker (no colon, no "It is false that:") must ALSO be rejected.
    bare = re.escape("**SUPERSEDED-IN-PART**")
    mutant = head.replace("**SUPERSEDED-IN-PART**", "NOT **SUPERSEDED-IN-PART**", 1)
    assert not _asserted(mutant, bare), (
        "negation mutant wrongly passed: 'NOT **SUPERSEDED-IN-PART**' still reads as the banner "
        "under a bare substring check — O8's exact finding"
    )


def test_the_description_skip_clause_names_both_lane_versions() -> None:
    """The `description:` is what the prompt router selects on and the quota dashboard's Commands
    tab displays. Since the hub runs lane v2 (3a803b44b), its SKIP clause must not present the v1 file cap
    and sync/heavy refusal as unconditional: it names the v2 module tests and scopes the old rules
    to lane v1 — and the old unconditional clause is refused."""
    head = _source_text().split("\n---", 1)[0]
    value = re.search(r"^description:\s*(.+)$", head, flags=re.M).group(1)
    skip = value.split("SKIP —", 1)[1].split("Stage:", 1)[0]
    # each version's rules sit INSIDE its own "at lane vN" clause — a v2 module test stated
    # unconditionally, or the v1 sync/heavy refusal restored before the scopes, both fail
    assert re.search(
        r"at lane v2[^;]*a contract path[^;]*consumers=external[^;]*appetite over 240 min", skip
    ), "lane v2's module tests must sit inside its own clause"
    assert re.search(r"at lane v1[^.;]*more than 3 files[^.;]*sync/heavy", skip), (
        "the file cap and the sync/heavy refusal must be scoped to lane v1"
    )
    shared = skip.split("at lane v2", 1)[0]
    for scoped in ("a contract path", "consumers=external", "more than 3 files", "sync/heavy"):
        assert scoped not in shared, f"{scoped!r} is stated before any lane-version scope"
    old = "anything the SIZE gate refuses: more than 3 files"
    assert old not in skip, "the SKIP clause still states the v1 file cap as unconditional"
