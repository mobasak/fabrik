#!/usr/bin/env bash
# vps_apply_limits.sh — apply Docker memory limits to all VPS containers
# Run after VPS reboot or after Coolify redeployments of infra services.
#
# Coolify gap (F5, 2026-05-16): Coolify v4.0.0-beta.459 stores `limits_memory`
# in its application config but does NOT translate that into the compose
# `deploy.resources.limits.memory` block it writes to disk. Docker therefore
# sees no limit (`HostConfig.Memory: 0` = unlimited).
#
# 2026-05-16 STATUS — F5 PERMANENT FIX APPLIED:
#   - 7 Coolify Applications (build_pack=dockercompose): deploy.resources.limits
#     committed to each service's git repo (translator, image-broker, captcha,
#     emailgateway, file-api, proxy, site-provisioner — file-worker already had
#     it). Coolify pulls the new compose on next redeploy.
#   - 12 Coolify Services (one-click stacks: apprise, netdata, grafana, loki,
#     promtail, node-exporter, cadvisor, alertmanager, postgres-main, n8n,
#     backrest, authelia): docker_compose_raw PATCHed via Coolify API
#     (scripts/coolify_services_f5.py). Effective on next redeploy.
#   - Scaffolder canonical compose (_write_canonical_compose) emits the deploy
#     block by default so NEW deployments are already correct.
#
# This script remains as a TRANSITIONAL stopgap: running containers were
# started from the OLD compose without limits. Until each service is
# redeployed once after F5, this script enforces the limit live via
# `docker update --memory`. After every service has been redeployed once,
# this script's main loop becomes a noop (the deploy block in compose will
# already enforce the limit). The script is safe to keep running indefinitely.
#
# Run pattern: `ssh vps "bash -s" < /opt/fabrik/scripts/vps_apply_limits.sh`

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
apply apprise-        1g     # bumped 2026-05-20: 615MB steady-state plateau, 768m was too tight (80%)
apply cadvisor-       512m
apply gatus-          256m
apply grafana-        512m
apply loki-           512m
apply netdata-        1g    # bumped 2026-05-16: live at 751/768m (97%), ContainerHighMemory alert firing
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

# Fabrik microservices — active services only.
# Destroyed services (captcha, emailgateway, file-api, file-worker,
# fabrik-proxy, translator) removed 2026-05-19.
apply image-broker-        512m  # spec: resources.limits.memory=512M
apply site-provisioner-    512m  # spec: resources.memory=512M

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

# Container names include timestamps that change on recreate.
# Use dynamic lookup by UUID prefix so this survives redeploys.
for pair in \
  "vckgs8c00o40o884k48cgow8:browserless" \
  "e04k4sco44ow04ccc0o0k00k:gotenberg" \
  "bs0wo48k4gwo440gcowscoc8:meilisearch" \
  "glitchtip-web-:glitchtip-web"; do
  prefix="${pair%%:*}"
  alias="${pair##*:}"
  container=$(sudo docker ps --format '{{.Names}}' | grep "^${prefix}" | head -1)
  if [ -n "$container" ]; then
    apply_alias "$container" "$alias"
  else
    echo "  SKIP $alias: no container matching ^${prefix}"
  fi
done
