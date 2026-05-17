# Fabrik Control Plane — Implementation Plan

**Created:** 2026-04-13
**Last Updated:** 2026-04-18 21:10 UTC+3 (scope re-clarified; zero-touch content moved out to its own plan)
**Status:** APPROVED — Phase 0 (pipeline gaps) COMPLETE · Phase 3 (SSH bypass) COMPLETE · Phase 1 + 2 pending
**Ports:** 8050 (`fabrik-api`) · 3004 (`fabrik-control-plane`)
**URL:** `https://control.vps1.ocoron.com`
**Scope:** Conversational UI + FastAPI bridge fronting the **WordPress 12-stage pipeline** only. Generic-project auto-deployment lives in `2026-04-18-zero-touch-deployment.md`.

---

## Vision

Building a Conversational Control Plane is the realization of a Zero-Ops architecture. By placing a chat interface at the very front of the pipeline, the complexity of Fabrik's microservices is abstracted into a simple dialogue.

Kilo AI acts as the brain. Access to multiple models allows it to dynamically switch contexts — using a creative model to brainstorm the website's niche, content strategy, and structure, then switching to a high-logic coding model to generate the exact JSON payloads required by the backend.

**The workflow has three phases:**

### Phase A — Negotiation (Conversational UI)

The Next.js frontend acts as the chat client. You converse with Kilo AI, defining the website's domain name, target keywords, aesthetic style, and core features. Kilo AI operates with a hidden system prompt that gives it full awareness of the Fabrik infrastructure (Coolify, Traefik, WordPress, site-provisioner, available presets, plugin stack) so it knows exactly what is possible and what parameters must be defined.

### Phase B — Compilation (Structured Output)

Once the website's design and architecture are agreed on, you give Kilo AI the green light. Instead of replying with standard text, Kilo switches modes and outputs a strictly formatted JSON object containing all decided variables (domain, brand, plugins, SEO config, post_deploy flags, monitoring config). This JSON maps exactly to the `site.yaml` spec schema.

### Phase C — Handoff (API Execution with Manual Sign-off)

The Next.js backend intercepts the JSON payload. It renders a **"Approve & Deploy" button** — manual sign-off is mandatory. No auto-fire. When you click approve, the backend POSTs the JSON to `fabrik-api`. The FastAPI bridge writes `site.yaml`, runs `fabrik wp plan && fabrik wp apply`, and streams the 12-stage stdout back to the UI as structured SSE events.

---

## Why Manual Sign-off (Not Auto-fire)

When dealing with stateful infrastructure — DNS propagation, Coolify service creation, volume allocation, automated billing triggers (GA4 property creation, GSC property registration) — a human-in-the-loop approval gate is mandatory. These operations are hard or impossible to reverse automatically. The "Approve & Deploy" button is the explicit contract between the conversation and the infrastructure change.

---

## Goal

Replace the CLI-only deployment workflow with a conversational control plane:

```text
Today:    Edit site.yaml → fabrik wp plan → fabrik wp apply  (WSL terminal only)
Target:   Chat with Kilo AI → approve JSON → click Approve → 12-stage pipeline runs
                                                            → SSE stream shows live progress in UI
```

---

## Backend Option Analysis (Decision Record)

Three options were evaluated for where the Next.js UI should POST the approved JSON payload.

### Option 1 — Direct to `site-provisioner` + Coolify ("Bypass Route") — REJECTED

The Next.js API route would POST directly to infrastructure microservices. **Rejected** because this would completely abandon the `fabrik` CLI's 12-stage WordPress pipeline (`dns → settings → theme → plugins → languages → pages → menus → forms → seo → post_deploy → analytics → monitoring → verify`). All that Python orchestration logic would have to be rewritten in Next.js TypeScript — a massive waste of existing work.

### Option 2 — n8n Workflow Orchestration ("Event-Driven Route") — DEFERRED

Next.js POSTs the JSON to an n8n webhook. n8n acts as the central brain, executing bash nodes to trigger `fabrik` CLI or making HTTP requests itself. **Deferred** because `fabrik` Python CLI is already the orchestrator — forcing n8n to wrap a perfectly functional CLI script just adds an unnecessary point of failure.

**However:** n8n is the correct choice for the *content/SEO pipeline* in a future phase — hooking into `SEOClient`, `TCOClient`, and `ImageBrokerClient` for the automated content creation loop after a site deploys. That is Phase 5 (not in scope here).

### Option 3 — FastAPI Wrapper Around `fabrik` ("Bridge Route") — CHOSEN

A thin FastAPI microservice (`fabrik-api`) sits on the same environment where `fabrik` CLI runs. It accepts the JSON payload, writes `site.yaml`, and spawns a background task running `fabrik wp plan <site> && fabrik wp apply <site>`. Because FastAPI is async, it opens a Server-Sent Events stream back to the Next.js UI, allowing live stage progress to be rendered in the chat window.

**Why this wins:** leverages 100% of existing Python codebase without modification. Zero logic duplication.

---

## Docker Execution Model — Discovery

This was the critical constraint that determined the execution environment. The `fabrik` CLI does **not** use the Docker socket directly. Instead:

```text
fabrik CLI (Python subprocess)
  → ["ssh", "vps", f"sudo docker exec {container} wp {command}"]
    → SSH to 172.93.160.197
      → sudo docker exec <container-name> wp ...
        → WP-CLI runs inside container
```

Specifically, `src/fabrik/drivers/wordpress.py` has two classes:

- **`ContainerResolver`** — resolves the container name by running `ssh vps "docker ps --filter name=<site>"`. Falls back to `WP_CONTAINER_NAME_<SLUG>` env var if set.
- **`WordPressClient`** — executes WP-CLI commands via `ssh_host` → `sudo docker exec`. The `ssh_host` parameter defaults to `"vps"` (the SSH alias in `~/.ssh/config` on WSL).

Both accept `ssh_host` as a constructor parameter — the bypass requires no refactor, just an env-var gate.

**`ContainerResolver` also needs the bypass.** When `FABRIK_EXEC_MODE=local`, the resolver must run `docker ps` directly instead of via SSH:

