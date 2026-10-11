"""/fabrik-task feedback queue answered in one pass (D-735) — each rule sits in the phase that owns it.

Rows answered: the /fabrik-task queue of 2026-10-11 (the commit's trailer lists every `ts`). Each test
pins one subject's rule inside the section a reader of that phase reads, so a rule moved to the wrong
phase or dropped fails here.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "commands" / "_sources" / "fabrik-task.md"
CRITIQUE = ROOT / "commands" / "_fragments" / "design-critique.md"


def _norm(path: Path) -> str:
    return re.sub(r"\s+", " ", path.read_text())


def _section(start: str, end: str) -> str:
    text = _norm(SRC)
    i = text.index(start)
    return text[i : text.index(end, i + len(start))]


def test_size_checks_each_declared_path_before_declaring_it() -> None:
    """Rows 1790966184, 1791467990: a typo'd declared path is accepted silently as a grader."""
    assert "`ls` and grep every other path for the rule first, since a typo reads as that grader" in _section(
        "## SIZE", "## Phase 1"
    )


def test_measure_executes_the_real_path() -> None:
    """S2 (population): the population is measured by executing the real path, never a proxy."""
    assert (
        "each by EXECUTING the real path on real data (the producer's code, the tool's run output per mode, "
        "the design's own classifier, the writer of each state value it trusts), never a source read or a proxy"
    ) in _section("## Phase 1", "## Phase 2")


def test_the_lane_critique_brief_asks_seats_to_execute() -> None:
    """S3 (critique brief): replay the incident, run claims against the real tool, pin the tree."""
    phase2 = _section("## Phase 2", "## Phase 3")
    assert "This lane's brief also has each seat EXECUTE: replay the reported incident through the design" in phase2
    assert "pins the tree (a commit or `git archive` copy), bars live-provider credentials" in phase2


def test_the_pre_record_checklist_sits_before_the_record_call() -> None:
    """S4 (design order): the refusal shapes and the one-shot rule precede the `step --design` call."""
    phase2 = _section("## Phase 2", "## Phase 3")
    checklist = phase2.index("`--design` lands ONCE. Record them:")
    assert checklist < phase2.index("step --phase 2 --title")


def test_mirror_searches_the_whole_tree_and_names_fail_direction() -> None:
    """S1 (readers) and the fail-direction rows: where the search runs, and which error is dangerous."""
    phase2 = _section("## Phase 2", "## Phase 3")
    assert "The search is the whole tracked tree (tests and their pinned strings, `commands/`, UI, docs)" in phase2
    assert "names its fail direction — which error is dangerous, an answer versus an outage" in phase2


def test_v1_commits_once_with_the_ledgers_and_graders_execute() -> None:
    """Row 1790689315 (v1's one commit vs phase 5's ledger commit) and S6 (graders)."""
    phase3 = _section("## Phase 3", "## Phase 4")
    assert "At v1 that one commit also carries phase 5's ledgers, so nothing is committed before phase 5" in phase3
    assert "every guard and threshold edge the change adds is mutated" in phase3


def test_the_third_review_question_excludes_an_equivalent_implementation() -> None:
    """Row 1790692304: any nameable equivalent implementation read as an UPGRADE verdict."""
    phase4 = _section("## Phase 4", "## Phase 5")
    assert "a second approach whose merits the build cannot settle (an equivalent implementation is not one)" in phase4
    assert "the declaration said did not exist" not in phase4


def test_the_receipt_range_tip_is_the_last_commit() -> None:
    """S5 (receipt close): task_lane.py check (d) refuses unless the range tip is the LAST --commit."""
    close = _section("## Phase 5", "## UPGRADE")
    assert "Its range tip must be the LAST `--commit` (`task_lane.py` check (d))" in close
    assert "never captured or passed to `--commit`" in close


def test_critique_is_not_rerun_on_the_folded_version() -> None:
    """Row 1791070230: 'once per artifact version' read as re-critiquing every folded design.md."""
    text = _norm(CRITIQUE)
    assert "nor is the version folding its ACCEPTED concerns" in text
    assert "once per artifact version" not in text
