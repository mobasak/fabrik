# Plan v2 — AI Watchdog Platform + Automation-Grade Foundations

**Date:** 2026-05-30
**Owner:** Özgür (solo dev)
**Status:** Approved — owner locked decisions A2 + B2 + Claude-Code-primary / OpenRouter-fallback (see § Locked decisions). P1 unblocked.
**Related downstream:** `docs/traycer/mega-epic-breakdown/02-epic-decomposition-command.md`
**Supersedes:** v1 of this file (commit history) — v1 had 6 hard errors and 5 unverified capabilities corrected here.

---

## Goal

Make every Fabrik-deployed service **autonomous-by-default**: self-monitor, self-heal where safe, escalate to owner where not, with disciplined LLM cost and tamper-evident audit. Purpose: a solo dev shipping "automated digital products for loved ones to live a good life," where products must run quietly and reliably without constant supervision.

This plan delivers:

1. **In-project AI watchdog** (sidecar pattern) for every deployed service whose `shape.kind` warrants it.
2. **Cross-cutting foundations** the watchdog and the rest of the portfolio need: tamper-evident `app-audit-log`, LLM `cost-budget`, self-healing synthesis rule pack.
3. **Updated `02-epic-decomposition-command`** that integrates universal-coverage enforcement into its existing structure (NOT a rewrite — it adds an enforcement overlay).

---

## Context — what we have today (verified)

**`Kind` enum** (`src/fabrik/spec_loader.py:18-32`) — 4 values: `service`, `worker`, `static`, `wordpress`. NOT 8.

**`Shape` model** (`src/fabrik/spec_loader.py:218+`) — 8 boolean flags + `kind`: `is_public`, `is_admin_dashboard`, `has_bearer_api`, `has_persistent_data`, `needs_database`, `has_search_feature`, `needs_cache`, `exposes_metrics`. `extra="forbid"`.

**`_REGISTRAR_ORDER`** (`src/fabrik/orchestrator/infrastructure.py:84`) — 9-tuple: `postgres, redis, gatus, backrest, glitchtip, grafana, authelia, meilisearch, prometheus`. Registrars are functions in `infrastructure.py`, NOT a separate `registrars/` directory.

**Driver pattern** (`src/fabrik/drivers/`) — separate file per integration. Reference sizes: `gatus.py` 283 lines, `glitchtip.py` 467 lines, `authelia.py` 592 lines.

**`src/fabrik/audit.py`** already exists — implements `fabrik audit-registrars`. Different namespace from the proposed `fabrik-lib/app-audit-log/` (renamed from `audit-log/` to avoid collision).

**Fabrik CLI commands** (verified via `fabrik --help`): `apply`, `redeploy`, `verify`, `scaffold`, `audit-registrars`, `validate`, `validate-deploy`, `fix`, `plan`, `preplan`, `destroy`, `reconcile-all`, `domain`, `vps-sync`, `status`, `logs`, `app-logs`, `projects`, `scan`, `export`, `import`, `templates`, `dev`, `ai`, `content`, `seo`, `review`. `sync-rules` does NOT exist; **the rule-sync mechanism is `fabrik fix <project> --type <scaffold-type>`** (per `fabrik fix --help`, adds missing required files including `.windsurfrules` and `.windsurf/rules/`).

**fabrik-lib modules (19, verified):** `abuse-prevention`, `adaptive-dispatch`, `alerting`, `api-auth`, `async-http-client` (with `circuit_breaker.py`), `cookie-consent`, `credits`, `cursor-pagination`, `docs-site`, `email-templates`, `file-cache`, `gdpr-data-rights`, `i18n`, `legal-pages`, `mt-router`, `pause-state` (227 lines), `storage`, `upstream-quota`, `webhooks`. Calibration: `email-templates` 204 / `abuse-prevention` 215 / `gdpr-data-rights` 210 / `credits` 782.

**`.windsurf/rules/` packs (30, verified):** `core/` (19 packs), `saas/` (4 packs), `mobile-app/` (5 packs), `chrome-ext/` (1 pack), plus design system packs.

**Existing infra used by the watchdog:** Apprise (one-way alerts; **NO interactive buttons** — verified send-only), Gatus (uptime probes), GlitchTip (error tracking; owner already gets alerts directly — **watchdog will NOT pull GlitchTip events in v1**), Prometheus (`/metrics` scrape), Backrest (B2 backups). Loki/Promtail are NOT in the core stack (only mentioned in `dev_tools.py` and `prometheus.py`); **watchdog reads logs via `docker logs <container>` directly**, not via Loki.

**Existing `02-epic-decomposition-command.md` structure** — Steps 1–4, one Checkpoint, an "Infrastructure Decisions" section with sub-sections (Database Strategy, Auth Strategy, Email Strategy, Background Processing, Embedding Model, Backing Services, External Services, Domain Structure, Shared Env Vars, Shared Shape Decisions), Deferred Compliance appendix, Output Contract, Does NOT, Acceptance Criteria. **Plan v2 INTEGRATES universal-coverage enforcement into Steps 2–3 and Infrastructure Decisions, NOT a rewrite.**

