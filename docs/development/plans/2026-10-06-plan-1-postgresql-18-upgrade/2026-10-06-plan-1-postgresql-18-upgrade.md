# Plan — PostgreSQL 16 → 18 across the fleet: hub branch, runbook and hand-offs ready for the operator's windows

Status: IN-PROGRESS
**Owner:** fleet
Spec: docs/superpowers/specs/2026-10-06-postgresql-18-fleet-upgrade-design.md
Date: 2026-10-06

Built from the CONVERGED spec, approved for planning (D-617) after `/fabrik-spec-review` and the operator-requested Opus 5.5
+ Fable 5.1 consult. Operator ruling D-612, verbatim: *"yes it must be done in all opt projects, wsl, all vps servers and our
rules must be updated in .windsurf/rules"*. Work item W-fd1c7f7a. Each ticket cites the spec section it implements and
restates nothing that section settles.

## What we already agreed

- The goal, personas and approach A (dump/restore into a new volume, the old one kept) — spec § Goal; spec § The delta.
- The hub window, D1 (disk gate, freeze, manifest, dump, swap, restore, diff, glitchtip first, cut-off, restart) — spec § The delta › D1.
- WSL first as the rehearsal, D2, with its KILL clause and 7-day parity bound — spec § The delta › D2.
- The hub repo changes, D3, merged after the hub window except the DR-chain hunk — spec § The delta › D3; D-617.
- The rule packs drafted here and handed to infra, D4 — spec § The delta › D4.
- The project requests, D5; trade-intelligence follows the fleet, D6; brand-identiy-creator's `pg_uuidv7`, D7 — spec § The delta › D5–D7.
- Rejected: pg_upgrade in place, logical replication, a spoke-side cluster — spec § Rejected alternatives.
- Decided HERE, from the grounding (no new operator question):
  - The plan ends at WINDOW READINESS. The WSL window and the hub window are executed by the operator from the runbook
    (T05) behind their own gates (T06 boards them; the hub window is Gate 2, production data). No ticket touches a live host or database.
  - `.windsurf/rules/versions.yaml`, `agents-fabrik.md`, `docs/reference/prebuilt-app-containers.md` and
    `docs/reference/technology-stack-decision-guide.md` are governance-sync triggers (measured below over every File Scope
    path), so — with the packs and `CLAIMS.yaml` — they are infra's: T06 mails infra the drafted edits; no ticket's Touches holds them.
  - PRECONDITION of T01a: infra adds `pgvector_version: "0.8.6"` to `.windsurf/rules/versions.yaml` with `postgres_major`
    still `"16"`, and re-dates the two unmarked `postgres:16-alpine` literals (`.windsurf/rules/core/30-ops.md:320`,
    `.windsurf/rules/core/25-data-postgres.md:23`) as history — one PRE-dispatch mail, sent by the orchestrator at execute
    start. Tag `pgvector/pgvector:0.8.6-pg16` is published (probed below: HTTP 200). T01a waits for the key and T01b for
    the two literals; T02–T05 are not blocked.
  - Of the spec's "29 live docs", only the current-state docs change (T04a, T04b, T03); dated plans, specs, research ledgers,
    retired orchestrator docs, `docs/DECISIONS.md` and `docs/LESSONS_LEARNT.md` are frozen history and are never rewritten.
  - The runbook is a NEW dedicated doc, `docs/operations/postgres-major-upgrade-runbook.md` — no runbook for a Postgres
    major upgrade exists (searched docs/operations, docs/infrastructure, docs/workstation, docs/reference), and it serves
    the next major too.
  - The grounding corrected three spec citations; the runbook cites the corrected lines: the 01:30 cron is
    `scripts/bootstrap/bootstrap-hub.sh:89` (the Backrest plans run 02:00–03:30, `docs/operations/disaster-recovery.md:43`);
    the watchdog sidecar's container-state check is `docs/infrastructure/vps-complete-inventory.md:733` and only one sidecar
    exists today (`:742`); the WSL tunnel command is `scripts/wsl_startup_hook.sh:227`. A spec text fix rides T06's receipt.
  - The runbook adds the archived plan's operator steps the spec left implicit (maintenance notice, alert silence,
    `fabrik audit-registrars`, GlitchTip check, per-service API call, 7-day dump hold) and the WSL writers the spec missed.

## Ticket Board

| Ticket | Title | Depends | Parallel | State | Commit |
|---|---|---|---|---|---|
| T01a | The CI scaffold derives its Postgres images from the version registry | — | ⚡ | ⬜ | |
| T01b | The loose-literal sweep sees the PG18 image shapes | — | ⚡ | ⬜ | |
| T02 | The repo's hub compose files describe the PG18 cluster and exporter | — | ⚡ | ✅ | a93a62b97 |
| T03 | The disaster-recovery chain restores postgres18-data | — | ⚡ | ✅ | ee57ee3dc |
| T04a | The hub's live pins and smaller current-state docs say 18 | — | ⚡ | ✅ | cb46e993c |
| T04b | The two large current-state docs say 18 | — | ⚡ | 🟡 | |
| T05 | The operator runbook for the WSL and hub windows | T02, T03 | ⛓️ | 🟡 | |
| T06 | Integration: rehearsal, hand-offs, gates and the receipt | T01a, T01b, T04a, T04b, T05 | ⛓️ | ⬜ | |

## Merge Order

1. T01a
2. T01b
3. T02
4. T03
5. T04a
6. T04b
7. T05
8. T06

