"""SSH + SCP helpers for Fabrik VPS operations.

Thin, dependency-free wrappers around `subprocess.run` for executing commands
and copying files to the Fabrik VPS. Both functions obey `FABRIK_VPS_SSH_HOST`
(default: ``"vps"`` — a ``~/.ssh/config`` alias that resolves to the actual
host, user, and key) so the underlying VPS can be swapped without a code
change and tests can target a throwaway alias.

Design notes
------------
* These helpers are the foundation for every Fabrik driver that mutates VPS
  state (Backrest, Authelia, Gatus). They MUST NOT attempt to hold remote
  file locks on their own — use :func:`fabrik.drivers.locks.run_locked` to
  run a full bash script under ``flock`` instead. See the locks module
  docstring for the proof that Python-orchestrated SSH chains cannot hold a
  remote lock.
* ``dry_run=True`` is a universal no-op switch used by ``fabrik apply
  --dry-run`` to surface the commands that *would* run without touching the
  VPS.
"""

from __future__ import annotations

import logging
import os
import re
import subprocess

logger = logging.getLogger(__name__)

DEFAULT_SSH_HOST = "vps"
"""Default SSH alias resolved via ``~/.ssh/config``. Overridable via
``FABRIK_VPS_SSH_HOST``.
"""

# Mask base64 payloads piped to `base64 -d` before they hit a DEBUG log. Callers
# like ``postgres._run_sql`` ship SQL — which may carry a role ``PASSWORD`` — as
# ``echo <base64> | base64 -d | … psql``; without this, enabling DEBUG (or wiring
# a Loki sink at DEBUG) trivially leaks every generated DB-role password.
_B64_PIPE = re.compile(r"echo\s+[A-Za-z0-9+/=]{20,}\s*\|\s*base64\s+-d")


_SECRETY_ASSIGN = re.compile(
    r"(\w*(?:TOKEN|SECRET|KEY|PASSWORD|PASSWD|CREDENTIAL)S?\w*\s*=\s*)(\S+)", re.I
)


def _redact(cmd: str) -> str:
    """Return ``cmd`` with base64 payloads AND secret-shaped assignments masked.

    The assignment mask (F12, 2026-08-31): a failing .env-write echoed the whole
    heredoc — CONSUMER_TOKENS included — through the error path; base64 masking
    alone never touched it.
    """
    out = _B64_PIPE.sub("echo <redacted-base64> | base64 -d", cmd)
    return _SECRETY_ASSIGN.sub(r"\1<redacted>", out)


def _ssh_host() -> str:
    """Return the SSH host alias, reading ``FABRIK_VPS_SSH_HOST`` at call time.

    Function-level (not module-level) lookup is deliberate: module-level
    reads capture the value at import time, which breaks tests that
    monkeypatch ``os.environ`` *after* the module is loaded.
    """
    return os.getenv("FABRIK_VPS_SSH_HOST", DEFAULT_SSH_HOST)


JUMP_ENV_PREFIX = "FABRIK_SSH_JUMP_"
"""Per-alias opt-in jump (W-2b657bee): ``FABRIK_SSH_JUMP_VPS=vps2`` routes ssh/scp to the
``vps`` alias through ``vps2`` — here, in ``drivers/dns.py`` and in ``audit._ssh_check``. Unset, the argv is exactly what it was before. Never an
automatic reroute: a dead path is named by ``preflight.verify_host_reachable`` instead.
"""

# One ProxyJump hop is ``[user@]host[:port]``; several are comma-separated (OpenSSH's own
# -J syntax). Strict on purpose, checked per hop with fullmatch: the value lands in ssh's
# argv, so a leading ``-``, a space or a shell character is refused rather than passed; so
# are IPv6 literals (name the hop by an alias) and ``none``, ProxyJump's disable keyword,
# which would silently mean "direct" while every message said "via jump".
_JUMP_HOP = re.compile(
    r"(?:(?P<user>[A-Za-z0-9_][A-Za-z0-9_.-]*)@)?(?P<host>[A-Za-z0-9_][A-Za-z0-9_.-]*)"
    r"(?::(?P<port>[1-9][0-9]{0,4}))?"
)


class JumpConfigError(ValueError):
    """``FABRIK_SSH_JUMP_<ALIAS>`` holds a non-ProxyJump value. Its own type so a caller's
    broad ``except Exception`` fallback (the orchestrator's DNS step) can let it through."""


def parse_hop(hop: str) -> tuple[str | None, str, int | None] | None:
    """Split one hop into ``(user, host, port)``, or ``None`` when it is outside the grammar
    (host ``none`` — ProxyJump's disable keyword — and ports past 65535 included)."""
    m = _JUMP_HOP.fullmatch(hop)
    if not m or m["host"].lower() == "none":
        return None
    port = int(m["port"]) if m["port"] else None
    if port is not None and port > 65535:
        return None
    return m["user"], m["host"], port


def jump_env_name(host: str) -> str:
    """Return the variable that names *host*'s jump: ``vps`` → ``FABRIK_SSH_JUMP_VPS``.

    Every character outside ``[A-Z0-9]`` becomes ``_``, so ``vps-1`` and ``vps_1`` share one.
    """
    return JUMP_ENV_PREFIX + re.sub(r"[^A-Z0-9]", "_", host.upper())


