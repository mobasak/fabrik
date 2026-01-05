# Step 1: Domain + Hosting - Full Automation

**Date:** 2025-12-25
**Status:** ✅ COMPLETE

---

## Overview

**Zero manual steps.** Full domain provisioning via VPS DNS Manager API.

### State Machine

```
INIT → CF_ZONE_CREATED → NC_NAMESERVERS_SET → CF_STATUS_PENDING/ACTIVE → DNS_SYNCED
```

### API Endpoints Used

| Step | Endpoint | Action |
|------|----------|--------|
| A | `POST /api/cloudflare/zones` | Create Cloudflare zone |
| B | `PUT /api/dns/{domain}/nameservers` | Set nameservers at Namecheap |
| C | `GET /api/cloudflare/zones/{domain}/status` | Track zone status |
| D | `POST /api/cloudflare/dns/{domain}` | Apply DNS records |

**Cloudflare status is the only gate.** No propagation waiting. No manual steps.

---

## Quick Start

### Provision New Domain (Full Automation)

```python
from fabrik.wordpress import provision_domain, sync_dns

# Step A-C: Create zone, set nameservers, check status
result = provision_domain('tojlo.com')
print(f"Zone ID: {result.zone_id}")
print(f"Nameservers: {result.nameservers}")
print(f"Status: {result.cloudflare_status}")  # 'pending' or 'active'

# Step D: Apply DNS records (when zone is active, or force=True)
dns_result = sync_dns('tojlo.com', vps_ip='172.93.160.197', proxied=True)
print(f"A Record Created: {dns_result.a_record_created}")
print(f"WWW Created: {dns_result.www_record_created}")
```

### Check Domain Status

```python
from fabrik.wordpress import get_domain_status

status = get_domain_status('tojlo.com')
# {
#   'domain': 'tojlo.com',
#   'zone_id': 'd6421553dec1222294328b3c1721b544',
#   'cloudflare_status': 'pending',
#   'nameservers': ['kiki.ns.cloudflare.com', 'lex.ns.cloudflare.com'],
#   'record_count': 2,
#   'has_a_record': True
# }
```

---

## Tested Domains

### tojlo.com (2025-12-25)

```
✅ Step A: Zone created (d6421553dec1222294328b3c1721b544)
✅ Step B: Nameservers set (kiki.ns.cloudflare.com, lex.ns.cloudflare.com)
⏳ Step C: Status pending (Cloudflare verifying nameservers)
✅ Step D: DNS records synced
   - A: tojlo.com → 172.93.160.197
   - CNAME: www.tojlo.com → tojlo.com
```

### ocoron.com (2025-12-25)

```
✅ Zone: b3494f947c71683f94b6afe1331a1ba6
✅ Status: active
✅ A record: ocoron.com → 172.93.160.197 (proxied)
✅ CNAME: www.ocoron.com → ocoron.com
✅ M365 records preserved (MX, autodiscover, SPF)
✅ HTTPS working (Cloudflare Edge Certificate)
```

---

## SSL Certificate (Automatic)

**With Cloudflare Proxy (`proxied: true`):**

```
Browser → Cloudflare Edge (SSL termination) → VPS (origin)
```

- **Edge Certificate:** Cloudflare provides automatically (free)
- **No Let's Encrypt needed** for public-facing SSL
- **No manual configuration** - zone + A record = HTTPS
- **Auto-renewal:** Cloudflare handles it

**Without Cloudflare Proxy (`proxied: false`):**

```
Browser → VPS (Traefik + Let's Encrypt)
```

- Used for internal services (e.g., wp-test.vps1.ocoron.com)
- Traefik requests Let's Encrypt certificate via ACME
- Auto-renewal every 90 days

---

## Module Reference

### File: `src/fabrik/wordpress/domain_setup.py`

```python
# Primary functions
provision_domain(domain: str) -> ProvisionResult
sync_dns(domain: str, vps_ip: str, proxied: bool, force: bool) -> DNSSyncResult
get_domain_status(domain: str) -> dict

# Classes
DomainProvisioner  # Full automation via VPS DNS Manager
ProvisionResult    # Result of Steps A-C
DNSSyncResult      # Result of Step D
ProvisionState     # State machine enum

# Legacy compatibility
DomainSetup        # Wraps DomainProvisioner
setup_domain()     # Legacy function
```

### ProvisionResult Fields

