# Plan 1 — Repair the subagent flywheel's recording path (2026-09-02)

**Status:** DRAFT
**Source of truth:** live measurement of `fabrik_analytics.subagent_runs` + `/opt/fabrik/.tmp/subagents/*.jsonl`, this session. No `/fabrik-spec` doc — the design was settled by measurement, not brainstorming (RICH by the Phase-0 gate: goal and approach are both pinned).
**Owner beat:** intel (models · benchmarks · flywheel).

## What we already agreed

- The flywheel's **data is sound and useful**; its **recording path is half-dead**. Fix the plumbing, don't touch the ranking maths except where a measured defect demands it.
- **The operator did not configure the price cap.** It was the pool's own always-on default, removed 2026-07-21 (`504af55f`). This plan never treats a config artefact as a model verdict.
- Fixes land **smallest-blast-radius first**: hub-local before fleet-synced, data before code, code before schema.
- Operator granted cross-repo `.env` write authorisation earlier this session; it is relied on in Phase A only.

## Global Constraints (every phase inherits these)

- **Shared tree, three sessions.** Explicit pathspecs only (`git commit -- <paths>`), `git diff --cached --numstat` before every commit, `git reset -q HEAD -- <paths>` after. Never `git add -A`, never `--amend`, never touch a sibling's dirty file.
- **`libs/subagents` is `VENDORED_DIRS`** (`scripts/fabrik_synced_manifest.py:115`) kept byte-identical to canonical `/opt/fabrik-lib/subagents`. **48 vendored copies exist** (`ls -d /opt/*/libs/subagents | wc -l` → 48). Any edit there is a cross-repo change to fabrik-lib FIRST, then a re-vendor, then a sync. Phases D and F carry that cost explicitly; Phases A–C and E deliberately avoid it.
- **`pg_ledger` is FAIL-OPEN by contract** — a DB error must never break a run — *"FAIL-OPEN — a Postgres error/outage NEVER breaks a run"*, `pg_ledger.py:15-17` (an earlier draft cited `:19-21`, which is the per-`agent_id` aggregation note). No phase may introduce a raise on the recording path.
- **`flush_outbox` is AT-LEAST-ONCE, by documented design** — "a crash BETWEEN commit and cleanup can
  re-insert the batch once … exactly-once would need a unique dedup key on the shared schema"
  (`pg_ledger.py:876-878`). Accepted upstream as minor skew for an aggregate flywheel; A1 makes it
  DAILY across 8 repos, which raises the exposure. **Phase F is where a dedup key would go if it ever
  matters** — noted there, not smuggled into A. Until then, aggregation must tolerate a duplicated
  `agent_id` batch (it already reconciles per `agent_id`, so a duplicate row does not double-count `n`).
- **12-Factor XI/XII:** the flush walker logs to stdout (the `_step` wrapper captures it); the Phase-F migration is a one-off process, never run from an import or a startup hook.
- **No crontab writes.** `daily_refresh.sh` is already scheduled; wiring goes there. A cron line, if ever needed, is handed to the operator (box rule, crontab wipe 2026-08-19).
- **Denominators stated.** Every count in an artefact this plan produces names its population and its bound.

## Context Ledger

| Source | What binds | Grounded ref |
|---|---|---|
| `core/62-using-subagents.md` (ACTIVE) | the fanout → `set_quality` → `record_agent_run` flywheel contract; pool-default for gradeable fan-out | pack §Flywheel rule |
| `core/25-data-postgres.md` (ACTIVE) | migration discipline, nullability, schema evolution — binds Phase F's `subagent_runs` change | pack §migrations |
| `core/45-testing-strategy.md` (ACTIVE) | one test per user-observable behaviour, risk-ordered, watched-fail-first | pack §Behavior Contract |
| `core/55-observability.md` (ACTIVE) | structured logs to stdout; **a silent drop is an observability defect** — the whole premise of Phase D | pack §structured logs |
| `libs/subagents/pg_ledger.py` (vendored module) | `flush_outbox(dsn=None, *, outbox_dir=None, connect=None, receipt_dir=None, reason_sink=None) -> int`; flock-serialised; processes a crashed `.flushing.jsonl` residual automatically | `pg_ledger.py:847-869` |
| `scripts/fabrik_synced_manifest.py` | `libs/subagents` is a `VENDORED_DIRS` entry → the 48-copy blast radius. ⚠️ The list is NO LONGER single-entry — `libs/health_probe` was added (D-082) while this review ran, so cite the ENTRY, never the list's shape | `:115-116` |
| `scripts/kilo-benchmarks/daily_refresh.sh` | the `_step "<label>" <cmd>` wrapper is the only sanctioned way to add a scheduled step (per-step timing + logging) | `:129`, examples `:143`, `:151`, `:420` |
| `src/fabrik/orchestrator/infrastructure.py` | `fabrik apply` injects `SUBAGENT_PROJECT` unconditionally and the `postgres-main:5432/fabrik_analytics` DSN **only when the role creation returned a password** (`if sa["ins"].get("password"):` at `:750`) — an earlier draft called the DSN itself unconditional, which the guard refutes | `:734-755`, DSN f-string `:751-754` |
| `scripts/kilo-benchmarks/rank_task_subagents.py` | the ranking reads **local** postgres only — `"Queries fabrik_analytics.subagent_runs on local postgres via sudo -u postgres psql"` | `:17`, `DB_NAME` at `:43` |
| `libs/subagents/select.py` | the always-on price cap is **gone**; only opt-in `max_cost_per_mtok` filters now | `:72`, `:85`, `:526` |
| `libs/subagents/loop.py` | `_apply_max_price` still sets OpenRouter's `provider.max_price` same-price ceiling; caller-set value wins | `:40-82`, kimi case documented at `:65` |
| fabrik-lib | **no new module** — this plan repairs an existing vendored one. No `🆕 fabrik-lib candidate`. | `fabrik-lib/README.md` module table consulted |

## ✅ RESOLVED (was a blocking unknown) — there is no split brain in practice

`fabrik apply` injects a `postgres-main:5432/fabrik_analytics` DSN into every deployed project
(`infrastructure.py:748-755`) and `ensure_shared_analytics_db()` applies the DDL there, while the
ranking that drives `pick_models` reads **local** postgres only (`rank_task_subagents.py:17`). That
looked like two flywheel databases with only one feeding routing.

**Measured 2026-09-02 during this review — the postgres-main table is EMPTY:**

```
$ ssh vps "sudo docker exec postgres-main psql -U postgres -d fabrik_analytics -tAc \
    \"SELECT count(*), count(DISTINCT agent_id), min(ts)::date, max(ts)::date, count(DISTINCT project) FROM subagent_runs;\""
0|0|||0
```

The table exists, no deployed service has ever written a row, and the local database IS the whole
population. Three consequences, each correcting an earlier statement:

1. **The figures in this plan are TOTALS, not a half.** An earlier draft disclosed them as "the
   dev-time half only" — that disclosure was itself wrong. Over-correcting a denominator is the same
   defect as under-counting one. The numbers stand.
