#!/usr/bin/env python3
# AFTER-EDIT: scripts/credit_fetchers/__init__.py scripts/declare_subscription.py
"""Behavior-Contract tests for the hybrid credit fetchers + declare_subscription (Phase C).

Fetcher tests mock the HTTP layer (no live vendor calls). The declare test uses the real local
fabrik_services PG with a throwaway service it deletes; skips if the DB is unreachable.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS))

cf = importlib.import_module("credit_fetchers")


def test_fetcher_failure_returns_none(monkeypatch):
    """Given the vendor API fails (None from the HTTP layer), When a fetcher runs, Then it
    returns None (no snapshot) and never raises."""
    monkeypatch.setattr(cf, "_get_json", lambda url, headers: None)
    assert cf.fetch_apify("k") is None
    assert cf.fetch_deepl("k") is None
    assert cf.fetch_balance("apify", "k") is None


def test_apify_parses_used(monkeypatch):
    """Given a sample Apify usage response, When parsed, Then balance + unit are extracted."""
    monkeypatch.setattr(
        cf, "_get_json", lambda url, headers: {"data": {"totalUsageCreditsUsd": 42.5}}
    )
    snap = cf.fetch_apify("k")
    assert snap is not None
    assert snap.balance == 42.5
    assert snap.unit == "usd_used_month"


def test_deepl_parses_remaining(monkeypatch):
    """Given DeepL character_count/limit, When parsed, Then balance is the remaining chars."""
    monkeypatch.setattr(
        cf, "_get_json", lambda url, headers: {"character_count": 100, "character_limit": 500000}
    )
    snap = cf.fetch_deepl("k")
    assert snap is not None
    assert snap.balance == 499900.0
    assert snap.unit == "chars_remaining"


def test_fetch_balance_unknown_provider_is_none():
    """Given a provider with no fetcher, When fetch_balance runs, Then None (no crash)."""
    assert cf.fetch_balance("nonesuch", "k") is None


def test_declare_subscription_persists(monkeypatch):
    """Given a synced service, When declare() runs, Then a subscriptions row persists with the
    renewal date + account email."""
    rdb = importlib.import_module("registry_db")
    try:
        rdb.connect().close()
    except Exception:  # noqa: BLE001
        pytest.skip("local fabrik_services PG not reachable")
    ds = importlib.import_module("declare_subscription")
    prov = "test_zzz_declare"
    conn = rdb.connect()
    try:
        with conn, conn.cursor() as cur:
            cur.execute(
                "INSERT INTO services (provider,category) VALUES (%s,'x') "
                "ON CONFLICT (provider) DO NOTHING",
                (prov,),
            )
        ds.declare(
            prov,
            plan="default",
            price=49,
            currency="USD",
            renews_on="2026-08-01",
            account_email="ob@ocoron.com",
        )
        with conn, conn.cursor() as cur:
            cur.execute(
                "SELECT renews_on, account_email FROM subscriptions s JOIN services v "
                "ON v.id=s.service_id WHERE v.provider=%s",
                (prov,),
            )
            row = cur.fetchone()
            assert row is not None
            assert str(row[0]) == "2026-08-01"
            assert row[1] == "ob@ocoron.com"
    finally:
        with conn, conn.cursor() as cur:
            cur.execute("DELETE FROM services WHERE provider=%s", (prov,))
        conn.close()


def test_fetch_balance_never_raises_on_malformed_field(monkeypatch):
    """Given a present-but-non-numeric field, When fetch_balance runs, Then None (never raises —
    so a bad vendor response can't abort the sync transaction)."""
    monkeypatch.setattr(
        cf, "_get_json", lambda url, headers: {"data": {"totalUsageCreditsUsd": "NaN-ish"}}
    )
    assert cf.fetch_balance("apify", "k") is None


def test_a_redirect_never_carries_the_vendor_key_to_another_host():
    """urllib's default handler re-sends every header — the vendor key included — to whatever
    host a 3xx names; a usage endpoint never legitimately redirects, so a redirect is a failed
    fetch and the second host never sees `Authorization` (BB8)."""
    import http.server
    import threading
    import urllib.error
    import urllib.request

    seen: list[tuple[str, str | None]] = []

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            seen.append((self.path, self.headers.get("Authorization")))
            if self.path == "/a":
                self.send_response(302)
                self.send_header("Location", f"http://127.0.0.1:{self.server.server_port}/b")
                self.end_headers()
            else:
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"{}")

        def log_message(self, *a):  # noqa: D102
            return

    srv = http.server.HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{srv.server_port}/a",
            headers={"Authorization": "DeepL-Auth-Key SENTINEL-NOT-A-REAL-KEY"},
        )
        with pytest.raises(urllib.error.HTTPError) as exc:
            with cf._OPENER.open(req, timeout=5):
                pass
        assert exc.value.code == 302
    finally:
        srv.shutdown()
    assert [p for p, _ in seen] == ["/a"], seen  # /b was never requested
