# Epic — Fleet CI + deploy debt (phantom imports & lint) + project-type / deployability audit

**Status:** OPEN · **Opened:** 2026-07-14 · **Owner:** hub (fabrik), execution delegated per-repo

---

## PART 0 — Project type determination & deployability (2026-07-14)

The 11 canonical scaffold types: `chrome-extension · desktop-app · docusaurus · file-api · file-worker ·
mobile-app · node-api · python-api · python-api-gpu · saas-skeleton · static-site · wordpress`.

**`project.yaml::type` cannot be trusted** — it is wrong or invalid in several repos. Types below are the
**verified** ones (from README + entrypoint + dependency signals), not the declared ones.

### ⛔ BLOCKER — 21 repos have `compose.yaml` + `Dockerfile` but NO hub spec

`fabrik apply` acts on `specs/services/<id>.yaml`. **No spec = cannot deploy, at all.** This — not lint — is
the real deployment blocker. Repos with Docker artifacts and no spec:
`apidoccreator · brand-identiy-creator · candle · captcha · ComplianceOps · email-reader · exam-coach ·
gmailaccountcreator · image-broker · image-generation · iterative_image_editor · llm_batch_processor ·
marketing-argumant-generator · proxy · Reference_Creator · rnfinal · supplement-tracker-advisor ·
trade-intelligence · ugc · web-scraper · wpf`

### ✅ OPERATOR RULINGS (2026-07-14)

| Repo | Ruling | Action |
|---|---|---|
| **meb** | **Will become a mobile app WITH a backend.** APK first, Play Store later. So the declared `mobile-app` type is right *aspirationally* — but today the repo holds a **Python Anki-deck generator** (4,459 LOC, `build.py`/`card_text.py`, no Docker). | Keep `mobile-app`. Needs a **backend** service added (which *will* need a Dockerfile+compose+hub spec). **Fix the 3 phantom imports regardless** — they break it today. Its agent owns this (280 modified files in flight). |
| **tojlo-mail** | **VERIFIED: not an Outlook add-in.** No `manifest.xml` exists anywhere (that is how Office add-ins declare themselves). It is a **Next.js SaaS web app that integrates Outlook via API** (`apps/web/utils/outlook`, `app/api/outlook/watch/*` — OAuth + mail-watch routes), forked from an AI email-assistant. **It DOES have a backend**: Next.js API routes + `apps/worker` + `db/` + `docker/` + `ai-document-service` + 2 image-proxy services. | `type: saas` ❌ → **`saas-skeleton`**. It already has a hub spec + compose → deploys as one stack. No extra specs needed. |
| **obsidian-agents** · **rn-kit-sandbox** · **rnfinal** | **OUT OF SCOPE — sandboxes/experiments.** | No hub spec, no Docker work, no deployment. Excluded from all future audits. |
| **8 empty scaffolds** | **Will be scaffolded properly.** Operator is being asked one-by-one what each should be. | See "Scaffold queue" below. |

### 📋 Scaffold queue — 8 empty repos (zero product code; 410/432-LOC boilerplate fingerprint, untouched 3 weeks)

**All 8 adjudicated by the operator (2026-07-14).** Every one currently declares `python-api` — 4 are wrong and
need a **re-scaffold under the correct type**.

| Repo | Declared | ✅ RULED type | Action | Done |
|---|---|---|---|---|
| `ComplianceOps` | `python-api` | **`saas-skeleton`** | **Re-scaffold** (type change). "Async compliance platform for HealthTech startups" — customer-facing, UI + auth. | ☐ |
| `exam-coach` | `python-api` | **`saas-skeleton`** | **Re-scaffold** (type change). Will *also* become a mobile app later — **SaaS first**. | ☐ |
| `gmailaccountcreator` | `python-api` | **`file-worker`** | **Re-scaffold** (type change). Background automation worker, no HTTP surface. | ☐ |
| `supplement-tracker-advisor` | `python-api` | **`mobile-app`** | **Re-scaffold** (type change). Phone app. | ☐ |
| `marketing-argumant-generator` | `python-api` | **`python-api`** ✓ | Type already correct — just needs building out. | ☐ |
| `Reference_Creator` | `python-api` | **`python-api`** ✓ | Type already correct — just needs building out. Complements `fabrik-citation-verifier`. | ☐ |
| `ugc` | `python-api` | **🗑️ DELETE** | Duplicate of `web-scraper` (which has real code). Kill the repo. | ☐ |
| `image-generation` | `python-api` | **⏸️ LEAVE AS-IS** | Duplicate — operator will **merge it into `iterative_image_editor`** himself. Hub takes no action. | ☐ |

### ✅ SCAFFOLD WORK — DONE (2026-07-14, by the hub)

**Nothing was deleted.** Every old dir was moved to `/opt/archived/` (policy: archive, never delete). All 5 had
**no GitHub remote** and only 5–6 boilerplate commits, so nothing of value was lost.

