"""Disposable DR drills for ``fabrik vultr drill`` (Phases 3-4).

Creates a throwaway Vultr instance, runs a kind-specific validation, then ALWAYS
destroys it (try/finally — no orphan even on failure or Ctrl-C), and appends one
JSON line per drill to ``logs/dr-drill-history.jsonl``.

Kinds:
- ``bare``  — smallest/cheapest IPv4 instance; validates Vultr API create→active→
  destroy + best-effort SSH reachability against stock Ubuntu. ~2 min.
- ``spoke`` — runs ``bootstrap-vps.sh --skip-mesh --skip-dns root@<ip> vps4``
  (hermetic: no prod mesh/DNS touch), then ``bootstrap-vps.sh --verify`` as the
  end-state contract. ~5-15 min.
- ``hub``   — runs ``bootstrap-hub.sh`` against a DR snapshot, then verify. ~90 min;
  requires snapshot + W9 env mirror present (operator-run, quarterly).

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
from pathlib import Path
from typing import Any

from fabrik.config import FABRIK_ROOT
from fabrik.drivers.vultr import VultrClient, VultrError
from fabrik.orchestrator import vultr_state

logger = logging.getLogger(__name__)

DRILL_LOG = FABRIK_ROOT / "logs" / "dr-drill-history.jsonl"
BOOTSTRAP_DIR = FABRIK_ROOT / "scripts" / "bootstrap"
DEFAULT_REGION = "lax"  # vps1 is in LA; cheapest round-trip for drills
DISPOSABLE_TTL_HOURS = 4
_HOURS_PER_MONTH = 672  # Vultr's monthly-cap divisor

# Fixed plans for spoke/hub drills (bare uses the cheapest IPv4 plan available).
# spoke mirrors a real spoke size; hub needs ~8GB for the full restore.
SPOKE_DRILL_PLAN = "vc2-1c-2gb"
HUB_DRILL_PLAN = "vc2-4c-8gb"
DRILL_SPOKE_NAME = "vps4"  # conventionally reserved drill identity (90-bootstrap-scripts.md)
_BOOTSTRAP_TIMEOUT = 1200  # 20 min — spoke bootstrap headroom
_VERIFY_TIMEOUT = 300
_HUB_BOOTSTRAP_TIMEOUT = 5400  # 90 min


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


def _plan_monthly_cost(client: VultrClient, plan_id: str) -> float:
    for p in client.list_plans():
        if p["id"] == plan_id:
            return p["monthly_cost"]
    raise VultrError(f"plan {plan_id!r} not found")


def _resolve_plan(client: VultrClient, kind: str, region: str) -> tuple[str, float]:
    if kind == "bare":
        return cheapest_ipv4_plan(client, region)
    if kind == "spoke":
        return SPOKE_DRILL_PLAN, _plan_monthly_cost(client, SPOKE_DRILL_PLAN)
    if kind == "hub":
        return HUB_DRILL_PLAN, _plan_monthly_cost(client, HUB_DRILL_PLAN)
    raise NotImplementedError(f"unknown drill kind {kind!r}")


def _ssh_probe(ip: str, *, attempts: int = 6, interval: int = 5) -> bool:
    """Best-effort: can we SSH root@ip and run a command? Never raises."""
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


def _run_script(argv: list[str], timeout: int, log_path) -> int:
    """Run a bootstrap script, tee output to log_path, return exit code (124 on timeout)."""
    try:
        with open(log_path, "w") as log:
            r = subprocess.run(
                argv, stdout=log, stderr=subprocess.STDOUT, timeout=timeout, check=False
            )
        return r.returncode
    except subprocess.TimeoutExpired:
        return 124
    except OSError as e:
        logger.error("drill: failed to run %s: %s", argv, e)
        return 127


def _wait_ssh(ip: str, *, attempts: int = 20, interval: int = 6) -> bool:
    return _ssh_probe(ip, attempts=attempts, interval=interval)


def _ssh_ozgur_drill(ip: str, cmd: str, *, timeout: int = 60) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            "ssh",
            "-o",
            "ConnectTimeout=5",
            "-o",
            "BatchMode=yes",
            "-o",
            "StrictHostKeyChecking=accept-new",
            "-o",
            "UserKnownHostsFile=/dev/null",
            f"ozgur@{ip}",
            cmd,
        ],
        capture_output=True,
        text=True,
        timeout=timeout + 5,
        check=False,
    )


def _g0_creds_smoke(ip: str) -> dict[str, Any]:
    """Partial-G0: copy the warm local Claude creds to the throwaway drill spoke
    and run one ``claude -p`` to check the COPIED-CREDS hypothesis (plan C2 part 2).

    Catches *immediate* single-session rejection only. It explicitly does NOT
    exercise the ~4-day OAuth refresh-token rotation race — that needs a
    multi-day observation, not a seconds-long smoke. Hashes the spoke's creds
    before/after to record whether first use rotated the token. Best-effort;
    never flips the drill's bootstrap+verify ``success``.
    """
    local = Path.home() / ".claude" / ".credentials.json"
    if not local.exists():
        return {"attempted": False, "reason": "no local ~/.claude/.credentials.json to copy"}
    try:
        _ssh_ozgur_drill(ip, "mkdir -p ~/.claude && chmod 700 ~/.claude")
        scp = subprocess.run(
            [
                "scp",
                "-q",
                "-o",
                "BatchMode=yes",
                "-o",
                "StrictHostKeyChecking=accept-new",
                "-o",
                "UserKnownHostsFile=/dev/null",
                str(local),
                f"ozgur@{ip}:.claude/.credentials.json",
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if scp.returncode != 0:
            return {"attempted": True, "pass": False, "reason": f"scp failed (rc={scp.returncode})"}
        _ssh_ozgur_drill(ip, "chmod 600 ~/.claude/.credentials.json")
        before = _ssh_ozgur_drill(ip, "sha256sum ~/.claude/.credentials.json").stdout.split()[:1]
        # exit code of claude -p is the immediate-auth signal
        rc = _ssh_ozgur_drill(ip, "claude -p ok >/dev/null 2>&1; echo RC=$?", timeout=120)
        claude_rc = next((int(t[3:]) for t in rc.stdout.split() if t.startswith("RC=")), 127)
        after = _ssh_ozgur_drill(ip, "sha256sum ~/.claude/.credentials.json").stdout.split()[:1]
        return {
            "attempted": True,
            "claude_p_rc": claude_rc,
            "immediate_auth_ok": claude_rc == 0,
            "spoke_creds_rotated_on_first_use": before != after,
            "pass": claude_rc == 0,
            "note": (
                "immediate single-session check only; the ~4-day refresh-token "
                "rotation race is NOT exercised here"
            ),
        }
    except (subprocess.TimeoutExpired, OSError) as e:
        return {"attempted": True, "pass": False, "reason": f"smoke error: {e}"}


def _validate_spoke(ip: str, name: str, *, g0_smoke: bool = False) -> dict[str, Any]:
    """Run bootstrap-vps.sh hermetically (--skip-mesh --skip-dns), then --verify."""
    script = str(BOOTSTRAP_DIR / "bootstrap-vps.sh")
    boot_log = FABRIK_ROOT / "logs" / f"drill-{name}.bootstrap.log"
    verify_log = FABRIK_ROOT / "logs" / f"drill-{name}.verify.log"
    checks: dict[str, Any] = {}
    checks["ssh_ready"] = _wait_ssh(ip)
    boot_rc = _run_script(
        [script, "--skip-mesh", "--skip-dns", f"root@{ip}", DRILL_SPOKE_NAME],
        _BOOTSTRAP_TIMEOUT,
        boot_log,
    )
    checks["bootstrap_rc"] = boot_rc
    checks["bootstrap"] = boot_rc == 0
    if boot_rc == 0:
        # step_01 disabled root login -> verify as the ozgur sudoer
        verify_rc = _run_script(
            [script, "--verify", f"ozgur@{ip}", DRILL_SPOKE_NAME], _VERIFY_TIMEOUT, verify_log
        )
        checks["verify_rc"] = verify_rc
        checks["verify"] = verify_rc == 0
        # Opt-in partial-G0 diagnostic — does NOT affect bootstrap+verify success.
        if g0_smoke and verify_rc == 0:
            checks["g0_smoke"] = _g0_creds_smoke(ip)
    checks["success"] = checks.get("bootstrap") and checks.get("verify", False)
    return checks


def _validate_hub(ip: str, name: str) -> dict[str, Any]:
    """Run bootstrap-hub.sh against the latest DR snapshot, then --verify.

    Drill safety contract — these flags are MANDATORY here and are why the
    drill cannot break the live mesh even though the droplet restores
    vps1's real private key:

    - ``--skip-mesh``: skips step_08 ``wg-quick@wg0`` bring-up. Without
      this, the drill droplet would handshake with vps2/vps3 using the
      restored vps1 keypair and the spokes would update their peer
      endpoint to point at the drill droplet's public IP — breaking the
      live vps1↔spoke mesh until the drill is destroyed.
    - ``--skip-services``: stops after step_12 (after the restic restores
      complete). Skips step_13 (compose-up — backrest container would
      start writing to B2 with vps1's restic identity), step_15
      (vps-sysadmin-bot enable — would Telegram from the drill), step_17
      (Cloudflare DNS rewrite — flag-gated default-off anyway).

    What the drill DOES measure with these guards: bootstrap-hub.sh
    steps 00-07 + iptables-docker-user.service path + step_09 +
    step_10 + the big restic pulls (host-state, opt-configs,
    docker-volumes). That's the slow part of the 90-min target — and
    the part where unknown-unknown bugs would surface.
    """
    script = str(BOOTSTRAP_DIR / "bootstrap-hub.sh")
    boot_log = FABRIK_ROOT / "logs" / f"drill-{name}.bootstrap.log"
    checks: dict[str, Any] = {"ssh_ready": _wait_ssh(ip)}
    boot_rc = _run_script(
        [script, "--skip-mesh", "--skip-services", f"root@{ip}"],
        _HUB_BOOTSTRAP_TIMEOUT,
        boot_log,
    )
    checks["bootstrap_rc"] = boot_rc
    checks["bootstrap"] = boot_rc == 0
    checks["success"] = checks["bootstrap"]
    return checks


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
    g0_smoke: bool = False,
    client: VultrClient | None = None,
) -> dict[str, Any]:
    """Run a disposable drill of ``kind`` (bare|spoke|hub). Returns the report dict.

    The instance is ALWAYS destroyed unless the drill failed AND ``keep_on_failure``
    is set (then it's left running for the operator to inspect).
    """
    if kind not in ("bare", "spoke", "hub"):
        raise NotImplementedError(f"unknown drill kind {kind!r}")

    client = client or VultrClient()
    plan, monthly = _resolve_plan(client, kind, region)
    # cost horizon: bare ~ TTL; spoke ~1h; hub ~2h
    horizon_s = {"bare": DISPOSABLE_TTL_HOURS * 3600, "spoke": 3600, "hub": 2 * 3600}[kind]
    est = estimate_cost(monthly, horizon_s)
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
        if kind == "bare":
            report["checks"]["ssh_reachable"] = _ssh_probe(ip) if ip else False
            report["success"] = bool(report["checks"]["ssh_reachable"])
        elif kind == "spoke":
            sc = _validate_spoke(ip, name, g0_smoke=g0_smoke)
            report["checks"].update(sc)
            report["success"] = bool(sc.get("success"))
        else:  # hub
            hc = _validate_hub(ip, name)
            report["checks"].update(hc)
            report["success"] = bool(hc.get("success"))
        report["step_durations"]["validate"] = round(time.monotonic() - t1, 1)
    except Exception as e:  # noqa: BLE001 - report every failure, then clean up
        failed = True
        report["error"] = str(e)
        logger.warning("drill %s failed: %s", name, e)
    finally:
        report["wall_clock_seconds"] = round(time.monotonic() - start, 1)
        keep = (failed or not report["success"]) and keep_on_failure
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
