# n8n Webhook Operations

**Last Updated:** 2026-06-16 (re-verified vs live n8n + Authelia + specs)

---

## Overview

n8n is deployed as a business automation platform at `https://auto.vps1.ocoron.com`.

> **Authentication:** n8n v1.0+ removed basic auth (there are no `N8N_USER` / `N8N_PASSWORD` env vars in `specs/infrastructure/n8n.yaml`). The instance is fronted by **Authelia SSO** — unauthenticated requests to `https://auto.vps1.ocoron.com/` return `302 → auth.vps1.ocoron.com` (verified live). After Authelia, you log in to n8n with the **owner account** created via the first-run setup wizard.

| Setting | Value |
|---------|-------|
| **Base URL** | `https://auto.vps1.ocoron.com` |
| **Auth** | Authelia SSO (302 → `auth.vps1.ocoron.com`) fronting the n8n owner-account login |
| **Internal port** | 5678 |
| **Apprise internal** | `http://apprise:8000/notify` (Docker network) |
| **Apprise external** | `https://notify.vps1.ocoron.com` (Traefik → internal 8000; no host port) |
| **Spec** | `specs/infrastructure/n8n.yaml` |

> **Port Mapping:** Apprise publishes **no host port** — Traefik routes `notify.vps1.ocoron.com` to the container's internal `8000` over the `fabrik` network.
> - **n8n → Apprise** (inside Docker): `http://apprise:8000/notify`
> - **External access**: `https://notify.vps1.ocoron.com` (Traefik reaches Apprise over the `fabrik` Docker network on internal port 8000 — the deployed compose publishes no host port)
>
> See `specs/infrastructure/apprise.yaml` and `PORTS.md` for details.

---

## Webhook Endpoints

| Webhook | Path | Method | Trigger |
|---------|------|--------|---------|
| Uptime Alert | `/webhook/uptime-alert` | POST | Gatus notification |
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

> **⚠️ Current behavior (verified live 2026-06-16):** The `/webhook/*` paths are **behind Authelia** — no bypass rule exists for them. The commands below currently return **`303 → auth.vps1.ocoron.com`** (an HTML auth redirect), *not* the documented JSON. For true external webhook delivery (e.g. from Gatus or third parties), a **Traefik/Authelia bypass rule for `auto.vps1.ocoron.com/webhook/*`** must be added — **this is a current gap.** The "Expected Responses" below assume that bypass is in place (or that the request carries a valid `authelia_session` cookie).

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

## Gatus Integration

Configure Gatus to send alerts to n8n:

1. Open Gatus: `https://status.vps1.ocoron.com`
2. Go to **Settings** > **Notifications**
3. Click **Setup Notification**
4. Select type: **Webhook**
5. Set URL: `https://auto.vps1.ocoron.com/webhook/uptime-alert`
6. Method: **POST**
7. Content-Type: `application/json`
8. Click **Test** to verify
9. Click **Save**

The webhook receives `status` (`down`/`up`) and `monitor.name` fields, which n8n routes through the switch node to `http://apprise:8000/notify` (internal Docker port) with appropriate alert titles and notification type.

---

## Apprise Notification Configuration

Workflow nodes POST to `http://apprise:8000/notify` (internal Docker port) with `urls`, `title`, and `body` fields.

> **Note:** Workflow JSON files in `configs/n8n/workflows/` contain **placeholder notification URLs** (`slack://tokenA/tokenB/tokenC`). After importing, configure credentials for reusability (preferred) or edit nodes directly.

### Recommended: Create n8n Credentials for Notification URLs

Store notification URLs as reusable n8n credentials to avoid per-node edits:

1. Open n8n: `https://auto.vps1.ocoron.com`
2. Go to **Credentials** → **Add Credential**
3. Select type: **Header Auth** (or create custom credential type)
4. Configure:
   - **Name:** `apprise-slack-urls` (or per-channel: `apprise-telegram-urls`)
   - **Header Name:** `X-Apprise-URLs` (placeholder, not actually used in header)
   - **Header Value:** Your Apprise URL(s), e.g., `slack://tokenA/tokenB/tokenC`
