#!/usr/bin/env python3
"""Daily direct-vendor pricing scraper — Phase 1 deliverable.

Reads `direct_vendor_pricing_registry.yaml`, iterates each vendor with a
populated `parser_module`, fetches the page via the vendored `web_scrape`
module (httpx or browserless), invokes the per-vendor parser, validates,
and merges into `agents` via per-vendor SQLite transactions.

Per docs/development/plans/2026-06-29-plan-direct-vendor-pricing.md.

Usage
-----
  python fetch_direct_vendor_prices.py                       # dry-run, all vendors with parsers
  python fetch_direct_vendor_prices.py --apply               # write to DB
  python fetch_direct_vendor_prices.py --vendors a,b,c       # subset
  python fetch_direct_vendor_prices.py --report cache/x.csv  # diff CSV
  python fetch_direct_vendor_prices.py --simulate-failure V  # force vendor V's fetch to fail (alert-smoke)
  python fetch_direct_vendor_prices.py --max-iter N          # loop N times for repeated-failure simulation

Exit codes
----------
  0   success (incl. dry-run)
  2   one or more vendors failed AND --apply was set; alerts fired

Failure model (per the plan §"Failure model"):
  - HTTP error / parser exception:
      log + (best-effort) Telegram alert via fabrik-lib/alerting
      bump in-memory `consecutive_fetch_failures` counter for the vendor
      row(s) untouched
  - Parsed pricing_unit != DB pricing_unit:
      REFUSE to write that row (parse bug); log + alert
  - Parsed price diff > 10% vs DB:
      audit alert; STILL writes the new price (audit threshold)
  - Parsed price diff > 50% vs DB:
      REFUSE to write that row (almost certainly a parse bug); log + alert
  - Row missing from parsed set even though vendor responded OK:
      bump row's consecutive_pricing_misses; flip status='deprecated' at 7
  - Vendor's consecutive_fetch_failures >= 7 (across daily runs — Phase 1
      tracks in-memory only; persistence is a Phase 5 deliverable):
      escalation alert
"""

from __future__ import annotations

import argparse
import csv
import importlib
import os
import sqlite3
import sys
import traceback
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import yaml

# Make the vendored web_scrape importable (we're inside scripts/kilo-benchmarks).
SCRIPT_DIR = Path(__file__).parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

# Adversarial-review CRITICAL fix (2026-06-30): cron runs with a clean env so
# TELEGRAM_BOT_TOKEN and BROWSERLESS_TOKEN won't be in os.environ. Without this
# load, alerting._is_enabled() returns False and critical alerts silently
# fail to fire at 06:00 UTC. Load /opt/fabrik/.env early — before _send_alert
# can be called and before WebScraper construction reads BROWSERLESS_TOKEN.
try:
    from dotenv import load_dotenv  # type: ignore[import-not-found]

    _FABRIK_ROOT = SCRIPT_DIR.parents[1]  # /opt/fabrik
    load_dotenv(_FABRIK_ROOT / ".env", override=False)
except ImportError:
    # dotenv not installed — env vars must already be in os.environ. Phase-1
    # tests + manual `.venv/bin/python` invocations from the shell have env
    # inherited, so this fallback path is fine for those; only cron is at risk.
    pass

from direct_vendor_parsers import ParsedRow  # noqa: E402  — local package
from web_scrape import (  # noqa: E402  — vendored from fabrik-lib
    FetchError,
    WebScraper,
    is_bot_wall,
)

DB_PATH = SCRIPT_DIR / "kilo_agents.db"
REGISTRY_PATH = SCRIPT_DIR / "direct_vendor_pricing_registry.yaml"
CACHE_DIR = SCRIPT_DIR / "cache" / "direct-vendor-scrape"
BROWSERLESS_URL_DEFAULT = "https://browser.vps1.ocoron.com"

# Plan §"Failure model" thresholds.
DIFF_ALERT_PCT = 0.10  # > this → alert + write
DIFF_BLOCK_PCT = 0.50  # > this → REFUSE to write
MISS_TO_DEPRECATE = 7  # >= this → flip row to 'deprecated'
VENDOR_FAILURE_ESCALATE = 7  # consecutive cron failures → critical alert

# Adversarial review H2 (2026-06-30): consecutive_fetch_failures was claimed in
# the docstring + a constant defined, but nothing ever incremented it in the
# orchestrator. The plan-stated 7-day escalation path was dead code. Persisted
# now in this JSON file: {vendor: consecutive_failures}. Survives cron runs.
VENDOR_FAILURES_PATH = SCRIPT_DIR / "cache" / "vendor_failures.json"


