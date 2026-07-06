---
auto_execution_mode: 0
description: End-to-end workflow for the fleet-wide subagent-runs model-selection flywheel — vendor, wire, write, aggregate, consume, verify.
---

# Subagent-Runs Flywheel — Operator Workflow

Wire a Fabrik project into the fleet-wide model-selection flywheel: every subagent run writes one row to a shared Postgres table on `postgres-main`, a nightly aggregator ranks models per task type, and future `pick_models()` calls in every project pick the empirically best model instead of a hardcoded default. Zero regression until you complete the wiring — the module runs on JSONL + a vendored `_TABLE` default indefinitely if you never set the env vars.

**Canonical references:**

- Design spec: [docs/superpowers/specs/2026-07-06-subagent-runs-telemetry-design.md](../../docs/superpowers/specs/2026-07-06-subagent-runs-telemetry-design.md)
- Implementation plan (archived): [docs/development/plans/archived/2026-07-06-plan-1-subagent-runs-lean.md](../../docs/development/plans/archived/2026-07-06-plan-1-subagent-runs-lean.md)
- Module: [`/opt/fabrik-lib/subagents/`](../../../fabrik-lib/subagents/) — README + `subagents/pg_ledger.py` + `subagents/select.py`
- Upstream feedback log: `/opt/fabrik-lib/subagents/UPSTREAM_FEEDBACK.md`
- Aggregator: [`scripts/kilo-benchmarks/rank_task_subagents.py`](../../scripts/kilo-benchmarks/rank_task_subagents.py)
- Emitted doc: [`docs/reference/kilo/TASK_SUBAGENT_SELECTION.md`](../../docs/reference/kilo/TASK_SUBAGENT_SELECTION.md)
- Driver: [`src/fabrik/drivers/postgres.py:create_subagent_ins_role`](../../src/fabrik/drivers/postgres.py) + [`src/fabrik/orchestrator/infrastructure.py:_provision_postgres`](../../src/fabrik/orchestrator/infrastructure.py)

## Architecture (the whole loop in one picture)

```
┌───────────────────────────┐    each run_agents() call        ┌──────────────────────────┐
│ project X                 │  ──────────────────────────►     │ postgres-main            │
│  (vendored subagents lib) │   record_run(project=X,          │ fabrik_analytics         │
│                           │       agent_id, task_type,       │  subagent_runs           │
│  from subagents import    │       model, provider, status,   │  (13 cols, 2 indexes)    │
│      run_agents,          │       cost_usd, turns,           │                          │
│      pick_models          │       latency_s, quality_score,  │  1 row per invocation    │
│                           │       tool_calls)                │                          │
│  pick_models("code") ────┐│                                  └──────────┬───────────────┘
└───────────────────────────┘                                             │ nightly (daily_refresh.sh)
                           │                                              ▼
                           │                    ┌───────────────────────────────────────────────┐
                           │                    │ /opt/fabrik/scripts/kilo-benchmarks/          │
                           │                    │  rank_task_subagents.py                       │
                           │        reads       │                                                │
                           │   ┌────────────────┤   SELECT task_type, model,                    │
                           │   │                │       COUNT(*), AVG(cost), AVG(quality),      │
                           │   │                │       SUM(CASE WHEN status='done' …)/COUNT(*) │
                           │   │                │   FROM subagent_runs                          │
                           │   │                │   WHERE ts > NOW() - INTERVAL '90 days'       │
                           │   │                │   GROUP BY task_type, model                   │
                           │   │                │   HAVING COUNT(*) >= 3                        │
                           │   │                │                                                │
                           │   │                │   value = success × quality / max(cost, 1e-9) │
                           │   │                └───────────────────────┬───────────────────────┘
                           │   │                                        │
                           │   │                                        ▼
                           │   ▼                    ┌───────────────────────────────────────┐
                           │  docs/reference/kilo/  │  Last refresh: 2026-07-06             │
                           │  TASK_SUBAGENT_        │  ### spec (n_total=127)               │
                           │   SELECTION.md         │  | rank | model | value | … |         │
                           │                        │  | 1 | z-ai/glm-5 | 4.82 | … |        │
                           │                        │  | 2 | minimax/… | 4.21 | … |         │
                           │                        │  ### plan (n_total=203)               │
                           │                        │  …                                     │
                           │                        └───────────────────────┬───────────────┘
                           │                                                │ governance-sync
                           │                                                │ (/opt/fabrik → every project's docs/)
                           │                                                ▼
                           │        ┌───────────────────────────────────────────────────────┐
                           └─────── │ vendored subagents.pick_models() at each project      │
                                    │  parses ### <task_type> sections → dict               │
                                    │  returns best-first list respecting cost ceiling +    │
                                    │  exclude set + quality/value preference               │
                                    │  Fallback to _TABLE default if file missing / stale   │
                                    │  (>14 days) / no ### sections                         │
                                    └───────────────────────────────────────────────────────┘
```

