"""/fabrik-ui-design feedback queue answered in one pass (D-735).

Each test pins one sentence in the section that owns it; the re-freeze WARN the command quotes is
produced by running check_frozen_chain on a re-frozen contract.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "commands" / "_sources" / "fabrik-ui-design.md"
sys.path.insert(0, str(ROOT / "scripts" / "enforcement"))

import check_frozen_chain  # noqa: E402


def _section(start: str, end: str) -> str:
    text = re.sub(r"\s+", " ", SRC.read_text())
    i = text.index(start)
    return text[i : text.index(end, i + len(start))]


def test_phase_zero_names_a_re_freeze_mode() -> None:
    """Row 1790918763: a single-screen re-freeze runs Phases 1-5 only over what it touches."""
    p0 = _section("## Phase 0", "## Phase 1")
    assert "**re-freeze** (a version bump on a FROZEN contract: Phases 1–5 run only" in p0


def test_the_size_ceiling_is_measured_by_a_whole_file_read() -> None:
    """Row 1791306147."""
    p1 = _section("## Phase 1", "## Phase 2")
    assert "exceeds maximum allowed tokens (25000)" in p1


def test_phase_six_checks_unique_ids_and_every_enum_value() -> None:
    """Rows 1791028014, 1791035742."""
    p6 = _section("## Phase 6", "## Phase 7")
    assert "| sort | uniq -d` prints nothing" in p6
    assert "states how the screen renders EVERY value the data contract lists for it" in p6


def test_re_freeze_close_out_sweeps_mirrors_and_names_the_review_gate() -> None:
    """Rows 1790725262, 1788970871, 1790981117, 1790963273."""
    close = _section("## Re-freeze close-out", "{{include:close-chain}}")
    assert "correct each mirror in the same version, before the closing pass" in close
    assert "name the control that now hosts each gate, consent or acknowledgement" in close
    assert "at `/fabrik-ui-design-review`'s design-approval gate" in close
    assert "the expected state after this run, not a regression" in close


def test_the_quoted_warn_is_what_the_check_prints_after_a_re_freeze(tmp_path: Path) -> None:
    """The close-out quotes this WARN; a contract re-frozen to v3 with a v2 attestation produces it."""
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "ui-design.md").write_text(
        "# UI design\n\n**Status:** FROZEN · **Version:** v3\n\nIndependently reviewed: v2\n\n## Screens\n"
    )
    findings = check_frozen_chain.check_chain(tmp_path)
    assert any(
        "newest independent review attests v2 but the contract is at v3" in f
        and "re-run the review twin or drop the claim" in f
        for f in findings
    ), findings
