# VPS Complete Service Inventory

**Date:** 2026-05-03
**Method:** SSH docker ps + Coolify API + Cloudflare DNS verification
**Total Containers:** 40 running

## How to re-verify this document

Every claim below was generated from live VPS state at the snapshot time above. To re-verify (or detect drift later), run the following on the VPS. Every command in this block is read-only.

```bash
# 1. Firewall rules (iptables DOCKER-USER)
sudo iptables -L DOCKER-USER -n -v --line-numbers

# 2. Host port bindings (all listening sockets + owning process)
sudo ss -tlnp

# 3. Traefik routers + middleware (via Traefik API, localhost only)
curl -s http://127.0.0.1:8080/api/http/routers | python3 -m json.tool

# 4. Docker network topology
sudo docker network inspect coolify --format '{{range .IPAM.Config}}{{.Subnet}} {{end}}'
sudo docker network ls | wc -l

# 5. Container inventory
sudo docker ps --format '{{.Names}}\t{{.Image}}\t{{.Ports}}'
sudo docker ps -q | wc -l

# 6. Authelia policy vs Traefik middleware audit
#    'errors' is intentionally NOT in this list — GlitchTip uses app-layer TOTP
#    (LESSONS_LEARNT.md §8.13). Should print 6x "OK" and 0x "GAP".
curl -s http://127.0.0.1:8080/api/http/routers | python3 -c "
import json,sys
ADMIN = {'auto','backup','coolify','monitor','netdata','notify'}
for r in json.load(sys.stdin):
    rule = r.get('rule','')
    for h in ADMIN:
        if f'{h}.vps1' in rule:
            mws = r.get('middlewares',[]) or []
            ok = any('authelia' in m for m in mws)
            print('OK' if ok else 'GAP', h, mws)"

# 7. External reachability of supposedly-blocked ports (should all timeout)
for p in 8000 8010 8011 8080; do
  echo -n "port $p: "; timeout 5 curl -sSo /dev/null -w "%{http_code}\n" --max-time 5 "http://172.93.160.197:$p/" || echo "TIMEOUT (good — DOCKER-USER dropped)"
done

# 8. DROP counter delta: should increment by the exact number of external probes above
sudo iptables -L DOCKER-USER -n -v | tail -1
```

**Drift detection:** run commands 1, 3, 6, and 8 weekly (or before any deploy). If output changes, update this document and add the finding to `LESSONS_LEARNT.md`.

## How to reach each service

Three flavours of access. Pick the row that matches what you're doing.

### A) Browser (you, a human)

Open the URL. If the service is Authelia-protected you'll be bounced to `https://auth.vps1.ocoron.com` for 2FA (TOTP or the fallback codes in `ssh vps 'sudo cat /opt/authelia/config/notification.txt'`).

| Purpose | URL | Auth |
|---|---|---|
| Deployment control plane | `https://coolify.vps1.ocoron.com` | Authelia 2FA → then Coolify login |
| Error tracking | `https://errors.vps1.ocoron.com` | **GlitchTip native login + TOTP** (no Authelia — see §8.13) |
| Metrics dashboards (Prom + Loki) | `https://monitor.vps1.ocoron.com` | Authelia 2FA → Grafana auto-login |
| Real-time host metrics | `https://netdata.vps1.ocoron.com` | Authelia 2FA |
| Uptime status board | `https://status.vps1.ocoron.com` | **Public** — no auth |
| Backup dashboard (Restic/B2) | `https://backup.vps1.ocoron.com` | Authelia 2FA |
| Workflow automation | `https://auto.vps1.ocoron.com` | Authelia 2FA → n8n login |
| Notifications sandbox | `https://notify.vps1.ocoron.com` | Authelia 2FA |
| Authelia itself (2FA portal) | `https://auth.vps1.ocoron.com` | Authelia login |
| Public marketing site | `https://ocoron.com` | **Public** |

### B) Programmatic API (machine-to-machine with Bearer/token auth)

All API endpoints sit behind Traefik on port 443 and use the same `*.vps1.ocoron.com` hostnames. Authelia bypasses them on either an `X-Internal-Token` header (Fabrik microservices) or a path pattern (`^/api/` on Coolify/Grafana). Tokens live in `/opt/fabrik/.env`.

| Service | Endpoint pattern | Auth header | Token env var |
|---|---|---|---|
| Coolify API | `https://coolify.vps1.ocoron.com/api/v1/*` | `Authorization: Bearer $TOKEN` | `COOLIFY_API_TOKEN` |
| Grafana API (internal only) | `http://<container-IP>:3000/api/*` (from VPS) | `Authorization: Bearer $TOKEN` | `GRAFANA_SERVICE_ACCOUNT_TOKEN` |
| GlitchTip API | `https://errors.vps1.ocoron.com/api/0/*` | `Authorization: Bearer $TOKEN` | `GLITCHTIP_AUTH_TOKEN` |
| DNS Manager / site-provisioner | `https://dns.vps1.ocoron.com/api/*` | `X-Internal-Token: $TOKEN` | `SITE_PROVISIONER_TOKEN` |
| Captcha solver | `https://captcha.vps1.ocoron.com/*` | `X-Internal-Token: $TOKEN` | `CAPTCHA_INTERNAL_TOKEN` |
| Translator | `https://translator.vps1.ocoron.com/*` | `X-Internal-Token: $TOKEN` | `TRANSLATOR_INTERNAL_TOKEN` |
| Proxy manager | `https://proxy.vps1.ocoron.com/*` | `X-Internal-Token: $TOKEN` | `PROXY_INTERNAL_TOKEN` |
| Image broker | `https://images.vps1.ocoron.com/api/v1/*` | `X-Internal-Token: $TOKEN` | `IMAGE_BROKER_INTERNAL_TOKEN` |
| Email gateway | `https://emailgateway.vps1.ocoron.com/*` | `X-Internal-Token: $TOKEN` | `EMAIL_GATEWAY_INTERNAL_TOKEN` |
| File API | `https://files-api.vps1.ocoron.com/*` | `X-Internal-Token: $TOKEN` | `FILE_API_INTERNAL_TOKEN` |
| Gotenberg (HTML→PDF) | `https://pdf.vps1.ocoron.com/forms/*` | `X-Internal-Token: $TOKEN` | `GOTENBERG_INTERNAL_TOKEN` |
| Browserless (headless Chrome) | `https://browser.vps1.ocoron.com/*?token=…` | query-string token | `BROWSERLESS_TOKEN` |
| MeiliSearch | `https://search.vps1.ocoron.com/indexes/*` | `Authorization: Bearer $MASTER_KEY` | `MEILISEARCH_MASTER_KEY` |
| Apprise (notification posts) | `https://notify.vps1.ocoron.com/notify/alerts` | *(token-less — stateless by design)* | — |
| Gatus health probes | `https://status.vps1.ocoron.com/api/v1/endpoints/statuses` | *(public read-only)* | — |

