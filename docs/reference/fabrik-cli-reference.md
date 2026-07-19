# Fabrik CLI Reference

**Last Updated:** 2026-07-19
**Source:** `src/fabrik/cli.py`
**Live help:** `fabrik --help` (run from any directory)

The `fabrik` CLI is the single entry point for the **4-stage Fabrik lifecycle**: Intent → Scaffolding → Deploy → Verify. It deploys across the 3-host fleet (vps1 hub + vps2/vps3 spokes; route with `--target-vps`, shared infra hub-only) via **SSH + Docker Compose** — no Coolify API layer, no PaaS, no Kubernetes.

This page documents **every command currently in `cli.py`** with what it does, when to use it, and the line in the source where it's defined. Commands are grouped by lifecycle stage rather than alphabetically, because that's how you'll actually invoke them.

---

## Stage 1 — Intent

Capture the "why" of a project before any code or scaffolding exists. Optional but recommended.

### `fabrik preplan new <slug>` — author a preplan

**Purpose:** Create `docs/preplans/<YYYY-MM-DD>-<slug>.md` from a 9-section template so the intent of the project is captured **before** scaffolding.

```bash
fabrik preplan new citation-verifier
fabrik preplan new my-feature --date 2026-05-30   # override the date stamp
```

**Why it matters:** When `fabrik scaffold --from-preplan <file>` later ingests this markdown, it pre-fills the project's `--type`, `shape:` block, domain and secrets, copies the preplan into `<project>/docs/preplan.md`, and **layers a `Preplan:` reference line into all 4 AI guardrail files** (AGENTS.md, CLAUDE.md, AGENTS-compact.md, .windsurfrules) so every downstream agent reads the same captured intent.

**Skipping is allowed.** Scaffold without a preplan works fine — you just lose the layered-intent context for AI agents.

---

## Stage 2 — Scaffolding

Produce a working project directory with template-driven structure, governance files, spec, and CI.

### `fabrik scaffold` — create a new project

**Purpose:** Materialize `/opt/<name>/` with everything needed to start coding. Reads `templates/<type>/defaults.yaml` for shape flags; emits `project.yaml`, `specs/services/<name>.yaml`, `.env.example`, README, tests, CI workflow.

```bash
fabrik scaffold <name> [--type <type>] [-d <description>] \
                       [--db] [--no-spec] [--from-preplan <preplan.md>]
```

| Flag | Purpose |
|---|---|
| `--type` / `-t` | One of `python-api` (default), `node-api`, `saas-skeleton`, `static-site`, `docusaurus`, `file-api`, `file-worker`, `chrome-extension`, `desktop-app`, `mobile-app`, `python-api-gpu`. (`wordpress` is still accepted as a type but scaffolding redirects to the standalone `/opt/wpf` `wpf` CLI.) |
| `--db` | Provision a local Postgres DB for WSL dev + add `DATABASE_URL` to `.env.local`. |
| `--no-spec` | Skip emitting `/opt/fabrik/specs/services/<name>.yaml` (rare). |
| `--from-preplan` | Ingest a preplan (see `fabrik preplan new`); pre-fills type/shape/domain/secrets. |
| `--github-create` / `--no-github` | Create the GitHub repo + push on scaffold (auto-enables for build-context types); `--no-github` opts out. |

```bash
fabrik scaffold my-api --type python-api -d "Customer API" --db
fabrik scaffold notes --from-preplan docs/preplans/2026-05-30-notes.md
# WordPress: scaffolding moved to /opt/wpf — use the `wpf` CLI (e.g. `wpf new blog`)
```

### `fabrik new` — alias **(hidden)**

**Purpose:** Backward-compatibility alias for `scaffold`. Not shown in `--help`. New code should use `fabrik scaffold`.

### `fabrik templates` — list scaffold templates

**Purpose:** Enumerate available templates. Mirrors what `--type` accepts.

```bash
fabrik templates
```

