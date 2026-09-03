---
description: Post-`fabrik apply` certification, hub-side — identity (deployed SHA = tested SHA, migration head, image digest), DNS vs two siblings, the health endpoint asserting real deps, every `shape:` registrar derived live from `_REGISTRAR_ORDER`, Gatus green, logs clean, then the project's FROZEN parity contract (`scripts/verify_prod_parity.py`) executed against the LIVE service — no contract = UNVERIFIED, never CONFIRMED. Verify-only; every FAIL routes to an ask. Not `/fabrik-release` (readiness) or `/fabrik-service-test` (gauntlet). Stage: 6-release. TRIGGER — EN: "verify the deploy", "did fabrik apply work", "check the live service"; TR: "deploy'u doğrula", "apply çalıştı mı".
argument-hint: "[optional: spec path or service id to verify — omit to read specs/services/<id>.yaml for this project]"
---

Run this project's **post-deploy verification** — the twin of `/fabrik-decommission`'s liveness probe run
in the opposite direction: proving a service that just deployed — via `/fabrik-deploy` (the triad's
executor) or a direct operator `fabrik apply` (the manual path) — is actually ALIVE, with
the same evidence discipline (a fresh probe this run, never a catalog/registry/env row read as proof).
This command **verifies only**: no `fabrik apply`, no `fabrik destroy`, no registrar re-run, no file
mutation at all — the verdict table is PRINTED (no report file; the run record is the durable trace).
**It certifies against what was BUILT, not against liveness alone**: a service once passed every check
here while production held 0 of its 760 companies, because nothing declared what the product should
contain. That declaration is the project's **parity contract** — `scripts/verify_prod_parity.py`, authored
and FROZEN by `/fabrik-deploy-checklist` — and Phase 6 EXECUTES it. Without a FROZEN contract the run's
verdict is `UNVERIFIED`: terminal, not success, and the signal to run the authoring command.

```
/fabrik-features REFRESH → /fabrik-deploy-checklist (FREEZE) → /fabrik-release (precondition: FROZEN) → deploy triad → /fabrik-deploy-verify (consumes)
```

**Where this runs:** hub-side, from `/opt/fabrik` — the hub carries fleet SSH creds (deploy is
trigger-not-execute; `agents-fabrik-core.md` § Deploy). A project itself cannot reach its own deployed VPS
this way — this command is the hub-side exception to the local-Docker-bridge-namespace warning
`commands/_sources/fabrik-catchup.md` § the local-`fabrik`-bridge probe documents for project-side probes (the WSL box's local
`fabrik` bridge is a different network from the fleet's and would silently probe the wrong thing), not a
violation of it. Each phase below is labeled `[anywhere]` (a public DNS/HTTPS probe any box can run) or
`[hub-side]` (needs the fleet SSH path — `ssh <target_vps> ...` or a hub-container `exec`).

{{include:run-record}}
{{include:grounding-artifact}}

## ⚠️ Termination contract

You are done when EVERY checklist item below (identity, DNS, health/readiness, registrar obligations, Gatus,
logs, parity) is TERMINAL — one of the four token FAMILIES (the Output block's row-specific spellings —
`discriminator void` is DNS's INCONCLUSIVE, `missing` is GATUS's FAIL, `n/a (not obligated)` is the
spec-voided NOT-RUN): **PASS (with evidence: a command's real output, this
run) · FAIL (with evidence + a named route) · INCONCLUSIVE (the probe cannot discriminate — the
re-probe instruction is the route) · NOT-RUN (<the cause> — the early-stop and store-guard branches'
honest token, never silence)** — and the verdict table has been printed (EXCEPT the Phase-0 store-surface hand-back, which emits its
own two-line closing form INSTEAD of the Output block — never manufacture n/a rows for fields that
do not exist on that path). A checklist item without a
fresh-this-run command output is not a verdict, it is a guess (`n/a (not obligated)` is the one
exception — it cites the spec flag that voids the obligation instead of a command output). You never perform a fix, redeploy, or
registrar mutation yourself: a FAIL's route is always one of `/fabrik-review` (a code-side defect), a
rollback note (name the prior known-good SHA, do not roll back), or a registrar re-apply **ask** to the
operator (`fabrik apply` reruns registrars; you name that, you never run it) — routes are asks, never
actions. **Context is never a reason to stop:** the harness auto-compacts and the run continues. If >3
items FAIL on the same root cause (e.g. the whole VPS is unreachable), stop early and report that cause
rather than exhausting the checklist against a dead host — every unreached item then carries
`NOT-RUN (<the shared root cause>)` in the verdict table, so the early stop stays fillable and honest.

## Phase 0 — Resolve the target

0. **⚠️ SURFACE GUARD — this command is VPS-only, and says so rather than dead-ending.** Every step
   below resolves from `specs/services/<id>.yaml`, which exists only for VPS-deployed types. If the
   target's `project.yaml::type` is a STORE surface — `mobile-app`, `chrome-extension`, `desktop-app`
   — there is no spec, no `domain` and no `target_vps` to read, and a run that pushes on will fail at
   step 1 looking like a missing file rather than an inapplicable command. **Stop and hand back
   instead**, naming what a store release actually needs verified: the build's provenance (the
   submitted artifact came from a pushed SHA), the store-side review/rollout state in the vendor
   console, and the first-ring crash/ANR signal — none of which this command probes, and none of
   which a `dig` against a domain can answer. That hand-back is a clean terminal ending, not a
   `BLOCKED:` — and it emits its OWN two-line closing form instead of the Output block (whose
   domain/target fields do not exist on this path): `DEPLOY-VERIFY: <project> — STORE SURFACE, handed
   back` + `NEEDS: <the three store verifications named above>`. ⚠️ The pipeline docs currently route store surfaces here post-submit; until a store
   analogue exists that routing is aspirational, and this guard is what keeps it honest at the point
   of use rather than discovering it mid-run (backlog: *Store-terminal adjudication*, blocked on the
   first real store release to ground what the analogue must probe).

