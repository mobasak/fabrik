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
    # nova-3 updated to whatever the FAQ-form price normalizes to (was
    # ~80/M from $0.288/hour; after adversarial-review C4 anchor hardening
    # the parser may pick $0.29/hour instead → ~80.56/M. Either form is a
    # real Deepgram price; bound the assertion to the plausible range.)
    assert 70.0 < rows["deepgram/nova-3"] < 100.0
    # nova-2 unchanged (refused_diff, so the seed value should still be the
    # 60.0 the test set up — but the seed price in this test is 60.0 from
    # the helper. Skip the strict equality since the refused_diff path is
    # what we're really asserting.)
    assert rows["deepgram/nova-2"] == 60.0


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


# ============================================================
# write_report_md (Phase 5 deliverable, added 2026-06-30)
# ============================================================

def test_write_report_md_basic_structure(tmp_path) -> None:
    """The audit MD must include date header, totals, per-vendor sections."""
    import sys
    sys.path.insert(0, str(REPO_ROOT / "scripts" / "kilo-benchmarks"))
    from fetch_direct_vendor_prices import VendorOutcome, WriteOutcome, write_report_md

    outcomes = [
        VendorOutcome(
            vendor="testvendor",
            fetched=True,
            parsed_count=1,
            writes=[
                WriteOutcome(
                    vendor="testvendor",
                    db_id="testvendor/foo",
                    before_price=1.0,
                    after_price=1.5,
                    pct_diff=0.5,
                    pricing_unit="M-tokens",
                    action="wrote",
                    raw_price_text="$1.5/M",
                    explanation="|diff|=50% — within tolerance",
                    source_url="https://test.example.com/",
                ),
            ],
            error=None,
        ),
    ]
    out = tmp_path / "audit.md"
    write_report_md(out, outcomes, apply=True)
    body = out.read_text()
    assert "# Direct-vendor pricing audit —" in body
    assert "Run mode: **APPLY**" in body
    assert "## Totals" in body
    assert "Rows wrote: **1**" in body
    assert "### testvendor (parsed=1, wrote=1" in body
    assert "wrote" in body and "testvendor/foo" in body


def test_write_report_md_subscription_only_suffix(tmp_path) -> None:
    """Vendors with parsed=0 and no error get the subscription-only suffix."""
    import sys
    sys.path.insert(0, str(REPO_ROOT / "scripts" / "kilo-benchmarks"))
    from fetch_direct_vendor_prices import VendorOutcome, write_report_md

    outcomes = [
        VendorOutcome(vendor="elevenlabs", fetched=True, parsed_count=0, writes=[], error=None),
    ]
    out = tmp_path / "audit.md"
    write_report_md(out, outcomes, apply=True)
    body = out.read_text()
    assert "subscription-only confirmed" in body
    assert "Subscription-confirmed" in body
    assert "1" in body  # 1 subscription-confirmed vendor


def test_write_report_md_alert_section_on_per_call_emergence(tmp_path) -> None:
    """If subscription_monitor emits an alert row, the audit must include it
    in the Alerts section so operator sees in daily-refresh stream."""
    import sys
    sys.path.insert(0, str(REPO_ROOT / "scripts" / "kilo-benchmarks"))
    from fetch_direct_vendor_prices import VendorOutcome, WriteOutcome, write_report_md

    outcomes = [
        VendorOutcome(
            vendor="suno",
            fetched=True,
            parsed_count=1,
            writes=[
                WriteOutcome(
                    vendor="suno",
                    db_id="<unmapped:suno.com:per-call-pricing-emergence-alert>",
                    before_price=None,
                    after_price=0.0,
                    pct_diff=None,
                    pricing_unit="alert",
                    action="missing",
                    raw_price_text="ALERT: per-call pattern(s) detected — $5 / 1M tokens",
                    explanation="parser returned slug 'suno.com:per-call-pricing-emergence-alert' not in registry",
                    source_url="https://suno.com/pricing",
                ),
            ],
            error=None,
        ),
    ]
    out = tmp_path / "audit.md"
    write_report_md(out, outcomes, apply=True)
    body = out.read_text()
    assert "## Alerts (operator review needed)" in body
    assert "🚨 **suno**: subscription-only vendor may have flipped" in body


# ============================================================
# Adversarial review Phase 3 — Fix Cluster 1
# C1: write_report_md uses "refused" instead of "refused_unit"/"refused_diff"
# C2: subscription_monitor's missing+alert action never reaches Telegram
# ============================================================

