# Plan — the scaffold stops emitting the retired Kilo/Traycer/Windsurf surface (mail 01M407YP)

Status: DRAFT
Profile: small
**Owner:** fleet

Spec: `docs/superpowers/specs/2026-10-03-scaffold-retired-agent-surface-design.md` (DRAFT, `Size: small`, `Profile: delta` —
`/fabrik-plan-review` grades its sections together with this plan and flips both). Source: infra's mail 01M407YP (acked;
reply 01M40SBBEGYNQ3R6AW3EAXBWT5 carries infra's half). Rulings: D-514 (development runs on Claude Code), D-364 (Kilo CLI
retired). Estimated diff: ≈180 code lines in 4 code files, tests excluded — `src/fabrik/scaffold.py` ≈150 (mostly
deletions plus the marker-removal helper), `src/fabrik/cli.py` ≈25 (the `fix` rendering and two help texts),
`src/fabrik/preplan.py` ≈5, `src/fabrik/portability.py` ≈2.

## What this plan is

The FLEET half of the spec (`spec § Chosen approach`, fleet half steps 1-5), in two inline phases the orchestrator codes
itself in the worktree; no coder is dispatched:

- **A — `_scaffold_shared` and `fix_project` stop emitting the retired surface**, `fix_project` removes the two empty
  Traycer markers from existing projects, and `fabrik fix` reports removals as removals.
- **B — the pre-plan copy stops writing into guardrail files**; docs, Finish.

**Ordering:** infra's half merges first (`spec § Chosen approach`, infra steps 1-5; `spec § Contract deltas`, merge
order) — fleet-first would leave a newly scaffolded project with `check_opencode_json.py` but no `opencode.json`, a
blocking gate red. This plan can be executed now; only its merge waits (Phase B step 9).

Per phase: `/fabrik-review-scoped` on that phase's surface. At Finish: one heavy `/fabrik-review` (the
`/fabrik-execute-plan` D7 floor) and one receipt.

## Intake Inventory

| I# | Item (anchored) | Disposition | Where |
|---|---|---|---|
| I1 | "scaffold.py:290-291 comments: Traycer Phases replace manual phase tracking" | IN | Phase A |
| I2 | "`.droid/review-context` and `.droid/traycer-reports` in SHARED_DIRS" | IN | Phase A |
| I3 | "emit the .droid gitignore block and traycer-reports/" | IN | Phase A |
| I4 | "copy AGENTS-compact.md, the Kilo CLI bootstrap" | IN | Phase A (scaffold side); the manifest side is infra's (reply 01M40SBB) |
| I5 | "inject a `Preplan:` line into all 4 AI guardrail files" | IN | Phase B; the governance line is infra's (reply 01M40SBB) |
| I6 | "`fabrik fix` re-adds `.droid/` to existing ones" | IN | Phase A |
| I7 | "The decision is whether to keep `.droid/dev_tracker.db`" | IN | decided in `spec § Decisions taken`; no scaffold code writes it, so no step here; the dead script is infra's (reply 01M40SBB) |
| I8 | infra's W-477e37cd retired-terms tripwire "waits on it" | OUT-OF-SCOPE | infra's own item W-477e37cd, unblocked once both halves merge |
| I9 | `docs/reference/kilo/` copied by the scaffold | IN (kept) | Phase A keeps it; `spec § Rejected alternatives` C |

## What we already agreed (citations, not restatement)

- Goal and personas: `spec § Goal`, `spec § Personas`.
- Why: `spec § Why this exists`; the per-artifact verdicts: `spec § What exists today (grounded)`.
- Chosen approach A and the two-owner split: `spec § Chosen approach`.
- Rejected B, C, D: `spec § Rejected alternatives`.
- The fleet delta: `spec § The delta`; contract mirrors: `spec § Contract deltas`.
- Validation: `spec § Validation` (rows 1-3 are this plan's; row 4 is after infra's merge).
- Decisions: `spec § Decisions taken`. The approval row is minted by `/fabrik-plan-review` at its gate (a `Size: small`
  spec is approved there, not here).

## Global Constraints (every phase inherits these)

- **Nothing a project owns is deleted except the two scaffold-owned Traycer markers**, and their directories only when
  empty (`spec § Chosen approach`, fleet step 3; `spec § Contract deltas`). `fix_project` never deletes
  `.windsurfrules`, `AGENTS-compact.md`, `opencode.json` or `scripts/kilo_47_agents_final.json` in a project — infra's
  prune owns the first three; the fourth is left for its owner. Nothing is removed through a symlink.
- **`docs/reference/kilo/` stays** — both copies (`scaffold.py:1312-1318`, `:7448-7460`) are untouched
  (`spec § Rejected alternatives` C).
- **`_DROID_GITIGNORE_BLOCK` keeps its name** — eight per-type writers embed it (`:1405`, `:4498`, `:4647`, `:4780`,
  `:5849`, `:6012`, `:6147`, `:6451`); only its content changes.
- **Every `fix_project` live block removed here takes its dry-run twin with it** (the `if not dry_run:` / `else:`
  pairing, `:7406-7553` / `:7554-7621`), and a new step gets a dry-run twin that reports what the live run would do.
- **Merge order: infra's half first** (`spec § Contract deltas`, merge order). This plan may be EXECUTED before infra
  merges; its merge request (Phase B step 9) asks infra to merge it only after infra's half (the manifest, the prune and
  the `check_opencode_json` retirement) is on master.
- No new dependency; `pyproject.toml` and `uv.lock` are not touched (`core/10-python.md:30`). No env var is added. No
  logging change beyond rewording one `logger.info` (`core/10-python.md:292`: no file sink is introduced).
- 12-Factor on this surface: a hub CLI's file generation — **III** no config added, **XI** logging unchanged; the rest not
  engaged (no service, no backing store, no process model change).
- Tests: watched-fail-first for every behaviour this plan adds or changes (`core/45-testing-strategy.md:22`); assertions on
  files and report strings, never cosmetic (`:21`). The shared `.venv` imports `fabrik` from `/opt/fabrik/src` — every run
  exports `PYTHONPATH=/opt/fabrik/.claude/worktrees/fleet/src`. Red-on-revert runs in a throwaway worktree
  (`git worktree add --detach <scratch>/probe HEAD`), never in the shared checkout.
- Seats never mutate git state (read-only git only); never read `~/.claude*`; never SSH.
- **Execution discipline (native seats only, D-181):** every phase ends with `/fabrik-review-scoped` on its surface (the
  floor of three native seats on different angles, stamped with `command_run.py dispatch`), not handing on until its
  closing pass confirms zero defects. The Finish `/fabrik-review` partitions the whole-plan diff by file into a Sonnet and
  a Haiku finder per slice (D-344), the orchestrator executing every refutation. Within a phase the steps are sequential
  (each consumes the previous); the review seats are the parallel fan-out, merged and refuted by the orchestrator.

## Context Ledger

| Source | What binds | Grounded ref |
|---|---|---|
| `.windsurf/rules/core/10-python.md` (MATCHED) | no deps-file edit; no file logging | `core/10-python.md:30`, `:292` |
| `.windsurf/rules/core/40-documentation.md` (MATCHED) | heading levels and fenced code in the docs edited | `core/40-documentation.md:241` |
| `.windsurf/rules/core/45-testing-strategy.md` (MATCHED) | one test per behaviour; watched-fail-first; no cosmetic assertions; a guard proven several ways | `45-testing-strategy.md:20-22`, `:199-200` |
| `.windsurf/rules/core/35-security-auth.md` (FLOOR) | config via env only — not engaged: no config, no secret | `core/35-security-auth.md:267` |
| `.windsurf/rules/core/30-ops.md` (FLOOR) | deploy/runtime rules — not engaged: no service, compose or deploy change | `spec § Shape / infra implications` |
| `.windsurf/rules/core/25-data-postgres.md` (FLOOR) | not engaged: no database | `spec § Shape / infra implications` |
| `fabrik-lib` | none — hub scaffold code | `spec § fabrik-lib verdict` |
| `agents-fabrik.md` § Scaffold Types | the scaffold is the generator for all registered types; the change applies to every type's create path | `agents-fabrik.md:390` |
| `specs/services/*.yaml` `shape:` | no flag changes | `spec § Shape / infra implications` |

## Constraints Digest (verbatim rows from the MUST-READ packs)

| Verbatim | file:line | Rule |
|---|---|---|
| "Dependencies live in `pyproject.toml` + `uv.lock`. Do not modify these files unless the ticket authorises it." | `.windsurf/rules/core/10-python.md:30` | Deps |
| "**BANNED:** `logging.FileHandler`, `logging.handlers.RotatingFileHandler`, `TimedRotatingFileHandler`, `loguru` file sinks, any `*.log` file write" | `.windsurf/rules/core/10-python.md:292` | Logs |
| "every ticket enumerates its distinct **user-observable behaviors / acceptance criteria** and tests **each one**" | `.windsurf/rules/core/45-testing-strategy.md:20` | Behaviour Contract |
| "**No cosmetic assertions**: never assert against CSS classes, Tailwind utility strings, pixel measurements, or snapshot hashes." | `.windsurf/rules/core/45-testing-strategy.md:21` | Assertions |
| "**Watched-fail-first** (for tests this change adds or modifies" | `.windsurf/rules/core/45-testing-strategy.md:22` | Red first |
| "A GUARD proven only by the ONE spelling of the defect you already fixed" | `.windsurf/rules/core/45-testing-strategy.md:199` | Guard spellings — five trees in A4 |
| "**No skipped heading levels** — `##` to `###`, never `##` to `####`" | `.windsurf/rules/core/40-documentation.md:241` | Docs |
| "Mandate: config via env vars only (`os.getenv("KEY", "default")`); **ZERO secrets/constants in code**." | `.windsurf/rules/core/35-security-auth.md:267` | Config (not engaged) |