**Example calls:**

```bash
# List Coolify services
curl -H "Authorization: Bearer $COOLIFY_API_TOKEN" \
  "https://coolify.vps1.ocoron.com/api/v1/services"

# Render HTML to PDF
curl -X POST -H "X-Internal-Token: $GOTENBERG_INTERNAL_TOKEN" \
  -F "files=@page.html" \
  "https://pdf.vps1.ocoron.com/forms/chromium/convert/html" \
  -o page.pdf

# Search images
curl -H "X-Internal-Token: $IMAGE_BROKER_INTERNAL_TOKEN" \
  "https://images.vps1.ocoron.com/api/v1/search?q=sunset&provider=pexels"
```

### C) Intra-VPS (container-to-container on the `coolify` Docker network)

All Coolify-managed containers get a short-name DNS alias (`grafana`, `prometheus`, `apprise`, `postgres-main`, …). Use the alias + the **container's internal port**, not the public hostname:

| From → To | URL | Notes |
|---|---|---|
| any → Grafana | `http://grafana:3000` | Admin API needs `Authorization: Bearer` token |
| any → Prometheus | `http://prometheus:9090` | No auth; localhost-equivalent |
| any → Loki | `http://loki:3100` | Log ingest + query |
| any → Alertmanager | `http://alertmanager:9093` | |
| any → Apprise | `http://apprise:8000/notify/alerts` | POST `{title,body,type}` |
| any → Postgres (shared) | `postgres://postgres:$PW@postgres-main:5432/<db>` | Password in `/opt/fabrik/.env` |
| any → Redis (shared) | `redis://:$PW@redis-main:6379/<db>` | Use DB index to separate tenants |
| any → MeiliSearch | `http://search:7700` | `Authorization: Bearer $MASTER_KEY` |
| any → Gotenberg | `http://pdf:3000/forms/...` | No `X-Internal-Token` needed internally |
| any → Browserless | `http://browser:3000` | Local, no token |
| any → Authelia (forward-auth only) | `http://authelia:9091/api/verify` | Called by Traefik, not apps |

> **If DNS fails** with `wget: bad address`: the client container probably only got an IPv6 answer from Docker's embedded resolver. Either restart the client container or resolve the IPv4 via `docker inspect`. See `LESSONS_LEARNT.md §8.2`.

### D) Host shell (you, via SSH)

```bash
ssh vps                                         # SSH alias in ~/.ssh/config, user=ozgur
# Then:
sudo docker ps                                  # inventory
sudo docker logs -f <container> --tail 200      # live logs
curl -s http://127.0.0.1:8080/api/http/routers  # Traefik API (localhost only)
sudo iptables -L DOCKER-USER -n -v              # firewall rules
```

### E) VPN (OpenVPN server is running on UDP 1194)

Not currently used for service access; it's there for emergency LAN-style access if the VPS network config breaks routable SSH. Config lives in `/etc/openvpn/server/`. Not wired into any Fabrik workflow today.

---

## Topology (at a glance)

```text
                                 ┌─────────────────────────────────────┐
                                 │   INTERNET (public)                 │
                                 │   172.93.160.197                    │
                                 └───────────────┬─────────────────────┘
                                                 │
        HOST-LEVEL PORTS (NOT under iptables DOCKER-USER — these bypass it):
          • tcp 22    → sshd  (OpenSSH, systemd-managed)
          • udp 1194  → openvpn-server@server.service (active since 2026-03-19)
          • tcp 25    → postfix  (127.0.0.1 only, local MTA)
                                                 │
                  ┌──────────────────────────────┴───────────────────────────────┐
                  │  iptables DOCKER-USER chain  (covers Docker-published ports) │
                  │  ──────────────────────────────────────────────────────────  │
                  │  RETURN  ctstate RELATED,ESTABLISHED                         │
                  │  RETURN  src 10.0.0.0/8  172.16.0.0/12  192.168.0.0/16       │
                  │  RETURN  tcp dpt:80, dpt:443, dpt:6001, dpt:6002             │
                  │  DROP    everything else   (counter actively incrementing)   │
                  │  → ports 8000/8010/8011/8080 ARE bound on host but DROPPED   │
                  │    externally by this chain. Verified via timeout on curl.   │
                  └──────────────────────────────┬───────────────────────────────┘
                                                 │ :80 / :443
                                     ┌───────────▼─────────────┐
                                     │   TRAEFIK v2.11         │
                                     │   container: `traefik`  │
                                     │   compose: /opt/traefik │
                                     │   (NOT Coolify-managed; │
                                     │    coolify-proxy v3.6   │
                                     │    exists but inactive) │
                                     │                         │
                                     │   - TLS (letsencrypt)   │
                                     │   - 30 routers          │
                                     │   - Docker provider     │
                                     │   - :8080 127.0.0.1 only│
                                     └─┬─────────┬──────┬──────┘
                                       │         │      │
            ┌──────────────────────────┘         │      └──────────────────────────────┐
            │                                    │                                     │
            │  forward-auth middleware           │  NO Authelia middleware              │  IP-allowlist
            │  = authelia-forward@docker         │  (public OR X-Internal-Token)        │  middleware
            │                                    │                                      │
            ▼                                    ▼                                      ▼
     ┌──────────────┐                    ┌──────────────┐                      ┌─────────────────┐
     │  AUTHELIA    │◄─ forward request  │  PUBLIC or   │                      │ provision.vps1  │
     │  (2FA gate)  │   decision         │  API-TOKEN   │                      │ (site-provison) │
     │              │                    │  PROTECTED   │                      │  IP allowlist   │
     │ auto.*       │                    │              │                      └─────────────────┘
     │ backup.*     │                    │  ocoron.com  │
     │ monitor.*    │                    │  www.ocoron. │
     │ netdata.*    │                    │  status.*    │
     │ notify.*     │                    │  wp-test.*   │
     │ coolify.*    │ (fixed 2026-04-18) │  auth.*      │ ← Authelia itself
     │ errors.*     │ (fixed 2026-04-18) │  captcha.*   │ ← X-Internal-Token
     │              │                    │  translator.*│
     │              │                    │  proxy.*     │
     │              │                    │  files-api.* │
     │              │                    │  images.*    │
     │              │                    │  pdf.*       │
     │              │                    │  browser.*   │
     │              │                    │  search.*    │
     │              │                    │  dns.*       │
     │              │                    │  emailgate.* │
     └──────┬───────┘                    └──────┬───────┘
            │                                   │
            └──────────┬────────────────────────┘
                       │
                       │  Docker network: `coolify`
                       │    IPv4: 10.0.1.0/24
                       │    IPv6: fdd7:c299:c60::/64
                       │  (Docker embedded DNS at 127.0.0.11;
                       │   see LESSONS_LEARNT.md §8.2 for the
                       │   AAAA-only resolution trap.)
         ┌─────────────┴────────────────────────────────────────────┐
         │                                                          │
         │         ALL COOLIFY-MANAGED SERVICES                     │
         │         (27 containers, each also on its own UUID net)   │
         │                                                          │
         │  grafana   prometheus  alertmanager  loki       netdata  │
         │  apprise   n8n         backrest      authelia   gatus    │
         │  cadvisor  node-exp.   promtail      glitchtip  ...      │
         │  postgres-main     site-provisioner  image-broker ...    │
         │                                                          │
         │  Coolify assigns short-name aliases (e.g. `grafana`,     │
         │  `prometheus`, `apprise`) for intra-network service      │
         │  discovery — no UUID suffix needed.                      │
         └──────────────────────────────────────────────────────────┘

     ┌──────────────────────────────────────────────────────────────┐
     │  STANDALONE (not Coolify-managed)                            │
     │  ────────────────────────────────                            │
     │  coolify, coolify-db, coolify-redis, coolify-realtime,       │
     │  coolify-sentinel  (self-managed)                            │
     │  redis-main, traefik  (shared infra)                         │
     │  ocoron-com-* (5 WordPress containers on internal + coolify) │
     └──────────────────────────────────────────────────────────────┘
```

