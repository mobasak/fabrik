# site-provisioner — Service Integration Contract

**Service:** Site Provisioner
**URL:** `https://provision.vps1.ocoron.com` (VPS) / `http://localhost:8001` (WSL dev)
**Port:** 8001 (internal container) / 18014 (host/registered)
**Source:** `/opt/site-provisioner`
**Status:** Live on vps1 (container `site-provisioner`, healthy, on the `fabrik` network) — the one Fabrik microservice still deployed. Contract field names like `ready_for_coolify` are historical — they predate the SSH+Compose migration but remain on the API surface as a stable contract; consumers now interpret "ready" as "ready for the SSH deployer to run `docker compose up -d`".
**Last verified:** 2026-06-17

---

## What It Does

Single gateway for all domain provisioning operations: DNS, Cloudflare, domain registration, analytics, and webmaster tools. Fabrik never calls Namecheap or Cloudflare APIs directly — everything goes through site-provisioner.

**Capabilities:**
- **DNS & CDN** — zones, DNS records, CDN (tiered cache), security (Page Shield, WAF), DNSSEC
- **Domain registration** — availability checks, pricing (multi-registrar), registration, WHOIS privacy, nameservers
- **Analytics** — Google Analytics 4 (GA4) property creation, Google Search Console (GSC) site verification
- **Webmaster Tools** — Bing Webmaster Tools integration, IndexNow pinging

site-provisioner manages registrar selection internally (Namecheap, DomainNameAPI, etc.). Fabrik does not need to know which registrar is used.

---

## Fabrik Integration

### Driver

```python
from fabrik.drivers.dns import DNSClient

dns = DNSClient()  # reads DNS_MANAGER_URL from env
```

### CLI Commands

```bash
fabrik domain check <domain>           # Check availability (Namecheap)
fabrik domain buy <domain>             # Register domain (Namecheap)
fabrik domain provision <domain>       # Full Cloudflare setup (DNS + CDN + WAF)
fabrik domain ready <domain>           # Verify deployment readiness
fabrik domain zones                    # List all Cloudflare zones
```

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SITE_PROVISIONER_URL` | No | `https://provision.vps1.ocoron.com` | Service URL |
| `SITE_PROVISIONER_TOKEN` | Prod only | — | Bearer token for auth |
| `VPS_IP` | For provision | — | Target IP for DNS records |

---

## Workflow 1: Deploy New Website (Existing Domain)

```
FABRIK                              dns-manager              Cloudflare
  │                                      │                       │
  │ POST /api/cloudflare/zones/{d}/provision                     │
  │ {target_ip, subdomains, ...}         │                       │
  │─────────────────────────────────────►│ Ensure zone           │
  │                                      │──────────────────────►│
  │                                      │ Create A records      │
  │                                      │──────────────────────►│
  │                                      │ Enable tiered cache   │
  │                                      │──────────────────────►│
  │                                      │ Enable page shield    │
  │                                      │──────────────────────►│
  │                                      │ Create WAF rule       │
  │                                      │──────────────────────►│
  │◄─────────────────────────────────────│                       │
  │ {ready_for_coolify: true}            │                       │
  │                                      │                       │
  │ GET /api/cloudflare/zones/{d}/ready  │                       │
  │─────────────────────────────────────►│ Check zone + features │
  │◄─────────────────────────────────────│                       │
  │ {ready_for_deployment: true}         │                       │
  │                                      │                       │
  │ Deploy to Coolify ───────────────────────────────────────────│
```

**CLI:**
```bash
fabrik domain provision newsite.com -s www -s api
fabrik domain ready newsite.com
fabrik apply specs/newsite.yaml
```

## Workflow 2: Buy + Deploy New Domain