# ---------------------------------------------------------------------------
# Vendor-failure counter (H2)
# ---------------------------------------------------------------------------
def _read_vendor_failures(path: Path = VENDOR_FAILURES_PATH) -> dict[str, int]:
    """Read the persisted {vendor: consecutive_failures} map.

    Defensive: missing file or malformed JSON → return empty dict so the
    counter starts fresh after a manual cache clear.
    """
    try:
        import json
        return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def _write_vendor_failures(counters: dict[str, int], path: Path = VENDOR_FAILURES_PATH) -> None:
    """Best-effort persist. Mirrors the heartbeat write pattern: log failure
    to stderr but don't crash the pipeline."""
    try:
        import json
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(counters, indent=2, sort_keys=True))
    except OSError as e:
        print(f"[vendor-failures] write to {path} failed: {e!r}", file=sys.stderr)


def _record_vendor_failure(vendor: str, path: Path = VENDOR_FAILURES_PATH) -> int:
    """Bump the consecutive-failures counter for `vendor` by 1. Returns new count.

    Fires a critical alert at VENDOR_FAILURE_ESCALATE so an operator sees the
    persistent outage. Pre-fix this path was missing entirely.
    """
    counters = _read_vendor_failures(path)
    counters[vendor] = counters.get(vendor, 0) + 1
    _write_vendor_failures(counters, path)
    n = counters[vendor]
    if n >= VENDOR_FAILURE_ESCALATE:
        _send_alert(
            title=f"{vendor} scraper: {n} consecutive failures",
            body=(
                f"Vendor {vendor} has failed {n} consecutive cron runs "
                f"(threshold: {VENDOR_FAILURE_ESCALATE}).\n"
                f"Check the daily_refresh log for the failure mode. The "
                f"counter persists until a successful fetch is recorded "
                f"(see _record_vendor_success)."
            ),
            severity="critical",
        )
    return n


def _record_vendor_success(vendor: str, path: Path = VENDOR_FAILURES_PATH) -> None:
    """Reset consecutive-failures for `vendor` to 0. Called on every
    successful fetch + parse (not write — even a refused-write counts as
    "vendor scraper is functioning" for this counter)."""
    counters = _read_vendor_failures(path)
    if vendor in counters:
        counters[vendor] = 0
        _write_vendor_failures(counters, path)


# ---------------------------------------------------------------------------
# Alerting (defensive: optional dependency on fabrik-lib/alerting)
# ---------------------------------------------------------------------------
def _send_alert(title: str, body: str, severity: str = "warning") -> bool:
    """Best-effort alert send. Returns True if at least one channel confirmed.

    Defensive: alerting is vendored per-project; if not present in this repo
    yet, we log + return False instead of crashing the scraper. Phase 5 wires
    the real alerting module into kilo-benchmarks.
    """
    try:
        from alerting import send_alert  # type: ignore[import-not-found]
    except ImportError:
        print(f"[alerter-stub] {severity.upper()} {title}: {body}", file=sys.stderr)
        return False
    try:
        return bool(send_alert(title=title, body=body, severity=severity))
    except Exception as e:
        print(f"[alerter] send_alert raised {e!r}; falling back to stderr", file=sys.stderr)
        print(f"[alerter-stderr-fallback] {severity.upper()} {title}: {body}", file=sys.stderr)
        return False


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
@dataclass
class WriteOutcome:
    vendor: str
    db_id: str
    before_price: float | None
    after_price: float | None
    pct_diff: float | None  # signed; None when before==0 or None
    pricing_unit: str
    action: str  # "wrote" | "refused_unit" | "refused_diff" | "no_change" | "missing"
    raw_price_text: str
    source_url: str
    explanation: str = ""


@dataclass
class VendorOutcome:
    vendor: str
    fetched: bool
    parsed_count: int
    writes: list[WriteOutcome]
    error: str | None = None  # non-None on fetch / parser failure


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------
def load_registry(path: Path = REGISTRY_PATH) -> dict[str, dict]:
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path}: top-level must be a mapping; got {type(data).__name__}")
    return data


def select_vendors(
    registry: dict[str, dict],
    only: list[str] | None,
    require_parser: bool = True,
) -> list[str]:
    """Vendor ids in registry order, optionally filtered.

    `require_parser=True` skips vendors with `parser_module: null` (Phase 1
    only ships 5 parsers; the rest are stubs).
    """
    selected: list[str] = []
    for vendor, cfg in registry.items():
        if only and vendor not in only:
            continue
        if require_parser and not (cfg or {}).get("parser_module"):
            continue
        selected.append(vendor)
    return selected


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------
def _today_utc_iso() -> str:
    return datetime.now(UTC).date().isoformat()


