# Fabrik Scaffold Structure

**Last Updated:** 2026-07-20 — `SCAFFOLD_TYPES` (12, incl. `python-api-gpu`), `SPEC_ENABLED_TYPES` (10, incl. `chrome-extension`/`mobile-app`), and the enforcement-dir file count (49) re-verified against `src/fabrik/scaffold.py`, `src/fabrik/spec_generator.py`, and `scripts/enforcement/`. WordPress scaffolding is fully retired from Fabrik — see `/opt/wpf/`. `fabrik new` remains deprecated/hidden (Phase 4k).
**Script:** `@/opt/fabrik/src/fabrik/scaffold.py` (scaffold command)

> Complete reference for the folder and file structure created by `fabrik scaffold`. Sister doc to the broader `FABRIK_SCAFFOLD_WORKFLOW.md` (this file is narrowly scoped to the file tree).

---

## Overview

When you run `fabrik scaffold <project-name> --type python-api`, the following structure is created in `/opt/<project-name>/`:

---

## Complete Scaffold Tree

```
/opt/<project-name>/
├── .windsurf/
│   ├── rules/
│   │   ├── 10-python.md
│   │   ├── 15-api-contracts.md
│   │   ├── 20-typescript.md
│   │   ├── 25-data-postgres.md
│   │   ├── 30-ops.md
│   │   ├── 35-security-auth.md
│   │   ├── 40-documentation.md
│   │   ├── 42-docusaurus.md
│   │   ├── 45-testing-strategy.md
│   │   ├── 50-code-review.md
│   │   ├── 55-observability.md
│   │   ├── 60-saas-ui.md
│   │   ├── saas/                    # 4 SaaS packs
│   │   ├── 65-rag-search.md
│   │   ├── 70-chrome-ext.md
│   │   ├── 75-workers-jobs.md
│   │   ├── 80-mobile.md
│   │   ├── 85-payments-billing.md
│   │   ├── core/                    # 20 shared packs
│   │   ├── 95-multi-tenant-saas.md
│   │   └── ocoron-design-system.md
│   └── workflows/
│       ├── bug-fix.md
│       ├── deploy.md
│       ├── kilo.md
│       ├── kilo-review.md
│       ├── local-coder.md
│       ├── local-docs.md
│       ├── local-fixer.md
│       ├── local-review.md
│       ├── new-feature.md
│       └── review.md
├── .droid/
│   ├── .gitignore
│   ├── review-context/
│   │   └── .gitkeep
│   └── traycer-reports/
│       └── .gitignore
├── .github/                       # CI (python-api / python-api-gpu / file-api only)
│   └── workflows/
│       └── (no ci.yml — CI checks retired fleet-wide 2026-08-29)
├── db/
│   └── schema.sql
├── docs/
│   ├── archive/
│   │   └── README.md
│   ├── development/
│   │   ├── plans/
│   │   └── PLANS.md
│   ├── reference/
│   │   └── windsurf/
│   ├── BUSINESS_MODEL.md
│   ├── CONFIGURATION.md
│   ├── FEATURES.md
│   ├── QUICKSTART.md
│   ├── README.md
│   └── TROUBLESHOOTING.md
├── scripts/
│   ├── enforcement/              # Entire dir copied from Fabrik (49 files, recounted 2026-07-20 via `git ls-files scripts/enforcement/ | wc -l`)
│   ├── ci_local.sh               # local clean-room check runner (python API types)
│   ├── docs_updater.py
│   ├── final_gate.py
│   ├── health_checker.py
│   ├── kilo_code_review.py
│   ├── kilo_docs_enforcer.py
│   ├── update_agents_toc.py
│   ├── runc
│   ├── rund
│   ├── rundsh
│   ├── runk
│   ├── sync_cascade_backup.sh
│   └── sync_extensions.sh
├── src/
│   └── <project_name>/
│       ├── __init__.py
│       └── main.py
├── tests/
│   ├── __init__.py
│   └── test_health.py
├── .dockerignore
├── .env.example
├── .gitignore
├── .pre-commit-config.yaml
├── AGENTS-compact.md
├── AGENTS.md
├── CHANGELOG.md
├── compose.dev.yaml
├── compose.yaml
├── Dockerfile
├── INDEX.md
├── Makefile
├── opencode.json
├── PORTS.md
├── project.yaml
├── pyproject.toml
├── requirements.txt
├── .windsurfrules
└── README.md
```

