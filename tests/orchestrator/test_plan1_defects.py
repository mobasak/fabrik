"""Regression tests for the four proven code defects in
docs/development/plans/2026-07-13-plan-1.md — one per defect (Behavior Contract).

Each test FAILS against the pre-fix code (that is what proves the defect) and passes
after the fix. Transport (SSH/Docker) is mocked; the real call graphs are exercised.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from fabrik.orchestrator.deployer_ssh import SSHDeployer, _validate_compose
from fabrik.orchestrator.exceptions import DeployError


# ── D1: _deploy_git must validate the compose (fail-closed on the standard path) ──────────

_BAD_GIT_COMPOSE = (
    "services:\n"
    "  web:\n"
    "    image: python:3.12\n"
    "    container_name: my-app\n"
    "    platform: linux/amd64\n"
    "    restart: unless-stopped\n"          # NOTE: no deploy.resources.limits.memory
    "    networks:\n"
    "      - fabrik\n"
    "networks:\n"
    "  fabrik:\n"
    "    external: true\n"
)


def test_d1_deploy_git_validates_compose_and_aborts_on_violation():
    """A git-sourced compose that omits the memory limit must abort _deploy_git with a
    validation error — the same enforcement _deploy_template applies (D1)."""
    deployer = SSHDeployer()

    def _fake_ssh(cmd, *a, **k):
        if ".git && echo exists" in cmd:
            return "exists"                      # already cloned → git pull path
        if "cat /opt/" in cmd and "compose" in cmd:
            return _BAD_GIT_COMPOSE              # the compose fetched back from the VPS
        return ""                                # keyscan / pull / anything else

    ctx = _ctx({"id": "git-app", "source": {"repository": "git@github.com:x/y.git"}})
    with patch("fabrik.drivers.ssh.ssh", side_effect=_fake_ssh), \
         patch("fabrik.orchestrator.deployer_ssh._write_file_to_vps"):
        with pytest.raises(DeployError, match="[Vv]alidation|memory"):
            deployer._deploy_git(
                ctx, "git-app", {"repository": "git@github.com:x/y.git", "branch": "main"}, None
            )


def test_d1_missing_networks_block_is_a_deliberate_error():
    """DECISION (fail-closed): a compose with NO top-level `networks:` block is rejected —
    every service must join the external `fabrik` network. (Was: silently passed.)"""
    compose = (
        "services:\n"
        "  web:\n"
        "    image: python:3.12\n"
        "    container_name: my-app\n"
        "    platform: linux/amd64\n"
        "    restart: unless-stopped\n"
        "    deploy:\n"
        "      resources:\n"
        "        limits:\n"
        "          memory: 256M\n"
    )
    errors = _validate_compose(compose)
    assert any("network" in e.lower() for e in errors), errors


# ── D2: uncapped watchdog rejected on apply + driver/model default agree ──────────────────

def test_d2_uncapped_watchdog_rejected_on_apply():
    """A watchdog with both caps zeroed is an uncapped LLM cost path → apply must reject it
    (D2). Currently resolve_applicability returns (True, 'enabled=true')."""
    from fabrik.orchestrator.infrastructure import resolve_applicability

    spec = {
        "id": "wd-app",
        "shape": {"kind": "service", "needs_database": False},
        "watchdog": {"daily_budget_usd": 0, "daily_invocations_cap": 0},
    }
    with pytest.raises(ValueError, match="[Uu]ncap|cap"):
        resolve_applicability(spec)


def test_d2_driver_budget_default_matches_model_default():
    """With no watchdog block, the daily budget the driver renders must equal the default
    WatchdogConfig documents (D2 — was driver $5.00 vs model $1.00)."""
    from fabrik.drivers.watchdog import WatchdogDriver
    from fabrik.spec_loader import WatchdogConfig

    rctx = WatchdogDriver()._build_render_context({"id": "wd-app", "watchdog": {"enabled": True}}, ctx=None)
    assert rctx is not None
    assert rctx.daily_budget_usd == WatchdogConfig().daily_budget_usd


# ── D3: audit-registrars has a watchdog audit function ────────────────────────────────────

def test_d3_watchdog_has_an_audit_function():
    """`_AUDIT_FUNCS` must cover the watchdog registrar so audit-registrars can report
    present/missing instead of `unknown` forever (D3)."""
    from fabrik.audit import _AUDIT_FUNCS
    from fabrik.orchestrator.infrastructure import _REGISTRAR_ORDER

    assert "watchdog" in _AUDIT_FUNCS
    assert set(_REGISTRAR_ORDER) <= set(_AUDIT_FUNCS) | {"grafana"} or "watchdog" in _AUDIT_FUNCS


# ── D4: destroy --use-state removes the watchdog governance dir ────────────────────────────

def test_d4_destroy_from_state_removes_governance_dir():
    """`destroy_from_state` (the --use-state path) must call `_destroy_watchdog_governance`,
    same as the spec-driven destroy — else /var/lib/watchdog-governance/<id> leaks (D4)."""
    from fabrik.orchestrator import destroyer
    from tests.orchestrator.test_destroyer import _maximal_service_spec

    spec = _maximal_service_spec("wd-app")
    state_data = {"registrars_applied": []}
    with patch.object(destroyer, "_destroy_watchdog_governance", wraps=destroyer._destroy_watchdog_governance) as spy:
        destroyer.destroy_from_state(state_data, spec, dry_run=True, keep_dns=True, keep_files=True)
    assert spy.called, "destroy_from_state never called _destroy_watchdog_governance"


def _ctx(spec: dict):
    from pathlib import Path

    from fabrik.orchestrator.context import DeploymentContext

    ctx = DeploymentContext(spec_path=Path("test.yaml"), dry_run=False)
    ctx.spec = spec
    return ctx