1. Read `specs/services/<id>.yaml` (or the path/id argument if given): `domain`, `target_vps` (default
   `vps1`), and every `shape:` flag — this is the obligation list Phase 3 checks against.
2. **Spoke-aware from here on.** `target_vps: vps1` (hub, default) → shared infra (`postgres-main`,
   `redis-main`, GlitchTip, Gatus, Authelia) lives on the same host as the app. `target_vps: vps2/vps3`
   (spoke) → the app reaches hub-shared infra at the registrar-injected mesh IP `10.99.0.1:<port>`
   (WireGuard carries packets, not DNS) — a spoke's `.env` correctly shows `10.99.0.1`, not
   `postgres-main`; that is not a defect, per `templates/scaffold/docs/DEPLOYMENT_TEMPLATE.md`.
3. Read `docs/RESILIENCE.md` §2 for the dependency inventory the spec's health endpoint should assert,
   and the **fleet-AI sections** of `docs/DEPLOYMENT.md` + `docs/OPERATIONS.md` (D-065) as the declaration
   inputs — what the project SAYS it deploys and runs.
4. **Read the parity contract's header block** — `scripts/verify_prod_parity.py --header` in the project
   checkout (`Status`, `Version`, `Date`; an older header's trailing `Mode:` is tolerated). **`Status: FROZEN` is the obligation gate**: absent, unparseable
   or `DRAFT` ⇒ the run's VERDICT is **`UNVERIFIED — no FROZEN parity contract`** (terminal, never
   `CONFIRMED`) and the Output's `ROUTES` names `/fabrik-deploy-checklist`. Every other phase still runs
   — liveness evidence is still evidence — but Phase 6 reports `NOT-RUN (no FROZEN contract)` and the
   verdict cannot climb above `UNVERIFIED`. Read it; never assume it. Absent is the NORMAL state of a project
   scaffolded before 2026-09-02 (the stub is seeded at scaffold time, never synced) — not a defect to hunt, the
   route to `/fabrik-deploy-checklist` is the whole answer.

## Phase 1 — DNS: live, not merely cataloged `[anywhere]`

