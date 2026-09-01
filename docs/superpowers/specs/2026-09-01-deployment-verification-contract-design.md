# Deployment Verification Contract — design spec

Status: DRAFT
Date: 2026-09-01
Author: fleet (hub)
Stage: 1-design · successor: `/fabrik-spec-review`

## The problem, in the operator's words

> *"you are deploying but you dont know the project well you make mistakes and you cant compare what
> is developed and what is deployed, this is my actual pain."*

And the bar: *"i want my projects 100% tested after deployment."*

**The proof that this is real, from this session:** I certified tryton-crm `DEPLOY CONFIRMED LIVE` with
**every check green** — DNS, health 200, 6/6 registrars, Gatus green, logs clean, routes serving — while
the product contained **none** of its 84 datasheets, 42 products, or 16,289 translations. Production held
0 companies; dev held 760. Nothing in the fleet's verification could fail on that, because nothing
anywhere declared what the deployed system was supposed to contain.

## Intake Inventory

| I# | Item (anchored) | Disposition | Where |
|---|---|---|---|
| I1 | *"i want each project be able to deploy their own development, you will only manage the infra"* | **IN** (partial) | § Ownership split — verification moves to the project; deploy *execution* is deferred, see I1b |
| I1b | Moving `fabrik apply` itself to projects | **OUT-OF-SCOPE** | Separate concern: registrars mutate shared fleet files (`/opt/monitoring/...`, backrest config) and the autoheal window is a single global lock — 43 concurrent writers is its own design. **Destination:** § Deferred, row 1; needs its own spec before any repo self-deploys |
| I2 | *"you … cant compare what is developed and what is deployed, this is my actual pain"* | **IN** | § The three failure modes · § Layer 2 Completeness — this is the spec's centre |
| I3 | *"do we need a fabrik command for verification by the developer?"* | **IN** (answered: no new command) | § Approach A vs B — extend `/fabrik-deploy-verify`, per *"Before new scripts: Grep scripts/. Extend, don't duplicate"* |
| I4 | *"can we use developer agent to uses strengthened /fabrik-deploy-verify"* | **IN** | § Ownership split — measured: the command is already box-wide and the SSH key is user-level |
| I5 | *"i want project agent validate its implementation fully, complete, up, and running"* | **IN** | § Verdict algebra — the three words become three separately-failable verdicts |
| I6 | *"if you were to agent who created the project what would you check in the vps"* | **IN** | § The check corpus, Layers 1–4 |
| I7 | *"does our /fabrik-deploy-verify check all these?"* → measured: no | **IN** | § Gap measurement — 10 of 10 author-layer checks absent |
| I8 | tryton-crm's checklist A–H (data parity · async machinery · external deps · config parity · behaviour parity · UI truth · durability · security) | **IN** | § The check corpus — adopted wholesale, mapped per layer |
| I9 | *"for every type of project take your findings, take tryton findings DO NOT SKIP A SINGLE thing"* | **IN** | § Per-type packs — all 13 `SCAFFOLD_TYPES` enumerated, none omitted |
| I10 | *"utilize all vps infra where applicable (glitchtip, backups, grafana, etc all)"* | **IN** | § Layer 3 Infra utilization — every `shape:` registrar proven *working*, not merely present |
| I11 | *"up and running as like in the wsl, all services are up, db current, external services there"* | **IN** | § Layer 1 Identity (db current) · § Layer 4 Behaviour (external services) |
| I12 | *"must follow same structure as like /fabrik-plan-after-chat"* | **IN** | § Build route — spec → review → epic, phased with gates |
| I13 | *"i want my projects 100% tested after deployment"* | **IN** | § Verdict algebra — "100%" made falsifiable via declared denominators |
| I14 | My measurement: `/fabrik-deploy-verify` has **zero** identity checks (`rev-parse` 0, `alembic` 0, `digest` 0) | **IN** | § Layer 1 — the cheapest, most universal missing layer |
| I15 | tryton-crm's three failure modes: *present-but-inert · different-by-config · reachable-but-wrong* | **IN** | § The three failure modes — adopted as the organising axis, replacing my layer-first framing |
| I16 | tryton-crm: *"the doc a verifier would check against is itself partly untrue"* (RESILIENCE.md template residue) | **IN** | § Authoritative vs descriptive sources |
| I17 | My measurement: 37 of 43 repos carry no `specs/services/*.yaml` | **IN** | § Onboarding — blocks Phase 0 for 86% of the fleet |
| I18 | D-065 (today): `OPERATIONS.md` + `DEPLOYMENT.md` are fleet-AI interfaces, machine-consumable | **IN** | § Declaration sources — consume these, do not invent a parallel artifact |
| I19 | D-017 (tryton-crm): production migrates the dev DB — "empty is expected" was **my** assumption | **IN** | § Declaration sources — the project's decision ledger is a verification input |
| I20 | tryton-crm: *"a backup plan configured is not a backup taken"* + cert-renewal-survives-restart | **IN** | § Layer 3 — durability armed, two named checks |
| I21 | Self-grading risk — the project verifies work it produced | **IN** | § Ownership split — thin hub cross-check retained |
| I22 | tryton-crm's `RESILIENCE.md` converge pass | **OUT-OF-SCOPE** | Their repo's doc debt, not this contract's. **Destination:** named in their reply thread; belongs to their `/fabrik-doc-converge` |

