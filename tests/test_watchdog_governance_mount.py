"""Tests for the watchdog governance-mount shipping (plan-2).

`_push_governance` ships the project's governance set (CLAUDE.md + AGENTS.md +
`.windsurf/rules/`) from the hub's project tree to a dedicated per-project VPS
dir, and gates the `/governance:ro` bind mount + `WATCHDOG_GOVERNANCE_MOUNT`
env — fail-soft (any problem → skip, sidecar materialize falls back to
`/project`). The `/project` mount is hollow on the VPS because deploy excludes
gitignored `.windsurf/rules/`; this makes governance reliably readable.
"""

from __future__ import annotations

import types
from unittest import mock

import pytest

import fabrik.drivers.watchdog as wd
from fabrik.drivers.watchdog import WatchdogDriver


def _ctx(spec: dict, *, target_vps: str | None = None) -> types.SimpleNamespace:
    return types.SimpleNamespace(spec=spec, app_name=spec.get("id"), target_vps=target_vps)


def _rctx(driver: WatchdogDriver):
    spec = {"id": "demo", "watchdog": {"enabled": True}}
    return driver._build_render_context(spec, _ctx(spec))


@pytest.fixture
def governance_src(tmp_path, monkeypatch):
    """Fake project tree under a patched _PROJECTS_ROOT carrying the full set."""
    proj = tmp_path / "demo"
    (proj / ".windsurf" / "rules" / "core").mkdir(parents=True)
    (proj / "CLAUDE.md").write_text("# CLAUDE\n", encoding="utf-8")
    (proj / "AGENTS.md").write_text("# AGENTS\n", encoding="utf-8")
    (proj / ".windsurf" / "rules" / "core" / "30-ops.md").write_text("ops\n", encoding="utf-8")
    monkeypatch.setattr(wd, "_PROJECTS_ROOT", tmp_path)
    return tmp_path


