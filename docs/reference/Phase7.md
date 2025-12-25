## Phase 7: Multi-Server Scaling — Complete Narrative

**Status: ❌ Not Started**

---

### Progress Tracker

| Step | Task | Status |
|------|------|--------|
| 1 | Second VPS provisioned | ❌ Pending |
| 2 | Server registry in Fabrik | ❌ Pending |
| 3 | Server selection in specs | ❌ Pending |
| 4 | Shared PostgreSQL (PgBouncer) | ❌ Pending |
| 5 | Shared Redis | ❌ Pending |
| 6 | Cross-server VPN (WireGuard) | ❌ Pending |
| 7 | Centralized monitoring | ❌ Pending |
| 8 | DNS-based load distribution | ❌ Pending |
| 9 | Deployment routing | ❌ Pending |

**Completion: 0/9 tasks (0%)**

---

### What We're Building in Phase 7

By the end of Phase 7, you will have:

1. **Second VPS** provisioned and hardened
2. **Server registry** in Fabrik tracking all available servers
3. **Server selection** in specs — deploy to any server
4. **Shared PostgreSQL access** via PgBouncer connection pooling
5. **Shared Redis** accessible from both servers
6. **Cross-server networking** via WireGuard VPN
7. **Centralized monitoring** — single Grafana sees all servers
8. **DNS-based load distribution** — different sites on different servers
9. **Deployment routing** — Fabrik chooses server automatically or manually

This transforms Fabrik from "single VPS" to "scalable infrastructure" — add capacity by adding servers.

---

### Why Multi-Server?

**Current State (Single VPS):**
- All sites compete for same CPU/memory/disk
- Single point of failure
- Limited total capacity
- One server's problems affect everything

**With Multi-Server:**
- Distribute load across servers
- Isolate high-traffic sites
- Add capacity without migration
- Geographic distribution possible
- Redundancy for critical services

---

### Prerequisites

Before starting Phase 7, confirm:

```
[ ] Phase 1-6 complete
[ ] Budget for second VPS (~$20-40/month)
[ ] Second VPS provisioned (same provider recommended)
[ ] SSH access to new VPS
[ ] Domain/subdomain for new server identification
```

---

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│  FABRIK CLI                                                     │
│                                                                 │
│  fabrik apply my-site --server=greencloud-2                     │
│  fabrik servers list                                            │
│  fabrik servers status                                          │
└─────────────────────┬───────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│  SERVER REGISTRY                                                │
│                                                                 │
│  servers/                                                       │
│    greencloud-1.yaml  (primary - existing)                      │
│    greencloud-2.yaml  (secondary - new)                         │
└─────────────────────┬───────────────────────────────────────────┘
                      │
        ┌─────────────┴─────────────┐
        │                           │
        ▼                           ▼
┌───────────────────────┐   ┌───────────────────────┐
│  GREENCLOUD-1         │   │  GREENCLOUD-2         │
│  (Primary Server)     │   │  (Secondary Server)   │
│                       │   │                       │
│  IP: 172.93.160.197   │   │  IP: 172.93.160.XXX   │
│  VPN: 10.10.0.1       │   │  VPN: 10.10.0.2       │
│                       │   │                       │
│  ┌─────────────────┐  │   │  ┌─────────────────┐  │
│  │ Coolify         │  │   │  │ Coolify         │  │
│  │ (Management)    │  │   │  │ (Worker only)   │  │
│  └─────────────────┘  │   │  └─────────────────┘  │
│                       │   │                       │
│  ┌─────────────────┐  │   │  ┌─────────────────┐  │
│  │ PostgreSQL      │◄─┼───┼──│ PgBouncer       │  │
│  │ (Primary DB)    │  │   │  │ (Connection Pool)│ │
│  └─────────────────┘  │   │  └─────────────────┘  │
│                       │   │                       │
│  ┌─────────────────┐  │   │  ┌─────────────────┐  │
│  │ Redis           │◄─┼───┼──│ Apps connect    │  │
│  │ (Primary Cache) │  │   │  │ via VPN         │  │
│  └─────────────────┘  │   │  └─────────────────┘  │
│                       │   │                       │
│  ┌─────────────────┐  │   │  ┌─────────────────┐  │
│  │ Loki/Prometheus │◄─┼───┼──│ Promtail/       │  │
│  │ Grafana         │  │   │  │ Node Exporter   │  │
│  │ (Monitoring Hub)│  │   │  │ (Ship metrics)  │  │
│  └─────────────────┘  │   │  └─────────────────┘  │
│                       │   │                       │
│  ┌─────────────────┐  │   │  ┌─────────────────┐  │
│  │ Site A          │  │   │  │ Site C          │  │
│  │ Site B          │  │   │  │ Site D          │  │
│  │ API 1           │  │   │  │ API 2           │  │
│  └─────────────────┘  │   │  └─────────────────┘  │
│                       │   │                       │
└───────────┬───────────┘   └───────────┬───────────┘
            │                           │
            │      WireGuard VPN        │
            │◄─────────────────────────►│
            │      10.10.0.0/24         │
            │                           │
            └───────────┬───────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│  INTERNET                                                       │
│                                                                 │
│  site-a.com → Cloudflare → greencloud-1                         │
│  site-b.com → Cloudflare → greencloud-1                         │
│  site-c.com → Cloudflare → greencloud-2                         │
│  site-d.com → Cloudflare → greencloud-2                         │
└─────────────────────────────────────────────────────────────────┘
```

---

### Step 1: Provision Second VPS

**Why:** Add compute capacity. Same provider simplifies networking.

**Requirements:**

| Spec | Minimum | Recommended |
|------|---------|-------------|
| CPU | 2 vCPU | 4 vCPU |
| RAM | 4 GB | 8 GB |
| Disk | 80 GB SSD | 160 GB SSD |
| Network | 1 Gbps | 1 Gbps |
| Location | Same region as primary | Same datacenter |

**Steps:**

1. Order VPS from same provider (GreenCloud, Hetzner, etc.)
2. Note the IP address
3. Set hostname: `greencloud-2`

```bash
# Save new server IP
export NEW_VPS_IP="172.93.160.XXX"  # Replace with actual IP
```

**Time:** 30 minutes

---

### Step 2: Harden Second VPS

**Why:** Apply same security baseline as primary server.

**Script:**

```bash
#!/bin/bash
# scripts/harden-new-server.sh

set -e

NEW_VPS_IP=$1
SSH_USER="root"  # Initial access, will create deploy user

