# Plan — PostgreSQL 16 → 18 across the fleet: hub branch, runbook and hand-offs ready for the operator's windows

Status: DRAFT
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
  - `.windsurf/rules/versions.yaml` and `agents-fabrik.md` are governance-sync triggers (measured below), so — with the
    packs and `CLAIMS.yaml` — they are infra's: T06 mails infra the drafted edits; no ticket's Touches holds them.
  - PRECONDITION of T01: infra adds `pgvector_version: "0.8.6"` to `.windsurf/rules/versions.yaml` with `postgres_major`
    still `"16"` (requested by mail when this plan is approved; tag `0.8.6-pg16` is a released pgvector build, spec pg-47).
    T01 is not dispatched until that key is on master; T02–T05 are not blocked by it.
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
| T01 | The CI scaffold derives its Postgres images from the version registry | — | ⚡ | ⬜ | |
| T02 | The repo's hub compose files describe the PG18 cluster and exporter | — | ⚡ | ⬜ | |
| T03 | The disaster-recovery chain restores postgres18-data | — | ⚡ | ⬜ | |
| T04a | The hub's live pins and smaller current-state docs say 18 | — | ⚡ | ⬜ | |
| T04b | The two large current-state docs say 18 | — | ⚡ | ⬜ | |
| T05 | The operator runbook for the WSL and hub windows | T02, T03 | ⛓️ | ⬜ | |
| T06 | Integration: rehearsal, hand-offs, gates and the receipt | T01, T04a, T04b, T05 | ⛓️ | ⬜ | |

## Merge Order

1. T01
2. T02
3. T03
4. T04a
5. T04b
6. T05
7. T06

T01, T02, T03, T04a and T04b are independent (disjoint Touches). T05 waits for T02 and T03 because the runbook cites their final lines. T06 is last.
T03 is merged to master by infra INSIDE the hub window (runbook step 8); every other ticket's commits merge after the window.
No two Depends-unconnected tickets share a path.

## Interfaces

- **T02 → T05 — the compose lines the runbook's swap and rollback steps cite.** Seam test: `tests/test_pg18_runbook.py` (T05) asserts the runbook's image and mount strings equal those `infra/vps1/postgres/compose.yaml` holds.
- **T03 → T05 — the DR volume name.** Seam test: `tests/test_pg18_runbook.py` (T05) asserts the runbook's step 8 names the same volume `scripts/bootstrap/bootstrap-config.sh` restores.
- **T01 → infra — the `pgvector_version` key.** Seam: T01's tests read the live registry, so a missing key fails loudly.

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
| Runbook steps idempotent | every step must be a no-op when its outcome is already present | .windsurf/rules/core/90-bootstrap-scripts.md:169 |
| Probe tools with command -v | Probe with `command -v` | .windsurf/rules/core/90-bootstrap-scripts.md:143 |
| The exporter must actually serve | `exposes_metrics: true` ⇒ the metrics path actually SERVES. | .windsurf/rules/core/30-ops.md:213 |
| CHANGELOG for config/compose changes | Any change to code (`src/`, `scripts/`, `templates/`) or config | .windsurf/rules/core/40-documentation.md:130 |
| Memory limit on every compose service | a memory limit per service is a Fabrik invariant | CLAUDE.md:298 |
| Volumes are data | Volumes are DATA — "dangling" ≠ disposable. | CLAUDE.md:306 |
| Destructive steps dry-run first | destructive script on prod data w/o dry-run | CLAUDE.md:305 |

The hub `postgres-main` keeps its mesh port `10.99.0.1:5432` (`infra/vps1/postgres/compose.yaml:22`) — the spokes reach the
shared cluster through it; T02 changes no port.

## Execution Discipline (binding on /fabrik-execute-plan)

