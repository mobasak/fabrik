# T03 — the command source `commands/_sources/fabrik-task.md`, its render, and the docs rows

## Scope
Implements spec § Chosen approach (the six phases as the command's text, pointing at run-record, close-feedback, the FIX DIRECTIVE, `/fabrik-review-scoped` and the D-row rule, restating none), § Constraints C1/C2 (≤ 8,847 B; the only `{{include:}}` is `run-record`; `close-feedback` auto-appended) and § Documentation landing sites (`docs/CAPABILITIES.md` bullet, `docs/reference/command-run-protocol.md` § CLI lines for `--file`/`--declare`, `--design`, `--commit` and the two row fields; the `INDEX.md` row is orchestrator-applied). The frontmatter carries the TRIGGER/SKIP/Stage grammar the corpus check grades; the description names `/fabrik-spec`'s triggers in its SKIP clause (spec § Awareness, surface 2 is RESOLVED-NEGATIVE — no router entry). DO-NOT: edit `.claude/hooks/skill_router.py`; include `term-coverage`/`term-edit`; edit either CLAUDE.md (T04a/T04b); render from a worktree.

Depends: T01b
Parallel: ⚡
Complexity: native
Gate: python commands/assemble_commands.py --check && .venv/bin/python scripts/enforcement/check_command_corpus.py && uv run pytest tests/test_fabrik_task_source.py -q
Docs: `docs/CAPABILITIES.md` (the command's bullet) · `docs/reference/command-run-protocol.md` § CLI · CHANGELOG (Deltas) · `INDEX.md` row (Deltas, orchestrator-applied)

## Touches
- commands/_sources/fabrik-task.md — PRIMARY PATH
- tests/test_fabrik_task_source.py
- docs/CAPABILITIES.md
- docs/reference/command-run-protocol.md

## Behavior Contract
- **Given** `commands/_sources/fabrik-task.md`, **When** the size/include grader runs, **Then** it is ≤ 8,847 bytes and its only `{{include:}}` is `run-record` (commands/assemble_commands.py:1170, :1184; spec § Constraints C2)
- **Given** the rendered corpus, **When** `assemble_commands.py --check` and `check_command_corpus.py` run, **Then** both are green and `~/.claude/commands/fabrik-task.md` exists (commands/assemble_commands.py:1170)
- **Given** every `command_run.py …` line the source carries, **When** parsed by the real parser, **Then** none is refused (scripts/command_run.py:2360-2496; spec § Chosen approach)

## Steps (the coder's order)
1. Red first: `tests/test_fabrik_task_source.py` with three graders — byte size ≤ 8,847 and includes = {`run-record`}; the rendered file exists after `assemble_commands.py --check`'s temp render (assert on the source's frontmatter keys the corpus check requires: `description` with `TRIGGER —` and `Stage:`, `argument-hint`); every fenced `python3 scripts/command_run.py …` line in the source is accepted by `scripts/command_run.py`'s argparse under `COMMAND_RUN_DIR=<tmp>` (a refused flag fails). Watch them FAIL (no source file).
2. Write the source at ≤ ~85 lines: frontmatter (`description:` with TRIGGER — EN "one small change with one decision", "fix + decide"; TR "küçük bir değişiklik, tek karar"; SKIP → the six tests that route elsewhere; `Stage: utility`), then `{{include:run-record}}`, then the six phases as ordered steps with the exact runnable lines: `start --command fabrik-task --phases 5 --terminal … --surface … --file … --declare decision=,heavy=,mechanism=,oneway=,tradeoffs=`; phase 1 `select_rules.py --changed <files>`; phase 2 the six fields into `<scratchpad>/fabrik-task/<sid>/<started_at>/design.md` and `step --phase 2 --design <that path>`; phase 3 the plan-lock read (`git diff --name-status -M <lock.baseline_commit> HEAD`, both paths of a rename) and the red-first grader; phase 4 `/fabrik-review-scoped` with the three seat questions; phase 5 the matrix rows, D-row (the `&#124;` rule), CHANGELOG, LESSONS, the gate, the commit + `mkdir -p … && git rev-parse -q --verify HEAD > …/commit.sha || exit 1`, the push ladder, `done --command fabrik-task --commit "$(cat …/commit.sha)" --evidence … --feedback …`; UPGRADE as the one-way ratchet with its two close shapes; the D-253 cobra note in the source's own docstring (the twelve cobras by number, pointing at the spec for their text). Point at, never restate: run-record, close-feedback, the FIX DIRECTIVE, `/fabrik-review-scoped`, the D-row rule.
3. Register the command's NEXT line in the assembler's `NEXT` dict (`commands/assemble_commands.py:50-88`; an absent entry falls back to "(no defined successor …)" at `:103`, so the entry is a choice, and this lane's is "resume what you were doing — a gate-shaped lane; on UPGRADE `/fabrik-spec` seeded with design.md"); the source must satisfy `check_command_corpus.py`'s predicates 5 and 7 (every command opens a run record, `_RUN_START_RE` `:96-98`; every printed close line carries `--feedback`, `_CLOSE_CMD_RE` `:121-123`); render from the MAIN checkout: `python commands/assemble_commands.py` → `--check` → `check_command_corpus.py`; `check_corpus_weight.py --check` will WARN on the `commands/_sources` growth — the commit message cites D-293 (the growth's D-row).
4. `docs/CAPABILITIES.md`: the `fabrik-task` bullet in the alphabetical command block — after `fabrik-spec-review` (`:392`) and before `fabrik-ui-design` (`:393`), in the `- [name](../CLAUDE.md) (owner: infra): <description>` shape of `:391`; `docs/reference/command-run-protocol.md` § CLI (`:48-61`): extend the `start` row (`:52`), the `step` row (`:53`) and the `done` row (`:56`) with `--file/--declare`, `--design` and `--commit`, plus one paragraph on the two row fields beside the existing `--surface` text (`:208-224`). No `INDEX.md` row is gate-required for a `commands/_sources/` file (`check_doc_index.py:7-9`, `:330` — `docs/`-prefixed links only; most sources carry none); the Deltas block adds one anyway beside `fabrik-rivals.md`'s (`INDEX.md:1489`).
5. Gate green; `python scripts/enforcement/check_doc_sync.py`; CHANGELOG + INDEX rows into the Deltas block.
6. `/fabrik-review` on this ticket's changed surface to a coverage-adjudicated exit (`dispatch_headroom.py --units 2` — the source's executability, the docs' truth — three seats minimum); every finding FIXED or REFUTED.
7. Commit with explicit pathspecs + provenance trailers (`Agent-Role: subagent`, `Agent-Task: T03`); the render lands in the same commit (render → `--check` → commit).

## Context Files
- .windsurf/rules/core/40-documentation.md
- commands/_fragments/run-record.md
- commands/_sources/fabrik-review-scoped.md
- commands/assemble_commands.py
- docs/CAPABILITIES.md
- docs/reference/command-run-protocol.md
