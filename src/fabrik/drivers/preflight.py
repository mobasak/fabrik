"""Pre-deploy checks run by ``fabrik apply`` before any mutating step.

Four independent, composable checks; the first three correspond to Critical Success
Factors §1, §2, and §4 in ``docs/development/plans/2026-04-18-zero-touch-deployment.md``:

* :func:`verify_architecture` — asserts every service in a compose YAML
  declares ``platform: linux/amd64`` (CSF §4). Pure, no side effects,
  runs before DNS and before Coolify is touched. Fail-fast on spec bugs.
* :func:`verify_dns_before_deployment` — asserts a FQDN resolves to the
  expected VPS IP from both the VPS itself (``getent hosts``) and the
  public internet (``dig +short @1.1.1.1``) within a timeout (CSF §2).
  DNS propagation is never instantaneous; this replaces the old
  "sleep(2) and hope" pattern with deterministic polling.
* :func:`restart_traefik_and_wait` — restarts the Traefik container and
  polls the Traefik API on ``127.0.0.1:8080`` via SSH until it returns
  200 (CSF §1). Replaces the blind ``time.sleep(5)`` from the plan's
  example with an evidence-based wait.
* :func:`verify_host_reachable` — one bounded ``ssh <alias> true`` probe run
  by ``fabrik apply`` before anything touches the fleet (W-2b657bee); a dead path
  raises :class:`HostUnreachableError` naming the alias, the dead leg and the fix
  instead of hanging each later call to its own timeout.

Design notes
------------
* Every function uses :func:`fabrik.drivers.ssh.ssh` for VPS-side work
  and the local ``subprocess`` module for local checks, mirroring the
  pattern established in :mod:`fabrik.drivers.ssh` and
  :mod:`fabrik.drivers.locks`.
* The DNS and Traefik checks accept ``dry_run: bool`` to return early without
  touching the VPS, matching the ``--dry-run`` contract of ``fabrik apply``;
  :func:`verify_host_reachable` has none — the orchestrator skips it on a dry run.
* No side effects other than what is named in the function name.
  :func:`verify_architecture` and :func:`verify_dns_before_deployment`
  are read-only; only :func:`restart_traefik_and_wait` mutates VPS state.
"""

from __future__ import annotations

import logging
import re
import subprocess
import time

import yaml

from fabrik.drivers.ssh import (
    JumpConfigError,
    _ssh_host,
    is_alias,
    jump_env_name,
    jump_for,
    parse_hop,
    ssh,
)

logger = logging.getLogger(__name__)

DEFAULT_VPS_IP = "172.93.160.197"
"""The Fabrik VPS public IPv4. Overridable via the ``expected_ip`` argument."""

PUBLIC_DNS_RESOLVER = "1.1.1.1"
"""Cloudflare public resolver, used for out-of-band DNS propagation checks."""

TRAEFIK_API_LOCAL_URL = "http://127.0.0.1:8080/api/http/routers"  # noqa — the VPS's own Traefik admin API, reached over SSH, never from this host
"""Traefik API endpoint. Bound to VPS loopback only; reached via SSH."""


# --------------------------------------------------------------------------- #
# 1. Architecture verification                                                 #
# --------------------------------------------------------------------------- #


