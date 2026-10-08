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

    def test_the_build_context_leaves_the_tool_caches_behind(self, tmp_path, monkeypatch):
        """The sidecar source on this box accumulates tool caches; a bare copytree shipped
        them into every sidecar image (W-f829a5aa)."""
        src = tmp_path / "watchdog_sidecar"
        (src / "pkg" / "__pycache__").mkdir(parents=True)
        (src / "pkg" / "agent.py").write_text("x = 1\n")
        (src / "pkg" / "__pycache__" / "agent.cpython-312.pyc").write_bytes(b"\0")
        (src / "stray.pyc").write_bytes(b"\0")
        for cache in (".mypy_cache", ".pytest_cache", ".ruff_cache"):
            (src / cache).mkdir()
            (src / cache / "entry").write_text("cached\n")
        monkeypatch.setattr("fabrik.drivers.watchdog.SIDECAR_SOURCE", src)
        ctx_dir = tmp_path / "ctx"
        ctx_dir.mkdir()
        monkeypatch.setattr("fabrik.drivers.watchdog.tempfile.mkdtemp", lambda **_kw: str(ctx_dir))
        rctx = types.SimpleNamespace(project_id="p", main_container="p", project_prefix="p")
        # No settings template in the fake tree: the build stops right after the copy.
        with pytest.raises(FileNotFoundError):
            WatchdogDriver()._build_image(rctx)
        shipped = sorted(
            p.relative_to(rctx.build_ctx_local).as_posix() for p in rctx.build_ctx_local.rglob("*")
        )
        assert shipped == ["pkg", "pkg/agent.py"]

    def test_provision_removes_the_build_tarball_beside_the_context(self, tmp_path):
        """_build_image writes <ctx>.tar.gz NEXT TO the context dir; the cleanup removed only the
        dir, so every build left a tarball in /tmp (W-f829a5aa review)."""
        d = WatchdogDriver()
        ctx_dir = tmp_path / "watchdog-build-demo-x"

        def build(rctx):
            ctx_dir.mkdir()
            rctx.build_ctx_local = ctx_dir
            ctx_dir.with_suffix(".tar.gz").write_bytes(b"\0")
            raise WatchdogProvisionError("scp failed")

        spec = {"id": "demo", "watchdog": {"enabled": True}}
        with (
            mock.patch.object(d, "_check_app_healthcheck", return_value=True),
            mock.patch.object(d, "_build_image", side_effect=build),
            mock.patch("fabrik.drivers.watchdog.ssh", return_value=""),
            pytest.raises(WatchdogProvisionError, match="scp failed"),
        ):
            d.provision(_ctx(spec))
        assert not ctx_dir.exists()
        assert not ctx_dir.with_suffix(".tar.gz").exists(), "the build tarball was left behind"

    def test_a_failing_tarball_cleanup_never_masks_the_build_error(self, tmp_path):
        """The cleanup is best-effort: a directory squatting on <ctx>.tar.gz makes unlink raise,
        and that must not replace the build's own error or skip the remote cleanup."""
        d = WatchdogDriver()
        ctx_dir = tmp_path / "watchdog-build-demo-y"

        def build(rctx):
            ctx_dir.mkdir()
            rctx.build_ctx_local = ctx_dir
            ctx_dir.with_suffix(".tar.gz").mkdir()
            raise WatchdogProvisionError("scp failed")

        spec = {"id": "demo", "watchdog": {"enabled": True}}
        with (
            mock.patch.object(d, "_check_app_healthcheck", return_value=True),
            mock.patch.object(d, "_build_image", side_effect=build),
            mock.patch("fabrik.drivers.watchdog.ssh", return_value="") as remote,
            pytest.raises(WatchdogProvisionError, match="scp failed"),
        ):
            d.provision(_ctx(spec))
        assert any("rm -rf" in c.args[0] for c in remote.call_args_list), "remote cleanup skipped"


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

    @pytest.mark.parametrize("key", ["daily_budget_usd", "per_incident_budget_usd"])
    @pytest.mark.parametrize("raw", [float("inf"), float("nan"), "inf", "x"])
    def test_a_non_finite_budget_never_reaches_the_sidecar_env(self, key, raw):
        """provision() is public: the render step refuses an inf/nan budget itself instead of
        writing WATCHDOG_*_BUDGET_USD=inf (no ceiling) into the sidecar."""
        spec = {"id": "demo", "watchdog": {"enabled": True, key: raw}}
        with pytest.raises(ValueError, match=f"{key} must be a finite number"):
            WatchdogDriver()._build_render_context(spec, _ctx(spec))

    def test_finite_budgets_render_unchanged(self):
        spec = {"id": "demo", "watchdog": {"daily_budget_usd": 2, "per_incident_budget_usd": "0.5"}}
        rctx = WatchdogDriver()._build_render_context(spec, _ctx(spec))
        assert (rctx.daily_budget_usd, rctx.per_incident_budget_usd) == (2.0, 0.5)

    def test_the_retired_promtail_drop_url_is_never_rendered(self):
        """install_log_drop_rule is retired (fabrik-lib D-398): a spec still naming its Promtail
        update URL renders no WATCHDOG_PROMTAIL_UPDATE_URL into the sidecar (W-1feb4dfa)."""
        spec = {"id": "demo", "watchdog": {"enabled": True, "promtail_update_url": "http://p:9080"}}
        d = WatchdogDriver()
        env = d._render_env(d._build_render_context(spec, _ctx(spec)))
        assert not [k for k in env if "PROMTAIL" in k], env


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
            "watchdog": {
                "enabled": True,
                "trigger_sources": ["emitter", "health", "error_webhook"],
            },
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


