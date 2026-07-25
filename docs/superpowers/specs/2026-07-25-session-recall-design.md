# session-recall — design spec

Status: CONVERGED (2026-07-25, /fabrik-spec-review: 2 passes, pass 2 = zero-candidate no-op)
Date: 2026-07-25
Scale: feature (one operator-carried plan) — routing verdict per `/fabrik-spec` Phase 0.

## Goal

Give Claude Code agents on this workstation searchable access to all past session history via an MCP
server — `search_chats`, `get_chat`, `recent_chats` — replacing the `episodic-memory` plugin, which the
operator is removing for crashes and system load. **Phase R0 of the build is the full safe removal of
episodic-memory.** Success = an agent in any session can answer "what did we decide about X in project Y"
from indexed history, with no daemons, no embeddings, no LLM calls, and bounded resource use.

## Phase R0 — safe removal of episodic-memory (FIRST, before any build)

Ordered, fail-safe removal; the **hard fence** is stated first:

> ⛔ **`~/.claude/projects/` is untouchable.** It is the live Claude Code history and the sole source of
> truth this project indexes. No removal step may write, move, or delete anything under `~/.claude/`
> except the plugin's own directories listed below. No glob may have `~/.claude` as its prefix root.

1. Uninstall the plugin (`/plugin uninstall episodic-memory@superpowers-marketplace` or `claude plugin remove`) —
   removes its MCP server registration + the `search-conversations` agent + `remembering-conversations` skill.
2. Remove its session-end hook if independently wired (check `~/.claude/settings.json` hooks and
   `.claude/hooks/session-end`; delete only entries referencing episodic-memory).
3. Delete its data (operator-approved 2026-07-25): `~/.config/superpowers/conversation-archive/` (4.7 GB),
   `~/.config/superpowers/conversation-index/` (1.5 GB), `~/.claude/plugins/data/episodic-memory-*`,
   `~/.claude/plugins/cache/superpowers-marketplace/episodic-memory/`.
4. Verify: a fresh `claude` session shows no episodic-memory MCP/agent; `~/.claude/projects/` file count
   and total size unchanged (record before/after).

**Recorded decision (operator override available):** the archive holds ~27,057 sessions vs ~6,151 in the
live tree — pre-prune history exists only there. Deleting it means session-recall indexes the live tree
only. This keeps the index purely **derived data** (rebuildable from source at any time → needs no backup).
If pre-prune history matters, say so before R0 runs and step 3 gains a one-time archive ingest first —
at the cost of the index no longer being rebuildable.

## Chosen approach

**Build a small owned tool (~300 lines) on the already-running local PostgreSQL 16** — parser + incremental
indexer CLI + stdio MCP server. Keyword-first hybrid search: `tsvector('simple')` + `pg_trgm`, RRF-fused —
the two non-vector legs of `fabrik-lib/rag/search.py`, vendored. No embeddings, no LLM calls, no daemon,
no file watcher.

Why this beats adopting a community tool (the 1c research, this session, 2026-07-25): the ecosystem
(exa + brave sweeps) shows the low-load consensus architecture is exactly this — local index, keyword FTS,
incremental by file-state, stdio spawn-per-session; but the only tools matching the operator's constraints
are unvetted (gebeer/conversation-search-mcp: 3★, no stated license; ticpu/claude-conversation-search-mcp:
7★, GPL/MIT conflict — both fetched 2026-07-25). The popular options each violate a stated requirement:
claude-mem (LLM compression calls), mnemo (persistent server + port 19419 dashboard), deja (ONNX embedding
load), ClaudeHistoryMCP (session-start auto-injection + cloud sync), Stefan-Nitu (in-memory index rebuilt
per start — 6.2 GB corpus in RAM). Anthropic's native chat search covers claude.ai app conversations, not
Claude Code CLI sessions (support.claude.com article, fetched 2026-07-25). The operator just removed a far
more popular community plugin for crashes; owning 300 governed, tested lines beats depending on a 3★ repo.

### Architecture (4 units, isolation-clean)