2. **Phase B collapses** from "widen the ranking to a union read" to recording the finding: the
   registrar provisions a sink with **no writer and no reader**. Real, on fleet's beat, already filed
   (`01M1H2XGV09Y78W9TGVG3G92TH`) — not this plan's work.
3. `scaffold.py:1364` points deployed services at that empty database. Phase A3 must not deepen it.

⚠️ **Every count here is POINT-IN-TIME against a live, growing table** and is stamped `as of
2026-09-02`. Totals moved 9,289 → 9,304 rows during this review alone. An executor RE-DERIVES rather
than asserts; a mismatch against a stamped figure is expected drift, not a defect.

## File Scope (owned paths)

Disjoint; the seven governance files (`check_plan_tickets.py::GOVERNANCE_FILES`) are deliberately
EXCLUDED as shared-append surfaces.

| path | phase | note |
|---|---|---|
| `scripts/kilo-benchmarks/flush_subagent_outboxes.py` | A | new |
| `scripts/kilo-benchmarks/tests/test_flush_subagent_outboxes.py` | A | new |
| `scripts/kilo-benchmarks/daily_refresh.sh` | A | ⚠️ **serialization point** — the pipeline's shared entry script |
| `/opt/trade-intelligence/.env` | A | cross-repo, operator-authorised |
| `src/fabrik/scaffold.py` | A | ⚠️ **synced surface** — correct for all ~46 projects or not at all |
| `scripts/kilo-benchmarks/rank_task_subagents.py` | B, E, G2 | ⚠️ **serialization point** — three phases touch it |
| `scripts/kilo-benchmarks/reclassify_cap_rows.py` | C1 | new, one-off |
| `libs/subagents/pg_ledger.py` · `libs/subagents/agent.py` | D, G1, F | ⚠️ **48 vendored copies** — canonical is `/opt/fabrik-lib/subagents` |

## Constraints Digest

Audited against the `review_rubric.py` run below; every MATCHED pack is named.

| rule | pack:section | implication here |
|---|---|---|
| "Never blindly trust `--autogenerate`. Always review `upgrade()` and `downgrade()`" | `core/25-data-postgres.md` | Phase F's migration is hand-written and reviewed both ways; C1's reclassification ships a dry-run first |
| FKs declare `ON DELETE` explicitly | `core/25-data-postgres.md` | Phase F adds a column only — no FK, no drop, no rename |
| "config via env vars only (`os.getenv`); ZERO secrets/constants in code" | `core/30-ops.md` (12-Factor III) | the walker takes its DSN from the hub env, never a literal |
| logs = stdout only, never a logfile (XI) | `core/55-observability.md` | the walker prints; `_step` captures — it opens no log file |
| a pool dispatch owes `results_table` + `record_agent_run` | `core/62-using-subagents.md` | Execution Discipline below; this review's own fan-out recorded 5 rows |
| fail-open vs fail-closed named on every guard | standing recurrence class | A1 fail-OPEN is deliberate and stated; G2's day-floor is fail-CLOSED (no demotion on thin data) |

```
# REVIEW RUBRIC — inject into EVERY finder prompt (generated by review_rubric.py)
# Honesty (L1): this arms the review — it raises compliance probability, it does not guarantee it.
```
(full 168-line output at the paths in File Scope; MATCHED sections: core/35-security-auth.md, core/25-data-postgres.md, core/30-ops.md, 12-FACTOR (all twelve axes), core/10-python.md, core/62-using-subagents.md)

## Coverage Checklist

| # | class | source | verdict |
|--:|---|---|---|
| 1 | migration reviewed both directions | rubric `25-data-postgres` | **CLEAN** — F adds a column, no drop/rename; C1 is dry-run-first |
| 2 | secrets/DSN never literal in code | rubric `30-ops` | **CLEAN** — walker reads hub env (F7); the plan's own DSN literals were stripped when the gate flagged them |
| 3 | logs to stdout, no logfile | rubric `55-observability` | **CLEAN** — walker prints only |
| 4 | pool dispatch records to the flywheel | rubric `62-using-subagents` | **FIXED** — Execution Discipline added; this review dispatched 5 pool units + 1 native Opus |
| 5 | **fail-open vs fail-closed on every guard** | standing class | **FIXED** — A1 fail-open stated as behaviour incl. the unreachable-sink line (F7); G2 fail-closed under the day-floor |
| 6 | **cost/quota/limit edges (unknown ≠ 0)** | standing class | **FIXED** — G3 forbids raising `max_turns` blindly; C1 no longer treats a caller-set cap as the default cap (F5) |
| 7 | **boundary/sentinel/prefix collisions** | standing class | **FIXED** — the `turns=0 ∧ cost=0` sentinel collided with 1,965 non-capped rows; scoped to `status='capped'` (F4) |
| 8 | **behaviour without a test** | standing class | **CLEAN** — A1 carries a 6-row Given/When/Then contract; every other phase has a runnable gate |
| 9 | bounded search read as a total | this review | **FIXED** — the 1,465→3,487 undercount (F1); the glob is now mandated |
| 10 | count re-derived, not re-cited | this review | **FIXED** — 43→44 DSN (F6), 7→8 repos (F1), point-in-time stamps added |
| 11 | provider-death on an unattended external loop | `58-resilience` | **FIXED** — C2 below |
| 12 | producer with no named consumer | wired-consumer audit | **FIXED** — the walker's consumer `daily_refresh.sh` had **no ranking step at all** (D1); A5 added, so the stall signal's consumer now actually runs |
| 13 | a commit MESSAGE read as the diff | this review | **FIXED** — the cap-removal date was taken from the commit that added the phrase, not the one that removed the code (D5); corrected to 2026-07-19 from `select.py:83` |
| 14 | ledger-derived count applied to a DB population | this review | **FIXED** — C1's "240" is a JSONL count; the DB holds 90 and has no error-text column (D6) |
| 15 | NULL-unsafe predicate | this review | **FIXED** — all 141 stalled rows have `cost_usd IS NULL`, so the literal `cost = 0` matched **zero** rows (D7) |
| 16 | one call where a loop is required | this review | **FIXED** — `flush_outbox` drains `.flushing` OR live, never both; 4 repos hold both (D3) |
| 17 | evidence with an unreconciled delta | this review | **OPEN, named** — 50 returned vs 46 landed (D9); A1 must reconcile per repo before the backlog is trusted |

## Execution Discipline

- **Every phase ends with a full `/fabrik-review` on its changed surface**, run to a
  coverage-adjudicated exit, BEFORE the next phase starts. Progression is gated on it coming back
  clean — not a mention, the full methodology.
- **Pool-default dispatch** (`fanout(task_type, units, repo=…, project=…)` — auto-records to the
  flywheel, then `set_quality` back-fills the verdict) for all gradeable fan-out: the per-repo
  verification in A, the per-model re-benchmark in C2, the consumer enumeration in D. **Native Opus is
  added on top** for the high-risk slices — the D/F vendored-library change and the F migration —
  never as a replacement. Pool-only lands no Opus eyes; native-only lands no flywheel rows.
