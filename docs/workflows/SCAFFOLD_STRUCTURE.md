# Fabrik Scaffold Structure

**Last Updated:** 2026-09-22 — every tree entry below is re-derived from a fresh `create_project(project_type="python-api")` emission (`scripts/enforcement/pack_layout_audit.py::_emitted_paths_for_type`, 283 paths; its walker prunes the 15 names in `scripts/rules_match.py::_EXCLUDE`, so `.droid/`, `backups/`, `output/`, `.tmp/`, `templates/`, `.git/` and `.venv/` are grounded in `scaffold.py` directly), every list from `scripts/fabrik_synced_manifest.py`, every count from `git ls-files`.
**Script:** `src/fabrik/scaffold.py` (`create_project`, the `fabrik scaffold` command)

> Complete reference for the folder and file structure created by `fabrik scaffold`. Sister doc to the broader `FABRIK_SCAFFOLD_WORKFLOW.md` (this file is narrowly scoped to the file tree).

---

## Overview

`fabrik scaffold <project-name> --type python-api` creates the structure below in `/opt/<project-name>/`. `SCAFFOLD_TYPES` (`scaffold.py`) registers 13 types; 12 scaffold and `wordpress` is refused (§ Scaffold Types).

---

## Complete Scaffold Tree (`--type python-api`)

```
/opt/<project-name>/
├── .claude/
│   ├── hooks/                     # 7 fleet-synced hooks: agent_role · final_gate_stop · mail_notify ·
│   │                              #   mcp_watch · quota_stop · session_orient · skill_router (with
│   │                              #   settings.json and .windsurf/hooks.json = the 9 AGENT_HOOK_FILES)
│   ├── settings.json              # synced (hooks + permissions.allow)
│   └── settings.local.json
├── .droid/                        # .gitignore · review-context/.gitkeep · traycer-reports/.gitignore
├── .fabrik/
│   └── run-pytest                 # arms the gate's pytest leg (python-api · python-api-gpu · file-api)
├── .git/ · .venv/                 # git init + the venv (Python types) — pruned from the emission, created by the scaffolder
├── .mcp.json                      # EMITTED by scripts/sysadmin/emit_mcp_project_config.py — gitignored
├── .windsurf/
│   ├── hooks.json                 # synced (AGENT_HOOK_FILES)
│   ├── rules/                     # 56 packs, ALL in subdirs: ai/ 11 · chrome-ext/ 3 · core/ 29 ·
│   │   ├── CLAIMS.yaml            #   desktop-app/ 2 · mobile-app/ 6 · saas/ 5 — no pack at the top level
│   │   └── versions.yaml
│   └── workflows/                 # 6: bug-fix · deploy · new-feature · registrar-audit · review · subagent-runs-flywheel
├── db/
│   └── schema.sql
├── docs/
│   ├── archive/README.md
│   ├── development/
│   │   ├── PLANS.md
│   │   └── plans/
│   ├── guides/
│   ├── operations/
│   ├── reference/
│   │   ├── MD/                    # created EMPTY at scaffold; filled by the sync (GOVERNANCE_DIRS)
│   │   ├── kilo/                  # copied at scaffold — 12 selection/benchmark docs (GOVERNANCE_DIRS)
│   │   ├── opt-project-catalog.md # copied at scaffold (from the hub's docs/PROJECT_CATALOG.md)
│   │   ├── prebuilt-app-containers.md
│   │   └── technology-stack-decision-guide.md
│   ├── CONFIGURATION.md · DECISIONS.md · DEPLOYMENT.md · FEATURES.md · LESSONS_LEARNT.md
│   ├── OPERATIONS.md · QUICKSTART.md · README.md · RESILIENCE.md · SERVICES.md
│   ├── STRATEGIC_BACKLOG.md · TROUBLESHOOTING.md
│   └── data-contract.md           # (docs/BUSINESS_MODEL.md is seeded for the SaaS bucket only — see § Document Generation)
├── libs/
│   └── health_probe/              # vendored (VENDORED_DIRS): __init__ · fingerprint · health_probe
├── templates/                     # (pruned from the emission — grounded in _scaffold_shared)
│   ├── saas-skeleton/             # 43 files, copied into EVERY type by _scaffold_shared (build artifacts excluded)
│   └── spec-pipeline/             # 3 Traycer stage-0 prompts + a README, copied from the hub
├── scripts/
│   ├── enforcement/               # the whole dir, 78 files (git ls-files scripts/enforcement)
│   ├── ci_local.sh                # local clean-room check runner (python-api · python-api-gpu · file-api)
│   ├── command_run.py · doc_reconcile.py · docs_updater.py · final_gate.py · health_checker.py
│   ├── mail.py · release_cut.py · review_receipt.py · review_rubric.py · rivals_run.py
│   ├── rules_match.py · select_rules.py · thread_anchor.py · whoami_agent.py   # CORE_SCRIPTS (14)
│   ├── verify_prod_parity.py      # the parity-contract runner
│   ├── kilo_47_agents_final.json  # agent registry snapshot (gitignored in the hub)
│   └── runc · runclean · rund · rundsh · runk · runlast · runls · runtail · runwait
│       · sync_cascade_backup.sh · sync_extensions.sh                           # RUN_SCRIPTS (11)
├── src/
│   └── <project_name>/
│       ├── __init__.py · main.py · logger.py · middleware.py · metrics.py
│       └── glitchtip_init.py · internal_auth.py · pause_state.py
├── tests/
│   └── __init__.py · conftest.py · test_health.py
├── config/ · data/ · logs/ · backups/ · .tmp/ · output/ · .cache/   # standard dirs
├── .dockerignore · .env.example · .gitignore · .pre-commit-config.yaml
├── .windsurfrules · .worktreeinclude
├── AFCL.md · AGENTS.md · AGENTS-compact.md · CHANGELOG.md · CLAUDE.md · INDEX.md · PORTS.md · README.md
├── compose.yaml · compose.dev.yaml · Dockerfile · Makefile
└── opencode.json · project.yaml · pyproject.toml · requirements.txt · requirements-dev.txt
```