**Dogfood project exists** at `/opt/test-saas-for-epic-wf` + `specs/services/test-saas-for-epic-wf.yaml`.

---

## Identified gaps (this plan fills)

1. No project-local self-monitoring / self-healing reasoning loop.
2. No tamper-evident append-only audit log for sensitive ops + watchdog actions.
3. No LLM cost guardrail (existential risk for AI-using projects).
4. Self-healing primitives (`pause-state`, `async-http-client/circuit_breaker.py`, `abuse-prevention`) exist but are not synthesized into one coherent escalation ladder.
5. `02-epic-decomposition-command` doesn't currently force universal coverage of these categories.

---

## Accepted deferrals (with revisit triggers — out of scope of this plan)

| Deferral | Revisit when |
| --- | --- |
| `desktop-app/` rule pack | First desktop-app scaffold ships |
| `wordpress/` rule pack (have `domain-modules/wordpress.md`) | A non-`/opt/wpf/` WordPress project ships |
| `static-site/` rule pack | A substantial marketing/landing surface ships |
| a11y rule pack + lib module | A public consumer SaaS surface ships |
| SEO module | A product needs growth via search |
| Analytics module | Cross-project consistency becomes valuable |
| Onboarding module | A non-owner SaaS with non-technical users ships |
| `openapi-codegen/` module | A multi-scaffold project (api + saas + mobile) needs shared contract |
| `file-validation/` module (MIME + virus scan via ClamAV + size limits) | A substantive `file-api` with user-uploaded content ships |
| `electron-app/` module + `desktop-app/` rule pack (paired) | First desktop-app scaffold ships (see also `desktop-app/` rule pack row above) |

---

## Locked decisions

**A2 — App-level hash chain.** Python helper computes `prev_hash` + `current_hash` in the `app-audit-log/` module before each insert. Both columns exist in the schema from day one so the future upgrade path to A1 (Postgres trigger) is non-breaking — only the write path changes. Threat model: solo-dev VPS where only the owner has direct DB write access; "someone bypasses the helper" is "owner bypasses themselves," not a real attack. Read-time verification still catches corruption + LLM-instructed lying.

**B2 — Shared Postgres ledger with per-project rows + fail-open WAL.** Cost rows live in a single `cost_ledger` table on `postgres-main`, indexed by `(project_id, ts)` for cap enforcement and by `ts` for portfolio analytics. Watchdog writes via a local SQLite write-ahead buffer; on Postgres unreachable, sidecar proceeds (fail-open) and replays the WAL when Postgres returns. Cost discipline still hard-capped per project via row aggregation; portfolio queries one-line SQL.

```sql
-- Created by the postgres registrar at fabrik apply (one-shot, idempotent)
CREATE TABLE IF NOT EXISTS cost_ledger (
  id          uuid PRIMARY KEY,          -- uuid7 (sortable)
  project_id  text NOT NULL,             -- spec.id
  ts          timestamptz NOT NULL DEFAULT now(),
  provider    text NOT NULL,             -- 'claude-code' | 'openrouter'
  model       text NOT NULL,             -- 'claude-sonnet-4-6' | 'gemini-2.5-flash' | ...
  in_tokens   int NOT NULL,
  out_tokens  int NOT NULL,
  cost_usd    numeric(10,6) NOT NULL,    -- 0.000000 for claude-code subscription calls
  incident_id text,                      -- nullable; links to watchdog incident
  action_id   text                       -- nullable; links to audit_log row
);
CREATE INDEX IF NOT EXISTS idx_cost_ledger_project_ts ON cost_ledger (project_id, ts DESC);
CREATE INDEX IF NOT EXISTS idx_cost_ledger_ts ON cost_ledger (ts DESC);
```

Portfolio queries are straightforward:

```sql
-- Monthly spend per project
SELECT project_id, SUM(cost_usd) AS spend_usd
FROM cost_ledger
WHERE ts > now() - interval '30 days'
GROUP BY project_id ORDER BY spend_usd DESC;

-- Claude Code call count per project (subscription burn visibility)
SELECT project_id, COUNT(*) AS calls
FROM cost_ledger
WHERE provider = 'claude-code' AND ts > now() - interval '7 days'
GROUP BY project_id ORDER BY calls DESC;
```

**LLM provider chain — Claude Code primary, OpenRouter fallback.** Claude Code is already installed and running on the VPS, with active Max subscription (2× headroom). Sidecar invokes `claude -p <prompt>` via subprocess; subscription quota absorbs the bulk of cost. On failure (CLI not responding, exit non-zero, timeout, subscription rate-limit) OR when the watchdog needs explicit cost telemetry for a high-value incident, sidecar falls back to OpenRouter HTTP API. **Cost tracking note:** Claude Code calls record `provider='claude-code'`, `cost_usd=0.000000` (subscription is flat) but still record `in_tokens` + `out_tokens` + invocation count — so subscription burn is visible per project even though dollar cost isn't real-time. Owner can correlate against the Anthropic dashboard separately. OpenRouter calls record actual per-token `cost_usd`.

**Why not Anthropic API direct:** rejected by owner — Claude Code subscription already covers the use case at flat cost; Anthropic API direct adds a second billing relationship with no upside given the subscription headroom.

