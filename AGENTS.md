# AGENTS.md — Fabrik Operating Manual

**Last Updated:** 2026-03-24
**Read by:** Traycer (full file) | Coding agents (via prompt templates — see Quick Navigation)
**Referenced by:** Prompt templates via `opencode.json` rules loading

> Traycer is the planning authority. Coding agents execute, never plan.
> Project scope lives in `README.md`. This file covers environment, constraints, and workflow rules only.

---

## Quick Navigation

| You are | Read | Skip |
|---------|------|------|
| **Traycer** | Full file | — |
| **Coder** | `[CODER]` + `[ALL AGENTS]` sections | `[TRAYCER ONLY]`, `[REVIEWER]`, `[FIXER]` |
| **Reviewer** | `[REVIEWER]` + `[ALL AGENTS]` sections | `[TRAYCER ONLY]`, `[CODER]`, `[FIXER]` |
| **Fixer** | `[FIXER]` + `[ALL AGENTS]` sections | `[TRAYCER ONLY]`, `[CODER]`, `[REVIEWER]` |
| **Documentator** | `[ALL AGENTS]` sections + Step 4 | `[TRAYCER ONLY]`, `[CODER]`, `[REVIEWER]`, `[FIXER]` |

**Coding agents receive their execution instructions via prompt templates, not this file.**

---

## [TRAYCER ONLY] Situational Awareness

> Read this section before planning any work. Full context: who the owner is, what exists, what constraints apply.

### Owner & Working Style

- **Solo developer** — Özgür Başak, Turkish electronics engineer & entrepreneur
- **Capacity:** ~50 focused hours/week
- **Budget:** Limited — prefer free/cheap tools, maximize ROI
- **Philosophy:** Fast but good. Ship fast, iterate, automate. No over-engineering.
- **Technical capability:** Limited Python, fully capable with AI assistance. Comfortable with advanced architectures when stable and low-maintenance.
- **Full profile:** `docs/owner_ozgur_basak.md`

### Development Environment

- **Dev machine:** WSL (Ubuntu 24.04) on Windows
- **IDE:** Windsurf (Cascade AI agents for interactive work)
- **Coding agents:** Windsurf Cascade (manual/interactive) · Kilo CLI (Phased YOLO / Smart YOLO)
- **Preferred execution:** Phased YOLO or Smart YOLO (`/execute`)
- **VPS:** ARM64 (aarch64) Ubuntu at 172.93.160.197 — all builds must be ARM-compatible
- **Deployment:** Coolify on VPS (Docker Compose) — `fabrik apply` automates DNS + Coolify + monitoring
- **Database:** PostgreSQL on VPS (default) · Supabase (when managed auth/realtime/pgvector needed)
- **Reverse proxy:** Traefik (managed by Coolify) — HTTPS/SSL via Let's Encrypt
- **Domains:** `*.vps1.ocoron.com` — managed by dns-manager (supports Namecheap, Cloudflare, auto-purchase)
- **Monitoring:** Uptime Kuma · Netdata · Grafana + Prometheus + Loki

### Project Scaffold

Every new project starts from `/opt/<project>/` with pre-configured: folder structure, `.venv`, Dockerfile, `compose.yaml`, `.env.example`, plan templates (`templates/docs/`), and SaaS skeleton (`templates/saas-skeleton/`).

- Prebuilt containers: `docs/reference/prebuilt-app-containers.md` — check before writing custom code

### Tech Stack Defaults

| Layer | Default | Deviate When |
|-------|---------|-------------|
| Backend | Python + FastAPI + Uvicorn | Node.js for web-adjacent workers |
| Frontend | Next.js 14 + TypeScript + Tailwind | — always use this |
| Database | PostgreSQL 16 (VPS, Coolify-managed) | Supabase for managed auth/realtime/pgvector |
| Background jobs | PostgreSQL jobs table + worker | Redis queue for high throughput |
| AI/LLM | Kilo CLI free tiers → OpenAI/Anthropic APIs | Self-hosted only if justified |
| Base images | `python:<current-stable>-slim-bookworm`, `node:<current-LTS>-bookworm-slim` | Never Alpine |
| PDF | Gotenberg (self-hosted) | WeasyPrint for simple cases |
| Search | MeiliSearch (self-hosted) | PostgreSQL FTS for simple cases |
| Notifications | Apprise (self-hosted) | Direct API for single-channel |
| Object storage | MinIO (self-hosted, S3-compatible) | Backblaze B2 for cold storage |

