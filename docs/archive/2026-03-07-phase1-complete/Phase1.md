> **Phase 1 Navigation:** [1a: Foundation](Phase1.md) | [1b: Cloud](Phase1b.md) | [1c: DNS](Phase1c.md) | [1d: WordPress](Phase1d.md) | [Phase 2 →](Phase2.md)

## Phase 1: Foundation — Complete Narrative

**Last Updated:** 2025-12-27
**Status:** ✅ COMPLETE (historical implementation)

---

### Progress Tracker

| Step | Task | Status |
|------|------|--------|
| 1 | SSH Hardening | ✅ Done |
| 2 | Firewall (UFW) | ✅ Done |
| 3 | Fail2Ban | ✅ Done |
| 4 | Automatic Security Updates | ✅ Done |
| 5 | Docker Log Rotation | ✅ Done |
| 6 | Install Coolify | ✅ Done |
| 7 | Secure Coolify | ✅ Done |
| 8 | Deploy Postgres | ✅ Done |
| 9 | Deploy Redis | ✅ Done |
| 10 | Configure Postgres Backup | ✅ Done (Duplicati to B2) |
| 11 | Create Fabrik Folder Structure | ✅ Done |
| 12 | Set Up Secrets | ✅ Done |
| 13 | Implement spec_loader.py | ✅ Done |
| 14 | Implement dns_namecheap.py | ✅ Done (as DNSClient driver) |
| 15 | Implement coolify.py | ✅ Done (as CoolifyClient driver) |
| 16 | Implement template_renderer.py | ✅ Done |
| 17 | Implement `fabrik new` | ✅ Done |
| 18 | Implement `fabrik plan` | ✅ Done |
| 19 | Implement `fabrik apply` | ✅ Done |
| 20 | Create app-python Template | ✅ Done |
| 21 | Deploy Hello API | ✅ Done (manual, not via fabrik) |
| 22 | Uptime Kuma Setup | ✅ Done |
| 23 | Test Backup and Restore | ✅ Done |
| 24 | Implement `fabrik logs` | ✅ Done |
| 25 | Implement `fabrik destroy` | ✅ Done |

**Completion: 25/25 tasks (100%)** ✅ Phase 1 Complete!

**Next Phases:**
- **Phase 1b:** Cloud Infrastructure (Supabase + R2) — See `Phase1b.md`
- **Phase 1c:** Cloudflare DNS Migration — See `Phase1c.md`

---

### What We're Building in Phase 1

By the end of Phase 1, you will have:

1. **A hardened VPS** that resists common attacks (bot scans, brute force, opportunistic exploits)
2. **Coolify installed** as the container runtime with HTTPS dashboard access
3. **Shared Postgres and Redis** running as foundational services
4. **Automated backups** to Backblaze B2
5. **Fabrik CLI** that can deploy Python APIs and WordPress sites from spec files
6. **DNS automation** that safely manages records without destroying existing ones
7. **Uptime monitoring** with alerts when things break
8. **One deployed Python API** proving the full chain works
9. **One deployed WordPress site** proving the WordPress template works

This is the minimum viable platform. Everything else builds on top of this foundation.

---

### Prerequisites

Before starting, confirm you have:

```
[ ] VPS accessible at 172.93.160.197
[ ] SSH key pair (public key on VPS, private key on your machine)
[ ] Root or sudo access to VPS
[ ] Namecheap account with API access enabled
[ ] Namecheap API credentials (API user, API key)
[ ] Your IP whitelisted for Namecheap API
[ ] Backblaze B2 account created
[ ] A domain you control for testing (e.g., yourdomain.com)
[ ] Subdomain decided for Coolify dashboard (e.g., coolify.yourdomain.com)
```

---

### Step 1: SSH Hardening

**Why:** SSH is the front door to your server. Default configurations allow password login and root access — both are attack vectors. Bots constantly scan for open SSH ports and attempt brute force attacks.

**What we're doing:**
- Disable root login (attackers always try root first)
- Disable password authentication (only SSH keys allowed)
- Limit login attempts
- Restrict to specific user

**Commands:**

```bash
# Connect as root (last time you'll do this)
ssh root@172.93.160.197

# Create deploy user
adduser deploy
usermod -aG sudo deploy

# Set up SSH key for deploy user
mkdir -p /home/deploy/.ssh
cp /root/.ssh/authorized_keys /home/deploy/.ssh/
chown -R deploy:deploy /home/deploy/.ssh
chmod 700 /home/deploy/.ssh
chmod 600 /home/deploy/.ssh/authorized_keys

# Test login in NEW terminal before changing SSH config
# ssh deploy@172.93.160.197
# If that works, continue:

# Edit SSH config
nano /etc/ssh/sshd_config
```

**Change these lines in sshd_config:**

```
PermitRootLogin no
PasswordAuthentication no
PubkeyAuthentication yes
MaxAuthTries 3
AllowUsers deploy
```

**Apply changes:**

```bash
# Validate config (catches syntax errors)
sshd -t

# Restart SSH
systemctl restart sshd
```

**Verification:**

```bash
# In a NEW terminal (don't close existing session yet):
ssh root@172.93.160.197
# Should fail: "Permission denied"

ssh deploy@172.93.160.197
# Should succeed
```

**Time:** 15 minutes

---

### Step 2: Firewall (UFW)

**Why:** By default, all ports are open. We only need three: SSH (22), HTTP (80), HTTPS (443). Everything else should be blocked.

**What we're doing:**
- Default deny all incoming traffic
- Allow only ports 22, 80, 443
- Allow all outgoing traffic (containers need to pull images, etc.)

**Commands:**

```bash
ssh deploy@172.93.160.197

# Install UFW if not present
sudo apt update
sudo apt install ufw -y

# Set defaults
sudo ufw default deny incoming
sudo ufw default allow outgoing

# Allow required ports
sudo ufw allow 22/tcp comment 'SSH'
sudo ufw allow 80/tcp comment 'HTTP'
sudo ufw allow 443/tcp comment 'HTTPS'

# Enable (type 'y' when prompted)
sudo ufw enable

# Check status
sudo ufw status verbose
```

**Expected output:**

```
Status: active

To                         Action      From
--                         ------      ----
22/tcp                     ALLOW IN    Anywhere        # SSH
80/tcp                     ALLOW IN    Anywhere        # HTTP
443/tcp                    ALLOW IN    Anywhere        # HTTPS
```

**Time:** 10 minutes

---

### Step 3: Fail2Ban

**Why:** Even with key-only SSH, bots will hammer your SSH port with login attempts. Fail2ban watches auth logs and temporarily bans IPs that fail too many times.

**What we're doing:**
- Install fail2ban
- Configure SSH jail (3 failures = 1 hour ban)
- Enable and start service

**Commands:**

```bash
# Install
sudo apt install fail2ban -y

# Create local config (don't edit main config)
sudo nano /etc/fail2ban/jail.local
```

**Add this content:**

```ini
[DEFAULT]
bantime = 3600
findtime = 600
maxretry = 3
backend = systemd

[sshd]
enabled = true
port = ssh
filter = sshd
logpath = /var/log/auth.log
maxretry = 3
bantime = 3600
```

**Start service:**

```bash
sudo systemctl enable fail2ban
sudo systemctl start fail2ban

# Check status
sudo fail2ban-client status sshd
```

**Expected output:**

