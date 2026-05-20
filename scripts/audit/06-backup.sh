#!/bin/bash
# Backup & disaster recovery audit data collection — runs ON the VPS via SSH.
# Usage: ssh vps 'bash -s' < scripts/audit/06-backup.sh
set -uo pipefail

echo "========== BACKREST CONTAINER =========="
BACKREST=$(docker ps --filter name=backrest --format "{{.Names}}" | head -1)
if [ -n "$BACKREST" ]; then
  echo "status: $(docker inspect "$BACKREST" --format "{{.State.Status}}" 2>/dev/null)"
  echo "uptime: $(docker inspect "$BACKREST" --format "{{.State.StartedAt}}" 2>/dev/null)"
else
  echo "BACKREST NOT RUNNING"
fi

echo ""
echo "========== BACKREST CONFIG =========="
if [ -f /opt/backrest/config/config.json ]; then
  python3 -c "
import json
cfg=json.load(open('/opt/backrest/config/config.json'))
print('=== Repos ===')
for r in cfg.get('repos',[]):
    print(f\"  {r.get('id','?'):20s} uri={r.get('uri','?')[:60]}\")
print()
print('=== Plans ===')
for p in cfg.get('plans',[]):
    paths = ', '.join(p.get('paths',[]))
    cron = p.get('schedule',{}).get('cron','none')
    retention = p.get('retention',{})
    print(f\"  {p.get('id','?'):30s}\")
    print(f\"    repo={p.get('repo','?')}\")
    print(f\"    paths={paths}\")
    print(f\"    schedule={cron}\")
    print(f\"    retention={retention}\")
    print()
  " 2>/dev/null
else
  echo "config not found at /opt/backrest/config/config.json"
fi

echo ""
echo "========== RECENT BACKUP ACTIVITY =========="
if [ -n "$BACKREST" ]; then
  sudo docker logs "$BACKREST" 2>&1 | grep -iE "backup|snapshot|error|fail|success" | tail -30
else
  echo "no backrest container"
fi

echo ""
echo "========== DOCKER VOLUMES =========="
echo "--- all volumes ---"
sudo docker volume ls --format "{{.Name}}" | sort
echo ""
echo "--- critical volume sizes ---"
for vol in $(docker volume ls --format "{{.Name}}" | grep -iE "postgres|redis|wp_content|db_data|authelia|grafana|loki|backrest"); do
  size=$(du -sh "/var/lib/docker/volumes/${vol}/_data/" 2>/dev/null | cut -f1)
  echo "$vol: $size"
done

echo ""
echo "========== SECRETS BACKUP =========="
echo "--- /opt/fabrik/.env ---"
if [ -f /opt/fabrik/.env ]; then
  echo "exists, $(wc -l < /opt/fabrik/.env) lines, $(stat --format=%Y /opt/fabrik/.env | xargs -I{} date -d @{} '+%Y-%m-%d %H:%M') last modified"
else
  echo "MISSING"
fi
echo "--- /opt/fabrik/backups/ ---"
ls -la /opt/fabrik/backups/ 2>/dev/null || echo "no backups dir"

echo ""
echo "========== COOLIFY STATE =========="
du -sh /data/coolify/ 2>/dev/null || echo "/data/coolify not found"
echo "--- services ---"
ls /data/coolify/services/ 2>/dev/null | wc -l
echo "--- applications ---"
ls /data/coolify/applications/ 2>/dev/null | wc -l

echo ""
echo "========== CRITICAL CONFIG FILES =========="
for f in \
  "/var/lib/docker/volumes/hks48k8sg8o4co4co08co00o_authelia-config/_data/configuration.yml" \
  "/opt/monitoring/configs/prometheus/prometheus.yml" \
  "/opt/monitoring/configs/prometheus/rules/alerts.yml" \
  "/opt/monitoring/configs/grafana/provisioning/datasources/fabrik.yaml" \
  "/opt/monitoring/configs/gatus/_base.yaml" \
  "/opt/monitoring/configs/loki/loki-config.yaml" \
  "/opt/monitoring/configs/promtail/promtail-config.yaml" \
  "/opt/monitoring/configs/alertmanager/alertmanager.yml" \
  "/etc/docker/daemon.json" \
  "/opt/backrest/config/config.json"; do
  if [ -f "$f" ]; then
    size=$(stat --format=%s "$f" 2>/dev/null)
    mod=$(stat --format=%Y "$f" 2>/dev/null | xargs -I{} date -d @{} '+%Y-%m-%d %H:%M')
    echo "OK: $f ($size bytes, modified $mod)"
  else
    echo "MISSING: $f"
  fi
done

echo ""
echo "========== POSTGRES DATABASES =========="
sudo docker exec $(docker ps --filter name=postgres-main --format "{{.Names}}" | head -1) psql -U postgres -t -c "SELECT datname, pg_size_pretty(pg_database_size(datname)) FROM pg_database WHERE datname NOT IN ('postgres','template0','template1')" 2>/dev/null || echo "cannot query postgres"

echo ""
echo "========== END =========="
