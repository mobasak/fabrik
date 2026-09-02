# Plan 1 — Deployment Verification Contract (hub build)

Status: CONVERGED
Date: 2026-09-01
Spec: `docs/superpowers/specs/2026-09-01-deployment-verification-contract-design.md` (CONVERGED, `3a853851`)
Scope: **`/opt/fabrik` only** — 5 file groups. Routed feature-scale (spec defect 15: the epic verdict was wrong).

## Why this plan exists

I certified tryton-crm `DEPLOY CONFIRMED LIVE` with every check green while production held **0 of its
760 companies**. Liveness checks cannot fail on a missing product, because nothing declared what the
product should contain.

## File Scope (exhaustive — nothing outside this list)

| # | path | change |
|---|---|---|
| 1 | `commands/_sources/fabrik-deploy-checklist.md` | **NEW** — the project-side authoring command |
| 2 | `commands/_sources/fabrik-deploy-verify.md` | rewrite (216 lines today) |
| 3 | `src/fabrik/scaffold.py` + `templates/scaffold/**` | seeding, on the `:285` precedent |
| 4 | `tests/test_scaffold_deploy_contract.py` | **NEW** — Phase C guards (stub exits non-zero; docusaurus does not publish it) |
| 5 | `tests/test_command_corpus.py` (extend) | Phase A/B guards — the rendered commands carry the required sections |

**READ-ONLY inputs, not edited:** `src/fabrik/orchestrator/infrastructure.py` (`_REGISTRAR_ORDER`),
`docs/superpowers/specs/2026-09-01-deployment-verification-contract-design.md`.

⚠️ **FLEET-SYNCED SURFACE.** Every `commands/_sources/` edit distributes to 43 repos on commit. **Merge-time
render only** — never bare-render `assemble_commands.py` from a worktree (it PRUNES installed commands
absent from the current tree). `--check` is always safe.

## OUT OF SCOPE — named, not silently dropped

- **fabrik-lib `health-probe` enhancement** — filed `01M1ESR5KJW5Z1EE2YE55MBTE8`; **they** spec and
  implement. This plan builds against the **FALLBACK** (vendor `health-probe` as-is, diff in the parity
  runner) so **nothing blocks on their reply**. If they land the core change, the runner swaps to it.
- **Per-project onboarding (27 deployable repos)** — self-serve; each project's own agent runs the new
  command in its own repo. Cross-repo commits are a HARD STOP, so this is not mine to execute.

## Phase A — `/fabrik-deploy-verify` rewrite (the runner)

**Steps**
1. Add **Layer 1 Identity** as a new phase: deployed SHA vs tested SHA · `alembic current` vs `heads` ·
   image digest · lockfile hash. *(Measured absent today: `rev-parse` 0, `alembic` 0, `digest` 0.)*
2. Rewrite **Layer 3** so registrar rows are **derived from `infrastructure.py::_REGISTRAR_ORDER`**.
   ⚠️ **DECIDED, because the DRAFT was ambiguous and it changes File Scope:** derivation happens at
   **RUN time — the command instructs the agent to read `_REGISTRAR_ORDER` live** — NOT at render time.
   Render-time injection would need an `assemble_commands.py` change (not in scope) and would re-freeze
   the list into the rendered text, re-creating the hand-listed staleness this fixes. Run-time reading
   also means a registrar added tomorrow is covered with no corpus edit.
   The 10 today: postgres · redis · gatus · backrest · glitchtip · grafana · authelia · **meilisearch** ·
   prometheus · watchdog. ⚠️ **Precision, corrected by the re-derivation pass:** meilisearch DOES have a row
   in `commands/_sources/fabrik-deploy-verify.md` (1 mention, its registrar-obligation row). What lacked
   it was **my spec's Layer 3** — a hand-listed denominator that dropped a registrar the command already
   knew about. The fix is the same; the claim needed to be accurate.
