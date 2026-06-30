"""Phase 7 (deploy-readiness-gaps): apply-time GlitchTip webhook reminder.

GlitchTip exposes no API to register a webhook recipient (probed 2026-06-29 —
/rules/, /alert-rules/, /alerts/ all 404), so `fabrik apply` can't automate it.
For any spec whose watchdog ingests `error_webhook`, it must instead print a
clear operator-manual reminder. These tests pin the pure reminder builder the
apply summary calls — see `cli.py` reconcile-all loop + `glitchtip.py`.
"""

from __future__ import annotations

from types import SimpleNamespace

from fabrik.drivers.glitchtip import webhook_registration_reminder


def _spec(sources: list[str], sid: str = "demo-svc") -> SimpleNamespace:
    return SimpleNamespace(id=sid, watchdog=SimpleNamespace(trigger_sources=sources))


def test_reminder_logged_when_error_webhook_enabled(monkeypatch):
    # Force defaults so the asserted URL is deterministic regardless of host env.
    monkeypatch.delenv("GLITCHTIP_ORG_SLUG", raising=False)
    monkeypatch.delenv("GLITCHTIP_URL", raising=False)
    rem = webhook_registration_reminder(_spec(["health", "error_webhook"]))
    assert rem is not None
    assert "ACTION REQUIRED: register GlitchTip webhook" in rem
    # canonical UI URL (org default 'ocoron', driver base) + the :8889 recipient
    assert "https://errors.vps1.ocoron.com/ocoron/demo-svc/" in rem
    assert "http://demo-svc-watchdog:8889/" in rem
    assert "recipient type: webhook" in rem


def test_no_reminder_when_error_webhook_disabled():
    assert webhook_registration_reminder(_spec(["emitter", "health"])) is None
    assert webhook_registration_reminder(_spec([])) is None
    # a spec with no watchdog block at all must not raise
    assert webhook_registration_reminder(SimpleNamespace(id="x", watchdog=None)) is None


def test_reminder_honours_org_and_base_overrides(monkeypatch):
    monkeypatch.setenv("GLITCHTIP_ORG_SLUG", "acme")
    monkeypatch.setenv("GLITCHTIP_URL", "https://gt.example.com/")
    rem = webhook_registration_reminder(_spec(["error_webhook"], sid="billing-api"))
    assert rem is not None
    assert "https://gt.example.com/acme/billing-api/" in rem
    assert "http://billing-api-watchdog:8889/" in rem
