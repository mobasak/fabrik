"""Tests for the 4 per-task rankers — Phase B.5.

Each ranker is a thin wrapper: query DB via _rank_service_type, render markdown,
atomic-write to the docs path. Test coverage: each ranker emits a header, a
table with at least one row (or the no-rows fallback), and mentions the model
IDs it queried.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _seed_2_rows(tmp_path: Path, service_type: str, ids: list[str], unit: str,
                 cost: float) -> Path:
    db = tmp_path / f"{service_type}_test.db"
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
    for i, mid in enumerate(ids):
        conn.execute(
            "INSERT INTO agents (id, provider, service_type, pricing_unit, "
            "input_cost_per_m, quality_elo, status, reachable_with_existing_keys) "
            "VALUES (?, ?, ?, ?, ?, ?, 'active', 1)",
            (mid, mid.split("/")[0], service_type, unit, cost * (i + 1), 1400 - i * 10),
        )
    conn.commit()
    conn.close()
    return db


@pytest.mark.parametrize(
    "module_name, service_type, unit, cost, ids",
    [
        ("rank_tts", "tts", "M-chars", 15.0, ["elevenlabs/turbo", "openai/tts-hd"]),
        ("rank_stt", "stt", "audio-min", 0.0043, ["deepgram/nova", "openai/whisper"]),
        ("rank_translation", "translation", "M-chars", 20.0,
         ["deepl/free", "qwen/qwen-mt-turbo"]),
        ("rank_image_gen", "image_gen", "image", 3000.0,
         ["bfl/flux-schnell", "stability/sdxl"]),
    ],
)
def test_rank_specialty_emits_valid_markdown(
    tmp_path, monkeypatch, module_name, service_type, unit, cost, ids
):
    db = _seed_2_rows(tmp_path, service_type, ids, unit, cost)
    out = tmp_path / f"{service_type}.md"
    monkeypatch.setenv("KILO_DB", str(db))
    module = __import__(module_name)
    monkeypatch.setattr(module, "DB_PATH", db)
    monkeypatch.setattr(module, "OUT_PATH", out)
    rc = module.main()
    assert rc == 0
    md = out.read_text(encoding="utf-8")
    assert md.startswith("Last refresh: ")
    # At least the highest-quality-elo model ID should appear (Pareto keeps it).
    assert any(mid in md for mid in ids)
