# Plan — the scaffold stops emitting the retired Kilo/Traycer/Windsurf surface (mail 01M407YP)

Status: DRAFT
Profile: small
**Owner:** fleet

Spec: `docs/superpowers/specs/2026-10-03-scaffold-retired-agent-surface-design.md` (DRAFT, `Size: small`, `Profile: delta` —
`/fabrik-plan-review` grades its sections together with this plan and flips both). Source: infra's mail 01M407YP (acked;
reply 01M40SBBEGYNQ3R6AW3EAXBWT5 carries infra's half). Rulings: D-514 (development runs on Claude Code), D-364 (Kilo CLI
retired). Estimated diff: ≈140 code lines in 4 code files, tests excluded — `src/fabrik/scaffold.py` ≈125 (mostly
deletions plus the marker-removal helper), `src/fabrik/preplan.py` ≈5, `src/fabrik/cli.py` ≈6, `src/fabrik/portability.py` ≈2.

## What this plan is

The FLEET half of the spec (`spec § Chosen approach`, fleet half steps 1-5), in two inline phases the orchestrator codes
itself in the worktree; no coder is dispatched:

- **A — `create_project` and `fix_project` stop emitting the retired surface**, and `fix_project` removes the two empty
  Traycer markers from existing projects.
- **B — the pre-plan copy stops writing into guardrail files**; docs, Finish.

**Ordering:** independent of infra's half (`spec § Chosen approach`, infra steps 1-5; `spec § Contract deltas`, merge
order). Fleet-first is safe: `fix` stops writing the three synced files but never deletes them, so the sync keeps
delivering them until infra's merge removes them.

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
  `.windsurfrules`, `AGENTS-compact.md`, `opencode.json` or `scripts/kilo_47_agents_final.json` in a project — the
  sync owns the first three; the fourth is left for its owner.
- **`docs/reference/kilo/` stays** — both copies (`scaffold.py:1312-1318`, `:7448-7460`) are untouched
  (`spec § Rejected alternatives` C).
- **`_DROID_GITIGNORE_BLOCK` keeps its name** — eight per-type writers embed it (`:1405`, `:4498`, `:4647`, `:4780`,
  `:5849`, `:6012`, `:6147`, `:6451`); only its content changes.
- **Every `fix_project` live block removed here takes its dry-run twin with it** (the `if not dry_run:` / `else:`
  pairing, `:7406-7553` / `:7554-7621`), and a new step gets a dry-run twin that reports without writing.
- **Merge order is free** (`spec § Contract deltas`, merge order): this plan does not wait for infra's half; it removes
  the scaffold's dependency on the hub copies of `.windsurfrules` and `opencode.json`.
- No new dependency; `pyproject.toml` and `uv.lock` are not touched (`core/10-python.md:30`). No env var is added. No
  logging change (`core/10-python.md:292`: no file sink is introduced).
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
| `.windsurf/rules/core/45-testing-strategy.md` (MATCHED) | one test per behaviour; watched-fail-first; no cosmetic assertions; a guard proven several ways | `45-testing-strategy.md:20-22`, `:199-200` |
| `.windsurf/rules/core/40-documentation.md` (MATCHED) | heading levels and fenced code in the three docs edited | `core/40-documentation.md:241` |
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
| "A GUARD proven only by the ONE spelling of the defect you already fixed" | `.windsurf/rules/core/45-testing-strategy.md:199` | Guard spellings |
| "**No skipped heading levels** — `##` to `###`, never `##` to `####`" | `.windsurf/rules/core/40-documentation.md:241` | Docs |
| "Mandate: config via env vars only (`os.getenv("KEY", "default")`); **ZERO secrets/constants in code**." | `.windsurf/rules/core/35-security-auth.md:267` | Config (not engaged) |

## Phase A — `create_project` and `fix_project` stop emitting the retired surface

Appetite: 60

**Interfaces — Produces** (all in `src/fabrik/scaffold.py`; `spec § Chosen approach`, fleet steps 1-3):
- `_DROID_GITIGNORE_BLOCK` (`:548-557`) — content exactly `.factory/consultations/`, `.droid/docs_queue/`,
  `.droid/docs_log/`, one per line, trailing newline.
- `_DROID_DIR_GITIGNORE` (`:699-708`) — content exactly `"# .droid runtime files (docs_queue/, docs_log/) — do not
  commit\n*\n!.gitignore\n"`. `_TRAYCER_REPORTS_GITIGNORE` (`:711-713`) removed.