| Unit | Does | Depends on |
|---|---|---|
| `ingest/parse.py` | one JSONL → session meta + turns (contract below) | stdlib only |
| `ingest/reindex.py` | walk `~/.claude/projects/**/*.jsonl`, incremental via `index_state`, batch `COPY` | parse.py, psycopg |
| `search/legs.py` | vendored rag two-leg search (tsvector + trgm + RRF), dense leg stripped | psycopg |
| `server.py` | stdio MCP: `search_chats` / `get_chat` / `recent_chats`, read-only | mcp (FastMCP), legs.py |

### Parse contract (pinned from real files THIS session — not from docs)

Line types observed in the live corpus (`dd3c06d1…jsonl`, 2026-07-25): `user`, `assistant`, `summary`,
`ai-title`, `last-prompt`, `queue-operation`, `attachment`, `file-history-snapshot`, `file-history-delta`,
`system`, `mode`, `frame-link`.

- **Index**: `type∈{user,assistant}` → `message.role`, `message.content` = list of blocks; keep `text`
  blocks only (drop `thinking`, `tool_use`, `tool_result`). Row fields from `uuid`, `sessionId`,
  `timestamp`, `cwd`, `gitBranch`.
- **Skip**: `isSidechain: true` lines (inline subagent branches — tool-noise; a v2 flag column can revisit).
- **Title**: `ai-title.aiTitle` if present, else first `summary.summary`, else first user text (truncated).
- **Malformed lines**: skip and count, never abort (JSONL-corruption incident is on record); report count.
- **Zero-turn files** (many exist): no session row.

### Schema (local PG 16, database `session_recall`)

```sql
sessions(id uuid PK, project text, cwd text, git_branch text, title text,
         started_at timestamptz, last_at timestamptz, turn_count int)
turns(id bigserial PK,
      session_id uuid REFERENCES sessions(id) ON DELETE CASCADE,
      seq int, role text CHECK (role IN ('user','assistant')),
      ts timestamptz, content text,
      tsv tsvector GENERATED ALWAYS AS (to_tsvector('simple', left(content, 300000))) STORED,
      UNIQUE(session_id, seq))
-- GIN(tsv) · GIN(left(content, 300000) gin_trgm_ops)
index_state(file_path text PK, inode bigint, size bigint, mtime timestamptz, lines_ingested int)
```

- `left(content, 300000)`: tsvector hard limit is **<1 MB** (PG16 docs, textsearch-limitations, fetched
  2026-07-25); real turns contain multi-MB pastes — an uncapped generated column aborts ingest.
- `ON DELETE CASCADE` + `UNIQUE(session_id, seq)`: the re-ingest path deletes sessions; uniqueness makes
  idempotency enforceable, not just observed. Explicit FK behavior per `core/25-data-postgres`.
- `'simple'` config: mixed TR/EN corpus — no stemming beats wrong stemming; trgm leg covers substrings.
- Roles: `recall_rw` (indexer) / `recall_ro` (MCP server) — real read-only split.
- **Derived data**: rebuildable from the JSONL corpus by one re-ingest → no backup, no Backrest.

### Indexer (no daemon, bounded)

- Runs from `wsl_startup_hook.sh` (one line, `pg_isready` guard, after PG; also manually runnable any time).
- Incremental: JSONL is append-only → resume from `lines_ingested`; inode/size regression → delete session
  (CASCADE) + full re-ingest of that file. Consensus mechanic across the surveyed tools.
- Batch `COPY` via psycopg 3.3.4 — local socket now, but batching kept (cheap, correct).
- **Initial 6.2 GB ingest runs under `systemd-run --scope` with hard CPU+memory caps**, and GIN builds get
  bounded `maintenance_work_mem` — the June "heavy unbounded indexer starved the box" incident class is a
  named design constraint, not a footnote.
- Freshness gap: startup-hook cadence → same-day sessions unindexed until next boot/manual run. Accepted v1.

### MCP server

