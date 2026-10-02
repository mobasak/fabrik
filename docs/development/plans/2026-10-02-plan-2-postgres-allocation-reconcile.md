# Plan — postgres allocation registry reconciled by the hourly audit (W-714ae2cf, D-498)

Status: CONVERGED (/fabrik-plan-review 2026-10-02, 4 passes; spec graded together, Size: small)
Profile: small
**Owner:** fleet

Spec: `docs/superpowers/specs/2026-10-02-postgres-allocation-reconcile-design.md` (DRAFT, `Size: small`, `Profile: delta` —
`/fabrik-plan-review` grades its sections together with this plan and flips both). Research ledger:
`docs/reference/research/2026-10-02-postgres-allocation-reconcile-ledger.md` (28 rows). Work item: W-714ae2cf. Ruling:
D-498. Estimated diff: ≈230 code lines in 5 code files, tests excluded (`spec § Size`).

## What this plan is

Three inline phases (the orchestrator codes each itself in the worktree; no coder is dispatched):

- **A — registry primitives:** `register_allocation_if_absent(...)` decided inside the lock, and `audit_postgres` reading
  the registrar's name rule from the existing helper.
- **B — the reconcile and the cron:** a new `src/fabrik/registry_reconcile.py`, wired into
  `scripts/audit_all_registrars.py` with the mode switch, the three new series and the `PUT` push.
- **C — alerts, docs and Finish:** two alert rules validated by `promtool`, the doc landing sites, the heavy
  `/fabrik-review` over the whole-plan diff, and the rollout steps the operator runs.

Per phase: `/fabrik-review-scoped` on that phase's surface. At Finish: one heavy `/fabrik-review` (the
`/fabrik-execute-plan` D7 floor) and one receipt.

## Intake Inventory

| I# | Item (anchored) | Disposition | Where |
|---|---|---|---|
| I1 | *"we must rule out 3 ways in your work revise"* (D-498) | IN | `spec § Why this exists`; causes 1-2 → Phases A-B; cause 3 already closed (ea99ee94f, f9475148a) |
| I2 | *"register existing unregistered databases"* | IN | Phase B (the reconcile) |
| I3 | *"retry failed registrations"* | IN | Phase B (every hourly run retries; A's in-lock check keeps it idempotent) |
| I4 | *"surface the failure"* | IN | Phase B (series) + Phase C (rules) |
| I5 | *"then register zitadel and site_provisioner through it"* | IN | Phase C, operator-run rollout steps R0-R4 |
| I6 | *"why there is orphan postgres databases exist"* | IN | `spec § Why this exists` (answered there; no code) |
| I7 | the backrest half of the drift alert | OUT-OF-SCOPE | W-5c4ad6a6 |
| I8 | databases no spec claims | OUT-OF-SCOPE | W-78d2a2df |
| I9 | stale entries (entry without a database) | OUT-OF-SCOPE | stays a reported drift (`spec § The delta` D3) |
| I10 | `fabrik reconcile-all` is dead on the retired Coolify API | OUT-OF-SCOPE | W-ef765f8d |
| I11 | `agents-fabrik.md:413` describes the registry's writer | OUT-OF-SCOPE for this plan | a governance-sync trigger (the `.pre-commit-config.yaml` `governance-sync` filter matches it, verified this run); its sentence stays TRUE (the reconcile writes through the same `register_allocation`), so this plan does not ship a fleet-wide sync for it — `docs/infrastructure/vps-complete-inventory.md` carries the change |

## What we already agreed (citations, not restatement)

- Goal, causes and the operator's words: `spec § Goal`, `spec § Why this exists`, `spec § Personas`.
- Chosen approach (B) and the judge panel's 2-1 split with the refuted dissent: `spec § Chosen approach`.
- Rejected A, C, a new cron, a Postgres-table registry: `spec § Rejected alternatives`.
- The six deltas D1-D6: `spec § The delta`. The spec's D1 names the existing helper
  `app_role_check._db_name_for_spec` (`src/fabrik/app_role_check.py:782-804`); D5 names the `PUT` push.
- What exists today: `spec § What exists today (grounded)`.
- Validation and the rollout order: `spec § Validation`.
- Decisions taken (owner, recorded user, never delete): `spec § Decisions taken`.
- The approval row is minted by `/fabrik-plan-review` at its gate (a `Size: small` spec is approved there, not here).

## Global Constraints (every phase inherits these)

- The reconcile never deletes, renames or creates a database, and never touches an entry whose database is missing
  (`spec § The delta` D3). It writes only through `register_allocation_if_absent(...)`, only for a database exactly one
  spec claims, and only with an owner role read from `pg_database`.
- No new dependency: `PyYAML`, `fabrik.drivers.postgres` and `fabrik.audit` are already importable; `pyproject.toml`
  and `uv.lock` are not touched (`core/10-python.md`).
- Config by env var only: `FABRIK_REGISTRY_RECONCILE` read with `os.getenv("FABRIK_REGISTRY_RECONCILE", "report")`
  (`.windsurf/rules/core/35-security-auth.md:267`); the default and any unknown value are `report` (fail safe: never
  write on a typo or before the operator opts in) and an unknown value is logged.
- 12-Factor on this surface: **III** one granular env var, no grouped config; **IV** the registry and `postgres-main`
  are reached through the existing driver, unchanged; **XI** the script logs to stdout through `logging` as today (cron
  redirects it); **XII** the reconcile is an admin process running from the deployed hub release (`/opt/fabrik/src`),
  never from a laptop; **II/V/VI/VII/VIII/IX/X** — not engaged.
- No silent action: every heal emits a series sample and one log line naming the database (`self-healing.md:96`); a
  caught exception is counted, never swallowed (`self-healing.md:73`, `58-resilience.md:408`).
- Tests: watched-fail-first for every behaviour this plan adds (`core/45-testing-strategy.md:22`); no test reaches a
  VPS — `ssh` and `_run_sql` are patched, and the existing conftest guard refuses real SSH.
- Seats never mutate git state (read-only git only); never read `~/.claude*`; never run `fabrik apply`, never SSH, never
  push metrics. The shared `.venv` imports `fabrik` from `/opt/fabrik/src` — every test run exports
  `PYTHONPATH=/opt/fabrik/.claude/worktrees/fleet/src`.
- **Operator-gated steps are never executed by an agent:** reading the first report run, adding
  `FABRIK_REGISTRY_RECONCILE=apply` to the hub crontab, and `scripts/sync_prometheus_to_vps.sh` (Phase C, R0-R4). The
  default `report` makes the code enforce that nothing writes before the operator's R2.

## Context Ledger

| Source | What binds | Grounded ref |
|---|---|---|
| `.windsurf/rules/core/10-python.md` (MATCHED) | no deps-file edit; `uv` is the package manager | `core/10-python.md` |
| `.windsurf/rules/core/35-security-auth.md` (FLOOR) | config via env vars only | `core/35-security-auth.md:267` |
| `.windsurf/rules/core/25-data-postgres.md` (FLOOR) | own database = a database on `postgres-main` | `core/25-data-postgres.md:26` |
| `.windsurf/rules/core/self-healing.md` (MATCHED via `**/health*`) | no silent action; a new self-healing response gets its ladder row first — proposed to infra, the pack owner (Phase C step 1) | `self-healing.md:73`, `:96`, `:64` |
| `.windsurf/rules/core/58-resilience.md` | count a fail-open | `58-resilience.md:408-410` |
| `.windsurf/rules/core/45-testing-strategy.md` | watched-fail-first | `45-testing-strategy.md:22` |
| `fabrik-lib` | none — no module covers hub control-plane reconciliation | `spec § fabrik-lib verdict` |
| `agents-fabrik.md` | registry contract (read-only here; sync trigger) | `agents-fabrik.md:413` |
| `specs/services/*.yaml` `shape:` | no flag changes; `needs_database` is what the reconcile reads | `spec § Shape / infra implications` |

## Constraints Digest (verbatim rows from the MUST-READ packs)

| Verbatim | file:line | Rule |
|---|---|---|
| "Silent swallow is data loss; you've removed the only signal a watchdog could see." | `.windsurf/rules/core/self-healing.md:73` | No silent swallow |
| "Each step emits a Prometheus counter + a structlog row carrying the resource name (no silent action)." | `.windsurf/rules/core/self-healing.md:96` | No silent action |
| "Say it out loud, and COUNT it." | `.windsurf/rules/core/58-resilience.md:408` | Count fail-open |
| "Mandate: config via env vars only (`os.getenv("KEY", "default")`)" | `.windsurf/rules/core/35-security-auth.md:267` | Config |
| ""Own database" means a DATABASE on `postgres-main`, never a database SERVER" | `.windsurf/rules/core/25-data-postgres.md:26` | Shared server |
| "**Watched-fail-first** (for tests this change adds or modifies" | `.windsurf/rules/core/45-testing-strategy.md:22` | Red first |
| "**`uv`** is the mandated Python package manager. Never use raw `pip`, `pip install`, `poetry`, or `pipenv`." | `.windsurf/rules/core/10-python.md:22` | Package manager |
| "The app writes structured events, unbuffered, to `stdout` and **nothing else**." | `.windsurf/rules/core/55-observability.md:72` | Logs to stdout |
| "**No skipped heading levels** — `##` to `###`, never `##` to `####`" | `.windsurf/rules/core/40-documentation.md:241` | Doc headings |
| "one-off admin processes should be run in an identical environment as the regular long-running processes of the app" | `.windsurf/rules/core/30-ops.md:430` | Admin processes |

## Phase A — Registry primitives — ✅ EXECUTED 2026-10-02 (96ca25289, review fixes aec09c11a; /fabrik-review-scoped closed 2 rounds 5→0)

Appetite: 35

**Interfaces — Produces:**
- `src/fabrik/drivers/postgres.py` (today `register_allocation` is `:1870-1923`):
  - a private `_register(db_name, entry: dict, *, if_absent: bool, dry_run: bool) -> tuple[dict[str, Any], bool]` holding
    today's body — `file_lock("postgres-allocations")`, `_load_remote_allocations()`, then, when `if_absent` and
    `db_name` is already in `allocations`, return `(payload, False)` with nothing written; otherwise set the entry, write
    unless `dry_run`, and return `(payload, True)`;
  - `register_allocation(db_name, *, spec_id, user="postgres", owner="fabrik", notes="", dry_run=False) -> dict[str, Any]`
    keeps its signature and return value and calls `_register(..., if_absent=False, ...)[0]`; its three callers
    (`:359`, `:453`, `:2139`) are unchanged;
  - new `register_allocation_if_absent(db_name, *, spec_id, user, owner, notes) -> bool` — `True` when it wrote, `False`
    when an entry already existed (decided inside the lock, so a concurrent writer's entry is never overwritten).
- `src/fabrik/audit.py::audit_postgres(spec)` (`:137-224`): the database name comes from
  `fabrik.app_role_check._db_name_for_spec(_spec_to_dict(spec))` instead of `sid.replace("-", "_")` (`:140`), then
  `fabrik.drivers.postgres._validate_identifier(db_name, "database")` before the SQL at `:150-153` (because
  `Depends.postgres` carries no pattern, `src/fabrik/spec_loader.py:183`; the `nosec` comment is reworded to name the
  validation). A `SpecResolutionError` or a `ValueError` from validation returns
  `AuditResult(status="unknown", detail=<the error>)`. The result's `actual` keeps its keys (`db_name`, `found`,
  `registry_entry`, `in_registry` — `:180-183`), which Phase B reads.
- **Mirror (named):** a spec that sets `depends.postgres` is now audited under that name. **9 of the 23
  postgres-applicable specs move** (probe in Evidence § Phase A): `ai-model-catalog`, `compliance-ops`, `exam-coach`,
  `gmail-account-creator` → `main`; `calendar-orchestration-engine` → `calendar_engine`; `evolution-api` → `evolution`;
  `fabrik-citation-verifier` → `citation_verifier`; `tryton-crm` → `tryton`; `youtube` → `youtube_pipeline`. Each row can
  move in either direction: to `present` or `drift` when the named database exists, or to `missing` when it does not
  (a live database still under the derived name — the registrar's rename guard, `orchestrator/infrastructure.py:729-740`,
  keeps that case possible). Rollout R1 reads every one. `audit.py` gains a module-level import of
  `fabrik.app_role_check`; no cycle (the orchestrator imports that module lazily, inside functions — `:512`, `:1076`;
  verified by the import step below).

**Consumes:** nothing.

1. **Write the failing tests first** in `tests/test_postgres_registry.py` (rows A1-A4 below, in order), using the file's
   existing `ssh` fake pattern (`tests/test_postgres_registry.py:64-68`, `SEED_PAYLOAD` `:44-60`). Run them and confirm
   they fail for the right reason (`AttributeError: ... register_allocation_if_absent`; the audit tests reading the wrong
   name and accepting a bad identifier).
2. Edit `src/fabrik/drivers/postgres.py` per the Interfaces: extract `_register`, keep `register_allocation`'s contract,
   add `register_allocation_if_absent`.
3. Edit `audit_postgres` per the Interfaces; keep `_spec_to_dict` (`audit.py:67-74`) as the adapter, and resolve and
   validate the name only AFTER the `n/a` return (`audit.py:139-142`), so a non-applicable spec stays `n/a`.
4. Run green: `cd /opt/fabrik/.claude/worktrees/fleet && PYTHONPATH=$PWD/src .venv/bin/python -m pytest
   tests/test_postgres_registry.py tests/test_app_role_driver.py tests/test_backrest_postgres_plan.py
   tests/drivers/test_postgres.py tests/test_audit.py -q -p no:cacheprovider` → all pass; and the import check
   `PYTHONPATH=$PWD/src .venv/bin/python -c "import fabrik.audit, fabrik.orchestrator.infrastructure, fabrik.cli"` → exit 0.
5. Prove red on revert in a throwaway worktree (`git worktree add --detach <scratch>/pa HEAD`, copy the edited files and
   the test, neuter the in-lock `if_absent` branch of `_register`, watch row A1 fail; restore it, drop the
   `_validate_identifier` call, watch row A4 fail; remove the worktree).
6. `python scripts/enforcement/check_doc_sync.py` (no doc row is keyed by this phase).
7. **`/fabrik-review-scoped`** on Phase A's surface (`src/fabrik/drivers/postgres.py`, `src/fabrik/audit.py`,
   `tests/test_postgres_registry.py`), run to its closing pass confirming 0 — BLOCKING before Phase B.
