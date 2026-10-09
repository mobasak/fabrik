"""/fabrik-data-contract queue — the recurring pass-ledger-placement subject (D-711: a recurrence is edited).

Fleet practice (trade-intelligence, tryton-crm, transdoc): a contract that carries a Pass Ledger section gains one
dated version entry per re-freeze, after the closing round. Each test asserts its sentence inside the paragraph
that owns it.
"""

from __future__ import annotations

from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "commands" / "_sources" / "fabrik-data-contract.md"


def _norm(p: Path) -> str:
    return " ".join(p.read_text(encoding="utf-8").split())


def _between(text: str, start: str, end: str) -> str:
    i = text.index(start)
    return text[i : text.index(end, i)]


def test_phase_3_names_the_ledger_home_and_when_the_version_entry_is_written() -> None:
    """Rows 1791138316 and 1791065143: a report-only contract and the not-yet-written version entry."""
    phase3 = _between(_norm(SRC), "## Phase 3 — Converge", "1. **Coverage**")
    assert (
        "The Pass Ledger lives in the contract's Pass Ledger section when it carries one, else in the closing report; "
        "a re-freeze adds its own dated version entry there after that closing round, so its absence is never a "
        "finding in any round of the run."
    ) in phase3


def test_the_version_entry_is_an_exempt_post_convergence_write_and_phase_2_keeps_the_section() -> (
    None
):
    """The entry changes the contract's md5 after the closing round, so Phase 4 and the Guardrails exempt it; Phase
    2's 'exactly the shape of the seeded template' must not strip an existing ledger section."""
    t = _norm(SRC)
    phase4 = _between(t, "## Phase 4", "## Phase 5")
    assert (
        "This status/header write — and the version's Pass Ledger entry (Phase 3) — is a post-convergence action, "
        "exempt from the no-op rule"
    ) in phase4
    assert (
        "(The Phase-4 `Status → FROZEN` header flip and the version's Pass Ledger entry are the exempt "
        "post-convergence writes, not reconciliation edits"
    ) in t
    phase2 = _between(t, "## Phase 2", "## Phase 3")
    assert (
        "which **is the canonical shape** (plus an existing Pass Ledger section, which is kept — Phase 3)."
    ) in phase2
