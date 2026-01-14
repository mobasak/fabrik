> **Phase Navigation:** [← Phase 3](Phase3.md) | **Phase 4** | [Phase 5 →](Phase5.md) | [All Phases](roadmap.md)

**Status:** ✅ COMPLETE (historical implementation)
## Phase 4: DNS Migration + Advanced Networking — Complete Narrative

**Status: ✅ COMPLETED (Done in Phase 1c)**

---

### Progress Tracker

| Step | Task | Status |
|------|------|--------|
| 1 | Cloudflare DNS driver | ✅ Done (Phase 1c) |
| 2 | Migrate from Namecheap to Cloudflare | ✅ Done (Phase 1c) |
| 3 | Proxy mode for CDN | ✅ Available |
| 4 | WAF rules | ⏸️ Deferred (with WordPress) |
| 5 | Page rules for caching | ⏸️ Deferred (with WordPress) |
| 6 | SSL mode (Full Strict) | ✅ Done |
| 7 | Dual-provider support | ✅ Done (dns.vps1.ocoron.com) |
| 8 | Unified DNS Manager service | ✅ Done |

**Completion: 6/8 tasks (75%)** - Core complete, WAF/caching deferred to WordPress deployment.

---

### What We Built in Phase 4 (via Phase 1c)

1. **Cloudflare DNS driver** with per-record CRUD operations (no destructive replace-all)
2. **Smooth migration path** from Namecheap to Cloudflare
3. **Proxy mode** for CDN and basic DDoS protection
4. **WAF rules** for WordPress-specific protection *(deferred)*
5. **Page rules** for caching optimization *(deferred)*
6. **SSL mode** properly configured (Full Strict)
7. **Dual-provider support** — can use either Namecheap or Cloudflare per domain
8. **Faster, safer DNS automation** for all future deployments

This phase eliminates the Namecheap API pain points (destructive setHosts, IP whitelisting) and adds CDN/security benefits.

---

### Why Migrate to Cloudflare?

**Namecheap DNS Problems:**

| Issue | Impact |
|-------|--------|
| `setHosts` replaces ALL records | Risk of deleting mail/verification records |
| Requires IP whitelisting | Breaks when your IP changes |
| No per-record API | Must read-all, merge, write-all |
| No CDN/WAF included | Separate service needed |
| Slower propagation | Changes take longer to apply |

**Cloudflare DNS Benefits:**

| Benefit | Impact |
|---------|--------|
| Per-record CRUD API | Safe, precise changes |
| No IP whitelist needed | Works from anywhere |
| Free CDN included | Faster global delivery |
| Free WAF included | Block common attacks |
| Fast propagation | Changes apply in seconds |
| DDoS protection | Automatic attack mitigation |
| Analytics | See traffic and threats |

**Cost:** Free tier covers everything we need.

---

### Prerequisites

Before starting Phase 4, confirm:

```
[ ] Phase 1-3 complete
[ ] At least one domain currently on Namecheap DNS
[ ] Cloudflare account created (free tier)
[ ] Access to Namecheap registrar settings
[ ] Current DNS records documented (exported from Namecheap)
```

---

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│  FABRIK CLI                                                     │
│                                                                 │
│  fabrik apply site-id                                           │
│                                                                 │
│  spec.yaml:                                                     │
│    dns:                                                         │
│      provider: cloudflare    # or namecheap                     │
│      zone_id: abc123                                            │
│      proxy: true             # Enable CDN                       │
└─────────────────────┬───────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│  DNS DRIVER (auto-selected by provider)                         │
│                                                                 │
│  ┌─────────────────────┐    ┌─────────────────────────────────┐ │
│  │  Namecheap Driver   │    │  Cloudflare Driver              │ │
│  │                     │    │                                 │ │
│  │  • Export all       │    │  • Get single record            │ │
│  │  • Merge desired    │    │  • Create record                │ │
│  │  • Replace all      │    │  • Update record                │ │
│  │  (risky)            │    │  • Delete record                │ │
│  └─────────────────────┘    │  (safe, per-record)             │ │
│                              └─────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│  CLOUDFLARE (when using Cloudflare)                             │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  DNS                                                    │    │
│  │  • A, AAAA, CNAME, MX, TXT records                      │    │
│  │  • Proxy mode (orange cloud) or DNS-only (gray cloud)   │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  CDN/Proxy (when proxy=true)                            │    │
│  │  • Global edge caching                                  │    │
│  │  • Automatic HTTPS                                      │    │
│  │  • HTTP/2, HTTP/3                                       │    │
│  │  • Brotli compression                                   │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  WAF (Web Application Firewall)                         │    │
│  │  • Managed rulesets (free)                              │    │
│  │  • WordPress-specific rules                             │    │
│  │  • Rate limiting                                        │    │
│  │  • Bot protection                                       │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Page Rules / Cache Rules                               │    │
│  │  • Cache static assets                                  │    │
│  │  • Bypass cache for admin                               │    │
│  │  • Security headers                                     │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│  YOUR VPS (origin server)                                       │
│                                                                 │
│  Coolify → Traefik → WordPress/Apps                             │
└─────────────────────────────────────────────────────────────────┘
```

---

### Step 1: Create Cloudflare Account and Get API Token

**Why:** We need API access to automate DNS management.

**Steps:**

**1.1: Create Cloudflare Account**

1. Go to https://dash.cloudflare.com/sign-up
2. Create account with your email
3. Verify email

**1.2: Create API Token**

1. Go to: Profile → API Tokens → Create Token
2. Use template: "Edit zone DNS"
3. Configure permissions:
   ```
   Zone - DNS - Edit
   Zone - Zone - Read
   Zone - Zone Settings - Edit (optional, for SSL/cache settings)
   ```
4. Zone Resources: Include → Specific zone → (select after adding domain)
   - Or: Include → All zones (if managing multiple domains)
5. Create Token
6. **Copy the token immediately** — you won't see it again

**1.3: Save Token**

```bash
# Add to secrets/platform.env
echo "CF_API_TOKEN=your_token_here" >> secrets/platform.env
```

**Time:** 15 minutes

---

### Step 2: Implement Cloudflare DNS Driver

**Why:** This is the core improvement — per-record CRUD operations instead of Namecheap's replace-all approach.

**Code:**

```python
# compiler/dns_cloudflare.py

import os
from typing import Optional
from dataclasses import dataclass
import httpx

@dataclass
class DNSRecord:
    type: str           # A, AAAA, CNAME, MX, TXT
    name: str           # @ or subdomain (Cloudflare uses full name internally)
    content: str        # IP, target, or value
    ttl: int = 1        # 1 = automatic
    priority: Optional[int] = None  # For MX
    proxied: bool = False  # Orange cloud (CDN) or gray cloud (DNS only)
    record_id: Optional[str] = None  # Cloudflare record ID

    def to_dict(self) -> dict:
        d = {
            'type': self.type,
            'name': self.name,
            'content': self.content,
            'ttl': self.ttl,
            'proxied': self.proxied
        }
        if self.priority is not None:
            d['priority'] = self.priority
        return d

    @classmethod
    def from_cf_response(cls, data: dict) -> 'DNSRecord':
        return cls(
            type=data['type'],
            name=data['name'],
            content=data['content'],
            ttl=data['ttl'],
            priority=data.get('priority'),
            proxied=data.get('proxied', False),
            record_id=data['id']
        )

