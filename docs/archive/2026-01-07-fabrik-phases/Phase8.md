> **Phase Navigation:** [← Phase 7](Phase7.md) | **Phase 8** | [All Phases](roadmap.md)

**Status:** ✅ COMPLETE (historical implementation)
## Phase 8: Business Automation with n8n — Complete Narrative

**Status: ❌ Not Started**

---

### Progress Tracker

| Step | Task | Status |
|------|------|--------|
| 1 | Deploy n8n | ❌ Pending |
| 2 | Lead capture workflows | ❌ Pending |
| 3 | Contact form processing | ❌ Pending |
| 4 | Site monitoring alerts | ❌ Pending |
| 5 | Scheduled reports | ❌ Pending |
| 6 | Client onboarding automation | ❌ Pending |
| 7 | Backup notifications | ❌ Pending |
| 8 | Content publishing workflows | ❌ Pending |
| 9 | Webhook endpoints | ❌ Pending |
| 10 | Integration templates | ❌ Pending |

**Completion: 0/10 tasks (0%)**

---

### What We're Building in Phase 8

By the end of Phase 8, you will have:

1. **n8n deployed** as self-hosted workflow automation platform
2. **Lead capture workflows** — form submissions → CRM/notification
3. **Contact form processing** — WordPress forms → email/Slack/sheets
4. **Site monitoring alerts** — Uptime Kuma → Slack/email notifications
5. **Scheduled reports** — daily/weekly summaries of site metrics
6. **Client onboarding automation** — new site request → provisioning workflow
7. **Backup notifications** — backup success/failure alerts
8. **Content publishing workflows** — AI content review → publish pipeline
9. **Webhook endpoints** — receive events from external services
10. **Integration templates** — reusable workflow patterns

This transforms Fabrik from "deployment platform" to "full business automation system" — sites don't just run, they connect to your business processes.

---

### Why n8n?

**Comparison with alternatives:**

| Feature | n8n | Zapier | Make |
|---------|-----|--------|------|
| Self-hosted | ✓ | ✗ | ✗ |
| Cost | Free | $20+/mo | $9+/mo |
| Custom code | ✓ | Limited | Limited |
| Data privacy | Full control | Third-party | Third-party |
| Complex logic | ✓ | Limited | ✓ |
| API access | Full | Limited | Limited |

**n8n advantages for Fabrik:**
- Runs on your VPS (no external dependency)
- No per-execution costs
- Full JavaScript/Python code nodes
- Direct database access
- Webhook endpoints for integrations
- Visual workflow builder

---

### Prerequisites

Before starting Phase 8, confirm:

```
[ ] Phase 1-7 complete
[ ] At least 512MB RAM available for n8n
[ ] Domain for n8n (e.g., auto.yourdomain.com)
[ ] Slack workspace (optional, for notifications)
[ ] Email SMTP credentials (optional, for email notifications)
```

---

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│  EXTERNAL TRIGGERS                                              │
│                                                                 │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐        │
│  │WordPress │  │ Uptime   │  │ Stripe   │  │ GitHub   │        │
│  │  Forms   │  │  Kuma    │  │ Webhooks │  │ Webhooks │        │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘        │
│       │             │             │             │               │
│       └─────────────┴──────┬──────┴─────────────┘               │
│                            │                                    │
│                      Webhooks                                   │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  n8n (Workflow Automation)                                      │
│  https://auto.yourdomain.com                                    │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Workflows                                              │    │
│  │                                                         │    │
│  │  • Lead Capture → CRM + Notification                    │    │
│  │  • Contact Form → Email + Slack                         │    │
│  │  • Uptime Alert → Slack + Email                         │    │
│  │  • Daily Report → Email                                 │    │
│  │  • New Site Request → Fabrik Deploy                     │    │
│  │  • Backup Status → Notification                         │    │
│  │  • Content Review → Publish                             │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Integrations                                           │    │
│  │                                                         │    │
│  │  • Slack (notifications)                                │    │
│  │  • Email/SMTP (alerts)                                  │    │
│  │  • Google Sheets (lead tracking)                        │    │
│  │  • Airtable (CRM)                                       │    │
│  │  • Telegram (mobile alerts)                             │    │
│  │  • HTTP/SSH (Fabrik commands)                           │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────┬───────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│  ACTIONS                                                        │
│                                                                 │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐        │
│  │  Slack   │  │  Email   │  │  Sheets  │  │  Fabrik  │        │
│  │ Messages │  │  Alerts  │  │  Logging │  │ Commands │        │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘        │
└─────────────────────────────────────────────────────────────────┘
```

---

### Step 1: Deploy n8n

**Why:** Core automation platform. Self-hosted for full control and no per-execution costs.

**Create spec:**

```yaml
# specs/n8n/spec.yaml

id: n8n
kind: service
template: null
environment: production

domain: auto.yourdomain.com

source:
  type: docker
  image: n8nio/n8n:latest

expose:
  http: true
  internal_only: false

env:
  N8N_HOST: auto.yourdomain.com
  N8N_PORT: "5678"
  N8N_PROTOCOL: https
  WEBHOOK_URL: https://auto.yourdomain.com/
  N8N_BASIC_AUTH_ACTIVE: "true"
  N8N_BASIC_AUTH_USER: ${N8N_USER}
  N8N_BASIC_AUTH_PASSWORD: ${N8N_PASSWORD}
  N8N_ENCRYPTION_KEY: ${N8N_ENCRYPTION_KEY}
  GENERIC_TIMEZONE: Europe/Istanbul
  TZ: Europe/Istanbul
  # Database (use PostgreSQL for production)
  DB_TYPE: postgresdb
  DB_POSTGRESDB_HOST: ${POSTGRES_HOST}
  DB_POSTGRESDB_PORT: "5432"
  DB_POSTGRESDB_DATABASE: n8n
  DB_POSTGRESDB_USER: n8n
  DB_POSTGRESDB_PASSWORD: ${N8N_DB_PASSWORD}

resources:
  memory: 512M
  cpu: "0.5"

storage:
  - name: data
    path: /home/node/.n8n
    backup: true

dns:
  provider: cloudflare
  zone_id: ${CF_ZONE_YOURDOMAIN}
  proxy: true
  records:
    - type: A
      name: auto
      content: ${VPS_IP}
      proxied: true

health:
  path: /healthz
  interval: 30s
```

**Create compose file:**

```yaml
# apps/n8n/compose.yaml

services:
  n8n:
    image: n8nio/n8n:latest
    ports:
      - "5678:5678"
    environment:
      - N8N_HOST=${N8N_HOST}
      - N8N_PORT=5678
      - N8N_PROTOCOL=https
      - WEBHOOK_URL=${WEBHOOK_URL}
      - N8N_BASIC_AUTH_ACTIVE=true
      - N8N_BASIC_AUTH_USER=${N8N_USER}
      - N8N_BASIC_AUTH_PASSWORD=${N8N_PASSWORD}
      - N8N_ENCRYPTION_KEY=${N8N_ENCRYPTION_KEY}
      - GENERIC_TIMEZONE=Europe/Istanbul
      - TZ=Europe/Istanbul
      - DB_TYPE=postgresdb
      - DB_POSTGRESDB_HOST=${POSTGRES_HOST}
      - DB_POSTGRESDB_PORT=5432
      - DB_POSTGRESDB_DATABASE=n8n
      - DB_POSTGRESDB_USER=n8n
      - DB_POSTGRESDB_PASSWORD=${N8N_DB_PASSWORD}
    volumes:
      - n8n-data:/home/node/.n8n
    deploy:
      resources:
        limits:
          memory: 512M
          cpus: '0.5'
    restart: unless-stopped
    networks:
      - internal
      - proxy

