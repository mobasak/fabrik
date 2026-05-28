# Mobile App Deployment Pipeline — Design Spec

**Date:** 2026-05-28
**Status:** Design approved, pending implementation plan
**Depends on:** SSH Deployer (Phase 11-1, `docs/development/plans/2026-05-28-ssh-deployer.md`) — implement SSH deployer first, then layer mobile changes on top. Cross-reference note added to SSH plan's "Cross-Reference" section.
**Canonical lifecycle doc:** `docs/reference/fabrik-lifecycle.md` (updated inline with each decision)

---

## Problem

The `mobile-app` scaffold type has a split deployment model: a VPS backend (automated via `fabrik apply`) and a client binary (shipped via App Store / Google Play). The current scaffold is incomplete — it emits a Node.js backend (should be FastAPI per rules), has no Expo/EAS configuration, no Sentry client init, and no support for Supabase-only apps (no VPS backend). The deployment pipeline needs to handle both patterns.

## Decisions Made

| Decision | Choice | Rationale |
|---|---|---|
| Scaffold approach | Single scaffold, shape-gated at deploy time (Approach A) | One template set, `has_vps_backend` flag controls deploy behavior. Matches how other shape flags work. No scaffold bifurcation. |
| Backend language | FastAPI (Python), replacing Node.js | 80-mobile.md says "FastAPI on VPS". All other Fabrik backends are Python. |
| Backend patterns | Both Supabase-only and Supabase+FastAPI supported | 80-mobile.md: Supabase is primary, FastAPI is secondary/optional. Shape-driven. |
| Supabase-only `fabrik apply` | Spec exists, deployer skips container. Only GlitchTip registrar runs. | No VPS endpoint = no DNS, no Gatus, no container-dependent registrars. |
| Client build/submit | Phase A (manual EAS) now. Phase B (`fabrik publish-mobile`) deferred until first app ships. Phase C (full CI/CD) not planned. | Store submission has manual review gates. Automation before a shipped app is premature. |
| Client crash reporting | `@sentry/react-native` SDK, DSN from EAS secrets | 55-observability.md mandates Sentry RN SDK. GlitchTip is Sentry-compatible. `sentry-expo` deprecated since SDK 50. |

---

## Two Backend Patterns

| Pattern | Backend | `shape.has_vps_backend` | `fabrik apply` behavior |
|---|---|---|---|
| **Supabase + FastAPI** | Supabase (auth, data, realtime, storage, edge functions) + FastAPI on VPS (AI workflows, scraping, scheduled jobs, secrets) | `true` | Full deploy: container creation + all shape-gated registrars |
| **Supabase-only** | Supabase handles everything | `false` | Deployer skips container. Only GlitchTip runs (creates project, outputs DSN to state + stdout). All other 8 registrars skipped. |

Per 80-mobile.md: Supabase is **primary**, FastAPI on VPS is **secondary**. Both are first-class.

---

## Shape & Scaffold Changes

### New shape flag

`has_vps_backend: bool = True` added to the `Shape` class in `spec_loader.py`.

**Validation constraint**: When `has_vps_backend: false`, the following flags MUST also be false/disabled — they require a VPS container to function. The validator (`validator.py`) should reject specs with contradictory flags:

- `needs_database: true` — postgres registrar tries to reach `postgres-main` via Docker DNS
- `needs_cache: true` — redis registrar injects `REDIS_URL` into a container that doesn't exist
- `has_search_feature: true` — meilisearch index creation needs an app to query it
- `has_persistent_data: true` — backrest backup plan targets a container volume
- `is_admin_dashboard: true` — authelia rule protects a URL that doesn't resolve

### Updated `defaults.yaml`

```yaml
shape:
  kind: service
  is_public: true
  is_admin_dashboard: false
  has_bearer_api: false
  has_persistent_data: false
  needs_database: false
  needs_cache: false
  has_search_feature: false
  exposes_metrics: true
  has_vps_backend: true
```

