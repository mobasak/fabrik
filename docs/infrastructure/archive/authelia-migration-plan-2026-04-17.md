# Authelia Migration to Coolify - Phase 12

**Date:** 2026-04-17
**Status:** In Progress
**Risk Level:** HIGH (Protects all admin dashboards)
**Estimated Duration:** 65 minutes
**Rollback Time:** < 2 minutes

---

## Executive Summary

**Goal:** Migrate Authelia from standalone Docker Compose to Coolify management.

**Why:**
1. Unified backup via Backrest (auto-includes config + SQLite)
2. Centralized secrets management in Coolify UI
3. Simplified Traefik integration (internal service names)
4. Consistency: 29/29 infrastructure services managed (100%)

**Current State:**
- **Image:** `authelia/authelia:latest`
- **Auth Backend:** File-based (`users_database.yml`)
- **Storage:** SQLite (`db.sqlite3`)
- **Config Files:** `/opt/authelia/config/`
- **Network:** Coolify external network
- **Domain:** `auth.vps1.ocoron.com`

**Backup Created:** `/tmp/authelia-backup-20260417-224123.tar.gz` (14KB)

---

## Safety Measures

### 1. Rollback Plan
```bash
# If anything fails, restore standalone:
ssh vps "cd /opt/authelia && sudo docker compose up -d"
# Downtime: ~30 seconds
```

### 2. SSH Tunnel Backdoor
```bash
# Direct Coolify UI access (bypasses Authelia):
ssh -L 8000:localhost:8000 vps
# Access: http://localhost:8000
```

### 3. IP Bypass (Added in Phase 12B)
WSL IP will be whitelisted in Authelia config to bypass 2FA during migration.

### 4. Parallel Run Period
Both instances will run simultaneously during testing phase.

---

## Phase 12A: Test Instance Deployment (30 min)

### Goal
Deploy Coolify-managed Authelia on test subdomain, verify functionality.

### Steps

1. **Copy config files to Fabrik**
   ```bash
   ssh vps "sudo cp -r /opt/authelia/config /tmp/authelia-config-copy"
   ssh vps "sudo chmod -R 755 /tmp/authelia-config-copy"
   scp -r vps:/tmp/authelia-config-copy /opt/fabrik/specs/infrastructure/authelia-config
   ```

2. **Create Coolify Docker Compose spec**
   - File: `specs/infrastructure/authelia.yaml`
   - Domain: `auth-test.vps1.ocoron.com`
   - Volume: Coolify-managed persistent volume

3. **Deploy via Coolify API**
   ```bash
   python -c "
   from src.fabrik.drivers.coolify import CoolifyClient
   import base64

   client = CoolifyClient()
   with open('specs/infrastructure/authelia.yaml') as f:
       compose = f.read()

   client.create_dockercompose_application(
       project_uuid='lww8g0oc48cg4gw08oc8k40k',
       server_uuid='jk4wskkcks8csg4gcokwgw8s',
       docker_compose_raw=base64.b64encode(compose.encode()).decode(),
       name='authelia-test',
       description='Authelia test instance for migration validation',
       instant_deploy=True
   )
   "
   ```

4. **Copy config files to Coolify volume**
   ```bash
   # Get container ID
   CONTAINER=$(ssh vps "sudo docker ps | grep authelia-test | awk '{print \$1}'")

   # Copy files
   ssh vps "sudo docker cp /opt/authelia/config/configuration.yml $CONTAINER:/config/"
   ssh vps "sudo docker cp /opt/authelia/config/users_database.yml $CONTAINER:/config/"
   ssh vps "sudo docker cp /opt/authelia/config/db.sqlite3 $CONTAINER:/config/"

   # Restart to load config
   ssh vps "sudo docker restart $CONTAINER"
   ```

5. **Verify health**
   ```bash
   curl -f https://auth-test.vps1.ocoron.com/api/health
   ```

6. **Test 2FA login**
   - Open: https://auth-test.vps1.ocoron.com
   - Login with existing credentials
   - Verify TOTP works

### Success Criteria
- [ ] Container healthy
- [ ] Health endpoint returns 200
- [ ] Can login with username/password
- [ ] 2FA TOTP works
- [ ] Session persists after restart

### Rollback
Delete test service in Coolify UI. Production unaffected.

---

## Phase 12B: IP Bypass + Validation (15 min)

### Goal
Add safety net before production cutover.

### Steps

1. **Get WSL IP**
   ```bash
   curl -s ifconfig.me
   ```

2. **Add IP bypass to both instances**

   Edit `/opt/authelia/config/configuration.yml` (standalone):
   ```yaml
   access_control:
     default_policy: deny
     rules:
       # SAFETY NET - Remove after migration
       - domain: "*.vps1.ocoron.com"
         policy: bypass
         networks:
           - "YOUR_WSL_IP/32"

       # Existing rules...
   ```

   Apply same to test instance config.

3. **Restart both instances**
   ```bash
   ssh vps "cd /opt/authelia && sudo docker compose restart"
   ssh vps "sudo docker restart authelia-test-<uuid>"
   ```

4. **Verify bypass works**
   - Access Grafana from WSL: https://monitor.vps1.ocoron.com
   - Should load without 2FA prompt

5. **Test ForwardAuth with test instance**
   - Update one non-critical service (Apprise) to use test Authelia
   - Verify it still works

### Success Criteria
- [ ] WSL IP bypass works on both instances
- [ ] Can access dashboards without 2FA from WSL
- [ ] ForwardAuth works with test instance