```python
# ContainerResolver.resolve() — local mode skips SSH
if get_exec_mode() == "local":
    result = subprocess.run(
        ["docker", "ps", "--filter", f"name={self.site_name}", "--format", "{{.Names}}"],
        capture_output=True, text=True, timeout=self.timeout
    )
else:
    result = subprocess.run(
        ["ssh", self.ssh_host, f"docker ps --filter name={self.site_name} --format '{{{{.Names}}}}'"],
        capture_output=True, text=True, timeout=self.timeout
    )
```

Alternatively, set `WP_CONTAINER_NAME_<SLUG>` env var per site in `/opt/fabrik-api/.env` to skip resolver entirely — simpler and recommended for production.

### Why containerizing `fabrik-api` was rejected

If `fabrik-api` ran inside a Docker container, it would need one of:

1. **Docker socket bind-mount** (`/var/run/docker.sock`) — any container with socket access can control all containers on the host. Security risk.
2. **SSH back to itself** (`localhost`) — adds SSH key management complexity and a loopback network hop.

**Decision: native VPS host process.** `fabrik-api` runs as a systemd service directly on the VPS host. `docker exec` calls work natively without SSH or socket exposure.

---

## Per-Site Container Isolation

Each WordPress site gets its own fully isolated Docker Compose stack:

```text
ocoron-com-wordpress-1   ← WordPress FPM (php8.3-fpm-bookworm)
ocoron-com-nginx-1       ← Nginx (reverse proxy + FastCGI cache)
ocoron-com-db-1          ← MariaDB 10.11 (dedicated DB, not shared)
```

Shared services (not duplicated per site):

```text
redis-main               ← shared object cache (all WP sites point here)
postgres-main            ← shared PostgreSQL (non-WP services)
traefik                  ← shared reverse proxy (routes by Host header)
```

Traefik routes by `Host` header — all sites on port 443, no conflicts:

```yaml
traefik.http.routers.ocoron-com.rule=Host(`ocoron.com`)
traefik.http.routers.newsite-com.rule=Host(`newsite.com`)
```

Each site gets:

- **Isolated named volumes** — `ocoron-com_wp_content`, `ocoron-com_db_data`
- **Isolated `.env`** — separate DB credentials, WP admin password, GA4 ID
- **Isolated `site.yaml`** — the spec driving `fabrik wp apply`

`fabrik-api` calls `docker exec ocoron-com-wordpress-1 wp ...` and `docker exec newsite-com-wordpress-1 wp ...` by name per site.

---

## Network Security Model

**Defense-in-depth: two independent security layers.**

**Layer 1 — Network isolation:** `fabrik-api` binds `127.0.0.1:8050` exclusively. The port is never exposed on a public interface. Traefik never sees it. Only processes on the VPS host can reach it.

**Layer 2 — Application authentication:** All requests require `Authorization: Bearer <FABRIK_API_TOKEN>`. Even if another container on the VPS is compromised and somehow reaches `127.0.0.1:8050`, it cannot fire deployments without the token.

**Container → host bridge:** The Next.js container reaches the host via `host.docker.internal:host-gateway`:

```yaml
# In fabrik-control-plane compose.yaml
extra_hosts:
  - "host.docker.internal:host-gateway"
```

```bash
# In fabrik-control-plane .env
FABRIK_API_URL=http://host.docker.internal:8050
FABRIK_API_TOKEN=<32-char CSPRNG>
```

The Kilo AI API key (`KILO_API_KEY`) lives only in Next.js server-side env. It is used exclusively in Server Components and API routes — never passed to the browser.

---

## Architecture

```text
Browser
  └─ fabrik-control-plane (Next.js 14, port 3004, Coolify container)
       ├─ /chat         Kilo AI conversation (negotiation + compilation)
       ├─ /deploy       JSON review + Approve & Deploy button
       └─ /status       SSE stream — live stage progress
            │
            │  POST /api/v1/deploy/plan   (Bearer token)
            │  GET  /api/v1/deploy/stream/{task_id}
            ▼
       fabrik-api (FastAPI, port 8050, native VPS host process)
            ├─ Writes site.yaml → /opt/<site>/
            ├─ Runs: fabrik wp plan <site> && fabrik wp apply <site>
            └─ Streams stdout as SSE JSON events
                 │
                 ▼  docker exec (local, no SSH hop)
            ocoron-com-wordpress-1
            newsite-com-wordpress-1
            ...
```

**Network security:**

- `fabrik-api` binds `127.0.0.1:8050` only — not reachable from the internet
- All API calls require `Authorization: Bearer <FABRIK_API_TOKEN>`
- Next.js container reaches host via `host.docker.internal:host-gateway`
- Kilo AI API key lives in Next.js env, never exposed to browser (Server Component calls only)

---

## Key Invariants

1. **Manual sign-off is mandatory** — no auto-fire on JSON compilation. Every deploy requires the "Approve & Deploy" button click.
2. **fabrik-api crashes on startup if `FABRIK_API_TOKEN` is missing** — no silent degradation to unauthenticated state.
3. **`FABRIK_EXEC_MODE=local` drops the SSH hop** — `docker exec` runs directly on the host. Setting `FABRIK_EXEC_MODE=ssh` (default for WSL) uses `ssh vps sudo docker exec ...`.
4. **fabrik-api is not containerized** — runs as a native process on the VPS host so it can call `docker exec` without socket exposure.
5. **All Kilo AI calls happen server-side** — API key never reaches the browser.
6. **SSE events are structured JSON, not raw text** — frontend drops them directly into React state without regex parsing.
7. **Traefik labels for Coolify-managed apps are declared explicitly, never auto-relied** — every compose emitted by Fabrik must contain the full label set (`enable`, rule, entrypoints, tls, certresolver, service-port, and middlewares where applicable). Coolify's runtime label injection is non-deterministic after `PATCH /services/{uuid}` and breaks routers. See `LESSONS_LEARNT.md §8.7`.
8. **Authelia protection requires BOTH the policy rule AND the Traefik middleware** — an `access_control` rule in `/config/configuration.yml` alone does not gate a host; Traefik must also attach `authelia-forward@docker` to that router. For every `shape.is_admin_dashboard=true` deploy, Fabrik MUST write both. See `LESSONS_LEARNT.md §8.9`.
9. **Compose source-of-truth depends on `build_pack` + `git_repository`** — for `build_pack=dockercompose` apps WITH a `git_repository` set, the upstream repo wins; `PATCH /applications/{uuid}.docker_compose_raw` is silently overwritten on the next deploy. The Fabrik orchestrator MUST branch on this: git-sourced → push to repo + `/deploy`; pure Coolify service → `PATCH /services/{uuid}`. See `LESSONS_LEARNT.md §8.10`.
10. **Authelia must bypass any Bearer-token API path on an admin dashboard's domain** — forward-auth on `example.vps1.ocoron.com/*` gates `/api/*` too, returning HTTP 401 to Bearer-token callers (e.g., Fabrik→Coolify, Fabrik→Grafana). For every admin dashboard with a programmatic API, Fabrik MUST add a `^/api/` bypass rule in `configuration.yml` before the catch-all `two_factor` policy. See `LESSONS_LEARNT.md §8.11`.