**Intake: 22 items — 20 IN, 2 OUT-OF-SCOPE (each with a named destination), 0 ASK.**

## Routing verdict (BLOCKING gate, stated either way)

**This spec is feature-scale; the BUILD it implies is epic-scale.** Decomposed deliberately:

- **HERE (feature-scale):** the *contract* — the failure-mode taxonomy, the ownership split, the
  declaration-source rules, the parity-script interface, and the verdict algebra. One artifact, one
  operator-carried plan.
- **ROUTED OUT (epic):** the *implementation* — 13 per-type check packs, the hub-side spine, and
  onboarding 37 repos. Needs a ticket store and dispatched agents → `docs/orchestrator/epic-to-ticket-workflow/00-trigger-fabrik.md`.

Specifying the checklist before fixing the contract produces a list nobody can implement. That ordering
is the whole reason this spec exists separately.

## Duplicate check (BLOCKING, stated either way)

Four existing verification surfaces, read before designing. **None duplicates this; the boundaries are real:**

| surface | scope | why it is not this |
|---|---|---|
| `/fabrik-deploy-verify` | hub-side liveness against prod | **This spec extends it.** Measured gap below |
| `/fabrik-service-test` | headless end-to-end gauntlet | runs against **dev/local**, certifies the product — never compares dev↔prod |
| `/fabrik-user-test` | GUI gauntlet | same: dev-side certification |
| `/fabrik-release` | pre-deploy readiness | fires **before** the deploy; cannot see prod |

**Nothing in the fleet compares developed↔deployed.** That is the vacancy.

## The measured gap

Every author-layer check, grepped individually against `~/.claude/commands/fabrik-deploy-verify.md`
(single terms — an earlier alternation-grep of mine mislabelled hits and is corrected here):

```
rev-parse 0 · alembic 0 · "image digest" 0 · openapi 0 · getenv 0 · cron 0
"write path" 0 · "write-path" 0 · "read back" 0 · digest 1 (incidental)
```

Phase 6 caps at *"first 3 `docs/FEATURES.md` rows"* and is advisory — a sample, not a denominator, that
cannot fail a verdict. **The command has never once verified that the code running on vps1 is the code
that passed tests.**

## The three failure modes (the organising axis — tryton-crm's, adopted)

Organise by **what each check catches**, not by what is easy to run. Every check in the corpus must name
which mode it closes, or it does not earn its place.

| mode | it looks like | live proof |
|---|---|---|
| **Present but inert** | registered, enabled, never fires | a healthcheck reporting healthy through a **22-hour database outage**; an init script baked into an image that nothing invoked; a Traefik router registered + enabled matching nothing |
| **Different by config** | a missing env var silently takes a code default | `REDIS_URL` absent for a whole run; `SALE_CREATE_STATE` / `EXPOSE_AMOUNTS_TO_CUSTOMER` changing product behaviour without erroring |
| **Reachable but wrong** | 200, wrong content | `/brand` returning **200 with a null body** on total dependency failure — which made its own smoke test pass |

⚠️ **The fourth mode this spec adds: ABSENT AND UNDECLARED.** An empty production database is none of the
three — it is *correct by every declared standard, because nothing declared the standard*. This is I2, the
operator's actual pain, and it is closed only by a denominator.

## Ownership split

**Verification moves to the project agent; the hub keeps a thin independent cross-check.**

Measured, not assumed: `~/.claude/commands/fabrik-deploy-verify.md` is user-level (box-wide, every project
session has it), and `~/.ssh/id_ed25519` is owned by `ozgur` — the same user every project session runs as.
The command's own doc says it is hub-side *"because the hub carries fleet SSH creds"*; **that is convention,
not enforcement.** No credential boundary exists on this box.

The project agent is the right owner because every mistake I made this session was missing *project*
knowledge, not missing infra skill — I probed a bare `/activities` because I did not know the router prefix
is `/internal/v1`; a project agent could not make that error.

