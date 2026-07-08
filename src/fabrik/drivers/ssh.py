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


def _redact(cmd: str) -> str:
    """Return ``cmd`` with any base64→``base64 -d`` payload masked for logging."""
    return _B64_PIPE.sub("echo <redacted-base64> | base64 -d", cmd)


def _ssh_host() -> str:
    """Return the SSH host alias, reading ``FABRIK_VPS_SSH_HOST`` at call time.

    Function-level (not module-level) lookup is deliberate: module-level
    reads capture the value at import time, which breaks tests that
    monkeypatch ``os.environ`` *after* the module is loaded.
    """
    return os.getenv("FABRIK_VPS_SSH_HOST", DEFAULT_SSH_HOST)


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

    Example:
        >>> ssh("uname -m")  # doctest: +SKIP
        'x86_64'
    """
    if dry_run:
        logger.info("[DRY RUN] SSH: %s", cmd)
        return ""

    host = _ssh_host()
    logger.debug("SSH %s: %s", host, _redact(cmd))
    result = subprocess.run(
        ["ssh", host, cmd],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"SSH to {host!r} failed (rc={result.returncode}): {result.stderr.strip()}"
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

    Example:
        >>> scp_to_vps("/tmp/config.yml", "/opt/svc/config.yml")  # doctest: +SKIP
    """
    if dry_run:
        logger.info("[DRY RUN] SCP: %s -> vps:%s", local_path, remote_path)
        return

    host = _ssh_host()
    logger.debug("SCP %s -> %s:%s", local_path, host, remote_path)
    result = subprocess.run(
        ["scp", local_path, f"{host}:{remote_path}"],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"SCP to {host!r} failed (rc={result.returncode}): {result.stderr.strip()}"
        )
