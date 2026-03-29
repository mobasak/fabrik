# AGENTS.md — Fabrik Operating Manual (Traycer Only)

**Last Updated:** 2026-03-26
**Read by:** Traycer only
**Coding agents:** Read `AGENTS-compact.md` via `opencode.json`

> Traycer is the planning authority. It creates plans, specs, epics, tickets.
> Coding agents (Kilo CLI) execute plans — they read `AGENTS-compact.md` only.

---

## Context Overview

### Owner & Working Style

- **Solo developer** — Özgür Başak, 46, Turkish electronics engineer & entrepreneur, biohacker
- **Capacity:** ~50 focused hours/week
- **Budget:** Limited — prefer free/cheap tools, maximize ROI
- **Philosophy:** Fast but good. Ship fast, iterate, automate. No over-engineering.

### Technical Capability

**AI-Augmented Systems Architect & Technical Orchestrator**

- **Infrastructure Background:** Senior-level expertise in enterprise networking (CCNA), Windows Server administration (MCITP), and complex B2B systems integration (PACS/DICOM/HL7).
- **Execution Style:** A "Zero-to-One" builder who thrives on creating automated, self-healing systems. Prioritizes "Boring Technology" and stable architectures that require low maintenance.
- **AI-Native Workflow:** Operates as a solo technical founder, using AI (Traycer, Cascade, Kilo CLI) as senior engineering team to handle implementation, boilerplate, and syntax while driving architectural vision and logic.
- **Bias for Action:** Adheres to a "Fast but Good" philosophy—shipping MVPs quickly to create "forcing functions" and avoid research-driven stagnation.
- **Domain Agnostic:** Highly resourceful at sourcing, vetting, and implementing new tools (Node.js, Python, Next.js) to bridge gaps in the stack, focusing on orchestration rather than just coding.

- **Full profile:** `docs/owner_ozgur_basak.md`

### Development Environment

- **Dev machine:** WSL (Ubuntu 24.04) on Windows
- **IDE:** Windsurf (Cascade AI agents for interactive work)
- **Coding agents:** Windsurf Cascade (manual/interactive) · Kilo CLI (Phased YOLO / Smart YOLO) · Local LLM agents
- **Preferred execution:** Phased YOLO or Smart YOLO (`/execute`)
- **VPS:** ARM64 (aarch64) Ubuntu at 172.93.160.197 — all builds must be ARM-compatible
- **Deployment:** Coolify on VPS (Docker Compose) — `fabrik apply` automates DNS + Coolify + monitoring
- **Database:** PostgreSQL on VPS (default) · Supabase (when managed auth/realtime/pgvector needed)
- **Reverse proxy:** Traefik (managed by Coolify) — HTTPS/SSL via Let's Encrypt
- **Domains:** `*.vps1.ocoron.com` — managed by dns-manager (supports Namecheap, Cloudflare, auto-purchase)
- **Monitoring:** Uptime Kuma · Netdata · Grafana + Prometheus + Loki

### Local LLM Agents

| Agent | Hardware | Memory Usage | Speed | Stability |
|-------|----------|--------------|-------|-----------|
| fabrik-coder | hybrid-cpu | ~19GB (8GB VRAM + 11GB RAM) | Moderate (~15-25 tok/s) | Stable |
| fabrik-reviewer | cpu | ~42GB RAM | Slow (~8-12 tok/s) | High memory pressure ⚠️ |
| fabrik-fixer | hybrid-gpu | ~9GB (8GB VRAM + 1GB RAM) | Fast (~40-60 tok/s) | Stable |
| fabrik-docs | gpu | ~5GB VRAM | Instant (~80-100 tok/s) | Rock solid |

### Project Scaffold

Owner creates project folder and runs `fabrik scaffold <name> --type <type>` before starting with Traycer. This creates:
- Full folder structure
- `.venv` (Python virtual environment)
- Dockerfile, compose.yaml, .env.example
- Plan templates (docs/development/plans/)
- SaaS skeleton (if using saas-skeleton type)

