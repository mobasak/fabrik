#!/usr/bin/env bash
# AFTER-EDIT: docs/workstation/session-history-retention.md | docs/development/plans/2026-09-06-plan-1-session-history-retention.md
# install_session_archive_timer.sh — install the session-history archive timer (plan A.7, D-565).
#
# Run from the MAIN checkout after the archiver change is merged: the unit runs
# /opt/fabrik/scripts/sysadmin/archive_transcripts.py, so installing it earlier would schedule
# whatever transport the main checkout still holds.
#
# Steps, each a hard stop on failure:
#   1. linger must be on — without it the user manager (and so the timer and its catch-up)
#      does not start until somebody logs in;
#   2. systemd-analyze --user verify the three units (the archive service, its timer and its failure alert,
#      W-36687f76), refusing ANY output: a key in the wrong section is only a warning at rc 0;
#   3. copy them to ~/.config/systemd/user/ — the alert unit FIRST: verify does not resolve an OnFailure=
#      target (rc 0 for a missing one), so the archive unit must never land without it — then daemon-reload,
#      enable --now.
# Deletes nothing.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
units="$here/systemd"
dest="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
user="$(id -un)"

linger="$(loginctl show-user "$user" -p Linger 2>/dev/null || true)"
if [ "$linger" != "Linger=yes" ]; then
  echo "install_session_archive_timer: linger is off for $user (${linger:-no answer})." >&2
  echo "  Enable it once with: loginctl enable-linger $user" >&2
  exit 1
fi

# A missing unit file fails verify at rc 1, so nothing is installed without the alert unit; the `||` keeps `set -e`
# from exiting before verify's own words are printed.
verify_rc=0
said="$(systemd-analyze --user verify "$units/session-archive.service" "$units/session-archive.timer" \
  "$units/session-archive-alert.service" 2>&1)" || verify_rc=$?
if [ "$verify_rc" -ne 0 ] || [ -n "$said" ]; then
  echo "install_session_archive_timer: systemd-analyze verify exited $verify_rc or was not silent — nothing installed:" >&2
  printf '%s\n' "$said" >&2
  exit 1
fi

mkdir -p "$dest"
install -m 0644 "$units/session-archive-alert.service" "$dest/session-archive-alert.service"
install -m 0644 "$units/session-archive.service" "$dest/session-archive.service"
install -m 0644 "$units/session-archive.timer" "$dest/session-archive.timer"
systemctl --user daemon-reload
systemctl --user enable --now session-archive.timer
systemctl --user list-timers session-archive.timer --no-pager
