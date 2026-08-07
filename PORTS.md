# Fabrik Port Allocations

**Last Updated:** 2026-06-16

This document tracks port allocations for all Fabrik services to prevent conflicts.

---

## Port Ranges

| Range | Purpose | Environment |
|-------|---------|-------------|
| 3000-3099 | Frontend apps (Node.js) | WSL & VPS |
| 5000-5099 | Python services (misc) | WSL only |
| 8000-8099 | Python APIs (FastAPI) | WSL & VPS |
| 8100-8199 | Workers & background services | WSL & VPS |
| 8200-8299 | Management tools | VPS only |

---

## Current Allocations

### Infrastructure Services (VPS)

| Port | Service | Project | URL |
|------|---------|---------|-----|
| ~~8000~~ | ~~Coolify~~ | — | **retired 2026-05-30 — not deployed** (decommissioned; port 8000 now free. `coolify` survives only as a Docker-network name — see Notes) |
| 3001 | Gatus | gatus | https://status.vps1.ocoron.com |
| 9898 | Backrest | backrest | https://backup.vps1.ocoron.com (Duplicati on 8200 retired 2026-04-17) |
| ~~19999~~ | ~~Netdata~~ | — | **retired 2026-05-30 — not deployed** (removed; port 19999 now free) |
| 3000 | browserless | specs/infrastructure/browserless.yaml | https://browser.vps1.ocoron.com |
| 3003 | gotenberg | specs/infrastructure/gotenberg.yaml | https://pdf.vps1.ocoron.com |
| 9000/9001 | minio | specs/infrastructure/minio.yaml | [reserved — not yet deployed] |
| 8005 | apprise | specs/infrastructure/apprise.yaml | https://notify.vps1.ocoron.com |
| 7700 | meilisearch | specs/infrastructure/meilisearch.yaml | https://search.vps1.ocoron.com |
| 3100 | loki | specs/infrastructure/monitoring-stack.yaml | internal only |
| 9090 | prometheus | specs/infrastructure/monitoring-stack.yaml | internal only |
| 9100 | node-exporter | specs/infrastructure/monitoring-stack.yaml | internal only |
| 8080 | cadvisor | specs/infrastructure/monitoring-stack.yaml | internal only |
| 3002 | grafana | specs/infrastructure/monitoring-stack.yaml | https://monitor.vps1.ocoron.com |
| 5678 | n8n | specs/infrastructure/n8n.yaml | https://auto.vps1.ocoron.com |

### Control Plane Services (VPS)

