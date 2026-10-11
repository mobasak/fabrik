"""/fabrik-review-scoped feedback queue answered in one pass (D-735): the probe catalogue and the text fixes.

The catalogue collects the specific probes the queue's rows asked for; the command points at it by its hub path and
stays lean. Each test pins one subject's lines in the section that owns them.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "commands" / "_sources" / "fabrik-review-scoped.md"
CAT = ROOT / "commands" / "_fragments" / "review-probe-catalogue.md"


def _norm(path: Path) -> str:
    return re.sub(r"\s+", " ", path.read_text())


def _section(text: str, start: str, end: str | None) -> str:
    i = text.index(start)
    return text[i : text.index(end, i + len(start))] if end else text[i:]


def test_the_command_points_at_the_catalogue_before_the_first_pin() -> None:
    """Step 5 names the catalogue by its hub path, and the file exists in this tree."""
    assert "/opt/fabrik/commands/_fragments/review-probe-catalogue.md` that match the change's SHAPE" in _norm(SRC)
    assert CAT.exists()


def test_the_catalogue_sections_hold_their_probes() -> None:
    """One anchor line per section, so a section moved or dropped fails here."""
    cat = _norm(CAT)
    pin = _section(cat, "## Before the first pin", "## The brief's hunt lines")
    assert "Trace the entry path: the first caller that reaches the fixed function" in pin
    assert "One mutant per clause the edit states, written as a literal before/after" in pin
    hunt = _section(cat, "## The brief's hunt lines", "## Graders")
    assert "every caller of a changed exit code, output line or gated script" in hunt
    assert "who waits on a new lock and behind what" in hunt
    graders = _section(cat, "## Graders", "## Prose and docs fixes")
    assert "Grade the PROPERTY across every example, never one spelling" in graders
    assert "isolation is proven by a reversed-order run and by removing the fixture" in graders
    prose = _section(cat, "## Prose and docs fixes", "## Seat isolation")
    assert "re-read an inserted sentence with the one after it" in prose
    iso = _section(cat, "## Seat isolation", "## Loop bookkeeping")
    assert "A SEAT never runs `git worktree add` on the shared `.git`" in iso
    assert "never `resumeFromRunId`" in _section(cat, "## Loop bookkeeping", None)
    loop = _section(cat, "## Loop bookkeeping", None)
    assert "`confirmed` counts DEFECTS, never checks passed" in loop


def test_escape_variants_are_asked_from_round_one() -> None:
    """Row 1791496929: the ask sat under the closing reader only, so round 1 never attacked the guard."""
    assert "owes every round's readers — round 1's first — and that INDEPENDENT reader the guard or rule by NAME" in (
        _norm(SRC)
    )


def test_command_run_is_cited_by_symbol_not_line() -> None:
    """The line anchors into command_run.py had drifted (:556, :508, :593-595, :880, :2547-2554, :3116)."""
    text = _norm(SRC)
    assert not re.search(r"command_run\.py:\d", text)
    assert "`command_run.py::_trend_label`" in text
    assert "`command_run.py::AGENT_CLOSED_STATES`" in text