3. Make **Phase 6 blocking and contract-driven** — remove the "first 3 rows" cap; consume the project's
   parity contract; `UNVERIFIABLE (<why>)` rows counted in the verdict.
4. Implement the **verdict algebra**: `UP` / `COMPLETE` / `RUNNING` separately-failable; `CONFIRMED`
   requires all three; **`UNVERIFIED`** when no contract exists; `not obligated` distinct from `not checked`.

**Gate:** `python scripts/final_gate.py --json` → success · `python commands/assemble_commands.py --check`
(temp-dir render, safe) · `grep -c _REGISTRAR_ORDER commands/_sources/fabrik-deploy-verify.md` ≥ 1.

**Evidence owed:** the 10 registrar names re-derived from `infrastructure.py` in-run; a `--check` render
showing no pruning.

## Phase B — the new authoring command

**Steps**
1. Author `commands/_sources/fabrik-deploy-checklist.md` — project-side. It walks the corpus and emits
   **the runnable command + expected result per row**, never prose.
2. Encode the **derived-denominator rules**: routes from the router's introspection · jobs from the live
   scheduler · env keys from `grep os.getenv` · services from **compose ∪ registrar-injected sidecars**
   (tryton-crm: compose declares 4, 5 run) · schema from `alembic heads`.
3. **Features cross-check** — features are prose and underivable, so: every derived route maps to a
   *Shipped* row and every *Shipped* row to a route; **either direction unmatched is a FINDING**.
4. Output `scripts/verify_prod_parity.py` + refresh `DEPLOYMENT.md`/`OPERATIONS.md` (D-065).
   ⚠️ **Derive from CODE + SPEC + DEV, never from PROD** — generating docs from deployed state launders
   drift into the declaration and destroys the only signal.
5. Add the NEXT-map entry so the command chains.

**Gate:** `final_gate --json` success · `assemble_commands.py --check` · the new command appears in the
NEXT map · a dry authoring run against tryton-crm produces a non-empty row set with its denominator stated.

## Phase C — scaffolder seeding (born compliant)

**Steps**
1. Seed on the **`scaffold.py:285` precedent** (`docs/data-contract-template.md` → `docs/data-contract.md`):
   `scripts/verify_prod_parity.py` stub that **EXITS NON-ZERO** (an unfilled contract fails closed),
   `specs/services/<id>.yaml` generated from `project.yaml` + `shape:`, and the `DEPLOYMENT.md` /
   `OPERATIONS.md` fleet-AI sections.
2. ⚠️ **Carry the `scaffold.py:293` docusaurus leak caveat** — seeding into `docs/` **publishes** it there.
   The parity contract names internal hosts, table names and row counts: seed outside `docs/` (`scripts/`
   already is) or add to the content-docs exclude.
3. Behavior test: scaffold each type in a temp dir; assert the stub exists, exits non-zero, and that a
   `docusaurus` scaffold does **not** publish it.

**Gate:** `final_gate --json` success · `timeout 900 pytest tests/test_scaffold*.py` green · the non-zero-exit and
docusaurus-exclusion assertions proven **red-on-revert**.

⚠️ **The 900s budget is MEASURED, not guessed** (2026-09-02, idle box, no concurrent runs):
`1 failed, 251 passed, 1 deselected in 560.49s (9m20s)`. 900s leaves ~60% headroom.
Three corrections behind that number, all mine:
- The suite was called HUNG three times. It never was — `test_scaffold.py` is **65 passed in 274.75s**
  and every rc=124 came from a timeout set below it, twice compounded by concurrent runs I had launched.
- `compose_traefik` WAS pathological (200s+ → **46 passed in 54s**) because `_scaffold` re-ran
  `create_project` (~24s) per parametrized test; fixed by caching per type (`7cca80f9`).
- The `1 deselected` is the `pnpm install` test, correctly marked `needs_network` (`84cb5dd3`) — the
  one genuinely network-bound case, and never the blocker I first blamed.
