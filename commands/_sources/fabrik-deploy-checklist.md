---
description: Author the project's deployment-verification CONTRACT — `scripts/verify_prod_parity.py`: one runnable check + expected result per row, every denominator DERIVED from the system, DEV-minus-exclusions baseline, every row SEEN RED before `FROZEN`; refreshes the fleet-AI sections of `DEPLOYMENT.md` + `OPERATIONS.md` from CODE + SPEC + DEV, never PROD. TRIGGER — EN: "author the deploy checklist", "what must prod contain", "freeze the parity contract"; TR: "deploy kontrol listesini yaz", "prod'da ne olmalı". SKIP: running it against the live deploy (→ /fabrik-deploy-verify) · field naming (→ /fabrik-data-contract) · the feature inventory (→ /fabrik-features). Stage: 6-release.
argument-hint: "[optional: a subsystem to scope the rows — omit to derive the whole deployed product]"
---

> **POOL OFF — D-181.** Run every fan-out this command names natively (Claude Task subagents); never write `NO-POOL:` for it.

Author this project's **deployment-verification contract**: executable rows declaring what the deployed system must contain, so a deploy is certified against what was BUILT, not liveness alone.

**You are at step 1 of the chain below — previous: end-to-end certification (`/fabrik-user-test` · `/fabrik-service-test`, green on the build you are about to freeze) · next: `/fabrik-release`.**

{{include:deploy-chain}}

**HARD GATE: no `/fabrik-release` READY verdict and no `DEPLOY CONFIRMED` against a contract that is still `DRAFT`.** A contract-less or unfrozen project reaches `UNVERIFIED` at verify time (terminal, not success) — the signal to run this command.

**Where this runs:** project-side, in the project's own repo — every phase is `[anywhere]`, no fleet SSH. The contract derives from CODE + SPEC + DEV; **PROD is never read by this command**, because a declaration derived from the deployed state launders drift into documentation.

{{include:run-record}}
{{include:orient}}

{{include:delegated-reads}}
{{include:term-edit}}
{{include:grounding-artifact}}
{{include:injection}}

## Phase 0 — Establish MODE + scope `[anywhere]`

**One source, always: what the project SHIPS.** Derive rows from the code, compose file, scheduler, env set and DEV state — never from a spec; specs reach this command only through `docs/FEATURES.md` (Phase 3). Re-run after each build and whenever compose services, the scheduler, the `os.getenv` set or the schema head change.

Inputs — read and name them: `project.yaml::type` (registry `scaffold.py::SCAFFOLD_TYPES`) → the per-type row pack; `specs/services/<id>.yaml` `shape:` (in a project repo usually absent — read the hub's `/opt/fabrik/specs/services/<id>.yaml`, read-only; when neither exists or the hub holds only a `.yaml.draft`, say so and treat every `shape:` row as obligated) → Layer-3 obligations (a `false` flag makes its row `not obligated`, never absent); `docs/DECISIONS.md` → the exclusion set (quote the ruling verbatim as the row's WHAT cell); `docs/FEATURES.md` → the cross-check inventory; `docs/DEPLOYMENT.md` + `docs/OPERATIONS.md` → the fleet-AI sections to refresh.

**Starting state + check-before-create:** the scaffolder seeds `scripts/verify_prod_parity.py` as a `Status: DRAFT` stub that **exits 2** (an unfilled contract fails closed). **If `libs/health_probe/health_probe.py` is absent**, copy it from `/opt/fabrik-lib/health-probe/` into THIS repo's `libs/health_probe/` and say so. **If `scripts/verify_prod_parity.py` is absent** (the stub is project-OWNED and deliberately **never synced**): copy `/opt/fabrik/templates/scaffold/scripts/verify_prod_parity.py` into THIS repo's `scripts/` and commit it with this run. **A DRAFT stub is meant to be edited through — its existence is NOT a STOP.** Only a `Status: FROZEN` header is a STOP: say so, and on the operator's word proceed as a **re-freeze** — bump `Version`, never a silent overwrite.

Store types (`mobile-app`, `chrome-extension`, `office-extension`, `desktop-app`) have no VPS: their contract is the **provenance pack only** (submitted artifact ↔ tested SHA, store review state); skip Layers 2–4. `wordpress` runs no fabrik command.

## Phase 1 — Derive the denominators `[anywhere]`

**A denominator is DERIVED wherever derivable; where it must be declared it is CROSS-CHECKED against a derived proxy.**

