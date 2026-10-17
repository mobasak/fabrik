"""The `_oauth_get` transport-dead latch (W-5a1b8961, D-939): a dead uplink costs one call, not N.

After ONE call fails on every host with a TRANSPORT error (an OSError on every attempt, never an
HTTP status), every further call inside `_OAUTH_TRANSPORT_DEAD_TTL_S` returns None at once. That
keeps `--status --json` inside quota_dashboard.py's 60 s subprocess cap on a dead link (observed
2026-10-12). Only positive evidence marks it: a bad header, a malformed body or a bug is not a dead
link. Any contact clears it. Both vendored copies are driven, so the twins cannot drift in
behaviour. No call here reaches the network: urlopen is stubbed in every test.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
COPIES = {
    "sysadmin": REPO / "scripts" / "sysadmin" / "claude_rotate.py",
    "aro-wake": REPO / "scripts" / "aro-wake" / "claude_rotate.py",
}


def _load(name: str):
    spec = importlib.util.spec_from_file_location(f"claude_rotate_latch_{name}", COPIES[name])
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(params=sorted(COPIES))
def cr(request):
    return _load(request.param)


class _Resp:
    def __init__(self, body: bytes) -> None:
        self._b = body

    def read(self, *a):
        return self._b

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _stub(monkeypatch, behaviour):
    calls = {"n": 0}

    def fake(req, timeout=None):
        calls["n"] += 1
        return behaviour(req)

    monkeypatch.setattr(urllib.request, "urlopen", fake)
    return calls


def _down(req):
    raise TimeoutError("the uplink is down")


def _ok(req):
    return _Resp(json.dumps({"ok": 1}).encode())


def test_a_dead_transport_fails_fast_inside_the_ttl(cr, monkeypatch):
    calls = _stub(monkeypatch, _down)
    assert cr._oauth_get("usage", "tok", attempts=2, backoff_s=0) is None
    spent = calls["n"]
    assert spent == len(cr._OAUTH_HOSTS) * 2  # the first call still pays its whole budget
    assert cr._oauth_get("profile", "tok", attempts=2, backoff_s=0) is None
    assert calls["n"] == spent, "inside the TTL the latch must answer without touching the network"


def test_the_latch_expires_after_its_ttl(cr, monkeypatch):
    calls = _stub(monkeypatch, _ok)
    cr._oauth_transport_dead_at = time.monotonic() - cr._OAUTH_TRANSPORT_DEAD_TTL_S + 5
    assert cr._oauth_get("usage", "tok", attempts=1, backoff_s=0) is None  # still inside the TTL
    assert calls["n"] == 0
    cr._oauth_transport_dead_at = time.monotonic() - cr._OAUTH_TRANSPORT_DEAD_TTL_S - 1
    assert cr._oauth_get("usage", "tok", attempts=1, backoff_s=0) == {"ok": 1}, (
        "past the TTL: probe"
    )
    assert calls["n"] == 1


@pytest.mark.parametrize("code", [500, 503, 429, 404, 401])
def test_an_http_status_never_trips_and_clears_the_latch(cr, monkeypatch, code):
    def status(req):
        raise urllib.error.HTTPError(req.full_url, code, "status", {}, None)

    calls = _stub(monkeypatch, status)
    assert cr._oauth_get("usage", "tok", attempts=1, backoff_s=0) is None
    assert cr._oauth_transport_dead() is False, "an HTTP status proves the transport is alive"
    before = calls["n"]
    cr._oauth_get("usage", "tok", attempts=1, backoff_s=0)
    assert calls["n"] > before, "no latch after a status: the next call probes again"
    # a set latch is cleared by contact (an earlier blackout, then the link answers)
    cr._oauth_mark_transport_dead()
    cr._oauth_transport_dead_at -= cr._OAUTH_TRANSPORT_DEAD_TTL_S + 1  # expired: one probe allowed
    cr._oauth_get("usage", "tok", attempts=1, backoff_s=0)
    assert cr._oauth_transport_dead_at is None, "an HTTP answer clears the latch"


def test_a_success_clears_the_latch(cr, monkeypatch):
    _stub(monkeypatch, _ok)
    cr._oauth_mark_transport_dead()
    cr._oauth_transport_dead_at -= cr._OAUTH_TRANSPORT_DEAD_TTL_S + 1
    assert cr._oauth_get("usage", "tok", attempts=1, backoff_s=0) == {"ok": 1}
    assert cr._oauth_transport_dead_at is None


@pytest.mark.parametrize(
    "error",
    [ValueError("Invalid header value b'Bearer a\\nb'"), json.JSONDecodeError("x", "y", 0)],
)
def test_a_non_transport_error_never_latches(cr, monkeypatch, error):
    """A token holding "\\n" makes http.client raise ValueError on EVERY host with no I/O at all;
    a malformed body raises a decode error. Neither is a dead link — one bad credential must not
    blank every other account for the TTL."""

    def broken(req):
        raise error

    _stub(monkeypatch, broken)
    assert cr._oauth_get("usage", "tok", attempts=2, backoff_s=0) is None
    assert cr._oauth_transport_dead() is False
    assert cr._oauth_get("usage", "tok", attempts=0, backoff_s=0) is None  # no attempt, no evidence
    assert cr._oauth_transport_dead() is False


def test_a_transport_error_mixed_with_another_error_never_latches(cr, monkeypatch):
    """One host times out, the other raises a non-transport error: not every failure was the link,
    so the evidence is not all transport — no latch."""

    def mixed(req):
        if cr._OAUTH_HOSTS[0] in req.full_url:
            raise TimeoutError("this host is unreachable")
        raise ValueError("Invalid header value")

    _stub(monkeypatch, mixed)
    assert cr._oauth_get("usage", "tok", attempts=1, backoff_s=0) is None
    assert cr._oauth_transport_dead() is False


def test_a_contact_landing_mid_call_voids_that_calls_mark(cr, monkeypatch):
    """Another thread reached the API while this call was still failing (simulated by a contact on
    the first attempt): its all-hosts transport failure must not re-poison the latch afterwards."""
    first = {"done": False}

    def flaky(req):
        if not first["done"]:
            first["done"] = True
            cr._oauth_clear_transport_dead()  # what a concurrent successful call does
        raise TimeoutError("still down for this call")

    _stub(monkeypatch, flaky)
    assert cr._oauth_get("usage", "tok", attempts=1, backoff_s=0) is None
    assert cr._oauth_transport_dead() is False


def test_a_tls_certificate_refusal_is_contact_not_a_dead_link(cr, monkeypatch):
    import ssl

    def portal(req):
        raise ssl.SSLCertVerificationError("certificate verify failed: captive portal")

    _stub(monkeypatch, portal)
    assert cr._oauth_get("usage", "tok", attempts=2, backoff_s=0) is None
    assert cr._oauth_transport_dead() is False
    cr._oauth_mark_transport_dead()  # an earlier blackout, expired so one probe is allowed
    cr._oauth_transport_dead_at -= cr._OAUTH_TRANSPORT_DEAD_TTL_S + 1
    cr._oauth_get("usage", "tok", attempts=1, backoff_s=0)
    assert cr._oauth_transport_dead_at is None, (
        "a certificate refusal is contact: it clears the latch"
    )


def test_a_status_on_one_host_after_a_timeout_on_the_other_never_latches(cr, monkeypatch):
    """Host 0 times out, host 1 answers 429: the link answered, so no mark."""

    def split(req):
        if cr._OAUTH_HOSTS[0] in req.full_url:
            raise TimeoutError("this host is unreachable")
        raise urllib.error.HTTPError(req.full_url, 429, "slow down", {}, None)

    _stub(monkeypatch, split)
    assert cr._oauth_get("usage", "tok", attempts=1, backoff_s=0) is None
    assert cr._oauth_transport_dead_at is None


def test_a_timeout_reading_a_200_body_never_latches(cr, monkeypatch):
    """The server answered 200 and the body read then timed out: an OSError, but after contact."""

    class _SlowBody(_Resp):
        def read(self, *a):
            raise TimeoutError("the body stalled")

    _stub(monkeypatch, lambda req: _SlowBody(b""))
    assert cr._oauth_get("usage", "tok", attempts=1, backoff_s=0) is None
    assert cr._oauth_transport_dead() is False


_TRIPPED: list[str] = []


def test_trip_the_package_instance_for_the_next_test(monkeypatch):
    """Sets the latch on the PERSISTENT package-import instance; the next test proves the autouse
    reset cleared it."""
    import scripts.sysadmin.claude_rotate as pkg

    _stub(monkeypatch, _down)
    pkg._oauth_get("usage", "tok", attempts=1, backoff_s=0)
    assert pkg._oauth_transport_dead() is True
    _TRIPPED.append(pkg.__name__)


def test_the_latch_never_survives_into_another_test():
    """The autouse reset (tests/conftest.py) clears every registered claude_rotate copy before each
    test, the package-import instance test_claude_fleet uses included. Meaningful only after the
    trip test above ran in this process; selected alone it SKIPS, saying why, rather than pass with
    nothing to prove."""
    if not _TRIPPED:
        pytest.skip("needs test_trip_the_package_instance_for_the_next_test to run first")
    import scripts.sysadmin.claude_rotate as pkg

    loaded = [
        m
        for m in list(sys.modules.values())
        if str(getattr(m, "__file__", "") or "").endswith("claude_rotate.py")
    ]
    assert pkg in loaded
    for mod in loaded:
        assert getattr(mod, "_oauth_transport_dead_at", None) is None, mod.__name__
