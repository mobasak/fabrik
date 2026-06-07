# GlitchTip SDK Integration — Setup

**Last Updated:** 2026-06-06 (no change to SDK integration mechanics; aro-wake itself does NOT use the GlitchTip SDK today — its error reporting goes through Telegram via the alertmanager fallback path + `/var/log/aro-wake.log`. If a future iteration wants aro-wake errors in GlitchTip, the integration follows the standard scaffold pattern documented below.)
**Status:** ✅ Live (originally 2026-05-08; rewritten 2026-05-31 after Coolify removal + `coolify` → `fabrik` network rename + multi-host Wireguard mesh)
**Scaffold-emitted:** `glitchtip_init.py` / `glitchtip_init.js` per project
**Provisioner:** `/opt/fabrik/scripts/provision_glitchtip_project.sh`
**GlitchTip UI (Authelia-protected):** <https://errors.vps1.ocoron.com>
**Internal DSN host (Docker DNS on vps1 `fabrik` network):** `glitchtip-web:8000`
**Internal DSN host (over Wireguard mesh, for services on vps2/vps3):** `10.99.0.1:8000` (when exposed — see § Multi-host section)

---

## Goal

Every Fabrik service emitted by `fabrik scaffold` ships with a Sentry-SDK init module pointed at GlitchTip. When `SENTRY_DSN` (or fallback `GLITCHTIP_DSN`) is set in the service's `.env`, unhandled exceptions auto-report to GlitchTip with stacktrace, release tag, and environment label. When unset, the SDK is a zero-overhead no-op — services can be deployed without DSN configured and pay nothing for the integration.

## Env var name: `SENTRY_DSN` (primary) or `GLITCHTIP_DSN` (fallback)

GlitchTip is Sentry-API-compatible, so the SDK accepts either name. Fabrik's convention:

- **`SENTRY_DSN`** is the primary name — `fabrik apply`'s glitchtip registrar injects it automatically via the SSH deployer's `inject_env()` into the service's `/opt/<svc>/.env` on the VPS. See [`src/fabrik/orchestrator/infrastructure.py`](../../src/fabrik/orchestrator/infrastructure.py).
- **`GLITCHTIP_DSN`** is accepted as a fallback for backwards compatibility / manual provisioning.

The scaffold-emitted `glitchtip_init` module reads `SENTRY_DSN` first, falls back to `GLITCHTIP_DSN`. Either works; setting both is redundant but harmless.

This eliminates two failure modes:

1. **No error visibility** in production until someone reads logs (Loki) line by line.
2. **Per-service custom Sentry init** drift — wrong sample rates, wrong PII handling, missing release tags.

## Critical Detail — DSN host rewriting

The DSN returned by GlitchTip's `/api/0/projects/{org}/{project}/keys/` endpoint emits the configured public host (typically `localhost:8000` because GlitchTip's `GLITCHTIP_DOMAIN` is left internal). The provisioner **rewrites the host part of the DSN** to one of:

- **`glitchtip-web:8000`** — stable Docker DNS alias on the `fabrik` network. Used when the service runs on **vps1** alongside GlitchTip.
- **`10.99.0.1:8000`** — vps1's Wireguard mesh IP. Used when the service runs on **vps2/vps3** and must reach GlitchTip over the mesh.

Without this rewrite, services would either:

