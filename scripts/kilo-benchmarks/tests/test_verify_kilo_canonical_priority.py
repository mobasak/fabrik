"""Regression guard: verify_openrouter_catalog's Kilo canonical-collision
resolution must pick the priced, prefixed record over stealth/* variants
and bare-id placeholders.

Bug fixed 2026-07-01: Kilo emits up to 3 records per model that
canonicalize to the same target — `anthropic/claude-opus-4.8` ($5/$25),
`stealth/claude-opus-4.8` ($4/$20 beta discount), and `claude-opus-4-8`
(bare, $0/$0 placeholder). Naive last-write-wins let the $0 placeholder
overwrite the real $5/$25 price, which then propagated to the browser's
"Kilo Gateway: free /M in (-100%)" bug.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _make_seed_db(tmp_path: Path) -> Path:
    """Minimal agents-table seed for the two rows the test covers."""
    db = tmp_path / "seed.db"
    conn = sqlite3.connect(db)
    conn.executescript(
        """
        CREATE TABLE agents (
            id TEXT PRIMARY KEY,
            name TEXT, provider TEXT, api_id TEXT,
            input_cost_per_m REAL, output_cost_per_m REAL,
            context_window_k INTEGER, has_vision INTEGER, has_tools INTEGER,
            is_agentic INTEGER, arena_elo INTEGER, task_tier INTEGER,
            perf_per_dollar REAL, status TEXT DEFAULT 'active',
            last_verified TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP, variant TEXT,
            blocked INTEGER DEFAULT 0,
            has_reasoning INTEGER,
            via_openrouter INTEGER DEFAULT 0,
            via_kilo INTEGER DEFAULT 0,
            kilo_input_cost_per_m REAL,
            kilo_output_cost_per_m REAL,
            kilo_family TEXT,
            kilo_provider_id TEXT,
            kilo_cache_read_cost_per_m REAL,
            kilo_cache_write_cost_per_m REAL,
            kilo_release_date TEXT,
            pricing_unit TEXT,
            is_moderated INTEGER DEFAULT 0,
            reasoning_mandatory INTEGER DEFAULT 0
        );
        INSERT INTO agents (id, name, provider, via_kilo, via_openrouter)
        VALUES ('anthropic/claude-opus-4.8', 'Anthropic: Claude Opus 4.8', 'anthropic', 1, 1);
        INSERT INTO agents (id, name, provider, via_kilo, via_openrouter)
        VALUES ('anthropic/claude-fable-5', 'Anthropic: Claude Fable 5', 'anthropic', 1, 1);
        """
    )
    conn.commit()
    conn.close()
    return db


def test_canonical_collision_picks_priced_prefixed_record(tmp_path, monkeypatch):
    """Three Kilo records for claude-opus-4.8:
      - anthropic/claude-opus-4.8   $5/$25   (priced, prefixed → highest priority)
      - stealth/claude-opus-4.8     $4/$20   (priced but stealth → medium)
      - claude-opus-4-8             $0/$0    (bare placeholder → lowest)
    Priority selection must pick the $5/$25 record."""
    import verify_openrouter_catalog as verify_module

    fake_kilo = {
        # Order matters — this mirrors Kilo's actual output where the
        # bare-form placeholder is emitted last (and would win naive
        # last-write-wins).
        "anthropic/claude-opus-4.8": {
            "id": "anthropic/claude-opus-4.8",
            "name": "Anthropic Claude Opus 4.8",
            "family": "claude-opus",
            "providerID": "openrouter",
            "cost": {"input": 5, "output": 25, "cache": {"read": 0.5, "write": 6.25}},
        },
        "stealth/claude-opus-4.8": {
            "id": "stealth/claude-opus-4.8",
            "family": "claude-opus",
            "providerID": "openrouter",
            "cost": {"input": 4, "output": 20, "cache": {"read": 0.4, "write": 5}},
        },
        "claude-opus-4-8": {
            "id": "claude-opus-4-8",
            "family": None,
            "providerID": "openrouter",
            "cost": {"input": 0, "output": 0},
        },
        # And a fable-5 case: only a bare-form Kilo record with the family.
        "claude-fable-5": {
            "id": "claude-fable-5",
            "family": "claude-fable",
            "providerID": "openrouter",
            "cost": {"input": 10, "output": 50, "cache": {"read": 1, "write": 12.5}},
        },
    }

    db_path = _make_seed_db(tmp_path)

    # Patch _fetch_kilo + _fetch_live to return the fake data
    monkeypatch.setattr(V, "_fetch_kilo", lambda: fake_kilo)

    def fake_or():
        # Serve the DB rows with a matching canonical_slug so canonical
        # collision routing is exercised.
        return {
            "anthropic/claude-opus-4.8": {
                "id": "anthropic/claude-opus-4.8",
                "name": "Anthropic: Claude Opus 4.8",
                "description": "test",
                "pricing": {"prompt": "0.000005", "completion": "0.000025"},
                "context_length": 1000000,
                "top_provider": {
                    "context_length": 1000000,
                    "max_completion_tokens": 128000,
                    "is_moderated": False,
                },
                "canonical_slug": "anthropic/claude-4.8-opus-20260528",
                "supported_parameters": ["reasoning", "tools"],
                "architecture": {"input_modalities": ["text", "image"]},
            },
            "anthropic/claude-fable-5": {
                "id": "anthropic/claude-fable-5",
                "name": "Anthropic: Claude Fable 5",
                "description": "test",
                "pricing": {"prompt": "0.00001", "completion": "0.00005"},
                "context_length": 1000000,
                "top_provider": {
                    "context_length": 1000000,
                    "max_completion_tokens": 128000,
                    "is_moderated": False,
                },
                "canonical_slug": "anthropic/claude-fable-5",
                "supported_parameters": ["reasoning"],
                "architecture": {"input_modalities": ["text"]},
            },
        }

    monkeypatch.setattr(V, "_fetch_live", fake_or)

    report = verify_module.verify(db_path)

    # The report must expose the priority-selected record per canonical.
    # Both `kilo_sourced` (pricing) and `kilo_best_record` (raw record for
    # the capabilities pass) must point at the $5/$25 anthropic-prefixed
    # entry — not the $0/$0 bare placeholder or the $4/$20 stealth variant.
    opus_prices = report["kilo_sourced"]["anthropic/claude-opus-4.8"]
    assert opus_prices["input"] == 5, f"expected 5, got {opus_prices['input']!r}"
    assert opus_prices["output"] == 25, f"expected 25, got {opus_prices['output']!r}"

    opus_rec = report["kilo_best_record"]["anthropic/claude-opus-4.8"]
    assert opus_rec["cost"]["input"] == 5
    assert opus_rec["family"] == "claude-opus"

    # Fable case: ONLY a bare-form Kilo record `claude-fable-5` exists.
    # Canonical resolution must route it onto the DB row
    # `anthropic/claude-fable-5` so the capabilities pass writes
    # kilo_family='claude-fable' to the correct row.
    fable_prices = report["kilo_sourced"]["anthropic/claude-fable-5"]
    assert fable_prices["input"] == 10, (
        f"bare-form Kilo record must map to canonical DB row via canonical "
        f"resolution — got kilo_sourced={fable_prices!r}"
    )
    fable_rec = report["kilo_best_record"]["anthropic/claude-fable-5"]
    assert fable_rec["family"] == "claude-fable"
