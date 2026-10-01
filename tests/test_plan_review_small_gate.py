"""Behaviour tests for T05c — spec § The delta D10 (plan-review half) and D11 (execute half).

Both commands here are PROSE, not Python: `/fabrik-plan-review` and `/fabrik-execute-plan` are
markdown command sources rendered into the Claude Code corpus. There is no runtime to invoke, so
the only grader available is the text itself — the same text-assertion style
`test_check_command_corpus.py` uses for `fabrik-deploy-plan.md`/`fabrik-deploy.md` (its
`test_the_deploy_triad_reads_the_frozen_contract_before_the_deploy_not_after`). Each assertion names
the exact clause the Behavior Contract row requires, so a future edit that drops the clause (not
just reword it) goes red here.
"""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SOURCES = REPO / "commands" / "_sources"


def _norm(name: str) -> str:
    """Whitespace-normalised source text — immune to line-wrap, never to a dropped clause."""
    return " ".join((SOURCES / name).read_text(encoding="utf-8").split())


def test_plan_review_small_spec_exception_names_the_joint_surface() -> None:
    """Behavior Contract row 1: the small-spec exception names `--surface` with the plan AND the
    spec path — a run graded with only the plan path never actually reviews the spec's sections."""
    text = _norm("fabrik-plan-review.md")
    assert "Size: small" in text
    assert "--surface" in text
    assert "<plan path> + <spec path>" in text or ("<plan path>" in text and "<spec path>" in text)


def test_plan_review_small_spec_exception_runs_one_joint_loop() -> None:
    """Behavior Contract row 1: the spec's sections are graded WITH the plan in one loop — never
    a second, separate pass over the spec."""
    text = _norm("fabrik-plan-review.md")
    assert "joint loop" in text


def test_plan_review_small_spec_exception_flips_the_spec_before_the_plan() -> None:
    """The T05a note: `check_stage_artifacts.py::_check_plan_spec_freshness` refuses a plan's new
    CONVERGED flip while its cited spec is not CONVERGED — so the exception must flip the SPEC to
    CONVERGED first (or in the same commit), then the plan, and say so in the text."""
    text = _norm("fabrik-plan-review.md")
    assert "_check_plan_spec_freshness" in text
    assert "flip the SPEC to CONVERGED first" in text
    assert "then the plan" in text


def test_plan_review_small_spec_exception_mints_the_approval_row_and_ends_at_the_gate() -> None:
    """Behavior Contract row 1: both documents flip to CONVERGED, the approval D-row is minted
    HERE (the duty spec-review holds for full-size work), and the run ends at the operator's
    design-approval gate instead of auto-chaining to `/fabrik-execute-plan` — the auto-handoff this
    command otherwise owns for a fully-autonomous run."""
    text = _norm("fabrik-plan-review.md")
    assert "mint the approval row" in text or "mints the approval row" in text
    assert "fabrik-spec-review.md:280-294" in text
    assert "design-approval gate" in text
    assert "auto-handoff" in text
    assert "Do NOT auto-invoke" in text or "do NOT auto-invoke" in text


def test_execute_plan_phase_start_passes_appetite() -> None:
    """Behavior Contract row 2: each phase start passes `step --appetite <minutes>` — D11's budget
    the phase declared in the plan, not a value invented at execution time."""
    text = _norm("fabrik-execute-plan.md")
    assert "--appetite" in text
    assert "step --phase" in text


def test_execute_plan_phase_marker_reads_elapsed_over_appetite() -> None:
    """Behavior Contract row 2: the phase marker (`command_run.py line`'s pinned `RUN:` line)
    reads `elapsed <m>/<appetite>` once a phase has an appetite budget."""
    text = _norm("fabrik-execute-plan.md")
    assert "elapsed <m>/<appetite>" in text
    assert "command_run.py line" in text


def test_execute_plan_dispatcher_coder_timeout_is_untouched() -> None:
    """The ticket's DO-NOT: dispatcher mode's own "Dispatch timeout" bullet (today
    `fabrik-execute-plan.md:527-529` — the ticket's `fabrik-execute-plan.md` cite for "dispatcher
    mode's coder timeout") keeps its exact wording — this change is additive to phase mode, never a
    rewrite of the dispatcher's own timeout."""
    text = _norm("fabrik-execute-plan.md")
    assert (
        "Dispatch timeout:** a coder with no result within 2× the ticket's plan-time estimate"
        in text
    )
    assert "2 consecutive timeouts on one ticket" in text
