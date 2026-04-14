# Fabrik Control Plane — Implementation Plan

**Created:** 2026-04-13
**Status:** APPROVED — Phase 0 (pipeline gaps) COMPLETE · Phase 3 (SSH bypass) COMPLETE · Phase 1 + 2 pending
**Ports:** 8050 (`fabrik-api`) · 3004 (`fabrik-control-plane`)
**URL:** `https://control.vps1.ocoron.com`

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

**However:** n8n is the correct choice for the *content/SEO pipeline* in a future phase — hooking into `SEOClient`, `TCOClient`, and `ImageBrokerClient` for the automated content creation loop after a site deploys. That is Phase 4 (not in scope here).

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

## Phase 4 — n8n Content Pipeline (Future, Not This Sprint)

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
