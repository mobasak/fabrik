"""The two ADVISORY hooks stand down under `FABRIK_HEADLESS=1` (T13.5, 01M23HB2M + 01M23K7XT).

An advisory hook has nobody to advise in a headless run: the mail dispatcher spawns `claude -p`
turns no human reads, and these two print to a stream that is captured and discarded. Cost with
no reader.

⚠️ The guard is for ADVISORY hooks ONLY. A blocking check that an environment variable can switch
off is a blocking check with a documented bypass — this suite asserts the Stop hook does NOT read
the flag, so the cobra path is closed by a grader and not only by a comment.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

HOOKS = Path(__file__).resolve().parents[1] / ".claude" / "hooks"
ADVISORY = ("mail_notify.py", "mcp_watch.py")


def _run(script: Path, env_extra: dict[str, str]) -> tuple[int, str]:
    env = {**os.environ, **env_extra}
    r = subprocess.run(
        [sys.executable, str(script)],
        input="{}",
        capture_output=True,
        text=True,
        timeout=120,
        env=env,
    )
    return r.returncode, r.stdout + r.stderr


@pytest.mark.parametrize("name", ADVISORY)
def test_an_advisory_hook_is_silent_and_green_when_headless(name: str) -> None:
    rc, out = _run(HOOKS / name, {"FABRIK_HEADLESS": "1"})
    assert rc == 0, f"{name} exited {rc} under FABRIK_HEADLESS=1"
    assert out == "", f"{name} printed {out!r} with nobody to read it"


@pytest.mark.parametrize("name", ADVISORY)
def test_the_guard_reads_exactly_1_not_any_value(name: str) -> None:
    """`FABRIK_HEADLESS=0` is a session declaring it is NOT headless. Treating any non-empty
    value as true would make `0` mean `1`, which is the shape that silences a hook by accident."""
    script = HOOKS / name
    src = script.read_text(encoding="utf-8")
    assert 'os.environ.get("FABRIK_HEADLESS") == "1"' in src, (
        f"{name} does not compare the flag to the literal '1'"
    )


def test_no_blocking_hook_reads_the_headless_flag() -> None:
    """THE COBRA PATH, graded. The cheapest way to satisfy any hook is to export a variable that
    turns it off — so the flag must never reach one that BLOCKS. `final_gate_stop.py` and
    `quota_stop.py` are the blocking pair; if a future change wants them quiet, it needs a
    different mechanism and this test is where that argument has to be had."""
    for blocking in ("final_gate_stop.py", "quota_stop.py"):
        p = HOOKS / blocking
        if not p.is_file():
            continue
        assert "FABRIK_HEADLESS" not in p.read_text(encoding="utf-8"), (
            f"{blocking} BLOCKS an exit and must not be switchable by an env var"
        )


@pytest.mark.parametrize("name", ADVISORY)
def test_the_hook_still_runs_when_the_flag_is_absent(name: str) -> None:
    """...or the guard has simply disabled the hook. Exit 0 either way (both are advisory), so
    the discriminator is that the code path is REACHED — proven by the flag-set case printing
    nothing while this one is free to print."""
    rc, _out = _run(HOOKS / name, {"FABRIK_HEADLESS": ""})
    assert rc == 0


def test_every_headless_claude_spawn_sets_the_flag() -> None:
    """The guard is inert unless the SPAWNER declares the run headless. Both `claude -p` call
    sites in this repo are headless by construction — a worker whose stdout is a log file, and a
    worker whose stdout is parsed as JSON (where a hook banner is a parse hazard, not just
    noise). Graded on the producer: the flag has to be in the env each one passes."""
    root = Path(__file__).resolve().parents[1]
    for rel in ("scripts/ci_fix_dispatcher.py", "scripts/rivals_run.py"):
        src = (root / rel).read_text(encoding="utf-8")
        assert '"claude"' in src, f"{rel} no longer spawns claude — re-point this grader"
        assert '"FABRIK_HEADLESS": "1"' in src, (
            f"{rel} spawns a headless claude turn without declaring it, so the advisory hooks "
            "still pay for banners nobody reads"
        )
        assert "**os.environ" in src, (
            f"{rel} must EXTEND the environment, never replace it — a bare env= drops PATH, "
            "the account pointer and the mesh markers"
        )
