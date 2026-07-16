# Epic — Fleet CI + deploy debt (phantom imports & lint) + project-type / deployability audit

**Status:** OPEN · **Opened:** 2026-07-14 · **Owner:** hub (fabrik), execution delegated per-repo

---

## PART 0 — Project type determination & deployability (2026-07-14)

The 11 canonical scaffold types: `chrome-extension · desktop-app · docusaurus · file-api · file-worker ·
mobile-app · node-api · python-api · python-api-gpu · saas-skeleton · static-site · wordpress`.

**`project.yaml::type` cannot be trusted** — it is wrong or invalid in several repos. Types below are the
**verified** ones (from README + entrypoint + dependency signals), not the declared ones.

### ⛔ BLOCKER — repos with `compose.yaml` + `Dockerfile` but NO hub spec

`fabrik apply` acts on `specs/services/<id>.yaml`. **No spec = cannot deploy, at all.** This — not lint — is
the real deployment blocker. **17 such repos remain** (down from 21: `compliance-ops` / `exam-coach` /
`gmail-account-creator` got specs via the re-scaffold; `ugc` was archived). Disposition (2026-07-14):

**🟢 12 real services — SPECS GENERATED for 10 (2026-07-14, `5caaa23b`).** Produced via the scaffold's own
`generate_and_save_spec` (real source/branch + secrets/env read from each `.env.example`, resources, health) +
three shape flags corrected from authoritative signals (active `.env.example` vars + real `/metrics`):
`needs_database`, `needs_cache`, `exposes_metrics`. Judgment flags left conservative for operator review.
Nothing auto-deploys — first-pass specs to verify before `fabrik apply`.
  - **Deploy-ready** (`source=git`): `wpf` · `proxy` · `image-broker` · `captcha`.
  - **Template-source** (valid spec, need a GitHub remote before deploy): `candle` · `email-reader`.
  - **DB drafts** (`*.yaml.draft` — a not-yet-deployed project's local `.env` uses a dev DB name, so the
    blocking `check_spec_db_match` trips until DATABASE_URL is repointed; rename `.draft`→`.yaml` at deploy):
    `trade-intelligence` · `brand-identiy-creator` · `apidoccreator` · `web-scraper`.
  - **Not generated (2) — blocked on rename:** `llm_batch_processor` + `iterative_image_editor` have UNDERSCORE
    names → invalid spec id (must be kebab-case). Rename the repo first, then generate.

