# Scaffold: stop emitting the retired Kilo/Traycer/Windsurf agent surface

Status: CONVERGED 2026-10-03 (graded with plan-1 by /fabrik-plan-review) — approved by the operator 2026-10-03 (D-529)
Size: small (≈190 lines, 4 files)
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

A new project scaffolded today, and an existing project after `fabrik fix`, carries no Kilo, Traycer or AGENTS-compact
file whose only reader is a retired tool, and loses nothing a live tool reads. The Windsurf `.windsurf/hooks.json` and
`.windsurf/workflows` ride a different sync list and are retired separately (W-a24fe72a).

## Why this exists

`fabrik scaffold` is the generator: each stale artifact is re-created in every new project, and `fabrik fix` re-adds
them to existing ones (`scaffold.py:7521-7553`). Three kinds of residue remain:
1. `.droid/review-context/`, `.droid/traycer-reports/` and the Kilo cache and review lines of the `.droid` gitignore
   block — nothing live reads them.
2. `AGENTS-compact.md` and `opencode.json` — read only by Kilo/opencode, kept alive by one gate check.
3. The `Preplan:` reference written into "all 4 AI guardrail files" — all four are fleet-synced, and the fleet sync
   runs with `--force` (`scripts/governance_sync_postcommit.sh:110`), so the next sync overwrites the injected line:
   the mechanism cannot work.

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
| `scripts/kilo_47_agents_final.json` (in projects) | scaffold `:1379-1384`; fix `:7512-7518`, dry run `:7593-7595`; in no manifest list, so no sync prunes it | hub-side only (`scripts/kilo_model_sync.py:35`, the kilo-benchmarks tests); nothing in a project reads it | dead in projects (38 project copies) |
| `.windsurf/hooks.json` | scaffold `_copy_windsurf_hooks` (`:526-539`, called `:1372`); fix `:7479-7484`; synced via `AGENT_HOOK_FILES` (`fabrik_synced_manifest.py:272`) | Windsurf Cascade only; gate consumer `check_hooks_index.py` | out of scope — W-a24fe72a |
| `.windsurfrules` | synced (`:104`); scaffold `:1253-1254` behind a fail-fast guard `:1240`, `:1244-1245`; fix `:7417-7422` behind `:7402`, `:7408-7409`, dry run `:7556-7557` | no agent; presence checks only in `sync_projects.py:368`, `health_summary.py:43` | dead, reporting-only checks |
| `docs/reference/kilo/` | synced (`:129`); scaffold `:1312-1318`; fix `:7448-7460` | `.windsurf/rules/ai/00-ai-model-selection.md:38`, `scripts/enforcement/check_routing_policy.py:5`, `scripts/enforcement/check_doc_index.py:51-55`, `src/fabrik/orchestrator/infrastructure.py:937`, daily `scripts/kilo-benchmarks/daily_refresh.sh` | **live — keep** (only the name is stale) |
| `Preplan:` line in AGENTS.md, CLAUDE.md, AGENTS-compact.md, `.windsurfrules` | `scaffold.py:6939-6998` (`_layer_preplan_into_project`, list `:6981-6986`), called `:7182-7183` | CLAUDE.md is read by Claude Code — but all four files are synced, so the next sync overwrites the line | broken mechanism |

`scripts/enforcement/check_synced_unmodified.py:125-126` fails the gate for any synced file DELETED in a project, so a file
leaves projects only by leaving the manifest first — and de-listing alone deletes no project copy (`§ Chosen approach`,
infra step 1). Nothing requires `.droid/` to exist.

## Rejected alternatives

- **B — remove from the scaffold only.** The governance sync re-delivers AGENTS-compact.md, opencode.json and
  `.windsurfrules` on the next run, and `check_synced_unmodified.py` fails any project that lacks them: dead on arrival.
- **C — also rename `docs/reference/kilo/`.** It is live (four readers plus a daily cron); renaming it is a separate
  cross-cutting change with no defect behind it. Out of scope.