8. Commit Phase A (explicit paths + provenance trailers, `Agent-Phase: A`), push.

### Behavior Contract — Phase A
- **Given** an existing entry for a database, **When** `register_allocation_if_absent(db, ...)` runs, **Then** it returns `False`, makes no write and the entry is unchanged (A1; `src/fabrik/drivers/postgres.py:1870`; `spec § The delta` D2)
- **Given** no entry for a database, **When** `register_allocation_if_absent(db, ...)` runs, **Then** it returns `True` and the entry is written with the given fields (A2; `src/fabrik/drivers/postgres.py:1870`)
- **Given** a spec with `depends.postgres: other_db`, **When** `audit_postgres` runs, **Then** it checks `other_db`, not the snake-cased id (A3; `src/fabrik/audit.py:140`; `spec § The delta` D1)
- **Given** a spec whose `depends.postgres` is not a valid identifier, **When** `audit_postgres` runs, **Then** it returns `unknown` and runs no SQL (A4; `src/fabrik/audit.py:150`)

## Phase B — The reconcile and the cron — ✅ EXECUTED 2026-10-02 (cfd9d3cbd, review fixes b56c41c05; /fabrik-review-scoped closed 2 rounds 8→0)

Appetite: 70

**Interfaces — Produces:**
- `src/fabrik/registry_reconcile.py` (new; a `# AFTER-EDIT: docs/reference/health-monitoring.md` comment in its first 25
  lines, checked by `grep -n "AFTER-EDIT" src/fabrik/registry_reconcile.py` because `check_script_headers.py` grades only
  `scripts/**`):
  - `@dataclass HealResult: spec_id: str; db: str; outcome: Literal["registered", "already-present", "would-register",
    "shared", "failed"]; reason: str = ""`.
  - `def mode() -> Literal["apply", "report", "off"]` — reads `os.getenv("FABRIK_REGISTRY_RECONCILE", "report")`; any
    other value → `"report"` with one warning log. **The default is `report`**: nothing writes until the operator sets
    `apply` on the crontab line (rollout R2).
  - `def reconcile_postgres(audits: dict[str, dict[str, AuditResult]], claims: dict[str, list[str]], *, claims_complete:
    bool, dry_run: bool) -> list[HealResult]` — `audits` maps spec id → `audit_all` result; `claims` and
    `claims_complete` come from the script (below). For each spec id whose `postgres` result is `drift` with `actual["found"] is True`
    and `actual["in_registry"] is False` (`audit.py:197-202`), with `db = actual["db_name"]`:
    1. the claim map comes from the specs, never from audit outcomes: `claims(specs) -> tuple[dict[str, list[str]],
       list[str]]` returns (the map `_db_name_for_spec(spec.model_dump())` → spec ids over every loaded spec whose postgres
       registrar applies, whatever its audit returned — an `unknown` or skipped sibling still counts; the ids whose name
       failed to resolve, never raising). When `claims_complete` is false (a spec failed to load or audit, or a database
       spec failed to resolve its name), every candidate gets `failed`, reason `claims-unresolved`, and nothing is written
       — the provisioner raises rather than guess in the same case (`orchestrator/infrastructure.py:506-508`). Otherwise
       a `db` with two or more claimants gets `shared` (reason: the other spec ids, comma-joined) and nothing is written
       (`orchestrator/infrastructure.py:500-547`);
    2. else `dry_run` → `would-register`;
    3. else `user = _db_owner(db, POSTGRES_CONTAINER)` (`postgres.py:572`, `:62`); `None` (the database is gone, or its
       owner fails validation) → `failed`, reason `owner-unresolved`, no write;
    4. else `register_allocation_if_absent(db, spec_id=spec_id, user=user, owner="fabrik", notes="registered by the hourly
       reconcile " + datetime.now(UTC).date().isoformat())` → `registered` when it returns `True`, `already-present` when
       `False`;
    5. any exception in 3-4 → `failed`, reason `type(exc).__name__`.
    One log line per result. It reads only the audit results the cron computed, plus `_db_owner`.