The lone red (`saas_backend::test_auth_and_headers`) was a **stale test**, not a scaffold defect: it
asserted Supabase Pattern B after `4a5e9b5b` deliberately flipped the scaffold to Pattern A. Fixed
against measured emitted output, so this gate can actually reach green.

## Phase D — convergence

`/fabrik-review` over the full diff to a raised-zero round; `docs_updater.py --check`; CHANGELOG entry;
`docs/DECISIONS.md` row (this is an architecture choice: verification ownership moves to the project).

## Self-audit

- **Every phase has a runnable gate** — no phase exits on inspection.
- **The riskiest step is Phase C's docusaurus caveat**: it is the one place this plan can leak internal
  infrastructure detail to a public site, and it is guarded by a test, not a comment.
- **Nothing here depends on fabrik-lib.** The fallback is the plan of record; their enhancement is an
  upgrade, not a prerequisite.
- **Residual risk, named:** the store/static per-type packs are the least-grounded content in the spec
  (no such deploy was exercised). Phase B ships their rows as `UNVERIFIABLE` **by default** rather than
  guessing, so a wrong check never silently passes.

## Evidence (re-derived from primary sources, this run)

```
$ grep -n '_REGISTRAR_ORDER' src/fabrik/orchestrator/infrastructure.py | head -1
151:_REGISTRAR_ORDER = (
$ grep -n 'data-contract-template' src/fabrik/scaffold.py
285:    "docs/data-contract-template.md": "docs/data-contract.md",  # frozen field dictionary
$ wc -l < commands/_sources/fabrik-deploy-verify.md
216
$ grep -c -- '--check' commands/assemble_commands.py
4
$ ls tests/test_scaffold*.py | wc -l
13
$ grep -ic meilisearch commands/_sources/fabrik-deploy-verify.md
1
```