volumes:
  n8n-data:

networks:
  internal:
    external: true
  proxy:
    external: true
```

**Set up database and secrets:**

```bash
# Generate secrets
N8N_PASSWORD=$(openssl rand -base64 24)
N8N_ENCRYPTION_KEY=$(openssl rand -hex 32)
N8N_DB_PASSWORD=$(openssl rand -base64 24)

# Save to secrets
cat >> secrets/platform.env << EOF
N8N_USER=admin
N8N_PASSWORD=$N8N_PASSWORD
N8N_ENCRYPTION_KEY=$N8N_ENCRYPTION_KEY
N8N_DB_PASSWORD=$N8N_DB_PASSWORD
N8N_HOST=auto.yourdomain.com
WEBHOOK_URL=https://auto.yourdomain.com/
EOF

echo "n8n credentials:"
echo "  URL: https://auto.yourdomain.com"
echo "  User: admin"
echo "  Password: $N8N_PASSWORD"

# Create n8n database
ssh deploy@$VPS_IP << ENDSSH
docker exec postgres-main psql -U postgres -c "CREATE USER n8n WITH PASSWORD '$N8N_DB_PASSWORD';"
docker exec postgres-main psql -U postgres -c "CREATE DATABASE n8n OWNER n8n;"
ENDSSH
```

**Deploy:**

```bash
fabrik apply n8n
```

**Time:** 1 hour

---

### Step 2: Configure Slack Integration

**Why:** Primary notification channel for alerts and updates.

**Create Slack App:**

1. Go to https://api.slack.com/apps
2. Click "Create New App" → "From scratch"
3. Name: "Fabrik Automation"
4. Select your workspace
5. Go to "Incoming Webhooks" → Enable
6. Click "Add New Webhook to Workspace"
7. Select channel (e.g., #alerts)
8. Copy webhook URL

**Save webhook URL:**

```bash
echo "SLACK_WEBHOOK_URL=https://hooks.slack.com/services/XXX/YYY/ZZZ" >> secrets/platform.env
```

**Create n8n Slack credential:**

1. Open n8n at https://auto.yourdomain.com
2. Go to Credentials → Add Credential
3. Search "Slack"
4. Choose "Slack API" or "Slack Webhook"
5. For Webhook: Paste webhook URL
6. For API: Create Slack Bot Token with `chat:write` scope
7. Save as "Slack - Alerts"

**Time:** 30 minutes

---

### Step 3: Configure Email Integration

**Why:** Email notifications for important alerts and reports.

**Options:**

| Provider | Cost | Setup |
|----------|------|-------|
| SMTP (your server) | Free | Complex |
| SendGrid | 100/day free | Easy |
| Mailgun | 5000/mo free | Easy |
| Amazon SES | $0.10/1000 | Medium |

**Using SendGrid (recommended):**

1. Create SendGrid account: https://sendgrid.com
2. Go to Settings → API Keys → Create API Key
3. Select "Restricted Access" → Mail Send: Full Access
4. Copy API key

**Create n8n Email credential:**

1. In n8n: Credentials → Add Credential
2. Search "SendGrid"
3. Paste API key
4. Save as "SendGrid - Notifications"

**Alternative - SMTP:**

```yaml
# In n8n credential settings
SMTP Host: smtp.yourprovider.com
SMTP Port: 587
SMTP User: your_email@domain.com
SMTP Password: your_password
From Email: notifications@yourdomain.com
```

**Time:** 30 minutes

---

### Step 4: Lead Capture Workflow

**Why:** Capture leads from WordPress contact forms and route to CRM + notifications.

**Workflow overview:**

```
WordPress Form Submit
        │
        ▼
   n8n Webhook
        │
        ├──► Validate Data
        │
        ├──► Add to Google Sheet
        │
        ├──► Send Slack Notification
        │
        ├──► Send Email to Sales
        │
        └──► Send Auto-Reply to Lead
```

**Create webhook in n8n:**

1. Create new workflow: "Lead Capture"
2. Add "Webhook" node as trigger
3. Set HTTP Method: POST
4. Copy webhook URL (e.g., `https://auto.yourdomain.com/webhook/lead-capture`)

**WordPress form configuration:**

For Contact Form 7:
```php
// In WordPress, add to functions.php or use plugin
add_action('wpcf7_mail_sent', 'send_to_n8n');

function send_to_n8n($contact_form) {
    $submission = WPCF7_Submission::get_instance();
    $data = $submission->get_posted_data();

    wp_remote_post('https://auto.yourdomain.com/webhook/lead-capture', [
        'body' => json_encode([
            'name' => $data['your-name'],
            'email' => $data['your-email'],
            'phone' => $data['your-phone'] ?? '',
            'message' => $data['your-message'],
            'source' => home_url(),
            'form' => $contact_form->title(),
            'timestamp' => current_time('c')
        ]),
        'headers' => ['Content-Type' => 'application/json']
    ]);
}
```

For WPForms/Gravity Forms: Use their webhook addon or Zapier integration pointing to n8n webhook.

**Complete n8n workflow:**

```json
{
  "name": "Lead Capture",
  "nodes": [
    {
      "name": "Webhook",
      "type": "n8n-nodes-base.webhook",
      "position": [250, 300],
      "webhookId": "lead-capture",
      "parameters": {
        "httpMethod": "POST",
        "path": "lead-capture",
        "responseMode": "onReceived",
        "responseData": "allEntries"
      }
    },
    {
      "name": "Validate",
      "type": "n8n-nodes-base.if",
      "position": [450, 300],
      "parameters": {
        "conditions": {
          "string": [
            {
              "value1": "={{$json.email}}",
              "operation": "isNotEmpty"
            }
          ]
        }
      }
    },
    {
      "name": "Google Sheets",
      "type": "n8n-nodes-base.googleSheets",
      "position": [650, 200],
      "parameters": {
        "operation": "append",
        "sheetId": "YOUR_SHEET_ID",
        "range": "Leads!A:G",
        "options": {
          "valueInputMode": "USER_ENTERED"
        }
      }
    },
    {
      "name": "Slack",
      "type": "n8n-nodes-base.slack",
      "position": [650, 300],
      "parameters": {
        "channel": "#leads",
        "text": "🎯 *New Lead*\n\n*Name:* {{$json.name}}\n*Email:* {{$json.email}}\n*Phone:* {{$json.phone}}\n*Source:* {{$json.source}}\n\n*Message:*\n{{$json.message}}"
      }
    },
    {
      "name": "Email to Sales",
      "type": "n8n-nodes-base.sendGrid",
      "position": [650, 400],
      "parameters": {
        "to": "sales@yourdomain.com",
        "subject": "New Lead: {{$json.name}}",
        "text": "New lead from {{$json.source}}\n\nName: {{$json.name}}\nEmail: {{$json.email}}\nPhone: {{$json.phone}}\n\nMessage:\n{{$json.message}}"
      }
    },
    {
      "name": "Auto-Reply",
      "type": "n8n-nodes-base.sendGrid",
      "position": [850, 300],
      "parameters": {
        "to": "={{$json.email}}",
        "subject": "Thank you for contacting us",
        "html": "<p>Hi {{$json.name}},</p><p>Thank you for reaching out. We've received your message and will get back to you within 24 hours.</p><p>Best regards,<br>Your Team</p>"
      }
    }
  ],
  "connections": {
    "Webhook": {
      "main": [[{"node": "Validate", "type": "main", "index": 0}]]
    },
    "Validate": {
      "main": [
        [
          {"node": "Google Sheets", "type": "main", "index": 0},
          {"node": "Slack", "type": "main", "index": 0},
          {"node": "Email to Sales", "type": "main", "index": 0}
        ]
      ]
    },
    "Email to Sales": {
      "main": [[{"node": "Auto-Reply", "type": "main", "index": 0}]]
    }
  }
}
```

