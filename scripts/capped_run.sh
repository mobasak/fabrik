#!/usr/bin/env bash
# capped_run.sh — run ONE command (a test suite, as a rule) under kernel-enforced caps (W-162398ef).
#
#   capped_run.sh [--mem SIZE] [--timeout SECS] -- <cmd> [args...]
#
# Why: on 2026-10-17 a test process grew to ~32 GB (about 300 MB/s) and took the whole WSL box,
# and every session on it, down twice. A per-test timeout cannot stop that in time; a cgroup
# memory ceiling can, because the kernel enforces it on the whole process tree.
#
# What it does, every launch:
#   0. ADMISSION BAND (W-6e656dac L5): while MemAvailable < 3 GiB or memory PSI `some avg10` > 10 the
#      start waits, up to FABRIK_TEST_ADMIT_WAIT seconds (default 300), then starts anyway and says so;
#      an unreadable meminfo or PSI (read through the FABRIK_PROC_ROOT seam, default /proc) starts at
#      once and says so. Exit codes and the "killed at the memory ceiling" prefix are untouched;
#   1. re-asserts a RUNTIME-only total ceiling on the shared slice `fabrik-agents-tests.slice`
#      (FABRIK_TEST_SLICE_MAX, default 12G). systemd reads the dash as nesting, so the slice sits
#      INSIDE `fabrik-agents.slice` and that parent's MemoryHigh/MemoryMax bound the test jobs too:
#      every capped run on the box — nested or concurrent — shares that total; nothing persists past
#      the user manager;
#   2. runs <cmd> in a named scope in that slice with its own ceiling (--mem / FABRIK_TEST_MEM_MAX,
#      default 4G), no swap, and RuntimeMaxSec (--timeout / FABRIK_TEST_TIMEOUT, default 1800 s),
#      under coreutils `timeout` as a backstop;
#   3. reads the scope's Result: `oom-kill` → exit 137 with a "killed at the memory ceiling" line,
#      `timeout` → exit 124; otherwise <cmd>'s own exit code.
# No reachable user manager → <cmd> runs UNCAPPED with a stderr WARNING (the one fail direction:
# an answer that names its risk). Never `ulimit -v`/RLIMIT_AS: it kills chromium at launch.
# A malformed or zero bound → exit 2.
#
# Cobra (D-253): the cheapest way past "tests run capped" is to launch bare; the rule (CLAUDE.md
# HARD STOPS) plus the hub suite's own in-process guard (tests/memguard.py) and the capped gate leg
# are the counters. The slice name (FABRIK_TEST_SLICE) exists so the tests never touch the shared one.
# Cobra on the admission band: the cheapest pass is FABRIK_TEST_ADMIT_WAIT=0 (no wait at all); the wait
# is bounded on purpose (a stuck box must not hang every gate), and each expired or skipped band is SAID.
set -u

die() { echo "capped_run: $*" >&2; exit 2; }

mem=${FABRIK_TEST_MEM_MAX:-4G}
tmo=${FABRIK_TEST_TIMEOUT:-1800}
slice=${FABRIK_TEST_SLICE:-fabrik-agents-tests.slice}
slice_max=${FABRIK_TEST_SLICE_MAX:-12G}

while [ $# -gt 0 ]; do
  case "$1" in
    --mem) [ $# -ge 2 ] || die "--mem needs a SIZE"; mem=$2; shift 2 ;;
    --timeout) [ $# -ge 2 ] || die "--timeout needs SECS"; tmo=$2; shift 2 ;;
    --) shift; break ;;
    *) die "unknown option '$1' (usage: capped_run.sh [--mem SIZE] [--timeout SECS] -- <cmd>)" ;;
  esac
done
[ $# -gt 0 ] || die "no command given after --"

# A size is <digits><K|M|G>, 1M to 999999999G: 0 would be a ceiling that kills everything, and a
# longer number overflows systemd's parser (it would fail later with an unrelated exit code).
size_ok() {
  case "$1" in
    *[!0-9KMG]* | "" ) return 1 ;;
  esac
  local n=${1%[KMG]} unit=${1##*[0-9]}
  [ -n "$unit" ] && [ "$n" = "${1%?}" ] || return 1
  case "$n" in "" | 0* | *[!0-9]* | ??????????*) return 1 ;; esac
  case "$unit" in K) [ "$n" -ge 1024 ] ;; M | G) [ "$n" -ge 1 ] ;; *) return 1 ;; esac
}
size_ok "$mem" || die "bad memory ceiling '$mem' (--mem / FABRIK_TEST_MEM_MAX: e.g. 512M or 4G, 1M to 999999999G)"
size_ok "$slice_max" || die "bad slice ceiling '$slice_max' (FABRIK_TEST_SLICE_MAX: e.g. 12G, 1M to 999999999G)"
# 1 s to 7 days: a longer limit is no limit, and a huge one wraps the backstop's arithmetic
case "$tmo" in "" | 0* | *[!0-9]* | ???????*) die "bad timeout '$tmo' (--timeout / FABRIK_TEST_TIMEOUT: 1 to 604800 seconds)" ;; esac
[ "$tmo" -le 604800 ] || die "bad timeout '$tmo' (--timeout / FABRIK_TEST_TIMEOUT: 1 to 604800 seconds)"
case "$slice" in *[!A-Za-z0-9_.-]* | "" | -*) die "bad slice name '$slice' (FABRIK_TEST_SLICE)" ;; *.slice) ;;
  *) die "bad slice name '$slice' (FABRIK_TEST_SLICE must end in .slice)" ;; esac

