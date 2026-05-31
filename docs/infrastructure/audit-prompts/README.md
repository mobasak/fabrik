# VPS Audit Prompts

**Last Updated:** 2026-05-31 (banner refreshed for post-Coolify-removal + 3-host mesh)

> **⚠️ Partial-rewrite needed.** All 8 audit prompts in this directory were authored 2026-05-19 during the Coolify era. They reference Coolify dashboards, UUID-suffix container names, and `coolify` Docker network. As of 2026-05-30:
>
> - Coolify is **gone** — replaced with SSH + Docker Compose (`/opt/<svc>/compose.yaml`)
> - Container names are **stable** (no UUID suffix) — `traefik`, `postgres-main`, `grafana`, etc.
> - Network renamed `coolify` → `fabrik` on 2026-05-31
> - Fleet grew vps1-only → **vps1 + vps2 + vps3** (Wireguard mesh)
>
> A targeted `coolify` → `fabrik` network rename has been swept across the 8 files. Other Coolify-isms (UI references, UUID lookups, `/data/coolify/` paths) remain — apply mental substitutions as you read:
>
> | Old (Coolify-era) | New (current) |
> | :--- | :--- |
> | "Check the Coolify dashboard" | `sudo docker compose -f /opt/<svc>/compose.yaml ps` |
> | "Edit env in Coolify UI" | edit `/opt/<svc>/.env` and `cd /opt/<svc> && sudo docker compose up -d` |
> | `<svc>-<24chars>-<timestamp>` container name | just `<svc>` (stable via `container_name:`) |
> | "Coolify v4" | "SSH + Docker Compose (Coolify removed 2026-05-30)" |
> | `/data/coolify/applications/<uuid>/` | `/opt/<svc>/` |
> | `/data/coolify/services/<uuid>/` | `/opt/<svc>/` |
> | "coolify network" | `fabrik` network |

Structured prompts for comprehensive VPS health auditing. Each file is a self-contained prompt designed to be pasted into an AI assistant (Claude Code, ChatGPT, etc.) alongside the diagnostic output it requests.

## Usage

1. Pick the audit you need
2. SSH to vps1 (or a spoke) and run the listed commands
3. Paste the prompt + command output into your AI assistant
4. Follow the remediation roadmap

## Prompts

| File | Scope | When to use | Rewrite priority |
| :--- | :--- | :--- | :--- |
| [01-full-system-audit.md](01-full-system-audit.md) | Complete 8-domain VPS health check | Monthly, after incidents, before going live | medium |
| [02-container-health.md](02-container-health.md) | Docker container diagnostics | After deploys, when services are slow/crashing | high (12 mentions) |
| [03-security-hardening.md](03-security-hardening.md) | Firewall, auth, TLS, attack surface | Before production launch, quarterly review | low |
| [04-performance-bottleneck.md](04-performance-bottleneck.md) | CPU, memory, disk I/O, network deep-dive | When VPS is slow, load is high, or users report latency | low |
| [05-observability-pipeline.md](05-observability-pipeline.md) | Prometheus, Loki, Grafana, GlitchTip, Gatus | When dashboards are empty, alerts aren't firing, logs are missing | low |
| [06-backup-disaster-recovery.md](06-backup-disaster-recovery.md) | Backrest, B2, volume integrity, recovery testing | Monthly, before major changes, after data incidents | medium (Backrest is now 0 plans; B2 empty) |
| [07-pre-production-checklist.md](07-pre-production-checklist.md) | Go-live readiness for a new service deployment | Before first real users hit the VPS | low |
| [08-hardening-remediation.md](08-hardening-remediation.md) | Post-audit hardening — execute fixes from findings | After running audits 01-06, to make VPS production-grade | low |

## Multi-host notes (2026-05-31)

When auditing the fleet, scope each audit per host. SSH aliases (already in `~/.ssh/config`):

- `ssh vps` → vps1.ocoron.com (hub, LA, 11.6 GB / 6 cores)
- `ssh vps2` → 96.9.214.128 (Coventry UK spoke, 8 GB / 4 cores)
- `ssh vps3` → 104.128.190.151 (Coventry UK spoke, 8 GB / 4 cores)

For fleet-wide observability checks (audit 05), run them against vps1 since Prometheus + Loki on vps1 have data from all hosts via mesh.