@dataclass
class DNSDiff:
    to_create: list[DNSRecord]
    to_update: list[tuple[DNSRecord, DNSRecord]]  # (current, desired)
    to_delete: list[DNSRecord]
    unchanged: list[DNSRecord]

    @property
    def has_changes(self) -> bool:
        return bool(self.to_create or self.to_update or self.to_delete)

@dataclass
class DNSResult:
    status: str  # applied, unchanged, error
    changes: DNSDiff
    created: int = 0
    updated: int = 0
    deleted: int = 0
    error: Optional[str] = None

class CloudflareDNS:
    """
    Cloudflare DNS driver with safe per-record operations.

    Unlike Namecheap, Cloudflare supports:
    - Get single record
    - Create single record
    - Update single record
    - Delete single record

    No risk of accidentally deleting unrelated records.
    """

    API_BASE = "https://api.cloudflare.com/client/v4"

    def __init__(self):
        self.token = os.environ.get('CF_API_TOKEN')
        if not self.token:
            raise ValueError("CF_API_TOKEN not set")

        self.client = httpx.Client(
            headers={
                'Authorization': f'Bearer {self.token}',
                'Content-Type': 'application/json'
            },
            timeout=30
        )

        # Cache zone IDs
        self._zone_cache = {}

    def _request(self, method: str, endpoint: str, data: dict = None) -> dict:
        """Make API request with error handling."""
        url = f"{self.API_BASE}{endpoint}"

        if method == 'GET':
            resp = self.client.get(url, params=data)
        elif method == 'POST':
            resp = self.client.post(url, json=data)
        elif method == 'PUT':
            resp = self.client.put(url, json=data)
        elif method == 'PATCH':
            resp = self.client.patch(url, json=data)
        elif method == 'DELETE':
            resp = self.client.delete(url)
        else:
            raise ValueError(f"Unknown method: {method}")

        result = resp.json()

        if not result.get('success', False):
            errors = result.get('errors', [])
            error_msg = '; '.join(e.get('message', str(e)) for e in errors)
            raise Exception(f"Cloudflare API error: {error_msg}")

        return result

    # ─────────────────────────────────────────────────────────────
    # Zone Management
    # ─────────────────────────────────────────────────────────────

    def get_zone_id(self, domain: str) -> str:
        """Get zone ID for domain."""

        # Check cache
        if domain in self._zone_cache:
            return self._zone_cache[domain]

        # Extract root domain (handle subdomains)
        parts = domain.split('.')
        if len(parts) > 2:
            # Check for common second-level TLDs
            common_sld = ['co', 'com', 'org', 'net', 'gov', 'edu']
            if parts[-2] in common_sld:
                root = '.'.join(parts[-3:])
            else:
                root = '.'.join(parts[-2:])
        else:
            root = domain

        # Query API
        result = self._request('GET', '/zones', {'name': root})

        zones = result.get('result', [])
        if not zones:
            raise ValueError(f"Zone not found for domain: {domain}")

        zone_id = zones[0]['id']
        self._zone_cache[domain] = zone_id

        return zone_id

    def list_zones(self) -> list[dict]:
        """List all zones in account."""
        result = self._request('GET', '/zones', {'per_page': 50})
        return result.get('result', [])

    # ─────────────────────────────────────────────────────────────
    # DNS Record Operations
    # ─────────────────────────────────────────────────────────────

    def list_records(self, zone_id: str, record_type: str = None) -> list[DNSRecord]:
        """List all DNS records in zone."""

        params = {'per_page': 100}
        if record_type:
            params['type'] = record_type

        result = self._request('GET', f'/zones/{zone_id}/dns_records', params)

        return [DNSRecord.from_cf_response(r) for r in result.get('result', [])]

    def get_record(self, zone_id: str, record_id: str) -> Optional[DNSRecord]:
        """Get single DNS record by ID."""
        try:
            result = self._request('GET', f'/zones/{zone_id}/dns_records/{record_id}')
            return DNSRecord.from_cf_response(result['result'])
        except:
            return None

    def find_record(self, zone_id: str, record_type: str, name: str) -> Optional[DNSRecord]:
        """Find record by type and name."""

        params = {
            'type': record_type,
            'name': name,
            'per_page': 1
        }

        result = self._request('GET', f'/zones/{zone_id}/dns_records', params)
        records = result.get('result', [])

        if records:
            return DNSRecord.from_cf_response(records[0])
        return None

    def create_record(self, zone_id: str, record: DNSRecord) -> DNSRecord:
        """Create new DNS record."""

        data = record.to_dict()

        result = self._request('POST', f'/zones/{zone_id}/dns_records', data)

        return DNSRecord.from_cf_response(result['result'])

    def update_record(self, zone_id: str, record_id: str, record: DNSRecord) -> DNSRecord:
        """Update existing DNS record."""

        data = record.to_dict()

        result = self._request('PUT', f'/zones/{zone_id}/dns_records/{record_id}', data)

        return DNSRecord.from_cf_response(result['result'])

    def delete_record(self, zone_id: str, record_id: str) -> bool:
        """Delete DNS record."""
        try:
            self._request('DELETE', f'/zones/{zone_id}/dns_records/{record_id}')
            return True
        except:
            return False

    # ─────────────────────────────────────────────────────────────
    # High-Level Operations (used by Fabrik)
    # ─────────────────────────────────────────────────────────────

    def normalize_name(self, name: str, domain: str) -> str:
        """Convert @ to domain, ensure FQDN."""
        if name == '@':
            return domain
        if not name.endswith(domain):
            return f"{name}.{domain}"
        return name

    def plan(self, domain: str, desired: list[DNSRecord], zone_id: str = None) -> DNSDiff:
        """
        Compare desired records against current state.
        Returns diff showing what will change.

        Note: Only manages records in 'desired' list.
        Does NOT delete records not in desired (preserves mail, etc.)
        """

        zone_id = zone_id or self.get_zone_id(domain)

        # Get current records
        current_records = self.list_records(zone_id)

        # Index current by (type, name)
        current_map = {}
        for r in current_records:
            key = (r.type, r.name)
            current_map[key] = r

        to_create = []
        to_update = []
        unchanged = []

        for desired_record in desired:
            # Normalize name
            full_name = self.normalize_name(desired_record.name, domain)
            desired_record.name = full_name

            key = (desired_record.type, full_name)

            if key not in current_map:
                # Record doesn't exist, create it
                to_create.append(desired_record)
            else:
                current = current_map[key]
                # Check if update needed
                if (current.content != desired_record.content or
                    current.proxied != desired_record.proxied or
                    (desired_record.ttl != 1 and current.ttl != desired_record.ttl)):
                    to_update.append((current, desired_record))
                else:
                    unchanged.append(current)

        # Note: We do NOT populate to_delete
        # Fabrik only manages records it knows about
        # This prevents accidental deletion of mail/verification records

        return DNSDiff(
            to_create=to_create,
            to_update=to_update,
            to_delete=[],  # Intentionally empty for safety
            unchanged=unchanged
        )

    def apply(self, domain: str, desired: list[DNSRecord], zone_id: str = None) -> DNSResult:
        """
        Apply desired DNS state.

        Creates missing records, updates changed records.
        Does NOT delete records not in desired list (safe by default).
        """

        zone_id = zone_id or self.get_zone_id(domain)

        diff = self.plan(domain, desired, zone_id)

        if not diff.has_changes:
            return DNSResult(status='unchanged', changes=diff)

        created = 0
        updated = 0
        errors = []

        # Create new records
        for record in diff.to_create:
            try:
                self.create_record(zone_id, record)
                created += 1
            except Exception as e:
                errors.append(f"Create {record.type} {record.name}: {e}")

        # Update existing records
        for current, desired_record in diff.to_update:
            try:
                self.update_record(zone_id, current.record_id, desired_record)
                updated += 1
            except Exception as e:
                errors.append(f"Update {desired_record.type} {desired_record.name}: {e}")

        if errors:
            return DNSResult(
                status='error',
                changes=diff,
                created=created,
                updated=updated,
                error='; '.join(errors)
            )

        return DNSResult(
            status='applied',
            changes=diff,
            created=created,
            updated=updated
        )

    def delete_managed_records(
        self,
        domain: str,
        records_to_delete: list[DNSRecord],
        zone_id: str = None
    ) -> int:
        """
        Explicitly delete specific records.

        Use this only when you intentionally want to remove records.
        """
        zone_id = zone_id or self.get_zone_id(domain)

        deleted = 0
        for record in records_to_delete:
            full_name = self.normalize_name(record.name, domain)
            existing = self.find_record(zone_id, record.type, full_name)

            if existing and existing.record_id:
                if self.delete_record(zone_id, existing.record_id):
                    deleted += 1

        return deleted

    # ─────────────────────────────────────────────────────────────
    # Export/Import for Migration
    # ─────────────────────────────────────────────────────────────

    def export_zone(self, domain: str, zone_id: str = None) -> list[dict]:
        """Export all records for backup/migration."""
        zone_id = zone_id or self.get_zone_id(domain)
        records = self.list_records(zone_id)

        return [
            {
                'type': r.type,
                'name': r.name,
                'content': r.content,
                'ttl': r.ttl,
                'priority': r.priority,
                'proxied': r.proxied
            }
            for r in records
        ]

    def import_records(
        self,
        domain: str,
        records: list[dict],
        zone_id: str = None,
        skip_existing: bool = True
    ) -> dict:
        """Import records (e.g., from Namecheap export)."""

        zone_id = zone_id or self.get_zone_id(domain)

        created = 0
        skipped = 0
        errors = []

        for record_data in records:
            record = DNSRecord(
                type=record_data['type'],
                name=self.normalize_name(record_data['name'], domain),
                content=record_data['content'],
                ttl=record_data.get('ttl', 1),
                priority=record_data.get('priority'),
                proxied=record_data.get('proxied', False)
            )

            # Check if exists
            existing = self.find_record(zone_id, record.type, record.name)

            if existing:
                if skip_existing:
                    skipped += 1
                    continue
                else:
                    # Update
                    try:
                        self.update_record(zone_id, existing.record_id, record)
                        created += 1
                    except Exception as e:
                        errors.append(f"{record.type} {record.name}: {e}")
            else:
                # Create
                try:
                    self.create_record(zone_id, record)
                    created += 1
                except Exception as e:
                    errors.append(f"{record.type} {record.name}: {e}")

        return {
            'created': created,
            'skipped': skipped,
            'errors': errors
        }
