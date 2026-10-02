"""Behaviour tests for T05c — spec § The delta D10 (plan-review half) and D11 (execute half).

Both commands here are PROSE, not Python: `/fabrik-plan-review` and `/fabrik-execute-plan` are
markdown command sources rendered into the Claude Code corpus. There is no runtime to invoke, so
the only grader available is the text itself — the same text-assertion style
`test_check_command_corpus.py` uses for `fabrik-deploy-plan.md`/`fabrik-deploy.md` (its
`test_the_deploy_triad_reads_the_frozen_contract_before_the_deploy_not_after`).

Round 1 (15 CONFIRMED, O3 refuted) found that whole-file substring assertions are too weak: a
clause can be satisfied by the WRONG section (O4), by a negated sentence (O5/O7), or by a weakened
rewrite that still contains the pinned substring (O6/O8). Round 1's own fix — ad hoc
`assert X not in text` pairs for the four worst offenders — was itself too weak (W-afe28a4a): a
SHORT affirmative pin (`"pass the TICKET's own"`) is still a literal substring of its own negation
(`"do NOT pass the TICKET's own"`), and a one-phrase `not in` guard only catches the ONE wording it
names, not `never`/`don't`/a capitalised `NOT`/an appended "or anywhere" qualifier.

`assert_affirmed()` replaces every bare `in`/`not in` pair in this file with ONE check: the
governing sentence, anchored on its own leading verb and subject so an insertion ANYWHERE inside it
breaks the literal match outright, PLUS a scan of the clause housing it (extended to the nearest
`.`/`;`/`—`/`:` on each side, excluding the pinned span itself) for a negation or weakening token.
A sentence that is ITSELF negative ("**Do NOT mint the approval row here**") is the affirmed
content, not a corruption — only text OUTSIDE the pinned span is scanned.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SOURCES = REPO / "commands" / "_sources"

# Case-insensitive negation tokens (word-bounded where that makes sense) + the two multi-word/
# suffix forms that cannot be: a contraction's "n't" and the two-word "instead of".
_NEGATION_RE = re.compile(r"\b(not|never|no|skip|skips|without)\b|n't|instead of", re.IGNORECASE)
# A weakening qualifier that broadens a precise trigger without negating it outright.
_WEAKENING_RE = re.compile(r"\banywhere\b", re.IGNORECASE)
# Clause boundaries for this prose: sentence/semicolon/em-dash breaks, plus the colon this
# command's terse pseudocode uses in place of punctuation ("for each PHASE in dependency order:").
_CLAUSE_BOUNDARY_CHARS = ".;—:"


def _raw(name: str) -> str:
    return (SOURCES / name).read_text(encoding="utf-8")


def _norm(name: str) -> str:
    """Whitespace-normalised source text — immune to line-wrap, never to a dropped clause."""
    return " ".join(_raw(name).split())


def _section(text: str, start: str, end: str) -> str:
    """The whitespace-normalised slice from `start` (inclusive) to the next `end` after it.

    O4 found that a whole-file grep is satisfied by a match living in an UNRELATED section (the
    run-record header paragraph, not the Execution Loop pseudocode it was meant to grade) — so a
    test naming one section must read ONLY that section's text.
    """
    i = text.index(start)
    j = text.index(end, i + len(start))
    return text[i:j]


def _clause_window(section: str, start: int, end: int) -> tuple[int, int]:
    """Expand `[start, end)` outward to the nearest clause-boundary character on each side."""
    cs = start
    while cs > 0 and section[cs - 1] not in _CLAUSE_BOUNDARY_CHARS:
        cs -= 1
    ce = end
    while ce < len(section) and section[ce] not in _CLAUSE_BOUNDARY_CHARS:
        ce += 1
    return cs, ce


def assert_affirmed(section: str, sentence: str) -> None:
    """Assert `sentence` stands, verbatim and UNNEGATED, as the governing text of its clause.

    Two checks close the gap every prior round's bare `in`/`not in` pair left open (O5-O9, O12-O16,
    the W-afe28a4a remainder):

    1. `sentence` is present character-for-character, anchored on its own leading verb and
       subject — an insertion ANYWHERE inside it (a prepended "do NOT", an appended "or anywhere
       else", a swapped verb like "skips" for "ends at") breaks the match outright, not just a
       sub-phrase of it.
    2. The clause housing `sentence` — `sentence` itself, extended outward to the nearest
       `.`/`;`/`—`/`:` on each side — carries no negation token (not/never/no/skip(s)/without/n't/
       "instead of", case-insensitive) and no weakening qualifier ("anywhere") OUTSIDE `sentence`'s
       own span. A negation INSIDE the pinned text (a sentence that is itself "Do NOT mint …") is
       the affirmed content, not a corruption, so only the surrounding context is scanned.
    """
    assert sentence in section, f"governing sentence not found verbatim: {sentence!r}"
    start = section.index(sentence)
    end = start + len(sentence)
    cs, ce = _clause_window(section, start, end)
    surrounding = section[cs:start] + section[end:ce]
    neg = _NEGATION_RE.search(surrounding)
    assert neg is None, (
        f"negation token {neg.group()!r} found around the pinned sentence "
        f"(clause: {section[cs:ce]!r})"
    )
    weak = _WEAKENING_RE.search(surrounding)
    assert weak is None, (
        f"weakening token {weak.group()!r} found around the pinned sentence "
        f"(clause: {section[cs:ce]!r})"
    )


def _plan_review_small_spec_section() -> str:
    text = _norm("fabrik-plan-review.md")
    return _section(text, "**Small-spec exception", "{{include:grounding-artifact}}")


def _execute_plan_run_record_note() -> str:
    """The run-record header's phase-open note (old line 27) — distinct from the Execution Loop
    pseudocode block; O4's mutant deleted the pseudocode block and left this note standing, which
    is why the two are graded separately below."""
    text = _norm("fabrik-execute-plan.md")
    return _section(
        text,
        '`step --phase <N> --title "<the plan\'s phase title>"',
        "## Before You Start",
    )


def _execute_plan_loop_section() -> str:
    text = _norm("fabrik-execute-plan.md")
    return _section(text, "## Execution Loop", "## Dispatcher Mode")


# ---------------------------------------------------------------------------
# Behavior Contract row 1 — /fabrik-plan-review's small-spec exception
# ---------------------------------------------------------------------------


def test_plan_review_small_spec_exception_names_the_joint_surface() -> None:
    """Row 1: `--surface` names BOTH the plan path AND the spec path, and the `Size: small` trigger
    is pinned on its own line (O5/O8/O14: a `--surface` naming only the plan, a trigger weakened to
    "anywhere in its body", or an "or anywhere else" append must all fail)."""
    section = _plan_review_small_spec_section()
    assert_affirmed(
        section,
        "When the plan's cited spec carries `Size: small` on its own line, this run starts with "
        '`--surface "<plan path> + <spec path>"`',
    )


def test_plan_review_small_spec_exception_runs_one_joint_loop() -> None:
    """Row 1: the spec's sections are graded WITH the plan in one loop — never a first, separate
    pass over the spec (O6: "after a separate first pass over the spec" must fail)."""
    section = _plan_review_small_spec_section()
    assert_affirmed(
        section,
        "the review grades the spec's sections together with the plan in ONE joint loop, never a "
        "separate pass over the spec",
    )


def test_plan_review_small_spec_exception_flips_the_spec_before_the_plan() -> None:
    """The T05a note: `check_stage_artifacts.py::_check_plan_spec_freshness` refuses a plan's new
    CONVERGED flip while its cited spec is not CONVERGED — so the exception must flip the SPEC to
    CONVERGED first (or in the same commit), then the plan."""
    section = _plan_review_small_spec_section()
    assert_affirmed(
        section,
        "`check_stage_artifacts.py::_check_plan_spec_freshness` refuses a plan's new CONVERGED "
        "flip while its cited spec is not CONVERGED",
    )
    assert_affirmed(
        section,
        "flip the SPEC to CONVERGED first (or in the same commit as the plan), then the plan",
    )


def test_plan_review_small_spec_exception_has_an_estimate_escape_hatch() -> None:
    """O10 (orchestrator ruling): spec § D10 says a plan larger than the spec's `Size: small`
    estimate sends the spec BACK to `/fabrik-spec-review` first (O16: "never send it to
    `/fabrik-spec-review` first" must fail — the bare citation substring survives that negation)."""
    section = _plan_review_small_spec_section()
    assert_affirmed(
        section,
        "if the converging plan outgrows the spec's own `Size: small` estimate (D-169's rule: more "
        "than ~400 code lines OR more than 5 code files, tests excluded), remove the `Size: small` "
        "line from the spec and send it to `/fabrik-spec-review` first",
    )


def test_plan_review_small_spec_exception_presents_in_spec_reviews_own_order() -> None:
    """S4/O12 (orchestrator ruling): present exactly what `/fabrik-spec-review` presents — the
    ask↔spec table (built from the spec's own `## Intake Inventory`, never fabricated), the
    converged spec + a summary of what hardened, and the full Pass Ledger — never dropping the
    middle item, and never ENDING the run some other way (O16: "skips the operator's
    design-approval gate" must fail)."""
    section = _plan_review_small_spec_section()
    assert_affirmed(
        section,
        "this run ends at the operator's design-approval gate — present exactly what "
        "`/fabrik-spec-review` presents (`fabrik-spec-review.md:280-296`), in the same order",
    )
    assert_affirmed(
        section,
        "(1) the ask↔spec comparison table, built from the spec's own `## Intake Inventory` "
        "section (the A0a enumeration `/fabrik-spec` already wrote when it authored this spec — "
        "this loop never re-runs that step and never fabricates rows)",
    )
    assert_affirmed(section, "(2) the converged spec + a short summary of what hardened")
    assert_affirmed(
        section,
        "(3) the full Pass Ledger; then **end the turn** with the `DECISION NEEDED (ground: gate)` "
        "block asking for design approval",
    )


def test_plan_review_small_spec_exception_does_not_mint_the_approval_row_in_the_loop() -> None:
    """O2 (orchestrator ruling): the approval row is minted ONLY on the operator's explicit
    approval, in a later turn — exactly as `/fabrik-spec-review` does. The loop itself must say it
    does NOT mint the row, and that prohibition must be the sentence's OWN wording (O7: a bare
    "mint the approval row" substring is satisfied by its own negation elsewhere)."""
    section = _plan_review_small_spec_section()
    assert_affirmed(
        section,
        "**Do NOT mint the approval row here, and do NOT auto-invoke `/fabrik-execute-plan`** — "
        "exactly as `/fabrik-spec-review` does today, this loop ends with BOTH documents CONVERGED "
        "and no approval row yet",
    )
    assert_affirmed(
        section,
        "only on the operator's explicit approval, in a LATER turn, does that approving turn's "
        "session mint the `docs/DECISIONS.md` approval row",
    )


def test_plan_review_full_size_spec_is_unaffected() -> None:
    """Row 1 else-branch: a spec with no `Size: small` line keeps today's fully-autonomous flip —
    no joint loop, no gate."""
    section = _plan_review_small_spec_section()
    assert_affirmed(
        section,
        "A spec with no `Size: small` line keeps today's behaviour unchanged: no joint loop, no "
        "gate, full autonomy.",
    )


# ---------------------------------------------------------------------------
# Behavior Contract row 2 — /fabrik-execute-plan's § Execution Loop
# ---------------------------------------------------------------------------


def test_execute_plan_loop_passes_appetite_on_phase_open() -> None:
    """Row 2: each phase start, INSIDE THE EXECUTION LOOP PSEUDOCODE ITSELF (not merely the header
    note above it — O4's mutant deleted the loop's own line and left every assertion green because
    the header carries the same substrings), passes `step --appetite <minutes>`."""
    loop = _execute_plan_loop_section()
    assert_affirmed(
        loop,
        'step --phase <N> --title "<phase title>" --appetite <the phase\'s Appetite: minutes>',
    )


def test_execute_plan_loop_phase_marker_reads_elapsed_over_appetite() -> None:
    """Row 2: the phase marker (`command_run.py line`'s pinned `RUN:` line) reads
    `elapsed <m>/<appetite>`, read from the Execution Loop block itself."""
    loop = _execute_plan_loop_section()
    assert_affirmed(loop, "`command_run.py line` shows `elapsed <m>/<appetite>`")


def test_execute_plan_loop_omits_appetite_when_the_phase_declares_none() -> None:
    """O11 (orchestrator ruling): a phase with no `Appetite:` line (pre-rollout plan) omits
    `--appetite` rather than inventing a value, and this is T08-landed per the run-record note."""
    loop = _execute_plan_loop_section()
    assert_affirmed(
        loop,
        "T08-landed per the run-record note above — omit --appetite when the phase declares none",
    )


def test_execute_plan_loop_names_the_2x_standing_order_never_a_forced_cancel() -> None:
    """O8 (orchestrator ruling): D11 is an order + a recorded verdict at 2× budget, NEVER a forced
    cancel — a regression to "past 1x it cancels the phase" must fail."""
    loop = _execute_plan_loop_section()
    assert_affirmed(
        loop,
        "past 2× it prints a standing order to stop and re-plan the rest of THIS phase with "
        "/fabrik-plan-after-chat",
    )
    assert_affirmed(
        loop,
        "an order and a recorded verdict, never a forced cancel (dispatcher mode's own \"Dispatch "
        'timeout" bullet, § Dispatcher Mode, is unchanged by this)',
    )


def test_execute_plan_loop_records_over_appetite_phases_not_over_appetite() -> None:
    """O9 (orchestrator ruling): the execute-plan close field is `over_appetite_phases` (the
    spine's own field name, per D11 and `plan_appetite.py:25`'s comment) and `phase_marks` — never
    the bare `over_appetite` token, which is the UNRELATED `/fabrik-task` close field."""
    loop = _execute_plan_loop_section()
    assert_affirmed(
        loop,
        "the close records the overrun in `over_appetite_phases` (count) and this phase's own "
        "`phase_marks` entry",
    )


def test_execute_plan_loop_dispatcher_coder_timeout_is_untouched() -> None:
    """The ticket's DO-NOT: dispatcher mode's own "Dispatch timeout" bullet (today
    `fabrik-execute-plan.md:527-529`) keeps its exact wording."""
    text = _norm("fabrik-execute-plan.md")
    assert_affirmed(
        text,
        "**Dispatch timeout:** a coder with no result within 2× the ticket's plan-time estimate "
        "(no estimate stated → use 30 min as the estimate, i.e. a 60-minute timeout) → the D6 "
        "salvage procedure; 2 consecutive timeouts on one ticket → \U0001f534.",
    )


def test_execute_plan_header_note_names_the_t08_landing_window() -> None:
    """S1/S2/S3/O1 (orchestrator ruling): `--appetite` on `step`, the `elapsed` segment on `line`,
    and the close recording are T08's mechanics, landing in the SAME merge window as T05c (O15:
    "NOT in the SAME merge window" must fail — the bare "SAME merge window" substring survives
    that negation)."""
    note = _execute_plan_run_record_note()
    assert_affirmed(
        note,
        "`--appetite` on `step`, the `elapsed <m>/<appetite>` segment on `line`, and the "
        "`over_appetite_phases`/`phase_marks` recording on `done` are T08's — they land in the "
        "SAME merge window as this change, so this text never runs ahead of the code it describes",
    )


def test_execute_plan_header_note_has_a_dispatcher_mode_appetite_fallback() -> None:
    """O11 (orchestrator ruling): in DISPATCHER MODE the Appetite sits on the ticket, not the
    phase — the header note must say the executor passes the TICKET's own Appetite there (O13: "do
    NOT"/"never"/"don't pass the TICKET's own" must all fail — a lowercase-only guard on one
    phrasing is not enough)."""
    note = _execute_plan_run_record_note()
    assert_affirmed(
        note,
        "Omit `--appetite` when the phase declares no `Appetite:` line (a plan dated before the "
        "rollout is not re-graded and may carry none)",
    )
    assert_affirmed(
        note,
        "in DISPATCHER MODE (§ Dispatcher Mode below) pass the TICKET's own `Appetite:` instead, "
        "since a spine declares none",
    )


def test_execute_plan_loop_and_header_note_are_distinct_sections() -> None:
    """Sanity guard for `_section()` itself: the two helpers must not resolve to the same slice —
    O4's whole-file mutant was invisible precisely because nothing distinguished them. (Structural,
    not a prose assertion — `assert_affirmed` does not apply.)"""
    assert _execute_plan_run_record_note() != _execute_plan_loop_section()
    assert "for each PHASE in dependency order" in _execute_plan_loop_section()
    assert "for each PHASE in dependency order" not in _execute_plan_run_record_note()
