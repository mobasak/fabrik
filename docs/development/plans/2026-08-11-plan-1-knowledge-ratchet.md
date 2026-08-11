# Plan — Knowledge-surface ratchet: LESSONS graduation status + AFCL stub retirement

Status: CONVERGED
Owner: hub (governance + scaffolder + fleet audit)
Operator directive (verbatim, 2026-08-11): "adopt the graduation-status convention and/or the AFCL
stub cleanup as a small follow-up plan, afterwards /fabrik-plan-review"

## What we already agreed

- **The measured problem (2026-08-11, this session):** LESSONS_LEARNT is write-enforced but
  read-never — zero read-mandates in the whole command corpus (grep evidence below); its real value
  path is graduation into gates/rules (hub Lessons 100–109 nearly all became enforcement checks or
  pack rules). AFCL is the inverse: read-mandated in six governance places but **31 of 38 non-hub
  copies are byte-identical untouched templates, in TWO generations** — 19 at the pre-2026-05-16
  generation (md5 `7521beff…`, 1,045B) and 12 at the current generation (md5 `bbce548e…`, 2,090B,
  byte-equal to the live `templates/scaffold/AFCL_TEMPLATE.md`; the template grew at commit
  `ec17faa1`, 2026-05-16). The scaffolder copies the template verbatim (`shutil.copy`,
  `scaffold.py:1167` — no rendering), so generation hashes are stable fleet-wide. The first census
  (19) was size-filtered and wrong — the pass-1 native grounder ran it unfiltered. Every task pays
  a mandated read that returns an empty template.
- **Adopted fix 1 — graduation-status convention:** every fleet-applicable `docs/LESSONS_LEARNT.md`
  entry dated on/after 2026-08-11 carries a one-line `Ratchet:` status naming where it graduated
  (enforcement check · rule-pack section · `term-coverage` standing recurrence class) or `local-only`
  / `pending — <named next step>`. A weekly WARN-tier sweep flags post-adoption entries missing the
  line. Pre-adoption entries are exempt by date — no retro-fill obligation (LESSONS_LEARNT is a
  shared-append surface outside any plan lock; retro-fill is an optional operator follow-up).
- **Adopted fix 2 — AFCL stub retirement:** delete the never-appended stubs across the fleet
  (dry-run first, exact-match only), retire all THREE scaffolder emission blocks and the template, and
  retire the doc-registry row as SSOT hygiene (verified this round: the row has NO live mechanical
  consumer — see Phase B step 4). The 8 non-stub AFCLs — hub (6.4KB, real project-local findings,
  outside the census by construction) plus the 7 diverged non-hub singletons (brand-identiy-creator
  3.5KB, seo, tojlo-mail, trade-intelligence, tryton-crm, web-ecommerce-factory, youtube) — are
  untouched; the file stays
  ALLOWED (`check_structure.py:42`) and the governance rule "read if exists; append friction
  findings" (`templates/governance/CLAUDE.md:25`) keeps working as create-on-first-friction.
- **Rejected alternative:** making the sweep a per-commit gate — reading 26 repos per commit is a
  time sink against the no-time-loss constraint; the weekly `fleet_doc_audit.py` cron is the home.
- **Cross-repo authorization:** the `--apply` run deletes + commits + pushes `AFCL.md` in ~31
  foreign repos. The CLAUDE.md cross-repo HARD STOP is satisfied by the operator directive above,
  recorded here verbatim; the script's matcher is scope-limited to byte-exact stubs so no living
  content is reachable.

## Shape decision — MONOLITH (2 phases), stated per the command's Phase-2 gate

Two phases, each the smallest unit carrying its own test cycle and worth a fresh `/fabrik-review`.
Length at review pass 1: 305 lines — marginally over the ~300 emit-time projection, the overage
being absorbed probes and evidence, not additional work units; the shape stands by the same
adjudication the emit rule states ("both shapes are first-class, no forced migration"): 2 phases
≤ 3, and the largest phase READ set (Phase B: `scaffold.py` regions + 4 small scripts/tests) is
far under `READ_BUDGET_BYTES` (262144, `check_plan_tickets.py:83`). Phases are logically
independent BUT both edit
`.windsurf/rules/core/40-documentation.md` — a named serialization point: **A then B, never
parallel.**

