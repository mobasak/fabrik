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
      # MASKED: one device down, ANOTHER still up — the only shape in which a membership test
      # that matches the wrong line is observable. Without this arm the fail-open half of the BRE
      # bug could be fully reintroduced with the whole suite green (proven by a review seat).
      [ "${FAIL_ON:-}" = "swapoff_masked" ] && {
        printf 'Filename\tType\tSize\tUsed\tPriority\n/swapZimg partition 33554432 512 -3\n' > "$AGENT_MEMORY_SWAPS"
        echo "swapoff: /swapZimg: Cannot allocate memory" >&2; exit 1; }
      # PARTIAL: devices really went down, THEN it failed — the multi-device ENOMEM shape
      [ "${FAIL_ON:-}" = "swapoff_partial" ] && {
        printf 'Filename\tType\tSize\tUsed\tPriority\n' > "$AGENT_MEMORY_SWAPS"
        echo "swapoff: /dev/sdd: Cannot allocate memory" >&2; exit 1; }
      printf 'Filename\tType\tSize\tUsed\tPriority\n' > "$AGENT_MEMORY_SWAPS"; exit 0 ;;
    swapon)
      nxt="${args[$((i+1))]:-}"
      # ⚠️ The read-only usability probe is checked FIRST: `swapon --show` mutates nothing, so a
      # test asking for the MUTATING swapon to fail must not also break the probe — otherwise the
      # script refuses up front and the graded path never runs.
      [ "$nxt" = "--show" ] && exit 0
      [ "${FAIL_ON:-}" = "swapon" ] && { echo "swapon: device busy" >&2; exit 1; }
      # `-a` with an fstab that has no swap entry: a silent, successful no-op
      [ "$nxt" = "-a" ] && exit 0
      # ⚠️ EBUSY on an ALREADY-ACTIVE device, as the real swapon does. Without this the stub made
      # re-enabling a live device look free, so deleting the intactness guard was undetectable —
      # one of seven fixes a review seat mutated away with the whole suite staying green.
      grep -qxF -- "$nxt" <(awk 'NR>1 && $1!="" {gsub(/\\\\040/," ",$1); print $1}' \
        "$AGENT_MEMORY_SWAPS" 2>/dev/null) && {
          echo "swapon: $nxt: Device or resource busy" >&2; exit 255; }
      # a DEVICE argument actually restores it — APPEND, because a multi-device box restores one
      # at a time and an overwriting stub would silently wipe the device restored a moment ago
      [ -s "$AGENT_MEMORY_SWAPS" ] || printf 'Filename\tType\tSize\tUsed\tPriority\n' > "$AGENT_MEMORY_SWAPS"
      printf '%s partition 67108864 0 -2\n' "$nxt" >> "$AGENT_MEMORY_SWAPS"; exit 0 ;;
  esac
