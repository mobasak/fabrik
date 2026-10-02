# Plan — backrest coverage: protect what a service persists, never a path that does not exist (W-5c4ad6a6)

Status: DRAFT
Profile: small
**Owner:** fleet

Spec: `docs/superpowers/specs/2026-10-02-backrest-paper-backups-design.md` (DRAFT, `Size: small`, `Profile: delta` —
`/fabrik-plan-review` grades its sections together with this plan and flips both). Research ledger:
`docs/reference/research/2026-10-02-backrest-paper-backups-ledger.md` (37 rows). Work item: W-5c4ad6a6. Estimated diff:
≈180 code lines in 3 code files, tests excluded (`spec § Size`).

## What this plan is

Three inline phases (the orchestrator codes each itself in the worktree; no coder is dispatched):

- **A — discovery and coverage in the driver:** `discover_persistence`, `read_plans`, `coverage`, `visible` in
  `src/fabrik/drivers/backrest.py`, with their tests.
- **B — the registrar, the audit and the rollback guard:** `_provision_backrest` and `audit_backrest` both run the spec's
  table through Phase A's functions; the registrar records a resource only for a plan it created.
- **C — docs, the infra proposal and Finish:** the doc landing sites, the mail to infra about the `30-ops` checklist line,
  the heavy `/fabrik-review` over the whole-plan diff, and the rollout steps the operator runs.

Per phase: `/fabrik-review-scoped` on that phase's surface. At Finish: one heavy `/fabrik-review` (the
`/fabrik-execute-plan` D7 floor) and one receipt.

## Intake Inventory

