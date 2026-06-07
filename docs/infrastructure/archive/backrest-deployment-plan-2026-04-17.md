# Backrest Deployment Plan

> **📌 ARCHIVED 2026-06-06.** Historical document preserved as-is for context. Frozen at the time of original ship. For current fleet state see [`vps-status.md`](../vps-status.md), [`vps-complete-inventory.md`](../vps-complete-inventory.md), and [`vps-fleet-architecture.md`](../vps-fleet-architecture.md). Do NOT update the content below — that would defeat the archive.

**Date:** 2026-04-17
**Purpose:** Deploy Backrest to replace Duplicati for VPS backups
**Status:** Ready for Review

---

## Overview

Deploy Backrest (restic-based backup UI) to VPS via Coolify, replacing the previously removed Duplicati service.

**Key Features:**
- Web UI at backup.vps1.ocoron.com (Authelia 2FA protected)
- Restic backend with Backblaze B2 storage
- Automated PostgreSQL dumps via hooks
- Three backup plans: /opt configs, Docker volumes, PostgreSQL dumps
- Apprise integration for failure notifications

---

## Pre-Deployment Validation

### ✅ System State Verified

**VPS Container Status:**
- postgres-main: `postgres-main-l0k4gk0kggc8okcwk0s4c8s8` (running, healthy)
- apprise: `apprise-lcocgs4gs8ksg4g08w40ows8` (running, healthy)
- authelia: `authelia` (running)
- traefik: Managed by Coolify
- duplicati: ✅ Already removed (2026-04-17 cleanup)

**Gatus Status:**
- Container: `gatus-v8s4cokcwg0co4w8okkccc0w` (running)
- Config location: `/opt/monitoring/configs/gatus/apps/`
- Format: YAML files per service

**Coolify Credentials:**
- API Token: Available in `/opt/fabrik/.env`
- Server UUID: ⚠️ Empty in .env - will fetch via API
- Project UUID: ⚠️ Empty in .env - will fetch via API

---

## Required Information (User Must Provide)

### Backblaze B2 Credentials

```
B2_KEY_ID=<Application Key ID from B2 console>
B2_APP_KEY=<Application Key from B2 console>
B2_ENDPOINT=<e.g., s3.us-west-004.backblazeb2.com>
B2_BUCKET=<e.g., vps1-ocoron-backups>
```

**Where to get these:**
1. Log into Backblaze B2 console
2. Create bucket (if not exists): `vps1-ocoron-backups`
3. Create Application Key with read/write access
4. Note the endpoint from bucket details page

### Coolify UUIDs (Will Auto-Fetch if Not Provided)

```
COOLIFY_PROJECT_UUID=<from Coolify URL when viewing fabrik-services>
COOLIFY_SERVER_UUID=<from Coolify → Servers page>
```

**Auto-fetch method:**
- GET `/api/v1/projects` → find "fabrik-services" → extract UUID
- GET `/api/v1/servers` → find VPS server → extract UUID

---

## Deployment Steps

### Step 1: Create Directory Structure

**Location:** VPS via SSH

```bash
ssh vps "sudo mkdir -p /opt/backrest/{data,config,cache,tmp}"
ssh vps "sudo mkdir -p /opt/backups/postgres"
ssh vps "sudo chmod 755 /opt/backrest"
ssh vps "sudo chmod 755 /opt/backups/postgres"
```

**Verification:**
```bash
ssh vps "ls -la /opt/backrest"
ssh vps "ls -la /opt/backups"
```

---

### Step 2: Create PostgreSQL Dump Script

**Location:** `/opt/backups/postgres/dump.sh` on VPS

**FIXED:** Dynamic container name lookup to survive postgres redeployments

```bash
#!/bin/bash
set -e
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DUMP_FILE="/opt/backups/postgres/all_databases_${TIMESTAMP}.sql"

# Dynamic lookup - survives container name changes
POSTGRES=$(docker ps --format '{{.Names}}' | grep '^postgres-main-')
docker exec $POSTGRES pg_dumpall -U postgres > "$DUMP_FILE"

echo "Dump complete: $DUMP_FILE"

# Keep only last 3 dumps (restic deduplicates in B2)
ls -t /opt/backups/postgres/*.sql 2>/dev/null | tail -n +4 | xargs rm -f
```