---

## Document Generation

### From Templates (`templates/scaffold/docs/`)

| Template | Generated File | Purpose |
|----------|----------------|---------|
| `PROJECT_INDEX_TEMPLATE.md` | `INDEX.md` | Master file index |
| `PROJECT_README_TEMPLATE.md` | `README.md` | Project overview |
| `CHANGELOG_TEMPLATE.md` | `CHANGELOG.md` | Change history |
| `DOCS_INDEX_TEMPLATE.md` | `docs/README.md` | Documentation index |
| `QUICKSTART_TEMPLATE.md` | `docs/QUICKSTART.md` | Quick start guide |
| `CONFIGURATION_TEMPLATE.md` | `docs/CONFIGURATION.md` | Configuration guide |
| `TROUBLESHOOTING_TEMPLATE.md` | `docs/TROUBLESHOOTING.md` | Troubleshooting guide |
| `BUSINESS_MODEL_TEMPLATE.md` | `docs/BUSINESS_MODEL.md` | Business model doc |
| `FEATURES_TEMPLATE.md` | `docs/FEATURES.md` | Features overview |
| `STRATEGIC_BACKLOG_TEMPLATE.md` | `docs/STRATEGIC_BACKLOG.md` | Strategic backlog for paused work |
| `LESSONS_LEARNT_TEMPLATE.md` | `docs/lessons-learnt.md` | Lessons learned documentation |

### Inline Generated (No Templates)

