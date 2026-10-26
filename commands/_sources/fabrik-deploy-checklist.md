---
description: Author the project's deployment-verification CONTRACT — `scripts/verify_prod_parity.py`: one runnable check + expected result per corpus row, every denominator DERIVED from the system (route table · compose ∪ sidecars · `os.getenv` · scheduler · schema head), features cross-checked, DEV-minus-exclusions baseline, every row SEEN RED before `FROZEN`; refreshes the fleet-AI sections of `DEPLOYMENT.md` + `OPERATIONS.md` from CODE + SPEC + DEV, never PROD. TRIGGER — EN: "author the deploy checklist", "what must prod contain", "freeze the parity contract"; TR: "deploy kontrol listesini yaz", "prod'da ne olmalı". SKIP: running it against the live deploy (→ /fabrik-deploy-verify) · field naming (→ /fabrik-data-contract) · the feature inventory (→ /fabrik-features). Stage: 6-release.
argument-hint: "[optional: a subsystem to scope the rows — omit to derive the whole deployed product]"
---

> **POOL OFF — D-181 (operator, 2026-09-07).** The OpenRouter subagent pool is OFF by operator ruling (D-181; mechanism revised by D-182, provider credentials stay provisioned): every `fanout` / `pick_models` / `set_quality` / `record_agent_run` / `results_table` instruction is SUSPENDED (left in place, or in `<!-- POOL OFF -->` comments, for re-enable). Run every fan-out this command names NATIVELY — Claude Task subagents (`fabrik-reviewer` · `fabrik-researcher` · `fabrik-gui` · general-purpose): same unit split, same author-blind rule, same decide/refute/merge — and skip every flywheel back-fill. Never write `NO-POOL:` for it: `check_subagent_flywheel.py`'s pool-or-declare layer stands down by the same ruling (`_POOL_POLICY_ON = False`, D-182). Canonical: `62-using-subagents.md` § Dispatch policy.

Author this project's deployment-verification contract: the artifact that lets a deploy be certified against what was BUILT, not liveness alone.

You are at step 1 of the chain below — previous: end-to-end certification (`/fabrik-user-test` · `/fabrik-service-test`, green on the build to freeze) · next: `/fabrik-release`.

{{include:deploy-chain}}

HARD GATE: no `/fabrik-release` READY verdict, no `DEPLOY CONFIRMED` against a `DRAFT` contract. A contract-less or unfrozen project reaches `UNVERIFIED` at verify time (a terminal verdict, not success) — `UNVERIFIED` is the signal to run this command.

Where this runs: project-side, in the project's own repo — every phase is `[anywhere]`. The contract derives from CODE + SPEC + DEV; PROD is never read by this command (deriving a declaration from the deployed state launders drift into documentation). Nothing here needs fleet SSH.

{{include:run-record}}
{{include:orient}}

{{include:delegated-reads}}
{{include:term-edit}}
{{include:grounding-artifact}}
{{include:injection}}

## Phase 0 — Establish MODE + scope `[anywhere]`