---

## Failure Modes

| Scenario | Symptom | Resolution |
| --- | --- | --- |
| `FABRIK_API_TOKEN` not set | fabrik-api crashes at startup with `ValueError` | Set token in VPS `/opt/fabrik-api/.env` |
| `FABRIK_EXEC_MODE` not set to `local` | `ssh: Could not resolve hostname vps` | Set `FABRIK_EXEC_MODE=local` on VPS |
| Next.js can't reach `host.docker.internal` | `ECONNREFUSED` on deploy POST | Verify `extra_hosts` in compose.yaml |
| Kilo AI returns malformed JSON spec | Plan route rejects payload, returns 422 with validation errors | UI shows error inline, user re-negotiates |
| fabrik wp apply stage fails mid-run | SSE emits `{"event": "stage_failed", "stage": "plugins", ...}` | UI shows failed stage, user runs `--force-stage` via API |
| Kilo omits required compliance field | Pydantic `ValidationError` on `POST /plan`, 422 response | UI prompts user to confirm missing field (table_prefix, backup bucket, etc.) |
| VPS host process dies | fabrik-api 502 from Next.js | Systemd unit restarts it; add Uptime Kuma TCP monitor on port 8050 |

---

## Acceptance Criteria

- [ ] `curl -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8050/health` returns `{"status": "ok"}`
- [ ] `fabrik-api` rejects requests without valid Bearer token with 401
- [ ] `POST /api/v1/deploy/plan` with valid site JSON returns `{"task_id": "...", "status": "queued"}` in < 200ms
- [ ] `GET /api/v1/deploy/stream/{task_id}` streams SSE events, one JSON object per line
- [ ] Full `fabrik wp apply` run for a test site streams all 12 stage events to the SSE client
- [ ] Next.js chat UI renders Kilo AI responses in real-time (streaming)
- [ ] Approve & Deploy button fires `POST /api/v1/deploy/plan` and immediately opens SSE stream
- [ ] Each stage appears in the UI as it starts and completes, with duration
- [ ] `FABRIK_EXEC_MODE=local` confirmed working: `docker exec` reaches WP container without SSH
- [ ] Written `site.yaml` contains all compliance fields: `security.table_prefix` ≠ `wp_`, `backup.duplicati.enabled: true`, `monitoring.wp_cron_ping_url` set, `post_deploy.browserless_screenshot: true`
- [ ] All created files and folders must use kebab-case naming. Exceptions: README.md, CHANGELOG.md, AGENTS.md, Dockerfile, Makefile, migration files.

---

## Phase 1 — `fabrik-api` (FastAPI bridge)

### SSH Bypass — Both Classes

Two changes needed in `/opt/fabrik/src/fabrik/drivers/wordpress.py`, both gated on `FABRIK_EXEC_MODE`:

**Change 1 — `WordPressClient._exec()`:** Drop SSH prefix, call `docker exec` directly.

**Change 2 — `ContainerResolver.resolve()`:** Drop SSH prefix for `docker ps` call, OR pre-set `WP_CONTAINER_NAME_<SLUG>` env vars in `/opt/fabrik-api/.env` (recommended — zero code change to resolver).

### fabrik-api project structure

```text
/opt/fabrik-api/
├── src/fabrik_api/
│   ├── __init__.py
│   ├── main.py           ← app factory, auth middleware, uvicorn entrypoint
│   ├── config.py         ← function-level env loading (no class-level config)
│   ├── auth.py           ← Bearer token dependency
│   ├── routes/
│   │   ├── health.py     ← GET /health
│   │   └── deploy.py     ← POST /api/v1/deploy/plan + GET /api/v1/deploy/stream/{id}
│   ├── tasks.py          ← background task runner, asyncio queue → SSE
│   └── spec_writer.py    ← validated JSON payload → site.yaml file writer
├── tests/
│   └── test_deploy.py
├── pyproject.toml
├── .env.example
├── README.md
└── project.yaml
```

### API contract

**`POST /api/v1/deploy/plan`**

Request body (JSON generated by Kilo AI, validated by Pydantic):

```json
{
  "domain": "newsite.com",
  "preset": "company",
  "brand": {"name": "New Site", "tagline": "Tagline here", "primary_color": "#2563EB"},
  "contact": {"email": "hello@newsite.com", "phone": "+905001234567"},
  "services": [{"slug": "consulting", "name": {"en_US": "Consulting"}, "summary": {"en_US": "..."}}],
  "plugins": {"add": ["shortpixel-image-optimiser"]},
  "security": {
    "table_prefix": "newsite_prod_",
    "brute_force_lockout_attempts": 5,
    "block_admin_username": true,
    "two_factor_roles": ["administrator", "editor"],
    "cloudflare_waf": true,
    "cron_method": "uptime_kuma"
  },
  "seo": {
    "meta_description": "...",
    "og_enabled": true,
    "rankmath": {
      "modules_enable": ["acf", "image-seo", "instant-indexing", "redirections", "rich-snippet", "sitemap"],
      "modules_disable": ["analytics", "link-counter", "amp", "bbpress", "buddypress"]
    }
  },
  "backup": {
    "destination": "b2",
    "duplicati": {
      "enabled": true,
      "volumes": ["newsite-com_wp_content", "newsite-com_db_data"],
      "bucket": "newsite-com-backup",
      "encryption": "aes256",
      "schedule": "0 3 * * *"
    }
  },
  "post_deploy": {
    "setup_bing": true,
    "setup_indexnow": true,
    "setup_ga4": false,
    "gsc_verification_method": "dns_txt",
    "browserless_screenshot": true
  },
  "monitoring": {
    "uptime_kuma": {
      "enabled": true,
      "interval": 60,
      "wp_cron_ping_url": "https://newsite.com/wp-cron.php?doing_wp_cron",
      "wp_cron_interval": 300
    }
  }
}
```

