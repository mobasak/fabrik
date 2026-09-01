# Deployment Verification Contract — design spec

Status: CONVERGED (re-converged 2026-09-01 after Amendment 1; passes A1–A2, md5-stable)
Date: 2026-09-01
Author: fleet (hub)
Stage: 1-design · converged by `/fabrik-spec-review` 2026-09-01 · successor: operator approval, then the epic route

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
| I17 | My measurement: 37 of 43 repos carry no own `specs/services/*.yaml` — ⚠️ **CORRECTED**: the onboarding population is **27**, not 37 | **IN** | § Onboarding — measured 2026-09-01: 43 git repos · 39 with `project.yaml` · **27 with a hub spec (deployable)** · 6 with their own. The store types have no VPS, so a deploy-verification contract is meaningless for them; 37 counted repos that can never need one |
| I18 | D-065 (today): `OPERATIONS.md` + `DEPLOYMENT.md` are fleet-AI interfaces, machine-consumable | **IN** | § Declaration sources — consume these, do not invent a parallel artifact |
| I19 | D-017 (tryton-crm): production migrates the dev DB — "empty is expected" was **my** assumption | **IN** | § Declaration sources — the project's decision ledger is a verification input |
| I20 | tryton-crm: *"a backup plan configured is not a backup taken"* + cert-renewal-survives-restart | **IN** | § Layer 3 — durability armed, two named checks |
| I21 | Self-grading risk — the project verifies work it produced | **IN** | § Ownership split — thin hub cross-check retained |
| I22 | tryton-crm's `RESILIENCE.md` converge pass | **OUT-OF-SCOPE** | Their repo's doc debt, not this contract's. **Destination:** named in their reply thread; belongs to their `/fabrik-doc-converge` |
| I23 | *"utilize all vps infra … grafana"* — **Grafana had NO row in Layer 3** (spec-review pass 1) | **IN** | § Layer 3 #17 — added; the registrar is fire-and-forget and logged `Grafana annotation failed (non-fatal)` during RUN 4 |
| I25 | *"i think there must be a new command and the developer ai must first create a full list of checklist with command for deployment verify"* | **IN** | § Amendment 1 — supersedes the DRAFT's Approach-A rejection |
| I27 | *"every new scaffolded projects must have it too"* | **IN** | § Born compliant — `scaffold.py` seeds the artifacts; the epic's prerequisite ticket |
| I26 | *"and update its operations.md and deployment.md"* | **IN** | § Amendment 1 — the authoring command refreshes both, with the derive-from-code-not-prod hazard rule |
| I24 | *"all services are up"* — nothing checked that EVERY compose service runs (spec-review pass 1) | **IN** | § Layer 3 #19 — added; tryton-crm is a 5-container stack and a dead companion passes every domain probe |

**Intake: 28 rows — 26 IN, 2 OUT-OF-SCOPE (each with a named destination), 0 ASK.**

⚠️ *Third intake correction (spec-review pass 1 on the amendment): the two operator rulings that PRODUCED
Amendment 1 had no intake rows of their own — the amendment was written into the body while the inventory
that is supposed to account for every item silently omitted its own cause. Three separate drops now, all
mine, all in the same table.*

⚠️ *Corrected in spec-review pass 3: I had written "24 items" by counting the `I<n>` sequence and
missing `I1b`, a sub-row. A miscounted denominator inside the document that makes denominators its
central rule — recorded, not silently fixed.*

⚠️ **The DRAFT claimed 22 items with zero silent drops and was wrong on two** — both found by the
spec-review's own intake re-hunt, both operator words I had read and not carried (`grafana` by name;
`all services are up`). Recorded rather than quietly corrected: an inventory that self-certifies
completeness is exactly the check-that-cannot-fail this spec warns about.

## Routing verdict (BLOCKING gate, stated either way)

**This spec is feature-scale; the BUILD it implies is epic-scale.** Decomposed deliberately:

- **HERE (feature-scale):** the *contract* — the failure-mode taxonomy, the ownership split, the
  declaration-source rules, the parity-script interface, and the verdict algebra. One artifact, one
  operator-carried plan.
  ⚠️ **Re-assessed after Amendment 1:** the build grew from *extend one command* to *author a new
  command + extend another + generate two docs per repo + a new pipeline position*. The **contract**
  is still feature-scale (this one artifact). The **build** was already routed to the epic chain and
  that verdict now holds more strongly, not less — Amendment 1 does not promote this spec, it enlarges
  what the epic must carry.
