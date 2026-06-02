# Migration Plan: Coolify → Standalone Docker Compose + SSH Deploy

**Created:** 2026-05-27 | **Final revision:** 2026-05-27 (audit: 150+ VPS tool calls)
**Status:** PLANNING — do not execute until each phase is signed off
**Executor:** Read every line before starting. This is a runbook, not a summary.

---

## Part 1 — Ground Truth (all facts verified 2026-05-27)

### Running Container → Managed-By Map

| Container name | Status | Managed by | Post-migration home |
|---|---|---|---|
| `traefik` | ✅ standalone | `/opt/traefik/compose.yaml` | no change |
| `redis-main` | ✅ standalone | `/opt/redis/compose.yaml` | no change |
| `prometheus` | ✅ standalone | `/opt/monitoring/compose.yaml` (project=`monitoring`) | no change |
| `postgres-exporter` | ✅ standalone | `/opt/monitoring/compose.yaml` | no change |
| `redis-exporter` | ✅ standalone | `/opt/monitoring/compose.yaml` | no change |
| `pushgateway` | ✅ standalone | `/opt/monitoring/compose.yaml` | no change |
| `ocoron-com-*` (5) | ✅ standalone | `/opt/ocoron-com/compose.yaml` | no change |
| `authelia-hks48k8sg8o4co4co08co00o` | ❌ Coolify svc | UUID `hks48k8sg8o4co4co08co00o` | `/opt/authelia/compose.yaml` (update to bind mount) |
| `postgres-main-l0k4gk0kggc8okcwk0s4c8s8` | ❌ Coolify svc | UUID `l0k4gk0kggc8okcwk0s4c8s8` | `/opt/postgres/compose.yaml` |
| `loki-r48swckog008wosgwcs4g0g0` | ❌ Coolify svc | UUID `r48swckog008wosgwcs4g0g0` | `/opt/monitoring/compose.yaml` (extend) |
| `promtail-w0000ckgsgg048w0848okk08` | ❌ Coolify svc | UUID `w0000ckgsgg048w0848okk08` | `/opt/monitoring/compose.yaml` (extend) |
| `alertmanager-zw4swgkwk0s4s8kg048gw80o` | ❌ Coolify svc | UUID `zw4swgkwk0s4s8kg048gw80o` | `/opt/monitoring/compose.yaml` (extend) |
| `node-exporter-doc8c8gkcgs88s8ckggw84o4` | ❌ Coolify svc | UUID `doc8c8gkcgs88s8ckggw84o4` | `/opt/monitoring/compose.yaml` (extend) |
| `cadvisor-r08sog4gwws88og048ows448` | ❌ Coolify svc | UUID `r08sog4gwws88og048ows448` | `/opt/monitoring/compose.yaml` (extend) |
| `grafana-loc484owg8gsw04owo0go8kc` | ❌ Coolify svc | UUID `loc484owg8gsw04owo0go8kc` | `/opt/monitoring/compose.yaml` (extend) |
| `netdata-kk4kcw4csksc48848go4o0wo` | ❌ Coolify svc | UUID `kk4kcw4csksc48848go4o0wo` | `/opt/monitoring/compose.yaml` (extend) |
| `gatus-v8s4cokcwg0co4w8okkccc0w` | ❌ Coolify svc | UUID `v8s4cokcwg0co4w8okkccc0w` | `/opt/gatus/compose.yaml` |
| `n8n-s8gwccsws0ccssw0wwgwsoks` | ❌ Coolify svc | UUID `s8gwccsws0ccssw0wwgwsoks` | `/opt/n8n/compose.yaml` |
| `apprise-lcocgs4gs8ksg4g08w40ows8` | ❌ Coolify svc | UUID `lcocgs4gs8ksg4g08w40ows8` | `/opt/apprise/compose.yaml` |
| `glitchtip-web-z00kkck8c8cwo800kk440csk` | ❌ Coolify svc | UUID `z00kkck8c8cwo800kk440csk` | `/opt/glitchtip/compose.yaml` |
| `glitchtip-worker-msgo0sg8gsgo4w4sscckc84g` | ❌ Coolify svc | UUID `msgo0sg8gsgo4w4sscckc84g` | `/opt/glitchtip/compose.yaml` |
| `backrest-l48000k44wc4gk8os88s8k0c` | ❌ Coolify svc | UUID `l48000k44wc4gk8os88s8k0c` | `/opt/backrest/compose.yaml` |
| `bs0wo48k4gwo440gcowscoc8-*` (meilisearch) | ❌ Coolify app | UUID `bs0wo48k4gwo440gcowscoc8` | `/opt/meilisearch/compose.yaml` |
| `e04k4sco44ow04ccc0o0k00k-*` (gotenberg) | ❌ Coolify app | UUID `e04k4sco44ow04ccc0o0k00k` | `/opt/gotenberg/compose.yaml` |
| `vckgs8c00o40o884k48cgow8-*` (browserless) | ❌ Coolify app | UUID `vckgs8c00o40o884k48cgow8` | `/opt/browserless/compose.yaml` |
| `site-provisioner-qokoksogwsk0c04gcs4swwgs-*` | ❌ Coolify app | UUID `qokoksogwsk0c04gcs4swwgs` | `/opt/site-provisioner/` via `fabrik apply` |
| `image-broker-zo4ggs4g880skwkocwwkscgk-*` | ❌ Coolify app | UUID `zo4ggs4g880skwkocwwkscgk` | `/opt/image-broker/` via `fabrik apply` |
| `coolify` + 4 | ✴️ control plane | — | remove in Phase 10 |

**Not running (Coolify DB only, no containers):** fabrik-captcha, fabrik-emailgateway, fabrik-file-api, fabrik-file-worker, fabrik-proxy, fabrik-translator. Compose files exist only in Coolify's postgres `docker_compose_raw` column.

### CRITICAL: Coolify Service Compose Files NOT on Disk

`/data/coolify/services/<uuid>/` directories exist but are empty. All service compose definitions are stored only in the Coolify postgres database in the `docker_compose_raw` column. **Must extract from DB before removing Coolify.**

```bash
ssh vps "sudo docker exec coolify-db psql -U coolify -d coolify -c \
  \"SELECT uuid, name, docker_compose_raw FROM services ORDER BY name;\" \
  > /tmp/coolify-services-dump.txt"
```

### CRITICAL: Monitoring Compose Already Running — Extend, Don't Replace

`/opt/monitoring/compose.yaml` is a live production file. It currently manages:
`prometheus`, `postgres-exporter`, `redis-exporter`, `pushgateway` (all running, all healthy).

It already contains the full service definitions for `loki`, `promtail`, `alertmanager`, `node-exporter`, `cadvisor`, `grafana` — but those services are currently running as separate Coolify Services with UUID names. The file needs only two additions: `netdata` and `gatus` (gatus will get its own compose instead).

Migration strategy: stop the 7 Coolify-managed monitoring containers → `docker compose up -d` in `/opt/monitoring/` → the 4 already-running services are untouched, the 6 others start with stable names.

### CRITICAL: Meilisearch Has No Persistent Volume

Container `bs0wo48k4gwo440gcowscoc8-211159651770` has **zero mounts**. All search index data at `/meili_data` is ephemeral in the container's overlay filesystem. If the container is removed, all indexes are lost. Must copy data to a new named volume before migration.

### Volume Map — Complete (all 22 named volumes verified)

| Volume | Used by | Target after migration | Strategy |
|---|---|---|---|
| `l0k4gk0kggc8okcwk0s4c8s8_postgres-data` | postgres-main | → `monitoring_postgres-data`¹ | copy |
| `s8gwccsws0ccssw0wwgwsoks_n8n-data` | n8n | → `n8n-data` | copy |
| `hks48k8sg8o4co4co08co00o_authelia-config` | authelia | → bind mount `/opt/authelia/config` | extract to disk |
| `loc484owg8gsw04owo0go8kc_grafana-data` | grafana | → `monitoring_grafana-data` | copy |
| `lcocgs4gs8ksg4g08w40ows8_apprise-config` | apprise | → `apprise-config`² | copy |
| `r48swckog008wosgwcs4g0g0_loki-data` | loki | → `monitoring_loki-data` | fresh (ephemeral logs) |
| `zw4swgkwk0s4s8kg048gw80o_alertmanager-data` | alertmanager | → `monitoring_alertmanager-data` | fresh |
| `w0000ckgsgg048w0848okk08_promtail-positions` | promtail | → `monitoring_promtail-positions` | fresh |
| `kk4kcw4csksc48848go4o0wo_netdata-config` | netdata | → `monitoring_netdata-config` | fresh |
| `kk4kcw4csksc48848go4o0wo_netdata-lib` | netdata | → `monitoring_netdata-lib` | fresh |
| `kk4kcw4csksc48848go4o0wo_netdata-cache` | netdata | → `monitoring_netdata-cache` | fresh |
| `monitoring_prometheus-data` | prometheus | already correct | no change |
| `zo4ggs4g880skwkocwwkscgk_image-cache` | image-broker | → `image-broker_image-cache` | fresh (cache — rebuild on first use) |
| `redis_redis-data` | redis-main | already correct | no change |
| `coolify-db`, `coolify-redis` | Coolify control plane | remove with Coolify | delete after Phase 10 |
| `ocoron-com_*` (4) | WordPress | already correct | no change |
| anonymous (2) | apprise plugins/attach | auto-created | ignore |

¹ Postgres standalone compose at `/opt/postgres/` will be project name `postgres`, creating `postgres_postgres-data`. Use `external: true` with the pre-created clean name.
² Apprise standalone compose at `/opt/apprise/` uses `external: true` with the pre-created volume named `apprise-config`. image-broker cache is fresh (auto-created by fabrik apply, no copy needed).

### Authelia — Three Files in Volume, Only One Synced to Disk

`authelia-config-sync.service` watches `/opt/authelia/config/configuration.yml` and syncs it to the Docker volume. The other two files exist **only in the volume**:

- `db.sqlite3` (311 KB) — TOTP device trust, active sessions
- `users_database.yml` — user `obasak` with bcrypt hash and TOTP secret

These must be extracted from the volume to `/opt/authelia/config/` before the bind-mount switch.

### Authelia Traefik Labels (Verbatim from Running Container)

These define the `authelia-forward@docker` middleware that every admin dashboard depends on:

