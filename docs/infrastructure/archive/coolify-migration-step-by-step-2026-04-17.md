# Coolify Migration: Step-by-Step Guide

> **📌 ARCHIVED 2026-06-06.** Historical document preserved as-is for context. Frozen at the time of original ship. For current fleet state see [`vps-status.md`](../vps-status.md), [`vps-complete-inventory.md`](../vps-complete-inventory.md), and [`vps-fleet-architecture.md`](../vps-fleet-architecture.md). Do NOT update the content below — that would defeat the archive.

**Date:** 2026-04-17
**Approach:** One service at a time, test thoroughly, rollback if needed

## Pre-Migration Checklist

### 1. Full VPS Backup

```bash
# Trigger Duplicati backup
ssh vps "sudo docker exec duplicati duplicati-cli backup"

# Verify backup completed
ssh vps "sudo docker logs duplicati --tail=50 | grep -i 'backup completed'"
```

### 2. Document Current State

```bash
# Save current docker ps output
ssh vps "sudo docker ps --format '{{.Names}}\t{{.Status}}\t{{.Ports}}' > /tmp/pre-migration-state.txt"

# Save current compose files
ssh vps "sudo tar -czf /tmp/compose-backup-$(date +%Y%m%d).tar.gz /opt/*/compose.yaml"
```

### 3. Identify Dependencies

**Services that depend on what we're migrating:**

| Service to Migrate | Used By | Connection Method |
|-------------------|---------|-------------------|
| **prometheus** | Grafana (data source), Alertmanager (metrics) | http://prometheus:9090 |
| **grafana** | Users via browser | https://monitor.vps1.ocoron.com |
| **loki** | Grafana (data source), Promtail (logs) | http://loki:3100 |
| **alertmanager** | Prometheus (alerts), n8n (webhooks) | http://alertmanager:9093 |
| **apprise** | Gatus (notifications), Alertmanager (fallback), n8n | http://apprise:8000 |
| **authelia** | Traefik (forward-auth middleware) | http://authelia:9091 |
| **n8n** | Users, workflows | https://auto.vps1.ocoron.com |
| **duplicati** | Users (backup management) | https://backup.vps1.ocoron.com |
| **netdata** | Users (metrics viewing) | https://netdata.vps1.ocoron.com |

---

## Migration Order (Least to Most Critical)

### Phase 1: Low-Risk Utilities (Test Phase)
1. netdata (standalone, no dependencies)
2. duplicati (standalone, backup service)

### Phase 2: Workflow Automation
3. n8n (has workflows but can tolerate brief downtime)

### Phase 3: Notifications
4. apprise (used by Gatus and Alertmanager)

### Phase 4: Authentication (Critical)
5. authelia (protects admin dashboards - VERY CAREFUL)

### Phase 5: Monitoring Stack (Most Complex)
6. promtail (log shipper - no external dependencies)
7. cadvisor (container metrics)
8. node-exporter (host metrics)
9. loki (log aggregation - depends on promtail)
10. alertmanager (depends on prometheus)
11. prometheus (core metrics - many dependencies)
12. grafana (depends on prometheus + loki)

---

## Migration Template (Use for Each Service)

### Step 1: Pre-Migration Checks

```bash
# Check current container status
ssh vps "sudo docker inspect SERVICE_NAME --format='{{.State.Status}}'"

# Check what's connecting to it
ssh vps "sudo docker logs SERVICE_NAME --tail=100 | grep -E 'connection|request' | tail -20"

# Save current config
ssh vps "sudo docker inspect SERVICE_NAME > /tmp/SERVICE_NAME-config.json"
```

### Step 2: Create Coolify Service

**Via Coolify UI:**
1. Go to Services → New Service
2. Select "Docker Compose"
3. Name: `SERVICE_NAME`
4. Copy compose configuration from `/opt/SERVICE_NAME/compose.yaml`
5. Add Traefik labels for domain routing
6. **DO NOT START YET**

### Step 3: Test Configuration

```bash
# Verify Coolify generated the compose file
ssh vps "sudo cat /data/coolify/services/UUID/docker-compose.yml"

# Check for errors in configuration
ssh vps "sudo docker compose -f /data/coolify/services/UUID/docker-compose.yml config"
```

### Step 4: Parallel Testing