- `scripts/audit_all_registrars.py`:
  - `main` (`:129-181`) keeps a `specs: dict[str, Spec]` beside `results` and builds `audits = dict(results)`; after the
    audit loop it computes `claim_map, unresolved = registry_reconcile.claims(specs.values())` and
    `claims_complete = error_count == 0 and not unresolved` (no spec failed to load or audit, no database spec's name
    failed to resolve); `m = registry_reconcile.mode()`; when `m != "off"`,
    `heals = reconcile_postgres(audits, claim_map, claims_complete=claims_complete, dry_run=(m == "report"))`, then re-run
    `audit_all(specs[sid])` only for `registered` results and replace them in `results`.
  - `_render_metrics(results, heals, *, success: bool, spec_errors: int)` (`:72-102`) keeps both existing gauges and adds
    `fabrik_registry_heal_total{spec_id,db,outcome} 1` per heal, `fabrik_registry_heal_failed{spec_id,db,reason} 1` per
    failed heal, `fabrik_audit_spec_errors <error_count>` every run, and `fabrik_audit_last_success_timestamp_seconds
    <unix time>` only when `success` = the audit loop had `error_count == 0` and the reconcile raised nothing uncaught.
  - `_push_to_gateway` (`:105-126`): the remote curl gains `-X PUT` (`:119`), replacing the whole `fabrik-audit` group each
    run (`spec § The delta` D5; ledger obs-8).
- **Mirror (named):** `PUT` replaces every series in the group. (a) The script is the group's only pusher inside this repo
  (`PUSHGATEWAY_JOB = "fabrik-audit"`, `scripts/audit_all_registrars.py:63`, is the only definition — Evidence § Phase B);
  a pusher outside the repo is beyond that grep. (b) A spec skipped by a load or audit error loses its
  `fabrik_audit_drift_total` series for that run (under `POST` it kept its last value), so a firing `FabrikRegistrarDrift`
  for it can resolve; the run therefore pushes `fabrik_audit_spec_errors` and withholds the last-success timestamp, and
  `FabrikAuditStale` names it. (c) A run that crashes before the push changes nothing in the pushgateway, as today; a run
  that pushes without the timestamp deletes the timestamp series, which Phase C's rule covers with `absent(...)`.

**Consumes:** Phase A's `register_allocation_if_absent` and `audit_postgres`'s `actual` keys.

1. **Write the failing tests first** in a new `tests/test_registry_reconcile.py` (rows B1-B7 below). Two patch sets, each
   on the module that owns the name: the reconcile's unit tests import `fabrik.registry_reconcile` normally and patch
   `_db_owner` there and `ssh` on `fabrik.drivers.postgres` (the real `register_allocation_if_absent` runs against the
   file's `ssh` fake, so the in-lock path is exercised); the script's wiring tests load it with
   `importlib.util.spec_from_file_location("audit_all_registrars", <repo>/scripts/audit_all_registrars.py)` and patch
   `audit_all`, `load_spec`, `subprocess.run` (the push) and `registry_reconcile.mode` / `registry_reconcile.reconcile_postgres`
   on that module. No SSH, no network. Confirm red (`ModuleNotFoundError: fabrik.registry_reconcile`, then each missing
   behaviour).
2. Create `src/fabrik/registry_reconcile.py` per the Interfaces.
3. Edit `scripts/audit_all_registrars.py` per the Interfaces; keep its exit codes (`:44-45`).
4. Run green: `PYTHONPATH=$PWD/src .venv/bin/python -m pytest tests/test_registry_reconcile.py tests/test_postgres_registry.py
   -q -p no:cacheprovider` → all pass. Lint: `.venv/bin/ruff check src/fabrik/registry_reconcile.py
   scripts/audit_all_registrars.py tests/test_registry_reconcile.py` → clean.
5. Prove red on revert in a throwaway worktree for B2 (call `register_allocation` instead of
   `register_allocation_if_absent` in the reconcile) and B5 (drop `-X PUT`), each watched failing, then remove the worktree.
6. `python scripts/enforcement/check_doc_sync.py`; `grep -n "AFTER-EDIT" src/fabrik/registry_reconcile.py` → one line.
7. **`/fabrik-review-scoped`** on Phase B's surface (`src/fabrik/registry_reconcile.py`, `scripts/audit_all_registrars.py`,
   `tests/test_registry_reconcile.py`), run to its closing pass confirming 0 — BLOCKING before Phase C.
8. Commit Phase B (`Agent-Phase: B`), push.

### Behavior Contract — Phase B
- **Given** a spec whose database exists with no registry entry, **When** the reconcile runs in `apply` mode, **Then** it registers the database with the owner role read from `pg_database` and outcome `registered` (B1; `src/fabrik/drivers/postgres.py:572`; `spec § The delta` D3)
- **Given** an entry exists by the time of the locked write, **When** the reconcile runs, **Then** the entry is left untouched and the outcome is `already-present` (B2; `src/fabrik/drivers/postgres.py:1870`)
- **Given** `FABRIK_REGISTRY_RECONCILE` unset, `report` or an unknown value, **When** the cron runs, **Then** nothing is written and each orphan reports `would-register`; with `off` the reconcile does not run (B3; `spec § The delta` D4)
- **Given** a registry write raises, or the owner lookup returns nothing, **When** the reconcile runs, **Then** the outcome is `failed` with the reason, nothing is written, a `fabrik_registry_heal_failed` sample is rendered and the run still renders its other series (B4; `spec § The delta` D5)
- **Given** a run with no spec errors whose reconcile raises nothing, **When** the cron pushes, **Then** it uses `PUT` and the payload carries `fabrik_audit_last_success_timestamp_seconds`; a run with a spec error, or whose reconcile raises, renders no timestamp and renders `fabrik_audit_spec_errors` (B5; `scripts/audit_all_registrars.py:119`)
- **Given** a stale entry (entry, no database) or a `missing` result, **When** the reconcile runs, **Then** it writes nothing and returns no result for it (B6; `src/fabrik/audit.py:197-203`; `spec § The delta` D3)
- **Given** two specs that resolve to the same orphan database — including when one of them audits `unknown` — **When** the reconcile runs in `apply` mode, **Then** the orphan gets outcome `shared`, naming the other, and nothing is written; when a spec's `depends.postgres` is not a string, `claims()` lists its id in `unresolved` without raising; and when `claims_complete` is false, every candidate gets `failed claims-unresolved` and nothing is written (B7; `src/fabrik/orchestrator/infrastructure.py:500`; `spec § The delta` D3)

## Phase C — Alerts, docs and Finish

Appetite: 45

**Interfaces — Produces:**
- `configs/prometheus/rules/fabrik-drift.yml` gains, in the existing group (`:9-12`):
  - `FabrikRegistryHealFailed`: `expr: max by (spec_id, db) (fabrik_registry_heal_failed) > 0` (aggregated so a changing
    `reason` label does not reset the window), `for: 2h`, `severity: warning`, `alert_class: registrar_drift`, annotation
    naming `{{ $labels.db }}`;
  - `FabrikAuditStale`: `expr: (time() - max(fabrik_audit_last_success_timestamp_seconds) > 10800) or
    absent(fabrik_audit_last_success_timestamp_seconds)`, `for: 5m`, `severity: warning`, `alert_class: registrar_drift`,
    annotation pointing at `/var/log/fabrik-audit-all.log` and `fabrik_audit_spec_errors`. The `absent(...)` arm covers a
    pushed run that carried no timestamp (a `PUT` deletes the series) and the time before the first success — so a run
    with a spec error raises this alert within minutes, not after 3 h; the health-monitoring doc (step 4) says so.
