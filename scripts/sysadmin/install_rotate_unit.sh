#!/usr/bin/env bash
# AFTER-EDIT: docs/workstation/session-history-retention.md | docs/workstation/hooks-index.md
# install_rotate_unit.sh [--check] — install (or check) the user systemd units that execute session rotations
# (W-f975fee0 slice 2, D-1135): fabrik-rotate.path watches ~/.claude/state/rotate-requests/*.json and starts
# fabrik-rotate.service, which runs `rotate_session.py execute`. Run from the MAIN checkout after the merge — the units
# point at /opt/fabrik/scripts/sysadmin/rotate_session.py. Idempotent. If the path unit ever reads `failed` (its own
# TriggerLimit, or the service's start limit), clear it with: systemctl --user reset-failed fabrik-rotate.path
# fabrik-rotate.service
set -euo pipefail
src="$(cd "$(dirname "$0")" && pwd)"
dst="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
units=(fabrik-rotate.path fabrik-rotate.service)
case "${1:-}" in "" | --check) ;; *) echo "usage: install_rotate_unit.sh [--check]" >&2; exit 2 ;; esac
if [ "${1:-}" = "--check" ]; then
  rc=0
  for u in "${units[@]}"; do
    if ! cmp -s "$src/$u" "$dst/$u"; then echo "install_rotate_unit: $u is not installed or differs from $src/$u"; rc=1; fi
  done
  state="$(systemctl --user is-active fabrik-rotate.path 2>/dev/null || true)"
  [ "$state" = active ] || { echo "install_rotate_unit: fabrik-rotate.path is ${state:-unknown}, not active"; rc=1; }
  [ "$rc" = 0 ] && echo "install_rotate_unit: installed and active"
  exit "$rc"
fi
req="$HOME/.claude/state/rotate-requests"
# install -d follows a symlink and chmods its target; refuse one, as rotate_session.py's _ensure_req_dir does
if [ -L "$req" ] || { [ -e "$req" ] && [ ! -d "$req" ]; }; then
  echo "install_rotate_unit: $req is not a plain directory — refusing" >&2
  exit 1
fi
mkdir -p "$dst"
install -d -m 0700 "$req"
for u in "${units[@]}"; do install -m 0644 "$src/$u" "$dst/$u"; done
systemctl --user daemon-reload
systemctl --user enable --now fabrik-rotate.path
echo "install_rotate_unit: fabrik-rotate.path enabled; requests in ~/.claude/state/rotate-requests/, outcomes in ~/.claude/state/rotations.jsonl"