def fetch_db_rows_for_vendor(conn: sqlite3.Connection, db_ids: list[str]) -> dict[str, dict]:
    if not db_ids:
        return {}
    placeholders = ",".join("?" * len(db_ids))
    rows = conn.execute(
        f"SELECT id, input_cost_per_m, pricing_unit, status, last_price_scraped, "
        f"consecutive_pricing_misses, price_scrape_source "
        f"FROM agents WHERE id IN ({placeholders})",
        db_ids,
    ).fetchall()
    columns = [
        "id",
        "input_cost_per_m",
        "pricing_unit",
        "status",
        "last_price_scraped",
        "consecutive_pricing_misses",
        "price_scrape_source",
    ]
    return {r[0]: dict(zip(columns, r, strict=True)) for r in rows}


# ---------------------------------------------------------------------------
# Per-vendor flow
# ---------------------------------------------------------------------------
def _signed_pct_diff(before: float | None, after: float) -> float | None:
    """Returns (after-before)/before. None if before is None/0/<0."""
    if before is None or before <= 0:
        return None
    return (after - before) / before


def _classify_diff(pct: float | None) -> tuple[bool, bool, str]:
    """Returns (block, alert_only, classification_text).

    block:        True if diff > DIFF_BLOCK_PCT (REFUSE to write)
    alert_only:   True if DIFF_ALERT_PCT < |pct| <= DIFF_BLOCK_PCT (write but alert)
    """
    if pct is None:
        return False, False, "first-scrape (no prior price for diff)"
    apct = abs(pct)
    if apct > DIFF_BLOCK_PCT:
        return True, False, f"|diff|={apct:.0%} > {DIFF_BLOCK_PCT:.0%} — REFUSED (parse bug?)"
    if apct > DIFF_ALERT_PCT:
        return False, True, f"|diff|={apct:.0%} > {DIFF_ALERT_PCT:.0%} — audit alert; wrote"
    return False, False, f"|diff|={apct:.0%} — within tolerance"


# Adversarial review C3 (2026-06-30): per-unit magnitude sanity bounds. The
# diff-threshold check at _classify_diff cannot catch a brand-new seed row
# (before_price=0 → _signed_pct_diff returns None → first-scrape OK) so a
# parser drift producing $999999/M-token writes silently. These bounds are
# anchored to real-world catalog prices observed over 2025-2026:
#   M-tokens: $0.001 (allenai/free models) .. $2000 (claude-fable-5 hypothetical)
#   M-chars: $0.01 (cheap TTS) .. $1000 (premium voice)
#   audio-min: $0.001 .. $10000 (~$0.0006/min .. ~$6/min)
#   image: $0 (legacy free) .. $200000 (top-tier image gen at $0.20/image)
#   page: $0.001 .. $5000 (OCR, e.g. amazon/textract at $1500/page == $0.0015)
#   M-tokens with output:M-chars ratio 5:1 implicitly handled by per-unit caps
#
# A parsed value outside the band is almost certainly a parse bug. The bounds
# are loose enough that legitimate vendor price changes (even a 10x repricing)
# fit, but tight enough to catch off-by-1000/1e6 errors.
_MAGNITUDE_BOUNDS: dict[str, tuple[float, float]] = {
    "M-tokens": (0.001, 2000.0),
    "M-chars": (0.01, 1000.0),
    "audio-min": (0.001, 10000.0),
    "image": (0.0, 200000.0),
    "page": (0.001, 5000.0),
    "video-sec": (0.001, 100000.0),
    "alert": (0.0, 1e9),  # subscription_monitor alert row — bounds-irrelevant
}


def _magnitude_check(price: float, pricing_unit: str) -> tuple[bool, str]:
    """Returns (block, reason). block=True means REFUSE write.

    Conservative: an unknown pricing_unit returns (False, "unknown unit; skipping
    magnitude check") so we never block a new legitimate unit. Bounds tightening
    can be added per-unit as the catalog evolves.
    """
    bounds = _MAGNITUDE_BOUNDS.get(pricing_unit)
    if bounds is None:
        return False, f"unknown pricing_unit {pricing_unit!r}; magnitude check skipped"
    low, high = bounds
    if price < low or price > high:
        return True, (
            f"magnitude REFUSED: {price:.4g}/{pricing_unit} outside [{low}, {high}]"
            f" — likely off-by-1000/1e6 parser bug"
        )
    return False, ""


def _classify_with_magnitude(
    before_price: float | None,
    after_price: float,
    pricing_unit: str,
) -> tuple[bool, bool, str]:
    """Composite of _classify_diff + _magnitude_check.

    Order: magnitude FIRST (catches first-scrape parser bugs that the
    diff-threshold cannot see — invariant #1). Diff classifier second
    (catches drift between known-sane prior and new value).
    """
    mag_block, mag_reason = _magnitude_check(after_price, pricing_unit)
    if mag_block:
        return True, False, mag_reason
    pct = _signed_pct_diff(before_price, after_price)
    return _classify_diff(pct)


