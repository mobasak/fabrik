# 01 — Full System Audit (per host)

**Last Updated:** 2026-06-02 (rewritten for the 3-VPS fleet — was single-VPS Coolify-era — patched 2026-06-02 evening after live-validation: hub `/opt/fabrik/.env` check removed; that file is dev-WSL-only and the probe was a false-negative)
**Run mode:** **per host**. Run once on each VPS you want audited; collect outputs separately.
**Scope:** vps1 (hub, LA) ‖ vps2 (spoke, Coventry UK) ‖ vps3 (spoke, Coventry UK)
**Time budget:** ~15 min of command output + ~10 min of analysis per host.

---

## Stack context (paste into Claude alongside the output)

```text
- Fleet: 3-VPS Wireguard mesh (10.99.0.0/24). Hub vps1 = 10.99.0.1 (LA, 11.6 GiB / 6 cores).
  Spokes vps2 = 10.99.0.2 and vps3 = 10.99.0.3 (Coventry UK, 7.7 GiB / 4 cores each).
- Deploy mechanism: SSH + Docker Compose via `fabrik apply` (no Coolify — removed 2026-05-30).
- vps1 hosts 29 containers (shared infra + monitoring + WordPress tenant).
- vps2/vps3 host 5 containers each: traefik + monitoring agents (node-exporter, cadvisor,
  promtail) + backrest.
- All containers stable-named (no UUID suffix). All on the `fabrik` Docker network
  (renamed from `coolify` 2026-05-31).
- Backups: Backrest + restic → Backblaze B2.
  - Hub: 4 plans (postgres-dumps, docker-volumes, opt-configs, host-state).
  - Each spoke: 2 plans (host-state, opt-configs).
- Auth: Authelia 2FA on vps1 (forward-auth at https://auth.vps1.ocoron.com).
- Observability centralized on vps1: Prometheus + Grafana + Loki + Alertmanager.
  Spokes ship metrics/logs over mesh (UFW allow from 10.99.0.0/24).
- AI sysadmin: vps-sysadmin-bot.service on vps1 only.
- Reference docs: docs/infrastructure/vps-status.md, vps-complete-inventory.md,
  vps-fleet-architecture.md.
```

---

## Data collection — HUB (vps1)

```bash
ssh vps bash <<'EOF'
echo "=== HOST IDENTITY ==="
hostnamectl; cat /etc/lsb-release; uptime
echo
echo "=== CPU ==="
nproc; lscpu | grep -E "Model name|MHz|Cache"
top -bn1 | head -20
echo
echo "=== MEMORY ==="
free -h; sudo dmesg --since '1 day ago' | grep -i 'oom-killer' | tail -5
echo
echo "=== DISK ==="
df -h --total | grep -vE 'tmpfs|overlay'
sudo du -sh /var/lib/docker /opt/* 2>/dev/null | sort -hr | head -10
echo
echo "=== NETWORK (public + mesh) ==="
ip -4 addr show ens3 | grep inet
ip -4 addr show wg0 | grep inet
sudo wg show wg0 | head -30
ss -tlnp 2>&1 | grep LISTEN | sort -k4
echo
echo "=== DOCKER ==="
sudo docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
sudo docker network inspect fabrik --format "{{len .Containers}} containers on fabrik network"
echo
echo "=== FIREWALL ==="
sudo ufw status verbose
sudo iptables -L DOCKER-USER -n --line-numbers
sudo fail2ban-client status sshd
echo
echo "=== SERVICES ==="
systemctl list-unit-files --state=enabled --type=service | head -25
systemctl --failed
echo
echo "=== SECURITY ==="
sudo grep -E "^(PermitRootLogin|PasswordAuthentication)" /etc/ssh/sshd_config
last -n 15
sudo journalctl -u sshd --since "1 day ago" 2>/dev/null | grep -iE "failed|invalid user" | tail -10
echo
echo "=== HUB-SPECIFIC ==="
ls -la /opt/ 2>&1 | head -25
# /opt/fabrik/.env is dev-WSL-only (the fabrik CLI canonical, mirrored to GitHub).
# The hub only has /opt/fabrik/.env.sysadmin (Telegram bot token + owner ID).
# Don't probe for the dev-WSL file here — would always emit a false-negative.
ls -la /opt/fabrik/.env.sysadmin 2>&1
sudo systemctl status vps-sysadmin-bot.service --no-pager | head -10
EOF
```

## Data collection — SPOKE (vps2 or vps3)