### ✅ Invariant compliance — no host port bindings on Fabrik microservices

Live check `sudo docker ps --format '{{.Names}} | {{.Ports}}' | grep -iE 'captcha|image-broker|translator|proxy|emailgateway|file-api|file-worker|site-provisioner'` shows **only internal ports** (`8000/tcp`, `3000/tcp`, `8001/tcp` — no `0.0.0.0:`), as required by the `AGENTS.md` invariant *"Never expose container ports to the host via `ports:`; all external traffic goes through Traefik."*

Previously (up to 2026-04-18 17:30 UTC+3), `image-broker` published `0.0.0.0:8010` and `captcha` published `0.0.0.0:8011`. Fixed in upstream repos `mobasak/image-broker@5773917` and `mobasak/captcha@f40cc0b` by removing the `ports:` block from each `compose.yaml`. Coolify redeploys pull from these repos, so the fix is permanent and survives all future redeploys. See `LESSONS_LEARNT.md §8.10`.

### Notification chains

```text
Prometheus (rules) ─► Alertmanager ─► Telegram        (native telegram_configs)
Gatus (30 endpoints) ─► Apprise ─► Telegram          (Gatus posts Apprise-shape JSON)
Authelia (login codes) ─► /config/notification.txt   (filesystem only; SMTP disabled)
```

> **Do NOT** point Alertmanager → `http://apprise:8000/notify`. Apprise expects
> `{body,title,type}`; Alertmanager sends its own schema. HTTP 400 silently.

### Ports exposed on the host

| Port | Bind | Service | Purpose |
|------|------|---------|---------|
| 22 | `0.0.0.0` | sshd | SSH access |
| 80 | `0.0.0.0` | traefik | HTTP → HTTPS redirect + Let's Encrypt |
| 443 | `0.0.0.0` | traefik | HTTPS ingress |
| 6001 | `0.0.0.0` | coolify-realtime | Coolify websockets |
| 6002 | `0.0.0.0` | coolify-realtime | Coolify terminal |
| 8080 | `127.0.0.1` | traefik API | Localhost-only (dashboard, routers list) |
| 8000 | — | coolify | Accessed via `coolify.vps1.ocoron.com`, **not** port 8000 |

All other container ports are **internal only** (enforced by iptables DOCKER-USER).

---

## Authelia protection audit (2026-04-18)

Authelia's `access_control` policy in `/opt/authelia/config/configuration.yml` declares 2FA for all `*.vps1.ocoron.com` except health endpoints, public sites, and explicitly-listed API services. **However, an Authelia policy is only enforced when Traefik attaches the `authelia-forward@docker` middleware to the router.** A service with no middleware reaches its backend regardless of Authelia's policy.

Live audit via Traefik API (`curl -s http://127.0.0.1:8080/api/http/routers` on VPS):

### ✅ Authelia forward-auth (middleware present) — 6 services

Services that lack native TOTP 2FA, gated by Authelia forward-auth. 302 to `auth.vps1.ocoron.com` on `/`.

| Domain | Service | Policy | Notes |
|---|---|---|---|
| `auto.vps1.ocoron.com` | n8n | `authelia-forward@docker` → `two_factor` | |
| `backup.vps1.ocoron.com` | Backrest | `authelia-forward@docker` → `two_factor` | |
| `coolify.vps1.ocoron.com` | **Coolify dashboard** | `authelia-forward@docker` → `two_factor` + `^/api/` bypass (§8.11) | Added 2026-04-18 via `/data/coolify/source/docker-compose.override.yml`. API path bypassed for Bearer-token machine callers. |
| `monitor.vps1.ocoron.com` | Grafana | `authelia-forward@docker` → `two_factor` + `^/api/` bypass (§8.11) | `^/api/` bypass added 2026-04-18 so `GRAFANA_SERVICE_ACCOUNT_TOKEN` can call `/api/annotations` for deploy markers. |
| `netdata.vps1.ocoron.com` | Netdata | `authelia-forward@docker` → `two_factor` | No native auth — forward-auth is the only boundary. |
| `notify.vps1.ocoron.com` | Apprise | `authelia-forward@docker` → `two_factor` | No native auth. |

