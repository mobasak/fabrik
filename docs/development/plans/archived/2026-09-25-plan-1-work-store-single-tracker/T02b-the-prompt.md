# T02b — The prompt block: obligations, every other session's claims, the unnamed-window line

## Scope

Implements spec § The delta D1, D4 and D6 in `scripts/work.py`'s `prompt_block` (`:3067-3103`) — still
read-only, no lock — consuming T02a's `obligations(root) -> list[str]` and its `kind: next` exclusion.

1. **`prompt_block`** (D1, D4, D6; `:3067-3103`) — in order: the unnamed-window line when
   `_agent_name()` is empty (`work: this window has no agent name — owned items cannot reach it; run python3 scripts/whoami_agent.py --as <name>`);
   the obligation lines of T02a's `obligations(root)`, each prefixed `work: `; the awaiting lines (unchanged); this session's `your claim`
   lines (unchanged); then one line per OTHER session holding live claims,
   `work: on it: <session[:8]> (<agent or unnamed>) — W-…, W-…` (ids sorted, the line clipped at `LINE_MAX`);
   then the ready count (now excluding `kind: next`). Every live claim in the repo therefore appears once.
   Still read-only, no lock; V4's budget: under 0.5 s on the hub's inbox and ledger — inside the prompt
   path's 3 s store budget (`scripts/thread_anchor.py:199`).
2. **The pinned tests move with the change, never weakened.** `tests/test_thread_anchor.py`'s `_env`
   (`:215`) sets `FABRIK_MAIL_ROOT` and `COMMAND_RUN_DIR` under `tmp_path`. The unnamed-window line changes
   five existing assertions, each updated here: `tests/test_work_claims.py:653` (`prompt_block == ""` on an
   empty store — its env now names the window); `tests/test_work_claims.py:663-664` (`a not in other` for
   `prompt_block(repo, "S2")` while S1 claims `a` — now `a` appears in S2's block only on S1's `on it:`
   line, never on a `your claim` line); and the three `tests/test_thread_anchor.py` tests that read
   the awaiting line as the first line — `test_awaiting_items_from_other_sessions_print_first_unfolded[prompt|compact]`
   (`:1212-1214`) and `test_the_rescue_makes_a_bounded_number_of_store_calls` (`:1407`) — which set
   `CLAUDE_AGENT` in their env so the window is named and their assertions stand as written.

DO-NOT: `obligations`, `ready`, `status` (T02a); `on_harvest`/`_set_next` (T05a); the register or any `thread_anchor.py` logic (T05b).

Depends: T02a
Parallel: ⛓️
Complexity: complex
Gate: .venv/bin/python -m pytest tests/test_work_claims.py tests/test_work_prompt.py tests/test_thread_anchor.py -q
Docs: `docs/reference/work-tracking.md` § The view is T07b's

## Touches
- scripts/work.py — PRIMARY PATH
- tests/test_work_claims.py
- tests/test_work_prompt.py
- tests/test_thread_anchor.py

## Behavior Contract
- **Given** a store with an `ack: required` mail, live claims held by this session and by two other sessions, and an open `kind: next` item, **When** `prompt_block` runs, **Then** it shows the mail line, this session's `your claim` lines, one `on it:` line per other session, and a ready count that leaves the `next` item out (spec § Validation V3)
- **Given** an unnamed window (no `CLAUDE_AGENT`, no binding), **When** `prompt_block` runs on an empty store, **Then** it returns exactly the no-agent-name line; with a name set, that line is absent and the empty store's block is `""` (spec § The delta D6)
- **Given** the hub-sized inbox and a 500-row ledger, **When** `prompt_block` is timed, **Then** it returns in under 0.5 s (spec § Validation V4)

## Context Files
- .windsurf/rules/core/10-python.md
- scripts/work.py
- tests/test_work_claims.py
- tests/test_thread_anchor.py
