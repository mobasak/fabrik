---
description: Author the project's deployment-verification CONTRACT — `scripts/verify_prod_parity.py`: one runnable check + expected result per corpus row, every denominator DERIVED from the system (route table · compose ∪ sidecars · `os.getenv` · scheduler · schema head), features cross-checked, DEV-minus-exclusions baseline, every row SEEN RED before `FROZEN`; refreshes the fleet-AI sections of `DEPLOYMENT.md` + `OPERATIONS.md` from CODE + SPEC + DEV, never PROD. TRIGGER — EN: "author the deploy checklist", "what must prod contain", "freeze the parity contract"; TR: "deploy kontrol listesini yaz", "prod'da ne olmalı". SKIP: running it against the live deploy (→ /fabrik-deploy-verify) · field naming (→ /fabrik-data-contract) · the feature inventory (→ /fabrik-features). Stage: 6-release.
argument-hint: "[optional: the approved spec path (Mode A) — omit to reverse-generate from the shipped project (Mode B)]"
---

Author this project's **deployment-verification contract** — the artifact that lets a deploy be certified
against what was BUILT rather than against liveness alone. It exists because a service passed every
liveness check while holding 0 of its 760 companies: nothing anywhere had declared what the deployed
system was supposed to contain. This command is where the project declares it, as executable rows.

```
/fabrik-features REFRESH  →  /fabrik-deploy-checklist (FREEZE)  →  /fabrik-release (precondition: FROZEN)  →  deploy triad  →  /fabrik-deploy-verify (consumes)
```

**HARD GATE: no `/fabrik-release` READY verdict and no `DEPLOY CONFIRMED` against a contract that is still
`DRAFT`.** A contract-less or unfrozen project reaches `UNVERIFIED` at verify time — a terminal verdict that
is not success — and `UNVERIFIED` is the signal to run this command.

**Where this runs:** project-side, in the project's own repo (cwd) — every phase is `[anywhere]`. The
contract derives from CODE + SPEC + DEV; **PROD is never read by this command** (deriving a declaration
from the deployed state launders drift into documentation). Nothing here needs fleet SSH.

{{include:run-record}}
{{include:term-edit}}
{{include:grounding-artifact}}
{{include:injection}}

## Phase 0 — Establish MODE + scope `[anywhere]`

State the mode and why:

- **Mode A — spec-driven (new work).** A CONVERGED `/fabrik-spec` design is `$ARGUMENTS`; its inventory
  (routes, jobs, state, external deps) seeds the rows. Phase 1 still reconciles every row against what
  the code actually registers — the spec is the source of INTENT, the code of FACT.
- **Mode B — reverse-generate (an existing, shipped project).** No spec; the rows are derived from the
  code, compose, scheduler and DEV. This is how the deployable repos get a contract — run it in each.
- **Mode C — fresh (no code worth deriving from yet).** Fill the seeded stub minimally (header + the
  Layer-1 identity rows, which need only git) so the project has the frozen skeleton to grow into.

Inputs — read them, name them: `project.yaml::type` (the live registry is `scaffold.py::SCAFFOLD_TYPES`)
→ the per-type pack of rows; `specs/services/<id>.yaml` `shape:` → the Layer-3 obligations (a flag that is
`false` makes its row `not obligated`, never absent); `docs/DECISIONS.md` → every ruling about what ships
and what does not (the exclusion set lives here — e.g. *"everything ships EXCEPT sales/activities/invoices
history"*; the ruling is the row's WHAT cell — 4th column, after `id | when | who` — quote it verbatim
beside the exclusion list); `docs/FEATURES.md` → the cross-check inventory; `docs/DEPLOYMENT.md` + `docs/OPERATIONS.md` →
the fleet-AI sections this run refreshes.

