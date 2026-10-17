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
#   1. re-asserts a RUNTIME-only total ceiling on the shared slice `fabrik-tests.slice`
#      (FABRIK_TEST_SLICE_MAX, default 12G): every capped run on the box — nested or concurrent —
#      shares that total, so the HOST stays bounded; nothing persists past the user manager;
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
set -u

die() { echo "capped_run: $*" >&2; exit 2; }

mem=${FABRIK_TEST_MEM_MAX:-4G}
tmo=${FABRIK_TEST_TIMEOUT:-1800}
slice=${FABRIK_TEST_SLICE:-fabrik-tests.slice}
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

# A size is <digits><K|M|G>, at least 1M: 0 would be a ceiling that kills everything.
size_ok() {
  case "$1" in
    *[!0-9KMG]* | "" ) return 1 ;;
  esac
  local n=${1%[KMG]} unit=${1##*[0-9]}
  [ -n "$unit" ] && [ "$n" = "${1%?}" ] || return 1
  case "$n" in "" | 0* | *[!0-9]*) return 1 ;; esac
  case "$unit" in K) [ "$n" -ge 1024 ] ;; M | G) [ "$n" -ge 1 ] ;; *) return 1 ;; esac
}
size_ok "$mem" || die "bad memory ceiling '$mem' (--mem / FABRIK_TEST_MEM_MAX: e.g. 512M or 4G, at least 1M)"
size_ok "$slice_max" || die "bad slice ceiling '$slice_max' (FABRIK_TEST_SLICE_MAX: e.g. 12G, at least 1M)"
case "$tmo" in "" | 0* | *[!0-9]*) die "bad timeout '$tmo' (--timeout / FABRIK_TEST_TIMEOUT: a positive number of seconds)" ;; esac

if [ -z "${XDG_RUNTIME_DIR:-}" ] && [ -S "/run/user/$(id -u)/bus" ]; then
  export XDG_RUNTIME_DIR="/run/user/$(id -u)"  # cron and stripped hook envs lack it (C5)
fi

if ! command -v systemd-run >/dev/null 2>&1 || ! command -v systemctl >/dev/null 2>&1 \
  || ! systemctl --user set-property --runtime "$slice" "MemoryMax=$slice_max" MemorySwapMax=0 >/dev/null 2>&1; then
  echo "capped_run: WARNING — no reachable user systemd manager; running UNCAPPED (no memory ceiling): $*" >&2
  exec timeout --foreground --kill-after=10 "$tmo" "$@"
fi

unit="fabrik-test-$$-${RANDOM}${RANDOM}"
cleanup() { systemctl --user stop "$unit.scope" >/dev/null 2>&1; }
trap cleanup EXIT
trap 'exit 143' TERM INT HUP

# Backgrounded + waited so bash prints no "Killed" job line for a ceiling kill; stdin is handed on
# explicitly because a non-interactive shell points a background job's stdin at /dev/null.
# --foreground keeps <cmd> in the CALLER's process group, so a caller's group kill (kaizen_outcomes'
# killpg) reaches the whole tree; a tree that escapes it is still ended by the scope's RuntimeMaxSec.
exec 3<&0
timeout --foreground --kill-after=10 "$((tmo + 30))" systemd-run --user --scope -q --slice="$slice" --unit="$unit" \
  -p "MemoryMax=$mem" -p MemorySwapMax=0 -p "RuntimeMaxSec=$tmo" -- "$@" <&3 &
wait "$!" 2>/dev/null  # the job notice is the shell's own stderr at wait; <cmd>'s stderr is untouched
rc=$?

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
