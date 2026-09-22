"""The `/fabrik-command-improve` DRIVE contract — who runs it, on what model, sized how.

Operator ruling 2026-09-20: the command was precise about its mechanics and silent on how it is
driven (11 of 17 aims absent). The rules point at existing machinery; this grader keeps them in
the source so a later "lean" edit cannot silently drop the caller restriction, the Fable-else-Opus
rule or the box-sized seat rule.
"""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "commands" / "_sources" / "fabrik-command-improve.md"


def _drive_section() -> str:
    text = SRC.read_text(encoding="utf-8")
    start = text.index("## Drive")
    end = text.index("\n## ", start + 1)
    # WRAP-AWARE: a needle that spans a soft line break must still match (a line grep cannot
    # see a wrapped claim — the first cut of this grader read "no\n  corpus" as absent).
    return " ".join(text[start:end].split())


def test_the_source_states_who_may_run_it() -> None:
    sec = _drive_section()
    assert "`CLAUDE_AGENT` is `infra` or `intel`" in sec
    assert "does not run it" in sec


def test_the_source_states_fable_drives_else_opus() -> None:
    sec = _drive_section()
    assert "on Fable" in sec and "driven on Opus" in sec
    # the TRIGGER is locked, not only the phrases: a mutant that loosened "when" survived round 1
    assert "bands RED and the window it names is Fable" in sec
    assert "this account's own Fable window" in sec and "/model claude-fable-5-1" in sec
    assert (
        "D-295" in sec
    )  # the band is raised to the account's own Fable reading; no flip reaches it


def test_the_source_sizes_seats_from_the_box_by_role() -> None:
    sec = _drive_section()
    assert "dispatch_headroom.py" in sec
    assert "haiku 1× · sonnet 2× · opus 5× · fable 10×" in sec
    assert "not restated here" in sec  # the dispatch shape is pointed at, never copied (round-1 C1)
    assert (
        "still RUNNING" in sec
    )  # the subtraction is dispatch_headroom.py's, over running records only
    assert "never below the floor" in sec  # the sibling subtraction never starves a session


def test_the_source_bounds_the_passes_with_the_real_d278_remedy() -> None:
    sec = _drive_section()
    # D-335 superseded D-229's delta sizing (chunk 1, f6beb8b88 re-cut this section) — the pin
    # kept the old id and read red at HEAD for a day; the stop's remedy (D-278) is unchanged
    assert "D-335" in sec and "D-278" in sec
    assert (
        "`--confirmed`/`--own-fix` pair" in sec
    )  # the stop reads the PAIR; --own-fix alone is silence
    assert "fix every confirmed defect still open" in sec
    assert "re-verify that fixed set alone" in sec  # the remainder rounds TERMINATE
    assert "backlog row with a named destination" in sec
    assert "no corpus rule names a clock" in sec  # the 3-minute timer stays out (round-1 F2)


def test_the_source_grounds_against_fabrik_lib_and_the_ledgers_before_drafting() -> None:
    sec = _drive_section()
    for needle in (
        "/opt/fabrik-lib/README.md",
        "docs/STRATEGIC_BACKLOG.md",
        "select_rules.py --changed",
        "EXECUTED before the render",
    ):
        assert needle in sec, needle


def test_the_source_sets_a_time_budget_from_measured_closes() -> None:
    sec = _drive_section()
    assert "Budget one run at 40 minutes" in sec
    assert "median 34" in sec and "max 54" in sec and "5 of the 16 past 40" in sec
