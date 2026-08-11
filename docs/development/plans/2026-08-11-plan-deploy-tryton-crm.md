# Deployment plan — tryton-crm (BHD CRM stack: bridge + trytond + worker + gotenberg)

Status: DRAFT
Service: tryton-crm · Surface: **vps** · Target: **vps1** · Date: 2026-08-11
Authored by: /fabrik-deploy-plan (first live run of the triad) · Plan stem: `2026-08-11-plan-deploy-tryton-crm`

**Release readiness — freshly proven in the SERVICE's repo this run:**

```
$ cd /opt/tryton-crm && .venv/bin/python scripts/final_gate.py --check --json
{"status": "success", "tier": 2, "passed": 45, "failed": 0}
$ git -C /opt/tryton-crm status --short        # (empty — clean)
$ git -C /opt/tryton-crm log origin/mobasak/tryton-crm..HEAD --oneline   # (empty — pushed)
```

The service `CHANGELOG.md [Unreleased]` describes what ships (first deploy of the full stack:
tenant branding, role bundles, bridge tenant-resolution fixes — `/opt/tryton-crm/CHANGELOG.md:10-257`;
the newest entry is a design spec explicitly marked "Nothing here ships into the pending BHD deploy").

## Context Ledger

- `specs/services/tryton-crm.yaml` (stack spec, re-specced 2026-08-09/10 with review findings A1/A4/A5 baked in)
- `/opt/tryton-crm/compose.yaml` (3+1 services; the A1 derivation at :144), `Dockerfile.trytond:45,49` (init scripts baked at `/opt/crm-init`)
- `docs/development/reviews/2026-08-10-tryton-crm-deploy-readiness-review.md` (the class definitions + runbook v2 this plan formalizes)
- `/opt/tryton-crm/scripts/trytond/create_rpc_service_user.py` (:30,51 — password GENERATED + printed once; :167 in-container prints, never writes)
- Live vps1 probes this run: `free -h`, `/opt/traefik/*.staged` + diff, `/run/fabrik-autoheal/`, Backrest plan paths, DNS digs
- `.venv/bin/fabrik plan specs/services/tryton-crm.yaml` (registrar preview, embedded below)
- `scripts/vps-autoheal.sh` (healer contract: pause file, 7200s staleness, PAUSED log line)

## File Scope (owned paths — what the DEPLOY will mutate)

