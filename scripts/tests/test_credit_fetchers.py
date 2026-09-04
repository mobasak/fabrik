#!/usr/bin/env python3
# AFTER-EDIT: scripts/credit_fetchers/__init__.py scripts/declare_subscription.py
"""Behavior-Contract tests for the hybrid credit fetchers + declare_subscription (Phase C).

Fetcher tests mock the HTTP layer (no live vendor calls). The declare test uses the real local
fabrik_services PG with a throwaway service it deletes; skips if the DB is unreachable.
"""

from __future__ import annotations

import importlib
import os
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
    if os.environ.get("REGISTRY_WRITE_TESTS") != "1":
        pytest.skip(
            "writes a row to the LIVE registry and a SIGKILL skips its finally — opt in with REGISTRY_WRITE_TESTS=1 (B66-C14)"
        )
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
        # through the SHIPPED call site, not the opener directly — reverting the fix must go red (BE2)
        got = cf._get_json(
            f"http://127.0.0.1:{srv.server_port}/a",
            {"Authorization": "DeepL-Auth-Key SENTINEL-NOT-A-REAL-KEY"},
        )
        assert got is None, got  # a redirect is a failed fetch, never a followed one
    finally:
        srv.shutdown()
        srv.server_close()  # release the listening socket too (BE7)
    assert {p for p, _ in seen} == {"/a"}, seen  # /b was never requested (the helper retries /a)


def test_only_transient_statuses_are_retried_and_retry_after_is_honoured_capped():
    """A 401 (revoked key) is final on the first answer; a 503 is retried; a hostile
    `Retry-After` is capped (BH4)."""
    import http.server
    import threading

    seen: dict[str, int] = {}

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            seen[self.path] = seen.get(self.path, 0) + 1
            code = int(self.path.strip("/"))
            self.send_response(code)
            if code == 503:
                self.send_header("Retry-After", "0")
            self.end_headers()

        def log_message(self, *a):  # noqa: D102
            return

    srv = http.server.HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        base = f"http://127.0.0.1:{srv.server_port}"
        assert cf._get_json(f"{base}/401", {}) is None and seen["/401"] == 1
        assert cf._get_json(f"{base}/503", {}) is None and seen["/503"] == cf.RETRIES + 1
    finally:
        srv.shutdown()
        srv.server_close()
    assert cf._retry_after("99999", 0) == 30.0 and cf._retry_after("garbage", 1) == 2.0
    assert cf._retry_after("-5", 0) == 0.0  # a negative header would crash time.sleep (BJ3)
    assert cf._retry_after("nan", 0) == 0.0  # NaN would crash time.sleep too (BK5)


def test_an_oversized_body_is_not_a_usage_answer():
    """`resp.read()` was unbounded: a misbehaving endpoint could hold the daily chain's memory
    and clock. The bound is what refuses the body — the first grader's oversized fixture was
    INVALID JSON, so `None` came from the parse branch and the size guard was ungraded (K-9);
    this body is valid JSON in its first bytes, padded past MAX_BODY with whitespace, and the
    fake records how much was read and how many times the vendor was opened (E2-C7)."""
    import io

    class _Resp(io.BytesIO):
        amt = None

        def read(self, amt=-1):
            _Resp.amt = amt
            return super().read(amt)

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    class _Opener:
        def __init__(self, body):
            self.body, self.opens = body, 0

        def open(self, req, timeout=None):
            self.opens += 1
            return _Resp(self.body)

    orig = cf._OPENER
    good = b'{"data": {"totalUsageCreditsUsd": 1.5}}'
    try:
        cf._OPENER = _Opener(good)
        assert cf._get_json("https://x.example", {}) == {"data": {"totalUsageCreditsUsd": 1.5}}
        assert _Resp.amt == cf.MAX_BODY + 1  # the read is BOUNDED, not `read()`
        cf._OPENER = _Opener(good + b" " * (cf.MAX_BODY * 2))
        assert cf._get_json("https://x.example", {}) is None
        assert cf._OPENER.opens == 1  # refused once — never retried three times as a parse error
        cf._OPENER = _Opener(
            good + b" " * (cf.MAX_BODY - len(good))
        )  # exactly MAX_BODY still parses
        assert cf._get_json("https://x.example", {}) == {"data": {"totalUsageCreditsUsd": 1.5}}
    finally:
        cf._OPENER = orig


def test_a_nan_or_infinite_vendor_number_is_no_snapshot(monkeypatch):
    """`json.loads` accepts `NaN`/`Infinity`; `float()` passed them to a NUMERIC column and the
    dashboard rendered `⚠ nan usd` (FC4)."""
    for body in (
        '{"data": {"totalUsageCreditsUsd": NaN}}',
        '{"data": {"totalUsageCreditsUsd": Infinity}}',
    ):
        monkeypatch.setattr(
            cf, "_get_json", lambda url, headers, b=body: __import__("json").loads(b)
        )
        assert cf.fetch_apify("k") is None, body
    monkeypatch.setattr(
        cf,
        "_get_json",
        lambda url, headers: {"character_count": 5, "character_limit": float("inf")},
    )
    assert cf.fetch_deepl("k") is None


