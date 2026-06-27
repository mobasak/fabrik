"""Tests for `scripts/kilo-benchmarks/category_route_mapper.py`.

Phase 3 of the OpenRouter routing plan. Integration tests against
synthetic DBs — exercises the persist + emit-JSON paths end-to-end.
"""

from __future__ import annotations

import importlib.util
import json
import sqlite3
import sys
import tempfile
from pathlib import Path

import pytest
import yaml

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


mapper = _load("category_route_mapper")


def _build_db(rows: list[tuple[str, str]]) -> Path:
    """Build a temp DB. rows: list of (agent_id, category)."""
    tmp = Path(tempfile.mkdtemp()) / "test.db"
    conn = sqlite3.connect(tmp)
    conn.execute(
        """
        CREATE TABLE agents (
            id TEXT PRIMARY KEY,
            provider TEXT,
            input_cost_per_m REAL DEFAULT 1.0,
            output_cost_per_m REAL DEFAULT 1.0,
            context_window_k INTEGER DEFAULT 64,
            has_vision INTEGER DEFAULT 0,
            has_tools INTEGER DEFAULT 1,
            has_reasoning INTEGER DEFAULT 1,
            is_agentic INTEGER DEFAULT 0,
            arena_elo INTEGER DEFAULT 1200,
            tbench_accuracy REAL DEFAULT 50.0,
            quality_tier INTEGER DEFAULT 2,
            is_ga INTEGER DEFAULT 1,
            status TEXT DEFAULT 'active',
            blocked INTEGER DEFAULT 0
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
    conn.execute(
        """
        CREATE TABLE agent_roles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role TEXT,
            agent_id TEXT,
            priority INTEGER,
            reason TEXT,
            min_elo INTEGER,
            assigned_by TEXT,
            assigned_at TIMESTAMP DEFAULT (datetime('now')),
            score_used REAL,
            score_type TEXT
        )
        """
    )
    # Matches the LIVE production schema (verified 2026-06-27 PRAGMA):
    # NO UNIQUE constraint — Pass A Finding 2 / 3. Idempotency comes from
    # the route mapper's explicit DELETE-by-day-then-INSERT, not from
    # `INSERT OR REPLACE` (which would silently degrade to plain INSERT
    # on this schema).
    conn.execute(
        """
        CREATE TABLE agent_roles_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role TEXT NOT NULL,
            agent_id TEXT NOT NULL,
            priority INTEGER NOT NULL,
            reason TEXT,
            min_elo INTEGER,
            assigned_by TEXT,
            assigned_at TIMESTAMP NOT NULL,
            archived_at TIMESTAMP,
            score_used REAL,
            score_type TEXT
        )
        """
    )
    for agent_id, category in rows:
        # Insert agent if not yet there (handle agents in multiple categories)
        conn.execute(
            "INSERT OR IGNORE INTO agents (id, provider) VALUES (?, ?)",
            (agent_id, agent_id.split("/")[0]),
        )
        conn.execute(
            "INSERT OR IGNORE INTO agent_categories (agent_id, category) VALUES (?, ?)",
            (agent_id, category),
        )
    conn.commit()
    conn.close()
    return tmp


def _make_yaml(tmp_dir: Path) -> Path:
    cfg = {
        "categories": {
            "language": {
                "pack_file": ".windsurf/rules/ai/30-language.md",
                "slots": 2,
                "min_quality_tier": 2,
                "min_context_window_k": 32,
                "allow_free": True,
                "stability_required": False,
                "sort_key": "input_cost_per_m ASC",
                "notes": "test language category",
            },
            "vision": {
                "pack_file": ".windsurf/rules/ai/20-vision.md",
                "slots": 2,
                "require_vision": True,
                "allow_free": False,
                "stability_required": True,
                "sort_key": "input_cost_per_m ASC",
                "notes": "test vision category",
            },
        }
    }
    p = tmp_dir / "cfg.yaml"
    p.write_text(yaml.safe_dump(cfg))
    return p


def test_full_run_writes_all_outputs(tmp_path, monkeypatch):
    db = _build_db([
        ("p/lang-1", "language"),
        ("p/lang-2", "language"),
        ("p/lang-3", "language"),
    ])
    cfg = _make_yaml(tmp_path)
    monkeypatch.setattr(mapper, "ROUTES_JSON_PATH", tmp_path / "routes.json")
    monkeypatch.setattr(mapper, "TRAYCER_EXPORT_PATH", tmp_path / "compact.json")

    routes, skipped = mapper.run(db_path=db, config_path=cfg)

    # G3.4 plan invariant: every config'd category appears in the JSON.
    payload = json.loads((tmp_path / "routes.json").read_text())
    assert set(payload["categories"].keys()) == {"language", "vision"}
    # language has 2 routes (slots=2 even though 3 candidates)
    assert len(payload["categories"]["language"]["routes"]) == 2
    # vision is zero-eligible — no rows have has_vision=1 in the test data
    assert payload["categories"]["vision"]["routes"] == []
    assert payload["categories"]["vision"]["reason"] != ""

    # Pin rows in agent_roles
    conn = sqlite3.connect(db)
    pinned = conn.execute(
        "SELECT role, agent_id, priority FROM agent_roles "
        "WHERE assigned_by='category_route_mapper' "
        "ORDER BY role, priority"
    ).fetchall()
    conn.close()
    assert [(r[0], r[1], r[2]) for r in pinned] == [
        ("openrouter:language", "p/lang-1", 1),
        ("openrouter:language", "p/lang-2", 2),
    ]


def test_rollback_isolation(tmp_path, monkeypatch):
    """G3.5 plan invariant: existing chat-side rows (cheapest-above-floors)
    are NOT touched by the mapper's DELETE."""
    db = _build_db([("p/m", "language")])
    cfg = _make_yaml(tmp_path)
    monkeypatch.setattr(mapper, "ROUTES_JSON_PATH", tmp_path / "routes.json")
    monkeypatch.setattr(mapper, "TRAYCER_EXPORT_PATH", tmp_path / "compact.json")

    # Plant a chat-side row that MUST survive the mapper run.
    conn = sqlite3.connect(db)
    conn.execute(
        "INSERT INTO agent_roles (role, agent_id, priority, assigned_by) "
        "VALUES ('chat-role-foo', 'p/m', 1, 'cheapest-above-floors')"
    )
    conn.commit()
    conn.close()

    mapper.run(db_path=db, config_path=cfg)

    conn = sqlite3.connect(db)
    chat_rows = conn.execute(
        "SELECT count(*) FROM agent_roles WHERE assigned_by='cheapest-above-floors'"
    ).fetchone()[0]
    conn.close()
    assert chat_rows == 1, "Mapper's DELETE touched chat-side rows — rollback isolation broken"