**Commands:**
```bash
# Write script with dynamic container lookup
ssh vps "sudo tee /opt/backups/postgres/dump.sh > /dev/null" << 'EOF'
#!/bin/bash
set -e
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DUMP_FILE="/opt/backups/postgres/all_databases_${TIMESTAMP}.sql"
POSTGRES=$(docker ps --format '{{.Names}}' | grep '^postgres-main-')
docker exec $POSTGRES pg_dumpall -U postgres > "$DUMP_FILE"
echo "Dump complete: $DUMP_FILE"
ls -t /opt/backups/postgres/*.sql 2>/dev/null | tail -n +4 | xargs rm -f
EOF

# Make executable
ssh vps "sudo chmod +x /opt/backups/postgres/dump.sh"

# Test it
ssh vps "sudo bash /opt/backups/postgres/dump.sh"
```

**Expected output:** `Dump complete: /opt/backups/postgres/all_databases_YYYYMMDD_HHMMSS.sql`

---

### Step 3: Generate Restic Encryption Password

**Critical:** This password encrypts all backups. Losing it = losing all backup data permanently.

```bash
# Generate on VPS
RESTIC_PASSWORD=$(ssh vps "openssl rand -hex 32")

# Save to VPS
ssh vps "echo '$RESTIC_PASSWORD' | sudo tee /opt/backrest/.restic-password > /dev/null"
ssh vps "sudo chmod 600 /opt/backrest/.restic-password"

# Display for operator to save
echo "═══════════════════════════════════════════════════════════"
echo "⚠️  CRITICAL: SAVE THIS PASSWORD IN YOUR PASSWORD MANAGER"
echo "═══════════════════════════════════════════════════════════"
echo "Restic Encryption Password: $RESTIC_PASSWORD"
echo "═══════════════════════════════════════════════════════════"
```

**Operator Action Required:** Save this password in password manager immediately.

---

### Step 4: Fetch Coolify UUIDs (if not provided)

**Method 1: From Coolify API**

```bash
# Get API token
COOLIFY_TOKEN=$(grep COOLIFY_API_TOKEN /opt/fabrik/.env | cut -d= -f2)

# Fetch projects
curl -s -H "Authorization: Bearer $COOLIFY_TOKEN" \
  https://coolify.vps1.ocoron.com/api/v1/projects | jq '.[] | select(.name=="fabrik-services") | .uuid'

# Fetch servers
curl -s -H "Authorization: Bearer $COOLIFY_TOKEN" \
  https://coolify.vps1.ocoron.com/api/v1/servers | jq '.[0].uuid'
```

**Method 2: From Coolify UI**
- Project UUID: Open Coolify → Projects → fabrik-services → URL contains UUID
- Server UUID: Open Coolify → Servers → Click server → URL contains UUID

**Store in .env:**
```bash
# Update /opt/fabrik/.env
COOLIFY_PROJECT_UUID=<fetched_uuid>
COOLIFY_SERVER_UUID=<fetched_uuid>
```

---

### Step 5: Prepare Docker Compose YAML

**File:** Backrest compose configuration (will be base64-encoded)

```yaml
services:
  backrest:
    image: ghcr.io/garethgeorge/backrest:latest
    container_name: backrest
    hostname: vps1
    restart: unless-stopped
    mem_limit: 384m
    environment:
      - BACKREST_DATA=/data
      - BACKREST_CONFIG=/config/config.json
      - XDG_CACHE_HOME=/cache
      - TMPDIR=/tmp
      - TZ=Europe/Istanbul
      - AWS_ACCESS_KEY_ID=${B2_KEY_ID}
      - AWS_SECRET_ACCESS_KEY=${B2_APP_KEY}
    volumes:
      - /opt/backrest/data:/data
      - /opt/backrest/config:/config
      - /opt/backrest/cache:/cache
      - /opt/backrest/tmp:/tmp
      - /opt:/backup-opt:ro
      - /var/lib/docker/volumes:/backup-volumes:ro
      - /opt/backups:/backup-postgres
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - /opt/backrest/.restic-password:/restic-password:ro
    labels:
      - traefik.enable=true
      - traefik.http.routers.backrest.rule=Host(`backup.vps1.ocoron.com`)
      - traefik.http.routers.backrest.entrypoints=websecure
      - traefik.http.routers.backrest.tls=true
      - traefik.http.routers.backrest.tls.certresolver=letsencrypt
      - traefik.http.routers.backrest.middlewares=authelia-forward@docker
      - traefik.http.services.backrest.loadbalancer.server.port=9898
    networks:
      - coolify

networks:
  coolify:
    external: true
```

**Note:** `${B2_KEY_ID}` and `${B2_APP_KEY}` will be replaced with actual values before encoding.

---

### Step 6: Deploy via Coolify API

**Using CoolifyClient Driver:**