**Time:** 2 hours

---

### Step 5: Uptime Alert Workflow

**Why:** Get notified when sites go down or recover.

**Configure Uptime Kuma webhook:**

1. In Uptime Kuma: Settings → Notifications
2. Add "Webhook" notification
3. URL: `https://auto.yourdomain.com/webhook/uptime-alert`
4. Content Type: application/json

**Create n8n workflow:**

```json
{
  "name": "Uptime Alerts",
  "nodes": [
    {
      "name": "Webhook",
      "type": "n8n-nodes-base.webhook",
      "position": [250, 300],
      "parameters": {
        "httpMethod": "POST",
        "path": "uptime-alert",
        "responseMode": "onReceived"
      }
    },
    {
      "name": "Format Message",
      "type": "n8n-nodes-base.set",
      "position": [450, 300],
      "parameters": {
        "values": {
          "string": [
            {
              "name": "emoji",
              "value": "={{$json.heartbeat.status === 1 ? '✅' : '🔴'}}"
            },
            {
              "name": "status_text",
              "value": "={{$json.heartbeat.status === 1 ? 'UP' : 'DOWN'}}"
            },
            {
              "name": "message",
              "value": "={{$json.emoji}} *{{$json.monitor.name}}* is *{{$json.status_text}}*\n\nURL: {{$json.monitor.url}}\nTime: {{$json.heartbeat.time}}\n{{$json.heartbeat.msg ? 'Details: ' + $json.heartbeat.msg : ''}}"
            }
          ]
        }
      }
    },
    {
      "name": "Slack Alert",
      "type": "n8n-nodes-base.slack",
      "position": [650, 250],
      "parameters": {
        "channel": "#alerts",
        "text": "={{$json.message}}"
      }
    },
    {
      "name": "Check if Down",
      "type": "n8n-nodes-base.if",
      "position": [650, 400],
      "parameters": {
        "conditions": {
          "number": [
            {
              "value1": "={{$json.heartbeat.status}}",
              "operation": "equal",
              "value2": 0
            }
          ]
        }
      }
    },
    {
      "name": "Email Alert (Down Only)",
      "type": "n8n-nodes-base.sendGrid",
      "position": [850, 400],
      "parameters": {
        "to": "admin@yourdomain.com",
        "subject": "🔴 ALERT: {{$json.monitor.name}} is DOWN",
        "text": "Site {{$json.monitor.name}} is DOWN\n\nURL: {{$json.monitor.url}}\nTime: {{$json.heartbeat.time}}\n\nPlease investigate immediately."
      }
    }
  ],
  "connections": {
    "Webhook": {
      "main": [[{"node": "Format Message", "type": "main", "index": 0}]]
    },
    "Format Message": {
      "main": [
        [
          {"node": "Slack Alert", "type": "main", "index": 0},
          {"node": "Check if Down", "type": "main", "index": 0}
        ]
      ]
    },
    "Check if Down": {
      "main": [[{"node": "Email Alert (Down Only)", "type": "main", "index": 0}]]
    }
  }
}
```

**Time:** 1 hour

---

### Step 6: Daily/Weekly Report Workflow

**Why:** Automated summary reports of system health and metrics.

**Workflow overview:**

```
Cron Trigger (9:00 AM daily)
        │
        ▼
   Query Prometheus
   (CPU, Memory, Disk, Containers)
        │
        ▼
   Query Loki
   (Error counts by service)
        │
        ▼
   Query Uptime Kuma
   (Uptime percentages)
        │
        ▼
   Format Report
        │
        ├──► Send to Slack #daily-report
        │
        └──► Send Email Summary
```

**Create n8n workflow:**

```json
{
  "name": "Daily System Report",
  "nodes": [
    {
      "name": "Cron",
      "type": "n8n-nodes-base.cron",
      "position": [250, 300],
      "parameters": {
        "triggerTimes": {
          "item": [
            {
              "mode": "everyDay",
              "hour": 9,
              "minute": 0
            }
          ]
        }
      }
    },
    {
      "name": "Get CPU Metrics",
      "type": "n8n-nodes-base.httpRequest",
      "position": [450, 200],
      "parameters": {
        "url": "http://prometheus:9090/api/v1/query",
        "qs": {
          "query": "100 - (avg(irate(node_cpu_seconds_total{mode=\"idle\"}[1h])) * 100)"
        }
      }
    },
    {
      "name": "Get Memory Metrics",
      "type": "n8n-nodes-base.httpRequest",
      "position": [450, 300],
      "parameters": {
        "url": "http://prometheus:9090/api/v1/query",
        "qs": {
          "query": "(1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100"
        }
      }
    },
    {
      "name": "Get Disk Metrics",
      "type": "n8n-nodes-base.httpRequest",
      "position": [450, 400],
      "parameters": {
        "url": "http://prometheus:9090/api/v1/query",
        "qs": {
          "query": "(1 - (node_filesystem_avail_bytes{mountpoint=\"/\"} / node_filesystem_size_bytes{mountpoint=\"/\"})) * 100"
        }
      }
    },
    {
      "name": "Get Error Count",
      "type": "n8n-nodes-base.httpRequest",
      "position": [450, 500],
      "parameters": {
        "url": "http://loki:3100/loki/api/v1/query",
        "qs": {
          "query": "count_over_time({job=\"containerlogs\"} |~ \"error\" [24h])"
        }
      }
    },
    {
      "name": "Merge Data",
      "type": "n8n-nodes-base.merge",
      "position": [650, 300],
      "parameters": {
        "mode": "mergeByIndex"
      }
    },
    {
      "name": "Format Report",
      "type": "n8n-nodes-base.code",
      "position": [850, 300],
      "parameters": {
        "jsCode": "const cpu = items[0].json.data?.result?.[0]?.value?.[1] || 'N/A';\nconst mem = items[1].json.data?.result?.[0]?.value?.[1] || 'N/A';\nconst disk = items[2].json.data?.result?.[0]?.value?.[1] || 'N/A';\nconst errors = items[3].json.data?.result?.[0]?.value?.[1] || '0';\n\nconst date = new Date().toLocaleDateString('en-US', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' });\n\nconst report = `📊 *Daily System Report*\n_${date}_\n\n*System Resources:*\n• CPU Usage: ${parseFloat(cpu).toFixed(1)}%\n• Memory Usage: ${parseFloat(mem).toFixed(1)}%\n• Disk Usage: ${parseFloat(disk).toFixed(1)}%\n\n*Application Health:*\n• Errors (24h): ${errors}\n\n_Report generated by Fabrik Automation_`;\n\nreturn [{ json: { report, cpu, mem, disk, errors, date } }];"
      }
    },
    {
      "name": "Send to Slack",
      "type": "n8n-nodes-base.slack",
      "position": [1050, 250],
      "parameters": {
        "channel": "#daily-report",
        "text": "={{$json.report}}"
      }
    },
    {
      "name": "Send Email",
      "type": "n8n-nodes-base.sendGrid",
      "position": [1050, 400],
      "parameters": {
        "to": "admin@yourdomain.com",
        "subject": "Daily System Report - {{$json.date}}",
        "text": "={{$json.report.replace(/\\*/g, '').replace(/\\_/g, '')}}"
      }
    }
  ],
  "connections": {
    "Cron": {
      "main": [
        [
          {"node": "Get CPU Metrics", "type": "main", "index": 0},
          {"node": "Get Memory Metrics", "type": "main", "index": 0},
          {"node": "Get Disk Metrics", "type": "main", "index": 0},
          {"node": "Get Error Count", "type": "main", "index": 0}
        ]
      ]
    },
    "Get CPU Metrics": {
      "main": [[{"node": "Merge Data", "type": "main", "index": 0}]]
    },
    "Get Memory Metrics": {
      "main": [[{"node": "Merge Data", "type": "main", "index": 1}]]
    },
    "Get Disk Metrics": {
      "main": [[{"node": "Merge Data", "type": "main", "index": 2}]]
    },
    "Get Error Count": {
      "main": [[{"node": "Merge Data", "type": "main", "index": 3}]]
    },
    "Merge Data": {
      "main": [[{"node": "Format Report", "type": "main", "index": 0}]]
    },
    "Format Report": {
      "main": [
        [
          {"node": "Send to Slack", "type": "main", "index": 0},
          {"node": "Send Email", "type": "main", "index": 0}
        ]
      ]
    }
  }
}
```

