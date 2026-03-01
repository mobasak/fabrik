# Fabrik

**Last Updated:** 2026-02-26

**AI-Driven Development Platform with Spec-to-Production Automation**

Fabrik is not just a deployment tool—it's a **complete AI-assisted software development platform** that combines:
- **Traycer**: IDE-integrated spec-driven planning with Epic mode workflows
- **9-Step Agile Workflow**: AI planning → coding → enforcement → review → verification → deployment
- **Kilo Code Review**: Iterative AI code reviewer with fix-and-revalidate loops
- **Final Gate**: 25 automated enforcement checks (2,230 lines of validation logic)
- **Deployment Orchestration**: Saga pattern with automatic rollback and state tracking
- **Full-Stack Templates**: SaaS skeleton, WordPress automation, API scaffolds

**13,565 lines of production code** across orchestration, provisioning, WordPress automation, and enforcement.

---

## Overview

### What Fabrik Actually Is

Fabrik is a **development methodology as code**—not just infrastructure automation. It enforces:

1. **Spec-Driven Development** via Traycer (Windsurf IDE extension)
2. **Mandatory Quality Gates** via Final Gate (deterministic checks) + Kilo (AI review)
3. **Convention Enforcement** via 19 enforcement scripts covering security, structure, documentation
4. **AI-Guided Workflows** via Fabrik skills, Traycer phases, Kilo sessions
5. **Production Deployment** via Coolify orchestration, DNS automation, health monitoring

### The Complete Development Flow

```
┌──────────────────┐
│  Traycer Plan    │  1. Spec-driven planning (Epic mode: 8-command workflow)
│  (IDE Extension) │  2. Phase breakdown with context preservation
└────────┬─────────┘  3. Hands off to coding agents
         │
         ▼
┌──────────────────┐
│  Windsurf/Cascade│  4. Code implementation (Gemini 3.1 Pro, escalate to Sonnet 4.5)
│  or Kilo CLI     │  5. Auto-invoked skills (10+ Fabrik conventions)
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  Self-Review     │  6. Coding AI reviews own work (spec compliance, edge cases, docs)
│  (MANDATORY)     │  7. Structured report: requirements, env vars, DB, issues
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  Final Gate      │  8. Pre-Kilo: Auto-fix format, lint, static analysis (saves tokens)
│  (Pre-Kilo)      │  9. Repo consistency: 25 checks across security/docs/structure
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  Kilo Review     │  10. Diff-scoped AI review (SPEC, SECURITY, CONFIG, EDGE, DOCS)
│  (Iterative)     │  11. Coder fixes ALL issues (BLOCKER, MAJOR, MINOR)
└────────┬─────────┘  12. Re-review until verdict=PASS (max 5 iterations)
         │
         ▼
┌──────────────────┐
│  Final Gate      │  13. Post-Kilo: Verify fixes didn't break deterministic rules
│  (Post-Kilo)     │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  Traycer Verify  │  14. Traycer's built-in verifier validates against spec
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  Sync & Commit   │  15. Final Gate --sync: Extensions + backup
│                  │  16. Pre-commit: 4 absolute blockers only
└────────┬─────────┘  17. Git commit succeeds
         │
         ▼
┌──────────────────┐
│  Deploy Pipeline │  18. Coolify orchestration (saga pattern)
│  (Orchestrator)  │  19. DNS + SSL + Health checks
└──────────────────┘  20. Automatic rollback on failure

---

## Architecture

### System Components

| Layer | Component | Lines of Code | Purpose |
|-------|-----------|---------------|----------|
| **Planning** | Traycer (IDE Extension) | External | Spec-driven Epic workflows, phase management, YOLO automation |
| **Coding** | Windsurf Cascade / Kilo CLI | External | AI coding agents (Cascade for IDE, Kilo for CLI/review) |
| **Enforcement** | Final Gate | 688 | Deterministic quality checks (25 checks, 3 phases) |
| **Enforcement** | 19 Enforcement Scripts | 2,230 | Security, structure, docs, conventions, health checks |
| **Review** | Kilo CLI Integration | 2,996 | Iterative AI code review with fix loops |
| **Orchestration** | DeploymentOrchestrator | 147 | State machine: validate → provision → deploy → verify → rollback |
| **Provisioning** | SiteProvisioner | 782 | Saga pattern: domain → DNS → Coolify → health (15 granular states) |
| **WordPress** | WordPress Automation | 2,500+ | Theme, pages, SEO, analytics, multilingual, content generation |
| **CLI** | Fabrik CLI | 828 | Commands: new, plan, apply, status, templates, scaffold |
| **Drivers** | External Integrations | 3,000+ | Coolify, Cloudflare, Namecheap, Supabase, R2, WordPress API |
| **Templates** | 18 Project Templates | - | SaaS skeleton, APIs, WordPress, workers, Chrome extensions |

**Total Production Code:** 13,565 lines

### AI Integration Architecture

```
┌─────────────────────┐
│   Traycer IDE Ext   │  • Epic Mode: 8-command Agile workflow
│   (WSL ~/.traycer)  │  • Phases: Multi-step context preservation
└──────────┬──────────┘  • Plan/Review/Spec modes
           │
           │ factory_submit.py / factory_wait.py
           ▼