- **D — keep injecting the Preplan line into CLAUDE.md only.** CLAUDE.md is synced too
  (`templates/governance/CLAUDE.md`); the line would still vanish on the next sync.
- **E — keep the two create-time copies but make them conditional** (copy `.windsurfrules`/`opencode.json` only when
  the hub has them), so either merge order is safe. Rejected: it keeps copy code whose only purpose is a retired tool,
  and the order it removes costs one line in the merge request; infra step 6 removes the hub copies instead.

## Chosen approach — A, retire by owner, two merges, infra's first

**Infra half (governance-sync path, full `/fabrik-review`; merges FIRST):**
1. Drop `AGENTS-compact.md`, `opencode.json` and `.windsurfrules` from `GOVERNANCE_FILES`
   (`fabrik_synced_manifest.py:102-104`) AND remove the projects' copies: de-listing alone deletes nothing — the
   governance loop only copies what is listed (`sync_enforcement_to_projects.py:2023-2030`) and the only prune is for
   retired scripts (`prune_retired_scripts`, `:1764`) — so the half needs a retired-governance list pruned the same way.
   Keep the HUB copies of `.windsurfrules` and `opencode.json` until fleet's half merges (`§ Contract deltas`).
2. Retire `scripts/enforcement/check_opencode_json.py` and its `final_gate.py:2080-2084` row (a blocking row: it exits 1
   on a missing `opencode.json`). This is what makes fleet's half safe to merge second.
3. Add one generic line to `templates/governance/CLAUDE.md`: "If `docs/preplan.md` exists, read it before planning —
   it holds the project's pre-plan: Idea, Project type, Shape preview, External deps, Domain, Success criteria, Out of
   scope, Open questions, VPS1 notes" (the nine sections of `preplan.py:10-20`). This replaces the per-project
   injection and survives every sync.
