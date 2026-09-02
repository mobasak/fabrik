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
- **`pg_ledger` is FAIL-OPEN by contract** — a DB error must never break a run (`libs/subagents/pg_ledger.py:19-21`). No phase may introduce a raise on the recording path.
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
| `scripts/fabrik_synced_manifest.py` | `VENDORED_DIRS = ["libs/subagents"]` → the 48-copy blast radius | `:115` |
| `scripts/kilo-benchmarks/daily_refresh.sh` | the `_step "<label>" <cmd>` wrapper is the only sanctioned way to add a scheduled step (per-step timing + logging) | `:129`, examples `:143`, `:151`, `:420` |
| `src/fabrik/orchestrator/infrastructure.py` | `fabrik apply` **unconditionally** injects a `postgres-main:5432/fabrik_analytics` DSN + a per-project `<id>_subagent_ins` writer role into every deployed project | `:734-755` |
| `scripts/kilo-benchmarks/rank_task_subagents.py` | the ranking reads **local** postgres only — `"Queries fabrik_analytics.subagent_runs on local postgres via sudo -u postgres psql"` | `:17`, `DB_NAME` at `:43` |
| `libs/subagents/select.py` | the always-on price cap is **gone**; only opt-in `max_cost_per_mtok` filters now | `:72`, `:85`, `:526` |
| `libs/subagents/loop.py` | `_apply_max_price` still sets OpenRouter's `provider.max_price` same-price ceiling; caller-set value wins | `:40-82`, kimi case documented at `:65` |
| fabrik-lib | **no new module** — this plan repairs an existing vendored one. No `🆕 fabrik-lib candidate`. | `fabrik-lib/README.md` module table consulted |

## ⚠️ BLOCKING UNKNOWN — resolve before Phase B is trusted

**There may be TWO flywheel databases, and the ranking reads only one.**

`fabrik apply` injects `postgresql://<id>_subagent_ins:<pw>@postgres-main:5432/fabrik_analytics` into every deployed project (`infrastructure.py:748-755`), and `ensure_shared_analytics_db()` applies `SUBAGENT_RUNS_DDL` there. The ranking that drives `pick_models` fleet-wide reads the **local WSL** `fabrik_analytics` (`rank_task_subagents.py:17`). If deployed services have been recording, that half has never influenced routing.

- **Confirmed:** at least one deployed project imports the pool — `/opt/trade-intelligence/src/trade_intelligence/web/_web_tools.py`. **Bound:** grep covered `/opt/*/src` and `/opt/*/app` only; 1 non-hub importer found, repos lacking those directories were not searched.
- **NOT confirmed:** whether `postgres-main`'s `fabrik_analytics.subagent_runs` holds any rows. A probe to `10.99.0.1:5432` from the hub produced no output within 25s (no route, or auth prompt) — **unverified, not empty.**
- **Resolution step (Phase B step 1, blocking):** reach the table over the fleet's own path and `SELECT count(*), min(ts), max(ts), count(DISTINCT project)`. If it holds rows, the ranking's input is incomplete and Phase B widens to a union read. If it is empty, record that as the finding and Phase B collapses to a one-line comment. **Do not proceed past B1 on an assumption either way.**

⚠️ **Consequence for anything already reported:** the figures circulated this session — 9,289 rows / 7,554 runs / 4,821 real dispatches / **$37.04 total spend** — are the **dev-time half only**. They were stated as the whole. Any artefact repeating them must carry that bound until B1 closes.

---

## Phase A — Close the stranding class (hub + `.env`; no fleet-synced code)

**Why first:** ~1,465 recorded runs exist on disk and cannot reach the DB. Every day this waits, more are written into files nothing reads. It needs no library change.

### A1 — Fleet-wide outbox flush walker

New: `scripts/kilo-benchmarks/flush_subagent_outboxes.py`. Walks `/opt/*/.tmp/subagents/` (and `/opt/*/*/.tmp/subagents/` — `trade-intelligence/web` has its own), calls `pg_ledger.flush_outbox(outbox_dir=…, reason_sink=…)` per directory, prints one line per repo (`repo · flushed N · reasons […]`) and a total. Exit 0 always (fail-open — a flusher that reds the daily refresh is worse than an unflushed row).