┌─────────────────────┐
│  Coding Agents      │  • Windsurf Cascade (Gemini 3.1 Pro High Thinking)
│  (Gemini/Sonnet)    │  • Kilo CLI (Claude Opus 4.6, GPT-5.1 Codex, Gemini 3.1 Pro)
└──────────┬──────────┘  • Auto-invoked Fabrik skills (10+ conventions)
           │
           ▼
┌─────────────────────┐
│  Final Gate         │  • Phase 1: Auto-fix (whitespace, EOF, ruff-format, ruff --fix)
│  (Deterministic)    │  • Phase 2: Static (ruff, mypy, bandit, semgrep, vulture)
└──────────┬──────────┘  • Phase 3: Consistency (25 checks, 2,230 lines)
           │
           ▼
┌─────────────────────┐
│  Kilo Review        │  • Diff-scoped review (not full codebase)
│  (AI Reasoning)     │  • Categories: SPEC, SECURITY, CONFIG, EDGE, DOCS
└──────────┬──────────┘  • Iterative fix loop (max 5 iterations)
           │
           ▼
┌─────────────────────┐
│  Traycer Verifier   │  • Validates against original spec
│  (Spec Compliance)  │  • Returns findings to fix
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Deployment         │  • Saga orchestration (15 states)
│  Orchestrator       │  • Automatic rollback on failure
└─────────────────────┘  • Health verification

---

## Key Features

### 1. Traycer-Driven Development (IDE Extension)

**Traycer runs as a Windsurf IDE extension**, connecting to WSL via `~/.traycer/cli-agents/`.

**Three workflow modes:**

| Mode | Use Case | Workflow |
|------|----------|----------|
| **Plan** | Single-PR task | Generate detailed implementation plan → Execute → Verify |
| **Phases** | Multi-step project | Break into phases → Context preservation → Execute sequentially |
| **Epic** | Feature with specs | 8-command Agile workflow: `/trigger_workflow` → `/epic-brief` → `/core-flows` → `/prd-validation` → `/tech-plan` → `/architecture-validation` → `/ticket-breakdown` → `/implementation-validation` |

**Context Preservation:**
- SQLite database at `~/.traycer/app-assets/app-assets.db` stores ALL task history
- File mappings, decisions, rationale carried forward across phases
- No re-analyzing architecture when executing later phases

**YOLO Mode (Full Automation):**
```
Regular YOLO (Phases):  Fixed config → All phases run automatically
Smart YOLO (Epic):      Orchestrator evolves Epic based on learnings
```

**Integration with Fabrik:**
- Submits plans via `factory_submit.py` (async job submission)
- Waits for completion via `factory_wait.py`
- Uses custom Kilo templates at `~/.traycer/prompt-templates/Kilo*.md`
- Integrates 9-step workflow into handoffs

---

### 2. Mandatory Quality Gates (Token-Optimized)

