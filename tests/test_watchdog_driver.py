"""Tests for the watchdog sidecar driver (src/fabrik/drivers/watchdog.py).

Enables dry-run + render-context testing with no VPS/SSH, and guards the
SIDECAR_SOURCE vendor path — regression for the 2026-06-29 break where
fabrik-lib renamed `sidecar/` → `watchdog_sidecar/`, which silently aborted
`fabrik apply` for every watchdog project at the build step.
"""

from __future__ import annotations

import types
from unittest import mock

import pytest

from fabrik.drivers.watchdog import (
    _BOOTSTRAP_PY,
    SIDECAR_SOURCE,
    WatchdogDriver,
    WatchdogProvisionError,
)


def _ctx(spec: dict, *, target_vps: str | None = None) -> types.SimpleNamespace:
    return types.SimpleNamespace(spec=spec, app_name=spec.get("id"), target_vps=target_vps)


class TestSidecarSource:
    def test_points_at_watchdog_sidecar(self):
        assert SIDECAR_SOURCE.name == "watchdog_sidecar"

    def test_vendor_path_exists_on_hub(self):
        # /opt/fabrik-lib is present on the hub; a drifted path would abort
        # _build_image() at runtime, so guard it here.
        assert SIDECAR_SOURCE.is_dir(), f"sidecar vendor path missing: {SIDECAR_SOURCE}"


class TestDryRun:
    def test_dry_run_returns_image_tag_without_ssh(self):
        r = WatchdogDriver().provision(
            _ctx({"id": "demo-proj", "watchdog": {"enabled": True}}), dry_run=True
        )
        assert r["status"] == "dry-run"
        assert r["image_tag"] == "fabrik/watchdog:demo-proj"

    def test_disabled_spec_skips(self):
        r = WatchdogDriver().provision(
            _ctx({"id": "demo", "watchdog": {"enabled": False}}), dry_run=True
        )
        assert r["status"] == "skipped"

    def test_missing_id_raises(self):
        with pytest.raises(WatchdogProvisionError, match="id/name"):
            WatchdogDriver().provision(_ctx({"watchdog": {"enabled": True}}), dry_run=True)


class TestRenderContext:
    def test_defaults(self):
        rctx = WatchdogDriver()._build_render_context(
            {"id": "demo", "watchdog": {"enabled": True}}, _ctx({"id": "demo"})
        )
        assert rctx is not None
        assert rctx.project_id == "demo"
        assert rctx.image_tag == "fabrik/watchdog:demo"
        assert rctx.target_vps == "vps1"
        assert rctx.redis_url.endswith("/15")  # watchdog's dedicated Redis DB index

    def test_target_vps_from_ctx(self):
        rctx = WatchdogDriver()._build_render_context(
            {"id": "demo", "watchdog": {"enabled": True}}, _ctx({"id": "demo"}, target_vps="vps2")
        )
        assert rctx.target_vps == "vps2"


def _rctx(driver: WatchdogDriver, *, propose_fix_prs: bool = False):
    spec = {"id": "demo", "watchdog": {"enabled": True, "propose_fix_prs": propose_fix_prs}}
    return driver._build_render_context(spec, _ctx(spec))


class TestAppHealthcheck:
    """Pre-flight: detect a missing app HEALTHCHECK (warn-only, never fails)."""

    def test_present_returns_true(self):
        d = WatchdogDriver()
        with mock.patch(
            "fabrik.drivers.watchdog.ssh", return_value="[CMD curl -fsS http://x/health]"
        ):
            assert d._check_app_healthcheck(_rctx(d)) is True

    @pytest.mark.parametrize("out", ["NONE", "MISSING", "[]", "<no value>", ""])
    def test_absent_returns_false_and_warns(self, out, caplog):
        d = WatchdogDriver()
        with mock.patch("fabrik.drivers.watchdog.ssh", return_value=out):
            with caplog.at_level("WARNING"):
                assert d._check_app_healthcheck(_rctx(d)) is False
        assert any("NO HEALTHCHECK" in r.message for r in caplog.records)