- **Parallelism:** A1's per-repo verification fans out one unit per repo (8 units, disjoint) and merges
  at the dry-run total. C2 fans out one unit per model (3 units). D's consumer enumeration fans out per
  consumer. Phases A, C and E are independent of each other and may run concurrently; **B, D, F and G1
  are serialized** — they share `rank_task_subagents.py` or the vendored module.
- **The final phase runs `/fabrik-docs-review`** over every doc this plan touches.

## Documentation steps (Doc Sync Matrix triggers this plan fires)

| trigger | doc | phase |
|---|---|---|
| new script / subsystem | `docs/reference/subagent-flywheel.md` (grep first — extend, never a second) + `INDEX.md` row | A |
| scheduled job added | `docs/RESILIENCE.md` §7 (canonical jobs/intervals inventory) | A |
| new env var documented | `.env.example` + `docs/CONFIGURATION.md` | A |
| code changed | `CHANGELOG.md` | every |
| schema migration | `db/schema.sql` + Alembic | F |
| decision made/received | `docs/DECISIONS.md` | B, E, and the CONVERGED flip |
| end of run | `docs/LESSONS_LEARNT.md` | final |

---

## Phase A — Close the stranding class (hub + `.env`; no fleet-synced code)

**Why first:** **3,505 recorded runs** (re-derived 2026-09-02) exist on disk across **8 repos / 14
files** and cannot reach the DB. Every day this waits, more are written into files nothing reads. It
needs no library change.

⚠️ **The first draft said "~1,465 across seven repos" — a 2.4× UNDERCOUNT, and a self-contradicting
one (it listed eight repo names under a "seven" heading).** Cause: the original scan tested only
`$d/.tmp/subagents/pg_outbox.jsonl`, so every crashed-flush `pg_outbox.flushing.jsonl` was invisible
except youtube's, which a separate `find` happened to surface. That is the bounded-search-as-total
class exactly. ⚠️ **AND THE CORRECTION WAS ITSELF BOUNDED — third time in this artefact's lineage.** The re-derived
"3,487 / 12 files" used `-maxdepth 4`, which cannot reach a nested repo: it missed
`/opt/trade-intelligence/web/.tmp/subagents/pg_outbox.jsonl` (4) and
`/opt/fabrik-lib/subagents/.tmp/subagents/pg_outbox.jsonl` (8). The author-blind reviewer's
depth-unbounded glob found them.

**The mandated command has NO `-maxdepth` and matches BOTH filenames:**

```
$ find /opt -path "*/.tmp/subagents/pg_outbox*.jsonl" -exec wc -l {} + | tail -1
   3505 total
```

Three successive counts of the same population — 1,465 → 3,487 → 3,505 — each one a different bound
presented as a total. The walker in A1 must therefore ENUMERATE what it walked and print it, so the
population is never again asserted from a glob someone typed once.

### A1 — Fleet-wide outbox flush walker

New: `scripts/kilo-benchmarks/flush_subagent_outboxes.py`. Walks `/opt/*/.tmp/subagents/` (and
`/opt/*/*/.tmp/subagents/` — `trade-intelligence/web` has its own), calls
`pg_ledger.flush_outbox(outbox_dir=…, reason_sink=…)` per directory, prints one line per repo
(`repo · flushed N · reasons […]`) and a total. Exit 0 always (fail-open — a flusher that reds the
daily refresh is worse than an unflushed row).