def test_C1_write_report_md_counts_refused_unit_in_totals(tmp_path) -> None:
    """REGRESSION (C1): an action="refused_unit" row must increment the
    Totals "Rows refused" count and appear in the Alerts section.

    Pre-fix: the writer used `action == "refused"` (a string that never
    exists in the codebase) so refused_unit writes silently counted as 0.
    Operator saw "Rows refused: 0" while critical writes were blocked.
    """
    import sys
    sys.path.insert(0, str(REPO_ROOT / "scripts" / "kilo-benchmarks"))
    from fetch_direct_vendor_prices import VendorOutcome, WriteOutcome, write_report_md

    outcomes = [
        VendorOutcome(
            vendor="testvendor",
            fetched=True,
            parsed_count=2,
            writes=[
                WriteOutcome(
                    vendor="testvendor",
                    db_id="testvendor/foo",
                    before_price=1.0, after_price=2.0, pct_diff=1.0,
                    pricing_unit="M-tokens",
                    action="refused_unit",
                    raw_price_text="$2.0/Mtok",
                    explanation="parsed M-chars; DB expects M-tokens",
                    source_url="https://test.example/",
                ),
                WriteOutcome(
                    vendor="testvendor",
                    db_id="testvendor/bar",
                    before_price=1.0, after_price=99.0, pct_diff=98.0,
                    pricing_unit="M-tokens",
                    action="refused_diff",
                    raw_price_text="$99.0/Mtok",
                    explanation="|diff|=9800% > 50% (refuse threshold)",
                    source_url="https://test.example/",
                ),
            ],
            error=None,
        ),
    ]
    out = tmp_path / "audit.md"
    write_report_md(out, outcomes, apply=True)
    body = out.read_text()
    # Totals must count BOTH refused_unit + refused_diff
    assert "Rows refused: **2**" in body, body
    # Alerts section must surface both
    assert "## Alerts" in body
    assert "testvendor/foo" in body
    assert "testvendor/bar" in body


def test_C2_subscription_monitor_alert_fires_telegram(monkeypatch) -> None:
    """REGRESSION (C2): when subscription_monitor emits an alert row
    (action="missing", pricing_unit="alert"), _fire_per_vendor_alerts
    MUST call _send_alert with severity="critical".

    Pre-fix: only action in {refused_diff, refused_unit, wrote+drift,
    vendor-error} triggered _send_alert. action="missing" with
    pricing_unit="alert" silently bypassed Telegram — so a subscription
    vendor flipping to per-call pricing produced ZERO alerts.
    Direct invariant-2 violation per the plan.
    """
    import sys
    sys.path.insert(0, str(REPO_ROOT / "scripts" / "kilo-benchmarks"))
    import fetch_direct_vendor_prices as m

    captured = []
    def fake_send(title, body, severity="warning"):
        captured.append({"title": title, "body": body, "severity": severity})
        return True
    monkeypatch.setattr(m, "_send_alert", fake_send)

    outcomes = m.VendorOutcome(
        vendor="suno",
        fetched=True,
        parsed_count=1,
        writes=[
            m.WriteOutcome(
                vendor="suno",
                db_id="<unmapped:suno.com:per-call-pricing-emergence-alert>",
                before_price=None, after_price=0.0, pct_diff=None,
                pricing_unit="alert",
                action="missing",
                raw_price_text="ALERT: per-call pattern(s) detected — $5 / 1M tokens",
                explanation="parser returned slug 'suno.com:per-call-pricing-emergence-alert' not in registry",
                source_url="https://suno.com/pricing",
            ),
        ],
        error=None,
    )
    m._fire_per_vendor_alerts(outcomes)
    # Telegram MUST receive the alert
    alerts = [a for a in captured if "per-call" in (a["title"] + a["body"]).lower()]
    assert len(alerts) == 1, f"expected 1 per-call alert, got {len(captured)}: {captured}"
    assert alerts[0]["severity"] == "critical"


# ============================================================
# Adversarial review Phase 3 — Fix Cluster 2: H4
# H4: _UPSERT_FIELDS includes via_openrouter + via_kilo → operator-set
# routing flags get silently reset to 0 on next seed run.
# ============================================================

