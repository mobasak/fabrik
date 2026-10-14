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
