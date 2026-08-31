# Deployment plan — tryton-crm (BHD CRM stack: bridge + trytond + worker + crm-gotenberg)

Status: DRAFT
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
**branch tip f4d80a2**, not the tag `v0.3.0` (a4e7c52). Measured this run, that gap is **23 commits and
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

The stack's declared ceiling is **4 G** — `tryton-crm` 512M + `trytond` 2G + `trytond-worker` 1G +
`crm-gotenberg` 512M (`compose.yaml:60,118,246,298`) — against 7.5 Gi available. It fits with ~3.5 Gi
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

| `from_env` secret | project `.env` | hub `.env` | verdict |
|---|---|---|---|
| `SERVICE_INTERNAL_SECRET_KEY` | present | present | resolves |
| `TRYTOND_RPC_USER` | present | present | resolves |
| `TRYTOND_RPC_PASSWORD` | present | present | resolves |
| `CONSUMER_TOKENS` | **absent** | present | resolves only if the hub source is reachable — **S0 verifies** |
| `BRIDGE_INTERNAL_TOKEN` | **absent** | **absent** | ⛔ **BLOCKER — see below** |

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

- **DNS** — `tryton-crm.vps1.ocoron.com` plus the tenant wildcard the compose routes via
  `HostRegexp(*.tojlo.com)` with `certresolver=cloudflare`. DNS is fleet-automated by site-provisioner
  (`fabrik apply` auto-creates the A record), so the runbook's DNS step is a `dig` **verification**, never
  an operator gate.
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

1. **S0 · `OPERATOR-GATE` · verify: in-session · NOT retryable without operator action** — mint the
   bridge consumer token. Add a consumer with `write` scope for the tenant org to `CONSUMER_TOKENS`, and
   set that same token as `BRIDGE_INTERNAL_TOKEN` in `/opt/tryton-crm/.env` on the **hub** (the surface
   `from_env` reads first). Also confirm `CONSUMER_TOKENS` resolves from the same file.
   *Verify:* `grep -c '^BRIDGE_INTERNAL_TOKEN=.\+' /opt/tryton-crm/.env` → `1`, and
   `grep -c '^CONSUMER_TOKENS=.\+' /opt/tryton-crm/.env` → `1`. Values never echoed.
   *Rollback:* remove the added lines; nothing has deployed yet.
   **This gate is why the plan exists — without it S13.4 fails with a misleading 401.**
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
   safe — the injected real value is protected.
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
  (`postgres-my_proj`, `postgres-zitadel`), so the registrar is expected to add `postgres-tryton` —
  **S13 must confirm it actually appeared**; a per-service plan pointed at an unused directory is a paper
  backup.
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

## Self-audit

**Verified live this run:** the 7-registrar resolution; the DATABASE_URL placeholder value and therefore
the A1 merge-guard behaviour; vps1 headroom and the 4 G stack ceiling; the empty target DB; the live
`gotenberg` name collision; the `fabrik` network; Backrest's real path lists and cron values; all five
`from_env` sources by presence; the service gate (53 passed / 0 failed); the tag-vs-branch delta and that
it touches no `src/`.

**Assumed / not yet provable until the deploy runs:** that the backrest registrar will create a
`postgres-tryton` plan (inferred from the sibling `postgres-my_proj` / `postgres-zitadel` plans — S13
must confirm, not assume); that trytond's first-boot init completes inside `FABRIK_BUILD_TIMEOUT=1200`;
that ACME issues the wildcard promptly.

**Residuals the review must attack:**
1. **The S0 blocker is the whole ballgame** — is minting a `CONSUMER_TOKENS` consumer and reusing its
   token as `BRIDGE_INTERNAL_TOKEN` actually the right shape, or should it be a distinct credential?
   `.env.example:182` says to mint a consumer with `write` scope; I have not verified the bridge accepts
   the *same* token in both roles.
2. `CONSUMER_TOKENS` lives only in the hub `.env`. I audited by **presence**, not by tracing the resolver
   — I could not locate the `from_env` resolution site in `deployer_ssh.py` (grep found only
   `spec_generator.py` and `validator.py`). The precedence claim in Phase 2 is therefore inherited from
   the A5 class definition, **not** re-derived this run. The review should read the real resolver and
   confirm a hub-`.env`-only value actually reaches the container.
3. RPO of 24 h on a system-of-record — accepted here, but it deserves an explicit operator acknowledgement
   rather than passing silently in a plan.
4. Whether the wildcard `*.tojlo.com` cert already exists or will be issued on first router load — Phase 3
   assumes the resolver is staged; S13.2 is the check.

**Corpus divergence found while authoring (a defect for the operator, per Phase 0's instruction):** the
command's Phase-0 surface table enumerates **12** scaffold types, but the live registry
(`src/fabrik/scaffold.py::SCAFFOLD_TYPES`) now holds **13** — `office-extension` was adopted 2026-08-30
(D-039) and never added to the table. The registry won (this run needed only `saas-skeleton`, which is
mapped either way), but the table is stale and an `office-extension` service would resolve to no surface
row at all.
