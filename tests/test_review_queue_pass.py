"""/fabrik-review feedback queue answered in one pass (D-735): the catalogue pointer and the text fixes.

Each test pins one subject's sentence in the section that owns it, so a section moved or a fix reverted fails here.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "commands" / "_sources" / "fabrik-review.md"
CAT = ROOT / "commands" / "_fragments" / "review-probe-catalogue.md"


def _norm(path: Path) -> str:
    return re.sub(r"\s+", " ", path.read_text())


def _section(text: str, start: str, end: str) -> str:
    i = text.index(start)
    return text[i : text.index(end, i + len(start))]


def test_phase_one_points_at_the_probe_catalogue() -> None:
    """The catalogue's rows were asked of /fabrik-review too; Phase 1 names it by its hub path."""
    p1 = _section(_norm(SRC), "## Phase 1 — Independent finders", "**Run the review-hygiene check")
    assert "`/opt/fabrik/commands/_fragments/review-probe-catalogue.md` that match the change's SHAPE" in p1
    assert CAT.exists()


def test_agent_tool_shape_covers_a_review_the_operator_did_not_invoke() -> None:
    """Row 1791755835: Workflow runs only on the operator's opt-in, so a hook- or caller-started review uses Agent."""
    assert "or the operator did not invoke this review (the tool runs only on their explicit opt-in)" in _norm(SRC)


def test_a_failed_refuters_candidates_are_executed_by_the_lead() -> None:
    """Rows 1791418194, 1791410409: a NO RESULT refuter is never a re-dispatch of the whole pass."""
    p2 = _section(_norm(SRC), "## Phase 2 — EXECUTE", "## Phase 3")
    assert "every candidate of a slice whose refuter failed or read `NO RESULT`" in p2
    assert "never a re-dispatch of the pass" in p2


def test_the_delta_brief_names_its_must_read_files() -> None:
    """Rows 1791506864, 1791478572: the fix diff's files and the previous pass's gap files, by path."""
    p4 = _section(_norm(SRC), "## Phase 4 — Converge", "## Behavior Contract")
    assert "The brief lists that file set by path as must-read, with every file the previous pass left as a `gap`." in p4


def test_closing_ledger_after_a_quiet_round_one() -> None:
    """Rows 1791490105, 1791493834: `next --ids` needs ids a quiet round 1 never raised; the ledger is omitted."""
    p4 = _section(_norm(SRC), "## Phase 4 — Converge", "## Behavior Contract")
    assert "its printed rows go in `args` as-is, never a file path" in p4
    assert "after a quiet round 1 there are no ids: omit `ledger`" in p4
    js = (ROOT / ".claude" / "workflows" / "fabrik-review-loop.js").read_text()
    assert "const ledger = slice.ledger && slice.ledger.length" in js  # an empty ledger takes the pass-1 head


def test_close_order_stages_before_the_in_progress_gate() -> None:
    """Row 1791508831: the gate's ruff leg lints staged changes only, so an unstaged fix is linted by nothing."""
    assert "Close in this ORDER: stage your own files (the gate's ruff leg lints only staged changes" in _norm(SRC)


def test_catalogue_holds_the_two_recurring_probes() -> None:
    """Rows 1791336906/1791400423 (redactor timing) and 1790358705/1790361809 (what a fix leaves unchanged)."""
    cat = _norm(CAT)
    assert "a regex redactor is also timed on a 100k-character input and probed at its truncation edges" in _section(
        cat, "## The brief's hunt lines", "## Graders"
    )
    assert "a fix recipe handed to a coder names one input it must leave unchanged and the test that holds it" in (
        _section(cat, "## Graders", "## Prose and docs fixes")
    )