Response:

```json
{"task_id": "uuid4", "status": "queued", "site_yaml_path": "/opt/newsite.com/site.yaml"}
```

**`GET /api/v1/deploy/stream/{task_id}`** — `text/event-stream`

```text
data: {"event": "stage_start", "stage": "dns", "index": 1, "total": 12}
data: {"event": "log", "stage": "dns", "line": "Checking A record for newsite.com..."}
data: {"event": "stage_done", "stage": "dns", "status": "success", "duration_ms": 1240}
data: {"event": "stage_start", "stage": "settings", "index": 2, "total": 12}
...
data: {"event": "complete", "overall_success": true, "duration_ms": 142000}
```

### SSH bypass implementation

In `src/fabrik_api/config.py` (local copy — `fabrik-api` does not import from the `fabrik` package):

```python
def get_exec_mode() -> str:
    return os.getenv("FABRIK_EXEC_MODE", "ssh")  # "local" on VPS, "ssh" on WSL
```

In `WordPressClient._exec()` — one-line change gated on env var:

```python
if get_exec_mode() == "local":
    full_cmd = ["sudo", "docker", "exec", shlex.quote(self.site.container),
                "wp", *wp_command.split(), root_flag]
else:
    full_cmd = ["ssh", self.ssh_host, cmd]
```

This change lives in `/opt/fabrik/src/fabrik/drivers/wordpress.py` — one targeted edit, no refactor.

### Token + Binding Config

- `FABRIK_API_TOKEN` — 32-char CSPRNG, generated at setup, stored in `/opt/fabrik-api/.env`
- `auth.py` dependency raises `HTTPException(401)` on missing/invalid token
- Applied to all routes except `/health`
- Uvicorn binds `host="127.0.0.1"` — hardcoded in `main.py`, not configurable via env

### Deployment (native VPS process)