**Per-phase anchors:** Phase A → `src/fabrik/orchestrator/infrastructure.py:151` (`_REGISTRAR_ORDER`) ·
Phase B → `commands/_sources/fabrik-deploy-verify.md:216` (the file it must chain from) ·
Phase C → `src/fabrik/scaffold.py:285` (the seeding precedent) and `src/fabrik/scaffold.py:293` (the
docusaurus leak caveat) · Phase D → `scripts/enforcement/check_convergence.py` (the gate that adjudicates
this plan's own CONVERGED claim).

## Coverage Checklist

**Rubric invocation** — `python scripts/review_rubric.py --changed commands/_sources/fabrik-deploy-verify.md src/fabrik/scaffold.py`

```
# REVIEW RUBRIC — inject into EVERY finder prompt (generated by review_rubric.py)
# Honesty (L1): this arms the review — it raises compliance probability, it does not guarantee it.

## FLOOR — always injected, regardless of glob (spec L3)

### core/35-security-auth.md
**The default for ALL new projects, including user-facing SaaS + mobile.** Vendor `fabrik-lib/fastapi-user-auth`: the app issues its own JWTs — **Argon2id** (the vendored argon2-cffi defaults meet OWASP minimums; never Argon2i) + timing-equalized login, atomic refresh-token rotation (`DELETE … RETURNING`), JWT `jti` denylist revocation, and dual-mode tenant-isolation RLS. Supabase is retired as a default (see `agents-fabrik.md § Supabase`); reach for Pattern B only for a project that *already* runs on Supabase Auth.
- Do not use NextAuth.js, Clerk, Auth0, or Firebase Auth.
- ADDITIONAL affordance a project justifies, never the default door.
- project files the fabrik-lib request FIRST, never hand-rolls WebAuthn.
| `chrome-extension` | ✅ **use this** | ⚠️ only via `chrome.identity.launchWebAuthFlow` + the `https://<ext-id>.chromiumapp.org/` redirect the pack already mandates; a bare mailed link lands in a TAB that cannot reach `chrome.storage.session` |
| `desktop-app` | ✅ **use this** | ⚠️ needs a registered custom protocol handler; the token then goes to `safeStorage` (`desktop-app/72-desktop.md`) |
- service MUST be able to say which:
| **Another Fabrik service** (Docker-to-Docker on the `fabrik` network) | `X-Internal-Token` + `internal_auth.py`, `hmac.compare_digest`, 403 on reject | § Internal Service Auth (M2M) below — **never** an inline `APIKeyHeader`, never a per-service key name |
   [FLOOR continues — the rows above are the ones bearing on this surface]
```

**What the rubric changed here:** the FLOOR's internal-service-auth row (`X-Internal-Token` +
`hmac.compare_digest`, never an inline `APIKeyHeader`) is what the parity contract's own probes must use
when they call a sibling service — recorded so Phase B does not hand-roll auth in generated check rows.


| Class | Verdict | Evidence |
|---|---|---|
| Gate runnability (every phase exits on a real command) | CLEAN | `--check` verified present (4 refs); 13 `tests/test_scaffold*.py` |
| File Scope completeness | **FIXED** | `tests/**` was unbounded → 2 named files; `infrastructure.py` declared READ-ONLY |
| Render-time vs run-time ambiguity | **FIXED** | decided RUN time; render-time would need an out-of-scope `assemble_commands.py` change |
| Cross-repo boundary | CLEAN | fabrik-lib filed not planned; 27-repo onboarding self-serve |
| Fleet-sync blast radius | CLEAN | merge-time render only; `--check` is the safe form |
| **fail-open/fail-closed** (standing) | CLEAN | the seeded stub EXITS NON-ZERO — an unfilled contract fails closed |
| **boundary/sentinel/prefix** (standing) | CLEAN | docusaurus leak boundary guarded by a test, not a comment |
| **cost/quota accounting** (standing) | CLEAN | no metered spend; no subagent fan-out planned |
| **behavior-without-a-test** (standing) | **FIXED** | Phase C's two assertions require red-on-revert proof |

## Pass ledger (`/fabrik-plan-review`)

| Pass | Axes | Raised | Fixed | md5 |
|---:|---|---:|---:|---|
| Pass 1 | gate-runnability · File Scope completeness · fabrik-lib fallback · render-vs-run ambiguity | 4 | 4 | `acbdf439…` → `49c6bc8c…` |
| Pass 2 | full confirming re-sweep | 0 | 0 | stable |
| Pass 3 | method: re-derivation — every count re-run against its primary source, not re-cited | 1 | 1 | edited |
| Pass 4 | confirming | **0** | **0** | stable ✓ |

**Pass 4 terminal — `found: 0, fixed: 0`.**

**Pass 3 (re-derivation) found a 5th:** I had written *"meilisearch has no verification row at all"*.
Re-running the grep shows it has **1** in the command — the absence was in my **spec's Layer 3**, not the
command. `_REGISTRAR_ORDER` is also at `:151`, not the range I had carried from another document. Both
corrected. This is why the closing pass must re-derive rather than re-read: passes 1–2 re-verified my
citations and my citations agreed with me.

**Findings, all mine:**
1. `tests/**` was an unbounded File Scope — replaced with two named test files.
2. `infrastructure.py` was referenced by Phase A but absent from scope — declared as a **READ-ONLY input**.
3. **Layer 3 derivation was ambiguous between render-time and run-time**, and the two have different File
   Scopes. **Decided: RUN time** — render-time injection would need an `assemble_commands.py` change
   (out of scope) *and* would re-freeze the list into rendered text, recreating the exact staleness this
   fixes.
4. Gates verified runnable, not assumed: `assemble_commands.py --check` exists (4 references), 13
   `tests/test_scaffold*.py` files present.

Status: **CONVERGED**.

## Next

`/fabrik-execute-plan` — on the operator's approval.