## Phase A — `_scaffold_shared` and `fix_project` stop emitting the retired surface

Appetite: 75

**Interfaces — Produces** (`src/fabrik/scaffold.py` unless named; `spec § Chosen approach`, fleet steps 1-3):
- `_DROID_GITIGNORE_BLOCK` (`:548-557`) — content exactly `.factory/consultations/`, `.droid/docs_queue/`,
  `.droid/docs_log/`, one per line, trailing newline; the comment above it (`:542-547`) names only `docs_updater.py`.
- `_RETIRED_DROID_GITIGNORE_LINES` — new tuple of the five retired lines (`.droid/kilo_usage.jsonl`, `.droid/reviews/`,
  `.droid/kilo_models_cache.json`, `.droid/.kilo_cache_last_refresh`, `.droid/traycer-reports/*.md`).
- `_patch_droid_block(content, canonical)` (`:7266-7303`) — "managed" becomes a line whose stripped text is one of the
  canonical block's lines or one of `_RETIRED_DROID_GITIGNORE_LINES`, instead of any line starting `.droid/` or
  `.factory/`; the fast path and the insert-at-first-managed-position behaviour are unchanged.
- `_DROID_DIR_GITIGNORE` (`:699-708`) — content exactly `"# .droid runtime files (docs_queue/, docs_log/) — do not
  commit\n*\n!.gitignore\n"`. `_TRAYCER_REPORTS_GITIGNORE` (`:711-713`) removed.
- `_scaffold_shared` (`def :1121`): `SHARED_DIRS` loses `.droid/review-context` and `.droid/traycer-reports`
  (`:495-496`) and gains `.droid` (the only creator of `.droid/` once they go; `:1131-1132` makes each entry); `:1136-1142`
  removed; the `.windsurfrules` guard and copy (`:1240`, `:1244-1245`, `:1253-1254` — the `.windsurf/rules` and
  `.windsurf/workflows` guards `:1246-1251` stay), the AGENTS-compact copy (`:1324-1327`), the kilo_47 copy
  (`:1379-1384`) and the `opencode.json` copy (`:1400-1401`) removed; comments `:290-291` and `:1333-1334` removed or
  reworded so they name no retired file.
- `_remove_retired_droid_markers(project_path: Path, *, dry_run: bool) -> list[str]` — new, beside `_patch_droid_block`;
  called only when `.droid` is a real directory (`fix_project` handles a symlinked `.droid`, below). For each of
  `(".droid/review-context", ".gitkeep")` and `(".droid/traycer-reports", ".gitignore")`, with `d` the directory and `m`
  the marker, the first matching rule wins:
  1. `d` missing (`not d.exists() and not d.is_symlink()`) → nothing;
  2. `d.is_symlink()` → `skipped <dir>/ (symlink)`;
  3. `d` is not a directory (a regular file of that name) → `kept <dir> (not a directory)`;
  4. `m.is_file() and not m.is_symlink()` → remove it (`m.unlink()`, not under `dry_run`) and report `removed <dir>/<marker>`;
     an `OSError` from that `unlink` reports `could not remove <dir>/<marker>: <strerror>` and ends this pair (no `rmdir`
     is tried); a marker that is a directory, a symlink (dangling or not) or absent is left and counted as an entry;
  5. `others` = the entries of `d` other than a regular-file marker that rule 4 removed or (under `dry_run`) would remove,
     so both modes count the same; `others == 0` → `d.rmdir()` (not under `dry_run`) and report `removed <dir>/ (empty)`;
     else report `kept <dir>/ (<others> other entries)`; an `OSError` from `rmdir` reports `could not remove <dir>/: <strerror>`.
  Entries are returned prefixed by their verb (`removed `, `kept `, `skipped `, `could not remove `).
- `fix_project`: the `.windsurfrules`, `AGENTS-compact.md`, `opencode.json`, `kilo_47_agents_final.json` blocks and
  their dry-run twins removed (`spec § Chosen approach` fleet step 3 lists every range), with the `windsurfrules_target`
  guard `:7402`, `:7408-7409` (the `.windsurf/rules` and `.windsurf/workflows` guards `:7410-7413` stay); the marker
  creation `:7530-7544` / `:7605-7613` replaced by one `_remove_retired_droid_markers` call in each branch, its entries
  appended to the returned list. When `.droid` is a symlink, dangling or not (`droid_dir.is_symlink()`), both branches
  skip the whole `.droid` block — no `mkdir` (`:7522` raises `FileExistsError` on a dangling link and writes through a live
  one), no `.droid/.gitignore` write, no helper call — and append one `skipped .droid/ (symlink)` entry. Otherwise the
  `.droid/.gitignore` rewrite and the root-`.gitignore` patch stay, writing the reduced constants.
- `src/fabrik/cli.py` `fix` command (`:2038-2058`): splits the returned list into notes (`kept `, `skipped `),
  failures (`could not remove `), removals (`removed `) and additions (everything else, as today). Additions print as
  today; removals print `🗑️  Removed: <rest>` (`Would remove: <rest>` under `--dry-run`); notes print `ℹ️  <entry>` and
  never count; failures print `⚠️  <entry>` and make the command exit 1, as unsupported entries do (`:2057-2058`).
  "No missing files - project structure is complete!" prints only when there are no additions, removals, failures or
  unsupported entries, notes or not; the closing count line counts additions and removals separately.

**Consumes:** nothing.

**Mirror (named):** tests asserting the old surface change with it — `tests/test_scaffold.py`
`TestDroidGitignoreBlock` (`:26-51`, the entry list), `TestPatchDroidBlock.test_replace_contiguous_block` (`:79-86`, its
`kilo_usage` count — an old block is now replaced by the reduced one), `TestScaffoldGitignoreCoverage` (`:89-127`, five
types' `kilo_usage`/`reviews`/`traycer` entries), `TestFixProjectDroidStructure` (`:186-242`, the marker files and
`_TRAYCER_REPORTS_GITIGNORE`), `TestFixProjectRootGitignorePatch` (`:245-308`, `kilo_usage` in the block),
`TestTracerReportsScaffolding` (`:311-349`, removed — replaced by A1), `test_droid_gitignore_block_present`
(`:527-546`, its `kilo_usage`, `reviews` and `traycer` entries); `tests/test_scaffold_fix.py` the `kilo_47` refresh tests
(`:262-281`) and the kilo line of `test_dry_run_previews_reference_doc_refresh` (`:297-298`, its reference-doc asserts
`:291-296` stay); `_source_root` (`:15-19`) removed if nothing else uses it. Fixture hub roots that create
`.windsurfrules`, `AGENTS-compact.md` and `opencode.json` (`tests/test_scaffold_logging.py:79-90`,
`tests/test_scaffold_doc_seeding.py:129-136`) keep working unchanged — the scaffold just stops copying from them.

0. Probe the environment: `cd /opt/fabrik/.claude/worktrees/fleet && PYTHONPATH=$PWD/src .venv/bin/python -c "import
   fabrik.scaffold as s; print(s.__file__)"` prints the worktree path.
