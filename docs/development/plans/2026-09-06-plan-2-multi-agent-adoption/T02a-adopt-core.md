# T02a — `docs_updater.py --adopt`: seed the PLANS markers, stamp owners, declare the merge owner, print the header

## Scope
Four additions to `scripts/docs_updater.py` (fleet-synced RUN_SCRIPT — every line must be correct for a project that has NONE of these files). (1) `MERGE_OWNER_RE` (the T01 regex, verbatim) + `read_merge_owner() -> tuple[str, str] | None` returning `(name, "D-NNN")` from the LAST matching row of `PROJECT_ROOT/docs/DECISIONS.md`, and a second header comment inside the PLANS block body, emitted by `generate_plans_table()` right after `_PLANS_PHASE_NOTE` (`docs_updater.py:924`): `<!-- Merge owner: <name> | source: D-NNN -->` or `<!-- Merge owner: UNDECLARED — run: python scripts/docs_updater.py --adopt <name> -->`; the header comment is part of the block BODY, so `replace_block` (`docs_updater.py:703` — its stamp is hard-coded `v1`, there is no version argument; the spec's "v2" is realised as this body change) reports every pre-change block stale exactly once. (2) `count_sessions_sharing(cwd: Path, proc_root: Path = Path("/proc")) -> int`: the number of processes whose `<proc_root>/<pid>/comm` is `claude` and whose `<proc_root>/<pid>/cwd` symlink resolves to `cwd` — stdlib only, unreadable or vanished entries skipped, never raises; `proc_root` exists so a test builds a fake tree (`<tmp>/proc/<pid>/comm` + a `cwd` symlink) and exercises the REAL scan, never a count override. (3) `--adopt <name>[,<name>…]` (argparse, beside `--sync` at `docs_updater.py:1562`): refuses with ONE stderr line and exit 2 when `count_sessions_sharing(PROJECT_ROOT) < 2` unless `--single-window` is also given; otherwise (a) if `PLANS_INDEX` exists without markers, appends `\n## Ownership (auto-generated)\n\n<!-- AUTO-GENERATED:PLANS:START -->\n<!-- AUTO-GENERATED:PLANS:END -->\n` below the existing content (creates the file with that block when absent), (b) stamps `**Owner:** <name>` as the line after the H1 of every plan unit (`generate_plans_table()`'s own unit list, `docs_updater.py:1024-1033` — monolith files and set spines) whose `parse_plan_owner()` is `NO_OWNER` and whose `parse_plan_status()` is not `EXECUTED` or `COMPLETE` (the two terminal values the normaliser at `docs_updater.py:889-905` produces; `BLOCKED`, `DRAFT`, `PLANNED`, `CONVERGED`, `IN_PROGRESS`, `PARTIAL`, `NOT_DONE` and `Active` are open), round-robin over the names in the order given, (c) appends the ledger row `| D-NNN | <today> | <first name> (--adopt) | MERGE OWNER: <first name> — …one sentence… | … | docs/development/PLANS.md |` with `D-NNN` = max existing id + 1 (the same `^\|\s*D-(\d+)\s*\|` scan `decisions.py:162` uses) ONLY when `read_merge_owner()` is None, (d) when `PLANS_DIR.parent / "epics"` exists and holds `*.md`, runs `python scripts/epic_order.py --assign <names>` via subprocess and includes its exit in the report, (e) regenerates the block (`sync_plans_index`) and prints a table `| Item | Owner | Source |` — one row per file/row it changed, `Source` ∈ {`markers`, `owner-line`, `ledger-row`, `epic_order`}. Idempotent: a second run with the same names changes no byte and prints `(nothing to adopt)`. (4) `_PLANS_PHASE_NOTE` loses the words "agent-1's tail sweep fills it" for "`--adopt` fills it". DO-NOT: touch STRATEGIC_BACKLOG.md (T02b); add the `--check` advisory (T03); touch `scripts/decisions.py` (T01); import anything outside the stdlib.

Depends: —
Parallel: ⚡
Complexity: complex
Gate: /opt/fabrik/.venv/bin/python -m pytest tests/test_docs_updater_adopt.py tests/test_docs_updater.py -q
Docs: CHANGELOG (Deltas) · INDEX row for `tests/test_docs_updater_adopt.py` (Deltas)

## Touches
- scripts/docs_updater.py — PRIMARY PATH
- tests/test_docs_updater_adopt.py

## Behavior Contract
- **Given** a scratch repo (PROJECT_ROOT monkeypatched) with a marker-less PLANS.md, two open plans with no Owner line, one EXECUTED plan, and a ledger with no `MERGE OWNER:` row, **When** `--adopt alpha,beta --single-window` runs, **Then** PLANS.md gains the markers and a v2 block whose second header line reads `<!-- Merge owner: alpha | source: D-NNN -->`, the two open plans carry `**Owner:** alpha` and `**Owner:** beta` on the line after their H1, the EXECUTED plan is untouched, exactly one `MERGE OWNER: alpha` row was appended with id max+1, and the printed table has one row per change (scripts/docs_updater.py:1046)
- **Given** the state after that run, **When** `--adopt alpha,beta --single-window` runs again, **Then** every touched file is byte-identical and the output is `(nothing to adopt)` (scripts/docs_updater.py:1015)
- **Given** a ledger already carrying `MERGE OWNER: alpha`, **When** `--adopt gamma --single-window` runs, **Then** NO new ledger row is written, the existing row is untouched, and the header comment still names `alpha` — a change of merge owner is a hand-minted superseding row, never `--adopt`'s write (scripts/decisions.py:82)
- **Given** a fake proc tree with ONE `claude` process whose cwd is the repo and no `--single-window`, **When** `--adopt alpha` runs with `proc_root` pointed at it, **Then** it exits 2 with one stderr line naming the count and the override, and no file changes; with two such processes it proceeds (scripts/docs_updater.py:1550)
- **Given** a ledger row whose `what` opens with `**MERGE OWNER: alpha**`, **When** `read_merge_owner()` runs, **Then** it returns `("alpha", "D-NNN")` (scripts/docs_updater.py:834)
- **Given** an epics dir with two frontmatter epics lacking `owner:`, **When** `--adopt alpha,beta --single-window` runs, **Then** `epic_order.py --assign alpha,beta` was invoked once and the table carries an `epic_order` row (scripts/epic_order.py:668)
- **Given** the live hub tree, **When** `generate_plans_table()` runs, **Then** its second line starts with `<!-- Merge owner:` and `validate_plans_indexed()` against the pre-change block reports the stale finding once, and `--sync` clears it (scripts/docs_updater.py:1066)

## Context Files
- .windsurf/rules/core/10-python.md
- .windsurf/rules/core/45-testing-strategy.md
- scripts/docs_updater.py
- tests/test_docs_updater.py
- scripts/decisions.py
- scripts/epic_order.py
- docs/superpowers/specs/2026-09-06-multi-agent-adoption-design.md
