# T02a — The view: obligations read live, a crisp `ready`, the distributor's `status` lines

## Scope

Implements spec § The delta D1 (the reader) and D4 (`ready`, `status`) in `scripts/work.py` — read-only
paths only (no lock, no write), so the parent's rule that the prompt path takes the store lock only for
the DECISION second chance holds unchanged. The prompt block that also shows these lines is T02b's.

1. **`obligations(repo: Path) -> list[str]`** (D1) — at most two lines, every error → that line
   omitted (one `_warn`), never a raise:
   - **Mail.** The mailbox is `Path(os.environ.get("FABRIK_MAIL_ROOT", "/opt/fabrik-mail")) / <name>`,
     `<name>` the MAIN checkout's basename — the first entry of `_worktrees(repo)` (`scripts/work.py:293`),
     the same rule as `mail.py`'s `_current_repo` (`scripts/mail.py:303-318`). Read `inbox/*.md` (dotfiles
     skipped) read-only and parse each header with `mail.py`'s own `_parse` (`scripts/mail.py:1208-1226`),
     imported by path from beside `work.py` the way `scripts/thread_anchor.py:245-270` imports `work.py`
     (cached, fail-open); a file `_parse` rejects is skipped — never moved (`list_msgs` quarantines,
     `scripts/mail.py:1509-1511`, so it is never called). `_parse(text) -> dict[str, str] | None` returns
     the frontmatter as flat strings (keys `id`, `from`, `to`, `ts`, `re`, `kind`, `ack`, `hops`, optional
     `agent`; `scripts/mail.py:440-466`). Count the headers with `ack: required`; the oldest is the one with
     the smallest `mail._ts_epoch(ts)` (`scripts/mail.py:499`, `float | None` — it normalises naive and
     offset stamps; a None is skipped), never a string minimum of the raw stamps. Line: `mail: <n> need an answer (oldest <d> d) — python3 scripts/mail.py list`
     (hours `<h> h` under a day); no such mail → no line. `ack: no` mail is never counted.
   - **Feedback queues** — only when `repo / "commands" / "_sources"` is a directory: import
     `command_feedback_report.py` by path from beside `work.py` and call `queue_depths()` (T04's
     interface, default ledger — `Path($COMMAND_RUN_DIR).parent / "command-feedback.jsonl"` when
     `COMMAND_RUN_DIR` is set, else `~/.claude/state/command-feedback.jsonl`,
     `scripts/command_feedback_report.py:34-42`); the three deepest, deepest first:
     `feedback queues: <cmd> <n> · <cmd> <n> · <cmd> <n> — /fabrik-command-improve <command>`; an empty
     mapping, a missing file or a missing `queue_depths` → no line.
2. **`ready`** (D4) — `cmd_ready` (`:2503`) prints, in order: the obligation lines; this session's
   claimed items (`_line` + ` (yours)`); open items owned by this agent; awaiting items; then the top 10
   remaining ready items by `_ready_from`'s order (`:672-688`), and a closing `… and <n> more — work.py ready --all`
   when more exist. No item prints twice. `--mine` keeps its meaning in both forms: the tail is filtered
   the way `_ready_from(mine=True)` filters it (own, then unassigned; items owned by anyone else left
   out), so `tests/test_work.py:406` (`ready --mine` → `[mine, unassigned]`) stays green unchanged;
   `tests/test_work.py:392` (plain `ready`'s exact order) moves to `ready --all`. `ready --all` prints
   exactly today's output. `next` is unchanged.
3. **`kind: next` items are their session's** — `_ready_from` skips them, so they never appear in
   `ready`, `ready --all`, `next` or the prompt's ready count (every caller of `_ready_from`, `prompt_block`'s
   count included); `status` still lists them.
4. **`status`** (D4) — `cmd_status` (`:2749-2776`) adds, before the item listing: the obligation lines;
   `UNOWNED          <n> open item(s) with no owner`; one `CLAIMS           <session[:8]> (<agent or unnamed>) <n>` line per session holding live claims, suffixed ` — over 5` when it holds more than 5; `STALE NEXT       <id> <session[:8]> set <d> d ago` for each open `kind: next` item whose `next_at` is more than 6 days old. And the spec's third growth trigger (spec § Lifecycle — Growth; the other two are V4's timing and T06's V5 reading): `AGED MAIL        <n> open mail item(s) created more than 14 days ago` whenever any exist, suffixed ` — over 50` above 50.
5. **Tests stay hermetic.** Both `_env` helpers (`tests/test_work.py:35`, `tests/test_work_claims.py:49`)
   set `FABRIK_MAIL_ROOT` and `COMMAND_RUN_DIR` under `tmp_path`, so no test reads `/opt/fabrik-mail` or
   `~/.claude/state`.

DO-NOT: `prompt_block` (T02b); `on_harvest`/`_set_next` (T05a); `drop`, the schema or the linked-item API (T01); `mail.py` or `command_feedback_report.py` (T03, T04 — consumed by path only).

Depends: T01, T04
Parallel: ⛓️
Complexity: complex
Gate: .venv/bin/python -m pytest tests/test_work.py tests/test_work_claims.py tests/test_work_view.py -q
Docs: `docs/reference/work-tracking.md` § The view is T07b's

## Touches
- scripts/work.py — PRIMARY PATH
- tests/test_work.py
- tests/test_work_claims.py
- tests/test_work_view.py

## Behavior Contract
- **Given** a temp mail root whose mailbox (named by the main checkout) holds two `ack: required` messages, one `ack: no` and one malformed file, **When** `obligations` runs, **Then** it prints `mail: 2 need an answer` with the older one's age, and the malformed file is still in the inbox afterwards (spec § The delta D1)
- **Given** a repo with `commands/_sources/` and a temp ledger with three commands' unanswered rows, **When** `obligations` runs, **Then** the feedback line lists the three deepest with their `queue_depths` counts; a repo without `commands/_sources/` prints no feedback line (spec § The delta D1)
- **Given** a store with this session's claim, an owned item, an awaiting item and 14 other ready items, **When** `ready` runs, **Then** it prints them in that order with exactly 10 others and the `… and 4 more` line, and `ready --all` prints every ready item as before (spec § Validation V3)
- **Given** an open `kind: next` item, **When** `ready`, `ready --all` and `next` run, **Then** none lists it, and `status` does (spec § The delta D3)
- **Given** live claims held by two sessions, one of them holding six, and 51 open mail items created 15 days ago, **When** `status` runs, **Then** it prints one `CLAIMS` line per session with the six-claim session flagged `over 5`, and `AGED MAIL` with `over 50` (spec § The delta D4; spec § Lifecycle — Growth)

## Context Files
- .windsurf/rules/core/10-python.md
- scripts/work.py
- tests/test_work.py
- tests/test_work_claims.py