if [ -z "$NEW_VPS_IP" ]; then
    echo "Usage: $0 <new_vps_ip>"
    exit 1
fi

echo "=== Hardening $NEW_VPS_IP ==="

# Copy SSH key
echo "[1/8] Copying SSH key..."
ssh-copy-id -i ~/.ssh/id_rsa.pub $SSH_USER@$NEW_VPS_IP

# Run hardening commands
ssh $SSH_USER@$NEW_VPS_IP << 'ENDSSH'
set -e

echo "[2/8] Updating system..."
apt update && apt upgrade -y

echo "[3/8] Creating deploy user..."
useradd -m -s /bin/bash deploy || true
mkdir -p /home/deploy/.ssh
cp ~/.ssh/authorized_keys /home/deploy/.ssh/
chown -R deploy:deploy /home/deploy/.ssh
chmod 700 /home/deploy/.ssh
chmod 600 /home/deploy/.ssh/authorized_keys

# Add to sudo group
usermod -aG sudo deploy
echo "deploy ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/deploy

echo "[4/8] Configuring SSH..."
cat > /etc/ssh/sshd_config.d/hardening.conf << 'EOF'
PermitRootLogin no
PasswordAuthentication no
PubkeyAuthentication yes
AllowUsers deploy
MaxAuthTries 3
ClientAliveInterval 300
ClientAliveCountMax 2
EOF

systemctl restart sshd

echo "[5/8] Configuring firewall..."
apt install -y ufw
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp comment 'SSH'
ufw allow 80/tcp comment 'HTTP'
ufw allow 443/tcp comment 'HTTPS'
ufw allow 51820/udp comment 'WireGuard'
ufw --force enable

echo "[6/8] Installing fail2ban..."
apt install -y fail2ban
cat > /etc/fail2ban/jail.local << 'EOF'
[sshd]
enabled = true
port = ssh
filter = sshd
logpath = /var/log/auth.log
maxretry = 3
bantime = 3600
findtime = 600
EOF
systemctl enable fail2ban
systemctl restart fail2ban

echo "[7/8] Enabling auto-updates..."
apt install -y unattended-upgrades
dpkg-reconfigure -plow unattended-upgrades

echo "[8/8] Installing Docker..."
curl -fsSL https://get.docker.com | sh
usermod -aG docker deploy

# Configure Docker logging
mkdir -p /etc/docker
cat > /etc/docker/daemon.json << 'EOF'
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
EOF
systemctl restart docker

echo "=== Hardening complete ==="
ENDSSH

echo "=== Server hardened. Test SSH as deploy user: ==="
echo "ssh deploy@$NEW_VPS_IP"
```

**Run:**

```bash
chmod +x scripts/harden-new-server.sh
./scripts/harden-new-server.sh $NEW_VPS_IP
```

**Verify:**

```bash
# Should work
ssh deploy@$NEW_VPS_IP "docker --version"

# Should fail (root disabled)
ssh root@$NEW_VPS_IP "echo test"
```

**Time:** 1 hour

---

### Step 3: Set Up WireGuard VPN

**Why:** Secure private network between servers. Database and Redis traffic stays encrypted and private.

**Install WireGuard on Primary (greencloud-1):**

```bash
ssh deploy@$VPS_IP << 'ENDSSH'
# Install WireGuard
sudo apt install -y wireguard

# Generate keys
wg genkey | sudo tee /etc/wireguard/private.key
sudo chmod 600 /etc/wireguard/private.key
sudo cat /etc/wireguard/private.key | wg pubkey | sudo tee /etc/wireguard/public.key

# Show public key (save this)
echo "Primary public key:"
sudo cat /etc/wireguard/public.key
ENDSSH
```

**Install WireGuard on Secondary (greencloud-2):**

```bash
ssh deploy@$NEW_VPS_IP << 'ENDSSH'
# Install WireGuard
sudo apt install -y wireguard

# Generate keys
wg genkey | sudo tee /etc/wireguard/private.key
sudo chmod 600 /etc/wireguard/private.key
sudo cat /etc/wireguard/private.key | wg pubkey | sudo tee /etc/wireguard/public.key

# Show public key (save this)
echo "Secondary public key:"
sudo cat /etc/wireguard/public.key
ENDSSH
```

**Configure Primary (greencloud-1):**

```bash
# Replace SECONDARY_PUBLIC_KEY and NEW_VPS_IP with actual values
ssh deploy@$VPS_IP << 'ENDSSH'
sudo cat > /etc/wireguard/wg0.conf << 'EOF'
[Interface]
Address = 10.10.0.1/24
ListenPort = 51820
PrivateKey = <PRIMARY_PRIVATE_KEY>
PostUp = iptables -A FORWARD -i wg0 -j ACCEPT; iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE
PostDown = iptables -D FORWARD -i wg0 -j ACCEPT; iptables -t nat -D POSTROUTING -o eth0 -j MASQUERADE

[Peer]
# greencloud-2
PublicKey = <SECONDARY_PUBLIC_KEY>
AllowedIPs = 10.10.0.2/32
Endpoint = <NEW_VPS_IP>:51820
PersistentKeepalive = 25
EOF

# Insert actual private key
sudo sed -i "s|<PRIMARY_PRIVATE_KEY>|$(sudo cat /etc/wireguard/private.key)|" /etc/wireguard/wg0.conf

# Enable and start
sudo systemctl enable wg-quick@wg0
sudo systemctl start wg-quick@wg0
ENDSSH
```

**Configure Secondary (greencloud-2):**

```bash
# Replace PRIMARY_PUBLIC_KEY and VPS_IP with actual values
ssh deploy@$NEW_VPS_IP << 'ENDSSH'
sudo cat > /etc/wireguard/wg0.conf << 'EOF'
[Interface]
Address = 10.10.0.2/24
ListenPort = 51820
PrivateKey = <SECONDARY_PRIVATE_KEY>

[Peer]
# greencloud-1
PublicKey = <PRIMARY_PUBLIC_KEY>
AllowedIPs = 10.10.0.1/32, 10.10.0.0/24
Endpoint = <VPS_IP>:51820
PersistentKeepalive = 25
EOF

# Insert actual private key
sudo sed -i "s|<SECONDARY_PRIVATE_KEY>|$(sudo cat /etc/wireguard/private.key)|" /etc/wireguard/wg0.conf

