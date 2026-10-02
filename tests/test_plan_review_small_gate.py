"""Behaviour tests for T05c — spec § The delta D10 (plan-review half) and D11 (execute half).

Both commands here are PROSE, not Python: `/fabrik-plan-review` and `/fabrik-execute-plan` are
markdown command sources rendered into the Claude Code corpus. There is no runtime to invoke, so
the only grader available is the text itself — the same text-assertion style
`test_check_command_corpus.py` uses for `fabrik-deploy-plan.md`/`fabrik-deploy.md` (its
`test_the_deploy_triad_reads_the_frozen_contract_before_the_deploy_not_after`).

Round-1 review (15 CONFIRMED, O3 refuted) found that whole-file substring assertions are too weak:
a clause can be satisfied by the WRONG section (O4), by a negated sentence (O5/O7), or by a
weakened rewrite that still contains the pinned substring (O6/O8). Every assertion below is
therefore SECTION-SCOPED — extracted from exactly the block the Behavior Contract row names — and
every affirmative assertion that admits a plausible negation/weakening carries a paired "the
regressed wording is ABSENT" assertion.
"""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SOURCES = REPO / "commands" / "_sources"


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
    """Row 1: `--surface` names BOTH the plan path AND the spec path (O5: a `--surface` naming only
    the plan, with the spec path merely "read as context", must fail)."""
    section = _plan_review_small_spec_section()
    assert "Size: small" in section
    assert '--surface "<plan path> + <spec path>"' in section
    # O5 regression guard: a --surface that drops the spec path from the flag's own value.
    assert '--surface "<plan path>"' not in section


def test_plan_review_small_spec_exception_runs_one_joint_loop() -> None:
    """Row 1: the spec's sections are graded WITH the plan in one loop — never a first, separate
    pass over the spec (O6: "after a separate first pass over the spec" must fail)."""
    section = _plan_review_small_spec_section()
    assert "in ONE joint loop, never a separate pass" in section
    assert "after a separate first pass" not in section


def test_plan_review_small_spec_exception_flips_the_spec_before_the_plan() -> None:
    """The T05a note: `check_stage_artifacts.py::_check_plan_spec_freshness` refuses a plan's new
    CONVERGED flip while its cited spec is not CONVERGED — so the exception must flip the SPEC to
    CONVERGED first (or in the same commit), then the plan."""
    section = _plan_review_small_spec_section()
    assert "_check_plan_spec_freshness" in section
    assert "flip the SPEC to CONVERGED first" in section
    assert "then the plan" in section


def test_plan_review_small_spec_exception_presents_in_spec_reviews_own_order() -> None:
    """S4/O12 (orchestrator ruling): present exactly what `/fabrik-spec-review` presents — the
    ask↔spec table (built from the spec's own `## Intake Inventory`, never fabricated), the
    converged spec + a summary of what hardened, and the full Pass Ledger — never dropping the
    middle item."""
    section = _plan_review_small_spec_section()
    assert "fabrik-spec-review.md:280-294" in section
    assert "## Intake Inventory" in section
    assert "the converged spec + a short summary of what hardened" in section
    assert "the full Pass Ledger" in section


def test_plan_review_small_spec_exception_does_not_mint_the_approval_row_in_the_loop() -> None:
    """O2 (orchestrator ruling): the approval row is minted ONLY on the operator's explicit
    approval, in a later turn — exactly as `/fabrik-spec-review` does. The loop itself must say it
    does NOT mint the row (O7: a bare "mint the approval row" substring is satisfied by its own
    negation, so both the affirmative deferral and the absence of the old wording are asserted)."""
    section = _plan_review_small_spec_section()
    assert "Do NOT mint the approval row here" in section
    assert "no approval row yet" in section
    assert "LATER turn" in section
    assert "mint the `docs/DECISIONS.md` approval row" in section
    # O7 regression guard: the pre-fix wording that minted the row INSIDE the loop, before gate.
    assert "mint the approval row in `docs/DECISIONS.md` here" not in section


def test_plan_review_small_spec_exception_ends_at_the_gate_not_the_auto_handoff() -> None:
    """Row 1: the run ends at the operator's design-approval gate instead of auto-chaining to
    `/fabrik-execute-plan` — the auto-handoff this command otherwise owns for a fully-autonomous
    run."""
    section = _plan_review_small_spec_section()
    assert "design-approval gate" in section
    assert "do NOT auto-invoke `/fabrik-execute-plan`" in section.replace("Do NOT", "do NOT")


def test_plan_review_small_spec_exception_has_an_estimate_escape_hatch() -> None:
    """O10 (orchestrator ruling): spec § D10 says a plan larger than the spec's `Size: small`
    estimate sends the spec BACK to `/fabrik-spec-review` first — the joint loop is not an
    unconditional substitute for the full review."""
    section = _plan_review_small_spec_section()
    assert "Escape hatch" in section
    assert "outgrows the spec's own `Size: small` estimate" in section
    assert "/fabrik-spec-review` first" in section


