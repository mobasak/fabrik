"""The container memory alerts judge the working set, per host (W-4801e4c3).

ContainerHighMemory divided `container_memory_usage_bytes` (page cache included) by the limit, so it
fired on Prometheus while its working set stayed well under 85% of the limit. ContainerMemoryHighOfHost divided by
`on() group_left() node_memory_MemTotal_bytes`, which errors once more than one host reports it, so it
never fired. The promtool fixture tests/fixtures/alerts-memory-rules-test.yml runs under the Prometheus
image the vps1 monitoring mirror names, as tests/test_registry_reconcile.py does for the drift rules.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parent.parent


def _rules() -> dict[str, dict]:
    doc = yaml.safe_load((REPO / "configs/prometheus/rules/alerts.yml").read_text())
    return {r["alert"]: r for g in doc["groups"] for r in g["rules"] if "alert" in r}


def _vps1_prometheus_image() -> str:
    compose = yaml.safe_load((REPO / "infra/vps1/monitoring/compose.yaml").read_text())
    return compose["services"]["prometheus"]["image"]


def test_memory_rules_read_the_working_set_per_host():
    rules = _rules()
    high = " ".join(rules["ContainerHighMemory"]["expr"].split())
    host = " ".join(rules["ContainerMemoryHighOfHost"]["expr"].split())
    for expr in (high, host):
        assert "container_memory_working_set_bytes" in expr, expr
        assert "container_memory_usage_bytes" not in expr, expr
    assert "/ on(instance) group_left() machine_memory_bytes" in host, host
    assert "on() group_left()" not in host, host
    assert "unless on(instance, name) (container_spec_memory_limit_bytes" in host, host


def test_promtool_fixture_names_both_rules():
    fixture = yaml.safe_load((REPO / "tests/fixtures/alerts-memory-rules-test.yml").read_text())
    names = {t["alertname"] for case in fixture["tests"] for t in case["alert_rule_test"]}
    assert names == {"ContainerHighMemory", "ContainerMemoryHighOfHost"}


@pytest.mark.skipif(
    shutil.which("docker") is None, reason="promtool runs from the docker image vps1 runs"
)
def test_promtool_memory_rule_unit_tests_pass():
    r = subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "-v",
            f"{REPO}/configs/prometheus/rules:/r:ro",
            "-v",
            f"{REPO}/tests/fixtures:/t:ro",
            "--entrypoint",
            "promtool",
            _vps1_prometheus_image(),
            "test",
            "rules",
            "/t/alerts-memory-rules-test.yml",
        ],
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    assert r.returncode == 0, r.stdout + r.stderr