# Enable and start
sudo systemctl enable wg-quick@wg0
sudo systemctl start wg-quick@wg0
ENDSSH
```

**Test VPN connectivity:**

```bash
# From primary, ping secondary
ssh deploy@$VPS_IP "ping -c 3 10.10.0.2"

# From secondary, ping primary
ssh deploy@$NEW_VPS_IP "ping -c 3 10.10.0.1"
```

**Time:** 1 hour

---

### Step 4: Create Server Registry

**Why:** Fabrik needs to know about all available servers and how to connect to them.

**Create server config schema:**

```python
# compiler/servers.py

import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum
import yaml

class ServerRole(str, Enum):
    PRIMARY = "primary"      # Runs shared services (DB, Redis, monitoring)
    WORKER = "worker"        # Runs applications only
    STANDALONE = "standalone" # Runs everything independently

class ServerStatus(str, Enum):
    ACTIVE = "active"
    MAINTENANCE = "maintenance"
    OFFLINE = "offline"

@dataclass
class ServerResources:
    cpu_cores: int
    memory_gb: float
    disk_gb: float
    
    # Current usage (updated by status check)
    cpu_used_percent: float = 0
    memory_used_percent: float = 0
    disk_used_percent: float = 0

@dataclass
class ServerConfig:
    id: str                    # greencloud-1, greencloud-2
    name: str                  # Human-readable name
    role: ServerRole
    status: ServerStatus
    
    # Connectivity
    public_ip: str
    vpn_ip: str                # WireGuard IP
    ssh_user: str = "deploy"
    ssh_port: int = 22
    
    # Coolify
    coolify_url: Optional[str] = None
    coolify_token_env: str = ""  # Environment variable name for token
    
    # Resources
    resources: ServerResources = None
    
    # Limits
    max_containers: int = 50
    reserved_memory_gb: float = 1.0  # Reserved for system
    
    # Tags for deployment routing
    tags: list[str] = field(default_factory=list)
    
    # Location
    region: str = ""
    provider: str = ""
    
    @classmethod
    def from_yaml(cls, path: str) -> 'ServerConfig':
        """Load server config from YAML file."""
        with open(path) as f:
            data = yaml.safe_load(f)
        
        # Parse nested objects
        if 'resources' in data and data['resources']:
            data['resources'] = ServerResources(**data['resources'])
        
        if 'role' in data:
            data['role'] = ServerRole(data['role'])
        
        if 'status' in data:
            data['status'] = ServerStatus(data['status'])
        
        return cls(**data)
    
    def to_yaml(self, path: str):
        """Save server config to YAML file."""
        data = {
            'id': self.id,
            'name': self.name,
            'role': self.role.value,
            'status': self.status.value,
            'public_ip': self.public_ip,
            'vpn_ip': self.vpn_ip,
            'ssh_user': self.ssh_user,
            'ssh_port': self.ssh_port,
            'coolify_url': self.coolify_url,
            'coolify_token_env': self.coolify_token_env,
            'max_containers': self.max_containers,
            'reserved_memory_gb': self.reserved_memory_gb,
            'tags': self.tags,
            'region': self.region,
            'provider': self.provider,
        }
        
        if self.resources:
            data['resources'] = {
                'cpu_cores': self.resources.cpu_cores,
                'memory_gb': self.resources.memory_gb,
                'disk_gb': self.resources.disk_gb,
            }
        
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w') as f:
            yaml.dump(data, f, default_flow_style=False)

class ServerRegistry:
    """Manage server registry."""
    
    def __init__(self, servers_dir: str = "servers"):
        self.servers_dir = Path(servers_dir)
        self._servers: dict[str, ServerConfig] = {}
        self._load_servers()
    
    def _load_servers(self):
        """Load all server configs from directory."""
        self._servers = {}
        
        if not self.servers_dir.exists():
            return
        
        for yaml_file in self.servers_dir.glob("*.yaml"):
            try:
                server = ServerConfig.from_yaml(str(yaml_file))
                self._servers[server.id] = server
            except Exception as e:
                print(f"Warning: Failed to load {yaml_file}: {e}")
    
    def get(self, server_id: str) -> Optional[ServerConfig]:
        """Get server by ID."""
        return self._servers.get(server_id)
    
    def list(self, status: ServerStatus = None, role: ServerRole = None) -> list[ServerConfig]:
        """List servers with optional filters."""
        servers = list(self._servers.values())
        
        if status:
            servers = [s for s in servers if s.status == status]
        
        if role:
            servers = [s for s in servers if s.role == role]
        
        return servers
    
    def get_active(self) -> list[ServerConfig]:
        """Get all active servers."""
        return self.list(status=ServerStatus.ACTIVE)
    
    def get_primary(self) -> Optional[ServerConfig]:
        """Get primary server."""
        primaries = self.list(role=ServerRole.PRIMARY)
        return primaries[0] if primaries else None
    
    def add(self, server: ServerConfig):
        """Add or update server in registry."""
        server.to_yaml(str(self.servers_dir / f"{server.id}.yaml"))
        self._servers[server.id] = server
    
    def remove(self, server_id: str):
        """Remove server from registry."""
        yaml_path = self.servers_dir / f"{server_id}.yaml"
        if yaml_path.exists():
            yaml_path.unlink()
        
        if server_id in self._servers:
            del self._servers[server_id]
    
    def select_server(
        self,
        preferred: str = None,
        required_memory_gb: float = 0.5,
        required_tags: list[str] = None,
        exclude: list[str] = None
    ) -> Optional[ServerConfig]:
        """
        Select best server for deployment.
        
        Priority:
        1. Preferred server if specified and available
        2. Server with most available resources
        3. Server matching required tags
        """
        
        candidates = self.get_active()
        
        # Filter by tags
        if required_tags:
            candidates = [
                s for s in candidates
                if all(tag in s.tags for tag in required_tags)
            ]
        
        # Exclude specific servers
        if exclude:
            candidates = [s for s in candidates if s.id not in exclude]
        
        if not candidates:
            return None
        
        # If preferred is specified and available, use it
        if preferred:
            for server in candidates:
                if server.id == preferred:
                    return server
        
        # Otherwise, select by available resources
        # (Would need real-time resource check here)
        # For now, just return first available
        return candidates[0]
```

**Create server config files:**

```yaml
# servers/greencloud-1.yaml

id: greencloud-1
name: GreenCloud Primary
role: primary
status: active

public_ip: 172.93.160.197
vpn_ip: 10.10.0.1
ssh_user: deploy
ssh_port: 22