- Docs (the `spec § Documentation landing sites`): `docs/reference/health-monitoring.md` § Hourly Per-Registrar Drift
  Alert (`:250-268`); `docs/infrastructure/vps-complete-inventory.md` § Postgres allocation registry (`:815-835`);
  `docs/CONFIGURATION.md` (the `FABRIK_` reference table, `:935`); `.env.example` (§ Fabrik Internal, `:252-289`);
  `INDEX.md` rows for the new module and test; `CHANGELOG.md` (both governance files: orchestrator-applied, outside File
  Scope by the plan grammar).

**Consumes:** Phase B's series and `FABRIK_REGISTRY_RECONCILE`.

1. Propose the ladder row to the pack owner (`self-healing.md:64`: "add the row to this pack first"): `python
   scripts/mail.py send --to fabrik --to-agent infra --kind request` with the D-035 contract, proposing the row
   "registry drift → hourly additive reconcile → `FabrikRegistryHealFailed`" for `.windsurf/rules/core/self-healing.md`
   (a fleet-synced surface this plan does not edit). Probe the toolchain: `docker --version` → present (`which promtool`
   → not found on the hub, so `promtool` runs from the image vps1 runs, `configs/monitoring-compose.yaml:47`).
2. **Write the failing tests first** in `tests/test_registry_reconcile.py` (rows C1-C2): load the rule file with
   `yaml.safe_load` and assert both new alerts exist with the named `expr` and `for`; and a promtool rule unit test file
   `tests/fixtures/fabrik-drift-rules-test.yml` covering the stale-by-age case, the absent case and a heal failure whose
   `reason` changes mid-window, run by C3's docker command (each `exp_alerts` entry lists its `exp_annotations`, which
   promtool compares). Confirm red.
3. Add the two rules per the Interfaces. Run green; then `docker run --rm -v "$PWD/configs/prometheus/rules:/r:ro" -v
   "$PWD/tests/fixtures:/t:ro" --entrypoint promtool prom/prometheus:v3.2.1 check rules /r/fabrik-drift.yml` →
   `SUCCESS: 3 rules found`, and the same image with `test rules /t/fabrik-drift-rules-test.yml` → `SUCCESS`.
4. The doc edits per the Interfaces; `INDEX.md` and `CHANGELOG.md` through the shared-append private-index recipe of
   `CLAUDE.md` § Behavior (the shared-repo bullet). Then `python scripts/enforcement/check_doc_sync.py`, `python
   scripts/render_doc_script_links.py --check`.
5. **`/fabrik-review-scoped`** on Phase C's surface (the rule file, the promtool fixture, the four docs, the test), run to
   its closing pass confirming 0.
6. **Finish — the heavy `/fabrik-review`** over the whole-plan diff (`git diff <phase-A base>..HEAD`): the D7 floor — at
   least one Opus authoritative seat plus one Sonnet and one Haiku seat per independent failure-class group, sized by
   `python3 /opt/fabrik/scripts/sysadmin/dispatch_headroom.py --units <groups>` and stamped with
   `python3 scripts/command_run.py dispatch --seats <n>` before they go out; the receipt at
   `docs/development/reviews/2026-10-02-plan-2-postgres-allocation-reconcile-review.md` embedding the verbatim
   `final_gate.py --json` success. Then `/fabrik-docs-review` over the four docs.
7. The full gate: `python scripts/final_gate.py --check --json` → `"status": "success"`, and
   `python scripts/enforcement/check_convergence.py` → exit 0. A green gate is necessary, not sufficient — the Evidence is
   the proof.
8. Commit Phase C (`Agent-Phase: C`), push, then `python3 scripts/merge_request.py request --review <the receipt>
   --item W-714ae2cf` and send the printed `SendMessage` line.

**Rollout — OPERATOR-GATED, never executed by an agent (after infra merges into master).** With the default `report`, the
hourly cron writes nothing until R2, so the order R1 → R2 is enforced by the code, not by timing. The `PUT` push, in
contrast, is live from the merge's first hourly run, and under `PUT` a skipped spec's drift series is absent from that
run, so its `FabrikRegistrarDrift` can resolve; `FabrikAuditStale` is what names that run, so R0 comes first.
- R0. At the merge, before the next hourly run: sync the rules (`scripts/sync_prometheus_to_vps.sh`) and confirm
  `FabrikRegistryHealFailed` and `FabrikAuditStale` load (Prometheus rules page).
- R1. Read the next hourly cron run's lines in `/var/log/fabrik-audit-all.log` (or run it by hand from the main checkout:
  `PYTHONPATH=/opt/fabrik/src /opt/fabrik/.venv/bin/python /opt/fabrik/scripts/audit_all_registrars.py`). Read every
  `would-register` and `shared` line — expected: `zitadel` and `site_provisioner`; any of the 9 specs Phase A re-names may
  also appear (each is read and its spec checked before R2); `main`, if it appears at all (only when that database
  exists unregistered), reads `shared`, because four specs claim it (`spec § Validation` step 2).
- R2. Add `FABRIK_REGISTRY_RECONCILE=apply` to the audit line of the hub crontab; the next hourly run heals; read the log
  for the `registered` lines.
- R3. Confirm `fabrik_audit_drift_total{registrar="postgres"}` is 0 for `zitadel` and `site-provisioner` (Prometheus).
  The metric's `spec_id` label is the spec id (`site-provisioner`); R1's log lines name the database
  (`site_provisioner`) — the same service.
- R4. Confirm `FabrikAuditStale` is not firing (a clean run pushed the last-success timestamp).

### Behavior Contract — Phase C
- **Given** the rule file, **When** it is loaded, **Then** `FabrikRegistryHealFailed` (`max by (spec_id, db) (fabrik_registry_heal_failed) > 0`, `for: 2h`) and `FabrikAuditStale` (`(time() - fabrik_audit_last_success_timestamp_seconds > 10800) or absent(fabrik_audit_last_success_timestamp_seconds)`) exist in the `fabrik-registrar-drift` group, and `promtool check rules` passes (C1; `configs/prometheus/rules/fabrik-drift.yml:9`; `spec § The delta` D5)
- **Given** the promtool rule test, **When** it runs, **Then** `FabrikAuditStale` fires both when the timestamp is older than 3 h and when it is absent, and `FabrikRegistryHealFailed` fires after 2 h of failure even when the `reason` label changes mid-window (C2; `configs/prometheus/rules/fabrik-drift.yml:13`)

## File Scope (owned paths)

- src/fabrik/drivers/postgres.py
- src/fabrik/audit.py
- src/fabrik/registry_reconcile.py
- scripts/audit_all_registrars.py
- configs/prometheus/rules/fabrik-drift.yml
- tests/test_postgres_registry.py
- tests/test_registry_reconcile.py
- tests/fixtures/fabrik-drift-rules-test.yml
- docs/reference/health-monitoring.md
- docs/infrastructure/vps-complete-inventory.md
- docs/CONFIGURATION.md
- .env.example
- docs/superpowers/specs/2026-10-02-postgres-allocation-reconcile-design.md
- docs/development/reviews/2026-10-02-plan-2-postgres-allocation-reconcile-review.md

## Evidence

**Phase A.** `register_allocation` at `src/fabrik/drivers/postgres.py:1870-1923` takes no `if_absent` today; its three
callers are `:359`, `:453`, `:2139`. `audit_postgres` derives the name at `src/fabrik/audit.py:140`; the existing helper
is `src/fabrik/app_role_check.py:782-804`.

```text
$ grep -rn "register_allocation(" --include="*.py" src/
src/fabrik/drivers/postgres.py:359
src/fabrik/drivers/postgres.py:453
src/fabrik/drivers/postgres.py:1870   (def)
src/fabrik/drivers/postgres.py:2139
```

