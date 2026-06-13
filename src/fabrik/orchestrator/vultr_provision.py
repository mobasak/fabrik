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


def _wg0_used_numbers() -> set[int]:
    """Spoke numbers already on vps1's wg0 (authoritative — 10.99.0.N/32). Best-effort:
    existing real spokes (vps2/vps3) live here even if they predate this tool's state."""
    used: set[int] = set()
    try:
        from fabrik.drivers.ssh import ssh

        out = ssh("sudo wg show wg0 allowed-ips 2>/dev/null || true", timeout=20)
        for m in re.finditer(r"10\.99\.0\.(\d+)/32", out):
            used.add(int(m.group(1)))
    except Exception as e:  # noqa: BLE001 - best-effort; bootstrap preflight is authoritative
        logger.warning("next_free_spoke: could not read vps1 wg0 (%s); using state+live only", e)
    return used


def next_free_spoke(client: VultrClient) -> str:
    """Lowest free vpsN (>=2) not on vps1's wg0, in active local state, or a live Vultr label.

    Consults vps1's wg0 so it doesn't collide with existing real spokes (vps2/vps3) that
    predate this tool's state file. bootstrap-vps.sh preflight is the authoritative check;
    a race still fails safe at bootstrap.
    """
    used: set[int] = _wg0_used_numbers()
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


def _wait_for_ssh(ip: str, *, timeout: int = 120, interval: int = 5) -> bool:
    """Poll the new VPS until sshd accepts a BatchMode probe or timeout.

    Bridges the gap between Vultr-API "active" and cloud-init-finished sshd.
    Uses the same BatchMode probe that bootstrap-vps.sh's preflight uses so
    a passing probe here guarantees the bootstrap script's preflight will
    also pass (assuming no fail2ban race).
    """
    import time as _time

    deadline = _time.monotonic() + timeout
    attempt = 0
    while _time.monotonic() < deadline:
        attempt += 1
        try:
            r = subprocess.run(
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
                    f"root@{ip}",
                    "echo ok",
                ],
                capture_output=True,
                timeout=10,
                check=False,
            )
            if r.returncode == 0 and b"ok" in r.stdout:
                logger.info("ssh-ready: root@%s reachable after %d attempts", ip, attempt)
                return True
        except subprocess.TimeoutExpired:
            pass
        _time.sleep(interval)
    logger.error("ssh-ready: root@%s NOT reachable within %ds (%d attempts)", ip, timeout, attempt)
    return False