done
exit 0
"""
# exit 1 = "no claude processes", i.e. an IDLE box, so reclaim actually proceeds
PGREP_IDLE = "#!/usr/bin/env bash\nexit 1\n"
PGREP_BUSY = "#!/usr/bin/env bash\necho 4242\n"


class _Stub:
    """pathlib.Path defines __slots__, so the fake /proc/swaps cannot be attached to it."""

    def __init__(self, bindir, swaps, meminfo=None, sysctl=None, conf=None):
        self.dir = bindir
        self.swaps_file = swaps
        self.meminfo = meminfo
        self.sysctl = sysctl
        self.conf = conf

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
    # ⚠️ PIN /proc/meminfo TOO. Without this, 9 of 10 tests read the LIVE box, and on a box with
    # nothing swapped `cmd_reclaim` returns early at "nothing swapped out" — so the headline
    # grader passed against the KNOWN-DANGEROUS `swapon -a` script, because the code path it
    # grades never ran. A review seat proved it: green on an idle box, red on this one.
    meminfo = tmp_path / "meminfo"
    meminfo.write_text(
        "MemTotal:       49309316 kB\nMemAvailable:   27000000 kB\n"
        "SwapTotal:      67108864 kB\nSwapFree:       52757592 kB\n"
    )
    sysctl = tmp_path / "sysctl_stub"
    sysctl.write_text(SYSCTL_STUB)
    sysctl.chmod(0o755)
    conf = tmp_path / "policy.conf"      # never the real /etc/sysctl.d file
    return _Stub(b, swaps, meminfo, sysctl, conf)


def _clean_env(**extra):
    """⚠️ Scrub the seams from the ambient environment. `dict(os.environ, ...)` inherited FAIL_ON,
    DRIFT and every AGENT_MEMORY_*, so an operator who exported one while debugging got a suite
    that lied — proven: `FAIL_ON=swapon pytest` turned two tests red."""
    base = {
        k: v for k, v in os.environ.items()
        if not k.startswith("AGENT_MEMORY_") and k not in ("FAIL_ON", "DRIFT")
    }
    base.update(extra)
    return base


def _run(stub_bin, *args, fail_on=None, busy=False):
    # ⚠️ Write the pgrep stub on EVERY call, not only when busy. Setting it once leaked BUSY state
    # into the next call in the same test, which then took the skip branch and never reached the
    # swapon failure it existed to prove — a green-looking test of the wrong path.
    (stub_bin / "pgrep").write_text(PGREP_BUSY if busy else PGREP_IDLE)
    (stub_bin / "pgrep").chmod(0o755)
    # ⚠️ Pin EVERY seam, not just the two this test is about. Leaving SYSCTL and CONF unpinned
    # meant `cron`'s drift check shelled the REAL sysctl and its policy compare read the REAL
    # /etc/sysctl.d file — so the test passed because THIS box has the policy installed, and would
    # fail on CI, a fresh clone, or this box before `install` had ever run. Proven by a seat:
    # point sysctl at a stub reporting kernel defaults and the grader goes red for a reason
    # unrelated to its claim.
    env = _clean_env(
        PATH=f"{stub_bin}:{os.environ['PATH']}",
        AGENT_MEMORY_SWAPS=str(stub_bin.swaps_file),
        AGENT_MEMORY_MEMINFO=str(stub_bin.meminfo),
        AGENT_MEMORY_SYSCTL=str(stub_bin.sysctl),
        AGENT_MEMORY_CONF=str(stub_bin.conf),
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
    # ⚠️ Assert the EXACT code, not merely "not 1". Mutating the skip branch from `return 10` to
    # `return 0` collapses skip into success — defeating the whole three-way contract — and an
    # `!= 1` assertion passes straight through it (proven by a review seat's mutation).
    assert r.returncode == 10, f"a benign skip is rc 10, got {r.returncode}"


def test_cron_never_touches_swap(stub_bin):
    """⚠️ THE COBRA. `cron` always exiting 0 is right for a skip — weekly_catchup.sh stamps only
    on success, so a non-zero there would re-run hourly and flip the liveness surface DEAD every
    night the operator happens to be working. It is WRONG for a box that just lost its swap: that
    must break the heartbeat, which is the only signal anyone would ever see.
    """
    before = stub_bin.swaps_file.read_text()
    r = _run(stub_bin, "cron", busy=False)          # an IDLE box: the old code would have reclaimed
    assert r.returncode == 0, f"{r.stdout}{r.stderr}"
    assert "reclaiming" not in r.stdout, f"the daily job must never swapoff:\n{r.stdout}"
    assert stub_bin.swaps_file.read_text() == before, "the daily job changed swap state"


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
    # ⚠️ Prove the graded path EXECUTED. Without this the assertion below is satisfied by
    # `cmd_reclaim` returning early at "nothing swapped out" — the fixture then still lists the
    # device and the test passes against a script that never restores anything.
    assert "reclaiming" in r.stdout, f"the swapoff path never ran:\n{r.stdout}{r.stderr}"
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
    env = _clean_env(
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
    conf = tmp_path / "conf"
    conf.write_text("vm.swappiness = 10\n")  # a good file that tee's O_TRUNC would destroy
    env = _clean_env(PATH=f"{stub_bin}:{os.environ['PATH']}", AGENT_MEMORY_CONF=str(conf))
    r = subprocess.run(
        ["bash", str(SCRIPT), "install"], capture_output=True, text=True, env=env, timeout=120
    )
    assert r.returncode != 0, f"a failed install must not exit 0:\n{r.stdout}{r.stderr}"
    # ⚠️ Two SEPARATE assertions. As `A or B` the second disjunct was always true (the script
    # prints "install FAILED" on this path), so the first was never load-bearing — a mutant that
    # printed "installed <path>" after a failed write passed.
    assert "installed" not in r.stdout.lower(), f"must not claim success:\n{r.stdout}"
    assert "FAILED" in (r.stdout + r.stderr), r.stdout + r.stderr
    # and the pre-existing good file must survive tee's O_TRUNC
    assert conf.read_text() == "vm.swappiness = 10\n", "a failed install destroyed the live policy"


@pytest.mark.parametrize("failing", ["mv", "sysctl"])
def test_install_reports_failure_from_every_privileged_step(stub_bin, tmp_path, failing):
    """`cmd_install` has three failure branches — tee, mv, and the final `sysctl -p`. Only the tee
    one was covered, so a regression in either of the others would have gone unnoticed while the
    function still printed success."""
    (stub_bin / "sudo").write_text(
        "#!/usr/bin/env bash\n"
        f'for a in "$@"; do [ "$a" = "{failing}" ] && exit 1; done\n'
        "exit 0\n"
    )
    (stub_bin / "sudo").chmod(0o755)
    env = _clean_env(
        PATH=f"{stub_bin}:{os.environ['PATH']}",
        AGENT_MEMORY_CONF=str(tmp_path / "conf"),
    )
    r = subprocess.run(
        ["bash", str(SCRIPT), "install"], capture_output=True, text=True, env=env, timeout=120
    )
    assert r.returncode != 0, f"a failed {failing} must not exit 0:\n{r.stdout}{r.stderr}"
    assert "FAILED" in (r.stdout + r.stderr), r.stdout + r.stderr


def test_a_partial_swapoff_re_asserts_every_device_it_took_down(stub_bin):
    """⚠️ `swapoff -a` walks devices one at a time and can fail PART-WAY (ENOMEM on a later one),
    so a non-zero rc does NOT mean "state unchanged" — devices are already down. That is the only
    shape in which the swapoff-failed path's re-assert loop is observable, and it is why asserting
    merely that the word FAILED appeared was not enough: a review seat deleted the whole loop and
    the old assertion stayed green, because on a CLEAN swapoff failure the stub never removed
    anything and `/dev/sdc in swaps` passed trivially.
    """
    r = _run(stub_bin, "reclaim", fail_on="swapoff_partial")
    assert r.returncode != 0, r.stdout + r.stderr
    assert "/dev/sdc" in stub_bin.swaps_file.read_text(), (
        "a partial swapoff must re-assert what it took down:\n" + r.stdout + r.stderr
    )


SYSCTL_STUB = """#!/usr/bin/env bash
# $DRIFT=1 reports kernel DEFAULTS (policy not in effect); otherwise the policy's own values.
if [ "$1" = "-n" ]; then
  case "$2" in
    vm.swappiness)             [ "${DRIFT:-}" = 1 ] && echo 60     || echo 10 ;;
    vm.vfs_cache_pressure)     [ "${DRIFT:-}" = 1 ] && echo 100    || echo 200 ;;
    vm.min_free_kbytes)        [ "${DRIFT:-}" = 1 ] && echo 45056  || echo 262144 ;;
    vm.watermark_scale_factor) [ "${DRIFT:-}" = 1 ] && echo 10     || echo 100 ;;
    *) echo "" ;;
  esac
