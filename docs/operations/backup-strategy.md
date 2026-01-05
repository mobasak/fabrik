# VPS Backup Strategy

Duplicati → Backblaze B2 for disaster recovery.

## Access

- **URL:** https://backup.vps1.ocoron.com
- **B2 Bucket:** `vps1-ocoron-backups`
- **Schedule:** Daily 5:00 AM

## Backup Configuration

### Source Paths

| Duplicati Path | VPS Path | Contains |
|----------------|----------|----------|
| `/source/opt/` | `/opt/` | Apps, SSH keys, OpenVPN, configs |
| `/source/docker-volumes/` | `/var/lib/docker/volumes/` | PostgreSQL, Redis data |
| `/source/data/coolify/` | `/data/coolify/` | Coolify DB, SSL, proxy |

### Exclusions

```
**/node_modules/, **/__pycache__/, **/.git/, **/*.log, **/venv/, **/.venv/
```

### Options

| Setting | Value |
|---------|-------|
| Encryption | None |
| Volume Size | 200 MB |
| Retention | Keep all versions |

## B2 Credentials (in fabrik .env)

```
B2_KEY_ID=0044e7ca36a086b0000000001
B2_APPLICATION_KEY=K004hcjQVRBA8hLY0uZzzKEYg4crlq8
B2_BUCKET_NAME=vps1-ocoron-backups
```

---

## Disaster Recovery Procedure

If VPS is completely lost, follow these steps:

### Step 1: Provision New VPS (5 min)

Get a new VPS with Ubuntu 22.04/24.04, then SSH in.

### Step 2: Install Docker (2 min)

```bash
curl -fsSL https://get.docker.com | sh
```

### Step 3: Install Coolify (5 min)

```bash
curl -fsSL https://cdn.coollabs.io/coolify/install.sh | bash
```

### Step 4: Run Duplicati for Restore (2 min)

```bash
docker run -d \
  --name duplicati-restore \
  -v /opt:/restore/opt \
  -v /data/coolify:/restore/data/coolify \
  -v /var/lib/docker/volumes:/restore/docker-volumes \
  -p 8200:8200 \
  lscr.io/linuxserver/duplicati:latest
```

### Step 5: Restore from B2 (30-60 min)

1. Open `http://NEW_VPS_IP:8200`
2. Click **Restore** → **Direct restore from backup files**
3. Storage Type: **B2 Cloud Storage**
4. Enter B2 credentials from fabrik .env
5. Bucket: `vps1-ocoron-backups`
6. Folder: `vps1-backup`
7. Select latest backup version
8. Restore paths:
   - `/source/opt/` → `/restore/opt/`
   - `/source/data/coolify/` → `/restore/data/coolify/`
   - `/source/docker-volumes/` → `/restore/docker-volumes/`
9. Click **Restore**

### Step 6: Restart Services (5 min)

```bash
# Stop restore container
docker stop duplicati-restore

# Restart Coolify to pick up restored config
systemctl restart coolify

# Verify all services start
docker ps
```

### Step 7: Update DNS (if IP changed)

If new VPS has different IP, update DNS records for:
- `vps1.ocoron.com` → new IP
- All subdomains (*.vps1.ocoron.com)

### Step 8: Restore OpenVPN (if needed)

```bash
# Copy OpenVPN config from backup
cp -r /opt/infrastructure/openvpn-backup/* /etc/openvpn/

# Restart OpenVPN
systemctl restart openvpn-server@server
```

### Step 9: Verify Services

```bash
# Check all containers running
docker ps

# Test health endpoints
curl https://translator.vps1.ocoron.com/health
curl https://captcha.vps1.ocoron.com/healthz
```

---

## Estimated Recovery Time

| Step | Duration |
|------|----------|
| New VPS + Docker + Coolify | 10 min |
| Duplicati restore | 30-60 min |
| Service verification | 10 min |
| **Total** | **~1 hour** |

---

## Fabrik Automation: Setting Up Backups on New VPS

When adding a new VPS to Fabrik management, use this procedure to set up automated backups.

### Prerequisites

1. Duplicati container deployed via Coolify with these volume mounts:
   - `/opt` → `/source/opt`
   - `/var/lib/docker/volumes` → `/source/docker-volumes`
   - `/data/coolify` → `/source/data/coolify`
   - Config volume → `/config`

2. B2 bucket created for the VPS (e.g., `vps2-ocoron-backups`)

3. B2 credentials added to `/opt/fabrik/.env`

### Automated Setup Script

Run from WSL after Duplicati container is deployed:

```bash
python /opt/fabrik/scripts/setup_duplicati_backup.py
```

### Manual Setup (if script unavailable)

#### Step 1: Create backup job in Duplicati database

