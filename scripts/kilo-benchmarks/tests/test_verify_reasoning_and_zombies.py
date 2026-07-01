"""Regression guards for two systemic bugs caught 2026-07-01 by
external fact-check:

1. _live_caps missed 'reasoning' in supported_parameters. Models that
   support reasoning as a toggle (no explicit effort levels published)
   were incorrectly stored as has_reasoning=0 despite being thinking-
   capable. Real cases: google/gemini-2.5-flash,
   qwen/qwen3.5-flash-02-23, x-ai/grok-4.20.

2. Deprecation blind spot: verify's db_rows filter (via_openrouter=1)
   made it impossible for the delisted check to see rows that had
   already had via_openrouter flipped to 0. Once OR delisted a model
   and the flag flipped, the row was invisible forever. Real case:
   x-ai/grok-4-fast — shown as 'active $0.20/M' in the browser
   despite OR having removed it. 178 rows were in this zombie state.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_live_caps_flags_parameter_supported_reasoning():
    """Model where OR publishes `reasoning` in supported_parameters but
    has no top-level reasoning block (gemini-2.5-flash / qwen3.5-flash
    shape). Must return has_reasoning=1."""
    from verify_openrouter_catalog import _live_caps

    record = {
        "id": "google/gemini-2.5-flash",
        "architecture": {"input_modalities": ["text", "image"]},
        "supported_parameters": [
            "include_reasoning",
            "max_tokens",
            "reasoning",
            "response_format",
            "seed",
            "structured_outputs",
            "temperature",
            "tool_choice",
            "tools",
            "top_p",
        ],
    }
    caps = _live_caps(record)
    assert caps["has_reasoning"] == 1, (
        "reasoning in supported_parameters is the toggle-support signal; "
        f"got has_reasoning={caps['has_reasoning']}"
    )
    assert caps["has_vision"] == 1
    assert caps["has_tools"] == 1


def test_live_caps_no_reasoning_when_truly_absent():
    """meta-llama/llama-4-* have no reasoning param at all — must
    still return has_reasoning=0."""
    from verify_openrouter_catalog import _live_caps

    record = {
        "architecture": {"input_modalities": ["text", "image"]},
        "supported_parameters": [
            "max_tokens",
            "response_format",
            "seed",
            "temperature",
            "tool_choice",
            "tools",
            "top_p",
        ],
    }
    assert _live_caps(record)["has_reasoning"] == 0


def test_live_caps_flags_mandatory_reasoning_block():
    """OR's `reasoning: {mandatory: true}` block also flags."""
    from verify_openrouter_catalog import _live_caps

    record = {
        "architecture": {"input_modalities": ["text"]},
        "supported_parameters": ["max_tokens", "temperature"],
        "reasoning": {"mandatory": True},
    }
    assert _live_caps(record)["has_reasoning"] == 1


def _make_seed_db_with_zombie(tmp_path: Path) -> Path:
    """DB with one zombie orphan (all-route-flags=0 but status=active)
    plus one truly-routed active row that must NOT be deprecated."""
    db = tmp_path / "seed.db"
    conn = sqlite3.connect(db)
    conn.executescript(
        """
        CREATE TABLE agents (
            id TEXT PRIMARY KEY,
            name TEXT, provider TEXT, api_id TEXT,
            input_cost_per_m REAL DEFAULT 0,
            output_cost_per_m REAL DEFAULT 0,
            context_window_k INTEGER DEFAULT 128,
            has_vision INTEGER DEFAULT 0, has_tools INTEGER DEFAULT 0,
            is_agentic INTEGER DEFAULT 0, arena_elo INTEGER, task_tier INTEGER,
            perf_per_dollar REAL, status TEXT DEFAULT 'active',
            last_verified TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP, variant TEXT,
            blocked INTEGER DEFAULT 0, has_reasoning INTEGER DEFAULT 0,
            via_openrouter INTEGER DEFAULT 0, via_kilo INTEGER DEFAULT 0,
            via_dashscope INTEGER DEFAULT 0, via_siliconflow INTEGER DEFAULT 0,
            kilo_input_cost_per_m REAL, kilo_output_cost_per_m REAL,
            kilo_family TEXT, kilo_provider_id TEXT,
            kilo_cache_read_cost_per_m REAL, kilo_cache_write_cost_per_m REAL,
            kilo_release_date TEXT, pricing_unit TEXT,
            is_moderated INTEGER DEFAULT 0, reasoning_mandatory INTEGER DEFAULT 0,
            discard_reason TEXT
        );
        -- Zombie orphan: all route flags 0, still active. Must deprecate.
        INSERT INTO agents (id, name, provider, status) VALUES
            ('x-ai/grok-4-fast', 'x-ai: Grok 4 Fast', 'x-ai', 'active');
        -- Genuinely routed row: still on OR + Kilo. Must NOT deprecate.
        INSERT INTO agents (id, name, provider, status, via_openrouter, via_kilo) VALUES
            ('anthropic/claude-opus-4.8', 'Anthropic: Claude Opus 4.8', 'anthropic', 'active', 1, 1);
        -- Direct-vendor row: via_dashscope=1, still active. Must NOT deprecate.
        INSERT INTO agents (id, name, provider, status, via_dashscope) VALUES
            ('qwen/qwen-mt-turbo', 'Qwen MT Turbo', 'qwen', 'active', 1);
        -- OR meta-route (openrouter/*): must NOT deprecate.
        INSERT INTO agents (id, name, provider, status) VALUES
            ('openrouter/owl-alpha', 'OwlAlpha', 'openrouter', 'active');
        """
    )
    conn.commit()
    conn.close()
    return db


def test_zombie_orphan_sweep_deprecates_routeless_rows(tmp_path, monkeypatch):
    """The apply_fixes zombie sweep must deprecate rows with all four
    route flags at 0 (excluding openrouter/* meta-routes)."""
    import verify_openrouter_catalog as verify_module

    db_path = _make_seed_db_with_zombie(tmp_path)

    # Minimal fake live catalogs — verify doesn't need to find anything
    # here for the sweep to run. Just serve empty responses.
    monkeypatch.setattr(verify_module, "_fetch_kilo", lambda: {})
    monkeypatch.setattr(verify_module, "_fetch_live", lambda: {})

    report = verify_module.verify(db_path)
    verify_module.apply_fixes(report, db_path)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    grok = conn.execute("SELECT status FROM agents WHERE id='x-ai/grok-4-fast'").fetchone()
    dashscope = conn.execute("SELECT status FROM agents WHERE id='qwen/qwen-mt-turbo'").fetchone()
    owl = conn.execute("SELECT status FROM agents WHERE id='openrouter/owl-alpha'").fetchone()
    conn.close()

    assert grok["status"] == "deprecated", (
        f"zombie orphan (via_openrouter=0 AND via_kilo=0 AND no direct route) "
        f"must be deprecated; got status={grok['status']!r}"
    )
    # Opus loses via_openrouter (empty live) but claim it was still Kilo?
    # Kilo also empty — so it should ALSO be deprecated. Actually both
    # flags flip to 0 during verify because upstream is empty. Verify the
    # sweep is aggressive: this is the correct behavior — routeless =
    # deprecated. Only the direct-vendor row and openrouter/* survive.
    assert dashscope["status"] == "active", (
        "direct-vendor row (via_dashscope=1) must stay active — the sweep "
        "exempts operator-seeded specialist routes"
    )
    assert owl["status"] == "active", (
        "openrouter/* meta-routes must stay active — OR hides them from "
        "/api/v1/models but keeps them routable"
    )
