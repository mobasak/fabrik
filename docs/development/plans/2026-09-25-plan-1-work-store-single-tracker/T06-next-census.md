# T06 — next_census.py: the NEXT-line measurement as one script

## Scope

Implements spec § Validation V5 and the three measurements of spec § Why this exists as one hub
sysadmin script, `scripts/sysadmin/next_census.py` (new; the spec's § Review — Pass Ledger records that
it does not exist yet). It reads Claude Code transcripts (`*.jsonl`, one per session, under
`<root>/<project-dir>/`) modified within the last `--since` days and prints, as plain lines on stdout:

1. **Classes.** Every assistant text block's `NEXT:` lines (a line whose text starts `NEXT:`, the rule
   the 2026-09-25 measurement used), classified in this order: `names-item` (a `W-` + 8 lowercase hex
   whole word — `scripts/work.py:88`'s `_ITEM_REF_RE`), `none` (value starts `none`), `operator-decision`
   (starts `operator decision`), `blocked` (starts `BLOCKED`), `free-text`. One line with each count, the
   total and the session denominator: `next: <total> lines over <n> sessions — names-item <a> · none <b> · operator-decision <c> · blocked <d> · free-text <e>`.
2. **Distinct.** The count of distinct `free-text` values: `distinct free-text: <n>`.
3. **Sessions per repo.** Sessions whose transcript ended at least one turn — the LAST `NEXT:` of an
   assistant message — on a `free-text` value that `thread_anchor._is_anchor` accepts
   (`scripts/thread_anchor.py:465`, imported by path from `Path(__file__).resolve().parents[1]`, the
   way `scripts/thread_anchor.py:245-270` loads `work.py`): `sessions with an accepted free-text NEXT: <n> (<repo> <k> · …)`,
   the repo named from the project directory (`-opt-<name>` → `<name>`).
4. **With `--repo <path>`** — the store reading V5 needs, read through `scripts/work.py` imported by
   path: open `kind: next` items whose `next_at` is within 7 days, the live claims (`work._live_claims`),
   and the sessions of item 3 for that repo; then `V5: PASS` when open next items ≤ those sessions AND
   live claims > 0, else `V5: FAIL — <which bound>`.

`--root` defaults to `$CLAUDE_CONFIG_DIR/projects` when that env var is set, else
`~/.claude/projects`; the test passes a temp `--root`. A transcript line that is not JSON, or a
file that cannot be read, is skipped and counted in a closing `skipped: <n> file(s)` line — never a silent zero.
Exit 0 always except a bad argument (argparse's 2); `--repo` on a repo without a store prints
`V5: no store in <path>` and exits 0. The `# AFTER-EDIT:` header names `docs/reference/work-tracking.md`.

DO-NOT: `scripts/work.py`, `scripts/thread_anchor.py` (read through their public functions only); no
write anywhere; no network.

Depends: —
Parallel: ⚡
Complexity: simple
Gate: .venv/bin/python -m pytest tests/test_next_census.py -q
Docs: `INDEX.md` gains the script's row (orchestrator Deltas — a governance file); `docs/reference/work-tracking.md` § Validation reading is T07b's

## Touches
- scripts/sysadmin/next_census.py — PRIMARY PATH
- tests/test_next_census.py

## Behavior Contract
- **Given** a temp root holding two sessions' transcripts with NEXT lines of all five classes, **When** `next_census.py --root <tmp> --since 7` runs, **Then** the classes line prints each count, the total and `over 2 sessions` exactly (spec § Why this exists)
- **Given** one session whose last NEXT of a turn is `phase B of the plan — docs/development/plans/x` and another whose free-text NEXT is `tidy the notes`, **When** the census runs, **Then** only the first is counted in the sessions line, under its repo (spec § The delta D3 measured volume)
- **Given** a transcript older than `--since` days and one unreadable line, **When** the census runs, **Then** the old file is not counted and the bad line is skipped without stopping the run (spec § Validation V5)
- **Given** a temp store with two open `next` items within 7 days, one live claim and two qualifying sessions for that repo, **When** the census runs with `--repo`, **Then** it prints `V5: PASS`; with no live claim it prints `V5: FAIL` naming the claims bound (spec § Validation V5)

## Context Files
- .windsurf/rules/core/10-python.md
- .windsurf/rules/core/45-testing-strategy.md
- scripts/thread_anchor.py
- tests/test_thread_anchor.py
