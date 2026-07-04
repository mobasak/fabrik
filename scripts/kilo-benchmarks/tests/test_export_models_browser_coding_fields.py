# AFTER-EDIT: scripts/kilo-benchmarks/export_models_browser.py
"""Coding-subagent ranking → browser payload projection tests.

Plan 2026-07-04-plan-2-browser-coding-subagent-integration.md Phase A.
"""

from __future__ import annotations

import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPT_DIR))


def test_rank_all_returns_list_of_dicts_with_score_and_grade():
    """The public `rank_all()` must return a list where every row carries
    both a numeric `score` in [0, 1] and a letter `doc_grade`."""
    from rank_coding_subagents import rank_all

    rows = rank_all()
    assert len(rows) > 0
    for r in rows:
        assert isinstance(r, dict), r
        assert "id" in r
        assert "score" in r and 0.0 <= r["score"] <= 1.0, r
        assert r["doc_grade"] in {"A+", "A", "B+", "B", "B-", "C+", "C"}, r["doc_grade"]


def test_public_aliases_match_private_originals():
    """The public aliases must return exactly what the private helpers do."""
    from rank_coding_subagents import (
        _fmt_body_hint,
        _grade_doc_review,
        fmt_body_hint,
        grade_doc_review,
    )

    for args in [(300, 75, 0, 0, 0), (900, 0, 0, 45, 1500), (100, 0, 0, 0, 0)]:
        assert grade_doc_review(*args) == _grade_doc_review(*args)
    for mid in ["minimax/minimax-m3", "z-ai/glm-5", "no/such-model"]:
        assert fmt_body_hint(mid) == _fmt_body_hint(mid)


def test_public_constants_are_single_source():
    """Browser code MUST read these constants from the ranker — never fork them."""
    from rank_coding_subagents import (
        BODY_HINTS,
        CODING_BODY_HINTS,
        CODING_EXCLUDE_MODELS,
        CODING_PROVIDER_PINS,
        EXCLUDE_MODELS,
        PROVIDER_PINS,
    )

    assert CODING_EXCLUDE_MODELS is EXCLUDE_MODELS
    assert CODING_PROVIDER_PINS is PROVIDER_PINS
    assert CODING_BODY_HINTS is BODY_HINTS


def test_export_payload_carries_coding_fields():
    """The browser JSON payload must project the ranker fields onto every
    chat model — sparse dict of None for out-of-scope rows."""
    from export_models_browser import _build_payload
    from rank_coding_subagents import DB_PATH

    payload = _build_payload(DB_PATH)
    chat = payload["chat_models"]
    assert len(chat) > 0

    # Every chat row has the 6 new keys (uniform schema)
    for m in chat:
        assert "code_subagent_candidate" in m
        assert "code_fit_score" in m
        assert "doc_code_grade" in m
        assert "code_excluded_reason" in m
        assert "code_provider_pin" in m
        assert "code_body_hint" in m

    # At least 30 rows ARE coding-subagent candidates w/ score + grade
    candidates = [m for m in chat if m["code_subagent_candidate"]]
    assert len(candidates) >= 30
    for c in candidates:
        assert 0 <= c["code_fit_score"] <= 1
        assert c["doc_code_grade"] in {"A+", "A", "B+", "B", "B-", "C+", "C"}

    # kimi-k2-thinking is excluded → candidate=False + excluded_reason non-empty
    exc = [m for m in chat if m["id"] == "moonshotai/kimi-k2-thinking"]
    assert len(exc) == 1
    assert exc[0]["code_subagent_candidate"] is False
    assert exc[0]["code_excluded_reason"] is not None

    # minimax/minimax-m3 → candidate=True + provider_pin populated
    m3 = [m for m in chat if m["id"] == "minimax/minimax-m3"]
    assert len(m3) == 1
    assert m3[0]["code_subagent_candidate"] is True
    assert m3[0]["code_provider_pin"] == ["Minimax", "Novita", "Parasail", "Together"]


def test_rank_all_respects_db_path_argument(tmp_path):
    """rank_all(db_path) MUST use the passed db_path, not the module default.

    Regression: earlier _fetch_chat_models called rank_all() with no arg,
    so a `--db /some/other.db` CLI would rank against the wrong DB.
    """
    import sqlite3

    from rank_coding_subagents import rank_all

    # Build an empty schema-compat DB — should yield zero candidates.
    empty_db = tmp_path / "empty.db"
    with sqlite3.connect(empty_db) as c:
        c.execute("""CREATE TABLE agents (
            id TEXT PRIMARY KEY, status TEXT, service_type TEXT,
            input_cost_per_m REAL, output_cost_per_m REAL,
            output_tokens_per_sec REAL,
            swe_bench_verified_pct REAL, aider_polyglot_pct REAL,
            aa_intelligence_index REAL, arena_elo REAL,
            context_window_k INTEGER, quality_tier INTEGER,
            has_reasoning INTEGER, via_openrouter INTEGER,
            cheapest_provider TEXT
        )""")

    rows = rank_all(empty_db)
    assert rows == [], f"empty DB should yield zero candidates, got {len(rows)}"


