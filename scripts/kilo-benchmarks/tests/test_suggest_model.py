"""Tests for suggest_model.py — Phase B of best-model-suggester.

Highest-risk paths:
- Empty pool → exit 1 (never extrapolate from thin air).
- Missing --volume-<unit> flag → exit 2 (unambiguous error).
- Mixed pricing_unit across one service_type (image_gen has per-image AND M-tokens
  rows) → normalize before comparing.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _make_db(tmp_path: Path, seeds: list[dict]) -> Path:
    db = tmp_path / "kilo_test.db"
    conn = sqlite3.connect(db)
    conn.executescript(
        """
        CREATE TABLE agents (
            id TEXT PRIMARY KEY,
            api_id TEXT,
            name TEXT,
            provider TEXT,
            service_type TEXT,
            pricing_unit TEXT,
            input_cost_per_m REAL,
            output_cost_per_m REAL,
            quality_elo REAL,
            output_tokens_per_sec REAL,
            perf_seconds REAL,
            status TEXT,
            reachable_with_existing_keys INTEGER NOT NULL DEFAULT 0
        );
        """
    )
    for row in seeds:
        conn.execute(
            "INSERT INTO agents (id, provider, service_type, pricing_unit, "
            "input_cost_per_m, quality_elo, status, reachable_with_existing_keys) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                row["id"],
                row["provider"],
                row["service_type"],
                row.get("pricing_unit", "M-tokens"),
                row.get("input_cost_per_m", 0.0),
                row.get("quality_elo"),
                row.get("status", "active"),
                row.get("reachable_with_existing_keys", 1),
            ),
        )
    conn.commit()
    conn.close()
    return db


def test_empty_pool_exits_1(tmp_path, monkeypatch, capsys):
    db = _make_db(tmp_path, [])
    monkeypatch.setenv("KILO_DB", str(db))
    from suggest_model import main

    rc = main(["--task", "video_gen", "--volume-images", "100"])
    out = capsys.readouterr()
    assert rc == 1
    assert "NO DATA for task=video_gen" in (out.out + out.err)


def test_missing_volume_flag_exits_2(tmp_path, monkeypatch, capsys):
    db = _make_db(
        tmp_path,
        [{"id": "elevenlabs/tts", "provider": "elevenlabs", "service_type": "tts",
          "pricing_unit": "M-chars", "input_cost_per_m": 15.0}],
    )
    monkeypatch.setenv("KILO_DB", str(db))
    from suggest_model import main

    rc = main(["--task", "tts"])  # no --volume-chars
    out = capsys.readouterr()
    assert rc == 2
    assert "--volume-chars required" in (out.err + out.out)


def test_mixed_pricing_unit_normalizes_across_image_gen(tmp_path, monkeypatch):
    """flux-schnell per-image=$0.003 → $3.00/1000; gemini-3.1-flash-image
    M-tokens=$0.5 × 1290 tok/img / 1e6 → $0.000645/img → $0.645/1000.
    Kwarg name is `images=` (matches volume.get('images', 0)). A regression using
    `volume_images=` would silently cost $0.00.
    """
    # Give flux-schnell a higher quality_elo so Pareto doesn't drop it
    # (gemini is cheaper; without this, flux-schnell would be dominated).
    # Test asserts on cost normalization, not on the Pareto filter.
    db = _make_db(
        tmp_path,
        [
            {"id": "bfl-via-replicate/flux-schnell", "provider": "bfl-via-replicate",
             "service_type": "image_gen", "pricing_unit": "image",
             "input_cost_per_m": 0.003 * 1_000_000, "quality_elo": 1400},
            {"id": "google/gemini-3.1-flash-image", "provider": "google",
             "service_type": "image_gen", "pricing_unit": "M-tokens",
             "input_cost_per_m": 0.5, "quality_elo": 1230},
        ],
    )
    monkeypatch.setenv("KILO_DB", str(db))
    from suggest_model import _rank_service_type

    conn = sqlite3.connect(db)
    rows = _rank_service_type(conn, "image_gen", images=1000)
    schnell = next(r for r in rows if "flux-schnell" in r["id"])
    gemini = next(r for r in rows if "gemini-3.1-flash-image" in r["id"])
    assert abs(schnell["cost_usd"] - 3.00) < 0.01
    assert abs(gemini["cost_usd"] - 0.645) < 0.01
    conn.close()