fi
exit 0
"""


def _cron(stub_bin, tmp_path, drift, busy=True):
    sysctl = tmp_path / "sysctl_stub"
    sysctl.write_text(SYSCTL_STUB)
    sysctl.chmod(0o755)
    (stub_bin / "pgrep").write_text(PGREP_BUSY if busy else PGREP_IDLE)
    (stub_bin / "pgrep").chmod(0o755)
    conf = tmp_path / "conf"
    env = _clean_env(
        PATH=f"{stub_bin}:{os.environ['PATH']}",
        AGENT_MEMORY_SWAPS=str(stub_bin.swaps_file),
        AGENT_MEMORY_MEMINFO=str(stub_bin.meminfo),
        AGENT_MEMORY_CONF=str(conf),
        AGENT_MEMORY_SYSCTL=str(sysctl),
        DRIFT="1" if drift else "0",
    )
    return subprocess.run(
        ["bash", str(SCRIPT), "cron"], capture_output=True, text=True, env=env, timeout=120
    )


def test_cron_withholds_the_stamp_when_the_policy_is_not_in_effect(stub_bin, tmp_path):
    """⚠️ THE COBRA COUNTER-MEASURE, which shipped with ZERO graders — and could not have had one,
    because the script PREPENDS /usr/sbin to PATH, so a stubbed `sysctl` could never be reached.
    That is why it needed the `AGENT_MEMORY_SYSCTL` seam: without it the check is unfalsifiable,
    and an unfalsifiable check is indistinguishable from an absent one. A review seat deleted the
    entire drift block and all ten graders stayed green.
    """
    drifted = _cron(stub_bin, tmp_path, drift=True)
    assert drifted.returncode != 0, f"drift must withhold the stamp:\n{drifted.stdout}{drifted.stderr}"
    assert "POLICY NOT IN EFFECT" in (drifted.stdout + drifted.stderr)

    ok = _cron(stub_bin, tmp_path, drift=False)
    assert ok.returncode == 0, f"no drift must stamp:\n{ok.stdout}{ok.stderr}"
    assert "NOT IN EFFECT" not in (ok.stdout + ok.stderr)


def test_a_refused_swapoff_on_an_intact_box_is_benign_not_critical(stub_bin):
    """⚠️ A REGRESSION THIS REVIEW INTRODUCED, then caught. `swapoff -a` failing usually means
    NOTHING came down — and re-asserting a device that is still active returns EBUSY. The first
    cut reported that as CRITICAL, returned 1, withheld the stamp and sent the runner into an
    hourly retry loop on a perfectly healthy box. Intact swap must read benign.
    """
    r = _run(stub_bin, "reclaim", fail_on="swapoff")
    assert r.returncode == 11, f"an intact box is benign (rc 11), got {r.returncode}:\n{r.stdout}{r.stderr}"
    assert "CRITICAL" not in (r.stdout + r.stderr), r.stdout + r.stderr
    assert "/dev/sdc" in stub_bin.swaps_file.read_text()


def test_a_swapoff_is_refused_when_there_is_nothing_to_restore_with(stub_bin):
    """⚠️ Found by mutating each behaviour in turn and checking the suite noticed: removing this
    guard was the ONE mutation of nine that no grader caught.

    If /proc/swaps lists no device, the restore loop has nothing to put back — so running
    `swapoff -a` anyway would be the one-way trip this whole fix exists to prevent, just reached by
    a different door. The guard must refuse, and refusing must be benign (rc 10), not a failure
    that breaks the heartbeat.
    """
    stub_bin.swaps_file.write_text("Filename\tType\tSize\tUsed\tPriority\n")
    r = _run(stub_bin, "reclaim")
    assert r.returncode == 10, f"expected a benign refusal, got {r.returncode}:\n{r.stdout}{r.stderr}"
    assert "no device to restore" in r.stdout, r.stdout
    assert "reclaiming" not in r.stdout, f"the swapoff must NOT have run:\n{r.stdout}"


def test_an_intact_box_is_detected_even_when_the_device_name_is_not_a_plain_literal(stub_bin):
    """⚠️ TWO CRITICALS IN ONE LINE, both introduced by an earlier round of this very review. The
    intactness test grepped the RAW /proc/swaps for the UN-ESCAPED name and interpolated it as a
    BASIC REGEX. It broke both ways: a swap file with a space (`/swap\\040file`) or any regex
    metacharacter false-alarmed CRITICAL and broke the heartbeat on a healthy box; and `/swap.img`
    MATCHED the surviving `/swapZimg` line, so a device that really went down was reported as
    "swap is intact" and the run stamped GREEN.
    """
    stub_bin.swaps_file.write_text(
        "Filename\tType\tSize\tUsed\tPriority\n/swap\\040file partition 67108864 1024 -2\n"
    )
    r = _run(stub_bin, "reclaim", fail_on="swapoff")
    assert "CRITICAL" not in (r.stdout + r.stderr), (
        "an escaped/space-bearing name on an INTACT box must not read as critical:\n"
        + r.stdout + r.stderr
    )
    assert r.returncode == 11, f"expected benign rc 11, got {r.returncode}"


def test_a_device_that_stayed_down_is_never_masked_by_another_devices_line(stub_bin):
    """The fail-OPEN half: `/swap.img`'s pattern matched `/swapZimg` because `.` is a BRE wildcard,
    so a genuinely-down device read as intact and the heartbeat stayed green."""
    stub_bin.swaps_file.write_text(
        "Filename\tType\tSize\tUsed\tPriority\n"
        "/swap.img partition 33554432 512 -2\n/swapZimg partition 33554432 512 -3\n"
    )
    # swapoff_partial takes everything down, then fails — so both must be put back
    r = _run(stub_bin, "reclaim", fail_on="swapoff_partial")
    back = stub_bin.swaps_file.read_text()
    assert "/swap.img" in back, f"a downed device was masked and never restored:\n{r.stdout}{r.stderr}\n{back}"


def test_an_unusable_sudo_is_critical_not_benign(stub_bin):
    """⚠️ rc 11 means "the kernel refused", never "sudo could not run". Under cron a sudo failure
    made swapoff fail, every device read as still-active, and the run returned benign rc 11 — so a
    job that could never work stamped GREEN indefinitely."""
    (stub_bin / "sudo").write_text("#!/usr/bin/env bash\necho 'sudo: a terminal is required' >&2\nexit 1\n")
    (stub_bin / "sudo").chmod(0o755)
    r = _run(stub_bin, "reclaim")  # every sudo call fails, including the usability probe
    assert r.returncode == 1, f"an unusable sudo is CRITICAL, got {r.returncode}:\n{r.stdout}{r.stderr}"
    assert "sudo is not usable" in (r.stdout + r.stderr)


def test_status_says_question_mark_rather_than_a_confident_zero(stub_bin, tmp_path):
    """A missing /proc/meminfo key must not be laundered into `0.00 GB`, which is indistinguishable
    from a true zero in the only human-readable output this job produces."""
    bad = tmp_path / "bad_meminfo"
    bad.write_text("MemTotal:       49309316 kB\n")   # no Swap*/Anon*/Cached keys at all
    env = _clean_env(
        PATH=f"{stub_bin}:{os.environ['PATH']}",
        AGENT_MEMORY_SWAPS=str(stub_bin.swaps_file),
        AGENT_MEMORY_MEMINFO=str(bad),
        AGENT_MEMORY_SYSCTL=str(stub_bin.sysctl),   # the last unpinned seam
        AGENT_MEMORY_CONF=str(stub_bin.conf),
    )
    r = subprocess.run(["bash", str(SCRIPT), "status"], capture_output=True, text=True,
                       env=env, timeout=120)
    assert "?" in r.stdout, f"an absent key must print '?', not a number:\n{r.stdout}"
    assert "0.00 GB in use" not in r.stdout, f"confident zero from a missing key:\n{r.stdout}"


def test_an_indented_policy_line_is_still_verified(stub_bin, tmp_path):
    """⚠️ The drift check required the line to START with `vm.`, so an indented one was skipped
    entirely — yet `sysctl -p` applies it. A cosmetic edit disabled the cobra counter-measure for
    that key, silently."""
    src = SCRIPT.read_text().replace("\nvm.swappiness = 10\n", "\n  vm.swappiness = 10\n", 1)
    mutant = tmp_path / "indented.sh"
    mutant.write_text(src)
    sysctl = tmp_path / "sysctl_stub"
    sysctl.write_text(SYSCTL_STUB)
    sysctl.chmod(0o755)
    (stub_bin / "pgrep").write_text(PGREP_BUSY)
    (stub_bin / "pgrep").chmod(0o755)
    env = _clean_env(
        PATH=f"{stub_bin}:{os.environ['PATH']}",
        AGENT_MEMORY_SWAPS=str(stub_bin.swaps_file),
        AGENT_MEMORY_MEMINFO=str(stub_bin.meminfo),
        AGENT_MEMORY_CONF=str(tmp_path / "c"),
        AGENT_MEMORY_SYSCTL=str(sysctl),
        DRIFT="1",
    )
    r = subprocess.run(["bash", str(mutant), "cron"], capture_output=True, text=True,
                       env=env, timeout=120)
    assert "vm.swappiness" in (r.stdout + r.stderr), (
        "an indented policy line must still be checked:\n" + r.stdout + r.stderr
    )


def test_a_downed_device_is_not_masked_when_another_survives(stub_bin):
    """⚠️ Finding 3. The previous grader for this used a stub that truncated the WHOLE swaps file,
    so nothing could mask anything and the assertion passed trivially — a seat reintroduced the
    entire BRE bug with 21 of 21 green. This arm leaves `/swapZimg` up while `/swap.img` goes
    down, which is the only shape where a membership test matching the wrong line is observable.
    """
    stub_bin.swaps_file.write_text(
        "Filename\tType\tSize\tUsed\tPriority\n"
        "/swap.img partition 33554432 512 -2\n/swapZimg partition 33554432 512 -3\n"
    )
    r = _run(stub_bin, "reclaim", fail_on="swapoff_masked")
    back = stub_bin.swaps_file.read_text()
    assert "/swap.img" in back, f"a downed device was masked by the survivor:\n{r.stdout}{r.stderr}\n{back}"
    assert "swap is intact" not in (r.stdout + r.stderr), (
        "it must not claim the box is intact when a device came down:\n" + r.stdout + r.stderr
    )


def test_a_partial_swapoff_says_devices_came_down(stub_bin):
    """Finding 7. The message distinguishing a repaired partial swapoff from an untouched box had
    no grader — it could revert to the old, wrong 'nothing was taken down' undetected."""
    r = _run(stub_bin, "reclaim", fail_on="swapoff_partial")
    # ⚠️ Assert on a string UNIQUE to the branch. "came down" also appears in the unconditional
    # "swapoff FAILED — checking whether anything came down" printed before any branch is chosen,
    # so the assertion was already satisfied and the behaviour was never observed: a seat replaced
    # the whole partial-swapoff message and 25 of 25 stayed green. Third instance of this class in
    # this review — a grader is not coverage until a mutation kills it.
    assert "in a partial swapoff" in (r.stdout + r.stderr), (
        "a repaired partial swapoff must say so, not 'nothing was taken down':\n" + r.stdout + r.stderr
    )


def test_an_unreadable_swaps_file_refuses_rather_than_reporting_it_empty(stub_bin):
    """Finding 8. 'cannot read it' and 'it is empty' are different facts and the script
    distinguishes them for /proc/meminfo; the guard doing the same for /proc/swaps had no grader."""
    stub_bin.swaps_file.chmod(0o000)
    try:
        r = _run(stub_bin, "reclaim")
    finally:
        stub_bin.swaps_file.chmod(0o644)
    assert r.returncode == 10, f"expected a benign refusal, got {r.returncode}:\n{r.stdout}{r.stderr}"
    assert "cannot read" in r.stdout, f"must say it could not READ it:\n{r.stdout}"


def test_a_device_name_with_a_tab_is_matched_against_its_own_line(stub_bin):
    """⚠️ Findings 1+2. The capture un-escaped all four kernel escapes while the membership test
    un-escaped only \\040, so a tab- or backslash-named device never matched its own line: the
    script then ran swapon on a STILL-ACTIVE device, got EBUSY, and cried CRITICAL on a healthy
    box. Both now go through one helper."""
    stub_bin.swaps_file.write_text(
        "Filename\tType\tSize\tUsed\tPriority\n/tab\\011file partition 33554432 512 -2\n"
    )
    r = _run(stub_bin, "reclaim", fail_on="swapoff")
    assert r.returncode == 11, f"an intact box with a tab-named device is benign: {r.returncode}\n{r.stdout}{r.stderr}"
    assert "CRITICAL" not in (r.stdout + r.stderr), r.stdout + r.stderr

    # ...and on the path where the name is actually HANDED to swapon, it must be the un-escaped
    # one. With a single helper the two lists can no longer diverge, so the remaining question is
    # whether the un-escaping itself is right — which only this path can answer.
    stub_bin.swaps_file.write_text(
        "Filename\tType\tSize\tUsed\tPriority\n/tab\\011file partition 33554432 512 -2\n"
    )
    ok = _run(stub_bin, "reclaim")
    assert ok.returncode == 0, f"{ok.stdout}{ok.stderr}"
    assert "/tab\tfile" in stub_bin.swaps_file.read_text(), (
        "swapon must receive the UN-ESCAPED name, not the literal \\011 token:\n"
        + stub_bin.swaps_file.read_text()
    )


def test_a_broken_pgrep_refuses_rather_than_reporting_no_sessions(stub_bin):
    """⚠️ Finding F2. `pgrep -x claude | wc -l` took the pipeline's rc from `wc`, always 0, so a
    BROKEN pgrep reported zero sessions and the swapoff ran with agents live. The guard now reads
    pgrep's own rc — but shipped with no grader, so it could silently revert."""
    (stub_bin / "pgrep").write_text("#!/usr/bin/env bash\nexit 2\n")   # neither 0 (match) nor 1 (none)
    (stub_bin / "pgrep").chmod(0o755)
    env = _clean_env(
        PATH=f"{stub_bin}:{os.environ['PATH']}",
        AGENT_MEMORY_SWAPS=str(stub_bin.swaps_file),
        AGENT_MEMORY_MEMINFO=str(stub_bin.meminfo),
        AGENT_MEMORY_SYSCTL=str(stub_bin.sysctl),
        AGENT_MEMORY_CONF=str(stub_bin.conf),
    )
    before = stub_bin.swaps_file.read_text()
    r = subprocess.run(["bash", str(SCRIPT), "reclaim"], capture_output=True, text=True,
                       env=env, timeout=120)
    assert r.returncode == 10, f"a broken pgrep must refuse, got {r.returncode}:\n{r.stdout}{r.stderr}"
    assert "pgrep failed" in r.stdout, r.stdout
    assert stub_bin.swaps_file.read_text() == before, "the swapoff ran despite an unusable pgrep"


