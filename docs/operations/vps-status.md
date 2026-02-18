# VPS Status

**Last Updated:** 2025-12-23 15:05 UTC+3
**Host:** vps1.ocoron.com (172.93.160.197)
**SSH:** `ssh vps` (ozgur user, key-only auth)

---

## System Overview

| Component | Value |
|-----------|-------|
| **OS** | Ubuntu 24.04.3 LTS (Noble Numbat) |
| **Kernel** | 6.8.0-87-generic |
| **Disk** | 108GB total, 75GB available (31% used) ⚠️ Limited |
| **Memory** | 11GB total, 10GB available |
| **Swap** | 2GB |
| **Snap Usage** | 8.1GB in /snap |

### ⚠️ Storage Warning

**This VPS has limited HDD storage (108GB total).** Plan accordingly:

- No local backup retention - all backups go directly to B2 cloud
- Monitor `/var/lib/docker` growth regularly
- Clean up unused Docker images: `docker system prune`
- PostgreSQL databases stored at `/data/coolify/databases/`
- Consider upgrading VPS or adding block storage if usage exceeds 70%

---

## Security Status

| Component | Status | Notes |
|-----------|--------|-------|
| **SSH Hardening** | ✅ Done | Root login disabled, password auth disabled |
| **UFW Firewall** | ✅ Active | Ports 22, 80, 443 only |
| **Fail2ban** | ✅ Running | SSH jail active |
| **Unattended Upgrades** | ✅ Running | apt-daily timers active |

### SSH Configuration

```text
PermitRootLogin No
PasswordAuthentication No
AllowUsers ozgur (implied)
```

### SSH Troubleshooting (Port 22 Blocked)

**Incident Date:** 2026-01-21

**Symptoms:**
- Port 22 connection refused
- Web services (80, 443, 8000) still working
- VPS responds to ping

**Root Causes Found:**
1. `/run/sshd` directory was missing (tmpfs issue after reboot)
2. `ssh.socket` activation got into bad state, blocking `ssh.service`

**Fix Applied (via GreenCloudVPS VNC console):**
```bash
# 1. Install SSH if missing
sudo apt update && sudo apt install -y openssh-server

# 2. Create missing directory
sudo mkdir -p /run/sshd
sudo chmod 755 /run/sshd

# 3. Disable socket activation (prevents dependency issues)
sudo systemctl disable --now ssh.socket

# 4. Add RuntimeDirectory override (prevents /run/sshd missing on reboot)
sudo mkdir -p /etc/systemd/system/ssh.service.d
echo -e '[Service]\nRuntimeDirectory=sshd\nRuntimeDirectoryMode=0755' | sudo tee /etc/systemd/system/ssh.service.d/override.conf

# 5. Reload and start
sudo systemctl daemon-reload
sudo systemctl enable ssh
sudo systemctl start ssh

# 6. Verify
systemctl is-active ssh && ss -lntp | grep :22
```

**Prevention (Already Applied):**
- `ssh.socket` disabled permanently
- `RuntimeDirectory=sshd` override ensures `/run/sshd` created on every boot
- GreenCloudVPS console credentials stored in `/opt/fabrik/.env`

**Emergency Access:**
- URL: https://greencloudvps.com
- Use VNC console when SSH is down
- Credentials: See `GREENCLOUDVPS_*` in `/opt/fabrik/.env`

---

## Installed Software

| Software | Version | Status |
|----------|---------|--------|
| **Docker** | 29.0.2 | ✅ Installed |
| **Docker Compose** | 2.40.3 | ✅ Installed |
| **PostgreSQL** | - | ✅ Removed (2025-12-21) |
| **OpenVPN** | Running | ✅ Keep (intentional) |
| **Tor** | - | ✅ Removed (2025-12-21) — will be per-container |
| **Postfix (SMTP)** | Running | ✅ Send-only (loopback-only, localhost only) |
| **CUPS** | Snap | ✅ Disabled (2025-12-21) |
| **ModemManager** | - | ✅ Disabled (2025-12-21) |
| **Chromium** | - | ✅ Removed (2025-12-21) — will be per-container |
| **Coolify** | 4.0.0-beta.455 | ✅ Installed (2025-12-21) |