- Remote vps1: `/opt/tryton-crm/**` (apply target), `/opt/traefik/{cf.env,traefik.yml,compose.yaml}` (S2 activation), `/run/fabrik-autoheal/{pause,pause.owner}` (window), Gatus config (S12)
- Hub: `/opt/fabrik/.env` (TRYTOND_RPC_PASSWORD, backed up first), `/opt/tryton-crm/.env` (same key — the from_env-winning copy, backed up first)
- This plan file (deploy ledger rows) · `docs/development/reviews/2026-08-11-plan-deploy-tryton-crm-review.md` (the review's artifact)

## Phase 1 — Target decision with evidence

Target `vps1` (`target_vps` default; spec `domain: tryton-crm.vps1.ocoron.com` — `specs/services/tryton-crm.yaml:4`).
Defense: the stack is **shared-infra-heavy** — postgres-main (`depends.postgres: tryton`), redis-main
(`shape.needs_cache`), and its consumers (trade-intelligence, Tojlo) are hub-local; a spoke pays the
WireGuard round-trip per RPC. Live headroom this run:

```
$ ssh vps "free -h | head -2; sudo docker ps --format '{{.Names}}' | wc -l"
               total        used        free      shared  buff/cache   available
Mem:            11Gi       3.8Gi       1.4Gi       124Mi       6.9Gi       7.8Gi
31
```

Declared stack limits: bridge 512M + gotenberg 1G + trytond 2G + worker (compose `deploy.resources.limits.memory`
rows at `/opt/tryton-crm/compose.yaml:51,109,202`) ≈ ~4.5G worst-case vs 7.8G available → fits with margin.
Mesh addressing: n/a (hub-local — `postgres-main:5432`, never `10.99.0.1`).

## Phase 2 — Spec ↔ code ↔ compose reconciliation

- **Shape flags re-verified:** `needs_database: true` — the stack's trytond/worker use the `tryton` DB
  (bridge itself DB-free by Decision F-DB, `specs/services/tryton-crm.yaml:19`); `needs_cache: true` —
  `pause_state.py` uses Redis (spec `:22`); `exposes_metrics: true` — `GET /metrics` live at
  `src/tryton_crm/main.py:53`; `is_public: true` + `is_admin_dashboard: false` — tenant self-service
  login must NOT sit behind Authelia (spec `:12-16`); `has_persistent_data: true` — trytond-filestore
  volume (Backrest, Phase 7).
- **A1 (placeholder key+value semantics) — the fix is IN the spec:** `TRYTOND_DATABASE_URI` is
  deliberately ABSENT; the placeholder lives under `DATABASE_URL` (`specs/services/tryton-crm.yaml:70-76`),
  the key the postgres registrar injects and `_is_placeholder` (`src/fabrik/orchestrator/deployer_ssh.py:650`,
  value-scoped — the value contains the literal `placeholder`) protects on re-apply. The compose derives
  `TRYTOND_DATABASE_URI=${TRYTOND_DATABASE_URI:-${DATABASE_URL:-}}` (`/opt/tryton-crm/compose.yaml:144`)
  — `:-` falls through only when unset/empty, which A1's fix guarantees.
- **A5 (from_env precedence) — audited live:** resolution reads `/opt/tryton-crm/.env` BEFORE the hub
  env. All four `from_env` keys present at their winning source this run: `TRYTOND_RPC_USER=crm-bridge-svc`
  in the project `.env` (the A5 guard value, verified), `SERVICE_INTERNAL_SECRET_KEY` project+hub,
  `TRYTOND_RPC_PASSWORD` project+hub (S9 MINTS A NEW value — S10 must write it to the PROJECT `.env`,
  the winning copy, not only the hub's), `CONSUMER_TOKENS` hub-only (falls through correctly).
- **Secrets lifecycle:** `TRYTOND_ADMIN_PASSWORD` minted by `secrets.generate` at apply; the RPC
  credential lifecycle is S9→S10→S11 below (generated in-container, propagated to both `.env`s, second
  apply re-syncs — `fabrik redeploy` is CODE-ONLY and never touches `.env`, so the second APPLY is
  load-bearing).
- **Registrar redis index:** `acquire_db_index` allocates a dedicated DB index
  (`src/fabrik/orchestrator/infrastructure.py:868-874`) — the spec's db0-collision concern is handled
  by mechanism.
- Cosmetic (no action): `fabrik plan`'s env preview prepends saas-skeleton template defaults
  (`NODE_ENV`, `NEXT_TELEMETRY_DISABLED`) — template noise, harmless to a python stack.

## Phase 3 — Infra prerequisites

- **Staged cloudflare resolver on vps1 — read and diffed this run:** `/opt/traefik/traefik.yml.staged`
  adds the `cloudflare` certresolver (DNS-01, storage `/acme-cloudflare.json`) AND fixes
  `network: coolify → fabrik` (review B8); `/opt/traefik/compose.yaml.staged` adds
  `env_file: ./cf.env` ("root-only, created at activation") + the `acme-cloudflare.json` mount.
  Backups already staged (`*.bak-cf-20260809-214630`). `acme-cloudflare.json` exists (0 bytes, root 600).
  `cf.env` does NOT exist yet — S2 creates it from the hub's `CLOUDFLARE_API_TOKEN` (present in
  `/opt/fabrik/.env`, verified key-presence only) written as `CF_DNS_API_TOKEN` (lego's variable —
  review B6 verified against lego source, traefik v2.11).
- **DNS — live digs this run:** `tryton-crm.vps1.ocoron.com → 172.93.160.197` (vps1);
  `tojlo.com`, `*.tojlo.com`, `bhdtrade.tojlo.com`, and a random probe subdomain all →
  `172.93.160.197`; NS = Cloudflare (kiki/lex.ns.cloudflare.com) — consistent with the CF DNS-01 token path.
- **Registrar preview (embedded):**

```
$ .venv/bin/fabrik plan specs/services/tryton-crm.yaml   (tail)
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
```

## Phase 4 — Ordered runbook (exact commands · per-step verification · rollback)

Every command below is executable as written (stem + timestamps substituted; `<PASTE>` marks the one
operator-visible credential value flowing between steps, never echoed into logs). The maintenance
window spans S4–S8 ONLY (`window-open`/`window-close` labels per Phase 5).

1. **S1 — pre-flight guards (A5 + from_env presence).** `[anywhere on hub]`
   Command: `grep -c '^TRYTOND_RPC_USER=crm-bridge-svc$' /opt/tryton-crm/.env && for k in SERVICE_INTERNAL_SECRET_KEY CONSUMER_TOKENS TRYTOND_RPC_PASSWORD; do grep -l "^$k=" /opt/tryton-crm/.env /opt/fabrik/.env | head -1; done`
   Verify: first output `1` (exact-value guard) and each key names a source file. Retryable: yes.
   Rollback: none (read-only). FAIL → fix the `.env` source, re-run; a wrong RPC_USER is the
   admin-on-public-login launch blocker (spec `:47-49`).
2. **S2 — activate the cloudflare resolver (staged → live).** Guard pre-check (makes the step
   safe to re-run): `ssh vps "grep -c 'cloudflare:' /opt/traefik/traefik.yml"` → `1` means ALREADY
   active → skip to verification.
   Command (one invocation, root):
   `ssh vps "sudo bash -c 'umask 077 && printf \"CF_DNS_API_TOKEN=%s\n\" \"<PASTE hub CLOUDFLARE_API_TOKEN>\" > /opt/traefik/cf.env && chmod 600 /opt/traefik/cf.env && cp /opt/traefik/traefik.yml.staged /opt/traefik/traefik.yml && cp /opt/traefik/compose.yaml.staged /opt/traefik/compose.yaml && cd /opt/traefik && docker compose up -d'"`
   Verify (fenced): `ssh vps "sudo bash -c 'ls -l /opt/traefik/cf.env && docker ps --filter name=traefik --format \"{{.Status}}\" && docker logs traefik --since 2m 2>&1 | grep -ci error'"` —
   cf.env `-rw------- root`, traefik `Up`, error count `0`.
   Retryable: yes (idempotent copies). Rollback: `ssh vps "sudo bash -c 'cp /opt/traefik/traefik.yml.bak-cf-20260809-214630 /opt/traefik/traefik.yml && cp /opt/traefik/compose.yaml.bak-cf-20260809-214630 /opt/traefik/compose.yaml && cd /opt/traefik && docker compose up -d && rm -f /opt/traefik/cf.env'"` —
   verify rollback: traefik `Up`, no `cloudflare:` in live traefik.yml.
3. **S3 — the first apply (build + registrars).** Expected duration: minutes (image build; the 300s
   default died at M1 — the knob is `FABRIK_BUILD_TIMEOUT`, read at `src/fabrik/orchestrator/deployer_ssh.py:33`).
   Command (BACKGROUND it — >30s): `FABRIK_BUILD_TIMEOUT=1200 .venv/bin/fabrik apply specs/services/tryton-crm.yaml`
   Verify (fenced): apply output ends in success; then
   `ssh vps "sudo docker ps --filter name=tryton --format '{{.Names}} {{.Status}}'"` — tryton-crm,
   trytond, trytond-worker, gotenberg all `Up`; and the A1 outcome:
   `ssh vps "sudo grep -c '^DATABASE_URL=postgresql://placeholder' /opt/tryton-crm/.env"` → `0`
   (the registrar's real DSN replaced the placeholder) plus
   `ssh vps "sudo grep -c '^REDIS_URL=' /opt/tryton-crm/.env"` → `1`.
   Retryable: yes (apply is re-runnable; `_is_placeholder` protects injected reals on re-apply).
   Rollback: none destructive needed pre-traffic — a failed apply leaves the prior state; a half-up
   stack: `ssh vps "sudo bash -c 'cd /opt/tryton-crm && docker compose down'"` (verify: the three
   stack containers gone; shared infra untouched).
4. **S4 — `window-open`** (the init in S6 runs 8–10 min against a ~190s worst-case time-to-unhealthy —
   review B3; the healer would restart trytond mid-init).
   Command: `ssh vps "sudo bash -c 'mkdir -p /run/fabrik-autoheal && printf \"%s %s\n\" 2026-08-11-plan-deploy-tryton-crm \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\" > /run/fabrik-autoheal/pause.owner && touch /run/fabrik-autoheal/pause'"`
   (OWNER first, pause second — the authored ordering.) Verify (fenced):
   `ssh vps "sudo bash -c 'stat -c \"%n %Y\" /run/fabrik-autoheal/pause && cat /run/fabrik-autoheal/pause.owner'"` —
   both landed, owner first token `2026-08-11-plan-deploy-tryton-crm`. A different stem after our
   write = clobber race → halt. Owner OURS + pause missing = half-landed open → re-run ONCE.
   Retryable: yes. Rollback: the S8 close (below).
5. **S5 — PAUSED confirmation (BOUNDED 5 min).**
   Command: `ssh vps "sudo journalctl -t fabrik-autoheal --since '<the S4 touch timestamp>'"`
   Verify: a `PAUSED (maintenance window…)` line newer than the touch (healer ticks per minute —
   `scripts/vps-autoheal.sh:45`). No line within 5 minutes → halt protocol (never start S6 on an
   unconfirmed window). A `SKIP-RUN` line = a live instance still restarting — keep waiting within
   the same bound. Retryable: yes (a fresh read). Rollback: none (read-only).
6. **S6 — Tryton module init (the window's sensitive step; expected 8–10 min, cap 90 ✓).**
   Command: `ssh vps "sudo docker exec -e TRYTON_DB=tryton trytond /opt/crm-init/10-init-modules.sh"`
   (script baked into the image — `Dockerfile.trytond:45,49`).
   Verify: exit code `0` (echo $? fenced) + no traceback in the last lines. Retryable: yes (module
   activation is idempotent — a re-run converges), max 3 attempts then halt. Rollback (on abandon):
   none destructive — an incomplete activation is corrected by re-run or the halt protocol routes to
   review; the DB pre-init state needs no unwind for a first deploy (S3's rollback covers the stack).
7. **S7 — restart after init (B2 — the stale-Pool 500s trap; the project's own OPERATIONS.md §5b).**
   Command: `ssh vps "sudo docker restart trytond trytond-worker"`
   Verify (fenced): `ssh vps "sudo docker ps --filter name=trytond --format '{{.Names}} {{.Status}}'"` —
   both `Up` (healthy after healthcheck interval); bridge `/health` 200 via
   `ssh vps "sudo docker exec tryton-crm python3 -c \"import urllib.request;print(urllib.request.urlopen('http://localhost:8000/health').status)\""` → `200`.
   Retryable: yes. Rollback: none (restart is the fix, not a mutation).
8. **S8 — `window-close`.**
   Command: `ssh vps "sudo bash -c '[ -f /run/fabrik-autoheal/pause.owner ] && grep -q \"^2026-08-11-plan-deploy-tryton-crm \" /run/fabrik-autoheal/pause.owner && rm -f /run/fabrik-autoheal/pause /run/fabrik-autoheal/pause.owner || echo OWNERSHIP-LOST'"`
   Verify — CONDITIONAL, never rc alone (`OWNERSHIP-LOST` exits 0): fresh
   `ssh vps "sudo bash -c 'ls /run/fabrik-autoheal/ && cat /run/fabrik-autoheal/pause.owner 2>/dev/null'"`;
   PASS = both files gone, OR `OWNERSHIP-LOST` with a FOREIGN owner (first token ≠ this plan's stem)
   confirmed by that fresh cat; both present WITHOUT a foreign owner = rm failed → step failure;
   pause GONE with owner still OURS = half-landed close → re-run the guarded close ONCE; pause
   present with owner ABSENT = FOREIGN, never remove; any other outcome → conservative default
   (stop, report raw state — the 2h self-heal bounds residue). Retryable: per the branches only.
   Rollback: n/a (the close IS the window's rollback; ordered after S6/S7 so any window-needing
   rollback ran inside it).
9. **S9 — create the RPC service user (B1 — the dev-port trap).**
   Command: `ssh vps "sudo docker exec -e TRYTOND_TEST_HOST=localhost:8000 trytond python3 /opt/crm-init/create_rpc_service_user.py"`
   (in-container default is dev-only `localhost:18000` — double-confirmed; `--write-env` is dead
   in-container, the script PRINTS the generated 32-char password ONCE —
   `create_rpc_service_user.py:27-30,51,167`).
   Verify: exit 0 + the `[rpc-user] created/updated: login=crm-bridge-svc …` line + the printed
   password CAPTURED (not logged). NON-RERUNNABLE guard: a re-run REGENERATES the password (the
   script updates the existing login) — safe, but every re-run re-obligates S10; never re-run after
   S11 verified green. Rollback: none needed (an unused new password is inert until propagated).
10. **S10 — propagate the credential to BOTH .env copies (A5: the PROJECT copy wins from_env).**
    Command: `cp /opt/tryton-crm/.env backups/tryton-crm.env.backup.$(date +%Y%m%d-%H%M%S) && cp /opt/fabrik/.env backups/fabrik.env.backup.$(date +%Y%m%d-%H%M%S)` then edit `TRYTOND_RPC_PASSWORD=<PASTE from S9>` in `/opt/tryton-crm/.env` AND `/opt/fabrik/.env` (hub-side files; the runbook v2 line named only the hub copy — the project copy is the one from_env actually reads first, so BOTH are written, project first).
    Verify (fenced, masked): `for f in /opt/tryton-crm/.env /opt/fabrik/.env; do grep -c "^TRYTOND_RPC_PASSWORD=" $f; done` → `1` `1` and the two values IDENTICAL (`diff <(grep ^TRYTOND_RPC_PASSWORD= /opt/tryton-crm/.env) <(grep ^TRYTOND_RPC_PASSWORD= /opt/fabrik/.env)` → empty).
    Retryable: yes. Rollback: restore the two timestamped backups (verify: grep values match the backups).
11. **S11 — second apply (env-sync propagates the real credential + restarts).** `redeploy` is
    CODE-ONLY and never touches `.env` — only APPLY re-syncs (the site-provisioner incident class).
    Command (BACKGROUND): `FABRIK_BUILD_TIMEOUT=1200 .venv/bin/fabrik apply specs/services/tryton-crm.yaml`
    Verify (fenced): apply success; remote value propagated:
    `ssh vps "sudo grep -c '^TRYTOND_RPC_PASSWORD=' /opt/tryton-crm/.env"` → `1`  # noqa — key-presence grep, no credential value in this document
    Containers `Up`,
    and the BRIDGE can authenticate: the battery's CRM write probe (S13) is the real proof.
    Retryable: yes. Rollback: S10's backups + re-apply (restores the prior credential state).
12. **S12 — Gatus tenant-subdomain endpoint with certificate-expiry condition (M2).** Today Gatus has
    ZERO tojlo.com endpoints (live grep this run — Phase 7). The gatus registrar adds the
    `tryton-crm.vps1.ocoron.com` monitor at S3; this step adds the TENANT cert watch
    (`bhdtrade.tojlo.com`, conditions incl. `[CERTIFICATE_EXPIRATION] > 240h`) via the hub's gatus
    driver path, then verifies: the Gatus UI/API shows the endpoint green.
    Retryable: yes (additive config). Rollback: remove the added endpoint block, reload Gatus
    (verify: endpoint gone, Gatus healthy).
13. **S13 — the verification battery (Phase 6) — the deploy's EXIT GATE.** After the runbook (no
    deferred terminal gate exists in this runbook — the battery runs LAST, per the authored rule).

No `OPERATOR-GATE` steps: every act is hub-executable with hub-held credentials (the CF token and
the RPC password flow hub↔fleet, no store dashboard, no third-party publish act).

## Phase 5 — Maintenance-window interactions

The window brackets S4–S8 (module init — the only step a healthcheck outlives: worst-case ~190s
time-to-unhealthy vs 8–10 min init, review B3; the fleet-wide pause mechanism was E2E-proven
2026-08-10, `PAUSED` log 13:50:13). Labels: S4 `window-open` · S8 `window-close` (both authored in
executable root form above, stem `2026-08-11-plan-deploy-tryton-crm` substituted, single-backslash
escapes, operators whole at end-of-line). **No heartbeat step is scheduled**: the window's total
span (init 8–10 min + restart + close ≈ ≤20 min) sits far under both the 90-minute single-step cap
and the 120-minute touch-to-touch invariant — a single S4 touch covers it (`scripts/vps-autoheal.sh:44`,
7200s staleness). WAIT BOUND (foreign pause at open): 30 minutes (default). Watchdog posture:
`watchdog.enabled: false` in the spec (first-days flip is Phase 8); restart policies:
`unless-stopped` per compose — first-boot restart storms are bounded by the healer's own
restart-cap (3 per 30 min window, `vps-autoheal.sh:22-23`), and the window keeps it out of the init.

## Phase 6 — Verification battery (the exit gate, run as S13)

| # | Probe | Command (hub-side) | PASS |
|---|---|---|---|
| 1 | Translations loaded | `ssh vps "sudo docker exec trytond python3 /opt/crm-init/export_db_only_translations.py --count-only"` (or the project's documented count probe) | tr + fa each ≥ 7000 |
| 2 | Bridge health (real deps) | `curl -fsS https://tryton-crm.vps1.ocoron.com/health` | 200, body asserts deps |
| 3 | **WRITE path** — one CRM activity via the bridge (catches stale-Pool B2) | the bridge's documented activity-create call with the S10 credential | 2xx + row visible |
| 4 | Queue drain | `ssh vps "sudo docker exec trytond psql-check: SELECT count(*) FROM ir_queue WHERE dequeued_at IS NULL AND scheduled_at < now() - interval '5 min'"` (via the stack's psql access) | 0 stuck rows |
| 5 | Companion reachability | `ssh vps "sudo docker exec tryton-crm python3 -c \"import urllib.request;print(urllib.request.urlopen('http://gotenberg:3000/health').status)\""` | 200 from inside the stack |
| 6 | Tenant TLS + login | `curl -fsSI https://bhdtrade.tojlo.com` (cert via the NEW cloudflare resolver) + a GUI login smoke | valid cert (issuer LE, SAN *.tojlo.com), login page 200 |
| 7 | Same-origin brand route | `curl -fsS https://bhdtrade.tojlo.com/brand/bhdtrade \| head -c 200` | 200, brand payload |
| 8 | ACME diagnostics BEFORE blaming routing | `ssh vps "sudo docker logs traefik --since 30m 2>&1 \| grep -i 'acme\|cloudflare' \| tail -20"` | no unresolved errors; cert issued (read this BEFORE interpreting probe 6 failures) |
| 9 | Monitoring green | Gatus: both endpoints green; Prometheus: `tryton-crm` target `up == 1` | green/up |

Any FAIL → the plan's rollback/retry path for the implicated step, else the halt protocol. Never
report the deploy complete on a partial battery.

## Phase 7 — Monitoring / backup / DR truth (read live this run, never assumed)

- **Gatus:** zero `tojlo`/`tryton` endpoints exist today (live grep of `/opt/gatus/config/config.yaml`
  — empty result). The gatus registrar adds the service monitor at S3; S12 adds the tenant cert
  endpoint (M2). Post-deploy state: TWO endpoints.
- **Prometheus:** zero `tryton` scrape jobs today (live grep of `/opt/prometheus/prometheus.yml`);
  the prometheus registrar creates the job at S3 (`exposes_metrics: true + domain set`).
- **Backrest (M3, corrected narrative re-verified live):** the per-service plan class is vestigial;
  the REAL cover, read from `/opt/backrest/config/config.json` this run: `docker-volumes` plan →
  `/var/lib/docker/volumes` (carries `trytond-filestore`) and `postgres-dumps` → `/opt/backups`
  (carries the `tryton` DB dumps). Daily frequency, retention 30 (spec `backup:` block).
  RPO: ≤24h (daily volume+dump snapshots). RTO: restore = Backrest snapshot restore + `fabrik apply`
  (rebuild) — hours-scale, consistent with the fleet DR posture.
- **GlitchTip:** registrar RUNS (kind=service) — error reporting wired at apply.

## Phase 8 — First-days posture

- Watchdog stays OFF (`watchdog.enabled: false`); flip decision after the first quiet week
  (Tier-D candidate list already names tryton-crm — revisit then).
- Expected first-hours alerts: none if the battery passed; a `ContainerDown` on trytond during S6/S7
  cannot fire falsely — the window suppresses healing, and Gatus endpoints are created AFTER the
  window closes.
- Rollback decision rule: battery probe 3 (CRM write) or probe 6 (tenant TLS) failing after two
  fix attempts → halt protocol + route to review; the service is pre-launch (no tenant traffic to
  protect), so rollback = stack down + spec-state restore, decided by the operator on the BLOCKED report.
- Imports (initial data loads) run off-peak per the project's own ops docs; first-week review hook:
  re-run the battery once after 7 days (cert renewal + queue health).

## Behavior Contract

The deploy's user-observable behaviors ARE the battery (S13) — one probe per behavior, all against
the LIVE service. **Mocked: nothing** (every probe is a real request/read; the plan forbids
registry-row proofs).

- **Given** the stack is applied and initialized, **When** the bridge's `/health` is fetched over
  TLS, **Then** it returns 200 asserting real dependencies (probe 2).
- **Given** the S10 credential propagated, **When** one CRM activity is created via the bridge,
  **Then** it succeeds and the row is visible — the stale-Pool class cannot hide (probe 3).
- **Given** module init completed, **When** translation counts are read, **Then** tr and fa each
  ≥ 7000 (probe 1).
- **Given** the worker runs, **When** `ir_queue` is inspected, **Then** zero stuck rows (probe 4).
- **Given** the compose stack network, **When** gotenberg's `/health` is fetched FROM the bridge
  container, **Then** 200 (probe 5).
- **Given** the cloudflare resolver is active, **When** `bhdtrade.tojlo.com` is fetched, **Then**
  TLS is valid (wildcard SAN) and login renders — with the ACME log read BEFORE interpreting any
  failure (probes 6+8).
- **Given** tenant routing, **When** `/brand/bhdtrade` is fetched same-origin, **Then** 200 with
  brand payload (probe 7).
- **Given** the registrars ran, **When** Gatus and Prometheus are checked, **Then** both endpoints
  green and the scrape target `up` (probe 9).

## Evidence

```
$ ssh vps "ls -la /run/fabrik-autoheal/"      # healer live, no pause residue (only .lock, ticking)
-rw-r--r--  1 root root    0 Aug 11 08:15 .lock
$ ssh vps "sudo diff /opt/traefik/traefik.yml /opt/traefik/traefik.yml.staged"   # staged delta
20c20  <     network: coolify   >     network: fabrik    (+ the cloudflare certresolver block)
$ dig +short tryton-crm.vps1.ocoron.com bhdtrade.tojlo.com   # both → 172.93.160.197
```

- Spec: `specs/services/tryton-crm.yaml:70-76` (A1 fix), `:47-49` (RPC_USER rationale), `:22` (redis note)
- Compose: `/opt/tryton-crm/compose.yaml:144` (derivation), `:51,109,202` (memory limits), `:224-228` (HostRegexp + cloudflare resolver)
- Init provenance: `/opt/tryton-crm/Dockerfile.trytond:45,49`
- Script behavior: `/opt/tryton-crm/scripts/trytond/create_rpc_service_user.py:30,51,167`
- Healer: `scripts/vps-autoheal.sh:44-48` (7200s), `:45` (PAUSED line)
- Build timeout: `src/fabrik/orchestrator/deployer_ssh.py:33`; placeholder guard `:650`
- Redis index: `src/fabrik/orchestrator/infrastructure.py:868-874`

## Self-audit

- Verified live this run: release readiness (service gate 45/0), target headroom, staged resolver
  content + diff, DNS (apex/wildcard/tenant), autoheal installed + clear state, Backrest plan paths,
  Gatus/Prometheus absence (pre-deploy truth), from_env source presence + the A5 guard value,
  registrar preview, init-script provenance, RPC-script password behavior.
- Assumed (runbook-verified at deploy time, not assumable now): the actual DSN/REDIS_URL injection
  values (S3 verifies), cert issuance through the new resolver (S13 probe 8 diagnoses before probe 6
  is interpreted), the battery's translation counts.
- Residuals the review must attack: (a) S10 writes a credential into TWO files — the masked-diff
  verification is the only cross-copy consistency proof; (b) probe 1's exact count command is the
  project's documented probe — the review should pin its exact form from the project's test docs;
  (c) probe 4's psql invocation shape needs the stack's actual psql access path pinned; (d) S12's
  gatus driver invocation is named, not spelled — pin the exact command or config block; (e) the
  deprecated `specs/services/trytond.yaml.superseded` must never be applied (S3 names the stack spec
  explicitly).
- Question bar: no operator decisions deferred — target, domain, and credential flows are all
  spec/review-settled; no `[OPEN]` items.

Next command: /fabrik-deploy-plan-review — adversarially converge the deploy plan before it is trusted.
