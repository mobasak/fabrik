# Gatus Monitoring Endpoints Inventory

> **📌 ARCHIVED 2026-06-06.** Historical document preserved as-is for context. Frozen at the time of original ship. For current fleet state see [`vps-status.md`](../vps-status.md), [`vps-complete-inventory.md`](../vps-complete-inventory.md), and [`vps-fleet-architecture.md`](../vps-fleet-architecture.md). Do NOT update the content below — that would defeat the archive.

**Date:** 2026-04-18 (validated via SSH)
**Location:** `/opt/monitoring/configs/gatus/`
**Total Endpoints:** 17 YAML files (duplicati removed)

---

## Overview

Gatus monitors all critical services across 6 categories. Each category has dedicated YAML files that Gatus auto-discovers.

**Categories:**
- `apps/` - Application services (11 files)
- `core/` - Core infrastructure (1 file)
- `data/` - Database services (1 file)
- `external/` - Public-facing endpoints (1 file)
- `observability/` - Monitoring stack (1 file)
- `infra/` - Infrastructure (empty)

---

## Apps Category (11 files)

### apps/alertmanager.yaml
- **alertmanager** - `http://alertmanager:9093/-/healthy`

### apps/apprise.yaml
- **apprise** - `http://apprise:8000/`

### apps/backrest.yaml
- **backrest** - `tcp://backrest-l48000k44wc4gk8os88s8k0c:9898`

### apps/dns-manager.yaml
- **dns-manager** - `http://site-provisioner-qokoksogwsk0c04gcs4swwgs-223724136560:8001/health`

### apps/fabrik-microservices.yaml (7 endpoints)
- **captcha** - `http://captcha-j8gg4ggskkossc4gkwowk4os-140246184500:8000/`
- **translator** - `http://translator-kgws0s4cscsosw8gg848cwgw-140305573177:8000/health`
- **proxy-service** - `http://proxy-v0cscowwsgkk88c4ckckgw0g-140350084065:8000/health`
- **dns-manager** - `http://site-provisioner-qokoksogwsk0c04gcs4swwgs-223724136560:8001/health` (duplicate)
- **file-api** - `http://file-api-bsswwg4kg480c000gksw004k-140449896537:3000/health`
- **image-broker** - `http://image-broker-zo4ggs4g880skwkocwwkscgk-140330450088:8000/health`
- **email-gateway** - `http://emailgateway-w4oocckkwko8kowggsw8sogc-140328040913:3000/health`

### apps/glitchtip.yaml
- **glitchtip-web** - `http://glitchtip-web-z00kkck8c8cwo800kk440csk:8000/api/0/`

### apps/grafana.yaml
- **grafana** - `http://grafana:3000/api/health`

### apps/loki.yaml
- **loki** - `http://loki:3100/ready`

### apps/n8n.yaml
- **n8n** - `http://n8n:5678/healthz`

### apps/netdata.yaml
- **netdata** - `http://netdata:19999/api/v1/info`

### apps/prometheus.yaml
- **prometheus** - `http://prometheus:9090/-/healthy`

### apps/services.yaml (3 endpoints)
- **gotenberg** - `tcp://e04k4sco44ow04ccc0o0k00k-151256201601:3000`
- **browserless** - `tcp://vckgs8c00o40o884k48cgow8-150756746544:3000`
- **glitchtip** - `tcp://glitchtip-web-z00kkck8c8cwo800kk440csk:8000`

---

## Core Category (1 file)

### core/infra.yaml (5 endpoints)
- **traefik** - `tcp://traefik:80`
- **authelia** - `http://authelia:9091/api/health`
- **coolify** - `http://coolify:8000/api/health`
- **n8n** - `http://n8n:5678/healthz` (duplicate)
- **apprise** - `tcp://apprise:8000` (duplicate)

---

## Data Category (1 file)

### data/databases.yaml (3 endpoints)
- **postgres-main** - `tcp://postgres-main:5432`
- **redis-main** - `tcp://redis-main:6379`
- **meilisearch** - `tcp://bs0wo48k4gwo440gcowscoc8-150802066640:7700`

---

## External Category (1 file)

### external/public.yaml (5 endpoints)
- **coolify-public** - `https://coolify.vps1.ocoron.com`
- **status-page** - `https://status.vps1.ocoron.com`
- **glitchtip-public** - `https://errors.vps1.ocoron.com`
- **search-public** - `https://search.vps1.ocoron.com`
- **monitor-public** - `https://monitor.vps1.ocoron.com`

---

## Observability Category (1 file)

### observability/stack.yaml (5 endpoints)
- **grafana** - `http://grafana:3000/api/health`
- **prometheus** - `http://prometheus:9090/-/healthy`
- **alertmanager** - `http://alertmanager:9093/-/healthy`
- **loki** - `http://loki:3100/ready`
- **netdata** - `http://netdata:19999/api/v1/info`

---

## Summary

**Total Unique Endpoints:** ~33 (some duplicates across files)

**By Protocol:**
- HTTP health checks: ~23
- TCP port checks: ~10

**By Category:**
- Apps: 22 endpoints (duplicati removed)
- Core: 5 endpoints
- Data: 3 endpoints
- External: 5 endpoints
- Observability: 5 endpoints

**Status:** ✅ All critical services monitored (duplicati replaced by backrest)

---

## Access

**Gatus Dashboard:** https://status.vps1.ocoron.com

**Alert Routing:**
```
Gatus (endpoint failure) → Apprise (http://apprise:8000/notify/alerts) → Telegram
```

**Configuration Location (VPS):**
```
/opt/monitoring/configs/gatus/
├── _base.yaml (alerting, connectivity, UI settings)
├── apps/ (11 files)
├── core/ (1 file)
├── data/ (1 file)
├── external/ (1 file)
├── infra/ (empty)
└── observability/ (1 file)
```

**Auto-Discovery:** Gatus automatically loads all YAML files in subdirectories on restart.