| Old | → New | Type | Spec | GitHub |
|---|---|---|---|---|
| `ComplianceOps` | **`compliance-ops`** *(renamed — scaffolder enforces kebab-case)* | `saas-skeleton` +db | ✅ `source=git` | `mobasak/compliance-ops` |
| `exam-coach` | `exam-coach` | `saas-skeleton` +db | ✅ `source=git` | `mobasak/exam-coach` |
| `gmailaccountcreator` | **`gmail-account-creator`** *(renamed — readability)* | `file-worker` +db | ✅ `source=git` | `mobasak/gmail-account-creator` |
| `supplement-tracker-advisor` | same | `mobile-app` | ✅ `source=git` | `mobasak/supplement-tracker-advisor` |
| `ugc` | **archived** (duplicate of `web-scraper`) | — | — | — |

Archived at: `/opt/archived/{ugc-duplicate-of-web-scraper,ComplianceOps-pre-rescaffold-python-api,exam-coach-pre-rescaffold-python-api,gmailaccountcreator-pre-rescaffold-python-api,supplement-tracker-advisor-pre-rescaffold-python-api}-20260714`

**Note:** `mobile-app` has no deploy template (expected — mobile ships via EAS build, not Docker).

**⚠️ Naming violations still latent:** `Reference_Creator` (capitals + underscore) and `iterative_image_editor`
(underscore) both violate the kebab-case rule the scaffolder enforces. They'd need renaming if ever re-scaffolded.

### ✅ Type verified correct (python-api / FastAPI services, real code)

`apidoccreator` · `brand-identiy-creator` · `candle` · `captcha` · `email-reader` · `fabrik-citation-verifier` ·
`fabrik-claim-validator` · `image-broker` · `iterative_image_editor` · `job-agent` · `llm_batch_processor` ·
`longephedia-vault` · `proposal-creator` · `proxy` · `seo` · `site-provisioner` · `trade-intelligence` ·
`trading-core` · `triggered-content-orchestration` · `tryton-crm` · `web-scraper` · `whatsapp-agent` · `wpf`
· `calendar-orchestration-engine` (node-api) · `youtube` (file-worker) · `transdoc` / `test-saas-platform` /
`test-saas-scaffold` (saas-skeleton)

### Not projects (infra/library — no type expected)

`fabrik-lib` (shared module library — vendored, never deployed) · `fabrik-dr-store` (DR credential store)

---

## PART 1 — CI + deploy debt (original scope)

## Why this exists

Two independent defects made `final_gate` go green while CI and the deployed container broke. Both are
"the local gate models the wrong universe":