- Hit the public Authelia-protected URL and get 401 (the SDK doesn't auth)
- Need the public URL allowlisted in Authelia just for SDK ingestion (defeats the security boundary)
- Or hardcode `localhost:8000` which only works inside the GlitchTip container itself

## Prerequisites

- GlitchTip deployed via `fabrik apply specs/services/glitchtip.yaml` (web + worker containers + `glitchtip` DB on `postgres-main`).
- `glitchtip-web` reachable on the `fabrik` Docker network (vps1):

  ```bash
  ssh vps 'sudo docker run --rm --network fabrik curlimages/curl:latest -sS \
    -o /dev/null -w "HTTP %{http_code}\n" http://glitchtip-web:8000/api/0/'
  # Expected: HTTP 200
  ```

- A GlitchTip auth token with `project:write` scope, created via the GlitchTip UI under Settings → Auth Tokens.
- Three credentials in `/opt/fabrik/.env` (your WSL dev machine):

  ```text
  GLITCHTIP_AUTH_TOKEN=<bearer-token>
  GLITCHTIP_ORG_SLUG=<your-org-slug>
  GLITCHTIP_TEAM_SLUG=<your-team-slug>
  ```

## Reproducible Setup

### 1. Verify GlitchTip is reachable on the internal network

From WSL:

```bash
ssh vps 'sudo docker run --rm --network fabrik curlimages/curl:latest -sS \
  -o /dev/null -w "HTTP %{http_code}\n" http://glitchtip-web:8000/api/0/'
# Expected: HTTP 200
```

### 2. Provision a project + DSN

```bash
# Python service:
bash /opt/fabrik/scripts/provision_glitchtip_project.sh my-service

# Node service (sets project platform tag for proper symbolication):
bash /opt/fabrik/scripts/provision_glitchtip_project.sh my-service --platform javascript-node
```

The script:

- Auto-detects WSL and re-execs on VPS via SSH (bringing your `.env` creds with it)
- GETs the project; if 404, POSTs to create it
- Fetches the DSN via `/api/0/projects/{org}/{project}/keys/`
- Rewrites the host to `glitchtip-web:8000`
- Prints the final DSN on the **last line of stdout** (other output goes to stderr)

The script is idempotent: re-running for an existing project just refetches the DSN.

### 3. Inject the DSN into the service's `.env`

For services managed by `fabrik apply`, the **glitchtip registrar runs automatically** as part of `fabrik apply` and writes `SENTRY_DSN` + `GLITCHTIP_DSN` into the service's `/opt/<svc>/.env` on the VPS, then triggers `docker compose up -d` so the new env is picked up. No manual step required.

For manual injection (one-off, debug, or pre-registrar services):

```bash
# Use the SSH deployer's inject_env() pattern, or do it by hand:
ssh vps "sudo bash -c '
  cd /opt/my-service
  # backup current .env
  cp .env .env.bak-\$(date +%Y%m%d-%H%M%S)
  # append (or overwrite if already present)
  grep -q ^SENTRY_DSN= .env && \
    sed -i \"s|^SENTRY_DSN=.*|SENTRY_DSN=<dsn-from-step-2>|\" .env || \
    echo \"SENTRY_DSN=<dsn-from-step-2>\" >> .env
  docker compose up -d
'"
```

### 4. Verify ingestion

The cleanest end-to-end check is the project's `firstEvent` timestamp:

```bash
TOKEN=$(grep '^GLITCHTIP_AUTH_TOKEN=' /opt/fabrik/.env | cut -d= -f2-)
ORG=$(grep '^GLITCHTIP_ORG_SLUG=' /opt/fabrik/.env | cut -d= -f2-)

ssh vps "sudo docker run --rm --network fabrik curlimages/curl:latest -sS \
  -H 'Authorization: Bearer $TOKEN' \
  http://glitchtip-web:8000/api/0/projects/$ORG/my-service/" \
| python3 -c "import sys,json; d=json.load(sys.stdin); print('firstEvent:', d.get('firstEvent'), 'platform:', d.get('platform'))"
```

If `firstEvent` is `null`, no events have arrived yet. Trigger a deliberate exception in the deployed service and re-check (events appear within a few seconds).

## Multi-host (vps2 / vps3 spokes)

As of 2026-05-31, Fabrik runs on a 3-host Wireguard mesh (`10.99.0.0/24`). GlitchTip itself stays on vps1; services hosted on vps2/vps3 need a path to reach it over the mesh.

### Path A — services on vps1 (most cases today)

DSN host: `glitchtip-web:8000`. Same Docker network, fastest path. No change from single-host setup.

### Path B — services on vps2 / vps3

DSN host: `10.99.0.1:8000` over the mesh. The `glitchtip-web` container's port 8000 is bound to vps1's mesh IP — verified live: `LISTEN 0 4096 10.99.0.1:8000 0.0.0.0:* docker-proxy` (probe 2026-06-02). Spoke services use `SENTRY_DSN=http://<key>@10.99.0.1:8000/<project_id>` and ingest over Wireguard (private, no Authelia hop).

Since W14 (2026-06-02), the SSH deployer's `inject_env()` itself env-swaps `FABRIK_VPS_SSH_HOST` to `ctx.target_vps` for the duration of the call — so when the glitchtip registrar runs `inject_env(ctx, {"SENTRY_DSN": dsn})` for a spoke-deployed service, the DSN is written to `/opt/<svc>/.env` on the **spoke**, not on vps1. The DSN's mesh-IP host (`10.99.0.1:8000`) stays the same because the spoke container reaches glitchtip over the mesh.

### Path C — fallback, public URL

DSN host: `errors.vps1.ocoron.com` (port 443, HTTPS). Works from anywhere but goes through the public internet + Traefik. Authelia is bypassed for SDK ingestion paths (configured via the `*.vps1.ocoron.com` bypass rule for `/api/<num>/store/`). Slower + crosses trust boundaries. Avoid unless paths A/B aren't viable.

## How the Scaffold Wires It

The integration is emitted automatically by `fabrik scaffold <name> --type python-api|node-api`. No manual file copying needed.

### Python (`python-api`, `file-worker`)

Emitted files:

```text
src/{package}/glitchtip_init.py    # init_glitchtip() with FastApiIntegration + StarletteIntegration
src/{package}/main.py              # imports + calls init_glitchtip() BEFORE FastAPI()
requirements.txt                   # adds: sentry-sdk[fastapi]>=2.18.0
.env.example                       # adds: SENTRY_DSN= and ENVIRONMENT=production
```

Init signature: `init_glitchtip() -> bool` — returns `True` if init ran, `False` if no-op (DSN unset OR sentry-sdk not installed). Idempotent.

### Node (`node-api`, `file-api`)

Emitted files:

```text
src/glitchtip_init.js              # Sentry.init() from @sentry/node, no-op-on-missing-DSN
src/index.js                       # require('./glitchtip_init') at the top, BEFORE http.createServer
package.json                       # adds: "@sentry/node": "^8.40.0"
.env.example                       # adds: SENTRY_DSN= and ENVIRONMENT=production
```

The init module exports the configured Sentry instance (or `null` if no-op) so callers can do `const Sentry = require('./glitchtip_init')` and use it for manual `captureException` calls.

## Capture Discipline (rules for code authors)

When `SENTRY_DSN` is set, errors auto-report. Treat redundant logging as noise:

**DO NOT:**

- Wrap every `try/except` with `logger.exception()` followed by `raise` — the SDK already captures the re-raise.
- Log the full traceback string to Loki when GlitchTip will get it. Wastes Loki retention.
- Initialize Sentry SDK from a different code path. The scaffold's module is the single entry point.

**DO:**

- Use `logger.info("event_name", correlation_id=cid)` for context — the correlation_id appears as a tag on the GlitchTip event AND lets you grep Loki by request.
- Use `sentry_sdk.capture_exception(e)` (Python) / `Sentry.captureException(e)` (Node) ONLY for **caught-then-rethrown** flow — a worker loop where you catch to keep the worker alive, log the event, then continue.
- Set `ENVIRONMENT=staging` for staging deploys to filter prod vs staging in the GlitchTip UI.

## Environment Variables Reference

| Variable | Default | Notes |
| :--- | :--- | :--- |
| `SENTRY_DSN` | (unset → no-op) | Primary — injected by the glitchtip registrar |
| `GLITCHTIP_DSN` | (unset → no-op) | Fallback alias; SDK prefers `SENTRY_DSN` if both present |
| `ENVIRONMENT` | `production` | Tags events; filter prod vs staging in UI |
| `GIT_SHA` | (unset) | Release tag — set this in CI from `git rev-parse HEAD` |
| `GLITCHTIP_TRACES_SAMPLE_RATE` | `0.05` | Performance tracing sample rate (0.0–1.0). Keep low. |
| `GLITCHTIP_PROFILES_SAMPLE_RATE` | `0` | Profiling off by default (would require native deps) |

## Troubleshooting

### Symptom: events not appearing in GlitchTip UI

1. Check the service's actual env on the VPS — is `SENTRY_DSN` set and non-empty?

   ```bash
   ssh vps 'sudo cat /opt/<service>/.env | grep -E "^(SENTRY|GLITCHTIP)_DSN"'
   ```

2. From inside the container's network namespace, confirm reachability:

   ```bash
   ssh vps 'sudo docker exec <service-container> sh -c "curl -sS -o /dev/null -w \"%{http_code}\n\" http://glitchtip-web:8000/api/0/"'
   # Expect 200
   ```

3. Check the project's `firstEvent` via the API (see step 4 above).
4. Check the GlitchTip worker logs:

   ```bash
   ssh vps 'sudo docker logs --tail 50 glitchtip-worker'
   ```

   Celery rejection messages indicate ingestion errors (DSN mismatch, project quotas, etc.).

### Symptom: `Permission denied` from `/api/0/projects/{org}/{project}/issues/`

The auth token has `project:write` but not `event:read` scope. Either create a second token with `event:read` for query operations, or use the project's `firstEvent` field as the ingestion sentinel (it's exposed without the elevated scope).

