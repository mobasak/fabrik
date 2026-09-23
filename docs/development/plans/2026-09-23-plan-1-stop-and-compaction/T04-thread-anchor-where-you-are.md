# T04 — `thread_anchor.py`: WHERE YOU ARE on compact, the DECISION harvest and clear, the 72 h fold

## Scope
Implements spec § C3 in `scripts/thread_anchor.py`. `line --hook` already parses the hook payload (`main`, `:241-251`) and already runs on every SessionStart source through the existing empty-matcher entry in `.claude/settings.json`, so no settings entry is added. On `source=compact` it prints `## ⏮ WHERE YOU ARE` INSTEAD of its usual block, with the five items spec § C3 names. Folds in A-O41 (the DECISION clear skips ONLY built-in slash commands — `/compact`, `/context`, `/cost`, `/model`, `/autocompact`, `/clear`, `/help`; a custom command or plain text clears it) and A-O42 (a fixture pins that rule). DO-NOT: touch the hook (T03's parser and helpers are imported unchanged); add a settings entry; delete any anchor.

Depends: T03
Parallel: ⛓️
Complexity: native
Gate: uv run pytest tests/test_thread_anchor.py tests/test_thread_anchor_flush_race.py -q
Docs: CHANGELOG (Deltas) — the docs row is T05's

## Touches
- scripts/thread_anchor.py — PRIMARY PATH
- tests/test_thread_anchor.py

## Behavior Contract
- **Given** a compaction in a session with a live run, an accepted DECISION block, and commits by two sessions, **When** SessionStart fires with `source=compact`, **Then** WHERE YOU ARE shows the run, the last NEXT, the open block, and only this session's unpushed commits and dirty files (spec § C3)
- **Given** an open DECISION block, **When** the operator submits a plain answer, a built-in slash command, or a custom command, **Then** the plain answer and the custom command clear it and the built-in does not (spec § C3; A-O41, A-O42)
- **Given** anchors aged 71 h and 73 h, **When** `line` renders, **Then** the 71 h anchor prints in full and the 73 h one is folded into the one-line summary, and nothing is deleted (spec § C3 item 5)

## Steps (the coder's order)
1. Red first, in `tests/test_thread_anchor.py` (state under a scratch `THREAD_ANCHOR_DIR`, the run record under a scratch `COMMAND_RUN_DIR`, a throwaway git repo with an upstream): `test_where_block_lists_only_this_sessions_commits` (the T03 → T04 seam: two sessions' commits, only the one whose files the transcript authored appears); `test_a_refused_block_is_never_stored` (the T03 → T04 seam: `harvest` without `--decision-ok` stores no block); a live `running` record appears with phase, round, terminal and surface, and a stopped one does not; the block shows until a plain UserPromptSubmit and survives one whose `prompt` is `/compact`, `/context` or `/model`, but not `/fabrik-deploy prod`; the prompt-time re-harvest of the previous message never re-stores a cleared block; 71 h vs 73 h anchors. Watch each FAIL.
2. `cmd_harvest` (`:165`) gains `decision_ok: bool`: with it, the message's last DECISION block is stored as `state["decision"]` with its timestamp; without it, nothing is stored.
3. `main` (`:225`): read `source` and `hook_event_name` and `prompt` from the payload; on `UserPromptSubmit` whose `prompt` does not start with one of the built-in commands listed above, clear `state["decision"]`; the prompt-time re-harvest (`:273-278`) never passes `decision_ok`.
4. `cmd_line` (`:187`): on `source=compact`, render WHERE YOU ARE — (1) the live run record read via the hook's `_run_record` (`final_gate_stop.py:519`); (2) `last_next`; (3) `state["decision"]` if open; (4) this session's unpushed commits and dirty files — authored set from `_session_files` (`:346`) floored by `_baseline_floor` (`:1179`) and `_this_sessions_edits` (`:1224`), the unpushed count from `_ahead_of_upstream` (`:677`), dirty files as `git status --porcelain` filtered to that set, 10 of each, 2 s timeouts; (5) anchors, folded. Import the hook module by path with `importlib` from the same repo; any import or call failure omits that item and writes one line to stderr.
5. The fold: anchors older than 72 h print as one line `N older thread(s), oldest <age> — close with thread_anchor.py done --match <substr>`; state keeps them.
6. Gate green; `uv run ruff check scripts/thread_anchor.py`; CHANGELOG line into the Deltas block.
7. `/fabrik-review` on this ticket's changed surface, partitioned by file (Opus on `thread_anchor.py`), to a coverage-adjudicated exit; every finding FIXED or REFUTED.
8. Commit with explicit pathspecs + provenance trailers (`Agent-Role: subagent`, `Agent-Task: T04`).

## Context Files
- .windsurf/rules/core/10-python.md
- .windsurf/rules/core/45-testing-strategy.md
- scripts/thread_anchor.py
- tests/test_thread_anchor.py
- tests/test_thread_anchor_flush_race.py
- .claude/hooks/final_gate_stop.py
- docs/superpowers/specs/2026-09-23-stop-and-compaction-enforcement-design.md
