"""Integration tests for `scripts/kilo-benchmarks/classify_ai_category.py`.

Phase 1 of the OpenRouter routing plan. Covers:

- Idempotency (re-run produces same row counts)
- Defense against orphan rows left by an external script that deleted
  from `agents` without `PRAGMA foreign_keys = ON` (Pass B Finding 3)
- Pass B Finding 5 partial-create check on migration

Tests use temp DBs — never mutate the real `kilo_agents.db`.
"""

from __future__ import annotations

import importlib.util
import sqlite3
import sys
import tempfile
from pathlib import Path

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


migrate = _load("migrate_ai_category_table")
classify = _load("classify_ai_category")


def _seed_db(db_path: Path) -> None:
    """Build a minimal `agents` table + run the migration."""
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE agents (
            id TEXT PRIMARY KEY,
            status TEXT DEFAULT 'active',
            blocked INTEGER DEFAULT 0,
            is_ga INTEGER DEFAULT 1,
            has_vision INTEGER DEFAULT 0,
            has_tools INTEGER DEFAULT 0,
            has_reasoning INTEGER DEFAULT 0,
            is_agentic INTEGER DEFAULT 0,
            context_window_k INTEGER DEFAULT 8,
            weighted_coding REAL,
            humaneval_score REAL,
            coding_score REAL
        )
        """
    )
    conn.executemany(
        "INSERT INTO agents (id, has_vision, context_window_k, coding_score) VALUES (?, ?, ?, ?)",
        [
            ("vendor/lang-only", 0, 8, None),
            ("vendor/vision-model", 1, 8, None),
            ("vendor/long-ctx", 0, 256, None),
            ("vendor/coder-1", 0, 8, 70.0),
            ("vendor/whisper-audio", 0, 8, None),
        ],
    )
    conn.commit()
    conn.close()
    migrate.migrate(db_path)


def test_migration_idempotent():
    """Second run of migrate.migrate() is a no-op."""
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "test.db"
        _seed_db(db_path)
        # First run already ran inside _seed_db
        result = migrate.migrate(db_path)
        assert result["table_created"] == 0
        assert result["index_created"] == 0
        assert result["foreign_keys_enabled"] == 1


def test_classify_idempotent():
    """Re-running classify() produces identical per-category counts."""
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "test.db"
        _seed_db(db_path)
        first = classify.classify(db_path)
        second = classify.classify(db_path)
        assert first == second, f"Idempotency failed: {first} vs {second}"


def test_orphan_cleanup_defense(capfd):
    """Pass B Finding 3: simulate an external script deleting from
    `agents` without PRAGMA on — orphan agent_categories rows accumulate.
    The next classify() run must auto-clean them and log a WARN."""
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "test.db"
        _seed_db(db_path)
        classify.classify(db_path)

        # An external connection deletes from agents WITHOUT PRAGMA on —
        # the CASCADE silently no-ops, leaving orphan agent_categories rows.
        attacker = sqlite3.connect(db_path)
        # NB: no PRAGMA foreign_keys = ON here — that's the whole point
        attacker.execute("DELETE FROM agents WHERE id = 'vendor/coder-1'")
        attacker.commit()
        orphan_count = attacker.execute(
            "SELECT count(*) FROM agent_categories WHERE agent_id = 'vendor/coder-1'"
        ).fetchone()[0]
        attacker.close()
        # Sanity: confirm we successfully created the orphan condition
        assert orphan_count > 0, "Test setup failed — CASCADE may have fired unexpectedly"

        # Now re-run classifier — it must clean orphans + log a WARN
        classify.classify(db_path)
        out, _ = capfd.readouterr()
        assert "deleted" in out and "orphan" in out, f"Expected orphan-cleanup WARN, got: {out!r}"

        # And the orphan rows must be gone
        check = sqlite3.connect(db_path)
        remaining = check.execute(
            "SELECT count(*) FROM agent_categories WHERE agent_id = 'vendor/coder-1'"
        ).fetchone()[0]
        check.close()
        assert remaining == 0, f"Orphan cleanup failed — still {remaining} rows"


def test_no_language_code_like_overlap():
    """G1.5 plan invariant: 0 language rows whose id matches LIKE
    `%code%` or `%coder%`."""
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "test.db"
        _seed_db(db_path)
        classify.classify(db_path)
        conn = sqlite3.connect(db_path)
        overlap = conn.execute(
            "SELECT count(*) FROM agent_categories WHERE category='language' "
            "AND agent_id IN (SELECT id FROM agents WHERE id LIKE '%code%' "
            "OR id LIKE '%coder%')"
        ).fetchone()[0]
        conn.close()
        assert overlap == 0, f"LIKE-rule overlap detected: {overlap} rows"
