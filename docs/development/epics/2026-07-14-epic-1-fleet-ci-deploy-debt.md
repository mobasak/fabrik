# Epic — Fleet CI + deploy debt (phantom imports & lint)

**Status:** OPEN · **Opened:** 2026-07-14 · **Owner:** hub (fabrik), execution delegated per-repo

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

Every repo has **uncommitted agent WIP** (`meb` alone: 280 modified + 518 untracked). A hub-side sweep would
risk destroying it — including via the governance pre-commit hook, which stashes/restores unstaged files and
can silently revert a sibling's whole uncommitted batch to HEAD. **Each fix below is done by that repo's own
agent, in its own tree.** Cross-repo editing is a CLAUDE.md HARD STOP.

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
