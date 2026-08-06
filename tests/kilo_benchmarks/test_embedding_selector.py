"""Integration tests for the embedding selection pipeline.

Runs against the REAL `kilo_agents.db` (read-only for the selector tests;
writable for the orchestrator tests). Mirrors the chat-side test style:
no mocks, adapt to daily catalog drift by re-querying the DB rather than
hardcoding model ids.

Tests cover:
- Selector: floors are enforced, free-tier excluded, ordering is deterministic.
- Orchestrator: writes embedding_roles + embedding_roles_history, emits both
  JSON files, idempotent on re-run.
- Schema: required columns / tables exist after the scraper has run once.
"""

from __future__ import annotations

import importlib.util
import json
import sqlite3
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = REPO_ROOT / "scripts" / "kilo-benchmarks"
DB_PATH = SCRIPT_DIR / "kilo_agents.db"
CONFIG_PATH = SCRIPT_DIR / "embedding_role_configs.yaml"


def _load_module(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPT_DIR / f"{name}.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


embedding_selector = _load_module("embedding_selector")
embedding_role_mapper = _load_module("embedding_role_mapper")
embedding_models_db = _load_module("embedding_models_db")

select_for_role = embedding_selector.select_for_role
NoEligibleEmbeddingError = embedding_selector.NoEligibleEmbeddingError
FREE_MARKERS = embedding_selector.FREE_MARKERS


@pytest.fixture(scope="module")
def db_conn():
    if not DB_PATH.exists():
        pytest.skip("kilo_agents.db missing — run embedding_models_db.py first")
    # Ensure the embedding_models table has been populated; skip the suite if not.
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='embedding_models'"
        )
        if cur.fetchone() is None:
            pytest.skip("embedding_models table not created — run embedding_models_db.py")
        count = conn.execute("SELECT COUNT(*) FROM embedding_models").fetchone()[0]
        if count == 0:
            pytest.skip("embedding_models is empty — run embedding_models_db.py all")
    except Exception:
        conn.close()
        raise
    yield conn
    conn.close()


@pytest.fixture(scope="module")
def role_configs():
    return yaml.safe_load(CONFIG_PATH.read_text())["roles"]


# ─── Schema / scraper sanity ───────────────────────────────────────────────


def test_schema_has_required_columns(db_conn):
    cols = {r[1] for r in db_conn.execute("PRAGMA table_info(embedding_models)").fetchall()}
    required = {
        "id",
        "input_cost_per_m",
        "context_window_k",
        "is_multilingual",
        "is_code_tuned",
        "is_ga",
        "quality_tier",
        "status",
        "blocked",
    }
    missing = required - cols
    assert not missing, f"missing columns: {missing}"


def test_schema_has_role_tables(db_conn):
    tables = {
        r[0]
        for r in db_conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    }
    assert {"embedding_roles", "embedding_roles_history"}.issubset(tables)


def test_derive_helpers_pure_functions():
    """The id-pattern helpers must be deterministic and pure."""
    assert embedding_models_db.derive_is_multilingual("qwen/qwen3-embedding-8b") == 1
    assert embedding_models_db.derive_is_multilingual("baai/bge-m3") == 1
    assert embedding_models_db.derive_is_multilingual("openai/text-embedding-3-small") == 0
    assert embedding_models_db.derive_is_code_tuned("mistralai/codestral-embed-2505") == 1
    assert embedding_models_db.derive_is_code_tuned("qwen/qwen3-embedding-8b") == 0
    assert embedding_models_db.derive_is_ga("openai/text-embedding-3-large") == 1
    assert embedding_models_db.derive_is_ga("google/gemini-embedding-2-preview") == 0
    assert embedding_models_db.derive_quality_tier(0.005) == 1
    assert embedding_models_db.derive_quality_tier(0.05) == 2
    assert embedding_models_db.derive_quality_tier(0.15) == 3
    assert embedding_models_db.derive_quality_tier(-1.0) == 1


# ─── Selector floors ───────────────────────────────────────────────────────


def test_multilingual_primary_returns_multilingual_models_only(db_conn, role_configs):
    cfg = role_configs["multilingual_primary"]
    rows = select_for_role(cfg)
    assert rows, "multilingual_primary should yield at least one row"
    for r in rows:
        assert r["is_multilingual"] == 1
        assert r["is_ga"] == 1
        assert r["context_window_k"] >= cfg["min_context_window_k"]
        assert r["quality_tier"] >= cfg["min_quality_tier"]
        lower = r["id"].lower()
        assert not any(m in lower for m in FREE_MARKERS)


def test_frontier_reference_enforces_tier_three(db_conn, role_configs):
    cfg = role_configs["frontier_reference"]
    rows = select_for_role(cfg)
    assert rows
    for r in rows:
        assert r["quality_tier"] >= 3, f"{r['id']} has quality_tier={r['quality_tier']}"
        assert r["is_ga"] == 1


def test_code_embedding_enforces_code_tuned(db_conn, role_configs):
    cfg = role_configs["code_embedding"]
    rows = select_for_role(cfg)
    assert rows
    for r in rows:
        assert r["is_code_tuned"] == 1


