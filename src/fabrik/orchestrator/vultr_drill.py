"""Disposable DR drills for ``fabrik vultr drill`` (Phase 3).

Creates a throwaway Vultr instance, runs a kind-specific validation, then ALWAYS
destroys it (try/finally — no orphan even on failure or Ctrl-C), and appends one
JSON line per drill to ``logs/dr-drill-history.jsonl``.

Phase 3a implements ``bare`` — the smallest/cheapest instance, validating the
Vultr API create→active→destroy plumbing + (best-effort) SSH reachability against
stock Ubuntu. ``spoke``/``hub`` (which invoke the bootstrap scripts) are Phase 3b/4.

Cost: Vultr bills hourly, capped monthly → ``hourly = monthly_cost / 672``; a drill
is rounded up to a whole hour for the estimate (Vultr's minimum billing increment).
"""

from __future__ import annotations

import json
import logging
import math
import subprocess
import time
from datetime import UTC, datetime, timedelta
from typing import Any

from fabrik.config import FABRIK_ROOT
from fabrik.drivers.vultr import VultrClient, VultrError
from fabrik.orchestrator import vultr_state

logger = logging.getLogger(__name__)

DRILL_LOG = FABRIK_ROOT / "logs" / "dr-drill-history.jsonl"
DEFAULT_REGION = "lax"  # vps1 is in LA; cheapest round-trip for drills
DISPOSABLE_TTL_HOURS = 4
_HOURS_PER_MONTH = 672  # Vultr's monthly-cap divisor


def estimate_cost(monthly_cost: float, seconds: float) -> float:
    """Hourly-billed, min 1h, rounded up to the whole hour."""
    hours = max(1, math.ceil(seconds / 3600))
    return round(monthly_cost / _HOURS_PER_MONTH * hours, 4)


def cheapest_ipv4_plan(
    client: VultrClient, region: str, plan_type: str = "vc2"
) -> tuple[str, float]:
    """Cheapest plan of ``plan_type`` available in ``region`` that has IPv4 (not ``*-v6``)."""
    cand = [
        p
        for p in client.list_plans(plan_type)
        if region in p.get("locations", []) and not p["id"].endswith("-v6")
    ]
    if not cand:
        raise VultrError(f"no {plan_type} IPv4 plan available in region {region!r}")
    cand.sort(key=lambda p: p["monthly_cost"])
    return cand[0]["id"], cand[0]["monthly_cost"]


def _ssh_probe(ip: str, *, attempts: int = 6, interval: int = 5) -> bool:
    """Best-effort: can we SSH root@ip and run a command? Records reachability;
    never raises (a fresh droplet's key may not match the local private key)."""
    for _ in range(attempts):
        try:
            r = subprocess.run(
                [
                    "ssh",
                    "-o",
                    "BatchMode=yes",
                    "-o",
                    "StrictHostKeyChecking=no",
                    "-o",
                    "UserKnownHostsFile=/dev/null",
                    "-o",
                    "ConnectTimeout=8",
                    f"root@{ip}",
                    "echo ok",
                ],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
            if r.returncode == 0 and "ok" in r.stdout:
                return True
        except (subprocess.TimeoutExpired, OSError):
            pass
        time.sleep(interval)
    return False


def write_report(report: dict[str, Any]) -> None:
    """Append one JSON line to the drill history (best-effort)."""
    try:
        DRILL_LOG.parent.mkdir(parents=True, exist_ok=True)
        with DRILL_LOG.open("a") as f:
            f.write(json.dumps(report, sort_keys=True) + "\n")
    except OSError as e:  # pragma: no cover - logging only
        logger.warning("drill: could not write report: %s", e)


def drill(
    kind: str,
    *,
    sshkey_ids: list[str],
    region: str = DEFAULT_REGION,
    dry_run: bool = False,
    keep_on_failure: bool = False,
    max_cost: float | None = None,
    client: VultrClient | None = None,
) -> dict[str, Any]:
    """Run a disposable drill of ``kind``. Returns the drill report dict.

    ``bare`` is implemented in Phase 3a. The instance is ALWAYS destroyed unless
    the drill failed AND ``keep_on_failure`` is set (then it's left for the operator).
    """
    if kind != "bare":
        raise NotImplementedError(f"drill kind {kind!r} not implemented yet (Phase 3b/4)")

    client = client or VultrClient()
    plan, monthly = cheapest_ipv4_plan(client, region)
    est = estimate_cost(monthly, DISPOSABLE_TTL_HOURS * 3600)
    if max_cost is not None and est > max_cost:
        raise VultrError(f"estimated cost ${est} exceeds --max-cost ${max_cost} (plan {plan})")

    ts = datetime.now(UTC)
    name = f"dr-drill-{kind}-{ts.strftime('%Y%m%d-%H%M%S')}"

    if dry_run:
        return {
            "dry_run": True,
            "kind": kind,
            "region": region,
            "plan": plan,
            "monthly_cost": monthly,
            "cost_estimate_usd": est,
            "name": name,
        }

    report: dict[str, Any] = {
        "ts": int(ts.timestamp()),
        "drill_kind": kind,
        "name": name,
        "region": region,
        "plan": plan,
        "vultr_id": None,
        "success": False,
        "cost_estimate_usd": est,
        "wall_clock_seconds": 0,
        "step_durations": {},
        "checks": {},
        "error": None,
    }
    rid: str | None = None
    res_kind = "instance"
    start = time.monotonic()
    failed = False
    try:
        res_kind, obj = client.create_instance(
            region=region,
            plan=plan,
            hostname=name,
            label=name,
            sshkey_ids=sshkey_ids,
            tags=["fabrik-drill", "disposable"],
        )
        rid = obj.get("id")
        report["vultr_id"] = rid
        vultr_state.upsert_instance(
            name,
            {
                "vultr_id": rid,
                "kind": res_kind,
                "mode": "disposable",
                "region": region,
                "plan": plan,
                "created_at": ts.isoformat(),
                "destroy_after": (ts + timedelta(hours=DISPOSABLE_TTL_HOURS)).isoformat(),
                "drill_kind": kind,
                "destroyed_at": None,
            },
        )
        t0 = time.monotonic()
        ready = client.wait_for_active(res_kind, rid, timeout=180)
        report["step_durations"]["provision_to_ready"] = round(time.monotonic() - t0, 1)
        ip = ready.get("main_ip")
        report["checks"]["active"] = True
        t1 = time.monotonic()
        report["checks"]["ssh_reachable"] = _ssh_probe(ip) if ip else False
        report["step_durations"]["ssh_probe"] = round(time.monotonic() - t1, 1)
        report["success"] = True
    except Exception as e:  # noqa: BLE001 - report every failure, then clean up
        failed = True
        report["error"] = str(e)
        logger.warning("drill %s failed: %s", name, e)
    finally:
        report["wall_clock_seconds"] = round(time.monotonic() - start, 1)
        keep = failed and keep_on_failure
        if rid and not keep:
            try:
                client.destroy(res_kind, rid)
                vultr_state.mark_destroyed(name)
                report["checks"]["destroyed"] = True
            except Exception as e:  # noqa: BLE001
                report["checks"]["destroyed"] = False
                report["error"] = (report["error"] or "") + f" | destroy failed: {e}"
                logger.error("drill %s: DESTROY FAILED for %s — manual cleanup needed", name, rid)
        elif keep:
            report["checks"]["kept_for_debug"] = True
        write_report(report)

    return report
