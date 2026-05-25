# Fabrik Development & Deployment Workflow — End-to-End

**Audience:** Owner reference + onboarding agents (Traycer / Claude Code / Cascade / Kilo CLI).
**Authority:** This document narrates the workflow. Authoritative rule sources stay in [AGENTS.md](../../AGENTS.md), [CLAUDE.md](../../CLAUDE.md), [.windsurfrules](../../.windsurfrules), [AGENTS-compact.md](../../AGENTS-compact.md), and the topic packs under [.windsurf/rules/](../../.windsurf/rules/). When this document and a rule file disagree, the rule file wins — update this document.
**Updated:** 2026-05-14
**Verification:** Every factual claim below has a grep / file check; see [§ Verification anchors](#verification-anchors) at the end.

---

## 0. Mental model

You are a solo developer in WSL Ubuntu on Windows. Every project deploys to one x86_64 VPS at `172.93.160.197`, orchestrated by Coolify (Docker Compose), routed by Traefik with Let's Encrypt, fronted by Authelia for admin UIs, protected by `X-Internal-Token` for API-to-API calls, and observed by Gatus + Prometheus + Grafana + Loki + GlitchTip + Netdata. The same code must run in three environments without modification: WSL dev (Postgres on localhost via `.env`), VPS Docker (`postgres-main` on the `coolify` network), and Supabase (env vars). Philosophy: **fast but pro** — ship, iterate, automate; no over-engineering.

Four families of files orchestrate the agents:

| File | Reader | Purpose |
|---|---|---|
| [AGENTS.md](../../AGENTS.md) | **Traycer** (planner) | Identity, infrastructure inventory, pack registry, pre-flight, planning constraints |
| [CLAUDE.md](../../CLAUDE.md) | **Claude Code** (coder) | Always-on rules + HARD STOPS for Claude Code |
| [.windsurfrules](../../.windsurfrules) | **Windsurf Cascade** (coder) | Always-on rules + HARD STOPS for Cascade |
| [AGENTS-compact.md](../../AGENTS-compact.md) | **Kilo CLI** (coder, via `opencode.json`) | Self-contained always-on rules for Kilo |
| [.windsurf/rules/](../../.windsurf/rules/) (21 packs) | All 3 coders | Scope-relevant topic deep-dives, loaded on demand |

---

## 1. Idea → Pre-research

You do external research with ChatGPT / Claude / Gemini, then drop the writeup at `docs/development/plans/00-research.md`. This is Traycer's starting context — a ground-truth dump from outside the codebase. The file is ad-hoc per ticket (not permanently present).

## 2. Scaffold the project

```bash
fabrik scaffold <name> --type <type>
```

`<type>` is one of **11** scaffold types: `python-api`, `node-api`, `saas-skeleton`, `chrome-extension`, `mobile-app`, `desktop-app`, `file-api`, `file-worker`, `wordpress`, `docusaurus`, `static-site`.

The scaffold writes the full project tree under `/opt/<name>/` and emits `specs/services/<name>.yaml` with a populated `shape:` block per `templates/<type>/defaults.yaml`. The `shape:` block — `kind` (`service` / `worker` / `wordpress` / `static`) + flags (`is_public`, `has_persistent_data`, `needs_database`) — drives which infrastructure registrars run later during `fabrik apply`: `postgres`, `redis`, `gatus`, `backrest`, `glitchtip`, `grafana`, `authelia`, `meilisearch`, `prometheus`.

For API scaffolds (`python-api`, `node-api`, `file-api`), the scaffold also writes — automatically, no manual ticket needed — `internal_auth.py` (M2M `X-Internal-Token` validation via `hmac.compare_digest`), `metrics.py` (Prometheus business counters `REQUEST_COUNT` / `ERROR_COUNT` / `ACTIVE_JOBS` / `PROCESSING_COUNT`), `/metrics` endpoint (Authelia-bypassed), `glitchtip_init.py` / `glitchtip_init.js` (Sentry SDK pointed at GlitchTip; no-op if `GLITCHTIP_DSN` unset; wired in `main.py` BEFORE app construction), `SERVICE_INTERNAL_SECRET_KEY` line in `.env.example`, and a structured logger module (`logger.py` / `logger.js`) emitting JSON with `SERVICE_NAME` from env.

The scaffold also propagates `.windsurfrules`, `.windsurf/rules/`, and `.windsurf/workflows/` so the new project carries the same agent contract.

**Authoritative shape matrix:** `src/fabrik/spec_loader.py::Shape` docstring (divergence from `templates/<type>/defaults.yaml` is a failing test in `tests/test_spec_generator.py`).
**Registrar applicability matrix:** `src/fabrik/orchestrator/infrastructure.py::resolve_applicability()`.

## 3. Plan with Traycer

Traycer reads `AGENTS.md` every interaction. The ticket workflow is `trigger` → `brief` → `plan` → `breakdown` → `execute`, defined in [docs/traycer/traycer-managed-development-workflow/](../traycer/traycer-managed-development-workflow/) (with a human-readable reference copy at [docs/traycer/fabrik-workflow.md](../traycer/fabrik-workflow.md)).

Before generating any plan, Traycer runs **6 mandatory pre-flight checks** ([AGENTS.md § MANDATORY ORCHESTRATOR PRE-FLIGHT](../../AGENTS.md)):

1. **PORTS.md** — assign a free port (Python 8000–8099, frontend 3000–3099). State it.
2. **BUSINESS_MODEL.md** — duplicate / similar project check. State the finding.
3. **Fabrik Microservices table** — use existing internal APIs before planning new logic.
4. **Hardware audit** — confirm all Docker images support `linux/amd64`.
5. **Design System** — for any UI surface, read `.windsurf/rules/core/ocoron-design-system.md` before generating any spec or copy.
6. **External Knowledge Verification** — for 3rd-party APIs (Coolify, Paddle, Traefik, Authelia, Supabase, Cloudflare, n8n — Stripe NOT available to TR entities), verify the current contract against live docs before writing the ticket; cite the URL in the ticket's `References:` field. After 3 search misses → mark ticket `BLOCKED: external-research-needed`.

Then Traycer applies the **12 planning constraints**: solo dev, x86_64 only, budget-conscious, reuse existing microservices, prebuilt containers, port conflicts, Coolify deployment, no Alpine, complete dependent modules first, DNS via site-provisioner, scaffold immutability (no reorganization), surface state conflicts explicitly.

Traycer's deliverable is one or more tickets. Each carries: **Scope** (which files), **Acceptance Criteria** (testable), **Final Gate Instruction** (literal command + flags), **Lessons Learnt** field (`none` or required), and **Implementation Notes**.

Critically, Traycer also **injects rule-pack guidance** into the coding-agent prompt at query-construction time. It reads `project.yaml::type` → default packs (e.g., `python-api` → `PY_CORE`), adds feature overlays based on ticket scope (`API_CONTRACTS` for endpoints, `DATA_PG` for migrations, `SECURITY` for auth, `TESTING` always, `OBSERVABILITY` for health/logging, `RAG_SEARCH` for vector work, `PAYMENTS` for Paddle, `MULTI_TENANT` for RLS) and emits up to **40 lines total** (6 per pack, type defaults preserved if overlays would overflow). Agents do NOT self-select packs — that's Traycer's authority. Mechanics: [scripts/kilo_dispatch.py](../../scripts/kilo_dispatch.py) (constants `MAX_RULE_LINES = 40`, `MAX_LINES_PER_PACK = 6`).

## 4. Pick a coder

Three coding paths, each with its own bootstrap:

| Coder | Bootstrap | How packs reach it |
|---|---|---|
| **Claude Code** | [CLAUDE.md](../../CLAUDE.md) (≤6,000 chars, enforced) | Reads scope-relevant packs from `.windsurf/rules/` on demand |
| **Windsurf Cascade** | [.windsurfrules](../../.windsurfrules) | Cascade auto-loads packs via frontmatter (`activation: glob` or `model_decision`) |
| **Kilo CLI** | [AGENTS-compact.md](../../AGENTS-compact.md) | `scripts/kilo_dispatch.py` injects the bootstrap + selectively-chosen packs into every prompt |

All three carry the same always-on contract: **FIRST OUTPUT line** (`RULES ACTIVE: <agent> | <3 rules applied>`), **Orient** (read `project.yaml`, `AFCL.md`, scope-relevant packs), **Behavior** (check-before-create, present-before-execute, stay-on-task, surface state conflicts), **Completion Contract** (IMPLEMENT → GATE → CHANGELOG → LESSONS LEARNT → EXIT), and a **HARD STOPS** table forbidding `git commit/push` without explicit user ask, `localhost` in connection strings, Alpine base images, raw `pip install`, Authelia SIGHUP, Gatus UUID names, `/tmp/` usage, FastAPI `except Exception` swallowing `HTTPException`, etc.

Scope-relevant packs that auto- or hand-load during work:

- [10-python.md](../../.windsurf/rules/core/10-python.md) — FastAPI lifespan, pydantic-settings, function-level config, FastAPI exception order (HTTPException re-raised before generic Exception).
- [30-ops.md](../../.windsurf/rules/core/30-ops.md) — Dockerfile / compose template, Docker DNS no-`localhost`, `fabrik redeploy` sequence, Authelia restart procedure, Gatus stable aliases, post-deploy checklist.
- [35-security-auth.md](../../.windsurf/rules/core/35-security-auth.md) — JWT lifecycle, CORS, CSP, canonical M2M `internal_auth.py` pattern, sensitive-file backup procedure, password policy (32-char `[a-zA-Z0-9]` via `secrets.choice()`).
- [55-observability.md](../../.windsurf/rules/core/55-observability.md) — structlog/pino patterns, GlitchTip discipline (no duplicate `logger.exception()` traceback), `/health` real-dep test, Gatus stable DNS rule.

## 5. Implementation

The coder implements within ticket Scope. Adjacent fixes in the same files are OK; out-of-scope edits are forbidden. Forbidden patterns: hardcoded secrets / `localhost`, silent failures, bare `pip install` (PEP 668 — must use `/opt/<project>/.venv/bin/pip`), Alpine base images, `/tmp/` usage, module-level config, raw SQL DDL (Alembic only; `db/schema.sql` is reference only), FastAPI `except Exception` swallowing `HTTPException` (always `except HTTPException: raise` first), `console.log()` / `print()` (use scaffolded structlog / pino), duplicate `logger.exception()` traceback when GlitchTip auto-captures.

One test for the highest-risk path is required (skip for docs-only tickets).

## 6. Doc Sync Matrix

Every code change triggers a documentation update — gate-enforced. The matrix:

| Change | Update |
|---|---|
| New env var | `.env.example` + Why / How / Default comment |
| Real secret value | `.env` (gitignored) |
| External cred setup changed | `docs/CONFIGURATION.md` |
| Code / Docker / deps changed | `CHANGELOG.md` (`## [Unreleased]` → `### Added\|Changed\|Fixed — Title (YYYY-MM-DD)`) |
| File added / removed / renamed | `INDEX.md` |
| Tech stack or setup changed | `README.md` |
| API / SDK / CLI / integration changed | `docs/QUICKSTART.md` |
| New port allocated | `PORTS.md` |
| Recurring symptom | `docs/TROUBLESHOOTING.md` (Symptom / Cause / Fix) |
| Feature shipped / deprecated | `docs/FEATURES.md` |
| New plan | `docs/development/plans/YYYY-MM-DD-plan-<name>.md` |
| Schema migration | Alembic + `db/schema.sql` |
| Future idea | `docs/STRATEGIC_BACKLOG.md` (Now / Later / Context) |
| Aha moment | `docs/LESSONS_LEARNT.md` |
| Silicon ceiling | `AFCL.md` |
| Pricing / GTM | `docs/BUSINESS_MODEL.md` |

**Skip:** refactor/docs/test-only → `CHANGELOG.md` only.

## 7. Gate

```bash
python scripts/final_gate.py --lean --json     # Tier 1: standard ticket (showstoppers only)
python scripts/final_gate.py --json            # Tier 2: milestone / multi-component / schema / auth (full)
python scripts/final_gate.py --systemic --json # Tier 3: epic closure (repo health)
```

- **Tier 1 (lean):** ruff / syntax / JSON / YAML / secrets / env contract / schema sync — fast, no context poisoning.
- **Tier 2 (full):** Tier 1 + mypy / bandit / semgrep + changelog / index / readme / test-proposal consistency. Diff-aware.
- **Tier 3 (systemic):** repo-wide health — docker compliance, ports, docs sprawl, duplicates, deps sync, health endpoints, watchdog, env contract.

The gate iterates **up to 3 times** internally, auto-fixing where it can. The coder iterates externally until `"status": "success"`. On success the gate **auto-stages** changes (`git add` only). The coder does NOT commit or push — that is the owner's decision. Maximum **5 external review iterations** before the coder escalates.

Optional manual review tools: [`scripts/kilo_code_review.py`](../../scripts/kilo_code_review.py) (AI multi-agent review on staged diff), [`scripts/kilo_docs_enforcer.py`](../../scripts/kilo_docs_enforcer.py) (bulk doc generation).

## 8. Lessons learnt

If the ticket revealed a non-obvious lesson (incident, anti-pattern, surprising vendor behavior), add a structured entry to [docs/LESSONS_LEARNT.md](../LESSONS_LEARNT.md). Otherwise the ticket's `Lessons Learnt:` field reads `none`. Silence (neither) is failure.

## 9. Commit + push (owner action)

```bash
git commit -m "..."
git push
```

The gate's auto-stage hands you a clean diff. Never force-push to main without explicit reason; never `--no-verify`.

## 10. Deploy via Coolify

Two CLI entry points, both routing through the same orchestrator pipeline:

- **`fabrik deploy`** — modern, `project.yaml`-driven.
- **`fabrik apply`** — legacy, spec-driven. Reads `specs/services/<name>.yaml`; runs the registrars whose flags match the `shape:` block.
- **`fabrik redeploy <app>`** — re-pulls a git-sourced app. **CRITICAL:** Coolify pulls from the GitHub remote, NOT from your local `/opt/<name>/` clone. Mandatory sequence: `git commit` → `git push` → `fabrik redeploy`. Skipping `git push` silently redeploys the previous remote commit. Full reference: [docs/DEPLOYMENT.md](../DEPLOYMENT.md).

Coolify pulls the image, runs `docker compose up`, attaches the container to the `coolify` Docker network. Traefik labels (scaffold-emitted) handle routing:

- Admin UI → `authelia-forward@docker,gzip@docker`
- API service → `gzip@docker`
- Public service → no auth middleware

DNS for `*.vps1.ocoron.com` is managed by **site-provisioner** (`dns.vps1.ocoron.com`, port 18014). The `fabrik domain` CLI covers `check` / `buy` / `provision` / `ready` / `zones` against Namecheap + Cloudflare + SSL + CDN + WAF + analytics. Full service contract: [docs/reference/service-contracts/site-provisioner.md](../reference/service-contracts/site-provisioner.md).

The 4-layer security model wraps every deployed service:

1. **iptables DOCKER-USER** drops all external Docker traffic except ports 80 / 443 / 6001 / 6002. Enforced via `/etc/systemd/system/iptables-docker-user.service` on the VPS.
2. **Authelia** forward-auth (2FA) protects admin dashboards (`n8n`, `Netdata`, `Backrest`, `Apprise`); `^/api/` bypass for Coolify and Grafana; GlitchTip is on full-bypass (uses django-allauth app-layer TOTP). **Authelia exits on SIGHUP** — config changes require `docker restart <authelia-container>`. Procedure: [30-ops.md § Authelia SSO](../../.windsurf/rules/core/30-ops.md).
3. **`X-Internal-Token`** (via `internal_auth.py` + shared `SERVICE_INTERNAL_SECRET_KEY` in `/opt/fabrik/.env`, same value pushed to Coolify env for every deployed service) for all API-to-API calls. Validation is constant-time (`hmac.compare_digest`). Exceptions: `file-api` uses Supabase Bearer JWT (user auth, different pattern); `site-provisioner` uses Traefik IP allowlist.
4. **Traefik** routes public sites (`ocoron.com`, `status.vps1.ocoron.com`) without auth.

Single-image Coolify Applications get a container name with a timestamp suffix that changes per redeploy. To keep Gatus and inter-service URLs stable, install a stable alias on the `coolify` network: (a) add to compose `networks.coolify.aliases`, (b) live-apply with `docker network disconnect coolify <uuid-name>` then `docker network connect --alias <stable> --alias <uuid-name> coolify <uuid-name>`, (c) register in `scripts/vps_apply_limits.sh` `apply_alias` section (reboot persistence). Currently registered: `browserless`, `gotenberg`, `meilisearch`, `glitchtip-web`. Procedure + canonical pair list: [docs/reference/coolify-stable-aliases.md](../reference/coolify-stable-aliases.md).

## 11. Observability fires

The moment the container is up:

- **Gatus** (`status.vps1.ocoron.com`) probes `/health` (memory storage, ~30 endpoints). 3 consecutive failures → push notification via Apprise → Telegram.
- **Prometheus** (internal `:9090`) scrapes `/metrics` (Authelia-bypassed by global `*.vps1.ocoron.com → /health` rule, which also covers `/metrics` per service config).
- **Alertmanager** (internal `:9093`) routes alerts. **10 rules** in `configs/prometheus/rules/alerts.yml`:

  | Alert | Severity | Threshold | For |
  |---|---|---|---|
  | ContainerDown | critical | not seen >2min | 2m |
  | ContainerHighCPU | warning | >80% | 5m |
  | ContainerHighMemory | warning | >85% of container's own limit | 5m |
  | ContainerMemoryHighOfHost | warning | >15% of VPS total RAM (catches containers without a limit) | 10m |
  | ContainerOOMKilled | critical | any OOM in 5m | 0m |
  | ContainerRestarting | critical | >3 in 15m | 0m |
  | HostHighCPU | warning | >85% | 10m |
  | HostHighMemory | critical | >90% | 5m |
  | HostDiskFull | critical | >85% | 5m |
  | ServiceUnhealthy | critical | target down | 2m |

  Routing: `Prometheus → Alertmanager → Telegram (native telegram_configs)`. ARO Brain (LLM alert triage) is planned but not yet deployed.
- **Loki** (internal `:3100`) ingests logs via **Promtail**. High-cardinality fields (`request_id`, `user_id`, `client_ip`) must be embedded in the JSON payload, not used as stream labels.
- **Grafana** (`monitor.vps1.ocoron.com`) renders Prometheus + Loki dashboards. Provisioning bind-mounted from `configs/grafana/provisioning/`.
- **GlitchTip** (`errors.vps1.ocoron.com`) auto-captures unhandled exceptions; the scaffolded `glitchtip_init.py` is no-op until `GLITCHTIP_DSN` is set per service via [scripts/provision_glitchtip_project.sh](../../scripts/provision_glitchtip_project.sh). Discipline: do NOT also `logger.exception()` for unhandled errors — that duplicates the traceback into Loki.
- **Netdata** (`netdata.vps1.ocoron.com`) shows real-time host metrics (CPU / RAM / disk / network) — dashboard only, no paging.
- **Authelia 2FA codes** go to `/config/notification.txt` on the Authelia container (SMTP via SES port 465 was disabled after it failed).

## 12. Operate, iterate, learn

- New friction → append to [AFCL.md](../../AFCL.md) (silicon ceilings, agent limitations, surprising behavior).
- New "aha" → append to [docs/LESSONS_LEARNT.md](../LESSONS_LEARNT.md) (name the target rule pack).
- New feature → record in [docs/FEATURES.md](../FEATURES.md).
- Future idea → [docs/STRATEGIC_BACKLOG.md](../STRATEGIC_BACKLOG.md) (Now / Later / Context).
- Pricing or GTM call → [docs/BUSINESS_MODEL.md](../BUSINESS_MODEL.md).
- Recurring symptom → [docs/TROUBLESHOOTING.md](../TROUBLESHOOTING.md) (Symptom / Cause / Fix).
- Container resource limits → [scripts/vps_apply_limits.sh](../../scripts/vps_apply_limits.sh) (also re-applies stable DNS aliases on VPS boot).
- Backups → Backrest (`backup.vps1.ocoron.com`) → Backblaze B2 (deployed 2026-04-17).

---

## The shape of one full loop

```
external research (ChatGPT / Claude / Gemini)
       ↓
docs/development/plans/00-research.md
       ↓
fabrik scaffold <name> --type <type>
       ↓  /opt/<name>/ tree + specs/services/<name>.yaml (shape: block)
       ↓  API scaffolds also emit: internal_auth.py, metrics.py, /metrics,
       ↓                          glitchtip_init.py, structured logger
       ↓
Traycer reads AGENTS.md
       ↓  → 6 pre-flight checks (PORTS, duplicates, microservices, amd64, design-system, vendor-docs)
       ↓  → 12 planning constraints
       ↓  → injects rule-packs into prompt (default + feature overlays, ≤40 lines)
       ↓  → emits tickets (Scope / AC / Final Gate / Lessons Learnt)
       ↓
You pick a coder:  Claude Code (CLAUDE.md) | Cascade (.windsurfrules) | Kilo CLI (AGENTS-compact.md)
       ↓
Coder loads bootstrap + scope-relevant packs from .windsurf/rules/
       ↓
IMPLEMENT (strict Scope; no hardcoded localhost / secrets; one test for risk path)
       ↓
DOC SYNC MATRIX (CHANGELOG mandatory; .env.example / INDEX / PORTS / README etc. per the table)
       ↓
GATE: scripts/final_gate.py  (--lean | <none=full> | --systemic)  → iterate to status:"success"
       ↓
LESSONS LEARNT (`none` | docs/LESSONS_LEARNT.md entry)
       ↓
Gate auto-stages (git add only). Coder STOPS.
       ↓
YOU:  git commit  →  git push  →  fabrik redeploy   (Coolify pulls from GitHub remote, not local /opt/)
       ↓
Coolify deploys via Docker Compose on the `coolify` network
       ↓
Traefik routes → Authelia (admin) / X-Internal-Token (API) / open (public)
       ↓
Gatus probes /health · Prometheus scrapes /metrics · Loki ingests logs · GlitchTip catches errors
       ↓
Alertmanager → Telegram on threshold breach (10 rules)
       ↓
Owner reviews AFCL / LESSONS_LEARNT / BUSINESS_MODEL  →  next ticket
```

---

## Verification anchors

Every claim in this document is checkable. The grep / file commands below validate each section's facts; if a claim drifts, you'll see it.

| Claim | Verify with |
|---|---|
| 21 rule packs in `.windsurf/rules/` | `ls /opt/fabrik/.windsurf/rules/ \| wc -l` |
| 11 scaffold types | `grep -E 'shape.kind' /opt/fabrik/templates/*/defaults.yaml \| wc -l` |
| Pack registry matches actual files | `awk '/^### Pack Registry/,/^### Project Type/' /opt/fabrik/AGENTS.md \| grep -c '^\| \`'` |
| `kilo_dispatch.py` injection caps (40 / 6) | `grep -E 'MAX_RULE_LINES\|MAX_LINES_PER_PACK' /opt/fabrik/scripts/kilo_dispatch.py` |
| `final_gate.py` flags (`--lean`, `--systemic`, `--json`) | `grep -nE '^\s+"--(lean\|systemic\|json)"' /opt/fabrik/scripts/final_gate.py` |
| `fabrik` CLI subcommands (scaffold / deploy / apply / redeploy / domain / new) | `grep -roE 'fabrik (scaffold\|deploy\|apply\|redeploy\|domain\|new)' /opt/fabrik/src/fabrik/ \| sort -u` |
| 10 Prometheus alerts in `alerts.yml` | `grep -cE '^\s+- alert:' /opt/fabrik/configs/prometheus/rules/alerts.yml` |
| 4 currently-registered Coolify stable aliases | `grep -E '^apply_alias ' /opt/fabrik/scripts/vps_apply_limits.sh \| wc -l` |
| 6 pre-flight items in AGENTS.md | `awk '/^## 🛑 MANDATORY/,/^## Planning Constraints/' /opt/fabrik/AGENTS.md \| grep -cE '^[0-9]+\. \*\*'` |
| 12 planning constraints in AGENTS.md | `awk '/^## Planning Constraints/,/^---$/' /opt/fabrik/AGENTS.md \| grep -cE '^[0-9]+\. \*\*'` |
| 0 packs left with `activation: always_on` | `grep -l 'activation: always_on' /opt/fabrik/.windsurf/rules/*.md \| wc -l` |
| `CROSS_CUTTING_REQUIREMENTS.md` is gone | `test -e /opt/fabrik/.windsurf/rules/CROSS_CUTTING_REQUIREMENTS.md && echo PRESENT \|\| echo absent` |
| Coolify pulls from GitHub, not `/opt/` | Read [.windsurf/rules/core/30-ops.md § Redeploying Git-Sourced Apps](../../.windsurf/rules/core/30-ops.md) |
| Authelia exits on SIGHUP | Read [.windsurf/rules/core/30-ops.md § Authelia SSO](../../.windsurf/rules/core/30-ops.md) |
| Scaffold-emitted modules per API scaffold | Read [AGENTS.md § What every API scaffold emits automatically](../../AGENTS.md) |

If any of these checks return a number that doesn't match what this document claims, update this document.