### Rollback
Remove IP bypass rules, restart containers.

---

## Phase 12C: Production Cutover (20 min)

### Goal
Switch production traffic to Coolify-managed instance.

### Pre-Flight Checklist
- [ ] SSH session active to VPS
- [ ] Coolify UI accessible via SSH tunnel
- [ ] Test instance verified healthy
- [ ] IP bypass confirmed working
- [ ] Backup verified: `/tmp/authelia-backup-20260417-224123.tar.gz`

### Steps

1. **Stop standalone Authelia**
   ```bash
   ssh vps "cd /opt/authelia && sudo docker compose down"
   ```

2. **Update test instance to production domain**
   - In Coolify UI: Update service domain from `auth-test` to `auth`
   - Redeploy service
   - Wait for Let's Encrypt cert

3. **Update all protected services**

   Services to update (8 total):
   - Coolify (if protected)
   - n8n
   - Grafana
   - Netdata
   - Backrest
   - Apprise
   - GlitchTip (if protected)

   Change middleware address from:
   ```yaml
   traefik.http.middlewares.authelia-forward.forwardAuth.address=http://authelia:9091/api/authz/forward-auth
   ```

   To:
   ```yaml
   traefik.http.middlewares.authelia-forward.forwardAuth.address=http://authelia-<coolify-uuid>:9091/api/authz/forward-auth
   ```

4. **Test each dashboard**
   - [ ] https://coolify.vps1.ocoron.com
   - [ ] https://auto.vps1.ocoron.com (n8n)
   - [ ] https://monitor.vps1.ocoron.com (Grafana)
   - [ ] https://netdata.vps1.ocoron.com
   - [ ] https://backup.vps1.ocoron.com (Backrest)
   - [ ] https://notify.vps1.ocoron.com (Apprise)

5. **Remove IP bypass** (after confirming all works)
   ```bash
   # Edit config in Coolify volume
   # Remove the bypass rule
   # Restart container
   ```

6. **Verify 2FA required**
   - Test from incognito browser
   - Should prompt for login + TOTP

7. **Clean up**
   ```bash
   # Remove standalone files (keep backup)
   ssh vps "sudo mv /opt/authelia /opt/authelia.old"

   # Remove test instance from Coolify
   # (via UI)
   ```

### Success Criteria
- [ ] All dashboards accessible
- [ ] 2FA prompts work
- [ ] Sessions persist
- [ ] No Traefik errors in logs
- [ ] Authelia container healthy

### Rollback Procedure
```bash
# 1. Restore standalone
ssh vps "sudo mv /opt/authelia.old /opt/authelia"
ssh vps "cd /opt/authelia && sudo docker compose up -d"

# 2. Wait for container healthy (~30 sec)
ssh vps "sudo docker ps | grep authelia"

# 3. Verify dashboards accessible
curl -I https://monitor.vps1.ocoron.com

# Total downtime: ~2 minutes
```

---

## Post-Migration Tasks

### 1. Update Documentation
- [ ] COOLIFY_STATUS.md - Mark authelia as migrated
- [ ] AGENTS.md - Update Authelia description
- [ ] MIGRATION_SUMMARY.md - Add Phase 12 completion
- [ ] CHANGELOG.md - Add migration entry

### 2. Verify Backrest Backup
```bash
# Check that Authelia config is in next backup
ssh vps "sudo docker exec backrest restic snapshots"
```

### 3. Update Gatus Monitoring
Add Authelia health check to Gatus config.

### 4. Remove Old Files (After 7 days)
```bash
ssh vps "sudo rm -rf /opt/authelia.old"
ssh vps "sudo rm /tmp/authelia-backup-*.tar.gz"
```

---

## Troubleshooting

### Issue: Can't login after migration
**Cause:** SQLite database not copied correctly
**Fix:**
```bash
ssh vps "sudo docker cp /tmp/authelia-config-copy/db.sqlite3 authelia-<uuid>:/config/"
ssh vps "sudo docker restart authelia-<uuid>"
```

### Issue: 2FA codes not working
**Cause:** Time sync issue
**Fix:**
```bash
ssh vps "sudo docker exec authelia-<uuid> date"
# Should match VPS time
```

### Issue: ForwardAuth fails
**Cause:** Wrong internal address
**Fix:** Verify middleware uses correct container name:
```bash
ssh vps "sudo docker ps | grep authelia"
# Use the full container name in middleware
```

### Issue: Let's Encrypt cert fails
**Cause:** DNS not updated yet
**Fix:** Wait 5 minutes for DNS propagation, then redeploy.

---

## Migration Timeline

| Phase | Duration | Risk | Rollback Time |
|-------|----------|------|---------------|
| 12A: Test Deploy | 30 min | None | Instant |
| 12B: IP Bypass | 15 min | Low | 1 min |
| 12C: Cutover | 20 min | Medium | 2 min |
| **Total** | **65 min** | **Controlled** | **< 2 min** |

---

## Success Metrics

- ✅ Authelia managed by Coolify
- ✅ All 8 dashboards protected and accessible
- ✅ 2FA working correctly
- ✅ Config backed up by Backrest
- ✅ Zero permanent downtime
- ✅ 29/29 infrastructure services in Coolify (100%)

---

## Notes

- **Coolify UUID:** Will be assigned during deployment
- **Internal Address:** `http://authelia-<uuid>:9091`
- **Config Volume:** Coolify-managed persistent volume
- **Network:** Coolify external network (already connected)

**Last Updated:** 2026-04-17 22:42 (UTC+3)
