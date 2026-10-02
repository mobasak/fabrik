# Postgres allocation registry: an hourly reconcile that registers what specs claim

Status: CONVERGED (/fabrik-plan-review 2026-10-02 with plan-2, Size: small — awaiting design approval)
Size: small (≈230 lines, 5 files)
Profile: delta — every intake item maps to code that exists today: the registry writer
(`src/fabrik/drivers/postgres.py::register_allocation`), the per-spec audit (`src/fabrik/audit.py::audit_postgres`), the
hourly audit cron (`scripts/audit_all_registrars.py`) and its alert rule (`configs/prometheus/rules/fabrik-drift.yml`).
Rejected alternatives, Lifecycle, the constraints digest and the fabrik-lib verdict are kept short; the delta adds one
automated consumer (the cron becomes a writer) and that section is written in full.

Work item: W-714ae2cf. Ruling: D-498. Beat: fleet (deploy and monitoring).
Research ledger: `docs/reference/research/2026-10-02-postgres-allocation-reconcile-ledger.md` (27 rows, every fact fetched
2026-10-02; every quote below was string-matched against the raw source the same day).

## Personas

- **PRIMARY — the operator.** In their words: *"we must rule out 3 ways in your work revise"* and *"why there is orphan
  postgres databases exist"*. They want a registry that cannot silently drift, and a red signal when it does. Their loop,
  counted: (1) a database exists that the registry lacks, by any of the three causes; (2) within an hour the reconcile
  registers it, or (3) if it cannot, an alert names the database and the reason. **Step budget: 0 operator steps on the
  healthy path once the one-time opt-in is done (the operator sets `apply` after reading a report run, D4), 1 (read
  the alert) on the failure path.** Today the healthy path costs a re-apply per orphan (a Gate-2 deploy)
  and the failure path costs an investigation, because the drift alert says only "drift".
- **The hourly audit cron (automated)** — `scripts/audit_all_registrars.py`, run from the hub crontab (`0 * * * *`,
  `/opt/fabrik/src`, log `/var/log/fabrik-audit-all.log`). **New duty: it is the registry's reconciler** — it registers
  spec-claimed databases, retries failed registrations, and pushes the heal and liveness series. It holds the only new
  write.
- **`create_database` (automated)** — the CREATE-time writer at `postgres.py:290-480`, called by the postgres registrar
  (`orchestrator/infrastructure.py:770`) and the database pre-provision step (`orchestrator/__init__.py:318`). Duty
  unchanged: it registers on CREATE. It stays the fast path; the reconcile is what makes the registry converge.
- **`audit_postgres` (automated)** — classifies each spec's database into present / drift / missing (`audit.py:137-224`).
  Duty unchanged except that it uses the same database-name rule as the registrar.
- **Prometheus and Alertmanager (automated)** — evaluate `fabrik-drift.yml` and route to the existing `telegram` receiver.
  New duty: two more rules.
- **`drop_database` and `fabrik destroy` (automated)** — the only path that removes an entry (`postgres.py:1806`). Duty
  unchanged; the reconcile never deletes.

## Goal

Make the postgres allocation registry converge on its own: every database that a spec claims is registered within one
audit cycle whatever put it there, a registration that fails is retried and surfaced, and the two live orphans,
`zitadel` and `site_provisioner`, are registered through that same mechanism.

## Why this exists

`FabrikRegistrarDrift` fires for `zitadel` and `site_provisioner` (live 2026-10-02). The registry is written only on the
CREATE path (`postgres.py:340-342` returns early for an existing database), so three causes leave an entry missing for good
(D-498):

1. **Created outside the CREATE path.** `site_provisioner` predates the registry (it existed by 2026-05-14, the registry
   arrived 2026-05-16, `git log -S'def register_allocation'` → `ec17faa13`), and a hub rebuild restores it from a volume
   (`scripts/bootstrap/bootstrap-hub.sh:1231`), which never calls `create_database`.
