# Fabrik Drivers

**Last Updated:** 2025-12-23

Fabrik drivers provide Python clients for external services used in deployment automation.

---

## Available Drivers

### CloudflareClient (Phase 1c)

Cloudflare DNS management with per-record CRUD operations.

```python
from fabrik.drivers.cloudflare import CloudflareClient

cf = CloudflareClient()

# Health check
cf.health()

# List zones
zones = cf.list_zones()

# Get zone ID by domain
zone_id = cf.get_zone_id("ocoron.com")

# List records
records = cf.list_records(zone_id)

# Create/update record (idempotent)
cf.ensure_record("ocoron.com", "A", "myapp.vps1", "172.93.160.197", proxied=False)

# Delete record
cf.delete_record_by_name("ocoron.com", "A", "myapp.vps1")

# Fabrik-compatible helper
cf.add_subdomain("ocoron.com", "myapp.vps1", "172.93.160.197")
```

**Environment Variables:**
```bash
CLOUDFLARE_API_TOKEN=xxx
CLOUDFLARE_ACCOUNT_ID=066f5cf1dfe20ba18549a592809aa080
CLOUDFLARE_ZONE_ID_OCORON=b3494f947c71683f94b6afe1331a1ba6
```

---

| Driver | Purpose | Config |
|--------|---------|--------|
| `DNSClient` | DNS management via unified DNS service | `DNS_MANAGER_URL` |
| `WordPressClient` | WP-CLI wrapper for WordPress containers | SSH to VPS |
| `WordPressAPIClient` | WordPress REST API for content operations | Site URL + App Password |
| `CloudflareClient` | Cloudflare DNS (direct or via service) | `CLOUDFLARE_API_TOKEN` |
| `CoolifyClient` | Coolify deployment API | `COOLIFY_API_URL`, `COOLIFY_API_TOKEN` |
| `UptimeKumaClient` | Status monitoring | `UPTIME_KUMA_URL`, `UPTIME_KUMA_USERNAME`, `UPTIME_KUMA_PASSWORD` |
| `SupabaseClient` | Auth + Database (Phase 1b) | `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY` |
| `R2Client` | Cloudflare R2 storage (Phase 1b) | `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET` |

---

## DNS Client

Wraps the already-deployed namecheap service at VPS. Does NOT call Namecheap API directly.

### Usage

```python
from fabrik.drivers.dns import DNSClient

# Initialize (uses NAMECHEAP_API_URL env var or default)
dns = DNSClient()

# Or specify URL explicitly
dns = DNSClient(base_url="https://namecheap.vps1.ocoron.com")

# Add subdomain (most common operation)
dns.add_subdomain("ocoron.com", "myapp.vps1", "172.93.160.197")
# Creates: myapp.vps1.ocoron.com -> 172.93.160.197

# List domains
domains = dns.list_domains()
for d in domains:
    print(d.get("@Name"), d.get("@Expires"))

# Get DNS records
records = dns.get_records("ocoron.com")
for r in records:
    print(r.get("type"), r.get("name"), r.get("value"))

# Check health
print(dns.health())

# Always close when done
dns.close()

# Or use context manager
with DNSClient() as dns:
    dns.add_subdomain("ocoron.com", "api.vps1", "172.93.160.197")
```

### Quick Helper

```python
from fabrik.drivers.dns import add_dns_record

# One-liner for adding subdomain
add_dns_record("ocoron.com", "api.vps1", "172.93.160.197")
```

### Available Methods

| Method | Description |
|--------|-------------|
| `health()` | Check service health |
| `list_domains()` | List all domains in account |
| `get_domain(domain)` | Get domain details |
| `get_records(domain)` | Get all DNS records |
| `add_subdomain(domain, subdomain, ip)` | Add A record for subdomain |
| `set_records(domain, records)` | Replace all records (careful!) |
| `get_nameservers(domain)` | Get current nameservers |
| `set_nameservers(domain, ns_list)` | Set custom nameservers |
| `get_balance()` | Get account balance |

---

## Coolify Client

Interacts with Coolify API for deployment management.

### Prerequisites

1. Generate API token in Coolify UI: **Settings → Keys & Tokens → API tokens**
2. Set `COOLIFY_API_TOKEN` in `.env`

### Usage

```python
from fabrik.drivers.coolify import CoolifyClient

# Initialize (uses env vars)
coolify = CoolifyClient()

# Or specify explicitly
coolify = CoolifyClient(
    base_url="http://172.93.160.197:8000",
    token="your-api-token"
)

# Get version
print(coolify.version())  # "4.0.0-beta.455"

# List servers
servers = coolify.list_servers()
for s in servers:
    print(s.get("name"), s.get("ip"))

# List projects
projects = coolify.list_projects()

# List applications
apps = coolify.list_applications()

# Deploy an application
coolify.deploy("app-uuid")

# Stop/Start/Restart
coolify.stop_application("app-uuid")
coolify.start_application("app-uuid")
coolify.restart_application("app-uuid")

# Environment variables
coolify.create_env_var("app-uuid", "API_KEY", "secret123")
coolify.get_env_vars("app-uuid")

# Always close
coolify.close()
```

### Available Methods

