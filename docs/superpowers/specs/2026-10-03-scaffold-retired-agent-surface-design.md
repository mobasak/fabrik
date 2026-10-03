# Scaffold: stop emitting the retired Kilo/Traycer/Windsurf agent surface

Status: DRAFT
Size: small (≈140 lines, 4 files)
Profile: delta — every intake item maps to code that exists today: `src/fabrik/scaffold.py` (`create_project`,
`fix_project`, `_layer_preplan_into_project`, `_DROID_GITIGNORE_BLOCK`), `src/fabrik/preplan.py`, `src/fabrik/cli.py`
(`--from-preplan`), `src/fabrik/portability.py` (a docstring list) and the sync manifest `scripts/fabrik_synced_manifest.py`. No new persona, consumer or service.

Mail: 01M407YP (infra → fleet). Rulings: D-514 (development runs on Claude Code in VS Code and the CLI; Windsurf,
Traycer and the Kilo CLI are not used), D-364 (Kilo CLI retired). Beat: fleet (scaffolding); the sync-manifest and
governance-template half is infra's.

## Personas

- **The operator scaffolding a project** (`fabrik scaffold`, `fabrik scaffold --from-preplan`): gets a tree with no
  file whose only reader is a retired tool.
- **An agent working in a project** (Claude Code): reads CLAUDE.md, AGENTS.md and `docs/`; finds the pre-plan through
  the governance line, not an injected line that the next sync removes.
- **The operator running `fabrik fix`** on an existing project: the scaffold-owned Traycer markers are removed, and
  nothing they did not create is touched.

## Goal

A new project scaffolded today, and an existing project after `fabrik fix`, carries no file whose only reader is a
retired tool, and loses nothing a live tool reads.

## Why this exists

`fabrik scaffold` is the generator: each stale artifact is re-created in every new project, and `fabrik fix` re-adds
them to existing ones (`scaffold.py:7521-7553`). Three kinds of residue remain:
1. `.droid/review-context/`, `.droid/traycer-reports/` and the Kilo cache and review lines of the `.droid` gitignore
   block — nothing live reads them.
2. `AGENTS-compact.md` and `opencode.json` — read only by Kilo/opencode, kept alive by one gate check.
3. The `Preplan:` reference written into "all 4 AI guardrail files" — all four are fleet-synced, so the next
   governance sync silently overwrites the injected line: the mechanism cannot work.

## What exists today (grounded)

| Artifact | Written by | Live reader | Verdict |
|---|---|---|---|
| `.droid/review-context/` | `scaffold.py:495`, `:1134-1137`; fix `:7531-7536` | none — `scripts/enforcement/check_doc_sprawl.py:289` only BLOCKS new files there; the writers `scripts/traycer_agents_fixed/*.sh` have no caller | dead |
| `.droid/traycer-reports/` | `scaffold.py:496`, `:1139-1142`; fix `:7539-7544` | `scripts/traycer_write_report.py:178`, no caller | dead |
| `.droid/kilo_usage.jsonl`, `reviews/`, `kilo_models_cache.json`, `.kilo_cache_last_refresh` (gitignore lines `scaffold.py:550-553`) | — | `scripts/archived/kilo_code_review.py` (RETIRED_CORE_SCRIPTS, `fabrik_synced_manifest.py:73`), `dev_tracker.py:97` (dead) | dead |
| `.droid/docs_queue/`, `.droid/docs_log/` (gitignore `:554-555`) | `scripts/docs_updater.py:107-108`, at import | created by every tier-3 gate run (`final_gate.py:2362`) and `work.py:1218` | **live — keep** |
| `.droid/dev_tracker.db` | `scripts/dev_tracker.py:24` | callers: only `kilo_terminal_runner.py:809`, itself uncalled; hub DB last written 2026-04-10 | dead |
| `AGENTS-compact.md` | synced (`fabrik_synced_manifest.py:102`); scaffold `:1324-1327`; fix `:7470-7477` | `opencode.json:4` (Kilo/opencode); gate `scripts/enforcement/check_opencode_json.py:21-23` (`final_gate.py:2082`) | dead tool, live gate |
| `opencode.json` | synced (`:103`); scaffold `:1400-1401` (unconditional `shutil.copy` — raises if the hub file is gone); fix `:7496-7500`, dry run `:7583-7585` | Kilo/opencode only | dead tool, live gate |
| `scripts/kilo_47_agents_final.json` (in projects) | scaffold `:1379-1384`; fix `:7512-7518`, dry run `:7593-7595`; in no manifest list | hub-side only (`scripts/kilo_model_sync.py:35`, the kilo-benchmarks tests); nothing in a project reads it | dead in projects |
| `.windsurfrules` | synced (`:104`); scaffold `:1253-1254` behind a fail-fast guard `:1240`, `:1244-1245`; fix `:7417-7422` behind `:7402`, `:7408-7409`, dry run `:7556-7557` | no agent; presence checks only in `sync_projects.py:368`, `health_summary.py:43` | dead, reporting-only checks |
| `docs/reference/kilo/` | synced (`:129`); scaffold `:1312-1318`; fix `:7448-7460` | `.windsurf/rules/ai/00-ai-model-selection.md:38`, `scripts/enforcement/check_routing_policy.py:5`, `scripts/enforcement/check_doc_index.py:51-55`, `src/fabrik/orchestrator/infrastructure.py:937`, daily `scripts/kilo-benchmarks/daily_refresh.sh` | **live — keep** (only the name is stale) |
| `Preplan:` line in AGENTS.md, CLAUDE.md, AGENTS-compact.md, `.windsurfrules` | `scaffold.py:6939-6998` (`_layer_preplan_into_project`, list `:6981-6986`), called `:7182-7183` | CLAUDE.md is read by Claude Code — but all four files are synced, so the next sync overwrites the line | broken mechanism |