1. **Write the failing tests first** (rows A1-A8): A1 and A2 call `_scaffold_shared` (every create-time copy is inside it,
   `def :1121`) against a fake `FABRIK_ROOT` built like `tests/test_scaffold_doc_seeding.py:129-151`, extended with
   `docs/reference/kilo/x.md` and `scripts/kilo_47_agents_final.json` so A1's kilo legs can go red (A2 omits
   `.windsurfrules` and `opencode.json`); A3-A7 build project trees in `tmp_path` and call `fix_project` with
   `FABRIK_ROOT` patched to a fake root outside `tmp_path`'s project dir holding `kilo_47_agents_final.json`,
   `AGENTS-compact.md`, `opencode.json`, `.windsurfrules`, `.windsurf/rules/x.md` and `.windsurf/workflows/x.md` (the
   `.windsurf` guards at `scaffold.py:7410-7413` stay and raise without them; the worktree has no `kilo_47`, so the real
   root cannot show A5 red); A8 drives the `fix` command
   through Click's `CliRunner` with `fix_project` patched to return fixed entries. Run them and confirm each fails for the
   right reason (A1: the retired files exist; A2: `FileNotFoundError` naming `.windsurfrules`; A3-A6: markers kept or
   synced files rewritten; A7: the user's `.droid/` line dropped; A8: a removal printed as `Added:`).
2. Change the constants, `_patch_droid_block`, `SHARED_DIRS` and `_scaffold_shared` per the Interfaces.
3. Add `_remove_retired_droid_markers`; rewrite `fix_project`'s blocks per the Interfaces, live and dry run; change the
   `fix` command's rendering in `cli.py`.
4. Update the named mirror tests.
5. Run green: `PYTHONPATH=$PWD/src .venv/bin/python -m pytest tests/test_scaffold.py tests/test_scaffold_fix.py
   tests/test_scaffold_doc_seeding.py tests/test_scaffold_logging.py tests/test_cli.py -q -p no:cacheprovider` → all pass
   (A8 lives in `tests/test_scaffold.py`; `tests/test_cli.py` is run because the `fix` command's output changes).
6. Prove red on revert in a throwaway worktree (copy each edited file to its exact path, grep a marker to confirm the
   copy landed): let `_remove_retired_droid_markers` remove a non-empty directory with `shutil.rmtree` → A4 fails; drop
   the `d.is_symlink()` check → A4 fails; restore the `opencode.json` copy → A1 fails; restore the `.windsurfrules` guard
   → A2 fails; restore the prefix test in `_patch_droid_block` → A7 fails; remove the worktree.
7. `python scripts/enforcement/check_doc_sync.py` → exit 0.
8. **`/fabrik-review-scoped`** on Phase A's surface (`src/fabrik/scaffold.py`, `src/fabrik/cli.py`,
   `tests/test_scaffold.py`, `tests/test_scaffold_fix.py`), run to its closing pass confirming 0 — BLOCKING before Phase B.
9. Commit Phase A (explicit paths + provenance trailers, `Agent-Phase: A`), push.

### Behavior Contract — Phase A
- **Given** a fake hub root carrying every source file, **When** `_scaffold_shared` builds a project, **Then** the project has no `.droid/review-context`, `.droid/traycer-reports`, `.windsurfrules`, `AGENTS-compact.md`, `opencode.json` or `scripts/kilo_47_agents_final.json`, has `docs/reference/kilo/`, its `.droid/.gitignore` equals `_DROID_DIR_GITIGNORE`, and its root `.gitignore` carries `.droid/docs_queue/` and `.droid/docs_log/` and no line containing `kilo`, `traycer` or `.droid/reviews` (A1; `spec § Validation` 1)
- **Given** a fake hub root with no `.windsurfrules` and no `opencode.json`, **When** `_scaffold_shared` runs, **Then** it completes and writes `.droid/.gitignore` (A2; `spec § Contract deltas`, merge order)
- **Given** an old-shaped project with `.droid/review-context/.gitkeep` and `.droid/traycer-reports/.gitignore` only, **When** `fix_project` runs, **Then** both markers and both directories are gone and the result carries a `removed` entry for each (A3; `spec § Validation` 2)
- **Given** five trees — `review-context/` holding `.gitkeep` and `notes.md`; a symlinked `.droid/traycer-reports`; a `.droid/` that is a symlink to a real directory and one that is a dangling symlink; a `.gitkeep` that is a directory; a `.gitkeep` that is a dangling symlink — plus a `.droid/review-context` that is a regular file and a project whose marker `unlink` raises `PermissionError`, **When** `fix_project` runs on each, **Then** `notes.md` survives with `kept .droid/review-context/ (1 other entries)`; each symlink and its target are untouched (no `.gitignore` written into the target) with one `skipped … (symlink)` entry and no exception; the directory marker, the dangling marker and the regular file stay with a `kept` entry; the refused removal yields one `could not remove …` entry, no `rmdir` is tried for that directory, and the run completes (A4; `45-testing-strategy.md:199`)
- **Given** a project holding its own `.windsurfrules`, `AGENTS-compact.md`, `opencode.json` and `scripts/kilo_47_agents_final.json` and a hub root holding all four, and one project holding none of them, **When** `fix_project` runs, **Then** the first keeps all four byte-identical, the second gains none, and no entry names them (A5; `spec § Chosen approach`, fleet step 3)
- **Given** the A3 tree and the A4 non-empty tree with `dry_run=True`, **When** `fix_project` runs, **Then** its entries equal the live run's entries for the same trees, and every file and directory is unchanged (A6; `spec § Validation` 2)
- **Given** a root `.gitignore` holding the old eight-line `.droid` block among user lines, one of them `.droid/secrets.json`, **When** `fix_project` runs, **Then** the block is replaced by the reduced one, the user lines — `.droid/secrets.json` included — survive in order, and a second run reports no `.gitignore` change (A7; `scaffold.py:7266-7303`)
- **Given** `fix_project` returning one addition, one `removed` entry and one `kept` entry; then only a `kept` entry; then one `could not remove` entry, **When** `fabrik fix` renders them, **Then** the addition prints `Added:`, the removal `Removed:`, the note without either label and outside the counts; the second run prints "No missing files - project structure is complete!" and exits 0; the third prints the failure, not the "complete" line, and exits 1 (A8; `cli.py:2038-2058`)

## Phase B — The pre-plan copy stops writing into guardrail files; docs; Finish

Appetite: 50

**Interfaces — Produces:**
- `src/fabrik/scaffold.py::_layer_preplan_into_project(project_dir: Path, preplan: object) -> None` (`:6939-7005`) —
  signature unchanged; copies the pre-plan to `docs/preplan.md` as today (`:6968-6972`) and returns; the
  `reference_line`, the guardrail list and the per-file loop (`:6975-7000`) are removed and the closing `logger.info`
  (`:7002-7005`) says only that the pre-plan was copied. Its docstring (`:6940-6960`), `create_project`'s (`:7104-7117`)
  and the caller comment (`:7179-7181`) say the pre-plan is copied to `docs/preplan.md` and the governance CLAUDE.md
  points agents at it.
- Docstrings and help, same wording: `src/fabrik/preplan.py:1-8`, `src/fabrik/cli.py:1806-1818` (the `--from-preplan`
  help) and `:2198-2211` (the `preplan` group), `src/fabrik/portability.py:416-417` (the governance list loses
  `.windsurfrules`, `AGENTS-compact.md` and `KILO_CLI_RULES.md`).
- Docs (`spec § Documentation landing sites`): `docs/QUICKSTART.md:70-77`, `docs/reference/architecture.md:255-256`,
  `docs/workflows/SCAFFOLD_STRUCTURE.md:27,70,147,263`, `docs/workflows/FABRIK_SCAFFOLD_WORKFLOW.md:266-268,444-446,604-613`,
  `docs/CONFIGURATION.md:596`, `docs/reference/fabrik-cli-reference.md:26`, `docs/preplans/README.md:25`,
  `docs/traycer/fabrik-workflow.md:92`; and through the
  orchestrator's governance path (outside File Scope by the plan grammar) `docs/FEATURES.md:427,606` and `CHANGELOG.md`.

**Consumes:** Phase A (the `.droid/` shape the docs describe).

**Mirror (named):** `tests/test_preplan.py` `test_injects_reference_into_all_4_guardrails` (`:175-195`),
`test_skips_missing_guardrail_files_silently` (`:197-214`) and `test_idempotent_does_not_duplicate_reference`
(`:216-237`) are replaced by B1; `test_copies_preplan_to_project_docs` (`:160-173`) and `test_none_preplan_is_no_op`
(`:239`) stay.

1. **Write the failing test first** (B1) in `tests/test_preplan.py`, replacing the three injection tests; confirm it fails
   against today's code (the guardrail files gain the line).
2. Rewrite `_layer_preplan_into_project`, its log line and the docstrings/help per the Interfaces.
3. Run green: `PYTHONPATH=$PWD/src .venv/bin/python -m pytest tests/test_preplan.py tests/test_scaffold.py -q -p
   no:cacheprovider`; and `command grep -rn "4 AI guardrail\|all 4 AI\|four AI guardrail\|4 guardrails" src/fabrik` → no
   output.
4. Prove red on revert in a throwaway worktree: restore the injection loop for `CLAUDE.md` only → B1 fails; remove it.
5. The doc edits per the Interfaces; `docs/FEATURES.md` and `CHANGELOG.md` through the shared-append private-index recipe
   (`CLAUDE.md` § Behavior, the shared-repo bullet). Then `command grep -rn "review-context\|traycer-reports\|4 AI
   guardrail" docs/QUICKSTART.md docs/CONFIGURATION.md docs/FEATURES.md docs/preplans/README.md docs/reference/architecture.md
   docs/reference/fabrik-cli-reference.md docs/workflows/SCAFFOLD_STRUCTURE.md docs/workflows/FABRIK_SCAFFOLD_WORKFLOW.md
   docs/traycer/fabrik-workflow.md`
   → only historical mentions (a "retired" note), each read; `python scripts/enforcement/check_doc_sync.py` and
   `python scripts/render_doc_script_links.py --check` → both exit 0.
6. **`/fabrik-review-scoped`** on Phase B's surface (the four source files, `tests/test_preplan.py`, the edited docs), run
   to its closing pass confirming 0.
7. **Finish — the heavy `/fabrik-review`** over the whole-plan diff (`git diff <phase-A base>..HEAD`): the D7 floor — at
   least one Opus authoritative seat plus one Sonnet and one Haiku seat per independent failure-class group, sized by
   `python3 /opt/fabrik/scripts/sysadmin/dispatch_headroom.py --units <groups>` and stamped with
   `python3 scripts/command_run.py dispatch --seats <n>` before they go out; the receipt at
   `docs/development/reviews/2026-10-03-plan-1-scaffold-retired-agent-surface-review.md` embedding the verbatim
   `final_gate.py --json` success. Then `/fabrik-docs-review` over the edited docs.
8. The full gate: `python scripts/final_gate.py --check --json` → `"status": "success"` (necessary, not sufficient — the
   Evidence below is the design proof), and `python scripts/enforcement/check_convergence.py` → exit 0.
9. Commit Phase B (`Agent-Phase: B`), push, then `python3 scripts/merge_request.py request --review <the receipt>` and send
   the printed `SendMessage` line, with the message saying: merge after infra's half (the manifest, the prune and the
   `check_opencode_json` retirement) is on master.