```
traefik.enable=true
traefik.http.routers.authelia.entryPoints=websecure
traefik.http.routers.authelia.rule=Host(`auth.vps1.ocoron.com`)
traefik.http.routers.authelia.tls=true
traefik.http.routers.authelia.tls.certresolver=letsencrypt
traefik.http.services.authelia.loadbalancer.server.port=9091
traefik.http.routers.authelia-http.entryPoints=web
traefik.http.routers.authelia-http.rule=Host(`auth.vps1.ocoron.com`)
traefik.http.routers.authelia-http.middlewares=redirect-to-https
traefik.http.middlewares.redirect-to-https.redirectscheme.scheme=https
traefik.http.middlewares.authelia-forward.forwardAuth.address=http://authelia:9091/api/authz/forward-auth
traefik.http.middlewares.authelia-forward.forwardAuth.trustForwardHeader=true
traefik.http.middlewares.authelia-forward.forwardAuth.authResponseHeaders=Remote-User,Remote-Groups,Remote-Name,Remote-Email
```

Container **must** have `container_name: authelia` — the forwardAuth URL hardcodes `http://authelia:9091`.

### N8N — SQLite, Not Postgres

n8n uses SQLite at `/home/node/.n8n/database.sqlite` (856 KB) in volume `s8gwccsws0ccssw0wwgwsoks_n8n-data`. Does NOT use postgres-main. `N8N_ENCRYPTION_KEY=4MUWbwje4W3D8ZvQos5s9M5aaKH0SR14` encrypts all stored credentials — if this value changes, all credentials become unreadable.

### Redis Index Allocations

| Index | Owner | Connection string |
|---|---|---|
| 3 | Authelia sessions | `redis-main:6379/3` |
| 4 | GlitchTip | `redis-main:6379/4` |

### Postgres-Main — Databases and Users

```
Databases: glitchtip, postgres, site_provisioner
Roles: ozgur, postgres (superuser), proxy_user, site_provisioner
postgres-exporter connects as: postgres:postgres@postgres-main — password is 'postgres'
```

### Grafana Domain

Grafana is served at `monitor.vps1.ocoron.com` (not `grafana.vps1.ocoron.com`).
Root URL in config: `https://monitor.vps1.ocoron.com`.

### Systemd Services (VPS)

| Service | Status | Action post-migration |
|---|---|---|
| `authelia-config-sync` | active/running | Update container name from UUID to `authelia`; keep service |
| `coolify-alias-watcher` | active/running | Stop + disable + remove after Phase 10 |
| `vps-sysadmin-bot` | active/running | No change — unrelated to Coolify |
| `iptables-docker-user` | active/exited | No change |

### Known Security Gaps (out of migration scope, document separately)

- `image-broker SERVICE_INTERNAL_SECRET_KEY = "your_internal_secret_key_here"` — placeholder in production
- `postgres-exporter` and `GlitchTip` connect to postgres-main as superuser `postgres:postgres`

---

## Part 2 — Secrets Inventory

Every secret must be extracted and stored in the password manager + `/opt/fabrik/docs/reference/vps-secrets.md` (gitignored) **before Phase 1 begins**. Many are marked `is_shown_once=true` in Coolify DB — they cannot be viewed through the Coolify UI again, but they are still in the database.

### Extraction Commands

```bash
# All env vars for all applications (keys only — for inventory)
ssh vps "sudo docker exec coolify-db psql -U coolify -d coolify -c \
  \"SELECT a.name, e.key, e.is_shown_once FROM environment_variables e \
    JOIN applications a ON e.application_id = a.id ORDER BY a.name, e.key;\""

# Full env vars for active applications (including values — pipe to secure local file)
ssh vps "sudo docker exec coolify-db psql -U coolify -d coolify -c \
  \"SELECT e.key, e.value FROM environment_variables e \
    WHERE e.application_id = 'qokoksogwsk0c04gcs4swwgs' ORDER BY e.key;\"" \
  > /opt/fabrik/docs/reference/vps-secrets-site-provisioner.txt

ssh vps "sudo docker exec coolify-db psql -U coolify -d coolify -c \
  \"SELECT e.key, e.value FROM environment_variables e \
    WHERE e.application_id = 'zo4ggs4g880skwkocwwkscgk' ORDER BY e.key;\"" \
  > /opt/fabrik/docs/reference/vps-secrets-image-broker.txt

# Exited apps — extract before Coolify is removed
for uuid in j8gg4ggskkossc4gkwowk4os w4oocckkwko8kowggsw8sogc bsswwg4kg480c000gksw004k \
            nwcckwggw0o0g40gwskk8kk8 zsccsksoc8sssc8k00sgcc08 kgws0s4cscsosw8gg848cwgw; do
  ssh vps "sudo docker exec coolify-db psql -U coolify -d coolify -c \
    \"SELECT a.name, e.key, e.value FROM environment_variables e \
      JOIN applications a ON e.application_id = a.id \
      WHERE a.uuid = '$uuid' ORDER BY e.key;\"" \
    >> /opt/fabrik/docs/reference/vps-secrets-exited-apps.txt
done

# Extract all service compose files (stored in DB only)
ssh vps "sudo docker exec coolify-db psql -U coolify -d coolify -t -c \
  \"SELECT 'UUID: ' || uuid || E'\nNAME: ' || name || E'\n---\n' || \
    COALESCE(docker_compose_raw, 'NULL') || E'\n\n' \
    FROM services ORDER BY name;\"" \
  > /opt/fabrik/docs/reference/coolify-services-compose-dump.txt

# Running container envs (capture secrets not in DB)
for container in \
  "$(ssh vps "sudo docker ps --format '{{.Names}}' | grep '^n8n-' | head -1")" \
  "$(ssh vps "sudo docker ps --format '{{.Names}}' | grep '^glitchtip-web-' | head -1")" \
  "$(ssh vps "sudo docker ps --format '{{.Names}}' | grep '^grafana-' | head -1")" \
  "$(ssh vps "sudo docker ps --format '{{.Names}}' | grep '^backrest-' | head -1")" \
  "$(ssh vps "sudo docker ps --format '{{.Names}}' | grep '^apprise-' | head -1")"; do
  echo "=== $container ===" >> /opt/fabrik/docs/reference/vps-secrets-running.txt
  ssh vps "sudo docker inspect $container --format '{{range .Config.Env}}{{println .}}{{end}}'" \
    >> /opt/fabrik/docs/reference/vps-secrets-running.txt
done
```

### Known-Value Secrets (confirmed in audit)

Store these in password manager NOW:

| Secret | Value (confirmed) | Owner |
|---|---|---|
| `N8N_ENCRYPTION_KEY` | `4MUWbwje4W3D8ZvQos5s9M5aaKH0SR14` | n8n |
| `MEILI_MASTER_KEY` | `n7mjRrSipeqy8nWzadLZYarxiUqO35tW` | meilisearch (also in Prometheus scrape config) |
| `BROWSERLESS_TOKEN` | `TWrqUboUGCDIm8IEck5wsqJUlJNvssPi` | browserless |
| `GOTENBERG_USER/PASS` | `gotenberg` / `aMuGTzjlZ7z9wPHeGiIbHq8noGjFSpY7` | gotenberg basic auth |
| `GLITCHTIP_SECRET_KEY` | `YWH7736oLuTID-NmAVDw90Th0CljrpDqWvp4UsrtIfndvT3KYA` | GlitchTip |
| `APPRISE_TELEGRAM` | `tgram://8751835294:AAHwhKgeCUoG2ovr9Sg-xo9fMl5Gy6kXj1I/6999645768` | apprise + alertmanager |
| `BACKREST_REPO_PASSWORD` | `22966574d505b0d670a15d3f1d9d178162801222668cdc1047567537eebbd7a2` | backrest |
| `AWS_ACCESS_KEY_ID` | `0044e7ca36a086b0000000001` | backrest (B2 key ID via S3-compat API) |
| `AWS_SECRET_ACCESS_KEY` | `K004hcjQVRBA8hLY0uZzzKEYg4crlq8` | backrest (B2 application key) |
| `AUTHELIA_JWT_SECRET` | in `/opt/authelia/config/configuration.yml` | authelia |
| `AUTHELIA_SESSION_SECRET` | in `/opt/authelia/config/configuration.yml` | authelia |
| `AUTHELIA_STORAGE_KEY` | in `/opt/authelia/config/configuration.yml` | authelia |

---

## Part 3 — Target Architecture

### Directory Layout After Migration

```
/opt/
├── traefik/          (unchanged)
├── redis/            (unchanged)
├── ocoron-com/       (unchanged)
├── monitoring/       (extended — adds loki, promtail, alertmanager, node-exporter, cadvisor, grafana, netdata)
├── gatus/            (NEW — standalone, config bind-mounted from /opt/monitoring/configs/gatus/)
├── postgres/         (NEW — standalone postgres-main)
├── authelia/         (updated — bind mount replaces Docker volume)
├── n8n/              (NEW)
├── apprise/          (NEW)
├── glitchtip/        (NEW — merges two Coolify services)
├── backrest/         (config + data already exists; just needs compose file)
├── meilisearch/      (NEW — adds persistent volume)
├── gotenberg/        (NEW)
├── browserless/      (NEW)
├── site-provisioner/ (NEW — via fabrik apply SSH deployer)
└── image-broker/     (NEW — via fabrik apply SSH deployer)
```

### Standalone Compose Specifications

#### `/opt/postgres/compose.yaml`

```yaml
services:
  postgres-main:
    image: postgres:16-alpine
    container_name: postgres-main
    restart: unless-stopped
    env_file: .env              # POSTGRES_PASSWORD, POSTGRES_USER
    volumes:
      - postgres-data:/var/lib/postgresql/data
    networks:
      - coolify
    deploy:
      resources:
        limits:
          memory: 2G
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 30s
      timeout: 5s
      retries: 3

volumes:
  postgres-data:
    external: true              # Pre-created from UUID volume copy

networks:
  coolify:
    external: true
```

`/opt/postgres/.env`:
```
POSTGRES_USER=postgres
POSTGRES_PASSWORD=<extract from running postgres-main container or Coolify service compose>
```

#### `/opt/authelia/compose.yaml` (update existing file)

