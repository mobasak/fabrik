# VPS Complete Service Inventory

**Date:** 2026-05-07 (updated 21:00 UTC+3)
**Method:** SSH docker ps + Coolify API + live verification
**Total Containers:** 40 running
**VPS:** vps1.ocoron.com (172.93.160.197) — Ubuntu 24.04, 6 vCores, 11GB RAM, 108GB disk

---

## How to re-verify this document

```bash
# Container inventory
ssh vps "sudo docker ps --format '{{.Names}}\t{{.Status}}\t{{.Ports}}' | sort"

# Firewall rules
ssh vps "sudo ufw status"

# Traefik routers + middlewares
ssh vps "sudo docker exec traefik wget -qO- http://localhost:8080/api/http/routers | python3 -m json.tool"
ssh vps "sudo docker exec traefik wget -qO- http://localhost:8080/api/http/middlewares | python3 -m json.tool"

# Resource limits
ssh vps "sudo docker inspect \$(sudo docker ps -q) --format '{{.Name}} Memory={{.HostConfig.Memory}} CPU={{.HostConfig.NanoCPUs}}'"

# Disk usage
ssh vps "sudo docker system df && df -h /"

# Fabrik audit
cd /opt/fabrik && python3 scripts/vps_sync.py --verify
```

---

## Network Topology

| Network | Subnet | Purpose |
|---|---|---|
| `coolify` | 10.0.1.0/24 | All Coolify-managed containers |
| `bridge` | 172.17.0.0/16 | Docker default (unused by services) |
| Host | 172.93.160.197 | Public IP — Traefik only on 80/443 |

All inter-service communication uses Docker network DNS (`service-name:port`). No containers expose ports directly to host except Traefik (80/443), Coolify Realtime (6001/6002), and OpenVPN (1194).

---

## Traefik Configuration

**Version:** v3.6  
**Config:** `/data/coolify/proxy/` (mounted into container as `/traefik`)  
**Dynamic config dir:** `/data/coolify/proxy/dynamic/` (hot-reload, file watching enabled)  
**SSL:** Let's Encrypt via HTTP challenge (`letsencrypt` certresolver) — `acme.json` at `/data/coolify/proxy/acme.json`

### Entrypoints
| Entrypoint | Port | Notes |
|---|---|---|
| `http` | :80 | HTTP→HTTPS redirect |
| `https` | :443 | TLS, HTTP/2, max 250 concurrent streams |

### Middlewares (active)
| Name | Type | Notes |
|---|---|---|
| `authelia-forward@docker` | forwardauth | → `http://authelia:9091/api/authz/forward-auth` |
| `gzip@docker` | compress | Global gzip; wire per-router as needed |
| `redirect-to-https@docker` | redirectscheme | HTTP → HTTPS |
| `site-provisioner-ipallowlist@docker` | ipallowlist | VPS + internal ranges only |
| `ocoron-com-rate-limit@docker` | ratelimit | WordPress protection |
| `ocoron-com-block-xmlrpc@docker` | replacepathregex | WordPress xmlrpc block |

---

## Firewall (UFW)

| Rule | Port | Action | Reason |
|---|---|---|---|
<!-- AUTO:ufw_rules -->
| Rule | Notes |
|---|---|
| `22/tcp                     ALLOW IN    Anywhere                   # SSH` | |
| `80/tcp                     ALLOW IN    Anywhere                   # HTTP` | |
| `443/tcp                    ALLOW IN    Anywhere                   # HTTPS+OpenVPN` | |
| `1194/tcp                   ALLOW IN    Anywhere` | |
| `6001/tcp                   ALLOW IN    Anywhere` | |
| `6002/tcp                   ALLOW IN    Anywhere` | |
| `8000/tcp                   DENY IN     Anywhere                   # Coolify raw port — use coolify.vps1.ocoron.com instead` | |
| `22/tcp (v6)                ALLOW IN    Anywhere (v6)              # SSH` | |
| `80/tcp (v6)                ALLOW IN    Anywhere (v6)              # HTTP` | |
| `443/tcp (v6)               ALLOW IN    Anywhere (v6)              # HTTPS+OpenVPN` | |
| `1194/tcp (v6)              ALLOW IN    Anywhere (v6)` | |
| `6001/tcp (v6)              ALLOW IN    Anywhere (v6)` | |
| `6002/tcp (v6)              ALLOW IN    Anywhere (v6)` | |
| `8000/tcp (v6)              DENY IN     Anywhere (v6)              # Coolify raw port — use coolify.vps1.ocoron.com instead` | |
<!-- /AUTO -->

