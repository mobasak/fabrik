#!/usr/bin/env python3
"""Subprocess utilities shared across Fabrik scripts.

Provides a safe wrapper around :func:`subprocess.run` with sensible defaults
for timeout enforcement, error logging, and optional dry-run support.

Also provides file locking for concurrent hook execution safety.
"""

from __future__ import annotations

import fcntl
import os
import subprocess
import sys
from collections.abc import Sequence
from contextlib import contextmanager
from pathlib import Path

# Default lock directory
LOCK_DIR = Path(os.getenv("FABRIK_LOCK_DIR", "/tmp/fabrik-locks"))


@contextmanager
def file_lock(name: str, timeout: float = 10.0):
    """Acquire an exclusive file lock for concurrent safety.

    Args:
        name: Lock name (will be sanitized to filename).
        timeout: Max seconds to wait for lock (raises TimeoutError if exceeded).

    Usage:
        with file_lock("hook-validation"):
            # Only one process runs this at a time
            run_validation()
    """
    LOCK_DIR.mkdir(parents=True, exist_ok=True)
    lock_file = LOCK_DIR / f"{name.replace('/', '_')}.lock"

    fd = os.open(str(lock_file), os.O_CREAT | os.O_RDWR)
    try:
        # Try non-blocking first
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            # Wait with timeout
            import time

            start = time.time()
            while time.time() - start < timeout:
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    time.sleep(0.1)
            else:
                raise TimeoutError(f"Could not acquire lock '{name}' within {timeout}s")

        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def safe_run(
    cmd: Sequence[str] | str,
    *,
    timeout: float = 30.0,
    check: bool = True,
    capture_output: bool = True,
    text: bool = True,
    cwd: str | None = None,
    env: dict | None = None,
    dry_run: bool = False,
    log_errors: bool = True,
) -> subprocess.CompletedProcess:
    """Run a subprocess with guardrails.

    Args:
        cmd: Command to execute (list or string).
        timeout: Seconds before the process is killed.
        check: Raise :class:`CalledProcessError` when return code is non-zero.
        capture_output: Capture stdout/stderr (default True for safety).
        text: Decode output to text.
        cwd: Working directory for the command.
        env: Optional environment variables.
        dry_run: If True, skip execution and return a dummy result.
        log_errors: If True, log failures to stderr before raising.

    Returns:
        :class:`subprocess.CompletedProcess` instance.

    Raises:
        subprocess.TimeoutExpired: When execution exceeds the timeout.
        subprocess.CalledProcessError: When check=True and return code != 0.
        FileNotFoundError: When the command is missing.
    """

    if dry_run:
        stdout = "" if capture_output else None
        stderr = "" if capture_output else None
        return subprocess.CompletedProcess(cmd, 0, stdout=stdout, stderr=stderr)

    try:
        return subprocess.run(  # type: ignore[call-arg]
            cmd,
            timeout=timeout,
            check=check,
            capture_output=capture_output,
            text=text,
            cwd=cwd,
            env=env,
        )
    except subprocess.TimeoutExpired:
        if log_errors:
            print(f"[safe_run] Timeout after {timeout}s: {cmd}", file=sys.stderr)
        raise
    except subprocess.CalledProcessError as e:
        if log_errors:
            stderr = (e.stderr or "").strip()
            print(
                f"[safe_run] Command failed with exit {e.returncode}: {cmd}\n{stderr}",
                file=sys.stderr,
            )
        raise
    except FileNotFoundError:
        if log_errors:
            print(f"[safe_run] Command not found: {cmd}", file=sys.stderr)
        raise
