---
description: Post-`fabrik apply` certification, hub-side — identity (deployed SHA = tested SHA, migration head, image digest), DNS vs two siblings, the health endpoint asserting real deps, every `shape:` registrar derived live from `_REGISTRAR_ORDER`, Gatus green, logs clean, then the project's FROZEN parity contract (`scripts/verify_prod_parity.py`) executed against the LIVE service — no contract = UNVERIFIED, never CONFIRMED. Verify-only; every FAIL routes to an ask. Not `/fabrik-release` (readiness) or `/fabrik-service-test` (gauntlet). Stage: 6-release. TRIGGER — EN: "verify the deploy", "did fabrik apply work", "check the live service"; TR: "deploy'u doğrula", "apply çalıştı mı".
argument-hint: "[optional: spec path or service id to verify — omit to read specs/services/<id>.yaml for this project]"
---

Run this project's **post-deploy verification**: prove a service that just deployed is actually ALIVE, with a fresh probe this run, never a catalog/registry/env row read as proof. This command **verifies only**: no `fabrik apply`, no `fabrik destroy`, no registrar re-run, no file mutation — the verdict table is PRINTED (no report file; the run record is the durable trace). **It certifies against what was BUILT, not liveness alone**: the project's **parity contract** — `scripts/verify_prod_parity.py`, FROZEN by `/fabrik-deploy-checklist` — is executed in Phase 6. Without a FROZEN contract the verdict is `UNVERIFIED`: terminal, not success, and the signal to run the authoring command.

**You are at step 6 of the chain below — previous: `/fabrik-deploy` (VPS) or the operator's store submission · next: none, terminal (a FAIL's route is the next action).**

{{include:deploy-chain}}

**Where this runs:** hub-side, from `/opt/fabrik` (the hub carries fleet SSH creds). A project cannot reach its own VPS this way, and the WSL box's local `fabrik` bridge is a different network from the fleet's. Each phase is labeled `[anywhere]` (a public DNS/HTTPS probe) or `[hub-side]` (needs `ssh <target_vps> ...` or a hub-container `exec`).

{{include:run-record}}
{{include:orient}}

{{include:delegated-reads}}
{{include:grounding-artifact}}

## ⚠️ Termination contract

You are done when EVERY checklist item (identity, DNS, health/readiness, registrar obligations, Gatus, logs, parity) is TERMINAL — one of four token FAMILIES: **PASS (with evidence: a command's real output, this run) · FAIL (with evidence + a named route) · INCONCLUSIVE (the probe cannot discriminate — the re-probe instruction is the route) · NOT-RUN (<the cause>)** (the Output block's spellings: `discriminator void` is DNS's INCONCLUSIVE, `missing` is GATUS's FAIL, `n/a (not obligated)` the spec-voided NOT-RUN) — and the verdict table is printed (EXCEPT the Phase-0 store-surface hand-back, which emits its own two-line form INSTEAD). An item without a fresh-this-run command output is a guess; `n/a (not obligated)` cites the spec flag instead. You never perform a fix, redeploy or registrar mutation: a FAIL's route is always `/fabrik-review` (a code-side defect), a rollback note (name the prior known-good SHA, do not roll back), or a registrar re-apply **ask** to the operator — routes are asks, never actions. **Context is never a reason to stop.** If >3 items FAIL on the same root cause (e.g. the VPS is unreachable), stop early and report it; every unreached item carries `NOT-RUN (<the shared root cause>)`.

## Phase 0 — Resolve the target

