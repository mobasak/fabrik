# Uptime Kuma Monitoring

Uptime Kuma monitors all VPS services for availability and sends alerts when services go down.

## Access

| Item | Value |
|------|-------|
| URL | https://status.vps1.ocoron.com |
| Auth | Password (configured in Coolify) |

## How It Works

### Detection Methods

| Type | How | Reliability |
|------|-----|-------------|
| **HTTP(S)** | GET request, expects 2xx | ✅ Very reliable |
| **Keyword** | HTTP + checks response text | ✅ Very reliable |
| **TCP Port** | Opens TCP connection | ✅ Reliable |
| **Ping** | ICMP packets | ⚠️ May be blocked |

### Check Flow

1. Uptime Kuma sends HTTP GET to health endpoint every 60 seconds
2. If response is 2xx within timeout → **UP**
3. If non-2xx, timeout, or refused → retry 3 times
4. After 3 failures → **DOWN** + send alert

### Reliability Notes

| Pro | Con |
|-----|-----|
| Low latency (runs on VPS) | Single point of failure |
| Lightweight (~50MB RAM) | Can't detect VPS-wide outages |
| Open source | No distributed monitoring |
| Alerts (Telegram, Email) | |

**Recommendation:** Add external monitor (UptimeRobot free tier) to watch Uptime Kuma itself.

## Adding New Services

### Option 1: Setup Script (Batch)

Add service to `/opt/fabrik/scripts/setup_uptime_kuma.py`:

```python
MONITORS = [
    # ... existing monitors ...
    {"name": "New Service", "type": MonitorType.HTTP, "url": "https://newservice.vps1.ocoron.com/health", "interval": 60},
]
```

Run:
```bash
cd /opt/fabrik && source .venv/bin/activate
python scripts/setup_uptime_kuma.py
```

### Option 2: Fabrik Driver (Programmatic)

```python
from fabrik.drivers.uptime_kuma import add_fabrik_service_to_monitoring

# After deployment
add_fabrik_service_to_monitoring(
    service_name="myservice",
    domain="vps1.ocoron.com",
    health_endpoint="/health"
)
```

### Option 3: UI (Manual)

1. Go to https://status.vps1.ocoron.com
2. Click "+ Add New Monitor"
3. Type: HTTP(s)
4. Name: Service Name
5. URL: https://service.vps1.ocoron.com/health
6. Interval: 60 seconds

## Current Monitors

Run to see all monitors:
```bash
cd /opt/fabrik && source .venv/bin/activate
python scripts/setup_uptime_kuma.py
```

## Environment Variables

Required in `/opt/fabrik/.env`:
```
UPTIME_KUMA_URL=https://status.vps1.ocoron.com
UPTIME_KUMA_USERNAME=<username>
UPTIME_KUMA_PASSWORD=<password>
```

## Health Endpoint Standards

All Fabrik services should expose a health endpoint:

| Pattern | Example |
|---------|---------|
| `/health` | Most services |
| `/healthz` | Captcha |
| `/api/v1/health` | Image Broker |

Response should be JSON with at least:
```json
{"status": "healthy"}
```

Better:
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "dependencies": {
    "database": "connected",
    "redis": "connected"
  }
}
```