```yaml
services:
  authelia:
    image: authelia/authelia:4.39.19
    container_name: authelia
    restart: unless-stopped
    volumes:
      - /opt/authelia/config:/config    # bind mount — replaces Docker volume
    environment:
      TZ: Europe/Istanbul
    networks:
      - coolify
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.authelia.entryPoints=websecure"
      - "traefik.http.routers.authelia.rule=Host(`auth.vps1.ocoron.com`)"
      - "traefik.http.routers.authelia.tls=true"
      - "traefik.http.routers.authelia.tls.certresolver=letsencrypt"
      - "traefik.http.services.authelia.loadbalancer.server.port=9091"
      - "traefik.http.routers.authelia-http.entryPoints=web"
      - "traefik.http.routers.authelia-http.rule=Host(`auth.vps1.ocoron.com`)"
      - "traefik.http.routers.authelia-http.middlewares=redirect-to-https"
      - "traefik.http.middlewares.redirect-to-https.redirectscheme.scheme=https"
      - "traefik.http.middlewares.authelia-forward.forwardAuth.address=http://authelia:9091/api/authz/forward-auth"
      - "traefik.http.middlewares.authelia-forward.forwardAuth.trustForwardHeader=true"
      - "traefik.http.middlewares.authelia-forward.forwardAuth.authResponseHeaders=Remote-User,Remote-Groups,Remote-Name,Remote-Email"
    deploy:
      resources:
        limits:
          memory: 512M

networks:
  coolify:
    external: true
```

#### `/opt/monitoring/compose.yaml` (add 4 new services — extend existing)

The file already has loki, promtail, prometheus, alertmanager, node-exporter, cadvisor, grafana, postgres-exporter, redis-exporter, pushgateway. Add these 4 blocks and update the volumes section:

**New services to append:**

```yaml
  netdata:
    image: netdata/netdata:latest
    container_name: netdata
    restart: unless-stopped
    hostname: vps1
    cap_add:
      - SYS_PTRACE
      - SYS_ADMIN
    security_opt:
      - apparmor:unconfined
    volumes:
      - netdata-config:/etc/netdata
      - netdata-lib:/var/lib/netdata
      - netdata-cache:/var/cache/netdata
      - /etc/passwd:/host/etc/passwd:ro
      - /etc/group:/host/etc/group:ro
      - /proc:/host/proc:ro
      - /sys:/host/sys:ro
      - /etc/os-release:/host/etc/os-release:ro
      - /var/run/docker.sock:/var/run/docker.sock:ro
    environment:
      NETDATA_CLAIM_TOKEN: ""
      NETDATA_CLAIM_URL: ""
    networks:
      - coolify
    labels:
      - "traefik.enable=true"
      - "traefik.docker.network=coolify"
      - "traefik.http.routers.netdata.rule=Host(`netdata.vps1.ocoron.com`)"
      - "traefik.http.routers.netdata.entrypoints=websecure"
      - "traefik.http.routers.netdata.tls=true"
      - "traefik.http.routers.netdata.tls.certresolver=letsencrypt"
      - "traefik.http.routers.netdata.middlewares=authelia-forward@docker,gzip@docker"
      - "traefik.http.services.netdata.loadbalancer.server.port=19999"
    deploy:
      resources:
        limits:
          memory: 1G
```

**Verify exact Traefik labels for netdata from running container before writing:**
```bash
ssh vps "sudo docker inspect netdata-kk4kcw4csksc48848go4o0wo \
  --format '{{json .Config.Labels}}' | python3 -m json.tool | grep traefik"
```

**Update volumes block in the monitoring compose (add 3 new):**
```yaml
volumes:
  loki-data:
  promtail-positions:
  prometheus-data:
  alertmanager-data:
  grafana-data:
  netdata-config:       # NEW
  netdata-lib:          # NEW
  netdata-cache:        # NEW
```

NOTE: Docker Compose project name is `monitoring` (from directory `/opt/monitoring/`). All volumes will be named `monitoring_<vol-name>`. When pre-creating `monitoring_grafana-data` and copying data into it, Docker Compose will find it already exists and use it.

#### `/opt/gatus/compose.yaml` (new)

```yaml
services:
  gatus:
    image: twinproduction/gatus:latest
    container_name: gatus
    restart: unless-stopped
    volumes:
      - /opt/monitoring/configs/gatus:/config:ro
    environment:
      GATUS_METRICS_ENABLED: "true"
    networks:
      - coolify
    labels:
      - "traefik.enable=true"
      - "traefik.docker.network=coolify"
      - "traefik.http.routers.gatus.rule=Host(`status.vps1.ocoron.com`)"
      - "traefik.http.routers.gatus.entrypoints=websecure"
      - "traefik.http.routers.gatus.tls=true"
      - "traefik.http.routers.gatus.tls.certresolver=letsencrypt"
      - "traefik.http.services.gatus.loadbalancer.server.port=8080"
    deploy:
      resources:
        limits:
          memory: 256M
    healthcheck:
      test: ["CMD-SHELL", "wget -qO- http://localhost:8080/health || exit 1"]
      interval: 30s
      timeout: 10s
      retries: 3

networks:
  coolify:
    external: true
```

**Verify exact Traefik labels and env from running gatus container before writing:**
```bash
ssh vps "sudo docker inspect gatus-v8s4cokcwg0co4w8okkccc0w \
  --format '{{json .Config.Labels}}' | python3 -m json.tool | grep traefik"
ssh vps "sudo docker inspect gatus-v8s4cokcwg0co4w8okkccc0w \
  --format '{{json .Config.Env}}'"
```

#### `/opt/n8n/compose.yaml` (new)

```yaml
services:
  n8n:
    image: n8nio/n8n:latest
    container_name: n8n
    restart: unless-stopped
    env_file: .env
    volumes:
      - n8n-data:/home/node/.n8n
    networks:
      - coolify
    labels:
      - "traefik.enable=true"
      - "traefik.docker.network=coolify"
      - "traefik.http.routers.n8n.rule=Host(`n8n.vps1.ocoron.com`)"
      - "traefik.http.routers.n8n.entrypoints=websecure"
      - "traefik.http.routers.n8n.tls=true"
      - "traefik.http.routers.n8n.tls.certresolver=letsencrypt"
      - "traefik.http.routers.n8n.middlewares=authelia-forward@docker,gzip@docker"
      - "traefik.http.services.n8n.loadbalancer.server.port=5678"
    deploy:
      resources:
        limits:
          memory: 2G
          cpus: "1.0"

volumes:
  n8n-data:
    external: true              # Pre-created from UUID volume copy

networks:
  coolify:
    external: true
```

`/opt/n8n/.env`:
```
N8N_ENCRYPTION_KEY=4MUWbwje4W3D8ZvQos5s9M5aaKH0SR14
N8N_HOST=n8n.vps1.ocoron.com
N8N_PROTOCOL=https
WEBHOOK_URL=https://n8n.vps1.ocoron.com/
GENERIC_TIMEZONE=Europe/Istanbul
N8N_DIAGNOSTICS_ENABLED=false
N8N_VERSION_NOTIFICATIONS_ENABLED=false
# plus any remaining vars from Coolify env extraction
```

#### `/opt/glitchtip/compose.yaml` (new — merges 2 Coolify services)

```yaml
services:
  glitchtip-web:
    image: glitchtip/glitchtip:latest
    container_name: glitchtip-web
    restart: unless-stopped
    env_file: .env
    networks:
      - coolify
    labels:
      - "traefik.enable=true"
      - "traefik.docker.network=coolify"
      - "traefik.http.routers.glitchtip.rule=Host(`errors.vps1.ocoron.com`)"
      - "traefik.http.routers.glitchtip.entrypoints=websecure"
      - "traefik.http.routers.glitchtip.tls=true"
      - "traefik.http.routers.glitchtip.tls.certresolver=letsencrypt"
      - "traefik.http.routers.glitchtip.middlewares=gzip@docker"
      - "traefik.http.services.glitchtip.loadbalancer.server.port=8000"
    deploy:
      resources:
        limits:
          memory: 512M
          cpus: "0.5"

  glitchtip-worker:
    image: glitchtip/glitchtip:latest
    container_name: glitchtip-worker
    command: ./bin/run-celery-with-beat.sh
    restart: unless-stopped
    env_file: .env
    environment:
      CELERY_WORKER_CONCURRENCY: "2"
    networks:
      - coolify
    deploy:
      resources:
        limits:
          memory: 512M
          cpus: "0.5"

# No volumes — all state in postgres-main/glitchtip database

networks:
  coolify:
    external: true
```

`/opt/glitchtip/.env`:
```
DATABASE_URL=postgresql://postgres:postgres@postgres-main:5432/glitchtip
REDIS_URL=redis://redis-main:6379/4
SECRET_KEY=YWH7736oLuTID-NmAVDw90Th0CljrpDqWvp4UsrtIfndvT3KYA
GLITCHTIP_DOMAIN=https://errors.vps1.ocoron.com
DEFAULT_FROM_EMAIL=noreply@ocoron.com
EMAIL_URL=<extract from Coolify service compose dump>
CELERY_WORKER_CONCURRENCY=2
```

#### `/opt/apprise/compose.yaml` (new)

Verify exact image, volumes, and labels from running container before writing:
```bash
ssh vps "sudo docker inspect apprise-lcocgs4gs8ksg4g08w40ows8 \
  --format '{\"Image\":\"{{.Config.Image}}\",\"Cmd\":{{json .Config.Cmd}},\"Env\":{{json .Config.Env}},\"Labels\":{{json .Config.Labels}},\"Mounts\":{{json .Mounts}}}' \
  | python3 -m json.tool"
```

Expected structure:
```yaml
services:
  apprise:
    image: caronc/apprise:latest
    container_name: apprise
    restart: unless-stopped
    volumes:
      - apprise-config:/config
    networks:
      - coolify
    labels:
      # extract from running container
    deploy:
      resources:
        limits:
          memory: 1G

volumes:
  apprise-config:
    external: true              # Pre-created from UUID volume copy

networks:
  coolify:
    external: true
```

Note: Apprise also has two anonymous volumes (`/plugin` and `/attach`). These are recreated automatically — do NOT preserve them.

#### `/opt/backrest/compose.yaml` (new)

Extract from Coolify services dump and strip Coolify labels. All mounts are bind mounts — no volume migration needed.

Expected structure:
```yaml
services:
  backrest:
    image: garethgeorge/backrest:latest
    container_name: backrest
    restart: unless-stopped
    volumes:
      - /opt/backrest/data:/data
      - /opt/backrest/config:/config
      - /opt/backrest/cache:/cache
      - /opt/backrest/tmp:/tmp
      - /opt:/backup-opt:ro
      - /var/lib/docker/volumes:/backup-volumes:ro
      - /opt/backups:/backup-postgres
      - /var/run/docker.sock:/var/run/docker.sock:ro
    env_file: .env           # AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY
    environment:
      BACKREST_DATA: /data
      BACKREST_CONFIG: /config/config.json
      XDG_CACHE_HOME: /cache
      TMPDIR: /tmp
      TZ: Europe/Istanbul
    networks:
      - coolify
    labels:
      # extract from Coolify services dump — backrest UUID: l48000k44wc4gk8os88s8k0c
    deploy:
      resources:
        limits:
          memory: 512M

networks:
  coolify:
    external: true
```