```
Status for the jail: sshd
|- Filter
|  |- Currently failed: 0
|  |- Total failed:     0
|  `- File list:        /var/log/auth.log
`- Actions
   |- Currently banned: 0
   |- Total banned:     0
   `- Banned IP list:
```

**Time:** 10 minutes

---

### Step 4: Automatic Security Updates

**Why:** Security vulnerabilities are discovered constantly. Unattended upgrades automatically install security patches without manual intervention.

**Commands:**

```bash
sudo apt install unattended-upgrades -y
sudo dpkg-reconfigure -plow unattended-upgrades
# Select "Yes" when prompted
```

**Verify:**

```bash
cat /etc/apt/apt.conf.d/20auto-upgrades
```

**Should show:**

```
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
```

**Time:** 5 minutes

---

### Step 5: Docker Log Rotation

**Why:** Docker containers generate logs continuously. Without rotation, logs consume all disk space and crash the server. This is a common "server died mysteriously" cause.

**Commands:**

```bash
sudo nano /etc/docker/daemon.json
```

**Add this content (create file if it doesn't exist):**

```json
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
```

**Restart Docker:**

```bash
sudo systemctl restart docker
```

**Verification:**

```bash
docker info | grep -A 5 "Logging Driver"
```

**Time:** 5 minutes

---

### Step 6: Install Coolify

**Why:** Coolify is the runtime that manages containers, domains, SSL certificates, and provides the API that Fabrik will call.

**What we're doing:**
- Run Coolify's installation script
- Wait for initial setup
- Access dashboard and create admin account

**Commands:**

```bash
# Run Coolify installer
curl -fsSL https://cdn.coollabs.io/coolify/install.sh | sudo bash
```

**This takes 5-10 minutes.** It will:
- Install Docker if not present
- Pull Coolify images
- Start Coolify containers
- Set up internal networking

**When complete, you'll see:**

```
Coolify installed successfully!
Please visit http://172.93.160.197:8000 to get started.
```

**Initial setup:**

1. Open `http://172.93.160.197:8000` in browser
2. Create admin account:
   - Email: your email
   - Password: **24+ characters, random** (use `openssl rand -base64 32`)
   - Save this password in your password manager immediately
3. Complete initial wizard

**Time:** 30 minutes

---

### Step 7: Secure Coolify

**Why:** Coolify dashboard has full control over your infrastructure. It needs HTTPS and strong authentication.

**What we're doing:**
- Point a domain to Coolify
- Enable HTTPS
- Configure 2FA if available

**Steps:**

**7.1: Add DNS record for Coolify**

In Namecheap dashboard (manual for now, Fabrik not built yet):

```
Type: A
Host: coolify
Value: 172.93.160.197
TTL: Automatic
```

**7.2: Configure domain in Coolify**

1. Go to Coolify dashboard → Settings → General
2. Set "Instance's Domain" to `coolify.yourdomain.com`
3. Save
4. Coolify will automatically provision SSL certificate

**7.3: Verify HTTPS**

Wait 2-5 minutes for DNS propagation and SSL issuance, then:

```
https://coolify.yourdomain.com
```

Should load Coolify dashboard with valid HTTPS.

**7.4: Enable 2FA (if available)**

Check Settings → Security for two-factor authentication options.

**Time:** 15 minutes

---

### Step 8: Deploy Postgres

**Why:** Shared database for all your applications. One container, many databases — efficient resource usage.

**What we're doing:**
- Deploy Postgres 16 via Coolify UI
- Configure strong password
- Ensure it's not exposed publicly

**Steps:**

1. Coolify dashboard → Projects → Create new project: "shared-services"
2. Inside project → Add Resource → Database → PostgreSQL
3. Configure:
   - Name: `postgres-main`
   - Version: 16
   - Password: Generate strong password (save it!)
   - **Public access: OFF** (critical)
4. Deploy

**Verification:**

```bash
# SSH into VPS
ssh deploy@172.93.160.197

# Test connection (get connection string from Coolify)
docker exec -it <postgres-container-id> psql -U postgres -c "SELECT version();"
```

**Time:** 10 minutes

---

### Step 9: Deploy Redis

**Why:** Shared cache and session storage. Used by WordPress, APIs, rate limiting.

**Steps:**

1. Same project "shared-services"
2. Add Resource → Database → Redis
3. Configure:
   - Name: `redis-main`
   - Password: Generate strong password
   - **Public access: OFF**
4. Deploy

**Verification:**

```bash
docker exec -it <redis-container-id> redis-cli -a <password> ping
# Should return: PONG
```

**Time:** 10 minutes

---

### Step 10: Configure Postgres Backup

**Why:** Data loss is catastrophic. Daily backups to off-site storage (Backblaze B2) ensure recovery.

**Steps:**

**10.1: Create Backblaze B2 bucket**

1. Log into Backblaze B2
2. Create bucket: `fabrik-backups`
3. Create application key:
   - Name: `fabrik-backup`
   - Allow access to: `fabrik-backups` bucket only
4. Save: keyID and applicationKey

**10.2: Configure backup in Coolify**

1. Coolify → postgres-main → Backups
2. Add S3-compatible destination:
   - Endpoint: `s3.us-west-004.backblazeb2.com` (check your region)
   - Bucket: `fabrik-backups`
   - Access Key: your keyID
   - Secret Key: your applicationKey
3. Schedule: Daily
4. Retention: 30 days
5. Test backup manually

**Time:** 15 minutes

---

### Step 11: Create Fabrik Folder Structure

**Why:** Organized structure makes the codebase maintainable and predictable.

**Where:** On your local machine (or wherever you run Fabrik from — could be WSL, could be VPS itself).

**Commands:**

```bash
# Create project directory
mkdir -p ~/projects/fabrik
cd ~/projects/fabrik

# Create structure
mkdir -p cli
mkdir -p compiler
mkdir -p templates/wp-site
mkdir -p templates/app-python
mkdir -p templates/app-node
mkdir -p apps
mkdir -p specs
mkdir -p secrets/projects
mkdir -p dns/state

# Create placeholder files
touch fabrik
touch cli/__init__.py
touch cli/main.py
touch cli/new.py
touch cli/plan.py
touch cli/apply.py
touch cli/status.py
touch cli/logs.py
touch cli/destroy.py
touch compiler/__init__.py
touch compiler/spec_loader.py
touch compiler/template_renderer.py
touch compiler/dns_namecheap.py
touch compiler/dns_cloudflare.py
touch compiler/coolify.py
touch compiler/secrets.py
touch compiler/reporter.py
touch templates/wp-site/defaults.yaml
touch templates/wp-site/compose.yaml.j2
touch templates/wp-site/hooks.py
touch templates/app-python/defaults.yaml
touch templates/app-python/compose.yaml.j2
touch templates/app-python/Dockerfile.j2
touch README.md

# Create .gitignore
cat > .gitignore << 'EOF'
secrets/
*.env
__pycache__/
*.pyc
.venv/
EOF

# Initialize git
git init
git add .
git commit -m "Initial Fabrik structure"
```

**Final structure:**