### `fabrik validate-deploy` — local readiness check

**Purpose:** Pre-flight a scaffolded project before deploy. Runs 5 local checks: template match, `.env.example`, Dockerfile, `/health` endpoint presence, spec pre-existence. **Warnings only — always exits 0.**

```bash
fabrik validate-deploy /opt/my-api --type python-api
```

### `fabrik validate` — standards compliance

**Purpose:** Verify an existing project conforms to current Fabrik scaffold standards (required files, structure, conventions).

```bash
fabrik validate /opt/my-api --type python-api
```

### `fabrik fix` — add missing required files

**Purpose:** Complementary to `validate`. Adds the missing required files (governance, `.gitignore` entries, etc.) without touching content. Always preview with `--dry-run` first.

```bash
fabrik fix /opt/my-api --dry-run
fabrik fix /opt/my-api
```

---

## Stage 3 — Plan & Deploy

### `fabrik plan <spec_path>` — dry-run preview

**Purpose:** Show exactly what `fabrik apply` would do without executing anything. Lists which of the 7 registrars will fire per the `shape:` block, with skip reasons.

```bash
fabrik plan specs/services/my-api.yaml
fabrik plan specs/services/my-api.yaml -s API_KEY=preview
```

### `fabrik apply` — **the primary deploy command**

**Purpose:** Run the full orchestrator pipeline end-to-end: validate spec → secrets resolution → DNS provisioning → SSH deploy (SCP compose.yaml + .env → `docker compose up -d --wait`) → 7 registrars based on `shape:` → health verification → rollback on failure.

```bash
fabrik apply [<spec_path>] [--dry-run] [--skip-dns] [--skip-deploy] \
             [-s KEY=VALUE] [--legacy] [--yes] [--keep-on-failure] \
             [--target-vps vps1|vps2|vps3]
```

| Flag | Purpose |
|---|---|
| `<spec_path>` | Path to `specs/services/<name>.yaml`. If omitted, resolves from `project.yaml` in cwd. |
| `--dry-run` | Simulate every mutation without executing. |
| `--skip-dns` | Don't touch DNS records. Use for re-runs where DNS is already correct. |
| `--skip-health-check` | Skip the post-deploy health verification step. |
| `--skip-deploy` | Validate + prepare, but don't push the container. Diagnostic. |
| `-s KEY=VALUE` | Override a single secret on the command line (highest precedence). |
| `--legacy` | Force the deprecated Coolify-API path (render-only; not for new deploys). |
| `--yes` / `-y` | Skip confirmation prompts. |
| `--keep-on-failure` | Skip auto-rollback so the failed container + .env stay on the VPS for inspection. Use when iterating on a broken deploy. |
| `--target-vps` | Which fleet host to deploy the container to: `vps1` (hub, default), `vps2`, `vps3`. Only the app container moves; shared infra (Postgres, monitoring, Authelia) stays on vps1. |

**Multi-host target resolution** (`--target-vps`, highest to lowest): CLI `--target-vps` flag > state file `.fabrik/state/<id>.json::target_vps` > spec's `target_vps:` field > `vps1`. Same flag + order on `redeploy` and `destroy`. `plan` has no flag — it reads the spec's `target_vps:` directly.

**Secret loading precedence** (highest to lowest):
1. `-s KEY=VALUE` command-line flag (injected into `os.environ` before SecretsManager loads)
2. Project `.env` at `/opt/<project>/.env` on the VPS (read-merged to preserve registrar-injected vars)
3. Fabrik `.env` at `/opt/fabrik/.env`
4. Process environment

```bash
fabrik apply specs/services/my-api.yaml
fabrik apply specs/services/my-api.yaml --dry-run
fabrik apply specs/services/my-api.yaml -s API_KEY=override -y
fabrik apply specs/services/my-api.yaml --keep-on-failure   # iterate on a broken deploy
```


### `fabrik redeploy <app>` — code-only update

