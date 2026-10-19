"""The monitoring drivers stage on the VPS through mktemp, never a fixed /tmp name (W-42e79070).

A fixed name (`/tmp/prometheus.yml.staged`, `/tmp/redis-assignments.json`,
`/tmp/gatus-endpoint-<name>.yaml`) let another VPS user pre-create or swap the file before the
`sudo mv` installed it as root. `ssh.install_world_readable` stages in a `remote_mktemp` file, makes
it root:root 0644 before the move, so the destination appears in one rename with its final owner
and mode, and removes it on every failure (D-1000's slice 2, D-1038).
"""

from __future__ import annotations

import pytest

from fabrik.drivers import gatus, prometheus, redis, ssh

STAGE = "/tmp/fabrik-Ab3dE5gH7j"  # what the VPS's mktemp answers


def _install(dest_quoted):
    """The one command that installs the stage; ``dest_quoted`` as shlex.quote renders it."""
    return (
        f"sudo chown root:root {STAGE} && sudo chmod 644 {STAGE} && sudo mv {STAGE} {dest_quoted}"
    )


class _Remote:
    """A fake ssh/scp pair that logs every call and fails on demand."""

    def __init__(self, *, mktemp=STAGE, fail_scp=None, fail_on=None):
        self.calls: list[tuple[str, str]] = []
        self.mktemp, self.fail_scp, self.fail_on = mktemp, fail_scp, fail_on

    def ssh(self, cmd, **_kw):
        self.calls.append(("ssh", cmd))
        if cmd.startswith("mktemp"):
            return self.mktemp
        if self.fail_on and self.fail_on in cmd:
            raise RuntimeError("ssh failed")
        return "missing" if "test -f" in cmd else ""

    def scp(self, local, remote, **_kw):
        self.calls.append(("scp", remote))
        if self.fail_scp:
            raise self.fail_scp

    def ssh_cmds(self):
        return [c for kind, c in self.calls if kind == "ssh"]


def test_the_helper_stages_in_mktemp_and_sets_owner_and_mode_before_the_move(tmp_path):
    r = _Remote()
    ssh.install_world_readable(r.ssh, r.scp, str(tmp_path / "f"), "/opt/x/conf.yml")
    assert r.calls == [
        ("ssh", "mktemp /tmp/fabrik-XXXXXXXXXX"),
        ("scp", STAGE),
        ("ssh", _install("/opt/x/conf.yml")),
    ], "a successful install leaves nothing to remove"


def test_the_helper_quotes_the_destination_for_the_shell(tmp_path):
    r = _Remote()
    ssh.install_world_readable(r.ssh, r.scp, str(tmp_path / "f"), "/opt/x/my conf;id.yml")
    assert r.ssh_cmds()[-1] == _install("'/opt/x/my conf;id.yml'")


@pytest.mark.parametrize(
    "remote",
    [
        _Remote(fail_scp=RuntimeError("scp failed")),
        _Remote(fail_scp=KeyboardInterrupt()),
        _Remote(fail_on="sudo mv"),
    ],
    ids=["scp-fails", "scp-interrupted", "move-fails"],
)
def test_the_helper_removes_the_stage_on_every_failure(remote, tmp_path):
    with pytest.raises((RuntimeError, KeyboardInterrupt)):
        ssh.install_world_readable(remote.ssh, remote.scp, str(tmp_path / "f"), "/opt/x/conf.yml")
    assert remote.ssh_cmds()[-1] == f"sudo rm -f {STAGE}"


def test_a_cleanup_failure_never_masks_the_original_error(tmp_path):
    r = _Remote(fail_scp=RuntimeError("scp failed"), fail_on="rm -f")
    with pytest.raises(RuntimeError, match="scp failed"):
        ssh.install_world_readable(r.ssh, r.scp, str(tmp_path / "f"), "/opt/x/conf.yml")


def test_a_bad_mktemp_answer_refuses_before_anything_is_copied(tmp_path):
    r = _Remote(mktemp="/tmp/prometheus.yml.staged")
    with pytest.raises(RuntimeError, match="unexpected path"):
        ssh.install_world_readable(r.ssh, r.scp, str(tmp_path / "f"), "/opt/x/conf.yml")
    assert not any(kind == "scp" for kind, _ in r.calls)


DRIVERS = {
    "gatus.add_endpoint": (
        gatus,
        lambda: gatus.add_endpoint("my-proj", "my-proj.vps1.ocoron.com"),
        gatus.GATUS_CONFIG_DIR + "/my-proj.yaml",
    ),
    "gatus.add_aro_wake_endpoint": (
        gatus,
        lambda: gatus.add_aro_wake_endpoint("vps4", "10.99.0.4"),
        gatus.GATUS_CONFIG_DIR + "/aro-wake-vps4.yaml",
    ),
    "prometheus._write_config": (
        prometheus,
        lambda: prometheus._write_config({"scrape_configs": []}),
        prometheus.PROMETHEUS_CONFIG_PATH,
    ),
    "redis._write_registry": (
        redis,
        lambda: redis._write_registry({"authelia": 3}),
        redis.REDIS_REGISTRY_PATH,
    ),
}


@pytest.mark.parametrize("name", sorted(DRIVERS))
def test_each_monitoring_driver_stages_through_mktemp(name, monkeypatch, tmp_path):
    module, call, dest = DRIVERS[name]
    r = _Remote()
    monkeypatch.setattr(module, "ssh", r.ssh)
    monkeypatch.setattr(module, "scp_to_vps", r.scp)
    if module is prometheus:
        monkeypatch.setattr(
            prometheus, "_LOCAL_PROMETHEUS_CONFIG_PATH", tmp_path / "prometheus.yml"
        )
    call()
    assert [remote for kind, remote in r.calls if kind == "scp"] == [STAGE]
    assert [c for c in r.ssh_cmds() if "sudo mv" in c] == [_install(dest)]