**Time:** 1.5 hours

---

### Step 7: Client Onboarding Automation

**Why:** When client requests new site, automatically start provisioning workflow.

**Workflow overview:**

```
New Site Request Form
        │
        ▼
   n8n Webhook
        │
        ├──► Validate Requirements
        │
        ├──► Create Spec File
        │
        ├──► Run Fabrik Deploy
        │
        ├──► Configure DNS
        │
        ├──► Send Client Welcome Email
        │
        └──► Notify Team on Slack
```

**Create n8n workflow:**

```json
{
  "name": "Client Site Onboarding",
  "nodes": [
    {
      "name": "Webhook",
      "type": "n8n-nodes-base.webhook",
      "position": [250, 300],
      "parameters": {
        "httpMethod": "POST",
        "path": "new-site-request",
        "responseMode": "lastNode"
      }
    },
    {
      "name": "Validate",
      "type": "n8n-nodes-base.if",
      "position": [450, 300],
      "parameters": {
        "conditions": {
          "string": [
            {
              "value1": "={{$json.client_name}}",
              "operation": "isNotEmpty"
            },
            {
              "value1": "={{$json.domain}}",
              "operation": "isNotEmpty"
            }
          ]
        }
      }
    },
    {
      "name": "Generate Site ID",
      "type": "n8n-nodes-base.set",
      "position": [650, 300],
      "parameters": {
        "values": {
          "string": [
            {
              "name": "site_id",
              "value": "={{$json.domain.replace(/\\./g, '-').toLowerCase()}}"
            },
            {
              "name": "spec_path",
              "value": "/opt/fabrik/specs/{{$json.site_id}}/spec.yaml"
            }
          ]
        }
      }
    },
    {
      "name": "Create Spec via SSH",
      "type": "n8n-nodes-base.ssh",
      "position": [850, 300],
      "parameters": {
        "command": "cd /opt/fabrik && ./fabrik new wp-site {{$json.site_id}} --domain={{$json.domain}}",
        "credentials": "SSH - VPS"
      }
    },
    {
      "name": "Deploy Site",
      "type": "n8n-nodes-base.ssh",
      "position": [1050, 300],
      "parameters": {
        "command": "cd /opt/fabrik && ./fabrik apply {{$json.site_id}} --skip-plan",
        "credentials": "SSH - VPS"
      }
    },
    {
      "name": "Wait for Deployment",
      "type": "n8n-nodes-base.wait",
      "position": [1250, 300],
      "parameters": {
        "amount": 60,
        "unit": "seconds"
      }
    },
    {
      "name": "Verify Site",
      "type": "n8n-nodes-base.httpRequest",
      "position": [1450, 300],
      "parameters": {
        "url": "https://{{$json.domain}}",
        "options": {
          "timeout": 30000
        }
      }
    },
    {
      "name": "Send Welcome Email",
      "type": "n8n-nodes-base.sendGrid",
      "position": [1650, 250],
      "parameters": {
        "to": "={{$json.client_email}}",
        "subject": "Your new website is ready!",
        "html": "<h1>Welcome, {{$json.client_name}}!</h1><p>Your new website at <a href='https://{{$json.domain}}'>{{$json.domain}}</a> is now live.</p><p>Admin Access:</p><ul><li>URL: https://{{$json.domain}}/wp-admin</li><li>Username: admin</li><li>Password: (sent separately)</li></ul><p>We'll be in touch to help you customize your site.</p>"
      }
    },
    {
      "name": "Notify Team",
      "type": "n8n-nodes-base.slack",
      "position": [1650, 400],
      "parameters": {
        "channel": "#new-sites",
        "text": "🎉 *New site deployed!*\n\n*Client:* {{$json.client_name}}\n*Domain:* {{$json.domain}}\n*Site ID:* {{$json.site_id}}\n\nSite is live at https://{{$json.domain}}"
      }
    },
    {
      "name": "Return Success",
      "type": "n8n-nodes-base.respondToWebhook",
      "position": [1850, 300],
      "parameters": {
        "respondWith": "json",
        "responseBody": {
          "success": true,
          "site_id": "={{$json.site_id}}",
          "url": "https://{{$json.domain}}",
          "message": "Site deployed successfully"
        }
      }
    }
  ],
  "connections": {
    "Webhook": {
      "main": [[{"node": "Validate", "type": "main", "index": 0}]]
    },
    "Validate": {
      "main": [[{"node": "Generate Site ID", "type": "main", "index": 0}]]
    },
    "Generate Site ID": {
      "main": [[{"node": "Create Spec via SSH", "type": "main", "index": 0}]]
    },
    "Create Spec via SSH": {
      "main": [[{"node": "Deploy Site", "type": "main", "index": 0}]]
    },
    "Deploy Site": {
      "main": [[{"node": "Wait for Deployment", "type": "main", "index": 0}]]
    },
    "Wait for Deployment": {
      "main": [[{"node": "Verify Site", "type": "main", "index": 0}]]
    },
    "Verify Site": {
      "main": [
        [
          {"node": "Send Welcome Email", "type": "main", "index": 0},
          {"node": "Notify Team", "type": "main", "index": 0}
        ]
      ]
    },
    "Notify Team": {
      "main": [[{"node": "Return Success", "type": "main", "index": 0}]]
    }
  }
}
```

**Create SSH credential in n8n:**

1. In n8n: Credentials → Add Credential
2. Search "SSH"
3. Configure:
   - Host: your VPS IP
   - Port: 22
   - Username: deploy
   - Private Key: (paste your SSH private key)
4. Save as "SSH - VPS"

**Time:** 2 hours

---

### Step 8: Backup Notification Workflow

**Why:** Know immediately when backups succeed or fail.

**Configure backup hook:**

