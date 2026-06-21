# Plan — saas-skeleton gains a pro-grade multi-tenant FastAPI backend

**Status:** CONVERGED (every step grounded to read code/pack evidence; plan carries its proof; `check_convergence.py` green with plan staged)
**Date:** 2026-06-21 · **Author:** Claude Code
**Goal:** Every `saas-skeleton` scaffold must emit a **frontend (Next.js) + a conforming FastAPI backend** so saas projects are multi-user and backend-supported by default — reusing `python-api`'s canonical backend and adding the multi-tenant / auth / API-contract layer the packs mandate, **and updating the `fabrik apply` deploy services** (shape flags → Postgres/Redis/Prometheus/Gatus/GlitchTip/Backrest registrars, with Prometheus targeting the api service in the 3-service compose), **plus a background-jobs tier** — PostgreSQL as the queue + an adaptive-pool worker that **auto-scales on queue depth** + a single-leader **beat scheduler for cron/periodic** tasks — so any async work, cron, db, workers, and worker auto-expansion deploy easily via `fabrik apply`. Lean: one example tenant-scoped resource + one example job wired end-to-end; the rest documented. After implementation the scaffold folder is created and tested (Phase 9), with live deploy proof as the ultimate gate (Phase 10).

## Binding rule packs (read via `scripts/select_rules.py`)

- `saas/95-multi-tenant-saas.md` — RLS (ENABLE+FORCE), fail-closed `current_tenant_id()`, `SET LOCAL app.tenant_id` per txn + `ContextVar`, membership validation (403), `tenant_id UUID` + B-tree index.
- `core/35-security-auth.md` — Pattern B (Supabase Auth + FastAPI validates Supabase JWT via JWKS); FastAPI security headers; M2M `X-Internal-Token`; CORS from env; auth rate-limit.
- `core/15-api-contracts.md` — RFC 9457 `application/problem+json`; `/api/v1/` versioning; `to_camel` base model; `X-Idempotency-Key`; service layer.
- `core/55-observability.md` — `/health` real-dep (`SELECT 1`), `/metrics`. `saas/60-saas-ui.md` — page inventory (frontend). `saas/87-abuse-detection.md` — signup gating (documented extension).

## Gate model (the gate each implementer runs)

This is a `/opt/fabrik` **code** change (the scaffolder), so the comprehensive gate applies here (unlike the fabrik-lib doc-modules):
- **Named test:** `python -m pytest tests/test_scaffold_saas_backend.py -q` (asserts the emitted saas has `server/`, the tenant/auth/worker files, the `jobs` queue schema, and a 3-service compose).
- **Comprehensive gate (NOT `--lean`):** `python scripts/final_gate.py --json` → `"status":"success"`.
- **Live proof:** `PROOF_ONLY=saas-skeleton python scripts/proof_run.py` → scaffolds → `fabrik apply` → `curl https://fabrik-test-saas-skeleton.vps1.ocoron.com/api/health` returns **200** (`proof_run.py:77`).

## One-Test Rule

**Why:** The whole point of this change is that a scaffolded saas is *backend-supported and deployable by default*. The single highest-risk path is the scaffolder emitting a structurally-conforming backend (server package + RLS/jobs schema + 3-service compose); if that regresses, every saas project ships broken. `tests/test_scaffold_saas_backend.py` is that gate.

**Contract:**
- **Given:** a clean temp dir and the saas-skeleton template.
- **When:** `create_project(type="saas-skeleton", generate_spec=False)` runs.
- **Then:** `server/` contains the FastAPI package (`main/auth/tenant/worker/...py`), `server/db/schema.sql` carries `current_tenant_id()` + `FORCE ROW LEVEL` + `tenant_isolation` + the `jobs` queue (`FOR UPDATE SKIP LOCKED`, `idx_jobs_pending`, `pg_notify`), and `compose.yaml` declares three memory-limited services (`<name>` + `api` at `PathPrefix(/api)` priority 100 + internal `worker`).
- **Mocked:** nothing — the test scaffolds for real and inspects emitted files. Live deploy (Phase 10) is the only mocked-free step deferred (needs commit+push).