admit_wait=${FABRIK_TEST_ADMIT_WAIT:-300}
case "$admit_wait" in *[!0-9]* | ?????*) die "bad admission wait '$admit_wait' (FABRIK_TEST_ADMIT_WAIT: 0 to 9999 seconds)" ;; esac
proc=${FABRIK_PROC_ROOT:-/proc}

# The admission band: prints why the box is busy (rc 0), nothing when it is fine (rc 1), or why the band cannot
# be judged (rc 2) — an unreadable meminfo or PSI is never read as "busy".
admit_busy() {
  local kb psi
  kb=$(awk '/^MemAvailable:/ { print $2; exit }' "$proc/meminfo" 2>/dev/null)
  psi=$(awk '/^some / { for (i = 2; i <= NF; i++) if ($i ~ /^avg10=/) { sub("avg10=", "", $i); print $i; exit } }' "$proc/pressure/memory" 2>/dev/null)
  case "$kb" in "" | *[!0-9]*) echo "meminfo ($proc/meminfo) has no MemAvailable"; return 2 ;; esac
  case "$psi" in "" | *[!0-9.]*) echo "memory PSI ($proc/pressure/memory) has no 'some avg10'"; return 2 ;; esac
  if [ "$kb" -lt 3145728 ]; then echo "MemAvailable $((kb / 1024)) MiB < 3 GiB"; return 0; fi
  if awk -v p="$psi" 'BEGIN { exit !(p + 0 > 10) }'; then echo "memory PSI some avg10=$psi > 10"; return 0; fi
  return 1
}
waited=0
announced=0
while why=$(admit_busy); rc_admit=$?; [ "$rc_admit" = 0 ]; do
  if [ "$waited" -ge "$admit_wait" ]; then
    echo "capped_run: admission: starting anyway after ${waited}s — still busy ($why): $*" >&2
    break
  fi
  if [ "$announced" = 0 ]; then
    echo "capped_run: admission: waiting up to ${admit_wait}s — $why" >&2
    announced=1
  fi
  sleep 1
  waited=$((waited + 1))
done
[ "$rc_admit" = 2 ] && echo "capped_run: admission: unreadable — $why; starting at once" >&2

if [ -z "${XDG_RUNTIME_DIR:-}" ] && [ -S "/run/user/$(id -u)/bus" ]; then
  export XDG_RUNTIME_DIR="/run/user/$(id -u)"  # cron and stripped hook envs lack it (C5)
fi
# A closed stdin (cron, hooks) becomes /dev/null — for <cmd>, and for systemctl, which fails without one.
{ exec 3<&0; } 2>/dev/null || { exec 0</dev/null; exec 3</dev/null; }

# UNCAPPED only when there is genuinely no user manager to ask. A manager that answers but refuses
# the slice ceiling is an error, never a silent fall-through to no cap at all.
if ! command -v systemd-run >/dev/null 2>&1 || ! command -v systemctl >/dev/null 2>&1 \
  || ! systemctl --user show-environment >/dev/null 2>&1; then
  echo "capped_run: WARNING — no reachable user systemd manager; running UNCAPPED (no memory ceiling): $*" >&2
  exec timeout --foreground --kill-after=10 "$tmo" "$@" <&3 3<&-
fi
if ! err=$(systemctl --user set-property --runtime "$slice" "MemoryMax=$slice_max" MemorySwapMax=0 2>&1); then
  die "the user manager refused the slice ceiling ($slice MemoryMax=$slice_max): $err"
fi

unit="fabrik-test-$$-${RANDOM}${RANDOM}"
cleanup() {
  systemctl --user stop "$unit.scope" >/dev/null 2>&1
  systemctl --user reset-failed "$unit.scope" >/dev/null 2>&1
}
trap cleanup EXIT
trap 'exit 143' TERM INT HUP

# Backgrounded + waited so bash prints no "Killed" job line for a ceiling kill; stdin is handed on
# explicitly (fd 3, closed again for <cmd>) because a non-interactive shell points a background
# job's stdin at /dev/null.
# --foreground keeps <cmd> in the CALLER's process group, so a caller's group kill (kaizen_outcomes'
# killpg) reaches the whole tree; a tree that escapes it is still ended by the scope's RuntimeMaxSec,
# and TimeoutStopSec=5 turns a stop the tree ignores into a SIGKILL 5 s later (the default is 90 s).
timeout --foreground --kill-after=10 "$((tmo + 30))" systemd-run --user --scope -q --slice="$slice" --unit="$unit" \
  -p "MemoryMax=$mem" -p MemorySwapMax=0 -p "RuntimeMaxSec=$tmo" -p TimeoutStopSec=5 -- "$@" <&3 3<&- &
wait "$!" 2>/dev/null  # the job notice is the shell's own stderr at wait; <cmd>'s stderr is untouched
rc=$?

# The scope can still be stopping when <cmd> has exited: read Result once it has settled (≤ 5 s),
# or the verdict is missed and the unit is left `failed` behind its reset.
for _ in 1 2 3 4 5 6 7 8 9 10; do
  case "$(systemctl --user show "$unit.scope" -p ActiveState --value 2>/dev/null)" in
    active | deactivating | activating) sleep 0.5 ;;
    *) break ;;
  esac
done
result=$(systemctl --user show "$unit.scope" -p Result --value 2>/dev/null)
systemctl --user reset-failed "$unit.scope" >/dev/null 2>&1
case "$result" in
  oom-kill)
    echo "capped_run: killed at the memory ceiling ($mem per run, $slice_max for $slice) — $*" >&2
    exit 137 ;;
  timeout)
    echo "capped_run: stopped at the ${tmo}s time limit — $*" >&2
    exit 124 ;;
esac
exit "$rc"