```

**Test:**

```bash
cd ~/projects/fabrik
source secrets/platform.env

python3 << 'EOF'
from compiler.dns_cloudflare import CloudflareDNS

cf = CloudflareDNS()

# List zones
zones = cf.list_zones()
print(f"Found {len(zones)} zones:")
for z in zones:
    print(f"  {z['name']} ({z['id']})")

# If you have a zone, list its records
if zones:
    zone_id = zones[0]['id']
    domain = zones[0]['name']
    records = cf.list_records(zone_id)
    print(f"\nRecords for {domain}:")
    for r in records:
        proxy = "🟠" if r.proxied else "⚪"
        print(f"  {proxy} {r.type:6} {r.name:30} → {r.content}")
EOF
```

**Time:** 2 hours

---

### Step 3: Add Domain to Cloudflare

**Why:** Before using Cloudflare DNS, the domain must be added to your Cloudflare account.

**Steps:**

**3.1: Add Site in Cloudflare Dashboard**

1. Log into Cloudflare Dashboard
2. Click "Add a Site"
3. Enter your domain: `yourdomain.com`
4. Select Free plan
5. Cloudflare will scan existing DNS records

**3.2: Review Imported Records**

Cloudflare automatically imports records from current DNS. Verify:
- All A records present
- MX records for email
- TXT records (SPF, DKIM, verification)
- CNAME records

**3.3: Get Zone ID**

1. Go to domain's Overview page
2. Scroll down to "API" section on right side
3. Copy "Zone ID"
4. Save it:

```bash
# Add to secrets/platform.env
echo "CF_ZONE_YOURDOMAIN=zone_id_here" >> secrets/platform.env
```

**3.4: Note Cloudflare Nameservers**

Cloudflare will show two nameservers like:
```
aria.ns.cloudflare.com
bob.ns.cloudflare.com
```

Don't change nameservers yet — we'll do that in Step 5.

**Time:** 15 minutes

---

### Step 4: Test Cloudflare DNS (Before Migration)

**Why:** Test the driver works before changing nameservers.

**Code:**

```python
# Test creating a record (won't resolve until nameservers change)

from compiler.dns_cloudflare import CloudflareDNS, DNSRecord

cf = CloudflareDNS()

zone_id = os.environ.get('CF_ZONE_YOURDOMAIN')
domain = 'yourdomain.com'

# Create a test record
test_record = DNSRecord(
    type='TXT',
    name='fabrik-test',
    content='Fabrik DNS test',
    proxied=False
)

result = cf.apply(domain, [test_record], zone_id)
print(f"Result: {result.status}")
print(f"Created: {result.created}")

# Verify it exists
records = cf.list_records(zone_id, record_type='TXT')
for r in records:
    if 'fabrik-test' in r.name:
        print(f"✓ Test record created: {r.name} = {r.content}")

# Clean up
cf.delete_managed_records(domain, [test_record], zone_id)
print("✓ Test record deleted")
```

**Time:** 30 minutes

---

### Step 5: Migrate Nameservers (The Actual Migration)

**Why:** This is the point of no return — DNS resolution switches from Namecheap to Cloudflare.

**Steps:**

**5.1: Document Current State**

Before changing anything, export current DNS state:

```bash
# Export from Namecheap (using our existing driver)
python3 << 'EOF'
from compiler.dns_namecheap import NamecheapDNS
import yaml

nc = NamecheapDNS()
records = nc.export('yourdomain.com')

# Save backup
with open('dns/backup/yourdomain.com-namecheap.yaml', 'w') as f:
    yaml.dump([r.to_dict() for r in records], f)

print(f"Exported {len(records)} records")
EOF
```

**5.2: Verify Cloudflare Has All Records**

Compare Namecheap export with Cloudflare import:

```bash
python3 << 'EOF'
import yaml
from compiler.dns_cloudflare import CloudflareDNS
import os

