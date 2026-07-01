"""Meta-regression: the audit script must catch every bug type it
claims to cover. Without this test, "100% clean" is tautological —
the audit can pass because it lacks the code path to find real bugs
(the 2026-07-01 has_reasoning / zombie-orphan failure).

Each test seeds a DB with one specific drift, runs the audit against
a controlled fake live-OR catalog, and asserts the drift is surfaced.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _seed_db(tmp_path: Path, overrides: dict | None = None) -> Path:
    """Seed a minimal DB with anthropic/claude-opus-4.8 marked as fully
    OR-routed. Overrides let each test invert one field to inject drift."""
    base = {
        "id": "anthropic/claude-opus-4.8",
        "name": "Anthropic: Claude Opus 4.8",
        "provider": "anthropic",
        "input_cost_per_m": 5.0,
        "output_cost_per_m": 25.0,
        "cache_read_cost_per_m": 0.5,
        "cache_write_cost_per_m": 6.25,
        "context_window_k": 1000,
        "max_completion_tokens": 128000,
        "has_vision": 1,
        "has_tools": 1,
        "has_reasoning": 1,
        "is_moderated": 0,
        "canonical_slug": "anthropic/claude-4.8-opus-20260528",
        "description": "Test description longer than 20 chars to enable audit compare",
        "status": "active",
        "via_openrouter": 1,
        "via_kilo": 1,
    }
    base.update(overrides or {})

    db = tmp_path / "seed.db"
    conn = sqlite3.connect(db)
    conn.executescript(
        """
        CREATE TABLE agents (
            id TEXT PRIMARY KEY, name TEXT, provider TEXT, api_id TEXT,
            input_cost_per_m REAL, output_cost_per_m REAL,
            cache_read_cost_per_m REAL, cache_write_cost_per_m REAL,
            context_window_k INTEGER, has_vision INTEGER, has_tools INTEGER,
            has_reasoning INTEGER, is_agentic INTEGER, arena_elo INTEGER,
            task_tier INTEGER, perf_per_dollar REAL, status TEXT DEFAULT 'active',
            last_verified TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP, variant TEXT,
            blocked INTEGER DEFAULT 0, via_openrouter INTEGER DEFAULT 0,
            via_kilo INTEGER DEFAULT 0, via_dashscope INTEGER DEFAULT 0,
            via_siliconflow INTEGER DEFAULT 0, kilo_input_cost_per_m REAL,
            kilo_output_cost_per_m REAL, canonical_slug TEXT,
            is_moderated INTEGER DEFAULT 0, max_completion_tokens INTEGER,
            reasoning_mandatory INTEGER DEFAULT 0,
            description TEXT
        );
        """
    )
    conn.execute(
        f"INSERT INTO agents ({','.join(base.keys())}) VALUES ({','.join('?' * len(base))})",
        list(base.values()),
    )
    conn.commit()
    conn.close()
    return db


# The "true" upstream OR record for claude-opus-4.8 — the audit compares against this
LIVE_OPUS = {
    "id": "anthropic/claude-opus-4.8",
    "name": "Anthropic: Claude Opus 4.8",
    "description": "Test description longer than 20 chars to enable audit compare",
    "context_length": 1000000,
    "top_provider": {
        "context_length": 1000000,
        "max_completion_tokens": 128000,
        "is_moderated": False,
    },
    "canonical_slug": "anthropic/claude-4.8-opus-20260528",
    "pricing": {
        "prompt": "0.000005",
        "completion": "0.000025",
        "input_cache_read": "0.0000005",
        "input_cache_write": "0.00000625",
    },
    "architecture": {"input_modalities": ["text", "image"]},
    "supported_parameters": ["reasoning", "tools", "temperature", "max_tokens"],
    "reasoning": {"supported_efforts": ["max", "high", "medium", "low"]},
}


def _run_audit(db_path: Path, live_catalog: dict) -> dict:
    """Invoke the audit's field-checker directly (no HTTP)."""
    from audit_ui_values import audit_or_fields

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    db_rows = [dict(r) for r in conn.execute("SELECT * FROM agents WHERE status='active'")]
    conn.close()
    return audit_or_fields(db_rows, live_catalog)


def test_audit_catches_input_price_drift(tmp_path):
    db = _seed_db(tmp_path, overrides={"input_cost_per_m": 999.0})
    findings = _run_audit(db, {LIVE_OPUS["id"]: LIVE_OPUS})
    drifts = [d for d in findings["verifier_tracked_drift"] if d["field"] == "input_cost_per_m"]
    assert drifts, "audit must catch input price drift"


