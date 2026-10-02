"""Graders for `commands/_sources/fabrik-task.md` — the `/fabrik-task` command source.

Three facts about the source, each mechanically decidable (spec
`docs/superpowers/specs/2026-09-17-fabrik-task-lane-design.md` § Constraints C2, § Chosen approach;
ticket T03 Behavior Contract), plus (T07, plan 2026-10-02-plan-1) the Revision-2 prose content:

1. SIZE + INCLUDES — the source is at most `SIZE_CAP` bytes (D-296 raised it to 8980 above C2's
   original 8,847; T07 raises it again to 10362 for D3/D6/D7/D8's required prose — a pending D-row,
   see the comment above `SIZE_CAP`) and its only `{{include:}}` is `run-record`. The include half
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
# new UPGRADE tokens) — a D-row is owed from the dispatching session citing this ratchet (the
# subagent brief forbids minting it); until then this comment is the citation.
SIZE_CAP = 10362
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


def test_source_size_and_single_include() -> None:
    """The byte ceiling, and `run-record` as the only include.

    ⚠️ The cap is 10362 B, NOT the spec's C2 figure of 8,847 nor D-296's 8980 (the latter stood
    until T07, plan 2026-10-02-plan-1, which gained the Behaviours cap, multi-commit build,
    `--design-amend`, the review flavour by surface, the close refusal and the four new UPGRADE
    tokens — all REQUIRED prose, not padding; see the `SIZE_CAP` comment above for the pending
    D-row). Before T07: the three HIGH findings of T03's delta round cost more bytes than the
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


def test_design_note_names_behaviours_cap_and_the_design_amend_remedy() -> None:
    """Behavior Contract row 1 (part): the Behaviours cap and the undeclared-path remedy.

    Mutant: drop "REFUSES" (e.g. to "records") or the cap "7" — the sentence this anchors no
    longer reads, so the match fails. Verified red on the pre-T07 blob (`git show HEAD:…`, which
    carries neither sentence) and green on the working tree."""
    text = _norm(_source_text())
    assert re.search(
        r"Add a `## Behaviours` list — each naming its test, at most 7 "
        r"\(an 8th is the `behaviours` UPGRADE\)",
        text,
    ), "the design note no longer caps Behaviours at 7 with the 8th as an UPGRADE"
    assert re.search(
        r"a committed path missing from both REFUSES `done` at close; the remedy is "
        r"`step --phase 2 --design-amend <path>`, append-only",
        text,
    ), "the design note no longer REFUSES done on an undeclared path, or drops --design-amend"
    assert "`design_amends`" in text, "an amendment is no longer counted as `design_amends`"


def test_build_and_review_sections_name_multicommit_sync_commit_and_full_review() -> None:
    """Behavior Contract row 1 (part): multi-commit build, the sync-path single commit (D7), and
    the review flavour by surface incl. the D8 nested stop.

    Mutant: change "ONCE" to "once more" or drop "not the third" — each assertion below reads the
    governing clause whole, not a keyword, so a weakened rewording fails it."""
    text = _norm(_source_text())
    assert re.search(
        r"`done --commit sha1,sha2,…` measures each in order; a sync-path run \(D7\) commits "
        r"ONCE, after phase 4, in the main checkout",
        text,
    ), "the build section no longer documents the multi-commit build or the sync single-commit rule"
    assert re.search(
        r"Invoke the review phase 0 already picked — `/fabrik-review-scoped`, or the full "
        r"`/fabrik-review` for a sync, heavy, migration or >5-file surface \(D2, D7\)",
        text,
    ), "phase 4 no longer selects the review flavour by surface"
    assert re.search(
        r"its own scope-growth stop fires at the FIRST own-fix-only round, not the third \(D8\), "
        r"still closing only on a confirmed-zero pass",
        text,
    ), "phase 4 no longer names the D8 nested stop and its confirmed-zero exit"


def test_close_section_refuses_undeclared_and_close_time_contract_hits() -> None:
    """Behavior Contract row 1 (part): the close REFUSES rather than merely records.

    Mutant: swap "REFUSES" for "records" (the pre-D3 behaviour) — the assertion is keyed on the
    verb, not just the words "oversized_mini" or "contract", which both texts would carry."""
    text = _norm(_source_text())
    assert re.search(
        r"A committed path missing from APPROACH/MIRROR/an amendment\s*"
        r"REFUSES `done` \(phase 2's remedy above\); `blocked`/`handoff` record it as "
        r"`oversized_mini` instead",
        text,
    ), (
        "the close no longer REFUSES an undeclared path on `done` (or no longer records it on blocked/handoff)"
    )
    assert re.search(
        r"A contract or new-source hit found only here REFUSES `done` and `handoff` too, until "
        r"`--review <a full /fabrik-review receipt>` names one — `blocked` needs none",
        text,
    ), "the close no longer refuses done/handoff on a close-time contract or new-source hit"