Resolve the spec's `domain` (`dig +short <domain>` or `getent hosts <domain>`) in the SAME probe run as
two KNOWN-LIVE sibling domains on the same `target_vps` — the absence-vs-outage discriminator from
`/fabrik-decommission`, run in reverse. Use `status.<target_vps>.ocoron.com` (Gatus, live per-VPS —
`PORTS.md`:28) as one sibling; pick the second from a domain of a currently-deployed spec on the same
`target_vps` (`grep -l 'target_vps: <vps>' specs/services/*.yaml`, read its `domain:` — e.g.
`search.vps1.ocoron.com` on vps1, verified resolving `2026-08-29` → `172.93.160.197`;
`canary.vps2.ocoron.com` on vps2, verified resolving `2026-08-07` → `96.9.214.128`). Never use
`gatus.<vps>.ocoron.com` / `grafana.<vps>.ocoron.com` as siblings — both NXDOMAIN on vps1 (verified
`2026-08-29`), a dead-sibling trap. Outcomes: target resolves → **PASS**. Target fails AND both siblings
resolve → **FAIL** (a real deploy gap — the DNS record never landed or `fabrik apply` didn't reach this
spec). Target AND siblings ALL fail → **inconclusive** (transient outage or a network-reachability gap
from this box) — name it, re-probe later, never report it as a verdict either way. **If a designated
sibling itself fails to resolve while the target's own result would otherwise be a FAIL, the discriminator
is VOID** — report `discriminator void (sibling NXDOMAIN)`, never `inconclusive`: a voided run means the
chosen sibling was a bad pick (pick a different one and re-probe), not a shared outage. Never treat the
spec's `domain:` field, a `PORTS.md` row, or a catalog entry as evidence of liveness — only a probe run
THIS session counts.

**Wildcard-DNS control probe — spoke targets only.** `*.vps2.ocoron.com` and `*.vps3.ocoron.com` carry
wildcard DNS: ANY subdomain resolves to the host IP whether or not a service is actually deployed there
(live-verified `dig totally-nonexistent-xyz987.vps2.ocoron.com` → `96.9.214.128`, `2026-08-29`); `vps1` has
no wildcard (a random subdomain there NXDOMAINs). Consequence: on `target_vps: vps2/vps3`, a PASS in the
DNS outcome table above proves only that the wildcard is live, not that this service is deployed —
resolution is **non-evidentiary** for spokes. Before trusting a spoke target's DNS PASS, run the control
probe first: `dig +short <random-nonsense-string>.<target_vps>.ocoron.com`. If that ALSO resolves, the
target's own resolution carries no deploy signal — do not stop at DNS; the discriminating evidence moves
to the HTTPS layer (Phase 2): a genuinely deployed service answers its own 2xx/redirect/auth challenge,
while an undeployed-but-wildcard-resolved name gets Traefik's default backend (typically a 404). Record
this explicitly in the verdict row: `wildcard DNS — resolution non-evidentiary, discriminating at HTTPS
layer`, and let Phase 2's HTTPS result — not Phase 1's DNS result — carry the PASS/FAIL for spoke targets.
`vps1` (hub, no wildcard) keeps the existing behavior unchanged: a real NXDOMAIN there still discriminates
on its own at the DNS layer.

## Phase 1b — Identity: the deployed build IS the tested build `[hub-side]`

Layer 1 of the contract corpus — **nothing below it means anything if it fails**: everything verified
later is true of *something*; only this phase proves it is true of *this build*. Over the fleet SSH path
against the target VPS's checkout (`/opt/<app>` — the same path `deployer_ssh.py:331` reads its rollback
point from):

1. **Deployed SHA == tested SHA** — `ssh <target_vps> "cd /opt/<app> && git rev-parse HEAD"` vs the SHA the
   release's green CI / `/fabrik-release` READY verdict names (the local `git rev-parse <tag-or-branch>` of
   what was pushed). Never the deploy log's echo — a silently-failed `git pull` leaves the old SHA in place.
2. **Migration head == repo head** (DB types) — `alembic current` inside the app container vs `alembic heads`
   in the checkout (trytond: `ir_module` state vs the shipped module list; no migration tool ⇒
   `n/a (not obligated)` with the type named).