`scripts/enforcement/check_synced_unmodified.py:125-126` fails the gate for any synced file DELETED in a project, so a file leaves projects
only by leaving the manifest first, then a sync. Nothing requires `.droid/` to exist.

## Rejected alternatives

- **B — remove from the scaffold only.** The governance sync re-delivers AGENTS-compact.md, opencode.json and
  `.windsurfrules` on the next run, and `check_synced_unmodified.py` fails any project that lacks them: dead on arrival.
- **C — also rename `docs/reference/kilo/`.** It is live (four readers plus a daily cron); renaming it is a separate
  cross-cutting change with no defect behind it. Out of scope.
- **D — keep injecting the Preplan line into CLAUDE.md only.** CLAUDE.md is synced too
  (`templates/governance/CLAUDE.md`); the line would still vanish on the next sync.

## Chosen approach — A, retire by owner, two independent merges

**Infra half (governance-sync path, full `/fabrik-review`):**
1. Drop `AGENTS-compact.md`, `opencode.json` and `.windsurfrules` from `GOVERNANCE_FILES`
   (`fabrik_synced_manifest.py:102-104`); the sync removes them and rewrites `.fabrik/synced.lock`.
2. Retire `scripts/enforcement/check_opencode_json.py` and its `final_gate.py:2082` row.
3. Add one generic line to `templates/governance/CLAUDE.md`: "If `docs/preplan.md` exists, read it before planning —
   it holds the project's pre-plan: problem, approach, constraints." This replaces the per-project injection and
   survives every sync.
4. Drop `.windsurfrules` from the presence lists in `sync_projects.py:368` and `health_summary.py:43`.
5. The other hub consumers of the three files, each a list or a check that names them: `scripts/final_gate.py:2425-2458`
   (`check_symlinks`), `scripts/enforcement/check_structure.py:20,34,47`, `scripts/sync_enforcement_to_projects.py:9`,
   `scripts/audit_all_projects.py:63-96`, `scripts/watch_enforcement_changes.sh:35-38`, and the synced-file rows of
   `docs/workflows/SCAFFOLD_STRUCTURE.md:81-84,138,165-166`.

**Fleet half (this spec's code; merges in either order with infra's):**
1. `_DROID_GITIGNORE_BLOCK` (`scaffold.py:548-557`) keeps `.factory/consultations/`, `.droid/docs_queue/`,
   `.droid/docs_log/`; the Kilo and Traycer lines go. The constant stays: eight per-type `.gitignore` writers embed it
   (`:1405`, `:4498`, `:4647`, `:4780`, `:5849`, `:6012`, `:6147`, `:6451`), and `_patch_droid_block` (`:7266`)
   replaces every `.droid/`/`.factory/` line of an existing root `.gitignore` with it, so `fix` drops the old lines.
   `_DROID_DIR_GITIGNORE` (`:699-708`) shrinks to a comment, `*` and `!.gitignore` (the directory stays ignored for
   `docs_queue/`/`docs_log/`); `_TRAYCER_REPORTS_GITIGNORE` (`:711-713`) is deleted.
2. `create_project` stops creating `.droid/review-context/` and `.droid/traycer-reports/` (`SHARED_DIRS :495-496`,
   `:1134-1142`) and stops copying `.windsurfrules` (`:1253-1254`, with its guard `:1240`, `:1244-1245`),
   AGENTS-compact.md (`:1324-1327`), `scripts/kilo_47_agents_final.json` (`:1379-1384`) and `opencode.json`
   (`:1400-1401`); the stale comments at `:290-291` go. `docs/reference/kilo/` stays.
