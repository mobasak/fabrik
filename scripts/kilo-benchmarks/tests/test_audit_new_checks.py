"""Direct unit tests for the three audit checks added in Pass 5:
_audit_derived_consistency, _audit_benchmark_freshness,
_audit_endpoints_recency. Previously only exercised indirectly via
the seeded-bug tests. Fills the coverage gap surfaced by the
convergence-loop's Pass 5."""

from __future__ import annotations

import json
import sqlite3
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _seed_min_db(tmp_path: Path) -> Path:
    db = tmp_path / "seed.db"
    conn = sqlite3.connect(db)
    conn.executescript(
        """
        CREATE TABLE agents (
            id TEXT PRIMARY KEY, status TEXT DEFAULT 'active',
            input_cost_per_m REAL, output_cost_per_m REAL,
            kilo_input_cost_per_m REAL, kilo_output_cost_per_m REAL,
            cheapest_provider TEXT, cheapest_provider_price REAL,
            cheapest_gateway TEXT, cheapest_gateway_price REAL,
            via_openrouter INTEGER, via_kilo INTEGER,
            endpoints_last_scraped TEXT
        );
        """
    )
    conn.commit()
    conn.close()
    return db


def test_derived_consistency_catches_direct_mismatch(tmp_path):
    """cheapest_gateway='direct' at $5 but input_cost_per_m=$3 → drift."""
    from audit_ui_values import _audit_derived_consistency

    db = _seed_min_db(tmp_path)
    conn = sqlite3.connect(db)
    conn.execute(
        "INSERT INTO agents (id, input_cost_per_m, cheapest_gateway, cheapest_gateway_price) "
        "VALUES ('test/model', 3.0, 'direct', 5.0)"
    )
    conn.commit()
    conn.close()
    drifts = _audit_derived_consistency(db)
    assert drifts, "must catch direct-gateway/price mismatch"
    assert drifts[0]["gateway"] == "direct"
    assert drifts[0]["price"] == 5.0
    assert drifts[0]["expected"] == 3.0


def test_derived_consistency_catches_or_provider_mismatch(tmp_path):
    """cheapest_gateway='or:Anthropic' at $10 but cheapest_provider_price=$8 → drift."""
    from audit_ui_values import _audit_derived_consistency

    db = _seed_min_db(tmp_path)
    conn = sqlite3.connect(db)
    conn.execute(
        "INSERT INTO agents (id, cheapest_provider, cheapest_provider_price, "
        "cheapest_gateway, cheapest_gateway_price) VALUES "
        "('test/model', 'Anthropic', 8.0, 'or:Anthropic', 10.0)"
    )
    conn.commit()
    conn.close()
    drifts = _audit_derived_consistency(db)
    assert drifts, "must catch or:provider/price mismatch"


def test_derived_consistency_clean_row_no_drift(tmp_path):
    from audit_ui_values import _audit_derived_consistency

    db = _seed_min_db(tmp_path)
    conn = sqlite3.connect(db)
    conn.execute(
        "INSERT INTO agents (id, input_cost_per_m, cheapest_gateway, cheapest_gateway_price) "
        "VALUES ('test/model', 5.0, 'direct', 5.0)"
    )
    conn.commit()
    conn.close()
    assert not _audit_derived_consistency(db)


def test_benchmark_freshness_reports_missing_cache(tmp_path, monkeypatch):
    """A missing cache file trips the freshness check."""
    import audit_ui_values

    monkeypatch.setattr(audit_ui_values, "SCRIPT_DIR", tmp_path)
    # No cache/ dir at all
    findings = audit_ui_values._audit_benchmark_freshness()
    assert any(f["problem"] == "MISSING" for f in findings), (
        "must report MISSING for absent cache files"
    )