`.github/` is not emitted: CI checks are retired fleet-wide (operator directive), and `scripts/ci_local.sh` is the
clean-room runner instead (`src/fabrik/ci_scaffold.py::ci_files` returns exactly `scripts/ci_local.sh` and
`.fabrik/run-pytest`; `render_ci_workflow` stays there as the statement of what the checks are).

---

## Document Generation

### From Templates (`templates/scaffold/docs/`, `scaffold.py::SHARED_TEMPLATE_MAP`, 17 entries)

Seeding is **type-aware**: `_scaffold_shared` skips a doc whose registry bucket does not cover the type
(`scripts/enforcement/_doc_registry.py` — a headless `python-api` gets no `BUSINESS_MODEL.md`), and a
`docusaurus` project never gets `data-contract.md` (it publishes its whole `docs/` tree).

| Template | Generated File |
|----------|----------------|
| `PROJECT_README_TEMPLATE.md` | `README.md` |
| `CHANGELOG_TEMPLATE.md` | `CHANGELOG.md` |
| `DOCS_INDEX_TEMPLATE.md` | `docs/README.md` |
| `QUICKSTART_TEMPLATE.md` | `docs/QUICKSTART.md` |
| `CONFIGURATION_TEMPLATE.md` | `docs/CONFIGURATION.md` |
| `TROUBLESHOOTING_TEMPLATE.md` | `docs/TROUBLESHOOTING.md` |
| `SERVICES_TEMPLATE.md` | `docs/SERVICES.md` |
| `RESILIENCE_TEMPLATE.md` | `docs/RESILIENCE.md` |
| `OPERATIONS_TEMPLATE.md` | `docs/OPERATIONS.md` |
| `DEPLOYMENT_TEMPLATE.md` | `docs/DEPLOYMENT.md` (deployed bucket) |
| `BUSINESS_MODEL_TEMPLATE.md` | `docs/BUSINESS_MODEL.md` (SaaS bucket) |
| `FEATURES_TEMPLATE.md` | `docs/FEATURES.md` |
| `STRATEGIC_BACKLOG_TEMPLATE.md` | `docs/STRATEGIC_BACKLOG.md` |
| `LESSONS_LEARNT_TEMPLATE.md` | `docs/LESSONS_LEARNT.md` |
| `DECISIONS_TEMPLATE.md` | `docs/DECISIONS.md` (the decision ledger; the sync also seeds it where missing) |
| `data-contract-template.md` | `docs/data-contract.md` (not for `docusaurus`) |
| `PROJECT_INDEX_TEMPLATE.md` | `INDEX.md` |

