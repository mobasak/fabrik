# Deployment plan — tryton-crm (BHD CRM stack: bridge + trytond + worker + crm-gotenberg)

Status: CONVERGED  (re-converged 2026-08-31 after the A1/A2 amendment + the predecessor step-diff; the earlier CONVERGED flip was FALSE and is recorded as such in the Pass Ledger)
Service: tryton-crm · Surface: **vps** · Target: **vps1** · Date: 2026-08-31
Authored by: /fabrik-deploy-plan · Plan stem: `2026-08-31-plan-deploy-tryton-crm`
Supersedes: `docs/development/plans/2026-08-11-plan-deploy-tryton-crm.md` (Status: DRAFT, never
converged, never executed). That plan was authored for the **v0.1.0** cut; **295 commits** have landed
since and the repo is now tagged v0.3.0. It is superseded, not deleted — its Phase-2 findings seeded the
spec annotations this plan re-verifies.

**Release readiness — proven FRESH in the SERVICE's repo this run:**

```
$ cd /opt/tryton-crm && .venv/bin/python scripts/final_gate.py --check --json
  status : success
  tier   : 2
  passed : 53  failed: 0

$ git -C /opt/tryton-crm log origin/mobasak/tryton-crm..HEAD --oneline    # (empty — pushed)

$ git -C /opt/tryton-crm status --short
 M .gitignore
```

**The one dirty file is adjudicated, not waived.** `.gitignore`'s diff is exclusively the
hub-generated *Fabrik-synced* block (`+.claude/hooks/mcp_watch.py`, `+scripts/rivals_run.py`,
`+scripts/thread_anchor.py`, `+.mcp.json`) — machine output from this hub's own governance-sync, not
authored work, and `.gitignore` ships nothing. The VPS deploys **pushed** state pulled from GitHub, so
a locally-dirty ignore file cannot reach the target. Release readiness stands.

**What actually deploys — and why it is NOT the v0.3.0 tag.** The spec pins
`source.branch: mobasak/tryton-crm` (`specs/services/tryton-crm.yaml:32`), so `fabrik apply` deploys the
**branch tip f4d80a2**, not the tag `v0.3.0` (a4e7c52). Measured this run, that gap is **22 commits and
ZERO application-code changes**:

```
$ git -C /opt/tryton-crm diff --name-only v0.3.0..HEAD | sed 's|/[^/]*$||' | sort | uniq -c | sort -rn
      2 docs/reference
      2 docs
      1 tests/ui
      1 scripts/trytond
      1 INDEX.md
      1 docs/development/reviews
      1 CHANGELOG.md

$ git -C /opt/tryton-crm log --oneline v0.3.0..HEAD -- src/     # (empty — no src/ change)
```

So "deploy v0.3.0" and "deploy the branch tip" are the **same shipped application**; the delta is UI
certification tests, docs, and a role-probe seeder. No spec change or tag pin is needed, and none is
proposed. (Recorded because the operator named v0.3.0: what runs is f4d80a2 ≡ v0.3.0 in application terms.)

---

## Context Ledger

Ground-truth sources this plan was authored from — all re-read this run, none inherited:

| Source | What it settled |
|---|---|
| `specs/services/tryton-crm.yaml` | the stack shape, env block, secrets, monitoring target, resources |
| `/opt/tryton-crm/compose.yaml` | the 4 services, memory limits, absence of host ports, the `${VAR}` surface |
| `/opt/tryton-crm/.env.example:174-188` | the S10 wizard contract — the BRIDGE_INTERNAL_TOKEN blocker below |
| `/opt/tryton-crm/scripts/trytond/seed_role_probe_users.py:1-24` | probe-user provenance + the deactivate contract |
| `fabrik plan specs/services/tryton-crm.yaml` | the 7-registrar resolution + the DATABASE_URL placeholder value |
| live vps1 (`free -h`, `docker ps`, `psql`, backrest config) | headroom, the gotenberg collision, the empty DB, backup coverage |
| `docs/development/reviews/2026-08-10-tryton-crm-deploy-readiness-review.md` | the A1/A5/B1/B2/B3/M2/M3 class definitions |

## File Scope (owned paths — what the DEPLOY will mutate)

- remote `/opt/tryton-crm/` on vps1 — the git clone, `compose.yaml`, generated `.env`
- remote docker state — 4 containers, the `trytond-filestore` volume, `fabrik` network attachments
- `postgres-main` — a new `tryton` database + role (postgres registrar)
- `redis-main` — an assigned index (redis registrar)
- hub-side registrar artifacts — Gatus endpoint, Prometheus job `fabrik-tryton-crm`, Backrest plan, GlitchTip project, Grafana
- Cloudflare DNS — `tryton-crm.vps1.ocoron.com`
- this plan file (Status flips, ledger rows)

Explicitly NOT mutated: `/opt/tryton-crm` on the **hub** (read-only source of truth), the standalone
`gotenberg` container/stack, any other tenant's data.

## Phase 1 — Target decision with evidence

**`target_vps: vps1`.** Not a preference — a constraint. The stack needs `postgres-main` and
`redis-main`, which are **hub-only**; a spoke would pay a WireGuard round-trip on every query and every
proteus RPC (`agents-fabrik-core.md` § Fleet: spokes reach shared infra at `10.99.0.1:<port>`). Measured
headroom this run:

```
               total        used        free      shared  buff/cache   available
Mem:            11Gi       4.1Gi       693Mi       178Mi       7.3Gi       7.5Gi
  containers: 32 running / 32 total
```

The stack's declared ceiling is **4 G** — `tryton-crm` 512M + `crm-gotenberg` 1G + `trytond` 2G +
`trytond-worker` 512M (`compose.yaml:60,118,246,298`; the per-service attribution was corrected
2026-08-31 — the DRAFT had gotenberg and the worker swapped. The 4G SUM was right, which is exactly
why the re-derivation pass missed it: it re-counted the total and never re-checked the mapping) — against 7.5 Gi available. It fits with ~3.5 Gi
spare, but it is **over half the remaining headroom on the hub**, which is the single most important
capacity fact in this plan and the reason Phase 8 watches memory first.

## Phase 2 — Spec ↔ code ↔ compose reconciliation

**Every `shape:` flag re-verified, not recalled** (`specs/services/tryton-crm.yaml:11-20`):

| Flag | Value | Verified at |
|---|---|---|
| `needs_database` | true | stack needs `postgres-main::tryton`; registrar preview resolves `postgres RUNS` |
| `needs_cache` | true | `pause_state.py` uses Redis; `redis RUNS` |
| `exposes_metrics` | true | `/metrics` route at `src/tryton_crm/main.py:53`; `prometheus RUNS` |
| `is_public` | true | tenant self-service login via compose Traefik `HostRegexp` |
| `is_admin_dashboard` | false | deliberate — Authelia would block tenant login; `authelia skipped` |
| `has_persistent_data` | true | `trytond-filestore` volume; `backrest RUNS` |
| `has_search_feature` | false | `meilisearch skipped` |

Registrar resolution, embedded verbatim in `## Evidence` — **7 RUN, 3 correctly skipped**. No lying flag.

**A1 (placeholder semantics) — VERIFIED SAFE.** `fabrik plan` emits
`DATABASE_URL=postgresql://placeholder:placeholder@postgres-main:5432/placeholder`. The merge guard
`_is_placeholder` is **value-scoped** (used `src/fabrik/orchestrator/deployer_ssh.py:649`, defined `:708`)
— it protects an already-injected real value only when the spec value contains the literal substring
`placeholder`. This value does. So a re-apply will **not** clobber the injected DSN. Correspondingly
`TRYTOND_DATABASE_URI` is deliberately ABSENT from the spec, because compose derives it via
`${TRYTOND_DATABASE_URI:-${DATABASE_URL:-}}` (`compose.yaml:148`) and any set value would win forever.

**A5 (`from_env` precedence audit) — ONE BLOCKER FOUND.** The spec declares five (not four)
`from_env` secrets. Resolution audited by presence, never by value:

**The resolver, RE-DERIVED from the real code this round** (the first draft inherited this claim from the
A5 class definition and was wrong about it). Two code paths, identical semantics —
`src/fabrik/orchestrator/__init__.py::_load_secrets:383-405` and `src/fabrik/cli.py:552-578`:

1. read `/opt/<spec.id>/.env` — the **project's** `.env` (`__init__.py:384-395`);
2. else `os.getenv(key)` — the hub **PROCESS** env (`__init__.py:401`);
3. else `logger.warning("Secret %s not found in environment")` and the key is **omitted**. Not a
   hard fail. **The deploy goes GREEN with the secret absent.**

⚠️ **The hub's `/opt/fabrik/.env` FILE is never consulted by either path.** A value living only there
does not reach the container. That correction turns one blocker into two:

| `from_env` secret | project `.env` | hub PROCESS env | verdict (executed) |
|---|---|---|---|
| `SERVICE_INTERNAL_SECRET_KEY` | present | no | resolves ✓ |
| `TRYTOND_RPC_USER` | present | no | resolves ✓ |
| `TRYTOND_RPC_PASSWORD` | present | no | resolves ✓ |
| `CONSUMER_TOKENS` | **absent** | **no** | ⛔ **BLOCKER — omitted with a warning** |
| `BRIDGE_INTERNAL_TOKEN` | **absent** | **no** | ⛔ **BLOCKER — omitted with a warning** |

