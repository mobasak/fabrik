# Coolify-Migration Doc & Code Cleanup — Surgical-Edit Plan

**Date:** 2026-05-30
**Author:** generated after Tier A complete + Tier B partial (commit `6ae18ab`)
**Scope:** Plan the remaining work to converge on factually-current docs and code comments after the Fabrik SSH+Compose migration replaced the Coolify-API deployer.

---

## 1. Context

### What's already done (commit `6ae18ab`)

- **Tier A (governance + Traycer planning)** — fully converged:
  - `CLAUDE.md`, both `EVALUATION_CHECKLIST*` files, `fabrik-workflow.md`, `1-trigger-workflow.md`, all `mega-epic-breakdown/` and `epic-to-ticket-workflow/` command files, all 5 `domain-modules/*` (chrome-ext, mobile-app, saas, wordpress, rag).
- **Tier B partial** — high-impact user-facing files:
  - `FAQ.md`, `QUICKSTART.md`, `TROUBLESHOOTING.md` — surgical edits done.
  - Bulk pass cleaned ~30 simple "via Coolify"→"via fabrik apply" swaps across other docs.
- **Source code (sync mechanism):**
  - `scaffold.py` + `sync_enforcement_to_projects.py` — catalog consolidated to `BUSINESS_MODEL.md`; lifecycle sync source moved to `operations/`; orphan deletion added.
  - `sync-vps-sysadmin.sh` + `sysadmin/system-prompt.txt` — lifecycle path updated.
- **Traycer mega-epic-breakdown renumbered** — `04 = cross-epic-validation`, `05 = dispatch-epic-tickets` (matches execution order).

### What remains (this plan)

- **Tier B continuation:** ~30 active docs with stale deploy-mechanism references that need per-file judgment.
- **Tier C:** ~10–15 source files with stale comments/docstrings.
- **Untouched on purpose:** auto-generated docs, intentional Coolify-system docs, historical plans, the legacy deployer/driver code.

### The critical context that governs scope

**Coolify is still installed on the VPS** (v4.0.0-beta.459, monitored by Gatus, hosts `coolify-db`, `coolify-redis`, several legacy containers). What changed is *fabrik no longer uses Coolify-API to deploy*. So **not every "Coolify" reference is stale** — three distinct treatments:

| Category | Treatment | Examples |
|---|---|---|
| **Stale deploy-mechanism refs** | **Fix** | "deploys via Coolify API", "Coolify v4 quirks", "push to Coolify API" |
| **Coolify-as-still-installed refs** | **Keep** | service inventory, env table, Gatus monitoring, the `coolify` Docker network name |
| **Legacy code refs** | **Keep, mark as legacy** | `drivers/coolify.py`, `coolify_uuid` state field, `deployer_coolify.py` archived file |

---

## 2. File-by-File Plan

### 2.1 Tier B — Active docs needing surgical edits

Counts are remaining Coolify mentions in each file as of commit `6ae18ab`. **The count is not the work estimate** — many will be quick keeps; some require deep rewrites.

#### 2.1.1 User-facing root docs (HIGH priority)