#### Servers
| Method | Description |
|--------|-------------|
| `list_servers()` | List all servers |
| `get_server(uuid)` | Get server details |
| `get_server_resources(uuid)` | Get all resources on server |
| `get_server_domains(uuid)` | Get all domains on server |

#### Projects
| Method | Description |
|--------|-------------|
| `list_projects()` | List all projects |
| `get_project(uuid)` | Get project details |
| `create_project(name, description)` | Create new project |

#### Applications
| Method | Description |
|--------|-------------|
| `list_applications()` | List all applications |
| `get_application(uuid)` | Get application details |
| `create_application(...)` | Create new application |
| `update_application(uuid, **kwargs)` | Update application |
| `delete_application(uuid)` | Delete application |
| `deploy(uuid, force=False)` | Deploy/redeploy |
| `stop_application(uuid)` | Stop application |
| `start_application(uuid)` | Start application |
| `restart_application(uuid)` | Restart application |

#### Environment Variables
| Method | Description |
|--------|-------------|
| `get_env_vars(uuid)` | Get all env vars |
| `create_env_var(uuid, key, value)` | Create env var |
| `update_env_var(uuid, env_uuid, **kwargs)` | Update env var |
| `delete_env_var(uuid, env_uuid)` | Delete env var |
| `bulk_update_env_vars(uuid, dict)` | Bulk update env vars |

#### Services & Databases
| Method | Description |
|--------|-------------|
| `list_services()` | List all services |
| `list_databases()` | List all databases |
| `create_database(...)` | Create database |
| `start_database(uuid)` | Start database |
| `stop_database(uuid)` | Stop database |

---

## Environment Variables

All credentials are stored in `/opt/fabrik/.env`:

```bash
# DNS
NAMECHEAP_API_URL=https://namecheap.vps1.ocoron.com

# Coolify
COOLIFY_API_URL=http://172.93.160.197:8000
COOLIFY_API_TOKEN=5|YA40VYboS...

# B2 Backups
B2_KEY_ID=0044e7ca36a086b0000000001
B2_APPLICATION_KEY=K004hcjQVRBA...
```

**Never commit `.env` to git!** It's already in `.gitignore`.

---

## Testing Drivers

```bash
cd /opt/fabrik
PYTHONPATH=src python3 -c "
from fabrik.drivers.dns import DNSClient
from fabrik.drivers.coolify import CoolifyClient

dns = DNSClient()
print('DNS Health:', dns.health())
dns.close()

coolify = CoolifyClient()
print('Coolify Version:', coolify.version())
coolify.close()
"
```

---

## Supabase Client (Phase 1b)

Client for Supabase Auth and Database operations.

### Usage

```python
from fabrik.drivers.supabase import SupabaseClient

# Initialize
supabase = SupabaseClient()

# Check health
print(supabase.health())

# Verify JWT token
result = supabase.verify_jwt(token)
if result["valid"]:
    user = result["user"]

# Database operations
rows = supabase.query("files", filters={"tenant_id": "abc"})
supabase.insert("files", {"filename": "test.pdf", "tenant_id": "abc"})
supabase.update("files", {"status": "ready"}, {"id": "123"})

# File processing jobs
job = supabase.create_processing_job(file_id="123", job_type="transcribe")
claimed = supabase.claim_next_job(["transcribe", "ocr"], worker_id="w1")
supabase.complete_job(job_id="123", success=True, result_data={"duration": 120})

supabase.close()
```

### Environment Variables

```bash
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_ANON_KEY=eyJhbGc...
SUPABASE_SERVICE_ROLE_KEY=eyJhbGc...
```

---

## R2 Client (Phase 1b)

Client for Cloudflare R2 object storage with S3-compatible API.

### Usage

```python
from fabrik.drivers.r2 import R2Client

# Initialize
r2 = R2Client(bucket="my-bucket")

# Generate presigned URLs
upload_url = r2.generate_presigned_url("uploads/file.pdf", method="PUT", expires_in=3600)
download_url = r2.generate_presigned_url("uploads/file.pdf", method="GET")

# Direct operations
r2.put_object("test.txt", b"Hello World", content_type="text/plain")
data = r2.get_object("test.txt")
r2.delete_object("test.txt")

# List objects
objects = r2.list_objects(prefix="uploads/")

r2.close()
```

### Environment Variables

```bash
R2_ACCOUNT_ID=abc123
R2_ACCESS_KEY_ID=xxx
R2_SECRET_ACCESS_KEY=xxx
R2_BUCKET=my-bucket
R2_PUBLIC_URL=https://files.example.com  # Optional
```

---

## File Locations

| File | Purpose |
|------|---------|
| `src/fabrik/drivers/__init__.py` | Driver exports |
| `src/fabrik/drivers/dns.py` | DNS client |
| `src/fabrik/drivers/coolify.py` | Coolify client |
| `src/fabrik/drivers/uptime_kuma.py` | Uptime Kuma client |
| `src/fabrik/drivers/supabase.py` | Supabase client |
| `src/fabrik/drivers/r2.py` | Cloudflare R2 client |
| `.env` | Credentials (gitignored) |
| `.env.example` | Template for .env |