```bash
# In your backup script, add webhook call
# scripts/backup-notify.sh

#!/bin/bash
BACKUP_RESULT=$1  # success or failure
BACKUP_TYPE=$2    # database, files, full
BACKUP_SIZE=$3    # in bytes
BACKUP_FILE=$4    # filename

curl -X POST "https://auto.yourdomain.com/webhook/backup-status" \
  -H "Content-Type: application/json" \
  -d "{
    \"result\": \"$BACKUP_RESULT\",
    \"type\": \"$BACKUP_TYPE\",
    \"size\": \"$BACKUP_SIZE\",
    \"file\": \"$BACKUP_FILE\",
    \"timestamp\": \"$(date -Iseconds)\",
    \"server\": \"$(hostname)\"
  }"
```

**Create n8n workflow:**

```json
{
  "name": "Backup Notifications",
  "nodes": [
    {
      "name": "Webhook",
      "type": "n8n-nodes-base.webhook",
      "position": [250, 300],
      "parameters": {
        "httpMethod": "POST",
        "path": "backup-status"
      }
    },
    {
      "name": "Check Result",
      "type": "n8n-nodes-base.switch",
      "position": [450, 300],
      "parameters": {
        "dataPropertyName": "result",
        "rules": {
          "rules": [
            {"value": "success"},
            {"value": "failure"}
          ]
        }
      }
    },
    {
      "name": "Format Success",
      "type": "n8n-nodes-base.set",
      "position": [650, 200],
      "parameters": {
        "values": {
          "string": [
            {
              "name": "message",
              "value": "✅ *Backup Successful*\n\nType: {{$json.type}}\nSize: {{Math.round($json.size / 1024 / 1024)}} MB\nFile: {{$json.file}}\nServer: {{$json.server}}\nTime: {{$json.timestamp}}"
            },
            {
              "name": "channel",
              "value": "#backups"
            }
          ]
        }
      }
    },
    {
      "name": "Format Failure",
      "type": "n8n-nodes-base.set",
      "position": [650, 400],
      "parameters": {
        "values": {
          "string": [
            {
              "name": "message",
              "value": "🔴 *Backup FAILED*\n\nType: {{$json.type}}\nServer: {{$json.server}}\nTime: {{$json.timestamp}}\n\n⚠️ Investigate immediately!"
            },
            {
              "name": "channel",
              "value": "#alerts"
            }
          ]
        }
      }
    },
    {
      "name": "Slack Success",
      "type": "n8n-nodes-base.slack",
      "position": [850, 200],
      "parameters": {
        "channel": "={{$json.channel}}",
        "text": "={{$json.message}}"
      }
    },
    {
      "name": "Slack Failure",
      "type": "n8n-nodes-base.slack",
      "position": [850, 350],
      "parameters": {
        "channel": "={{$json.channel}}",
        "text": "={{$json.message}}"
      }
    },
    {
      "name": "Email Failure",
      "type": "n8n-nodes-base.sendGrid",
      "position": [850, 450],
      "parameters": {
        "to": "admin@yourdomain.com",
        "subject": "🔴 BACKUP FAILED - {{$json.server}}",
        "text": "={{$json.message.replace(/\\*/g, '')}}"
      }
    }
  ],
  "connections": {
    "Webhook": {
      "main": [[{"node": "Check Result", "type": "main", "index": 0}]]
    },
    "Check Result": {
      "main": [
        [{"node": "Format Success", "type": "main", "index": 0}],
        [{"node": "Format Failure", "type": "main", "index": 0}]
      ]
    },
    "Format Success": {
      "main": [[{"node": "Slack Success", "type": "main", "index": 0}]]
    },
    "Format Failure": {
      "main": [
        [
          {"node": "Slack Failure", "type": "main", "index": 0},
          {"node": "Email Failure", "type": "main", "index": 0}
        ]
      ]
    }
  }
}
```

**Time:** 1 hour

---

### Step 9: AI Content Review Workflow

**Why:** Human review step before AI-generated content goes live.

**Workflow overview:**

```
AI Content Generated
        │
        ▼
   Save as Draft in WordPress
        │
        ▼
   Send Review Request to Slack
   (with Approve/Reject buttons)
        │
        ├──► Approve → Publish Content
        │
        └──► Reject → Delete Draft + Notify
```

**Create n8n workflow:**

```json
{
  "name": "AI Content Review",
  "nodes": [
    {
      "name": "Webhook - New Content",
      "type": "n8n-nodes-base.webhook",
      "position": [250, 300],
      "parameters": {
        "httpMethod": "POST",
        "path": "content-review"
      }
    },
    {
      "name": "Create Draft in WP",
      "type": "n8n-nodes-base.httpRequest",
      "position": [450, 300],
      "parameters": {
        "method": "POST",
        "url": "https://{{$json.site_domain}}/wp-json/wp/v2/{{$json.content_type}}",
        "authentication": "genericCredentialType",
        "genericAuthType": "httpBasicAuth",
        "body": {
          "title": "={{$json.title}}",
          "content": "={{$json.content}}",
          "status": "draft",
          "meta": {
            "ai_generated": true,
            "review_requested": "={{new Date().toISOString()}}"
          }
        }
      }
    },
    {
      "name": "Send Slack Review Request",
      "type": "n8n-nodes-base.slack",
      "position": [650, 300],
      "parameters": {
        "channel": "#content-review",
        "blocksUi": {
          "blocks": [
            {
              "type": "section",
              "text": {
                "type": "mrkdwn",
                "text": "📝 *New AI Content for Review*\n\n*Site:* {{$json.site_domain}}\n*Type:* {{$json.content_type}}\n*Title:* {{$json.title}}"
              }
            },
            {
              "type": "section",
              "text": {
                "type": "mrkdwn",
                "text": "*Preview:*\n{{$json.content.substring(0, 500)}}..."
              }
            },
            {
              "type": "actions",
              "elements": [
                {
                  "type": "button",
                  "text": {"type": "plain_text", "text": "✅ Approve & Publish"},
                  "style": "primary",
                  "action_id": "approve_content",
                  "value": "{{$json.post_id}}"
                },
                {
                  "type": "button",
                  "text": {"type": "plain_text", "text": "❌ Reject"},
                  "style": "danger",
                  "action_id": "reject_content",
                  "value": "{{$json.post_id}}"
                },
                {
                  "type": "button",
                  "text": {"type": "plain_text", "text": "👁️ View Draft"},
                  "url": "https://{{$json.site_domain}}/wp-admin/post.php?post={{$json.post_id}}&action=edit"
                }
              ]
            }
          ]
        }
      }
    }
  ]
}
```

**Separate workflow for Slack button responses:**

