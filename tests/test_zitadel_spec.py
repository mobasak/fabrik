"""The Zitadel deploy spec serves what its Prometheus scrape job reads.

`specs/services/zitadel.yaml` registers a scrape of `/debug/metrics` (shape.exposes_metrics +
monitoring.metrics_path), but Zitadel v4.17.1 ships `Instrumentation.Metric.Exporter.Type: "none"`
(cmd/defaults.yaml), so the endpoint 404s unless the env enables a prometheus exporter. The
target was down — and its critical ServiceUnhealthy alert firing — for 31 days (W-ef6ecf90).
"""

from __future__ import annotations

from pathlib import Path

import yaml

from fabrik.spec_loader import load_spec

SPEC = Path(__file__).resolve().parents[1] / "specs" / "services" / "zitadel.yaml"


def test_a_scraped_metrics_path_has_its_exporter_enabled() -> None:
    spec = load_spec(SPEC)
    raw = yaml.safe_load(SPEC.read_text())
    assert spec.shape.exposes_metrics
    assert raw["monitoring"]["metrics_path"] == "/debug/metrics"
    assert spec.env.get("ZITADEL_INSTRUMENTATION_METRIC_EXPORTER_TYPE") == "prometheus"