## Context Ledger

| Source | What binds | Grounded ref |
|---|---|---|
| `core/40-documentation.md` (ACTIVE, **EDITED by A §1 + B §5**) | doc rules canonical home; § LESSONS_LEARNT.md is where the Ratchet grammar lands; packs state rules present-tense, never change-history | `.windsurf/rules/core/40-documentation.md:24,128-134` |
| `core/10-python.md` (ACTIVE) | the scripts' typing/env discipline; no logfile sinks (12-Factor XI) | pack § typing |
| `core/45-testing-strategy.md` (ACTIVE) | test-per-behavior, watched-fail-first for the risky rows | pack § Behavior Contract |
| `core/62-using-subagents.md` (ACTIVE) | pool-default dispatch for test authoring + review finders; native non-author closing round | pack § Dispatch policy |
| `scripts/fleet_doc_audit.py` | the weekly mechanical rot detector — probes LAG/STALE/STUBS/MISSING; report to `docs/infrastructure/probe-reports/`; **cron `30 6 * * 1 … fleet_doc_audit.py --commit`** — the sweep's home and its wired consumer | `scripts/fleet_doc_audit.py:1-25`; AFTER-EDIT coupling → `tests/test_fleet_doc_audit.py` (`:2`) |
| `scripts/enforcement/_doc_registry.py` | the SSOT doc registry; `DocRow("AFCL.md", …)` — verified ZERO live mechanical consumers for this row (MISSING probe reads the hardcoded `KEY_DOCS` tuple, `fleet_doc_audit.py:64,157`; `docs_allowlist()` returns only flat `docs/*.md` so a root-level row never enters it, `_doc_registry.py:302-306`; stubs/reconcile need a detector AFCL lacks) — retirement is SSOT hygiene, not alarm prevention | `scripts/enforcement/_doc_registry.py:164` |
| `scripts/enforcement/check_doc_stubs.py` | unaffected by the registry-row removal: it checks the intersection of registry × mechanical trigger detectors, and AFCL has no detector ("friction hit" has no code signal) | `check_doc_stubs.py:13,52` |
| `scripts/enforcement/check_structure.py` | AFCL.md is in the root ALLOWLIST (allowed, never required) — absence is legal, entry stays | `check_structure.py:42` |
| `src/fabrik/scaffold.py` | THREE emission blocks: scaffold-time copy · `fix_project` re-creation-if-missing ("Only created if missing") · `fix_project`'s DRY-RUN reporting mirror (same guard, reports "AFCL.md (created)" without copying — found by the deep-round grounder) — retiring only some leaves regeneration or dead code | `scaffold.py:1164-1167`, `:5910` (`def fix_project`), `:6056-6060`, `:6143-6147` |
| `scripts/fabrik_synced_manifest.py` | AFCL is NOT synced (scaffolded per-project) — the NOTE gets updated truthfully; ⚠ the manifest file is itself a governance-sync trigger | `fabrik_synced_manifest.py:58` |
| `templates/governance/CLAUDE.md` + hub `CLAUDE.md` | Completion Contract item 4 is the always-loaded LESSONS mandate the convention extends; § Orient 2 "read if exists; append friction" already tolerates AFCL absence | `templates/governance/CLAUDE.md:50,25`; hub `CLAUDE.md` § Completion Contract item 4 |
| `commands/_fragments/term-coverage.md` | the standing recurrence classes — one of the named graduation DESTINATIONS | `term-coverage.md:10` |
| fabrik-lib | **consulted — no applicable module** (no fleet-file-ops / doc-audit module in the README table; both deliverables extend existing hub scripts) — not a new-module candidate (hub-governance-specific) | `/opt/fabrik-lib/README.md` module table |
| `specs/services/*.yaml` `shape:` | **N/A** — no service, DB, cache, metrics, search, or admin surface | — |

## Global Constraints