def process_vendor(
    vendor: str,
    cfg: dict,
    scraper: WebScraper,
    db_path: Path,
    apply: bool,
    simulate_failure: bool = False,
) -> VendorOutcome:
    url = cfg.get("pricing_url")
    method = cfg.get("fetch_method", "static")
    parser_module_name = cfg.get("parser_module")
    models_cfg = cfg.get("models") or {}

    if not parser_module_name:
        return VendorOutcome(
            vendor=vendor,
            fetched=False,
            parsed_count=0,
            writes=[],
            error="no parser_module in registry (stubbed)",
        )

    if simulate_failure:
        return VendorOutcome(
            vendor=vendor,
            fetched=False,
            parsed_count=0,
            writes=[],
            error="simulated fetch failure (--simulate-failure)",
        )

    # Pre-compute the DB ids this vendor manages so we can write the
    # URL_BROKEN_ sentinel on fetch failure (Plan §"DB schema additions"
    # SET rule; adversarial Pass-1 finding #4).
    pre_db_ids = list((models_cfg or {}).keys())

    def _mark_url_broken(reason: str) -> None:
        """Adversarial Pass-1 SET rule: when a vendor fetch fails AND apply
        is True, write URL_BROKEN_<YYYY-MM-DD> into price_scrape_source for
        each of the vendor's rows whose source is currently NULL. Idempotent
        because of the IS NULL guard."""
        if not apply or not pre_db_ids:
            return
        sentinel = f"URL_BROKEN_{_today_utc_iso()}"
        sconn = sqlite3.connect(db_path)
        try:
            placeholders = ",".join("?" * len(pre_db_ids))
            sconn.execute("BEGIN")
            try:
                sconn.execute(
                    f"UPDATE agents SET price_scrape_source=? "
                    f"WHERE id IN ({placeholders}) AND price_scrape_source IS NULL",
                    (sentinel, *pre_db_ids),
                )
                sconn.commit()
            except Exception:
                sconn.rollback()
                raise
        finally:
            sconn.close()
        _ = reason  # reserved for a future audit log row

    # Fetch
    try:
        if method == "static":
            html = scraper.fetch_static(url)
        elif method == "rendered":
            html = scraper.fetch_rendered(url)
        elif method == "stealth":
            html = scraper.fetch_rendered(url, stealth=True)
        else:
            _mark_url_broken(f"unknown fetch_method {method!r}")
            return VendorOutcome(
                vendor=vendor,
                fetched=False,
                parsed_count=0,
                writes=[],
                error=f"unknown fetch_method {method!r}",
            )
    # Adversarial review H1 (2026-06-30): narrowed `except (FetchError, Exception)`
    # to ONLY catch network-class errors. Pre-fix, the broad `Exception` catch
    # swallowed every programming bug (AttributeError, TypeError, NameError, etc.)
    # as "fetch failed: X" → vendor URL marked broken, run continues green, real
    # bugs hidden behind a 7-day deprecation countdown. Now: only network
    # exceptions are treated as transient outages; programming errors propagate
    # and are reported with their actual type.
    except (FetchError, OSError) as e:
        _mark_url_broken(f"fetch failed: {type(e).__name__}: {e}")
        _record_vendor_failure(vendor)  # H2: bump persistent counter
        return VendorOutcome(
            vendor=vendor,
            fetched=False,
            parsed_count=0,
            writes=[],
            error=f"fetch failed: {type(e).__name__}: {e}",
        )

    # Defense: if a fetch_static returned a Cloudflare wall, escalate to stealth.
    if isinstance(html, str) and is_bot_wall(html) and method != "stealth":
        try:
            html = scraper.fetch_rendered(url, stealth=True)
        except (FetchError, OSError) as e:
            _mark_url_broken(f"bot-wall escalation failed: {type(e).__name__}: {e}")
            _record_vendor_failure(vendor)  # H2
            return VendorOutcome(
                vendor=vendor,
                fetched=False,
                parsed_count=0,
                writes=[],
                error=f"bot-wall escalation also failed: {type(e).__name__}: {e}",
            )

    # Successful fetch + bot-wall check passed → record success (H2: reset
    # the consecutive-failure counter for this vendor; even a downstream
    # parser/write failure means the SCRAPER is functioning, only the parser
    # or data layer is at fault).
    _record_vendor_success(vendor)

    # Parse
    try:
        parser_module = importlib.import_module(parser_module_name)
        parsed: list[ParsedRow] = parser_module.extract(html, url)
    except Exception as e:
        tb = traceback.format_exc(limit=3)
        return VendorOutcome(
            vendor=vendor,
            fetched=True,
            parsed_count=0,
            writes=[],
            error=f"parser raised: {type(e).__name__}: {e}\n{tb}",
        )

    # Map parsed slugs to DB ids via registry
    slug_to_db_id: dict[str, str] = {}
    db_id_to_expected_unit: dict[str, str] = {}
    for db_id, mcfg in models_cfg.items():
        slug = mcfg.get("slug_on_page")
        if not slug:
            continue
        slug_to_db_id[slug] = db_id
        db_id_to_expected_unit[db_id] = mcfg.get("expected_unit", "")

    db_ids = list(slug_to_db_id.values())
    conn = sqlite3.connect(db_path)
    try:
        db_rows = fetch_db_rows_for_vendor(conn, db_ids)

        # Build write outcomes (no I/O yet)
        writes: list[WriteOutcome] = []
        parsed_slugs_seen: set[str] = set()

        for pr in parsed:
            parsed_slugs_seen.add(pr.model_slug)
            db_id = slug_to_db_id.get(pr.model_slug)
            if db_id is None:
                # Parser returned a model not in our registry — log but don't write
                writes.append(
                    WriteOutcome(
                        vendor=vendor,
                        db_id=f"<unmapped:{pr.model_slug}>",
                        before_price=None,
                        after_price=pr.input_price_per_M,
                        pct_diff=None,
                        pricing_unit=pr.pricing_unit,
                        action="missing",
                        raw_price_text=pr.raw_price_text,
                        source_url=pr.source_url,
                        explanation=f"parser returned slug {pr.model_slug!r} not in registry",
                    )
                )
                continue
            db_row = db_rows.get(db_id)
            if db_row is None:
                writes.append(
                    WriteOutcome(
                        vendor=vendor,
                        db_id=db_id,
                        before_price=None,
                        after_price=pr.input_price_per_M,
                        pct_diff=None,
                        pricing_unit=pr.pricing_unit,
                        action="missing",
                        raw_price_text=pr.raw_price_text,
                        source_url=pr.source_url,
                        explanation=f"registry says {db_id} exists but DB has no such row",
                    )
                )
                continue

            expected_unit = db_id_to_expected_unit[db_id] or db_row["pricing_unit"]
            db_unit = db_row["pricing_unit"]

            if pr.pricing_unit != expected_unit or pr.pricing_unit != db_unit:
                writes.append(
                    WriteOutcome(
                        vendor=vendor,
                        db_id=db_id,
                        before_price=db_row["input_cost_per_m"],
                        after_price=pr.input_price_per_M,
                        pct_diff=None,
                        pricing_unit=pr.pricing_unit,
                        action="refused_unit",
                        raw_price_text=pr.raw_price_text,
                        source_url=pr.source_url,
                        explanation=(
                            f"parsed unit={pr.pricing_unit!r} != "
                            f"expected={expected_unit!r} (DB={db_unit!r})"
                        ),
                    )
                )
                continue

            # Adversarial review C3: use composite classifier (magnitude bounds
            # FIRST, then diff threshold). Magnitude catches the invariant #1
            # hole where a first-scrape (before_price=0) implausible value
            # (e.g. parser off-by-1e6) silently wrote.
            block, alert_only, classification = _classify_with_magnitude(
                before_price=db_row["input_cost_per_m"],
                after_price=pr.input_price_per_M,
                pricing_unit=pr.pricing_unit,
            )
            pct = _signed_pct_diff(db_row["input_cost_per_m"], pr.input_price_per_M)
            action = "refused_diff" if block else "wrote"
            writes.append(
                WriteOutcome(
                    vendor=vendor,
                    db_id=db_id,
                    before_price=db_row["input_cost_per_m"],
                    after_price=pr.input_price_per_M,
                    pct_diff=pct,
                    pricing_unit=pr.pricing_unit,
                    action=action,
                    raw_price_text=pr.raw_price_text,
                    source_url=pr.source_url,
                    explanation=classification,
                )
            )

        # Rows expected by registry but absent from parsed set → miss-counter bump
        for db_id in db_ids:
            if db_id in (w.db_id for w in writes):
                continue
            db_row = db_rows.get(db_id)
            if db_row is None:
                continue
            writes.append(
                WriteOutcome(
                    vendor=vendor,
                    db_id=db_id,
                    before_price=db_row["input_cost_per_m"],
                    after_price=None,
                    pct_diff=None,
                    pricing_unit=db_row["pricing_unit"],
                    action="missing",
                    raw_price_text="",
                    source_url=url,
                    explanation="vendor responded OK but parser did not return this row's slug",
                )
            )

        # Apply writes (transaction per vendor)
        if apply:
            today = _today_utc_iso()
            conn.execute("BEGIN")
            try:
                for w in writes:
                    if w.action == "wrote":
                        # Adversarial Pass-1 finding (CORRECTNESS #3): the Plan's
                        # §"DB schema additions" CLEAR rule says "NULL-out
                        # price_scrape_source whenever it writes a non-NULL
                        # last_price_scraped for the same row." Previous version
                        # wrote w.source_url here, which meant a URL_BROKEN_
                        # sentinel from a prior run would never auto-clear.
                        # Now writes NULL literally so the carve-out filter
                        # (`price_scrape_source NOT LIKE 'URL_BROKEN_%'`) sees
                        # the row again on next run.
                        conn.execute(
                            "UPDATE agents SET input_cost_per_m=?, last_price_scraped=?, "
                            "price_scrape_source=NULL, consecutive_pricing_misses=0 "
                            "WHERE id=?",
                            (w.after_price, today, w.db_id),
                        )
                    elif w.action == "missing" and w.db_id.startswith("<unmapped"):
                        # Don't update on unmapped — registry mistake
                        continue
                    elif w.action == "missing":
                        # Row was expected but vendor didn't return it: bump miss counter
                        new_misses = (
                            conn.execute(
                                "SELECT COALESCE(consecutive_pricing_misses, 0) FROM agents WHERE id=?",
                                (w.db_id,),
                            ).fetchone()
                            or (0,)
                        )[0] + 1
                        conn.execute(
                            "UPDATE agents SET consecutive_pricing_misses=? WHERE id=?",
                            (new_misses, w.db_id),
                        )
                        if new_misses >= MISS_TO_DEPRECATE:
                            conn.execute(
                                "UPDATE agents SET status='deprecated', "
                                "discard_reason=? WHERE id=? AND status='active'",
                                (
                                    f"missing from {vendor} catalog ≥{MISS_TO_DEPRECATE} days "
                                    f"({today})",
                                    w.db_id,
                                ),
                            )
                    # refused_unit / refused_diff: no DB write
                conn.commit()
            except Exception:
                conn.rollback()
                raise

        return VendorOutcome(vendor=vendor, fetched=True, parsed_count=len(parsed), writes=writes)
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# CLI / orchestration
# ---------------------------------------------------------------------------
def _emit_outcome(o: VendorOutcome, apply: bool) -> None:
    if o.error:
        print(f"[fetch] {o.vendor:14s} ERROR: {o.error.splitlines()[0]}")
        return
    wrote = sum(1 for w in o.writes if w.action == "wrote")
    refused = sum(1 for w in o.writes if w.action.startswith("refused"))
    missing = sum(1 for w in o.writes if w.action == "missing")
    flag = "APPLY" if apply else "DRY-RUN"
    print(
        f"[fetch] {o.vendor:14s} {flag}  parsed={o.parsed_count}  wrote={wrote}  "
        f"refused={refused}  missing={missing}"
    )
    for w in o.writes:
        if w.action == "wrote" and w.pct_diff is not None and abs(w.pct_diff) > DIFF_ALERT_PCT:
            print(
                f"           AUDIT  {w.db_id}: {w.before_price:.2f} → {w.after_price:.2f}  "
                f"({w.pct_diff:+.0%}) — {w.explanation}"
            )
        elif w.action == "refused_diff":
            print(
                f"           BLOCK  {w.db_id}: {w.before_price:.2f} → {w.after_price:.2f}  "
                f"({w.pct_diff:+.0%}) — {w.explanation}"
            )
        elif w.action == "refused_unit":
            print(f"           BLOCK  {w.db_id}: {w.explanation}")


