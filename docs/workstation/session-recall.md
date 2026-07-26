# session-recall — workstation session history & recall

**Last Updated:** 2026-07-26

> **What this is:** the workstation-level overview of **session-recall** — the local index of every Claude
> Code session on this box, exposed to every agent as MCP tools + an auto-injected session-start digest.
> Code lives in its own repo at **`/opt/session-recall`** (a `python-api` workstation tool — no deploy, no
> Docker, no Redis). This doc explains what it does, how the pieces fit, and **which file holds each part**.

---

## What it does

Every Claude Code conversation on this box is parsed from the raw transcripts under
`~/.claude/projects/**/*.jsonl` into a **local PostgreSQL 16** index, and served back to any agent. It lets
an agent answer, from the *real transcripts* rather than its own memory:

- *"What did we decide about X?"* — keyword search across all history
- *"Continue where we left off"* — the most recent session in this project
- *"What was I doing?"* after a `/compact` wiped the live context

## Data flow (end to end)

```
~/.claude/projects/**/*.jsonl        (raw Claude Code transcripts — the source of truth)
        │
        ▼  ingest/parse.py   → streaming JSONL parse (text turns only; sidechain/tool/thinking dropped)
        ▼  ingest/reindex.py → incremental upsert + dedup + title backfill
        │
   PostgreSQL: sessions · turns · index_state · index_run
        │
        ├── search/legs.py         → tsvector + trigram hybrid (RRF), Turkish-diacritic folded
        ├── server.py (stdio MCP)  → search_chats · recent_chats · get_chat  ← agents query here
        └── session_context.py     → SessionStart hook: prints the orientation digest at session start
```

## Code files — where each part lives (all under `/opt/session-recall/`)

| File | Role | Key symbols |
|------|------|-------------|
| `server.py` | **stdio MCP server** — the query surface agents call. Self-heals freshness before each answer; every psycopg error → one literal `DB_UNREACHABLE` string (never raises). | `search_chats` · `recent_chats` · `get_chat` (`@mcp.tool`) · `_self_heal_freshness` · `STALE_AFTER` · `_ro_dsn`/`_rw_dsn` |
| `session_context.py` | **SessionStart digest CLI** — the auto-injected orientation printed at the start of every session in every repo. Reads DB read-only; exits 0 always; prints nothing if PG is down; spawns a detached reindex nudge. | `build_digest(conn, cwd, exclude_session)` · `_hook_input(argv)` · `_spawn_reindex_detached` · `MAX_LINES=140` |
| `ingest/parse.py` | **Streaming JSONL parser** — one transcript → `ParseResult(meta, turns, stats)`. Malformed lines skipped+counted, never raise. Title = ai-title > summary > first *substantive* user text. | `parse_file` · `is_substantive_user_text` · `_NONSUBSTANTIVE_PREFIXES` |
| `ingest/reindex.py` | **Incremental indexer** — per-file transactions, batched COPY, append-resume. End-of-run cross-session pass (gated on `sessions>0`): dedup + title backfill. Run: `python -m ingest.reindex [--full\|--stats]`. | `dedup_pass` · `backfill_titles` · `RunTotals` |
| `search/legs.py` | **Search legs** — websearch-tsquery + substring-ILIKE trigram, RRF k=60, `ts_headline` snippets, `f_unaccent` folding. Excludes `superseded_by IS NULL`; `get_chat` still returns superseded by id. | `search` · `get_turns` · `recent_sessions` |
| `db/schema.sql` | **Schema** — `sessions`, `turns` (capped tsvector generated col + GIN/btree), `index_state` (heartbeat + `head_sha`), `index_run`. Idempotent rw/ro role bootstrap. | `sessions.superseded_by` (self-FK, indexed) |
| `/opt/session-recall/scripts/install_session_context_hook.py` | **Global hook installer** — merges our `SessionStart` block into `~/.claude/settings.json` (backs it up, preserves the existing tap, idempotent, migrates a stale block). Dry-run by default; `--apply` writes atomically. | `merge_hook` · `_our_block_index` · `_hook_block` (`matcher:""`) |

## The three MCP tools (query surface — `server.py`)

- **`search_chats(query, project?, after?)`** — keyword + substring hybrid, ranked+highlighted snippets; byte-identical snippets across sessions collapse to one (`· also in N other session(s)`).
- **`recent_chats(project?, n?)`** — most recent sessions by recency (the "continue where we left off" entry).
- **`get_chat(session_id, around_seq?, window?)`** — read a seq-window of turns from one session (returns superseded sessions too).

## Features (v2, shipped 2026-07-26)

1. **Freshness self-heal** — each tool runs one bounded incremental reindex before answering (`STALE_AFTER` ≈ 30 s, 8 s cap), so minutes-old work shows without a manual reindex. Fail-soft: PG down → stale/empty + a one-line notice, never an error.
2. **Dedup of forked/duplicate sessions** — a turn-content signature (not head SHA, which differs across forks) marks exact-duplicate and strict-prefix-fork sessions `superseded_by`; hidden from search/recent but still readable by id. A session that later diverges un-hides.
3. **Substantive titles** — title from the first *substantive* user message (command-stub / IDE-context / caveat openers skipped); a DB backfill upgrades existing generic titles.
4. **SessionStart digest** (`session_context.py` + the installed hook) — at the start of **every** session in **every** repo, prints a bounded (~≤2K token) digest: last 5 sessions here (title·age), the most recent session's **closing context** (its last user requests *and* the last assistant deliverables, merged in order), 3 recent sessions elsewhere, and a footer naming the MCP tools. Fires on **all** sources (matcher `""` = startup/**resume**/**compact**/fork/clear — the real flow is close-VS-Code → reopen → *continue*, a `resume`). **Excludes the session being resumed** from every section (never injects the current chat's own turns back into itself). Exit-0-always; prints nothing if recall is down.

## Config (env / `/opt/session-recall/.env`, template in `.env.example`)

| Var | Purpose |
|-----|---------|
| `SESSION_RECALL_DATABASE_URL` | read-only DSN (`recall_ro`) — the query path |
| `SESSION_RECALL_INDEXER_DSN` | read-write DSN — the indexer / self-heal |
| `SESSION_RECALL_HEAL_MAX_STALE_S` | staleness window before a tool self-heals (default 30) |
| `SESSION_RECALL_HEAL_TIMEOUT_S` | hard cap on the self-heal subprocess (default 8) |
| `SESSION_RECALL_TEST_DSN` | throwaway DB for the behavior tests |

> The MCP server is spawned by Claude Code **with no env block**, so `server.py`/`session_context.py` read
> config from `os.environ` **or** `.env` (via `dotenv_values`).

## Run / operate

```bash
cd /opt/session-recall
.venv/bin/python -m ingest.reindex            # incremental reindex (tools also self-heal)
.venv/bin/python -m ingest.reindex --full     # full re-ingest + dedup/title backfill
.venv/bin/python -m ingest.reindex --stats    # DB totals
.venv/bin/python session_context.py --cwd /opt/fabrik          # print the digest manually
.venv/bin/python scripts/install_session_context_hook.py [--apply]   # register the global hook
```

> **In-repo detail** (line refs, tests, review history) lives with the code:
> `/opt/session-recall/README.md`, `INDEX.md`, and `CHANGELOG.md`. This workstation doc is the box-level
> orientation; that repo is the source of truth for the code itself.