### Symptom: provisioner errors with `unparseable DSN`

GlitchTip's DSN format changed between versions. Check the raw `keys/` response:

```bash
ssh vps "sudo docker run --rm --network fabrik curlimages/curl:latest -sS \
  -H 'Authorization: Bearer <token>' \
  http://glitchtip-web:8000/api/0/projects/<org>/<project>/keys/"
```

Update the regex in `provision_glitchtip_project.sh` step 2 if the format diverged.

### Symptom: services on vps2/vps3 can't reach `glitchtip-web:8000`

Docker DNS for `glitchtip-web` exists only on vps1's local `fabrik` network. Cross-VPS calls must use the mesh IP (`10.99.0.1:8000`). See § Multi-host above and ensure GlitchTip's compose binds port 8000 to `10.99.0.1`.

### Symptom: scaffold doesn't emit `glitchtip_init.py`

Ensure `/opt/fabrik` is on the new scaffold (post-2026-05-08 commit). Verify:

```bash
grep -c "glitchtip_init" /opt/fabrik/src/fabrik/scaffold.py
# Expected: ≥ 5 (init module emit, main.py wire, env hint, package dep, .env.example block)
```

## File Manifest

| Path | Purpose |
| :--- | :--- |
| `/opt/fabrik/scripts/provision_glitchtip_project.sh` | CLI provisioner (idempotent, WSL-aware) |
| `/opt/fabrik/src/fabrik/scaffold.py` | Scaffold logic that emits `glitchtip_init.{py,js}` |
| `/opt/fabrik/src/fabrik/orchestrator/infrastructure.py` | `_provision_glitchtip()` registrar — runs from `fabrik apply` |
| `/opt/fabrik/src/fabrik/drivers/glitchtip.py` | DSN verification (`docker inspect`-based, per Lesson 31) |
| `/opt/fabrik/.env` (WSL) | Holds `GLITCHTIP_AUTH_TOKEN`, `GLITCHTIP_ORG_SLUG`, `GLITCHTIP_TEAM_SLUG` |
| `/opt/fabrik/.windsurf/rules/core/55-observability.md` | Canonical capture discipline rules |
| `<service>/src/{pkg}/glitchtip_init.py` | Per-service Python init module (scaffold-emitted) |
| `<service>/src/glitchtip_init.js` | Per-service Node init module (scaffold-emitted) |