`CONSUMER_TOKENS` being absent is the more severe of the two: it is the **entire M2M consumer registry**
(`src/tryton_crm/internal_auth.py:83` — `os.getenv("CONSUMER_TOKENS","")`, empty ⇒ `{}`), so with it
unset *every* internal call 401s, the wizard's included. Both must be written into
**`/opt/tryton-crm/.env`** — the only surface step 1 reads.

⛔ **BRIDGE_INTERNAL_TOKEN is unset on every surface, and production REQUIRES it.** This is the plan's
single hard pre-flight blocker, and the project's own config surface documents the failure mode
(`.env.example:179-183`): the S10 quotation wizard runs inside trytond and calls the bridge; it falls
back to `SERVICE_INTERNAL_SECRET_KEY`, which the bridge accepts **only while `ENVIRONMENT != production`**
— and the spec sets `ENVIRONMENT: production` (`specs/services/tryton-crm.yaml:44`). So in production the
fallback is a **non-empty token that is rejected**, which is strictly worse than empty: being non-empty it
defeats the wizard's own "not configured" guard, and the operator sees a bare
`The document service failed (401)` with nothing naming the knob. Compose confirms the empty default
(`compose.yaml:143` → `BRIDGE_INTERNAL_TOKEN=${BRIDGE_INTERNAL_TOKEN:-}`).
**Remedy is S0 — mint a `CONSUMER_TOKENS` consumer with `write` scope for the tenant org and set its
token as `BRIDGE_INTERNAL_TOKEN`.** Deploying without it ships a CRM whose offer-send is 401 DOA.

**The token shape is PROVEN, not assumed** (`src/tryton_crm/internal_auth.py:78-112`):
`_parse_consumer_registry()` parses `CONSUMER_TOKENS` as
`{"<name>": {"token": "<secret>", "orgs": [...], "scopes": [...]}}` and builds a `{token: Consumer}`
lookup; the bridge authenticates on the `X-Internal-Token` header. The wizard sends
`BRIDGE_INTERNAL_TOKEN` as that header, so it **must equal the `token` value of a consumer entry** —
confirming `.env.example:182`. Two S0 correctness constraints the same code imposes: `orgs`/`scopes`
**must be lists** (a bare string char-splits — the consumer is skipped, `:100-104`), and a duplicate
token across two consumers is rejected rather than silently overwritten (`:111`). Omitted scopes deny.

**B1 (in-container semantics) / naming collision — LIVE, re-verified this run.** A standalone
`gotenberg` container is running on vps1 right now and owns both the container name and the `gotenberg`
alias on the shared `fabrik` network. The stack's own service is therefore named `crm-gotenberg` and the
bridge is pointed at it explicitly (`GOTENBERG_URL=http://crm-gotenberg:3000`,
`specs/services/tryton-crm.yaml:60`). The code default `http://gotenberg:3000` would resolve to the
basic-auth'd standalone and 401. S9 probes this by name.

**Monitoring target — explicit, and load-bearing.** `monitoring.target: tryton-crm:8000`
(`specs/services/tryton-crm.yaml:41`). Without it the saas-skeleton branch aims at `tryton-crm-api:8000`,
which does not exist in this compose → `up` 0 forever.

**Dead field, recorded so no one reconciles against it:** `expose.internal_only`
(`specs/services/tryton-crm.yaml:25`) is defined at `spec_loader.py:123` and read by no orchestrator
code. Routing truth is the compose's Traefik labels.

## Phase 3 — Infra prerequisites

- **DNS** — `tryton-crm.vps1.ocoron.com` is fleet-automated by site-provisioner (`fabrik apply` creates
  the A record), so the runbook's DNS step is a `dig` **verification**, never an operator gate.

⛔ **BLOCKER 2 — the tenant wildcard cannot be issued as the fleet stands. Probed live, not assumed.**
The compose declares TWO routers requesting `certresolver=cloudflare`, not one — `tryton-crm-brand` AND the tenant front door `trytond-saas` (`compose.yaml:277`). The first draft named only the brand router, understating the scope. Both request
`tls.certresolver=cloudflare` with `domains[0].main=tojlo.com` / `sans=*.tojlo.com`
(`/opt/tryton-crm/compose.yaml:86-88`). Live traefik on vps1 (`/opt/traefik/traefik.yml:22-28`) defines
**exactly one** resolver:

```
certificatesResolvers:
  letsencrypt:
    acme:
      email: ob@ocoron.com
      storage: /acme.json
      httpChallenge:
        entryPoint: web
```

Two independent reasons this fails: (1) **there is no `cloudflare` resolver** for the router to use; and
(2) a **wildcard requires DNS-01** — `httpChallenge` is HTTP-01, which Let's Encrypt will not issue a
wildcard against, so even renaming the resolver would not work. The acme store holds 46 certificates and
**no `tojlo.com` among them** — the single `tojlo` substring match is `main=tojlo.shop`, a different
domain (evidence below). Consequence: the primary router (`tryton-crm.vps1.ocoron.com`,
`certresolver=letsencrypt`, `compose.yaml:70`) is **fine**; every tenant `<slug>.tojlo.com` would fail
TLS. Behavior **B5 cannot pass** until a DNS-01 `cloudflare` resolver exists on vps1 — which needs a
fleet work — the Cloudflare credential already lives in `/opt/fabrik/.env` AND in the site-provisioner
container, and `drivers/dns.py` already drives Cloudflare through it. Carried as **S0b**, mailed to tryton-crm
(`01M1AXWSG8CWZX4D6WAJFV5E4C` — see Self-audit) because the compose's expectation and the fleet's reality must be
reconciled by one side or the other.
- **Network** — external `fabrik` network confirmed present on vps1 this run.
- **Database** — `postgres-main` carries **no** `tryton` database today (verified: the `pg_database`
  query returned empty). The target is genuinely fresh, which is what makes the probe-user question below
  answerable rather than speculative.
- **Registrar preview** — embedded in `## Evidence`.

**Seeded-fixture risk — grounded independently and CLOSED for this deploy.** The certification probe
seeder (`scripts/trytond/seed_role_probe_users.py`) creates `cert-role-`-prefixed users and states they
are "NEVER tenant deliverables". Two facts retire the risk here: it is invoked by **no** deploy artifact
(grep across compose/Dockerfile/entrypoints/`*.sh` returned nothing outside tests and its own file), and
it is **dry-run by default** (`--apply` required). Combined with an empty target DB, no probe user can
carry into production. Retained as battery item **S13.6** — assert zero `cert-role-%` logins post-init —
because "cannot happen" is worth one cheap query on a system-of-record.

## Phase 4 — Ordered runbook

Every step: stable id, exact command, verification, retryability, rollback. Steps are numbered list
items by design (headings would inflate the citation denominator). Grounding for the sequence:
`src/fabrik/orchestrator/deployer_ssh.py:649` (env merge) and the registrar order in the Phase-3 preview.

