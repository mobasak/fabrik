# session-recall — build plan (spec-fed)

Status: CONVERGED (2026-07-25, /fabrik-plan-review: 4 passes to no-op + amendment round from operator-forwarded review [R0 state resync, unit-sweep verification, discoverability: behavioral tool descriptions + CLAUDE.md section + freshness self-heal, dual DSNs] + confirming no-op pass)
Spec: `docs/superpowers/specs/2026-07-25-session-recall-design.md` (CONVERGED 2026-07-25 — inherits its
grounding: cited external facts, fabrik-lib verdicts, parse contract, schema, rejected alternatives).
Date: 2026-07-25

## What we already agreed (operator decisions — quoted where theirs)

- Replace episodic-memory ("i will delete episodic memory, i did not like it at all" / "episodic memory has
  a lot of crashes, and put system a big load") with an owned, keyword-first, no-daemon MCP search tool.
- **R0 (safe removal) is ALREADY FULLY EXECUTED** (2026-07-25, across two sessions — state resynced here so
  no executor re-runs it): plugin uninstalled (registry + `settings.json` 0 refs); archive (4.7 GB) + index
  (1.5 GB, 27,057 sessions — figures from live `du`/`find` reads taken BEFORE deletion) deleted at 23:17;
  **`episodic-index.timer`** — a systemd timer refiring indexing every 10 min, the likely load/crash source —
  found and removed by the sibling session at 23:11 (journalctl-verified); its orphaned drop-in
  `/etc/systemd/system/episodic-index.service.d/` and two `~/.claude.json` `episodic-memory@inline` entries
  removed at 23:2x (backups kept). `~/.claude/projects` verified byte-identical throughout (6,152 files /
  6.2 GB). Phase A re-verifies the end-state only — now INCLUDING the unit/cron sweep (A.2).
- Store = **local PostgreSQL 16** (`127.0.0.1:5432`, running) — "we have local postgres in our wsl". Hub /
  tunnel / Supabase rejected (spec § Rejected).
- Index = **derived data**: rebuildable by one re-ingest → no backup.
- Archive is gone → live-tree-only ingest (decision resolved by the operator's "remove it").
- `/fabrik-data-contract` **skipped by operator instruction** ("now /fabrik-plan-after-chat with its spec
  now") — the spec's 3-table schema block IS the frozen field truth; no phase may invent a field beyond it.
- **Recorded Doc-Sync-Matrix deviations (adjudicated here so no gate WARN stalls the run):**
  (1) `docs/data-contract.md` is NOT produced — operator skipped the freeze; `check_schema_sync.py`'s WARN
  is expected and adjudicated by this line. (2) No Alembic — a workstation tool with one `db/schema.sql`
  applied as a one-off; the Matrix's "Alembic +" half is a recorded deviation, not an omission.
- Three MCP tools exactly: `search_chats`, `get_chat`, `recent_chats`. No embeddings, no LLM calls, no
  daemons, no file watcher in v1. "P4 — nothing" (ship, use two weeks before any pgvector talk).

## Cross-tree scope (operator-sanctioned — recorded so the executor doesn't halt)

The plan is hub-resident but builds a NEW project. Sanctioned writes outside `/opt/fabrik`:
`/opt/session-recall/**` (created by Phase A scaffold — brand-new, no sibling agents can be harmed) and
`~/.claude.json` (one `mcpServers` entry, backup-first). Hub-side writes: `scripts/wsl_startup_hook.sh`
(one line + header-list update) + `docs/workflows/DATA_SYNC_WORKFLOW.md` (the new pipeline step) + hub
`CLAUDE.md` (the 5-line discoverability section, E.4b) + hub `CHANGELOG.md`. The operator's dispatch of
this plan is the explicit approval for exactly these paths — nothing else outside the tree.

## Global Constraints (every phase inherits; copied verbatim from binding sources)

- Deps pinned in `/opt/session-recall/requirements.txt`: `mcp>=1.27,<2` (v2 renames FastMCP — spec dep
  table) · `psycopg[binary]>=3.3,<4`. No other runtime deps in v1.
- DB: `session_recall` on `127.0.0.1:5432` via TWO env DSNs in `/opt/session-recall/.env` (gitignored;
  role passwords generated in A.6): `SESSION_RECALL_DATABASE_URL` = the **recall_ro** DSN (server queries)
  and `SESSION_RECALL_INDEXER_DSN` = the **recall_rw** DSN (indexer CLI + E.1 freshness subprocess). No
  default DSN in code, no password anywhere but `.env` (12F-III/IV).
- **Test DB name MUST end `_test`** → `session_recall_test` — the scaffold-emitted `tests/conftest.py`
  `require_throwaway()` guard refuses anything else (fail-closed; shipped fabrik `55415e06`).
- tsvector source capped: `left(content, 300000)` (PG16 tsvector <1 MB — spec dep table). Same cap on the
  trgm expression index.
- 12-Factor non-negotiables: logs = stdout only, the hook owns redirection — the tool NEVER writes a
  logfile (XI) · schema applied by a one-off `psql -f`, never at import/startup (XII) · same backing service
  in dev+test = the one local PG (X) · no daemon / PID file (VIII) · indexer is resumable + idempotent —
  killed mid-run it loses at most the current batch and the next run re-ingests it (IX) · config = granular
  env vars, zero secrets in code (III).
- Heavy-job cap (operator feedback, June incident): the initial 6.2 GB ingest runs ONLY under
  `sudo systemd-run --scope -p MemoryMax=2G -p CPUQuota=200% …`; `SET maintenance_work_mem='256MB'` before
  GIN builds.
- ⛔ `~/.claude/projects/` is read-only to every phase. No write/move/delete ever targets it.
- Naming kebab-case; project `session-recall`, package `session_recall`.

## Context Ledger

| Source | What binds | Grounded ref |
|---|---|---|
| Spec (CONVERGED) | goal, approach, schema, parse contract, dep pins, rejected alts | `docs/superpowers/specs/2026-07-25-session-recall-design.md` |
| `core/25-data-postgres.md` (ACTIVE) | explicit FK `ON DELETE`; no SQLite backing service; env-config DSN | pack § FK / § banned |
| `core/45-testing-strategy.md` (ACTIVE) | Behavior Contract per phase; destructive tests call `require_throwaway()` first | pack anti-pattern table (destructive-test row) |
| `core/10-python.md` (ACTIVE) | py3.12, type hints, ruff clean, structlog-style stdout | pack header |
| fabrik-lib `rag` (VENDOR+ENHANCE per spec) | sparse+trigram+RRF legs to adapt (dense leg stripped) | `/opt/fabrik-lib/rag/search.py:47-57` (`search(…, rrf_k: int = 60)`), `:100-124` (calls SQL fn `rag_search(...)` returning `sparse_rank`,`trigram_rank`,`rrf_score`); leg SQL lives in `/opt/fabrik-lib/rag/migration.sql` — Phase D reads it before adapting |
| fabrik-lib `db-pool` | SKIP (spec verdict: psycopg2/Flask-oriented; spawn-per-call needs one psycopg3 conn) | `/opt/fabrik-lib/README.md` db-pool row |
| Scaffold CLI | project creation + GitHub remote | `/opt/fabrik/src/fabrik/cli.py:1755` (`--github-create`), `:1779` (`def scaffold`) |
| Hook | insertion point + `LOG_FILE` convention | `scripts/wsl_startup_hook.sh:60` (`LOG_FILE=…`), `:165` (tunnel line), `:168` (`'=== Pipeline complete …'` echo — our line goes immediately BEFORE it, INSIDE the once-per-day backgrounded block, matching its idiom; per-shell/foreground placement is wrong — see E.4) |
| Local PG bootstrap path | `sudo -n -u postgres psql` works passwordless (probed 2026-07-25); TCP as `postgres` needs a password → all DDL via `sudo -u postgres psql` | probe output in ## Evidence |
| JSONL parse contract | 12 line types; `user`/`assistant` carry `message.content` block-lists; `isSidechain`; `ai-title`/`summary`/`last-prompt` | live reads 2026-07-25 (spec § Parse contract; fenced sample in ## Evidence) |

No `docs/data-contract.md` / `docs/ui-design.md` exist for this project (data-contract skipped by operator;
no GUI). 🆕 fabrik-lib candidates: none — spec adjudicated the build as project-local (single-workstation
tool, fails candidate-check (b)).

## Phases

### Phase A — Scaffold + preflight + DB bootstrap (hub-side start)

> "Hub-side" = the `/opt/fabrik` repo **on this workstation** (the scaffold CLI lives in its venv).
> **Nothing in any phase touches vps1 or any VPS** — store is local PG per the spec; there is no deploy.

**Files:** creates `/opt/session-recall/` (scaffold output), edits its `requirements.txt`, adds
`db/schema.sql`, `README` note. **One responsibility:** a governed, empty, DB-ready project.

Steps:
1. Preflight probes (each a gate): `pg_isready -h 127.0.0.1 -p 5432` → `accepting connections` ·
   `sudo -n -u postgres psql -c 'select version()'` → `PostgreSQL 16.x` · `python3 --version` → 3.12.x ·
   `gh auth status` → logged in (needed by `--github-create`) ·
   `sudo -n systemd-run --scope -p MemoryMax=100M true` → `Running as unit: run-….scope` (probed green
   2026-07-25 — the C.3 cap mechanism exists and sudo is passwordless for it).
2. R0 end-state re-verify (read-only — the checklist a real removal taught us; every line expects EMPTY):
   `ls ~/.config/superpowers/ 2>/dev/null | wc -l` → `0` ·
   `ls -d ~/.claude/plugins/data/episodic-memory-* 2>/dev/null | wc -l` → `0` ·
   `systemctl list-timers --all 2>/dev/null | grep -ci episodic` → `0` (the timer was the respawner) ·
   `ls /etc/systemd/system/episodic* /etc/systemd/system/*/..data/../episodic* 2>/dev/null | wc -l` → `0` ·
   `crontab -l 2>/dev/null | grep -ci 'episodic\|superpowers'` → `0` ·
   `grep -ci episodic ~/.claude.json ~/.claude/settings.json` → `0` per file.
3. Scaffold from the hub: `cd /opt/fabrik && .venv/bin/python -m fabrik.cli scaffold session-recall --type python-api --github-create`
   (memory/feedback: always `--github-create`). Gate: `/opt/session-recall/project.yaml` exists;
   `git -C /opt/session-recall remote get-url origin` → a github URL.
4. Record the deviation in `/opt/session-recall/README.md` (one line): *workstation tool — deliberately no
   `specs/services/*.yaml`, no deploy; do not "fix" by deploying* (spec § Shape). Strip scaffold's FastAPI
   server remnants Phase-E won't use? **NO — keep scaffold output intact** (gate + packs assume it); the MCP
   server lives beside it. Delete nothing.
5. Deps: set `requirements.txt` runtime block to exactly `mcp>=1.27,<2` + `psycopg[binary]>=3.3,<4`
   (+ scaffold's dev/test pins untouched). `python -m venv .venv && .venv/bin/pip install -r requirements.txt`.
   Gate: `.venv/bin/python -c "from mcp.server.fastmcp import FastMCP; import psycopg; print('ok')"` → `ok`.
6. Write `db/schema.sql` — VERBATIM the spec's 3 tables + the two GIN indexes + `CREATE EXTENSION IF NOT
   EXISTS pg_trgm` + two ADDITIVE btree indexes the read paths need (recorded spec addition — additive,
   like the extension line): `CREATE INDEX IF NOT EXISTS sessions_last_at_idx ON sessions(last_at DESC);`
   `CREATE INDEX IF NOT EXISTS turns_ts_idx ON turns(ts);` (`recent_chats` orders by `last_at`; `after=`
   filters `turns.ts`; `get_chat` is already backed by `UNIQUE(session_id, seq)`) + idempotent role
   bootstrap: `DO $$ BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='recall_rw') THEN CREATE ROLE
   recall_rw LOGIN; END IF; … END $$;` (same for `recall_ro`; `GRANT SELECT` only to `recall_ro`).
   **TCP auth resolved concretely (the local PG demands a password over TCP — probed):** generate one
   32-char `[a-zA-Z0-9]` password per role via `python3 -c "import secrets,string;print(''.join(
   secrets.choice(string.ascii_letters+string.digits) for _ in range(32)))"`, apply with
   `sudo -u postgres psql -c "ALTER ROLE recall_rw PASSWORD '…'"` (same for `recall_ro`), store ONLY in
   `/opt/session-recall/.env` (gitignored; `.env.example` documents the names) — never in code (12F-III).
   `.env` carries BOTH DSNs: `SESSION_RECALL_DATABASE_URL` (recall_ro — the server's query connection) and
   `SESSION_RECALL_INDEXER_DSN` (recall_rw — the indexer CLI + E.1's freshness-self-heal subprocess).
7. Apply as a one-off (12F-XII): `sudo -u postgres psql -d session_recall -f db/schema.sql -v ON_ERROR_STOP=1`
   after `sudo -u postgres createdb session_recall` (skip-if-exists guard). Same for `session_recall_test`.
   Gates: `sudo -u postgres psql -d session_recall -c '\d turns'` shows `tsv` generated column +
   `UNIQUE(session_id, seq)` + FK `ON DELETE CASCADE`; **TCP round-trip as each role**:
   `psql "$SESSION_RECALL_DATABASE_URL" -c 'select 1'` → `1` (recall_ro) and
   `psql "$SESSION_RECALL_INDEXER_DSN" -c 'select 1'` → `1` (recall_rw).
8. Closing sequence: (a) project gate `cd /opt/session-recall && python scripts/final_gate.py --lean --json`
   → fix to `"status":"success"`; (b) `python scripts/enforcement/check_doc_sync.py` — resolve any WARNING
   whose trigger is in this phase's diff (CHANGELOG entry: scaffold + schema); (c) **run `/fabrik-review` on
   Phase A's changed surface (schema.sql + requirements + README) to its coverage-adjudicated exit — pool
   finders via `fanout("review", …, mode="read_only")` + ≥1 native `fabrik-reviewer` (Opus), every finding
   FIXED/REFUTED, quiet-round exit**; (d) commit in `/opt/session-recall` (explicit paths, trailers
   `Agent-Role: orchestrator`, `Agent-Phase: A`) and push (new repo, no siblings).

**Behavior Contract (A):** schema idempotency — re-running step 7 changes nothing
(`psql -f db/schema.sql` twice → second run exit 0, zero errors); guard wiring — the scaffolded
`tests/conftest.py` `require_throwaway` refuses `…/session_recall` and accepts `…/session_recall_test`
(2 tests, TDD them first: red on a stub schema file, green after step 6).

**Interfaces (A produces):** DB `session_recall` (+`_test`) with tables `sessions/turns/index_state` exactly
as spec § Schema + the two additive btree indexes (A.6); roles `recall_rw`/`recall_ro` with TCP passwords in
`/opt/session-recall/.env` (gitignored; names documented in `.env.example`); env names
`SESSION_RECALL_DATABASE_URL` (recall_ro, server) + `SESSION_RECALL_INDEXER_DSN` (recall_rw, indexer),
both full DSNs read from `.env`; project venv at `/opt/session-recall/.venv`.

### Phase B — Parser (`ingest/parse.py`) + fixtures

**Files:** `ingest/__init__.py` + `ingest/parse.py`, `tests/fixtures/*.jsonl` (5 fixtures),
`tests/test_parse.py`. **One responsibility:** one JSONL file → `ParseResult` (streaming), never raising
on bad input. (`ingest/` is a package — the `__init__.py` makes `python -m ingest.reindex` resolvable
from the project root, which is the cwd every invocation sets — see C.3/E.4.)

**Consumes:** nothing from A (pure stdlib). **Produces:** `parse_file(path: Path) -> ParseResult` — a
dataclass `ParseResult(meta: SessionMeta, turns: Iterator[Turn], stats: ParseStats)`; `turns` is a
**generator** (a 500 MB session must never materialize as a list — C batches it 500 rows at a time);
`ParseStats.malformed: int` is valid only after the iterator is exhausted (documented on the class).
Files are read with `encoding="utf-8", errors="replace"` (a corrupt byte never aborts a file);
`SessionMeta(id: uuid.UUID, project: str, cwd: str|None, git_branch: str|None, title: str|None,
started_at: datetime|None, last_at: datetime|None)`;
`Turn(seq: int, role: Literal['user','assistant'], ts: datetime|None, content: str)`.
`project` = the `~/.claude/projects/<dirname>` decoded (leading `-` stripped, `-`→`/` NOT attempted —
store the raw dirname; display-decoding is the consumer's concern).

Steps (TDD — risky first):
1. Build fixtures from REAL corpus slices (redact nothing — local-only test data, but keep each <50 KB):
   `clean.jsonl` (user+assistant text blocks), `malformed.jsonl` (3 broken lines injected),
   `sidechain.jsonl` (`isSidechain: true` lines), `titled.jsonl` (`ai-title` + `summary` + `last-prompt`
   lines), `empty.jsonl` (only `queue-operation`/`file-history-snapshot` lines → zero turns).
2. Write the failing tests FIRST, run red for the right reason, then implement to green — Behavior
   Contract (B), one test per row: (1) malformed lines skipped AND counted, parse never raises;
   (2) `tool_use`/`tool_result`/`thinking` blocks dropped, `text` blocks joined; (3) sidechain lines
   skipped; (4) title precedence `ai-title` > first `summary` > first user text truncated to 120 chars;
   (5) zero-turn file → `turns == []` (caller creates no session row); (6) seq is 0-based, ordered,
   role-restricted to user/assistant.
3. Gate: `cd /opt/session-recall && .venv/bin/python -m pytest tests/test_parse.py -q` → all green;
   `.venv/bin/ruff check ingest/; echo $?` → `0`.
4. Closing sequence — same as Phase A steps (a)–(d), scope = Phase B files, `Agent-Phase: B`.
   **(c) is the literal `/fabrik-review` blocking gate — pool finders + native Opus, quiet-round exit.**

### Phase C — Indexer (`ingest/reindex.py`) + initial ingest

**Files:** `ingest/reindex.py`, `tests/test_reindex.py`. **One responsibility:** walk the live tree,
incremental-ingest via `index_state`, batched `COPY`, bounded resources.

**Consumes (from A/B):** `parse_file` signature above; DB/roles from A; connects via
`SESSION_RECALL_INDEXER_DSN` (the recall_rw DSN — A's Interfaces). **Produces:** CLI
`python -m ingest.reindex [--full] [--stats]` exiting 0 on success/quiet-skip (PG down → exit 0 with one
stderr line — the hook must never hang or loop); `index_state` rows per spec schema.

Steps (TDD — risky first):
1. Failing tests first against `session_recall_test` (fixtures from B; `require_throwaway` called in the
   destructive setup fixture — Behavior Contract (C)): (1) fresh file → sessions+turns rows match fixture
   counts; (2) **idempotency: second run = zero new rows** (`SELECT count(*)` unchanged); (3) append 2 lines
   to the fixture → exactly 2 new turns (resume from `lines_ingested`); (4) inode/size regression → session's
   turns deleted (CASCADE) + fully re-ingested; (5) `pg_isready` fail path → exit 0, single stderr line;
   (6) a turn with 2 MB content ingests (tsvector cap holds — no `string is too long` error);
   (7) a file deleted between walk and open (`FileNotFoundError`) → skipped with a counted warning, run
   continues (the live tree is another process's data — races are normal, never fatal).
2. Implement: `COPY turns FROM STDIN` via psycopg3 `cursor.copy()` in batches of 500 rows; per-file
   transaction (file fully ingested or `index_state` untouched — IX resumability); `ON CONFLICT DO NOTHING`
   is NOT used — the UNIQUE constraint + per-file transaction make duplicates impossible; sessions upserted
   (`INSERT … ON CONFLICT (id) DO UPDATE SET last_at/turn_count/title`).
3. Initial full ingest (the ONLY heavy run — cwd is part of the command, `-m` needs the project root):
   `cd /opt/session-recall && sudo systemd-run --scope -p MemoryMax=2G -p CPUQuota=200% --same-dir .venv/bin/python -m ingest.reindex --full`
   (probe `--same-dir` support first: `systemd-run --scope --same-dir true`; if the systemd version lacks
   it, the fallback IS the plain scope — it inherits cwd — verify with
   `sudo systemd-run --scope pwd | grep session-recall`), with `SET maintenance_work_mem='256MB'` applied
   in-session before index-heavy work. Gates: exits 0; `--stats` prints `sessions=<N> turns=<M>
   malformed=<K> skipped_files=<J>` with `N>0` and `M>0` (N is the parseable-session count — the plan's
   acceptance number, no "≈"); `SELECT pg_size_pretty(pg_database_size('session_recall'))` recorded in the
   phase commit msg.
4. Measure search-path latency baseline: `EXPLAIN ANALYZE` one tsv query + one trgm query → both use their
   GIN indexes (plan shows Bitmap Index Scan). Record numbers in commit message.
5. Closing sequence (a)–(d), `Agent-Phase: C`. **(c) `/fabrik-review` — pool + native Opus (this phase
   touches the DB-write path + subprocess caps = the high-risk slice), quiet-round exit.**

### Phase D — Search legs (`search/legs.py`) — vendored from rag

**Files:** `search/legs.py`, `tests/test_search_legs.py`. **One responsibility:** `search(conn, query,
project=None, limit=10, after=None) -> list[Hit]` — 2-leg (tsvector + trgm) RRF fusion, read-only.

**Consumes:** schema from A; test DB + fixtures ingested via C's machinery. **Produces:**
`search(conn, query, project=None, limit=10, after=None) -> list[Hit]` with
`Hit(session_id: uuid.UUID, seq: int, project: str, ts: datetime|None, snippet: str, rrf_score: float)`
(`snippet` = `ts_headline('simple', left(content,300000), …)` with `[[match]]` markers);
**plus the two read accessors Phase E's other tools need** (same file, same read-only connection):
`get_turns(conn, session_id, around_seq=None, window=20) -> list[Turn]` and
`recent_sessions(conn, project=None, n=10) -> list[SessionMeta]` — `Turn` and `SessionMeta` are Phase B's
dataclasses, imported `from ingest.parse import SessionMeta, Turn` (one shared definition, no duplicates).

Steps:
1. READ `/opt/fabrik-lib/rag/migration.sql::rag_search` first (fn at `:304-424`; sparse CTE `:354-363`,
   trigram CTE `:372-381`, RRF `:405-407`) — adapt its sparse + trigram CTEs + RRF (`1.0/(rrf_k+rank)`,
   `rrf_k=60` per `search.py:57`) into a plain SQL query (no SQL function — two tables, no tenancy, no
   RLS). Dense leg stripped (spec verdict; adaptation, not core change).
   ⚠️ **Predicate must match the expression index:** the trgm index is on `left(content, 300000)`, so the
   trigram leg's predicate and ordering are `left(content, 300000) % $q` /
   `similarity(left(content, 300000), $q)` — a predicate on bare `content` (as in `migration.sql:381`)
   would seq-scan the 6.2 GB corpus. Same for `ts_headline` input.
2. TDD — Behavior Contract (D): (1) exact keyword hits rank via tsv leg (`websearch_to_tsquery('simple',…)`);
   (2) substring/typo'd Turkish token hits via trgm leg (`left(content,300000) %`/`similarity`) — seeded
   fixture with a Turkish sentence; (3) RRF: a row hit by BOTH legs outranks single-leg rows; (4) `project=`
   and `after=` filters constrain results; (5) read-only — a `recall_ro` connection serves every function
   end-to-end; (6) `get_turns(conn, session_id, around_seq=None, window=20) -> list[Turn]` returns the
   seq-window (backed by `UNIQUE(session_id, seq)`); (7) `recent_sessions(conn, project=None, n=10)`
   orders by `last_at DESC` (backed by `sessions_last_at_idx`), respects `project=`.
3. Gate: `pytest tests/test_search_legs.py -q` green;
   `EXPLAIN (FORMAT TEXT) <the legs query> | grep -c 'Bitmap Index Scan'` → `≥2` (both GIN indexes engaged).
4. Closing sequence (a)–(d), `Agent-Phase: D`. **(c) `/fabrik-review` quiet-round exit (pool + native Opus).**

### Phase E — MCP server + registration + hook + docs convergence

**Files:** `server.py`, `tests/test_server.py`; edits `~/.claude.json` (backup first), hub
`scripts/wsl_startup_hook.sh`, hub `CHANGELOG.md`; project docs per Doc Sync Matrix. **One
responsibility:** expose the three tools to Claude Code and wire the daily incremental.

**Consumes:** `search/legs.py` — `search()`, `get_turns()`, `recent_sessions()` (all of D's Produces);
C's reindex CLI; A's env name. **Produces:** MCP tools `search_chats(query, project=None, limit=10,
after=None)` (→ `search`), `get_chat(session_id, around_seq=None, window=20)` (→ `get_turns`),
`recent_chats(project=None, n=10)` (→ `recent_sessions`); registration name `session-recall`.

Steps:
1. `server.py`: `FastMCP("session-recall")`, stdio; each tool opens ONE `recall_ro` psycopg connection per
   call (spawn-per-session process — no pool, spec verdict); **ANY `psycopg.Error`** (down, mid-query drop,
   timeout — `connect_timeout=5`) → return the literal string
   `"session-recall: database unreachable (is local postgres up?)"` — never raise, never retry (TDD this:
   Behavior Contract (E) test 1 with PG env pointed at a dead port).
   **Tool descriptions are behavioral triggers, not feature prose (recorded spec amendment — reviewer
   feedback, adopted):** each description states WHEN to reach for the tool — for `search_chats`: *"The
   user may reference work, decisions, or discussions not visible in this conversation ('the bug we
   fixed', 'as we decided', 'continue where we left off'). Search before answering such references, and
   after context compaction when earlier decisions are unclear. Never state that no previous conversation
   exists without searching first."* — analogous when-to-use lines on `get_chat`/`recent_chats`.
   **Freshness self-heal (recorded spec amendment — closes the day-of gap the boot-cadence indexer
   leaves):** `search_chats` first runs `SELECT max(mtime) FROM index_state`; if NULL or older than 3
   hours, it spawns `timeout 120 <venv>/python -m ingest.reindex` (cwd `/opt/session-recall`, RW DSN from
   `SESSION_RECALL_INDEXER_DSN` env — queries stay on the `recall_ro` connection, the role split survives)
   and proceeds after it returns (or on timeout, with results possibly stale — never an error). Behavior
   Contract (E) gains: (6) stale `index_state` → the indexer subprocess is invoked (monkeypatched spawn
   asserted), fresh → not; (7) indexer-subprocess failure/timeout → search still answers from the
   existing index.
2. TDD remaining Behavior Contract (E): (2) `search_chats` returns snippets w/ session_id+project+ts;
   (3) `get_chat` centers `around_seq` ±window and paginates; (4) `recent_chats` orders by `last_at` desc,
   respects `project=`; (5) stdio smoke — `tests/test_server.py::test_stdio_handshake` spawns
   `.venv/bin/python server.py` as a subprocess via the SDK's own client
   (`mcp.client.stdio.stdio_client` + `ClientSession.initialize()`) and asserts the session lists exactly
   the 3 tools; runnable as `pytest tests/test_server.py::test_stdio_handshake -q`.
3. Register (backup first per credentials-file rule):
   `cp ~/.claude.json backups/claude.json.backup.$(date +%Y%m%d-%H%M%S)` (project `backups/`, gitignored) →
   python-json edit adding `mcpServers["session-recall"] = {"command": "/opt/session-recall/.venv/bin/python",
   "args": ["/opt/session-recall/server.py"]}`. **Recorded spec amendment (surfaced, not silent):** the
   spec's `:124` says `python3 …` — the venv interpreter replaces it because the pinned deps live in the
   venv; a bare `python3` would `ModuleNotFoundError: mcp` on spawn.
   Gate: `python3 -c "import json;d=json.load(open('$HOME/.claude.json'));print(d['mcpServers']['session-recall']['command'])"`.
4. Hub hook line — INSIDE the once-per-day backgrounded pipeline block, immediately BEFORE the
   `'=== Pipeline complete …'` echo (`wsl_startup_hook.sh:168`), matching the block's own idiom (every
   long step there runs `>> $LOG_FILE 2>&1` inside the `nohup bash -c "…" &` wrapper — daily cadence, never
   per-shell, never foreground):
   `cd /opt/session-recall && timeout 600 .venv/bin/python -m ingest.reindex >> $LOG_FILE 2>&1 || echo \"[session-recall] incremental index failed (non-fatal)\" >> $LOG_FILE`
   (the `cd` makes `-m ingest.reindex` resolvable; `timeout 600` bounds a hung DB; the reindex CLI itself
   exits 0-with-stderr-line when PG is down, per C). Gates: `bash -n scripts/wsl_startup_hook.sh` → exit 0;
   `grep -c 'ingest.reindex' scripts/wsl_startup_hook.sh` → `1`. Also update the hook's header step list
   (`:8-28`) with the new step, and add the step to `docs/workflows/DATA_SYNC_WORKFLOW.md` (its stated
   single-source-of-truth role). Hub CHANGELOG entry.
4b. **Discoverability — the governance layer (recorded spec amendment; reviewer feedback, adopted):** add a
   5-line section to hub `/opt/fabrik/CLAUDE.md` (synced fleet-wide by the governance pipeline) —
   *"Past sessions are searchable"*: names the three `session-recall` MCP tools and the trigger situations
   (resuming work, prior-decision references, post-compaction gaps; search before claiming no history
   exists). Gate: `grep -c 'session-recall' /opt/fabrik/CLAUDE.md` → `≥1`; hub `final_gate --lean` green.
   **Kilo: decided NO** — Kilo CLI retired org-wide 2026-07-19; Claude Code agents only.
5. **Live end-to-end test (the spec's success criterion), headless and executor-runnable:**
   `claude -p 'Use the session-recall MCP tools: call search_chats("claudeck fable model picker") and then get_chat on the top hit. Print both results verbatim.'`
   → output contains hits from THIS conversation's session (project `-opt-fabrik`). Recorded verbatim in
   the phase commit message.
6. Doc steps (pool-reconciled + native-verified via `scripts/doc_reconcile.py`, curated not hand-drafted):
   project `docs/CONFIGURATION.md` (+`.env.example`: `SESSION_RECALL_DATABASE_URL` +
   `SESSION_RECALL_INDEXER_DSN`), `docs/QUICKSTART.md`
   (the 3 tools), `docs/FEATURES.md`, `CHANGELOG.md`, `INDEX.md` (+ project `docs/README.md` if any doc
   file is added rather than edited), `db/schema.sql` already in-repo; hub `CHANGELOG.md` +
   `docs/workflows/DATA_SYNC_WORKFLOW.md` (hook step, per E.4).
7. Closing sequence (a)–(d), `Agent-Phase: E`; **(c) `/fabrik-review` quiet-round exit (registration +
   hook edit = outward-facing slice → native Opus mandatory)**; then **(final) run `/fabrik-docs-review`**
   on the project docs to a zero-discrepancy no-op — the plan's last act before the whole-plan wrap-up.
8. Whole-plan wrap-up: `python scripts/final_gate.py --check --json` (FULL Tier-2) in `/opt/session-recall`
   → `"status":"success"` verbatim in the run report; `python scripts/enforcement/check_convergence.py`
   green; hub-side `final_gate --lean` green for the hook/CHANGELOG edit; **`docs/LESSONS_LEARNT.md`** —
   write the run's entry in the project (or record `none` explicitly in the completion block; silence =
   failure per CLAUDE.md). Green gates are necessary, NOT sufficient — the Evidence + the live E2E test are
   the proof of soundness.

## Parallelism & subagents (pool-default, per phase)

- Phases are SEQUENTIAL (B needs A's schema; C needs B's parser; D needs C's data; E needs D) — no
  phase-level fan-out. Within phases: fixture authoring (B.1) and per-behavior test authoring (all phases)
  fan out to **pool** authors via `/fabrik-generate-tests` machinery (`fanout("code", mode="write")`, disjoint
  `owned_paths` = one test file each), reviewed + applied by the orchestrator. Every `/fabrik-review` gate
  dispatches **pool finders (`fanout("review", mode="read_only")`, auto-recorded + `set_quality` back-filled)
  AND ≥1 native `fabrik-reviewer` on Opus** — never either-only.

## File Scope (owned paths)

- `/opt/session-recall/**` (new project — entire tree)
- `/opt/fabrik/scripts/wsl_startup_hook.sh` (one line + header list) · `/opt/fabrik/CHANGELOG.md` (one
  entry) · `/opt/fabrik/docs/workflows/DATA_SYNC_WORKFLOW.md` (one step) · `/opt/fabrik/CLAUDE.md` (the
  5-line discoverability section, E.4b)
- `~/.claude.json` (one `mcpServers` key; backup-first)
- `docs/development/plans/2026-07-25-plan-1-session-recall.md` (this file — status updates per phase)
Disjoint from all known in-flight plans (none touch these paths).

## Evidence

Phase-grounding captured 2026-07-25 (this session):

- Hook: `scripts/wsl_startup_hook.sh:60` `LOG_FILE="$FABRIK_ROOT/scripts/kilo-benchmarks/cache/update.log"`;
  `:165` tunnel line inside the backgrounded block; `:168` pipeline-complete echo (insertion point — before
  it, inside the block); block closes `" &` at `:169`; `FABRIK_ROOT` defined at `:32`.
- Scaffold CLI: `src/fabrik/cli.py:1755` `"--github-create"`, `:1779` `def scaffold(`.
- rag legs: `/opt/fabrik-lib/rag/search.py:2` "Three-leg hybrid search (pgvector + tsvector + pg_trgm +
  RRF)"; `:57` `rrf_k: int = 60`; `:100-124` SQL call returning `sparse_rank, trigram_rank, rrf_score`.
- Local PG probe:

```
$ sudo -n -u postgres psql -c 'select 1'   # peer auth works passwordless
 ?column?
----------
$ psql -U postgres -h 127.0.0.1 -c 'select 1'
Password for user postgres:               # TCP needs password → DDL via sudo -u postgres
```

- JSONL line-type inventory (live read, `dd3c06d1…jsonl`):

```
user -> keys [..., 'isSidechain', 'message', ...] message_keys ['content','role'] content_type list block_types ['text']
assistant -> message_keys [..., 'model','role','usage'] block_types ['thinking']
ai-title -> {'aiTitle', 'sessionId', 'type'} · summary -> {'leafUuid','summary','type'} · last-prompt · queue-operation · attachment · file-history-snapshot/delta · system · mode · frame-link
```

- R0 end-state: `~/.config/superpowers/` empty; plugin dirs gone; `~/.claude/projects` 6,152 files / 6.2 GB
  before AND after deletion (fence held).
- External pins inherited from the spec's dep table (all fetched 2026-07-25): `mcp` 1.28.1 stable, v2
  pre-release (pin `<2`); `psycopg` 3.3.4; tsvector <1 MB; `gin_trgm_ops` LIKE/ILIKE acceleration.

## Self-audit

- Grounding passes: spec inheritance (verbatim schema/pins), hook-file read (insertion point + LOG_FILE),
  PG auth probe (sudo path works, TCP needs password → shaped step A.7), scaffold CLI flags at path:line,
  rag API at path:line, JSONL shapes from live files.
- (a) Coverage vs "What we already agreed": replace episodic-memory → A.2 verify + E.5 E2E; local PG →
  A.6-7; derived-data/no-backup → Global Constraints + C design; 3 tools → E; no daemons/embeddings/LLM →
  Global Constraints + D/E design; skipped data-contract → schema frozen from spec § Schema (A.6 verbatim);
  "P4 nothing" → no phase F exists. No gaps found.
- (b) Cross-phase signatures: `parse_file/ParseResult(meta, turns: Iterator[Turn], stats: ParseStats)`
  (B→C), `search/Hit` + `get_turns` + `recent_sessions` (D→E, one per MCP tool), env
  env DSNs `SESSION_RECALL_DATABASE_URL` (recall_ro: A→D/E) + `SESSION_RECALL_INDEXER_DSN` (recall_rw:
  A→C + E.1 self-heal), CLI `cd /opt/session-recall && … -m ingest.reindex` (C→E hook, cwd always set) —
  names identical at every consume site in this file.
- Fixed point NOT yet claimed — that is `/fabrik-plan-review`'s call.

## Residual unknowns

- **Resolved:** store, schema, pins, hook point, PG bootstrap path, parse contract, R0 state, test-DB guard
  interplay (`session_recall_test` passes the `_test` marker).
- **Still-open (self-service — the executor settles these without stopping):**
  1. Sidechain-drop percentage (measured by C.3 `--stats`; informational only, affects no structure).
  2. Exact live-tree parseable-session count vs 6,152 files (many are zero-turn; C.3's `--stats`
     `sessions=<N>` output IS the acceptance number — the gate requires only `N>0`, `M>0`).
  3. Whether scaffold's emitted FastAPI `src/` passes the project gate untouched alongside the new modules
     (A.8 gate answers it; if mypy flags unused scaffold stubs, fix forward within Phase A scope).
