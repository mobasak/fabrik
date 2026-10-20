"""The Prometheus hot-reload must not depend on another container resolving `prometheus`.

Probed live 2026-10-02 (plan-2 rollout R0): `docker exec alertmanager wget http://prometheus:9090/-/reload`
answered `wget: bad address 'prometheus:9090'`, so scripts/sync_prometheus_to_vps.sh always reported a failed
reload and drivers/prometheus._reload_prometheus always fell back to a full container RESTART on every
`fabrik apply` that touched scrape targets. The reload now runs inside the prometheus container against
localhost (W-a1a359c8).

Both halves are tested by EXECUTING the remote shell command the code builds, under bash, with stub `sudo` and
`docker` binaries that model vps1: `docker ps` lists the configured containers; `docker exec <c> wget <url>`
succeeds only for c == "prometheus" and a localhost:9090 URL (anything else is the `bad address` failure, and an
empty or unknown container name is docker's "No such container"); `docker restart <c>` succeeds only for a
running container. Every docker call is logged, so a test can assert what never ran. `CONFIG_VALID=0` models a
written config Prometheus will not load: `/-/reload` answers HTTP 500 and `promtool check config` fails
(W-5aa5e3d8: restarting into that config takes Prometheus down instead of keeping the last good one).
"""

from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path

import pytest

from fabrik.drivers import prometheus as prom

REPO = Path(__file__).resolve().parents[1]

_DOCKER = r"""#!/bin/bash
printf '%s\n' "$*" >> "$DOCKER_LOG"
case "$1" in
  ps) for c in $CONTAINERS; do echo "$c"; done ;;
  exec)
    c="$2"
    if [[ -z "$c" ]] || [[ " $CONTAINERS " != *" $c "* ]]; then echo "No such container: '$c'" >&2; exit 1; fi
    if [[ "${EXEC_BROKEN:-0}" == 1 ]]; then echo "Error response from daemon: container $c is not running" >&2; exit 1; fi
    if [[ "$*" == *"promtool check config /etc/prometheus/prometheus.yml"* ]]; then
      if [[ "${CONFIG_VALID:-1}" == 0 ]]; then echo "FAILED: parsing YAML file /etc/prometheus/prometheus.yml" >&2; exit 1; fi
      echo "SUCCESS: /etc/prometheus/prometheus.yml is valid prometheus config file syntax"; exit 0
    fi
    if [[ "$c" == prometheus ]] && [[ "$*" == *"http://localhost:9090/-/reload"* ]]; then
      if [[ "${CONFIG_VALID:-1}" == 0 ]]; then echo "wget: server returned error: HTTP/1.1 500 Internal Server Error" >&2; exit 1; fi
      exit 0
    fi
    echo "wget: bad address 'prometheus:9090'" >&2; exit 1 ;;
  restart)
    c="$2"
    if [[ -n "$c" ]] && [[ " $CONTAINERS " == *" $c "* ]]; then echo "$c"; exit 0; fi
    echo "No such container: '$c'" >&2; exit 1 ;;
esac
exit 0
"""


def _vps1(tmp_path: Path, containers: str) -> tuple[dict, Path]:
    """A bin dir with stub sudo + docker modelling vps1, and the env that puts it first on PATH."""
    bindir = tmp_path / "vps1bin"
    bindir.mkdir(exist_ok=True)
    (bindir / "sudo").write_text('#!/bin/bash\nexec "$@"\n')
    (bindir / "docker").write_text(_DOCKER)
    for f in ("sudo", "docker"):
        (bindir / f).chmod(0o755)
    log = tmp_path / "docker.log"
    log.write_text("")
    env = {
        **os.environ,
        "PATH": f"{bindir}:{os.environ['PATH']}",
        "CONTAINERS": containers,
        "DOCKER_LOG": str(log),
    }
    return env, log


def _remote(cmd: str, env: dict) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", "-c", cmd], capture_output=True, text=True, env=env, timeout=30, check=False
    )