---

## Watchdog architecture (committed)

**Pattern:** sidecar container in each deployed project's `compose.yaml`. NOT centralized.

**Why sidecar:**

- Per-project context (logs, local files, queue state) is only reachable from inside the project's network.
- Failure isolation — central watchdog down ≠ nothing watched.
- Clean spec contract — each project declares `watchdog:` in its spec.
- Matches `/opt/fabrik-lib/` vendor philosophy.

**Two pieces ship together:**

1. **Sidecar image** — `fabrik/watchdog:latest`, built from `fabrik-lib/watchdog/sidecar/Dockerfile`
2. **Emitter library** — `fabrik-lib/watchdog/emitter/`, vendored into the main app for `emit_incident("payment_failed", {...})` calls

**Sidecar capabilities (v1):**

- Subscribes to: `docker logs <main-container>` (direct, no Loki dep) + Prometheus `/metrics` (scrape main app's endpoint, if `shape.exposes_metrics: true`).
- **Does NOT** subscribe to GlitchTip events in v1 (owner already gets GlitchTip alerts; avoiding API-token plumbing complexity for v1).
- Check loop every 60s (configurable via `watchdog.yaml`).
- Anomaly → wake LLM reasoning loop. Otherwise idle (near-zero cost).
- **LLM provider chain (Claude Code primary, OpenRouter fallback):**
  - Primary invocation: `claude -p <prompt> --bare --permission-mode auto --settings /etc/watchdog/claude-settings.json --allowedTools "Bash,Read,Edit,Grep,Glob" --output-format json --append-system-prompt "<project-scoped context>"`. Run as **non-root** UID inside the sidecar (Claude Code refuses `--dangerously-skip-permissions` under root/sudo on Linux, and we want the same security posture even though we're not using bypass mode).
  - `--bare` skips auto-discovery of hooks/plugins/MCP/CLAUDE.md so the sidecar's runtime context is fully declarative (`--settings`, `--allowedTools`, `--append-system-prompt`). Reproducible across invocations.
  - `--permission-mode auto` engages the AI classifier (NOT `--enable-auto-mode` — that flag doesn't exist; my v1 reference was wrong). Classifier auto-approves routine diagnostics, blocks destructive ops. `autoMode.environment` (declared in settings) tells the classifier what context is trusted (this project's container, this docker.sock scope, etc.).
  - Sidecar inherits host Claude Code auth via read-only mount of `~/.claude/` (host) → `/home/watchdog/.claude/` (sidecar). No API key plumbing for Claude Code path.
  - Fallback: OpenRouter HTTP API (`openrouter.ai/api/v1/chat/completions`) with key from `WATCHDOG_OPENROUTER_KEY`. Triggered on: Claude Code exit non-zero, timeout >60s, classifier abort (3 consecutive blocks or 20 total → headless session terminates), rate-limit signal, or owner-configured "use OpenRouter for this incident class."
  - Cost telemetry: every call (either provider) emits one `cost_ledger` row. Claude Code rows record `cost_usd=0.000000` + token counts; OpenRouter rows record actual cost.
  - Model tiering (applies to both providers): cheap model first (Claude Code → Haiku; OpenRouter → Gemini Flash) returns structured output with self-rated confidence; escalate to expensive (Sonnet) on low confidence OR rule-based heuristics (stack trace present → escalate). Acknowledged limitation: cheap-model confidence calibration varies; rule-based fallback is the safety net.

- **Claude Code permission boundaries (defense in depth — three layers):**
  1. **Settings (`/etc/watchdog/claude-settings.json`, mounted into sidecar):** `permissions.allow` / `ask` / `deny` arrays with `Bash(<pattern>)` syntax; `deny > ask > allow` priority. `defaultMode: "auto"`. `autoMode.environment` declares trusted scope (project id, container name, docker.sock label filter). `sandbox.filesystem.allowWrite` limited to `/opt/<project>/watchdog/` + `/tmp/`; `denyWrite` covers `/opt/<project>/src/` + `/opt/<project>/.git/` + `/opt/<project>/.env` + `/opt/<project>/secrets/`. MCP fully denied via `permissions.deny: ["mcp__*"]` (watchdog has no MCP need). `WebFetch` and `WebSearch` denied (sidecar has no business calling external HTTP outside the project).
  2. **PreToolUse hook (`.claude/hooks/PreToolUse.sh`):** custom shell script that intercepts every tool call as JSON and exits 0 (allow) or non-zero (block). Enforces the Tier A/B/C action allow-list from § Action surface — settings.json patterns are the broad layer; the hook is the surgical layer (e.g., `docker restart {project_id}` allowed; `docker restart postgres-main` blocked by hook even if it slipped past the regex). The hook reads `project_id` from env and constructs the allow-list dynamically per project.
  3. **Docker `docker.sock` mount scoping:** the sidecar's docker socket access is constrained by Docker label filter to its own `com.docker.compose.project=<project_id>` label. Cannot list, exec, restart, or stop containers from other compose projects. Cannot touch `postgres-main` / `redis-main` / `traefik` (none of which carry this project's label). Belt-and-braces with the PreToolUse hook.

- **Concrete `claude-settings.json` shape** (template; watchdog driver expands `<project_id>` and `<main_container>` at apply time):

```json
{
  "defaultMode": "auto",
  "permissions": {
    "allow": [
      "Bash(docker logs <main_container> *)",
      "Bash(docker inspect <main_container>)",
      "Bash(docker restart <main_container>)",
      "Bash(docker stats --no-stream <main_container>)",
      "Bash(curl -s localhost:*/metrics)",
      "Bash(curl -s localhost:*/health)",
      "Bash(ls /opt/<project_id>/*)",
      "Bash(cat /opt/<project_id>/logs/*)",
      "Bash(tail -n * /opt/<project_id>/logs/*)",
      "Bash(grep * /opt/<project_id>/logs/*)",
      "Read", "Grep", "Glob"
    ],
    "ask": [],
    "deny": [
      "Bash(rm -rf *)",
      "Bash(docker stop postgres-main)",
      "Bash(docker stop redis-main)",
      "Bash(docker stop traefik*)",
      "Bash(docker rm *)",
      "Bash(docker volume rm *)",
      "Bash(systemctl *)",
      "Bash(sudo *)",
      "Bash(git push *)",
      "Bash(curl http://* http*://*)",
      "Edit", "Write",
      "WebFetch", "WebSearch",
      "mcp__*"
    ]
  },
  "autoMode": {
    "environment": [
      "You are the watchdog sidecar for project '<project_id>'",
      "Main container: <main_container>; you may restart it",
      "Working directory: /opt/<project_id>",
      "You CANNOT touch postgres-main, redis-main, or traefik (other projects' shared infra)",
      "You CANNOT edit code, push to git, or modify configuration",
      "Tier A actions allowed: restart main container, clear local file-cache, scale concurrency, pause workers via pause-state, drop oldest queue items, rotate stuck locks",
      "Tier B/C actions: escalate to owner via Apprise; do NOT execute"
    ],
    "hardDeny": [
      "Never edit source code under /opt/<project_id>/src",
      "Never push to git",
      "Never touch postgres-main, redis-main, or traefik",
      "Never modify Traefik configuration",
      "Never read or write files outside /opt/<project_id>/"
    ]
  },
  "sandbox": {
    "enabled": true,
    "failIfUnavailable": true,
    "filesystem": {
      "allowWrite": ["/opt/<project_id>/watchdog/", "/tmp/"],
      "denyWrite": [
        "/opt/<project_id>/src/",
        "/opt/<project_id>/.git/",
        "/opt/<project_id>/.env",
        "/opt/<project_id>/compose.yaml",
        "/opt/<project_id>/secrets/"
      ],
      "allowRead": ["/opt/<project_id>/"]
    },
    "network": {
      "allowedDomains": []
    }
  }
}
```

- State: SQLite at `/opt/{project}/watchdog/state.db` — incidents, action history, **cost-ledger write-ahead buffer** (replays to `postgres-main` on Postgres reachable).
- `docker.sock` mounted read-only, scoped via Docker label filter to the sidecar's own compose project (cannot touch other projects' containers, cannot touch `postgres-main` / `redis-main` / Traefik).