**Purpose:** Rebuild and restart a service without re-running registrars. The deployer SSHes in, runs `git pull` (git-sourced apps), `docker compose build`, `docker compose up -d --wait`. **Health-check rollback** is built in for git-sourced apps: if the new container fails to come up healthy, the deployer auto-reverts to the last-known-good commit and rebuilds.

```bash
fabrik redeploy <app> [--force] [--refresh-infra --spec <path>] [--dry-run] \
                [--target-vps vps1|vps2|vps3]
```

| Flag | Purpose |
|---|---|
| `--force` / `-f` | Add `--no-cache` to build (git) or `--force-recreate` to `up` (non-git). |
| `--refresh-infra --spec <path>` | Re-run all 7 registrars against the existing container without rebuilding. Use when `shape:` flags change but code hasn't. |
| `--dry-run` | Simulate (`--refresh-infra` path only — standard redeploy ignores this flag). |
| `--target-vps` | Which fleet host the app lives on: `vps1` (default), `vps2`, `vps3`. Resolution: CLI flag > state file `.fabrik/state/<app>.json::target_vps` > `vps1`. |

```bash
fabrik redeploy my-api
fabrik redeploy my-api --force
fabrik redeploy --refresh-infra --spec specs/services/my-api.yaml
```

**Important:** `redeploy` does **not** touch the `.env` file and does **not** re-run registrars. For .env updates or registrar re-runs, use `fabrik apply`.

### `fabrik destroy <spec_path>` — tear down a deployment

**Purpose:** Reverse the full provisioner chain. Tears down all 7 registrars in destroy order (meilisearch → authelia → glitchtip → backrest → gatus → postgres (reverse of apply order)), then `docker compose down`, `rm -rf /opt/<name>`, `docker image prune`, then DNS.

```bash
fabrik destroy <spec_path> [--yes] [--keep-dns] [--drop-data] \
               [--partial <registrar>] [--use-state] [--dry-run] \
               [--target-vps vps1|vps2|vps3]
```

| Flag | Purpose |
|---|---|
| `--yes` / `-y` | Skip confirmation. |
| `--keep-dns` | Don't remove the DNS A record. Useful for migration. |
| `--drop-data` | Actually drop the Postgres DB, FLUSHDB Redis, delete MeiliSearch index, `down -v`. **Without this flag, data-bearing resources are preserved.** |
| `--partial <reg>` | Surgical un-registration. Repeatable: `--partial gatus --partial backrest`. |
| `--use-state` | Tear down using the recorded `.fabrik/state/<id>.json` rather than re-deriving from the current spec. Use when the spec has drifted between apply and destroy. State is archived after a successful run. |
| `--dry-run` | Print what would happen. |
| `--target-vps` | Which fleet host to tear the app down from: `vps1` (default), `vps2`, `vps3`. Resolution: CLI flag > state file `.fabrik/state/<id>.json::target_vps` > spec's `target_vps:` > `vps1`. |

```bash
fabrik destroy specs/services/my-api.yaml --dry-run
fabrik destroy specs/services/my-api.yaml -y
fabrik destroy specs/services/my-api.yaml --drop-data -y         # also drops the DB
fabrik destroy specs/services/my-api.yaml --partial gatus -y     # surgical
fabrik destroy specs/services/my-api.yaml --use-state -y         # tear down from state file
```

---

## Stage 4 — Verify & Audit

### `fabrik verify <domain>` — postcondition check

**Purpose:** Probe a live deployment against a declarative postcondition spec at `specs/verification/<type>.yaml`. Returns a check-by-check pass/fail report.

```bash
fabrik verify <domain> [--spec <type>] [--app-name <name>] [--no-rollback]
```

| Flag | Purpose |
|---|---|
| `--spec` / `-s` | Which verification spec: `deploy` (default), `dns`, `registrars`. |
| `--app-name` / `-a` | App name (defaults to the domain prefix). |
| `--no-rollback` | Don't auto-rollback the deploy on verification failure. |