- ⚠️ **ROUTING CORRECTED (spec-review pass G1, operator challenge: *"why do you suggest epic route but
  not /fabrik-plan-after-chat?"*). The DRAFT said epic. That was WRONG.** The criterion is verbatim
  *"needs a ticket store + dispatched agents"*. The hub-side build is:

  | # | deliverable | size |
  |---|---|---|
  | 1 | the new authoring command | 1 file, `commands/_sources/` |
  | 2 | rewrite `/fabrik-deploy-verify` | 1 file (216 lines today) |
  | 3 | scaffolder seeding | `src/fabrik/scaffold.py` + template stubs |
  | 4 | `health-probe` enhancement | **cross-repo** → a fabrik-lib filing, not a ticket I dispatch |

  **~4 files in one repo. No ticket store. No dispatched agents. → `/fabrik-plan-after-chat`.**

  **The error was counting fleet-wide CONSEQUENCES as build work.** The "13 per-type packs" are
  *sections inside two command files*, not 13 deliverables — I inflated a table into a work breakdown.
  And "onboarding the 27 deployable repos" is **not hub work at all**: cross-repo commits are a HARD STOP, so I cannot
  dispatch into those repos even in principle. Each project's own agent runs the authoring command in
  its own repo, triggered by its own next deploy — **self-serve rollout, not a migration I execute.**
  Once the scaffolder seeds new projects (§ Born compliant), the 37 are the only backlog and it drains
  by ordinary use.

  **A wide blast radius is not the same as a large build.** This spec changes what 43 repos *do*; it
  does so by editing four files.

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

⚠️ **The denominator here is DERIVED from code, not hand-listed** (spec-review pass F1 — the spec was
violating its own denominator-integrity rule). The authoritative list is
`src/fabrik/orchestrator/infrastructure.py::_REGISTRAR_ORDER`, read live this run:

`postgres · redis · gatus · backrest · glitchtip · grafana · authelia · meilisearch · prometheus · watchdog`

**All ten verified RUNNING on vps1 this run**, together with `traefik`, `loki` and `cadvisor` (the three
auto-discovered, non-registrar services). The rows below must be **generated from that list**, not
maintained by hand — a hand-written Layer 3 goes stale the moment a registrar is added, which is the
`present-but-inert` failure mode applied to the verifier itself.

⚠️ **`meilisearch` is the proof this was needed:** it is a real registrar (`has_search_feature: true`)
and appeared in the DRAFT exactly once — as a *counter-example in the verdict algebra* — with **no
verification row at all**. A hand-listed denominator lost a whole registrar without anything noticing.
Its check is the one the deploy-verify corpus already prescribes: a query against the service's own
search route, or a hub-side index-existence check — never a `.env` read, because the driver provisions
indexes container-side and nothing lands in the app env.

**Paths verified live this run** (not cited from memory): `/opt/monitoring/configs/gatus` ✓ ·
`/opt/backrest/config/config.json` ✓ · `/opt/monitoring/configs/prometheus/prometheus.yml` ✓ ·
`/run/fabrik-autoheal` ✓. Two of these were wrong in my own probes earlier today
(`/opt/gatus/config.yaml`, a bare `/opt/backrest/` listing), which is why they are pinned here.

11. Gatus **green**, not merely registered
12. Prometheus **actively scraping** (target `up 1`)
13. GlitchTip receives a **deliberately-emitted** error
14. **a backup TAKEN with a timestamp** — a plan configured is not a snapshot taken (I20)
15. **restore rehearsed at least once**
16. TLS/cert config **persisted on disk and surviving a restart** — a DNS-01 resolver added at runtime
    renews nothing, and every tenant URL breaks in ~60 days with no warning (I20)
17. **Grafana deploy annotation actually posted** — the registrar treats it as fire-and-forget
    (`Grafana annotation failed (non-fatal)` was logged verbatim during RUN 4 and the deploy continued).
    Operator named Grafana explicitly in I10; a non-fatal registrar is exactly the *present-but-inert*
    class and must be a verdict-bearing row, not a warning
18. Authelia challenge on admin routes; Loki receiving logs; memory limits declared per service
19. **EVERY service is running and healthy** (I11 — *"all services are up"*). Not "the app container is
    up": a dead companion passes every domain-level probe.
    ⚠️ **The denominator is TWO sources, and using either alone under-counts** — re-derived in
    spec-review pass 2: tryton-crm's `compose.yaml` declares **4** services (`tryton-crm`,
    `crm-gotenberg`, `trytond`, `trytond-worker`) while **5** containers run. The fifth,
    `tryton-crm-watchdog`, is **registrar-injected** (`drivers/watchdog.py`, `container_name =
    f"{project_id}-watchdog"`) and appears in no compose file. So the denominator is
    **compose services ∪ registrar-injected sidecars**, derived from the compose *and* the `shape:`
    flags — and the count is stated. A verifier that reads only the compose would have declared this
    stack complete with its watchdog dead

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

