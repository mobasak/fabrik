"""GlitchTip must never receive a secret — checked on the CAPTURED EVENT, not the init kwargs.

Emitted by the Fabrik scaffolder (fabrik: templates/scaffold/python/test_glitchtip_no_secret_leak.py,
W-dc4f5470). It raises inside a real request with secrets in the frame locals, the JSON body, a
header, the query string and an interpolated log line, then searches everything the transport
would have sent (55-observability § Error Reporting).

Two tests, both kept:
  * test_no_secret_reaches_the_wire — through this project's own init_glitchtip().
  * test_vacuity_guard_an_unscrubbed_sdk_does_leak — the same capture through a PLAIN sentry_sdk
    init must show a secret. If an SDK upgrade changes the capture path so nothing is captured,
    this goes red, instead of the first test going green while certifying nothing.

Capture is a Transport SUBCLASS: sentry-sdk deprecated function transports, and a security test
that silently stops capturing on an SDK bump is the worst way for it to fail.
"""

import importlib
import logging

# a plain import on purpose: a missing sentry-sdk must FAIL this file, never skip it
import httpx
import pytest
import sentry_sdk
from fastapi import FastAPI, Request
from sentry_sdk.transport import Transport
from starlette.testclient import TestClient

SECRETS = {
    "dsn": "postgres://svc:PGPASSWORD_LEAK@postgres-main:5432/db",
    # no "@": a redactor keyed on "@" passes this credential through as the "host"
    "dsn_no_at": "postgres://svc:NOATPASSWORD_LEAK",
    "apikey": "BREADCRUMBAPIKEY_LEAK",
    "jwt": "JWTSECRET_LEAK",
    "password": "BODYPASSWORD_LEAK",
    "header": "SIGNINGSECRET_LEAK",
    "query": "URLTOKEN_LEAK",
    "otp": "OTPINTERPOLATED_LEAK",
}
FAKE_DSN = "https://publickey@glitchtip.invalid/42"


@pytest.fixture(autouse=True)
def _sentry_off_afterwards():
    """Each test initialises the global SDK; leave it disabled, never capturing, for the rest
    of the suite (the vacuity guard's client has PII and locals switched on)."""
    yield
    scope = sentry_sdk.get_global_scope()  # where sentry_sdk.init binds its client
    scope.client.close()
    scope.set_client(None)  # back to the non-recording client


class CaptureTransport(Transport):
    """Keeps every envelope instead of sending it."""

    def __init__(self, options=None):
        super().__init__(options)
        self.envelopes = []

    def capture_envelope(self, envelope):
        self.envelopes.append(envelope)

    def flush(self, timeout, callback=None):
        return None

    def kill(self):
        return None


def _install_capture():
    client = sentry_sdk.get_client()
    old = client.transport
    capture = CaptureTransport(client.options)
    client.transport = capture
    if old is not None:
        old.kill()
    return capture


def _raise_with_secrets_in_play() -> None:
    app = FastAPI()

    @app.post("/boom")
    async def boom(request: Request):
        settings_repr = f"Settings(database_url='{SECRETS['dsn']}', jwt_secret='{SECRETS['jwt']}')"  # noqa: F841
        body = await request.json()  # noqa: F841
        signing = request.headers.get("X-Signing-Secret")  # noqa: F841
        logging.getLogger("leak-guard").error("otp=%s", SECRETS["otp"])
        logging.getLogger("leak-guard").error("connecting to " + SECRETS["dsn_no_at"])
        try:  # the outbound URL, key and all, travels in the transaction's http span data
            httpx.get(f"http://127.0.0.1:1/probe?apikey={SECRETS['apikey']}", timeout=0.05)
        except httpx.HTTPError:
            pass
        raise RuntimeError("boom")

    with TestClient(app, raise_server_exceptions=False) as client:
        client.post(
            f"/boom?token={SECRETS['query']}",
            json={"password": SECRETS["password"]},
            headers={"X-Signing-Secret": SECRETS["header"]},
        )
    sentry_sdk.get_client().flush(timeout=2)


def _wire(capture: CaptureTransport) -> str:
    """Every byte the transport would have sent: envelope headers, item headers, every payload."""
    return b"\n".join(envelope.serialize() for envelope in capture.envelopes).decode(
        "utf-8", errors="replace"
    )


def _error_events(capture: CaptureTransport) -> list:
    return [
        item.payload.json
        for envelope in capture.envelopes
        for item in envelope.items
        if isinstance(getattr(item.payload, "json", None), dict)
        and "exception" in item.payload.json
    ]


def test_no_secret_reaches_the_wire(monkeypatch):
    # the scaffolder substitutes this project's package name into the module path
    init_glitchtip = importlib.import_module("{pkg}.glitchtip_init").init_glitchtip

    monkeypatch.setenv("SENTRY_DSN", FAKE_DSN)
    monkeypatch.setenv("GLITCHTIP_TRACES_SAMPLE_RATE", "1.0")
    assert init_glitchtip() is True, "init_glitchtip() did not initialise; nothing below is checked"
    capture = _install_capture()

    _raise_with_secrets_in_play()

    assert _error_events(capture), "no error event was captured; the check below would be vacuous"
    wire = _wire(capture)
    leaked = sorted(name for name, value in SECRETS.items() if value in wire)
    assert not leaked, f"secrets reached GlitchTip through: {leaked}"


def test_vacuity_guard_an_unscrubbed_sdk_does_leak():
    sentry_sdk.init(
        dsn=FAKE_DSN,
        include_local_variables=True,
        max_request_body_size="always",
        send_default_pii=True,
        traces_sample_rate=1.0,
        transport=CaptureTransport,
    )
    capture = sentry_sdk.get_client().transport
    assert isinstance(capture, CaptureTransport), "the SDK did not accept the Transport subclass"

    _raise_with_secrets_in_play()

    wire = _wire(capture)
    assert _error_events(capture), "the SDK captured no error event at all"
    unseen = sorted(name for name, value in SECRETS.items() if value not in wire)
    assert not unseen, (
        f"an unscrubbed SDK no longer ships {unseen}, so the capture path for those channels has "
        "changed and test_no_secret_reaches_the_wire proves nothing about them until this is updated"
    )
