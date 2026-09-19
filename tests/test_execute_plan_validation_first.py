"""The § Before You Start step-6 ruling: a plan's own validation of the rule it BUILDS runs first.

D-298 measured the cost of the inverse: a backtest scheduled in the integration ticket returned its
verdict after six tickets had implemented the rule and two governance contracts carried it, having
survived three `/fabrik-spec-review` runs, a `/fabrik-plan-review` and fifteen execution review
rounds. The ruling is prose in a 100 KB command, which is exactly the shape that gets reworded away;
`tests/test_execute_plan_d7.py` is this file's precedent for pinning a load-bearing ordering rule.
"""

from __future__ import annotations

from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / "commands" / "_sources" / "fabrik-execute-plan.md"


def _step6() -> str:
    """The step-6 block of § Before You Start — both anchors asserted, and BOUNDED.

    The first cut split on `"\\n7. "`, which matches twice in this file (step 7 of this section and
    step 7 of § Finish). Renumbering step 7 — the routine edit here — widened the span to 93% of
    the file, and every assertion below then passed with the clause re-homed 130 lines away, which
    is precisely what `test_the_pin_is_not_vacuous` exists to refuse.
    """
    text = SOURCE.read_text(encoding="utf-8")
    start = text.index("## Before You Start")
    head = text.index("6. Identify all phases", start)
    tail = text.index("\n7. **Acquire the scope lock", head)
    block = text[head:tail]
    assert len(block) < 3_000, f"step-6 span escaped § Before You Start: {len(block)} chars"
    return block


def test_the_validation_first_ruling_is_present_and_keyed_on_existing_evidence() -> None:
    """Keyed on the EVIDENCE, never the genre: the first cut said "a backtest, a dogfood, a probe",
    and a dogfood cannot run before the build — it invokes the command the plan builds (the spec's
    own V2), as a live probe exercises the gate the plan builds (V3). Applied literally to its own
    motivating spec, the genre-keyed rule was impossible."""
    block = _step6()
    assert "against evidence that ALREADY EXISTS" in block
    assert "runs FIRST, before the FIRST ticket that" in block
    assert "wherever the Board scheduled it" in block
    # the exclusion is what makes the rule applicable rather than impossible
    # ⚠️ Pin the NEGATION, not the noun: "a live probe — can, and is not this rule" passed every
    # earlier assertion while re-admitting the exact defect round 1 confirmed (delta round, executed).
    flat = " ".join(block.split())
    assert "needs the built artifact — a dogfood, a live probe — cannot, and is not this rule" in flat
    # The keying itself, bolded and scoped — round 3 killed neither by dropping "or the PART of one"
    # nor by narrowing the rule to "In a hub-only plan".
    assert "⚠️ **A validation, or the PART of one, that tests" in block
    assert "re-cuts the spec before the implementing ticket runs" in " ".join(block.split())
    # The core directive is invertible in one word; "the BOARD's favour" passed all four tests.
    assert "resolve in the SPEC's favour" in block
    # Both numbers round 1 paid for, and the scope sentence, carried no grader at all.
    assert "24 of 101 lane-choice commits" in block
    assert "re-cut two clauses of the decision rule" in block
    assert "Most specs carry no such validation" in block
    # The applicability test and the traceability half were both invertible/droppable (round 3).
    assert "whether the recipe can run on" in flat
    assert "naming the re-order in the run record" in flat


def test_the_ruling_disposes_of_a_refuting_verdict_and_not_only_of_the_re_order() -> None:
    """Ordering a run and saying nothing about its verdict is the fail-open: the executor is left
    between "the validation refutes the rule" and "the plan says build it", and the autonomous
    contract resolves that by building anyway — the D-298 outcome with extra steps."""
    block = _step6()
    assert "REFUTES the rule" in block
    assert "stop threshold" in block
    # ⚠️ The exit is keyed on AUTHORISATION, never on blast radius, and `BLOCKED:` alone does not
    # pin that: the first cut halted on "a synced surface", which on this rule's OWN motivating plan
    # would stop an authorised ticket whose primary path IS a synced surface (delta round, executed).
    flat = " ".join(block.split())
    # ⚠️ Pin the ORDERED PAIR, never one half: "OWNED paths is authorised work you" matched both
    # polarities, so swapping inside↔outside inverted the ruling with all four tests green (round 3,
    # executed). The spec edit is unconditional; only the CONSEQUENT code edits are gated.
    assert "The spec edit is always yours" in block
    assert "inside the spine's `## File Scope` they are authorised work you do" in flat
    assert "outside it the `BLOCKED: unresolvable spec/scope contradiction` case" in flat
    # The ledger is not optional: "skip the D-row" passed every other pin (round 3, executed) and
    # would contradict the `decision-ledger` universal marker from inside a command that mandates it.
    assert "mint the D-row" in flat
    # The threshold is the SPEC's, never the executor's; and the no-op case stays a no-op.
    assert "the spec's own stop threshold" in flat
    assert "when yours has none, nothing is owed" in flat
    assert "sync discipline distributes it" in flat
    assert "Blast radius is not the test" in flat
    assert "never a finding" in block
    # The INVERSION control the precedent (tests/test_execute_plan_d7.py) carries and this family
    # kept dropping: a directive reworded from mandatory to discretionary passes every phrase pin.
    for hedge in ("should run FIRST", "when convenient", "at the orchestrator's discretion",
                  "where practical", "runs early", "may run"):
        assert hedge not in block, hedge


def test_the_ruling_does_not_collide_with_d7s_whole_plan_validation() -> None:
    """"Validation" names two things in this command — a spec's recipe and D7's adversarial pass,
    which `### D7` gates on every non-🔴 ticket being terminal. Without the disambiguation a reader
    reconciles them as one rule and re-schedules the spec's recipe to the end, which is the exact
    inversion this ruling forbids."""
    block = _step6()
    assert "D7's whole-plan validation" in block and "still runs last" in block


def test_the_pin_is_not_vacuous() -> None:
    """Every phrase above is absent from the rest of the command, so the block — not the file — is
    what these assertions read. A pin satisfied by text elsewhere pins nothing."""
    text = SOURCE.read_text(encoding="utf-8")
    block = _step6()
    assert 0 < len(block) < len(text)
    for phrase in ("against evidence that ALREADY EXISTS", "REFUTES the rule", "D7's whole-plan validation"):
        assert text.count(phrase) == 1, phrase
        assert phrase in block, phrase