class TestDeployKey:
    """Generate-once git deploy key; idempotent; gated on propose_fix_prs."""

    def test_keeps_existing_key(self):
        d = WatchdogDriver()
        with mock.patch("fabrik.drivers.watchdog.ssh", return_value="PRESENT") as m:
            d._ensure_deploy_key(_rctx(d, propose_fix_prs=True))
        # Only the existence probe runs — no keygen / cp / cat.
        assert m.call_count == 1

    def test_no_container_raises(self):
        d = WatchdogDriver()
        with mock.patch("fabrik.drivers.watchdog.ssh", return_value="NOCONTAINER"):
            with pytest.raises(WatchdogProvisionError, match="not running"):
                d._ensure_deploy_key(_rctx(d, propose_fix_prs=True))

    def test_generates_when_absent_and_logs_pubkey(self, caplog):
        d = WatchdogDriver()
        pub = "ssh-ed25519 AAAAC3Nz...stub watchdog-demo@fabrik"
        # probe=ABSENT, keygen='', place='', cat=pubkey, rm=''
        side = ["ABSENT", "", "", pub, ""]
        with mock.patch("fabrik.drivers.watchdog.ssh", side_effect=side) as m:
            with caplog.at_level("WARNING"):
                d._ensure_deploy_key(_rctx(d, propose_fix_prs=True))
        joined = " ".join(c.args[0] for c in m.call_args_list)
        assert "ssh-keygen -t ed25519" in joined
        assert "docker cp" in joined
        assert "chmod 600" in joined
        assert any(pub in r.message for r in caplog.records)

    def test_removes_host_key_copy_even_if_place_fails(self):
        """The host-side tmp key must be rm'd even when docker cp/chmod errors."""
        d = WatchdogDriver()

        def boom(cmd, *a, **k):
            if cmd.startswith("sudo docker exec -u 0") and "test -f" in cmd:
                return "ABSENT"
            if cmd.startswith("rm -f") and "ssh-keygen" in cmd:
                return ""
            if "docker cp" in cmd:
                raise RuntimeError("cp failed")
            return ""

        with mock.patch("fabrik.drivers.watchdog.ssh", side_effect=boom) as m:
            with pytest.raises(RuntimeError, match="cp failed"):
                d._ensure_deploy_key(_rctx(d, propose_fix_prs=True))
        # The cleanup rm (finally) must have run.
        assert any(c.args[0].startswith("rm -f /tmp/") for c in m.call_args_list)


class TestDryRunSteps:
    def test_dry_run_lists_deploy_key_only_when_pushing(self, caplog):
        d = WatchdogDriver()
        with caplog.at_level("INFO"):
            d.provision(
                _ctx({"id": "p", "watchdog": {"enabled": True, "propose_fix_prs": True}}),
                dry_run=True,
            )
        assert any("deploy key" in r.message for r in caplog.records)

    def test_dry_run_omits_deploy_key_when_not_pushing(self, caplog):
        d = WatchdogDriver()
        with caplog.at_level("INFO"):
            d.provision(
                _ctx({"id": "p", "watchdog": {"enabled": True, "propose_fix_prs": False}}),
                dry_run=True,
            )
        assert not any("deploy key" in r.message for r in caplog.records)
        assert any("HEALTHCHECK" in r.message for r in caplog.records)

    def test_dry_run_lists_tier_d_bootstrap_when_auto_code_fix(self, caplog):
        d = WatchdogDriver()
        with caplog.at_level("INFO"):
            d.provision(
                _ctx(
                    {
                        "id": "p",
                        "watchdog": {
                            "enabled": True,
                            "propose_fix_prs": True,
                            "auto_code_fix": True,
                        },
                    }
                ),
                dry_run=True,
            )
        assert any("Tier-D bootstrap" in r.message for r in caplog.records)


def _tier_d_rctx(driver, *, git_remote="git@github.com:o/p.git"):
    # git remote comes from spec.source.repository (real flow), NOT the watchdog block.
    spec = {
        "id": "demo",
        "source": {"type": "git", "repository": git_remote} if git_remote else {"type": "docker"},
        "watchdog": {
            "enabled": True,
            "propose_fix_prs": True,
            "auto_code_fix": True,
            "code_fix_window_sec": 600,
            "critical_paths": ["src/auth/", "compose.yaml"],
        },
    }
    return driver._build_render_context(spec, _ctx(spec))


class TestGitRemoteDerivation:
    def test_from_source_repository(self):
        rctx = _tier_d_rctx(WatchdogDriver(), git_remote="git@github.com:o/p.git")
        assert rctx.project_git_remote == "git@github.com:o/p.git"

    def test_docker_source_yields_empty(self):
        # docker-sourced project has no git repo → empty remote → Tier-D gate rejects
        rctx = _tier_d_rctx(WatchdogDriver(), git_remote="")
        assert rctx.project_git_remote == ""


class TestTierDRenderContext:
    def test_fields_threaded(self):
        rctx = _tier_d_rctx(WatchdogDriver())
        assert rctx.auto_code_fix is True
        assert rctx.code_fix_window_sec == 600
        assert rctx.critical_paths == ["src/auth/", "compose.yaml"]

    def test_driver_defaults_match_pydantic(self):
        """R-E: the raw-dict driver defaults must equal the Pydantic defaults."""
        from fabrik.spec_loader import WatchdogConfig

        rctx = WatchdogDriver()._build_render_context(
            {"id": "demo", "watchdog": {"enabled": True}}, _ctx({"id": "demo"})
        )
        wc = WatchdogConfig()
        assert rctx.auto_code_fix == wc.auto_code_fix
        assert rctx.code_fix_window_sec == wc.code_fix_window_sec
        assert rctx.critical_paths == wc.critical_paths