| denominator | derive from (authoritative) | never from | when underivable |
|---|---|---|---|
| routes | `/openapi.json` from the started app (a `TestClient(app)` context, or the running DEV server) minus the framework paths (`/`, `/docs`, `/redoc`, `/openapi.json`, `/docs/oauth2-redirect`); state BOTH counts (`total / application`) | `FEATURES.md` prose · a flat `app.routes` read (misses nested `include_router` routers) · `grep include_router` | `UNVERIFIABLE (no introspection: <why>)` |
| services | `yaml.safe_load(compose)["services"]` ∪ the registrar-injected sidecars the `shape:` flags imply (a `watchdog` appears in no compose file) | compose read by eye · an indentation regex (counts `volumes:`/`networks:` keys) | — (always derivable) |
| env keys | `os.getenv(...)`/`os.environ[...]` names over `src/`, de-duplicated | `.env.example` alone | — |
| scheduled jobs | the live scheduler: `ir_cron` rows (Tryton), Beat/APScheduler registrations (scaffolded API), `crontab -l` (host job) | `RESILIENCE.md` §7 | `UNVERIFIABLE (scheduler not introspectable from here: <why>)` |
| schema head | the type's own mechanism: `alembic heads` (scaffolded API), `ir_module` state (trytond), a migrations dir count (node) | `db/schema.sql`, a doc | `UNVERIFIABLE (no migration tool: <why>)` — never a guess |
| state baseline | **DEV minus the declared exclusion set** — row counts, reference data, translations, filestore counts measured in DEV; exclusions from `docs/DECISIONS.md` | PROD (see the hazard rule) | a missing exclusion ruling is the one thing to RAISE (§ Question bar) |
| features | not derivable (`FEATURES.md` is prose) | — | cross-checked in Phase 3, never trusted alone |

Record every derivation as the COMMAND that produced it and its COUNT (`routes: 23 via app.routes`); a count without its command is a claim.

**Parallelism — UNCONDITIONAL, every run:** one native `general-purpose` grounder per surface (routes · jobs · env · services · schema), all dispatched in ONE message; `dispatch_headroom.py --units <N>` prints the seats, stamped BEFORE they go out with `python3 scripts/command_run.py dispatch --seats <n>` (D-191). **Never solo, never two:** fewer than three units still dispatches **THREE seats on DIFFERENT angles** (D-186). The exclusion-set judgement and every DEV measurement stay native.

## Phase 2 — Emit the contract `[anywhere]`

Write `scripts/verify_prod_parity.py` to the seeded template's shape:

- **Header block:** `# Status: DRAFT | FROZEN · Version: v<N> · Date: YYYY-MM-DD` and the freeze rule verbatim: *"Frozen — no agent adds, removes or re-derives a row not listed here. Any change = bump Version + re-freeze via `/fabrik-deploy-checklist`."*
- **Every row declares its SITE** — `@site("container")` for rows needing the database, redis or the internal network, `@site("host")` for `docker ps` / volume rows, nothing for the public surface (`hub`). The runner runs one leg per site and merges; a row sited where it cannot reach its target never resolves.
- **No self-referential row** (`expected` and `actual` from one source): it cannot be seen red. Only the `not obligated` markers may compare a constant to itself.
- **No snapshot fallback**: a declaration not derivable where the row runs makes the row `UNVERIFIABLE (<why>)`, never a remembered number.
- **Comparators by ONE test — "does this number change when a user does their job?"** No → compare EXACTLY. Yes → a **floor** (`comparator=lambda e, a: a >= e`) after the first deploy. **Derived stores that mirror a row set take the SAME comparator as the rows they mirror and switch together.** The first-deploy freeze may be exact everywhere; the contract names which rows switch to floors at the next bump, and coupled rows name each other.
- **Declare the container leg's service when it is not the app**: `CONTAINER_LEG_SERVICE = "<compose service>"` beside `SITES`, carrying Python AND the comparator's deps (`httpx`, `python-dotenv`) — read its Dockerfile first. A Node image has no `python` at all (`node-api`, `file-api`, `docusaurus`): site those rows on the hub or host leg or a Python sidecar, never the app container; `saas-skeleton` and `static-site` use their Python backend service.
- **One function per corpus row**, named by its lowercase corpus id (`l2_routes`), returning `{system, status, detail, expected, actual, match, compare_error}` with `system` = the corpus id. ⚠️ **A liveness row returns the three-key `{system, status, detail}` shape and NONE of the comparison keys**: ANY of `expected`/`actual`/`match` makes the vendored CLI treat it as a comparison row. `expected` is DERIVED at run time; a snapshot-only row says `mode: snapshot` in `detail`.
- **`UNVERIFIABLE (<why>)` rows are emitted, never dropped** — they stay in the denominator.
- **A `--rows-from` merge checks the leg files before counting them** (`_rows_for` calls `check_leg_rows`): each contract row must appear exactly once, with the three comparison keys all or none, a tri-state `match` and a known status, or the merge exits 64. An older contract merges legs unchecked until a re-freeze copies the check in.
- **The exclusion set is data** in the script, each entry with its ruling's `D-NNN`.
- **Read-only against the target.** A mutating row is `UNVERIFIABLE (mutating — needs a scoped payload + the operator's go)`, never executed.
- `--json` prints the rows; `--self-check` runs the FREEZE CHECKLIST (header parses · every function returns the row shape · every `UNVERIFIABLE` carries a why · the exclusion list names a ruling) and exits non-zero on a miss.

## Phase 3 — Features cross-check `[anywhere]`

