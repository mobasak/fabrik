"""Per-registrar drift audit module (T2-02 G-G2).

Companion to :mod:`fabrik.orchestrator.infrastructure` — that module decides
what SHOULD run (``resolve_applicability``); this module asks the live VPS
what IS actually registered. The pair is the foundation of
``fabrik audit-registrars``, ``fabrik reconcile-all``, and the future
state-aware destroy (T4-01/T4-02).

Each ``audit_<reg>(spec)`` function returns an :class:`AuditResult` with:

* ``status`` ∈ {``present``, ``missing``, ``n/a``, ``unknown``} — exactly
  what audit functions produce. ``drift`` (live shape differs from
  expected) is not yet produced by any auditor; will be added in a
  follow-up that compares config bags. ``override`` is folded into
  ``n/a`` with the override reason in ``detail``.
* ``detail`` — short human-readable explanation
* ``expected`` — what the spec's shape says SHOULD be there (per
  ``resolve_applicability``)
* ``actual`` — what we observed live

Driver-pattern parity
---------------------

Every registrar driver in :mod:`fabrik.drivers` uses SSH for VPS reads;
``glitchtip`` adds an HTTP layer (``requests``) for the GlitchTip API.
Audit functions mirror exactly: SSH where the driver uses SSH, ``requests``
where the driver uses ``requests``. No new transport surfaces.

When an audit can't be implemented cleanly (e.g. ``grafana`` annotations
are point-in-time markers with no live driftable state), the function
returns ``status="n/a"`` with a reason. Auditors NEVER raise — every
failure mode collapses to ``status="unknown"`` with the exception text
in ``detail`` so the aggregate ``audit_all`` stays robust.
"""

from __future__ import annotations

import logging
import os
import shlex
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from fabrik.orchestrator.infrastructure import _REGISTRAR_ORDER, resolve_applicability

logger = logging.getLogger(__name__)

AuditStatus = Literal["present", "missing", "n/a", "unknown"]


@dataclass
class AuditResult:
    status: AuditStatus
    detail: str = ""
    expected: dict[str, Any] = field(default_factory=dict)
    actual: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _spec_to_dict(spec: Any) -> dict[str, Any]:
    # Tolerate both pydantic Spec and a parsed dict — audit is called from
    # both CLI (loaded Spec) and orchestrator/tests (raw dict).
    if hasattr(spec, "model_dump"):
        return spec.model_dump()
    if hasattr(spec, "dict"):
        return spec.dict()
    return dict(spec)


def _spec_id(spec: Any) -> str:
    d = _spec_to_dict(spec)
    return str(d.get("id") or d.get("name") or "")


def _spec_domain(spec: Any) -> str:
    return str(_spec_to_dict(spec).get("domain") or "")


def _resolved_for(spec: Any) -> dict[str, tuple[bool, str]]:
    return resolve_applicability(_spec_to_dict(spec))