**But self-grading is real** (I21). The hub retains the fleet-health half. What made today's migration
trustworthy was not either party's diligence — it was **two independent measurements agreeing to the row**
(their dry-run and mine, both 193,664 rows). That property is worth preserving structurally.

## Declaration sources — authoritative vs descriptive

tryton-crm's caveat (I16) is load-bearing: *the doc a verifier checks against may itself be untrue.*
Their `RESILIENCE.md` still carries scaffold-template residue (WordPress cron, a YouTube example).

**Rule: derive from the system, never from prose.**

| purpose | AUTHORITATIVE (derive from) | DESCRIPTIVE (never the sole basis) |
|---|---|---|
| scheduled jobs | `ir_cron` rows / the live scheduler | `RESILIENCE.md` §7 |
| routes | the app's own introspection (`/openapi.json`, `urls.py`) | `FEATURES.md` prose |
| schema | `alembic current` / `pg_catalog` | `db/schema.sql` |
| env keys the code needs | `grep os.getenv` over source | `.env.example` |
| what must be deployed | **`DEPLOYMENT.md` + `OPERATIONS.md` (D-065 — machine-consumable fleet-AI interfaces)** | — |
| what state must exist | the project's decision ledger + parity contract | assumption |

D-065 (I18) is why the declaration half largely **already exists** and must be consumed rather than
duplicated. D-017 (I19) is why the project's `docs/DECISIONS.md` is a verification input: my "empty is
expected for a fresh deploy" was an assumption contradicted by a ruling I never read.

## The check corpus

### Layer 1 — Identity (universal, all 13 types) · catches *different-by-config*
1. deployed SHA == the SHA whose tests passed (`git rev-parse HEAD` on prod vs green CI commit)
2. migration head == repo head (`alembic current` vs `alembic heads`)
3. image digest == the built digest — a silently-failed rebuild runs old code under a new commit
4. lockfile hash == tested dependency set

**Nothing below Layer 1 means anything if it fails.** Everything verified today was true of *something*;
it was never proven true of *my build*.

### Layer 2 — Completeness (per-type) · catches *absent-and-undeclared*
5. **route-table diff** — live `/openapi.json` vs the code's registered routes. Makes probe-path errors
   structurally impossible: the service *tells* you its prefix
6. every `os.getenv` key present in the remote `.env` (verify the **set**, never the values)
7. scheduled jobs: declared count present **and `next_call` advancing** — a cron registered but never
   fired is indistinguishable from a healthy one (*present-but-inert*)
8. queue: enqueue one real task, confirm the worker **consumed** it — not that the container is up
9. **state contract** — the project's expected-state assertions (row counts, reference data, file counts)
10. filestore/asset count + **one artefact fetched by content** — a row whose file is missing reads
    identical to one whose file is there until someone clicks it

### Layer 3 — Infra utilization (I10; `shape:`-gated) · catches *present-but-inert*
11. Gatus **green**, not merely registered
12. Prometheus **actively scraping** (target `up 1`)
13. GlitchTip receives a **deliberately-emitted** error
14. **a backup TAKEN with a timestamp** — a plan configured is not a snapshot taken (I20)
15. **restore rehearsed at least once**
16. TLS/cert config **persisted on disk and surviving a restart** — a DNS-01 resolver added at runtime
    renews nothing, and every tenant URL breaks in ~60 days with no warning (I20)
17. Authelia challenge on admin routes; Loki receiving logs; memory limits declared

### Layer 4 — Behaviour (per-type) · catches *reachable-but-wrong*
18. **every *Shipped* `FEATURES.md` row** exercised, count stated — no sampling
19. **one real write path**, created and read back, then removed
20. **one deliberate failure** — bad token → 401, missing record → 404. The `/brand` 200-with-null-body
    class is invisible to positive tests only
21. **the money path end-to-end** where one exists (quote → sequence format → PDF → email → delete the
    probe record) — one scratch record, deliberately **not** the full gauntlet, which would recreate the
    test debris we spent a day removing
22. external dependencies probed **from inside the containers** with real calls, not port checks —
    TLS-authenticated SMTP that accepts the connection and rejects the sender identity is a live failure
    mode already debugged once
23. i18n/UI truth: translations **rendering**, not merely 8,289 rows existing — that precise defect shipped before

### Per-type applicability (all 13 `SCAFFOLD_TYPES` — none omitted, I9)