`templates/scaffold/AFCL_TEMPLATE.md` → `AFCL.md` (copied, then customised per project — never synced).
`templates/scaffold/docs/FINANCIALS.md` is on disk but in no map.

### Inline Generated (No Templates)

| File | Purpose |
|------|---------|
| `PORTS.md` | Port allocation tracking |
| `docs/development/PLANS.md` | Development plans index |
| `docs/archive/README.md` | Archive directory index |
| `db/schema.sql` | Schema header, written as an f-string (the `templates/scaffold/db/schema.sql` file is not read) |
| `scripts/ci_local.sh` + `.fabrik/run-pytest` | `python-api`, `python-api-gpu` and `file-api` only (`_CI_PYTHON_TYPES`). `.fabrik/run-pytest` is load-bearing: `final_gate.py`'s pytest leg is armed by the sentinel (or a workflow naming pytest), so a project with neither never runs its suite (CLAUDE.md § Completion Contract 2) |
| `.mcp.json` | the repo's ruled MCP set, emitted inside `create_project` and gitignored (`docs/workstation/mcp-roster.md`) |

### Copied from Fabrik at scaffold time

| Source | Destination |
|--------|-------------|
| `/opt/fabrik/AGENTS.md` (a 9-line pointer to `agents-fabrik.md`), `AGENTS-compact.md`, `.windsurfrules`, `opencode.json` | same name at the project root — 4 of the 6 GOVERNANCE_FILES; `agents-fabrik.md` and `agents-fabrik-core.md` arrive with the governance sync, not at scaffold time |
| `templates/governance/CLAUDE.md`, `DECISIONS.md`, `.worktreeinclude` | `CLAUDE.md`, `docs/DECISIONS.md`, `.worktreeinclude` (GOVERNANCE_TEMPLATES) |
| `/opt/fabrik/.windsurf/rules/`, `.windsurf/workflows/`, `docs/reference/kilo/` | same paths (3 of the 4 GOVERNANCE_DIRS; `docs/reference/MD/` is created empty and filled by the sync) |
| `/opt/fabrik/scripts/enforcement/` | `scripts/enforcement/` (78 files) |
| `/opt/fabrik/scripts/<core>` (CORE_SCRIPTS, 14, read from the manifest) | `scripts/` |
| `templates/scaffold/scripts/` — the 11 RUN_SCRIPTS + `verify_prod_parity.py` (`scaffold.py::SCRIPT_FILES`, 12) | `scripts/` |
| `/opt/fabrik/.claude/hooks/*` + `.claude/settings.json` + `.windsurf/hooks.json` | same paths (AGENT_HOOK_FILES, 9) |
| `libs/health_probe/` | `libs/health_probe/` (VENDORED_DIRS) |
| `docs/PROJECT_CATALOG.md`, `PORTS.md`, `docs/reference/technology-stack-decision-guide.md` — 3 of the 7 REFERENCE_DOCS — plus `docs/reference/prebuilt-app-containers.md` (in no manifest list) | `docs/reference/opt-project-catalog.md`, `PORTS.md`, the same two names. The `PORTS.md` copy is overwritten at once by the inline-generated one — which the first FORCED governance-sync replaces with the hub's `PORTS.md` again — the post-commit sync runs `--force` (`scripts/governance_sync_postcommit.sh`), and `--force` skips the `dest_mtime > source_mtime` "destination newer" branch entirely (`sync_enforcement_to_projects.py::sync_single_file`); a NON-forced run (the live `watch_enforcement_changes.sh` watcher and the 06:00 `daily_refresh.sh` step, both invoking the sync with no flags) WARN-skips that generated file — written with `mtime = now` — as destination-newer until a hub edit makes the source newer. 46 of the 48 synced projects hold the hub's `PORTS.md` byte-for-byte today and none holds a generated one. The remaining 4 REFERENCE_DOCS arrive with the sync |
| `/opt/fabrik/scripts/kilo_47_agents_final.json` | `scripts/kilo_47_agents_final.json` (in no manifest list) |
| `templates/saas-skeleton/` (43 files, build artifacts excluded) + `templates/spec-pipeline/` (4 files) | the same paths, for every type |