**Action surface:**

| Tier | Actions | Authority |
| --- | --- | --- |
| **A — autonomous, frequent** | Restart main container, clear local file-cache, scale concurrency ±50%, pause worker via `pause-state`, drop oldest queue items above N, rotate stuck request locks | Always allowed |
| **B — autonomous, rate-limited, opt-in** | Wipe Redis cache, reset DB connection pool | `auto_tier_b: false` default per project; opt-in only |
| **C — always escalate** | Code changes, config changes, secret rotation, DNS changes, anything touching `postgres-main` / `redis-main` / Traefik / shared infra, **Backrest restore from snapshot** (moved here from v1 Tier B — too dangerous without owner confirmation) | Never autonomous |

**Owner channel:** Apprise (already wired, one-way). Severity-graded: Tier A → info, Tier B → warn, Tier C → urgent. **No interactive button confirmations** (Apprise is send-only). Owner approval for Tier B opt-in is via spec config (`auto_tier_b: true`); per-action owner confirmation for Tier C is via owner reading the alert and acting manually.

**Defaults — when watchdog runs by `shape.kind`:**

| `kind:` | Watchdog default |
| --- | --- |
| `service` | **Enabled** (python-api, node-api, saas-skeleton, file-api) |
| `worker` | **Enabled** (file-worker) |
| `wordpress` | **Enabled** (WP container is deployed; benefits from self-healing on PHP-FPM hangs, plugin update crashes) |
| `static` | **Disabled** (static-site, docusaurus, chrome-extension, mobile-app, desktop-app — packaged artefacts or static deploys; Gatus external probe sufficient; sidecar overhead not worth it) |

Owner can override either way via `watchdog.enabled: true|false` in the spec.

---

## Net-new artifacts (12, verified count)