### ⚠️ Honest bias assessment (spec-review pass C1 — operator: *"is your spec only validating tryton-crm?"*)

**Yes, partly — and it is worth stating rather than defending.** The corpus was derived from one live
deploy (tryton-crm, a DB-backed multi-container service) and it shows:

| layer | generalises cleanly | carries a service/DB assumption |
|---|---|---|
| **1 Identity** | SHA · image digest · lockfile — **all 13 types** | *migration head* — DB types only |
| **2 Completeness** | env keys · declared-inventory diff | route table (HTTP only) · queue drain (worker only) · **row counts / filestore (DB only)** |
| **3 Infra** | `shape:`-gated throughout — **correct by construction** | — |
| **4 Behaviour** | deliberate-failure probe · declared-capability exercise | write path · **money path** · external-deps-from-inside-containers (service only) |

So Layers 1 and 3 are genuinely universal; **Layers 2 and 4 are service-shaped**, and the per-type table
below handles the rest by *exception* (8 delta rows) rather than by construction. For a `static-site`
that reads *"partial"* without saying which rows — which is the same under-specification this spec
criticises elsewhere.

**The generalisation that fixes it, and it is one sentence:** every Layer-2/4 row is an instance of
**"the project's declared inventory, exercised against the deployed artifact"**. The *inventory* differs
per type — routes and rows for a service, pages and asset hashes for a `static-site`, permissions and
entry points for a `chrome-extension`, jobs and queue depth for a `file-worker` — but the *rule* does not.
The per-type packs therefore each declare their own inventory kind; they do not each re-invent a
checklist. **That is what makes this a contract rather than a Tryton checklist.**

⚠️ **Named risk, not resolved here:** the packs for the four store types and the two static types are
the LEAST grounded in this spec, because no such deploy was exercised this session. They are the epic's
highest-uncertainty tickets and should be built against a real deploy of each, not from this document's
extrapolation.

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
- ⚠️ **DENOMINATOR INTEGRITY — the clause that makes *"100% tested"* mean anything** (spec-review pass
  D1). The DRAFT made the **numerator** falsifiable (*every declared denominator exercised*) and left the
  **denominator self-declared** — and the project authors both the checklist and the denominator. A repo
  could declare 3 checks, pass 3, and report **100%**. That is the operator's bar satisfied on paper and
  void in fact, and it is the same shape as the empty-database certification this spec exists to prevent.

  **Rule: a denominator is DERIVED wherever derivable, and where it must be declared it is CROSS-CHECKED
  against a derived proxy.**

  | denominator | derived from (authoritative) | never |
  |---|---|---|
  | routes | the router's own introspection | `FEATURES.md` prose |
  | scheduled jobs | `ir_cron` / the live scheduler | `RESILIENCE.md` |
  | env keys | `grep os.getenv` over source | `.env.example` alone |
  | services | compose ∪ registrar-injected sidecars | compose alone |
  | schema | `alembic heads` | a doc |
  | **features** | **not derivable — `FEATURES.md` is prose** | — |

  **The features row is the dangerous one, and it gets a cross-check instead of a source:** every derived
  route must map to a *Shipped* row, and every *Shipped* row to a route. **A route with no feature row, or
  a feature row with no route, is a FINDING** — which is what makes an under-declared `FEATURES.md`
  detectable rather than silently shrinking the denominator.

  **And the checklist's own denominator is the corpus:** the authoring command must emit a row for every
  Layer 1–4 check applicable to the type. A row the project cannot yet assert is
  `UNVERIFIABLE (<why>)` — **counted and reported in the verdict**, so a shrunk denominator is visible
  rather than absent. *"18 of 22 exercised, 4 UNVERIFIABLE"* is a true statement; *"100%"* over a
  self-chosen 3 is not.

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

## Amendment 1 — a NEW authoring command (operator ruling, 2026-09-01)

> *"i think there must be a new command and the developer ai must first create a full list of
> checklist with command for deployment verify."*

**The DRAFT was wrong, and the error was a conflation.** Approach A rejected "a new command" citing
*"Extend, don't duplicate"* — but that reasoning applies to the **runner**, and the operator is naming
the **author**. Those are different commands, and the authoring one has no home:

| concern | today | verdict |
|---|---|---|
| RUNNING verification | `/fabrik-deploy-verify` | extend — the DRAFT's Approach B stands |
| AUTHORING the checklist | `/fabrik-deploy-plan` Phase 6 — **hub-side, per-plan, dies with the plan** | **VACANT project-side → new command** |

