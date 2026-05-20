# Full System Audit — VPS Health Check

Analyze this Ubuntu 24.04 LTS production VPS running Coolify with ~36 Docker containers. Be thorough, concrete, production-aware. No generic textbook answers — every finding must reference the actual data provided. If critical data is missing, say which command to run.

## Stack

- Ubuntu 24.04 LTS, 6 vCores (x86_64), 11GB RAM, 108GB disk
- Coolify v4 (container orchestration), Traefik v2.11 (reverse proxy + HTTPS)
- PostgreSQL 16 (shared `postgres-main`), Redis 7 (shared `redis-main`)
- Prometheus + Alertmanager + Grafana + Loki + Promtail + Gatus + GlitchTip + Netdata
- Backrest -> Backblaze B2 (backups)
- Docker daemon: `json-file` log driver with `tag: {{.Name}}`, max 10m x 3 files
- All containers on `coolify` Docker network (10.0.1.0/24)
- Coolify single-image Applications use UUID-based container names (e.g. `bs0wo48k4gwo440gcowscoc8-211159651770`); stable DNS aliases applied by `coolify-alias-watcher` systemd service

## Data Collection

**Automated** (run from WSL — script executes on VPS via SSH):
```bash
ssh vps 'sudo bash -s' < /opt/fabrik/scripts/audit/01-full-system.sh
```

**Or manual** — paste ALL outputs below (run on VPS via SSH):

```bash
# 1. System identity
uname -a
uptime
systemd-detect-virt
cat /etc/os-release | head -5

# 2. CPU & processes
top -bn1 | head -30
vmstat 1 5
ps aux --sort=-%mem | head -20
ps aux --sort=-%cpu | head -20

# 3. Memory
free -h
cat /proc/meminfo | grep -E "MemTotal|MemFree|MemAvailable|Buffers|Cached|SwapTotal|SwapFree|Dirty|Writeback"
swapon --show
cat /proc/sys/vm/swappiness
dmesg -T | grep -i "oom\|out of memory\|killed process" | tail -20

# 4. Disk & I/O
df -h
df -i
iostat -x 1 3 2>/dev/null || echo "iostat not installed — run: apt install sysstat"
lsblk
cat /etc/fstab

# 5. Network
ss -s
ss -tulpn
ip -s link show eth0 2>/dev/null || ip -s link show ens3 2>/dev/null || ip -s link
cat /etc/resolv.conf
resolvectl status 2>/dev/null | head -20

# 6. Services
systemctl --failed
systemctl list-units --type=service --state=running | wc -l
journalctl --disk-usage
du -sh /var/log/

# 7. Security
sudo ufw status verbose
sudo iptables -L DOCKER-USER -n --line-numbers
sudo ss -tlnp | grep -v "127.0.0.1\|::1\|10\.0\."
last -10
sudo journalctl -u ssh --since "24 hours ago" | grep -c "Failed password"
sudo aa-status 2>/dev/null | head -20

# 8. Docker & containers
sudo docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Image}}" | sort
sudo docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}\t{{.NetIO}}\t{{.BlockIO}}"
sudo docker system df
sudo docker ps --format "{{.Names}} {{.Status}}" | grep -i "restarting\|unhealthy\|exited"
sudo docker volume ls -f dangling=true
```

## Analysis Checklist

Cover ALL 8 domains. For each, state: OK / WARNING / CRITICAL + evidence.

### 1. System Identity & Baseline
- Kernel version, taint flags, virtualization type
- Uptime, load average vs core count (6 cores), load trajectory

### 2. CPU & Process Health
- Core utilization balance, software/hardware interrupts, steal time
- Zombie/orphan processes, runaway resource consumers
- Context switching rate (reasonable: <10k/s per core under normal load)

### 3. Memory & Swap
- True available memory (accounting for buffers/cache)
- Swap usage — any swap > 0 on an 11GB VPS with 36 containers is a warning
- OOM kills in dmesg — which container, when, why

### 4. Disk & I/O
- Disk usage vs capacity (108GB), inode exhaustion
- I/O wait, queue depth, read/write latency
- Mount options (noatime? discard for SSD?)

### 5. Network
- Socket states: excessive TIME_WAIT, CLOSE_WAIT, SYN_RECV
- Interface errors: drops, overruns, CRC
- DNS resolution health

### 6. Service Health
- Failed systemd units
- Journal disk usage (should be <500MB)
- Boot/recovery speed

### 7. Security
- Ports bound to 0.0.0.0 that shouldn't be (everything should be behind Traefik or coolify network)
- UFW + DOCKER-USER chain integrity
- SSH brute-force attempts in last 24h
- AppArmor enforcement

### 8. Docker & Container Health
- Containers in restart loop or unhealthy
- Memory usage per container vs limits (OOM risk)
- Dangling volumes/images consuming disk
- Top CPU/memory consumers — are any monitoring agents (Prometheus, Netdata, cAdvisor) consuming more than the services they monitor?

## Output Format

1. **EXECUTIVE SUMMARY** — 3 sentences: system viability (Healthy / Degraded / Critical), biggest risk, most urgent action
2. **CRITICAL ALERTS** — bulleted, immediate action required
3. **WARNINGS** — bulleted, needs attention within days
4. **MISSING DATA** — commands to run if any section can't be evaluated
5. **DOMAIN-BY-DOMAIN ANALYSIS** — all 8 domains, each with status + evidence
6. **REMEDIATION ROADMAP**:
   - Phase 1: Non-intrusive (safe to run now, zero downtime)
   - Phase 2: Scheduled maintenance (requires restarts or brief windows)