coolify_url: https://coolify.yourdomain.com
coolify_token_env: COOLIFY_API_TOKEN

resources:
  cpu_cores: 4
  memory_gb: 8
  disk_gb: 160

max_containers: 50
reserved_memory_gb: 2.0

tags:
  - production
  - primary
  - database

region: us-central
provider: greencloud
```

```yaml
# servers/greencloud-2.yaml

id: greencloud-2
name: GreenCloud Secondary
role: worker
status: active

public_ip: 172.93.160.XXX  # Replace with actual IP
vpn_ip: 10.10.0.2
ssh_user: deploy
ssh_port: 22

coolify_url: https://coolify2.yourdomain.com
coolify_token_env: COOLIFY2_API_TOKEN

resources:
  cpu_cores: 4
  memory_gb: 8
  disk_gb: 160

max_containers: 50
reserved_memory_gb: 1.0

tags:
  - production
  - worker

region: us-central
provider: greencloud
```

**Time:** 1 hour

---

### Step 5: Install Coolify on Secondary Server

**Why:** Each server needs Coolify to manage its containers.

**Install Coolify:**

```bash
ssh deploy@$NEW_VPS_IP << 'ENDSSH'
# Install Coolify
curl -fsSL https://cdn.coollabs.io/coolify/install.sh | sudo bash

echo "Coolify installed. Access at: http://$NEW_VPS_IP:8000"
echo "Complete setup in browser, then get API token."
ENDSSH
```

**Post-installation:**

1. Access Coolify at `http://$NEW_VPS_IP:8000`
2. Complete initial setup (create admin account)
3. Generate API token: Settings → API Tokens
4. Save token:

```bash
echo "COOLIFY2_API_TOKEN=your_token_here" >> secrets/platform.env
```

**Configure Coolify domain (optional):**

```bash
# Add DNS record for coolify2.yourdomain.com
fabrik dns add yourdomain.com --type=A --name=coolify2 --content=$NEW_VPS_IP --proxy
```

**Time:** 1 hour

---

### Step 6: Configure Shared Database Access

**Why:** Secondary server applications need access to PostgreSQL on primary server.

**Option A: Direct PostgreSQL access via VPN (simpler):**

```bash
# On primary server, configure PostgreSQL to listen on VPN interface
ssh deploy@$VPS_IP << 'ENDSSH'
# Edit PostgreSQL config (inside container or host)
# Add VPN network to pg_hba.conf

# If PostgreSQL is in Docker, we need to expose it on VPN interface
# This depends on your Coolify setup

# For Coolify-managed PostgreSQL, add environment variable:
# POSTGRES_HOST_AUTH_METHOD=md5

# And expose port 5432 on VPN network only
ENDSSH
```

**Option B: PgBouncer on secondary (recommended for production):**

**Why PgBouncer:** Connection pooling reduces database connection overhead. Essential when many applications share one database.

**Deploy PgBouncer on secondary:**

```yaml
# apps/pgbouncer/compose.yaml (for greencloud-2)

services:
  pgbouncer:
    image: edoburu/pgbouncer:1.21.0
    ports:
      - "6432:6432"
    environment:
      - DATABASE_URL=postgres://postgres:${POSTGRES_PASSWORD}@10.10.0.1:5432/postgres
      - POOL_MODE=transaction
      - MAX_CLIENT_CONN=100
      - DEFAULT_POOL_SIZE=20
      - MIN_POOL_SIZE=5
      - RESERVE_POOL_SIZE=5
      - RESERVE_POOL_TIMEOUT=3
      - SERVER_RESET_QUERY=DISCARD ALL
      - AUTH_TYPE=md5
    volumes:
      - ./pgbouncer.ini:/etc/pgbouncer/pgbouncer.ini:ro
      - ./userlist.txt:/etc/pgbouncer/userlist.txt:ro
    deploy:
      resources:
        limits:
          memory: 64M
          cpus: '0.25'
    restart: unless-stopped
    networks:
      - internal

networks:
  internal:
    external: true
```

**Create PgBouncer config:**

```ini
# apps/pgbouncer/pgbouncer.ini

[databases]
* = host=10.10.0.1 port=5432

[pgbouncer]
listen_addr = 0.0.0.0
listen_port = 6432
auth_type = md5
auth_file = /etc/pgbouncer/userlist.txt
pool_mode = transaction
max_client_conn = 100
default_pool_size = 20
min_pool_size = 5
reserve_pool_size = 5
reserve_pool_timeout = 3
server_reset_query = DISCARD ALL
log_connections = 0
log_disconnections = 0
log_pooler_errors = 1
stats_period = 60
```

```
# apps/pgbouncer/userlist.txt
# Format: "username" "password"
"postgres" "your_postgres_password"
"app_user" "app_password"
```

**Deploy:**

```bash
# Deploy PgBouncer on secondary server
fabrik apply pgbouncer --server=greencloud-2
```

**Time:** 1 hour

---

### Step 7: Configure Shared Redis Access

**Why:** Applications on secondary server need access to Redis cache on primary.

**Expose Redis on VPN (primary server):**

```bash
# Modify Redis deployment to listen on VPN interface
# This depends on how Redis is deployed in Coolify

# Option 1: Update Redis container to bind to 10.10.0.1
# Option 2: Use Docker network that includes VPN interface
```

**Create Redis proxy on secondary (if needed):**

```yaml
# apps/redis-proxy/compose.yaml (for greencloud-2)

services:
  redis-proxy:
    image: haproxy:2.8
    ports:
      - "6379:6379"
    volumes:
      - ./haproxy.cfg:/usr/local/etc/haproxy/haproxy.cfg:ro
    deploy:
      resources:
        limits:
          memory: 32M
          cpus: '0.1'
    restart: unless-stopped
    networks:
      - internal

networks:
  internal:
    external: true
```

```
# apps/redis-proxy/haproxy.cfg

defaults
    mode tcp
    timeout connect 5s
    timeout client 30s
    timeout server 30s

frontend redis_front
    bind *:6379
    default_backend redis_back

backend redis_back
    server redis1 10.10.0.1:6379 check
```

**Alternative: Direct connection via VPN:**

Applications on secondary server can connect directly to `10.10.0.1:6379` if Redis is exposed on VPN network.

**Time:** 30 minutes

---

### Step 8: Update Spec Format for Server Selection

**Why:** Specs need to specify which server to deploy to.

**Update spec schema:**