The audit names Phase A moves, executed by the orchestrator during round 1 of `/fabrik-plan-review`
(`<scratchpad>/pr/probe_names.py`: every spec loaded, `audit.py`'s old rule vs `_db_name_for_spec(spec.model_dump())`):

```text
$ FABRIK_SCAFFOLD_OFFLINE=1 .venv/bin/python probe_names.py
CHANGED ai-model-catalog.yaml: ai_model_catalog -> main
CHANGED calendar-orchestration-engine.yaml: calendar_orchestration_engine -> calendar_engine
CHANGED compliance-ops.yaml: compliance_ops -> main
CHANGED evolution-api.yaml: evolution_api -> evolution
CHANGED exam-coach.yaml: exam_coach -> main
CHANGED fabrik-citation-verifier.yaml: fabrik_citation_verifier -> citation_verifier
CHANGED gmail-account-creator.yaml: gmail_account_creator -> main
CHANGED tryton-crm.yaml: tryton_crm -> tryton
CHANGED youtube.yaml: youtube -> youtube_pipeline
specs=72 postgres-applicable=23 name-changes=9 errors=0
```

**Phase B.** The orphan quadrant and the `actual` keys the reconcile reads: `src/fabrik/audit.py:180-183`, `:197-203`.
The push is a `POST` today: `scripts/audit_all_registrars.py:119`. The owner lookup: `src/fabrik/drivers/postgres.py:572`
(`_db_owner(db_name, container)`), container constant `:62`. No test covers the script today.

```text
$ grep -rln "audit_all_registrars" tests/
tests/test_hub_write_root.py        (a path-convention table, not a behaviour test)
tests/test_kaizen_shrink_audit.py   (fixture string only)
$ grep -rn "fabrik-audit" --include=*.py --include=*.sh scripts src
scripts/audit_all_registrars.py:16    (docstring: /tmp/fabrik-audit-metrics.txt)
scripts/audit_all_registrars.py:19    (docstring: metrics/job/fabrik-audit)
scripts/audit_all_registrars.py:62    METRICS_OUT_FILE = Path("/tmp/fabrik-audit-metrics.txt")
scripts/audit_all_registrars.py:63    PUSHGATEWAY_JOB = "fabrik-audit"   (:119 builds the URL from it)
(no other definition in scripts/ or src/; a pusher outside this repo is beyond the grep)
```

Pushgateway semantics, raw README (ledger obs-8):

```text
README.md:368  `PUT` is used to push a group of metrics. All metrics with the
README.md:369  grouping key specified in the URL are replaced by the metrics pushed
README.md:411  `POST` works exactly like the `PUT` method but only metrics with the
README.md:412  same name as the newly pushed metrics are replaced
```

**Phase C.** The rule file is one alert today (`configs/prometheus/rules/fabrik-drift.yml:13-24`); the VPS image is
`prom/prometheus:v3.2.1` (`configs/monitoring-compose.yaml:47`); the sync script copies and reloads
(`scripts/sync_prometheus_to_vps.sh:130-137`, `:144-146`).

```text
$ which promtool
promtool: command not found
$ grep -r "fabrik-drift" tests/
(0 hits)
```

The sync-trigger check for the docs this plan could touch (I11):

```text
$ python3 - (governance-sync files filter from .pre-commit-config.yaml)
SYNC  agents-fabrik.md
local docs/reference/health-monitoring.md
local docs/infrastructure/vps-complete-inventory.md
local docs/CONFIGURATION.md
local .env.example
```

## Self-audit

- Grounding: three repo seats (postgres driver; audit and cron; alerts and toolchain) returned anchors; the orchestrator
  re-read every cited line it relies on. Two findings changed the spec: the existing name helper (D1 now reuses
  `_db_name_for_spec`) and the `POST` push (D5 now switches to `PUT`).
- (a) Coverage: I1-I6 map to Phases A-C and the rollout; I7-I11 have named destinations.
- (b) Signatures: `register_allocation_if_absent(db, *, spec_id, user, owner, notes) -> bool` (A) is what B calls;
  `HealResult`, `claims(specs) -> (map, unresolved)` and `reconcile_postgres(audits, claims, *, claims_complete, dry_run)` (B) are what the script calls; the series B renders are what
  C's rules read: `fabrik_registry_heal_failed`, `fabrik_audit_last_success_timestamp_seconds` (plus
  `fabrik_registry_heal_total` and `fabrik_audit_spec_errors`, read by people, not rules).
- Not yet at a fixed point: `/fabrik-plan-review` runs next.

## Residual unknowns

- **Resolved:** the name rule (existing helper); the push semantics (`PUT`); promtool (from the image via docker); the
  rule deploy path (`sync_prometheus_to_vps.sh`); the only definition of the pushed job inside this repo.
