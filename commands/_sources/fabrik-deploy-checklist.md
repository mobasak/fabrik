---
description: Author the project's deployment-verification CONTRACT — `scripts/verify_prod_parity.py`: one runnable check + expected result per corpus row, every denominator DERIVED from the system (route table · compose ∪ sidecars · `os.getenv` · scheduler · schema head), features cross-checked, DEV-minus-exclusions baseline, every row SEEN RED before `FROZEN`; refreshes the fleet-AI sections of `DEPLOYMENT.md` + `OPERATIONS.md` from CODE + SPEC + DEV, never PROD. TRIGGER — EN: "author the deploy checklist", "what must prod contain", "freeze the parity contract"; TR: "deploy kontrol listesini yaz", "prod'da ne olmalı". SKIP: running it against the live deploy (→ /fabrik-deploy-verify) · field naming (→ /fabrik-data-contract) · the feature inventory (→ /fabrik-features). Stage: 6-release.
argument-hint: "[optional: a subsystem to scope the rows — omit to derive the whole deployed product]"
---

> **POOL OFF — D-181.** Run every fan-out this command names natively (Claude Task subagents: `fabrik-reviewer` · `fabrik-researcher` · `fabrik-gui` · general-purpose; same unit split, same author-blind rule) and skip every flywheel back-fill; every `fanout` / `pick_models` / `set_quality` / `record_agent_run` / `results_table` instruction is SUSPENDED. Never write `NO-POOL:` for it: `check_subagent_flywheel.py`'s pool-or-declare layer stands down (`_POOL_POLICY_ON = False`, D-182). Canonical: `62-using-subagents.md` § Dispatch policy.

Author this project's **deployment-verification contract**: executable rows declaring what the deployed system must contain, so a deploy is certified against what was BUILT, not liveness alone.

**You are at step 1 of the chain below — previous: end-to-end certification (`/fabrik-user-test` · `/fabrik-service-test`, green on the build you are about to freeze) · next: `/fabrik-release`.**

{{include:deploy-chain}}

**HARD GATE: no `/fabrik-release` READY verdict and no `DEPLOY CONFIRMED` against a contract that is still `DRAFT`.** A contract-less or unfrozen project reaches `UNVERIFIED` at verify time (terminal, not success) — the signal to run this command.

**Where this runs:** project-side, in the project's own repo — every phase is `[anywhere]`, no fleet SSH. The contract derives from CODE + SPEC + DEV; **PROD is never read by this command** (deriving a declaration from the deployed state launders drift into documentation).

{{include:run-record}}
{{include:orient}}

{{include:delegated-reads}}
{{include:term-edit}}
{{include:grounding-artifact}}
{{include:injection}}

## Phase 0 — Establish MODE + scope `[anywhere]`

**One source, always: what the project SHIPS.** Derive rows from the code, compose file, scheduler, env set and DEV state — never from a spec; specs reach this command only through `docs/FEATURES.md`, the cross-check inventory Phase 3 walks both ways (a feature a spec promised and nothing ships is a finding there). Run it when the project is ready to deploy, and again whenever compose services, the scheduler, the `os.getenv` set or the schema head change; a project with little code yet simply gets few rows (the Layer-1 identity rows need only git) and the same run, re-run after each build, grows the contract — there is no separate "fresh" or "spec" path to choose.

Inputs — read and name them: `project.yaml::type` (registry `scaffold.py::SCAFFOLD_TYPES`) → the per-type row pack; `specs/services/<id>.yaml` `shape:` (in a project repo usually absent — read the hub's `/opt/fabrik/specs/services/<id>.yaml`, read-only; the hub copy wins when both exist, and when neither exists or the hub holds only a `.yaml.draft`, say so and treat every `shape:` row as obligated) → Layer-3 obligations (a `false` flag makes its row `not obligated`, never absent); `docs/DECISIONS.md` → every ruling about what ships and what does not (the exclusion set lives here; the ruling is the row's WHAT cell — 4th column, after `id | when | who` — quote it verbatim beside the exclusion list); `docs/FEATURES.md` → the cross-check inventory; `docs/DEPLOYMENT.md` + `docs/OPERATIONS.md` → the fleet-AI sections to refresh.