def test_a_dash_prefixed_policy_line_is_still_verified(stub_bin, tmp_path):
    """Finding F3. A leading `-` means ignore-errors to sysctl, NOT a comment — the line is still
    applied, so the drift check must still verify it."""
    src = SCRIPT.read_text().replace("\nvm.swappiness = 10\n", "\n-vm.swappiness = 10\n", 1)
    mutant = tmp_path / "dash.sh"
    mutant.write_text(src)
    (stub_bin / "pgrep").write_text(PGREP_BUSY)
    (stub_bin / "pgrep").chmod(0o755)
    env = _clean_env(
        PATH=f"{stub_bin}:{os.environ['PATH']}",
        AGENT_MEMORY_SWAPS=str(stub_bin.swaps_file),
        AGENT_MEMORY_MEMINFO=str(stub_bin.meminfo),
        AGENT_MEMORY_CONF=str(tmp_path / "c"),
        AGENT_MEMORY_SYSCTL=str(stub_bin.sysctl),
        DRIFT="1",
    )
    r = subprocess.run(["bash", str(mutant), "cron"], capture_output=True, text=True,
                       env=env, timeout=120)
    # ⚠️ Assert on the DRIFT line, not the bare key: cmd_status prints all four knob NAMES in its
    # status block, so `"vm.swappiness" in output` is satisfied whether the drift check ran or not.
    # Fourth instance in this review of an assertion matched by text printed somewhere else.
    assert "NOT IN EFFECT — vm.swappiness" in (r.stdout + r.stderr), (
        "a `-`-prefixed policy line is applied by sysctl and must still be checked:\n"
        + r.stdout + r.stderr
    )