```python
# Update compiler/spec_loader.py

class CoolifyConfig(BaseModel):
    project: str = "ozgur"
    server: str = "greencloud-1"  # NEW: Server ID
    compose_path: Optional[str] = None

class Spec(BaseModel):
    # ... existing fields ...
    
    coolify: CoolifyConfig = Field(default_factory=CoolifyConfig)
    
    # Server can also be specified at top level for convenience
    server: Optional[str] = None  # Overrides coolify.server if set
    
    def get_server_id(self) -> str:
        """Get effective server ID."""
        return self.server or self.coolify.server or "greencloud-1"
```

**Updated spec format:**

```yaml
# specs/client-site/spec.yaml

id: client-site
kind: service
template: wp-site
environment: production

domain: client.com

# Server selection (choose one)
server: greencloud-2  # Deploy to secondary server

# Or via coolify config
coolify:
  project: clients
  server: greencloud-2
  compose_path: apps/client-site/compose.yaml

# ... rest of spec ...
```

**Time:** 30 minutes

---

### Step 9: Update Apply Command for Multi-Server

**Why:** Apply command needs to route deployment to correct server.

**Code:**

```python
# compiler/deployment.py

import os
from compiler.servers import ServerRegistry, ServerConfig
from compiler.spec_loader import Spec
from compiler.coolify import CoolifyAPI

class DeploymentRouter:
    """Route deployments to appropriate servers."""
    
    def __init__(self):
        self.registry = ServerRegistry()
    
    def get_server_for_spec(self, spec: Spec) -> ServerConfig:
        """
        Determine which server to deploy spec to.
        
        Priority:
        1. Explicit server in spec
        2. Existing deployment location (for updates)
        3. Auto-select based on resources
        """
        
        # Check explicit server selection
        server_id = spec.get_server_id()
        
        if server_id:
            server = self.registry.get(server_id)
            if server:
                return server
            else:
                raise ValueError(f"Server not found: {server_id}")
        
        # Auto-select server
        return self.registry.select_server(
            required_memory_gb=self._estimate_memory(spec)
        )
    
    def _estimate_memory(self, spec: Spec) -> float:
        """Estimate memory requirement from spec."""
        if spec.resources and spec.resources.memory:
            # Parse "512M" -> 0.5
            mem = spec.resources.memory
            if mem.endswith('M'):
                return float(mem[:-1]) / 1024
            elif mem.endswith('G'):
                return float(mem[:-1])
        
        # Defaults by template
        defaults = {
            'wp-site': 0.5,
            'app-python': 0.25,
            'app-node': 0.25,
        }
        
        return defaults.get(spec.template, 0.25)
    
    def get_coolify_client(self, server: ServerConfig) -> CoolifyAPI:
        """Get Coolify API client for server."""
        
        token = os.environ.get(server.coolify_token_env)
        if not token:
            raise ValueError(f"Missing Coolify token: {server.coolify_token_env}")
        
        return CoolifyAPI(
            base_url=server.coolify_url,
            token=token
        )
    
    def get_database_url(self, spec: Spec, server: ServerConfig) -> str:
        """
        Get database URL based on server location.
        
        - Primary server: Direct connection
        - Worker server: Via VPN or PgBouncer
        """
        
        primary = self.registry.get_primary()
        
        if server.id == primary.id:
            # Direct connection on primary
            return f"postgres://postgres:${{POSTGRES_PASSWORD}}@postgres-main:5432/{spec.database_name}"
        else:
            # Connection via VPN to primary
            return f"postgres://postgres:${{POSTGRES_PASSWORD}}@{primary.vpn_ip}:5432/{spec.database_name}"
    
    def get_redis_url(self, spec: Spec, server: ServerConfig) -> str:
        """Get Redis URL based on server location."""
        
        primary = self.registry.get_primary()
        
        if server.id == primary.id:
            return "redis://redis-main:6379"
        else:
            return f"redis://{primary.vpn_ip}:6379"
```

**Update apply.py:**

```python
# cli/apply.py (updated for multi-server)

import click
from compiler.spec_loader import load_spec
from compiler.deployment import DeploymentRouter
from compiler.template_renderer import render_template

@click.command()
@click.argument('site_id')
@click.option('--server', '-s', help='Override server selection')
@click.option('--skip-plan', is_flag=True, help='Skip plan confirmation')
def apply(site_id, server, skip_plan):
    """Deploy a site from its spec."""
    
    # Load spec
    spec = load_spec(f"specs/{site_id}/spec.yaml")
    
    # Override server if specified
    if server:
        spec.server = server
    
    # Get deployment router
    router = DeploymentRouter()
    
    # Determine target server
    target_server = router.get_server_for_spec(spec)
    
    click.echo(f"\nDeploying {site_id}")
    click.echo(f"  Server: {target_server.name} ({target_server.id})")
    click.echo(f"  IP: {target_server.public_ip}")
    click.echo("-" * 50)
    
    # Get server-specific URLs
    database_url = router.get_database_url(spec, target_server)
    redis_url = router.get_redis_url(spec, target_server)
    
    # Add to environment
    extra_env = {
        'DATABASE_URL': database_url,
        'REDIS_URL': redis_url,
    }
    
    # Render templates
    compose_path = render_template(spec, extra_env=extra_env)
    
    # Get Coolify client for target server
    coolify = router.get_coolify_client(target_server)
    
    # Plan deployment
    plan = coolify.plan(spec, compose_path)
    
    if not skip_plan:
        click.echo("\nPlan:")
        click.echo(plan.summary())
        
        if not click.confirm("\nApply?"):
            raise click.Abort()
    
    # Apply deployment
    click.echo("\nApplying...")
    result = coolify.apply(spec, compose_path)
    
    # Update DNS to point to target server
    if spec.domain and spec.dns:
        from compiler.dns_cloudflare import CloudflareDNS
        
        dns = CloudflareDNS()
        
        # Update A record to target server IP
        dns_result = dns.apply(
            spec.domain,
            [{'type': 'A', 'name': '@', 'content': target_server.public_ip, 'proxied': True}]
        )
        
        click.echo(f"  DNS: Updated to {target_server.public_ip}")
    
    click.echo(f"\n✓ Deployed to {target_server.name}")
    click.echo(f"  URL: https://{spec.domain}")
```

**Time:** 2 hours

---

### Step 10: Set Up Centralized Monitoring

**Why:** Single Grafana dashboard should show metrics from all servers.

**Configure Prometheus on primary to scrape secondary:**