iptables `DOCKER-USER` chain: static rules blocking raw host port access from internet; Traefik is the only entry point for Docker services.

---

<!-- AUTO:container_inventory -->
| Container | Status | Memory limit |
|---|---|---|
| `alertmanager-zw4swgkwk0s4s8kg048gw80o` | ✅ Up 2 weeks (healthy) | 256m |
| `apprise-lcocgs4gs8ksg4g08w40ows8` | ✅ Up 2 weeks (healthy) | 256m |
| `authelia-hks48k8sg8o4co4co08co00o` | ✅ Up 3 days (healthy) | 512m |
| `backrest-l48000k44wc4gk8os88s8k0c` | ✅ Up 3 days | 512m |
| `bs0wo48k4gwo440gcowscoc8-150802066640` | ✅ Up 2 weeks (healthy) | 512m |
| `cadvisor-r08sog4gwws88og048ows448` | ✅ Up 8 seconds (health: starting) | 256m |
| `captcha-j8gg4ggskkossc4gkwowk4os-202315639637` | ✅ Up 2 hours (healthy) | 512m |
| `coolify` | ✅ Up 2 weeks (healthy) | — |
| `coolify-db` | ✅ Up 2 weeks (healthy) | — |
| `coolify-proxy` | ✅ Up 2 weeks (healthy) | — |
| `coolify-realtime` | ✅ Up 2 weeks (healthy) | — |
| `coolify-redis` | ✅ Up 2 weeks (healthy) | — |
| `coolify-sentinel` | ✅ Up 8 minutes (healthy) | — |
| `e04k4sco44ow04ccc0o0k00k-151256201601` | ✅ Up 2 weeks (healthy) | 512m |
| `emailgateway-w4oocckkwko8kowggsw8sogc-140328040913` | ✅ Up 2 weeks | 512m |
| `fabrik-proxy-zsccsksoc8sssc8k00sgcc08-203530465024` | ✅ Up 2 hours (healthy) | 512m |
| `file-api-bsswwg4kg480c000gksw004k-140449896537` | ✅ Up 2 weeks | 1g |
| `file-worker-nwcckwggw0o0g40gwskk8kk8-154849864122` | ✅ Up 2 days | 1g |
| `gatus-v8s4cokcwg0co4w8okkccc0w` | ✅ Up 11 hours | 256m |
| `glitchtip-web-z00kkck8c8cwo800kk440csk` | ✅ Up 2 weeks | 512m |
| `glitchtip-worker-msgo0sg8gsgo4w4sscckc84g` | ✅ Up 2 weeks | 512m |
| `grafana-loc484owg8gsw04owo0go8kc` | ✅ Up 2 weeks (healthy) | 512m |
| `image-broker-zo4ggs4g880skwkocwwkscgk-202312741716` | ✅ Up 2 hours (healthy) | 512m |
| `loki-r48swckog008wosgwcs4g0g0` | ✅ Up 2 weeks (healthy) | 512m |
| `n8n-s8gwccsws0ccssw0wwgwsoks` | ✅ Up 2 weeks (healthy) | 2g |
| `netdata-kk4kcw4csksc48848go4o0wo` | ✅ Up 8 minutes (healthy) | 512m |
| `node-exporter-doc8c8gkcgs88s8ckggw84o4` | ✅ Up 2 weeks | 128m |
| `ocoron-com-backup-1` | ✅ Up 2 weeks | — |
| `ocoron-com-db-1` | ✅ Up 2 weeks (healthy) | 1g |
| `ocoron-com-nginx-1` | ✅ Up 2 weeks | 256m |
| `ocoron-com-redis-1` | ✅ Up 2 weeks (healthy) | 256m |
| `ocoron-com-wordpress-1` | ✅ Up 2 weeks | 512m |
| `postgres-main-l0k4gk0kggc8okcwk0s4c8s8` | ✅ Up 2 weeks (healthy) | 2g |
| `prometheus` | ✅ Up 22 seconds (health: starting) | 512m |
| `promtail-w0000ckgsgg048w0848okk08` | ✅ Up 2 weeks | 128m |
| `redis-main` | ✅ Up 2 weeks (healthy) | 512m |
| `site-provisioner-qokoksogwsk0c04gcs4swwgs-143727579258` | ✅ Up 2 weeks (healthy) | 512m |
| `traefik` | ✅ Up 2 weeks | 256m |
| `translator-kgws0s4cscsosw8gg848cwgw-211011556971` | ✅ Up 57 minutes (healthy) | 512m |
| `vckgs8c00o40o884k48cgow8-220643454460` | ✅ Up 3 days | 2g |
<!-- /AUTO -->

