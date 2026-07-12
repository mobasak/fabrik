#!/usr/bin/env bash
# install-docker-user-rules.sh <ssh-host> [--dry-run] — install the DOCKER-USER chain + its boot unit on an
# ALREADY-BOOTSTRAPPED fleet host. Idempotent. Replicates `bootstrap-vps.sh` step_10 exactly.
#
# WHY: Docker inserts its own FORWARD rules and therefore **bypasses UFW** — a container that publishes a port
# is reachable from the internet even when UFW would deny it. `DOCKER-USER` is the one chain Docker consults
# before its own rules, so it is where mesh-only ports get blocked from the public interface.
#
# DRIFT this fixes (found by /fabrik-docs-review 2026-07-12): vps2 + vps3 had NO
# `iptables-docker-user.service` and an EMPTY `DOCKER-USER` chain, despite the docs claiming step_10 installs
# it. Not an exposure at the time (the only Docker-published spoke ports were Traefik 80/443, intentionally
# public) — but any future spoke container publishing a mesh-only port would have been wide open.
#
# The rules (identical to step_10, and the port list is SOURCED from bootstrap-config.sh so it can never
# drift from the canonical one):
#   1. ACCEPT  everything arriving on the mesh iface (wg0)            → spokes trust the mesh
#   2. DROP    tcp dports <FABRIK_MESH_ONLY_PORTS> on the public iface → mesh-only services never public
# 80/443/22 are NOT in the drop list, so Traefik and SSH are unaffected.
#
# Usage:  scripts/sysadmin/install-docker-user-rules.sh vps2 [--dry-run]
# AFTER-EDIT: docs/infrastructure/vps-fleet-architecture.md
set -euo pipefail

HOST="${1:?usage: install-docker-user-rules.sh <ssh-host> [--dry-run]}"
DRY=0
[ "${2:-}" = "--dry-run" ] && DRY=1

HERE="$(cd "$(dirname "$0")" && pwd)"
# Single source of truth for the mesh iface + mesh-only port list (same file bootstrap-vps.sh step_10 reads).
# shellcheck disable=SC1091
source "${HERE}/../bootstrap/bootstrap-config.sh"

MESH_IFACE="${FABRIK_MESH_IFACE}"
PORTS_CSV="$(IFS=,; echo "${FABRIK_MESH_ONLY_PORTS[*]}")"

PUBLIC_IFACE="$(ssh "$HOST" "ip route get 1.1.1.1 | awk '/dev/ {print \$5; exit}'")"
[ -n "$PUBLIC_IFACE" ] || PUBLIC_IFACE="$FABRIK_PUBLIC_IFACE_DEFAULT"

echo "== DOCKER-USER rules → $HOST =="
echo "   mesh iface   : $MESH_IFACE"
echo "   public iface : $PUBLIC_IFACE"
echo "   mesh-only    : $PORTS_CSV"
echo "   rules:"
echo "     iptables -I DOCKER-USER -i $MESH_IFACE -j ACCEPT"
echo "     iptables -I DOCKER-USER -i $PUBLIC_IFACE -p tcp -m multiport --dports $PORTS_CSV -j DROP"
if [ "$DRY" = 1 ]; then echo "   [dry-run] nothing applied"; exit 0; fi

TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT

cat > "$TMP/add-docker-user-rules.sh" <<EOF
#!/bin/bash
# DOCKER-USER rules — installed by scripts/sysadmin/install-docker-user-rules.sh (mirrors bootstrap-vps.sh
# step_10). Run at boot by iptables-docker-user.service (After=docker.service). Idempotent.
iptables -C DOCKER-USER -i ${MESH_IFACE} -j ACCEPT 2>/dev/null || iptables -I DOCKER-USER -i ${MESH_IFACE} -j ACCEPT
iptables -C DOCKER-USER -i ${PUBLIC_IFACE} -p tcp -m multiport --dports ${PORTS_CSV} -j DROP 2>/dev/null || iptables -I DOCKER-USER -i ${PUBLIC_IFACE} -p tcp -m multiport --dports ${PORTS_CSV} -j DROP
EOF

cat > "$TMP/rm-docker-user-rules.sh" <<EOF
#!/bin/bash
iptables -D DOCKER-USER -i ${MESH_IFACE} -j ACCEPT 2>/dev/null || true
iptables -D DOCKER-USER -i ${PUBLIC_IFACE} -p tcp -m multiport --dports ${PORTS_CSV} -j DROP 2>/dev/null || true
EOF

cat > "$TMP/iptables-docker-user.service" <<'EOF'
[Unit]
Description=Docker-User iptables rules (block external access to internal ports)
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
ExecStart=/etc/iptables/add-docker-user-rules.sh
ExecStop=/etc/iptables/rm-docker-user-rules.sh
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF

scp -q "$TMP/add-docker-user-rules.sh" "$TMP/rm-docker-user-rules.sh" "$TMP/iptables-docker-user.service" "$HOST:/tmp/"
ssh "$HOST" '
  set -e
  sudo mkdir -p /etc/iptables
  sudo install -m 755 -o root -g root /tmp/add-docker-user-rules.sh /etc/iptables/add-docker-user-rules.sh
  sudo install -m 755 -o root -g root /tmp/rm-docker-user-rules.sh  /etc/iptables/rm-docker-user-rules.sh
  sudo install -m 644 -o root -g root /tmp/iptables-docker-user.service /etc/systemd/system/iptables-docker-user.service
  rm -f /tmp/add-docker-user-rules.sh /tmp/rm-docker-user-rules.sh /tmp/iptables-docker-user.service
  sudo systemctl daemon-reload
  sudo systemctl enable --now iptables-docker-user.service
  echo "  enabled=$(systemctl is-enabled iptables-docker-user.service) active=$(systemctl is-active iptables-docker-user.service)"
'
echo "   live DOCKER-USER chain:"
ssh "$HOST" 'sudo iptables -L DOCKER-USER -n --line-numbers' | sed 's/^/     /'
echo "== $HOST done =="