_B2 = {"STORAGE_BACKEND": "b2", "B2_KEY_ID": "k", "B2_APPLICATION_KEY": "a", "B2_BUCKET_NAME": "b"}
_SUPABASE = {
    "STORAGE_BACKEND": "supabase",
    "SUPABASE_URL": "https://x.supabase.co",
    "SUPABASE_SERVICE_KEY": "s",
    "SUPABASE_BUCKET": "b",
}


class TestGateTierD:
    def test_missing_git_remote_hard_fails(self):
        d = WatchdogDriver()
        rctx = _tier_d_rctx(d, git_remote="")
        with pytest.raises(WatchdogProvisionError, match="project_git_remote is empty"):
            d._gate_tier_d(rctx, has_healthcheck=True, storage_env=_B2)

    def test_no_healthcheck_degrades_to_escalate_only(self, caplog):
        d = WatchdogDriver()
        rctx = _tier_d_rctx(d)
        with caplog.at_level("ERROR"):
            d._gate_tier_d(rctx, has_healthcheck=False, storage_env={})
        assert rctx.auto_code_fix is False  # degraded
        assert any("REFUSING Tier-D" in r.message for r in caplog.records)
        # one reason per refusal: the storage check does not pile on
        assert not any("pre-apply snapshot" in r.message for r in caplog.records)

    @pytest.mark.parametrize("env", [_B2, _SUPABASE, {**_B2, "STORAGE_BACKEND": "B2"}])
    def test_all_prereqs_met_keeps_tier_d(self, env):
        d = WatchdogDriver()
        rctx = _tier_d_rctx(d)
        d._gate_tier_d(rctx, has_healthcheck=True, storage_env=env)
        assert rctx.auto_code_fix is True

    @pytest.mark.parametrize(
        "env",
        [
            {},
            {"STORAGE_BACKEND": "s3"},
            {**_B2, "STORAGE_BACKEND": ""},
            {k: v for k, v in _B2.items() if k != "B2_APPLICATION_KEY"},  # backend, no key
            {**_SUPABASE, "SUPABASE_BUCKET": ""},
            {**_B2, "B2_BUCKET_NAME": "  "},
        ],
    )
    def test_no_usable_snapshot_storage_degrades_to_escalate_only(self, env, caplog):
        """The sidecar refuses every apply whose pre-apply snapshot it cannot store (mail 01M384GX):
        an autonomous loop that can never apply a fix is escalate-only in all but name."""
        d = WatchdogDriver()
        rctx = _tier_d_rctx(d)
        with caplog.at_level("ERROR"):
            d._gate_tier_d(rctx, has_healthcheck=True, storage_env=env)
        assert rctx.auto_code_fix is False
        msgs = [r.getMessage() for r in caplog.records]
        assert any("pre-apply snapshot" in m and "REFUSING Tier-D" in m for m in msgs)
        assert all("https://x.supabase.co" not in m for m in msgs)  # values are never logged

    def test_noop_when_tier_d_off(self):
        d = WatchdogDriver()
        rctx = _rctx(d)  # auto_code_fix False
        d._gate_tier_d(rctx, has_healthcheck=False, storage_env={})  # must not raise
        assert rctx.auto_code_fix is False