---

## Phase 0 — Shared `_scaffold_fastapi_backend()` helper

### Evidence
`python-api` already emits the canonical backend (internal_auth, metrics, /metrics, logger/middleware/main):
```
$ grep -nE 'def _scaffold_python_api|internal_auth.py|metrics.py' src/fabrik/scaffold.py | head -3
1178:def _scaffold_python_api(project_dir: Path, name: str, description: str, **kwargs: object) -> None:
```
- **Read:** `src/fabrik/scaffold.py:1178` — `_scaffold_python_api` writes `<pkg>/internal_auth.py` (M2M), `<pkg>/metrics.py` + `/metrics`, `<pkg>/main.py` (FastAPI), `requirements.txt`. This is the backend to reuse, not reinvent.

### Steps
1. Extract the FastAPI-emitting core of `_scaffold_python_api` into `_scaffold_fastapi_backend(dest_dir, name, package_name)` (writes the package + requirements into `dest_dir`).
2. Repoint `_scaffold_python_api` to call it (no behavior change — same files, same content). Keeps one backend generator.

### Gate
`python -m pytest tests/ -k scaffold_python_api -q` (existing python-api scaffold tests still green) · `python scripts/final_gate.py --json`.

---

## Phase 1 — saas-skeleton emits the backend under `server/`

### Evidence
```
$ grep -nE 'def _scaffold_saas_skeleton' src/fabrik/scaffold.py
1650:def _scaffold_saas_skeleton(
1771:def _scaffold_saas_skeleton_with_docs(
```
- **Read:** `src/fabrik/scaffold.py:1650` — `_scaffold_saas_skeleton` copies `templates/saas-skeleton/` (Next.js) + patches names; `:1771` `_with_docs` delegates to it. Today it emits **no backend**.

### Steps
1. In `_scaffold_saas_skeleton`, after the template copy, call `_scaffold_fastapi_backend(project_dir / "server", name, package_name)` → emits `server/src/<pkg>/...` + `server/requirements.txt`.
2. Add `server/Dockerfile` (python:3.12-slim, uvicorn) — mirror `python-api`'s Dockerfile.

### Gate
`python -m pytest tests/test_scaffold_saas_backend.py::test_emits_server -q` · `python scripts/final_gate.py --json`.

---

## Phase 2 — Multi-tenant DB schema (RLS, fail-closed)

### Evidence
The pack mandates the exact SQL:
```
$ grep -n 'current_tenant_id() RETURNS UUID\|ENABLE ROW LEVEL SECURITY\|FORCE ROW LEVEL' .windsurf/rules/saas/95-multi-tenant-saas.md
44:  CREATE OR REPLACE FUNCTION current_tenant_id() RETURNS UUID AS $$
```
- **Read:** `.windsurf/rules/saas/95-multi-tenant-saas.md:44` (the `current_tenant_id()` fail-closed fn) and `:23` (RLS `ENABLE`+`FORCE` + `tenant_isolation` policy).
- **Read:** `.windsurf/rules/core/75-workers-jobs.md:34` (`SELECT … FOR UPDATE SKIP LOCKED` dequeue), `:103` (`LISTEN/NOTIFY` worker wake-up) — fabrik's queue **is** PostgreSQL, no external broker.

### Steps
1. Emit `server/db/schema.sql`: `tenants` table; `current_tenant_id()` (NULLIF→deny); one example tenant-scoped table with `tenant_id UUID NOT NULL` + FK + B-tree index; `ALTER TABLE … ENABLE/FORCE ROW LEVEL SECURITY`; `CREATE POLICY tenant_isolation … USING (tenant_id = current_tenant_id())`.
2. Emit the **PG jobs queue** in the same schema: a `jobs` table (`id, tenant_id, type, payload jsonb, status, attempts, run_after, locked_at`) dequeued via `SELECT … FOR UPDATE SKIP LOCKED` + a `NOTIFY` on insert (instant wake-up) — the canonical fabrik queue (`75:34,103`); tenant-scoped (RLS) too.
3. `shape.needs_database` stays `true` so `fabrik apply` provisions the DB.