---

## Running Services (Current)

| Port | Service | Binding | Status |
|------|---------|---------|--------|
| 22 | SSH | 0.0.0.0 | ✅ Open (UFW allowed) |
| 25 | SMTP (Postfix) | 127.0.0.1 | ✅ Localhost only (send-only) |
| 80 | HTTP | - | ✅ UFW allowed (for Coolify) |
| 443 | OpenVPN + HTTPS | 0.0.0.0 | ✅ Open (UFW allowed) |

**Removed/Disabled:**

- Port 5432 (PostgreSQL) — Uninstalled 2025-12-21
- Port 631 (CUPS) — Disabled 2025-12-21
- Port 4713 (PulseAudio) — Killed 2025-12-21
- proxy_validation/sync services — Removed 2025-12-21

---

## Custom Services Found

### Useful (Keep)

| Service | Timer | Purpose |
|---------|-------|---------|
| `duplicati` | Daily 02:00 | Incremental backup to B2 via https://backup.vps1.ocoron.com |

---

## Systemd Timers (Active)

| Timer | Schedule | Purpose | Status |
|-------|----------|---------|--------|
| apt-daily.timer | Daily | Package list update | ✅ Keep |
| apt-daily-upgrade.timer | Daily | Auto upgrades | ✅ Keep |
| logrotate.timer | Daily | Log rotation | ✅ Keep |
| vps-backup.timer | Daily 02:00 | Custom backup | ✅ Keep |
| fstrim.timer | Weekly | SSD maintenance | ✅ Keep |

---

## Cron Jobs

| Location | Jobs |
|----------|------|
| root crontab | None |
| ozgur crontab | None |
| /etc/cron.daily | apport, apt-compat, dpkg, logrotate, man-db, sysstat |
| /etc/cron.d | e2scrub_all, sysstat |

All standard Ubuntu cron jobs — nothing custom.

---

## Container Strategy: Tor & Headless Browsers

**Decision (2025-12-21):** Per-container approach — each Docker container includes its own dependencies.

| Dependency | System-wide | Per-Container |
|------------|-------------|---------------|
| Tor | ❌ Removed | ✅ YouTube docker will install |
| Chromium | ❌ Removed | ✅ Containers use Playwright install |

**Why per-container:**

- Containers are self-contained and portable
- No VPS-specific dependencies
- Easier debugging — everything in one container
- Clean host system — only Docker + Coolify

---

## Docker Status

| Item | Status |
|------|--------|
| Docker daemon | ✅ Running |
| Running containers | 11 (Coolify stack + Tier 1 services) |
| Networks | coolify (shared) |

### Running Containers (2025-12-22 13:43 UTC+3)

| Container | Port | Status | Health Check |
|-----------|------|--------|--------------|
| traefik | 80, 443, 8080 | ✅ Running | — |
| postgres-main | internal | ✅ Running | `SELECT 1` ✅ |
| proxy | internal (via Traefik) | ✅ Running | `/health` ✅ |
| captcha | internal (via Traefik) | ✅ Running | `/` returns service info ✅ |
| translator | internal (via Traefik) | ✅ Running | `/health` ✅ (deepl active) |
| namecheap | internal (via Traefik) | ✅ Running | `/health` ✅ |
| emailgateway | internal (via Traefik) | ✅ Running | `/health` ✅ |
| netdata | internal (via Traefik) | ✅ Running | `/api/v1/info` ✅ |
| redis-main | internal | ✅ Running | `redis-cli ping` ✅ |
| duplicati | internal (via Traefik) | ✅ Running | Web UI at :8200 |
| coolify | 8000 | ✅ Running |
| coolify-db | internal | ✅ Running |
| coolify-redis | internal | ✅ Running |
| coolify-realtime | 6001-6002 | ✅ Running |
| coolify-sentinel | internal | ✅ Running |