Changes from current: `is_public` flipped to `true` (mobile APIs are public), added `needs_cache`, `exposes_metrics`, `has_vps_backend`.

### Template rewrite — FastAPI backend

Following the `python-api` template conventions:

- **`Dockerfile.j2`**: Python 3.12 bookworm-slim, multi-stage build, uvicorn, dynamic port via `svc_port` (default 8081)
- **`compose.yaml.j2`**: FastAPI service, healthcheck at `/health` (not `/status`), `start_period: 40s`, Traefik middleware routing, `platform: linux/amd64`, `deploy.resources.limits.memory`, `container_name: {{ spec.id }}`, `restart: unless-stopped`, `networks: [coolify]` external
- **Port 8081** registered in `PORTS.md`

### New scaffold outputs

The `_scaffold_mobile_app()` function in `scaffold.py` must additionally emit:

| File | Purpose | Source |
|---|---|---|
| `app.json` | Expo config: bundle identifiers from spec, privacy/ToS URLs, config plugins, Sentry plugin | 80-mobile.md, 89-mobile-launch-checklist.md |
| `eas.json` | Three EAS build profiles: `development`, `preview`, `production` | 80-mobile.md line 218 |
| Sentry init in app entry point | `@sentry/react-native` init before `registerRootComponent`, DSN from config | 55-observability.md lines 195-202 |
| Updated `package.json` | Expo SDK 55 deps, `@sentry/react-native`, replace bare RN 0.72 | 80-mobile.md line 81 |

### No scaffold bifurcation

Supabase-only projects: developer deletes unused backend files (`src/backend/`, `Dockerfile`, `compose.yaml`) and sets `has_vps_backend: false` in the spec.

---

## Deploy Pipeline

### `fabrik apply` with `has_vps_backend: true`

Standard flow, identical to any other service:

1. Validate spec + compute hash
2. Load secrets
3. DNS — Cloudflare A record → VPS IP
4. SSHDeployer — render compose, write to `/opt/{name}/`, `docker compose up -d`
5. Registrars — shape-gated, in `_REGISTRAR_ORDER` (postgres, redis, gatus, backrest, glitchtip, grafana, authelia, meilisearch, prometheus)
6. Verify — HTTPS + `/health`

### `fabrik apply` with `has_vps_backend: false`

Lightweight path — orchestrator checks `spec["shape"]["has_vps_backend"]` at 3 branch points:

| Step | `true` | `false` |
|---|---|---|
| Validate + hash | runs | runs |
| Load secrets | runs | runs (GlitchTip API needs creds) |
| DNS | runs | **skipped** — no VPS endpoint |
| Deployer | runs | **skipped** — no container |
| Registrars | all shape-gated | only GlitchTip runs; `inject_env` replaced with output DSN to state + stdout; `verify_dsn_injection` skipped (no container) |
| Verify | HTTPS + `/health` | **skipped** — nothing on VPS |

### Implementation touchpoints

- **`orchestrator/__init__.py` `deploy()`**: Check `has_vps_backend` before the DNS, deployer, and verify calls. The orchestrator calls `infrastructure_provisioner.provision(ctx)` as a single call (not individual registrars), so the DNS/deployer/verify gates go in `deploy()` but registrar gating goes in `resolve_applicability()`. Note: line numbers reference pre-SSH-deployer state; adjust after SSH deployer plan Step 3 is implemented.
- **`infrastructure.py` `resolve_applicability()`**: Add `has_vps_backend` check at the top of this pure function. When `false`, return `False` for all registrars except `glitchtip`. This is the correct gate point — the function already takes the spec dict as input and returns per-registrar applicability. Do NOT gate in the orchestrator's `deploy()` method, which only calls `provision()` as a single unit.
- **`infrastructure.py` `_provision_glitchtip()`**: When `has_vps_backend: false`, create GlitchTip project + write DSN to state (via `ctx.add_resource` at line ~420), then early-return before `inject_env` and `verify_dsn_injection`. Output DSN to stdout so mobile developer can add it to EAS secrets. This fork point is after SSH deployer plan Step 4 rewrites the registrar.
- **`verifier.py` `verify()`**: Add `has_vps_backend` to the existing worker/non-HTTP skip block (lines 85-92). Alternatively, mobile specs could set `expose.http: false` to reuse the existing B35 skip logic without code changes.