### ✅ Full-bypass with native app-layer auth — 1 admin service + Fabrik microservices

Services with mature native auth + TOTP; forward-auth is intentionally absent per the decision matrix in `LESSONS_LEARNT.md §8.13`.

| Domain | Service | Auth boundary | Rationale |
|---|---|---|---|
| `errors.vps1.ocoron.com` | **GlitchTip** | django-allauth + TOTP 2FA (app-layer) + Bearer token on `/api/0/*` | **Moved to full-bypass 2026-04-18.** Authelia forward-auth broke the django-allauth SPA signup flow (§8.13). GlitchTip admin user `admin@ocoron.com` created via `./manage.py shell`; TOTP enforced at app layer. This is the Sentry-canonical deployment posture. |
| `auth.vps1.ocoron.com` | Authelia itself | Authelia's own login | Must be reachable without auth to serve the login flow. |

### ✅ Intentionally public / API-token protected — 14 services

Per Authelia `access_control` bypass rules (no Authelia middleware by design):

- **Public sites:** `ocoron.com`, `www.ocoron.com`, `wp-test.vps1.ocoron.com`, `status.vps1.ocoron.com`
- **API services (protected by `X-Internal-Token` header):** `captcha`, `translator`, `proxy`, `files-api`, `images`, `pdf`, `browser`, `search`, `dns`, `emailgateway`
- **IP allowlist:** `provision.vps1.ocoron.com` (legacy, restricted to known IPs)

### Health-endpoint bypass (all services)

`^/health$`, `^/healthz$`, `^/metrics$`, `^/api/health$` on `*.vps1.ocoron.com` are bypass-all by Authelia policy — used by Gatus for liveness probes without triggering 2FA.

### Summary (post-fix 2026-04-18)

- 6 dashboards behind Authelia forward-auth (services without native TOTP)
- 1 dashboard on full-bypass with app-layer TOTP (GlitchTip — Sentry-canonical pattern)
- All 7 administrative surfaces have a 2FA boundary somewhere; the split is by app architecture, not by sensitivity. See the decision matrix in `docs/DEPLOYMENT.md` Authelia section.
- 30 Traefik routers total; every one is either gated, Bearer-token-protected, IP-restricted, or intentionally public.

---

## Docker Networks

**Total:** 33 networks
- **coolify** - Main Coolify network (shared by most services)
- **bridge** - Default Docker bridge
- **host** - Host network mode
- **Service-specific networks** - Per-service isolation (30 networks)

## All Services Categorized

### 1. Coolify Core (5 containers - Standalone, DO NOT MIGRATE)

| Container | Image | Network | Managed By | Coolify? |
|-----------|-------|---------|------------|----------|
| coolify | ghcr.io/coollabsio/coolify:latest | coolify | Coolify itself | ❌ NO |
| coolify-db | postgres:15-alpine | coolify | Coolify itself | ❌ NO |
| coolify-redis | redis:7-alpine | coolify | Coolify itself | ❌ NO |
| coolify-realtime | ghcr.io/coollabsio/coolify-realtime:1.0.10 | coolify | Coolify itself | ❌ NO |

**Status:** Core Coolify infrastructure (self-managed, not via Coolify API)

**Note:** coolify-sentinel is now Coolify-managed (see Coolify-Managed Services section)

---

### 2. Monitoring Stack (10 containers - All Coolify-Managed)

| Container | Image | Network | Managed By | Coolify? |
|-----------|-------|---------|------------|----------|
| prometheus-c8cg0kosok4wswwcos04wwg0 | prom/prometheus:v3.2.1 | c8cg0kosok4wswwcos04wwg0,coolify | Coolify app | ✅ YES |
| grafana-loc484owg8gsw04owo0go8kc | grafana/grafana:11.6.1 | loc484owg8gsw04owo0go8kc,coolify | Coolify app | ✅ YES |
| alertmanager-zw4swgkwk0s4s8kg048gw80o | prom/alertmanager:v0.28.1 | zw4swgkwk0s4s8kg048gw80o,coolify | Coolify app | ✅ YES |
| loki-r48swckog008wosgwcs4g0g0 | grafana/loki:3.4.2 | r48swckog008wosgwcs4g0g0,coolify | Coolify app | ✅ YES |
| promtail-w0000ckgsgg048w0848okk08 | grafana/promtail:3.4.2 | w0000ckgsgg048w0848okk08,coolify | Coolify app | ✅ YES |
| cadvisor-r08sog4gwws88og048ows448 | gcr.io/cadvisor/cadvisor:v0.52.1 | r08sog4gwws88og048ows448,coolify | Coolify app | ✅ YES |
| node-exporter-doc8c8gkcgs88s8ckggw84o4 | prom/node-exporter:v1.9.1 | doc8c8gkcgs88s8ckggw84o4,coolify | Coolify app | ✅ YES |
| gatus-v8s4cokcwg0co4w8okkccc0w | twinproduction/gatus:latest | coolify + own | Coolify app | ✅ YES |
| glitchtip-web-z00kkck8c8cwo800kk440csk | glitchtip/glitchtip:latest | coolify + own | Coolify app | ✅ YES |
| glitchtip-worker-msgo0sg8gsgo4w4sscckc84g | glitchtip/glitchtip:latest | coolify + own | Coolify app | ✅ YES |

**Key Finding:** All monitoring stack services migrated to Coolify management (2026-04-17). However, 7 of them (prometheus, grafana, alertmanager, loki, promtail, cadvisor, node-exporter) were initially attached to only their per-service UUID network, leaving Traefik (on `coolify`) unable to proxy to them — users with a valid Authelia session hit HTTP 504. **Remediated 2026-04-18** by PATCH-ing each service's `docker_compose_raw` via Coolify API to add `coolify: external` as a second network. All 10 now on `coolify` + private network. See `LESSONS_LEARNT.md` → Lesson 25.

