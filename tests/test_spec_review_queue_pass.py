"""/fabrik-spec-review feedback queue answered in one pass (D-735): the pass ceiling, the round recipe, Phase 0.

The ceiling test is a property over every command source, since the same wrong phrase sat in four of them.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ROOT / "commands" / "_sources"
SRC = SOURCES / "fabrik-spec-review.md"


def _norm(path: Path = SRC) -> str:
    return re.sub(r"\s+", " ", path.read_text())


def test_no_command_caps_the_workflow_pass_number() -> None:
    """Row 1790692298: term-edit has no round ceiling and the workflow never validates `pass`."""
    capped = [p.name for p in sorted(SOURCES.glob("*.md")) if "`pass: 2|3`" in _norm(p)]
    assert not capped, capped
    for name in (
        "fabrik-spec-review.md",
        "fabrik-plan-review.md",
        "fabrik-review-scoped.md",
        "fabrik-review.md",
    ):
        assert "`pass: <n>`, the next pass number (unbounded)" in _norm(SOURCES / name), name


def test_the_round_recipe_states_own_fix() -> None:
    """Row 1790713088: term-edit makes every delta round state --own-fix; both recipes omitted it."""
    for path in (SRC, SOURCES / "fabrik-plan-review.md"):
        assert (
            "--own-fix <own-fix; round 1: 0> --slices <name>:<verified>/<claims>,… --classes-swept <every class swept>"
            in _norm(path)
        ), path.name


def test_an_executable_rule_is_run_from_round_one_not_only_at_the_close() -> None:
    """Row 1792014614 (fleet, the scratch-lifecycle spec review): the spec's state classifier was read, not run,
    for three delta rounds; the contradiction surfaced only when the closing round executed it. Row 1791448830
    had asked the same and was rejected as 'already in term-edit' — which placed the execution at the CLOSING
    round only, so the second filing was a placement gap, not a repeat (D-711). The rule's home is
    `commands/_fragments/term-edit.md` (rendered into 17 review-family commands): obligation (4) of the
    before-every-pin list runs the artifact's rule at pass 1 and after every fix that touched it, and the closing
    paragraph re-executes it and points at (4). Mutants: restore 'the closing round EXECUTES it' (execution at the
    close only), delete obligation (4), 'four' back to 'three', drop 'EVERY case', drop 'a fix touched the rule or
    a case', append 'where convenient' — each fails an assertion."""
    assert "{{include:term-edit}}" in SRC.read_text(), (
        "the spec-review source no longer renders the fragment"
    )


def test_phase_zero_points_at_the_flip_gates() -> None:
    """Rows 1789467454, 1789418890: the flipped-scratch-copy gate as a Phase 0 step."""
    p0 = _norm()[_norm().index("## Phase 0") : _norm().index("## Phase 1")]
    assert (
        "**Flip gates, at Pass 1 and at the close:** run term-edit's flip gates on a flipped SCRATCH copy before Pass 1 and again at the close"
        in p0
    )


def test_briefs_apply_the_probe_catalogue() -> None:
    """Row 1790716618: the catalogue the review family already applies."""
    assert (
        "`/opt/fabrik/commands/_fragments/review-probe-catalogue.md` that match the change's SHAPE"
        in _norm()
    )


def test_flow_fixes_panel_residue_and_absolute_brief_paths() -> None:
    """Rows 1791937893 and 1791945243: a code-FLOW fix is invariants from its first edit; routed panel-delta
    residue is recorded, never confirmed, so it keeps the flip; a brief's pin, copy and fix paths are absolute."""
    assert (
        "every fix inside such a section is written as invariants + touchpoints from its FIRST edit — not only "
        "once the edit loop's TWO CONSECUTIVE RESIDUE PASSES rule forces a rewrite there — and never as a re-worded "
        "sequence or new mechanism"
    ) in _norm()
    critique = _norm(ROOT / "commands" / "_fragments" / "design-critique.md")
    assert (
        "residue a delta round raises AFTER the stop fired is `RECORDED — measured` there (term-edit's scope-growth "
        "stop), not confirmed, so it does not hold the flip, while the round that fires the stop confirms and "
        "fixes its defects and does"
    ) in critique
    core = _norm(ROOT / "commands" / "_fragments" / "subagents-core.md")
    assert (
        "The dispatcher writes every pin, copy, fix and scratch path a brief names as a literal absolute path, never "
        "one relative to a checkout or a placeholder the seat expands"
    ) in core