| Port | Service | Project | Notes |
|------|---------|---------|-------|
| 8017 | **vps-sysadmin-bot health** | `/opt/fabrik/scripts/sysadmin/bot.py` | systemd service on vps1 host; **binds `127.0.0.1:8017` only** since W5 of fleet-hardening plan (2026-06-01). Distinct socket from the `:8017` container-internal allocation under "Python APIs" below — host-loopback and container-internal do not collide at the OS level. Override via `SYSADMIN_HEALTH_HOST=<ip>` in `/opt/fabrik/.env.sysadmin`. |
| 8050 | fabrik-api | /opt/fabrik-api | FastAPI bridge — native VPS host process, binds `127.0.0.1` only |
| ~~3004~~ | ~~fabrik-control-plane~~ | /opt/fabrik-control-plane | **retired 2026-05-30 — not deployed** (Next.js 14 chat UI; no live container in the fleet. Port 3004 now free) |
| 8201 | **aro-wake** (per-host push-trigger AI endpoint) | `/opt/fabrik/scripts/aro-wake/` | Trio plan Phase 3 (2026-06-04). systemd service on every fleet host; **binds `0.0.0.0:8201`** (changed 2026-06-05 batch-6 from mesh-only because Alertmanager's docker container can't reach the host's wg0 IP from its network namespace; verified via `docker exec alertmanager wget http://10.99.0.1:8201` → timeout). Endpoint: `POST /wake` for peer consult (LIVE) / Alertmanager webhook (Phase 4, LIVE on vps1) / manual ops curl. Reaches Claude via the same calling convention as `bot.py::_run_claude`. Allocated from the 8200-8299 "Management tools" range (Duplicati 8200 retired 2026-04-17). **Access control via UFW + iptables**: default-deny incoming on UFW (allow-list is 22/80/443/1194/51820 — 8201 not listed) blocks public ingress; explicit allow rules `from 10.0.0.0/8 to any port 8201 proto tcp` (docker bridge for Alertmanager + other containers) and `from 10.99.0.0/24 to any port 8201 proto tcp` (wg0 peer consults) permit the legitimate callers without exposing publicly. Reachability matrix verified live on vps1 2026-06-05: container on `fabrik` net via `10.0.1.1:8201` ✓; host loopback / wg0 IP ✓; peer over wg0 ✓; **public internet timeout (UFW deny) ✓**. Operator probe from host: `curl http://10.99.0.<N>:8201/health`. Alertmanager probe: `docker exec alertmanager wget -qO- http://10.0.1.1:8201/health`. **Prometheus exposition sub-allocation on same port** (added 2026-06-06): `GET /metrics` returns 8 `aro_wake_*` SLI families (counters: requests_total{source,status}, cost_usd_total{source}, dedup_drops_total, hop_limit_exceeded_total, forward_suppressed_total{target_host,reason}, storm_breaker_trips_total{target_host}; gauges: pending_queue_size, active_sessions). Scraped by Prometheus on `fabrik` net (renamed from `coolify` 2026-05-31) across the full trio fleet: `http://10.0.1.1:8201/metrics` (vps1, docker-bridge gateway), `http://10.99.0.2:8201/metrics` (vps2, wg0), `http://10.99.0.3:8201/metrics` (vps3, wg0). Cross-mesh container→host NAT verified live 2026-06-06 — Prometheus container's outbound to spoke wg0 IPs is SNAT'd to 10.99.0.1 by docker MASQUERADE, which the spokes' `from 10.99.0.0/24 to any port 8201 proto tcp` UFW rule already permits. |

### Fabrik Microservices (VPS Host Ports)

| Host Port | Service | Project | URL |
|-----------|---------|---------|-----|
| ~~18011~~ | ~~Captcha Solver~~ | /opt/captcha | **retired — fully removed 2026-08-07** (`fabrik destroy` ran: DNS + Gatus + GlitchTip + watchdog-governance torn down; spec deleted. Port 18011 free) |
| ~~18012~~ | ~~Translator API~~ | /opt/translator | **retired — not currently deployed** (no live container/router; `specs/services/translator.yaml` persists but nothing deployed. Port 18012 free) |
| ~~18013~~ | ~~Proxy Manager~~ | /opt/proxy | **retired — not currently deployed** (no live container/router. Port 18013 free) |
| ~~18014~~ | ~~DNS Manager~~ | /opt/dns-manager | **retired — not currently deployed** (no live container/router). **Port 18014 reallocated to site-provisioner** — see auto-generated table below |
| ~~18015~~ | ~~File API~~ | /opt/file-api | **retired — not currently deployed** (no live container/router; `files-api.vps1.ocoron.com` NXDOMAIN. Port 18015 free) |
| ~~18017~~ | ~~Email Gateway~~ | /opt/emailgateway | **retired — not currently deployed** (no live container/router. Port 18017 free) |
| 18018 | Email Reader | /opt/email-reader | — |

### Development Services (WSL Only)

| Port | Service | Project | Notes |
|------|---------|---------|-------|
| 5050 | Email Reader | /opt/email-reader | Gmail/M365 integration |
| 8000 | Local dev server | varies | Default FastAPI port |

---

## Port Conflict Resolution

If you encounter a port conflict:

1. Check this file for existing allocations
2. Choose the next available port in the appropriate range
3. Update this file with the new allocation
4. Update the service's `.env` and `compose.yaml`

---


<!-- AUTO-GENERATED:PORTS:START -->
<!-- Last synced: 2026-08-07 14:44:33 -->

### Project Port Allocations (from project.yaml)

| Port | Project | Type | Path |
|------|---------|------|------|
| 3000 | **test-saas-platform** | saas-skeleton | /opt/test-saas-platform |
| 3001 | **calendar-orchestration-engine** | node-api | /opt/calendar-orchestration-engine |
| 3002 | **test-saas-scaffold** | saas-skeleton | /opt/test-saas-scaffold |
| 3003 | **transdoc** | saas-skeleton | /opt/transdoc |
| 3004 | **tojlo-mail** | saas | /opt/tojlo-mail |
| 3005 | **compliance-ops** | saas-skeleton | /opt/compliance-ops |
| 3006 | **exam-coach** | saas-skeleton | /opt/exam-coach |
| 3007 | **web-ecommerce-factory** | saas-skeleton | /opt/web-ecommerce-factory |
| 3008 | **ai-model-catalog** | saas-skeleton | /opt/ai-model-catalog |
| 8000 | **tryton-crm** | python-api | /opt/tryton-crm |
| 8001 | **longephedia-vault** | python-api | /opt/longephedia-vault |
| 8002 | **fabrik-claim-validator** | python-api | /opt/fabrik-claim-validator |
| 8003 | **obsidian-agents** | desktop-app | /opt/obsidian-agents |
| 8004 | **brand-identiy-creator** | python-api | /opt/brand-identiy-creator |
| 8005 | **candle** | python-api | /opt/candle |
| 8006 | **gmail-account-creator** | file-worker | /opt/gmail-account-creator |
| 8007 | **whatsapp-agent** | python-api | /opt/whatsapp-agent |
| 8008 | **supplement-tracker-advisor** | mobile-app | /opt/supplement-tracker-advisor |
| 8009 | **image-generation** | python-api | /opt/image-generation |
| 8010 | **iterative_image_editor** | python-api | /opt/iterative_image_editor |
| 8011 | **job-agent** | python-api | /opt/job-agent |
| 8012 | **llm_batch_processor** | python-api | /opt/llm_batch_processor |
| 8013 | **marketing-argumant-generator** | python-api | /opt/marketing-argumant-generator |
| 8014 | **rnfinal** | mobile-app | /opt/rnfinal |
| 8015 | **proposal-creator** | python-api | /opt/proposal-creator |
| 8016 | **seo** | python-api | /opt/seo |
| 8017 | **session-recall** | python-api | /opt/session-recall |
| 8018 | **Reference_Creator** | python-api | /opt/Reference_Creator |
| 8022 | **trade-intelligence** | saas-skeleton | /opt/trade-intelligence |
| 8023 | **trading-core** | python-api | /opt/trading-core |
| 8025 | **triggered-content-orchestration** | python-api | /opt/triggered-content-orchestration |
| 8027 | **web-scraper** | python-api | /opt/web-scraper |
| 8029 | **youtube** | file-worker | /opt/youtube |
| 8031 | **youtube** | file-worker | /opt/youtube |
| 8032 | **fabrik-citation-verifier** | python-api | /opt/fabrik-citation-verifier |
| 8302 | **apidoccreator** | python-api | /opt/apidoccreator |
| 18013 | **proxy** | python-api | /opt/proxy |
| 18014 | **site-provisioner** | python-api | /opt/site-provisioner |
| 18018 | **email-reader** | python-api | /opt/email-reader |

<!-- AUTO-GENERATED:PORTS:END -->

## Notes

- **VPS services use Traefik reverse proxy** — External access is via HTTPS (port 443)
- **Internal container ports** — May differ from external ports (Traefik handles routing)
- **WSL ports** — Accessible directly via `localhost:<port>`
- **Docker networks** — Services communicate via container names, not ports
- **Legacy `coolify` network name** — Coolify (the platform) was decommissioned 2026-05-30, but its Docker network name `coolify` survives as the shared bridge (renamed to `fabrik` 2026-05-31 in some contexts; references to the `coolify` *network* are not the dead service)
- **Auto-generated block** — The `AUTO-GENERATED:PORTS` table is synced from on-disk `project.yaml` scaffolds (dev intent), not live deployment state. Entries there (e.g. `captcha`/`proxy`/`image-broker`) reflect scaffolded projects and may not be deployed; the curated tables above are the authoritative deployment registry

---

## Adding a New Service

1. Choose port from appropriate range
2. Add entry to this file
3. Configure in service's `.env`:
   ```
   PORT=8xxx
   ```
4. Configure in `compose.yaml`:
   ```yaml
   ports:
     - "8xxx:8xxx"
   ```
5. Add Traefik labels for external access (VPS only)