| Axis | `final_gate` sees | CI / deploy sees | Bug it hides |
|---|---|---|---|
| **Content** | the working tree — incl. untracked/**gitignored** files on disk | a **clean checkout** (tracked only) | **phantom imports** |
| **Scope** | only the files **the diff touched** | the **whole repo** | **accumulated lint debt** |

**Axis A is FIXED** (`scripts/enforcement/check_imports_resolvable.py`, Tier-1 showstopper, wired into
`final_gate.py`, synced to all 47 projects, in the scaffold for new ones — commits `fe3a3f07`, `bf59943a`).
**Axis B is NOT built** — see the Backlog.

## ⚠️ Execution rule — do NOT sweep these from the hub

**Operator decision (2026-07-14): the git dirt is cleared by EACH REPO'S OWN AGENT. The hub touches nothing
cross-repo.** A hub-side sweep would risk destroying uncommitted work — including via the governance
pre-commit hook, which stashes/restores unstaged files and can silently revert a sibling's whole uncommitted
batch to HEAD. Cross-repo editing is a CLAUDE.md HARD STOP.

### What the "git dirt" actually is (surveyed 2026-07-14)

It is **mostly NOT agent WIP — it is sync churn**, and that is a **hub bug**:

| Modified file | Repos affected | What it is |
|---|---|---|
| `.gitignore` | **41** | The sync **rewrites** it (patches in the generated "Fabrik-synced block"). Diff is real (e.g. captcha: −72/+29). |
| `docs/workflows/kilo-consult-workflow.md` | **28** | Another **tracked** file the sync overwrites. |

`sync_enforcement_to_projects.py` writes to **tracked** files, so **every project is left permanently dirty
after every sync**. Genuine agent WIP is confined to ~5 repos (`meb` 280, `rn-kit-sandbox` 46,
`site-provisioner` 16, `tojlo-mail` 13, plus a few real source files).

**→ Backlog item (hub):** make the sync idempotent w.r.t. tracked files — either it must not rewrite tracked
files, or it must commit what it rewrites. Until fixed, the dirt returns on the next sync and any per-repo
cleanup is Sisyphean.

**Per-repo agent task (all 41):** commit the sync churn (`.gitignore`, `docs/workflows/kilo-consult-workflow.md`)
— it is machine-generated content, zero data-loss risk — and commit or stash your own WIP deliberately.

---

## 🔴 P0 — Deploy-breaking (ships broken; no CI, so nothing alerts)

| Repo | Finding | Action | Done |
|---|---|---|---|
| **meb** | **3 phantom imports** — `src/export_app_data.py` imports `card_text` + `image_bg`, which resolve ONLY via **gitignored** `src/card_text.py` / `src/image_bg.py`. Container will `ImportError`. Has **no CI workflow**, so it never surfaced. | `git add` them if they're real source, else fix `.gitignore`. The new gate now **blocks** this repo (`exit=1`) — warn its agent first: it has 280 modified files in flight. | ☐ |

## 🔴 P0 — CI is RED right now (their workflow runs `ruff check .`)

| Repo | Finding | Action | Done |
|---|---|---|---|
| **tryton-crm** | **47 ruff errors** repo-wide. *This is the CI email.* Nothing to do with imports (its import check passes). | `ruff check . --fix`, then fix the rest by hand until `ruff check .` is clean. | ☐ |
| **whatsapp-agent** | **2 ruff errors**; `ci.yml` runs `ruff check .` | `ruff check . --fix` | ☐ |

## 🟡 P1 — Big debt, CI does *not* gate ruff (latent, not currently red)

| Repo | Ruff errors | Note | Done |
|---|---|---|---|
| **youtube** | **1,952** | CI runs pytest only | ☐ |
| **proxy** | 203 | `validate.yml` doesn't gate ruff | ☐ |
| **fabrik** (hub) | 119 | its own `ci.yml` doesn't gate ruff either | ☐ |

## ⚪ P2 — No CI; latent debt that will block the future zero-tolerance gate

`llm_batch_processor` **1,314** · `iterative_image_editor` **493** · `seo` **275** · `proposal-creator` **141** ·
`site-provisioner` **133** · `email-reader` **94** · `calendar-orchestration-engine` 49 · `candle` 48 ·
`image-broker` 46 · `apidoccreator` 45 · `triggered-content-orchestration` 40 · `captcha` 27 ·
`brand-identiy-creator` 18 · `wpf` 16 · `fabrik-claim-validator` 5 · `fabrik-citation-verifier` 4 ·
`ComplianceOps` / `exam-coach` / `gmailaccountcreator` / `image-generation` / `job-agent` /
`marketing-argumant-generator` / `Reference_Creator` / `rnfinal` / `supplement-tracker-advisor` / `ugc` 3 each ·
`whatsapp-agent` 2 · `test-saas-scaffold` / `tojlo-mail` / `transdoc` 1 each

**Fleet total: ~5,000 ruff errors across 34 repos.**

## ✅ Done

| Repo | Outcome |
|---|---|
| **trade-intelligence** | Diagnosed *and fixed by its own agent*: vendored `web_tools` into **tracked** source, committed `95c7a41`. Phantom imports 0, ruff 0. Its `scripts/check_phantom_imports.py` was **promoted into the hub** and synced back wired into `final_gate` — it should now **delete its local copy**. |
| **hub** | `check_imports_resolvable.py` built, hardened (closed the relative-import + untracked-not-just-ignored holes; killed a frozen-stdlib and a synced-dir cry-wolf), 6 regression tests, wired into `final_gate` Tier 1, synced to 47 projects + scaffold. |

---

## Backlog — Axis B: the lint ratchet (NOT built)

Repo-wide lint is invisible to `final_gate` because it lints **only the diff** (`final_gate.py:429`) — which is
deliberate (don't red the gate on pre-existing or Fabrik-synced lines the change never touched, and in a project
is *forbidden* to edit). Correct for the auto-**fixer**, wrong for a CI-parity **assertion**.

**Proposed mechanism** (lands safely on all 47 today, no cross-repo editing):
1. Commit a per-repo **lint baseline** (current repo-wide error count).
2. Gate **FAILS if the count RISES** → no agent can ever add a new lint error again.
3. When a repo's baseline hits **0**, the gate **auto-locks it to zero-tolerance** permanently.

Zero-tolerance then arrives **per repo, as each is cleaned** — no flag day, no mass breakage.

## Also outstanding

- **fabrik-lib**: add a `DEV-TIME ONLY — importing this from src/ or tests/ breaks CI and deploy` banner to
  `subagents/__init__.py` (canonical source; the hub's `libs/subagents` is a re-vendored copy and would be
  overwritten). Split `web_tools` into a standalone **vendorable** module so products can copy it into tracked
  source instead of reaching into a gitignored dir.
- **CI coverage gap**: most repos have **no CI workflow at all** — which is why `meb` shipped broken silently.
  Worth deciding whether every deployed project should get a minimal `ci.yml`.
