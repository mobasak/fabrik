# n8n Webhook Operations

**Last Updated:** 2026-03-01

---

## Overview

n8n is deployed as a business automation platform at `https://auto.vps1.ocoron.com`.

| Setting | Value |
|---------|-------|
| **Base URL** | `https://auto.vps1.ocoron.com` |
| **Auth** | Basic auth (`N8N_USER` / `N8N_PASSWORD`) |
| **Internal port** | 5678 |
| **Apprise endpoint** | `http://apprise:8005/notify` |
| **Spec** | `specs/infrastructure/n8n.yaml` |

---

## Webhook Endpoints

| Webhook | Path | Method | Trigger |
|---------|------|--------|---------|
| Uptime Alert | `/webhook/uptime-alert` | POST | Uptime Kuma notification |
| Test Endpoint | `/webhook/test` | POST | Manual testing |

---

## Payload Schemas

### Uptime Alert (`/webhook/uptime-alert`)

```json
{
  "status": "down",
  "monitor": {
    "name": "Service Name"
  }
}
```

| Field | Type | Required | Values |
|-------|------|----------|--------|
| `status` | string | Yes | `"down"` or `"up"` |
| `monitor.name` | string | Yes | Name of the monitored service |

### Test Endpoint (`/webhook/test`)

Accepts any JSON body. Returns the received payload in the response.

```json
{
  "test": "data"
}
```

---

## curl Test Commands

### Test Endpoint

```bash
curl -X POST https://auto.vps1.ocoron.com/webhook/test \
  -H "Content-Type: application/json" \
  -d '{"test": "data"}'
```

### Uptime Alert (Service DOWN)

```bash
curl -X POST https://auto.vps1.ocoron.com/webhook/uptime-alert \
  -H "Content-Type: application/json" \
  -d '{"status": "down", "monitor": {"name": "Test Service"}}'
```

### Uptime Alert (Service UP)

```bash
curl -X POST https://auto.vps1.ocoron.com/webhook/uptime-alert \
  -H "Content-Type: application/json" \
  -d '{"status": "up", "monitor": {"name": "Test Service"}}'
```

---

## Expected Responses

### Test Endpoint

```json
{
  "received": true,
  "timestamp": "2026-02-28T12:00:00.000Z",
  "data": {
    "test": "data"
  }
}
```

### Uptime Alert

n8n returns a standard `200 OK` with an empty body after processing. The notification is forwarded to Apprise asynchronously.

---

## Uptime Kuma Integration

Configure Uptime Kuma to send alerts to n8n:

1. Open Uptime Kuma: `https://status.vps1.ocoron.com`
2. Go to **Settings** > **Notifications**
3. Click **Setup Notification**
4. Select type: **Webhook**
5. Set URL: `https://auto.vps1.ocoron.com/webhook/uptime-alert`
6. Method: **POST**
7. Content-Type: `application/json`
8. Click **Test** to verify
9. Click **Save**

The webhook receives `status` (`down`/`up`) and `monitor.name` fields, which n8n routes through the switch node to `http://apprise:8005/notify` with appropriate alert titles and notification type.

---

## Apprise Notification Configuration

Workflow nodes POST directly to `http://apprise:8005/notify` with `urls`, `title`, and `body` fields. Notification URLs are configured as explicit values in each workflow's HTTP Request nodes — no n8n variables or preconfigured Apprise tags are required.

### Prerequisite: Set Notification URLs in Workflow Nodes

Before activating workflows, replace the placeholder notification URLs in each HTTP Request node:

1. Open n8n: `https://auto.vps1.ocoron.com`
2. Open the workflow to configure
3. Click each notification HTTP Request node (e.g., "Notify Success", "Alert Down")
4. In the **Body Parameters**, replace the `urls` value (`slack://tokenA/tokenB/tokenC`) with your actual Apprise notification URLs
5. Save the workflow

### How It Works

1. Notification URLs are configured directly in each workflow's HTTP Request node `urls` parameter
2. Workflow HTTP Request nodes POST to `http://apprise:8005/notify` with `urls`, `title`, and `body`
3. Apprise resolves the URLs and dispatches notifications directly — no tag lookup required

### Payload Contract

Each notification node sends the following JSON body to `POST http://apprise:8005/notify`:

```json
{
  "urls": "slack://tokenA/tokenB/tokenC",
  "title": "Notification Title",
  "body": "Notification body text"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `urls` | string | Yes | Comma-separated Apprise notification URLs |
| `title` | string | Yes | Notification title |
| `body` | string | Yes | Notification body text |

### Validating After Import

After importing a workflow, verify the Apprise endpoint is working:

```bash
# 1. Verify Apprise is reachable on port 8000
curl -X POST http://apprise:8005/notify \
  -H "Content-Type: application/json" \
  -d '{"urls": "slack://tokenA/tokenB/tokenC", "title": "Test", "body": "n8n integration test"}'

# 2. Then activate the workflow and trigger a manual execution in n8n UI
#    to confirm notifications are delivered.
```

If the `urls` value has not been replaced from the placeholder, Apprise will fail to deliver notifications.

### Supported Channels

| Channel | URL Format | Example |
|---------|-----------|---------|
| Slack | `slack://tokenA/tokenB/tokenC` | Incoming Webhook token |
| Email | `mailto://user:pass@host` | SMTP credentials |
| Telegram | `tgram://bottoken/ChatID` | Bot token + chat ID |
| Discord | `discord://webhook_id/webhook_token` | Discord webhook |
| Generic Webhook | `json://host/path` | Any JSON webhook |

See [Apprise documentation](https://github.com/caronc/apprise/wiki) for the full list of supported notification services.

---

## Workflow Import

Workflow JSON files are stored in `configs/n8n/workflows/`:

| File | Purpose |
|------|---------|
| `backup-notification.json` | Daily cron -> Duplicati status -> Apprise notification |
| `uptime-alert.json` | Webhook -> switch (down/up) -> Apprise alert |
| `webhook-test.json` | Webhook -> echo response (for testing) |

### Import Steps

1. Open n8n: `https://auto.vps1.ocoron.com`
2. Log in with basic auth credentials
3. Go to **Settings** > **Import from file**
4. Select the JSON file from `configs/n8n/workflows/`
5. **Replace placeholder notification URLs** in each HTTP Request node — see [Apprise Notification Configuration](#apprise-notification-configuration)
6. Activate the workflow

---

## Troubleshooting

### Webhook returns 404

- Ensure the workflow is **active** (toggled on in n8n UI)
- Check the webhook path matches exactly (`/webhook/uptime-alert`, not `/webhook/uptime-alert/`)

### Apprise notification not received

- Verify Apprise is running: `curl http://apprise:8005/`
- Verify the `urls` value in each workflow HTTP Request node has been replaced from the placeholder (`slack://tokenA/tokenB/tokenC`) with your actual notification URLs
- Test the endpoint directly: `curl -X POST http://apprise:8005/notify -H "Content-Type: application/json" -d '{"urls": "slack://tokenA/tokenB/tokenC", "title": "Test", "body": "Ping"}'`
- Check n8n execution log for HTTP errors

### n8n health check failing

```bash
# Check from inside Docker network (wget is available in the n8n container; curl is not)
wget -q -O - http://localhost:5678/healthz

# Check container logs
docker logs n8n --tail 50
```

The n8n container uses `wget --spider -q` for its healthcheck (defined in `specs/infrastructure/n8n.yaml`). The `/healthz` endpoint is explicitly enabled via `QUEUE_HEALTH_CHECK_ACTIVE: "true"` in the container environment.
