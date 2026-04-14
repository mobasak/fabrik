# Fabrik Port Allocations

**Last Updated:** 2026-02-28

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
| 19999 | Netdata monitoring | VPS only |

---

## Current Allocations

### Infrastructure Services (VPS)

| Port | Service | Project | URL |
|------|---------|---------|-----|
| 8000 | Coolify | coolify | https://coolify.vps1.ocoron.com |
| 3001 | Uptime Kuma | uptime-kuma | https://status.vps1.ocoron.com |
| 8200 | Duplicati | duplicati | https://backup.vps1.ocoron.com |
| 19999 | Netdata | netdata | https://netdata.vps1.ocoron.com |
| 3000 | browserless | specs/infrastructure/browserless.yaml | https://browser.vps1.ocoron.com |
| 3003 | gotenberg | specs/infrastructure/gotenberg.yaml | https://pdf.vps1.ocoron.com |
| 9000/9001 | minio | specs/infrastructure/minio.yaml | https://s3.vps1.ocoron.com |
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
| 8050 | fabrik-api | /opt/fabrik-api | FastAPI bridge — native VPS host process, binds `127.0.0.1` only |
| 3004 | fabrik-control-plane | /opt/fabrik-control-plane | Next.js 14 chat UI — Coolify-managed container |

### Fabrik Microservices (VPS Host Ports)

| Host Port | Service | Project | URL |
|-----------|---------|---------|-----|
| 18011 | Captcha Solver | /opt/captcha | https://captcha.vps1.ocoron.com |
| 18012 | Translator API | /opt/translator | https://translator.vps1.ocoron.com |
| 18013 | Proxy Manager | /opt/proxy | https://proxy.vps1.ocoron.com |
| 18014 | DNS Manager | /opt/dns-manager | https://dns.vps1.ocoron.com |
| 18015 | File API | /opt/file-api | https://files-api.vps1.ocoron.com |
| 18016 | Image Broker | /opt/image-broker | https://images.vps1.ocoron.com |
| 18017 | Email Gateway | /opt/emailgateway | https://email.vps1.ocoron.com |
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
<!-- Last synced: 2026-04-15 00:00:49 -->

### ⚠️ Port Conflicts Detected

| Port | Conflicting Projects |
|------|---------------------|
| **18014** | dns-manager, site-provisioner |

### Project Port Allocations (from project.yaml)

| Port | Project | Type | Path |
|------|---------|------|------|
| 3001 | **calendar-orchestration-engine** | python-api | /opt/calendar-orchestration-engine |
| 8002 | **apidoccreator** | python-api | /opt/apidoccreator |
| 8003 | **apps** | python-api | /opt/apps |
| 8004 | **brand-identiy-creator** | python-api | /opt/brand-identiy-creator |
| 8005 | **candle** | python-api | /opt/candle |
| 8006 | **exam-coach** | python-api | /opt/exam-coach |
| 8007 | **file-worker** | file-worker | /opt/file-worker |
| 8008 | **gmailaccountcreator** | python-api | /opt/gmailaccountcreator |
| 8009 | **image-generation** | python-api | /opt/image-generation |
| 8010 | **iterative_image_editor** | python-api | /opt/iterative_image_editor |
| 8011 | **job-agent** | python-api | /opt/job-agent |
| 8012 | **llm_batch_processor** | python-api | /opt/llm_batch_processor |
| 8013 | **marketing-argumant-generator** | python-api | /opt/marketing-argumant-generator |
| 8014 | **namecheap** | python-api | /opt/namecheap |
| 8015 | **proposal-creator** | python-api | /opt/proposal-creator |
| 8016 | **seo** | python-api | /opt/seo |
| 8017 | **supplement-tracker-advisor** | python-api | /opt/supplement-tracker-advisor |
| 8018 | **Reference_Creator** | python-api | /opt/Reference_Creator |
| 8022 | **trade-intelligence** | python-api | /opt/trade-intelligence |
| 8023 | **trading-core** | python-api | /opt/trading-core |
| 8024 | **transcriber** | python-api | /opt/transcriber |
| 8025 | **triggered-content-orchestration** | python-api | /opt/triggered-content-orchestration |
| 8026 | **ugc** | python-api | /opt/ugc |
| 8027 | **web-scraper** | python-api | /opt/web-scraper |
| 8029 | **youtube** | python-api | /opt/youtube |
| 8033 | **ComplianceOps** | python-api | /opt/ComplianceOps |
| 18011 | **captcha** | python-api | /opt/captcha |
| 18012 | **translator** | python-api | /opt/translator |
| 18013 | **proxy** | automation | /opt/proxy |
| 18014 ⚠️ | **dns-manager** | python-api | /opt/dns-manager |
| 18014 ⚠️ | **site-provisioner** | python-api | /opt/site-provisioner |
| 18015 | **file-api** | node-api | /opt/file-api |
| 18016 | **image-broker** | python-api | /opt/image-broker |
| 18017 | **emailgateway** | node-api | /opt/emailgateway |
| 18018 | **email-reader** | python-api | /opt/email-reader |

<!-- AUTO-GENERATED:PORTS:END -->

## Notes

- **VPS services use Traefik reverse proxy** — External access is via HTTPS (port 443)
- **Internal container ports** — May differ from external ports (Traefik handles routing)
- **WSL ports** — Accessible directly via `localhost:<port>`
- **Docker networks** — Services communicate via container names, not ports

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