**Why this workflow saves money:**
- Deterministic checks BEFORE LLM review (Final Gate catches ~80% of issues for FREE)
- LLM tokens used only for reasoning problems (not lint/syntax)
- Typical cost: Review ~$0.03-0.40 vs Auto-fix ~$1-2

**Final Gate (688 lines, 25 checks):**

**Phase 1: Auto-Fix Formatting**
```bash
✓ Trim trailing whitespace
✓ Fix EOF newlines
✓ ruff-format (code formatting)
✓ ruff --fix (auto-fixable lint)
```

**Phase 2: Static Analysis**
```bash
✓ ruff (Python linter)
✓ mypy (type checking - src/fabrik/ only for speed)
✓ bandit (security scanner)
✓ semgrep (SAST - best effort, skips if not authenticated)
✓ check yaml/json (syntax validation)
✓ sqlfluff-lint (SQL style)
✓ vulture (dead code detection - REQUIRED)
```

**Phase 3: Repo Consistency (2,230 lines across 19 scripts)**

| Check | Script | Severity | Purpose |
|-------|--------|----------|----------|
| Hardcoded localhost | `check_env_vars.py` | ERROR | No `localhost` or `127.0.0.1` in code |
| Hardcoded secrets | `check_secrets.py` | ERROR | No API keys, tokens in code |
| Env var contract | `check_env_contract.py` | ERROR/WARN | `.env.example` ↔ `compose.yaml` ↔ docs sync |
| Health endpoint | `check_health.py` | WARN | `/health` tests dependencies + test file exists |
| Docker standards | `check_docker.py` | ERROR/WARN | No Alpine, HEALTHCHECK required, port consistency |
| Port registration | `check_ports.py` | WARN | Port in PORTS.md |
| Watchdog exists | `check_watchdog.py` | WARN | Service has monitoring script |
| Doc structure | `check_structure.py` | ERROR/WARN | `.md` files in correct locations |
| Changelog updated | `check_changelog.py` | ERROR | CHANGELOG entry for code changes (smart: >10 lines) |
| Module docs | `check_docs.py` | WARN | New `src/` modules have reference docs |
| Plan naming | `check_plans.py` | ERROR/WARN | `YYYY-MM-DD-plan-<name>.md` format |
| Rule file size | `check_rule_size.py` | ERROR | `.windsurf/rules/*.md` < 12KB (AI context limits) |

**Pre-commit (Step 8 - Only 4 Absolute Blockers):**
```yaml
- check-added-large-files  # No files >500KB
- check-merge-conflict      # No <<<< markers
- detect-private-key        # No SSH keys
- forbid-secrets            # No .env, .pem, .key files
```

---

### 3. Kilo Code Review (Iterative AI Review)

**2,996 lines of iterative review logic** with fix-and-revalidate loops.

**How it works:**
```bash
# Initial review: pass task/plan for SPEC verification
python scripts/kilo_code_review.py review src/api.py \
  --plan .droid/review-context/task.md \
  --review-agent ask \
  --output json

# Subsequent reviews: maintain context
python scripts/kilo_code_review.py review src/api.py \
  --session continue \
  --output json
```

**Review Categories:**
- **SPEC**: Meets requirements from plan/spec?
- **SECURITY**: Vulnerabilities, auth issues, injection risks
- **CONFIG**: Env vars, hardcoded values, deployment issues
- **EDGE**: Error handling, null checks, edge cases
- **DOCS**: Code comments, docstrings, README updates

**Iterative Loop:**
1. Kilo reviews diff (not full codebase - saves tokens)
2. Returns JSON: `{"verdict": "FAIL", "issues": [{severity: "MAJOR", ...}]}`
3. **Coder fixes ALL issues** (not Kilo auto-fix - cheaper)
4. Re-review with `--session continue` (maintains context)
5. Repeat until `verdict=PASS` (max 5 iterations)

**Variant escalation:**
- Start with `variant=high` (fast, cheap)
- Final verification uses `variant=max` (thorough, expensive)
- Doc-only files: max 2 iterations (lighter review)

---

### 4. WordPress Full-Stack Automation (2,500+ lines)