def _probe_ozgur_works(ip: str, *, timeout: int = 10) -> bool:
    """SAFE-RERUN-TRAP signal probe: does ``ozgur@<ip> 'sudo -n id'`` succeed?

    Mirrors the exact check `bootstrap-vps.sh`'s `preflight()` does after
    a `root@<ip>` failure (see `scripts/bootstrap/bootstrap-vps.sh:198-217`
    SAFE-RERUN-TRAP block + `.windsurf/rules/core/90-bootstrap-scripts.md`
    Rule 1). When this returns True AND `root@<ip>` BatchMode SSH fails,
    that's the unambiguous signal that step_00 + step_01 already ran on
    this VPS (sudoer exists with NOPASSWD, root login disabled) — the
    bootstrap can be safely re-invoked as `ozgur@<ip>` instead of failing
    to "left for inspection".

    The probe itself is `sudo -n id` (not just `id`) so that we only
    return True when the user can ALSO get root non-interactively — which
    is what bootstrap-vps.sh needs to run its sudo'd steps.
    """
    try:
        r = subprocess.run(
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
                "sudo -n id",
            ],
            capture_output=True,
            timeout=timeout,
            check=False,
        )
        return r.returncode == 0 and b"uid=0" in r.stdout
    except (subprocess.TimeoutExpired, OSError):
        return False


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

    # Wait for sshd to actually accept connections.
    # `wait_for_active`'s 4-condition status check returns when Vultr's API
    # reports the instance as active+running+ok+ip-assigned, but there's
    # usually a 10-30s gap before cloud-init finishes binding sshd.
    # Without this, bootstrap-vps.sh's preflight hits "cannot SSH" on the
    # first attempt — verified live 2026-06-08 against vps4 provisioning.
    if not _wait_for_ssh(ip, timeout=120):
        report["error"] = (
            f"sshd never came up on {ip} within 120s after Vultr reported active. "
            f"Instance LEFT for inspection — destroy with "
            f"`fabrik vultr destroy {name} --reverse-fleet-add`."
        )
        logger.error(report["error"])
        return report

    script = str(BOOTSTRAP_DIR / "bootstrap-vps.sh")
    log_path = FABRIK_ROOT / "logs" / f"provision-{name}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    rc = _run_script([script, f"root@{ip}", name], _BOOTSTRAP_TIMEOUT, log_path)
    report["bootstrap_rc"] = rc

    # G6: SAFE-RERUN-TRAP auto-retry as ozgur@.
    # When the first bootstrap pass dies AFTER step_01 has already
    # disabled root SSH login (e.g. mid-step crash, network blip,
    # step_02 SSH session drop pre-fix), re-invoking as `root@<ip>` will
    # fail at the preflight's BatchMode SSH probe and trip fail2ban.
    # Bootstrap-vps.sh's preflight detects this case and exits with rc=1
    # plus an actionable message — but that's for humans. Automation key
    # off the same signal: if ozgur@<ip> can `sudo -n id` AND
    # root@<ip> is now broken, step_00+step_01 ran, the bootstrap is
    # idempotent step-by-step, and we can safely resume as the sudoer.
    if rc != 0 and _probe_ozgur_works(ip):
        logger.warning(
            "bootstrap rc=%d as root@%s but ozgur@%s 'sudo -n id' works "
            "(SAFE-RERUN-TRAP signal — step_01 already disabled root SSH). "
            "Re-invoking bootstrap as ozgur@%s to resume idempotently.",
            rc,
            ip,
            ip,
            ip,
        )
        rc = _run_script([script, f"ozgur@{ip}", name], _BOOTSTRAP_TIMEOUT, log_path)
        report["bootstrap_rc"] = rc
        report["bootstrap_retry_as_ozgur"] = True

    if rc == 0:
        vultr_state.upsert_instance(name, {"bootstrap_completed_at": datetime.now(UTC).isoformat()})
        report["success"] = True
        # Register the spoke with hub observability — symmetric with the
        # `reverse_fleet_destroy` unwind (gatus + prometheus removal both
        # already wired in). Without these, a provisioned spoke ships logs
        # to Loki (bootstrap step_11) but is invisible to Prometheus +
        # Gatus. Verified live during the vps4 drill 2026-06-08: 14 active
        # Prometheus targets before + after provision until this landed.
        # Best-effort: any failure here is logged but does NOT fail the
        # provision report — the box is up + mesh + DNS + bootstrap all
        # succeeded; observability registration can be re-driven.
        _register_observability(name, mesh_ip, report)
        # PR3: auto-install the spoke's AI sysadmin (token from pool, enable
        # units, verify). Best-effort — never fails the up-and-bootstrapped box.
        _provision_sysadmin(name, ip, mesh_ip, report)
    else:
        report["error"] = (
            f"bootstrap failed (rc={rc}); instance LEFT for inspection (see {log_path}). "
            f"Fix + re-run, or `fabrik vultr destroy {name} --reverse-fleet-add`."
        )
        logger.error(report["error"])
    return report


def _register_observability(name: str, mesh_ip: str, report: dict[str, Any]) -> None:
    """Wire a freshly-provisioned spoke into Prometheus + Gatus.

    Each step is best-effort; failures land under ``report['observability']``
    instead of bubbling up. SIGHUPs happen inside the driver helpers.
    """
    obs: dict[str, str] = {}
    try:
        from fabrik.drivers.prometheus import add_aro_wake_target

        r = add_aro_wake_target(name, mesh_ip)
        obs["prometheus"] = r.get("status", "?")
    except Exception as e:  # noqa: BLE001 — best-effort post-deploy registration
        obs["prometheus"] = f"error: {e}"
        logger.warning("prometheus aro-wake register %s failed: %s", name, e)

    try:
        from fabrik.drivers.gatus import add_aro_wake_endpoint

        r = add_aro_wake_endpoint(name, mesh_ip)
        obs["gatus"] = r.get("status", "?")
    except Exception as e:  # noqa: BLE001
        obs["gatus"] = f"error: {e}"
        logger.warning("gatus aro-wake register %s failed: %s", name, e)

    report["observability"] = obs


