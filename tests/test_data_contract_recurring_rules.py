"""/fabrik-data-contract queue — the recurring pass-ledger-placement subject (D-711: a recurrence is edited).

Each test asserts the sentence inside the paragraph that owns it, through its delimiter.
"""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _norm(p: Path) -> str:
    return " ".join(p.read_text(encoding="utf-8").split())


def _between(text: str, start: str, end: str) -> str:
    i = text.index(start)
    return text[i : text.index(end, i)]


def test_phase_3_names_the_ledger_home_and_when_the_version_entry_is_written() -> None:
    """Rows 1791138316 and 1791065143: a report-only contract and the not-yet-written version entry."""
    phase3 = _between(
        _norm(REPO / "commands" / "_sources" / "fabrik-data-contract.md"),
        "## Phase 3 — Converge",
        "1. **Coverage**",
    )
    assert (
        "The Pass Ledger lives in the run report unless the contract already carries one (a re-freeze never adds "
        "that section), and the entry for the version being frozen is written after that closing round, so its "
        "absence is never a round-1 finding."
    ) in phase3


def test_term_edit_names_which_pass_ledger_keeps_the_numbering() -> None:
    """The fragment read the ledger as the artifact's only; the default home is the report."""
    t = _norm(REPO / "commands" / "_fragments" / "term-edit.md")
    assert (
        "the Pass Ledger keeps the true numbering — the report's, or the artifact's where it already carries one);"
    ) in t
    assert "the artifact's Pass Ledger keeps the true numbering" not in t