**Complete WordPress site from YAML spec** - not just deployment, but content generation.

**Spec Example:**
```yaml
schema_version: 1
preset: company
site:
  domain: example.com
  name: example-com
brand:
  name: "Acme Corp"
  tagline:
    en_US: "Strategic Consulting for Growing Businesses"
  colors:
    primary: "#1e3a5f"
services:  # Auto-generates pages
  - slug: investment-incentives
    name:
      en_US: "Investment Incentives"
    icon: landmark
```

**What Gets Automated:**

| Component | Module | Lines | Features |
|-----------|--------|-------|----------|
| **Theme Customization** | `theme.py` | 300+ | Colors, fonts, logos, custom CSS |
| **Page Generation** | `page_generator.py`, `pages.py` | 500+ | From service specs, hero sections, CTAs |
| **Menu Structure** | `menus.py` | 200+ | Header, footer, automatic hierarchy |
| **Contact Forms** | `forms.py` | 250+ | Contact, quote requests, SMTP config |
| **SEO** | `seo.py` | 200+ | Meta tags, Open Graph, sitemap, robots.txt |
| **Analytics** | `analytics.py` | 150+ | GA4, Google Tag Manager injection |
| **Legal Pages** | `legal.py` | 200+ | Privacy Policy, Terms, GDPR compliance |
| **Multilingual** | Content rendering | 300+ | Multiple languages from single spec |
| **Media Management** | `media.py` | 150+ | Upload, organize, featured images |
| **Deployment** | `deployer.py` | 573 | Orchestrates all modules end-to-end |

**Presets:**
- `company` - Corporate site (services, team, about)
- `landing` - Marketing landing page
- `saas` - SaaS product site
- `ecommerce` - Online store
- `content` - Blog/magazine

---

### 5. Deployment Orchestration (Saga Pattern)

**SiteProvisioner (782 lines) - 15 Granular States:**

```python
class ProvisionState(str, Enum):
    INIT = "INIT"

    # Step 0: Domain Registration
    STEP0_CF_ZONE_CREATED = "..."
    STEP0_DOMAIN_REGISTER_REQUESTED = "..."
    STEP0_DOMAIN_REGISTERED = "..."

    # Step 1: DNS Setup
    STEP1_DNS_RECORDS_UPSERTED = "..."
    STEP1_CF_STATUS_SNAPSHOT = "..."
    GATE_WAIT_CF_ACTIVE = "..."  # Wait for Cloudflare activation

    # Step 2: WordPress Deployment
    STEP2_COOLIFY_CREATE_REQUESTED = "..."
    STEP2_COOLIFY_CREATED = "..."
    STEP2_COOLIFY_DEPLOY_REQUESTED = "..."
    STEP2_COOLIFY_DEPLOY_RUNNING = "..."
    STEP2_COOLIFY_DEPLOY_SUCCEEDED = "..."
    STEP2_HTTP_VERIFIED = "..."

    # Terminal states
    COMPLETE = "COMPLETE"
    FAILED_RETRYABLE = "FAILED_RETRYABLE"
    FAILED_TERMINAL = "FAILED_TERMINAL"
```

**Crash Recovery:**
- State persisted to disk after each transition
- Resumable from any state
- Retry tracking per step
- GitOps fallback if API deploy fails

**Automatic Rollback:**
- Deletes created DNS records
- Stops deployed containers
- Cleans up created resources
- Detailed error tracking

---

### 6. Fabrik Skills (Convention Enforcement)

**10+ Fabrik skills** define project conventions and patterns.

**Location:** `.factory/skills/` and `~/.factory/skills/`

| Skill | Triggers | What It Does |
|-------|----------|-------------|
| `fabrik-saas-scaffold` | "SaaS", "web app", "dashboard" | Copies SaaS skeleton template, customizes config |
| `fabrik-scaffold` | "new project", "create service" | Full project structure with ALL conventions |
| `fabrik-docker` | "dockerfile", "compose" | ARM64 Debian images, HEALTHCHECK, Traefik labels |
| `fabrik-health-endpoint` | "health", "healthcheck" | `/health` that tests DB, not fake "ok" |
| `fabrik-config` | "config", "environment" | `os.getenv()` patterns, `.env.example` template |
| `fabrik-api-endpoint` | "endpoint", "route", "API" | FastAPI + Pydantic patterns |
| `fabrik-watchdog` | "watchdog", "monitor" | Service monitoring scripts with auto-restart |
| `fabrik-postgres` | "database", "postgres" | PostgreSQL + pgvector setup |