**🟡 2 not-for-Docker-deploy** (correct their absence of a hub spec — they don't deploy as containers):
`rnfinal` (mobile-app → ships via EAS build, not Docker) · `rn-kit-sandbox` (sandbox — out of scope).

**⚪ 3 empty scaffolds** (410–432-LOC boilerplate, no product code → nothing to deploy yet):
`image-generation` (operator is merging it into `iterative_image_editor`) · `Reference_Creator` ·
`marketing-argumant-generator`. These get a spec only once they have real code.

The Docker artifacts on the 2 mobile/sandbox + 3 empty repos are scaffold leftovers; leaving them specless is
correct, not a gap.

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

**Axis A is FIXED + HARDENED** (`scripts/enforcement/check_imports_resolvable.py`, Tier-1 showstopper, wired
into `final_gate.py`, synced to all 47 projects, in the scaffold for new ones). Built `fe3a3f07`, `bf59943a`;
then a full `/fabrik-review` (2026-07-14, passes 1–4) surfaced **35 findings** in my own code and drove them
to FIXED/REFUTED — commits `02e3a839`, `9ef037a1`, `d8eec3d2`, `4f651d65`. What the review caught: the check
`find_spec`-imported parent packages (crashed on a raising `__init__.py`; 16 s→2.6 s once replaced with pure
`sys.path` resolution), several fail-open paths (git-failure → "OK, 0 checked"), false-negatives (a phantom
inside a plain `if:`; anything resolving *outside* the repo, which caught a real one in `wpf`), false-positives
(`.so` build artifacts, git submodules, frozen stdlib) now guarded + an `# phantom-ok` escape hatch, and three
**lying tests** (validated a copy of the logic; a regression test that didn't test its own fix). Fleet sweep:
47 projects, **0 crashes, 0 false positives, 1 true positive** (`wpf`). **Axis B is NOT built** — see the Backlog.

## ⚠️ Execution rule — do NOT sweep these from the hub

**Operator decision (2026-07-14): the git dirt is cleared by EACH REPO'S OWN AGENT. The hub touches nothing
cross-repo.** A hub-side sweep would risk destroying uncommitted work — including via the governance
pre-commit hook, which stashes/restores unstaged files and can silently revert a sibling's whole uncommitted
batch to HEAD. Cross-repo editing is a CLAUDE.md HARD STOP.

### What the "git dirt" actually is (surveyed 2026-07-14; re-verified after the sync fix)

Most of it is **not agent WIP — it is the sync's managed `.gitignore` block** being kept current (~38 repos
have a dirty `.gitignore`). That is **tracked churn each repo's agent simply commits** — machine-generated, no
data-loss risk. (The earlier claim that the sync also overwrites `docs/workflows/kilo-consult-workflow.md` was
**wrong** — that file is not in the synced set and does not exist in the hub; its modification in ~28 repos has
another origin, unrelated to this sync.) Genuine agent WIP is confined to ~5 repos (`meb`, `rn-kit-sandbox`,
`site-provisioner`, `tojlo-mail`, plus a few real source files).

**✅ The one real HUB BUG here is FIXED (commits `8f79f6f6`, `02e3a839`).** When a project's `.gitignore` was
**empty**, the sync produced a `.gitignore` containing *only* the Fabrik block — which does not ignore `.env`
/ `.venv/` / `__pycache__/`, leaving the repo one `git add -A` from committing secrets (found live in 3 repos:
`captcha`, `fabrik-dr-store`, `Reference_Creator`; nothing had actually leaked). The sync now enforces a
git-authoritative, fail-closed **safety floor** that self-heals a damaged repo, and **fails the run** (non-zero
exit) if a repair does not hold. **Re-verified 2026-07-14: 0 repos expose `.env`** (was 3).

**Per-repo agent task:** commit the `.gitignore` block churn (machine-generated, zero-risk) and commit or stash
your own WIP deliberately.

---

## 🔴 P0 — Deploy-breaking (ships broken; no CI, so nothing alerts)

| Repo | Finding | Action | Done |
|---|---|---|---|
| ~~**meb**~~ | ~~3 phantom imports (`src/export_app_data.py` → gitignored `card_text` / `image_bg`)~~ | **✅ FIXED by meb's own agent** (`738ede2`): both files are now TRACKED; the gate passes (0 errors) — re-verified 2026-07-14. Residual: ~280 uncommitted files still in its tree (its agent's to land). | ✅ |

## 🔴 P0 — CI is RED right now (their workflow runs `ruff check .`)

| Repo | Finding | Action | Done |
|---|---|---|---|
| ~~**tryton-crm**~~ | ~~**47 ruff errors** repo-wide. *This is the CI email.*~~ | **✅ FIXED by its own agent** — re-verified **0 ruff** 2026-07-15. | ✅ |
| ~~**whatsapp-agent**~~ | ~~**2 ruff errors**~~ | **✅ FIXED by its own agent** — re-verified **0 ruff** 2026-07-15. | ✅ |

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
| **hub — Axis A gate** | `check_imports_resolvable.py` built, then hardened through a full 4-pass `/fabrik-review` (35 findings, incl. 3 crash paths + 4 fail-opens + 3 lying tests). Pure `sys.path` resolution (no imports; 16 s→2.6 s), git-authoritative + fail-closed, `# phantom-ok` escape hatch. **29 import-gate tests** (4 provably fail on revert) + the sync suite. Wired into `final_gate` Tier 1, synced to all 47 (md5-identical) + scaffold. Fleet sweep: 0 crashes, 0 FPs, 1 TP (`wpf`). |
| **hub — sync `.env` bug** | `sync_enforcement_to_projects.py` could strip a project's `.gitignore` to the Fabrik block, un-ignoring `.env` (3 repos, no leak). Fixed with a git-authoritative fail-closed safety floor that self-heals + fails the run if a repair doesn't hold (`8f79f6f6`, `02e3a839`). **0 repos expose `.env`** (was 3). |
| **hub — scaffold cleanup** | 4 mis-typed empty repos re-scaffolded under correct types (`compliance-ops`/`exam-coach` saas-skeleton, `gmail-account-creator` file-worker, `supplement-tracker-advisor` mobile-app); `ugc` archived as a `web-scraper` duplicate. Nothing deleted — all in `/opt/archived/`. |

---

## ✅ Axis B — the lint ratchet (BUILT 2026-07-14, `483ac729`)

