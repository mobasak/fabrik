"""Permanent spoke provisioning + reverse-fleet teardown (Phase 5).

``provision()`` creates a real, billed fleet member: a Vultr instance named
``vpsN`` whose mesh IP is deterministically ``10.99.0.N`` (see plan §C), then runs
the FULL ``bootstrap-vps.sh root@<ip> vpsN`` (no ``--skip`` flags) — which handles
mesh peer registration (step_06), DNS (step_13), and monitoring agents (step_11).
State is recorded with ``mode=permanent``.

``reverse_fleet_destroy()`` (``fabrik vultr destroy <name> --reverse-fleet-add``)
unwinds provision in reverse: Gatus → Prometheus → Backrest → DNS → wg0 peer →
instance, then marks state destroyed. Each step is best-effort (continue-on-error).

SAFETY: provision is irreversible billing + a production topology change. It
requires an explicit ``confirm=True`` (the CLI prompts interactively; no ``-y``
bypass). On bootstrap failure the instance is LEFT for the operator (not auto-
destroyed) — permanent boxes may hold partial state worth inspecting.
"""

from __future__ import annotations

import logging
import re
import subprocess
from datetime import UTC, datetime
from typing import Any

from fabrik.config import FABRIK_ROOT
from fabrik.drivers.vultr import VultrClient, VultrError
from fabrik.orchestrator import vultr_state

logger = logging.getLogger(__name__)

BOOTSTRAP_DIR = FABRIK_ROOT / "scripts" / "bootstrap"
MESH_SUBNET_PREFIX = "10.99.0"
SPOKE_NAME_RE = re.compile(r"^vps([0-9]+)$")
_MIN_SPOKE_N = 2  # vps1 is the hub
_MAX_SPOKE_N = 254
_BOOTSTRAP_TIMEOUT = 1500  # 25 min for a full spoke bootstrap


def spoke_number(name: str) -> int:
    m = SPOKE_NAME_RE.match(name)
    if not m:
        raise VultrError(f"spoke name {name!r} must match ^vps[0-9]+$")
    n = int(m.group(1))
    if not (_MIN_SPOKE_N <= n <= _MAX_SPOKE_N):
        raise VultrError(f"spoke number {n} out of range [{_MIN_SPOKE_N}, {_MAX_SPOKE_N}]")
    return n


def mesh_ip_for(name: str) -> str:
    """Deterministic mesh IP: vpsN -> 10.99.0.N (plan §C / bootstrap-vps.sh:110)."""
    return f"{MESH_SUBNET_PREFIX}.{spoke_number(name)}"


def next_free_spoke(client: VultrClient) -> str:
    """Lowest free vpsN (>=2) not in active local state nor a live Vultr label.

    bootstrap-vps.sh preflight does the authoritative wg0 collision check, so this
    is a convenience picker; a race still fails safe at bootstrap.
    """
    used: set[int] = set()
    for name, rec in vultr_state.active_instances().items():
        sn = rec.get("spoke_name") or name
        m = SPOKE_NAME_RE.match(sn)
        if m:
            used.add(int(m.group(1)))
    for inst in client.list_instances():
        m = SPOKE_NAME_RE.match(inst.get("label", "") or "")
        if m:
            used.add(int(m.group(1)))
    for n in range(_MIN_SPOKE_N, _MAX_SPOKE_N + 1):
        if n not in used:
            return f"vps{n}"
    raise VultrError("no free spoke number in 10.99.0.0/24")


def _run_script(argv: list[str], timeout: int, log_path) -> int:
    try:
        with open(log_path, "w") as log:
            r = subprocess.run(
                argv, stdout=log, stderr=subprocess.STDOUT, timeout=timeout, check=False
            )
        return r.returncode
    except subprocess.TimeoutExpired:
        return 124
    except OSError as e:
        logger.error("provision: failed to run %s: %s", argv, e)
        return 127


