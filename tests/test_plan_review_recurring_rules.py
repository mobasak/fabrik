"""/fabrik-plan-review queue — recurring HELD subjects (D-711: a recurrence is edited, never re-rejected).

Each test asserts the rule sentence in the file every consumer renders it from, through its delimiter.
"""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
FRAG = REPO / "commands" / "_fragments"


def _norm(p: Path) -> str:
    return " ".join(p.read_text(encoding="utf-8").split())


def test_checklist_rows_are_adjudicated_before_the_closing_pass_and_new_code_runs_before_the_pin() -> (
    None
):
    """checklist-adjudication-timing (4 rows) and execute-plan-snippets-early (2 rows)."""
    t = _norm(REPO / "commands" / "_sources" / "fabrik-plan-review.md")
    assert (
        "Adjudicate each row in the round whose evidence settles it — the rows the plan already proves before "
        "the first pin, the rest no later than the last delta round — so the closing pass re-derives verdicts "
        "and the flip adds no content."
    ) in t
    assert (
        "before the first pin, RUN every new module, stub or algorithm the plan specifies on a scratch copy "
        "over the plan's own Behavior Contract inputs, so no seat is the first to execute it."
    ) in t


def test_the_panel_delta_round_shares_the_scope_growth_window() -> None:
    """panel-delta-scope-growth (3 rows): one loop, one window, one backlog row."""
    t = _norm(FRAG / "design-critique.md")
    assert (
        "(else the loop continues — that round is a delta round of the same loop, so its own-fix defects count "
        "in the same scope-growth window and route to the same backlog row); in `/fabrik-task`"
    ) in t


def test_round_zero_cites_the_callee_and_the_flip_copy_is_gradeable() -> None:
    """fix-cites-callee-source (2 rows) and flip-gate-scratch-root (2 rows)."""
    t = _norm(FRAG / "term-edit.md")
    assert (
        "a fix that names an interface (a function, flag, field or verb) cites the callee's signature and line "
        "range read at the pinned SHA, and is re-read against that range before the pin"
    ) in t
    assert (
        "so a flipped scratch copy is a git checkout whose commit holds the DRAFT and whose working tree holds "
        "the flip (`check_convergence` grades only the plans `git status` lists there), with the repo's "
        "`scripts/review_rubric.py` and `.windsurf/rules/` beside it (`check_rule_grounding` reports the plan "
        "UNGRADED without them)."
    ) in t