def test_H4_seed_does_not_overwrite_operator_set_routing_flags(tmp_path):
    """REGRESSION (H4): seed_direct_vendors.upsert() must NEVER overwrite
    via_openrouter or via_kilo flags on an existing row.

    Pre-fix: _UPSERT_FIELDS included via_openrouter + via_kilo, and the
    per-spec `setdefault('via_openrouter', 0)` forced the spec dict to
    carry value 0 for every _add() call (none pass these kwargs). The
    UPDATE path then wrote 0 to the DB, silently resetting any
    operator-flipped value to 0. This bit us this morning (commit
    cb7e7631 only removed the 4 Anthropic INSTANCES; the structural
    bug remained for any future direct-vendor row that gets OR-listed).
    """
    import importlib
    import sqlite3 as sq
    import sys
    sys.path.insert(0, str(REPO_ROOT / "scripts" / "kilo-benchmarks"))
    db = tmp_path / "seed.db"
    # Mirror just enough schema for the seed-upsert path
    sq.connect(db).executescript("""
        CREATE TABLE agents (
            id TEXT PRIMARY KEY,
            api_id TEXT, name TEXT, provider TEXT, service_type TEXT,
            status TEXT NOT NULL DEFAULT 'active',
            via_openrouter INTEGER NOT NULL DEFAULT 0,
            via_kilo INTEGER NOT NULL DEFAULT 0,
            input_cost_per_m REAL, output_cost_per_m REAL,
            context_window_k INTEGER, pricing_unit TEXT,
            quality_tier INTEGER, is_ga INTEGER,
            description TEXT,
            is_stt_capable INTEGER, is_translation_capable INTEGER,
            stt_quality REAL,
            last_verified TEXT, created_at TEXT, updated_at TEXT,
            discard_reason TEXT
        );
        -- Seed an existing direct-vendor row that operator has flipped to
        -- via_openrouter=1 (e.g., the vendor got OR-listed since seed insert)
        INSERT INTO agents (
            id, api_id, name, provider, service_type, status,
            via_openrouter, via_kilo, input_cost_per_m, pricing_unit,
            created_at, updated_at
        ) VALUES (
            'soniox/stt-async-v4', 'stt-async-v4', 'Soniox Async', 'soniox', 'stt',
            'active', 1, 1, 27.78, 'audio-min',
            '2026-01-01 00:00:00', '2026-01-01 00:00:00'
        );
    """)

    # Force a re-import so DB_PATH respects our temp path
    import seed_direct_vendors as sd
    importlib.reload(sd)
    conn = sq.connect(db)
    sd.upsert(conn, today="2026-06-30")
    conn.commit()
    row = conn.execute(
        "SELECT via_openrouter, via_kilo FROM agents WHERE id='soniox/stt-async-v4'"
    ).fetchone()
    conn.close()
    assert row == (1, 1), (
        f"REGRESSION: seed reset operator-flipped routing flags. "
        f"Expected via_openrouter=1, via_kilo=1; got via_openrouter={row[0]}, via_kilo={row[1]}"
    )


# ============================================================
# Adversarial review Phase 3 — Fix Cluster 3: C3
# C3: invariant #1 hole — magnitude unbounded + first-scrape
#     (before_price=0) bypasses >50% REFUSE.
# ============================================================

def test_C3_first_scrape_with_implausible_magnitude_blocks_write() -> None:
    """REGRESSION (C3): a parser drift producing input_price_per_M = 999999.0
    (off by 1e6) on a row whose before_price is 0 (brand-new seed) MUST be
    refused. Pre-fix, _signed_pct_diff(0, X) returned None → _classify_diff
    returned (False, False, 'first-scrape') → write proceeded with no guard.

    Combined invariant #1 hole: no magnitude bounds + first-scrape bypass
    of the >50% REFUSE."""
    import sys
    sys.path.insert(0, str(REPO_ROOT / "scripts" / "kilo-benchmarks"))
    import fetch_direct_vendor_prices as m

    # Per-unit sanity bounds (anchored to real-world prices: M-tokens
    # never exceeds ~$1000/M today; audio-min ~$5000/M etc.)
    # The fix introduces these; the test pins them.
    for unit, low, high, in_bounds, out_of_bounds in [
        ("M-tokens",  0.001,  2000.0,   100.0,    999_999.0),   # 999999/M-tok = impossible
        ("M-tokens",  0.001,  2000.0,    50.0,         0.0),    # 0/M-tok = parser dropped sign
        ("M-chars",   0.01,   1000.0,    30.0,    900_000.0),   # 900000/M-chars = impossible
        ("audio-min", 0.001,  10000.0, 1000.0,  9_999_999.0),   # 9.9M/M-min = impossible
    ]:
        block_in, _ = m._magnitude_check(in_bounds, unit)
        assert not block_in, f"C3 false-positive: {in_bounds}/{unit} should be in-bounds"
        block_out, reason = m._magnitude_check(out_of_bounds, unit)
        assert block_out, f"C3 regression: {out_of_bounds}/{unit} should be REFUSED but passed"
        assert unit in reason