class TestDriverReload:
    def _reload(
        self, monkeypatch, tmp_path, containers: str, config_valid: str = "1"
    ) -> tuple[bool, list[str], str]:
        env, log = _vps1(tmp_path, containers)
        env["CONFIG_VALID"] = config_valid
        sent: list[str] = []

        def fake_ssh(cmd, *, timeout=60, **_kw):
            sent.append(cmd)
            r = _remote(cmd, env)
            if r.returncode != 0:
                raise RuntimeError(f"rc={r.returncode}: {r.stderr.strip()}")
            return r.stdout.strip()

        monkeypatch.setattr(prom, "ssh", fake_ssh)
        return prom._reload_prometheus(), sent, log.read_text()

    def test_hot_reload_runs_inside_prometheus_and_never_restarts(self, monkeypatch, tmp_path):
        ok, sent, docker = self._reload(
            monkeypatch, tmp_path, "alertmanager prometheus pushgateway"
        )
        assert ok is True
        assert len(sent) == 1, sent
        assert "exec prometheus wget" in docker
        assert "restart" not in docker

    def test_no_prometheus_container_runs_nothing_and_reports_failure(
        self, monkeypatch, tmp_path, caplog
    ):
        caplog.set_level(logging.INFO, logger=prom.__name__)
        ok, sent, docker = self._reload(monkeypatch, tmp_path, "alertmanager pushgateway")
        assert ok is False
        # the logged reason NAMES the cause (a bare `[ -n ]` left it as `rc=1: `, restart-S2)
        warning = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
        assert len(warning) == 1 and "no running prometheus container" in warning[0]
        assert len(sent) == 2  # hot-reload, then the restart fallback
        assert (
            "exec" not in docker and "restart" not in docker
        )  # an empty name never reaches docker

    def test_failed_hot_reload_falls_back_to_restarting_prometheus(self, monkeypatch, tmp_path):
        env, log = _vps1(tmp_path, "alertmanager prometheus")

        def fake_ssh(cmd, *, timeout=60, **_kw):
            if "wget" in cmd:
                raise RuntimeError("rc=1: reload refused")
            r = _remote(cmd, env)
            if r.returncode != 0:
                raise RuntimeError(r.stderr)
            return r.stdout

        monkeypatch.setattr(prom, "ssh", fake_ssh)
        assert prom._reload_prometheus() is True
        docker = log.read_text()
        assert "restart prometheus" in docker
        # the config was validated before the restart, never after
        assert docker.index("promtool check config") < docker.index("restart prometheus")

    def test_invalid_config_is_never_restarted_into(self, monkeypatch, tmp_path, caplog):
        """/-/reload refuses an invalid config and the running Prometheus keeps its last good one;
        a restart would drop it and crash-loop on the bad file (W-5aa5e3d8)."""
        ok, sent, docker = self._reload(
            monkeypatch, tmp_path, "alertmanager prometheus", config_valid="0"
        )
        assert ok is False
        assert len(sent) == 2  # hot-reload refused, then the guarded restart leg
        assert "promtool check config" in docker
        assert "restart" not in docker
        warning = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
        assert len(warning) == 1 and "FAILED: parsing YAML" in warning[0]
        assert "no running prometheus container" not in warning[0]


