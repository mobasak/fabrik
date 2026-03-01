# Phase 8: n8n Business Automation

## Goal
Deploy n8n and create core workflow templates.

## DONE WHEN
- [ ] n8n accessible at auto.vps1.ocoron.com
- [ ] Admin credentials secured
- [ ] Backup notification workflow working
- [ ] Uptime alert workflow working
- [ ] Webhook test endpoint working
- [ ] Workflows exported to /opt/fabrik/configs/n8n/workflows/
- [ ] Integration with Apprise for notifications
- [ ] PORTS.md updated
- [ ] SERVICES.md updated
- [ ] CHANGELOG.md updated

## Out of Scope
- Project-specific workflows (triggered-content, ComplianceOps)
- Complex multi-step pipelines
- Custom credential stores

## Service Deployment

### n8n Service Spec
File: `/opt/fabrik/specs/infrastructure/n8n.yaml`
```yaml
name: n8n
type: docker
domain: auto.vps1.ocoron.com
image: n8nio/n8n:latest
environment:
  N8N_BASIC_AUTH_ACTIVE: "true"
  N8N_BASIC_AUTH_USER: ${N8N_USER}
  N8N_BASIC_AUTH_PASSWORD: ${N8N_PASSWORD}
  N8N_HOST: auto.vps1.ocoron.com
  N8N_PROTOCOL: https
  WEBHOOK_URL: https://auto.vps1.ocoron.com
  GENERIC_TIMEZONE: UTC
  N8N_ENCRYPTION_KEY: ${N8N_ENCRYPTION_KEY}
volumes:
  - n8n-data:/home/node/.n8n
ports:
  - "5678:5678"
networks:
  - coolify
restart: unless-stopped
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:5678/healthz"]
  interval: 30s
  timeout: 10s
  retries: 3
```

## Execution Steps

### Step 1: Verify ARM64 Support
```bash
cd /opt/fabrik && source .venv/bin/activate
python scripts/container_images.py check-arch n8nio/n8n:latest
```

### Step 2: Create Directories
```bash
mkdir -p /opt/fabrik/specs/infrastructure
mkdir -p /opt/fabrik/configs/n8n/workflows
```

### Step 3: Generate Credentials
```bash
python -c "import secrets; print(f'N8N_USER=admin')"
python -c "import secrets; print(f'N8N_PASSWORD={secrets.token_urlsafe(24)}')"
python -c "import secrets; print(f'N8N_ENCRYPTION_KEY={secrets.token_urlsafe(32)}')"
```

### Step 4: Add to /opt/fabrik/.env
```
N8N_USER=admin
N8N_PASSWORD=<generated>
N8N_ENCRYPTION_KEY=<generated>
```

### Step 5: Create Spec File
Create `/opt/fabrik/specs/infrastructure/n8n.yaml` with the spec above.

### Step 6: Deploy via Coolify
Manual deployment through Coolify UI.

### Step 7: Verify Health
```bash
curl -sf https://auto.vps1.ocoron.com/healthz
```

### Step 8: Create Workflows

#### Workflow 1: System Backup Notification
```json
{
  "name": "Backup Status Notification",
  "nodes": [
    {
      "name": "Schedule",
      "type": "n8n-nodes-base.scheduleTrigger",
      "parameters": {
        "rule": {
          "interval": [{ "field": "hours", "hoursInterval": 24 }]
        }
      }
    },
    {
      "name": "Check Backup",
      "type": "n8n-nodes-base.httpRequest",
      "parameters": {
        "url": "http://duplicati:8200/api/v1/status",
        "method": "GET"
      }
    },
    {
      "name": "Notify Success",
      "type": "n8n-nodes-base.httpRequest",
      "parameters": {
        "url": "http://apprise:8000/notify",
        "method": "POST",
        "body": {
          "urls": ["slack://..."],
          "title": "Backup Complete",
          "body": "Daily backup completed successfully"
        }
      }
    }
  ]
}
```