```json
{
  "name": "Content Review Actions",
  "nodes": [
    {
      "name": "Slack Trigger",
      "type": "n8n-nodes-base.slackTrigger",
      "position": [250, 300],
      "parameters": {
        "triggerOn": "anyInteraction"
      }
    },
    {
      "name": "Check Action",
      "type": "n8n-nodes-base.switch",
      "position": [450, 300],
      "parameters": {
        "dataPropertyName": "actions[0].action_id",
        "rules": {
          "rules": [
            {"value": "approve_content"},
            {"value": "reject_content"}
          ]
        }
      }
    },
    {
      "name": "Publish Content",
      "type": "n8n-nodes-base.httpRequest",
      "position": [650, 200],
      "parameters": {
        "method": "POST",
        "url": "https://{{$json.site_domain}}/wp-json/wp/v2/posts/{{$json.post_id}}",
        "body": {
          "status": "publish"
        }
      }
    },
    {
      "name": "Delete Draft",
      "type": "n8n-nodes-base.httpRequest",
      "position": [650, 400],
      "parameters": {
        "method": "DELETE",
        "url": "https://{{$json.site_domain}}/wp-json/wp/v2/posts/{{$json.post_id}}"
      }
    },
    {
      "name": "Update Slack - Approved",
      "type": "n8n-nodes-base.slack",
      "position": [850, 200],
      "parameters": {
        "operation": "update",
        "channel": "={{$json.channel.id}}",
        "ts": "={{$json.message.ts}}",
        "text": "✅ Content approved and published by {{$json.user.name}}"
      }
    },
    {
      "name": "Update Slack - Rejected",
      "type": "n8n-nodes-base.slack",
      "position": [850, 400],
      "parameters": {
        "operation": "update",
        "channel": "={{$json.channel.id}}",
        "ts": "={{$json.message.ts}}",
        "text": "❌ Content rejected by {{$json.user.name}}"
      }
    }
  ]
}
```

**Time:** 2 hours

---

### Step 10: Workflow Templates Library

**Why:** Reusable patterns for common automation needs.

**Create workflow templates:**

```python
# compiler/n8n/templates.py

import json
from pathlib import Path
from typing import Optional

class N8NWorkflowTemplates:
    """Library of reusable n8n workflow templates."""

    def __init__(self, templates_dir: str = "templates/n8n"):
        self.templates_dir = Path(templates_dir)
        self.templates_dir.mkdir(parents=True, exist_ok=True)

    def save_template(self, name: str, workflow: dict, description: str = ""):
        """Save workflow as template."""
        template = {
            "name": name,
            "description": description,
            "workflow": workflow,
            "variables": self._extract_variables(workflow)
        }

        path = self.templates_dir / f"{name}.json"
        with open(path, 'w') as f:
            json.dump(template, f, indent=2)

    def load_template(self, name: str) -> dict:
        """Load workflow template."""
        path = self.templates_dir / f"{name}.json"
        with open(path) as f:
            return json.load(f)

    def instantiate(self, name: str, variables: dict) -> dict:
        """
        Create workflow from template with variables replaced.

        Variables in templates use {{variable_name}} syntax.
        """
        template = self.load_template(name)
        workflow = template['workflow']

        # Replace variables in workflow JSON
        workflow_str = json.dumps(workflow)

        for var_name, var_value in variables.items():
            workflow_str = workflow_str.replace(f"{{{{var_{var_name}}}}}", str(var_value))

        return json.loads(workflow_str)

    def _extract_variables(self, workflow: dict) -> list:
        """Extract variable names from workflow."""
        workflow_str = json.dumps(workflow)

        import re
        matches = re.findall(r'\{\{var_(\w+)\}\}', workflow_str)

        return list(set(matches))

    def list_templates(self) -> list[dict]:
        """List all available templates."""
        templates = []

        for path in self.templates_dir.glob("*.json"):
            with open(path) as f:
                data = json.load(f)
                templates.append({
                    "name": data['name'],
                    "description": data.get('description', ''),
                    "variables": data.get('variables', [])
                })

        return templates


# Pre-built templates

def get_form_to_slack_template() -> dict:
    """Template: Form submission to Slack notification."""
    return {
        "name": "Form to Slack",
        "nodes": [
            {
                "name": "Webhook",
                "type": "n8n-nodes-base.webhook",
                "parameters": {
                    "path": "{{var_webhook_path}}",
                    "httpMethod": "POST"
                }
            },
            {
                "name": "Slack",
                "type": "n8n-nodes-base.slack",
                "parameters": {
                    "channel": "{{var_slack_channel}}",
                    "text": "{{var_message_template}}"
                }
            }
        ],
        "connections": {
            "Webhook": {
                "main": [[{"node": "Slack", "type": "main", "index": 0}]]
            }
        }
    }

def get_scheduled_report_template() -> dict:
    """Template: Scheduled HTTP request with notification."""
    return {
        "name": "Scheduled Report",
        "nodes": [
            {
                "name": "Cron",
                "type": "n8n-nodes-base.cron",
                "parameters": {
                    "triggerTimes": {
                        "item": [{
                            "mode": "everyDay",
                            "hour": "{{var_hour}}",
                            "minute": "{{var_minute}}"
                        }]
                    }
                }
            },
            {
                "name": "HTTP Request",
                "type": "n8n-nodes-base.httpRequest",
                "parameters": {
                    "url": "{{var_api_url}}"
                }
            },
            {
                "name": "Format",
                "type": "n8n-nodes-base.code",
                "parameters": {
                    "jsCode": "{{var_format_code}}"
                }
            },
            {
                "name": "Send",
                "type": "n8n-nodes-base.slack",
                "parameters": {
                    "channel": "{{var_channel}}",
                    "text": "={{$json.formatted}}"
                }
            }
        ]
    }

def get_error_alert_template() -> dict:
    """Template: Error detection and multi-channel alert."""
    return {
        "name": "Error Alert",
        "nodes": [
            {
                "name": "Webhook",
                "type": "n8n-nodes-base.webhook",
                "parameters": {
                    "path": "{{var_webhook_path}}",
                    "httpMethod": "POST"
                }
            },
            {
                "name": "Check Severity",
                "type": "n8n-nodes-base.if",
                "parameters": {
                    "conditions": {
                        "string": [{
                            "value1": "={{$json.severity}}",
                            "operation": "equal",
                            "value2": "critical"
                        }]
                    }
                }
            },
            {
                "name": "Slack Alert",
                "type": "n8n-nodes-base.slack",
                "parameters": {
                    "channel": "{{var_alert_channel}}",
                    "text": "🔴 *{{$json.title}}*\n{{$json.message}}"
                }
            },
            {
                "name": "Email Alert",
                "type": "n8n-nodes-base.sendGrid",
                "parameters": {
                    "to": "{{var_alert_email}}",
                    "subject": "CRITICAL: {{$json.title}}",
                    "text": "={{$json.message}}"
                }
            }
        ]
    }
```

**Time:** 1 hour

---

### Step 11: CLI Commands for n8n Management

**Why:** Manage n8n workflows from Fabrik CLI.

**Code:**