**Enforcement:** Skills are documented in `.factory/skills/*.md` and define Fabrik's coding conventions.

---

## Production Infrastructure

| Service | Location | Purpose |
| **VPS** | Hetzner LA (172.93.160.197) | ARM64 server running all services |
| **Coolify** | http://172.93.160.197:8000 | Container orchestration + deployment |
| **Traefik** | VPS (ports 80/443) | Reverse proxy + automatic HTTPS |
| **PostgreSQL** | postgres-main container | Shared database |
| **Redis** | redis-main container | Shared cache |
| **dns-manager** | https://dns.vps1.ocoron.com | DNS automation (Namecheap + Cloudflare) |
| **Uptime Kuma** | https://status.vps1.ocoron.com | Status monitoring |
| **Duplicati** | https://backup.vps1.ocoron.com | Encrypted backups to B2 |
| **File API** | https://files-api.vps1.ocoron.com | File uploads (R2 storage) |

---

## Available Templates (18 Total)

### Production-Ready Templates

Create production-ready services instantly:

| Template | Stack | Use Case | Features |
|----------|-------|----------|----------|
| `python-api` | FastAPI + Uvicorn | REST APIs, microservices | Health checks, CORS, structured logging |
| `node-api` | Express.js | Node.js APIs | Fast, lightweight services |
| `next-tailwind` | Next.js 14 + Tailwind | Full-stack web apps | SSR, API routes, modern UI |
| `file-api` | Node.js + Cloudflare R2 | File upload services | Presigned URLs, direct browser uploads |
| `file-worker` | Python + R2 | Background processing | OCR, transcription, async jobs |
| `wordpress` | WordPress + MySQL | Content sites, blogs | Automated theme, plugins, content |
| `saas-skeleton` | Next.js + Supabase + Stripe | Multi-tenant SaaS | Auth, billing, dashboard, job workflow, SSE streaming |
| `chrome-extension` | Manifest V3 + React | Browser extensions | Popup, background, content scripts |
| `desktop-app` | Electron + React | Desktop applications | Cross-platform native apps |
| `mobile-app` | React Native | Mobile apps | iOS + Android from one codebase |
| `docusaurus` | Docusaurus | Documentation sites | Versioning, search, i18n |

**SaaS Skeleton Features** (Most comprehensive template):
- Marketing site (hero, pricing, features pages)
- App dashboard with job workflow UI
- SSE streaming for AI chat integration
- Supabase auth + Row-level security
- Stripe billing integration
- Admin panel
- ChatUI component for AI features

---

## Quick Start

### For AI-Assisted Development (Recommended)

**Install Traycer** (Windsurf IDE extension):
1. Install Windsurf IDE
2. Install Traycer extension from marketplace
3. Configure CLI agents: `~/.traycer/cli-agents/Factory AI.sh` → point to `/opt/fabrik`
4. Create Epic: `/trigger_workflow` in Traycer

### Manual Installation

### Prerequisites

- VPS with SSH access (Hetzner, DigitalOcean, etc.)
- Domain you control
- Coolify installed on VPS (or use Fabrik to deploy Coolify)

### Installation

```bash
# Clone and install
cd /opt/fabrik
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

### Configuration

```bash
# Copy environment template
cp .env.example .env

# Edit credentials (see docs/QUICKSTART.md for details)
nano .env
```

**Required:**
- `VPS_HOST`, `VPS_USER` - SSH access to your VPS
- `COOLIFY_API_URL`, `COOLIFY_API_TOKEN` - Coolify API
- `NAMECHEAP_API_URL` or `CLOUDFLARE_API_TOKEN` - DNS provider

### Create Your First Project

```bash
# Option 1: Full project structure (recommended for development)
fabrik scaffold my-api -d "User authentication API"
# Creates complete structure with docs, tests, Docker, pre-commit hooks
# See: docs/reference/fabrik-scaffold-specs.md

