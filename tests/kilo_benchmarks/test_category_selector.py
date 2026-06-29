"""Tests for `scripts/kilo-benchmarks/category_selector.py`.

Phase 3 of the OpenRouter routing plan. Pure-function unit tests on
synthetic DBs — never touch the real `kilo_agents.db`.
"""

from __future__ import annotations

import importlib.util
import sqlite3
import sys
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = REPO_ROOT / "scripts" / "kilo-benchmarks"

if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPT_DIR / f"{name}.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


sel = _load("category_selector")


def _make_db(rows: list[dict]) -> Path:
    """Build a temp DB with the minimal schema the selector needs."""
    tmp = Path(tempfile.mkdtemp()) / "test.db"
    conn = sqlite3.connect(tmp)
    conn.execute(
        """
        CREATE TABLE agents (
            id TEXT PRIMARY KEY,
            api_id TEXT, name TEXT, provider TEXT,
            input_cost_per_m REAL DEFAULT 0,
            output_cost_per_m REAL DEFAULT 0,
            context_window_k INTEGER DEFAULT 8,
            has_vision INTEGER DEFAULT 0,
            has_tools INTEGER DEFAULT 0,
            is_agentic INTEGER DEFAULT 0,
            has_reasoning INTEGER DEFAULT 0,
            arena_elo INTEGER,
            tbench_accuracy REAL,
            task_tier INTEGER,
            quality_tier INTEGER DEFAULT 1,
            is_ga INTEGER DEFAULT 1,
            status TEXT DEFAULT 'active',
            blocked INTEGER DEFAULT 0,
            weighted_coding REAL, humaneval_score REAL, coding_score REAL,
            livecodebench REAL, swe_bench_pro REAL,
            output_tokens_per_sec REAL, ttft_ms REAL,
            gateway_prices TEXT,
            cheapest_gateway TEXT,
            cheapest_gateway_price REAL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE agent_categories (
            agent_id TEXT NOT NULL,
            category TEXT NOT NULL,
            classified_at TIMESTAMP DEFAULT (datetime('now')),
            PRIMARY KEY (agent_id, category),
            FOREIGN KEY (agent_id) REFERENCES agents(id) ON DELETE CASCADE
        )
        """
    )
    for r in rows:
        # Pop the test-only `_category` marker before the agents insert.
        category = r.pop("_category", "language")
        cols = ", ".join(r.keys())
        qs = ", ".join("?" * len(r))
        conn.execute(f"INSERT INTO agents ({cols}) VALUES ({qs})", tuple(r.values()))
        conn.execute(
            "INSERT INTO agent_categories (agent_id, category) VALUES (?, ?)",
            (r["id"], category),
        )
    conn.commit()
    conn.close()
    return tmp


def test_basic_select():
    db = _make_db([
        {"id": "a/1", "provider": "a", "quality_tier": 2, "input_cost_per_m": 1.0,
         "_category": "language"},
        {"id": "a/2", "provider": "a", "quality_tier": 2, "input_cost_per_m": 0.5,
         "_category": "language"},
    ])
    rows = sel.select_for_category(
        "language",
        {"slots": 2, "min_quality_tier": 2, "sort_key": "input_cost_per_m ASC"},
        db_path=db,
    )
    assert [r["id"] for r in rows] == ["a/2", "a/1"]
    assert rows[0]["score_used"] == 0.5
    assert rows[0]["score_type"] == "input_cost_per_m"


def test_no_eligible_raises():
    db = _make_db([
        {"id": "low/tier", "provider": "x", "quality_tier": 1, "_category": "code"},
    ])
    with pytest.raises(sel.NoEligibleCategoryError):
        sel.select_for_category(
            "code",
            {"slots": 1, "min_quality_tier": 3},
            db_path=db,
        )


def test_require_vision_excludes():
    db = _make_db([
        {"id": "x/no-vision", "provider": "x", "has_vision": 0, "_category": "vision"},
        {"id": "x/yes-vision", "provider": "x", "has_vision": 1, "_category": "vision"},
    ])
    rows = sel.select_for_category(
        "vision",
        {"slots": 5, "require_vision": True},
        db_path=db,
    )
    assert [r["id"] for r in rows] == ["x/yes-vision"]


def test_allow_free_false_excludes_free():
    db = _make_db([
        {"id": "p/paid", "provider": "p", "input_cost_per_m": 2.0, "_category": "vision"},
        {"id": "p/model:free", "provider": "p", "input_cost_per_m": 0.0, "_category": "vision"},
    ])
    rows = sel.select_for_category(
        "vision",
        {"slots": 5, "allow_free": False, "sort_key": "input_cost_per_m ASC"},
        db_path=db,
    )
    assert [r["id"] for r in rows] == ["p/paid"]


def test_allow_free_true_includes_free():
    db = _make_db([
        {"id": "p/paid", "provider": "p", "input_cost_per_m": 2.0, "_category": "language"},
        {"id": "p/model:free", "provider": "p", "input_cost_per_m": 0.0, "_category": "language"},
    ])
    rows = sel.select_for_category(
        "language",
        {"slots": 5, "allow_free": True, "sort_key": "input_cost_per_m ASC"},
        db_path=db,
    )
    assert [r["id"] for r in rows] == ["p/model:free", "p/paid"]


def test_sort_key_allowlist_rejects_injection():
    db = _make_db([{"id": "x/1", "provider": "x", "_category": "language"}])
    with pytest.raises(ValueError, match="unsupported sort_key"):
        sel.select_for_category(
            "language",
            {"slots": 1, "sort_key": "1; DROP TABLE agents"},
            db_path=db,
        )


def test_blocked_rows_excluded():
    db = _make_db([
        {"id": "a/ok", "provider": "a", "blocked": 0, "_category": "language"},
        {"id": "a/blocked", "provider": "a", "blocked": 1, "_category": "language"},
    ])
    rows = sel.select_for_category(
        "language", {"slots": 5}, db_path=db,
    )
    assert [r["id"] for r in rows] == ["a/ok"]


def test_status_filter():
    db = _make_db([
        {"id": "a/active", "provider": "a", "status": "active", "_category": "language"},
        {"id": "a/deprecated", "provider": "a", "status": "deprecated",
         "_category": "language"},
    ])
    rows = sel.select_for_category(
        "language", {"slots": 5}, db_path=db,
    )
    assert [r["id"] for r in rows] == ["a/active"]


def test_slots_must_be_positive():
    """Pass A Finding 1: slots <= 0 must raise — SQLite's `LIMIT -1`
    means 'no limit' (returns all rows) and `LIMIT 0` returns zero;
    a YAML typo like `slots: -1` would otherwise silently emit every
    candidate, completely defeating per-category slot semantics."""
    db = _make_db([{"id": "x/1", "provider": "x", "_category": "language"}])
    for bad in (0, -1, -100):
        with pytest.raises(ValueError, match="slots must be >= 1"):
            sel.select_for_category(
                "language", {"slots": bad}, db_path=db,
            )


def test_slots_must_be_int_not_float_or_bool():
    """Pass B Finding 2: floats silently truncate via `int(...)`. Bools
    are a subclass of int in Python — `slots: yes` in YAML parses as
    True which would otherwise quietly become `slots: 1`. Strict type
    check rejects both."""
    db = _make_db([{"id": "x/1", "provider": "x", "_category": "language"}])
    for bad in (3.5, 0.0, -1.5, True, False, "1", None):
        with pytest.raises(ValueError, match="slots must be an integer"):
            sel.select_for_category(
                "language", {"slots": bad}, db_path=db,
            )