3. **Image digest == the built digest** — `docker inspect --format '{{.Image}}' <container>` vs the image
   the build produced (`docker images --digests` on the target); a silently-failed rebuild runs old code
   under a new commit.
4. **Lockfile hash == the tested dependency set** — the checkout's lockfile hash vs the one inside the
   running container (`sha256sum` both sides).

**Early-stop:** an identity FAIL is a shared root cause — every later row carries `NOT-RUN (identity)`,
the verdict is `VERIFICATION FAILED`, and the route is a rollback note naming the prior known-good SHA
(never a rollback performed). PASS requires all four; a row that cannot be probed from the hub is
`INCONCLUSIVE (<why>)`, never PASS.

## Phase 2 — Health + readiness (real dependency assertions, liveness kept separate) `[anywhere]`

Two distinct checks — never conflate them. Per `templates/scaffold/docs/RESILIENCE_TEMPLATE.md`:307,
`/healthz` is contractually a **static liveness probe** (always 200, even when degraded); it is never
dependency-asserting and a static 200 there is CORRECT, not a FAIL.

1. **The spec's health endpoint.** Read `health.path` from `specs/services/<id>.yaml` (fallback `/health`;
   `saas-skeleton` scaffolds default `/api/health`). `curl -sf https://<domain><health.path>`. **PASS**
   requires a 2xx AND the body/behavior proves a real dependency was tested (per `docs/RESILIENCE.md` §2
   and `CLAUDE.md` § Health endpoint — e.g. a DB-backed service's health route must actually run
   `SELECT 1`, not return a static 200). A 200 that is provably static (no dependency call in the route's
   own code, if reachable) is a **FAIL** — route to `/fabrik-review` (a code defect, not a deploy defect).
2. **`/healthz`** (if reachable) — a static 200 is correct by contract; never fail this one.
3. **`/readyz`** — verify-if-present only: if reachable, a 2xx is **PASS**; absence is **not a FAIL** (zero
   scaffold emits it today). Do not attempt to induce a pause to exercise the 503-under-pause contract —
   that's unactionable from a verify-only run; report `/readyz` presence/response as informational and
   never gate the phase verdict on it.

## Phase 3 — Registrar obligations: the spec's `shape:` truth, deployed `[hub-side]` (`.env` rows) / `[anywhere]` (probe rows — see column)

For every `shape:` flag true in Phase 0, confirm the registrar it obligates actually landed. Because this
command runs hub-side (see "Where this runs" above), the authoritative `.env` read is the **REMOTE**
`/opt/<app>/.env` on the target VPS over the fleet SSH path — that is where `inject_env` writes
(`src/fabrik/orchestrator/deployer_ssh.py::inject_env`, def at `:258`; call sites drift with the
file — find them live with `grep -n inject_env src/fabrik/orchestrator/infrastructure.py`, e.g.
`:588` postgres / `:621` watchdog as of 2026-08-29) — never the local project dev `.env` (registrars never touch that file; reading
it produces a false PASS or FAIL either way). Where a probe endpoint can prove the same fact (a `/metrics`
body, an admin-route auth challenge, a health body naming its dependencies), **prefer the probe** and use
the remote `.env` read as corroboration, not the sole source.

**⚠️ The registrar denominator is DERIVED at RUN time, never copied from this file.** Read
`src/fabrik/orchestrator/infrastructure.py::_REGISTRAR_ORDER` live (`grep -n '_REGISTRAR_ORDER' -A12`) and
emit ONE row per registrar it names, in its order, keyed by name — the rule text below is looked up BY
NAME. A registrar the registry names that has no rule text here is **`FAIL (unmapped registrar →
/fabrik-review)`**, never a silent skip: that is the *present-but-inert* failure mode applied to the
verifier itself (a hand-listed table lost `meilisearch` once). State the count: `REGISTRARS: <n> named by
_REGISTRAR_ORDER`. The three auto-discovered services (`traefik`, `promtail/loki`, `cadvisor`) are not
registrars and stay informational rows.

Rule text per registrar name (`templates/scaffold/docs/RESILIENCE_TEMPLATE.md` §11 is the project-side
mirror):