class TestTierDEnv:
    def test_env_emitted_only_when_auto_code_fix(self):
        d = WatchdogDriver()
        on = d._render_env(_tier_d_rctx(d))
        assert on["WATCHDOG_AUTO_CODE_FIX"] == "true"
        assert on["WATCHDOG_PROPOSE_FIX_PRS"] == "true"
        assert on["WATCHDOG_APPROVAL_WINDOW_SEC"] == "600"
        assert on["WATCHDOG_CRITICAL_PATHS"] == "src/auth/,compose.yaml"

        off = d._render_env(_rctx(d))
        assert "WATCHDOG_AUTO_CODE_FIX" not in off
        assert "WATCHDOG_APPROVAL_WINDOW_SEC" not in off


class TestTriggerSources:
    def test_rendered_when_set(self):
        d = WatchdogDriver()
        spec = {
            "id": "demo",
            "watchdog": {"enabled": True, "trigger_sources": ["emitter", "health", "error_webhook"]},
        }
        env = d._render_env(d._build_render_context(spec, _ctx(spec)))
        assert env["WATCHDOG_TRIGGER_SOURCES"] == "emitter,health,error_webhook"

    def test_absent_when_empty(self):
        # Empty → unset → library legacy poll path (no bus). Backward-compatible.
        d = WatchdogDriver()
        env = d._render_env(_rctx(d))
        assert "WATCHDOG_TRIGGER_SOURCES" not in env

    def test_independent_of_tier_d(self):
        # error_webhook trigger needs no Tier-D / git source.
        d = WatchdogDriver()
        spec = {"id": "demo", "watchdog": {"enabled": True, "trigger_sources": ["error_webhook"]}}
        rctx = d._build_render_context(spec, _ctx(spec))
        assert rctx.auto_code_fix is False
        assert d._render_env(rctx)["WATCHDOG_TRIGGER_SOURCES"] == "error_webhook"

    def test_critical_paths_rendered_for_alerting_only_target(self):
        # error_webhook on, auto_code_fix OFF → critical_paths must still render
        # (else signals capture but never page). This is the activation dep.
        d = WatchdogDriver()
        spec = {
            "id": "demo",
            "watchdog": {
                "enabled": True,
                "trigger_sources": ["health", "error_webhook"],
                "critical_paths": ["PaymentError", "/checkout"],
            },
        }
        env = d._render_env(d._build_render_context(spec, _ctx(spec)))
        assert env["WATCHDOG_CRITICAL_PATHS"] == "PaymentError,/checkout"
        assert "WATCHDOG_AUTO_CODE_FIX" not in env  # no Tier-D

    def test_warns_error_webhook_without_critical_paths(self, caplog):
        d = WatchdogDriver()
        spec = {"id": "demo", "watchdog": {"enabled": True, "trigger_sources": ["error_webhook"]}}
        with caplog.at_level("WARNING"):
            env = d._render_env(d._build_render_context(spec, _ctx(spec)))
        assert "WATCHDOG_CRITICAL_PATHS" not in env
        assert any("never PAGE" in r.message for r in caplog.records)


class TestGateTierD:
    def test_missing_git_remote_hard_fails(self):
        d = WatchdogDriver()
        rctx = _tier_d_rctx(d, git_remote="")
        with pytest.raises(WatchdogProvisionError, match="project_git_remote is empty"):
            d._gate_tier_d(rctx, has_healthcheck=True)

    def test_no_healthcheck_degrades_to_escalate_only(self, caplog):
        d = WatchdogDriver()
        rctx = _tier_d_rctx(d)
        with caplog.at_level("ERROR"):
            d._gate_tier_d(rctx, has_healthcheck=False)
        assert rctx.auto_code_fix is False  # degraded
        assert any("REFUSING Tier-D" in r.message for r in caplog.records)

    def test_all_prereqs_met_keeps_tier_d(self):
        d = WatchdogDriver()
        rctx = _tier_d_rctx(d)
        d._gate_tier_d(rctx, has_healthcheck=True)
        assert rctx.auto_code_fix is True

    def test_noop_when_tier_d_off(self):
        d = WatchdogDriver()
        rctx = _rctx(d)  # auto_code_fix False
        d._gate_tier_d(rctx, has_healthcheck=False)  # must not raise
        assert rctx.auto_code_fix is False


class TestBootstrapTemplate:
    def test_is_valid_python(self):
        compile(_BOOTSTRAP_PY, "bootstrap.py", "exec")

    def test_wires_repo_dir_to_proposed_workspace(self):
        # repo_dir MUST be the stable per-project clone agent.propose_fix reuses.
        assert "PROPOSED_WORKSPACE_ROOT" in _BOOTSTRAP_PY
        assert "GitPushDeployAdapter(" in _BOOTSTRAP_PY
        assert "configure(**build_deps())" in _BOOTSTRAP_PY

    def test_refuses_without_telegram(self):
        # The bootstrap must hard-exit (not silently degrade) if Telegram is unset.
        assert "raise SystemExit" in _BOOTSTRAP_PY
        assert "TelegramBot.from_env()" in _BOOTSTRAP_PY