---

## Completed Actions

### 2025-12-21

| Action | Status |
|--------|--------|
| PostgreSQL uninstalled | ✅ |
| CUPS snap disabled | ✅ |
| ModemManager disabled | ✅ |
| PulseAudio killed | ✅ |
| Proxy services removed | ✅ |
| Postfix set to loopback-only | ✅ |
| UFW enabled (22, 80, 443) | ✅ |
| Fail2ban installed | ✅ |
| Tor removed (per-container) | ✅ |
| Chromium snap removed (per-container) | ✅ |
| Coolify installed | ✅ |
| PostgreSQL (postgres-main) deployed | ✅ |

### 2025-12-22

| Action | Status |
|--------|--------|
| WSL databases migrated to VPS | ✅ |
| Tier 1 services deployed | ✅ |
| OpenVPN moved to port 1194 | ✅ |
| Traefik deployed (80/443) | ✅ |
| Services moved behind Traefik | ✅ |
| Host port mappings removed | ✅ |
| DNS records created via namecheap API | ✅ |
| Let's Encrypt certs obtained | ✅ |
| Proxy service DB connection fixed | ✅ |
| Proxy service DB permissions granted | ✅ |
| All services restart policy verified | ✅ |
| Netdata monitoring deployed | ✅ |
| Netdata secured with basic auth | ✅ |
| All Tier 1 services functionally verified | ✅ |
| Redis-main deployed | ✅ |
| Duplicati backup deployed (replaces bash script) | ✅ |
| Duplicati backup job created via ServerUtil | ✅ |
| First backup completed and verified on B2 | ✅ |
| Docker log rotation verified | ✅ |
| VPS /opt cleanup - freed 15GB | ✅ |
| Duplicati complete backup with postgres-main | ✅ |
| Uptime Kuma deployed | ✅ |

**VPS Cleanup (2025-12-23 15:00):**
- Deleted: youtube/ (15GB), Proxy/, BackupSystem/, shared-docs/, test-project/, CLEANUP-BACKUP-*/, backup/, backupsystem/
- Kept: All active service folders (synced from WSL or deployed)
- Disk usage: 34GB → 19GB (17% used, 90GB available)

**Functional verification (2025-12-22 14:10):**
- captcha: AntiCaptcha provider connected (balance: 0.0)
- translator: DeepL provider active, API key validation working
- namecheap: Returns real domains (5) and DNS records (14 for ocoron.com)
- emailgateway: Resend provider connected (490ms latency)
- postgres-main: 7 databases, 204 proxies in proxy_management

**Proxy fixes applied:**
- `db_proxy_manager_api.py`: Changed hardcoded `localhost` to `os.getenv('DB_HOST')`
- `api.py`: Fixed `PostgresAdapter()` call to pass `DB_CONFIG`
- `api.py`: Fixed method `execute_query` → `fetchall`
- PostgreSQL: Granted `ozgur` user permissions on `proxy_management` tables

---

## PostgreSQL Connection

```text
Host: postgres-main (inside coolify network)
Port: 5432
User: postgres
Password: fabrik2025secure
Database: fabrik
Internal URL: postgres://postgres:fabrik2025secure@postgres-main:5432/fabrik
```

---

## Network Architecture

### Current State (2025-12-22)

```text
Internet
    │
    ├── :22   → SSH (UFW allowed)
    ├── :80   → Traefik (HTTP → HTTPS redirect)
    ├── :443  → Traefik (HTTPS with Let's Encrypt)
    ├── :1194 → OpenVPN
    ├── :8000 → Coolify UI
    └── :8080 → Traefik Dashboard

Traefik → coolify network → services (internal, no host ports)
```

### Traefik Configuration