**Every derived route maps to a shipped feature row, and every shipped feature row to a route.** **Walk EVERY table in `FEATURES.md` and take each table's status rule from ITS OWN header** — a `Status` column (a `✅ Shipped`-prefixed cell counts, variants too), else a non-empty `Endpoint / Module` cell; never assume a vocabulary or stop at the first table. **A route with no feature row, or a feature row with no route, is a FINDING** in the report and a row in the contract (`l2_features_crosscheck`, expected 0 unmatched).

## Phase 4 — Converge `[anywhere]` (the self-audit LOOP — iterate to a no-op)

Run passes until the Termination contract's closing round — `confirmed: 0`, the script's md5 unchanged. Each pass checks ALL of: **corpus coverage** (a row per applicable Layer 1–4 + pack check) · **derived denominators** (every `expected` traces to a Phase-1 command and count) · **features cross-check** · **executability** (`--json` runs; `--self-check` green) · **exclusions** (each names its ruling) · **red-seen** (Phase 5's table complete) · **docs** (the fleet-AI sections match the rows). List what you re-read and changed, then run one MORE pass.

## Phase 5 — SEE EVERY ROW RED `[anywhere]`

*A check that cannot fail is a defect.* Prove each row can fail before freezing:

1. Run the contract against DEV: every derived row `match: True`, every `UNVERIFIABLE` row `match: None` with its why.
2. Run the probes in a copy that carries the gitignored files the contract reads (`libs/` and `.env`); the copy isolates the code only — DEV itself is shared. Run the unmutated copy first as the control: a red the control also shows proves nothing. Then, per row CLASS, break DEV and re-run (drop a table's rows · rename an env key · stop the scheduler · remove a route · detach a service). **Each targeted row must report `match: False`** (or, for a raising comparator, `match: None` **with `compare_error` set**). Restore DEV after each.
3. A row that cannot be made to fail is REWRITTEN, or marked `UNVERIFIABLE (cannot be seen red: <why>)`.
4. A test added for the contract runs in the gate's pytest leg (the whole suite, one process) before freeze — where that leg is off (the gate prints `pytest (NOT RUN)`), run `python -m pytest tests/ -q` yourself and paste its tail.
5. Paste the red table: `row · how DEV was broken · result`. **A contract with no red table is DRAFT** whatever its header says.

## Phase 6 — Freeze + wire the truth `[anywhere]`

- **The freeze (and every re-freeze bump) is a Status flip — mint its `docs/DECISIONS.md` row in the SAME change.**
- Set the header `Status: FROZEN · Version: v<N> · Date`, freeze rule verbatim; this write is a post-convergence action, exempt from the no-op rule.
- **Refresh the fleet-AI sections of `docs/DEPLOYMENT.md` and `docs/OPERATIONS.md`** (D-065) from the Phase 1 inventory, touching ONLY the sentinel-marked sections the template seeds. **If the sections are absent** (an older project), ADD them first, verbatim from `templates/scaffold/docs/DEPLOYMENT_TEMPLATE.md` § *Fleet-AI interface — what to deploy* and `OPERATIONS_TEMPLATE.md` § *5b. Fleet-AI interface — what runs*, then fill the cells. ⚠️ **HAZARD — derive these from CODE + SPEC + DEV, never from PROD:** the docs declare what SHOULD be true, the verify run reports what IS.

## Phase 7 — Hand off `[anywhere]`

- The contract is `FROZEN` → **`/fabrik-release`**, whose VPS-path precondition BLOCKS on `DRAFT`. State this and stop.
- A run that could derive only the identity rows still freezes; say which layers await code.
- **On a version BUMP:** the Re-freeze close-out below names what the next `/fabrik-deploy-verify` must re-run.

{{include:questionbar}}
## Guardrails — never
- Derive a row, a count or a doc section from PROD — the deployed state is the thing under test.
- Drop a row you cannot assert — emit it `UNVERIFIABLE (<why>)`; a shrunk denominator hides the gap.
- Freeze on a pass whose reconciliation made edits, or on a contract with no red table.
- Invent a check with no corpus id, or read `match: None` as agreement anywhere.
- Execute a mutating row, or read PROD data, from this command — it authors; `/fabrik-deploy-verify` runs.
- Hand off to `/fabrik-release` while the header is `DRAFT`.

## Re-freeze close-out (runs ONLY when this run was a version bump N→N+1 on an already-FROZEN contract)

1. **Diff the script against its pre-run version** (`git diff HEAD -- scripts/verify_prod_parity.py`) and extract the changed row ids and expected values.
2. **Emit a Downstream impact table**: `changed row → what the next verify must re-run → why`. Zero changed rows is a stated result, never an omitted one.
3. **The NEXT line becomes the owed re-verify** when the impact is non-empty: `/fabrik-deploy-verify` against the bumped Version, with the changed rows named as its arguments.


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

Next command: `/fabrik-release` — its VPS-path precondition reads the `FROZEN` header. On a version BUMP
with downstream impact: `/fabrik-deploy-verify` re-run against the bumped contract, changed rows named.

{{include:close-chain}}
