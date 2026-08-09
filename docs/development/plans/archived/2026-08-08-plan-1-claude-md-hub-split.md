# Plan 1 — CLAUDE.md hub/project split (2026-08-08)

Status: EXECUTED 2026-08-08 (bee1eb31 → 29176126 → e46bd7c5 → 3427b25f)
Whole-plan review: docs/development/reviews/2026-08-08-plan-1-claude-md-hub-split-review.md

## Goal

`/opt/fabrik/CLAUDE.md` currently serves two masters: it is the HUB agents' always-on contract AND the
file distributed verbatim to every `/opt` project. Split them: the hub gets a platform-repo contract
(authoring synced surfaces, fleet blast radius, merge-time-render), projects keep receiving the current
project-oriented content from a template path — **byte-identical at cutover, zero fleet behavior change**.
`fabrik-lib` keeps its own `CLAUDE.md` (already sync-excluded).

## Context Ledger

- **ACTIVE packs consulted:** `core/10-python.md` (script edits), `core/40-documentation.md` (doc rules,
  Sync Matrix), `core/45-testing-strategy.md` (red-first, behavior-contract tests). The other ACTIVE
  packs (ai/*, chrome-ext/*, gpu, workers, bootstrap) touch no surface of this plan — no AI calls, no
  UI, no workers here.
- **agents-fabrik.md:** § Platform at a Glance row 9 (Sync — centrally managed list =
  `fabrik_synced_manifest.py`), § Planning Constraints #11 (scaffold immutability — `templates/governance/`
  is a new subdir of the existing `templates/`, not a project-tree change), § Scaffold Types (scaffold is
  the other distribution door).
- **Machinery (all verified this session; re-opened in plan-review pass 1):**
  - `"CLAUDE.md"` in `GOVERNANCE_FILES`: `scripts/fabrik_synced_manifest.py:64`
  - Governance copy loop `source = FABRIK_ROOT / gov_file`: `scripts/sync_enforcement_to_projects.py:500-507`
  - `iter_synced_pairs` GOVERNANCE_FILES leg (src rel == dest rel): `scripts/fabrik_synced_manifest.py:211-213`
  - **(src_rel, dest_rel) tuple precedent** — `REFERENCE_DOCS` leg: `fabrik_synced_manifest.py:216-217`;
    template-dir precedent `RUN_SCRIPTS_SRC_DIR = "templates/scaffold/scripts"`: `:209` — the pattern to reuse.
  - Lock writer keys by DEST rel (`dest.relative_to(project_dir)`): `sync_enforcement_to_projects.py:663-667`;
    `check_synced_unmodified.py` compares ONLY the per-project `.fabrik/synced.lock` (docstring + `:70`) —
    **no repoint needed there**; the lock follows whatever the sync distributes.
  - Scaffold seeds new projects by DIRECT copy `FABRIK_ROOT / "CLAUDE.md"`: `src/fabrik/scaffold.py:1141-1143`
    (G-B5) — **must repoint to the template** or new projects get the hub contract. The
    `guardrail_files` list at `scaffold.py:5695-5700` is a DEST-name list (no source path) —
    adjudicated in review pass 1: **no change needed there**.
  - `templates/**/*.md` is an established md-as-template class (`AFCL_TEMPLATE.md`,
    `scaffold/docs/*_TEMPLATE.md`, `docusaurus/README.md`) and `templates` is not in
    `check_structure.NO_MD_DIRS` — the new template file's placement is gate-clean by precedent.
  - Pre-commit `governance-sync` files-filter carries `^CLAUDE\.md$`: `.pre-commit-config.yaml:57`.
  - `fabrik-lib` excluded from sync targets: `sync_enforcement_to_projects.py:759`.
  - Doc table row: `docs/workflows/SYNC_ENFORCEMENT_WORKFLOW.md:42`.
  - Only ONE code reference to the hub path as template source (`grep -rn 'FABRIK_ROOT / "CLAUDE'` over
    `src/ scripts/ commands/_sources/ .claude/hooks/`): `scaffold.py:1141`.
- **shape.\* / spec:** n/a — hub repo, no `project.yaml`, no service spec changes.
- **fabrik-lib:** nothing vendored or changed.

## File Scope (owned paths)

- `scripts/fabrik_synced_manifest.py`
- `scripts/sync_enforcement_to_projects.py`
- `src/fabrik/scaffold.py`
- `.pre-commit-config.yaml`
- `templates/governance/CLAUDE.md` (new)
- `CLAUDE.md`
- `docs/workflows/SYNC_ENFORCEMENT_WORKFLOW.md`
- `tests/test_governance_template_split.py` (new)

Disjoint from every active plan (none running). CHANGELOG/INDEX/docs-README/LESSONS stay out per grammar.

## Phase A — Machinery cutover: CLAUDE.md becomes template-sourced (tests red-first)

1. **Red-first tests** (`tests/test_governance_template_split.py`, run BEFORE the code change, watch fail).
   Fixture note: `iter_synced_pairs(project_root, fabrik_root=…)` takes the fabrik root as a parameter —
   tests pass a tmp fabrik root containing a fixture template file, so Phase A never depends on the real
   `templates/governance/CLAUDE.md` existing (that file lands in Phase B):
   - `iter_synced_pairs` yields `(<fabrik_root>/"templates/governance/CLAUDE.md", <proj>/"CLAUDE.md")` and
     does NOT yield `(<fabrik_root>/"CLAUDE.md", …)` for any dest.
   - `"CLAUDE.md" not in GOVERNANCE_FILES` and the new `GOVERNANCE_TEMPLATES` list equals
     `[("templates/governance/CLAUDE.md", "CLAUDE.md")]`.
   - Sync dry-run over a tmp project reports CLAUDE.md sourced from `templates/governance/` (assert on the
     `SyncResult` source path).
   - Scaffold seed source: assert the G-B5 copy reads the template path (unit-level: monkeypatch/inspect,
     not a full scaffold run).
2. Manifest: add `GOVERNANCE_TEMPLATES = [("templates/governance/CLAUDE.md", "CLAUDE.md")]`
   (REFERENCE_DOCS-style pairs); remove `"CLAUDE.md"` from `GOVERNANCE_FILES`; extend `iter_synced_pairs`
   with the new leg (**unconditional yield, like the GOVERNANCE_FILES leg** — the lock comprehension
   filters on `dest.exists()`, so a project's CLAUDE.md stays lock-protected even if the template is
   momentarily absent); update the module docstring's consumer notes.
   **A→B gap safety (proven in review pass 1):** if a sibling commit fires governance-sync between
   Phase A's commit and Phase B's, the copy loop skips the missing template source (no overwrite, projects
   keep current CLAUDE.md) and the lock keeps its CLAUDE.md entry (keyed on dest existence) — the gap is
   fail-safe and self-heals at Phase B's sync.
3. Sync script: new loop over `GOVERNANCE_TEMPLATES` mirroring the governance loop
   (`sync_enforcement_to_projects.py:500-507`), `source = FABRIK_ROOT / src_rel`, dest `project_dir / dest_rel`.
4. Scaffold: repoint `scaffold.py:1141` to `FABRIK_ROOT / "templates/governance/CLAUDE.md"` (the
   `guardrail_files` dest-name list at `:5695-5700` needs no change — adjudicated; the `.gitignore`
   Fabrik-synced block derives from DEST rels, which don't change).
5. Pre-commit: in the `governance-sync` files-filter (`.pre-commit-config.yaml:57`) replace
   `^CLAUDE\.md$` with `^templates/governance/` (hub-file edits must NOT trigger a fleet sync; template
   edits MUST). **Commit-sequencing (verified):** pre-commit reads the working-tree config, so Phase A's
   own commit already runs with the NEW filter — no template staged → no sync fired at A; Phase B's commit
   stages the template → sync fires exactly once, with machinery and content both in place.
6. **Gate:** `python -m pytest tests/test_governance_template_split.py tests/test_scaffold_doc_seeding.py -q`
   green (pass-2 verified: no existing test covers `iter_synced_pairs` or the G-B5 copy — the new test
   file IS the coverage; `test_scaffold_doc_seeding.py` rides along as the nearest-neighbor regression
   canary); `ruff` clean on touched files.
   Behavior rows: Phase-A rows 1–4 of `## Behavior Contract` below — watched-fail-first binds all four.

## Phase B — Content split: byte-preserving template, hub rewrite

1. `mkdir -p templates/governance && cp CLAUDE.md templates/governance/CLAUDE.md` — then
   `md5sum CLAUDE.md templates/governance/CLAUDE.md` must MATCH (the cutover-safety invariant: what
   projects receive next sync is byte-identical to what they received last sync). Record both hashes in
   `## Evidence`.
2. Rewrite `/opt/fabrik/CLAUDE.md` as the HUB contract. Section-by-section delta from the template:
   - **Contract header + Orient step 1** → hub identity: this repo IS the platform (CLI, `scaffold.py`,
     enforcement, `commands/_sources`, `.windsurf/rules` authoring, `specs/services/*.yaml` = OTHER
     projects' deploy specs). No `project.yaml`; SCAFFOLD_TYPES are what we EMIT, not what we are.
   - **Behavior** → keep all shared rows; ADD: merge-time-render (never bare-render `assemble_commands.py`
     from a worktree — renders only from merged master; `--check` is always safe), and sync-consciousness
     (a commit touching synced surfaces distributes fleet-wide via the pre-commit hook — know the blast
     radius before staging).
   - **HARD STOPS** → keep every shared row (deploys, compose memory limits, localhost bans, Authelia,
     Gatus, health-bypass, md-allowlist, destructive-dry-run, credentials, convergence-proof); REPLACE the
     "edit a Fabrik-synced file" row with its hub INVERSE: *editing a synced source here IS the canonical
     change — make it only if correct for ALL projects, ground enumerations from the live registry, verify
     a flag's effect by reading the fn, and let the pre-commit sync distribute it; never hand-edit a
     project's copy to "hotfix" one repo.*
   - **Keep verbatim:** Completion Contract, External Knowledge, Doc Sync Matrix, Agent Provenance
     Trailers, session-recall, Pointers, § Pipeline, FINAL OUTPUT (6-line), Spec contract awareness
     (already hub-worded: `fabrik plan` runs here), `@agents-fabrik-core.md` import.
3. **Gate:** `grep -c "@agents-fabrik-core.md" CLAUDE.md` = 1; FINAL OUTPUT block present in both files;
   `md5sum` match from step 1 unchanged (the template was not touched by the rewrite).
   Behavior rows: Phase-B rows 5–6 of `## Behavior Contract` below (hash + grep invariants; prose content, no unit tests).

## Phase C — Distribution, docs, verification

1. `docs/workflows/SYNC_ENFORCEMENT_WORKFLOW.md`: update the What-Gets-Synced row for CLAUDE.md (source =
   `templates/governance/CLAUDE.md`); add one line on the hub/template split.
2. Stale-reference sweep (pass-2 pre-run — hits enumerated): the ONLY live hit is
   `docs/FEATURES.md:302` ("file copy of `/opt/fabrik/CLAUDE.md`") — update it to the template path
   (FEATURES is in the grammar's out-of-scope governance set; edited as a Doc Sync Matrix obligation).
   All other hits are `docs/development/plans/archived/**` + `docs/archive/**` — frozen history, never
   edited. Re-run the grep at execution to confirm no new references appeared.
3. Run `python scripts/sync_enforcement_to_projects.py --force` (real run). Verify on TWO sample projects
   (one active e.g. `/opt/seo`, one recently-synced): `md5sum <proj>/CLAUDE.md` == template hash from
   Phase B; `.fabrik/synced.lock` entry for `CLAUDE.md` == that hash. Verify `/opt/fabrik-lib/CLAUDE.md`
   untouched (mtime + hash unchanged).
4. `/fabrik-review` over the whole diff (monolith phase-boundary review; enforcement + governance are
   NO-POOL surfaces per § Subagent fan-out — native finders + Opus floor, no pool dispatch, which is the
   sanctioned exception to the pool-default).
5. **Gate:** `python scripts/final_gate.py --json` → the standing 43/1 (sole failure = operator-owned seo
   DB-name drift, disclosed) with NO new failures; corpus `--check` untouched (no command-source edits).

## Behavior Contract

- **Given** the split manifest, **When** `iter_synced_pairs(tmp_proj, fabrik_root=tmp_fabrik)` runs, **Then** it yields `(templates/governance/CLAUDE.md → CLAUDE.md)` and never a `<fabrik_root>/CLAUDE.md` source (`tests/test_governance_template_split.py`). [Phase A]
- **Given** the manifest module, **When** imported, **Then** `"CLAUDE.md" not in GOVERNANCE_FILES` and `GOVERNANCE_TEMPLATES == [("templates/governance/CLAUDE.md", "CLAUDE.md")]`. [Phase A]
- **Given** a tmp project and a tmp fabrik root carrying a fixture template, **When** the sync runs `--dry-run`, **Then** the CLAUDE.md `SyncResult` source path is under `templates/governance/`. [Phase A]
- **Given** the scaffolder, **When** G-B5 seeds CLAUDE.md, **Then** the copy source is the template path (unit-level assert, no full scaffold run). [Phase A]
- **Given** the pre-split CLAUDE.md at HEAD, **When** the template is created and the hub file rewritten, **Then** `md5sum templates/governance/CLAUDE.md` equals the pre-split hash and stays unchanged through the rewrite. [Phase B]
- **Given** the hub rewrite, **When** grepped, **Then** exactly one `@agents-fabrik-core.md` import and a FINAL OUTPUT block exist in BOTH files, and the six named hub deltas are present (grep proofs in Evidence). [Phase B]
- **Mocked:** tmp fabrik-root + tmp project dirs only (Phase A); nothing in Phase B — hash and grep run on the real files. The manifest, sync, and scaffold functions always run real.

## Subagents & parallelism

Phases are strictly sequential (A's machinery must land before C's real sync; A is self-contained
against tmp fixture roots per its step-1 fixture note, so it never depends on B's real template file).
Reviews: native-only (NO-POOL surfaces: enforcement,
scaffold, CLAUDE.md, pre-commit config) — the `check_subagent_flywheel` zero-pool-rows WARN is the
documented, sanctioned outcome for this surface class. Phase-boundary `/fabrik-review` after A+B together
(one diff), and after C.

## Evidence

**Planning-time grounding (review passes 1–2; execution appends per-phase proof below):**
every machinery citation was re-opened this session. The load-bearing ones, with the verifying output:
`scripts/fabrik_synced_manifest.py:64` (CLAUDE.md in GOVERNANCE_FILES), `sync_enforcement_to_projects.py:500-507`
(copy loop), `:663-667` (lock keyed by dest rel), `src/fabrik/scaffold.py:1141-1143` (G-B5 direct copy),
`.pre-commit-config.yaml:57` (filter), `docs/FEATURES.md:302` (sole live doc reference).

```
$ sed -n '58,68p' scripts/fabrik_synced_manifest.py        # CLAUDE.md at :64 in GOVERNANCE_FILES
GOVERNANCE_FILES = [
    "AGENTS.md", "agents-fabrik.md", "agents-fabrik-core.md",
    "AGENTS-compact.md", "CLAUDE.md", "opencode.json", ".windsurfrules",
]
$ grep -rln "opt/fabrik/CLAUDE\.md" docs/ commands/_sources/ .windsurf/rules/ | grep -v archived | grep -v archive/
docs/FEATURES.md
docs/development/plans/2026-08-08-plan-1-claude-md-hub-split.md   # this plan
$ grep -n "CLAUDE" tests/test_scaffold_doc_seeding.py             # (no output — G-B5 has no test today)
```

**Execution evidence (appended at §Finish):**

- Phase A: 4 tests seen RED (`4 failed in 0.19s`) → machinery landed → green; commit `bee1eb31`.
- Phase B (`templates/governance/CLAUDE.md` byte-identity + hub divergence; commit `29176126`):

```
$ md5sum CLAUDE.md templates/governance/CLAUDE.md   # after cp, before rewrite
20f25d8e7ee5d6cfda0cd025fd9ae919  CLAUDE.md
20f25d8e7ee5d6cfda0cd025fd9ae919  templates/governance/CLAUDE.md
$ md5sum CLAUDE.md templates/governance/CLAUDE.md   # after hub rewrite
42a4aac977bd593be94e8654b777bc1c  CLAUDE.md
20f25d8e7ee5d6cfda0cd025fd9ae919  templates/governance/CLAUDE.md
```

- Phase C (fleet sync + verification; commit `e46bd7c5`):

```
Results: 46 projects synced, 2 failed  # Traycer/microsoft: root-owned non-fabrik dirs
/opt/seo: file=20f25d8e… lock=20f25d8e… match_tpl=YES
/opt/trade-intelligence: file=20f25d8e… lock=20f25d8e… match_tpl=YES
6ab88afc89abb4a3b2ee6ac14acc46c7  /opt/fabrik-lib/CLAUDE.md   (mtime 2026-07-23 — untouched)
```

- Adjudication fixes (commit `3427b25f`): gitignore canary RED → fix → fleet re-sync → IGNORED verified
  on 5 projects; filter guard proven red-on-revert; suites 37 green. Full detail: the cited whole-plan
  validation doc.

## Pass Ledger (plan-review convergence)

| Pass | axes re-grounded | edits | plan md5 (start → end) |
|-----:|---|---:|---|
| 1 | citations (all re-opened) · pillars · A→B gap · commit sequencing · scaffold:5697 adjudication | 8 | 3c432030… → (superseded) |
| 2 | executability (gate `-k` selector vs real test names) · sweep-hit enumeration · File Scope | 2 | (superseded) |
| 3 | full re-read · internal consistency (Subagents stale phrasing) · Evidence/ledger fill · gate-demanded G/W/T grammar (indented pseudo-heading → real `## Behavior Contract` section, `check_test_proposal._section` is line-anchored) · Status flip | 9 | → 0cd00cd6… |
| 4 | all axes, fresh re-read — **0 content edits**; gate 43/1 (sole failure operator-owned seo, disclosed); this ledger row-write is the only change after verification | 0 | 0cd00cd6… → (this write) |

## Self-audit

- (a) Every conversation agreement maps: hub-specific file → Phase B; byte-identical template → Phase B
  step 1 + Phase C step 3; fabrik-lib untouched → Phase C step 3; "properly" = machinery + tests +
  docs + fleet verification → Phases A/C.
- (b) Cross-phase interfaces: A's `GOVERNANCE_TEMPLATES` shape ↔ B's file location ↔ C's sync
  verification all name the same path `templates/governance/CLAUDE.md`.

## Residual unknowns

- **AGENTS-compact.md / AGENTS.md / opencode.json stay single-file** (hub copy == project copy) — OUT OF
  SCOPE v1. Named consequence while it stands: hub-side Kilo/opencode agents read the PROJECT-worded
  AGENTS-compact.md (e.g. its "never edit synced files" row) alongside the new hub CLAUDE.md's inverse —
  a known, disclosed contradiction on the hub only, for non-Claude agents only; the follow-up split
  resolves it if it bites.
- Projects' `.gitignore` "Fabrik-synced" block: derives from DEST rels (unchanged) — no regeneration
  needed; verified implicitly by Phase C's lock check.
