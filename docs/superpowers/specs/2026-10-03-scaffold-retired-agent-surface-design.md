# Scaffold: stop emitting the retired Kilo/Traycer/Windsurf agent surface

Status: DRAFT
Size: small (≈180 lines, 4 files)
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
   it holds the project's pre-plan: problem, approach, constraints." This replaces the per-project injection and
   survives every sync.
4. Drop `.windsurfrules` from the presence lists in `sync_projects.py:368` and `health_summary.py:43`.
5. The other hub consumers of the three files, each a list or a check that names them: `scripts/final_gate.py:2425-2458`
   (`check_symlinks`, defined but called by no gate row), `scripts/enforcement/check_structure.py:20,34,47`,
   `scripts/sync_enforcement_to_projects.py:9`, `scripts/audit_all_projects.py:63-96`,
   `scripts/watch_enforcement_changes.sh:35-38`, and the synced-file rows of
   `docs/workflows/SCAFFOLD_STRUCTURE.md:81-84,138,165-166`.

**Fleet half (this spec's code; merges after infra's):**
1. `_DROID_GITIGNORE_BLOCK` (`scaffold.py:548-557`) keeps `.factory/consultations/`, `.droid/docs_queue/`,
   `.droid/docs_log/`; the Kilo and Traycer lines go, and the writer comment above it (`:542-547`) names only
   `docs_updater.py`. The constant stays: eight per-type `.gitignore` writers embed it (`:1405`, `:4498`, `:4647`,
   `:4780`, `:5849`, `:6012`, `:6147`, `:6451`). `_patch_droid_block` (`:7266-7303`) today drops EVERY `.droid/` or
   `.factory/` line of an existing root `.gitignore`, a user's own included; it changes to drop only the lines the
   scaffold ever wrote — the current block's three plus the five retired ones — so a user's `.droid/<own>` line survives.
   `_DROID_DIR_GITIGNORE` (`:699-708`) shrinks to a comment, `*` and `!.gitignore` (the directory stays ignored for
   `docs_queue/`/`docs_log/`); `_TRAYCER_REPORTS_GITIGNORE` (`:711-713`) is deleted.
2. `_scaffold_shared` (`def :1121` — every create-time copy below is inside it) stops creating
   `.droid/review-context/` and `.droid/traycer-reports/` (`SHARED_DIRS :495-496`, `:1134-1142`) and creates `.droid/`
   itself before writing `.droid/.gitignore` (`:1135`; the two retired entries were the only thing that created it). It
   stops copying `.windsurfrules` (`:1253-1254`, with its guard `:1240`, `:1244-1245`), AGENTS-compact.md
   (`:1324-1327`), `scripts/kilo_47_agents_final.json` (`:1379-1384`) and `opencode.json` (`:1400-1401`). The stale
   comments at `:290-291` and `:1333-1334` go. `docs/reference/kilo/` stays.
3. `fix_project` stops (re)creating the same items, each with its dry-run twin: `.windsurfrules` (`:7417-7422`, guard
   `:7402`, `:7408-7409`; dry run `:7556-7557`), AGENTS-compact.md (`:7470-7477`; `:7569-7571`), `opencode.json`
   (`:7496-7500`; `:7583-7585`), `kilo_47_agents_final.json` (`:7512-7518`; `:7593-7595`), the Traycer markers
   (`:7530-7544`; `:7605-7613`). In an existing project it removes the two scaffold-owned markers
   (`.droid/review-context/.gitkeep`, `.droid/traycer-reports/.gitignore`) and then each directory only when it is
   empty. It never acts through a symlink (a symlinked `.droid/` or marker directory is skipped and reported), never
   deletes a marker that is not a regular file, and reports — never raises on — a removal the filesystem refuses. The
   dry run reports exactly what the live run would do. `.droid/.gitignore` and the root `.gitignore` are rewritten to the
   reduced content (`:7524-7528`, `:7546-7553`). The `fabrik fix` command (`cli.py:2038-2056`) prints a removal as a
   removal and a kept directory as a note, never as "Added", and still says the structure is complete when only notes
   remain.
4. `_layer_preplan_into_project` (`:6939-7005`) keeps copying the pre-plan to `docs/preplan.md` and stops writing
   into guardrail files; its closing log line (`:7002-7005`) stops claiming an injection. The docstrings that describe
   the injection change with it: `create_project` (`:7104-7117`), the function's own (`:6940-6960`), the caller comment
   (`:7179-7181`), `preplan.py:1-8`, the `--from-preplan` help (`cli.py:1806-1818`), the `preplan` group
   (`cli.py:2198-2211`), and the governance list in `portability.py:416-417`.
5. `.droid/dev_tracker.db`: not created, not ignored, no change needed. Retiring `dev_tracker.py` and
   `kilo_terminal_runner.py` (hub scripts, infra) is filed separately.

## The delta