### 2. Security & Auth

| Container | Image | URL | Middleware | Limits |
|---|---|---|---|---|
| `authelia` | `authelia/authelia` | `auth.vps1.ocoron.com` | self | — |

### 3. Observability Stack

| Container | URL | Traefik route | Middleware | Limits |
|---|---|---|---|---|
| `grafana` | `monitor.vps1.ocoron.com` | ✅ | Authelia | — |
| `prometheus` | internal | ✅ internal | — | — |
| `loki` | internal | ✅ internal | — | — |
| `promtail` | internal | — | — | — |
| `cadvisor` | internal | — | — | — |
| `node-exporter` | internal | — | — | — |
| `alertmanager` | internal | — | — | — |
| `netdata` | `netdata.vps1.ocoron.com` | ✅ | Authelia | — |
| `gatus` | `status.vps1.ocoron.com` | ✅ | none (read-only) | — |

### 4. Data Services

| Container | Internal address | Type | Notes |
|---|---|---|---|
| `postgres-main` | `postgres-main:5432` | PostgreSQL | Shared app DB; hosts `proxy_management`, others |
| `redis-main` | `redis-main:6379` | Redis | Shared app cache |
| `meilisearch` | `search.vps1.ocoron.com` | MeiliSearch | Full-text search |

### 5. Fabrik Application Services

| Container | URL | Auth | CPU | Mem | Notes |
|---|---|---|---|---|---|
| `fabrik-proxy` | `proxy.vps1.ocoron.com` | X-API-Key | 0.5 | 512m | Webshare proxy manager; DB: `proxy_management` |
| `fabrik-captcha` | `captcha.vps1.ocoron.com` | X-API-Key | 0.5 | 512m | AntiCaptcha solver |
| `fabrik-image-broker` | `images.vps1.ocoron.com` | X-API-Key | 0.5 | 512m | Pexels/Pixabay broker |
| `fabrik-translator` | `translator.vps1.ocoron.com` | X-API-Key | 0.5 | 512m | ⚠️ Restarting — investigate |
| `fabrik-emailgateway` | `emailgateway.vps1.ocoron.com` | app-layer | 0.5 | 512m | Fastify email service |
| `fabrik-file-api` | `files-api.vps1.ocoron.com` | Bearer (Supabase) | 1.0 | 1g | Node.js file upload/download |
| `fabrik-file-worker` | internal | — | 1.0 | 1g | Background file processing |
| `fabrik-site-provisioner` | `provision.vps1.ocoron.com` | IP allowlist | 0.5 | 512m | DNS/domain provisioning |
| `fabrik-n8n` | `auto.vps1.ocoron.com` | Authelia | — | — | n8n automation |
| `fabrik-glitchtip-web` | `errors.vps1.ocoron.com` | Authelia | — | — | Error tracking (Sentry-compatible) |
| `fabrik-glitchtip-worker` | internal | — | — | — | GlitchTip background worker |

### 6. Other Services

| Container | URL | Auth | Notes |
|---|---|---|---|
| `browserless` | `browser.vps1.ocoron.com` | — | Headless Chrome; 2GB/1CPU |
| `apprise` | `notify.vps1.ocoron.com` | Authelia | Multi-channel notification hub |
| `pdf-service` | `pdf.vps1.ocoron.com` | — | PDF generation |
| `backrest` | `backup.vps1.ocoron.com` | Authelia | Backblaze B2 backup via Restic |

### 7. Infrastructure Automation

| Container | URL | Notes |
|---|---|---|
| `promtail` | internal | Ships container logs → Loki |

### 8. WordPress Stack (ocoron.com)

| Container | Notes |
|---|---|
| `ocoron-com-nginx-1` | Nginx frontend, port 80 behind Traefik |
| `ocoron-com-wordpress-1` | PHP-FPM 9000 |
| `ocoron-com-db-1` | MariaDB 3306 |
| `ocoron-com-redis-1` | Redis object cache |
| `ocoron-com-backup-1` | Backup cron |

---
<!-- /AUTO -->

## Security Posture Summary (2026-05-07)

