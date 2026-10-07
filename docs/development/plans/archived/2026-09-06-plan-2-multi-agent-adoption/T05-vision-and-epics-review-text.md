# T05 — `/fabrik-vision` EXISTING reads the two work stores; `/fabrik-epics-review` writes the merge-owner row

## Scope
Two command sources (rendered box-wide by the merge owner: render → `--check` → commit from the main checkout, never from a worktree). (1) `commands/_sources/fabrik-vision.md` Phase 0's "EXISTING mode only" read list (`fabrik-vision.md:63-66`) gains `docs/development/PLANS.md` (its `AUTO-GENERATED:PLANS` block — open rows: Status not EXECUTED/COMPLETE — and the `<!-- Merge owner: … -->` header) and `docs/STRATEGIC_BACKLOG.md`; Phase 2's Scale Assessment / epic-seed text gains one paragraph: every open plan and every backlog row is a candidate line, carried with its `[name]` tag / Owner so an epic cut from a `[beta]` row is written with `owner: beta` (the operator's ruling D-154 cited, not literature). (2) `commands/_sources/fabrik-epics-review.md` § Step 1.5 (`fabrik-epics-review.md:138`) gains one sentence: after `--assign`, when `python3 scripts/decisions.py --merge-owner .` prints `UNDECLARED`, the review mints the `MERGE OWNER: <first name>` row (next id via `--next-id`) in the same change, so the epic path and `--adopt` converge on one declaration. ~14 lines of text in total; the 1024-char skill description cap is untouched (body text only). DO-NOT: touch any other command source; render from a worktree; change either command's frontmatter.

Depends: —
Parallel: ⚡
Complexity: native
Gate: python3 commands/assemble_commands.py --check && python3 scripts/enforcement/check_command_corpus.py
Docs: CHANGELOG (Deltas) · INDEX row for `tests/test_vision_reads_work_stores.py` (Deltas)

## Touches
- commands/_sources/fabrik-vision.md — PRIMARY PATH
- commands/_sources/fabrik-epics-review.md
- tests/test_vision_reads_work_stores.py

## Behavior Contract
- **Given** the vision source, **When** `tests/test_vision_reads_work_stores.py` greps its EXISTING read list, **Then** `docs/development/PLANS.md` and `docs/STRATEGIC_BACKLOG.md` both appear between the `EXISTING mode only` bullet and the fabrik-lib bullet, and the epic-seed paragraph names `owner:` inheritance from a `[name]` tag (commands/_sources/fabrik-vision.md:63)
- **Given** the epics-review source, **When** the test greps § Step 1.5, **Then** it names `decisions.py --merge-owner` and the `MERGE OWNER:` row mint (commands/_sources/fabrik-epics-review.md:138)
- **Given** both sources edited, **When** `assemble_commands.py --check` and `check_command_corpus.py` run from the main checkout, **Then** both exit 0 and every composed skill description stays ≤ 1024 chars (commands/assemble_commands.py:1)

## Context Files
- .windsurf/rules/core/40-documentation.md
- commands/_sources/fabrik-vision.md
- commands/_sources/fabrik-epics-review.md
- commands/assemble_commands.py
- docs/superpowers/specs/2026-09-06-multi-agent-adoption-design.md
