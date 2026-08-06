"""The Authelia bearer bypass prefix is configurable per-spec via
``shape.bearer_bypass_prefix`` (default ``^/api/``).

Security driver (calendar): bearer auth is mounted only on ``/api/v1`` while
legacy ``/api/*`` are unauthenticated destructive admin routes — a broad
``^/api/`` bypass would expose them publicly, so the bypass must narrow to
``^/api/v1`` and the verifier must probe that exact prefix.

Tests call ``check_api_bypass`` and ``_provision_authelia`` directly to avoid the
``verify()`` DNS path (real ``dig``, slow/offline).
"""

from __future__ import annotations

from pathlib import Path
from unittest import mock

import pytest

from fabrik.orchestrator import verifier
from fabrik.orchestrator.context import DeploymentContext
from fabrik.orchestrator.exceptions import VerificationError
from fabrik.orchestrator.infrastructure import InfrastructureProvisioner


def _resp(code: int, location: str | None = None):
    r = mock.MagicMock()
    r.getcode.return_value = code
    r.headers = {"Location": location} if location else {}
    return r


def _captured_url(prefix: str | None) -> str:
    captured: dict[str, str] = {}

    def fake_urlopen(req, *a, **k):
        captured["url"] = req if isinstance(req, str) else getattr(req, "full_url", "")
        return _resp(401)  # backend's own auth, NOT a 302 → bypass working

    kw = {} if prefix is None else {"prefix": prefix}
    with mock.patch.object(verifier, "urlopen", side_effect=fake_urlopen):
        verifier.check_api_bypass("calendar.vps1.ocoron.com", timeout=1, **kw)
    return captured["url"]


def test_verifier_probes_configured_prefix():
    assert _captured_url("^/api/v1") == "https://calendar.vps1.ocoron.com/api/v1"


def test_verifier_default_prefix_unchanged():
    # Back-compat: default resolves to the historical /api/ probe.
    assert _captured_url(None) == "https://calendar.vps1.ocoron.com/api/"


def test_verifier_raises_when_authelia_intercepts_configured_prefix():
    redirect = _resp(
        302, "https://auth.vps1.ocoron.com/?rd=https://calendar.vps1.ocoron.com/api/v1"
    )
    with mock.patch.object(verifier, "urlopen", return_value=redirect):
        with pytest.raises(VerificationError) as exc:
            verifier.check_api_bypass("calendar.vps1.ocoron.com", prefix="^/api/v1", timeout=1)
    assert "^/api/v1" in str(exc.value)  # message names the configured prefix


def _provision_bypass_resources(shape: dict) -> list[str]:
    prov = InfrastructureProvisioner(deployer=mock.MagicMock())
    ctx = DeploymentContext(spec_path=Path("x.yaml"))
    bypass: list[list[str]] = []

    def fake_add(domain, **kw):
        if kw.get("policy") == "bypass":
            bypass.append(kw["resources"])

    with mock.patch("fabrik.drivers.authelia.add_access_rule", side_effect=fake_add):
        prov._provision_authelia("c.vps1.ocoron.com", shape, ctx, dry_run=False)
    return bypass[0] if bypass else []


def test_registrar_uses_configured_prefix():
    res = _provision_bypass_resources({"has_bearer_api": True, "bearer_bypass_prefix": "^/api/v1"})
    assert res == ["^/api/v1"]


def test_registrar_defaults_to_api():
    res = _provision_bypass_resources({"has_bearer_api": True})
    assert res == ["^/api/"]


def test_no_bypass_when_not_bearer_api():
    res = _provision_bypass_resources({"has_bearer_api": False})
    assert res == []