```
fabrik/
├── fabrik                       # CLI entry point
├── cli/
│   ├── __init__.py
│   ├── main.py
│   ├── new.py
│   ├── plan.py
│   ├── apply.py
│   ├── status.py
│   ├── logs.py
│   └── destroy.py
├── compiler/
│   ├── __init__.py
│   ├── spec_loader.py
│   ├── template_renderer.py
│   ├── dns_namecheap.py
│   ├── dns_cloudflare.py
│   ├── coolify.py
│   ├── secrets.py
│   └── reporter.py
├── templates/
│   ├── wp-site/
│   ├── app-python/
│   └── app-node/
├── apps/
├── specs/
├── secrets/
│   └── projects/
├── dns/
│   └── state/
└── README.md
```

**Time:** 15 minutes

---

### Step 12: Set Up Secrets

**Why:** API tokens and passwords need secure storage with proper permissions.

**Commands:**

```bash
cd ~/projects/fabrik

# Create platform secrets file
cat > secrets/platform.env << 'EOF'
# Coolify
COOLIFY_URL=https://coolify.yourdomain.com
COOLIFY_API_TOKEN=

# Namecheap DNS
NAMECHEAP_API_USER=
NAMECHEAP_API_KEY=
NAMECHEAP_CLIENT_IP=

# Cloudflare (for later)
CF_API_TOKEN=

# Database
POSTGRES_HOST=
POSTGRES_PASSWORD=
POSTGRES_URL=

# Redis
REDIS_HOST=
REDIS_PASSWORD=
REDIS_URL=

# Backups
B2_ACCESS_KEY=
B2_SECRET_KEY=
B2_BUCKET=fabrik-backups

# VPS
VPS_IP=172.93.160.197
EOF

# Set permissions
chmod 600 secrets/platform.env
```

**Fill in the values:**

1. **COOLIFY_API_TOKEN:** Coolify dashboard → Settings → API → Generate token
2. **NAMECHEAP_API_USER:** Your Namecheap username
3. **NAMECHEAP_API_KEY:** From Namecheap API settings
4. **NAMECHEAP_CLIENT_IP:** Your current IP (must be whitelisted)
5. **POSTGRES_HOST:** Internal Docker hostname (get from Coolify)
6. **POSTGRES_PASSWORD:** The password you generated in Step 8
7. **POSTGRES_URL:** `postgresql://postgres:<password>@<host>:5432/postgres`
8. **REDIS_HOST:** Internal Docker hostname
9. **REDIS_PASSWORD:** The password you generated in Step 9
10. **REDIS_URL:** `redis://:<password>@<host>:6379`
11. **B2_ACCESS_KEY:** From Backblaze B2
12. **B2_SECRET_KEY:** From Backblaze B2

**Time:** 15 minutes

---

### Step 13: Implement spec_loader.py

**Why:** This module parses and validates spec files. It's the foundation — everything else depends on correctly loaded specs.

**Code:**

```python
# compiler/spec_loader.py

from pathlib import Path
from typing import Optional
import yaml
from pydantic import BaseModel, Field, validator
from enum import Enum

class Kind(str, Enum):
    SERVICE = "service"
    WORKER = "worker"

class SourceType(str, Enum):
    TEMPLATE = "template"
    GIT = "git"
    DOCKER = "docker"

class DNSProvider(str, Enum):
    NAMECHEAP = "namecheap"
    CLOUDFLARE = "cloudflare"

class DNSRecord(BaseModel):
    type: str  # A, CNAME, TXT, MX
    name: str  # @ or subdomain
    content: str  # IP or target
    ttl: int = 1800
    priority: Optional[int] = None  # For MX records

class DNSConfig(BaseModel):
    provider: DNSProvider
    records: list[DNSRecord] = []

class Source(BaseModel):
    type: SourceType
    repository: Optional[str] = None
    branch: str = "main"
    image: Optional[str] = None

class Expose(BaseModel):
    http: bool = True
    internal_only: bool = False

class Resources(BaseModel):
    memory: str = "256M"
    cpu: str = "0.5"

class Health(BaseModel):
    path: str = "/"
    interval: str = "30s"

class Storage(BaseModel):
    name: str
    path: str
    backup: bool = False

class Backup(BaseModel):
    enabled: bool = True
    frequency: str = "daily"
    retention: int = 30

class SecretsPolicy(BaseModel):
    required: list[str] = []
    generate: list[str] = []

class CoolifyConfig(BaseModel):
    project: str = "default"
    server: str = "localhost"
    compose_path: Optional[str] = None

class Depends(BaseModel):
    postgres: Optional[str] = None
    redis: Optional[str] = None

class WordPressPlugin(BaseModel):
    slug: str
    activate: bool = True
    source: str = "wp_repo"  # wp_repo | zip
    zip_url: Optional[str] = None

class WordPressConfig(BaseModel):
    plugins: list[WordPressPlugin] = []
    disable_xmlrpc: bool = True
    disable_file_edit: bool = True

class Spec(BaseModel):
    id: str
    kind: Kind
    template: str
    domain: Optional[str] = None
    expose: Expose = Expose()
    source: Source = Source(type=SourceType.TEMPLATE)
    coolify: CoolifyConfig = CoolifyConfig()
    depends: Depends = Depends()
    env: dict[str, str] = {}
    secrets: SecretsPolicy = SecretsPolicy()
    resources: Resources = Resources()
    health: Optional[Health] = None
    storage: list[Storage] = []
    dns: Optional[DNSConfig] = None
    backup: Backup = Backup()
    wordpress: Optional[WordPressConfig] = None

    @validator('domain')
    def domain_required_for_http_service(cls, v, values):
        if values.get('kind') == Kind.SERVICE:
            expose = values.get('expose', Expose())
            if expose.http and not v:
                raise ValueError('domain required for HTTP services')
        return v

def load_spec(spec_path: str) -> Spec:
    """Load and validate a spec file."""
    path = Path(spec_path)

    if not path.exists():
        raise FileNotFoundError(f"Spec not found: {spec_path}")

    with open(path) as f:
        raw = yaml.safe_load(f)

    return Spec(**raw)

def save_spec(spec: Spec, spec_path: str):
    """Save a spec to file."""
    path = Path(spec_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, 'w') as f:
        yaml.dump(spec.dict(exclude_none=True), f, default_flow_style=False)
```

**Test:**

```bash
cd ~/projects/fabrik
python3 -c "from compiler.spec_loader import load_spec; print('OK')"
```

**Time:** 1 hour

---

### Step 14: Implement dns_namecheap.py

**Why:** This is the critical DNS driver. Must be safe — export existing records, compute diff, write back full set without destroying unmanaged records.

**Code:**

