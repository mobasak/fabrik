# VPS Disaster Recovery Guide

**Last Updated:** 2025-12-22
**Recovery Time Objective (RTO):** 1-2 hours
**Recovery Point Objective (RPO):** 24 hours (daily backups)

---

## Backup System Overview

| Component | Value |
|-----------|-------|
| **Backup Tool** | Duplicati |
| **Web UI** | https://backup.vps1.ocoron.com |
| **Password** | `fabrik2025` |
| **Storage Backend** | Backblaze B2 |
| **Bucket** | `vps1-ocoron-backups` |
| **Schedule** | Daily (configurable in UI) |
| **Retention** | 7 versions |

### B2 Credentials (Store Securely)

| Field | Value |
|-------|-------|
| Account ID | `0044e7ca36a086b0000000001` |
| Application Key | `K004hcjQVRBA8hLY0uZzzKEYg4crlq8` |
| Key Name | `vps1-b2-app-key` |

---

## What Is Backed Up

### Critical Data (Must Restore)

| Path | Contents | Size |
|------|----------|------|
| `/opt/traefik/` | SSL certs (acme.json), htpasswd, config | ~1MB |
| `/opt/*/compose.yaml` | Service definitions | ~50KB |
| `/opt/*/.env` | All secrets and credentials | ~10KB |
| `coolify-db` volume | Coolify PostgreSQL (projects, settings) | ~70MB |
| `proxy_postgres_data` volume | Proxy service database | ~48MB |

### Service Configs (Needed for Rebuild)

| Service | Path | Critical Files |
|---------|------|----------------|
| traefik | `/opt/traefik/` | `compose.yaml`, `traefik.yml`, `acme.json`, `htpasswd` |
| captcha | `/opt/captcha/` | `compose.yaml`, `.env` |
| emailgateway | `/opt/emailgateway/` | `compose.yaml`, `.env` |
| translator | `/opt/translator/` | `compose.yaml`, `.env` |
| namecheap | `/opt/namecheap/` | `compose.yaml`, `.env` |
| proxy | `/opt/proxy/` | `compose.yaml`, `.env` |
| redis | `/opt/redis/` | `compose.yaml` |
| netdata | `/opt/netdata/` | `compose.yaml` |
| duplicati | `/opt/duplicati/` | `compose.yaml` |

### Docker Volumes (Stateful Data)

| Volume | Service | Purpose | Critical? |
|--------|---------|---------|-----------|
| `coolify-db` | Coolify | PostgreSQL data | ✅ Yes |
| `proxy_postgres_data` | Proxy | Proxy database | ✅ Yes |
| `duplicati_duplicati-config` | Duplicati | Backup job config | ✅ Yes |
| `coolify-redis` | Coolify | Cache | ⚠️ Optional |
| `redis_redis-data` | Redis | App cache | ⚠️ Optional |
| `netdata_*` | Netdata | Monitoring cache | ❌ Skip |

### Excluded From Backup

| Pattern | Reason |
|---------|--------|
| `**/node_modules/` | Rebuilt on deploy |
| `**/__pycache__/` | Python cache |
| `**/.git/` | Already in GitHub |
| `**/*.log` | Ephemeral logs |
| `**/venv/` | Python virtual envs |
| `**/.venv/` | Python virtual envs |

---

## Disaster Recovery Procedure

### Prerequisites

- New VPS provisioned (Ubuntu 24.04 LTS)
- SSH access to new VPS
- Access to B2 console or rclone configured locally

### Step 1: Provision New VPS (15 min)

```bash
# Order new VPS from GreenCloud or provider
# Minimum specs: 4 vCPU, 8GB RAM, 80GB SSD
# Note the new IP address
export NEW_VPS_IP="x.x.x.x"
```

### Step 2: Initial Access & Hardening (20 min)

```bash
# SSH as root initially
ssh root@$NEW_VPS_IP

# Update system
apt update && apt upgrade -y

# Create deploy user
useradd -m -s /bin/bash ozgur
mkdir -p /home/ozgur/.ssh
cp ~/.ssh/authorized_keys /home/ozgur/.ssh/
chown -R ozgur:ozgur /home/ozgur/.ssh
chmod 700 /home/ozgur/.ssh
echo "ozgur ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

# Harden SSH
sed -i 's/PermitRootLogin yes/PermitRootLogin no/' /etc/ssh/sshd_config
sed -i 's/#PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config
systemctl restart sshd

# Configure firewall
ufw allow 22
ufw allow 80
ufw allow 443
ufw allow 1194
ufw allow 8000
ufw --force enable

# Install fail2ban
apt install -y fail2ban
systemctl enable fail2ban
```

### Step 3: Install Docker (10 min)

```bash
# Install Docker
curl -fsSL https://get.docker.com | sh
usermod -aG docker ozgur

# Configure log rotation
cat > /etc/docker/daemon.json << 'EOF'
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
EOF
systemctl restart docker
```

### Step 4: Install Coolify (15 min)