| File | Remaining | Notes |
|---|---:|---|
| `docs/CONFIGURATION.md` | 14 | **Tricky.** `Coolify API Token` section (l46–51) — obsolete for fabrik, mark deprecated. The `coolify.alias` spec field section (l300–316) — *still active* for Gatus monitoring of single-image Coolify Applications; keep but note it's a Coolify-platform feature. `Coolify API 401` troubleshooting (l333–338) — obsolete; remove. `Production: env vars set by Coolify` (l389) — stale; replace with "set by fabrik in `/opt/<name>/.env`". |
| `docs/FEATURES.md` | 19 | Deploy-flow narrative (l38, l46) — replace Coolify mechanic. `coolify_uuid`/`coolify_app_name` state fields (l359–360, l406) — keep, describe as legacy compat. Drivers list (l102) — mark `coolify` as legacy. `--partial` description (l423), `fabrik dev no Coolify involvement` (l474), destroy phases (l567) — clean refs. |
| `docs/DEPLOYMENT_ARCHITECTURE.md` | 23 | **Mostly correct already** (reviewed earlier in session). Re-scan for any "Coolify"-as-deploy-platform language; legacy `deployer_coolify.py` + `CoolifyConfig` + `coolify_uuid` references are intentional. |
| `docs/SERVICES.md` | 13 | **Mostly correct** — describes Coolify-as-installed-service (still true). Only fix: l3 "Last Updated" parenthetical "migrated to Coolify management" — true historically but consider noting fabrik doesn't deploy via Coolify anymore. Headers l34 "Managed by Coolify" — accurate for legacy services. Verify nothing leaked from bulk sed. |
| `docs/BUSINESS_MODEL.md` | 1 | Service table row "Coolify Free Deployment" — accurate (Coolify still installed, used for legacy services). Keep, optionally annotate "legacy services only". |
| `docs/EXTERNAL_SYSTEMS.md` | 8 | Coolify documented as external system. Mostly accurate — Coolify is still installed. Update the integration description to clarify fabrik no longer calls the Coolify API. |
| `docs/FAQ.md` | ~2 (post-edit) | Re-verify after my earlier edits; line 96 still references the old `coolify` net mention. |
| `docs/QUICKSTART.md` | ~0 (post-edit) | Re-verify. |
| `docs/TROUBLESHOOTING.md` | ~6 (post-edit) | Historical "Pre-2026-04-28" fix descriptions still reference Coolify mechanics (l85–106 health-check-404, l108–114 docusaurus grace, l128–130 inline-compose endpoint). These are historical — either delete or reframe as "Historical (Coolify-era)". |

#### 2.1.2 Operations docs (MEDIUM priority)

| File | Remaining | Notes |
|---|---:|---|
| `docs/operations/deployment.md` | 8 | Already heavily reviewed. Check for remaining intentional/legacy refs. |
| `docs/operations/backup-strategy.md` | 12 | Backups now via Backrest, not Coolify. Update references. |
| `docs/operations/disaster-recovery.md` | 14 | DR procedures — likely reference Coolify restore steps that are now SSH+Compose-based. |
| `docs/operations/fabrik-lifecycle.md` | 3 | Already reviewed; minor residue. |
| `docs/infrastructure/vps-urls.md` | 12 | URL table — `coolify.vps1.ocoron.com` is still a valid URL since Coolify is installed. Verify URLs match live state. |

#### 2.1.3 Reference docs (MEDIUM-LOW priority)

| File | Remaining | Notes |
|---|---:|---|
| `docs/reference/stack.md` | 46 | **Heaviest.** Tech-stack overview that may extensively describe Coolify as the deploy platform. Needs deep rewrite of deploy sections. |
| `docs/reference/architecture.md` | 20 | Architecture diagrams + narrative — replace Coolify-deploy-flow descriptions. |
| `docs/reference/provisioner.md` | 18 | Documents `src/fabrik/provisioner.py` (the legacy Coolify provisioner). Keep references as documenting legacy code; mark as "legacy / pre-SSH-deployer". |
| `docs/reference/health-monitoring.md` | 17 | Health/monitoring guide. Coolify health checks are now Gatus checks. |
| `docs/reference/prebuilt-app-containers.md` | 11 | "Deploy via Coolify" instructions for prebuilt containers — replace with fabrik flow. |
| `docs/reference/fabrik.md` | 10 | Fabrik CLI overview. |
| `docs/reference/drivers.md` | 9 | Driver list including `coolify`. Mark as legacy. |
| `docs/reference/fabrik-cli-reference.md` | 8 | Likely describes `fabrik logs` etc. that historically used Coolify API. |
| `docs/reference/file-api-deployment.md` | 6 | file-api deployment instructions. |
| `docs/reference/saas-alternative-gui.md` | 6 | SaaS alternatives comparison (Coolify vs Vercel etc.). Keep — comparison context. |
| `docs/reference/roadmap.md` | 6 | Roadmap may mention Coolify deprecation. Review. |
| `docs/reference/service-contracts/site-provisioner.md` | 4 | Service contract doc. |
| `docs/reference/orchestrator.md` | 3 | Orchestrator description. |
| `docs/reference/templates.md` | 3 | Template descriptions. |
| `docs/reference/technology-stack-decision-guide.md` | 2 | Already reviewed; minor residue. |
| `docs/reference/glitchtip-api.md` | 2 | GlitchTip API integration; quick check. |
| `docs/reference/windsurf/windsurf_features.md` | 1 | Quick check. |
| `docs/reference/uptime-kuma.md` | 1 | Quick check. |

#### 2.1.4 Workflows (MEDIUM priority)