```python
# compiler/dns_namecheap.py

import os
import xml.etree.ElementTree as ET
from pathlib import Path
from dataclasses import dataclass
from typing import Optional
import httpx
import yaml
from datetime import datetime

@dataclass
class DNSRecord:
    type: str
    name: str
    content: str
    ttl: int = 1800
    priority: Optional[int] = None

    def to_dict(self):
        d = {
            'type': self.type,
            'name': self.name,
            'content': self.content,
            'ttl': self.ttl
        }
        if self.priority is not None:
            d['priority'] = self.priority
        return d

    @classmethod
    def from_dict(cls, d):
        return cls(**d)

@dataclass
class DNSDiff:
    to_add: list[DNSRecord]
    to_update: list[DNSRecord]
    to_delete: list[DNSRecord]
    unchanged: list[DNSRecord]

    @property
    def has_changes(self):
        return bool(self.to_add or self.to_update or self.to_delete)

@dataclass
class DNSResult:
    status: str
    changes: DNSDiff
    error: Optional[str] = None

class NamecheapDNS:
    """
    Namecheap DNS driver with SAFE export→diff→apply pattern.

    CRITICAL: Namecheap setHosts REPLACES all records.
    We must always read existing records first and merge.
    """

    API_URL = "https://api.namecheap.com/xml.response"

    def __init__(self):
        self.api_user = os.environ.get('NAMECHEAP_API_USER')
        self.api_key = os.environ.get('NAMECHEAP_API_KEY')
        self.client_ip = os.environ.get('NAMECHEAP_CLIENT_IP')

        if not all([self.api_user, self.api_key, self.client_ip]):
            raise ValueError("Missing Namecheap credentials in environment")

        self.state_dir = Path("dns/state")
        self.state_dir.mkdir(parents=True, exist_ok=True)

    def _api_call(self, command: str, params: dict) -> ET.Element:
        """Make Namecheap API call."""
        base_params = {
            'ApiUser': self.api_user,
            'ApiKey': self.api_key,
            'UserName': self.api_user,
            'ClientIp': self.client_ip,
            'Command': command
        }

        with httpx.Client(timeout=30) as client:
            resp = client.get(self.API_URL, params={**base_params, **params})
            resp.raise_for_status()

        root = ET.fromstring(resp.text)

        # Check for API errors
        status = root.attrib.get('Status')
        if status != 'OK':
            errors = root.findall('.//Error')
            error_msg = '; '.join(e.text for e in errors)
            raise Exception(f"Namecheap API error: {error_msg}")

        return root

    def _parse_domain(self, domain: str) -> tuple[str, str]:
        """Split domain into SLD and TLD."""
        parts = domain.split('.')
        if len(parts) < 2:
            raise ValueError(f"Invalid domain: {domain}")

        # Handle common TLDs
        if len(parts) == 2:
            return parts[0], parts[1]

        # Handle .co.uk, .com.tr, etc.
        common_second_level = ['co', 'com', 'org', 'net', 'gov', 'edu']
        if parts[-2] in common_second_level:
            return '.'.join(parts[:-2]), '.'.join(parts[-2:])

        return '.'.join(parts[:-1]), parts[-1]

    def export(self, domain: str) -> list[DNSRecord]:
        """
        Fetch current DNS records from Namecheap.
        Saves state to dns/state/<domain>.yaml
        """
        sld, tld = self._parse_domain(domain)

        root = self._api_call('namecheap.domains.dns.getHosts', {
            'SLD': sld,
            'TLD': tld
        })

        records = []
        for host in root.findall('.//host'):
            record = DNSRecord(
                type=host.attrib['Type'],
                name=host.attrib['Name'],
                content=host.attrib['Address'],
                ttl=int(host.attrib.get('TTL', 1800)),
                priority=int(host.attrib['MXPref']) if host.attrib.get('MXPref') else None
            )
            records.append(record)

        # Save state
        state = {
            'domain': domain,
            'exported_at': datetime.utcnow().isoformat(),
            'records': [r.to_dict() for r in records]
        }

        state_file = self.state_dir / f"{domain}.yaml"
        with open(state_file, 'w') as f:
            yaml.dump(state, f, default_flow_style=False)

        return records

    def _load_state(self, domain: str) -> list[DNSRecord]:
        """Load cached state, or export if not exists."""
        state_file = self.state_dir / f"{domain}.yaml"

        if not state_file.exists():
            return self.export(domain)

        with open(state_file) as f:
            state = yaml.safe_load(f)

        return [DNSRecord.from_dict(r) for r in state['records']]

    def plan(self, domain: str, desired: list[DNSRecord]) -> DNSDiff:
        """
        Compare desired records vs current state.
        Returns diff showing what will change.
        """
        current = self._load_state(domain)

        # Index current records by (type, name)
        current_map = {(r.type, r.name): r for r in current}
        desired_map = {(r.type, r.name): r for r in desired}

        to_add = []
        to_update = []
        to_delete = []
        unchanged = []

        # Check desired records
        for key, desired_record in desired_map.items():
            if key not in current_map:
                to_add.append(desired_record)
            elif current_map[key].content != desired_record.content:
                to_update.append(desired_record)
            else:
                unchanged.append(desired_record)

        # We do NOT delete records not in desired — they might be mail, verification, etc.
        # Only delete if explicitly marked (not implemented in v1)

        return DNSDiff(
            to_add=to_add,
            to_update=to_update,
            to_delete=to_delete,
            unchanged=unchanged
        )

    def apply(self, domain: str, desired: list[DNSRecord]) -> DNSResult:
        """
        SAFELY apply DNS changes.

        1. Export current records
        2. Merge desired into current (preserves unmanaged records)
        3. setHosts with full merged set
        """
        # Always export fresh before applying
        current = self.export(domain)

        # Compute what we're changing
        diff = self.plan(domain, desired)

        if not diff.has_changes:
            return DNSResult(status="unchanged", changes=diff)

        # Merge: keep all current, override/add desired
        merged_map = {(r.type, r.name): r for r in current}
        for record in desired:
            merged_map[(record.type, record.name)] = record

        merged = list(merged_map.values())

        # Build setHosts params
        sld, tld = self._parse_domain(domain)
        params = {'SLD': sld, 'TLD': tld}

        for i, record in enumerate(merged, 1):
            params[f'HostName{i}'] = record.name
            params[f'RecordType{i}'] = record.type
            params[f'Address{i}'] = record.content
            params[f'TTL{i}'] = record.ttl
            if record.priority is not None:
                params[f'MXPref{i}'] = record.priority

        # Execute
        try:
            self._api_call('namecheap.domains.dns.setHosts', params)
        except Exception as e:
            return DNSResult(status="error", changes=diff, error=str(e))

        # Update state
        self.export(domain)

        return DNSResult(status="applied", changes=diff)
```

**Test:**

```bash
# Load environment
source secrets/platform.env

# Test export (read-only, safe)
python3 -c "
from compiler.dns_namecheap import NamecheapDNS
dns = NamecheapDNS()
records = dns.export('yourdomain.com')
print(f'Found {len(records)} records')
for r in records:
    print(f'  {r.type} {r.name} -> {r.content}')
"
```

**Time:** 2 hours

---

### Step 15: Implement coolify.py

**Why:** This driver talks to Coolify's API to create applications, set environment variables, configure domains, and trigger deployments.

**Code:**

