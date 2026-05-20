# Backup & Disaster Recovery Audit

Verify that backups are running, recoverable, and cover all critical data. A backup that hasn't been tested is not a backup — it's a hope.

## Stack

- **Backrest** (restic-based) → Backblaze B2 bucket
- **Managed by:** Coolify Service (`backrest-*` container)
- **UI:** `https://backup.vps1.ocoron.com` (Authelia-protected)
- **Config:** `/opt/backrest/config/config.json` on VPS (bind-mounted into container)
- **Critical data to back up:**
  - `postgres-main` data volume (all app databases: glitchtip, site_provisioner)
  - `redis-main` data volume (Authelia sessions, cache)
  - WordPress `wp_content` + `db_data` volumes (ocoron-com)
  - `/opt/fabrik/.env` (all secrets)
  - `/data/coolify/` (Coolify state — services, applications, proxy config)
  - Authelia config volume (access control rules, TOTP secrets)

## Data Collection

**Automated:** `ssh vps 'sudo bash -s' < /opt/fabrik/scripts/audit/06-backup.sh`

**Or manual:**

```bash
# 1. Backrest container health
sudo docker ps --filter name=backrest --format "{{.Names}} {{.Status}}"
sudo docker logs $(sudo docker ps --filter name=backrest --format "{{.Names}}") --tail 20 2>&1

# 2. Backrest plans and repos
sudo cat /opt/backrest/config/config.json 2>/dev/null | python3 -c "
import json,sys
cfg=json.load(sys.stdin)
print('=== Repos ===')
for r in cfg.get('repos',[]):
    print(f\"  {r.get('id','?'):20s} uri={r.get('uri','?')}\")
print()
print('=== Plans ===')
for p in cfg.get('plans',[]):
    print(f\"  {p.get('id','?'):30s} repo={p.get('repo','?')} paths={p.get('paths',[])} schedule={p.get('schedule',{}).get('cron','none')}\")
" 2>/dev/null || echo "config not found or not JSON"

# 3. Last backup status (from Backrest API or logs)
sudo docker logs $(sudo docker ps --filter name=backrest --format "{{.Names}}") 2>&1 | grep -iE "backup|snapshot|error|failed" | tail -20

# 4. Docker volumes — what exists
sudo docker volume ls --format "{{.Name}}" | sort

# 5. Volume sizes
for vol in $(sudo docker volume ls --format "{{.Name}}" | grep -E "postgres|redis|wp_content|db_data|authelia|grafana|loki"); do
  size=$(sudo du -sh /var/lib/docker/volumes/${vol}/_data/ 2>/dev/null | cut -f1)
  echo "$vol: $size"
done

# 6. B2 bucket connectivity (from inside Backrest container)
sudo docker exec $(sudo docker ps --filter name=backrest --format "{{.Names}}") restic -r "$REPO_URI" snapshots --latest 3 2>/dev/null || echo "Cannot reach B2 — check creds"

# 7. Secrets backup
ls -la /opt/fabrik/.env
ls -la /opt/fabrik/backups/

# 8. Coolify state
du -sh /data/coolify/ 2>/dev/null
ls /data/coolify/source/ /data/coolify/proxy/ /data/coolify/services/ /data/coolify/applications/ 2>/dev/null | head -20

# 9. Critical config files (do they exist?)
for f in "/var/lib/docker/volumes/hks48k8sg8o4co4co08co00o_authelia-config/_data/configuration.yml" "/opt/monitoring/configs/prometheus/prometheus.yml" "/opt/monitoring/configs/grafana/provisioning/datasources/fabrik.yaml" "/opt/monitoring/configs/gatus/_base.yaml"; do
  if sudo test -f "$f"; then
    echo "EXISTS: $f"
  else
    echo "MISSING: $f"
  fi
done
```

## Analysis Checklist

### 1. Backup Coverage
- Is postgres-main volume backed up? (ALL app data)
- Is redis-main volume backed up? (Authelia sessions)
- Is WordPress data backed up? (wp_content + db_data)
- Is Coolify state backed up? (/data/coolify/)
- Is Authelia config backed up? (TOTP secrets, access rules)
- Is /opt/fabrik/.env backed up? (all secrets)
- Are monitoring configs backed up? (prometheus, grafana, gatus)

### 2. Backup Schedule
- How often do backups run? (daily minimum for databases)
- Last successful backup timestamp — is it within 24 hours?
- Any failed backups in recent history?

### 3. Backup Integrity
- Can snapshots be listed from B2? (proves repo is accessible)
- Latest snapshot age — matches schedule?
- Retention policy set? (e.g. 30 days, 4 weekly, 12 monthly)

### 4. Recovery Readiness
- Can you restore a single file from the latest snapshot?
- Can you restore the full postgres database?
- Is there a documented recovery procedure?
- Time to recovery estimate (RTO)?

### 5. Secrets Management
- /opt/fabrik/.env backed up locally (backups/ dir)?
- .env has all critical creds (Coolify, Cloudflare, GlitchTip, Grafana tokens)?
- When was .env last backed up?

### 6. What's NOT Backed Up (Gaps)
- Docker images (recoverable from registry/git — OK to skip)
- Container state (ephemeral — OK to skip)
- Node_modules, .venv (rebuildable — OK to skip)
- But: any custom scripts or configs outside /opt/fabrik/ that aren't in git?

## Output Format

1. **BACKUP STATUS** — Last successful backup time, coverage %, schedule health
2. **COVERAGE GAPS** — critical data not backed up
3. **RECOVERY CONFIDENCE** — High / Medium / Low with justification
4. **REMEDIATION** — what to add to backup plans, what to test