def test_plan_review_full_size_spec_is_unaffected() -> None:
    """Row 1 else-branch: a spec with no `Size: small` line keeps today's fully-autonomous flip —
    no joint loop, no gate."""
    section = _plan_review_small_spec_section()
    assert "A spec with no `Size: small` line keeps" in section
    assert "no joint loop, no gate, full autonomy" in section


# ---------------------------------------------------------------------------
# Behavior Contract row 2 — /fabrik-execute-plan's § Execution Loop
# ---------------------------------------------------------------------------


def test_execute_plan_loop_passes_appetite_on_phase_open() -> None:
    """Row 2: each phase start, INSIDE THE EXECUTION LOOP PSEUDOCODE ITSELF (not merely the header
    note above it — O4's mutant deleted the loop's own line and left every assertion green because
    the header carries the same substrings), passes `step --appetite <minutes>`."""
    loop = _execute_plan_loop_section()
    assert "step --phase" in loop
    assert "--appetite <the phase's Appetite: minutes>" in loop


def test_execute_plan_loop_phase_marker_reads_elapsed_over_appetite() -> None:
    """Row 2: the phase marker (`command_run.py line`'s pinned `RUN:` line) reads
    `elapsed <m>/<appetite>`, read from the Execution Loop block itself."""
    loop = _execute_plan_loop_section()
    assert "elapsed <m>/<appetite>" in loop
    assert "command_run.py line" in loop


def test_execute_plan_loop_names_the_2x_standing_order_never_a_forced_cancel() -> None:
    """O8 (orchestrator ruling): D11 is an order + a recorded verdict at 2× budget, NEVER a forced
    cancel — a regression to "past 1x it cancels the phase" must fail."""
    loop = _execute_plan_loop_section()
    assert "past 2×" in loop
    assert "prints a standing order to stop and re-plan the rest of THIS phase" in loop
    assert "never a forced cancel" in loop
    # O8 regression guard: a forced-cancel rewrite, or a 1x threshold.
    assert "past 1×" not in loop
    assert "cancels the phase" not in loop


def test_execute_plan_loop_records_over_appetite_phases_not_over_appetite() -> None:
    """O9 (orchestrator ruling): the execute-plan close field is `over_appetite_phases` (the
    spine's own field name, per D11 and `plan_appetite.py:25`'s comment) and `phase_marks` — never
    the bare `over_appetite` token, which is the UNRELATED `/fabrik-task` close field."""
    loop = _execute_plan_loop_section()
    assert "over_appetite_phases" in loop
    assert "phase_marks" in loop
    # O9 regression guard: the bare token (minus its "_phases" suffix) must not stand alone.
    assert "records over_appetite —" not in loop
    assert "recorded over_appetite —" not in loop


def test_execute_plan_loop_omits_appetite_when_the_phase_declares_none() -> None:
    """O11 (orchestrator ruling): a phase with no `Appetite:` line (pre-rollout plan) omits
    `--appetite` rather than inventing a value."""
    loop = _execute_plan_loop_section()
    assert "omit --appetite when the phase declares none" in loop


def test_execute_plan_loop_dispatcher_coder_timeout_is_untouched() -> None:
    """The ticket's DO-NOT: dispatcher mode's own "Dispatch timeout" bullet (today
    `fabrik-execute-plan.md:527-529`) keeps its exact wording."""
    text = _norm("fabrik-execute-plan.md")
    assert (
        "**Dispatch timeout:** a coder with no result within 2× the ticket's plan-time estimate"
        in text
    )
    assert "2 consecutive timeouts on one ticket → \U0001f534." in text


def test_execute_plan_header_note_names_the_t08_landing_window() -> None:
    """S1/S2/S3/O1 (orchestrator ruling): `--appetite` on `step`, the `elapsed` segment on `line`,
    and the close recording are T08's mechanics, landing in the SAME merge window as T05c — the
    text must say so, not present them as already true of today's `command_run.py`."""
    note = _execute_plan_run_record_note()
    assert "are T08's" in note
    assert "SAME merge window" in note


def test_execute_plan_header_note_has_a_dispatcher_mode_appetite_fallback() -> None:
    """O11 (orchestrator ruling): in DISPATCHER MODE the Appetite sits on the ticket, not the
    phase — the header note must say the executor passes the TICKET's own Appetite there."""
    note = _execute_plan_run_record_note()
    assert "DISPATCHER MODE" in note
    assert "pass the TICKET's own" in note
    assert "Appetite" in note


def test_execute_plan_loop_and_header_note_are_distinct_sections() -> None:
    """Sanity guard for `_section()` itself: the two helpers must not resolve to the same slice —
    O4's whole-file mutant was invisible precisely because nothing distinguished them."""
    assert _execute_plan_run_record_note() != _execute_plan_loop_section()
    assert "for each PHASE in dependency order" in _execute_plan_loop_section()
    assert "for each PHASE in dependency order" not in _execute_plan_run_record_note()