## Prerequisites

- [ ] Hub at `/opt/fabrik` on latest master (commit ≥ `07961166` — this is where the driver + orchestrator changes live)
- [ ] Postgres running:
  - WSL dev: local postgres accepting `sudo -n -u postgres psql` (peer auth on unix socket)
  - VPS: `postgres-main` container reachable via `fabrik apply`'s SSH
- [ ] `fabrik_analytics` DB exists with `subagent_runs` table + `subagent_runs_id_seq`
  - WSL dev: `bash /opt/fabrik/scripts/kilo-benchmarks/apply_subagent_runs_ddl.sh` (idempotent)
  - VPS: applied automatically by `ensure_shared_analytics_db()` during `fabrik apply` (**deferred: extend that function to apply `SUBAGENT_RUNS_DDL` alongside `cost_ledger` — currently WSL-only**)
- [ ] `OPENROUTER_API_KEY` set in the project's environment (this is the ONLY env var the module strictly needs to function — everything else auto-degrades)

---

## Part A — Vendor the module into a project

Do this per-project, once, on the WSL dev machine. Not every project needs it — only projects that spawn subagents.

### Step 1. Copy the module

```bash
# From the project root:
cp -r /opt/fabrik-lib/subagents ./libs/subagents
```

### Step 2. Fix internal imports

Vendored fabrik-lib modules follow the convention `libs/<name>/`. The module's own internal imports use `from subagents import ...`. Rewrite them to `from libs.subagents import ...`:

```bash
# Optional grep to see what needs rewriting (usually zero — the module is stdlib-clean):
grep -rn "^from subagents" libs/subagents/subagents/*.py
```

If nothing shows up, the module is import-clean and you skip this step. Otherwise, rewrite the offending imports.

### Step 3. Verify import works

```bash
cd <project root>
python -c "from libs.subagents.subagents import run_agents, pick_models, record_run, SUBAGENT_RUNS_DDL; print('vendored OK:', run_agents.__name__, pick_models.__name__)"
```

Expected: `vendored OK: run_agents pick_models`.

### Step 4. Ensure requirements

The module lazy-imports `psycopg[binary]>=3.1` — needed ONLY when `SUBAGENT_RUNS_DSN` is set. Add to the project's `requirements.txt` (or leave the module in JSONL-only mode by not installing it):

```
psycopg[binary]>=3.1
```

---

## Part B — Wire the env vars (dev vs. VPS deploy)

Three env vars close the flywheel. The module has independent fallbacks for each — unset any one and the module gracefully degrades. The full list:

| Env var | Purpose | Set for | Unset behavior |
|---|---|---|---|
| `OPENROUTER_API_KEY` | Auth for OpenRouter (used by `run_agents`) | Always | `run_agents` cannot dispatch — hard fail (module raises) |
| `SUBAGENT_RUNS_DSN` | Postgres DSN for writing runs | Fleet-wide | JSONL-only sink (no fleet flywheel; per-project only) |
| `SUBAGENT_PROJECT` | Project id tagging every row | Fleet-wide | Rows tagged `"unknown"` |
| `SUBAGENT_SELECTION_DOC` | Path to the ranked doc for `pick_models` | Fleet-wide | `pick_models` uses vendored `_TABLE` hardcoded default |

### For VPS deploy (via `fabrik apply`) — automatic

The `_provision_postgres` block in the orchestrator (`src/fabrik/orchestrator/infrastructure.py`) invokes `create_subagent_ins_role(<project>)` and injects all 3 env vars via `deployer.inject_env(ctx, {…})` after the watchdog roles block. **No manual step required.** Just run `fabrik apply` and check the resource summary:

// turbo

```bash
fabrik apply /opt/fabrik/specs/services/<project>.yaml --dry-run 2>&1 | grep -E "subagent-ins-role|SUBAGENT_"
```