- **Governance-sync blast radius — verified against the live filter (`.pre-commit-config.yaml:57`),
  not recalled:** `.windsurf/rules/core/40-documentation.md` (`^\.windsurf/rules/`),
  `templates/governance/CLAUDE.md` (`^templates/governance/`), `scripts/enforcement/_doc_registry.py`
  (`^scripts/enforcement/`), and `scripts/fabrik_synced_manifest.py` (the named-scripts group) ARE
  trigger surfaces — each commit touching them distributes fleet-wide (~48 repos); every edit must
  be correct for ALL projects. **Hub `CLAUDE.md` is NOT a trigger** (the filter has no root-CLAUDE
  pattern — it is the hub agents' own contract; its item-4 edit binds hub sessions only, while the
  `templates/governance/` copy is the fleet's). `scaffold.py`, `fleet_doc_audit.py`,
  `cleanup_afcl_stubs.py`, the workflow docs and the tests are hub-only.
- **Cross-repo law:** the ONLY cross-repo mutation in this plan is `cleanup_afcl_stubs.py --apply`,
  authorized by the operator directive quoted in "What we already agreed". Per foreign repo it may
  do exactly: `git rm AFCL.md` + a pathspec commit with Agent Provenance Trailers + `git push`
  (rejection → report, NEVER `--force`). Nothing else. A dirty `AFCL.md` (uncommitted sibling edit)
  → skip + report, never resolve.
- **Destructive-op law:** dry-run is the script's DEFAULT; `--apply` requires the flag and runs
  only after the dry-run table has been emitted in the same session.
- **No functionality loss:** the convention adds a line to future entries — no existing entry, gate,
  or command behavior changes; the sweep is WARN-tier inside a weekly report, never a commit gate.
  AFCL stays a first-class optional surface (allowlisted root file, create-on-first-friction).
- Pack prose stays present-tense — no change-history in `40-documentation.md` edits.
- 12-Factor: N/A to prose; the scripts add no daemon, logfile sink, host port, or backing-service
  substitution (fleet_doc_audit's report file is its existing documented output, not a log sink).
- Commit discipline: explicit pathspecs + trailers; the four governance files +
  `docs/LESSONS_LEARNT.md` stay OUT of File Scope (shared-append surfaces).

## Phase A — LESSONS graduation status (convention + weekly sweep)

**Interfaces — Consumes:** nothing. **Produces:** the `Ratchet:` grammar. No Phase-B consumer —
the phases share only the `40-documentation.md` file, hence the serialization.

Steps:

0. **Toolchain preflight:** `.venv/bin/python -m pytest --version && git --version` — both exist
   hub-side or the phase stops here.
1. **`.windsurf/rules/core/40-documentation.md` § LESSONS_LEARNT.md (`:128-134`) — add the Ratchet
   grammar as a new `**Ratchet:**` block between the existing `**Format:**` and `**Enforced:**`
   lines** (⚠ governance-sync; repo-agnostic prose only). The canonical entry structure that
   `**Format:**` references (my-workflow/06 § Step 8) is UNCHANGED — the Ratchet line is appended
   to an entry, orthogonal to its structure; no my-workflow edit:
   - Every entry dated on/after **2026-08-11** ends with one line:
     `Ratchet: scripts/enforcement/<check>.py` · `Ratchet: .windsurf/rules/<pack> § <section>` ·
     `Ratchet: term-coverage standing class "<name>"` · `Ratchet: local-only` ·
     `Ratchet: pending — <named next step>`.
   - One sentence of WHY, present-tense: a lesson helps the fleet only after it graduates into an
     enforced surface; the line makes graduation a definition of done, not a habit.
2. **Completion Contract item 4 — one-sentence extension, BOTH copies**
   (`templates/governance/CLAUDE.md:50` and hub `CLAUDE.md` § Completion Contract item 4, same
   sentence): append `Fleet-applicable entries add a Ratchet: line (graduation status: target ·
   local-only · pending) — grammar in .windsurf/rules/core/40-documentation.md § LESSONS_LEARNT.md.`
   (The parenthetical enumerates all THREE status kinds — a closed "target or local-only" would
   mis-train agents that `Ratchet: pending` is invalid, the form they will most often need first;
   deep-round finding.)
3. **`scripts/fleet_doc_audit.py` — probe 5 `UNGRADUATED`** (the wired consumer is the existing
   Monday-06:30 cron — no new invoker needed): for each repo's `docs/LESSONS_LEARNT.md` (and the
   legacy lowercase alias `docs/lessons-learnt.md`), parse deterministically: an ENTRY is the block
   from one `**Date:** YYYY-MM-DD` anchor line to the next anchor (or EOF); its heading for the
   WARN row is the nearest markdown heading ABOVE the anchor (else the anchor line itself); a
   `Ratchet:` token counts iff it appears WITHIN the block. Entries dated ≥ 2026-08-11 lacking one
   are WARN rows in the weekly report (repo · entry heading · date). Tolerance is fail-soft by
   design: a file with zero parseable
   dated entries is skipped silently; any per-repo parse error skips that repo, never the audit.
   ⚠ AFTER-EDIT coupling (`fleet_doc_audit.py:2`): `tests/test_fleet_doc_audit.py` must be staged
   in the same commit.
4. **Tests (`tests/test_fleet_doc_audit.py`)** — pool-authored per the `/fabrik-generate-tests`
   loop (`fanout("code", mode="write")`, disjoint `owned_paths`), executor-curated. Fixture LESSONS
   files covering: post-adoption entry without `Ratchet:` → flagged; with `Ratchet: local-only` →
   silent; pre-adoption entry without → silent; file with no dated entries → repo skipped, exit 0.
   Watched-fail-first on the flagging row; mutation-kill the date threshold (a `<` vs `<=` mutant
   must die).

Validation gate A (runnable): `python -m pytest tests/test_fleet_doc_audit.py -q` green;
`.venv/bin/python scripts/fleet_doc_audit.py --stdout` exits 0 and its summary includes the
`UNGRADUATED` section header.

**Behavior Contract (Phase A):**
- **Given** an entry dated ≥ 2026-08-11 with no `Ratchet:` line, **When** the audit runs, **Then**
  it emits a WARN row naming repo + entry (`scripts/fleet_doc_audit.py`).
- **Given** the same entry carrying `Ratchet: local-only`, **When** the audit runs, **Then** it is
  silent for that entry.
- **Given** an entry dated before 2026-08-11, **When** the audit runs, **Then** it is exempt —
  no retro-fill obligation.
- **Given** a LESSONS file with no parseable dated entries, **When** the audit runs, **Then** the
  repo is skipped and the audit still exits 0.

Closing sequence: gate A → `python scripts/enforcement/check_doc_sync.py` + the phase's CHANGELOG
entry (code + governance changed — a Doc Sync Matrix trigger) → **`/fabrik-review` on Phase A's
changed surface to its coverage-adjudicated exit** (pool finders record to the flywheel +
`set_quality` back-fill; the closing round's finders dispatch to fresh NON-AUTHOR subagents per the
role-separation rule adopted in plan-2) → commit with provenance trailers (governance-sync fires —
re-verify the pack edit reads correctly for a project repo before staging).

## Phase B — AFCL stub retirement (cleanup first, then the emitters)

**Interfaces — Consumes:** nothing from A (shared-file serialization only). **Produces:** a fleet
with only living AFCLs; a scaffolder that never emits the stub.

Steps (cleanup BEFORE emitter retirement — the matcher's forward arm reads the live template, and
no cron invokes `fix_project` between the steps, so nothing regenerates mid-phase):

0. **Phase preflight (deep-round finding — Phase B is the higher-risk phase and had none):**
   `git --version`, then prove push reachability on ONE sample MATCH repo before the loop —
   `git -C <sample> ls-remote --exit-code origin >/dev/null`. If unreachable, `--apply` runs in
   COMMIT-ONLY mode (pushes deferred and reported per repo) rather than failing mid-loop after
   some repos are already processed.
1. **New `scripts/cleanup_afcl_stubs.py`** (with an `# AFTER-EDIT: tests/test_cleanup_afcl_stubs.py`
   header per the script-coupling rule). Behavior:
   - Scan `/opt/*/AFCL.md`, **excluding `/opt/fabrik`**. A file MATCHES iff its whole-file md5 is
     one of the TWO frozen generation hashes — `7521beff3895f7456b0c1981c1632227` (pre-2026-05-16
     template, 19 repos) or `bbce548e3126c0a3da85c87025dd91dc` (current template, 12 repos) — OR
     it is byte-equal to the live `templates/scaffold/AFCL_TEMPLATE.md` (the forward arm, for any
     copy created between census and run). The scaffolder copies verbatim (`shutil.copy`,
     `scaffold.py:1167`) — there is NO rendering, so generation hashes are exact; any appended
     byte breaks the match and the file is KEEP.
   - Default = **dry-run**: print the verdict table (repo · md5 ·
     MATCH/KEEP/SKIP-dirty/SKIP-not-a-repo/SKIP-detached) and exit. A directory that is not a git
     repo → SKIP-not-a-repo (reported, untouched); a repo not on a named branch
     (`git symbolic-ref -q HEAD` fails) → SKIP-detached (no commit is ever attempted there — an
     orphan commit on a detached HEAD is a data-loss shape). The `/opt/*/AFCL.md` glob depth
     structurally excludes `/opt/archived/<project>/` trees.
   - `--apply`, per MATCHED repo only: assert `git -C <repo> status --porcelain -- AFCL.md` is
     empty (else SKIP-dirty + report) → `git rm AFCL.md` → commit with subject
     `chore(afcl): retire scaffold-stub AFCL.md (hub plan 2026-08-11-plan-1)` + trailers
     (`Agent-Role: primary`, `Agent-Context: fleet AFCL stub retirement per hub plan
     2026-08-11-plan-1`), pathspec `-- AFCL.md` → `git push`; push rejection → report and continue
     (committed state is safe), never `--force`. Non-matching files are unreachable by construction.
2. **Run it:** dry-run (expected ~31 MATCH rows — the 2026-08-11 two-generation census, 19 + 12;
   the dry-run table is the truth at execution time), embed the table in the phase's evidence,
   then `--apply`; re-run dry-run after (expect 0 MATCH rows).
3. **Retire the emitters — all THREE blocks:** delete the scaffold-time copy
   (`scaffold.py:1164-1167`), the `fix_project` re-creation block (`scaffold.py:6056-6060`, inside
   `def fix_project` `:5910`), AND the `fix_project` dry-run reporting mirror
   (`scaffold.py:6143-6147` — same `afcl_template.exists() and not afcl_target.exists()` guard,
   emits `"AFCL.md (created)"` into the dry-run report; left in place it becomes unreachable dead
   code referencing a deleted template, and the rewritten test at `test_scaffold_fix.py` Case-2
   would pass vacuously without ever forcing its removal);
   delete `templates/scaffold/AFCL_TEMPLATE.md`; update the manifest NOTE
   (`fabrik_synced_manifest.py:58`) to state present-tense truth: AFCL is optional,
   created-on-first-friction, never scaffolded, never synced.
4. **Retire the registry row** `_doc_registry.py:164` — as SSOT hygiene, with the honest,
   round-1-verified rationale: the row has NO live mechanical consumer (the MISSING probe iterates
   the hardcoded `KEY_DOCS` tuple, `fleet_doc_audit.py:64,157` — AFCL is not in it;
   `docs_allowlist()` returns only the flat `docs/*.md` set so a root-level row never enters it,
   `_doc_registry.py:302-306`; `check_doc_stubs`/`doc_reconcile` need a trigger detector AFCL
   lacks, `check_doc_stubs.py:13,52`). A registry that keeps describing a doc no one scaffolds or
   obligates misleads the NEXT consumer someone writes against it — that is the defect being
   retired. `check_structure.py:42` allowlist stays (the file remains legal where it lives or is
   later created).
5. **`40-documentation.md:24`** — annotate AFCL in the doc-surface list: `(optional — created at
   first friction, never scaffolded)`. Present-tense, fleet-true. (⚠ governance-sync, same file
   Phase A touched — the serialization point.)
5b. **Update the three hub workflow docs that assert the retired behavior** (found by the pass-1
   grounder; all hand-maintained, none generated): `docs/workflows/DATA_SYNC_WORKFLOW.md:123` and
   `docs/workflows/SYNC_ENFORCEMENT_WORKFLOW.md:50` (both say "AFCL.md is scaffolded as
   AFCL_TEMPLATE.md and customized per project") and
   `docs/workflows/FABRIK_SCAFFOLD_WORKFLOW.md:1170` (lists `AFCL_TEMPLATE.md` as a live template
   file) — rewrite each to the present-tense truth: AFCL is optional, created at first friction,
   never scaffolded, never synced.
6. **Tests** (pool-authored per `/fabrik-generate-tests`, executor-curated):
   - `tests/test_scaffold_fix.py` — **REWRITE, do not merely extend**: the pre-existing
     `TestFixProjectAFCLPreservation` class (`:61`) contains `test_missing_afcl_is_created_from_template`
     (`:81`) and the Case-2 half of `test_dry_run_reports_afcl_only_when_missing`, both asserting
     the creation-when-missing behavior this phase REMOVES, both guarded by
     `AFCL_TEMPLATE.md exists()` — after step 3 deletes the template those guards go False and the
     tests become vacuous no-ops with docstrings describing removed behavior. Rewrite them into
     "fix_project never creates `AFCL.md`" assertions; KEEP the `:64` preservation test
     ("project-local content survives") as the re-introduction guard.
   - `tests/test_scaffold_doc_seeding.py` — add "a fresh scaffold contains NO `AFCL.md`" — and
     note the existing `mock_root` fixture (`:110-130`) carries NO `AFCL_TEMPLATE.md` double, so
     on PRE-fix code the assertion would already pass vacuously. Add the template double to the
     fixture FIRST so the new assertion is RED on pre-fix code (real watched-fail-first /
     red-on-revert), then apply the scaffolder change and watch it green.
   - New `tests/test_cleanup_afcl_stubs.py` on tmp-dir fixture repos: BOTH generation hashes →
     MATCH; content-modified → KEEP; dirty-AFCL → SKIP-dirty; dry-run mutates nothing (tree-hash
     assert).

Validation gate B (runnable): `python -m pytest tests/test_cleanup_afcl_stubs.py
tests/test_scaffold_doc_seeding.py tests/test_scaffold_fix.py tests/test_fleet_doc_audit.py -q`
green; `.venv/bin/python scripts/cleanup_afcl_stubs.py` (dry-run) exits 0 post-apply reporting
EITHER 0 MATCH rows OR only MATCH rows belonging to SKIP-dirty/SKIP-detached/SKIP-not-a-repo
repos, each named in the phase evidence (a legitimately-skipped repo is a report line for the
operator, never a gate failure — deep-round finding); `.venv/bin/python scripts/fleet_doc_audit.py
--stdout` exits 0 with zero AFCL-MISSING rows.

**Behavior Contract (Phase B):**
- **Given** a byte-exact stub AFCL, **When** `--apply` runs, **Then** the file is removed,
  committed with trailers, and pushed in its own repo (`scripts/cleanup_afcl_stubs.py`).
- **Given** an AFCL whose content differs from the stub, **When** the script runs, **Then** the
  repo is KEEP and untouched.
- **Given** an uncommitted local edit to a repo's AFCL, **When** `--apply` runs, **Then** the repo
  is SKIP-dirty and untouched.
- **Given** dry-run mode, **When** the script runs, **Then** no repo mutates (tree-hash assert).
- **Given** a fresh `fabrik scaffold`, **When** it completes, **Then** no `AFCL.md` exists
  (`src/fabrik/scaffold.py:1164`).
- **Given** `fix_project` on a repo without AFCL, **When** it runs (real or dry-run), **Then** it
  neither re-creates the file nor reports `"AFCL.md (created)"`
  (`src/fabrik/scaffold.py:6056`, `:6143-6147`).

Closing sequence: gate B → `check_doc_sync.py` + declared doc steps (CHANGELOG entry; INDEX.md is
orchestrator-applied) → **`/fabrik-review` to a coverage-adjudicated exit** (same dispatch shape as
Phase A) → `/fabrik-docs-review` → `python scripts/final_gate.py --check --json` to
`"status":"success"` → `python scripts/enforcement/check_convergence.py` → commit.

## File Scope (owned paths)

- `.windsurf/rules/core/40-documentation.md`
- `templates/governance/CLAUDE.md`
- `CLAUDE.md`
- `scripts/fleet_doc_audit.py`
- `tests/test_fleet_doc_audit.py`
- `scripts/cleanup_afcl_stubs.py`
- `tests/test_cleanup_afcl_stubs.py`
- `src/fabrik/scaffold.py`
- `tests/test_scaffold_doc_seeding.py`
- `tests/test_scaffold_fix.py`
- `scripts/enforcement/_doc_registry.py`
- `scripts/fabrik_synced_manifest.py`
- `templates/scaffold/AFCL_TEMPLATE.md` (deleted)
- `docs/workflows/DATA_SYNC_WORKFLOW.md`
- `docs/workflows/SYNC_ENFORCEMENT_WORKFLOW.md`
- `docs/workflows/FABRIK_SCAFFOLD_WORKFLOW.md`

(The ~31 foreign-repo `AFCL.md` deletions are the script's authorized runtime effect, not owned
paths — File Scope is hub-local by the gate's own out-of-repo ban. CHANGELOG/INDEX/docs
README/FEATURES + `docs/LESSONS_LEARNT.md` stay OUT — shared-append surfaces.)

## Evidence

- The read/write asymmetry that motivates Phase A — zero read-mandates in the corpus (captured
  2026-08-11):

```
$ cd /opt/fabrik/commands/_sources && grep -in 'read.*lessons\|lessons.*before\|consult.*lessons' *.md ../_fragments/*.md
fabrik-plan-review.md:63:  governance files** CHANGELOG/INDEX/docs README/FEATURES + docs/LESSONS_LEARNT.md, which stay OUT of
fabrik-plan-after-chat.md:295:README/FEATURES + docs/LESSONS_LEARNT.md — and its legacy lowercase alias `docs/lessons-learnt.md`,
fabrik-plan-after-chat.md:560:  governance files** CHANGELOG/INDEX/docs README/FEATURES + docs/LESSONS_LEARNT.md, which stay OUT
```

  (All three hits are File-Scope bookkeeping, not read mandates.)

- The stub monoculture that motivates Phase B — the UNFILTERED census (captured 2026-08-11 by the
  pass-1 native grounder; the first version of this probe pre-filtered on size 1045 and missed the
  entire second generation — the size filter is exactly the probe defect the probe duty warns
  about):

```
$ for f in /opt/*/AFCL.md; do [ "$(dirname $f)" = "/opt/fabrik" ] && continue; md5sum "$f"; done \
    | awk '{print $1}' | sort | uniq -c | sort -rn
     19 7521beff3895f7456b0c1981c1632227
     12 bbce548e3126c0a3da85c87025dd91dc
      1 c414ec5432f1fb5572babbdbd2e27df1
      1 ab4e6939c785affe2a7236d3366393a4
      1 8887232abcf2a5ca84964ff2a9f403f2
      1 28ac39279165917a30e68f0f5b1b9e0a
      1 24c0721f55bd97cbe8fb587fa1674e92
      1 1da4c27fcd8fc68fc46a4e159899f724
      1 1aee5e4da1a9858884c61f3c8cf0ca45
$ md5sum templates/scaffold/AFCL_TEMPLATE.md
bbce548e3126c0a3da85c87025dd91dc  templates/scaffold/AFCL_TEMPLATE.md
```

  (31 of 38 non-hub copies are byte-identical templates across two generations; the 7 singleton
  hashes are the living/diverged AFCLs the matcher can never touch.)

- The regeneration hazard — `fix_project` re-creates a missing AFCL (`src/fabrik/scaffold.py:6056-6060`):

```
        afcl_template = FABRIK_ROOT / "templates" / "scaffold" / "AFCL_TEMPLATE.md"
        afcl_target = project_path / "AFCL.md"
        if afcl_template.exists() and not afcl_target.exists():
            shutil.copy(afcl_template, afcl_target)
            added.append("AFCL.md (created)")
```

- The sweep's wired consumer — the existing weekly cron (captured from `crontab -l`, 2026-08-11):

```
30 6 * * 1 cd /opt/fabrik && .venv/bin/python scripts/fleet_doc_audit.py --commit >> /tmp/fleet_doc_audit.log 2>&1
```

- The registry row the cleanup must retire — `scripts/enforcement/_doc_registry.py:164`:

```
    DocRow("AFCL.md", "AFCL_TEMPLATE.md", frozenset({"universal"}), "friction hit", "agent"),
```

## Self-audit

Grounding passes run this session: (1) fleet measurement (AFCL md5 census, LESSONS recency,
corpus read/write-mandate grep) — produced the problem statement; the census was then CORRECTED in
review pass 1 (the authoring probe size-filtered and missed the 12-repo second generation — 31
stubs, not 19); (2) consumer trace of AFCL (scaffold-time emitter + `fix_project` re-creation +
`_doc_registry` row + `check_structure` allowlist + `check_doc_stubs` intersection + sync-manifest
NOTE + the three hub workflow docs) — produced Phase B's step set; the registry-row rationale was
CORRECTED in pass 1 (no live consumer — SSOT hygiene, not alarm prevention: `KEY_DOCS` is
hardcoded, `docs_allowlist()` is flat-docs-only); (3) sweep-home trace (`fleet_doc_audit.py`
probes + cron + AFTER-EDIT coupling) — produced Phase A step 3; (4) fabrik-lib table consulted —
no applicable module; (5) governance-sync triggers verified against the live filter, not recalled
(hub `CLAUDE.md` is NOT one).

**(a) Coverage of "What we already agreed":** graduation convention → Phase A steps 1-2 · weekly
WARN sweep → Phase A steps 3-4 · pre-adoption exemption → A step 3 + BC row 3 · stub cleanup
dry-run-first → B steps 1-2 · emitter retirement (all THREE blocks) → B step 3 · registry retirement →
B step 4 · stale workflow-doc truth → B step 5b · living AFCLs untouched + file stays legal →
B matcher + `check_structure` row · cross-repo authorization → Global Constraints. No agreed item
unassigned.

**(b) Cross-phase signature consistency:** the phases share no Produces/Consumes — only the
`40-documentation.md` file, declared as a serialization point (A then B).

Review state: CONVERGED under `/fabrik-plan-review`, three passes — pass 1 (pool 2 units + native
non-author grounder; 13 edits: census corrected 19→31 two-generation, registry rationale
de-fabricated, hub CLAUDE.md de-listed as a trigger, three workflow docs into scope, test-rewrite
+ fixture-double specifics) · pass 2 (non-author wave verifier: all 7 corrections VERIFIED true;
its 2 defects + the orchestrator's 7 remnants, 9 edits) · pass 3 (confirming full linear re-read:
zero candidates, zero edits, md5 stable) · operator-ordered DEEP round 2 (3 fresh pool units + a
second native full re-ground, blind to prior passes: the third scaffolder emission block
`:6143-6147`, the item-4 parenthetical, parser determinism, cleanup-script edge semantics, the
gate-B SKIP carve-out, Phase-B preflight). The Pass Ledger with md5s is reproduced in each review
invocation's report output (term-edit contract — plan reviews persist no separate review file;
that mandate is term-coverage's, for code reviews); the Status flipped on an edit-free,
md5-verified no-op and was re-verified after the deep round.

## Residual unknowns

**Resolved:** whether deletion breaks a gate (no — `check_structure` allows; the registry row has
NO live mechanical consumer at all, so nothing false-alarms with or without it — its retirement in
B step 4 is SSOT hygiene); whether anything regenerates the stub (`fix_project` does — retired in
B step 3); where the sweep runs (the existing Monday cron — no new invoker).

**Still open:**

1. **Project-local LESSONS formats vary** (hub-style vs loose) — the date-anchored parser is
   deliberately fail-soft; resolution: observe the first weekly reports; a repo that never parses
   simply gets no graduation nudge (acceptable — WARN-tier advisory).
2. **Retro-filling hub Lessons 100–109 with Ratchet lines** — optional operator follow-up, out of
   scope (shared-append surface, exemption-by-date already keeps the sweep quiet on them).
3. **`Ratchet: pending` aging** (should a pending older than N weeks escalate?) — decide with real
   report data, not now.
