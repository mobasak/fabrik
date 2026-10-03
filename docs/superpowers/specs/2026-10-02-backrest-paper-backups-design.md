# Backrest coverage: protect what a service actually persists, never a path that does not exist

Status: CONVERGED (/fabrik-plan-review 2026-10-03 with plan-3, on the D-518 revision; Size: small) — APPROVED by the operator 2026-10-03 (D-520)
Size: small (≈210 lines, 3 files)
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
  (`infrastructure.py:262-270`, called at `:634-635`). **Changed duty:** it no longer writes any plan. It runs the coverage
  check at deploy time and warns, naming every path no reachable plan covers.
- **`audit_backrest` and the hourly audit cron (automated)** — `audit.py:331-390`, driven by
  `scripts/audit_all_registrars.py` into the `fabrik_audit_drift_total` series and the `FabrikRegistrarDrift` rule.
  **Changed duty:** the same discovery and coverage check as the registrar.
- **Backrest on each VPS (automated)** — runs the plans; `os.Stat`s every plan path before restic and fails the run on a
  missing one (ledger brk-5, brk-7). Duty unchanged.
- **`create_database` (automated)** — registers the per-database `postgres-<db>` plan and the tracked-DB line that
  `pre-backup.sh` dumps nightly (`drivers/backrest.py:342-370`, called from `drivers/postgres.py:377,470`). Duty
  unchanged; its dump directory becomes a path the coverage check reads.
- **Rollback and `fabrik destroy` (automated)** — remove `<name>-data` by id (`rollback.py:307-316`,
  `destroyer.py:213-226`). Duty unchanged; the registrar records no `backrest` resource any more, so rollback has nothing
  of this registrar's to undo, and destroy keeps cleaning up a legacy `<name>-data`.

## Goal

Every path a persistent service writes is in a Backrest plan that Backrest can actually run over it, verified at deploy
(a warning) and every hour (the audit); the backrest registrar stops writing plans altogether, so it can never write a
paper plan again (the postgres registrar still registers `postgres-<db>` plans, and the audit reports any whose dump
directory is absent); and the paper plans live on vps1 (`tryton-crm-data`, `zitadel-data`, and any `postgres-<db>` plan whose dump
directory is absent) are removed on the operator's go, after which `FabrikRegistrarDrift` stops firing for them.

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

## Chosen approach — A, a coverage check, check-and-warn only (revised, D-518)

The registrar and the audit ask one question, **on the VPS the service runs on** (each VPS has its own Backrest):
**is every path this service persists covered by a plan Backrest can actually run over it?** Nothing writes a plan: the
registrar warns at deploy, the audit reports every hour. Both call one
shared check that takes the two hosts as parameters — the service's `target_host` for its paths, the `hub_host` for the
database — and sets `FABRIK_VPS_SSH_HOST` itself, restoring it afterwards; neither caller wraps it in the deployer's
`_target_vps_env` (`orchestrator/deployer_ssh.py:116-140`), so the hub host is read before any swap. Today the
registrar runs hub-side after `deploy()` restores the hub host (`orchestrator/deployer_ssh.py:156-170`,
`orchestrator/__init__.py:174-180`).

Why no writes (the critiques' shared finding): on today's fleet every volume Mountpoint is under the host
`docker-volumes` plan and every `/opt` bind under `opt-configs`, and a spoke's Backrest cannot stat volume paths anyway, so
a write path would never run while adding failure modes of its own — a plan over a later-removed volume becomes the next
paper plan. A missing host plan is an operator decision (which plan, which retention), so it is reported, not invented.

**A plan is trusted only if Backrest can run it over the path** — conservative on purpose, because a false uncovered costs
a warning line and a false `present` costs a backup:
- the plan lists the path or a parent of it (trailing slashes stripped);
- every one of the plan's own paths is visible to Backrest (a plan with an unreachable path fails the whole run, ledger
  brk-5/brk-7, so it protects nothing);
- it has a schedule and the schedule is not `disabled`, and it carries no `iexcludes` and no `backup_flags` (flags can exclude files or supply
  paths, ledger brk-1/brk-4 — any flag makes the plan untrusted for coverage);
