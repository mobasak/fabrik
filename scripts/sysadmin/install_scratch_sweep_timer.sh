#!/usr/bin/env bash
# AFTER-EDIT: docs/workstation/cleanup-automation.md | tests/test_scratch_sweep_timer.py
# install_scratch_sweep_timer.sh — run the scratch janitor hourly from a systemd user timer (W-d1a4a8f5).
# The operator runs it once, from the MAIN checkout after merge.
#
# The timer is the PRIMARY scheduler; the 04:20 crontab line stays as the FALLBACK and is never touched:
# a user timer stops with the user manager, the failure D-1389's boot showed, while system cron needs no
# user session. The janitor's own lock makes the pair safe — a run that finds the other holding it exits 0
# having done nothing (scripts/scratch_sweep.py, `_Lock`).
#
# Steps, each a hard stop on failure:
#   1. linger must be on — without it the user manager (and so the timer) does not start until somebody logs in;
#   2. the janitor the unit's ExecStart= names must exist;
#   3. systemd-analyze --user verify both units, refusing ANY output (a misplaced key is only a warning at rc 0);
#   4. copy them to ~/.config/systemd/user/, daemon-reload, enable, restart, and require the timer `active` —
#      any of those failing disables the timer again, leaving cron as it was.
# Deletes nothing; never reads or writes the crontab.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
units="$here/systemd"
dest="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
user="$(id -un)"
me="install_scratch_sweep_timer"
undo="systemctl --user disable --now scratch-sweep.timer"
# the one ExecStart= line is `/usr/bin/python3 <janitor> --dead --apply`: check the path it will really run
janitor="$(sed -n 's|^ExecStart=/usr/bin/python3 \([^ ]*\) .*|\1|p' "$units/scratch-sweep.service")"

linger="$(loginctl show-user "$user" -p Linger 2>/dev/null || true)"
if [ "$linger" != "Linger=yes" ]; then
  echo "$me: linger is off for $user (${linger:-no answer})." >&2
  echo "  Enable it once with: loginctl enable-linger $user — then re-run this script." >&2
  exit 1
fi

if [ -z "$janitor" ] || [ ! -f "$janitor" ]; then
  echo "$me: the unit's janitor (${janitor:-no ExecStart=/usr/bin/python3 line}) does not exist — nothing installed." >&2
  exit 1
fi

verify_rc=0
said="$(systemd-analyze --user verify "$units/scratch-sweep.service" "$units/scratch-sweep.timer" 2>&1)" \
  || verify_rc=$?
if [ "$verify_rc" -ne 0 ] || [ -n "$said" ]; then
  echo "$me: systemd-analyze verify exited $verify_rc or was not silent — nothing installed:" >&2
  printf '%s\n' "$said" >&2
  exit 1
fi

mkdir -p "$dest"
install -m 0644 "$units/scratch-sweep.service" "$dest/scratch-sweep.service"
install -m 0644 "$units/scratch-sweep.timer" "$dest/scratch-sweep.timer"
# From here a failing step never ends the script through `set -e` with the timer enabled: each one
# disables it again, so cron's 04:20 line stays the one scheduler, and says so.
rollback() {
  echo "$me: $1 — disabling the timer again; cron's 04:20 line still runs the janitor." >&2
  $undo || echo "$me: the disable failed too — run by hand: $undo" >&2
  exit 1
}
systemctl --user daemon-reload || rollback "daemon-reload failed"
systemctl --user enable scratch-sweep.timer || rollback "enable failed"
systemctl --user restart scratch-sweep.timer || rollback "restart failed"
active="$(systemctl --user is-active scratch-sweep.timer 2>/dev/null || true)"
if [ "$active" != "active" ]; then
  rollback "scratch-sweep.timer is '${active:-no answer}', not active"
fi
systemctl --user list-timers scratch-sweep.timer --no-pager || true  # information only
echo "$me: the janitor now runs hourly at :20 (journalctl --user -u scratch-sweep.service); cron's 04:20 line stays as the fallback."
echo "To undo, run: $undo"