Measured: `/fabrik-deploy-plan` mentions `battery` 8 times and Phase 6 is *"Verification battery (the
deploy's exit gate)"*. But it is authored by the **hub**, which is precisely the party that does not know
the project — the root cause this whole spec exists to fix — and the artifact is per-deploy, so nothing
durable accumulates.

The DRAFT's own § Approach C already proved the authoring must be project-side (*"quote a sale → confirm
DDMMYYYY-seq → render PDF"* is unknowable to a fleet command). It then failed to give that authoring a
command, leaving "the project writes `verify_prod_parity.py`" as a hand-wave. **The operator's ruling
closes that gap.**

This matches the corpus pattern rather than breaking it — every other frozen contract has an authoring
command: `/fabrik-features` (feature inventory), `/fabrik-data-contract` (fields), `/fabrik-flows`
(journeys). The verification contract had none.

**Shape (to be specced in the amendment pass):** a project-side command that walks the check corpus
(Layers 1–4 + per-type pack), and for each row emits **the actual runnable command plus its expected
result** — not prose. Its terminal condition is a checklist where every row is executable, and its
denominator is the corpus, so a row the project cannot yet assert is recorded `UNVERIFIABLE (<why>)`
rather than dropped. Output is the durable, versioned artifact `/fabrik-deploy-verify` then consumes.