```bash
# Start new Coolify-managed container (will get different name)
# Via Coolify UI: Click "Start"

# Verify new container is running
ssh vps "sudo docker ps | grep SERVICE_NAME"

# Test new container
curl -I https://NEW_DOMAIN_OR_IP

# Check logs for errors
ssh vps "sudo docker logs NEW_CONTAINER_NAME --tail=50"
```

### Step 5: Connection Testing

```bash
# Test internal connectivity
ssh vps "sudo docker exec NEW_CONTAINER_NAME ping -c 3 OTHER_SERVICE"

# Test service functionality
# (Service-specific tests below)
```

### Step 6: Switch Traffic

**For services with Traefik routing:**
1. Update DNS or Traefik labels to point to new container
2. Monitor logs for incoming traffic
3. Verify no errors

**For internal services:**
1. Update dependent services' connection strings
2. Restart dependent services
3. Verify connectivity

### Step 7: Monitor & Verify

```bash
# Monitor for 15 minutes
watch -n 10 'ssh vps "sudo docker logs NEW_CONTAINER_NAME --tail=20"'

# Check dependent services
ssh vps "sudo docker logs DEPENDENT_SERVICE --tail=50 | grep SERVICE_NAME"
```

### Step 8: Decommission Old Container

```bash
# Stop old container
ssh vps "cd /opt/SERVICE_NAME && sudo docker compose down"

# Keep config for 7 days
ssh vps "sudo mv /opt/SERVICE_NAME /opt/.archive/SERVICE_NAME-$(date +%Y%m%d)"
```

### Step 9: Rollback (If Needed)

```bash
# Stop new Coolify container
# Via Coolify UI: Stop service

# Restart old container
ssh vps "cd /opt/SERVICE_NAME && sudo docker compose up -d"

# Verify old container is working
curl -I https://DOMAIN
```

---

## Service-Specific Migration Instructions

### 1. NETDATA (Easiest - Start Here)

**Dependencies:** None (standalone metrics viewer)
**Risk:** LOW
**Downtime:** ~2 minutes

**Pre-checks:**
```bash
ssh vps "curl -I https://netdata.vps1.ocoron.com"
```

**Coolify Configuration:**
```yaml
services:
  netdata:
    image: netdata/netdata:stable
    container_name: netdata
    hostname: vps1.ocoron.com
    cap_add:
      - SYS_PTRACE
      - SYS_ADMIN
    security_opt:
      - apparmor:unconfined
    volumes:
      - netdataconfig:/etc/netdata
      - netdatalib:/var/lib/netdata
      - netdatacache:/var/cache/netdata
      - /etc/passwd:/host/etc/passwd:ro
      - /etc/group:/host/etc/group:ro
      - /proc:/host/proc:ro
      - /sys:/host/sys:ro
      - /var/run/docker.sock:/var/run/docker.sock:ro
    restart: unless-stopped
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.netdata.rule=Host(`netdata.vps1.ocoron.com`)"
      - "traefik.http.routers.netdata.entrypoints=websecure"
      - "traefik.http.routers.netdata.tls=true"
      - "traefik.http.routers.netdata.tls.certresolver=letsencrypt"
      - "traefik.http.services.netdata.loadbalancer.server.port=19999"
      - "traefik.http.routers.netdata.middlewares=authelia-forward@docker"

volumes:
  netdataconfig:
  netdatalib:
  netdatacache:
```

**Test:**
```bash
curl -I https://netdata.vps1.ocoron.com
# Should return 200 OK
```

**Success Criteria:**
- ✓ Netdata UI accessible
- ✓ Real-time metrics updating
- ✓ Docker container metrics visible

---

### 2. DUPLICATI (Low Risk)

**Dependencies:** None (standalone backup service)
**Risk:** LOW
**Downtime:** ~2 minutes

**Pre-checks:**
```bash
ssh vps "curl -I https://backup.vps1.ocoron.com"
ssh vps "sudo docker exec duplicati ls -la /backups"
```

**Coolify Configuration:**
```yaml
services:
  duplicati:
    image: lscr.io/linuxserver/duplicati:latest
    container_name: duplicati
    environment:
      - PUID=1000
      - PGID=1000
      - TZ=Europe/Istanbul
    volumes:
      - duplicati-config:/config
      - /opt:/source/opt:ro
      - /var/lib/docker/volumes:/source/volumes:ro
    restart: unless-stopped
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.duplicati.rule=Host(`backup.vps1.ocoron.com`)"
      - "traefik.http.routers.duplicati.entrypoints=websecure"
      - "traefik.http.routers.duplicati.tls=true"
      - "traefik.http.routers.duplicati.tls.certresolver=letsencrypt"
      - "traefik.http.services.duplicati.loadbalancer.server.port=8200"
      - "traefik.http.routers.duplicati.middlewares=authelia-forward@docker"

volumes:
  duplicati-config:
```

