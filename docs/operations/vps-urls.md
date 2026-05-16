# VPS1 Service URLs

**Last Updated:** 2026-05-16 14:13 UTC
**VPS:** vps1.ocoron.com (172.93.160.197) — Los Angeles, CA
**Pattern:** All services via HTTPS through Traefik. HTTP auto-redirects to HTTPS.

---

<!-- AUTO:coolify_apps -->
| Name | FQDN | Status |
|---|---|---|
| `alertmanager` | internal | ⚠️ running:healthy |
| `apprise` | internal | ⚠️ running:healthy |
| `authelia` | internal | ⚠️ running:healthy |
| `backrest` | internal | ⚠️ running:unknown |
| `browserless` | https://browser.vps1.ocoron.com | ⚠️ running:unknown |
| `cadvisor` | internal | ⚠️ running:healthy |
| `fabrik-captcha` | internal | ⚠️ running:healthy |
| `fabrik-emailgateway` | internal | ⚠️ running:healthy |
| `fabrik-file-api` | internal | ⚠️ running:healthy |
| `fabrik-file-worker` | internal | ⚠️ running:healthy |
| `fabrik-image-broker` | internal | ⚠️ running:healthy |
| `fabrik-proxy` | https://proxy.vps1.ocoron.com | ⚠️ running:healthy |
| `fabrik-translator` | internal | ⚠️ running:healthy |
| `gatus` | internal | ⚠️ running:unknown |
| `glitchtip-web` | internal | ⚠️ running:unknown |
| `glitchtip-worker-v10` | internal | ⚠️ running:unknown |
| `gotenberg` | https://pdf.vps1.ocoron.com | ⚠️ running:healthy |
| `grafana` | internal | ⚠️ running:healthy |
| `loki` | internal | ⚠️ running:healthy |
| `meilisearch` | https://search.vps1.ocoron.com | ⚠️ running:healthy |
| `n8n` | internal | ⚠️ running:healthy |
| `netdata` | internal | ⚠️ running:healthy |
| `node-exporter` | internal | ⚠️ running:unknown |
| `postgres-main` | internal | ⚠️ running:healthy |
| `promtail` | internal | ⚠️ running:unknown |
| `site-provisioner` | internal | ⚠️ running:healthy |
| `test-file-api` | https://test-file-api.vps1.ocoron.com | ⚠️ running:healthy |
<!-- /AUTO -->

---

## Gatus Monitoring URLs

| Purpose | URL |
|---|---|
| Public status page | `https://status.vps1.ocoron.com` |
| Gatus internal health | `http://gatus:8080` (Docker internal) |

### Stable Docker DNS aliases
Gatus uses these names — never the raw UUID container names:
`browserless:3000`, `gotenberg:3000`, `meilisearch:7700`, `glitchtip-web:8000`

See `.windsurf/rules/55-observability.md` § "Gatus — Stable DNS Names" + `docs/reference/coolify-stable-aliases.md` for the full procedure when adding new single-image Applications.

## Manually-Added Public URLs (not in Coolify Apps)

| Purpose | URL | Auth |
|---|---|---|
| GlitchTip error reporting UI | `https://errors.vps1.ocoron.com` | Authelia |
| Public status page (Gatus) | `https://status.vps1.ocoron.com` | None |

GlitchTip is reachable internally (no auth) via `http://glitchtip-web:8000` on the `coolify` Docker network — the SDK ingestion uses this alias, not the public URL.

## Fabrik Microservices — GlitchTip DSN Convention

All 7 Fabrik microservices report errors to GlitchTip via Sentry-API-compatible SDK.
- **Primary env var**: `SENTRY_DSN` (what `fabrik apply` orchestrator injects automatically)
- **Fallback env var**: `GLITCHTIP_DSN` (read if SENTRY_DSN unset; for manual provisioning)
- **DSN format**: `http://<key>@glitchtip-web:8000/<project_id>` (internal alias, bypasses Authelia)
- **Public dashboard**: `https://errors.vps1.ocoron.com` (Authelia 2FA)

| Service | GlitchTip Project ID | firstEvent (2026-05-08) |
|---|---|---|
| captcha | 65 | ✅ flowing |
| image-broker | 66 | ✅ flowing |
| translator | 67 | ✅ flowing |
| emailgateway | 68 | ⚠️ idle (no errors yet) |
| file-api | 69 | ✅ flowing |
| file-worker | 70 | ⚠️ idle (no errors yet) |
| site-provisioner | 24 | ✅ flowing (CF errors visible) |

## Webshare.io API Key (fabrik-proxy)

The fabrik-proxy service uses Webshare's residential proxy backbone for outbound
egress (LinkedIn, Instagram, etc.). It also pulls a list of country-targeted
proxy IPs via Webshare's API.

- **Coolify env keys** on Application UUID `zsccsksoc8sssc8k00sgcc08`:
  - `WEBSHARE_API_KEY` (account-level API token)
  - `WEBSHARE_BACKBONE_USERNAME`
  - `WEBSHARE_BACKBONE_PASSWORD`
  - `WEBSHARE_BACKBONE_HOST` (default: `p.webshare.io`)
  - `WEBSHARE_BACKBONE_PORT` (default: `80`)
  - `WEBSHARE_IP_AUTH` (default: `false`)
