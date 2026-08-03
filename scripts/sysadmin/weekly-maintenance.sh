#!/bin/bash
# Weekly preventive maintenance — runs Sunday 03:00 via cron.
# Performs safe, routine cleanup tasks that veteran sysadmins do every week.
# Reports what it did to Telegram.
#
# SAFETY: Only performs read-safe or explicitly safe operations.
# NEVER prunes volumes, NEVER deletes running containers.
#
# Cron: 0 3 * * 0 root /opt/fabrik/scripts/sysadmin/weekly-maintenance.sh

set -uo pipefail

PROJECT_DIR="/opt/fabrik"
REPORT=""

add_report() {
  REPORT+="$1
"
}

echo "$(date -Iseconds) Running weekly maintenance..."

add_report "🔧 Weekly Maintenance — $(date +%Y-%m-%d)"
add_report ""

# 1. Check dangling Docker images (from old deployments)
DANGLING_COUNT=$(sudo docker images -f dangling=true --format '{{.ID}}' | wc -l)
if [ "$DANGLING_COUNT" -gt 0 ]; then
  DANGLING_SIZE=$(sudo docker images -f dangling=true --format '{{.Size}}' | paste -sd+ | bc 2>/dev/null || echo "unknown")
  add_report "📦 Dangling images: $DANGLING_COUNT (not auto-cleaned — report only)"
else
  add_report "📦 Dangling images: 0 ✅"
fi

# 2. Check dangling volumes
DANG_VOL=$(sudo docker volume ls -f dangling=true --format '{{.Name}}' | wc -l)
if [ "$DANG_VOL" -gt 0 ]; then
  add_report "💾 Dangling volumes: $DANG_VOL (not auto-cleaned — report only)"
else
  add_report "💾 Dangling volumes: 0 ✅"
fi

# 3. Check journal size
JOURNAL_SIZE=$(sudo journalctl --disk-usage 2>/dev/null | grep -oP '\d+\.\d+[MGK]' || echo "unknown")
add_report "📝 Journal: $JOURNAL_SIZE"

# 4. Check /var/log size
LOG_SIZE=$(sudo du -sh /var/log/ 2>/dev/null | cut -f1)
add_report "📝 /var/log: $LOG_SIZE"

# 5. Check Docker disk usage
DOCKER_SIZE=$(sudo du -sh /var/lib/docker/ 2>/dev/null | cut -f1)
DISK_PERCENT=$(df -h / | tail -1 | awk '{print $5}')
add_report "🐳 Docker: $DOCKER_SIZE | Disk: $DISK_PERCENT"

# 6. Check backup freshness (Backrest last activity)
BACKREST=$(sudo docker ps --filter name=backrest --format '{{.Names}}' | head -1)
if [ -n "$BACKREST" ]; then
  LAST_BACKUP=$(sudo docker logs "$BACKREST" 2>&1 | grep -i "snapshot" | tail -1 | head -c 80)
  if [ -n "$LAST_BACKUP" ]; then
    add_report "💾 Last backup activity: $LAST_BACKUP"
  else
    add_report "⚠️ Backrest running but no recent snapshot in logs"
  fi
else
  add_report "🔥 Backrest NOT running!"
fi

# 7. Check container restart counts (any abnormal)
HIGH_RESTARTS=$(sudo docker inspect $(sudo docker ps -q) --format '{{.Name}} {{.RestartCount}}' 2>/dev/null | sed 's|/||' | awk '$2 > 3 {print $1 ": " $2 " restarts"}')
if [ -n "$HIGH_RESTARTS" ]; then
  add_report "⚠️ High restart counts:"
  add_report "$HIGH_RESTARTS"
else
  add_report "🔄 Container restarts: all normal ✅"
fi

# 8. Memory limits check — any unlimited containers?
UNLIMITED=$(sudo docker ps --format '{{.Names}}' | while read c; do
  mem=$(sudo docker inspect "$c" --format '{{.HostConfig.Memory}}' 2>/dev/null)
  [ "$mem" = "0" ] && echo "$c"
done | grep -v "^coolify" | wc -l)
add_report "🧠 Containers without memory limit (excl coolify): $UNLIMITED"

# 9. Check stale created/exited containers
STALE=$(sudo docker ps -a --filter status=created --filter status=exited --format '{{.Names}}' | wc -l)
if [ "$STALE" -gt 0 ]; then
  STALE_LIST=$(sudo docker ps -a --filter status=created --filter status=exited --format '{{.Names}} ({{.Status}})' | head -5)
  add_report "⚠️ Stale containers: $STALE"
  add_report "$STALE_LIST"
else
  add_report "🧹 Stale containers: 0 ✅"
fi

# 10. Cert expiry summary
add_report ""
add_report "🔒 TLS certs:"
for domain in ocoron.com status.vps1.ocoron.com monitor.vps1.ocoron.com errors.vps1.ocoron.com coolify.vps1.ocoron.com; do
  expiry=$(echo | timeout 5 openssl s_client -servername "$domain" -connect "$domain":443 2>/dev/null | openssl x509 -noout -enddate 2>/dev/null | cut -d= -f2)
  if [ -n "$expiry" ]; then
    days=$(( ($(date -d "$expiry" +%s) - $(date +%s)) / 86400 ))
    add_report "  $domain: ${days}d"
  fi
done 2>/dev/null

# ── Send report ───────────────────────────────────────────────────────────

ESCAPED=$(echo "$REPORT" | python3 -c "import sys,json; print(json.dumps(sys.stdin.read().strip()))")

# NOTE: this send was DEAD fleet-wide for months — it still said `--network coolify`
# (renamed `fabrik` 2026-05-31) and discarded the exit status, so it always failed AND
# always logged "sent" (found in the 2026-08-03 sysadmin audit). Now: correct network,
# delivery-gated, with the fleet-wide direct-Telegram fallback (send-telegram.sh).
if sudo docker ps --format '{{.Names}}' 2>/dev/null | grep -q '^apprise$' && \
   sudo docker run --rm --network fabrik curlimages/curl:latest -sf -X POST "http://apprise:8000/notify/alerts" \
  -H "Content-Type: application/json" \
  -d "{\"title\":\"🔧 Weekly Maintenance\",\"body\":${ESCAPED}}" \
  >/dev/null 2>&1; then
  echo "$(date -Iseconds) Weekly maintenance report sent"
elif bash /opt/fabrik/scripts/sysadmin/send-telegram.sh "🔧 Weekly Maintenance
$REPORT" >/dev/null 2>&1; then
  echo "$(date -Iseconds) Weekly maintenance report sent via direct Telegram fallback"
else
  echo "$(date -Iseconds) Weekly maintenance report FAILED via BOTH Apprise and Telegram fallback" >&2
fi