2. **A CREATE-time registration failed once.** Both writes are wrapped in a warning-only `except` (`postgres.py:366`,
   `:461`) and nothing retries them. `zitadel` was created through `create_database` on 2026-08-28 (archived deploy plan
   `docs/development/plans/archived/2026-08-28-plan-deploy-zitadel.md:22`), both registration paths existed then, and yet
   it has no entry.
3. **A write after a failed read saved over the registry.** CLOSED by ea99ee94f and f9475148a: a failed read, an unreadable
   file or a refused `sudo` now raises, and every caller skips the write.

The audit already finds the orphans every hour (`audit.py:197-202` returns `drift` for a database with no entry); it
cannot fix them, and the alert cannot say why the registry is wrong.

## Chosen approach — B, reconcile in the hourly audit job

The audit cron already visits every database-backed spec each hour from the hub, already finds the orphan quadrant
(`audit.py:197-202`), and already holds the SSH access the registry write needs. Giving it the repair makes the registry
level-triggered: a missed or failed registration is found again next hour, whatever caused it. That is the field's
current practice for state that must converge despite missed events. Kubernetes' API conventions call behaviour
"level-based rather than edge-based", which "enables robust behavior in the presence of missed intermediate state
changes" (ledger rec-1). Kubebuilder warns that logic written "according to specific events … may lead to … resources
becoming stuck and requiring manual intervention" (rec-4), which is exactly what cause 2 is today. HCP Terraform finds
out-of-band drift with periodic assessments, not only at apply time (rec-10).

The repair is additive and idempotent; anything destructive stays a reported drift. Argo CD's automated sync "will not
delete resources" unless pruning is opted into (rem-7); Azure Policy auto-remediates the missing-resource case
(rem-4); AWS Config makes automatic remediation a per-rule choice (rem-1). Failure is surfaced the way Prometheus
documents for batch jobs: "The key metric of a batch job is the last time it succeeded" (obs-1), alerting once it "has
not succeeded recently enough", allowing "at least enough time for 2 full runs" (obs-2), with a failure series rather
than a log line (obs-4).

Judge panel (three Sonnet seats, approaches given alphabetically with no recommendation): **2 of 3 ranked B first; judge 2
ranked A first and failed B.** Judge 2's case rested on two points:
- *A is cheap because `fabrik reconcile-all` re-runs the registrars without a deploy.* **Refuted:** `reconcile-all` builds
  its deployed set from `CoolifyClient().list_applications()` (`src/fabrik/cli.py:1540-1545`), and Coolify was
  decommissioned 2026-05-30 (`CHANGELOG.md:10638`), so it exits 1 or skips every spec. A's live orphans therefore still
  need two Gate-2 re-applies. The dead verb is filed as W-ef765f8d.
- *An unattended hourly writer to a production file is the risk class the hub's hard stops exist for, and adopting drift
  is a person's call (ledger rec-11).* **Accepted as a risk, mitigated, and carried to approval as a split verdict:** B
  writes only an entry that a spec already declares (`needs_database` names the database, so the desired state is written
  down, not guessed), never overwrites or deletes, runs a `report` pass before its first write, and has an off switch
  (D3, D4, Validation).
Second open point carried to approval: judge 3 asked whether a healed database should be recorded as `owner="fabrik"`
(this spec, because a spec claims it) or with a marker that it was adopted rather than created (see Decisions taken).

## Rejected alternatives

