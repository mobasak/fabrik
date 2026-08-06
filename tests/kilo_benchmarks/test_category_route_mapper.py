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
    db = _build_db(
        [
            ("p/lang-1", "language"),
            ("p/lang-2", "language"),
            ("p/lang-3", "language"),
        ]
    )
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
    real_do_inserts = mapper._do_inserts

    def fail_after_first_insert(conn, routes, today_iso):
        # Run one insert then blow up.
        cur = conn.cursor()
        for category, winners in routes.items():
            if winners:
                w = winners[0]
                cur.execute(
                    "INSERT INTO agent_roles "
                    "(role, agent_id, priority, reason, score_used, score_type, assigned_by) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        f"openrouter:{category}",
                        w["id"],
                        1,
                        "",
                        w["score_used"],
                        w["score_type"],
                        "category_route_mapper",
                    ),
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
        "SELECT count(*) FROM agent_roles_history WHERE assigned_by='category_route_mapper'"
    ).fetchone()[0]
    pins1 = conn.execute(
        "SELECT count(*) FROM agent_roles WHERE assigned_by='category_route_mapper'"
    ).fetchone()[0]
    conn.close()

    mapper.run(db_path=db, config_path=cfg)
    payload2 = json.loads((tmp_path / "routes.json").read_text())
    conn = sqlite3.connect(db)
    hist2 = conn.execute(
        "SELECT count(*) FROM agent_roles_history WHERE assigned_by='category_route_mapper'"
    ).fetchone()[0]
    pins2 = conn.execute(
        "SELECT count(*) FROM agent_roles WHERE assigned_by='category_route_mapper'"
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


def test_full_surface_pass1_f1_does_not_clobber_production_paths(tmp_path, monkeypatch):
    """Full-surface Pass 1 F1: ad-hoc caller passing only db_path=X used
    to silently overwrite the module-level production JSON paths.
    `run()` now accepts `routes_json_path` + `traycer_export_path`
    keyword args; an explicit pass routes the writes to those paths
    instead of the production defaults."""
    db = _build_db([("p/x", "language")])
    cfg = _make_yaml(tmp_path)

    # Pin sentinel paths the test owns.
    routes_dst = tmp_path / "my_routes.json"
    traycer_dst = tmp_path / "my_traycer.json"

    # Track writes to the module-level defaults — they MUST NOT be
    # touched when the caller passes explicit paths.
    prod_writes: list[str] = []
    real_write = type(routes_dst).write_text

    def tracking_write(self, *a, **kw):
        if self == mapper.ROUTES_JSON_PATH or self == mapper.TRAYCER_EXPORT_PATH:
            prod_writes.append(str(self))
        return real_write(self, *a, **kw)

    monkeypatch.setattr(type(routes_dst), "write_text", tracking_write)

    mapper.run(
        db_path=db,
        config_path=cfg,
        routes_json_path=routes_dst,
        traycer_export_path=traycer_dst,
    )

    assert routes_dst.exists(), "explicit routes_json_path was not written"
    assert traycer_dst.exists(), "explicit traycer_export_path was not written"
    assert prod_writes == [], f"production paths clobbered despite explicit override: {prod_writes}"


def test_full_surface_pass1_f3_today_bound_once(tmp_path, monkeypatch):
    """Full-surface Pass 1 F3: SQLite's DATE('now') was evaluated
    per-statement, so a cross-midnight UTC transaction could DELETE
    day N rows and INSERT day N+1 rows in the same BEGIN…COMMIT block.
    The fix passes a Python-computed today_iso to BOTH the DELETE and
    the INSERTs as a bound parameter — a snapshot, not a live clock."""
    db = _build_db([("p/x", "language")])
    cfg = _make_yaml(tmp_path)
    routes_dst = tmp_path / "routes.json"
    traycer_dst = tmp_path / "compact.json"

    # Simulate the writer's pre-midnight slice by replacing _utc_today_iso
    # to return a frozen date; verify both the DELETE and the INSERTs
    # use THAT exact date, not whatever SQLite's wall clock thinks.
    FROZEN = "2099-12-31"
    monkeypatch.setattr(mapper, "_utc_today_iso", lambda: FROZEN)

    mapper.run(
        db_path=db,
        config_path=cfg,
        routes_json_path=routes_dst,
        traycer_export_path=traycer_dst,
    )

    conn = sqlite3.connect(db)
    rows = conn.execute(
        "SELECT DISTINCT DATE(assigned_at) FROM agent_roles_history "
        "WHERE assigned_by='category_route_mapper'"
    ).fetchall()
    conn.close()
    assert rows == [(FROZEN,)], (
        f"agent_roles_history assigned_at must be the frozen today "
        f"({FROZEN!r}), not SQLite's DATE('now'). Got: {rows}"
    )


def test_full_surface_pass5_f1_pragma_failure_closes_connection(tmp_path, monkeypatch):
    """Pass 5 F1: `conn.execute('PRAGMA foreign_keys = ON')` used to run
    BEFORE the try/finally that closes the connection. If PRAGMA raised
    (corrupt DB, locked file), the connection leaked until Python GC
    reclaimed it. The PRAGMA call is now inside the try block."""
    db = _build_db([("p/x", "language")])
    cfg = _make_yaml(tmp_path)

    # Track connections opened by the mapper.
    real_connect = sqlite3.connect
    closed_calls: list[bool] = []

    class TrackedConn:
        def __init__(self, real):
            self.real = real
            self.fail_pragma = True

        def execute(self, *a, **k):
            if self.fail_pragma and isinstance(a[0], str) and "PRAGMA" in a[0]:
                self.fail_pragma = False
                raise sqlite3.OperationalError("simulated PRAGMA failure")
            return self.real.execute(*a, **k)

        def close(self):
            closed_calls.append(True)
            return self.real.close()

        def __getattr__(self, n):
            return getattr(self.real, n)

    target_db = str(db)

    def tracing_connect(path, *a, **k):
        real = real_connect(path, *a, **k)
        if str(path) == target_db:
            return TrackedConn(real)
        return real

    monkeypatch.setattr(mapper.sqlite3, "connect", tracing_connect)

    with pytest.raises(sqlite3.OperationalError, match="simulated"):
        mapper.run(
            db_path=db,
            config_path=cfg,
            routes_json_path=tmp_path / "r.json",
            traycer_export_path=tmp_path / "t.json",
        )
    assert closed_calls == [True], "PRAGMA failure leaked the connection — close() was not called"


def test_full_surface_pass5_f3_atomic_json_write(tmp_path):
    """Pass 5 F3: previously the DB committed BEFORE the JSON files
    were written, so a PermissionError on the traycer write left the DB
    with today's openrouter:* pins while the JSON files disagreed
    (split-brain). Now both JSON files are rendered to *.tmp first, the
    DB transaction commits, and only then os.replace() promotes them —
    OR the whole thing rolls back atomically."""
    import os as _os

    db = _build_db([("p/x", "language")])
    cfg = _make_yaml(tmp_path)
    routes_json = tmp_path / "routes.json"

    # Read-only directory for the traycer export → write must fail.
    ro_dir = tmp_path / "readonly"
    ro_dir.mkdir()
    _os.chmod(ro_dir, 0o555)
    traycer = ro_dir / "compact.json"

    try:
        with pytest.raises(PermissionError):
            mapper.run(
                db_path=db,
                config_path=cfg,
                routes_json_path=routes_json,
                traycer_export_path=traycer,
            )
        conn = sqlite3.connect(db)
        pin_count = conn.execute(
            "SELECT count(*) FROM agent_roles WHERE assigned_by='category_route_mapper'"
        ).fetchone()[0]
        hist_count = conn.execute(
            "SELECT count(*) FROM agent_roles_history WHERE assigned_by='category_route_mapper'"
        ).fetchone()[0]
        conn.close()
        # DB must NOT have today's pins (transaction rolled back on JSON failure).
        assert pin_count == 0, f"split-brain: DB has {pin_count} pins but traycer JSON write failed"
        assert hist_count == 0, (
            f"split-brain: DB has {hist_count} history rows but traycer JSON write failed"
        )
        # routes.json must NOT have been promoted to its final position.
        assert not routes_json.exists(), (
            "split-brain: routes.json landed at final path despite traycer-write failure"
        )
        # No *.tmp files left lying around.
        leftovers = list(tmp_path.glob("*.tmp"))
        assert leftovers == [], f"orphan tmp files left behind: {leftovers}"
    finally:
        _os.chmod(ro_dir, 0o755)


def test_full_surface_pass6_fb_atomic_promote_or_restore(tmp_path, monkeypatch):
    """Pass 6 F-B: the Pass 5 F3 fix kept the two-promote sequence as
    two consecutive `os.replace` calls — if the SECOND failed (cross-
    device, EACCES, ENOSPC), routes.json showed today while traycer.json
    still showed yesterday — the precise split-brain F3 was meant to
    eliminate. Now we snapshot both final paths to .bak before replacing,
    and restore on any replace failure so the end-state is always
    coherent (either both today or both yesterday)."""
    db = _build_db([("p/x", "language")])
    cfg = _make_yaml(tmp_path)
    routes_final = tmp_path / "routes.json"
    traycer_final = tmp_path / "compact.json"

    # Plant yesterday's content in both consumer-facing paths.
    routes_final.write_text('{"DAY": "yesterday"}')
    traycer_final.write_text('{"DAY": "yesterday"}')

    # Make os.replace fail on the SECOND call (the one that promotes
    # traycer.json). It must be the same module that the mapper imports.
    real_replace = mapper.os.replace
    seen = {"n": 0}

    def failing_replace(src, dst):
        seen["n"] += 1
        if seen["n"] == 3:  # the 2 snapshot replaces succeed; the FIRST promote ok, SECOND fails
            raise OSError("simulated promote failure")
        return real_replace(src, dst)

    # snapshot #1: routes_final → routes_final.bak  (seen=1)
    # snapshot #2: traycer_final → traycer_final.bak (seen=2)
    # promote  #1: routes_tmp → routes_final         (seen=3) ← FAILS
    monkeypatch.setattr(mapper.os, "replace", failing_replace)

    with pytest.raises(OSError, match="simulated promote failure"):
        mapper.run(
            db_path=db,
            config_path=cfg,
            routes_json_path=routes_final,
            traycer_export_path=traycer_final,
        )

    # End-state must be coherent: BOTH yesterday (snapshots restored)
    # OR both today (impossible here since we forced failure). NOT split.
    routes_day = json.loads(routes_final.read_text()).get("DAY")
    traycer_day = json.loads(traycer_final.read_text()).get("DAY")
    assert routes_day == traycer_day, (
        f"split-brain: routes={routes_day!r} traycer={traycer_day!r} — Pass 6 F-B regression"
    )
    assert routes_day == "yesterday", f"snapshots did not restore — routes shows {routes_day!r}"
    # No tmp / bak files left lying around.
    leftovers = [p.name for p in tmp_path.iterdir() if p.suffix in (".tmp", ".bak")]
    assert leftovers == [], f"orphan tmp/bak files: {leftovers}"


def test_full_surface_pass7_f1_promote_failure_rolls_back_db(tmp_path, monkeypatch):
    """Pass 7 F1: even after Pass 5 F3 + Pass 6 F-B, the DB committed
    BEFORE the promote ran. A promote failure left the JSON snapshots
    restored to yesterday while the DB held today's openrouter:* pins —
    consumers reading the DB saw today, consumers reading the JSON saw
    yesterday. Now the commit happens AFTER promote succeeds; a promote
    failure rolls back the DB so both stores end on yesterday."""
    db = _build_db([("p/x", "language")])
    cfg = _make_yaml(tmp_path)
    routes_final = tmp_path / "routes.json"
    traycer_final = tmp_path / "compact.json"

    # Plant yesterday's state in BOTH the DB and the JSON files so the
    # restored state is identifiable.
    routes_final.write_text('{"DAY": "yesterday"}')
    traycer_final.write_text('{"DAY": "yesterday"}')
    conn = sqlite3.connect(db)
    conn.execute(
        "INSERT INTO agent_roles (role, agent_id, priority, score_used, score_type, assigned_by) "
        "VALUES ('openrouter:language', 'YESTERDAY/M', 1, 0.0, 'input_cost_per_m', 'category_route_mapper')"
    )
    conn.commit()
    conn.close()

    real_replace = mapper.os.replace
    seen = {"n": 0}

    def failing_replace(src, dst):
        seen["n"] += 1
        if seen["n"] == 3:  # snapshot1 ok, snapshot2 ok, promote#1 FAILS
            raise OSError("simulated promote failure")
        return real_replace(src, dst)

    monkeypatch.setattr(mapper.os, "replace", failing_replace)

    with pytest.raises(OSError, match="simulated promote failure"):
        mapper.run(
            db_path=db,
            config_path=cfg,
            routes_json_path=routes_final,
            traycer_export_path=traycer_final,
        )

    # JSON snapshots should be back at yesterday.
    assert json.loads(routes_final.read_text())["DAY"] == "yesterday"
    assert json.loads(traycer_final.read_text())["DAY"] == "yesterday"

    # DB must be back at yesterday too — the YESTERDAY/M pin must still
    # be present (transaction rolled back rather than committed).
    conn = sqlite3.connect(db)
    rows = conn.execute(
        "SELECT agent_id FROM agent_roles "
        "WHERE assigned_by='category_route_mapper' AND role='openrouter:language'"
    ).fetchall()
    conn.close()
    assert rows == [("YESTERDAY/M",)], (
        f"DB↔JSON split-brain: JSON shows yesterday but DB shows {rows} — Pass 7 F1 regression"
    )


def test_full_surface_pass8_f1_commit_failure_restores_json(tmp_path, monkeypatch):
    """Pass 8 F1: Pass 7 swapped the split-brain direction — when
    conn.commit() failed AFTER a successful promote, JSON sat on today
    while DB rolled back to yesterday. Now .bak snapshots are kept
    alive across the commit; a commit failure restores the JSON to
    yesterday so both stores end coherent."""
    db = _build_db([("p/x", "language")])
    cfg = _make_yaml(tmp_path)
    routes_final = tmp_path / "routes.json"
    traycer_final = tmp_path / "compact.json"

    # Plant yesterday's state in JSON files AND the DB.
    routes_final.write_text('{"DAY": "yesterday"}')
    traycer_final.write_text('{"DAY": "yesterday"}')
    conn = sqlite3.connect(db)
    conn.execute(
        "INSERT INTO agent_roles (role, agent_id, priority, score_used, score_type, assigned_by) "
        "VALUES ('openrouter:language', 'YESTERDAY/M', 1, 0.0, 'input_cost_per_m', 'category_route_mapper')"
    )
    conn.commit()
    conn.close()

    # Wrap the mapper's connect so the FIRST connection (selector's read)
    # works fine, but the SECOND connection (mapper's write) has its
    # commit() raise.
    real_connect = mapper.sqlite3.connect
    write_conn_box: dict[str, object] = {}

    class FailingCommitConn:
        def __init__(self, r):
            self.r = r

        def commit(self):
            raise sqlite3.OperationalError("simulated commit failure")

        def __getattr__(self, n):
            return getattr(self.r, n)

    target = str(db)
    seen_writes = {"n": 0}

    def trace(p, *a, **k):
        c = real_connect(p, *a, **k)
        if str(p) == target:
            seen_writes["n"] += 1
            if seen_writes["n"] >= 2:  # selector reads first; mapper writes second
                wrap = FailingCommitConn(c)
                write_conn_box["c"] = wrap
                return wrap
        return c

    monkeypatch.setattr(mapper.sqlite3, "connect", trace)

    with pytest.raises(sqlite3.OperationalError, match="simulated commit failure"):
        mapper.run(
            db_path=db,
            config_path=cfg,
            routes_json_path=routes_final,
            traycer_export_path=traycer_final,
        )

    # JSON snapshots restored to yesterday.
    assert json.loads(routes_final.read_text())["DAY"] == "yesterday", (
        "split-brain: routes JSON not restored after commit failure"
    )
    assert json.loads(traycer_final.read_text())["DAY"] == "yesterday", (
        "split-brain: traycer JSON not restored after commit failure"
    )

    # DB rollback effectively occurred (selector check via fresh connection).
    conn = sqlite3.connect(db)
    rows = conn.execute(
        "SELECT agent_id FROM agent_roles WHERE role='openrouter:language'"
    ).fetchall()
    conn.close()
    assert rows == [("YESTERDAY/M",)], f"DB↔JSON split-brain: expected yesterday in DB, got {rows}"
    # No orphan .tmp or .bak files.
    leftovers = sorted(p.name for p in tmp_path.iterdir() if p.suffix in (".tmp", ".bak"))
    assert leftovers == [], f"orphans: {leftovers}"


def test_full_surface_pass9_snapshot_failure_restores_first(tmp_path, monkeypatch):
    """Pass 9: the snapshot pair used to live OUTSIDE the try/restore
    block — failure of the SECOND snapshot left routes_final missing
    (moved to routes_bak by the first) while traycer_final still showed
    yesterday → split-brain regression of Pass 6 F-B. Both snapshot
    AND promote now share the same try/restore."""
    db = _build_db([("p/x", "language")])
    cfg = _make_yaml(tmp_path)
    routes_final = tmp_path / "routes.json"
    traycer_final = tmp_path / "compact.json"
    routes_final.write_text('{"DAY": "yesterday"}')
    traycer_final.write_text('{"DAY": "yesterday"}')

    real_replace = mapper.os.replace
    seen = {"n": 0}

    def failing_replace(src, dst):
        seen["n"] += 1
        # n=1 routes_final → routes_bak (OK)
        # n=2 traycer_final → traycer_bak (FAIL)
        if seen["n"] == 2:
            raise OSError("simulated snapshot #2 failure")
        return real_replace(src, dst)

    monkeypatch.setattr(mapper.os, "replace", failing_replace)

    with pytest.raises(OSError, match="simulated snapshot #2"):
        mapper.run(
            db_path=db,
            config_path=cfg,
            routes_json_path=routes_final,
            traycer_export_path=traycer_final,
        )

    # routes_final must be restored (not missing because snapshot #1
    # already moved it to .bak before snapshot #2 failed).
    assert routes_final.exists(), "split-brain: routes.json missing after snapshot failure"
    assert json.loads(routes_final.read_text())["DAY"] == "yesterday"
    assert json.loads(traycer_final.read_text())["DAY"] == "yesterday"
    leftovers = sorted(p.name for p in tmp_path.iterdir() if p.suffix in (".tmp", ".bak"))
    assert leftovers == [], f"orphans: {leftovers}"
