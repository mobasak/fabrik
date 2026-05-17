# The Fabrik Lifecycle — Canonical 4-Stage Reference

**Last verified:** 2026-05-16 | **Canonical source:** this file supersedes any vision narrative pasted into individual tickets.
**Maintenance:** This file is in the doc-sync memory set. Every session that changes the deployer, registrars, scaffold system, or VPS infrastructure MUST update this file. Enforced by `scripts/final_gate.py` check for significant changes to `src/fabrik/orchestrator/`, `src/fabrik/scaffold.py`, or `src/fabrik/drivers/`.

---

## Stage 1 — Intent & Scaffolding (WSL)

Everything begins in WSL Ubuntu. You initiate a project using `fabrik scaffold` (or, since T3-01: `fabrik preplan new <slug>` BEFORE scaffold to capture intent).

This isn't just folder creation; it's a **Context Injection**:

- **Type-appropriate source layout.** Each of the 11 scaffold types (`python-api`, `node-api`, `saas-skeleton`, `file-api`, `file-worker`, `wordpress`, `docusaurus`, `chrome-extension`, `mobile-app`, `desktop-app`, `static-site`) emits the directory structure its runtime demands — `src/<name>/` for Python APIs, `extension/` for Chrome, `electron/` for desktop, `worker/` for background processors, etc.
- **Standard dirs** every type shares: `docs/`, `scripts/`, `tests/`, `config/`, `data/`, `db/`, `logs/`, `.tmp/`, `.cache/`, `output/`.
- **The AI guardrails.** The scaffolder populates 6 governance files: `AGENTS.md` (Traycer planner), `CLAUDE.md` (Claude Code), `AGENTS-compact.md` (Kilo CLI), `KILO_CLI_RULES.md` (Kilo spec-contract awareness), `.windsurfrules` (Windsurf Cascade), and `opencode.json` (Kilo bootstrap config). Plus the full `.windsurf/rules/` directory (21 packs covering Python, TypeScript, ops, security, observability, payments, etc.). All pre-loaded with VPS1 inventory + shape/registrar awareness so agents never hallucinate `localhost` databases or invent auth patterns.
- **Reference docs.** `docs/reference/technology-stack-decision-guide.md`, `docs/reference/AI_TAXONOMY.md`, `docs/reference/fabrik-lifecycle.md` (this file), `docs/reference/windsurf/cascade-models.md`, `docs/reference/long-command-monitoring.md` — all synced to every project via `scripts/sync_enforcement_to_projects.py`.
- **The spec.** `specs/services/<id>.yaml` is emitted with a `shape:` block derived from `templates/<type>/defaults.yaml`. The shape block is the deploy contract — it declares which registrars `fabrik apply` will activate.

### Project-type architecture note

| Family | Deploy target | Stage 3 path |
|---|---|---|
| Backend services (`python-api`, `node-api`, `file-api`, `file-worker`) | VPS via Coolify (compose.yaml + Dockerfile) | Full registrar set |
| Frontends (`saas-skeleton`, `static-site`, `docusaurus`) | VPS via Coolify (compose or static serve) | Lean registrar set (no postgres/redis typically) |
| WordPress (`wordpress`) | VPS via Coolify (multi-container: php-fpm + nginx + db + redis + backup) | WordPress-specific registrar flow |
| Mobile apps (`mobile-app`) | Two-faced: **backend deploys to VPS/Supabase/Backblaze**, client ships via App Store/Play Store | Backend gets registrars; client is built locally |
| Desktop apps (`desktop-app`) | Two-faced: **installer distributed FROM the VPS**, app runs on user machine | Download-server deployed; Electron app built locally |
| Chrome extension (`chrome-extension`) | Two-faced: **FastAPI backend deploys to Coolify**, TS extension uploaded to Chrome Web Store | Backend gets full registrar set; extension is browser-side |

---

## Stage 2 — Agentic Implementation (WSL)

You execute work through **Ticket Design** via the Traycer workflow: `trigger-workflow → epic-brief → core-flows → tech-plan → deploy-plan → ticket-outline → ticket-breakdown → execute → implementation-validation → deploy`. You present structured tickets to your agents (Claude Code, Windsurf Cascade, Kilo CLI). Because they have the guardrail files (propagated via `scripts/sync_enforcement_to_projects.py` to all 43 projects), they write code that is **Infrastructure-Aware:**

- They don't just write a Dockerfile; they write a `specs/services/<id>.yaml` whose `shape:` block declares the specific registrars needed — which Coolify app, which Gatus endpoint, which Prometheus scrape target, which GlitchTip project.
- If code adds a database call → `shape.needs_database` MUST be `true` in the spec.
- If code exposes `/metrics` → `shape.exposes_metrics` MUST be `true`.
- The `## Spec contract awareness` snippet (T3-02) lives in every executor file and enforces this at code-writing time — not deploy time.

