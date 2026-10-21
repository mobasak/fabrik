"""W-a7cff030: a plan's Status read skips a `Status:` line that sits inside a multi-line inline code span.

The W-8f9a7d2c construct: an example span that wraps onto a line reading `**Status:** DRAFT` came before the plan's real
Status, and first-match read the example. Each reader fails a different way (Lesson 103):
- check_plan_quality._sibling_spine_is_draft fails OPEN: a quoted DRAFT downgrades the ticket checks;
- check_convergence's archived-plan reads fail CLOSED: a false "archived while DRAFT".
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ENF = ROOT / "scripts" / "enforcement"
if str(ENF) not in sys.path:
    sys.path.insert(0, str(ENF))


def _load(name: str):
    spec = importlib.util.spec_from_file_location(f"_span_{name}", ENF / f"{name}.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


QUALITY = _load("check_plan_quality")
CONVERGENCE = _load("check_convergence")

SPAN_THEN_REAL = (
    "# Plan\n\n"
    "An example of the old header, quoted: `the line\n"
    "**Status:** DRAFT\n"
    "ended here` in prose.\n\n"
    "**Status:** {real}\n"
)


def test_a_spine_status_inside_a_code_span_does_not_mark_the_set_draft(tmp_path: Path) -> None:
    plan_set = tmp_path / "2026-10-21-plan-9-x"
    plan_set.mkdir()
    (plan_set / "2026-10-21-plan-9-x.md").write_text(
        SPAN_THEN_REAL.format(real="CONVERGED"), encoding="utf-8"
    )
    ticket = plan_set / "T01-a.md"
    ticket.write_text("# T01\n", encoding="utf-8")
    assert QUALITY._sibling_spine_is_draft(ticket) is False


def test_a_real_draft_spine_still_reads_draft(tmp_path: Path) -> None:
    plan_set = tmp_path / "2026-10-21-plan-9-y"
    plan_set.mkdir()
    (plan_set / "2026-10-21-plan-9-y.md").write_text(
        "# Plan\n\n**Status:** DRAFT\n", encoding="utf-8"
    )
    ticket = plan_set / "T01-a.md"
    ticket.write_text("# T01\n", encoding="utf-8")
    assert QUALITY._sibling_spine_is_draft(ticket) is True


def test_an_archived_plan_status_skips_a_code_span() -> None:
    assert CONVERGENCE._archived_plan_status(SPAN_THEN_REAL.format(real="EXECUTED")) == "EXECUTED"


def test_an_archived_plan_status_still_reads_a_real_draft() -> None:
    assert CONVERGENCE._archived_plan_status("# Plan\n\n**Status:** DRAFT\n") == "DRAFT"


def test_both_archived_plan_reads_go_through_the_one_helper() -> None:
    src = (ENF / "check_convergence.py").read_text(encoding="utf-8")
    # the bare name only: _REVIEW_STATUS_LINE and ANY_STATUS_LINE are other patterns
    assert len(re.findall(r"(?<![A-Z_])_STATUS_LINE\.search\(", src)) == 1, (
        "a second direct read bypasses the code-span blank"
    )