```bash
fabrik verify my-api.vps1.ocoron.com
fabrik verify my-api.vps1.ocoron.com --spec registrars
fabrik verify my-api.vps1.ocoron.com --no-rollback
```

### `fabrik audit-registrars` — drift detection

**Purpose:** Compare each spec's shape-resolved registrars against live VPS state. Per registrar per spec it returns one of:

- **`present`** — live matches what shape says
- **`missing`** — shape says yes, live says no
- **`drift`** — both present but the shape differs (orphan resource or ghost registry entry)
- **`n/a`** — shape says skip
- **`override`** — `infra: { <reg>: false }` opted out
- **`unknown`** — couldn't be verified

```bash
fabrik audit-registrars                                     # walk all specs
fabrik audit-registrars --spec specs/services/my-api.yaml   # single spec
fabrik audit-registrars --json | jq .                       # machine-readable
```

**Drift cases caught** (postgres example, `audit.py:186-190`):

| Live DB | Registry | Verdict |
|---|---|---|
| present | present | `present` |
| present | missing | `drift` — orphan DB (created outside fabrik) |
| missing | present | `drift` — ghost entry |
| missing | missing | `missing` (spec said it should exist) |

> **Not yet automated.** `AGENTS.md:73` documents an hourly WSL cron pushing metrics to Prometheus + Alertmanager → Telegram on drift as the *target* — it's not currently in the local crontab. Run manually for now.

### `fabrik reconcile-all` — sweep the fleet

**Purpose:** Re-run `InfrastructureProvisioner` against every spec to converge live state back to what the specs say. Use after `audit-registrars` flags drift.

```bash
fabrik reconcile-all [--yes] [--filter <substr>]
fabrik reconcile-all --filter my-api        # dry-run, scoped to one
fabrik reconcile-all --yes                  # apply across fleet
```

---

## Status & Logs

### `fabrik status <spec_path>` — current state

**Purpose:** Read the live container state + the local `.fabrik/state/<id>.json` and report status.

```bash
fabrik status specs/services/my-api.yaml
```

### `fabrik logs <spec_path>` — centralized logs (Loki)

**Purpose:** Query Loki for centralized container logs.

```bash
fabrik logs [service] [-n/--tail N] [--since 1h] [--follow]
fabrik logs --local [-f] [--service <name>]      # local dev stack via docker compose logs
```

### `fabrik app-logs <spec_path>` — live container tail

**Purpose:** Tail the live container's logs via SSH `docker logs`.

```bash
fabrik app-logs <spec_path> [-n LINES] [-f]
```

---

## Domain management

All domain/DNS operations go through the site-provisioner microservice at `provision.vps1.ocoron.com`.

| Command | Purpose |
|---|---|
| `fabrik domain check <domain>` | Availability check across registrars. |
| `fabrik domain buy <domain> [--years N] [-y]` | Register a new domain via Namecheap. |
| `fabrik domain provision <domain> [--ip ..] [--subdomain ..] [--no-dnssec] [--no-cache] [--no-shield] [--no-waf] [--setup-google] [--no-bing] [--no-indexnow] [--setup-ga4] [--ga4-account-id ..] [--sitemap-url ..]` | Full DNS/CDN/security/analytics provisioning for a domain. |
| `fabrik domain ready <domain> [--wait]` | Poll DNS + SSL readiness before deploying. |
| `fabrik domain zones` | List all Cloudflare zones. |
| `fabrik domain integrations <domain>` | GA4, GSC, Bing, IndexNow metadata. |
| `fabrik domain sitemap <domain> --sitemap-url <url>` | Regenerate and resubmit a sitemap. |

```bash
fabrik domain check ocoron.com
fabrik domain buy newproject.com --years 2 -y
fabrik domain ready my-api.vps1.ocoron.com --wait
```

---

## Local development

