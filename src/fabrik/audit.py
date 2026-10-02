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
import re
import shlex
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Literal, cast

from fabrik.app_role_check import _db_name_for_spec
from fabrik.drivers.postgres import _validate_identifier
from fabrik.orchestrator.infrastructure import _REGISTRAR_ORDER, resolve_applicability

logger = logging.getLogger(__name__)

AuditStatus = Literal["present", "missing", "n/a", "unknown", "drift"]


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
_CONTAINER_PROBE_FAILED: dict[str, float] = {}
_PROBE_RETRY_S = 60.0


def _now() -> float:
    return time.monotonic()


def _resolve_container(prefix: str) -> str | None:
    # Resolve a container name from a stable prefix like "postgres-main",
    # "backrest" or "authelia" (bare name or a legacy `<prefix>-<suffix>`).
    #
    # Cached per-process so audit_all's sweep does at most one docker-ps
    # round-trip per distinct prefix — but only an ANSWERED probe is cached
    # (a name, or "" for a container that is not running). `docker ps` runs
    # alone, so its own exit status reaches `ok`: in a `docker ps | grep | head`
    # pipeline a failed docker (daemon down, sudo refused) exits 0 through
    # `head` and read as "not running". A FAILED probe is not cached for the
    # run, which once blinded every later audit after one ssh blip
    # (W-c6d27660); it is held back for _PROBE_RETRY_S, so a dead ssh costs a
    # few probes per run instead of one ~30 s timeout per audit call.
    if prefix in _CONTAINER_CACHE:
        return _CONTAINER_CACHE[prefix] or None
    if _now() < _CONTAINER_PROBE_FAILED.get(prefix, 0.0):
        return None
    ok, out = _ssh_check("sudo docker ps --format '{{.Names}}'")
    if not ok:
        _CONTAINER_PROBE_FAILED[prefix] = _now() + _PROBE_RETRY_S
        return None
    pattern = re.compile(rf"^{re.escape(prefix)}(-|$)")
    name = next((n.strip() for n in out.splitlines() if pattern.match(n.strip())), "")
    _CONTAINER_CACHE[prefix] = name
    _CONTAINER_PROBE_FAILED.pop(prefix, None)
    return name or None


# ─────────────────────────────────────────────────────────────────────────────
# Per-registrar audits
# ─────────────────────────────────────────────────────────────────────────────