3. `fix_project` stops (re)creating the same items, each with its dry-run twin: `.windsurfrules` (`:7417-7422`, guard
   `:7402`, `:7408-7409`; dry run `:7556-7557`), AGENTS-compact.md (`:7470-7477`; `:7569-7571`), `opencode.json`
   (`:7496-7500`; `:7583-7585`), `kilo_47_agents_final.json` (`:7512-7518`; `:7593-7595`), the Traycer markers
   (`:7530-7544`; `:7605-7613`). In an existing project it removes the two scaffold-owned markers
   (`.droid/review-context/.gitkeep`, `.droid/traycer-reports/.gitignore`) and then each directory only when it is
   empty, reporting what it removed and what it left; the dry run reports the same without deleting. `.droid/.gitignore`
   and the root `.gitignore` are rewritten to the reduced content (`:7524-7528`, `:7546-7553`).
4. `_layer_preplan_into_project` (`:6939-7000`) keeps copying the pre-plan to `docs/preplan.md` and stops writing
   into guardrail files. The docstrings that describe the injection change with it: `create_project` (`:7104-7117`),
   the function's own (`:6940-6960`), `preplan.py:1-8`, the `--from-preplan` help (`cli.py:1806-1818`), the `preplan`
   group (`cli.py:2198-2211`), and the governance list in `portability.py:416-417`.
5. `.droid/dev_tracker.db`: not created, not ignored, no change needed. Retiring `dev_tracker.py` and
   `kilo_terminal_runner.py` (hub scripts, infra) is filed separately.

## The delta

| File | Change |
|---|---|
| `src/fabrik/scaffold.py` | the fleet half, steps 1-4 |
| `src/fabrik/preplan.py` | docstring: no "4 guardrail files" |
| `src/fabrik/cli.py` | `--from-preplan` help and the `preplan` group docstring |
| `src/fabrik/portability.py` | the governance-file list in a docstring (`:416-417`) |
| `tests/test_scaffold.py` | the `.droid` block, fix-structure and traycer tests (`:26-51`, `:186-308`, `:311-349`, `:527-546`) rewritten to the reduced surface; a fix test that removes the empty markers and keeps a non-empty directory |
| `tests/test_scaffold_fix.py` | the `kilo_47_agents_final.json` refresh tests (`:262-298`) become "not copied"; `_source_root` (`:15-19`) removed if unused |
| `tests/test_preplan.py` | the injection tests (`:175-237`) become "copied to `docs/preplan.md`, no guardrail file touched" |
| docs | `docs/QUICKSTART.md:70-77`, `docs/reference/architecture.md:255`, `docs/workflows/SCAFFOLD_STRUCTURE.md:27,70,147` |

## Contract deltas

- `fabrik scaffold` output: the five artifacts in the table above are no longer emitted. Mirror: a tool that expects
  `.droid/review-context/` to exist breaks. Measured: the only reader is `check_doc_sprawl.py:289`, which tests a path
  prefix and does not require the directory.
- `fabrik fix`: removes two marker files and their empty directories. Mirror: a project that keeps hand-written notes
  in `review-context/` keeps them; fix never removes a non-empty directory.
- `--from-preplan`: guardrail files are no longer edited. Mirror: an agent that read the injected line now relies on
  the governance line, which lands with infra's half. If fleet's half lands first, a project scaffolded
  `--from-preplan` in the window carries `docs/preplan.md` with no pointer until infra's line syncs — the old pointer was
  wiped by the first sync anyway, so nothing is lost that survived before.
- Merge order: either order is safe. Fleet-first: `fix` no longer writes the three synced files but never deletes them,
  so the sync keeps delivering them until infra's merge removes them; the scaffold no longer depends on hub copies infra
  may delete. Infra-first: until fleet merges, `create_project` still copies `opencode.json` unconditionally
  (`:1400-1401`) and raises on a missing `.windsurfrules` (`:1244-1245`), so infra keeps the hub copies until then.

## Cost

About 140 code lines in four fleet files (mostly deletions) plus the test rewrites in three test files and three
doc edits. No runtime cost and no new dependency. Infra's half is about ten files plus one governance sync.

## Validation

1. Scaffold a project in a temp dir: no `.droid/review-context`, no `.droid/traycer-reports`, no AGENTS-compact.md,
   `.windsurfrules`, `opencode.json` or `scripts/kilo_47_agents_final.json` written by the scaffold,
   `docs/reference/kilo/` present, and the root `.gitignore` carries the reduced block with no Kilo/Traycer line.