Expected output: `subagent-ins-role: <project> → dry_run` (or `provisioned` on real apply).

The DSN written into the project's `.env` looks like:
```
SUBAGENT_RUNS_DSN=postgresql://<project>_subagent_ins:<32-char-CSPRNG-pw>@postgres-main:5432/fabrik_analytics
SUBAGENT_PROJECT=<project>
SUBAGENT_SELECTION_DOC=docs/reference/kilo/TASK_SUBAGENT_SELECTION.md
```

**Password lifecycle** (mirrors `WATCHDOG_DB_URL_RW` discipline):

- Fresh role → CSPRNG password generated + DSN injected (overwrites any prior value in `.env`).
- Existing role on re-apply → password NOT rotated, DSN NOT re-injected. The prior `.env` value survives, so a running project with a cached image build (Compose does not recreate the container to pick up a new `.env`) never breaks.

### For WSL dev — manual

WSL dev projects don't go through `fabrik apply`, so the env inject rail doesn't fire. Two options:

**Option 1 — Peer auth via unix socket** (simplest for personal dev, no password):

```bash
# In <project>/.env.local:
OPENROUTER_API_KEY=sk-or-v1-...
SUBAGENT_RUNS_DSN=postgresql://postgres@localhost:5432/fabrik_analytics?host=/var/run/postgresql
SUBAGENT_PROJECT=<project-id-string>
SUBAGENT_SELECTION_DOC=docs/reference/kilo/TASK_SUBAGENT_SELECTION.md
```

The `?host=/var/run/postgresql` forces the client to use the unix socket, which triggers `peer` auth (from `/etc/postgresql/*/main/pg_hba.conf: local all postgres peer`) — no password needed. Verify with:

```bash
python -c "import psycopg; c = psycopg.connect('postgresql://postgres@localhost:5432/fabrik_analytics?host=/var/run/postgresql'); print('OK:', c.info.dbname)"
```

**Option 2 — Superuser password via TCP** (matches VPS behavior but requires setting a password once):

```bash
# One-time on WSL:
sudo -u postgres psql -c "ALTER ROLE postgres PASSWORD '<your-dev-password>'"
```

Then in `.env.local`:

```
SUBAGENT_RUNS_DSN=postgresql://postgres:<your-dev-password>@localhost:5432/fabrik_analytics
```

**Option 3 — Mint a per-project INSERT-only role locally** (matches VPS exactly):

```bash
# One-time:
cd /opt/fabrik && python -c "
from fabrik.drivers import postgres as pg
# NOTE: this uses _run_sql which SSHes to VPS by default. For LOCAL WSL, apply the
# same SQL manually via sudo -u postgres psql — see the section 'Local role setup' below.
"
```

The cleanest lean answer: **use Option 1 (unix socket peer auth)** in WSL. It's password-free, matches the security discipline of the module (no shared secret), and requires zero postgres config changes.

---

## Part C — Write agent code that uses the flywheel

### The write path — `run_agents`

Every call to `run_agents([AgentSpec, …])` records one row per agent to the ledger (JSONL always; Postgres too when `SUBAGENT_RUNS_DSN` is set — fail-open, never blocks the run).

```python
from libs.subagents.subagents import run_agents, AgentSpec

results = run_agents(
    [
        AgentSpec(
            task="Write a test for the retry path in http_client.py",
            model="anthropic/claude-sonnet-5",
            task_type="code",       # ← required for the flywheel to categorize
            owned_paths=["tests/*.py"],
            max_turns=8,
            max_cost_usd=0.50,
        ),
    ],
    repo="/opt/<project>",
)

for r in results:
    print(r.agent_id, r.status, r.cost_usd, r.diff)
```

`task_type` must be one of `TaskKind`: `"spec"`, `"plan"`, `"code"`, `"review"`, `"docs"`, `"research"`. Rows with an unknown task_type still get written but won't be aggregated (the SQL groups per known `task_type`).

### The read path — `pick_models`

Before dispatching, ask `pick_models` for the best-ranked candidate:

```python
from libs.subagents.subagents import pick_models

# Simplest form — return the top-1 model for this task type
models = pick_models("code", n=1)
best_model = models[0]

# With a cost ceiling — drops models over $2/M output tokens
models = pick_models("code", n=3, max_cost_per_mtok=2.0, prefer="value")

# Excluding one that failed earlier in this session
models = pick_models("code", n=1, exclude=("anthropic/claude-opus-4.8",))
```