### `fabrik dev` — local dev stack

**Purpose:** Run the project's `compose.dev.yaml` stack locally in WSL via `docker compose up`. Hot-reload + bind mounts; the container has its own system Python (no `.venv` inside).

```bash
fabrik dev [--project <path>] [-d|--detach]
```

```bash
cd /opt/my-api
fabrik dev -d
fabrik logs --local -f
```

Fails clean if `compose.dev.yaml` is missing.

### `fabrik review` — pre-PR review pack

**Purpose:** Bundle `git diff + spec + docs/preplan.md + resolved registrar table` into a single markdown at `.fabrik/review/<YYYY-MM-DD-HHMMSS>.md`. Intended for handoff to a human reviewer or a Claude Code / pool review run.

```bash
fabrik review [--since HEAD~N] [--spec <path>] [--out <file>]
```

```bash
fabrik review                                    # diff since HEAD
fabrik review --since HEAD~3
fabrik review --spec specs/services/api.yaml --out review.md
```


---

## Registry & inventory

### `fabrik projects` — list the registry

**Purpose:** List every project from `data/projects.yaml` with status.

```bash
fabrik projects [--status <status>] [--sync]
```

`--sync` re-runs the project scanner before listing.

### `fabrik scan` — refresh the registry

**Purpose:** Walk `/opt/<*>` and update `data/projects.yaml` + the auto-generated blocks in `docs/BUSINESS_MODEL.md` and `PORTS.md`.

```bash
fabrik scan [--health] [--base <path>]
```

### `fabrik vps-sync` — refresh VPS state docs

**Purpose:** Pull live VPS state and regenerate `docs/infrastructure/vps-status.md`, `docs/infrastructure/vps-urls.md`, and `docs/infrastructure/vps-complete-inventory.md`. **Read-only on the VPS.**

```bash
fabrik vps-sync [--dry-run]
```

---

## AI & content

```bash
fabrik ai usage [--month YYYY-MM] [--project <name>]
fabrik seo site-register <site-id> [...]
fabrik seo job-create <site-id> [...]
fabrik seo job-run <job-id> [--wait]
fabrik seo briefs-list <site-id> [--status <status>]
```

> `fabrik ai generate` / `fabrik ai revise` were removed (2026-06-16); `usage` is the only `ai` subcommand. The `content` group remains registered but has no subcommands (`content publish` removed with `content_publisher.py`).

All AI/SEO subcommands: `ai usage` · `seo site-register` · `seo job-create` · `seo job-run` · `seo briefs-list`.

---

## GPU rental — `fabrik gpu`

Rent/manage GPU compute across RunPod, Modal, and Vast (auto-selection by workload/utilization; cost guards via `--max-cost` + `MAX_DAILY_GPU_COST`). Full runbook: `docs/operations/gpu-rent.md`.

```bash
fabrik gpu rent --workload <desc> [--provider auto|runpod|modal|vast] [--utilization F] [--needs-checkpointing] [--needs-serverless] [--max-lifetime H] [--max-cost USD] [--dry-run] [...]
fabrik gpu list | status | destroy | pause | resume | history [--lines N] | compare
fabrik gpu reconcile [--provider all|runpod|modal|vast] [--auto-destroy]
```

## DR / Vultr fleet — `fabrik vultr`

Disposable-instance provisioning + DR drills (see `docs/operations/disaster-recovery.md`).

```bash
fabrik vultr list | status | cost | cleanup
fabrik vultr provision <name>        # real spoke provisioning
fabrik vultr destroy <name>
fabrik vultr drill hub|spoke|spoke-restore   # disposable DR drill
fabrik vultr drill-history
fabrik vultr reconcile
```

## Portability

### `fabrik export` — package a project for transport

**Purpose:** Bundle a project (and optionally its data) into a transportable archive for migration to another host.

```bash
fabrik export [--output <path>] [--include-data] [--skip-remote]
```

