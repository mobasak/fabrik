"""/fabrik-doc-converge feedback queue answered in one pass (D-735): the contract table's own denominators.

Each test pins one row's sentence; the guardrail test proves the RESILIENCE row no longer counts from the doc itself.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "commands" / "_sources" / "fabrik-doc-converge.md"


def _norm() -> str:
    return re.sub(r"\s+", " ", SRC.read_text())


def test_resilience_billable_set_comes_from_the_code() -> None:
    """Row 1789552091: the row took §2's own list as the denominator, which the guardrail forbids."""
    text = _norm()
    assert "every external API in §2 with a billable balance" not in text
    assert "every external API the CODE calls with a billable balance" in text
    assert "Trust the doc as its own inventory" in text  # the guardrail the old row broke


def test_readme_capability_claims_are_checked_against_code() -> None:
    """Row 1789562683: a claim wrong in both README and FEATURES passed a maps-to-a-FEATURES-row check."""
    text = _norm()
    assert (
        "every capability claim is verified against the code, with FEATURES as a cross-check"
        in text
    )
    assert "every capability claim maps to a FEATURES row" not in text


def test_every_docs_level_index_obeys_the_index_row() -> None:
    """Row 1789561977: docs/INDEX.md had no row, and two indexes disagreed."""
    assert (
        "any other docs-level index (`docs/INDEX.md`) obeys the same rule and agrees with this one"
        in _norm()
    )


def test_a_code_defect_found_mid_converge_is_filed_and_described_as_is() -> None:
    """Rows 1791209085, 1789490218: file it to its owner; the doc states today's behaviour with the filed id."""
    p2 = _norm()[_norm().index("## Phase 2") : _norm().index("## Phase 3")]
    assert (
        "a CODE defect the converge uncovers is filed to its owner, never patched inside a doc converge"
        in p2
    )


def test_index_row_reads_untracked_files_as_present() -> None:
    """Row 1789558823: `git ls-files` alone flagged an untracked-but-present file as a deleted path."""
    assert "a file on disk but untracked is present, not deleted" in _norm()