```yaml
# Update apps/prometheus/prometheus-config.yaml

global:
  scrape_interval: 15s

scrape_configs:
  # Local metrics (greencloud-1)
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']

  - job_name: 'node-greencloud-1'
    static_configs:
      - targets: ['node-exporter:9100']
        labels:
          server: greencloud-1

  - job_name: 'cadvisor-greencloud-1'
    static_configs:
      - targets: ['cadvisor:8080']
        labels:
          server: greencloud-1

  # Remote metrics (greencloud-2) via VPN
  - job_name: 'node-greencloud-2'
    static_configs:
      - targets: ['10.10.0.2:9100']
        labels:
          server: greencloud-2

  - job_name: 'cadvisor-greencloud-2'
    static_configs:
      - targets: ['10.10.0.2:8080']
        labels:
          server: greencloud-2
```

**Deploy Node Exporter and cAdvisor on secondary:**

```bash
# Create compose file for monitoring agents on secondary
cat > apps/monitoring-agents/compose.yaml << 'EOF'
services:
  node-exporter:
    image: prom/node-exporter:v1.6.1
    command:
      - '--path.procfs=/host/proc'
      - '--path.rootfs=/rootfs'
      - '--path.sysfs=/host/sys'
      - '--collector.filesystem.mount-points-exclude=^/(sys|proc|dev|host|etc)($$|/)'
    ports:
      - "9100:9100"
    volumes:
      - /proc:/host/proc:ro
      - /sys:/host/sys:ro
      - /:/rootfs:ro
    restart: unless-stopped

  cadvisor:
    image: gcr.io/cadvisor/cadvisor:v0.47.2
    privileged: true
    ports:
      - "8080:8080"
    volumes:
      - /:/rootfs:ro
      - /var/run:/var/run:ro
      - /sys:/sys:ro
      - /var/lib/docker/:/var/lib/docker:ro
      - /dev/disk/:/dev/disk:ro
    restart: unless-stopped
EOF

# Deploy on secondary server
fabrik apply monitoring-agents --server=greencloud-2
```

**Configure Promtail on secondary to ship to primary Loki:**

```yaml
# apps/promtail-secondary/promtail-config.yaml

server:
  http_listen_port: 9080
  grpc_listen_port: 0

positions:
  filename: /tmp/positions.yaml

clients:
  # Ship logs to primary server's Loki via VPN
  - url: http://10.10.0.1:3100/loki/api/v1/push

scrape_configs:
  - job_name: containers
    static_configs:
      - targets:
          - localhost
        labels:
          job: containerlogs
          server: greencloud-2  # Add server label
          __path__: /var/lib/docker/containers/*/*log

    pipeline_stages:
      - json:
          expressions:
            output: log
            stream: stream
            timestamp: time
      - labels:
          stream:
      - output:
          source: output
```

**Update Grafana dashboards to show server selector:**

```python
# Add server variable to dashboards

def add_server_variable(dashboard: dict) -> dict:
    """Add server selector variable to dashboard."""
    
    if 'templating' not in dashboard:
        dashboard['templating'] = {'list': []}
    
    server_var = {
        'name': 'server',
        'type': 'query',
        'datasource': {'type': 'prometheus', 'uid': 'prometheus'},
        'query': 'label_values(node_uname_info, server)',
        'refresh': 2,
        'includeAll': True,
        'multi': True,
        'current': {'selected': True, 'text': 'All', 'value': '$__all'}
    }
    
    dashboard['templating']['list'].insert(0, server_var)
    
    # Update panel queries to filter by server
    for panel in dashboard.get('panels', []):
        for target in panel.get('targets', []):
            if 'expr' in target and 'server=' not in target['expr']:
                # Add server filter to PromQL
                target['expr'] = target['expr'].replace(
                    '{',
                    '{server=~"$server",'
                )
    
    return dashboard
```

**Time:** 2 hours

---

### Step 11: CLI Commands for Server Management

**Why:** Easy management of multi-server infrastructure.

**Code:**

