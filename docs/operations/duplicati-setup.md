# Duplicati Backup Setup Guide

**URL:** https://backup.vps1.ocoron.com
**Password:** `fabrik2025`
**Status:** ✅ Fully configured with postgres-main included (2025-12-23)
**Restart Policy:** `always` (survives reboots)

---

## ⚠️ VPS Storage Constraints

| Resource | Value | Notes |
|----------|-------|-------|
| **Total Disk** | 108 GB | Single disk, no expansion |
| **Used** | 34 GB (31%) | As of 2025-12-23 |
| **Available** | 75 GB | Monitor closely |

**Implications for backups:**
- Duplicati stores temporary data locally before upload
- Keep local backup retention minimal
- All backups go to B2 (unlimited cloud storage)
- Monitor `/var/lib/docker` growth

---

## Current Backup Job

| Setting | Value |
|---------|-------|
| **Name** | VPS Complete Backup |
| **ID** | 1 |
| **Destination** | B2: `vps1-ocoron-backups/duplicati/` |
| **Encryption** | AES-256 (passphrase: `fabrik2025backup`) |
| **Retention** | 7 versions |
| **Schedule** | Daily 02:00 |
| **Source Size** | ~16 GB |
| **First Backup** | 2025-12-23 |

### Backup Sources

| Path | Contents | Critical? |
|------|----------|-----------|
| `/source/opt/` | All service configs | ✅ Yes |
| `/source/docker-volumes/` | Container volumes | ✅ Yes |
| `/source/data/coolify/` | **postgres-main + Coolify config** | ✅ **Critical** |

> **Note:** The `/source/data/coolify/` mount was added on 2025-12-23 to include postgres-main database. Without this, database recovery would fail.

---

## Container Changes Log

### 2025-12-23: Added /data/coolify mount

**Problem:** postgres-main database (199MB) was NOT being backed up.

**Cause:** postgres-main uses bind mount at `/data/coolify/databases/postgres-main/`, not a Docker volume.

**Fix:** Recreated Duplicati container with additional mount:

```bash
# Old container stopped and removed
docker stop duplicati && docker rm duplicati

# New container with /data/coolify mount added
docker run -d \
  --name duplicati \
  --restart unless-stopped \
  --network coolify \
  -e SETTINGS_ENCRYPTION_KEY=fabrik2025duplicati \
  -v duplicati_duplicati-config:/config \
  -v /var/backups:/backups \
  -v /opt:/source/opt:ro \
  -v /var/lib/docker/volumes:/source/docker-volumes:ro \
  -v /data/coolify:/source/data/coolify:ro \
  -l 'traefik.enable=true' \
  -l 'traefik.http.routers.duplicati.rule=Host(`backup.vps1.ocoron.com`)' \
  -l 'traefik.http.routers.duplicati.entrypoints=websecure' \
  -l 'traefik.http.routers.duplicati.tls.certresolver=letsencrypt' \
  -l 'traefik.http.services.duplicati.loadbalancer.server.port=8200' \
  --log-opt max-size=10m \
  --log-opt max-file=3 \
  lscr.io/linuxserver/duplicati:latest
```

**Result:** `/source/data/coolify/` now available in Duplicati for backup sources.

### 2025-12-23: Final Working Configuration

Fresh container created with:
- Restart policy: `always`
- Password: `fabrik2025`
- Settings encryption key: `fabrik2025duplicati`
- All three source mounts configured
- Backup job imported via ServerUtil CLI

```bash
docker run -d \
  --name duplicati \
  --restart always \
  --network coolify \
  -e PUID=0 \
  -e PGID=0 \
  -e SETTINGS_ENCRYPTION_KEY=fabrik2025duplicati \
  -v duplicati_duplicati-config:/config \
  -v /var/backups:/backups \
  -v /opt:/source/opt:ro \
  -v /var/lib/docker/volumes:/source/docker-volumes:ro \
  -v /data/coolify:/source/data/coolify:ro \
  -l 'traefik.enable=true' \
  -l 'traefik.http.routers.duplicati.rule=Host(`backup.vps1.ocoron.com`)' \
  -l 'traefik.http.routers.duplicati.entrypoints=websecure' \
  -l 'traefik.http.routers.duplicati.tls.certresolver=letsencrypt' \
  -l 'traefik.http.services.duplicati.loadbalancer.server.port=8200' \
  --log-opt max-size=10m \
  --log-opt max-file=3 \
  lscr.io/linuxserver/duplicati:latest
```

---

## Automation with `setup_duplicati_backup.py`

Fabrik includes a Python script for full automation of Duplicati setup and execution on the VPS.

**Location:** `scripts/setup_duplicati_backup.py`

### Features
- **Auto-Provisioning**: Stops Duplicati, wipes existing jobs, and creates a fresh "VPS Complete Backup" job with correct B2 credentials and source paths.
- **Critical Path Inclusion**: Automatically includes `/opt`, `/var/lib/docker/volumes`, and `/data/coolify` (postgres-main).
- **Exclude Pattern Management**: Pre-configures standard excludes (node_modules, .git, .venv, logs).
- **Cron Setup**: Automatically installs a daily backup script and cron job on the VPS.
- **Manual Execution**: Allows triggering a backup run directly from the CLI.

### Usage

```bash
# Setup the backup job and cron (Requires B2 credentials in .env)
python scripts/setup_duplicati_backup.py

# Manually trigger a backup run
python scripts/setup_duplicati_backup.py --run-backup
```

### Configuration
The script uses environment variables from the project `.env` file:
- `B2_BUCKET_NAME`: Target B2 bucket (default: `vps1-ocoron-backups`)
- `B2_KEY_ID`: Backblaze application key ID
- `B2_APPLICATION_KEY`: Backblaze application key