### `fabrik redeploy`

When `has_vps_backend: false`, prints "No VPS backend to redeploy" and exits. The guard requires loading the spec YAML first (via `--spec` flag or resolving from state file at `/opt/{name}/`) to check the flag before calling `find_existing()`. This layers on top of the SSH deployer plan's Step 7 redeploy rewrite.

### `fabrik destroy`

Works naturally via state-driven destroy. State file only contains what was created:
- `has_vps_backend: true` → state has compose + DNS + registrar resources → full teardown
- `has_vps_backend: false` → state has only GlitchTip project → tears down GlitchTip only

---

## Client Build & Store Submission

### Phase A — Manual (current)

```
Developer workflow:
1. Code the React Native / Expo app in WSL
2. fabrik apply specs/services/my-app.yaml
   → deploys backend (if has_vps_backend: true)
   → creates GlitchTip project (always)
   → outputs DSN to stdout
3. Add GlitchTip DSN to EAS secrets:
   eas secret:create --name SENTRY_DSN --value <dsn> --scope project
4. eas build --platform all
   → builds APK/IPA via Expo EAS cloud
5. eas submit --platform all
   → uploads to App Store / Google Play
6. Wait for store review
```

Fabrik's responsibility ends at step 2. Steps 3-6 are developer-driven.

### Phase B — Semi-automated (deferred until first app ships)

`fabrik publish-mobile <spec>`:
- Reads `eas.json` from project directory
- Runs `eas build --platform all --non-interactive`
- On success, runs `eas submit --platform all --non-interactive`
- Logs build/submit URLs to stdout
- Manual trigger, no CI/CD

### Phase C — Full CI/CD (not planned)

GitHub push → EAS Build → auto-submit. Deferred indefinitely — solo dev, manual trigger is fine.

### DSN injection for mobile client

Via EAS secrets (`eas secret:create`), read at build time in `app.json` `extra` field or at runtime via `expo-constants`. Matches the env-var pattern used everywhere else in Fabrik — no file placeholders.

### Store prerequisites (from 89-mobile-launch-checklist.md)

- Google Play Console: Organization account (bypasses 14-day tester mandate)
- Apple Developer Program: Organization ($99/yr)
- Both stores: 15% Small Business Program enrolled
- Both stores: W-8BEN-E filed for US-Turkey treaty (0% withholding)
- App identity locked: `ios.bundleIdentifier` + `android.package` in `app.json` (cannot change post-submission)

### Crash reporting

- SDK: `@sentry/react-native` (NOT deprecated `sentry-expo`)
- Source maps: `@sentry/react-native/expo` plugin + Sentry Metro plugin in EAS build config
- Crash-free rate target: >= 99.5% (store ranking factor, per 55-observability.md)

---

## Backup & Durability Context

The mobile deployment design inherits Fabrik's existing backup strategy:

| What | How | Mobile relevance |
|---|---|---|
| **Postgres data** | WAL/PITR continuous backup to B2 | VPS backend with `needs_database: true`. Supabase-only: handled by Supabase's own PITR. |
| **File assets** | Directly in Backblaze B2 (S3-compatible) | App uploads go to B2 via the backend or Supabase Storage |
| **Persistent app data on disk** | Backrest → B2 daily snapshots (when `has_persistent_data: true`) | Only for VPS backends with local persistent files |
| **Job state** | Postgres SKIP LOCKED (durable) | Survives crash/restart — no in-memory queue loss |
| **Infra config** | Defined in Fabrik git repo + SSH/Docker Compose | Reproducible box rebuild |