- stdio, spawn-per-session, `mcp` SDK FastMCP — **pinned `mcp>=1.27,<2`**: the v2 pre-release line renames
  `FastMCP` → `MCPServer` and its stable is targeted 2026-07-27; the SDK's own README instructs adding the
  `<2` bound (github.com/modelcontextprotocol/python-sdk v1.x + main READMEs, both fetched 2026-07-25).
  Current stable 1.28.1, Python ≥3.10.
- `search_chats(query, project=None, limit=10, after=None)` → RRF-fused snippets with grep-style ±context
  and match markers (patterns adopted from ticpu/gebeer, cited above); `get_chat(session_id, around_seq=None,
  window=20)`; `recent_chats(project=None, n=10)` (sessions by `last_at`).
- PG down → one clear error string; never crash, never retry-loop.
- Registration: global `~/.claude.json` `mcpServers` entry, absolute path, `python3 /opt/session-recall/server.py`.

## Rejected alternatives

1. **Hub `postgres-main` over the tunnel** (original draft): tunnel SPOF, ~400 ms/search, 1.5–2 GB on an
   11.6 GB box running 31 containers — for zero benefit once the DB is recognized as derived data. Local
   PG 16 is already running (`127.0.0.1:5432`, verified this session).
2. **Adopt a community MCP tool**: see Chosen approach — no candidate is both constraint-matching and vetted.
3. **SQLite FTS5 DIY**: fewer moving parts in isolation, but PG is already running (zero added infra),
   `core/25-data-postgres` bans SQLite as a backing service (a workstation tool is a gray zone not worth
   entering), TR substring matching is stronger with `pg_trgm`, and pgvector is the free v2 path.
4. **Fix/keep episodic-memory**: operator decision — removed for crashes + load (embedding + summarization
   pipeline). Its 11 GB archive+index duplication also conflicts with lean storage.
5. **Supabase**: retired org-wide 2026-07-03 (ADR exception only); cloud DB for private transcripts is also
   a privacy non-starter. Rejected on governance + shape both.

## External dependencies (all fetched THIS session, 2026-07-25)

| Dependency | Grounded fact | Source |
|---|---|---|
| `mcp` (Python SDK) | v1.28.1 (2026-06-26), Python ≥3.10, FastMCP + stdio transport. ⚠️ Pin `>=1.27,<2`: v2 (stable targeted 2026-07-27) renames FastMCP → MCPServer; upstream README mandates the `<2` bound | pypi.org/project/mcp/ + github.com/modelcontextprotocol/python-sdk (v1.x & main READMEs) |
| `psycopg` | v3.3.4 (2026-05-01), Python ≥3.10, `[binary]` extra | pypi.org/project/psycopg/ |
| PG tsvector limits | tsvector <1 MB; lexeme <2 KB; positions ≤16,383 | postgresql.org/docs/16/textsearch-limitations.html |
| `pg_trgm` | `gin_trgm_ops` GIN class; accelerates LIKE/ILIKE/`%`; trigram-free patterns degenerate to full-index scan | postgresql.org/docs/16/pgtrgm.html |
| Ecosystem survey | 8 tools compared (mnemo, deja, claude-mem, ClaudeHistoryMCP, Stefan-Nitu, gebeer, ticpu, claude-session-explorer) | exa + brave sweeps + 2 repo fetches, 2026-07-25 |
| Native chat search | claude.ai app conversations only, not Claude Code CLI | support.claude.com/en/articles/11817273 |
| JSONL corpus | 6.2 GB, 6,151 files; line-type inventory + field shapes read from live files | local reads, 2026-07-25 |
| Local PostgreSQL | native PG 16 active on 127.0.0.1:5432 (systemd, up since boot) | `ps`/`ss` verification, 2026-07-25 |

## fabrik-lib verdict table