def test_audit_catches_output_price_drift(tmp_path):
    db = _seed_db(tmp_path, overrides={"output_cost_per_m": 999.0})
    findings = _run_audit(db, {LIVE_OPUS["id"]: LIVE_OPUS})
    drifts = [d for d in findings["verifier_tracked_drift"] if d["field"] == "output_cost_per_m"]
    assert drifts, "audit must catch output price drift"


def test_audit_catches_context_drift(tmp_path):
    db = _seed_db(tmp_path, overrides={"context_window_k": 42})
    findings = _run_audit(db, {LIVE_OPUS["id"]: LIVE_OPUS})
    drifts = [d for d in findings["verifier_tracked_drift"] if d["field"] == "context_window_k"]
    assert drifts, "audit must catch context_window_k drift"


def test_audit_catches_cache_price_drift(tmp_path):
    db = _seed_db(tmp_path, overrides={"cache_read_cost_per_m": 999.0})
    findings = _run_audit(db, {LIVE_OPUS["id"]: LIVE_OPUS})
    drifts = [
        d for d in findings["verifier_untracked_drift"] if d["field"] == "cache_read_cost_per_m"
    ]
    assert drifts, "audit must catch cache_read_cost_per_m drift"


def test_audit_catches_reasoning_flag_drift(tmp_path):
    """This is the exact bug that got past me 2026-07-01. Seed has_reasoning=0
    on a model that OR reports as reasoning-capable — audit MUST flag it."""
    db = _seed_db(tmp_path, overrides={"has_reasoning": 0})
    findings = _run_audit(db, {LIVE_OPUS["id"]: LIVE_OPUS})
    drifts = [d for d in findings["verifier_tracked_drift"] if d["field"] == "has_reasoning"]
    assert drifts, (
        "audit must catch has_reasoning=0 when OR publishes reasoning in "
        "supported_parameters (2026-07-01 regression guard)"
    )


def test_audit_catches_vision_flag_drift(tmp_path):
    db = _seed_db(tmp_path, overrides={"has_vision": 0})
    findings = _run_audit(db, {LIVE_OPUS["id"]: LIVE_OPUS})
    drifts = [d for d in findings["verifier_tracked_drift"] if d["field"] == "has_vision"]
    assert drifts


def test_audit_catches_tools_flag_drift(tmp_path):
    db = _seed_db(tmp_path, overrides={"has_tools": 0})
    findings = _run_audit(db, {LIVE_OPUS["id"]: LIVE_OPUS})
    drifts = [d for d in findings["verifier_tracked_drift"] if d["field"] == "has_tools"]
    assert drifts


def test_audit_catches_canonical_slug_drift(tmp_path):
    db = _seed_db(tmp_path, overrides={"canonical_slug": "wrong-canonical"})
    findings = _run_audit(db, {LIVE_OPUS["id"]: LIVE_OPUS})
    drifts = [d for d in findings["verifier_tracked_drift"] if d["field"] == "canonical_slug"]
    assert drifts


def test_audit_catches_max_completion_tokens_drift(tmp_path):
    db = _seed_db(tmp_path, overrides={"max_completion_tokens": 42})
    findings = _run_audit(db, {LIVE_OPUS["id"]: LIVE_OPUS})
    drifts = [
        d for d in findings["verifier_tracked_drift"] if d["field"] == "max_completion_tokens"
    ]
    assert drifts


def test_audit_catches_row_missing_from_live_when_via_openrouter_true(tmp_path):
    """The exact grok-4-fast case: DB says via_openrouter=1 + active, but
    OR live doesn't have the row. Audit MUST surface it."""
    db = _seed_db(
        tmp_path,
        overrides={
            "id": "x-ai/grok-4-fast",
            "name": "Grok 4 Fast",
            "via_openrouter": 1,
        },
    )
    findings = _run_audit(db, live_catalog={})
    assert "x-ai/grok-4-fast" in findings["row_missing_from_live"], (
        "audit must flag OR-claimed rows that are absent upstream (2026-07-01 regression guard)"
    )


def test_audit_no_false_positive_on_clean_row(tmp_path):
    """A fully-correct DB row must produce ZERO drift findings."""
    db = _seed_db(tmp_path)  # no overrides — everything matches LIVE_OPUS
    findings = _run_audit(db, {LIVE_OPUS["id"]: LIVE_OPUS})
    assert not findings["verifier_tracked_drift"], (
        f"clean row must have zero tracked drift; got: {findings['verifier_tracked_drift']}"
    )
    assert not findings["verifier_untracked_drift"], (
        f"clean row must have zero untracked drift; got: {findings['verifier_untracked_drift']}"
    )
    assert not findings["row_missing_from_live"]