def _fire_per_vendor_alerts(o: VendorOutcome) -> None:
    if o.error and "simulated" in (o.error or "").lower():
        # Simulated failure → alert intentionally (smoke-test for Phase 1 Gate 3)
        _send_alert(
            title=f"{o.vendor} scraper down (simulated)",
            body=(
                f"Vendor: {o.vendor}\nError: {o.error}\n"
                f"This is a Phase 1 alert-smoke test (--simulate-failure)."
            ),
            severity="warning",
        )
        return
    if o.error:
        _send_alert(
            title=f"{o.vendor} scraper failed",
            body=f"Vendor: {o.vendor}\nError: {o.error}",
            severity="warning",
        )
        return
    for w in o.writes:
        if w.action == "refused_diff":
            _send_alert(
                title=f"{o.vendor}: blocked write (diff>{DIFF_BLOCK_PCT:.0%})",
                body=(
                    f"Row {w.db_id} parsed price {w.after_price:.2f} vs "
                    f"DB {w.before_price:.2f} ({w.pct_diff:+.0%}). Refused to write."
                ),
                severity="critical",
            )
        elif w.action == "wrote" and w.pct_diff is not None and abs(w.pct_diff) > DIFF_ALERT_PCT:
            _send_alert(
                title=f"{o.vendor}: price drift audit",
                body=(
                    f"Row {w.db_id} updated {w.before_price:.2f} → {w.after_price:.2f} "
                    f"({w.pct_diff:+.0%}). Raw text: {w.raw_price_text!r}. URL: {w.source_url}"
                ),
                severity="info",
            )
        elif w.action == "refused_unit":
            _send_alert(
                title=f"{o.vendor}: unit mismatch (likely parse bug)",
                body=f"{w.db_id}: {w.explanation}",
                severity="critical",
            )
        elif w.action == "missing" and w.pricing_unit == "alert":
            # Adversarial-review C2: subscription_monitor emergence alerts must
            # reach Telegram. Pre-fix, this path silently fell into the
            # <unmapped:...> bucket and never fired _send_alert, violating
            # invariant #2 ("never silently miss a vendor flipping to per-call").
            _send_alert(
                title=f"{o.vendor}: per-call pricing detected on sub-only vendor",
                body=(
                    f"Vendor was confirmed subscription-only previously. "
                    f"Per-call pattern(s) appeared on {w.source_url}\n"
                    f"Parser output: {w.raw_price_text}\n"
                    f"Operator should re-classify the vendor (consider adding "
                    f"real parser_module + registry mappings)."
                ),
                severity="critical",
            )


