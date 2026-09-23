#!/usr/bin/env bash
# AFTER-EDIT: docs/workstation/hooks-index.md | tests/test_selfwatch_arm.py | scripts/sysadmin/selfwatch_check.py
# selfwatch_arm.sh <session_id> — arm the resume-mesh self-watch as ONE background Bash task (D-356).
#
# The arm used to be `Monitor(persistent: true, …)`. Claude Code 2.1.280's Monitor has no persistent mode and
# ends every watch within 30 minutes (code.claude.com/docs/en/tools-reference), so each expiry woke the session
# for a re-arm turn and the watch lapsed between them. A background Bash task has no such deadline (measured:
# 13 min past the 10-min foreground cap, D-356) and re-invokes the session when it EXITS. So this runs the
# standing watcher unchanged and exits on its FIRST line — a wake, or the watcher's own refusal — after killing
# the watcher AND its children: a child `sleep` inherits the lock fd, and a lock held past the wake makes the
# re-arm read "already armed" and exit, leaving nothing armed.
#
# Arm: Bash(run_in_background: true, command: "bash /opt/fabrik/scripts/sysadmin/selfwatch_arm.sh <sid>")
# One wake per arm: after a wake the lock is free and selfwatch_check.py's arm order returns on the next prompt.
set -u
# The whole body is ONE function, called on the file's last line and followed by `exit`: bash then parses every
# byte before running any of it and never reads this file again. Unwrapped, an arm waiting at `read` for up to an
# hour resumed at its old byte offset in whatever the file held after an in-place edit and ran the new file's
# comments as commands (mail 01M36FPTT9YS7ADH3CYQ5MQ1P3; tests/test_selfwatch_arm.py pins it).
main() {
sid="${1:?session id}"
watcher="${SELFWATCH_BIN:-$HOME/.claude/bin/claude-selfwatch.sh}"
[ -f "$watcher" ] || { printf 'self-watch NOT armed: %s is missing\n' "$watcher"; exit 1; }
# pdeathsig: a SIGKILL of this wrapper runs no trap, so the watcher is told to die with its parent — an orphan would
# hold the lock (reads "armed") and print its wake into a dead pipe (review of D-356, A-S1)
# (util-linux; without it the arm still works and only loses that guard — never an arm that cannot hold, A-S4)
if command -v setpriv >/dev/null 2>&1; then
  coproc W { exec setpriv --pdeathsig TERM bash "$watcher" "$sid" 2>/dev/null; }
else
  coproc W { exec bash "$watcher" "$sid" 2>/dev/null; }
fi
pid=$W_PID
# Stop the watcher FIRST so it cannot fork, then kill its children, then it: a child `sleep` or `curl` holds the
# lock fd, and one forked between a `pkill -P` and the kill kept the lock past the wake. The watcher stays in this
# task's process group, so a kill of the background task reaches it too; the trap covers a TERM/HUP/INT to the arm
# — an orphaned watcher would hold the lock (reads "armed") and print its wake into a dead pipe.
stop_watch() {
  kill -STOP "$pid" 2>/dev/null
  pkill -TERM -P "$pid" 2>/dev/null
  kill -TERM "$pid" 2>/dev/null
  kill -CONT "$pid" 2>/dev/null
  wait "$pid" 2>/dev/null
}
trap 'stop_watch; exit 143' TERM HUP INT
IFS= read -r line <&"${W[0]}" || true  # at EOF read still fills `line` with what arrived (A-S5)
stop_watch
# EOF is not a wake: the watcher ended without a line, so nothing is armed — say so, and never order a re-arm into
# an arm that cannot hold (review of D-356 pass 2, A-S4)
[ -n "$line" ] || { printf 'self-watch NOT armed: %s exited without a line — check it by hand\n' "$watcher"; exit 1; }
# the watcher is a STANDING watch and says so ("… — this self-watch STAYS ARMED (… do NOT re-arm …)"); through
# this wrapper that clause is false — the watch ended — so it is cut, and the re-arm order below replaces it
line="${line%% — this self-watch STAYS ARMED*}"
printf '%s\n' "${line:-self-watch ended without a line}"
case "$line" in "self-watch already armed"*) exit 0 ;; esac  # the standing arm still holds the lock
printf 'This wake ENDED the watch (armed through selfwatch_arm.sh, one wake per arm) — re-arm it: Bash(run_in_background: true, command: "bash /opt/fabrik/scripts/sysadmin/selfwatch_arm.sh %s")\n' "$sid"
}
main "$@"; exit $?