1. **S0 · ✅ DONE 2026-08-31 (executed this run; kept for the ledger + re-run safety)** — write BOTH
   missing secrets into **`/opt/tryton-crm/.env`** (the hub's own `.env` is NOT read — proven in Phase 2).
   Mint a consumer with `write` scope for the tenant org inside `CONSUMER_TOKENS`
   (`{"crm-bridge": {"token": "<secret>", "orgs": ["<org_id>"], "scopes": ["read","write"]}}` — `orgs`
   and `scopes` MUST be JSON lists), then set that consumer's **same token** as `BRIDGE_INTERNAL_TOKEN`.
   *Verify:* `grep -c '^BRIDGE_INTERNAL_TOKEN=.\+' /opt/tryton-crm/.env` → `1`;
   `grep -c '^CONSUMER_TOKENS=.\+' /opt/tryton-crm/.env` → `1`; and
   `python3 -c "import json,os;d=json.load(open('/dev/stdin'));…"` confirming the token appears as a
   consumer's `token` value. Values never echoed.
   *Rollback:* remove the added lines; nothing has deployed yet.
   **This gate is why the plan exists — without it S13.4 fails with a misleading 401, and with
   `CONSUMER_TOKENS` unset EVERY internal call 401s.**

   **✅ EXECUTED AND PROVEN THROUGH THE REAL CODE PATH, not by shape-checking the file.** The org id
   did not need the pending mail after all — the project documents it in its own
   `.env.example:24` (`"orgs":["bhd-group"]`), and this IS the BHD stack. Token minted with the
   project's own prescribed method (`secrets.token_urlsafe(32)`, `.env.example:17`), written to
   `/opt/tryton-crm/.env` (backed up first to `backups/.env.backup.20260831-064012`, mode 600).
   Verified by importing tryton-crm's own `internal_auth` with `ENVIRONMENT=production`:

   ```
   resolve_consumer(BRIDGE_INTERNAL_TOKEN) -> Consumer(name='crm-bridge')
   authorized orgs                         : ['bhd-group']
   scopes                                  : ['read', 'write']
   may_provision (must be False)           : False
   dev shared-secret fallback enabled?     : False   (prod fail-closed, as designed)
   a WRONG token is rejected               : True
   ```

   `may_provision` is deliberately **False**: it is a namespace-level entitlement to create tenants,
   and nothing in the offer-send path needs it. Consequence to know before first tenant traffic —
   authorization requires the request's `org_id` to be IN this allowlist, or the tenant to have been
   `provisioned_by` this same consumer (`api/deps.py:134-139`; `provisioned_by is None` falls back to
   the allowlist, never to "anyone"). So a tenant whose `org_id` is not `bhd-group` will 403 until it
   is added here. That is correct isolation, not a defect — but it makes the allowlist a
   per-tenant-onboarding step, which `docs/reference/tenant-onboarding.md` should carry.
2. **S0b · FLEET WORK (NOT an operator gate — corrected 2026-08-31) · retryable · blocks behavior B5 only**
   — the tenant wildcard TLS. The first draft called this an `OPERATOR-GATE` needing "a Cloudflare API
   token from the operator". **That ask was fabricated, and the correction matters more than the step:**
   the fleet already holds the credential in TWO places — `/opt/fabrik/.env` carries
   `CLOUDFLARE_API_TOKEN` *and* `CLOUDFLARE_ZONE_ID_TOJLO` (the exact zone), and the live
   `site-provisioner` container on vps1 (healthy, up 4 weeks) carries `CLOUDFLARE_API_TOKEN` + account id
   + email. `src/fabrik/drivers/dns.py` is already a full Cloudflare client through site-provisioner
   (`/api/cloudflare/dns/*`, `/api/cloudflare/zones/*`). DNS and its credentials are FLEET-AUTOMATED;
   none of this is the operator's homework.
   *Action:* back up `/opt/traefik/traefik.yml`, add a DNS-01 `cloudflare` certresolver using the
   existing `CLOUDFLARE_API_TOKEN`, restart traefik.
   *Verify:* `sudo grep -A4 cloudflare /opt/traefik/traefik.yml` shows a `dnsChallenge`; after the first
   router load `*.tojlo.com` appears in `/opt/traefik/acme.json`.
   *Rollback:* restore the backup, restart traefik. The primary `tryton-crm.vps1.ocoron.com` router uses
   `letsencrypt` throughout and is unaffected either way.
3. **S1 · retryable** — pre-flight re-proof: service gate green, branch pushed, target DB still absent,
   `fabrik` network present.
   *Verify:* the four commands in `## Evidence` reproduce their outputs.
   *Rollback:* n/a (read-only).
4. **S2 · `window-open` · retryable once** — open the autoheal window before anything can leave a
   container legitimately unhealthy (trytond module init runs minutes; autoheal's worst case to unhealthy
   is shorter — the B3 class).
   `ssh vps "sudo bash -c 'mkdir -p /run/fabrik-autoheal && printf \"%s %s\n\" 2026-08-31-plan-deploy-tryton-crm 2026-08-31T03:14:21Z > /run/fabrik-autoheal/pause.owner && touch /run/fabrik-autoheal/pause'"`
   (owner FIRST, pause second — deliberate.)
   *Verify:* both files exist and `pause.owner` begins with this plan's stem; then wait for a `PAUSED`
   line newer than the touch in the healer's log, **bounded at 5 minutes** — no `PAUSED` within 5 min
   means the healer cron is absent or wedged → halt.
   *Rollback:* the S8 guarded close.
5. **S3 · retryable · ~5-15 min · ⛔ EXPECTED TO FAIL, AND MUST CARRY `--keep-on-failure`** —
   `FABRIK_BUILD_TIMEOUT=1200 fabrik apply specs/services/tryton-crm.yaml --keep-on-failure`
   from `/opt/fabrik`. Builds `Dockerfile.trytond`, creates the `tryton` DB + role, injects `DATABASE_URL`
   and the Redis index, writes `.env`, brings the stack up.
   ⚠️ **This step does NOT reach the registrars, and its failure is the DESIGNED path** — S3a proves
   `up -d --wait` cannot pass before the Tryton schema exists. Two consequences were mis-stated by the
   previous revision of this step, both re-derived from the orchestrator this run:
   - **The old verify criterion ("command reports deployment complete") was UNREACHABLE** and directly
     contradicted S3a's own "`fabrik apply` in S3 WILL FAIL WITHOUT THIS". A step whose success
     criterion cannot be met is a step that reads as broken when it is behaving exactly as designed.
   - **Without `--keep-on-failure` the failure DELETES the DNS record this step just created.**
     `deploy()` runs `_provision_dns` (step 3, `orchestrator/__init__.py`:163) which records
     `add_resource("dns", domain, zone=…)`; `deployer.deploy` (step 4) then raises `DeployError` on the
     `--wait` timeout; the handler at `:213-216` sees a NON-empty `created_resources` and rolls back,
     and `_rollback_dns` (`rollback.py`:186) deletes the record — raising `RollbackError` if that
     delete itself fails. `--keep-on-failure` (`cli.py`:420, plumbed to `deploy(keep_on_failure=…)` at
     `:529`) suppresses exactly this. The app itself is never torn down either way: no code path
     records a `"compose"` resource (grep of every `add_resource(` call in `src/fabrik/`), so
     `_rollback_compose` is unreachable here and `/opt/tryton-crm` survives for S3a to init.
   *Verify:* the command FAILS at the `--wait` step with trytond unhealthy — that is the PASS condition
   here. Assert all four containers exist and the DNS record survived:
   `ssh vps 'sudo docker ps -a --format "{{.Names}}" | grep -E "^(tryton-crm|trytond|trytond-worker|crm-gotenberg)$"'` → 4 lines,
   and `dig +short tryton-crm.vps1.ocoron.com` → `172.93.160.197` (proves `--keep-on-failure` held).
   If the dig is EMPTY the flag was omitted — re-run S3 with it; S3b will recreate the record either way.
   *Rollback:* S-RB below.
6. **S3a · ⛔ THE STEP THE FIRST PLAN MISSED · retryable · ~10 min** — initialise the Tryton database.
   **`fabrik apply` in S3 WILL FAIL WITHOUT THIS, and the failure is not optional.** Proven mechanically:
   `deployer_ssh.py:64-65` runs `docker compose up -d --wait` for a health-enabled service (this spec sets
   `health.disabled: false`), and trytond's healthcheck asserts the database is a *Tryton* database via
   `common.db.list()` (`compose.yaml:262`). The postgres registrar creates an **empty** PG database, and
   **nothing initialises the Tryton schema**: `Dockerfile.trytond` bakes `/opt/crm-init/10-init-modules.sh`
   into the image, the compose sets **no `command:`** for trytond, and the base `tryton/tryton:8.0`
   entrypoint is a bare `exec "$@"` that scans no init directory. So the healthcheck can never pass, and
   `--wait` blocks until the deployer's 120 s ssh timeout and raises.
   *Command (uses the BAKED script, deliberately — see the warning below):*
   `ssh vps 'cd /opt/tryton-crm && sudo docker compose run --rm trytond sh /opt/crm-init/10-init-modules.sh'`
   *Verify:* `ssh vps "sudo docker compose -f /opt/tryton-crm/compose.yaml run --rm trytond python3 -c \"import xmlrpc.client;print('tryton' in xmlrpc.client.ServerProxy('http://trytond:8000/rpc/',allow_none=True).common.db.list())\""` → `True`.
   *Rollback:* S-RB (drop the database); the init is idempotent, so a partial run is re-runnable rather than
   corrupting.
   ⚠️ **Do NOT substitute the inline command in the project's `OPERATIONS.md` §5b.** It activates a SUBSET —
   9 modules, and `account_payment_clearing` is **absent** from it (0 occurrences there vs 2 in the baked
   script). The script's own comment records why that matters: without that module "a cheque settles
   NOTHING… a fresh production deploy [gets] `account_dunning` with no way to settle one by cheque." A CRM
   initialised from the §5b snippet comes up looking healthy and silently cannot reconcile payments. Filed
   to tryton-crm.
7. **S3a-2 · ⛔ FOUND BY SWEEPING THE NEW COLD-START CLASS, not by the checklist row · retryable** —
   create the bridge's trytond service user. `10-init-modules.sh` invokes ONLY `init_company.py`
   (`scripts/trytond/10-init-modules.sh:110`); it does **not** create `crm-bridge-svc`. But `.env` sets
   `TRYTOND_RPC_USER=crm-bridge-svc`, and `proteus_client._connect()` (`src/tryton_crm/proteus_client.py:145`)
   authenticates to trytond as that login. On a fresh database that user does not exist, so **every
   bridge→trytond call raises `ProteusConnectionError` while `/health` still reports fine** — the stack
   looks deployed and is functionally dead for anything touching the ERP.
   *Command:* `ssh vps 'cd /opt/tryton-crm && sudo docker compose run --rm -v /opt/tryton-crm/scripts:/scripts:ro trytond python3 /scripts/trytond/create_rpc_service_user.py'`
   *Verify:* a proteus connect as `crm-bridge-svc` succeeds — proven by battery item S13.3 (the write path),
   which cannot pass without it.
   *Rollback:* S-RB.
   ⚠️ **Do NOT "fix" a failure here by letting `TRYTOND_RPC_USER` fall back to `admin`.** That default is
   what `create_rpc_service_user.py` exists to eliminate, and its docstring states the stakes exactly:
   trytond's login form accepts any user on any host, so on a public `<slug>.tojlo.com` `admin` becomes
   typeable from the open internet — and `TRYTOND_RPC_PASSWORD`, an M2M secret sitting in the bridge's
   env, is that account's password. "One credential, two exposure classes."
8. **S3a-3 · ⛔ FOUND BY THE STEP-DIFF (predecessor S10) · OPERATOR-GATE · verify: in-session** —
   propagate the RPC credential. `create_rpc_service_user.py` **GENERATES** a fresh 32-char password
   (`:48-51`) and prints it **once**; `--write-env` targets `parents[2]/.env` and is DEAD in-container. So
   the moment S3a-2 runs, the `TRYTOND_RPC_PASSWORD` already in `/opt/tryton-crm/.env` goes **STALE** — it
   no longer matches the Tryton user, and the bridge cannot authenticate. Capture the printed value and
   write it to `TRYTOND_RPC_PASSWORD` in the project `.env` on **both** hub and vps1 (the hub copy is what
   `from_env` reads first — Phase 2), backing up each first.
   *Verify:* `ssh vps 'sudo docker exec tryton-crm sh -c "test -n \"$TRYTOND_RPC_PASSWORD\" && echo SET"'` → `SET`;
   compare sha256 prefixes across the two copies. Never echo the value.
   *Rollback:* restore the `.env` backups.
9. **S3a-4 · ⛔ FOUND BY THE STEP-DIFF (predecessor S7 — the B2 stale-Pool 500s trap) · retryable** —
   restart trytond + worker after the init. Module activation leaves connection pools stale; `fabrik
   apply`'s `up -d` does NOT recreate a container whose config is unchanged, so S3b alone does not fix it.
   *Command:* `ssh vps 'sudo docker restart trytond trytond-worker'`
   *Verify:* `ssh vps "sudo docker ps --filter name=trytond --format '{{.Names}} {{.Status}}'"` — PASS
   requires the literal `(healthy)` in BOTH status strings (`Up` alone means the healthcheck has not
   confirmed; wait out interval × retries).
   *Rollback:* none — a restart is the fix, not a mutation.
10. **S3b · retryable** — re-run `fabrik apply specs/services/tryton-crm.yaml` so `up -d --wait` now passes
   with trytond healthy, and the post-deploy registrars (which S3 never reached) actually run.
   *Verify:* the command reports deployment complete; `ssh vps 'sudo docker ps --filter name=trytond --format "{{.Status}}"'` shows `(healthy)`.
   *Rollback:* S-RB.
11. **S4 · `window-heartbeat`** — refresh the pause with the stem-guarded form (both files must exist, or
   `OWNERSHIP-LOST` → stop and disambiguate). No single in-window step may exceed 90 minutes; S3 is the
   only long one and is bounded by `FABRIK_BUILD_TIMEOUT=1200` (20 min).
12. **S5 · retryable** — DSN ordering check. `.env` is written before `DATABASE_URL` is injected on a first
   deploy (the evolution-api pattern). Confirm the real DSN landed rather than assuming the two-pass is
   needed.
   *Verify:* `ssh vps 'sudo docker exec trytond printenv TRYTOND_DATABASE_URI | sed "s|//[^@]*@|//***@|"'` → a
   `postgresql://***@postgres-main:5432/tryton` shape, **not** `placeholder`.
   *If it shows placeholder:* re-run S3 once (env-sync pass), then re-verify. `_is_placeholder` makes this
   safe — re-read this round and confirmed to be a **value substring test**,
   `return "placeholder" in value.lower()` (`deployer_ssh.py:708-717`, used `:649`), so the injected real
   value is protected. Note the compose already softens this case for the worker: `trytond-worker` runs an
   inline psycopg readiness poll that **waits rather than crash-looping** on an unready DSN
   (`compose.yaml:332-345`), so a placeholder DSN on first apply does not take down `up --wait`.
13. **S6 · retryable** — confirm the injected secrets are non-empty **without printing them**:
   `ssh vps 'sudo docker exec trytond sh -c "test -n \"\$BRIDGE_INTERNAL_TOKEN\" && echo SET || echo EMPTY"'` → `SET`.
   *Rollback:* fix on the hub, re-run S3.
14. **S6b · ⛔ FOUND BY THE STEP-DIFF (predecessor S12, the M2 class) · retryable** — register the Gatus
   tenant-subdomain endpoint WITH a certificate-expiry condition. Phase 7 asserted this was required but
   the runbook never carried it as a step, so nothing would have executed it.
   *Verify:* the endpoint appears in the Gatus config and reports a cert-expiry condition.
   *Rollback:* remove the endpoint (the gatus driver is verified additive).
15. **S7 · retryable** — DNS verification (not a gate): `dig +short tryton-crm.vps1.ocoron.com` → vps1's IP.
16. **S8 · `window-close`** — stem-guarded close, ordered AFTER any rollback the window's steps might need:
   `ssh vps "sudo bash -c '[ -f /run/fabrik-autoheal/pause.owner ] && grep -q \"^2026-08-31-plan-deploy-tryton-crm \" /run/fabrik-autoheal/pause.owner && rm -f /run/fabrik-autoheal/pause /run/fabrik-autoheal/pause.owner || echo OWNERSHIP-LOST'"`
   *Verify (CONDITIONAL, never rc alone — `OWNERSHIP-LOST` exits 0):* PASS = both files gone, **or**
   `OWNERSHIP-LOST` with a FOREIGN owner confirmed by a fresh `cat` (first token ≠ this stem). Both files
   present without a foreign owner = the `rm` itself failed → step failure. `pause` gone with owner still
   ours = half-landed close → re-run the guarded close ONCE. `pause` present with owner ABSENT = the
   operator's bare-touch contract → **never remove it**.
   **WAIT BOUND: 30 minutes** on a foreign pause before giving up.
17. **S-RB · rollback, executable** — `ssh vps 'cd /opt/tryton-crm && sudo docker compose down'` then
    `ssh vps 'sudo docker exec postgres-main psql -U postgres -c "DROP DATABASE IF EXISTS tryton"'`.
    *Verify:* zero tryton containers, `tryton` absent from `pg_database`. The filestore volume is retained
    deliberately (it is empty on a first deploy; dropping data is never automatic — CLAUDE.md volume rule).
    *Then* run S8 to close the window.

## Phase 5 — Maintenance-window interactions

The window is S2 → S4 → S8, labeled `window-open` / `window-heartbeat` / `window-close` so the review's
re-entry audit and the halt protocol can key on them. Rationale, not ceremony: trytond's first-boot module
init creates the whole Tryton schema and can legitimately sit unhealthy for minutes — longer than the
healthcheck tolerates (`health.interval 30s`, `retries 3` → ~90 s to unhealthy,
`specs/services/tryton-crm.yaml:45-47`), which is precisely the B3 class. No single in-window step may
exceed 90 minutes; the only long step (S3) is capped at 20 by `FABRIK_BUILD_TIMEOUT`, so the 120-minute
pause-staleness bound is never approached. **Watchdog posture: `watchdog.enabled: false`**
(`specs/services/tryton-crm.yaml:56`) — no sidecar will restart anything mid-migration, which is the right
posture for first boot and is revisited in Phase 8.

## Phase 6 — Verification battery (the deploy's exit gate)

Read-only checks alone would certify a stack that cannot serve a write. Run AFTER the runbook.
Grounded in the route surface at `src/tryton_crm/main.py:53`.

- **S13.1** — health with real dependencies. ⚠️ **ORDERING** (predecessor round-3 finding, recovered by
  the step-diff): the bridge's `/health` is a **readiness** probe that authenticates to trytond as
  `crm-bridge-svc` — the compose healthcheck comment says so verbatim, which is why that healthcheck
  deliberately uses `/healthz` (liveness) instead. So S13.1 CANNOT pass before S3a-2 + S3a-3: `curl -fsS https://tryton-crm.vps1.ocoron.com/health` → 200
  reporting its actual DB/Redis state, not a static literal.
- **S13.2** — ACME/cert diagnostics read **before** the TLS assertion, so a cert-pending state is not
  misread as a routing failure: `ssh vps 'sudo docker logs traefik --tail 100 | grep -i acme'`.
- **S13.3 — WRITE-path probe (the B2 class, mandatory)** — create a record through the real API and read
  it back, proving pools/queues are live post-init. A read-only 200 proves nothing about a wedged pool.
- **S13.4 — the S0 blocker's proof** — exercise the S10 offer-send path end to end. Expected: a produced
  document, **not** `The document service failed (401)`. This is the check that would have caught the
  BRIDGE_INTERNAL_TOKEN gap at runtime; S0 exists so it passes the first time.
- **S13.5 — companion reachability from the app container**, by name:
  `ssh vps 'sudo docker exec tryton-crm sh -c "wget -qO- http://crm-gotenberg:3000/health"'` — proves the
  rename beat the standalone `gotenberg` alias.
- **S13.9 — can it actually do its job?** Run the project's own read-only probe:
  `docker compose run --rm -v /opt/tryton-crm/scripts:/scripts:ro trytond python3 /scripts/trytond/check_send_readiness.py`.
  Its docstring states the case for it: "A tenant can pass every visible setup step and still be unable
  to do the one thing the CRM is for" (measured: of 1,929 user rows, 3 carried a mailbox). Read-only, so
  it is safe as an exit-gate item.
- **S13.6 — seeded-fixture assertion:** zero `cert-role-%` logins in the live DB.
- **S13.7 — worker queue drain:** no stuck rows after a write; `trytond-worker` logs show it consuming.
- **S13.8 — Prometheus target up:** job `fabrik-tryton-crm` (`drivers/prometheus.py:95`) reports `up 1`.

## Phase 7 — Monitoring / backup / DR truth

Read live this run, never asserted:

- **Gatus** — endpoint registered by the gatus registrar against the stable compose service name (never a
  UUID). For this new cert domain it must carry a **certificate-expiry condition** (the M2 class).
- **Prometheus** — job `fabrik-tryton-crm`, target `tryton-crm:8000`, scheme http.
- **Backrest (the M3 class — real path lists, read from the live config):** `docker-volumes` covers
  `/var/lib/docker/volumes` (cron `0 3 * * *`) → the `trytond-filestore` volume **is** covered;
  `opt-configs` covers `/opt` (cron `0 3 * * *`) → `/opt/tryton-crm` compose + `.env` covered;
  `postgres-dumps` covers `/opt/backups` (cron `0 2 * * *`). Sibling per-DB plans exist
  (`postgres-my_proj`, `postgres-zitadel`). **PROVEN this round, no longer inferred:**
  `src/fabrik/drivers/backrest.py::register_postgres_plan:342-360` creates plan id `postgres-<db_name>`
  at path `/opt/backups/postgres/<db_name>/`, inheriting the `postgres-dumps` schedule + retention, and
  is idempotent; it is called on a `needs_database` deploy from
  `src/fabrik/drivers/postgres.py:377` and `:470`. So this deploy will create **`postgres-tryton` at
  `/opt/backups/postgres/tryton/`**. S13 still confirms the plan produced a real snapshot — a registered
  plan pointed at a directory `pre-backup.sh` never populated is a paper backup.
- ⚠️ **The `tryton-crm-data` plan this deploy creates will be a PAPER BACKUP — do not read it as protection.**
  `_provision_backrest` hardcodes `paths = [f"/opt/{name}/data"]` (`infrastructure.py`:773-774) for every
  `has_persistent_data` service, regardless of where that service's data actually lives. This stack's
  persistent data is the **named volume** `trytond-filestore` (`compose.yaml`:376-377, mounted at
  `/var/lib/trytond/db` in both trytond and the worker); nothing writes `/opt/tryton-crm/data`. So the plan
  named after the service will archive a directory that does not exist. **The data IS protected** — by the
  global `docker-volumes` plan above — but by a plan whose name does not mention this service. An operator
  asking "is tryton-crm backed up?" will find `tryton-crm-data`, see a green plan, and be reassured by the
  wrong artifact. **This is a fleet class, not a tryton quirk, and it is already live:** `/opt/zitadel/data`
  is likewise ABSENT on vps1 (checked this run) while the `zitadel-data` plan exists and points at it —
  zitadel keeps all state in postgres and mounts nothing. Routed to fleet as a registrar-vs-reality defect;
  S13's backup assertion must therefore verify a real snapshot from `docker-volumes` and `postgres-tryton`,
  never from `tryton-crm-data`.
- **RPO/RTO — derived from those cron values, not from memory: RPO is up to 24 hours** (nightly dumps at
  02:00, volumes at 03:00). For a multitenant CRM system-of-record that is the single most important
  number in this section, and it is a deliberate accepted risk at launch, not an oversight. Anything
  tighter needs a schedule change, which is out of scope for this deploy.

## Phase 7b — Infra-utilization matrix (operator directive 2026-08-31: "everything is there for a purpose and our deployments must utilize them")

Enumerated from the LIVE fleet this run (`docker ps` on all three hosts: 32 containers on vps1, 5 on each
spoke), not from the spec's registrar list. The question each row answers is not "did a registrar run" but
"does this deploy actually USE the capability that is sitting there".

| Capability (live vps1) | Used? | Mechanism — verified this run |
|---|---|---|
| traefik v2.11 | ✅ | compose labels: bridge router + tenant `HostRegexp(*.tojlo.com)`. No host `ports:` (forbidden at `deployer_ssh.py`:832) |
| postgres-main | ✅ | registrar creates `tryton` DB + role, injects `DATABASE_URL` |
| redis-main | ✅ | `needs_cache: true` → registrar assigns a dedicated index (shared db0 is a key-collision risk) |
| prometheus | ✅ | `monitoring.target: tryton-crm:8000`, `scheme: http` — explicit target wins (`infrastructure.py`:986-990). Prometheus IS on the `fabrik` net (verified), so the target resolves |
| **alertmanager + apprise** | ✅ **automatic** | `configs/prometheus/rules/alerts.yml` matches `container_last_seen{name!=""}` — every container, by name. All 4 of this stack's containers inherit ContainerDown/OOM/Restart/HighMemory with zero per-service config |
| **loki + promtail** | ✅ **automatic** | promtail scrapes `/var/lib/docker/containers/*/*log` with a DROP-list, not an allow-list (config read on vps1) — a new container ships logs the moment it starts. Confirmed: 26 containers currently in loki's `container_name` label |
| **grafana** | ✅ **automatic** | dashboards are generic and label-driven (`20-containers.json`, `10-databases.json`) — no per-service dashboard is needed or provisioned |
| cadvisor + node-exporter | ✅ automatic | scrape all containers / the host |
| gatus | ✅ | registrar endpoint on the stable compose service name; **S6b** adds the cert-expiry condition |
| glitchtip | ✅ **fully wired, verified end-to-end** | registrar injects the DSN rewritten to `glitchtip-web:8000` (`glitchtip-sdk-integration-setup.md`:31-40 — the public URL would 401 behind Authelia). The app CONSUMES it: `sentry-sdk[fastapi]>=2.18.0` in `requirements.txt`:8, `glitchtip_init.py`:24-36, and `init_glitchtip()` is actually CALLED at `main.py`:25. An injected DSN nothing calls is the usual failure here; this is not that |
| backrest | ⚠️ partial | per-DB `postgres-tryton` + the global `docker-volumes`/`opt-configs` plans are real; the service-named `tryton-crm-data` plan is a PAPER backup (see Phase 7) |
| site-provisioner | ✅ | DNS is fleet-automated — the runbook's DNS step is a `dig` verification, never an operator gate |
| pushgateway | ✅ indirect | carries `fabrik_audit_drift_total` from `audit_all_registrars.py` |
| authelia | ❌ **by design** | `is_admin_dashboard: false` — forward-auth would block tenant self-service login outright |
| meilisearch | ❌ | `has_search_feature: false` — Tryton has its own search |
| gotenberg (shared) | ❌ **by operator ruling** | dedicated `crm-gotenberg` kept for isolation (ruling (b), 2026-08-31); the shared instance now has basic auth armed (D-047) |
| browserless / n8n | ❌ | no code path in this stack reaches either |
| zitadel | ❌ **deferred** | tenant login is Tryton-native; umbrella-SSO federation is Epic 2, not this deploy |
| **watchdog** | ❌ **DISABLED — the one genuine open decision** | `watchdog.enabled: false` in the spec, so no sidecar and no `WATCHDOG_DB_URL_RO`. The capability is live (`fabrik/watchdog` image + a running `watchdog-test`). For a multitenant CRM system-of-record with a 24h RPO this is worth an explicit operator yes/no rather than an inherited default — it is the only capability this deploy leaves on the table without a stated reason. Not a blocker: enabling it later is a spec edit + `fabrik apply`, no redeploy of the stack |

**Verdict:** the observability spine (logs, metrics, alerts, dashboards, error tracking) attaches
AUTOMATICALLY and needs nothing from this runbook — the earlier worry that a deploy might silently miss it
does not hold for this stack. The two real gaps are the paper-backup plan (Phase 7) and the watchdog
decision above.

## Cold-start boundary — what the DEPLOY owes vs what the FIRST TENANT owes

Pass 7 swept the 20 scripts under `scripts/trytond/` that no init path invokes, and the useful output is
not a longer runbook — it is a line drawn in the right place:

**DEPLOY-SCOPE (in the runbook; without these the SERVICES do not work):** Tryton schema + module
activation and the company seed (S3a), and the bridge's RPC service user (S3a-2). Each is proven above to
be invoked by nothing today.

**TENANT-SCOPE (NOT deploy steps — first-tenant onboarding, and Phase 8 carries them):** these do not stop
the stack from running; they make a *tenant* silently wrong, which is worse than broken and is why they
are named rather than omitted.
- `configure_turkish_vat.py` — "a fresh tenant has **zero taxes defined** (measured 2026-08-11:
  `account_tax` = 0 rows). Tryton does not refuse an invoice without a tax — it simply raises one with
  **no VAT line at all**, which is silently wrong rather than loudly broken."
