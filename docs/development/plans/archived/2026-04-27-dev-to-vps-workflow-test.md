# Dev→VPS Workflow End-to-End Test (2026-04-27)

**Goal:** validate the full Fabrik scaffold→spec→`fabrik apply`→verify→destroy cycle end-to-end on real VPS infrastructure. Surface and fix every workflow bug.

## Key Invariants

1. Every scaffolded project must produce a deployable spec OR be intentionally non-deployable (with a clear reason).
2. `fabrik apply` must wire shape-gated registrars per `shape.*` flags (postgres if `needs_database`, gatus if public, glitchtip always, grafana, authelia if admin dashboard).
3. Cleanup must remove **all** created resources: Coolify app, Traefik route, Cloudflare DNS, GlitchTip project, Gatus endpoint, Grafana dashboard, postgres DB if created.
4. No silent failures. Every registrar fires-or-skips with a logged reason.

## Failure Modes (anticipated)

- Coolify v4 inline-compose path may have its own quirks (separate from the open #6 git-deploy 404).
- Cloudflare zone provisioning may collide with existing DNS.
- GlitchTip DSN injection has a 240s window (per 2026-04-22 fix); rebuild slower than that → false-negative rollback.
- `coolify.project: default` placeholder triggers auto-create of a "default" project — pollutes Coolify.
- Postgres registrar may fail to drop DB on rollback if connections held.
- Domains assigned to chrome-ext / mobile-app / desktop-app are nonsensical (client-side artifacts, not web services).

## Bugs Already Surfaced (pre-deploy)

| ID | File | Description | Severity |
|----|------|-------------|----------|
| **B1** | `src/fabrik/scaffold.py` (--db handler) | `--db` flag creates local PostgreSQL DB but does not set `shape.needs_database: true` in emitted spec. Confirmed: `fabrik-test-python-api` was scaffolded with `--db`, spec has `needs_database: false`. Postgres registrar will not fire on apply. | HIGH (silent feature breakage) |
| **B2** | `src/fabrik/scaffold.py` (spec emitter) | All emitted specs have `coolify.project: default` and `coolify.server: localhost` as placeholders. With deployer fix from this session, this auto-creates a "default" Coolify project. Should be unset (env override) or sensible (e.g. `fabrik-services`). | MEDIUM (clutter, not breaking) |
| **B3** | `src/fabrik/scaffold.py` (artifact-type emitters) | `chrome-extension`, `mobile-app`, `desktop-app` all emit `specs/services/*.yaml` with `domain: <name>.vps1.ocoron.com`, `expose.http: true`. These are client-side build artifacts, not VPS-deployable. Spec should not be emitted at all OR `kind:` should be `artifact` so deployer skips. | HIGH (would leak DNS records on apply) |
| **B4** | `src/fabrik/scaffold.py` (kind consistency) | Top-level `kind: service` while `shape.kind: static` for chrome-ext/mobile-app/desktop-app. Inconsistent. | LOW (cosmetic) |

## Test Plan (5 representative projects, not all 11)

To bound VPS state and make cleanup reliable, deploy 5 representative projects covering all 4 shape kinds:

| # | Project | Shape | DB? | Why this one |
|---|---------|-------|-----|--------------|
| 1 | `fabrik-test-python-api` | service | yes (after B1 fix) | Most-common shape; mirrors proxy/site-provisioner; max-coverage of registrars |
| 2 | `fabrik-test-node-api` | service | no | Service shape, different language stack (Node), fewer registrars |
| 3 | `fabrik-test-static-site` | static | no | Static shape; tests that postgres+glitchtip skip correctly |
| 4 | `fabrik-test-file-worker` | worker | no | Worker shape (no domain, no Gatus); tests `is_public: false` skip path |
| 5 | `fabrik-test-saas-skeleton` | service | yes | Heaviest service (Next.js + Stripe + Supabase env vars); stress-tests env-var sync |

Skip for VPS testing (artifact types): chrome-extension, desktop-app, mobile-app, docusaurus (Docusaurus could deploy as static-site but adds noise), file-api (similar to python-api), wordpress (uses different `fabrik wp` path).

## Per-Project Cycle (each of the 5)

1. **Pre-deploy snapshot:** record Coolify apps, Cloudflare DNS records, GlitchTip projects, Gatus endpoints, Grafana dashboards.
2. **Apply:** `fabrik apply specs/services/<name>.yaml --use-orchestrator` with `-s` for required secrets.
3. **Verify (live):**
   - Coolify app status: running, container Up
   - Traefik router exists for the domain
   - HTTPS reachable (200 on `/health` for services, 200 on `/` for static)
   - DNS A record resolves to VPS IP (172.93.160.197)
   - GlitchTip project + DSN injected into container env
   - Gatus monitoring the endpoint (if public)
   - Postgres DB created (if `needs_database`)
4. **Destroy:** `fabrik destroy <name>` (or manual reverse-order cleanup if destroy not implemented).
5. **Post-destroy snapshot diff:** verify Coolify, DNS, GlitchTip, Gatus, Grafana all returned to pre-deploy state. Any leak = bug.
6. **Log result** in `## Run Log` below.

## Run Log

### 2026-04-27 — first-pass deployment surfaced 3 new bugs

**Pre-deploy snapshot:** `.tmp/vps-snapshot-pre-deploy.json` — 11 apps + 30 services (41 total under `list_applications`), 25 vps1 DNS records, 4 GlitchTip projects, 16 Gatus endpoints. Snapshot tool: `scripts/snapshot_vps_state.py` (read-only; supports `--diff A B`).

**Bugs surfaced + fixed during the python-api deploy attempt:**

| ID | Symptom | Root cause | Fix |
|----|---------|-----------|-----|
| **B5** | `fabrik apply` returns Coolify 422 `"docker_compose_raw should be base64 encoded"` even though the driver does base64-encode. | Coolify v4 inline-compose endpoint silently rejects compose YAML containing **non-ASCII characters** (em-dash `—` in a comment in `templates/python-api/compose.yaml.j2:60` and in 3 wordpress templates) with the wrong error message. Verified via bisect against a minimal nginx compose. | Replaced em-dashes with ASCII hyphens in 4 templates. Added defensive ASCII pre-check in `coolify.create_dockercompose_application` so future regressions fail with a clear error instead of Coolify's misleading 422. |
| **B6 (silent-failure log noise)** | Rollback path does raw `GET /applications/{uuid}` and gets 404 because dockercompose-created resources live under `/services/{uuid}`. | Pre-existing partial fix in `coolify._resolve_resource_base` already routes via dual-probe; the rollback's noisy 404 logs come from probe step itself, but rollback succeeded. **Not a functional bug**, just confusing log noise. Will revisit if it masks real failures. | Deferred. |
| **B7 (P0 architectural)** | Container never comes up; `_wait_for_container` times out at 90s; DSN injection then times out at 240s. | The scaffolder emits `source.type: template` and the `python-api/compose.yaml.j2` template uses `build: context: .` — but Coolify's inline-compose endpoint receives **only the compose YAML, not the source tree**. There is no source for `build:` to consume, so the build silently never happens and no container is created. Verified: working services (`proxy`, `site-provisioner`) all use `source.type: git`. | **Open — needs design decision.** Scaffolder default of `source.type: template` is incompatible with Coolify deploy when the compose has a `build:` directive. Options: (a) scaffolder defaults `source.type: git` once project has a git remote, (b) compose templates use `image:` from a registry instead of `build:`, (c) deploy pipeline pushes source to a Coolify-side workdir before deploy. |

**State after first-pass:** 0 leaks (verified via `--diff pre-deploy after-cleanup-2`). The failed apply did create `fabrik_test_python_api` postgres DB which was preserved by the destroyer's no-auto-drop policy; manually dropped to restore baseline.

**Stopping point:** B7 blocks all 5 representative project deployments because every `fabrik scaffold`-emitted spec has `source.type: template`. Cannot proceed with the apply→verify→destroy loop until B7 is resolved by owner decision. Continuing would surface the same bug 5 more times.