### Gate
`pytest tests/test_scaffold_saas_backend.py::test_rls_schema -q` (asserts `FORCE ROW LEVEL`, `current_tenant_id`, `tenant_isolation`) **and** `::test_jobs_queue_schema` (asserts the `jobs` table + `FOR UPDATE SKIP LOCKED`) · `final_gate.py --json`.

---

## Phase 3 — Tenant context propagation

### Evidence
- **Read:** `.windsurf/rules/saas/95-multi-tenant-saas.md:53` (Tenant Context Propagation): `SET LOCAL app.tenant_id` per **transaction**, FastAPI `ContextVar`, never pool-level; `:77` membership validation → 403.
```
$ grep -nE 'SET LOCAL app.tenant_id|ContextVar\("tenant_id"' .windsurf/rules/saas/95-multi-tenant-saas.md
55:- Set tenant context using `SET LOCAL app.tenant_id = '<uuid>'` at the start of every transaction
62:tenant_context: ContextVar[str] = ContextVar("tenant_id", default="")
```

### Steps
1. `server/src/<pkg>/tenant.py`: `tenant_context: ContextVar[str]`; middleware resolves tenant (JWT claim / `X-Tenant-ID`) → validates membership (403 if not a member) → sets the ContextVar.
2. A DB session dependency runs `SET LOCAL app.tenant_id = :tid` at txn start; document that developers write plain queries (RLS appends the filter).

### Gate
`pytest tests/test_scaffold_saas_backend.py::test_tenant_middleware -q` · `final_gate.py --json`.

---

## Phase 4 — Auth Pattern B + security headers + CORS

### Evidence
- **Read:** `.windsurf/rules/core/35-security-auth.md:43` (Pattern B — Supabase Auth + FastAPI validates Supabase JWT via JWKS), `:112` security headers (`Strict-Transport-Security`…), `:91` CORS from env (no `*` with credentials).
```
$ grep -nE 'scaffold is .saas-skeleton|X-Frame-Options: DENY' .windsurf/rules/core/35-security-auth.md
39:**Which pattern?** … If `shape` references Supabase or the scaffold is `saas-skeleton` / `mobile-app`, use Pattern B.
118:- `X-Frame-Options: DENY`
```

### Steps
1. `server/src/<pkg>/auth.py`: validate Supabase JWT via JWKS (FastAPI dependency); never issue own user tokens.
2. Security-headers ASGI middleware (precomputed HSTS / `nosniff` / `X-Frame-Options: DENY` / `Referrer-Policy`).
3. CORS origins from `CORS_ORIGINS` env. Auth-path rate limiting (per `35:182`). `internal_auth.py` reused from the backend helper (Phase 0).

### Gate
`pytest tests/test_scaffold_saas_backend.py::test_auth_and_headers -q` · `final_gate.py --json`.

---

## Phase 5 — API contracts (RFC 9457, versioning, casing)

### Evidence
```
$ grep -n 'RFC 9457\|/api/v1/\|application/problem' .windsurf/rules/core/15-api-contracts.md | head -3
40:## Error Schema (RFC 9457 — Problem Details)
```
- **Read:** `.windsurf/rules/core/15-api-contracts.md:40` (RFC 9457 `application/problem+json`), `:80` `/api/v1/` versioning, `:22` `to_camel` base model, `:57` `X-Idempotency-Key`.

### Steps
1. `server/src/<pkg>/main.py`: RFC 9457 exception handler (`application/problem+json`); mount business routes under `/api/v1/`; keep `/api/health` (unversioned) + `/metrics`.
2. Pydantic base model with `alias_generator=to_camel`, `populate_by_name=True`. `X-Idempotency-Key` accepted on the example mutation. One example tenant-scoped CRUD route (the wired pattern).

### Gate
`pytest tests/test_scaffold_saas_backend.py::test_api_contracts -q` · `final_gate.py --json`.

---

## Phase 6 — compose.yaml: three services (web + api + worker) + routing