- **Local working copy**: `/opt/proxy/.env` (must be kept in sync with Coolify)
- **IMPORTANT — env duplication**: Coolify maintains separate prod and preview env
  rows for each key. When rotating a value, **both must be PATCHed** otherwise
  the next preview deploy uses the stale value. See `docs/operations/deployment.md`
  Gotcha 7.
- **Last rotated**: 2026-05-08 (`WEBSHARE_API_KEY` only; backbone creds unchanged)

## Cloudflare API Token (site-provisioner)

The token used by site-provisioner to manage DNS lives in:
- **Coolify env**: `CLOUDFLARE_API_TOKEN` on Application UUID `qokoksogwsk0c04gcs4swwgs`
- **Local working copy**: `/opt/site-provisioner/.env` (must be kept in sync)
- **Token name (in Cloudflare)**: `dns-manager-full-access`
- **Status**: Active as of 2026-05-08 (rotated after the previous token was flagged "Exposed" by Cloudflare's leak detector)
- **Verify**: `curl -H "Authorization: Bearer $TOKEN" https://api.cloudflare.com/client/v4/user/tokens/verify`
- **Zones accessible**: ocoron.com, ozgurbasak.com, tojlo.com

⚠️ **Scope hardening recommended** — current token has `Account.Workers Scripts` + `Account.Account Settings` permissions which is broader than site-provisioner needs. Should be narrowed to `Zone.DNS:Edit` + `Zone.Zone:Read` + specific zones only.

## DNS Records (Cloudflare — all A → 172.93.160.197)

Active subdomains under `*.vps1.ocoron.com`:
`auth`, `auto`, `backup`, `browser`, `captcha`, `coolify`, `emailgateway`, `errors`, `files-api`, `images`, `monitor`, `netdata`, `notify`, `pdf`, `provision`, `proxy`, `search`, `status`, `translator`

Plus: `ocoron.com`, `www.ocoron.com`

---

## Port Reference

| Port | Binding | Status | Purpose |
|---|---|---|---|
| 22/tcp | `0.0.0.0:22` | ✅ ALLOW | SSH |
| 80/tcp | `0.0.0.0:80` | ✅ ALLOW | HTTP → Traefik → HTTPS |
| 443/tcp | `0.0.0.0:443` | ✅ ALLOW | HTTPS + OpenVPN |
| 1194/tcp | `0.0.0.0:1194` | ✅ ALLOW | OpenVPN |
| 6001-6002/tcp | `0.0.0.0:6001-6002` | ✅ ALLOW | Coolify Realtime / Soketi |
| 8000/tcp | `0.0.0.0:8000` | ❌ DENY | Coolify raw — blocked by UFW |
| 8080/tcp | `127.0.0.1:8080` | localhost only | Traefik API dashboard |

---

## Docker Connection Strings — Always Use These

```bash
# Database — NEVER localhost inside a container
DATABASE_URL=postgresql+asyncpg://postgres:<pass>@postgres-main:5432/<dbname>
DB_HOST=postgres-main
DB_PORT=5432

# Cache + Authelia sessions
REDIS_URL=redis://redis-main:6379/0
# Authelia uses: redis-main:6379 DB index 3

# Prometheus scrape targets (internal)
# prometheus:9090 → cadvisor:8080 → node-exporter:9100 → loki:3100 → netdata:19999
```

---

## Calling Another Service (M2M Pattern)

```python
import os, httpx
headers = {"X-Internal-Token": os.environ["SERVICE_INTERNAL_SECRET_KEY"]}
resp = httpx.get("https://translator.vps1.ocoron.com/api/translate", headers=headers)
```

```javascript
const headers = { 'X-Internal-Token': process.env.SERVICE_INTERNAL_SECRET_KEY };
const resp = await fetch('https://translator.vps1.ocoron.com/api/translate', { headers });
```

---

## Maintenance Commands

```bash
# After VPS reboot — reapply infra memory limits
ssh vps "bash /opt/fabrik/scripts/vps_apply_limits.sh"

# Full health audit
cd /opt/fabrik && python3 scripts/vps_sync.py --verify

# Deploy new service
cd /opt/fabrik && fabrik apply specs/services/<name>.yaml

# Redeploy (git push FIRST — Coolify pulls from GitHub not local /opt/)
cd /opt/<service> && git add -A && git commit -m "..." && git push
cd /opt/fabrik && fabrik redeploy fabrik-<name>

# Restart Authelia after config change (NEVER SIGHUP)
ssh vps "sudo docker restart authelia-hks48k8sg8o4co4co08co00o"

# Reload Prometheus after editing /opt/monitoring/configs/prometheus/prometheus.yml
ssh vps "cd /opt/prometheus && sudo docker compose restart"

# Weekly cleanup
ssh vps "sudo docker image prune -f && sudo docker builder prune -f"
```