def jump_for(host: str) -> str | None:
    """Return the ProxyJump value set for *host*, or ``None`` (unset or empty).

    Raises:
        JumpConfigError: the variable is set to something outside the hop grammar. Fail
            closed: a typo must not silently fall back to the dead direct path.
    """
    name = jump_env_name(host)
    value = os.getenv(name, "")
    if not value:
        return None
    hops = value.split(",")
    if not all(parse_hop(h) for h in hops):
        raise JumpConfigError(
            f"{name}={value!r} is not a ProxyJump value: [user@]host[:port] hops, comma-"
            "separated, port 1-65535 (no IPv6 literals — use an ssh alias; 'none' is refused)"
        )
    return value


def _jump_opts(jump: str | None) -> list[str]:
    return ["-o", f"ProxyJump={jump}"] if jump else []


def jump_args(host: str) -> list[str]:
    """Return the ssh/scp options that route *host* through its jump — ``[]`` when none is set."""
    return _jump_opts(jump_for(host))


def _via(jump: str | None) -> str:
    """`` via jump 'vps2'`` for a failure message, or ``""`` when no jump is set."""
    return f" via jump {jump!r}" if jump else ""


def ssh(cmd: str, timeout: int = 60, dry_run: bool = False) -> str:
    """Execute a shell command on the Fabrik VPS via SSH and return stdout.

    Args:
        cmd: Shell command to run on the VPS. Passed as a single argument to
            ``ssh <host> <cmd>``, so the remote shell handles word splitting.
        timeout: Seconds to wait for the SSH call to complete. Exceeding the
            timeout raises :class:`subprocess.TimeoutExpired`.
        dry_run: If True, log the command at INFO level and return empty
            string without invoking ``ssh``.

    Returns:
        The command's stdout with trailing whitespace stripped.

    Raises:
        RuntimeError: SSH returned a non-zero exit code. Stderr is included
            in the exception message for quick diagnosis.
        subprocess.TimeoutExpired: The SSH call exceeded ``timeout`` seconds.
        JumpConfigError: ``FABRIK_SSH_JUMP_<ALIAS>`` is set to a non-ProxyJump value.

    Example:
        >>> ssh("uname -m")  # doctest: +SKIP
        'x86_64'
    """
    if dry_run:
        logger.info("[DRY RUN] SSH: %s", cmd)
        return ""

    host = _ssh_host()
    jump = jump_for(host)  # read once: the argv and the error text name the same jump
    logger.debug("SSH %s: %s", host, _redact(cmd))
    try:
        result = subprocess.run(
            ["ssh", *_jump_opts(jump), host, cmd],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        timed_out = False
    except subprocess.TimeoutExpired:
        timed_out = True
    if timed_out:
        # Re-raised OUTSIDE the except block: TimeoutExpired's str/repr carry the full
        # argv, and `_run_sql`'s argv holds the base64 SQL batch (`ALTER ROLE … PASSWORD`),
        # which registrars log via str(e). Raising here leaves no __context__ holding it.
        raise subprocess.TimeoutExpired(["ssh", host, "<command redacted>"], timeout) from None
    if result.returncode != 0:
        # _redact the FAILURE surface too (F12, 01M1C95A2S: a failing .env-write heredoc
        # echoed a live CONSUMER_TOKENS bearer token verbatim into the apply log twice —
        # the debug line above redacts the command, but the error path shipped raw stderr,
        # forcing a mid-deploy credential rotation).
        raise RuntimeError(
            f"SSH to {host!r}{_via(jump)} failed (rc={result.returncode}): "
            f"{_redact(result.stderr.strip())}"
        )
    return result.stdout.strip()


def scp_to_vps(
    local_path: str,
    remote_path: str,
    timeout: int = 30,
    dry_run: bool = False,
) -> None:
    """Copy a local file to the Fabrik VPS via ``scp``.

    Args:
        local_path: Absolute or relative path to the local source file.
        remote_path: Absolute destination path on the VPS.
        timeout: Seconds to wait for the copy to complete.
        dry_run: If True, log the intended copy and return without running.

    Raises:
        RuntimeError: ``scp`` returned a non-zero exit code.
        subprocess.TimeoutExpired: The copy exceeded ``timeout`` seconds.
        JumpConfigError: ``FABRIK_SSH_JUMP_<ALIAS>`` is set to a non-ProxyJump value.

    Example:
        >>> scp_to_vps("/tmp/config.yml", "/opt/svc/config.yml")  # doctest: +SKIP
    """
    if dry_run:
        logger.info("[DRY RUN] SCP: %s -> vps:%s", local_path, remote_path)
        return

    host = _ssh_host()
    jump = jump_for(host)
    logger.debug("SCP %s -> %s:%s", local_path, host, remote_path)
    result = subprocess.run(
        ["scp", *_jump_opts(jump), local_path, f"{host}:{remote_path}"],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"SCP to {host!r}{_via(jump)} failed (rc={result.returncode}): "
            f"{_redact(result.stderr.strip())}"
        )
