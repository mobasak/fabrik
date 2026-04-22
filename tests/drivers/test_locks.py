"""Unit tests for fabrik.drivers.locks + live-VPS concurrency proof.

Unit tests mock the ssh() call and verify the command-construction contract
(flock invocation, lock path, shlex-quoting of the script body).

The concurrency proof test is gated by ``@pytest.mark.requires_fabrik_env``
and actually SSH's into the Fabrik VPS twice in parallel to prove that
``run_locked`` serializes concurrent callers on the same resource. It
is skipped in CI and in any environment without the `vps` SSH alias.
"""

from __future__ import annotations

import shlex
import shutil
import subprocess
import threading
import time
from unittest.mock import patch

import pytest

from fabrik.drivers.locks import (
    GIT_VERSIONED_DIRS,
    git_commit_config,
    run_locked,
)


class TestRunLockedContract:
    """Verify the bash command run_locked builds — no live VPS needed."""

    @patch("fabrik.drivers.locks.ssh")
    def test_builds_flock_command_with_resource_lockfile(self, mock_ssh):
        mock_ssh.return_value = "ok"
        run_locked("backrest-config", "set -euo pipefail; echo hi", timeout=120)
        sent_cmd = mock_ssh.call_args[0][0]
        # Lock file path
        assert "/tmp/fabrik-backrest-config.lock" in sent_cmd
        # Exclusive lock with bounded wait
        assert "flock -x -w 120" in sent_cmd
        # Script body is shlex-quoted so embedded single quotes can't escape
        assert shlex.quote("set -euo pipefail; echo hi") in sent_cmd
        # Script is handed to bash -c, not eval'd directly
        assert "bash -c" in sent_cmd

    @patch("fabrik.drivers.locks.ssh")
    def test_ssh_timeout_is_larger_than_flock_timeout(self, mock_ssh):
        """flock timeout fires first, so the caller sees 'lock timed out'
        rather than a confusing 'SSH timed out'."""
        mock_ssh.return_value = ""
        run_locked("demo", "true", timeout=60)
        ssh_timeout = mock_ssh.call_args.kwargs["timeout"]
        assert ssh_timeout > 60

    @patch("fabrik.drivers.locks.ssh")
    def test_distinct_resources_use_distinct_lockfiles(self, mock_ssh):
        mock_ssh.return_value = ""
        run_locked("backrest-config", "true")
        run_locked("authelia-config", "true")
        cmds = [c.args[0] for c in mock_ssh.call_args_list]
        assert "/tmp/fabrik-backrest-config.lock" in cmds[0]
        assert "/tmp/fabrik-authelia-config.lock" in cmds[1]

    @patch("fabrik.drivers.locks.ssh")
    def test_returns_ssh_stdout_verbatim(self, mock_ssh):
        mock_ssh.return_value = "CREATED"
        assert run_locked("r", "echo CREATED") == "CREATED"

    @patch("fabrik.drivers.locks.ssh")
    def test_script_with_embedded_single_quotes_is_safely_quoted(self, mock_ssh):
        """Regression: earlier drafts broke on scripts containing single
        quotes (payloads, JSON, etc.). shlex.quote handles all edge cases."""
        mock_ssh.return_value = ""
        tricky = "echo 'hello'; printf '%s\\n' \"$(date)\""
        run_locked("r", tricky)
        sent_cmd = mock_ssh.call_args[0][0]
        # The quoted form survives round-tripping through bash -c
        assert shlex.quote(tricky) in sent_cmd


class TestGitCommitConfig:
    """Whitelist enforcement for git_commit_config()."""

    def test_whitelist_contains_only_gatus_today(self):
        """Guard against accidental additions — any change here is a
        security decision that must be reviewed, not a drive-by edit."""
        assert {"/opt/monitoring/configs/gatus"} == GIT_VERSIONED_DIRS

    def test_rejects_non_whitelisted_path(self):
        with pytest.raises(ValueError, match="not in whitelist"):
            git_commit_config("/opt/backrest/config", "leak secrets please")

    def test_rejects_authelia_config_path(self):
        """Authelia config has live JWT/session secrets — must never go to git."""
        with pytest.raises(ValueError, match="not in whitelist"):
            git_commit_config("/opt/authelia/config", "nope")

    def test_dry_run_on_whitelisted_path_does_not_call_ssh(self):
        with patch("fabrik.drivers.locks.ssh") as mock_ssh:
            git_commit_config("/opt/monitoring/configs/gatus", "test commit", dry_run=True)
            mock_ssh.assert_not_called()

    @patch("fabrik.drivers.locks.ssh")
    def test_ssh_errors_are_non_fatal(self, mock_ssh):
        """Failed audit-trail commit must not break the deploy."""
        mock_ssh.side_effect = RuntimeError("git: not found")
        # Must NOT raise
        git_commit_config("/opt/monitoring/configs/gatus", "test")


# ─────────────────────────────────────────────────────────────────────
# Live-VPS concurrency proof — requires `ssh vps` to work.
# Skipped in CI and on any dev box without the SSH alias configured.
# ─────────────────────────────────────────────────────────────────────


def _vps_ssh_available() -> bool:
    """True if the `ssh` binary exists and the `vps` alias resolves."""
    if shutil.which("ssh") is None:
        return False
    try:
        r = subprocess.run(
            ["ssh", "-G", "vps"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        # `ssh -G` always exits 0 if it can parse config; non-zero means
        # no such host alias in ~/.ssh/config.
        return r.returncode == 0
    except Exception:
        return False


@pytest.mark.requires_fabrik_env
@pytest.mark.skipif(
    not _vps_ssh_available(),
    reason="requires `ssh vps` alias in ~/.ssh/config",
)
def test_run_locked_concurrency_proof_live_vps():
    """Two concurrent run_locked() calls on the same resource must serialize.

    Each thread acquires the lock, sleeps 3 seconds, then echoes a UNIX
    timestamp. If the lock is correctly held for the full script duration,
    the two returned timestamps differ by >= 3 seconds. If the lock is
    released early (the bug this module was written to prevent), they
    differ by < 1 second.

    Runs against a unique lock resource so it can't collide with other
    callers even if two test sessions run simultaneously.
    """
    resource = f"fabrik-test-concurrency-{int(time.time() * 1000)}"
    script = "set -euo pipefail\nsleep 3\ndate +%s"

    results: dict[int, str] = {}

    def worker(idx: int) -> None:
        results[idx] = run_locked(resource, script, timeout=30)

    t1 = threading.Thread(target=worker, args=(1,))
    t2 = threading.Thread(target=worker, args=(2,))

    t0 = time.monotonic()
    t1.start()
    # Slight stagger so the first thread is guaranteed to acquire first.
    time.sleep(0.2)
    t2.start()
    t1.join(timeout=60)
    t2.join(timeout=60)
    wall_elapsed = time.monotonic() - t0

    assert set(results.keys()) == {1, 2}, "both threads must complete"
    ts1 = int(results[1])
    ts2 = int(results[2])
    delta = abs(ts2 - ts1)

    # The second holder can't have run until the first released — at least
    # the 3s sleep must separate them.
    assert delta >= 3, (
        f"Lock released early: timestamps differ by only {delta}s (results: {results})"
    )
    # Both scripts ran serially: total wall time >= 2 * 3s sleep.
    assert wall_elapsed >= 6.0, f"Wall time {wall_elapsed:.1f}s < 6.0s — calls did not serialize"