### `fabrik import` — restore an exported bundle

**Purpose:** Restore a previously-exported bundle.

```bash
fabrik import <bundle.tar.gz> [--real-run]
```

`--real-run` actually mutates; without it, dry-run only.

---

## WordPress — moved to a separate CLI

`fabrik wp ...` no longer exists in the Fabrik CLI. WordPress operations live in the standalone `/opt/wpf/` factory and use its own CLI:

```bash
wpf wp plan <site-id>
wpf wp apply <site-id>
wpf wp verify <site-id>
```

(Cache flushing is internal to `wpf wp apply`/`verify`, not a standalone `wpf wp flush` subcommand. The full `wp` group is `plan | apply | verify | create | preview | promote`.)

See `/opt/wpf/AGENTS.md` and `/opt/wpf/docs/DEPLOYMENT.md` for the WP-specific architecture (golden Docker image, deployed via SSH + Docker Compose as a 4-container per-site stack — e.g. the live `ocoron-com-{wordpress,db,redis,nginx,backup}` containers; Coolify was decommissioned 2026-05-30). WordPress is **out of scope for Fabrik planning** — `/opt/wpf` is the only source of truth (the former `domain-modules/wordpress.md` was deleted 2026-07-13 as fully dead: the scaffold and deploy paths both hard-error).

---

## Command → Module map

| Command | Implementation |
|---|---|
| `scaffold`, `new` | `src/fabrik/scaffold.py` |
| `preplan` | `src/fabrik/preplan.py` |
| `apply` | `orchestrator/DeploymentOrchestrator.deploy()` (default) — legacy `--legacy` path: `deploy.py::deploy_to_coolify` |
| `deploy` | `deploy_router.route_deploy()` — project-based dispatch over orchestrator |
| `redeploy` | `orchestrator/deployer_ssh.SSHDeployer.redeploy()` |
| `destroy` | `orchestrator/destroyer.destroy_deployment()` (default) or `destroy_from_state()` (`--use-state`) |
| `verify` | `verify.py::PostconditionChecker` |
| `audit-registrars` | `audit.py::audit_all` |
| `reconcile-all` | `orchestrator/reconcile.py` (re-uses `InfrastructureProvisioner`) |
| `validate-deploy`, `validate`, `fix` | `deploy_validator.py` + `scaffold.py` |
| `vps-sync` | `scripts/vps_sync.py` |
| `status`, `logs`, `app-logs` | `cli.py` directly + `drivers/ssh.py` |
| `domain *` | `drivers/dns.py::DNSClient` |
| `dev`, `review`, `import`, `export` | `dev_tools.py` + `portability.py` |
| `ai usage` | `ai/tracker.py::UsageTracker` |
| `seo *` | `seo/` package |

---

## What's intentionally not here

- **`fabrik wp ...`** — moved to `/opt/wpf/` as `wpf wp ...`. See above.
- **Direct Docker / Compose commands** — fabrik shells out internally; you don't need to. For local dev use `fabrik dev`. For VPS inspection use `ssh vps "sudo docker ..."`.
- **Direct registrar driver calls** — registrars fire automatically from `fabrik apply` based on the spec's `shape:` block; manual driver invocation is for scripts only.

---

## Related

- [QUICKSTART.md](../QUICKSTART.md) — 5-minute walkthrough from scaffold to deploy
- [DEPLOYMENT_ARCHITECTURE.md](../DEPLOYMENT_ARCHITECTURE.md) — code-level map of every file on the deploy path
- [operations/deployment.md](../operations/deployment.md) — apply/redeploy/destroy procedures
- [operations/fabrik-lifecycle.md](../operations/fabrik-lifecycle.md) — runtime behavior & data safety per operation
- [reference/orchestrator.md](orchestrator.md) — orchestrator pipeline internals
- [reference/drivers.md](drivers.md) — every external-API client
- [reference/templates.md](templates.md) — all 12 scaffold types
