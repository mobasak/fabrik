# T01b — `command_run.py`: `--commit` on the close verbs, the own-commit re-measure, the two row fields

## Scope
Implements spec § Chosen approach, Phase 5 — the SIX INVARIANTS (i)–(vi), the three close-time refusals, the persisted-SHA close line — and UPGRADE's `upgrade` keying, restating nothing those paragraphs already say; this ticket's Behavior Contract IS the operator's Phase A acceptance criteria (D-293). Scoped to records whose `command` is `fabrik-task`; every other command's close and ledger row byte-identical to today's. DO-NOT: touch `start`/`step` (T01a); read the working tree's mtimes (the deleted leg, spec § Chosen approach, Phase 5); add a third row field (D-290); import PyYAML or read `.pre-commit-config.yaml` with anything but T01a's stdlib extractor.

Depends: T01a
Parallel: ⛓️
Complexity: native
Gate: uv run pytest tests/test_command_run_fabrik_task.py -q -k "commit or remeasure or oversized or upgrade or matrix or close"
Docs: CHANGELOG (Deltas) · `docs/reference/command-run-protocol.md` § CLI gains the `--commit` line and the two row fields — owned by T03, cited here

## Touches
- scripts/command_run.py — PRIMARY PATH
- tests/test_command_run_fabrik_task.py

## Behavior Contract
- **Given** a `fabrik-task` record with `declared.files = [a]` and a commit that changed `a` and added `b`, **When** `done --commit <that sha>` runs, **Then** the ledger row carries `oversized_mini: 1 · paths=b · commit=<sha>` (scripts/command_run.py:3121, :3655-3676; spec § Chosen approach, Phase 5 (iii)–(vi))
- **Given** the same record and a commit that changed only `a`, `CHANGELOG.md` and `docs/FEATURES.md`, **When** `done --commit` runs, **Then** the row carries `oversized_mini: 0` (the Doc Sync Matrix destinations parsed from `CLAUDE.md` § Doc Sync Matrix at close time plus `docs/CAPABILITIES.md` are excluded) (CLAUDE.md § Doc Sync Matrix; spec § Chosen approach, Phase 5 (iv))
- **Given** a commit that renames a declared file into `scripts/enforcement/`, **When** `done --commit` runs, **Then** the row counts the destination as a sync hit (scripts/command_run.py:3121; spec § Chosen approach, Phase 5 (v))
- **Given** `--commit` that is empty, resolves to a merge, or is dated before `started_at`, **When** `done` runs, **Then** it is REFUSED with the matching one of the three close-time messages and the record stays `running` (scripts/command_run.py:3360-3371; spec § Chosen approach, Phase 5 (ii))
- **Given** `handoff --reason "UPGRADE: mechanism"` or `done --evidence "UPGRADE: sync — …"` on a `fabrik-task` record, **When** the close runs, **Then** the row carries `upgrade: mechanism` / `upgrade: sync`; a `/fabrik-review` close writes neither field (scripts/command_run.py:3074, :3655-3676; spec § Chosen approach, UPGRADE)
- **Given** the parser of `CLAUDE.md` § Doc Sync Matrix, **When** run on the live file, **Then** it reads every table row (22 today) and yields 25 paths plus the two prefixes (CLAUDE.md § Doc Sync Matrix; spec § Chosen approach, Phase 5 (iv))