# Option 2: Deployment spec only (for existing projects)
fabrik new my-api --template python-api --domain api.example.com

# Preview deployment plan
fabrik plan specs/my-api.yaml

# Deploy to production
fabrik apply specs/my-api.yaml

# Check status
fabrik status specs/my-api.yaml

# Test endpoint
curl https://api.example.com/health
```

**Result:** API live with HTTPS, DNS configured, health monitoring active.

### Running the 9-Step Workflow Manually

```bash
# After coding (Step 2)
cd /opt/my-api

# Step 2.5: Self-Review (MANDATORY)
echo "SELF-REVIEW COMPLETE:"
echo "✓ All spec requirements implemented"
echo "✓ Edge cases handled: [list]"
echo "✓ Env vars documented: [list]"
echo "✓ DB changes documented: N/A"
echo "⚠ Potential issues: None identified"

# Step 3: Pre-Kilo Final Gate
python /opt/fabrik/scripts/final_gate.py
# → Auto-fixes format, runs lint, checks conventions

# Step 4: Kilo Review (if Final Gate passes)
python /opt/fabrik/scripts/kilo_code_review.py review src/ \
  --plan .droid/review-context/task.md \
  --output json
# → Read JSON, fix ALL issues, re-review with --session continue

# Step 5: Post-Kilo Final Gate
python /opt/fabrik/scripts/final_gate.py

# Step 7: Sync
python /opt/fabrik/scripts/final_gate.py --sync

# Step 8: Commit (pre-commit runs 4 blockers only)
git commit -m "feat: user authentication"

# Step 9: Deploy
fabrik apply specs/my-api.yaml
```

---

## Key Features

### 1. Spec-Driven Everything

Define infrastructure as code with simple YAML:

```yaml
# specs/translator-api.yaml
name: translator-api
template: python-api
domain: translator.vps1.ocoron.com

environment:
  DATABASE_URL: ${DATABASE_URL:?}  # Required from .env
  DEEPL_API_KEY: ${DEEPL_API_KEY:?}
  LOG_LEVEL: ${LOG_LEVEL:-info}

resources:
  cpu: 1
  memory: 512M

healthcheck:
  path: /health
  interval: 30s
```

### 2. Deployment Orchestration

**State machine with automatic rollback:**

```
VALIDATING → PROVISIONING → DEPLOYING → VERIFYING → COMPLETE
     ↓             ↓             ↓            ↓
   FAILED ← ROLLING_BACK ← ROLLING_BACK ← ROLLING_BACK
```

**What gets tracked:**
- Created DNS records → deleted on rollback
- Deployed containers → stopped on rollback
- Uploaded files → cleaned up on rollback
- State checkpoints → resumable deployments

### 3. WordPress Automation

Full WordPress site deployment from spec:

```yaml
# specs/sites/ocoron.com.yaml
schema_version: 1
preset: company

site:
  domain: ocoron.com
  name: ocoron-com

brand:
  name: "Ocoron"
  tagline:
    en_US: "Strategic Consulting for Growing Businesses"
  colors:
    primary: "#1e3a5f"

services:  # Generates pages automatically
  - slug: investment-incentives
    name:
      en_US: "Investment Incentives"
    icon: landmark
```

**Automated:**
- Theme customization (colors, fonts, logos)
- Page generation from service specs
- Menu structure
- Contact forms
- SEO meta tags
- Analytics (GA4)
- Legal pages (Privacy Policy, Terms)
- Multilingual support

### 4. Cloud Integration

**Supabase + Cloudflare R2:**
- Multi-tenant database (PostgreSQL)
- Row-level security
- Real-time subscriptions
- S3-compatible object storage
- Presigned upload URLs (bypass server)
- Background job queue

### 5. Project Scaffolding

Create new projects with best practices built-in:

```bash
fabrik scaffold my-service

