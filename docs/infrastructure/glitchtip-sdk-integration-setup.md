# GlitchTip SDK Integration — Setup

**Status:** ✅ Live (2026-05-08)
**Scaffold-emitted:** `glitchtip_init.py` / `glitchtip_init.js` per project
**Provisioner:** `/opt/fabrik/scripts/provision_glitchtip_project.sh`
**GlitchTip URL (Authelia-protected):** `https://errors.vps1.ocoron.com`
**GlitchTip URL (internal coolify-network alias):** `http://glitchtip-web:8000`

---

## Goal

Every Fabrik service emitted by `fabrik scaffold` ships with a Sentry-SDK init module pointed at the in-cluster GlitchTip. When `GLITCHTIP_DSN` is set in the service's Coolify env, unhandled exceptions auto-report to GlitchTip with stacktrace, release tag, and environment label. When unset, the SDK is a zero-overhead no-op — services can be deployed without DSN configured and pay nothing for the integration.

This eliminates two failure modes:
1. **No error visibility** in production until someone reads logs (Loki) line by line.
2. **Per-service custom Sentry init** drift — wrong sample rates, wrong PII handling, missing release tags.

## Critical Detail

The DSN returned by GlitchTip's `/api/0/projects/{org}/{project}/keys/` endpoint emits the public host (typically `localhost:8000` because GlitchTip's `GLITCHTIP_DOMAIN` is internal). The provisioner **rewrites the host part of the DSN to `glitchtip-web:8000`** — the stable Docker DNS alias on the `coolify` network — so containers ingest events through the internal network without going through Authelia or TLS termination.

Without this rewrite, services would either:
- Hit the public Authelia-protected URL and get 401 (the SDK doesn't auth)
- Need the public URL whitelisted in Authelia just for SDK ingestion (defeats the security boundary)
- Or hardcode `localhost:8000` which only works inside the GlitchTip container itself

## Prerequisites

- GlitchTip deployed via Coolify (web + worker containers, postgres-main has `glitchtip` DB)
- `glitchtip-web` is a stable DNS alias on the `coolify` network (verify: `sudo docker run --rm --network coolify curlimages/curl:latest -sS -o /dev/null -w "%{http_code}\n" http://glitchtip-web:8000/api/0/`)
- A GlitchTip auth token with `project:write` scope, created via the GlitchTip UI under Settings → Auth Tokens
- Three credentials in `/opt/fabrik/.env` (WSL local mirror):
  ```
  GLITCHTIP_AUTH_TOKEN=<bearer-token>
  GLITCHTIP_ORG_SLUG=<your-org-slug>
  GLITCHTIP_TEAM_SLUG=<your-team-slug>
  ```

## Reproducible Setup

### 1. Verify GlitchTip is reachable on the internal network

From WSL:
```bash
ssh vps 'sudo docker run --rm --network coolify curlimages/curl:latest -sS \
  -o /dev/null -w "HTTP %{http_code}\n" http://glitchtip-web:8000/api/0/'
# Expected: HTTP 200
```

### 2. Provision a project + DSN

```bash
# Python service:
bash /opt/fabrik/scripts/provision_glitchtip_project.sh my-service

# Node service (sets project platform tag for proper symbolication):
bash /opt/fabrik/scripts/provision_glitchtip_project.sh my-service --platform javascript-node

# With automatic Coolify env push:
bash /opt/fabrik/scripts/provision_glitchtip_project.sh my-service \
  --coolify-uuid <service-uuid>
```

The script:
- Auto-detects WSL and re-execs on VPS via SSH (bringing your `.env` creds with it)
- GETs the project; if 404, POSTs to create it
- Fetches the DSN via `/api/0/projects/{org}/{project}/keys/`
- Rewrites the host to `glitchtip-web:8000`
- Optionally pushes the DSN to a Coolify service env via the Coolify API (PATCH `/api/v1/services/{uuid}/envs`)
- Prints the final DSN on the **last line of stdout** (other output goes to stderr)

The script is idempotent: re-running for an existing project just refetches the DSN.

### 3. Push the DSN to Coolify env (if not done in step 2)

In Coolify UI for the service, add:
```
GLITCHTIP_DSN=http://<key>@glitchtip-web:8000/<project_id>
ENVIRONMENT=production
GIT_SHA=<commit-sha-from-CI>   # optional but recommended
```

Or via the API directly with the DSN from step 2.

Then `fabrik redeploy <service>` (after `git commit && git push` per the standing rule).

### 4. Verify ingestion

The cleanest end-to-end check is the project's `firstEvent` timestamp:

```bash
TOKEN=$(grep '^GLITCHTIP_AUTH_TOKEN=' /opt/fabrik/.env | cut -d= -f2-)
ORG=$(grep '^GLITCHTIP_ORG_SLUG=' /opt/fabrik/.env | cut -d= -f2-)

ssh vps "sudo docker run --rm --network coolify curlimages/curl:latest -sS \
  -H 'Authorization: Bearer $TOKEN' \
  http://glitchtip-web:8000/api/0/projects/$ORG/my-service/" \
| python3 -c "import sys,json; d=json.load(sys.stdin); print('firstEvent:', d.get('firstEvent'), 'platform:', d.get('platform'))"
```

If `firstEvent` is `null`, no events have arrived yet. Trigger a deliberate exception in the deployed service and re-check (events appear within a few seconds).

## How the Scaffold Wires It

The integration is emitted automatically by `fabrik scaffold <name> --type python-api|node-api`. No manual file copying needed.

### Python (`python-api`, `file-worker`)

Emitted files:
```
src/{package}/glitchtip_init.py    # init_glitchtip() with FastApiIntegration + StarletteIntegration
src/{package}/main.py              # imports + calls init_glitchtip() BEFORE FastAPI()
requirements.txt                   # adds: sentry-sdk[fastapi]>=2.18.0
.env.example                       # adds: GLITCHTIP_DSN= and ENVIRONMENT=production
```

Init signature: `init_glitchtip() -> bool` returns True if init ran, False if no-op (DSN unset OR sentry-sdk not installed). Idempotent.

### Node (`node-api`, `file-api`)

Emitted files:
```
src/glitchtip_init.js              # Sentry.init() from @sentry/node, no-op-on-missing-DSN
src/index.js                       # require('./glitchtip_init') at the top, BEFORE http.createServer
package.json                       # adds: "@sentry/node": "^8.40.0"
.env.example                       # adds: GLITCHTIP_DSN= and ENVIRONMENT=production
```

The init module exports the configured Sentry instance (or `null` if no-op) so callers can do `const Sentry = require('./glitchtip_init')` and use it for manual `captureException` calls.

## Capture Discipline (rules for code authors)

When `GLITCHTIP_DSN` is set, errors auto-report. Treat redundant logging as noise:

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
| `GLITCHTIP_DSN` | (unset → no-op) | DSN returned by the provisioner |
| `ENVIRONMENT` | `production` | Tags events; filter prod vs staging in UI |
| `GIT_SHA` | (unset) | Release tag — falls back to `COOLIFY_DEPLOYMENT_UUID` |
| `GLITCHTIP_TRACES_SAMPLE_RATE` | `0.05` | Performance tracing sample rate (0.0–1.0). Keep low. |
| `GLITCHTIP_PROFILES_SAMPLE_RATE` | `0` | Profiling off by default (would require native deps) |

## Troubleshooting

**Symptom: events not appearing in GlitchTip UI**

1. Check the service's actual env in Coolify — is `GLITCHTIP_DSN` set and non-empty?
2. SSH to VPS and inspect: `sudo docker exec <container> env | grep GLITCHTIP`
3. From inside the container's network, confirm reachability: `sudo docker exec <container> curl -sS -o /dev/null -w "%{http_code}\n" http://glitchtip-web:8000/api/0/` — expect 200.
4. Check the project's `firstEvent` via the API (see step 4 above).
5. Check the GlitchTip worker logs: `sudo docker logs --tail 50 glitchtip-worker-msgo0sg8gsgo4w4sscckc84g` — Celery rejection messages indicate ingestion errors.

**Symptom: `Permission denied` from `/api/0/projects/{org}/{project}/issues/`**

The auth token has `project:write` but not `event:read` scope. Either create a second token with `event:read` for query operations, or use the project's `firstEvent` field as the ingestion sentinel (it's exposed without the elevated scope).

