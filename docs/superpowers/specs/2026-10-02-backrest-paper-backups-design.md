# Backrest coverage: protect what a service actually persists, never a path that does not exist

Status: DRAFT
Size: small (≈180 lines, 3 files)
Profile: delta — every intake item maps to code that exists today: the backrest registrar
(`src/fabrik/orchestrator/infrastructure.py::_provision_backrest`), the plan driver (`src/fabrik/drivers/backrest.py`), the
per-spec audit (`src/fabrik/audit.py::audit_backrest`) and the rollback handler (`src/fabrik/orchestrator/rollback.py`).
Rejected alternatives, Lifecycle, the constraints digest and the fabrik-lib verdict are kept short; no new persona or
consumer appears.

Work item: W-5c4ad6a6 (split from W-714ae2cf). Beat: fleet (deploy and monitoring).
Research ledger: `docs/reference/research/2026-10-02-backrest-paper-backups-ledger.md` (37 rows, every fact fetched
2026-10-02, `check_research_ledger.py` 0 refused).

## Personas

- **PRIMARY — the operator.** The work is the backrest half of the `FabrikRegistrarDrift` alert whose postgres half they
  ruled on (*"we must rule out 3 ways in your work revise"*, D-498; split into this item when W-714ae2cf was sized), and
  their standing instruction for this queue is *"if you dont need a decision do not stop to ask … finish your tasks and
  mails"*. They want a backup alert that is true: green means the data is in B2, red names
  what is not. Their loop, counted: (1) a service is deployed or changes how it persists; (2) within an hour the audit says
  whether every path it persists is in a backup plan; (3) if not, the alert names the path and the reason. **Step budget:
  0 operator steps on the healthy path; 1 (read the alert) on the failure path; plus one one-time go to remove the paper
  plans already on vps1 (a delete).** Today the healthy path is unreachable for 21 of 21 persistent specs (Why this
  exists), and every paper plan also fails nightly in Backrest and pages through Apprise.
- **The backrest registrar (automated)** — `_provision_backrest`, run by `fabrik apply` when `shape.has_persistent_data`
  (`infrastructure.py:262-270`, called at `:634-635`). **Changed duty:** it discovers where the service persists, writes
  nothing when an existing plan already covers it, and creates `<name>-data` only for paths no plan covers.
- **`audit_backrest` and the hourly audit cron (automated)** — `audit.py:331-390`, driven by
  `scripts/audit_all_registrars.py` into the `fabrik_audit_drift_total` series and the `FabrikRegistrarDrift` rule.
  **Changed duty:** the same discovery and coverage check as the registrar.
- **Backrest on each VPS (automated)** — runs the plans; `os.Stat`s every plan path before restic and fails the run on a
  missing one (ledger brk-5, brk-7). Duty unchanged.
- **`create_database` (automated)** — registers the per-database `postgres-<db>` plan and the tracked-DB line that
  `pre-backup.sh` dumps nightly (`drivers/backrest.py:342-370`, called from `drivers/postgres.py:377,470`). Duty
  unchanged; its dump directory becomes a path the coverage check reads.
- **Rollback and `fabrik destroy` (automated)** — remove `<name>-data` by id (`rollback.py:307-316`,
  `destroyer.py:213-226`). **Changed duty (rollback):** only a plan this run CREATED is recorded, so only that plan can be
  rolled back.

## Goal

Every path a persistent service writes is in a Backrest plan whose paths exist, verified at deploy and every hour; no
registrar writes a plan for a path that does not exist; and the two paper plans live on vps1 (`tryton-crm-data`,
`zitadel-data`) are removed on the operator's go, after which `FabrikRegistrarDrift` stops firing for them.

## Why this exists

`_provision_backrest` writes plan `<name>-data` with `paths = [f"/opt/{name}/data"]` for every persistent spec
(`infrastructure.py:1137-1147`) and never looks at where the service persists:

1. **Scaffolded services persist to named volumes.** The templates render `spec.volumes` as `name:path` named volumes
   (`templates/python-api/compose.yaml.j2:51-55,87-91`); compose runs from `/opt/{name}` (`orchestrator/deployer_ssh.py:67-69`),
   so the data sits at Docker's volume `Mountpoint`, never at `/opt/<name>/data`.