- `_remove_retired_droid_markers(project_path: Path, *, dry_run: bool) -> list[str]` — new, beside `_patch_droid_block`
  (`:7266`). For each of `(".droid/review-context", ".gitkeep")` and `(".droid/traycer-reports", ".gitignore")`: when the
  marker file exists, remove it (not under `dry_run`) and report `removed <dir>/<marker>`; then, when the directory
  exists, holds no entry other than the marker, and is not a symlink, remove it (`Path.rmdir`, not under `dry_run`) and
  report `removed <dir>/ (empty)`; when it holds other entries, leave it and report `kept <dir>/ (not empty: <n>
  entries)`. A missing directory reports nothing. Never follows a symlink, never deletes a file other than the named
  marker. Called once in each `fix_project` branch.
- `create_project` / `_scaffold_shared`: no `.droid/review-context`, `.droid/traycer-reports`, `.windsurfrules`,
  `AGENTS-compact.md`, `scripts/kilo_47_agents_final.json` or `opencode.json` written; no `FileNotFoundError` for a
  missing hub `.windsurfrules` (the `.windsurf/rules` and `.windsurf/workflows` guards `:1246-1251` stay).
- `fix_project`: the `.windsurfrules`, `AGENTS-compact.md`, `opencode.json`, `kilo_47_agents_final.json` blocks and
  their dry-run twins removed (`spec § Chosen approach` fleet step 3 lists every range), with the `windsurfrules_target`
  guard `:7402`, `:7408-7409`; the `.droid/.gitignore` and root-`.gitignore` rewrites kept, now writing the reduced
  constants; the marker creation `:7530-7544` / `:7605-7613` replaced by the `_remove_retired_droid_markers` call.

**Consumes:** nothing.

**Mirror (named):** tests asserting the old surface change with it — `tests/test_scaffold.py`
`TestDroidGitignoreBlock` (`:26-51`, the entry list), `TestFixProjectDroidStructure` (`:186-242`, the marker files and
`_TRAYCER_REPORTS_GITIGNORE`), `TestFixProjectRootGitignorePatch` (`:245-308`, `.droid/kilo_usage.jsonl` no longer in
the block), `TestTracerReportsScaffolding` (`:311-349`, removed — replaced by A1), `test_droid_gitignore_block_present`
(`:527-546`, its `traycer-reports` entry); `tests/test_scaffold_fix.py` the `kilo_47` refresh tests (`:262-281`) and the
kilo line of `test_dry_run_previews_reference_doc_refresh` (`:297-298`, its reference-doc asserts `:291-296` stay);
`_source_root` (`:15-19`) removed if nothing else uses it. Fixture hub roots that create `.windsurfrules`,
`AGENTS-compact.md` and `opencode.json` (`tests/test_scaffold_logging.py:79-90`, `tests/test_scaffold_doc_seeding.py:129-136`)
keep working unchanged — the scaffold just stops copying from them.

0. Probe the environment: `cd /opt/fabrik/.claude/worktrees/fleet && PYTHONPATH=$PWD/src .venv/bin/python -c "import
   fabrik.scaffold as s; print(s.__file__)"` prints the worktree path.
1. **Write the failing tests first** (rows A1-A6) in `tests/test_scaffold.py`: A1 and A2 call `create_project` against a
   fake `FABRIK_ROOT` built like `tests/test_scaffold_doc_seeding.py:129-151` (A2 omits `.windsurfrules` and
   `opencode.json` from it); A3-A6 build an old-shaped project tree in `tmp_path` and call `fix_project`. Run them and
   confirm each fails for the right reason (A1: the retired files exist; A2: `FileNotFoundError`; A3-A5: markers still
   present / synced files rewritten; A6: the old block survives).
2. Change the constants, `SHARED_DIRS`, `_scaffold_shared` and `create_project` per the Interfaces; delete the comments
   at `:290-291`.
3. Add `_remove_retired_droid_markers`; rewrite `fix_project`'s blocks per the Interfaces, live and dry run.
4. Update the named mirror tests.
5. Run green: `PYTHONPATH=$PWD/src .venv/bin/python -m pytest tests/test_scaffold.py tests/test_scaffold_fix.py
   tests/test_scaffold_doc_seeding.py tests/test_scaffold_logging.py -q -p no:cacheprovider` → all pass.
6. Prove red on revert in a throwaway worktree (copy each edited file to its exact path, grep a marker to confirm the
   copy landed): let `_remove_retired_droid_markers` remove a non-empty directory with `shutil.rmtree` → A4 fails;
   restore the `opencode.json` copy in `create_project` → A1 fails; restore the `.windsurfrules` guard → A2 fails;
   remove the worktree.