0. **⚠️ SURFACE GUARD — this command is VPS-only.** If `project.yaml::type` is a STORE surface — `mobile-app`, `chrome-extension`, `desktop-app` — there is no spec, `domain` or `target_vps`. **Stop and hand back**, naming what a store release needs verified: the build's provenance (the submitted artifact came from a pushed SHA), the store-side review/rollout state, and the first-ring crash/ANR signal. That is a clean terminal ending, not a `BLOCKED:`, and emits its OWN two-line form instead of the Output block: `DEPLOY-VERIFY: <project> — STORE SURFACE, handed back` + `NEEDS: <the three store verifications named above>`.
1. Read `specs/services/<id>.yaml` (or the path/id argument): `domain`, `target_vps` (default `vps1`), and every `shape:` flag — the obligation list Phase 3 checks.
2. **Spoke-aware from here on.** `vps1` (hub) → shared infra (`postgres-main`, `redis-main`, GlitchTip, Gatus, Authelia) is on the app's host. `vps2/vps3` (spoke) → the app reaches it at the registrar-injected mesh IP `10.99.0.1:<port>`; a spoke's `.env` showing that, not `postgres-main`, is not a defect.
3. Read `docs/RESILIENCE.md` §2 (the dependency inventory the health endpoint should assert) and the **fleet-AI sections** of `docs/DEPLOYMENT.md` + `docs/OPERATIONS.md` (D-065) as the declaration inputs.
4. **Read the parity contract's header** — `scripts/verify_prod_parity.py --header` in the project checkout (`Status`, `Version`, `Date`). **`Status: FROZEN` is the obligation gate**: absent, unparseable or `DRAFT` ⇒ the VERDICT is **`UNVERIFIED — no FROZEN parity contract`** (terminal, never `CONFIRMED`) and `ROUTES` names `/fabrik-deploy-checklist`. Every other phase still runs, but Phase 6 reports `NOT-RUN (no FROZEN contract)`. Absent is the NORMAL state of a project scaffolded before 2026-09-02 (the stub is never synced) — the route to `/fabrik-deploy-checklist` is the whole answer.

## Phase 1 — DNS: live, not merely cataloged `[anywhere]`

Resolve the spec's `domain` (`dig +short <domain>` or `getent hosts <domain>`) in the SAME probe run as two KNOWN-LIVE sibling domains on the same `target_vps`: `status.<target_vps>.ocoron.com` and a `domain:` from a deployed spec on that VPS (`grep -l 'target_vps: <vps>' specs/services/*.yaml`); never `gatus.<vps>.ocoron.com` / `grafana.<vps>.ocoron.com` (NXDOMAIN on vps1). Target resolves → **PASS**. Target fails AND both siblings resolve → **FAIL** (a real deploy gap). Target AND siblings ALL fail → **inconclusive** (outage or reachability gap): name it, re-probe later. **If a sibling fails to resolve while the target would otherwise FAIL, the discriminator is VOID** — report `discriminator void (sibling NXDOMAIN)`, never `inconclusive`, and re-probe with another sibling. Never treat the spec's `domain:`, a `PORTS.md` row or a catalog entry as liveness evidence.

**Wildcard-DNS control probe — spoke targets only.** `*.vps2.ocoron.com` and `*.vps3.ocoron.com` resolve ANY subdomain (`vps1` has no wildcard), so on a spoke a DNS PASS is **non-evidentiary**. First run `dig +short <random-nonsense-string>.<target_vps>.ocoron.com`; if that ALSO resolves, the evidence moves to Phase 2's HTTPS layer (a deployed service answers its own 2xx/redirect/auth challenge; an undeployed name gets Traefik's default 404), recorded as `wildcard DNS — resolution non-evidentiary, discriminating at HTTPS layer`.

## Phase 1b — Identity: the deployed build IS the tested build `[hub-side]`

Layer 1 of the contract corpus — **nothing below it means anything if it fails.** Over the fleet SSH path against the target's checkout (`/opt/<app>`):

1. **Deployed SHA == tested SHA** — `ssh <target_vps> "cd /opt/<app> && git rev-parse HEAD"` vs the SHA the release's green CI / `/fabrik-release` READY verdict names; never the deploy log's echo.
2. **Migration head == repo head** (DB types) — `alembic current` in the app container vs `alembic heads` in the checkout (trytond: `ir_module` state vs the shipped module list; no migration tool ⇒ `n/a (not obligated)` with the type named).
3. **Image digest == the built digest** — `docker inspect --format '{{.Image}}' <container>` vs `docker images --digests` on the target.
4. **Lockfile hash == the tested dependency set** — `sha256sum` of the checkout's lockfile vs the running container's.