### Behavior Contract — Phase B
- **Given** a parsed pre-plan and a project holding `AGENTS.md`, `CLAUDE.md`, `AGENTS-compact.md` and `.windsurfrules`, **When** `_layer_preplan_into_project` runs, **Then** `docs/preplan.md` equals the source pre-plan and all four files are byte-identical to before (B1; `spec § Validation` 3)
- **Given** the merged change, **When** `check_doc_sync.py` and `render_doc_script_links.py --check` run, **Then** both pass and no file under `src/fabrik/` says "4 AI guardrail" or "4 guardrails" (B2; `spec § Documentation landing sites`)

## File Scope (owned paths)

- src/fabrik/scaffold.py
- src/fabrik/preplan.py
- src/fabrik/cli.py
- src/fabrik/portability.py
- tests/test_scaffold.py
- tests/test_scaffold_fix.py
- tests/test_preplan.py
- docs/QUICKSTART.md
- docs/CONFIGURATION.md
- docs/preplans/README.md
- docs/reference/architecture.md
- docs/reference/fabrik-cli-reference.md
- docs/workflows/SCAFFOLD_STRUCTURE.md
- docs/workflows/FABRIK_SCAFFOLD_WORKFLOW.md
- docs/traycer/fabrik-workflow.md
- docs/superpowers/specs/2026-10-03-scaffold-retired-agent-surface-design.md
- docs/development/reviews/2026-10-03-plan-1-scaffold-retired-agent-surface-review.md

## Evidence

**Phase A.** The create-time copies and the guard, all inside `_scaffold_shared` (`def :1121`, read this run):
```text
src/fabrik/scaffold.py:1244:     if not fabrik_windsurfrules.exists():
src/fabrik/scaffold.py:1254:     shutil.copy(fabrik_windsurfrules, project_dir / ".windsurfrules")
src/fabrik/scaffold.py:1384:         shutil.copy(fabrik_kilo_config, scripts_target_dir / "kilo_47_agents_final.json")
src/fabrik/scaffold.py:1401:     shutil.copy(FABRIK_ROOT / "opencode.json", project_dir / "opencode.json")
```
`.droid/` is created only by the two retired `SHARED_DIRS` entries today (`:1131-1132`, `:495-496`), then written at
`:1135` — the pass-1 seat ran the change without a `.droid` entry and got `FileNotFoundError: …/.droid/.gitignore`. The
fix path's live/dry-run pairing: `:7406-7553` / `:7554-7621`; every deletion in the live branch is a replace-before-copy
(10 sites: `:7420`, `:7427`, `:7429`, `:7438`, `:7440`, `:7453`, `:7455`, `:7465`, `:7474`, `:7482`), so
`_remove_retired_droid_markers` is new code with its own guards. Today's `_patch_droid_block` drops a user's own line:
```text
$ python3 -c "...from fabrik.scaffold import _patch_droid_block as p; print(repr(p('.env\n.droid/secrets.json\n.droid/kilo_usage.jsonl\n', '.factory/consultations/\n.droid/docs_queue/\n.droid/docs_log/\n')))"
'.env\n.factory/consultations/\n.droid/docs_queue/\n.droid/docs_log/\n'
```
The `fix` command prints every returned entry as `Added:` and counts it (`cli.py:2044-2056`). The live readers of what
stays: `scripts/docs_updater.py:107-108` creates `.droid/docs_queue` and `.droid/docs_log` at import.

**Phase B.** The injection and its consumers:
```text
src/fabrik/scaffold.py:6981:     guardrail_files = [
src/fabrik/scaffold.py:7003:         "preplan layering: copied to %s + reference injected into 4 guardrails",
src/fabrik/cli.py:1814:         "'Preplan:' reference to all 4 AI guardrail files (AGENTS.md, CLAUDE.md, "
src/fabrik/preplan.py:6: the four AI guardrail files (CLAUDE.md, AGENTS.md, AGENTS-compact.md,
tests/test_preplan.py:175:     def test_injects_reference_into_all_4_guardrails(self, fake_root, tmp_path):
```
The docs: `docs/QUICKSTART.md:70-77`, `docs/CONFIGURATION.md:596`, `docs/preplans/README.md:25`,
`docs/reference/architecture.md:255-256`, `docs/reference/fabrik-cli-reference.md:26`,
`docs/workflows/SCAFFOLD_STRUCTURE.md:27`, `:70`, `:147`, `:263`, `docs/workflows/FABRIK_SCAFFOLD_WORKFLOW.md:266-268`,
`:444-446`, `:604-613`, `docs/traycer/fabrik-workflow.md:92`, `docs/FEATURES.md:427`, `:606`. Population: `command grep
-rln '4 AI guardrail\|review-context\|traycer-reports' docs --include=*.md` outside archives, specs, plans, reviews and the
ledgers lists 10 files — these nine plus `docs/traycer/README.md`, a doc retired by its own banner (2026-07-19) and left
as history.

## Self-audit

- Grounding: three native seats (Opus on `fix_project`, Sonnet on the create path, Sonnet on the pre-plan path and every
  consumer), all returning `path:line`; the orchestrator re-read every anchor this plan and the spec cite.
- The seats changed the design: `opencode.json` and `kilo_47_agents_final.json` are also copied at create time; both
  `.windsurfrules` copies sit behind a fail-fast guard; every fix block has a dry-run twin; the constant feeds eight
  writers. The spec was amended for each.
- Plan-review pass 1 changed it again (Pass Ledger): the merge order is infra-first, not free; `.droid/` needs its own
  creator; de-listing deletes no project copy, so infra owes a prune; the marker helper never acts through a symlink and
  reports refused removals; `_patch_droid_block` keeps a user's own `.droid/` lines; the `fix` command renders removals
  and notes; more mirror tests and docs are named.
- Infra's half now carries a prune (`spec § Chosen approach`, infra step 1) and the merge order — mailed to infra.
- (a) Coverage: I1-I3, I6 → Phase A; I4 → Phase A (scaffold side), infra (manifest + prune); I5 → Phase B, infra
  (governance line); I7 → decided, no scaffold code; I9 → kept (Global Constraints); I8 → W-477e37cd.
- (b) Signatures: `_remove_retired_droid_markers` (A) is called from both `fix_project` branches (A) and its entry
  prefixes are what the `fix` command (A) splits on; `_RETIRED_DROID_GITIGNORE_LINES` (A) is read by `_patch_droid_block`
  (A); B consumes no A function, only the `.droid/` shape its docs describe; `_layer_preplan_into_project`'s signature is
  unchanged for its one caller (`:7182-7183`).
- Fixed point: see the Pass Ledger.

## Residual unknowns

- **Open, not blocking — whether any live project keeps its own files under `.droid/review-context/`.** A4 covers it
  (kept and reported); the operator sees the `kept` notes on the next `fabrik fix`. No step depends on the answer.
- **Resolved:** who reads each retired artifact (`spec § What exists today`); that today's `_patch_droid_block` drops
  user lines (executed above; A7 changes it); the merge order (`spec § Contract deltas`); that de-listing deletes no
  project copy (`sync_enforcement_to_projects.py:2023-2030`, `prune_retired_scripts` at `:1764`).

## Pass Ledger

`/fabrik-plan-review`, 2026-10-03. Native seats only (D-181), partitioned by section (D-212, D-218): `rules` (Opus — Global
Constraints, Context Ledger, Constraints Digest, every Interfaces block and Mirror paragraph, the step lists, both Behavior
Contracts, File Scope, Evidence, Coverage Checklist; spec What exists today, Chosen approach, The delta, Contract deltas,
Validation, Constraints digest) and `prose` (Sonnet — the rest of both). The spec is `Size: small`, so its sections are
graded here with the plan. `dispatch_headroom.py --slices opus=1,sonnet=1` → `SEATS: 2`, stamped with the refuters.