```python
# cli/automation.py

import click
import os
from pathlib import Path
import httpx
import json

def load_env():
    """Load environment."""
    env_file = Path("secrets/platform.env")
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                if '=' in line and not line.startswith('#'):
                    k, v = line.strip().split('=', 1)
                    os.environ[k] = v

class N8NClient:
    """Client for n8n API."""

    def __init__(self):
        self.base_url = os.environ.get('N8N_URL', 'https://auto.yourdomain.com')
        self.api_key = os.environ.get('N8N_API_KEY', '')

        self.client = httpx.Client(
            base_url=f"{self.base_url}/api/v1",
            headers={
                'X-N8N-API-KEY': self.api_key,
                'Content-Type': 'application/json'
            },
            timeout=30
        )

    def list_workflows(self) -> list:
        """List all workflows."""
        resp = self.client.get('/workflows')
        return resp.json().get('data', [])

    def get_workflow(self, workflow_id: str) -> dict:
        """Get workflow by ID."""
        resp = self.client.get(f'/workflows/{workflow_id}')
        return resp.json()

    def create_workflow(self, workflow: dict) -> dict:
        """Create new workflow."""
        resp = self.client.post('/workflows', json=workflow)
        return resp.json()

    def update_workflow(self, workflow_id: str, workflow: dict) -> dict:
        """Update existing workflow."""
        resp = self.client.put(f'/workflows/{workflow_id}', json=workflow)
        return resp.json()

    def activate_workflow(self, workflow_id: str) -> bool:
        """Activate workflow."""
        resp = self.client.post(f'/workflows/{workflow_id}/activate')
        return resp.status_code == 200

    def deactivate_workflow(self, workflow_id: str) -> bool:
        """Deactivate workflow."""
        resp = self.client.post(f'/workflows/{workflow_id}/deactivate')
        return resp.status_code == 200

    def execute_workflow(self, workflow_id: str, data: dict = None) -> dict:
        """Execute workflow manually."""
        body = {'workflowData': data} if data else {}
        resp = self.client.post(f'/workflows/{workflow_id}/run', json=body)
        return resp.json()

    def list_executions(self, workflow_id: str = None, limit: int = 20) -> list:
        """List workflow executions."""
        params = {'limit': limit}
        if workflow_id:
            params['workflowId'] = workflow_id

        resp = self.client.get('/executions', params=params)
        return resp.json().get('data', [])

@click.group()
def automation():
    """Automation and workflow commands."""
    load_env()

# ─────────────────────────────────────────────────────────────
# Workflows
# ─────────────────────────────────────────────────────────────

@automation.command('list')
@click.option('--active-only', is_flag=True, help='Show only active workflows')
def list_workflows(active_only):
    """List all n8n workflows."""

    n8n = N8NClient()
    workflows = n8n.list_workflows()

    if active_only:
        workflows = [w for w in workflows if w.get('active')]

    if not workflows:
        click.echo("No workflows found.")
        return

    click.echo("\n" + "=" * 70)
    click.echo(f"  {'ID':<10} {'NAME':<35} {'ACTIVE':<10} {'UPDATED':<15}")
    click.echo("=" * 70)

    for w in workflows:
        active = click.style('✓', fg='green') if w.get('active') else click.style('✗', fg='red')
        updated = w.get('updatedAt', '')[:10]

        click.echo(f"  {w['id']:<10} {w['name'][:35]:<35} {active:<10} {updated:<15}")

    click.echo("=" * 70 + "\n")

@automation.command('status')
@click.argument('workflow_id')
def workflow_status(workflow_id):
    """Show workflow status and recent executions."""

    n8n = N8NClient()

    workflow = n8n.get_workflow(workflow_id)

    click.echo(f"\n{'=' * 60}")
    click.echo(f"  Workflow: {workflow['name']}")
    click.echo(f"{'=' * 60}")
    click.echo(f"  ID:      {workflow['id']}")
    click.echo(f"  Active:  {workflow.get('active', False)}")
    click.echo(f"  Created: {workflow.get('createdAt', 'N/A')}")
    click.echo(f"  Updated: {workflow.get('updatedAt', 'N/A')}")
    click.echo(f"  Nodes:   {len(workflow.get('nodes', []))}")

    # Get recent executions
    executions = n8n.list_executions(workflow_id=workflow_id, limit=5)

    if executions:
        click.echo(f"\n  Recent Executions:")
        for ex in executions:
            status = '✓' if ex.get('finished') and not ex.get('stoppedAt') else '✗'
            started = ex.get('startedAt', '')[:19]
            click.echo(f"    {status} {ex['id']} - {started}")

    click.echo("")

@automation.command('activate')
@click.argument('workflow_id')
def activate(workflow_id):
    """Activate a workflow."""

    n8n = N8NClient()

    if n8n.activate_workflow(workflow_id):
        click.echo(f"✓ Workflow {workflow_id} activated")
    else:
        click.echo(f"✗ Failed to activate workflow {workflow_id}")

@automation.command('deactivate')
@click.argument('workflow_id')
def deactivate(workflow_id):
    """Deactivate a workflow."""

    n8n = N8NClient()

    if n8n.deactivate_workflow(workflow_id):
        click.echo(f"✓ Workflow {workflow_id} deactivated")
    else:
        click.echo(f"✗ Failed to deactivate workflow {workflow_id}")

@automation.command('run')
@click.argument('workflow_id')
@click.option('--data', type=str, help='JSON data to pass to workflow')
def run(workflow_id, data):
    """Manually execute a workflow."""

    n8n = N8NClient()

    payload = json.loads(data) if data else None

    click.echo(f"Executing workflow {workflow_id}...")

    result = n8n.execute_workflow(workflow_id, payload)

    if result.get('data', {}).get('executionId'):
        click.echo(f"✓ Execution started: {result['data']['executionId']}")
    else:
        click.echo(f"✗ Execution failed: {result}")

# ─────────────────────────────────────────────────────────────
# Templates
# ─────────────────────────────────────────────────────────────

@automation.command('templates')
def list_templates():
    """List available workflow templates."""

    from compiler.n8n.templates import N8NWorkflowTemplates

    templates = N8NWorkflowTemplates()
    template_list = templates.list_templates()

    if not template_list:
        click.echo("No templates found.")
        return

    click.echo("\nAvailable Templates:")
    click.echo("-" * 50)

    for t in template_list:
        click.echo(f"\n  {t['name']}")
        click.echo(f"    {t['description']}")
        if t['variables']:
            click.echo(f"    Variables: {', '.join(t['variables'])}")

@automation.command('create-from-template')
@click.argument('template_name')
@click.option('--var', multiple=True, help='Variable in format name=value')
def create_from_template(template_name, var):
    """Create workflow from template."""

    from compiler.n8n.templates import N8NWorkflowTemplates

    templates = N8NWorkflowTemplates()
    n8n = N8NClient()

    # Parse variables
    variables = {}
    for v in var:
        if '=' in v:
            name, value = v.split('=', 1)
            variables[name] = value

    # Instantiate template
    try:
        workflow = templates.instantiate(template_name, variables)
    except FileNotFoundError:
        click.echo(f"Template not found: {template_name}")
        raise click.Abort()

    # Create in n8n
    result = n8n.create_workflow(workflow)

    if result.get('id'):
        click.echo(f"✓ Workflow created: {result['id']}")
        click.echo(f"  Name: {result['name']}")
        click.echo(f"  URL: {os.environ.get('N8N_URL')}/workflow/{result['id']}")
    else:
        click.echo(f"✗ Failed to create workflow: {result}")

# ─────────────────────────────────────────────────────────────
# Executions
# ─────────────────────────────────────────────────────────────

@automation.command('executions')
@click.option('--workflow', 'workflow_id', help='Filter by workflow ID')
@click.option('--limit', default=20, help='Number of executions to show')
@click.option('--failed-only', is_flag=True, help='Show only failed executions')
def executions(workflow_id, limit, failed_only):
    """List recent workflow executions."""

    n8n = N8NClient()

    execs = n8n.list_executions(workflow_id=workflow_id, limit=limit)

    if failed_only:
        execs = [e for e in execs if e.get('stoppedAt')]

    if not execs:
        click.echo("No executions found.")
        return

    click.echo("\n" + "=" * 80)
    click.echo(f"  {'ID':<12} {'WORKFLOW':<30} {'STATUS':<10} {'STARTED':<20}")
    click.echo("=" * 80)

    for ex in execs:
        status = click.style('✓', fg='green') if ex.get('finished') and not ex.get('stoppedAt') else click.style('✗', fg='red')
        started = ex.get('startedAt', '')[:19]
        wf_name = ex.get('workflowData', {}).get('name', 'N/A')[:30]

        click.echo(f"  {ex['id']:<12} {wf_name:<30} {status:<10} {started:<20}")

    click.echo("=" * 80 + "\n")

# ─────────────────────────────────────────────────────────────
# Webhooks
# ─────────────────────────────────────────────────────────────

@automation.command('webhooks')
def list_webhooks():
    """List all webhook URLs."""

    n8n = N8NClient()
    workflows = n8n.list_workflows()

    webhook_url = os.environ.get('WEBHOOK_URL', 'https://auto.yourdomain.com')

    click.echo("\nWebhook Endpoints:")
    click.echo("-" * 60)

    for w in workflows:
        # Check if workflow has webhook trigger
        for node in w.get('nodes', []):
            if node.get('type') == 'n8n-nodes-base.webhook':
                path = node.get('parameters', {}).get('path', '')
                active = '✓' if w.get('active') else '✗'
                click.echo(f"  {active} {w['name']}")
                click.echo(f"    {webhook_url}/webhook/{path}")
                click.echo("")

# ─────────────────────────────────────────────────────────────
# Dashboard
# ─────────────────────────────────────────────────────────────

@automation.command('dashboard')
@click.option('--open', 'open_browser', is_flag=True, help='Open in browser')
def dashboard(open_browser):
    """Get n8n dashboard URL."""

    n8n_url = os.environ.get('N8N_URL', 'https://auto.yourdomain.com')

    click.echo(f"\nn8n Dashboard: {n8n_url}")

    if open_browser:
        import webbrowser
        webbrowser.open(n8n_url)

if __name__ == '__main__':
    automation()
```