The `prefer="value"` mode re-ranks by `rank_weight / price` — a slightly-worse but much-cheaper model can beat a top-tier one on that axis. Default `prefer="quality"` uses the doc's rank order (best-first).

### Manual `record_run` (for orchestrator-scored quality)

The module's automatic `run_agents` path writes `quality_score=NULL` because it has no way to know how good the agent's output was. If you have an orchestrator that can score outcomes (e.g. "did the test pass? did the PR get approved?"), call `record_run` directly:

```python
from libs.subagents.subagents import record_run

record_run(
    agent_id="agent-42",
    task_type="review",
    model="z-ai/glm-5",
    provider="openrouter",
    status="done",
    cost_usd=0.31,
    turns=5,
    latency_s=42.1,
    quality_score=0.87,    # ← YOUR scoring — 0..2 conventionally
    tool_calls=None,
)
```

Rows with a real `quality_score` sharpen the ranking. Rows without (`NULL`) fall back to `success_rate / cost` in the aggregator (neutral quality = 1.0).

---

## Part D — Verify writes are landing

After running `run_agents` a few times with the env vars set, confirm rows arrived:

```bash
# From the hub:
sudo -n -u postgres psql -d fabrik_analytics -c "
SELECT project, task_type, model, status, cost_usd, quality_score, ts
FROM subagent_runs
ORDER BY ts DESC
LIMIT 10;
"
```

If the table is empty:

```bash
# Check the module's JSONL fallback — every run always writes there:
tail -5 ~/.local/state/subagents/ledger.jsonl 2>/dev/null || \
tail -5 /tmp/subagents-ledger.jsonl 2>/dev/null || \
find / -name "ledger.jsonl" 2>/dev/null | head
```

If JSONL has rows but Postgres doesn't → the DSN isn't reaching the module. Check:

```bash
# Verify env var is visible to the process running run_agents:
env | grep -E "^SUBAGENT_"

# Verify the DSN actually connects:
python -c "
import os, psycopg
dsn = os.environ['SUBAGENT_RUNS_DSN']
c = psycopg.connect(dsn)
print('connected OK to:', c.info.dbname, 'as:', c.info.user)
"
```

Common issues:

| Symptom | Cause | Fix |
|---|---|---|
| `password authentication failed` | scram-sha-256 requires password on TCP | Use Option 1 (unix socket) or Option 2 (set superuser password) in Part B |
| `permission denied for table subagent_runs` | Role has CONNECT but not INSERT | Re-run `create_subagent_ins_role(<project>)` |
| `permission denied for sequence subagent_runs_id_seq` | Missed sequence USAGE grant | Same fix — the function grants both |
| `role "…_subagent_ins" does not exist` | `fabrik apply` didn't run against this project | Run `fabrik apply <spec>` |
| DB rows count doesn't grow | `SUBAGENT_RUNS_DSN` unset in the actual runtime env | Check the Docker container's env, not just the `.env.local` on host |

---

## Part E — Watch the nightly aggregation

`daily_refresh.sh` runs the aggregator between steps 8 (`rank_coding_subagents`) and 9 (`export_models_browser`):

```bash
# Manual invocation:
python /opt/fabrik/scripts/kilo-benchmarks/rank_task_subagents.py

# Expected output:
# wrote /opt/fabrik/docs/reference/kilo/TASK_SUBAGENT_SELECTION.md (state=ok, N rows aggregated)
```

`state="ok"` = query ran cleanly (rows may be 0 if not enough data yet). `state="error"` = subprocess/psql failed, distinct stub emitted, main() exits 1 so `daily_refresh.sh`'s `|| echo "failed"` catches it.

### Read the emitted doc

```bash
head -30 /opt/fabrik/docs/reference/kilo/TASK_SUBAGENT_SELECTION.md
```

- **Fresh install (no data yet)**: shows the "No aggregated runs yet" stub. `pick_models` uses the vendored `_TABLE` default.
- **After some fleet activity**: sections per task type, best-first per `value = success × quality / max(cost, 1e-9)`.

### Governance sync

