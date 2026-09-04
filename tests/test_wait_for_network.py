# AFTER-EDIT: scripts/wait_for_network.sh
"""The boot-time network guard: it must wait, it must bound the wait, and it must NEVER block a login.

Measured 2026-09-04: WSL booted at 20:41:29 and the startup hook's pipeline began at 20:44:31, while
DNS was still unavailable. Three failures in that one boot traced to it — a real contract-drift alert
lost on both channels, the daily pipeline's auto-commit stranded off-box ("push failed — commit left
local"), and a pool round returning 0 of 10 units. The alert path itself was healthy: a selftest that
evening returned "PASS: alert delivered".

The guard is sourced into every interactive login, so the failure mode that matters is not "waited too
little" — it is "hung a shell forever on a box with no network". Every test here is really about that.
"""

from __future__ import annotations

import subprocess
import time
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "wait_for_network.sh"


def _run(timeout: float = 30.0, **env_over: str) -> tuple[int, str, float]:
    env = {"PATH": "/usr/bin:/bin", "HOME": "/tmp", **env_over}
    t0 = time.monotonic()
    p = subprocess.run(
        ["bash", str(SCRIPT)], capture_output=True, text=True, env=env, timeout=timeout
    )
    return p.returncode, p.stdout + p.stderr, time.monotonic() - t0


def test_a_resolvable_host_returns_at_once_and_says_nothing():
    """localhost always resolves, so the guard must cost a boot nothing in the normal case."""
    rc, out, elapsed = _run(WAIT_NET_HOST="localhost", WAIT_NET_TIMEOUT_S="30")

    assert rc == 0
    assert elapsed < 3.0, f"guard added {elapsed:.1f}s to a boot whose network was already up"
    assert "WARNING" not in out
    assert out.strip() == "", "a silent success keeps the operator's login clean"


def test_an_unresolvable_host_gives_up_and_still_exits_zero():
    """THE contract. A boot with no network must never hang a login shell — the guard warns and
    stands aside. An exit code other than 0 would abort the whole pipeline chain."""
    rc, out, elapsed = _run(
        WAIT_NET_HOST="no-such-host.invalid", WAIT_NET_TIMEOUT_S="4", WAIT_NET_INTERVAL_S="1"
    )

    assert rc == 0, "FAIL-OPEN: a guard that can fail is worse than the race it fixes"
    assert "WARNING" in out and "did not resolve" in out
    assert elapsed < 12.0, f"gave up after {elapsed:.1f}s — the budget is not bounding the loop"


def test_the_budget_is_actually_honoured():
    """A budget that is ignored is an infinite hang wearing a number."""
    _, _, short = _run(
        WAIT_NET_HOST="no-such-host.invalid", WAIT_NET_TIMEOUT_S="2", WAIT_NET_INTERVAL_S="1"
    )
    _, _, longer = _run(
        WAIT_NET_HOST="no-such-host.invalid", WAIT_NET_TIMEOUT_S="6", WAIT_NET_INTERVAL_S="1"
    )

    assert longer > short + 1.5, f"budget ignored: 2s took {short:.1f}s, 6s took {longer:.1f}s"


def test_a_garbage_budget_cannot_hang_the_boot(tmp_path):
    """An env typo (`WAIT_NET_TIMEOUT_S=forever`) must fall back to the default, not loop forever
    and not crash under `set -u`. Tested with a 20s ceiling: the default budget is 90s, so an
    infinite loop trips the subprocess timeout and fails this test loudly."""
    rc, out, _ = _run(
        timeout=20.0,
        WAIT_NET_HOST="localhost",
        WAIT_NET_TIMEOUT_S="forever",
        WAIT_NET_INTERVAL_S="also-garbage",
    )

    assert rc == 0
    assert "WARNING" not in out, "localhost resolves; a garbage budget must not force the warning"


def test_it_is_wired_into_the_startup_hook_before_the_network_steps():
    """A guard nobody calls is dead code. The hook's pipeline must invoke it, and it must come
    BEFORE the first network-dependent step or it guards nothing."""
    hook = (SCRIPT.parent / "wsl_startup_hook.sh").read_text()

    assert "wait_for_network.sh" in hook, "the startup hook does not call the guard"
    guard_at = hook.index("wait_for_network.sh")
    # pipeline_alert is the first thing in the chain that needs DNS (telegram) or a route (ssh)
    alert_at = hook.index("pipeline_alert.sh", guard_at)
    assert guard_at < alert_at, "the guard runs after the alerting it exists to protect"


# ── The retired-tool retry: 60s of every boot spent waiting for a binary that will never appear ──


def test_sync_extensions_skips_at_once_when_windsurf_is_absent():
    """Measured 2026-09-04: `windsurf` is not installed (Windsurf/Cascade is retired), yet
    sync_extensions.sh ran its "the IDE may not be ready yet" retry — 2 x 30s sleeps — on EVERY WSL
    boot, then warned in words that read like a transient fault. A retired tool is not a slow tool."""
    script = SCRIPT.parent / "sync_extensions.sh"
    t0 = time.monotonic()
    p = subprocess.run(
        ["bash", str(script)],
        capture_output=True,
        text=True,
        cwd=SCRIPT.parent.parent,
        env={"PATH": "/usr/bin:/bin", "HOME": "/tmp"},  # a PATH with no windsurf on it
        timeout=90,
    )
    elapsed = time.monotonic() - t0

    assert p.returncode == 0, "an absent optional tool must never fail the boot chain"
    assert elapsed < 5.0, f"still sleeping through the retry loop: {elapsed:.1f}s"
    assert "retired" in (p.stdout + p.stderr).lower(), "say WHY it skipped, not just that it did"