No mobile-specific backup work needed. Existing registrars and infrastructure cover both patterns.

---

## Registrar Behavior Matrix

| Registrar | `has_vps_backend: true` | `has_vps_backend: false` | Gate condition |
|---|---|---|---|
| **postgres** | Shape-gated (`needs_database`) | Skipped | `needs_database` |
| **redis** | Shape-gated (`needs_cache`) | Skipped | `needs_cache` |
| **gatus** | Runs (monitors `/health`) | Skipped | `kind in (service, worker, wordpress)` — but orchestrator skips all non-GlitchTip registrars when `has_vps_backend: false` |
| **backrest** | Shape-gated (`has_persistent_data`) | Skipped | `has_persistent_data` |
| **glitchtip** | Creates project + `inject_env` DSN | Creates project + outputs DSN to state/stdout | `kind in (service, worker, wordpress)` |
| **grafana** | Deploy annotation | Skipped | Always runs for VPS deploys — orchestrator skips when `has_vps_backend: false` |
| **authelia** | Shape-gated (`is_admin_dashboard`) | Skipped | `is_admin_dashboard` |
| **meilisearch** | Shape-gated (`has_search_feature`) | Skipped | `has_search_feature` |
| **prometheus** | Shape-gated (`exposes_metrics`) | Skipped | `exposes_metrics` |

---

## What Changes Where

| Component | Change | Scope |
|---|---|---|
| `spec_loader.py` | Add `has_vps_backend: bool = True` to Shape class | 1 field |
| `templates/mobile-app/defaults.yaml` | Add `has_vps_backend`, `needs_cache`, `exposes_metrics`; flip `is_public` | ~5 lines |
| `orchestrator/__init__.py` | Check `has_vps_backend` before DNS, deployer, verify | ~15 lines |
| `infrastructure.py` | GlitchTip: skip `inject_env` + `verify_dsn_injection` when no VPS; output DSN to state + stdout | ~20 lines |
| `templates/mobile-app/Dockerfile.j2` | Replace Node.js with Python 3.12 FastAPI | Full rewrite |
| `templates/mobile-app/compose.yaml.j2` | FastAPI, `/health`, `start_period: 40s`, port 8081 | Full rewrite |
| `templates/mobile-app/package.json` | Expo SDK 55, `@sentry/react-native` | Full rewrite |
| `scaffold.py` | Emit `app.json`, `eas.json`, Sentry init for mobile-app | ~80 lines |
| `PORTS.md` | Register port 8081 for mobile-app backend | 1 line |
| `cli.py` redeploy | Guard for `has_vps_backend: false` | ~5 lines |
| `fabrik-lifecycle.md` | Already updated with all decisions | Done |

### Not changed by this design

These components are NOT modified by the mobile design itself, but depend on the SSH Deployer (Phase 11-1) being fully implemented first:

- 9 registrar drivers — self-gate via shape flags
- Verifier — orchestrator skips the call via `has_vps_backend` check; verifier code unchanged
- SSH deployer (Phase 11-1) — consumed as-is
- Template renderer — consumed as-is
- Destroyer — uses SSH deployer's Step 6 `_destroy_compose()` function to handle compose resources. Without Step 6, destroy would silently skip app directory cleanup for SSH-deployed services.
- Rollback — uses SSH deployer's Step 5 `_rollback_compose()` method to handle compose resources. Without Step 5, rollback would silently skip compose cleanup.

### Dependencies

This design requires the SSH deployer (Phase 11-1) to be implemented first, including:

- `SSHDeployer.inject_env()` — called by the GlitchTip registrar
- `_destroy_compose()` (Step 6) — required for `fabrik destroy` to clean up compose apps
- `_rollback_compose()` (Step 5) — required for rollback to clean up failed compose deploys