```bash
# Install Coolify
curl -fsSL https://get.coollabs.io/coolify/install.sh | bash

# Wait for Coolify to start
sleep 60

# Access Coolify at http://$NEW_VPS_IP:8000
# Complete initial setup in browser
```

### Step 5: Install rclone & Configure B2 (5 min)

```bash
# Install rclone
curl https://rclone.org/install.sh | sudo bash

# Configure B2
sudo rclone config create b2 b2 \
  account='0044e7ca36a086b0000000001' \
  key='K004hcjQVRBA8hLY0uZzzKEYg4crlq8'

# Verify access
sudo rclone ls b2:vps1-ocoron-backups/ | head -5
```

### Step 6: Download Latest Backup (10 min)

```bash
# Create restore directory
sudo mkdir -p /var/restore
cd /var/restore

# List available backups (find latest timestamp folder)
sudo rclone lsd b2:vps1-ocoron-backups/

# Download latest backup (replace TIMESTAMP with actual value)
# Note: Duplicati stores in its own format, you may need to use Duplicati CLI
# Alternative: Use Duplicati web UI from another machine to restore

# For manual file restore if backup was in raw format:
sudo rclone copy b2:vps1-ocoron-backups/LATEST/ /var/restore/ --progress
```

### Step 7: Restore /opt Folders (10 min)

```bash
# Create /opt structure
sudo mkdir -p /opt/{traefik,captcha,emailgateway,translator,namecheap,proxy,redis,netdata,duplicati}

# Restore from backup (adjust paths based on backup structure)
# If using Duplicati backup, install Duplicati first and use its restore

# Copy compose.yaml and .env files to each service folder
# Example:
sudo cp /var/restore/opt/traefik/* /opt/traefik/
sudo cp /var/restore/opt/captcha/* /opt/captcha/
# ... repeat for each service
```

### Step 8: Restore Docker Volumes (15 min)

```bash
# Create volumes
docker volume create coolify-db
docker volume create proxy_postgres_data

# Restore coolify-db
docker run --rm \
  -v coolify-db:/data \
  -v /var/restore/docker-volumes/coolify-db/_data:/backup:ro \
  alpine cp -a /backup/. /data/

# Restore proxy_postgres_data
docker run --rm \
  -v proxy_postgres_data:/data \
  -v /var/restore/docker-volumes/proxy_postgres_data/_data:/backup:ro \
  alpine cp -a /backup/. /data/
```

### Step 9: Start Services (10 min)

```bash
# Start Traefik first (handles routing)
cd /opt/traefik && docker compose up -d

# Start infrastructure services
cd /opt/redis && docker compose up -d

# Start application services
cd /opt/proxy && docker compose up -d
cd /opt/captcha && docker compose up -d
cd /opt/translator && docker compose up -d
cd /opt/namecheap && docker compose up -d
cd /opt/emailgateway && docker compose up -d

# Start monitoring
cd /opt/netdata && docker compose up -d
cd /opt/duplicati && docker compose up -d
```

### Step 10: Update DNS (5 min)

```bash
# Update DNS A records to point to new VPS IP
# Use namecheap service or Namecheap web console

# Records to update:
# - vps1.ocoron.com → NEW_IP
# - proxy.vps1.ocoron.com → NEW_IP
# - captcha.vps1.ocoron.com → NEW_IP
# - translator.vps1.ocoron.com → NEW_IP
# - namecheap.vps1.ocoron.com → NEW_IP
# - emailgateway.vps1.ocoron.com → NEW_IP
# - status.vps1.ocoron.com → NEW_IP
# - backup.vps1.ocoron.com → NEW_IP
```

### Step 11: Verify Services (10 min)

```bash
# Check all containers running
docker ps

# Test each service
curl -s https://proxy.vps1.ocoron.com/health
curl -s https://translator.vps1.ocoron.com/health
curl -s https://namecheap.vps1.ocoron.com/health
curl -s https://emailgateway.vps1.ocoron.com/health

# Access Coolify
# https://NEW_IP:8000 or configure domain
```

### Step 12: Reconfigure Backup (5 min)

```bash
# Access Duplicati at https://backup.vps1.ocoron.com
# Verify backup job is configured
# Run manual backup to verify
```

---

## Quick Recovery Checklist

```
[ ] New VPS provisioned
[ ] SSH hardened (no root, no password)
[ ] UFW firewall enabled
[ ] Docker installed
[ ] Coolify installed
[ ] rclone configured with B2
[ ] Backup downloaded
[ ] /opt folders restored
[ ] Docker volumes restored
[ ] Traefik started
[ ] All services started
[ ] DNS updated
[ ] Services verified
[ ] Backup reconfigured
```

---

## Testing Recovery (Recommended Quarterly)

1. Provision test VPS
2. Follow recovery steps
3. Verify all services work
4. Document any issues
5. Destroy test VPS

---

## Emergency Contacts

| Service | Contact |
|---------|---------|
| GreenCloud (VPS) | Support ticket |
| Backblaze B2 | support@backblaze.com |
| Namecheap (DNS) | Support ticket |

---

## Version History

| Date | Change |
|------|--------|
| 2025-12-22 | Initial document |