The manifest is the canonical list of what the SYNC distributes — read it, never this table, when the two disagree; this table is what the scaffolder itself copies.

### Type-Specific Documents

| Type | File | Purpose |
|------|------|---------|
| `chrome-extension` | `extension/wxt.config.ts` | WXT config (auto-manifest, Preact via @preact/preset-vite) |
| `office-extension` | `manifest.xml` | the Office add-in manifest the host loads (`_write_office_manifest`) |

---

## Key Components Synced from Fabrik

These are **auto-synced** from `/opt/fabrik/` to every project by `scripts/sync_enforcement_to_projects.py`; the canonical list is `scripts/fabrik_synced_manifest.py`:

1. **Cascade compact contract** — `.windsurfrules` (81 lines; Cascade silently truncates it at 6,000 characters, so the budget is characters, not lines).
2. **Governance files** — the 6 GOVERNANCE_FILES (`AGENTS.md`, `AGENTS-compact.md`, `agents-fabrik.md`, `agents-fabrik-core.md`, `.windsurfrules`, `opencode.json` — the last is the Kilo-safe rules config, still gated by `check_opencode_json.py`) and the 3 GOVERNANCE_TEMPLATES (`CLAUDE.md`, `docs/DECISIONS.md`, `.worktreeinclude`).
3. **Governance rules** — `.windsurf/rules/` (56 packs in 6 subdirs) — project-wide coding standards.
4. **Workflows** — `.windsurf/workflows/` (6 files).
5. **Enforcement scripts** — `scripts/enforcement/` (78 files): the quality-gate checks.
6. **Core scripts** — the 14 CORE_SCRIPTS (`final_gate.py` is the COMPLETION gate, run by hand; `command_run.py`, `docs_updater.py`, `review_rubric.py`, …) and the 11 RUN_SCRIPTS. `kilo_code_review.py`, `kilo_docs_enforcer.py` and `update_agents_toc.py` are RETIRED_CORE_SCRIPTS: the sync DELETES stale project copies and never re-seeds them.
7. **Agent hooks** — `.claude/hooks/` + `.claude/settings.json` + `.windsurf/hooks.json` (AGENT_HOOK_FILES).
8. **Reference docs and dirs** — REFERENCE_DOCS + `docs/reference/MD/` + `docs/reference/kilo/`.
9. **Vendored module** — `libs/health_probe/`.

The project's `.gitignore` carries a generated "Fabrik-synced" block for these paths (DISTRIBUTED_GITIGNORE_GROUPS), and `check_synced_unmodified.py` blocks local edits to a synced copy.

---

## Variable Substitution

The scaffolder does not run a template engine. `_scaffold_shared` (`scaffold.py`, the `SHARED_TEMPLATE_MAP` loop) rewrites bracket tokens by plain string replacement — `[Project Name]`, `<project>`, `project-name`, `myproject`, `[package_name]`, `<package_name>`, `YYYY-MM-DD`, `[Brief description]`, `[PORT]` — and a few type scaffolders replace literal `{{ spec.name }}` / `{{ spec.id }}` / `{{ name }}` tokens the same way. The Jinja2 environment in `src/fabrik/template_renderer.py` renders the DEPLOY templates from a spec and is never imported by `scaffold.py`; a `{{ … }}` placeholder found under `templates/scaffold/` is not something the scaffolder reads.

---

## Scaffold-to-Deploy Integration

### Auto-Spec Generation

Inside `create_project`, `generate_and_save_spec()` writes a deployment spec for the 10 `SPEC_ENABLED_TYPES` (`src/fabrik/spec_generator.py`): `python-api`, `python-api-gpu`, `saas-skeleton`, `node-api`, `file-api`, `file-worker`, `static-site`, `docusaurus`, `chrome-extension`, `mobile-app`. Each type's `shape:` defaults come from `templates/<type>/defaults.yaml`, which is also where the per-type `compose.yaml.j2` lives — those directories serve the spec/deploy path, not the scaffold tree.