```python
from fabrik.drivers.coolify import CoolifyClient
import base64
import os

# Initialize client
client = CoolifyClient(
    base_url="https://coolify.vps1.ocoron.com",
    api_token=os.getenv("COOLIFY_API_TOKEN")
)

# Prepare compose YAML with B2 credentials
compose_yaml = """<YAML from Step 5>"""
compose_yaml = compose_yaml.replace("${B2_KEY_ID}", b2_key_id)
compose_yaml = compose_yaml.replace("${B2_APP_KEY}", b2_app_key)

# Base64 encode
compose_b64 = base64.b64encode(compose_yaml.encode()).decode()

# Create application
response = client.create_dockercompose_application(
    project_uuid=project_uuid,
    server_uuid=server_uuid,
    docker_compose_raw=compose_b64,
    name="backrest",
    description="Restic-based backup service with B2 storage",
    instant_deploy=True
)

backrest_uuid = response["uuid"]
print(f"✓ Backrest created: {backrest_uuid}")
```

**Alternative: Direct API Call**

```bash
# Prepare base64-encoded compose
COMPOSE_B64=$(echo "$COMPOSE_YAML" | base64 -w 0)

# Create application
curl -X POST https://coolify.vps1.ocoron.com/api/v1/applications/dockercompose \
  -H "Authorization: Bearer $COOLIFY_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"project_uuid\": \"$PROJECT_UUID\",
    \"server_uuid\": \"$SERVER_UUID\",
    \"environment_name\": \"production\",
    \"docker_compose_raw\": \"$COMPOSE_B64\",
    \"name\": \"backrest\",
    \"description\": \"Restic-based backup service with B2 storage\",
    \"instant_deploy\": true
  }"
```

**Verification:**
```bash
# Wait for container to start
ssh vps "sudo docker ps | grep backrest"
```

Expected: `backrest` container running

---

### Step 7: Initialize Restic Repository

**Wait for container to be healthy:**

```bash
# Poll until running
while ! ssh vps "sudo docker ps | grep backrest | grep -q Up"; do
  echo "Waiting for backrest container..."
  sleep 5
done
echo "✓ Backrest container is running"
```

**Initialize B2 repository:**

```bash
ssh vps "sudo docker exec backrest restic \
  -r s3:https://${B2_ENDPOINT}/${B2_BUCKET} \
  --password-file /restic-password \
  init"
```

**Expected outputs:**
- Success: `created restic repository ... at s3:...`
- Already exists: `repository ... already exists` (OK if re-running)

---

### Step 8: Create Backrest Configuration

**File:** `/opt/backrest/config/config.json` on VPS

```json
{
  "modno": 1,
  "version": 2,
  "instance": "vps1",
  "repos": [
    {
      "id": "b2-vps1",
      "uri": "s3:https://${B2_ENDPOINT}/${B2_BUCKET}",
      "password": "",
      "passwordFile": "/restic-password",
      "env": [
        "AWS_ACCESS_KEY_ID=${B2_KEY_ID}",
        "AWS_SECRET_ACCESS_KEY=${B2_APP_KEY}"
      ],
      "flags": ["--compression=auto"],
      "prunePolicy": {
        "schedule": {"cron": "0 4 * * *"},
        "keepLastN": 0,
        "keepHourly": 0,
        "keepDaily": 7,
        "keepWeekly": 4,
        "keepMonthly": 3,
        "keepYearly": 1
      }
    }
  ],
  "plans": [
    {
      "id": "opt-configs",
      "repo": "b2-vps1",
      "paths": ["/backup-opt"],
      "excludes": [
        "**/node_modules",
        "**/.git",
        "**/cache",
        "**/__pycache__",
        "**/*.log",
        "**/tmp"
      ],
      "schedule": {"cron": "0 3 * * *"},
      "retention": {
        "keepDaily": 7,
        "keepWeekly": 4,
        "keepMonthly": 3
      },
      "hooks": [
        {
          "conditions": ["CONDITION_ANY_ERROR"],
          "actionCommand": {
            "command": "curl -s -X POST http://apprise-lcocgs4gs8ksg4g08w40ows8:8000/notify/alerts -H 'Content-Type: application/json' -d '{\"title\":\"Backup failed: opt-configs\",\"body\":\"Backrest opt-configs plan failed on vps1\",\"type\":\"failure\"}'"
          }
        }
      ]
    },
    {
      "id": "docker-volumes",
      "repo": "b2-vps1",
      "paths": ["/backup-volumes"],
      "excludes": ["**/cache", "**/*.log", "**/tmp"],
      "schedule": {"cron": "30 3 * * *"},
      "retention": {
        "keepDaily": 7,
        "keepWeekly": 4,
        "keepMonthly": 3
      },
      "hooks": [
        {
          "conditions": ["CONDITION_ANY_ERROR"],
          "actionCommand": {
            "command": "curl -s -X POST http://apprise-lcocgs4gs8ksg4g08w40ows8:8000/notify/alerts -H 'Content-Type: application/json' -d '{\"title\":\"Backup failed: docker-volumes\",\"body\":\"Backrest docker-volumes plan failed on vps1\",\"type\":\"failure\"}'"
          }
        }
      ]
    },
    {
      "id": "postgres-dumps",
      "repo": "b2-vps1",
      "paths": ["/backup-postgres"],
      "excludes": ["**/*.sh"],
      "schedule": {"cron": "0 2 * * *"},
      "retention": {
        "keepDaily": 7,
        "keepWeekly": 4,
        "keepMonthly": 3
      },
      "hooks": [
        {
          "conditions": ["CONDITION_SNAPSHOT_START"],
          "actionCommand": {
            "command": "bash /backup-postgres/dump.sh"
          }
        },
        {
          "conditions": ["CONDITION_ANY_ERROR"],
          "actionCommand": {
            "command": "curl -s -X POST http://apprise-lcocgs4gs8ksg4g08w40ows8:8000/notify/alerts -H 'Content-Type: application/json' -d '{\"title\":\"Backup failed: postgres\",\"body\":\"Backrest postgres-dumps plan failed on vps1\",\"type\":\"failure\"}'"
          }
        }
      ]
    }
  ]
}
```

