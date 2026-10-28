"""/fabrik-ui-design feedback queue answered in one pass (D-735).

Each test pins one sentence in the section that owns it; the re-freeze WARN the command quotes is
produced by running check_frozen_chain on a re-frozen contract.
"""

import re
import subprocess
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


def test_the_uniqueness_recipe_counts_definitions_not_mentions(tmp_path: Path) -> None:
    """Row 1791028014: the Phase 6 recipe, run as written, flags a twice-defined id and not a cited one."""
    p6 = _section("## Phase 6", "## Phase 7")
    recipe = re.search(r"`(grep -oE '\^.*?uniq -d)`", p6).group(1).replace("<prefix>", "R-ui")
    cited = "## Rules\n- **R-ui-12**: one\n- **R-ui-13**: two\n\nScreen A enforces R-ui-12.\n"
    twice = cited + "- **R-ui-12**: again\n"

    def run(body: str) -> str:
        (tmp_path / "docs").mkdir(exist_ok=True)
        (tmp_path / "docs" / "ui-design.md").write_text(body)
        return subprocess.run(["bash", "-c", recipe], cwd=tmp_path, capture_output=True, text=True).stdout

    assert run(cited) == ""
    assert run(twice).split() == ["R-ui-12"]
    assert run("1. **R-ui-20**: one\n2. **R-ui-20**: again\n").split() == ["R-ui-20"]


def test_re_freeze_mode_skips_phase_seven_seeding_and_hand_off() -> None:
    p0 = _section("## Phase 0", "## Phase 1")
    assert "skips its one-time seeding and its planning hand-off" in p0