#### `/opt/meilisearch/compose.yaml` (new — with persistent volume)

```yaml
services:
  meilisearch:
    image: getmeili/meilisearch:v1.13
    container_name: meilisearch
    restart: unless-stopped
    volumes:
      - meilisearch-data:/meili_data
    environment:
      MEILI_MASTER_KEY: "${MEILI_MASTER_KEY}"
      MEILI_ENV: production
      MEILI_EXPERIMENTAL_ENABLE_METRICS: "true"
    networks:
      - coolify
    deploy:
      resources:
        limits:
          memory: 512M

volumes:
  meilisearch-data:
    external: true              # Pre-created from container's /meili_data

networks:
  coolify:
    external: true
```

`/opt/meilisearch/.env`:
```
MEILI_MASTER_KEY=n7mjRrSipeqy8nWzadLZYarxiUqO35tW
```

#### `/opt/gotenberg/compose.yaml` (new)

```yaml
services:
  gotenberg:
    image: gotenberg/gotenberg:8.32.0
    container_name: gotenberg
    restart: unless-stopped
    command:
      - "gotenberg"
      - "--api-port=3000"
      - "--api-basic-auth-username=gotenberg"
      - "--api-basic-auth-password=aMuGTzjlZ7z9wPHeGiIbHq8noGjFSpY7"
    networks:
      - coolify
    deploy:
      resources:
        limits:
          memory: 512M

# No volumes — stateless

networks:
  coolify:
    external: true
```

Verify exact command flags from running container:
```bash
ssh vps "sudo docker inspect e04k4sco44ow04ccc0o0k00k-210433823748 \
  --format '{{json .Config.Cmd}}'"
```

#### `/opt/browserless/compose.yaml` (new)

```yaml
services:
  browserless:
    image: ghcr.io/browserless/chromium:latest
    container_name: browserless
    restart: unless-stopped
    environment:
      TOKEN: "${BROWSERLESS_TOKEN}"
      CONCURRENT: "10"
      TIMEOUT: "60000"
    networks:
      - coolify
    deploy:
      resources:
        limits:
          memory: 2G

# No volumes — stateless

networks:
  coolify:
    external: true
```

`/opt/browserless/.env`:
```
BROWSERLESS_TOKEN=TWrqUboUGCDIm8IEck5wsqJUlJNvssPi
```

---

## Part 4 — Migration Phases

### Phase 0 — Extract Everything (VPS read-only, no containers changed)

**All of Phase 0 must complete before any container is touched.**

#### 0-A: Extract Coolify Service Composes from DB

The compose files for all 15 services exist only in the Coolify database. Extract them now:

```bash
ssh vps "sudo docker exec coolify-db psql -U coolify -d coolify -t -A -c \
  \"SELECT 'UUID: ' || uuid || E'\nNAME: ' || name || E'\n' || \
    COALESCE(docker_compose_raw, 'NULL') || E'\n===END===\n' \
    FROM services ORDER BY name;\"" \
  > /opt/fabrik/docs/reference/coolify-services-compose-dump.txt
wc -l /opt/fabrik/docs/reference/coolify-services-compose-dump.txt
# Should be several hundred lines
```

Cross-reference each service's compose with the standalone compose file being written. Understand every difference.

#### 0-B: Extract All Application Secrets

```bash
# site-provisioner
ssh vps "sudo docker exec coolify-db psql -U coolify -d coolify -t -A -c \
  \"SELECT key || '=' || value FROM environment_variables \
    WHERE application_id='qokoksogwsk0c04gcs4swwgs' ORDER BY key;\"" \
  > /opt/fabrik/docs/reference/vps-env-site-provisioner.txt

# image-broker
ssh vps "sudo docker exec coolify-db psql -U coolify -d coolify -t -A -c \
  \"SELECT key || '=' || value FROM environment_variables \
    WHERE application_id='zo4ggs4g880skwkocwwkscgk' ORDER BY key;\"" \
  > /opt/fabrik/docs/reference/vps-env-image-broker.txt

# All exited apps (secrets would be lost with Coolify)
for uuid in j8gg4ggskkossc4gkwowk4os w4oocckkwko8kowggsw8sogc bsswwg4kg480c000gksw004k \
            nwcckwggw0o0g40gwskk8kk8 zsccsksoc8sssc8k00sgcc08 kgws0s4cscsosw8gg848cwgw; do
  echo "=== $uuid ===" >> /opt/fabrik/docs/reference/vps-env-exited-apps.txt
  ssh vps "sudo docker exec coolify-db psql -U coolify -d coolify -t -A -c \
    \"SELECT a.name || ' | ' || e.key || '=' || e.value FROM environment_variables e \
      JOIN applications a ON e.application_id = a.id \
      WHERE a.uuid='$uuid' ORDER BY e.key;\"" \
    >> /opt/fabrik/docs/reference/vps-env-exited-apps.txt
done
```

#### 0-C: Extract Exited App Compose Files from DB

```bash
for uuid in j8gg4ggskkossc4gkwowk4os w4oocckkwko8kowggsw8sogc bsswwg4kg480c000gksw004k \
            nwcckwggw0o0g40gwskk8kk8 zsccsksoc8sssc8k00sgcc08 kgws0s4cscsosw8gg848cwgw; do
  echo "=== $uuid ===" >> /opt/fabrik/docs/archive/coolify-exited-app-composes.txt
  ssh vps "sudo docker exec coolify-db psql -U coolify -d coolify -t -A -c \
    \"SELECT COALESCE(docker_compose_raw, 'NULL') FROM applications WHERE uuid='$uuid';\"" \
    >> /opt/fabrik/docs/archive/coolify-exited-app-composes.txt
done
```

#### 0-D: Extract postgres-main POSTGRES_PASSWORD and Backrest B2 Key

```bash
# postgres-main password
ssh vps "sudo docker inspect postgres-main-l0k4gk0kggc8okcwk0s4c8s8 \
  --format '{{range .Config.Env}}{{println .}}{{end}}' | grep POSTGRES_PASSWORD"
# Save to password manager and /opt/postgres/.env

# Backrest B2 application key (not in known-value secrets — extract from running container or Coolify DB)
ssh vps "sudo docker inspect \$(sudo docker ps --format '{{.Names}}' | grep '^backrest-' | head -1) \
  --format '{{range .Config.Env}}{{println .}}{{end}}' | grep -E 'B2_(KEY|APPLICATION|BUCKET)'"
# Save BACKREST_B2_KEY_ID and BACKREST_B2_APPLICATION_KEY to password manager
```

#### 0-E: Extract All Running Container Envs (full backup)

```bash
ssh vps "sudo docker ps --format '{{.Names}}' | while read n; do
  echo \"===== \$n =====\"
  sudo docker inspect \$n --format '{{range .Config.Env}}{{println .}}{{end}}'
done" > /opt/fabrik/docs/reference/vps-all-container-envs.txt
# This is the safety net — everything recoverable from here if needed
```

#### 0-F: Write All Standalone Compose Files

Write every compose file from Part 3 to the fabrik repo. Commit to git before any VPS changes:

```bash
git add /opt/fabrik/...  # all new compose files
git commit -m "feat: standalone compose files for Coolify migration"
git push
```

#### 0-G: Write .env Files for VPS

Write `.env` files locally (not committed — gitignored), then `scp` to VPS as part of each service phase:

- `/opt/postgres/.env`
- `/opt/n8n/.env`
- `/opt/glitchtip/.env`
- `/opt/apprise/.env` (if needed)
- `/opt/meilisearch/.env`
- `/opt/browserless/.env`
- `/opt/monitoring/.env` (just `GRAFANA_ADMIN_PASSWORD=<value>`)

#### 0-H: Verify Pre-flight State

Before leaving Phase 0:
```bash
# All compose files committed
git log --oneline -3

# All secrets in password manager
# All .env files written locally
# All reference files written to /opt/fabrik/docs/reference/

# Verify Gatus all-green (baseline)
curl -s https://status.vps1.ocoron.com/api/v1/endpoints/statuses | \
  python3 -c "import json,sys; d=json.load(sys.stdin); \
  bad=[e['name'] for e in d if e['results'][-1]['success']==False]; \
  print('FAILING:', bad if bad else 'none')"

# Verify prometheus targets all healthy
ssh vps "curl -s http://localhost:9090/api/v1/targets | \
  python3 -c \"import json,sys; d=json.load(sys.stdin); \
  bad=[t['labels']['job'] for t in d['data']['activeTargets'] if t['health']!='up']; \
  print('DOWN targets:', bad if bad else 'none')\""
```

---

### Phase 1 — postgres-main Migration (~5 min downtime for app services)

Postgres is the highest-risk migration. All application databases live here.

**Before starting:** Confirm `POSTGRES_PASSWORD` from Phase 0-D is saved.