# Creates:
# ├── INDEX.md              # Master navigation
# ├── README.md             # Project overview
# ├── CHANGELOG.md          # Release tracking
# ├── AGENTS.md             # AI agent briefing (symlinked)
# ├── Dockerfile            # Production container
# ├── compose.yaml          # Docker Compose
# ├── pyproject.toml        # Python deps (uv)
# ├── src/                  # Source code
# ├── tests/                # Test suite
# ├── scripts/              # Automation
# ├── docs/                 # Documentation
# │   ├── QUICKSTART.md
# │   ├── CONFIGURATION.md
# │   └── guides/
# └── .github/workflows/    # CI/CD
```

---

## Why Fabrik?

### vs Manual Development

| Aspect | Manual | With Fabrik |
|--------|--------|-------------|
| **Code Review** | Manual PR reviews, inconsistent | Automated Kilo review (5 categories, iterative loops) |
| **Conventions** | Varies by developer | 19 enforcement scripts, 25 automated checks |
| **Deployment** | 2-3 hours per service | 5 minutes (`fabrik apply`) |
| **Quality Gates** | Hope pre-commit catches issues | 3-phase Final Gate + Kilo + Traycer verification |
| **Documentation** | Often stale or missing | Auto-generated, enforced by Final Gate |

### vs Kubernetes

| Aspect | Kubernetes | Fabrik |
|--------|------------|--------|
| **Complexity** | 100+ YAML files, steep learning curve | 1 YAML file per service |
| **Cost** | $50-200/month managed cluster | $10/month VPS, unlimited services |
| **Setup Time** | Days to weeks | 30 minutes |
| **AI Integration** | None built-in | Traycer + Kilo + skills = full AI workflow |
| **Enforcement** | Manual helm chart reviews | Automated (2,230 lines of checks) |

### vs Platform-as-a-Service (Heroku, Vercel, Railway)

| Aspect | PaaS | Fabrik |
|--------|------|--------|
| **Cost** | $20-100/month per service | $10/month total |
| **Vendor Lock-in** | Locked to platform | Self-hosted, portable |
| **AI Workflow** | None | Traycer + 9-step workflow |
| **Customization** | Platform constraints | Full Docker control |

### vs Terraform/Ansible

| Aspect | Terraform/Ansible | Fabrik |
|--------|------------------|--------|
| **Scope** | Infrastructure only | End-to-end (infra + app + monitoring + AI workflow) |
| **Application Deployment** | Separate tool needed | Built-in orchestration |
| **AI Integration** | None | Traycer planning + Kilo review |
| **WordPress** | Manual setup | Full automation (2,500+ lines) |

**Fabrik's unique value:** Not just deployment - it's a complete AI-assisted development methodology with enforcement.

---

## Tech Stack

### Development Tools

| Layer | Technology | Purpose |
|-------|------------|----------|
| **Planning** | Traycer (Windsurf Extension) | Spec-driven Epic workflows, YOLO automation |
| **Coding** | Cascade (Gemini 3.1 Pro High Thinking) | Primary implementation agent |
| **Coding** | Kilo CLI (Claude Opus 4.6, GPT-5.1 Codex, Gemini 3.1 Pro) | Terminal-based coding agent, code review |
| **Review** | Kilo CLI | Diff-scoped AI review with iterative loops |
| **Enforcement** | Final Gate + 19 scripts | 25 checks (format, lint, security, conventions) |
| **Python Tooling** | uv, ruff, mypy, bandit | Fast package manager, linter, types, security |

### Infrastructure

| Layer | Technology |
|-------|------------|
| **CLI** | Python 3.12, Click |
| **Orchestration** | State machines, saga pattern (782 lines) |
| **Deployment** | Coolify API, Docker Compose |
| **DNS** | dns-manager service (Namecheap + Cloudflare) |
| **Reverse Proxy** | Traefik (automatic HTTPS) |
| **Database** | PostgreSQL 16, Supabase |
| **Cache** | Redis |
| **Storage** | Cloudflare R2 (S3-compatible) |
| **Monitoring** | Uptime Kuma, custom health checks |
| **Backups** | Duplicati → Backblaze B2 |
| **WordPress** | WP-CLI, REST API automation (2,500+ lines) |

---

## Documentation

### Core Docs

- **[AGENTS.md](AGENTS.md)** - **Complete AI agent briefing** (896 lines covering 9-step workflow, Traycer integration, enforcement)
- **[INDEX.md](INDEX.md)** - Master documentation map
- **[Quick Start](docs/QUICKSTART.md)** - Get running in 5 minutes
- **[FAQ](docs/FAQ.md)** - Comprehensive Q&A (500+ lines)

### Guides

- **[Configuration](docs/CONFIGURATION.md)** - Credentials, architecture, troubleshooting
- **[Deployment](docs/DEPLOYMENT.md)** - Deployment strategies, DNS, SSL
- **[Troubleshooting](docs/TROUBLESHOOTING.md)** - Debug guides
- **[Development Workflow](docs/guides/DEVELOPMENT_WORKFLOW.md)** - How Traycer fits into 9-step workflow

### Reference

- **[Windsurf Rules](.windsurf/rules/)** - 6 rule files (critical, Python, TypeScript, ops, docs, review)
- **[Enforcement Scripts](scripts/enforcement/)** - 19 scripts, 2,230 lines
- **[Traycer Integration](docs/traycer/README.md)** - Complete workflow details

---

## Project Status

| Component | Status | Lines of Code |
|-----------|--------|---------------|
| **Final Gate** | ✅ Production | 688 |
| **Enforcement Scripts** | ✅ Production | 2,230 (19 scripts) |
| **Kilo Integration** | ✅ Production | 2,996 |
| **Deployment Orchestrator** | ✅ Production | 147 |
| **Site Provisioner** | ✅ Production | 782 (15 states) |
| **WordPress Automation** | 🚧 90% Complete | 2,500+ |
| **Fabrik CLI** | ✅ Production | 828 |
| **Drivers** | ✅ Production | 3,000+ |
| **Templates** | ✅ Production | 18 templates |

**Total:** 13,565+ lines of production code

**Current Focus:** WordPress v2 spec implementation (multi-site, advanced SEO)

See [tasks.md](tasks.md) for detailed roadmap.

---

## Contributing

Fabrik is proprietary but used internally for:
- Client SaaS product development (with AI-assisted workflow)
- WordPress site automation at scale
- Internal microservices deployment
- Enforcing development standards across teams
fabrik apply specs/file-worker.yaml  # Background processor
# → OCR, transcription, thumbnail generation
```