**Early-stop:** an identity FAIL is a shared root cause — every later row carries `NOT-RUN (identity)`, the verdict is `VERIFICATION FAILED`, and the route is a rollback note naming the prior known-good SHA. PASS requires all four; a row the hub cannot probe is `INCONCLUSIVE (<why>)`, never PASS.

## Phase 2 — Health + readiness (real dependency assertions, liveness kept separate) `[anywhere]`

Never conflate the two checks: `/healthz` is contractually a **static liveness probe** (always 200), so a static 200 there is CORRECT, not a FAIL.

1. **The spec's health endpoint.** Read `health.path` from the spec (fallback `/health`; `saas-skeleton` defaults `/api/health`); `curl -sf https://<domain><health.path>`. **PASS** requires a 2xx AND evidence that a real dependency was tested (a DB-backed service's route must actually run `SELECT 1`, per `docs/RESILIENCE.md` §2). A provably static 200 is a **FAIL** — route to `/fabrik-review` (a code defect, not a deploy defect).
2. **`/healthz`** (if reachable) — a static 200 is correct; never fail this one.
3. **`/readyz`** — verify-if-present only: a 2xx is **PASS**; absence is **not a FAIL**. Never induce a pause to exercise the 503 contract; report it as informational and never gate the phase verdict on it.

## Phase 3 — Registrar obligations: the spec's `shape:` truth, deployed `[hub-side]` (`.env` rows) / `[anywhere]` (probe rows — see column)

For every `shape:` flag true in Phase 0, confirm its registrar landed. The authoritative `.env` read is the **REMOTE** `/opt/<app>/.env` on the target VPS (where `inject_env` writes), never the local dev `.env`; where a probe can prove the same fact, **prefer the probe** and use the remote `.env` as corroboration.

**⚠️ The registrar denominator is DERIVED at RUN time, never copied from this file.** Read `src/fabrik/orchestrator/infrastructure.py::_REGISTRAR_ORDER` live and emit ONE row per registrar it names, in its order, keyed by name. A registrar the registry names that has no rule text here is **`FAIL (unmapped registrar → /fabrik-review)`**, never a silent skip. State the count: `REGISTRARS: <n> named by _REGISTRAR_ORDER`. The auto-discovered services (`traefik`, `promtail/loki`, `cadvisor`) are not registrars and stay informational rows.

| Flag | Registrar | Verify via |
|---|---|---|
| `needs_database: true` | `postgres` | remote `.env` `DATABASE_URL` present, pointed at `postgres-main:5432` (hub) or `10.99.0.1:5432` (spoke) — never `localhost` |
| `needs_cache: true` | `redis` | remote `.env` `REDIS_URL` present, same hub/spoke rule — `REDIS_HOST` is never injected; do not accept it as evidence |
| `kind ∈ {service, worker, wordpress}` | `glitchtip` | remote `.env` `GLITCHTIP_DSN`/`SENTRY_DSN` present and non-empty |
| `exposes_metrics: true` + `domain` set | `prometheus` | `curl -sf https://<domain>/metrics` returns a real Prometheus text-format body, not 404/401 |
| `has_search_feature: true` | `meilisearch` | a query against the service's OWN search route returns results (preferred), OR a hub-side index-existence check (`exec` against the hub meilisearch container) — a `.env` check is never valid evidence here |
| `is_admin_dashboard: true` + `domain` set | `authelia` | the admin route unauthenticated returns a redirect/401 to the Authelia flow, never a bare 200 |
| `watchdog.enabled` (default true) | `watchdog` | remote `.env` `WATCHDOG_DB_URL_RO` present (+ `WATCHDOG_DB_URL_RW` when `needs_database`), OR the sidecar `fabrik/watchdog:<project_id>` running on the target VPS |
| `has_persistent_data: true` | `backrest` | **not project-verifiable** — informational, never a FAIL |
| always / auto-discovered | `grafana` (deploy annotation), `promtail/loki`, `cadvisor` | **not project-verifiable** — informational only |
| auto-discovered | `traefik` | implied by Phase 1 DNS + Phase 2 HTTPS succeeding |

