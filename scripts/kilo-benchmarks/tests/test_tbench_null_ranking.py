#!/usr/bin/env python3
# AFTER-EDIT: scripts/kilo-benchmarks/compute_assignments.py scripts/kilo-benchmarks/category_selector.py scripts/kilo-benchmarks/llm_selector.py
"""Regression tests for the tbench NULL-ranking fix (plan-1 Phase C).

The bug: `COALESCE(tbench_accuracy, 0)` / `none_to_zero(tbench)` in a DESC sort
made an UNBENCHED (NULL) model tie with a genuinely-measured 0-scorer — so an
unmeasured model ranked identically to one proven 0% at terminal tasks. The fix
sorts NULL strictly LAST (below real 0). The `>=70` hard-min filters and the
composite-score site are intentionally NOT changed (NULL→0 is correct there).
"""

from __future__ import annotations

import re
import sqlite3
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPT_DIR))

import compute_assignments as ca  # noqa: E402


# --- SQL sort sites (category_selector:119, llm_selector:183) -----------------
def test_sql_desc_orders_null_after_real_zero():
    """The fixed SQL uses `tbench_accuracy DESC` (no COALESCE) → SQLite sorts
    NULL last, so a real 0 ranks ABOVE an unbenched NULL."""
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE agents (id TEXT, tbench_accuracy REAL)")
    conn.executemany(
        "INSERT INTO agents VALUES (?,?)",
        [("real50", 50.0), ("real0", 0.0), ("unbenched", None), ("real30", 30.0)],
    )
    conn.commit()
    order = [r[0] for r in conn.execute(
        "SELECT id FROM agents ORDER BY tbench_accuracy DESC"
    ).fetchall()]
    assert order == ["real50", "real30", "real0", "unbenched"]
    assert order.index("real0") < order.index("unbenched")  # the specific bug


def _no_coalesce_tbench_desc(path: Path) -> bool:
    """True if the file has NO `COALESCE(...tbench_accuracy..., 0) ... DESC` sort."""
    txt = path.read_text()
    return re.search(r"COALESCE\([^)]*tbench_accuracy[^)]*,\s*0\)\s*DESC", txt) is None


def test_category_selector_sql_no_longer_coalesces_tbench_to_zero():
    assert _no_coalesce_tbench_desc(SCRIPT_DIR / "category_selector.py")


def test_llm_selector_sql_no_longer_coalesces_tbench_to_zero():
    assert _no_coalesce_tbench_desc(SCRIPT_DIR / "llm_selector.py")


# --- Python sort sites (compute_assignments) ----------------------------------
def test_null_last_key_orders_none_below_real_zero():
    # reverse=True sort → larger first; a real 0 must outrank None.
    assert ca._null_last(50.0) > ca._null_last(0.0) > ca._null_last(None)


def test_testing_role_ranks_real_zero_above_unbenched():
    """The testing-role pool is NOT tbench-filtered → NULL models reach the sort.
    A measured-0 model must rank above an unmeasured (NULL) one."""
    models = [
        {"id": "real0", "has_tools": 1, "is_agentic": 1, "tbench_accuracy": 0.0, "arena_elo": 1000},
        {"id": "unbenched", "has_tools": 1, "is_agentic": 1, "tbench_accuracy": None, "arena_elo": 1000},
        {"id": "real40", "has_tools": 1, "is_agentic": 1, "tbench_accuracy": 40.0, "arena_elo": 1000},
    ]
    order = ca.rank_testing_pool(models)
    assert order.index("real0") < order.index("unbenched")
    assert order[0] == "real40"


# --- Guard: the hard-min filters + composite are UNCHANGED (NULL→0 correct) ---
def test_hard_min_filter_still_excludes_unbenched():
    """A NULL-tbench model must still be excluded from a `>=70` pool."""
    models = [
        {"id": "unbenched", "has_tools": 1, "is_agentic": 1, "tbench_accuracy": None},
        {"id": "high", "has_tools": 1, "is_agentic": 1, "tbench_accuracy": 85.0},
    ]
    coding = ca.filter_ge70(models)
    assert [m["id"] for m in coding] == ["high"]