| I# | Item (anchored) | Disposition | Where |
|---|---|---|---|
| I1 | "_provision_backrest hardcodes /opt/<name>/data" (W-5c4ad6a6) | IN | Phases A-B |
| I2 | named-volume services (tryton-crm) | IN | Phase A discovery (volume mounts) |
| I3 | DB-only services (zitadel) | IN | Phase A discovery (database path) + Phase B |
| I4 | `FabrikRegistrarDrift` fires for tryton-crm and zitadel | IN | Phase B audit + rollout V3-V4 |
| I5 | heal the live paper plans | IN | Rollout V4 — OPERATOR-GATED |
| I6 | every scaffold type and spokes | IN | Phase B (the `not visible to Backrest` branch) |
| I7 | never delete a live plan without the operator's go | IN | Global Constraints; no code path deletes |
| I8 | rollback removes a plan it did not create | IN | Phase B (B5) |
| I9 | an empty or stale snapshot alert | OUT-OF-SCOPE | W-43904006 |
| I10 | the four test specs with nothing to persist | OUT-OF-SCOPE | the audit names them (B4's shape-mismatch row); their owners fix the flag |
| I11 | the `30-ops` checklist line (fleet-synced, infra's beat) | IN | Phase C step 1 — a proposal to infra, never an edit here |

## What we already agreed (citations, not restatement)

- Goal, the pain, the personas and the step budget: `spec § Goal`, `spec § Why this exists`, `spec § Personas`.
- Chosen approach A and its decision table; the unanimous panel: `spec § Chosen approach`.
- Rejected C, B, a second backup system, a computed path: `spec § Rejected alternatives`.
- The five deltas D1-D5: `spec § The delta`.
- What exists today: `spec § What exists today (grounded)`.
- Validation and the operator-gated rollout: `spec § Validation`.
- Decisions taken: `spec § Decisions taken`. The approval row is minted by `/fabrik-plan-review` at its gate (a
  `Size: small` spec is approved there, not here).

## Global Constraints (every phase inherits these)

- **No code path deletes a backup plan.** The registrar only adds `<name>-data` for uncovered, visible paths; the audit is
  read-only; removing a paper plan is rollout V4, run on the operator's go (`spec § The delta` D5).
- **A plan is never written with zero paths, and never for a path Backrest cannot stat** (ledger brk-4, brk-5).
- **Secrets stay on the VPS:** `read_plans` extracts `id`, `paths` and `excludes` with `jq` on the VPS; the repo
  section of `config.json` (B2 credentials, `drivers/backrest.py:22-25`) never crosses SSH or reaches a log.
- **Discovery is read-only and its exit status is honest:** every SSH probe runs the docker command alone and parses the
  output in Python (the class closed in W-c6d27660, 9b6137382); a failed probe returns `None` and is `unknown`, never a
  confident `present` or `drift`.
- **Dry run makes no SSH call:** `_provision_backrest` under `dry_run` logs what it would check and returns.
- No new dependency (`fnmatch`, `json` and `shlex` are stdlib); `pyproject.toml` and `uv.lock` are not touched
  (`core/10-python.md`). No env var is added (`spec § Constraints digest`, the config row).
- 12-Factor on this surface: **IV** the backing services (Docker, Backrest) are reached over the existing SSH driver;
  **XI** logging through `logging` as today; **XII** the audit runs from the deployed hub release (`/opt/fabrik/src`); the
  rest not engaged.
- Tests: watched-fail-first for every behaviour this plan adds (`core/45-testing-strategy.md:22`); no test reaches a VPS —
  `ssh`/`_ssh_check` are patched, and the conftest guard refuses real SSH. The shared `.venv` imports `fabrik` from
  `/opt/fabrik/src` — every test run exports `PYTHONPATH=/opt/fabrik/.claude/worktrees/fleet/src`.
- Seats never mutate git state (read-only git only); never read `~/.claude*`; never SSH, never run `fabrik apply`.
- **Execution discipline (native seats only, D-181):** every phase ends with `/fabrik-review-scoped` (its floor of
  three native seats on different angles, stamped with `command_run.py dispatch`) and does not hand on until a closing
  pass confirms zero defects; the Finish `/fabrik-review` partitions the whole-plan diff by file into Sonnet + Haiku
  finder seats per slice (D-344), the orchestrator executing every refutation; within a phase the steps are sequential
  (each depends on the previous), and the review seats are the parallel fan-out, merged and refuted by the orchestrator.
- **Operator-gated steps are never executed by an agent:** rollout V3 is a read-only report on vps1 after infra merges;
  V4 removes production backup config.

## Context Ledger

| Source | What binds | Grounded ref |
|---|---|---|
| `.windsurf/rules/core/30-ops.md` (FLOOR) | a volume relies on the global `docker-volumes` plan; a service-named plan is not the protection | `core/30-ops.md:219-223` |
| `.windsurf/rules/core/25-data-postgres.md` (FLOOR) | DB backups go through Backrest, registered when `needs_database` | `core/25-data-postgres.md:332` |
| `.windsurf/rules/core/35-security-auth.md` (FLOOR) | config via env vars only; zero secrets in code | `core/35-security-auth.md:267` |
| `.windsurf/rules/core/10-python.md` (MATCHED) | no deps-file edit | `core/10-python.md` |
| `.windsurf/rules/core/45-testing-strategy.md` | watched-fail-first | `45-testing-strategy.md:22` |
| `.windsurf/rules/ai/50-agentic.md` (MATCHED by glob on `orchestrator/`) | not engaged — no LLM or agent loop in this change | `spec § Constraints digest` |
| `fabrik-lib` | none — no module covers the hub registrar layer | `spec § fabrik-lib verdict` |
| `specs/services/*.yaml` `shape:` | no flag changes; `has_persistent_data` and `needs_database` are read | `spec § Shape / infra implications` |

## Constraints Digest (verbatim rows from the MUST-READ packs)

| Verbatim | file:line | Rule |
|---|---|---|
| "If the data is a volume, say so in the spec comment and rely on the global `docker-volumes`" | `.windsurf/rules/core/30-ops.md:222` | Volume data |
| "plan; never let a service-named plan be mistaken for the protection." | `.windsurf/rules/core/30-ops.md:223` | Volume data |
| "Backups managed via Backrest → Backblaze B2 (registered by `fabrik apply` when `shape.needs_database: true`)." | `.windsurf/rules/core/25-data-postgres.md:332` | DB backups |
| "Mandate: config via env vars only (`os.getenv("KEY", "default")`)" | `.windsurf/rules/core/35-security-auth.md:267` | Config |
| "**Watched-fail-first** (for tests this change adds or modifies" | `.windsurf/rules/core/45-testing-strategy.md:22` | Red first |

## Phase A — Discovery and coverage in the driver

Appetite: 45

**Interfaces — Produces** (all in `src/fabrik/drivers/backrest.py`, after the per-database section that ends at `:370`):
- `discover_persistence(name: str, db_name: str | None) -> list[str] | None` — one `ssh` call (the module's existing
  `ssh`, `drivers/backrest.py:49`) that prints, per container of compose project `<name>`
  (`docker ps -aq --filter label=com.docker.compose.project=<name>`; when that is empty, containers whose name matches
  `^<name>(-|$)`), one line per mount `"<Type>\t<Source>"` from `docker inspect --format`. Parsed in Python: every
  `volume` Source, every `bind` Source that is a directory under `/opt/<name>/` (a trailing-slash-safe prefix test, so
  `/opt/<name>x/` never matches); plus `/opt/backups/postgres/<db_name>/` when `db_name` is given. Returns sorted unique
  paths; `None` when the SSH call raises. `name` and `db_name` are validated (the `_NAME_RE`-style pattern already in
  `drivers/backrest.py:285`) before they reach a shell.
- `read_plans() -> list[dict] | None` — `sudo jq -c '[.plans[]? | {id, paths: (.paths // []), excludes: (.excludes // [])}]'
  /opt/backrest/config/config.json` over `ssh`; parsed with `json.loads`; `None` on any failure.
- `coverage(paths: list[str], plans: list[dict]) -> dict[str, str | None]` — pure: for each path, the id of the first
  plan (by id order) that lists the path or a parent of it (`p == q` or `p.startswith(q.rstrip("/") + "/")`) and whose
  excludes do not match it (`fnmatch.fnmatch` against the path and against the path with a trailing `/`); `None` when no
  plan covers it.
- `visible(paths: list[str]) -> set[str] | None` — `test -e` for each path run INSIDE the Backrest container, one `ssh`
  call; the container is resolved with the module's pattern `^backrest(-|$)` (`drivers/backrest.py:152`) behind an
  explicit empty-name guard that fails the call (the guard of the W-a1a359c8 fix, so a failed `docker ps` can never
  read as "nothing visible"); returns the visible subset; `None` on failure.

**Consumes:** nothing.

1. **Write the failing tests first** in `tests/test_backrest_coverage.py` (new; rows A1-A5), patching
   `fabrik.drivers.backrest.ssh` with a fake that returns recorded `docker inspect`/`jq`/`test -e` outputs (the
   `patch.object(backrest, ...)` pattern of `tests/drivers/test_backrest.py:127-140`). Confirm each fails with `AttributeError` for the right name.
2. Add the four functions per the Interfaces; export them in `__all__` (`drivers/backrest.py:396-408`).
3. Run green: `cd /opt/fabrik/.claude/worktrees/fleet && PYTHONPATH=$PWD/src .venv/bin/python -m pytest
   tests/test_backrest_coverage.py tests/drivers/test_backrest.py tests/test_backrest_postgres_plan.py -q -p no:cacheprovider`.
4. Prove red on revert in a throwaway worktree (`git worktree add --detach <scratch>/pa HEAD`, copy the edited files):
   neuter the trailing-slash in `coverage`'s prefix test → A1's sibling-prefix row fails; drop the exclude check → A1's
   exclude row fails; remove the worktree.
5. **`/fabrik-review-scoped`** on Phase A's surface (`src/fabrik/drivers/backrest.py`, `tests/test_backrest_coverage.py`),
   run to its closing pass confirming 0 — BLOCKING before Phase B.
6. Commit Phase A (explicit paths + provenance trailers, `Agent-Phase: A`), push.

### Behavior Contract — Phase A
- **Given** plans `docker-volumes` (`/var/lib/docker/volumes`) and `opt-configs` (`/opt`, excluding `**/cache`), **When** `coverage` runs over `/var/lib/docker/volumes/x_y/_data`, `/opt/a/data`, `/opt/a/cache` and `/srv/z`, **Then** it maps them to `docker-volumes`, `opt-configs`, `None` and `None`, and `/opt/ab` is never covered by a plan listing `/opt/a` (A1; `spec § Chosen approach`)
- **Given** `docker inspect` output with a volume mount, a bind of `/opt/<name>/data`, a bind of `/var/run/docker.sock` and a bind of a config file under another directory, **When** `discover_persistence(name, "db")` runs, **Then** it returns the volume Mountpoint, `/opt/<name>/data` and `/opt/backups/postgres/db/`, sorted, and nothing else (A2; `spec § The delta` D1)
- **Given** no container labelled with the compose project but one named `<name>`, **When** `discover_persistence` runs, **Then** the name fallback finds its mounts (A3; `spec § Chosen approach`)
- **Given** the SSH call raises, **When** `discover_persistence`, `read_plans` or `visible` runs, **Then** each returns `None` (A4; `spec § The delta` D1-D2)
- **Given** a `config.json` with a repo section carrying credentials, **When** `read_plans` runs, **Then** the command sent over SSH selects only `id`, `paths` and `excludes`, and the parsed result holds nothing else (A5; `drivers/backrest.py:22-25`)

## Phase B — The registrar, the audit and the rollback guard

Appetite: 50

**Interfaces — Produces:**
- `src/fabrik/orchestrator/infrastructure.py::_provision_backrest(name, spec, ctx, dry_run, *, with_database: bool)` —
  today `(name, ctx, dry_run)` at `:1137-1147`; the call at `:634-635` passes `spec` and
  `with_database=should_run["postgres"]` (so an `infra.postgres: false` override drops the database path). Body: under
  `dry_run`, log and return (no SSH). Otherwise `db = app_role_check._db_name_for_spec(spec) if with_database else None`
  (a `ValueError` from it → warn, discover without the database path); `paths = discover_persistence(name, db)`;
  `None` → `_nonfatal` warning, return. Empty → warn `has_persistent_data set but no persistence found`, return.
  `plans = read_plans()`; `None` → warn, return. `cov = coverage(paths, plans)`; `uncovered = [p for p, q in cov.items()
  if q is None]`; none → log `covered by <ids>`, return. `vis = visible(uncovered)`; for paths not visible → warn naming
  each path and that Backrest needs a bind for it; for visible ones → `add_backup_plan(f"{name}-data", visible_paths)`.
  `ctx.add_resource("backrest", plan_id, ...)` **only when the result's status is `created`**.
- `src/fabrik/audit.py::audit_backrest(spec)` (`:331-390`) — the spec's right column, through the same Phase A functions
  (patched in tests through `fabrik.drivers.backrest`). The order of checks: discovery `None` → `unknown`; empty and no
  database → `drift` (shape mismatch); `read_plans` `None` → `unknown`; a `<sid>-data` plan whose paths are not all
  visible → `drift` (`paper plan <id>: remove it`, the missing paths in `actual`); any uncovered path → `drift`
  (`unprotected`, naming each path and whether Backrest can stat it); any covered path not visible → `drift`
  (`<path> missing`); else `present` with `actual={"covered_by": {path: plan_id}}`. `_missing_host_paths`
  (`audit.py:314-328`) is replaced by `visible` (Backrest's own view, ledger brk-5) and removed; the `missing` status is
  no longer produced.
- **Mirror (named):** `tests/orchestrator/test_infrastructure.py::test_dry_run_passes_through_to_every_driver`
  (`:380-420`) asserts `add_backup_plan` received `dry_run=True`; under this plan a dry run calls no backrest driver, so
  that test's `backrest` entry becomes an assertion that `add_backup_plan` was NOT called. `TestAuditBackrest`
  (`tests/test_audit.py:215-305`) is rewritten to the new rows (its `missing` case becomes the covered-without-plan
  `present` case). `scripts/audit_all_registrars.py` maps any status to its gauges generically (`:85-107`) and
  `fabrik audit-registrars` renders any status (`src/fabrik/cli.py:1435-1446`), so dropping `missing` for backrest
  breaks no consumer (Evidence § Phase B).

**Consumes:** Phase A's four functions.

1. **Write the failing tests first:** rows B1-B4 in `tests/test_audit.py` (`TestAuditBackrest` rewritten) and B5 in
   `tests/orchestrator/test_infrastructure.py` (a new test beside `TestProvisionDispatch`, `:344`), patching the Phase A
   functions. Confirm red against today's code.
2. Edit `_provision_backrest` and its call per the Interfaces.
3. Edit `audit_backrest` per the Interfaces; remove `_missing_host_paths`.
4. Update the named mirror test in `tests/orchestrator/test_infrastructure.py`.
5. Run green: `PYTHONPATH=$PWD/src .venv/bin/python -m pytest tests/test_audit.py tests/orchestrator/
   tests/test_backrest_coverage.py tests/drivers/test_backrest.py -q -p no:cacheprovider`.
6. Prove red on revert in a throwaway worktree: restore `add_resource` on `exists` → B5 fails; make the registrar skip the
   `visible` check → B2's invisible row fails; remove the worktree.
7. **`/fabrik-review-scoped`** on Phase B's surface (`src/fabrik/orchestrator/infrastructure.py`, `src/fabrik/audit.py`,
   the two test files), run to its closing pass confirming 0.
8. Commit Phase B (`Agent-Phase: B`), push.

### Behavior Contract — Phase B
- **Given** a service whose every discovered path is covered by a host plan and visible, **When** the registrar runs, **Then** it calls no `add_backup_plan` and records no resource, and **When** the audit runs, **Then** it returns `present` with each path's covering plan (B1; `spec § Chosen approach`)
- **Given** an uncovered path that Backrest can stat and one it cannot, **When** the registrar runs, **Then** it calls `add_backup_plan("<name>-data", [the visible path])` once and warns naming the invisible path, and the audit returns `drift` naming the invisible path (B2; `spec § The delta` D3)
- **Given** a `<sid>-data` plan whose path is not visible and the service's real paths covered elsewhere, **When** the audit runs, **Then** it returns `drift` with `paper plan <sid>-data: remove it` and calls no driver that writes (B3; `spec § The delta` D5)
- **Given** `has_persistent_data` with no persistence found and no database, or a discovery that fails, **When** the audit runs, **Then** it returns `drift` naming the shape mismatch, or `unknown` (B4; `spec § Chosen approach`)
- **Given** `add_backup_plan` returns `exists`, **When** the registrar runs, **Then** no `backrest` resource is recorded, so a later rollback cannot remove a plan this run did not create (B5; `src/fabrik/orchestrator/rollback.py:153-154`)

## Phase C — Docs, the infra proposal and Finish

Appetite: 40

**Interfaces — Produces:**
- Docs (`spec § Documentation landing sites`): `docs/reference/modules/drivers.md` § Backrest (`:158-170`, and the module
  table row `:33`) gains the four functions and the rule "a per-service plan only for an uncovered, visible path";
  `docs/infrastructure/vps-complete-inventory.md` § Backups (`:550-566`) gains one paragraph: per-service plans are
  created only for paths no host plan covers, and the audit names paper plans; `INDEX.md` row for
  `tests/test_backrest_coverage.py`; `CHANGELOG.md` (both governance files: orchestrator-applied, outside File Scope by
  the plan grammar).

**Consumes:** Phases A-B.

1. Propose the `30-ops` checklist update to its owner: `python scripts/mail.py send --to fabrik --to-agent infra --kind
   request` with the D-035 contract, proposing that `.windsurf/rules/core/30-ops.md:219-223` say the registrar now checks
   coverage (a fleet-synced surface this plan does not edit).
2. The doc edits per the Interfaces; `INDEX.md` and `CHANGELOG.md` through the shared-append private-index recipe of
   `CLAUDE.md` § Behavior (the shared-repo bullet). Then `python scripts/enforcement/check_doc_sync.py` and
   `python scripts/render_doc_script_links.py --check`.
3. **`/fabrik-review-scoped`** on Phase C's surface (the two docs), run to its closing pass confirming 0.
4. **Finish — the heavy `/fabrik-review`** over the whole-plan diff (`git diff <phase-A base>..HEAD`): the D7 floor — at
   least one Opus authoritative seat plus one Sonnet and one Haiku seat per independent failure-class group, sized by
   `python3 /opt/fabrik/scripts/sysadmin/dispatch_headroom.py --units <groups>` and stamped with
   `python3 scripts/command_run.py dispatch --seats <n>` before they go out; the receipt at
   `docs/development/reviews/2026-10-02-plan-3-backrest-coverage-review.md` embedding the verbatim `final_gate.py --json`
   success. Then `/fabrik-docs-review` over the two docs.
5. The full gate: `python scripts/final_gate.py --check --json` → `"status": "success"`, and
   `python scripts/enforcement/check_convergence.py` → exit 0.
6. Commit Phase C (`Agent-Phase: C`), push, then `python3 scripts/merge_request.py request --review <the receipt>
   --item W-5c4ad6a6` and send the printed `SendMessage` line.

**Rollout — OPERATOR-GATED, never executed by an agent (after infra merges into master).**
- V3. Read the next hourly cron run's backrest lines in `/var/log/fabrik-audit-all.log` (or run it by hand from the main
  checkout: `PYTHONPATH=/opt/fabrik/src /opt/fabrik/.venv/bin/python /opt/fabrik/scripts/audit_all_registrars.py`). Expected:
  tryton-crm and zitadel read `paper plan <id>-data: remove it` with their real paths covered (`docker-volumes`, the
  `postgres-<db>` dump directory); every other persistent spec reads `present`, `unprotected`, a missing dump directory, or
  the shape mismatch — each line read before V4.
- V4. On the operator's go, remove each paper plan V3 listed (`python -c "from fabrik.drivers.backrest import
  remove_backup_plan; remove_backup_plan('<id>')"` from the main checkout — the driver writes a timestamped `.bak` first,
  `drivers/backrest.py:157-182`). The next hourly run reads `present` for both and `FabrikRegistrarDrift` resolves for the
  backrest registrar.