### Evidence
```
$ sed -n '2,3p;22p' templates/saas-skeleton/compose.yaml
  web:
    build: .
          memory: 512M
$ sed -n '91p' src/fabrik/spec_generator.py
    "saas-skeleton": {"memory": "256M", "cpu": "0.5", "health_path": "/api/health"},
```
- **Read:** `templates/saas-skeleton/compose.yaml:2` (`web` service) + `:22` (memory limit pattern), `src/fabrik/spec_generator.py:91` (saas health path `/api/health`). **Routing nuance:** once `/api`→backend, `/api/health` is served by the **backend**, and the Next.js app uses Server Actions (not `/api` routes) — per `35:83`.
- **Read:** `src/fabrik/scaffold.py:2172` (`_scaffold_file_worker` — the canonical `worker/` adaptive-pool process fabrik already ships) + `.windsurf/rules/core/75-workers-jobs.md:205,213` (`scale_loop` ticks every 30s, scales the pool between `min`/`max` workers on PG queue depth). The worker is an **internal** service: it drains the `jobs` queue (Phase 2), so **no Traefik route, no Gatus, no public edge**.

### Steps
1. `templates/saas-skeleton/compose.yaml` + `.j2`: keep `web` (Next.js :3000, `Host(domain)`); add `api` service (`build: ./server`, FastAPI :8000, `Host(domain) && PathPrefix(/api)` at **higher priority** + `gzip@docker`). Both `deploy.resources.limits.memory` (web 512M, api 256M) on the `fabrik` net.
2. **Add a third `worker` service** (`build: ./server`, command runs the adaptive-pool worker reused from `_scaffold_file_worker` (`scaffold.py:2172`); reads the same shared `.env`; `deploy.resources.limits.memory: 512M`; on the `fabrik` net; **no Traefik labels, no published ports, no healthcheck route** — it is queue-driven, not request-driven). One worker process internally auto-scales its task pool on queue depth (`75:205,213`); it does double duty as the **beat scheduler** (Phase 8) for cron.
3. `/api/health` (Authelia-bypassed, public health_path) → backend; `api` container healthcheck → `localhost:8000/api/health`; `/metrics` scraped internally (`http://api:8000/metrics`), not via Traefik edge.
4. **Retarget the `web` container healthcheck** — it currently hits `localhost:3000/api/health` (`templates/saas-skeleton/compose.yaml:12`), which would 404 once `/api`→backend and Next.js uses Server Actions; change it to the frontend's own liveness (`localhost:3000/`).

### Gate
`pytest tests/test_scaffold_saas_backend.py::test_compose_services -q` (asserts `web` + `api` + `worker`, all three memory-limited, PathPrefix `/api` on `api`, **no** Traefik/ports on `worker`) · `final_gate.py --json` (`deployer_ssh._validate_compose` enforces the per-service memory limits — all three).

---

## Phase 7 — shape, required-files, proof_run, test

### Evidence
```
$ sed -n '228p' src/fabrik/scaffold.py
    "saas-skeleton": _SHARED_REQUIRED_FILES + ["compose.yaml"],
$ grep -n 'saas-skeleton' scripts/proof_run.py | head -2
53:    "saas-skeleton",
```
- **Read:** `src/fabrik/scaffold.py:228` (`TYPE_REQUIRED_FILES["saas-skeleton"]`), `scripts/proof_run.py:53` (saas in `SCAFFOLD_TYPES`), `:77` (`ACCEPT_CODES["saas-skeleton"]={200}`), `templates/saas-skeleton/defaults.yaml` `shape`.

### Steps
1. `defaults.yaml`: set `shape.has_bearer_api: true` (it now exposes an API).
2. `TYPE_REQUIRED_FILES["saas-skeleton"]` (`scaffold.py:228`): add `server/requirements.txt`, `server/Dockerfile`, `server/src/<pkg>/main.py` (structure-check teeth).
3. New `tests/test_scaffold_saas_backend.py` with the per-phase assertions referenced above (scaffolds to a tmp dir, inspects output).

### Gate
`pytest tests/test_scaffold_saas_backend.py -q` (all assertions) · `final_gate.py --json`.

---

## Phase 8 — Deploy services: shape flags + registrar wiring + jobs/cron tier

