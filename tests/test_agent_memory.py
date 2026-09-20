"""Graders for scripts/sysadmin/agent_memory.sh — the workstation RAM policy (D-316).

Every test drives the REAL script with `sudo`, `pgrep` and `sysctl` stubbed onto PATH, so the
live box's swap and /etc are never touched. The stub decides which privileged leg "fails",
which is the only way to reach the branches that matter.
"""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "sysadmin" / "agent_memory.sh"

SUDO_STUB = """#!/usr/bin/env bash
for a in "$@"; do
  case "$a" in
    swapoff) [ "${FAIL_ON:-}" = "swapoff" ] && { echo "swapoff: Cannot allocate memory" >&2; exit 1; }
             echo "STUB swapoff"; exit 0 ;;
    swapon)  [ "${FAIL_ON:-}" = "swapon" ] && { echo "swapon: device busy" >&2; exit 1; }
             echo "STUB swapon"; exit 0 ;;
  esac
done
exit 0
"""
# exit 1 = "no claude processes", i.e. an IDLE box, so reclaim actually proceeds
PGREP_IDLE = "#!/usr/bin/env bash\nexit 1\n"
PGREP_BUSY = "#!/usr/bin/env bash\necho 4242\n"


@pytest.fixture()
def stub_bin(tmp_path):
    b = tmp_path / "bin"
    b.mkdir()
    (b / "sudo").write_text(SUDO_STUB)
    (b / "pgrep").write_text(PGREP_IDLE)
    for f in b.iterdir():
        f.chmod(0o755)
    return b


def _run(stub_bin, *args, fail_on=None, busy=False):
    # ⚠️ Write the pgrep stub on EVERY call, not only when busy. Setting it once leaked BUSY state
    # into the next call in the same test, which then took the skip branch and never reached the
    # swapon failure it existed to prove — a green-looking test of the wrong path.
    (stub_bin / "pgrep").write_text(PGREP_BUSY if busy else PGREP_IDLE)
    (stub_bin / "pgrep").chmod(0o755)
    env = dict(os.environ, PATH=f"{stub_bin}:{os.environ['PATH']}")
    if fail_on:
        env["FAIL_ON"] = fail_on
    return subprocess.run(
        ["bash", str(SCRIPT), *args], capture_output=True, text=True, env=env, timeout=120
    )


def test_a_failed_swapon_after_a_successful_swapoff_is_never_reported_as_success(stub_bin):
    """⚠️ THE MOST CONSEQUENTIAL FAILURE IN THIS SCRIPT, reproduced 2026-09-20 before the fix:
    `swapoff -a` succeeded, `swapon -a` failed, and the script printed "reclaimed." and returned
    0. The box is then running with NO SWAP and ~15.5 GB of anonymous memory, while the cron log
    and the exit code both say success — so weekly_catchup.sh stamps the run and the
    `agent-memory-policy` liveness surface reads LIVE. The next spike OOM-kills something and
    nothing anywhere reports why.
    """
    r = _run(stub_bin, "reclaim", fail_on="swapon")
    assert r.returncode != 0, f"a box left without swap must not exit 0:\n{r.stdout}{r.stderr}"
    assert "reclaimed." not in r.stdout, f"must not claim success:\n{r.stdout}"
    combined = r.stdout + r.stderr
    assert "swapon" in combined.lower() and (
        "without swap" in combined.lower() or "critical" in combined.lower()
    ), f"the operator must be told the box has no swap:\n{combined}"


def test_a_failed_swapoff_leaves_swap_on_and_says_so(stub_bin):
    """The SAFE failure: swapoff refused, so swap was never removed. It must re-enable and report,
    and it must not be confused with the dangerous case above."""
    r = _run(stub_bin, "reclaim", fail_on="swapoff")
    assert r.returncode != 0
    assert "reclaimed." not in r.stdout
    assert "FAILED" in (r.stdout + r.stderr)


def test_the_happy_path_still_reports_success(stub_bin):
    r = _run(stub_bin, "reclaim")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "reclaimed." in r.stdout


def test_a_live_session_skips_rather_than_failing(stub_bin):
    """A refused reclaim because agents are working is the EXPECTED nightly outcome. It must be
    distinguishable from a genuine failure, or the cron heartbeat cannot stay honest."""
    r = _run(stub_bin, "reclaim", busy=True)
    assert "skipped" in r.stdout.lower(), r.stdout
    assert r.returncode != 1, "a skip must not look like a crash"


def test_cron_stamps_on_a_skip_but_not_when_the_box_lost_its_swap(stub_bin):
    """⚠️ THE COBRA. `cron` always exiting 0 is right for a skip — weekly_catchup.sh stamps only
    on success, so a non-zero there would re-run hourly and flip the liveness surface DEAD every
    night the operator happens to be working. It is WRONG for a box that just lost its swap: that
    must break the heartbeat, which is the only signal anyone would ever see.
    """
    skip = _run(stub_bin, "cron", busy=True)
    assert skip.returncode == 0, f"a skip must stamp:\n{skip.stdout}{skip.stderr}"

    lost = _run(stub_bin, "cron", fail_on="swapon")
    assert lost.returncode != 0, (
        "cron must NOT stamp success after swapon failed — the box has no swap:\n"
        f"{lost.stdout}{lost.stderr}"
    )


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash required")
def test_the_script_is_syntactically_valid():
    assert subprocess.run(["bash", "-n", str(SCRIPT)], capture_output=True).returncode == 0