**Starting state + check-before-create:** the scaffolder seeds `scripts/verify_prod_parity.py` as a
`Status: DRAFT` stub that **exits 2** — an unfilled contract fails closed — and the fleet sync seeds the
vendored `libs/health_probe/` it imports (VENDORED_DIRS). **If `libs/health_probe/health_probe.py` is absent**
(a repo the sync has not reached yet): copy it from `/opt/fabrik-lib/health-probe/` into THIS repo's
`libs/health_probe/` (a read of the sibling repo and a write in your own tree — not a cross-repo edit), say so
in the report, and carry on; the next sync overwrites it with the identical bytes. **If `scripts/verify_prod_parity.py` is absent** (every project scaffolded before 2026-09-02 — the stub is seeded by the scaffolder's `SCRIPT_FILES` at scaffold time and is deliberately **never synced**: the contract is project-OWNED and committed, and a synced copy would be gitignored and overwritten on every sync): copy `/opt/fabrik/templates/scaffold/scripts/verify_prod_parity.py` into THIS repo's `scripts/` (a read of the hub, a write in your own tree), commit it with this run, and carry on — it is the same DRAFT stub the scaffolder would have seeded. **A DRAFT stub is meant to be
edited through — its existence is NOT a STOP.** Only a `Status: FROZEN` header is a STOP: say so, and on
the operator's word proceed as a **re-freeze** — bump `Version`, never a silent overwrite.

Store types (`mobile-app`, `chrome-extension`, `office-extension`, `desktop-app`) have no VPS: their
contract is the **provenance pack only** (submitted artifact ↔ tested SHA, store review state) — say so
and skip Layers 2–4. `wordpress` runs no fabrik command (out of fabrik).

## Phase 1 — Derive the denominators `[anywhere]`

**A denominator is DERIVED wherever derivable; where it must be declared it is CROSS-CHECKED against a
derived proxy.** Each source below is authoritative; the prose next to it is never the sole basis.

| denominator | derive from (authoritative) | never from | when underivable |
|---|---|---|---|
| routes | the app's OWN published table: **`/openapi.json` from the started app** (a `TestClient(app)` context runs the lifespan; or the running DEV server), **then subtract the framework's paths** (`/`, `/docs`, `/redoc`, `/openapi.json`, `/docs/oauth2-redirect`) and state BOTH counts (`total / application`). ⚠️ A flat read of `app.routes` UNDER-COUNTS: routers included via `include_router` sit nested under router objects whose own `.routes` must be walked — measured on a real project, flat `app.routes` gave **3** application routes while `/openapi.json` gave **27** paths. ⚠️ Never a `grep include_router`: a composed `v1_router` carries its prefix on the parent (`prefix="/internal/v1"`), and the grep returns nothing | `FEATURES.md` prose · a flat `app.routes` read | `UNVERIFIABLE (no introspection: <why>)` |
| services | `yaml.safe_load(compose)["services"]` ∪ the registrar-injected sidecars the `shape:` flags imply (a `watchdog` container appears in no compose file). ⚠️ Never an indentation regex — it counts `volumes:`/`networks:` keys as services (measured: 6 for 4) | compose read by eye | — (always derivable) |
| env keys | `os.getenv(...)`/`os.environ[...]` names over `src/` (every key, de-duplicated) | `.env.example` alone | — |
| scheduled jobs | the live scheduler: `ir_cron` rows for a Tryton stack, Beat/APScheduler registrations for a scaffolded API, `crontab -l` for a host job | `RESILIENCE.md` §7 | `UNVERIFIABLE (scheduler not introspectable from here: <why>)` |
| schema head | the type's OWN mechanism: `alembic heads` for a scaffolded API; module state (`ir_module`) for trytond; a migrations dir count for node | `db/schema.sql`, a doc | `UNVERIFIABLE (no migration tool: <why>)` — never a guess |
| state baseline | **DEV minus the declared exclusion set** — row counts, reference data, translations, filestore counts measured in DEV; exclusions from `docs/DECISIONS.md` (fixture companies, test users, history the ruling excludes) | PROD (see the hazard rule) | a missing exclusion ruling is the one thing to RAISE (§ Question bar) |
| features | not derivable — `FEATURES.md` is prose | — | cross-checked in Phase 3, never trusted alone |

Record every derivation as the COMMAND that produced it and its COUNT (`routes: 23 via app.routes` ·
`services: 4 + 1 sidecar` · `env keys: 32 distinct over 49 sites`). A count without its command is a
claim.

**Parallelism — the default with 2+ derivation surfaces:** one pool grounder per surface (routes · jobs ·
env · services · schema) per § Subagents; the exclusion-set judgement and every DEV measurement stay
native — they read the project's own environment.

## Phase 2 — Emit the contract `[anywhere]`

Write `scripts/verify_prod_parity.py` to the seeded template's shape:

- **Header block** (machine-readable, the runner and the release precondition parse it):
  `# Status: DRAFT | FROZEN · Version: v<N> · Date: YYYY-MM-DD · Mode: A | B | C` and the freeze rule
  verbatim: *"Frozen — no agent adds, removes or re-derives a row not listed here. Any change = bump Version
  + re-freeze via `/fabrik-deploy-checklist`."*
- **One function per corpus row**, named by its corpus id (`l1_identity_sha`, `l2_routes`,
  `l2_state_companies`, `l3_postgres`, … — lowercase: the hub's ruff N802 refuses capitalised function names), returning the `health-probe` comparison row shape —
  `{system, status, detail, expected, actual, match, compare_error}` — with `system` = the corpus id.
  ⚠️ **A liveness row (Layer 3/4 reachability, no declared value) returns the three-key `{system, status,
  detail}` shape and NONE of the comparison keys** — the vendored CLI treats a row carrying ANY of
  `expected`/`actual`/`match` as a comparison row (`_COMPARISON_KEYS`, a disjunction on purpose), so a
  liveness row emitted with `match: None` would FAIL the contract as attempted-unresolved.
  `expected` is DERIVED at run time where Phase 1 derived it (**snapshot values are a cache of a
  derivation; ship the derivation**); a row that can only snapshot is marked `mode: snapshot` in `detail`
  — the legal *degraded* form, reported as such, never silently.
- **`UNVERIFIABLE (<why>)` rows are emitted, never dropped** — they count in the denominator so shrinkage
  is visible. The store-type and static-type packs ship `UNVERIFIABLE` by default; a wrong check that
  silently passes is worse than a stated gap.
- **The exclusion set is data** in the script (a list with the ruling's `D-NNN` beside it), applied to the
  DEV baseline, so the runner and a reader see what was excluded and why.
- **Read-only against the target.** A row that would mutate the deployed service is written as
  `UNVERIFIABLE (mutating — needs a scoped payload + the operator's go)`, never executed.
- `--json` prints the row list; `--self-check` runs the FREEZE CHECKLIST (header parses · every function
  returns the row shape · every `UNVERIFIABLE` carries a why · the exclusion list names a ruling) and
  exits non-zero on any miss.

## Phase 3 — Features cross-check `[anywhere]`

`FEATURES.md` is prose and cannot be derived, so it is cross-checked instead: **every derived route maps
to a shipped feature row, and every shipped feature row to a route.** **Walk EVERY table in the file, and
derive each table's status rule from ITS OWN header** — a `Status` column when present (a `✅ Shipped`-prefixed
cell is shipped; variants like `✅ Shipped (sandbox)` count), else a non-empty `Endpoint / Module` cell (the
scaffold template carries no status column at all). Do not assume a vocabulary and do not stop at the first
table: measured on a real project, the FIRST table's header was `Feature | Description | Module` with no
status cell, a literal-word grep returned 0, and the shipped rows (37, `✅ Shipped`) lived in a LATER table. **A route with no feature row, or a feature row with no route, is
a FINDING** in the report and a row in the contract (`l2_features_crosscheck`, expected 0 unmatched) —
that is what makes an under-declared inventory detectable rather than a smaller denominator.

## Phase 4 — Converge `[anywhere]` (the self-audit LOOP — iterate to a no-op)

Run repeated passes until one demonstrably-thorough pass makes zero edits to the script (Termination
contract). Each pass checks ALL of: **corpus coverage** (a row per applicable Layer 1–4 + pack check,
`UNVERIFIABLE` where it must be) · **derived denominators** (every `expected` traces to a Phase-1 command
and count) · **features cross-check** (both directions) · **executability** (`--json` runs; `--self-check`
green) · **exclusions** (each names its ruling) · **red-seen** (Phase 5's table complete) · **docs** (the
fleet-AI sections say what the rows assert). List what you re-read and what changed, then run one MORE
pass.

## Phase 5 — SEE EVERY ROW RED `[anywhere]`

*A check that cannot fail is a defect.* Before freezing, prove each row can fail:

1. Run the contract against DEV — expected: every derived row `match: True`, every `UNVERIFIABLE` row
   `match: None` with its why.
2. For each row CLASS, break DEV deliberately and re-run: drop a table's rows for a state row · rename an
   env key for the env row · stop the scheduler for the jobs row · remove a route for the routes row ·
   detach a service for the services row. **Each targeted row must report `match: False`** (or, for a
   raising comparator, `match: None` **with `compare_error` set** — that is fail-closed, not green).
   Restore DEV after each.
3. A row that cannot be made to fail is REWRITTEN, or marked `UNVERIFIABLE (cannot be seen red: <why>)`.
4. Paste the red table into the report: `row · how DEV was broken · result`. **A contract with no red
   table is DRAFT** whatever its header says.

## Phase 6 — Freeze + wire the truth `[anywhere]`

- **The freeze (and every re-freeze bump) is a Status flip — mint its `docs/DECISIONS.md` row in the SAME
  change** (classify at mint; a contract freeze is normally reversible-by-re-freeze).
- Set the header: `Status: FROZEN · Version: v<N> · Date · Mode`, freeze rule verbatim. **This header write
  is a post-convergence action, exempt from the no-op rule** — measured on the body, not the flip.
- **Refresh the fleet-AI sections of `docs/DEPLOYMENT.md` and `docs/OPERATIONS.md`** (D-065) — the
  services/jobs/env/dependency inventory Phase 1 derived IS the content those sections owe. Touch ONLY the
  sentinel-marked fleet-AI sections the template seeds; the project's own runbook prose is theirs. **If the
  sections are absent** (a project scaffolded before 2026-09-02 — the templates only reach new scaffolds), ADD them
  first, verbatim from `templates/scaffold/docs/DEPLOYMENT_TEMPLATE.md` § *Fleet-AI interface — what to deploy* and
  `OPERATIONS_TEMPLATE.md` § *5b. Fleet-AI interface — what runs*, then fill the cells.
  ⚠️ **HAZARD — derive these from CODE + SPEC + DEV, never from PROD.** *"prod has 0 companies, therefore
  document 0 companies"* makes an empty-database certification self-consistent and still wrong. The docs
  declare what SHOULD be true; the verify run reports what IS; the gap between them is the product.
- **Gate coupling, stated:** a change to compose services, the scheduler, the `os.getenv` set or the
  schema head without a Version bump is drift the runner will surface as a `match: False` on the next
  verify. No enforcement check grades this header today — that is a deliberate, recorded deferral
  (`docs/STRATEGIC_BACKLOG.md`), not an oversight.

## Phase 7 — Hand off `[anywhere]`

- **Mode A / B:** the contract is `FROZEN` → **`/fabrik-release`**, whose VPS-path precondition reads this
  header and BLOCKS on `DRAFT`. State this and stop.
- **Mode C:** stop at the filled stub, `Status: DRAFT`, and say which rows await code.
- **On a version BUMP:** the Re-freeze close-out below names what the next `/fabrik-deploy-verify` must
  re-run.

{{include:questionbar}}
## Guardrails — never
- Derive a row, a count or a doc section from PROD — the deployed state is the thing under test.
- Drop a row you cannot assert — emit it `UNVERIFIABLE (<why>)`; a shrunk denominator hides the gap.
- Freeze on a pass whose reconciliation made edits, or on a contract with no red table.
- Invent a check with no corpus id, or read `match: None` as agreement anywhere.
- Execute a mutating row, or read PROD data, from this command — it authors; `/fabrik-deploy-verify` runs.
- Hand off to `/fabrik-release` while the header is `DRAFT`.

## Re-freeze close-out (runs ONLY when this run was a version bump N→N+1 on an already-FROZEN contract)

1. **Diff the script against its pre-run version** (`git diff HEAD -- scripts/verify_prod_parity.py`)
   and extract the changed row ids and expected values.
2. **Emit a Downstream impact table**: `changed row → what the next verify must re-run → why`. Zero
   changed rows is a stated result, never an omitted one.
3. **The NEXT line becomes the owed re-verify** when the impact is non-empty: `/fabrik-deploy-verify`
   against the bumped Version, with the changed rows named as its arguments.

{{include:subagents-core}}
## Output (always, last thing)

```
DEPLOY-CHECKLIST: <project> · type <scaffold type> · Mode <A|B|C> · contract v<N>
DENOMINATORS: routes <n> (via <cmd>) · services <n>+<sidecars> · env keys <n> · jobs <n> | UNVERIFIABLE (<why>) · schema <head> | UNVERIFIABLE (<why>)
ROWS: <N> total — <n> derived / <n> snapshot / <n> UNVERIFIABLE / <n> not obligated
RED-SEEN: <n> of <N> asserting rows proven able to fail · <n> cannot-be-seen-red (listed)
FEATURES: <n> routes ↔ <n> shipped rows · <n> unmatched (FINDINGS listed)
EXCLUSIONS: <n> items, rulings <D-NNN, …>
DOCS: DEPLOYMENT.md + OPERATIONS.md fleet-AI sections refreshed from CODE + SPEC + DEV
STATUS: FROZEN v<N> | DRAFT (<why>)
```

Next command: `/fabrik-release` — its VPS-path precondition reads the `FROZEN` header. On a version BUMP
with downstream impact: `/fabrik-deploy-verify` re-run against the bumped contract, changed rows named.