| File | Remaining | Notes |
|---|---:|---|
| `docs/workflows/FABRIK_SCAFFOLD_WORKFLOW.md` | 38 | **Heavy.** Scaffold workflow may have substantial Coolify-deploy instructions. |
| `docs/workflows/KILO_CONSULT_WORKFLOW.md` | 13 | Kilo consultation workflow. |
| `docs/workflows/development-and-deployment-workflow.md` | 12 | Dev+deploy workflow guide. |
| `docs/workflows/windsurf-triggered-workflows.md` | 3 | Windsurf workflow triggers. |
| `docs/workflows/DATA_SYNC_WORKFLOW.md` | 1 | Quick check. |

#### 2.1.5 Infrastructure (MEDIUM priority)

| File | Remaining | Notes |
|---|---:|---|
| `docs/infrastructure/glitchtip-sdk-integration-setup.md` | 16 | GlitchTip setup that referenced Coolify env-var injection. Now fabrik handles this via registrars. |
| `docs/infrastructure/grafana-provisioning-setup.md` | 12 | Grafana setup. |
| `docs/infrastructure/promtail-noise-filter-setup.md` | 12 | Filter setup — references `coolify-db`, `coolify-redis` log streams (legitimate; those containers still run). Keep. |
| `docs/infrastructure/prometheus-app-metrics-setup.md` | 10 | Prometheus integration. |
| `docs/infrastructure/vps-bootstrap-plan.md` | 8 | VPS bootstrap procedures. |
| `docs/infrastructure/vps-ai-sysadmin.md` | 8 | AI sysadmin guide. |
| `docs/infrastructure/vps-residue-policy.md` | 7 | VPS cleanup policy. |
| `docs/infrastructure/grafana-dashboards-setup.md` | 4 | Dashboard setup. |
| `docs/infrastructure/audit-prompts/02-container-health.md` | 13 | Audit prompt — references Coolify limits. |
| `docs/infrastructure/audit-prompts/01-full-system-audit.md` | * | Audit prompts series — check each. |
| `docs/infrastructure/audit-prompts/03-security-hardening.md` | * | " |
| `docs/infrastructure/audit-prompts/04-performance-bottleneck.md` | * | " |
| `docs/infrastructure/audit-prompts/05-observability-pipeline.md` | * | " |
| `docs/infrastructure/audit-prompts/06-backup-disaster-recovery.md` | * | " |
| `docs/infrastructure/audit-prompts/07-pre-production-checklist.md` | * | " |
| `docs/infrastructure/audit-prompts/08-hardening-remediation.md` | * | " |
| `docs/infrastructure/audit-prompts/README.md` | * | " |

#### 2.1.6 Root docs (LOW)

| File | Remaining | Notes |
|---|---:|---|
| `INDEX.md` | 21 | Tree listings + brief descriptions. Most refs are file-path mentions (`deployer_coolify.py`, `coolify-ssh-permissions.*`) which are real files — keep. Descriptive text ("# Coolify deployment API client") should mark as legacy. |
| `README.md` | 19 | Project README. Likely high-level description still mentions Coolify deploy. |
| `docs/preplans/README.md` | 1 | Quick check. |

### 2.2 Tier C — Active source code with stale comments/docstrings

| File | Remaining | Notes |
|---|---:|---|
| `src/fabrik/cli.py` | 55 | `fabrik logs` docstring (l713, l771), various command help text. The legacy commands (`status`, `logs`, `reconcile-all`) still use Coolify API. Help text should clarify these are legacy paths. |
| `src/fabrik/scaffold.py` | 40 | Env-var template comments (l999, l1600, l2813) — "Set via Coolify env vars on deploy" should be "Set via project `/opt/<name>/.env` (managed by `fabrik apply`)". Plus other comments. |
| `src/fabrik/spec_generator.py` | 15 | Error message + comment about Coolify inline-compose endpoint. The `Project types deployed via Coolify` comment (l46) needs updating to reflect SSH+Compose. |
| `src/fabrik/spec_loader.py` | * (low) | "pre-Fabrik-orchestrator via Coolify GUI" docstring (l41). Update. |
| `src/fabrik/__init__.py` | 1 | Module docstring "via Coolify" (l5). Replace. |
| `src/fabrik/drivers/redis.py` | 1 | Comment "via Coolify env-var update + redeploy" (l39). Update. |
| `src/fabrik/portability.py` | 52 | Strips `coolify_uuid` from state files. Mostly intentional (legacy state compat). Just verify docstrings describe current behavior. |
| `scripts/final_gate.py` | * | Comment about "Coolify's auto-inject" (l652). Update. |
| `scripts/enforcement/check_traefik_labels.py` | * | Docstring (l8) — Coolify auto-inject reference. Update. |
| `scripts/vps_apply_limits.sh` | * | Comment (l17) — Coolify API PATCH reference. Update for SSH+Compose model. |