```bash
# Step 1: Verify source volume size
ssh vps "sudo docker run --rm -v l0k4gk0kggc8okcwk0s4c8s8_postgres-data:/v \
  alpine du -sh /v"
# Note the size. Target must match.

# Step 2: Create target volume and standalone compose directory
ssh vps "sudo docker volume create postgres-data"
ssh vps "mkdir -p /opt/postgres"
scp /opt/fabrik/infra/postgres/compose.yaml vps:/opt/postgres/compose.yaml
scp /opt/fabrik/infra/postgres/.env vps:/opt/postgres/.env
ssh vps "chmod 600 /opt/postgres/.env"

# Step 3: Stop all postgres consumers
ssh vps "for prefix in site-provisioner-qokoks image-broker-zo4ggs \
  glitchtip-web-z00k glitchtip-worker-msgo n8n-s8gwc; do
  c=\$(sudo docker ps --format '{{.Names}}' | grep ^\${prefix} | head -1)
  [ -n \"\$c\" ] && sudo docker stop \$c && echo \"Stopped \$c\"
done"

# Step 4: Stop postgres
ssh vps "sudo docker stop postgres-main-l0k4gk0kggc8okcwk0s4c8s8"

# Step 5: Offline copy (consistent — postgres is stopped)
ssh vps "sudo docker run --rm \
  -v l0k4gk0kggc8okcwk0s4c8s8_postgres-data:/src \
  -v postgres-data:/dst \
  alpine sh -c 'cd /src && cp -a . /dst/ && echo COPY_DONE'"
# Must print COPY_DONE

# Step 6: Verify sizes match (within 1%)
SRC=$(ssh vps "sudo docker run --rm -v l0k4gk0kggc8okcwk0s4c8s8_postgres-data:/v alpine du -sb /v | cut -f1")
DST=$(ssh vps "sudo docker run --rm -v postgres-data:/v alpine du -sb /v | cut -f1")
echo "Source: $SRC bytes, Dest: $DST bytes"
# Must be within 1% (allow for metadata overhead)

# Step 7: Start postgres from standalone compose
ssh vps "cd /opt/postgres && sudo docker compose up -d"
ssh vps "until sudo docker exec postgres-main pg_isready -U postgres 2>/dev/null; do
  echo 'waiting for postgres...' && sleep 2
done && echo 'postgres ready'"

# Step 8: Verify all databases exist
ssh vps "sudo docker exec postgres-main psql -U postgres -c '\l'"
# Must see: glitchtip, postgres, site_provisioner (and templates)

# Step 9: Verify postgres-main DNS name works (other services use this name)
ssh vps "sudo docker run --rm --network coolify alpine \
  sh -c 'nc -zv postgres-main 5432 && echo DNS_OK || echo DNS_FAIL'"

# Step 10: Restart consumers
ssh vps "for prefix in site-provisioner-qokoks image-broker-zo4ggs \
  glitchtip-web-z00k glitchtip-worker-msgo n8n-s8gwc; do
  c=\$(sudo docker ps -a --format '{{.Names}}' | grep ^\${prefix} | head -1)
  [ -n \"\$c\" ] && sudo docker start \$c && echo \"Started \$c\"
done"

# Step 11: Verify consumers reconnected
sleep 10
for svc in site-provisioner glitchtip-web; do
  ssh vps "sudo docker logs \$(sudo docker ps --format '{{.Names}}' | grep ^\$svc | head -1) \
    2>&1 | grep -E '(error|connected|ready|started)' | tail -5"
done
```

**ROLLBACK (if postgres fails):**
```bash
ssh vps "cd /opt/postgres && sudo docker compose down"
ssh vps "sudo docker start postgres-main-l0k4gk0kggc8okcwk0s4c8s8"
# Wait for ready, then restart consumers
```

---

### Phase 2 — n8n Migration (~3 min downtime for automation)

**Before starting:** Verify `N8N_ENCRYPTION_KEY=4MUWbwje4W3D8ZvQos5s9M5aaKH0SR14` is in `/opt/n8n/.env`.

```bash
# Pre-check: Confirm n8n Authelia middleware is working before touching anything
curl -si https://n8n.vps1.ocoron.com/ -o /dev/null -w "%{http_code}\n"
# Must be 302 (Authelia redirect) — confirms authelia-forward@docker middleware is registered
# 200 = n8n accessible without auth (wrong), 502 = Traefik can't reach n8n (stop and fix first)
# Note: n8n compose spec declares middlewares=authelia-forward@docker,gzip@docker
# This middleware is defined by the Authelia container labels. Requires Authelia running.
# Phase 3 migrates Authelia with stable container_name: authelia — middleware survives restart.
```

```bash
# Step 1: Verify source volume
ssh vps "sudo docker run --rm -v s8gwccsws0ccssw0wwgwsoks_n8n-data:/v alpine du -sh /v"
# Note size. Should be ~856KB.

# Step 2: Create volume and deploy files
ssh vps "sudo docker volume create n8n-data"
ssh vps "mkdir -p /opt/n8n"
scp /opt/fabrik/infra/n8n/compose.yaml vps:/opt/n8n/compose.yaml
scp /opt/fabrik/infra/n8n/.env vps:/opt/n8n/.env
ssh vps "chmod 600 /opt/n8n/.env"

# Step 3: Stop n8n
ssh vps "sudo docker stop n8n-s8gwccsws0ccssw0wwgwsoks"

# Step 4: Copy volume
ssh vps "sudo docker run --rm \
  -v s8gwccsws0ccssw0wwgwsoks_n8n-data:/src \
  -v n8n-data:/dst \
  alpine sh -c 'cd /src && cp -a . /dst/ && echo COPY_DONE'"

# Step 5: Start from standalone compose
ssh vps "cd /opt/n8n && sudo docker compose up -d"
sleep 15

# Step 6: Verify (no encryption errors = key is correct)
ssh vps "sudo docker logs n8n 2>&1 | grep -iE '(error|encrypt|ready|listening)' | tail -20"
# Must NOT contain: "Failed to decrypt credentials", "encryption key"
# Must contain: "Editor is now accessible" or similar startup message

# Step 7: Verify workflows accessible
curl -si https://n8n.vps1.ocoron.com/ -o /dev/null -w "%{http_code}\n"
# 200 or 302 (redirect to Authelia)
```

**ROLLBACK:**
```bash
ssh vps "cd /opt/n8n && sudo docker compose down"
ssh vps "sudo docker start n8n-s8gwccsws0ccssw0wwgwsoks"
```

---

### Phase 3 — Authelia Migration (~2 min auth interruption)

Auth will be down for ~2 min. Admin dashboards return 502. Gatus fires alerts — this is expected.

#### Step 3-1: Extract All Files from Volume to Disk

```bash
# The volume contains 3 files. Copy ALL to /opt/authelia/config/.
ssh vps "sudo docker run --rm \
  -v hks48k8sg8o4co4co08co00o_authelia-config:/src \
  -v /opt/authelia/config:/dst \
  alpine sh -c 'cp -a /src/. /dst/ && ls -la /dst/'"
# Must see: configuration.yml, db.sqlite3, users_database.yml

# Verify all 3 are non-zero
ssh vps "du -sh /opt/authelia/config/configuration.yml \
  /opt/authelia/config/db.sqlite3 \
  /opt/authelia/config/users_database.yml"
# All must be > 0. db.sqlite3 must be ~311KB.
```

#### Step 3-2: Fix Permissions

Authelia container runs as UID 8000. `chown` must succeed — never fall back to world-writable permissions on TOTP secrets.

```bash
ssh vps "sudo chown -R 8000:8000 /opt/authelia/config/"
# Verify ownership applied
ssh vps "ls -la /opt/authelia/config/"
# All 3 files must show owner 8000 (not root). If chown fails, fix sudo config first.
# db.sqlite3 must be writable by owner (8000) for Authelia to update sessions.
```

#### Step 3-3: Upload New Authelia Compose

```bash
scp /opt/fabrik/infra/authelia/compose.yaml vps:/opt/authelia/compose.yaml
```

#### Step 3-4: Switch (~2 min auth down)

```bash
# Stop Coolify-managed authelia
ssh vps "sudo docker stop authelia-hks48k8sg8o4co4co08co00o"

# Start from standalone compose (bind mount)
ssh vps "cd /opt/authelia && sudo docker compose up -d"

# Wait and check logs
sleep 10
ssh vps "sudo docker logs authelia 2>&1 | tail -30"
# Must see: "Configuration parsed and loaded successfully"
# Must NOT see: "error loading configuration", "panic", "failed to"

# Verify auth endpoint responds
ssh vps "curl -si http://localhost:9091/api/health"
# Expected: HTTP 200

# Verify authelia-forward middleware works from outside
curl -si https://monitor.vps1.ocoron.com/ -o /dev/null -w "%{http_code}\n"
# Expected: 302 (redirect to Authelia) NOT 502
```

#### Step 3-5: Update authelia-config-sync to Use Stable Name

```bash
# See current service file
ssh vps "sudo cat /etc/systemd/system/authelia-config-sync.service"

# Update UUID container name to stable name
ssh vps "sudo sed -i \
  's/authelia-hks48k8sg8o4co4co08co00o/authelia/g' \
  /etc/systemd/system/authelia-config-sync.service"

# Reload and restart
ssh vps "sudo systemctl daemon-reload && sudo systemctl restart authelia-config-sync"
ssh vps "sudo systemctl status authelia-config-sync"

# Test: touch config and verify authelia restarts cleanly
ssh vps "sudo touch /opt/authelia/config/configuration.yml"
sleep 5
ssh vps "sudo docker ps | grep authelia"
# Container should be running (sync triggers restart, not crash)
```

**ROLLBACK:**
```bash
ssh vps "cd /opt/authelia && sudo docker compose down"
ssh vps "sudo docker start authelia-hks48k8sg8o4co4co08co00o"
ssh vps "sudo sed -i 's/authelia$/authelia-hks48k8sg8o4co4co08co00o/g' \
  /etc/systemd/system/authelia-config-sync.service"
ssh vps "sudo systemctl daemon-reload && sudo systemctl restart authelia-config-sync"
```

---

### Phase 4 — Monitoring Stack Consolidation (~5 min observability gap)

**Pre-flight: Confirm compose project name is `monitoring`.**

```bash
# The project name determines all volume name prefixes. Must be 'monitoring'.
ssh vps "cd /opt/monitoring && sudo docker compose ls"
# Must show project name: monitoring
# If it shows a different name, volume pre-creation commands in this phase MUST be updated.
ssh vps "sudo docker volume ls | grep monitoring_ | sort"
# Must show: monitoring_prometheus-data (plus alertmanager-data, grafana-data, etc. if already created)
```

`/opt/monitoring/compose.yaml` already runs prometheus, postgres-exporter, redis-exporter, pushgateway correctly. The 7 Coolify-managed monitoring services (loki, promtail, alertmanager, node-exporter, cadvisor, grafana, netdata) need to join the same compose.

The compose file already has correct definitions for all of them (from Part 3 above — just add netdata). Volumes will be created as `monitoring_<name>` (Docker Compose project prefix).

#### Step 4-1: Pre-create grafana volume with data

```bash
# Create the monitoring-project-prefixed volume
ssh vps "sudo docker volume create monitoring_grafana-data"

# Copy from UUID volume to monitoring volume (while Coolify grafana still running)
ssh vps "sudo docker run --rm \
  -v loc484owg8gsw04owo0go8kc_grafana-data:/src \
  -v monitoring_grafana-data:/dst \
  alpine sh -c 'cp -a /src/. /dst/ && echo COPY_DONE'"

# Verify
ssh vps "sudo docker run --rm -v monitoring_grafana-data:/v alpine du -sh /v"
ssh vps "sudo docker run --rm -v loc484owg8gsw04owo0go8kc_grafana-data:/v alpine du -sh /v"
# Must match (within 1%)
```

#### Step 4-2: Add netdata to /opt/monitoring/compose.yaml

Upload the updated compose file (with netdata added from Part 3):
```bash
scp /opt/fabrik/infra/monitoring/compose.yaml vps:/opt/monitoring/compose.yaml
```

#### Step 4-3: Stop All 7 Coolify Monitoring Containers

