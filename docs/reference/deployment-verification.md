# Deployment verification — the contract, the two commands, the verdict

**What it is:** every deployable project declares what its deployed product must *contain*, as executable
rows, and the post-deploy certification EXECUTES that declaration against the live service. Liveness alone
once certified `DEPLOY CONFIRMED LIVE` over a production database holding 0 of its 760 companies — nothing
had declared what the product should hold. Spec: `docs/superpowers/specs/2026-09-01-deployment-verification-contract-design.md`
(CONVERGED, D-077) · plan: `docs/development/plans/archived/2026-09-01-plan-1-deployment-verification.md` (D-082).

## The pieces (all built 2026-09-02)

| piece | where | what |
|---|---|---|
| The parity contract | `scripts/verify_prod_parity.py` in every scaffolded project (template: `templates/scaffold/scripts/verify_prod_parity.py`, hub-rooted symlink at `scripts/`) | a `Status: DRAFT \| FROZEN · Version · Date` header block, one function per corpus row returning the vendored comparison-row shape, `--json` (rows) · `--verdict` (the algebra, executed) · `--self-check` (the FREEZE CHECKLIST) · `--header`. Seeded as `DRAFT`; **the contract run (`--json` / `--verdict`) exits 2 until FROZEN** — `--header` is an inspection flag (exit 0); `--self-check` is STATIC (never executes a row — a checklist that fired every probe at production per run was the wrong instrument) and exits 2 on the bare stub (only the precondition row is authored — freezing it certifies nothing); `NOT_OBLIGATED` is declared in the stub and applied by `--verdict`; an unknown flag prints usage and exits 64. **Project-OWNED and never synced**: a project scaffolded before 2026-09-02 has no stub until its first `/fabrik-deploy-checklist` copies the template in (a synced copy would be gitignored and overwritten) |
| The vendored comparator | `libs/health_probe/` (hub source; `VENDORED_DIRS` → scaffolded + fleet-synced, gitignored in projects) | fabrik-lib `health-probe` AS SHIPPED (`health_probe.py` @ e48ba19c, `fingerprint.py` @ f21f2123) under a 3-line `VENDORED-FROM` header; `compare(name, expected, actual, *, comparator=None)` produces every parity row |
| The authoring command | `/fabrik-deploy-checklist` (`commands/_sources/fabrik-deploy-checklist.md`) | ONE source — what the project ships (never a spec; specs reach it through `FEATURES.md`); derives every denominator, cross-checks FEATURES.md both ways, SEES EVERY ROW RED, freezes with the DECISIONS row, refreshes the fleet-AI sections of DEPLOYMENT.md + OPERATIONS.md from CODE + SPEC + DEV — never PROD |
| The runner | `/fabrik-deploy-verify` (`commands/_sources/fabrik-deploy-verify.md`) | hub-side orchestration: identity (Phase 1b) · DNS · health · registrars DERIVED from `_REGISTRAR_ORDER` at run time · Gatus · logs · **Phase 6 Parity (BLOCKING)** — **one leg per SITE**: `hub` rows from the project's checkout, `container` rows via `docker exec` inside the running app container (the comparator is `docker cp`'d in first — it is gitignored, so the VPS checkout lacks it), `host` rows on the VPS host; an unreachable leg is emitted `UNVERIFIABLE` (`--unreachable`), never dropped; the legs merge with `--verdict --rows-from` and the two lines are copied verbatim |
| The release precondition | `/fabrik-release` VPS path | `BLOCKED: parity contract DRAFT → /fabrik-deploy-checklist`; a stale `Version` is a ⚠ WARN in the Gate-2 block |
| The deploy-triad preconditions (2026-09-03) | `/fabrik-deploy-plan` § Precondition + Phase 2 · `/fabrik-deploy` Phase 0 step 2 | the plan reads `--header` in the SERVICE's checkout (`FROZEN` or `BLOCKED: parity contract DRAFT`; `version` + `container_leg_service` become header facts) and proves in Phase 2 that the leg image can run the comparator (interpreter + `python-dotenv`); the deploy re-reads the header pre-flip and refuses `DRAFT` or a version re-frozen after the plan converged (→ `/fabrik-deploy-plan-review`). Battery ≠ contract: the battery proves the deploy works, the contract proves prod contains what was built |
| The pipeline position | both contracts — hub `CLAUDE.md` and the fleet-synced `templates/governance/CLAUDE.md` — § Orient `6-release` row + § Pipeline flow | `/fabrik-features` REFRESH → certification (`/fabrik-user-test` · `/fabrik-service-test`) → **`/fabrik-deploy-checklist`** (on the certified build — moved after certification 2026-09-03, D-096) → `/fabrik-release` → deploy triad → `/fabrik-deploy-verify` |
| The fleet-AI sections | `DEPLOYMENT_TEMPLATE.md` ("what to deploy") + `OPERATIONS_TEMPLATE.md` ("what runs") | D-065 machine-consumable cells with `{PROJECT_NAME}` sentinels — the token `check_doc_stubs` recognises (it nudges `docs/OPERATIONS.md` on a compose change; `docs/DEPLOYMENT.md` has no code signal in that map today) |

