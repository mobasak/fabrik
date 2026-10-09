"""/fabrik-plan-review queue — recurring HELD subjects (D-711: a recurrence is edited, never re-rejected).

Each test asserts the rule sentence inside the paragraph that owns it (a relocated or negated copy elsewhere in
the file is a mutation), through its delimiter, in every fragment that carries the rule.
"""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
FRAG = REPO / "commands" / "_fragments"


def _norm(p: Path) -> str:
    return " ".join(p.read_text(encoding="utf-8").split())


def _between(text: str, start: str, end: str) -> str:
    i = text.index(start)
    return text[i : text.index(end, i)]


def test_checklist_rows_are_adjudicated_before_the_closing_pass_and_new_code_runs_before_the_pin() -> (
    None
):
    """checklist-adjudication-timing (4 rows) and execute-plan-snippets-early (2 rows), in step 2."""
    step2 = _between(
        _norm(REPO / "commands" / "_sources" / "fabrik-plan-review.md"),
        "2. **Coverage Checklist.**",
        "3. **",
    )
    assert (
        "Adjudicate each row in the round whose evidence settles it — the rows the plan already proves before "
        "the first pin, the rest no later than the last delta round — so the closing pass re-derives verdicts "
        "and the flip adds no content."
    ) in step2
    assert (
        "before the first pin, RUN every new module, stub or algorithm the plan specifies on a scratch copy "
        "over the plan's own Behavior Contract inputs, so no seat is the first to execute it."
    ) in step2


def test_the_panel_delta_round_shares_the_scope_growth_window() -> None:
    """panel-delta-scope-growth (3 rows): one loop, one window; the backlog exit only once the stop fired."""
    accepted = _between(_norm(FRAG / "design-critique.md"), "- `ACCEPTED`", "- `REJECTED`")
    assert (
        "(else the loop continues — that round is a delta round of the same loop, so its own-fix defects count "
        "in the same scope-growth window and, once the scope-growth stop has fired, route to its backlog row); in "
        "`/fabrik-task`"
    ) in accepted


def test_round_zero_cites_the_callee_in_both_review_contracts() -> None:
    """fix-cites-callee-source (2 rows): term-edit and term-coverage round zero, before the regex rule; each names
    the commit it reads the callee at in its own vocabulary (term-edit pins by SHA, term-coverage by the briefs)."""
    pin = {
        "term-edit.md": "at the pinned SHA",
        "term-coverage.md": "at the commit the round's briefs pin (`git show <sha>:<path>`)",
    }
    for frag, at in pin.items():
        zero = _between(_norm(FRAG / frag), "**Round zero", "bind the probe:")
        want = (
            "listed before the probe runs; a fix that names an interface (a function, flag, field or verb) cites the "
            f"callee's signature and line range read {at}, and is re-read against that range before the pin; "
            "a regex fix"
        )
        assert want in zero, frag


def test_the_flip_copy_recipe_is_the_matrix_rows_method() -> None:
    """flip-gate-scratch-root (2 rows): the copy shows the flip as a change and links scripts/ and .windsurf/."""
    gate = _between(_norm(FRAG / "term-edit.md"), "a gate run COUNTS only", "**Round zero")
    assert (
        "so a flipped scratch copy is a git checkout in which the flip shows as a change, the DRAFT committed and "
        "the flip in the working tree or staged (`check_convergence` grades only the plans `git status` lists "
        "there), with the repo's `scripts/` and `.windsurf/` linked in, the MATRIX row's method (without them "
        "`check_rule_grounding` reports the plan UNGRADED and every digest quote QUOTE-NOT-FOUND)."
    ) in gate
