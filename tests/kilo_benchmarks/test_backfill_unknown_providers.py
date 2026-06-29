"""Regression tests for backfill_unknown_providers.py (Phase 4)."""

from __future__ import annotations

import importlib.util
import sqlite3
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = REPO_ROOT / "scripts" / "kilo-benchmarks"

if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))


def _load():
    spec = importlib.util.spec_from_file_location(
        "backfill_unknown_providers", SCRIPT_DIR / "backfill_unknown_providers.py"
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_infer_provider_claude_family() -> None:
    mod = _load()
    assert mod.infer_provider("claude-opus-4-7") == "anthropic"
    assert mod.infer_provider("claude-haiku-4-5") == "anthropic"
    assert mod.infer_provider("claude-fable-5") == "anthropic"


def test_infer_provider_colon_form() -> None:
    mod = _load()
    assert mod.infer_provider("corethink:free") == "corethink"
    assert mod.infer_provider("vendor:paid") == "vendor"


def test_infer_provider_slash_form() -> None:
    mod = _load()
    assert mod.infer_provider("openai/gpt-4o") == "openai"
    assert mod.infer_provider("anthropic/claude-3.5-sonnet") == "anthropic"


def test_infer_provider_unrecognized() -> None:
    mod = _load()
    assert mod.infer_provider("") is None
    assert mod.infer_provider(None) is None
    assert mod.infer_provider("just-some-string") is None


def _seed(db_path: Path) -> None:
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE agents (
            id TEXT PRIMARY KEY,
            provider TEXT,
            service_type TEXT,
            status TEXT NOT NULL DEFAULT 'active'
        );
        INSERT INTO agents (id, provider, service_type) VALUES
            ('claude-opus-4-7', 'unknown', 'llm'),
            ('corethink:free',  'unknown', 'llm'),
            ('openai/gpt-4o',   'unknown', 'llm'),
            ('mystery-name',    'unknown', 'llm'),
            ('already/correct', 'openai',  'llm');
        """
    )
    conn.commit()
    conn.close()


def test_dry_run_does_not_write(tmp_path: Path) -> None:
    db = tmp_path / "k.db"
    _seed(db)
    mod = _load()
    result = mod.run(db, apply=False)
    assert result["matched"] == 3   # claude-opus-4-7, corethink:free, openai/gpt-4o
    assert result["updated"] == 0
    assert result["unmappable"] == 1
    # DB unchanged
    conn = sqlite3.connect(db)
    providers = dict(conn.execute("SELECT id, provider FROM agents").fetchall())
    conn.close()
    assert providers["claude-opus-4-7"] == "unknown"


def test_apply_writes_inferred_providers(tmp_path: Path) -> None:
    db = tmp_path / "k.db"
    _seed(db)
    mod = _load()
    result = mod.run(db, apply=True)
    assert result["updated"] == 3
    conn = sqlite3.connect(db)
    providers = dict(conn.execute("SELECT id, provider FROM agents").fetchall())
    conn.close()
    assert providers["claude-opus-4-7"] == "anthropic"
    assert providers["corethink:free"] == "corethink"
    assert providers["openai/gpt-4o"] == "openai"
    assert providers["mystery-name"] == "unknown"  # unmappable
    assert providers["already/correct"] == "openai"  # untouched (provider != 'unknown')


def test_idempotent_second_run(tmp_path: Path) -> None:
    db = tmp_path / "k.db"
    _seed(db)
    mod = _load()
    mod.run(db, apply=True)
    # Second run should be a no-op
    result = mod.run(db, apply=True)
    assert result["matched"] == 0
    assert result["updated"] == 0