- **Review floor** — every ticket, on the coder's return, runs `/fabrik-review` on its changed surface to a
  coverage-adjudicated exit BEFORE its merge; no ticket merges on a first-pass green. T01 (`src/fabrik/ci_scaffold.py`
  feeds every scaffold's CI) and T03 (the DR chain) take the full `/fabrik-review`; T05 is a production runbook and takes it too.
- **Dispatch policy** — native Claude seats for every fan-out (the pool is OFF, D-181/D-182): `dispatch_headroom.py` then
  `python3 scripts/command_run.py dispatch --seats N` before each fan-out. Coders: Sonnet for T02, T03, T04a, T04b (`simple`),
  T01 (`complex`); Opus for T05 (`native`, design-heavy); T06 is the orchestrator's. Haiku never codes. Seats never read
  `$HOME/.claude*` or any `.env`, never ssh, never touch a live database; a scratch docker rehearsal uses named containers removed after.
- **Precondition gate** — T01 is not dispatched while `.windsurf/rules/versions.yaml` on master lacks `pgvector_version`.
- **Operator gates** — no ticket executes the WSL window or the hub window; T06 boards both, and the hub window is Gate 2.
- **Parallelism + merge** — T01, T02, T03, T04a and T04b fan out concurrently (disjoint Touches) once T01's precondition holds;
  T05 starts when T02 and T03 are merged; every merge happens in the fleet worktree branch in § Merge Order, and the
  results merge/dedupe at T06, which re-runs every ticket's gate on the merged branch.
- **Ids** — every D-row this plan mints uses `python3 scripts/decisions.py --reserve-id .`.

## Behavior Contract

- **Given** a registry with `postgres_major: "16"` and `pgvector_version: "0.8.6"`, **When** `ci_files` renders a config with and without `db_extensions=("pgvector",)`, **Then** the workflow and the local script both name `pgvector/pgvector:0.8.6-pg16` and `postgres:16` respectively (src/fabrik/ci_scaffold.py:47; spec § The delta › D3)
- **Given** the registry path monkeypatched to one with `postgres_major: "18"`, **When** the same configs render, **Then** they name `pgvector/pgvector:0.8.6-pg18` and `postgres:18` (spec § The delta › D3)
- **Given** a registry lacking `pgvector_version`, **When** `fabrik.ci_scaffold` is imported, **Then** the import succeeds, and **When** `pg_image()` runs for a pgvector config, **Then** it raises `VersionRegistryError` naming `pgvector_version` (src/fabrik/version_registry.py:33)
- **Given** the strings `postgres:18-alpine`, `postgres:18.6-alpine` and `pgvector/pgvector:0.8.6-pg18`, **When** `_LOOSE` searches each, **Then** each matches, and the existing `PostgreSQL 16` and `pgvector:pg16` cases still match (scripts/sysadmin/rules_render_versions.py:36)
- **Given** `infra/vps1/postgres/compose.yaml`, **When** it is parsed, **Then** postgres-main runs `postgres:18.6-alpine`, mounts the external volume `postgres18-data` at `/var/lib/postgresql`, keeps `deploy.resources.limits.memory`, `container_name` and the `fabrik` network, and no service mounts anything at `/var/lib/postgresql/data` (infra/vps1/postgres/compose.yaml:3; spec § The delta › D1)
- **Given** `infra/vps1/monitoring/compose.yaml`, **When** it is parsed, **Then** postgres-exporter runs `prometheuscommunity/postgres-exporter:v0.20.1` with `--collector.stat_checkpointer` and keeps its memory limit (infra/vps1/monitoring/compose.yaml:178; spec § Compatibility checks)
- **Given** `scripts/bootstrap/bootstrap-config.sh`, **When** `FABRIK_HUB_VOLUMES_TO_RESTORE` is sourced in bash, **Then** it contains `postgres18-data` and not `postgres-data` (scripts/bootstrap/bootstrap-config.sh:201; spec § The delta › D3)
- **Given** the DR scripts and docs this ticket owns, **When** they are searched for a restore instruction naming `postgres-data`, **Then** none remains outside an explicit release-time note (docs/operations/disaster-recovery.md:74)
- **Given** the files this ticket owns, **When** they are searched for `PostgreSQL 16`, `Postgres 16`, `postgres:16` or `PG16`, **Then** none matches (README.md:859; spec § Documentation landing sites)
- **Given** docker on WSL, **When** `tests/test_app_role_real_pg.py` runs, **Then** its scratch container is `postgres:18.6-alpine` and the suite passes (tests/test_app_role_real_pg.py:30; spec § Validation V4)
- **Given** the two docs, **When** they are searched for a statement that the fleet or postgres-main runs `PostgreSQL 16` or `postgres:16`, **Then** none matches (docs/infrastructure/vps-complete-inventory.md:120; spec § Documentation landing sites)
- **Given** the runbook, **When** its hub-window section is read, **Then** every D1 step (the disk gate, 1–8 and 6a) has a command block, a verify line and a rollback line, in the spec's order (spec § The delta › D1)
- **Given** the runbook, **When** its WSL section is read, **Then** D2 steps 0–6 appear in order and the local-writer stop list names session-recall, the youtube financials cron, the trade-intelligence GTIP refresh and the MCP tunnel (docs/operations/wsl-environment.md:52; spec § The delta › D2)
- **Given** the runbook, **When** its release section is read, **Then** no step removes a docker volume or a cluster without the operator's explicit word (CLAUDE.md volumes HARD STOP; spec § Lifecycle)
- **Given** the runbook's appendix, **When** it is read, **Then** it carries one request text per D5 project, each naming that project's exact files from spec § What exists today (spec § The delta › D5)
- **Given** the scratch rehearsal, **When** it runs the runbook's hub window from a seeded 16 cluster, **Then** V1 is green on 18.6 — counts, content hashes, roles, ACLs, settings and the recorded connection limit — and the restore stderr holds only `role "postgres" already exists` (spec § Validation V1)
- **Given** the hand-offs, **When** infra's and brand-identiy-creator's inboxes are read, **Then** each holds one request naming its exact files, and the two operator gates are open awaiting items (spec § The delta › D4, D7; § Lifecycle)

## Global Constraints

- Never-Route: .windsurf/rules/
- Never-Route: agents-fabrik.md
- No ticket touches a live host, a live database, the hub's `/opt/postgres/compose.yaml`, or a docker volume.
- Shared tree: sibling WIP is never staged, reverted or stashed; ledger rows go through the private-index recipe in ONE shell.
- Infra merges this branch (`scripts/merge_request.py request`); T03's hunk is merged inside the hub window, the rest after it.

## Context Ledger

| Source | What binds | Grounded ref |
|---|---|---|
| Spec (CONVERGED, approved D-617) | every design choice | `docs/superpowers/specs/2026-10-06-postgresql-18-fleet-upgrade-design.md` |
| Research ledger (61 rows) | every external fact (image tags, pg_dumpall behaviour, exporter version) | `docs/reference/research/2026-10-06-postgresql-18-upgrade-ledger.md` |
| `.windsurf/rules/core/25-data-postgres.md` (ACTIVE) | real-PG tests, the uuidv7 rule D4 rewrites | `.windsurf/rules/core/25-data-postgres.md:163,270` |
| `.windsurf/rules/core/30-ops.md` (ACTIVE) | compose invariants, never hot-patch, probe live | `.windsurf/rules/core/30-ops.md:148-151,268,320` |
| `.windsurf/rules/core/90-bootstrap-scripts.md` (MATCHED) | idempotent bootstrap/runbook steps | `.windsurf/rules/core/90-bootstrap-scripts.md:143,169` |
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
- docs/reference/prebuilt-app-containers.md
- docs/reference/technology-stack-decision-guide.md
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
- docs/development/reviews/2026-10-06-plan-1-postgresql-18-upgrade-review.md

## Intake Inventory

| I# | Item (anchored) | Disposition | Where |
|---|---|---|---|
| I1 | "it must be done in all opt projects" | IN — D5 request texts in the runbook appendix, D7 sent now | T05, T06 |
| I2 | "wsl" | IN — the WSL window in the runbook, gated | T05, T06 |
| I3 | "all vps servers" | IN — the hub window, compose, DR chain; spokes reconnect only (they run no Postgres) | T02, T03, T05 |
| I4 | "our rules must be updated in .windsurf/rules" | IN — drafted edits mailed to infra (governance-sync paths) | T06 |
| I5 | "use fable 5.1 and opus 5.5 subagents and consult them, revise if needed then proceed" | IN — done before planning (D-617); this plan is the "proceed" | spec |
| I6 | "when can i start db in wsl and my docer for trade-intelligence?" | IN — trade-intelligence's GTIP cron is in the WSL writer stop list; nothing stops WSL before the window | T05 |
| I7 | the stale 2026-05-25 plan's operator steps | IN — carried into the runbook | T05 |

Intake: 7 items — 7 IN, 0 OUT-OF-SCOPE, 0 ASK.

## Evidence

Governance-sync triggers among the paths this work touches (regex read from `.pre-commit-config.yaml`), verbatim:

```text
True agents-fabrik.md
True .windsurf/rules/versions.yaml
True .windsurf/rules/core/25-data-postgres.md
True .windsurf/rules/CLAIMS.yaml
False src/fabrik/ci_scaffold.py
False scripts/sysadmin/rules_render_versions.py
False scripts/bootstrap/bootstrap-config.sh
False README.md
False docs/operations/disaster-recovery.md
False infra/vps1/postgres/compose.yaml
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
22:    - 10.99.0.1:5432:5432
25:  postgres-data:
26:    external: true
```

Primary paths, one per ticket: `src/fabrik/ci_scaffold.py:47` (T01), `infra/vps1/postgres/compose.yaml:3` (T02),
`scripts/bootstrap/bootstrap-config.sh:201` (T03), `tests/test_app_role_real_pg.py:30` (T04a), `docs/infrastructure/vps-complete-inventory.md:120` (T04b),
`docs/operations/wsl-environment.md:52` and `scripts/bootstrap/bootstrap-hub.sh:89` (T05), `docs/operations/disaster-recovery.md:43` (T06's rehearsal window rule).

## Self-audit

- Grounding: three native seats (Opus on the window touchpoints, Sonnet on the hub code, Sonnet on the constraints digest);
  their corrections are applied above — `scripts/backfill_ci.py` asserts only `RUFF_VERSION`, not image strings; three spec
  citations corrected; five more DR-doc lines and four more WSL writers found.
- (a) Coverage: D1 → T05 (+ T02 mirror); D2 → T05; D3 → T01, T02, T03, T04a, T04b; D4 → T06 (infra mail); D5 → T05 appendix;
  D6 → T05 appendix (trade-intelligence's six pins); D7 → T06; Validation V1 → T06 rehearsal, V4 → T04a, V2/V3/V5/V6/V8 →
  runbook verify lines (T05), V7 → infra's registry flip after the window.
- (b) Interfaces: the runbook's compose and volume strings are asserted against T02's and T03's files by T05's seam test.
- Not yet converged — `/fabrik-plan-review` owns the fixed point.

## Coverage Checklist

Armed by running the rubric over the File Scope paths:

```text
python scripts/review_rubric.py --changed src/fabrik/ci_scaffold.py scripts/sysadmin/rules_render_versions.py infra/vps1/postgres/compose.yaml infra/vps1/monitoring/compose.yaml scripts/bootstrap/bootstrap-config.sh scripts/bootstrap/bootstrap-hub.sh src/fabrik/orchestrator/vultr_drill.py docs/operations/disaster-recovery.md
# FLOOR: core/35-security-auth.md, core/25-data-postgres.md, core/30-ops.md, 12-FACTOR
# MATCHED: ai/50-agentic.md, core/10-python.md, core/30-ops.md, core/40-documentation.md, core/45-testing-strategy.md, core/55-observability.md, core/90-bootstrap-scripts.md
```

- [ ] compose invariants kept (memory limit, container_name, fabrik network, amd64) — T02
- [ ] registry read at call time; import never fails on a broken registry — T01
- [ ] no live host, database or volume touched by any ticket — all
- [ ] runbook steps idempotent, each with verify and rollback — T05
- Standing recurrence classes: citation drift · count drift · own-fix regressions · shared-tree hygiene.

## Residual unknowns

- Resolved: where the runbook lives (new doc); which of the 29 docs change (current-state only); who edits the registry (infra).
- Open — U1 hub cluster size and free disk: read live by the runbook's pre-window probes; the disk gate decides.
- Open — U2 `pre-backup.sh` retention: read live in the pre-window probes.
- Open — infra's `pgvector_version` key: requested by mail on approval; T01 waits on it (precondition gate).
- Open — every service's pool size vs `max_connections`: read live in the pre-window probes (project code and `.env` are not readable by agents).