T01a, T01b, T02, T03, T04a and T04b are independent (disjoint Touches). T05 waits for T02 and T03 because the runbook cites their final lines. T06 is last.
T03 is committed on its own branch `fleet-pg18-dr`, cut from master, which infra merges ALONE inside the hub window
(runbook step 8); the fleet branch also merges `fleet-pg18-dr` so T05 reads T03's lines, and everything on the fleet branch
merges after the window (T03's commits are then already on master).
No two Depends-unconnected tickets share a path.

Breadth advisory (`check_ticket_breadth.py`): T01 was split on it (the CI derivation and the `_LOOSE` sweep are two risk
classes) into T01a and T01b. T05 (score 5) is **kept**: it is ONE runbook whose steps share one sequence, one set of
probes and one rollback chain, so a split would put half a window in each ticket.

## Interfaces

- **T02 → T05 — the compose lines the runbook's swap and rollback steps cite.** Seam test: `tests/test_pg18_runbook.py` (T05) asserts the runbook's image and mount strings equal those `infra/vps1/postgres/compose.yaml` holds.
- **T03 → T05 — the DR volume name.** Seam test: `tests/test_pg18_runbook.py` (T05) asserts the runbook's step 8 names the same volume `scripts/bootstrap/bootstrap-config.sh` restores.
- **T01a → infra — the `pgvector_version` key.** Seam: T01a's tests read the live registry, so a missing key fails loudly.

## Constraints Digest

| Rule | Quote | Source |
|---|---|---|
| The registry flip is a fleet DB upgrade | postgres-main's actual major (FLEET STATE, not auto-watched; flip = fleet DB upgrade | .windsurf/rules/versions.yaml:17 |
| Dev, test and CI track the same major | dev, test, and CI run real PostgreSQL too | .windsurf/rules/core/25-data-postgres.md:270 |
| No SQLite stand-in | A test suite that passes on SQLite and fails on Postgres has tested nothing. | .windsurf/rules/core/45-testing-strategy.md:178 |
| Real PostgreSQL in backend tests | Backend tests run against real PostgreSQL. | .windsurf/rules/core/45-testing-strategy.md:223 |
| Watched-fail-first | Watch it fail first, or neuter the change → prove red → restore → re-run green | .windsurf/rules/core/45-testing-strategy.md:200 |
| Native uuidv7 arrives with the newer major | newer PostgreSQL majors ship native `uuidv7()` (probe: `SELECT uuidv7()`); prefer `DEFAULT uuidv7()` at schema level where it exists | .windsurf/rules/core/25-data-postgres.md:163 |
| Probe the live image, never a doc | probe the live truth, never copy a tag from a doc | .windsurf/rules/core/30-ops.md:320 |
| Never hot-patch a container | NEVER hot‑patch a running container | .windsurf/rules/core/30-ops.md:268 |
| Migrations are one-off, never startup | concurrent replicas race the Alembic version table → wedged deploy | .windsurf/rules/core/30-ops.md:436 |
| Backups exist and are restore-verified | Verify restore quarterly on a throwaway database. | .windsurf/rules/core/25-data-postgres.md:332 |
| No host ports for services | No `ports:` section. | .windsurf/rules/core/30-ops.md:148 |
| Stable container names | `container_name: <name>` is mandatory. | .windsurf/rules/core/30-ops.md:150 |
| amd64 pin | `platform: linux/amd64` is mandatory. | .windsurf/rules/core/30-ops.md:151 |
| Runbook steps idempotent | every step must be a no-op when its outcome is already present | .windsurf/rules/core/90-bootstrap-scripts.md:169-170 |
| Probe tools with command -v | Probe with `command -v` | .windsurf/rules/core/90-bootstrap-scripts.md:143 |
| The exporter must actually serve | `exposes_metrics: true` ⇒ the metrics path actually SERVES. | .windsurf/rules/core/30-ops.md:213 |
| CHANGELOG for config/compose changes | Any change to code (`src/`, `scripts/`, `templates/`) or config | .windsurf/rules/core/40-documentation.md:130 |
| Memory limit on every compose service | a memory limit per service is a Fabrik invariant | CLAUDE.md:298 |
| Volumes are data | Volumes are DATA — "dangling" ≠ disposable. | CLAUDE.md:306 |
| Destructive steps dry-run first | destructive script on prod data w/o dry-run | CLAUDE.md:305 |
| uv for Python tooling (T01a, T01b, T04a scripts) | is the mandated Python package manager. Never use raw `pip`, `pip install`, `poetry`, or `pipenv`. | .windsurf/rules/core/10-python.md:22 |
| Aware datetimes in any script touched | `datetime.now(UTC)`, never `datetime.utcnow()` | .windsurf/rules/core/10-python.md:220 |
| Scrape follows the shape flag (T02's exporter) | Prometheus scrapes it when the spec has `shape.exposes_metrics: true` | .windsurf/rules/core/55-observability.md:200 |
| A guard is never the only thing before an irreversible act (T03's DR drill path) | is never the only thing between the agent and an irreversible act. | .windsurf/rules/ai/50-agentic.md:49 |

The hub `postgres-main` keeps its mesh port `10.99.0.1:5432` (`infra/vps1/postgres/compose.yaml:23`) — the spokes reach the
shared cluster through it; T02 changes no port.

## Execution Discipline (binding on /fabrik-execute-plan)

- **Review floor** — every ticket, on the coder's return, runs `/fabrik-review` on its changed surface to a
  coverage-adjudicated exit BEFORE its merge; no ticket merges on a first-pass green. T01a (`src/fabrik/ci_scaffold.py`
  feeds every scaffold's CI) and T03 (the DR chain) take the full `/fabrik-review`; T05 is a production runbook and takes it too.
- **Dispatch policy** — native Claude seats for every fan-out (the pool is OFF, D-181/D-182): `dispatch_headroom.py` then
  `python3 scripts/command_run.py dispatch --seats N` before each fan-out. Coders: Sonnet for T02, T03, T04a, T04b (`simple`),
  T01a (`complex`), T01b (`simple`); Opus for T05 (`native`, design-heavy); T06 is the orchestrator's. Haiku never codes. Seats never read
  `$HOME/.claude*` or any `.env`, never ssh, never touch a live database; a scratch docker rehearsal uses named containers removed after.
- **Precondition gate** — T01a is not dispatched while `.windsurf/rules/versions.yaml` on master lacks `pgvector_version`;
  T01b is not dispatched while `.windsurf/rules/core/30-ops.md:320` or `.windsurf/rules/core/25-data-postgres.md:23` still
  carries an unmarked `postgres:16-alpine` on master.
- **Operator gates** — no ticket executes the WSL window or the hub window; T06 boards both, and the hub window is Gate 2.
- **Parallelism + merge** — T01a, T01b, T02, T03, T04a and T04b fan out concurrently (disjoint Touches), T01a and T01b once their preconditions hold;
  T05 starts when T02 is merged into the fleet branch and T03 is committed on `fleet-pg18-dr` and merged into the fleet branch; every merge happens in the fleet worktree branch in § Merge Order, and the
  results merge/dedupe at T06, which re-runs every ticket's gate on the merged branch.
- **Ids** — every D-row this plan mints uses `python3 scripts/decisions.py --reserve-id .`.

## Behavior Contract

- **Given** `fabrik.version_registry.VERSIONS_FILE` monkeypatched to a registry with `postgres_major: "16"` and `pgvector_version: "0.8.6"`, **When** `ci_files` renders a config with and without `db_extensions=("pgvector",)`, **Then** the workflow and the local script both name `pgvector/pgvector:0.8.6-pg16` and `postgres:16` respectively (src/fabrik/ci_scaffold.py:47; spec § The delta › D3)
- **Given** `VERSIONS_FILE` monkeypatched to a registry with `postgres_major: "18"`, **When** the same configs render, **Then** they name `pgvector/pgvector:0.8.6-pg18` and `postgres:18` (spec § The delta › D3)
- **Given** `VERSIONS_FILE` monkeypatched to a registry lacking `pgvector_version`, **When** `fabrik.ci_scaffold` is reloaded with `importlib.reload`, **Then** the reload succeeds, and **When** `pg_image()` runs for a pgvector config, **Then** it raises `VersionRegistryError` naming `pgvector_version` (src/fabrik/version_registry.py:22)
- **Given** the live `.windsurf/rules/versions.yaml`, **When** it is loaded, **Then** it carries non-empty `postgres_major` and `pgvector_version` (the only test bound to the live registry, so infra's later flip to 18 never reds the others) (spec § The delta › D3)
- **Given** the strings `postgres:18-alpine`, `postgres:18.6-alpine` and `pgvector/pgvector:0.8.6-pg18`, **When** `_LOOSE` searches each, **Then** each matches, the existing `PostgreSQL 16` and `pgvector:pg16` cases still match, and `port 5432` does not (scripts/sysadmin/rules_render_versions.py:36)
- **Given** `infra/vps1/postgres/compose.yaml`, **When** it is parsed, **Then** postgres-main runs `postgres:18.6-alpine`, mounts the external volume `postgres18-data` at `/var/lib/postgresql`, keeps `deploy.resources.limits.memory`, `container_name` and the `fabrik` network, and no service mounts anything at `/var/lib/postgresql/data` (infra/vps1/postgres/compose.yaml:3; spec § The delta › D1)
- **Given** `infra/vps1/monitoring/compose.yaml`, **When** it is parsed, **Then** postgres-exporter runs `prometheuscommunity/postgres-exporter:v0.20.1` with `--collector.stat_checkpointer` and keeps its memory limit (infra/vps1/monitoring/compose.yaml:178; spec § Compatibility checks)
- **Given** `scripts/bootstrap/bootstrap-config.sh`, **When** `FABRIK_HUB_VOLUMES_TO_RESTORE` is sourced in bash, **Then** it contains `postgres18-data` and not `postgres-data` (scripts/bootstrap/bootstrap-config.sh:201; spec § The delta › D3)
- **Given** the DR scripts and docs this ticket owns, **When** they are searched for `postgres-data` as a whole word (so `postgres18-data` never matches), **Then** no line matches, and `disaster-recovery.md`'s volume-count comment reads 11 until release (docs/operations/disaster-recovery.md:74)
- **Given** the files this ticket owns, **When** they are searched for `PostgreSQL 16`, `Postgres 16`, `postgres:16` or `PG16`, **Then** none matches (README.md:859; spec § Documentation landing sites)
- **Given** docker on WSL, **When** `tests/test_app_role_real_pg.py` runs, **Then** its scratch container is `postgres:18.6-alpine` and the suite passes (tests/test_app_role_real_pg.py:30; spec § Validation V4)
- **Given** the two docs, **When** they are searched for `PostgreSQL 16`, `postgres:16` or `pgvector:pg16` stated as the current major, **Then** none matches (docs/infrastructure/vps-complete-inventory.md:120; spec § Documentation landing sites)
- **Given** the runbook, **When** its hub-window section is read, **Then** every D1 step (the disk gate, 1–8 and 6a) has a command block, a verify line and a rollback line, in the spec's order, and step 6's verify carries the § Compatibility checks items (spec § The delta › D1; § Compatibility checks)
- **Given** the runbook, **When** its WSL section is read, **Then** D2 steps 0–6 appear in order and the local-writer stop list names session-recall, the youtube financials cron and the trade-intelligence GTIP refresh (docs/operations/wsl-environment.md:52; spec § The delta › D2)
- **Given** the runbook, **When** its release section is read, **Then** the V8 DR drill precedes any release step, and no step removes a docker volume or a cluster without the operator's explicit word (CLAUDE.md volumes HARD STOP; spec § Lifecycle; § Validation V8)
- **Given** the runbook's appendix, **When** it is read, **Then** it carries one request text per spec D5 bullet and for D6, each naming its projects' exact files from spec § What exists today, the 27 doc-only projects in one broadcast (spec § The delta › D5)
- **Given** the scratch rehearsal, **When** it runs the runbook's hub window from a seeded 16 cluster, **Then** V1 is green on 18.6 — counts, content hashes, roles, ACLs, settings and the recorded connection limit — and the restore stderr holds only `role "postgres" already exists` (spec § Validation V1)
- **Given** the hand-offs, **When** infra's and brand-identiy-creator's inboxes are read, **Then** each holds one request naming its exact files, and the two operator gates are open awaiting items (spec § The delta › D4, D7; § Lifecycle)

## Global Constraints

- Never-Route: .windsurf/rules/
- Never-Route: agents-fabrik.md
- No ticket touches a live host, a live database, the hub's `/opt/postgres/compose.yaml`, or a docker volume.
- Shared tree: sibling WIP is never staged, reverted or stashed; ledger rows go through the private-index recipe in ONE shell.
- Infra merges two branches (`scripts/merge_request.py request` for each): `fleet-pg18-dr` (T03 alone) inside the hub window, the fleet branch after it.

## Context Ledger

| Source | What binds | Grounded ref |
|---|---|---|
| Spec (CONVERGED, approved D-617) | every design choice | `docs/superpowers/specs/2026-10-06-postgresql-18-fleet-upgrade-design.md` |
| Research ledger (61 rows) | every external fact (image tags, pg_dumpall behaviour, exporter version), except the `0.8.6-pg16` tag probed in § Evidence | `docs/reference/research/2026-10-06-postgresql-18-upgrade-ledger.md` |
| `.windsurf/rules/core/25-data-postgres.md` (ACTIVE) | real-PG tests, the uuidv7 rule D4 rewrites | `.windsurf/rules/core/25-data-postgres.md:163,270` |
| `.windsurf/rules/core/30-ops.md` (ACTIVE) | compose invariants, never hot-patch, probe live | `.windsurf/rules/core/30-ops.md:148-151,268,320` |
| `.windsurf/rules/core/90-bootstrap-scripts.md` (MATCHED) | idempotent bootstrap/runbook steps | `.windsurf/rules/core/90-bootstrap-scripts.md:143,169-170` |
| `agents-fabrik.md` § Tech Stack Defaults / § Infrastructure Services | postgres-main is the shared hub cluster | `agents-fabrik.md:170` |
| fabrik-lib | none needed — no new capability; the CI derivation reuses the hub's own `fabrik.version_registry` | `src/fabrik/version_registry.py:33` |
| `specs/services/*.yaml` shape | unchanged — no service gains or loses a database | n/a |

## File Scope (owned paths)

- README.md
- docs/development/reviews/2026-10-06-plan-1-postgresql-18-upgrade-review.md
- docs/infrastructure/vps-complete-inventory.md
- docs/infrastructure/vps-hub-rebuild.md
- docs/operations/disaster-recovery.md
- docs/operations/hub-restore-inventory.md
- docs/operations/postgres-major-upgrade-runbook.md
- docs/traycer/fabrik-workflow.md
- docs/workstation/session-recall.md
- infra/vps1/monitoring/compose.yaml
- infra/vps1/postgres/compose.yaml
- scripts/bootstrap/bootstrap-config.sh
- scripts/bootstrap/bootstrap-hub.sh
- scripts/container_images.py
- scripts/generate_vps_inventory.py
- scripts/sysadmin/rules_render_versions.py
- src/fabrik/ci_scaffold.py
- src/fabrik/orchestrator/vultr_drill.py
- tests/sysadmin/test_rules_render_versions.py
- tests/test_app_role_real_pg.py
- tests/test_ci_scaffold.py
- tests/test_dr_chain_pg18.py
- tests/test_infra_vps1_postgres_compose.py
- tests/test_large_docs_pg18.py
- tests/test_live_docs_pg18.py
- tests/test_pg18_runbook.py

## Intake Inventory

| I# | Item (anchored) | Disposition | Where |
|---|---|---|---|
| I1 | "it must be done in all opt projects" | IN — D5 request texts in the runbook appendix, D7 sent now | T05, T06 |
| I2 | "wsl" | IN — the WSL window in the runbook, gated | T05, T06 |
| I3 | "all vps servers" | IN — the hub window, compose, DR chain; spokes reconnect only (they run no Postgres) | T02, T03, T05 |
| I4 | "our rules must be updated in .windsurf/rules" | IN — drafted edits mailed to infra (governance-sync paths) | T06 |
| I5 | "use fable 5.1 and opus 5.5 subagents and consult them, revise if needed then proceed" | IN — done before planning (D-617); this plan is the "proceed" | spec |
| I6 | "when can i start db in wsl and my docer for trade-intelligence?" (the operator, this session, 2026-10-06) | IN — trade-intelligence's GTIP cron is in the WSL writer stop list; nothing stops WSL before the window | T05 |
| I7 | the stale 2026-05-25 plan's operator steps | IN — carried into the runbook | T05 |

Intake: 7 items — 7 IN, 0 OUT-OF-SCOPE, 0 ASK.

## Evidence

Governance-sync triggers among the paths this work touches (regex read from `.pre-commit-config.yaml`). The four routed-out
paths, then every File Scope path of the pre-fix revision (28), verbatim:

```text
True agents-fabrik.md
True .windsurf/rules/versions.yaml
True .windsurf/rules/core/25-data-postgres.md
True .windsurf/rules/CLAIMS.yaml
28
SYNC docs/reference/prebuilt-app-containers.md
SYNC docs/reference/technology-stack-decision-guide.md
```

Both SYNC docs moved to infra's hand-off (T06 b); no File Scope path is a trigger now.

The pgvector tag the precondition relies on (Docker Hub tags API, probed 2026-10-06):

```text
0.8.6-pg16 200
0.8.6-pg18 200
0.8.7-pg16 200
```

The current CI literals and registry loader:

```text
src/fabrik/ci_scaffold.py:33  _PG_PLAIN = "postgres:16"
src/fabrik/ci_scaffold.py:34  _PG_PGVECTOR = "pgvector/pgvector:pg16"  # postgres:16 + the vector extension
src/fabrik/ci_scaffold.py:47      def pg_image(self) -> str:
src/fabrik/ci_scaffold.py:48          return _PG_PGVECTOR if "pgvector" in self.db_extensions else _PG_PLAIN
src/fabrik/version_registry.py:26  REQUIRED_KEYS: tuple[str, ...] = ("node_lts", "debian_codename", "node_engines_floor")
```

The hub compose today (`infra/vps1/postgres/compose.yaml`):

```text
3:    image: postgres:16-alpine
8:    - postgres-data:/var/lib/postgresql/data
14:          memory: 2G
23:    - 10.99.0.1:5432:5432
25:  postgres-data:
26:    external: true
```

Primary paths, one per ticket: `src/fabrik/ci_scaffold.py:47` (T01a), `scripts/sysadmin/rules_render_versions.py:36` (T01b), `infra/vps1/postgres/compose.yaml:3` (T02),
`scripts/bootstrap/bootstrap-config.sh:201` (T03), `tests/test_app_role_real_pg.py:30` (T04a), `docs/infrastructure/vps-complete-inventory.md:120` (T04b),
`docs/operations/wsl-environment.md:52` and `scripts/bootstrap/bootstrap-hub.sh:89` (T05), `docs/operations/disaster-recovery.md:43` (T06's rehearsal window rule).

## Self-audit

- Grounding: three native seats (Opus on the window touchpoints, Sonnet on the hub code, Sonnet on the constraints digest);
  their corrections are applied above — `scripts/backfill_ci.py` asserts only `RUFF_VERSION`, not image strings; three spec
  citations corrected; five more DR-doc lines and four more WSL writers found.
- (a) Coverage: D1 → T05 (+ T02 mirror); D2 → T05; D3 → T01a, T01b, T02, T03, T04a, T04b; D4 → T06 (infra mail); D5 → T05 appendix;
  D6 → T05 appendix (trade-intelligence's six pins); D7 → T06; Validation V1 → T06 rehearsal, V4 → T04a, V2/V3/V5/V6 →
  runbook verify lines (T05), V7 → infra's registry flip after the window; V8 → the runbook's release section (T05).
- (b) Interfaces: the runbook's compose and volume strings are asserted against T02's and T03's files by T05's seam test.
- Not yet converged — `/fabrik-plan-review` owns the fixed point.

## Coverage Checklist

Armed by `python scripts/review_rubric.py --changed <the 28 File Scope paths of the round-1 revision; the two routed-out docs/reference files add no pack>`, output verbatim (the promote tail elided, declared):

```text
# REVIEW RUBRIC — inject into EVERY finder prompt (generated by review_rubric.py)
# Honesty (L1): this arms the review — it raises compliance probability, it does not guarantee it.

## FLOOR — always injected, regardless of glob (spec L3; SERVICE surface)

### core/35-security-auth.md
**The default for ALL new projects, including user-facing SaaS + mobile.** Vendor `fabrik-lib/fastapi-user-auth`: the app issues its own JWTs — **Argon2id** (the vendored argon2-cffi defaults meet OWASP minimums; never Argon2i) + timing-equalized login, atomic refresh-token rotation (`DELETE … RETURNING`), JWT `jti` denylist revocation, and dual-mode tenant-isolation RLS. Supabase is retired as a default (see `agents-fabrik.md § Supabase`); reach for Pattern B only for a project that *already* runs on Supabase Auth.
- Do not use NextAuth.js, Clerk, Auth0, or Firebase Auth.
- ADDITIONAL affordance a project justifies, never the default door.
- project files the fabrik-lib request FIRST, never hand-rolls WebAuthn.
| `chrome-extension` | ✅ **use this** | ⚠️ only via `chrome.identity.launchWebAuthFlow` + the `https://<ext-id>.chromiumapp.org/` redirect the pack already mandates; a bare mailed link lands in a TAB that cannot reach `chrome.storage.session` |
| `desktop-app` | ✅ **use this** | ⚠️ needs a registered custom protocol handler; the token then goes to `safeStorage` (`desktop-app/72-desktop.md`) |
- service MUST be able to say which:
| **Another Fabrik service** (Docker-to-Docker on the `fabrik` network) | `X-Internal-Token` + `internal_auth.py`, `hmac.compare_digest`, 403 on reject | § Internal Service Auth (M2M) below — **never** an inline `APIKeyHeader`, never a per-service key name |
- An approval link opened somewhere the user did not start must never mint a session silently.
- > **Fail-closed invariant (hard, every mode).** `auth.uid()` and `current_tenant_id()` MUST return `NULL` (→ the policy denies) on unset, empty, or malformed claims — wrap the body in `EXCEPTION WHEN OTHERS THEN RETURN NULL`. **Never** raise and never default to a value: a default turns one bad/empty JWT into a cross-tenant read, and a raise turns a deny into a 500. This is the single most security-critical line in the build — verify it explicitly with a no-context probe (`SELECT auth.uid()` → `NULL`).
- The JWT signing secret must be at least 256 bits, generated via `openssl rand -hex 32`, and injected via Pydantic Settings. Never hardcode it.
- **Pin the algorithm in the VERIFIER** — pass an explicit allow-list (`algorithms=["HS256"]`), never let the library dispatch on the token header's `alg`. Header-driven dispatch is the classic confusion attack (an RS256 public key replayed as an HS256 HMAC secret); `alg: none` is rejected unconditionally.
- "Sticky sessions are a violation of twelve-factor and should never be used or relied upon."
- => Mandate: processes are stateless/share-nothing. **STICKY SESSIONS ARE BANNED** (not just file-based sessions). Session state goes to `redis-main` (Redis) with a TTL. Never in-process memory, never on local disk. Any design that assumes "the same user hits the same process" is a violation.
- **Pattern B (legacy / migration-only):** The Supabase client SDK handles token storage. On mobile, wrap with `expo-secure-store` (never AsyncStorage or MMKV for tokens). See `80-mobile.md` § Backend Integration.
- **Both patterns:** Never store JWTs in `localStorage` or `sessionStorage` on web. Never store JWTs in AsyncStorage or MMKV on mobile.
- **Chrome Extension (MV3) specifics:** `chrome.storage.session` defaults to `TRUSTED_CONTEXTS`, so **content scripts cannot read the token** — keep it in the SW / extension-page context and have content scripts fetch it via SW-mediated messaging (`chrome.runtime.sendMessage`), not a direct read. For social login use `chrome.identity.launchWebAuthFlow` with **PKCE** (`code_verifier` via `crypto.subtle`, held in `storage.session`, redirect `https://<ext-id>.chromiumapp.org/`); the **backend** does the code-for-token exchange. **Never a heavy browser auth SDK** (Auth0-SPA-JS, `oidc-client-ts`) — they assume DOM/`localStorage`/iframes and break in the service worker. Pin a manifest `key` so the extension ID (and thus the `chrome-extension://<id>` CORS origin) is stable across machines. Full detail: `chrome-ext/70-chrome-ext.md`.
- **Never rely solely on the framework's request-shaping layer for access control.** CVE-2025-29927 (the `x-middleware-subrequest` bypass) proved COMPLETE middleware bypass via one crafted header; it is long patched upstream, but the rule outlives the patch — current Next.js even RENAMED the file to say so: `middleware.ts` became **`proxy.ts`**, explicitly repositioned as request-shaping, not a security boundary. ⚠️ **On current majors a leftover `middleware.ts` is SILENTLY IGNORED at build** — nonce injection and redirects stop executing with no error; rename it when upgrading.
- `CORSMiddleware` in FastAPI must populate `allow_origins` from environment variables (Pydantic Settings). Never hardcode origins.
- `X-Frame-Options: DENY` — kept as the legacy fallback only; formally obsoleted by `frame-ancestors`, never ship it ALONE
**Never** write inline `APIKeyHeader` / `require_api_key`. **Never** use per-service key names (`SERVICE_API_KEY`, `PROXY_API_KEY`). Scaffold `python-api` auto-emits `internal_auth.py`, `metrics.py` (REQUEST_COUNT / ERROR_COUNT / ACTIVE_JOBS / PROCESSING_COUNT), `/metrics` endpoint (Authelia-bypassed), and `SERVICE_INTERNAL_SECRET_KEY` in `.env.example`.
- => Mandate: config via env vars only (`os.getenv("KEY", "default")`); **ZERO secrets/constants in code**. Apply the open-source litmus test to every change. **BANNED**: grouped/named env config sets (e.g. a `config/production.yml` or a `settings.production` group) — env vars are granular and orthogonal, set per deploy. (The pack already covers secret handling — cross-reference existing secret patterns and extend with config orthogonality.)
- [ ] Mobile tokens stored in `expo-secure-store` — never AsyncStorage or MMKV.
- > **⚠️ Bearer bypass scope — security-critical.** The bypass defaults to `^/api/`, which makes the **entire** `/api/*` surface public (un-2FA'd). If the application authenticates only a **sub-prefix** (e.g. `/api/v1` carries the bearer/internal-token check) while OTHER `/api/*` routes are unauthenticated (legacy / admin / destructive), you **MUST** narrow the bypass with `shape.bearer_bypass_prefix: "^/api/v1"` — otherwise `fabrik apply` exposes those routes to the public internet. **Bypass ONLY the path the app itself authenticates.** Value must start with `^/`; the verifier (`orchestrator/verifier.check_api_bypass`) probes the configured prefix on deploy. When unsure whether a service has un-auth'd `/api/*` routes, ask the app owner before relying on the `^/api/` default.

### core/25-data-postgres.md
| Vector search | pgvector on `postgres-main` + `fabrik-lib/rag` — ⚠️ the extension is NOT currently installed there (probed 2026-09-01: `postgres:16-alpine`, `plpgsql` only); a project needing vectors REQUESTS the fleet infra change first, never assumes it | same `postgres-main` DSN |
**"Own database" means a DATABASE on `postgres-main`, never a database SERVER.** Per-project isolation is a separate database (its own name, its own role) on the shared container — isolation, quota and backup are all satisfied at that grain. A dedicated Postgres instance is a decision, not a default: it needs its own `docs/DECISIONS.md` row naming what the shared server cannot serve (web-ecommerce-factory 01M1Q8X9, 2026-09-05: "one DB per store" read naively as one server per customer).
- Use Pydantic `BaseSettings` (per `10-python.md` § Config Loading) — never raw `os.getenv` **for an APPLICATION's settings surface**:
- ⚠️ **Scope, stated here because this LINE is what `review_rubric.py` injects — without its section.** The rubric FLOOR-injects this mandate *and* `35-security-auth`'s "config via env vars only (`os.getenv("KEY", "default")`)" into every finder prompt on every review, so a finder reading both literally has two rules it cannot both satisfy, and files a false positive on whichever it applies. The carve-out: `BaseSettings` governs a SERVICE's config surface (a `Settings` object, DB/Redis DSNs, secrets). A **vendored fabrik-lib module** has no settings object by design — it reads its own knobs with bare `os.getenv("KEY", "default")`, which is `35-security-auth`'s mandate being satisfied, not this … (wrapped further — read the pack)
- Never blindly trust `--autogenerate`. Always review `upgrade()` and `downgrade()` for unintended column drops, rename misinterpretations, and ENUM alterations before committing.
- > **Older pythons only** (services pinned below stdlib-uuid7 — which today includes SCAFFOLDED services: the scaffold still emits an older interpreter and ships `uuid-utils`; alignment tracked in the backlog): import `uuid7` from `uuid_utils.compat`, never `uuid_utils.uuid7()` directly — the latter returns `uuid_utils.UUID`, which asyncpg rejects (not a stdlib `uuid.UUID`). **DB-side:** newer PostgreSQL majors ship native `uuidv7()` (probe: `SELECT uuidv7()`); prefer `DEFAULT uuidv7()` at schema level where it exists. `postgres-main` currently runs major <!--v:postgres_major-->16<!--/v-->, which predates it — generate app-side on the fleet.
- Foreign keys must declare `ON DELETE` behaviour explicitly — `CASCADE` if children cannot exist without the parent, `RESTRICT` to protect audit trails. Never rely on the implicit default.
- This section owns the **canonical** engine, session, and `get_db`. `10-python.md` imports from here — never redefines its own.
- Database `AsyncSession` must be scoped to the route handler via `Depends()`. Never open sessions or transactions in global middleware — this holds connections during serialisation and I/O, exhausting the pool.
**BANNED as a server-side backing service** (dev, test, and prod alike):
**⚠️ SCOPE — this ban is about BACKING SERVICES, not client-local storage.** It does **NOT** apply to:
- **`desktop-app`** — SQLite is the **mandated** engine there (`desktop-app/72-desktop.md` § Local Persistence: `better-sqlite3` + SQLCipher; *"Production builds MUST encrypt the local SQLite file"*).
**12-Factor IV (Backing Services) — generalised:** swapping ANY attached backing service (DB, cache, object storage) is a **config change, never a code change**. The handle lives in `DATABASE_URL` / `REDIS_URL` / storage env — the code *reads* it, the code does not *decide* it. Never `if ENV == "prod":` branching to pick a host. (See § PostgreSQL Host Selection, which already mandates this for the DB.)
- [ ] All primary keys use UUIDv7 — stdlib `uuid.uuid7` on current Python (older pythons: `uuid_utils.compat.uuid7`, never direct `uuid_utils.uuid7()`); no `uuid4()`.

### core/30-ops.md
- the pinned release leaves full security support, never per-pack.
- All services deploy via `fabrik apply` (SSH + Docker Compose) on the `fabrik` network. Traefik routes external traffic — services do NOT bind host ports.
- **No `ports:` section.** All external traffic routes through Traefik. Never bind host ports. See Docker Port Security below. **12‑Factor VII (Port binding):** "the app is self‑contained and exports HTTP by binding to a port; it does not rely on runtime injection of a webserver" — which is exactly WHY no host `ports:`.
- **`container_name: <name>` is mandatory.** Same `_validate_compose()` gate refuses any service without it. Stable names are required so Gatus endpoints, inter-service URLs, and `docker exec`/`docker inspect` keys don't drift per redeploy. Use the bare service name (`browserless`, `gotenberg`, `meilisearch`, `glitchtip-web`, `site-provisioner`, etc.) — never UUID-suffixed names.
- gets one (ruling D-052) — see `core/60-watchdog.md`. Do not author a `watchdog: { enabled: false }` opt-out; if a project genuinely cannot host the sidecar, that is a ruling to obtain, not a default to flip.
- path before the flag goes in the spec, and assert target health (`/api/v1/targets` → `up`), never a bare `curl` of a path you assumed.
- remove it` on the hub) names a plan that protects nothing. Never add a service-named plan.
- health-enabled service can NEVER pass `up -d --wait` on a fresh database, and the deploy hangs to timeout.  An init the deploy cannot perform itself is a runbook step the plan MUST own.
- `fabrik redeploy <app>` SSHes to the VPS and runs `git pull` + `docker compose up -d --wait` against the **GitHub remote**, NOT the local `/opt/<app>` clone. Skipping `git push` redeploys the previous remote commit — the VPS never sees local changes.
**Mandate:** build → release → run are strictly separated. Releases are IMMUTABLE; the git SHA is the release ID. NEVER hot‑patch a running container (no `docker exec` to edit code/config in place, no in‑place code mutation on the VPS). Any change = a new build + a new release via `fabrik apply` / `fabrik redeploy`.
- Runtime database migrations that modify the app container (migrations MUST be run as separate deploy‑time steps)
**Place a service next to its data.** A spoke-hosted service reaches `postgres-main`/`redis-main` over the WireGuard mesh, and that hop is cross-Atlantic (Coventry ↔ LA) on EVERY query — a per-request chatty service pays it hundreds of times per page. So a DB-chatty service targets vps1; a spoke earns a service whose data traffic is light, batched or cached; a service PINNED to a spoke by hardware (GPU) batches or caches its data access — the data never moves off vps1. Measure before choosing (`ping 10.99.0.1` from the spoke, and the request's query count), never assume — the correctness rule ("container DNS, never localhost") says nothing about latency.
**Mandate:** WSL dev and the VPS run the SAME backing services (PostgreSQL + Redis), same major version. NEVER substitute a different backing service in dev (no SQLite standing in for Postgres, no in‑memory dict standing in for Redis). The same code must run unmodified in both environments.
- WSL runs PostgreSQL + Redis at the SAME MAJOR as the VPS containers — probe the live truth, never copy a tag from a doc: `ssh vps "sudo docker inspect postgres-main redis-main --format '{{.Config.Image}}'"` (2026-09-01: `postgres:16-alpine` · `redis:7-alpine` — upstream official images, outside OUR-image Alpine ban per § Banned Patterns)
**Invariant:** Never use `ports:` in compose.yaml to expose internal services to the host. All external traffic must go through Traefik.
**Health endpoints (`/health`, `/healthz`, `/metrics`, `/api/health`) bypass Authelia on all services** — required for Gatus and Prometheus monitoring. The bypass is **resource-based, not domain-bound** — applies on every domain routed through Authelia (hub direct + spokes via `authelia-vps1@file` middleware). Never protect these paths.
**CRITICAL:** Use `web`/`websecure` in Traefik labels — never `http`/`https` (those entrypoints do not exist). The scaffolder emits the correct entrypoint names; if you hand-write labels, match these exactly.
**Mandate:** migrations and admin tasks run as a ONE‑OFF process against the DEPLOYED image + env — identical environment to regular processes. NEVER run admin tasks from a laptop against prod, NEVER via `docker exec` into a live container, and **ABSOLUTELY NEVER auto-run migrations from app startup/`lifespan`** (concurrent replicas race the Alembic version table → wedged deploy).
- > **`fabrik run` and `.fabrik/hooks/post-deploy/` do NOT exist** — the real CLI answers `Error: No such command 'run'`, the hook path appears nowhere in the platform, and `_post_deploy_sync()` (`cli.py:64`) only refreshes `data/projects.yaml`; an agent following either ships a deploy where migrations never run. Do not re-add either without a `path:line` in `src/fabrik/` that executes it.
**Processes are share-nothing:** any state shared across requests MUST go to Redis (`redis-main`) with a TTL. A project using Redis for sessions MUST declare `shape.needs_cache: true` in `specs/services/<id>.yaml`, or `fabrik apply` skips the Redis registrar and the deploy is silently broken.
- "A twelve-factor app never relies on implicit existence of system-wide packages"
**Mandate:** any binary the app shells out to (ffmpeg, yt-dlp, poppler, tesseract…) MUST be `apt-get install`-ed in the Dockerfile, with a `shutil.which()` startup probe that fails fast. **The pinned base image is the version boundary** — exact `=version` apt pins are banned: they break on every Debian point release as old debs leave the mirrors (the "works then mysteriously breaks" class this section exists to prevent); the codename pin + image digest give the reproducibility. Never assume `curl`/ImageMagick/ffmpeg exist in the image — they don't by default.

### 12-FACTOR (all twelve axes)
- I codebase: shared code → fabrik-lib, never two apps in one repo
- II deps: every shelled-out binary installed + pinned in the Dockerfile
- III config: granular env vars; no secrets in code; no grouped env sets
- IV backing services: swappable by DSN/config change only
- V build/release/run: releases immutable; never hot-patch a container
- VI processes: stateless; session state → redis-main; no sticky sessions
- VII port binding: bind in-container; Traefik routes; no host ports:
- VIII concurrency: scale out; never daemonize or write PID files
- IX disposability: SIGTERM returns in-flight jobs to the queue; jobs idempotent
- X dev/prod parity: same backing services everywhere; no SQLite-for-Postgres
- XI logs: unbuffered stdout only; the app never writes/rotates a logfile
- XII admin: migrations/one-offs run against the deployed release, never startup

## MATCHED — packs whose globs hit the changed paths

### ai/50-agentic.md  (hit: src/fabrik/orchestrator/vultr_drill.py)
- is never the only thing between the agent and an irreversible act.
- **Auth boundary.** Agents run on the subscription's OAuth through the unmodified CLI, never `ANTHROPIC_API_KEY` (ai/00). Never pass `bare=True` on that lane: bare mode never reads OAuth credentials and fails with "Not logged in". A deployed service declares `shape.uses_claude_cli` and mounts the rotated `~/.claude`, never a static token. Anthropic's terms say subscription OAuth is for ordinary, individual use of Claude Code and its own apps; developers building products or services, including with the Agent SDK, should use an API key, and Anthropic does not permit routing requests through Free, Pro or Max credentials on behalf of their users, reserving the right to enforce that without notice. The operator's own development and automation through the unmodified CLI is the closest fit to that … (wrapped further — read the pack)
- output, and some models never return them. Pick the rate per model from the bake-off browser (hub-only), using its tools chip.

### core/10-python.md  (hit: scripts/container_images.py, scripts/generate_vps_inventory.py, scripts/sysadmin/rules_render_versions.py)
**`uv`** is the mandated Python package manager. Never use raw `pip`, `pip install`, `poetry`, or `pipenv`.
- Dependencies live in `pyproject.toml` + `uv.lock`. Do not modify these files unless the ticket authorises it.
- its own reviewed commit, never as a side effect of unrelated work.
- The one RULE: use SQLAlchemy async consistently — never mix `async def` with sync `.query().all()` (the Banned table row; the full session pattern is `25-data-postgres.md`'s).
- The canonical `engine`, `async_session`, and `get_db` are defined in `src/database.py` — owned by `25-data-postgres.md`. Import from there, never redefine:
**Config convention:** apps read a complete `DATABASE_URL` (`postgresql+asyncpg://user:pass@host:port/db`) and `REDIS_URL` from env. Discrete `DB_HOST`/`DB_PORT`/`DB_NAME`/`DB_USER`/`DB_PASSWORD` for the app to assemble are **banned**. The env supplies the complete URL — `localhost` in WSL, `postgres-main` on VPS — so the host concern is an env-layer responsibility, never code logic. See `30-ops.md` compose template for how discrete vars are interpolated into `DATABASE_URL` at the compose level.
- volume** (`30-ops.md` § Volumes), never in `.tmp` and never in `/tmp`.
**GlitchTip discipline:** unhandled exceptions (FastAPI 500s) are auto-captured by GlitchTip with full stacktraces. In the `except Exception` branch, log a **short event name + correlation_id** — never `logger.exception()` (that duplicates the traceback in Loki AND GlitchTip). See `55-observability.md` § Error Reporting for the full rule.
**Note:** Use the scaffolded logger: `from {package}.logger import get_logger` (see `55-observability.md` § Pre-Scaffolded Logging). Do not use `structlog.get_logger()` directly or `logging.getLogger(__name__)`.
- **Never a bare `asyncio.create_task()`** — an unreferenced task is silently garbage-collected and its exceptions vanish. Hold the reference and await it, or use `asyncio.TaskGroup`.
- **`datetime.now(UTC)`, never `datetime.utcnow()`** — deprecated and naive; naive datetimes are a real cross-service defect class.
- Ruff's selected rule-sets MUST include `ASYNC` (blocking IO in async code — machine-enforces this pack's hardest-to-review rule), `B` (bugbear) and `S` (bandit) alongside the defaults; configured in `pyproject.toml`, emitted by the scaffolder.
- Production services run via `uvicorn` CLI in the Dockerfile, not `uvicorn.run()` in code. Base image is always the pinned Debian `-slim` variant on `linux/amd64` (the variant is pinned fleet-wide in `30-ops.md` § Container Base Images — change it THERE, never per-repo). Never use Alpine — musllinux wheels exist now (PEP 656) but coverage is still partial, source builds are dramatically slower, and musl's allocator/stack defaults degrade CPython; the trade never pays on this fleet.
- `uvicorn.run()` is for local development only. Never ship it in production code.
- a fleet scaling decision (more containers), never a per-app flag.
**BANNED: grouped/named env config sets.** 12F is explicit — *"env vars are granular controls, each fully orthogonal to other env vars"* — so a `config/production.yml`, a `settings.production` group, or a `config/{dev,staging,prod}.yaml` tree is a violation. Env vars are granular and set **per deploy**, never batched into a named "environment".
**BANNED:** `logging.FileHandler`, `logging.handlers.RotatingFileHandler`, `TimedRotatingFileHandler`, `loguru` file sinks, any `*.log` file write, any in-app log rotation/retention/cleanup. The app never decides where logs are stored or routed — Docker → Promtail → Loki does. Full rule: `55-observability.md` § Logs.
**Factor XII — Admin processes. NEVER migrate from app startup.**
**BANNED: `alembic upgrade head` in FastAPI's `lifespan`, in an `@app.on_event("startup")`, or as an import side-effect.** With more than one replica (or a restart storm) two containers run `upgrade head` **concurrently** → they race the Alembic version table → duplicate DDL → **wedged deploy**. Migrations are a **one-off admin process against the deployed release**: `docker compose run --rm <svc> alembic upgrade head` (see `30-ops.md` § Release & Admin Processes).

### core/40-documentation.md  (hit: README.md, docs/development/reviews/2026-10-06-plan-1-postgresql-18-upgrade-review.md, docs/infrastructure/vps-complete-inventory.md)
- > **⚠️ `docs/OPERATIONS.md` + `docs/DEPLOYMENT.md` are FLEET-AI INTERFACES, not just docs (D-065).**
- **Tier-1 (author → verify → converge; the author leg is NATIVE while the pool is OFF, D-181 — `scripts/doc_reconcile.py`'s pool author cannot dispatch):** for each **mechanically-detectable** doc whose Doc-Sync trigger fired (`docs/QUICKSTART.md` · `docs/CONFIGURATION.md` · `docs/data-contract.md` · `docs/SERVICES.md` · `docs/OPERATIONS.md` — the reliable-signal subset), `scripts/doc_reconcile.py` dispatches a cheap OpenRouter-pool author (`libs.subagents`, `pick_models("docs")`) to emit a **minimal structured patch**, **verifies it before applying** (a symbol cross-check catches invented endpoints; the orchestrator injects a higher-assurance native-Claude verify), and loops to a zero-edit round. Runs per phase in `/fabrik-execute-plan`; never blocks (fail-safe). The other docs (CHANGELOG, INDEX, FEATURES, RESILIENCE, PORTS, the READMEs, `db/schema.sql`, …) have no reliable mechanical content-signal → they rely on the touch-on-change backstop below + your own edit (force-update, not force-correct).
- The SSOT is the type-aware registry (`scripts/enforcement/_doc_registry.py::PROJECT_DOCS`) — this table is its project-facing rendering, kept in step, never a second truth. `/fabrik-plan-after-chat` (the plan set's spine + tickets — the ticket-format authority) injects these rows per ticket as its `Docs:` line.
- Standalone work (not plan execution) → `Agent-Role: primary`. Trailers go below a blank line, above `Co-Authored-By`. ⚠️ The trailer block must be its OWN paragraph with NO blank line inside it: git parses only the LAST paragraph, and only if it is all-trailers. A blank line before `Co-Authored-By:` demotes everything above it to prose; so does a prose line glued to the top of the block. Measured 2026-08-15: 200 of the last 200 hub commits carried `Agent-Role:` and only 10 parsed, because the old example here shipped the blank line.
- **⚠️ Link it or it is decoration.** *Measured:* requests for files that do NOT exist came ~zero from AI bots — agents never go looking. It follows (inference, not measurement) that a file only gets read when something points at it: reference it from the docs index or README.
- ⚠️ **In THIS repo `llms.txt` is GENERATED** (`scripts/generate_capability_index.py`, refreshed daily) — never hand-edit it; change the generator. A project writing one by hand owns it.
- either way. Cheap and reversible — never at the expense of `OPERATIONS.md`/`DEPLOYMENT.md`, which are the load-bearing agent interfaces (D-065).
- **No skipped heading levels** — `##` to `###`, never `##` to `####`
- **Fenced code blocks only** — never indented code (AI treats it inconsistently)

### core/45-testing-strategy.md  (hit: tests/sysadmin/test_rules_render_versions.py, tests/test_app_role_real_pg.py, tests/test_ci_scaffold.py)
- **Behavior Contract**: every ticket enumerates its distinct **user-observable behaviors / acceptance criteria** and tests **each one** — one high-value integration/E2E test per behavior, risk-ordered, TDD for the risky ones. Skip trivia (getters / framework glue / config): **lean-but-complete, NOT 100%-line-coverage dogma**. Do not chase line coverage — ensure every behavior has a test that would fail if that behavior regressed. (Cheap pool subagents can author the per-behavior tests — the suggest→curate→author→fix workflow in `62-using-subagents.md` § Dispatch policy + `~/.claude/commands/fabrik-review.md`.)
- **No cosmetic assertions**: never assert against CSS classes, Tailwind utility strings, pixel measurements, or snapshot hashes. Assert application state and user-visible outcomes only.
- **Watched-fail-first** (for tests this change adds or modifies; trivia stays skipped per the Behavior Contract): a non-trivial behavior's test proves something only if it has been SEEN RED — either write it first and watch it fail, or (after the fact) neuter the fix/feature, prove the test goes red, then RESTORE and re-run to green. The neutered state is never staged, committed, or left in the tree. A green test never seen red is unverified — a suite can pass with its guard deleted.
- **Run tests**: `uv run pytest tests/` (never bare `pytest` — Fabrik uses `uv`) — **when the project has a `pyproject.toml`/`uv.lock`**. A `requirements.txt`-only project (no manifest) runs `.venv/bin/python -m pytest tests/` — the manifest clause chooses the RUNNER, it never disarms the mandate to run the suite (web-ecommerce-factory 01M1QEY5, 2026-09-05: the clause read as "does not apply here"). ⚠️ **Gate this on the manifest, because this line is FLOOR-injected into finder prompts and a vendored fabrik-lib MODULE has neither by design**: the module recipe ships `requirements.txt` (`fabrik-lib/README.md` § Creating a Reference Implementation), so `uv run` cannot resolve it and `python3 -m pytest` is the only thing that works. Telling a finder the sole working … (wrapped further — read the pack)
- **Zero-mock database policy**: never mock SQLAlchemy, SQLModel, or database sessions. All backend tests execute against a real PostgreSQL instance.
- **`ASGITransport` never runs lifespan** — anything the app initializes at startup (scaffolded apps are lifespan-based) silently does not exist in tests; wrap with `asgi-lifespan`'s `LifespanManager` when a test needs startup state.
- Use `structlog` in test helpers if logging is needed — never `print()`. See `55-observability.md`.
- **Never stub a server action from Playwright** — the server is the E2E boundary; stubbing belongs in the unit lane where the action is a plain function.
- Run Playwright against the PRODUCTION build (`next build && next start`), never the dev server.
- All locators must be **semantic**: `page.getByRole('button', { name: /submit/i })`. Never use CSS selectors or XPath.
- Launch Playwright's **bundled Chromium** (`channel: 'chromium'`) — stable Chrome/Edge removed the `--load-extension` / `--disable-extensions-except` side-load flags (Chrome 137/139), so those args only work under bundled Chromium, never installed stable Chrome.
- Run `@axe-core/playwright` with **`bypassCSP: true`** (the non-relaxable extension CSP otherwise makes axe throw on `chrome-extension://` pages); keep `@axe-core/playwright` a **dev-dependency only** (MPL-2.0 — never bundled into the shipped artifact). Gate bundle size with `size-limit` **per surface** (popup / side-panel / content-script). Full loop: `chrome-ext/70-chrome-ext.md` § Testing & UI Verification.
- Keep the generated types committed and re-generate on schema changes (`uv run python -c "import json; from <package>.main import app; print(json.dumps(app.openapi()))" > openapi.json` — the scaffold emits `src/<package>/main.py`, never a flat `src/main.py`, so `src.main` imports nothing).
**BANNED in tests:**
| A GUARD proven only by the ONE spelling of the defect you already fixed | Write the guard's subject five LEGITIMATE ways — five a DIFFERENT author would plausibly write, not five typos of yours — and count how many it still catches; one of five means it is keyed on your fix, not on the class — and one of five is the FLOOR of the failure, never its definition: four of five is a partial class and is reported as four of five. This is IN ADDITION to red-on-revert below, not a rival bar: that one proves the guard fires at all, this one proves it fires on the class. ⚠️ Cheapest ways to satisfy it WITHOUT the outcome (`CLAUDE.md` § UNIVERSAL governance markers, the entry whose anchor is **you get the behavior you measure** — search the ANCHOR, not the rule name: the project-facing contract lists that section by anchor alone and carries the name `cobra-effect` nowhere): (i) write five near-identical spellings and count 5/5; (ii) ship at 2/5 and REPORT it, needing no fabrication at all, in the hope that a reported count reads as a passed one — it does not: under 5/5 is a finding; (iii) claim the exercise and record nothing, since the five are never committed. So the bar is TWO things and needs both: **the five go IN the test file as executable CASES**, never a comment — a comment cannot go RED, so nothing can falsify it, and that is the objection, not that it records nothing — **and anything under 5/5 is a finding, not a pass**. ⚠️ Two paths this row does NOT close, stated rather than pretended away: you can shrink the SUBJECT until five legitimate spellings all land inside what the guard already catches (nothing is fabricated; the claim narrowed, not the guard), and an honest 4/5 — real information, 80% of the class — costs the author something to report, so the cheapest response to it is silence. Report the count you got either way — a 4/5 with the miss NAMED is a finding someone can act on, and a 5/5 nobody can execute is not a pass at all. Measured 4× in one day across 2 repos (01M1S4D78KRM0ZSYDNGTHS9HYQ), and once more the day this row landed: a contract-parity grader that read the LIVE file instead of the tree under test stayed green under the exact drift it existed to catch |
| A test THIS change adds/modifies that was never seen red (no fail-first, no red-on-revert proof) | Watch it fail first, or neuter the change → prove red → restore → re-run green |
- [ ] Destructive DB tests call `require_throwaway(TEST_DATABASE_URL)` before connecting — never point them at a dev/shared DB.

### core/55-observability.md  (hit: infra/vps1/monitoring/compose.yaml)
- ⚠️ **The shipper is Promtail today and Promtail reached END OF LIFE (2026-03-02)** — no updates, no support. Grafana Alloy is the successor (`alloy convert` migrates the config). Fleet migration is an infra action, not a per-project one; until it lands, nothing about the rules below changes.
- **The label set is the PIPELINE's, not yours** — live: `container_name`, `filename`, `host`, `job`, `service_name`, `stream`. An app cannot add labels by logging a field; a JSON field is queried with `| json`, never as a label.
- > *"A twelve-factor app never concerns itself with routing or storage of its output stream. It should not attempt to write to or manage logfiles."*
**Mandate.** The app writes structured events, unbuffered, to `stdout` and **nothing else**. The app MUST NEVER write, rotate, append to, truncate, compress, age out, or otherwise manage a logfile, and MUST NEVER decide where logs are stored, how long they are kept, or how they are routed. Routing, rotation, retention, and storage are exclusively the **execution environment's** concern.
**BANNED in app code:**
- The scaffolded logger (structlog / pino — see § Pre-Scaffolded Logging) writes to stdout. Do not add a second handler, sink, or transport alongside the stdout one.
- ❌ **BANNED — in-app file logging:**
- > **⚠️ THE SERVER'S OWN LOGGERS ARE NOT YOURS — and they leak plain text by default.**
**Chrome extension frontend:** Use `chrome.storage.local` buffer pattern per the Chrome Extension Telemetry section below. Do not use pino directly in service workers.
- Every `python-api` and `node-api` scaffold emits a pre-configured `/metrics` endpoint. DO NOT create custom metrics modules. **A VENDORED module (fabrik-lib copies) never constructs its own `Counter`/`Histogram` either:** the scaffold serves `/metrics` from a PRIVATE `CollectorRegistry` (`scaffold.py::metrics_app`), so a module-made metric on the global default registry is invisible on most `/metrics` surfaces and the module cannot know which registry its host scrapes. A module exposes an injectable callback (`on_<event>: Callable | None`) and a structured log-once; the HOST wires the callback to the registry it owns in one line. Precedent: fabrik-lib `async-http-client` (01M1GVYN, 01M1GY91).
- Name metrics with `snake_case` and a **base-unit** suffix (`_seconds`, `_bytes`); `_total` is the COUNTER suffix and composes with units (`process_cpu_seconds_total`). ⚠️ `prometheus_client` appends `_total` to a Counter itself — declare `Counter("requests", …)`, never `Counter("requests_total", …)`, and never `_count` (an OpenMetrics reserved suffix).
- ⚠️ **Know which failure YOUR stack gives you — they are not the same.** Under an OTel SDK, a metric that overflows its cardinality limit fails SILENTLY: totals stay correct while queries that *filter or group by* an attribute UNDERCOUNT, so dashboards and SLOs keep rendering numbers that are quietly too low. **Our scaffolded stack is `prometheus_client`, which has no such limit** — here a blowup is memory/TSDB growth, and Prometheus's own `sample_limit` fails the whole scrape LOUDLY (`up=0`) rather than skewing a breakdown. Loud is survivable; the reason to care about both is that a service moving to OTel inherits the silent one.
- is named, never dropped because someone remembered to remove it — and `_keep()` additionally enforces LEAF SHAPE: an allowlisted key holding an unexpected container is nulled. That last rule is what closes a channel nobody enumerated, which is the whole reason this is a shape rather than a list.
- `include_local_variables=False`, `max_request_body_size="never"`, `include_source_context=False`, `max_breadcrumbs=0`, and the fleet logging default `LoggingIntegration(event_level=logging.ERROR, level=None)` (D-126).
- ⚠️ **That last one is COUPLED to the allowlist and the two must move together.** The upstream reference uses `event_level=None`, which closes the log channel by never creating an event. The fleet keeps ERROR records as events — we want them in GlitchTip — so the channel is open, and what closes it is `_ALLOWED_LOGENTRY_KEYS == {"message"}`: the message TEMPLATE survives, `params` and `formatted` (the interpolated text) do not. Verified: `logger.error("otp=%s", secret)` yields one event with `logentry == {'message': 'otp=%s'}` and no secret. Widening that allowlist turns the fleet default into a leak where the upstream default would not.
- Every `sentry_sdk.init` / `Sentry.init` in the fleet MUST still set both:
| `max_request_body_size="never"` | **n/a — see below** | the request BODY, attached irrespective of `send_default_pii` (that flag gates COOKIES). Every auth, payments-webhook and token-exchange route is exposed the moment it logs an error while handling its request. **PYTHON ONLY** |
- ⚠️ **The two SDKs are NOT symmetric.** `maxRequestBodySize` is a PYTHON option name; `@sentry/node` has no such init key, so a project that dutifully added it got a silently-ignored unknown key — a line that reads like a fix and does nothing. In `@sentry/node` the body channel is already closed by `sendDefaultPii: false`, which makes the SDK report body **size only, never content**. If a project wants it structural regardless of PII, the real control is `httpIntegration({ maxIncomingRequestBodySize: 'none' })` — note `'none'`, not `'never'`. `includeLocalVariables: false` IS correct and needed for Node (locals default ON for Node runtimes).
**Never port an option name across SDKs by symmetry; check that SDK's own docs.**
- `api_key`/`token`/`secret` BY KEY. ⚠️ **This section used to conclude "so the HTTP-header channel is closed out of the box". That was wrong and is corrected here.** The scrubber matches a FIXED list of NAMES — 37 in sentry-sdk 2.68.1 (`DEFAULT_DENYLIST` 33 + `DEFAULT_PII_DENYLIST` 4), of which about a dozen are header-shaped (`authorization`, `cookie`, `token`, `api_key`, `secret`, `x_csrftoken`, …) — so a header the fleet invents sails straight through it. Measured, not assumed: `X-Signing-Secret` matches nothing in that list. Sentry maintaining the list does not help when the name is ours. The header channel is closed by the vendored scrubber's header ALLOWLIST, not by the SDK: unknown header names are … (wrapped further — read the pack)
- message, or a span name is the residual, and it ships. Never interpolate a secret into either. That is the honest boundary — not "only free-text remains after two flags", which was the claim that left four channels open.
**Verify on the CAPTURED EVENT, never the init kwarg.** Swap the SDK transport in a test, make a real dependency raise, and assert on what the event actually contains — asserting the kwarg was passed proves you configured it, not that nothing leaks. The hub's own guard is the pattern to copy: `tests/test_scaffold_glitchtip_security.py` swaps `capture_envelope`, raises inside a real request with six secrets in play, and substring-searches everything the transport would ship — never a field list — asserting the TRANSACTION event as well as the error, since `before_send` never sees it.
- ⚠️ **A project scaffolded before 2026-09-05 has the OLD init — the two flags at best, and the four channels above open.** Nothing back-fills it. Vendor `templates/scaffold/python/glitchtip_init.py` from the hub over your own `src/{package}/glitchtip_init.py`, keeping your `{pkg}` import line and your service name, then prove it with the captured-event guard rather than by reading the diff.
- This is intentional: services without DSN configured never pay for SDK runtime cost
- ⚠️ **Outside that set nothing captures it.** A deliberate 401/403/429 you WANT audited reaches GlitchTip never — widen `failed_request_status_codes` in the init rather than sprinkling `capture_exception` through handlers.
- For `chrome-extension`: use `@sentry/browser` in the popup/options/side-panel (trusted extension pages). **In content scripts, never call the global `Sentry.init`** — a content script shares the host page's `window`, so global-state integrations hijack host-page errors. Build an isolated `BrowserClient` + `Scope` (drop `GlobalHandlers` / `Breadcrumbs`) and wrap with `makeBrowserOfflineTransport` (IndexedDB buffer/flush). Service workers use the `chrome.storage.local` buffer pattern (see Chrome Extension Telemetry below).
- **Caught-and-handled** exceptions: log with stack traces via `exc_info=True` in Python (dedicated JSON attribute, never raw multi-line text). **Unhandled** exceptions (FastAPI 500s, uncaught throws): do NOT log tracebacks — GlitchTip auto-captures them. Log a short event name + `correlation_id` only. See § Error Reporting above.
- In FastAPI: use `contextvars` + ASGI middleware to bind the ID to `structlog` context. Never use `threading.local()` in async code.
- ⚠️ **Why this fleet stops at a correlation ID, and what to name the field.** Probed across ALL THREE fleet hosts (vps1/vps2/vps3): Loki + Prometheus + Grafana only — **no DEDICATED trace backend (Tempo/Jaeger) and no OTel collector on any of them**, and Grafana carries exactly two datasources (loki, prometheus). ⚠️ Not "no spans at all": Sentry-SDK services already emit performance transactions to GlitchTip at `GLITCHTIP_TRACES_SAMPLE_RATE` (§ config above) — that is the only span-shaped signal here, and it is not a queryable trace store. So do NOT instrument distributed tracing here: spans with nowhere to go are cost without a consumer, and "add OpenTelemetry" is over-engineering until a backend exists. A request-scoped correlation ID … (wrapped further — read the pack)
- Never rely on downstream log processors (Promtail, Logstash) for redaction — unredacted data may persist in transport buffers.
- **Never** use high-cardinality values as Loki stream labels. `request_id`, `user_id`, `session_id`, `client_ip` must remain inside the JSON payload only.
- ⚠️ **The label set is the PIPELINE's — an app cannot create one by logging a field.** See § Loki above for the LIVE set; `service`, `environment` and `level` are *not* labels on this fleet, they are JSON fields queried with `| json`.
- `/health` is Authelia-bypassed on all services. The bypass is **resource-based, not domain-bound** — `/health`, `/healthz`, `/metrics`, `/api/health` are bypassed on every domain routed through Authelia (hub direct + spokes via `authelia-vps1@file`). Never protect these paths.
- Never use UUID or timestamp-suffixed container names in Gatus configs or inter-service URLs — they drift per redeploy.
- MV3 service workers are ephemeral (terminated after ~30s idle). Do not hold logs in memory waiting for a batch window.
- Do not propose OTel instrumentation for a fleet service without new evidence. Measured against this stack: OTel **logs** remain the weakest-maturity signal in both Python and JS — exactly the one Loki already serves well — and adoption would mean a stateful Collector on memory-constrained VPSes plus re-instrumenting every project to gain distributed tracing nobody has asked for. The logs + metrics + errors triad stays.
- GlitchTip DSN comes from `GLITCHTIP_DSN` env var injected by the orchestrator from the GlitchTip registrar — do NOT hardcode the DSN in the repo.

### core/90-bootstrap-scripts.md  (hit: docs/infrastructure/vps-hub-rebuild.md, scripts/bootstrap/bootstrap-config.sh, scripts/bootstrap/bootstrap-hub.sh)
**If you see this message, switch to `ozgur@<ip>` and re-run. Do not retry with `root@<ip>`.**
- `ozgur@<ip>`. Do not test root first.
- the single-quoted remote program as one string literal and never parses it, so the remote-bash syntax error WILL NOT be caught by `bash -n` of the local script — only by an actual ssh execution.
- Every dependency-install step (apt, npm, pip, systemd-unit creation) MUST be a no-op when its outcome is already present. Probe with `command -v` (the POSIX builtin, which looks a name up the way the shell will) — not `which`, which is non-standard:
- already-bootstrapped VPS — every step should print `already installed` or `already configured`, never re-do work.
- higher unused number). Do not use `vps-drill` or other free-form names — the script will reject them.
**Prevention:** fail2ban never bans an address in `ignoreip`. Adding the operator's IP and the mesh range in a `/etc/fail2ban/jail.d/*.local` drop-in (or at runtime with `sudo fail2ban-client set sshd addignoreip <ip>`) retires this whole lockout class; the bootstrap scripts do not do it yet.
- the log, the script never runs, and the absent log looks like "it ran and printed nothing". Cron runs the line with `/bin/sh`; the shell's error goes to cron's mail (the crontab owner, or `MAILTO`), and on a box with no mail agent cron discards it. The journal (`journalctl -t CRON`) then shows only that the job ran and that its output was discarded — never the shell's error — so the writability probe below is the diagnostic, not the log.
- Founding incident: `scripts/sysadmin/liveness_audit.py:10-11` — the Claude-config DR backup had never once run from cron for exactly this reason. Reproduced again 2026-08-29 (`touch /var/log/x` → `Permission denied` for the WSL user), when a plan copied an existing `>> /var/log/…` line verbatim from a working precedent and shipped the same defect; only a native Opus reviewer caught it.
- naming — letters, digits, underscores and hyphens only), so a template installed as `vps-sysadmin.cron` never runs.
- ⚠️ **Not mechanically gated, deliberately.** Dozens of `>> /var/log/` redirects exist across this repo's docs, scripts and templates, and most are correct — VPS root cron writing pre-created files. A check flagging all of them would fire mostly on legitimate lines, and a rule that is routinely waived teaches agents that the gate's findings are advisory. Writability depends on the user and the host; only the author can resolve it, which is why this is a rule you apply rather than a check that fires.

# promote-to-check_*: tail elided (118 greppable mandates; the full mandates are above)
```

| Class | State | Evidence (paths hunted) |
|---|---|---|
| core/35-security-auth (FLOOR) | CLEAN | no ticket touches auth; seats A–C hunted the spine and every ticket — no secret, token or credential step (the runbook proves `$PGPW` by a test connection, never prints it) |
| core/25-data-postgres (FLOOR) | CLEAN | real-PG tests kept (T04a `tests/test_app_role_real_pg.py:30`); the uuidv7 rule change is routed to infra (T06 b); seat C |
| core/30-ops (FLOOR) | FIXED | compose invariants asserted by T02's BC; mesh port cite corrected to `infra/vps1/postgres/compose.yaml:23` (round 1 C8) |
| 12-FACTOR (FLOOR) | CLEAN | no step daemonizes, hot-patches or migrates at startup; the restore is an operator one-off (T05); seat C |
| ai/50-agentic (MATCHED) | CLEAN | the `src/fabrik/orchestrator/vultr_drill.py:310` edit is a comment; the V8 drill is operator-run (T05); seat A |
| core/10-python (MATCHED) | FIXED | T01a reads the registry at call time with isolated tests (round 1 C4/C5); seat A refuted import-time calls |
| core/40-documentation (MATCHED) | FIXED | T04b covers the `pgvector:pg16` tag at `docs/traycer/fabrik-workflow.md:412`; T04a covers `tests/test_app_role_real_pg.py:1,270` (round 1 slice B) |
| core/45-testing-strategy (MATCHED) | FIXED | T01b gated on the two `CLEANED_PACKS` literals (round 1 B1, round 2 NEW-1); T03's BC made satisfiable (round 2 NEW-2; grep re-derived 18 lines) |
| core/55-observability (MATCHED) | CLEAN | exporter v0.20.1 + `--collector.stat_checkpointer` in T02; no existing `command:` to merge (seat B read `infra/vps1/monitoring/compose.yaml:178`) |
| core/90-bootstrap-scripts (MATCHED) | FIXED | T03 edits only the volume array and comments; the quote cite corrected to `:169-170` (round 1 C8, round 2 leftover) |
| fail-open vs fail-closed on every gate/guard | CLEAN | the registry read raises a named `VersionRegistryError` (seat A, `src/fabrik/version_registry.py:57-66`); the freeze is closed by `default_transaction_read_only` (spec D1 step 1) |
| cost/quota/limit accounting edges | CLEAN | the disk gate and the `max_connections` check are runbook probes (T05); seat C found no other limit edge |
| boundary/sentinel/prefix collisions | FIXED | whole-word `postgres-data` search so `postgres18-data` never matches (round 2 NEW-2); restic include paths do not collide (seat A) |
| behavior-without-a-test | FIXED | the T01a live-registry test split from the isolated ones, plus a reload test (round 1 C4/C5); T03's allowlist replaced by a zero-match assertion |

## Pass Ledger

| Pass | seats · axes re-checked | counters | method | plan md5 (start → end) |
|-----:|---|---|---|---|
| Pass 1 | opus×1 (spine, T01a, T03) + sonnet×2 (T01b/T02/T04a/T04b; T05/T06/roll-up) · all axes | found: 20, new: 20, confirmed: 20, fixed: 20, unexecuted: 0, edits: 20 | method: citation — full pass over the pinned set; every candidate executed (the tag probed: `0.8.6-pg16` HTTP 200; the sync regex re-run; the `_LOOSE` shapes run against `CLEANED_PACKS`) | 7de15c23… → 8694a13c… |
| Pass 2 | opus×1 + sonnet×2 (the round-1 slice owners) · the fix hunks + one hop | found: 3, new: 3, confirmed: 3, fixed: 3, unexecuted: 0, edits: 6 | method: re-derivation — each owner re-derived its round-1 claims (B: `_LOOSE` over all 7 `CLEANED_PACKS`; C: the roll-up's 18 rows by text diff); A confirmed 3 own-fix defects in round-1 hunks and 3 leftovers | 8694a13c… → 197c1b2b… |
| Pass 3 | opus×1 (the round-1 slice A owner) · the round-2 hunks | found: 0, new: 0, confirmed: 0, fixed: 0, unexecuted: 0, edits: 0 | method: re-derivation — `command grep -nw postgres-data` over T03's six files re-derived 18 lines, all in T03's edit list; standing clean since pass 2: slices B and C | 197c1b2b… → 197c1b2b… ✓ → **CONVERGED** |

Recorded, not counted: the Execution Discipline line "every merge happens in the fleet worktree branch" reads awkwardly beside T03's own worktree (round 3, slice A) — wording only; the same line states T03's branch merges into the fleet branch.

## Residual unknowns

- Resolved: where the runbook lives (new doc); which of the 29 docs change (current-state only); who edits the registry (infra).
- Open — U1 hub cluster size and free disk: read live by the runbook's pre-window probes; the disk gate decides.
- Open — U2 `pre-backup.sh` retention: read live in the pre-window probes.
- Open — infra's `pgvector_version` key: requested by mail on approval; T01a waits on it (precondition gate).
- Open — every service's pool size vs `max_connections`: read live in the pre-window probes (project code and `.env` are not readable by agents).