---

### 3. Core Infrastructure (3 containers)

| Container | Image | Network | Managed By | Coolify? |
|-----------|-------|---------|------------|----------|
| postgres-main-l0k4gk0kggc8okcwk0s4c8s8 | postgres:16-alpine | coolify,l0k4gk0kggc8okcwk0s4c8s8 | Coolify app | ✅ YES |
| redis-main | redis:7-alpine | coolify | Standalone | ❌ NO |
| traefik | traefik:v2.11 | coolify | Coolify itself | ❌ NO |

**Key Finding:**
- postgres-main migrated to Coolify (2026-04-17) and is on coolify network
- redis-main and traefik remain standalone (DO NOT MIGRATE)

---

### 4. Authentication & Notifications (2 containers - Coolify-Managed)

| Container | Image | Network | Managed By | Coolify? |
|-----------|-------|---------|------------|----------|
| authelia-hks48k8sg8o4co4co08co00o | authelia/authelia:latest | coolify,hks48k8sg8o4co4co08co00o | Coolify app | ✅ YES |
| apprise-lcocgs4gs8ksg4g08w40ows8 | caronc/apprise:latest | lcocgs4gs8ksg4g08w40ows8,coolify | Coolify app | ✅ YES |

**Key Finding:** Both migrated to Coolify management (2026-04-17). **Apprise** was initially isolated on its UUID-only network (same bug as the monitoring stack); remediated 2026-04-18 by PATCH-ing compose via Coolify API — `notify.vps1.ocoron.com` now reachable end-to-end. Authelia was already on both networks from day one.

**Authelia Migration Benefits (2026-04-17):**
- ✅ Unified backup via Backrest (auto-includes config + SQLite)
- ✅ Centralized secrets in Coolify UI
- ✅ Simplified Traefik integration (internal service names)
- ✅ Consistent management (29/29 services = 100%)
- ✅ No separate backup cron jobs
- ✅ No manual config file sync
- ✅ Volume management by Coolify

**Protected Dashboards:** 8 services (Coolify, n8n, Grafana, Netdata, Backrest, Apprise, GlitchTip, others)

---

### 5. Utilities (3 containers - Coolify-Managed)

| Container | Image | Network | Managed By | Coolify? |
|-----------|-------|---------|------------|----------|
| n8n-s8gwccsws0ccssw0wwgwsoks | n8nio/n8n:latest | s8gwccsws0ccssw0wwgwsoks,coolify | Coolify app | ✅ YES |
| netdata-kk4kcw4csksc48848go4o0wo | netdata/netdata:stable | kk4kcw4csksc48848go4o0wo,coolify | Coolify app | ✅ YES |
| backrest-l48000k44wc4gk8os88s8k0c | ghcr.io/garethgeorge/backrest:latest | coolify,l48000k44wc4gk8os88s8k0c | Coolify app | ✅ YES |

**Key Finding:** All migrated to Coolify management (2026-04-17). **n8n** was initially isolated on its UUID-only network (same bug as the monitoring stack); remediated 2026-04-18 via Coolify API PATCH — `auto.vps1.ocoron.com` now reachable end-to-end. Duplicati removed (replaced by backrest).

**Cleanup Results (2026-04-17):**
- Space reclaimed: 2.88GB (old service volumes ~100MB, dangling volumes 61.53MB, unused images 2.821GB)
- Containers removed: duplicati, grafana, prometheus, loki, alertmanager, promtail, cadvisor, node-exporter (8 total)
- Volumes removed: duplicati (1), netdata (3), n8n (1), apprise (1) - 6 total
- External volumes preserved: monitoring stack volumes reused by Coolify-managed containers

---

### 6. Fabrik Microservices (8 containers - All Coolify-Managed)

| Container | Purpose | Network | Managed By | Coolify? |
|-----------|---------|---------|------------|----------|
| captcha-j8gg4ggskkossc4gkwowk4os-140246184500 | Anti-Captcha | j8gg4ggskkossc4gkwowk4os,coolify | Coolify app | ✅ YES |
| translator-kgws0s4cscsosw8gg848cwgw-140305573177 | Translation | kgws0s4cscsosw8gg848cwgw,coolify | Coolify app | ✅ YES |
| proxy-v0cscowwsgkk88c4ckckgw0g-140350084065 | Proxy management | coolify,v0cscowwsgkk88c4ckckgw0g | Coolify app | ✅ YES |
| emailgateway-w4oocckkwko8kowggsw8sogc-140328040913 | Email gateway | coolify,w4oocckkwko8kowggsw8sogc | Coolify app | ✅ YES |
| image-broker-zo4ggs4g880skwkocwwkscgk-140330450088 | Stock image API | coolify,zo4ggs4g880skwkocwwkscgk | Coolify app | ✅ YES |
| file-api-bsswwg4kg480c000gksw004k-140449896537 | File operations | bsswwg4kg480c000gksw004k,coolify | Coolify app | ✅ YES |
| file-worker-nwcckwggw0o0g40gwskk8kk8-154849864122 | File processing | coolify,nwcckwggw0o0g40gwskk8kk8 | Coolify app | ✅ YES |
| site-provisioner-qokoksogwsk0c04gcs4swwgs-223724136560 | DNS Manager | coolify,qokoksogwsk0c04gcs4swwgs | Coolify app | ✅ YES |

**Key Finding:** All Fabrik microservices are on coolify network + their own UUID networks. Traefik can reach them.

---

### 7. WordPress Sites (5 containers - Standalone, DO NOT MIGRATE)

#### ocoron.com (5 containers)

| Container | Image | Network | Managed By | Coolify? |
|-----------|-------|---------|------------|----------|
| ocoron-com-wordpress-1 | wordpress:php8.3-fpm | ocoron-com-internal | Standalone compose | ❌ NO |
| ocoron-com-db-1 | mariadb:10.11 | ocoron-com-internal | Standalone compose | ❌ NO |
| ocoron-com-redis-1 | redis:7-bookworm | ocoron-com-internal | Standalone compose | ❌ NO |
| ocoron-com-nginx-1 | nginx:stable-alpine | ocoron-com-internal,coolify | Standalone compose | ❌ NO |
| ocoron-com-backup-1 | debian:bookworm-slim | ocoron-com-internal | Standalone compose | ❌ NO |