### Evidence
The `fabrik apply` registrars fire off shape flags:
```
$ sed -n '14,24p' src/fabrik/orchestrator/infrastructure.py
 postgres     shape.needs_database
 gatus        shape.is_public AND spec.domain set
 backrest     shape.has_persistent_data
 glitchtip    shape.kind in {service, worker, wordpress}
 authelia     shape.is_admin_dashboard AND spec.domain set
 meilisearch  shape.has_search_feature
 prometheus   shape.exposes_metrics AND spec.domain set
 redis        shape.needs_cache
```
- **Read:** `src/fabrik/orchestrator/infrastructure.py:23` (`prometheus ← exposes_metrics`), `:24` (`redis ← needs_cache`). The current saas shape sets **neither** (`templates/saas-skeleton/defaults.yaml` only declares `has_bearer_api: false`) → a saas gets no Prometheus scrape and no Redis today.
- **Read:** `src/fabrik/drivers/prometheus.py:248` — `register_target(service_name, domain, target=None, metrics_path)` defaults the scrape target to `<domain>:443`; the backend `/metrics` is **not** on the public edge in this multi-service compose, so an explicit `target=<project>-api:8000` is required.
- **Read:** `src/fabrik/orchestrator/deployer_ssh.py:197` — registrar-injected vars (`DATABASE_URL`/`REDIS_URL`/`GLITCHTIP_DSN`) merge into the project's **shared `.env`**; all three compose services read it via `env_file`, the backend + worker consume them (no per-service injection needed).
- **Read:** `.windsurf/rules/core/75-workers-jobs.md:205,213` (adaptive pool `scale_loop` — auto-expansion is **in-process**: one `worker` container scales its own task pool on PG queue depth between `min`/`max`, no container autoscaler needed) and `:131,135` (beat scheduler runs **single-leader** via `pg_advisory_lock` or Redis `SET NX EX` — so periodic/cron tasks fire once even if the worker is later scaled to N replicas). The worker's queue is Postgres (`needs_database`) and its beat lock is Redis (`needs_cache`) — both already provisioned by the Phase 8 shape flags. **Cron = the app beat scheduler, not `pg_cron`** (fabrik has no pg_cron registrar).
- **Read:** `src/fabrik/orchestrator/infrastructure.py:17` — `glitchtip ← shape.kind in {service, worker, wordpress}`; the saas project keeps `kind: service`, so the worker's unhandled exceptions report to the same GlitchTip project as the api (no separate spec).

### Steps
1. `templates/saas-skeleton/defaults.yaml` shape: add `exposes_metrics: true` (Prometheus scrapes the backend `/metrics`) and `needs_cache: true` (Redis for auth rate-limit + tenant cache, `95:103`/`35:182`); set `has_bearer_api: true`. Keep `needs_database`/`has_persistent_data`/`is_public: true`; **`is_admin_dashboard: false`** — end-user auth is Supabase, so **no Authelia registrar** (Authelia is admin-only, `35:43`).
2. Wire the Prometheus scrape to the **api** service: emit a stable `container_name` (compose service `api` on `:8000`, not a UUID — HARD-STOP) and have the orchestrator pass `target=<project>-api:8000`, `metrics_path=/metrics` to `register_target` (the explicit target, not the `<domain>:443` default).
3. `DATABASE_URL`/`REDIS_URL`/`GLITCHTIP_DSN` reach the backend **and the worker** via the shared `.env` (verified) — no per-service env wiring.
4. **Worker auto-expansion + cron** ship in `server/src/<pkg>/worker.py` (vendored from `_scaffold_file_worker`, `scaffold.py:2172`): the adaptive-pool `scale_loop` (`75:205,213`) drains the `jobs` queue and grows/shrinks the in-process pool on depth; a single-leader beat scheduler (`75:131` `pg_advisory_lock`) enqueues periodic/cron tasks. Env-tunable `WORKER_MIN`/`WORKER_MAX` (`os.getenv(...,default)`) — `needs_cache: true` (step 1) already provisions the Redis the beat lock can alternatively use (`75:135`).
5. No new registrar is needed for the worker: its queue rides `needs_database`, its lock rides `needs_cache`, its errors ride the project's `kind: service` GlitchTip — all already wired by steps 1–3. The worker is **not public** → it deliberately gets **no Gatus/Traefik/Prometheus-edge** entry.

