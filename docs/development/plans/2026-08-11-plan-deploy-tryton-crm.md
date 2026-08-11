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

What this first deploy ships = the **v0.1.0 cut** (tagged 2026-08-10 — tenant branding, role
bundles and the bulk of the CRM build live under `## [0.1.0]`) **plus the `[Unreleased]` tail**
(bridge tenant-resolution fixes, VAT/KDV work, and interleaved design-spec entries). Ordinal- and
position-free by design (rounds 3-4: sibling commits move entries within minutes, and design-spec
entries interleave with feature entries — no positional rule holds): design/spec entries describe
plans and ship nothing by their own text (one carries the explicit marker "Nothing here ships into
the pending BHD deploy"); every feature/fix entry in the section is part of the deploying build.
`/fabrik-deploy`'s Phase 0 re-proves release readiness FRESH at dispatch — this header records the
authoring-time proof, not a dispatch-time claim.

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
rows at `/opt/tryton-crm/compose.yaml:51,109,202,254` — bridge 512M + gotenberg 1G + trytond 2G +
worker 512M) ≈ ~4.0G worst-case vs 7.8G available → fits with margin.
Mesh addressing: n/a (hub-local — `postgres-main:5432`, never `10.99.0.1`).

## Phase 2 — Spec ↔ code ↔ compose reconciliation

- **Shape flags re-verified:** `needs_database: true` — the stack's trytond/worker use the `tryton` DB
  (bridge itself DB-free by Decision F-DB, `specs/services/tryton-crm.yaml:19`); `needs_cache: true` —
  `pause_state.py` uses Redis (spec `:21`); `exposes_metrics: true` — `GET /metrics` live at
  `src/tryton_crm/main.py:53`; `is_public: true` + `is_admin_dashboard: false` — tenant self-service
  login must NOT sit behind Authelia (spec `:12-16`); `has_persistent_data: true` — trytond-filestore
  volume (Backrest, Phase 7).
- **⚠ GOTENBERG COLLISION (review F1 — would kill the first apply):** a STANDALONE `gotenberg`
  container (compose project `/opt/gotenberg`, image 8.32.0, basic-auth, public at
  `pdf.vps1.ocoron.com`) has been Up on vps1 for ~4 weeks and owns both the container NAME and the
  `gotenberg` network alias on the shared `fabrik` net. The stack's compose also declares
  `container_name: gotenberg` (`/opt/tryton-crm/compose.yaml:103`) — `docker compose up` in a
  different project dies on the name conflict, and even renamed, the bridge's code-default
  `http://gotenberg:3000` would resolve to the basic-auth'd standalone (401). Resolution (decided):
  the stack's service+container rename to `crm-gotenberg` (PROJECT compose edit — the S0 relay
  precondition) + `GOTENBERG_URL: http://crm-gotenberg:3000` now declared in the spec
  (`specs/services/tryton-crm.yaml` env block, added by this review). The compose's own "no such
  service exists anywhere on the fleet" comment (`compose.yaml:90-91`) was false when written.
- **A1 (placeholder key+value semantics) — the fix is IN the spec:** `TRYTOND_DATABASE_URI` is
  deliberately ABSENT; the placeholder lives under `DATABASE_URL` (`specs/services/tryton-crm.yaml:71-76`, the placeholder at `:76`),
  the key the postgres registrar injects and `_is_placeholder` (`src/fabrik/orchestrator/deployer_ssh.py:650`,
  value-scoped — the value contains the literal `placeholder`) protects on re-apply. The compose derives
  `TRYTOND_DATABASE_URI=${TRYTOND_DATABASE_URI:-${DATABASE_URL:-}}` (`/opt/tryton-crm/compose.yaml:144`)
  — `:-` falls through only when unset/empty, which A1's fix guarantees.