# Load Namecheap backup
with open('dns/backup/yourdomain.com-namecheap.yaml') as f:
    nc_records = yaml.safe_load(f)

# Get Cloudflare records
cf = CloudflareDNS()
zone_id = os.environ.get('CF_ZONE_YOURDOMAIN')
cf_records = cf.list_records(zone_id)

print("Namecheap records:")
for r in nc_records:
    print(f"  {r['type']:6} {r['name']:20} → {r['content']}")

print("\nCloudflare records:")
for r in cf_records:
    print(f"  {r.type:6} {r.name:20} → {r.content}")

# Check for missing
nc_set = {(r['type'], r['name']) for r in nc_records}
cf_set = {(r.type, r.name.replace('.yourdomain.com', '').replace('yourdomain.com', '@')) for r in cf_records}

missing = nc_set - cf_set
if missing:
    print(f"\n⚠ Missing in Cloudflare: {missing}")
else:
    print("\n✓ All records present in Cloudflare")
EOF
```

**5.3: Change Nameservers at Namecheap**

1. Log into Namecheap
2. Go to Domain List → Manage (for your domain)
3. Under "Nameservers", select "Custom DNS"
4. Enter Cloudflare nameservers:
   ```
   aria.ns.cloudflare.com
   bob.ns.cloudflare.com
   ```
5. Save changes

**5.4: Wait for Propagation**

- Cloudflare will show "Pending Nameserver Update" initially
- Propagation takes 10 minutes to 48 hours (usually <1 hour)
- You'll get email from Cloudflare when active

**5.5: Verify Migration**

```bash
# Check nameservers
dig NS yourdomain.com +short
# Should show: aria.ns.cloudflare.com, bob.ns.cloudflare.com

# Check A record resolves
dig A yourdomain.com +short
# Should show your VPS IP

# Check site loads
curl -I https://yourdomain.com
```

**Time:** 1 hour (mostly waiting for propagation)

---

### Step 6: Update Fabrik Specs to Use Cloudflare

**Why:** Now that the domain is on Cloudflare, update specs to use the new driver.

**Update spec format:**

```yaml
# specs/my-site/spec.yaml

dns:
  provider: cloudflare        # Changed from 'namecheap'
  zone_id: ${CF_ZONE_YOURDOMAIN}
  proxy: true                 # Enable CDN (orange cloud)
  records:
    - type: A
      name: "@"
      content: ${VPS_IP}
      proxied: true
    - type: A
      name: "www"
      content: ${VPS_IP}
      proxied: true
```

**Update apply.py to use correct driver:**

```python
# In cli/apply.py - update DNS section

def get_dns_driver(provider: str):
    """Get DNS driver based on provider."""
    if provider == 'cloudflare':
        from compiler.dns_cloudflare import CloudflareDNS
        return CloudflareDNS()
    elif provider == 'namecheap':
        from compiler.dns_namecheap import NamecheapDNS
        return NamecheapDNS()
    else:
        raise ValueError(f"Unknown DNS provider: {provider}")

# In the apply function:
if spec.dns and spec.domain:
    click.echo(f"[{timestamp()}] Applying DNS ({spec.dns.provider})...")

    dns = get_dns_driver(spec.dns.provider)

    vps_ip = os.environ.get('VPS_IP', '')

    # Build records from spec
    desired_records = []
    for r in spec.dns.records:
        if spec.dns.provider == 'cloudflare':
            from compiler.dns_cloudflare import DNSRecord as CFRecord
            desired_records.append(CFRecord(
                type=r.type,
                name=r.name,
                content=r.content.replace('${VPS_IP}', vps_ip),
                ttl=r.ttl if hasattr(r, 'ttl') else 1,
                proxied=getattr(r, 'proxied', spec.dns.proxy if hasattr(spec.dns, 'proxy') else False)
            ))
        else:
            from compiler.dns_namecheap import DNSRecord as NCRecord
            desired_records.append(NCRecord(
                type=r.type,
                name=r.name,
                content=r.content.replace('${VPS_IP}', vps_ip),
                ttl=r.ttl if hasattr(r, 'ttl') else 1800
            ))

    # For Cloudflare, pass zone_id
    if spec.dns.provider == 'cloudflare':
        zone_id = os.environ.get(spec.dns.zone_id.replace('${', '').replace('}', ''))
        dns_result = dns.apply(spec.domain, desired_records, zone_id)
    else:
        dns_result = dns.apply(spec.domain, desired_records)

    if dns_result.status == "error":
        click.echo(f"         ✗ DNS failed: {dns_result.error}")
        raise click.Abort()

    click.echo(f"         → {dns_result.created} created, {dns_result.updated} updated")
```

**Time:** 1 hour

---

### Step 7: Configure SSL Mode

**Why:** Cloudflare can handle SSL in different modes. We want "Full (Strict)" for maximum security — encryption end-to-end with validated origin certificate.

**Options:**

| Mode | Description | Recommendation |
|------|-------------|----------------|
| Off | No HTTPS | Never use |
| Flexible | HTTPS to Cloudflare, HTTP to origin | Insecure, avoid |
| Full | HTTPS end-to-end, but origin cert not validated | Acceptable |
| Full (Strict) | HTTPS end-to-end, origin cert validated | **Recommended** |

**Since Coolify/Traefik already provides valid Let's Encrypt certificates, use Full (Strict).**

**Code:**

```python
# compiler/cloudflare_settings.py

import os
import httpx