**Symptom: provisioner errors with `unparseable DSN`**

GlitchTip's DSN format changed between versions. Check the raw `keys/` response:
```bash
ssh vps "sudo docker run --rm --network coolify curlimages/curl:latest -sS \
  -H 'Authorization: Bearer <token>' \
  http://glitchtip-web:8000/api/0/projects/<org>/<project>/keys/"
```
Update the regex in `provision_glitchtip_project.sh` step 2 if the format diverged.

**Symptom: scaffold doesn't emit `glitchtip_init.py`**

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
| `/opt/fabrik/.env` (WSL) | Holds `GLITCHTIP_AUTH_TOKEN`, `GLITCHTIP_ORG_SLUG`, `GLITCHTIP_TEAM_SLUG` |
| `/opt/fabrik/.windsurf/rules/55-observability.md` | Canonical capture discipline rules |
| `<service>/src/{pkg}/glitchtip_init.py` | Per-service Python init module (scaffold-emitted) |
| `<service>/src/glitchtip_init.js` | Per-service Node init module (scaffold-emitted) |

## Validation Performed (2026-05-08)

- Provisioned `fabrik-gt-validation-test` project: HTTP 201, DSN returned `http://f59a0b1c78ba412bb894b1a9a11e4fd8@glitchtip-web:8000/64`
- Idempotence: re-run returned same DSN, "skipping create" log
- Synthetic `ValueError` sent via `sentry-sdk` from inside coolify network → project's `firstEvent` populated `2026-05-08T14:35:52.164Z` (~90s after creation)
- Scaffold emission validated for both `python-api` and `node-api`; no-op paths exercised (DSN unset → False; DSN set + SDK missing → False)
- `node --check` and `python -m py_compile` both pass on emitted modules

## References

- GlitchTip docs: https://glitchtip.com/documentation/install
- Sentry SDK Python: https://docs.sentry.io/platforms/python/integrations/fastapi/
- Sentry SDK Node: https://docs.sentry.io/platforms/javascript/guides/node/
- Sister runbooks (same canonical style):
  - `docs/infrastructure/grafana-provisioning-setup.md`
  - `docs/infrastructure/promtail-noise-filter-setup.md`