**Key Finding:** ocoron-com-nginx-1 is also on coolify network (for Traefik routing). WordPress sites have their own isolated networks, NOT managed by Coolify.

---

### 8. Infrastructure Services (3 containers - Coolify-Managed)

| Container | Purpose | Network | Managed By | Coolify? |
|-----------|---------|---------|------------|----------|
| bs0wo48k4gwo440gcowscoc8-150802066640 | MeiliSearch | coolify | Coolify app | ✅ YES |
| e04k4sco44ow04ccc0o0k00k-151256201601 | Gotenberg (PDF) | coolify | Coolify app | ✅ YES |
| vckgs8c00o40o884k48cgow8-150756746544 | Browserless | coolify | Coolify app | ✅ YES |

**Key Finding:** All infrastructure services are on coolify network only (no UUID networks). Traefik can reach them.

---

## Summary Statistics

**Total Containers:** 40 running

### By Management Type

| Type | Count | Percentage |
|------|-------|------------|
| **Coolify-managed** | 27 | 69% |
| **Standalone** | 12 | 31% |

### By Category

| Category | Total | Coolify-Managed | Standalone |
|----------|-------|-----------------|------------|
| Coolify Core | 5 | 0 | 5 |
| Monitoring Stack | 10 | 10 | 0 |
| Core Infrastructure | 3 | 1 | 2 |
| Auth & Notifications | 2 | 2 | 0 |
| Utilities | 3 | 3 | 0 |
| Fabrik Microservices | 8 | 8 | 0 |
| Infrastructure Services | 3 | 3 | 0 |
| WordPress Sites | 5 | 0 | 5 |

---

## DNS Domain Mappings

**Date:** 2026-05-03
**Zone:** ocoron.com (Cloudflare)
**Total A Records:** 23 (all point to `172.93.160.197`)

### Monitoring & Observability

| Domain | Service | Internal Port | Purpose |
|---|---|---|---|
| `monitor.vps1.ocoron.com` | Grafana | 3000 | Metrics dashboards (Prometheus + Loki) |
| `netdata.vps1.ocoron.com` | Netdata | 19999 | Real-time server metrics (CPU/RAM/disk) |
| `status.vps1.ocoron.com` | Gatus | 8080 | Uptime monitoring (30 endpoints) |
| `errors.vps1.ocoron.com` | GlitchTip | 8000 | Error tracking (Sentry-compatible) |

### Admin & Control

| Domain | Service | Internal Port | Purpose |
|---|---|---|---|
| `coolify.vps1.ocoron.com` | Coolify | 8000 | Deployment control plane |
| `auth.vps1.ocoron.com` | Authelia | 9091 | SSO/2FA forward-auth for admin dashboards |
| `backup.vps1.ocoron.com` | Backrest | 9898 | Restic-based backup UI → Backblaze B2 |
| `dns.vps1.ocoron.com` | DNS Manager (site-provisioner) | 8001 | Domain registration, DNS, website provisioning |
| `control.vps1.ocoron.com` | Fabrik Control Plane | — | Future web UI for Fabrik CLI (planned) |

### Fabrik Microservices

| Domain | Service | Internal Port | Purpose |
|---|---|---|---|
| `captcha.vps1.ocoron.com` | Captcha Solver | 8000 | Anti-Captcha solving |
| `translator.vps1.ocoron.com` | Translator | 8000 | DeepL + Azure translation |
| `proxy.vps1.ocoron.com` | Proxy Manager | 8000 | Webshare.io proxy management |
| `files-api.vps1.ocoron.com` | File API | 3000 | File operations |
| `images.vps1.ocoron.com` | Image Broker | 8000 | Stock image API (Pexels/Pixabay) |
| `emailgateway.vps1.ocoron.com` | Email Gateway | 3000 | Resend + SES email sending |

### Infrastructure Services

| Domain | Service | Internal Port | Purpose |
|---|---|---|---|
| `search.vps1.ocoron.com` | MeiliSearch | 7700 | Full-text and vector search |
| `pdf.vps1.ocoron.com` | Gotenberg | 3000 | HTML/Office/PDF conversion API |
| `browser.vps1.ocoron.com` | Browserless | 3000 | Headless Chrome as a service |
| `notify.vps1.ocoron.com` | Apprise | 8000 | Multi-channel notifications |
| `auto.vps1.ocoron.com` | n8n | 5678 | Workflow automation |

### Test Sites

| Domain | Service | Internal Port | Purpose |
|---|---|---|---|
| `wp-test.vps1.ocoron.com` | WordPress | 80 | Test WordPress deployment |
| `provision.vps1.ocoron.com` | Site Provisioner (legacy) | — | Old DNS manager endpoint (deprecated) |

### Root

| Domain | Service | Internal Port | Purpose |
|---|---|---|---|
| `vps1.ocoron.com` | VPS gateway | — | Root domain for the VPS |

**Security Note:** All services are routed through Traefik on ports 80/443. No container ports are exposed directly to the public (iptables DOCKER-USER rules enforce this). External traffic goes through Traefik, which handles SSL termination and routing to the appropriate internal container.

---

## Network Architecture

### Container Network Distribution

| Network | Containers | Purpose |
|---------|------------|---------|
| coolify | 12 | Main Coolify network - Traefik can reach these |
| coolify + own UUID | 21 | Coolify-managed services with additional isolation (all Coolify-managed services are now on coolify) |
| bridge | 1 | coolify-sentinel |
| ocoron-com-internal | 4 | WordPress site (ocoron.com) internal containers |
| Total | 39 | |

### Services ON coolify Network (Traefik Can Reach)

**Coolify-Managed (all 27 services):**
- Monitoring Stack (10): prometheus, grafana, alertmanager, loki, promtail, cadvisor, node-exporter, gatus, glitchtip-web, glitchtip-worker - all on coolify + own UUID networks
- Core Infrastructure (1): postgres-main - on coolify + own UUID network
- Auth & Notifications (2): authelia, apprise - on coolify + own UUID networks
- Utilities (3): n8n, netdata, backrest - on coolify + own UUID networks
- Fabrik Microservices (8): captcha, translator, proxy, file-api, file-worker, image-broker, emailgateway, site-provisioner - all on coolify + own UUID networks
- Infrastructure Services (3): meilisearch, gotenberg, browserless - on coolify network only