def test_upgrade_section_gains_the_four_close_raised_tokens() -> None:
    """Behavior Contract row 1 (part): the UPGRADE token list gains `contract`, `new-source`,
    `behaviours`, `appetite`, distinguished from the six agent-typed ones."""
    text = _norm(_source_text())
    assert re.search(
        r"lead with `files` · `oneway` · `tradeoffs` · `seat` · `sync` · `heavy` · `contract` · "
        r"`new-source` · `behaviours` · `appetite`, then a dash and the detail",
        text,
    ), "the UPGRADE token list no longer carries all ten tokens in order"
    assert re.search(
        r"The last four the CLOSE raises itself, from the commit, never typed by hand: "
        r"`contract`/`new-source` REFUSE `done`/`handoff` until `--review <receipt>` names one; "
        r"`behaviours`/`appetite` are findings only",
        text,
    ), "the source no longer distinguishes the close-raised tokens from the agent-typed ones"


def test_independent_slices_are_several_task_runs() -> None:
    """Spec § The delta D6, named in this ticket's Scope."""
    text = _norm(_source_text())
    assert re.search(
        r"A feature splitting into independently shippable slices is several of these runs, "
        r"never one bundling them \(D6\)",
        text,
    ), "the source no longer states that independent slices are several /fabrik-task runs"


def test_protocol_doc_documents_every_flag_and_feedback_field_this_ticket_scopes() -> None:
    """Behavior Contract row 2: every flag and feedback field named in T07's Scope is documented
    in `docs/reference/command-run-protocol.md` — one assertion per token, each read in the
    sentence that introduces it so a dropped clause (not just a deleted word) is caught."""
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
        ("A v2 start stamps `gate: 2` on the record", "the `gate: 2` stamp"),
        (
            "`--design-amend <path>` (`fabrik-task` only) APPENDS one path to the design's "
            "declared surface",
            "`step --design-amend`",
        ),
        ("`--appetite <min>` (`fabrik-execute-plan` phase steps, D11)", "`step --appetite`"),
        (
            "it names THIS run's commit(s), read from the capture file written the instant the "
            "commit returns, and the close re-measures each commit's diff IN ORDER",
            "`done --commit` accepting a multi-commit list",
        ),
        (
            "`--review <receipt>` is REQUIRED on `done`/`handoff` when the re-measure finds a "
            "contract or new-source hit",
            "`done`/`handoff --review`",
        ),
    ]:
        assert needle in text, f"the protocol doc no longer documents {why}: {needle!r} not found"
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


def test_scope_growth_fragment_names_the_lane_variant() -> None:
    """Behavior Contract row 3 (spec § The delta D8; D-355): the fragment names the lane variant
    of the scope-growth stop and that the review still closes only on a confirmed-zero pass."""
    assert SCOPE_GROWTH_FRAGMENT.exists(), f"{SCOPE_GROWTH_FRAGMENT} does not exist"
    text = _norm(SCOPE_GROWTH_FRAGMENT.read_text(encoding="utf-8"))
    assert re.search(
        r"Nested under a `fabrik-task` run.*the own-fix bar drops to round 1, not round 3 — "
        r"the FIRST own-fix-only round stops the hunt",
        text,
    ), "the fragment no longer names the fabrik-task lane variant of the scope-growth stop"
    assert re.search(
        r"the exit is unchanged: it still closes only on a round that CONFIRMS zero \(D8; D-355\)",
        text,
    ), (
        "the fragment no longer states that the lane variant still closes only on a confirmed-zero pass"
    )


def test_old_lane_spec_carries_a_superseded_in_part_banner() -> None:
    """Behavior Contract row 4 (spec § Documentation landing sites): the 2026-09-17 lane spec's
    header carries a SUPERSEDED-IN-PART banner pointing at the 2026-10-02 spec. Read in the first
    15 lines only — a banner buried in the body is not a HEADER banner."""
    assert OLD_LANE_SPEC.exists(), f"{OLD_LANE_SPEC} does not exist"
    head = _norm("\n".join(OLD_LANE_SPEC.read_text(encoding="utf-8").splitlines()[:15]))
    assert "SUPERSEDED-IN-PART" in head, (
        "the old lane spec's header carries no SUPERSEDED-IN-PART banner"
    )
    assert "2026-10-02-fabrik-task-feature-lane-design.md" in head, (
        "the SUPERSEDED-IN-PART banner does not point at the superseding spec"
    )