### Behavior Contract — Phase C
- **Given** the merged change, **When** `check_doc_sync.py` and `render_doc_script_links.py --check` run, **Then** both pass and `docs/reference/modules/drivers.md` names the four functions (C1; `spec § Documentation landing sites`)

## File Scope (owned paths)

- src/fabrik/drivers/backrest.py
- src/fabrik/orchestrator/infrastructure.py
- src/fabrik/audit.py
- tests/test_backrest_coverage.py
- tests/test_audit.py
- tests/orchestrator/test_infrastructure.py
- docs/reference/modules/drivers.md
- docs/infrastructure/vps-complete-inventory.md
- docs/superpowers/specs/2026-10-02-backrest-paper-backups-design.md
- docs/development/reviews/2026-10-02-plan-3-backrest-coverage-review.md

## Evidence

**Phase A.** The registrar's hardcoded path and the driver's id-only idempotency:
`src/fabrik/orchestrator/infrastructure.py:1137-1147`, `src/fabrik/drivers/backrest.py:109-155` (step 1 returns `EXISTS`
on an id match). The per-database dump directory: `src/fabrik/drivers/backrest.py:342-370`.
```text
$ sed -n 1140,1144p src/fabrik/orchestrator/infrastructure.py
            plan_id = f"{name}-data"
            paths = [f"/opt/{name}/data"]
            result = add_backup_plan(plan_id, paths, dry_run=dry_run)
            ctx.add_resource("backrest", plan_id, status=result.get("status"))
```
The persistent-spec inventory (`spec § Why this exists` 2), executed 2026-10-02 over `specs/services/*.yaml` and
`/opt/<repo>/compose.yaml`:
```text
specs scanned: 72; has_persistent_data: 21
tryton-crm | named: trytond-filestore | binds: ./trytond.conf
youtube    | named: crowdlex-audio,crowdlex-audio-text,crowdlex-logs,crowdlex-watchdog-state | binds: /var/run/docker.sock
(19 others: no named volume, no persistent bind; 15 of them needs_database=True, 4 test specs False)
```
**Phase B.** The status consumers:
```text
$ grep -n "status" scripts/audit_all_registrars.py | sed -n 1,4p
85:    - ``fabrik_audit_drift_total`` — 1 when status is ``drift``, else 0.
87:    - ``fabrik_audit_status`` — encodes the full status as a label so
88:      Grafana can chart missing/unknown/n/a separately.
107:            status = result.status if hasattr(result, "status") else str(result.get("status"))
$ grep -n '"missing"' src/fabrik/cli.py
1435:        "missing": "  ✗ ",
```
Rollback has no status filter: `src/fabrik/orchestrator/rollback.py:153-154` → `_rollback_backrest`
`:307-316`. The audit's host-path probe: `src/fabrik/audit.py:314-328`. The registrar's call site: `:634-635`; `spec`
is a local of `provision()` there.
**Phase C.** The doc anchors: `docs/reference/modules/drivers.md:33`, `:158-170`;
`docs/infrastructure/vps-complete-inventory.md:550-566`.

