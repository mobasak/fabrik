# Infrastructure Services Coolify Migration - Summary

> **📌 ARCHIVED 2026-06-06.** Historical document preserved as-is for context. Frozen at the time of original ship. For current fleet state see [`vps-status.md`](../vps-status.md), [`vps-complete-inventory.md`](../vps-complete-inventory.md), and [`vps-fleet-architecture.md`](../vps-fleet-architecture.md). Do NOT update the content below — that would defeat the archive.

**Date:** 2026-04-17
**Status:** ✅ ALL PHASES COMPLETE (12/12 services migrated - 100%)

---

## Overview

Migrating standalone infrastructure services from manual Docker Compose to Coolify-managed deployments.

## Progress

### Completed ✅

| Service | UUID | Duration | Issues | Date |
|---------|------|----------|--------|------|
| netdata | kk4kcw4csksc48848go4o0wo | 15 min | Minor (Traefik routing) | 2026-04-17 |
| n8n | s8gwccsws0ccssw0wwgwsoks | 5 min | None | 2026-04-17 |
| apprise | lcocgs4gs8ksg4g08w40ows8 | 4 min | None | 2026-04-17 |
| node-exporter | doc8c8gkcgs88s8ckggw84o4 | 3 min | None | 2026-04-17 |
| promtail | w0000ckgsgg048w0848okk08 | 3 min | None | 2026-04-17 |
| cadvisor | r08sog4gwws88og048ows448 | 3 min | None | 2026-04-17 |
| loki | r48swckog008wosgwcs4g0g0 | 4 min | None | 2026-04-17 |
| alertmanager | zw4swgkwk0s4s8kg048gw80o | 4 min | None | 2026-04-17 |
| prometheus | c8cg0kosok4wswwcos04wwg0 | 4 min | None | 2026-04-17 |
| grafana | loc484owg8gsw04owo0go8kc | 4 min | None | 2026-04-17 |
| **backrest** | **l48000k44wc4gk8os88s8k0c** | **20 min** | **Config schema (retention vs prunePolicy)** | **2026-04-17** |
| **authelia** | **hks48k8sg8o4co4co08co00o** | **45 min** | **DNS, Traefik router conflict, site-provisioner routing** | **2026-04-17** |

### Migration Complete ✅

**All 12 infrastructure services successfully migrated to Coolify!**

**Final Phase (Authelia):**
- **Completed:** 2026-04-17 23:38 (UTC+3)
- **UUID:** hks48k8sg8o4co4co08co00o
- **Domain:** auth.vps1.ocoron.com
- **Downtime:** ~30 seconds (during cutover)
- **Issues Fixed:** DNS record creation, Traefik router name conflict, site-provisioner API routing

### Not Migrated ❌

| Service | Status | Reason |
|---------|--------|--------|
| duplicati | Replaced | Replaced by Backrest (l48000k44wc4gk8os88s8k0c) on 2026-04-17 |

## Key Learnings

1. **Coolify API quirk** - `docker_compose_raw` must be base64-encoded
2. **Traefik routing** - Restart Traefik after deploying new services
3. **Data preservation** - Use `external: true` volumes with exact names
4. **Network topology** - Always verify with `docker inspect`, don't assume
5. **Parallel testing** - Deploy test container first for zero-downtime
6. **Lessons applied** - Phase 2 (n8n) was 3x faster than Phase 1 (netdata)

## Documentation

- **Main runbook:** `docs/infrastructure/archive/coolify-migration.md`
- **Step-by-step guide:** `docs/infrastructure/coolify-migration-step-by-step.md`
- **Migration logs:** `docs/infrastructure/migration-log-phase1.md`, `migration-log-phase2.md`
- **Lessons learnt:** `docs/LESSONS_LEARNT.md`
- **VPS inventory:** `docs/infrastructure/vps-complete-inventory.md`
- **Service analysis:** `docs/infrastructure/vps-services-coolify-migration.md`

## Next Steps

1. **Monitor current migrations** - Watch netdata and n8n for 24 hours
2. **Phase 3: apprise** - Critical notification service
3. **Phase 4: authelia** - High-risk auth service (have SSH ready)
4. **Phase 5: Monitoring stack** - Complex interconnected services

## Rollback

All migrated services have 7-day rollback capability via archived configs in `/opt/.archive/`.
