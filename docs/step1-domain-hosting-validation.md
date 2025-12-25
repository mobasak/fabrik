# Step 1: Domain + Hosting - Validation & Automation Plan

**Date:** 2025-12-25  
**Status:** Planning

---

## User Requirements

### Domain Registration
- **Provider:** Namecheap
- **Method:** Auto-register via Namecheap API
- **Trigger:** Web client (from future-development.md)

### DNS Management
- **Provider:** Cloudflare
- **Method:** VPS DNS Manager API (`https://dns.vps1.ocoron.com`)
- **API Access:** ✅ Available (Cloudflare API integration)

### HTTPS Certificate
- **Provider:** Let's Encrypt (via Traefik/Coolify)
- **Method:** Auto-provision when domain points to VPS
- **Note:** Namecheap SSL not needed (Let's Encrypt is free and auto-renewing)

### Database
- **Provider:** PostgreSQL (postgres-main container on VPS)
- **Method:** Fabrik creates database after WordPress deployment

---

## Current Infrastructure Status

### ✅ VPS DNS Manager (Operational)
```bash
URL: https://dns.vps1.ocoron.com
Status: healthy
Version: 0.1.0
Sandbox: false
```

**Capabilities:**
- ✅ Cloudflare DNS API integration
- ✅ Add/update/delete DNS records
- ✅ List zones and records
- ✅ Subdomain creation

**Test:**
```bash
curl -s https://dns.vps1.ocoron.com/health
# {"status":"healthy","version":"0.1.0","sandbox":false}
```

### ✅ Cloudflare DNS Driver (Implemented)
```python
# src/fabrik/drivers/cloudflare.py
from fabrik.drivers.cloudflare import CloudflareClient

cf = CloudflareClient()
zone_id = cf.get_zone_id("ocoron.com")
cf.create_record(zone_id, "A", "myapp", "172.93.160.197", proxied=True)
```

**Features:**
- List zones
- Get zone ID by domain
- Create/update/delete DNS records
- Enable Cloudflare proxy (CDN/WAF)
- Per-record CRUD (safer than Namecheap's destructive API)

### ✅ DNS Client Wrapper (Implemented)
```python
# src/fabrik/drivers/dns.py
from fabrik.drivers.dns import DNSClient

dns = DNSClient()
dns.add_subdomain("ocoron.com", "myapp.vps1", "172.93.160.197")
```

**Features:**
- Wraps VPS DNS Manager service
- Supports both Namecheap and Cloudflare
- Health checks and rate limiting
- Domain availability checking

---

## Namecheap Domain Registration API

### ❌ NOT IMPLEMENTED YET

**Namecheap API Capabilities:**
- `domains.create` - Register new domain
- `domains.check` - Check availability
- `domains.getList` - List owned domains
- `domains.getInfo` - Get domain details

**Requirements:**
- Namecheap API key (production mode)
- Whitelisted IP address
- Account balance for domain purchase

**Implementation Needed:**
```python
# src/fabrik/drivers/namecheap.py (NEW FILE)
class NamecheapClient:
    def check_availability(self, domain: str) -> bool:
        """Check if domain is available for registration."""
        
    def register_domain(
        self,
        domain: str,
        years: int = 1,
        registrant_info: dict = None
    ) -> dict:
        """Register a new domain."""
        
    def get_domain_info(self, domain: str) -> dict:
        """Get domain registration details."""
```

**Current Status:**
- DNS Manager has Namecheap API access (for DNS records)
- Domain registration API NOT integrated
- Would need to add to DNS Manager service or create separate client

---

## HTTPS Certificate Strategy

### ✅ Let's Encrypt (Recommended - Already Working)

**How it works:**
1. Domain points to VPS (A record)
2. Traefik (reverse proxy) detects new domain
3. Traefik requests Let's Encrypt certificate via ACME
4. Certificate auto-renews every 90 days

**Advantages:**
- ✅ Free
- ✅ Auto-renewal
- ✅ Already configured on VPS
- ✅ Works with Coolify deployments
- ✅ No additional API calls needed

**Example (wp-test.vps1.ocoron.com):**
```bash
curl -I https://wp-test.vps1.ocoron.com
# HTTP/2 200
# server: nginx
# ... (HTTPS working)
```

### ❌ Namecheap SSL (Not Recommended)

**Why not:**
- Costs money ($9-60/year depending on type)
- Manual renewal or API complexity
- Need to install certificate manually
- Let's Encrypt is already working and free

**Verdict:** Use Let's Encrypt, not Namecheap SSL

---

## ocoron.com Current Status

### Domain Registration
```
✅ Registered at Namecheap
✅ Active and owned
```

### DNS Configuration
```bash
# Current DNS records (via Cloudflare API)
curl -s https://dns.vps1.ocoron.com/api/cloudflare/dns/ocoron.com

Records found:
- MX: ocoron-com.mail.protection.outlook.com (Microsoft 365 email)
- NS: dns1.registrar-servers.com, dns2.registrar-servers.com (Namecheap nameservers)
- TXT: SPF, MS verification
```

**Issue:** Nameservers still point to Namecheap, not Cloudflare

**To migrate to Cloudflare:**
1. Get Cloudflare nameservers for ocoron.com zone
2. Update nameservers at Namecheap registrar
3. Wait for DNS propagation (24-48 hours)

### HTTPS Certificate
```
❓ Unknown - need to check if ocoron.com has A record pointing to VPS
```

**To check:**
```bash
dig ocoron.com A
# Should return: 172.93.160.197 (VPS IP)
```

**If no A record:** Need to add via DNS Manager

---

## Step 1 Automation Flow (Proposed)

### For New Domain (Full Automation)

```
1. Check Domain Availability
   ├─ Call: namecheap.check_availability(domain)
   └─ If unavailable: suggest alternatives

2. Register Domain (if available)
   ├─ Call: namecheap.register_domain(domain, registrant_info)
   ├─ Cost: ~$10-15/year (charged to Namecheap account)
   └─ Wait: 1-5 minutes for registration

3. Set Cloudflare Nameservers
   ├─ Get: Cloudflare nameservers for zone
   ├─ Call: namecheap.set_nameservers(domain, cf_nameservers)
   └─ Wait: 24-48 hours for propagation

4. Add DNS Records (Cloudflare)
   ├─ Call: cloudflare.create_record(zone_id, "A", "@", vps_ip, proxied=True)
   ├─ Call: cloudflare.create_record(zone_id, "A", "www", vps_ip, proxied=True)
   └─ Immediate effect (once nameservers propagated)

5. Wait for HTTPS Certificate
   ├─ Traefik detects new domain
   ├─ Requests Let's Encrypt certificate
   └─ Wait: 1-5 minutes for certificate issuance

6. Deploy WordPress Container (Coolify)
   ├─ Create project in Coolify
   ├─ Deploy Docker Compose (WordPress + MariaDB)
   └─ Wait: 2-5 minutes for deployment

7. Create Database
   ├─ WordPress container creates database automatically
   └─ Or: Fabrik creates via postgres-main if using PostgreSQL

✅ Domain ready for Step 2 (WordPress installation)
```

### For Existing Domain (ocoron.com)

```
1. Verify Domain Ownership
   ├─ Call: namecheap.get_domain_info("ocoron.com")
   └─ Confirm: registered and active

2. Check DNS Configuration
   ├─ Call: cloudflare.get_zone_id("ocoron.com")
   ├─ If not in Cloudflare: create zone
   └─ Get Cloudflare nameservers

3. Update Nameservers (if needed)
   ├─ Current: dns1.registrar-servers.com (Namecheap)
   ├─ Target: ns1.cloudflare.com, ns2.cloudflare.com
   ├─ Call: namecheap.set_nameservers("ocoron.com", cf_nameservers)
   └─ Wait: 24-48 hours

4. Add A Record (if missing)
   ├─ Check: dig ocoron.com A
   ├─ If no record: cloudflare.create_record(zone_id, "A", "@", "172.93.160.197")
   └─ Wait: 1-5 minutes for DNS propagation

5. Verify HTTPS
   ├─ Wait for Let's Encrypt certificate
   ├─ Test: curl -I https://ocoron.com
   └─ Should return: HTTP/2 200

6. Deploy WordPress (Step 2)
   └─ Continue to WordPress installation

✅ Domain ready for Step 2
```

---

## Implementation Gaps

### ❌ Missing Components

1. **Namecheap Domain Registration API**
   - File: `src/fabrik/drivers/namecheap.py` (doesn't exist)
   - Methods: `check_availability()`, `register_domain()`, `set_nameservers()`
   - Effort: 1-2 days

2. **Domain Registration CLI Command**
   - Command: `fabrik domain register <domain>`
   - Effort: 1 day

3. **Nameserver Migration Helper**
   - Command: `fabrik domain migrate-to-cloudflare <domain>`
   - Effort: 1 day

4. **Step 1 Orchestrator**
   - Module: `src/fabrik/wordpress/domain_setup.py`
   - Class: `DomainSetup`
   - Methods: `register()`, `configure_dns()`, `verify_https()`
   - Effort: 2-3 days

### ✅ Already Working

1. **Cloudflare DNS Management** - `src/fabrik/drivers/cloudflare.py`
2. **DNS Manager Service** - `https://dns.vps1.ocoron.com`
3. **Let's Encrypt HTTPS** - Traefik auto-provision
4. **VPS Infrastructure** - All services operational

---

## Recommendations

### For Immediate Progress (ocoron.com)

**Skip domain registration** (already registered) and focus on:

1. ✅ Verify ocoron.com DNS configuration
2. ✅ Add A record if missing (point to VPS)
3. ✅ Verify HTTPS certificate
4. ✅ Mark Step 1 complete for ocoron.com
5. ✅ Proceed to Step 2 (WordPress installation)

### For Future Sites

**Build domain registration automation:**

1. Implement `NamecheapClient` for domain registration
2. Add `fabrik domain register` command
3. Integrate with web client (future-development.md)
4. Full automation: domain check → register → DNS → HTTPS → deploy

---

## Next Actions

### Option A: Complete Step 1 for ocoron.com (Fast)
```bash
# 1. Check if A record exists
dig ocoron.com A

# 2. Add A record if missing
fabrik dns add ocoron.com @ 172.93.160.197

# 3. Verify HTTPS
curl -I https://ocoron.com

# 4. Mark Step 1 complete
# 5. Proceed to Step 2
```

### Option B: Build Full Automation (Slower)
```bash
# 1. Implement NamecheapClient
# 2. Add domain registration commands
# 3. Test with new domain
# 4. Then proceed with ocoron.com
```

---

## Summary

| Component | Status | Notes |
|-----------|--------|-------|
| **Namecheap Domain Registration** | ❌ Not implemented | Need to build API client |
| **Cloudflare DNS** | ✅ Working | Via VPS DNS Manager + CloudflareClient |
| **HTTPS Certificates** | ✅ Working | Let's Encrypt via Traefik (free, auto-renew) |
| **Database Creation** | ✅ Working | Fabrik creates after WordPress deployment |
| **ocoron.com Domain** | ✅ Registered | Need to verify DNS and HTTPS |

**Recommendation:** Proceed with Option A (complete Step 1 for ocoron.com) and build full automation later for future sites.