7. `python scripts/enforcement/check_doc_sync.py` → exit 0.
8. **`/fabrik-review-scoped`** on Phase A's surface (`src/fabrik/scaffold.py`, `tests/test_scaffold.py`,
   `tests/test_scaffold_fix.py`), run to its closing pass confirming 0 — BLOCKING before Phase B.
9. Commit Phase A (explicit paths + provenance trailers, `Agent-Phase: A`), push.

### Behavior Contract — Phase A
- **Given** a fake hub root carrying every source file, **When** `create_project` scaffolds a `python-api` project, **Then** the project has no `.droid/review-context`, `.droid/traycer-reports`, `.windsurfrules`, `AGENTS-compact.md`, `opencode.json` or `scripts/kilo_47_agents_final.json`, has `docs/reference/kilo/`, its `.droid/.gitignore` equals `_DROID_DIR_GITIGNORE`, and its root `.gitignore` carries `.droid/docs_queue/` and `.droid/docs_log/` and no line containing `kilo`, `traycer` or `.droid/reviews` (A1; `spec § Validation` 1)
- **Given** a fake hub root with no `.windsurfrules` and no `opencode.json`, **When** `create_project` runs, **Then** it completes without raising (A2; `spec § Contract deltas`, merge order)
- **Given** an old-shaped project with `.droid/review-context/.gitkeep` and `.droid/traycer-reports/.gitignore` only, **When** `fix_project` runs, **Then** both markers and both directories are gone and the report names each removal (A3; `spec § Validation` 2)
- **Given** `.droid/review-context/` holding `.gitkeep` and `notes.md`, a symlinked `.droid/traycer-reports`, and a project with no `.droid/` at all, **When** `fix_project` runs on each, **Then** `notes.md` survives with its directory reported `kept … (not empty: 1 entries)`, the symlink and its target are untouched, and the `.droid`-less project reports no removal and raises nothing (A4; `45-testing-strategy.md:199`)
- **Given** a project holding its own `.windsurfrules`, `AGENTS-compact.md`, `opencode.json` and `scripts/kilo_47_agents_final.json`, and one holding none of them, **When** `fix_project` runs, **Then** the first keeps all four byte-identical, the second gains none, and no report line names them (A5; `spec § Chosen approach`, fleet step 3)
- **Given** an old-shaped project and `dry_run=True`, **When** `fix_project` runs, **Then** the report lists the marker removals and the `.gitignore` rewrites, and every file and directory is unchanged (A6; `spec § Validation` 2)
- **Given** a root `.gitignore` holding the old eight-line `.droid` block among user lines, **When** `fix_project` runs, **Then** the block is replaced by the reduced one, the user lines survive in order, and a second run reports no `.gitignore` change (A7; `scaffold.py:7266`)

## Phase B — The pre-plan copy stops writing into guardrail files; docs; Finish

Appetite: 45

**Interfaces — Produces:**
- `src/fabrik/scaffold.py::_layer_preplan_into_project(project_dir: Path, preplan: object) -> None` (`:6939-7000`) —
  signature unchanged; copies the pre-plan to `docs/preplan.md` as today (`:6968-6972`) and returns; the
  `reference_line`, the guardrail list and the per-file loop (`:6975-7000`) are removed. Its docstring (`:6940-6960`),
  `create_project`'s (`:7104-7117`) and the caller comment (`:7179-7181`) say the pre-plan is copied to
  `docs/preplan.md` and the governance CLAUDE.md points agents at it.
- Docstrings and help, same wording: `src/fabrik/preplan.py:1-8`, `src/fabrik/cli.py:1806-1818` (the `--from-preplan`
  help) and `:2198-2211` (the `preplan` group), `src/fabrik/portability.py:416-417` (the governance list loses
  `.windsurfrules`, `AGENTS-compact.md` and `KILO_CLI_RULES.md`).
- Docs: `docs/QUICKSTART.md:70-77` (the preplan comment and the AGENTS-compact line), `docs/reference/architecture.md:255`
  (the `.droid/review-context/` row → the `.droid/` row naming `docs_queue/` and `docs_log/`),
  `docs/workflows/SCAFFOLD_STRUCTURE.md:27,70,147` (the scaffold-emitted rows); `CHANGELOG.md` (orchestrator-applied,
  outside File Scope by the plan grammar).

**Consumes:** Phase A (the `.droid/` shape the docs describe).

