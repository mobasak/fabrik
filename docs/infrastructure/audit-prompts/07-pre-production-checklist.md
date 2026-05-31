# Pre-Production Checklist — Go-Live Readiness

Run this audit before the VPS serves its first real user. Covers every layer from infrastructure to application to operational readiness. Not a theoretical checklist — every item is verified against live state.

## Context

This VPS will host:
- SaaS products (ocoron.com WordPress site, future GUI apps)
- Backend APIs (site-provisioner, image-broker)
- Observability stack (Grafana, Prometheus, Gatus, GlitchTip)
- Deployment platform (Coolify)

## Commands to Run

Run the full system audit (01) + security audit (03) + observability audit (05) + backup audit (06) commands. Then add:

```bash
# 1. Public endpoint verification
for domain in ocoron.com www.ocoron.com status.vps1.ocoron.com monitor.vps1.ocoron.com errors.vps1.ocoron.com backup.vps1.ocoron.com provision.vps1.ocoron.com; do
  code=$(curl -sS -o /dev/null -w "%{http_code}" --max-time 10 "https://$domain/" 2>/dev/null)
  echo "$domain: HTTP $code"
done

# 2. Health endpoints (internal)
sudo docker run --rm --network fabrik curlimages/curl:latest -sS -o /dev/null -w "%{http_code}" http://prometheus:9090/-/ready
sudo docker run --rm --network fabrik curlimages/curl:latest -sS -o /dev/null -w "%{http_code}" http://loki:3100/ready
sudo docker run --rm --network fabrik curlimages/curl:latest -sS -o /dev/null -w "%{http_code}" http://grafana:3000/api/health
sudo docker run --rm --network fabrik curlimages/curl:latest -sS -o /dev/null -w "%{http_code}" http://glitchtip-web:8000/api/0/
sudo docker run --rm --network fabrik curlimages/curl:latest -sS -o /dev/null -w "%{http_code}" http://gatus:8080/api/v1/endpoints/statuses

# 3. DNS resolution (external)
for domain in ocoron.com status.vps1.ocoron.com monitor.vps1.ocoron.com; do
  ip=$(dig +short $domain @1.1.1.1 2>/dev/null)
  echo "$domain → $ip"
done

# 4. WordPress-specific
curl -sS -o /dev/null -w "%{http_code}" "https://ocoron.com/"
curl -sS -o /dev/null -w "%{http_code}" "https://ocoron.com/wp-json/wp/v2/users"
curl -sS -o /dev/null -w "%{http_code}" "https://ocoron.com/xmlrpc.php"

# 5. System resource headroom
free -h | grep Mem | awk '{printf "Memory: %s used of %s (%.0f%% free)\n", $3, $2, ($4/$2)*100}'
df -h / | tail -1 | awk '{printf "Disk: %s used of %s (%s free)\n", $3, $2, $4}'

# 6. Cron jobs (WSL + VPS)
crontab -l 2>/dev/null
ssh vps "crontab -l" 2>/dev/null

# 7. Auto-restart verification
sudo docker ps --format "{{.Names}} {{.RestartCount}}" | sort -t' ' -k2 -rn | head -10
```

## Go-Live Checklist

### Infrastructure Layer
- [ ] All containers healthy (0 unhealthy, 0 restarting)
- [ ] Memory headroom > 1GB free
- [ ] Disk headroom > 20GB free
- [ ] Swap usage = 0 (no memory pressure)
- [ ] Load average < 3.0 (50% of 6 cores)
- [ ] Docker log rotation configured (daemon.json: max-size 10m, max-file 3)
- [ ] Docker log tag configured (daemon.json: `tag: {{.Name}}`)

### Security Layer
- [ ] UFW active with only ports 22, 80, 443, 6001, 6002 allowed
- [ ] DOCKER-USER chain has 9 rules (catch-all DROP at end)
- [ ] SSH: key-only, no root, Ed25519
- [ ] Authelia: all admin dashboards behind 2FA
- [ ] All public-facing TLS certs valid (>14 days to expiry)
- [ ] No containers running in privileged mode (except cAdvisor/Netdata)
- [ ] SERVICE_INTERNAL_SECRET_KEY is 32+ chars, not a default

### Observability Layer
- [ ] Prometheus: all scrape targets UP
- [ ] Loki: receiving logs, container_name label populated
- [ ] Grafana: datasources connected, 8 dashboards present
- [ ] GlitchTip: API reachable, projects with firstEvent
- [ ] Gatus: all endpoints monitored, alerts → Telegram working
- [ ] Alertmanager: drift alert rule loaded
- [ ] Promtail: noise filter dropping coolify-db/redis/realtime/sentinel

### Backup Layer
- [ ] Backrest: last backup < 24h ago
- [ ] postgres-main volume in backup plan
- [ ] WordPress volumes in backup plan
- [ ] /opt/fabrik/.env backed up locally
- [ ] Recovery tested at least once

### Application Layer
- [ ] ocoron.com: HTTP 200, valid cert, language switcher working
- [ ] ocoron.com: /wp-json/wp/v2/users returns 403 (REST hardening)
- [ ] ocoron.com: /xmlrpc.php returns 403 (xmlrpc blocked)
- [ ] All API services: /health returns 200
- [ ] DNS resolves correctly for all domains

### Operational Layer
- [ ] WSL cron: hourly registrar audit running
- [ ] WSL cron: weekly Authelia audit running
- [ ] WSL cron: daily kilo_model_sync running
- [ ] `fabrik audit-registrars` returns 0 drift
- [ ] `fabrik vps-sync --verify` returns clean
- [ ] VPS inventory doc (`generate_vps_inventory.py --update`) matches live state
- [ ] LESSONS_LEARNT.md reviewed — no known gotchas unaddressed

## Output Format

1. **GO/NO-GO DECISION** — with evidence for each failing item
2. **BLOCKING ISSUES** — must fix before go-live
3. **KNOWN RISKS** — acceptable for launch, fix within first week
4. **POST-LAUNCH MONITORING PLAN** — what to watch in the first 48 hours