## Self-audit

- Grounding: the spec's three research seats (ledger, 37 rows) and the orchestrator's own reads of every cited line; the
  judge panel re-verified the spec's anchors independently (all three).
- (a) Coverage: I1-I8 and I11 map to Phases A-C and the rollout; I9-I10 have named destinations.
- (b) Signatures: `discover_persistence`, `read_plans`, `coverage`, `visible` (A) are what B calls in both the registrar
  and the audit; the registrar's new signature is called from one site (`:634-635`).
- Not yet at a fixed point: `/fabrik-plan-review` runs next.

## Residual unknowns

- **Open — vps1's live plan list and Backrest binds.** A read-only probe this session was refused (production reads);
  rollout V3 reads them through the code this plan adds, and a missing host plan reads `drift`, never `present`.
- **Open — a compose with a custom `name:`.** The name fallback catches its containers; a miss reads as the shape
  mismatch, never silence.
- **Resolved:** what Backrest does with a missing path (ledger brk-5, brk-7); where the registrar's SSH goes for a spoke
  (`target_vps`, `cli.py:972-974`); that no consumer reads backrest `missing`.

## Coverage Checklist

Every row starts UNCHECKED and is adjudicated by `/fabrik-plan-review`.

| Class | Verdict |
|---|---|
| FLOOR core/35-security-auth — secrets, auth, config via env | UNCHECKED |
| FLOOR core/25-data-postgres — database, backups | UNCHECKED |
| FLOOR core/30-ops — volume backup rule, admin processes | UNCHECKED |
| FLOOR 12-Factor — all twelve axes against what the plan steps | UNCHECKED |
| MATCHED core/10-python — no deps-file edits, no file logging | UNCHECKED |
| MATCHED core/40-documentation — heading levels, the docs the change makes stale | UNCHECKED |
| MATCHED core/45-testing-strategy — one test per behaviour, watched-fail-first | UNCHECKED |
| MATCHED ai/50-agentic — not engaged (no LLM) | UNCHECKED |
| Production-write safety: no delete, no zero-path plan, no plan for an invisible path | UNCHECKED |
| Secret handling: `read_plans` never moves the repo section off the VPS | UNCHECKED |
| fail-open vs fail-closed on every probe (discovery, plans, visibility) | UNCHECKED |
| boundary/sentinel/prefix collisions (`/opt/a` vs `/opt/ab`, trailing slashes, exclude globs) | UNCHECKED |
| rollback and destroy only touch what this run created | UNCHECKED |
| behavior-without-a-test | UNCHECKED |

