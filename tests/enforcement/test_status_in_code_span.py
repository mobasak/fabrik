"""W-a7cff030: plan Status reads reject a `Status:` line hidden in an inline code span, and never lose a real one.

The W-8f9a7d2c construct: an example span that wraps onto a line reading `**Status:** DRAFT` came before the plan's
real Status, and first-match read the example. Each reader fails a different way (Lesson 103):
- check_plan_quality._sibling_spine_is_draft and the two severity reads fail OPEN: a quoted DRAFT downgrades checks.
- check_convergence's archived-plan reads fail CLOSED: a false "archived while DRAFT".

The Opus + Fable panel ruled (both seats C): match on the ORIGINAL text, treat a span-hidden candidate as rejected, and
when only hidden candidates exist take the reader's strict branch. Round 1 of the review found the blank-then-match
draft wrong in three ways (C1 a stray backtick erased a real line, C2 a value tail crossed lines, C3 a span-led line
matched); each is a case below.
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
STRAY_TICK = "# P\n\nRun the `fabrik tool now\n**Status:** {real}\nlater `x` y\n"  # C1
ONLY_SPANNED = "# P\n\nquoted: `a\n**Status:** {value}\nb` end\n"


def _spine(tmp_path: Path, text: str) -> Path:
    plan_set = tmp_path / "2026-10-21-plan-9-x"
    plan_set.mkdir()
    (plan_set / "2026-10-21-plan-9-x.md").write_text(text, encoding="utf-8")
    ticket = plan_set / "T01-a.md"
    ticket.write_text("# T01\n", encoding="utf-8")
    return ticket


# --- the original defect -------------------------------------------------------------------------------------------


def test_a_spine_status_inside_a_code_span_does_not_mark_the_set_draft(tmp_path: Path) -> None:
    assert (
        QUALITY._sibling_spine_is_draft(_spine(tmp_path, SPAN_THEN_REAL.format(real="CONVERGED")))
        is False
    )


def test_an_archived_plan_status_skips_a_code_span() -> None:
    assert CONVERGENCE._archived_plan_status(SPAN_THEN_REAL.format(real="EXECUTED")) == "EXECUTED"


# --- real headers still read ---------------------------------------------------------------------------------------


def test_a_real_draft_spine_still_reads_draft(tmp_path: Path) -> None:
    assert (
        QUALITY._sibling_spine_is_draft(_spine(tmp_path, "# Plan\n\n**Status:** DRAFT\n")) is True
    )


def test_an_absent_spine_status_still_reads_draft(tmp_path: Path) -> None:
    assert QUALITY._sibling_spine_is_draft(_spine(tmp_path, "# Plan\n\nno header yet\n")) is True


def test_an_archived_plan_status_still_reads_a_real_draft() -> None:
    assert CONVERGENCE._archived_plan_status("# Plan\n\n**Status:** DRAFT\n") == "DRAFT"


# --- C1: a stray backtick never erases a real Status line ----------------------------------------------------------


def test_a_stray_backtick_does_not_hide_a_real_spine_status(tmp_path: Path) -> None:
    assert (
        QUALITY._sibling_spine_is_draft(_spine(tmp_path, STRAY_TICK.format(real="EXECUTED")))
        is False
    )


def test_a_stray_backtick_does_not_hide_a_real_archived_status() -> None:
    assert CONVERGENCE._archived_plan_status(STRAY_TICK.format(real="DRAFT")) == "DRAFT"


# --- C2: a backticked value never reads the next line --------------------------------------------------------------


def test_a_backticked_value_does_not_read_the_next_line() -> None:
    assert CONVERGENCE._archived_plan_status("# P\n**Status:** `EXECUTED`\n\nOpen\n") is None


# --- C3: a line that starts with a span is not a Status line -------------------------------------------------------


def test_a_span_led_line_is_not_a_status_line() -> None:
    text = "# P\n\n`plan.md` Status: DRAFT drives this\n\n**Status:** EXECUTED\n"
    assert CONVERGENCE._archived_plan_status(text) == "EXECUTED"


# --- the strict branch when only spanned candidates exist ----------------------------------------------------------


def test_a_spine_with_only_a_spanned_status_takes_the_strict_branch(tmp_path: Path) -> None:
    # fails OPEN otherwise: the strict branch is "not draft", so the ticket checks keep ERROR
    assert (
        QUALITY._sibling_spine_is_draft(_spine(tmp_path, ONLY_SPANNED.format(value="DRAFT")))
        is False
    )


def test_an_archived_plan_with_only_a_spanned_midflight_status_is_flagged() -> None:
    # fails CLOSED: the strict branch reports the mid-flight value it can see
    assert CONVERGENCE._archived_plan_status(ONLY_SPANNED.format(value="DRAFT")) == "DRAFT"
    assert CONVERGENCE._archived_plan_status(ONLY_SPANNED.format(value="EXECUTED")) is None


# --- C4: the two severity reads in check_plan_quality --------------------------------------------------------------


def test_the_severity_reads_skip_a_spanned_draft_and_keep_a_real_one() -> None:
    assert QUALITY._modern_status(SPAN_THEN_REAL.format(real="CONVERGED")) == ("CONVERGED", True)
    assert QUALITY._modern_status("# P\n\n**Status:** DRAFT\n") == ("DRAFT", False)
    assert QUALITY._modern_status(ONLY_SPANNED.format(value="DRAFT")) == (None, True)
    assert QUALITY._modern_status("# P\n\nnothing\n") == (None, False)


# --- C5: every Status read in both files routes through the helpers ------------------------------------------------


def test_every_status_read_routes_through_the_span_aware_helpers() -> None:
    conv = (ENF / "check_convergence.py").read_text(encoding="utf-8")
    assert not re.search(r"(?<![A-Z_])_STATUS_LINE\.(search|match|finditer|findall)\(", conv)
    assert conv.count("_archived_plan_status(") == 3, (
        "the def plus the two archived-plan call sites"
    )
    quality = (ENF / "check_plan_quality.py").read_text(encoding="utf-8")
    assert not re.search(r"MODERN_STATUS_RE\.search\(_BLOCKQUOTE_RE", quality)
    assert quality.count("_modern_status(") == 4, (
        "the def plus the spine, _check_modern and lane-severity reads"
    )