```bash
ssh vps "for uuid in loc484owg8gsw04owo0go8kc r48swckog008wosgwcs4g0g0 \
  zw4swgkwk0s4s8kg048gw80o w0000ckgsgg048w0848okk08 \
  doc8c8gkcgs88s8ckggw84o4 r08sog4gwws88og048ows448 kk4kcw4csksc48848go4o0wo; do
  c=\$(sudo docker ps --format '{{.Names}}' | grep \${uuid} | head -1)
  [ -n \"\$c\" ] && sudo docker stop \$c && echo \"Stopped \$c\"
done"
```

#### Step 4-4: Start from Unified Compose

```bash
# This starts only the services not already running
# (prometheus/postgres-exporter/redis-exporter/pushgateway are unaffected)
ssh vps "cd /opt/monitoring && sudo docker compose up -d"
```

#### Step 4-5: Verify

```bash
# All monitoring containers running with stable names
ssh vps "sudo docker ps --format '{{.Names}}' | grep -E \
  '^(prometheus|postgres-exporter|redis-exporter|pushgateway|loki|promtail|alertmanager|node-exporter|cadvisor|grafana|netdata)$' | sort"
# Must show all 11 services

# Grafana accessible
sleep 30
curl -si https://monitor.vps1.ocoron.com/ -o /dev/null -w "%{http_code}\n"
# 302 or 200

# Prometheus sees grafana as a target
ssh vps "curl -s http://localhost:9090/api/v1/targets | \
  python3 -c \"import json,sys; d=json.load(sys.stdin); \
  [print(t['labels']['job'], t['health']) for t in d['data']['activeTargets']]\""
# All target jobs should show 'up' (some may be 'unknown' briefly)
```

**ROLLBACK:**
```bash
# Stop newly started monitoring services
ssh vps "cd /opt/monitoring && sudo docker compose stop loki promtail alertmanager \
  node-exporter cadvisor grafana netdata"
# Restart Coolify UUID containers
ssh vps "for uuid in loc484owg8gsw04owo0go8kc r48swckog008wosgwcs4g0g0 \
  zw4swgkwk0s4s8kg048gw80o w0000ckgsgg048w0848okk08 \
  doc8c8gkcgs88s8ckggw84o4 r08sog4gwws88og048ows448 kk4kcw4csksc48848go4o0wo; do
  c=\$(sudo docker ps -a --format '{{.Names}}' | grep \${uuid} | head -1)
  [ -n \"\$c\" ] && sudo docker start \$c && echo \"Started \$c\"
done"
```

---

### Phase 5 — Gatus Migration (~1 min monitoring gap)

Gatus is a Coolify Service but its config is already bind-mounted from `/opt/monitoring/configs/gatus/`. Migration is lightweight.

```bash
# Create compose directory
ssh vps "mkdir -p /opt/gatus"
scp /opt/fabrik/infra/gatus/compose.yaml vps:/opt/gatus/compose.yaml

# Stop Coolify gatus
ssh vps "sudo docker stop gatus-v8s4cokcwg0co4w8okkccc0w"

# Start standalone
ssh vps "cd /opt/gatus && sudo docker compose up -d"
sleep 10

# Verify
ssh vps "sudo docker ps | grep gatus"
curl -si https://status.vps1.ocoron.com/ -o /dev/null -w "%{http_code}\n"
# 200

# Verify Prometheus can scrape gatus by stable name
ssh vps "curl -s http://localhost:9090/api/v1/targets | \
  python3 -c \"import json,sys; d=json.load(sys.stdin); \
  [print(t['labels']['job'],t['labels'].get('instance',''),t['health']) \
  for t in d['data']['activeTargets'] if 'gatus' in str(t['labels'])]\""
```

**ROLLBACK:**
```bash
ssh vps "cd /opt/gatus && sudo docker compose down"
ssh vps "sudo docker start gatus-v8s4cokcwg0co4w8okkccc0w"
```

---

### Phase 6 — GlitchTip Migration (~2 min error tracking gap)

```bash
ssh vps "mkdir -p /opt/glitchtip"
scp /opt/fabrik/infra/glitchtip/compose.yaml vps:/opt/glitchtip/compose.yaml
scp /opt/fabrik/infra/glitchtip/.env vps:/opt/glitchtip/.env
ssh vps "chmod 600 /opt/glitchtip/.env"

# Stop both Coolify GlitchTip containers
ssh vps "sudo docker stop glitchtip-web-z00kkck8c8cwo800kk440csk glitchtip-worker-msgo0sg8gsgo4w4sscckc84g"

# Start from unified compose
ssh vps "cd /opt/glitchtip && sudo docker compose up -d"
sleep 15

# Verify
ssh vps "sudo docker ps | grep glitchtip"
# Must show: glitchtip-web, glitchtip-worker (stable names)

curl -si https://errors.vps1.ocoron.com/ -o /dev/null -w "%{http_code}\n"
# 200 or 302

# Check worker connected
ssh vps "sudo docker logs glitchtip-worker 2>&1 | tail -10"
```

**ROLLBACK:**
```bash
ssh vps "cd /opt/glitchtip && sudo docker compose down"
ssh vps "sudo docker start glitchtip-web-z00kkck8c8cwo800kk440csk glitchtip-worker-msgo0sg8gsgo4w4sscckc84g"
```

---

### Phase 7 — Apprise Migration (~1 min notification gap)

```bash
# Copy apprise-config volume to clean name
ssh vps "sudo docker volume create apprise-config"
ssh vps "sudo docker stop apprise-lcocgs4gs8ksg4g08w40ows8"
ssh vps "sudo docker run --rm \
  -v lcocgs4gs8ksg4g08w40ows8_apprise-config:/src \
  -v apprise-config:/dst \
  alpine sh -c 'cp -a /src/. /dst/ && echo COPY_DONE'"

ssh vps "mkdir -p /opt/apprise"
scp /opt/fabrik/infra/apprise/compose.yaml vps:/opt/apprise/compose.yaml
ssh vps "cd /opt/apprise && sudo docker compose up -d"
sleep 10

# Verify apprise is reachable internally
ssh vps "sudo docker exec gatus sh -c 'wget -qO- http://apprise:8000/' 2>/dev/null || \
  curl -s http://apprise:8000/ | head -5"
```

**ROLLBACK:**
```bash
ssh vps "cd /opt/apprise && sudo docker compose down"
ssh vps "sudo docker start apprise-lcocgs4gs8ksg4g08w40ows8"
```

---

### Phase 8 — Backrest Migration (~1 min backup management gap)

Backrest is 100% bind-mount based — no volume copy needed.

```bash
scp /opt/fabrik/infra/backrest/compose.yaml vps:/opt/backrest/compose.yaml

# Verify /opt/backrest/config/config.json exists and is non-empty
ssh vps "ls -lh /opt/backrest/config/config.json"

# Stop Coolify backrest
ssh vps "sudo docker stop backrest-l48000k44wc4gk8os88s8k0c"

# Start standalone
ssh vps "cd /opt/backrest && sudo docker compose up -d"
sleep 10

# Verify backrest UI accessible
curl -si https://backrest.vps1.ocoron.com/ -o /dev/null -w "%{http_code}\n" 2>/dev/null || echo "check domain"
ssh vps "sudo docker logs backrest 2>&1 | tail -10"
```

---

### Phase 9 — Meilisearch Migration (volume creation required)

**This phase creates a persistent volume from ephemeral container data. Do not skip.**

```bash
# Step 1: Verify meilisearch has no mounts (confirming ephemeral)
container=$(ssh vps "sudo docker ps --format '{{.Names}}' | grep '^bs0wo48k4gwo440gcowscoc8' | head -1")
ssh vps "sudo docker inspect $container --format '{{json .Mounts}}'"
# Expected: [] (empty — no mounts)

# Step 2: Check what's in /meili_data
ssh vps "sudo docker exec $container find /meili_data -type f | head -20"
# If empty, indexes were never built — fresh start is safe
# If non-empty, must copy before migration

# Step 3: Create volume
ssh vps "sudo docker volume create meilisearch-data"

# Step 4: Copy from container's overlay filesystem to new volume
# (Can't use docker cp directly to a volume — use intermediate host path)
ssh vps "sudo rm -rf /tmp/meili_backup && sudo docker cp $container:/meili_data /tmp/meili_backup"
ssh vps "sudo docker run --rm \
  -v meilisearch-data:/meili_data \
  -v /tmp/meili_backup:/backup:ro \
  alpine sh -c 'cp -a /backup/. /meili_data/ && echo COPY_DONE'"
ssh vps "rm -rf /tmp/meili_backup"

# Step 5: Stop UUID container
ssh vps "sudo docker stop $container"

# Step 6: Deploy standalone
ssh vps "mkdir -p /opt/meilisearch"
scp /opt/fabrik/infra/meilisearch/compose.yaml vps:/opt/meilisearch/compose.yaml
scp /opt/fabrik/infra/meilisearch/.env vps:/opt/meilisearch/.env
ssh vps "chmod 600 /opt/meilisearch/.env"
ssh vps "cd /opt/meilisearch && sudo docker compose up -d"
sleep 10

# Step 7: Verify same master key (Prometheus scrape uses this key)
ssh vps "curl -s -H 'Authorization: Bearer n7mjRrSipeqy8nWzadLZYarxiUqO35tW' \
  http://meilisearch:7700/health 2>/dev/null || \
  sudo docker exec meilisearch curl -s http://localhost:7700/health"

# Step 8: Verify stable DNS name works (Prometheus scrape job uses 'meilisearch:7700')
ssh vps "sudo docker run --rm --network coolify alpine \
  sh -c 'nc -zv meilisearch 7700 && echo DNS_OK'"
```

**ROLLBACK:**
```bash
ssh vps "cd /opt/meilisearch && sudo docker compose down"
ssh vps "sudo docker start $container"  # UUID container still exists until Phase 11
```

---

### Phase 10 — Gotenberg + Browserless Migration (stateless — trivial)