```python
# cli/servers.py

import click
import os
from pathlib import Path
import subprocess

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
def servers():
    """Server management commands."""
    load_env()

# ─────────────────────────────────────────────────────────────
# List and Status
# ─────────────────────────────────────────────────────────────

@servers.command('list')
@click.option('--status', type=click.Choice(['active', 'maintenance', 'offline']))
@click.option('--role', type=click.Choice(['primary', 'worker', 'standalone']))
def list_servers(status, role):
    """List all registered servers."""
    
    from compiler.servers import ServerRegistry, ServerStatus, ServerRole
    
    registry = ServerRegistry()
    
    status_filter = ServerStatus(status) if status else None
    role_filter = ServerRole(role) if role else None
    
    servers_list = registry.list(status=status_filter, role=role_filter)
    
    if not servers_list:
        click.echo("No servers found.")
        return
    
    click.echo("\n" + "=" * 80)
    click.echo(f"  {'ID':<20} {'NAME':<20} {'ROLE':<12} {'STATUS':<12} {'IP':<15}")
    click.echo("=" * 80)
    
    for server in servers_list:
        status_color = {
            'active': 'green',
            'maintenance': 'yellow',
            'offline': 'red'
        }.get(server.status.value, 'white')
        
        status_str = click.style(server.status.value, fg=status_color)
        
        click.echo(f"  {server.id:<20} {server.name:<20} {server.role.value:<12} {status_str:<12} {server.public_ip:<15}")
    
    click.echo("=" * 80 + "\n")

@servers.command('status')
@click.argument('server_id', required=False)
def status(server_id):
    """Show detailed server status."""
    
    from compiler.servers import ServerRegistry
    import httpx
    
    registry = ServerRegistry()
    
    if server_id:
        servers_list = [registry.get(server_id)]
        if not servers_list[0]:
            click.echo(f"Server not found: {server_id}")
            raise click.Abort()
    else:
        servers_list = registry.get_active()
    
    for server in servers_list:
        click.echo(f"\n{'=' * 60}")
        click.echo(f"  {server.name} ({server.id})")
        click.echo(f"{'=' * 60}")
        
        click.echo(f"  Role:       {server.role.value}")
        click.echo(f"  Status:     {server.status.value}")
        click.echo(f"  Public IP:  {server.public_ip}")
        click.echo(f"  VPN IP:     {server.vpn_ip}")
        click.echo(f"  Region:     {server.region}")
        click.echo(f"  Provider:   {server.provider}")
        
        # Check connectivity
        click.echo(f"\n  Connectivity:")
        
        # SSH check
        ssh_result = subprocess.run(
            ['ssh', '-o', 'ConnectTimeout=5', '-o', 'BatchMode=yes',
             f'{server.ssh_user}@{server.public_ip}', 'echo ok'],
            capture_output=True, text=True
        )
        ssh_ok = ssh_result.returncode == 0
        click.echo(f"    SSH:      {click.style('✓' if ssh_ok else '✗', fg='green' if ssh_ok else 'red')}")
        
        # VPN check
        vpn_result = subprocess.run(
            ['ping', '-c', '1', '-W', '2', server.vpn_ip],
            capture_output=True
        )
        vpn_ok = vpn_result.returncode == 0
        click.echo(f"    VPN:      {click.style('✓' if vpn_ok else '✗', fg='green' if vpn_ok else 'red')}")
        
        # Coolify check
        if server.coolify_url:
            try:
                resp = httpx.get(f"{server.coolify_url}/api/v1/healthcheck", timeout=5)
                coolify_ok = resp.status_code == 200
            except:
                coolify_ok = False
            click.echo(f"    Coolify:  {click.style('✓' if coolify_ok else '✗', fg='green' if coolify_ok else 'red')}")
        
        # Get system metrics if Prometheus available
        prometheus_url = os.environ.get('PROMETHEUS_URL', 'http://localhost:9090')
        
        try:
            queries = {
                'CPU': f'100 - (avg(irate(node_cpu_seconds_total{{mode="idle",server="{server.id}"}}[5m])) * 100)',
                'Memory': f'(1 - (node_memory_MemAvailable_bytes{{server="{server.id}"}} / node_memory_MemTotal_bytes{{server="{server.id}"}})) * 100',
                'Disk': f'(1 - (node_filesystem_avail_bytes{{mountpoint="/",server="{server.id}"}} / node_filesystem_size_bytes{{mountpoint="/",server="{server.id}"}})) * 100',
            }
            
            click.echo(f"\n  Resources:")
            
            for name, query in queries.items():
                resp = httpx.get(
                    f'{prometheus_url}/api/v1/query',
                    params={'query': query},
                    timeout=5
                )
                data = resp.json()
                results = data.get('data', {}).get('result', [])
                
                if results:
                    value = float(results[0]['value'][1])
                    
                    if value > 90:
                        color = 'red'
                    elif value > 70:
                        color = 'yellow'
                    else:
                        color = 'green'
                    
                    click.echo(f"    {name:<10} {click.style(f'{value:.1f}%', fg=color)}")
                else:
                    click.echo(f"    {name:<10} N/A")
        
        except Exception as e:
            click.echo(f"\n  Resources: Unable to fetch ({e})")
        
        # Count containers
        try:
            ssh_cmd = f"ssh {server.ssh_user}@{server.public_ip} 'docker ps -q | wc -l'"
            result = subprocess.run(ssh_cmd, shell=True, capture_output=True, text=True)
            container_count = int(result.stdout.strip())
            click.echo(f"\n  Containers: {container_count}")
        except:
            pass
    
    click.echo("")

# ─────────────────────────────────────────────────────────────
# Add and Remove
# ─────────────────────────────────────────────────────────────

@servers.command('add')
@click.option('--id', 'server_id', required=True, help='Unique server ID')
@click.option('--name', required=True, help='Human-readable name')
@click.option('--ip', 'public_ip', required=True, help='Public IP address')
@click.option('--vpn-ip', required=True, help='WireGuard VPN IP')
@click.option('--role', type=click.Choice(['primary', 'worker', 'standalone']), default='worker')
@click.option('--coolify-url', help='Coolify dashboard URL')
@click.option('--coolify-token-env', help='Environment variable name for Coolify token')
def add(server_id, name, public_ip, vpn_ip, role, coolify_url, coolify_token_env):
    """Add a new server to the registry."""
    
    from compiler.servers import ServerRegistry, ServerConfig, ServerRole, ServerStatus, ServerResources
    
    registry = ServerRegistry()
    
    # Check if exists
    if registry.get(server_id):
        click.echo(f"Server already exists: {server_id}")
        raise click.Abort()
    
    server = ServerConfig(
        id=server_id,
        name=name,
        role=ServerRole(role),
        status=ServerStatus.ACTIVE,
        public_ip=public_ip,
        vpn_ip=vpn_ip,
        coolify_url=coolify_url,
        coolify_token_env=coolify_token_env or f"COOLIFY_{server_id.upper().replace('-', '_')}_TOKEN",
        resources=ServerResources(cpu_cores=4, memory_gb=8, disk_gb=160)
    )
    
    registry.add(server)
    
    click.echo(f"✓ Server added: {server_id}")
    click.echo(f"  Config saved to: servers/{server_id}.yaml")

@servers.command('remove')
@click.argument('server_id')
@click.confirmation_option(prompt='Are you sure you want to remove this server?')
def remove(server_id):
    """Remove a server from the registry."""
    
    from compiler.servers import ServerRegistry
    
    registry = ServerRegistry()
    
    if not registry.get(server_id):
        click.echo(f"Server not found: {server_id}")
        raise click.Abort()
    
    registry.remove(server_id)
    
    click.echo(f"✓ Server removed: {server_id}")

# ─────────────────────────────────────────────────────────────
# Maintenance
# ─────────────────────────────────────────────────────────────

@servers.command('maintenance')
@click.argument('server_id')
@click.option('--enable/--disable', default=True)
def maintenance(server_id, enable):
    """Enable or disable maintenance mode for a server."""
    
    from compiler.servers import ServerRegistry, ServerStatus
    
    registry = ServerRegistry()
    server = registry.get(server_id)
    
    if not server:
        click.echo(f"Server not found: {server_id}")
        raise click.Abort()
    
    new_status = ServerStatus.MAINTENANCE if enable else ServerStatus.ACTIVE
    server.status = new_status
    registry.add(server)  # Save updated config
    
    action = "enabled" if enable else "disabled"
    click.echo(f"✓ Maintenance mode {action} for {server_id}")

# ─────────────────────────────────────────────────────────────
# SSH and Shell
# ─────────────────────────────────────────────────────────────

@servers.command('ssh')
@click.argument('server_id')
def ssh(server_id):
    """SSH into a server."""
    
    from compiler.servers import ServerRegistry
    
    registry = ServerRegistry()
    server = registry.get(server_id)
    
    if not server:
        click.echo(f"Server not found: {server_id}")
        raise click.Abort()
    
    import subprocess
    subprocess.run(['ssh', f'{server.ssh_user}@{server.public_ip}'])

@servers.command('exec')
@click.argument('server_id')
@click.argument('command', nargs=-1)
def exec_cmd(server_id, command):
    """Execute a command on a server."""
    
    from compiler.servers import ServerRegistry
    
    registry = ServerRegistry()
    server = registry.get(server_id)
    
    if not server:
        click.echo(f"Server not found: {server_id}")
        raise click.Abort()
    
    cmd_str = ' '.join(command)
    
    import subprocess
    result = subprocess.run(
        ['ssh', f'{server.ssh_user}@{server.public_ip}', cmd_str],
        capture_output=False
    )

# ─────────────────────────────────────────────────────────────
# Deployments
# ─────────────────────────────────────────────────────────────

@servers.command('deployments')
@click.argument('server_id')
def deployments(server_id):
    """List deployments on a server."""
    
    from compiler.servers import ServerRegistry
    from compiler.spec_loader import load_spec
    from pathlib import Path
    
    registry = ServerRegistry()
    server = registry.get(server_id)
    
    if not server:
        click.echo(f"Server not found: {server_id}")
        raise click.Abort()
    
    # Find specs deployed to this server
    specs_dir = Path("specs")
    deployed = []
    
    for spec_path in specs_dir.glob("*/spec.yaml"):
        try:
            spec = load_spec(str(spec_path))
            if spec.get_server_id() == server_id:
                deployed.append({
                    'id': spec.id,
                    'template': spec.template,
                    'domain': spec.domain,
                    'environment': spec.environment.value
                })
        except:
            continue
    
    if not deployed:
        click.echo(f"No deployments found on {server_id}")
        return
    
    click.echo(f"\nDeployments on {server_id}:")
    click.echo("-" * 60)
    
    for d in deployed:
        click.echo(f"  {d['id']:<25} {d['template']:<15} {d['domain'] or 'N/A'}")

if __name__ == '__main__':
    servers()
```

