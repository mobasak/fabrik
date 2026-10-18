"""W-719b2678: the watchdog driver stages nothing on the VPS under a predictable /tmp name.

A local VPS user could pre-create, swap or read `/tmp/fabrik-watchdog-build/<id>.tar.gz` (extracted by
root, then `docker build`), `/tmp/<id>-compose.watchdog.yaml` (WATCHDOG_PG_DSN) and
`/tmp/<id>-git-deploy.key` (a write-enabled deploy key). Every stage is now a remote `mktemp` file or
dir (random name, 0600/0700) made through `drivers.ssh.remote_mktemp`, and removed after use.
The remote host is a fake that answers `mktemp` the way GNU mktemp does; no ssh runs.
"""

from __future__ import annotations

import re
import types
from unittest import mock

import pytest

import fabrik.drivers.watchdog as wd
from fabrik.drivers.ssh import remote_mktemp
from fabrik.drivers.watchdog import WatchdogDriver, WatchdogProvisionError

_STAGE = re.compile(r"/tmp/fabrik-[A-Za-z0-9]{10}")


class _Remote:
    """A VPS that answers mktemp with a fresh name and records every command; `fail_on` raises."""

    def __init__(self, fail_on: str | None = None):
        self.cmds: list[str] = []
        self.made: list[str] = []
        self.kinds: list[str] = []  # "dir" or "file", one per made path
        self.fail_on = fail_on

    def __call__(self, cmd, *a, **k):
        self.cmds.append(cmd)
        if self.fail_on and self.fail_on in cmd:
            raise RuntimeError(f"boom: {self.fail_on}")
        if cmd.startswith("mktemp"):
            path = f"/tmp/fabrik-Stage{len(self.made):05d}"
            self.made.append(path)
            self.kinds.append("dir" if cmd.startswith("mktemp -d ") else "file")
            return path + "\n"
        if "test -f" in cmd:
            return "ABSENT"  # the deploy-key existence probe
        if cmd.startswith("cat "):
            return "ssh-ed25519 AAAAC3Nz stub watchdog-demo@fabrik"
        return ""


def _scp_failing(fail_on):
    def scp(local, dst, **k):
        if fail_on == "scp":
            raise RuntimeError("boom: scp")

    return scp


def _ctx(spec):
    return types.SimpleNamespace(spec=spec, app_name=spec.get("id"), target_vps=None)


def _rctx(driver, **wd_fields):
    spec = {"id": "demo", "watchdog": {"enabled": True, **wd_fields}}
    return driver._build_render_context(spec, _ctx(spec))


def _paths(text: str) -> list[str]:
    return re.findall(r"/tmp/[^\s'\";&|]+", text)


def _assert_only_stage_paths(remote: _Remote, scps: list[str]) -> None:
    """Every /tmp path the driver named lies inside a path mktemp handed back; the project id never
    names a /tmp entry."""
    named = [p for c in remote.cmds if not c.startswith("mktemp ") for p in _paths(c)] + scps
    assert named, "the driver staged nothing"
    for p in named:
        assert any(p == s or p.startswith(s + "/") for s in remote.made), (p, remote.made)
        assert not re.match(r"/tmp/[^/]*demo", p), p


@pytest.fixture
def sidecar(tmp_path, monkeypatch):
    """A minimal sidecar source _build_image can render and tar."""
    src = tmp_path / "watchdog_sidecar"
    src.mkdir()
    (src / "claude-settings.json.template").write_text('{"p": "<project_id>"}\n')
    (src / "Dockerfile").write_text('COPY claude-settings.json.template ./\nCMD ["python3"]\n')
    monkeypatch.setattr(wd, "SIDECAR_SOURCE", src)
    return src


@pytest.fixture
def governance_src(tmp_path, monkeypatch):
    proj = tmp_path / "projects" / "demo"
    proj.mkdir(parents=True)
    (proj / "CLAUDE.md").write_text("# CLAUDE\n")
    monkeypatch.setattr(wd, "_PROJECTS_ROOT", tmp_path / "projects")
    return proj


@pytest.mark.parametrize(
    "answer, ok",
    [
        ("/tmp/fabrik-Ab3dEf9hIj\n", True),
        ("Welcome to vps1\n/tmp/fabrik-Ab3dEf9hIj\n", True),
        ("/tmp/fabrik-Ab3dEf9hIj\nbye\n", False),
        ("", False),
        ("   \n", False),
        (None, False),
        (b"/tmp/fabrik-Ab3dEf9hIj", False),
        ("/tmp/x\n", False),
        ("/var/tmp/fabrik-Ab3dEf9hIj\n", False),
        ("/tmp/fabrik-Ab3dEf9hI\n", False),
        ("/tmp/fabrik-Ab3dEf9hIjk\n", False),
        ("/tmp/fabrik-Ab3d/f9hIj\n", False),
        ("/tmp/fabrik-Ab3d f9hIj\n", False),
    ],
)
@pytest.mark.parametrize("directory", [False, True])
def test_remote_mktemp_reads_only_a_mktemp_path(answer, ok, directory):
    cmds: list[str] = []

    def fake(cmd, *a, **k):
        cmds.append(cmd)
        return answer if cmd.startswith("mktemp") else ""

    if ok:
        assert remote_mktemp(fake, directory=directory) == "/tmp/fabrik-Ab3dEf9hIj"
        assert cmds == [("mktemp -d " if directory else "mktemp ") + "/tmp/fabrik-XXXXXXXXXX"]
        return
    with pytest.raises(RuntimeError, match="remote mktemp returned an unexpected path"):
        remote_mktemp(fake, directory=directory)
    # a path mktemp DID create before trailing output is removed; nothing else is touched
    removed = cmds[1:]
    if isinstance(answer, str) and "/tmp/fabrik-Ab3dEf9hIj\nbye" in answer:
        assert removed == [("rm -rf " if directory else "rm -f ") + "/tmp/fabrik-Ab3dEf9hIj"]
    else:
        assert removed == []