- Prebuilt containers: `docs/reference/prebuilt-app-containers.md` — check before writing custom code

### Tech Stack Defaults

| Layer | Default | Deviate When |
|-------|---------|-------------|
| Backend | Python + FastAPI + Uvicorn | Node.js for web-adjacent workers |
| Frontend | Next.js 14 + TypeScript + Tailwind | — always use this |
| Database | PostgreSQL 16 (VPS, Coolify-managed) | Supabase for managed auth/realtime/pgvector |
| Background jobs | PostgreSQL jobs table + worker | Redis queue for high throughput |
| AI/LLM | Kilo CLI free tiers → OpenAI/Anthropic APIs | Local Ollama for offline/free |
| **Local LLM** | Ollama (localhost:11434) | See `docs/reference/LOCAL_LLM_INFRASTRUCTURE.md` |
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
| Local LLM | `docs/reference/LOCAL_LLM_INFRASTRUCTURE.md` | Ollama setup, model assignments per agent role |
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

## Authority Model & Orchestration

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

### Mode Selection (Manual)

Owner selects mode manually in Traycer UI:

| Task | Mode |
|------|------|
| Single focused task / bug fix | Plan |
| Complex feature, multiple steps | Phases |
| Safe refactoring | Traycer Refactoring Workflow |
| Feature with specs + tickets | Epic |

### YOLO Activation

In Epic mode, when owner types `/execute`, Traycer can use Smart YOLO mode and run parallel agents where available.

Full workflow: `docs/traycer/traycer-yolo-workflow.md`

### Prompt Templates (Pass to Spawned Agents)

| Agent | Mode | Template |
|-------|------|----------|
| Coder | Plan | `Coder-for-Plan-Mode.md` |
| Coder | Phased/Epic | `Coder-for-Phased-Epic-Modes.md` |
| Fixer | After Review | `Fix-After-Review.md` |
| Fixer | After Verification | `Fix-After-Verification.md` |

### What Traycer Does

Traycer is the **planning authority**. It does NOT execute code. It:
1. Creates plans, specs, epics, tickets
2. Assigns tickets to phases
3. Spawns Kilo CLI agents for implementation
4. Decides when to run gates (review, documentator, final_gate)
5. Verifies implementation against spec
6. Commits when all gates pass

### Stage 0: Discovery & Definition (Desired Workflow)

> **Note:** These stages describe the desired workflow. Use natural language to guide Traycer through these stages.

| Stage | Goal | Output |
|-------|------|--------|
| 0.1: Idea | Extract pain points, user personas, solution direction | `specs/<project>/00-idea.md` |
| 0.2: Scope | Define P0 "Must Haves" and explicit "Out of Scope" | `specs/<project>/01-scope.md` |
| 0.3: Spec | Create the Single Source of Truth (SSoT) | `specs/<project>/02-spec.md` |

**Templates available:** `templates/spec-pipeline/` contains prompt templates for each stage.

**After spec is complete:** Convert `02-spec.md` into Phased YOLO or Epic plan.

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

## Mandatory Workflow (Traycer Creates Plans With This Structure)

**UNDERSTAND → PLAN → EXECUTE → SELF_REVIEW → FIX_ISSUES → STAGE**

### Plan Structure (Traycer Creates)
Traycer's plan should force the called agent (CODER or FIXER) to:
| Step | Who | Action |
|------|-----|--------|
| 1 — Understand | Agent | First understand the need/task requirements |
| 2 — Task List | Agent | Create task list by itself |
| 3 — Execute | Agent | Make the execution |
| 4 — Self-Review | Agent | Review its own work |
| 5 — Fix Issues | Agent | Fix the found issues |
| 6 — Stage | Agent | Stage changes (no commit) |

### End-of-Phase Gates (Traycer decides when)
| Gate | Command | Purpose |
|------|---------|--------|
| Kilo Review | `git add -A && python scripts/kilo_code_review.py staged` | Find issues |
| Fix findings | Fixer agent | Fix BLOCKER/MAJOR/MINOR |
| Documentator | `python scripts/kilo_docs_enforcer.py --auto-generate` | Update docs |
| Final Gate | `python scripts/final_gate.py` | Validate all |