```python
# compiler/coolify.py

import os
import time
from dataclasses import dataclass
from typing import Optional
import httpx

@dataclass
class Deployment:
    id: str
    status: str
    error: Optional[str] = None

@dataclass
class Application:
    id: str
    name: str
    status: str

class CoolifyDriver:
    """
    Coolify API driver.

    API Reference: https://coolify.io/docs/api-reference/api/
    """

    def __init__(self):
        self.base_url = os.environ.get('COOLIFY_URL', '').rstrip('/')
        self.token = os.environ.get('COOLIFY_API_TOKEN')

        if not self.base_url or not self.token:
            raise ValueError("Missing COOLIFY_URL or COOLIFY_API_TOKEN")

        self.client = httpx.Client(
            base_url=self.base_url,
            headers={
                'Authorization': f'Bearer {self.token}',
                'Content-Type': 'application/json'
            },
            timeout=60
        )

    def _get(self, path: str) -> dict:
        resp = self.client.get(path)
        resp.raise_for_status()
        return resp.json()

    def _post(self, path: str, data: dict = None) -> dict:
        resp = self.client.post(path, json=data or {})
        resp.raise_for_status()
        return resp.json()

    def _patch(self, path: str, data: dict) -> dict:
        resp = self.client.patch(path, json=data)
        resp.raise_for_status()
        return resp.json()

    def _delete(self, path: str) -> dict:
        resp = self.client.delete(path)
        resp.raise_for_status()
        return resp.json()

    # ─────────────────────────────────────────────────────────────
    # Projects
    # ─────────────────────────────────────────────────────────────

    def list_projects(self) -> list[dict]:
        return self._get('/api/v1/projects')

    def get_project(self, uuid: str) -> dict:
        return self._get(f'/api/v1/projects/{uuid}')

    def create_project(self, name: str, description: str = "") -> dict:
        return self._post('/api/v1/projects', {
            'name': name,
            'description': description
        })

    def ensure_project(self, name: str) -> dict:
        """Get existing project or create new one."""
        projects = self.list_projects()
        for p in projects:
            if p.get('name') == name:
                return p
        return self.create_project(name)

    # ─────────────────────────────────────────────────────────────
    # Servers
    # ─────────────────────────────────────────────────────────────

    def list_servers(self) -> list[dict]:
        return self._get('/api/v1/servers')

    def get_server(self, uuid: str) -> dict:
        return self._get(f'/api/v1/servers/{uuid}')

    # ─────────────────────────────────────────────────────────────
    # Applications
    # ─────────────────────────────────────────────────────────────

    def list_applications(self) -> list[dict]:
        return self._get('/api/v1/applications')

    def get_application(self, uuid: str) -> dict:
        return self._get(f'/api/v1/applications/{uuid}')

    def create_application(
        self,
        project_uuid: str,
        server_uuid: str,
        environment_name: str,
        name: str,
        git_repository: str = None,
        git_branch: str = "main",
        build_pack: str = "dockerfile",
        dockerfile_path: str = "Dockerfile",
        compose_path: str = None
    ) -> dict:
        """Create a new application."""

        data = {
            'project_uuid': project_uuid,
            'server_uuid': server_uuid,
            'environment_name': environment_name,
            'name': name,
            'build_pack': build_pack,
        }

        if git_repository:
            data['git_repository'] = git_repository
            data['git_branch'] = git_branch

        if build_pack == 'dockerfile':
            data['dockerfile'] = dockerfile_path
        elif build_pack == 'dockercompose':
            data['docker_compose_location'] = compose_path or 'docker-compose.yaml'

        return self._post('/api/v1/applications', data)

    def update_application(self, uuid: str, data: dict) -> dict:
        return self._patch(f'/api/v1/applications/{uuid}', data)

    def delete_application(self, uuid: str) -> dict:
        return self._delete(f'/api/v1/applications/{uuid}')

    # ─────────────────────────────────────────────────────────────
    # Environment Variables
    # ─────────────────────────────────────────────────────────────

    def list_env_vars(self, app_uuid: str) -> list[dict]:
        return self._get(f'/api/v1/applications/{app_uuid}/envs')

    def create_env_var(self, app_uuid: str, key: str, value: str, is_secret: bool = False) -> dict:
        return self._post(f'/api/v1/applications/{app_uuid}/envs', {
            'key': key,
            'value': value,
            'is_preview': False,
            'is_build_time': False,
            'is_secret': is_secret
        })

    def update_env_var(self, app_uuid: str, env_uuid: str, value: str) -> dict:
        return self._patch(f'/api/v1/applications/{app_uuid}/envs/{env_uuid}', {
            'value': value
        })

    def set_env_vars(self, app_uuid: str, env_vars: dict[str, str], secrets: list[str] = None):
        """Set multiple environment variables, creating or updating as needed."""
        secrets = secrets or []
        existing = {e['key']: e for e in self.list_env_vars(app_uuid)}

        for key, value in env_vars.items():
            is_secret = key in secrets
            if key in existing:
                self.update_env_var(app_uuid, existing[key]['uuid'], value)
            else:
                self.create_env_var(app_uuid, key, value, is_secret)

    # ─────────────────────────────────────────────────────────────
    # Domains
    # ─────────────────────────────────────────────────────────────

    def set_domain(self, app_uuid: str, domain: str):
        """Set application domain (enables HTTPS automatically)."""
        return self.update_application(app_uuid, {
            'fqdn': f'https://{domain}'
        })

    # ─────────────────────────────────────────────────────────────
    # Deployments
    # ─────────────────────────────────────────────────────────────

    def deploy(self, app_uuid: str) -> dict:
        """Trigger deployment."""
        return self._post(f'/api/v1/applications/{app_uuid}/deploy')

    def get_deployment(self, deployment_uuid: str) -> dict:
        return self._get(f'/api/v1/deployments/{deployment_uuid}')

    def list_deployments(self, app_uuid: str) -> list[dict]:
        return self._get(f'/api/v1/applications/{app_uuid}/deployments')

    def wait_for_deployment(self, app_uuid: str, timeout: int = 300) -> Deployment:
        """Poll until deployment completes or fails."""
        start = time.time()

        while time.time() - start < timeout:
            deployments = self.list_deployments(app_uuid)
            if not deployments:
                time.sleep(5)
                continue

            latest = deployments[0]
            status = latest.get('status', 'unknown')

            if status in ('finished', 'success', 'running'):
                return Deployment(
                    id=latest.get('uuid', ''),
                    status='running'
                )
            elif status in ('failed', 'error', 'cancelled'):
                return Deployment(
                    id=latest.get('uuid', ''),
                    status='failed',
                    error=latest.get('error', 'Unknown error')
                )

            time.sleep(5)

        return Deployment(id='', status='timeout', error=f'Deployment did not complete in {timeout}s')

    # ─────────────────────────────────────────────────────────────
    # Logs
    # ─────────────────────────────────────────────────────────────

    def get_logs(self, app_uuid: str, lines: int = 100) -> str:
        """Get application logs."""
        # Note: Coolify API may have different endpoint for logs
        # This is a placeholder - verify with actual API
        try:
            resp = self._get(f'/api/v1/applications/{app_uuid}/logs')
            return resp.get('logs', '')
        except:
            return "Logs not available via API"
```

**Test:**

```bash
source secrets/platform.env

python3 -c "
from compiler.coolify import CoolifyDriver
coolify = CoolifyDriver()
projects = coolify.list_projects()
print(f'Found {len(projects)} projects')
servers = coolify.list_servers()
print(f'Found {len(servers)} servers')
"
```

**Time:** 2 hours

---

### Step 16: Implement template_renderer.py

**Why:** Converts specs into actual compose.yaml files with proper variable substitution.

**Code:**