2. **Most persistent specs keep their state in Postgres.** Of 72 specs, 21 set `has_persistent_data: true`; 2 mount named
   volumes in their compose (tryton-crm `trytond-filestore`; youtube four `crowdlex-*` volumes, `/opt/youtube/compose.yaml`);
   15 of the remaining 19 set `needs_database: true` and mount nothing persistent (inventory 2026-10-02 over
   `specs/services/*.yaml` and `/opt/<repo>/compose.yaml`). Their data is already dumped per database by `postgres-<db>`.
3. **A plan whose path is missing is worse than no plan.** Backrest `os.Stat`s each path and fails the run (ledger brk-5),
   which fires `CONDITION_ANY_ERROR` (brk-7) — the driver wires that hook to an Apprise "Backup failed" notify
   (`drivers/backrest.py:93-104`). So each paper plan reads as a backup, fails every night, and pages.

`audit_backrest` already reports the paper plan as `drift` (`audit.py:357-378`), which is why `FabrikRegistrarDrift` fires
for tryton-crm and zitadel (2026-10-02). Meanwhile the data IS protected on vps1 by the host-wide plans: `docker-volumes`
(`/var/lib/docker/volumes`), `opt-configs` and `postgres-dumps`, with the Backrest container bind-mounting those trees
read-only at the same path (`docs/infrastructure/vps-complete-inventory.md:134,562`). The pack already says what to do:
*"If the data is a volume, say so in the spec comment and rely on the global `docker-volumes` plan; never let a
service-named plan be mistaken for the protection."* (`.windsurf/rules/core/30-ops.md:219-223`). Nothing in the code does
it.

## Chosen approach — A, a coverage check (the judge panel's unanimous first)

The registrar and the audit ask one question: **is every path this service persists covered by a Backrest plan whose
path Backrest can stat?** A path is covered when a plan lists it or a parent of it, and no exclude glob of that plan
matches it (`fnmatch`). Discovery asks Docker, never a convention:

- **Volume and bind paths** — the containers of compose project `<name>` (`label=com.docker.compose.project=<name>`, the
  project the deployer creates at `/opt/<name>`), falling back to containers named `^<name>(-|$)` for single-image apps;
  each `type=volume` mount's `Source` (the volume Mountpoint) and each `type=bind` mount whose source is a DIRECTORY under
  `/opt/<name>/`. Other binds (the Docker socket, a single config file) are not service data.