| type | Layers 1/3 | notable delta |
|---|---|---|
| `python-api`, `python-api-gpu`, `node-api`, `file-api` | full | route-table diff native |
| `file-worker` | full | **no HTTP** — prove by consuming: enqueue → drain. Liveness nearly meaningless |
| `saas-skeleton` | full | + tenant isolation: two tenants, one cannot read the other |
| `static-site`, `docusaurus` | partial | build-output hash vs served content — a stale CDN serves 200 forever |
| `mobile-app`, `chrome-extension`, `office-extension`, `desktop-app` | **N/A — no VPS** | store/artifact provenance: submitted binary from the tested SHA |
| `wordpress` | out of fabrik | `/opt/wpf` archived 2026-08-07; `scaffold.py` raises |

## Verdict algebra (I5, I13)

*Fully, complete, up, and running* becomes **three separately-failable verdicts**, and "100%" becomes
falsifiable:

- **UP** — Layers 1+3. **COMPLETE** — Layer 2. **RUNNING** — Layer 4.
- `CONFIRMED` requires **all three PASS**. Any FAIL ⇒ `VERIFICATION FAILED`.
- **`not obligated` is a first-class verdict**, distinct from `not checked` — asserting Meilisearch on
  `has_search_feature: false` is a false failure. `shape:`-driven, never assumed.
- **Every percentage carries its denominator.** "18 of 18 Shipped rows exercised" is a claim; "looks
  complete" is not. A zero without a denominator is indistinguishable from having looked nowhere.
- **A check that cannot fail is a defect.** Every check must be **seen red** against a deliberately broken
  state, or it does not count — watched-fail-first applied to verification itself. This is what a
  healthcheck surviving a 22-hour outage teaches.
- **No contract ⇒ cannot reach `CONFIRMED`.** Not a silent pass, not a warning.

## fabrik-lib ladder (Phase 1b)

| capability | verdict | basis |
|---|---|---|
| external-dependency probing (Layer 4 #22) | **VENDOR + ENHANCE** | `health-probe/` — *"generic Postgres/Redis/HTTP-auth probes + **injectable project probes**; uniform `{system,status,detail}`"*, already backing a CLI with exit-code semantics. The injectable-probe seam **is** the project-supplied extension point this design needs; enhancements (dev↔prod diff mode) go back upstream per the ladder |
| identity checks (Layer 1) | **BUILD** — project-local | trivial git/alembic/digest reads; fails the ≥2-type generic bar |
| the parity contract runner | **BUILD** → **🆕 fabrik-lib candidate** | generic (no business logic) · used by ≥2 types · small interface (`expected` vs `actual` → diff) · nothing covers it · would have saved this project a day |

**Composition, not reinvention:** vendored `health-probe` for dependency probes + a thin parity runner +
per-type packs.

## Approaches

**A — New developer-side command.** Rejected: violates *"Extend, don't duplicate"*; leaves
`/fabrik-deploy-verify` still reaching `CONFIRMED LIVE` on an empty database, so the defect survives beside
the fix.

**B — Extend `/fabrik-deploy-verify`; project-run; contract-driven.** ✅ **RECOMMENDED.** Reuses the
existing Phase-6 hook (already a project-artifact-driven phase, merely too weak), keeps one verification
surface, and needs no credential movement — **the artifact travels, not the SSH key**, exactly as
`battery-expected.txt` governed my verdict today without tryton-crm ever touching vps1.

**C — Hub-authored per-type checks, no project contract.** Rejected on evidence: *"quote a sale → confirm
DDMMYYYY-seq → render PDF → send email"* is unknowable to a fleet command across 43 repos. The hub cannot
hold that knowledge; it can only demand, run, and adjudicate the project's own proof.

## Open questions for `/fabrik-spec-review`

1. **Contract shape: snapshot vs derived.** `battery-expected.txt` (frozen values, goes stale) vs
   `cleanup_d017.py` (derives from `pg_catalog` at runtime, never stale, more work per project).
   *Leaning derived*, because both artefacts that worked today converged on it.
2. **Rollout for 37 spec-less repos** — does a missing contract **block** the deploy or mark it
   `unverified`? Blocking is honest and stops 86% of the fleet until each writes one.
3. Where the contract lives — `docs/deploy-contract.md`, or a script under `scripts/`?
4. Does the hub cross-check stay mandatory, or become opt-in once a project's contract matures?

## Deferred (named, not dropped)

1. **Moving `fabrik apply` to projects (I1b)** — registrars mutate shared fleet files and the autoheal
   window is one global lock; 43 concurrent writers needs its own spec.
2. **tryton-crm's `RESILIENCE.md` converge pass (I22)** — their doc debt, their command.

## Next

`/fabrik-spec-review` — this is fleet-synced to 43 repos and earns an adversarial pass. Then the epic route
for per-type packs.