| Flag | Registrar | Verify via |
|---|---|---|
| `needs_database: true` | `postgres` | remote `.env` `DATABASE_URL` present, pointed at `postgres-main:5432` (hub) or `10.99.0.1:5432` (spoke) — never `localhost` |
| `needs_cache: true` | `redis` | remote `.env` `REDIS_URL` present, same hub/spoke DNS-vs-mesh-IP rule — `REDIS_HOST` is never injected by the registrar; do not accept it as evidence |
| `kind ∈ {service, worker, wordpress}` | `glitchtip` | remote `.env` `GLITCHTIP_DSN`/`SENTRY_DSN` present and non-empty |
| `exposes_metrics: true` + `domain` set | `prometheus` | `curl -sf https://<domain>/metrics` returns a real Prometheus text-format body, not 404/401 (probe-only — no dedicated env var to corroborate with) |
| `has_search_feature: true` | `meilisearch` | a lightweight query against the service's OWN search route returns results (preferred), OR a hub-side index-existence check (`exec` against the hub meilisearch container) — the driver provisions indexes container-side; nothing lands in the app `.env`, so a `.env` check is never valid evidence here |
| `is_admin_dashboard: true` + `domain` set | `authelia` | hitting the admin route unauthenticated returns a redirect/401 to the Authelia forward-auth flow, never a bare 200 |
| `watchdog.enabled` (default true, kind/shape-driven — `.windsurf/rules/core/60-watchdog.md`) | `watchdog` | remote `.env` `WATCHDOG_DB_URL_RO` present (+ `WATCHDOG_DB_URL_RW` when `needs_database`), OR the sidecar container `fabrik/watchdog:<project_id>` running on the target VPS |
| `has_persistent_data: true` | `backrest` | **not project-verifiable** (hub-only schedule state) — report as informational, never a FAIL from this run |
| always | `grafana` (deploy annotation) | **not project-verifiable** — informational only |
| auto-discovered | `traefik` | implied by Phase 1 DNS + Phase 2 HTTPS reachability succeeding — do not re-probe separately |
| auto-discovered | `promtail/loki` | **not project-verifiable** from a domain/env probe (infra-side log shipping) — informational only |
| auto-discovered | `cadvisor` | **not project-verifiable** (infra-side container-resource-metrics scrape) — informational only |

A flag `true` with no corresponding remote-`.env` var or live probe response is a **FAIL** — route it as a
**registrar re-apply ask to the operator** (`fabrik apply` re-runs registrars; name the exact flag and
spec path, never run it yourself). A flag that is honestly `false` and correspondingly absent is not
checked (nothing was obligated).

## Phase 4 — Gatus probe `[anywhere]`

If `is_public: true` and `domain` is set, the spec obligates a Gatus endpoint (per §11). Confirm it exists
and is currently green — read Gatus's own status (its public status page or API if reachable from this
box) for this domain's endpoint. Missing entirely = **FAIL**, route as a registrar re-apply ask. Present
but red = **FAIL**, route to `/fabrik-review` if the redness traces to this service's own `/health`
contract, otherwise name the dependency it's failing on.

## Phase 5 — Bounded log scan `[hub-side]`

Pull a bounded recent window of THIS service's container logs from the TARGET VPS over the fleet SSH path
(`ssh <target_vps> docker logs --since <window> <container>`) — never local Docker: the WSL box's local
`fabrik` bridge is a different network from the fleet's `fabrik` network, and a local scan would silently
hit the wrong container (or none) — the false-clean trap `commands/_sources/fabrik-catchup.md` § the local-`fabrik`-bridge probe
documents for project-side probes. Grep the window for crash/restart signatures: `Traceback`, `FATAL`,
`OOMKilled`, `exit code`, a restart-loop timestamp pattern. Zero hits in the window = **PASS**. Any hit =
**FAIL**, quote the line, route to `/fabrik-review` (application-side) unless the signature is clearly
infra-side (OOM against too-low `deploy.resources.limits.memory`), in which case name that as the fix
instead.

## Phase 6 — Parity (contract-driven, BLOCKING) `[anywhere]`