## Validation Performed (2026-05-08)

- Provisioned `fabrik-gt-validation-test` project: HTTP 201, DSN returned `http://f59a0b1c78ba412bb894b1a9a11e4fd8@glitchtip-web:8000/64`
- Idempotence: re-run returned same DSN, "skipping create" log
- Synthetic `ValueError` sent via `sentry-sdk` from inside the `fabrik` network → project's `firstEvent` populated `2026-05-08T14:35:52.164Z` (~90s after creation)
- Scaffold emission validated for both `python-api` and `node-api`; no-op paths exercised (DSN unset → False; DSN set + SDK missing → False)
- `node --check` and `python -m py_compile` both pass on emitted modules

## Validation Pending (Post-Multi-Host)

- Spoke (vps2/vps3) → vps1 ingestion via `10.99.0.1:8000`. Requires the mesh-IP port binding documented in § Multi-host Path B. Will be added when the first SaaS lands on vps2/vps3.

## References

- GlitchTip docs: <https://glitchtip.com/documentation/install>
- Sentry SDK Python: <https://docs.sentry.io/platforms/python/integrations/fastapi/>
- Sentry SDK Node: <https://docs.sentry.io/platforms/javascript/guides/node/>
- Sister runbooks (same canonical style):
  - `docs/infrastructure/grafana-provisioning-setup.md`
  - `docs/infrastructure/promtail-noise-filter-setup.md`