- The module was **designed** for this and never wired: *"run from a machine WITH the DSN (the hub, e.g. wired into `daily_refresh.sh` next to the ranking regen)"* (`pg_ledger.py:855-858`).
- `flush_outbox` already handles a crashed `.flushing.jsonl` residual, so youtube's 87 stranded rows need no special case.
- **Never delete an outbox file directly** — `flush_outbox` owns the atomic claim + quarantine path (`pg_ledger.py:864-869`, `:300`).

## Behavior Contract

- **Given** a repo with a live `pg_outbox.jsonl` and a reachable DSN, **When** the walker runs, **Then** those rows appear in `subagent_runs` and the outbox is gone.
- **Given** a repo with no `.tmp/subagents` directory, **When** the walker runs, **Then** it is skipped silently and the exit code stays 0.
- **Given** three repos where the second is unreadable, **When** the walker runs, **Then** repos one and three still flush and the failure is named on stdout.
- **Given** a `pg_outbox.flushing.jsonl` left by a crashed flush (youtube's 87 rows), **When** the walker runs, **Then** that residual is recovered and lands.
- **Given** every failure mode forced at once (no DSN, unreadable dir, DB down), **When** the walker runs, **Then** it still exits 0 — a flusher that reds the daily refresh is worse than an unflushed row.
- **Mocked:** nothing. A real throwaway Postgres and real outbox files on disk — a substring assertion on the helper's SQL would stay green if the flush inverted.

**Gate:** `.venv/bin/python -m pytest scripts/kilo-benchmarks/tests/test_flush_subagent_outboxes.py -q` → all pass; then `.venv/bin/python scripts/kilo-benchmarks/flush_subagent_outboxes.py --dry-run` → prints a per-repo table whose total equals `find /opt -path "*/.tmp/subagents/pg_outbox*.jsonl" | xargs wc -l`.

### A2 — Wire it into the daily refresh

Add to `scripts/kilo-benchmarks/daily_refresh.sh`, **before** the ranking regen (rows must land before the ranking reads them), using the existing wrapper:

```bash
_step "flush_subagent_outboxes" "$VENV_PY" "$KB/flush_subagent_outboxes.py" ...
```

**Gate:** `bash -n scripts/kilo-benchmarks/daily_refresh.sh` → clean; `grep -n 'flush_subagent_outboxes' scripts/kilo-benchmarks/daily_refresh.sh` → shows the step ordered before the ranking step; a `--dry-run` invocation of the refresh shows the step in its plan.

### A3 — DSN configuration (cross-repo `.env`, operator-authorised)

- **43 of 48** repos carrying `libs/subagents` have no `SUBAGENT_RUNS_DSN` (measured: 5 have one — fabrik, fabrik-lib, iterative_image_editor, trade-intelligence, tryton-crm). Add `SUBAGENT_RUNS_DSN=postgresql:///fabrik_analytics` to the dev `.env` of each repo that vendors the module. **Back up first** (`cp .env backups/.env.backup.$(date +%Y%m%d-%H%M%S)`), never touch a `.env` a sibling has open.
- **Repoint trade-intelligence.** Its DSN targets `localhost:54322/trade_intelligence` (a project-local database, credentials elided); that database has **no `subagent_runs` table** (verified — see Evidence). Its 613 outboxed rows can never land as configured.
- Hub `.env.example:393` already carries the correct value; the **scaffolder** template (`src/fabrik/scaffold.py:1364`) ships it commented and pointed at `postgres-main`, which is right for deployed services and wrong for WSL dev. Add the dev line alongside it, commented with which environment each is for. ⚠️ `scaffold.py` is a synced surface — the edit must be correct for all ~46 projects.

**Gate:** `for d in /opt/*/; do [ -d "$d/libs/subagents" ] && grep -qs '^SUBAGENT_RUNS_DSN' "$d.env" || echo "MISSING $d"; done` → empty; `psql "$(grep ^SUBAGENT_RUNS_DSN /opt/trade-intelligence/.env | cut -d= -f2-)" -tAc "SELECT 1 FROM subagent_runs LIMIT 1"` → no error.

### A4 — Reply to the open finding

Mail `01M1EWW9G8SSFZX08KFPRQEAM2` (fleet) reports `missing-driver-psycopg` as the cause. The measured cause is **no DSN at all** in 4 of 5 probed repos, which makes `pg_ledger` a documented no-op regardless of driver. Reply with the correction, the fix, and `ack`.

**Gate:** `python3 scripts/mail.py list --agent intel` no longer shows it unacked.

---

## Phase B — Resolve the split-brain (blocking gate B1)

**B1 (blocking):** reach `postgres-main`'s `fabrik_analytics.subagent_runs` and count it. **B2 (conditional on B1):** if it holds rows, make the ranking read both halves — union in `rank_task_subagents.py`, keeping the local DB authoritative for dev rows — and restate every published figure against the combined denominator. If it is empty, record the finding in `docs/DECISIONS.md` and add the comment to `rank_task_subagents.py:17` naming the deliberate scope.

**Gate:** the ranking's own header line states which database(s) it read and the row count from each; `python scripts/enforcement/check_convergence.py` green.

---

## Phase C — Correct the poisoned rows, re-measure the priced-out models (hub-local)

**Not** a status-semantics change fleet-wide — the cause was fixed six weeks ago; what remains is stale data plus three unmeasured models.

### C1 — Reclassify the pre-2026-07-21 cap rejections

240 of 246 `max price` rejections are dated **2026-07-18**, before the always-on cap was removed on **2026-07-21** (`504af55f`). They currently count as model failures and drag three models' success rates to 0–20%. Reclassify those rows to a non-failure status (`skipped`) with a one-off, dry-run-first migration. The 6 survivors (2026-08-26/27/28, all `deepseek-v4-pro`) are the live `_apply_max_price` same-price ceiling working as designed at ~2/day — **leave them**.

**Gate:** dry-run prints exactly 240 candidate rows and their date bound; after apply, `SELECT count(*) FROM subagent_runs WHERE status='error' AND ts::date < '2026-07-21'` → 0 for that cause, and the three models' success rates recompute above 0.

### C2 — Re-benchmark the three priced-out models

`moonshotai/kimi-k2.5`, `z-ai/glm-5` and `qwen/qwen3.7-max` have **100% of their errors from the cap** and were never retried after it lifted. They are *unmeasured*, not bad. Re-run them on the existing unchanged 22-mutant corpus, one at a time (the batching variance caveat already documented in `TASK_SUBAGENT_SELECTION.md`).

**Gate:** each model has ≥1 non-cap-errored scored run; the ranking regenerates with them present or with a stated reason for exclusion that is not an error rate.

### C3 — Tolerate the blank-status rows

2,727 rows dated 2026-07-18 carry `status=''`. Any status-reading aggregation this plan touches must treat blank as *unknown*, never as success or failure.

**Gate:** a test asserting the aggregation's counts are unchanged when 100 blank-status rows are injected.

---

## Phase D — Make the drop loud (fleet-synced; fabrik-lib first)

The failure only surfaces if a caller passes `reason_sink=[]` and inspects it (`pg_ledger.py` signature, `:853`). The fanout banner says nothing, so a dead flywheel is indistinguishable from a working one — which makes `check_subagent_flywheel.py`'s premise unmeetable regardless of agent discipline. Fleet's mail endorses this and it is the right call.

**Route:** edit canonical `/opt/fabrik-lib/subagents` (cross-repo — **needs the operator's explicit approval at that point**), re-vendor to `/opt/fabrik/libs/subagents`, let the sync distribute to 48 copies.
**Mirror to name (contract change):** a new banner line changes stdout that other tools may parse; the reason strings become a public surface. Enumerate what breaks before editing.

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

## Evidence

### Phase A — the stranding is real and the route works

```
$ for d in /opt/*/; do f="$d.tmp/subagents/pg_outbox.jsonl"; [ -f "$f" ] && echo "$(wc -l < "$f") $f"; done
57 /opt/brand-identiy-creator/.tmp/subagents/pg_outbox.jsonl
50 /opt/fabrik/.tmp/subagents/pg_outbox.jsonl
5 /opt/fabrik-lib/.tmp/subagents/pg_outbox.jsonl
60 /opt/iterative_image_editor/.tmp/subagents/pg_outbox.jsonl
67 /opt/job-agent/.tmp/subagents/pg_outbox.jsonl
551 /opt/seo/.tmp/subagents/pg_outbox.jsonl
613 /opt/trade-intelligence/.tmp/subagents/pg_outbox.jsonl
112 /opt/web-ecommerce-factory/.tmp/subagents/pg_outbox.jsonl
87 /opt/youtube/.tmp/subagents/pg_outbox.flushing.jsonl   ← crashed mid-flush
```

Nothing flushes them on a schedule:

```
$ crontab -l | grep -iE "flush|outbox|flywheel"
(no cron entry)
$ grep -rln "flush_outbox" scripts/ *.sh
(no match)
```

The route itself is healthy — flushed by hand this session:

```
$ .venv/bin/python -c "from subagents import pg_ledger; r=[]; print(pg_ledger.flush_outbox(reason_sink=r), r)"
hub flush -> 50 reasons: []
$ psql postgresql:///fabrik_analytics -tAc "SELECT count(*) FROM subagent_runs"
9289          # was 9243 before the flush
```

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
               model               |  n  | ok% | avg_q | ¢/run | total $
 deepseek/deepseek-v3.2-exp        | 565 |  90 |  3.25 |  0.39 |   2.152
 deepseek/deepseek-v4-pro          | 552 |  88 |  3.39 |  1.75 |   8.867
 minimax/minimax-m3                | 577 |  85 |  3.41 |  1.57 |   8.228
```

### Phase F — the attribution is unusable today

```
$ psql postgresql:///fabrik_analytics -c "SELECT project, count(*) FROM subagent_runs GROUP BY 1 ORDER BY 2 DESC LIMIT 4;"
 review   | 4423
 backfill | 1092
 transdoc |  320
 spec-review | 220
```

## Self-audit

- **Every phase has a runnable gate**, and none of them is a `fabrik …` shell-out (hub-side CLI; these all run from the hub anyway, but the gates are inspection- or pytest-based regardless).
- **Blast radius is stated per phase**, and the two phases that touch the 48-copy vendored surface (D, F) are last, not first. Phases A, C and E were deliberately re-scoped to avoid it — C in particular shrank from a fleet-wide status-semantics change to a hub-local data migration once the cap's removal date was read rather than assumed.
- **One blocking unknown is named and gated** (postgres-main), rather than deferred into execution as an `[OPEN]` residual. Phase B cannot proceed past B1 without it.
- **A denominator error in my own prior reporting is disclosed** rather than quietly corrected: the `$37.04 / 4,821 runs` figures are the dev-time half and were stated as the whole.
- **The `max_price` finding reversed on inspection.** The first reading — "246 errors poisoning the rankings, change the status semantics" — was wrong in emphasis: 240 predate a fix already shipped on 2026-07-21. An error *rate* was again nearly used as a disposition; the error *text* and its date settled it. Three models move from "bad" to "unmeasured".
- **Known weakness:** Phase E's quality claim rests on a corpus whose own documentation says only 1 of 22 items discriminates at the frontier. The plan therefore argues cost, not quality, and says so in the phase.
- **Not covered:** the task-type skew (review 8,465 of 9,289 rows; code 53, plan 40, spec 9 — the published `spec` ranking is one model on six runs). Real, out of scope here, belongs in `docs/STRATEGIC_BACKLOG.md`.