def test_zero_eligible_does_not_crash(tmp_path, monkeypatch):
    """G3.2 plan invariant: zero eligible across all categories must
    exit 0 with empty routes, not raise."""
    # Build DB with NO categories that satisfy floors
    db = _build_db([("low/q", "language")])
    # Bump min_quality_tier to impossible
    cfg_data = yaml.safe_load(_make_yaml(tmp_path).read_text())
    cfg_data["categories"]["language"]["min_quality_tier"] = 99
    cfg_data["categories"]["vision"]["min_quality_tier"] = 99
    p = tmp_path / "impossible.yaml"
    p.write_text(yaml.safe_dump(cfg_data))

    monkeypatch.setattr(mapper, "ROUTES_JSON_PATH", tmp_path / "routes.json")
    monkeypatch.setattr(mapper, "TRAYCER_EXPORT_PATH", tmp_path / "compact.json")
    routes, skipped = mapper.run(db_path=db, config_path=p)

    assert routes == {}
    assert len(skipped) == 2
    # JSON output still contains all 2 categories with empty routes
    payload = json.loads((tmp_path / "routes.json").read_text())
    assert set(payload["categories"].keys()) == {"language", "vision"}
    for cat_data in payload["categories"].values():
        assert cat_data["routes"] == []
        assert cat_data["reason"]