### 2.3 Keep as-is — Intentional Coolify content

#### 2.3.1 Source code (legacy modules, still imported)

These describe Coolify-specific behavior in legacy code that is still imported by some still-working CLI commands (`status`, `logs`, `reconcile-all` for legacy services).

- `src/fabrik/orchestrator/deployer_coolify.py` (112 mentions) — the **archived legacy deployer**. Intentional.
- `src/fabrik/drivers/coolify.py` (58) — Coolify v4 API client, still used by legacy CLI paths.
- `src/fabrik/provisioner.py` (60) — legacy provisioner.
- `src/fabrik/orchestrator/coolify_alias.py` (28) — Coolify single-image alias-watcher helper (Coolify-platform-specific).
- `src/fabrik/drivers/compose_updater.py` (33) — likely Coolify-specific compose mutation.
- `src/fabrik/orchestrator/rollback.py` (22) — handles `coolify` resource-type rollback for legacy state.
- `src/fabrik/health_app.py`, `deploy.py`, `deploy_router.py` — verify each, mark explicit legacy where unclear.

#### 2.3.2 Intentional Coolify documentation

- `docs/infrastructure/archive/coolify-migration.md` (the migration plan itself)
- `docs/infrastructure/archive/coolify-api-reference.md`, `coolify-openapi.json`, `coolify-services-compose-dump.txt`, `coolify-stable-aliases.md`
- `scripts/migrate-authelia-to-coolify.sh`
- `scripts/coolify-ssh-permissions.{sh,service,timer}` (still active on VPS for Coolify-managed services)

#### 2.3.3 The `coolify` Docker network name

Used everywhere. **Intentionally retained** per deploy invariants. Per the deploy-invariants memory: *"The coolify network name is a historical artifact, cosmetic."* All references to `networks: coolify`, `coolify net`, `external: coolify` etc. **stay.**

### 2.4 Auto-generated — never edit by hand

These regenerate from live VPS state. Editing manually is wasted work; regenerate when state changes. Coolify is still on the VPS, so they'll keep mentioning it (correctly).

- `docs/infrastructure/vps-status.md` — generated by `update_vps_docs.py`
- `docs/infrastructure/vps-complete-inventory.md` — generated by `generate_vps_inventory.py`
- `PORTS.md` AUTO-GENERATED block — generated by `sync_projects.py`
- `docs/BUSINESS_MODEL.md` AUTO-GENERATED:PROJECTS block — same
- `data/projects.yaml` — generated; carries `coolify_uuid` / `coolify_app_name` for legacy services
- `docs/infrastructure/vps-urls.md` — auto-refreshed by sync

### 2.5 Historical — leave intact

These were excluded from the original scope and remain so. Coolify references in these files are historically accurate.

- `docs/development/plans/previously-planned-fabrik-phases/**`
- `docs/development/plans/fabrik workflow missing items/**`
- `docs/development/plans/archived/**`
- `docs/development/plans/issues/2026-03-15-deployment-log.md`
- `docs/development/plans/youtube/00-vision.md`
- `docs/development/plans/2026-05-27-coolify-migration.md` (the migration plan)
- `docs/development/plans/2026-05-28-ssh-deployer.md` (the SSH deployer migration plan)
- `docs/superpowers/specs/**`
- `docs/LESSONS_LEARNT*.md`
- `docs/archive/**`
- `docs/reference/DOC_REVIEW_*.md` (historical doc reviews)
- `docs/reference/project-registry.md` (deprecated in favor of BUSINESS_MODEL.md)
- VPS state captures (`docs/infrastructure/vps-captured-state-*.txt`, `docs/reference/vps-*.txt`)

---

## 3. Execution Plan

### 3.1 Batches (recommended order)

Each batch is a single PR-sized unit. Designed for "iterate-to-converge" sessions.

