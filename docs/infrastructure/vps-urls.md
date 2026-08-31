# VPS Fleet — Service URLs and Endpoints

**Last Updated:** 2026-08-31 18:57 UTC
**Last probe report:** [`probe-reports/infra-probe-2026-06-07T20-20Z.yaml`](probe-reports/infra-probe-2026-06-07T20-20Z.yaml)
**Hosts:** vps1 (hub, LA, `172.93.160.197`) · vps2 (Coventry UK, `96.9.214.128`) · vps3 (Coventry UK, `104.128.190.151`)
**Mesh:** Wireguard `10.99.0.0/24` over UDP 51820 (vps1 = `.1`, vps2 = `.2`, vps3 = `.3`)
**Pattern:** Public traffic → per-host Traefik → TLS terminated per host → Authelia forward-auth on admin dashboards. HTTP auto-redirects to HTTPS. No service binds a public port directly; Traefik fronts everything except SSH and Wireguard.

> **Read this first:** [`vps-complete-inventory.md`](vps-complete-inventory.md) is the source-of-truth for *what runs where*. This file is the source-of-truth for *how to reach it*.

---

## Public DNS

All `A` records via Cloudflare (zone `ocoron.com`, unproxied — orange-cloud OFF — so TLS terminates at our Traefik with Let's Encrypt, not Cloudflare's edge).

### vps1 — `*.vps1.ocoron.com` → `172.93.160.197`

CF zone `ocoron.com` has **18 A records** total (live, verified 2026-06-17 — the 2 `vps4` orphans were deleted). For vps1 (alphabetical), all → `172.93.160.197`:

`auth`, `auto`, `backup`, `browser`, `errors`, `monitor`, `notify`, `pdf`, **`provision`** (created 2026-05-31 evening — was missing despite the Traefik router existing), `search`, `status`, `vps1` (apex), **`watchdog-test`** (live Traefik router — the T-P5 watchdog dogfood)

Plus zone apex: `ocoron.com`, `www.ocoron.com` (WordPress tenant; `www` is a CNAME → apex).

**13 vps1 records route to a live Traefik router** (the 12 below + `watchdog-test.vps1`).

**ORPHAN residue — RESOLVED 2026-06-17 (re-verified 2026-07-12):** `*.vps4.ocoron.com` and `vps4.ocoron.com` (leftover DR-drill residue → `45.77.68.63`, no live vps4 droplet) **have been deleted** — both now resolve NXDOMAIN. Consistent with the header and the 18-A-record count above.

### vps2 — `*.vps2.ocoron.com` → `96.9.214.128` (NEW today)

- `vps2.ocoron.com` (apex `A`)
- `*.vps2.ocoron.com` (wildcard `A`) — covers `auth.vps2`, any future `<tenant>.vps2`
- No tenants deployed yet. First tenant deploy will trigger Let's Encrypt issuance.

### vps3 — `*.vps3.ocoron.com` → `104.128.190.151` (NEW today)

- `vps3.ocoron.com` (apex `A`)
- `*.vps3.ocoron.com` (wildcard `A`)
- Same as vps2: no tenants, first deploy issues a cert.

### How to verify DNS without waiting for cache

```bash
NS=$(dig +short NS ocoron.com | head -1)
for h in vps2.ocoron.com test.vps2.ocoron.com vps3.ocoron.com test.vps3.ocoron.com; do
  echo "$h -> $(dig +short @"$NS" "$h")"
done
```

---

## vps1 service URLs (verified against live Traefik routers, 2026-05-31 afternoon)

Snapshot taken from `docker exec traefik wget -qO- http://localhost:8080/api/http/routers`. Only routers that actually exist are listed. Where a `vps1.ocoron.com` subdomain has DNS but no router, it's called out in the "Stale DNS" section below.