| Capability | Verdict | Module / why |
|---|---|---|
| Hybrid search legs + RRF | **VENDOR + ENHANCE** | `rag/search.py` is three-leg (pgvector+tsvector+trgm+RRF, `search.py:2-5`); vendor the two sparse legs + RRF SQL, strip the dense leg (adaptation at the seams, not a core change — no upstream needed; if leg-toggling lands upstream note it in `rag/UPSTREAM_FEEDBACK.md`) |
| DB pool | **skip** | `db-pool/` is psycopg2/Flask-oriented; a spawn-per-call stdio server needs one short-lived psycopg3 connection, no pool |
| JSONL parser · indexer · MCP glue | **BUILD (project-local)** | Claude-Code-transcript-specific; new-module-candidate check FAILS (b): single-workstation operator tool, not reused by ≥2 project types → no fabrik-lib flag |
| Alerting/auth/storage/etc. | **n/a** | no auth (local, single user), no cloud storage, no alerts in v1 |

## Shape / infra implications

- **Not a deployed service.** No `specs/services/*.yaml`, no compose, no Traefik, no VPS — a workstation
  tool. Scaffold as `python-api` for governance packs + gate, with a recorded deviation: *no deploy spec on
  purpose; do not "fix" by deploying.* (`shape:` flags: none — nothing registers.)
- 12-Factor where it applies to a local CLI/MCP: deps in `requirements.txt` (II); `DATABASE_URL` from env
  with localhost default (III/IV); stdout logging, hook owns redirection (XI); no daemon (VIII).
- **Recorded deviations (single-environment tool):** the "`localhost` as a DB host = defect" and dev/prod-parity
  mandates target *deployed* services reaching `postgres-main`; this tool has exactly one environment (the
  workstation), never deploys, and swaps its DB by `DATABASE_URL` alone — the constraint's intent (config-only
  swap, IV) is satisfied. Likewise `/health`+`/metrics` are **n/a**: a spawn-per-call stdio process is not a
  probeable service; operational visibility = the MCP error string + the hook's ingest log line.

## Constraints digest (rule-grounding gate)

| Rule | Source | Implication here |
|---|---|---|
| SQLite banned as server-side backing service | `core/25-data-postgres` | store = local PG 16, not SQLite (also kills alternative 3) |
| Vector DB = pgvector on Postgres only | `agents-fabrik.md` hard constraints | v2 semantic leg (if ever) = pgvector in-place, never Pinecone/Qdrant |
| Explicit FK `ON DELETE` | `core/25-data-postgres` | `turns.session_id … ON DELETE CASCADE` |
| Vendor before build | `CLAUDE.md` / fabrik-lib ladder | rag search legs vendored, ladder run for every capability |
| Heavy local jobs must be capped | operator feedback (June incident) | initial ingest under `systemd-run --scope`; bounded `maintenance_work_mem` |
| LLM gateway = OpenRouter only | `agents-fabrik.md` | n/a by design — zero LLM calls in this tool |
| Secrets never in code | `core/35-security-auth` floor | only cred is local PG role password via env |
| kebab-case naming | `CLAUDE.md` | `session-recall` |

## Open / blocking unknowns

- **RESOLVED this session:** store location (local PG); episodic-memory fate (remove, R0); data deletion
  scope (archive+index deleted; `~/.claude/projects` fenced); JSONL field shapes (read from live files);
  tsvector limit (cited); ecosystem alternatives (surveyed, rejected with cites).
- **OPEN (self-service, resolved at plan time — no user input needed):**
  1. Exact `wsl_startup_hook.sh` insertion point + `$LOG_FILE` convention → read the hook file during
     planning (it's on this machine).
  2. `recall_rw`/`recall_ro` role bootstrap idempotency → standard `DO $$ … IF NOT EXISTS` block, written
     at plan time.
  3. Sidechain volume (what % of turns `isSidechain` filtering drops) → measure during P0 of the plan;
     affects nothing structural.
- No "zero unknowns" claim — the plan's P0 re-verifies the parse contract against 3+ files including a
  repaired one before any schema is created.

## Pipeline

Data-shaped → next: `/fabrik-data-contract` (freeze the 3-table contract), then `/fabrik-plan-after-chat`
(no GUI — skip UI commands).