| # | Artifact | Type | Path | Est. lines | Purpose |
| --- | --- | --- | --- | ---: | --- |
| 1 | `app-audit-log/` | fabrik-lib module | `/opt/fabrik-lib/app-audit-log/` | ~350 | Append-only Postgres `audit_log` table, hash-chained per row (per Decision A), monthly partitions, app helper + verification query. Renamed from `audit-log/` to avoid collision with existing `src/fabrik/audit.py`. |
| 2 | `cost-budget/` | fabrik-lib module | `/opt/fabrik-lib/cost-budget/` | ~300 | Per-project daily/weekly/monthly cost caps (USD for OpenRouter, invocation-count for Claude Code subscription) + per-task soft cap. Kill-switch on overrun → rule-only mode. Shared `cost_ledger` on `postgres-main` (B2) + local SQLite write-ahead buffer with fail-open replay. `llm_cost_dollars_total` + `llm_invocations_total{provider}` Prometheus metrics. Renamed from `llm-budget/` for broader applicability. |
| 3 | `watchdog/sidecar/` | fabrik-lib module + Docker image | `/opt/fabrik-lib/watchdog/sidecar/` | ~1000 | Sidecar Dockerfile, agent loop, LLM tiered client, action handlers, state SQLite, Docker SDK calls |
| 4 | `watchdog/emitter/` | fabrik-lib module | `/opt/fabrik-lib/watchdog/emitter/` | ~150 | Python helper `emit_incident()` vendored into main app |
| 5 | `core/app-audit-log.md` | rule pack | `/opt/fabrik/.windsurf/rules/core/app-audit-log.md` | ~80 | When/how to use audit log, what events to log (auth, billing, admin, data export, watchdog actions), retention policy, hash-chain verification on read |
| 6 | `core/cost-budget.md` | rule pack | `/opt/fabrik/.windsurf/rules/core/cost-budget.md` | ~100 | Budget discipline patterns, tiered model selection ladder, fallback to rule-only mode |
| 7 | `core/watchdog.md` | rule pack | `/opt/fabrik/.windsurf/rules/core/watchdog.md` | ~150 | Action allow-list, escalation thresholds, integration with `pause-state` / `async-http-client.circuit_breaker`, Tier B opt-in flow |
| 8 | `core/self-healing.md` | rule pack | `/opt/fabrik/.windsurf/rules/core/self-healing.md` | ~120 | Synthesis of existing primitives (`pause-state` + `async-http-client.circuit_breaker` + `abuse-prevention` + restart-on-OOM + queue backpressure) into one escalation ladder. Cites `58-resilience.md`, `75-workers-jobs.md`. |
| 9 | `Shape` model field — add `watchdog: WatchdogConfig` (NEW Pydantic class) | spec schema | `src/fabrik/spec_loader.py` | ~40 | Top-level spec block `watchdog:` with `enabled: bool`, `daily_budget_usd: float` (OpenRouter cost cap), `daily_invocations_cap: int` (Claude Code subscription cap), `auto_tier_b: bool`, `escalation_channel: str`, `llm_provider_primary: str` (default `"claude-code"`), `llm_provider_fallback: str` (default `"openrouter"`), `cheap_model_primary: str`, `expensive_model_primary: str`, `cheap_model_fallback: str`, `expensive_model_fallback: str`. Defaults computed from `shape.kind` per the table above. |
| 10 | `_register_watchdog()` function | registrar function | `src/fabrik/orchestrator/infrastructure.py` | ~60 | Dispatcher gate following pattern of `_register_gatus`/`_register_glitchtip`. Inserted into `_REGISTRAR_ORDER` AFTER `postgres` (so audit-log DB exists) and AFTER `prometheus` (so `/metrics` is scrape-ready). |
| 11 | `src/fabrik/drivers/watchdog.py` | driver module | `src/fabrik/drivers/watchdog.py` | ~450 | At `fabrik apply`: inject sidecar service into compose, wire `WATCHDOG_*` env vars, register per-project Apprise channel. Pattern matches `drivers/gatus.py` (283) and `drivers/glitchtip.py` (467). |
| 12 | `02-epic-decomposition-command.md` update | Traycer command edit | `docs/traycer/mega-epic-breakdown/02-epic-decomposition-command.md` | ~150–200 lines changed | INTEGRATE universal-coverage overlay into existing Step 2 + Infrastructure Decisions (NOT a rewrite). Add a new sub-step "Universal Coverage Check" that asserts the epic set covers categories 1–14 below. |

**Total net-new:** 4 fabrik-lib modules + 4 rule packs + 1 spec field + 1 registrar fn + 1 driver + 1 Traycer command update ≈ **~2,940 lines**.

---

## Phased implementation (corrected effort)