### Gate
`pytest tests/test_scaffold_saas_backend.py::test_shape_drives_registrars -q` (asserts the shape flags) **and** `::test_worker_module_present` (asserts `server/src/<pkg>/worker.py` ships the `scale_loop` + beat single-leader) · `python scripts/final_gate.py --json` · the `fabrik plan` preview in Phase 9 confirms the registrar set.

---

## Phase 9 — Scaffold the project + test it (structural + `fabrik plan`)

### Evidence
```
$ grep -n 'def plan' src/fabrik/cli.py
246:def plan(spec_path: str, secrets: tuple):
```
- **Read:** `src/fabrik/cli.py:246` — `fabrik plan specs/services/<id>.yaml` previews which registrars fire (`resolve_applicability`, `src/fabrik/orchestrator/infrastructure.py:133`).

### Steps
1. **Create the scaffold folder:** `fabrik scaffold <name> --type saas-skeleton -d "…"` → `/opt/<name>` with `app/` (Next.js) **and** `server/` (FastAPI backend + worker) + a 3-service `compose.yaml`.
2. **Structural test** (the named pytest, scaffolds to a tmp dir): `server/src/<pkg>/{main,auth,tenant,internal_auth,metrics,worker}.py` present, `server/db/schema.sql` carries the RLS pattern **and the `jobs` queue** (`FOR UPDATE SKIP LOCKED`), `compose.yaml` has `web` + `api` + `worker` all memory-limited (worker with no Traefik/ports), `defaults.yaml` shape has the new flags.
3. **Deploy-preview test:** `fabrik plan specs/services/<name>.yaml` → confirm **postgres + redis + prometheus + gatus + glitchtip + backrest** are applicable and **authelia is NOT**. Tear the test project down (`fabrik destroy` + `rm`) after.

### Gate
`pytest tests/test_scaffold_saas_backend.py -q` (full structural suite) · `python scripts/final_gate.py --json` · `fabrik plan` shows the expected registrar set.

---

## Phase 10 — Live proof (ULTIMATE)

### Evidence
- **Read:** `scripts/proof_run.py:53` — `saas-skeleton` is in `SCAFFOLD_TYPES`; the harness scaffolds → pushes → `fabrik apply` → curls `/api/health`.
```
$ sed -n '52,53p;77p' scripts/proof_run.py
SCAFFOLD_TYPES = [
    "saas-skeleton",
    "saas-skeleton": {200},
```

### Steps
Run `PROOF_ONLY=saas-skeleton python scripts/proof_run.py` (after committing — proof_run deploys from the git remote, `proof_run.py:8`). Silence `ContainerDown` first (memory: silence-alerts-before-downtime); tear down the `fabrik-test-saas-skeleton` deploy after.

### Gate (ULTIMATE)
`curl -sI https://fabrik-test-saas-skeleton.vps1.ocoron.com/api/health` → **200** (the now-backend-served health) **AND** `scripts/final_gate.py --json` → `"status":"success"`. Both green = done.

---

## Self-audit (convergence floor)

