"""/fabrik-doc-converge feedback queue answered in one pass (D-735): the contract table's own denominators.

Each test pins one row's clause in the table line that owns it, so a reverted or moved clause fails here.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "commands" / "_sources" / "fabrik-doc-converge.md"


def _norm() -> str:
    return re.sub(r"\s+", " ", SRC.read_text())


def _row(doc: str) -> str:
    return next(ln for ln in SRC.read_text().splitlines() if ln.startswith(f"| `{doc}`"))


def test_resilience_billable_set_comes_from_the_code() -> None:
    """Row 1789552091: the row took §2's own list as the denominator, which the guardrail forbids."""
    row = _row("docs/RESILIENCE.md")
    assert "every external API the CODE calls with a billable balance" in row
    assert "never §2's own cost column" in row
    # the ground-truth column carries the denominator the clause counts from
    assert (
        "every external call-site in code with its per-call price, balance endpoint or quota constant"
        in row
    )


def test_readme_capability_claims_are_checked_against_code() -> None:
    """Row 1789562683: a claim wrong in both README and FEATURES passed a maps-to-a-FEATURES-row check."""
    row = _row("README.md")
    assert (
        "every capability claim is verified against the code, with FEATURES as a cross-check" in row
    )
    assert "every capability claim maps to a FEATURES row" not in _norm()


def test_every_docs_level_index_obeys_the_index_row() -> None:
    """Row 1789561977: docs/INDEX.md had no row, and two indexes disagreed."""
    row = _row("docs/README.md")
    assert row.startswith("| `docs/README.md` · `docs/INDEX.md` |")
    assert "each docs-level index obeys this rule and the two agree" in row


def test_index_row_reads_untracked_files_as_present() -> None:
    """Row 1789558823: `git ls-files` alone flagged an untracked-but-present file as a deleted path."""
    row = _row("INDEX.md")
    assert "a file on disk but untracked is present, not deleted" in row
    assert "a bare filename in a directory's row resolves under that directory" in row


def test_a_code_defect_found_mid_converge_is_filed_and_described_as_is() -> None:
    """Rows 1791209085, 1789490218: file it to its owner; the doc states today's behaviour with the filed id."""
    p2 = _norm()[_norm().index("## Phase 2") : _norm().index("## Phase 3")]
    assert "a CODE defect the converge uncovers is filed to its owner" in p2
    assert (
        "never patched inside a doc converge; the doc states what the code does today and names the filed id"
        in p2
    )
