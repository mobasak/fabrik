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
    return text[start:end]


def test_the_source_states_who_may_run_it() -> None:
    sec = _drive_section()
    assert "`CLAUDE_AGENT` is `infra` or `intel`" in sec
    assert "does not run it" in sec


def test_the_source_states_fable_drives_else_opus() -> None:
    sec = _drive_section()
    assert "on Fable" in sec and "driven on Opus" in sec
    assert "D-295" in sec  # Fable's window is its own reading; no flip reaches it


def test_the_source_sizes_seats_from_the_box_by_role() -> None:
    sec = _drive_section()
    assert "dispatch_headroom.py" in sec
    assert "haiku 1× · sonnet 2× · opus 5× · fable 10×" in sec
    assert "D-229" in sec and "D-278" in sec  # bounded passes, the scope-growth stop


def test_the_source_grounds_against_fabrik_lib_and_the_ledgers_before_drafting() -> None:
    sec = _drive_section()
    for needle in ("/opt/fabrik-lib/README.md", "docs/STRATEGIC_BACKLOG.md", "select_rules.py --changed", "EXECUTED before the render"):
        assert needle in sec, needle


def test_the_source_sets_a_time_budget_from_measured_closes() -> None:
    assert "under 40 minutes" in _drive_section()
