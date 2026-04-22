# Coolify Management Status Report

**Date:** 2026-04-18 (UTC+3)
**Generated:** Validated via SSH docker ps inspection
**Last Migration:** Authelia (Phase 12 Complete, 2026-04-17)

---

## Executive Summary

- **Coolify-Managed:** 29 services ✅
- **Standalone (Not Managed):** 10 services
- **Migration Progress:** 12/12 infrastructure services (100%) ✅
- **Backup Solution:** Backrest deployed (replaces Duplicati)
- **Cleanup Complete:** 2.88GB disk space reclaimed
- **Firewall:** Ports 6001, 6002 opened for real-time service
- **Latest:** Authelia migration complete (Phase 12) ✅

---

## Coolify-Managed Services (29)

### Recently Migrated (Phases 1-11)
| Service | UUID | Status | Migrated |
|---------|------|--------|----------|
| netdata | kk4kcw4csksc48848go4o0wo | ✅ Healthy | 2026-04-17 |
| n8n | s8gwccsws0ccssw0wwgwsoks | ✅ Healthy | 2026-04-17 |
| apprise | lcocgs4gs8ksg4g08w40ows8 | ✅ Healthy | 2026-04-17 |
| node-exporter | doc8c8gkcgs88s8ckggw84o4 | ✅ Healthy | 2026-04-17 |
| promtail | w0000ckgsgg048w0848okk08 | ✅ Healthy | 2026-04-17 |
| cadvisor | r08sog4gwws88og048ows448 | ✅ Healthy | 2026-04-17 |
| loki | r48swckog008wosgwcs4g0g0 | ✅ Healthy | 2026-04-17 |
| alertmanager | zw4swgkwk0s4s8kg048gw80o | ✅ Healthy | 2026-04-17 |
| prometheus | c8cg0kosok4wswwcos04wwg0 | ✅ Healthy | 2026-04-17 |
| grafana | loc484owg8gsw04owo0go8kc | ✅ Healthy | 2026-04-17 |
| **backrest** | **l48000k44wc4gk8os88s8k0c** | **✅ Healthy** | **2026-04-17** |
| **authelia** | **hks48k8sg8o4co4co08co00o** | **✅ Healthy** | **2026-04-17** |

### Fabrik Microservices (Already Managed)
| Service | Container Name | Status |
|---------|----------------|--------|
| captcha | captcha-j8gg4ggskkossc4gkwowk4os-140246184500 | ✅ Running |
| translator | translator-kgws0s4cscsosw8gg848cwgw-140305573177 | ✅ Running |
| emailgateway | emailgateway-w4oocckkwko8kowggsw8sogc-140328040913 | ✅ Running |
| image-broker | image-broker-zo4ggs4g880skwkocwwkscgk-140330450088 | ✅ Running |
| proxy | proxy-v0cscowwsgkk88c4ckckgw0g-140350084065 | ✅ Running |
| file-api | file-api-bsswwg4kg480c000gksw004k-140449896537 | ✅ Running |
| file-worker | file-worker-nwcckwggw0o0g40gwskk8kk8-154849864122 | ✅ Running |
| site-provisioner (dns-manager) | site-provisioner-qokoksogwsk0c04gcs4swwgs-223724136560 | ✅ Running |

### Infrastructure Services (Already Managed)
| Service | Container Name | Status |
|---------|----------------|--------|
| postgres-main | postgres-main-l0k4gk0kggc8okcwk0s4c8s8 | ✅ Running |
| gatus | gatus-v8s4cokcwg0co4w8okkccc0w | ✅ Running |
| glitchtip-web | glitchtip-web-z00kkck8c8cwo800kk440csk | ✅ Running |
| glitchtip-worker | glitchtip-worker-msgo0sg8gsgo4w4sscckc84g | ✅ Running |

### Coolify Core (Self-Managed)
| Service | Container Name | Status |
|---------|----------------|--------|
| coolify-realtime | coolify-realtime | ✅ Running |
| coolify-sentinel | coolify-sentinel | ✅ Running |

### Infrastructure Services (Already Managed - Part 2)
| Service | Container Name | Status |
|---------|----------------|--------|
| meilisearch | bs0wo48k4gwo440gcowscoc8-150802066640 | ✅ Running |
| gotenberg | e04k4sco44ow04ccc0o0k00k-151256201601 | ✅ Running |
| browserless | vckgs8c00o40o884k48cgow8-150756746544 | ✅ Running |

---

## ⏳ Standalone Services (Not Coolify-Managed) - 10 Services

### Infrastructure - All Migrated ✅

### Coolify Core (3 services - DO NOT MIGRATE)
- **coolify** - Main Coolify container
- **coolify-db** - Coolify PostgreSQL database
- **coolify-redis** - Coolify Redis cache

### Shared Infrastructure (2 services - DO NOT MIGRATE)
- **redis-main** - Shared Redis for all services
- **traefik** - Reverse proxy (managed by Coolify)

### WordPress Sites (5 services - DO NOT MIGRATE)
- **ocoron-com-wordpress-1** - Main WordPress site
- **ocoron-com-db-1** - WordPress database
- **ocoron-com-redis-1** - WordPress cache
- **ocoron-com-nginx-1** - WordPress web server
- **ocoron-com-backup-1** - WordPress backup