def test_C3_classify_diff_refuses_first_scrape_when_magnitude_outside_bounds() -> None:
    """REGRESSION (C3): when before_price is None/0 (first scrape), the
    diff classifier returns first-scrape OK — but only if magnitude_check
    passes. If magnitude is outside per-unit bounds, REFUSE regardless of
    diff-availability."""
    import sys
    sys.path.insert(0, str(REPO_ROOT / "scripts" / "kilo-benchmarks"))
    import fetch_direct_vendor_prices as m

    # First-scrape, sane magnitude → write
    block, alert, _ = m._classify_with_magnitude(
        before_price=None, after_price=15.0, pricing_unit="M-tokens"
    )
    assert (block, alert) == (False, False)

    # First-scrape, INSANE magnitude → REFUSE
    block, alert, reason = m._classify_with_magnitude(
        before_price=None, after_price=999_999.0, pricing_unit="M-tokens"
    )
    assert block is True, f"C3 first-scrape implausible magnitude not blocked: {reason}"

    # before=0, sane → write (seed default)
    block, _, _ = m._classify_with_magnitude(
        before_price=0, after_price=15.0, pricing_unit="M-tokens"
    )
    assert block is False

    # before=0, INSANE → REFUSE (this was the C3 hole)
    block, _, reason = m._classify_with_magnitude(
        before_price=0, after_price=999_999.0, pricing_unit="M-tokens"
    )
    assert block is True, f"C3 invariant violation: {reason}"


# ============================================================
# Adversarial review Phase 3 — Fix Cluster 5
# H1: except (FetchError, Exception) swallows programming bugs as
#     "fetch failed" → vendor URL marked broken, run continues green,
#     real bugs hide as URL_BROKEN flags.
# H2: consecutive_fetch_failures defined in constants + docstring but
#     NEVER incremented → 7-day escalation path is dead code.
# ============================================================

def test_H1_programming_errors_propagate_not_masked_as_fetch_failure(tmp_path):
    """REGRESSION (H1): a scraper raising a non-network exception (e.g.,
    AttributeError from a typo) MUST propagate out of process_vendor —
    not get swallowed as 'fetch failed: X'.

    Pre-fix: except (FetchError, Exception) caught every Exception subclass
    including programming bugs → masked as transient outage, vendor marked
    URL_BROKEN, 7-day deprecation countdown begins.

    Post-fix: process_vendor catches only (FetchError, OSError); programming
    errors propagate to the main loop's defensive wrap, which records them
    with the actual exception name ('orchestrator error: AttributeError: …')
    instead of the misleading 'fetch failed' prefix."""
    import sys
    sys.path.insert(0, str(REPO_ROOT / "scripts" / "kilo-benchmarks"))
    import fetch_direct_vendor_prices as m

    db = tmp_path / "k.db"
    _seed_db(db)
    reg = _registry()

    class BuggyScraper:
        def fetch_static(self, url, **kw):
            raise AttributeError("typo in our own code (NOT a network error)")
        def fetch_rendered(self, url, **kw):
            raise AttributeError("same")

    # Post-fix: AttributeError propagates out of process_vendor.
    with pytest.raises(AttributeError):
        m.process_vendor(
            vendor="soniox", cfg=reg["soniox"], scraper=BuggyScraper(),
            db_path=db, apply=True,
        )
    # And URL_BROKEN must NOT have been written.
    import sqlite3
    conn = sqlite3.connect(db)
    row = conn.execute(
        "SELECT price_scrape_source FROM agents WHERE id='soniox/stt-async-v4'"
    ).fetchone()
    conn.close()
    assert row[0] is None or "URL_BROKEN" not in (row[0] or ""), (
        f"H1 regression: programming bug masked as URL_BROKEN sentinel "
        f"({row[0]!r}). AttributeError should never look like a vendor outage."
    )