5. Save the credential

**Using credentials in workflows:**

After creating credentials, update HTTP Request nodes to reference them:

1. Open the workflow
2. Click the HTTP Request node (e.g., "Notify")
3. In **Body Parameters** → `urls`, use expression: `{{ $credentials.apprise-slack-urls.headerValue }}`
4. Attach the credential to the node
5. Save and activate

**Benefits:**
- Single source of truth for notification URLs
- Change URLs in one place, all workflows update
- No need to edit each node individually after import

### Alternative: Direct Node Editing

If credentials are not desired, edit nodes directly after import:

1. Open n8n: `https://auto.vps1.ocoron.com`
2. Open the imported workflow
3. Click each HTTP Request node (e.g., "Notify", "Alert Down", "Alert Up")
4. In **Body Parameters**, replace the `urls` value (`slack://tokenA/tokenB/tokenC`) with your actual Apprise notification URLs
5. Save and activate the workflow

### How It Works

1. HTTP Request nodes POST to `http://apprise:8000/notify` (internal) with `urls`, `title`, and `body`
2. Apprise resolves the URLs and dispatches notifications to configured channels

### Payload Contract

Each notification node sends the following JSON body to `POST http://apprise:8000/notify` (internal):

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

After importing and configuring a workflow, verify the Apprise endpoint is working:

```bash
# 1. Verify Apprise is reachable (from inside Docker network)
curl -X POST http://apprise:8000/notify \
  -H "Content-Type: application/json" \
  -d '{"urls": "slack://tokenA/tokenB/tokenC", "title": "Test", "body": "n8n integration test"}'

# 2. Verify workflow is configured:
#    - Open workflow in n8n UI
#    - Confirm placeholder URLs have been replaced with actual notification URLs
#    - Trigger manual execution to confirm notifications are delivered
```

If notifications fail, check that placeholder URLs have been replaced with your actual Apprise notification URLs.

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
| `backup-notification.json` | Daily cron -> backrest status -> Apprise notification |
| `uptime-alert.json` | Webhook -> switch (down/up) -> Apprise alert |
| `webhook-test.json` | Webhook -> echo response (for testing) |

> **Note:** The live backup tool on vps1 is **backrest** (container `backrest`), not Duplicati. The `configs/n8n/workflows/backup-notification.json` workflow JSON itself still contains stale `duplicati` node references and needs updating before import.

### Import Steps

1. Open n8n: `https://auto.vps1.ocoron.com`
2. Authenticate via Authelia (302 → `auth.vps1.ocoron.com`), then log in to n8n with the owner account
3. Go to **Settings** > **Import from file**
4. Select the JSON file from `configs/n8n/workflows/`
5. **Replace placeholder notification URLs** (`slack://tokenA/tokenB/tokenC`) in each HTTP Request node with your actual Apprise URLs — see [Apprise Notification Configuration](#apprise-notification-configuration)
6. Activate the workflow

---

## Troubleshooting

### Webhook returns 404

- Ensure the workflow is **active** (toggled on in n8n UI)
- Check the webhook path matches exactly (`/webhook/uptime-alert`, not `/webhook/uptime-alert/`)

### Apprise notification not received

- Verify Apprise is running: `curl http://apprise:8000/` (internal port)
- Verify placeholder URLs have been replaced with actual notification URLs in each HTTP Request node
- Test the endpoint directly (from Docker network): `curl -X POST http://apprise:8000/notify -H "Content-Type: application/json" -d '{"urls": "YOUR_ACTUAL_URL", "title": "Test", "body": "Ping"}'`
- Check n8n execution log for HTTP errors

### n8n health check failing

```bash
# Check health endpoint (wget is used by the container healthcheck — the n8n image has no curl)
wget -qO- http://localhost:5678/healthz

# Check container logs
docker logs n8n --tail 50
```

The n8n container uses `wget -qO- http://localhost:5678/healthz` for its healthcheck (defined in `specs/infrastructure/n8n.yaml`) — the n8n image ships without `curl`. The `/healthz` endpoint is available by default in n8n without additional configuration and returns `{"status":"ok"}`.