class TestReadStorageEnv:
    """The snapshot keys of the app's /opt/<id>/.env as compose's env_file reads them."""

    @pytest.mark.parametrize(
        ("out", "want"),
        [
            ("STORAGE_BACKEND=b2\n", "b2"),
            ('STORAGE_BACKEND="supabase"\n', "supabase"),
            ("export STORAGE_BACKEND=b2\n", "b2"),
            ("  STORAGE_BACKEND=b2\n", "b2"),
            ("STORAGE_BACKEND=b2 # prod\n", "b2"),
            ('STORAGE_BACKEND="b2" # prod\n', "b2"),
            ("STORAGE_BACKEND=b2\r\n", "b2"),
            ('STORAGE_BACKEND=b2"\n', 'b2"'),  # an unmatched quote is kept, as compose keeps it
            ("STORAGE_BACKEND=b2\n export STORAGE_BACKEND=supabase\n", "supabase"),  # last wins
            ("STORAGE_BACKEND = b2\n", "b2"),
            ("STORAGE_BACKEND: b2\n", "b2"),
            ("STORAGE_BACKEND=${BACKEND}\n", ""),  # unresolved interpolation reads as unset
            ('STORAGE_BACKEND="$BACKEND"\n', ""),  # double quotes still interpolate
            ("", None),
        ],
    )
    def test_parses_like_compose_env_file(self, out, want):
        d = WatchdogDriver()
        with mock.patch("fabrik.drivers.watchdog.ssh", return_value=out) as m:
            env = d._read_storage_env(_rctx(d))
        assert env.get("STORAGE_BACKEND") == want
        cmd = m.call_args.args[0]
        assert "/opt/demo/.env" in cmd and "export" in cmd and "B2_KEY_ID" in cmd

    @pytest.mark.parametrize(
        ("line", "want"),
        [
            ("B2_APPLICATION_KEY='abc$def'", "abc$def"),  # single quotes: literal
            ("B2_APPLICATION_KEY=abc$$def", "abc$def"),  # $$ is an escaped $
            ("B2_APPLICATION_KEY=abc$def", ""),  # a reference: unresolved
            ('B2_APPLICATION_KEY="${K}"', ""),
        ],
    )
    def test_interpolation_like_compose(self, line, want):
        d = WatchdogDriver()
        with mock.patch("fabrik.drivers.watchdog.ssh", return_value=line + "\n"):
            assert d._read_storage_env(_rctx(d))["B2_APPLICATION_KEY"] == want
        env = {**_B2, "B2_APPLICATION_KEY": want}
        rctx = _tier_d_rctx(d)
        d._gate_tier_d(rctx, has_healthcheck=True, storage_env=env)
        assert rctx.auto_code_fix is bool(
            want
        )  # a literal with $ keeps Tier-D; unresolved degrades

    def test_reads_the_backend_keys_too(self):
        d = WatchdogDriver()
        out = "STORAGE_BACKEND=b2\nB2_KEY_ID=k\nB2_APPLICATION_KEY='a'\nB2_BUCKET_NAME=b\nOTHER=x\n"
        with mock.patch("fabrik.drivers.watchdog.ssh", return_value=out):
            assert d._read_storage_env(_rctx(d)) == _B2

    def test_an_ssh_failure_reads_as_empty(self):
        d = WatchdogDriver()
        with mock.patch("fabrik.drivers.watchdog.ssh", side_effect=RuntimeError("down")):
            assert d._read_storage_env(_rctx(d)) == {}

    def test_the_remote_grep_selects_what_the_parser_needs(self, tmp_path):
        """Run the exact command the driver sends (minus sudo, against a local copy of the .env)."""
        import subprocess

        dotenv = tmp_path / ".env"
        dotenv.write_text(
            "OTHER=1\n  export STORAGE_BACKEND=b2 # prod\nB2_KEY_ID = k\n#STORAGE_BACKEND=x\n"
            "B2_APPLICATION_KEY: a\nB2_BUCKET_NAME=b\nSTORAGE_BACKENDX=no\n",
            encoding="utf-8",
        )
        d = WatchdogDriver()
        with mock.patch("fabrik.drivers.watchdog.ssh", return_value="") as m:
            d._read_storage_env(_rctx(d))
        cmd = m.call_args.args[0].replace("sudo ", "", 1).replace("/opt/demo/.env", str(dotenv))
        out = subprocess.run(cmd, shell=True, capture_output=True, text=True, check=True).stdout
        with mock.patch("fabrik.drivers.watchdog.ssh", return_value=out):
            assert d._read_storage_env(_rctx(d)) == _B2