**It also refreshes `OPERATIONS.md` + `DEPLOYMENT.md`** (operator, same ruling: *"and update its
operations.md and deployment.md"*). This closes a loop rather than adding a chore:

- **D-065 already requires it** — both docs are ruled machine-consumable fleet-AI interfaces that must
  stay *"FULLY current"*. Nothing today produces that currency; it is asserted and decays.
- **The authoring command is the only party positioned to** — it must enumerate every service, job,
  companion, env key and dependency to build the checklist. That enumeration IS the content those docs
  owe. Deriving it twice guarantees two descriptions that drift.
- **It kills I16 at the root** — tryton-crm's *"the doc a verifier would check against is itself partly
  untrue"* (`RESILIENCE.md` still carrying WordPress-cron template residue). A doc regenerated from the
  same derivation that drives the checks cannot carry scaffold residue.

⚠️ **THREE SOURCES, NOT TWO — the goal's own words force this** (spec-review pass B1). The operator's
bar is *"up and running **as like in the wsl**"*: **DEV is the reference baseline.** The DRAFT collapsed
the world into CODE+SPEC vs PROD and named dev **nowhere** — so the artifact meant to close the
dev↔prod gap did not contain the word for one side of it.

| source | authoritative for | never for |
|---|---|---|
| **CODE + SPEC** | routes, env keys, job inventory, schema head, `shape:` obligations | product state |
| **DEV (WSL)** | **the state baseline** — row counts, reference data, translations, filestore contents, i18n completeness | fixture/test debris (see below) |
| **PROD** | *nothing* — it is the thing under test | anything |

**DEV minus a declared exclusion set** is the operative rule, and D-017 is its worked example:
*"everything ships EXCEPT sales/activities/invoices history"* — plus the 757 fixture chart-shell
companies and the cert-role test users, which existed in dev and **must not** ship. A verifier that took
dev wholesale would have demanded 760 companies in production when the correct answer is 3. So the
contract asserts **dev, minus the project's declared exclusions** — and the exclusion list is
project-owned, exactly like the rest of the contract.

This also explains why `battery-expected.txt` worked: its six numbers were **measured in dev**, and the
cleanup's post-clean battery encoded the exclusions. Both halves were present; the DRAFT only named one.

⚠️ **HAZARD, and the rule that contains it: derive the docs from the CODE + SPEC, never from PROD.**
Writing docs from the deployed state launders drift into documentation — *"prod has 0 companies,
therefore document 0 companies"* would have made my empty-database certification **self-consistent and
still wrong**. The docs declare what SHOULD be true (from code, compose, `shape:`, the decision ledger);
the verify run reports what IS. **The gap between them is the product, and a generator that closes that
gap by editing the declaration has destroyed the only signal.**

**Sequencing consequence:** authoring runs at build/release time, not at deploy time. A project without
the artifact reaches `UNVERIFIED` (Q2), which is now also the signal to run the authoring command.

⚠️ **Status returned to DRAFT.** This amendment lands after the CONVERGED flip and materially changes the
architecture (one command → two, plus a new pipeline position). Per the post-flip rule, the convergence
is void until `/fabrik-spec-review` re-runs over the amended artifact.

## Approaches

**A — New developer-side command.** ⚠️ **SUPERSEDED BY AMENDMENT 1 — read that first.** As originally
written this row rejected *any* new command, and it was wrong because it conflated two: rejecting a new
**runner** is still correct (it would leave `/fabrik-deploy-verify` reaching `CONFIRMED LIVE` on an empty
database, the defect surviving beside the fix), but a new **author** is required and now specced. Kept
rather than deleted so the reasoning error stays visible.

**B — Extend `/fabrik-deploy-verify`; project-run; contract-driven.** ✅ **RECOMMENDED.** Reuses the
existing Phase-6 hook (already a project-artifact-driven phase, merely too weak), keeps one verification
surface, and needs no credential movement — **the artifact travels, not the SSH key**, exactly as
`battery-expected.txt` governed my verdict today without tryton-crm ever touching vps1.

**C — Hub-authored per-type checks, no project contract.** Rejected on evidence: *"quote a sale → confirm
DDMMYYYY-seq → render PDF → send email"* is unknowable to a fleet command across 43 repos. The hub cannot
hold that knowledge; it can only demand, run, and adjudicate the project's own proof.

## The four questions — RESOLVED BY DERIVATION (spec-review pass 1)

The DRAFT left these open. Handing four forks to the operator is the menuing the question bar forbids —
*"i dont want to decide that kind of things"*. Each is derived from an existing artifact and cited.

**Q1 · Contract shape → DERIVED, not snapshot.** Both artefacts that actually worked today converged on
derivation independently: `cleanup_d017.py` reads FK closure from `pg_catalog` at runtime *"so there is no
hand-frozen list to drift"*, and its dry-run **executes then rolls back**, making counts exact by
construction rather than by estimate. The snapshot form (`battery-expected.txt`) worked once and was stale
the moment dev moved — its `parties_108` row already encoded a column name (`company`) that does not exist,
which errored on first run. **Snapshot values are a cache of a derivation; ship the derivation.** Snapshot
remains legal as a *degraded* mode for a project that cannot yet derive, and is marked as such in the
verdict, never silently.

**Q2 · Missing contract → BLOCKS, with a dated grace window.** Derived from the spec's own verdict algebra:
*"No contract ⇒ cannot reach `CONFIRMED`"* — a warning that lets `CONFIRMED` through reproduces the exact
defect this spec exists to close (I certified an empty database green). But hard-blocking 37 of 43 repos on
day one strands 86% of the fleet, which the FIX DIRECTIVE's *"no overengineering — measured, not vibed"*
weighs against. Resolution: a contract-less deploy reaches **`UNVERIFIED`** — a terminal verdict that is
**not** `CONFIRMED` and is reported as a deficiency, never as success. `UNVERIFIED` is the honest name for
what every deploy before today actually was.

**Q3 · Where the contract lives → `scripts/verify_prod_parity.py`, project-owned.** Follows Q1: a derivation
is executable, so it is a script, not a doc. Precedent is exact — tryton-crm already proposed this path by
name, and `cleanup_d017.py` sits at `scripts/trytond/`. A doc would re-create the *descriptive-source*
problem this spec warns about (I16: `RESILIENCE.md` template residue). The **declaration** half stays in
`DEPLOYMENT.md`/`OPERATIONS.md` per D-065; the **assertion** half is code.

**Q4 · Hub cross-check → STAYS MANDATORY.** Derived from measured evidence, not preference: the property
that made today's migration trustworthy was **two independent measurements agreeing to the row**
(193,664 / 44 tables, and history 153/129/116 from two separately-written queries). A project verifying its
own deploy is self-grading (I21); the cross-check is what converts a self-assessment into corroboration.
It stays thin — the hub asserts fleet health and identity, the project asserts completeness and behaviour —
and it is **not** opt-out, because the value is precisely in its independence.

## Pass ledger (`/fabrik-spec-review`)

| Pass | Axes re-checked | Method | Raised | Edits | md5 (start → end) |
|---:|---|---|---:|---:|---|
| 1 | intake completeness · measured claims · fabrik-lib verdict · open questions | citation + live grep | 3 | 3 | `42a9eba2…` → `975d9a54…` |
| 2 | all cited facts re-derived from primary source, not re-cited | **re-derivation** | 1 | 1 | `34cbe70e…` → edited |
| 3 | full re-sweep of every axis | re-derivation | 1 | 1 | edited — intake miscount |
| 4 | full re-sweep, confirming | re-derivation | **0** | **0** | stable ✓ |
| — | **AMENDMENT 1 landed (operator ruling) — convergence voided, review re-run** | — | — | — | — |
| A1 | Amendment ripple hunt across the whole spec | citation + live grep | 3 | 3 | `adefee55…` → `49ca35b2…` |
| A2 | all claims re-derived from primary source, confirming | **re-derivation** | **0** | **0** | `49ca35b2…` stable ✓ |
| — | **operator: "state our goal first" — review re-run with GOAL CONFORMANCE as the axis** | — | — | — | — |
| B1 | every goal clause audited against what the spec delivers | goal-conformance | 2 | 2 | `58f7e9f5…` → `1173ae8c…` |
| B2 | full confirming re-sweep | re-derivation | **0** | **0** | `1173ae8c…` stable ✓ |
| C1 | tryton-coverage audit + **type-generality** (operator: *"is your spec only validating tryton-crm?"*) | coverage + bias | 1 | 1 | edited — bias assessment |
| C2 | confirming re-sweep | re-derivation | **0** | **0** | stable ✓ |
| — | **operator re-invoked with THE GOAL as the argument — reviewed against the bar itself** | — | — | — | — |
| D1 | *"100% tested"* stress-tested for circularity | goal-as-measuring-stick | 1 | 1 | `a7b5307f…` → `b00ff30a…` |
| D2 | confirming re-sweep | re-derivation | **0** | **0** | `b00ff30a…` stable ✓ |
| — | **operator: *"every new scaffolded projects must have it too"*** | — | — | — | — |
| E1 | permanence — is the design a migration or a property? | goal-as-measuring-stick | 1 | 1 | `c1a97b32…` → edited |
| E2 | confirming re-sweep | re-derivation | **0** | **0** | stable ✓ |
| — | **operator: *"be 100% sure all factual and validated from our infra first"*** | — | — | — | — |
| F1 | every infra claim probed against the LIVE fleet | **live infra validation** | 1 | 1 | `c9173ade…` → `235463aa…` |
| F2 | confirming re-sweep | re-derivation | **0** | **0** | `235463aa…` stable ✓ |
| — | **operator: *"why do you suggest epic route but not /fabrik-plan-after-chat?"*** | — | — | — | — |
| G1 | routing verdict re-derived against the literal criterion | criterion-vs-artifact | 1 | 1 | edited |
| G2 | confirming re-sweep | re-derivation | **0** | **0** | stable ✓ |

**Pass G2 terminal round — `found: 0, fixed: 0`.**

**Defect 15 — the routing verdict was wrong, and it survived six lenses because none of them re-read the
criterion.** The epic test is *"needs a ticket store + dispatched agents"*; the hub build is ~4 files in
one repo. I reached "epic" by counting fleet-wide **consequences** as build work — inflating a 13-row
per-type *table* into 13 deliverables, and treating a 37-repo rollout as a migration I execute when
cross-repo commits are a HARD STOP that makes it impossible by construction. **Corrected to
`/fabrik-plan-after-chat`.** A wide blast radius is not a large build.

**Pass F2 terminal round — `found: 0, fixed: 0`.**

**Defect 14 — Layer 3's denominator was HAND-LISTED, in the document that demands derived denominators.**
The DRAFT's Layer 3 was 9 ad-hoc rows; the authoritative list is
`infrastructure.py::_REGISTRAR_ORDER` (10 registrars, read live). The rows happened to cover most of
them and included `loki`/`cadvisor`, which are **not registrars at all**.

**`meilisearch` is the proof:** a real registrar that appeared exactly once in the whole DRAFT — as a
*counter-example in the verdict algebra* — with **no verification row**. A hand-listed denominator lost
an entire registrar and nothing noticed, which is precisely the failure the spec's own denominator-
integrity rule exists to prevent. The spec was not applying its own rule to itself.

**Everything else validated clean against the live fleet:** all 10 registrar services plus `traefik`,
`loki`, `cadvisor` **RUNNING on vps1**; all four cited paths **EXIST** — including the two I had
previously probed at the wrong location (`/opt/gatus/config.yaml`, a bare `/opt/backrest/` listing),
now pinned to their verified paths so the error cannot recur through this document.

**14 defects across 12 passes.** Six distinct lenses, each finding what the previous could not:
internal consistency (1–8) → goal conformance (9–10) → type generality (11) → goal-as-measuring-stick
(12) → permanence (13) → **live infra validation (14)**. The last is the only lens that could have
caught a hand-listed denominator, because the artifact was internally consistent with itself the whole
time.

**Pass E2 terminal round — `found: 0, fixed: 0`.**

**Defect 13 — the design was a one-time migration, not a permanent property.** Nothing touched
`scaffold.py`, so new projects would be born non-compliant and the backlog would refill as fast as it
drained. Fixed by seeding the artifacts at scaffold time on the exact precedent of
`docs/data-contract.md` (`scaffold.py:285`), with the stub **exiting non-zero** so an unfilled contract
fails rather than silently passing — and carrying forward that file's own `docusaurus` leak caveat
(`:293`), since a parity contract naming internal hosts and row counts must never become a public page.
The scaffolder ticket becomes an epic **prerequisite**: seed first, then onboard, or the migration races
new projects forever.

**Pass D2 terminal round — `found: 0, fixed: 0`.**

**Defect 12 — *"100% tested"* was circular, and it is the operator's actual bar.** The spec made the
**numerator** falsifiable (*every declared denominator exercised*) while the **denominator stayed
self-declared** — and the project authors both the checklist and the denominator. A repo could declare 3
checks, pass 3, and report **100%**: the bar satisfied on paper and void in fact, the same shape as the
empty-database certification. Fixed with **denominator integrity** — derive every denominator that is
derivable (routes from the router, jobs from the scheduler, env keys from source, services from
compose ∪ sidecars, schema from `alembic heads`), and for the one that cannot be derived (**features**,
because `FEATURES.md` is prose) require a **bidirectional cross-check against derived routes**, so an
under-declared inventory is a finding rather than a smaller denominator. The checklist's own denominator
is the corpus, and `UNVERIFIABLE (<why>)` rows are **counted in the verdict** so shrinkage is visible.

**12 defects across 10 passes, all mine.** The pattern is worth stating plainly: passes 1–8 asked *"is
this internally consistent?"*, B1–B2 asked *"does it serve the goal?"*, C1 asked *"does it generalise?"*,
and D1 asked *"can the goal's own words be gamed?"* — each new question found something the previous
lens structurally could not. **Convergence is relative to the question being asked**, which is the
deepest thing this review taught, and it applies to the verification contract itself.

**Pass C2 terminal round — `found: 0, fixed: 0`.**

**Defect 11 — the corpus is service/DB-shaped and did not admit it.** All 12 of tryton-crm's A–H checks
map (verified individually), but the *layers* were derived from one DB-backed multi-container deploy.
Layers 1 and 3 generalise; Layers 2 and 4 carry service assumptions that the per-type table papered over
with the word *"partial"*. Fixed by naming the bias, stating the generalisation that resolves it
(**declared inventory, exercised against the deployed artifact** — the inventory kind varies by type, the
rule does not), and flagging the six least-grounded packs as the epic's highest-uncertainty tickets.

**Pass B2 terminal round — `found: 0, fixed: 0`.**

**What the goal-conformance pass found (2 more — 10 total, all mine):**
9. ⚠️ **The goal says *"up and running as like in the WSL"* — and the spec named DEV nowhere.** Zero
   mentions as a source. The hazard rule correctly banned deriving from PROD and, in doing so,
   accidentally excluded DEV — **the artifact meant to close the dev↔prod gap did not contain the word
   for one side of it.** Fixed with a three-source model (CODE+SPEC · DEV · PROD) where dev is the state
   baseline *minus a declared exclusion set*, D-017 being the worked example: dev held 760 companies,
   production correctly holds 3.
10. **Goal conformance was never stated as such.** Two clauses land **PARTIAL** — the operator's opening
    ask (projects owning their own deploys) is genuinely not delivered here. That was true in the
    intake's fine print and invisible at the level the operator reads.

Defect 9 is the most consequential of all ten: five prior passes over this artifact — including two
re-derivation passes — never found it, because every one asked *"is the spec internally consistent?"*
The goal was the only lens that asked *"is the spec **right**?"*

**Pass A2 terminal round — `found: 0, fixed: 0`.**

**What the amendment review found (3 more, all mine — 8 total across both reviews):**
6. **Approach A still read "Rejected"** while Amendment 1 supersedes it — a live self-contradiction left
   in the artifact. Kept and marked SUPERSEDED rather than deleted, so the reasoning error stays visible.
7. **The two operator rulings that PRODUCED the amendment had no intake rows.** The amendment was written
   into the body while the inventory meant to account for every item silently omitted its own cause.
8. **The routing verdict was stale** — it still described "one operator-carried plan" after the build grew
   to *new command + extend another + generate two docs per repo + a new pipeline position*.

⚠️ **Three intake corrections across three passes** (I23/I24, the 24-vs-25 miscount, now I25/I26). The
inventory has been wrong every single time it was checked. That is the strongest argument in this
document for its own central rule: **a self-certifying count is not evidence.**

**Pass 4 terminal round — `found: 0, fixed: 0`.**

**What the review found in my own DRAFT (5 defects, all mine):**
1. **Grafana absent** from Layer 3 though the operator named it explicitly (I23)
2. **"all services are up" uncovered** — no per-service check at all (I24)
3. **The intake self-certified "zero silent drops" and had two** — an inventory that grades itself
4. **Pass 2, re-derivation:** the service denominator was wrong — I wrote *"the compose service list"*,
   but compose declares 4 and 5 containers run; `tryton-crm-watchdog` is registrar-injected and in no
   compose file. A verifier built to the DRAFT would have passed this stack with its watchdog dead.

5. **Pass 3:** the intake summary said *24 items*; there are **25 rows** — `I1b` uncounted. A wrong
   denominator in the spec whose central rule is that every count carries its denominator.

Defect 4 is the one that justifies the re-derivation method: it survived pass 1 because pass 1 re-*cited*
my own prose. Only re-running the count against `compose.yaml` and `docker ps` separately exposed it.

## Goal conformance (spec-review pass B1)

The stated goal, and what this spec actually delivers against each clause:

| goal clause (operator's words) | delivered? | where / gap |
|---|---|---|
| *"each project be able to deploy their own development"* | **PARTIAL** | verification ownership: yes. **Deploy execution: NO** — deferred (§ Deferred 1). The goal is not fully met by this spec alone and says so rather than implying otherwise |
| *"you will only manage the infra"* | **PARTIAL** | same boundary — I keep the fleet-health cross-check by design (§ Q4), so "only infra" is approached, not reached |
| *"cant compare what is developed and what is deployed"* | **YES** | § Layer 2 + the three-source model — the spec's centre |
| *"validate its implementation fully, complete, up, and running"* | **YES** | § Verdict algebra — three separately-failable verdicts |
| *"utilize all vps infra … glitchtip, backups, grafana"* | **YES** | § Layer 3, 9 rows, `shape:`-gated |
| *"up and running as like in the wsl"* | **YES** (after B1) | § three-source model — **dev is the state baseline**, minus declared exclusions. This clause was NOT served before pass B1 |
| *"a new command … full list of checklist with command"* | **YES** | § Amendment 1 |
| *"update its operations.md and deployment.md"* | **YES** | § Amendment 1 |
| *"100% tested after deployment"* | **YES, as defined** | § Verdict algebra — "100%" means every declared denominator exercised, not an unbounded claim |

⚠️ **Two clauses land PARTIAL, and that is stated here rather than buried in an intake disposition.**
The operator's opening ask — projects owning their own deploys — is genuinely not delivered by this spec;
it is deferred with a named destination and a reason (shared-fleet writers, one global window lock). A
spec that let the goal read as fully met would be the same defect class as a deploy that reads green.

## Born compliant — the scaffolder seeds it (operator ruling, spec-review pass E1)

> *"every new scaffolded projects must have it too."*

**The DRAFT specced a one-time migration, not a permanent property.** It handled the 27 deployable repos
as onboarding and said nothing about `scaffold.py` — so a project scaffolded tomorrow would be born
**without** the contract and join the backlog on day one. The backlog would refill as fast as it drained.
That is a defect in the design's shape, not a missing task.

**The precedent is exact and already in the tree:** `src/fabrik/scaffold.py:285` maps
`docs/data-contract-template.md` → `docs/data-contract.md`, seeded into every new project as a DRAFT
stub that `/fabrik-data-contract` later fills. The verification contract follows the identical pattern:

| seeded artifact | filled by | state at scaffold time |
|---|---|---|
| `scripts/verify_prod_parity.py` | the new authoring command | executable stub that **exits non-zero** — an unfilled contract must fail, never silently pass |
| `specs/services/<id>.yaml` | scaffolder, from `project.yaml` + `shape:` | complete — this is why 37 repos lack one and no future repo will |
| `DEPLOYMENT.md` / `OPERATIONS.md` | the authoring command (D-065) | template with the fleet-AI sections present |

⚠️ **The `docusaurus` leak caveat, inherited from the same precedent** — `scaffold.py:293` records that
seeding docs into a `docusaurus` project **publishes them**, because it renders the whole `docs/` tree.
That is the exact class closed earlier this session by adding a content-docs `exclude`. The verification
artifacts must therefore either seed outside `docs/` (`scripts/` already is) or land in the exclude list.
**A parity contract naming internal hosts, table names and row counts is precisely what must not become
a public page.**

**Consequence for the epic:** the scaffolder ticket is a **prerequisite**, not a parallel one. Seed first,
then onboard the 37 — otherwise the migration races new projects and never converges. It also shrinks the
onboarding: every repo scaffolded after the seed lands needs no retro-fit.

## Deferred (named, not dropped)

1. **Moving `fabrik apply` to projects (I1b)** — registrars mutate shared fleet files and the autoheal
   window is one global lock; 43 concurrent writers needs its own spec.
2. **tryton-crm's `RESILIENCE.md` converge pass (I22)** — their doc debt, their command.

## Next

`/fabrik-spec-review` — this is fleet-synced to 43 repos and earns an adversarial pass. Then the epic route
for per-type packs.