## The row shape and the verdict algebra (executed, never applied in prose)

**Where a row runs is part of the row.** `@site("container")` / `@site("host")` / undeclared = `hub`; `--site NAME` runs one leg, `--rows-from` merges legs. **The contract declares WHICH container its `container` leg runs in** (`CONTAINER_LEG_SERVICE`, surfaced by `--header` as `container_leg_service`; empty = the project's own app service): a DB-free bridge in front of a stateful backend is common (tryton-crm's leg runs in `trytond`, not the app), and that container must carry the comparator's runtime deps (`python-dotenv` at least). Comparators follow one test — *does this number change when a user does their job?* — and derived stores (a filestore, a search index) take the same comparator as the rows they mirror. tryton-crm's first freeze showed why: executed from the hub, 15 of its 27 rows (every DB row, redis, the filestore, the internal renderer) were permanently UNVERIFIABLE — the contract could never be CONFIRMED where the runner ran it.

A parity row is the vendored comparison row `{system, status, detail, expected, actual, match, compare_error}`;
`compare_error` is present only when the comparator raised. **What makes a row a parity row is the vendored
`_COMPARISON_KEYS` DISJUNCTION** — any of `expected` / `actual` / `match` present (a row carrying only
`match` is a comparison row; the `expected AND actual` predicate was the fail-open fabrik-lib closed). A
liveness row carries none of the three keys and sits outside the parity denominator.

| row | verdict effect |
|---|---|
| parity, `match is True` | numerator + denominator |
| parity, `match is False` | denominator; denies `CONFIRMED`; exit 2 |
| parity, `match is None` | **attempted-but-unresolved — fails closed**; denies `CONFIRMED`; exit 2 (a contract whose rows all return `None` FAILS, it does not "report 0 of N") |
| no comparison row authored at all | **fails closed** — "0 of 0" never certifies (rows that exist but are ALL `not obligated` stay CONFIRMED with `N not obligated` printed: explicit data the reader sees) |
| liveness (no comparison key) | outside the denominator; a `DOWN` → exit 1 |
| `not obligated` (a `shape:` flag) | removed from the denominator — the ONLY thing that removes a row |
| `UNVERIFIABLE (<why>)` | counted in the denominator, never the numerator; fails closed |

Exit precedence `1 → 2 → 0`: liveness wins and never upgrades a verdict; ONE algebra — the default/`--json` run exits exactly as `--verdict` (`_exit_code` delegates to `verdict()`). **No `FROZEN` header ⇒
`UNVERIFIED`** — terminal, not success, and the signal to run `/fabrik-deploy-checklist`. The runner's
`DEPLOY CONFIRMED` requires every liveness row PASS *and* the contract's own `VERDICT: CONFIRMED` (exit 0).
Reference implementation and tests: `verify_prod_parity.py::verdict()` · `tests/test_deploy_verify_verdict.py`
(rows produced by the real `compare()`; the retired rule runs beside them and is seen giving the false all-clear).

## Denominator integrity

A denominator is DERIVED wherever derivable and CROSS-CHECKED where it must be declared: routes from the
STARTED app's `/openapi.json` minus the framework's paths (a flat `app.routes` read under-counted 3 vs 27),
services from a YAML parse of compose ∪ registrar-injected sidecars (4 declared, 5 run on tryton-crm), env
keys from `os.getenv` over `src/`, jobs from the live scheduler, schema head by the type's own mechanism,
features cross-checked both ways over EVERY table. **A check that cannot fail is a defect** — every row is
seen red against a deliberately broken DEV state before `FROZEN`.

## Gate coupling — and one deliberate deferral

`check_command_corpus.py` predicate 3 resolves the two commands' `scripts/verify_prod_parity.py` references
against the hub-rooted symlink; `check_sync_trigger_coverage` and `check_print_ban` exempt the vendored
module by path, the way every other vendored lib is exempt. **No executable check grades the contract's
`FROZEN` header today** (`check_stage_artifacts.py` grades the `docs/data-contract.md`, `docs/ui-design.md` and `docs/flows.md` flips — three artifacts, none of them this script): the release
precondition binds on honour, recorded as a `docs/STRATEGIC_BACKLOG.md` row rather than left absent.

## Related

- `docs/workstation/hooks-index.md` — the run-record and Stop-hook mesh both commands ride
- `docs/reference/command-corpus-check.md` — the corpus predicates the two sources pass
- `/opt/fabrik-lib/health-probe/README.md` — the vendored module's own contract (read-only from here)