```bash
ssh vps2 bash <<'EOF'    # repeat for vps3
echo "=== HOST IDENTITY ==="
hostnamectl; cat /etc/lsb-release; uptime
echo
echo "=== CPU + MEMORY + DISK ==="
nproc; lscpu | grep -E "Model name|MHz"
free -h
df -h --total | grep -vE 'tmpfs|overlay'
echo
echo "=== NETWORK (public + mesh) ==="
ip -4 addr show
sudo wg show wg0
ping -c 3 10.99.0.1
ss -tlnp 2>&1 | grep LISTEN | sort -k4
echo
echo "=== DOCKER (expect 5 containers) ==="
sudo docker ps --format "table {{.Names}}\t{{.Status}}"
sudo docker network inspect fabrik --format "{{len .Containers}}" 2>&1
echo
echo "=== FIREWALL (expect: 22/80/443/51820 + 'allow from 10.99.0.0/24') ==="
sudo ufw status verbose
sudo iptables -L DOCKER-USER -n
sudo fail2ban-client status sshd
echo
echo "=== SPOKE-SPECIFIC ==="
ls /opt/
sudo docker ps --filter "name=traefik" --format "{{.Names}} {{.Status}}"
sudo docker inspect traefik --format '{{range $k,$v := .Config.Labels}}{{$k}}={{$v}}{{println}}{{end}}' 2>&1 | grep gzip
sudo cat /opt/backrest/config/config.json | python3 -c "import json,sys; d=json.load(sys.stdin); print('backrest plans:', [p['id'] for p in d.get('plans',[])])"
EOF
```

---

## Analysis checklist

### 1. Identity & baseline

- Hostname matches `vpsN.ocoron.com` and `vpsN` short name.
- Ubuntu 24.04 LTS; kernel current.
- Uptime reasonable (no recent unplanned reboot).

### 2. CPU & process health

- Load average < `nproc` × 1.5 for hub; < `nproc` for spokes.
- No single process > 50% CPU sustained.
- Top processes match expected workload (docker, fabrik, postgres on hub; agents on spokes).

### 3. Memory & swap

- Used memory leaves > 20% free.
- No OOM-killer activity in last 24h.
- No swap thrashing.

### 4. Disk & I/O

- `/` < 80% used (hub typically ~27%, spokes ~11%).
- `/var/lib/docker` reasonable; no runaway image cache.
- No `/data/coolify/` growth (legacy; should stay around 201 MB residue on hub only).

### 5. Network

- Public iface (`ens3`) shows expected public IP.
- `wg0` shows `10.99.0.<N>` mesh IP.
- Mesh handshake within last 5 min (`latest handshake`).
- Only `22/80/443/1194/51820` (hub) or `22/80/443/51820` (spoke) listen on public; mesh-only services bind `10.99.0.1` on hub.

### 6. Docker

- Container count matches expectation (**hub: 29, spoke: 5**). Deviation = investigate.
- All containers `Up` (none `Restarting` or `Exited`).
- `fabrik` network exists; container count matches `docker ps`.
- **W15 check (spokes only):** `traefik` container has label `traefik.http.middlewares.gzip.compress=true`.

### 7. Firewall

- UFW `active`, default `deny (incoming)`.
- Hub: 6 v4 rules — 5 ALLOW (22/80/443/1194/51820) + 1 DENY on 8000 (carries a stale "Coolify raw port" comment; defense-in-depth, keep). Spokes: 5 v4 rules — 4 ALLOW (22/80/443/51820) + 1 ALLOW from `10.99.0.0/24` for mesh observability (W8 fix).
- DOCKER-USER: hub has 1 ACCEPT rule + ACCEPT-from-wg0 + DROP-mesh-only-ports from public; spokes have 2 rules.
- `fail2ban` active; ban counts non-zero on hub (internet-facing target).

### 8. Services & systemd

- No failed units in `systemctl --failed`.
- `wg-quick@wg0`, `docker`, `iptables-docker-user`, `fail2ban` all active.
- Hub: `vps-sysadmin-bot.service` active. Spokes: not installed.

### 9. Security

- SSH: `PermitRootLogin no`, `PasswordAuthentication no`.
- No suspicious failed-login spikes (compare to fail2ban ban count — fail2ban catching them = healthy).
- No active root SSH session beyond the audit run.

### 10. Spoke-only checks

- `/opt/` contains: `traefik/`, `monitoring-agent/`, `backrest/`, `containerd/`.
- Backrest config has 2 plans: `host-state`, `opt-configs`.
- Mesh ping to `10.99.0.1` succeeds.

---

## Output format

```markdown
## VPS Audit — <hostN> — <UTC date>

**Verdict:** GREEN / YELLOW / RED
**Summary:** one-paragraph

### Findings
1. [severity] <description>
   - Evidence: <command output excerpt>
   - Why it matters: <impact>
   - Fix: <command or doc link>

### Trends to watch
- ...

### What's correct (verify-not-fix)
- ...
```
