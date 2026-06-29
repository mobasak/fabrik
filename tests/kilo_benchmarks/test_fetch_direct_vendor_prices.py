"""Orchestrator integration tests for fetch_direct_vendor_prices.py.

Exercises the failure-model state machine, idempotency, alert wiring, and
DB-merge atomicity. Uses a tiny temp SQLite DB + mocked WebScraper so tests
don't touch the network or the real kilo_agents.db.

Per docs/development/plans/2026-06-29-plan-direct-vendor-pricing.md (Phase 1).
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = REPO_ROOT / "scripts" / "kilo-benchmarks"

if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

# Module under test
import fetch_direct_vendor_prices as orch  # noqa: E402
from direct_vendor_parsers import ParsedRow  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
def _seed_db(db_path: Path) -> None:
    """Mirror enough of `agents` for the orchestrator's UPDATE paths."""
    conn = sqlite3.connect(db_path)
    try:
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
                consecutive_pricing_misses INTEGER DEFAULT 0,
                price_scrape_source TEXT,
                discard_reason TEXT
            );
            INSERT INTO agents (id, provider, service_type, input_cost_per_m, pricing_unit)
            VALUES
                ('soniox/stt-async-v4',   'soniox', 'stt', 1666.67, 'audio-min'),
                ('soniox/stt-realtime-v4','soniox', 'stt', 2166.67, 'audio-min'),
                ('cartesia/sonic-2',      'cartesia','tts',   40.0, 'M-chars'),
                ('deepgram/nova-2',       'deepgram','stt',   60.0, 'audio-min'),
                ('deepgram/nova-3',       'deepgram','stt',   71.67,'audio-min')
            ;
            """
        )
        conn.commit()
    finally:
        conn.close()


def _registry() -> dict:
    return {
        "soniox": {
            "pricing_url": "https://soniox.com/pricing/",
            "fetch_method": "static",
            "parser_module": "direct_vendor_parsers.soniox",
            "models": {
                "soniox/stt-async-v4":   {"slug_on_page": "stt-async-v4",   "expected_unit": "audio-min"},
                "soniox/stt-realtime-v4":{"slug_on_page": "stt-realtime-v4","expected_unit": "audio-min"},
            },
        },
        "cartesia": {
            "pricing_url": "https://cartesia.ai/pricing",
            "fetch_method": "static",
            "parser_module": "direct_vendor_parsers.cartesia",
            "models": {
                "cartesia/sonic-2": {"slug_on_page": "sonic-2", "expected_unit": "audio-min"},
            },
        },
        "deepgram": {
            "pricing_url": "https://deepgram.com/pricing",
            "fetch_method": "static",
            "parser_module": "direct_vendor_parsers.deepgram",
            "models": {
                "deepgram/nova-2": {"slug_on_page": "nova-2", "expected_unit": "audio-min"},
                "deepgram/nova-3": {"slug_on_page": "nova-3", "expected_unit": "audio-min"},
            },
        },
    }


class _FakeScraper:
    """In-process WebScraper substitute. Returns scripted HTML per URL."""

    def __init__(self, url_to_html: dict[str, str], boom_urls: set[str] | None = None):
        self.url_to_html = url_to_html
        self.boom_urls = boom_urls or set()

    def fetch_static(self, url: str, **_kw) -> str:
        if url in self.boom_urls:
            raise orch.FetchError(f"simulated 5xx for {url}")
        return self.url_to_html[url]

    def fetch_rendered(self, url: str, **_kw) -> str:
        if url in self.boom_urls:
            raise orch.FetchError(f"simulated 5xx for {url}")
        return self.url_to_html[url]


# ---------------------------------------------------------------------------
# Helper-level tests
# ---------------------------------------------------------------------------
def test_signed_pct_diff_handles_zero_and_none() -> None:
    assert orch._signed_pct_diff(None, 100.0) is None
    assert orch._signed_pct_diff(0.0, 100.0) is None
    assert orch._signed_pct_diff(-1.0, 100.0) is None
    assert abs(orch._signed_pct_diff(100.0, 110.0) - 0.10) < 1e-9
    assert abs(orch._signed_pct_diff(100.0, 50.0) + 0.50) < 1e-9


def test_classify_diff_thresholds() -> None:
    # 0% — clean write
    block, alert_only, _ = orch._classify_diff(0.0)
    assert (block, alert_only) == (False, False)
    # 9% — clean write
    block, alert_only, _ = orch._classify_diff(0.09)
    assert (block, alert_only) == (False, False)
    # 25% — audit alert, write
    block, alert_only, _ = orch._classify_diff(0.25)
    assert (block, alert_only) == (False, True)
    # -55% — block
    block, alert_only, _ = orch._classify_diff(-0.55)
    assert (block, alert_only) == (True, False)
    # None — clean (first-scrape)
    block, alert_only, _ = orch._classify_diff(None)
    assert (block, alert_only) == (False, False)


# ---------------------------------------------------------------------------
# Per-vendor flow
# ---------------------------------------------------------------------------
def test_soniox_block_on_99pct_drop(tmp_path: Path) -> None:
    db = tmp_path / "k.db"
    _seed_db(db)
    reg = _registry()
    # Real Soniox fixture price ($0.10/hour) = 27.78/M which is -98% from seed 1666.67
    html = (Path(__file__).parent / "fixtures" / "direct_vendor_parsers" / "soniox.html").read_text()
    scraper = _FakeScraper({"https://soniox.com/pricing/": html})

    outcome = orch.process_vendor(
        vendor="soniox", cfg=reg["soniox"], scraper=scraper,
        db_path=db, apply=True,
    )
    assert outcome.error is None
    assert outcome.parsed_count == 2

    by_id = {w.db_id: w for w in outcome.writes}
    assert by_id["soniox/stt-async-v4"].action == "refused_diff"
    assert by_id["soniox/stt-realtime-v4"].action == "refused_diff"

    # CRITICAL: refused writes must NOT have updated the DB
    conn = sqlite3.connect(db)
    rows = dict(conn.execute(
        "SELECT id, input_cost_per_m FROM agents WHERE id LIKE 'soniox/%'"
    ).fetchall())
    conn.close()
    assert abs(rows["soniox/stt-async-v4"] - 1666.67) < 0.01
    assert abs(rows["soniox/stt-realtime-v4"] - 2166.67) < 0.01


def test_cartesia_unit_mismatch_refused(tmp_path: Path) -> None:
    db = tmp_path / "k.db"
    _seed_db(db)
    reg = _registry()
    # Parser will produce audio-min, but Cartesia DB row is M-chars
    html = (Path(__file__).parent / "fixtures" / "direct_vendor_parsers" / "cartesia.html").read_text()
    scraper = _FakeScraper({"https://cartesia.ai/pricing": html})

    outcome = orch.process_vendor(
        vendor="cartesia", cfg=reg["cartesia"], scraper=scraper,
        db_path=db, apply=True,
    )
    assert outcome.error is None
    (w,) = outcome.writes
    assert w.action == "refused_unit"
    assert "M-chars" in w.explanation

    # DB row unchanged
    conn = sqlite3.connect(db)
    row = conn.execute(
        "SELECT input_cost_per_m, pricing_unit FROM agents WHERE id='cartesia/sonic-2'"
    ).fetchone()
    conn.close()
    assert abs(row[0] - 40.0) < 0.01
    assert row[1] == "M-chars"


def test_deepgram_audit_write_and_block_mix(tmp_path: Path) -> None:
    db = tmp_path / "k.db"
    _seed_db(db)
    reg = _registry()
    html = (Path(__file__).parent / "fixtures" / "direct_vendor_parsers" / "deepgram.html").read_text()
    scraper = _FakeScraper({"https://deepgram.com/pricing": html})

    outcome = orch.process_vendor(
        vendor="deepgram", cfg=reg["deepgram"], scraper=scraper,
        db_path=db, apply=True,
    )
    by_id = {w.db_id: w for w in outcome.writes}
    # nova-3: ~12% audit, WROTE
    assert by_id["deepgram/nova-3"].action == "wrote"
    # nova-2: ~62% block
    assert by_id["deepgram/nova-2"].action == "refused_diff"

    conn = sqlite3.connect(db)
    rows = dict(conn.execute(
        "SELECT id, input_cost_per_m FROM agents WHERE id LIKE 'deepgram/%'"
    ).fetchall())
    conn.close()
    # nova-3 updated
    assert abs(rows["deepgram/nova-3"] - 80.0) < 0.5
    # nova-2 unchanged
    assert abs(rows["deepgram/nova-2"] - 60.0) < 0.01


def test_fetch_failure_yields_error_outcome(tmp_path: Path) -> None:
    db = tmp_path / "k.db"
    _seed_db(db)
    reg = _registry()
    scraper = _FakeScraper(url_to_html={}, boom_urls={"https://deepgram.com/pricing"})

    outcome = orch.process_vendor(
        vendor="deepgram", cfg=reg["deepgram"], scraper=scraper,
        db_path=db, apply=True,
    )
    assert outcome.error is not None
    assert outcome.fetched is False
    assert outcome.parsed_count == 0
    # No DB writes attempted
    conn = sqlite3.connect(db)
    row = conn.execute(
        "SELECT input_cost_per_m FROM agents WHERE id='deepgram/nova-3'"
    ).fetchone()
    conn.close()
    assert abs(row[0] - 71.67) < 0.01


def test_simulate_failure_path(tmp_path: Path) -> None:
    db = tmp_path / "k.db"
    _seed_db(db)
    reg = _registry()
    scraper = _FakeScraper({})

    outcome = orch.process_vendor(
        vendor="soniox", cfg=reg["soniox"], scraper=scraper,
        db_path=db, apply=True, simulate_failure=True,
    )
    assert outcome.error is not None
    assert "simulated" in outcome.error.lower()


def test_idempotency_safe_write(tmp_path: Path) -> None:
    """Running the orchestrator twice produces the same final DB state.

    Specifically: nova-3 gets written on the first pass (12% audit). On the
    second pass, the DB already holds the new value, so the diff drops to 0%
    and the write becomes a no-op-equivalent (still writes, but same value
    + last_price_scraped already today).
    """
    db = tmp_path / "k.db"
    _seed_db(db)
    reg = _registry()
    html = (Path(__file__).parent / "fixtures" / "direct_vendor_parsers" / "deepgram.html").read_text()
    scraper = _FakeScraper({"https://deepgram.com/pricing": html})

    o1 = orch.process_vendor(vendor="deepgram", cfg=reg["deepgram"],
                             scraper=scraper, db_path=db, apply=True)
    o2 = orch.process_vendor(vendor="deepgram", cfg=reg["deepgram"],
                             scraper=scraper, db_path=db, apply=True)

    # Second pass: nova-3 still wrote (price equal → 0% diff → clean write)
    by_id_1 = {w.db_id: w for w in o1.writes}
    by_id_2 = {w.db_id: w for w in o2.writes}
    assert by_id_1["deepgram/nova-3"].action == "wrote"
    # On pass 2, before-price = pass1's after-price, so diff=0; action stays "wrote"
    assert by_id_2["deepgram/nova-3"].action == "wrote"
    assert (by_id_2["deepgram/nova-3"].pct_diff or 0) == 0.0


def test_unmapped_slug_does_not_corrupt_db(tmp_path: Path) -> None:
    """A parser returning a slug not in the registry must NOT touch any DB row."""
    db = tmp_path / "k.db"
    _seed_db(db)
    reg = _registry()
    reg["test"] = {
        "pricing_url": "https://test.example/pricing",
        "fetch_method": "static",
        "parser_module": "direct_vendor_parsers.soniox",
        "models": {},  # NO models registered
    }
    html = (Path(__file__).parent / "fixtures" / "direct_vendor_parsers" / "soniox.html").read_text()
    scraper = _FakeScraper({"https://test.example/pricing": html})

    outcome = orch.process_vendor(
        vendor="test", cfg=reg["test"], scraper=scraper,
        db_path=db, apply=True,
    )
    # All parsed rows are reported missing (unmapped); no DB writes
    assert all(w.action == "missing" for w in outcome.writes)
    conn = sqlite3.connect(db)
    counts = conn.execute("SELECT COUNT(*) FROM agents WHERE last_price_scraped IS NOT NULL").fetchone()[0]
    conn.close()
    assert counts == 0


def test_missing_row_bumps_miss_counter(tmp_path: Path) -> None:
    """If parser returns no rows but vendor fetched OK, miss-counter bumps."""
    db = tmp_path / "k.db"
    _seed_db(db)
    reg = _registry()
    # Parser will return [] because the HTML has no Nova markers
    scraper = _FakeScraper({"https://deepgram.com/pricing": "<html>nothing here</html>"})

    o = orch.process_vendor(vendor="deepgram", cfg=reg["deepgram"], scraper=scraper,
                            db_path=db, apply=True)
    conn = sqlite3.connect(db)
    misses = dict(conn.execute(
        "SELECT id, consecutive_pricing_misses FROM agents WHERE id LIKE 'deepgram/%'"
    ).fetchall())
    conn.close()
    assert misses["deepgram/nova-2"] == 1
    assert misses["deepgram/nova-3"] == 1


def test_seven_consecutive_misses_flips_status(tmp_path: Path) -> None:
    """After MISS_TO_DEPRECATE consecutive misses, status flips to 'deprecated'."""
    db = tmp_path / "k.db"
    _seed_db(db)
    reg = _registry()
    scraper = _FakeScraper({"https://deepgram.com/pricing": "<html>nothing here</html>"})

    for _ in range(orch.MISS_TO_DEPRECATE):
        orch.process_vendor(vendor="deepgram", cfg=reg["deepgram"], scraper=scraper,
                            db_path=db, apply=True)

    conn = sqlite3.connect(db)
    rows = {r[0]: (r[1], r[2]) for r in conn.execute(
        "SELECT id, status, consecutive_pricing_misses FROM agents WHERE id LIKE 'deepgram/%'"
    ).fetchall()}
    conn.close()
    # Both rows hit the threshold
    for db_id in ("deepgram/nova-2", "deepgram/nova-3"):
        assert rows[db_id][0] == "deprecated", f"{db_id}: status should be 'deprecated'"
        assert rows[db_id][1] >= orch.MISS_TO_DEPRECATE


# ---------------------------------------------------------------------------
# Dry-run vs apply
# ---------------------------------------------------------------------------
def test_dry_run_never_writes(tmp_path: Path) -> None:
    db = tmp_path / "k.db"
    _seed_db(db)
    reg = _registry()
    html = (Path(__file__).parent / "fixtures" / "direct_vendor_parsers" / "deepgram.html").read_text()
    scraper = _FakeScraper({"https://deepgram.com/pricing": html})

    o = orch.process_vendor(vendor="deepgram", cfg=reg["deepgram"], scraper=scraper,
                            db_path=db, apply=False)
    # Outcomes show wrote/refused, but the DB is untouched
    conn = sqlite3.connect(db)
    rows = {r[0]: (r[1], r[2]) for r in conn.execute(
        "SELECT id, input_cost_per_m, last_price_scraped FROM agents WHERE id LIKE 'deepgram/%'"
    ).fetchall()}
    conn.close()
    # nova-3 still at original seed value, last_price_scraped still NULL
    assert abs(rows["deepgram/nova-3"][0] - 71.67) < 0.01
    assert rows["deepgram/nova-3"][1] is None


# ---------------------------------------------------------------------------
# Alert wiring
# ---------------------------------------------------------------------------
def test_send_alert_returns_false_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """As of the Phase-5 alerting wire-up, fabrik-lib/alerting IS vendored
    into scripts/kilo-benchmarks/alerting/. The previous "stderr fallback
    when lib absent" path is no longer reachable. Instead, _send_alert
    delegates to the real alerting module which honors ALERT_ENABLED.

    Test: with ALERT_ENABLED=0, send_alert returns False without firing
    a Telegram message — the test never hits the network."""
    monkeypatch.setenv("ALERT_ENABLED", "0")
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("ALERT_VPS_HOST", raising=False)
    ok = orch._send_alert("title", "body", "warning")
    assert ok is False


def test_alert_fires_on_refused_diff(tmp_path: Path) -> None:
    """End-to-end: a refused write must trigger a _send_alert call."""
    db = tmp_path / "k.db"
    _seed_db(db)
    reg = _registry()
    html = (Path(__file__).parent / "fixtures" / "direct_vendor_parsers" / "soniox.html").read_text()
    scraper = _FakeScraper({"https://soniox.com/pricing/": html})

    captured: list[tuple[str, str, str]] = []

    def fake_send(title: str, body: str, severity: str = "warning") -> bool:
        captured.append((title, body, severity))
        return True

    with patch.object(orch, "_send_alert", side_effect=fake_send):
        outcome = orch.process_vendor(vendor="soniox", cfg=reg["soniox"], scraper=scraper,
                                      db_path=db, apply=True)
        orch._fire_per_vendor_alerts(outcome)

    # Both soniox rows are refused; expect 2 alerts
    refused_alerts = [t for t in captured if "blocked write" in t[0]]
    assert len(refused_alerts) == 2
    for title, body, severity in refused_alerts:
        assert "soniox" in title
        assert severity == "critical"


# ============================================================
# Adversarial Pass-1 regression tests (Phase 1 review)
# ============================================================

def test_url_broken_sentinel_clears_on_successful_write(tmp_path: Path) -> None:
    """Adversarial Pass-1 finding #3: Plan §"DB schema additions" CLEAR rule
    says price_scrape_source MUST be NULLed on every successful write. A
    previous version of the orchestrator wrote w.source_url here, which meant
    a row stamped URL_BROKEN_<date> would never auto-clear once its URL got
    fixed."""
    db = tmp_path / "k.db"
    _seed_db(db)
    # Pre-seed a URL_BROKEN sentinel for nova-3
    conn = sqlite3.connect(db)
    conn.execute(
        "UPDATE agents SET price_scrape_source='URL_BROKEN_2026-01-01' WHERE id='deepgram/nova-3'"
    )
    conn.commit()
    conn.close()

    reg = _registry()
    html = (Path(__file__).parent / "fixtures" / "direct_vendor_parsers" / "deepgram.html").read_text()
    scraper = _FakeScraper({"https://deepgram.com/pricing": html})

    orch.process_vendor(vendor="deepgram", cfg=reg["deepgram"], scraper=scraper,
                        db_path=db, apply=True)

    conn = sqlite3.connect(db)
    source = conn.execute(
        "SELECT price_scrape_source FROM agents WHERE id='deepgram/nova-3'"
    ).fetchone()[0]
    conn.close()
    # nova-3 had a +12% audit-alert write; CLEAR rule must NULL the sentinel.
    assert source is None, f"sentinel should clear but found {source!r}"


def test_url_broken_sentinel_set_on_fetch_failure(tmp_path: Path) -> None:
    """Adversarial Pass-1 finding #4: Plan §"DB schema additions" SET rule
    says orchestrator MUST write URL_BROKEN_<YYYY-MM-DD> into
    price_scrape_source when (a) URL fails AND (b) source is currently NULL.
    Previous version had ZERO implementation; rows just kept their old
    price + NULL source + no audit trail of the failure."""
    db = tmp_path / "k.db"
    _seed_db(db)
    reg = _registry()
    scraper = _FakeScraper({}, boom_urls={"https://deepgram.com/pricing"})

    outcome = orch.process_vendor(vendor="deepgram", cfg=reg["deepgram"],
                                  scraper=scraper, db_path=db, apply=True)
    assert outcome.error is not None

    conn = sqlite3.connect(db)
    rows = {r[0]: r[1] for r in conn.execute(
        "SELECT id, price_scrape_source FROM agents WHERE id LIKE 'deepgram/%'"
    ).fetchall()}
    conn.close()
    today = orch._today_utc_iso()
    for db_id in ("deepgram/nova-2", "deepgram/nova-3"):
        assert rows[db_id] is not None, f"{db_id}: sentinel should be SET"
        assert rows[db_id] == f"URL_BROKEN_{today}", (
            f"{db_id}: expected URL_BROKEN_{today}, got {rows[db_id]!r}")


def test_url_broken_set_rule_idempotent(tmp_path: Path) -> None:
    """A row that ALREADY has a non-NULL price_scrape_source (e.g. set by a
    previous failure run) must NOT be overwritten by a second failure."""
    db = tmp_path / "k.db"
    _seed_db(db)
    # Pre-set a sentinel from yesterday
    conn = sqlite3.connect(db)
    conn.execute(
        "UPDATE agents SET price_scrape_source='URL_BROKEN_2026-01-01' "
        "WHERE id='deepgram/nova-2'"
    )
    conn.commit()
    conn.close()

    reg = _registry()
    scraper = _FakeScraper({}, boom_urls={"https://deepgram.com/pricing"})

    orch.process_vendor(vendor="deepgram", cfg=reg["deepgram"],
                        scraper=scraper, db_path=db, apply=True)

    conn = sqlite3.connect(db)
    rows = {r[0]: r[1] for r in conn.execute(
        "SELECT id, price_scrape_source FROM agents WHERE id LIKE 'deepgram/%'"
    ).fetchall()}
    conn.close()
    # nova-2 keeps its pre-existing sentinel; nova-3 (was NULL) gets today's
    assert rows["deepgram/nova-2"] == "URL_BROKEN_2026-01-01"
    today = orch._today_utc_iso()
    assert rows["deepgram/nova-3"] == f"URL_BROKEN_{today}"


def test_url_broken_set_rule_skipped_under_dry_run(tmp_path: Path) -> None:
    """SET rule must NOT touch the DB under --dry-run."""
    db = tmp_path / "k.db"
    _seed_db(db)
    reg = _registry()
    scraper = _FakeScraper({}, boom_urls={"https://deepgram.com/pricing"})

    orch.process_vendor(vendor="deepgram", cfg=reg["deepgram"],
                        scraper=scraper, db_path=db, apply=False)

    conn = sqlite3.connect(db)
    rows = dict(conn.execute(
        "SELECT id, price_scrape_source FROM agents WHERE id LIKE 'deepgram/%'"
    ).fetchall())
    conn.close()
    assert rows["deepgram/nova-2"] is None
    assert rows["deepgram/nova-3"] is None


def test_load_dotenv_runs_at_module_entry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Adversarial review of 93d24f9c (alerting wire-up) found that cron runs
    with a clean env so TELEGRAM_BOT_TOKEN/BROWSERLESS_TOKEN wouldn't reach
    the orchestrator. Fixed by adding load_dotenv() at module entry.

    This test pins that the load_dotenv import + call happens at module-level
    (not inside a function) so it executes ONCE when the module is first
    imported, before any _send_alert or WebScraper construction.
    """
    import inspect
    src = inspect.getsource(orch)
    # Must import load_dotenv at module level
    assert "from dotenv import load_dotenv" in src
    # Must call load_dotenv at module-level (i.e., outside any def/class block)
    # by checking the call appears BEFORE the first `def ` in the source.
    first_def_pos = src.find("\ndef ")
    load_call_pos = src.find("load_dotenv(")
    assert load_call_pos > 0, "load_dotenv() must be called somewhere"
    assert load_call_pos < first_def_pos, (
        "load_dotenv() must be called at module-import time (before the first "
        "`def`), otherwise cron runs miss the env load — see adversarial-review "
        "finding documented in CHANGELOG."
    )
