# Deploy Plan — Zitadel v4 umbrella IdP (`auth.ocoron.com`)

Status: CONVERGED — re-converged 2026-08-29 after the RUN 3 verify halt; all FOUR deploy-machinery findings (D1 db_before_boot · Aa1! password · up--wait · verifier health.disabled probe 1c90bf81) resolved + landed on master; RUN 1-3 ⛔ rows adjudicated; clean slate re-probed (DB absent, container absent)
Service: zitadel
Surface: VPS (single-image `source.type: docker`, third-party image — no service repo)
Target: vps1 (LA hub)
Date: 2026-08-28
Stage: 6-release · deploy triad step 2 (re-review after the D1 fix)

## ✅ RESOLVED FINDING D1 — deploy-order/DB-at-boot contradiction (fixed by machinery + fallback runbook)

**The finding (grounded, Zitadel issues [#5810], [#11942] + self-hosting troubleshooting doc):**
`start-from-init` has **no DB-connection retry — it exits immediately if postgres is unreachable.** But
fabrik's order is container-first: `deploy()` runs `deployer.deploy` (`up -d --wait`) at
`orchestrator/__init__.py:170`, and the postgres registrar injects `DATABASE_URL` only afterward at `:180`.
So a naive `fabrik apply` boots Zitadel with an empty DSN → it exits → the compose-up (deployer_ssh.py `_compose_up`)
raises → rollback at `:207` **before** the registrar runs → no DB → a repeat re-crashes identically.

**Fix (b) — the durable machinery change (shipped this review):** a new opt-in `deploy.db_before_boot: true`
(`specs/services/zitadel.yaml`). When set + `needs_database`, the orchestrator's new
`_pre_provision_db_for_boot` (`__init__.py`, called at step 2b **before** `deployer.deploy`) creates the DB +
role via `create_database` and seeds the resolved `DATABASE_URL` into `ctx.secrets`, so
`_build_env_content` (deployer_ssh.py) writes it into the **initial** `.env` — the container's first boot has
the DSN, `start-from-init` connects, init succeeds. The post-deploy registrar (:173) runs `create_database`
again → idempotent (DB exists → no password → `.env` preserved), so **no double-provision**. Opt-in, so every
other service is byte-identical. Red-first tests: `tests/orchestrator/test_pre_provision_db.py` (6 tests:
seed-on-flag, strict no-op without the flag, no-op without `needs_database`, `depends.postgres` derivation,
**name-first precedence parity with the registrar (#3)**, **DB tracked for rollback (#4a)**). **Fabrik-wide
follow-up** (make this automatic for all init-at-boot images, or a DB-wait wrapper) stays filed at
`docs/STRATEGIC_BACKLOG.md` [fleet].

**Re-review hardening (independent finder, 2026-08-28) — 3 issues found + resolved:** (#3) the pre-provision's
db-name precedence was reversed vs the registrar (`id`-first vs `name`-first) — a latent split-brain for a future
`db_before_boot` service with `name != id` and no `depends.postgres`; **fixed** to `name or id`
(`__init__.py`, matching `infrastructure.py:413`) + a parity test. (#4a) the pre-provisioned DB wasn't tracked;
**fixed** with `ctx.add_resource` so a failed-deploy rollback warns about the orphan (postgres rollback is a
manual-drop advisory, never destructive). (#6) the fix rides on docker-compose **`env_file` value interpolation**
(`ZITADEL_DATABASE_POSTGRES_DSN=${DATABASE_URL}`) — a mechanism distinct from the `command:` interpolation the
emitter verified; **grounded** by a live `docker compose config` test on the box (Compose 2.40.3): the value
resolves to a real `postgresql://…` (not the literal `${DATABASE_URL}`). Version dependency: env_file
interpolation is default-on ≥ Compose 2.24; the box is 2.40.3. See `## Evidence`.

**Fallback (a) — manual bootstrap (if `db_before_boot` is ever unavailable):** create the `zitadel` DB+role on
`postgres-main` out-of-band, write the resolved DSN into `/opt/zitadel/.env`, then `docker compose up -d`.
On a FRESH first deploy the masterkey re-mint (F1) is harmless (no data yet), widening the options. This is
the documented recovery; the primary path is now the clean `fabrik apply` (S3) that (b) makes work.

## ✅ RESOLVED — deploy-machinery findings surfaced live (all fixed + proven)

This deploy stress-tested the machinery: one live `fabrik apply` surfaced FOUR distinct deploy-machinery
defects across RUN 1–3 (D1 was found earlier at plan-review). Each was fixed at the source and re-proven the
next run; the ledger below carries the per-run adjudication. Summary of the fixes the next dispatch relies on:

- **D1 — deploy-order / DB-at-boot** → `deploy.db_before_boot` pre-provisions the DB + seeds `DATABASE_URL`
  before first boot (commit a47d5e20; see the D1 section above). *Proven live RUN 2 (DB pre-created).*
- **Admin-password complexity** → `ZITADEL_FIRSTINSTANCE_ORG_HUMAN_PASSWORD: "${ZITADEL_ADMIN_PASSWORD}Aa1!"`
  guarantees the symbol/upper/lower/number Zitadel's default policy requires (commit 03265c1d).
  *Proven live RUN 2 (start-from-init cleared 03_default_instance, served /debug/ready 200).*
- **`up --wait` ↔ `health.disabled`** → `deployer_ssh._compose_up` uses `up -d` (not `--wait`, which needs a
  healthcheck a scratch image can't have) + an external readiness poll (commit 43ced0d3).
  *Proven live RUN 3 (deploy reached all six registrars).*
- **Verifier in-band probe ↔ `health.disabled`** → `DeploymentVerifier.verify` skips the in-band HTTPS
  probe when `health.disabled` is set, mirroring `_compose_up`; liveness is owned by external Gatus + the
  deployer's readiness poll (commit 1c90bf81, 2 red-on-revert tests). This is the RUN 3 blocker; a healthy
  Zitadel had been rolled back (incl. its DNS record) by a transient DNS/ACME-timing probe failure.

All four are landed + pushed on master. The next dispatch runs the amended runbook from S1 with a clean slate
for the deploy — **re-probed this turn on vps1: no `zitadel` container, no `zitadel` DB, `auth.ocoron.com`
unresolved.** NB the postgres rollback is a destructive-NO-OP (`rollback.py` only WARNS, never drops a DB), so
"the rollback removed everything" would be false: the `zitadel` DB was dropped **out-of-band** during RUN 1–3
recovery, and `/opt/zitadel/.env` + `/opt/zitadel/` **survive** on the box. Both survivors are harmless — RUN 4's
fresh secrets overlay `.env` unconditionally (`deployer_ssh.py:655`), and `db_before_boot` re-creates the ABSENT
DB + re-seeds the DSN (the empty DB makes the F1 masterkey re-mint harmless). S1's pre-flight (`## Evidence`)
asserts the DB is absent before S3 — the one survivor that WOULD matter (a lingering DB) is checked, not assumed.

## Release readiness — `N/A (third-party image)` + hub-artifact evidence

Zitadel is a **third-party container** (`ghcr.io/zitadel/zitadel:v4.17.1`) — there is **no `/opt/zitadel`
service repo** and **no service `scripts/final_gate.py`** to prove release-ready in the usual sense, so the
`/fabrik-release` precondition is `N/A-VPS(third-party-image)`. The **deployable artifacts** are all in the
HUB repo and are release-proven this session:

```
$ git log --oneline -4 --format='%h %s'
c5eec314 chore(plan): Epic-1 Zitadel deploy plan EXECUTED — archived + lock released
adbbc384 docs(deploy): docs/reference/zitadel.md — Zitadel v4 deploy runbook + verification
2c1c0bbe feat(deploy): specs/services/zitadel.yaml — Zitadel v4 umbrella IdP deploy spec
(Phase-0 emitter fix a20fa1cb: _generate_docker_compose emits image_command + honors health.disabled)

$ git log origin/master..HEAD --oneline    # unpushed
(empty — all three artifacts pushed)

$ python scripts/final_gate.py --json   # THIS session, post-Phase-B
GATE: success passed 55 failed 0
```

The spec is CONVERGED + committed; the emitter machinery it depends on is committed+pushed; the hub gate is
green. Operator directive this turn: proceed to the deploy triad (`NEXT:` pasted verbatim). The tree's other
dirty paths (`.windsurf/rules/ai/*`, `PORTS.md`, …) are **sibling WIP, not this run's** — untouched.

---

## Phase 0 — Surface resolution

Zitadel has no `project.yaml` (a third-party image, not a scaffolded project), so surface is resolved from
**artifact inference** (`fabrik-deploy-plan.md:98-108`): exactly one probe matches — `specs/services/zitadel.yaml`
exists in the HUB tree → **VPS**. `eas.json` / MV3 `manifest.json` / electron config: none. Running from
`/opt/fabrik` (hub-side) — correct for a VPS surface (`fabrik-deploy-plan.md:62-67`). The spec's shape is
`kind: service` (`specs/services/zitadel.yaml:2`), the full VPS contract (Phases 1–8) applies.

## Phase 1 — Target decision with evidence

`target_vps: vps1`. Zitadel's DB is `postgres-main` (`depends.postgres: zitadel`,
`specs/services/zitadel.yaml:25-26`), which is **hub-only** (`agents-fabrik-core.md`: shared infra is vps1;
spokes reach it at `10.99.0.1:5432` over WireGuard, paying a round-trip per query). An identity provider is
on the hot path for every RP login → co-locate with `postgres-main` on vps1. Headroom confirms it fits:

```
$ ssh vps "free -h | grep Mem"
Mem:   11Gi   4.1Gi used   846Mi free   7.1Gi buff/cache   7.5Gi available
$ ssh vps "sudo docker ps -q | wc -l"
31
```

7.5 GiB available vs the spec's `resources.memory: 1G` (`specs/services/zitadel.yaml:60-61`) — ample. No spoke
mesh-addressing consequence applies (vps1 uses container DNS `postgres-main`, not `10.99.0.1`).

## Phase 2 — Spec ↔ code ↔ compose reconciliation (the deploy-breakers)

**Shape flags** — re-verified; for a third-party image the flags describe Zitadel's behavior, not "our code":
`needs_database:true` (DSN env consumed, `specs/services/zitadel.yaml:35`), `exposes_metrics:true`
(`/debug/metrics` default-on, `docs/reference/zitadel.md:48`), `needs_cache:false` (Zitadel self-caches),
`is_admin_dashboard:false` (Zitadel **is** the auth — never behind Authelia), `is_public:true`,
`has_persistent_data:true` (state in postgres). The `fabrik plan` preview confirms the resolved registrar set:

```
$ fabrik plan specs/services/zitadel.yaml
   postgres  RUNS (needs_database) · gatus RUNS (is_public+domain) · backrest RUNS (has_persistent_data)
   glitchtip RUNS (kind=SERVICE) · grafana RUNS (always) · prometheus RUNS (exposes_metrics+domain)
   redis/authelia/meilisearch/watchdog: skipped.  Proceeding with 6 registrars.
```

**`${VAR}` tracing** — every compose var has a source: `${DATABASE_URL}` ← postgres registrar
(`infrastructure.py:588` `inject_env(ctx, {"DATABASE_URL": ...})`); `${ZITADEL_MASTERKEY}` +
`${ZITADEL_ADMIN_PASSWORD}` ← `secrets.generate` (`specs/services/zitadel.yaml:54-56`);
`${RESEND_API_KEY}` ← `from_env`, **present in the hub `.env`** (verified: `grep -qc RESEND_API_KEY .env` → present).
**Correction (D4, review):** an earlier draft claimed the python-api template injects `LOG_LEVEL`/`PYTHONUNBUFFERED`
— it does NOT for a `source.type: docker` service (the compose is built by `_generate_docker_compose`, no
template rendering; `_build_env_content` seeds `.env` only from the remote `.env` + spec env + secrets). Those
vars are simply **absent**; the `fabrik plan` preview showed them because `plan` renders the nominal template,
not the docker path. No unresolved or double-sourced var.

**⚠️ FINDING F1 (CRITICAL — masterkey re-mint = data loss).** `generate` secrets resolve via
`secrets_manager.load_all(generate)` (`orchestrator/__init__.py:301-303`), which reads only process-env + a
**hub-local** dotenv (`secrets.py:60,77-101`) — it does **NOT** get the remote-`.env` preservation read that
`from_env` gets (`__init__.py:306-320`), and even that read targets a hub-local `/opt/zitadel/.env` that will
never exist for a remote-only service. Consequence: the masterkey is minted on **first** apply into the
**remote** `/opt/zitadel/.env`, but a **second** `fabrik apply` re-mints a NEW masterkey (the hub resolver
never sees the remote value) and the secret is layered unconditionally at highest precedence
(`deployer_ssh.py:655`, `merged[key]=str(value)` — no `_is_placeholder` guard, unlike DATABASE_URL) →
**Zitadel can no longer decrypt stored data.** Mitigation is a runbook invariant (S-INV below): **apply once**.
⚠️ **Both `fabrik apply` AND `fabrik redeploy --refresh-infra` re-run `_load_secrets`** (`__init__.py:154`,
`:387`) and re-mint; only **plain `fabrik redeploy zitadel`** is safe — its non-git branch is bare
`docker compose up -d --wait` (`deployer_ssh.py:316-333`), no secret re-resolution. **D3 (review): plain redeploy
also cannot deliver an image bump** (it neither `pull`s nor re-renders the compose for a pinned tag), so a
Zitadel security patch has no safe fabrik path — redeploy won't fetch it, apply re-mints. Safe upgrade =
manual in-place: `ssh vps "cd /opt/zitadel && sudo sed -i 's|:v4.17.1|:vNEW|' compose.yaml && sudo docker
compose pull && sudo docker compose up -d"` (`.env` + masterkey preserved). Masterkey length is correct —
`generate_secret()` defaults to 32 `[a-zA-Z0-9]` chars (`secrets.py:12-22`) = Zitadel's hard requirement.

**FINDING F2 (A1 placeholder class — does NOT bite here).** The `_is_placeholder` merge guard
(`deployer_ssh.py:649` guard, def `:708`) protects an injected real value only when the spec value contains the literal
`placeholder`. Zitadel's spec carries **no** dummy secret values (secrets are `generate`/`from_env`, not
literals), and `${DATABASE_URL}` is the exact key the registrar injects — so no realistic-dummy clobber path
exists. Noted clean.

**FINDING F3 (A5 from_env precedence — clean).** `RESEND_API_KEY` has no `/opt/zitadel/.env` on the hub, so it
resolves from the hub process-env / hub `.env` (`__init__.py:321-325`) — the value verified present. Idempotent
(an external key, same value every apply). Runbook S2 prints it masked before apply.

## Phase 3 — Infra prerequisites

**DNS — AUTO-PROVISIONED by `fabrik apply` (NOT operator-gated, corrected 2026-08-28).** `auth.ocoron.com` does
not resolve today, but that is expected pre-deploy and requires **no manual action**: `fabrik apply`'s
`_provision_dns` (`src/fabrik/orchestrator/__init__.py:166` call, def `:529`, deploy step 3, BEFORE the container) parses the
spec `domain` into subdomain `auth` + base `ocoron.com`, resolves `target_vps: vps1 → 172.93.160.197` from its
`VPS_IPS` table, and creates the A record via `DNSClient.add_subdomain` → `POST /api/cloudflare/dns/{domain}/subdomain`
— the **Cloudflare** route through site-provisioner (`provision.vps1.ocoron.com`, the fleet's DNS gateway;
`ocoron.com` is a Cloudflare-managed zone, NS `kiki/lex.ns.cloudflare.com`). From the hub, `DNSClient` reaches
the container over SSH (`SITE_PROVISIONER_CONTAINER` + `SITE_PROVISIONER_INTERNAL_URL` in `.env`). The
line-582 `_provision_dns` code comment still reads "Namecheap first" — that comment is STALE; the primary call
is the Cloudflare subdomain endpoint (the `CloudflareClient` direct-API path is the on-exception fallback). The
runbook only **VERIFIES** the record (S1 below), never creates it by hand.

```
$ dig +short auth.ocoron.com A         # (empty NOW — fabrik apply's _provision_dns creates it at deploy)
$ dig +short provision.vps1.ocoron.com A
172.93.160.197                          # vps1 — the IP _provision_dns will point auth.ocoron.com at
```

**Cert story:** new base label on the existing `ocoron.com` zone; Traefik's existing ACME resolver issues on
first router load (public HTTP-01/DNS-01 per the hub's Traefik config) — no new resolver needed (same zone as
`provision.vps1.ocoron.com`, already issuing).
**Traefik middleware:** `is_admin_dashboard:false` + `is_public:true` (`specs/services/zitadel.yaml:7-8`) → the
scaffold-emitted public middleware is `gzip@docker` only, **no `authelia-forward`** (CLAUDE.md middleware rule:
Zitadel is the auth, never behind Authelia). Registrar preview embedded in Phase 2.

## Phase 4 — Ordered runbook (each step: id · command · verify · rollback)

**S-INV (standing invariant, not a step):** per F1, this service is **apply-once**. After S3 succeeds, updates
ship via `fabrik redeploy zitadel` (code/image only). A re-`apply` is permitted **only** after the operator
pins the remote-minted `ZITADEL_MASTERKEY` into the hub secret source — otherwise it is a data-loss event.

1. **S1** — DNS is created AUTOMATICALLY by S3's `fabrik apply` (`_provision_dns`, `__init__.py:166`, routes
   `auth.ocoron.com → 172.93.160.197` via site-provisioner) — **no manual/operator step**. This step VERIFIES it
   post-apply: `dig +short auth.ocoron.com A` → `172.93.160.197` (allow a short propagation window). *rollback:*
   n/a (a stray A record is harmless; delete via `fabrik.drivers.dns.DNSClient` / site-provisioner if ever needed).
   *rerunnable:* yes (read-only verify; `_provision_dns` itself is idempotent).
2. **S2** — masked from_env preview (confirm the key is present without printing its value):
   `grep -q RESEND_API_KEY /opt/fabrik/.env && echo "RESEND present"`.
   *verify:* prints `RESEND present`. *rollback:* n/a (read-only). *rerunnable:* yes.
3. **S3** — first deploy: `FABRIK_BUILD_TIMEOUT=1200 fabrik apply specs/services/zitadel.yaml`. **D1-fixed:**
   because `deploy.db_before_boot: true`, the orchestrator pre-creates the `zitadel` DB + role and seeds
   `DATABASE_URL` into the initial `.env` at **step 2b** (before `deployer.deploy`), so the container's first
   `start-from-init` boot connects, runs migrations, and completes; the post-deploy registrar (:173) then no-ops
   on the existing DB. Pulls the ~1 GiB scratch image + init ≈ 3–8 min. *verify (S5); rollback (S-RB).*
   *rerunnable:* on a FRESH first deploy the masterkey re-mint (F1) is harmless (no data yet), so a re-run is
   safe until Zitadel first completes init; after data exists, updates go via plain `redeploy` only (S-INV).
4. **S4** — retrieve the admin password: `ssh vps "sudo grep ZITADEL_ADMIN_PASSWORD /opt/zitadel/.env"`.
   ⚠️ **the actual LOGIN password is that value + `Aa1!`** (the spec sets `ZITADEL_FIRSTINSTANCE_ORG_HUMAN_PASSWORD:
   "${ZITADEL_ADMIN_PASSWORD}Aa1!"` to satisfy Zitadel's default complexity policy — see the S3-halt fix); it is
   change-required on first login, so the suffix is throwaway. *verify:* a 32-char value returned (login = it + `Aa1!`).
   *rollback:* n/a. *rerunnable:* yes.
5. **S5** — env-injection proof (scratch image, **no shell** — `docker inspect`, never `docker exec printenv`,
   `docs/reference/zitadel.md:42`): `ssh vps "sudo docker inspect zitadel --format '{{range .Config.Env}}{{println .}}{{end}}'" | grep -E 'ZITADEL_DATABASE_POSTGRES_DSN=postgresql://|GLITCHTIP_DSN=|ZITADEL_MASTERKEY=.'`.
   **D2 (review): grep the RESOLVED DSN, not the raw `DATABASE_URL` key** — `ZITADEL_DATABASE_POSTGRES_DSN=${DATABASE_URL}`
   (`zitadel.yaml:35`) is what Zitadel actually reads, and `.env`-value interpolation is compose-version-dependent
   (default-on only since ~v2.24); a bare `DATABASE_URL` key can be present while the consumed DSN is still the
   literal `${DATABASE_URL}`. Verifying the raw key "cannot fail" in the way that matters. *verify:* the DSN line
   shows a real `postgresql://…` value + `GLITCHTIP_DSN` present. *rollback:* n/a (read-only). *rerunnable:* yes.
- **S-RB (rollback, whole-deploy, first-deploy only):**
  `ssh vps "cd /opt/zitadel && sudo docker compose down"` then drop the empty DB
  `ssh vps "sudo docker exec postgres-main psql -U postgres -c 'DROP DATABASE zitadel'"`.
  *verify:* `dig`/`curl` no longer routes; `psql -l` shows no `zitadel`. **Safe ONLY before any real user/org
  data exists** (a fresh first deploy) — the masterkey is disposable while the DB is empty. Never run against a
  live instance.
  **⚠️ Recovery after a failed first apply (#4b, re-review):** `db_before_boot` creates the DB **before** the
  container boots, so a first-boot failure leaves the DB behind (now tracked → the rollback warns about it).
  A blind `fabrik apply` re-run will NOT re-seed `DATABASE_URL` — `create_database` early-returns on the existing
  DB with **no password**, so the fresh `.env` regenerates without the DSN and the container re-crashes.
  **Drop the DB first** (`DROP DATABASE zitadel` as above, empty-DB-only), then re-apply from clean — the
  pre-provision then re-mints the role password and re-seeds the DSN. (Data-bearing instance → never drop; go
  via `redeploy`.)

## Phase 5 — Maintenance-window interactions (healing layer) — `N/A-VPS`

**No window bracket is needed.** `vps-autoheal.sh` only restarts containers Docker marks **UNHEALTHY**
(`scripts/vps-autoheal.sh:53`, the `--filter health=unhealthy` predicate). With `health.disabled` (`specs/services/zitadel.yaml:73-75`) the compose emits
**no HEALTHCHECK**, so Docker reports the container's health as *none* — never `unhealthy` — and autoheal never
acts on it, even during the multi-minute `start-from-init` migration. There is therefore no long-unhealthy
step to bracket with `window-open/heartbeat/close`. ⚠️ **Caveat (review):** `restart: unless-stopped` (emitter
default) will crash-loop `start-from-init` UNCAPPED if the DB is unreachable (Docker's own restart policy —
autoheal's storm-cap governs only autoheal restarts) — this is the surface form of D1, and because there's no
healthcheck, Gatus (once probing `/debug/ready` per the F-A fix) is what surfaces a persistent crash-loop. This
Phase-5 N/A (no autoheal window) is grounded in the autoheal predicate; the crash-loop risk itself is D1's.

## Phase 6 — Verification battery (the deploy's exit gate)

Authored here; `/fabrik-deploy` runs it AFTER the runbook (no deferred gate). Full method table:
`docs/reference/zitadel.md:70-78`. The load-bearing probes:

- **WRITE-path (B2) — D4/F-D (review): `/debug/ready` → 200 is a READ/connectivity proof, NOT a write proof.**
  `curl -fsS https://auth.ocoron.com/debug/ready` → `200` proves the connection pool to `postgres-main` is live
  (DB-checked readiness, `docs/reference/zitadel.md:47`) — it only *indirectly* implies init's row-seeding
  succeeded. **The real automated write probe is: create a user via the mgmt API / Console → the row persists**
  (a fresh read returns it). Do not label the 200 a write proof; keep the user-create as the battery's write step.
- **OIDC discovery:** `curl -s https://auth.ocoron.com/.well-known/openid-configuration | jq .backchannel_logout_supported`
  → `true`; JWKS URI reachable.
- **Companion reachability:** `postgres-main` from the zitadel container (already implied by a 200 `/debug/ready`).
- **ACME/cert (new domain, M2):** read the Traefik acme log **before** the TLS test so a cert-pending state is
  not misread as a routing failure.
- **SMTP:** trigger a verification mail → delivered via Resend.

## Phase 7 — Monitoring / backup / DR truth

- **Gatus (F-A, FIXED at source):** the gatus registrar reads `health.path` (`infrastructure.py:762`), which
  defaults to `/health` — a path Zitadel does NOT serve (404 → permanent false-DOWN). **Fixed by adding
  `health.path: /debug/ready` to the spec** (`specs/services/zitadel.yaml`, this review) so the registrar probes
  `https://auth.ocoron.com/debug/ready`. `/debug/ready` is not on the Authelia bypass list, but Zitadel isn't
  behind Authelia, so the probe reaches it (`docs/reference/zitadel.md:49-51`).
- **Prometheus (F-B, FIXED at source):** the registrar reads `monitoring.metrics_path` defaulting to `/metrics`
  (`infrastructure.py:979`) — Zitadel serves `/debug/metrics`. **Fixed by adding a `monitoring: {metrics_path:
  /debug/metrics}` block to the spec** (this review) so the scrape target is correct.
- **F-C (review): the Gatus cert-expiry condition claimed earlier does NOT exist.** `add_endpoint` (gatus.py:120)
  takes no conditions arg and `_build_endpoint_yaml` hardcodes `["[STATUS] == 200"]` (gatus.py:106) — no
  `[CERTIFICATE_EXPIRATION]` is emittable via the registrar. Cert renewal is Traefik's job (auto-renews before
  expiry), so the risk is low, but the plan must NOT claim a cert-expiry alert exists. Residual R5: if cert-expiry
  monitoring is wanted, add a manual Gatus condition post-deploy.
- **⚠️ FINDING F4 (M3 — paper backup).** The backrest registrar hardcodes `paths=[f"/opt/{name}/data"]`
  (`infrastructure.py:774`) → a `zitadel-data` plan pointed at `/opt/zitadel/data`, which **does not exist**
  (spec `volumes: []`, `specs/services/zitadel.yaml:66`; Zitadel's container is stateless). The **real**
  persistence is the `zitadel` **DB on `postgres-main`**, covered by the **postgres-main-level Backrest plan** —
  exactly the pattern `specs/services/site-provisioner.yaml:9` documents ("backups handled at postgres-main
  level via existing Backrest plans"). **DR relies on the postgres-main backup, not on `zitadel-data`.**
- **⚠️ F-E (review): "the postgres-main backup covers the new `zitadel` DB" is asserted, not grounded.** If the
  postgres-main Backrest plan is per-DB `pg_dump` (an explicit DB list) rather than a whole-cluster/data-dir
  snapshot, the newly-created `zitadel` DB is **silently outside the backup set until explicitly added** —
  unrecoverable while the operator believes DR is covered. This is the real DR gap. **Named deploy step (S-DR,
  before Gate 2 sign-off): read the postgres-main Backrest plan's actual DB list; if `zitadel` is absent, ADD it.**
- **RPO/RTO:** derived from that plan's schedule/retention — read live at deploy from the Backrest instance on vps1
  (`infra/vps1/backrest/compose.yaml` mounts `/backup-postgres`; the schedule lives in Backrest's runtime state,
  not a repo file). Residual R3. Restore = restore the `zitadel` DB from that plan; the masterkey (remote `.env`,
  under the box `.env` backup discipline) must be preserved to decrypt it — losing it makes a DB restore
  undecryptable (ties to F1).

## Phase 8 — First-days posture

- **Watchdog:** stays **off** (`specs/services/zitadel.yaml:72-73`) — a third-party image can't run the
  product-aware sidecar; do not flip it.
- **Alerts expected in the first hours (NOT rollback triggers):** ContainerDown / probe-fail until DNS
  propagates + the cert issues + init finishes; a cert-pending window. Once `/debug/ready` → 200 and Gatus
  greens, these should clear.
- **Rollback decision rule:** if `/debug/ready` never reaches 200 **after** the acme log shows a cert issued
  **and** `docker inspect` confirms `DATABASE_URL` present (i.e. not a DNS/cert/env red herring), the deploy is
  genuinely broken → S-RB (operator decides, first-deploy only). A first-hours ContainerDown alone is **not** a
  rollback trigger.
- **First-week review hook:** confirm the en/tr login switch, a real OIDC login from one RP (Epic-2 handoff),
  and that no masterkey re-mint occurred (F1 invariant held).

---

## Context Ledger

Authored from: `specs/services/zitadel.yaml` (the spec) · `docs/reference/zitadel.md` (the verification
reference) · `src/fabrik/orchestrator/deployer_ssh.py` (`_generate_docker_compose` Phase-0 emitter :882;
`inject_env` merge :234-239; `_is_placeholder` :593) · `src/fabrik/orchestrator/infrastructure.py`
(DATABASE_URL inject :588; backrest paths :774) · `src/fabrik/orchestrator/__init__.py` (secret resolution
:301-325) · `src/fabrik/orchestrator/secrets.py` (generate_secret :12-22, resolution :77-101) ·
`scripts/vps-autoheal.sh` (:3-8) · live: `fabrik plan` output, `dig auth.ocoron.com`, `free -h`/`docker ps` on
vps1 · `specs/services/site-provisioner.yaml:9` (DB-only backup precedent). Class definitions: A1/A5/B1/B2/B3/M2/M3
per `fabrik-deploy-plan.md:11-13`.

## File Scope (owned paths — what `/fabrik-deploy` will mutate)

- Remote vps1: `/opt/zitadel/compose.yaml`, `/opt/zitadel/.env` (minted secrets + injected DATABASE_URL/GLITCHTIP_DSN),
  the running `zitadel` container.
- `postgres-main`: new `zitadel` database + role.
- Registrar side-effects: Gatus endpoint, Prometheus target, GlitchTip project, Grafana, a `zitadel-data`
  Backrest plan (paper — F4), Traefik route for `auth.ocoron.com`.
- DNS: `auth.ocoron.com A` record — auto-created by `fabrik apply`'s `_provision_dns` via site-provisioner (S1 verifies).
- This plan file.

## Behavior Contract (one row per user-observable post-deploy behavior)

| # | Given | When | Then |
|---|---|---|---|
| B1 | the deploy ran | `curl https://auth.ocoron.com/debug/ready` | HTTP 200 (DB-checked readiness — pool to postgres-main live) |
| B2 | the deploy ran | open `https://auth.ocoron.com` in a browser | the branded login UI loads over a valid TLS cert |
| B3 | the deploy ran | `curl …/.well-known/openid-configuration \| jq .backchannel_logout_supported` | `true` (OIDC issuer live) |
| B4 | admin credentials retrieved (S4: `ZITADEL_ADMIN_PASSWORD` + `Aa1!`) | sign in as `admin@ocoron.com` | login succeeds (complexity policy satisfied), password-change is required |
| B5 | the deploy ran | a Zitadel verification email is triggered | it is delivered through Resend |
| B6 | `postgres-main` is unreachable | `curl …/debug/ready` | non-200 (Gatus flags it) |
| B7 | metrics enabled | Prometheus scrapes `/debug/metrics` | series present; `docker inspect` shows `GLITCHTIP_DSN` |
| B8 | a first-deploy failure with no data | run S-RB | route stops answering, `zitadel` DB dropped, re-deployable |

## Evidence

```
$ dig +short auth.ocoron.com A          →  (empty NOW — fabrik apply's _provision_dns auto-creates it at deploy)
$ dig +short provision.vps1.ocoron.com A →  172.93.160.197   (vps1 A-record target)

# S1 pre-flight — clean-slate assertion (re-probed 2026-08-29, NOT recalled): DB absent, container absent, .env survivor
$ ssh vps "sudo docker exec postgres-main psql -U postgres -tAc \"SELECT count(*) FROM pg_database WHERE datname='zitadel'\""  →  0   (DB ABSENT — db_before_boot will create it fresh)
$ ssh vps "sudo docker ps -aq --filter name=^zitadel | wc -l"  →  0   (no container)
$ ssh vps "sudo test -f /opt/zitadel/.env && echo SURVIVES"    →  SURVIVES   (harmless — RUN 4 secrets overlay it; the postgres rollback is a no-op so the DB was dropped out-of-band, not by rollback)
$ ssh vps "free -h | grep Mem"          →  11Gi total · 7.5Gi available   (fits 1G limit)
$ ssh vps "sudo docker ps -q | wc -l"   →  31 containers
$ fabrik plan specs/services/zitadel.yaml → 6 registrars RUN (postgres/gatus/backrest/glitchtip/grafana/prometheus)
$ grep -qc RESEND_API_KEY /opt/fabrik/.env  →  present   (from_env source present)
$ git log origin/master..HEAD --oneline →  (empty — spec/doc/emitter all pushed)

# D1-fix grounding (#6): env_file VALUE interpolation on the box (Compose 2.40.3) — the fix rides on this
$ docker compose version                →  Docker Compose version 2.40.3   (≥ 2.24, env_file interpolation default-on)
$ printf 'DATABASE_URL=postgresql://USER:PW@postgres-main:5432/zitadel\nZITADEL_DATABASE_POSTGRES_DSN=[dollar]{DATABASE_URL}\n' > .env
$ docker compose config   # (busybox svc, env_file: .env)
      ZITADEL_DATABASE_POSTGRES_DSN: postgresql://USER:PW@postgres-main:5432/zitadel   # RESOLVED, not the literal [dollar]{…}
```
Grounding for F1 (masterkey re-mint): `__init__.py:301-303` (generate → load_all, no remote read) vs
`:306-320` (from_env's remote read) + `deployer_ssh.py:655` (unconditional overlay, no placeholder guard). D1
(deploy-order): `__init__.py:170` (deploy) → `:180` (registrar) → `:216` (rollback-before-registrar) +
Zitadel [#5810]/[#11942] (no init retry). F4: `infrastructure.py:774` vs `specs/services/zitadel.yaml:66`.

## Self-audit

**Verified (grounded at path:line / live probe, re-opened author-blind + 2 native Opus finders):** surface
inference; target headroom; all 6 registrars via `fabrik plan`; every `${VAR}` source; the masterkey re-mint
path (F1) + that plain `redeploy` is the only safe update path (D3); the placeholder guard is inert here (F2);
RESEND from_env present (F3); autoheal N/A via its own predicate (Phase 5); the backrest paper-backup (F4); DNS
absent (S1). **The review CORRECTED:** F-A/F-B (Gatus/Prometheus probed the wrong paths → spec fix), F-C (no
cert-expiry condition exists), F-D (readiness ≠ write proof), D2 (S5 grepped the wrong var), D4 (LOG_LEVEL drift).

**D1 — RESOLVED (was blocking):** the deploy-order/DB-at-boot contradiction is fixed by the opt-in
`deploy.db_before_boot` machinery change (commit a47d5e20; `__init__.py::_pre_provision_db_for_boot` at step 2b
seeds `DATABASE_URL` into the initial `.env` before first boot) + the documented manual-bootstrap fallback (see
✅ RESOLVED FINDING D1). Grounded: step 2b runs before `deployer.deploy` (`__init__.py:161`<`:170`); the
post-deploy registrar is idempotent (no password on existing DB → `inject_env` skipped, `infrastructure.py:583`);
db_name parity (`__init__.py:311` == `infrastructure.py:525`); opt-in early-return leaves other services
byte-identical; red-first tests `tests/orchestrator/test_pre_provision_db.py`. The fleet-wide auto-detection
follow-up stays filed at `docs/STRATEGIC_BACKLOG.md`.

**Residual (self-service at deploy — exact probe/default stated, no deferred question):**
- **R1 (F1):** after the (bootstrapped) first init completes, capture the minted `ZITADEL_MASTERKEY` and never
  run `apply`/`redeploy --refresh-infra` again without pinning it first (S-INV). Machinery gap → backlog.
- **R3:** RPO/RTO numbers = the postgres-main Backrest plan's live schedule/retention (S-DR reads it at deploy).
- **R4 (RESOLVED):** the `zitadel-data` paper-backup plan is left **inert** — harmless, DR uses the postgres-main
  backup (F-E / S-DR). No suppression needed; no decision deferred.
- **R5:** cert-expiry monitoring is not auto-emitted (F-C) — add a manual Gatus condition post-deploy if wanted;
  Traefik auto-renewal makes this low-priority.

With D1 resolved and every finding fixed, the plan is convergence-ready — the re-review's md5-verified no-op
earns `CONVERGED`, handing to Gate 2.

## Coverage Checklist

Classes derived from the deploy-plan-review canonical checklist + the four standing recurrence classes, with
the rubric injected via `python scripts/review_rubric.py --changed <plan + specs/services/zitadel.yaml + the
orchestrator/deployer/infrastructure paths>` (run at Phase 1 of both review rounds). Every class swept to a
verdict; two adversarial rounds (2 native Opus finders round 1, 1 finder round 2) + author-blind grounding.

| # | Class | Verdict | Evidence |
|---|---|---|---|
| 1 | Secrets flow | FIXED | F1 re-mint invariant grounded; `db_before_boot` DSN coexists with masterkey; plain `redeploy` safe. **S3-halt fix:** the alphanumeric `secrets.generate` admin password failed Zitadel's HasSymbol policy → `ZITADEL_FIRSTINSTANCE_ORG_HUMAN_PASSWORD: "${ZITADEL_ADMIN_PASSWORD}Aa1!"` guarantees complexity (interpolation verified on the box) |
| 2 | Env/config completeness | FIXED | D4 LOG_LEVEL drift corrected; every `${VAR}` traced; DATABASE_URL seeded + env_file interpolation verified live (`docker compose config`, Compose 2.40.3) |
| 3 | Staged-infra validity | CLEAN | DNS auto-provisioned by `fabrik apply` (`_provision_dns` → site-provisioner; S1 verifies, NOT operator-gated), 6-registrar `fabrik plan` preview, cert story |
| 4 | Runbook ordering + timing | FIXED | D1 resolved (`deploy.db_before_boot` pre-provision at step 2b `__init__.py:161`<`:170`); D2 (S5 greps the resolved DSN); stable `S`-ids; S-RB + #4b recovery |
| 5 | Healing / rollout | CLEAN — N/A-vps | `health.disabled`→no healthcheck→`vps-autoheal.sh:53` (unhealthy-only) never acts; no window bracket needed |
| 6 | Battery completeness | FIXED | F-D readiness≠write-proof corrected; write path = Console user-create; ACME/cert diag before TLS |
| 7 | Monitoring + backup/DR truth | FIXED | F-A/F-B fixed at the spec (`health.path`/`monitoring.metrics_path`); F-C cert-expiry dropped; F-E → S-DR backup-coverage step |
| 8 | Standing recurrence sweep | FIXED | #3 db_name parity (name-first, `__init__.py:311`==`infrastructure.py:413`); #4a orphan-DB tracked; #4b re-run recovery; #6 interpolation grounded; opt-in = byte-identical for other services |

## BLOCKED: none

**Next command:** /fabrik-deploy-plan-review docs/development/plans/2026-08-28-plan-deploy-zitadel.md — adversarially converge this plan before Gate 2.

## Deploy Ledger

— RUN 1 2026-08-28T21:47:07Z
— ⛔ BLOCKED S3 2026-08-28T21:53:43Z start-from-init setup migration 03_default_instance failed: Errors.User.PasswordComplexityPolicy.HasSymbol — the secrets.generate ZITADEL_ADMIN_PASSWORD is 32 alphanumeric chars (NO symbol), but Zitadel's default password-complexity policy requires a symbol → the first-instance admin bootstrap is rejected → container crash-loops. db_before_boot + DNS worked (logs: "database … skipping creation"). Rollback taken: docker compose down + removed; connections terminated; zitadel DB dropped (empty — setup failed pre-data, masterkey encrypted nothing). Residue (harmless): the auth.ocoron.com A record + /opt/zitadel/.env (old secrets) persist; a re-deploy overlays them. [ADJUDICATED 2026-08-28 — closed by this re-convergence: admin-password complexity fix]

— RUN 2 2026-08-28T22:12:12Z
— ⛔ BLOCKED S3 2026-08-28T22:19:58Z RUN 2 — the admin-password fix WORKED (start-from-init cleared all migrations incl. 03_default_instance; container ran, /debug/ready→200, /debug/healthz→200, server listening :8080), BUT `fabrik apply` returned rc=1: `docker compose up -d --wait` REQUIRES a healthcheck, and with health.disabled (scratch image — no in-container shell/curl for one) it exits 1 ("container zitadel has no healthcheck configured"), so deploy() aborts at deployer_ssh.py:515 BEFORE the post-deploy registrars (:173) → gatus/prometheus/glitchtip/backrest/grafana never provisioned → false-failure + incomplete deploy. THIRD deploy-machinery defect (after D1 ordering + password-complexity). Rollback: container down+removed, connections terminated, zitadel DB dropped (RUN-2 instance had only default org/admin, no real data). Fix needed (deployer): for health.disabled services use `docker compose up -d` (NOT --wait, which needs a healthcheck) at deployer_ssh.py:515 (_deploy_docker) AND :239 (inject_env), + an external readiness poll. Then re-converge + clean re-deploy. [ADJUDICATED 2026-08-28 — closed by the deployer fix 43ced0d3: _compose_up uses `up -d` (no --wait) + an external readiness poll for health.disabled services; 5 red-first tests, 122 deployer tests green]

— RUN 3 2026-08-28T22:49:58Z
— ⛔ BLOCKED verify 2026-08-28T23:01:27Z RUN 3 — the up--wait fix WORKED: deploy() reached the container (up -d + readiness poll passed, restarts=0) AND ran ALL post-deploy registrars (GLITCHTIP_DSN injected, DB DSN resolved, /debug/ready→200 in-network) — then FAILED at the deployer's verify. Root cause (ONE machinery finding, corrected 2026-08-29): DeploymentVerifier.verify ran an in-band HTTPS probe of the DOMAIN even for health.disabled services; on the DNS-propagation/ACME timing window it raised VerificationError, whose rollback deleted the container + DB + the just-created DNS record. The two findings originally logged here COLLAPSE into this one: (4) VERIFIER-DNS-TIMING was the real defect; (5) "DNS-PROVIDER-MISROUTE" was a MISDIAGNOSIS — _provision_dns's line-582 comment says "Namecheap first" but the code calls DNSClient.add_subdomain → POST /api/cloudflare/dns/{domain}/subdomain, the CLOUDFLARE route via site-provisioner (src/fabrik/drivers/dns.py:294-316; hub .env has SITE_PROVISIONER_CONTAINER + SITE_PROVISIONER_INTERNAL_URL so DNSClient reaches it over SSH). The record WAS created correctly in the Cloudflare zone and was DELETED by the verify-failure rollback (ctx.add_resource("dns",…), __init__.py:591 → DNS is a rolled-back resource); auth.ocoron.com reading empty via 1.1.1.1 afterward was that rollback artifact, not a misroute. Rollback: container down+removed, connections terminated, zitadel DB dropped (default data only). Findings 1-3 (db_before_boot, Aa1! password, up--wait) all FIXED + proven LIVE this run. [ADJUDICATED 2026-08-29 — closed by the verifier fix 1c90bf81: verify() skips the in-band probe when health.disabled is set (mirroring _compose_up); liveness owned by external Gatus + the deployer's readiness poll; 2 red-on-revert tests, gate green]