**Test:**
```bash
curl -I https://backup.vps1.ocoron.com
# Verify backup jobs are listed
```

**Success Criteria:**
- ✓ Duplicati UI accessible
- ✓ Backup jobs visible
- ✓ Next scheduled backup shows correct time

---

### 3. N8N (Medium Risk)

**Dependencies:** None (but has active workflows)
**Risk:** MEDIUM (workflows may be running)
**Downtime:** ~5 minutes

**Pre-checks:**
```bash
ssh vps "curl -I https://auto.vps1.ocoron.com"
# Check for active workflow executions
ssh vps "sudo docker logs n8n --tail=100 | grep -i 'workflow.*running'"
```

**Coolify Configuration:**
```yaml
services:
  n8n:
    image: n8nio/n8n:latest
    container_name: n8n
    environment:
      - N8N_HOST=auto.vps1.ocoron.com
      - N8N_PORT=5678
      - N8N_PROTOCOL=https
      - WEBHOOK_URL=https://auto.vps1.ocoron.com/
      - GENERIC_TIMEZONE=Europe/Istanbul
    volumes:
      - n8n-data:/home/node/.n8n
    restart: unless-stopped
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.n8n.rule=Host(`auto.vps1.ocoron.com`)"
      - "traefik.http.routers.n8n.entrypoints=websecure"
      - "traefik.http.routers.n8n.tls=true"
      - "traefik.http.routers.n8n.tls.certresolver=letsencrypt"
      - "traefik.http.services.n8n.loadbalancer.server.port=5678"
      - "traefik.http.routers.n8n.middlewares=authelia-forward@docker"

volumes:
  n8n-data:
```

**Test:**
```bash
curl -I https://auto.vps1.ocoron.com
# Test webhook endpoint
curl -X POST https://auto.vps1.ocoron.com/webhook-test/test
```

**Success Criteria:**
- ✓ n8n UI accessible
- ✓ Workflows list loads
- ✓ Test workflow executes successfully

---

### 4. APPRISE (Medium-High Risk)

**Dependencies:** Used by Gatus, Alertmanager, n8n
**Risk:** MEDIUM-HIGH (notifications will fail if broken)
**Downtime:** ~3 minutes

**Pre-checks:**
```bash
ssh vps "curl -I https://notify.vps1.ocoron.com"
# Test notification
ssh vps "curl -X POST http://apprise:8000/notify/alerts -H 'Content-Type: application/json' -d '{\"title\":\"Test\",\"body\":\"Pre-migration test\"}'"
```

**Coolify Configuration:**
```yaml
services:
  apprise:
    image: caronc/apprise:latest
    container_name: apprise
    environment:
      - APPRISE_STATELESS_URLS=tgram://<REDACTED-TELEGRAM-BOT-TOKEN>/6999645768
    volumes:
      - apprise-config:/config
    restart: unless-stopped
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.apprise.rule=Host(`notify.vps1.ocoron.com`)"
      - "traefik.http.routers.apprise.entrypoints=websecure"
      - "traefik.http.routers.apprise.tls=true"
      - "traefik.http.routers.apprise.tls.certresolver=letsencrypt"
      - "traefik.http.services.apprise.loadbalancer.server.port=8000"
      - "traefik.http.routers.apprise.middlewares=authelia-forward@docker"

volumes:
  apprise-config:
```

**Critical:** After migration, update Gatus and Alertmanager configs to use new container name

**Test:**
```bash
# Test notification
curl -X POST https://notify.vps1.ocoron.com/notify/alerts \
  -H "Content-Type: application/json" \
  -d '{"title":"Migration Test","body":"Apprise migrated to Coolify"}'

# Check Telegram for message
```

**Success Criteria:**
- ✓ Apprise UI accessible
- ✓ Test notification received in Telegram
- ✓ Gatus can send notifications
- ✓ Alertmanager can send notifications

---

### 5. AUTHELIA (HIGH RISK - VERY CAREFUL)

**Dependencies:** Traefik middleware for ALL admin dashboards
**Risk:** VERY HIGH (could lock you out of admin interfaces)
**Downtime:** ~5 minutes

**⚠️ CRITICAL:** Have SSH access ready. If this breaks, you'll need to fix via SSH.