class CloudflareSettings:
    """Manage Cloudflare zone settings."""

    API_BASE = "https://api.cloudflare.com/client/v4"

    def __init__(self):
        self.token = os.environ.get('CF_API_TOKEN')
        self.client = httpx.Client(
            headers={
                'Authorization': f'Bearer {self.token}',
                'Content-Type': 'application/json'
            },
            timeout=30
        )

    def _patch_setting(self, zone_id: str, setting: str, value) -> bool:
        """Update a zone setting."""
        url = f"{self.API_BASE}/zones/{zone_id}/settings/{setting}"
        resp = self.client.patch(url, json={'value': value})
        return resp.json().get('success', False)

    def _get_setting(self, zone_id: str, setting: str):
        """Get a zone setting."""
        url = f"{self.API_BASE}/zones/{zone_id}/settings/{setting}"
        resp = self.client.get(url)
        return resp.json().get('result', {}).get('value')

    # ─────────────────────────────────────────────────────────────
    # SSL Settings
    # ─────────────────────────────────────────────────────────────

    def set_ssl_mode(self, zone_id: str, mode: str = 'full') -> bool:
        """
        Set SSL mode.

        Options: off, flexible, full, strict
        """
        return self._patch_setting(zone_id, 'ssl', mode)

    def set_always_https(self, zone_id: str, enabled: bool = True) -> bool:
        """Enable/disable Always Use HTTPS."""
        return self._patch_setting(zone_id, 'always_use_https', 'on' if enabled else 'off')

    def set_min_tls_version(self, zone_id: str, version: str = '1.2') -> bool:
        """Set minimum TLS version (1.0, 1.1, 1.2, 1.3)."""
        return self._patch_setting(zone_id, 'min_tls_version', version)

    # ─────────────────────────────────────────────────────────────
    # Performance Settings
    # ─────────────────────────────────────────────────────────────

    def set_brotli(self, zone_id: str, enabled: bool = True) -> bool:
        """Enable/disable Brotli compression."""
        return self._patch_setting(zone_id, 'brotli', 'on' if enabled else 'off')

    def set_early_hints(self, zone_id: str, enabled: bool = True) -> bool:
        """Enable/disable Early Hints."""
        return self._patch_setting(zone_id, 'early_hints', 'on' if enabled else 'off')

    def set_http3(self, zone_id: str, enabled: bool = True) -> bool:
        """Enable/disable HTTP/3."""
        return self._patch_setting(zone_id, 'http3', 'on' if enabled else 'off')

    # ─────────────────────────────────────────────────────────────
    # Security Settings
    # ─────────────────────────────────────────────────────────────

    def set_security_level(self, zone_id: str, level: str = 'medium') -> bool:
        """
        Set security level.

        Options: off, essentially_off, low, medium, high, under_attack
        """
        return self._patch_setting(zone_id, 'security_level', level)

    def set_browser_check(self, zone_id: str, enabled: bool = True) -> bool:
        """Enable/disable Browser Integrity Check."""
        return self._patch_setting(zone_id, 'browser_check', 'on' if enabled else 'off')

    # ─────────────────────────────────────────────────────────────
    # Caching Settings
    # ─────────────────────────────────────────────────────────────

    def set_cache_level(self, zone_id: str, level: str = 'aggressive') -> bool:
        """
        Set cache level.

        Options: bypass, basic, simplified, aggressive
        """
        return self._patch_setting(zone_id, 'cache_level', level)

    def set_browser_cache_ttl(self, zone_id: str, ttl: int = 14400) -> bool:
        """Set browser cache TTL in seconds."""
        return self._patch_setting(zone_id, 'browser_cache_ttl', ttl)

    # ─────────────────────────────────────────────────────────────
    # Apply Standard Configuration
    # ─────────────────────────────────────────────────────────────

    def apply_standard_config(self, zone_id: str) -> dict:
        """Apply standard configuration for WordPress sites."""

        results = {}

        # SSL
        results['ssl'] = self.set_ssl_mode(zone_id, 'strict')
        results['always_https'] = self.set_always_https(zone_id, True)
        results['min_tls'] = self.set_min_tls_version(zone_id, '1.2')

        # Performance
        results['brotli'] = self.set_brotli(zone_id, True)
        results['http3'] = self.set_http3(zone_id, True)
        results['early_hints'] = self.set_early_hints(zone_id, True)

        # Security
        results['security_level'] = self.set_security_level(zone_id, 'medium')
        results['browser_check'] = self.set_browser_check(zone_id, True)

        # Caching
        results['cache_level'] = self.set_cache_level(zone_id, 'aggressive')
        results['browser_cache_ttl'] = self.set_browser_cache_ttl(zone_id, 14400)  # 4 hours

        return results
```

**Apply configuration:**

```bash
python3 << 'EOF'
from compiler.cloudflare_settings import CloudflareSettings
import os

cf = CloudflareSettings()
zone_id = os.environ.get('CF_ZONE_YOURDOMAIN')

results = cf.apply_standard_config(zone_id)

print("Applied settings:")
for setting, success in results.items():
    status = "✓" if success else "✗"
    print(f"  {status} {setting}")
EOF
```

**Time:** 1 hour

---

### Step 8: Configure WAF Rules for WordPress

**Why:** WordPress is a common attack target. Cloudflare's free WAF can block common attacks.

**Code:**

```python
# compiler/cloudflare_waf.py

import os
import httpx
from typing import Optional