- **Database path** — `needs_database` adds `/opt/backups/postgres/<db>/` (`<db>` by `app_role_check._db_name_for_spec`,
  the registrar's own rule), the directory `pre-backup.sh` dumps into for every tracked database (`drivers/backrest.py:285-300`).

Then:

| Discovery says | Registrar does | Audit reports |
|---|---|---|
| every path covered, every path exists | nothing (logs `covered by <plan ids>`) | `present` |
| a path uncovered, Backrest can stat it | creates `<name>-data` with exactly the uncovered paths | `drift` until the plan exists, then `present` |
| a path uncovered, Backrest cannot stat it (e.g. a spoke without the volumes bind) | writes nothing; warns naming the path and the bind it needs | `drift` — "unprotected: <path> (not visible to Backrest)" |
| a covered path does not exist (e.g. no dump yet for a new database) | nothing | `drift` — "<path> missing" (first dump lands nightly) |
| a `<sid>-data` plan with a missing path | nothing (never deletes) | `drift` — "paper plan <id>: remove it" |
| nothing persistent found and no database | nothing; warns `has_persistent_data set but no persistence found` | `drift` — names the shape mismatch |
| discovery failed (ssh, docker) | nothing; non-fatal | `unknown` |

Cited practice: coverage verified as a signal rather than trusted from config is current SRE and restic practice
(ledger cov-1, cov-3); a host-level restic over `/var/lib/docker/volumes` is the field's lean pattern (vol-8); live DB
state is dumped, never copied as files (vol-3). One discovery function serves the registrar and the audit.

## Rejected alternatives

- **C — discover and always keep a per-service plan** (judges' second, 2 of 3): heals paper plans in place, but on vps1
  every named volume is scanned by `docker-volumes` AND `<name>-data` every night, forever — duplicate functionality the
  pack rule above forbids; dedup saves the bytes, not the double scan, metadata and coupled retention (brk-15, brk-18).
  Per-service restore granularity stays available through restic's path filter on the host snapshot.
- **B — declared paths in the spec** (`spec.volumes[].backup`, a dead field today, `spec_loader.py:149-154`): explicit,
  but 21 cross-project spec edits, a second source of truth that a hand-made compose (tryton-crm) drifts from, and no
  runtime check that the declaration is true.
- **A per-volume tar helper or a second backup daemon** (Docker's `--volumes-from` tar, volkeep — vol-1, vol-7): a
  second backup system beside Backrest.
- **Fixing the path only** (`/var/lib/docker/volumes/<project>_<vol>/_data` computed from the spec): guesses the compose
  project and volume names; Docker reports the real Mountpoint, so ask it (vol-2).

## What exists today (grounded)

- Registrar gate and call: `infrastructure.py:262-270`, `:634-635`; the body `:1137-1147` (`/opt/{name}/data`, records a
  `backrest` resource whatever the status).
- Driver: `add_backup_plan` is idempotent by plan id and never compares paths (`drivers/backrest.py:109-155,185-239`);
  `remove_backup_plan` (`:242`); per-database plans and the tracked-DB file (`:285-370`). The config is edited under flock
  and Backrest restarted, which a cached config requires (ledger brk-11).
- Audit: `audit.py:331-390` (plan-id lookup, host path probe `_missing_host_paths` `:314-328`, fail-open).
- Rollback: `rollback.py:153-154` dispatches every `backrest` resource to `_rollback_backrest` (`:307-316`) with no status
  filter, so a re-apply that recorded `status=exists` and then failed would remove a plan it did not create.
- Target host: the registrar's SSH goes to the spec's `target_vps` (env swap, `cli.py:972-974`, mirrored by
  `SSHDeployer.deploy()`).

## The delta

- **D1 — discovery** (`drivers/backrest.py::discover_persistence(name, db_name|None) -> list[str] | None`): one SSH call
  lists the project's container mounts (`docker ps -aq --filter label=com.docker.compose.project=<name>`, falling back to
  the name pattern, then `docker inspect --format` over `.Mounts`); returns sorted unique paths per the rules above, or
  `None` when the probe fails. The output is parsed in Python; no pipeline can mask docker's exit status (the class fixed in
  W-c6d27660).
- **D2 — plans and coverage** (`drivers/backrest.py::read_plans() -> list[dict] | None` reads `id/paths/excludes` only —
  never the repo or credential fields — from `/opt/backrest/config/config.json` with `jq`; `coverage(paths, plans) ->
  {path: plan_id | None}`, a pure function; `visible(paths) -> set[str]`, `test -e` run INSIDE the Backrest container,
  because Backrest's `os.Stat` is what decides (brk-5)).
- **D3 — registrar** (`infrastructure.py::_provision_backrest`): the table's left column. A plan is never written with
  zero paths (Backrest refuses one, brk-4); `ctx.add_resource("backrest", …)` only when the driver returned `created`.
- **D4 — audit** (`audit.py::audit_backrest`): the table's right column, through the same D1/D2 calls on the audit host.
  The `missing` status (no `<sid>-data` plan) goes: no plan is correct when another plan covers the paths.
- **D5 — heal the live paper plans**: after D4 ships, the audit's report lists every paper plan on vps1. Removing them
  is a delete of production backup config, so it is an operator-gated rollout step (Validation 4) using the existing
  `remove_backup_plan` (which writes a timestamped `.bak` first, `drivers/backrest.py:157-182`). The registrar and the
  audit never delete.

## Contract deltas

None: no data contract, no UI. `audit_backrest`'s statuses keep the `AuditResult` shape; its `missing` value is no longer
produced (consumers read `drift` and `present`, `scripts/audit_all_registrars.py`).

## Cost

No new service, no new plan on vps1 (the paper plans go away). One extra SSH round trip per apply and per hourly audit of a
persistent spec.

## Validation

1. **Red first** — tests in `tests/test_backrest_coverage.py` (new) and `tests/test_audit.py`: the coverage function over a
   table (exact path, parent path, exclude glob, sibling-prefix `/opt/a` vs `/opt/ab`); discovery parsing from recorded
   `docker inspect` output (volume, bind dir, socket bind skipped, single-image fallback, probe failure → `None`); each
   registrar row, asserting which driver call ran or never ran; each audit row. Each written first and seen red against
   today's code.
2. **Rollback guard** — a test that a re-apply recording `exists` leaves no `backrest` resource, red on today's code.
3. **Report on vps1 (read-only, after merge)** — one `scripts/audit_all_registrars.py` run; its backrest rows must show
   tryton-crm and zitadel as `paper plan` drift with their real paths covered, and list any other paper plan. Run by the
   hub cron or by the operator; this spec makes no VPS write.
4. **Operator-gated heal** — on the operator's go, `remove_backup_plan` for each listed paper plan; the next hourly run
   shows `present` for both and `FabrikRegistrarDrift` resolves.

## Decisions taken

- Approach A (coverage check) over C and B, by a unanimous judge panel; reversible (three files).
- The registrar never writes a plan for a path Backrest cannot stat and never deletes a plan; removing paper plans is
  operator-gated (D5).
- Databases are covered through their dump directory, not a volume copy (vol-3); `has_persistent_data` keeps its meaning
  and its 21 specs are not edited.
- The ledger row for the approach is minted at the approval gate (`/fabrik-plan-review`, this spec is `Size: small`).

## Lifecycle

- **First run:** the read-only report (Validation 3), then the one-time operator go (Validation 4).
- **Growth:** discovery costs one SSH call per persistent spec per hour (21 today). Trigger to revisit: a spoke hosting a
  persistent service (the `not visible to Backrest` row fires) — then the spoke's Backrest gains the
  `/var/lib/docker/volumes` and `/opt/backups` binds and a `docker-volumes-<vps>` plan (deferred today,
  `vps-complete-inventory.md:666`).
- **Failure:** a removed host plan uncovers every service at once — the next hourly audit reports each path `drift`;
  discovery failure is `unknown`, never a false `present`.
- **Retirement:** if Backrest's own `/metrics` (since v1.5.0, ledger cov-8) is scraped one day, per-plan last-success joins
  the check; coverage stays the question.

## Intake Inventory

| I# | Item (anchored) | Disposition | Where |
|---|---|---|---|
| I1 | "Backrest registrar makes paper backups: _provision_backrest hardcodes /opt/<name>/data" (W-5c4ad6a6) | IN | Why this exists; D1-D3 |
| I2 | "absent for named-volume … services" (tryton-crm) | IN | Chosen approach, volume discovery; D1 |
| I3 | "absent for … DB-only services" (zitadel) | IN | Chosen approach, database path; D1 |
| I4 | "FabrikRegistrarDrift fires for tryton-crm and zitadel" | IN | D4, D5, Validation 3-4 |
| I5 | heal the existing paper plans on vps1 | IN | D5 + Validation 4 (operator-gated delete) |
| I6 | the fix must hold for every scaffold type and for spokes | IN | Chosen approach table (visibility row); Lifecycle growth trigger |
| I7 | never delete a live backrest plan without the operator's go | IN | D5; Decisions taken |
| I8 | rollback removes a plan it did not create (found while grounding) | IN | D3 + Validation 2 |
| I9 | Backrest's own Prometheus metrics / empty-snapshot detection (restic `summary.total_files_processed`, cov-5) | OUT-OF-SCOPE | W-43904006 (backlog: alert on an empty or stale Backrest snapshot) |
| I10 | the four test specs with `has_persistent_data` and nothing to persist | OUT-OF-SCOPE | the audit's shape-mismatch drift names them; correcting their flags is a spec edit for their owners when deployed |
| I11 | the Apprise hook URL still carries a Coolify-era name (`vps-complete-inventory.md:661`) | OUT-OF-SCOPE | already tracked there (Issue 1) |

## Constraints digest

| Rule | Verbatim | Source | Applies |
|---|---|---|---|
| Volume data | "If the data is a volume, say so in the spec comment and rely on the global `docker-volumes` plan; never let a service-named plan be mistaken for the protection." | `.windsurf/rules/core/30-ops.md:222-223` | the whole approach |
| DB backups | "Backups managed via Backrest → Backblaze B2 (registered by `fabrik apply` when `shape.needs_database: true`)." | `.windsurf/rules/core/25-data-postgres.md:332` | the database path is covered by `postgres-<db>` |
| Config | "Mandate: config via env vars only (`os.getenv(\"KEY\", \"default\")`)" | `.windsurf/rules/core/35-security-auth.md:267` | unconstrained — the design adds no knob |
| Red first | "**Watched-fail-first** (for tests this change adds or modifies …)" | `.windsurf/rules/core/45-testing-strategy.md:22` | Validation 1-2 |

## External dependencies

All fetched 2026-10-02; the full rows are in the research ledger.
- Backrest plan schema and validation — https://raw.githubusercontent.com/garethgeorge/backrest/main/proto/v1/config.proto
  and https://raw.githubusercontent.com/garethgeorge/backrest/main/internal/config/validate.go (brk-1, brk-4).
- Backrest fails a run on a missing path and fires `CONDITION_ANY_ERROR` —
  https://raw.githubusercontent.com/garethgeorge/backrest/main/pkg/restic/restic.go and
  https://raw.githubusercontent.com/garethgeorge/backrest/main/internal/orchestrator/tasks/taskbackup.go (brk-5, brk-7).
- Restic dedup across plans — https://restic.readthedocs.io/en/stable/040_backup.html (brk-15).
- Docker volume data access and backup guidance — https://docs.docker.com/engine/storage/ (vol-2) and
  https://www.docker.com/blog/back-up-and-share-docker-volumes-with-this-extension/ (vol-3).
- Coverage as a monitored signal — https://sre.google/sre-book/data-integrity/ (cov-1) and
  https://github.com/nuz014/Restic-Prometheus-Exporter (cov-3).

## fabrik-lib verdict

Build — no fabrik-lib module covers the hub's registrar/audit layer (`/opt/fabrik-lib/README.md`). Not a candidate:
hub-only, one consumer.

## Shape / infra implications

None for any project's `shape:`; no spec edits. Hub-side only. No VPS write until the operator-gated heal.

## Documentation landing sites

- `docs/reference/modules/drivers.md` § backrest — discovery, coverage, visibility.
- `docs/infrastructure/vps-complete-inventory.md` § Backrest — per-service plans are created only for uncovered paths.
- `.windsurf/rules/core/30-ops.md:219-223` — the checklist line becomes true of the code; its wording is infra's beat
  (fleet-synced), so a fabrik-mail to infra proposes the edit; this spec does not edit the pack.
- `INDEX.md` (new test file), `CHANGELOG.md`, `docs/reference/research/` (this ledger).

## Open / blocking unknowns

- **Open — vps1's live plan list and Backrest mounts today.** The docs (2026-06-02) and the tryton-crm deploy plan agree on
  `docker-volumes`/`opt-configs`/`postgres-dumps` and the path-preserving binds; a read-only probe this session was
  refused by the auto-mode classifier (production reads). Resolution: Validation 3's report run reads them through the
  same code the design adds; if a host plan is missing, the report says `drift`, never a false `present`.
- **Open — compose files that set `name:`** (a project name other than `<name>`). Resolution: the single-image fallback
  pattern catches the containers; a miss shows as the shape-mismatch drift, never silence.
- **Resolved:** what Backrest does with a missing path (fails the run, brk-5/brk-7); whether overlapping plans copy data
  twice (no, dedup, brk-15; they do scan twice, brk-18); where the registrar's SSH goes for a spoke (`target_vps`).