def verify_architecture(compose_yaml: str) -> None:
    """Assert every service in ``compose_yaml`` declares ``platform: linux/amd64``.

    The Fabrik VPS is x86_64 (AMD EPYC-Genoa). Several common base images
    (including some ``node`` and ``postgres`` tags) default to ``linux/arm64``
    on Docker Hub when pulled from an ARM host. If a compose service omits
    the ``platform`` directive and happens to be built/rendered from an ARM
    machine, Coolify will deploy an unrunnable image to the VPS. This check
    catches that class of bug before DNS is provisioned.

    Args:
        compose_yaml: Full compose YAML as a string (not a path). The caller
            is responsible for reading the file.

    Raises:
        ValueError: ``compose_yaml`` is not valid YAML or has no top-level
            ``services`` mapping.
        RuntimeError: One or more services are missing ``platform: linux/amd64``.
            The message lists the offending service names.

    Example:
        >>> compose = '''
        ... services:
        ...   app:
        ...     image: nginx
        ...     platform: linux/amd64
        ... '''
        >>> verify_architecture(compose)  # returns None
    """
    try:
        doc = yaml.safe_load(compose_yaml)
    except yaml.YAMLError as e:
        raise ValueError(f"compose_yaml is not valid YAML: {e}") from e

    if not isinstance(doc, dict):
        raise ValueError("compose_yaml must be a YAML mapping at the top level")

    services = doc.get("services")
    if not isinstance(services, dict) or not services:
        raise ValueError("compose_yaml has no 'services' mapping")

    offenders: list[str] = []
    for name, spec in services.items():
        if not isinstance(spec, dict):
            offenders.append(str(name))
            continue
        platform = spec.get("platform")
        if platform != "linux/amd64":
            offenders.append(str(name))

    if offenders:
        raise RuntimeError(
            f"Compose services missing 'platform: linux/amd64' (VPS is x86_64): {sorted(offenders)}"
        )

    logger.info("Architecture pre-flight OK: all %d service(s) declare linux/amd64", len(services))


# --------------------------------------------------------------------------- #
# 2. DNS verification                                                          #
# --------------------------------------------------------------------------- #


def _vps_resolves(fqdn: str, expected_ip: str, dry_run: bool = False) -> bool:
    """Return True if the VPS's ``getent hosts`` returns ``expected_ip`` for ``fqdn``."""
    if dry_run:
        logger.info("[DRY RUN] Would check VPS getent hosts %s == %s", fqdn, expected_ip)
        return True
    try:
        output = ssh(f"getent hosts {fqdn}", timeout=5)
    except RuntimeError:
        return False
    # getent output: "<ip>  <fqdn>"; first whitespace-separated token is the IP
    first_token = output.split()[0] if output else ""
    return first_token == expected_ip


