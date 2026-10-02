"""Graders for `commands/_sources/fabrik-task.md` — the `/fabrik-task` command source.

Three facts about the source, each mechanically decidable (spec
`docs/superpowers/specs/2026-09-17-fabrik-task-lane-design.md` § Constraints C2, § Chosen approach;
ticket T03 Behavior Contract), plus (T07, plan 2026-10-02-plan-1) the Revision-2 prose content:

1. SIZE + INCLUDES — the source is at most `SIZE_CAP` bytes (D-296 raised it to 8980 above C2's
   original 8,847; T07 raises it again to 11672 for D3/D6/D7/D8's required prose plus the v1/v2
   scope tags and the O7 fix review round 1 found missing — a pending D-row, see the comment
   above `SIZE_CAP`) and its only `{{include:}}` is `run-record`. The include half
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
# keeps today's gate, so the text has to say which) plus the O7 contradiction fix — a D-row is
# owed from the dispatching session citing this ratchet (the subagent brief forbids minting it);
# until then this comment is the citation.
SIZE_CAP = 11672
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


def _norm(text: str) -> str:
    """Whitespace-collapsed text, with each line's leading blockquote marker (`>`) stripped
    first — `scope-growth-exit.md` wraps every line in `> `, which would otherwise land INSIDE a
    sentence this plan wrapped across source lines. T07's content checks read SENTENCES, never
    isolated keywords (a bare substring is satisfied by its own negation, Addendum)."""
    stripped = "\n".join(re.sub(r"^\s*>\s*", "", line) for line in text.splitlines())
    return re.sub(r"\s+", " ", stripped)


# T07 review round 1 (O8): a bare `in text` / unanchored `re.search` is satisfied by its own
# negation — "NOT <the exact governing sentence>" still CONTAINS that sentence verbatim, so a
# substring check reads it as present. `_asserted` additionally refuses a match whose preceding
# ~80 chars carry a negation marker, which is where a prefix-wrap lands.
_NEGATION = re.compile(
    r"\b(not|never|n't|without|no longer|neither|nor|isn't|doesn't|drop(?:s|ped)?|"
    r"remove(?:s|d)?|lack(?:s|ing)?|fail(?:s|ed)?\s+to|refuses?\s+to\s+(?:name|state))\b",
    re.I,
)


def _asserted(text: str, pattern: str, *, window: int = 80) -> bool:
    """True iff `pattern` matches `text` with no negation marker in the CURRENT clause
    immediately before the match. False on no match OR a negated/weakened match — the two
    failure modes a bare substring/`re.search` check cannot tell apart (T07 review O8).

    The `window` characters before the match are truncated at the LAST `;`, `.` or em-dash
    (`—`) inside them, so a negation word that belongs to the PRIOR clause/sentence (e.g.
    "…never refusing); the remedy is …", or "…not round 3 — the FIRST…") never flags the
    clause that follows it — only a negation with nothing but whitespace/markup between it
    and the match (the "NOT <exact sentence>" wrap, or "— NOT <exact sentence>") does."""
    m = re.search(pattern, text)
    if not m:
        return False
    before = text[max(0, m.start() - window) : m.start()]
    boundary = max(before.rfind(";"), before.rfind("."), before.rfind("—"))
    if boundary != -1:
        before = before[boundary + 1 :]
    return _NEGATION.search(before) is None


def test_source_size_and_single_include() -> None:
    """The byte ceiling, and `run-record` as the only include.

    ⚠️ The cap is 11672 B, NOT the spec's C2 figure of 8,847 nor D-296's 8980 (the latter stood
    until T07, plan 2026-10-02-plan-1, which gained the Behaviours cap, multi-commit build,
    `--design-amend`, the review flavour by surface, the close refusal, the four new UPGRADE
    tokens, and (review round 1) the v1/v2 scope tags every one of those needed plus the O7
    contradiction fix — all REQUIRED prose, not padding; see the `SIZE_CAP` comment above for
    the pending D-row). Before T07: the three HIGH findings of T03's delta round cost more bytes than the
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
    assert includes == {"run-record", "orient"}, (
        f"includes are {sorted(includes)}; C2 allows exactly ['run-record'] plus `orient` "
        "(D-342 — the four executed opening lines every command carries, 19 B in the source) — "
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


def _not_prefix(sentence: str) -> str:
    """The cheapest negation mutant: wrap the exact governing sentence in a NOT-clause while
    keeping it byte-identical — the shape a bare substring/`re.search` check cannot distinguish
    from the real thing (T07 review O8)."""
    return f"This is NOT true: {sentence} — the rest of the paragraph is unaffected."


def test_design_note_names_behaviours_cap_and_the_design_amend_remedy() -> None:
    """Behavior Contract row 1 (part): the Behaviours cap (v2 UPGRADE), the v2 undeclared-path
    REFUSAL (v1 only records), and the `--design-amend` remedy.

    Mutant table (negation — `_not_prefix` wraps the exact sentence in "This is NOT true: …",
    which a bare substring check cannot tell from the real text): all three assertions below
    FAIL on their own mutant and PASS on the real source."""
    text = _norm(_source_text())
    cap = (
        "Add a `## Behaviours` list — each naming its test, at most 7 (an 8th is the "
        "`behaviours` UPGRADE, *(v2)*)"
    )
    refuse = (
        "*(v2)* a committed path missing from both REFUSES `done` at close (v1 only RECORDS it, "
        "never refusing)"
    )
    amend = (
        "the remedy is `step --phase 2 --design-amend <path>` *(v2)*, append-only — it never "
        "overwrites a recorded field"
    )
    for sentence, why in (
        (cap, "the Behaviours cap"),
        (refuse, "the v2 REFUSAL"),
        (amend, "the --design-amend remedy"),
    ):
        pat = re.escape(sentence)
        assert _asserted(text, pat), f"the design note no longer states {why}: {sentence!r}"
        assert not _asserted(_not_prefix(sentence), pat), (
            f"negation mutant wrongly passed for {why}"
        )
    assert "`design_amends`" in text, "an amendment is no longer counted as `design_amends`"


def test_build_and_review_sections_name_multicommit_sync_commit_and_full_review() -> None:
    """Behavior Contract row 1 (part): the v1-single/v2-multi commit build, the sync-path single
    commit (D7), and the review flavour by surface (v1 always scoped; v2 by surface) incl. the
    D8 nested stop."""
    text = _norm(_source_text())
    multicommit = (
        "One commit carries it at v1; *(v2)* several may, SPACE-separated — `done --commit shaA "
        "shaB …` measures each in order; a sync-path run (D7) commits ONCE, after phase 4, in the "
        "main checkout"
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
        pat = re.escape(sentence)
        assert _asserted(text, pat), f"the source no longer states {why}: {sentence!r}"
        assert not _asserted(_not_prefix(sentence), pat), (
            f"negation mutant wrongly passed for {why}"
        )
    # the comma-joined form this ticket's review found and REMOVED — never resurfaces
    assert "sha1,sha2" not in text, (
        'a comma-joined --commit example returned (nargs="+" is SPACE-separated)'
    )


def test_close_section_refuses_undeclared_and_close_time_contract_hits() -> None:
    """Behavior Contract row 1 (part): the v2 close REFUSES (v1 still only records)."""
    text = _norm(_source_text())
    undeclared = (
        "*(v2)* a committed path missing from APPROACH/MIRROR/an amendment REFUSES `done` "
        "(phase 2's remedy above); `blocked`/`handoff` record it as `oversized_mini` instead, "
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
        pat = re.escape(sentence)
        assert _asserted(text, pat), f"the close section no longer states {why}: {sentence!r}"
        assert not _asserted(_not_prefix(sentence), pat), (
            f"negation mutant wrongly passed for {why}"
        )


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
        "`contract`/`new-source` REFUSE `done`/ `handoff` until `--review <receipt>` names one; "
        "`behaviours`/`appetite` are findings only."
    )
    for sentence, why in (
        (token_list, "the ten-token list"),
        (close_raised, "the close-raised rule"),
    ):
        pat = re.escape(sentence)
        assert _asserted(text, pat), f"the UPGRADE section no longer states {why}: {sentence!r}"
        assert not _asserted(_not_prefix(sentence), pat), (
            f"negation mutant wrongly passed for {why}"
        )
    # O7's contradiction, as an executable refusal: "never typed by hand" must NOT recur anywhere
    # near the four close-raised tokens — the single rule is "whether or not you typed them".
    assert "never typed by hand" not in text, (
        "O7's contradiction returned — the close-raised tokens are no longer described with the "
        "single 'whether or not you typed them' rule"
    )
    assert "a contract path" not in _norm(
        text[: text.index("UPGRADE — the one-way ratchet")]
        if "UPGRADE — the one-way ratchet" in text
        else text
    ), "the lead sentence resumed citing a contract path as something typed by hand pre-commit"


def test_independent_slices_are_several_task_runs() -> None:
    """Spec § The delta D6, named in this ticket's Scope."""
    text = _norm(_source_text())
    sentence = (
        "A feature splitting into independently shippable slices is several of these runs, "
        "never one bundling them (D6)."
    )
    pat = re.escape(sentence)
    assert _asserted(text, pat), f"the source no longer states D6: {sentence!r}"
    assert not _asserted(_not_prefix(sentence), pat), "negation mutant wrongly passed for D6"


def test_protocol_doc_documents_every_flag_and_feedback_field_this_ticket_scopes() -> None:
    """Behavior Contract row 2: every flag and feedback field named in T07's Scope is documented
    in `docs/reference/command-run-protocol.md`, matching T08's actual writer at `e6944534f`
    (`scripts/command_run.py`, read via `git show`, never checked out) — grounded, not guessed:
    `--commit`/`--review` are SPACE-separated (`nargs="+"`); `step --appetite` is accepted on ANY
    command at lane v2, refused if non-positive regardless of version, ignored-with-note at v1;
    `phase_marks`/`over_appetite_phases` are counts as strings; `size` is the bare word `small`;
    `over_appetite` is `yes`/`no`; `from_downgrade` is written on a v2 task close OR a
    `/fabrik-spec` DOWNGRADE handoff; the `start` line matches the exact printed format."""
    assert PROTOCOL_DOC.exists(), f"{PROTOCOL_DOC} does not exist"
    text = _norm(PROTOCOL_DOC.read_text(encoding="utf-8"))
    for needle, why in [
        (
            "Lane v2 (D12) adds a sixth declare key, `consumers=external\\|internal`",
            "the sixth declare key `consumers`",
        ),
        (
            "`--appetite <min>` (default 240; past it routes `chain: appetite`)",
            "`--appetite` on `start`",
        ),
        ('`--why "<reason>"` (required with `oneway=yes`/`tradeoffs=yes`', "`--why`"),
        ("`--from-downgrade <refusal id>`", "`--from-downgrade`"),
        (
            "A v2 start prints `lane: v2 (switch <sha\\|uncommitted>) · review: <scoped\\|full> · "
            "appetite: <n> min`",
            "the exact v2 `start` print line",
        ),
        (
            "lane v2 — REFUSED on any other command or an unstamped record) APPENDS one path to "
            "the design's declared surface",
            "`step --design-amend`",
        ),
        (
            "`--appetite <min>` is accepted on `step` for ANY command, not `fabrik-task`-only "
            "(D11): a non-positive value is REFUSED regardless of lane version",
            "`step --appetite` on any command, refused if non-positive",
        ),
        (
            "at lane v1 it is accepted and IGNORED with a stderr note",
            "`step --appetite` ignored-with-note at v1",
        ),
        (
            "`--commit` is the `fabrik-task` lane's flag on the three close verbs "
            '(`nargs="+"` — SPACE-separated, never comma-joined)',
            "`done --commit` SPACE-separated, never comma-joined",
        ),
        (
            "at lane v1 more than one is REFUSED (pass ONE)",
            "the v1 one-commit rule",
        ),
        (
            "`--review <receipt>` is REQUIRED on `done`/`handoff` when the re-measure finds a "
            "contract or new-source hit",
            "`done`/`handoff --review`",
        ),
        (
            "the close ALSO raises `contract`/`new-source`/`behaviours`/`appetite` itself, "
            "straight from the commit, WHETHER OR NOT the agent typed them",
            "the close-raised tokens, consistent with O7's single rule",
        ),
        (
            "`size` (the bare word `small` on a `/fabrik-spec` close",
            "`size` as the bare word `small`",
        ),
        (
            "written EITHER on a v2 `fabrik-task` close started `--from-downgrade <id>`, OR on a "
            "`/fabrik-spec` `handoff` whose `--reason` opens `DOWNGRADE: LR-xxxxxxxx`",
            "`from_downgrade`'s two write sites",
        ),
        ("`over_appetite` (`yes`/`no`)", "`over_appetite` as yes/no"),
        (
            "`phase_marks`/`over_appetite_phases` (both COUNTS, as strings",
            "`phase_marks`/`over_appetite_phases` as string counts",
        ),
    ]:
        pat = re.escape(needle)
        assert _asserted(text, pat), f"the protocol doc no longer documents {why}: {needle!r}"
        assert not _asserted(_not_prefix(needle), pat), f"negation mutant wrongly passed for {why}"
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
    variant = (
        "the own-fix bar drops to round 1, not round 3 — the FIRST own-fix-only round stops "
        "the hunt"
    )
    confirmed_zero = (
        "the exit is unchanged: it still closes only on a round that CONFIRMS zero (D8; D-355)."
    )
    for sentence, why in (
        (variant, "the lane variant"),
        (confirmed_zero, "the confirmed-zero exit"),
    ):
        pat = re.escape(sentence)
        assert _asserted(text, pat), f"the fragment no longer states {why}: {sentence!r}"
        assert not _asserted(_not_prefix(sentence), pat), (
            f"negation mutant wrongly passed for {why}"
        )


def test_old_lane_spec_carries_a_superseded_in_part_banner() -> None:
    """Behavior Contract row 4 (spec § Documentation landing sites): the 2026-09-17 lane spec's
    header carries a SUPERSEDED-IN-PART banner pointing at the 2026-10-02 spec. Read in the first
    15 lines only — a banner buried in the body is not a HEADER banner.

    Mutant (T07 review O8, the concrete case): `"> NOT **SUPERSEDED-IN-PART** by …"` still
    CONTAINS the substring "SUPERSEDED-IN-PART" verbatim — a bare `in head` check (the pre-fix
    shape of this test) would wrongly pass it. `_asserted`'s negation window catches the "NOT"."""
    assert OLD_LANE_SPEC.exists(), f"{OLD_LANE_SPEC} does not exist"
    head = _norm("\n".join(OLD_LANE_SPEC.read_text(encoding="utf-8").splitlines()[:15]))
    banner = re.escape("**SUPERSEDED-IN-PART**")
    pointer = re.escape("2026-10-02-fabrik-task-feature-lane-design.md")
    assert _asserted(head, banner), (
        "the old lane spec's header carries no SUPERSEDED-IN-PART banner"
    )
    assert _asserted(head, pointer), (
        "the SUPERSEDED-IN-PART banner does not point at the superseding spec"
    )
    mutant = head.replace("**SUPERSEDED-IN-PART**", "NOT **SUPERSEDED-IN-PART**", 1)
    assert not _asserted(mutant, banner), (
        "negation mutant wrongly passed: 'NOT **SUPERSEDED-IN-PART**' still reads as the banner "
        "under a bare substring check — O8's exact finding"
    )
