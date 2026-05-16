# The Fabrik Lifecycle — Canonical 4-Stage Reference

**Last verified:** 2026-05-16 | **Canonical source:** this file supersedes any vision narrative pasted into individual tickets.

---

## Stage 1 — Intent & Scaffolding (WSL)

Everything begins in WSL Ubuntu. You initiate a project using `fabrik scaffold` (or, since T3-01: `fabrik preplan new <slug>` BEFORE scaffold to capture intent).

This isn't just folder creation; it's a **Context Injection**:

- **Type-appropriate source layout.** Each of the 11 scaffold types (`python-api`, `node-api`, `saas-skeleton`, `file-api`, `file-worker`, `wordpress`, `docusaurus`, `chrome-extension`, `mobile-app`, `desktop-app`, `static-site`) emits the directory structure its runtime demands — `src/<name>/` for Python APIs, `extension/` for Chrome, `electron/` for desktop, `worker/` for background processors, etc.
- **Standard dirs** every type shares: `docs/`, `scripts/`, `tests/`, `config/`, `data/`, `db/`, `logs/`, `.tmp/`, `.cache/`, `output/`.
- **The AI guardrails.** The scaffolder populates 5 files: `AGENTS.md` (Traycer planner), `CLAUDE.md` (Claude Code), `AGENTS-compact.md` (Kilo CLI), `KILO_CLI_RULES.md` (Kilo spec-contract awareness), and `.windsurfrules` (Windsurf Cascade). These are pre-loaded with VPS1 inventory + shape/registrar awareness so agents never hallucinate `localhost` databases or invent auth patterns.
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

You execute work through **Ticket Design.** You present a structured ticket to your agents (Claude Code, Windsurf, Kilo). Because they have the guardrail files (propagated via `scripts/sync_enforcement_to_projects.py` to all 41+ projects), they write code that is **Infrastructure-Aware:**

- They don't just write a Dockerfile; they write a `specs/services/<id>.yaml` whose `shape:` block declares the specific registrars needed — which Coolify app, which Gatus endpoint, which Prometheus scrape target, which GlitchTip project.
- If code adds a database call → `shape.needs_database` MUST be `true` in the spec.
- If code exposes `/metrics` → `shape.exposes_metrics` MUST be `true`.
- The `## Spec contract awareness` snippet (T3-02) lives in every executor file and enforces this at code-writing time — not deploy time.

**Local dev loop (T3-03):** `fabrik dev -d` starts the `compose.dev.yaml` stack; `fabrik logs --local -f` tails it; `fabrik review` bundles `git diff` + spec + resolved registrars for review dispatch. All in-WSL, sub-second feedback.

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

**Resource limits (F5 fix):** Every `compose.yaml` emitted by the scaffolder includes `deploy.resources.limits.memory` + `cpus` (Coolify v4.0.0-beta.459 ignores its `limits_memory` UI field for `build_pack=dockercompose` apps — the compose must carry the declaration explicitly).

---

## Stage 4 — Verification & Testing

Once the Coolify build is green, verification runs from WSL against the live VPS1 endpoint:

**Implemented (T2-02 + T4-04):**

- `fabrik verify <domain> --spec registrars` — postcondition gate; fails on any `missing` registrar.
- `fabrik audit-registrars [--json]` — fleet-wide pivot table of all 9 registrars × all specs.
- **Hourly drift detection (T4-04):** WSL cron pushes `fabrik_audit_drift_total` gauge to the VPS-local pushgateway → Prometheus alert rule `FabrikRegistrarDrift` (`for: 10m`) → Alertmanager route `alert_class=registrar_drift` → existing `telegram` receiver. Detection latency: ≤71 minutes.
- `fabrik destroy --use-state` (T4-02) — if teardown is needed, replays from state file (not current shape) so spec-drift doesn't orphan registrars. Data-bearing protection requires explicit `--drop-data`.

**Open (next ticket):**

- **Auto-rollback:** `verify.py:394` — if the health check or GlitchTip integration fails post-deploy, trigger `destroy_from_state(state.load(spec.id))` automatically. The wire is mechanically possible (T4-02 exports `destroy_from_state`); the orchestrator just needs to call it from the verify-failure path.

---

## Summary of what the scaffolder emits for Stage 3

The scaffolder's `_write_canonical_compose` function (the authoritative compose generator) emits for every Coolify-deployed type:

1. **Traefik labels** in `compose.yaml` — `Host(...)` routing rule, `websecure` entrypoint, LetsEncrypt cert resolver. These ARE Docker labels because Traefik's service-mesh discovery is label-based.
2. **`deploy.resources.limits`** in `compose.yaml` — memory + CPU cap that Docker enforces (F5 fix).
3. **Healthcheck** in `compose.yaml` — HTTP or process probe that Coolify uses to gate deploy success.

The scaffolder does NOT emit Prometheus/Promtail/cAdvisor labels or configs per service — those are handled by the **registrar system** at `fabrik apply` time (prometheus registrar) or by **auto-discovery** (Promtail, cAdvisor via docker.sock). This is a deliberate architecture decision: compose.yaml is the build/deploy contract; observability config is the registrar's domain.