| Phase | Deliverable | Depends on | Realistic effort | Acceptance |
| --- | --- | --- | --- | --- |
| **P1 — Foundations** | `app-audit-log/` (A2 app-level hash) + `cost-budget/` (B2 shared Postgres + local WAL) + `core/app-audit-log.md` + `core/cost-budget.md` + postgres-registrar migration for `cost_ledger` table | None — decisions locked | **3–4 days** | Both modules vendor cleanly into a test project; `cost_ledger` table created by postgres registrar on first apply; WAL replay verified on Postgres outage simulation; READMEs match `fabrik-lib/README.md` rule; rule packs lint-pass |
| **P2 — Watchdog core** | `watchdog/sidecar/` (incl. Claude Code subprocess + OpenRouter HTTP client + fallback chain) + `watchdog/emitter/` + `core/watchdog.md` + spec field + `_register_watchdog()` + `drivers/watchdog.py` | P1 (app-audit-log + cost-budget) | **6–8 days** | Sidecar image builds with Claude Code CLI inherited from host config mount; `fabrik apply` on a test spec produces compose with watchdog service; emitter `emit_incident()` writes to audit log; restart-action handler works against test container; primary-to-fallback provider chain verified by killing Claude Code session mid-test |
| **P3 — Self-healing synthesis** | `core/self-healing.md` | None (parallel to P2) | **1 day** | Doc lints; cites existing primitives correctly; escalation ladder unambiguous |
| **P4 — 02 integration** | Universal-coverage overlay integrated into `02-epic-decomposition-command.md` | P1 + P2 + P3 must exist before 02 cites them | **2 days** | Traycer cold-read of updated 02 on test Vision Summary produces epic set covering all 14 universal categories + saas-skeleton overlay; existing Step 1–4 + Infrastructure Decisions structure preserved |
| **P5 — Dogfood E2E** | End-to-end on `/opt/test-saas-for-epic-wf`: 00 → 02 → 03 → ticket execution → `fabrik apply` → watchdog active | P1–P4 | **3 days** | Watchdog sidecar running; audit-log table populated; cost-budget enforced; synthetic anomaly (e.g., `docker kill main && watch for restart`) triggers Tier A restart within 90s + audit row written + Apprise notification received |

