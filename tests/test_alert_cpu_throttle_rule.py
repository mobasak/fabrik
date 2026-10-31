"""ContainerCPUThrottled watches the cost of vps1's CPU caps (W-fc701b31, after D-1324 capped them).

Sustained CFS throttling above 25% of periods for 15 minutes, only while the container runs more than
one period per second — measured on 7 days of vps1 data (2026-10-29): 0 fires with that floor, one
idle-container false fire without it. The promtool fixture tests/fixtures/alerts-cpu-throttle-rules-test.yml
pins the 16-minute edge, the floor, a 10-minute spike, a low-duty worker and a recreated container's
two ids, and runs under the Prometheus image the vps1 monitoring mirror names, as
tests/test_alert_memory_rules.py does for the memory rules.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parent.parent


def _rule() -> dict:
    doc = yaml.safe_load((REPO / "configs/prometheus/rules/alerts.yml").read_text())
    rules = [
        r for g in doc["groups"] for r in g["rules"] if r.get("alert") == "ContainerCPUThrottled"
    ]
    assert len(rules) == 1, f"expected one ContainerCPUThrottled rule, found {len(rules)}"
    return rules[0]


def test_the_throttle_rule_has_its_floor_and_window():
    """Given alerts.yml, when ContainerCPUThrottled is read, then it judges throttled/total periods
    above 0.25 behind the 1-period-per-second floor, for 15 minutes, as a warning (aro-wake only)."""
    rule = _rule()
    expr = " ".join(rule["expr"].split())
    assert (
        'rate(container_cpu_cfs_throttled_periods_total{name!=""}[5m]) '
        '/ rate(container_cpu_cfs_periods_total{name!=""}[5m]) > 0.25'
    ) in expr, expr
    assert '> 0.25 and rate(container_cpu_cfs_periods_total{name!=""}[5m]) > 1' in expr, expr
    assert " on(" not in expr, (
        "an on() division fails a recreated container's two ids; an on() `and` lets an idle id "
        "borrow a busy sibling's period rate"
    )
    assert rule["for"] == "15m"
    assert rule["labels"] == {"severity": "warning"}


def _vps1_prometheus_image() -> str:
    compose = yaml.safe_load((REPO / "infra/vps1/monitoring/compose.yaml").read_text())
    return compose["services"]["prometheus"]["image"]


@pytest.mark.skipif(
    shutil.which("docker") is None, reason="promtool runs from the docker image vps1 runs"
)
def test_promtool_cpu_throttle_rule_unit_tests_pass():
    """Given the fixture, when promtool runs it against alerts.yml, then every case holds."""
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
            "/t/alerts-cpu-throttle-rules-test.yml",
        ],
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    assert r.returncode == 0, r.stdout + r.stderr