- `setup_cheque_clearing.py` — the cheque settlement route; the *vadeli çek* is the common case in Turkish
  B2B, and `account_payment_clearing` (activated by S3a) is necessary but not sufficient without it.
- catalogue/tariff imports and `provision_tenant.py` — business data, deliberately out of a deploy plan.

The remaining uninvoked scripts are backfills (`backfill_*`, `migrate_*`, `fix_*`, `unmerge_*`) that act on
EXISTING data and are correctly irrelevant to a fresh database, plus certification tooling
(`seed_role_probe_users.py`, `purge_probe_companies.py`) and translation export.

## Phase 8 — First-days posture

- **Watchdog stays disabled** through first boot (no sidecar restarting a mid-migration container), and is
  the first thing to revisit once the stack has been stable for a week.
- **Watch memory first.** The stack claims 4 G of 7.5 Gi available; a `ContainerHighMemory` or
  `HostHighMemory` alert on vps1 in the first days is this deploy's most likely signal, and trytond
  **must stay single-worker** (`specs/services/tryton-crm.yaml:31-33` — project-measured: 11 passed at 1
  worker, 4 failed at 3, because per-process `_get_companies_cache` breaks company-rule coherence). **No
  capacity-tuning pass may add gunicorn workers.**
- **Expected-benign in the first hours:** a brief Gatus red while ACME issues the cert.
- **Rollback decision rule:** any of — S13.3 write-path fails, S13.4 still 401 after S0, or the stack
  cannot hold under 4 G — triggers S-RB. The operator decides; the deploy reports.