### Phase Completion
| Step | Who | Action |
|------|-----|--------|
| 6 — Verify | Traycer | SPEC compliance confirmed |
| 6.1 — Fix Issues | Fixer | If Traycer finds issues, spawn Fixer with issues list |
| 6.2 — Re-verify | Traycer | Continue until all issues resolved |
| 7 — Commit | Traycer | 4 blockers only: large-files, merge-conflict, private-key, secrets |

**Traycer commits. Coding agents never commit.**
**Gates run at END OF PHASE, not every ticket — Traycer decides when.**

---

## Project Scaffold (What `fabrik scaffold` Creates)

Every project at `/opt/<project>/` gets this structure:

```
/opt/<project>/
├── .venv/                    # Python virtual environment (pre-created)
├── .droid/                   # Kilo/Traycer runtime files
│   ├── review-context/       # Review context files
│   └── traycer-reports/      # Traycer report files
├── config/                   # Configuration files
├── data/                     # Data files
├── db/                       # Database schema (schema.sql)
├── docs/
│   ├── archive/              # Archived docs
│   ├── development/
│   │   └── plans/            # Development plans (YYYY-MM-DD-plan-<n>.md)
│   ├── guides/               # User guides
│   ├── operations/           # Operations docs
│   └── reference/            # Reference docs
├── logs/                     # Log files
├── output/                   # Output files
├── scripts/                  # Project scripts
├── src/                      # Source code (Python projects)
├── tests/                    # Test files
├── .cache/                   # Cache directory
├── .tmp/                     # Temp files (never use /tmp/)
├── .env.example              # Environment variable reference
├── CHANGELOG.md              # Change log (required entry per change)
├── compose.yaml              # Docker Compose config
├── Dockerfile                # Docker build file
├── INDEX.md                  # Project index
├── Makefile                  # Build commands
├── pyproject.toml            # Python project config
└── README.md                 # Project readme
```

### Scaffold Types

| Type | Template | Created Structure |
|------|----------|------------------|
| `python-api` | `templates/scaffold/` | FastAPI + Uvicorn + Docker |
| `saas-skeleton` | `templates/saas-skeleton/` | Next.js 14 + TypeScript + Tailwind |
| `node-api` | `templates/node-api/` | Node.js API + Docker |
| `file-api` | `templates/file-api/` | File operations API |
| `file-worker` | `templates/file-worker/` | Background file worker |
| `wordpress` | `templates/wordpress/` | WordPress + WP-CLI |
| `docusaurus` | `templates/docusaurus/` | Documentation site |
| `chrome-extension` | `templates/chrome-extension/` | Chrome extension |
| `mobile-app` | `templates/mobile-app/` | React Native app |
| `desktop-app` | `templates/desktop-app/` | Electron app |

### Key Scaffold Files

| File | Purpose |
|------|---------|
| `project.yaml` | Project metadata (auto-created, editable) |
| `.env.example` | Environment variable reference |
| `compose.yaml` | Docker Compose config (Coolify-compatible) |
| `db/schema.sql` | Database schema (source of truth) |
| `AGENTS-compact.md` | Symlink to Fabrik's compact agent rules |

---

## Environment Constraints (Traycer Enforces)

- **Runtime:** WSL (Ubuntu). Linux paths and commands only. Never Windows tooling.
- **Scaffold:** Fixed structure — do not reorganize, flatten, or add top-level directories.
- **pip:** Never bare `pip install`. Always `/opt/<project>/.venv/bin/pip install`
- **Env vars:** Never hardcode. Always `os.getenv('KEY', 'default')`
- **Base images:** `python:<current-stable>-slim-bookworm` / `node:<current-LTS>-bookworm-slim`. Never Alpine. Check actual Dockerfiles in `templates/scaffold/docker/` for pinned versions.
- **Deployment:** Linux VPS via Coolify. ARM-compatible builds required.
- **Ports:** Python 8000–8099 / Frontend 3000–3099. Register new ports in `PORTS.md`.
- **Conflicts:** If task contradicts project state — stop and return to Traycer. Do not silently overwrite.