One source, always: what the project SHIPS. Rows derive from code, compose file, scheduler, env set and DEV state — never from a spec. Specs reach this command only through `docs/FEATURES.md`, the cross-check inventory Phase 3 walks both ways (a feature a spec promised and nothing ships is a finding there). A project with little code yet gets few rows — the Layer-1 identity rows need only git — and the same run, re-run after each build, grows the contract; there is no separate "fresh" or "spec" path to choose. Run it when the project is ready to deploy and whenever compose services, the scheduler, the `os.getenv` set or the schema head change (the release precondition warns when the contract's `Version` predates one).

Inputs — read them, name them: `project.yaml::type` (registry `scaffold.py::SCAFFOLD_TYPES`) → the per-type pack of rows; `specs/services/<id>.yaml` `shape:` (in a project repo usually absent — read the hub's `/opt/fabrik/specs/services/<id>.yaml`, read-only; the hub copy wins when both exist, and when neither exists or the hub holds only a `.yaml.draft`, say so and treat every `shape:` row as obligated) → the Layer-3 obligations (a flag that is `false` makes its row `not obligated`, never absent); `docs/DECISIONS.md` → every ruling about what ships and what does not (exclusion set, e.g. *"everything ships EXCEPT sales/activities/invoices history"*; the ruling is the row's WHAT cell, 4th column after `id | when | who` — quote it verbatim beside the exclusion list); `docs/FEATURES.md` → the cross-check inventory; `docs/DEPLOYMENT.md` + `docs/OPERATIONS.md` → the fleet-AI sections.

Starting state + check-before-create: the scaffolder seeds `scripts/verify_prod_parity.py` as a `Status: DRAFT` stub that exits 2 (an unfilled contract fails closed); the fleet sync seeds the vendored `libs/health_probe/` it imports (VENDORED_DIRS). If `libs/health_probe/health_probe.py` is absent, copy it from `/opt/fabrik-lib/health-probe/` into THIS repo's `libs/health_probe/` (a read of the sibling repo, a write in your own tree — not a cross-repo edit), say so in the report, and carry on.

If `scripts/verify_prod_parity.py` is absent (every project scaffolded before 2026-09-02 — the stub is seeded by the scaffolder's `SCRIPT_FILES` at scaffold time and is deliberately never synced: the contract is project-OWNED and committed, and a synced copy would be gitignored and overwritten on every sync): copy `/opt/fabrik/templates/scaffold/scripts/verify_prod_parity.py` into THIS repo's `scripts/` (a read of the hub, a write in your own tree), commit it with this run, and carry on.

A DRAFT stub is meant to be edited through — its existence is NOT a STOP. Only a `Status: FROZEN` header is a STOP: say so, and on the operator's word proceed as a re-freeze — bump `Version`, never a silent overwrite.

Store types (`mobile-app`, `chrome-extension`, `office-extension`, `desktop-app`) have no VPS: their contract is the provenance pack only (submitted artifact ↔ tested SHA, store review state) — say so and skip Layers 2–4. `wordpress` runs no fabrik command.

## Phase 1 — Derive the denominators `[anywhere]`

A denominator is DERIVED wherever derivable; where it must be declared it is CROSS-CHECKED against a derived proxy. Each source below is authoritative; the prose next to it is never the sole basis.

| denominator | derive from (authoritative) | never from | when underivable |
|---|---|---|---|
| routes | `/openapi.json` from the started app (a `TestClient(app)` context, or the running DEV server), minus the framework's paths (`/`, `/docs`, `/redoc`, `/openapi.json`, `/docs/oauth2-redirect`); state BOTH counts (`total / application`). A flat read of `app.routes` UNDER-COUNTS: routers included via `include_router` sit nested under router objects whose own `.routes` must be walked — measured: flat `app.routes` gave 3 application routes while `/openapi.json` gave 27 paths. ⚠️ Never a `grep include_router`: a composed `v1_router` carries its prefix on the parent (`prefix="/internal/v1"`), and the grep returns nothing | `FEATURES.md` prose · a flat `app.routes` read | `UNVERIFIABLE (no introspection: <why>)` |
| services | `yaml.safe_load(compose)["services"]` ∪ the registrar-injected sidecars the `shape:` flags imply (a `watchdog` appears in no compose file). ⚠️ Never an indentation regex — it counts `volumes:`/`networks:` keys as services (measured: 6 for 4) | compose read by eye | — (always derivable) |
| env keys | `os.getenv(...)`/`os.environ[...]` names over `src/` (every key, de-duplicated) | `.env.example` alone | — |
| scheduled jobs | the live scheduler: `ir_cron` rows for a Tryton stack, Beat/APScheduler registrations for a scaffolded API, `crontab -l` for a host job | `RESILIENCE.md` §7 | `UNVERIFIABLE (scheduler not introspectable from here: <why>)` |
| schema head | the type's OWN mechanism: `alembic heads` for a scaffolded API; module state (`ir_module`) for trytond; a migrations dir count for node | `db/schema.sql`, a doc | `UNVERIFIABLE (no migration tool: <why>)` — never a guess |
| state baseline | DEV minus the declared exclusion set — row counts, reference data, translations, filestore counts measured in DEV; exclusions from `docs/DECISIONS.md` (fixture companies, test users, history the ruling excludes) | PROD | a missing exclusion ruling is the one thing to RAISE |
| features | not derivable — `FEATURES.md` is prose | — | cross-checked in Phase 3, never trusted alone |

Record every derivation as the COMMAND that produced it and its COUNT (`routes: 23 via app.routes` · `services: 4 + 1 sidecar` · `env keys: 32 distinct over 49 sites`). A count without its command is a claim.

Parallelism — UNCONDITIONAL, every run: one native `general-purpose` grounder per surface, all dispatched in ONE message — the surface count is the PARTITION, `dispatch_headroom.py --units <N>` prints the seats — stamped BEFORE they go out with `python3 scripts/command_run.py dispatch --seats <n>` so sibling sessions subtract them — (D-191) (routes · jobs · env · services · schema) per § Subagents. Never solo, never two: a surface with fewer than three units still dispatches THREE seats on DIFFERENT angles over it. The exclusion-set judgement and every DEV measurement stay native — they read the project's own environment.

## Phase 2 — Emit the contract `[anywhere]`

Write `scripts/verify_prod_parity.py` to the seeded template's shape:

- Header block (machine-readable, the runner and the release precondition parse it): `# Status: DRAFT | FROZEN · Version: v<N> · Date: YYYY-MM-DD` and the freeze rule verbatim: *"Frozen — no agent adds, removes or re-derives a row not listed here. Any change = bump Version + re-freeze via `/fabrik-deploy-checklist`."*
- Every row declares its SITE — `@site("container")` for rows that need the database, redis or the internal network, `@site("host")` for `docker ps` / volume rows, nothing for the public surface (`hub`, the default). The runner executes one leg per site and merges; a row placed at a site that cannot reach its target is a row that can never resolve (tryton-crm's first freeze: 15 of 27 rows were DB/host rows left at the hub site — permanently UNVERIFIABLE). A row carries no site, so a leg's site is known only from the file it came in.
- No self-referential row: a row whose `expected` and `actual` come from the same source cannot be seen red and inflates the numerator — the only rows allowed to compare a constant to itself are the `not obligated` markers, and only because `NOT_OBLIGATED` removes them from the denominator.
- No snapshot fallback: when a declaration cannot be derived where the row runs, the row is `UNVERIFIABLE (<why>)` — never a number remembered from an earlier run, which drifts silently the first time a route is added.
- Comparators by ONE test, never by an example list — "does this number change when a user does their job?" No → compare EXACTLY. Yes → a floor (`comparator=lambda e, a: a >= e`) after the first deploy. Derived stores that mirror a row set take the SAME comparator as the rows they mirror and switch together. The first-deploy freeze may be exact everywhere; the contract names which rows switch to floors at the next bump, and coupled rows name each other.
- Declare the container leg's service when it is not the app: `CONTAINER_LEG_SERVICE = "<compose service>"` beside `SITES`, the container that can reach the database and the internal network; the runner reads this from `--header` rather than assuming (a DB-free bridge's leg runs in `trytond`). That container must carry a Python interpreter AND the comparator's runtime deps (`httpx` at module level, `python-dotenv` for the `.env` load) — read the leg service's Dockerfile before siting a row there. A Node image has no `python` at all — `node-api` and `file-api` ship one (`Dockerfile.node`), so does `docusaurus` (its `Dockerfile.j2`); those projects site their DB/redis rows on the hub or host leg, or declare a Python sidecar as the leg — never the app container, where every row would read UNVERIFIABLE at the first verify run. `saas-skeleton` and `static-site` pair a Node frontend with a Python backend service (`scaffold.py::_scaffold_saas_backend`) — there the backend IS the leg; declare it.
- One function per corpus row, named by its corpus id (`l1_identity_sha`, `l2_routes`, `l2_state_companies`, `l3_postgres`, … — lowercase: the hub's ruff N802 refuses capitalised function names), returning the `health-probe` comparison row shape — `{system, status, detail, expected, actual, match, compare_error}` — with `system` = the corpus id. A liveness row (Layer 3/4 reachability, no declared value) returns the three-key `{system, status, detail}` shape and NONE of the comparison keys — the vendored CLI treats a row carrying ANY of `expected`/`actual`/`match` as a comparison row (`_COMPARISON_KEYS`, a disjunction on purpose), so a liveness row emitted with `match: None` would FAIL the contract.
- `expected` is DERIVED at run time where Phase 1 derived it (snapshot values are a cache of a derivation; ship the derivation); a row that can only snapshot is marked `mode: snapshot` in `detail` — the legal *degraded* form, reported as such, never silently.
- `UNVERIFIABLE (<why>)` rows are emitted, never dropped — they count in the denominator so shrinkage is visible. The store-type and static-type packs ship `UNVERIFIABLE` by default; a wrong check that silently passes is worse than a stated gap.
- A `--rows-from` merge checks the leg files before it counts them (`_rows_for` calls `check_leg_rows`): every contract row appears exactly once, with the three comparison keys all or none, a tri-state `match` and a known status, or the merge exits 64. A contract frozen before the template had `check_leg_rows` merges its legs unchecked until a re-freeze copies the check in.
- The exclusion set is data in the script (a list with the ruling's `D-NNN` beside it), applied to the DEV baseline.
- Read-only against the target. A row that would mutate the deployed service is written as `UNVERIFIABLE (mutating — needs a scoped payload + the operator's go)`, never executed.
- `--json` prints the row list; `--self-check` runs the FREEZE CHECKLIST (header parses · every function returns the row shape · every `UNVERIFIABLE` carries a why · the exclusion list names a ruling) and exits non-zero on any miss.

## Phase 3 — Features cross-check `[anywhere]`

`FEATURES.md` is prose and cannot be derived, so it is cross-checked instead: every derived route maps to a shipped feature row, and every shipped feature row to a route. Walk EVERY table in the file, deriving each table's status rule from ITS OWN header — a `Status` column when present (a `✅ Shipped`-prefixed cell is shipped; variants like `✅ Shipped (sandbox)` count), else a non-empty `Endpoint / Module` cell. Do not assume a vocabulary and do not stop at the first table. A route with no feature row, or a feature row with no route, is a FINDING in the report and a row in the contract (`l2_features_crosscheck`, expected 0 unmatched).

## Phase 4 — Converge `[anywhere]` (the self-audit LOOP — iterate to a no-op)

Run repeated passes until the Termination contract's closing round — `confirmed: 0`, the script's md5 unchanged. Each pass checks ALL of: corpus coverage (a row per applicable Layer 1–4 + pack check, `UNVERIFIABLE` where it must be) · derived denominators (every `expected` traces to a Phase-1 command and count) · features cross-check (both directions) · executability (`--json` runs; `--self-check` green) · exclusions (each names its ruling) · red-seen (Phase 5's table complete) · docs (the fleet-AI sections say what the rows assert). List what you re-read and what changed, then run one MORE pass.

## Phase 5 — SEE EVERY ROW RED `[anywhere]`

*A check that cannot fail is a defect.* Before freezing, prove each row can fail:

1. Run the contract against DEV — expected: every derived row `match: True`, every `UNVERIFIABLE` row `match: None` with its why.
2. Run the probes in a copy that carries the gitignored files the contract reads (`libs/` and `.env` — a fresh worktree lacks them; the copy isolates the code only — DEV itself is shared, so break and restore it as below), and run the unmutated copy first as the control: a red the control also shows proves nothing.
3. For each row CLASS, break DEV deliberately and re-run: drop a table's rows for a state row · rename an env key for the env row · stop the scheduler for the jobs row · remove a route for the routes row · detach a service for the services row. Each targeted row must report `match: False` (or, for a raising comparator, `match: None` with `compare_error` set — that is fail-closed, not green). Restore DEV after each.
4. A row that cannot be made to fail is REWRITTEN, or marked `UNVERIFIABLE (cannot be seen red: <why>)`.
5. A test added for the contract runs in the gate's pytest leg (the whole suite, one process) before freeze — where that leg is off (the gate prints `pytest (NOT RUN)`), run `python -m pytest tests/ -q` yourself and paste its tail: the first row that needs the vendored probe loads the project's `.env` into `os.environ`, and that state reaches every later test in the process.
6. Paste the red table into the report: `row · how DEV was broken · result`. A contract with no red table is DRAFT whatever its header says.

## Phase 6 — Freeze + wire the truth `[anywhere]`

- The freeze (and every re-freeze bump) is a Status flip — mint its `docs/DECISIONS.md` row in the SAME change (classify at mint; a contract freeze is normally reversible-by-re-freeze).
- Set the header: `Status: FROZEN · Version: v<N> · Date`, freeze rule verbatim (a trailing `· Mode: …` from an earlier freeze parses; the re-freeze drops it). This header write is a post-convergence action, exempt from the no-op rule.
- Refresh the fleet-AI sections of `docs/DEPLOYMENT.md` and `docs/OPERATIONS.md` (D-065) — the services/jobs/env/dependency inventory Phase 1 derived. Touch ONLY the sentinel-marked fleet-AI sections the template seeds; the project's own runbook prose is theirs. If the sections are absent (a project scaffolded before 2026-09-02 — the templates only reach new scaffolds), ADD them first, verbatim from `templates/scaffold/docs/DEPLOYMENT_TEMPLATE.md` § *Fleet-AI interface — what to deploy* and `OPERATIONS_TEMPLATE.md` § *5b. Fleet-AI interface — what runs*, then fill the cells.
- ⚠️ HAZARD — derive these from CODE + SPEC + DEV, never from PROD. *"prod has 0 companies, therefore document 0 companies"* is self-consistent and still wrong. The docs declare what SHOULD be true; the verify run reports what IS; the gap between them is the product.
- Gate coupling, stated: a change to compose services, the scheduler, the `os.getenv` set or the schema head without a Version bump is drift the runner will surface as a `match: False` on the next verify. No enforcement check grades this header today — that is a deliberate, recorded deferral (`docs/STRATEGIC_BACKLOG.md`), not an oversight.

## Phase 7 — Hand off `[anywhere]`

The contract is `FROZEN` → `/fabrik-release`, whose VPS-path precondition reads this header and BLOCKS on `DRAFT`. State this and stop. A run that could derive only the identity rows (little code yet) still freezes — few rows is a true contract; say which layers await code. On a version BUMP: the Re-freeze close-out below names what the next `/fabrik-deploy-verify` must re-run.

{{include:questionbar}}
## Guardrails — never
- Derive a row, a count or a doc section from PROD — the deployed state is the thing under test.
- Drop a row you cannot assert — emit it `UNVERIFIABLE (<why>)`; a shrunk denominator hides the gap.
- Freeze on a pass whose reconciliation made edits, or on a contract with no red table.
- Invent a check with no corpus id, or read `match: None` as agreement anywhere.
- Execute a mutating row, or read PROD data, from this command — it authors; `/fabrik-deploy-verify` runs.
- Hand off to `/fabrik-release` while the header is `DRAFT`.

## Re-freeze close-out (runs ONLY when this run was a version bump N→N+1 on an already-FROZEN contract)

1. Diff the script against its pre-run version (`git diff HEAD -- scripts/verify_prod_parity.py`) and extract the changed row ids and expected values.
2. Emit a Downstream impact table: `changed row → what the next verify must re-run → why`. Zero changed rows is a stated result, never an omitted one.
3. The NEXT line becomes the owed re-verify when the impact is non-empty: `/fabrik-deploy-verify` against the bumped Version, with the changed rows named as its arguments.

{{include:subagents-core}}
## Output (always, last thing)

```
DEPLOY-CHECKLIST: <project> · type <scaffold type> · contract v<N>
DENOMINATORS: routes <n> (via <cmd>) · services <n>+<sidecars> · env keys <n> · jobs <n> | UNVERIFIABLE (<why>) · schema <head> | UNVERIFIABLE (<why>)
ROWS: <N> total — <n> derived / <n> snapshot / <n> UNVERIFIABLE / <n> not obligated
RED-SEEN: <n> of <N> asserting rows proven able to fail · <n> cannot-be-seen-red (listed)
FEATURES: <n> routes ↔ <n> shipped rows · <n> unmatched (FINDINGS listed)
EXCLUSIONS: <n> items, rulings <D-NNN, …>
DOCS: DEPLOYMENT.md + OPERATIONS.md fleet-AI sections refreshed from CODE + SPEC + DEV
STATUS: FROZEN v<N> | DRAFT (<why>)
```

Next command: `/fabrik-release` — its VPS-path precondition reads the `FROZEN` header. On a version BUMP with downstream impact: `/fabrik-deploy-verify` re-run against the bumped contract, changed rows named.

{{include:close-chain}}