- **Open — the fire rate of the first `apply` run.** Resolution: rollout R1 lists every `would-register` before any write.
- **Open — the push path's own health** (pushgateway or Alertmanager down): out of scope (`spec § Open / blocking
  unknowns`); `FabrikAuditStale` covers a dead cron only.

## Pass Ledger

`/fabrik-plan-review`, 2026-10-02. Native seats only (D-181), partitioned by section (D-212, D-218): `rules` (Opus — Global
Constraints, Context Ledger, Constraints Digest, every Interfaces block, every Behavior Contract, Evidence, File Scope,
Coverage Checklist; spec The delta, Validation, Constraints digest, What exists today) and `prose` (Sonnet — the rest of
both). The spec is `Size: small`, so its sections are graded here with the plan (`/fabrik-spec` § Phase 5).
`dispatch_headroom.py --slices opus=1,sonnet=1` → `SEATS: 2`, stamped.

| Pass | seats · axes re-checked (claims · gates · interfaces · completeness) | counters | method | plan md5 (start → end) · spec md5 (start → end) |
|-----:|---|---|---|---|
| Pass 1 | opus×1 (`rules`, 58 claims) + sonnet×1 (`prose`, 23 claims) · all axes, plus two orchestrator probes | found: 24, new: 24, confirmed: 23, fixed: 23, unexecuted: 0, edits: 31 | method: citation — full partitioned pass; every candidate executed by the orchestrator or by its seat's probe. Orchestrator probes: the name-rule move hits 9 of 23 postgres-applicable specs, 4 onto one database `main` (→ outcome `shared`). Rules: the `apply` default would write before the report pass (→ default `report`); a `PUT` without the timestamp deletes it so `FabrikAuditStale` could never fire (→ `or absent(...)`, promtool-proven); `_db_owner` `None` fell back to `db` (→ `failed owner-unresolved`); `registered` vs `already-present` was unknowable (→ `register_allocation_if_absent -> bool`, B2 tested on the real lock path); a changing `reason` reset `for: 2h` (→ `max by (spec_id, db)`); `PUT` drops a skipped spec's drift series (→ `fabrik_audit_spec_errors`, no timestamp on a spec error); `depends.postgres` has no pattern before SQL (→ `_validate_identifier`); the pusher grep, the header-check path and coverage, the writer lines, signature/date/series wording, the import-cycle reasoning, the self-healing scope (MATCHED via `**/health*` → row proposed to infra). Prose: B6 script path, A5 watched the wrong row, B1 patched names on the wrong module, the shared-append recipe's section, the site-provisioner spellings. Refuted 1: listing `INDEX.md`/`CHANGELOG.md` in File Scope (governance files are excluded by the plan grammar). | df375e0a1b89c80e8b659e1df6a31e24 → 91abe075c42a0903005f2476af829d62 · 7d45177e4fe9cb2aac559fa124b5f5bb → fedc2db3e83527c8f7d6f84563f8fe2d |
| Pass 2 | opus×1 (round-1 owner of `rules`, 30 claims re-executed) + sonnet×1 (round-1 owner of `prose`, 9 claims) · the round-1 fix hunks + one hop | found: 4, new: 4, confirmed: 4, fixed: 4, unexecuted: 0, edits: 9 | method: re-derivation — all 21 round-1 candidates re-verified closed against the pin; promtool re-run on the corrected rules (6 cases, SUCCESS; orchestrator's own 3-case run SUCCESS, `check rules` → `SUCCESS: 3 rules found`); the 9/23 name-move probe re-run independently (identical). Confirmed, all inside round-1 fix text: N1 the `shared` claim map counted only audit outcomes, so an `unknown` or skipped sibling made a shared database look singly claimed (→ claims from every loaded database spec's name rule; any load/resolve failure → `failed claims-unresolved`); N2 spec D6 still said the first run registers (→ after the operator turns on `apply`); R1's unconditional "`main` must read `shared`" (→ conditional); the spec Personas' 0-step budget ignored the one-time opt-in. Recorded and folded: the name is resolved after the `n/a` return; the stale alert's `absent` arm also means a spec error (doc step); the promtool fixture sets `exp_annotations`. | 5287d516473890980855530c4d4fa7f4 → cfc00b95f94f51d75b77b2d56c12c11e · fedc2db3e83527c8f7d6f84563f8fe2d → a449286da9e9b5a144bc244234471287 |
| Pass 3 | opus×1 (owner of `rules`, 12 claims re-executed) + sonnet×1 (owner of `prose`, 6 claims) · the round-2 fix hunks + one hop | found: 3, new: 3, confirmed: 3, fixed: 3, unexecuted: 0, edits: 7 | method: re-derivation — the claim map executed over the live specs by both seats and the orchestrator (20 databases, `main` → 4 spec ids, 0 load and 0 resolve failures, so `claims_complete` is true today); all six round-2 closures re-verified. Confirmed, all inside round-2 fix text: C3-1 the old `reconcile_postgres` signature survived in spec D3 and the plan Self-audit; C3-2 `claims()` had no channel for an unresolved name (→ returns `(map, unresolved)`; `claims_complete = error_count == 0 and not unresolved`; B7 covers a non-string `depends.postgres`; spec: "any spec failed to load"); C3-3 the `infrastructure.py` anchor is `:506-508`. **Scope-growth stop:** Passes 2 and 3 were both all own-fix (4/4, 3/3), so the named set is fixed here and the next pass re-verifies only that set; a further own-fix defect is recorded, not re-armed. | 88257bf53723283202fabc87bee06a3d → 71fe2f5df1d6912e108d876bc88efcb0 · a449286da9e9b5a144bc244234471287 → b516d477ca963a2493568cd02d406956 |
| Pass 4 | opus×1 (owner of `rules`, 10 claims re-executed) + sonnet×1 (owner of `prose`, 4 claims) · ONLY the round-3 fixed set, under the scope-growth stop | found: 2, new: 2, confirmed: 0, fixed: 0, unexecuted: 0, edits: 0 | method: re-derivation — all three round-3 fixes re-verified closed: the signature agrees at all four sites, `claims()` returns `(map, unresolved)` with `claims_complete = error_count == 0 and not unresolved`, and the `infrastructure.py:506-508` anchor matches the live file; the pydantic probe shows a non-string `depends.postgres` fails at `load_spec`. Two further own-fix findings are RECORDED — measured, not counted and not re-arming the stop (`term-edit` § Scope-growth stop): B7's non-string case must be built with `Spec.model_construct` plus the load-error case that really happens, and the trigger wording should name "load or audit" — routed to W-2b456a18 for Phase B's executor. Standing-clean classes not re-read: citations, safety, push-lifecycle, name-rule, alert-rules, pillars. | 6db0ec4b8390c466c5ebc7aae18470c9 → 6db0ec4b8390c466c5ebc7aae18470c9 · b516d477ca963a2493568cd02d406956 → b516d477ca963a2493568cd02d406956 |
| Flip | orchestrator · the CONVERGED flip gates | found: 0, new: 0, confirmed: 0, fixed: 0, unexecuted: 0, edits: 3 | method: gate — Status flipped on plan and spec; the 17 Coverage Checklist rows adjudicated from Passes 1-4; the Constraints Digest columns reordered to `| Verbatim | file:line | Rule |` and six backslash escapes removed so `check_rule_grounding` can read it (content unchanged — the reorder script asserts the 10 (rule, quote, source) triples are identical before and after). `check_convergence` rc 0 with no finding for this plan; `check_plan_quality` rc 0; `check_rule_grounding` 0 findings for this plan (unbudgeted audit); `check_spec_convergence` rc 0 with no finding for the spec. | 6db0ec4b8390c466c5ebc7aae18470c9 → 8f22ca7f71b70d81f378892d60ef7b49 · b516d477ca963a2493568cd02d406956 → Status line only |

## Coverage Checklist

Derived from the rubric below (FLOOR + MATCHED) plus the four standing recurrence classes and two
surface-specific classes. Every row starts UNCHECKED and is adjudicated by `/fabrik-plan-review`.

| Class | Verdict |
|---|---|
| FLOOR core/35-security-auth — secrets, auth, config via env | FIXED r1 — one env var read with `os.getenv(..., "report")`, fail-safe default and unknown value (rules #1); no secret or credential added |
| FLOOR core/25-data-postgres — database, sessions, backing services | FIXED r1 — reads `postgres-main` through the existing driver; the database name is validated before SQL because `depends.postgres` has no pattern (rules #10) |
| FLOOR core/30-ops — compose invariants, immutable releases, admin processes | CLEAN — no compose or container change; the reconcile is an admin process run from the deployed hub release (`/opt/fabrik/src`) |
| FLOOR 12-Factor — all twelve axes against what the plan steps | CLEAN — III (one granular env var), IV (driver unchanged), XI (stdout logging as today), XII (hub admin process) stated in Global Constraints; the rest not engaged |
| MATCHED core/10-python — no deps-file edits, no file logging | FIXED r1 — no deps-file edit, no logfile; the date is `datetime.now(UTC)`, not naive (rules #14) |
| MATCHED core/40-documentation — heading levels, fenced code, the docs the change makes stale | FIXED r1 — doc landing sites aligned with the plan, `agents-fabrik.md` left out as a sync trigger whose sentence stays true (rules #15); headings step `##` to `###`, code fenced |
| MATCHED core/45-testing-strategy — one test per behaviour, watched-fail-first, class-proof guards | FIXED r1-r3 — rows numbered A1-A4, B1-B7, C1-C2; A5 watches the right row (prose #2); B2 runs the real lock path (rules #7); B7 refinements routed to W-2b456a18 (Pass 4, recorded) |
| MATCHED core/55-observability — metrics, alert thresholds, no logfiles | FIXED r1 — staleness via a last-success timestamp with `absent(...)`, failure series aggregated `max by (spec_id, db)`, promtool unit-tested (rules #2, #8) |
| MATCHED core/58-resilience — counted fail-open, no silent swallow | FIXED r1-r2 — an unresolved owner, a failed write and an unresolvable claim are each counted and surfaced, never swallowed (rules #4; round 2 N1) |
| MATCHED core/self-healing — no silent action; ladder scope (a service's runtime failure classes) | FIXED r1 — the pack MATCHES via `**/health*`; the new response's ladder row is proposed to infra (Phase C step 1); every heal logs and counts (rules #17) |
| Production-write safety: the reconcile's only write is additive, in-lock, never overwrite or delete | FIXED r1-r3 — default `report`; `register_allocation_if_absent` in-lock; owner from `pg_database` or no write; `shared` and `claims-unresolved` refuse (rules #1, #4, #7; N1; C3-2) |
| Metric lifecycle in the pushgateway (POST vs PUT, stale series, last-success staleness) | FIXED r1 — `PUT` replaces the group (obs-8); a skipped spec withholds the timestamp and pushes `fabrik_audit_spec_errors` (rules #9); `absent(...)` covers a deleted timestamp (rules #2) |
| fail-open vs fail-closed on every gate/guard (unknown mode value, unreadable registry, owner lookup failure) | FIXED r1-r2 — unknown mode becomes `report`; a failed registry read raises (ea99ee94f, f9475148a); owner lookup `None` writes nothing; unresolvable claims write nothing |
| cost/quota/limit accounting edges (seats sized and stamped; per-run SSH reads) | CLEAN — every round's seats sized by `dispatch_headroom.py` (2) and stamped; the reconcile adds one `_db_owner` query per orphan only |
| boundary/sentinel/prefix collisions (empty or non-string depends.postgres, missing found/in_registry keys, db names with hyphens) | FIXED r1 — identifier validated before SQL (rules #10); a non-string value fails at `load_spec` (Pass 4 probe); name resolved after the `n/a` return (round 2 R-b) |
| one database claimed by several specs (`main`) and the name-rule move of 9 specs | FIXED r1-r2 — `main` x4 becomes `shared` from a spec-derived claim map (orchestrator probe; N1); the 9 moves listed in Phase A's Mirror and Evidence, read in rollout R1 |
| behavior-without-a-test | FIXED r1-r2 — rows added for owner-unresolved (B4), shared and claims-unresolved (B7), spec errors (B5), the promtool cases (C2) |

The rubric this plan's reviews inject into every seat brief, run on the plan's own `## File Scope (owned paths)`:

```bash
python3 scripts/review_rubric.py --changed src/fabrik/drivers/postgres.py src/fabrik/audit.py src/fabrik/registry_reconcile.py scripts/audit_all_registrars.py configs/prometheus/rules/fabrik-drift.yml tests/test_postgres_registry.py tests/test_registry_reconcile.py docs/reference/health-monitoring.md docs/infrastructure/vps-complete-inventory.md docs/CONFIGURATION.md .env.example
```

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
- VOLUME gets a plan pointed at a directory that never exists — a paper backup that reads green and archives nothing.  If the data is a volume, say so in the spec comment and rely on the global `docker-volumes` plan; never let a service-named plan be mistaken for the protection.
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

### core/10-python.md  (hit: scripts/audit_all_registrars.py, src/fabrik/audit.py, src/fabrik/drivers/postgres.py)
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

### core/40-documentation.md  (hit: docs/CONFIGURATION.md, docs/infrastructure/vps-complete-inventory.md, docs/reference/health-monitoring.md)
- > **⚠️ `docs/OPERATIONS.md` + `docs/DEPLOYMENT.md` are FLEET-AI INTERFACES, not just docs (D-065).**
- **Tier-1 (author → verify → converge; the author leg is NATIVE while the pool is OFF, D-181 — `scripts/doc_reconcile.py`'s pool author cannot dispatch):** for each **mechanically-detectable** doc whose Doc-Sync trigger fired (`docs/QUICKSTART.md` · `docs/CONFIGURATION.md` · `docs/data-contract.md` · `docs/SERVICES.md` · `docs/OPERATIONS.md` — the reliable-signal subset), `scripts/doc_reconcile.py` dispatches a cheap OpenRouter-pool author (`libs.subagents`, `pick_models("docs")`) to emit a **minimal structured patch**, **verifies it before applying** (a symbol cross-check catches invented endpoints; the orchestrator injects a higher-assurance native-Claude verify), and loops to a zero-edit round. Runs per phase in `/fabrik-execute-plan`; never blocks (fail-safe). The other docs (CHANGELOG, INDEX, FEATURES, RESILIENCE, PORTS, the READMEs, `db/schema.sql`, …) have no reliable mechanical content-signal → they rely on the touch-on-change backstop below + your own edit (force-update, not force-correct).
- The SSOT is the type-aware registry (`scripts/enforcement/_doc_registry.py::PROJECT_DOCS`) — this table is its project-facing rendering, kept in step, never a second truth. `/fabrik-plan-after-chat` (the plan set's spine + tickets — the ticket-format authority) injects these rows per ticket as its `Docs:` line.
- Standalone work (not plan execution) → `Agent-Role: primary`. Trailers go below a blank line, above `Co-Authored-By`. ⚠️ The trailer block must be its OWN paragraph with NO blank line inside it: git parses only the LAST paragraph, and only if it is all-trailers. A blank line before `Co-Authored-By:` demotes everything above it to prose; so does a prose line glued to the top of the block. Measured 2026-08-15: 200 of the last 200 hub commits carried `Agent-Role:` and only 10 parsed, because the old example here shipped the blank line.
- **⚠️ Link it or it is decoration.** *Measured:* requests for files that do NOT exist came ~zero from AI bots — agents never go looking. It follows (inference, not measurement) that a file only gets read when something points at it: reference it from the docs index or README.
- ⚠️ **In THIS repo `llms.txt` is GENERATED** (`scripts/generate_capability_index.py`, refreshed daily) — never hand-edit it; change the generator. A project writing one by hand owns it.
- either way. Cheap and reversible — never at the expense of `OPERATIONS.md`/`DEPLOYMENT.md`, which are the load-bearing agent interfaces (D-065).
- **No skipped heading levels** — `##` to `###`, never `##` to `####`
- **Fenced code blocks only** — never indented code (AI treats it inconsistently)

### core/45-testing-strategy.md  (hit: tests/test_postgres_registry.py, tests/test_registry_reconcile.py)
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

### core/55-observability.md  (hit: docs/reference/health-monitoring.md)
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

### core/58-resilience.md  (hit: docs/reference/health-monitoring.md)
- indexed here, never restated; "can actually suffer" is decided by § Per-Scaffold Applicability above. An N/A with a reason is a complete answer, a silent gap is not.
- ⚠️ **Rows 9 and 22 make "autorecovery" honest.** Everything else recovers a *call*; row 9 recovers the
- **`httpx.AsyncClient`** is the only HTTP client for async FastAPI. Never use `requests` (sync, blocks the event loop).
**`wait_random_exponential` / `wait_exponential_jitter`, never bare `wait_exponential`**. Not a style preference: tenacity's own docstring says `wait_exponential`'s intervals "are fixed (i.e. there is no jitter) … *not* suitable for resolving contention between multiple processes for a shared resource". N workers that fail together retry in lockstep and re-hammer the dependency exactly as it recovers — the thundering herd. Every worker fleet here is that "multiple processes" case.
- 400/401/403/404/422 — a permanent client error retried is just load. ⚠️ **`429` and `408` are the exceptions and they matter most**: `429` is the commonest retryable response from a rate-limited vendor and `408` is transient by definition, so a flat "never retry 4xx" makes an agent give up on precisely the failure backoff exists for.
- curve does. ⚠️ **Two legal formats**: delay-seconds (`120`) *or* an HTTP-date (`Wed, 21 Oct 2026 07:28:00 GMT`). Parse both, **clamp both ends** (a hostile `86400` must not park a worker for a day; a hostile `-1` must not raise out of your retry machinery), and fall back to jittered backoff when absent or unparseable. `tenacity.wait_exception` exposes the response for this.
- **⚠️ Inline retry vs PAUSE — and `429` is where they meet.** An inline retry handles a **blip**; a pause handles a **condition**, where every job will hit the same wall and retrying inline just multiplies load across the queue. The test is not the status code but **whether the next job would fail for the same reason**: a single `429` with a short `Retry-After` → honour it inline; repeated `429`s, or a `Retry-After` beyond your inline budget → `set_pause(key, ttl)` so one worker's discovery spares the whole queue. ⚠️ **Clamp that TTL too** (§7a): the inline cap stops a hostile `86400` parking ONE worker for a day; the same unvalidated value in a pause key parks the ENTIRE … (wrapped further — read the pack)
- **⚠️ Retry at ONE layer.** Retries compose multiplicatively: tenacity ×3 in a job, a queue retry ×3 around it, your caller ×3 = up to **27** upstream calls per logical operation, long before a breaker sees a pattern. Pick the owning layer; make the inner ones fail fast. For worker jobs the queue retry IS the retry — do not also wrap the call in `@retry`.
- **⚠️ Retrying a non-idempotent write can double-charge, double-send or double-create.** A `POST` (or non-idempotent `PATCH`) needs an `Idempotency-Key` before it gets a retry — otherwise retrying after a timeout you never saw the response to is a second real mutation. `PUT`/`DELETE` are idempotent by HTTP semantics. `15-api-contracts` owns the SERVING side; this pack owns the caller's question —
- **Graceful fallback** — cached data, a default, or a clear error. Never let an external failure crash your endpoint. ⚠️ That includes the *parse*: a `200` with malformed JSON raises `JSONDecodeError`, which is not an `httpx.HTTPError` and will sail straight past the `except` above.
- Clients call a **self-hosted FastAPI backend** (Pattern A — `fabrik-lib/fastapi-user-auth`), never a database-as-a-service SDK directly. Browser `fetch` / mobile HTTP clients have no built-in timeout or retry — wire them explicitly:
- **Backend outage fallback:** cached data (MMKV on mobile, localStorage on web) or a clear error state — never a blank screen or crash.
- **Auth token refresh:** the app's auth client owns the refresh flow (`35-security-auth.md` Pattern A). Never scatter ad-hoc refresh logic across service calls.
| **`open` returns the fallback IMMEDIATELY**, never a queued timeout wait | you re-pay the read timeout on every call to a dead dependency |
- distributed breaker: never back it with Redis to "share" state. ⚠️ Corollary: with N workers, up to `N × failure_threshold` calls hit a dead dependency first. When that matters the fleet-wide stop is a
- **Never auto-run migrations at startup** — a one-shot deploy step (`30-ops` § Release & Admin).
- ⚠️ **The "fail readiness first, then drain" step in every Kubernetes guide does NOT apply here by default** — it lets a load balancer deregister one replica while its siblings serve, and this stack does not set `deploy.replicas` on app services (`30-ops`). Add it only with real multi-replica Traefik routing; unconditionally it buys a longer outage per deploy, not a shorter one.
- **The signal must arrive.** Shell-form `CMD` makes `/bin/sh` PID 1, which never forwards SIGTERM — exec-form, or `sh -c "exec ..."` (`30-ops`).
- stampedes the origin — a herd from your own cache, not a retry loop, so jitter and backoff never touch it. Coalesce behind a single-flight lock, or refresh before expiry.
| **Backblaze B2** (S3 API, `boto3`) | 30s connect / 120s read | return an error; never block a request on an upload |
- B2 uploads go async via the job queue, never inline in a handler. **boto3 is sync** — keep it in the worker or a thread executor, never inside an `async def` route.
- B2 downloads use server-side presigned URLs (generation is local, no I/O — safe in async). Never proxy file bytes through FastAPI.
- ⚠️ **Never point `HEALTHCHECK` at the dependency-checking endpoint** — one `postgres-main` blip would flip every container on the fleet to `unhealthy` at once. A DB blip degrades readiness; it must never mark the container unhealthy.
- Both endpoints are Authelia-bypassed on all services. Never protect them.
- ⚠️ **Docker does NOT restart an unhealthy container.** `restart: unless-stopped` acts on process EXIT only; health status feeds `up --wait`, `depends_on: service_healthy` and Traefik routing — never a restart. A process that is **wedged but alive** is recovered by nothing in compose: that is the watchdog's Tier A `restart_container` (`60-watchdog`), and it is why the watchdog exists. Never design as if the daemon will do it.
- see pause state without it firing Gatus alerts. ⚠️ That deliberate green is exactly why a long pause must escalate on its own (§ The Four Properties, property 2).
- 1. **Detection is proactive AND reactive.** Beat tasks poll vendor balance APIs *before* workers fail; error classifiers map exceptions to pause keys on the way through. Never one without the other for a critical dependency.
- ⚠️ **So a pause carries its FIRST-set time and escalates exactly once past N× its TTL** (`self-healing` row 4). ⚠️ **`fabrik-lib/alerting/` does NOT give you that property, and the provider-death row 3 of § Provider-death resilience points here rather than repeating it** — NOT the coverage map's row 3, which is the circuit-breaker row. Read at `/opt/fabrik-lib/alerting/__init__.py`, its dedup is a module-level `_last_sent` dict, so it is per-process — and a forked child INHERITS the parent's, rather than starting clean. Four things it is not. (1) Not a latch: the window is `ALERT_MIN_INTERVAL` … (wrapped further — read the pack)
- boot). Sliding TTL: every detection event calls `set_pause(...)` with a fresh TTL — never `setnx`, never permanent. Scope (§2c of the project's RESILIENCE.md):
- your dependencies, never inline at a call site.
- The classifier maps transient signals → pause. Its mirror-image rule is just as load-bearing: **an operational failure must never be written as a terminal *content* verdict.** Model the outcome on two axes — **(transport outcome) × (content evidence)** — and record a content terminal (`deleted`, `private`, `unavailable`…) only on **positive content evidence**. Everything else is transient.
| 1 | **No single point of death** — one model or endpoint dying must not stop the loop | **Declare** the mechanism in §2b. Outage-aware routing is step 1 of OpenRouter's default strategy and a `models` array falls back on **any** error. ⚠️ **The trap: setting `sort` or `order` DISABLES load balancing, and the outage step is *part of* it** — pinning silently opts you out of the protection you think you have (claims row `openrouter-pin-disables-failover`); if you pin, you owe the `models` array explicitly | **Build it**: probe the quality-ordered candidates **once at run start** (never per item) and rebuild the chain from live survivors, best first, so it self-restores on recovery. Base it on `fabrik-lib/health-probe/`; the chain-rebuild helper is `health_probe.live_chain()` (fabrik-lib `health-probe/`, vendored to projects as `libs/health_probe/` by the governance sync). Needs **intra-provider** (2+ models of one provider) AND **cross-provider** diversity |
| 3 | **Absence of progress is alarmed** — N minutes of zero progress fires ONE alert, cleared on recovery | No gateway provides this. Export a monotonically-increasing **progress** counter (rows done, items classified) and alert on *it*, not on error codes. Threshold ≥ 2 full loop runs, a §7a knob. ⚠️ The exactly-one half is YOURS to build — `fabrik-lib/alerting/` does not provide it; see the pause-escalation bullet under § Advanced: Autonomous Pause-State Pipeline → The Four Properties for what it actually does and why — this file's own section, not `RESILIENCE.md` §7 | Same |
| Worker clears `dispatched:<id>` flag when paused | Worker MUST keep the flag on pause-skip (queue bloat) |
| Backup that has never been restored to staging | Run §10 drill within 30 days or it doesn't exist |
| A fallback chain whose **bottom rung has never been executed** | Exercise the last resort on a schedule — an untested fallback is a silently-dead one, and the chain is a rung shorter than its author believes |
- one-shot migration step boot must never do
- [ ] Retries use **jittered** backoff (`wait_random_exponential`/`wait_exponential_jitter`, never bare `wait_exponential`) on transient errors only.
- naming only `TimeoutException`/`ConnectError` never retries a 429.
- state — never a blank screen.

### core/self-healing.md  (hit: docs/reference/health-monitoring.md)
- AGENT USAGE: Pick the failure class, walk the ladder top-to-bottom, stop at the first step that resolves. Never invent a step. Never skip a step. -->
- [`60-watchdog`](60-watchdog.md) — the escalation engine and the owner of its tiers. Tier A acts automatically (it registers `restart_container`, `clear_file_cache`, `scale_concurrency`, `pause_worker`); Tier B is opt-in; Tier C escalates — and carries the **approved-write lane** (`drop_queue_items`, `rotate_locks`), off by default; **Tier D** (opt-in, Telegram-gated) applies a tested code fix with auto-rollback. ⚠️ Registered is not runnable — see **What the sidecar can execute today** below.
- Each row reads left-to-right: **Symptom** (an observable signal) → **First response** (a `58-resilience` primitive or the module that implements it) → **Fallback** (another primitive or a `60-watchdog` action) → **Escalate** (operator-bound). The agent picks the row matching the active failure, walks left-to-right, and **stops at the first step that resolves**. Never skip rightward.
**⚠️ Row 10 is NOT the deadman timer, and the difference is the whole point.** The Tier-C deadman below (`spec.watchdog.deadman_timeout_seconds`, 60–3600, default 300 s, rendered as `WATCHDOG_DEADMAN_TIMEOUT`) measures **operator silence** — it arms only
- If a failure class doesn't appear in the table above, the rule is: **add the row to this pack first, then the response logic to the code.** Never silently invent a self-healing response — it'll diverge from the operator's mental model and break the ladder's discipline.
- 4. **Self-healing without a visible signal.** A pause flag, breaker, or rate-limit reject that doesn't increment a counter and emit a structured log line is invisible — when it misfires, you can't tell. Every ladder step MUST emit a counter AND a `structlog.info()` (or `pino.info()`) row carrying the resource name + reason; without that, the next operator audit has no way to tell the difference between "step fired and recovered" and "step never ran". **Tier-D steps (stabilize / remediate / apply / rollback) are held to the same bar:** each MUST emit a counter + structured log AND write the `incidents` / `approvals` / `deploys` tables — an unaudited or irreversible code-remediation is not self-healing, it's an unreviewed deploy.
- 2. **Fallback — `pause-state` (Redis-backed).** When `signups_per_ip_per_minute` for a specific IP stays high after the first defense's per-IP cap fires, the worker emits an incident; the watchdog sidecar reads the inbox and proposes Tier A `pause_worker` with `resource=signup_<ip_hash>` (the action accepts `^[a-z][a-z0-9_]{0,31}$` and a TTL of 5–3600 s, so truncate the hash to fit — and it is unreachable today, above, so until upstream carries parameters the app sets this pause itself with `pause_state.set_global_pause(...)`). Every signup-handling worker checks `pause_state.is_paused("signup_<ip_hash>")` from the vendored fabrik-lib `pause-state` (the scaffold's own `pause_state.py` has no `is_paused`), with `PAUSE_KEY_PREFIX` equal to `<project_id>:pause:`, and bails without touching the DB. Never gate other workers on `is_globally_paused()` while per-IP keys share the prefix — it reports ANY key under it, so one IP would stop them all.

# promote-to-check_*: 139 injected mandate(s) look deterministically greppable — their backtick literals, one line each (the full mandates are ABOVE, not repeated: re-emitting ~20 FLOOR lines verbatim doubled the rubric and got it skimmed — web-ecommerce-factory 01M1QEY5, 2026-09-05)
- `fabrik-lib/fastapi-user-auth` `DELETE … RETURNING` `jti` `agents-fabrik.md § Supabase`
- `chrome-extension` `chrome.identity.launchWebAuthFlow` `https://<ext-id>.chromiumapp.org/` `chrome.storage.session`
- `desktop-app` `safeStorage` `desktop-app/72-desktop.md`
- `fabrik` `X-Internal-Token` `internal_auth.py` `hmac.compare_digest` `APIKeyHeader`
- `auth.uid()` `current_tenant_id()` `NULL` `EXCEPTION WHEN OTHERS THEN RETURN NULL` `SELECT auth.uid()` `NULL`
- `openssl rand -hex 32`
- `algorithms=["HS256"]` `alg` `alg: none`
- `redis-main`
- `expo-secure-store` `80-mobile.md`
- `localStorage` `sessionStorage`
- `chrome.storage.session` `TRUSTED_CONTEXTS` `chrome.runtime.sendMessage` `chrome.identity.launchWebAuthFlow` `code_verifier` `crypto.subtle` `storage.session`
- `x-middleware-subrequest` `middleware.ts` `proxy.ts` `middleware.ts`
- `CORSMiddleware` `allow_origins`
- `X-Frame-Options: DENY` `frame-ancestors`
- `APIKeyHeader` `require_api_key` `SERVICE_API_KEY` `PROXY_API_KEY` `python-api` `internal_auth.py` `metrics.py` `/metrics` `SERVICE_INTERNAL_SECRET_KEY`
- `os.getenv("KEY", "default")` `config/production.yml` `settings.production`
- `expo-secure-store`
- `^/api/` `/api/*` `/api/v1` `/api/*` `shape.bearer_bypass_prefix: "^/api/v1"` `fabrik apply` `^/` `orchestrator/verifier.check_api_bypass` `/api/*` `^/api/`
- `postgres-main` `fabrik-lib/rag` `postgres:16-alpine` `plpgsql` `postgres-main`
- `postgres-main` `docs/DECISIONS.md`
```
