"""WSL-side file-lock primitive for serializing local Python orchestration.

This is the project-scoped sibling of :mod:`fabrik.drivers.locks` (whose
``run_locked`` wraps a single bash script on the VPS via SSH and is unable
to hold a remote lock across multiple Python-side SSH calls — see that
module's docstring for the proof).

Use this primitive whenever a Python process on the WSL side must hold
exclusive ownership of a logical resource for the duration of multiple
async-style operations: e.g. ``fabrik reconcile-all`` walking specs and
calling ``redeploy --refresh-infra`` per spec, or ``state.save`` writing
``.fabrik/state/<id>.json`` while another invocation might race on the
same file.

Mechanics
---------

* ``fcntl.flock(fd, LOCK_EX | LOCK_NB)`` with polling — non-blocking
  acquire, retry every ``poll_interval`` seconds until ``timeout_seconds``
  elapses, at which point :class:`TimeoutError` is raised.
* One lock file per logical resource, under ``$FABRIK_LOCK_DIR`` (default
  ``~/.cache/fabrik-locks``). The name is sanitized to a safe filename.
* The fd is closed on context exit, which releases the kernel-level lock.
  Exceptions inside the ``with`` body propagate; the lock is still released.

Environment
-----------

``FABRIK_LOCK_DIR``: directory for the lock files. Defaults to
``~/.cache/fabrik-locks`` (``Path.home()``, which falls back to the passwd home when ``HOME`` is unset, as
under cron), so every hub process of one user shares it and no other local user can pre-create it the way
a fixed ``/tmp`` name allowed (W-1f70f2e9). The dir is made 0700 when created; its privacy rests on a private
HOME, since a missing ``~/.cache`` parent takes the umask's mode and an existing dir is left as it is. It
fails closed: with HOME unwritable or empty, ``file_lock`` raises ``OSError`` — set ``FABRIK_LOCK_DIR``.
"""

from __future__ import annotations

import errno
import fcntl
import logging
import os
import re
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

logger = logging.getLogger(__name__)

# Per user, under a private HOME, and the same dir for every hub process of that user: cron has no
# XDG_RUNTIME_DIR, and a per-checkout dir would stop worktrees excluding each other (W-1f70f2e9).
LOCK_DIR = Path(os.getenv("FABRIK_LOCK_DIR") or Path.home() / ".cache" / "fabrik-locks")

_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._-]")


def _sanitize(name: str) -> str:
    # Reduce to filesystem-safe characters; collapse anything else to '_'.
    cleaned = _SAFE_NAME_RE.sub("_", name).strip("_")
    return cleaned or "_"


@contextmanager
def file_lock(
    name: str, timeout_seconds: float = 30.0, poll_interval: float = 0.5
) -> Iterator[Path]:
    """Acquire an exclusive file lock named ``name`` for the duration of
    the ``with`` block.

    Args:
        name: Logical resource name (e.g. ``"reconcile-translator"`` or
            ``"state-fabrik-translator"``). Sanitized to filesystem-safe.
        timeout_seconds: Max wall-clock seconds to wait for the lock.
            On expiry, raises :class:`TimeoutError`.
        poll_interval: Seconds between retries while waiting.

    Yields:
        The path to the lock file (e.g. for logging — callers rarely
        need it).

    Raises:
        TimeoutError: lock not acquired within ``timeout_seconds``.
        OSError: filesystem-level failure unrelated to lock contention.
    """
    LOCK_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    safe = _sanitize(name)
    lock_path = LOCK_DIR / f"{safe}.lock"
    deadline = time.monotonic() + timeout_seconds
    fd = os.open(str(lock_path), os.O_RDWR | os.O_CREAT, 0o600)
    try:
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                logger.debug("file_lock acquired: %s", lock_path)
                break
            except OSError as e:
                if e.errno not in (errno.EWOULDBLOCK, errno.EAGAIN):
                    raise
                if time.monotonic() >= deadline:
                    raise TimeoutError(
                        f"file_lock({name!r}) timed out after {timeout_seconds}s"
                    ) from e
                time.sleep(poll_interval)
        try:
            yield lock_path
        finally:
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
            except OSError:
                pass
    finally:
        os.close(fd)