**Starting state + check-before-create:** the scaffolder seeds `scripts/verify_prod_parity.py` as a `Status: DRAFT` stub that **exits 2** (an unfilled contract fails closed); the fleet sync seeds the vendored `libs/health_probe/` it imports (VENDORED_DIRS). **If `libs/health_probe/health_probe.py` is absent**, copy it from `/opt/fabrik-lib/health-probe/` into THIS repo's `libs/health_probe/` (a read of the sibling repo and a write in your own tree — not a cross-repo edit), say so in the report, and carry on. **If `scripts/verify_prod_parity.py` is absent** (every project scaffolded before 2026-09-02 — the stub is seeded by the scaffolder's `SCRIPT_FILES` at scaffold time and is deliberately **never synced**: the contract is project-OWNED and committed): copy `/opt/fabrik/templates/scaffold/scripts/verify_prod_parity.py` into THIS repo's `scripts/` (a read of the hub, a write in your own tree), commit it with this run, and carry on — it is the same DRAFT stub the scaffolder would have seeded. **A DRAFT stub is meant to be edited through — its existence is NOT a STOP.** Only a `Status: FROZEN` header is a STOP: say so, and on the operator's word proceed as a **re-freeze** — bump `Version`, never a silent overwrite.

Store types (`mobile-app`, `chrome-extension`, `office-extension`, `desktop-app`) have no VPS: their contract is the **provenance pack only** (submitted artifact ↔ tested SHA, store review state) — say so and skip Layers 2–4. `wordpress` runs no fabrik command.

## Phase 1 — Derive the denominators `[anywhere]`

**A denominator is DERIVED wherever derivable; where it must be declared it is CROSS-CHECKED against a derived proxy; each source below is authoritative, and the prose next to it is never the sole basis.**

| denominator | derive from (authoritative) | never from | when underivable |
|---|---|---|---|
| routes | `/openapi.json` from the started app (a `TestClient(app)` context, or the running DEV server) minus the framework paths (`/`, `/docs`, `/redoc`, `/openapi.json`, `/docs/oauth2-redirect`); state BOTH counts (`total / application`) | `FEATURES.md` prose · a flat `app.routes` read (UNDER-COUNTS: `include_router` routers sit nested under router objects whose own `.routes` must be walked — measured: flat `app.routes` gave 3 application routes while `/openapi.json` gave 27 paths) · a `grep include_router` (a composed `v1_router` carries its prefix on the parent, `prefix="/internal/v1"`, so the grep returns nothing) | `UNVERIFIABLE (no introspection: <why>)` |
| services | `yaml.safe_load(compose)["services"]` ∪ the registrar-injected sidecars the `shape:` flags imply (a `watchdog` appears in no compose file) | compose read by eye · an indentation regex (counts `volumes:`/`networks:` keys as services — measured: 6 for 4) | — (always derivable) |
| env keys | `os.getenv(...)`/`os.environ[...]` names over `src/` (every key, de-duplicated) | `.env.example` alone | — |
| scheduled jobs | the live scheduler: `ir_cron` rows (Tryton), Beat/APScheduler registrations (scaffolded API), `crontab -l` (host job) | `RESILIENCE.md` §7 | `UNVERIFIABLE (scheduler not introspectable from here: <why>)` |
| schema head | the type's own mechanism: `alembic heads` (scaffolded API), `ir_module` state (trytond), a migrations dir count (node) | `db/schema.sql`, a doc | `UNVERIFIABLE (no migration tool: <why>)` — never a guess |
| state baseline | **DEV minus the declared exclusion set** — row counts, reference data, translations, filestore counts measured in DEV; exclusions from `docs/DECISIONS.md` | PROD (see the hazard rule) | a missing exclusion ruling is the one thing to RAISE (§ Question bar) |
| features | not derivable (`FEATURES.md` is prose) | — | cross-checked in Phase 3, never trusted alone |

Record every derivation as the COMMAND that produced it and its COUNT (`routes: 23 via app.routes` · `services: 4 + 1 sidecar` · `env keys: 32 distinct over 49 sites`); a count without its command is a claim.

**Parallelism — UNCONDITIONAL, every run:** one native `general-purpose` grounder per surface (routes · jobs · env · services · schema) per § Subagents, all dispatched in ONE message — the surface count is the PARTITION; `dispatch_headroom.py --units <N>` prints the seats, stamped BEFORE they go out with `python3 scripts/command_run.py dispatch --seats <n>` so sibling sessions subtract them (D-191). **Never solo, never two:** a surface with fewer than three units still dispatches **THREE seats on DIFFERENT angles** over it (1 seat found 0; 3 over the same surface found 0/5/0, and the 5 held a real fail-open; D-186). The exclusion-set judgement and every DEV measurement stay native.