**Architectural mandates (enforced at planning time via Traycer workflow):**

- **12-Factor App compliance** — every service satisfies [The Twelve-Factor App](https://12factor.net/) methodology. Config via env vars only. Stateless processes. Structured logs to stdout. Fast startup + graceful SIGTERM. Same image in dev and prod.
- **Concurrency** — every service handles multiple simultaneous requests (uvicorn workers / async handlers / node cluster / worker pool). Never single-threaded blocking.
- **i18n** — every GUI/user-facing service supports multi-language from day one. Default: English (en). Second: Turkish (tr). Adding a language = adding a locale file, zero code changes.
- **Resilience** — every external call has timeout + retry with backoff. Circuit-breaker for repeated failures. Graceful fallback when dependencies are down. `/health` tests ALL real deps.

**Local dev loop (T3-03):** `fabrik dev -d` starts the `compose.dev.yaml` stack; `fabrik logs --local -f` tails it; `fabrik review` bundles `git diff` + spec + resolved registrars for review dispatch. All in-WSL, sub-second feedback.

**External services available (use before building custom):**

| Need | Use | Address |
|---|---|---|
| Database | PostgreSQL 16 | `postgres-main:5432` |
| Cache/Queue | Redis 7 | `redis-main:6379` |
| Search | MeiliSearch | `search.vps1.ocoron.com` (port 7700 internal) |
| File storage | Backblaze B2 | S3-compatible API |
| PDF generation | Gotenberg | `pdf.vps1.ocoron.com` |
| Notifications | Apprise | `notify.vps1.ocoron.com` |
| Automation | n8n | `auto.vps1.ocoron.com` |
| Headless browser | Browserless | `browser.vps1.ocoron.com` |
| Auth (admin) | Authelia | forward-auth 2FA |
| Auth (user-facing) | Supabase Auth | managed auth + realtime + pgvector |
| Error tracking | GlitchTip | `errors.vps1.ocoron.com` (SENTRY_DSN) |
| Backups | Backrest → Backblaze B2 | `backup.vps1.ocoron.com` |

---

## Stage 3 — Proper Registration (VPS deploy via Coolify API)

When you run `fabrik apply specs/services/<id>.yaml` from WSL, the CLI performs a multi-stage orchestration via the Coolify API:

**The Bridge:** It doesn't run code in WSL. It tells VPS1 (via API) to pull the build from the GitHub remote (which is why `git push` MUST precede `fabrik apply` for git-sourced apps).

**Auto-Registration (the 9 registrars, shape-gated):**

| Registrar | What it does | Mechanism |
|---|---|---|
| **postgres** | Creates a logical DB on `postgres-main` + registers in `allocations.json` (T4-01) | SSH → `docker exec psql` |
| **redis** | Assigns a logical DB index on `redis-main` | SSH → assignments.json |
| **gatus** | Pushes a new endpoint monitor → `status.vps1.ocoron.com` | SSH → gatus config dir |
| **backrest** | Creates a restic backup plan | SSH → backrest config.json |
| **glitchtip** | Creates a GlitchTip project + injects `SENTRY_DSN` into Coolify env vars | GlitchTip API + Coolify API |
| **grafana** | Stamps a deploy annotation | Grafana API |
| **authelia** | Adds an access-control rule for admin dashboards / paired-pattern | SSH → authelia configuration.yml + container restart |
| **meilisearch** | Creates a search index | Meilisearch API |
| **prometheus** | Adds a scrape target to `prometheus.yml` | SSH → prometheus config + reload |

**Observability (auto, no per-service action needed):**

- **Promtail** → Loki: auto-discovers ALL containers via docker.sock. No labels or config changes needed per service.
- **cAdvisor** → Prometheus: auto-discovers ALL containers via docker.sock. Per-container CPU/memory/network metrics flow without any registration.
- **Netdata:** fleet-wide host-level observer (not per-container; runs alongside the above). Dashboard at `netdata.vps1.ocoron.com`.

**Network security (auto, defense-in-depth):**

- **UFW:** 14 rules — allows SSH (22), HTTP (80), HTTPS (443), OpenVPN (1194), Coolify Realtime (6001-6002). Denies Coolify raw port (8000).
- **DOCKER-USER iptables chain:** 9 rules via `iptables-docker-user.service` (systemd, runs after `docker.service`). Docker bypasses UFW by inserting NAT rules — this chain catches what UFW misses. Allows: established connections, container-to-container (10.0/8, 172.16/12, 192.168/16), ports 80/443/6001/6002. **Catch-all DROP** on everything else. Even if a container accidentally publishes `0.0.0.0:8080`, external traffic is dropped. Source: `/etc/iptables/add-docker-user-rules.sh` (idempotent, flushes + re-applies on every boot).
- **No per-service firewall action needed.** All containers route through Traefik on the `coolify` network; no host port bindings. The iptables chain is a safety net, not a per-deploy concern.

**Resource limits (F5 fix):** Every `compose.yaml` emitted by the scaffolder includes `deploy.resources.limits.memory` + `cpus` (Coolify v4.0.0-beta.459 ignores its `limits_memory` UI field for `build_pack=dockercompose` apps — the compose must carry the declaration explicitly).

**Coolify v4 workarounds (built into `deployer.py`):**

- **SSH fallback build (Fix 2):** Coolify's silent build-trigger bug (#9161) sometimes writes the compose but never builds the image. After 300s grace, the deployer SSHs to VPS, clones the repo into `/data/coolify/applications/<uuid>/`, builds using Coolify's own compose, and starts the container.
- **`.env` pre-seed (Fix 3):** Coolify injects `env_file: .env` into compose but doesn't create the file before `docker compose config` runs. The deployer `touch`es it via SSH immediately after app creation.
- **Destroy hardening:** `_destroy_coolify` runs SSH `docker compose down` before the API DELETE (handles containers started by the SSH fallback).

**Postgres allocation registry (T4-01):** Every `create_database` call registers the DB in `/opt/monitoring/configs/postgres/allocations.json`. `audit_postgres` cross-references this against live `pg_database` to detect drift (orphan DBs or stale registry entries).

**Portability (T4-03):** `fabrik export --out <tarball>` captures the full VPS registration state (specs, state files, Coolify apps/services with UUIDs stripped, monitoring configs, Authelia/Backrest configs with secrets redacted, redacted .env key list). `fabrik import <tarball>` provides a rebuild scaffold for a fresh target VPS (import path shipped untested; roundtrip deferred to vps2 stand-up).

---

## Stage 4 — Verification & Testing

Once the Coolify build is green, verification runs from WSL against the live VPS1 endpoint:

**Implemented (T2-02 + T4-04):**

- `fabrik verify <domain> --spec registrars` — postcondition gate; fails on any `missing` registrar.
- `fabrik audit-registrars [--json]` — fleet-wide pivot table of all 9 registrars × all specs.
- `fabrik reconcile-all [--filter <substr>] [--yes]` — re-runs `refresh_infrastructure` per spec across the fleet. Converges drift to zero.
- **Hourly drift detection (T4-04):** WSL cron (`scripts/audit_all_registrars.py`) pushes `fabrik_audit_drift_total` gauge to VPS-local pushgateway → Prometheus alert rule `FabrikRegistrarDrift` (`for: 10m`) → Alertmanager route `alert_class=registrar_drift` → existing `telegram` receiver. Detection latency: ≤71 minutes.
- `fabrik destroy --use-state` (T4-02) — if teardown is needed, replays from state file (not current shape) so spec-drift doesn't orphan registrars. Data-bearing protection requires explicit `--drop-data`.
- `scripts/vps_apply_limits.sh` — run after VPS reboot or Coolify redeploys to re-apply Docker memory limits (Coolify drops them on container restart). Also applies stable Docker network aliases for single-image Applications.

**Open (next ticket):**

- **Auto-rollback:** `verify.py:394` — if the health check or GlitchTip integration fails post-deploy, trigger `destroy_from_state(state.load(spec.id))` automatically. The wire is mechanically possible (T4-02 exports `destroy_from_state`); the orchestrator just needs to call it from the verify-failure path.

---

## Summary of what the scaffolder emits for Stage 3

The scaffolder's `_write_canonical_compose` function (the authoritative compose generator) emits for every Coolify-deployed type:

1. **Traefik labels** in `compose.yaml` — `Host(...)` routing rule, `websecure` entrypoint, LetsEncrypt cert resolver. These ARE Docker labels because Traefik's service-mesh discovery is label-based.
2. **`deploy.resources.limits`** in `compose.yaml` — memory + CPU cap that Docker enforces (F5 fix).
3. **Healthcheck** in `compose.yaml` — HTTP or process probe that Coolify uses to gate deploy success.

The scaffolder does NOT emit Prometheus/Promtail/cAdvisor labels or configs per service — those are handled by the **registrar system** at `fabrik apply` time (prometheus registrar) or by **auto-discovery** (Promtail, cAdvisor via docker.sock). This is a deliberate architecture decision: compose.yaml is the build/deploy contract; observability config is the registrar's domain.

For admin-dashboard types (`shape.is_admin_dashboard: true`), the scaffolder also emits `authelia-forward@docker` middleware in Traefik labels — the Authelia registrar then adds the corresponding access-control rule to the Authelia configuration on `fabrik apply`.