**Write to VPS:**

```bash
# Create config with actual values
CONFIG_JSON='<JSON above with placeholders replaced>'

ssh vps "echo '$CONFIG_JSON' | sudo tee /opt/backrest/config/config.json > /dev/null"

# Restart to load config
ssh vps "sudo docker restart backrest"

# Wait for restart
sleep 10
```

**Note on Container Names:**
- Apprise URL uses actual container name: `apprise-lcocgs4gs8ksg4g08w40ows8`
- **Limitation:** Hook commands run inside Backrest container and cannot execute dynamic lookups
- **Risk:** If Apprise is redeployed, hooks will break until config.json is updated
- **Alternative:** Use Coolify service discovery if available, or accept manual update on redeploy

---

### Step 9: Trigger First Backup

**Verify restic access:**

```bash
ssh vps "sudo docker exec backrest restic \
  -r s3:https://${B2_ENDPOINT}/${B2_BUCKET} \
  --password-file /restic-password \
  snapshots"
```

Expected: Empty list (no snapshots yet)

**Trigger postgres backup via Backrest API:**

```bash
# Trigger backup
ssh vps "curl -s -X POST http://localhost:9898/api/v1/plan/postgres-dumps/backup"

# Wait 30 seconds
sleep 30

# Check logs
ssh vps "sudo docker logs backrest --tail=50"

# Verify snapshot created
ssh vps "sudo docker exec backrest restic \
  -r s3:https://${B2_ENDPOINT}/${B2_BUCKET} \
  --password-file /restic-password \
  snapshots"
```

**Expected:** At least 1 snapshot listed with postgres dump data.

---

### Step 10: Add Gatus Monitoring

**File:** `/opt/monitoring/configs/gatus/apps/backrest.yaml`

```yaml
endpoints:
  - name: backrest
    group: services
    url: "tcp://backrest:9898"
    interval: 120s
    conditions:
      - "[CONNECTED] == true"
    alerts:
      - type: custom
        failure-threshold: 2
        send-on-resolved: true
```

**Commands:**

```bash
# Write Gatus config
ssh vps "sudo tee /opt/monitoring/configs/gatus/apps/backrest.yaml > /dev/null" << 'EOF'
endpoints:
  - name: backrest
    group: services
    url: "tcp://backrest:9898"
    interval: 120s
    conditions:
      - "[CONNECTED] == true"
    alerts:
      - type: custom
        failure-threshold: 2
        send-on-resolved: true
EOF

# Restart Gatus to load new config
ssh vps "sudo docker restart gatus-v8s4cokcwg0co4w8okkccc0w"
```

**Verification:**
- Check Gatus UI at status.vps1.ocoron.com
- Should show "backrest" endpoint with status

---

### Step 11: Update Documentation

**Files to update:**

1. **AGENTS.md** - Infrastructure Services table
   - Remove: `| Duplicati | backup.vps1.ocoron.com | Full VPS backup to Backblaze B2 |`
   - Add: `| Backrest | backup.vps1.ocoron.com | Restic-based backup UI → Backblaze B2 |`

2. **COOLIFY_STATUS.md** - Recently Migrated table
   - Add row for backrest with UUID and deployment date