```python
# compiler/template_renderer.py

from pathlib import Path
from typing import Optional
import yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape

from compiler.spec_loader import Spec

class TemplateRenderer:
    """Renders spec + template into deployable compose.yaml"""

    def __init__(self, templates_dir: str = "templates"):
        self.templates_dir = Path(templates_dir)
        self.apps_dir = Path("apps")
        self.apps_dir.mkdir(exist_ok=True)

        self.jinja = Environment(
            loader=FileSystemLoader(str(self.templates_dir)),
            autoescape=select_autoescape(['yaml', 'j2'])
        )

    def render(self, spec: Spec, secrets: dict[str, str]) -> Path:
        """
        Render template for spec, return path to compose.yaml

        Creates:
          apps/<id>/compose.yaml
          apps/<id>/Dockerfile (if template has one)
          apps/<id>/.env.example
        """

        # Create app directory
        app_dir = self.apps_dir / spec.id
        app_dir.mkdir(parents=True, exist_ok=True)

        # Load template defaults
        defaults_path = self.templates_dir / spec.template / "defaults.yaml"
        defaults = {}
        if defaults_path.exists():
            with open(defaults_path) as f:
                defaults = yaml.safe_load(f) or {}

        # Merge: defaults < spec.env < secrets
        env_vars = {**defaults.get('env', {}), **spec.env, **secrets}

        # Context for Jinja
        context = {
            'spec': spec,
            'env': env_vars,
            'resources': spec.resources,
            'health': spec.health,
            'storage': spec.storage,
            'depends': spec.depends,
        }

        # Render compose.yaml
        compose_template = f"{spec.template}/compose.yaml.j2"
        compose_content = self.jinja.get_template(compose_template).render(**context)

        compose_path = app_dir / "compose.yaml"
        with open(compose_path, 'w') as f:
            f.write(compose_content)

        # Render Dockerfile if exists
        dockerfile_template = self.templates_dir / spec.template / "Dockerfile.j2"
        if dockerfile_template.exists():
            dockerfile_content = self.jinja.get_template(
                f"{spec.template}/Dockerfile.j2"
            ).render(**context)

            with open(app_dir / "Dockerfile", 'w') as f:
                f.write(dockerfile_content)

        # Generate .env.example (documents required vars)
        env_example = app_dir / ".env.example"
        with open(env_example, 'w') as f:
            f.write("# Required environment variables\n")
            for key in spec.secrets.required:
                f.write(f"{key}=\n")
            f.write("\n# Optional environment variables\n")
            for key in spec.env.keys():
                if key not in spec.secrets.required:
                    f.write(f"{key}={spec.env[key]}\n")

        return compose_path

def render_template(spec: Spec, secrets: dict[str, str]) -> Path:
    """Convenience function."""
    renderer = TemplateRenderer()
    return renderer.render(spec, secrets)
```

**Time:** 1 hour

---

### Step 17: Implement `fabrik new`

**Why:** Creates a new spec from a template so you don't write YAML from scratch.

**Code:**

```python
# cli/new.py

import click
from pathlib import Path
import yaml
from datetime import datetime

TEMPLATES = ['wp-site', 'app-python', 'app-node']

@click.command()
@click.argument('template', type=click.Choice(TEMPLATES))
@click.argument('id')
@click.option('--domain', help='Domain for the service')
def new(template: str, id: str, domain: str = None):
    """Create a new spec from template."""

    specs_dir = Path("specs") / id
    spec_file = specs_dir / "spec.yaml"

    if spec_file.exists():
        click.echo(f"Error: Spec already exists: {spec_file}")
        raise click.Abort()

    specs_dir.mkdir(parents=True, exist_ok=True)

    # Base spec
    spec = {
        'id': id,
        'kind': 'service',
        'template': template,
        'expose': {
            'http': True,
            'internal_only': False
        },
        'coolify': {
            'project': 'default',
            'server': 'localhost'
        },
        'resources': {
            'memory': '256M',
            'cpu': '0.5'
        },
        'backup': {
            'enabled': True,
            'frequency': 'daily',
            'retention': 30
        }
    }

    if domain:
        spec['domain'] = domain
        spec['dns'] = {
            'provider': 'namecheap',
            'records': [
                {'type': 'A', 'name': '@', 'content': '${VPS_IP}'},
                {'type': 'A', 'name': 'www', 'content': '${VPS_IP}'}
            ]
        }

    # Template-specific defaults
    if template == 'wp-site':
        spec['env'] = {
            'WP_TITLE': id.replace('-', ' ').title(),
            'WP_ADMIN_EMAIL': 'admin@example.com'
        }
        spec['secrets'] = {
            'required': ['DATABASE_URL', 'WP_ADMIN_PASSWORD'],
            'generate': ['WP_ADMIN_PASSWORD']
        }
        spec['wordpress'] = {
            'plugins': [
                {'slug': 'limit-login-attempts-reloaded', 'activate': True},
                {'slug': 'wordpress-seo', 'activate': True}
            ],
            'disable_xmlrpc': True,
            'disable_file_edit': True
        }
        spec['health'] = {'path': '/', 'interval': '30s'}
        spec['storage'] = [
            {'name': 'uploads', 'path': '/var/www/html/wp-content/uploads', 'backup': True}
        ]
        spec['resources'] = {'memory': '512M', 'cpu': '0.5'}

    elif template == 'app-python':
        spec['env'] = {
            'LOG_LEVEL': 'info'
        }
        spec['secrets'] = {
            'required': ['DATABASE_URL', 'SECRET_KEY'],
            'generate': ['SECRET_KEY']
        }
        spec['depends'] = {
            'postgres': 'postgres-main',
            'redis': 'redis-main'
        }
        spec['health'] = {'path': '/health', 'interval': '30s'}

    elif template == 'app-node':
        spec['env'] = {
            'NODE_ENV': 'production'
        }
        spec['secrets'] = {
            'required': ['DATABASE_URL', 'SESSION_SECRET'],
            'generate': ['SESSION_SECRET']
        }
        spec['depends'] = {
            'postgres': 'postgres-main',
            'redis': 'redis-main'
        }
        spec['health'] = {'path': '/health', 'interval': '30s'}

    # Write spec
    with open(spec_file, 'w') as f:
        yaml.dump(spec, f, default_flow_style=False, sort_keys=False)

    click.echo(f"Created: {spec_file}")
    click.echo(f"Edit the spec, then run: fabrik plan {id}")

if __name__ == '__main__':
    new()
```

**Time:** 30 minutes

---

### Step 18: Implement `fabrik plan`

**Why:** Shows what will change before making changes. Critical for safety.

**Code:**