def test_selector_ordering_cheapest_first(db_conn, role_configs):
    """Within a role, results must be sorted by input_cost_per_m ASC."""
    for role_name, cfg in role_configs.items():
        try:
            rows = select_for_role(cfg, limit=10)
        except NoEligibleEmbeddingError:
            continue
        costs = [r["input_cost_per_m"] for r in rows]
        assert costs == sorted(costs), f"{role_name} not sorted ASC: {costs}"


def test_unsatisfiable_floors_raise():
    """An impossible floor must raise rather than return a degraded pick."""
    impossible = {
        "slots": 1,
        "min_quality_tier": 3,
        "min_context_window_k": 1_000_000,  # 1M-token embedder doesn't exist
        "require_multilingual": True,
        "require_code_tuned": True,
        "allow_free": False,
        "stability_required": True,
        "cost_axis": "input",
    }
    with pytest.raises(NoEligibleEmbeddingError):
        select_for_role(impossible)


def test_invalid_cost_axis_raises():
    bad = {
        "slots": 1,
        "min_quality_tier": 1,
        "min_context_window_k": 1,
        "require_multilingual": False,
        "require_code_tuned": False,
        "allow_free": False,
        "stability_required": True,
        "cost_axis": "output",
    }
    with pytest.raises(ValueError):
        select_for_role(bad)


# ─── Orchestrator end-to-end ───────────────────────────────────────────────


def _fresh_conn() -> sqlite3.Connection:
    """Open a new connection — needed after run() writes so that reads see
    the committed state (the module-scoped db_conn caches a snapshot)."""
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def test_role_mapper_writes_db_and_json(role_configs):
    """Full pipeline writes embedding_roles, history, and both JSON files."""
    assignments = embedding_role_mapper.run()

    # 1. Returned shape: every role from the YAML appears.
    assert set(assignments.keys()) == set(role_configs.keys())

    expected_pairs = {
        (role, idx + 1, w["id"])
        for role, winners in assignments.items()
        for idx, w in enumerate(winners)
    }

    # 2. DB rows match the returned assignments exactly. Use a fresh
    #    connection so we see the writer's committed state.
    c = _fresh_conn()
    try:
        db_rows = c.execute(
            "SELECT role, priority, model_id, score_used FROM embedding_roles "
            "ORDER BY role, priority"
        ).fetchall()
        actual_pairs = {(r["role"], r["priority"], r["model_id"]) for r in db_rows}
        assert actual_pairs == expected_pairs

        # 3. History got today's snapshot.
        today_count = c.execute(
            "SELECT COUNT(*) FROM embedding_roles_history WHERE snapshot_date = DATE('now')"
        ).fetchone()[0]
        assert today_count == len(expected_pairs), (
            "embedding_roles_history must contain one row per (role, priority) for today"
        )
    finally:
        c.close()

    # 4. JSON files written and valid.
    assignments_json = json.loads(embedding_role_mapper.ASSIGNMENTS_PATH.read_text())
    assert set(assignments_json["roles"]) == set(role_configs.keys())
    traycer_json = json.loads(embedding_role_mapper.TRAYCER_EXPORT_PATH.read_text())
    assert set(traycer_json["roles"]) == set(role_configs.keys())


def test_role_mapper_is_idempotent_on_rerun():
    """Running the mapper twice in a row must NOT duplicate embedding_roles."""
    embedding_role_mapper.run()
    c1 = _fresh_conn()
    try:
        count_first = c1.execute("SELECT COUNT(*) FROM embedding_roles").fetchone()[0]
    finally:
        c1.close()

    embedding_role_mapper.run()
    c2 = _fresh_conn()
    try:
        count_second = c2.execute("SELECT COUNT(*) FROM embedding_roles").fetchone()[0]
        assert count_first == count_second, (
            f"re-run grew table from {count_first} to {count_second} — "
            "UNIQUE(role, priority) not enforced?"
        )
        # History snapshot for today should also remain exactly at count_first
        # (UNIQUE(role, priority, snapshot_date) → INSERT OR REPLACE upserts).
        today_count = c2.execute(
            "SELECT COUNT(*) FROM embedding_roles_history WHERE snapshot_date = DATE('now')"
        ).fetchone()[0]
        assert today_count == count_first
    finally:
        c2.close()


def test_qwen3_embedding_8b_wins_multilingual_primary(db_conn):
    """Acceptance: today's known target winner for multilingual_primary is
    qwen/qwen3-embedding-8b. If this fails, either the catalog has drifted or
    the floors need adjusting — investigate before changing the assertion."""
    assignments = embedding_role_mapper.run()
    winners = assignments.get("multilingual_primary", [])
    if not winners:
        pytest.skip("multilingual_primary has no eligible model today (catalog drift)")
    assert winners[0]["id"] == "qwen/qwen3-embedding-8b", (
        f"Expected qwen/qwen3-embedding-8b at P1, got {winners[0]['id']}"
    )