## Steps (the coder's order)
1. Red first: extend `tests/test_command_run_fabrik_task.py` (T01a's harness) with the six graders above; each builds a throwaway repo (`git init -b main`, commits with `-c user.email -c user.name`), runs the real `start --command fabrik-task --file a …` through the harness, commits the shapes the row asserts, and closes with `done --commit "$(git rev-parse HEAD)"` — plus one refusal test per close-time message; run them and watch them FAIL for the right reason (unknown `--commit`; no `oversized_mini` key).
2. Parsers: add `--commit SHA` to `done` (`scripts/command_run.py:2440-2456`), `handoff` (`:2464-2477`) and `blocked` (`:2485-2496`) — required on `done` only when the live record's command is `fabrik-task` (checked in `_close`, not argparse, because argparse cannot see the record); refused with `REFUSED — --commit belongs to --command fabrik-task` on any other record.
3. In `_close` (`:3121`), after the `--feedback` refusal (`:3360-3371`) and the verb branch (`:3500-3511`), before `_row` is built (`:3655`), the re-measure (git calls in the `:3215-3229` subprocess shape, `cwd=rec["repo_root"]`), ONLY when `rec["command"] == "fabrik-task"`: (ii) resolve `--commit` — `git cat-file -t` is `commit`, parent count ≤ 1 (`git log -1 --format=%p`), committer date (`%ct`) ≥ `rec["started_epoch"]`; else the refusal (`REFUSED — fabrik-task: --commit <v> is not this run's commit`; an empty value its own `… --commit is empty — re-read the capture file written beside the commit`); `blocked`/`handoff` without `--commit` → `oversized_mini: unmeasurable=no-commit`, never a refusal; (iii) `git diff --name-status -M <c>~1 <c>` (a root commit against the empty tree `4b825dc642cb6eb9a060e54bf8d69288fbee4904`); (iv) EXCL = the Doc Sync Matrix's *Update* column parsed from `<repo_root>/CLAUDE.md` between `## Doc Sync Matrix` and the next `## ` (every backticked `.md`/`.example`/`.sql` token; `<name>.md` entries as prefixes) + the five ledger files + `docs/CAPABILITIES.md` (a named constant with its own grader asserting the file exists); the matrix is read from the record's `repo_root`, and a repo whose `CLAUDE.md` lacks the section falls back to the five ledger files + the constant alone — stated in the source's docstring and graded, never a fourth `unmeasurable` reason; (v) the count = |paths ∉ declared ∪ EXCL (an `R`/`C` destination inheriting its source's membership) ∪ every path, excluded or not, source or destination, matching T01a's sync regex| — deduplicated; a `--evidence` beginning `UPGRADE: sync` with zero sync hits in the commit → `REFUSED — fabrik-task: --evidence claims UPGRADE: sync but the commit has no sync-regex hit`; (vi) the field: `0` · `<n> · paths=<first three> · commit=<sha>` · `unmeasurable=<no-commit|no-git|sync_test-unavailable>` (`no-git` when git itself is unavailable; `sync_test-unavailable` when `declared.sync_test == "unavailable"` and the close's re-run of T01a's extractor still fails — the membership arm still runs and a count still wins), capped by `_cap_field` (`:1605-1606`).
4. `upgrade`: on any `fabrik-task` close, the token after `UPGRADE:` up to the first whitespace in `args.reason` (`handoff`/`blocked`) or `args.evidence` (`done`); absent otherwise.
5. Write both keys into `_row` at `:3674-3675` (after `cost_usd`, before `**_tok`) under the `fabrik-task` branch only; mirror them into the `run_close` kaizen event dict (`:3604-3623`) so the event stream carries what the row carries; the append at `:3705-3712` needs no change.
6. Run the gate green; `ruff format --check` + `ruff check`; the negative grader: a `/fabrik-review` record's close produces a row without either key and byte-identical stdout.
7. `python scripts/enforcement/check_doc_sync.py`; CHANGELOG line into the Deltas block.
8. `/fabrik-review` on this ticket's changed surface to a coverage-adjudicated exit (partitioned by file: Opus on `scripts/command_run.py`, Sonnet on the test file — `dispatch_headroom.py --slices opus=1,sonnet=1`, stamped first); the shared-tree hazards (a sibling's commit in the window, the rebase) are the review's named classes; every finding FIXED or REFUTED.
9. Commit with explicit pathspecs + provenance trailers (`Agent-Role: subagent`, `Agent-Task: T01b`).

## Context Files
- .windsurf/rules/core/10-python.md
- .windsurf/rules/core/45-testing-strategy.md
- scripts/command_run.py
