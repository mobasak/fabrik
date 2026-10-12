"""/fabrik-execute-plan feedback queue answered in one pass (D-735): three wrong sentences and the recurring steps.

Each test pins one subject's sentence in the section that owns it; the trailer test executes the parser it describes.
"""

import importlib.util
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "commands" / "_sources" / "fabrik-execute-plan.md"


def _norm() -> str:
    return re.sub(r"\s+", " ", SRC.read_text())


def _section(start: str, end: str) -> str:
    text = _norm()
    i = text.index(start)
    return text[i : text.index(end, i + len(start))]


def test_a_merged_sibling_lock_is_visible_to_the_overlap_scan() -> None:
    """Row 1790897638: committed locks travel with a merged branch, so 'invisible' holds only until the merge."""
    text = _norm()
    assert (
        "A sibling AGENT's lock is invisible from here until this tree's branch contains the merge of its branch"
        in text
    )
    assert "A sibling AGENT's lock is invisible from here and that is safe" not in text


def test_the_baseline_gate_runs_in_check_mode() -> None:
    """Row 1790967489: a bare gate auto-fixes and re-stages, so the baseline must be read-only."""
    text = _norm()
    assert (
        "Record the starting gate state: `python scripts/final_gate.py --lean --check --json`"
        in text
    )


def test_the_review_artifact_binds_every_phase_not_only_gui() -> None:
    """Row 1791157267: the rule sat after 'Non-GUI phases skip this'; command_run.py refuses step for any phase."""
    text = _norm()
    assert "Non-GUI phases skip the screen steps above, never what follows." in text
    assert "Every phase's review exit — GUI or not — must EMIT AN ARTIFACT" in text
    assert "Non-GUI phases skip this. ⚠️ **That exit must EMIT AN ARTIFACT**" not in text


def test_a_resumed_run_names_receipts_with_the_plan_prefix() -> None:
    """Rows 1790974389, 1790767055: earlier phases pass `step` through the plan-prefix form, not a waiver."""
    assert (
        "which `step` reads from the record's `--surface` — so that run's `--surface` names the plan file"
        in _norm()
    )


def test_the_loop_names_the_profile_small_waiver_and_the_interpreter() -> None:
    """Rows 1790956193 and 1788820659, both in the Execution Loop block."""
    loop = _section("## Execution Loop", "## Dispatcher Mode")
    assert "under `Profile: small` add item 3b's `--review-waived`" in loop
    assert "under the repo's own interpreter, its `.venv` python where it has one" in loop
    assert "re-run step 9's path:line and symbol spot-check on this phase's cites" in loop


def test_the_preflight_repeats_before_each_phase() -> None:
    """Rows 1790392963, 1789580800, 1789247175: re-ground cites before each later phase, mechanism claims too."""
    text = _norm()
    assert (
        "Repeat the `path:line` and symbol spot-check before each later phase's first edit or dispatch"
        in text
    )
    assert "This is a **one-time upfront sanity gate**" not in text


def test_d4_wave_brief_points_at_the_catalogue_and_closes_in_order() -> None:
    """The CATALOGUE rows and 1790929913: the wave review's brief and receipt close."""
    d4 = _section("### D4 — Per-wave receive + review", "### D5 — Merge protocol")
    assert (
        "`/opt/fabrik/commands/_fragments/review-probe-catalogue.md` that match the change's SHAPE"
        in d4
    )
    assert (
        "passes `python3 scripts/enforcement/check_review_coverage.py <the receipt>` before its closing round is recorded"
        in d4
    )
    assert (
        "each wave receipt starts from `review_receipt.py --init` (the `## Coverage Checklist`"
        in d4
    )


def test_d5_compares_named_reds_and_d7_points_at_the_pause() -> None:
    """Rows 1789674993 (named reds) and 1789739684 (the pause beside the terminal states)."""
    assert (
        "on the tree before the merge and on the integrated tree, their reds compared BY NAME"
        in _section("### D5 — Merge protocol", "### D6")
    )
    assert "a NEW red → fixup routed to the **CONSUMER's coder**" in _section(
        "### D5 — Merge protocol", "### D6"
    )
    assert "**A quota pause is not a block** — D2's Quota-pause terminal owns it." in _section(
        "### D7 — Final validation", "## Subagent Strategy"
    )


def test_one_ticket_id_per_agent_task_line_is_what_the_parser_reads() -> None:
    """Row 1791056532: the table says one ID per line, and the parser indeed drops the second ID of a list."""
    assert "one ID per `Agent-Task:` line" in _norm()
    spec = importlib.util.spec_from_file_location(
        "check_plan_tickets", ROOT / "scripts" / "enforcement" / "check_plan_tickets.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod  # its dataclasses resolve their module through sys.modules
    spec.loader.exec_module(mod)
    assert mod.AGENT_TASK_RE.findall("Agent-Task: T04, T05\n") == ["T04"]
    assert mod.AGENT_TASK_RE.findall("Agent-Task: T04\nAgent-Task: T05\n") == ["T04", "T05"]


def test_ruff_format_only_touches_files_formatted_at_baseline() -> None:
    """Row 1791842869 (D-793): the second verdict on the held ruff-format subject, edited."""
    text = re.sub(r"\s+", " ", (ROOT / "commands" / "_sources" / "fabrik-execute-plan.md").read_text())
    assert "Run `ruff format` only on files this phase changed that `ruff format --check` passed at the phase's baseline — never wholesale on a sibling's lane, even a granted one" in text