- **A — Heal on re-apply** (`create_database`'s exists branch registers if absent). Edge-triggered: cause 1 and cause 2
  heal only when someone re-applies that service, which is a Gate-2 deploy; `site_provisioner` is rarely re-applied. It
  adds an SSH read to every re-apply of every database-backed service, and it surfaces a failure only on one deploy's
  resource status. It was built and reverted in this session (48dc71495 → ea99ee94f) when two reviewers named this spec's
  approach as a real alternative. Kubebuilder's event-keyed warning (rec-4) is the field's verdict on it. Keeping it as an
  extra fast path is rejected too: the CREATE path already registers, and the reconcile catches anything it misses within
  an hour, so a second writer would add risk without closing a cause.
- **C — Operator-run verb** (`fabrik audit-registrars --reconcile`). Retries and surfaces nothing unless a person runs it,
  which is the failure mode D-498 exists to remove; judges 1 and 3 both failed it on set-and-forget.
- **A new dedicated cron or a VPS-side job.** A second schedule duplicates the audit cron's walk and its SSH path; a
  VPS-side writer would need the spec tree, which lives only on the hub.
- **Moving the registry into a Postgres table.** Removes the file lock and makes the repair one `INSERT … ON CONFLICT DO
  NOTHING`, but migrates a documented contract (`agents-fabrik.md:413`, `vps-complete-inventory.md:815`) for two orphans;
  recorded under Lifecycle as the retirement path.

## What exists today (grounded)

| Piece | Where | What it does |
|---|---|---|
| Registry file | `/opt/monitoring/configs/postgres/allocations.json` on vps1 (`postgres.py:72`) | `{db: {owner, spec_id, user, notes}}`; documented at `docs/infrastructure/vps-complete-inventory.md:815-835` and `agents-fabrik.md:413` |
| Writer | `postgres.py::register_allocation` (`:1870-1923`) | read-modify-write under `file_lock("postgres-allocations")`, a single-host `fcntl.flock` (`src/fabrik/locks_local.py:60`); overwrites any existing entry |
| Reader | `postgres.py::_load_remote_allocations` (`:1812`) | `sudo sh -c 'if test -e P; then cat P; fi'`; a failed read raises (f9475148a) |
| Owner lookup | `postgres.py::_db_owner` (`:572`) | `pg_get_userbyid(datdba)` for one database |
| Registrar name rule | `orchestrator/infrastructure.py:722-727` | `depends.postgres` if set, else `spec.id.replace('-', '_')` |
| Audit name rule | `audit.py:140` | `spec.id.replace('-', '_')` only — differs from the registrar when `depends.postgres` is set |
| Shared name rule | `app_role_check.py:782-804` (`_db_name_for_spec`) | the registrar's rule, already used by `infrastructure.py:512`, `:537`; refuses a non-string `depends.postgres` |
| Audit | `audit.py::audit_postgres` (`:137-224`) | four quadrants: present · drift (orphan DB) · drift (stale entry) · missing |
| Cron | `scripts/audit_all_registrars.py` (`main` `:129-181`) | `audit_all` per spec → `fabrik_audit_drift_total` + `fabrik_audit_status` → pushgateway job `fabrik-audit` by `POST` (`:119`); no last-success series |
| Alert | `configs/prometheus/rules/fabrik-drift.yml` | `FabrikRegistrarDrift: fabrik_audit_drift_total > 0, for: 10m`; reaches vps1 via `scripts/sync_prometheus_to_vps.sh` |

## The delta

D1. **One database-name rule.** `audit_postgres` stops deriving the name itself (`audit.py:140`) and calls the existing
    `fabrik.app_role_check._db_name_for_spec(_spec_to_dict(spec))` (`src/fabrik/app_role_check.py:782-804`), which already
    mirrors the registrar's rule (`depends.postgres` if set, else the name or id snake-cased) and refuses a non-string
    `depends.postgres`. Without this, a spec that pins `depends.postgres` is audited under a name it never created, and
    its orphan is never found. A `SpecResolutionError` from the helper becomes an `unknown` audit result naming the cause.
    The registrar's own inline copy (`infrastructure.py:722-727`) is unchanged; the helper's docstring already names it
    as the rule it mirrors.

D2. **Register only if absent, decided inside the lock.** `src/fabrik/drivers/postgres.py` gains
    `register_allocation_if_absent(db, *, spec_id, user, owner, notes) -> bool`: under the same `file_lock`, after the
    read, an existing entry is left untouched and it returns `False`; otherwise it writes and returns `True`. It shares
    one private body with `register_allocation`, whose signature, return value and three callers are unchanged. The
    reconcile writes only through it, so a concurrent `fabrik apply` or a hand-seeded entry is never overwritten, and the
    reconcile knows whether it actually wrote.

D3. **The reconcile.** A new module, `src/fabrik/registry_reconcile.py`, exposes
    `reconcile_postgres(audits, claims, *, claims_complete: bool, dry_run: bool) -> list[HealResult]`, where `audits`
    maps each spec id to the `audit_all` result the cron already computed, `claims` maps each database to the spec ids
    that claim it (from `claims(specs)`, below) and `claims_complete` says no spec failed to load or audit and no name
    failed to resolve. For each spec whose `postgres` result is `drift` with
    `actual.found is True` and `actual.in_registry is False` (the orphan quadrant, `audit.py:197-202`), with
    `db = actual.db_name`: a run in which any spec failed to load, or any database spec failed to resolve its name → `failed`, reason
    `claims-unresolved`, for every candidate (the provisioner raises rather than guess in that case,
    `orchestrator/infrastructure.py:506-508`); a database two or more specs claim → `shared` (below), the claims counted
    from every loaded database spec's name rule, never from audit outcomes, so an `unknown` sibling still counts; in `report` mode → `would-register`;
    otherwise `user = _db_owner(db)` (`postgres.py:572`) — `None` (the database is gone, or its owner fails validation) →
    `failed`, reason `owner-unresolved`, no write — then `register_allocation_if_absent(db, spec_id=..., user=user,
    owner="fabrik", notes="registered by the hourly reconcile <UTC date>")` → `registered` or `already-present`; any
    exception → `failed` with the exception class as reason. Each call is one `HealResult`
    (`spec_id`, `db`, `outcome ∈ {registered, already-present, would-register, shared, failed}`, `reason`). **It never deletes,
    renames or creates a database, and never touches an entry whose database is missing** — that stale quadrant stays a
    reported drift for a person (Argo CD prunes only on opt-in; Terraform's plan never applies itself; ledger rem-5, rem-7).
    **It adopts only what exactly ONE spec claims** — a database no spec names is not in the per-spec audit's reach and is
    left alone (HCP Terraform leaves adoption of out-of-band drift to a person; ledger rec-11); a database that two or more
    database specs resolve to (today `main`, claimed by `ai-model-catalog`, `compliance-ops`, `exam-coach` and
    `gmail-account-creator`) is outcome `shared` — reported, never written, because one registry entry cannot name one
    owner honestly. That is the posture the provisioner already takes for a shared database
    (`orchestrator/infrastructure.py:500-547`, `_shared_db_siblings`: "the answer would otherwise be a guess").
    `audit_postgres` also validates the name before its SQL (`_validate_identifier`), because `depends.postgres` carries
    no pattern (`src/fabrik/spec_loader.py:183`) and the reconcile then passes that name on to `_db_owner`.

D4. **The cron runs it.** `audit_all_registrars.py::main` keeps the loaded specs beside the results, calls
    `reconcile_postgres` after the first audit pass, re-audits only the specs it healed so the pushed drift gauge shows the
    repaired state in the same run, then renders and pushes. `FABRIK_REGISTRY_RECONCILE` selects the mode — `report`
    (**the default**: compute and push `would-register`, write nothing; Puppet's `noop`, ledger rem-6), `apply` or `off`.
    Read with `os.getenv("FABRIK_REGISTRY_RECONCILE", "report")` (35-security-auth.md:267); an unknown value is `report`.
    Because the hub crontab line sets no mode, the code itself guarantees nothing is written until the operator adds
    `FABRIK_REGISTRY_RECONCILE=apply` to it after reading a report run.

D5. **Surface every outcome.** Each run's push carries, besides the two existing gauges:
    - `fabrik_registry_heal_total{spec_id, db, outcome}` — one sample per `HealResult` this run (a gauge of 1; the attempt
      total and the failure total come from summing it, ledger obs-4); none on an hour with no orphans;
    - `fabrik_registry_heal_failed{spec_id, db, reason}` — 1 for each failed heal, with a one-word cause as `reason`
      (ledger rec-7); none when nothing failed;
    - `fabrik_audit_spec_errors` — the count of specs the run could not load or audit, every run;
    - `fabrik_audit_last_success_timestamp_seconds` — rendered only when the run had no spec error and the reconcile raised
      nothing uncaught (ledger obs-1). It travels inside the push, so a push that fails leaves the gateway's previous
      timestamp to age.
    The push switches from `POST` (curl's default with `--data-binary`, `scripts/audit_all_registrars.py:119`) to `PUT`:
    a `POST` replaces only the metric names present in the new push, so a heal-failed sample that stops being sent
    would keep its last value forever; a `PUT` replaces the whole `fabrik-audit` group each run (ledger obs-8). The
    script is the only definition of that job in this repo (`PUSHGATEWAY_JOB`, `:63`). Under `PUT` a spec skipped for an
    error loses its drift series for that run, which is why such a run withholds the timestamp.
    And `fabrik-drift.yml` gains two rules:
    - `FabrikRegistryHealFailed: max by (spec_id, db) (fabrik_registry_heal_failed) > 0` with `for: 2h` (two hourly runs
      failing before it pages, ledger obs-2; aggregated so a changing `reason` label does not reset the window);
    - `FabrikAuditStale: (time() - fabrik_audit_last_success_timestamp_seconds > 10800) or
      absent(fabrik_audit_last_success_timestamp_seconds)` (3 h = more than two missed runs, ledger obs-2; `absent` covers a
      pushed run that carried no timestamp, which a `PUT` turns into a missing series, and the time before the first
      success). Without it a dead cron freezes every gauge in the pushgateway at its last value, which reads as healthy
      (ledger obs-5).
    Each heal also writes one log line naming the database and the outcome (self-healing.md:96).

D6. **The two live orphans.** No special-casing. After the operator turns on `apply` (Validation, rollout step 3), the
    next hourly run on the hub (`/opt/fabrik/src`, the main checkout) registers `zitadel` and `site_provisioner` if they are
    still orphans. D1 also moves the audit of 9 of
    the 23 database-backed specs onto the database they really use (the specs that pin `depends.postgres`, counted by the
    plan's probe), so the first run can find more orphans than these two: any of those 9 whose database exists without an
    entry. With the default `report`, the first runs after the merge write nothing; the operator reads one of them and then
    turns on `apply` (see Validation).

## Contract deltas

None. No data contract, UI design or `shape:` field changes. The registry's JSON schema is unchanged; `notes` gains a
value. The pushgateway job `fabrik-audit` gains three metric families and the alert rule file gains two rules.

## Cost

No new service, dependency or vendor. One extra `_db_owner` query per healed database (zero on a healthy hour), and the
registry read the audit already makes. The reconcile adds about 1 s per orphan to an hourly run.

## Validation

- Per behaviour, red first (45-testing-strategy.md:22): an orphan is registered with its real owner; an existing entry is
  never overwritten, including when it appears between the audit and the write (D2's in-lock check); `report` (and the
  unset default) writes nothing and pushes `would-register`; `off` does nothing; a failed write or an unresolved owner
  yields `failed` with its reason and the heal-failed series; a database two specs claim yields `shared` and no write; the
  stale-entry quadrant and an unclaimed database are never touched; a run with a spec error renders no last-success
  timestamp; the shared name rule returns `depends.postgres` when set, and an invalid name yields `unknown` with no SQL.
- The alert rules pass `promtool check rules`, run from the image vps1 runs (`configs/monitoring-compose.yaml:47`,
  `prom/prometheus:v3.2.1`): `docker run --rm -v "$PWD/configs/prometheus/rules:/r:ro" --entrypoint promtool
  prom/prometheus:v3.2.1 check rules /r/fabrik-drift.yml`. `promtool` is not installed on the hub (`which promtool` →
  not found); docker is. A promtool rule unit test (`promtool test rules`) proves `FabrikAuditStale` fires both on age and
  on absence, and `FabrikRegistryHealFailed` fires after 2 h even when `reason` changes mid-window.
- Rollout, in order: (1) merge — the cron now runs in the default `report` mode; (2) read one run's `would-register` and
  `shared` lines in `/var/log/fabrik-audit-all.log` (or run it by hand) — the fire-rate measurement FIX DIRECTIVE 5
  requires before the mechanism writes; `zitadel` and `site_provisioner` are expected, any of the 9 re-named specs may
  appear, and `main`, if it appears, reads `shared`; (3) the operator adds `FABRIK_REGISTRY_RECONCILE=apply` to the crontab line and the
  next hourly run heals; (4) confirm `fabrik_audit_drift_total{registrar="postgres"}` is 0 for `zitadel` and
  `site-provisioner`; (5) sync the rules with `scripts/sync_prometheus_to_vps.sh` and confirm both new rules load.

## Decisions taken

- The reconcile lives in the existing hourly audit job, not a new cron (see Chosen approach).
- It registers only spec-claimed databases and never deletes (D3).
- `owner="fabrik"` for a healed database: the spec claims it, which is what "fabrik" means in the registry
  (`agents-fabrik.md:413`). A hand-made entry with another owner is never touched (D2).
- The recorded `user` is the database's real owner role from `pg_database`, never an assumed name (D3), because a
  restored or hand-made database is often owned by `postgres`; when it cannot be read, nothing is written.
- The default mode is `report`, so the code, not a rollout instruction, keeps the writer off until the operator opts in
  (D4).

## Lifecycle

- **First run:** the `report` pass by hand, then the next hourly `apply` run heals the backlog (two known databases, plus
  any of the 9 specs D1 re-names whose database turns out unregistered).
- **Growth:** one `audit_postgres` per database-backed spec already runs hourly; the reconcile adds work only for orphans.
  Trigger to revisit: more than 5 heals in one run (a sign something upstream keeps creating unregistered databases — find
  the generator), or `FabrikRegistryHealFailed` firing for the same database for a day.
- **Failure:** a failed heal leaves the drift gauge at 1 (`FabrikRegistrarDrift` still fires), adds a named
  `FabrikRegistryHealFailed`, and retries next hour. A dead cron, or a run with a spec error, raises `FabrikAuditStale`.
  Removing `FABRIK_REGISTRY_RECONCILE=apply` from the crontab line (or setting `off`) turns the writer off without a
  deploy.
- **Retirement:** if the registry moves into Postgres itself (a table instead of a file), the reconcile becomes one
  `INSERT … ON CONFLICT DO NOTHING` and this module goes.

## Intake Inventory

| I# | Item (anchored) | Disposition | Where |
|---|---|---|---|
| I1 | *"we must rule out 3 ways in your work revise"* (D-498) | IN | Why this exists; causes 1-2 → D1-D5; cause 3 closed by ea99ee94f, f9475148a |
| I2 | *"register existing unregistered databases"* | IN | D3 |
| I3 | *"retry failed registrations"* | IN | D4 (every hourly run retries; D2 keeps it idempotent) |
| I4 | *"surface the failure"* | IN | D5 |
| I5 | *"then register zitadel and site_provisioner through it"* | IN | D6 + Validation rollout |
| I6 | *"why there is orphan postgres databases exist"* | IN | Why this exists |
| I7 | the backrest half of the same drift alert (W-714ae2cf's original title) | OUT-OF-SCOPE | W-5c4ad6a6 (spec chain, backrest paper backups) |
| I8 | a database that no spec claims (e.g. created by hand, not in any spec) | OUT-OF-SCOPE | reported nowhere today; adopting it is a person's call (ledger rec-11) — W-78d2a2df |
| I9 | an entry whose database is missing (stale quadrant) | OUT-OF-SCOPE | stays a reported drift, never auto-deleted (D3; ledger rem-5, rem-7) |
| I10 | `fabrik reconcile-all` is dead (found by the judge panel: it lists apps through the retired Coolify) | OUT-OF-SCOPE | W-ef765f8d |

## Constraints digest

| Rule | Verbatim | Source | Applies |
|---|---|---|---|
| No silent swallow | "Silent swallow is data loss; you've removed the only signal a watchdog could see." | `.windsurf/rules/core/self-healing.md:73` | D5: every failed heal is a series and a log line |
| No silent action | "Each step emits a Prometheus counter + a structlog row carrying the resource name (no silent action)." | `.windsurf/rules/core/self-healing.md:96` | D5 |
| Ladder scope | "If a failure class doesn't appear in the table above, the rule is: **add the row to this pack first, then the response logic to the code.**" | `.windsurf/rules/core/self-healing.md:64` | the pack MATCHES this plan (its `**/health*` glob, `self-healing.md:3`, hits `docs/reference/health-monitoring.md`). Its ladder rows are a service's runtime failure classes; this reconcile is a new hub-side self-healing response, so its row ("registry drift → hourly additive reconcile → `FabrikRegistryHealFailed`") is proposed to the pack's owner (infra, `.windsurf/rules/` is a fleet-synced surface) by fabrik-mail before Phase C lands, per the row-first rule — never edited into the pack from this plan |
| Count fail-open | "Say it out loud, and COUNT it." | `.windsurf/rules/core/58-resilience.md:408` | D5 |
| Config | "Mandate: config via env vars only (`os.getenv(\"KEY\", \"default\")`)" | `.windsurf/rules/core/35-security-auth.md:267` | D4's mode switch |
| Shared server | "\"Own database\" means a DATABASE on `postgres-main`, never a database SERVER" | `.windsurf/rules/core/25-data-postgres.md:26` | unchanged; the reconcile reads `postgres-main` only |
| Red first | "**Watched-fail-first** (for tests this change adds or modifies …)" | `.windsurf/rules/core/45-testing-strategy.md:22` | Validation |

## fabrik-lib verdict

Build — no fabrik-lib module touches the hub's own control plane (`/opt/fabrik-lib/README.md` module table: none for
registry reconciliation). Not a fabrik-lib candidate: it is hub-only, used by one consumer.

## Shape / infra implications

None for any project's `shape:`. Hub-side only: the cron gains a write; the alert rules change on vps1 via
`scripts/sync_prometheus_to_vps.sh` (an operator-run sync).

## Documentation landing sites

- `docs/reference/health-monitoring.md` — the `audit_all_registrars.py` AFTER-EDIT target: the reconcile, the new series,
  the two rules and the mode switch.
- `docs/infrastructure/vps-complete-inventory.md` § Postgres allocation registry (`:815`) — "written by `create_database`
  and reconciled hourly by the audit cron". `agents-fabrik.md:413` is a governance-sync trigger whose sentence stays true
  (the reconcile writes through the same driver), so it is not edited here (plan intake I11).
- `docs/CONFIGURATION.md` + `.env.example` — `FABRIK_REGISTRY_RECONCILE` (Doc Sync Matrix: new env var).
- `INDEX.md` — the new module and its test file; `CHANGELOG.md`.

## Open / blocking unknowns

- **Resolved:** why the orphans exist (Why this exists); whether the audit can see both (yes, `audit.py:197-202`); how rules
  reach vps1 (`sync_prometheus_to_vps.sh`).
- **Open — the reconcile's fire rate.** Resolution: the rollout's `report` pass (Validation step 2) lists every database it
  would register; the default `report` keeps it from writing until the operator turns on `apply`.
- **Open — the push path's own health.** If the pushgateway or Alertmanager is down, neither new rule fires (ledger obs-7).
  Resolution: out of scope here; `FabrikAuditStale` covers a dead cron, not a dead Prometheus.
