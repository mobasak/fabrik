# Fabrik — Features

**Last Updated:** 2026-05-20

---

## Quick Reference

| Feature | Status | Audience | Headline |
|---------|--------|----------|----------|
| [Deployment Orchestration](#deployment-orchestration) | ✅ Shipped | Operator | `fabrik apply` — spec-driven deploy with 9 shape-gated registrars, saga rollback, state tracking |
| [Preplan Handoff](#preplan-handoff) | ✅ Shipped | Developer | Capture intent before scaffold; every agent reads the same intent |
| [Project Scaffolding](#project-scaffolding) | ✅ Shipped | Developer | 11 scaffold types with `.droid/`, AI guardrails, and spec emission |
| [Documentation Enforcement](#documentation-enforcement) | ✅ Shipped | Developer | Never ship undocumented code again |
| [9-Step Workflow](#9-step-workflow) | ✅ Shipped | Developer | Systematic code quality from plan to commit |
| [Kilo AI Review](#kilo-ai-review) | ✅ Shipped | Developer | AI-powered code review with fix suggestions |
| [Development Workspace](#development-workspace) | ✅ Shipped | Developer | `.droid/` per-project workspace for Kilo sessions, transcripts, cost tracking, model sync |
| [Deploy State Store](#deploy-state-store) | ✅ Shipped | Operator | `.fabrik/state/` records what was deployed; feeds audit, destroy, export, verify |
| [Registrar Audit & Reconcile](#registrar-audit--reconcile) | ✅ Shipped | Operator | Spec ↔ live drift detection across the fleet |
| [Local Dev Loop](#local-dev-loop) | ✅ Shipped | Developer | `fabrik dev` / `fabrik logs --local` / `fabrik review` |
| [State-Driven Destroy](#state-driven-destroy) | ✅ Shipped | Operator | `fabrik destroy --use-state` reverses what was actually deployed |
| [Cross-VPS Portability](#cross-vps-portability) | ✅ Shipped (import untested) | Operator | `fabrik export` / `fabrik import` — bundle VPS state for rebuild |
| [i18n Kit](#i18n-kit) | ✅ Shipped | Developer | Multi-platform i18n: one JSON format, one validator, 6 platform loaders — auto-provisioned by scaffold |
| [VPS AI Sysadmin](#vps-ai-sysadmin) | ✅ Shipped | Operator | On-demand AI system administrator — Claude Code on VPS, triggered via Telegram, autonomous diagnostics and remediation |
| [VPS Audit System](#vps-audit-system) | ✅ Shipped | Operator | 7 audit prompts + 7 runner scripts for systematic VPS health checks: security, performance, containers, observability, backup |

**Status Legend:**
- ✅ **Shipped** — Production-ready
- 🚧 **Beta** — Available but may change
- 📋 **Planned** — On roadmap

---

## Deployment Orchestration

**Status:** ✅ Shipped | **Audience:** Operator | **Since:** v0.1

> **Headline:** `fabrik apply` takes a YAML spec with a `shape:` block and deploys it end-to-end — Coolify container, DNS, SSL, plus 9 registrars that fire automatically based on shape flags.

### What It Does

The core of Fabrik. A spec at `specs/services/<id>.yaml` declares what a service needs via its `shape:` block (needs_database, is_public, has_persistent_data, etc.). `fabrik apply` runs a state-machine orchestrator that:

1. **Validates** — spec schema, deploy readiness, compose linting
2. **Provisions secrets** — resolves from `-s` flag > project `.env` > fabrik `.env` > process env
3. **Deploys** — pushes to Coolify API (with 300s grace + SSH fallback for Coolify v4 quirks)
4. **Fires registrars** — 9 shape-gated registrars provision infrastructure automatically
5. **Verifies** — health checks, postcondition validation
6. **Rolls back** on failure — reverse-order cleanup of everything created

### The 9 Registrars

Each registrar fires only when the spec's `shape:` block activates it. `infra: <registrar>: false` overrides to disable.

| Registrar | Fires when | What it provisions |
|-----------|-----------|-------------------|
| **postgres** | `needs_database: true` | Database on postgres-main, credentials in Coolify env |
| **redis** | `needs_cache: true` | Cache index on redis-main via `assignments.json` |
| **gatus** | `is_public: true` + domain set | Health monitor endpoint on status.vps1.ocoron.com |
| **backrest** | `has_persistent_data: true` | Restic backup plan → Backblaze B2 |
| **glitchtip** | kind = service/worker/wordpress | Error tracking project + DSN |
| **grafana** | always | Dashboard annotation (decorative, not driftable) |
| **authelia** | `is_admin_dashboard: true` + domain | Forward-auth middleware rule |
| **meilisearch** | `has_search_feature: true` | Search index creation |
| **prometheus** | `exposes_metrics: true` + domain | Scrape target registration |

Order matters: postgres first (other registrars may need DB), prometheus last. Destroy reverses this order.

### How To Use

```bash
# Preview what will happen (registrar resolution, compose validation)
fabrik plan specs/services/my-api.yaml

# Deploy — orchestrator runs, registrars fire, state file written
fabrik apply specs/services/my-api.yaml

# Check post-deploy health
fabrik verify my-api.vps1.ocoron.com --spec registrars

# Redeploy (same spec, fresh container)
fabrik redeploy --spec specs/services/my-api.yaml

# Tail logs
fabrik logs my-api -f
fabrik app-logs specs/services/my-api.yaml --lines 100
```

### State Machine

```
PENDING → VALIDATING → PROVISIONING → DEPLOYING → VERIFYING → COMPLETE
                ↓             ↓             ↓            ↓
              FAILED ← ROLLING_BACK ← ROLLING_BACK ← ROLLING_BACK → ROLLED_BACK
```

Every `fabrik apply` writes `.fabrik/state/<id>.json` — see [Deploy State Store](#deploy-state-store). Every registrar is isolated in try/except — one failure doesn't block others.

### Technical Details

- **Orchestrator:** `src/fabrik/orchestrator/` — `deployer.py` (state machine), `infrastructure.py` (registrar dispatch), `rollback.py` (reverse cleanup), `secrets.py`, `verifier.py`
- **Drivers:** `src/fabrik/drivers/` — 20+ integrations (coolify, postgres, redis, gatus, backrest, glitchtip, grafana, authelia, meilisearch, prometheus, cloudflare, dns, ssh, r2, supabase, etc.)
- **Spec loader:** `src/fabrik/spec_loader.py` — YAML parsing, shape validation, template merging
- **State:** `src/fabrik/state.py` — 8-field manifest written after each successful apply

---

## Preplan Handoff

**Status:** ✅ Shipped | **Audience:** Developer | **Since:** v0.2 (T3-01)

> **Headline:** Capture project intent BEFORE scaffold — every agent reads the same intent without re-deriving it.

### What It Does

The Fabrik lifecycle begins with **intent capture**. Before `fabrik scaffold` creates any files, run `fabrik preplan new <slug>` to author `docs/preplans/<YYYY-MM-DD>-<slug>.md` from a 9-section template (Idea / Project type / Shape preview / External deps / Domain / Success criteria / Out of scope / Open questions / Notes-VPS1-inventory-reminders). Refine the markdown with Opus / Claude / ChatGPT until the intent is hardened. Then `fabrik scaffold <name> --from-preplan <path>` ingests it:

1. Pre-fills `--type` from the preplan's "Project type" section
2. Pre-fills the spec's `shape:` block from the preplan's "Shape preview" yaml
3. Adopts the preplan's "Idea" first line as the project description
4. Copies the preplan to `<project>/docs/preplan.md`
5. **Appends a `Preplan:` reference line to all 4 AI guardrail files** — `AGENTS.md` (Traycer), `CLAUDE.md` (Claude Code), `AGENTS-compact.md` (Kilo), `.windsurfrules` (Windsurf) — so every downstream agent that opens the project reads the same intent

### How To Use

```bash
fabrik preplan new citation-verifier
# Edit docs/preplans/<today>-citation-verifier.md — fill in the 9 sections
fabrik scaffold citation-verifier --from-preplan docs/preplans/<today>-citation-verifier.md
```

Traycer's `docs/traycer/fabrik-workflow.md` Step 2.5 is the planning-side companion: when Traycer detects a fresh project (no scaffold yet), it looks for a matching preplan in `docs/preplans/` BEFORE asking the operator to declare anything from scratch.

### Why This Matters

Without intent capture, every downstream agent (Claude Code writing code, Kilo reviewing, Windsurf editing, Traycer planning) has to **re-derive** what the project does from incomplete context. That re-derivation is where "wait, what was this project supposed to do?" drift comes from. The preplan is the single source of truth; the 4-guardrail injection makes sure every agent reads it.

The template's `## 9. Notes` section also embeds the VPS1-inventory reminders (postgres-main:5432, redis-main:6379, X-Internal-Token pattern, `*.vps1/health` Authelia bypass, /metrics scrape target, GlitchTip DSN convention) — so agents reading the preplan stay grounded in the same VPS1 reality the scaffold-emitted guardrails enforce.

---

## Project Scaffolding

**Status:** ✅ Shipped | **Audience:** Developer | **Since:** v0.1

> **Headline:** Create production-ready projects in seconds with built-in best practices

### What It Does

Fabrik scaffold generates a complete project structure with pre-configured tooling, documentation templates, and inherited quality rules. Every scaffolded project starts with the same conventions, reducing onboarding time and ensuring consistency.

### How To Use

```bash
fabrik scaffold my-project --type python-api
```

### Marketing Copy

| Channel | Copy |
|---------|------|
| **Landing Page** | "Stop configuring, start building. Fabrik scaffolds production-ready projects with documentation, testing, and deployment ready to go." |
| **Email Subject** | "New project? Fabrik gets you to 'Hello World' in 30 seconds" |
| **Social Media** | "🏗️ fabrik scaffold my-app → Full project with docs, tests, CI/CD in seconds #DevTools" |
| **Sales One-liner** | "Fabrik scaffold eliminates boilerplate so teams ship features, not config." |

### Technical Details

<details>
<summary>Click to expand</summary>

**CLI Command:** `fabrik scaffold <name> [--type TYPE] [--github-create]`

**Generated Structure:**
- `src/` — Source code with `__init__.py`
- `tests/` — Test directory with sample test
- `docs/` — Documentation with FEATURES.md, INDEX.md
- `.env.example` — Environment template
- `AGENTS.md` — file copy of `/opt/fabrik/AGENTS.md` (Traycer)
- `AGENTS-compact.md` — file copy of `/opt/fabrik/AGENTS-compact.md` (Kilo CLI)
- `CLAUDE.md` — file copy of `/opt/fabrik/CLAUDE.md` (Claude Code) — *added T1-02 G-B5*
- `.windsurfrules` — file copy of `/opt/fabrik/.windsurfrules` (Windsurf Cascade)
- `.windsurf/rules/` — file copy of `/opt/fabrik/.windsurf/rules/`

**Optional flags:**

- `--github-create` (T1-02 G-B2): also creates a private GitHub repo at `mobasak/<name>` via `gh repo create … --yes`. Best-effort — missing `gh` binary or unauthenticated state log a warning and continue.

**Output trailer:** Every successful scaffold ends with a `# Next: cd /opt/<name>; open Traycer …` hint pointing at the Traycer-managed workflow (T1-02 G-B4).

**Project Types:** `python-api`, `saas-skeleton`, `node-api`, `file-api`, `file-worker`, `wordpress`, `docusaurus`, `chrome-extension`, `mobile-app`, `desktop-app`, `static-site`

</details>

---

## Documentation Enforcement

**Status:** ✅ Shipped | **Audience:** Developer | **Since:** v0.1

> **Headline:** Never ship undocumented code again

### What It Does

Automated checks ensure documentation stays in sync with code. When you add a feature, change a schema, or create an API endpoint, Fabrik reminds you to update the relevant docs.

### Enforcement Scripts

| Script | Trigger | Severity |
|--------|---------|----------|
| `check_changelog.py` | Code changes ≥10 lines | ERROR |
| `check_schema_sync.py` | DB model changes | ERROR |
| `check_readme_md.py` | Missing required sections | ERROR |
| `check_openapi_sync.py` | New API routes | WARNING |
| `check_test_coverage.py` | New public functions | WARNING |
| `check_env_example.py` | New env vars in code | WARNING |
| `check_compose_services.py` | New Docker services | WARNING |

### Marketing Copy

| Channel | Copy |
|---------|------|
| **Landing Page** | "Documentation that updates itself. Fabrik catches missing docs before they reach production." |
| **Email Subject** | "Your code review just got smarter: auto-doc enforcement" |
| **Social Media** | "📝 Fabrik now enforces schema.sql sync, API docs, and test coverage automatically #DevOps" |
| **Sales One-liner** | "Fabrik's enforcement scripts catch documentation drift at commit time." |

---

## 9-Step Workflow

**Status:** ✅ Shipped | **Audience:** Developer | **Since:** v0.1

> **Headline:** Systematic code quality from plan to commit

### What It Does

A structured workflow that ensures every code change goes through planning, implementation, review, and verification before commit. Token-optimized to run deterministic checks before expensive AI review.

### The Flow

```
PLAN → IMPLEMENT → SELF_REVIEW → FINAL_GATE → KILO → FINAL_GATE → VERIFY → SYNC → COMMIT
```

| Step | Action |
|------|--------|
| 1 | Traycer Plan (spec, edge cases, env vars) |
| 2 | Coder Implements |
| 2.5 | Self-Review (MANDATORY) |
| 3 | Final Gate (pre-Kilo) |
| 4 | Kilo Review Loop |
| 5 | Final Gate (post-Kilo) |
| 6 | Traycer Verification |
| 7 | Sync Only |
| 8 | Commit |

### Marketing Copy

| Channel | Copy |
|---------|------|
| **Landing Page** | "From idea to commit in 9 verified steps. No shortcuts, no surprises." |
| **Email Subject** | "The workflow that catches bugs before your users do" |
| **Social Media** | "🔄 9-step workflow: Plan → Code → Review → Gate → Ship. Every time. #QualityFirst" |
| **Sales One-liner** | "Fabrik's 9-step workflow embeds quality gates into every commit." |

---

## Kilo AI Review

**Status:** ✅ Shipped | **Audience:** Developer | **Since:** v0.1

> **Headline:** AI-powered code review with actionable fix suggestions

### What It Does

Kilo is a diff-aware AI code reviewer that analyzes changes against your task spec. It identifies issues, suggests fixes, and validates plan coverage—all with structured JSON output for automation.

### How To Use

```bash
python scripts/kilo_code_review.py review <files> --plan "Task description" --output json
```

### Marketing Copy

| Channel | Copy |
|---------|------|
| **Landing Page** | "AI code review that understands your intent. Kilo checks your changes against your plan." |
| **Email Subject** | "Meet Kilo: Your AI code reviewer that actually reads the spec" |
| **Social Media** | "🤖 Kilo AI review: $0.03-0.40 per review, catches issues humans miss #AICodeReview" |
| **Sales One-liner** | "Kilo reviews code against your spec, not just syntax—finding logic errors, not just lint." |

---

## Development Workspace

**Status:** ✅ Shipped | **Audience:** Developer | **Since:** v0.1

> **Headline:** Every scaffolded project gets a `.droid/` directory — the runtime workspace for Kilo CLI, Traycer dispatch, multi-model consultations, and development cost tracking.

### What It Does

`.droid/` is created by `fabrik scaffold` (part of `SHARED_DIRS` in `scaffold.py`) for all 11 scaffold types. `fabrik fix` also creates/updates it on existing projects. Only `review-context/` and `traycer-reports/` are git-tracked; everything else is gitignored runtime state.

The 9-step development flow generates artifacts at each stage. `.droid/` is where they accumulate:

| Path | Written by | What it stores |
|------|-----------|---------------|
| `review-context/` | Kilo agent scripts | Task/plan `.md` files Kilo reviews against (git-tracked) |
| `traycer-reports/` | `kilo_dispatch.py` | Traycer analysis reports after dispatched sessions (git-tracked) |
| `transcripts/` | `kilo_terminal_runner.py` | Raw terminal output from each agent session (timestamped, per-model) |
| `consultations/` | `kilo_consult.py` | Multi-model architecture consultation JSON (Claude, GPT, Gemini queried in parallel) |
| `responses/` | Ad-hoc gap analysis runs | Cross-model JSON responses from plan reviews |
| `docs_log/` | `docs_updater.py` | Which docs were auto-generated and when |
| `docs_queue/` | `docs_updater.py` | Pending doc generation jobs |
| `dev_tracker.db` | `dev_tracker.py` | SQLite — gate results, review costs, issues, workflow events |
| `kilo_usage.jsonl` | Kilo agent `.sh` scripts | Append-only JSONL — token counts + cost per review |
| `kilo_model_sync.log` | `kilo_model_sync_startup.sh` | Daily cron model availability sync log |

### How To Use

```bash
# Cost report across all Kilo sessions
python scripts/kilo_cost_report.py

# Query the dev tracker
python scripts/dev_tracker.py report summary
python scripts/dev_tracker.py report costs
python scripts/dev_tracker.py query "SELECT * FROM ai_usage ORDER BY timestamp DESC LIMIT 10"

# Run a multi-model consultation
python scripts/kilo_consult.py --question "Should we use saga or orchestrator pattern?"
```

### How It Connects to the Workflow

- **Step 4 (Kilo review):** reads task context from `review-context/` via `--plan .droid/review-context/task.md`
- **After each session:** `kilo_terminal_runner.py` saves the transcript and logs cost/tokens to `dev_tracker.db`
- **After each review:** generated Kilo agent scripts append to `kilo_usage.jsonl`
- **Traycer dispatch:** `kilo_dispatch.py` writes `traycer-reports/latest.md`
- **Model sync (daily cron):** `kilo_model_sync.py --sync` checks LLM provider availability, logs to `kilo_model_sync.log`

---

## Deploy State Store

**Status:** ✅ Shipped | **Audience:** Operator | **Since:** v0.2 (T2-01)

> **Headline:** `.fabrik/state/<id>.json` records exactly what `fabrik apply` deployed — which registrars fired, which UUIDs were created, at what git SHA. Every downstream command (destroy, audit, export, verify) reads from this state.

### What It Does

Every successful `fabrik apply` writes an 8-field JSON manifest to `.fabrik/state/<id>.json`. This is the backbone of the deploy/destroy/audit pipeline:

```json
{
  "applied_at": "2026-05-16T14:03:04Z",
  "coolify_app_name": "my-api",
  "coolify_uuid": "lgg84cs8gkso0swk8g4cwo80",
  "domain": "my-api.vps1.ocoron.com",
  "git_sha": "ce9d1ed...",
  "registrars_applied": [
    {"type": "gatus", "id": "my-api", "status": "created", "data_bearing": false},
    {"type": "prometheus", "id": "my-api", "status": "created", "data_bearing": false}
  ],
  "spec_hash": "72f31d75097f4672",
  "spec_path": "/opt/fabrik/specs/services/my-api.yaml"
}
```

### Who Reads It

| Command | How it uses state |
|---------|------------------|
| `fabrik apply` | Writes state after successful deploy |
| `fabrik destroy --use-state` | Reads state to replay exact teardown (see [State-Driven Destroy](#state-driven-destroy)) |
| `fabrik audit-registrars` | Reads all state files for fleet-wide drift detection (see [Registrar Audit](#registrar-audit--reconcile)) |
| `fabrik verify --spec registrars` | Reads state for postcondition gate |
| `fabrik export` | Bundles state files into portability tarball (UUIDs stripped) |
| `fabrik review` | Writes `.fabrik/review/<ts>.md` — diff + spec + registrars bundled for review |

### Directory Structure

```
.fabrik/
├── state/
│   ├── <id>.json                  # Active deploy state (one per applied spec)
│   └── _destroyed/
│       └── <id>.json.<UTC-ts>     # Archived state from destroyed services
└── review/
    └── <YYYY-MM-DD-HHMMSS>.md     # Review bundles from `fabrik review` (gitignored)
```

Also related (outside `.fabrik/`): `data/projects.yaml` holds the project registry and `data/provision-jobs/` holds SiteProvisioner saga state.

### Data-Bearing Protection

Registrars that create persistent data (postgres, redis, meilisearch) are marked `data_bearing: true` in the state file. `fabrik destroy --use-state` refuses to tear these down without `--drop-data` — preventing accidental data loss when spec has drifted.

### Technical Details

- **Writer:** `src/fabrik/state.py` — `save()` writes atomically after each `fabrik apply`
- **Lock:** `src/fabrik/locks_local.py` — file-based lock prevents concurrent applies to the same spec
- **Archive:** `state.archive_destroyed()` moves to `_destroyed/` on successful destroy
- **Portability:** `src/fabrik/portability.py` — strips `coolify_uuid` from state files for export

---

## Registrar Audit & Reconcile

**Status:** ✅ Shipped | **Audience:** Operator | **Since:** v0.2 (T2-02)

> **Headline:** Spec ↔ live drift detection across the fleet, surgical destroy, fleet-wide reconcile

### What It Does

Every `fabrik apply` writes a per-spec state file (T2-01) capturing which registrars fired. T2-02 layers four operator commands on top of that foundation:

- **`fabrik audit-registrars`** — Compares each spec's shape-resolved registrars (what SHOULD be live) to the VPS's actual state (postgres `\l`, gatus `apps/<id>.yaml`, authelia config rules, backrest `config.json` plans, glitchtip project API, meilisearch index, prometheus scrape jobs, redis `assignments.json`). Outputs a pivot table or JSON. Exit 2 if any `missing`.
- **`fabrik reconcile-all`** — Walks every deployed spec, holds a per-spec file lock (T2-01 `locks_local.file_lock`), re-runs `DeploymentOrchestrator.refresh_infrastructure` per spec. Dry-run by default; `--yes` to apply. `--filter <substr>` to scope.
- **`fabrik verify <domain> --spec registrars`** — Single-domain postcondition check using the YAML-driven `PostconditionChecker`. Fails on any `missing` registrar.
- **`fabrik destroy --partial <reg>`** — Surgical un-registration without touching DNS, Coolify app, or local files. Repeatable: `--partial gatus --partial backrest`. Backed by module-level `HANDLER_ARGS` / `HANDLER_FUNCS` exports in `orchestrator/destroyer.py` (also consumed by T4-02).

### How To Use

```bash
# Audit the whole fleet
fabrik audit-registrars

# JSON for automation (alerts, dashboards)
fabrik audit-registrars --spec specs/services/translator.yaml --json | jq .

# Re-run registrars across the fleet (dry-run)
fabrik reconcile-all --filter translator

# Single-domain registrar coverage check
fabrik verify translator.vps1.ocoron.com --spec registrars

# Surgical removal of one or more registrars
fabrik destroy specs/services/translator.yaml --partial gatus --dry-run
fabrik destroy specs/services/translator.yaml --partial gatus --partial backrest -y
```

### Status Glyphs

| Glyph | Status  | Meaning                                                          |
|-------|---------|------------------------------------------------------------------|
| `✓`   | present | Shape says yes, live state agrees                                |
| `✗`   | missing | Shape says yes, live state says no                               |
| `·`   | n/a     | Shape says skip (includes `infra:` override case, reason in detail) |
| `?`   | unknown | Probe failed (e.g. SSH error, missing token, container not found)   |

A `drift` status (live exists but in a different shape than expected) is
not yet produced by any auditor — they currently check presence only.
Follow-up auditors will compare config bags.

### Excluded by design

`grafana` is intentionally excluded from destroy handlers and reports `n/a` for audit. Grafana annotations are point-in-time decorative markers, not driftable lifecycle state.

---

## Local Dev Loop

**Status:** ✅ Shipped | **Audience:** Developer | **Since:** v0.3 (T3-03)

> **Headline:** Code, watch, and bundle for review without leaving WSL. Three CLI commands close the inner-loop gap between scaffold and `fabrik apply`.

### What It Does

Stage 2 of the Fabrik lifecycle (Agentic Implementation) is where the developer iterates on code against the spec contract. T3-03 ships three commands that keep that loop tight without round-tripping to the VPS:

- **`fabrik dev`** — runs the project's `compose.dev.yaml` stack locally via `docker compose up`. Hot-reload + bind mounts, no Coolify involvement.
- **`fabrik logs --local`** — tails `docker compose -f compose.dev.yaml logs` (sibling of the Loki-backed `fabrik logs <service>` for remote queries).
- **`fabrik review`** — bundles `git diff` + `specs/services/<id>.yaml` + `docs/preplan.md` + the resolved-registrar table into `.fabrik/review/<ts>.md`. Hand the bundle to a human reviewer or dispatch to Kilo CLI's reviewer agent.

### How To Use

```bash
cd /opt/<project>

# 1. Spin up the local dev stack (compose.dev.yaml from the scaffold)
fabrik dev -d

# 2. Tail logs in another terminal
fabrik logs --local -f
fabrik logs --local --service api -f   # one service only

# 3. When the diff looks good, bundle for review
fabrik review                          # uses HEAD by default
fabrik review --since HEAD~3           # last 3 commits
fabrik review --out /tmp/review.md     # custom output path

# 4. Dispatch (out-of-band)
kilo run --agent reviewer --input .fabrik/review/<ts>.md
```

### Why This Matters

Pre-T3-03 the only feedback channel was `fabrik apply` → VPS deploy → Loki tail. That's a multi-minute loop for every iteration. `fabrik dev` keeps the loop in-WSL (sub-second), and `fabrik review` puts the spec contract + resolved-registrar surface in front of every reviewer so they catch shape contradictions before the deploy phase (consistent with the agent-rule snippet T3-02 propagated everywhere: "don't ship code that contradicts the spec").

### Technical Details

- **Scope of `--local`**: only `fabrik logs --local` branches to docker. The remote `fabrik logs <service>` path (Loki) is unchanged — `--local` is opt-in.
- **`.fabrik/review/` is gitignored**: bundles are local artefacts. The PR diff already captures the change set; the bundle is a reviewer prompt, not a tracked file.
- **Spec auto-detection**: `fabrik review` finds the first `specs/services/*.yaml` under cwd. Override with `--spec <path>`.
- **No spec required**: works on projects without a spec (the resolved-registrar section is omitted).
- **Helpers extracted** to [`src/fabrik/dev_tools.py`](../src/fabrik/dev_tools.py) so tests can exercise `build_review_bundle` / `run_dev_compose` / `run_local_logs` without invoking docker.

---

## State-Driven Destroy

**Status:** ✅ Shipped | **Audience:** Operator | **Since:** v0.3 (T4-02)

> **Headline:** `fabrik destroy --use-state` reverses what was actually applied, not what the spec says now. The spec is allowed to drift; the teardown isn't.

### What It Does

The default `fabrik destroy <spec>` walks the spec's current `shape:` block and runs only the destroyers the current shape declares applicable. That breaks when the spec drifted between apply and destroy:

```bash
# Day 1 — apply with search
echo "shape: { has_search_feature: true }" >> spec.yaml
fabrik apply spec.yaml         # meilisearch index created

# Day 7 — search no longer needed
sed -i 's/has_search_feature: true/has_search_feature: false/' spec.yaml

# Day 30 — destroy
fabrik destroy spec.yaml       # ❌ shape says no search → meilisearch destroyer SKIPPED → orphan index
fabrik destroy spec.yaml --use-state --drop-data -y   # ✅ replays Day-1 state, reaps the index
```

### How To Use

```bash
# Dry-run to see what state-driven destroy would tear down
fabrik destroy /opt/fabrik/specs/services/hello-api.yaml --use-state --dry-run

# Safe path (no data-bearing registrars in state, or operator OK with refusal)
fabrik destroy /opt/fabrik/specs/services/hello-api.yaml --use-state -y

# State has postgres / redis / meilisearch → must explicitly drop data
fabrik destroy /opt/fabrik/specs/services/hello-api.yaml --use-state --drop-data -y
```

### Why This Matters

Two invariants the vision insists on (Stage 3 — Proper Registration) are now load-bearing on teardown too:

1. **Zero leaks.** Every registrar that `fabrik apply` ran ends up in the state file; `--use-state` guarantees every one of them runs its destroyer. No orphan auth rules, no orphan meilisearch indexes, no ghost gatus monitors.
2. **No silent data destruction.** State files mark `postgres / redis / meilisearch` entries with `data_bearing: true` (per [`state.DATA_BEARING_REGISTRARS`](../src/fabrik/state.py#L69)). `--use-state` refuses with an explicit error if any are present and `--drop-data` isn't set:

   ```text
   ❌ data-bearing-guard refused — state has data-bearing registrars (meilisearch, postgres);
      re-run with --drop-data to confirm destruction
   ```

   Operators have to type the data-destruction intent every single time.

### Technical Details

- **Phase 0** — data-bearing guard. Scans state's `registrars_applied` for `data_bearing: true` entries; refuses pre-flight if `--drop-data` not set.
- **Phase 1** — canonical reverse-order registrar teardown using `reversed(_REGISTRAR_ORDER)`: `prometheus → meilisearch → authelia → grafana → glitchtip → backrest → gatus → redis → postgres`. Order is enforced because postgres-last avoids FK violations against authelia session rows. Grafana is intentionally skipped (annotations are decorative). Dispatch uses T2-02's module-level `HANDLER_FUNCS` + `HANDLER_ARGS` maps.
- **Phase 2** — Coolify app (always), DNS (gated by `--keep-dns` + spec domain), local files (gated by `--keep-files`).
- **On success** — `state.archive_destroyed(spec.id)` moves `<id>.json` → `_destroyed/<id>.json.<UTC-ts>`. State file is the deploy-state record; the archive preserves the audit trail without leaving the file in place to confuse future audits.
- **Mutually exclusive with `--partial`** — both flags exist for distinct surgical purposes (per-registrar vs. per-state-file). The combination errors out (exit 2).
- **Handler exception → bounded error.** A single failing destroyer doesn't abort the rest of the teardown; the failure goes into the report as an `error` ActionResult and `--use-state` exits 2 so CI can catch it.

### Acceptance Reference

Epic Brief Success Criterion 3. Live verification: `pytest tests/test_destroy_use_state.py -v` (16/16 pass), including the primary-path `TestPrimaryPathSpecDrift::test_a_resources_destroyed_even_after_shape_b`.

---

## Cross-VPS Portability

**Status:** ✅ Shipped (export verified; import path untested in this epic) | **Audience:** Operator | **Since:** v0.3 (T4-03)

> **Headline:** `fabrik export` produces a portable tarball that captures every resource `fabrik apply` registers on this VPS. `fabrik import` provides the rebuild scaffold on a fresh target. Zero secrets, zero UUIDs.

### What It Does

If vps1 dies — or you want to spin up vps2 as a base for a second customer / staging environment — the portability bundle lets you carry the registration story across machines without re-running every `fabrik apply` ticket by hand:

```bash
# On vps1 — produce the bundle
fabrik export --out /tmp/vps1-base.tar.gz

# Transfer to the new VPS (operator's choice: scp, rsync, etc.)
scp /tmp/vps1-base.tar.gz vps2:/tmp/

# On vps2 — see what would be restored (dry-run, default)
fabrik import /tmp/vps1-base.tar.gz

# Re-populate .env secrets per the bundle's secrets-redacted.json checklist
# (the ~0.5-day manual cost pack §28 'Secrets ergonomics' calls out)
nano /opt/fabrik/.env

# Execute the restore (stubbed in this epic; live roundtrip lands in vps2 stand-up)
fabrik import /tmp/vps1-base.tar.gz --apply
```

### What's Inside the Bundle

```text
fabrik-export-vps1-YYYY-MM-DD.tar.gz
├── manifest.json                  # version + section counts + untested_paths
├── README.md                      # restore steps + prerequisites
├── secrets-redacted.json          # .env KEY NAMES (never values)
├── specs/services/*.yaml          # every service spec
├── state/*.json                   # T2-01 state files, coolify_uuid stripped
├── coolify/{applications,services,projects}.json    # UUIDs recursively stripped
├── monitoring/{prometheus,alertmanager,redis-assignments,postgres-allocations}*
├── monitoring/grafana-dashboards/  # repo-local mirrors
├── authelia/configuration.yml      # SSH-pulled (best-effort)
└── backrest/config.json            # SSH-pulled (best-effort)
```

### Security Invariants (test-enforced)

1. **No plaintext secret values.** `_redact_env_keys` reads only up to the first `=` of each `.env` line. The test byte-scans the entire gzip stream for known values and asserts zero hits.
2. **No Coolify UUIDs.** `_strip_uuids` recurses both keys (14 known UUID-named fields including `private_key_uuid`, `server_uuid`, `deployment_uuid`) and bare 24-alphanum string values. The test scans 5 distinct UUID markers across all bundle entries.
3. **No Coolify private-key UUIDs** (a special case of the above) — guarantees the target can't accidentally inherit the source's git deploy-key references.

### Why Import Is Shipped Untested

The real roundtrip needs a fresh Ubuntu VM with bootstrapped Coolify + postgres-main + redis-main. Pack §28 explicitly defers this to the vps2 stand-up. Until then:

- The `import` pipeline parses the bundle, validates the manifest, and emits a restore plan.
- The `--apply` flag runs but ends at a documented stub (`phase: real_run / status: stub`).
- The bundle README enumerates manual follow-ups not automated by import: LetsEncrypt cert transfer, DNS provider re-binding, OAuth provider re-creation, postgres/meilisearch data restore (only if `--include-data` was used at export).

### Acceptance Reference

Pack v3.2 §EPIC SCOPE Tier 4 G-J2 (effort revised v2: +0.5 day for secrets ergonomics). Live verification: `pytest tests/test_portability.py -v` (23/23 pass). Sample run on `/opt/fabrik` produced a 44 KB tarball with 26 Coolify applications, 348 redacted secret keys, and zero UUID leaks.

---

## i18n Kit

**Status:** ✅ Shipped | **Audience:** Developer | **Since:** v0.4

> **Headline:** One JSON format, one validator, 6 platform loaders — auto-provisioned by `fabrik scaffold` for every GUI project type.

### What It Does

Every GUI scaffold type ships with internationalization out of the box. `fabrik scaffold my-app --type saas-skeleton` places the right i18n loader, starter JSON, validation script, and reference docs into the project. Coding agents find these files on day one and use them — no manual setup, no third-party library installation.

### Platform Coverage

| Scaffold type | Strategy | What gets placed |
|---------------|----------|-----------------|
| **saas-skeleton** | React context | `lib/i18n/I18nProvider.tsx` + `server.ts` + `LanguageSwitcher.tsx`, `public/i18n/en.json` |
| **static-site** | Vanilla DOM | `static/js/i18n.js`, `static/i18n/en.json`, HTML snippets |
| **desktop-app** | Vanilla DOM | Same as static-site (Electron is Chromium) |
| **chrome-extension** | Chrome adapter | `extension/src/i18n.js`, `scripts/chrome_messages.py` (generates `_locales/`) |
| **mobile-app** | RN adapter | `scripts/sync_rn_locales.py` (syncs to `src/locales/` for i18next) |
| **docusaurus** | Docusaurus adapter | `scripts/sync_docusaurus.py` (syncs custom strings to `i18n/<lang>/code.json`) |

All types also receive: `scripts/validate_i18n.py` (3-level validator), `en.json` + example translations, `docs/reference/multilingual-plan.md` (1170-line architecture bible).

### Shared JSON Format

```json
{
  "_meta": { "language": "en", "nativeName": "English", "completeness": 1.0 },
  "nav": { "home": "Home", "settings": "Settings" },
  "common": { "save": "Save", "cancel": "Cancel" },
  "error": { "not_found": "Page not found" }
}
```

Nested dot-path keys (`nav.home`), `{variable}` interpolation, `_meta` block for completeness tracking. Same format consumed by all 6 loaders.

### Translation Workflow

```
1. Developer writes English UI using t('key') or data-i18n="key"
2. en.json is the source of truth — all keys present
3. AI translates en.json → tr.json (Claude/GPT first pass)
4. python scripts/validate_i18n.py --validate tr
   ├── Level 1: Structural (keys match, placeholders preserved) — free, instant
   ├── Level 2: Back-translation via Kilo CLI (semantic drift detection)
   └── Level 3: Native-speaker critique via Kilo CLI (tone/grammar + auto-fix)
5. Ship.
```

### Validation

Per-language model selection optimized by the validator:

| Language | Kilo Model | Rationale |
|----------|-----------|-----------|
| Turkish | `kilo/x-ai/grok-4.3` | Best at Turkish register (sen vs siz) |
| Spanish | `kilo/~google/gemini-pro-latest` | Catches technical term misses |
| Portuguese (BR) | `kilo/~google/gemini-pro-latest` | Knows BR tech keeps English terms |
| Japanese | `kilo/anthropic/claude-sonnet-4.6` | Best at cultural nuance |
| Default | `kilo/x-ai/grok-4.3` | Fallback for any new language |

Override per-run: `KILO_I18N_MODEL="kilo/x-ai/grok-4.3" python scripts/validate_i18n.py --validate tr`

### Rule Pack Integration

- **60-saas-ui.md**: "Use scaffolded `lib/i18n/` — do not install next-intl or react-i18next"
- **70-chrome-ext.md**: "Sync i18n via `scripts/chrome_messages.py`"
- **80-mobile.md**: "Source-of-truth at `static/i18n/`, sync via `scripts/sync_rn_locales.py`"

These rules ensure coding agents use the scaffolded i18n system rather than installing their own.

### Technical Details

- **Source:** `templates/i18n-kit/` in the fabrik repo (19 files, ~1600 LoC)
- **Provisioner:** `_provision_i18n()` in `scaffold.py`, called from `create_project()` after type-specific scaffolder runs
- **Types map:** `I18N_ENABLED_TYPES` in `scaffold.py` — maps scaffold type → strategy (`react`, `vanilla`, `chrome`, `rn`, `docusaurus`)
- **Battle-tested:** Originally built for the Tojlo project (738 keys, 6 languages, 24 pages), generalized for all fabrik GUI types

---

## VPS AI Sysadmin

**Status:** ✅ Shipped | **Audience:** Operator | **Since:** v0.5 (2026-05-20)

> **Headline:** On-demand AI system administrator — Claude Code Opus running locally on VPS. Talks via Telegram. Queries 15 infrastructure APIs directly. Acts autonomously on safe operations. Proactive health checks every 15 min. Morning briefings. Weekly security patrols. Monthly backup verification. Shift notes for memory between sessions. Incident playbooks. Service criticality tiers. 1136 lines of code, zero cost when idle.

### Three Trigger Paths

1. **You message Telegram** → bot spawns Claude Opus → Claude runs commands locally (docker, curl, audit scripts) → responds → session lives until "done" or 10min silence → shift notes written
2. **Alert fires** → Alertmanager → Apprise → Telegram (existing flow) → you reply to investigate → Claude wakes with full context
3. **Proactive cron** (every 15min) → bash checks 11 Prometheus thresholds + TLS cert expiry + disk prediction (zero tokens) → only if anomaly detected → Claude wakes, diagnoses, acts autonomously, reports to Telegram

### Five Scheduled Routines

| Routine | Schedule | Uses Claude? | What it does |
|---|---|---|---|
| Proactive check | Every 15 min | Only on anomaly | 10+ PromQL thresholds + cert expiry + disk prediction. Bash prefilter = zero cost when healthy. Claude acts + reports when something is wrong. |
| Morning report | Daily 08:00 | Always | Collects: containers, disk, RAM, certs, alerts, shift notes, yesterday's actions. Claude formats concise Telegram briefing with trends. |
| Security patrol | Monday 08:30 | Always | Runs `03-security.sh`, Claude analyzes against `03-security-hardening.md` checklist. Reports GREEN/YELLOW/RED with findings. |
| Maintenance | Sunday 03:00 | Never | Pure bash: checks dangling images/volumes, journal size, backup freshness, restart counts, stale containers, cert expiry. |
| Backup verification | 1st of month 04:00 | Always | Runs `06-backup.sh`, Claude analyzes against `06-backup-disaster-recovery.md` checklist. Reports coverage gaps + recovery confidence. |

### Infrastructure APIs (15 services, queried locally)

| Service | What the sysadmin gets |
|---|---|
| Prometheus (`:9090`) | Container + host metrics, 13 alert rules, scrape target health |
| Loki (`:3100`) | All container logs — errors, stack traces, crash messages |
| Grafana (`:3000`) | Dashboard + datasource health (8 dashboards, 2 datasources) |
| Alertmanager (`:9093`) | Active firing alerts, silences |
| Gatus (`:8080`) | Uptime status for 30+ endpoints |
| GlitchTip (`:8000`) | Application errors, unhandled exceptions |
| Netdata (`:19999`) | Real-time per-second system metrics |
| Apprise (`:8000`) | Send notifications to Telegram |
| Pushgateway (`:9091`) | Drift audit metrics |
| Meilisearch (`:7700`) | Search index health |
| Docker CLI | Container lifecycle — ps, stats, logs, restart, update, inspect |
| Node exporter (via Prometheus) | Host CPU, RAM, disk, network |
| cAdvisor (via Prometheus) | Per-container resource metrics |
| Postgres exporter (via Prometheus) | Database connections, query rates |
| Redis exporter (via Prometheus) | Cache memory, hit rate |

### Safety Model

- **Autonomous:** restart application/platform containers, scale memory up (check host capacity first), all read operations, write shift notes
- **Ask first:** scale down, stop containers, anything destructive-adjacent, anything unsure about
- **Never:** delete anything, touch networking/firewall/boot config, modify critical-infra or monitoring, modify env vars

### Veteran Sysadmin Features

| Feature | How |
|---|---|
| **Incident playbooks** | 6 documented procedures in system prompt: OOM, restart loop, disk full, host memory, target down, cert expiry |
| **Service criticality tiers** | P0 (revenue: ocoron.com) → P1 (platform: traefik, postgres) → P2 (operations) → P3 (monitoring) → P4 (utility). Triage by tier when multiple issues. |
| **Shift notes** | `logs/sysadmin-shift-notes.md` — Claude reads at session start, writes at session end. Remembers context between conversations. |
| **Action log** | `logs/sysadmin-actions.jsonl` — every conversation logged with timestamp, session ID, message, response. Persistent audit trail. |
| **Audit prompt integration** | Weekly security + monthly backup routines reference the matching audit-prompt checklist. Claude doesn't improvise — it checks against documented criteria. |

### Components (1136 lines total)

| File | Lines | Purpose |
|---|---|---|
| `scripts/sysadmin/bot.py` | 332 | Telegram bot — spawns Claude Opus per message, JSON output parsing, session management, action logging, health endpoint `:8017`, daily heartbeat |
| `scripts/sysadmin/system-prompt.txt` | 232 | Sysadmin brain — role, 15 APIs, container classification, 6 incident playbooks, P0-P4 criticality, shift notes protocol, communication protocol, safety rules |
| `scripts/sysadmin/proactive-check.sh` | 202 | Two-stage cron — 11 checks (10 PromQL + Prometheus connectivity) + cert expiry. Bash prefilter (zero tokens). Claude acts on anomaly. Rate-limited 5/hr. |
| `scripts/sysadmin/morning-report.sh` | 124 | Daily briefing — containers, disk, RAM, certs, alerts, shift notes, yesterday's actions. Claude formats Telegram-friendly summary. |
| `scripts/sysadmin/weekly-maintenance.sh` | 115 | Sunday cleanup report — dangling resources, journal, backup freshness, restart counts, stale containers, cert expiry. Pure bash, no Claude. |
| `scripts/sysadmin/monthly-backup-verify.sh` | 70 | Backup audit vs DR checklist — coverage, freshness, retention, recovery confidence. |
| `scripts/sysadmin/weekly-security.sh` | 61 | Security audit vs hardening checklist — GREEN/YELLOW/RED with findings. |
| `ops/vps-sysadmin-bot.service` | 20 | Systemd unit — auto-start, `Restart=always`, `After=network.target docker.service` |

### Technical Details

- **Model:** Claude Opus (`--model opus`) — best reasoning for infrastructure diagnosis
- **Bot:** systemd service on VPS, `Restart=always`, health endpoint at `:8017/health`
- **Session:** `claude -p` per message, `--resume` for follow-ups, cleared on "done" / 10min timeout
- **System prompt:** injected via `--system-prompt` (NOT CLAUDE.md — that's for WSL development)
- **Auth:** Max subscription via `claude auth login` — no API key stored on VPS
- **Token economics:** $0 on quiet days (bash prefilter handles 95%), $5-15/month typical (included in Max)
- **Knowledge sync:** `scripts/sync-vps-sysadmin.sh` pushes docs, audit scripts, specs from WSL to VPS after any change

### Full Reference

- `docs/infrastructure/vps-ai-sysadmin.md` — 697-line canonical reference: architecture, firewall docs, session model, knowledge sync, notification templates, all scheduled routines, troubleshooting, 9-step replication recipe, files manifest

---

## VPS Audit System

**Status:** ✅ Shipped | **Audience:** Operator | **Since:** v0.5 (2026-05-20)

> **Headline:** 7 structured audit prompts + 7 runner scripts for systematic VPS health evaluation. Designed for parallel AI agent dispatch — each audit runs independently, returns a domain-specific report.

### What It Does

Each audit covers one domain of VPS health. The prompt defines what to check, the script collects the diagnostic data, and Claude Code (or any AI) analyzes it.

| Audit | Script | Prompt | Scope |
|---|---|---|---|
| Full system | `01-full-system.sh` | `01-full-system-audit.md` | CPU, memory, disk, network, services, security, Docker — all 8 domains |
| Container health | `02-container-health.sh` | `02-container-health.md` | Fleet stability, resource pressure, crash loops, Coolify issues |
| Security | `03-security.sh` | `03-security-hardening.md` | Firewall, TLS, SSH, Authelia, container isolation, secrets |
| Performance | `04-performance.sh` | `04-performance-bottleneck.md` | CPU/memory/disk/network bottleneck identification |
| Observability | `05-observability.sh` | `05-observability-pipeline.md` | Prometheus, Loki, Grafana, GlitchTip, Gatus pipeline health |
| Backup/DR | `06-backup.sh` | `06-backup-disaster-recovery.md` | Backrest plans, B2 connectivity, coverage, recovery readiness |
| Hardening verify | `08-hardening-verify.sh` | `08-hardening-remediation.md` | Post-audit remediation verification with pass/fail score |
| Pre-production | — | `07-pre-production-checklist.md` | Go-live readiness across all layers |

### How To Run

```bash
# Single audit (run from WSL):
ssh vps 'sudo bash -s' < scripts/audit/01-full-system.sh | claude -p "analyze this"

# All audits in parallel (6 agents):
for i in 01 02 03 04 05 06; do
  ssh vps 'sudo bash -s' < scripts/audit/${i}-*.sh > /tmp/audit-${i}.txt &
done; wait

# Via the sysadmin bot (from Telegram):
"run a full security audit"
"check backup health"
"run performance analysis"
```

### Technical Details

- Scripts run with `sudo` (root access for Docker, iptables, journalctl)
- Each script takes 10-30 seconds, outputs structured text
- Prompts include analysis checklists, thresholds, and output format requirements
- First run (2026-05-19) identified: broken Promtail log pipeline, duplicate monitoring containers, empty backup retention, 28 containers without memory limits — all fixed

---

## WordPress Automation

**Status:** Extracted to `/opt/wpf/` | **Audience:** Operator | **Since:** v0.1 (fabrik), standalone since 2026-05

> **Headline:** WordPress site lifecycle was built inside fabrik (Phase 2), then extracted to a standalone project at `/opt/wpf/` — the WordPress Factory.

### History

The WordPress automation engine (13-stage deployer, planner, preset loader, WP-CLI driver, REST API client, theme/page/SEO/analytics/forms/menu modules — ~9,700 LoC) was originally built inside fabrik as Phase 2. It used fabrik's drivers (Coolify, Backrest, Gatus, Cloudflare via site-provisioner) to deploy WordPress sites from YAML specs.

In May 2026, the engine was extracted to `/opt/wpf/` as a standalone project because:

1. WordPress sites use `kind: wordpress` specs consumed by `wpf wp apply` — they never flow through `fabrik apply` (which only validates `kind: service`)
2. wpf manages its own registrar dispatch (Backrest, Gatus, Cloudflare WAF) independently of fabrik's 9-registrar pipeline
3. wpf will become a SaaS product (GUI wizard, Watchdog AI, billing) — concerns that don't belong in the deployment platform

### Current State

- **fabrik:** WordPress scaffold type still exists (creates the project structure), but `deploy_router.py` raises `NotImplementedError` for WordPress deploys — use wpf instead
- **wpf (`/opt/wpf/`):** Has the full engine, golden-base Docker image system, 133 premium plugin zips, and site specs. Currently in Phase 1+2 (Foundation + Golden Base) — first deploy target is `ocoron.com`
- **Shared drivers:** wpf calls the same VPS infrastructure fabrik does (Coolify API via `COOLIFY_API_TOKEN`, site-provisioner at `:18014`, redis-main, Backrest) but manages WordPress site lifecycle independently

---

## See Also

- [README.md](../README.md) — Project overview
- [CHANGELOG.md](../CHANGELOG.md) — Version history
- [AGENTS.md](../AGENTS.md) — AI agent briefing
- [DEPLOYMENT.md](DEPLOYMENT.md) — Deploy flows, state machine, secrets
- [docs/operations/fabrik-lifecycle.md](operations/fabrik-lifecycle.md) — 4-stage lifecycle (Intent → Implementation → Registration → Verification)
