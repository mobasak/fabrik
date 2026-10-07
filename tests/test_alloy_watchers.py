"""T04a — the Prometheus `alloy` job and the Gatus `alloy` endpoint replace the Promtail ones.

Behavior Contract (docs/development/plans/2026-10-08-plan-1-promtail-to-alloy/T04a-watchers.md):
- `configs/prometheus/prometheus.yml` has a job `alloy` scraping exactly `alloy:12345`,
  `10.99.0.2:12345` and `10.99.0.3:12345` (spec § The delta › D3), with no `promtail-spokes` job.
- `configs/gatus/apps/observability-agents.yaml` has an endpoint `alloy` checking
  `http://alloy:12345/-/ready` with the old interval and failure threshold, with no `promtail`
  endpoint.
"""

from __future__ import annotations

from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
PROMETHEUS_YML = REPO / "configs" / "prometheus" / "prometheus.yml"
GATUS_OBSERVABILITY_AGENTS = REPO / "configs" / "gatus" / "apps" / "observability-agents.yaml"


def _scrape_jobs() -> dict:
    config = yaml.safe_load(PROMETHEUS_YML.read_text())
    return {job["job_name"]: job for job in config["scrape_configs"]}


def _gatus_endpoints() -> dict:
    config = yaml.safe_load(GATUS_OBSERVABILITY_AGENTS.read_text())
    return {endpoint["name"]: endpoint for endpoint in config["endpoints"]}


def _targets_with_labels(job: dict) -> list[tuple[tuple[str, ...], dict]]:
    """Flatten a job's static_configs into (targets, labels) pairs, labels defaulted to {}."""
    return [
        (tuple(sc["targets"]), sc.get("labels", {}))
        for sc in job["static_configs"]
    ]


class TestPrometheusAlloyJob:
    def test_no_promtail_spokes_job_remains(self):
        jobs = _scrape_jobs()
        assert "promtail-spokes" not in jobs, jobs.keys()

    def test_alloy_job_scrapes_exactly_the_three_targets(self):
        jobs = _scrape_jobs()
        assert "alloy" in jobs, jobs.keys()
        all_targets: set[str] = set()
        for targets, _labels in _targets_with_labels(jobs["alloy"]):
            all_targets.update(targets)
        assert all_targets == {"alloy:12345", "10.99.0.2:12345", "10.99.0.3:12345"}

    def test_spoke_targets_keep_their_old_host_and_role_labels(self):
        jobs = _scrape_jobs()
        by_target: dict[str, dict] = {}
        for targets, labels in _targets_with_labels(jobs["alloy"]):
            for t in targets:
                by_target[t] = labels
        assert by_target["10.99.0.2:12345"] == {"host": "vps2", "role": "spoke"}
        assert by_target["10.99.0.3:12345"] == {"host": "vps3", "role": "spoke"}

    def test_hub_target_carries_host_vps1_and_the_hub_role_label(self):
        jobs = _scrape_jobs()
        by_target: dict[str, dict] = {}
        for targets, labels in _targets_with_labels(jobs["alloy"]):
            for t in targets:
                by_target[t] = labels
        # role value matches the hub's other targets in this same file (e.g. job `aro-wake`,
        # prometheus.yml:28, and job `cadvisor`, prometheus.yml:45 — both label the hub `role: hub`).
        assert by_target["alloy:12345"] == {"host": "vps1", "role": "hub"}


class TestGatusAlloyEndpoint:
    def test_no_promtail_endpoint_remains(self):
        endpoints = _gatus_endpoints()
        assert "promtail" not in endpoints, endpoints.keys()

    def test_alloy_endpoint_checks_the_alloy_ready_url(self):
        endpoints = _gatus_endpoints()
        assert "alloy" in endpoints, endpoints.keys()
        assert endpoints["alloy"]["url"] == "http://alloy:12345/-/ready"

    def test_alloy_endpoint_keeps_the_old_interval_and_failure_threshold(self):
        endpoints = _gatus_endpoints()
        endpoint = endpoints["alloy"]
        assert endpoint["interval"] == "60s"
        assert endpoint["alerts"][0]["failure-threshold"] == 3
