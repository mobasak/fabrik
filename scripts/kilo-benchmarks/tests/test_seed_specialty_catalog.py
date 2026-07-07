"""Tests for seed_specialty_catalog.py — Phase A of best-model-suggester.

The critical path is the catalog→seed join. If parse_vendor_catalog returns
wrong provider IDs, every seeded row lands with reachable_with_existing_keys=0
and the suggester returns empty pools for everything. Guard that first.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_parse_vendor_catalog_maps_status_to_accessibility(tmp_path):
    md = tmp_path / "AI_VENDOR_ACCESS.md"
    md.write_text(
        "Last verified: 2026-07-05\n\n"
        "| Vendor | DB provider(s) | Auth | Status | Credits | Notes |\n"
        "|---|---|---|---|---|---|\n"
        "| OpenRouter | openai, anthropic | env | ✅ | $50 | ok |\n"
        "| BFL direct | bfl | env | ❌ | none | deprecated |\n"
        "| ElevenLabs | elevenlabs | env | ⚠️ | low | free tier |\n",
        encoding="utf-8",
    )
    from seed_specialty_catalog import parse_vendor_catalog

    result = parse_vendor_catalog(md)
    assert result == {
        "openai": True,
        "anthropic": True,
        "bfl": False,
        "elevenlabs": True,
    }


def test_migrate_is_idempotent_on_repeated_runs(tmp_path):
    """Regression: parts[4] vs parts[5] indexing bug in _migrate would raise
    OperationalError('duplicate column name: quality_elo') on the second run.
    """
    db = tmp_path / "test.db"
    conn = sqlite3.connect(db)
    conn.executescript(
        """
        CREATE TABLE agents (
            id TEXT PRIMARY KEY,
            provider TEXT,
            service_type TEXT,
            status TEXT
        );
        """
    )
    from seed_specialty_catalog import _migrate

    _migrate(conn)
    _migrate(conn)  # second run must not raise
    cols = {row[1] for row in conn.execute("PRAGMA table_info(agents)")}
    assert "quality_elo" in cols
    assert "reachable_with_existing_keys" in cols
    conn.close()


def test_seed_quality_elo_only_touches_matching_ids(tmp_path):
    """Guard against Elo bleed into unrelated rows.

    Only rows whose id exactly matches a hardcoded Elo mapping receive the
    quality_elo value. Any other row must stay NULL.
    """
    db = tmp_path / "test.db"
    conn = sqlite3.connect(db)
    conn.executescript(
        """
        CREATE TABLE agents (
            id TEXT PRIMARY KEY,
            provider TEXT,
            service_type TEXT,
            quality_elo REAL,
            status TEXT,
            reachable_with_existing_keys INTEGER NOT NULL DEFAULT 0
        );
        INSERT INTO agents (id, provider, service_type, status)
          VALUES ('openai/gpt-image-2', 'openai', 'image_gen', 'active');
        INSERT INTO agents (id, provider, service_type, status)
          VALUES ('stability/sdxl', 'stability', 'image_gen', 'active');
        """
    )
    from seed_specialty_catalog import _seed_quality_elo

    _seed_quality_elo(conn)

    row = conn.execute(
        "SELECT quality_elo FROM agents WHERE id='openai/gpt-image-2'"
    ).fetchone()
    assert row[0] == 1339
    unmatched = conn.execute(
        "SELECT quality_elo FROM agents WHERE id='stability/sdxl'"
    ).fetchone()
    assert unmatched[0] is None
    conn.close()