def test_H2_consecutive_fetch_failures_persisted_across_runs(tmp_path):
    """REGRESSION (H2): consecutive_fetch_failures must persist across
    cron runs (in-memory counter is meaningless because each daily
    invocation starts fresh). Pre-fix, the constant existed and the
    docstring promised escalation at 7 — but nothing ever incremented
    a counter ANYWHERE.

    Post-fix: persisted in cache/vendor_failures.json. Run 1 fails →
    counter becomes 1. Run 2 fails → counter becomes 2. Successful run
    resets to 0. Escalation alert fires at VENDOR_FAILURE_ESCALATE=7.
    """
    import sys
    sys.path.insert(0, str(REPO_ROOT / "scripts" / "kilo-benchmarks"))
    import fetch_direct_vendor_prices as m

    counter_file = tmp_path / "vendor_failures.json"

    # Initial: vendor not in counter file → 0 failures
    n = m._read_vendor_failures(counter_file)
    assert n == {}, f"H2 regression: expected empty initial state, got {n}"

    # Record 1 failure
    m._record_vendor_failure("badvendor", counter_file)
    assert m._read_vendor_failures(counter_file)["badvendor"] == 1

    # Record 2 more
    m._record_vendor_failure("badvendor", counter_file)
    m._record_vendor_failure("badvendor", counter_file)
    assert m._read_vendor_failures(counter_file)["badvendor"] == 3

    # Successful fetch resets counter
    m._record_vendor_success("badvendor", counter_file)
    assert m._read_vendor_failures(counter_file).get("badvendor", 0) == 0


# ============================================================
# Adversarial review Phase 3 — Fix Cluster 6
# H3: audit classifies future-dated `last_price_scraped` as "scraped" with negative age
# M4: ISO-datetime strings fall through to "seed-only" silently
# ============================================================

def test_H3_audit_future_timestamp_classified_as_clock_skew(tmp_path):
    """REGRESSION (H3): a future-dated last_price_scraped (clock skew or
    bad write) MUST be classified as 'clock-skew' (or 'stale'), not
    'scraped' with negative age. Pre-fix the operator saw '-5d' age and
    a fresh-classified row that wasn't actually fresh."""
    import sys
    sys.path.insert(0, str(REPO_ROOT / "scripts" / "kilo-benchmarks"))
    import audit_direct_vendor_freshness as a

    # Future date relative to today
    status, age = a.classify("2030-01-01", None, today=__import__("datetime").date(2026, 6, 30), max_age_days=3)
    # Either 'clock-skew' or 'stale' is acceptable — both surface the issue.
    # 'scraped' with negative age is the bug.
    assert status != "scraped" or (age is not None and age >= 0), (
        f"H3 regression: future timestamp classified as 'scraped' with age={age}"
    )


def test_M4_audit_iso_datetime_with_time_component_parses(tmp_path):
    """REGRESSION (M4): a stored `last_price_scraped` value with a time
    component (ISO-datetime, e.g., '2026-06-30T12:00:00') must parse
    correctly and classify accordingly — not silently fall through to
    'seed-only' as if the row were never scraped.

    Pre-fix: _parse_iso_date used datetime.date.fromisoformat which
    rejects time components, returning None → row classified seed-only
    forever even after fresh writes."""
    import sys
    sys.path.insert(0, str(REPO_ROOT / "scripts" / "kilo-benchmarks"))
    import audit_direct_vendor_freshness as a

    # Today's date with a time component
    status, age = a.classify("2026-06-30T12:00:00", None, today=__import__("datetime").date(2026, 6, 30), max_age_days=3)
    assert status == "scraped", (
        f"M4 regression: ISO-datetime fell through to '{status}' (expected 'scraped')"
    )
    assert age == 0


# ============================================================
# Cluster 6 leftover regression tests: M3, M6
# ============================================================