**The product's declared contents, checked against the LIVE service — the phase that fails on a missing
product.** Skipped only by Phase 0 step 4 (`NOT-RUN (no FROZEN contract)`).

1. **One leg per SITE, each where it can reach — then ONE merge.** Every row declares its site
   (`@site("container")` / `@site("host")`; undeclared = `hub`), and the runner executes exactly three legs:
   - **hub leg** — from the PROJECT's checkout with the PROJECT's interpreter (its rows import the project's
     own code and the vendored `libs/health_probe`): `cd /opt/<project> && .venv/bin/python
     scripts/verify_prod_parity.py --json --site hub > <run>/hub.json`. Never against a hub cwd (a hub-cwd run
     once reported the hub's own tables as the project's).
   - **container leg** — inside the RUNNING container that can REACH the database, redis and the internal
     network. **Which container is the contract's to say, never yours to assume:** read `container_leg_service`
     from `scripts/verify_prod_parity.py --header` (`CONTAINER_LEG_SERVICE` in the contract); empty means the
     project's own app service. A DB-free bridge in front of a stateful backend is a common shape — tryton-crm's
     app container carries no psycopg by design and its leg runs in `trytond` — so exec'ing "the app" there
     kills every DB row. Resolve the service name to the running container (`ssh <vps> "docker compose -f
     /opt/<project>/compose.yaml ps -q <service>"`, or the `container_name` the compose declares). The
     vendored comparator is gitignored in projects, so the VPS checkout the image was built from does NOT
     contain it: ship both files first, then run:
     `ssh <vps> "docker cp /opt/<project>/scripts/verify_prod_parity.py <leg>:/app/scripts/ 2>/dev/null;
     true"` (the image already carries the script when the Dockerfile `COPY . .`s the checkout — the copy
     refreshes it), `scp -r libs/health_probe <vps>:/tmp/health_probe && ssh <vps> "docker cp
     /tmp/health_probe <leg>:/app/libs/"`, then `ssh <vps> "docker exec <leg> python scripts/verify_prod_parity.py
     --json --site container" > <run>/container.json`. The container's own env (`DATABASE_URL`, `REDIS_URL`,
     the compose network) is what makes these rows resolvable — that is why they live there. **The leg
     container must carry the comparator's runtime deps** — `libs/health_probe` imports `python-dotenv` at
     module level (and `psycopg`/`redis` for the rows that use them); an image without them dies on import, and
     the leg reads UNVERIFIABLE for every row. An `ImportError` in `container.json` is that, not a product FAIL:
     route it to the project (add the dep to the leg service's Dockerfile), never to a rollback.
   - **host leg** — on the VPS host for rows that need `docker ps` or a volume path:
     `scp scripts/verify_prod_parity.py <vps>:/tmp/ && ssh <vps> "cd /opt/<project> && PARITY_FILESTORE_PATH=<mount>
     python3 /tmp/verify_prod_parity.py --json --site host" > <run>/host.json` (the host leg needs no
     comparator for liveness rows; a comparison row there gets the same `docker cp`-free `scp -r libs/health_probe`).
   A leg you CANNOT reach (no SSH, the container not running) is never skipped: emit its rows as
   UNVERIFIABLE from the hub — `scripts/verify_prod_parity.py --json --site container --unreachable "<why>"
   > <run>/container.json` — so the denominator stays whole and the verdict fails closed on that leg.
   **Read-only rows only** on every leg: a row the contract marks `UNVERIFIABLE (mutating — …)` is named in
   the table, never executed.
2. Merge: `scripts/verify_prod_parity.py --verdict --rows-from <run>/hub.json <run>/container.json
   <run>/host.json` and **copy its two lines verbatim** into the Output block —
   the verdict algebra is EXECUTED by that script (`verdict()`: rows carrying ANY comparison key are parity
   rows — the vendored `_COMPARISON_KEYS` disjunction; `match True` = numerator; `False` = denies CONFIRMED;
   `None` on a parity row = ATTEMPTED-BUT-UNRESOLVED = fail closed, exit 2; a row with none of the keys is a
   liveness row outside the denominator; `not obligated` — a `shape:` flag — is the only thing that removes a
   row; exit 1 (a DOWN) outranks 2 outranks 0 and never upgrades a verdict). **Never re-derive the verdict in
   prose from the row list**; a verdict you computed by reading is the retired rule wearing a table.
3. Read every row's `{system, status, detail, expected, actual, match, compare_error}` with `.get()`
   (`compare_error` is present only when the comparator raised). Per row: `match True` → PASS (quote
   expected/actual); `False` → FAIL, route `/fabrik-review` (a code- or data-side defect — the deployed
   product differs from what was built) or a rollback note; `None` on a parity row → FAIL
   `attempted-unresolved (<compare_error>)`, route `/fabrik-deploy-checklist` (the row's comparator is
   broken — a check that cannot fail is a defect, and one that cannot resolve is worse); an `UNVERIFIABLE
   (<why>)` row → listed with its why, counted in the denominator, never PASS.
4. **State the denominator with every count**: `<n> agree / <n> disagree / <n> unresolved / <n>
   UNVERIFIABLE of <N> (contract v<N>, <n> not obligated)` — the `PARITY:` line the script
   prints. `N` is the corpus applicable to the type; a row the project could not assert is visible as
   UNVERIFIABLE, never absent.

(The former top-3 `FEATURES.md` smoke is subsumed: the contract's Layer-4 rows exercise EVERY shipped
feature row with the count stated, per spec corpus #24 — a sample of three was the shape that certified an
empty database.)

## Output (always, last thing)

```
DEPLOY-VERIFY: <project> @ <domain> (target_vps: <vps1|vps2|vps3>)
IDENTITY: PASS (sha <7> = tested · migrations at head · digest match · lockfile match) | FAIL — <which> | INCONCLUSIVE (<why>) | NOT-RUN (<cause>)
DNS: PASS | FAIL (siblings resolved, target didn't) | inconclusive (re-probe — siblings also failed) | discriminator void (sibling NXDOMAIN) | NOT-RUN (<cause>) | n/a (not obligated — no domain set)
HEALTH/READYZ: PASS | FAIL — <evidence> | INCONCLUSIVE (<why>) | NOT-RUN (<cause>)
REGISTRARS: <n> obligated, <n> PASS, <n> FAIL, <n> not-project-verifiable (informational), <n> NOT-RUN
GATUS: PASS | FAIL | missing | INCONCLUSIVE (<why>) | NOT-RUN (<cause>) | n/a (not obligated — not public/no domain)
LOGS: PASS (clean window) | FAIL — <signature> | INCONCLUSIVE (<why>) | NOT-RUN (<cause>)
PARITY: <n> agree / <n> disagree / <n> unresolved / <n> UNVERIFIABLE of <N> (contract v<N>, <n> not obligated) | NOT-RUN (no FROZEN contract) | NOT-RUN (<cause>)
VERDICT: DEPLOY CONFIRMED | VERIFICATION FAILED — <n> FAIL routed below | UNVERIFIED — no FROZEN parity contract → /fabrik-deploy-checklist | VERIFICATION INCOMPLETE — <n> non-PASS rows (CONFIRMED is claimable ONLY when every verdict-bearing row above reads PASS — zero FAIL AND zero NOT-RUN/INCONCLUSIVE/discriminator-void rows — AND the contract's own VERDICT line reads CONFIRMED (exit 0); GATUS `missing` = FAIL per Phase 4; informational registrar rows AND `n/a (not obligated)` rows are exempt. An UNVERIFIED contract caps the run at UNVERIFIED whatever the liveness rows say. An early stop with nothing failed is INCOMPLETE, never confirmed)
ROUTES: <one line per FAIL: item — route — what the operator/route must do> | none
```

Next command: none — terminal. This closes the trigger→verify loop this plan set opened: the operator's
`fabrik apply` triggered the deploy, this command is its own verification; a FAIL's named routes
(`/fabrik-review`, a registrar re-apply ask, or a rollback note) are the next actions, never auto-chained
from here. An `UNVERIFIED` verdict routes to `/fabrik-deploy-checklist` — author and freeze the parity
contract, then re-run this command.