**Status:** Running standalone, managed via docker-compose

---

## Migration Complete ✅

**All 12 infrastructure services successfully migrated to Coolify!**

### Completed Phases (2026-04-17)

| Phase | Service | Duration | Status |
|-------|---------|----------|--------|
| 1 | netdata | 15 min | ✅ Complete |
| 2-3 | n8n, apprise | 5-4 min | ✅ Complete |
| 4 | node-exporter | 3 min | ✅ Complete |
| 5 | promtail | 3 min | ✅ Complete |
| 6 | cadvisor | 3 min | ✅ Complete |
| 7 | loki | 4 min | ✅ Complete |
| 8 | alertmanager | 4 min | ✅ Complete |
| 9 | prometheus | 4 min | ✅ Complete |
| 10 | grafana | 4 min | ✅ Complete |
| 11 | backrest | 10 min | ✅ Complete |
| 12 | authelia | 15 min | ✅ Complete |

**Total Migration Time:** ~70 minutes
**Success Rate:** 100% (12/12)
**Downtime:** Zero (rolling migrations)

---

## Known Issues

### GlitchTip Container Name Mismatch (Low Priority)

**Status:** ⚠️ Cosmetic issue - services are healthy

**Problem:** GlitchTip may show errors for services with Coolify-generated container names.

**Root Cause:** GlitchTip expects short container names (e.g., `netdata`) but Coolify uses UUID-suffixed names (e.g., `netdata-kk4kcw4csksc48848go4o0wo`).

**Impact:** Low - Error tracking works, but container-level monitoring may show false negatives.

**Solution:** Configure GlitchTip DSN per service (optional - see service configuration audit results).

**Priority:** LOW - Services are functional, error tracking is optional.

---

## Post-Migration Tasks

### Completed ✅
1. [x] All 12 infrastructure services migrated to Coolify
2. [x] Authelia 2FA working and protecting admin dashboards
3. [x] Backrest deployed and backing up to Backblaze B2
4. [x] Cleanup complete - 2.88GB disk space reclaimed
5. [x] All services verified healthy

### Optional Improvements
1. [ ] Configure GlitchTip DSN for critical services (site-provisioner, emailgateway)
2. [ ] Import Grafana dashboards (1860 - Node Exporter, 14232 - Netdata)
3. [ ] Deploy Browserless/Gotenberg when projects need them
4. [ ] Document all Gatus endpoints (18 files currently monitored)

---

## Firewall Configuration

**Required Ports for Coolify (Self-Hosted):**

| Port | Purpose | Status |
|------|---------|--------|
| 22 | SSH access | ✅ Open |
| 80 | HTTP / SSL cert generation | ✅ Open |
| 443 | HTTPS traffic | ✅ Open |
| 6001 | Real-time communications (WebSocket) | ✅ Open (2026-04-17) |
| 6002 | Terminal access | ✅ Open (2026-04-17) |
| 8000 | Coolify dashboard (optional if using custom domain) | ✅ Open |

**Verification:**
```bash
sudo ufw status | grep -E '(6001|6002)'
curl -I http://172.93.160.197:6001  # Should return HTTP response
```

**Reference:** <https://coolify.io/docs/knowledge-base/server/firewall>

---

## Cleanup Summary (2026-04-17)

**Space Reclaimed:** 2.88GB

| Category | Details | Size |
|----------|---------|------|
| Old containers | 7 monitoring stack containers removed | N/A |
| Old volumes | 9 service volumes removed | ~100MB |
| Dangling volumes | 30 volumes pruned | 61.53MB |
| Unused images | Pruned images older than 24h | 2.821GB |

**Removed Services:**
- duplicati (container + volume)
- Old monitoring stack (grafana, prometheus, loki, alertmanager, promtail, cadvisor, node-exporter)

**Documentation:** `docs/infrastructure/coolify-migration-cleanup.md`

---

## Summary

**Infrastructure Status:**
- ✅ **100% Coolify-managed:** All 12 infrastructure services migrated
- ✅ **29 total services** managed by Coolify
- ✅ **10 standalone services** (Coolify core, shared infra, WordPress)
- ✅ **Zero downtime** during all migrations
- ✅ **All services healthy** and accessible
- ✅ **Firewall configured** (ports 6001, 6002 opened)
- ✅ **Cleanup complete** - 2.88GB disk space reclaimed

**Backup & Security:**
- ✅ Backrest deployed - daily backups to Backblaze B2
- ✅ Authelia protecting 6 admin dashboards with 2FA
- ✅ postgres-main backed up daily (1.04 MB dumps)
- ✅ Meilisearch secured with master key

**Optional Improvements:**
- ⚠️ GlitchTip DSN integration (optional error tracking)
- ⏸️ Grafana dashboards import (nice to have)
- ℹ️ Browserless/Gotenberg (deploy when needed)

**Migration Velocity:**
- Total time: ~70 minutes for 12 services
- Average: 6 minutes per service
- Success rate: 100% (12/12)
- **Trend:** Consistent and efficient ✅

**Status:** 🟢 **PRODUCTION READY** - All critical infrastructure migrated and operational.
