"""Regression tests for audit_direct_vendor_freshness.py."""

from __future__ import annotations

import importlib.util
import sqlite3
import sys
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = REPO_ROOT / "scripts" / "kilo-benchmarks"

if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))


def _load():
    spec = importlib.util.spec_from_file_location(
        "audit_direct_vendor_freshness", SCRIPT_DIR / "audit_direct_vendor_freshness.py"
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_classify_seed_only_when_no_timestamp() -> None:
    mod = _load()
    status, age = mod.classify(None, None, today=date(2026, 6, 30))
    assert status == "seed-only"
    assert age is None


def test_classify_url_broken_sentinel_takes_precedence() -> None:
    """If price_scrape_source carries the sentinel, that trumps any age check
    on last_price_scraped (operator needs to fix the URL first)."""
    mod = _load()
    status, age = mod.classify(
        last_price_scraped="2026-06-25",
        price_scrape_source="URL_BROKEN_2026-06-25",
        today=date(2026, 6, 30),
    )
    assert status == "url-broken"
    assert age is None


def test_classify_scraped_when_within_max_age() -> None:
    mod = _load()
    status, age = mod.classify("2026-06-29", None, today=date(2026, 6, 30), max_age_days=3)
    assert status == "scraped"
    assert age == 1


def test_classify_stale_when_older_than_max_age() -> None:
    mod = _load()
    status, age = mod.classify("2026-06-20", None, today=date(2026, 6, 30), max_age_days=3)
    assert status == "stale"
    assert age == 10


def test_classify_boundary_at_max_age_is_scraped() -> None:
    """Off-by-one guard: exactly at max_age_days = scraped, not stale."""
    mod = _load()
    status, age = mod.classify("2026-06-27", None, today=date(2026, 6, 30), max_age_days=3)
    assert status == "scraped"
    assert age == 3


def test_classify_invalid_iso_date_treated_as_seed_only() -> None:
    mod = _load()
    status, age = mod.classify("not-a-date", None, today=date(2026, 6, 30))
    assert status == "seed-only"
    assert age is None


def test_classify_empty_string_treated_as_seed_only() -> None:
    mod = _load()
    status, age = mod.classify("", None, today=date(2026, 6, 30))
    assert status == "seed-only"


def _seed(db_path: Path) -> None:
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE agents (
            id TEXT PRIMARY KEY,
            provider TEXT,
            service_type TEXT,
            status TEXT NOT NULL DEFAULT 'active',
            via_openrouter INTEGER NOT NULL DEFAULT 0,
            via_kilo INTEGER NOT NULL DEFAULT 0,
            input_cost_per_m REAL,
            pricing_unit TEXT,
            last_price_scraped TEXT,
            price_scrape_source TEXT,
            consecutive_pricing_misses INTEGER DEFAULT 0
        );
        INSERT INTO agents (id, provider, service_type, input_cost_per_m, pricing_unit,
                            last_price_scraped, price_scrape_source) VALUES
            ('soniox/tts',         'soniox', 'tts', 180.0,   'M-chars',   NULL, NULL),
            ('cartesia/sonic-2',   'cartesia','tts',1000.0, 'audio-min','2026-06-30', NULL),
            ('legacy/url-broken',  'legacy', 'tts',  40.0,  'M-chars',  '2026-01-01', 'URL_BROKEN_2026-01-01'),
            ('stale/row',          'stale',  'tts',  10.0,  'audio-min','2026-06-01', NULL);
        """
    )
    # Also a row that should be EXCLUDED (via_openrouter=1)
    conn.execute(
        "INSERT INTO agents (id, provider, service_type, via_openrouter, input_cost_per_m, pricing_unit) "
        "VALUES ('openai/gpt-4o', 'openai', 'llm', 1, 5.0, 'M-tokens')"
    )
    conn.commit()
    conn.close()


def test_run_excludes_openrouter_rows(tmp_path: Path) -> None:
    db = tmp_path / "k.db"
    _seed(db)
    mod = _load()
    rows = mod.run(db, max_age_days=3, filter_status=None)
    ids = {r["id"] for r in rows}
    assert "openai/gpt-4o" not in ids
    assert {"soniox/tts", "cartesia/sonic-2", "legacy/url-broken", "stale/row"} <= ids


def test_run_sort_order_attention_first(tmp_path: Path) -> None:
    """stale → url-broken → seed-only → scraped (the operator triages top-down)."""
    db = tmp_path / "k.db"
    _seed(db)
    mod = _load()
    rows = mod.run(db, max_age_days=3, filter_status=None)
    # First row should be the stale one, then url-broken, then seed-only,
    # then scraped (if any).
    statuses = [r["freshness_status"] for r in rows]
    assert statuses[0] == "stale", f"first row should be stale; got {statuses}"
    assert "url-broken" in statuses
    assert "seed-only" in statuses


def test_filter_status_returns_only_matching(tmp_path: Path) -> None:
    db = tmp_path / "k.db"
    _seed(db)
    mod = _load()
    rows = mod.run(db, max_age_days=3, filter_status="seed-only")
    assert all(r["freshness_status"] == "seed-only" for r in rows)
    assert any(r["id"] == "soniox/tts" for r in rows)


def test_csv_output(tmp_path: Path) -> None:
    db = tmp_path / "k.db"
    _seed(db)
    mod = _load()
    rows = mod.run(db, max_age_days=3, filter_status=None)
    out = tmp_path / "audit.csv"
    mod.emit_csv(rows, out)
    text = out.read_text()
    assert "freshness_status" in text
    assert "stale" in text


def test_empty_db_emits_csv_header(tmp_path: Path) -> None:
    db = tmp_path / "k.db"
    # Create empty agents table
    conn = sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE agents (id TEXT, provider TEXT, service_type TEXT, "
        "status TEXT NOT NULL DEFAULT 'active', "
        "via_openrouter INTEGER NOT NULL DEFAULT 0, "
        "via_kilo INTEGER NOT NULL DEFAULT 0, "
        "input_cost_per_m REAL, pricing_unit TEXT, "
        "last_price_scraped TEXT, price_scrape_source TEXT, "
        "consecutive_pricing_misses INTEGER DEFAULT 0)"
    )
    conn.commit()
    conn.close()
    mod = _load()
    out = tmp_path / "audit.csv"
    mod.emit_csv([], out)
    assert out.exists()
    assert "id" in out.read_text()