## Phase 2 — Emit the contract `[anywhere]`

Write `scripts/verify_prod_parity.py` to the seeded template's shape:

- **Header block:** `# Status: DRAFT | FROZEN · Version: v<N> · Date: YYYY-MM-DD` and the freeze rule verbatim: *"Frozen — no agent adds, removes or re-derives a row not listed here. Any change = bump Version + re-freeze via `/fabrik-deploy-checklist`."*
- **Every row declares its SITE** — `@site("container")` for rows needing the database, redis or the internal network, `@site("host")` for `docker ps` / volume rows, nothing for the public surface (`hub`, the default). The runner runs one leg per site and merges; a row placed at a site that cannot reach its target is a row that can never resolve (tryton-crm's first freeze: 15 of 27 rows were DB/host rows left at the hub site — permanently UNVERIFIABLE).
- **No self-referential row** (`expected` and `actual` from one source): it cannot be seen red. The only rows allowed to compare a constant to itself are the `not obligated` markers, and only because `NOT_OBLIGATED` removes them from the denominator.
- **No snapshot fallback**: a declaration not derivable where the row runs makes the row `UNVERIFIABLE (<why>)`, never a number remembered from an earlier run.
- **Comparators by ONE test, never by an example list — "does this number change when a user does their job?"** No → compare EXACTLY. Yes → a **floor** (`comparator=lambda e, a: a >= e`) after the first deploy. **Derived stores that mirror a row set take the SAME comparator as the rows they mirror and switch together.** The first-deploy freeze may be exact everywhere; the contract names which rows switch to floors at the next bump, and coupled rows name each other.
- **Declare the container leg's service when it is not the app**: `CONTAINER_LEG_SERVICE = "<compose service>"` beside `SITES`; that container must carry Python AND the comparator's runtime deps (`httpx` at module level, `python-dotenv` for the `.env` load) — read its Dockerfile first; the runner reads this from `--header` rather than assuming. A Node image has no `python` at all (`node-api` and `file-api` ship `Dockerfile.node`, `docusaurus` its `Dockerfile.j2`): site those rows on the hub or host leg, or declare a Python sidecar as the leg — never the app container, where every row would read UNVERIFIABLE at the first verify run. `saas-skeleton` and `static-site` pair a Node frontend with a Python backend service (`scaffold.py::_scaffold_saas_backend`) — there the backend IS the leg; declare it.
- **One function per corpus row**, named by its lowercase corpus id (`l1_identity_sha`, `l2_routes`, `l2_state_companies`, `l3_postgres`, … — lowercase: the hub's ruff N802 refuses capitalised function names), returning the `health-probe` comparison row shape `{system, status, detail, expected, actual, match, compare_error}` with `system` = the corpus id. ⚠️ **A liveness row returns the three-key `{system, status, detail}` shape and NONE of the comparison keys**: ANY of `expected`/`actual`/`match` makes the vendored CLI treat it as a comparison row (`_COMPARISON_KEYS`, a disjunction on purpose), so a liveness row emitted with `match: None` would FAIL the contract. `expected` is DERIVED at run time; a snapshot-only row says `mode: snapshot` in `detail` — the legal *degraded* form, reported as such, never silently.
- **`UNVERIFIABLE (<why>)` rows are emitted, never dropped** — they stay in the denominator. The store-type and static-type packs ship `UNVERIFIABLE` by default; a wrong check that silently passes is worse than a stated gap.
- **A `--rows-from` merge checks the leg files before counting them** (`_rows_for` calls `check_leg_rows`): a leg file could otherwise reach CONFIRMED through row ids, counts, comparison keys or `match`, so each contract row must appear exactly once, with the three comparison keys all or none, a tri-state `match` and a known status, or the merge exits 64. An older contract merges legs unchecked until a re-freeze copies the check in.
- **The exclusion set is data** in the script, each entry with its ruling's `D-NNN`, applied to the DEV baseline so the runner and a reader see what was excluded.
- **Read-only against the target.** A mutating row is `UNVERIFIABLE (mutating — needs a scoped payload + the operator's go)`, never executed.
- `--json` prints the rows; `--self-check` runs the FREEZE CHECKLIST (header parses · every function returns the row shape · every `UNVERIFIABLE` carries a why · the exclusion list names a ruling) and exits non-zero on any miss.

## Phase 3 — Features cross-check `[anywhere]`

**Every derived route maps to a shipped feature row, and every shipped feature row to a route.** **Walk EVERY table in `FEATURES.md` and take each table's status rule from ITS OWN header** — a `Status` column (a `✅ Shipped`-prefixed cell counts, variants too), else a non-empty `Endpoint / Module` cell; never assume a vocabulary or stop at the first table. **A route with no feature row, or a feature row with no route, is a FINDING** in the report and a row in the contract (`l2_features_crosscheck`, expected 0 unmatched).

## Phase 4 — Converge `[anywhere]` (the self-audit LOOP — iterate to a no-op)

Run repeated passes until the Termination contract's closing round — `confirmed: 0`, the script's md5 unchanged. Each pass checks ALL of: **corpus coverage** (a row per applicable Layer 1–4 + pack check, `UNVERIFIABLE` where it must be) · **derived denominators** (every `expected` traces to a Phase-1 command and count) · **features cross-check** (both directions) · **executability** (`--json` runs; `--self-check` green) · **exclusions** (each names its ruling) · **red-seen** (Phase 5's table complete) · **docs** (the fleet-AI sections match the rows). List what you re-read and changed, then run one MORE pass.

## Phase 5 — SEE EVERY ROW RED `[anywhere]`

*A check that cannot fail is a defect.* Prove each row can fail before freezing:

1. Run the contract against DEV: every derived row `match: True`, every `UNVERIFIABLE` row `match: None` with its why.
2. Run the probes in a copy that carries the gitignored files the contract reads (`libs/` and `.env` — a fresh worktree lacks them, and every comparison row there reads UNVERIFIABLE for the wrong reason); the copy isolates the code only — DEV itself is shared. Run the unmutated copy first as the control: a red the control also shows proves nothing. Then, per row CLASS, break DEV and re-run (drop a table's rows · rename an env key · stop the scheduler · remove a route · detach a service). **Each targeted row must report `match: False`** (or, for a raising comparator, `match: None` **with `compare_error` set**). Restore DEV after each.
3. A row that cannot be made to fail is REWRITTEN, or marked `UNVERIFIABLE (cannot be seen red: <why>)`.
4. A test added for the contract runs in the gate's pytest leg (the whole suite, one process) before freeze — where that leg is off (the gate prints `pytest (NOT RUN)`), run `python -m pytest tests/ -q` yourself and paste its tail: the first row that needs the vendored probe loads the project's `.env` into `os.environ`, and that state reaches every later test in the process.
5. Paste the red table: `row · how DEV was broken · result`. **A contract with no red table is DRAFT** whatever its header says.

## Phase 6 — Freeze + wire the truth `[anywhere]`

- **The freeze (and every re-freeze bump) is a Status flip — mint its `docs/DECISIONS.md` row in the SAME change** (classify at mint; a contract freeze is normally reversible-by-re-freeze).
- Set the header `Status: FROZEN · Version: v<N> · Date`, freeze rule verbatim (a header that still carries a trailing `· Mode: …` from an earlier freeze parses, and the re-freeze drops it); this write is a post-convergence action, exempt from the no-op rule — measured on the body, not the flip.
- **Refresh the fleet-AI sections of `docs/DEPLOYMENT.md` and `docs/OPERATIONS.md`** (D-065) from the Phase 1 inventory, touching ONLY the sentinel-marked fleet-AI sections the template seeds; the project's own runbook prose is theirs. **If the sections are absent** (a project scaffolded before 2026-09-02 — the templates only reach new scaffolds), ADD them first, verbatim from `templates/scaffold/docs/DEPLOYMENT_TEMPLATE.md` § *Fleet-AI interface — what to deploy* and `OPERATIONS_TEMPLATE.md` § *5b. Fleet-AI interface — what runs*, then fill the cells. ⚠️ **HAZARD — derive these from CODE + SPEC + DEV, never from PROD:** *"prod has 0 companies, therefore document 0 companies"* makes an empty-database certification self-consistent and still wrong; the docs declare what SHOULD be true, the verify run reports what IS.
- Gate coupling: a change to compose services, the scheduler, the `os.getenv` set or the schema head without a Version bump is drift the runner will surface as `match: False` on the next verify.
- No enforcement check grades this header today — a deliberate, recorded deferral (`docs/STRATEGIC_BACKLOG.md`), not an oversight.

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
