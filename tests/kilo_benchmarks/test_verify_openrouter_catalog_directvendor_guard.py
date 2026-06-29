"""Regression test for the via_openrouter=1 filter in verify_openrouter_catalog.py.

Background: convergence Pass 6 caught a long-standing bug at
`scripts/kilo-benchmarks/verify_openrouter_catalog.py:192` — the SELECT that
loads candidate rows for "did it vanish from OpenRouter's live catalog?" check
lacked an `AND via_openrouter=1` filter. As a result, direct-vendor rows
(via_openrouter=0) — Soniox, ElevenLabs, AssemblyAI, Coqui, etc. — were swept
into `delisted[]` and flipped to `status='deprecated'` on every daily run, even
though they were never on OpenRouter to begin with.

This test pins the filter in place so a future refactor doesn't silently
re-introduce the bug. We construct a tiny in-memory DB with two rows:
  - one OpenRouter-routed row that IS in the live catalog (should stay active)
  - one direct-vendor row that is NOT in the live catalog (must NOT be deprecated)

Then we call the verifier's `verify()` function and assert that the
direct-vendor row is NOT in `report["delisted"]`.

See docs/development/plans/2026-06-29-plan-direct-vendor-pricing.md (Phase 1
first sub-task).
"""

from __future__ import annotations

import importlib.util
import sqlite3
import sys
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = REPO_ROOT / "scripts" / "kilo-benchmarks"

if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPT_DIR / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _seed_minimal_db(db_path: Path) -> None:
    """Create just enough of `agents` for verify() to run."""
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(
            """
            CREATE TABLE agents (
                id TEXT PRIMARY KEY,
                name TEXT,
                provider TEXT,
                service_type TEXT,
                status TEXT NOT NULL DEFAULT 'active',
                via_openrouter INTEGER NOT NULL DEFAULT 0,
                via_kilo INTEGER NOT NULL DEFAULT 0,
                input_cost_per_m REAL,
                output_cost_per_m REAL,
                pricing_unit TEXT,
                context_window_k INTEGER,
                kind TEXT NOT NULL DEFAULT 'chat',
                is_ga INTEGER NOT NULL DEFAULT 1,
                last_verified TEXT,
                discard_reason TEXT
            );
            INSERT INTO agents (id, provider, service_type, status, via_openrouter, via_kilo)
                VALUES ('soniox/tts', 'soniox', 'tts', 'active', 0, 0);
            INSERT INTO agents (id, provider, service_type, status, via_openrouter, via_kilo)
                VALUES ('openai/gpt-4o', 'openai', 'llm', 'active', 1, 0);
            """
        )
        conn.commit()
    finally:
        conn.close()


def test_directvendor_rows_excluded_from_delisted(tmp_path: Path) -> None:
    """The bug: verify() loaded ALL active rows, so direct-vendor rows that
    aren't in OpenRouter's catalog got added to `delisted[]` and deprecated."""
    db_path = tmp_path / "kilo_agents.db"
    _seed_minimal_db(db_path)

    verify_module = _load("verify_openrouter_catalog")

    # Mock the live catalog fetchers so the test doesn't hit the network.
    # Live catalog contains the OpenRouter row but NOT the direct-vendor row.
    fake_live = {
        "openai/gpt-4o": {
            "id": "openai/gpt-4o",
            "name": "GPT-4o",
            "pricing": {"prompt": "0.0000025", "completion": "0.00001"},
            "context_length": 128_000,
        }
    }
    fake_kilo = {"openai/gpt-4o": {"id": "openai/gpt-4o", "cost": {"input": 2.5, "output": 10.0}}}

    with (
        patch.object(verify_module, "_fetch_live", return_value=fake_live),
        patch.object(verify_module, "_fetch_kilo", return_value=fake_kilo),
    ):
        report = verify_module.verify(db_path=db_path)

    # The bug regression: soniox/tts (via_openrouter=0) MUST NOT be in delisted.
    assert "soniox/tts" not in report["delisted"], (
        "Direct-vendor row (via_openrouter=0) was added to delisted[] — "
        "the verifier's SELECT filter has regressed. Check "
        "verify_openrouter_catalog.py line ~192."
    )


def test_openrouter_row_correctly_kept_active(tmp_path: Path) -> None:
    """Sanity: an OpenRouter-routed row that's still in the live catalog must
    not be added to delisted[] either."""
    db_path = tmp_path / "kilo_agents.db"
    _seed_minimal_db(db_path)

    verify_module = _load("verify_openrouter_catalog")
    fake_live = {
        "openai/gpt-4o": {
            "id": "openai/gpt-4o",
            "name": "GPT-4o",
            "pricing": {"prompt": "0.0000025", "completion": "0.00001"},
            "context_length": 128_000,
        }
    }
    fake_kilo = {"openai/gpt-4o": {"id": "openai/gpt-4o", "cost": {"input": 2.5, "output": 10.0}}}

    with (
        patch.object(verify_module, "_fetch_live", return_value=fake_live),
        patch.object(verify_module, "_fetch_kilo", return_value=fake_kilo),
    ):
        report = verify_module.verify(db_path=db_path)

    assert "openai/gpt-4o" not in report["delisted"]


def test_openrouter_row_that_vanished_does_get_delisted(tmp_path: Path) -> None:
    """Sanity in the other direction: an OpenRouter-routed row that IS NO
    LONGER in the live catalog must still be added to delisted[] — the bug
    fix preserves the verifier's intended behavior for actual OpenRouter
    delisting events."""
    db_path = tmp_path / "kilo_agents.db"
    _seed_minimal_db(db_path)

    verify_module = _load("verify_openrouter_catalog")
    # Live catalog is empty — both rows should be evaluated, but only the
    # openai/gpt-4o row (via_openrouter=1) should land in delisted[].
    # soniox/tts (via_openrouter=0) is excluded by the SELECT filter so it
    # never gets compared in the first place.
    fake_live: dict = {}
    fake_kilo: dict = {}

    with (
        patch.object(verify_module, "_fetch_live", return_value=fake_live),
        patch.object(verify_module, "_fetch_kilo", return_value=fake_kilo),
    ):
        report = verify_module.verify(db_path=db_path)

    assert "openai/gpt-4o" in report["delisted"], (
        "OpenRouter row that vanished from the live catalog should still be "
        "added to delisted[]. The bug fix shouldn't have over-corrected."
    )
    assert "soniox/tts" not in report["delisted"]
