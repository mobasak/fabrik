# Deployment plan — tryton-crm (BHD CRM stack: bridge + trytond + worker + crm-gotenberg)

Status: CONVERGED
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
The compose declares a second router `tryton-crm-brand` requesting
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
2. **S1 · retryable** — pre-flight re-proof: service gate green, branch pushed, target DB still absent,
   `fabrik` network present.
   *Verify:* the four commands in `## Evidence` reproduce their outputs.
   *Rollback:* n/a (read-only).
3. **S2 · `window-open` · retryable once** — open the autoheal window before anything can leave a
   container legitimately unhealthy (trytond module init runs minutes; autoheal's worst case to unhealthy
   is shorter — the B3 class).
   `ssh vps "sudo bash -c 'mkdir -p /run/fabrik-autoheal && printf \"%s %s\n\" 2026-08-31-plan-deploy-tryton-crm 2026-08-31T03:14:21Z > /run/fabrik-autoheal/pause.owner && touch /run/fabrik-autoheal/pause'"`
   (owner FIRST, pause second — deliberate.)
   *Verify:* both files exist and `pause.owner` begins with this plan's stem; then wait for a `PAUSED`
   line newer than the touch in the healer's log, **bounded at 5 minutes** — no `PAUSED` within 5 min
   means the healer cron is absent or wedged → halt.
   *Rollback:* the S8 guarded close.
4. **S3 · retryable · ~5-15 min** — `FABRIK_BUILD_TIMEOUT=1200 fabrik apply specs/services/tryton-crm.yaml`
   from `/opt/fabrik`. Builds `Dockerfile.trytond`, creates the `tryton` DB + role, injects `DATABASE_URL`
   and the Redis index, writes `.env`, brings the stack up, runs the 7 registrars.
   *Verify:* command reports deployment complete; `ssh vps 'sudo docker ps --format "{{.Names}}" | grep -E "^(tryton-crm|trytond|trytond-worker|crm-gotenberg)$"'` → 4 lines.
   *Rollback:* S-RB below.
5. **S4 · `window-heartbeat`** — refresh the pause with the stem-guarded form (both files must exist, or
   `OWNERSHIP-LOST` → stop and disambiguate). No single in-window step may exceed 90 minutes; S3 is the
   only long one and is bounded by `FABRIK_BUILD_TIMEOUT=1200` (20 min).
6. **S5 · retryable** — DSN ordering check. `.env` is written before `DATABASE_URL` is injected on a first
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
7. **S6 · retryable** — confirm the injected secrets are non-empty **without printing them**:
   `ssh vps 'sudo docker exec trytond sh -c "test -n \"\$BRIDGE_INTERNAL_TOKEN\" && echo SET || echo EMPTY"'` → `SET`.
   *Rollback:* fix on the hub, re-run S3.
8. **S7 · retryable** — DNS verification (not a gate): `dig +short tryton-crm.vps1.ocoron.com` → vps1's IP.
9. **S8 · `window-close`** — stem-guarded close, ordered AFTER any rollback the window's steps might need:
   `ssh vps "sudo bash -c '[ -f /run/fabrik-autoheal/pause.owner ] && grep -q \"^2026-08-31-plan-deploy-tryton-crm \" /run/fabrik-autoheal/pause.owner && rm -f /run/fabrik-autoheal/pause /run/fabrik-autoheal/pause.owner || echo OWNERSHIP-LOST'"`
   *Verify (CONDITIONAL, never rc alone — `OWNERSHIP-LOST` exits 0):* PASS = both files gone, **or**
   `OWNERSHIP-LOST` with a FOREIGN owner confirmed by a fresh `cat` (first token ≠ this stem). Both files
   present without a foreign owner = the `rm` itself failed → step failure. `pause` gone with owner still
   ours = half-landed close → re-run the guarded close ONCE. `pause` present with owner ABSENT = the
   operator's bare-touch contract → **never remove it**.
   **WAIT BOUND: 30 minutes** on a foreign pause before giving up.
10. **S-RB · rollback, executable** — `ssh vps 'cd /opt/tryton-crm && sudo docker compose down'` then
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

- **S13.1** — health with real dependencies: `curl -fsS https://tryton-crm.vps1.ocoron.com/health` → 200
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
- **RPO/RTO — derived from those cron values, not from memory: RPO is up to 24 hours** (nightly dumps at
  02:00, volumes at 03:00). For a multitenant CRM system-of-record that is the single most important
  number in this section, and it is a deliberate accepted risk at launch, not an oversight. Anything
  tighter needs a schedule change, which is out of scope for this deploy.

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
| count-honesty | a stated count never re-counted | closing re-derivation pass below | **FIXED** — the commit count was overstated by one and is corrected to 22 |

## Pass Ledger

| Pass | Method | Findings | Edits | Outcome |
|---|---|---|---|---|
| Pass 1 | residual attack + code re-derivation (`from_env`, `_is_placeholder`, backrest, live traefik/acme) | 4 (2 new blockers, 2 residuals proven) | yes | not done — plan corrected |
| Pass 2 | method: re-derivation — every count/enumeration RE-COUNTED from primary source, not re-cited | **1** (commit count 23→22; the 4G sum re-confirmed after a flawed `G→000M` conversion in my own probe) | 1 correction | md5 stable after |
| Pass 3 | confirmation sweep across all 10 classes | **0** | **0** | **CONVERGED — no-op, md5 stable** |

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

**FIX PREPARED BUT NOT APPLIED — blocked by the permission classifier, which correctly refused a remote
privileged in-place edit of a production service config.** `/opt/gotenberg/compose.yaml` was backed up
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

**Corpus divergence found while authoring (a defect for the operator, per Phase 0's instruction):** the
command's Phase-0 surface table enumerates **12** scaffold types, but the live registry
(`src/fabrik/scaffold.py::SCAFFOLD_TYPES`) now holds **13** — `office-extension` was adopted 2026-08-30
(D-039) and never added to the table. The registry won (this run needed only `saas-skeleton`, which is
mapped either way), but the table is stale and an `office-extension` service would resolve to no surface
row at all.