| File | Change |
|---|---|
| `src/fabrik/scaffold.py` | the fleet half, steps 1-4 |
| `src/fabrik/preplan.py` | docstring: no "4 guardrail files" |
| `src/fabrik/cli.py` | the `fabrik fix` report rendering; the `--from-preplan` help and the `preplan` group docstring |
| `src/fabrik/portability.py` | the governance-file list in a docstring (`:416-417`) |
| `tests/test_scaffold.py` | every test asserting the old block or markers (`:26-51`, `:79-86`, `:89-127`, `:186-308`, `:311-349`, `:527-546`) rewritten to the reduced surface; the marker-removal and gitignore-patch tests |
| `tests/test_scaffold_fix.py` | the `kilo_47_agents_final.json` refresh tests (`:262-298`) become "not copied"; `_source_root` (`:15-19`) removed if unused |
| `tests/test_preplan.py` | the injection tests (`:175-237`) become "copied to `docs/preplan.md`, no guardrail file touched" |
| docs | see `§ Documentation landing sites` |

## Contract deltas

- `fabrik scaffold` output: the six artifacts of `§ What exists today` that the scaffold wrote (`.droid/review-context/`,
  `.droid/traycer-reports/`, `.windsurfrules`, `AGENTS-compact.md`, `opencode.json`,
  `scripts/kilo_47_agents_final.json`) and the five retired `.gitignore` lines are no longer emitted. Mirror: a tool that
  expects `.droid/review-context/` to exist breaks. Measured: the only reader is `check_doc_sprawl.py:289`, which tests a
  path prefix and does not require the directory.
- `fabrik fix`: removes two marker files and their empty directories, and drops only scaffold-written lines from a root
  `.gitignore`. Mirror: a project that keeps notes in `review-context/` keeps them; a user's own `.droid/` ignore line —
  dropped by today's `_patch_droid_block` — now survives.
- `--from-preplan`: guardrail files are no longer edited. Mirror: an agent that read the injected line now relies on
  the governance line, which lands with infra's half first.
- Merge order: infra's half FIRST, fleet's second. Fleet-first breaks new projects: a project scaffolded in that window
  has no `opencode.json` but carries `check_opencode_json.py` (the scaffold copies all of `scripts/enforcement/`,
  `:1207-1215`), a blocking gate row (`final_gate.py:2080-2084`) that fails until a governance sync happens to run.
  Infra-first is safe if infra keeps the hub copies of `.windsurfrules` and `opencode.json` until fleet merges, because
  until then `_scaffold_shared` still copies `opencode.json` unconditionally (`:1400-1401`) and raises on a missing
  `.windsurfrules` (`:1244-1245`). Its one window: a `fabrik fix` run between the two merges re-copies the three files
  into a project; infra's prune (infra step 1) removes them again on the next sync.

## Cost

About 180 code lines in four fleet files (mostly deletions, plus the marker-removal helper and the fix report
rendering), the test rewrites in three test files, and the doc edits listed below. No runtime cost and no new
dependency. Infra's half is about ten files plus one governance sync.

## Validation

1. Scaffold a project in a temp dir: no `.droid/review-context`, no `.droid/traycer-reports`, no AGENTS-compact.md,
   `.windsurfrules`, `opencode.json` or `scripts/kilo_47_agents_final.json` written by the scaffold,
   `docs/reference/kilo/` present, `.droid/.gitignore` written, and the root `.gitignore` carries the reduced block with no
   Kilo/Traycer line.
2. `fabrik fix` on a project with the old tree: the two markers and their empty directories are removed; a non-empty
   `review-context/`, a symlinked marker directory, a marker that is a directory and a dangling-symlink marker are each
   left in place and reported; a refused removal is reported and the run continues; the three synced files are neither
   written nor deleted; a user's own `.droid/` ignore line survives; the dry run reports the same and changes nothing.
3. `--from-preplan`: `docs/preplan.md` written; AGENTS.md and CLAUDE.md unchanged byte-for-byte.
4. After infra's merge, a governance sync on one project: AGENTS-compact.md, opencode.json and `.windsurfrules` gone,
   `check_synced_unmodified.py` green, the project's gate green.

## Decisions taken

- `.droid/` stays for `docs_queue/` and `docs_log/` (live writer); everything else under it is retired.
- `.droid/dev_tracker.db` is retired with its dead script (filed for infra).
- `docs/reference/kilo/` stays (live); its rename is out of scope.
- The pre-plan reaches agents through one generic governance line, not a per-project injection.
- Infra's half merges first (`§ Contract deltas`, merge order).

## Lifecycle

Two merges, infra's first: the manifest/prune/template/gate change, then fleet's scaffold change. Projects converge on
their next governance sync (files removed) and their next `fabrik fix` (markers removed). Nothing touches a VPS.

## Intake Inventory

| I# | Item (anchored) | Disposition | Where |
|---|---|---|---|
| I1 | "scaffold.py:290-291 comments: Traycer Phases replace manual phase tracking" | IN | fleet half step 2 (comments dropped, with `:1333-1334` and `:542-547`) |
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
`docs/CONFIGURATION.md:596`, `docs/reference/fabrik-cli-reference.md:26` and `docs/preplans/README.md:25` (the injection),
`docs/FEATURES.md:427,606` (a governance file, applied by the orchestrator), `CHANGELOG.md`. No file is added or
removed, so `INDEX.md` is untouched. Infra owns `templates/governance/CLAUDE.md`, the manifest docs and
`SCAFFOLD_STRUCTURE.md`'s synced-file rows (infra half step 5).

## Open / blocking unknowns

None blocking. The halves are ordered (`§ Contract deltas`, merge order). Not blocking: whether any live project keeps
its own files under `.droid/review-context/` — the fix keeps and reports them either way.