| Claim / risk | Status | Grounding |
|---|---|---|
| Reuse python-api backend, not reinvent | ✓ | `scaffold.py:1178` emits internal_auth/metrics/main (Phase 0 EV) |
| saas emits no backend today (the gap) | ✓ | `_scaffold_saas_skeleton` `scaffold.py:1650` copies template only (Phase 1 EV) |
| RLS SQL is the pack's exact pattern | ✓ | `95-multi-tenant.md:44` `current_tenant_id()`, `:23` ENABLE/FORCE (Phase 2 EV) |
| Tenant context per-txn, not pool | ✓ | `95:53` (Phase 3); avoids the pooled-connection leak the pack warns of |
| Auth = Pattern B (Supabase JWT), saas type | ✓ | `35:43` "if scaffold is saas-skeleton, use Pattern B" (Phase 4 EV) |
| Errors RFC 9457 + `/api/v1` versioning | ✓ | `15:40`, `:80` (Phase 5 EV) |
| `/api/health` now served by backend (routing) | ✓ | `spec_generator.py:91` health path + PathPrefix routing — surfaced + handled (Phase 6), not assumed |
| Memory limits all three services (OOM invariant) | ✓ | `compose.yaml:22` pattern; `deployer_ssh._validate_compose` enforces web+api+worker (Phase 6 gate) |
| proof_run already expects saas → 200 | ✓ | `proof_run.py:53,77` (Phase 10 EV) |
| Shape flags drive the right registrars | ✓ | `infrastructure.py:23/24` — `exposes_metrics`→prometheus, `needs_cache`→redis (Phase 8 EV); saas shape updated, was missing both |
| Prometheus must target the api container, not the edge | ✓ | `prometheus.py:248` default `<domain>:443` is wrong for a 3-service compose → explicit `target=<project>-api:8000` (Phase 8) |
| Registrar env (DB/Redis/GlitchTip) reaches the backend + worker | ✓ | shared `.env` via `env_file`, `deployer_ssh.py:197` (Phase 8 EV) — backend + worker consume, web ignores |
| Background jobs ride a PG queue, no external broker | ✓ | `jobs` table + `FOR UPDATE SKIP LOCKED` in `server/db/schema.sql`, `75-workers-jobs.md:34,103` (Phase 2 EV) |
| Worker auto-expansion is in-process on queue depth | ✓ | adaptive-pool `scale_loop` `75:205,213` vendored from `_scaffold_file_worker` `scaffold.py:2172` (Phase 6/8 EV) — no container autoscaler |
| Cron = single-leader beat scheduler, not pg_cron | ✓ | `75:131` `pg_advisory_lock` (Redis `SET NX EX` alt `:135`) fires periodic tasks once; fabrik has no pg_cron registrar (Phase 8 EV) |
| Worker is internal — no public edge | ✓ | `worker` service has no Traefik/ports/Gatus; queue-driven not request-driven (Phase 6 step 2, Phase 8 step 5) |
| No Authelia for end-user saas | ✓ | `is_admin_dashboard=false` → authelia registrar skipped (`infrastructure.py:19`); Supabase is the end-user IdP |
| Scaffold folder actually created + tested | ✓ | Phase 9 — `fabrik scaffold` → structural pytest + `fabrik plan` registrar preview (`cli.py:246`) |
| Comprehensive gate (not `--lean`) — fabrik code | ✓ | this is a `/opt/fabrik` change; `final_gate.py --json` + proof_run named per phase |

**Known deferred (lean — documented extension points, not unknowns):** signup abuse-detection (`87`, vendor the module), billing UI (`60:160`), custom-domain per-tenant (`95:71`), full page inventory beyond login/dashboard. Each is a *choice* with a pack to follow, not a gap in the scaffold's spine.

**Unhandled edge cases surfaced & assigned:** Next.js `/api/*` routes shadowed by the backend → frontend uses Server Actions (Phase 6, `35:83`); **`web` container healthcheck hit `/api/health` (now backend) → retargeted to `localhost:3000/`** (Phase 6, `compose.yaml:12`); `/metrics` not on the Traefik edge → scraped internally (Phase 6); `package_name` derivation for `server/src/<pkg>/` → reuse `python-api`'s existing slugify (Phase 0); Phase 0 extraction must not change `python-api` output → its scaffold tests gate it (Phase 0 gate).

## Evidence index

Per-phase `### Evidence` blocks (path:line + fenced command output): Phase 0 (`scaffold.py:1178`), 1 (`:1650`), 2 (`95-multi-tenant.md:44`), 3 (`95:53`), 4 (`35:43/:112`), 5 (`15:40`), 6 (`compose.yaml:2`, `spec_generator.py:91`), 7 (`scaffold.py:228`), 8 (deploy services — `infrastructure.py:14-24`, `prometheus.py:248`, `deployer_ssh.py:197`), 9 (scaffold + test — `cli.py:246`), 10 (live proof — `proof_run.py:53`). Gate model grounded above.
