"""The Zitadel deploy spec serves what its Prometheus scrape job reads.

`specs/services/zitadel.yaml` registers a scrape of `/debug/metrics` (shape.exposes_metrics +
monitoring.metrics_path). Live, the endpoint answered Go's bare 404 (no exporter registered,
internal/api/api.go:378-383 at v4.17.1) while /debug/healthz answered 200; why is unverified.
Naming ZITADEL_INSTRUMENTATION_METRIC_EXPORTER_TYPE=prometheus registers it. The target was down
from 2026-08-29 (W-ef6ecf90).
"""

from __future__ import annotations

from pathlib import Path

import yaml

from fabrik.spec_loader import load_spec

SPEC = Path(__file__).resolve().parents[1] / "specs" / "services" / "zitadel.yaml"


def test_a_scraped_metrics_path_has_its_exporter_enabled() -> None:
    spec = load_spec(SPEC)
    raw = yaml.safe_load(SPEC.read_text())
    # the raw spec, not the loaded Shape: load_spec merges a template default that already says true
    assert raw["shape"]["exposes_metrics"] is True
    assert raw["monitoring"]["metrics_path"] == "/debug/metrics"
    assert spec.env.get("ZITADEL_INSTRUMENTATION_METRIC_EXPORTER_TYPE") == "prometheus"