| Pass | seats · axes re-checked (claims · gates · interfaces · completeness) | counters | method | plan md5 (start → end) · spec md5 (start → end) |
|-----:|---|---|---|---|
| Pass 1 | opus×1 (`rules`) + sonnet×1 (`prose`) + one sonnet refuter per slice · all axes | found: 22, new: 22, confirmed: 22, fixed: 22, unexecuted: 0, edits: 2 files | method: citation — full partitioned pass, shape: workflow (wf_66e32be9-d25); the orchestrator re-ran every confirmed check (`verify1.py`) and added O18 (de-listing deletes no project copy, `sync_enforcement_to_projects.py:2023-2030`). Confirmed: `.droid/` loses its only creator (O1); fleet-first fails a new project's gate (O2); the create-time tests could not go red as written (O3, O11); mirror tests missing (O4); the helper acts through a symlinked directory, mishandles a directory or dangling marker, and raises on a refused removal (O5, O6); live and dry-run counts can differ (O7); removals print as `Added:` (O8); the log line survives (O9); docs missing (O10, S1, S2); the guard rule's five spellings (O12); the infra-first window (O13); stale comments (O14); five vs six (O15); the Evidence enumeration (O16); user `.gitignore` lines dropped (O17); plan vs spec on open unknowns (S3); plus the spec's approach floor (0 cited URLs, `check_spec_convergence`), fixed in 458d507b2. | a65530f1ca3b344cd25f65d5666c14d3 → the Pass 2 pin · b0cc428411e56ab2fd8b80bf65ec7a34 → the Pass 2 pin |
| Pass 2 | opus×1 (`rules`, round-1 owner) + sonnet×1 (`prose`, round-1 owner) + one sonnet refuter per slice · delta over the pass-1 fix hunks (8af931102) + one hop | found: 7, new: 7, confirmed: 6, fixed: 6, unexecuted: 0, edits: 2 files | method: re-derivation — all 20 pass-1 ledger claims NOW_FALSE (17 rules, 3 prose; the rules seat re-ran the A1/A2 fake-root probe and the live/dry-run comparison on the pinned source, and `git log -p -G'droid/'` to prove the managed-line set covers every line the scaffold ever wrote); the orchestrator re-ran O18, O21, O22 (`verify2.py`: write-through via a symlinked `.droid`, `FileExistsError` on a dangling one, `NotADirectoryError` on a file) and re-derived the doc population (10 files). Confirmed, all inside pass-1 hunks (own-fix: round 1): the kept `.droid/.gitignore` write acts through a symlinked `.droid` (O18) and a dangling one raises (O21); the A3-A7 fake root lacked the `.windsurf` dirs the kept guards need (O19); a refused removal printed "complete" (O20); a regular file named like the marker directory aborted the listing (O22); a failed `unlink` still led to `rmdir` (O23). Recorded: O24 `docs/traycer/fabrik-workflow.md:92` (one hop) — folded into the doc lists anyway. | 30a94eb6caf96090363d5f6731f15a2c → the Pass 3 pin · 451560e4b76d5c8214dd1956bb481cb8 → the Pass 3 pin |

## Coverage Checklist

Rows adjudicated by `/fabrik-plan-review`.

| Class | Verdict |
|---|---|
| FLOOR core/35-security-auth — secrets, auth, config via env | UNCHECKED |
| FLOOR core/25-data-postgres — database | UNCHECKED |
| FLOOR core/30-ops — deploy, runtime | UNCHECKED |
| FLOOR 12-Factor — all twelve axes against what the plan steps | UNCHECKED |
| MATCHED core/10-python — no deps-file edits, no file logging | UNCHECKED |
| MATCHED core/40-documentation — heading levels, fenced code, every doc the change makes stale | UNCHECKED |
| MATCHED core/45-testing-strategy — one test per behaviour, watched-fail-first, guard spellings | UNCHECKED |
| Deletion safety: only the two markers and empty directories, never through a symlink | UNCHECKED |
| Live/dry-run pairing in `fix_project` | UNCHECKED |
| `fabrik fix` report rendering (additions, removals, notes) | UNCHECKED |
| Merge order with infra's half | UNCHECKED |
| fail-open vs fail-closed (a missing hub file, a missing `.droid/`) | UNCHECKED |
| cost/quota accounting — not engaged (no metered call) | UNCHECKED |
| boundary/sentinel (empty vs one-entry directory, marker vs user file, symlink) | UNCHECKED |
| behavior-without-a-test | UNCHECKED |

The rubric this plan's reviews inject into every seat brief, run on the plan's code surface:

```bash
python3 scripts/review_rubric.py --changed src/fabrik/scaffold.py src/fabrik/preplan.py src/fabrik/cli.py src/fabrik/portability.py tests/test_scaffold.py tests/test_scaffold_fix.py tests/test_preplan.py docs/QUICKSTART.md docs/CONFIGURATION.md docs/preplans/README.md docs/reference/architecture.md docs/reference/fabrik-cli-reference.md docs/workflows/SCAFFOLD_STRUCTURE.md docs/workflows/FABRIK_SCAFFOLD_WORKFLOW.md
```