## ServerUtil CLI (Automation)

Duplicati can be managed via `duplicati-server-util` inside the container:

```bash
# Login (saves persistent token)
ssh vps "sudo docker exec duplicati /app/duplicati/duplicati-server-util login --password=fabrik2025 --settings-encryption-key=fabrik2025duplicati"

# List backups
ssh vps "sudo docker exec duplicati /app/duplicati/duplicati-server-util list-backups"

# Run backup manually
ssh vps "sudo docker exec duplicati /app/duplicati/duplicati-server-util run 2"

# Check status
ssh vps "sudo docker exec duplicati /app/duplicati/duplicati-server-util status"

# Import new backup config
ssh vps "sudo docker exec duplicati /app/duplicati/duplicati-server-util import /tmp/config.json <passphrase>"
```

---

## Step 1: Login (Web UI)

1. Open https://backup.vps1.ocoron.com
2. Enter password: `fabrik2025`
3. Click "OK"

---

## Step 2: Add New Backup

1. Click **"Add backup"** on the left sidebar
2. Select **"Configure a new backup"**
3. Click **"Next"**

---

## Step 3: General Settings

| Field | Value |
|-------|-------|
| Name | `VPS Daily Backup` |
| Description | `Full VPS backup to B2 - configs, volumes, databases` |
| Encryption | AES-256 (recommended) |
| Passphrase | `fabrik2025backup` (SAVE THIS - needed for restore!) |

Click **"Next"**

---

## Step 4: Backup Destination (B2)

1. Storage Type: Select **"B2 Cloud Storage"**

2. Enter these values:

| Field | Value |
|-------|-------|
| Bucket | `vps1-ocoron-backups` |
| Folder path | `duplicati` |
| B2 Account ID | `0044e7ca36a086b0000000001` |
| B2 Application Key | `K004hcjQVRBA8hLY0uZzzKEYg4crlq8` |

3. Click **"Test connection"** - should show success

4. Click **"Next"**

---

## Step 5: Source Data

### Folders to Include (check these):

**Service Configs:**
```
/source/opt/traefik/
/source/opt/captcha/
/source/opt/emailgateway/
/source/opt/translator/
/source/opt/namecheap/
/source/opt/proxy/
/source/opt/redis/
/source/opt/netdata/
/source/opt/duplicati/
/source/opt/email-reader/
/source/opt/youtube/
```

**Docker Volumes (Critical Data):**
```
/source/docker-volumes/coolify-db/
/source/docker-volumes/proxy_postgres_data/
/source/docker-volumes/duplicati_duplicati-config/
```

### Folders to EXCLUDE:
- `/source/opt/containerd/`
- `/source/opt/CLEANUP-*`
- `/source/opt/test-*`
- `/source/opt/backupsystem/`
- `/source/opt/BackupSystem/`
- `/source/opt/backup/`

Click **"Next"**

---

## Step 6: Schedule

| Field | Value |
|-------|-------|
| Automatically run backups | ✅ Enabled |
| Run every | 1 day |
| At | 02:00 |
| Allowed days | All days |

Click **"Next"**

---

## Step 7: Options

### General Options:
| Option | Value |
|--------|-------|
| Remote volume size | 50 MB |
| Backup retention | Keep a specific number of backups: **7** |

### Filters (Add these exclude filters):

Click **"Add filter"** and add:
```
-**/node_modules/
-**/__pycache__/
-**/.git/
-**/*.log
-**/*.pyc
-**/venv/
-**/.venv/
-**/.cache/
```

Click **"Save"**

---

## Step 8: Run First Backup

1. On the backup job page, click **"Run now"**
2. Watch progress in the UI
3. First backup may take 5-10 minutes

---

## How to View Backups

### View Backup History:
1. Click on your backup job name ("VPS Daily Backup")
2. Click **"Show log"** → See all backup runs with timestamps

### Browse Backed Up Files:
1. Click on your backup job
2. Click **"Restore"**
3. Browse files by date/version
4. You can explore the full folder structure

### View in B2 Console:
1. Go to https://secure.backblaze.com/b2_buckets.htm
2. Login with Backblaze account
3. Click on `vps1-ocoron-backups` bucket
4. Browse `duplicati/` folder

---

## Restore Files

### Restore Specific Files:
1. Click backup job → **"Restore"**
2. Select version (date)
3. Browse and check files to restore
4. Choose destination:
   - Original location
   - Pick location
   - Download as ZIP
5. Click **"Restore"**

### Full Disaster Recovery:
See: [disaster-recovery.md](disaster-recovery.md)

---

## Backup Job Status Icons

| Icon | Meaning |
|------|---------|
| ✅ Green | Backup completed successfully |
| ⚠️ Yellow | Backup completed with warnings |
| ❌ Red | Backup failed |
| 🔄 Spinning | Backup in progress |

---

## Troubleshooting

### "Connection test failed"
- Verify B2 credentials
- Check bucket name spelling
- Ensure B2 application key has read/write access

### "Backup stuck"
- Check VPS disk space: `df -h`
- Check Duplicati logs in UI
- Restart container: `cd /opt/duplicati && docker compose restart`

### "Cannot access web UI"
- Check container running: `docker ps | grep duplicati`
- Check Traefik routing: `docker logs traefik | grep duplicati`
- Try direct access: `curl http://localhost:8200/`

---

## Important Credentials Summary

| Item | Value |
|------|-------|
| Web UI URL | https://backup.vps1.ocoron.com |
| Web UI Password | `fabrik2025` |
| Encryption Passphrase | `fabrik2025backup` |
| B2 Account ID | `0044e7ca36a086b0000000001` |
| B2 Application Key | `K004hcjQVRBA8hLY0uZzzKEYg4crlq8` |
| B2 Bucket | `vps1-ocoron-backups` |