**Pre-checks:**
```bash
ssh vps "curl -I https://auth.vps1.ocoron.com"
# Test 2FA login
# Verify you can access protected services
```

**Backup:**
```bash
ssh vps "sudo tar -czf /tmp/authelia-backup-$(date +%Y%m%d).tar.gz /opt/authelia"
```

**Coolify Configuration:**
```yaml
services:
  authelia:
    image: authelia/authelia:latest
    container_name: authelia
    volumes:
      - authelia-config:/config
    restart: unless-stopped
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.authelia.rule=Host(`auth.vps1.ocoron.com`)"
      - "traefik.http.routers.authelia.entrypoints=websecure"
      - "traefik.http.routers.authelia.tls=true"
      - "traefik.http.routers.authelia.tls.certresolver=letsencrypt"
      - "traefik.http.services.authelia.loadbalancer.server.port=9091"
      # Forward-auth middleware
      - "traefik.http.middlewares.authelia-forward.forwardauth.address=http://authelia:9091/api/verify?rd=https://auth.vps1.ocoron.com/"
      - "traefik.http.middlewares.authelia-forward.forwardauth.trustForwardHeader=true"
      - "traefik.http.middlewares.authelia-forward.forwardauth.authResponseHeaders=Remote-User,Remote-Groups,Remote-Name,Remote-Email"

volumes:
  authelia-config:
    driver: local
    driver_opts:
      type: none
      o: bind
      device: /opt/authelia/config
```

**Test:**
```bash
# Test login page
curl -I https://auth.vps1.ocoron.com

# Test protected service (should redirect to Authelia)
curl -I https://coolify.vps1.ocoron.com

# Login and verify access
```

**Success Criteria:**
- ✓ Authelia login page loads
- ✓ 2FA works (TOTP code accepted)
- ✓ Can access Coolify after login
- ✓ Can access n8n after login
- ✓ Can access Grafana after login

**Rollback Plan:**
```bash
# If locked out, immediately:
ssh vps "cd /opt/authelia && sudo docker compose up -d"
# Wait 30 seconds
# Try accessing protected services again
```

---

### 6-12. MONITORING STACK (Complex - Do Last)

**Order:**
1. promtail (no dependencies)
2. cadvisor (no dependencies)
3. node-exporter (no dependencies)
4. loki (depends on promtail)
5. alertmanager (depends on prometheus)
6. prometheus (many dependencies - CAREFUL)
7. grafana (depends on prometheus + loki)

**Note:** These are complex and interconnected. Recommend migrating monitoring stack as a SINGLE unit via Coolify's Docker Compose service, not individually.

---

## Post-Migration Verification

### 1. Check All Services

```bash
ssh vps "sudo docker ps --format '{{.Names}}\t{{.Status}}' | grep -E 'netdata|duplicati|n8n|apprise|authelia'"
```

### 2. Verify Coolify Management

```bash
ssh vps "sudo docker inspect SERVICE_NAME --format='{{index .Config.Labels \"coolify.managed\"}}'"
# Should return "true"
```

### 3. Test End-to-End

- Access each service via browser
- Verify Authelia 2FA works
- Send test notification via Apprise
- Check n8n workflows
- Verify Netdata metrics
- Check Duplicati backup schedule

### 4. Monitor for 24 Hours

```bash
# Set up monitoring
watch -n 60 'ssh vps "sudo docker ps --filter status=exited"'
```

---

## Rollback Checklist

If ANY service fails:

1. **Stop new Coolify container** (via Coolify UI)
2. **Start old container:** `ssh vps "cd /opt/SERVICE_NAME && sudo docker compose up -d"`
3. **Verify old container works**
4. **Document the issue**
5. **DO NOT proceed to next service**

---

## Final Notes

- **One service at a time** - Do not rush
- **Test thoroughly** - 15 minutes minimum per service
- **Keep old configs** - Archive for 7 days minimum
- **Monitor logs** - Watch for errors continuously
- **Have rollback ready** - Know how to revert quickly
- **Iptables unchanged** - No firewall changes needed (all services already in Coolify network)

---

## Migration Log Template

```
Date: YYYY-MM-DD HH:MM
Service: SERVICE_NAME
Status: [STARTED|SUCCESS|FAILED|ROLLED_BACK]
Duration: X minutes
Issues: None / [describe issues]
Rollback: No / Yes - [reason]
Notes: [any observations]
```
