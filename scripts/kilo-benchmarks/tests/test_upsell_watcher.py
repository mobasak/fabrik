"""Tests for suggest_model's upsell watcher — Phase E of best-model-suggester.

The 💡 Consider signup line must fire ONLY when a locked-out row Pareto-dominates
the accessible frontier by ≥ UPSELL_MIN_SAVING_PCT (30%) and stays within
UPSELL_QUALITY_TOLERANCE_ELO (50) of the accessible best.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _make_llm_db(tmp_path, rows):
    db = tmp_path / "upsell_test.db"
    conn = sqlite3.connect(db)
    conn.executescript(
        """
        CREATE TABLE agents (
            id TEXT PRIMARY KEY, api_id TEXT, name TEXT, provider TEXT,
            service_type TEXT, pricing_unit TEXT, input_cost_per_m REAL,
            output_cost_per_m REAL, quality_elo REAL,
            output_tokens_per_sec REAL, perf_seconds REAL, status TEXT,
            reachable_with_existing_keys INTEGER NOT NULL DEFAULT 0
        );
        """
    )
    for r in rows:
        conn.execute(
            "INSERT INTO agents (id, provider, service_type, pricing_unit, "
            "input_cost_per_m, quality_elo, status, reachable_with_existing_keys) "
            "VALUES (?, ?, ?, ?, ?, ?, 'active', ?)",
            (
                r["id"],
                r["provider"],
                "image_gen",
                "image",
                r["cost"],
                r.get("quality_elo"),
                r["reach"],
            ),
        )
    conn.commit()
    conn.close()
    return db


def test_upsell_prints_when_locked_out_row_beats_accessible_by_30pct(tmp_path, monkeypatch, capsys):
    """Accessible bfl@$3.00; locked-out hyperbolic@$1.50 — 50% cheaper.
    Same quality (both 1400). Expect: 💡 line, exit 0.
    """
    db = _make_llm_db(
        tmp_path,
        [
            {
                "id": "bfl-via-replicate/flux",
                "provider": "bfl-via-replicate",
                "cost": 3.0 * 1_000_000,
                "quality_elo": 1400,
                "reach": 1,
            },
            {
                "id": "hyperbolic/flux-hyper",
                "provider": "hyperbolic",
                "cost": 1.5 * 1_000_000,
                "quality_elo": 1400,
                "reach": 0,
            },
        ],
    )
    monkeypatch.setenv("KILO_DB", str(db))
    from suggest_model import main

    rc = main(["--task", "image_gen", "--volume-images", "1"])
    err = capsys.readouterr().err
    assert rc == 0
    assert "💡 Consider signup:" in err
    assert "hyperbolic" in err.lower()


def test_strict_flag_suppresses_upsell(tmp_path, monkeypatch, capsys):
    db = _make_llm_db(
        tmp_path,
        [
            {
                "id": "bfl-via-replicate/flux",
                "provider": "bfl-via-replicate",
                "cost": 3.0 * 1_000_000,
                "quality_elo": 1400,
                "reach": 1,
            },
            {
                "id": "hyperbolic/flux-hyper",
                "provider": "hyperbolic",
                "cost": 1.5 * 1_000_000,
                "quality_elo": 1400,
                "reach": 0,
            },
        ],
    )
    monkeypatch.setenv("KILO_DB", str(db))
    from suggest_model import main

    rc = main(["--task", "image_gen", "--volume-images", "1", "--strict"])
    err = capsys.readouterr().err
    assert rc == 0
    assert "Consider signup" not in err


def test_upsell_skipped_when_saving_below_threshold(tmp_path, monkeypatch, capsys):
    """Locked-out 20% cheaper — below UPSELL_MIN_SAVING_PCT=0.30. No 💡."""
    db = _make_llm_db(
        tmp_path,
        [
            {
                "id": "bfl-via-replicate/flux",
                "provider": "bfl-via-replicate",
                "cost": 3.0 * 1_000_000,
                "quality_elo": 1400,
                "reach": 1,
            },
            {
                "id": "hyperbolic/flux-hyper",
                "provider": "hyperbolic",
                "cost": 2.4 * 1_000_000,
                "quality_elo": 1400,
                "reach": 0,
            },
        ],
    )
    monkeypatch.setenv("KILO_DB", str(db))
    from suggest_model import main

    rc = main(["--task", "image_gen", "--volume-images", "1"])
    err = capsys.readouterr().err
    assert rc == 0
    assert "Consider signup" not in err
