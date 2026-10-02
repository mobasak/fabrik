"""The Prometheus hot-reload must not depend on another container resolving `prometheus`.

Probed live 2026-10-02 (plan-2 rollout R0): `docker exec alertmanager wget http://prometheus:9090/-/reload`
answered `wget: bad address 'prometheus:9090'`, so scripts/sync_prometheus_to_vps.sh always reported a failed
reload and drivers/prometheus._reload_prometheus always fell back to a full container RESTART (a scrape gap) on
every `fabrik apply` that touched scrape targets. The reload now runs inside the prometheus container against
localhost (W-a1a359c8). Both tests model the live network: a reload sent from any other container, or to the
`prometheus` hostname, fails.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from fabrik.drivers import prometheus as prom

REPO = Path(__file__).resolve().parents[1]


def _reload_only_works_inside_prometheus(cmd: str) -> bool:
    """True when a docker-exec reload command would succeed on vps1's network as probed."""
    return (
        "docker exec" in cmd
        and "prometheus" in cmd.split("wget")[0]
        and "localhost:9090/-/reload" in cmd
    )


class TestDriverReload:
    def test_hot_reload_runs_inside_prometheus_and_never_restarts(self, monkeypatch):
        calls: list[str] = []

        def fake_ssh(cmd, *, timeout=60, **_kw):
            calls.append(cmd)
            if "restart" in cmd:
                return ""
            if not _reload_only_works_inside_prometheus(cmd) or "alertmanager" in cmd:
                raise RuntimeError("wget: bad address 'prometheus:9090'")
            return ""

        monkeypatch.setattr(prom, "ssh", fake_ssh)
        assert prom._reload_prometheus() is True
        assert len(calls) == 1, calls
        assert "restart" not in calls[0]


class TestSyncScriptReload:
    def _run(self, tmp_path: Path) -> subprocess.CompletedProcess:
        root = tmp_path / "root"
        (root / "configs" / "prometheus" / "rules").mkdir(parents=True)
        (root / "configs" / "prometheus" / "rules" / "x.yml").write_text("groups: []\n")
        bindir = tmp_path / "bin"
        bindir.mkdir()
        log = tmp_path / "ssh.log"
        # A remote `docker exec <c> wget <url>` succeeds only inside prometheus against localhost,
        # as probed on vps1; every other remote command is a no-op.
        (bindir / "ssh").write_text(
            "#!/bin/bash\n"
            f'cmd="${{@: -1}}"; printf "%s\\n" "$cmd" >> "{log}"\n'
            'case "$cmd" in\n'
            "  *mktemp*) echo /tmp/fake-prom ;;\n"
            "  *md5sum*) echo remote-md5 ;;\n"
            '  *"docker exec"*)\n'
            '    if [[ "$cmd" == *alertmanager* ]] || [[ "$cmd" != *localhost:9090/-/reload* ]]; then\n'
            '      [[ "$cmd" == *"&& echo OK || echo FAIL"* ]] && echo FAIL || exit 1\n'
            "    else\n"
            '      [[ "$cmd" == *"&& echo OK || echo FAIL"* ]] && echo OK\n'
            "    fi ;;\n"
            "esac\n"
            "exit 0\n"
        )
        (bindir / "scp").write_text("#!/bin/bash\nexit 0\n")
        for f in ("ssh", "scp"):
            (bindir / f).chmod(0o755)
        env = {**os.environ, "PATH": f"{bindir}:{os.environ['PATH']}", "FABRIK_ROOT": str(root)}
        return subprocess.run(
            ["bash", str(REPO / "scripts" / "sync_prometheus_to_vps.sh"), "--push"],
            capture_output=True,
            text=True,
            env=env,
            timeout=60,
            check=False,
        )

    def test_push_reloads_inside_prometheus_and_reports_success(self, tmp_path):
        r = self._run(tmp_path)
        assert r.returncode == 0, r.stdout + r.stderr
        assert "prometheus reloaded" in r.stdout
        log = (tmp_path / "ssh.log").read_text()
        assert "alertmanager" not in log