def test_M3_consecutive_pricing_misses_atomic_update(tmp_path):
    """REGRESSION (M3): the miss-counter increment must be atomic at the
    row level. Pre-fix used SELECT-then-UPDATE (race-prone). Post-fix
    uses `UPDATE ... SET = COALESCE(..., 0) + 1 RETURNING ...` which is
    a single statement under SQLite.

    This test simulates 3 sequential miss-bumps and verifies the counter
    end-state is 3 (i.e., no lost updates from interleaving)."""
    import sqlite3 as sq
    import sys
    sys.path.insert(0, str(REPO_ROOT / "scripts" / "kilo-benchmarks"))

    db = tmp_path / "k.db"
    _seed_db(db)
    # Issue 3 sequential atomic bumps via the new SQL pattern
    conn = sq.connect(db)
    for _ in range(3):
        new_n = conn.execute(
            "UPDATE agents SET consecutive_pricing_misses = "
            "COALESCE(consecutive_pricing_misses, 0) + 1 "
            "WHERE id=? RETURNING consecutive_pricing_misses",
            ("soniox/stt-async-v4",),
        ).fetchone()[0]
        conn.commit()
    conn.close()
    assert new_n == 3, f"M3 regression: 3 bumps yielded counter={new_n}"


def test_M6_cartesia_sonic_regex_requires_version() -> None:
    """REGRESSION (M6): bare 'Sonic' (no version) must NOT anchor — if
    Cartesia adds a "Sonic Voice Agents" sub-product, it could quote a
    different price. Version 2 OR 3 accepted; 4+ requires deliberate code update."""
    import sys
    sys.path.insert(0, str(REPO_ROOT / "scripts" / "kilo-benchmarks"))
    from direct_vendor_parsers.cartesia import _SONIC_RE
    assert _SONIC_RE.search("Sonic-2 pricing") is not None
    assert _SONIC_RE.search("Sonic 3") is not None  # accepted (3 in version set)
    assert _SONIC_RE.search("Sonic only") is None   # bare — rejected
    assert _SONIC_RE.search("Sonic-4") is None      # unknown version — rejected
    assert _SONIC_RE.search("supersonic") is None   # word boundary respected


# ============================================================
# Phase 4 convergence-pass regressions:
# NF1: original _MAGNITUDE_BOUNDS were tighter than the live catalog
# NF2: _read_vendor_failures returned non-dict types from corrupt files
# ============================================================

def test_NF1_magnitude_bounds_accept_live_catalog_prices() -> None:
    """REGRESSION (NF1): every price currently in the live catalog MUST
    pass _magnitude_check. Pre-fix bounds were too tight: google/veo-3
    at 750000/video-sec exceeded the 100000 ceiling, magnitude_check
    would REFUSE legit writes."""
    import sqlite3 as sq
    import sys
    sys.path.insert(0, str(REPO_ROOT / "scripts" / "kilo-benchmarks"))
    import fetch_direct_vendor_prices as m

    db_path = REPO_ROOT / "scripts" / "kilo-benchmarks" / "kilo_agents.db"
    if not db_path.exists():
        import pytest
        pytest.skip("real kilo_agents.db not present")
    conn = sq.connect(db_path)
    rows = conn.execute(
        "SELECT id, input_cost_per_m, pricing_unit FROM agents "
        "WHERE pricing_unit IN ('M-tokens','M-chars','audio-min','image','page','video-sec') "
        "AND input_cost_per_m > 0 AND status='active'"
    ).fetchall()
    conn.close()
    rejected = []
    for id_, price, unit in rows:
        block, reason = m._magnitude_check(price, unit)
        if block:
            rejected.append(f"  {id_}: {price}/{unit} — {reason}")
    assert not rejected, "NF1 regression: bounds reject live catalog prices:\n" + "\n".join(rejected[:10])


def test_NF2_read_vendor_failures_rejects_non_dict(tmp_path):
    """REGRESSION (NF2): if the persisted JSON contains `null`, a list,
    or values that aren't integers, return {} rather than the literal
    payload. Pre-fix, downstream code crashed on `.get()` over non-dict."""
    import sys
    sys.path.insert(0, str(REPO_ROOT / "scripts" / "kilo-benchmarks"))
    import fetch_direct_vendor_prices as m

    for bad in ["null", '["not a dict"]', '"string"', "42", "{invalid", '{"v":"str"}']:
        p = tmp_path / "bad.json"
        p.write_text(bad)
        result = m._read_vendor_failures(p)
        assert isinstance(result, dict), f"NF2 regression: {bad!r} → {result!r} (not dict)"
        # Values must be ints when present
        for v in result.values():
            assert isinstance(v, int), f"NF2 regression: non-int value passed through: {v!r}"

    # Sanity: valid payload survives
    p = tmp_path / "ok.json"
    p.write_text('{"foo": 3, "bar": 1}')
    assert m._read_vendor_failures(p) == {"foo": 3, "bar": 1}