**Standalone (12 services):**
- Coolify Core (5): coolify, coolify-db, coolify-redis, coolify-realtime, coolify-sentinel - on coolify network (except coolify-sentinel on bridge)
- Shared Infrastructure (2): redis-main, traefik - on coolify network
- WordPress Sites (5): nginx on coolify + internal, others on internal only

**Status:** ✅ All Coolify-managed services are now on coolify network. Traefik can reach all services. Network issue fixed on 2026-04-18.

---

## Key Findings & Corrections

### ✅ Current State (2026-04-18 - Validated via SSH)

**Coolify-managed services (27 containers, UUID-suffixed):**
- Monitoring Stack (10): prometheus, grafana, loki, alertmanager, promtail, cadvisor, node-exporter, gatus, glitchtip-web, glitchtip-worker
- Core Infrastructure (1): postgres-main
- Auth & Notifications (2): authelia, apprise
- Utilities (3): n8n, netdata, backrest
- Fabrik Microservices (8): captcha, translator, proxy, file-api, file-worker, image-broker, emailgateway, site-provisioner
- Infrastructure Services (3): meilisearch, gotenberg, browserless

**Standalone services (12 containers, no UUID):**
- Coolify Core (5): coolify, coolify-db, coolify-redis, coolify-realtime, coolify-sentinel
- Core Infrastructure (2): traefik, redis-main
- WordPress Sites (5): ocoron-com-wordpress-1, ocoron-com-db-1, ocoron-com-redis-1, ocoron-com-nginx-1, ocoron-com-backup-1

**Migration Status:** All infrastructure services migrated to Coolify management (2026-04-17). Only Coolify core, shared infrastructure (traefik, redis-main), and WordPress sites remain standalone by design.

---

## Migration Recommendations

### Migration Status (2026-04-18)

✅ **Complete - All infrastructure services migrated to Coolify (2026-04-17):**
- Monitoring Stack (10): prometheus, grafana, loki, alertmanager, promtail, cadvisor, node-exporter, gatus, glitchtip-web, glitchtip-worker
- Auth & Notifications (2): authelia, apprise
- Utilities (2): n8n, netdata
- Core Infrastructure (1): postgres-main
- Infrastructure Services (4): meilisearch, gotenberg, browserless, backrest

❌ **DO NOT MIGRATE (by design):**
- Coolify Core (5): coolify, coolify-db, coolify-redis, coolify-realtime, coolify-sentinel (self-managed)
- Core Infrastructure (2): traefik, redis-main (shared infrastructure)
- WordPress Sites (5): ocoron-com-wordpress-1, ocoron-com-db-1, ocoron-com-redis-1, ocoron-com-nginx-1, ocoron-com-backup-1 (production sites)

---

## Conclusion

**Coolify Network Architecture:**
- Coolify uses a shared `coolify` network
- 33 of 39 containers are in the coolify network
- Being in the network ≠ being Coolify-managed
- 26 containers (67%) are Coolify-managed (UUID-suffixed)
- 13 containers (33%) are standalone (no UUID) by design

**Migration Status (2026-04-17):**
- All infrastructure services successfully migrated to Coolify management
- Zero downtime during all migrations
- 100% success rate (19 services migrated)
- Only Coolify core, shared infrastructure (traefik, redis-main), and WordPress sites remain standalone by design

**Recommendation:**
- Current state is production-ready
- No further migrations needed
- Standalone services (Coolify core, traefik, redis-main, WordPress) should remain standalone

---

## Coolify Management Status (Current)

**Date:** 2026-05-03
**Method:** Validated via SSH docker ps inspection

### Executive Summary

- **Coolify-Managed:** 27 services ✅
- **Standalone (Not Managed):** 12 services
- **Migration Progress:** 12/12 infrastructure services (100%) ✅
- **Backup Solution:** Backrest deployed (replaces Duplicati)
- **Cleanup Complete:** 2.88GB disk space reclaimed
- **Firewall:** Ports 6001, 6002 opened for real-time service
- **Status:** 🟢 **PRODUCTION READY**

### Coolify-Managed Services (27) - Current Health Status

#### Recently Migrated Infrastructure (12 services)

| Service | UUID | Status |
|---------|------|--------|
| netdata | kk4kcw4csksc48848go4o0wo | ✅ Healthy |
| n8n | s8gwccsws0ccssw0wwgwsoks | ✅ Healthy |
| apprise | lcocgs4gs8ksg4g08w40ows8 | ✅ Healthy |
| node-exporter | doc8c8gkcgs88s8ckggw84o4 | ✅ Healthy |
| promtail | w0000ckgsgg048w0848okk08 | ✅ Healthy |
| cadvisor | r08sog4gwws88og048ows448 | ✅ Healthy |
| loki | r48swckog008wosgwcs4g0g0 | ✅ Healthy |
| alertmanager | zw4swgkwk0s4s8kg048gw80o | ✅ Healthy |
| prometheus | c8cg0kosok4wswwcos04wwg0 | ✅ Healthy |
| grafana | loc484owg8gsw04owo0go8kc | ✅ Healthy |
| backrest | l48000k44wc4gk8os88s8k0c | ✅ Healthy |
| authelia | hks48k8sg8o4co4co08co00o | ✅ Healthy |

#### Fabrik Microservices (8 services)

| Service | Container Name | Status |
|---------|----------------|--------|
| captcha | captcha-j8gg4ggskkossc4gkwowk4os-140246184500 | ✅ Running |
| translator | translator-kgws0s4cscsosw8gg848cwgw-140305573177 | ✅ Running |
| emailgateway | emailgateway-w4oocckkwko8kowggsw8sogc-140328040913 | ✅ Running |
| image-broker | image-broker-zo4ggs4g880skwkocwwkscgk-140330450088 | ✅ Running |
| proxy | proxy-v0cscowwsgkk88c4ckckgw0g-140350084065 | ✅ Running |
| file-api | file-api-bsswwg4kg480c000gksw004k-140449896537 | ✅ Running |
| file-worker | file-worker-nwcckwggw0o0g40gwskk8kk8-154849864122 | ✅ Running |
| site-provisioner (dns-manager) | site-provisioner-qokoksogwsk0c04gcs4swwgs-223724136560 | ✅ Running |

