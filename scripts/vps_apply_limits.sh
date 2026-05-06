#!/usr/bin/env bash
# vps_apply_limits.sh — apply Docker memory limits to all VPS containers
# Run after VPS reboot or after Coolify redeployments of infra services.
# Fabrik application limits are managed via Coolify API (limits_memory/limits_cpus).
# Infra services (Coolify-managed stacks) are set here via docker update.
# Usage: ssh vps "bash /opt/fabrik/scripts/vps_apply_limits.sh"

set -e

apply() {
  local pattern=$1 mem=$2
  local cont
  cont=$(sudo docker ps --format '{{.Names}}' | grep "^${pattern}" | head -1)
  if [ -z "$cont" ]; then
    echo "  NOT FOUND: $pattern"
    return
  fi
  sudo docker update --memory "$mem" --memory-swap "$mem" "$cont" > /dev/null 2>&1 \
    && echo "  ✅ $pattern → $mem" \
    || echo "  ❌ $pattern → failed"
}

echo "=== VPS resource limits ==="

# Observability
apply alertmanager-   256m
apply apprise-        256m
apply cadvisor-       256m
apply gatus-          256m
apply grafana-        512m
apply loki-           512m
apply netdata-        512m
apply node-exporter-  128m
apply promtail-       128m
apply prometheus      512m

# Auth & ops
apply authelia-       512m
apply backrest-       512m

# Data
apply postgres-main-  2g
apply redis-main      512m

# Automation
apply n8n-            2g

# Network
apply traefik         256m

# WordPress stack
apply ocoron-com-db-1         1g
apply ocoron-com-wordpress-1  512m
apply ocoron-com-nginx-1      256m
apply ocoron-com-redis-1      256m

echo "=== Done ==="