class CloudflareWAF:
    """Manage Cloudflare WAF rules."""

    API_BASE = "https://api.cloudflare.com/client/v4"

    def __init__(self):
        self.token = os.environ.get('CF_API_TOKEN')
        self.client = httpx.Client(
            headers={
                'Authorization': f'Bearer {self.token}',
                'Content-Type': 'application/json'
            },
            timeout=30
        )

    def _request(self, method: str, endpoint: str, data: dict = None):
        url = f"{self.API_BASE}{endpoint}"

        if method == 'GET':
            resp = self.client.get(url, params=data)
        elif method == 'POST':
            resp = self.client.post(url, json=data)
        elif method == 'PUT':
            resp = self.client.put(url, json=data)
        elif method == 'DELETE':
            resp = self.client.delete(url)

        return resp.json()

    # ─────────────────────────────────────────────────────────────
    # Firewall Rules (Custom Rules)
    # ─────────────────────────────────────────────────────────────

    def create_firewall_rule(
        self,
        zone_id: str,
        description: str,
        expression: str,
        action: str  # block, challenge, js_challenge, managed_challenge, allow, skip
    ) -> dict:
        """Create a custom firewall rule."""

        # First create the filter
        filter_result = self._request('POST', f'/zones/{zone_id}/filters', {
            'expression': expression,
            'description': description
        })

        if not filter_result.get('success'):
            return filter_result

        filter_id = filter_result['result'][0]['id']

        # Then create the firewall rule using the filter
        rule_result = self._request('POST', f'/zones/{zone_id}/firewall/rules', [{
            'filter': {'id': filter_id},
            'action': action,
            'description': description
        }])

        return rule_result

    def list_firewall_rules(self, zone_id: str) -> list:
        """List all firewall rules."""
        result = self._request('GET', f'/zones/{zone_id}/firewall/rules')
        return result.get('result', [])

    def delete_firewall_rule(self, zone_id: str, rule_id: str) -> bool:
        """Delete a firewall rule."""
        result = self._request('DELETE', f'/zones/{zone_id}/firewall/rules/{rule_id}')
        return result.get('success', False)

    # ─────────────────────────────────────────────────────────────
    # WordPress-Specific Rules
    # ─────────────────────────────────────────────────────────────

    def apply_wordpress_rules(self, zone_id: str) -> dict:
        """Apply standard WordPress security rules."""

        results = {}

        rules = [
            {
                'description': 'Block xmlrpc.php access',
                'expression': '(http.request.uri.path eq "/xmlrpc.php")',
                'action': 'block'
            },
            {
                'description': 'Block wp-config.php access',
                'expression': '(http.request.uri.path contains "wp-config.php")',
                'action': 'block'
            },
            {
                'description': 'Block .htaccess access',
                'expression': '(http.request.uri.path contains ".htaccess")',
                'action': 'block'
            },
            {
                'description': 'Challenge wp-login brute force',
                'expression': '(http.request.uri.path eq "/wp-login.php") and (cf.threat_score gt 10)',
                'action': 'managed_challenge'
            },
            {
                'description': 'Block readme.html access',
                'expression': '(http.request.uri.path eq "/readme.html")',
                'action': 'block'
            },
            {
                'description': 'Block debug.log access',
                'expression': '(http.request.uri.path contains "debug.log")',
                'action': 'block'
            },
            {
                'description': 'Block PHP in uploads',
                'expression': '(http.request.uri.path contains "/wp-content/uploads/") and (http.request.uri.path contains ".php")',
                'action': 'block'
            },
        ]

        for rule in rules:
            try:
                result = self.create_firewall_rule(
                    zone_id,
                    rule['description'],
                    rule['expression'],
                    rule['action']
                )
                results[rule['description']] = result.get('success', False)
            except Exception as e:
                results[rule['description']] = f"Error: {e}"

        return results

    # ─────────────────────────────────────────────────────────────
    # Rate Limiting
    # ─────────────────────────────────────────────────────────────

    def create_rate_limit(
        self,
        zone_id: str,
        description: str,
        match_url: str,
        threshold: int,
        period: int,  # seconds
        action: str = 'block',
        timeout: int = 60
    ) -> dict:
        """Create a rate limiting rule."""

        result = self._request('POST', f'/zones/{zone_id}/rate_limits', {
            'description': description,
            'match': {
                'request': {
                    'url_pattern': match_url,
                    'schemes': ['HTTP', 'HTTPS'],
                    'methods': ['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'HEAD']
                },
                'response': {}
            },
            'threshold': threshold,
            'period': period,
            'action': {
                'mode': action,
                'timeout': timeout
            }
        })

        return result

    def apply_wordpress_rate_limits(self, zone_id: str) -> dict:
        """Apply rate limiting for WordPress."""

        results = {}

        # Rate limit login page
        results['login_rate_limit'] = self.create_rate_limit(
            zone_id,
            description='Rate limit wp-login',
            match_url='*wp-login.php*',
            threshold=5,     # 5 requests
            period=60,       # per minute
            action='block',
            timeout=300      # block for 5 minutes
        ).get('success', False)

        # Rate limit xmlrpc (if not blocked)
        results['xmlrpc_rate_limit'] = self.create_rate_limit(
            zone_id,
            description='Rate limit xmlrpc',
            match_url='*xmlrpc.php*',
            threshold=2,
            period=60,
            action='block',
            timeout=3600
        ).get('success', False)

        # Rate limit admin-ajax
        results['ajax_rate_limit'] = self.create_rate_limit(
            zone_id,
            description='Rate limit admin-ajax',
            match_url='*admin-ajax.php*',
            threshold=100,
            period=60,
            action='challenge'
        ).get('success', False)

        return results
```

**Apply WAF rules:**

```bash
python3 << 'EOF'
from compiler.cloudflare_waf import CloudflareWAF
import os

waf = CloudflareWAF()
zone_id = os.environ.get('CF_ZONE_YOURDOMAIN')

print("Applying WordPress WAF rules...")
results = waf.apply_wordpress_rules(zone_id)

for rule, success in results.items():
    status = "✓" if success else "✗"
    print(f"  {status} {rule}")

print("\nApplying rate limits...")
rate_results = waf.apply_wordpress_rate_limits(zone_id)

for rule, success in rate_results.items():
    status = "✓" if success else "✗"
    print(f"  {status} {rule}")
EOF
```

**Time:** 1 hour

---

### Step 9: Configure Cache Rules

**Why:** Proper caching improves performance dramatically. WordPress has different caching needs for static assets vs. dynamic content vs. admin.

**Code:**

```python
# compiler/cloudflare_cache.py

import os
import httpx

class CloudflareCache:
    """Manage Cloudflare cache rules."""

    API_BASE = "https://api.cloudflare.com/client/v4"

    def __init__(self):
        self.token = os.environ.get('CF_API_TOKEN')
        self.client = httpx.Client(
            headers={
                'Authorization': f'Bearer {self.token}',
                'Content-Type': 'application/json'
            },
            timeout=30
        )

    def _request(self, method: str, endpoint: str, data: dict = None):
        url = f"{self.API_BASE}{endpoint}"

        if method == 'GET':
            resp = self.client.get(url, params=data)
        elif method == 'POST':
            resp = self.client.post(url, json=data)
        elif method == 'PUT':
            resp = self.client.put(url, json=data)
        elif method == 'PATCH':
            resp = self.client.patch(url, json=data)
        elif method == 'DELETE':
            resp = self.client.delete(url)

        return resp.json()

    # ─────────────────────────────────────────────────────────────
    # Page Rules (legacy, but still useful on free tier)
    # ─────────────────────────────────────────────────────────────

    def create_page_rule(
        self,
        zone_id: str,
        url_pattern: str,
        actions: list[dict],
        priority: int = 1,
        status: str = 'active'
    ) -> dict:
        """
        Create a page rule.

        Free tier: 3 page rules
        """

        result = self._request('POST', f'/zones/{zone_id}/pagerules', {
            'targets': [
                {
                    'target': 'url',
                    'constraint': {
                        'operator': 'matches',
                        'value': url_pattern
                    }
                }
            ],
            'actions': actions,
            'priority': priority,
            'status': status
        })

        return result

    def list_page_rules(self, zone_id: str) -> list:
        """List all page rules."""
        result = self._request('GET', f'/zones/{zone_id}/pagerules')
        return result.get('result', [])

    def delete_page_rule(self, zone_id: str, rule_id: str) -> bool:
        """Delete a page rule."""
        result = self._request('DELETE', f'/zones/{zone_id}/pagerules/{rule_id}')
        return result.get('success', False)

    # ─────────────────────────────────────────────────────────────
    # WordPress Cache Configuration
    # ─────────────────────────────────────────────────────────────

    def apply_wordpress_cache_rules(self, zone_id: str, domain: str) -> dict:
        """
        Apply standard WordPress cache configuration.

        Uses 3 page rules (free tier limit):
        1. Bypass cache for admin
        2. Cache static assets aggressively
        3. Standard cache for everything else
        """

        results = {}

        # Rule 1: Bypass cache for wp-admin and wp-login
        results['admin_bypass'] = self.create_page_rule(
            zone_id,
            url_pattern=f'*{domain}/wp-admin/*',
            actions=[
                {'id': 'cache_level', 'value': 'bypass'},
                {'id': 'disable_apps', 'value': True},
                {'id': 'disable_performance', 'value': True}
            ],
            priority=1
        ).get('success', False)

        # Rule 2: Cache static assets aggressively
        results['static_cache'] = self.create_page_rule(
            zone_id,
            url_pattern=f'*{domain}/wp-content/*',
            actions=[
                {'id': 'cache_level', 'value': 'cache_everything'},
                {'id': 'edge_cache_ttl', 'value': 2592000},  # 30 days
                {'id': 'browser_cache_ttl', 'value': 604800}  # 7 days
            ],
            priority=2
        ).get('success', False)

        # Rule 3: Bypass cache for logged-in users (using cookie)
        results['logged_in_bypass'] = self.create_page_rule(
            zone_id,
            url_pattern=f'*{domain}/*',
            actions=[
                {'id': 'bypass_cache_on_cookie', 'value': 'wordpress_logged_in.*|wp-postpass_.*'}
            ],
            priority=3
        ).get('success', False)

        return results

    # ─────────────────────────────────────────────────────────────
    # Cache Purge
    # ─────────────────────────────────────────────────────────────

    def purge_everything(self, zone_id: str) -> bool:
        """Purge all cached content."""
        result = self._request('POST', f'/zones/{zone_id}/purge_cache', {
            'purge_everything': True
        })
        return result.get('success', False)

    def purge_urls(self, zone_id: str, urls: list[str]) -> bool:
        """Purge specific URLs."""
        result = self._request('POST', f'/zones/{zone_id}/purge_cache', {
            'files': urls
        })
        return result.get('success', False)

    def purge_by_prefix(self, zone_id: str, prefixes: list[str]) -> bool:
        """Purge by URL prefix (Enterprise only, will fail on free tier)."""
        result = self._request('POST', f'/zones/{zone_id}/purge_cache', {
            'prefixes': prefixes
        })
        return result.get('success', False)
```

**Apply cache rules:**

```bash
python3 << 'EOF'
from compiler.cloudflare_cache import CloudflareCache
import os

cache = CloudflareCache()
zone_id = os.environ.get('CF_ZONE_YOURDOMAIN')
domain = 'yourdomain.com'

print("Applying WordPress cache rules...")
results = cache.apply_wordpress_cache_rules(zone_id, domain)

for rule, success in results.items():
    status = "✓" if success else "✗"
    print(f"  {status} {rule}")
EOF
```

**Time:** 1 hour

---

### Step 10: CLI Commands for DNS Management

**Why:** Expose DNS operations through CLI for easy access.

**Code:**

```python
# cli/dns.py

import click
import os
from pathlib import Path
import yaml

def load_env():
    """Load environment."""
    env_file = Path("secrets/platform.env")
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                if '=' in line and not line.startswith('#'):
                    k, v = line.strip().split('=', 1)
                    os.environ[k] = v

@click.group()
def dns():
    """DNS management commands."""
    load_env()

# ─────────────────────────────────────────────────────────────
# Zone Management
# ─────────────────────────────────────────────────────────────

@dns.command('zones')
@click.option('--provider', type=click.Choice(['cloudflare', 'namecheap']), default='cloudflare')
def list_zones(provider):
    """List all DNS zones."""

    if provider == 'cloudflare':
        from compiler.dns_cloudflare import CloudflareDNS
        cf = CloudflareDNS()
        zones = cf.list_zones()

        click.echo(f"\nCloudflare zones:")
        click.echo("-" * 50)
        for z in zones:
            click.echo(f"  {z['name']:30} {z['id']}")
    else:
        click.echo("Namecheap does not support listing zones via API")

# ─────────────────────────────────────────────────────────────
# Record Management
# ─────────────────────────────────────────────────────────────

@dns.command('records')
@click.argument('domain')
@click.option('--provider', type=click.Choice(['cloudflare', 'namecheap']), default='cloudflare')
@click.option('--type', 'record_type', help='Filter by record type (A, CNAME, MX, TXT)')
def list_records(domain, provider, record_type):
    """List DNS records for a domain."""

    if provider == 'cloudflare':
        from compiler.dns_cloudflare import CloudflareDNS
        cf = CloudflareDNS()

        zone_id = cf.get_zone_id(domain)
        records = cf.list_records(zone_id, record_type=record_type)

        click.echo(f"\nRecords for {domain} (Cloudflare):")
        click.echo("-" * 70)

        for r in records:
            proxy = "🟠" if r.proxied else "⚪"
            click.echo(f"  {proxy} {r.type:6} {r.name:35} → {r.content}")

    else:
        from compiler.dns_namecheap import NamecheapDNS
        nc = NamecheapDNS()

        records = nc.export(domain)

        click.echo(f"\nRecords for {domain} (Namecheap):")
        click.echo("-" * 60)

        for r in records:
            click.echo(f"  {r.type:6} {r.name:20} → {r.content}")

@dns.command('export')
@click.argument('domain')
@click.option('--provider', type=click.Choice(['cloudflare', 'namecheap']), default='cloudflare')
@click.option('--output', type=click.Path(), help='Output file (default: dns/backup/<domain>.yaml)')
def export_records(domain, provider, output):
    """Export DNS records to YAML file."""

    if not output:
        Path('dns/backup').mkdir(parents=True, exist_ok=True)
        output = f'dns/backup/{domain}-{provider}.yaml'

    if provider == 'cloudflare':
        from compiler.dns_cloudflare import CloudflareDNS
        cf = CloudflareDNS()
        records = cf.export_zone(domain)
    else:
        from compiler.dns_namecheap import NamecheapDNS
        nc = NamecheapDNS()
        records = [r.to_dict() for r in nc.export(domain)]

    with open(output, 'w') as f:
        yaml.dump(records, f, default_flow_style=False)

    click.echo(f"✓ Exported {len(records)} records to {output}")

@dns.command('add')
@click.argument('domain')
@click.option('--type', 'record_type', required=True, type=click.Choice(['A', 'AAAA', 'CNAME', 'MX', 'TXT']))
@click.option('--name', required=True, help='Record name (@ for root)')
@click.option('--content', required=True, help='Record value')
@click.option('--proxy/--no-proxy', default=False, help='Enable Cloudflare proxy (CDN)')
@click.option('--provider', type=click.Choice(['cloudflare', 'namecheap']), default='cloudflare')
def add_record(domain, record_type, name, content, proxy, provider):
    """Add a DNS record."""

    if provider == 'cloudflare':
        from compiler.dns_cloudflare import CloudflareDNS, DNSRecord
        cf = CloudflareDNS()

        zone_id = cf.get_zone_id(domain)

        record = DNSRecord(
            type=record_type,
            name=name,
            content=content,
            proxied=proxy
        )

        result = cf.apply(domain, [record], zone_id)

        if result.status == 'applied':
            click.echo(f"✓ Created {record_type} {name} → {content}")
        else:
            click.echo(f"✗ Failed: {result.error}")

    else:
        click.echo("For Namecheap, use 'fabrik apply' to manage records safely")

@dns.command('delete')
@click.argument('domain')
@click.option('--type', 'record_type', required=True, type=click.Choice(['A', 'AAAA', 'CNAME', 'MX', 'TXT']))
@click.option('--name', required=True, help='Record name')
@click.option('--provider', type=click.Choice(['cloudflare']), default='cloudflare')
@click.confirmation_option(prompt='Are you sure you want to delete this record?')
def delete_record(domain, record_type, name, provider):
    """Delete a DNS record."""

    if provider == 'cloudflare':
        from compiler.dns_cloudflare import CloudflareDNS, DNSRecord
        cf = CloudflareDNS()

        zone_id = cf.get_zone_id(domain)

        record = DNSRecord(type=record_type, name=name, content='')
        deleted = cf.delete_managed_records(domain, [record], zone_id)

        if deleted > 0:
            click.echo(f"✓ Deleted {record_type} {name}")
        else:
            click.echo(f"✗ Record not found")

    else:
        click.echo("Delete not supported for Namecheap (would require replace-all)")

# ─────────────────────────────────────────────────────────────
# Migration
# ─────────────────────────────────────────────────────────────

@dns.command('migrate')
@click.argument('domain')
@click.option('--from-provider', 'from_prov', type=click.Choice(['namecheap']), default='namecheap')
@click.option('--to-provider', 'to_prov', type=click.Choice(['cloudflare']), default='cloudflare')
@click.option('--zone-id', help='Cloudflare zone ID (if already added)')
def migrate(domain, from_prov, to_prov, zone_id):
    """Migrate DNS records from one provider to another."""

    click.echo(f"Migrating {domain} from {from_prov} to {to_prov}")

    # Export from source
    click.echo(f"\n1. Exporting records from {from_prov}...")

    from compiler.dns_namecheap import NamecheapDNS
    nc = NamecheapDNS()
    records = [r.to_dict() for r in nc.export(domain)]

    click.echo(f"   Found {len(records)} records")

    # Save backup
    Path('dns/backup').mkdir(parents=True, exist_ok=True)
    backup_file = f'dns/backup/{domain}-pre-migration.yaml'
    with open(backup_file, 'w') as f:
        yaml.dump(records, f)
    click.echo(f"   Backup saved: {backup_file}")

    # Import to destination
    click.echo(f"\n2. Importing records to {to_prov}...")

    from compiler.dns_cloudflare import CloudflareDNS
    cf = CloudflareDNS()

    if not zone_id:
        try:
            zone_id = cf.get_zone_id(domain)
        except:
            click.echo(f"   ✗ Domain not found in Cloudflare. Add it first at dash.cloudflare.com")
            raise click.Abort()

    result = cf.import_records(domain, records, zone_id)

    click.echo(f"   Created: {result['created']}")
    click.echo(f"   Skipped (already exist): {result['skipped']}")

    if result['errors']:
        click.echo(f"   Errors:")
        for err in result['errors']:
            click.echo(f"     ✗ {err}")

    click.echo(f"""
3. Next steps:
   a. Verify records in Cloudflare dashboard
   b. Update nameservers at Namecheap to Cloudflare's nameservers
   c. Wait for propagation (up to 48 hours)
   d. Update specs to use provider: cloudflare
""")

# ─────────────────────────────────────────────────────────────
# Cache/Security Configuration
# ─────────────────────────────────────────────────────────────

@dns.command('configure')
@click.argument('domain')
@click.option('--wordpress', is_flag=True, help='Apply WordPress-optimized configuration')
@click.option('--waf/--no-waf', default=True, help='Apply WAF rules')
@click.option('--cache/--no-cache', default=True, help='Apply cache rules')
def configure(domain, wordpress, waf, cache):
    """Apply Cloudflare configuration for a domain."""

    from compiler.dns_cloudflare import CloudflareDNS
    cf = CloudflareDNS()
    zone_id = cf.get_zone_id(domain)

    click.echo(f"\nConfiguring {domain} (Zone: {zone_id})")

    # Base settings
    click.echo("\n1. Applying base settings...")
    from compiler.cloudflare_settings import CloudflareSettings
    settings = CloudflareSettings()
    results = settings.apply_standard_config(zone_id)

    for setting, success in results.items():
        status = "✓" if success else "✗"
        click.echo(f"   {status} {setting}")

    # WAF rules
    if waf and wordpress:
        click.echo("\n2. Applying WordPress WAF rules...")
        from compiler.cloudflare_waf import CloudflareWAF
        waf_mgr = CloudflareWAF()
        waf_results = waf_mgr.apply_wordpress_rules(zone_id)

        for rule, success in waf_results.items():
            status = "✓" if success else "✗"
            click.echo(f"   {status} {rule}")

        click.echo("\n3. Applying rate limits...")
        rate_results = waf_mgr.apply_wordpress_rate_limits(zone_id)

        for rule, success in rate_results.items():
            status = "✓" if success else "✗"
            click.echo(f"   {status} {rule}")

    # Cache rules
    if cache and wordpress:
        click.echo("\n4. Applying cache rules...")
        from compiler.cloudflare_cache import CloudflareCache
        cache_mgr = CloudflareCache()
        cache_results = cache_mgr.apply_wordpress_cache_rules(zone_id, domain)

        for rule, success in cache_results.items():
            status = "✓" if success else "✗"
            click.echo(f"   {status} {rule}")

    click.echo(f"\n✓ Configuration complete for {domain}")

@dns.command('purge-cache')
@click.argument('domain')
@click.option('--all', 'purge_all', is_flag=True, help='Purge everything')
@click.option('--url', multiple=True, help='Specific URLs to purge')
def purge_cache(domain, purge_all, url):
    """Purge Cloudflare cache."""

    from compiler.dns_cloudflare import CloudflareDNS
    from compiler.cloudflare_cache import CloudflareCache

    cf = CloudflareDNS()
    zone_id = cf.get_zone_id(domain)

    cache = CloudflareCache()

    if purge_all:
        if cache.purge_everything(zone_id):
            click.echo(f"✓ Purged all cache for {domain}")
        else:
            click.echo(f"✗ Failed to purge cache")
    elif url:
        if cache.purge_urls(zone_id, list(url)):
            click.echo(f"✓ Purged {len(url)} URLs")
        else:
            click.echo(f"✗ Failed to purge URLs")
    else:
        click.echo("Specify --all or --url")

if __name__ == '__main__':
    dns()
```

**Update main CLI:**

```python
# cli/main.py - add dns commands

from cli.dns import dns

cli.add_command(dns)
```

**Time:** 2 hours

---

### Phase 4 Complete

After completing all steps, you have:

```
✓ Cloudflare account with API token
✓ Cloudflare DNS driver with safe per-record operations
✓ Domain migrated from Namecheap to Cloudflare
✓ SSL mode: Full (Strict)
✓ WordPress WAF rules active
✓ Rate limiting on sensitive endpoints
✓ Cache rules optimized for WordPress
✓ CLI commands for DNS management
✓ Dual-provider support in Fabrik
```

**New CLI commands:**

```bash
# List zones
fabrik dns zones

# List records
fabrik dns records yourdomain.com

# Export records
fabrik dns export yourdomain.com

# Add record
fabrik dns add yourdomain.com --type=A --name=@ --content=1.2.3.4 --proxy

# Delete record
fabrik dns delete yourdomain.com --type=A --name=test

# Migrate from Namecheap to Cloudflare
fabrik dns migrate yourdomain.com

# Configure WordPress optimization
fabrik dns configure yourdomain.com --wordpress

# Purge cache
fabrik dns purge-cache yourdomain.com --all
```

---

### Updated Spec Format

```yaml
# specs/my-site/spec.yaml

dns:
  provider: cloudflare
  zone_id: ${CF_ZONE_YOURDOMAIN}
  proxy: true
  records:
    - type: A
      name: "@"
      content: ${VPS_IP}
      proxied: true
    - type: A
      name: "www"
      content: ${VPS_IP}
      proxied: true
```

---

### Phase 4 Summary

| Step | Task | Time |
|------|------|------|
| 1 | Create Cloudflare account and API token | 15 min |
| 2 | Implement Cloudflare DNS driver | 2 hrs |
| 3 | Add domain to Cloudflare | 15 min |
| 4 | Test Cloudflare DNS | 30 min |
| 5 | Migrate nameservers | 1 hr |
| 6 | Update Fabrik specs | 1 hr |
| 7 | Configure SSL mode | 1 hr |
| 8 | Configure WAF rules | 1 hr |
| 9 | Configure cache rules | 1 hr |
| 10 | CLI commands for DNS | 2 hrs |

**Total: ~10 hours (1-2 days)**

---

### Benefits Realized

| Before (Namecheap) | After (Cloudflare) |
|-------------------|-------------------|
| Replace-all API (risky) | Per-record CRUD (safe) |
| IP whitelist required | No whitelist needed |
| DNS-only | CDN + DNS |
| No WAF | Free WAF included |
| Slow propagation | Fast propagation |
| No analytics | Traffic analytics |

---

### What's Next (Phase 5 Preview)

Phase 5 adds staging environments:
- Clone production to staging
- Test changes safely
- Promote staging to production
- Database cloning and anonymization

---
