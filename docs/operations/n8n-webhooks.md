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

Workflow nodes POST to `http://apprise:8005/notify` with `urls`, `title`, and `body` fields. Notification URLs are stored as **n8n credentials** for reusability and secret management.

### Setup: Create n8n Credential for Apprise URLs

Store notification URLs as reusable n8n credentials (not inline in workflows):

1. Open n8n: `https://auto.vps1.ocoron.com`
2. Go to **Settings** > **Credentials** > **Add Credential**
3. Select type: **Header Auth** (or create a custom credential type)
4. Name: `apprise-notification-urls`
5. Value: Your Apprise notification URLs (e.g., `slack://tokenA/tokenB/tokenC,tgram://bot/chat`)
6. Save the credential

### How It Works

1. Notification URLs are stored in n8n credentials (single source of truth)
2. Workflow HTTP Request nodes reference the credential via expression: `{{ $credentials.apprise-notification-urls }}`
3. HTTP Request nodes POST to `http://apprise:8005/notify` with `urls`, `title`, and `body`
4. Apprise resolves the URLs and dispatches notifications

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

After importing a workflow, verify the Apprise endpoint and credential are working:

```bash
# 1. Verify Apprise is reachable
curl -X POST http://apprise:8005/notify \
  -H "Content-Type: application/json" \
  -d '{"urls": "slack://tokenA/tokenB/tokenC", "title": "Test", "body": "n8n integration test"}'

# 2. Verify n8n credential is set:
#    - Open workflow in n8n UI
#    - Check HTTP Request node references `apprise-notification-urls` credential
#    - Trigger manual execution to confirm notifications are delivered
```

If the credential is not configured, create it per the Setup section above.

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
- Verify the `apprise-notification-urls` credential is configured in n8n (Settings > Credentials)
- Verify workflow HTTP Request nodes reference the credential correctly
- Test the endpoint directly: `curl -X POST http://apprise:8005/notify -H "Content-Type: application/json" -d '{"urls": "slack://tokenA/tokenB/tokenC", "title": "Test", "body": "Ping"}'`
- Check n8n execution log for HTTP errors

### n8n health check failing

```bash
# Check health endpoint (curl is used by the container healthcheck)
curl -f http://localhost:5678/healthz

# Check container logs
docker logs n8n --tail 50
```

The n8n container uses `curl -f http://localhost:5678/healthz` for its healthcheck (defined in `specs/infrastructure/n8n.yaml`). The `/healthz` endpoint is available by default in n8n without additional configuration.