| Batch | Scope | Files | Effort |
|---|---|---|---|
| **B-1** | Top user-facing | `CONFIGURATION.md`, `FEATURES.md`, `EXTERNAL_SYSTEMS.md`, `README.md`, `INDEX.md` (descriptions only) | 1 session |
| **B-2** | Operations | `operations/deployment.md`, `backup-strategy.md`, `disaster-recovery.md`, `fabrik-lifecycle.md`, `vps-urls.md` | 1 session |
| **B-3** | Heavy references | `reference/stack.md`, `reference/architecture.md`, `reference/provisioner.md`, `reference/health-monitoring.md` | 1–2 sessions (stack.md alone is heavy) |
| **B-4** | Light references | All remaining `reference/*.md` | 1 session |
| **B-5** | Workflows | `workflows/FABRIK_SCAFFOLD_WORKFLOW.md` + others | 1 session |
| **B-6** | Infrastructure | All `infrastructure/*.md` + audit-prompts series | 1 session |
| **B-7** | Verification pass | Re-scan all Tier B files; verify zero stale claims; verify all intentional refs intact | 0.5 session |
| **C-1** | Source comments | `cli.py`, `scaffold.py`, `spec_generator.py`, `spec_loader.py`, `__init__.py`, `drivers/redis.py`, scripts | 1 session |
| **C-2** | Source verification | Re-scan all source; verify only legacy-marked refs remain in non-legacy files | 0.5 session |

Total: **~7–9 sessions** to fully converge.

### 3.2 Per-file workflow

For each file:

1. **Read** the file (or relevant section if large).
2. **Categorize each Coolify mention** as Fix / Keep / Keep-mark-legacy.
3. **Apply Edits** surgically (precise old_string/new_string).
4. **Verify** with `grep -ni "coolify" <file>` — every remaining match should be intentional.
5. **Note** in the batch summary which refs were kept and why.

### 3.3 Convergence criteria

Per-file done when:

- Zero stale deploy-mechanism claims (no "deploys via Coolify API", "Coolify v4 quirks", etc.).
- Every remaining "Coolify" reference is either:
  - Documenting the still-installed Coolify service on the VPS, OR
  - Documenting legacy code paths (marked as such), OR
  - The `coolify` Docker network name (intentional artifact), OR
  - Auto-generated content.

Repo-wide done when all batches B-1 through C-2 are complete + the verification pass shows convergence per the criteria above.

### 3.4 What NOT to do

- ❌ **No bulk sed across files** (was tried; created false positives — see commit `6ae18ab` and the partial revert). Per-file judgment is required.
- ❌ **No edits to auto-generated files.** They regenerate.
- ❌ **No edits to historical plans/specs/archives.** They're snapshots.
- ❌ **No renaming the `coolify` Docker network.** It's intentional.
- ❌ **No deleting `deployer_coolify.py` / `drivers/coolify.py` etc.** Still referenced by legacy CLI commands.

---

## 4. Open Questions for the Owner

These need decisions before some batches can proceed:

1. **Should the `coolify.alias` spec field be deprecated** (`CONFIGURATION.md` l300–316)? It's still functionally relevant for Gatus monitoring of single-image Coolify Applications, but fabrik doesn't deploy via Coolify anymore. Keep the docs as-is, or mark as "legacy Coolify-only feature"?
2. **Coolify-era legacy CLI commands** (`fabrik status`, `fabrik logs`, `fabrik reconcile-all`) — should they be (a) kept with "(legacy)" annotation, (b) rewritten for the SSH+Compose model, or (c) removed entirely?
3. **`docs/reference/project-registry.md`** — already marked deprecated, but it's still referenced in places. Delete? Repoint everything to BUSINESS_MODEL.md?
4. **`docs/infrastructure/archive/coolify-migration.md`** — keep as historical record? Move to `docs/archive/`?

---

## 5. Quick Reference

- **Residue scan command:** `grep -rln -i "coolify" docs/ src/ scripts/ AGENTS.md CLAUDE.md INDEX.md README.md | grep -v archive | grep -v previously-planned`
- **Intentional-mention exclusions:** see §2.3 / §2.4 / §2.5
- **Pre-flight before any edit:** read the file, decide Fix / Keep / Keep-mark-legacy per mention, never bulk-sed.

---

**Status:** plan written 2026-05-30; commit `6ae18ab` represents Tier A complete + Tier B partial.
**Next:** start Batch B-1 when ready.