3. **CHANGELOG.md** - Add entry
   ```markdown
   ### Added — Backrest Backup Service (2026-04-17)
   - Deployed Backrest (UUID: <uuid>) to replace Duplicati
   - Restic-based backups to Backblaze B2
   - Three backup plans: /opt configs, Docker volumes, PostgreSQL dumps
   - Automated pg_dump hooks for database backups
   - Apprise integration for failure notifications
   - Web UI at backup.vps1.ocoron.com (Authelia 2FA)
   - Gatus monitoring endpoint added
   ```

4. **MIGRATION_SUMMARY.md** - Update duplicati status
   - Change from "Removed" to "Replaced by Backrest"

---

## Success Criteria

- [ ] Backrest container running and healthy
- [ ] backup.vps1.ocoron.com accessible (returns 404 from Authelia - correct)
- [ ] At least 1 restic snapshot visible in B2
- [ ] PostgreSQL dump script tested and working
- [ ] Gatus monitoring endpoint active
- [ ] Restic password saved in password manager
- [ ] All documentation updated

---

## Rollback Plan

If deployment fails:

```bash
# Stop and remove container
ssh vps "sudo docker stop backrest && sudo docker rm backrest"

# Remove via Coolify API
curl -X DELETE https://coolify.vps1.ocoron.com/api/v1/applications/$BACKREST_UUID \
  -H "Authorization: Bearer $COOLIFY_TOKEN"

# Clean up directories (optional)
ssh vps "sudo rm -rf /opt/backrest /opt/backups/postgres"
```

---

## Security Notes

1. **Restic Password:** 64-character hex string, stored in `/opt/backrest/.restic-password` with 600 permissions
2. **B2 Credentials:** Embedded in Docker Compose (base64-encoded), not exposed in Coolify UI
3. **Authelia Protection:** Web UI requires 2FA login
4. **Read-only Mounts:** `/opt` and `/var/lib/docker/volumes` mounted read-only
5. **Docker Socket:** Mounted read-only for container inspection only

---

## Cost Estimate

**Backblaze B2 Pricing:**
- Storage: $0.005/GB/month
- Download: $0.01/GB (only when restoring)

**Estimated monthly cost:**
- 50GB backups: $0.25/month
- 100GB backups: $0.50/month
- 500GB backups: $2.50/month

**Retention policy keeps:**
- Daily: 7 days
- Weekly: 4 weeks
- Monthly: 3 months
- Yearly: 1 year

---

## Known Issues & Corrections from Original Task

### ❌ Issues in Original Specification

1. **Wrong API Endpoint:**
   - Original: `POST /api/v1/services`
   - Correct: `POST /applications/dockercompose`

2. **Wrong Environment Variable Handling:**
   - Original: Separate `POST /api/v1/services/{UUID}/envs` call
   - Correct: Embed in compose YAML, then base64-encode entire file

3. **Wrong Container Name:**
   - Original: `postgres-main`
   - Correct: `postgres-main-l0k4gk0kggc8okcwk0s4c8s8`

4. **Wrong Apprise Container Name:**
   - Original: `apprise`
   - Correct: `apprise-lcocgs4gs8ksg4g08w40ows8`

5. **Duplicati Already Removed:**
   - Original: Step 9 removes Duplicati
   - Reality: Already removed in 2026-04-17 cleanup
   - Action: Skip removal, update docs only

6. **Authelia Middleware Label:**
   - Original: `authelia@docker`
   - Correct: `authelia-forward@docker` (verify from existing services)

### ✅ Corrections Applied

- Using CoolifyClient driver with correct endpoint
- Base64-encoding compose with embedded credentials
- Using actual container names from `docker ps`
- Skipping Duplicati removal step
- Verifying Authelia middleware label before deployment

---

## Next Steps After Deployment

1. **Monitor first scheduled backup** (2 AM UTC+3 for postgres)
2. **Test restore process** with a small file
3. **Set up backup success notifications** (optional)
4. **Document restore procedure** in operations docs
5. **Add to monthly review checklist**

---

## Questions for Review

1. **B2 Credentials Ready?** Do you have B2_KEY_ID, B2_APP_KEY, B2_ENDPOINT, B2_BUCKET?
2. **Coolify UUIDs?** Should I auto-fetch or do you have them?
3. **Backup Schedule OK?** 2 AM postgres, 3 AM /opt, 3:30 AM volumes, 4 AM prune
4. **Retention Policy OK?** 7 daily, 4 weekly, 3 monthly, 1 yearly
5. **Proceed with Deployment?** Ready to execute all steps?
