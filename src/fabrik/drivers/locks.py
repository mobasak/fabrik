"""VPS-side file locking + whitelisted git versioning.

This module provides :func:`run_locked`, the only correct way to execute
config-mutating bash scripts on the Fabrik VPS under an exclusive file
lock. The lock is held for the entire script duration — NOT for the
duration of a Python context manager, NOT across multiple ``ssh()`` calls
chained from Python.

Why this module exists
----------------------

Early Fabrik drafts used a Python context-manager ``VPSLock`` that opened
an SSH session, ran ``flock ... -c 'echo locked'``, and returned. ``flock``
releases the lock the instant the inner command exits — before ``__enter__``
returns. Every subsequent ``ssh()`` call inside the ``with`` block ran
unlocked. This was proven against the live Fabrik VPS::

    $ ssh vps "flock -x /tmp/tlp.lock -c 'echo FIRST at \\$(date +%s)'; \\
               flock -x -w 1 /tmp/tlp.lock -c 'echo SECOND at \\$(date +%s)'"
    FIRST at 1776500626
    SECOND at 1776500626   # same second — both acquired. Lock did not persist.

Python-side orchestration of SSH calls **cannot** hold a remote file lock.
The only correct pattern is to run the entire mutation as one bash script
under ``flock``, which is exactly what :func:`run_locked` does.

Usage pattern
-------------

Every config-mutating driver (Backrest, Authelia, and any future driver
that edits a shared config file on the VPS) MUST build its mutation as a
single bash script and pass it to :func:`run_locked`::

    script = '''set -euo pipefail
    # 1. idempotency check
    # 2. timestamped backup
    # 3. mutation -> tmp
    # 4. validate tmp
    # 5. atomic mv tmp -> live
    # 6. restart service
    '''
    run_locked("backrest-config", script, timeout=120)

Do NOT chain ``ssh()`` calls from Python and expect them to share a lock.
They won't. See the module docstring above for proof.
"""

from __future__ import annotations

import logging
import shlex

from fabrik.drivers.ssh import ssh

logger = logging.getLogger(__name__)

GIT_VERSIONED_DIRS: set[str] = {"/opt/monitoring/configs/gatus"}
"""Whitelist of VPS paths that may be committed to git by :func:`git_commit_config`.

Secret-bearing configs (Backrest's ``config.json`` with live B2 credentials,
Authelia's ``configuration.yml`` with JWT/session secrets) are explicitly
excluded from this whitelist — they rely on timestamped ``.bak.{ts}`` files
for rollback, never git. Adding a new entry here is a security decision and
must be reviewed.
"""


def run_locked(resource: str, script: str, timeout: int = 120) -> str:
    """Run a bash script on the Fabrik VPS under an exclusive file lock.

    The lock is held for the entire script duration — all mutation steps
    MUST be combined in the script body (``&&``, ``;``, or multi-line).
    Do not try to chain multiple ``ssh()`` calls from Python and expect
    them to share a lock; see the module docstring for why that fails.

    The lock file lives at ``/tmp/fabrik-{resource}.lock`` on the VPS.
    ``flock -x -w <timeout>`` is used: an exclusive (write) lock with a
    bounded wait. If the lock can't be acquired in ``timeout`` seconds,
    ``flock`` exits 1 and this function raises :class:`RuntimeError`.

    Args:
        resource: Logical name of the resource being mutated
            (e.g. ``"backrest-config"``, ``"authelia-config"``). Becomes
            ``/tmp/fabrik-{resource}.lock`` on the VPS. Use distinct names
            for distinct resources so unrelated mutations don't serialize.
        script: Full bash script. MUST start with ``set -euo pipefail`` so
            any failed step aborts the whole script (and releases the lock).
        timeout: Seconds to wait for lock acquisition AND for the entire
            script to run. Pick a value larger than the slowest expected
            mutation (config rewrites: ~10s; docker restart: ~30s).

    Returns:
        stdout from the script (stripped of trailing whitespace).

    Raises:
        RuntimeError: Lock acquisition timed out, or the script exited
            non-zero. The ``ssh()`` wrapper re-raises its own RuntimeError
            with stderr included in the message.

    Example:
        >>> run_locked("test-demo", "set -euo pipefail; echo hello")  # doctest: +SKIP
        'hello'
    """
    lock_file = f"/tmp/fabrik-{resource}.lock"
    cmd = f"flock -x -w {timeout} {lock_file} bash -c {shlex.quote(script)}"
    # Give ssh() a slightly larger timeout than flock's so the flock error
    # surfaces as "lock acquisition timed out" rather than "SSH timed out".
    return ssh(cmd, timeout=timeout + 10)


def git_commit_config(
    config_dir: str,
    message: str,
    dry_run: bool = False,
) -> None:
    """Commit a non-secret VPS config directory to git for audit trail.

    Only paths in :data:`GIT_VERSIONED_DIRS` may be versioned. Secret-bearing
    configs rely on ``.bak.{timestamp}`` files, never git — committing a
    config with live credentials would leak them into the git history where
    operators (and anyone with repo read access) could retrieve them via
    ``git show`` or ``git log -p``.

    Args:
        config_dir: Absolute path on the VPS. MUST be a member of
            :data:`GIT_VERSIONED_DIRS`.
        message: Commit message. Quoted into the ``git commit -m`` argument.
        dry_run: If True, log the intent and return without running git.

    Raises:
        ValueError: ``config_dir`` is not in the whitelist.

    Notes:
        Non-fatal on git errors (the actual config write has already
        succeeded by the time this is called; a failed commit is a
        degraded audit trail, not a broken deploy).
    """
    if config_dir not in GIT_VERSIONED_DIRS:
        raise ValueError(
            f"Refusing to git-version {config_dir}: not in whitelist "
            f"({sorted(GIT_VERSIONED_DIRS)}). Secret-bearing configs rely "
            f"on .bak.{{timestamp}} files for rollback, not git."
        )
    if dry_run:
        logger.info("[DRY RUN] git commit: %s (%s)", config_dir, message)
        return
    try:
        ssh(
            f"cd {shlex.quote(config_dir)} && "
            f"(git rev-parse --git-dir >/dev/null 2>&1 || git init -q)"
        )
        ssh(f"cd {shlex.quote(config_dir)} && git config user.name 'Fabrik Automation'")
        ssh(f"cd {shlex.quote(config_dir)} && git config user.email 'fabrik@ocoron.com'")
        ssh(f"cd {shlex.quote(config_dir)} && chmod 700 .git")
        ssh(
            f"cd {shlex.quote(config_dir)} && git add -A && "
            f"git commit -m {shlex.quote(message)} --allow-empty || true"
        )
    except Exception as e:
        logger.warning("Git commit failed (non-fatal): %s", e)