**Realistic total: 15–18 working days** for solo dev + AI agent assistance. (v1's "10 days" was a ~50% underestimate.)

---

## What 02 will enforce after P4 (14 universal categories + overlay)

These categories are added as a "Universal Coverage Check" sub-step in Step 2 of 02. They overlay on the existing Step 2 (Epic Boundaries) + Step 3 (Infrastructure Decisions) structure — they do NOT replace either. 02's existing sections (Database Strategy, Auth Strategy, etc.) absorb the matching universal categories.

| # | Universal category | Trigger | Cites |
| --- | --- | --- | --- |
| 1 | Foundation | Always | scaffold sync, AI guardrails, `.windsurf/rules/` sync (via `fabrik fix`), `.env.example`, `project.yaml`, spec `shape:` block, `docs/RESILIENCE.md` |
| 2 | Features | Always (one or more per Vision § Full Feature Inventory) | Vision Summary |
| 3 | Persistence | If `shape.needs_database` | `core/25-data-postgres.md` — schema, migrations, multi-tenancy |
| 4 | Workers | If pipeline/async work | `core/75-workers-jobs.md` + `pause-state/` |
| 5 | External integrations | If any upstream API use | `core/58-resilience.md` + `async-http-client/circuit_breaker.py` + `upstream-quota/` |
| 6 | Self-healing | Always for `shape.kind ∈ {service, worker, wordpress}` | `core/self-healing.md` (new) |
| 7 | Watchdog wiring | `watchdog.enabled: true` (default per kind) | `core/watchdog.md` (new) |
| 8 | Observability | Always | `core/55-observability.md` — `/health` with real deps, `/metrics` (if `exposes_metrics`), structured logs, GlitchTip DSN |
| 9 | Cost guardrails | Any LLM/paid-API use | `core/cost-budget.md` (new) + `cost-budget/` |
| 10 | Deployment | Always | `core/30-ops.md` — compose validation, registrars, DNS, SSL, Traefik, env parity |
| 11 | Documentation | Always | `core/40-documentation.md` — CHANGELOG, FEATURES, QUICKSTART, RESILIENCE |
| 12 | Security | Always | `core/35-security-auth.md` + `saas/87-abuse-detection.md` (if signup) + `core/app-audit-log.md` (new, for sensitive ops) |
| 13 | Testing | Always | `core/45-testing-strategy.md` — integration tests against real DB |
| 14 | Retrofit | EXISTING mode only — one per Fix-now Compliance Report row | Compliance Report from 00 Step E5 |

**Scaffold-type overlays** (loaded from `domain-modules/<type>.md`):

- `saas-skeleton`: payments + i18n + GDPR + cookie consent + legal pages + abuse defense + customer portal + launch checklist
- `mobile-app`: EAS Build + IAP via RevenueCat + store metadata + push + privacy nutrition + ATT + launch checklist
- `chrome-extension`: Manifest V3 + CSP + content scripts + CWS submission
- `file-api / file-worker`: storage + upload validation + queue + DLQ
- `wordpress`: per `domain-modules/wordpress.md` (Tier-4 deferral; no rule pack)
- `docusaurus / static-site`: minimal overlay; watchdog disabled

---

## Risks & mitigations (corrected)

| Risk | Mitigation |
| --- | --- |
| Watchdog cost-loops (runaway LLM calls) | Hard `cost-budget` daily kill-switch → rule-only mode. For Claude Code primary path: invocation-count cap (subscription quota is the real limit, but per-project caps prevent one project from burning the shared subscription on everyone else's behalf). For OpenRouter fallback: USD cost cap. `restart: unless-stopped` on the sidecar is NOT the cost-loop fix; the kill-switch is. |
| Claude Code CLI breaks (CLI upgrade, auth expires, host config changes) | Sidecar mounts the host's Claude Code config dir; if `claude -p` exits non-zero or times out, watchdog falls back to OpenRouter automatically and emits a Tier C "primary LLM provider unavailable" alert to owner so the CLI can be repaired without losing watchdog coverage. |
| One project burns the shared Claude Code subscription | Per-project `daily_invocations_cap` enforced by `cost-budget` via `cost_ledger` aggregation. Hit cap → that project's watchdog switches to OpenRouter (paying real USD) instead of starving others. Portfolio query `SELECT project_id, COUNT(*) ... WHERE provider='claude-code'` makes burn visible. |
| `postgres-main` outage blinds cost tracking | Local SQLite write-ahead buffer (fail-open semantics, see Locked Decisions § B2). Sidecar continues operating; ledger replays within ~30s of Postgres returning. Worst case: ~30s of pre-cap blindness during a DB blip, never an autonomous-action failure. |
| Watchdog Tier A action breaks main app | Tier A actions are reversible (restart, scale, clear cache, pause). `restart: unless-stopped` on main brings it back from non-deep failures. **Deep failures (DB corruption, leaked secrets, expired certs without renewal cron) are NOT restart-recoverable** — they escalate to Tier C alert and owner intervenes. |
| Sidecar overhead on small VPS | Watchdog idle: ~30MB RAM + near-zero CPU. Anomaly-triggered LLM calls bounded by cost-budget. Disabled by default for `kind: static`. Memory limit `128M` enforced in compose. |
| LLM hallucinates a fix | Tier A actions constrained to hardcoded allow-list. LLM picks WHICH action from list; cannot invent new ones. Out-of-allow-list response → sidecar logs incident, skips. |
| Audit log grows unbounded | Monthly partitions + Backrest backup + 12-month retention default (configurable). Old partitions archived to B2. **Retention enforcement is via app-level scheduled task** (pg_cron availability on `postgres-main` is unverified — do NOT assume). |
| Audit log hash chain bypassable | Depends on Decision A. A1 (DB trigger) = strict; A2 (app-level) = bypassable but acceptable for solo-dev threat model. |
| Adoption friction | `watchdog.enabled` default true for `kind ∈ {service, worker, wordpress}`. Spec validator warns if missing. 02 enforces watchdog category for every applicable Vision. |
| Sidecar can't reach main `/metrics` | Watchdog degrades to log-only mode (still useful for restart-on-crash signals). |
| Cheap LLM confidence calibration unreliable | Rule-based heuristic fallback (stack trace in logs → escalate to expensive model) covers the gap. |
| Plan scope creep into deferral list | Deferrals explicitly documented above. Anything outside this plan = new plan file. |

---

## Acceptance criteria (whole plan)

- All 12 net-new artifacts exist; modules have READMEs per `fabrik-lib/README.md` rule; rule packs lint-pass.
- `fabrik apply` on a `kind: service` test spec produces a deployed project with watchdog sidecar running.
- Synthetic anomaly (`docker kill main`) triggers Tier A restart within 90s, writes audit-log row (app-level hash-chained per A2), sends Apprise info notification, updates watchdog SQLite state, and writes one `cost_ledger` row to `postgres-main` (`provider='claude-code'`, `cost_usd=0.000000`, token counts populated).
- Killing the Claude Code session mid-test: sidecar falls back to OpenRouter within 60s, emits Tier C "primary LLM provider unavailable" alert, continues operating; subsequent `cost_ledger` rows have `provider='openrouter'` with real `cost_usd`.
- Same project with `cost-budget` forced to zero (both `daily_budget_usd: 0` and `daily_invocations_cap: 0`) drops to rule-only mode — no LLM calls, no `cost_ledger` rows added, rule-based alerts continue.
- `postgres-main` stopped for 60s mid-test: sidecar continues operating; local SQLite WAL accumulates cost rows; on Postgres restart, WAL drains within 30s; no rows lost.
- Updated `02-epic-decomposition-command.md` cold-read on dogfood Vision Summary produces an epic set covering all 14 universal categories + saas-skeleton overlay. Existing 02 structure (Steps 1–4 + Infrastructure Decisions) preserved.
- CHANGELOG entries written per artifact.
- LESSONS_LEARNT entry capturing any cross-cutting insight from the build.

---

## Out of scope (will not be done in this plan)

- Cross-project learning (watchdog aggregating insights across multiple projects). Future plan.
- Watchdog dashboard UI. Apprise-only alerting for v1. Future plan.
- Auto-tuning of cost-budget based on observed cost-per-success. Future plan.
- All Tier-4 deferrals listed above.
- Updates to `03-expand-epic-files-command.md`, `04-cross-epic-validation-command.md`, `05-dispatch-epic-tickets-command.md`. May follow naturally from P4 but tracked as separate work.
- GlitchTip event-pull integration into watchdog (v2 enhancement if value justifies the API-token plumbing).
- Interactive owner approval via Telegram bot (would require new service, out of scope).
- Removing the stale `coolify:` block from spec schema — tracked separately under the Coolify-residue plan.

---

## v1 → v2 changelog (for the record)

| Issue in v1 | v2 fix |
| --- | --- |
| Claimed `Kind` has 8 values | Corrected to 4: `service`, `worker`, `static`, `wordpress` |
| Claimed registrar lives at `src/fabrik/registrars/watchdog.py` | Corrected to `_register_watchdog()` in `src/fabrik/orchestrator/infrastructure.py` + `src/fabrik/drivers/watchdog.py` (split into 2 artifacts) |
| Claimed Apprise has interactive buttons | Removed; Apprise is send-only; Tier B opt-in via spec, not in-channel |
| Claimed sidecar subscribes to Promtail | Corrected to `docker logs <container>` directly; Loki/Promtail not in stack |
| Initially claimed `fabrik validate` doesn't exist | **Retracted in review** — `fabrik validate` exists; my grep methodology was flawed. v2 correctly cites it. |
| Claimed `fabrik sync-rules` exists | Removed; replaced with real command `fabrik fix <project> --type <scaffold>` |
| Assumed 02 is greenfield rewrite | Corrected to INTEGRATE universal-coverage overlay into existing Step 2 + Infrastructure Decisions |
| Backrest restore as Tier B (autonomous) | Moved to Tier C (always escalate) — too dangerous without confirmation |
| GlitchTip event-pull as input | Dropped from v1; rely on owner's existing GlitchTip alerts; revisit in v2 of watchdog itself |
| pg_cron assumed for audit-log retention | Made explicit: NOT assumed; use app-level scheduled task |
| LLM cost ledger location unspecified | Locked: B2 (shared `postgres-main` `cost_ledger` table with per-project rows + local SQLite write-ahead buffer, fail-open semantics) |
| LLM provider unspecified | Locked: Claude Code primary (subprocess, inherits host config + Max subscription), OpenRouter fallback (HTTP API on Claude Code failure / timeout / quota). Anthropic API direct explicitly rejected by owner. Per-project caps: USD for OpenRouter, invocation-count for Claude Code subscription. |
| Claude Code permission system originally cited `--enable-auto-mode` flag | **Verified via official docs (2026-05-30):** flag does NOT exist. Correct mechanism is `--permission-mode auto` (CLI) or `defaultMode: "auto"` (settings.json). 6 modes exist: `default`, `acceptEdits`, `plan`, `auto`, `dontAsk`, `bypassPermissions`. |
| Permissions JSON shape (v1 implicit) | **Verified:** three arrays — `allow` / `ask` / `deny`. Priority: deny > ask > allow. Bash pattern syntax: `Bash(<pattern>)` with `*` wildcard; bare `"Bash"` allows all. Compound commands auto-split on `&&`, double-pipe, `;`, single-pipe. |
| Sidecar runs Claude Code: implementation pattern unclear | **Verified pattern:** `claude -p <prompt> --bare --permission-mode auto --settings <path> --allowedTools "Bash,Read,Edit,Grep,Glob" --output-format json --append-system-prompt <project-context>`. `--bare` skips host config auto-discovery (hooks/plugins/MCP/CLAUDE.md) so sidecar context is fully declarative. Sidecar runs as **non-root UID** (Linux refuses bypass mode under root/sudo, and we want the same posture). |
| Sidecar permission enforcement single-layer | **Upgraded to 3-layer defense in depth:** (1) `settings.json` allow/ask/deny + `autoMode.environment` + `sandbox.filesystem` denyWrite — declarative broad layer; (2) `PreToolUse` hook enforces Tier A/B/C action allow-list surgically (per-project allow-list expanded from env vars at apply time); (3) `docker.sock` scoped via `com.docker.compose.project=<project_id>` label filter — cannot touch other projects' containers or shared infra. |
| `--dangerously-skip-permissions` considered for sidecar | **Rejected.** Cannot run under root/sudo on Linux. Auto mode + sandbox + PreToolUse hook is the correct posture; bypass mode forfeits the safety net and is reserved for disposable ephemeral environments. |
| Audit log hash-chain implementation hand-waved | Locked: A2 (app-level Python hashing). Both `prev_hash` and `current_hash` columns present in schema from day one so future upgrade to A1 (Postgres trigger) is non-breaking. |
| Effort estimate 10 days | Corrected to 15–18 days realistic |
| Artifact count 10 | Corrected to 12 (split watchdog into sidecar + emitter + driver + registrar fn) |
| Module name `audit-log/` collides with `src/fabrik/audit.py` | Renamed to `app-audit-log/` |
| Module name `llm-budget/` too narrow | Renamed to `cost-budget/` (broader applicability to any paid API) |
| Risk mitigation overstated safety of `restart: unless-stopped` | Clarified: doesn't fix cost-loops; doesn't recover deep failures |
| LLM confidence claim hand-waved | Acknowledged: not all cheap models calibrate well; rule-based fallback covers gap |
