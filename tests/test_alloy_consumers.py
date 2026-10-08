"""Every repo consumer of the log shipper names Alloy's container, port and metrics.

Plan: docs/development/plans/2026-10-08-plan-1-promtail-to-alloy/T04b-repo-consumers.md
(spec docs/superpowers/specs/2026-10-05-promtail-to-alloy-design.md § The delta › D3, D4, D6).

The four Behavior Contract rows:
1. the observability audit's ALLOY block greps only metric names that a live Alloy
   actually exports once it has pushed to Loki (scripts/audit/05-observability.sh), and
   fails closed (an explicit marker line) on an unreachable Alloy or a cold start.
2. PORTS.md lists 12345 for alloy and marks 9080 promtail rollback-only.
3. vps_sync.py's two classification sets both contain "alloy" and still contain "promtail".
4. the repo consumers named in the spec no longer present Promtail as the running shipper,
   outside the rollback-profile references (the classification sets and the backup path).

Round-1 review fixups (O1-O5, O8) folded in: the audit's docker-network helper was still
named for the retired `coolify` network (O2); the ALLOY block was fail-open on an
unreachable Alloy or a cold start (O1); a proactive-check.sh comment claimed Alloy "now
writes" the legacy `promtail-positions` volume, when D4 says Alloy only READS it once at
the hand-over and keeps its own positions under the `alloy-data` volume (O3); another
comment wrongly carried the SPOKE's `network_mode: host` onto the HUB's alloy, which runs
on the `fabrik` network with no host port (D3, spec:256) (O4); the metric-name check was a
subset check that would stay green if an audited metric were silently dropped (O5); and the
row-4 consumer checks only asserted the new phrase was present, never that no "Promtail is
the running shipper" phrasing survived (O8).

Metric-name measurement (recorded 2026-10-08; re-run live by
test_live_alloy_exposes_every_audited_metric_name below, skipped when docker is absent)::

    docker network create fabrik-t04b-probe-net
    docker run -d --name fabrik-t04b-probe-loki --network fabrik-t04b-probe-net \\
      --network-alias probe-loki grafana/loki:3.4.2

    # config.alloy (scratch dir outside the repo — the hub's real
    # configs/alloy/config.alloy is T01's, not in this tree):
    #   local.file_match "probe" { path_targets = [{"__path__" = "/probe/test.log"}] }
    #   loki.source.file "probe" {
    #     targets = local.file_match.probe.targets
    #     forward_to = [loki.write.probe.receiver]
    #   }
    #   loki.write "probe" { endpoint { url = "http://probe-loki:3100/loki/api/v1/push" } }

    docker run -d --name fabrik-t04b-probe-alloy --network fabrik-t04b-probe-net \\
      -v "$PWD/config.alloy:/etc/alloy/config.alloy:ro" \\
      -v "$PWD/logdir:/probe:ro" -p 0:12345 grafana/alloy:v1.20.1 \\
      run /etc/alloy/config.alloy --server.http.listen-addr=0.0.0.0:12345

    # waited (bounded 60s) for loki_write_sent_entries_total to appear at
    # http://127.0.0.1:<published-port>/metrics — the `loki_source_file_*` family
    # appeared immediately (tailing started on the pre-existing line), the
    # `loki_write_*` family only after the first push to the throwaway Loki,
    # confirming spec ledger cv-04 (write family absent on a cold start).

    docker rm -f fabrik-t04b-probe-alloy fabrik-t04b-probe-loki
    docker network rm fabrik-t04b-probe-net

Names actually observed on that live Alloy's :12345/metrics (full set; the audit greps a
subset — the three with a direct Promtail analogue; there is no Alloy equivalent of
`promtail_targets_active_total`, so it is dropped rather than grepped for a name that
never exists):
    loki_experimental_features_in_use_total, loki_source_file_file_bytes_total,
    loki_source_file_files_active_total, loki_source_file_read_bytes_total,
    loki_source_file_read_lines_total, loki_write_batch_retries_total,
    loki_write_batch_size_bytes_{bucket,count,sum}, loki_write_dropped_bytes_total,
    loki_write_dropped_entries_total, loki_write_entry_propagation_latency_seconds_*,
    loki_write_request_duration_seconds_*, loki_write_request_size_bytes_*,
    loki_write_sent_bytes_total, loki_write_sent_entries_total.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

# Recorded from the live measurement above — the fixture the audit's grep pattern is
# checked against (the metric-name Behavior Contract row). O5: this must equal the set
# of names the audit greps for, not merely contain it — dropping an audited metric
# (or silently widening the grep) is a defect either direction.
MEASURED_ALLOY_METRIC_NAMES = frozenset(
    {
        "loki_write_sent_entries_total",
        "loki_write_dropped_entries_total",
        "loki_source_file_files_active_total",
    }
)


def _read(relpath: str) -> str:
    return (REPO_ROOT / relpath).read_text()


def _alloy_grep_names(script: str) -> list[str]:
    match = re.search(r'echo "\$_alloy_metrics" \| grep -E "([^"]+)"', script)
    assert match, "no ALLOY block grep -E pattern found in 05-observability.sh"
    return match.group(1).split("|")


def _alloy_block(script: str) -> str:
    """The ALLOY section's body (O1 fixups), isolated so its fail-closed logic can be
    run standalone against fixture `fabrik_curl` output."""
    start_anchor = 'echo "========== ALLOY =========="\n'
    end_anchor = '\necho ""\necho "========== GRAFANA =========="'
    start = script.index(start_anchor) + len(start_anchor)
    end = script.index(end_anchor, start)
    return script[start:end]


def _run_alloy_block(fixture_metrics: str) -> str:
    """Executes the live ALLOY block (verbatim from the script) with `fabrik_curl`
    stubbed to return `fixture_metrics`, and returns its captured stdout."""
    block = _alloy_block(_read("scripts/audit/05-observability.sh"))
    wrapper = (
        "set -uo pipefail\n"
        "fabrik_curl() { printf '%s' \"$FIXTURE_METRICS\"; }\n"
        + block
    )
    env = dict(os.environ)
    env["FIXTURE_METRICS"] = fixture_metrics
    result = subprocess.run(
        ["bash", "-c", wrapper],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
        env=env,
    )
    return result.stdout


def _braced_string_set(text: str, var_name: str) -> set[str]:
    match = re.search(rf"{var_name}\s*=\s*\{{([^}}]*)\}}", text, re.S)
    assert match, f"{var_name!r} set literal not found"
    return set(re.findall(r'"([^"]+)"', match.group(1)))


# ---------------------------------------------------------------------------
# Row 1 — the observability audit's ALLOY block
# ---------------------------------------------------------------------------


def test_observability_audit_greps_exactly_the_measured_alloy_metric_names() -> None:
    # O5: equality, not subset — dropping an audited metric must fail this.
    script = _read("scripts/audit/05-observability.sh")
    assert "========== ALLOY ==========" in script
    assert "========== PROMTAIL ==========" not in script
    names = _alloy_grep_names(script)
    assert names, "the ALLOY block's grep pattern is empty"
    assert set(names) == MEASURED_ALLOY_METRIC_NAMES


def test_observability_audit_container_health_list_names_alloy_not_promtail() -> None:
    script = _read("scripts/audit/05-observability.sh")
    loop_line = next(line for line in script.splitlines() if line.startswith("for name in"))
    assert "alloy" in loop_line
    assert "promtail" not in loop_line


def test_observability_audit_uses_fabrik_network_not_coolify() -> None:
    # O2: `coolify` was renamed to `fabrik` 2026-05-31 (infra/vps1/monitoring/compose.yaml:244-246;
    # scripts/sysadmin/test_claude_run.py:223 bans the stale name for the same reason) — a
    # `--network coolify` docker run fails silently (2>/dev/null) and every fabrik_curl call
    # in this script would print nothing, reading as a clean audit.
    script = _read("scripts/audit/05-observability.sh")
    assert "--network coolify" not in script, "05-observability.sh uses the removed 'coolify' network"
    assert "--network fabrik" in script
    assert "coolify_curl" not in script
    assert "fabrik_curl" in script


def test_alloy_block_fails_closed_when_alloy_is_unreachable() -> None:
    # O1 fixture 1/3: an unreachable Alloy / missing container — fabrik_curl returns empty.
    out = _run_alloy_block("")
    assert "FAILED: alloy metrics unreachable on alloy:12345" in out
    assert "WARNING" not in out
    assert "loki_write_sent_entries_total" not in out


def test_alloy_block_warns_on_a_cold_start_with_no_write_metrics() -> None:
    # O1 fixture 2/3: Alloy is up and tailing, but has not pushed to Loki yet — no
    # loki_write_* series exists, which a bare grep silently drops.
    fixture = "loki_source_file_files_active_total 1\n"
    out = _run_alloy_block(fixture)
    assert "FAILED" not in out
    assert "loki_source_file_files_active_total 1" in out
    assert "WARNING: alloy has not pushed to Loki yet (no loki_write_* series)" in out


def test_alloy_block_prints_metrics_cleanly_once_a_push_landed() -> None:
    # O1 fixture 3/3: the full, healthy case — no FAILED/WARNING marker, every grepped
    # metric line present.
    fixture = (
        "loki_write_sent_entries_total 3\n"
        "loki_write_dropped_entries_total 0\n"
        "loki_source_file_files_active_total 1\n"
    )
    out = _run_alloy_block(fixture)
    assert "FAILED" not in out
    assert "WARNING" not in out
    assert "loki_write_sent_entries_total 3" in out
    assert "loki_write_dropped_entries_total 0" in out
    assert "loki_source_file_files_active_total 1" in out


@pytest.mark.skipif(shutil.which("docker") is None, reason="docker is not installed")
def test_live_alloy_exposes_every_audited_metric_name(tmp_path: Path) -> None:
    """Reproduces the metric-name measurement live: builds a minimal Alloy pipeline
    (local.file_match -> loki.source.file -> loki.write) against a throwaway Loki on a
    private docker network, waits (bounded 60s) for loki_write_sent_entries_total, then
    asserts every name the audit greps for is actually present. Never touches any
    existing container/volume/network — only named, removed-in-finally ones."""
    probe = subprocess.run(
        ["docker", "info"], capture_output=True, text=True, timeout=10, check=False
    )
    if probe.returncode != 0:
        pytest.skip("docker daemon is not reachable")

    names = _alloy_grep_names(_read("scripts/audit/05-observability.sh"))

    tag = uuid.uuid4().hex[:8]
    net = f"fabrik-t04b-test-net-{tag}"
    loki_name = f"fabrik-t04b-test-loki-{tag}"
    alloy_name = f"fabrik-t04b-test-alloy-{tag}"

    logdir = tmp_path / "logdir"
    logdir.mkdir()
    (logdir / "test.log").write_text("probe line\n")
    config = tmp_path / "config.alloy"
    config.write_text(
        'local.file_match "probe" {\n'
        '\tpath_targets = [{"__path__" = "/probe/test.log"}]\n'
        "}\n\n"
        'loki.source.file "probe" {\n'
        "\ttargets    = local.file_match.probe.targets\n"
        "\tforward_to = [loki.write.probe.receiver]\n"
        "}\n\n"
        'loki.write "probe" {\n'
        "\tendpoint {\n"
        '\t\turl = "http://probe-loki:3100/loki/api/v1/push"\n'
        "\t}\n"
        "}\n"
    )

    def _docker(*args: str, timeout: int = 60) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["docker", *args], capture_output=True, text=True, timeout=timeout, check=False
        )

    try:
        created = _docker("network", "create", net)
        if created.returncode != 0:
            pytest.skip(f"could not create a throwaway docker network: {created.stderr}")

        loki_up = _docker(
            "run",
            "-d",
            "--name",
            loki_name,
            "--network",
            net,
            "--network-alias",
            "probe-loki",
            "grafana/loki:3.4.2",
        )
        if loki_up.returncode != 0:
            pytest.skip(f"could not run a throwaway grafana/loki:3.4.2: {loki_up.stderr}")

        alloy_up = _docker(
            "run",
            "-d",
            "--name",
            alloy_name,
            "--network",
            net,
            "-v",
            f"{config}:/etc/alloy/config.alloy:ro",
            "-v",
            f"{logdir}:/probe:ro",
            "-p",
            "0:12345",
            "grafana/alloy:v1.20.1",
            "run",
            "/etc/alloy/config.alloy",
            "--server.http.listen-addr=0.0.0.0:12345",
        )
        if alloy_up.returncode != 0:
            pytest.skip(f"could not run a throwaway grafana/alloy:v1.20.1: {alloy_up.stderr}")

        port_lines = _docker("port", alloy_name, "12345/tcp").stdout.strip().splitlines()
        assert port_lines, "alloy container published no mapping for 12345/tcp"
        port = port_lines[0].rsplit(":", 1)[1]

        deadline = time.monotonic() + 60
        metrics_text = ""
        while time.monotonic() < deadline:
            try:
                with urllib.request.urlopen(
                    f"http://127.0.0.1:{port}/metrics", timeout=5
                ) as resp:
                    metrics_text = resp.read().decode()
            except (OSError, urllib.error.URLError):
                metrics_text = ""
            if "loki_write_sent_entries_total" in metrics_text:
                break
            time.sleep(2)
        else:
            pytest.fail("loki_write_sent_entries_total never appeared within 60s")

        for name in names:
            assert re.search(rf"^{re.escape(name)}(\{{|\s)", metrics_text, re.M), (
                f"{name!r} absent from the live Alloy /metrics output"
            )
    finally:
        _docker("rm", "-f", alloy_name)
        _docker("rm", "-f", loki_name)
        _docker("network", "rm", net)


# ---------------------------------------------------------------------------
# Row 2 — PORTS.md
# ---------------------------------------------------------------------------


def test_ports_md_lists_alloy_and_marks_promtail_rollback_only() -> None:
    lines = _read("PORTS.md").splitlines()
    alloy_row = next(line for line in lines if re.search(r"\|\s*12345\s*\|", line))
    assert "alloy" in alloy_row
    promtail_row = next(line for line in lines if re.search(r"\|\s*9080\s*\|", line))
    assert "promtail" in promtail_row
    assert "rollback-only" in promtail_row
    assert "Gate S" in promtail_row


# ---------------------------------------------------------------------------
# Row 3 — vps_sync.py classification sets
# ---------------------------------------------------------------------------


def test_vps_sync_classification_sets_contain_alloy_and_promtail() -> None:
    text = _read("scripts/vps_sync.py")
    monitoring_patterns = _braced_string_set(text, "monitoring_patterns")
    required = _braced_string_set(text, "required")
    for classification_set in (monitoring_patterns, required):
        assert "alloy" in classification_set
        assert "promtail" in classification_set


# ---------------------------------------------------------------------------
# Row 4 — the other repo consumers never present Promtail as the running shipper
# ---------------------------------------------------------------------------


def test_06_backup_adds_alloy_config_path_beside_promtail() -> None:
    text = _read("scripts/audit/06-backup.sh")
    assert "/opt/monitoring/configs/alloy/config.alloy" in text
    # rollback profile still needs the promtail path backed up until Gate S
    assert "/opt/monitoring/configs/promtail/promtail-config.yaml" in text


def test_generate_vps_inventory_names_alloy_as_the_shipper() -> None:
    text = _read("scripts/generate_vps_inventory.py")
    assert '"alloy": "Log shipper' in text
    assert "receives from Alloy" in text
    # O8: no phrasing may present Promtail as the running shipper any more
    assert "receives from Promtail" not in text
    assert "promtail ships" not in text.lower()


def test_proactive_check_comments_name_alloy_not_promtail() -> None:
    text = _read("scripts/sysadmin/proactive-check.sh")
    assert "cadvisor + alloy" in text
    assert "Loki receiving no lines = Alloy or pipeline broken" in text
    # O4: the hub's alloy runs on the `fabrik` network with no host port (spec D3,
    # spec:256) — it never carries the SPOKE's `network_mode: host`.
    assert "the hub's alloy runs on" in text
    assert "no host port and has no curl" in text
    assert "network_mode: host and has no curl" not in text
    # O3: Alloy only READS the rollback-profile `promtail-positions` volume once, at the
    # hand-over (D4) — it never writes into it; its own positions live under `alloy-data`.
    assert "read once by Alloy at the hand-over" in text
    assert "alloy-data" in text
    assert "now written by Alloy" not in text
    # O8: no phrasing may present Promtail as the running shipper any more
    assert "receives from Promtail" not in text
    assert "promtail ships" not in text.lower()


def test_system_prompt_monitoring_list_names_alloy_not_promtail() -> None:
    text = _read("scripts/sysadmin/system-prompt.txt")
    monitoring_line = next(
        line for line in text.splitlines() if line.strip().startswith("2. MONITORING")
    )
    assert "alloy" in monitoring_line
    assert "promtail" not in monitoring_line


def test_bootstrap_hub_comments_name_alloy_not_promtail() -> None:
    text = _read("scripts/bootstrap/bootstrap-hub.sh")
    assert "container tag for alloy" in text
    assert "log rotation + alloy tag" in text
    assert "promtail" not in text.lower()


def test_compose_template_names_alloy_not_promtail() -> None:
    text = _read("templates/file-worker/compose.yaml.j2")
    assert "Alloy -> Loki" in text
    assert "Promtail" not in text