```text
# REVIEW RUBRIC — inject into EVERY finder prompt (generated by review_rubric.py)
# Honesty (L1): this arms the review — it raises compliance probability, it does not guarantee it.

## FLOOR — always injected, regardless of glob (spec L3; SERVICE surface)

### core/35-security-auth.md
**The default for ALL new projects, including user-facing SaaS + mobile.** Vendor `fabrik-lib/fastapi-user-auth`: the app issues its own JWTs — **Argon2id** (the vendored argon2-cffi defaults meet OWASP minimums; never Argon2i) + timing-equalized login, atomic refresh-token rotation (`DELETE … RETURNING`), JWT `jti` denylist revocation, and dual-mode tenant-isolation RLS. Supabase is retired as a default (see `agents-fabrik.md § Supabase`); reach for Pattern B only for a project that *already* runs on Supabase Auth.
- Do not use NextAuth.js, Clerk, Auth0, or Firebase Auth.
- ADDITIONAL affordance a project justifies, never the default door.
- project files the fabrik-lib request FIRST, never hand-rolls WebAuthn.
| `chrome-extension` | ✅ **use this** | ⚠️ only via `chrome.identity.launchWebAuthFlow` + the `https://<ext-id>.chromiumapp.org/` redirect the pack already mandates; a bare mailed link lands in a TAB that cannot reach `chrome.storage.session` |
| `desktop-app` | ✅ **use this** | ⚠️ needs a registered custom protocol handler; the token then goes to `safeStorage` (`desktop-app/72-desktop.md`) |
- service MUST be able to say which:
| **Another Fabrik service** (Docker-to-Docker on the `fabrik` network) | `X-Internal-Token` + `internal_auth.py`, `hmac.compare_digest`, 403 on reject | § Internal Service Auth (M2M) below — **never** an inline `APIKeyHeader`, never a per-service key name |
- An approval link opened somewhere the user did not start must never mint a session silently.
- > **Fail-closed invariant (hard, every mode).** `auth.uid()` and `current_tenant_id()` MUST return `NULL` (→ the policy denies) on unset, empty, or malformed claims — wrap the body in `EXCEPTION WHEN OTHERS THEN RETURN NULL`. **Never** raise and never default to a value: a default turns one bad/empty JWT into a cross-tenant read, and a raise turns a deny into a 500. This is the single most security-critical line in the build — verify it explicitly with a no-context probe (`SELECT auth.uid()` → `NULL`).
- The JWT signing secret must be at least 256 bits, generated via `openssl rand -hex 32`, and injected via Pydantic Settings. Never hardcode it.
- **Pin the algorithm in the VERIFIER** — pass an explicit allow-list (`algorithms=["HS256"]`), never let the library dispatch on the token header's `alg`. Header-driven dispatch is the classic confusion attack (an RS256 public key replayed as an HS256 HMAC secret); `alg: none` is rejected unconditionally.
- "Sticky sessions are a violation of twelve-factor and should never be used or relied upon."
- => Mandate: processes are stateless/share-nothing. **STICKY SESSIONS ARE BANNED** (not just file-based sessions). Session state goes to `redis-main` (Redis) with a TTL. Never in-process memory, never on local disk. Any design that assumes "the same user hits the same process" is a violation.
- **Pattern B (legacy / migration-only):** The Supabase client SDK handles token storage. On mobile, wrap with `expo-secure-store` (never AsyncStorage or MMKV for tokens). See `80-mobile.md` § Backend Integration.
- **Both patterns:** Never store JWTs in `localStorage` or `sessionStorage` on web. Never store JWTs in AsyncStorage or MMKV on mobile.
- **Chrome Extension (MV3) specifics:** `chrome.storage.session` defaults to `TRUSTED_CONTEXTS`, so **content scripts cannot read the token** — keep it in the SW / extension-page context and have content scripts fetch it via SW-mediated messaging (`chrome.runtime.sendMessage`), not a direct read. For social login use `chrome.identity.launchWebAuthFlow` with **PKCE** (`code_verifier` via `crypto.subtle`, held in `storage.session`, redirect `https://<ext-id>.chromiumapp.org/`); the **backend** does the code-for-token exchange. **Never a heavy browser auth SDK** (Auth0-SPA-JS, `oidc-client-ts`) — they assume DOM/`localStorage`/iframes and break in the service worker. Pin a manifest `key` so the extension ID (and thus the `chrome-extension://<id>` CORS origin) is stable across machines. Full detail: `chrome-ext/70-chrome-ext.md`.
- **Never rely solely on the framework's request-shaping layer for access control.** CVE-2025-29927 (the `x-middleware-subrequest` bypass) proved COMPLETE middleware bypass via one crafted header; it is long patched upstream, but the rule outlives the patch — current Next.js even RENAMED the file to say so: `middleware.ts` became **`proxy.ts`**, explicitly repositioned as request-shaping, not a security boundary. ⚠️ **On current majors a leftover `middleware.ts` is SILENTLY IGNORED at build** — nonce injection and redirects stop executing with no error; rename it when upgrading.
- `CORSMiddleware` in FastAPI must populate `allow_origins` from environment variables (Pydantic Settings). Never hardcode origins.
- `X-Frame-Options: DENY` — kept as the legacy fallback only; formally obsoleted by `frame-ancestors`, never ship it ALONE
**Never** write inline `APIKeyHeader` / `require_api_key`. **Never** use per-service key names (`SERVICE_API_KEY`, `PROXY_API_KEY`). Scaffold `python-api` auto-emits `internal_auth.py`, `metrics.py` (REQUEST_COUNT / ERROR_COUNT / ACTIVE_JOBS / PROCESSING_COUNT), `/metrics` endpoint (Authelia-bypassed), and `SERVICE_INTERNAL_SECRET_KEY` in `.env.example`.
- => Mandate: config via env vars only (`os.getenv("KEY", "default")`); **ZERO secrets/constants in code**. Apply the open-source litmus test to every change. **BANNED**: grouped/named env config sets (e.g. a `config/production.yml` or a `settings.production` group) — env vars are granular and orthogonal, set per deploy. (The pack already covers secret handling — cross-reference existing secret patterns and extend with config orthogonality.)
- [ ] Mobile tokens stored in `expo-secure-store` — never AsyncStorage or MMKV.
- > **⚠️ Bearer bypass scope — security-critical.** The bypass defaults to `^/api/`, which makes the **entire** `/api/*` surface public (un-2FA'd). If the application authenticates only a **sub-prefix** (e.g. `/api/v1` carries the bearer/internal-token check) while OTHER `/api/*` routes are unauthenticated (legacy / admin / destructive), you **MUST** narrow the bypass with `shape.bearer_bypass_prefix: "^/api/v1"` — otherwise `fabrik apply` exposes those routes to the public internet. **Bypass ONLY the path the app itself authenticates.** Value must start with `^/`; the verifier (`orchestrator/verifier.check_api_bypass`) probes the configured prefix on deploy. When unsure whether a service has un-auth'd `/api/*` routes, ask the app owner before relying on the `^/api/` default.

### core/25-data-postgres.md
| Vector search | pgvector on `postgres-main` + `fabrik-lib/rag` — ⚠️ the extension is NOT currently installed there (probed 2026-09-01: `postgres:16-alpine`, `plpgsql` only); a project needing vectors REQUESTS the fleet infra change first, never assumes it | same `postgres-main` DSN |
**"Own database" means a DATABASE on `postgres-main`, never a database SERVER.** Per-project isolation is a separate database (its own name, its own role) on the shared container — isolation, quota and backup are all satisfied at that grain. A dedicated Postgres instance is a decision, not a default: it needs its own `docs/DECISIONS.md` row naming what the shared server cannot serve (web-ecommerce-factory 01M1Q8X9, 2026-09-05: "one DB per store" read naively as one server per customer).
- Use Pydantic `BaseSettings` (per `10-python.md` § Config Loading) — never raw `os.getenv` **for an APPLICATION's settings surface**:
- ⚠️ **Scope, stated here because this LINE is what `review_rubric.py` injects — without its section.** The rubric FLOOR-injects this mandate *and* `35-security-auth`'s "config via env vars only (`os.getenv("KEY", "default")`)" into every finder prompt on every review, so a finder reading both literally has two rules it cannot both satisfy, and files a false positive on whichever it applies. The carve-out: `BaseSettings` governs a SERVICE's config surface (a `Settings` object, DB/Redis DSNs, secrets). A **vendored fabrik-lib module** has no settings object by design — it reads its own knobs with bare `os.getenv("KEY", "default")`, which is `35-security-auth`'s mandate being satisfied, not this … (wrapped further — read the pack)
- Never blindly trust `--autogenerate`. Always review `upgrade()` and `downgrade()` for unintended column drops, rename misinterpretations, and ENUM alterations before committing.
- > **Older pythons only** (services pinned below stdlib-uuid7 — which today includes SCAFFOLDED services: the scaffold still emits an older interpreter and ships `uuid-utils`; alignment tracked in the backlog): import `uuid7` from `uuid_utils.compat`, never `uuid_utils.uuid7()` directly — the latter returns `uuid_utils.UUID`, which asyncpg rejects (not a stdlib `uuid.UUID`). **DB-side:** newer PostgreSQL majors ship native `uuidv7()` (probe: `SELECT uuidv7()`); prefer `DEFAULT uuidv7()` at schema level where it exists. `postgres-main` currently runs major <!--v:postgres_major-->16<!--/v-->, which predates it — generate app-side on the fleet.
- Foreign keys must declare `ON DELETE` behaviour explicitly — `CASCADE` if children cannot exist without the parent, `RESTRICT` to protect audit trails. Never rely on the implicit default.
- This section owns the **canonical** engine, session, and `get_db`. `10-python.md` imports from here — never redefines its own.
- Database `AsyncSession` must be scoped to the route handler via `Depends()`. Never open sessions or transactions in global middleware — this holds connections during serialisation and I/O, exhausting the pool.
**BANNED as a server-side backing service** (dev, test, and prod alike):
**⚠️ SCOPE — this ban is about BACKING SERVICES, not client-local storage.** It does **NOT** apply to:
- **`desktop-app`** — SQLite is the **mandated** engine there (`desktop-app/72-desktop.md` § Local Persistence: `better-sqlite3` + SQLCipher; *"Production builds MUST encrypt the local SQLite file"*).
**12-Factor IV (Backing Services) — generalised:** swapping ANY attached backing service (DB, cache, object storage) is a **config change, never a code change**. The handle lives in `DATABASE_URL` / `REDIS_URL` / storage env — the code *reads* it, the code does not *decide* it. Never `if ENV == "prod":` branching to pick a host. (See § PostgreSQL Host Selection, which already mandates this for the DB.)
- [ ] All primary keys use UUIDv7 — stdlib `uuid.uuid7` on current Python (older pythons: `uuid_utils.compat.uuid7`, never direct `uuid_utils.uuid7()`); no `uuid4()`.

### core/30-ops.md
- the pinned release leaves full security support, never per-pack.
- All services deploy via `fabrik apply` (SSH + Docker Compose) on the `fabrik` network. Traefik routes external traffic — services do NOT bind host ports.
- **No `ports:` section.** All external traffic routes through Traefik. Never bind host ports. See Docker Port Security below. **12‑Factor VII (Port binding):** "the app is self‑contained and exports HTTP by binding to a port; it does not rely on runtime injection of a webserver" — which is exactly WHY no host `ports:`.
- **`container_name: <name>` is mandatory.** Same `_validate_compose()` gate refuses any service without it. Stable names are required so Gatus endpoints, inter-service URLs, and `docker exec`/`docker inspect` keys don't drift per redeploy. Use the bare service name (`browserless`, `gotenberg`, `meilisearch`, `glitchtip-web`, `site-provisioner`, etc.) — never UUID-suffixed names.
- gets one (ruling D-052) — see `core/60-watchdog.md`. Do not author a `watchdog: { enabled: false }` opt-out; if a project genuinely cannot host the sidecar, that is a ruling to obtain, not a default to flip.
- path before the flag goes in the spec, and assert target health (`/api/v1/targets` → `up`), never a bare `curl` of a path you assumed.
- VOLUME gets a plan pointed at a directory that never exists — a paper backup that reads green and archives nothing.  If the data is a volume, say so in the spec comment and rely on the global `docker-volumes` plan; never let a service-named plan be mistaken for the protection.
- health-enabled service can NEVER pass `up -d --wait` on a fresh database, and the deploy hangs to timeout.  An init the deploy cannot perform itself is a runbook step the plan MUST own.
- `fabrik redeploy <app>` SSHes to the VPS and runs `git pull` + `docker compose up -d --wait` against the **GitHub remote**, NOT the local `/opt/<app>` clone. Skipping `git push` redeploys the previous remote commit — the VPS never sees local changes.
**Mandate:** build → release → run are strictly separated. Releases are IMMUTABLE; the git SHA is the release ID. NEVER hot‑patch a running container (no `docker exec` to edit code/config in place, no in‑place code mutation on the VPS). Any change = a new build + a new release via `fabrik apply` / `fabrik redeploy`.
- Runtime database migrations that modify the app container (migrations MUST be run as separate deploy‑time steps)
**Place a service next to its data.** A spoke-hosted service reaches `postgres-main`/`redis-main` over the WireGuard mesh, and that hop is cross-Atlantic (Coventry ↔ LA) on EVERY query — a per-request chatty service pays it hundreds of times per page. So a DB-chatty service targets vps1; a spoke earns a service whose data traffic is light, batched or cached; a service PINNED to a spoke by hardware (GPU) batches or caches its data access — the data never moves off vps1. Measure before choosing (`ping 10.99.0.1` from the spoke, and the request's query count), never assume — the correctness rule ("container DNS, never localhost") says nothing about latency.
**Mandate:** WSL dev and the VPS run the SAME backing services (PostgreSQL + Redis), same major version. NEVER substitute a different backing service in dev (no SQLite standing in for Postgres, no in‑memory dict standing in for Redis). The same code must run unmodified in both environments.
- WSL runs PostgreSQL + Redis at the SAME MAJOR as the VPS containers — probe the live truth, never copy a tag from a doc: `ssh vps "sudo docker inspect postgres-main redis-main --format '{{.Config.Image}}'"` (2026-09-01: `postgres:16-alpine` · `redis:7-alpine` — upstream official images, outside OUR-image Alpine ban per § Banned Patterns)
**Invariant:** Never use `ports:` in compose.yaml to expose internal services to the host. All external traffic must go through Traefik.
**Health endpoints (`/health`, `/healthz`, `/metrics`, `/api/health`) bypass Authelia on all services** — required for Gatus and Prometheus monitoring. The bypass is **resource-based, not domain-bound** — applies on every domain routed through Authelia (hub direct + spokes via `authelia-vps1@file` middleware). Never protect these paths.
**CRITICAL:** Use `web`/`websecure` in Traefik labels — never `http`/`https` (those entrypoints do not exist). The scaffolder emits the correct entrypoint names; if you hand-write labels, match these exactly.
**Mandate:** migrations and admin tasks run as a ONE‑OFF process against the DEPLOYED image + env — identical environment to regular processes. NEVER run admin tasks from a laptop against prod, NEVER via `docker exec` into a live container, and **ABSOLUTELY NEVER auto-run migrations from app startup/`lifespan`** (concurrent replicas race the Alembic version table → wedged deploy).
- > **`fabrik run` and `.fabrik/hooks/post-deploy/` do NOT exist** — the real CLI answers `Error: No such command 'run'`, the hook path appears nowhere in the platform, and `_post_deploy_sync()` (`cli.py:64`) only refreshes `data/projects.yaml`; an agent following either ships a deploy where migrations never run. Do not re-add either without a `path:line` in `src/fabrik/` that executes it.
**Processes are share-nothing:** any state shared across requests MUST go to Redis (`redis-main`) with a TTL. A project using Redis for sessions MUST declare `shape.needs_cache: true` in `specs/services/<id>.yaml`, or `fabrik apply` skips the Redis registrar and the deploy is silently broken.
- "A twelve-factor app never relies on implicit existence of system-wide packages"
**Mandate:** any binary the app shells out to (ffmpeg, yt-dlp, poppler, tesseract…) MUST be `apt-get install`-ed in the Dockerfile, with a `shutil.which()` startup probe that fails fast. **The pinned base image is the version boundary** — exact `=version` apt pins are banned: they break on every Debian point release as old debs leave the mirrors (the "works then mysteriously breaks" class this section exists to prevent); the codename pin + image digest give the reproducibility. Never assume `curl`/ImageMagick/ffmpeg exist in the image — they don't by default.

### 12-FACTOR (all twelve axes)
- I codebase: shared code → fabrik-lib, never two apps in one repo
- II deps: every shelled-out binary installed + pinned in the Dockerfile
- III config: granular env vars; no secrets in code; no grouped env sets
- IV backing services: swappable by DSN/config change only
- V build/release/run: releases immutable; never hot-patch a container
- VI processes: stateless; session state → redis-main; no sticky sessions
- VII port binding: bind in-container; Traefik routes; no host ports:
- VIII concurrency: scale out; never daemonize or write PID files
- IX disposability: SIGTERM returns in-flight jobs to the queue; jobs idempotent
- X dev/prod parity: same backing services everywhere; no SQLite-for-Postgres
- XI logs: unbuffered stdout only; the app never writes/rotates a logfile
- XII admin: migrations/one-offs run against the deployed release, never startup

## MATCHED — packs whose globs hit the changed paths

### core/10-python.md  (hit: src/fabrik/cli.py, src/fabrik/portability.py, src/fabrik/preplan.py)
**`uv`** is the mandated Python package manager. Never use raw `pip`, `pip install`, `poetry`, or `pipenv`.
- Dependencies live in `pyproject.toml` + `uv.lock`. Do not modify these files unless the ticket authorises it.
- its own reviewed commit, never as a side effect of unrelated work.
- The one RULE: use SQLAlchemy async consistently — never mix `async def` with sync `.query().all()` (the Banned table row; the full session pattern is `25-data-postgres.md`'s).
- The canonical `engine`, `async_session`, and `get_db` are defined in `src/database.py` — owned by `25-data-postgres.md`. Import from there, never redefine:
**Config convention:** apps read a complete `DATABASE_URL` (`postgresql+asyncpg://user:pass@host:port/db`) and `REDIS_URL` from env. Discrete `DB_HOST`/`DB_PORT`/`DB_NAME`/`DB_USER`/`DB_PASSWORD` for the app to assemble are **banned**. The env supplies the complete URL — `localhost` in WSL, `postgres-main` on VPS — so the host concern is an env-layer responsibility, never code logic. See `30-ops.md` compose template for how discrete vars are interpolated into `DATABASE_URL` at the compose level.
- volume** (`30-ops.md` § Volumes), never in `.tmp` and never in `/tmp`.
**GlitchTip discipline:** unhandled exceptions (FastAPI 500s) are auto-captured by GlitchTip with full stacktraces. In the `except Exception` branch, log a **short event name + correlation_id** — never `logger.exception()` (that duplicates the traceback in Loki AND GlitchTip). See `55-observability.md` § Error Reporting for the full rule.
**Note:** Use the scaffolded logger: `from {package}.logger import get_logger` (see `55-observability.md` § Pre-Scaffolded Logging). Do not use `structlog.get_logger()` directly or `logging.getLogger(__name__)`.
- **Never a bare `asyncio.create_task()`** — an unreferenced task is silently garbage-collected and its exceptions vanish. Hold the reference and await it, or use `asyncio.TaskGroup`.
- **`datetime.now(UTC)`, never `datetime.utcnow()`** — deprecated and naive; naive datetimes are a real cross-service defect class.
- Ruff's selected rule-sets MUST include `ASYNC` (blocking IO in async code — machine-enforces this pack's hardest-to-review rule), `B` (bugbear) and `S` (bandit) alongside the defaults; configured in `pyproject.toml`, emitted by the scaffolder.
- Production services run via `uvicorn` CLI in the Dockerfile, not `uvicorn.run()` in code. Base image is always the pinned Debian `-slim` variant on `linux/amd64` (the variant is pinned fleet-wide in `30-ops.md` § Container Base Images — change it THERE, never per-repo). Never use Alpine — musllinux wheels exist now (PEP 656) but coverage is still partial, source builds are dramatically slower, and musl's allocator/stack defaults degrade CPython; the trade never pays on this fleet.
- `uvicorn.run()` is for local development only. Never ship it in production code.
- a fleet scaling decision (more containers), never a per-app flag.
**BANNED: grouped/named env config sets.** 12F is explicit — *"env vars are granular controls, each fully orthogonal to other env vars"* — so a `config/production.yml`, a `settings.production` group, or a `config/{dev,staging,prod}.yaml` tree is a violation. Env vars are granular and set **per deploy**, never batched into a named "environment".
**BANNED:** `logging.FileHandler`, `logging.handlers.RotatingFileHandler`, `TimedRotatingFileHandler`, `loguru` file sinks, any `*.log` file write, any in-app log rotation/retention/cleanup. The app never decides where logs are stored or routed — Docker → Promtail → Loki does. Full rule: `55-observability.md` § Logs.
**Factor XII — Admin processes. NEVER migrate from app startup.**
**BANNED: `alembic upgrade head` in FastAPI's `lifespan`, in an `@app.on_event("startup")`, or as an import side-effect.** With more than one replica (or a restart storm) two containers run `upgrade head` **concurrently** → they race the Alembic version table → duplicate DDL → **wedged deploy**. Migrations are a **one-off admin process against the deployed release**: `docker compose run --rm <svc> alembic upgrade head` (see `30-ops.md` § Release & Admin Processes).

### core/40-documentation.md  (hit: docs/CONFIGURATION.md, docs/QUICKSTART.md, docs/preplans/README.md)
- > **⚠️ `docs/OPERATIONS.md` + `docs/DEPLOYMENT.md` are FLEET-AI INTERFACES, not just docs (D-065).**
- **Tier-1 (author → verify → converge; the author leg is NATIVE while the pool is OFF, D-181 — `scripts/doc_reconcile.py`'s pool author cannot dispatch):** for each **mechanically-detectable** doc whose Doc-Sync trigger fired (`docs/QUICKSTART.md` · `docs/CONFIGURATION.md` · `docs/data-contract.md` · `docs/SERVICES.md` · `docs/OPERATIONS.md` — the reliable-signal subset), `scripts/doc_reconcile.py` dispatches a cheap OpenRouter-pool author (`libs.subagents`, `pick_models("docs")`) to emit a **minimal structured patch**, **verifies it before applying** (a symbol cross-check catches invented endpoints; the orchestrator injects a higher-assurance native-Claude verify), and loops to a zero-edit round. Runs per phase in `/fabrik-execute-plan`; never blocks (fail-safe). The other docs (CHANGELOG, INDEX, FEATURES, RESILIENCE, PORTS, the READMEs, `db/schema.sql`, …) have no reliable mechanical content-signal → they rely on the touch-on-change backstop below + your own edit (force-update, not force-correct).
- The SSOT is the type-aware registry (`scripts/enforcement/_doc_registry.py::PROJECT_DOCS`) — this table is its project-facing rendering, kept in step, never a second truth. `/fabrik-plan-after-chat` (the plan set's spine + tickets — the ticket-format authority) injects these rows per ticket as its `Docs:` line.
- Standalone work (not plan execution) → `Agent-Role: primary`. Trailers go below a blank line, above `Co-Authored-By`. ⚠️ The trailer block must be its OWN paragraph with NO blank line inside it: git parses only the LAST paragraph, and only if it is all-trailers. A blank line before `Co-Authored-By:` demotes everything above it to prose; so does a prose line glued to the top of the block. Measured 2026-08-15: 200 of the last 200 hub commits carried `Agent-Role:` and only 10 parsed, because the old example here shipped the blank line.
- **⚠️ Link it or it is decoration.** *Measured:* requests for files that do NOT exist came ~zero from AI bots — agents never go looking. It follows (inference, not measurement) that a file only gets read when something points at it: reference it from the docs index or README.
- ⚠️ **In THIS repo `llms.txt` is GENERATED** (`scripts/generate_capability_index.py`, refreshed daily) — never hand-edit it; change the generator. A project writing one by hand owns it.
- either way. Cheap and reversible — never at the expense of `OPERATIONS.md`/`DEPLOYMENT.md`, which are the load-bearing agent interfaces (D-065).
- **No skipped heading levels** — `##` to `###`, never `##` to `####`
- **Fenced code blocks only** — never indented code (AI treats it inconsistently)

### core/45-testing-strategy.md  (hit: tests/test_preplan.py, tests/test_scaffold.py, tests/test_scaffold_fix.py)
- **Behavior Contract**: every ticket enumerates its distinct **user-observable behaviors / acceptance criteria** and tests **each one** — one high-value integration/E2E test per behavior, risk-ordered, TDD for the risky ones. Skip trivia (getters / framework glue / config): **lean-but-complete, NOT 100%-line-coverage dogma**. Do not chase line coverage — ensure every behavior has a test that would fail if that behavior regressed. (Cheap pool subagents can author the per-behavior tests — the suggest→curate→author→fix workflow in `62-using-subagents.md` § Dispatch policy + `~/.claude/commands/fabrik-review.md`.)
- **No cosmetic assertions**: never assert against CSS classes, Tailwind utility strings, pixel measurements, or snapshot hashes. Assert application state and user-visible outcomes only.
- **Watched-fail-first** (for tests this change adds or modifies; trivia stays skipped per the Behavior Contract): a non-trivial behavior's test proves something only if it has been SEEN RED — either write it first and watch it fail, or (after the fact) neuter the fix/feature, prove the test goes red, then RESTORE and re-run to green. The neutered state is never staged, committed, or left in the tree. A green test never seen red is unverified — a suite can pass with its guard deleted.
- **Run tests**: `uv run pytest tests/` (never bare `pytest` — Fabrik uses `uv`) — **when the project has a `pyproject.toml`/`uv.lock`**. A `requirements.txt`-only project (no manifest) runs `.venv/bin/python -m pytest tests/` — the manifest clause chooses the RUNNER, it never disarms the mandate to run the suite (web-ecommerce-factory 01M1QEY5, 2026-09-05: the clause read as "does not apply here"). ⚠️ **Gate this on the manifest, because this line is FLOOR-injected into finder prompts and a vendored fabrik-lib MODULE has neither by design**: the module recipe ships `requirements.txt` (`fabrik-lib/README.md` § Creating a Reference Implementation), so `uv run` cannot resolve it and `python3 -m pytest` is the only thing that works. Telling a finder the sole working … (wrapped further — read the pack)
- **Zero-mock database policy**: never mock SQLAlchemy, SQLModel, or database sessions. All backend tests execute against a real PostgreSQL instance.
- **`ASGITransport` never runs lifespan** — anything the app initializes at startup (scaffolded apps are lifespan-based) silently does not exist in tests; wrap with `asgi-lifespan`'s `LifespanManager` when a test needs startup state.
- Use `structlog` in test helpers if logging is needed — never `print()`. See `55-observability.md`.
- **Never stub a server action from Playwright** — the server is the E2E boundary; stubbing belongs in the unit lane where the action is a plain function.
- Run Playwright against the PRODUCTION build (`next build && next start`), never the dev server.
- All locators must be **semantic**: `page.getByRole('button', { name: /submit/i })`. Never use CSS selectors or XPath.
- Launch Playwright's **bundled Chromium** (`channel: 'chromium'`) — stable Chrome/Edge removed the `--load-extension` / `--disable-extensions-except` side-load flags (Chrome 137/139), so those args only work under bundled Chromium, never installed stable Chrome.
- Run `@axe-core/playwright` with **`bypassCSP: true`** (the non-relaxable extension CSP otherwise makes axe throw on `chrome-extension://` pages); keep `@axe-core/playwright` a **dev-dependency only** (MPL-2.0 — never bundled into the shipped artifact). Gate bundle size with `size-limit` **per surface** (popup / side-panel / content-script). Full loop: `chrome-ext/70-chrome-ext.md` § Testing & UI Verification.
- Keep the generated types committed and re-generate on schema changes (`uv run python -c "import json; from <package>.main import app; print(json.dumps(app.openapi()))" > openapi.json` — the scaffold emits `src/<package>/main.py`, never a flat `src/main.py`, so `src.main` imports nothing).
**BANNED in tests:**
| A GUARD proven only by the ONE spelling of the defect you already fixed | Write the guard's subject five LEGITIMATE ways — five a DIFFERENT author would plausibly write, not five typos of yours — and count how many it still catches; one of five means it is keyed on your fix, not on the class — and one of five is the FLOOR of the failure, never its definition: four of five is a partial class and is reported as four of five. This is IN ADDITION to red-on-revert below, not a rival bar: that one proves the guard fires at all, this one proves it fires on the class. ⚠️ Cheapest ways to satisfy it WITHOUT the outcome (`CLAUDE.md` § UNIVERSAL governance markers, the entry whose anchor is **you get the behavior you measure** — search the ANCHOR, not the rule name: the project-facing contract lists that section by anchor alone and carries the name `cobra-effect` nowhere): (i) write five near-identical spellings and count 5/5; (ii) ship at 2/5 and REPORT it, needing no fabrication at all, in the hope that a reported count reads as a passed one — it does not: under 5/5 is a finding; (iii) claim the exercise and record nothing, since the five are never committed. So the bar is TWO things and needs both: **the five go IN the test file as executable CASES**, never a comment — a comment cannot go RED, so nothing can falsify it, and that is the objection, not that it records nothing — **and anything under 5/5 is a finding, not a pass**. ⚠️ Two paths this row does NOT close, stated rather than pretended away: you can shrink the SUBJECT until five legitimate spellings all land inside what the guard already catches (nothing is fabricated; the claim narrowed, not the guard), and an honest 4/5 — real information, 80% of the class — costs the author something to report, so the cheapest response to it is silence. Report the count you got either way — a 4/5 with the miss NAMED is a finding someone can act on, and a 5/5 nobody can execute is not a pass at all. Measured 4× in one day across 2 repos (01M1S4D78KRM0ZSYDNGTHS9HYQ), and once more the day this row landed: a contract-parity grader that read the LIVE file instead of the tree under test stayed green under the exact drift it existed to catch |
| A test THIS change adds/modifies that was never seen red (no fail-first, no red-on-revert proof) | Watch it fail first, or neuter the change → prove red → restore → re-run green |
- [ ] Destructive DB tests call `require_throwaway(TEST_DATABASE_URL)` before connecting — never point them at a dev/shared DB.

# promote-to-check_*: 82 injected mandate(s) look deterministically greppable — their backtick literals, one line each (the full mandates are ABOVE, not repeated: re-emitting ~20 FLOOR lines verbatim doubled the rubric and got it skimmed — web-ecommerce-factory 01M1QEY5, 2026-09-05)
- `fabrik-lib/fastapi-user-auth` `DELETE … RETURNING` `jti` `agents-fabrik.md § Supabase`
- `chrome-extension` `chrome.identity.launchWebAuthFlow` `https://<ext-id>.chromiumapp.org/` `chrome.storage.session`
- `desktop-app` `safeStorage` `desktop-app/72-desktop.md`
- `fabrik` `X-Internal-Token` `internal_auth.py` `hmac.compare_digest` `APIKeyHeader`
- `auth.uid()` `current_tenant_id()` `NULL` `EXCEPTION WHEN OTHERS THEN RETURN NULL` `SELECT auth.uid()` `NULL`
- `openssl rand -hex 32`
- `algorithms=["HS256"]` `alg` `alg: none`
- `redis-main`
- `expo-secure-store` `80-mobile.md`
- `localStorage` `sessionStorage`
- `chrome.storage.session` `TRUSTED_CONTEXTS` `chrome.runtime.sendMessage` `chrome.identity.launchWebAuthFlow` `code_verifier` `crypto.subtle` `storage.session`
- `x-middleware-subrequest` `middleware.ts` `proxy.ts` `middleware.ts`
- `CORSMiddleware` `allow_origins`
- `X-Frame-Options: DENY` `frame-ancestors`
- `APIKeyHeader` `require_api_key` `SERVICE_API_KEY` `PROXY_API_KEY` `python-api` `internal_auth.py` `metrics.py` `/metrics` `SERVICE_INTERNAL_SECRET_KEY`
- `os.getenv("KEY", "default")` `config/production.yml` `settings.production`
- `expo-secure-store`
- `^/api/` `/api/*` `/api/v1` `/api/*` `shape.bearer_bypass_prefix: "^/api/v1"` `fabrik apply` `^/` `orchestrator/verifier.check_api_bypass` `/api/*` `^/api/`
- `postgres-main` `fabrik-lib/rag` `postgres:16-alpine` `plpgsql` `postgres-main`
- `postgres-main` `docs/DECISIONS.md`
```