The rubric this plan's reviews inject into every seat brief, run on the plan's own `## File Scope (owned paths)`:

```bash
python3 scripts/review_rubric.py --changed src/fabrik/drivers/backrest.py src/fabrik/orchestrator/infrastructure.py src/fabrik/audit.py tests/test_backrest_coverage.py tests/test_audit.py tests/orchestrator/test_infrastructure.py docs/reference/modules/drivers.md docs/infrastructure/vps-complete-inventory.md
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

### ai/50-agentic.md  (hit: src/fabrik/orchestrator/infrastructure.py, tests/orchestrator/test_infrastructure.py)
- **Claude** for reasoning + tool use. **Operational** agents (sysadmin, watchdog, bootstrap) run via **Claude Code CLI w/ subscription OAuth** — never `ANTHROPIC_API_KEY`.

### core/10-python.md  (hit: src/fabrik/audit.py, src/fabrik/drivers/backrest.py, src/fabrik/orchestrator/infrastructure.py)
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

### core/40-documentation.md  (hit: docs/infrastructure/vps-complete-inventory.md, docs/reference/modules/drivers.md)
- > **⚠️ `docs/OPERATIONS.md` + `docs/DEPLOYMENT.md` are FLEET-AI INTERFACES, not just docs (D-065).**
- **Tier-1 (author → verify → converge; the author leg is NATIVE while the pool is OFF, D-181 — `scripts/doc_reconcile.py`'s pool author cannot dispatch):** for each **mechanically-detectable** doc whose Doc-Sync trigger fired (`docs/QUICKSTART.md` · `docs/CONFIGURATION.md` · `docs/data-contract.md` · `docs/SERVICES.md` · `docs/OPERATIONS.md` — the reliable-signal subset), `scripts/doc_reconcile.py` dispatches a cheap OpenRouter-pool author (`libs.subagents`, `pick_models("docs")`) to emit a **minimal structured patch**, **verifies it before applying** (a symbol cross-check catches invented endpoints; the orchestrator injects a higher-assurance native-Claude verify), and loops to a zero-edit round. Runs per phase in `/fabrik-execute-plan`; never blocks (fail-safe). The other docs (CHANGELOG, INDEX, FEATURES, RESILIENCE, PORTS, the READMEs, `db/schema.sql`, …) have no reliable mechanical content-signal → they rely on the touch-on-change backstop below + your own edit (force-update, not force-correct).
- The SSOT is the type-aware registry (`scripts/enforcement/_doc_registry.py::PROJECT_DOCS`) — this table is its project-facing rendering, kept in step, never a second truth. `/fabrik-plan-after-chat` (the plan set's spine + tickets — the ticket-format authority) injects these rows per ticket as its `Docs:` line.
- Standalone work (not plan execution) → `Agent-Role: primary`. Trailers go below a blank line, above `Co-Authored-By`. ⚠️ The trailer block must be its OWN paragraph with NO blank line inside it: git parses only the LAST paragraph, and only if it is all-trailers. A blank line before `Co-Authored-By:` demotes everything above it to prose; so does a prose line glued to the top of the block. Measured 2026-08-15: 200 of the last 200 hub commits carried `Agent-Role:` and only 10 parsed, because the old example here shipped the blank line.
- **⚠️ Link it or it is decoration.** *Measured:* requests for files that do NOT exist came ~zero from AI bots — agents never go looking. It follows (inference, not measurement) that a file only gets read when something points at it: reference it from the docs index or README.
- ⚠️ **In THIS repo `llms.txt` is GENERATED** (`scripts/generate_capability_index.py`, refreshed daily) — never hand-edit it; change the generator. A project writing one by hand owns it.
- either way. Cheap and reversible — never at the expense of `OPERATIONS.md`/`DEPLOYMENT.md`, which are the load-bearing agent interfaces (D-065).
- **No skipped heading levels** — `##` to `###`, never `##` to `####`
- **Fenced code blocks only** — never indented code (AI treats it inconsistently)

### core/45-testing-strategy.md  (hit: tests/orchestrator/test_infrastructure.py, tests/test_audit.py, tests/test_backrest_coverage.py)
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

# promote-to-check_*: 83 injected mandate(s) look deterministically greppable — their backtick literals, one line each (the full mandates are ABOVE, not repeated: re-emitting ~20 FLOOR lines verbatim doubled the rubric and got it skimmed — web-ecommerce-factory 01M1QEY5, 2026-09-05)
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
