# Scaffold: stop emitting the retired Kilo/Traycer/Windsurf agent surface

Status: DRAFT
Size: small (≈120 lines, 3 files)
Profile: delta — every intake item maps to code that exists today: `src/fabrik/scaffold.py` (`create_project`,
`fix_project`, `_layer_preplan_into_project`, `_DROID_GITIGNORE_BLOCK`), `src/fabrik/preplan.py`, `src/fabrik/cli.py`
(`--from-preplan`) and the sync manifest `scripts/fabrik_synced_manifest.py`. No new persona, consumer or service.

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
| `opencode.json` | synced (`:103`); fix `:7496-7500` | Kilo/opencode only | dead tool, live gate |
| `.windsurfrules` | synced (`:104`); scaffold `:1253-1254`; fix `:7417-7422` | no agent; presence checks only in `sync_projects.py:368`, `health_summary.py:43` | dead, reporting-only checks |
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

## Chosen approach — A, retire by owner, in two ordered merges

**Infra half (first merge; governance-sync path, full `/fabrik-review`):**
1. Drop `AGENTS-compact.md`, `opencode.json` and `.windsurfrules` from `GOVERNANCE_FILES`
   (`fabrik_synced_manifest.py:102-104`); the sync removes them and rewrites `.fabrik/synced.lock`.
2. Retire `scripts/enforcement/check_opencode_json.py` and its `final_gate.py:2082` row.
3. Add one generic line to `templates/governance/CLAUDE.md`: "If `docs/preplan.md` exists, read it before planning —
   it holds the project's pre-plan: problem, approach, constraints." This replaces the per-project injection and
   survives every sync.
4. Drop `.windsurfrules` from the presence lists in `sync_projects.py:368` and `health_summary.py:43`.

**Fleet half (second merge, after infra lands; this spec's code):**
1. `_DROID_GITIGNORE_BLOCK` keeps `.factory/consultations/`, `.droid/docs_queue/`, `.droid/docs_log/`; the Kilo
   and Traycer lines go. `_DROID_DIR_GITIGNORE` (`scaffold.py:699-708`) shrinks to `*` + `!.gitignore` (the
   directory stays ignored for `docs_queue/`/`docs_log/`); `_TRAYCER_REPORTS_GITIGNORE` (`:711`) is deleted.
2. `create_project` stops creating `.droid/review-context/` and `.droid/traycer-reports/` (`SHARED_DIRS :495-496`,
   `:1134-1142`) and stops copying AGENTS-compact.md and `.windsurfrules` (`:1253-1254`, `:1324-1327`).
   `docs/reference/kilo/` stays.
3. `fix_project` stops (re)creating the same items (`:7417-7422`, `:7470-7477`, `:7496-7500`, `:7512-7518`,
   `:7531-7544`). In an existing project it removes the two scaffold-owned markers
   (`.droid/review-context/.gitkeep`, `.droid/traycer-reports/.gitignore`) and their directories only when nothing else
   is inside, and reports what it removed or left. The root `.gitignore` patch writes the reduced block.
4. `_layer_preplan_into_project` keeps copying the pre-plan to `docs/preplan.md` and stops writing into guardrail
   files; `preplan.py`'s docstring and `cli.py`'s `--from-preplan` help say where the pre-plan lands and that the
   governance CLAUDE.md points agents at it.
5. `.droid/dev_tracker.db`: not created, not ignored, no change needed. Retiring `dev_tracker.py` and
   `kilo_terminal_runner.py` (hub scripts, infra) is filed separately.

## The delta

| File | Change |
|---|---|
| `src/fabrik/scaffold.py` | the five steps of the fleet half |
| `src/fabrik/preplan.py` | docstring: no "4 guardrail files" |
| `src/fabrik/cli.py` | `--from-preplan` help and the `preplan` group docstring |
| `tests/test_scaffold.py` | the `.droid` block, fix-structure and traycer tests rewritten to the reduced surface; a fix test that removes the empty markers and keeps a non-empty directory |
| `tests/test_preplan.py` | the 4-guardrail injection tests become "copied to `docs/preplan.md`, no guardrail file touched" |

## Contract deltas

- `fabrik scaffold` output: the five artifacts in the table above are no longer emitted. Mirror: a tool that expects
  `.droid/review-context/` to exist breaks. Measured: the only reader is `check_doc_sprawl.py:289`, which tests a path
  prefix and does not require the directory.
- `fabrik fix`: removes two marker files and their empty directories. Mirror: a project that keeps hand-written notes
  in `review-context/` keeps them; fix never removes a non-empty directory.
- `--from-preplan`: guardrail files are no longer edited. Mirror: an agent that read the injected line now relies on
  the governance line, which lands with infra's half. Fleet's half lands second for that reason.

## Cost

About 150 lines changed in five fleet files, mostly deletions and test rewrites. No runtime cost and no new
dependency. Infra's half is about 4 files plus one governance sync.

## Validation

1. Scaffold a project of each type in a temp dir: no `.droid/review-context`, no `.droid/traycer-reports`, no
   AGENTS-compact.md or `.windsurfrules` written by the scaffold, `docs/reference/kilo/` present, the `.gitignore`
   carries exactly the reduced block.
2. `fabrik fix` on a copy of an existing project with the old tree: the two markers and their empty directories are
   removed, a non-empty `review-context/` is kept and reported, nothing else is deleted.
3. `--from-preplan`: `docs/preplan.md` written; AGENTS.md and CLAUDE.md unchanged byte-for-byte.
4. After infra's merge, a governance sync on one project: AGENTS-compact.md, opencode.json and `.windsurfrules` gone,
   `check_synced_unmodified.py` green, the project's gate green.

## Decisions taken

- `.droid/` stays for `docs_queue/` and `docs_log/` (live writer); everything else under it is retired.
- `.droid/dev_tracker.db` is retired with its dead script (filed for infra).
- `docs/reference/kilo/` stays (live); its rename is out of scope.
- The pre-plan reaches agents through one generic governance line, not a per-project injection.

## Lifecycle

Two merges: infra's manifest/template/gate change, then fleet's scaffold change. Projects converge on their next
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

`docs/QUICKSTART.md` (if it names `--from-preplan`'s 4 files), `docs/reference/architecture.md` (the `.droid` and
AGENTS-compact rows), `INDEX.md` for removed files, `CHANGELOG.md`. Infra owns `templates/governance/CLAUDE.md` and
the manifest docs.

## Open / blocking unknowns

None. The ordering (infra first) is the only coupling; a fleet merge landing first is harmless (the sync still delivers
the files) but leaves `fabrik fix` and the sync disagreeing until infra lands.
