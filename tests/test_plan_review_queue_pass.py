"""/fabrik-plan-review feedback queue answered in one pass (D-735): the panel's ACCEPTED delta round, recorded.

The rule lives in the shared design-critique fragment; the advisory it calls expected is executed against command_run.
"""

import importlib.util
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRAG = ROOT / "commands" / "_fragments" / "design-critique.md"


def _accepted_clause() -> str:
    text = re.sub(r"\s+", " ", FRAG.read_text())
    start = text.index("in spec-review and plan-review it re-opens the loop")
    return text[start : text.index("in `/fabrik-task`", start)]


def test_the_accepted_delta_round_is_recorded_and_its_advisory_expected() -> None:
    """Row 1791770042 (and spec-review's 1791303387): the delta is the next Pass, slices restated, advisory expected."""
    clause = _accepted_clause()
    assert (
        "recorded as the next Pass with every slice an earlier round stated re-stated in `--slices`"
        in clause
    )
    assert (
        "an OSCILLATING advisory naming that round's count after an earlier 0 is expected there, not drift"
        in clause
    )


def test_the_advisory_the_clause_expects_is_what_command_run_prints() -> None:
    """A quiet round then a panel delta confirming k: from round 5 the advisory on that round names `0 → k`."""
    spec = importlib.util.spec_from_file_location(
        "command_run", ROOT / "scripts" / "command_run.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    warning = mod.convergence_warning([5, 3, 1, 0, 4])
    assert "OSCILLATING" in warning and "0 → 4" in warning
    assert (
        mod.convergence_warning([3, 0, 4]) == ""
    )  # below the heuristic's minimum rounds it stays silent


def test_the_opus_floor_and_the_half_blocked_split_are_stated() -> None:
    """Mail 01M3VSFP9D (fabrik-lib): D-344's 'no Opus finder' hid execute-plan's floor; a half-blocked plan had no split rule."""
    core = " ".join((ROOT / "commands" / "_fragments" / "subagents-core.md").read_text().split())
    assert (
        "`/fabrik-execute-plan`'s per-round Opus finder floor, once at D7 under `Profile: small`, is its own rule and still stands"
        in core
    )
    plan = " ".join((ROOT / "commands" / "_sources" / "fabrik-plan-review.md").read_text().split())
    assert (
        "SPLIT the plan: the phases BEFORE the first blocked one keep the plan's name, converge and execute; that phase and every later one move to a new `DRAFT` plan"
        in plan
    )
    review = " ".join((ROOT / "commands" / "_sources" / "fabrik-review.md").read_text().split())
    assert "a run `/fabrik-execute-plan` dispatches still seats its per-round Opus floor" in review


def test_a_seat_never_executes_a_script_that_acts_outside_its_scratch() -> None:
    """Row 1791938982 (fleet, 2026-10-14): four plan-review seats executed scripts/proof_run.py because the brief said
    to confirm what a sentence described, and destroyed a live fixture. The rule rides in both texts a seat can load:
    the seat-isolation paragraph of subagents-core and the native reviewer's house rules, whose verdict for such a
    claim is `unverified`."""
    core = " ".join((ROOT / "commands" / "_fragments" / "subagents-core.md").read_text().split())
    assert (
        "A seat reads a script before it EXECUTES it, its `--help` included, and never executes one that deletes,"
        " deploys, provisions, writes outside its scratch dir or contacts a non-local host, whatever binary does it,"
        " even when its brief asks it to confirm what that script does: it cites the lines and returns that claim"
        " `unverified` (read-only by rule)" in core
    )
    agent = " ".join((ROOT / "commands" / "_agents" / "fabrik-reviewer.md").read_text().split())
    assert (
        "read a script before you execute it, its `--help` included, and never execute one that deletes, deploys,"
        " provisions, writes outside your scratch dir or contacts a non-local host, whatever binary does it, even"
        " when a check asks you to: cite the lines and return that claim `unverified` (read-only by rule);"
        in agent
    )


def test_the_ledger_home_names_what_the_gate_grades_in_plan_and_receipt() -> None:
    """Row 1792013533 (kaizen, 2026-10-15, the one-door monolith loop): the command said the Pass Ledger lives in the
    review receipt, and the lead learnt by precedent (the venv plan) that the PLAN must carry its own ledger too —
    `check_convergence._check_plan` grades the plan text's `method: re-derivation` Pass row for every plan (:710) and
    its last `confirmed: 0` row for a monolith (:717-722; `_check_spine_set` grades a spine's, :464), and never opens
    the receipt; the receipt is graded by its own
    ledger only when its header `Command:` label names this command AND it carries no live `## Coverage Checklist`
    heading (`_is_design_receipt`, :1310) — which the `review_receipt.py --init` skeleton emits (:247), so a receipt
    built from it is read as a code review and owes the gate embed. The sentence now states both homes (ledger and Residual), which function grades which row for a spine and a
    monolith, and both receipt conditions. Mutants, each a failing assertion: restore 'lives in the review receipt' (the receipt-only claim);
    drop 'a spine's or a monolith's'; drop the `_check_plan` row grammar; drop the Coverage Checklist condition; drop
    the skeleton clause; move the sentence out of Phase 1."""
    src = ROOT / "commands" / "_sources" / "fabrik-plan-review.md"
    text = " ".join(src.read_text().split())
    phase1 = text[text.index("## Phase 1 — Grounding passes") : text.index("## Phase 2 — Make every step executable")]
    sentence = (
        "The plan and its review receipt both carry the Pass Ledger and its Residual. At the flip `check_convergence.py` grades the PLAN's own rows, a spine's or a monolith's — a `method: re-derivation` Pass row (`_check_plan`) and a last counter row reading `confirmed: 0` (`_check_plan` for a monolith, `_check_spine_set` for a spine) — beside the plan's adjudicated Coverage Checklist (step 2). The review receipt, `docs/development/reviews/<YYYY-MM-DD>-<slug>-plan-review.md`, whose first 10 lines carry the line `**Command:** /fabrik-plan-review`, carries the same ledger plus the panel table and the ask↔spec table: once it claims a finished review, the gate grades it by its ledger only under that label and with no `## Coverage Checklist` heading of its own (`_is_design_receipt`), and demands a code review's gate embed otherwise — `review_receipt.py --init` writes receipts for the two code-review commands only and always emits that heading."
    )
    assert phase1.count(sentence) == 1, "the ledger-home sentence is stated once, in Phase 1"
    assert "Pass Ledger lives in the review receipt" not in text, "the receipt-only claim is gone"
    # the two homes are named exactly once each in Phase 1 — a second statement is a restatement that drifts
    assert phase1.count("The plan and its review receipt both carry the Pass Ledger") == 1
    lowered = text.lower()
    for restatement in (
        "lives only in the review receipt",
        "receipt holds only",
        "only in the receipt",
        "lives only in the plan",
        "only in the plan",
    ):
        assert restatement not in lowered, restatement
    assert phase1.count("`_is_design_receipt`") == 1


def test_round_zero_scripts_step_references_and_mutant_predictions() -> None:
    """Row 1792092814, the sixth verdict answered from rule (1) as already stated: three of six rounds found a step
    reference, a count or a mutant prediction the lead's own fix added, unexecuted. Rule (1) now names the two kinds
    it left out, in both homes of the round-zero rule (term-edit for text loops, term-coverage for code loops)."""
    clause = (
        "AND every count, enumeration, line anchor, step reference, mutant prediction (a mutant its grader is said to"
        " kill) or negative, is executed at round 1, or before the pin that first carries it,"
    )
    # row 1792194120: an advisory count the plan quotes is re-run when a fix changes what it counts, not only its text
    rerun = (
        "re-run and re-cited when the claim or what it measures changes (a fix that changes what a quoted advisory"
        " counts, such as a plan's Touches)"
    )
    for name in ("term-edit.md", "term-coverage.md"):
        text = re.sub(r"\s+", " ", (ROOT / "commands" / "_fragments" / name).read_text())
        assert clause in text, name
        assert rerun in text, name
