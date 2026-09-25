# T02 — The view: obligations read live, every claim shown, a crisp `ready`, the unnamed-window line

## Scope

Implements spec § The delta D1, D4 and D6 in `scripts/work.py` — read-only paths only (no lock, no
write), so the parent's rule that the prompt path takes the store lock only for the DECISION second
chance holds unchanged.

1. **`obligations(repo: Path) -> list[str]`** (D1) — at most two lines, every error → that line
   omitted (one `_warn`), never a raise:
   - **Mail.** The mailbox is `Path(os.environ.get("FABRIK_MAIL_ROOT", "/opt/fabrik-mail")) / <name>`,
     `<name>` the MAIN checkout's basename — the first entry of `_worktrees(repo)` (`scripts/work.py:293`),
     the same rule as `mail.py`'s `_current_repo` (`scripts/mail.py:303-318`). Read `inbox/*.md` (dotfiles
     skipped) read-only and parse each header with `mail.py`'s own `_parse` (`scripts/mail.py:1208-1226`),
     imported by path from beside `work.py` the way `scripts/thread_anchor.py:245-270` imports `work.py`
     (cached, fail-open); a file `_parse` rejects is skipped — never moved (`list_msgs` quarantines,
     `scripts/mail.py:1509-1511`, so it is never called). Count the headers with `ack: required`; the
     oldest is the minimum `ts`. Line: `mail: <n> need an answer (oldest <d> d) — python3 scripts/mail.py list`
     (hours `<h> h` under a day); no such mail → no line. `ack: no` mail is never counted.
   - **Feedback queues** — only when `repo / "commands" / "_sources"` is a directory: import
     `command_feedback_report.py` by path from beside `work.py` and call `queue_depths()` (T04's
     interface, default ledger); the three deepest, deepest first:
     `feedback queues: <cmd> <n> · <cmd> <n> · <cmd> <n> — /fabrik-command-improve <command>`; an empty
     mapping, a missing file or a missing `queue_depths` → no line.
2. **`ready`** (D4) — `cmd_ready` (`:2503`) prints, in order: the obligation lines; this session's
   claimed items (`_line` + ` (yours)`); open items owned by this agent; awaiting items; then the top 10
   remaining ready items by `_ready_from`'s order (`:672-688`), and a closing `… and <n> more — work.py ready --all`
   when more exist. No item prints twice. `ready --all` prints exactly today's output (every ready item,
   `--mine` still honoured). `next` is unchanged.
3. **`kind: next` items are their session's** — `_ready_from` skips them, so they never appear in
   `ready`, `ready --all`, `next` or the prompt's ready count; `status` still lists them.
4. **`status`** (D4) — `cmd_status` (`:2749-2776`) adds, before the item listing: the obligation lines;
   `UNOWNED          <n> open item(s) with no owner`; one `CLAIMS           <session[:8]> (<agent or unnamed>) <n>` line per session holding live claims, suffixed ` — over 5` when it holds more than 5; `STALE NEXT       <id> <session[:8]> set <d> d ago` for each open `kind: next` item whose `next_at` is more than 6 days old.
5. **`prompt_block`** (D1, D4, D6; `:3067-3103`) — in order: the unnamed-window line when
   `_agent_name()` is empty (`work: this window has no agent name — owned items cannot reach it; run python3 scripts/whoami_agent.py --as <name>`);
   the obligation lines prefixed `work: `; the awaiting lines (unchanged); this session's `your claim`
   lines (unchanged); then one line per OTHER session holding live claims,
   `work: on it: <session[:8]> (<agent or unnamed>) — W-…, W-…` (ids sorted, the line clipped at `LINE_MAX`);
   then the ready count (now excluding `kind: next`). Every live claim in the repo therefore appears once.
   Still read-only, no lock; V4's budget: under 0.5 s on the hub's inbox and ledger.

DO-NOT: `on_harvest`/`_set_next` (T05a); `drop`, the schema or the linked-item API (T01); `mail.py` or `command_feedback_report.py` (T03, T04 — consumed by path only).

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
- **Given** an open `kind: next` item, **When** `ready`, `ready --all`, `next` and `prompt_block` run, **Then** none lists or counts it, and `status` does (spec § The delta D3)
- **Given** live claims held by two other sessions, one of them holding six, **When** `prompt_block` and `status` run, **Then** the prompt shows one `on it:` line per other session and `status` flags the six-claim session `over 5` (spec § Validation V3)
- **Given** an unnamed window (no `CLAUDE_AGENT`, no binding), **When** `prompt_block` runs, **Then** its first line is the no-agent-name line; with a name set, that line is absent (spec § The delta D6)
- **Given** the hub-sized inbox and a 500-row ledger, **When** `prompt_block` is timed, **Then** it returns in under 0.5 s (spec § Validation V4)

## Context Files
- .windsurf/rules/core/10-python.md
- scripts/work.py
- tests/test_work.py
- tests/test_work_claims.py