def test_every_watchdog_staging_path_is_a_mktemp_path(sidecar, governance_src):
    d = WatchdogDriver()
    remote, scps = _Remote(), []
    with (
        mock.patch.object(wd, "ssh", side_effect=remote),
        mock.patch.object(wd, "scp_to_vps", side_effect=lambda local, dst, **k: scps.append(dst)),
        mock.patch.object(d, "_detect_docker_sock_gid", return_value=999),
    ):
        rctx = _rctx(d, propose_fix_prs=True)
        d._build_image(rctx)
        assert d._push_governance(rctx) is True
        d._push_overlay(rctx)
        d._ensure_deploy_key(rctx)
    assert len(remote.made) == 4, remote.made  # build, governance, overlay, key: one stage each
    # the build and governance stages hold a tarball and its extract, the key a pair: dirs; the overlay
    # is moved into place as ONE file
    assert remote.kinds == ["dir", "dir", "file", "dir"], remote.kinds
    assert rctx.remote_build_dir == remote.made[0]
    _assert_only_stage_paths(remote, scps)
    keygen = next(c for c in remote.cmds if "ssh-keygen" in c)
    assert f"-f {remote.made[3]}/key" in keygen
    assert any(c.startswith("mktemp -d") for c in remote.cmds)


@pytest.mark.parametrize(
    "fail_on", [None, "scp", "tar -xzf", "ssh-keygen", "docker cp", "sudo mv", "sudo chown"]
)
def test_watchdog_stages_are_removed_and_never_guessed(fail_on, sidecar, governance_src):
    """Each stage is removed whether its step succeeds or fails, and nothing outside a stage is rm'd."""
    d = WatchdogDriver()
    remote = _Remote(fail_on=fail_on)
    with (
        mock.patch.object(wd, "ssh", side_effect=remote),
        mock.patch.object(wd, "scp_to_vps", side_effect=_scp_failing(fail_on)),
        mock.patch.object(d, "_detect_docker_sock_gid", return_value=999),
    ):
        rctx = _rctx(d, propose_fix_prs=True)
        steps = [
            lambda: d._build_image(rctx),
            lambda: d._push_governance(rctx),
            lambda: d._push_overlay(rctx),
            lambda: d._ensure_deploy_key(rctx),
        ]
        for step in steps:
            try:
                step()
            except (RuntimeError, WatchdogProvisionError):
                pass
        d._remove_build_stage(rctx)
    removes = [c for c in remote.cmds if re.search(r"\brm -r?f\b", c) and "/tmp/" in c]
    for stage in remote.made:
        # removed, or (the overlay on success) moved into place by the command that ran without error
        moved = (
            any(f"sudo mv {stage} " in c and not (fail_on and fail_on in c) for c in remote.cmds)
            and fail_on != "scp"
        )
        assert moved or any(stage in _paths(c) for c in removes), (stage, remote.cmds)
    for c in removes:
        assert all(any(p == s or p.startswith(s + "/") for s in remote.made) for p in _paths(c)), c


def test_no_stage_means_no_root_rm():
    """provision()'s cleanup removes the build stage only when one was made and still reads as one."""
    d = WatchdogDriver()
    for stage in (None, "", "/tmp/fabrik-watchdog-build", "/tmp/fabrik-Ab3dEf9hIj/..", "/"):
        remote = _Remote()
        with mock.patch.object(wd, "ssh", side_effect=remote):
            d._remove_build_stage(types.SimpleNamespace(remote_build_dir=stage))
        assert remote.cmds == [], (stage, remote.cmds)
    remote = _Remote()
    with mock.patch.object(wd, "ssh", side_effect=remote):
        d._remove_build_stage(types.SimpleNamespace(remote_build_dir="/tmp/fabrik-Ab3dEf9hIj"))
    assert remote.cmds == ["sudo rm -rf /tmp/fabrik-Ab3dEf9hIj"]


def test_the_overlay_is_private_before_it_moves():
    """The overlay carries WATCHDOG_PG_DSN: it is 0600 before it reaches /opt/<id>, where the sidecar's
    /project mount could otherwise read it."""
    d = WatchdogDriver()
    remote = _Remote()
    with (
        mock.patch.object(wd, "ssh", side_effect=remote),
        mock.patch.object(wd, "scp_to_vps"),
        mock.patch.object(d, "_detect_docker_sock_gid", return_value=999),
    ):
        d._push_overlay(_rctx(d))
    (stage,) = remote.made
    move = next(c for c in remote.cmds if "sudo mv" in c)
    assert move.index(f"sudo chmod 0600 {stage}") < move.index("sudo mv"), move