```bash
# On VPS
cd /opt/fabrik-api
python3 -m venv .venv
.venv/bin/pip install -e ".[prod]"

# systemd unit: /etc/systemd/system/fabrik-api.service
[Unit]
Description=Fabrik API Bridge
After=network.target docker.service

[Service]
User=ozgur
WorkingDirectory=/opt/fabrik-api
EnvironmentFile=/opt/fabrik-api/.env
ExecStart=/opt/fabrik-api/.venv/bin/uvicorn fabrik_api.main:app --host 127.0.0.1 --port 8050
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

---

## Phase 2 — `fabrik-control-plane` (Next.js 14)

> **Deployment invariants** — this project IS an admin dashboard with a Bearer-token API (`fabrik-api` at `/api/v1/*`), so its own Coolify deployment MUST satisfy all four 2026-04-18 invariants from the top of this document:
>
> - **§7 Full Traefik label set** in its compose (don't rely on Coolify auto-inject).
> - **§8 Authelia policy rule + `authelia-forward@docker` middleware** — write both, not just one.
> - **§9 Compose source-of-truth:** if deployed via `git_repository`, compose changes go through the Git repo; Coolify API PATCH is silently reverted.
> - **§10 `^/api/` Authelia bypass** on `control.vps1.ocoron.com` so Next.js can call `fabrik-api` with Bearer tokens without the 2FA gate intercepting the API traffic.
>
> These are the same invariants enforced by the zero-touch plan (`2026-04-18-zero-touch-deployment.md` CSFs §7–§10). A post-deploy `verify.py` run against this project is the single source of truth that all four are satisfied.

### fabrik-control-plane project structure

```text
/opt/fabrik-control-plane/
├── src/app/
│   ├── layout.tsx
│   ├── page.tsx            ← redirect to /chat
│   ├── chat/
│   │   └── page.tsx        ← Kilo AI conversation UI
│   ├── deploy/
│   │   └── page.tsx        ← JSON spec review + Approve & Deploy button
│   └── api/
│       ├── chat/
│       │   └── route.ts    ← Server: proxies to Kilo AI (key hidden)
│       └── deploy/
│           ├── plan/
│           │   └── route.ts   ← Server: POSTs to fabrik-api
│           └── stream/
│               └── [taskId]/
│                   └── route.ts  ← Server: proxies SSE from fabrik-api
├── src/components/
│   ├── ChatWindow.tsx      ← message list + input
│   ├── SpecPreview.tsx     ← JSON diff viewer, approve button
│   └── DeployStream.tsx    ← SSE consumer, animated stage checklist
├── compose.yaml            ← Coolify-managed, extra_hosts: host.docker.internal
├── .env.example
└── project.yaml
```

### Admin Credential UX — Phase B compilation requirement

During the **Phase B compilation** step (when Kilo AI outputs the final JSON spec), the UI **must**:

1. **Auto-generate WP admin password** using CSPRNG (32 chars, `[a-zA-Z0-9]`) — never ask the user to type one
2. **Show the password prominently** in a copyable field with a "Save this now — it will not be shown again" warning before the Approve & Deploy button becomes clickable
3. **Collect admin email** from the user as an explicit input field in the chat negotiation phase (e.g. "What email should be used for the WordPress admin account?")
4. **Admin username** comes from spec `security.admin_username` (Kilo AI sets it, never `admin`)

```typescript
// In spec_writer / Phase B compilation:
const adminPassword = generateCsprng(32); // crypto.randomBytes based
const adminEmail = collectedFromUser;     // required chat field

// Show in UI before approve:
<PasswordReveal password={adminPassword} label="WordPress Admin Password" />
<Warning>Save this password now — it cannot be recovered after deployment.</Warning>
```

**`fabrik-api` receives** `admin_password` in the deploy payload (treated as a secret, never logged). It writes `WP_ADMIN_PASSWORD` to the site-specific `.env` on VPS, not to the shared `/opt/fabrik/.env`.

**Why not store in Fabrik .env:** Each site gets its own credentials. The shared `.env` is for platform-level secrets (Coolify token, R2 keys, etc.), not per-site WP passwords. Future: store in a secrets vault keyed by domain.

### Kilo AI system prompt (stored server-side, never in browser)

The system prompt gives Kilo full awareness of the Fabrik infrastructure:

- All available presets (`company`, `saas`, `content`, `landing`, `ecommerce`)
- All available plugins and their config keys (drawn from `templates/wordpress/defaults.yaml` base stack)
- All `post_deploy` flags and their effects: `setup_bing`, `setup_indexnow`, `setup_ga4`, `gsc_verification_method` (always `dns_txt`), `browserless_screenshot` (always `true` before go-live)
- **Security hardening fields** (mandatory, 62-wordpress.md): `table_prefix` (never `wp_`, pattern `<slug>_prod_`), `brute_force_lockout_attempts: 5`, `block_admin_username: true`, `two_factor_roles: [administrator, editor]`, `cloudflare_waf: true`, `cron_method: uptime_kuma`
- **RankMath module lists** (62-wordpress.md §Plugin): enable `acf, image-seo, instant-indexing, redirections, rich-snippet, sitemap`; disable `analytics, link-counter, amp, bbpress, buddypress`
- **Backup fields**: `destination: b2`, `duplicati.volumes` naming convention (`<name>_wp_content`, `<name>_db_data`), `bucket` pattern (`<domain-slug>-backup`), encryption AES-256, schedule `0 3 * * *`
- **Monitoring fields** (nested under `monitoring.uptime_kuma`): `wp_cron_ping_url` pattern (`https://<domain>/wp-cron.php?doing_wp_cron`), `wp_cron_interval: 300`, `interval: 60`
- The exact JSON schema it must output when the user says "approve" or "build it" — see §API contract above
- Instruction to switch to JSON-only output mode on compilation trigger; no prose, no markdown, only the raw JSON object

### Compose config (key excerpt)

```yaml
services:
  fabrik-control-plane:
    image: node:22-bookworm-slim
    platform: linux/amd64
    extra_hosts:
      - "host.docker.internal:host-gateway"
    environment:
      FABRIK_API_URL: http://host.docker.internal:8050
      FABRIK_API_TOKEN: ${FABRIK_API_TOKEN}
      KILO_API_KEY: ${KILO_API_KEY}
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.control-plane.rule=Host(`control.vps1.ocoron.com`)"
      - "traefik.http.routers.control-plane.entrypoints=websecure"
      - "traefik.http.routers.control-plane.tls.certresolver=letsencrypt"
```

---

## Phase 3 — Wire SSH bypass into fabrik ✅ COMPLETE

**File:** `/opt/fabrik/src/fabrik/drivers/wordpress.py`

Both changes are implemented and verified:

1. `WordPressClient._exec()` — `FABRIK_EXEC_MODE=local` path drops SSH hop, calls `docker exec` directly
2. `ContainerResolver.resolve()` — `FABRIK_EXEC_MODE=local` path runs `docker ps` directly; `WP_CONTAINER_NAME_<SLUG>` env var skips resolver entirely (recommended for production)

Zero impact on existing WSL workflow (default remains `ssh`). See `src/fabrik/drivers/wordpress.py`.

---

## Execution Order

```text
Phase 0:   ✅ All pipeline code gaps closed — DONE (2026-04-14)
           Gap 1: seo.py — archives_noindex, breadcrumbs, og_enabled, robots_txt, sitemap, schema all implemented
           Gap 2: stages/monitoring.py — created, registered in deployer.py
           Gap 3: stages/post_deploy.py — created, registered in deployer.py
           Gap 4: Stage order fixed — seo → post_deploy → analytics → monitoring → verify
           Gap 5: forms.py — reads contact.form.fields from spec
           Gap 8: settings.py — reads security.admin_username, renames from 'admin'
           Gap 9: Makefile.wordpress — created in templates/scaffold/docker/
           Gap 12: planner.py STAGE_KEYS — post_deploy + monitoring added

Phase 3:   ✅ FABRIK_EXEC_MODE patch in wordpress.py — DONE

Phase 1a:  Scaffold /opt/fabrik-api — pyproject.toml, main.py, config.py, auth.py
Phase 1b:  Implement routes/health.py + routes/deploy.py + tasks.py + spec_writer.py
           spec_writer.py must handle full compliance schema:
           security.table_prefix, seo.rankmath modules, backup.duplicati,
           post_deploy.gsc_verification_method, post_deploy.browserless_screenshot,
           monitoring.wp_cron_ping_url, monitoring.wp_cron_interval
Phase 1c:  Write tests/test_deploy.py
Phase 1d:  Install on VPS, create systemd unit, verify with curl
Phase 1e:  Add Uptime Kuma TCP monitor for port 8050

Phase 2a:  Scaffold /opt/fabrik-control-plane — Next.js 14 App Router
Phase 2b:  Implement server-side Kilo AI chat route (system prompt includes full compliance schema)
Phase 2c:  Build ChatWindow, SpecPreview, DeployStream components
Phase 2d:  Wire API routes (plan POST + stream GET proxy)
Phase 2e:  Deploy to Coolify, verify SSE stream end-to-end
```

---

## Lessons Learned — ocoron.com Reference Deployment (2026-04-14 to 2026-04-15)

These constraints were discovered during the first real pipeline run and must be encoded into all future site deployments via `fabrik-api` and `provisioner.py`.

**Total fixes: 50+ issues resolved across infrastructure, WordPress core, pages, REST API, SEO, plugins, monitoring, verify stage, error handling, VPS deployment, and root cause analysis.**

### Summary of All Fixes (2026-04-13 to 2026-04-15)

**Infrastructure & Docker:**
- `compose-coolify.yaml.j2` mounts full web root → Fixed to mount only `wp_html` volume
- nginx FastCGI cache uses `/tmp/wp_cache` → Fixed to use `/var/cache/nginx/wp_cache`
- nginx+FPM requires shared `/var/www/html` volume → Fixed with `wp_html` volume
- PHP-FPM IPv6-only binding breaks nginx upstream → Fixed with FPM override config
- Docker DNS collision with service name `wordpress` → Fixed to use full container name
- WP-CLI missing in php8.3-fpm container → Fixed by installing WP-CLI manually

**WordPress Core & Settings:**
- Pipeline assumes WP core is installed → Fixed with auto-install check in settings stage
- `user_login` is immutable in WordPress → Fixed with create-new-user workflow
- Admin username `admin` never renamed → Fixed with user replacement logic
- Duplicate `contact:` top-level key in `site.yaml.j2` → Fixed YAML structure
- Wrong plugin slugs in `defaults.yaml` → Fixed plugin slugs to match wordpress.org

**Pages & Content:**
- Homepage creation fails with large HTML content → Fixed with temporary file + `wp post update`
- Revert status=publish,draft query → Fixed to avoid 400 error
- WP-CLI invalid page template error → Fixed with retry without template
- Pages stage hang (DNSClient sitemap resubmit) → Fixed with daemon thread timeout
- Homepage not created (empty slug issue) → Fixed to check both '' and 'home' slugs
- Homepage not set as static front page → Fixed with set_homepage logic
- Rewrite rules not flushed → Added rewrite_flush after set_homepage

**REST API & Authentication:**
- 401 Unauthorized — missing HTTP_AUTHORIZATION → Fixed nginx template
- 401 — Application Password not quoted → Fixed .env quoting
- Generate WordPress Application Password → Fixed with app password generation
- WP-CLI fallback in PageCreator → Implemented for page creation
- ContainerResolver naming convention → Fixed to match Docker Compose
- Pages 401 Unauthorized — fallback to 'admin' → Fixed username fallback logic

**SEO & Schema:**
- `seo.py`: 5 spec keys read nowhere → Implemented missing SEO methods
- SEO stage crashes on mixed i18n `default_meta` → Fixed isinstance guard
- SEO — isinstance guard in _merge_option → Fixed json.loads result
- SEO — isinstance guard for robots_txt → Fixed apply_site_seo
- SEO 'str object is not a mapping' → Fixed add_schema_markup method
- configure_sitemap() never called → Fixed to call in seo stage
- add_schema_markup() was stub → Implemented LocalBusiness JSON-LD

**Plugins & Languages:**
- Polylang not auto-injected for multilingual sites → Fixed in spec_loader.py
- Polylang injection timing → Fixed direct injection into plugins.base
- Wordfence whitelist config variable → Fixed to use DB (wfConfig option)
- Add Wordfence whitelist for VPS IP → Implemented in plugins.py
- Disable Wordfence rate limiting → Implemented as direct fix
- No active form plugin detected → Handled with skip logic

**Monitoring & Analytics:**
- `stages/monitoring.py` does not exist → Created monitoring stage
- uptime-kuma-api missing from dependencies → Added to pyproject.toml
- Uptime Kuma socketio timeout → Fixed with timeout increase
- `stages/post_deploy.py` does not exist → Created post_deploy stage
- GA4 measurement ID feedback loop → Fixed stage order
- STAGE_KEYS missing new stages → Added post_deploy + monitoring

**Verify Stage:**
- Cloudflare rate limiting in verify stage → Fixed with increased delay (2s → 5s)
- Add delay between URL checks → Implemented 1-second delay (later increased to 5s)
- Verify 404 homepage → Fixed homepage creation
- Verify 429 rate limit → Fixed with Cloudflare delay

**Forms & Contact:**
- Forms field structure mismatch → Documented workaround
- admin email conflict → Fixed by changing to old-admin@ocoron.com
- Move admin email to .env → Implemented with conflict detection

**Error Handling & Logging:**
- create_page() hides REST failure → Fixed with better error logging (exc_info=True)
- create_page_cli() large content failure → Fixed with temporary file approach
- Broad except clauses → Fixed with specific exception handling

**VPS & Deployment:**
- Restart VPS compose stack → Implemented to pick up config changes
- Update nginx config directly on VPS → Applied manual config fix
- Apply WP-CLI fix to VPS compose → Recreated container with fix
- Manual homepage creation on VPS → Direct fix to unblock pipeline
- Manual Wordfence disable → Direct fix to unblock pipeline
- Manual rewrite rules flush → Direct fix to unblock pipeline

**Consultations & Root Cause:**
- 4 AI consultations (Claude Opus, GPT-4o, Claude Sonnet, GPT-5.4) → Used to identify root causes
- Root cause: find_page("") returns ALL pages → Fixed empty slug handling
- Root cause: create_page_cli() shell argument limit → Fixed with file-based approach
- Root cause: Cloudflare rate limiting → Fixed with increased delays

---

### 1. Coolify API — compose constraints

| Constraint | Impact | Fix applied |
|---|---|---|
| `docker_compose_raw` must be base64-encoded ASCII | 422 validation error on service create | Encode before POST; strip non-ASCII from compose |
| `WORDPRESS_CONFIG_EXTRA` multiline block | SQL varchar(255) overflow, 500 error | Removed from compose env; apply via WP-CLI post-install |
| Relative bind mounts (`./nginx/...`) | Container exits instantly — path resolves to Coolify workdir | Use absolute paths (`/opt/<site>/nginx/...`) in all bind mounts |
| `build_pack` field disallowed on `/applications/dockercompose` | 422 validation | Never send `build_pack` in dockercompose payload |
| Coolify `/start` endpoint is `GET` not `POST` | Silent no-op when called with POST | Always use `GET /api/v1/services/{uuid}/start` |
| `storages` API endpoint (`POST /api/v1/services/{uuid}/storages`) | 404 — not implemented in this Coolify version | Use absolute bind mount paths instead |

### 2. WordPress image — always use `-apache`, never `-fpm`

`wordpress:php8.3-fpm` has no WP-CLI. The entire pipeline relies on `wp` CLI inside the container.

- **Always use:** `wordpress:php8.3-apache` in `compose-coolify.yaml.j2`
- **Template fixed:** `compose-coolify.yaml.j2` updated 2026-04-14
- **Note:** With `-apache`, nginx is still used as a reverse proxy in front (nginx handles TLS termination + Traefik labels; Apache handles PHP inside the `wordpress` container on port 80 internal). This is intentional.

### 3. Site-provisioner access from WSL

`dns.vps1.ocoron.com` has a Traefik IP allowlist middleware. WSL's NAT IP is not in it. Direct HTTPS calls from WSL return 403.

**Pattern for all Fabrik drivers calling VPS-internal services:**

```python
# In driver __init__:
self._internal_url = os.getenv("SITE_PROVISIONER_INTERNAL_URL")
# When set, proxy requests through SSH to the container's Docker IP

# .env:
SITE_PROVISIONER_INTERNAL_URL=http://10.0.1.30:8001
```

`10.0.1.30` is the site-provisioner container's IP on the `coolify` network. Find it via:
```bash
ssh vps "sudo docker inspect <container> | python3 -c \"import sys,json; d=json.load(sys.stdin); print(d[0]['NetworkSettings']['Networks']['coolify']['IPAddress'])\""
```

**`fabrik-api` on VPS host** does not have this problem — it calls Docker IPs directly without Traefik. No SSH proxy needed.

### 4. Docker permissions on VPS

VPS user `ozgur` is not in the `docker` group. All `docker` commands require `sudo`.

- **`drivers/wordpress.py` `ContainerResolver`:** Fixed to use `sudo docker ps` 2026-04-14
- **`drivers/wordpress.py` `WordPressClient._exec()`:** Already uses `sudo docker exec` via SSH
- **`fabrik-api` on VPS:** Runs as `ozgur` — must prefix all `docker` calls with `sudo`

### 5. Plugin slugs must match wordpress.org exactly (Gap 15)

`defaults.yaml` had `generatepress` in `plugins.base` — but it's a **theme**, not a plugin. Also `rank-math-seo` is wrong; the real slug is `seo-by-rank-math`. `gp-premium` is premium-only (not on wordpress.org).

**`fabrik-api` implication:** The Phase B compilation (Kilo AI JSON) must reference correct wordpress.org slugs. Add a validation step in `spec_writer.py` that verifies each plugin slug against a known-good list or queries the wordpress.org API before writing `site.yaml`.

### 6. WordPress `user_login` is immutable (Gap 16)

`wp user update --user_login=...` silently fails. WordPress does not allow renaming `user_login`.

**Pattern for admin replacement:**
```bash
wp user create <new_admin> <email> --role=administrator --user_pass=<pass>
wp user delete 1 --reassign=<new_id> --yes
```

**`fabrik-api` implication:** The `wp core install` step should create the admin with the correct username from the start (never use `admin`). This eliminates the need for the replacement dance entirely.

### 7. WP core install is a pipeline prerequisite (Gap 14)

Fresh Docker volumes = empty MariaDB = no WP tables. The pipeline calls WP-CLI immediately in `settings` stage without checking if WP is installed. Error: `The site you have requested is not installed`.

**Resolution for `fabrik-api`:** Before calling `fabrik wp apply`, run `wp core install` programmatically using spec values. Add this as a pre-apply step in `spec_writer.py` or as an auto-check at the top of `stages/settings.py`.

```python
# Top of stages/settings.py apply():
if not wp.is_installed():
    wp.core_install(
        url=spec["site"]["url"],
        title=spec["brand"]["name"],
        admin_user=spec["security"]["admin_username"],
        admin_password=os.getenv("WP_ADMIN_PASSWORD"),
        admin_email=spec["contact"]["email"],
    )
```

### 8. nginx+FPM requires shared `/var/www/html` volume (Gap 17)

The compose template only shared `wp_content:/var/www/html/wp-content`. Nginx needs the **full WordPress root** (`index.php`, `wp-admin/`, `wp-includes/`) to serve static assets and pass PHP files via `try_files $uri =404`.

Without the full root, nginx returns 403 on every request because `index.php` doesn't exist on its filesystem.

**Fix:** Replace `wp_content` volume with `wp_html` volume mapping to `/var/www/html` on both `wordpress` (read-write) and `nginx` (read-only). Backup container mounts same volume for content access.

**Compose template implication:** `compose-coolify.yaml.j2` must always use a shared `wp_html` volume, never separate `wp_content`.

### 9. PHP-FPM IPv6-only binding breaks nginx upstream (Gap 18)

Modern `wordpress:php8.3-fpm` images bind FPM to `[::]:9000` (IPv6 only). Docker's internal DNS resolves service names to IPv4 addresses. Nginx connects to `fastcgi://10.x.x.x:9000` (IPv4), but FPM only listens on IPv6 → **502 Bad Gateway**.

**Fix:** Mount a PHP-FPM config override that forces IPv4 binding:

```ini
# /usr/local/etc/php-fpm.d/zz-fabrik-listen.conf
[www]
listen = 0.0.0.0:9000
```

Prefix `zz-` ensures it loads last and overrides `zz-docker.conf`. Mount via compose volume from host file or Coolify File Storage.

### 10. Docker DNS collision with bare service name `wordpress` (Gap 18a)

Nginx on the `coolify` external network resolved `wordpress` to `wp-test-wordpress` (a different compose project's container) instead of `ocoron-com-wordpress-1`. Docker DNS returns results from ALL networks a container is connected to.

**`fabrik-api` implication:** The nginx config template must use the **full container name** (`{{ name }}-wordpress-1`) instead of the bare compose service name (`wordpress`). Combined with `resolver 127.0.0.11 ipv6=off;` and variable-based `fastcgi_pass $upstream_fpm:9000;`.

### 11. SEO stage crashes on mixed i18n `default_meta` (Gap 20)

`seo.default_meta` in specs mixes flat string keys (`description: "{{brand.tagline}}"`) with locale dicts (`en_US: {...}`). The fallback `next(iter(values))` returns a string, then `.get()` fails.

**`fabrik-api` implication:** `spec_writer.py` should normalize `default_meta` to a clean locale-dict-only structure during Phase B compilation. Never mix flat strings and locale dicts in the same dict.

### 12. Polylang auto-injection for multilingual sites (Gap 19)

When `languages.additional` is set, the languages stage requires Polylang. But it wasn't in `plugins.base` (not needed for monolingual sites). Pipeline silently fails.

**`fabrik-api` implication:** The spec compilation must auto-add `polylang` to the plugin list when `languages.additional` is non-empty. This is now handled in `spec_loader.py:apply_plugin_rules()` but `spec_writer.py` should also enforce it.

### 13. Homepage creation fails with large HTML content (Gap 22) — **DISCOVERED 2026-04-15**

`PageCreator.create_page_cli()` passes full page content as a shell argument to WP-CLI: `f"--post_content={content}"`. For large homepage HTML (~10KB), this exceeds shell argument length limits and causes quoting failures. The page creation silently fails, homepage is never created.

**Fix:** Modified `create_page_cli()` to:
1. Create page without content first using `wp post create`
2. Write content to temporary file
3. Use `wp post update <id> --post_content=< <file>` to set content
4. Clean up temporary file

Also added better error logging in `create_page()` with `exc_info=True` to show full traceback when REST API fails.

**`fabrik-api` implication:** The spec compilation should warn if page content exceeds ~8KB. Split large pages into smaller chunks or use file-based content delivery.

### 14. Cloudflare rate limiting in verify stage (Gap 23) — **DISCOVERED 2026-04-15**

The verify stage checks 14 URLs with a 2-second delay between each check. Cloudflare's rate limiting triggers on the rapid succession of requests from the same IP, returning 429 Too Many Requests on later URLs (e.g., `/terms`).

**Fix:** Increased delay between URL checks from 2 seconds to 5 seconds in `stages/verify.py`. This gives Cloudflare more time between requests and avoids triggering rate limits.

**`fabrik-api` implication:** The verify stage should use exponential backoff instead of fixed delay. Start at 1s, double on each 429 response, max 30s. This adapts to Cloudflare's dynamic rate limits.

### 15. SEO methods all implemented (Gap 1) — **CORRECTED 2026-04-15**

Earlier plan document claimed `seo.py` had 5 missing methods. This was incorrect — all methods are implemented:
- `configure_sitemap()` — line 281-298
- `set_archives_noindex()` — line 300-329
- `set_breadcrumbs()` — line 331-349
- `set_open_graph()` — line 351-385
- `set_robots_txt_ai_crawlers()` — line 387-422
- `add_schema_markup()` — line 424-454 (injects LocalBusiness JSON-LD via RankMath)

**`fabrik-api` implication:** None — SEO stage is fully functional.

---

## Phase 4 — Zero-Touch Infrastructure Provisioning (moved)

> **Moved to its own plan:** `docs/development/plans/2026-04-18-zero-touch-deployment.md`
>
> Reason: this plan (`fabrik-control-plane.md`) is scoped to the **conversational UI + `fabrik-api` bridge** that fronts the WordPress 12-stage pipeline (Phases 0–3 above). The zero-touch auto-deployment of generic projects (PostgreSQL + Gatus + Backrest + GlitchTip + Grafana + Authelia + MeiliSearch drivers, `fabrik apply <project>`) is a separate, larger deliverable that was temporarily consolidated here during a 2026-04-18 doc-reorg pass. Keeping the two concerns in one file blurred the scope and made the title misleading. The zero-touch plan has been restored to its own file.

### What stays in THIS plan (Phases 0–3)

- `fabrik-api` FastAPI bridge that wraps the **WordPress** 12-stage flow (`fabrik wp apply`)
- Next.js `fabrik-control-plane` UI at `https://control.vps1.ocoron.com`
- Kilo-AI conversational negotiation → JSON spec → "Approve & Deploy" → SSE live progress
- The `FABRIK_EXEC_MODE` SSH-bypass switch and systemd deployment of `fabrik-api` on the VPS

### What moved out to `2026-04-18-zero-touch-deployment.md`

- Generic `fabrik apply <project>` orchestrator (non-WordPress projects)
- Drivers: `ssh.py`, `postgres.py`, `gatus.py`, `backrest.py`, `meilisearch.py`, `glitchtip.py`, `grafana.py`, `authelia.py`, `compose_updater.py`
- `InfrastructureProvisioner` orchestrator step 6a–6g
- Backrest config structure, volume topology, Traefik-restart CSF
- The 10 Critical Success Factors (§§1–6 original + §§7–10 added 2026-04-18 from `LESSONS_LEARNT.md §8.7–§8.11`)
- Migration Velocity appendix and service-config audit

### Cross-cutting invariants still enforced here

The Key Invariants §7–§10 at the top of this document remain applicable to the control-plane UI project itself, because the control-plane-UI is a Coolify-managed app that:

- Deploys behind Traefik → needs the full explicit label set (Invariant §7)
- Is an admin dashboard with 2FA → needs Authelia policy rule **and** `authelia-forward@docker` middleware (Invariant §8)
- Will likely be git-sourced on `build_pack=dockercompose` → compose updates must go via git push, not `docker_compose_raw` PATCH (Invariant §9)
- Exposes `fabrik-api` Bearer-token endpoints on the same host → Authelia must bypass `^/api/` (Invariant §10)

Phase 2 (the Next.js project) MUST follow all four when its own compose is authored.

See `2026-04-18-zero-touch-deployment.md` for the full driver specs and acceptance criteria that implement these invariants across all project types.

---

## Phase 5 — n8n Content Pipeline (Future, Not This Sprint)

Once `fabrik-api` and the control plane UI are running, the next natural extension is automated post-deploy content creation via n8n. This is the correct use case for n8n in this stack.

**Trigger:** After `fabrik wp apply` completes successfully, the SSE `{"event": "complete"}` event fires an n8n webhook.

**n8n workflow sequence:**

```text
1. SEOClient.register_site(domain) → get keyword brief
2. TCOClient.generate_from_brief(brief) → AI-generated page content packages
3. ImageBrokerClient.search(keywords) → fetch stock images per page
4. fabrik-api POST /api/v1/content/publish → push content to WordPress REST API
5. Apprise notification → "Content published for {domain}"
```

This separates concerns cleanly: WordPress pipeline (Python/`fabrik-api`) handles infrastructure, n8n handles the content orchestration event chain after site is live.

---

## One-Test Rule

**Test:** `POST /api/v1/deploy/plan` with a minimal valid spec → poll SSE stream → assert all 12 stage events received.

```text
Given:  fabrik-api running with FABRIK_EXEC_MODE=local, FABRIK_API_TOKEN set
        wp-test container running on VPS
When:   POST /api/v1/deploy/plan with {"domain": "wp-test.vps1.ocoron.com", "preset": "company", ...}
Then:   Response contains task_id
        GET /api/v1/deploy/stream/{task_id} emits exactly 12 stage_start events
        Final event is {"event": "complete", "overall_success": true}
Mocked: None — integration test against real wp-test container
Real:   WordPressClient + docker exec on VPS host
Why:    This test validates the entire bridge: auth → spec_writer → fabrik CLI → SSE stream.
        If this passes, the Next.js UI is trivial to wire. If it fails, the root cause
        (SSH bypass, docker exec perms, SSE buffering) is found before any frontend work.
```
