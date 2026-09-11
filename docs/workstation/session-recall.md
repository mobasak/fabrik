# session-recall — workstation session history & recall

**Last Updated:** 2026-08-03 (verified live — PostgreSQL 16.14 cluster online, index at 3 878 sessions / 138 971 turns fresh to the minute, `session-recall` MCP registered in `~/.claude.json`, the `SessionStart` hook installed in `~/.claude/settings.json` alongside the pre-existing claude-manager tap)

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

## ⚠️ How that `**` is keyed — and why a session can vanish from the history picker

The `**` in `~/.claude/projects/**/*.jsonl` is **the session's current working directory, path-mangled**
(`/opt/iterative_image_editor` → `-opt-iterative-image-editor`). Two consequences that look like data loss
and are not:

- **A session that CHANGES cwd is RE-FILED mid-session.** `EnterWorktree` (and any `--worktree` launch) moves
  the cwd into `<repo>/.claude/worktrees/<name>`, so the transcript moves from `-opt-<repo>` to
  `-opt-<repo>--claude-worktrees-<name>`. Nothing is copied back.
- **The VS Code history picker lists only the sessions filed under the window's OWN cwd key.** Reload the
  window at the repo root and a lane that had entered a worktree is simply not in the list — and a reload
  also ends its process, so the reopened window shows no history either.

**Measured 2026-09-11** (`/opt/iterative_image_editor`, three concurrent lanes): after a VS Code reload at
the repo root the picker showed two of three. The missing lane's transcript was intact — 259 MB, written
minutes earlier — filed under `-opt-iterative-image-editor--claude-worktrees-store-content-set` because that
session's cwd had moved into the worktree. Its first record carried `cwd: /opt/iterative_image_editor`, its
last `cwd: …/.claude/worktrees/store-content-set`, which is the whole story in two lines.

**Recovery, in order of cost:**

| you want | do this |
|---|---|
| the conversation CONTENT, from any window | `search_chats` / `recent_chats` / `get_chat` — the index is keyed by session id and project, so it finds a transcript under any cwd key. For a 259 MB thread this is the cheap option. |
| the session BACK, interactively | `cd <the worktree path> && claude --resume <session-id>`, or open that worktree folder as the VS Code workspace |
| to find which key a session is under | `ls ~/.claude/projects/*/<session-id>.jsonl`, or `recent_chats` with the project name |

⚠️ **Do not diagnose this with `pgrep -f <session-id>`** — the pattern matches the grep's own command line and
reports the session as alive when it is not (cost 20 minutes on 2026-09-11). Walk `/proc` and read each
`cmdline`, or check `readlink /proc/<pid>/cwd`, before claiming a session is running.

## The OTHER reason history looks missing: compaction, not filing

The cwd-keying above explains a session absent from the PICKER. A session you can open but which shows
only the last exchange is a different thing entirely — **compaction**, working as designed.

Measured 2026-09-11 on the two live `/opt/trade-intelligence` lanes:

| session | records | compactions | records AFTER the last one | what the window shows |
|---|---|---|---|---|
| `37887efc` | 116,388 | 96 | **31** | almost nothing |
| `1991fa9b` | 105,741 | 86 | 3,917 | a normal-looking session |

`37887efc` spans 2026-06-06 → 2026-09-09. Ninety-six compactions later the window renders the 31 records
after the final boundary; the other 116,357 are still in the file, just not live chat. Nothing is lost —
`get_chat` on that id returns its 7 June turns verbatim.

**So the triage is:** session absent from the picker → a cwd/filing problem (above). Session present but
nearly empty → compaction, and the history is in `get_chat`/`search_chats`, never in the window.

## Making a re-filed session visible again (measured, and safe)

Claude Code **appends to the transcript in place** — proven on a throwaway session: the inode was stable
across a `--resume` write. So a **hardlink** of the transcript into a second project key costs zero blocks,
keeps one inode (both names stay in sync through further writes), and is undone with a plain `rm` of the
extra name, because the data lives on through the other link.

```bash
# make every worktree-filed session of a repo visible from the repo-root picker
REPO=-opt-<repo>                     # e.g. -opt-iterative-image-editor
P=~/.claude/projects
for src in "$P/$REPO--claude-worktrees-"*/*.jsonl; do
  [ -e "$src" ] || continue
  dst="$P/$REPO/$(basename "$src")"
  [ -e "$dst" ] || ln "$src" "$dst"        # hardlink; never a copy
done
```

Two facts that make this safe rather than clever, both established by experiment rather than assumed:
**`--resume <session-id>` resolves the id GLOBALLY** — resuming from an unrelated cwd worked — so the
transcript is always reachable by id even with no hardlink; and **a resume does NOT migrate the file** — the
turn written from the second cwd landed in the ORIGINAL key, so the hardlink is what puts it in the other
picker, not the resume.

Scale, measured 2026-09-11: 21 worktree keys box-wide holding 23 transcripts out of 5,327 — but only
**3 keys in real `/opt` repos** (fabrik, iterative_image_editor, transdoc); the rest are `/tmp` probes.
Small today, and it grows with every lane that enters a worktree.

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

## Design notes — lexical-only, and where it sits in the memory stack

**It's lexical by design — no embeddings, no vector store, no LLM in the storage/retrieval loop.** Both
search legs match on **surface form**, not meaning: tsvector stems word tokens (`run`/`running` match, but
`car` never matches `automobile`); trigram matches 3-char overlap (this is what makes `gecmis` find `geçmiş`
after `unaccent`, but `memoize` and `cache the result` share almost no trigrams). This is deliberate — a
verbatim, deterministic, ~zero-cost index that hands back the **actual decision**, not an LLM's lossy
paraphrase of it. It fits the house rule (*don't trust the model's memory — cite the real thing*) and the
quota-is-the-binding-constraint reality; an LLM-distilled "episodic memory" would spend quota on every write
and re-introduce exactly the paraphrase-drift this environment fights.

**Known limitation (accepted):** because retrieval is lexical, it can miss a concept you recall by *meaning*
but not by any word actually typed — e.g. searching *"that database speedup trick"* won't find a transcript
that says *"add a btree index on `session_id`"* (no shared stem, no shared trigrams). The information is in
the index verbatim; the query just can't reach it. Covered in practice by: **`recent_chats` + the digest**
(recency — the "continue where we left off" path needs no naming), **concrete-term lookup** (most real
searches use a file/flag/service name that *was* typed), and **`get_chat` + substantive titles** (walk into
the right session from any nearby thread). **Semantic search was declined (v2 item 3, reaffirmed 2026-07-27)
— not worth the pipeline/storage/tuning for how it's used.** If ever reopened, the only acceptable shape is a
semantic *third leg over the same verbatim rows* (every hit still resolves to a real transcript via
`get_chat`) — never a lossy summary store replacing the verbatim index.

**Two-tier memory architecture (this box already runs the hybrid):**
- **Verbatim episodic** = session-recall — *what happened, exactly, searchable.* The ground-truth backstop.
- **Distilled semantic** = the `~/.claude/projects/*/memory/` auto-memory (`MEMORY.md` + per-fact files) —
  *what's durably true, recalled by relevance.* Fast, curated, but a derivative.

The layering is the point: the distilled layer for quick relevance, the verbatim layer as the source of
truth it can always be checked against. session-recall is the **foundation**, not a competitor to it.

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