```bash
# SSH to VPS and stop Duplicati
ssh vps "sudo docker stop duplicati"

# Insert backup job into SQLite
ssh vps "sudo sqlite3 /var/lib/docker/volumes/duplicati_duplicati-config/_data/Duplicati-server.sqlite \"
INSERT INTO Backup (Name, Description, Tags, TargetURL, DBPath) VALUES (
  'VPS Complete Backup',
  'Full VPS backup to Backblaze B2',
  '',
  'b2://BUCKET_NAME/vps-backup?b2-accountid=KEY_ID&b2-applicationkey=APP_KEY',
  '/config/VPS-Complete-Backup.sqlite'
);
INSERT INTO Source VALUES (1, '/source/opt/');
INSERT INTO Source VALUES (1, '/source/docker-volumes/');
INSERT INTO Source VALUES (1, '/source/data/coolify/');
INSERT INTO Filter VALUES (1, 0, 0, '**/node_modules/**');
INSERT INTO Filter VALUES (1, 1, 0, '**/__pycache__/**');
INSERT INTO Filter VALUES (1, 2, 0, '**/.git/**');
INSERT INTO Filter VALUES (1, 3, 0, '**/*.log');
INSERT INTO Filter VALUES (1, 4, 0, '**/venv/**');
INSERT INTO Filter VALUES (1, 5, 0, '**/.venv/**');
INSERT INTO Option VALUES (1, '', 'encryption-module', '');
INSERT INTO Option VALUES (1, '', 'no-encryption', 'true');
INSERT INTO Option VALUES (1, '', 'dblock-size', '200MB');
INSERT INTO Schedule VALUES (1, 'ID=1', strftime('%s', '2025-01-01 05:00:00'), '1D', 0, '');
\""

# Start Duplicati
ssh vps "sudo docker start duplicati"
```

#### Step 2: Run first backup to populate restore database

```bash
ssh vps "sudo docker exec duplicati /app/duplicati/duplicati-cli backup \
  'b2://BUCKET_NAME/vps-backup?b2-accountid=KEY_ID&b2-applicationkey=APP_KEY' \
  /source/opt /source/docker-volumes /source/data/coolify \
  --no-encryption \
  --dblock-size=200MB \
  --exclude='**/node_modules/**' \
  --exclude='**/__pycache__/**' \
  --exclude='**/.git/**' \
  --exclude='**/*.log' \
  --exclude='**/venv/**' \
  --exclude='**/.venv/**' \
  --dbpath=/config/VPS-Complete-Backup.sqlite"
```

#### Step 3: Set up cron job for scheduled backups

```bash
# Create backup script
ssh vps "sudo mkdir -p /opt/scripts && cat > /tmp/duplicati-backup.sh << 'EOF'
#!/bin/bash
docker exec duplicati /app/duplicati/duplicati-cli backup \
  'b2://BUCKET_NAME/vps-backup?b2-accountid=KEY_ID&b2-applicationkey=APP_KEY' \
  /source/opt /source/docker-volumes /source/data/coolify \
  --no-encryption \
  --dblock-size=200MB \
  --exclude='**/node_modules/**' \
  --exclude='**/__pycache__/**' \
  --exclude='**/.git/**' \
  --exclude='**/*.log' \
  --exclude='**/venv/**' \
  --exclude='**/.venv/**' \
  --dbpath=/config/VPS-Complete-Backup.sqlite \
  2>&1 | logger -t duplicati-backup
EOF
sudo mv /tmp/duplicati-backup.sh /opt/scripts/duplicati-backup.sh
sudo chmod +x /opt/scripts/duplicati-backup.sh"

# Set up cron (daily at 5 AM UTC)
ssh vps "echo '0 5 * * * root /opt/scripts/duplicati-backup.sh' | sudo tee /etc/cron.d/duplicati-backup"
```

### Key Configuration Notes

| Setting | Value | Reason |
|---------|-------|--------|
| `dblock-size` | 200MB | 1GB blocks can timeout on upload |
| `no-encryption` | true | B2 provides encryption at rest |
| `dbpath` | `/config/VPS-Complete-Backup.sqlite` | Must match DBPath in Backup table for UI restore |

### Verification

```bash
# Check job visible in Duplicati
ssh vps "sudo docker exec duplicati /app/duplicati/duplicati-server-util list-backups --password='PASSWORD'"

# Check B2 has backup files
python -c "
from b2sdk.v2 import B2Api, InMemoryAccountInfo
info = InMemoryAccountInfo()
api = B2Api(info)
api.authorize_account('production', 'KEY_ID', 'APP_KEY')
bucket = api.get_bucket_by_name('BUCKET_NAME')
files = list(bucket.ls(recursive=True))
print(f'Files: {len(files)}, Size: {sum(f.size for f,_ in files)/1024/1024/1024:.2f} GB')
"
```

### Troubleshooting

See `/opt/fabrik/docs/TROUBLESHOOTING.md` → Duplicati Issues section.