def _ssh_check(cmd: str, *, timeout: int = 30) -> tuple[bool, str]:
    # Best-effort SSH probe. Never raises; returns (ok, stdout|stderr).
    import subprocess

    vps = os.getenv("FABRIK_AUDIT_VPS", "vps")
    try:
        r = subprocess.run(
            ["ssh", vps, cmd],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        if r.returncode == 0:
            return True, r.stdout.strip()
        return False, (r.stderr or r.stdout).strip()
    except Exception as e:  # noqa: BLE001
        return False, f"{type(e).__name__}: {e}"


_CONTAINER_CACHE: dict[str, str] = {}


def _resolve_container(prefix: str) -> str | None:
    # Resolve a Coolify-managed container name from a stable prefix like
    # "postgres-main" or "backrest" or "authelia". Coolify renames the
    # container on every redeploy (suffix is a UUID); hardcoding the
    # current UUID would make audits silently break after the next
    # Coolify redeploy.
    #
    # Cached per-process so audit_all's 9-call sweep does at most one
    # docker-ps round-trip per distinct prefix.
    if prefix in _CONTAINER_CACHE:
        return _CONTAINER_CACHE[prefix] or None
    ok, out = _ssh_check(
        f"sudo docker ps --format '{{{{.Names}}}}' | grep -E '^{prefix}(-|$)' | head -1"
    )
    name = out.strip() if ok else ""
    _CONTAINER_CACHE[prefix] = name
    return name or None


# ─────────────────────────────────────────────────────────────────────────────
# Per-registrar audits
# ─────────────────────────────────────────────────────────────────────────────


def audit_postgres(spec: Any) -> AuditResult:
    sid = _spec_id(spec)
    applicable = _resolved_for(spec).get("postgres", (False, "n/a"))
    db_name = sid.replace("-", "_")
    if not applicable[0]:
        return AuditResult(status="n/a", detail=applicable[1])
    container = _resolve_container("postgres-main")
    if not container:
        return AuditResult(
            status="unknown",
            detail="postgres-main container not found",
            expected={"db_name": db_name},
        )
    # Mirror postgres.py:155 — SELECT 1 FROM pg_database WHERE datname=...
    # nosec B608 — db_name is derived from spec.id which is regex-validated
    # at load time; same pattern as postgres.py:155 which carries the same
    # annotation. No external untrusted input flows through this query.
    sql = f"SELECT 1 FROM pg_database WHERE datname='{db_name}'"  # nosec B608
    ok, out = _ssh_check(
        f"sudo docker exec {shlex.quote(container)} psql -U postgres -At -c {shlex.quote(sql)}"
    )
    actual = {"db_name": db_name, "found": out == "1"} if ok else {"error": out}
    if not ok:
        return AuditResult(
            status="unknown",
            detail=f"ssh probe failed: {out[:80]}",
            expected={"db_name": db_name},
            actual=actual,
        )
    if out == "1":
        return AuditResult(
            status="present",
            detail=f"db {db_name} exists",
            expected={"db_name": db_name},
            actual=actual,
        )
    return AuditResult(
        status="missing",
        detail=f"db {db_name} not found",
        expected={"db_name": db_name},
        actual=actual,
    )


def audit_redis(spec: Any) -> AuditResult:
    sid = _spec_id(spec)
    applicable = _resolved_for(spec).get("redis", (False, "n/a"))
    if not applicable[0]:
        return AuditResult(status="n/a", detail=applicable[1])
    # Mirror redis.py — the source of truth is the host-side registry at
    # /opt/monitoring/configs/redis/assignments.json. A present entry =
    # registered.
    ok, out = _ssh_check("sudo cat /opt/monitoring/configs/redis/assignments.json 2>/dev/null")
    if not ok:
        return AuditResult(
            status="unknown",
            detail=f"assignments.json unreadable: {out[:80]}",
            expected={"service": sid},
            actual={"error": out},
        )
    import json

    try:
        assignments = json.loads(out) if out else {}
    except json.JSONDecodeError as e:
        return AuditResult(
            status="unknown",
            detail=f"assignments.json invalid: {e}",
            expected={"service": sid},
            actual={"raw": out[:120]},
        )
    if sid in assignments:
        return AuditResult(
            status="present",
            detail=f"redis slot {assignments[sid]} assigned",
            expected={"service": sid},
            actual={"db_index": assignments[sid]},
        )
    return AuditResult(
        status="missing",
        detail=f"no redis slot for {sid}",
        expected={"service": sid},
        actual={"assignments_keys": sorted(assignments)},
    )


def audit_gatus(spec: Any) -> AuditResult:
    sid = _spec_id(spec)
    applicable = _resolved_for(spec).get("gatus", (False, "n/a"))
    if not applicable[0]:
        return AuditResult(status="n/a", detail=applicable[1])
    # Mirror gatus.py: per-service endpoint config under apps/<name>.yaml
    ok, out = _ssh_check(
        f"sudo test -f /opt/monitoring/configs/gatus/apps/{shlex.quote(sid)}.yaml && echo present || echo missing"
    )
    if not ok:
        return AuditResult(status="unknown", detail=f"ssh probe failed: {out[:80]}")
    found = "present" in out
    return AuditResult(
        status="present" if found else "missing",
        detail=f"gatus/apps/{sid}.yaml {'exists' if found else 'absent'}",
        expected={"config_path": f"/opt/monitoring/configs/gatus/apps/{sid}.yaml"},
        actual={"found": found},
    )


def audit_backrest(spec: Any) -> AuditResult:
    sid = _spec_id(spec)
    applicable = _resolved_for(spec).get("backrest", (False, "n/a"))
    if not applicable[0]:
        return AuditResult(status="n/a", detail=applicable[1])
    # Mirror backrest.py: plans live inside container's config.json
    container = _resolve_container("backrest")
    if not container:
        return AuditResult(status="unknown", detail="backrest container not found")
    ok, out = _ssh_check(
        f"sudo docker exec {shlex.quote(container)} cat /config/config.json 2>/dev/null"
    )
    if not ok:
        return AuditResult(status="unknown", detail=f"config.json unreadable: {out[:80]}")
    import json

    try:
        cfg = json.loads(out) if out else {}
    except json.JSONDecodeError as e:
        return AuditResult(status="unknown", detail=f"config.json invalid: {e}")
    plans = {p.get("id"): p for p in cfg.get("plans", [])}
    if sid in plans:
        return AuditResult(
            status="present",
            detail=f"backrest plan {sid} exists",
            expected={"plan_id": sid},
            actual={"paths": plans[sid].get("paths", [])},
        )
    return AuditResult(
        status="missing",
        detail=f"no backrest plan for {sid}",
        expected={"plan_id": sid},
        actual={"plan_ids": sorted(plans)},
    )


def audit_glitchtip(spec: Any) -> AuditResult:
    sid = _spec_id(spec)
    applicable = _resolved_for(spec).get("glitchtip", (False, "n/a"))
    if not applicable[0]:
        return AuditResult(status="n/a", detail=applicable[1])
    # Mirror glitchtip.py: GET /api/0/projects/{org}/{name}/ → 200/404
    try:
        import requests  # noqa: F401  # only imported when needed

        from fabrik.drivers.glitchtip import _project_url
    except ImportError as e:
        return AuditResult(status="unknown", detail=f"driver import failed: {e}")
    org = os.getenv("GLITCHTIP_ORG", "ocoron")
    token = os.getenv("GLITCHTIP_API_TOKEN", "")
    if not token:
        return AuditResult(
            status="unknown",
            detail="GLITCHTIP_API_TOKEN not set",
            expected={"project": sid, "org": org},
        )
    headers = {"Authorization": f"Bearer {token}"}
    try:
        import requests

        url = _project_url(org, sid)
        resp = requests.get(url, headers=headers, timeout=10)
    except Exception as e:  # noqa: BLE001
        return AuditResult(status="unknown", detail=f"http probe failed: {e}")
    if resp.status_code == 200:
        return AuditResult(
            status="present",
            detail=f"glitchtip project {org}/{sid} exists",
            expected={"project": sid},
            actual={"http_status": 200},
        )
    if resp.status_code == 404:
        return AuditResult(
            status="missing",
            detail=f"glitchtip project {org}/{sid} not found",
            expected={"project": sid},
            actual={"http_status": 404},
        )
    return AuditResult(
        status="unknown",
        detail=f"unexpected http status {resp.status_code}",
        actual={"http_status": resp.status_code},
    )


def audit_grafana(spec: Any) -> AuditResult:
    # Grafana annotations are point-in-time markers, not driftable state.
    # No live check is meaningful; returning n/a documents the design
    # choice explicitly.
    return AuditResult(
        status="n/a",
        detail="grafana annotations are decorative (point-in-time markers); not driftable",
    )


def audit_authelia(spec: Any) -> AuditResult:
    domain = _spec_domain(spec)
    applicable = _resolved_for(spec).get("authelia", (False, "n/a"))
    if not applicable[0]:
        return AuditResult(status="n/a", detail=applicable[1])
    if not domain:
        return AuditResult(
            status="missing",
            detail="no domain in spec",
            expected={"domain": "(required)"},
            actual={},
        )
    # Mirror authelia.py: cat /config/configuration.yml inside container
    container = _resolve_container("authelia")
    if not container:
        return AuditResult(status="unknown", detail="authelia container not found")
    ok, out = _ssh_check(
        f"sudo docker exec {shlex.quote(container)} cat /config/configuration.yml 2>/dev/null"
    )
    if not ok:
        return AuditResult(status="unknown", detail=f"config unreadable: {out[:80]}")
    try:
        import yaml as yaml_lib

        cfg = yaml_lib.safe_load(out) or {}
    except yaml_lib.YAMLError as e:
        return AuditResult(status="unknown", detail=f"yaml invalid: {e}")
    rules = cfg.get("access_control", {}).get("rules", [])
    matches = []
    for r in rules:
        d = r.get("domain")
        domains = d if isinstance(d, list) else [d]
        if domain in domains:
            matches.append({"policy": r.get("policy"), "resources": r.get("resources")})
    if matches:
        return AuditResult(
            status="present",
            detail=f"{len(matches)} authelia rule(s) for {domain}",
            expected={"domain": domain},
            actual={"rules": matches},
        )
    return AuditResult(
        status="missing",
        detail=f"no authelia rule for {domain}",
        expected={"domain": domain},
        actual={"rule_count": len(rules)},
    )


def audit_meilisearch(spec: Any) -> AuditResult:
    sid = _spec_id(spec)
    applicable = _resolved_for(spec).get("meilisearch", (False, "n/a"))
    if not applicable[0]:
        return AuditResult(status="n/a", detail=applicable[1])
    # Mirror meilisearch.py — call its in-container curl helper indirectly
    # via the same docker-exec pattern. index_uid converts dashes → underscores.
    index_uid = sid.replace("-", "_")
    ok, container = _ssh_check(
        "sudo docker ps --format '{{.Names}}' | grep -E '^bs0wo48k|^meilisearch' | head -1"
    )
    if not ok or not container:
        return AuditResult(
            status="unknown",
            detail="meilisearch container not found via docker ps",
        )
    # Use in-container curl against /indexes/<uid>; 200 = present, 404 = missing
    probe = (
        f"sudo docker exec {shlex.quote(container)} "
        f"sh -c 'curl -s -o /dev/null -w %{{http_code}} "
        f'-H "Authorization: Bearer ${{MEILI_MASTER_KEY}}" '
        f"http://localhost:7700/indexes/{shlex.quote(index_uid)}'"
    )
    ok, code = _ssh_check(probe)
    if not ok:
        return AuditResult(status="unknown", detail=f"probe failed: {code[:80]}")
    if code == "200":
        return AuditResult(
            status="present",
            detail=f"index {index_uid} exists",
            expected={"index": index_uid},
            actual={"http_status": 200},
        )
    if code == "404":
        return AuditResult(
            status="missing",
            detail=f"index {index_uid} not found",
            expected={"index": index_uid},
            actual={"http_status": 404},
        )
    return AuditResult(
        status="unknown",
        detail=f"unexpected http status {code}",
        actual={"http_status": code},
    )


def audit_prometheus(spec: Any) -> AuditResult:
    sid = _spec_id(spec)
    applicable = _resolved_for(spec).get("prometheus", (False, "n/a"))
    if not applicable[0]:
        return AuditResult(status="n/a", detail=applicable[1])
    # Mirror prometheus.py: scrape jobs live in /opt/monitoring/configs/prometheus/prometheus.yml
    # File uses YAML list form: ``- job_name: <name>``
    ok, out = _ssh_check(
        "sudo grep 'job_name' /opt/monitoring/configs/prometheus/prometheus.yml 2>/dev/null"
    )
    if not ok:
        return AuditResult(status="unknown", detail=f"prometheus.yml unreadable: {out[:80]}")
    jobs = []
    for line in out.splitlines():
        # Strip leading "  - " or "    " prefixes; split on first ':'
        cleaned = line.lstrip(" -")
        if cleaned.startswith("job_name:"):
            val = cleaned[len("job_name:") :].strip().strip("'\"")
            if val:
                jobs.append(val)
    if sid in jobs or f"fabrik-{sid}" in jobs:
        matched = sid if sid in jobs else f"fabrik-{sid}"
        return AuditResult(
            status="present",
            detail=f"scrape job {matched} configured",
            expected={"job_name": sid},
            actual={"job_name": matched, "all_jobs": jobs},
        )
    return AuditResult(
        status="missing",
        detail=f"no scrape job for {sid}",
        expected={"job_name": sid},
        actual={"all_jobs": jobs},
    )


# ─────────────────────────────────────────────────────────────────────────────
# Aggregator
# ─────────────────────────────────────────────────────────────────────────────


_AUDIT_FUNCS = {
    "postgres": audit_postgres,
    "redis": audit_redis,
    "gatus": audit_gatus,
    "backrest": audit_backrest,
    "glitchtip": audit_glitchtip,
    "grafana": audit_grafana,
    "authelia": audit_authelia,
    "meilisearch": audit_meilisearch,
    "prometheus": audit_prometheus,
}


def audit_all(spec: Any) -> dict[str, AuditResult]:
    """Run all 9 per-registrar audits for ``spec``.

    Returns a dict keyed by registrar name. Every key in
    :data:`fabrik.orchestrator.infrastructure._REGISTRAR_ORDER` is present
    in the output. Failures in individual audits collapse to
    ``AuditResult(status="unknown", detail=str(exc))`` — this function
    never raises.
    """
    results: dict[str, AuditResult] = {}
    for name in _REGISTRAR_ORDER:
        fn = _AUDIT_FUNCS.get(name)
        if fn is None:
            results[name] = AuditResult(status="unknown", detail="no audit function registered")
            continue
        try:
            results[name] = fn(spec)
        except Exception as e:  # noqa: BLE001
            results[name] = AuditResult(status="unknown", detail=f"{type(e).__name__}: {e}")
    return results


__all__ = [
    "AuditResult",
    "AuditStatus",
    "audit_all",
    "audit_authelia",
    "audit_backrest",
    "audit_gatus",
    "audit_glitchtip",
    "audit_grafana",
    "audit_meilisearch",
    "audit_postgres",
    "audit_prometheus",
    "audit_redis",
]