```python
@dataclass
class ProvisionResult:
    success: bool
    domain: str
    state: ProvisionState
    zone_id: str | None
    zone_created: bool
    nameservers: list[str]
    registrar_ns_set: bool
    cloudflare_status: 'pending' | 'active' | None
    errors: list[str]
```

### DNSSyncResult Fields

```python
@dataclass
class DNSSyncResult:
    success: bool
    domain: str
    applied: bool
    blocked_by_status: 'pending' | None
    a_record_created: bool
    www_record_created: bool
    records_preserved: int
    errors: list[str]
```

---

## VPS DNS Manager API

Base URL: `https://dns.vps1.ocoron.com`

### Create Zone (Step A)

```bash
curl -X POST "https://dns.vps1.ocoron.com/api/cloudflare/zones" \
  -H "Content-Type: application/json" \
  -d '{"domain": "example.com"}'

# Response:
# {
#   "zone_id": "abc123...",
#   "domain": "example.com",
#   "status": "pending",
#   "name_servers": ["kiki.ns.cloudflare.com", "lex.ns.cloudflare.com"],
#   "created": true
# }
```

### Set Nameservers at Namecheap (Step B)

```bash
curl -X PUT "https://dns.vps1.ocoron.com/api/dns/example.com/nameservers" \
  -H "Content-Type: application/json" \
  -d '{"nameservers": ["kiki.ns.cloudflare.com", "lex.ns.cloudflare.com"]}'

# Response:
# {"success": true, "message": "Nameservers updated"}
```

### Check Zone Status (Step C)

```bash
curl "https://dns.vps1.ocoron.com/api/cloudflare/zones/example.com/status"

# Response:
# {
#   "zone_id": "abc123...",
#   "domain": "example.com",
#   "status": "active",
#   "name_servers": ["kiki.ns.cloudflare.com", "lex.ns.cloudflare.com"],
#   "paused": false
# }
```

### Add DNS Record (Step D)

```bash
curl -X POST "https://dns.vps1.ocoron.com/api/cloudflare/dns/example.com" \
  -H "Content-Type: application/json" \
  -d '{
    "record_type": "A",
    "name": "example.com",
    "content": "172.93.160.197",
    "ttl": 1,
    "proxied": true
  }'
```

### List DNS Records

```bash
curl "https://dns.vps1.ocoron.com/api/cloudflare/dns/example.com"

# Response:
# {
#   "domain": "example.com",
#   "zone_id": "abc123...",
#   "records": [
#     {"type": "A", "name": "example.com", "content": "172.93.160.197", ...},
#     {"type": "CNAME", "name": "www.example.com", "content": "example.com", ...}
#   ]
# }
```

---

## Deployer Integration

```python
from fabrik.wordpress import SiteDeployer

# DNS is Step 1 in the deployer
deployer = SiteDeployer('example.com')
result = deployer.deploy()

# Steps: dns → settings → theme → pages → menus → forms → seo → finalize
```

---

## Design Decisions

### Why Cloudflare (not Namecheap DNS)?

- **Namecheap DNS API:** Destructive (delete all → set all)
- **Cloudflare DNS API:** Per-record CRUD (safe, preserves existing records)
- **M365 records:** MX, autodiscover, SPF preserved automatically

### Why VPS DNS Manager (not direct API calls)?

- **Centralized:** Single service manages both Namecheap and Cloudflare
- **Credentials:** API tokens stored securely on VPS only
- **Logging:** All DNS operations logged in one place
- **Rate limiting:** Built-in protection

### Why No Propagation Waiting?

- **Cloudflare status** is the authoritative gate
- DNS records can be created even when zone is `pending`
- System tracks state, not timing
- Re-run safe (idempotent)

---

## Summary

| Component | Status |
|-----------|--------|
| Zone Creation | ✅ `POST /api/cloudflare/zones` |
| Nameserver Setting | ✅ `PUT /api/dns/{domain}/nameservers` |
| Status Tracking | ✅ `GET /api/cloudflare/zones/{domain}/status` |
| DNS Record Sync | ✅ `POST /api/cloudflare/dns/{domain}` |
| HTTPS Certificate | ✅ Automatic (Cloudflare Edge) |
| M365 Preservation | ✅ Per-record CRUD |
| Deployer Integration | ✅ `_step_dns()` |

**Step 1 is fully automated. Ready for Step 2 (WordPress deployment).**