---

## Why Fabrik?

**vs Manual Deployment:**
- Manual: 2-3 hours per service (DNS, Docker, SSL, monitoring)
- Fabrik: 5 minutes (`fabrik apply`)

**vs Platform-as-a-Service (Heroku, Vercel, Railway):**
- PaaS: $20-100/month per service, vendor lock-in
- Fabrik: $10/month VPS, unlimited services, full control

**vs Kubernetes:**
- K8s: Complex (100+ YAML files), expensive ($50+ for managed cluster)
- Fabrik: Simple (1 YAML file), cheap (single VPS), production-ready

**vs Terraform/Ansible:**
- Terraform: Infrastructure only, no application deployment
- Fabrik: End-to-end (infra + app + monitoring + backups)

---

## Development

### Run Fabrik Locally

```bash
cd /opt/fabrik
source .venv/bin/activate
PYTHONPATH=src python -m fabrik.main --help
```

### Run Tests

```bash
pytest tests/ -v
```

### Add New Template

```bash
# 1. Create template directory
mkdir templates/my-template

# 2. Add Dockerfile, compose.yaml, defaults.yaml
# 3. Register in templates/

# 4. Test
fabrik new test-service --template my-template
```

---

## Contributing

Fabrik is proprietary but used internally for:
- Client infrastructure deployment
- SaaS product hosting
- WordPress site automation
- Internal tool deployment

---

## License

Proprietary — All rights reserved.

---

## Support

- **Documentation Issues**: Create GitHub issue
- **Deployment Help**: See [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)
- **Feature Requests**: See [tasks.md](tasks.md) for roadmap