| File | Purpose |
|------|---------|
| `PORTS.md` | Port allocation tracking |
| `docs/development/PLANS.md` | Development plans index |
| `docs/archive/README.md` | Archive directory index |
| `scripts/ci_local.sh` + `.fabrik/run-pytest` | **python API types only.** ⚠️ **No `.github/workflows/ci.yml` since 2026-08-29** — operator directive: no CI checks in existing or future repos (36 of 46 repos are private and burn metered Actions minutes; every existing repo's check workflows were disabled that day). `ci_local.sh` is the clean-room runner (`pgvector/pgvector:pg16` with a DB, else `postgres:16`). `.fabrik/run-pytest` is **load-bearing**: `final_gate.py::_ci_runs_pytest` historically decided local pytest by scanning workflow files for the word "pytest", so a project with no workflow would silently never run its suite. `render_ci_workflow` is retained in `ci_scaffold.py` as the statement of what the checks are, and is what a repo re-emits if the decision is reversed. |

### Copied from Fabrik

| Source | Destination | Purpose |
|--------|-------------|---------|
| `/opt/fabrik/AGENTS.md` | `AGENTS.md` | Traycer orchestrator contract |
| `/opt/fabrik/AGENTS-compact.md` | `AGENTS-compact.md` | Compact agent reference |
| `/opt/fabrik/.windsurfrules` | `.windsurfrules` | Cascade compact agent contract |
| `/opt/fabrik/.windsurf/rules/` | `.windsurf/rules/` | Windsurf IDE rules (22 files) |
| `/opt/fabrik/.windsurf/workflows/` | `.windsurf/workflows/` | Cascade slash-command workflows |
| `/opt/fabrik/opencode.json` | `opencode.json` | Kilo CLI configuration |

### Type-Specific Documents

| Type | File | Purpose |
|------|------|---------|
| `chrome-extension` | `extension/wxt.config.ts` | WXT config (auto-manifest, Preact via @preact/preset-vite) |

---

## Key Components Synced from Fabrik

These files/folders are **auto-synced** from `/opt/fabrik/` to all projects:

### 1. Cascade Compact Contract (`.windsurfrules`)
- **Source:** `/opt/fabrik/.windsurfrules`
- **Synced by:** `sync_enforcement_to_projects.py`
- **Purpose:** Always-loaded Cascade agent contract (~154 lines) — orientation, behavior rules, essential invariants, decision-grade audit

### 2. Governance Rules (`.windsurf/rules/`)
- **Source:** `/opt/fabrik/.windsurf/rules/`
- **Synced by:** `sync_enforcement_to_projects.py`
- **Purpose:** Project-wide coding standards and conventions (22 rule files)

### 3. Cascade Workflows (`.windsurf/workflows/`)
- **Source:** `/opt/fabrik/.windsurf/workflows/`
- **Synced by:** `sync_enforcement_to_projects.py`
- **Purpose:** Slash command workflows for Windsurf Cascade

### 4. Enforcement Scripts (`scripts/enforcement/`)
- **Source:** `/opt/fabrik/scripts/enforcement/`
- **Synced by:** `sync_enforcement_to_projects.py`
- **Purpose:** Quality gate checks (docker, health, env, schema, etc.)

### 5. Cascade Wrappers (`scripts/Local_*.sh`, the Kilo review wrapper (retired 2026-08-15))
- **Source:** `/opt/fabrik/scripts/`
- **Synced by:** `sync_enforcement_to_projects.py`
- **Purpose:** Hardware-safe local LLM agent wrappers

### 6. Core Scripts
- `final_gate.py` - Pre-commit quality gate
- `kilo_code_review.py` - AI-powered code review
- `kilo_docs_enforcer.py` - Documentation enforcer

---

## Variable Substitution

Templates use Jinja2 syntax for variable substitution:

| Variable | Example Value | Used In |
|----------|---------------|---------|
| `{{ project_name }}` | `my-api` | All templates |
| `{{ python_version }}` | `3.12` | Dockerfile, pyproject.toml |
| `{{ port }}` | `8000` | Dockerfile, compose.yaml |
| `{{ description }}` | `API description` | README, pyproject.toml |

---

## Scaffold-to-Deploy Integration (P2/P3/P4 - Implemented 2026-04-10)

### Auto-Spec Generation (P2)

After scaffold completes, `fabrik scaffold` automatically generates a deployment spec file for supported types:

**Supported types (`SPEC_ENABLED_TYPES`, source: `@/opt/fabrik/src/fabrik/spec_generator.py:60-73`, 10 entries):**

- `python-api`
- `python-api-gpu`
- `saas-skeleton`
- `node-api`
- `file-api`
- `file-worker`
- `static-site`
- `docusaurus`
- `chrome-extension`
- `mobile-app`

> **`chrome-extension` and `mobile-app` ARE in `SPEC_ENABLED_TYPES`** — each bundles a deployable FastAPI backend (port 8000, `/health`: `chrome-extension`'s `server/`, `mobile-app`'s `server/` per `scaffold.py:4878-4890`), so each gets its own `specs/services/<name>.yaml` for that backend. Only the packaged client artifact (Chrome Web Store `.zip` / App Store build) is out-of-spec.
>
> **Excluded by design:** `wordpress` (no longer scaffolds in Fabrik — **creation, deployment + lifecycle all moved out** to the standalone `/opt/wpf/` project, `wpf` CLI, per-site `specs/sites/<domain>.yaml`; `fabrik scaffold --type wordpress` redirects to the `wpf` CLI, no skeleton built, `templates/wordpress/` retired; `fabrik apply` on a `wordpress`-type project errors and redirects to `wpf`) and `desktop-app` (a genuinely packaged, direct-distribution artifact with no server component — no VPS deploy, so no spec).

**Spec file location:** `/opt/fabrik/specs/services/{project-name}.yaml`

**Skip spec generation:**
```bash
fabrik scaffold my-api --type python-api --no-spec
```

### CLI Enhancements (P3 — superseded by Phase 4k 2026-04-22)

> 📜 **HISTORICAL:** P3 added `fabrik new --from-project` and `fabrik new --output` flags. Phase 4k deprecated `fabrik new` entirely (hidden from `--help`, deprecation warning to stderr, removal scheduled). `fabrik scaffold` now emits the spec in lock-step with the project tree, with a `shape:` block driven by `templates/<type>/defaults.yaml` — there is no longer any need for a separate spec-generation command.

### Deployment Validation (P4)

**`fabrik validate-deploy` command:**
Checks deployment readiness of a scaffolded project with 5 checks:
- Deploy template exists
- `.env.example` present
- Dockerfile present
- Health endpoint detected
- Spec pre-existence info

**Post-scaffold validation:**
`fabrik scaffold` automatically runs validation after project creation and prints warnings (non-blocking).

---

## Scaffold Types

Different scaffold types create variations:

| Type | Base Template | Additional Files |
|------|---------------|------------------|
| `python-api` | `templates/scaffold/` | FastAPI + Uvicorn setup |
| `python-api-gpu` | `templates/python-api-gpu/` | GPU-aware `python-api` variant (`gpu_rent` job-handler hook) |
| `saas-skeleton` | `templates/saas-skeleton/` | Next.js 14 + TypeScript + Tailwind |
| `static-site` | `templates/saas-skeleton/` | Same as saas-skeleton (landing pages) |
| `node-api` | `templates/node-api/` | Express + JavaScript |
| `file-api` | `templates/file-api/` | File operations API (Node.js) |
| `file-worker` | `templates/file-worker/` | Python background worker |
| `wordpress` | _(retired — moved to `/opt/wpf/`)_ | `fabrik scaffold --type wordpress` redirects to the `wpf` CLI; no scaffolding or deploy in Fabrik |
| `docusaurus` | `templates/docusaurus/` | Docusaurus docs site |
| `chrome-extension` | `templates/chrome-extension/` | Chrome extension (WXT + Preact) + Python backend |
| `mobile-app` | `templates/mobile-app/` | Expo/React Native client + bundled FastAPI backend (`server/`) that deploys via `fabrik apply`, mirroring `chrome-extension` |
| `desktop-app` | `templates/desktop-app/` | Electron + TypeScript |

> ✅ **Resolved 2026-06-17:** WordPress scaffolding was retired (the code-side decision). `_scaffold_wordpress` + `WORDPRESS_TEMPLATE_DIR` were removed from `scaffold.py`; `fabrik scaffold --type wordpress` now redirects to the `/opt/wpf` `wpf` CLI before writing anything (no crash, no partial directory). `wordpress` stays a recognised deploy/shape type.

---

## Post-Scaffold Initialization

`create_project()` (`@/opt/fabrik/src/fabrik/scaffold.py:2915`) **already performs** these steps automatically before returning:

1. `git init` + `git checkout -b mobasak/<project-name>`
2. `.venv` creation + `pip install -r requirements-dev.txt` (Python types only)
3. `pre-commit install` (via `_install_pre_commit()`, `scaffold.py:327`)
4. Initial commit (`git add . && git commit -m "Initial commit"`)
5. `_post_scaffold_sync()` registers the project in `data/projects.yaml` and refreshes the Fabrik-level `docs/PROJECT_CATALOG.md` (renamed from `BUSINESS_MODEL.md` 2026-07-11 — not the new project's own per-project `docs/BUSINESS_MODEL.md`, which is seeded separately from the scaffold's `BUSINESS_MODEL_TEMPLATE.md`)
6. `generate_and_save_spec()` for `SPEC_ENABLED_TYPES` (skipped if `--no-spec`)
7. `validate-deploy` warnings printed (non-blocking)

What the **user** typically does next:

```bash
cd /opt/<project-name>
source .venv/bin/activate          # activate the venv scaffold already created
uv pip install -e ".[dev]"         # editable install if you want imports to resolve from src/
python scripts/final_gate.py --lean # sanity-check the freshly-scaffolded tree
```

> **Do not re-run** `git init` or `pre-commit install` — they have already executed and a clean initial commit exists on a `mobasak/<project-name>` branch.

---

## Sync Mechanism

Projects stay synchronized with Fabrik master via:

1. **Pre-commit hook:** Runs `sync_enforcement_to_projects.py` before each commit in Fabrik
2. **Manual sync:** Run `python /opt/fabrik/scripts/sync_enforcement_to_projects.py` anytime
3. **Scaffold refresh:** Re-scaffolding updates templates (preserves project-specific code)

---

## See Also

- [FABRIK_SCAFFOLD_WORKFLOW.md](FABRIK_SCAFFOLD_WORKFLOW.md) - Detailed scaffold workflow
- [SYNC_ENFORCEMENT_WORKFLOW.md](SYNC_ENFORCEMENT_WORKFLOW.md) - How syncing works
- [FINAL_GATE_WORKFLOW.md](FINAL_GATE_WORKFLOW.md) - Quality gates
- `docs/reference/modules/templates.md` - Template reference (templates/ has no dev-guide README of its own)