A flag `true` with no corresponding remote-`.env` var or live probe response is a **FAIL**, routed as a **registrar re-apply ask to the operator** (name the exact flag and spec path, never run `fabrik apply`). A flag honestly `false` and absent is not checked.

## Phase 4 — Gatus probe `[anywhere]`

If `is_public: true` and `domain` is set, read Gatus's own status (public page or API) for this domain's endpoint. Missing = **FAIL**, routed as a registrar re-apply ask. Present but red = **FAIL**, routed to `/fabrik-review` if the redness traces to this service's own `/health` contract, otherwise name the failing dependency.

## Phase 5 — Bounded log scan `[hub-side]`

Pull a bounded recent window of THIS service's container logs from the TARGET VPS (`ssh <target_vps> docker logs --since <window> <container>`) — never local Docker (a false-clean trap). Grep for `Traceback`, `FATAL`, `OOMKilled`, `exit code`, a restart-loop timestamp pattern. Zero hits = **PASS**. Any hit = **FAIL**: quote the line and route to `/fabrik-review`, unless the signature is infra-side (OOM against too-low `deploy.resources.limits.memory`), in which case name that as the fix.

## Phase 6 — Parity (contract-driven, BLOCKING) `[anywhere]`

**The product's declared contents, checked against the LIVE service.** Skipped only by Phase 0 step 4 (`NOT-RUN (no FROZEN contract)`).