**Update main CLI:**

```python
# cli/main.py - add automation commands

from cli.automation import automation

cli.add_command(automation)
```

**Time:** 2 hours

---

### Phase 8 Complete

After completing all steps, you have:

```
✓ n8n deployed and configured
✓ Slack integration for notifications
✓ Email integration for alerts
✓ Lead capture workflow (forms → CRM/notifications)
✓ Uptime alert workflow (down/up → Slack/email)
✓ Daily report workflow (metrics summary)
✓ Client onboarding workflow (request → deploy)
✓ Backup notification workflow (success/failure alerts)
✓ AI content review workflow (approve/reject pipeline)
✓ Workflow templates library
✓ CLI commands for automation management
```

**New CLI commands:**

```bash
# List workflows
fabrik automation list
fabrik automation list --active-only

# Workflow status
fabrik automation status <workflow_id>

# Activate/deactivate workflows
fabrik automation activate <workflow_id>
fabrik automation deactivate <workflow_id>

# Manually run workflow
fabrik automation run <workflow_id>
fabrik automation run <workflow_id> --data='{"key": "value"}'

# List templates
fabrik automation templates

# Create from template
fabrik automation create-from-template form-to-slack \
  --var webhook_path=my-form \
  --var slack_channel=#leads

# View executions
fabrik automation executions
fabrik automation executions --workflow=123 --failed-only

# List webhooks
fabrik automation webhooks

# Open dashboard
fabrik automation dashboard --open
```

**Webhook Endpoints:**

```
Lead Capture:      https://auto.yourdomain.com/webhook/lead-capture
Uptime Alerts:     https://auto.yourdomain.com/webhook/uptime-alert
Backup Status:     https://auto.yourdomain.com/webhook/backup-status
Content Review:    https://auto.yourdomain.com/webhook/content-review
New Site Request:  https://auto.yourdomain.com/webhook/new-site-request
```

---

### Complete Automation Ecosystem

```
┌─────────────────────────────────────────────────────────────────┐
│  FABRIK AUTOMATION ECOSYSTEM                                    │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  TRIGGERS                                               │    │
│  │                                                         │    │
│  │  • WordPress form submissions                           │    │
│  │  • Uptime Kuma status changes                           │    │
│  │  • Scheduled times (cron)                               │    │
│  │  • Backup completion                                    │    │
│  │  • GitHub webhooks                                      │    │
│  │  • Stripe payment events                                │    │
│  │  • Manual API calls                                     │    │
│  └─────────────────────────────────────────────────────────┘    │
│                            │                                    │
│                            ▼                                    │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  n8n WORKFLOWS                                          │    │
│  │                                                         │    │
│  │  • Lead Capture                                         │    │
│  │  • Uptime Alerts                                        │    │
│  │  • Daily Reports                                        │    │
│  │  • Client Onboarding                                    │    │
│  │  • Backup Notifications                                 │    │
│  │  • Content Review                                       │    │
│  │  • Custom integrations                                  │    │
│  └─────────────────────────────────────────────────────────┘    │
│                            │                                    │
│                            ▼                                    │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  ACTIONS                                                │    │
│  │                                                         │    │
│  │  • Slack messages (#alerts, #leads, #daily-report)      │    │
│  │  • Email notifications                                  │    │
│  │  • Google Sheets logging                                │    │
│  │  • Fabrik deployments (via SSH)                         │    │
│  │  • WordPress API calls                                  │    │
│  │  • Database operations                                  │    │
│  │  • External API integrations                            │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

---

### Phase 8 Summary

| Step | Task | Time |
|------|------|------|
| 1 | Deploy n8n | 1 hr |
| 2 | Configure Slack integration | 30 min |
| 3 | Configure email integration | 30 min |
| 4 | Lead capture workflow | 2 hrs |
| 5 | Uptime alert workflow | 1 hr |
| 6 | Daily/weekly report workflow | 1.5 hrs |
| 7 | Client onboarding automation | 2 hrs |
| 8 | Backup notification workflow | 1 hr |
| 9 | AI content review workflow | 2 hrs |
| 10 | Workflow templates library | 1 hr |
| 11 | CLI commands | 2 hrs |

**Total: ~14 hours (2-3 days)**

---

### What You've Built (Complete Fabrik Platform)

After completing all 8 phases:

```
Phase 1: Foundation           (20 hrs)  → VPS + Coolify + Basic Deploys
Phase 2: WordPress Automation (20 hrs)  → Full WP Lifecycle Management
Phase 3: AI Content           (24 hrs)  → AI-Generated Sites + Content
Phase 4: DNS Migration        (10 hrs)  → Cloudflare + CDN + WAF
Phase 5: Staging Environments (13 hrs)  → Safe Testing + Promotion
Phase 6: Advanced Monitoring  (14 hrs)  → Logs + Metrics + Alerts
Phase 7: Multi-Server         (11 hrs)  → Scale Across VPSes
Phase 8: Business Automation  (14 hrs)  → n8n + Workflows

TOTAL: ~126 hours (15-20 working days)
```

**Capabilities:**

```bash
# Deploy WordPress site with AI content
fabrik new wp-site client-site --domain=client.com
fabrik apply client-site
fabrik ai generate-website client-site \
  --business="Client Corp" \
  --services="Web Design,SEO,Marketing"

# Create staging, test, promote
fabrik staging:create client-site
fabrik staging:sync client-site
fabrik staging:promote client-site

# Monitor everything
fabrik monitor status
fabrik monitor logs --container=client-site
fabrik automation list

# Scale to multiple servers
fabrik servers list
fabrik apply new-site --server=greencloud-2

# Automated notifications
# → Lead forms → Slack + Email
# → Site down → Instant alert
# → Daily reports → Automated
```

**You now have a complete, professional-grade deployment platform.**
