# AFTER-EDIT: ../stage_ai_rule_renders.py
"""Marker-scoped committer tests — the sibling-bundling guard is the load-bearing behavior."""

from __future__ import annotations

import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS_DIR.parent))

from stage_ai_rule_renders import allowed_lines, diff_is_engine_only  # noqa: E402

BASE = """---
trigger: glob
---

# 3. Language AI

Last content verification: 2026-08-16

Hand-written prose a sibling may edit.

<!-- GATEWAY_COUNTS:START — last-refreshed: 2026-08-16 (auto-managed by x.py) -->
*Live gateway counts (2026-08-16 UTC):*
| a | 1 |
<!-- GATEWAY_COUNTS:END -->

More hand prose.
"""


def test_pure_marker_refresh_qualifies():
    new = BASE.replace("2026-08-16", "2026-08-18")  # date line + marker region only
    ok, offender = diff_is_engine_only(BASE, new)
    assert ok, offender


def test_hand_edit_outside_markers_disqualifies():
    new = BASE.replace("Hand-written prose a sibling may edit.", "SIBLING EDIT")
    ok, offender = diff_is_engine_only(BASE, new)
    assert not ok and offender in ("SIBLING EDIT", "Hand-written prose a sibling may edit.")


def test_mixed_engine_plus_hand_edit_disqualifies():
    new = BASE.replace("2026-08-16", "2026-08-18").replace("More hand prose.", "tweak")
    ok, offender = diff_is_engine_only(BASE, new)
    assert not ok and offender in ("More hand prose.", "tweak")


def test_row_change_inside_marker_qualifies():
    new = BASE.replace("| a | 1 |", "| a | 2 |\n| b | 3 |")
    ok, offender = diff_is_engine_only(BASE, new)
    assert ok, offender


def test_allowed_lines_marker_bounds_inclusive():
    lines = BASE.splitlines()
    allowed = allowed_lines(lines)
    start = next(i for i, ln in enumerate(lines) if "GATEWAY_COUNTS:START" in ln)
    end = next(i for i, ln in enumerate(lines) if "GATEWAY_COUNTS:END" in ln)
    date = next(i for i, ln in enumerate(lines) if ln.startswith("Last content verification"))
    assert {start, start + 1, start + 2, end, date} <= allowed
    prose = next(i for i, ln in enumerate(lines) if ln.startswith("Hand-written"))
    assert prose not in allowed


def test_rogue_human_start_region_disqualifies():
    # PURE INSERTION: a sibling appends their own START-shaped comment region (no "auto-managed
    # by") without touching any existing line — the old side offers no catch, so the region must
    # NOT self-allow on the new side. False-qualify auto-publishes fleet-wide (finding F2).
    new = BASE + "<!-- NOTE:START -->\nSIBLING EDIT INSIDE FAKE REGION\n<!-- NOTE:END -->\n"
    ok, offender = diff_is_engine_only(BASE, new)
    assert not ok


def test_rogue_end_line_in_prose_disqualifies():
    # PURE INSERTION of a stray END with no open engine region — must not self-allow
    new = BASE + "<!-- GATEWAY_COUNTS:END -->\n"
    ok, offender = diff_is_engine_only(BASE, new)
    assert not ok


def test_identical_content_reports_not_engine_only():
    # mode-only dirt: content identical -> the caller must SKIP, not stage a chmod
    ok, offender = diff_is_engine_only(BASE, BASE)
    assert ok  # no changed lines — but qualifying_paths must skip old==new BEFORE calling this


def test_allowed_lines_exact_set():
    lines = BASE.splitlines()
    allowed = allowed_lines(lines)
    start = next(i for i, ln in enumerate(lines) if "GATEWAY_COUNTS:START" in ln)
    end = next(i for i, ln in enumerate(lines) if "GATEWAY_COUNTS:END" in ln)
    date = next(i for i, ln in enumerate(lines) if ln.startswith("Last content verification"))
    assert allowed == set(range(start, end + 1)) | {date}  # EXACT — nothing else is engine-owned
