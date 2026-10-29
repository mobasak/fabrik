#!/usr/bin/env bash
# AFTER-EDIT: docs/workstation/wsl-net-heartbeat.md
# wsl_net_heartbeat.sh — WSL proves its own network to the Windows NAT watchdog (W-960d68a8).
#
# The operator's WSL-NatWatchdog used to launch `wsl.exe … curl` to probe WSL's network; about one
# run in seven left an orphaned /init relay holding hv_sock channels forever (W-97557e65). This
# script, run every minute by wsl-net-heartbeat.timer, writes two files on the Windows drive instead:
#   wsl-net-ran — touched when the probe RAN and its answer is about the network;
#   wsl-net-ok  — touched only when the probe fetched (curl -f: any HTTP status below 400).
# The watchdog reads whether each file's LastWriteTime CHANGED since its previous check: ran moved
# and ok still means "no network" (it may restart the WSL adapter); ran still means "the heartbeat
# is broken" (it only toasts).
#
# So curl's exit code is sorted three ways. 0 → both files. A network code → ran only, curl's reason
# to the journal, exit 0 (an outage is not a fault, so the unit is not failed every minute of one).
# Anything else — a malformed URL (3), curl missing (127), an option error — is a LOCAL fault an
# adapter restart cannot cure: neither file moves and the run exits 1. `-q` (it must come first)
# keeps a user's ~/.curlrc out of the probe. A failed write exits nonzero too.
set -euo pipefail

dir="${WSL_NET_HEARTBEAT_DIR:-/mnt/c/Users/user/hotel-wifi}"
url="${WSL_NET_HEARTBEAT_URL:-http://www.msftconnecttest.com/connecttest.txt}"

rc=0
said="$(curl -q -sSf -m 5 -o /dev/null -- "$url" 2>&1)" || rc=$?
case "$rc" in
  0)
    touch -- "$dir/wsl-net-ran" "$dir/wsl-net-ok"
    ;;
  # couldn't resolve proxy/host, couldn't connect, HTTP >= 400, timeout, TLS connect, empty reply,
  # send error, receive error — curl(1) EXIT CODES
  5 | 6 | 7 | 22 | 28 | 35 | 52 | 55 | 56)
    printf '%s\n' "$said" >&2
    touch -- "$dir/wsl-net-ran"
    ;;
  *)
    printf 'wsl_net_heartbeat: curl exited %s, a local fault, not an outage: %s\n' "$rc" "$said" >&2
    exit 1
    ;;
esac