# ── PR3: spoke AI-sysadmin auto-provision ──────────────────────────────────

ARO_WAKE_HEALTH_PORT = 8201  # mesh-facing; the bot's own health is 8017 (loopback)


def _ssh_ozgur(ip: str, remote_cmd: str, *, timeout: int = 30) -> subprocess.CompletedProcess:
    """Run a command on the bootstrapped spoke as ``ozgur@<ip>`` (root login is
    disabled by bootstrap step_01, so post-bootstrap access is the sudoer)."""
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
            remote_cmd,
        ],
        capture_output=True,
        timeout=timeout,
        check=False,
    )


def _local_env_sysadmin() -> dict[str, str]:
    """Fleet-uniform sysadmin values from the local ``.env.sysadmin`` (the host
    running provision is a fleet member — vps1). ``{}`` if absent."""
    path = FABRIK_ROOT / ".env.sysadmin"
    if not path.exists():
        return {}
    out: dict[str, str] = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        out[k.strip()] = v.strip()
    return out


def _check_aro_wake_health(mesh_ip: str, *, timeout: int = 10, attempts: int = 3) -> str:
    """Bounded health probe of the spoke's aro-wake from this host (works on the
    mesh, e.g. the hub). Never hangs (``--max-time``); annotates if off-mesh.

    Retries a few times because the probe fires immediately after
    ``systemctl enable --now`` — aro-wake needs ~1-2s to bind its socket, and a
    single connection-refused in that window would wrongly report a healthy box
    as ``unhealthy`` and send the operator chasing a non-issue.
    """
    import time as _time

    url = f"http://{mesh_ip}:{ARO_WAKE_HEALTH_PORT}/health"
    last = "no-response"
    for attempt in range(attempts):
        try:
            r = subprocess.run(
                [
                    "curl",
                    "-s",
                    "-o",
                    "/dev/null",
                    "-w",
                    "%{http_code}",
                    "--max-time",
                    str(timeout),
                    url,
                ],
                capture_output=True,
                text=True,
                timeout=timeout + 5,
                check=False,
            )
            code = (r.stdout or "").strip()
            if code == "200":
                return "200"
            last = f"http={code or 'no-response'}"
        except (subprocess.TimeoutExpired, OSError) as e:
            last = str(e)
        if attempt < attempts - 1:
            _time.sleep(3)
    return f"unhealthy ({last}) after {attempts} tries — verify from a mesh host: curl {url}"


def _check_bot_token(token: str, *, timeout: int = 10) -> str:
    """Validate the Telegram bot token via getMe (no message sent). The token is
    never logged or returned — only the boolean result is surfaced."""
    try:
        r = subprocess.run(
            [
                "curl",
                "-s",
                "--max-time",
                str(timeout),
                f"https://api.telegram.org/bot{token}/getMe",
            ],
            capture_output=True,
            text=True,
            timeout=timeout + 5,
            check=False,
        )
        import json as _json

        ok = _json.loads(r.stdout or "{}").get("ok") is True
        return "valid" if ok else "invalid (getMe ok!=true)"
    except (subprocess.TimeoutExpired, OSError, ValueError):
        return "unverified (getMe call failed)"