def _public_resolves(fqdn: str, expected_ip: str, dry_run: bool = False) -> bool:
    """Return True if ``dig +short @PUBLIC_DNS_RESOLVER`` returns ``expected_ip``."""
    if dry_run:
        logger.info(
            "[DRY RUN] Would check dig +short %s @%s == %s",
            fqdn,
            PUBLIC_DNS_RESOLVER,
            expected_ip,
        )
        return True
    try:
        result = subprocess.run(
            ["dig", "+short", fqdn, f"@{PUBLIC_DNS_RESOLVER}"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return False
    if result.returncode != 0:
        return False
    # dig +short yields one IP (or CNAME chain) per line
    answers = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    return expected_ip in answers


def verify_dns_before_deployment(
    fqdn: str,
    expected_ip: str = DEFAULT_VPS_IP,
    timeout: int = 30,
    poll_interval: float = 2.0,
    dry_run: bool = False,
) -> None:
    """Block until ``fqdn`` resolves to ``expected_ip`` from both VPS and public DNS.

    Implements Critical Success Factor §2 of the zero-touch plan: DNS must
    exist *before* the Coolify deploy step, otherwise Traefik cannot route
    the new router and SSL cert generation fails. The check is performed
    from two vantage points to catch propagation lag:

    * **VPS-side** (``ssh "getent hosts"``) — what Traefik/Docker will actually
      see when attempting to route.
    * **Public-side** (``dig +short @1.1.1.1``) — what Let's Encrypt's
      HTTP-01 challenge and external health probes will see.

    Both must report the expected IP before the function returns. Polls
    every ``poll_interval`` seconds up to ``timeout`` seconds.

    Args:
        fqdn: Fully-qualified domain name to check (e.g. ``"example.vps1.ocoron.com"``).
        expected_ip: Expected A record target. Defaults to the Fabrik VPS.
        timeout: Maximum seconds to wait for propagation.
        poll_interval: Seconds between poll rounds.
        dry_run: Log the intended checks and return without running them.

    Raises:
        TimeoutError: Neither vantage reports the expected IP within ``timeout``.
            The message names which side(s) failed so the operator can
            diagnose upstream (registrar vs. VPS resolver).

    Example:
        >>> verify_dns_before_deployment("coolify.vps1.ocoron.com")  # doctest: +SKIP
    """
    if dry_run:
        logger.info("[DRY RUN] Would verify DNS for %s -> %s (VPS + public)", fqdn, expected_ip)
        return

    deadline = time.monotonic() + timeout
    last_vps: bool = False
    last_public: bool = False

    while time.monotonic() < deadline:
        last_vps = _vps_resolves(fqdn, expected_ip)
        last_public = _public_resolves(fqdn, expected_ip)
        if last_vps and last_public:
            logger.info("DNS OK: %s -> %s from both VPS and public resolver", fqdn, expected_ip)
            return
        logger.debug(
            "DNS not yet propagated (vps=%s public=%s); sleeping %.1fs",
            last_vps,
            last_public,
            poll_interval,
        )
        time.sleep(poll_interval)

    failing: list[str] = []
    if not last_vps:
        failing.append("VPS resolver")
    if not last_public:
        failing.append(f"public resolver ({PUBLIC_DNS_RESOLVER})")
    raise TimeoutError(
        f"DNS for {fqdn!r} did not resolve to {expected_ip!r} "
        f"within {timeout}s from: {', '.join(failing)}"
    )


# --------------------------------------------------------------------------- #
# 3. Traefik restart + wait                                                    #
# --------------------------------------------------------------------------- #


def _traefik_api_reachable(dry_run: bool = False) -> bool:
    """Return True if the Traefik API on ``127.0.0.1:8080`` returns HTTP 200."""
    if dry_run:
        return True
    try:
        # -f: exit non-zero on HTTP errors; -s: silent; --max-time: hard cap
        ssh(
            f"curl -fsS --max-time 3 {TRAEFIK_API_LOCAL_URL} -o /dev/null",
            timeout=5,
        )
        return True
    except RuntimeError:
        return False


def restart_traefik_and_wait(
    timeout: int = 30,
    poll_interval: float = 1.0,
    dry_run: bool = False,
) -> None:
    """Restart the Traefik container and wait for its API to come back up.

    Implements Critical Success Factor §1 of the zero-touch plan: 100%
    of the 12 completed migrations required a manual Traefik restart
    before health checks passed, because Traefik does not reliably
    auto-detect new Docker labels on running containers without a
    restart. This function replaces the plan's example ``time.sleep(5)``
    stopgap with a deterministic poll of the Traefik API.

    Args:
        timeout: Maximum seconds to wait for the Traefik API to respond
            with HTTP 200 after the restart command returns.
        poll_interval: Seconds between poll rounds.
        dry_run: Log the intended restart and return without executing.

    Raises:
        RuntimeError: ``docker restart traefik`` failed on the VPS.
        TimeoutError: The Traefik API did not respond within ``timeout``
            seconds of the restart command. The caller should treat this
            as a deploy-blocking failure — downstream health checks will
            return 404 until Traefik is up.

    Example:
        >>> restart_traefik_and_wait(timeout=60)  # doctest: +SKIP
    """
    if dry_run:
        logger.info("[DRY RUN] Would restart Traefik and poll %s", TRAEFIK_API_LOCAL_URL)
        return

    logger.info("Restarting Traefik on VPS")
    ssh("sudo docker restart traefik", timeout=30)

    deadline = time.monotonic() + timeout
    attempts = 0
    while time.monotonic() < deadline:
        attempts += 1
        if _traefik_api_reachable():
            logger.info("Traefik API reachable after %d attempt(s); restart complete", attempts)
            return
        time.sleep(poll_interval)

    raise TimeoutError(
        f"Traefik API at {TRAEFIK_API_LOCAL_URL!r} did not return HTTP 200 "
        f"within {timeout}s after restart (attempts={attempts})"
    )


# --------------------------------------------------------------------------- #
# 4. SSH reachability                                                          #
# --------------------------------------------------------------------------- #


class HostUnreachableError(RuntimeError):
    """The ssh path to a fleet alias is dead; the message names the leg and the fix."""


# stderr shapes of a NETWORK failure — only these earn the "set/check the jump" advice; a
# host-key or auth failure (also rc 255) gets "run ssh <alias> true by hand" instead.
# "connection closed" is deliberately absent: sshd also closes after an auth failure.
_NETWORK_STDERR = re.compile(
    r"timed out|banner exchange|connection refused|connection reset|no route|unreachable"
    r"|network is down|could not resolve|name or service not known",
    re.I,
)
# ssh's noise — its generic sign-off and the known_hosts addition notice; neither says why it
# failed. Every other `Warning:` line stays: one can BE the cause (a host key that differs for
# the IP, W-6a96f699) — but none counts toward the network shape, since it can name a host.
_SSH_NOISE = re.compile(r"connection (closed|to \S+ closed)|warning: permanently added", re.I)
_WARNING = re.compile(r"warning:", re.I)
_REASON_MAX = 300  # one terminal-width-ish error line; ssh's longest (a changed host key) is ~600


def _probe(argv: list[str], timeout: int) -> tuple[bool, bool, str]:
    """Run one ``ssh … true`` probe; return ``(ok, network_shaped, reason)``.

    The OUTER timeout is load-bearing: ``ConnectTimeout`` bounds the direct connect and
    handshake, but ssh never passes ``-o`` options on to a ProxyJump hop, so a hung jump
    host is bounded only here. ``stdin`` is closed so no prompt can wait for input.
    """
    try:
        r = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=timeout + 5,
            stdin=subprocess.DEVNULL,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return False, True, f"no answer in {timeout + 5}s"
    except OSError as e:
        return False, False, f"{type(e).__name__}: {e}".rstrip(".")
    if r.returncode == 0:
        return True, False, ""
    # Each line stripped of its `@` frame (the host-key banner's rules become empty, its headline
    # stays) and its trailing period; a line left empty says nothing.
    lines, headline = [], []
    for raw in (r.stderr or "").splitlines():
        text = raw.strip().strip("@").strip().rstrip(".")
        if text:
            lines.append(text)
            if raw.strip().startswith("@") and text not in headline:
                headline.append(text)
    # Every line but ssh's noise, in order — no single line is picked, because which line
    # says WHY differs by failure (a jumped refusal's cause comes first, a host-key failure's
    # last). The banner's headline leads; the rest is tail-kept when long: ssh prints the
    # failure last.
    said = [ln for ln in lines if not _SSH_NOISE.match(ln)]
    body = [ln for ln in said if ln not in headline]
    reason = "; ".join(body)
    if len(reason) > _REASON_MAX:
        reason = "…" + reason[-_REASON_MAX:]
    head = "; ".join(headline)  # a banner has one headline; never let it grow, and mark a cut
    if len(head) > _REASON_MAX:
        head = head[: _REASON_MAX - 1] + "…"
    # Nothing kept: the last line that says anything (a noise line, as before), else the exit
    # code — saying whether stderr was empty or held only `@`/`.` (it is not "no stderr" then).
    empty = "no stderr" if not (r.stderr or "").strip() else "stderr held no text"
    reason = "; ".join(part for part in (head, reason) if part) or (
        lines[-1] if lines else f"rc={r.returncode}, {empty}"
    )
    network = any(_NETWORK_STDERR.search(ln) for ln in said if not _WARNING.match(ln))
    return False, network, reason


def _batch(timeout: int) -> list[str]:
    return ["-o", "BatchMode=yes", "-o", f"ConnectTimeout={timeout}"]


def _hop_destination(hop: str) -> str:
    """The hop as an ssh destination: ``[user@]host``, or ``ssh://[user@]host:port`` when it
    carries a port — ssh reads ``host:port`` as a HOSTNAME; the URI is the form it parses."""
    parsed = parse_hop(hop)
    if parsed is None:  # unreachable: jump_for already refused it; never strip to a TypeError
        return hop
    user, host, port = parsed
    who = f"{user}@{host}" if user else host
    return f"ssh://{who}:{port}" if port else who


def check_ssh_config(host: str) -> str | None:
    """The no-network half of the preflight (a dry run runs only this): *host* must be an
    ssh alias and its jump variable well-formed. Returns the jump, or ``None``.

    Raises:
        HostUnreachableError: either check failed.
    """
    if not is_alias(host):
        raise HostUnreachableError(
            f"SSH preflight: {host!r} is not an ssh alias (nothing was changed)"
        )
    try:
        return jump_for(host)
    except JumpConfigError as e:
        raise HostUnreachableError(f"SSH preflight: {e} (nothing was changed)") from None


def verify_host_reachable(host: str | None = None, timeout: int = 10) -> None:
    """Prove ``ssh <host> true`` answers before a deploy touches the fleet.

    Probes the path every later call will take: through ``FABRIK_SSH_JUMP_<ALIAS>`` when
    it is set, else exactly as ssh config resolves the alias. Never switches path (no
    automatic reroute, D-row of W-2b657bee): on a jumped pass it only LOGS when the direct
    path answers again, so the variable can be removed by hand.

    Args:
        host: ssh alias; defaults to ``FABRIK_VPS_SSH_HOST`` (``vps``).
        timeout: ``ConnectTimeout`` seconds; the outer bound is ``timeout + 5``.

    Raises:
        HostUnreachableError: the path is dead, the alias is malformed, or the jump
            variable is. The message names the alias, the path, the dead leg when a jump is
            set, the reason and the next step.
    """
    host = host or _ssh_host()
    jump = check_ssh_config(host)
    var = jump_env_name(host)
    path = f"via jump {jump!r}" if jump else "without a FABRIK jump (as ssh config resolves it)"
    hop = ["-o", f"ProxyJump={jump}"] if jump else []  # the value read once, above
    ok, network, reason = _probe(["ssh", *hop, *_batch(timeout), host, "true"], timeout)
    if ok:
        if jump:
            _advise_if_direct_back(host, var)
        return
    head = f"SSH preflight: {host!r} is unreachable {path}: {reason}."
    if jump:
        hops = jump.split(",")
        first = hops[0]
        dest = _hop_destination(first)  # what the operator should type, too
        first_ok, first_network, first_reason = _probe(
            ["ssh", *_batch(timeout), dest, "true"], timeout
        )
        if first_ok:
            beyond = "a later hop or the leg to" if len(hops) > 1 else "the leg from it to"
            tail = (
                f" The jump host {first!r} answers; {beyond} {host!r} does not. Check that"
                f" leg's network, or unset {var} if the direct path is back."
                if network
                else f" The jump host {first!r} answers. Run `ssh {host} true` by hand to see why."
            )
        elif first_network:
            tail = (
                f" The jump host {first!r} is unreachable too: {first_reason}. Check"
                f" `ssh {dest} true`, or unset {var} if the direct path is back."
            )
        else:
            tail = (
                f" The jump host {first!r} fails: {first_reason}. Run `ssh {dest} true` by"
                " hand to see why."
            )
        msg = head + tail
    elif network:
        msg = head + (
            f" If another fleet host reaches it (e.g. over WireGuard), set {var}=<that alias>"
            " and re-run."
        )
    else:
        msg = head + f" Run `ssh {host} true` by hand to see why."
    raise HostUnreachableError(msg + " (nothing was changed)")


def _advise_if_direct_back(host: str, var: str) -> None:
    """Log (never act) when the direct path answers again. Fail-quiet: any error is silence."""
    argv = ["ssh", "-o", "ProxyJump=none", *_batch(3), host, "true"]
    try:
        r = subprocess.run(
            argv, capture_output=True, text=True, timeout=5, stdin=subprocess.DEVNULL, check=False
        )
    except Exception:  # noqa: BLE001 — an advisory probe must never fail the deploy
        return
    if r.returncode == 0:
        logger.warning(
            "The direct path to %r answers again — %s can be removed (the jump stays in use"
            " until it is).",
            host,
            var,
        )


__all__: tuple[str, ...] = (
    "DEFAULT_VPS_IP",
    "PUBLIC_DNS_RESOLVER",
    "TRAEFIK_API_LOCAL_URL",
    "verify_architecture",
    "verify_dns_before_deployment",
    "restart_traefik_and_wait",
    "HostUnreachableError",
    "check_ssh_config",
    "verify_host_reachable",
)
