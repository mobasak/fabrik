# T02 — `command_feedback_report.py --queue fabrik-task`: the two series and the adoption share

## Scope
Implements spec § Validation V4 and § Personas (the `command_feedback_report.py --queue fabrik-task` reader): the existing `queue()` header gains the `oversized_mini` rate (numeric-first-token rows, count ≥ 1 over all numeric rows, excluding `upgrade: sync` rows), the `unmeasurable` share, the `upgrade` rate, and the ADOPTION SHARE (`/fabrik-task` closes over `/fabrik-task` + STANDALONE `/fabrik-review-scoped` closes, a review-scoped row nested when another command's row with the same `sid` satisfies `o.ts − o.wall_s ≤ r.ts ≤ o.ts`), restating nothing V4 already says; ~15 lines; no new reader, no new flag. DO-NOT: change any other command's header (byte-identical); add a ledger field; touch `command_run.py`.

Depends: T01b
Parallel: ⛓️
Complexity: simple
Gate: uv run pytest tests/test_command_feedback_report.py -q -k "queue or fabrik_task or adoption"
Docs: CHANGELOG (Deltas) · none other

## Touches
- scripts/command_feedback_report.py — PRIMARY PATH
- tests/test_command_feedback_report.py

## Behavior Contract
- **Given** a ledger with `fabrik-task` rows carrying `oversized_mini`/`upgrade` and review-scoped rows some of which are nested (same `sid`, `o.ts − o.wall_s ≤ r.ts ≤ o.ts`), **When** `--queue fabrik-task` renders, **Then** the header carries the `oversized_mini` rate over numeric rows excluding `upgrade: sync` rows, the `unmeasurable` share, the `upgrade` rate and the adoption share with nested rows excluded (scripts/command_feedback_report.py:1106, :1139-1142; spec § Validation V4)
- **Given** `--queue <any other command>`, **When** it renders, **Then** the header is byte-identical to today's (scripts/command_feedback_report.py:1139-1142)

## Steps (the coder's order)
1. Red first: in `tests/test_command_feedback_report.py`, using the file's existing synthetic-ledger fixture, using `_row(cmd, wall, rounds, change, **kw)` (`:22-39`), `_write` (`:42-43`) and `_run(... --ledger <path>)` (`:46-52`) exactly as `test_queue_prints_one_commands_verdicts_newest_first_with_their_ts` (`:1493-1515`) does, add (a) a `fabrik-task` ledger with rows `oversized_mini: 0`, `2 · paths=a,b · commit=abc`, `unmeasurable=no-commit`, one `upgrade: sync` row, plus three review-scoped rows of which one is nested under a `fabrik-execute-plan` row by the rule — assert the header's four numbers; (b) the seam test — a row written by the REAL `scripts/command_run.py done --commit …` in a throwaway `COMMAND_RUN_DIR` (the ledger lands at its parent's `command-feedback.jsonl`, `command_run.py:1621-1622`) is read by `--queue fabrik-task --ledger <that file>` and counted; (c) `--queue fabrik-review` header unchanged; watch them FAIL.
2. In `queue()` (`scripts/command_feedback_report.py:1106`), after the existing `head` f-string (`:1138-1144`; the filters at `:1119-1129`), when `command == "fabrik-task"`: compute the four numbers from `rows` (the whole window the function already receives) and append one line `series: oversized_mini <k>/<n> (<pct>%) · unmeasurable <u>/<total> · upgrade <g>/<total> · adoption <t>/<t + standalone review-scoped>` — first token of `oversized_mini` decides the bucket; rows whose `upgrade` is `sync` leave the rate's denominator.
3. Gate green; `ruff format --check` + `ruff check`.
4. `python scripts/enforcement/check_doc_sync.py`; CHANGELOG line into the Deltas block.
5. `/fabrik-review` on this ticket's changed surface to a coverage-adjudicated exit (`dispatch_headroom.py --units 1`, three seats on different angles: the arithmetic, the nesting rule, the byte-identical header); every finding FIXED or REFUTED.
6. Commit with explicit pathspecs + provenance trailers (`Agent-Role: subagent`, `Agent-Task: T02`).

## Context Files
- .windsurf/rules/core/10-python.md
- scripts/command_feedback_report.py
- tests/test_command_feedback_report.py