## Lessons Learned (2026-05-19 + 2026-05-31 + 2026-06-01)

1. **All scripts must use `sudo`** for: docker, ufw, iptables, dmesg, journalctl, sshd, aa-status, last, and any file under `/var/lib/docker/volumes/`. SSH user is not root and not in the docker group.
2. **Scripts that read `/opt/fabrik/.env`** must account for the fact that `.env` lives on the WSL dev machine, not the VPS. Tokens for Grafana/GlitchTip/etc. need to be passed as env vars or read from VPS-local paths.
3. **Time-series commands** (`vmstat 1 5`, `iostat -x 1 3`) add 3-15 s per script. Acceptable for parallel execution but not for sequential.
4. **`ip -s link`** without a specific interface dumps all Docker bridges + wg0. Always detect primary interface first.
5. **Container names** are now stable (post-2026-05-30) — use `--filter name=<exact-name>` directly. Old prompts that say "use `name=<pattern>`" because Coolify UUID-suffixed names can use exact-match now.
6. **Mesh-bound services** on vps1 (postgres-main, redis-main, glitchtip-web, authelia, loki) listen on `10.99.0.1:<port>` in addition to internal Docker DNS. Audit scripts checking external reachability should test `0.0.0.0:<port>` (should fail — public should not reach these) AND `10.99.0.1:<port>` (should succeed from other hosts on mesh).
7. **Verify UFW with all 3 probes — Lesson 68 (2026-06-01)**: a package in `rc` state ("removed but config files remain") returns empty from `dpkg -l ufw \| awk '/^ii/'` while `systemctl is-active ufw` returns "active" — and the binary is missing. Single-probe checks of "is UFW installed and enforcing?" mislead. Audit scripts must run all three: `dpkg -l ufw \| awk '/^(ii|rc)/'` (distinguishes installed from removed-with-config from never-installed), `command -v ufw` (binary present), `sudo ufw status` (rules + default policy). Pre-W1 vps2 + vps3 had `rc`-state UFW for weeks; only DOCKER-USER was actually enforcing. Captured in `docs/LESSONS_LEARNT.md § Lesson 68`.

## Stack Context (paste into any prompt if needed)

```text
Fleet: 3 hosts, Wireguard mesh 10.99.0.0/24 (UDP 51820, MTU 1420)
  vps1 (10.99.0.1): Ubuntu 24.04 LTS, 6 vCores, 11.6 GB RAM, 108 GB disk
  vps2 (10.99.0.2): Ubuntu 24.04 LTS, 4 vCores, 8 GB RAM, 60 GB NVMe
  vps3 (10.99.0.3): Ubuntu 24.04 LTS, 4 vCores, 8 GB RAM, 60 GB NVMe

Orchestration: SSH + Docker Compose (no Coolify; removed 2026-05-30)
                Traefik v2.11 on each host (per-host TLS termination)
                Authelia v4 on vps1 (forward-auth for *.vps1.ocoron.com;
                  cross-host pattern: 10.99.0.1:9091 via spoke Traefik
                  authelia-vps1@file middleware)

Data (all on vps1, mesh-exposed):
  PostgreSQL 16 (postgres-main) on 10.99.0.1:5432
  Redis 7 (redis-main) on 10.99.0.1:6379
  Meilisearch (per-service index) on http://meilisearch:7700 (vps1 only)

Observability (centralized on vps1):
  Prometheus + Alertmanager + Grafana + Loki + Promtail + Gatus + GlitchTip
  Loki accepts pushes at 10.99.0.1:3100 (mesh); spokes' promtail uses it
  Prometheus scrapes 20 targets (14 vps1 + 6 spoke) — every series has
    host label (vps1/vps2/vps3) for filtering

Backups: Backrest → Backblaze B2 (CURRENTLY 0 PLANS, intentional;
  see docs/operations/disaster-recovery.md)

Docker:
  vps1: ~28 containers
  vps2 + vps3: 4 containers each (traefik + node-exporter + cadvisor + promtail)
  Network: fabrik (renamed from coolify on 2026-05-31)
  daemon.json: log tag enabled on vps1; PENDING on spokes

Compose layout: /opt/<svc>/compose.yaml on every host
.env files: /opt/<svc>/.env on every host (the SSH deployer's inject_env()
  writes here; never edit in a "dashboard")
```