- **A5 (from_env precedence) — audited live, order QUOTED FROM CODE:** `_load_secrets` reads the
  project copy first (`src/fabrik/orchestrator/__init__.py:306-317` — `project_path =
  Path(f"/opt/{spec.id}")`, project `.env` keys win) and only then falls to `os.getenv`
  (`:321-325`), whose values come from `/opt/fabrik/.env` via `config.py:16 load_dotenv()`. All four
  `from_env` keys present at their winning source this run: `TRYTOND_RPC_USER=crm-bridge-svc`
  in the project `.env` (the A5 guard value, verified), `SERVICE_INTERNAL_SECRET_KEY` project+hub,
  `TRYTOND_RPC_PASSWORD` project+hub (S9 MINTS A NEW value — S10 must write it to the PROJECT `.env`,
  the winning copy, not only the hub's), `CONSUMER_TOKENS` hub-only (falls through correctly).
- **Secrets lifecycle — ⚠ the `generate` re-mint trap (review F4):** `TRYTOND_ADMIN_PASSWORD` is
  `secrets.generate`; `SecretsManager.get` resolves os.environ → hub `.env` → **generate fresh,
  never persisted** — and the hub `.env` has NO such key today (verified count 0), so EVERY apply
  mints a NEW value and `_build_env_content` overwrites the remote `.env` with it
  (`deployer_ssh.py:595-597`). S6 sets the DB admin password to the S3-minted value
  (`10-init-modules.sh:42-50` reads it from env); an unpinned S11 would re-mint and desynchronize
  the DB from every `.env` copy, stranding the real admin password nowhere. S3b therefore PINS the
  S3-minted value into `/opt/fabrik/.env` (backed up) BEFORE any later apply, making `get()` stable.
  The RPC credential lifecycle is S9→S10→S11 (generated in-container, propagated to both `.env`s,
  second apply re-syncs — `fabrik redeploy` is CODE-ONLY and never touches `.env`, so the second
  APPLY is load-bearing).
- **Registrar redis index:** `acquire_db_index` allocates a dedicated DB index
  (`src/fabrik/orchestrator/infrastructure.py:868-874`) — the spec's db0-collision concern
  (`specs/services/tryton-crm.yaml:21`) is handled by mechanism.
- **First-deploy choreography truth (round 2):** the apply pipeline is secrets → DNS → deploy
  (`up -d --wait`, raises on failure) → registrars → verifier (`orchestrator/__init__.py:154-186`) —
  the `tryton` DB and env injections exist only AFTER a successful `--wait`, and the bridge's
  readiness `/health` cannot pass before S9 (its ping authenticates as the S9-created login). S0(b)
  (liveness healthcheck) + S3's `--skip-health-check` are what make the first apply completable;
  the S13 battery is the honest readiness gate.
- **Spec doc-truth corrections (this review):** `expose.internal_only` is a DEAD field (defined
  `spec_loader.py:123`, read by no orchestrator code) and its comment now says so — the compose's
  Traefik labels are the routing truth; the `SERVICE_INTERNAL_SECRET_KEY` comment now states the
  production fail-closed truth (dev-allowlist only, `internal_auth.py:38-45`).
- Cosmetic (no action): `fabrik plan`'s env preview prepends saas-skeleton template defaults
  (`NODE_ENV`, `NEXT_TELEMETRY_DISABLED`) — template noise, harmless to a python stack.

## Phase 3 — Infra prerequisites

- **Staged cloudflare resolver on vps1 — read and diffed this run:** `/opt/traefik/traefik.yml.staged`
  adds the `cloudflare` certresolver (DNS-01, storage `/acme-cloudflare.json`) AND fixes
  `network: coolify → fabrik` (review B8); `/opt/traefik/compose.yaml.staged` adds
  `env_file: ./cf.env` ("root-only, created at activation") + the `acme-cloudflare.json` mount.
  Backups already staged — exact names matter for the S2 rollback (live `ls` this run):
  `traefik.yml.bak-20260809-214630` (NO `-cf` infix) and `compose.yaml.bak-cf-20260809-214630`
  (WITH it). `acme-cloudflare.json` exists (0 bytes, root 600).
  `cf.env` does NOT exist yet — S2 creates it from the hub's `CLOUDFLARE_API_TOKEN` (present in
  `/opt/fabrik/.env`, verified key-presence only) written as `CF_DNS_API_TOKEN` (lego's variable —
  review B6 verified against lego source, traefik v2.11).
- **DNS — live digs, re-verified authoritatively (review F3 corrected the first draft's false
  line):** `tryton-crm.vps1.ocoron.com` is **NXDOMAIN today** — no record, no wildcard under
  `vps1.ocoron.com`; `fabrik apply` CREATES it (the orchestrator's `_provision_dns` — `src/fabrik/orchestrator/__init__.py:159` calling `:451-510`, `dns.add_subdomain`; the vps1 IP is in that path's own table, no `VPS_IP` env precondition),
  so the deploy is not blocked — S3's verification confirms the record post-apply. The tenant side
  IS live: `tojlo.com`, `*.tojlo.com`, `bhdtrade.tojlo.com` all → `172.93.160.197`; NS = Cloudflare
  (kiki/lex.ns.cloudflare.com) — consistent with the CF DNS-01 token path.
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

Every command below is executable as written (stem + timestamps substituted; `<PASTE …>` marks the
THREE operator-flowed credential-adjacent values — the S10 RPC password from S9's print, and probe
3's `org_id` AND consumer token from the operator's CONSUMER_TOKENS grant — never echoed into
fenced output or the ledger). Every grep-count verify in this runbook is judged by its PRINTED
value, never by exit code (a correct `0` count exits nonzero — rc alone misreads success as failure).
The maintenance window spans S4–S8 ONLY (`window-open`/`window-close` labels per Phase 5).