**Update main CLI:**

```python
# cli/main.py - add server commands

from cli.servers import servers

cli.add_command(servers)
```

**Time:** 2 hours

---

### Phase 7 Complete

After completing all steps, you have:

```
✓ Second VPS provisioned and hardened
✓ WireGuard VPN connecting servers
✓ Server registry tracking all servers
✓ Server selection in specs
✓ Shared PostgreSQL via VPN
✓ Shared Redis via VPN
✓ PgBouncer for connection pooling
✓ Centralized monitoring (all servers → single Grafana)
✓ CLI commands for server management
```

**New CLI commands:**

```bash
# List servers
fabrik servers list
fabrik servers list --status=active
fabrik servers list --role=worker

# Server status
fabrik servers status
fabrik servers status greencloud-2

# Add server
fabrik servers add \
  --id=greencloud-3 \
  --name="GreenCloud Tertiary" \
  --ip=172.93.160.YYY \
  --vpn-ip=10.10.0.3 \
  --role=worker \
  --coolify-url=https://coolify3.yourdomain.com

# Remove server
fabrik servers remove greencloud-3

# Maintenance mode
fabrik servers maintenance greencloud-2 --enable
fabrik servers maintenance greencloud-2 --disable

# SSH into server
fabrik servers ssh greencloud-2

# Execute command on server
fabrik servers exec greencloud-2 "docker ps"

# List deployments on server
fabrik servers deployments greencloud-2
```

**Deploy to specific server:**

```bash
# Explicit server selection
fabrik apply my-site --server=greencloud-2

# Or in spec
# specs/my-site/spec.yaml
# server: greencloud-2
```

---

### Deployment Distribution Example

```
┌─────────────────────────────────────────────────────────────────┐
│  GREENCLOUD-1 (Primary)                                         │
│                                                                 │
│  Shared Services:                                               │
│    - PostgreSQL (database)                                      │
│    - Redis (cache)                                              │
│    - Loki + Prometheus + Grafana (monitoring)                   │
│                                                                 │
│  Applications:                                                  │
│    - coolify (management)                                       │
│    - uptime-kuma (uptime monitoring)                            │
│    - client-site-1 (WordPress)                                  │
│    - client-site-2 (WordPress)                                  │
│    - internal-api (FastAPI)                                     │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  GREENCLOUD-2 (Worker)                                          │
│                                                                 │
│  Local Services:                                                │
│    - PgBouncer (connection pooling)                             │
│    - Promtail + Node Exporter (metrics shipping)                │
│                                                                 │
│  Applications:                                                  │
│    - client-site-3 (high-traffic WordPress)                     │
│    - client-site-4 (WordPress)                                  │
│    - public-api (high-traffic FastAPI)                          │
│    - worker-jobs (background processing)                        │
└─────────────────────────────────────────────────────────────────┘
```

---

### When to Add Another Server

**Add server when:**
- Memory usage consistently >70%
- CPU usage consistently >60%
- Disk usage >80%
- Single site needs isolation (high traffic, security)
- Geographic distribution needed
- Redundancy required for critical services

**Server sizing guide:**

| Use Case | Recommended Spec |
|----------|------------------|
| 5-10 WordPress sites | 4 CPU, 8 GB RAM |
| High-traffic single site | 4 CPU, 8 GB RAM (dedicated) |
| API services cluster | 2 CPU, 4 GB RAM |
| Background workers | 2 CPU, 4 GB RAM |

---

### Phase 7 Summary

| Step | Task | Time |
|------|------|------|
| 1 | Provision second VPS | 30 min |
| 2 | Harden second VPS | 1 hr |
| 3 | Set up WireGuard VPN | 1 hr |
| 4 | Create server registry | 1 hr |
| 5 | Install Coolify on secondary | 1 hr |
| 6 | Configure shared database access | 1 hr |
| 7 | Configure shared Redis access | 30 min |
| 8 | Update spec format for server selection | 30 min |
| 9 | Update apply command for multi-server | 2 hrs |
| 10 | Set up centralized monitoring | 2 hrs |
| 11 | CLI commands for server management | 2 hrs |

**Total: ~11 hours (2 days)**

---

### What's Next (Phase 8 Preview)

Phase 8 adds business automation with n8n:
- Deploy n8n workflow automation
- Lead capture → CRM workflows
- Form submission → notifications
- Scheduled reports and alerts
- Integration with external services

---