#### Workflow 2: Uptime Kuma Alert
```json
{
  "name": "Uptime Alert Pipeline",
  "nodes": [
    {
      "name": "Webhook",
      "type": "n8n-nodes-base.webhook",
      "parameters": {
        "path": "uptime-alert",
        "method": "POST"
      }
    },
    {
      "name": "Switch Status",
      "type": "n8n-nodes-base.switch",
      "parameters": {
        "dataPropertyName": "status",
        "rules": [
          { "value": "down" },
          { "value": "up" }
        ]
      }
    },
    {
      "name": "Alert Down",
      "type": "n8n-nodes-base.httpRequest",
      "parameters": {
        "url": "http://apprise:8000/notify",
        "method": "POST",
        "body": {
          "urls": ["slack://..."],
          "title": "🔴 Service DOWN",
          "body": "{{ $json.monitor.name }} is DOWN"
        }
      }
    },
    {
      "name": "Alert Up",
      "type": "n8n-nodes-base.httpRequest",
      "parameters": {
        "url": "http://apprise:8000/notify",
        "method": "POST",
        "body": {
          "urls": ["slack://..."],
          "title": "🟢 Service UP",
          "body": "{{ $json.monitor.name }} recovered"
        }
      }
    }
  ]
}
```

#### Workflow 3: Webhook Test
```json
{
  "name": "Webhook Test Endpoint",
  "nodes": [
    {
      "name": "Webhook",
      "type": "n8n-nodes-base.webhook",
      "parameters": {
        "path": "test",
        "method": "POST",
        "responseMode": "responseNode"
      }
    },
    {
      "name": "Respond",
      "type": "n8n-nodes-base.respondToWebhook",
      "parameters": {
        "respondWith": "json",
        "responseBody": {
          "received": true,
          "timestamp": "={{ $now.toISO() }}",
          "data": "={{ $json }}"
        }
      }
    }
  ]
}
```

### Step 9: Export Workflows
After creating workflows in n8n UI:
1. Go to each workflow → Settings → Export
2. Save JSON to `/opt/fabrik/configs/n8n/workflows/`

### Step 10: Configure Uptime Kuma Integration
In Uptime Kuma:
1. Go to Settings → Notifications
2. Add Webhook notification
3. URL: `https://auto.vps1.ocoron.com/webhook/uptime-alert`
4. Enable for all monitors

### Step 11: Update Documentation

**PORTS.md** - Add:
| Service | Port | Domain |
|---------|------|--------|
| n8n | 5678 | auto.vps1.ocoron.com |

**docs/SERVICES.md** - Add n8n service entry

**CHANGELOG.md** - Add Phase 8 completion entry

## Workflow Testing

### Test Webhook Endpoint
```bash
curl -X POST https://auto.vps1.ocoron.com/webhook/test \
  -H "Content-Type: application/json" \
  -d '{"test": "data"}'
```

Expected response:
```json
{
  "received": true,
  "timestamp": "2026-02-28T10:00:00.000Z",
  "data": {"test": "data"}
}
```

### Test Uptime Alert
Manually trigger in Uptime Kuma or:
```bash
curl -X POST https://auto.vps1.ocoron.com/webhook/uptime-alert \
  -H "Content-Type: application/json" \
  -d '{"status": "down", "monitor": {"name": "Test Service"}}'
```

## Apprise Integration

Configure Apprise notification URLs in n8n:
- Slack: `slack://tokenA/tokenB/tokenC`
- Email: `mailto://user:pass@gmail.com`
- Telegram: `tgram://bottoken/ChatID`

Store these as n8n credentials for reuse across workflows.

## Reference Files
- /opt/fabrik/docs/development/plans/previously-planned-fabrik-phases/Phase8.md

## Constraints
- n8n MUST be password protected (N8N_BASIC_AUTH_ACTIVE=true)
- Webhook URLs must use HTTPS
- Export all workflows as JSON for version control
- Follow 9-step workflow
- Requires Phase 9 Apprise deployment first for notifications
