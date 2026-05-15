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
apply apprise-        768m   # bumped 2026-05-15: live at 80% of 512m, Lesson 6 was prescient
apply cadvisor-       512m
apply gatus-          256m
apply grafana-        512m
apply loki-           512m
apply netdata-        768m
apply node-exporter-  128m
apply promtail-       128m
apply prometheus      1g
apply redis-exporter      64m   # T3-01 follow-up 2026-05-15: previously unlimited
apply postgres-exporter   64m   # T3-01 follow-up 2026-05-15: previously unlimited

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

# Coolify control plane (host-internal — small footprint)
apply coolify-sentinel    64m   # T3-01 follow-up 2026-05-15: previously unlimited

# WordPress stack
apply ocoron-com-db-1         1g
apply ocoron-com-wordpress-1  512m
apply ocoron-com-nginx-1      256m
apply ocoron-com-redis-1      256m
apply ocoron-com-backup-1     128m  # T3-01 follow-up 2026-05-15: previously unlimited

echo "=== Done ==="

# Auto-update VPS docs after limits applied
echo "📝 Updating VPS docs..."
cd /opt/fabrik && python3 scripts/update_vps_docs.py 2>&1 | tail -5

# ── Stable Docker network aliases (Gatus DNS fix) ──────────────────────────
# Coolify single-image Applications generate UUID container names with no stable
# DNS alias. These `network connect --alias` calls add a stable name that Gatus
# and inter-service callers can rely on across redeploys.
# Run automatically on every VPS reboot via this script.
echo "Applying stable Docker network aliases..."

apply_alias() {
  local container=$1
  local alias=$2
  # Check container is running
  if ! sudo docker inspect "$container" &>/dev/null; then
    echo "  SKIP $alias: container $container not found"
    return
  fi
  # Disconnect then reconnect with alias (idempotent)
  sudo docker network disconnect coolify "$container" 2>/dev/null || true
  sudo docker network connect --alias "$alias" --alias "$container" coolify "$container" 2>/dev/null \
    && echo "  ✅ $alias → $container" \
    || echo "  ⚠️  $alias: connect failed (may already be connected)"
}

apply_alias vckgs8c00o40o884k48cgow8-220643454460 browserless
apply_alias e04k4sco44ow04ccc0o0k00k-151256201601  gotenberg
apply_alias bs0wo48k4gwo440gcowscoc8-150802066640  meilisearch
apply_alias glitchtip-web-z00kkck8c8cwo800kk440csk glitchtip-web