#### Infrastructure Services (7 services)

| Service | Container Name | Status |
|---------|----------------|--------|
| postgres-main | postgres-main-l0k4gk0kggc8okcwk0s4c8s8 | ✅ Running |
| gatus | gatus-v8s4cokcwg0co4w8okkccc0w | ✅ Running |
| glitchtip-web | glitchtip-web-z00kkck8c8cwo800kk440csk | ✅ Running |
| glitchtip-worker | glitchtip-worker-msgo0sg8gsgo4w4sscckc84g | ✅ Running |
| meilisearch | bs0wo48k4gwo440gcowscoc8-150802066640 | ✅ Running |
| gotenberg | e04k4sco44ow04ccc0o0k00k-151256201601 | ✅ Running |
| browserless | vckgs8c00o40o884k48cgow8-150756746544 | ✅ Running |

### Standalone Services (12) - Not Coolify-Managed

#### Coolify Core (5 services)
- coolify - Main Coolify container
- coolify-db - Coolify PostgreSQL database
- coolify-redis - Coolify Redis cache
- coolify-realtime - Real-time communications
- coolify-sentinel - Sentinel service

#### Shared Infrastructure (2 services)
- redis-main - Shared Redis for all services
- traefik - Reverse proxy (managed by Coolify)

#### WordPress Sites (5 services)
- ocoron-com-wordpress-1 - Main WordPress site
- ocoron-com-db-1 - WordPress database
- ocoron-com-redis-1 - WordPress cache
- ocoron-com-nginx-1 - WordPress web server
- ocoron-com-backup-1 - WordPress backup

### Known Issues

#### GlitchTip Container Name Mismatch (Low Priority)

**Status:** ⚠️ Cosmetic issue - services are healthy

**Problem:** GlitchTip expects short container names (e.g., `netdata`) but Coolify uses UUID-suffixed names (e.g., `netdata-kk4kcw4csksc48848go4o0wo`).

**Impact:** Low - Error tracking works, but container-level monitoring may show false negatives.

**Priority:** LOW - Services are functional, error tracking is optional.

### Optional Improvements

1. Configure GlitchTip DSN for critical services (site-provisioner, emailgateway)
2. Import Grafana dashboards (1860 - Node Exporter, 14232 - Netdata)
3. Document all Gatus endpoints (17 files currently monitored)

### Firewall Configuration

| Port | Purpose | Status |
|------|---------|--------|
| 22 | SSH access | ✅ Open |
| 80 | HTTP / SSL cert generation | ✅ Open |
| 443 | HTTPS traffic | ✅ Open |
| 6001 | Real-time communications (WebSocket) | ✅ Open |
| 6002 | Terminal access | ✅ Open |
| 8000 | Coolify dashboard | ✅ Open |

### Backup & Security Status

- ✅ Backrest deployed - daily backups to Backblaze B2
- ✅ Authelia protecting 6 admin dashboards with 2FA
- ✅ postgres-main backed up daily (1.04 MB dumps)
- ✅ Meilisearch secured with master key

---

## Standalone Services - By Design

### Coolify Core (5 services - Self-Managed)

**Services:** coolify, coolify-db, coolify-redis, coolify-realtime, coolify-sentinel

**Status:** Self-managed by Coolify, not via Coolify API

**Reason:** Coolify manages itself. These are the core Coolify infrastructure containers that Coolify deploys and manages directly. They cannot be migrated to Coolify management via Coolify API.

**Action:** Keep standalone by design

### Core Infrastructure (2 services - Shared Infrastructure)

#### redis-main

**Container:** `redis-main`
**Image:** `redis:7-alpine`
**Used by:** Multiple services for caching

**Status:** Standalone (DO NOT MIGRATE)

**Reasons:**
- Shared cache infrastructure
- Multiple services depend on it
- Low benefit from migration
- Current setup is stable and proven

**Action:** Keep as standalone container

#### traefik

**Container:** `traefik`
**Image:** `traefik:v2.11`
**Purpose:** Reverse proxy for all services

**Status:** Standalone, managed by Coolify (DO NOT MIGRATE)

**Reasons:**
- Core reverse proxy for all services
- Coolify manages it directly
- Critical infrastructure component

**Action:** Keep standalone by design

### WordPress Sites (5 containers - Production Site)

#### ocoron.com

**Containers:** 5 (wordpress, nginx, db, redis, backup)
**Location:** `/opt/ocoron.com/compose.yaml`

**Status:** Standalone (DO NOT MIGRATE)

**Reasons:**
- Production site, high risk
- Current setup works fine
- Has its own isolated network
- WordPress requires specific configuration

**Action:** Keep standalone by design

---

## Final Recommendations

### Migration Status

**All infrastructure migrations completed (2026-04-17):**
- Monitoring Stack (10 services): prometheus, grafana, alertmanager, loki, promtail, cadvisor, node-exporter, gatus, glitchtip-web, glitchtip-worker
- Core Infrastructure (1 service): postgres-main
- Authentication & Notifications (2 services): authelia, apprise
- Utilities (3 services): n8n, netdata, backrest (replaced duplicati)
- Infrastructure Services (3 services): meilisearch, gotenberg, browserless

**Total migrated:** 19 services
**Migration success rate:** 100%
**Downtime:** Zero (rolling migrations)

### Current Architecture

**Production-ready state:**
- 69% of containers are Coolify-managed (27/39)
- 31% of containers are standalone by design (12/39)
- All critical infrastructure services migrated to Coolify
- Zero downtime during migrations

**Standalone services remain by design:**
- Coolify Core (5): Self-managed by Coolify
- Shared Infrastructure (2): redis-main, traefik
- WordPress Sites (5): Production site

### Architecture Benefits

**Current architecture provides:**
- Centralized management for all infrastructure services
- Clear separation of concerns
- Production stability (standalone WordPress, shared databases)
- Easy troubleshooting and monitoring
- Zero downtime capabilities

### No Further Migrations Needed

**Recommendation:** Keep current architecture
- All infrastructure services successfully migrated
- Standalone services are standalone by design for good reasons
- Current setup is production-ready and stable