1. **One leg per SITE, each where it can reach — then ONE merge.** Every row declares its site (`@site("container")` / `@site("host")`; undeclared = `hub`), and the runner executes exactly three legs:
   - **hub leg** — from the PROJECT's checkout with the PROJECT's interpreter: `cd /opt/<project> && .venv/bin/python scripts/verify_prod_parity.py --json --site hub > <run>/hub.json`. Never against a hub cwd.
   - **container leg** — inside the RUNNING container that can REACH the database, redis and the internal network. **Which container is the contract's to say, never yours to assume:** read `container_leg_service` from `scripts/verify_prod_parity.py --header` (`CONTAINER_LEG_SERVICE` in the contract); empty means the project's own app service. Resolve it to the running container (`ssh <vps> "docker compose -f /opt/<project>/compose.yaml ps -q <service>"`). The vendored comparator is gitignored in projects, so ship both files first, then run: `ssh <vps> "rm -rf /tmp/health_probe" && scp -r libs/health_probe <vps>:/tmp/health_probe` (a repeat `scp -r` into an existing copy nests the package), `ssh <vps> "docker exec -u 0 <leg> rm -rf /app/libs/health_probe && docker exec -u 0 <leg> mkdir -p /app/scripts /app/libs && docker cp /opt/<project>/scripts/verify_prod_parity.py <leg>:/app/scripts/ && docker cp /tmp/health_probe <leg>:/app/libs/"` (`docker cp` into a MISSING `/app/libs` makes it the package itself; `-u 0` because the image's user may not own `/app`; a failed stage is a reason for `--unreachable` below, never swallowed), then `ssh <vps> "docker exec <leg> python /app/scripts/verify_prod_parity.py --json --site container" > <run>/container.json`. **The leg container must carry the comparator's runtime deps** (`httpx`, `psycopg2`/`redis`, `python-dotenv`). An `ImportError` in `container.json` is that, not a product FAIL: route it to the project (add the dep to the leg service's Dockerfile), never to a rollback. A `docker exec` dying with `executable file not found` (`python` absent — every Node image) is the OTHER class: the route is the CONTRACT (`/fabrik-deploy-checklist`: re-site those rows on the hub/host leg or declare a Python leg), never the Dockerfile. Both are `/fabrik-deploy-plan` Phase 2's to catch BEFORE the deploy; reaching them here is itself a finding for it.
   - **host leg** — on the VPS host for rows that need `docker ps` or a volume path. STAGE, then run. Liveness rows need only the script: `scp scripts/verify_prod_parity.py <vps>:/tmp/`. A comparison row also needs the comparator BESIDE the script (D-744), fresh and writable by nobody else (the stub refuses a group- or other-writable copy): `ssh <vps> "rm -rf /tmp/health_probe" && scp -r libs/health_probe <vps>:/tmp/health_probe && ssh <vps> "chmod -R go-w /tmp/health_probe"`. Then run: `ssh <vps> "cd /opt/<project> && PARITY_FILESTORE_PATH=<mount> python3 /tmp/verify_prod_parity.py --json --site host" > <run>/host.json`. A stub older than that rule reads only its own clone (`grep -q _comparator_root scripts/verify_prod_parity.py` fails for it), so stage and run it in a private clone layout instead, as ONE command line (the `$d` lives only in that shell): `d=$(ssh <vps> mktemp -d) && ssh <vps> "mkdir -p $d/scripts $d/libs" && scp scripts/verify_prod_parity.py <vps>:$d/scripts/ && scp -r libs/health_probe <vps>:$d/libs/ && ssh <vps> "cd /opt/<project> && PARITY_FILESTORE_PATH=<mount> python3 $d/scripts/verify_prod_parity.py --json --site host" > <run>/host.json; ssh <vps> "rm -rf $d"`.
   **A site the contract has no rows for** — when `--header` carries a `sites` object and that site's count is 0 — skips its REMOTE exec only: emit it from the hub, `scripts/verify_prod_parity.py --json --site <site> --unreachable "header: 0 rows" > <run>/<site>.json`, and merge it like any leg (its exit status is not the leg's verdict — a true zero can print `[]` and still exit non-zero; only the merge decides). A true zero adds no row; a wrong zero adds that site's rows as UNVERIFIABLE with `header: 0 rows` in their detail, so the header's count can never shrink the denominator. A header without `sites` runs every leg as above.
   A leg you CANNOT reach (no SSH, the container not running) is never skipped: emit its rows as UNVERIFIABLE from the hub — `scripts/verify_prod_parity.py --json --site container --unreachable "<why>" > <run>/container.json` — so the denominator stays whole and the verdict fails closed on that leg. **Read-only rows only** on every leg: a row marked `UNVERIFIABLE (mutating — …)` is named in the table, never executed.
2. Merge: `scripts/verify_prod_parity.py --verdict --rows-from <run>/hub.json <run>/container.json <run>/host.json` and **copy its two lines verbatim** into the Output block. The script EXECUTES the verdict algebra (`verdict()`: a row carrying ANY comparison key is a parity row; `match True` = numerator; `False` denies CONFIRMED; `None` on a parity row = ATTEMPTED-BUT-UNRESOLVED = fail closed, exit 2; a row with none of the keys is a liveness row outside the denominator; `not obligated` — a `shape:` flag — is the only thing that removes a row; exit 1 (a DOWN) outranks 2 outranks 0 and never upgrades a verdict). **Never re-derive the verdict in prose from the row list.** An exit 64 with no `VERDICT:` line is a REFUSED merge, not a verdict: its stderr lines name each miss by row id, or by leg file where the file itself is malformed — re-run the leg that produced (or should have produced) each named row from the contract at the deployed SHA and merge again; it is never a product FAIL and never a rollback.
3. Read every row's `{system, status, detail, expected, actual, match, compare_error}` with `.get()` (`compare_error` only when the comparator raised). `match True` → PASS (quote expected/actual); `False` → FAIL, route `/fabrik-review` (the deployed product differs from what was built) or a rollback note; `None` on a parity row → FAIL `attempted-unresolved (<compare_error>)`, route `/fabrik-deploy-checklist` (the comparator is broken); an `UNVERIFIABLE (<why>)` row → listed with its why, counted in the denominator, never PASS.
4. **State the denominator with every count**: `<n> agree / <n> disagree / <n> unresolved / <n> UNVERIFIABLE of <N> (contract v<N>, <n> not obligated)` — the `PARITY:` line the script prints. A row the project could not assert is visible as UNVERIFIABLE, never absent.

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

Next command: none — terminal. A FAIL's named routes (`/fabrik-review`, a registrar re-apply ask, or a rollback note) are the next actions, never auto-chained from here. An `UNVERIFIED` verdict routes to `/fabrik-deploy-checklist` — author and freeze the parity contract, then re-run this command.

{{include:close-chain}}