4. Drop `.windsurfrules` from the presence lists in `sync_projects.py:368` and `health_summary.py:43`.
5. The other hub surfaces that name the three files: `scripts/final_gate.py:2425-2458` (`check_symlinks`, defined but
   called by no gate row), `scripts/enforcement/check_structure.py:20,34,47`, `scripts/sync_enforcement_to_projects.py:9`,
   `scripts/audit_all_projects.py:63-96`, `scripts/watch_enforcement_changes.sh:35-38`, the generated
   `templates/governance/.worktreeinclude:11-13` (regenerated from the manifest), the governance-sync trigger regex
   (`.pre-commit-config.yaml:164`), `.windsurf/rules/core/40-documentation.md:45`, the synced `agents-fabrik.md` (`:10`,
   and `:398`, which states the four-file `Preplan:` injection fleet's half removes), and the synced-file rows of
   `docs/workflows/SCAFFOLD_STRUCTURE.md:81-84,138,165-166`.
6. After fleet's half merges: delete the hub copies of `.windsurfrules`, `opencode.json` and `AGENTS-compact.md`
   (nothing reads them once `_scaffold_shared` and `fix_project` stop copying them).

**Fleet half (this spec's code; merges after infra's):**
1. `_DROID_GITIGNORE_BLOCK` (`scaffold.py:548-557`) keeps `.factory/consultations/`, `.droid/docs_queue/`,
   `.droid/docs_log/`; the Kilo and Traycer lines go, and the writer comment above it (`:542-547`) names only
   `docs_updater.py`. The constant stays: eight per-type `.gitignore` writers embed it (`:1405`, `:4498`, `:4647`,
   `:4780`, `:5849`, `:6012`, `:6147`, `:6451`). `_patch_droid_block` (`:7266-7303`) today drops EVERY `.droid/` or
   `.factory/` line of an existing root `.gitignore`, a user's own included; it changes to drop only the lines the
   scaffold ever wrote — the current block's three plus the five retired ones — so a user's `.droid/<own>` line survives.
   `_DROID_DIR_GITIGNORE` (`:699-708`) and `_TRAYCER_REPORTS_GITIGNORE` (`:711-713`) are deleted: the scaffold no
   longer creates `.droid/` at all. Its only live writer, `docs_updater.py`, creates `.droid/docs_queue` and
   `.droid/docs_log` itself at import (`:107-108`), and the root block already ignores both.
2. `_scaffold_shared` (`def :1121` — every create-time copy below is inside it) loses `.droid/review-context` and
   `.droid/traycer-reports` from `SHARED_DIRS` (`:495-496`) and the whole `.droid` write block (`:1134-1142`, including
   the `.droid/.gitignore` write at `:1135`). It stops copying `.windsurfrules` (`:1253-1254`, with its guard `:1240`,
   `:1244-1245`), AGENTS-compact.md (`:1324-1327`), `scripts/kilo_47_agents_final.json` (`:1379-1384`) and
   `opencode.json` (`:1400-1401`). The stale comments at `:290-291` and `:1333-1334` go. `docs/reference/kilo/` stays.
3. `fix_project` stops (re)creating the same items, each with its dry-run twin: `.windsurfrules` (`:7417-7422`, guard
   `:7402`, `:7408-7409`; dry run `:7556-7557`), AGENTS-compact.md (`:7470-7477`; `:7569-7571`), `opencode.json`
   (`:7496-7500`; `:7583-7585`), `kilo_47_agents_final.json` (`:7512-7518`; `:7593-7595`), and the whole `.droid`
   block (`:7520-7544`; `:7597-7613`) — it no longer creates `.droid/` or writes `.droid/.gitignore`, and an existing
   `.droid/.gitignore` is left as it is (it still ignores the old runtime files of an existing project). When `.droid`
   is a real directory it removes the two scaffold-owned markers (`.droid/review-context/.gitkeep`,
   `.droid/traycer-reports/.gitignore`) and then each directory only when it is empty; a symlinked or non-directory
   `.droid` is skipped and reported. It never acts through a symlink, never deletes a marker that is not a regular file,
   and reports — never raises on — a filesystem refusal. It also removes the project's
   `scripts/kilo_47_agents_final.json` when that is a regular file (38 project copies today; read only on the hub). The
   dry run reports exactly what the live run would do. The root `.gitignore` is still patched to the reduced block
   (`:7546-7553`) for every project. The `fabrik fix` command (`cli.py:2038-2060`) prints a removal as a removal, a kept
   directory as a note, and a refusal as a warning — never as "Added" — and does not claim the structure is complete
   when a refusal is listed; a refusal leaves dead residue, not a missing file, so it does not change the exit status.
4. `_layer_preplan_into_project` (`:6939-7005`) keeps copying the pre-plan to `docs/preplan.md` and stops writing
   into guardrail files; its closing log line (`:7002-7005`) stops claiming an injection. The docstrings that describe
   the injection change with it: `create_project` (`:7104-7117`), the function's own (`:6940-6960`), the caller comment
   (`:7179-7181`), `preplan.py:1-8`, the `--from-preplan` help (`cli.py:1806-1818`), the `preplan` group
   (`cli.py:2198-2211`), and the governance list in `portability.py:416-417`.
5. `.droid/dev_tracker.db`: not created, not ignored, no change needed — it exists only on the hub (0 of 40 project
   `.droid/` dirs hold one). Retiring `dev_tracker.py` and `kilo_terminal_runner.py` (hub scripts, infra) is filed
   separately.

## The delta

| File | Change |
|---|---|
| `src/fabrik/scaffold.py` | the fleet half, steps 1-4 |
| `src/fabrik/preplan.py` | docstring: no "4 guardrail files" |
| `src/fabrik/cli.py` | the `fabrik fix` report rendering; the `--from-preplan` help and the `preplan` group docstring |
| `src/fabrik/portability.py` | the governance-file list in a docstring (`:416-417`) |
| `tests/test_scaffold.py` | every test asserting the old block, the `.droid` files or the markers (`:26-51`, `:79-86`, `:89-127`, `:186-308`, `:311-349`, `:527-546`) rewritten to the reduced surface; the marker-removal and gitignore-patch tests |
| `tests/test_scaffold_fix.py` | the `kilo_47_agents_final.json` refresh tests (`:262-298`) become "removed from the project, never copied"; `_source_root` (`:15-19`) removed if unused |
| `tests/test_preplan.py` | the injection tests (`:175-237`) become "copied to `docs/preplan.md`, no guardrail file touched" |
| docs | see `§ Documentation landing sites` |

## Contract deltas

- `fabrik scaffold` output: the six artifacts of `§ What exists today` that the scaffold wrote (`.droid/review-context/`,
  `.droid/traycer-reports/`, `.windsurfrules`, `AGENTS-compact.md`, `opencode.json`,
  `scripts/kilo_47_agents_final.json`), `.droid/` itself with its `.gitignore`, and the five retired root `.gitignore`
  lines are no longer emitted. Mirror: a tool that expects `.droid/` or `.droid/review-context/` to exist breaks.
  Measured: `docs_updater.py:107-108` creates what it needs, and the only other reader, `check_doc_sprawl.py:289`, tests
  a path prefix and does not require the directory.
- `fabrik fix`: no longer creates `.droid/` or rewrites `.droid/.gitignore`; removes two marker files, their empty
  directories and `scripts/kilo_47_agents_final.json`; drops only scaffold-written lines from a root `.gitignore`. The
  markers are TRACKED in every scaffolded project (the initial commit is `git add .`, `scaffold.py:7191-7193`), so a fix
  run leaves tracked deletions uncommitted, as every other fix change is left for the project owner to commit. Mirror:
  six projects keep 30 files of their own in `review-context/` (measured 2026-10-03: apidoccreator 1, candle 1, seo 10,
  trade-intelligence 13, triggered-content-orchestration 1, web-scraper 4 — all Kilo/Traycer task notes); they are kept
  and reported, and because `.droid/.gitignore` is left alone their ignore rules do not change. A user's own `.droid/`
  ignore line — dropped by today's `_patch_droid_block` — now survives.
- `--from-preplan`: guardrail files are no longer edited. Mirror: an agent that read the injected line now relies on
  the governance line, which lands with infra's half first. The injected line never survived anyway: the fleet sync
  runs with `--force` (`governance_sync_postcommit.sh:110`), which overwrites a project copy whose md5 differs.
- Merge order: infra's half FIRST, fleet's second. Fleet-first breaks new projects: a project scaffolded in that window
  has no `opencode.json` but carries `check_opencode_json.py` (the scaffold copies all of `scripts/enforcement/`,
  `:1207-1215`), a blocking gate row (`final_gate.py:2080-2084`) that fails until a governance sync happens to run.
  Infra-first is safe if infra keeps the hub copies of `.windsurfrules` and `opencode.json` until fleet merges, because
  until then `_scaffold_shared` still copies `opencode.json` unconditionally (`:1400-1401`) and raises on a missing
  `.windsurfrules` (`:1244-1245`). Its one window: between the two merges a `fabrik fix` run copies the three files into a
  pruned project as untracked residue, and a `fabrik scaffold` run commits them in the new project's initial commit
  (`git add .`, `scaffold.py:7191-7193`); infra's prune (infra step 1) removes them on that project's next sync — for the
  scaffolded project a tracked deletion left for the owner to commit, as with the markers. Infra step 6 deletes the hub copies once fleet has merged.

## Cost

About 190 code lines in four fleet files (mostly deletions, plus the marker-removal helper and the fix report
rendering), the test rewrites in three test files, and the doc edits listed below. No runtime cost and no new
dependency. Infra's half is about fifteen files plus one governance sync.

## Validation

1. Scaffold a project in a temp dir: no `.droid/` at all, no AGENTS-compact.md, `.windsurfrules`, `opencode.json` or
   `scripts/kilo_47_agents_final.json` written by the scaffold, `docs/reference/kilo/` present, and the root `.gitignore`
   carries the reduced block with no Kilo/Traycer line.
2. `fabrik fix` on a project with the old tree: the two markers and their empty directories are removed and
   `scripts/kilo_47_agents_final.json` is removed; a non-empty `review-context/`, a symlinked marker directory, a marker
   that is a directory and a dangling-symlink marker are each left in place and reported; a symlinked or non-directory
   `.droid` is skipped; a refused removal is reported and the run continues; `.droid/.gitignore` is untouched; the three
   synced files are neither written nor deleted; a user's own `.droid/` ignore line survives; the dry run reports the
   same and changes nothing.
3. `--from-preplan`: `docs/preplan.md` written; AGENTS.md and CLAUDE.md unchanged byte-for-byte.
4. After infra's merge, a governance sync on one project: AGENTS-compact.md, opencode.json and `.windsurfrules` gone,
   `check_synced_unmodified.py` green, the project's gate green.

## Decisions taken

- The scaffold no longer creates `.droid/`; `docs_updater.py` creates its two directories itself and the root block
  ignores them. An existing `.droid/.gitignore` is left as it is.
- `fix` removes the dead project copy of `scripts/kilo_47_agents_final.json`.
- `.droid/dev_tracker.db` is retired with its dead script (filed for infra).
- `docs/reference/kilo/` stays (live); its rename is out of scope.
- `.windsurf/hooks.json` and `.windsurf/workflows` are out of scope here: their retirement runs through a different sync
  list (`AGENT_HOOK_FILES`, `fabrik_synced_manifest.py:272`) and a gate consumer (`check_hooks_index.py`), filed as
  W-a24fe72a.
- The pre-plan reaches agents through one generic governance line, not a per-project injection.
- Infra's half merges first (`§ Contract deltas`, merge order).

## Lifecycle

Two merges, infra's first: the manifest/prune/template/gate change, then fleet's scaffold change, then infra deletes the
hub copies (infra step 6). Projects converge on their next governance sync (files removed) and their next `fabrik fix`
(markers and the kilo_47 copy removed, left for the owner to commit). Nothing touches a VPS.

## Intake Inventory

| I# | Item (anchored) | Disposition | Where |
|---|---|---|---|
| I1 | "scaffold.py:290-291 comments: Traycer Phases replace manual phase tracking" | IN | fleet half step 2 (comments dropped, with `:1333-1334` and `:542-547`) |
| I2 | "`.droid/review-context` and `.droid/traycer-reports` in SHARED_DIRS" | IN | fleet half steps 2-3 |
| I3 | "emit the .droid gitignore block and traycer-reports/" | IN | fleet half step 1 |
| I4 | "copy AGENTS-compact.md, the Kilo CLI bootstrap" | IN | infra step 1 + fleet step 2 |
| I5 | "inject a `Preplan:` line into all 4 AI guardrail files" | IN | infra step 3 + fleet step 4 |
| I6 | "`fabrik fix` re-adds `.droid/` to existing ones" | IN | fleet half step 3 (`fix` no longer creates `.droid/`) |
| I7 | "The decision is whether to keep `.droid/dev_tracker.db`" | IN | Decisions taken (retired; script retirement filed) |
| I8 | infra's W-477e37cd retired-terms tripwire "waits on it" | OUT-OF-SCOPE | infra's own item W-477e37cd, unblocked by this spec's merge |
| I9 | `docs/reference/kilo/` copied by the scaffold | IN (kept) | What exists today; Rejected C |
| I10 | design critiques: `.windsurf/hooks.json` is a Windsurf-only file the scaffold still emits | OUT-OF-SCOPE | W-a24fe72a (different sync list and gate consumer) |
| I11 | design critique: same-ruling Kilo residue outside the scaffold (final_gate Kilo CLI row, `--post-kilo`, review-pack help) | OUT-OF-SCOPE | W-9a50a9a1 (infra) |

Intake: 11 items — 8 IN, 3 OUT-OF-SCOPE (W-477e37cd, W-a24fe72a, W-9a50a9a1), 0 ASK.

## Constraints digest

| Rule | Verbatim | Where it binds |
|---|---|---|
| Synced surfaces are fleet-wide | "treat a synced-surface edit as hub-local (canonical list: `scripts/fabrik_synced_manifest.py`" — CLAUDE.md:308 | infra half: the manifest change ships to ~46 repos; full `/fabrik-review` |
| Behaviour Contract | "every ticket enumerates its distinct **user-observable behaviors / acceptance criteria**" — `.windsurf/rules/core/45-testing-strategy.md:20` | one test per Validation row |
| Watched-fail-first | "**Watched-fail-first** (for tests this change adds or modifies" — `45-testing-strategy.md:22` | the rewritten scaffold and preplan tests |
| Guard spellings | "A GUARD proven only by the ONE spelling of the defect you already fixed" — `45-testing-strategy.md:199` | the marker-removal guard is proven on five legitimately different trees: a non-empty directory, a symlinked marker directory, a symlinked `.droid/`, a marker that is a directory, and a dangling-symlink marker |
| No dependency edits | "Do not modify these files unless the ticket authorises it." — `.windsurf/rules/core/10-python.md:30` | no `pyproject.toml`/`uv.lock` change |

## External dependencies

Every claim about the change is about hub code, grounded at path:line above. Two external facts back the approach,
fetched 2026-10-03 with WebFetch:
- Claude Code loads `./CLAUDE.md` (or `./AGENTS.md`) at the start of every session, and a CLAUDE.md can pull in another
  file with `@path/to/import` — "Imported files are expanded and loaded into context at launch alongside the CLAUDE.md
  that references them" (https://code.claude.com/docs/en/memory § Import additional files). So one line in the synced
  governance CLAUDE.md reaches every agent, which is why the per-project injection is replaced rather than moved
  (`§ Chosen approach`, infra step 3). The line stays plain text, not an `@docs/preplan.md` import, because most projects
  have no pre-plan and the page does not say what a missing import does.
- opencode loads extra instruction files only through the `instructions` key of `opencode.json` — "This takes an array of
  paths and glob patterns to instruction files" (https://opencode.ai/docs/config/). `opencode.json:4` lists
  `AGENTS-compact.md` there, so with opencode retired nothing loads it (`§ What exists today`).

## fabrik-lib verdict

Not applicable: the scaffold and its fix path are hub code, and no fabrik-lib module is involved.

## Shape / infra implications

None: no spec `shape:` field, registrar or VPS changes.

## Documentation landing sites

Every live doc that states the retired behaviour (`command grep -n 'review-context\|traycer-reports\|4 AI guardrail\|Preplan:'`
over `docs/`): `docs/QUICKSTART.md:70-77` (the preplan comment and the AGENTS-compact line),
`docs/reference/architecture.md:255-256` (the `.droid/review-context/` and `.droid/traycer-reports/` rows),
`docs/workflows/SCAFFOLD_STRUCTURE.md:27,70,147,263` (the scaffold-emitted rows and the `fix_project` repair line),
`docs/workflows/FABRIK_SCAFFOLD_WORKFLOW.md:266-268,444-446,604-613` (the `.droid/` tree and tables),
`docs/CONFIGURATION.md:596`, `docs/reference/fabrik-cli-reference.md:26`, `docs/preplans/README.md:25` and
`docs/traycer/fabrik-workflow.md:92` (the injection),
`docs/FEATURES.md:427,606` (a governance file, applied by the orchestrator), `CHANGELOG.md`. No file is added or
removed, so `INDEX.md` is untouched. Infra owns `templates/governance/CLAUDE.md`, the manifest docs and
`SCAFFOLD_STRUCTURE.md`'s synced-file rows (infra half step 5).

## Open / blocking unknowns

None. The halves are ordered (`§ Contract deltas`, merge order). Answered: six projects keep 30 files of their own
under `.droid/review-context/` (`§ Contract deltas`); the fix keeps and reports them.