### Infrastructure Services (Deployed on VPS)

| Service | URL | Purpose |
|---------|-----|---------|
| Coolify | coolify.vps1.ocoron.com | Deployment control plane |
| PostgreSQL | (internal) | Shared database |
| Redis | (internal) | Shared cache |
| Uptime Kuma | status.vps1.ocoron.com | Uptime monitoring |
| Netdata | netdata.vps1.ocoron.com | Server metrics |
| Grafana | monitor.vps1.ocoron.com | Dashboards |
| Duplicati | backup.vps1.ocoron.com | PostgreSQL backup to B2 |
| Browserless | browser.vps1.ocoron.com | Headless Chrome farm |
| Gotenberg | pdf.vps1.ocoron.com | PDF generation API |
| MinIO | s3.vps1.ocoron.com | Object storage |
| MeiliSearch | search.vps1.ocoron.com | Full-text search |
| Apprise | notify.vps1.ocoron.com | Multi-channel notifications |
| n8n | auto.vps1.ocoron.com | Workflow automation |

### Fabrik Microservices (Custom-Built, on VPS)

| Service | Port | Purpose |
|---------|------|---------|
| Translator | 8000 | DeepL + Azure translation |
| Captcha | 8000 | Anti-Captcha solving |
| Proxy | 8000 | Webshare.io proxy management |
| DNS Manager | 8001 | Namecheap DNS API |
| File API | 8004 | File operations |
| Image Broker | 8010 | AI image generation (FLUX) |
| Email Gateway | 3000 | Resend + SES email sending |

### Active Projects

