# VPS Bootstrap Automation — Future Plan

**Status:** Planned
**Created:** 2026-05-20
**State capture:** `docs/infrastructure/vps-captured-state-20260520.txt` (737 lines, full VPS config dump)

## Goal

Fresh Ubuntu 24.04 → fully provisioned VPS with complete stack in ~15 minutes via automated script. Eliminates manual setup, ensures reproducibility, enables instant VPS cloning.

## Approach

Two scripts:

1. **`scripts/provision-vps.sh`** — runs on fresh Ubuntu, installs and configures everything
2. **`scripts/configure-vps-instance.sh`** — per-instance customization (hostname, secrets, domains)

After both succeed → Hetzner snapshot → golden image for instant clones.

## What the Provisioning Script Must Codify

Extracted from VPS state capture 2026-05-20:

### System Hardening
- SSH: Ed25519 keys, `PermitRootLogin No`, `PasswordAuthentication No`
- UFW: ports 22, 80, 443, 1194, 6001, 6002 ALLOW; 8000 DENY
- DOCKER-USER iptables chain: 9 rules (`/etc/iptables/add-docker-user-rules.sh`)
- `iptables-docker-user.service` (systemd, after docker)
- fail2ban for SSH jail
- sysctl: `vm.swappiness=10`, `net.ipv4.ip_forward=1` (OpenVPN)
- Kernel hardening: all `/etc/sysctl.d/10-*.conf` files (Ubuntu defaults — verify present)

### Docker
- Docker CE install
- `/etc/docker/daemon.json`: json-file driver, max-size 10m, max-file 3, tag `{{.Name}}`, DNS 1.1.1.1/8.8.8.8, address pool 10.0.0.0/8

### Coolify
- Coolify v4 install (official one-liner)
- Traefik v2.11 configuration

### OpenVPN
- Server config at `/etc/openvpn/server/`
- `iptables-openvpn.service` + NAT rules
- sysctl `ip_forward=1`

### Monitoring Stack (non-Coolify managed)
- `/opt/monitoring/compose.yaml`: prometheus, alertmanager, node-exporter, cadvisor, postgres-exporter, redis-exporter, pushgateway
- `/opt/monitoring/configs/prometheus/prometheus.yml` + rules/alerts.yml + rules/fabrik-drift.yml
- `/opt/monitoring/configs/alertmanager/alertmanager.yml`
- `/opt/monitoring/configs/loki/loki-config.yaml`
- `/opt/monitoring/configs/promtail/promtail-config.yaml`
- `/opt/monitoring/configs/grafana/provisioning/` (datasources + dashboards + json-dashboards)
- `/opt/monitoring/configs/gatus/` (all endpoint YAML files)
- `/opt/monitoring/configs/redis/assignments.json`
- `/opt/monitoring/configs/postgres/allocations.json`

### Coolify Services (deployed via `fabrik apply` (SSH + Docker Compose)/UI)
- Grafana, Loki, Promtail, Gatus, cAdvisor, node-exporter, Alertmanager
- Authelia, Apprise, Backrest, n8n, Netdata
- GlitchTip (web + worker)
- Postgres-main, Redis-main
- Meilisearch, Gotenberg, Browserless

### Custom Systemd Services
- `authelia-config-sync.service` — watches `/opt/authelia/config/`, syncs to Docker volume, restarts Authelia
- `coolify-alias-watcher.service` — re-applies friendly DNS aliases on Coolify redeploy
- `iptables-docker-user.service` — firewall rules after Docker starts
- `iptables-openvpn.service` — OpenVPN NAT rules

### Supporting Scripts
- `/opt/fabrik/scripts/vps_apply_limits.sh` — memory limits + alias application
- `/opt/coolify-alias-watcher/watcher.sh` + `aliases.json`
- `/opt/authelia-config-sync/sync.sh`
- `/opt/backrest/config/config.json` (with retention policies)
- Root crontab: `/opt/backups/pre-backup.sh` at 07:45

## Per-Instance Configuration (configure-vps-instance.sh)

These vary per VPS and must be provided at setup time:
- Hostname
- VPS IP address
- SSH authorized keys
- `/opt/fabrik/.env` (all secrets: Coolify, Cloudflare, GlitchTip, Grafana tokens)
- Backrest B2 credentials
- Authelia TOTP secrets
- Domain names + DNS records
- Let's Encrypt certificates (auto-generated on first deploy)
- OpenVPN keys + certificates

## Dead Stuff to Clean First

Before codifying, these must be removed from the VPS (legacy, replaced, or never configured):

- `/opt/duplicati/` — old backup tool, replaced by Backrest
- `/opt/uptime-kuma/` — old monitoring, replaced by Gatus
- `/opt/apps/` — legacy deploy convention
- `/opt/_archive/` — old archived stuff
- `/opt/namecheap/` — old DNS tool, replaced by site-provisioner
- `/opt/email-reader/` — old project (not deployed)
- `/opt/infrastructure/` — unclear purpose
- `/opt/scripts/` — unclear purpose
- `proxy_sync_scheduled.service` — template never configured (references `/home/your_user/`)
- `vps-backup.service` — disabled
- `coolify-ssh-permissions.service` — disabled
- `.bak` files in monitoring configs (6 files)

## References

- VPS state capture: `docs/infrastructure/vps-captured-state-20260520.txt`
- VPS inventory: `docs/infrastructure/vps-complete-inventory.md`
- Audit prompts: `docs/infrastructure/audit-prompts/`
- Architecture: `docs/reference/architecture.md`
