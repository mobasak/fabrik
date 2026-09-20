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

# ⚠️ The stub models the REAL asymmetry that `swapoff -a` / `swapon -a` have on this box:
# swapoff -a reads /proc/swaps and takes the device down; swapon -a reads /etc/fstab ONLY, which
# here has no swap entry, so it restores NOTHING and still exits 0. $AGENT_MEMORY_SWAPS is the fake
# /proc/swaps the stub maintains, so a test can assert whether swap actually came back.
SUDO_STUB = """#!/usr/bin/env bash
args=("$@")
for i in "${!args[@]}"; do
  case "${args[$i]}" in
    swapoff)
      [ "${FAIL_ON:-}" = "swapoff" ] && { echo "swapoff: Cannot allocate memory" >&2; exit 1; }
      printf 'Filename\tType\tSize\tUsed\tPriority\n' > "$AGENT_MEMORY_SWAPS"; exit 0 ;;
    swapon)
      [ "${FAIL_ON:-}" = "swapon" ] && { echo "swapon: device busy" >&2; exit 1; }
      nxt="${args[$((i+1))]:-}"
      # `-a` with an fstab that has no swap entry: a silent, successful no-op
      [ "$nxt" = "-a" ] && exit 0
      # a DEVICE argument actually restores it
      printf 'Filename\tType\tSize\tUsed\tPriority\n%s partition 67108864 0 -2\n' \
        "$nxt" > "$AGENT_MEMORY_SWAPS"; exit 0 ;;
  esac
done
exit 0
"""
# exit 1 = "no claude processes", i.e. an IDLE box, so reclaim actually proceeds
PGREP_IDLE = "#!/usr/bin/env bash\nexit 1\n"
PGREP_BUSY = "#!/usr/bin/env bash\necho 4242\n"


class _Stub:
    """pathlib.Path defines __slots__, so the fake /proc/swaps cannot be attached to it."""

    def __init__(self, bindir, swaps):
        self.dir = bindir
        self.swaps_file = swaps

    def __truediv__(self, name):
        return self.dir / name

    def __str__(self):
        return str(self.dir)


@pytest.fixture()
def stub_bin(tmp_path):
    b = tmp_path / "bin"
    b.mkdir()
    (b / "sudo").write_text(SUDO_STUB)
    (b / "pgrep").write_text(PGREP_IDLE)
    for f in b.iterdir():
        f.chmod(0o755)
    swaps = tmp_path / "swaps"
    swaps.write_text(
        "Filename\tType\tSize\tUsed\tPriority\n/dev/sdc partition 67108864 14351272 -2\n"
    )
    return _Stub(b, swaps)


def _run(stub_bin, *args, fail_on=None, busy=False):
    # ⚠️ Write the pgrep stub on EVERY call, not only when busy. Setting it once leaked BUSY state
    # into the next call in the same test, which then took the skip branch and never reached the
    # swapon failure it existed to prove — a green-looking test of the wrong path.
    (stub_bin / "pgrep").write_text(PGREP_BUSY if busy else PGREP_IDLE)
    (stub_bin / "pgrep").chmod(0o755)
    env = dict(
        os.environ,
        PATH=f"{stub_bin}:{os.environ['PATH']}",
        AGENT_MEMORY_SWAPS=str(stub_bin.swaps_file),
    )
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


def test_swap_is_restored_by_device_because_swapon_dash_a_reads_only_fstab(stub_bin):
    """⚠️ THE DEFECT THAT COULD DAMAGE THE MACHINE, found by the authoritative review seat.

    `swapoff -a` and `swapon -a` are NOT symmetric. swapoff -a takes down every device found in
    /proc/swaps; swapon -a activates only devices marked swap in /etc/fstab. On this box
    /etc/fstab has ZERO swap entries (swap is /dev/sdc, brought up by WSL init, with no systemd
    .swap unit either), so `swapon -a` restores NOTHING and still exits 0.

    An rc check therefore cannot catch it. On the first idle night the job would have taken 64 GB
    of swap down, restored none of it, printed "reclaimed.", stamped the heartbeat green, and left
    the box with ~16 GB anon and no swap backstop until a full `wsl --shutdown` — while
    cmd_status printed "swap 0.00 GB in use of 0.00 GB", which reads exactly like success.
    """
    r = _run(stub_bin, "reclaim")
    swaps = stub_bin.swaps_file.read_text()
    assert "/dev/sdc" in swaps, (
        "swap must be restored BY DEVICE — `swapon -a` cannot do it on this box:\n"
        f"{r.stdout}{r.stderr}\n/proc/swaps now:\n{swaps}"
    )
    assert r.returncode == 0, r.stdout + r.stderr


def test_a_swap_that_does_not_come_back_is_reported_as_critical(stub_bin):
    """If the per-device restore itself fails, the box has no swap and that must be LOUD and
    non-zero — it is the only signal anyone will see."""
    r = _run(stub_bin, "reclaim", fail_on="swapon")
    assert r.returncode != 0, r.stdout + r.stderr
    combined = (r.stdout + r.stderr).lower()
    assert "without swap" in combined or "critical" in combined, combined
    assert "reclaimed." not in r.stdout


def test_the_enomem_guard_fails_closed_when_meminfo_is_unreadable(stub_bin, tmp_path):
    """⚠️ The guard that refuses a swapoff which would abort half-way read `[ "$used" -gt "$avail" ]`
    with avail EMPTY when MemAvailable is missing. `[` then exits 2, `if` reads that as false, and
    the ELSE path is the swapoff — so the guard silently disabled itself in exactly the degraded
    condition it exists for. set -u does not catch it: the variable is set-but-empty, not unset."""
    fake = tmp_path / "meminfo"
    fake.write_text("MemTotal:       49309316 kB\nSwapTotal:      67108864 kB\nSwapFree:       52757592 kB\n")
    env = dict(
        os.environ,
        PATH=f"{stub_bin}:{os.environ['PATH']}",
        AGENT_MEMORY_SWAPS=str(stub_bin.swaps_file),
        AGENT_MEMORY_MEMINFO=str(fake),
    )
    r = subprocess.run(
        ["bash", str(SCRIPT), "reclaim"], capture_output=True, text=True, env=env, timeout=120
    )
    swaps = stub_bin.swaps_file.read_text()
    assert "/dev/sdc" in swaps, f"the swapoff must NOT have run:\n{r.stdout}{r.stderr}"
    assert r.returncode != 0, f"an unreadable meminfo must refuse, not proceed:\n{r.stdout}"


def test_install_does_not_claim_success_when_the_write_failed(stub_bin, tmp_path):
    """`tee` opens with O_TRUNC, so an ENOSPC write empties the policy file BEFORE failing — and
    `sysctl -p` on an empty file returns 0 with no output. The old code then printed
    'installed <path>' while the live policy silently reverted at the next boot."""
    failing = stub_bin / "sudo"
    failing.write_text("#!/usr/bin/env bash\nfor a in \"$@\"; do [ \"$a\" = tee ] && exit 1; done\nexit 0\n")
    failing.chmod(0o755)
    env = dict(os.environ, PATH=f"{stub_bin}:{os.environ['PATH']}", AGENT_MEMORY_CONF=str(tmp_path / "conf"))
    r = subprocess.run(
        ["bash", str(SCRIPT), "install"], capture_output=True, text=True, env=env, timeout=120
    )
    assert r.returncode != 0, f"a failed install must not exit 0:\n{r.stdout}{r.stderr}"
    assert "installed" not in r.stdout.lower() or "FAILED" in (r.stdout + r.stderr), r.stdout