Repo-wide lint was invisible to `final_gate` (it lints **only the diff**) — deliberate for the auto-fixer, wrong
for a CI-parity assertion. Now `scripts/enforcement/check_lint_ratchet.py` (Tier-1, synced to all 47, wired into
`final_gate`): first run **seeds** a per-repo baseline (`.fabrik/lint-baseline.json`, tracked) + passes; a
**rise FAILS**; a **drop tightens** the baseline (it can only shrink); at **0 it locks** to zero-tolerance.
`--check` (CI) blocks a rise without rewriting. Lands safely — the seed run never blocks (fleet dry-run: 43
repos, 0 crashes, 0 blocked). Zero-tolerance arrives **per repo, as each is cleaned** — no flag-day. Hub
baseline seeded at 119. 7 regression tests. So the ~5,045-error fleet debt is now *ratcheted*: it can only ever
shrink, and no agent can add to it.

## Also outstanding

- **fabrik-lib**: add a `DEV-TIME ONLY — importing this from src/ or tests/ breaks CI and deploy` banner to
  `subagents/__init__.py` (canonical source; the hub's `libs/subagents` is a re-vendored copy and would be
  overwritten). Split `web_tools` into a standalone **vendorable** module so products can copy it into tracked
  source instead of reaching into a gitignored dir.
- **CI coverage gap**: most repos have **no CI workflow at all** — which is why `meb` shipped broken silently.
  Worth deciding whether every deployed project should get a minimal `ci.yml`.
- **Retired `docs/workflows/kilo-consult-workflow.md` orphans** (superseded by the OpenRouter pool 2026-07-11;
  distributor archived). 7 **untracked** copies swept 2026-07-14. It remains **committed (tracked) in ~30
  repos** — a harmless dead file; each repo's agent can `git rm docs/workflows/kilo-consult-workflow.md` when
  convenient (a real tracked change, so not swept from the hub). Root confirmed: the project `.gitignore`
  block is generated from the synced manifest, so **every governance file is auto-ignored and cannot drift**;
  this orphan is unignored precisely because it was retired *out* of the manifest.

---

## PART 2 — 2026-07-15 additions (CI-failure emails)

### ✅ Broken `stale.yml` GitHub Action — FIXED

The "Mark stale issues and pull requests" workflow failed on every run (~8–10 s) on `supplement-tracker-advisor`
+ `rnfulltest`. Root cause: the **mobile-app scaffold template** shipped `.github/workflows/stale.yml` on
`actions/stale@v1` (Node 12 — current runners hard-fail deprecated-Node actions) with `permissions:` granting
only `pull-requests: write` while the job marks *issues* stale (needs `issues: write` too). It had **never**
worked; it was the only scaffold type carrying a stale bot (vestigial RN boilerplate).

- **Template:** removed from `templates/mobile-app/.github/workflows/stale.yml` (`f521c3e2`) → future scaffolds clean.
- **Live repos:** deleted `stale.yml` on both remotes via `gh` (`8bb5860d`, `46b1715`); verified 404.
- **Fleet:** authoritative scan = **0/40** repos still carry it (an earlier "39 repos" reading was a scan bug —
  `gh api --jq .sha` emits literal `null` on a 404). Only the two mobile-app scaffolds ever had it.

### ✅ Default branch = `mobasak/<name>` — INVESTIGATED, non-issue, guidance corrected

~15 recently-scaffolded repos have their default branch named `mobasak/<slug>` (not `main`/`master`); a few show
older names (`trade-intelligence` → `mobasak/trading-intelligence`). Source: **intentional** —
`scaffold.py:1366` does `branch_name = f"mobasak/{name}"` + `git checkout -b`, and `--github-create` pushes it as
the sole branch → it becomes the GitHub default.

**Verdict: functionally correct, left as-is.** The pipeline is internally consistent — `detect_git_source`
(`spec_generator.py:326`) records the real branch into the spec (`branch: mobasak/<name>`), and the deployer
(`deployer_ssh.py:446`) does `git clone -b {branch}` using that spec branch. Deploy/CI/watchdog all use the
default branch, so nothing breaks. Switching the scaffolder to `master` would create a three-way fleet split
(old `main`/`master` · these ~15 `mobasak/<name>` · future `master`) and the existing repos can't be easily
renamed → **more** inconsistency. The only real defect was two stale human-facing hint strings hardcoding
`git push -u origin main`; fixed to `git push -u origin HEAD` (branch-agnostic) in `spec_generator.py:437` +
`deployer_coolify.py:542`.

