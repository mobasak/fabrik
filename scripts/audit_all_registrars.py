#!/usr/bin/env python3
# AFTER-EDIT: docs/reference/health-monitoring.md
"""T4-04 G-G5 — hourly drift audit across all 9 registrars × all specs.

Runs WSL-side via crontab (matches T2-03's G-G4 mechanism — single audit
scheduling pattern). Walks every spec under ``specs/services/*.yaml``,
calls :func:`fabrik.audit.audit_all`, emits Prometheus text-format gauge
metrics, and pushes them through SSH to the VPS-local pushgateway.

Wire diagram::

    crontab(WSL) ─[hourly]─> this script
                              │
                              ├─> fabrik.audit.audit_all(spec)  (per-spec, ×N)
                              │
                              ├─> /tmp/fabrik-audit-metrics.txt  (Prom text)
                              │
                              └─> ssh vps 'curl --data-binary @- <pushgateway>/
                                            metrics/job/fabrik-audit'
                                  └─> pushgateway, port 9091 on vps1's OWN loopback
                                      (the literal lives in `_push_metrics` below —
                                      it is the remote host's loopback, not ours,
                                      which is why it is not a container DNS name)
                                       └─> prometheus scrapes pushgateway
                                            └─> rules/fabrik-drift.yml
                                                 └─> alertmanager route
                                                      └─> existing 'telegram'
                                                           receiver

Metric contract (matches ``rules/fabrik-drift.yml``)::

    # HELP fabrik_audit_drift_total 1 if (spec_id, registrar) is in drift, 0 otherwise.
    # TYPE fabrik_audit_drift_total gauge
    fabrik_audit_drift_total{spec_id="captcha",registrar="postgres"} 0
    fabrik_audit_drift_total{spec_id="captcha",registrar="gatus"}    1

The "_total" suffix is conventional but the semantics are **gauge** — the
value swings 0/1 as drift appears + resolves. We expose ``status`` as a
distinct gauge too so the operator can dashboard "how many missing" vs
"how many drifted" separately.

Exit codes
----------
0  — audit completed; metrics pushed (even when drift was found).
1  — operational error (SSH unreachable / pushgateway down / no specs).
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import sys
import time
from pathlib import Path

from fabrik import registry_reconcile
from fabrik.audit import audit_all
from fabrik.config import FABRIK_ROOT
from fabrik.spec_loader import load_spec

logger = logging.getLogger(__name__)

METRICS_OUT_FILE = Path("/tmp/fabrik-audit-metrics.txt")
PUSHGATEWAY_JOB = "fabrik-audit"
SPECS_DIR = FABRIK_ROOT / "specs" / "services"


def _escape_label(value: str) -> str:
    """Escape a Prometheus label value per the exposition format."""
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _render_metrics(
    results: list[tuple[str, dict[str, object]]],
    heals: list[registry_reconcile.HealResult] | None = None,
    *,
    success: bool = False,
    spec_errors: int = 0,
) -> str:
    """Render the per-(spec_id, registrar) audit results as Prom text.

    Two audit gauges:

    - ``fabrik_audit_drift_total`` — 1 when status is ``drift``, else 0.
      This is what the alert rule fires on.
    - ``fabrik_audit_status`` — encodes the full status as a label so
      Grafana can chart missing/unknown/n/a separately.

    Plus the registry reconcile's series (plan-2): ``fabrik_registry_heal_total``
    per heal outcome, ``fabrik_registry_heal_failed`` per failed heal,
    ``fabrik_audit_spec_errors`` every run, and
    ``fabrik_audit_last_success_timestamp_seconds`` only when ``success`` (no spec
    error and the reconcile raised nothing). The push replaces the whole group, so
    a run without the timestamp deletes it and ``FabrikAuditStale`` fires.
    """
    lines: list[str] = [
        "# HELP fabrik_audit_drift_total 1 if (spec_id, registrar) is in drift, 0 otherwise.",
        "# TYPE fabrik_audit_drift_total gauge",
    ]
    status_lines: list[str] = [
        "# HELP fabrik_audit_status 1 when (spec_id, registrar, status) is the current audit state.",
        "# TYPE fabrik_audit_status gauge",
    ]
    for spec_id, registrar_results in results:
        for registrar, result in registrar_results.items():
            status = result.status if hasattr(result, "status") else str(result.get("status"))
            spec_id_esc = _escape_label(spec_id)
            registrar_esc = _escape_label(registrar)
            drift_value = 1 if status == "drift" else 0
            lines.append(
                f'fabrik_audit_drift_total{{spec_id="{spec_id_esc}",registrar="{registrar_esc}"}} {drift_value}'
            )
            status_lines.append(
                f'fabrik_audit_status{{spec_id="{spec_id_esc}",registrar="{registrar_esc}",status="{_escape_label(status)}"}} 1'
            )
    heal_lines = [
        "# HELP fabrik_registry_heal_total 1 per (spec_id, db, outcome) the registry reconcile produced this run.",
        "# TYPE fabrik_registry_heal_total gauge",
    ]
    failed_lines = [
        "# HELP fabrik_registry_heal_failed 1 per (spec_id, db, reason) the registry reconcile could not register.",
        "# TYPE fabrik_registry_heal_failed gauge",
    ]
    for h in heals or []:
        sid, db = _escape_label(h.spec_id), _escape_label(h.db)
        heal_lines.append(
            f'fabrik_registry_heal_total{{spec_id="{sid}",db="{db}",outcome="{_escape_label(h.outcome)}"}} 1'
        )
        if h.outcome == "failed":
            failed_lines.append(
                f'fabrik_registry_heal_failed{{spec_id="{sid}",db="{db}",reason="{_escape_label(h.reason)}"}} 1'
            )
    run_lines = [
        "# HELP fabrik_audit_spec_errors Specs skipped this run because they failed to load or audit.",
        "# TYPE fabrik_audit_spec_errors gauge",
        f"fabrik_audit_spec_errors {spec_errors}",
    ]
    if success:
        run_lines += [
            "# HELP fabrik_audit_last_success_timestamp_seconds Unix time of the last run with no spec error and no reconcile crash.",
            "# TYPE fabrik_audit_last_success_timestamp_seconds gauge",
            f"fabrik_audit_last_success_timestamp_seconds {int(time.time())}",
        ]
    blocks = [lines, status_lines, heal_lines, failed_lines, run_lines]
    return "\n\n".join("\n".join(b) for b in blocks) + "\n"


def _push_to_gateway(metrics_path: Path) -> None:
    """Push the Prom-text file to the VPS-local pushgateway via SSH.

    The pushgateway is bound to ``127.0.0.1:9091`` on the VPS host (not
    publicly exposed). We run curl INSIDE the VPS via ssh so the
    loopback bind is reachable — no port-forwarding / Cloudflare proxy
    needed for the audit cron.
    """
    ssh = shutil.which("ssh")
    if ssh is None:
        raise RuntimeError("ssh not found in PATH — cannot push metrics")
    cmd = [
        ssh,
        "vps",
        f"curl -fsS -X PUT --data-binary @- http://localhost:9091/metrics/job/{PUSHGATEWAY_JOB}",  # noqa: runs remotely via ssh; pushgateway is loopback-bound on vps1
    ]
    with metrics_path.open("rb") as f:
        proc = subprocess.run(cmd, stdin=f, capture_output=True, timeout=30, check=False)
    if proc.returncode != 0:
        raise RuntimeError(
            f"pushgateway push failed: rc={proc.returncode} stderr={proc.stderr.decode()[:200]}"
        )


def _reconcile(
    results: list[tuple[str, dict[str, object]]], specs: dict[str, object], error_count: int
) -> tuple[list[registry_reconcile.HealResult], bool]:
    """Run the registry reconcile over this run's audits; ``(heals, ok)``.

    ``ok`` is False when the reconcile itself raised — the audit series are still
    pushed, without the last-success timestamp.
    """
    m = registry_reconcile.mode()
    if m == "off":
        return [], True
    try:
        claim_map, unresolved = registry_reconcile.claims(specs.values())
        heals = registry_reconcile.reconcile_postgres(
            dict(results),
            claim_map,
            claims_complete=error_count == 0 and not unresolved,
            dry_run=m == "report",
        )
    except Exception as exc:  # noqa: BLE001 — the audit push must survive a reconcile crash
        logger.error("registry reconcile failed: %s", exc)
        return [], False
    return heals, True


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s audit_all_registrars: %(message)s",
    )

    if not SPECS_DIR.is_dir():
        logger.error("no specs dir at %s", SPECS_DIR)
        return 1

    spec_paths = sorted(SPECS_DIR.glob("*.yaml"))
    if not spec_paths:
        logger.error("no specs found under %s", SPECS_DIR)
        return 1

    results: list[tuple[str, dict[str, object]]] = []
    specs: dict[str, object] = {}
    drift_count = 0
    error_count = 0
    for path in spec_paths:
        try:
            spec = load_spec(str(path))
        except Exception as exc:  # noqa: BLE001 — best-effort per spec
            logger.warning("skip %s: load failed (%s)", path.name, exc)
            error_count += 1
            continue
        if spec.id in specs:
            logger.warning("skip %s: duplicate spec id %s", path.name, spec.id)
            error_count += 1
            continue
        try:
            per_registrar = audit_all(spec)
        except Exception as exc:  # noqa: BLE001
            logger.warning("skip %s: audit_all failed (%s)", spec.id, exc)
            error_count += 1
            continue
        for _registrar, result in per_registrar.items():
            status = result.status if hasattr(result, "status") else str(result.get("status"))
            if status == "drift":
                drift_count += 1
        results.append((spec.id, per_registrar))
        specs[spec.id] = spec

    logger.info(
        "audited %d specs; drift=%d, errors=%d, pushing metrics",
        len(results),
        drift_count,
        error_count,
    )

    heals, reconcile_ok = _reconcile(results, specs, error_count)
    registered = {h.spec_id for h in heals if h.outcome == "registered"}
    for i, (sid, _old) in enumerate(results):
        if sid not in registered:
            continue
        try:
            results[i] = (sid, audit_all(specs[sid]))
        except Exception as exc:  # noqa: BLE001 — keep the pre-heal result, withhold the timestamp
            logger.warning("re-audit of %s after registration failed (%s)", sid, exc)
            reconcile_ok = False

    METRICS_OUT_FILE.write_text(
        _render_metrics(
            results, heals, success=error_count == 0 and reconcile_ok, spec_errors=error_count
        ),
        encoding="utf-8",
    )
    try:
        _push_to_gateway(METRICS_OUT_FILE)
    except Exception as exc:  # noqa: BLE001 — cron must surface push failures
        logger.error("pushgateway push failed: %s", exc)
        return 1

    logger.info("metrics pushed to pushgateway job=%s", PUSHGATEWAY_JOB)
    return 0


if __name__ == "__main__":
    sys.exit(main())