```bash
# Gotenberg
got_container=$(ssh vps "sudo docker ps --format '{{.Names}}' | grep '^e04k4sco44ow04ccc0o0k00k' | head -1")
ssh vps "mkdir -p /opt/gotenberg"
scp /opt/fabrik/infra/gotenberg/compose.yaml vps:/opt/gotenberg/compose.yaml
ssh vps "sudo docker stop $got_container"
ssh vps "cd /opt/gotenberg && sudo docker compose up -d"
sleep 5
ssh vps "sudo docker run --rm --network coolify alpine sh -c 'nc -zv gotenberg 3000 && echo OK'"

# Browserless
bl_container=$(ssh vps "sudo docker ps --format '{{.Names}}' | grep '^vckgs8c00o40o884k48cgow8' | head -1")
ssh vps "mkdir -p /opt/browserless"
scp /opt/fabrik/infra/browserless/compose.yaml vps:/opt/browserless/compose.yaml
scp /opt/fabrik/infra/browserless/.env vps:/opt/browserless/.env
ssh vps "sudo docker stop $bl_container"
ssh vps "cd /opt/browserless && sudo docker compose up -d"
sleep 10
ssh vps "sudo docker run --rm --network coolify alpine sh -c 'nc -zv browserless 3000 && echo OK'"
```

---

### Phase 11 — Replace deployer.py + Migrate Fabrik Applications

> **PREREQUISITE — BLOCKING:** The SSH deployer (`deployer_ssh.py`) must be written, tested, and merged to main **before Phase 11 begins**. Phases 1-10 are fully independent and can be executed without it. If the SSH deployer is not ready when Phases 1-10 complete, stop and defer Phase 11 until it is.
>
> site-provisioner and image-broker continue running as UUID-named Coolify apps until the SSH deployer is ready. This is safe — Coolify is still running at this point (removed in Phase 13). Do not remove Coolify (Phase 13) until Phase 11 is complete.

#### Step 11-1: Swap deployer

```bash
cd /opt/fabrik
mv src/fabrik/orchestrator/deployer.py src/fabrik/orchestrator/deployer_coolify.py
# deployer_ssh.py already written
# Update __init__.py import
python -m pytest tests/orchestrator/ -x
.venv/bin/fabrik apply specs/services/image-broker.yaml --dry-run
# Verify output shows SSH commands, not Coolify API calls
```

#### Step 11-2: site-provisioner

```bash
ssh vps "mkdir -p /opt/site-provisioner"
scp /opt/fabrik/docs/reference/vps-env-site-provisioner.txt vps:/opt/site-provisioner/.env
ssh vps "chmod 600 /opt/site-provisioner/.env"

# Run fabrik apply — SSH deployer clones repo, writes compose, builds, starts
cd /opt/fabrik
.venv/bin/fabrik apply specs/services/site-provisioner.yaml

# Verify new container running with stable name
curl -si https://provision.vps1.ocoron.com/health
# 200

# Stop old UUID container (still running, no longer serving traffic)
ssh vps "sudo docker stop \$(sudo docker ps --format '{{.Names}}' | \
  grep '^site-provisioner-qokoks' | head -1)"
```

#### Step 11-3: image-broker

image-broker has a named volume `zo4ggs4g880skwkocwwkscgk_image-cache` — this is a **cache** (external image URLs cached locally). It will be **rebuilt on first use** after migration. No copy needed; `fabrik apply` creates `image-broker_image-cache` fresh.

```bash
ssh vps "mkdir -p /opt/image-broker"
scp /opt/fabrik/docs/reference/vps-env-image-broker.txt vps:/opt/image-broker/.env
ssh vps "chmod 600 /opt/image-broker/.env"

cd /opt/fabrik
.venv/bin/fabrik apply specs/services/image-broker.yaml

# Verify new image-broker cache volume auto-created
ssh vps "sudo docker volume ls | grep image-broker"
# Should show: image-broker_image-cache

# Verify
curl -si https://images.vps1.ocoron.com/health
# 200

# Verify API bypass works (no Authelia redirect)
curl -si https://images.vps1.ocoron.com/api/health
# 200 (no redirect)

# Verify admin UI is protected
curl -si https://images.vps1.ocoron.com/ -o /dev/null -w "%{http_code}\n"
# 302 (Authelia redirect)

# Stop old UUID container
ssh vps "sudo docker stop \$(sudo docker ps --format '{{.Names}}' | \
  grep '^image-broker-zo4ggs' | head -1)"
```

---

### Phase 12 — Pre-Flight Verification (STOP HERE if any check fails)

```bash
echo "=== 1. All expected containers running with stable names ==="
ssh vps "sudo docker ps --format '{{.Names}}' | sort"
# Must include all of: traefik, redis-main, prometheus, postgres-main, authelia,
#   loki, promtail, alertmanager, node-exporter, cadvisor, grafana, netdata,
#   pushgateway, postgres-exporter, redis-exporter, gatus,
#   n8n, apprise, glitchtip-web, glitchtip-worker, backrest,
#   meilisearch, gotenberg, browserless, site-provisioner, image-broker

echo "=== 2. No UUID-suffixed service containers remaining ==="
ssh vps "sudo docker ps --format '{{.Names}}' | grep -E '[a-z0-9]{20}' | grep -v coolify"
# Expected: empty output

echo "=== 3. Gatus all endpoints ==="
curl -s https://status.vps1.ocoron.com/api/v1/endpoints/statuses | \
  python3 -c "import json,sys; d=json.load(sys.stdin);
bad=[e['name'] for e in d if not e['results'][-1]['success']]
print('FAILING:', bad if bad else 'NONE')"

echo "=== 4. Prometheus targets ==="
ssh vps "curl -s http://localhost:9090/api/v1/targets | \
  python3 -c \"import json,sys; d=json.load(sys.stdin)
bad=[t['labels']['job'] for t in d['data']['activeTargets'] if t['health']!='up']
print('DOWN:', bad if bad else 'NONE')\""

echo "=== 5. Auth working ==="
curl -si https://monitor.vps1.ocoron.com/ -o /dev/null -w "%{http_code}\n"
# 302

echo "=== 6. fabrik audit ==="
cd /opt/fabrik && .venv/bin/fabrik audit-registrars
# 0 missing for deployed services

echo "=== 7. fabrik dry-run (no Coolify API calls) ==="
.venv/bin/fabrik apply specs/services/image-broker.yaml --dry-run
# Should show SSH commands, not 'Calling Coolify API'

echo "=== 8. Backrest can connect to B2 ==="
ssh vps "sudo docker exec backrest backrest check --repo vps1-ocoron-backups 2>&1 | tail -5" || \
  echo "check manually via Backrest UI"

echo "=== 9. n8n workflows intact ==="
# Log in to https://n8n.vps1.ocoron.com and verify workflows are visible + credentials work
# Cannot automate — manual check required

echo "=== 10. State files present ==="
ls /opt/fabrik/.fabrik/state/
# site-provisioner.json, image-broker.json

echo "=== 11. Known security gaps acknowledged (post-migration follow-up) ==="
# These are pre-existing gaps, not introduced by this migration:
# a) postgres-exporter uses superuser postgres:postgres — create dedicated read-only user
#    Ticket to file: "Create postgres-exporter dedicated read-only role"
#    SQL: CREATE ROLE exporter LOGIN PASSWORD '<new>' IN ROLE pg_monitor;
#    Then update /opt/monitoring/.env POSTGRES_EXPORTER_DSN and restart postgres-exporter
# b) image-broker SERVICE_INTERNAL_SECRET_KEY is a placeholder — replace with real secret
#    Ticket to file: "Rotate image-broker SERVICE_INTERNAL_SECRET_KEY from placeholder"
echo "REMINDER: File follow-up tickets for items (a) and (b) above"
```

**DO NOT proceed to Phase 13 until all checks pass.**

---

### Phase 13 — Remove Coolify Control Plane (ONE-WAY DOOR)

```bash
# Final confirmation: all services running standalone
ssh vps "sudo docker ps --format '{{.Names}}' | grep -v coolify | sort"

# Stop Coolify control plane
ssh vps "sudo docker stop coolify coolify-db coolify-redis coolify-realtime coolify-sentinel 2>/dev/null || true"

# Remove containers
ssh vps "sudo docker rm coolify coolify-db coolify-redis coolify-realtime coolify-sentinel coolify-proxy 2>/dev/null || true"

# Remove Coolify's own volumes (NOT service data volumes)
ssh vps "sudo docker volume rm coolify-db coolify-redis 2>/dev/null || true"

# Retain /data/coolify/ for 30 days as reference
# After 30 days: ssh vps "sudo mv /data/coolify/ /data/coolify-archive-$(date +%Y%m%d)/"

# Verify everything still running
ssh vps "sudo docker ps --format '{{.Names}}' | wc -l"
# Should be same count minus 5 (Coolify containers removed)

# coolify network now has no owner — this is harmless
ssh vps "sudo docker network inspect coolify --format '{{.Name}}: {{len .Containers}} containers'"
# Shows all service containers still attached
```

---

### Phase 14 — Cleanup

#### Remove coolify-alias-watcher

```bash
ssh vps "sudo systemctl stop coolify-alias-watcher && sudo systemctl disable coolify-alias-watcher"
ssh vps "sudo rm -rf /opt/coolify-alias-watcher"
ssh vps "sudo rm -f /etc/systemd/system/coolify-alias-watcher.service"
ssh vps "sudo systemctl daemon-reload"
```

#### Update vps_apply_limits.sh

Replace `/opt/fabrik/scripts/vps_apply_limits.sh` with the following content (all UUID-prefix patterns replaced with stable names; Coolify control plane entry and alias section removed):

```bash
#!/usr/bin/env bash
# vps_apply_limits.sh — apply Docker memory/CPU limits to all VPS containers
# Run after VPS reboot or after any container restart.
#
# Post-Coolify-migration (2026-05-27): all services have stable container_name.
# No UUID-prefix grep needed. apply_alias section removed (stable names built-in).
# Coolify-sentinel entry removed (control plane gone).

set -e

apply() {
  local pattern=$1 mem=$2 cpu=${3:-}
  local cont
  cont=$(sudo docker ps --format '{{.Names}}' | grep "^${pattern}" | head -1)
  if [ -z "$cont" ]; then
    echo "  NOT FOUND: $pattern"
    return
  fi
  local update_args="--memory $mem --memory-swap $mem"
  [ -n "$cpu" ] && update_args="$update_args --cpus $cpu"
  sudo docker update $update_args "$cont" > /dev/null 2>&1 \
    && echo "  ✅ $pattern → mem=${mem}${cpu:+ cpu=${cpu}}" \
    || echo "  ❌ $pattern → failed"
}

echo "=== VPS resource limits ==="

# Observability
apply alertmanager     256m
apply cadvisor         512m
apply gatus            256m
apply grafana          512m
apply loki             512m   0.5
apply netdata          1g
apply node-exporter    128m
apply promtail         128m
apply prometheus       1g     1.0
apply redis-exporter   64m
apply postgres-exporter 64m
apply pushgateway      64m

# Auth & ops
apply authelia         512m
apply backrest         512m
apply glitchtip-web    512m   0.5
apply glitchtip-worker 512m   0.5

# Data
apply postgres-main    2g
apply redis-main       512m

# Automation
apply n8n              2g     1.0

# Network
apply traefik          256m

# WordPress stack
apply ocoron-com-db-1         1g
apply ocoron-com-wordpress-1  512m
apply ocoron-com-nginx-1      256m
apply ocoron-com-redis-1      256m
apply ocoron-com-backup-1     128m

# Fabrik microservices
apply image-broker     512m
apply site-provisioner 512m

echo "=== Done ==="

# Auto-update VPS docs after limits applied
echo "📝 Updating VPS docs..."
cd /opt/fabrik && python3 scripts/update_vps_docs.py 2>&1 | tail -5
```

