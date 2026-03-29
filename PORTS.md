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
<!-- Last synced: 2026-03-28 11:42:55 -->

### Project Port Allocations (from project.yaml)

| Port | Project | Type | Path |
|------|---------|------|------|
| 3001 | **calendar-orchestration-engine** | python-api | /opt/calendar-orchestration-engine |
| 8000 | **ComplianceOps** | unknown | /opt/ComplianceOps |
| 8001 | **Reference_Creator** | unknown | /opt/Reference_Creator |
| 8002 | **apidoccreator** | unknown | /opt/apidoccreator |
| 8003 | **apps** | unknown | /opt/apps |
| 8004 | **brand-identiy-creator** | unknown | /opt/brand-identiy-creator |
| 8005 | **candle** | python-api | /opt/candle |
| 8006 | **exam-coach** | unknown | /opt/exam-coach |
| 8007 | **file-worker** | python-api | /opt/file-worker |
| 8008 | **gmailaccountcreator** | unknown | /opt/gmailaccountcreator |
| 8009 | **image-generation** | unknown | /opt/image-generation |
| 8010 | **iterative_image_editor** | python-api | /opt/iterative_image_editor |
| 8011 | **job-agent** | python-api | /opt/job-agent |
| 8012 | **llm_batch_processor** | python-api | /opt/llm_batch_processor |
| 8013 | **marketing-argumant-generator** | unknown | /opt/marketing-argumant-generator |
| 8014 | **namecheap** | unknown | /opt/namecheap |
| 8015 | **proposal-creator** | python-api | /opt/proposal-creator |
| 8016 | **seo** | python-api | /opt/seo |
| 8017 | **supplement-tracker-advisor** | unknown | /opt/supplement-tracker-advisor |
| 8018 | **test-coolify** | python-api | /opt/test-coolify |
| 8019 | **test-final** | python-api | /opt/test-final |
| 8020 | **test-session-check** | python-api | /opt/test-session-check |
| 8021 | **test-zero-refs** | python-api | /opt/test-zero-refs |
| 8022 | **trade-intelligence** | python-api | /opt/trade-intelligence |
| 8023 | **trading-core** | python-api | /opt/trading-core |
| 8024 | **transcriber** | unknown | /opt/transcriber |
| 8025 | **triggered-content-orchestration** | python-api | /opt/triggered-content-orchestration |
| 8026 | **ugc** | unknown | /opt/ugc |
| 8027 | **web-scraper** | python-api | /opt/web-scraper |
| 8028 | **test-project-2024** | python-api | /opt/test-project-2024 |
| 8029 | **youtube** | python-api | /opt/youtube |
| 18011 | **captcha** | python-api | /opt/captcha |
| 18012 | **translator** | python-api | /opt/translator |
| 18013 | **proxy** | automation | /opt/proxy |
| 18014 | **dns-manager** | python-api | /opt/dns-manager |
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
