# Fabrik Development Tasks

**Last Updated:** 2025-12-27

---

## Phase 1: Foundation ✅ COMPLETE (25/25)

### VPS Hardening ✅

- [x] SSH hardening (keys only, no root, AllowUsers)
- [x] UFW firewall (22, 80, 443 only)
- [x] Fail2ban setup
- [x] Unattended upgrades
- [x] Docker log rotation

### Coolify Setup ✅

- [x] Install Coolify (v4.0.0-beta.455)
- [x] Secure Coolify (password, HTTPS)
- [x] Deploy postgres-main (PostgreSQL 16)
- [x] Deploy redis-main
- [x] Configure postgres backup to B2 (Duplicati)

### Fabrik Core ✅

- [x] Create folder structure
- [x] Set up secrets (platform.env)
- [x] Implement spec_loader.py
- [x] Implement dns_namecheap.py (DNSClient driver)
- [x] Implement coolify.py (CoolifyClient driver)
- [x] Implement template_renderer.py
- [x] Implement `fabrik new`
- [x] Implement `fabrik plan`
- [x] Implement `fabrik apply`
- [x] Implement `fabrik logs`
- [x] Implement `fabrik destroy`

### First Deployment ✅

- [x] Create app-python template
- [x] Deploy hello-api (manual, not via fabrik)

### Monitoring ✅

- [x] Deploy Uptime Kuma
- [x] Configure checks + alerts

### Validation ✅

- [x] Test backup + restore

---

## Phase 1b: Cloud Infrastructure ✅ COMPLETE (10/10)

- [x] Set up Supabase project
- [x] Set up Cloudflare R2 bucket
- [x] Create Supabase driver
- [x] Create R2 driver
- [x] Apply DDL (tenants, files, jobs, derivatives)
- [x] Update Fabrik spec schema for `storage: r2`
- [x] Create Node API template (presigned URLs) — templates/file-api
- [x] Create Python worker template — templates/file-worker
- [x] Deploy first file-processing service (local test passed)
- [x] Verify end-to-end flow

---

## Phase 1c: Cloudflare DNS Migration ⚡ 75% (9/12)

- [x] Create Cloudflare account
- [x] Add domain to Cloudflare (ocoron.com)
- [x] Implement Cloudflare DNS driver
- [x] Migrate DNS records from Namecheap
- [x] Update nameservers at registrar
- [x] Configure SSL mode (Full Strict)
- [ ] Set up WAF rules — *Deferred (with WordPress)*
- [x] Update Fabrik to use Cloudflare driver
- [x] Unified DNS Manager service (dns.vps1.ocoron.com)
- [x] WordPress tasks moved to Phase 2

---

## Phase 2: WordPress Automation ⚡ 67% (8/12)

### Core ✅

- [x] Create WordPress template (compose + env + hardening)
- [x] Add backup sidecar to template
- [x] Deploy WordPress test site (wp-test.vps1.ocoron.com)
- [x] WP-CLI wrapper (WordPressClient driver)
- [x] WordPress REST API client (WordPressAPIClient driver)
- [x] Theme management (via WP-CLI wrapper)
- [x] Plugin management (via WP-CLI wrapper)
- [x] Content operations (via REST API client)

### Pending ❌

- [ ] Configure WAF rules — *Needs Cloudflare permissions*
- [ ] Build preset loader — *Load presets/saas.yaml, company.yaml, etc.*
- [ ] Create themes (flavor-starter, flavor-corporate)
- [ ] **Deploy ocoron.com** — *Company site, multilingual EN/TR*

---

## Phase 3: AI Content Integration ❌ NOT STARTED (0/6)

*Requires Phase 2 complete*

- [ ] LLM client wrapper (Claude/OpenAI)
- [ ] Content generation engine
- [ ] Content revision system
- [ ] Bulk generation tools
- [ ] SEO optimization
- [ ] Windsurf agent integration

---

## Phase 4-8: Future Phases ❌ NOT STARTED

- **Phase 4:** DNS Migration + Advanced Networking
- **Phase 5:** Staging + Multi-Environment
- **Phase 6:** Advanced Monitoring
- **Phase 7:** Multi-Server Scaling
- **Phase 8:** Business Automation (n8n)

---

## Current Priority

1. **Deploy ocoron.com** — Company site with multilingual support
2. Build preset loader
3. Create custom themes

---

## VPS Services Deployed

| Service | URL | Status |
|---------|-----|--------|
| Coolify | vps1.ocoron.com:8000 | ✅ |
| Netdata | netdata.vps1.ocoron.com | ✅ |
| Uptime Kuma | status.vps1.ocoron.com | ✅ |
| Duplicati | backup.vps1.ocoron.com | ✅ |
| Image Broker | images.vps1.ocoron.com | ✅ |
| DNS Manager | dns.vps1.ocoron.com | ✅ |
| Translator | translator.vps1.ocoron.com | ✅ |
| Captcha | captcha.vps1.ocoron.com | ✅ |
| File API | files-api.vps1.ocoron.com | ✅ |
| Email Gateway | emailgateway.vps1.ocoron.com | ✅ |
| Proxy API | proxy.vps1.ocoron.com | ✅ |
| WordPress Test | wp-test.vps1.ocoron.com | ✅ |