```
FABRIK                              dns-manager              Registrar
  │                                      │                       │
  │ POST /api/domains/check              │                       │
  │ {domains: ["newsite.com"]}           │                       │
  │─────────────────────────────────────►│ Query registrars      │
  │                                      │──────────────────────►│
  │◄─────────────────────────────────────│                       │
  │ {available: true}                    │                       │
  │                                      │                       │
  │ POST /api/domains/register           │                       │
  │ {domain, years}                      │                       │
  │─────────────────────────────────────►│ Register at best      │
  │                                      │──────────────────────►│
  │◄─────────────────────────────────────│ Registered            │
  │                                      │                       │
  │ POST /api/cloudflare/zones/{d}/provision  (→ Cloudflare)     │
  │─────────────────────────────────────►│ Setup DNS + Security  │
  │◄─────────────────────────────────────│                       │
  │                                      │                       │
  │ Deploy to Coolify                    │                       │
```

**CLI:**
```bash
fabrik domain check newsite.com
fabrik domain buy newsite.com
fabrik domain provision newsite.com -s www -s api
fabrik domain ready newsite.com
fabrik apply specs/newsite.yaml
```

---

## API Reference

### Cloudflare Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/cloudflare/health` | Cloudflare API health check |
| `GET` | `/api/cloudflare/zones` | List all zones |
| `POST` | `/api/cloudflare/zones` | Create new zone |
| `GET` | `/api/cloudflare/zones/{domain}/status` | Zone status + nameservers |
| `POST` | `/api/cloudflare/zones/{domain}/provision` | **Full website provisioning** |
| `GET` | `/api/cloudflare/zones/{domain}/ready` | **Deployment readiness check** |
| `GET` | `/api/cloudflare/dns/{domain}` | List DNS records |
| `POST` | `/api/cloudflare/dns/{domain}` | Create DNS record |
| `DELETE` | `/api/cloudflare/dns/{domain}` | Delete DNS records |
| `POST` | `/api/cloudflare/dns/{domain}/subdomain` | Add subdomain A record |
| `POST` | `/api/cloudflare/enterprise/enable-all` | Apply enterprise features to all zones |

### Domain Registration Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/domains` | List all registered domains |
| `GET` | `/api/domains/{domain}` | Domain details |
| `POST` | `/api/domains/check` | Check availability (queries all registrars) |
| `POST` | `/api/domains/register` | Register new domain (dns-manager selects registrar) |
| `GET` | `/api/domains/pricing/{tld}` | TLD pricing (from all registrars) |

### Registrar DNS Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/dns/{domain}` | Get DNS records (registrar-level) |
| `PUT` | `/api/dns/{domain}` | Set DNS records (replaces all) |
| `POST` | `/api/dns/{domain}/subdomain` | Add subdomain (safe merge) |
| `GET` | `/api/dns/{domain}/nameservers` | Get nameservers |
| `PUT` | `/api/dns/{domain}/nameservers` | Set nameservers |

---

## Provision Request Schema

```json
POST /api/cloudflare/zones/{domain}/provision
{
  "target_ip": "172.93.160.197",
  "subdomains": ["www", "api"],
  "enable_dnssec": true,
  "enable_tiered_cache": true,
  "enable_page_shield": true,
  "create_threat_rule": true,
  "threat_threshold": 50
}
```

**Response:**
```json
{
  "success": true,
  "domain": "newsite.com",
  "dns_records": [{"type": "A", "name": "api", "content": "172.93.160.197", "proxied": true}],
  "features_enabled": {
    "dnssec": true,
    "tiered_cache": true,
    "page_shield": true,
    "threat_rule": "cf.threat_score gt 50"
  },
  "ready_for_coolify": true
}
```

## Ready Check Response Schema

```json
GET /api/cloudflare/zones/{domain}/ready
{
  "domain": "newsite.com",
  "zone_exists": true,
  "zone_status": "active",
  "dns_records": [{"name": "newsite.com", "content": "172.93.160.197", "proxied": true}],
  "features": {"dnssec": "active", "tiered_cache": true, "page_shield": true},
  "ready_for_deployment": true
}
```

---

## Notes

- **DNSSEC** may require specific auth configuration in dns-manager. If it fails, other features still work.
- Some registrar endpoints require whitelisted IP — only works from VPS, not from WSL dev. Cloudflare endpoints work from anywhere.
- Fabrik does not manage API keys or tokens for any provider — dns-manager holds all credentials.
- dns-manager sets appropriate nameservers at registration time so DNS works immediately — no propagation wait.