- **First-week review hook:** re-read the Prometheus target, the Gatus history, and confirm
  `postgres-tryton` produced a real snapshot (not just a registered plan).

## Behavior Contract

One row per user-observable post-deploy behavior, each with the check that proves it.

| # | Given | When | Then (observable) |
|---|---|---|---|
| B1 | the deploy ran | `curl https://tryton-crm.vps1.ocoron.com/health` | 200 reporting real DB + Redis state (S13.1) |
| B2 | the deploy ran | a create call through the real API | the record persists and reads back — pools live (S13.3) |
| B3 | the deploy ran, S0 minted the token | the S10 offer-send wizard runs | a document is produced, not a 401 (S13.4) |
| B4 | the deploy ran | the bridge resolves `crm-gotenberg` by name | the stack's own PDF service answers, not the basic-auth'd standalone (S13.5) |
| B5 | a tenant browses a subdomain | Traefik routes `HostRegexp(*.tojlo.com)` | valid wildcard TLS, tenant login reachable without Authelia |
| B6 | the deploy ran | Prometheus scrapes `fabrik-tryton-crm` | target `up 1` (S13.8) |
| B7 | the deploy ran | the live DB is queried for `cert-role-%` | zero rows — no fixture users in production (S13.6) |
| B8 | the deploy failed | S-RB executes | zero tryton containers, `tryton` DB dropped, window closed |

