"""Tests for ``scripts/audit_authelia_gates.py``.

Covers Plan §8 + acceptance criterion at
``docs/development/plans/2026-04-18-zero-touch-deployment.md:2088``:

    scripts/audit_authelia_gates.py weekly cron prints 7 OK lines, 0 GAP
    lines against the current admin-dashboard inventory. Any GAP →
    Alertmanager → Telegram alert (§8).

The script is a drift detector for the Authelia gating invariant
(LESSONS_LEARNT §8.9): an Authelia `access_control` rule is only
enforced when Traefik also attaches `authelia-forward@docker` to the
router. Policy alone is not enforcement. Middleware alone is not policy.
Both must be present AND agree for every admin dashboard — any drift
silently breaks 2FA.

Canonical inventory (7 total — matches plan text):

  * 6 services expecting authelia-forward middleware:
    auto, backup, coolify, monitor, netdata, notify
  * 1 service expected to NOT have it (app-layer TOTP, §8.13):
    errors (GlitchTip)

Four states per dashboard:
  OK      — actual state matches expectation
  GAP     — expected middleware missing (unprotected dashboard)
  GAP     — unexpected middleware present (double-auth, breaks app)
  MISSING — host not found in Traefik routers at all (deploy regressed)

No live VPS: the ``ssh()`` helper is patched to return canned Traefik
``/api/http/routers`` JSON. Tests are deterministic and offline.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / "scripts" / "audit_authelia_gates.py"


@pytest.fixture(scope="module")
def audit_module():
    """Load the script as a module. It lives in ``scripts/`` (not a
    package) so ``importlib`` is the clean way in.

    ``sys.modules`` registration BEFORE ``exec_module`` is required —
    otherwise ``@dataclass`` breaks trying to resolve ``cls.__module__``
    to a dict when the module hasn't been registered yet
    (Python 3.12 dataclasses.py:749 ``NoneType has no __dict__``)."""
    mod_name = "audit_authelia_gates"
    spec = importlib.util.spec_from_file_location(mod_name, SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = module
    spec.loader.exec_module(module)
    return module


# --- Fixtures: synthetic Traefik /api/http/routers payloads ---------------- #


def _router(name: str, host: str, middlewares: list[str] | None) -> dict:
    """Shape-approximation of a Traefik-v3 dynamic router entry.

    Real payloads include many more fields (entryPoints, service, tls,
    status, etc.). The audit only inspects ``rule`` and ``middlewares``
    so we keep the fixture minimal to make intent obvious in tests."""
    entry = {
        "name": name,
        "rule": f"Host(`{host}`)",
    }
    if middlewares is not None:
        entry["middlewares"] = middlewares
    return entry


def _all_compliant() -> list[dict]:
    """All 7 canonical admin dashboards present with correct middleware.

    The audit should print 7 OK lines and exit 0 against this payload."""
    return [
        _router("n8n@docker", "auto.vps1.ocoron.com", ["authelia-forward@docker"]),
        _router("backrest@docker", "backup.vps1.ocoron.com", ["authelia-forward@docker"]),
        _router("coolify-ui@docker", "coolify.vps1.ocoron.com", ["authelia-forward@docker"]),
        _router("grafana@docker", "monitor.vps1.ocoron.com", ["authelia-forward@docker"]),
        _router("netdata@docker", "netdata.vps1.ocoron.com", ["authelia-forward@docker"]),
        _router("apprise@docker", "notify.vps1.ocoron.com", ["authelia-forward@docker"]),
        # errors/GlitchTip intentionally NO authelia middleware (§8.13)
        _router("glitchtip-web@docker", "errors.vps1.ocoron.com", []),
        # Unrelated routers the audit must ignore.
        _router("public-site@docker", "ocoron.com", []),
        _router("status@docker", "status.vps1.ocoron.com", []),
    ]


# --- Classification: classify_router() ------------------------------------- #


class TestClassify:
    """The pure classification function — no SSH, no IO."""

    def test_expected_middleware_present_is_ok(self, audit_module) -> None:
        dash = audit_module.ADMIN_DASHBOARDS[0]  # "auto"
        assert dash.authelia_expected is True
        router = _router("n8n@docker", "auto.vps1.ocoron.com", ["authelia-forward@docker"])
        result = audit_module.classify_router(dash, router)
        assert result.state == "OK"
        assert "authelia-forward@docker" in result.middlewares

    def test_expected_middleware_missing_is_gap(self, audit_module) -> None:
        dash = audit_module.ADMIN_DASHBOARDS[0]  # "auto"
        router = _router("n8n@docker", "auto.vps1.ocoron.com", [])
        result = audit_module.classify_router(dash, router)
        assert result.state == "GAP"
        assert "missing" in result.reason.lower()

    def test_unexpected_middleware_on_app_layer_service_is_gap(self, audit_module) -> None:
        """GlitchTip uses app-layer TOTP (§8.13). If someone accidentally
        adds authelia-forward, the user gets double-auth — app breaks.
        The audit must flag this as a GAP in the OTHER direction."""
        # Find the "errors" dashboard entry (authelia_expected=False).
        errors_dash = next(d for d in audit_module.ADMIN_DASHBOARDS if d.host == "errors")
        assert errors_dash.authelia_expected is False
        router = _router(
            "glitchtip-web@docker",
            "errors.vps1.ocoron.com",
            ["authelia-forward@docker"],  # WRONG — should not be here
        )
        result = audit_module.classify_router(errors_dash, router)
        assert result.state == "GAP"
        assert "unexpected" in result.reason.lower()

    def test_app_layer_service_without_middleware_is_ok(self, audit_module) -> None:
        """The canonical state for errors/GlitchTip — no middleware, uses
        app-layer TOTP. Must report OK."""
        errors_dash = next(d for d in audit_module.ADMIN_DASHBOARDS if d.host == "errors")
        router = _router("glitchtip-web@docker", "errors.vps1.ocoron.com", [])
        result = audit_module.classify_router(errors_dash, router)
        assert result.state == "OK"

    def test_any_authelia_middleware_variant_counts(self, audit_module) -> None:
        """Middleware names can vary (``authelia@docker``, ``authelia-
        forward@docker``, ``authelia-forward@file``). The audit's
        ``authelia`` substring match is permissive by design — any
        middleware with 'authelia' in the name is assumed to be a
        forward-auth gate (see LESSONS_LEARNT §8.9 audit snippet)."""
        dash = audit_module.ADMIN_DASHBOARDS[0]  # "auto", expected=True
        for variant in [
            "authelia-forward@docker",
            "authelia@docker",
            "authelia-forward@file",
            "my-authelia-custom@docker",
        ]:
            router = _router("x", f"{dash.host}.vps1.ocoron.com", [variant])
            result = audit_module.classify_router(dash, router)
            assert result.state == "OK", f"variant {variant!r} should satisfy the authelia check"


# --- Auditing: audit_routers() against full payloads ----------------------- #


class TestAuditRouters:
    """Full audit against a list of routers — the function the CLI calls."""

    def test_all_compliant_yields_seven_ok_zero_gap(self, audit_module) -> None:
        """The acceptance criterion: 7 OK lines, 0 GAP lines."""
        results = audit_module.audit_routers(_all_compliant())
        assert len(results) == 7, f"expected 7 results, got {len(results)}"
        assert all(r.state == "OK" for r in results), (
            f"non-OK entries: {[r for r in results if r.state != 'OK']}"
        )

    def test_missing_host_is_reported_as_missing(self, audit_module) -> None:
        """If an admin dashboard's host is not in the Traefik API output at
        all, it's been de-provisioned or the deploy regressed. Must be
        flagged — absence is not silence."""
        routers = _all_compliant()
        # Remove the "backup" dashboard from the payload.
        routers = [r for r in routers if "backup.vps1" not in r["rule"]]
        results = audit_module.audit_routers(routers)
        missing = [r for r in results if r.state == "MISSING"]
        assert len(missing) == 1
        assert missing[0].host == "backup"

    def test_gap_when_expected_middleware_dropped(self, audit_module) -> None:
        """Simulate the exact GlitchTip-class regression: middleware
        silently disappeared after a compose PATCH (§8.7 scenario)."""
        routers = _all_compliant()
        for r in routers:
            if "netdata.vps1" in r["rule"]:
                r["middlewares"] = []
        results = audit_module.audit_routers(routers)
        gaps = [r for r in results if r.state == "GAP"]
        assert len(gaps) == 1
        assert gaps[0].host == "netdata"

    def test_order_is_stable_and_alphabetical_by_canonical_inventory(self, audit_module) -> None:
        """Cron output is grep-friendly when order is stable. The order
        is defined by the canonical ADMIN_DASHBOARDS list, independent
        of the Traefik API's response order."""
        routers = list(reversed(_all_compliant()))  # reversed input
        results = audit_module.audit_routers(routers)
        # Output order must still match ADMIN_DASHBOARDS, not the reversed input.
        expected_hosts = [d.host for d in audit_module.ADMIN_DASHBOARDS]
        actual_hosts = [r.host for r in results]
        assert actual_hosts == expected_hosts


