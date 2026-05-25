# YouTube Pipeline — Modernization Vision

> **Status:** Pre-planning. Captures verified current state + the architectural fork that must be resolved before any modernization ticket is opened.
> **Last verified:** 2026-05-17 by direct file reads in `/opt/youtube/` from `/opt/fabrik/` (no review-summary trust).
> **Authoritative for:** `00-vision.md` only. Tickets, breakdowns, and execute steps live in sibling files once the fork is resolved.

---

## What We're Building

YouTube Pipeline is a **multi-tenant transcript + comments + audio SaaS** for the Tojlo brand. Users submit YouTube URLs → the pipeline extracts metadata, fetches captions (or transcribes audio via Soniox), mines comments, stores everything in a per-user content tree, and offers a Flask web dashboard (login, library, watchlists, payments via Paddle, teams, projects, settings).

The product is **live in production** under `youtube.vps1.ocoron.com`. The modernization scope is **not "build the product"** — it's "align the production deployment topology with the Fabrik python-api scaffold conventions so it gets the same observability, resilience, and 12-Factor guarantees as every other Fabrik service."

---

## The Architectural Fork (must resolve before any ticket)

**Verified contradiction:** the Coolify-deployed FastAPI on port 8029 (`src/youtube/main.py`, 109 lines, two endpoints: `/health` + `/`) is **not** the real product. The real product is `dashboard/app.py` — Flask, 256 KB / ~7000 lines, 28 templates, all user-facing routes (login, register, library, pricing, video, watchlists, teams, settings, projects, payment_success, Stripe webhooks). Flask runs ad-hoc via `nohup` (`dashboard/run.sh` and `scripts/dashboard.sh`), with **no Traefik label, no Coolify entry, no systemd unit, no restart-on-reboot**.

Whatever serves `youtube.vps1.ocoron.com → :5000` (Flask) today does so via VPS-level proxy plumbing outside the repo. The Coolify container is an empty FastAPI shell.

### Three forks (pick one before opening tickets)

| Fork | What it means | Effort | Pro | Con |
|:--|:--|:--|:--|:--|
| **A. Flask → FastAPI Jinja templates** | Port the 7000-line `dashboard/app.py` into `src/youtube/main.py` routes. Translate Flask `render_template` → FastAPI `Jinja2Templates`. One web app, one container, one framework. | Weeks. 28 templates, Flask-Login, Flask-Limiter, payments, auth — all need rewriting. | True alignment with `python-api` scaffold. One framework. Observability + resilience apply to the real product. | High-risk migration of payments/auth/library. Likely regressions. Time better spent elsewhere if Flask is "good enough". |
| **B. Containerize Flask, replace FastAPI** | Add Flask service to `compose.yaml` (new Dockerfile entry or replace existing CMD). Drop FastAPI shell. Traefik points to Flask. | Days. | Smallest change; ships the alignment fast. Real product gets compose-managed restart, healthcheck, resource limits, registrar coverage. | Repo says "python-api" scaffold but ships Flask — scaffold type lies. May need a new scaffold type or accept the lie. |
| **C. Multi-container compose** | `app-api` (FastAPI for `/api/*`) + `app-web` (Flask for `/`). Traefik path-routes. Both healthcheck'd. | Week. | Hedges. Lets FastAPI grow into the API surface while Flask stays the GUI. Future migration to Fork A is gradual. | Most complex compose. Two web frameworks long-term. Doubled resource limits. |

**Recommendation:** Fork **B** if the Flask app is stable and the goal is alignment, not framework purity. Fork **C** if you anticipate API consumers (mobile app, n8n workflows, public API) within 6 months. Fork **A** only if you have weeks and zero feature roadmap pressure.

---

## Verified Current State (ground truth — direct file reads 2026-05-17)

### Deployment topology