| Purpose | URL | Auth | Backend container |
| :--- | :--- | :--- | :--- |
| WordPress tenant | `https://ocoron.com`, `https://www.ocoron.com` | none (public) | `ocoron-com-nginx-1` |
| Gatus public status page | `https://status.vps1.ocoron.com` | none | `gatus` |
| Authelia portal | `https://auth.vps1.ocoron.com` | (this IS Authelia) | `authelia` |
| Grafana | `https://monitor.vps1.ocoron.com` | Authelia 2FA (`^/api/` bypassed) | `grafana` |
| GlitchTip UI | `https://errors.vps1.ocoron.com` | none (router bypasses Authelia today — rule #6) | `glitchtip-web` |
| Backrest UI | `https://backup.vps1.ocoron.com` | Authelia 2FA | `backrest` |
| n8n workflow editor | `https://auto.vps1.ocoron.com` | Authelia 2FA | `n8n` |
| Apprise notify | `https://notify.vps1.ocoron.com` | Authelia 2FA | `apprise` |
| Gotenberg (PDF) | `https://pdf.vps1.ocoron.com` | bypass | `gotenberg` |
| Browserless (headless Chrome) | `https://browser.vps1.ocoron.com` | bypass | `browserless` |
| Meilisearch | `https://search.vps1.ocoron.com` | bypass (master key validation at app layer) | `meilisearch` |
| **site-provisioner** (DNS / domain registrar API) | `https://provision.vps1.ocoron.com` | Bearer `API_KEY` + Traefik IP allowlist | `site-provisioner` |
| **watchdog-test** (T-P5 watchdog dogfood) | `https://watchdog-test.vps1.ocoron.com` | (per router) | live Traefik router |

> **Reality vs. older docs:** Earlier versions of this file listed `https://captcha.vps1...`, `https://images.vps1...`, `https://translator.vps1...`, `https://proxy.vps1...`, `https://emailgateway.vps1...`, `https://files-api.vps1...`, `https://netdata.vps1...` as live URLs. **None of those have a live Traefik router or a backing container today** — see [`vps-complete-inventory.md` § Microservices status](vps-complete-inventory.md).

**Note on site-provisioner:** the container is healthy (alembic migrations applied, `/health` returns 200, CF + Postgres connectivity verified), but it's an **interim manual stand-up** as of 2026-05-31 afternoon — the `fabrik apply` redeploy pipeline isn't ready yet. The Traefik IP allowlist is the front-line gate; the `API_KEY` bearer is checked at the app layer. See [`vps-complete-inventory.md` § site-provisioner status](vps-complete-inventory.md) before redeploying.

### Stale vps1 DNS records — CLEARED 2026-05-31 evening

The 6 stale subdomains (`coolify`, `control`, `dns`, `fabrik-e2e-timing`, `images`, `netdata`) were deleted via Cloudflare API. The vps1 zone is now exactly the set of records backed by a live Traefik router.

If a future audit surfaces new orphans, the one-liner to find them:

```bash
# DNS records vs live Traefik routers
CF_TOKEN=$(grep '^CLOUDFLARE_API_TOKEN=' /opt/fabrik/.env | cut -d= -f2-)
diff <(curl -s -H "Authorization: Bearer $CF_TOKEN" \
       "https://api.cloudflare.com/client/v4/zones/b3494f947c71683f94b6afe1331a1ba6/dns_records?per_page=200&type=A" \
       | python3 -c 'import json,sys; [print(r["name"]) for r in json.load(sys.stdin)["result"] if "vps1" in r["name"]]' | sort) \
     <(ssh vps 'sudo docker exec traefik wget -qO- http://localhost:8080/api/http/routers 2>/dev/null' \
       | python3 -c 'import json,sys
for r in json.load(sys.stdin):
    rule=r.get("rule","")
    if "Host(" in rule and "vps1" in rule:
        print(rule.split("Host(\`")[1].split("\`")[0])' | sort -u)
```

---

## vps2 / vps3 service URLs

**None production yet, but the path is proven end-to-end (2026-06-02).** `spoke-canary` (`nginx:alpine`, `target_vps=vps2`) deployed clean, `curl https://canary.vps2.ocoron.com` returned HTTP 200, Let's Encrypt cert issued (`Issuer: Let's Encrypt YR2`, `notAfter: Aug 30 2026 GMT`) — first LE issuance on a spoke ever. Canary destroyed afterwards (cert sits in `/opt/traefik/acme.json` on vps2 until rotation). vps3 still untested but the W15 Traefik fix is in place on both spokes.

**Deploy path is wired** end-to-end as of 2026-06-02 (W-Multi M4 + W3 + W14 + W15). The pattern:

```bash
# In the spec
cat specs/services/my-service.yaml
# ...
# target_vps: vps2
# domain: my-service.vps2.ocoron.com
# ...

# Deploy via fabrik
.venv/bin/fabrik apply specs/services/my-service.yaml --yes
# or override the spec's target_vps on the CLI:
.venv/bin/fabrik apply specs/services/my-service.yaml --target-vps vps3 --yes
```

What happens under the hood:

1. CF DNS A record auto-created: `my-service.vps2.ocoron.com` → `96.9.214.128` (vps2's IP — picked from the `VPS_IPS` map in [`src/fabrik/orchestrator/__init__.py`](../../src/fabrik/orchestrator/__init__.py)).
2. SSH deployer env-swaps `FABRIK_VPS_SSH_HOST=vps2` via the `_target_vps_env(ctx)` contextmanager around three windows: `SSHDeployer.deploy()` (W-Multi M4), `SSHDeployer.inject_env()` (W14 — so glitchtip DSN / redis URL writes land on vps2), and compose rollback (W14 — reads `target_vps` from the resource record so a failed verify on a spoke tears the container down on the spoke).
3. Hub-side registrars (`postgres-main`, `redis-main`, `gatus`, `glitchtip-web`, `authelia`, `grafana`, `meilisearch`) run **outside** the swap windows and keep talking to vps1 — they live there. For a spoke target the registrar **rewrites the injected connection host to vps1's mesh IP `10.99.0.1`** (a spoke container can't resolve the `*-main` Docker-DNS names — WireGuard carries no DNS → SERVFAIL), via `_rewrite_shared_infra_host()` in [`src/fabrik/orchestrator/infrastructure.py`](../../src/fabrik/orchestrator/infrastructure.py) — a no-op on vps1, applied at all five injection sites (`DATABASE_URL`, `WATCHDOG_DB_URL_RO/RW`, `SUBAGENT_RUNS_DSN`, `SENTRY_DSN`/`GLITCHTIP_DSN`, `REDIS_URL`). The spoke app therefore receives:
   - `DATABASE_URL=postgresql://...@10.99.0.1:5432/...`
   - `REDIS_URL=redis://10.99.0.1:6379/...`
   - `SENTRY_DSN=http://<key>@10.99.0.1:8000/<project_id>`
4. The spoke's Traefik picks up the container's labels, requests a Let's Encrypt cert (first issuance on first spoke deploy), and starts serving. The `gzip@docker` middleware that the orchestrator emits on every router is now defined on both spokes via labels on the Traefik container itself (W15, 2026-06-02). vps2 verified live: HTTP 200 + Let's Encrypt YR2 cert. vps3 untested but the same fix is in place.

For cross-host admin dashboards on a spoke: `https://<service>.vpsN.ocoron.com` with Traefik's `authelia-vps1@file` middleware (defined in `/opt/traefik/dynamic/authelia.yml` on each spoke). That middleware forward-auths to `http://10.99.0.1:9091/api/verify` over the mesh — vps1's Authelia issues the cookie scoped to `*.vpsN.ocoron.com`. Cookie-domain plumbing for cross-host SSO is on the W-Multi M7 backlog item; until that lands, spoke admin dashboards work but the user re-auths per host. The Authelia rule registrar itself is FQDN-pattern-agnostic and handles `*.vps2 / *.vps3` patterns without code change (W13 verified 2026-06-02).

### Spoke parity status

Fully automated end-to-end (no manual steps) since W16 ship 2026-06-02. A new spoke gets its Traefik stack — including the W15 `labels:` block that publishes `gzip@docker` — from `step_12_install_spoke_traefik()` in `bootstrap-vps.sh`. The DNS records (apex + wildcard `*.vpsN.ocoron.com`) are created at `step_13_create_dns_records()` via a `curl POST` to `/api/cloudflare/dns/ocoron.com/subdomain` on `provision.vps1.ocoron.com`, executed from vps1 (allowlisted IP + in-VPS `API_KEY`). The call is idempotent: re-runs return `action: unchanged` from `ensure_record()`. No `--skip-dns` workaround needed.

---

## Internal service URLs (Docker DNS on `fabrik` network)

These resolve only *inside* a container on the same `fabrik` network on the same host. They bypass Traefik / TLS / Authelia entirely.

| Use | URL inside a vps1 container |
| :--- | :--- |
| PostgreSQL | `postgres-main:5432` |
| Redis | `redis-main:6379` |
| Meilisearch | `meilisearch:7700` |
| GlitchTip ingest (SDK DSN) | `http://glitchtip-web:8000/<project_id>` |
| Loki push API | `http://loki:3100/loki/api/v1/push` |
| Prometheus query | `http://prometheus:9090` |
| Authelia forward-auth target | `http://authelia:9091/api/verify` |
| Apprise notify (stateful — the fleet convention) | `http://apprise:8000/notify/alerts` |
| Apprise notify (stateless — n8n only) | `http://apprise:8000/notify` |
| Gotenberg | `http://gotenberg:3000` |
| Browserless | `http://browserless:3000` |
| n8n internal webhook | `http://n8n:5678` |

**Stable names guaranteed:** every service declares `container_name: <name>` in its compose file. No UUID suffixes anywhere (post-Coolify-removal).

---

## Mesh URLs (vps2 / vps3 reaching vps1 shared infra)

A spoke container reaches vps1's shared infra over the Wireguard mesh — bind addresses are `10.99.0.1:<port>`, only reachable from peers on the mesh (UFW + DOCKER-USER chain block these ports on the public iface).

| From a spoke container, use | Service | Verified |
| :--- | :--- | :--- |
| `postgresql+asyncpg://<user>:<pass>@10.99.0.1:5432/<db>` | postgres-main | ✓ |
| `redis://10.99.0.1:6379/<db>` | redis-main | ✓ |
| `http://10.99.0.1:8000/<project_id>` | GlitchTip ingest | ✓ |
| `http://10.99.0.1:9091/api/verify` | Authelia forward-auth (spoke Traefik uses this) | ✓ |
| `http://10.99.0.1:3100/loki/api/v1/push` | Loki ingest (spoke promtail uses this) | ✓ |
| `http://10.99.0.1:8201/wake` | aro-wake peer-protocol consult / Alertmanager webhook on vps1 (trio Phase 3+4 LIVE 2026-06-05) | ✓ |
| `http://10.99.0.1:8201/metrics` | aro-wake Prometheus exposition on vps1 (8 SLI metrics, scraped 15s) — LIVE 2026-06-06 | ✓ |
| `http://10.99.0.2:8201/wake` | aro-wake peer-protocol consult on vps2 — LIVE 2026-06-06 (real cross-host vps2→vps1 verified) | ✓ |
| `http://10.99.0.2:8201/metrics` | aro-wake Prometheus exposition on vps2 — scraped by hub Prometheus over wg0 (~270ms) | ✓ |
| `http://10.99.0.3:8201/wake` | aro-wake peer-protocol consult on vps3 — LIVE 2026-06-06 | ✓ |
| `http://10.99.0.3:8201/metrics` | aro-wake Prometheus exposition on vps3 — scraped by hub Prometheus over wg0 (~270ms) | ✓ |

aro-wake on EVERY host binds `0.0.0.0:8201`; UFW rule `from 10.99.0.0/24 to any port 8201 proto tcp` permits peer access on every host while public ingress is denied. aro-wake LIVE on all 3 hosts since 2026-06-06 — `http://10.99.0.<N>:8201/wake` is fully symmetric. **Spoke↔spoke routing also LIVE**: single `ufw route allow in on wg0 out on wg0` on vps1 enables direct vps2↔vps3 reach at ~266ms via hub-hop (vps1 acts as wg0 router, kernel forwarding was already enabled, spokes already had `AllowedIPs=10.99.0.0/24`). vps1 is NOT a public-internet egress relay for spokes (UFW default-DROP routed policy + tcpdump-verified that the routed allow is strictly wg0→wg0, never wg0→eth0).

No spoke service binds to a mesh port itself today (only monitoring agents expose `10.99.0.<N>:<port>` so vps1's Prometheus can scrape them — see below).

## Internal docker-bridge URLs (for Alertmanager / other fabrik-network containers reaching aro-wake on the host)

aro-wake binds the host's `0.0.0.0:8201`, but containers on the `fabrik` network can't reach the host via wg0 (different namespace). They reach the host via the fabrik bridge gateway:

| From a fabrik-network container, use | Service | Notes |
| :--- | :--- | :--- |
| `http://10.0.1.1:8201/wake?source=alertmanager` | aro-wake on the local host | Used by Alertmanager's `aro-wake-routed` webhook receiver. UFW rule `from 10.0.0.0/8 to any port 8201 proto tcp` covers this access path. Returns 202 in ~36ms (async); Claude processes in background. |
| `http://10.0.1.1:8201/health` | aro-wake health probe | Operator check from inside `alertmanager`: `docker exec alertmanager wget -qO- http://10.0.1.1:8201/health` |

---

## Prometheus scrape targets (17 `job_name`s configured / 16 active (`fabrik-services` null-target; `pushgateway` restored `b8071f40` 2026-07-19; repo re-verified 2026-07-20; prior live probe 2026-07-12: 20/20 targets up))

vps1's Prometheus runs **17 configured jobs**; `fabrik-services` currently has null targets (spec-driven, populated by the prometheus registrar), leaving **16 active jobs** (`pushgateway` restored 2026-07-19; prior 2026-07-12 live probe: 20/20 targets up). This includes the spoke federation (`node-spokes` / `cadvisor-spokes` / `promtail-spokes`, 2 targets each, live since `8342ef1`). The live `prometheus.yml` job set:

| Job | Target(s) | Notes |
| :--- | :--- | :--- |
| `prometheus` | `localhost:9090` | self-monitoring |
| `node` | `node-exporter:9100` | vps1 host metrics |
| `cadvisor` | `cadvisor:8080` | vps1 container metrics |
| `loki` | `loki:3100` | ingest stats |
| `alertmanager` | `alertmanager:9093` | dispatch counters |
| `gatus` | `gatus:8080` | synthetic check results |
| `grafana` | `grafana:3000` | dashboard/datasource health |
| `authelia` | `authelia:9959` | auth success/fail rates |
| `meilisearch` | `meilisearch:7700` | Bearer-token; search latency/index size |
| `postgres` | `postgres-exporter:9187` | connections, slow queries |
| `redis` | `redis-exporter:9121` | hit ratio, memory, ops/sec |
| `aro-wake` | `10.0.1.1:8201` (vps1, hub), `10.99.0.2:8201` (vps2, spoke), `10.99.0.3:8201` (vps3, spoke) | 3 targets; SLI metrics over docker-bridge (vps1) + wg0 (spokes) |
| `fabrik-services` | (null today) | spec-driven, `shape.exposes_metrics: true`; 30 s scrape; HTTPS |

The repo `configs/prometheus/prometheus.yml` (re-verified 2026-07-20) HAS `pushgateway` (`:126`, restored 2026-07-19), `node-spokes` (`:46`), `cadvisor-spokes` (`:58`) and `promtail-spokes` (`:70`) scrape jobs — 17 `job_name`s total (16 active; `fabrik-services` is a null-target placeholder). Spoke node/container/log metrics ARE federated over the mesh; there is still no `traefik` or `glitchtip` scrape job.

Every series carries a `host` label (`vps1`, `vps2`, or `vps3`). Grafana dashboards all have a `$host` template variable (regex `/^vps/`).

---

## Cloudflare API token (live, in `/opt/fabrik/.env`)

- **Env var:** `CLOUDFLARE_API_TOKEN` in `/opt/fabrik/.env`
- **Refreshed:** 2026-05-31 afternoon (synced from the working token in the local site-provisioner instance's `.env`; pre-edit backup at `backups/.env.backup.20260531-155948`)
- **Token name in Cloudflare:** `dns-manager-full-access`
- **Verify:** `curl -H "Authorization: Bearer $TOKEN" https://api.cloudflare.com/client/v4/user/tokens/verify`
- **Zones the token has access to:** `ocoron.com`, `ozgurbasak.com`, `tojlo.com`
- **Scope:** Currently broader than strictly needed. Single-operator dev environment — not rotating to a narrower token until there's a realistic attacker to defend against.

The same token is what site-provisioner uses for live DNS provisioning. Keep `/opt/fabrik/.env` and `/opt/site-provisioner/.env` in sync.

---

## GlitchTip DSN convention (when services are deployed)

DSN format that the orchestrator's glitchtip registrar would inject on a real `fabrik apply`:

```text
http://<key>@glitchtip-web:8000/<project_id>
```

- Uses the internal Docker DNS alias on the `fabrik` network — bypasses Authelia and TLS
- Primary env var: `SENTRY_DSN` (Sentry-compatible SDKs read this)
- Fallback env var: `GLITCHTIP_DSN` (read if `SENTRY_DSN` unset, for manual provisioning)
- Public dashboard (humans): `https://errors.vps1.ocoron.com` — see auth note above (router bypasses Authelia today via rule #6)
- **Cross-host:** a spoke tenant gets `http://<key>@10.99.0.1:8000/<project_id>` over the mesh — the bind is already in place, and the glitchtip registrar now performs the `glitchtip-web` → `10.99.0.1` host swap automatically for spoke targets (`_rewrite_shared_infra_host`, 2026-07-13); no app-side config change

Project IDs retained in the GlitchTip database from the Coolify-era audit. **Six of these have no live service emitting events** — they're retained for history and for the moment a service is redeployed:

| Service | GlitchTip project ID | Emitting events today? |
| :--- | :--- | :--- |
| captcha | 65 | no (service not deployed) |
| image-broker | 66 | **orphaned — spec removed 2026-06-02; safe to delete in GlitchTip UI** |
| translator | 67 | no |
| emailgateway | 68 | no |
| file-api | 69 | no |
| file-worker | 70 | no |
| site-provisioner | 24 | yes (interim — flowing) |

---

## Calling another service (M2M pattern)

```python
import os, httpx
headers = {"X-Internal-Token": os.environ["SERVICE_INTERNAL_SECRET_KEY"]}
resp = httpx.get("https://translator.vps1.ocoron.com/api/translate", headers=headers)
```

```javascript
const headers = { 'X-Internal-Token': process.env.SERVICE_INTERNAL_SECRET_KEY };
const resp = await fetch('https://translator.vps1.ocoron.com/api/translate', { headers });
```

`SERVICE_INTERNAL_SECRET_KEY` is one shared key across all M2M-protected services; lives in `/opt/fabrik/.env` and is injected into each service's `.env` by the SSH deployer.

**Status today:** no live service is consuming this — the 6 microservices that used the pattern (`captcha`, `translator`, `proxy`, `emailgateway`, `file-api`, `file-worker`) are not currently deployed. The key + scaffold-emitted `internal_auth.{py,js}` modules are intact and ready for the next deploy. (`image-broker` was the 7th in this group; its spec was removed 2026-06-02.)

---

## Port reference (per host)

### vps1 UFW

| Port | Binding | UFW | Purpose |
| :--- | :--- | :--- | :--- |
| 22/tcp | `0.0.0.0:22` | ALLOW | SSH (`ozgur` user, key-only) |
| 80/tcp | `0.0.0.0:80` | ALLOW | HTTP → Traefik (auto-redirect to HTTPS) |
| 443/tcp | `0.0.0.0:443` | ALLOW | HTTPS via Traefik |
| 1194/tcp | `0.0.0.0:1194` | ALLOW | OpenVPN — **out-of-platform-scope (operator's personal VPN)**. Documented per W5 of fleet-hardening plan; not platform infra, no probe required. |
| 8000/tcp | n/a | DENY | ⚠ stale Coolify comment — rule still useful as belt-and-suspenders |
| 8201/tcp | (mesh / bridge) | ALLOW `from 10.0.0.0/8`, ALLOW `from 10.99.0.0/24` | aro-wake — bridge gateway (Alertmanager) + wg0 peer access; public ingress denied |
| 51820/udp | `0.0.0.0:51820` | ALLOW | Wireguard mesh (hub listener) |
| 5432/tcp | `10.99.0.1:5432` | (mesh-only) | postgres-main — DOCKER-USER chain blocks on public iface |
| 6379/tcp | `10.99.0.1:6379` | (mesh-only) | redis-main |
| 8000/tcp | `10.99.0.1:8000` | (mesh-only) | glitchtip-web ingest |
| 9091/tcp | `10.99.0.1:9091` | (mesh-only) | authelia (cross-host forward-auth) |
| 3100/tcp | `10.99.0.1:3100` | (mesh-only) | loki push API |
| 8080/tcp | `127.0.0.1:8080` | localhost | Traefik API dashboard |

### vps2 / vps3 UFW (identical) — active + enforcing as of 2026-05-31 evening (W1 shipped)

| Port | Binding | UFW | Purpose |
| :--- | :--- | :--- | :--- |
| 22/tcp | `0.0.0.0:22` | ALLOW | SSH |
| 80/tcp | `0.0.0.0:80` | ALLOW | HTTP → Traefik |
| 443/tcp | `0.0.0.0:443` | ALLOW | HTTPS via Traefik |
| 51820/udp | `0.0.0.0:51820` | ALLOW | Wireguard mesh (spoke listener) |
| 9100/tcp | `10.99.0.<N>:9100` | (mesh-only) | node-exporter — scraped by vps1's Prometheus |
| 8080/tcp | `10.99.0.<N>:8080` | (mesh-only) | cadvisor |
| 9080/tcp | `10.99.0.<N>:9080` | (mesh-only) | promtail |

DOCKER-USER iptables chain on every host blocks the mesh-only port list (`5432,6379,9090,9091,9100,8080,3100,7700,8000`) on the public interface.

---

## SSH aliases (dev WSL `~/.ssh/config`)

```text
Host vps   →  ozgur@vps1.ocoron.com  (172.93.160.197) — LA hub
Host vps2  →  ozgur@96.9.214.128                       — Coventry UK spoke
Host vps3  →  ozgur@104.128.190.151                    — Coventry UK spoke
```

All three hosts: `ozgur` user (NOPASSWD sudo), Ed25519 key auth only, root login disabled, password auth disabled, fail2ban active. SSH posture matches across the fleet (this was the Lesson 65 takeaway from the vps2 bootstrap lockout).

---

## Maintenance command quick-reference

```bash
# Full health + residue audit (limits drift, stale Authelia rules, orphan compose dirs)
cd /opt/fabrik && python3 scripts/vps_sync.py --verify

# After VPS reboot — reapply memory limits
ssh vps "bash /opt/fabrik/scripts/vps_apply_limits.sh"

# Deploy a new service via fabrik (defaults to vps1 hub)
cd /opt/fabrik && .venv/bin/fabrik apply specs/services/<name>.yaml

# Deploy to a spoke (W-Multi M4 — 2026-05-31 evening)
cd /opt/fabrik && .venv/bin/fabrik apply specs/services/<name>.yaml --target-vps vps2

# Redeploy a git-source service
#   1. push to GitHub first — VPS pulls from the remote, not your local
#   2. then redeploy
cd /opt/<service> && git push
cd /opt/fabrik && .venv/bin/fabrik redeploy <name>

# Restart Authelia after config edit (NEVER SIGHUP — Authelia exits on SIGHUP)
ssh vps "sudo docker restart authelia"

# Reload Prometheus after editing prometheus.yml
ssh vps "sudo docker kill -s HUP prometheus"

# Verify Cloudflare token is active
CF=$(grep '^CLOUDFLARE_API_TOKEN=' /opt/fabrik/.env | cut -d= -f2-)
curl -s -H "Authorization: Bearer $CF" https://api.cloudflare.com/client/v4/user/tokens/verify

# Weekly disk cleanup on a host
ssh vps "sudo docker image prune -f && sudo docker builder prune -f"
```

---

## Cross-references

- Container-level inventory: [`vps-complete-inventory.md`](vps-complete-inventory.md)
- Per-host runtime state and recent maintenance: [`vps-status.md`](vps-status.md)
- Deployment mechanics: `docs/operations/deployment.md`
- Disaster recovery: `docs/operations/disaster-recovery.md`
- AI sysadmin reference: [`vps-ai-sysadmin.md`](vps-ai-sysadmin.md)
- Bootstrap a new spoke: [`vps-bootstrap-plan.md`](vps-bootstrap-plan.md) + `scripts/bootstrap/README.md`
- Residue policy: [`vps-residue-policy.md`](vps-residue-policy.md)
