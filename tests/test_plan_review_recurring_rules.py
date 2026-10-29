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
        "before the first pin, RUN every new module, stub or algorithm the plan specifies on a scratch copy "
        "over the plan's own Behavior Contract inputs, so no seat is the first to execute it."
    ) in step2


def test_the_panel_delta_round_shares_the_scope_growth_window() -> None:
    """panel-delta-scope-growth (3 rows): one loop, one window; the backlog exit only once the stop fired."""
    accepted = _between(_norm(FRAG / "design-critique.md"), "- `ACCEPTED`", "- `REJECTED`")
    assert (
        "(a round that confirms more leaves the artifact `DRAFT` and the loop continues — that round is a delta round "
        "of the same loop, so its own-fix defects count "
        "in the same scope-growth window and, once the scope-growth stop has fired, route to its backlog row — "
        "residue a delta round raises AFTER the stop fired is `RECORDED — measured` there (term-edit's scope-growth "
        "stop), not confirmed, so it does not hold the flip, while the round that fires the stop confirms and "
        "fixes its defects and does; an artifact already CONVERGED at HEAD, re-reviewed, goes back to `DRAFT` with a "
        "row superseding its flip row until such a round confirms 0); an "
        "OSCILLATING advisory naming that round's count after an earlier 0 is expected there, not drift; in "
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
        # term-coverage's input-space duty moved to the head of its round zero (W-7c290366), so the
        # interface duty now follows the class sweep there; term-edit keeps the input-space duty before it
        before = (
            "not to run another round; "
            if frag == "term-coverage.md"
            else "listed before the probe runs; "
        )
        want = (
            before + "a fix that names an interface (a function, flag, field or verb) cites the "
            f"callee's signature and line range read {at}, and is re-read against that range before the pin; "
            "a fix to a matcher, replacer, predicate or filter, a regex included"
        )
        assert want in zero, frag


def test_plan_tickets_reruns_after_every_behavior_contract_edit_and_the_small_loop_flips_at_the_panel() -> (
    None
):
    """Row 1791954506: a stale roll-up cost a round because check_plan_tickets was not re-run after ticket rows
    were edited mid-loop; and the Size: small joint loop flips both documents in the panel's approval commit."""
    text = _norm(REPO / "commands" / "_sources" / "fabrik-plan-review.md")
    assert (
        "must exit 0 before the `CONVERGED` flip, and again after every edit to a ticket's Behavior Contract (the"
        " spine's roll-up must still equal its tickets' rows)"
    ) in text
    assert (
        "Once the joint loop's closing round is quiet (both documents still `DRAFT`, flipped in the approval"
        " commit), this run ends at the design-approval gate"
    ) in text