def provision(
    name: str,
    *,
    sshkey_ids: list[str],
    region: str,
    plan: str = "vc2-2c-4gb",
    confirm: bool = False,
    dry_run: bool = False,
    client: VultrClient | None = None,
) -> dict[str, Any]:
    """Provision a permanent spoke. Returns a report. Requires ``confirm=True`` to run."""
    n = spoke_number(name)
    mesh_ip = mesh_ip_for(name)
    client = client or VultrClient()

    # collision check (local + live)
    if name in vultr_state.active_instances():
        raise VultrError(f"{name} already tracked as active in state")
    for inst in client.list_instances():
        if (inst.get("label") or "") == name:
            raise VultrError(f"{name} already exists live on Vultr (id={inst.get('id')})")

    steps = [
        "create instance",
        "wait active + ssh",
        f"bootstrap-vps.sh root@<ip> {name} (full)",
        "mesh peer reg (bootstrap step_06)",
        "DNS (bootstrap step_13)",
        "monitoring agents (bootstrap step_11)",
        "record state mode=permanent",
    ]
    if dry_run:
        return {
            "dry_run": True,
            "name": name,
            "spoke_number": n,
            "mesh_ip": mesh_ip,
            "region": region,
            "plan": plan,
            "steps": steps,
        }
    if not confirm:
        raise VultrError(
            "permanent provision requires explicit confirm=True (irreversible billing)"
        )

    ts = datetime.now(UTC)
    report: dict[str, Any] = {
        "name": name,
        "spoke_number": n,
        "mesh_ip": mesh_ip,
        "region": region,
        "plan": plan,
        "vultr_id": None,
        "ip": None,
        "bootstrap_rc": None,
        "success": False,
        "error": None,
    }
    res_kind, obj = client.create_instance(
        region=region,
        plan=plan,
        hostname=name,
        label=name,
        sshkey_ids=sshkey_ids,
        tags=["fabrik", "permanent", name],
    )
    rid = obj.get("id")
    report["vultr_id"] = rid
    vultr_state.upsert_instance(
        name,
        {
            "vultr_id": rid,
            "kind": res_kind,
            "mode": "permanent",
            "region": region,
            "plan": plan,
            "created_at": ts.isoformat(),
            "mesh_ip": mesh_ip,
            "spoke_name": name,
            "bootstrap_completed_at": None,
            "destroyed_at": None,
        },
    )
    ready = client.wait_for_active(res_kind, rid, timeout=240)
    ip = ready.get("main_ip")
    report["ip"] = ip
    vultr_state.upsert_instance(name, {"ip": ip})

    script = str(BOOTSTRAP_DIR / "bootstrap-vps.sh")
    log_path = FABRIK_ROOT / "logs" / f"provision-{name}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    rc = _run_script([script, f"root@{ip}", name], _BOOTSTRAP_TIMEOUT, log_path)
    report["bootstrap_rc"] = rc
    if rc == 0:
        vultr_state.upsert_instance(name, {"bootstrap_completed_at": datetime.now(UTC).isoformat()})
        report["success"] = True
    else:
        report["error"] = (
            f"bootstrap failed (rc={rc}); instance LEFT for inspection (see {log_path}). "
            f"Fix + re-run, or `fabrik vultr destroy {name} --reverse-fleet-add`."
        )
        logger.error(report["error"])
    return report


def reverse_fleet_destroy(
    name: str,
    *,
    keep_dns: bool = False,
    dry_run: bool = False,
    client: VultrClient | None = None,
) -> dict[str, Any]:
    """Unwind a permanent spoke in reverse-of-provision order. Best-effort per step."""
    rec = vultr_state.get_instance(name)
    if not rec:
        raise VultrError(f"no tracked instance named {name!r}")
    mesh_ip = rec.get("mesh_ip") or mesh_ip_for(name)
    domain_root = f"{name}.ocoron.com"
    plan_steps = [
        f"gatus: remove aro-wake-{name} endpoint",
        f"prometheus: remove {name} scrape target",
        f"backrest: remove {name} backup plan",
        f"dns: remove *.{domain_root}" + (" (SKIPPED --keep-dns)" if keep_dns else ""),
        f"wg0: deregister peer {mesh_ip} on vps1",
        "instance: destroy",
        "state: mark destroyed",
    ]
    if dry_run:
        return {"dry_run": True, "name": name, "mesh_ip": mesh_ip, "steps": plan_steps}

    client = client or VultrClient()
    results: list[tuple[str, str]] = []

    def _try(step: str, fn) -> None:
        try:
            fn()
            results.append((step, "ok"))
        except Exception as e:  # noqa: BLE001 - best-effort teardown
            results.append((step, f"error: {e}"))
            logger.warning("reverse_fleet_destroy %s: %s failed: %s", name, step, e)

    # 1-3: monitoring/backup registrars (best-effort; import lazily)
    def _gatus():
        from fabrik.drivers.gatus import remove_endpoint

        remove_endpoint(f"aro-wake-{name}")

    _try("gatus", _gatus)

    def _prom():
        from fabrik.drivers.prometheus import remove_scrape_target

        remove_scrape_target(name)

    _try("prometheus", _prom)

    def _backrest():
        from fabrik.drivers.backrest import remove_backup_plan

        remove_backup_plan(name)

    _try("backrest", _backrest)

    # 4: DNS
    if not keep_dns:

        def _dns():
            from fabrik.drivers.dns import DNSClient

            DNSClient().delete_record("ocoron.com", "A", name)

        _try("dns", _dns)

    # 5: wg0 peer deregistration on the hub
    def _wg():
        from fabrik.drivers.ssh import ssh

        ssh(f"sudo wg set wg0 peer-remove-by-ip {mesh_ip} 2>/dev/null || true", timeout=30)

    _try("wg0-peer", _wg)

    # 6: destroy the instance
    if rec.get("vultr_id"):
        _try(
            "destroy-instance", lambda: client.destroy(rec.get("kind", "instance"), rec["vultr_id"])
        )

    # 7: state
    vultr_state.mark_destroyed(name)
    results.append(("state", "marked destroyed"))

    return {"name": name, "results": results}