Full auto-generated project list (39 projects) in `docs/BUSINESS_MODEL.md` under `<!-- AUTO-GENERATED:PROJECTS -->`.
Run `python scripts/sync_projects.py` to refresh (Fabrik project only - child projects don't have this script).

### Reference Documents

| Document | Path | Use When |
|----------|------|----------|
| Project Portfolio | `docs/BUSINESS_MODEL.md` | Full project list with statuses |
| AI Taxonomy | `docs/reference/AI_TAXONOMY.md` | Selecting AI tools/models for a feature |
| Stack Decision Guide | `docs/reference/technology-stack-decision-guide.md` | Choosing tech stack for new project |
| Prebuilt Containers | `docs/reference/prebuilt-app-containers.md` | Infrastructure services, ready-made Docker solutions |
| Stack Overview | `docs/reference/stack.md` | Frozen architecture decisions, tools inventory |
| Database Strategy | `docs/reference/DATABASE_STRATEGY.md` | Database, migration, vector storage decisions |
| Owner Profile | `docs/owner_ozgur_basak.md` | Owner background, goals, AI instructions |
| Architecture | `docs/reference/architecture.md` | Fabrik CLI internals and deployment flow |
| Port Allocations | `PORTS.md` | Assigning ports to new services |
| Traycer Workflows | `docs/traycer/README.md` | Traycer integration, YOLO modes |
| SaaS UI Patterns | `docs/reference/Modern GUI Approaches for a Lean, Fast, Effective, Low-Confusion SaaS Web App.md` | Planning SaaS frontend UI |
| Chrome Extension UI | `docs/reference/Modern GUI Approaches for Chrome Extensionst.md` | Planning Chrome extensions |
| Mobile UI | `docs/reference/Modern Mobile GUI Approaches for Android and iOS.md` | Planning mobile apps (Android/iOS) |
| ~~Project Registry~~ | `docs/reference/project-registry.md` | ⚠️ DEPRECATED — use `BUSINESS_MODEL.md` |

### Planning Constraints

Before creating any plan, verify:

1. **Solo developer** — no team handoff, one person executes everything
2. **ARM64 VPS** — all Docker images must support `linux/arm64`
3. **Budget-conscious** — prefer free Kilo models, free-tier APIs, self-hosted over SaaS
4. **Existing services** — check if a Fabrik microservice already solves the need before building
5. **Prebuilt containers** — check `prebuilt-app-containers.md` before writing custom code
6. **Port conflicts** — check `PORTS.md` before assigning ports
7. **Coolify deployment** — all services deploy as Docker Compose apps via Coolify
8. **No Alpine** — use `-slim-bookworm` base images only
9. **Module dependencies** — if a project needs an incomplete Fabrik module, plan module completion first. Check module status in `docs/BUSINESS_MODEL.md` before planning dependent work
10. **DNS** — dns-manager handles Namecheap + Cloudflare + domain purchasing automatically

---

## [TRAYCER ONLY] Authority Model & Orchestration

**Traycer is the planning authority.** All other agents execute, never plan.

| Role | Tool | Responsibility |
|------|------|----------------|
| Planner / Orchestrator | Traycer | Plans, phases, verification, commits |
| Coder | Kilo CLI / Cascade | Implements spec — current phase only |
| Reviewer | Kilo CLI | Reviews staged code, reports findings |
| Fixer | Kilo CLI | Fixes review and verification findings |

### Plan Quality Gate — Do NOT hand off to Coder without:
- [ ] `specs/<project>/02-spec.md` exists and is complete (Stage 0 output)
- [ ] Functional spec (exact behavior, not goals)
- [ ] Edge cases (boundaries, null paths, failure states)
- [ ] Required env vars (new or changed)
- [ ] DB changes (schema, migrations)
- [ ] Docs impact (CHANGELOG, README features table)
- [ ] Out of scope (explicitly stated)

### Mode Selection

| Task | Mode |
|------|------|
| Single focused task / bug fix | Plan |
| Complex feature, multiple steps | Phases |
| Safe refactoring | Traycer Refactoring Workflow |
| Feature with specs + tickets | Epic |

### YOLO Activation

```bash
/yolo smart "task description"     # Single-phase
/yolo phased "task description"    # Multi-phase
```

Full workflow: `docs/traycer/traycer-yolo-workflow.md`

### Prompt Templates (Pass to Spawned Agents)

| Agent | Mode | Template |
|-------|------|----------|
| Coder | Plan | `Execute by Coder.md` |
| Coder | Plan (skip-plan) | `Direct Execute by Coder.md` |
| Coder | Epic | `Execute Epic.md` |
| Coder | YOLO | `Phased YOLO Execute by Coder.md` |
| Reviewer | Manual | `Reviewer.md` |
| Fixer | Manual | `Fix.md` |
| Fixer | YOLO (Review tab) | `Phased YOLO Review.md` |
| Fixer | YOLO (Verification tab) | `Phased YOLO FixafterVerification.md` |

### Traycer Execution Rules
1. Carry forward file mappings, decisions, and rationale across phases
2. Follow steps exactly in order — do NOT redesign or change scope mid-plan
3. One step at a time — complete current step before moving to next
4. After each step: show Evidence + Gate result
5. If a Gate fails → STOP and re-plan

### Stage 0: Discovery & Definition (Pre-Planning)

**Traycer MUST NOT generate an implementation plan until a project has passed through the Discovery Pipeline.**

| Stage | Command | Traycer Output | Goal |
|-------|---------|----------------|------|
| 0.1: Idea | `/discover <idea>` | `specs/<project>/00-idea.md` | Extract pain points, user personas, solution direction |
| 0.2: Scope | `/scope <project>` | `specs/<project>/01-scope.md` | Define P0 "Must Haves" and explicit "Out of Scope" |
| 0.3: Spec | `/spec <project>` | `specs/<project>/02-spec.md` | Create the Single Source of Truth (SSoT) |

**How it works:**

1. **Discovery Mode:** Use `templates/spec-pipeline/00-idea-prompt.md` to interview the owner. Output `specs/<project>/00-idea.md`.
2. **Boundary Mode:** Use `templates/spec-pipeline/01-scope-prompt.md` to lock MVP boundaries. Respect the owner's ~50 focused hours/week capacity. Output `specs/<project>/01-scope.md`.
3. **SSoT Mode:** Use `templates/spec-pipeline/02-spec-prompt.md` to define technical architecture (Data Model, API, One-Test Rule). Auto-inject Fabrik Stack Defaults into the Stack Profile. Output `specs/<project>/02-spec.md`.
4. **Execution Mode:** Convert `specs/<project>/02-spec.md` into a `Phased YOLO` or `Epic` plan.

**Enforcement:** Traycer will reject implementation tasks if `specs/<project>/02-spec.md` is missing or incomplete.

**Stack Auto-Injection:** During Stage 0.3, Traycer injects these Fabrik defaults into the spec's Stack Profile:

| Component | Default | Override When |
|-----------|---------|---------------|
| Frontend | Next.js 14 + TypeScript + Tailwind | — |
| Backend | Python + FastAPI + Uvicorn | Node.js for web-adjacent workers |
| Database | PostgreSQL 16 (Coolify-managed) | Supabase for managed auth/realtime/pgvector |
| Base images | `python:<current-stable>-slim-bookworm` / `node:<current-LTS>-bookworm-slim` | Never Alpine |
| Platform | `linux/arm64` | Never x86-only |
| Hosting | Coolify on ARM64 VPS | — |
| Domains | `*.vps1.ocoron.com` | — |

---

## [ALL AGENTS] Mandatory Workflow

**PLAN → IMPLEMENT → SELF_REVIEW → KILO_REVIEW → DOCUMENTATOR → FINAL_GATE → VERIFY → COMMIT**

| Step | Who | Gate |
|------|-----|------|
| 1 — Plan | Traycer | Spec: requirements, edge cases, env vars, DB changes, docs impact |
| 2 — Implement | Coder (mid-tier) / Cascade | Phase scope only |
| 2.5 — Self-review | Coder / Cascade | MANDATORY before Kilo Review |
| 3 — Kilo Review | Reviewer (report-only) | `python scripts/kilo_code_review.py staged --plan "..."` — findings only, never fixes |
| 3b — Fix review findings | Coder / Cascade | CODER fixes all Kilo review findings (BLOCKER, MAJOR, MINOR) |
| **4 — Documentator** | **Documentator (cheap)** | **`python scripts/kilo_docs_enforcer.py --auto-generate` → `--enforce`** |
| 5 — Final Gate | Coder / Cascade | `python scripts/final_gate.py` → all PASS (code + docs) |
| 6 — Verify | Traycer | SPEC compliance confirmed |
| 7 — Commit | Traycer | 4 blockers only: large-files, merge-conflict, private-key, secrets |

**Conditional FIXER loop** (triggered only when Step 6 VERIFY fails):

| Workflow | Who Fixes | Trigger |
|----------|-----------|--------|
| Kilo CLI (YOLO) | Fixer (expensive, separate agent) | Receives Traycer verification comments |
| Cascade (interactive) | Cascade itself (fixer role) | User relays Traycer verification comments in chat |

After fix → Traycer re-verifies. Loop until PASS, then proceed to Step 7.

**Traycer commits. Coding agents never commit.**
**Skipping any step = workflow must stop and the step re-run.**

---

## [ALL AGENTS] Environment Constraints

- **Runtime:** WSL (Ubuntu). Linux paths and commands only. Never Windows tooling.
- **Scaffold:** Fixed structure — do not reorganize, flatten, or add top-level directories.
- **pip:** Never bare `pip install`. Always `/opt/<project>/.venv/bin/pip install`
- **Env vars:** Never hardcode. Always `os.getenv('KEY', 'default')`
- **Base images:** `python:<current-stable>-slim-bookworm` / `node:<current-LTS>-bookworm-slim`. Never Alpine. Check actual Dockerfiles in `templates/scaffold/docker/` for pinned versions.
- **Deployment:** Linux VPS via Coolify. ARM-compatible builds required.
- **Ports:** Python 8000–8099 / Frontend 3000–3099. Register new ports in `PORTS.md`.
- **Conflicts:** If task contradicts project state — stop and return to Traycer. Do not silently overwrite.

---

## [ALL AGENTS] Security & Quality Gates

### Kilo Review (Step 3 — Report-Only)
```bash
git add -A                          # CRITICAL: stage ALL uncommitted files, not just yours
git diff --staged --name-only       # Verify staged matches intent
python scripts/kilo_code_review.py staged --plan "task description" --output json
```
**⚠️ NEVER `git add` only your files** — other tools (final_gate, sync_projects, scaffold) may have modified files too. Review ALL changes or risk missing issues.
Automatic: risk detection → model selection → variant selection → session isolation.
**Reviewer AI never fixes** — findings only. CODER fixes all severities (BLOCKER, MAJOR, MINOR).
Max 5 iterations before escalating to Traycer.

### Documentator (Step 4)
```bash
python scripts/kilo_docs_enforcer.py --auto-generate
git add CHANGELOG.md docs/reference/*.md docs/CONFIGURATION.md .env.example
python scripts/kilo_docs_enforcer.py --enforce
```
Auto-generates: CHANGELOG entries, API docs, env var docs. Uses cheap agents from `kilo_agents.db`.

### Final Gate (Step 5)
```bash
python scripts/final_gate.py
```
Runs: auto-fix formatting → static analysis (ruff, mypy, bandit, semgrep) → repo consistency.
**Runs once after DOCUMENTATOR** — validates both code quality AND documentation.
Fix all failures. Re-run until PASS. Do not proceed with failures.

### Enforcement Scripts (`scripts/enforcement/`)

| Script | Checks | Severity |
|--------|--------|----------|
| `check_env_vars.py` | Hardcoded localhost / 127.0.0.1 | ERROR |
| `check_secrets.py` | Hardcoded API keys, tokens | ERROR |
| `check_docker.py` | Alpine base, HEALTHCHECK, port consistency | ERROR |
| `check_changelog.py` | CHANGELOG entry for every code change | ERROR |
| `check_env_contract.py` | .env.example ↔ compose.yaml sync | ERROR |
| `check_health.py` | /health tests real dependencies | WARN |
| `check_structure.py` | MD file placement (anti-sprawl) | ERROR |

---

## [ALL AGENTS] Sensitive Data Protection

Before modifying any credentials file (`.env`, `*.key`, `*.pem`, `secrets/`, `.ssh/`):

```bash
cp <file> <file>.backup.$(date +%Y%m%d-%H%M%S)
# Verify backup exists before proceeding
```

**Forbidden without dry-run:** Destructive scripts on production data.
**Forbidden without full diff approval:** Any credentials change.

---

## [ALL AGENTS] Code Patterns (Authoritative)

### Python / FastAPI
```python
# Config — always function-level, never class/module-level
def get_db_url() -> str:
    return f"postgresql://{os.getenv('DB_HOST','localhost')}:{os.getenv('DB_PORT','5432')}/db"

# Health — always test real dependencies
@app.get("/health")
async def health():
    await db.execute("SELECT 1")
    return {"status": "ok", "db": "connected"}

# Temp files — never /tmp/
TEMP_DIR = Path(__file__).parent.parent / ".tmp"
```

### Docker
```dockerfile
FROM python:<current-stable>-slim-bookworm  # See templates/scaffold/docker/ for pinned version
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/health || exit 1
```

### compose.yaml
```yaml
networks:
  coolify:
    external: true
environment:
  - DB_HOST=postgres-main   # service name, never localhost
```

---

## [ALL AGENTS] Documentation Rules

- **CHANGELOG.md:** Entry required for every code change. Format: `### Added/Changed/Fixed — Title (YYYY-MM-DD)`
- **README.md features table:** Every new feature added with ✅/🚧/❌ status
- **New `.md` files:** Blocked outside allowlist. Allowed: root files, scaffold docs, `docs/development/plans/YYYY-MM-DD-plan-<n>.md`, `docs/archive/**`
- **AUTO-GENERATED blocks:** Never edit manually. Run `python scripts/sync_projects.py` (Fabrik project only)
- **`.env.example`:** Authoritative variable reference. `docs/CONFIGURATION.md` is a guide only — no variable tables there.

---

## [CODER] Implementation Directives

> These directives are enforced. Violating any = workflow failure.

1. **D1 — Completeness:** Complete the full implementation — do not stub, skip, or leave TODOs.
2. **D2 — No Hallucination:** Do not hallucinate APIs, methods, or library features. If you are unsure whether something exists, say so.
3. **D3 — Verified Imports:** Only use functions and imports you can confirm exist in this codebase or the specified library version.
4. **D4 — Production Quality:** Write production-ready code — not prototype or demo quality.
5. **D5 — Task Focus:** Focus exclusively on the task. Do not refactor unrelated code.
6. **D6 — Self-Review:** Before returning, review your own output for correctness, completeness, and consistency.

### Project Scaffold

- SaaS skeleton: `templates/saas-skeleton/` — Next.js 14 + TypeScript + Tailwind (project-local)
- Plan templates: `templates/docs/` — PLAN_TEMPLATE.md, EXECUTION_PLAN_TEMPLATE.md (project-local)
- Check `docs/reference/prebuilt-app-containers.md` before building custom infrastructure code

### Project Layout

- Every project lives at `/opt/<project>/` with pre-created `.venv`, Dockerfile, `compose.yaml`, `.env.example`
- Use the project's `.venv` — never bare `pip install`
- Docker patterns: `python:<current-stable>-slim-bookworm` / `node:<current-LTS>-bookworm-slim` base images, never Alpine. See `templates/scaffold/docker/` for pinned versions

### Windsurf Cascade Users

- **Terminal selection:** Never use "legacy terminal" in Windsurf IDE — it hangs on certain commands. If Windsurf shows "Using legacy terminal", cancel and re-run in a proper terminal.
- **Check before create:** Always verify a file exists (`ls`, `find`, `read_file`) before creating it with `write_to_file`. Attempting to create a file that already exists = stop and acknowledge error.

---

## [REVIEWER] Review Directives

> Reviewers report findings only. They do NOT fix code — that is the Fixer's job.

1. **R1:** Review this code thoroughly: identify bugs, security issues, performance problems, and violations of best practices. Be specific — cite line numbers or function names.
2. **R2:** Do not just describe what the code does — evaluate whether it does it correctly and safely.
3. **R3:** Flag any silent failure modes — paths where the code proceeds without error but produces wrong results.
4. **R4:** Prioritize findings: BLOCKER / MAJOR / MINOR.

### Output Format

- Group findings by severity (BLOCKER → MAJOR → MINOR)
- Cite file path, line number, and function/symbol name for each finding
- State what's wrong and why it matters — not just "this looks suspicious"

---

## [FIXER] Fix Directives

> Fixers fix reported issues only. No refactoring, no new features, no scope expansion.

1. **F1:** Fix ONLY reported issues — no refactoring, no new features.
2. **F2:** Do not assume — if something is ambiguous, state your assumption explicitly before proceeding.
3. **F3:** Focus exclusively on the task. Do not refactor unrelated code.
4. **F4:** Do a final pass: look for off-by-one errors, null paths, and missing imports.

### Fix Rules

- **Minimal edits** — change only what's needed to resolve the finding. Follow existing code style.
- **All severities** — fix BLOCKER, MAJOR, and MINOR findings. Do not skip MINOR.
- **Re-run gates** — after fixing, re-run `final_gate.py` until PASS. Max 5 iterations before escalating to Traycer.

---

## [TRAYCER ONLY] Infrastructure & Deployment

**Deployment:** `fabrik apply` → Coolify
**Secrets:** Project `.env` (primary)
**ARM check:** `python scripts/container_images.py check-arch <image:tag>` (Fabrik project only - child projects use Docker Hub docs)

### Microservice URLs

| Environment | Pattern |
|-------------|---------|
| WSL dev | `http://localhost:PORT` |
| VPS internal | `http://service-name:PORT` |
| VPS external | `https://service.vps1.ocoron.com` |

### GitHub Actions

| Workflow | Trigger | Purpose |
|----------|---------|---------|
| `ci.yml` | Push / PR | `check_duplicates.py` (jscpd wrapper) + KPI schema validation |
| `docs-check.yml` | Push to main (src/docs/scripts) | Documentation drift detection via `docs_updater.py --check` |

### Quality Gates (Local Scripts)

These run locally during the mandatory workflow (Steps 3-5), not as GitHub Actions.

| Script | Workflow Step | Purpose |
|--------|-------------|---------|
| `scripts/kilo_code_review.py` | Step 3: Kilo Review | AI-powered code review — reviews staged changes, reports BLOCKER/MAJOR/MINOR findings. Multi-model support. |
| `scripts/kilo_docs_enforcer.py` | Step 4: Documentator | AI documentation enforcement — auto-generates CHANGELOG entries, README features. Calls AI documentator agents. |
| `scripts/final_gate.py` | Step 5: Final Gate | Orchestrates 27 enforcement scripts in `scripts/enforcement/`. All must pass before commit. |

### Enforcement Scripts (`scripts/enforcement/`)

Run by `final_gate.py`. Each checks one convention:

| Category | Scripts | What They Enforce |
|----------|---------|-------------------|
| **Docker** | `check_docker.py` | No Alpine, HEALTHCHECK required, ARM64 platform, port consistency |
| **Secrets** | `check_secrets.py` | No hardcoded API keys, passwords, private keys |
| **Config** | `check_env_contract.py`, `check_env_vars.py`, `check_env_updates.py`, `check_env_example.py` | .env.example ↔ compose.yaml ↔ CONFIGURATION.md sync |
| **Health** | `check_health.py` | Health endpoints must test actual dependencies (not fake `{"status": "ok"}`) |
| **Database** | `check_schema_sync.py` | Model changes require schema.sql or migration update |
| **Watchdog** | `check_watchdog.py` | Services with compose.yaml must have `scripts/watchdog*.sh` |
| **Docs** | `check_changelog.py`, `check_docs.py`, `check_doc_sprawl.py`, `check_readme_md.py`, `check_index_md.py` | CHANGELOG updated, no doc sprawl, README/INDEX present |
| **Structure** | `check_structure.py`, `check_ports.py`, `check_deps_sync.py`, `check_configuration_md.py` | Project structure, port registration, dependency sync |
| **Code** | `validate_conventions.py`, `check_opencode_json.py`, `check_plan_quality.py` | Fabrik conventions, Kilo CLI config, plan quality |

### Pre-commit Hooks

Minimal blockers at commit time (`.pre-commit-config.yaml`):

| Hook | Purpose |
|------|---------|
| `check-added-large-files` | Blocks files > 500KB |
| `check-merge-conflict` | Blocks unresolved conflicts |
| `detect-private-key` | Blocks private key files |
| `forbid-secrets` | Blocks `.env`, `.pem`, `.key`, `secrets/` from commit |

### Fabrik Behavior Patterns

These patterns are enforced via `.windsurf/rules/` (for AI agents) and `scripts/enforcement/` (automated):

| Pattern | Rules File | Enforcement Script | CLI Command |
|---------|-----------|-------------------|-------------|
| Project scaffolding | — | — | `fabrik scaffold <name> --type <type>` |
| SaaS scaffolding | `20-typescript.md` | — | `fabrik scaffold <name> --type saas-skeleton` |
| Docker conventions | `30-ops.md` | `check_docker.py` | — |
| Health endpoints | `00-critical.md`, `10-python.md` | `check_health.py` | — |
| Config / env vars | `00-critical.md`, `10-python.md` | `check_env_contract.py` | — |
| API patterns | `10-python.md` | `validate_conventions.py` | — |
| Database / schema | `00-critical.md` | `check_schema_sync.py` | — |
| Watchdog scripts | `30-ops.md` | `check_watchdog.py` | — |
| Documentation | `40-documentation.md` | `check_changelog.py`, `check_docs.py` | `kilo_docs_enforcer.py` |
| Deploy preflight | — | All 27 scripts via `final_gate.py` | — |

### MCP Servers

Config: `opencode.json` (project-level) or `~/.config/kilo/opencode.json` (global)

MCP servers are configured per-project as needed. See [Kilo CLI MCP docs](https://kilo.ai/docs/automate/mcp/using-in-cli) for setup.