| Setting | Value |
|---------|-------|
| Image | traefik:v2.11 |
| HTTP | :80 (redirects to HTTPS) |
| HTTPS | :443 (Let's Encrypt) |
| Dashboard | :8080 |
| Config | /opt/traefik/traefik.yml |
| Certs | /opt/traefik/acme.json |

### Service Routing (via Traefik)

| Service | External URL | Internal URL |
|---------|--------------|--------------|
| proxy | https://proxy.vps1.ocoron.com | http://proxy:8000 |
| captcha | https://captcha.vps1.ocoron.com | http://captcha:8000 |
| translator | https://translator.vps1.ocoron.com | http://translator:8000 |
| namecheap | https://namecheap.vps1.ocoron.com | http://namecheap:8001 |
| emailgateway | https://emailgateway.vps1.ocoron.com | http://emailgateway:3000 |
| netdata | https://status.vps1.ocoron.com (auth required) | http://netdata:19999 |
| duplicati | https://backup.vps1.ocoron.com | http://duplicati:8200 |
| postgres | N/A | postgres-main:5432 |
| redis | N/A | redis-main:6379 |

**External:** Public HTTPS via Traefik + Let's Encrypt
**Netdata:** Protected with basic auth (credentials in `/opt/traefik/htpasswd`)
**Internal:** Container-to-container via Docker DNS on `coolify` network

### UFW Rules (Current)

| Port | Action | Purpose |
|------|--------|---------|
| 22 | ALLOW | SSH |
| 80 | ALLOW | Traefik HTTP |
| 443 | ALLOW | Traefik HTTPS |
| 1194 | ALLOW | OpenVPN |
| 8000 | ALLOW | Coolify UI |
| 8080 | ALLOW | Traefik Dashboard |

---

## Next Steps

### 1. ~~Install Coolify~~ ✅ Done

### 2. ~~Deploy PostgreSQL~~ ✅ Done

### 3. ~~Migrate WSL Databases~~ ✅ Done

### 4. ~~Deploy Tier 1 Services~~ ✅ Done

### 5. ~~Deploy Traefik~~ ✅ Done

### 6. ~~Configure DNS Records~~ ✅ Done

DNS A records created via namecheap service API:

| Subdomain | IP | Status |
|-----------|----|----|
| proxy.vps1.ocoron.com | 172.93.160.197 | ✅ |
| captcha.vps1.ocoron.com | 172.93.160.197 | ✅ |
| translator.vps1.ocoron.com | 172.93.160.197 | ✅ |
| namecheap.vps1.ocoron.com | 172.93.160.197 | ✅ |
| emailgateway.vps1.ocoron.com | 172.93.160.197 | ✅ |

### 7. Deploy Tier 2 Services (Pending)

| Service | Status |
|---------|--------|
| youtube | Pending |
| calendar-orchestration-engine | Pending |
| llm_batch_processor | Pending |

---

## Owned Domains (Namecheap)

| Domain | Expires | AutoRenew | Purpose |
|--------|---------|-----------|---------|
| **ocoron.com** | 2032-06-18 | ✅ | Primary infrastructure |
| **ozgurbasak.com** | 2027-11-22 | ✅ | Personal |
| **aktivitepaketi.com** | 2026-04-10 | ✅ | Project |
| **longephedia.com** | 2026-04-30 | ✅ | Project |
| **tojlo.com** | 2026-04-21 | ✅ | Project |

All domains use Namecheap DNS and have WhoisGuard enabled.

---

## Reference

- **Phase 1 Tasks:** [tasks.md](../../tasks.md)
- **Phase 1 Narrative:** [Phase1.md](../reference/Phase1.md)
- **Stack Overview:** [stack.md](../reference/stack.md)
- **Disaster Recovery:** [disaster-recovery.md](disaster-recovery.md)
- **Duplicati Setup:** [duplicati-setup.md](duplicati-setup.md)
- **Active Roadmap:** [ROADMAP_ACTIVE.md](../ROADMAP_ACTIVE.md)
- **Fabrik Drivers:** [drivers.md](../reference/drivers.md)