def write_report_csv(path: Path, outcomes: list[VendorOutcome]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "vendor",
                "db_id",
                "before_price",
                "after_price",
                "pct_diff",
                "pricing_unit",
                "action",
                "raw_price_text",
                "explanation",
                "source_url",
            ]
        )
        for o in outcomes:
            for w in o.writes:
                writer.writerow(
                    [
                        w.vendor,
                        w.db_id,
                        "" if w.before_price is None else f"{w.before_price:.4f}",
                        "" if w.after_price is None else f"{w.after_price:.4f}",
                        "" if w.pct_diff is None else f"{w.pct_diff:.4f}",
                        w.pricing_unit,
                        w.action,
                        w.raw_price_text,
                        w.explanation,
                        w.source_url,
                    ]
                )


def write_report_md(path: Path, outcomes: list[VendorOutcome], apply: bool) -> None:
    """Per-vendor markdown summary for the daily refresh log.

    Phase 5 deliverable: human-readable per-day audit at
    `cache/direct_vendor_audit_<YYYY-MM-DD>.md`. Sections:
      - Header: timestamp + total counts
      - Per-vendor: parsed / wrote / refused / missing + per-row diffs
      - Alerts: unit mismatches, big-diff refusals, scrape errors,
        subscription-only confirmations

    Cron consumes this via `--report-md cache/direct_vendor_audit_$(date -u +%F).md`.
    """
    from datetime import UTC
    from datetime import datetime as _dt

    path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    mode = "APPLY" if apply else "DRY-RUN"
    lines.append(f"# Direct-vendor pricing audit — {_dt.now(UTC).date().isoformat()}")
    lines.append("")
    lines.append(f"Run mode: **{mode}** · Timestamp: {_dt.now(UTC).isoformat()}")
    lines.append("")

    # Totals
    total_parsed = sum(o.parsed_count for o in outcomes)
    total_wrote = sum(sum(1 for w in o.writes if w.action == "wrote") for o in outcomes)
    total_refused = sum(
        sum(1 for w in o.writes if w.action.startswith("refused")) for o in outcomes
    )
    total_missing = sum(sum(1 for w in o.writes if w.action == "missing") for o in outcomes)
    total_errors = sum(1 for o in outcomes if o.error)
    total_subs = sum(1 for o in outcomes if o.parsed_count == 0 and not o.error)
    lines.append("## Totals")
    lines.append("")
    lines.append(f"- Vendors processed: **{len(outcomes)}**")
    lines.append(f"- Rows parsed: **{total_parsed}**")
    lines.append(f"- Rows wrote: **{total_wrote}**")
    lines.append(f"- Rows refused: **{total_refused}** (unit mismatch or >50% diff)")
    lines.append(f"- Rows missing: **{total_missing}** (parser returned slug not in registry)")
    lines.append(f"- Vendor errors: **{total_errors}**")
    lines.append(f"- Subscription-confirmed (parsed=0, no error): **{total_subs}**")
    lines.append("")

    # Per-vendor
    lines.append("## Per-vendor")
    lines.append("")
    for o in outcomes:
        wrote = sum(1 for w in o.writes if w.action == "wrote")
        refused = sum(1 for w in o.writes if w.action.startswith("refused"))
        missing = sum(1 for w in o.writes if w.action == "missing")
        err_suffix = f" — ERROR: {o.error}" if o.error else ""
        sub_suffix = (
            " — subscription-only confirmed" if (o.parsed_count == 0 and not o.error) else ""
        )
        lines.append(
            f"### {o.vendor} (parsed={o.parsed_count}, wrote={wrote}, "
            f"refused={refused}, missing={missing}){err_suffix}{sub_suffix}"
        )
        lines.append("")
        if not o.writes and not o.error:
            lines.append("_no writes_")
            lines.append("")
            continue
        for w in o.writes:
            bp = "—" if w.before_price is None else f"{w.before_price:.4f}"
            ap = "—" if w.after_price is None else f"{w.after_price:.4f}"
            pd = "—" if w.pct_diff is None else f"{w.pct_diff:+.1%}"
            lines.append(
                f"- **{w.action}** `{w.db_id}` ({w.pricing_unit}): {bp} → {ap} "
                f"({pd}) — {w.raw_price_text}"
            )
            if w.explanation:
                lines.append(f"    - _note:_ {w.explanation}")
        lines.append("")

    # Alerts (de-duplicated by action type)
    alerts: list[str] = []
    for o in outcomes:
        if o.error:
            alerts.append(f"- ❌ **{o.vendor}**: {o.error}")
        for w in o.writes:
            if w.action.startswith("refused"):
                alerts.append(f"- 🚫 **{o.vendor}**: refused `{w.db_id}` — {w.explanation}")
            elif w.action == "missing" and w.pricing_unit == "alert":
                alerts.append(
                    f"- 🚨 **{o.vendor}**: subscription-only vendor may have flipped "
                    f"to per-call pricing — {w.raw_price_text}"
                )
    if alerts:
        lines.append("## Alerts (operator review needed)")
        lines.append("")
        lines.extend(alerts)
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DB_PATH)
    parser.add_argument("--registry", type=Path, default=REGISTRY_PATH)
    parser.add_argument("--cache-dir", type=Path, default=CACHE_DIR)
    parser.add_argument(
        "--vendors",
        type=str,
        default="",
        help="Comma-separated subset; default = all vendors with a parser_module.",
    )
    parser.add_argument("--apply", action="store_true", help="Write to DB. Default is dry-run.")
    parser.add_argument(
        "--simulate-failure",
        type=str,
        default="",
        help="Force the named vendor's fetch to fail (alert-smoke).",
    )
    parser.add_argument(
        "--max-iter",
        type=int,
        default=1,
        help="Run N consecutive passes (for repeated-failure simulation).",
    )
    parser.add_argument(
        "--report", type=Path, default=None, help="Write a per-row CSV diff report to this path."
    )
    parser.add_argument(
        "--report-md",
        type=Path,
        default=None,
        help="Write a per-vendor markdown audit report (Phase 5 deliverable).",
    )
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    if not args.db.exists():
        print(f"ERROR: DB does not exist: {args.db}", file=sys.stderr)
        return 1

    registry = load_registry(args.registry)
    only = [v.strip() for v in args.vendors.split(",") if v.strip()] or None
    vendors = select_vendors(registry, only)

    browserless_token = os.environ.get("BROWSERLESS_TOKEN", "")
    if not browserless_token:
        print(
            "[fetch] WARNING: BROWSERLESS_TOKEN not set; rendered/stealth fetches will fail",
            file=sys.stderr,
        )
    scraper = WebScraper(
        cache_dir=args.cache_dir,
        browserless_url=os.environ.get("BROWSERLESS_URL", BROWSERLESS_URL_DEFAULT),
        browserless_token=browserless_token or "missing-token",
        cache_ttl_s=86_400,
    )

    all_outcomes: list[VendorOutcome] = []
    any_error = False

    for iteration in range(args.max_iter):
        if args.max_iter > 1 and not args.quiet:
            print(f"[fetch] iteration {iteration + 1}/{args.max_iter}")
        for vendor in vendors:
            simulate = vendor == args.simulate_failure
            # Adversarial review H1: process_vendor narrowly catches only
            # network errors. A programming bug now propagates here. Wrap
            # at the main-loop level so one vendor's bug doesn't crash the
            # whole pipeline — but record it as a vendor error with the
            # ACTUAL exception type (not "fetch failed: X").
            try:
                outcome = process_vendor(
                    vendor=vendor,
                    cfg=registry[vendor],
                    scraper=scraper,
                    db_path=args.db,
                    apply=args.apply,
                    simulate_failure=simulate,
                )
            except Exception as exc:  # noqa: BLE001 — pipeline defensive
                tb = traceback.format_exc(limit=3)
                outcome = VendorOutcome(
                    vendor=vendor,
                    fetched=False,
                    parsed_count=0,
                    writes=[],
                    error=f"orchestrator error: {type(exc).__name__}: {exc}\n{tb}",
                )
            all_outcomes.append(outcome)
            if not args.quiet:
                _emit_outcome(outcome, args.apply)
            _fire_per_vendor_alerts(outcome)
            if outcome.error:
                any_error = True

    if args.report:
        write_report_csv(args.report, all_outcomes)
        if not args.quiet:
            print(f"[fetch] wrote diff report -> {args.report}")

    if args.report_md:
        write_report_md(args.report_md, all_outcomes, args.apply)
        if not args.quiet:
            print(f"[fetch] wrote markdown audit -> {args.report_md}")

    # Exit 2 on hard failure under --apply (lets daily_refresh.sh detect breakage)
    return 2 if (any_error and args.apply) else 0


if __name__ == "__main__":
    sys.exit(main())