> `chrome-extension` and `mobile-app` ARE spec-enabled: each bundles a deployable FastAPI backend under `server/` (port 8000, `/health`), so each gets its own `specs/services/<name>.yaml` for that backend. Only the packaged client artifact (Chrome Web Store `.zip` / App Store build) is out-of-spec.
>
> **Not spec-enabled:** `desktop-app` (a packaged, direct-distribution artifact with no server component), `office-extension` (not in `SPEC_ENABLED_TYPES`), and `wordpress` (not scaffolded at all — § Scaffold Types).

**Spec file location:** `/opt/fabrik/specs/services/{project-name}.yaml`. Skip it with `fabrik scaffold my-api --type python-api --no-spec`.

`fabrik new` is DEPRECATED and hidden (`cli.py`, `hidden=True`): `fabrik scaffold` emits the spec in lock-step with the tree.

### Deployment Validation

**`fabrik validate-deploy <project_path> [--type <type>]`** (`src/fabrik/deploy_validator.py::validate`) runs 5 local checks and always exits 0 — warnings only: deploy template exists · `.env.example` present · Dockerfile present (skipped for the types whose validator does not require a root Dockerfile) · health endpoint detected (a real scan of the health file) · spec pre-existence.

The `fabrik scaffold` command runs the same checks after `create_project()` returns and prints the warnings (non-blocking); a programmatic `create_project()` caller gets no validation.

---

## Scaffold Types

`_TYPE_SCAFFOLDERS` (`scaffold.py`) maps each type to its scaffold function. The "Scaffolder reads" column names what the type's own function opens; several types are generated inline. Two shared steps apply to every type and are not repeated per row: `_scaffold_shared` seeds the `templates/scaffold/` docs and scripts first, and `_provision_i18n` adds the `templates/i18n-kit/` files afterwards for the `I18N_ENABLED_TYPES` (`saas-skeleton`, `static-site`, `desktop-app`, `mobile-app`, `docusaurus`).

| Type | Scaffolder reads | What is built |
|------|------------------|---------------|
| `python-api` | `templates/scaffold/` (`TEMPLATE_DIR`) | FastAPI + Uvicorn service (`_scaffold_fastapi_backend`) |
| `python-api-gpu` | the `python-api` scaffold, then inline GPU additions | GPU-aware `python-api` variant (`gpu_rent` job-handler hook) |
| `saas-skeleton` | `templates/saas-skeleton/` (`SAAS_SKELETON_DIR`) | Next.js + TypeScript + Tailwind, with a FastAPI backend (`_scaffold_saas_backend`) |
| `static-site` | the `saas-skeleton` scaffolder | same tree (landing pages) |
| `office-extension` | the `saas-skeleton` scaffolder; `manifest.xml` written inline | the hosted taskpane web + backend, plus `manifest.xml` |
| `node-api` | `templates/scaffold/docker/Dockerfile.node` + `Makefile.node`; the rest inline | a Node.js service on the built-in `http.createServer` with `pino` logging and optional `@sentry/node` — no Express (`templates/node-api/` holds only the deploy defaults; its `package.json` is not read) |
| `file-api` | `templates/file-api/` + `templates/scaffold/` | File operations API (Node.js) |
| `file-worker` | `templates/file-worker/` + `templates/scaffold/` | Python background worker |
| `docusaurus` | `templates/docusaurus/` | Docusaurus docs site |
| `chrome-extension` | inline only (`templates/chrome-extension/` holds only the deploy defaults) | Chrome extension (WXT + Preact) + FastAPI backend under `server/` |
| `mobile-app` | `templates/mobile-app/` | Expo/React Native client + FastAPI backend under `server/`, deployable via `fabrik apply` |
| `desktop-app` | `templates/desktop-app/` | Electron + TypeScript |
| `wordpress` | _(refused)_ | stays in `SCAFFOLD_TYPES` for legacy deploy/shape routing only: `create_project` raises `NotImplementedError` and the `fabrik scaffold` command exits 1 first. WordPress creation, deployment and lifecycle left Fabrik; the standalone `wpf` project is archived at `/opt/archived/wpf` and its CLI no longer exists |

