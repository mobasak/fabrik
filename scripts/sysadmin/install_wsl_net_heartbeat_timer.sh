#!/usr/bin/env bash
# AFTER-EDIT: docs/workstation/wsl-net-heartbeat.md
# install_wsl_net_heartbeat_timer.sh — install the WSL network heartbeat timer (W-960d68a8).
#
# Run from the MAIN checkout after the change is merged: the unit runs
# /opt/fabrik/scripts/sysadmin/wsl_net_heartbeat.sh.
#
# Steps, each a hard stop on failure:
#   1. linger must be on — without it the user manager (and so the timer) does not start until somebody logs in;
#   2. the script the unit's ExecStart= names must exist — the unit runs it through bash, so verify no
#      longer checks it;
#   3. systemd-analyze --user verify both units, refusing ANY output: a key in the wrong section is only a
#      warning at rc 0;
#   4. copy them to ~/.config/systemd/user/, daemon-reload, enable, restart (a re-run then applies
#      changed timer settings; enable --now leaves a running timer on the old ones).
# Deletes nothing.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
units="$here/systemd"
dest="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
user="$(id -un)"
# The one ExecStart= line is `/usr/bin/bash <script>`: check the path the unit will really run.
script="$(sed -n 's|^ExecStart=/usr/bin/bash ||p' "$units/wsl-net-heartbeat.service")"

linger="$(loginctl show-user "$user" -p Linger 2>/dev/null || true)"
if [ "$linger" != "Linger=yes" ]; then
  echo "install_wsl_net_heartbeat_timer: linger is off for $user (${linger:-no answer})." >&2
  echo "  Enable it once with: loginctl enable-linger $user" >&2
  exit 1
fi

if [ -z "$script" ] || [ ! -f "$script" ]; then
  echo "install_wsl_net_heartbeat_timer: the unit's script (${script:-no ExecStart=/usr/bin/bash line}) does not exist — run this from the main checkout after merge (wsl_net_heartbeat.sh)." >&2
  exit 1
fi

verify_rc=0
said="$(systemd-analyze --user verify "$units/wsl-net-heartbeat.service" "$units/wsl-net-heartbeat.timer" 2>&1)" \
  || verify_rc=$?
if [ "$verify_rc" -ne 0 ] || [ -n "$said" ]; then
  echo "install_wsl_net_heartbeat_timer: systemd-analyze verify exited $verify_rc or was not silent — nothing installed:" >&2
  printf '%s\n' "$said" >&2
  exit 1
fi

mkdir -p "$dest"
install -m 0644 "$units/wsl-net-heartbeat.service" "$dest/wsl-net-heartbeat.service"
install -m 0644 "$units/wsl-net-heartbeat.timer" "$dest/wsl-net-heartbeat.timer"
systemctl --user daemon-reload
systemctl --user enable wsl-net-heartbeat.timer
systemctl --user restart wsl-net-heartbeat.timer
systemctl --user list-timers wsl-net-heartbeat.timer --no-pager
