# VPS Status

**Last Updated:** 2026-05-06 22:06 UTC
**Host:** vps1.ocoron.com (172.93.160.197)
**Location:** Los Angeles, CA, USA (Psychz Networks AS32421)
**SSH:** `ssh vps` (ozgur user, key-only Ed25519 auth)
**Uptime:** 48 days

---

## System Overview

| Component | Value |
|---|---|
<!-- AUTO:system_overview -->
| **Containers running** | 40 |
| **Disk** | 108G total, 38G used, 70G free (36%) |
| **Memory** | 11Gi total, 3.8Gi used, 3.9Gi free |
| **Uptime** | up 6 weeks, 6 days, 23 hours, 46 minutes |
| **Last snapshot** | 2026-05-06 22:06 UTC |
<!-- /AUTO -->

| **OS** | Ubuntu 24.04 LTS |
| **CPU** | 6 vCores |
| **Memory** | 11GB total, ~4.5GB available, 2GB swap (1.7GB used) |
| **Disk** | 108GB total, 38GB used, 70GB free (35%) |
| **Docker Images** | 14.2GB (all active — no reclaimable after 2026-05-06 prune) |
| **Docker Volumes** | 3.6GB |
| **Build Cache** | 0B (cleared 2026-05-06) |
| **Load Average** | 1.89 / 2.96 / 3.36 (5m/10m/15m) |

### Storage Notes
- No local backup retention — all backups go to Backblaze B2 via Backrest
- Monitor `/var/lib/docker` growth; run `docker image prune -af` monthly
- PostgreSQL data at `/data/coolify/databases/`
- Alert threshold: 70% disk usage

---

## Security Status

| Component | Status | Notes |
|---|---|---|
| **SSH** | ✅ | Root disabled, password auth disabled, Ed25519 key only |
| **UFW** | ✅ | Active — see Firewall section below |
| **Port 8000 (Coolify raw)** | ✅ BLOCKED | DENY rule added 2026-05-06; use `coolify.vps1.ocoron.com` |
| **Traefik dashboard** | ✅ | Bound to `127.0.0.1:8080` only |
| **Coolify UI** | ✅ | Behind Traefik + Authelia on `coolify.vps1.ocoron.com` |
| **OpenVPN** | ✅ | Port 1194/tcp, kernel service |
| **Authelia SSO** | ✅ | Forward-auth on all admin dashboards |
| **Service API keys** | ✅ | proxy, captcha, image-broker, translator all require `X-API-Key` |
| **Site-provisioner** | ✅ | IP allowlist middleware (VPS IP + internal Docker ranges only) |

### Firewall (UFW) — current rules

| Port | Action | Protocol | Purpose |
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

---

## Container Status (40 running — 2026-05-07)

<!-- AUTO:container_status -->
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
## Known Issues (2026-05-07)

| # | Service | Issue | Action |
|---|---|---|---|
| 2 | Swap | 1.7GB / 2GB used | Memory pressure; monitor closely |
| 3 | Resource limits after reboot | `docker update` limits reset on VPS reboot | Run: `ssh vps "bash /opt/fabrik/scripts/vps_apply_limits.sh"` |
| 4 | Wildcard SSL | Per-service Let's Encrypt HTTP challenge | Migrate to Cloudflare DNS challenge in Coolify for wildcard |

---

## Traefik Middleware Registry

| Middleware | Type | Used by |
|---|---|---|
<!-- AUTO:traefik_middlewares -->
| Name | Type |
|---|---|
| `authelia-forward@docker` | forwardauth |
| `dashboard_redirect@internal` | redirectregex |
| `dashboard_stripprefix@internal` | stripprefix |
| `gzip@docker` | compress |
| `ocoron-com-block-xmlrpc@docker` | replacepathregex |
| `ocoron-com-rate-limit@docker` | ratelimit |
| `ocoron-com-www-redirect@docker` | redirectregex |
| `redirect-to-https@docker` | redirectscheme |
| `redirect-web-to-websecure@internal` | redirectscheme |
| `site-provisioner-ipallowlist@docker` | ipallowlist |
<!-- /AUTO -->

---

## Resource Limits (complete — 2026-05-07)

Two mechanisms — Coolify API for applications (survives redeploys), `docker update` for services (resets on reboot).

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
⚠️ **After VPS reboot, run:** `ssh vps "bash /opt/fabrik/scripts/vps_apply_limits.sh"`

---

## Maintenance Procedures

```bash
# Weekly cleanup (cron or manual)
ssh vps "sudo docker image prune -f && sudo docker builder prune -f"

# Check all service health
cd /opt/fabrik && python3 scripts/vps_sync.py --verify

# Full status
ssh vps "sudo docker ps --format '{{.Names}}\t{{.Status}}' | sort"

# Restart a specific service
cd /opt/fabrik && fabrik redeploy <service-name>

# After VPS reboot — reapply infra memory limits
ssh vps "bash /opt/fabrik/scripts/vps_apply_limits.sh"

# Check translator crash
ssh vps "sudo docker logs \$(sudo docker ps -a --filter name=translator --format '{{.Names}}' | head -1) --tail 50"
```