**The reason tokens the walker must surface** (the module's own enumerated set, `pg_ledger.py:889-892`):
`dsn-missing` · `outbox-empty` · `setup-failed` · `lock-held` · `claim-failed` · `outbox-unreadable` ·
`all-rows-malformed` · `all-rows-rejected` · `missing-driver-psycopg` · `db-connect-failed` ·
`db-session-lost-before-insert` · `db-commit-uncertain` · `db-failed`. ⚠️ **The module has NO logger by
deliberate convention** — the token travels only through the caller's `reason_sink`, so if the walker
does not print it, nobody ever sees it. Printing the token per repo IS the observability half of A1.

**Where the DSN comes from (was unspecified — pool finder, HIGH).** The walker passes NO `dsn=`; it
relies on `flush_outbox`'s own resolution, which reads `SUBAGENT_RUNS_DSN` from the HUB's environment
(`/opt/fabrik/.env:393` → `postgresql:///fabrik_analytics`, loaded by `_dotenv`). It therefore flushes
every repo's rows into the hub's database regardless of what that repo's own `.env` says — which is
the entire point, and is why A3 is small. **If the hub's DSN is unset or unreachable the walker prints
`SINK UNREACHABLE — 0 flushed, N rows left in place` and still exits 0**; it must never delete or claim
an outbox it could not deliver. State that as a behaviour, not a hope.

- The module was **designed** for this and never wired: *"run from a machine WITH the DSN (the hub, e.g. wired into `daily_refresh.sh` next to the ranking regen)"* (`pg_ledger.py:855-858`).
- **Never delete an outbox file directly** — `flush_outbox` owns the atomic claim + quarantine path (`pg_ledger.py:864-869`, `:300`).

⚠️ **ONE CALL PER DIRECTORY IS NOT ENOUGH — the walker MUST LOOP** (author-blind reviewer D3,
confirmed against `pg_ledger.py:993-1001`). A single `flush_outbox()` processes the `.flushing`
residual **or** the live outbox, never both: *"A batch already pending in `.flushing` … is processed
first and `live` is left to accumulate (claimed next run) — there is NO file-merging."* Four repos
carry BOTH (web-ecommerce-factory 831+114, brand-identiy-creator 754+57, iterative_image_editor
328+60, youtube 87+20), so a one-shot walker recovers the residuals and silently leaves ~250 live rows
for tomorrow — and the A1 Behavior Contract's *"the outbox is gone"* would be FALSE for exactly the
repos this phase exists to rescue. **Loop `flush_outbox` per directory until it returns 0 or reports
`outbox-empty`**, with an iteration cap so a pathological repo cannot spin.

⚠️ **PASS `receipt_dir` (author-blind reviewer D4).** `_flush_locked` writes one receipt per flushed
row via `write_receipt(…, receipt_dir=receipt_dir)`; with `receipt_dir=None`, `ledger._receipts_path`
falls back to `.tmp/subagents` **relative to CWD** — the hub — so flushing seo's 551 rows would append
551 receipts to `/opt/fabrik/.tmp/subagents/receipts.jsonl` and give seo none. Receipts are exactly what
`check_subagent_flywheel.py` reconciles against, i.e. the gate Phase D exists to make meaningful. The
walker passes `receipt_dir=<that repo's .tmp/subagents>`. It is a silent misroute, not an error.

⚠️ **STAMP THE REPO (author-blind reviewer D15).** The walker is the ONLY place that knows a row's true
repo — it holds the directory path — and discarding it makes Phase A actively inflate Phase F's
backfill: web-ecommerce-factory's residual alone carries **81 distinct `project` values**
(`plan1-phaseB-review`, `session-review-r6`, `two-budget-crawl`, …) of which exactly one is the repo
name. Flushing ~3,500 such rows grows F's population by roughly 75%. Record the walked repo at flush
time so A reduces F's work instead of multiplying it.

⚠️ **The append-during-claim window is REAL and this phase activates it daily** (`pg_ledger.py:864-869`,
which this plan already cites for a different purpose): *"an appended write follows the INODE, so it
lands inside the file this flush already read and is unlinked with it … the window is real, narrow and
cross-process, and `_append_outbox` deliberately does not take `pg_outbox.lock`."* `flock` serialises
FLUSHERS against each other; it does not protect against a concurrent `record_run` in a sibling
session. Accepted (the alternative is blocking a live run), but it must be stated where it is switched
on, not left in the module docstring.

## Behavior Contract

- **Given** a repo with a live `pg_outbox.jsonl` and a reachable DSN, **When** the walker runs, **Then** those rows appear in `subagent_runs` and the outbox is gone.
- **Given** a repo holding BOTH a `.flushing` residual and a live `pg_outbox.jsonl`, **When** the walker runs once, **Then** BOTH are drained — the loop, not a single call (D3).
- **Given** any flushed row, **When** its receipt is written, **Then** it lands in that repo's own `.tmp/subagents/receipts.jsonl`, never the hub's (D4).
- **Given** a repo with no `.tmp/subagents` directory, **When** the walker runs, **Then** it is skipped silently and the exit code stays 0.
- **Given** three repos where the second is unreadable, **When** the walker runs, **Then** repos one and three still flush and the failure is named on stdout.
- **Given** a `pg_outbox.flushing.jsonl` left by a crashed flush (youtube's 87 rows), **When** the walker runs, **Then** that residual is recovered and lands.
- **Given** every failure mode forced at once (no DSN, unreadable dir, DB down), **When** the walker runs, **Then** it still exits 0 — a flusher that reds the daily refresh is worse than an unflushed row.
- **Mocked:** nothing. A real throwaway Postgres and real outbox files on disk — a substring assertion on the helper's SQL would stay green if the flush inverted.

**Gate:** `.venv/bin/python -m pytest scripts/kilo-benchmarks/tests/test_flush_subagent_outboxes.py -q`
→ all pass; then `.venv/bin/python scripts/kilo-benchmarks/flush_subagent_outboxes.py --dry-run` →
prints a per-repo table whose total equals

```
$ find /opt -maxdepth 4 -path "*/.tmp/subagents/pg_outbox*.jsonl" -exec wc -l {} + | tail -1
```

⚠️ The glob is `pg_outbox*.jsonl`, matching the live outbox AND any `.flushing.jsonl` residual —
the bare `pg_outbox.jsonl` is what produced this plan's 2.4× undercount. The dry-run counts residuals
too, or the comparison is meaningless (pool finder, MED).

### A2 — Wire it into the daily refresh

⚠️ **SCOPE DISCOVERY (author-blind reviewer, D1 — confirmed): `daily_refresh.sh` HAS NO RANKING STEP.**
An earlier draft ordered this step "before the ranking regen". Enumerated, the file's complete set of
`_step` labels is six:

```
$ grep -n '_step "' scripts/kilo-benchmarks/daily_refresh.sh
143: check_daily_refresh_freshness   151: external_services_chain
244: deliver_to_fabrik               252: generate_capability_index
271: generate_kilo_agents            420: sync_enforcement_to_projects
```

`rank_task_subagents` appears exactly once in 493 lines — **inside a comment** (`:349`). So the ranking
that drives `pick_models` fleet-wide is **not regenerated on any schedule**, which means (a) this step
has nothing to be ordered against, and (b) **Phase E's entire delivery mechanism is void** — "implement
in the gate, not by hand-editing the doc" produces a doc nothing regenerates. `TASK_SUBAGENT_SELECTION.md`
reads `Last refresh: 2026-09-02` only because someone ran it by hand.

**This is larger than the plan and is NOT silently absorbed into A2.** A2 places the flush step after
`check_daily_refresh_freshness` (so a stale-doc warning still fires first) and **A5 is added below** to
wire the ranking regen itself. Add to `scripts/kilo-benchmarks/daily_refresh.sh` using the wrapper:

```bash
_step "flush_subagent_outboxes" "$VENV_PY" "$KB/flush_subagent_outboxes.py" ...
```

**Gate:** `bash -n scripts/kilo-benchmarks/daily_refresh.sh` → clean; `grep -n '_step "' …` shows
`flush_subagent_outboxes` present and positioned after `check_daily_refresh_freshness`.

### A5 — Wire the ranking regen (opened by A2's discovery)

`rank_task_subagents.py` runs on no schedule. Add it as a `_step` **after** `flush_subagent_outboxes`,
so each day's rows land before the ranking reads them. Without A5, every other phase that "changes the
gate" changes a document that is only regenerated by hand.

**Gate:** `grep -n '_step "' scripts/kilo-benchmarks/daily_refresh.sh` shows `flush_subagent_outboxes`
then the ranking step, in that order; a dry-run of the refresh lists both.

### A3 — DSN configuration (cross-repo `.env`, operator-authorised)

- **44 of 48** repos carrying `libs/subagents` have no `SUBAGENT_RUNS_DSN` (re-derived 2026-09-02: exactly FOUR have one — fabrik, iterative_image_editor, trade-intelligence, tryton-crm; an earlier draft said "43 of 48 / 5 have one", counting fabrik-lib, which carries the env line but is not among the 48 vendoring dirs). Add `SUBAGENT_RUNS_DSN=postgresql:///fabrik_analytics` to the dev `.env` of each repo that vendors the module. **Back up first** (`cp .env backups/.env.backup.$(date +%Y%m%d-%H%M%S)`), never touch a `.env` a sibling has open.
- **Repoint trade-intelligence.** Its DSN targets `localhost:54322/trade_intelligence` (a project-local database, credentials elided); that database has **no `subagent_runs` table** (verified — see Evidence). Its 613 outboxed rows can never land as configured.
⚠️ **A3 is deliberately NARROW — only ONE item is required.** A pool finder challenged the 44-repo
DSN write as unargued churn, and it was right: with the A1 walker flushing from the hub, a project's
own DSN buys only *immediacy* (a direct write instead of an outbox hop), not correctness. So:

- **REQUIRED — repoint trade-intelligence** (below): its DSN is actively WRONG, aiming at a database
  with no `subagent_runs` table, which is a real, present defect.
- **OPTIONAL, and explicitly deferred** — adding `SUBAGENT_RUNS_DSN` to the other 43. Rationale if
  ever done: it removes outbox latency so a run is visible to the ranking the same day. Cost: 43
  cross-repo `.env` writes. **The executor does NOT do this as part of Phase A** — it is recorded here
  so the option is not silently lost.

- **Do NOT install psycopg into the 43 project venvs.** It is not needed and it is a deps change requiring authorisation. With the A1 walker in place the projects never talk to Postgres at all: a project with no driver (or no DSN) fail-opens to its local outbox — which is exactly why seo has 551 rows on disk with neither — and the HUB, which has psycopg, flushes them. Adding the driver fleet-wide would buy nothing and widen the change by 43 dependency files.
- Hub `.env.example:393` already carries the correct value; the **scaffolder** template
  (`src/fabrik/scaffold.py`, the commented `# SUBAGENT_RUNS_DSN=postgresql://<writer>…` line — **:1364
  at authoring, :1367 by the end of this review**) ships it pointed at `postgres-main`, which is right
  for deployed services and, per the RESOLVED section above, currently aims at an EMPTY table.
  ⚠️ **`src/fabrik/scaffold.py` is under concurrent edit by another session** (`git status` shows it
  modified, +4/−1, during this review). Grep for the line, never trust the number, and re-check for a
  sibling's WIP before touching it. Add the dev line alongside it, commented with which environment each is for. ⚠️ `scaffold.py` is a synced surface — the edit must be correct for all ~46 projects.

**Gate** (⚠️ the earlier form was `A && B || C`, which fires `C` whenever `A` is false, so every `/opt`
dir *without* `libs/subagents` printed MISSING — 53 lines today, and it could never be empty even after
a perfect A3; author-blind reviewer D11):

```
$ for d in /opt/*/; do if [ -d "$d/libs/subagents" ]; then \
    grep -qs '^SUBAGENT_RUNS_DSN' "$d.env" || echo "MISSING $d"; fi; done
```
→ empty after A3's required item plus whatever optional writes were taken; `psql "$(grep ^SUBAGENT_RUNS_DSN /opt/trade-intelligence/.env | cut -d= -f2-)" -tAc "SELECT 1 FROM subagent_runs LIMIT 1"` → no error.

### A4 — Reply to the open finding

Mail `01M1EWW9G8SSFZX08KFPRQEAM2` (fleet) reports `missing-driver-psycopg`.

⚠️ **An earlier draft of this plan called that reason string "wrong about its own cause" and mailed
that claim to fleet twice. THE CLAIM WAS WRONG — read the emitting code, not the `.env` files.**
`flush_outbox` returns `dsn-missing` at `pg_ledger.py:914` and only reaches `missing-driver-psycopg`
at `:1058`, far below it. The early return means **a `missing-driver-psycopg` token PROVES a DSN was
resolved in that run.** So the reporter's token was accurate and the correction was not.

Both causes are real and they affect different populations:
- **`dsn-missing`** — repos with no `SUBAGENT_RUNS_DSN` in `.env` (44 of 48). Their rows outbox and
  the A1 walker recovers them. No project-side change needed.
- **`missing-driver-psycopg`** — a run where the DSN *did* resolve (real env, or `_dotenv`'s walk-up
  finding a parent `.env` — `_dotenv.py:99-109`) but the interpreter had no psycopg. Also recovered by
  the walker, since the hub has the driver.

A1 fixes both without touching any project. **A4 owes fleet a correction OF MY CORRECTION**, not a
restatement of it.

**Gate:** `python3 scripts/mail.py list --agent intel` no longer shows it unacked, AND the correcting
mail names `pg_ledger.py:914` vs `:1058` as the evidence.

**Gate:** `python3 scripts/mail.py list --agent intel` no longer shows it unacked.

---

## Phase B — Record the provisioned-but-unread sink (one step; the unknown is closed)

B1 is answered above. Remaining work: a `docs/DECISIONS.md` row, plus a comment at
`rank_task_subagents.py:17` stating that reading local-only is DELIBERATE and why, so the next reader
does not re-open it as a bug. The registrar-side defect is fleet's and is filed — **do not fix it here.**

**Gate:** `grep -n "postgres-main" scripts/kilo-benchmarks/rank_task_subagents.py` → shows the comment;
the DECISIONS row exists and cites the measurement above.

## Phase C — Correct the poisoned rows, re-measure the priced-out models (hub-local)

**Not** a status-semantics change fleet-wide — the cause was fixed six weeks ago; what remains is stale data plus three unmeasured models.

### C1 — Reclassify the default-cap rejections (REWRITTEN — the original was unexecutable)

⚠️ **Three defects, all confirmed against primary sources.**

**(a) The cut-off date was wrong — the cap went 2026-07-19, not 07-21.** The earlier date came from
`git log -S"always-on cap is gone"`, which finds the commit that added the *phrase*, not the one that
removed the *enforcement*. `select.py` says so in its own body:

```
$ sed -n '83p' libs/subagents/select.py
# (removed 2026-07-19 per operator: the pool is curated, and per-run task cost is pennies regardless
```

This plan's own Self-audit lesson, recurring one level down: *the commit message is not the diff.*

**(b) The migration cannot select its rows — the cause is not in the database.** `subagent_runs` has
**no error-text column**. The "240" is a **JSONL-ledger** count; the DB holds **90** matching rows
(kimi-k2.5 30, qwen3.7-max 30, glm-5 30, all 2026-07-18) and nothing in them records *why* they failed.
The two populations were never distinguished. Selection is by `(model, ts::date)` against that
enumerated set — never by a text match that cannot exist.

**(c) The post-apply gate could never return 0.** It asserted no `status='error'` rows before the
cut-off; there are **135**, at most 90 of them cap rows. The gate asserts the 90 named rows flipped and
that the three models recompute above 0% success — never a global zero.

Also: `z-ai/glm-5` carries a `status='error'` row on **2026-07-07**, so "every error for all three is
the cap" is false for glm-5 (30 of 31); it holds for kimi-k2.5 and qwen3.7-max.

⚠️ **Do not reclassify on date alone.** `max_cost_per_mtok` is still an OPT-IN caller filter
(`select.py:526`), so a `max price` rejection can also be a caller's deliberate ceiling. The dry-run
lists each candidate with its project/caller; the executor confirms before applying.

**The live residue is 19, not 6 — and it is one model.** Re-derived across ALL repo ledgers (the "6"
scanned only the hub — a bounded search again): **19** post-removal rejections, 2026-08-20 → 08-31,
across 5 repos, **every one `deepseek/deepseek-v4-pro`**. The author-blind reviewer reported 11 across
five models; that did not reproduce at my bound (`/opt/*/.tmp/subagents/*.jsonl` +
`/opt/*/*/.tmp/subagents/*.jsonl` → 19 hits, one model). The COUNT correction stands; the model spread
does not. These are `_apply_max_price`'s same-price ceiling working as designed — **leave them**.

**Gate:** the dry-run lists exactly the 90 DB rows by `(model, ts::date)` and names the ledger-vs-DB
difference explicitly; after apply those 90 carry the non-failure status and the three models recompute
above 0% success. No global-zero assertion.

### C2 — Re-benchmark the three priced-out models

These three were priced out by the default cap. ⚠️ **The claim "never retried after it lifted" is FALSE,
and this plan's own citation refutes it** (author-blind reviewer D14): `loop.py:56-64`, inside the block
cited here as `:40-82`, records *"Proven live 2026-07-19: qwen3.7-max ($3.75), glm-5 ($1.92), kimi-k2.5
($2.025) → 200 bare, 404 at max_price=1.5, 200 at 3×"*. All three WERE retried the day the cap came off.
The narrower true claim — and the one that actually justifies C2 — is that they were never **re-scored
on the mutant corpus** (zero rows for any of them after 2026-07-18). They are *unscored*, not
unmeasured. Re-run them on the existing unchanged 22-mutant corpus, one at a time (the batching-variance
caveat already documented in `TASK_SUBAGENT_SELECTION.md`).

**Provider-death handling (`58-resilience.md` § Provider-death resilience — this is an unattended
loop whose forward progress depends on OpenRouter):** no single point of death — the re-benchmark
iterates models independently, so one dead provider never stalls the sweep; the last rung is
EXERCISED — if a model returns no usable run after 3 attempts it is recorded `unmeasurable` with the
reason text, which is a real terminal state the ranking reads, not a silent skip; and zero-forward-
progress alarms — a sweep that completes with 0 new scored rows prints a loud failure and exits
non-zero, because "ran and measured nothing" is the outcome that otherwise looks like success.

**Gate:** each model has ≥1 non-cap-errored scored run OR a recorded `unmeasurable` verdict with its
reason; the ranking regenerates with them present or with a stated reason for exclusion that is not an
error rate.

### C3 — Tolerate the blank-status rows

2,727 rows dated 2026-07-18 carry `status=''`. Any status-reading aggregation this plan touches must treat blank as *unknown*, never as success or failure.

**Gate:** a test asserting the aggregation's counts are unchanged when 100 blank-status rows are injected.

---

## Phase D — Make the drop loud (fleet-synced; fabrik-lib first)

The failure only surfaces if a caller passes `reason_sink=[]` and inspects it (`pg_ledger.py` signature, `:853`). The fanout banner says nothing, so a dead flywheel is indistinguishable from a working one — which makes `check_subagent_flywheel.py`'s premise unmeetable regardless of agent discipline. Fleet's mail endorses this and it is the right call.

**Route:** edit canonical `/opt/fabrik-lib/subagents` (cross-repo — **needs the operator's explicit approval at that point**), re-vendor to `/opt/fabrik/libs/subagents`, let the sync distribute to 48 copies.
**Steps (the route above is not a step list — pool finder, HIGH):**
1. Operator approval for the cross-repo write to `/opt/fabrik-lib/subagents`.
2. Make the change there; run fabrik-lib's own gate.
3. Re-vendor into `/opt/fabrik/libs/subagents` and assert byte-identity with canonical
   (`diff -r /opt/fabrik-lib/subagents /opt/fabrik/libs/subagents` → empty).
4. Commit on a governance-sync TRIGGER path so the post-commit sync distributes, or run
   `scripts/sync_enforcement_to_projects.py --force`; then spot-verify ≥2 project copies.

**Mirror to name (contract change), as a RUNNABLE gate — "enumerate what breaks" is not one:**

```
$ grep -rn "flush_outbox\|reason_sink" --include=*.py --include=*.sh /opt/*/scripts /opt/*/libs 2>/dev/null | grep -v "/libs/subagents/"
```

Every hit is a consumer to inspect for stdout-format reliance; record the list and the verdict per hit
in the plan before editing.

**Gate:** a dispatch with an unreachable sink prints the drop and the reason at dispatch time; `python scripts/enforcement/check_subagent_flywheel.py` green.

---

## Phase E — Reviewer default (ranking gate, hub-local)

Shift the default reviewer from `deepseek-v4-pro`/`minimax-m3` (68% of dev-half spend — $17.10 of the top four's $25.26) toward `deepseek-v3.2-exp` (565 runs, 90% ok, avg_q 3.25, **0.39¢/run** vs 1.75¢). Implement in the `rank_task_subagents.py` gate, not by hand-editing the doc.

⚠️ **Do not over-claim the quality delta.** `TASK_SUBAGENT_SELECTION.md` states its own instrument ceiling: 15 of 22 mutants are caught by every strong model and 6 by none, so **exactly 1 item discriminates at the frontier**. A 0.15 quality gap on that corpus is inside the noise. The defensible claim is the cost, not the quality.

**Gate:** the regenerated ranking's `review` table shows the new order with `n` and `shrunk_q` per row; a before/after cost projection over the last 30 days' real dispatches is embedded in the plan's Evidence.

---

## Phase F — Project attribution (schema; last, largest)

4,423 of 9,289 rows say `project='review'` — the column holds run labels, not repos. Make `SUBAGENT_PROJECT` the repo name and move the run label to its own column.

**Cost, stated:** a migration on the shared table **plus** a read path that tolerates 48 vendored copies at different vintages writing the old shape. Additive column + backfill + tolerant read; no rename, no drop. `pg_ledger.py:87-95` already documents why `_REQUIRED_OUTBOX_COLS` is validated instead of `_COLS` — an outbox row is written by an *older* copy than the one flushing it. That contract binds this phase.

**Gate:** an old-shape row (no new column) still flushes and still aggregates; `SELECT count(DISTINCT project)` returns repo names; `final_gate.py --json` → `"status":"success"`.

---

## Phase G — `capped` is two unrelated failures sharing one label (hub-local, blocks any model verdict)

**Found by the operator's coverage audit, 2026-09-02** — `capped` and `stall` appeared **zero times**
in this plan's first draft, while 232 capped runs (11% of dev-half spend) sat unexplained. The
operator's instinct was right: *"capped runs make it hard to conclude."* Measured, it is worse than
hard — the label is currently unusable as evidence, because it conflates two failures with opposite
dispositions:

| class | n | cost | avg turns | avg latency | whose fault |
|---|--:|--:|--:|--:|---|
| **provider stalled** — accepted, streamed nothing until the wall clock | 141 (61%) | **$0.00** | 0.0 | 799s | the provider |
| **turn budget exhausted** — ran fine, hit OUR ceiling | 91 (39%) | $3.71 | 14.1 | 146s | our config |

The ceilings actually hit are `max_turns` 8 (25×), 20 (21×), 6 (14×), 24 (8×). A 14-turn average
against an 8-turn ceiling means we are **paying for truncated work** — a budget-setting defect, not a
model defect.

### G1 — Split the label at record time

Record a stall as `stalled` and a budget cut-off as `turn_exhausted` instead of both as `capped`.
Until then no aggregation can tell "the provider died" from "we cut it off", and **no model verdict
built on capped rate is defensible.** ⚠️ This touches the recording path in `libs/subagents` → the
48-copy blast radius of Phase D; it ships **with** D, not separately.

Historical rows are distinguishable without a migration, but **only INSIDE `status='capped'`** — the
predicate is `status='capped' AND (turns = 0 OR turns IS NULL)`. ⚠️ An earlier draft wrote it as a bare
`turns = 0 AND cost = 0 ⇒ stalled`; measured against the real table that also matches **1,746 `scored`,
217 `error` and 2 `done`** rows, so an executor applying it table-wide would misclassify ~1,965 rows.
A pool finder raised the inference as unjustified and the measurement confirmed it.

```
$ psql postgresql:///fabrik_analytics -c "SELECT status, count(*) FROM subagent_runs \
    WHERE (turns IS NULL OR turns=0) AND (cost_usd IS NULL OR cost_usd=0) GROUP BY 1 ORDER BY 2 DESC;"
 scored | 1746
 error  |  217
 capped |  141
 done   |    2
```

**Gate:** a forced stall records `stalled`; a forced turn cut-off records `turn_exhausted`; the
existing `capped` rows still aggregate correctly under the derived rule.

### G2 — Stall rate as a ranking signal, with a denominator floor

The stall rate is the **one** genuine model-side signal inside `capped` — it is provider
availability, not our config. But it is confounded for every model measured only in the sweep:

```
stepfun/step-3.5-flash        33.3%   n=60  over 2 days   ← one bad afternoon is indistinguishable
xiaomi/mimo-v2.5              26.7%   n=60  over 2 days
tencent/hy3-preview           25.4%   n=59  over 2 days
minimax/minimax-m3             7.7%   n=574 over 33 days  ← the only statistically meaningful figure
```

⚠️ **THE "2 DAYS" READING WAS BACKWARDS, AND IT INVERTS THIS DESIGN** (author-blind reviewer D8). The
two days are **2026-07-18 and 2026-09-02 — forty-six days apart**, not one afternoon:

```
 stepfun/step-3.5-flash | 2026-07-18 | 11    tencent/hy3-preview | 2026-07-18 |  2
 stepfun/step-3.5-flash | 2026-09-02 |  9    tencent/hy3-preview | 2026-09-02 | 13
 xiaomi/mimo-v2.5       | 2026-07-18 |  6    xiaomi/mimo-v2.5    | 2026-09-02 | 10
```

A signal **reproduced across two independent incidents six weeks apart** is *stronger* evidence, not
weaker. And a "minimum-distinct-days floor" counts distinct DISPATCH days — it would suppress exactly
this reproduced signal while passing a model swept on ten consecutive days of one outage. **The floor
measures sampling breadth and was being sold as incident independence.**

Replace it with a **distinct-incident** rule: a stall rate routes only when the stalls fall on ≥2
dispatch days **separated by ≥7 days**. That admits the three models above and still rejects a
one-outage artefact. ⚠️ And every rate carries its filter: this table is computed under `status <> ''`,
under which `minimax-m3` gives **6.1% of n=726**, not 7.7% of n=574 — the earlier figure mixed
populations, and Phase E's table says 577 for what should be the same set. A rate without its
denominator is not routed on.

**Gate:** a model with a high stall rate over ≤2 distinct days is displayed with its rate but not
demoted; one over ≥10 days is demoted. Test both directions.

### G3 — Set the turn budgets deliberately

`max_turns` is currently set per-caller with no stated basis (8, 6, 20, 24 all appear). Derive the
ceiling from the observed turn distribution of SUCCESSFUL runs per task type and set it once, with
the number written down. **Do not raise budgets blindly** — that converts a truncation into an
unbounded spend.

**Gate:** the chosen ceiling per task type is recorded with the percentile of successful runs it
covers; a run that exceeds it is `turn_exhausted`, visible, and countable.

### G4 — The provider-stall class is the largest genuine failure mode

141 stalls (capped) + 102 stall-classed errors are, together, the biggest non-config failure class in
the dataset — larger than every transport error combined. It costs $0 but loses the dispatch, and at
799s average it burns 13 minutes of wall clock each time. Out of scope to *fix* here (it is
provider-side), in scope to **measure and route around** via G2.

---

## Evidence

### Phase A — the stranding is real and the route works

```
$ find /opt -maxdepth 4 -path "*/.tmp/subagents/pg_outbox*.jsonl" -exec wc -l {} +   # as of 2026-09-02
   754 /opt/brand-identiy-creator/.tmp/subagents/pg_outbox.flushing.jsonl
    57 /opt/brand-identiy-creator/.tmp/subagents/pg_outbox.jsonl
     5 /opt/fabrik-lib/.tmp/subagents/pg_outbox.jsonl
   328 /opt/iterative_image_editor/.tmp/subagents/pg_outbox.flushing.jsonl
    60 /opt/iterative_image_editor/.tmp/subagents/pg_outbox.jsonl
    67 /opt/job-agent/.tmp/subagents/pg_outbox.jsonl
   551 /opt/seo/.tmp/subagents/pg_outbox.jsonl
   613 /opt/trade-intelligence/.tmp/subagents/pg_outbox.jsonl
   831 /opt/web-ecommerce-factory/.tmp/subagents/pg_outbox.flushing.jsonl
   114 /opt/web-ecommerce-factory/.tmp/subagents/pg_outbox.jsonl
    87 /opt/youtube/.tmp/subagents/pg_outbox.flushing.jsonl
    20 /opt/youtube/.tmp/subagents/pg_outbox.jsonl
  3487 total          ← 12 files, 8 repos
```

The `.flushing.jsonl` residuals are 2,000 of those 3,487 rows — more than half the backlog sits in
crashed-flush files, which is precisely what the first draft's narrow glob could not see.

Nothing flushes them on a schedule:

```
$ crontab -l | grep -iE "flush|outbox|flywheel"
(no cron entry)
$ grep -rln "flush_outbox" scripts/ *.sh
(no match)
```

⚠️ **The reported total spend was a SUBSET presented as a total.** `$37.04` excludes the 2,727
blank-status rows of 2026-07-18, which carry ~$4.8 of real cost. Measured now: **all rows $42.07**,
the `$37.04` basis (excluding blank + scored) **$37.26**. Both are legitimate figures; only one was
labelled. Any spend statement names its filter.

The route itself is healthy — flushed by hand this session:

```
$ .venv/bin/python -c "from subagents import pg_ledger; r=[]; print(pg_ledger.flush_outbox(reason_sink=r), r)"
hub flush -> 50 reasons: []
$ psql postgresql:///fabrik_analytics -tAc "SELECT count(*) FROM subagent_runs"
9289          # was 9243 before the flush
```

⚠️ **That is a 46-row delta against a returned 50, and the gap is UNEXPLAINED** (author-blind reviewer
D9). `flush_outbox` returns `len(good)` post-commit and appends `partial-N-quarantined` to the sink when
rows are dropped — the sink was empty, and the hub has no `pg_outbox.quarantine.jsonl` or
`.corrupt.jsonl`. So four rows are unaccounted for in the very mechanism Phase A is about to run across
~3,500 rows. **A1 carries a reconciliation step: assert `rows_after − rows_before == returned`, per
repo, and fail loudly when it does not.** Until that is understood, the walker is not trusted with the
backlog.

trade-intelligence's configured DSN cannot accept rows (`.env` grounding at `/opt/trade-intelligence/.env`):

```
$ psql "<trade-intelligence SUBAGENT_RUNS_DSN — localhost:54322/trade_intelligence>" \
    -tAc "SELECT count(*) FROM subagent_runs;"
ERROR:  relation "subagent_runs" does not exist
```

### Phase B — the two databases

`src/fabrik/orchestrator/infrastructure.py:748-755` injects the postgres-main DSN unconditionally; `scripts/kilo-benchmarks/rank_task_subagents.py:17` reads local only:

```
17:  1. Queries `fabrik_analytics.subagent_runs` on local postgres via `sudo -u postgres psql`
43: DB_NAME = "fabrik_analytics"
```

### Phase C — the cap was ours, and it was already fixed

```
max_price rejections by DATE:
  2026-07-18: 240
  2026-08-26: 2
  2026-08-27: 2
  2026-08-28: 2
total: 246
$ git log -1 --format='%h %ad %s' --date=short -S"always-on cap is gone" -- libs/subagents/select.py
504af55f 2026-07-21 feat(kilo): claude -p first-class scoring — CONVERGED plan + pool pricing groundwork
```

Per-model attribution — every error for all three is the cap:

```
moonshotai/kimi-k2.5:   90  OUR max_price cap
z-ai/glm-5:             90  OUR max_price cap
qwen/qwen3.7-max:       60  OUR max_price cap
```

The six survivors are one model, the live same-price ceiling (`loop.py:40-82`):

```
2026-08-26  deepseek/deepseek-v4-pro  HTTP 404: No endpoints found that satisfy the max price...
2026-08-27  deepseek/deepseek-v4-pro  ...
2026-08-28  deepseek/deepseek-v4-pro  ...
```

### Phase E — the cost case (dev half; bound stated)

```
$ psql postgresql:///fabrik_analytics   # re-derived during review, as of 2026-09-02 late
               model               |  n  | ok% | avg_q | ¢/run | total $
 deepseek/deepseek-v3.2-exp        | 566 |  90 |  3.25 |  0.39 |   2.155
 deepseek/deepseek-v4-pro          | 553 |  88 |  3.33 |  1.75 |   8.867
 minimax/minimax-m3                | 578 |  85 |  3.35 |  1.59 |   8.308
```

⚠️ These moved during the review (`n` +1 each; `avg_q` for v4-pro 3.39→3.33 and m3 3.41→3.35) because
this review's OWN pool dispatch scored five rows into the same table. That is the point-in-time drift
the header warns about — and it makes Phase E's case *stronger*, not weaker: the quality gap between
the cheapest and the dearest workhorse narrowed from 0.14 to **0.08**, which is further inside the
corpus's stated resolution floor. Re-derive at execution; do not copy these.

### Phase F — the attribution is unusable today

```
$ psql postgresql:///fabrik_analytics -c "SELECT project, count(*) FROM subagent_runs GROUP BY 1 ORDER BY 2 DESC LIMIT 4;"
 review   | 4435          # 4423 at authoring; live table, re-derive at execution
 backfill | 1092
 transdoc |  320
 spec-review | 220
```

## Self-audit

- **Every phase has a runnable gate**, and none of them is a `fabrik …` shell-out (hub-side CLI; these all run from the hub anyway, but the gates are inspection- or pytest-based regardless).
- **Blast radius is stated per phase**, and the two phases that touch the 48-copy vendored surface (D, F) are last, not first. Phases A, C and E were deliberately re-scoped to avoid it — C in particular shrank from a fleet-wide status-semantics change to a hub-local data migration once the cap's removal date was read rather than assumed.
- **One blocking unknown is named and gated** (postgres-main), rather than deferred into execution as an `[OPEN]` residual. Phase B cannot proceed past B1 without it.
- **A denominator error was disclosed, then the disclosure ITSELF proved wrong, and both are recorded.**
  The `$37.04 / 4,821 runs` figures were first stated as totals, then re-disclosed as "the dev-time half"
  when the postgres-main sink was found — and measurement then showed that sink EMPTY, making the
  original figures correct after all. Over-correcting a denominator is the same defect as under-counting
  one; the fix for both is to measure, not to hedge.
- **The `max_price` finding reversed on inspection.** The first reading — "246 errors poisoning the rankings, change the status semantics" — was wrong in emphasis: 240 predate a fix already shipped on 2026-07-21. An error *rate* was again nearly used as a disposition; the error *text* and its date settled it. Three models move from "bad" to "unmeasured".
- **The author-blind pass found what the author could not, and that is the finding.** An independent
  Opus reviewer returned 15 defects against a plan its author had already taken through four passes.
  Five were severe and none were reachable by re-reading: **A2 ordered a step against a ranking step
  that does not exist** (D1 — and its absence voids Phase E's whole delivery mechanism), **the walker
  cannot satisfy its own Behavior Contract** because `flush_outbox` drains one file per call (D3),
  **receipts would be misfiled into the hub** (D4), **C1's migration cannot select its rows** because
  the DB has no error-text column (D6), and **G1's predicate matched zero rows** because `cost_usd` is
  NULL, not 0 (D7). The author's own four passes had found real defects too — but every one of them was
  a *number* or a *citation*, and none was a *mechanism*. That asymmetry is the argument for the
  author-blind pass being mandatory rather than advisory.
- **Not everything the finder reported survived.** Its D13 claimed 11 post-removal cap rejections across
  five models; re-derived across all repo ledgers the count is 19 and every one is `deepseek-v4-pro`.
  The count correction was right, the model spread was not — recorded in C1 with both bounds stated.
- **The same bounded-search defect fired three times on one number.** 1,465 → 3,487 → 3,505, each a
  different glob presented as a total. Fixing a bounded search with another bounded search is the trap;
  the plan now mandates the depth-unbounded command and makes the walker enumerate what it walked.
- **Known weakness:** Phase E's quality claim rests on a corpus whose own documentation says only 1 of 22 items discriminates at the frontier. The plan therefore argues cost, not quality, and says so in the phase.
- **Two gaps were found by the operator's coverage audit, not by me** (2026-09-02): `capped` and
  `stall` appeared zero times in the first draft, leaving 232 runs and 11% of spend unaccounted for.
  Phase G now covers them. The lesson is that this plan's own diagnosis listed capped runs as "a
  budget-setting problem" and then failed to carry that item into a phase — a finding stated in prose
  and dropped on the way to the plan is a finding lost.
- **Not covered:** the task-type skew (review 8,465 of 9,289 rows; code 53, plan 40, spec 9 — the published `spec` ranking is one model on six runs). Real, out of scope here, belongs in `docs/STRATEGIC_BACKLOG.md`.