def _provision_sysadmin(name: str, ip: str, mesh_ip: str, report: dict[str, Any]) -> None:
    """Auto-install the spoke's AI sysadmin (PR3). Best-effort: failures land in
    ``report['sysadmin']`` and never fail the provision (the box is already up,
    mesh+DNS+bootstrap all succeeded). Reduces the post-bootstrap manual finish
    from 5 steps to 1 (the operator's one remaining action is the Claude
    device-flow). Constraint C2: NO creds are copied — device-flow stays manual.
    """
    from fabrik.orchestrator import sysadmin_tokens

    sysd: dict[str, str] = {}
    report["sysadmin"] = sysd

    env = _local_env_sysadmin()
    owner = env.get("TELEGRAM_OWNER_ID", "")
    orkey = env.get("WATCHDOG_OPENROUTER_KEY", "")
    have_owner = bool(owner) and "__OPERATOR" not in owner

    # C4: an empty/exhausted pool returns None — we then SKIP enabling the bot
    # rather than write the placeholder token (which crash-loops bot.py into
    # StartLimitBurst). Same if the fleet-uniform owner ID isn't resolvable.
    # ``bot_skip_reason`` distinguishes the three skip causes (no token / no
    # owner / write failed) so the operator message points at the real fix
    # rather than misattributing a failed write to a missing token.
    tok = sysadmin_tokens.claim_bot_token(name)
    if not tok:
        bot_skip_reason: str | None = "token pool empty/exhausted"
    elif not have_owner:
        bot_skip_reason = "fleet TELEGRAM_OWNER_ID unresolved"
    else:
        bot_skip_reason = None

    if bot_skip_reason is None:
        # Edit the spoke's already-rendered .env.sysadmin in place (bootstrap
        # step_14 wrote it with placeholders + correct host identity). Values
        # contain no '|' or quotes, so single-quoted sed exprs are Rule-2 safe.
        seds = (
            f"-e 's|^TELEGRAM_BOT_TOKEN=.*|TELEGRAM_BOT_TOKEN={tok}|' "
            f"-e 's|^TELEGRAM_OWNER_ID=.*|TELEGRAM_OWNER_ID={owner}|' "
            f"-e 's|^WATCHDOG_OPENROUTER_KEY=.*|WATCHDOG_OPENROUTER_KEY={orkey}|' "
        )
        r = _ssh_ozgur(ip, f"sudo sed -i {seds} /opt/fabrik/.env.sysadmin")
        if r.returncode == 0:
            sysd["env_sysadmin"] = "written"
        else:
            sysd["env_sysadmin"] = f"error (rc={r.returncode})"
            bot_skip_reason = f".env.sysadmin write failed (rc={r.returncode})"
    else:
        sysd["env_sysadmin"] = f"skipped: {bot_skip_reason}"

    bot_enable = bot_skip_reason is None

    # Enable aro-wake always (no Claude dep); the bot only with a real token.
    units = "aro-wake.service" + (" vps-sysadmin-bot.service" if bot_enable else "")
    r = _ssh_ozgur(ip, f"sudo systemctl enable --now {units}")
    sysd["units_enabled"] = units if r.returncode == 0 else f"error (rc={r.returncode}): {units}"

    if not bot_enable:
        sysd["bot"] = (
            f"NOT enabled ({bot_skip_reason}) — resolve, then "
            f"`ssh {name} 'sudo systemctl enable --now vps-sysadmin-bot.service'`"
        )

    # Verify gate — bounded, never hangs, never hard-fails the provision.
    sysd["aro_wake_health"] = _check_aro_wake_health(mesh_ip)
    if bot_enable:
        sysd["bot_token_valid"] = _check_bot_token(tok)

    # The single remaining manual step (constraint C2 — proven-safe path).
    sysd["operator_next"] = (
        f"ssh {name} 'claude'   # one-time device-flow OAuth to unlock claude -p"
    )
    logger.info("sysadmin auto-provision for %s: %s", name, sysd)


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
        f"sysadmin: release bot-token pool slot for {name}",
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

    # 0: release the bot-token pool slot (reverse of PR3's last provision step —
    # so a destroyed/rebuilt spoke frees its token for the next provision).
    def _sysadmin_token():
        from fabrik.orchestrator import sysadmin_tokens

        sysadmin_tokens.release_bot_token(name)

    _try("sysadmin token", _sysadmin_token)

    # 1-3: monitoring/backup registrars (best-effort; import lazily)
    def _gatus():
        from fabrik.drivers.gatus import remove_endpoint

        remove_endpoint(f"aro-wake-{name}")

    _try("gatus", _gatus)

    def _prom():
        # Use the aro-wake-target remover, NOT the general
        # `remove_scrape_target` (which only handles `fabrik-<name>` jobs).
        # `add_aro_wake_target` in provision() registers the spoke inside
        # the shared `aro-wake` job's `static_configs` list — that's what
        # we need to undo here. The old call path was symmetric-looking
        # but a no-op in practice (no `fabrik-vps4` job ever got created).
        from fabrik.drivers.prometheus import remove_aro_wake_target

        remove_aro_wake_target(name)

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

    # 5: wg0 peer deregistration on the hub — runtime removal + persistence.
    # `wg set <iface> peer <pubkey> remove` is the only valid removal syntax —
    # `peer-remove-by-ip` does NOT exist (silently fails under `|| true`,
    # leaving a stale peer behind — verified live 2026-06-08 against vps4).
    # The runtime remove alone is NOT enough: vps1's wg0.conf still carries
    # the `[Peer]` block, so a vps1 reboot restores the stale peer (verified
    # live 2026-06-08 — vps4's marker block was still on disk after a
    # "successful" destroy until manual cleanup).
    #
    # IMPORTANT: do NOT use `wg-quick save wg0` — it round-trips through
    # `wg showconf`, which omits wg-quick extensions (`Address`, `MTU`,
    # `PostUp`, `PostDown`). vps1's `PostUp` carries the MSS-clamp rule
    # that keeps cross-Atlantic mesh TCP from fragmenting; losing it would
    # be a mesh regression for the whole fleet.
    #
    # So: targeted block removal keyed on the marker comment step_06 writes
    #     `# === peer: <SPOKE_NAME> (added <ISO timestamp>) ===`
    # Delete from that marker line through end-of-next-marker-or-EOF.
    # Preserves [Interface] + every other peer block exactly.
    def _wg():
        from fabrik.drivers.ssh import ssh

        # 5a — runtime remove via pubkey lookup
        pubkey = ssh(
            f"sudo wg show wg0 allowed-ips | awk '/[^0-9]{mesh_ip}\\//{{print $1; exit}}'",
            timeout=30,
        ).strip()
        if pubkey:
            ssh(f"sudo wg set wg0 peer {pubkey} remove", timeout=30)
        else:
            logger.info(
                "wg0-peer: no peer with allowed-ip %s — nothing to remove at runtime", mesh_ip
            )

        # 5b — strip the [Peer] block from /etc/wireguard/wg0.conf so the
        # change survives a hub reboot. Mirror step_06's regex pattern.
        # Exit-code is the contract; diagnostic messages go to stderr so the
        # main process logger surfaces them but stdout stays empty.
        ssh(
            f'sudo python3 -c "\n'
            f"import re, sys\n"
            f"path = '/etc/wireguard/wg0.conf'\n"
            f"with open(path) as f: c = f.read()\n"
            f"marker = '# === peer: {name} '\n"
            f"if marker not in c:\n"
            f"    sys.stderr.write('no marker for {name} — already clean\\n')\n"
            f"    raise SystemExit(0)\n"
            f"pattern = r'\\n# === peer: {name} .*?(?=\\n# === peer:|\\Z)'\n"
            f"c2 = re.sub(pattern, '', c, flags=re.DOTALL)\n"
            f"if c2 == c:\n"
            f"    sys.stderr.write('marker matched but regex removed nothing — refusing to write\\n')\n"
            f"    raise SystemExit(1)\n"
            # Ensure the file always ends with a single newline. The regex
            # boundary is `\\Z` (end-of-string), so removing the last
            # [Peer] block leaves the file with no trailing newline —
            # cosmetically off and breaks `wc -l` / diff comparisons.
            # Verified live 2026-06-08 on vps1's wg0.conf after the first
            # production G3 strip: file ended with `\\ No newline at end
            # of file` per diff output.
            f"if not c2.endswith('\\n'): c2 += '\\n'\n"
            f"with open(path, 'w') as f: f.write(c2)\n"
            f"sys.stderr.write('removed [Peer] block for {name}\\n')\n"
            f'"',
            timeout=30,
        )

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