class TestPushGovernance:
    def test_ships_and_returns_true(self, governance_src):
        d = WatchdogDriver()
        rctx = _rctx(d)
        with (
            mock.patch("fabrik.drivers.watchdog.ssh") as m_ssh,
            mock.patch("fabrik.drivers.watchdog.scp_to_vps") as m_scp,
        ):
            ok = d._push_governance(rctx)
        assert ok is True
        # Exactly one scp (local governance tar → remote).
        assert m_scp.call_count == 1
        joined = " ".join(c.args[0] for c in m_ssh.call_args_list if c.args)
        assert "/var/lib/watchdog-governance/demo" in joined  # dedicated per-project dir
        assert "tar -xzf" in joined
        assert "chmod -R a+rX" in joined  # non-secret, world-readable (NOT chmod 600)
        assert "rm -rf /var/lib/watchdog-governance/demo" in joined  # wipe+recreate (refresh)

    def test_tar_contains_all_three_members_flat_at_root(self, governance_src):
        """The mount root must present /governance/{CLAUDE.md,AGENTS.md,.windsurf/rules/**}."""
        d = WatchdogDriver()
        rctx = _rctx(d)
        captured = {}

        def cap_scp(local_path, remote_path, **kw):
            import tarfile

            with tarfile.open(local_path) as t:
                captured["names"] = t.getnames()

        with (
            mock.patch("fabrik.drivers.watchdog.ssh"),
            mock.patch("fabrik.drivers.watchdog.scp_to_vps", side_effect=cap_scp),
        ):
            assert d._push_governance(rctx) is True
        names = captured["names"]
        assert "CLAUDE.md" in names
        assert "AGENTS.md" in names
        assert any(n.startswith(".windsurf/rules") for n in names)

    def test_no_source_returns_false_no_scp(self, tmp_path, monkeypatch):
        monkeypatch.setattr(wd, "_PROJECTS_ROOT", tmp_path)  # empty — no governance members
        d = WatchdogDriver()
        rctx = _rctx(d)
        with (
            mock.patch("fabrik.drivers.watchdog.ssh") as m_ssh,  # noqa: F841
            mock.patch("fabrik.drivers.watchdog.scp_to_vps") as m_scp,
        ):
            ok = d._push_governance(rctx)
        assert ok is False
        assert m_scp.call_count == 0

    @pytest.mark.parametrize("bad_id", ["../etc", "a/b", ".hidden", ""])
    def test_unsafe_project_id_returns_false_no_scp(self, bad_id, tmp_path, monkeypatch):
        """A traversal/absolute/hidden id must be refused before any path/ssh use."""
        monkeypatch.setattr(wd, "_PROJECTS_ROOT", tmp_path)
        d = WatchdogDriver()
        rctx = _rctx(d)
        rctx.project_id = bad_id
        with (
            mock.patch("fabrik.drivers.watchdog.ssh") as m_ssh,  # noqa: F841
            mock.patch("fabrik.drivers.watchdog.scp_to_vps") as m_scp,
        ):
            assert d._push_governance(rctx) is False
        assert m_scp.call_count == 0

    def test_ssh_failure_is_fail_soft(self, governance_src):
        """A VPS-side failure must return False, never raise (never abort provision)."""
        d = WatchdogDriver()
        rctx = _rctx(d)
        with (
            mock.patch("fabrik.drivers.watchdog.ssh", side_effect=RuntimeError("boom")),
            mock.patch("fabrik.drivers.watchdog.scp_to_vps"),
        ):
            ok = d._push_governance(rctx)  # must NOT raise
        assert ok is False

    def test_mkdtemp_failure_is_fail_soft(self, governance_src):
        """Even a local temp-dir failure must stay fail-soft (not raise out of provision)."""
        d = WatchdogDriver()
        rctx = _rctx(d)
        with (
            mock.patch("fabrik.drivers.watchdog.tempfile.mkdtemp", side_effect=OSError("no space")),
            mock.patch("fabrik.drivers.watchdog.ssh"),
            mock.patch("fabrik.drivers.watchdog.scp_to_vps") as m_scp,
        ):
            ok = d._push_governance(rctx)  # must NOT raise
        assert ok is False
        assert m_scp.call_count == 0


class TestOverlayVolumeGate:
    def _run_push_overlay(self, ready: bool, governance_src):
        d = WatchdogDriver()
        rctx = _rctx(d)
        rctx.governance_mount_ready = ready
        captured = {}
        real_dump = wd.yaml.safe_dump

        def cap_dump(obj, **kw):
            captured["compose"] = obj
            return real_dump(obj, **kw)

        with (
            mock.patch("fabrik.drivers.watchdog.ssh"),
            mock.patch("fabrik.drivers.watchdog.scp_to_vps"),
            mock.patch.object(d, "_detect_docker_sock_gid", return_value=999),
            mock.patch("fabrik.drivers.watchdog.yaml.safe_dump", side_effect=cap_dump),
        ):
            d._push_overlay(rctx)
        return captured["compose"]["services"]["watchdog"]["volumes"]

    def test_mount_added_when_ready(self, governance_src):
        vols = self._run_push_overlay(True, governance_src)
        assert "/var/lib/watchdog-governance/demo:/governance:ro" in vols

    def test_mount_absent_when_not_ready(self, governance_src):
        vols = self._run_push_overlay(False, governance_src)
        assert not any("/governance" in v for v in vols)


class TestRenderEnvGate:
    def test_env_set_when_ready(self):
        d = WatchdogDriver()
        rctx = _rctx(d)
        rctx.governance_mount_ready = True
        assert d._render_env(rctx)["WATCHDOG_GOVERNANCE_MOUNT"] == "/governance"

    def test_env_absent_when_not_ready(self):
        d = WatchdogDriver()
        rctx = _rctx(d)  # governance_mount_ready defaults False
        assert "WATCHDOG_GOVERNANCE_MOUNT" not in d._render_env(rctx)