---

## PART 3 — CI backfill + fleet compliance status (2026-07-16)

### ✅ CI backfill — built, proven, debt-tolerant, DATA-SAFE
The complete scaffold audit found **31 deployable repos with no `ci.yml`** → broken code ships silently.
Built + shipped from the hub:
- **Debt-tolerant CI generator** (`ci_scaffold.py`): ruff is a **ratchet** (pinned `0.14.10`, `--exit-zero` count,
  fails only on a rise); install handles `requirements.txt` **and** `pyproject.toml` (`-e .`); pytest tolerates
  "no tests collected". `ci_local` binds a **free** Postgres port (no clash with the dev PG). Commits:
  `9019876e`, `a64d33d2`, `8d2f9069`. 18 tests.
- **`scripts/backfill_ci.py`** (`818fad2a`): writes CI + seeds `.fabrik/lint-baseline.json` at the current count
  so CI lands green; grounds `needs_database` from spec/`.env`. Dry-run default; never commits cross-repo.
- **`scratchpad/rollout_ci.py`** (data-safe, gated): per repo → apply → gate via `ci_local` in a **clean
  `git worktree` at HEAD** (no local `.env`/dirty-WIP leak) → **push only if green**; skips repos with
  pre-existing CI files, unpushed commits (`AHEAD`), or divergence; explicit-path commits + `--no-verify`.
- **Live + green:** `captcha`, `wpf` (real GitHub Actions `success`). 3 canary-caught bugs fixed pre-rollout.

### 🔴 The gating reality — fleet is entangled with LIVE agent work
The repos with debt are the repos with **live agents mid-work**: e.g. `iterative_image_editor` (2 plan-locks,
32 uncommitted incl. `src/`), `tojlo-mail` (7 locks), plus 8 repos `AHEAD` (unpushed commits). **The hub cannot
force-clean or push these without publishing/mixing another agent's work** (data loss). So compliance is
**sequenced**: agents land their WIP → hub finalizes on the quiesced tree → the gates hold the line.

### 📋 Fleet compliance punch-list — "done" = every remote+deployable row `CI:y · SPEC:yaml · DIRTY:0 · AHEAD:0 · KILO:-`
- **CI:** only `captcha·wpf·trade-intelligence·tryton-crm·whatsapp-agent` have it. Re-run `rollout_ci.py` →
  gates+pushes the ~6 safe DB repos (`calendar-orchestration-engine·compliance-ops·exam-coach·
  fabrik-claim-validator·gmail-account-creator·image-broker`). 16 no-remote repos need a remote first; 8
  `AHEAD` repos need their agent to push first.
- **Specs:** `llm_batch_processor`+`iterative_image_editor` need kebab-rename (BLOCKED — land their WIP first, or
  a rename destroys uncommitted work) → then generate specs.
- **Git hygiene (per-repo agent):** ~28 track the retired `kilo-consult-workflow.md` (`git rm`); `.gitignore`
  churn to commit; `tojlo-mail` type `saas`→`saas-skeleton`.

### 🎫 Open ticket — brand-identiy-creator gate cleanup (its agent's job; hub delivered the grounded triage)
65 mypy errors + 8 non-allowlisted root `.md`. Hub CANNOT land it (3 unpushed sibling commits + 6 uncommitted
files + behavior-changing docx fixes + sibling-WIP `logo_selection.py`/`questionnaire.py`). Per-error ticket
(safe-mechanical vs real-bug-needs-review vs sibling-WIP vs doc-moves) handed to its agent 2026-07-16.

---

## PART 4 — One-by-one fleet completion log (2026-07-16)

Per-project: scaffold complete → tree clean → real blockers fixed → CI gated green locally → GitHub remote
created + pushed → Actions run verified green (no failure emails). Agents finish their own in-flight work as we go.

| # | Project | Scaffold | Tree clean | Remote | CI green | Notes |
|---|---|---|---|---|---|---|
| 1 | `trading-core` | ✅ | ✅ | ✅ `mobasak/trading-core` | ✅ Actions success | **Fixed real bug:** `ctrader-open-api>=2.0.0` pin never existed (→ `>=0.9.0`); 13 tests |
| 2 | `longephedia-vault` | ✅ | ✅ | ✅ `mobasak/longephedia-vault` | ✅ Actions success | clean; 5 tests |