def test_transaction_rollback_on_persist_failure(tmp_path, monkeypatch):
    """Pass B Finding 1: if any INSERT inside the persist loop fails,
    the DELETE-by-day step must roll back so today's history isn't
    silently dropped. Python sqlite3's default isolation_level='' is
    deferred — `conn.commit()` after a failed statement would otherwise
    commit the DELETE alone.

    Reproduce by monkey-patching the INSERT helper to raise mid-loop;
    after the exception, neither agent_roles nor agent_roles_history
    should have lost prior content."""
    db = _build_db([("p/x", "language"), ("p/y", "language")])
    cfg = _make_yaml(tmp_path)
    monkeypatch.setattr(mapper, "ROUTES_JSON_PATH", tmp_path / "routes.json")
    monkeypatch.setattr(mapper, "TRAYCER_EXPORT_PATH", tmp_path / "compact.json")

    # First, populate today's history via a successful run.
    mapper.run(db_path=db, config_path=cfg)
    conn = sqlite3.connect(db)
    pre_pins = conn.execute(
        "SELECT count(*) FROM agent_roles WHERE assigned_by='category_route_mapper'"
    ).fetchone()[0]
    pre_hist = conn.execute(
        "SELECT count(*) FROM agent_roles_history WHERE assigned_by='category_route_mapper'"
    ).fetchone()[0]
    conn.close()
    assert pre_pins > 0
    assert pre_hist > 0

    # Now inject a failure mid-persist: monkeypatch _do_inserts to raise
    # after the first INSERT. The DELETE steps already ran; the
    # try/except wrapper must roll them back so prior content is intact.
    import sqlite3 as _sqlite3
    real_do_inserts = mapper._do_inserts

    def fail_after_first_insert(conn, routes):
        # Run one insert then blow up.
        cur = conn.cursor()
        for category, winners in routes.items():
            if winners:
                w = winners[0]
                cur.execute(
                    "INSERT INTO agent_roles "
                    "(role, agent_id, priority, reason, score_used, score_type, assigned_by) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (f"openrouter:{category}", w["id"], 1, "", w["score_used"],
                     w["score_type"], "category_route_mapper"),
                )
                break
        raise RuntimeError("simulated mid-loop failure")

    monkeypatch.setattr(mapper, "_do_inserts", fail_after_first_insert)

    with pytest.raises(RuntimeError, match="simulated mid-loop failure"):
        mapper.run(db_path=db, config_path=cfg)

    # The rollback should have restored prior counts — failure must
    # not have dropped today's history.
    conn = sqlite3.connect(db)
    post_pins = conn.execute(
        "SELECT count(*) FROM agent_roles WHERE assigned_by='category_route_mapper'"
    ).fetchone()[0]
    post_hist = conn.execute(
        "SELECT count(*) FROM agent_roles_history WHERE assigned_by='category_route_mapper'"
    ).fetchone()[0]
    conn.close()

    assert post_pins == pre_pins, (
        f"Rollback failed — agent_roles dropped from {pre_pins} to {post_pins}"
    )
    assert post_hist == pre_hist, (
        f"Rollback failed — agent_roles_history dropped from {pre_hist} to "
        f"{post_hist} (Pass B Finding 1 regression — DELETE-by-day committed "
        "without matching INSERTs)"
    )

    # Restore for any later test
    monkeypatch.setattr(mapper, "_do_inserts", real_do_inserts)


def test_idempotent(tmp_path, monkeypatch):
    """G3.3: re-running the same day produces the same pin set AND the
    same history-row count (Pass A Finding 2 regression: live schema
    lacks a UNIQUE constraint, so `INSERT OR REPLACE` would silently
    degrade to plain INSERT and double history rows daily)."""
    db = _build_db([("p/x", "language"), ("p/y", "language")])
    cfg = _make_yaml(tmp_path)
    monkeypatch.setattr(mapper, "ROUTES_JSON_PATH", tmp_path / "routes.json")
    monkeypatch.setattr(mapper, "TRAYCER_EXPORT_PATH", tmp_path / "compact.json")

    mapper.run(db_path=db, config_path=cfg)
    payload1 = json.loads((tmp_path / "routes.json").read_text())
    conn = sqlite3.connect(db)
    hist1 = conn.execute(
        "SELECT count(*) FROM agent_roles_history "
        "WHERE assigned_by='category_route_mapper'"
    ).fetchone()[0]
    pins1 = conn.execute(
        "SELECT count(*) FROM agent_roles "
        "WHERE assigned_by='category_route_mapper'"
    ).fetchone()[0]
    conn.close()

    mapper.run(db_path=db, config_path=cfg)
    payload2 = json.loads((tmp_path / "routes.json").read_text())
    conn = sqlite3.connect(db)
    hist2 = conn.execute(
        "SELECT count(*) FROM agent_roles_history "
        "WHERE assigned_by='category_route_mapper'"
    ).fetchone()[0]
    pins2 = conn.execute(
        "SELECT count(*) FROM agent_roles "
        "WHERE assigned_by='category_route_mapper'"
    ).fetchone()[0]
    conn.close()

    # JSON byte-identical (modulo generated_at, which we don't compare).
    assert payload1["categories"] == payload2["categories"]
    # agent_roles: idempotent (DELETE + INSERT every run).
    assert pins2 == pins1, f"agent_roles not idempotent: {pins1} → {pins2}"
    # agent_roles_history: idempotent today (DELETE-by-day + INSERT).
    assert hist2 == hist1, (
        f"agent_roles_history not idempotent: {hist1} → {hist2}. "
        "Pass A Finding 2 regression — the DELETE-by-day step in "
        "_persist_to_agent_roles is broken."
    )