class TestReloadOutcome:
    """W-cc9b0532: the outcome names WHICH failure — promtool refusing the on-disk config (it is invalid;
    the next restart crash-loops Prometheus) is told apart from Prometheus being unavailable."""

    def _outcome(
        self,
        monkeypatch,
        tmp_path,
        containers: str,
        config_valid: str = "1",
        reload_ok=True,
        exec_broken: str = "0",
    ):
        env, log = _vps1(tmp_path, containers)
        env["CONFIG_VALID"] = config_valid
        env["EXEC_BROKEN"] = exec_broken

        def fake_ssh(cmd, *, timeout=60, **_kw):
            if "wget" in cmd and not reload_ok:
                raise RuntimeError("SSH to 'vps1' failed (rc=1): reload refused")
            r = _remote(cmd, env)
            if r.returncode != 0:
                raise RuntimeError(f"SSH to 'vps1' failed (rc={r.returncode}): {r.stderr.strip()}")
            return r.stdout.strip()

        monkeypatch.setattr(prom, "ssh", fake_ssh)
        return prom._reload_prometheus_outcome(), log.read_text()

    def test_a_hot_reload_is_reloaded(self, monkeypatch, tmp_path):
        out, _ = self._outcome(monkeypatch, tmp_path, "alertmanager prometheus")
        assert out == "reloaded"

    def test_a_refused_reload_with_a_valid_config_is_restarted(self, monkeypatch, tmp_path):
        out, docker = self._outcome(monkeypatch, tmp_path, "prometheus", reload_ok=False)
        assert out == "restarted" and "restart prometheus" in docker

    def test_an_invalid_config_is_refused_and_never_restarted_into(self, monkeypatch, tmp_path):
        out, docker = self._outcome(monkeypatch, tmp_path, "prometheus", config_valid="0")
        assert out == "refused" and "restart" not in docker

    def test_no_prometheus_container_is_unavailable_not_refused(self, monkeypatch, tmp_path):
        out, docker = self._outcome(monkeypatch, tmp_path, "alertmanager")
        assert out == "unavailable" and "exec" not in docker

    def test_a_docker_exec_failure_is_unavailable_not_refused(self, monkeypatch, tmp_path):
        """promtool, docker exec and the no-container guard all exit 1: only promtool's FAILED verdict
        may read as refused (review A-1) — a docker error never claims the config is invalid."""
        out, docker = self._outcome(
            monkeypatch, tmp_path, "prometheus", reload_ok=False, exec_broken="1"
        )
        assert out == "unavailable" and "restart" not in docker

    def test_rc3_inside_remote_stderr_is_not_refused(self, monkeypatch):
        """Only ssh's own `failed (rc=3)` reads as refused, never a number in the remote text (A-2)."""

        def fake_ssh(cmd, *, timeout=60, **_kw):
            raise RuntimeError("SSH to 'vps1' failed (rc=1): upstream said rc=3 earlier")

        monkeypatch.setattr(prom, "ssh", fake_ssh)
        assert prom._reload_prometheus_outcome() == "unavailable"

    def test_a_failing_restart_is_unavailable(self, monkeypatch, tmp_path):
        env, _ = _vps1(tmp_path, "prometheus")

        def fake_ssh(cmd, *, timeout=60, **_kw):
            if "wget" in cmd:
                raise RuntimeError("SSH to 'vps1' failed (rc=1): reload refused")
            raise RuntimeError("SSH to 'vps1' failed (rc=255): Connection refused")

        monkeypatch.setattr(prom, "ssh", fake_ssh)
        assert prom._reload_prometheus_outcome() == "unavailable"

    @pytest.mark.parametrize(
        ("outcome", "ok"),
        [("reloaded", True), ("restarted", True), ("refused", False), ("unavailable", False)],
    )
    def test_the_bool_wrapper_keeps_its_contract(self, monkeypatch, outcome, ok):
        monkeypatch.setattr(prom, "_reload_prometheus_outcome", lambda: outcome)
        assert prom._reload_prometheus() is ok


class TestSyncScriptReload:
    def _push(self, tmp_path: Path, containers: str) -> tuple[subprocess.CompletedProcess, str]:
        root = tmp_path / "root"
        (root / "configs" / "prometheus" / "rules").mkdir(parents=True)
        (root / "configs" / "prometheus" / "rules" / "x.yml").write_text("groups: []\n")
        env, log = _vps1(tmp_path, containers)
        bindir = tmp_path / "localbin"
        bindir.mkdir()
        # Local ssh: answer the bookkeeping commands, and EXECUTE the reload command under the vps1 model.
        (bindir / "ssh").write_text(
            "#!/bin/bash\n"
            'cmd="${@: -1}"\n'
            'case "$cmd" in\n'
            "  *mktemp*) echo /tmp/fake-prom ;;\n"
            "  *md5sum*) echo remote-md5 ;;\n"
            '  *"docker "*) exec bash -c "$cmd" ;;\n'
            "esac\n"
            "exit 0\n"
        )
        (bindir / "scp").write_text("#!/bin/bash\nexit 0\n")
        for f in ("ssh", "scp"):
            (bindir / f).chmod(0o755)
        env = {**env, "PATH": f"{bindir}:{env['PATH']}", "FABRIK_ROOT": str(root)}
        r = subprocess.run(
            ["bash", str(REPO / "scripts" / "sync_prometheus_to_vps.sh"), "--push"],
            capture_output=True,
            text=True,
            env=env,
            timeout=60,
            check=False,
        )
        return r, log.read_text()

    def test_push_reloads_inside_prometheus_and_reports_success(self, tmp_path):
        r, docker = self._push(tmp_path, "alertmanager prometheus pushgateway")
        assert r.returncode == 0, r.stdout + r.stderr
        assert "prometheus reloaded" in r.stdout
        assert "exec prometheus wget" in docker
        assert "alertmanager" not in docker.replace("ps --format", "")

    def test_push_without_a_prometheus_container_warns_and_execs_nothing(self, tmp_path):
        r, docker = self._push(tmp_path, "alertmanager pushgateway")
        assert r.returncode == 1
        assert "WARN: prometheus reload returned non-zero" in r.stdout
        assert "exec" not in docker