**Mirror (named):** `tests/test_preplan.py` `test_injects_reference_into_all_4_guardrails` (`:175-195`),
`test_skips_missing_guardrail_files_silently` (`:197-214`) and `test_idempotent_does_not_duplicate_reference`
(`:216-237`) are replaced by B1; `test_copies_preplan_to_project_docs` (`:160-173`) and `test_none_preplan_is_no_op`
(`:239`) stay.

1. **Write the failing test first** (B1) in `tests/test_preplan.py`, replacing the three injection tests; confirm it fails
   against today's code (the guardrail files gain the line).
2. Rewrite `_layer_preplan_into_project` and the docstrings/help per the Interfaces.
3. Run green: `PYTHONPATH=$PWD/src .venv/bin/python -m pytest tests/test_preplan.py tests/test_scaffold.py -q -p
   no:cacheprovider`; and `command grep -rn "4 AI guardrail\|all 4 AI\|four AI guardrail" src/fabrik` → no output.
4. Prove red on revert in a throwaway worktree: restore the injection loop for `CLAUDE.md` only → B1 fails; remove it.
5. The doc edits per the Interfaces; `CHANGELOG.md` through the shared-append private-index recipe (`CLAUDE.md`
   § Behavior, the shared-repo bullet). Then `python scripts/enforcement/check_doc_sync.py` and
   `python scripts/render_doc_script_links.py --check` → both exit 0.
6. **`/fabrik-review-scoped`** on Phase B's surface (the four source files, `tests/test_preplan.py`, the three docs), run to
   its closing pass confirming 0.
7. **Finish — the heavy `/fabrik-review`** over the whole-plan diff (`git diff <phase-A base>..HEAD`): the D7 floor — at
   least one Opus authoritative seat plus one Sonnet and one Haiku seat per independent failure-class group, sized by
   `python3 /opt/fabrik/scripts/sysadmin/dispatch_headroom.py --units <groups>` and stamped with
   `python3 scripts/command_run.py dispatch --seats <n>` before they go out; the receipt at
   `docs/development/reviews/2026-10-03-plan-1-scaffold-retired-agent-surface-review.md` embedding the verbatim
   `final_gate.py --json` success. Then `/fabrik-docs-review` over the three docs.
8. The full gate: `python scripts/final_gate.py --check --json` → `"status": "success"` (necessary, not sufficient — the
   Evidence below is the design proof), and `python scripts/enforcement/check_convergence.py` → exit 0.
9. Commit Phase B (`Agent-Phase: B`), push, then `python3 scripts/merge_request.py request --review <the receipt>` and send
   the printed `SendMessage` line.

### Behavior Contract — Phase B
- **Given** a parsed pre-plan and a project holding `AGENTS.md`, `CLAUDE.md`, `AGENTS-compact.md` and `.windsurfrules`, **When** `_layer_preplan_into_project` runs, **Then** `docs/preplan.md` equals the source pre-plan and all four files are byte-identical to before (B1; `spec § Validation` 3)
- **Given** the merged change, **When** `check_doc_sync.py` and `render_doc_script_links.py --check` run, **Then** both pass and no file under `src/fabrik/` says "4 AI guardrail" (B2; `spec § Documentation landing sites`)

## File Scope (owned paths)

- src/fabrik/scaffold.py
- src/fabrik/preplan.py
- src/fabrik/cli.py
- src/fabrik/portability.py
- tests/test_scaffold.py
- tests/test_scaffold_fix.py
- tests/test_preplan.py
- docs/QUICKSTART.md
- docs/reference/architecture.md
- docs/workflows/SCAFFOLD_STRUCTURE.md
- docs/superpowers/specs/2026-10-03-scaffold-retired-agent-surface-design.md
- docs/development/reviews/2026-10-03-plan-1-scaffold-retired-agent-surface-review.md

## Evidence