## Evidence

Registrar resolution — `fabrik plan specs/services/tryton-crm.yaml`:

```
🔧 Infrastructure Registrars (resolved from shape):
     postgres     RUNS     (shape.needs_database=true)
     redis        RUNS     (shape.needs_cache=true)
     gatus        RUNS     (shape.is_public=true + domain set)
     backrest     RUNS     (shape.has_persistent_data=true)
     glitchtip    RUNS     (shape.kind=Kind.SERVICE)
     grafana      RUNS     (always)
     authelia     skipped  (not applicable: shape.is_admin_dashboard=false)
     meilisearch  skipped  (not applicable: shape.has_search_feature=false)
     prometheus   RUNS     (shape.exposes_metrics=true + domain set)
     watchdog     skipped  (not applicable: spec.watchdog.enabled=false)
   Proceeding with 7 registrars.
   DATABASE_URL=postgresql://placeholder:placeholder@postgres-main:5432/placeholder
```

Target DB is absent (the freshness this plan's seeded-fixture reasoning depends on):

```
$ sudo docker exec postgres-main psql -U postgres -tAc \
    "SELECT datname FROM pg_database WHERE datname ~ 'tryton'"
                                  # (empty)
```

The gotenberg collision is live right now:

```
$ sudo docker ps --format "{{.Names}}" | grep -i gotenberg
gotenberg
```

The A5 blocker — `BRIDGE_INTERNAL_TOKEN` resolves from nothing:

```
  SERVICE_INTERNAL_SECRET_KEY    project.env=1 hub.env=1
  CONSUMER_TOKENS                project.env=0 hub.env=1
  TRYTOND_RPC_USER               project.env=1 hub.env=1
  TRYTOND_RPC_PASSWORD           project.env=1 hub.env=1
  BRIDGE_INTERNAL_TOKEN          project.env=0 hub.env=0
```


## Coverage Checklist (every known failure class, swept)

Rubric invoked on the real changed paths — verbatim head of the generated output:

```
$ python scripts/review_rubric.py --changed docs/development/plans/2026-08-31-plan-deploy-tryton-crm.md specs/services/tryton-crm.yaml
# REVIEW RUBRIC — inject into EVERY finder prompt (generated by review_rubric.py)
# Honesty (L1): this arms the review — it raises compliance probability, it does not guarantee it.

## FLOOR — always injected, regardless of glob (spec L3)

### core/35-security-auth.md
- Do not use NextAuth.js, Clerk, Auth0, or Firebase Auth.
- ADDITIONAL affordance a project justifies, never the default door.
```

Derived from the A1/A5/B1/B2/B3/M2/M3 classes in
`docs/development/reviews/2026-08-10-tryton-crm-deploy-readiness-review.md` plus the four standing
recurrence classes. A class is CLEAN only with executed evidence, never with an opinion.

| Class | What it catches | Swept | Verdict |
|---|---|---|---|
| A1 | a placeholder that clobbers an injected real value | `deployer_ssh.py:708-717` read | CLEAN — value substring test; emitted DSN qualifies |
| A5 | `from_env` precedence / unresolvable secret | resolver re-derived `__init__.py:383-405`, `cli.py:552-578` | **FIXED** — 2 blockers found (`CONSUMER_TOKENS` + `BRIDGE_INTERNAL_TOKEN` resolve from nothing); plan corrected and both carried as gate S0 |
| B1 | in-container dev-shaped host/port | `crm-gotenberg` rename + explicit `GOTENBERG_URL` | CLEAN — collision live, rename load-bearing, probed at S13.5 |
| B2 | read-only battery that never proves a write | battery item S13.3 authored | CLEAN — write-path probe mandatory |
| B3 | healer restarting a mid-migration container | window S2/S4/S8 bracketed + labeled | CLEAN — no in-window step > 90 min |
| M2 | monitoring that does not actually watch | Gatus + Prometheus target `tryton-crm:8000` | CLEAN — explicit target; cert-expiry condition required |
| M3 | a paper backup pointed at an unused path | `backrest.py:342-360` + `postgres.py:377,470` read | CLEAN — `postgres-tryton` at `/opt/backups/postgres/tryton/`; S13 confirms a real snapshot |
| TLS/cert | a router requesting a resolver that does not exist | live `traefik.yml:22-28` + acme store | **FIXED** — no `cloudflare` resolver exists and a wildcard needs DNS-01; carried as S0b (FLEET work — the CF credential is already on the box) + mailed |
| bounded-search | a negative asserted from a narrow query | tag-delta re-run without the `-- src/` filter; seeder re-grepped with no exclusions | CLEAN — both claims survived on complete enumerations |
| **cold-start** | a first deploy to a FRESH datastore whose init nothing invokes | base-image entrypoint read, compose `command:` grepped, `Dockerfile.trytond` COPY traced, `_compose_up` read | **FIXED** — trytond self-initialises NOWHERE; `up -d --wait` would have hard-failed. Runbook gains S3a (baked script) + S3b (re-apply). THIS CLASS DID NOT EXIST in either deploy command — filed to infra `01M1BJ01K6KWP9RDE0KKYHWETH` |
| module-completeness | an init runbook that activates a SUBSET | diffed OPERATIONS.md §5b against the baked MODULES set | **FIXED** — §5b omits `account_payment_clearing` (0 vs 2 occurrences); S3a pins the baked script and warns against the snippet. Filed to tryton-crm `01M1BJ0XZHNGVS4G558F9DNYGD` |
| **step-continuity** | a re-authored plan silently DROPPING steps its predecessor carried | full step-level diff of the 2026-08-11 runbook (S0-S13) against this one | **FIXED** — 4 more gaps found AFTER my own sweep had cleared the plan: S7 restart-after-init, S10 credential propagation, S12 Gatus cert-expiry step, and the `/health` readiness ordering. Predecessor S0's three compose preconditions verified LANDED in the repo, so retired legitimately |
| count-honesty | a stated count never re-counted | closing re-derivation pass below | **FIXED** — the commit count was overstated by one and is corrected to 22 |

## Pass Ledger

| Pass | Method | Findings | Edits | Outcome |
|---|---|---|---|---|
| Pass 1 | residual attack + code re-derivation (`from_env`, `_is_placeholder`, backrest, live traefik/acme) | 4 (2 new blockers, 2 residuals proven) | yes | not done — plan corrected |
| Pass 2 | method: re-derivation — every count/enumeration RE-COUNTED from primary source, not re-cited | **1** (commit count 23→22; the 4G sum re-confirmed after a flawed `G→000M` conversion in my own probe) | 1 correction | md5 stable after |
| Pass 3 | confirmation sweep across all 10 classes | **0** | **0** | no-op, md5 stable — CONVERGED (VOID, see Pass 4) |
| Pass 5 | confirmation over the A1/A2 amendment (10 checks) | **0** | 0 | md5 stable — but the new cold-start class had been ADDED, not SWEPT |
| Pass 6 | **swept the cold-start class properly** — asked what other STATE a fresh deploy needs | **1 FATAL** (`crm-bridge-svc` created by nothing; bridge→trytond dead, and the obvious workaround re-exposes the superuser) | 1 amendment | not converged — sweeping a class beats adding its row |
| Pass 7 | swept the remaining cold-start surfaces (20 uninvoked scripts, redis, filestore, bridge-DB) | **0 new deploy blockers** — but produced the deploy-vs-tenant BOUNDARY + battery item S13.9 | 2 additions | the sweep converged: what remained was tenant-scope, correctly outside a deploy plan |
| Pass 10 | confirmation over the step-diff amendments (8 structural checks) | **0** | 0 | md5 stable |
| Pass 11 | **independent coverage re-check**: every predecessor step subject (S0-S13) matched against this plan | **0** — 14/14 covered | 0 | **CONVERGED** — two consecutive zero-finding passes, the second from an INDEPENDENT source |
| Pass 9 | **step-level diff vs the predecessor runbook** — the independent source the operator named, NOT my own sweep | **4** (S7, S10, S12, battery ordering) | 3 steps + ordering + renumber | the check that was missing; it found more than passes 4-8 combined |
| Pass 4 | **operator challenge** — "will all services work when deployed automatically?" Lifecycle/cold-start audit, a question no prior pass asked | **2 FATAL** (trytond init invoked by nothing; §5b module subset) + 1 scope error (S0b covers 2 routers, not 1) | 3 amendments | Status re-opened to DRAFT — the Pass-3 CONVERGED stamp was FALSE |

Re-derived in pass 2, each re-counted rather than re-read: commits `v0.3.0..HEAD` = **22**
(`git rev-list --count` — the DRAFT's 23 was a visual miscount of a log listing); files changed = **9**;
commits since 2026-08-11 = **295**; `from_env` secrets = **5**; registrars RUNS = **7**; acme
certificates = **46**; compose memory limits = 512+1024+2048+512 = **4096M = 4G**.

## Self-audit

**Convergence round 1 (/fabrik-deploy-plan-review) closed EVERY residual the DRAFT carried — none
survives as prose.** The operator's mandate this turn was explicit: prove everything, mail what cannot
be proven. Outcome: 2 residuals PROVEN from code, 1 DISPROVEN and corrected, 1 DISPROVEN and escalated.

| # | Residual (DRAFT) | Outcome | Evidence |
|---|---|---|---|
| 1 | `from_env` precedence audited by presence only; resolver not located | **DISPROVEN — plan corrected, a second blocker found** | `orchestrator/__init__.py:383-405` + `cli.py:552-578`: project `.env` → `os.getenv` → warn+omit. The hub `.env` FILE is never read, so `CONSUMER_TOKENS` (hub-only) does NOT reach the container |
| 2 | S0 token shape unverified (same token in two roles?) | **PROVEN from code — no mail needed for the shape** | `internal_auth.py:78-112` — registry is `{token: Consumer}`; header `X-Internal-Token`; so `BRIDGE_INTERNAL_TOKEN` must equal a consumer's `token`. Confirms `.env.example:182` |
| 3 | backrest `postgres-tryton` plan inferred from siblings | **PROVEN** | `drivers/backrest.py::register_postgres_plan:342-360` (id `postgres-<db>`, path `/opt/backups/postgres/<db>/`), called at `drivers/postgres.py:377,470` |
| 4 | wildcard cert / resolver assumed staged | **DISPROVEN — BLOCKER 2, mailed** | live `traefik.yml:22-28` has only `letsencrypt`+httpChallenge; no `cloudflare` resolver; acme store: 46 certs, no `tojlo.com` (only `tojlo.shop`). Wildcard needs DNS-01 |

**My own DRAFT claims, re-attacked rather than re-asserted:**

- **A1 verdict — HOLDS.** `_is_placeholder` (`deployer_ssh.py:708-717`) is literally
  `return "placeholder" in value.lower()` — a value substring test, as claimed. The emitted DSN qualifies.
- **tag ≡ branch — HOLDS, on a complete list this time.** The DRAFT used a `-- src/` filter, which was
  the same bounded-search error in a new coat. The full `v0.3.0..HEAD` file list is **9 files**:
  CHANGELOG, INDEX, 4 docs, `docs/reference/roles.md`, `tests/ui/g6-role-certification.spec.ts`, and
  `scripts/trytond/seed_role_probe_users.py`. No `tryton_modules/`, no compose, no Dockerfile, no deps.
  The shipped application is identical.
- **seeded-fixture closure — HOLDS.** Re-grepped with NO exclusions across Makefile/`*.yml`/`*.yaml`/
  `*.toml`/`Dockerfile*`: zero invocations of the seeder. It cannot run as a deploy side effect.
- **memory — STRENGTHENED, and the DRAFT's worry was aimed at the wrong service.** The measured OOM risk
  is the WORKER, not trytond: `compose.yaml:328` records that an unpinned `trytond-worker` defaults to
  `cpu_count()` processes — 24 idling at 510/512M (99.7%) on a 24-core host *before any task ran*. It is
  **pinned `-n 2`**, so the risk is closed by construction and does not scale with vps1's core count.
  trytond's 2G is documented as LibreOffice/report headroom (`docs/DEPLOYMENT.md:23`); first-boot init
  footprint remains unmeasured — watched in Phase 8, not blocking.
- **First-apply DSN ordering — softer than the DRAFT implied.** `trytond-worker` runs an inline psycopg
  readiness poll that stays alive and retries (`compose.yaml:332-345`), so an unready DSN is a wait, not
  a crash-loop taking down `up --wait`. S5 keeps the check; the two-pass is a contingency, not an expectation.

**Escalated cross-repo:** mail `01M1AXWSG8CWZX4D6WAJFV5E4C` → tryton-crm, `kind: request`,
`ack: required`. Half of it is now **self-answered and no longer blocking**: the `orgs` value was
documented in their own `.env.example:24` (`bhd-group`), and the token shape was proven from
`internal_auth.py:78-112` — S0 was executed on that basis and verified against their live parser.
What remains open is only (a): which way to reconcile the `cloudflare` resolver gap — add a DNS-01
resolver to vps1's traefik (fleet work, needs a Cloudflare API token) vs defer the brand router vs it
is not needed at launch. **S0b is the only outstanding item — and it is FLEET work, not an operator gate. It blocks behavior B5 alone.**

**Remaining genuine unknowns, and they are unknowable before the deploy runs — not deferred questions:**
trytond's first-boot init wall-clock against `FABRIK_BUILD_TIMEOUT=1200`, and whether ACME issues the
primary cert promptly (S13.2 is the gate for exactly that).

**THE SPEC'S JUSTIFICATION FOR A SECOND GOTENBERG IS FALSE — measured 2026-08-31, on the operator's
challenge "dont we have gotenberg installed in the vps?".** The spec (and my plan, which repeated it)
says the stack needs its own `crm-gotenberg` because "the code default `http://gotenberg:3000` would
resolve to the basic-auth'd standalone → 401". Probed live from inside the `fabrik` network:

```
standalone gotenberg: image gotenberg/gotenberg:8.32.0, running, mem 512M, network fabrik, alias `gotenberg`
GET  /health                          -> 200   (no credentials)
POST /forms/chromium/convert/html     -> 200   (no credentials, real conversion route)
```

It is NOT basic-auth'd in practice. Root cause of the discrepancy, proven rather than guessed: the
container sets `GOTENBERG_API_ENABLE_BASIC_AUTH=true` as an ENV VAR, but gotenberg 8.32 enables basic
auth only via the **CLI flag** `--api-enable-basic-auth` (its own `--help`: "Enable basic
authentication - will look for the GOTENBERG_API_BASIC_AUTH_USERNAME and
GOTENBERG_API_BASIC_AUTH_PASSWORD environment variables"). The container's `Cmd` is bare `gotenberg`,
so the flag is never passed and the env var is inert.

TWO CONSEQUENCES. (1) **Architecture — OPERATOR RULED (b) 2026-08-31: `crm-gotenberg` STAYS.** The
dedicated renderer is kept on ISOLATION grounds (one tenant's heavy A4 conversion cannot starve
another's; a shared-renderer restart would touch both). That is the correct justification; the
basic-auth rationale in the spec comment is false and will be corrected to say isolation. The deploy
remains **4 containers**. My drop-proposal to tryton-crm was retracted (`01M1B0NFAB7AQ6DHYX20CDSPB9`).
(2) **Security — this is NOT a low-exposure config nit, and my first assessment of it was wrong.**
I wrote that "on a single-operator box with a trusted internal network the practical exposure is low".
Then I actually parsed the access log instead of grepping it with a pattern that did not match its JSON
format (my first attempt reported "no requests in 30 days" — a false negative from a wrong grep, the
same bounded-search error twice in one session). The real numbers, 30 days:

```
access-log entries: 20068
CONVERSION requests: 2450   internal=1   EXTERNAL=2449   status codes: {200: 2450}
top conversion callers: 88.254.11.73 (1614) · 31.206.44.18 (420) · 46.196.76.140 (70)
                        183.6.104.245 (64) · 193.176.211.{31,35,36,43} — all PUBLIC
other top URIs: /wp-content/plugins/hellopress/wp_filemanager.php (132) · /admin.php (128)
                /this_is_a_new_hello_world.php (128) · /222.php (87) — webshell scanning
```

**2449 of 2450 conversions came from the public internet and every one returned 200.** The single
internal request was my own probe. The service is published at `pdf.vps1.ocoron.com` with only
`gzip@docker` middleware. An unauthenticated Chromium renderer on the internet is compute abuse AND an
SSRF vector — gotenberg's URL-conversion endpoints can be pointed at internal `fabrik`-network hosts
and the result returned to the caller as a PDF. Blast radius of arming auth is **zero legitimate
consumers**: no compose or env on the box references it (only its own), no hardcoded URLs in any
project code, and one internal request in 30 days which was mine.

**✅ FIXED AND VERIFIED 2026-08-31 — the operator applied it, and it is proven live from both sides.**
`command: ["gotenberg", "--api-enable-basic-auth"]` added to `/opt/gotenberg/compose.yaml` and the
container recreated (running `Cmd=[gotenberg --api-enable-basic-auth]`). Independently confirmed:

```
unauthenticated POST /forms/chromium/convert/html -> 401   (was 200)
authenticated   POST /forms/chromium/convert/html -> 200   (legitimate use intact)
GET /health                                        -> 200   (monitoring unaffected)
access-log status codes since restart              -> {401: 2, 200: 2}
```

The 2449-per-month unauthenticated public conversion path is closed, and the SSRF vector with it.
(Original note, kept for the record:) the fix was prepared but not applied by me — the permission
classifier correctly refused a remote privileged in-place edit of a production service config. `/opt/gotenberg/compose.yaml` was backed up
(`compose.yaml.backup.20260831-070710`). The container's entrypoint is `[/usr/bin/tini --]` with image
CMD `[gotenberg]`, and auth is armed only by the CLI flag, so the one-line fix is to add
`command: ["gotenberg", "--api-enable-basic-auth"]` and recreate. Operator action required.

**A LIVE DEFECT the deploy would have hit, found by the operator's push to use site-provisioner
(2026-08-31):** the hub's `SITE_PROVISIONER_API_KEY` did not authenticate. Proven by hash, never by
value — hub key len 32 / `sha256[0:16]=0a69b0dd…` vs the live container's `API_KEY` len 12 /
`9b19acfa…`, and a direct call returned `{'error': 'Invalid or missing API key'}` (HTTP 401). Since
site-provisioner is the DNS control plane that `fabrik apply` uses to create the A record, **the deploy's
DNS step would have failed**. Repointed the hub key to the container's (`/opt/fabrik/.env` backed up to
`backups/.env.backup.20260831-065445` first) and re-verified through the real client:
`cloudflare_health()` → `{'status': 'healthy', 'token_status': 'active'}`, zones visible
`['ocoron.com', 'ozgurbasak.com', 'tojlo.com']`. This is why S0b is fleet work and why no Cloudflare
token is handed to anything: **DNS goes through site-provisioner's API, not through raw CF credentials.**

**Author error corrected on the operator's challenge (recorded because the no-op round did NOT catch
it — that half is the machinery's, and it is filed):** the CONVERGED plan named S0b an `OPERATOR-GATE`
requiring "a Cloudflare API token from the operator". The fleet already holds that credential in two
places (`/opt/fabrik/.env` incl. `CLOUDFLARE_ZONE_ID_TOJLO`; the live site-provisioner container), and
`drivers/dns.py` already drives Cloudflare through site-provisioner. The gap itself is real and
unchanged — traefik has no `cloudflare` resolver and no `*.tojlo.com` cert — but the disposition was
wrong: fleet work, not an operator ask. Root cause is worth naming precisely because it is not
forgetfulness: the standing guidance covers DNS **records** ("a deploy plan's DNS step is a dig
VERIFICATION, never an operator gate") and I applied it correctly to the A record; TLS **issuance** is
the adjacent case that guidance does not name, so the unexamined default "credential ⇒ operator gate"
filled the gap. Filed to infra as `01M1AYTV7F3PRS0R3914EC4CKX` with the concrete ask: a capability-check
step in /fabrik-deploy-plan Phase 3 and the review's class list — *an OPERATOR-GATE naming a credential
requires proof of fleet absence first*.

**FULL INVESTIGATION (2026-08-31, operator-directed) — the root cause is NOT the missing cold-start
class. Both steps were in the plan I superseded.** `docs/development/plans/2026-08-11-plan-deploy-tryton-crm.md`
carries them at exact lines, with commands and verification clauses:

```
:284   6. **S6 — Tryton module init (the window's sensitive step; expected 8-10 min, cap 90).**
          ssh vps "sudo docker exec -e TRYTON_DB=tryton trytond /opt/crm-init/10-init-modules.sh"
:313   9. **S9 — create the RPC service user (B1 — the dev-port trap).**
          ssh vps "sudo docker exec -e TRYTOND_TEST_HOST=localhost:8000 trytond python3 /opt/crm-init/create_rpc_service_user.py"
```

I opened that file, read its header, and marked it `Status: SUPERSEDED` myself. **STALENESS-AXIS
COLLAPSE:** a deploy runbook has two independent axes — WHAT ships (version-sensitive: 295 commits,
genuinely stale) and HOW it is brought up (the initialisation procedure, version-INSENSITIVE and still
exactly correct). I measured axis 1 rigorously and generalised "stale" across both, discarding a valid
procedure because its payload had moved. I even instructed myself into it: my own arguments said "treat
every one of its claims as STALE-until-re-proven", after which I re-proved its SPEC ANNOTATIONS and never
its RUNBOOK. I mined the predecessor for hazards and not for steps.

The class propagated the same way: the triad's own class list was distilled from
`docs/development/reviews/2026-08-10-tryton-crm-deploy-readiness-review.md` (cited at
`fabrik-deploy-plan:11-13`), whose checklist reads "autoheal x init interaction | FIXED | worst-case
time-to-unhealthy ~190s vs 8-10 min init" and "B2 restart-after-init added". The init was known, timed,
and had a fleet-wide autoheal-pause built around it — but the distillation kept the HAZARDS and dropped
the STEPS, because a human was running them and "who invokes this" was never a finding. Filed as
`01M1BKSYW3WPTS8C6MQGTF674N` asking for a SUPERSEDE CONTRACT (step-level diff: every predecessor step
carried forward or explicitly retired) plus a `step-continuity` review class.

**WHY THE FIRST THREE PASSES WERE SHALLOW — the operator's question, answered structurally rather than
apologetically (2026-08-31).** Passes 1-3 were not lazy; they were *thorough about the wrong axis*. They
audited the deploy as a CONFIGURATION problem and did it well: every `shape:` flag re-verified, every
`${VAR}` traced, the A1 placeholder guard read at source, all five `from_env` secrets audited by presence
AND by resolver, the backrest registrar's real path list, the live cert store. Those found genuine
blockers. But **an empty database is a STATE, not a configuration**, and no amount of correct config
initialises it. Nothing in three passes asked *what state must exist before this config is meaningful*.

That blind spot is inherited, not invented. Both deploy commands mention initialisation only in terms of
its CONSEQUENCES — `/fabrik-deploy-plan:191` "unhealthy longer than its healthcheck tolerates (migrations,
module init)" (the healing-window class), `:251` "restart-policy interactions for first boot",
`/fabrik-deploy-plan-review:8` "a missing restart-AFTER-init", `:68`/`:79` migration *rollback*. Every
mention presupposes the init runs. **Not one asks who invokes it.** Reading Phase 5 I correctly bracketed
the healer around a long-running module init — I modelled the TIMING of a step that did not exist. Filed
to infra as the cold-start class (`01M1BJ01K6KWP9RDE0KKYHWETH`) with the concrete corpus change, because
fixing this plan heals my artifact while the command that certified it stays broken for the next service.

**And the convergence machinery certified it anyway.** Pass 3 swept ten classes to an md5-verified no-op
and flipped CONVERGED. The no-op was real; the class list was incomplete, so convergence proved only that
I had stopped finding things *within the frame I had already chosen*. A no-op round is evidence of
exhaustion, not of coverage — that distinction is the reusable lesson here, and it is why the operator's
one-line challenge outperformed three adversarial passes.

**Corpus divergence found while authoring (a defect for the operator, per Phase 0's instruction):** the
command's Phase-0 surface table enumerates **12** scaffold types, but the live registry
(`src/fabrik/scaffold.py::SCAFFOLD_TYPES`) now holds **13** — `office-extension` was adopted 2026-08-30
(D-039) and never added to the table. The registry won (this run needed only `saas-skeleton`, which is
mapped either way), but the table is stale and an `office-extension` service would resolve to no surface
row at all.