The file lives under `docs/reference/kilo/` which is fabrik-synced (`scripts/fabrik_synced_manifest.py:69`). It propagates to every project's `docs/reference/kilo/TASK_SUBAGENT_SELECTION.md` on the next governance-sync pass. Projects don't need to fetch it — they just read from their local copy.

### The 14-day staleness gate

The vendored `pick_models` (per the fabrik-lib AI's implementation at `select.py:84` — `load_task_ranking(path, *, min_n=0, max_age_days=None)` with `max_age_days=14` in `_synced_ranking()`) automatically ignores the doc if `Last refresh:` is more than 14 days old — falls back to `_TABLE`. So if `daily_refresh.sh` silently stops running for 3 weeks, `pick_models` reverts to the vendored default instead of serving a months-old ranking.

---

## Part F — Reference tables

### Database schema — `fabrik_analytics.subagent_runs`

Applied by `apply_subagent_runs_ddl.sh` (WSL) or `ensure_shared_analytics_db()` on VPS. Source of truth: `python -c "from subagents import SUBAGENT_RUNS_DDL; print(SUBAGENT_RUNS_DDL)"`.

```sql
CREATE TABLE IF NOT EXISTS subagent_runs (
    id            BIGSERIAL PRIMARY KEY,
    ts            TIMESTAMPTZ NOT NULL DEFAULT now(),
    project       TEXT NOT NULL,
    agent_id      TEXT NOT NULL,
    task_type     TEXT NOT NULL,
    model         TEXT NOT NULL,
    provider      TEXT,
    status        TEXT NOT NULL,
    cost_usd      DOUBLE PRECISION,
    turns         INTEGER,
    latency_s     DOUBLE PRECISION,
    quality_score REAL,
    tool_calls    JSONB
);
CREATE INDEX IF NOT EXISTS subagent_runs_task_model_idx ON subagent_runs (task_type, model);
CREATE INDEX IF NOT EXISTS subagent_runs_ts_idx ON subagent_runs (ts);
```

**Column semantics:**

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `id` | BIGSERIAL | no | primary key — allocated from `subagent_runs_id_seq`, needs `USAGE` grant to the ins role |
| `ts` | TIMESTAMPTZ | no | `DEFAULT now()` — write-time, not user-supplied |
| `project` | TEXT | no | from `SUBAGENT_PROJECT` env var — tags every row with its owning project |
| `agent_id` | TEXT | no | per-run identifier, arbitrary |
| `task_type` | TEXT | no | one of the 6 TaskKinds; ranker aggregates by this |
| `model` | TEXT | no | full OpenRouter ID (`provider/model`) |
| `provider` | TEXT | yes | usually `"openrouter"`; NULL for non-OR runs |
| `status` | TEXT | no | `"done"` counts as success in the success_rate calc; anything else is failure |
| `cost_usd` | DOUBLE PRECISION | yes | NULL rows are dropped by the aggregator (would collapse ranking) |
| `turns` | INTEGER | yes | agent conversation turns — informational, not ranked on |
| `latency_s` | DOUBLE PRECISION | yes | wall-clock — informational, not ranked on |
| `quality_score` | REAL | yes | orchestrator opt-in via `record_run`; NULL → aggregator treats as 1.0 (neutral) |
| `tool_calls` | JSONB | yes | structured trace of tools invoked — informational |

### Per-project INSERT-only role

Provisioned by `create_subagent_ins_role(project_id)` in `src/fabrik/drivers/postgres.py`. Grants exactly:

```sql
GRANT CONNECT ON DATABASE fabrik_analytics TO "<project>_subagent_ins";
GRANT USAGE ON SCHEMA public TO "<project>_subagent_ins";
GRANT INSERT ON subagent_runs TO "<project>_subagent_ins";
GRANT USAGE ON SEQUENCE subagent_runs_id_seq TO "<project>_subagent_ins";
```

**No SELECT, UPDATE, DELETE, TRUNCATE.** A compromised project key can only APPEND rows tagged with its own `SUBAGENT_PROJECT`. It can't:

- Read other projects' history (no SELECT).
- Falsify past rows (no UPDATE).
- Delete audit rows (no DELETE / TRUNCATE).
- Alter the schema (no owner, no CREATE, `NOSUPERUSER NOCREATEDB NOCREATEROLE`).

**Password lifecycle:** CSPRNG-generated only on fresh create. Existing role on re-apply → password = None → DSN NOT re-injected → prior `.env` value survives. This is deliberate — rotating on re-apply would break a running project's cached-image container that doesn't recreate to pick up the new `.env`.

### File locations

**On the hub (`/opt/fabrik`):**

| Path | Purpose |
|---|---|
| `scripts/kilo-benchmarks/apply_subagent_runs_ddl.sh` | One-shot DDL applier for WSL local postgres. VPS uses `ensure_shared_analytics_db()`. |
| `scripts/kilo-benchmarks/rank_task_subagents.py` | Nightly aggregator — reads `subagent_runs`, emits the ranked markdown. |
| `scripts/kilo-benchmarks/tests/test_rank_task_subagents.py` | 16 tests, incl. 2 live-DB integration tests (skip if postgres unreachable) |
| `scripts/kilo-benchmarks/daily_refresh.sh` | Cron chain — invokes `rank_task_subagents.py` as step 8b between `rank_coding_subagents` (8) and `update_gateway_counts` (later) |
| `docs/reference/kilo/TASK_SUBAGENT_SELECTION.md` | The emitted ranked doc — governance-synced to every project |
| `src/fabrik/drivers/postgres.py:create_subagent_ins_role` | Per-project role provisioner |
| `src/fabrik/orchestrator/infrastructure.py:_provision_postgres` | Env inject rail — hooked into `fabrik apply` |
| `tests/test_subagent_ins_role.py` | 10 unit tests pinning the privilege boundary |

**On fabrik-lib (`/opt/fabrik-lib/subagents/`):**

| Path | Purpose |
|---|---|
| `subagents/pg_ledger.py:SUBAGENT_RUNS_DDL` | Canonical DDL source — always import, never author locally |
| `subagents/pg_ledger.py:record_run` | The Postgres write path — lazy-imports psycopg |
| `subagents/select.py:pick_models` | The read path — cost-ceiling + exclude + quality/value |
| `subagents/select.py:load_task_ranking` | Parses `TASK_SUBAGENT_SELECTION.md` → `{task_type: [models]}` |
| `subagents/select.py:_synced_ranking` | mtime-cached wrapper + 14-day staleness gate |
| `UPSTREAM_FEEDBACK.md` | Cross-repo coordination log — hub side and module side amend each other here |

**Per-project (`/opt/<project>/`):**

| Path | Purpose |
|---|---|
| `libs/subagents/` | Vendored copy of the module (per `cp -r` in Part A) |
| `.env` (VPS) / `.env.local` (WSL) | Runtime env vars — see Part B |
| `docs/reference/kilo/TASK_SUBAGENT_SELECTION.md` | Governance-synced copy of the hub's file — read by `pick_models` |

---

## Part G — Troubleshooting

### The aggregator says `state=error`

```bash
# See what went wrong:
python /opt/fabrik/scripts/kilo-benchmarks/rank_task_subagents.py 2>&1
```

The stderr line names the specific failure. Common causes:

- `sudo: a password is required` → NOPASSWD not set for postgres user. Fix `/etc/sudoers.d/postgres` to include `%<your-user> ALL=(postgres) NOPASSWD: /usr/bin/psql`.
- `psql: FATAL: role "postgres" does not exist` → WSL postgres running with a different superuser role. Adjust the script to your postgres cluster.
- `psql: FATAL: database "fabrik_analytics" does not exist` → Run `bash scripts/kilo-benchmarks/apply_subagent_runs_ddl.sh` once.
- `Timeout` → Query took >300s. Bump `SUBAGENT_RANK_TIMEOUT=600 python …` for the run.

### The aggregator says `state=ok` but always 0 rows

```bash
# Are there ANY rows in the table?
sudo -n -u postgres psql -d fabrik_analytics -c "SELECT COUNT(*) FROM subagent_runs"

# Are they within the 90-day window?
sudo -n -u postgres psql -d fabrik_analytics -c "SELECT MIN(ts), MAX(ts), COUNT(*) FROM subagent_runs"

# Does at least one (task_type, model) pair clear min-3?
sudo -n -u postgres psql -d fabrik_analytics -c "
SELECT task_type, model, COUNT(*)
FROM subagent_runs
WHERE ts > NOW() - INTERVAL '90 days'
GROUP BY task_type, model
HAVING COUNT(*) >= 3
ORDER BY COUNT(*) DESC
"
```

If zero rows clear the threshold, that's the "stub with No aggregated runs yet" case — pick_models correctly falls back to `_TABLE`, no action needed until you accumulate more runs.

### `pick_models` returns the vendored default even though the doc has real data

The 14-day staleness gate kicked in — the doc's `Last refresh:` is older than 14 days. Check:

```bash
head -1 /opt/<project>/docs/reference/kilo/TASK_SUBAGENT_SELECTION.md
```

If the date is old, either governance-sync stopped propagating the hub's fresh file, or `daily_refresh.sh` isn't running. Fix the cron / manual re-sync.

### `SUBAGENT_RUNS_DSN` unset in the container but set in `.env`

Docker Compose reads `.env` at container start but doesn't re-inject on file change unless the container is recreated:

```bash
docker compose up -d --force-recreate <service>
```

`fabrik apply` does this automatically when it injects fresh env; a manual `.env.local` edit doesn't.

---

## Part H — What's still deferred (real follow-ups)

Not blocking anyone; noted for future planning.

1. **VPS `postgres-main` DDL apply.** `ensure_shared_analytics_db()` at `src/fabrik/drivers/postgres.py:990` applies `cost_ledger` today. Extend it to also apply `SUBAGENT_RUNS_DDL` alongside — ~5 lines. Currently VPS deploys will hit `role does not exist` because the table isn't there yet, and `create_subagent_ins_role` will error. Do this before the first VPS project vendors `subagents`.

2. **WSL-dev scaffolder update.** New projects scaffolded via `fabrik scaffold` don't get the 3 env vars in their `.env.local` template. Extend `src/fabrik/scaffold.py` to add them. Existing projects still need manual `.env.local` edits per Part B.

3. **`SUBAGENT_SELECTION_DOC` absolute-path resolution.** Currently injected as a relative path (`docs/reference/kilo/TASK_SUBAGENT_SELECTION.md`) resolved from the app's cwd. If a project runs Python from a different working dir, `pick_models` misses the doc. Consider using an env-var-expanded absolute path or letting the module resolve via `pkg_resources` / project root discovery.

4. **Orchestrator quality scoring.** Every row currently has `quality_score=NULL` because `run_agents` has no automatic way to score outcomes. Building an orchestrator that scores outcomes (test-pass rate, PR-approval rate, human vote) and calls `record_run(..., quality_score=x)` closes the last-mile of the ranking.

---

## Part I — Testing conventions used in this workflow

For anyone tracing back through the code:

- **Unit tests (mocked)** live under `tests/` for driver-level code and `scripts/kilo-benchmarks/tests/` for the aggregator. All hermetic (mock `_run_sql` or `subprocess.run`).
- **Live-DB integration tests** are gated by `@pytest.mark.skipif(not _postgres_reachable(), ...)`. They seed real rows via `sudo -n -u postgres psql`, exercise the SQL, then clean up in `try/finally`. Run on WSL dev; skip in CI without postgres.
- **Privilege-boundary tests** pin the *emitted SQL* against a list of forbidden verbs (`SELECT/UPDATE/DELETE/TRUNCATE/REFERENCES/TRIGGER`) checked line-by-line against every line that names the target role. A regression that adds a stray grant on a new line is caught.

---

## What "done" looks like end-to-end

For a project X to be fully wired into the flywheel:

- [ ] `libs/subagents/` present, imports work
- [ ] `psycopg[binary]>=3.1` in `requirements.txt`
- [ ] `OPENROUTER_API_KEY` set in runtime env
- [ ] `SUBAGENT_RUNS_DSN` set (VPS: auto-injected; WSL: manual `.env.local`)
- [ ] `SUBAGENT_PROJECT=X` set
- [ ] `SUBAGENT_SELECTION_DOC=docs/reference/kilo/TASK_SUBAGENT_SELECTION.md` set
- [ ] `docs/reference/kilo/TASK_SUBAGENT_SELECTION.md` present (governance-synced)
- [ ] A `python -c "from libs.subagents.subagents import run_agents, AgentSpec; …"` smoke run has recorded a row to `subagent_runs` (verify via `SELECT COUNT(*) WHERE project='X'`)
- [ ] After ≥3 runs per (task_type, model), the nightly aggregator will list your project's data in the ranked doc.

The flywheel closes automatically from there — every future `pick_models(task_type)` call in any project returns the fleet-best model backed by real runs, and every future `run_agents` call adds a data point that sharpens the ranking further.