Deploy the new script:
```bash
scp /opt/fabrik/scripts/vps_apply_limits.sh vps:/opt/fabrik/scripts/vps_apply_limits.sh
ssh vps "bash /opt/fabrik/scripts/vps_apply_limits.sh"
# All services should show ✅, none should show NOT FOUND
```

#### Remove UUID Volumes (after 7 days of stable operation)

```bash
# Verify no container uses these before removing
for vol in \
  l0k4gk0kggc8okcwk0s4c8s8_postgres-data \
  s8gwccsws0ccssw0wwgwsoks_n8n-data \
  loc484owg8gsw04owo0go8kc_grafana-data \
  lcocgs4gs8ksg4g08w40ows8_apprise-config \
  r48swckog008wosgwcs4g0g0_loki-data \
  zw4swgkwk0s4s8kg048gw80o_alertmanager-data \
  w0000ckgsgg048w0848okk08_promtail-positions \
  kk4kcw4csksc48848go4o0wo_netdata-config \
  kk4kcw4csksc48848go4o0wo_netdata-lib \
  kk4kcw4csksc48848go4o0wo_netdata-cache \
  hks48k8sg8o4co4co08co00o_authelia-config \
  zo4ggs4g880skwkocwwkscgk_image-cache; do
  ssh vps "sudo docker volume rm $vol 2>/dev/null && echo 'removed $vol' || echo 'in use: $vol'"
done
# Clean up UUID-named Docker networks
ssh vps "sudo docker network prune -f"
```

#### Update Documentation

```bash
# AGENTS.md — remove Coolify from Platform at a Glance, update deploy pipeline
# PORTS.md — remove Coolify port 8000
# docs/CONFIGURATION.md — remove COOLIFY_BASE_URL, COOLIFY_API_TOKEN
# .env.example — remove COOLIFY_BASE_URL, COOLIFY_API_TOKEN
# CHANGELOG.md — add migration entry
# docs/LESSONS_LEARNT.md — add lessons
```

---

## Part 5 — Bootstrap Script (New VPS)

`/opt/fabrik/scripts/bootstrap-vps.sh`:

```bash
#!/usr/bin/env bash
# bootstrap-vps.sh — Bring a fresh VPS to full Fabrik platform state
# Usage: ./scripts/bootstrap-vps.sh <vps-ip>
# Prerequisites:
#   - SSH key access to <vps-ip>
#   - /opt/traefik/acme.json backed up (TLS certs)
#   - .env files prepared for each service
set -euo pipefail

VPS="${1:?Usage: $0 <vps-ip>}"
S="ssh ozgur@$VPS"

echo "=== 1. Docker ==="
$S "curl -fsSL https://get.docker.com | sh && sudo usermod -aG docker ozgur"
# NOTE: 'newgrp docker' opens a local subshell — it does NOT activate the group on the remote.
# After this step, disconnect and reconnect SSH so the docker group takes effect.
# Alternatively, use 'sudo docker' for all subsequent commands (script already uses sudo docker).
echo ">>> Re-connect SSH now to pick up docker group: ssh ozgur@$VPS <<<"
read -r -p "Press Enter after reconnecting..."

echo "=== 2. coolify network ==="
$S "sudo docker network create --driver bridge --subnet 10.0.1.0/24 coolify 2>/dev/null || true"

echo "=== 3. Clone fabrik repo ==="
$S "sudo git clone https://github.com/mobasak/fabrik.git /opt/fabrik"

echo "=== 4. Traefik (routing — must be first) ==="
# Restore acme.json from backup FIRST
scp ./backups/acme.json "ozgur@$VPS:/opt/traefik/acme.json"
$S "sudo chmod 600 /opt/traefik/acme.json"
$S "cd /opt/traefik && sudo docker compose up -d"

echo "=== 5. Data layer ==="
# Write .env files before starting
scp ./envs/postgres.env "ozgur@$VPS:/opt/postgres/.env"
$S "cd /opt/postgres && sudo docker compose up -d"
$S "until sudo docker exec postgres-main pg_isready -U postgres 2>/dev/null; do sleep 2; done && echo postgres ready"
$S "cd /opt/redis && sudo docker compose up -d"

echo "=== 6. Auth ==="
# /opt/authelia/config/ must have: configuration.yml, db.sqlite3, users_database.yml
# Restore from backup
scp -r ./backups/authelia-config/ "ozgur@$VPS:/opt/authelia/config/"
$S "sudo chown -R 8000:8000 /opt/authelia/config/"
# If chown fails, do NOT use chmod 777 — fix sudo configuration instead
$S "cd /opt/authelia && sudo docker compose up -d"
$S "sleep 5 && curl -sf http://localhost:9091/api/health && echo authelia ready"

echo "=== 7. Monitoring ==="
scp ./envs/monitoring.env "ozgur@$VPS:/opt/monitoring/.env"
$S "cd /opt/monitoring && sudo docker compose up -d"

echo "=== 8. Gatus ==="
$S "cd /opt/gatus && sudo docker compose up -d"

echo "=== 9. GlitchTip ==="
scp ./envs/glitchtip.env "ozgur@$VPS:/opt/glitchtip/.env"
$S "cd /opt/glitchtip && sudo docker compose up -d"

echo "=== 10. n8n ==="
scp ./envs/n8n.env "ozgur@$VPS:/opt/n8n/.env"
$S "cd /opt/n8n && sudo docker compose up -d"

echo "=== 11. Backrest ==="
# /opt/backrest/config/config.json must be restored from backup
$S "cd /opt/backrest && sudo docker compose up -d"

echo "=== 12. Apprise ==="
$S "cd /opt/apprise && sudo docker compose up -d"

echo "=== 13. Static apps ==="
scp ./envs/meilisearch.env "ozgur@$VPS:/opt/meilisearch/.env"
scp ./envs/browserless.env "ozgur@$VPS:/opt/browserless/.env"
$S "cd /opt/meilisearch && sudo docker compose up -d"
$S "cd /opt/gotenberg && sudo docker compose up -d"
$S "cd /opt/browserless && sudo docker compose up -d"

echo "=== 14. WordPress (optional) ==="
# $S "cd /opt/ocoron-com && sudo docker compose up -d"

echo "=== 15. Fabrik applications ==="
echo "Manual step: set up .env files for site-provisioner and image-broker"
echo "Then: fabrik apply specs/services/site-provisioner.yaml"
echo "Then: fabrik apply specs/services/image-broker.yaml"

echo ""
echo "Bootstrap complete. All platform services should be running."
echo "Run: ssh ozgur@$VPS 'sudo docker ps | wc -l' to verify container count"
```

---

## Part 6 — Rollback Matrix

| Phase | Can rollback? | How |
|---|---|---|
| 0 (extract only) | N/A | No changes made |
| 1 (postgres volume) | ✅ Yes | `docker compose down` in /opt/postgres; `docker start postgres-main-l0k4gk0...` |
| 2 (n8n volume) | ✅ Yes | `docker compose down` in /opt/n8n; `docker start n8n-s8gwc...` |
| 3 (authelia) | ✅ Yes | `docker compose down` in /opt/authelia; `docker start authelia-hks48k...`; revert sync service sed; reload |
| 4 (monitoring) | ✅ Yes | `docker compose stop` new services in /opt/monitoring; `docker start` UUID containers |
| 5 (gatus) | ✅ Yes | `docker compose down` in /opt/gatus; `docker start gatus-v8s4c...` |
| 6 (glitchtip) | ✅ Yes | `docker compose down` in /opt/glitchtip; `docker start glitchtip-web-z00k... glitchtip-worker-msgo...` |
| 7 (apprise) | ✅ Yes | `docker compose down` in /opt/apprise; `docker start apprise-lcocgs...` |
| 8 (backrest) | ✅ Yes | `docker compose down` in /opt/backrest; `docker start backrest-l48000...` |
| 9 (meilisearch) | ✅ Yes | `docker compose down` in /opt/meilisearch; `docker start bs0wo48k...` UUID container |
| 10 (gotenberg/browserless) | ✅ Yes | `docker compose down`; `docker start` UUID containers |
| 11 (deployer + apps) | ✅ Yes | Revert `__init__.py` import; stop new containers; `docker start` UUID containers |
| 12 (pre-flight) | N/A | Verification only |
| 13 (remove Coolify) | ⚠️ Partial | Reinstall Coolify (5 min); DB volume gone = app records lost; service data safe. **Do not cross Phase 13 until Phase 12 all-green.** |
| 14 (cleanup) | ✅ Yes | Restore config from git |

---

## Part 7 — Execution Timeline

| Phase | Description | Service impact | Duration |
|---|---|---|---|
| 0 | Extract secrets + composes from Coolify | None | 2-3 hours |
| 0 | Write all standalone compose files | None | 1-2 days |
| 1 | postgres-main volume + standalone | ~5 min app services offline | 1 hour |
| 2 | n8n volume + standalone | ~3 min n8n offline | 30 min |
| 3 | Authelia bind-mount switch | ~2 min auth offline | 1 hour |
| 4 | Monitoring stack consolidation | ~5 min metrics gap | 1 hour |
| 5 | Gatus standalone | ~1 min status page offline | 20 min |
| 6 | GlitchTip merge | ~2 min error tracking offline | 30 min |
| 7 | Apprise standalone | ~1 min notifications offline | 20 min |
| 8 | Backrest standalone | ~1 min backup UI offline | 20 min |
| 9 | Meilisearch + persistent volume | ~2 min search offline | 30 min |
| 10 | Gotenberg + Browserless | ~1 min each | 20 min |
| 11 | Deployer swap + Fabrik apps | None | 2 hours |
| 12 | Pre-flight verification | None | 30 min |
| 13 | Remove Coolify | None | 15 min |
| 14 | Cleanup | None | 2 hours |

**Total:** ~5 focused days. All phases independently rollback-able until Phase 13.