**Phase A.** The create-time copies and the guard (read this run):
```text
src/fabrik/scaffold.py:1244:     if not fabrik_windsurfrules.exists():
src/fabrik/scaffold.py:1254:     shutil.copy(fabrik_windsurfrules, project_dir / ".windsurfrules")
src/fabrik/scaffold.py:1384:         shutil.copy(fabrik_kilo_config, scripts_target_dir / "kilo_47_agents_final.json")
src/fabrik/scaffold.py:1401:     shutil.copy(FABRIK_ROOT / "opencode.json", project_dir / "opencode.json")
```
The fix path's live/dry-run pairing and its markers: `src/fabrik/scaffold.py:7406-7553` / `:7554-7621`;
`_patch_droid_block` replaces every `.droid/`/`.factory/` line (`:7266-7302`):
```text
src/fabrik/scaffold.py:7536:             added.append(".droid/review-context/.gitkeep")
src/fabrik/scaffold.py:7544:             added.append(".droid/traycer-reports/.gitignore (created/updated)")
src/fabrik/scaffold.py:7557:         added.append(".windsurfrules (copied)")
src/fabrik/scaffold.py:7585:             added.append("opencode.json (refresh from master)")
```
No existing `fix_project` step deletes a regular file or an empty directory (a full read of `:7323-7643` by the grounding
seat; every deletion there is a replace-before-copy at `:7420`, `:7429`, `:7453-7455`), so `_remove_retired_droid_markers`
is new code with its own guards. The live readers of what stays: `scripts/docs_updater.py:107-108` creates
`.droid/docs_queue` and `.droid/docs_log` at import.

**Phase B.** The injection and its consumers:
```text
src/fabrik/scaffold.py:6981:     guardrail_files = [
src/fabrik/cli.py:1814:         "'Preplan:' reference to all 4 AI guardrail files (AGENTS.md, CLAUDE.md, "
src/fabrik/preplan.py:6: the four AI guardrail files (CLAUDE.md, AGENTS.md, AGENTS-compact.md,
tests/test_preplan.py:175:     def test_injects_reference_into_all_4_guardrails(self, fake_root, tmp_path):
```
The docs: `docs/QUICKSTART.md:70-77`, `docs/reference/architecture.md:255`, `docs/workflows/SCAFFOLD_STRUCTURE.md:27`,
`:70`, `:147`.

## Self-audit

- Grounding: three native seats (Opus on `fix_project`, Sonnet on the create path, Sonnet on the pre-plan path and every
  consumer), all returning `path:line`; the orchestrator re-read every anchor this plan and the spec cite
  (`anchors2.py`, 70 lines printed) and re-ran the spec's path check (32 paths, 2 expected misses: a gitignored hub
  artifact and a project-side path).
- The seats changed the design: `opencode.json` and `kilo_47_agents_final.json` are also copied at create time; both
  `.windsurfrules` copies sit behind a fail-fast guard; every fix block has a dry-run twin; the constant feeds eight
  writers; a fleet-first merge is safe, so the ordering gate was dropped. The spec was amended for each.
- Five more hub consumers of the three synced files belong to infra (`spec § Chosen approach`, infra step 5) — mailed
  as an addendum to 01M40SBB.
- (a) Coverage: I1-I3, I6 → Phase A; I4 → Phase A (scaffold side), infra (manifest); I5 → Phase B, infra (governance
  line); I7 → decided, no scaffold code; I9 → kept (Global Constraints); I8 → W-477e37cd.
- (b) Signatures: `_remove_retired_droid_markers` (A) is called from both `fix_project` branches (A); B consumes no A
  function, only the `.droid/` shape its docs describe; `_layer_preplan_into_project`'s signature is unchanged for its
  one caller (`:7182-7183`).
- Fixed point: not yet — `/fabrik-plan-review` runs next.

## Residual unknowns

- **Open — whether any live project keeps real files under `.droid/review-context/`.** A4 covers it (kept and reported);
  the operator sees the `kept` lines on the next `fabrik fix`. No step depends on the answer.
- **Resolved:** who reads each retired artifact (`spec § What exists today`); whether `_patch_droid_block` drops the old
  lines (it replaces every managed line, `:7266-7302`); whether the merge order matters (`spec § Contract deltas`).

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
| fail-open vs fail-closed (a missing hub file, a missing `.droid/`) | UNCHECKED |
| cost/quota accounting — not engaged (no metered call) | UNCHECKED |
| boundary/sentinel (empty vs one-entry directory, marker vs user file, symlink) | UNCHECKED |
| behavior-without-a-test | UNCHECKED |

The rubric this plan's reviews inject into every seat brief, run on the plan's code surface:

```bash
python3 scripts/review_rubric.py --changed src/fabrik/scaffold.py src/fabrik/preplan.py src/fabrik/cli.py src/fabrik/portability.py tests/test_scaffold.py tests/test_scaffold_fix.py tests/test_preplan.py docs/QUICKSTART.md docs/reference/architecture.md docs/workflows/SCAFFOLD_STRUCTURE.md
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

### core/40-documentation.md  (hit: docs/QUICKSTART.md, docs/reference/architecture.md, docs/workflows/SCAFFOLD_STRUCTURE.md)
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