```python
# cli/plan.py

import click
import os
from pathlib import Path

from compiler.spec_loader import load_spec
from compiler.dns_namecheap import NamecheapDNS, DNSRecord
from compiler.coolify import CoolifyDriver
from compiler.secrets import ensure_secrets

def load_env():
    """Load platform environment."""
    env_file = Path("secrets/platform.env")
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key] = value

@click.command()
@click.argument('id')
def plan(id: str):
    """Show what changes will be made."""

    load_env()

    spec_path = f"specs/{id}/spec.yaml"

    click.echo(f"\n{'═' * 60}")
    click.echo(f"  FABRIK PLAN: {id}")
    click.echo(f"{'═' * 60}\n")

    # Load spec
    try:
        spec = load_spec(spec_path)
        click.echo(f"✓ Spec loaded: {spec_path}")
    except Exception as e:
        click.echo(f"✗ Failed to load spec: {e}")
        raise click.Abort()

    # Check secrets
    click.echo(f"\n{'─' * 40}")
    click.echo("SECRETS")
    click.echo(f"{'─' * 40}")

    secrets_file = Path(f"secrets/projects/{id}.env")
    existing_secrets = {}
    if secrets_file.exists():
        with open(secrets_file) as f:
            for line in f:
                if '=' in line and not line.startswith('#'):
                    k, v = line.strip().split('=', 1)
                    existing_secrets[k] = v

    for secret in spec.secrets.required:
        if secret in existing_secrets:
            click.echo(f"  ✓ {secret}: exists")
        elif secret in spec.secrets.generate:
            click.echo(f"  ~ {secret}: will generate")
        else:
            click.echo(f"  ✗ {secret}: MISSING (add to secrets/projects/{id}.env)")

    # DNS plan
    if spec.dns and spec.domain:
        click.echo(f"\n{'─' * 40}")
        click.echo(f"DNS CHANGES ({spec.domain})")
        click.echo(f"{'─' * 40}")

        try:
            dns = NamecheapDNS()
            desired_records = [
                DNSRecord(
                    type=r.type,
                    name=r.name,
                    content=r.content.replace('${VPS_IP}', os.environ.get('VPS_IP', ''))
                )
                for r in spec.dns.records
            ]
            diff = dns.plan(spec.domain, desired_records)

            if not diff.has_changes:
                click.echo("  No changes")
            else:
                for r in diff.to_add:
                    click.echo(f"  + {r.type:6} {r.name:12} → {r.content}")
                for r in diff.to_update:
                    click.echo(f"  ~ {r.type:6} {r.name:12} → {r.content}")
                for r in diff.to_delete:
                    click.echo(f"  - {r.type:6} {r.name:12}")
                click.echo(f"  = {len(diff.unchanged)} unchanged")
        except Exception as e:
            click.echo(f"  ✗ DNS plan failed: {e}")

    # Coolify plan
    click.echo(f"\n{'─' * 40}")
    click.echo("COOLIFY CHANGES")
    click.echo(f"{'─' * 40}")

    try:
        coolify = CoolifyDriver()

        # Check if app exists
        apps = coolify.list_applications()
        existing = None
        for app in apps:
            if app.get('name') == id:
                existing = app
                break

        if existing:
            click.echo(f"  ~ Update existing application: {id}")
        else:
            click.echo(f"  + Create new application: {id}")

        if spec.domain:
            click.echo(f"  + Set domain: {spec.domain}")

        env_count = len(spec.env) + len(spec.secrets.required)
        click.echo(f"  + Environment variables: {env_count}")

    except Exception as e:
        click.echo(f"  ✗ Coolify plan failed: {e}")

    # Resources
    click.echo(f"\n{'─' * 40}")
    click.echo("RESOURCES")
    click.echo(f"{'─' * 40}")
    click.echo(f"  Memory: {spec.resources.memory}")
    click.echo(f"  CPU: {spec.resources.cpu}")

    click.echo(f"\n{'═' * 60}")
    click.echo(f"Run 'fabrik apply {id}' to execute this plan")
    click.echo(f"{'═' * 60}\n")

if __name__ == '__main__':
    plan()
```

**Time:** 1 hour

---

### Step 19: Implement `fabrik apply`

**Why:** This is THE command. It executes the full deployment pipeline.

**Code:**

```python
# cli/apply.py

import click
import os
from pathlib import Path
import time

from compiler.spec_loader import load_spec
from compiler.dns_namecheap import NamecheapDNS, DNSRecord
from compiler.coolify import CoolifyDriver
from compiler.secrets import ensure_secrets
from compiler.template_renderer import render_template
from compiler.reporter import print_report, DeploymentReport

def load_env():
    """Load platform environment."""
    env_file = Path("secrets/platform.env")
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key] = value

def timestamp():
    return time.strftime("%H:%M:%S")

@click.command()
@click.argument('id')
@click.option('--yes', '-y', is_flag=True, help='Skip confirmation')
def apply(id: str, yes: bool):
    """Deploy or update a service."""

    load_env()

    spec_path = f"specs/{id}/spec.yaml"

    click.echo(f"\n[{timestamp()}] Loading spec: {spec_path}")
    spec = load_spec(spec_path)
    click.echo(f"[{timestamp()}] Validating spec... ✓")

    # Ensure secrets
    click.echo(f"[{timestamp()}] Ensuring secrets...")
    secrets = ensure_secrets(spec)
    for key in spec.secrets.generate:
        if key in secrets:
            click.echo(f"         → Generated: {key}")
    click.echo(f"         → Saved: secrets/projects/{id}.env")

    # Render template
    click.echo(f"[{timestamp()}] Rendering template...")
    compose_path = render_template(spec, secrets)
    click.echo(f"         → Created: {compose_path}")

    # Confirm
    if not yes:
        if not click.confirm(f"\nProceed with deployment?"):
            raise click.Abort()

    # DNS
    if spec.dns and spec.domain:
        click.echo(f"[{timestamp()}] Applying DNS...")
        dns = NamecheapDNS()

        vps_ip = os.environ.get('VPS_IP', '')
        desired_records = [
            DNSRecord(
                type=r.type,
                name=r.name,
                content=r.content.replace('${VPS_IP}', vps_ip),
                ttl=r.ttl
            )
            for r in spec.dns.records
        ]

        dns_result = dns.apply(spec.domain, desired_records)

        if dns_result.status == "error":
            click.echo(f"         ✗ DNS failed: {dns_result.error}")
            raise click.Abort()

        changes = dns_result.changes
        click.echo(f"         → {len(changes.to_add)} added, {len(changes.to_update)} updated, {len(changes.unchanged)} unchanged")

    # Coolify
    click.echo(f"[{timestamp()}] Configuring Coolify...")
    coolify = CoolifyDriver()

    # Ensure project
    project = coolify.ensure_project(spec.coolify.project)
    click.echo(f"         → Project: {project.get('name', spec.coolify.project)}")

    # Get server
    servers = coolify.list_servers()
    if not servers:
        click.echo("         ✗ No servers found in Coolify")
        raise click.Abort()
    server = servers[0]  # Use first server

    # Check if app exists
    apps = coolify.list_applications()
    existing = None
    for app in apps:
        if app.get('name') == id:
            existing = app
            break

    if existing:
        app_uuid = existing['uuid']
        click.echo(f"         → Updating existing application")
    else:
        # Create application
        # Note: Actual creation depends on Coolify API structure
        # This is simplified - may need adjustment based on actual API
        click.echo(f"         → Creating new application")
        app = coolify.create_application(
            project_uuid=project['uuid'],
            server_uuid=server['uuid'],
            environment_name='production',
            name=id,
            build_pack='dockercompose',
            compose_path=str(compose_path)
        )
        app_uuid = app['uuid']

    # Set environment variables
    click.echo(f"[{timestamp()}] Setting environment variables...")
    all_env = {**spec.env, **secrets}
    secret_keys = list(spec.secrets.required)
    coolify.set_env_vars(app_uuid, all_env, secrets=secret_keys)
    click.echo(f"         → {len(all_env)} variables set")

    # Set domain
    if spec.domain:
        click.echo(f"[{timestamp()}] Setting domain...")
        coolify.set_domain(app_uuid, spec.domain)
        click.echo(f"         → {spec.domain}")

    # Deploy
    click.echo(f"[{timestamp()}] Triggering deployment...")
    coolify.deploy(app_uuid)

    click.echo(f"[{timestamp()}] Waiting for deployment...")
    deployment = coolify.wait_for_deployment(app_uuid, timeout=300)

    if deployment.status != 'running':
        click.echo(f"         ✗ Deployment failed: {deployment.error}")
        raise click.Abort()

    click.echo(f"[{timestamp()}] Deployment complete ✓")

    # Report
    report = DeploymentReport(
        id=id,
        status='running',
        url=f"https://{spec.domain}" if spec.domain else None,
        health_url=f"https://{spec.domain}{spec.health.path}" if spec.domain and spec.health else None,
        secrets_path=f"secrets/projects/{id}.env",
        resources=spec.resources
    )

    print_report(report)

if __name__ == '__main__':
    apply()
```