class TestProvisionWiresTheStorageGate:
    """provision() feeds the gate what the reader returned, and probes only for Tier-D."""

    class _StopError(Exception):
        pass

    def _run(self, spec_watchdog):
        d = WatchdogDriver()
        seen = {}

        def gate(rctx, has_hc, storage_env):
            seen["storage_env"] = storage_env
            raise self._StopError

        spec = {"id": "p", "source": {"type": "git", "repository": "git@github.com:o/p.git"}}
        spec["watchdog"] = {"enabled": True, **spec_watchdog}
        with (
            mock.patch.object(d, "_check_app_healthcheck", return_value=True),
            mock.patch.object(d, "_read_storage_env", return_value={"STORAGE_BACKEND": "zz"}) as rd,
            mock.patch.object(d, "_gate_tier_d", side_effect=gate),
        ):
            with pytest.raises(WatchdogProvisionError, match="_StopError"):
                d.provision(_ctx(spec), dry_run=False)  # provision wraps every failure
        return seen["storage_env"], rd.call_count

    def test_tier_d_reads_and_forwards_the_storage_env(self):
        env, calls = self._run({"propose_fix_prs": True, "auto_code_fix": True})
        assert env == {"STORAGE_BACKEND": "zz"} and calls == 1

    def test_no_probe_without_tier_d(self):
        env, calls = self._run({})
        assert env == {} and calls == 0


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


class TestLlmActions:
    """watchdog.llm_actions → WATCHDOG_LLM_ACTIONS (fabrik-lib D-412). `fabrik apply` takes the raw
    spec dict, so the render context must apply the same check WatchdogConfig does."""

    def _render(self, wcfg: dict):
        d = WatchdogDriver()
        spec = {"id": "demo", "watchdog": {"enabled": True, **wcfg}}
        return d._render_env(d._build_render_context(spec, _ctx(spec)))

    def test_llm_actions_rendered_only_when_set(self):
        from fabrik.spec_loader import WatchdogConfig

        env = self._render({"llm_actions": ["Pause_Worker", "clear_file_cache", "pause_worker"]})
        assert env["WATCHDOG_LLM_ACTIONS"] == "pause_worker,clear_file_cache"
        assert "WATCHDOG_LLM_ACTIONS" not in self._render({})
        d = WatchdogDriver()
        rctx = d._build_render_context({"id": "demo", "watchdog": {"enabled": True}}, _ctx({"id": "demo"}))
        assert rctx.llm_actions == WatchdogConfig().llm_actions

    @pytest.mark.parametrize("value", ["pause_worker", ["bogus"], ["create_fix_pr"]])
    def test_render_context_validates_llm_actions(self, value):
        with pytest.raises(ValueError, match="llm_actions"):
            self._render({"llm_actions": value})

    def test_tier_b_llm_action_without_auto_tier_b_warns(self, caplog):
        with caplog.at_level("WARNING"):
            env = self._render({"llm_actions": ["wipe_redis_cache"]})
        assert env["WATCHDOG_LLM_ACTIONS"] == "wipe_redis_cache"
        assert any("auto_tier_b" in r.message and "wipe_redis_cache" in r.message for r in caplog.records)
        caplog.clear()
        with caplog.at_level("WARNING"):
            self._render({"llm_actions": ["wipe_redis_cache"], "auto_tier_b": True})
        assert not any("auto_tier_b" in r.message for r in caplog.records)

    def test_stale_sidecar_source_warns(self, caplog, tmp_path, monkeypatch):
        import fabrik.drivers.watchdog as wd

        (tmp_path / "actions.py").write_text("DEFAULT_MENU = ('restart_container',)\n")
        monkeypatch.setattr(wd, "SIDECAR_SOURCE", tmp_path)
        with caplog.at_level("WARNING"):
            self._render({"llm_actions": ["pause_worker"]})
        assert any("does not read WATCHDOG_LLM_ACTIONS" in r.message for r in caplog.records)
        # A source that reads it — here from a subpackage — stays quiet (no always-warn).
        (tmp_path / "sub").mkdir()
        (tmp_path / "sub" / "menu.py").write_text('RAW = os.environ.get("WATCHDOG_LLM_ACTIONS", "")\n')
        caplog.clear()
        with caplog.at_level("WARNING"):
            self._render({"llm_actions": ["pause_worker"]})
        assert not any("does not read WATCHDOG_LLM_ACTIONS" in r.message for r in caplog.records)
