# VPS Services: Coolify vs Standalone Analysis

**Date:** 2026-04-18 (validated via SSH)
**Total Containers:** 39
**Coolify-Managed:** 26 (67%)
**Standalone:** 13 (33%)

**Migration Status:** ✅ **ALL INFRASTRUCTURE MIGRATIONS COMPLETE (2026-04-17)**

## Services NOT in Coolify (Standalone - By Design)

### 1. Coolify Core (5 services - DO NOT MIGRATE)

- **coolify** - Main Coolify application
- **coolify-db** - Coolify PostgreSQL database
- **coolify-redis** - Coolify Redis cache
- **coolify-realtime** - Real-time communications
- **coolify-sentinel** - Sentinel service

**Status:** Self-managed by Coolify, not via Coolify API
**Action:** Keep standalone by design

---

### 2. Core Infrastructure (2 services - DO NOT MIGRATE)

#### redis-main

**Container:** `redis-main`
**Image:** `redis:7-alpine`
**Used by:** Multiple services for caching

**Status:** Standalone (DO NOT MIGRATE)
**Reasons:** Shared cache infrastructure, multiple services depend on it
**Action:** Keep as standalone container

#### traefik

**Container:** `traefik`
**Image:** `traefik:v2.11`
**Purpose:** Reverse proxy for all services

**Status:** Standalone, managed by Coolify (DO NOT MIGRATE)
**Reasons:** Core reverse proxy, Coolify manages it directly
**Action:** Keep standalone by design

---

### 3. Authentication & Notifications (✅ MIGRATED TO COOLIFY - 2026-04-17)

#### authelia

**Status:** ✅ **COOLIFY-MANAGED (migrated 2026-04-17)**
**URL:** auth.vps1.ocoron.com
**Protects:** Coolify, n8n, Grafana, Netdata, Backrest, Apprise
**Action:** No action needed - migration complete

#### apprise

**Status:** ✅ **COOLIFY-MANAGED (migrated 2026-04-17)**
**URL:** notify.vps1.ocoron.com
**Used by:** Gatus, n8n, Alertmanager
**Action:** No action needed - migration complete

---

### 4. Utilities (✅ MIGRATED TO COOLIFY - 2026-04-17)

#### n8n

**Status:** ✅ **COOLIFY-MANAGED (migrated 2026-04-17)**
**URL:** auto.vps1.ocoron.com
**Purpose:** Workflow automation
**Action:** No action needed - migration complete

#### netdata

**Status:** ✅ **COOLIFY-MANAGED (migrated 2026-04-17)**
**URL:** netdata.vps1.ocoron.com
**Purpose:** Real-time server metrics
**Action:** No action needed - migration complete

#### backrest (replaced duplicati)

**Status:** ✅ **COOLIFY-MANAGED (migrated 2026-04-17)**
**URL:** backup.vps1.ocoron.com
**Purpose:** VPS backups to Backblaze B2
**Note:** Duplicati removed, replaced by Backrest
**Action:** No action needed - migration complete

---

### 5. WordPress Sites (1 site - Standalone by Design)

#### ocoron.com

**Containers:** 5 (wordpress, nginx, db, redis, backup)
**Location:** `/opt/ocoron.com/compose.yaml`

**Status:** Standalone (DO NOT MIGRATE)
**Reasons:** Production site, high risk, current setup works fine
**Action:** Keep standalone by design

---

## Services IN Coolify (Already Managed)

### Monitoring Stack (✅ All Migrated 2026-04-17)

- prometheus
- grafana
- alertmanager
- loki
- promtail
- cadvisor
- node-exporter
- gatus
- glitchtip-web
- glitchtip-worker

### Core Infrastructure (✅ Migrated 2026-04-17)

- postgres-main

### Authentication & Notifications (✅ Migrated 2026-04-17)

- authelia
- apprise

### Utilities (✅ Migrated 2026-04-17)

- n8n
- netdata
- backrest (replaced duplicati)

### Fabrik Microservices (All in Coolify)

- captcha
- translator
- proxy
- site-provisioner / DNS Manager
- file-api
- file-worker
- image-broker
- emailgateway

### Infrastructure Services (In Coolify)

- meilisearch (search.vps1.ocoron.com)
- browserless (browser.vps1.ocoron.com)
- gotenberg (pdf.vps1.ocoron.com)

---

## Summary & Recommendations (Updated 2026-04-18)

### ✅ MIGRATED TO COOLIFY (2026-04-17)

**All infrastructure services successfully migrated:**
- Monitoring Stack (10 services): prometheus, grafana, alertmanager, loki, promtail, cadvisor, node-exporter, gatus, glitchtip-web, glitchtip-worker
- Core Infrastructure (1 service): postgres-main
- Authentication & Notifications (2 services): authelia, apprise
- Utilities (3 services): n8n, netdata, backrest (replaced duplicati)
- Infrastructure Services (3 services): meilisearch, gotenberg, browserless

**Total migrated:** 19 services
**Migration success rate:** 100%
**Downtime:** Zero (rolling migrations)

### ❌ DO NOT MIGRATE (By Design)

- Coolify Core (5 services): coolify, coolify-db, coolify-redis, coolify-realtime, coolify-sentinel (self-managed)
- Core Infrastructure (2 services): redis-main, traefik (shared infrastructure)
- WordPress Sites (1 site): ocoron.com (production site, high risk)

### ✅ ALREADY IN COOLIFY

- Fabrik Microservices (8 services): captcha, translator, proxy, file-api, file-worker, image-broker, emailgateway, site-provisioner

### Final Recommendation

**Current state is production-ready:**
- 67% of containers are Coolify-managed (26/39)
- All critical infrastructure services migrated to Coolify
- Zero downtime during migrations
- Standalone services remain by design (Coolify core, shared infrastructure, production WordPress)

**No further migrations needed.** Current architecture provides:
- Centralized management for all infrastructure services
- Clear separation of concerns
- Production stability (standalone WordPress, shared databases)
- Easy troubleshooting and monitoring

---

## Status Update — 2026-05-07

Architecture remains as documented above. Key changes since April 18:

- **40 containers** running (was 39 at migration time)
- **Security hardened** 2026-05-06: port 8000 blocked, API keys added to proxy/captcha/image-broker/translator, `.dockerignore` added to all projects, resource limits set on 7 Fabrik apps
- **Observability** fully operational: Grafana, Prometheus, Loki, Gatus, GlitchTip, Netdata all running
- **Fabrik PaaS** deployed at `/opt/fabrik` — `fabrik apply`, `fabrik redeploy`, `fabrik destroy` workflow operational
- Current live state: see `docs/infrastructure/vps-status.md` and `docs/infrastructure/vps-complete-inventory.md`