def test_benchmark_freshness_reports_stale_cache(tmp_path, monkeypatch):
    """A cache older than the threshold trips the warning."""
    import audit_ui_values

    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    stale_ts = (datetime.now(UTC) - timedelta(days=30)).isoformat()
    fresh_ts = datetime.now(UTC).isoformat()
    (cache_dir / "arena_parsed.json").write_text(json.dumps({"scraped_at": stale_ts}))
    (cache_dir / "aa_parsed.json").write_text(json.dumps({"fetched_at": fresh_ts}))
    (cache_dir / "tbench_parsed.json").write_text(json.dumps({"scraped_at": fresh_ts}))
    (cache_dir / "benchmark_cache.json").write_text(json.dumps({"last_updated": fresh_ts}))

    monkeypatch.setattr(audit_ui_values, "SCRIPT_DIR", tmp_path)
    findings = audit_ui_values._audit_benchmark_freshness()
    stale = [f for f in findings if f.get("cache") == "arena_parsed.json"]
    assert stale, f"must catch stale arena cache; got {findings}"
    assert stale[0]["age_days"] > audit_ui_values.BENCHMARK_STALE_DAYS


def test_benchmark_freshness_clean_when_all_fresh(tmp_path, monkeypatch):
    import audit_ui_values

    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    fresh_ts = datetime.now(UTC).isoformat()
    for f in ("arena_parsed.json", "aa_parsed.json", "tbench_parsed.json", "benchmark_cache.json"):
        # Each cache has a different timestamp key — cover them all
        key = {"aa_parsed.json": "fetched_at", "benchmark_cache.json": "last_updated"}.get(
            f, "scraped_at"
        )
        (cache_dir / f).write_text(json.dumps({key: fresh_ts}))
    monkeypatch.setattr(audit_ui_values, "SCRIPT_DIR", tmp_path)
    assert not audit_ui_values._audit_benchmark_freshness()


def test_endpoints_recency_catches_stale_row(tmp_path):
    """A row whose endpoints haven't been scraped in > threshold days is flagged."""
    from audit_ui_values import _audit_endpoints_recency

    db = _seed_min_db(tmp_path)
    conn = sqlite3.connect(db)
    stale = (date.today() - timedelta(days=30)).isoformat()
    fresh = date.today().isoformat()
    conn.execute(
        "INSERT INTO agents (id, via_openrouter, status, endpoints_last_scraped) "
        "VALUES ('stale/model', 1, 'active', ?)",
        (stale,),
    )
    conn.execute(
        "INSERT INTO agents (id, via_openrouter, status, endpoints_last_scraped) "
        "VALUES ('fresh/model', 1, 'active', ?)",
        (fresh,),
    )
    conn.commit()
    conn.close()
    stale_rows = _audit_endpoints_recency(db)
    ids = {r["id"] for r in stale_rows}
    assert "stale/model" in ids, "must flag stale row"
    assert "fresh/model" not in ids, "must not flag fresh row"


def test_endpoints_recency_catches_null_scraped(tmp_path):
    """A row that has never been scraped (NULL) must be flagged."""
    from audit_ui_values import _audit_endpoints_recency

    db = _seed_min_db(tmp_path)
    conn = sqlite3.connect(db)
    conn.execute(
        "INSERT INTO agents (id, via_openrouter, status, endpoints_last_scraped) "
        "VALUES ('never/scraped', 1, 'active', NULL)"
    )
    conn.commit()
    conn.close()
    stale_rows = _audit_endpoints_recency(db)
    assert any(r["id"] == "never/scraped" for r in stale_rows), "must flag never-scraped row"


def test_endpoints_recency_skips_non_or_rows(tmp_path):
    """Direct-vendor rows (via_openrouter=0) are exempt — they don't have
    endpoints to scrape."""
    from audit_ui_values import _audit_endpoints_recency

    db = _seed_min_db(tmp_path)
    conn = sqlite3.connect(db)
    conn.execute(
        "INSERT INTO agents (id, via_openrouter, status, endpoints_last_scraped) "
        "VALUES ('direct/vendor', 0, 'active', NULL)"
    )
    conn.commit()
    conn.close()
    assert not _audit_endpoints_recency(db)
