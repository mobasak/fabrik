# T01a — `command_run.py`: SIZE at `start` (`--file`/`--declare`, the inventory) and `step --design`

## Scope
Implements spec § Chosen approach, Phase 0 (the SIZE inventory, the refusal enumeration, the persisted `declared`, the `RECORD:` print, the stdlib regex extraction with its fail-open arm) and Phase 2 (the `design` record field via `step --design`), restating nothing those sections already say. Every new behaviour is scoped to `--command fabrik-task`; every other command's `start` and `step` output is byte-identical to today's. DO-NOT: touch `_close`, the ledger row or any close verb (T01b); add any import outside the stdlib (`scripts/command_run.py:46-60`); read `CLAUDE.md` (T01b's exclusion parse); change `skill_router.py`.

Depends: —
Parallel: ⚡
Complexity: native
Gate: uv run pytest tests/test_command_run_fabrik_task.py -q -k "start or step or declare or design or sync_test"
Docs: CHANGELOG (Deltas) · `docs/reference/command-run-protocol.md` § CLI gains the `--file`/`--declare`/`--design` lines — owned by T03, cited here

## Touches
- scripts/command_run.py — PRIMARY PATH
- tests/test_command_run_fabrik_task.py

## Behavior Contract
- **Given** `start --command fabrik-task` with no `--file`, **When** it runs, **Then** it exits 1 with `REFUSED — fabrik-task: missing --file` and no record opens (scripts/command_run.py:2360-2368; spec § Chosen approach, Phase 0)
- **Given** `start --command fabrik-review --file a.py`, **When** it runs, **Then** it exits 1 with `REFUSED — --file/--declare belong to --command fabrik-task` and every other command's start output is byte-identical to today's (scripts/command_run.py:2360-2368; spec § Chosen approach, Phase 0)
- **Given** a declared path that matches the governance-sync regex read from the hub's `.pre-commit-config.yaml` `- id: governance-sync` block, **When** `start` runs with `mechanism=no`, **Then** it exits 1 with `REFUSED — fabrik-task: sync → right-now + /fabrik-review`; with `mechanism=yes` also declared the lane named is `/fabrik-spec` (scripts/governance_sync_postcommit.sh:28-30; .pre-commit-config.yaml:149-155; spec § The decision rule)
- **Given** a declared path that is tracked, present and modified, or present and untracked, **When** `start` runs, **Then** it exits 1 with the dirty-at-start message; an absent declared path starts (scripts/command_run.py:2583, :2623-2663; spec § Chosen approach, Phase 0)
- **Given** a valid declaration, **When** `start` succeeds, **Then** the record carries `declared` with the seven keys and `sha`, and stdout carries `RECORD: <started_at>` after the pinned line (scripts/command_run.py:2636, :2682; spec § Chosen approach, Phase 0)
- **Given** the stdlib extraction of the `files:` scalar, **When** compared to PyYAML's read of the same file, **Then** they are equal on the live file, and an absent or empty scalar yields `sync_test: unavailable`, never an empty regex (scripts/governance_sync_postcommit.sh:44; spec § Chosen approach, Phase 0)
- **Given** `step --phase 2 --design <path>` on a `fabrik-task` record, **When** the file is ≤ 2,000 characters, **Then** `rec["design"]` holds its text and no later `step` overwrites it; over 2,000 it is REFUSED (scripts/command_run.py:2370-2377, :1602; spec § Chosen approach, Phase 2)
- **Given** a `fabrik-task` record in a repo with no commits, **When** `start` runs, **Then** the record carries `sha: unavailable` and the dirty check is skipped (scripts/command_run.py:2636; spec § Chosen approach, Phase 0)

## Steps (the coder's order)
1. Toolchain preflight: `uv --version` and `.venv/bin/python -c "import yaml"` (PyYAML is present in the hub venv for the GRADER only — `command_run.py` never imports it).
2. Red first: write `tests/test_command_run_fabrik_task.py` with the `_cr`-shaped harness copied from `tests/test_command_run.py:43-80` (a `COMMAND_RUN_DIR` under `tmp_path`, `KAIZEN_EVENTS_DIR` beside it, `CLAUDE_SESSION_ID`, the auto-injected `--feedback`) and the git-repo fixture shape of `:497-510`; run it and watch the eight tests FAIL for the right reason (unknown `--file` flag; no `RECORD:` line; no `design` key).
3. `start` parser (`scripts/command_run.py:2360-2368`): add `--file` (`action="append"`, `metavar="PATH"`) and `--declare` (`k=v,…`); inline in `_mutate` where `start` is handled (`:2583`), BEFORE the record literal at `:2623` is built: if `args.command != "fabrik-task"` and either flag is present → print the cross-command refusal, `return 1`; if `fabrik-task`: the guard order — required flags (each gap its own line) → path validity (normalise to repo-root-relative against `_repo_root()`; outside-repo and directory refusals) → dirty-at-start (`git diff --quiet HEAD -- <p>` non-zero with the file present, or present-and-untracked; skipped with `sha: unavailable` when `git rev-parse -q --verify HEAD` is rc 1) → the two lane tests (`len(files) > 3`; the sync regex) and the five declared answers evaluated together with the spec-chain precedence (`mechanism`/`oneway`/`tradeoffs`/fourth file → `/fabrik-spec` even when sync or `heavy` also tripped; sync or `heavy=yes` alone → `right-now + /fabrik-review`; `decision=no` alone → `right-now + /fabrik-review-scoped`), the parametrised lane message `REFUSED — fabrik-task: <test> → <lane>`.
4. The sync regex: a stdlib function that opens `/opt/fabrik/.pre-commit-config.yaml` by absolute path, locates the `- id: governance-sync` block and its single-quoted `files:` scalar (the FIFTH `files:` in the file — anchored by the id, never the first match), unescapes `''`, compiles it with `re.X`; any failure (unreadable, absent, empty scalar) → `declared["sync_test"] = "unavailable"` and the test is skipped, never an empty regex.
5. Persist `declared: {files, decision, heavy, mechanism, oneway, tradeoffs, sha, sync_test}` in the record literal beside `started_epoch` (`:2636`); after the only stdout print `print(pinned_line(new))` (`:2682`), print `RECORD: <started_at>` — only under `fabrik-task`; every refusal uses the close-time shape (`:3369-3371`: rc 1, `[command_run] ` on stderr, the bare message on stdout).
6. `step` parser (`:2370-2377`): add `--design PATH`; in the inline `step` handler (`:2708`), after `rec["phase_title"] = args.title` (`:2789`) and before `save` (`:2792`), on a `fabrik-task` record, read the file, refuse over `_LEDGER_FIELD_CAP` (`:1602`) with `REFUSED — fabrik-task: --design is <n> chars, the cap is 2000`, else set `rec["design"]` once (a later `step` never overwrites a set value).
7. Run the gate green; `ruff format --check` and `ruff check` on the two files; the equality grader: a test that reads the scalar both ways (stdlib vs `yaml.safe_load`) on the live hub file and asserts equality (678 chars today).
8. `python scripts/enforcement/check_doc_sync.py`; CHANGELOG line into the Deltas block (orchestrator-applied).
9. `/fabrik-review` on this ticket's changed surface to a coverage-adjudicated exit (partitioned by file: Opus on `scripts/command_run.py`, Sonnet on the test file — `dispatch_headroom.py --slices opus=1,sonnet=1`, stamped first); every finding FIXED or REFUTED; the fixing pass is never the last look.
10. Commit with explicit pathspecs + provenance trailers (`Agent-Role: subagent`, `Agent-Task: T01a`).

## Context Files
- .windsurf/rules/core/10-python.md
- .windsurf/rules/core/45-testing-strategy.md
- scripts/command_run.py
