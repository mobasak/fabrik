"""/fabrik-spec feedback queue answered in one pass (D-735, D-760).

Each test pins one sentence in the section that owns it; the 1a wording is also run through the
convergence check's own pattern, so the recipe the command gives is one the check accepts.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "commands" / "_sources" / "fabrik-spec.md"
RESEARCHER = ROOT / "commands" / "_agents" / "fabrik-researcher.md"
sys.path.insert(0, str(ROOT / "scripts" / "enforcement"))

import check_spec_convergence  # noqa: E402


def _flat(path: Path) -> str:
    return re.sub(r"\s+", " ", path.read_text())


def _section(start: str, end: str) -> str:
    text = _flat(SRC)
    i = text.index(start)
    return text[i : text.index(end, i + len(start))]


def test_an_amendment_states_no_external_facts_in_words_the_check_reads() -> None:
    """Row 1789399457: the recipe sentence clears SILENT-1a; the 'no NEW external facts' wording does not."""
    s1a = _section("### 1a", "### 1b")
    m = re.search(r"`(This amendment adds no external facts beyond [^`]+)`", s1a)
    assert m, "1a gives no amendment recipe"
    assert check_spec_convergence.NO_EXTERNAL_RE.search(m.group(1))
    assert not check_spec_convergence.NO_EXTERNAL_RE.search("This amendment adds no new external facts.")


def test_a_best_practice_seat_carries_the_1a_facts() -> None:
    """Row 1791761722."""
    s1c = _section("### 1c", "## Phase 2")
    assert "A 1c (best-practice) seat is dispatched after the 1a facts it rests on are grounded or executed" in s1c


def test_self_review_grades_a_converged_copy_of_the_draft() -> None:
    """Row 1789139668: the script never grades a DRAFT, so the self-review grades a flipped copy."""
    p5 = _section("## Phase 5", "## Phase 6")
    assert "set the copy's Status line to `CONVERGED`" in p5
    assert "scripts/enforcement/check_spec_convergence.py <the copy>" in p5
    assert "a DRAFT is not graded" in p5


def test_researcher_quotes_schema_and_versions_from_a_raw_fetch() -> None:
    """Row 1791275601."""
    text = _flat(RESEARCHER)
    assert "a schema field, a parameter name or a version number is quoted from a raw fetch" in text
