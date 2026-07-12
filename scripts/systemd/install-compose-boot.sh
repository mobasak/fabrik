#!/usr/bin/env bash
# install-compose-boot.sh <ssh-host> [--run|--dry-run] — install + enable the fabrik-compose-boot boot unit
# on a fleet host (hub or spoke). Idempotent. Closes the reboot race (see fabrik-compose-boot.sh).
#
#   ./install-compose-boot.sh vps            # install + enable for next boot (no live sweep)
#   ./install-compose-boot.sh vps --dry-run  # + run the discovery dry-run to verify stack detection
#   ./install-compose-boot.sh vps --run      # + run a live `up -d` reconcile now (may recreate drifted ctrs)
#
# AFTER-EDIT: scripts/systemd/README.md
set -euo pipefail
HOST="${1:?usage: install-compose-boot.sh <ssh-host> [--run|--dry-run]}"
MODE="${2:-}"
HERE="$(cd "$(dirname "$0")" && pwd)"

echo "== fabrik-compose-boot → $HOST =="
scp -q "$HERE/fabrik-compose-boot.sh" "$HERE/fabrik-compose-boot.service" "$HOST:/tmp/"
ssh "$HOST" '
  set -e
  sudo install -m 755 -o root -g root /tmp/fabrik-compose-boot.sh /usr/local/bin/fabrik-compose-boot.sh
  sudo install -m 644 -o root -g root /tmp/fabrik-compose-boot.service /etc/systemd/system/fabrik-compose-boot.service
  rm -f /tmp/fabrik-compose-boot.sh /tmp/fabrik-compose-boot.service
  sudo systemctl daemon-reload
  sudo systemctl enable fabrik-compose-boot.service >/dev/null 2>&1
  echo "  installed; enabled=$(systemctl is-enabled fabrik-compose-boot.service)"
  sudo systemd-analyze verify /etc/systemd/system/fabrik-compose-boot.service && echo "  unit verify: OK"
'
case "$MODE" in
  --dry-run) echo "-- discovery dry-run --"; ssh "$HOST" 'sudo /usr/local/bin/fabrik-compose-boot.sh --dry-run' ;;
  --run)     echo "-- live reconcile (up -d) --"; ssh "$HOST" 'sudo systemctl start fabrik-compose-boot.service && sudo journalctl -u fabrik-compose-boot.service -n 40 --no-pager' ;;
esac
echo "== $HOST done =="