---

## Security & Quality Gates (Checks Traycer Includes in Plans)

### Kilo Review (Check to Include in Plans)
Traycer includes this check in implementation plans:
```bash
git add -A && python scripts/kilo_code_review.py staged --plan "task description" --output json
```
**⚠️ NEVER `git add` only your files** — other tools (final_gate, sync_projects, scaffold) may have modified files too. Review ALL changes or risk missing issues.
Automatic: risk detection → model selection → variant selection → session isolation.
**Reviewer AI never fixes** — findings only. CODER fixes all severities (BLOCKER, MAJOR, MINOR).
Max 5 iterations before escalating to Traycer.

### Documentator (Check to Include in Plans)
Traycer includes this check in implementation plans:
```bash
python scripts/kilo_docs_enforcer.py --auto-generate
git add CHANGELOG.md docs/reference/*.md docs/CONFIGURATION.md .env.example
python scripts/kilo_docs_enforcer.py --enforce
```
Auto-generates: CHANGELOG entries, API docs, env var docs. Uses cheap agents from `kilo_agents.db`.

### Final Gate (Check to Include in Plans)
Traycer includes this check in implementation plans:
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

## Sensitive Data Protection

Before modifying any credentials file (`.env`, `*.key`, `*.pem`, `secrets/`, `.ssh/`):

```bash
cp <file> <file>.backup.$(date +%Y%m%d-%H%M%S)
# Verify backup exists before proceeding
```

**Forbidden without dry-run:** Destructive scripts on production data.
**Forbidden without full diff approval:** Any credentials change.

---

## Code Patterns (Traycer Enforces)

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

## Documentation Rules (Traycer Enforces)

- **CHANGELOG.md:** Entry required for every code change. Format: `### Added/Changed/Fixed — Title (YYYY-MM-DD)`
- **README.md features table:** Every new feature added with ✅/🚧/❌ status
- **New `.md` files:** Blocked outside allowlist. Allowed: root files, scaffold docs, `docs/development/plans/YYYY-MM-DD-plan-<n>.md`, `docs/archive/**`
- **AUTO-GENERATED blocks:** Never edit manually. Run `python scripts/sync_projects.py` (Fabrik project only)
- **`.env.example`:** Authoritative variable reference. `docs/CONFIGURATION.md` is a guide only — no variable tables there.

---

## Coder Directives (Traycer Passes to Coder Agents)

These directives are included in Coder prompt templates:

1. **D1 — Completeness:** Complete the full implementation — do not stub, skip, or leave TODOs.
2. **D2 — No Hallucination:** Do not hallucinate APIs, methods, or library features.
3. **D3 — Verified Imports:** Only use functions and imports confirmed to exist.
4. **D4 — Production Quality:** Write production-ready code — not prototype quality.
5. **D5 — Task Focus:** Focus exclusively on the task. Do not refactor unrelated code.
6. **D6 — Self-Review:** Review own output for correctness before reporting completion.

---

## Reviewer Directives (Traycer Passes to Reviewer Agents)

Reviewers report findings only — they do NOT fix code.

1. **R1:** Identify bugs, security issues, performance problems. Cite line numbers.
2. **R2:** Evaluate correctness and safety, not just describe code.
3. **R3:** Flag silent failure modes.
4. **R4:** Prioritize: BLOCKER / MAJOR / MINOR.

---

## Fixer Directives (Traycer Passes to Fixer Agents)

Fixers fix reported issues only — no refactoring, no new features.

1. **F1:** Fix ONLY reported issues.
2. **F2:** State assumptions explicitly if ambiguous.
3. **F3:** Minimal edits — follow existing code style.
4. **F4:** Final pass: check off-by-one errors, null paths, missing imports.

---

## Infrastructure & Deployment

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
