"""Prometheus metrics for fabrik gpu rent — Phase 4.

Exposes counters/gauges that Grafana can chart for monthly cost rollup,
per-provider spend, orphan detection, and lifetime-exceeded alerts.

The metrics are exposed via a one-shot ``write_textfile()`` call that
dumps Prometheus text-format to ``logs/gpu-rent-metrics.prom``. The vps1
node-exporter is configured to scrape ``--collector.textfile.directory``
(see /etc/systemd/system/node-exporter.service or the redis.py driver's
metrics pattern) — pointing it at our textfile means the metrics ride
the existing observability path without a new scrape target.

For real-time push (mid-rental telemetry), use the pushgateway. Phase 4
ships the textfile pattern; pushgateway is a Phase 4.5 add-on.

Metrics
=======

- ``gpu_rent_sessions_total{provider,kind,workload,success}`` — counter
- ``gpu_rent_cost_usd_total{provider,kind,workload}`` — counter (sum of
  cost_actual_usd)
- ``gpu_rent_active{provider}`` — gauge (currently-alive sessions)
- ``gpu_rent_destroy_pending{provider}`` — gauge (should always be 0;
  >0 = orphan risk → alert)
- ``gpu_rent_foreign_pods`` — gauge (non-Fabrik pods on the account;
  informational; never destroyed by reaper)
- ``gpu_rent_last_reconcile_age_seconds`` — gauge (time since last
  ``fabrik gpu reconcile`` ran; alert if > 1 hour)
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fabrik.config import FABRIK_ROOT
from fabrik.orchestrator import gpu_rent, gpu_state

logger = logging.getLogger(__name__)

METRICS_FILE = FABRIK_ROOT / "logs" / "gpu-rent-metrics.prom"


def _escape_label(v: str) -> str:
    return v.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _line(metric: str, labels: dict[str, str], value: float) -> str:
    if labels:
        label_str = ",".join(f'{k}="{_escape_label(str(v))}"' for k, v in labels.items())
        return f"{metric}{{{label_str}}} {value}"
    return f"{metric} {value}"


def collect() -> dict[str, Any]:
    """Build the metrics dict from gpu_state + the history log.

    Returns a structured dict (for tests). Use ``render()`` to format as
    Prometheus text.
    """
    state = gpu_state.load_state()
    sessions = state.get("sessions", {})
    now = datetime.now(UTC)

    # Counters from history log
    sessions_total: dict[tuple[str, str, str, str], int] = {}
    cost_total: dict[tuple[str, str, str], float] = {}

    if gpu_rent.GPU_RENT_LOG.exists():
        for raw in gpu_rent.GPU_RENT_LOG.read_text().splitlines():
            if not raw.strip():
                continue
            try:
                rec = json.loads(raw)
            except json.JSONDecodeError:
                continue
            provider = rec.get("provider", "unknown")
            kind = rec.get("kind", "unknown")
            workload = rec.get("workload", "unknown")
            success = "true" if rec.get("success") else "false"
            sessions_total[(provider, kind, workload, success)] = (
                sessions_total.get((provider, kind, workload, success), 0) + 1
            )
            cost = rec.get("cost_actual_usd") or 0.0
            if cost > 0:
                cost_total[(provider, kind, workload)] = (
                    cost_total.get((provider, kind, workload), 0.0) + cost
                )

    # Gauges from state
    active_per_provider: dict[str, int] = {}
    destroy_pending_per_provider: dict[str, int] = {}
    for rec in sessions.values():
        if rec.get("destroyed_at"):
            continue
        provider = rec.get("provider", "unknown")
        active_per_provider[provider] = active_per_provider.get(provider, 0) + 1
        if rec.get("destroy_pending"):
            destroy_pending_per_provider[provider] = (
                destroy_pending_per_provider.get(provider, 0) + 1
            )

    # Reconcile age
    last_recon = state.get("last_reconciled")
    if last_recon:
        try:
            age_seconds = (now - datetime.fromisoformat(last_recon)).total_seconds()
        except ValueError:
            age_seconds = -1.0
    else:
        age_seconds = -1.0

    return {
        "sessions_total": sessions_total,
        "cost_total": cost_total,
        "active_per_provider": active_per_provider,
        "destroy_pending_per_provider": destroy_pending_per_provider,
        "last_reconcile_age_seconds": age_seconds,
    }


def render(metrics: dict[str, Any] | None = None) -> str:
    """Render metrics as Prometheus text-format. Suitable for textfile collector."""
    if metrics is None:
        metrics = collect()

    lines: list[str] = []

    lines.append("# HELP gpu_rent_sessions_total Total number of GPU rental sessions.")
    lines.append("# TYPE gpu_rent_sessions_total counter")
    for (provider, kind, workload, success), value in metrics["sessions_total"].items():
        lines.append(
            _line(
                "gpu_rent_sessions_total",
                {
                    "provider": provider,
                    "kind": kind,
                    "workload": workload,
                    "success": success,
                },
                value,
            )
        )

    lines.append("# HELP gpu_rent_cost_usd_total Total actual cost of completed rentals.")
    lines.append("# TYPE gpu_rent_cost_usd_total counter")
    for (provider, kind, workload), value in metrics["cost_total"].items():
        lines.append(
            _line(
                "gpu_rent_cost_usd_total",
                {
                    "provider": provider,
                    "kind": kind,
                    "workload": workload,
                },
                value,
            )
        )

    lines.append("# HELP gpu_rent_active Currently-active GPU rentals (not yet destroyed).")
    lines.append("# TYPE gpu_rent_active gauge")
    if not metrics["active_per_provider"]:
        lines.append('gpu_rent_active{provider="runpod"} 0')
    for provider, count in metrics["active_per_provider"].items():
        lines.append(_line("gpu_rent_active", {"provider": provider}, count))

    lines.append(
        "# HELP gpu_rent_destroy_pending Sessions whose previous destroy call failed. SHOULD BE 0."
    )
    lines.append("# TYPE gpu_rent_destroy_pending gauge")
    if not metrics["destroy_pending_per_provider"]:
        lines.append('gpu_rent_destroy_pending{provider="runpod"} 0')
    for provider, count in metrics["destroy_pending_per_provider"].items():
        lines.append(_line("gpu_rent_destroy_pending", {"provider": provider}, count))

    lines.append(
        "# HELP gpu_rent_last_reconcile_age_seconds Seconds since last `fabrik gpu reconcile`. Alert if > 3600."
    )
    lines.append("# TYPE gpu_rent_last_reconcile_age_seconds gauge")
    lines.append(
        _line("gpu_rent_last_reconcile_age_seconds", {}, metrics["last_reconcile_age_seconds"])
    )

    return "\n".join(lines) + "\n"


def write_textfile() -> Path:
    """Render metrics + write atomically to METRICS_FILE."""
    METRICS_FILE.parent.mkdir(parents=True, exist_ok=True)
    text = render()
    tmp = METRICS_FILE.with_suffix(".prom.tmp")
    tmp.write_text(text)
    tmp.replace(METRICS_FILE)
    return METRICS_FILE