def test_both_design_reviews_name_the_receipt_and_the_command_line_the_gate_routes_on(
    tmp_path: Path,
) -> None:
    """Mail 01M4W4ZWTZ: check_convergence routes a design receipt by its header `Command:` line, so each review
    command names its receipt path and that line, and the line as written routes through the real checker."""
    from scripts.enforcement import check_convergence as cc

    ledger = (
        "\n## Pass Ledger\n| Pass 1 | found: 0, new: 0, confirmed: 0, fixed: 0, unexecuted: 0 |\n"
    )
    # plan-review's sentence names BOTH ledger homes since row 1792013533 (its own queue-pass test pins the whole
    # sentence); the receipt path, the header line and the label-routed grading are what this test asserts for both
    expected = {
        "spec": (
            "The Pass Ledger lives in the review receipt,"
            " `docs/development/reviews/<YYYY-MM-DD>-<slug>-spec-review.md`, whose first 10 lines carry the line"
            " `**Command:** /fabrik-spec-review`: once the receipt claims a finished review,"
            " `check_convergence.py` grades it by its ledger only under that label, and demands a code review's"
            " gate embed without it."
        ),
        "plan": (
            "The review receipt, `docs/development/reviews/<YYYY-MM-DD>-<slug>-plan-review.md`, whose first 10 lines"
            " carry the line `**Command:** /fabrik-plan-review`, carries the same ledger plus the panel table and the"
            " ask↔spec table: once it claims a finished review, the gate grades it by its ledger only under that label"
        ),
    }
    for kind in ("spec", "plan"):
        text = _norm(SOURCES / f"fabrik-{kind}-review.md")
        assert expected[kind] in text
        line = re.search(r"`(\*\*Command:\*\* /fabrik-" + kind + r"-review)`", text).group(1)
        inside = tmp_path / f"{kind}-inside.md"
        inside.write_text(f"# Review\n\n**Status:** CONVERGED\n{line}\n{ledger}")
        assert cc._check_review(tmp_path, inside) == []
        past = tmp_path / f"{kind}-past.md"
        past.write_text("# Review\n\n**Status:** CONVERGED\n" + "x\n" * 7 + f"{line}\n{ledger}")
        assert cc._check_review(tmp_path, past)


def test_an_accepted_panel_change_is_written_as_required_behaviour() -> None:
    """Row 1792016473 (infra, the coordinator-role spec review): pass 5's seven residue findings came from
    panel fixes written as mechanism text; the panel step said only 'apply every ACCEPTED change', and Phase 1
    D's invariants rule was never pointed at from the panel section. Now: Phase 1 D's rule covers a parenthesis
    or example and the one-way decision the spec must settle (one rule for loop fixes and panel fixes alike);
    the After-the-quiet-closing-round list points a panel change at that rule and translates a seat's proposed
    mechanism to the behaviour it secures; the shared panel step 2 tells every includer to write the change as
    its command's own fix-shape rule says. The row's other half (the closing round passes --slices) is already
    stated at design-critique.md and is asserted here so it stays. Mutants: delete the bullet, move it after the
    comparison-table bullet, drop 'translated to the behaviour it secures', drop D's parenthesis clause or its
    decision clause, append 'where practical' to the bullet, drop the fragment's pointer — each fails an
    assertion (the bullet is bounded from its head to the next list item)."""
    text = _norm()
    # ONE rule, in Phase 1 D, for every fix in a flow section — the panel path points at it, never restates it
    rule = (
        "every fix inside such a section is written as invariants + touchpoints from its FIRST edit — not only"
        " once the edit loop's TWO CONSECUTIVE RESIDUE PASSES rule forces a rewrite there — and never as a"
        " re-worded sequence or new mechanism. That holds in the sentence itself and in a parenthesis or example"
        " beside it; a change that is itself a decision the spec must settle states the decision (naming what it"
        " chose) and the constraint it imposes, never the steps that carry it out."
    )
    assert rule in text, (
        "Phase 1 D's rule lost its parenthesis clause or its one-way decision clause"
    )
    assert (
        "A section describing a code FLOW states its invariants and touchpoints (what must hold, which paths it"
        " touches); the executable sequence belongs to the plan, so " + rule
    ) in text, "D's flow-sentence head (what 'such a section' refers to) is gone"
    after = text[text.index("## After the quiet closing round") :]
    head = "- **An ACCEPTED panel change is a fix under Phase 1 D's flow rule — this command's fix-shape rule**"
    assert head in after, "the panel-fix bullet left the After-the-quiet-closing-round section"
    start = after.index(head)
    assert after.index("{{include:design-gate-panel}}") < start, (
        "the bullet sits after the panel include"
    )
    bullet = after[start : after.index(" - **", start + len(head))]
    assert (
        bullet.startswith(head)
        and "**The ask ↔ spec comparison table**" in after[start + len(bullet) :][:80]
    ), "the bullet is the first list item after the include, right before the comparison table"
    assert (
        "(invariants + touchpoints, never a re-worded sequence or new mechanism): a seat's proposed mechanism is"
        " translated to the behaviour it secures, and its verb, flag or sequence is left to the plan."
    ) in bullet, "the pointer, the translation rule and the plan boundary are one contiguous clause"
    assert bullet.rstrip().endswith("left to the plan."), bullet[-80:]
    for weakener in ("where practical", "where possible", "optionally", "should", "unless"):
        assert weakener not in bullet.lower(), weakener
    panel = _norm(ROOT / "commands" / "_fragments" / "design-gate-panel.md")
    assert (
        "Apply every ACCEPTED change to the artifact — written as this command's own fix-shape rule says, where"
        " it states one — and to any linked artifact it makes stale"
    ) in panel, "the shared step 2 must point every includer at its command's own fix-shape rule"
    assert (
        "approval row lists each change as written — a translated mechanism is listed as the behaviour it secures —"
        " and the delta round's seats check each one in the revised artifact."
    ) in panel, "the Cobra counter must count a translated change as made"
    critique = _norm(ROOT / "commands" / "_fragments" / "design-critique.md")
    assert "with every slice an earlier round stated re-stated in `--slices`" in critique, (
        "the panel delta round's --slices restatement (the row's other half) is already stated there"
    )