- no exclude pattern can match: an exclude counts against the path when its LAST non-empty component (trailing `/`
  stripped) matches any component of the WHOLE absolute path (`fnmatch.fnmatchcase`), a pattern with no non-empty
  component (e.g. `/`) counts as matching everything, and any pattern containing `[`, `\`, `$` or `!` counts as matching (Python and restic read brackets, escapes and environment expansion differently).
  This over-reads restic's own rules — which match against the full path — so a doubt reads uncovered.

(The hub's `docker-volumes` plan excludes whole volumes such as Prometheus and Loki data,
`docs/operations/hub-restore-inventory.md:93-112`; a service volume excluded there reads uncovered.)

**Discovery asks Docker, never a convention**, in one `bash -o pipefail` SSH call so docker's exit status reaches the
caller:
- **Containers** — compose project `<name>` (`label=com.docker.compose.project=<name>`; the deployer runs compose from
  `/opt/<name>`, `orchestrator/deployer_ssh.py:67-69`, and no `/opt/*/compose*` file sets a top-level `name:`), falling
  back to docker's own name filter `^<name>$` for single-image apps (a looser `^<name>-` matched sibling projects such as
  `test-guide-enabled`). Zero containers is its own answer
  ("not running on this host").
- **Paths** — each named `type=volume` mount's `Source` (the Mountpoint; an anonymous volume, a 64-hex name, is skipped
  and counted, because compose replaces it on recreate and the hub's `docker-volumes` plan excludes them,
  `docs/operations/hub-restore-inventory.md:93`), and each `type=bind` mount that is writable (`RW=true`) and a directory
  on the host (`test -d`); a read-only bind, a single file (tryton-crm's `./trytond.conf`), a socket or a `tmpfs` mount
  is not service data.
- **Database** — with `needs_database` (and no `infra.postgres: false`), the database `<db>` (by
  `app_role_check._db_name_for_spec`) is covered only when its per-database dump directory `/opt/backups/postgres/<db>/`
  EXISTS (visible to Backrest) and a trusted plan covers it — a directory that does not exist is a dump that is not
  happening, whatever plan covers its parent. The live `postgres-main` data volume does not count: copying a running
  PGDATA is a file-level copy of live database state, which the cited practice rules out (vol-3); the hub restore uses
  that volume opportunistically with a dump as the fallback (`docs/infrastructure/vps-hub-rebuild.md:171`,
  `scripts/bootstrap/bootstrap-hub.sh:1315`), so the dump is what must exist. The database is always checked **on the
  hub** (where `postgres-main` and `/opt/backups` live), whichever VPS the service runs on.

Then:

| Discovery says | Registrar (warn only) | Audit reports |
|---|---|---|
| a probe failed (SSH, docker, `config.json`, the visibility check) | warns | `unknown` |
| a plan tied to this spec — `<sid>-data` or `postgres-<db>` — with a path Backrest cannot stat | warns: paper plan, remove it | `drift` — "paper plan <id>: remove it" (listed with any other finding) |
| zero containers on the host | warns | `missing` — "not running on <host>" (an undeployed spec is not drift) |
| containers, no persistent path, database not engaged | warns: shape mismatch | `drift` — names the shape mismatch |
| a path no trusted plan covers | warns, naming the path | `drift` — "unprotected: <path>" |
| the database's dump directory is absent or not covered by a trusted plan | warns | `drift` — "database <db>: no dump covered" |
| everything covered by trusted plans | logs `covered by <plan ids>` | `present`, each path's covering plan in `actual` |

`present` means "configured and runnable": it says nothing about last night's run, which is W-43904006.

Cited practice: coverage verified as a signal rather than trusted from config (ledger cov-1, cov-3); a host-level restic
over `/var/lib/docker/volumes` is the field's lean pattern (vol-8); live DB state is dumped, never copied as files
(vol-3). One discovery function serves the registrar and the audit.

## Rejected alternatives

- **C — discover and always keep a per-service plan** (judges' second, 2 of 3): heals paper plans in place and, as the
  Fable critique noted, a per-service plan's failure NAMES the service while a `docker-volumes` failure does not. But on
  vps1 every named volume would be scanned by `docker-volumes` AND `<name>-data` every night — duplicate functionality the
  pack rule above forbids (brk-15, brk-18) — and a per-service plan over a removed volume becomes the next paper plan.
  Per-service restore stays available through restic's path filter on the host snapshot.
- **A with a write path** (the converged 2026-10-02 version: create or extend `<name>-data` for an uncovered path):
  rejected on the operator's ruling D-518 after both critiques — the write branch has no live use on today's fleet and its
  own failure modes (volume churn, a reimplemented restic exclude engine that has to be exact because it writes).
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
- Target host: only `deploy()` and `fabrik destroy` swap SSH to the spec's `target_vps` (`orchestrator/deployer_ssh.py:156-170`,
  `cli.py:972-974`); the registrars run after `deploy()` restored the hub host (`orchestrator/__init__.py:174-180`), and the
  audit reads one host, `FABRIK_AUDIT_VPS` (`audit.py:98`). Every persistent spec targets vps1 today.
- Consumers of the audit's status: the cron maps any status to gauges (`scripts/audit_all_registrars.py:85-107`),
  `fabrik audit-registrars` renders any status (`src/fabrik/cli.py:1430-1446`), and the post-deploy postcondition fails
  only on `missing` (`src/fabrik/verify.py:239-276`).

## The delta

- **D1 — discovery** (`drivers/backrest.py::discover_persistence(name) -> Persistence | None`, where `Persistence` holds
  `containers: int`, `paths: list[str]` and `anonymous: int`): the one `bash -o pipefail` SSH call above, parsed in
  Python; `None` when it fails. `name` is validated with the deployer's name pattern `^[a-z0-9][a-z0-9-]{0,62}$`
  (`orchestrator/deployer_ssh.py:31`) before it reaches a shell; `db_name` is validated with `_validate_db_name`
  (`drivers/backrest.py:307-315`) in D3, and an invalid one is reported as a finding.
- **D2 — plans, trust, coverage, visibility** (`read_plans() -> list[dict] | None` reads only `id`, `paths`, `excludes`,
  `iexcludes`, `backup_flags` and `schedule.disabled` with `jq` on the VPS — never the repo or credential fields;
  `visible(paths) -> set[str] | None`, `test -e` run INSIDE the Backrest container resolved by `^backrest(-|$)` behind an
  explicit empty-name guard; `trusted(plan, visible) -> bool` and `coverage(paths, plans, visible) -> {path: plan_id |
  None}`, pure functions with the rules above). `read_plans` also reads whether the plan has a schedule at all.
- **D3 — the shared check and the registrar**: `drivers/backrest.py::coverage_findings(name, db_name, *, target_host,
  hub_host) -> (status, findings, actual)` evaluates the table (paths on `target_host`, the database on `hub_host`,
  setting and restoring `FABRIK_VPS_SSH_HOST` itself — the one new host mechanism, a parameter pair replacing the
  deployer's env-swap context); it lives in the
  driver because `audit.py` already imports `fabrik.orchestrator.infrastructure` at module level (`audit.py:48`), so a
  helper in `audit.py` imported back by the orchestrator would cycle. `infrastructure.py::_provision_backrest` calls it
  outside any env swap — `target_host` from `ctx.target_vps` (`vps1` → the hub host), `hub_host` the hub host
  (`FABRIK_VPS_SSH_HOST`, default `vps`, read before any swap) — and logs the table's middle column; it calls no plan-writing function and records no resource.
  Under `dry_run` it makes no SSH call.
- **D4 — audit** (`audit.py::audit_backrest`): the table's right column, through the same `coverage_findings`;
  the host is `fabrik destroy`'s order without the CLI flag — `<FABRIK_ROOT>/.fabrik/state/<id>.json` `target_vps`, then
  the spec field, then `vps1` (`cli.py:955-970`); `vps1` maps to `FABRIK_AUDIT_VPS` (default `vps`, `audit.py:98`) so
  the backrest audit honours the same host override as every other audit. `missing` now means "not running on the host"; `_missing_host_paths`
  (`audit.py:314-328`) is replaced by `visible`.
- **D5 — heal the live paper plans**: the audit's report lists every paper plan tied to a spec. Removing them is a
  delete of production backup config, so it is an operator-gated rollout step (Validation 4) using the existing
  `remove_backup_plan` (which writes a timestamped `.bak` first, `drivers/backrest.py:157-182`). No code this spec adds
  writes, edits or deletes a plan.

## Contract deltas

None: no data contract, no UI. `audit_backrest` keeps the `AuditResult` shape; `missing` changes meaning to "not running
on the host". Mirror on the post-deploy postcondition (`verify.py:239-276`, fails only on `missing`): right after a
deploy the containers exist, so a `missing` there now means discovery could not find them — the postcondition fails
loudly; an uncovered path is `drift` and passes, as today's paper-plan drift does. Mirror on new services: a service
whose data no host plan covers gets a warning and an hourly `drift`, never a plan of its own — adding the covering host
plan is the operator's call.

## Cost

No new service, no new plan (the paper plans go away). Three SSH calls per apply and per hourly audit of a persistent
spec (discovery, plans, visibility on the target host), plus two for a database-backed one (plans and visibility on the
hub); `read_plans` may be cached per host per sweep later if it shows in the cron's runtime.

## Validation

1. **Red first** — tests in `tests/test_backrest_coverage.py` (new) and `tests/test_audit.py`: trust and coverage over a
   table (exact path, parent path, trailing slashes, sibling prefix `/opt/a` vs `/opt/ab`, an excluded ancestor, a bare
   name, a bracket pattern, `iexcludes`, `backup_flags`, a disabled schedule, a plan with one unreachable path);
   discovery parsing (volume, writable bind dir anywhere, read-only bind, file and socket skipped, zero containers,
   name fallback, probe failure → `None`); each registrar row, asserting no plan-writing function and no resource in any
   branch; each audit row. Each written first and seen red against today's code.
2. **Pre-merge read-only probe (operator-gated)** — before infra merges, the operator runs or approves one read-only
   probe of vps1 (plan `id/paths/excludes/iexcludes/backup_flags/schedule` via `jq`, and `docker inspect` of Backrest's
   mounts), because the first hourly run after the merge already alerts. This settles the Open unknowns as facts.
3. **Report on vps1 (read-only, after merge)** — one `scripts/audit_all_registrars.py` run; its backrest rows must show
   tryton-crm and zitadel as `paper plan` drift with their real paths covered, and list any other paper plan.
4. **Operator-gated heal** — on the operator's go, `remove_backup_plan` for each listed paper plan; the next hourly run
   shows `present` for both and `FabrikRegistrarDrift` resolves.

## Decisions taken

- Approach A (coverage check) over C and B, by a unanimous judge panel; check-and-warn only, on the operator's ruling
  D-518 after the Opus 5.5 and Fable 5.1 critiques; reversible (three files).
- A plan is trusted only when Backrest can run it over the path (D2); the database is covered only by its per-database
  dump directory, which must exist, checked on the hub — never by a plan id or a live-volume copy (vol-3).
- No code writes, edits or deletes a plan; removing paper plans is operator-gated (D5). `has_persistent_data` keeps its
  meaning and its 21 specs are not edited.
- The approval row is minted at the approval gate (`/fabrik-plan-review`; this spec is `Size: small`).

## Lifecycle

- **First run:** the pre-merge probe (Validation 2), the read-only report (3), then the one-time operator go (4).
- **Growth:** three SSH calls per persistent spec per hour, five for a database-backed one (21 persistent today, 15 of
  them database-backed). Trigger to revisit: a spoke hosting a persistent
  service (its paths read `unprotected`) — then the spoke's Backrest gains the `/var/lib/docker/volumes` and
  `/opt/backups` binds and a `docker-volumes-<vps>` plan (deferred today, `vps-complete-inventory.md:666`); or the cron's
  runtime grows enough to cache `read_plans` per host.
- **Failure:** a removed, disabled or flag-bearing host plan uncovers every service at once — the next hourly audit
  reports each path `drift`; a probe failure is `unknown`, never a false `present` (an alert on long-lived `unknown` is
  W-efe1b6b5).
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
| I8 | rollback removes a plan it did not create (found while grounding) | IN | moot: the registrar records no resource (D3) |
| I9 | Backrest's own Prometheus metrics / empty-snapshot detection (restic `summary.total_files_processed`, cov-5) | OUT-OF-SCOPE | W-43904006 (backlog: alert on an empty or stale Backrest snapshot) |
| I10 | the four test specs with `has_persistent_data` and nothing to persist | OUT-OF-SCOPE | the audit's shape-mismatch drift names them; correcting their flags is a spec edit for their owners when deployed |
| I15 | the `30-ops` checklist line (fleet-synced, infra's beat) | IN | Documentation landing sites — a proposal to infra, never an edit here |
| I16 | `refresh_infrastructure` never sets `ctx.target_vps` (found at plan-review pass 2) | OUT-OF-SCOPE | W-c5b9397b |
| I12 | services that mount volumes but do not set `has_persistent_data` (job-agent `job-agent-data`, seo `cost_wal` — Opus critique, verified) | OUT-OF-SCOPE | W-c60d5708 |
| I13 | no alert fires on a long-lived backrest `unknown` (Opus critique) | OUT-OF-SCOPE | W-efe1b6b5 |
| I14 | the two independent design critiques (Opus 5.5, Fable 5.1), operator: *"revise"* | IN | Chosen approach (check-and-warn), D2 trust rules, database rule, bind discovery, Validation 2; D-518 |
| I11 | the Apprise hook URL's Coolify-era name (`vps-complete-inventory.md:661`) | OUT-OF-SCOPE | already resolved — Issue 1, RESOLVED 2026-07-12 (`vps-complete-inventory.md:687`); the driver's hook targets `apprise:8000` (`drivers/backrest.py:93-104`) |

## Constraints digest

| Rule | Verbatim | Source | Applies |
|---|---|---|---|
| Volume data | "If the data is a volume, say so in the spec comment and rely on the global `docker-volumes` plan; never let a service-named plan be mistaken for the protection." | `.windsurf/rules/core/30-ops.md:222-223` | the whole approach |
| DB backups | "Backups managed via Backrest → Backblaze B2 (registered by `fabrik apply` when `shape.needs_database: true`)." | `.windsurf/rules/core/25-data-postgres.md:332` | the database is covered only by its per-database dump, reached on the hub |
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
- `docs/infrastructure/vps-complete-inventory.md` § Backups — the registrar no longer creates per-service plans; the audit
  names uncovered paths and paper plans.
- `.windsurf/rules/core/30-ops.md:219-223` — the checklist line becomes true of the code; its wording is infra's beat
  (fleet-synced), so a fabrik-mail to infra proposes the edit; this spec does not edit the pack.
- `INDEX.md` (new test file), `CHANGELOG.md`, `docs/reference/research/` (this ledger).

## Open / blocking unknowns

- **Open — vps1's live plan list, plan flags and Backrest mounts today.** The docs (2026-06-02) and the tryton-crm deploy
  plan agree on `docker-volumes`/`opt-configs`/`postgres-dumps` and the path-preserving binds; a read-only probe this
  session was refused by the auto-mode classifier (production reads). Resolution: Validation 2, the operator-gated
  pre-merge probe; if a host plan is missing or untrusted, the report says `drift`, never a false `present`.
- **Open — a future compose that sets `name:`**. Resolution: the name fallback catches its containers; a miss reads
  `missing` ("not running"), which fails the post-deploy postcondition loudly, never silence.
- **Open — whether vps1 carries the per-database dump patch** (`docs/operations/deployment.md:512-545`). Resolution:
  Validation 2 shows it; without it every database-backed service reads `database <db>: no dump covered` and each
  `postgres-<db>` plan reads as a paper plan — a true report, and applying the patch is the operator's one-time step.
- **Resolved:** what Backrest does with a missing path (fails the run, brk-5/brk-7); whether overlapping plans copy data
  twice (no, dedup, brk-15; they do scan twice, brk-18); where the registrar's SSH goes (vps1 today; D3 moves the backrest
  calls to `target_vps`); compose project names (0 of 39 `/opt/*/compose*` files set `name:`).