**Additional files needed:**

```python
# compiler/secrets.py

import os
from pathlib import Path
import secrets as py_secrets

from compiler.spec_loader import Spec

def generate_secret(length: int = 32) -> str:
    """Generate a secure random secret."""
    return py_secrets.token_urlsafe(length)

def ensure_secrets(spec: Spec) -> dict[str, str]:
    """
    Ensure all required secrets exist.
    Generate any that are in the generate list.
    Returns dict of all secrets.
    """

    secrets_dir = Path("secrets/projects")
    secrets_dir.mkdir(parents=True, exist_ok=True)

    secrets_file = secrets_dir / f"{spec.id}.env"

    # Load existing
    existing = {}
    if secrets_file.exists():
        with open(secrets_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    existing[key] = value

    # Process required secrets
    result = {}
    for secret_name in spec.secrets.required:
        if secret_name in existing:
            result[secret_name] = existing[secret_name]
        elif secret_name in spec.secrets.generate:
            result[secret_name] = generate_secret()
        else:
            raise ValueError(f"Required secret {secret_name} not found and not in generate list")

    # Save
    with open(secrets_file, 'w') as f:
        for key, value in {**existing, **result}.items():
            f.write(f"{key}={value}\n")

    os.chmod(secrets_file, 0o600)

    return result
```

```python
# compiler/reporter.py

from dataclasses import dataclass
from typing import Optional
import click

@dataclass
class DeploymentReport:
    id: str
    status: str
    url: Optional[str] = None
    health_url: Optional[str] = None
    secrets_path: Optional[str] = None
    resources: Optional[dict] = None
    error: Optional[str] = None

def print_report(report: DeploymentReport):
    """Print deployment report."""

    click.echo(f"\n{'═' * 60}")
    click.echo(f"DEPLOYMENT REPORT: {report.id}")
    click.echo(f"{'═' * 60}\n")

    if report.url:
        click.echo(f"URL:          {report.url}")

    if report.health_url:
        click.echo(f"Health:       {report.health_url}")

    click.echo(f"Status:       {report.status}")

    if report.resources:
        click.echo(f"\nResources:")
        click.echo(f"  Memory:     {report.resources.memory}")
        click.echo(f"  CPU:        {report.resources.cpu}")

    if report.secrets_path:
        click.echo(f"\nSecrets:")
        click.echo(f"  Location:   {report.secrets_path}")

    click.echo(f"\nLogs:         fabrik logs {report.id}")

    click.echo(f"\n{'═' * 60}\n")
```

**Time:** 1 hour

---

### Step 20: Create app-python Template

**Why:** The first real template. Proves the template system works.

**Files:**

```yaml
# templates/app-python/defaults.yaml

env:
  LOG_LEVEL: info
  PORT: "8000"

resources:
  memory: 256M
  cpu: "0.5"

health:
  path: /health
  interval: 30s
```

```yaml
# templates/app-python/compose.yaml.j2

services:
  app:
    build:
      context: .
      dockerfile: Dockerfile
    environment:
      - DATABASE_URL=${DATABASE_URL:?}
      - REDIS_URL=${REDIS_URL:-}
      - SECRET_KEY=${SECRET_KEY:?}
      - LOG_LEVEL={{ env.get('LOG_LEVEL', 'info') }}
      - PORT={{ env.get('PORT', '8000') }}
{% for key, value in env.items() if key not in ['LOG_LEVEL', 'PORT'] %}
      - {{ key }}={{ value }}
{% endfor %}
    deploy:
      resources:
        limits:
          memory: {{ resources.memory }}
          cpus: '{{ resources.cpu }}'
{% if health %}
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:{{ env.get('PORT', '8000') }}{{ health.path }}"]
      interval: {{ health.interval }}
      timeout: 10s
      retries: 3
{% endif %}
    restart: unless-stopped
    expose:
      - "{{ env.get('PORT', '8000') }}"
```

```dockerfile
# templates/app-python/Dockerfile.j2

FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Run
EXPOSE {{ env.get('PORT', '8000') }}
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "{{ env.get('PORT', '8000') }}"]
```

**Time:** 1 hour

---

### Step 21: Deploy Hello API

**Why:** Proves the entire chain works end-to-end.

**Steps:**

**21.1: Create a test API repo**

```bash
mkdir -p ~/projects/hello-api
cd ~/projects/hello-api

# Create simple FastAPI app
cat > main.py << 'EOF'
from fastapi import FastAPI
import os

app = FastAPI()

@app.get("/")
def root():
    return {"message": "Hello from Fabrik!"}

@app.get("/health")
def health():
    return {"status": "healthy"}
EOF

cat > requirements.txt << 'EOF'
fastapi==0.104.1
uvicorn==0.24.0
EOF

# Initialize git
git init
git add .
git commit -m "Initial hello API"

# Push to GitHub (or your Git host)
# gh repo create hello-api --private --push
```

**21.2: Create spec**

```bash
cd ~/projects/fabrik
./fabrik new app-python hello-api --domain=api.yourdomain.com
```

**21.3: Edit spec**

```bash
nano specs/hello-api/spec.yaml
```

Update source to point to your Git repo:

```yaml
source:
  type: git
  repository: https://github.com/yourusername/hello-api
  branch: main
```

**21.4: Plan and apply**

```bash
./fabrik plan hello-api
./fabrik apply hello-api
```

**21.5: Verify**

Wait 2-5 minutes for DNS propagation and deployment, then:

```bash
curl https://api.yourdomain.com/health
# Should return: {"status": "healthy"}
```

**Time:** 1 hour

---

### Step 22-24: WordPress Template and Deployment

Similar process but with WordPress-specific compose template and post-deploy hooks for WP-CLI. This follows the same pattern as app-python.

**Time:** 4 hours total

---

### Step 25-26: Uptime Kuma

**Why:** Monitoring and alerting when things break.

**Steps:**

1. Create spec for Uptime Kuma
2. Deploy via Fabrik
3. Configure checks for:
   - Coolify dashboard
   - Hello API
   - WordPress site
4. Configure Slack/email alerts

**Time:** 1 hour

---

### Step 27: Test Backup and Restore

**Why:** Backups are worthless if restore doesn't work.

**Steps:**

1. Trigger manual backup of postgres-main
2. Create test data in a database
3. Delete the test data
4. Restore from backup
5. Verify test data is back

**Time:** 1 hour

---

## Phase 1 Complete

After completing all steps, you have:

```
✓ Hardened VPS (SSH, firewall, fail2ban, auto-updates)
✓ Coolify running with HTTPS
✓ Shared Postgres and Redis
✓ Automated backups to B2
✓ Fabrik CLI with 6 commands
✓ Safe DNS automation
✓ app-python template working
✓ wp-site template working
✓ One deployed Python API
✓ One deployed WordPress site
✓ Uptime monitoring with alerts
✓ Verified backup/restore
```

You can now deploy new services with:

```bash
fabrik new <template> <id> --domain=<domain>
fabrik plan <id>
fabrik apply <id>
```

---