2. `fabrik fix` on a project with the old tree: the two markers and their empty directories are removed, a non-empty
   `review-context/` is kept and reported, nothing else is deleted; the three synced files are neither written nor
   deleted; the dry run reports the same and changes nothing.
3. `--from-preplan`: `docs/preplan.md` written; AGENTS.md and CLAUDE.md unchanged byte-for-byte.
4. After infra's merge, a governance sync on one project: AGENTS-compact.md, opencode.json and `.windsurfrules` gone,
   `check_synced_unmodified.py` green, the project's gate green.

## Decisions taken

- `.droid/` stays for `docs_queue/` and `docs_log/` (live writer); everything else under it is retired.
- `.droid/dev_tracker.db` is retired with its dead script (filed for infra).
- `docs/reference/kilo/` stays (live); its rename is out of scope.
- The pre-plan reaches agents through one generic governance line, not a per-project injection.

## Lifecycle

Two independent merges: infra's manifest/template/gate change and fleet's scaffold change. Projects converge on their next
governance sync (files removed) and their next `fabrik fix` (markers removed). Nothing touches a VPS.

## Intake Inventory

| I# | Item (anchored) | Disposition | Where |
|---|---|---|---|
| I1 | "scaffold.py:290-291 comments: Traycer Phases replace manual phase tracking" | IN | fleet half step 2 (comments dropped with the code) |
| I2 | "`.droid/review-context` and `.droid/traycer-reports` in SHARED_DIRS" | IN | fleet half steps 2-3 |
| I3 | "emit the .droid gitignore block and traycer-reports/" | IN | fleet half step 1 |
| I4 | "copy AGENTS-compact.md, the Kilo CLI bootstrap" | IN | infra step 1 + fleet step 2 |
| I5 | "inject a `Preplan:` line into all 4 AI guardrail files" | IN | infra step 3 + fleet step 4 |
| I6 | "`fabrik fix` re-adds `.droid/` to existing ones" | IN | fleet half step 3 |
| I7 | "The decision is whether to keep `.droid/dev_tracker.db`" | IN | Decisions taken (retired; script retirement filed) |
| I8 | infra's W-477e37cd retired-terms tripwire "waits on it" | OUT-OF-SCOPE | infra's own item W-477e37cd, unblocked by this spec's merge |
| I9 | `docs/reference/kilo/` copied by the scaffold | IN (kept) | What exists today; Rejected C |

Intake: 9 items — 8 IN, 1 OUT-OF-SCOPE (W-477e37cd, infra), 0 ASK.

## Constraints digest

| Rule | Verbatim | Where it binds |
|---|---|---|
| Synced surfaces are fleet-wide | "treat a synced-surface edit as hub-local (canonical list: `scripts/fabrik_synced_manifest.py`" — CLAUDE.md:308 | infra half: the manifest change ships to ~46 repos; full `/fabrik-review` |
| Behaviour Contract | "every ticket enumerates its distinct **user-observable behaviors / acceptance criteria**" — `.windsurf/rules/core/45-testing-strategy.md:20` | one test per Validation row |
| Watched-fail-first | "**Watched-fail-first** (for tests this change adds or modifies" — `45-testing-strategy.md:22` | the rewritten scaffold and preplan tests |
| Guard spellings | "A GUARD proven only by the ONE spelling of the defect you already fixed" — `45-testing-strategy.md:199` | the fix-removal test covers empty, non-empty and missing directories |
| No dependency edits | "Do not modify these files unless the ticket authorises it." — `.windsurf/rules/core/10-python.md:30` | no `pyproject.toml`/`uv.lock` change |

## External dependencies

No external facts: every claim is about hub code, grounded at path:line above.

## fabrik-lib verdict

Not applicable: the scaffold and its fix path are hub code, and no fabrik-lib module is involved.

## Shape / infra implications

None: no spec `shape:` field, registrar or VPS changes.

## Documentation landing sites

`docs/QUICKSTART.md:70-77` (the preplan comment and the AGENTS-compact line), `docs/reference/architecture.md:255`
(the `.droid/review-context/` row), `docs/workflows/SCAFFOLD_STRUCTURE.md:27,70,147` (the scaffold-emitted rows),
`CHANGELOG.md`. No file is added or removed, so `INDEX.md` is untouched. Infra owns `templates/governance/CLAUDE.md`,
the manifest docs and `SCAFFOLD_STRUCTURE.md`'s synced-file rows (infra half step 5).

## Open / blocking unknowns

None. The two halves are coupled only by the preplan pointer and by infra keeping the hub copies until fleet merges
(`§ Contract deltas`, merge order).