# --- CLI: main() exit codes + stdout shape --------------------------------- #


class TestCLI:
    """End-to-end via subprocess invoking the script with mocked SSH."""

    def test_cli_exits_zero_on_all_ok(self, audit_module) -> None:
        """Direct main() invocation with mocked ssh → Traefik payload."""
        payload = json.dumps(_all_compliant())
        with patch.object(audit_module, "ssh", return_value=payload):
            rc = audit_module.main([])
        assert rc == 0

    def test_cli_exits_one_when_any_gap(self, audit_module) -> None:
        routers = _all_compliant()
        for r in routers:
            if "coolify.vps1" in r["rule"]:
                r["middlewares"] = []  # middleware dropped
        payload = json.dumps(routers)
        with patch.object(audit_module, "ssh", return_value=payload):
            rc = audit_module.main([])
        assert rc == 1

    def test_cli_exits_one_when_host_missing(self, audit_module) -> None:
        routers = [r for r in _all_compliant() if "auto.vps1" not in r["rule"]]
        payload = json.dumps(routers)
        with patch.object(audit_module, "ssh", return_value=payload):
            rc = audit_module.main([])
        assert rc == 1

    def test_cli_exits_two_on_ssh_failure(self, audit_module) -> None:
        """Network / VPS unreachable is a different class of failure than
        drift — exit 2 (operational) vs exit 1 (policy). Cron alerting
        should be able to distinguish.

        We use RuntimeError because that's what the real ``ssh()`` helper
        raises on non-zero exit (``fabrik.drivers.ssh.ssh``)."""
        with patch.object(audit_module, "ssh", side_effect=RuntimeError("ssh down")):
            rc = audit_module.main([])
        assert rc == 2

    def test_cli_stdout_has_one_ok_line_per_dashboard_when_compliant(
        self, audit_module, capsys
    ) -> None:
        payload = json.dumps(_all_compliant())
        with patch.object(audit_module, "ssh", return_value=payload):
            audit_module.main([])
        out = capsys.readouterr().out
        ok_lines = [line for line in out.splitlines() if line.startswith("OK")]
        assert len(ok_lines) == 7, (
            f"expected 7 OK lines (plan §8 acceptance criterion), got "
            f"{len(ok_lines)}. Full stdout:\n{out}"
        )

    def test_cli_stdout_names_specific_host_on_gap(self, audit_module, capsys) -> None:
        """A cron alert that fires into Telegram needs to name the
        specific dashboard at fault — an operator shouldn't have to SSH
        in to find out which one drifted."""
        routers = _all_compliant()
        for r in routers:
            if "monitor.vps1" in r["rule"]:
                r["middlewares"] = []
        payload = json.dumps(routers)
        with patch.object(audit_module, "ssh", return_value=payload):
            audit_module.main([])
        out = capsys.readouterr().out
        gap_lines = [line for line in out.splitlines() if line.startswith("GAP")]
        assert len(gap_lines) == 1
        assert "monitor" in gap_lines[0]


# --- Integration: subprocess with --help / --inventory (no SSH needed) ----- #


class TestNoSSHSubcommands:
    """``--inventory`` dumps the canonical list without touching the VPS.
    Useful for CI and for operators cross-referencing against
    vps-complete-inventory.md."""

    def test_inventory_flag_prints_all_7_dashboards(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "--inventory"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0, result.stderr
        for host in ("auto", "backup", "coolify", "errors", "monitor", "netdata", "notify"):
            assert host in result.stdout

    def test_help_runs_without_error(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "--help"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0
        assert "authelia" in result.stdout.lower()