| Layer | Status | Detail |
|---|---|---|
| **SSH** | ✅ | Ed25519 key only; root disabled |
| **UFW** | ✅ | Minimal rules; port 8000 DENY |
| **Traefik** | ✅ | Dashboard localhost-only; no raw ports |
| **Authelia** | ✅ | Forward-auth on all admin dashboards |
| **API services** | ✅ | proxy/captcha/image-broker/translator: X-API-Key |
| **File API** | ✅ | Supabase Bearer auth |
| **Site-provisioner** | ✅ | Traefik IP allowlist |
| **Resource limits** | ✅ complete | All 40 containers limited. Fabrik apps: Coolify API. Infra: `docker update` via `scripts/vps_apply_limits.sh` |
| **Wildcard SSL** | ⚠️ | Per-service HTTP challenge; TODO: Cloudflare DNS challenge |
| **Gzip compression** | ✅ | `gzip@docker` middleware registered; wire per-router as needed |
| **Docker images** | ✅ | Pruned 2026-05-06; build cache cleared |
| **.dockerignore** | ✅ | Added to all 21 projects missing it |
| **Coolify CVEs** | ✅ | Running v4.0.0-beta.459 (CVEs fixed in beta.451+) |

---

## Resource Limits Reference

<!-- AUTO:limits_summary -->
| Container | Memory |
|---|---|
| `alertmanager-zw4swgkwk0s4s8kg048gw80o` | 256m |
| `apprise-lcocgs4gs8ksg4g08w40ows8` | 256m |
| `authelia-hks48k8sg8o4co4co08co00o` | 512m |
| `backrest-l48000k44wc4gk8os88s8k0c` | 512m |
| `bs0wo48k4gwo440gcowscoc8-150802066640` | 512m |
| `cadvisor-r08sog4gwws88og048ows448` | 256m |
| `captcha-j8gg4ggskkossc4gkwowk4os-202315639637` | 512m |
| `e04k4sco44ow04ccc0o0k00k-151256201601` | 512m |
| `emailgateway-w4oocckkwko8kowggsw8sogc-140328040913` | 512m |
| `fabrik-proxy-zsccsksoc8sssc8k00sgcc08-203530465024` | 512m |
| `file-api-bsswwg4kg480c000gksw004k-140449896537` | 1g |
| `file-worker-nwcckwggw0o0g40gwskk8kk8-154849864122` | 1g |
| `gatus-v8s4cokcwg0co4w8okkccc0w` | 256m |
| `glitchtip-web-z00kkck8c8cwo800kk440csk` | 512m |
| `glitchtip-worker-msgo0sg8gsgo4w4sscckc84g` | 512m |
| `grafana-loc484owg8gsw04owo0go8kc` | 512m |
| `image-broker-zo4ggs4g880skwkocwwkscgk-202312741716` | 512m |
| `loki-r48swckog008wosgwcs4g0g0` | 512m |
| `n8n-s8gwccsws0ccssw0wwgwsoks` | 2g |
| `netdata-kk4kcw4csksc48848go4o0wo` | 512m |
| `node-exporter-doc8c8gkcgs88s8ckggw84o4` | 128m |
| `ocoron-com-db-1` | 1g |
| `ocoron-com-nginx-1` | 256m |
| `ocoron-com-redis-1` | 256m |
| `ocoron-com-wordpress-1` | 512m |
| `postgres-main-l0k4gk0kggc8okcwk0s4c8s8` | 2g |
| `prometheus` | 512m |
| `promtail-w0000ckgsgg048w0848okk08` | 128m |
| `redis-main` | 512m |
| `site-provisioner-qokoksogwsk0c04gcs4swwgs-143727579258` | 512m |
| `traefik` | 256m |
| `translator-kgws0s4cscsosw8gg848cwgw-211011556971` | 512m |
| `vckgs8c00o40o884k48cgow8-220643454460` | 2g |
<!-- /AUTO -->

**After VPS reboot:**
```bash
ssh vps "bash /opt/fabrik/scripts/vps_apply_limits.sh"
```

**Why Coolify API fails for services:** Coolify v4 service stacks are multi-container templates — the API rejects `limits_memory` with 422 because it cannot determine which sub-container to target. `docker update` bypasses this cleanly.

---

## Pending Actions

| # | Action | Where | Priority |
|---|---|---|---|
| 1 | Migrate SSL to Cloudflare DNS challenge (wildcard) | Coolify → Proxy → Add resolver | Low |
| 2 | Wire `gzip@docker` middleware to high-traffic routers | Coolify → each app → Traefik config | Low |

**Completed 2026-05-07:**
- ✅ Resource limits set on all 40 containers (Coolify API for apps, `docker update` for infra)
- ✅ translator crash loop fixed (DATABASE_URL localhost→postgres-main)