---

## Post-Scaffold Initialization

`create_project()` (`scaffold.py::create_project`) performs these steps before returning:

1. `_scaffold_shared`: the shared tree, then `git init` + `git checkout -b mobasak/<project-name>`, then `pre-commit install` (`_install_pre_commit`, the system binary — before any venv exists)
2. the type's scaffolder; for Python types it creates `.venv` and runs `pip install -r requirements-dev.txt`
3. `_provision_i18n` for the `I18N_ENABLED_TYPES`
4. Initial commit (`git add . && git commit -m "Initial commit"`)
5. `_post_scaffold_sync()` runs `scripts/sync_projects.py`: registers the project in `data/projects.yaml` and refreshes the hub's `docs/PROJECT_CATALOG.md`
6. the repo's `.mcp.json` is emitted (the MCP split, D-028/D-029)
7. `generate_and_save_spec()` for `SPEC_ENABLED_TYPES` (skipped with `--no-spec`)

The `fabrik scaffold` command then prints the `validate-deploy` warnings and, for build-context types with `gh` authenticated, creates and wires a private GitHub repo at `mobasak/<name>` (`--github-create` forces it, `--no-github` skips it).

What the **user** typically does next:

```bash
cd /opt/<project-name>
source .venv/bin/activate          # activate the venv scaffold already created
uv pip install -e ".[dev]"         # editable install (pyproject.toml declares the dev group)
python scripts/final_gate.py --lean # sanity-check the freshly-scaffolded tree
```

> **Do not re-run** `git init` or `pre-commit install` — they have already executed and a clean initial commit exists on a `mobasak/<project-name>` branch.

---

## Sync Mechanism

Projects stay synchronized with Fabrik master via:

1. **Post-commit hook (hub):** a plain git post-commit hook (`scripts/install_post_commit_hook.sh`) runs `scripts/governance_sync_postcommit.sh`, which reads the trigger regex from the `governance-sync` entry in `.pre-commit-config.yaml` (`stages: [manual]` — pre-commit never runs it, D-369) — a hub commit touching a trigger surface distributes to every `/opt` project after the commit lands; the trigger set is that hook's `files:` filter (CLAUDE.md § Sync-consciousness). It cannot block a commit, and a failed sync prints the manual re-run command.
2. **Manual sync:** `python /opt/fabrik/scripts/sync_enforcement_to_projects.py [--force]` anytime.
3. **Watcher:** `scripts/watch_enforcement_changes.sh` (inotifywait on the governance files) when started from the WSL startup hook.
4. **Repair:** `scaffold.py::fix_project` adds the required files a project is missing AND force-refreshes the synced surfaces from the hub — `.windsurf/rules/`, `.windsurf/workflows/` and `docs/reference/kilo/` are deleted and re-copied, and `.windsurfrules`, `AGENTS.md`, `AGENTS-compact.md`, `.windsurf/hooks.json`, `opencode.json`, `docs/reference/technology-stack-decision-guide.md`, `docs/reference/prebuilt-app-containers.md` and `scripts/kilo_47_agents_final.json` are overwritten; a local edit under any of those is lost. Its missing-file seeding uses `fabrik fix --type` when given, else the `type` in the project's own `project.yaml`, and refuses when there is neither; the same type drives the `has_user_guide` backfill. `python-api` and `python-api-gpu` are repaired from the python-api template map, every other type from the shared map only, and a missing type-specific file with no template is reported (`[unsupported-fix]`, exit 1 from the CLI) and never stubbed.

---

## See Also

- [FABRIK_SCAFFOLD_WORKFLOW.md](FABRIK_SCAFFOLD_WORKFLOW.md) - Detailed scaffold workflow
- [SYNC_ENFORCEMENT_WORKFLOW.md](SYNC_ENFORCEMENT_WORKFLOW.md) - How syncing works
- [FINAL_GATE_WORKFLOW.md](FINAL_GATE_WORKFLOW.md) - Quality gates
- `docs/reference/modules/templates.md` - Template reference (`templates/` carries no README of its own)
