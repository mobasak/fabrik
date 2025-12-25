# Future Development Decisions

**Last Updated:** 2025-12-22

This document captures architectural decisions and future development recommendations for Fabrik.

---

## DNS Strategy

### Current State
- **Provider:** Namecheap DNS
- **Service:** `/opt/namecheap` API wrapper deployed and functional
- **Status:** Working, manages 5 domains, 14+ DNS records

### Recommendation

**Keep Namecheap DNS** if:
- Services are protected (auth + firewall)
- No need for edge caching/CDN
- IP whitelist stays stable
- Minimal operational changes desired

**Migrate to Cloudflare** when either happens:
1. You want an easy "edge" layer (TLS/CDN/basic DDoS) with low ops, free tier acceptable
2. You start getting hostile traffic (bots/bruteforce) and want edge mitigation without building it yourself

### Comparison

| Aspect | Namecheap | Cloudflare |
|--------|-----------|------------|
| **API Safety** | ❌ Destructive (replaces ALL records) | ✅ Per-record CRUD |
| **IP Whitelist** | ❌ Required | ✅ Not needed |
| **CDN** | ❌ None | ✅ Free global CDN |
| **WAF/DDoS** | ❌ None | ✅ Free protection |
| **Propagation** | Slower | Fast (seconds) |
| **Cost** | Free | Free |

### Migration Path (When Ready)
See `Phase4.md` for detailed Cloudflare migration steps including:
- Cloudflare DNS driver implementation
- Per-domain migration checklist
- Zero-downtime nameserver change procedure

---

## Infrastructure Improvements

### Completed (2025-12-22 / 2025-12-23)
- [x] Docker log rotation verified (already configured in `/etc/docker/daemon.json`)
- [x] Redis deployed (`redis-main` on coolify network, 256MB max memory, LRU eviction)
- [x] Duplicati backup system deployed and configured:
  - **Web UI:** https://backup.vps1.ocoron.com
  - **Backend:** Backblaze B2 (`vps1-ocoron-backups/duplicati/`)
  - **Features:** Incremental backups, web-based restore, browse by date
  - **Sources:** `/opt` configs, Docker volumes
  - **First backup:** ✅ Completed 2025-12-23 (~750MB)
  - **Automation:** ServerUtil CLI available for scripted management
- [x] Fabrik drivers created (DNS + Coolify API clients)
- [x] Master credentials file consolidated at `/opt/fabrik/.env`
- [x] Windsurfrules updated with mandatory credentials management
  
### Backup Adjustment Required When Projects Go Live

> **IMPORTANT:** Current backup configuration (daily, 7-day retention) is suitable for development/early stage. When projects go live with active users and frequent database changes:

| Scenario | Recommended Change |
|----------|-------------------|
| **High-frequency DB writes** | Increase backup frequency to every 4-6 hours |
| **Critical user data** | Enable PostgreSQL WAL archiving for point-in-time recovery |
| **Large media files** | Consider separate backup job with longer retention |
| **Compliance requirements** | Extend retention to 30-90 days |

Adjust in Duplicati web UI: https://backup.vps1.ocoron.com

### Planned
- [x] Uptime Kuma monitoring (Phase 1) - Deployed 2025-12-23
- [ ] Grafana + Loki stack (Phase 6)
- [ ] Multi-server scaling (Phase 7)
- [ ] n8n workflow automation (Phase 8)

---

## Fabrik CLI Development

### Priority Order
1. **Minimal CLI** - Wrap existing services (namecheap, postgres-main)
2. **Template System** - Python API and WordPress templates
3. **WordPress Automation** - WP-CLI + REST API (Phase 2)
4. **AI Content** - LLM integration (Phase 3)

### Existing Services to Leverage
Instead of rebuilding, Fabrik CLI should call:
- `namecheap` service for DNS (already has safe merge-before-write)
- `postgres-main` for database provisioning
- `traefik` labels for routing

---

## Notes

_Add future architectural decisions and recommendations here._