def test_export_payload_uses_supplied_db_path_for_overlay(tmp_path):
    """Regression for db_path plumbing: `_build_payload(db_path=X)` must
    overlay against X, not against the ranker's module default.

    The fake DB uses `minimax/minimax-m3` — a model that IS in the production
    DB's ranked pool. If the overlay incorrectly calls `rank_all()` (no arg)
    it will use the production DB and rank m3 as a candidate → test flips.
    Correctly calling `rank_all(fake_db)` returns empty (fake DB has no
    scored rows) → candidate is False → test passes.
    """
    import sqlite3

    from export_models_browser import _fetch_chat_models

    fake_db = tmp_path / "fake.db"
    with sqlite3.connect(fake_db) as c:
        c.execute("""CREATE TABLE agents (
            id TEXT PRIMARY KEY, api_id TEXT, name TEXT, provider TEXT,
            input_cost_per_m REAL, output_cost_per_m REAL, context_window_k INTEGER,
            status TEXT, service_type TEXT, quality_tier INTEGER,
            has_reasoning INTEGER, via_openrouter INTEGER, cheapest_provider TEXT,
            aa_intelligence_index REAL, arena_elo REAL,
            swe_bench_verified_pct REAL, aider_polyglot_pct REAL,
            output_tokens_per_sec REAL
        )""")
        c.execute("""CREATE TABLE agent_categories (agent_id TEXT, category TEXT)""")
        c.execute("""CREATE TABLE agent_roles (
            agent_id TEXT, role TEXT, priority INTEGER, assigned_by TEXT
        )""")
        # Insert an ID that IS a candidate in the production DB — but with
        # `status='deprecated'` so the ranker's `WHERE status='active'`
        # filter excludes it in the fake DB → `rank_all(fake_db) == []`.
        # The browser's unfiltered `SELECT * FROM agents` still shows it.
        c.execute(
            "INSERT INTO agents(id, name, status, service_type, quality_tier) "
            "VALUES ('minimax/minimax-m3','MiniMax M3 (fake)','deprecated','llm', 2)"
        )

    with sqlite3.connect(fake_db) as conn:
        chat = _fetch_chat_models(conn, fake_db)

    assert len(chat) == 1
    m = chat[0]
    assert m["id"] == "minimax/minimax-m3"
    # Would flip to True if the overlay ranked against the production DB.
    assert m["code_subagent_candidate"] is False, (
        "overlay MUST rank against the supplied db_path, not the ranker's "
        "module default — a True here means _fetch_chat_models is calling "
        "rank_all() with no arg (round-1 bug)"
    )
    assert m["code_fit_score"] is None
    assert m["doc_code_grade"] is None
    # excluded_reason + provider_pin + body_hint are populated from CONSTANTS
    # (not the ranker query), so they're independent of db_path.
    assert m["code_excluded_reason"] is None  # m3 isn't in EXCLUDE_MODELS
    # m3 IS in PROVIDER_PINS regardless of DB — this is the constant.
    assert m["code_provider_pin"] == ["Minimax", "Novita", "Parasail", "Together"]
    assert m["code_body_hint"] is not None  # includes the pin


def test_compose_score_stays_bounded_under_negative_cost_anomaly():
    """Defense-in-depth: even if a row's cost went negative (data-entry
    anomaly), the composite score MUST stay ≤ 1.0."""
    from rank_coding_subagents import _compose_score

    # All signals maxed + impossibly-negative cost
    row = {
        "swe": 100,
        "aider": 100,
        "aa_idx": 60,
        "arena": 2000,
        "db_tps": 1000,
        "in_M": -5.0,
        "out_M": -5.0,
    }
    score = _compose_score(row)
    assert 0.0 <= score <= 1.0, f"score {score} out of bounds"


def test_export_models_browser_does_not_fork_ranker_constants():
    """export_models_browser MUST import CODING_* from rank_coding_subagents,
    never define its own EXCLUDE_MODELS / PROVIDER_PINS / BODY_HINTS."""
    src = (SCRIPT_DIR / "export_models_browser.py").read_text()
    # No local dict/set literal named like the ranker's constants
    for forbidden in ["EXCLUDE_MODELS =", "PROVIDER_PINS =", "BODY_HINTS ="]:
        assert forbidden not in src, f"export_models_browser forks {forbidden}"
    # And it must reference the ranker's public API
    assert "from rank_coding_subagents import" in src