def test_deepls_no_limit_sentinel_is_usage_not_a_balance(monkeypatch):
    """DeepL's documented `1e12 = no limit` sentinel rendered as `1e+12 chars_remaining` (FC4)."""
    monkeypatch.setattr(
        cf,
        "_get_json",
        lambda url, headers: {"character_count": 1234, "character_limit": 1000000000000},
    )
    snap = cf.fetch_deepl("k")
    assert snap is not None and snap.unit == "chars_used_unlimited_plan" and snap.balance == 1234.0


def test_crossing_the_body_cap_is_said(capsys):
    """A body over MAX_BODY was a silent `None` — a stale cell whose stated causes never named it (FC4)."""
    import io

    class _Resp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    class _Opener:
        def open(self, req, timeout=None):
            return _Resp(b'{"a": 1}' + b" " * (cf.MAX_BODY * 2))

    orig = cf._OPENER
    try:
        cf._OPENER = _Opener()
        assert cf._get_json("https://x.example/usage", {}) is None
    finally:
        cf._OPENER = orig
    assert "response over" in capsys.readouterr().err


def test_a_flag_a_string_and_an_overflowing_int_are_not_measurements(monkeypatch):
    """`_finite(True)` published a fresh $1.00 balance (which also silenced the staleness flag);
    `"12"` became 12.0 while DeepL rejected the same string; `math.isfinite(10**400)` raised
    OverflowError inside `fetch_deepl`; a negative limit produced a negative balance (K64-6/13/18, FD7)."""
    assert (
        cf._finite(True, "u") is None
        and cf._finite("12", "u") is None
        and cf._finite(10**400, "u") is None
    )
    assert cf._finite(12, "u") == cf.CreditSnapshot(12.0, "u")
    cases = {
        '{"character_count": true, "character_limit": 500000}': None,
        '{"character_count": "100", "character_limit": 500000}': None,
        '{"character_count": 100, "character_limit": -500}': None,
        '{"character_count": 100, "character_limit": 1e400}': None,
        '{"character_count": 100, "character_limit": 10000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000}': None,  # a 400-digit INT: `math.isfinite` raises OverflowError on it
        '{"character_count": 100, "character_limit": 500}': cf.CreditSnapshot(
            400.0, "chars_remaining"
        ),
    }
    for body, want in cases.items():
        monkeypatch.setattr(cf, "_get_json", lambda *a, _b=body, **k: __import__("json").loads(_b))
        assert cf.fetch_deepl("k:fx") == want, body
    monkeypatch.setattr(cf, "_get_json", lambda *a, **k: {"data": {"totalUsageCreditsUsd": True}})
    assert cf.fetch_apify("k") is None
    for data in (
        [1],
        "x",
        5,
        True,
        None,
    ):  # a non-dict `data` raised AttributeError inside the fetcher (FE1)
        monkeypatch.setattr(cf, "_get_json", lambda *a, _d=data, **k: {"data": _d})
        assert cf.fetch_apify("k") is None, data
    monkeypatch.setattr(cf, "_get_json", lambda *a, **k: {"data": {"totalUsageCreditsUsd": -5}})
    assert cf.fetch_apify("k") is None, "a negative usage is not a measurement"
    assert cf._finite(-0.5, "u") is None and cf._finite(0, "u") == cf.CreditSnapshot(0.0, "u")
    for body in (
        '{"character_count": -100, "character_limit": 500}',
        '{"character_count": 600, "character_limit": 500}',
    ):
        monkeypatch.setattr(cf, "_get_json", lambda *a, _b=body, **k: __import__("json").loads(_b))
        assert cf.fetch_deepl("k:fx") is None, (
            body
        )  # a negative count inflated the remainder; an overage is a negative remainder — neither is a balance (FE1)


def test_a_truncated_chunked_body_and_a_bottomless_json_are_no_snapshot_not_a_raise():
    """`http.client.IncompleteRead` and a `RecursionError` from a 100 000-deep JSON escaped
    `_get_json`'s "never raises" contract — held only by `fetch_balance`'s blanket catch (K66-5, FF1)."""
    import http.client
    import io

    class _Resp(io.BytesIO):
        def read(self, amt=-1):
            raise http.client.IncompleteRead(b"")

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    class _Opener:
        def __init__(self, resp):
            self.resp, self.opens = resp, 0

        def open(self, req, timeout=None):
            self.opens += 1
            return self.resp

    orig = cf._OPENER
    try:
        cf._OPENER = _Opener(_Resp(b""))
        assert cf._get_json("https://x.example", {}) is None
        cf._OPENER = _Opener(io.BytesIO(b"[" * 100_000))
        cf._OPENER.resp.__enter__ = lambda s=cf._OPENER.resp: s
        cf._OPENER.resp.__exit__ = lambda *a: False
        assert cf._get_json("https://x.example", {}) is None
    finally:
        cf._OPENER = orig