0. **S0 — BLOCKING PRECONDITION: TWO project-compose edits (reviews F1 + R2-deadlock).** The
   tryton-crm project must land BOTH, in one relay (cross-repo — the operator relays to the
   tryton-crm AI; the deploy session may not edit that repo):
   (a) rename the in-stack service+container `gotenberg → crm-gotenberg`
   (`/opt/tryton-crm/compose.yaml:100-109` — service key, `container_name`, and any depends_on
   references; the spec now pins `GOTENBERG_URL: http://crm-gotenberg:3000`);
   (b) point the BRIDGE's compose healthcheck at the LIVENESS endpoint —
   `compose.yaml:37` test URL `/health` → `/healthz` (`main.py:113-124` — always-200 liveness);
   (c) make `trytond-worker` TOLERATE an unavailable/unauthorized DB at startup (round-3 finding,
   REPRODUCED with the project's own image: the worker opens a real connection at startup —
   `trytond/worker.py:84` → `:30 get_connection()` — and on the first-apply placeholder DSN dies in
   `psycopg_pool.PoolTimeout` after 30s, exit 1, crash-looping under `restart: unless-stopped` so
   `--wait` never settles even with (a)+(b) landed. Requirement, mechanism the project AI chooses:
   a wait-for-DB entrypoint loop (stay alive while the DSN is unready) AND no DB-dependent
   healthcheck on the worker service; production-correct anyway — a postgres-main restart must not
   crash-loop the worker).
   Rationale (round-2 confirmed first-deploy DEADLOCK): the bridge's `/health` is READINESS —
   `proteus_client.ping` reads `res.user` AS `crm-bridge-svc` (`proteus_client.py:211-235`), a
   login S9 creates — so the bridge CANNOT be Docker-healthy before init+S9, `docker compose up -d
   --wait` fails (`deployer_ssh.py:473` — the GIT-source deploy path this spec takes), the deployer raises, and the registrars (which create the
   `tryton` DB) NEVER RUN — S3 deadlocks by construction. Liveness is also the correct Docker
   semantic: restarting the bridge never fixes an unreachable trytond, and the healer would
   restart-storm it on every trytond blip. Readiness stays Gatus's job (the domain `/health`).
   Verify (fenced, before S1): `grep -c 'container_name: crm-gotenberg' /opt/tryton-crm/compose.yaml`
   → `1` AND `grep -c 'container_name: gotenberg$' /opt/tryton-crm/compose.yaml` → `0` AND the
   SERVICE KEY too — `grep -c '^  crm-gotenberg:' /opt/tryton-crm/compose.yaml` → `1` AND
   `grep -c '^  gotenberg:' /opt/tryton-crm/compose.yaml` → `0` (a container_name-only rename still
   publishes the `gotenberg` network alias from the service name — the collision survives) AND
   `grep -c 'healthz' /opt/tryton-crm/compose.yaml` → `≥1` (0 today — bridge :37 and gotenberg :113
   both use `/health`, live-proven non-vacuous) AND the worker tolerance landed (grep the worker
   block for its wait mechanism as the project AI names it in the relay reply — re-pinned at the
   review's re-entry) AND committed+pushed, EXECUTABLY:
   `git -C /opt/tryton-crm status --short` → empty AND
   `git -C /opt/tryton-crm log origin/mobasak/tryton-crm..HEAD --oneline` → empty. ANY check wrong
   → HALT — do NOT proceed to S1. Retryable: yes (re-grep). Rollback: n/a (a verification gate).
   THE PLAN STAYS DRAFT until all three land.
1. **S1 — pre-flight guards (A5 + from_env presence + cross-copy drift).** `[anywhere on hub]`
   Command: `grep -c '^TRYTOND_RPC_USER=crm-bridge-svc$' /opt/tryton-crm/.env && grep -c '^TRYTOND_RPC_USER=crm-bridge-svc$' /opt/fabrik/.env && for k in SERVICE_INTERNAL_SECRET_KEY CONSUMER_TOKENS TRYTOND_RPC_PASSWORD; do grep -l "^$k=" /opt/tryton-crm/.env /opt/fabrik/.env | head -1; done`
   Verify: first TWO outputs `1` (exact-value guard in BOTH copies — the project copy wins from_env,
   the hub copy must not drift) and each key names a source file. Retryable: yes.
   Rollback: none (read-only). FAIL → fix the `.env` source, re-run; a wrong RPC_USER is the
   admin-on-public-login launch blocker (spec `:49-51`).
2. **S2 — activate the cloudflare resolver (staged → live).** Guard pre-check (makes the step
   safe to re-run; the indented-key form cannot match a comment): `ssh vps "grep -c '^  cloudflare:' /opt/traefik/traefik.yml"` → `1` means ALREADY
   active → skip to verification.
   Command (TWO invocations; the token never appears on any command line — review F9-class fix: it
   is read from the hub `.env` into the pipe directly):
   `grep '^CLOUDFLARE_API_TOKEN=' /opt/fabrik/.env | sed 's/^CLOUDFLARE_API_TOKEN=/CF_DNS_API_TOKEN=/' | ssh vps "sudo bash -c 'umask 077 && cat > /opt/traefik/cf.env && chmod 600 /opt/traefik/cf.env'"`  # noqa — key-name grep/pipe form, no credential value in this document
   then
   `ssh vps "sudo bash -c 'cp /opt/traefik/traefik.yml.staged /opt/traefik/traefik.yml && cp /opt/traefik/compose.yaml.staged /opt/traefik/compose.yaml && cd /opt/traefik && docker compose up -d'"`
   Verify (fenced): `ssh vps "sudo bash -c 'ls -l /opt/traefik/cf.env && wc -l < /opt/traefik/cf.env && docker ps --filter name=traefik --format \"{{.Status}}\" && docker logs traefik --since 2m 2>&1 | grep -ci error'"` —
   cf.env `-rw------- root`, exactly `1` line, traefik `Up`, error count `0`.
   Retryable: yes (idempotent copies). Rollback (exact live backup names — the traefik one has NO
   `-cf` infix): `ssh vps "sudo bash -c 'cp /opt/traefik/traefik.yml.bak-20260809-214630 /opt/traefik/traefik.yml && cp /opt/traefik/compose.yaml.bak-cf-20260809-214630 /opt/traefik/compose.yaml && cd /opt/traefik && docker compose up -d && rm -f /opt/traefik/cf.env'"` —
   verify rollback: traefik `Up`, no `cloudflare:` in live traefik.yml, cf.env gone.
3. **S3 — the first apply (build + registrars).** Expected duration: minutes (image build; the 300s
   default died at M1 — the knob is `FABRIK_BUILD_TIMEOUT`, read at `src/fabrik/orchestrator/deployer_ssh.py:33`).
   Command (BACKGROUND it — >30s): `FABRIK_BUILD_TIMEOUT=1200 .venv/bin/fabrik apply --skip-health-check specs/services/tryton-crm.yaml`
   (`--skip-health-check` — `cli.py:418`, wired at `:528`, skips ONLY the verifier's post-deploy
   `/health` probe (`verifier.py:62`), which is readiness-shaped and legitimately 503 until S11 on
   this first deploy; container liveness still gates via compose `--wait` — `deployer_ssh.py:473`,
   the GIT-source path — on the S0(b) `/healthz` healthcheck plus the S0(c) worker tolerance, and
   the S13 battery is the honest health gate. S0(b)+(c)+this flag are jointly what make the first
   apply completable.)
   Verify (fenced): apply output ends in success; then
   `ssh vps "sudo docker ps --format '{{.Names}} {{.Status}}' | grep -E 'tryton|crm-gotenberg'"` — tryton-crm,
   trytond, trytond-worker, crm-gotenberg all `Up` (a `--filter name=tryton` can never show
   crm-gotenberg — substring filter); the A1 outcome:
   `ssh vps "sudo grep -c '^DATABASE_URL=postgresql://placeholder' /opt/tryton-crm/.env"` → `0`
   (the registrar's real DSN replaced the placeholder) plus
   `ssh vps "sudo grep -c '^REDIS_URL=' /opt/tryton-crm/.env"` → `1`; the registrar's DB really
   exists (guards S6 against a partial apply):
   `ssh vps "sudo docker exec postgres-main psql -U postgres -lqt"` — a `tryton` row present; and
   the DNS record now exists: `dig @kiki.ns.cloudflare.com +short tryton-crm.vps1.ocoron.com` →
   `172.93.160.197` (AUTHORITATIVE NS — public resolvers, 1.1.1.1 included, negative-cache the
   pre-apply NXDOMAIN for up to the SOA minimum ~30 min; the zone's own NS answers fresh).
   Retryable: yes (apply is re-runnable; `_is_placeholder` protects injected reals on re-apply).
   Rollback: none destructive needed pre-traffic — a failed apply leaves the prior state; a half-up
   stack: `ssh vps "sudo bash -c 'cd /opt/tryton-crm && docker compose down'"` (verify: the four
   stack containers gone; shared infra untouched).
3b. **S3b — pin the minted admin credential (review F4 — every apply RE-MINTS `generate` keys).**
   `SecretsManager.get` resolves os.environ → hub `.env` → mint-fresh-never-persist; the hub `.env`
   has no `TRYTOND_ADMIN_PASSWORD` today, so S11 would mint a NEW value and desynchronize the DB
   (set at S6 from the S3 value) from every `.env`. Pin the S3-minted value NOW:
   `if grep -q '^TRYTOND_ADMIN_PASSWORD=' /opt/fabrik/.env; then echo PRE-EXISTING; else mkdir -p /opt/fabrik/backups && cp /opt/fabrik/.env /opt/fabrik/backups/fabrik.env.backup.$(date +%Y%m%d-%H%M%S) && ssh vps "sudo grep '^TRYTOND_ADMIN_PASSWORD=' /opt/tryton-crm/.env" >> /opt/fabrik/.env; fi`  # noqa — key-name grep/pipe form, no credential value in this document
   (the guard is IN the command — a blind re-run prints `PRE-EXISTING` and appends nothing, so no
   duplicate line is possible).
   Verify (fenced, count only): `grep -c '^TRYTOND_ADMIN_PASSWORD=' /opt/fabrik/.env` → `1`, and
   `cmp -s <(ssh vps "sudo grep '^TRYTOND_ADMIN_PASSWORD=' /opt/tryton-crm/.env") <(grep '^TRYTOND_ADMIN_PASSWORD=' /opt/fabrik/.env) && echo IDENTICAL` → `IDENTICAL` (values never printed).  # noqa — key-name grep/pipe form, no credential value in this document
   On `PRE-EXISTING` + a `cmp` MISMATCH: STOP — a prior run's pin diverged from the remote;
   investigate (the backups + the remote value decide), never overwrite blind.
   Retryable: yes (now idempotent by the in-command guard). Rollback: restore the timestamped backup.
4. **S4 — `window-open`** (the init in S6 runs 8–10 min against a ~190s worst-case time-to-unhealthy —
   review B3; the healer would restart trytond mid-init).
   PRE-OPEN PROBE (round 3 — the open's `printf >` would silently truncate a foreign owner):
   `ssh vps "sudo bash -c 'stat -c %Y /run/fabrik-autoheal/pause 2>/dev/null; cat /run/fabrik-autoheal/pause.owner 2>/dev/null'"` —
   pause present with a FOREIGN first token and age <2h → the Phase-5 WAIT BOUND (re-probe every
   60s up to 30 min, then halt — never write over a live foreign window); absent / ours / ≥2h-dead
   → open:
   Command: `ssh vps "sudo bash -c 'mkdir -p /run/fabrik-autoheal && printf \"%s %s\n\" 2026-08-11-plan-deploy-tryton-crm \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\" > /run/fabrik-autoheal/pause.owner && touch /run/fabrik-autoheal/pause'"`
   (OWNER first, pause second — the authored ordering.) Verify (fenced):
   `ssh vps "sudo bash -c 'stat -c \"%n %Y\" /run/fabrik-autoheal/pause && date -u +%Y-%m-%dT%H:%M:%SZ && cat /run/fabrik-autoheal/pause.owner'"` —
   both landed, owner first token `2026-08-11-plan-deploy-tryton-crm`; CAPTURE the epoch (`%Y`) for
   S5's `--since "@<epoch>"` form. A different stem after our
   write = clobber race → halt. Owner OURS + pause missing = half-landed open → re-run ONCE.
   Retryable: yes. Rollback: the S8 close (below).
5. **S5 — PAUSED confirmation (BOUNDED 5 min).**
   Command: `ssh vps "sudo journalctl -t fabrik-autoheal --since '@<the S4 pause epoch from stat %Y>'"`
   (`--since` needs `@epoch` or a date string — a bare epoch fails to parse.)
   Verify: a `PAUSED (maintenance window…)` line newer than the touch (healer ticks per minute —
   `scripts/vps-autoheal.sh:45`). No line within 5 minutes → halt protocol (never start S6 on an
   unconfirmed window). A `SKIP-RUN` line = a live instance still restarting — keep waiting within
   the same bound. Retryable: yes (a fresh read). Rollback: none (read-only).
6. **S6 — Tryton module init (the window's sensitive step; expected 8–10 min, cap 90 ✓).**
   Command: `ssh vps "sudo docker exec -e TRYTON_DB=tryton trytond /opt/crm-init/10-init-modules.sh"`
   (script baked into the image — `Dockerfile.trytond:45,49`).
   Verify: exit code `0` (echo $? fenced) + no traceback in the last lines. Per-attempt runtime
   bound: ABORT a wedged attempt at 20 minutes (2× the expected ceiling — kills the
   silent-wedge path long before the 7200s pause staleness; the window has no heartbeat).
   Retryable: yes (module activation is idempotent — a re-run converges), max 3 attempts then halt. Rollback (on abandon):
   none destructive — an incomplete activation is corrected by re-run or the halt protocol routes to
   review; the DB pre-init state needs no unwind for a first deploy (S3's rollback covers the stack).
7. **S7 — restart after init (B2 — the stale-Pool 500s trap; the project's own OPERATIONS.md §5b).**
   Command: `ssh vps "sudo docker restart trytond trytond-worker"`
   Verify (fenced): `ssh vps "sudo docker ps --filter name=trytond --format '{{.Names}} {{.Status}}'"` —
   PASS requires the literal `(healthy)` in BOTH Status strings (gates S9 — `Up` alone means the
   healthcheck hasn't confirmed; wait out the 30s interval × retries); bridge LIVENESS `/healthz`
   200 (round 3: `/health` readiness CANNOT pass before S11 — its ping authenticates as the
   S9-created login with the S10-propagated password; battery probe 2 owns the `/health` 200) via
   `ssh vps "sudo docker exec tryton-crm python3 -c \"import urllib.request;print(urllib.request.urlopen('http://localhost:8000/healthz').status)\""` → `200`.
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
    Command: `mkdir -p /opt/fabrik/backups && cp /opt/tryton-crm/.env /opt/fabrik/backups/tryton-crm.env.backup.$(date +%Y%m%d-%H%M%S) && cp /opt/fabrik/.env /opt/fabrik/backups/fabrik.env.backup.$(date +%Y%m%d-%H%M%S)` then edit `TRYTOND_RPC_PASSWORD=<PASTE from S9>` in `/opt/tryton-crm/.env` AND `/opt/fabrik/.env` (hub-side files; the runbook v2 line named only the hub copy — the project copy is the one from_env actually reads first, so BOTH are written, project first).
    Verify (fenced, masked — `cmp -s`, never `diff`, so a MISMATCH prints nothing rather than both
    credential lines): `for f in /opt/tryton-crm/.env /opt/fabrik/.env; do grep -c "^TRYTOND_RPC_PASSWORD=" $f; done` → `1` `1` and
    `cmp -s <(grep '^TRYTOND_RPC_PASSWORD=' /opt/tryton-crm/.env) <(grep '^TRYTOND_RPC_PASSWORD=' /opt/fabrik/.env) && echo IDENTICAL || echo MISMATCH` → `IDENTICAL`.  # noqa — key-name grep/pipe form, no credential value in this document
    Retryable: yes. Rollback: restore the two timestamped backups (verify: grep values match the backups).
11. **S11 — second apply (env-sync propagates the real credential + restarts).** `redeploy` is
    CODE-ONLY and never touches `.env` — only APPLY re-syncs (the site-provisioner incident class).
    Command (BACKGROUND): `FABRIK_BUILD_TIMEOUT=1200 .venv/bin/fabrik apply specs/services/tryton-crm.yaml`
    Verify (fenced): apply success; remote value propagated:
    `ssh vps "sudo grep -c '^TRYTOND_RPC_PASSWORD=' /opt/tryton-crm/.env"` → `1`  # noqa — key-presence grep, no credential value in this document
    Containers `Up`,
    and the BRIDGE can authenticate: the battery's CRM write probe (S13) is the real proof.
    Retryable: yes. Rollback: S10's backups + re-apply (restores the prior credential state).
12. **S12 — Gatus tenant-subdomain endpoint with certificate-expiry condition (M2).** Today Gatus
    has ZERO tojlo.com endpoints (verified at the REAL config path — Phase 7). The gatus registrar
    adds the `tryton-crm.vps1.ocoron.com` monitor at S3, but the driver's `add_endpoint` has NO
    conditions parameter (`src/fabrik/drivers/gatus.py`) — the cert condition needs an explicit
    per-app config block, matching the live format (`/opt/monitoring/configs/gatus/apps/*.yaml`,
    `endpoints:` list with `conditions:`):
    write `/opt/monitoring/configs/gatus/apps/tryton-crm-tenant.yaml` on vps1 (root) with:
    `endpoints: [{name: tryton-crm-tenant-cert, group: apps, url: "https://bhdtrade.tojlo.com/", interval: 5m, conditions: ["[STATUS] == 200", "[CERTIFICATE_EXPIRATION] > 240h"], alerts: [{type: custom}]}]`
    (YAML-expanded, matching the sibling files' shape) then `ssh vps "sudo docker restart gatus"`.
    Verify: the Gatus UI/API shows `tryton-crm-tenant-cert` green.
    Retryable: yes (additive config). Rollback: remove the added file, restart Gatus
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

Table-cell command convention (round 3): a backslash-pipe (`\|`) inside a cell is the MARKDOWN
escape for a literal shell pipe — strip the backslash when executing (grep-REGEX alternations like
`'login\|tryton'` keep theirs: that backslash is BRE syntax, not markdown). `<now ISO>` in probe 3
= `$(date -u +%Y-%m-%dT%H:%M:%SZ)` substituted hub-side when building the JSON body.

| # | Probe | Command (hub-side) | PASS |
|---|---|---|---|
| 1 | Translations loaded (the project's OWN documented probe — `/opt/tryton-crm/docs/DEPLOYMENT.md:217-218`) | `ssh vps "sudo docker exec postgres-main psql -U postgres -d tryton -c \"select lang, count(*) from ir_translation where lang in ('tr','fa') and value<>'' group by lang;\""` | tr ≈ 7000+, fa ≈ 7200+ (a tr of 0 = the translatable step failed) |
| 2 | Bridge health (readiness) | `curl -fsS https://tryton-crm.vps1.ocoron.com/health` | 200 — asserts the TRYTOND dependency, the app's designed readiness scope (`main.py:126-143`; gotenberg is probe 5's, the write path proves the rest) |
| 3 | **WRITE path** — party + activity through the bridge (catches stale-Pool B2; exercises the S10 RPC credential end-to-end). ⚠ Auth truth (round 2): `ENVIRONMENT=production` disables the shared-secret path — `_shared_secret_enabled()` fails closed outside the dev allowlist (`src/tryton_crm/internal_auth.py:38-45`), so the token MUST be a `CONSUMER_TOKENS` consumer token whose grant carries this org + `write` scope (`internal_auth.py:109-133`). All routes mount under `/internal/v1` (`api/__init__.py:26`) | two calls with `-H "X-Internal-Token: <PASTE consumer token from CONSUMER_TOKENS>"`: `curl -fsS -X POST "https://tryton-crm.vps1.ocoron.com/internal/v1/parties/upsert?org_id=<PASTE org_id from the same grant>" -H 'Content-Type: application/json' -d '{"org_id":"<same org_id>","org_name":"Deploy Probe Org","external_id":"deploy-probe-2026-08-11","name":"Deploy Probe","country":"TR","confidence":1.0}'` then `POST /internal/v1/activities/upsert?org_id=<same>` with `{"party_id":<party_id from call 1>,"external_id":"deploy-probe-act-1","kind":"note","summary":"deploy battery probe","timestamp":"<now ISO>","confidence":1.0}` (`api/parties_write.py:47,53`, `api/activities.py:91`, required fields per `schemas/write.py:56-69,102-113`; body org_id must equal the query per `assert_org_match`) | both 2xx; `activity_id` returned (the probe party is inert pre-launch data — note it in the ledger) |
| 3b | **Fail-closed auth** — the write path REJECTS a bad AND a missing token (the rubric's fail-closed mandate; auth is a dependency, so it beats body validation — proven 401-before-422) | `curl -s -o /dev/null -w '%{http_code}' -X POST "https://tryton-crm.vps1.ocoron.com/internal/v1/parties/upsert?org_id=<same>" -H "X-Internal-Token: invalid-garbage" -H 'Content-Type: application/json' -d '{}'` then the SAME call with NO `X-Internal-Token` header at all | `401` (or `403`) BOTH times — never 2xx/422 |
| 4 | Queue drain (via postgres-main — the stack containers carry no psql; form proven live this review) | `ssh vps "sudo docker exec postgres-main psql -U postgres -d tryton -c \"SELECT count(*) FROM ir_queue WHERE dequeued_at IS NULL AND scheduled_at < now() - interval '5 min'\""` | `0` stuck rows |
| 5 | Companion reachability (the RENAMED in-stack renderer — S0) | `ssh vps "sudo docker exec tryton-crm python3 -c \"import urllib.request;print(urllib.request.urlopen('http://crm-gotenberg:3000/health').status)\""` | 200 from inside the stack |
| 6 | ACME diagnostics FIRST (ordered BEFORE the TLS probes — a cert-pending state must never be misread as a routing failure) | `ssh vps "sudo docker logs traefik --since 30m 2>&1 \| grep -i 'acme\|cloudflare' \| tail -50"` | no unresolved errors; the wildcard cert issued via the `cloudflare` resolver |
| 7 | Tenant TLS + login surface (executable form — the interactive GUI login is the operator's Phase-8 first-days smoke, not a battery gate) | `curl -fsSI https://bhdtrade.tojlo.com` then `curl -fsS https://bhdtrade.tojlo.com \| grep -ci 'login\|tryton'` | valid cert (SAN `*.tojlo.com`), 200, login markers ≥ 1 (on FAIL: probe 6's ACME read is already in hand — diagnose from it) |
| 8 | Same-origin brand route | `curl -fsS https://bhdtrade.tojlo.com/brand/bhdtrade \| head -c 200` | 200, brand payload (`api/brand.py:39`) |
| 9 | Monitoring green (forms proven live this review) | Gatus API via fabrik-net DNS: `ssh vps "sudo docker exec tryton-crm python3 -c \"import urllib.request,json;d=json.load(urllib.request.urlopen('http://gatus:8080/api/v1/endpoints/statuses',timeout=5));print([(e['name'],e['results'][-1]['success'] if e['results'] else None) for e in d if e['name'] in ('tryton-crm','tryton-crm-tenant-cert')])\""` — prints exactly the two endpoints' (name, success) tuples (the raw payload is ~350KB — a filter, never a slice); Prometheus: `ssh vps "sudo docker exec prometheus wget -qO- 'http://localhost:9090/api/v1/query?query=up{job=\"fabrik-tryton-crm\"}'"` — the registrar prefixes every job `fabrik-` (`drivers/prometheus.py:95,122-123`); a `None` in the output = an empty `results` list (a just-created S12 endpoint inside its first 5m interval) — not-yet-green, wait one interval and re-run | both Gatus endpoints success; Prometheus value `"1"` |

Any FAIL → the plan's rollback/retry path for the implicated step, else the halt protocol. Never
report the deploy complete on a partial battery.

## Phase 7 — Monitoring / backup / DR truth (read live this run, never assumed)

- **Gatus:** zero `tojlo`/`tryton` endpoints exist today — verified at the REAL config path
  (review F7 corrected the first draft's nonexistent-path grep): per-app files under
  `/opt/monitoring/configs/gatus/apps/` (`GATUS_CONFIG_DIR`, `src/fabrik/drivers/gatus.py:44`;
  13 app files live, zero tojlo/tryton matches). The gatus registrar adds the service monitor at
  S3 (`infrastructure.py:688-706`); S12 adds the tenant cert endpoint (M2). Post-deploy: TWO endpoints.
- **Prometheus:** zero `tryton` scrape jobs today — verified at the REAL path
  `/opt/monitoring/configs/prometheus/prometheus.yml` (`src/fabrik/drivers/prometheus.py:61-62`);
  the prometheus registrar creates the job at S3 (`exposes_metrics: true + domain set`) as
  **`fabrik-tryton-crm`** (JOB_PREFIX, `prometheus.py:95,122-123`), scraping the spec's explicit
  `monitoring.target: tryton-crm:8000` (added by this review, round 6 — WITHOUT it the
  saas-skeleton branch would target the nonexistent `tryton-crm-api:8000` and `up` would be 0
  forever, `infrastructure.py:927-932`).
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
- **Expected alert window DURING the deploy (review F5 corrected the first draft's false claim):**
  the gatus registrar creates the service monitor at S3 — BEFORE the S4–S8 window — and the
  bridge's `/health` is a readiness probe that 503s whenever trytond is unreachable
  (`src/tryton_crm/main.py:126-143`), so Gatus MAY flap red during S6 init and the S7 restart (the
  healer pause suppresses the HEALER, never Gatus). Per the fleet rule (silence alerts before
  >2-min downtime), the deploy session acknowledges/silences the tryton-crm Gatus alert for the
  FULL S3→S11 span (round 3: `/health` is 503 from first boot until S11 completes — the monitor is
  red the whole choreography, not just S4–S8) — or accepts the bounded Telegram noise and says so
  in the ledger. First hours AFTER
  the battery: no alerts expected; any `ContainerDown`/endpoint-red then is real.
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
  TLS, **Then** it returns 200 asserting the trytond dependency — the app's designed readiness
  scope (probe 2).
- **Given** the S10 credential propagated, **When** one CRM activity is created via the bridge,
  **Then** it succeeds and the row is visible — the stale-Pool class cannot hide (probe 3).
- **Given** module init completed, **When** translation counts are read, **Then** tr and fa each
  ≥ 7000 (probe 1).
- **Given** the worker runs, **When** `ir_queue` is inspected, **Then** zero stuck rows (probe 4).
- **Given** the compose stack network, **When** `crm-gotenberg`'s `/health` is fetched FROM the
  bridge container, **Then** 200 (probe 5).
- **Given** the cloudflare resolver is active, **When** `bhdtrade.tojlo.com` is fetched, **Then**
  TLS is valid (wildcard SAN) and login renders — with the ACME log read FIRST (probes 6→7).
- **Given** a garbage `X-Internal-Token`, **When** a write route is called, **Then** 401/403 —
  the auth path fails CLOSED (probe 3b).
- **Given** tenant routing, **When** `/brand/bhdtrade` is fetched same-origin, **Then** 200 with
  brand payload (probe 8).
- **Given** the registrars ran, **When** Gatus and Prometheus are checked, **Then** both endpoints
  green and the scrape target `up` (probe 9).

## Evidence

```
$ ssh vps "ls -la /run/fabrik-autoheal/"      # healer live, no pause residue (only .lock, ticking)
-rw-r--r--  1 root root    0 Aug 11 08:15 .lock
$ ssh vps "sudo diff /opt/traefik/traefik.yml /opt/traefik/traefik.yml.staged"   # staged delta
20c20  <     network: coolify   >     network: fabrik    (+ the cloudflare certresolver block)
$ dig @1.1.1.1 tryton-crm.vps1.ocoron.com A   # NXDOMAIN — apply creates it (_provision_dns, orchestrator/__init__.py:451-510)
$ dig +short bhdtrade.tojlo.com               # 172.93.160.197 (wildcard *.tojlo.com live)
$ ssh vps "sudo docker inspect gotenberg --format '{{.Config.Image}} {{.State.Status}}'"
gotenberg/gotenberg:8.32.0 running               # the F1 standalone collision, live
```

- Spec: `specs/services/tryton-crm.yaml:71-76` (A1 fix, placeholder `:76`), `:49-51` (RPC_USER rationale), `:21` (redis note), `:62` `GOTENBERG_URL` (F1)
- Compose: `/opt/tryton-crm/compose.yaml:144` (derivation), `:51,109,202,254` (memory limits), `:224-228` (HostRegexp + cloudflare resolver)
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
- Review round 1 (2026-08-11, pool ×4 + native Opus + author grounding) resolved the first draft's
  residuals: probe 1/3/4 forms PINNED from the project's own docs and live probes; S12's config
  block spelled against the live per-app format; S10's verify made leak-proof (`cmp -s`); the
  monitoring evidence re-grounded at the real driver paths; the DNS and backup-name evidence
  corrected to authoritative truth; S3b added for the `generate` re-mint trap; the CHANGELOG cite
  refreshed (positions move under sibling commits — the marker entry is anchored by its TEXT, not
  its position; see the header's position-free rule).
- **BLOCKING unknown (the flip waits on it): S0 — THREE project-side compose/entrypoint edits**
  (cross-repo — owner: the tryton-crm AI, relayed by the operator): (a) rename the service key +
  `container_name` `gotenberg → crm-gotenberg` (`/opt/tryton-crm/compose.yaml:100-109`); (b) bridge
  healthcheck test URL `/health` → `/healthz` (`compose.yaml:37`); (c) `trytond-worker` startup
  tolerance for an unavailable DB (wait-loop entrypoint + no DB-dependent healthcheck — the exact
  mechanism is the project AI's, named in the relay reply). Commit + push all three. Verify lands
  via S0's greps + the git-clean/pushed checks. Until all three land the plan stays DRAFT.
- Standing residuals (bounded): (e) the deprecated `specs/services/trytond.yaml.superseded` must
  never be applied (S3 names the stack spec explicitly); the Backrest restore path is stated but
  not drill-rehearsed (fleet DR posture item, not this deploy's scope).
- Question bar: ONE batched operator item — relay S0's THREE project edits (rename + healthz
  healthcheck + worker DB-wait tolerance) to the tryton-crm AI (a cross-repo relay, not a design
  decision; the resolutions are decided and pinned above).

Next command: /fabrik-deploy-plan-review — adversarially converge the deploy plan before it is trusted.
