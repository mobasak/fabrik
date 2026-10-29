#!/usr/bin/env bash
# AFTER-EDIT: docs/workstation/wsl-net-heartbeat.md
# wsl_net_heartbeat.sh — WSL proves its own network to the Windows NAT watchdog (W-960d68a8).
#
# The operator's WSL-NatWatchdog used to launch `wsl.exe … curl` to probe WSL's network; about one
# run in seven left an orphaned /init relay holding hv_sock channels forever (W-97557e65). This
# script, run every minute by wsl-net-heartbeat.timer, writes two files on the Windows drive instead:
#   wsl-net-ran — touched on EVERY run: the heartbeat itself is alive;
#   wsl-net-ok  — touched only when the probe fetches (curl -f: any HTTP status below 400).
# The watchdog reads whether each file's LastWriteTime CHANGED since its previous check.
#
# A probe failure is an outage, not a fault: curl's own reason goes to stderr (the journal) and the
# run exits 0, so the unit is not failed every minute of an outage. Only a failed touch exits nonzero.
set -euo pipefail

dir="${WSL_NET_HEARTBEAT_DIR:-/mnt/c/Users/user/hotel-wifi}"
url="${WSL_NET_HEARTBEAT_URL:-http://www.msftconnecttest.com/connecttest.txt}"

touch -- "$dir/wsl-net-ran"
if curl -sSf -m 5 -o /dev/null -- "$url"; then
  touch -- "$dir/wsl-net-ok"
fi