| Process | How it starts | Where it lives | Reachable as | Verified |
|:--|:--|:--|:--|:--|
| FastAPI (`src/youtube/main.py`) | `compose.yaml` → Coolify → `uvicorn youtube.main:app` | Container on `coolify` network | `youtube.vps1.ocoron.com` via Traefik label — but only `/health` + `/` | ✅ |
| Flask dashboard (`dashboard/app.py`) | `nohup python3 app.py` via `dashboard/run.sh` or `scripts/dashboard.sh` | Bare-metal VPS, port 5000 | `localhost:5000` only; not Traefik-labelled | ✅ |
| Celery worker (`worker/celery_app.py`) | `youtube-worker.service` systemd unit → `scripts/start_worker.sh` | Bare-metal systemd. **User=`ozgur`** (per user; not `www-data` as the repo's unit file shows — VPS reality differs from repo). | N/A | ⚠️ Repo says `www-data`, user says `ozgur` runs in production. Repo file likely stale. |
| Celery Beat | `scripts/start_beat.sh --detach` | Bare-metal background process. No systemd unit in repo. | N/A | ✅ |
| `scripts/start_dashboard_workers.sh` | Dead code — references `/opt/youtube/workers/` (dir exists but empty) | N/A | N/A | ✅ Dead. Plus leaks `PGPASSWORD=yt_secure_2025` on line 94. |
| Duplicate dashboard launchers | `dashboard/run.sh` AND `scripts/dashboard.sh` — both `nohup` Flask | N/A | N/A | ✅ Duplication. Pick one. |

### Verified 12-Factor violations

| # | Factor | File:line | Evidence | Severity |
|:--|:--|:--|:--|:--|
| 1 | III (Config) | `dashboard/app.py:20` | `load_dotenv('/opt/youtube/.env')` — hardcoded absolute path | High |
| 2 | III (Config) | `dashboard/app.py:21` | `sys.path.insert(0, '/opt/youtube')` — hardcoded absolute path | High |
| 3 | III (Config) | `scripts/start_dashboard_workers.sh:94` | `PGPASSWORD=yt_secure_2025` hardcoded **AND pushed to public/private GitHub** | **Critical — credential rotation required** |
| 4 | III (Config) | `dashboard/app.py:37` | `'dev-secret-key-change-in-production-2025'` as default for `FLASK_SECRET_KEY` | Medium |
| 5 | VI (Processes) | `compose.yaml` + `Dockerfile:49` | FastAPI started with no `--workers N` → single uvicorn process | Medium (FastAPI is shell; not blocking real users) |
| 6 | VIII (Concurrency) | `Dockerfile:49` | Single uvicorn process | Medium |
| 7 | IX (Disposability) | `dashboard/run.sh`, `scripts/dashboard.sh` | `nohup` Flask has no restart-on-reboot, no graceful SIGTERM path | High |
| 8 | IX (Disposability) | No systemd unit for Beat | `start_beat.sh --detach` only — won't survive reboot | High |

### Verified resource limits

- `compose.yaml` has **no `deploy.resources.limits`** block. Coolify v4.0.0-beta.459's UI field doesn't propagate to compose for `build_pack=dockercompose`. F5 fix required.
- `youtube-worker.service` has no `MemoryLimit=` directive → can OOM the VPS.

### Verified external dependencies (from `docs/reference/pipeline-resilience.md`, 398 lines, already documents resilience semantics)

| # | Dependency | Resilience already documented? |
|:--|:--|:--|
| 1 | IPRoyal residential proxy (pool + bandwidth) | ✅ Two pause keys, TTLs, autosnapshot Beat |
| 2 | YouTube Data API + bot detection | ✅ Pause key, IP rotation cooldown |
| 3 | Network / DNS | ✅ Pause key, 30s TTL |
| 4 | SSL / mid-stream | ✅ Documented |
| 5 | PostgreSQL (`postgres-main:5432`) | ✅ SSL EOF mitigation in `celery_app.py:221` |
| 6 | Redis (`redis-main:6379`) | ✅ Broker + result backend; orphan sweep mitigates outages |
| 7 | Apify (audio downloader) | ✅ Concurrency=12, throttle in `apify_throttle.py` |
| 8 | Soniox (transcription) | ✅ Balance check Beat, $5 floor |
| 9 | Paddle (payments) | Partial — webhooks exist; no documented retry policy |
| 10 | YouTube oEmbed / yt-dlp | Documented via pipeline-resilience |
| 11 | Backblaze B2 (file storage) | Partial — migration script exists, no resilience cards |
| 12 | DeepL / Azure (translator) | Partial — used by dashboard, no resilience cards |
| 13 | GlitchTip (error tracking) | Optional (commented out in `.env.example`) |

**Resilience backfill effort:** mechanical translation of `pipeline-resilience.md` into the canonical `docs/RESILIENCE.md` template. Mostly copy-paste with section renames.

---

## Service Architecture

### Current

```
┌───────────────────────────────────────────────────────────┐
│                  USER (Browser)                            │
│                       ↓                                    │
│      youtube.vps1.ocoron.com   ←─ Traefik (in Coolify)     │
│                       ↓                                    │
│   ┌───────────────────────┴────────────────────────────┐   │
│   │  FastAPI :8029  (Coolify-managed, has Traefik)     │   │
│   │  src/youtube/main.py — 2 endpoints, EMPTY SHELL    │   │
│   └─────────────────────────────────────────────────────┘  │
│                                                            │
│   ─────────── parallel, NOT Traefik-routed ─────────────   │
│                                                            │
│   ┌─────────────────────────────────────────────────────┐  │
│   │  Flask :5000  (nohup, NO systemd, NO Traefik)       │  │
│   │  dashboard/app.py — REAL PRODUCT, 7000 lines        │  │
│   │  Login, library, payments, watchlists, 28 templates │  │
│   └─────────────────────────────────────────────────────┘  │
│                                                            │
│   ┌─────────────────────────────────────────────────────┐  │
│   │  Celery worker (systemd, prefork=24)                │  │
│   │  Queues: default, transcripts, comments, audio      │  │
│   └─────────────────────────────────────────────────────┘  │
│                                                            │
│   ┌─────────────────────────────────────────────────────┐  │
│   │  Celery Beat (--detach, NO systemd)                 │  │
│   │  6 periodic tasks: watchlists, retry, balance, etc. │  │
│   └─────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────┘
       ↓ talks to ↓
  postgres-main:5432 · redis-main:6379 · YouTube API · Apify
  · Soniox · IPRoyal · Paddle · Backblaze B2 · GlitchTip
```

### Proposed (Fork B — recommended default)

```
┌───────────────────────────────────────────────────────────┐
│                  USER (Browser)                            │
│                       ↓                                    │
│      youtube.vps1.ocoron.com   ←─ Traefik                  │
│                       ↓                                    │
│   ┌─────────────────────────────────────────────────────┐  │
│   │  Flask :5000  (Coolify-managed, Traefik-routed)     │  │
│   │  dashboard/app.py — single web service              │  │
│   │  deploy.resources.limits: 1G / 1.0 cpu              │  │
│   └─────────────────────────────────────────────────────┘  │
│                                                            │
│   ┌─────────────────────────────────────────────────────┐  │
│   │  Celery worker (Coolify-managed, prefork=12)        │  │
│   │  deploy.resources.limits: 4G / 2.0 cpu              │  │
│   └─────────────────────────────────────────────────────┘  │
│                                                            │
│   ┌─────────────────────────────────────────────────────┐  │
│   │  Celery Beat (Coolify-managed, singleton)           │  │
│   │  deploy.resources.limits: 256M / 0.25 cpu           │  │
│   └─────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────┘
```

Three compose services. systemd unit `youtube-worker.service` decommissioned. `nohup` launchers (`dashboard/run.sh`, `scripts/dashboard.sh`) deleted. FastAPI shell deleted (or kept as `/api/*` for Fork C).

---

## Modernization Phases (sized for slow weekly cadence)

| Phase | What | Why this order | Estimated tickets |
|:--|:--|:--|:--|
| **0. Security** | Rotate `yt_secure_2025`. Delete `scripts/start_dashboard_workers.sh`. Audit git history for other secrets. Update `.env`, Coolify env, `youtube-worker.service` `EnvironmentFile`. | Credential leak is unbounded blast radius. Must precede everything. | 1 |
| **1. Fork decision** | Document A/B/C choice in `01-fork-decision.md`. Owner: human (Özgür). | Without this, nothing else is plannable. | 0 (decision doc) |
| **2. Resilience backfill** | Translate `docs/reference/pipeline-resilience.md` → `docs/RESILIENCE.md` per `.windsurf/rules/core/58-resilience.md` template. Add §2b cards for Paddle, B2, DeepL/Azure (3 missing). | Pure docs work; safe; can run in parallel with anything else; gives RESILIENCE rule pack something to point at. | 1 |
| **3. Spec emission** | Fabrik (`/opt/fabrik`) emits `specs/services/youtube.yaml` with `shape:` block: `kind=service, is_public=true, has_persistent_data=true, needs_database=true, exposes_metrics=true, has_search_feature=false, is_admin_dashboard=false, coolify.alias=youtube`. | Spec is the deploy contract; everything downstream (registrars, monitoring) keys off it. Fabrik-side work, not youtube-side. | 1 |
| **4. Compose hardening** | Add `deploy.resources.limits.memory + cpus` to `compose.yaml` per F5 fix. Add `MemoryLimit=` to `youtube-worker.service` until it's decommissioned in Phase 6. | Independent of fork; immediate OOM protection. | 1 |
| **5. 12-Factor cleanup** | Fix `dashboard/app.py:20-21` (relative paths). Fix `dashboard/app.py:37` (require `FLASK_SECRET_KEY` from env, fail if missing in production). Add `--workers N` to FastAPI CMD (if FastAPI survives the fork). | Application-level fixes; safe to do regardless of fork. | 2 |
| **6. Topology migration** | Fork-dependent. B: containerize Flask, decommission systemd worker, decommission Beat `--detach`. C: multi-container. A: rewrite. | Biggest blast radius — runs last. | 2–5 |
| **7. Observability** | Run `fabrik apply` → registrars wire Gatus + GlitchTip + Prometheus scrape + Backrest + Grafana annotation. Verify via `fabrik verify youtube.vps1.ocoron.com --spec registrars`. | Auto once Phase 3 spec is correct + Phase 6 lands. | 1 |
| **8. Preplan + lessons** | Write forward preplan `docs/preplans/2026-05-17-youtube-scaffold-modernization.md`. Update `docs/LESSONS_LEARNT.md` with anything novel discovered. | Closes the loop; T3-01 G-A4 layer expects it. | 1 |

**Total:** ~9–12 tickets across 3–5 weeks at the stated "one week, slowly" pace.

---

## Open Questions (need human input before tickets)

| # | Question | Blocks |
|:--|:--|:--|
| Q1 | Fork A / B / C? | Phase 6, partially Phase 3 |
| Q2 | Is `github.com/mobasak/youtube-pipeline` public or private? Public → `git filter-repo` needed. Private → rotation + delete is sufficient. | Phase 0 |
| Q3 | If Fork B: keep `src/youtube/` (FastAPI) as dead code, or `git rm` the directory? | Phase 6 cleanup |
| Q4 | If Fork C: what's the path split? `/api/*` → FastAPI feels obvious. Anything else? | Phase 6 design |
| Q5 | Beat: keep as `--detach` background process (and accept reboot-fragility), or compose it? Recommendation: compose, singleton. | Phase 6 |
| Q6 | systemd worker user: confirmed `ozgur` in production (user clarified). Repo file says `www-data` — update repo to match, or document as VPS-only override? | Phase 4 hygiene |

---

## Success Criteria

| Metric | Target | How measured |
|:--|:--|:--|
| `compose.yaml` carries `deploy.resources.limits` | Yes | grep |
| Real product (Flask) is Coolify-managed with Traefik label | Yes | `docker inspect` on container with `youtube.vps1.ocoron.com` Host rule |
| Real product survives VPS reboot without human action | Yes | `reboot` test, wait 5 min, hit `/health` |
| `yt_secure_2025` removed from working tree + rotated on Postgres | Yes | `grep -rn yt_secure_2025` returns 0; new password works |
| `docs/RESILIENCE.md` exists per template, all 13 deps covered | Yes | File check + dep list match |
| `specs/services/youtube.yaml` exists with shape block | Yes | File check |
| All 9 registrars green for youtube | Yes | `fabrik verify youtube.vps1.ocoron.com --spec registrars` |
| No 12-Factor violations on the verified list | Yes | Manual recheck per row |
| Celery Beat survives reboot | Yes | Reboot test |
| systemd `youtube-worker.service` decommissioned (Fork B/C) | Yes | `systemctl status` reports `inactive`; unit file removed from repo |

---

## Reference Files

| What | Where | Status |
|:--|:--|:--|
| This vision doc | `docs/development/plans/youtube/00-vision.md` | ✅ Written |
| Fork decision | `docs/development/plans/youtube/01-fork-decision.md` | 🆕 To write after Q1 |
| Forward preplan | `/opt/youtube/docs/preplans/2026-05-17-youtube-scaffold-modernization.md` | 🆕 Phase 8 |
| Resilience canonical | `/opt/youtube/docs/RESILIENCE.md` | 🆕 Phase 2 |
| Resilience source (current) | `/opt/youtube/docs/reference/pipeline-resilience.md` | ✅ Exists, 398 lines |
| Spec | `/opt/fabrik/specs/services/youtube.yaml` | 🆕 Phase 3 (Fabrik-side) |
| Fabrik lifecycle | `/opt/fabrik/docs/reference/fabrik-lifecycle.md` | ✅ Reference |
| Resilience rule pack | `/opt/fabrik/.windsurf/rules/core/58-resilience.md` | ✅ Reference |
| python-api scaffold | `/opt/fabrik/src/fabrik/scaffold.py` | ✅ Reference (preplan layering added T3-01) |

---

## What is explicitly NOT in scope

- **RAG / vector search.** Deferred. Not part of this modernization.
- **Flask → FastAPI rewrite** (unless Fork A is picked).
- **Multi-VPS support** — single VPS for foreseeable future.
- **Schema / migration changes.** Database is stable.
- **New product features.** Modernization only.
- **`DATABASE_URL` consolidation** (replacing `DB_HOST`/`DB_PORT`/`DB_USER`/`DB_PASSWORD`). Touches main connection path; deferred to a separate epic.