def audit_postgres(spec: Any) -> AuditResult:
    applicable = _resolved_for(spec).get("postgres", (False, "n/a"))
    if not applicable[0]:
        return AuditResult(status="n/a", detail=applicable[1])
    # The registrar's name rule (depends.postgres wins), validated before any
    # SQL because depends.postgres carries no pattern at load time.
    try:
        db_name = _db_name_for_spec(_spec_to_dict(spec))
        _validate_identifier(db_name, "database")
    except ValueError as exc:  # SpecResolutionError is a ValueError
        return AuditResult(status="unknown", detail=str(exc))
    container = _resolve_container("postgres-main")
    if not container:
        return AuditResult(
            status="unknown",
            detail="postgres-main container not found",
            expected={"db_name": db_name},
        )
    # Mirror postgres.py — SELECT 1 FROM pg_database WHERE datname=...
    # nosec B608 — db_name passed _validate_identifier above
    # ([a-zA-Z_][a-zA-Z0-9_]{0,62}); same pattern as postgres.py.
    sql = f"SELECT 1 FROM pg_database WHERE datname='{db_name}'"  # nosec B608
    ok, out = _ssh_check(
        f"sudo docker exec {shlex.quote(container)} psql -U postgres -At -c {shlex.quote(sql)}"
    )
    if not ok:
        return AuditResult(
            status="unknown",
            detail=f"ssh probe failed: {out[:80]}",
            expected={"db_name": db_name},
            actual={"error": out},
        )
    db_present = out == "1"

    # T4-01 G-J4: cross-reference allocations.json. The registry is the
    # source of truth for "who owns this DB"; drift means the registry
    # and live pg_database disagree.
    try:
        from fabrik.drivers.postgres import list_allocations

        allocs = list_allocations().get("allocations", {})
        registry_entry = allocs.get(db_name)
    except Exception as exc:  # noqa: BLE001 — registry read is informational
        logger.warning("audit_postgres: registry read failed (%s); skipping drift check", exc)
        registry_entry = None
        allocs = None

    actual: dict[str, Any] = {"db_name": db_name, "found": db_present}
    if allocs is not None:
        actual["registry_entry"] = registry_entry
        actual["in_registry"] = registry_entry is not None

    # Four-quadrant classification:
    #   DB present + registry present  → present
    #   DB present + registry missing  → drift  (orphan DB: unmanaged)
    #   DB missing + registry present  → drift  (stale registry: ghost entry)
    #   DB missing + registry missing  → missing (spec says it should exist)
    if db_present and registry_entry is not None:
        return AuditResult(
            status="present",
            detail=f"db {db_name} exists; registry owner={registry_entry.get('owner')!r}",
            expected={"db_name": db_name},
            actual=actual,
        )
    if db_present and allocs is not None and registry_entry is None:
        return AuditResult(
            status="drift",
            detail=f"db {db_name} exists in pg_database but is not in allocations.json (orphan/unmanaged)",
            expected={"db_name": db_name, "registry": "entry"},
            actual=actual,
        )
    if not db_present and allocs is not None and registry_entry is not None:
        return AuditResult(
            status="drift",
            detail=f"db {db_name} in allocations.json but missing from pg_database (stale registry)",
            expected={"db_name": db_name},
            actual=actual,
        )
    if db_present:
        # Registry read failed; fall back to legacy "DB present == present"
        return AuditResult(
            status="present",
            detail=f"db {db_name} exists (registry unreadable; drift check skipped)",
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
        from fabrik.drivers.redis import extract_assignments

        assignments = extract_assignments(json.loads(out)) if out else {}
    except (json.JSONDecodeError, RuntimeError, AttributeError) as e:
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


def _backrest_target(spec: Any, sid: str, hub: str) -> str:
    """The host the service runs on, resolved as ``fabrik destroy`` does without its CLI flag:
    ``<FABRIK_ROOT>/.fabrik/state/<id>.json`` (anchored at the hub root, never the cwd), then the
    spec's ``target_vps``, then ``vps1`` — and ``vps1`` is the hub alias."""
    import json

    from fabrik import config

    target = None
    try:
        state = config.FABRIK_ROOT / ".fabrik" / "state" / f"{sid}.json"
        if state.is_file():
            target = json.loads(state.read_text()).get("target_vps")
    except (OSError, ValueError, AttributeError):
        target = None
    target = target or _spec_to_dict(spec).get("target_vps") or "vps1"
    return hub if target == "vps1" else str(target)


def audit_backrest(spec: Any) -> AuditResult:
    """Coverage of the service's real persistence by trusted host plans (W-5c4ad6a6, D-518)."""
    sid = _spec_id(spec)
    resolved = _resolved_for(spec)
    applicable = resolved.get("backrest", (False, "n/a"))
    if not applicable[0]:
        return AuditResult(status="n/a", detail=applicable[1])
    from fabrik.drivers import backrest

    hub = os.getenv("FABRIK_AUDIT_VPS", "vps")
    target = _backrest_target(spec, sid, hub)
    # the compose project the deployer created: /opt/<spec name> (deployer_ssh.py, ctx.spec["name"]),
    # name-first as the registrar reads it — `sid` is id-first and keys only the state file
    project = str(_spec_to_dict(spec).get("name") or sid)
    db = None
    if resolved.get("postgres", (False, ""))[0]:
        try:
            db = _db_name_for_spec(_spec_to_dict(spec))
        except ValueError:
            db = None
    expected = {"project": project, "target_host": target, "database": db}
    try:
        status, findings, actual = backrest.coverage_findings(
            project, db, target_host=target, hub_host=hub
        )
    except Exception as e:  # noqa: BLE001 — a check that cannot run is unknown, never a guess
        return AuditResult(
            status="unknown", detail=f"coverage check failed: {e}", expected=expected
        )
    if findings:
        detail = "; ".join(findings)
    else:
        ids = sorted(set((actual.get("covered_by") or {}).values()))
        detail = f"covered by {', '.join(ids)}" if ids else "covered"
    return AuditResult(
        status=cast(AuditStatus, status), detail=detail, expected=expected, actual=actual
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
        f"http://localhost:7700/indexes/{shlex.quote(index_uid)}'"  # noqa: localhost is correct — runs INSIDE the meilisearch container via docker exec
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


def audit_watchdog(spec: Any) -> AuditResult:
    """Audit the per-project watchdog sidecar (D3).

    The sidecar is injected via a ``compose.watchdog.yaml`` overlay and named
    ``<project>-watchdog`` (e.g. ``watchdog-test-watchdog``). Report whether that container is
    running on the target VPS, so ``audit-registrars`` answers present/missing instead of the
    ``unknown`` it returns today (``_AUDIT_FUNCS`` was missing a ``watchdog`` entry).
    """
    sid = _spec_id(spec)
    applicable = _resolved_for(spec).get("watchdog", (False, "n/a"))
    if not applicable[0]:
        return AuditResult(status="n/a", detail=applicable[1])
    container = f"{sid}-watchdog"
    # docker runs alone so its exit status reaches `ok`: behind `| grep -q . || echo missing`
    # a failed docker read as an absent sidecar (W-c6d27660).
    ok, out = _ssh_check(
        f"sudo docker ps --filter name={shlex.quote('^' + container + '$')} --format '{{{{.Names}}}}'"
    )
    if not ok:
        return AuditResult(status="unknown", detail=f"ssh probe failed: {out[:80]}")
    found = container in out.split()
    return AuditResult(
        status="present" if found else "missing",
        detail=f"{container} sidecar {'running' if found else 'absent'}",
        expected={"container": container},
        actual={"found": found},
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
    "watchdog": audit_watchdog,
}


def audit_all(spec: Any) -> dict[str, AuditResult]:
    """Run all 10 per-registrar audits for ``spec``.

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
