# Plan — Knowledge-surface ratchet: LESSONS graduation status + AFCL stub retirement

Status: DRAFT
Owner: hub (governance + scaffolder + fleet audit)
Operator directive (verbatim, 2026-08-11): "adopt the graduation-status convention and/or the AFCL
stub cleanup as a small follow-up plan, afterwards /fabrik-plan-review"

## What we already agreed

- **The measured problem (2026-08-11, this session):** LESSONS_LEARNT is write-enforced but
  read-never — zero read-mandates in the whole command corpus (grep evidence below); its real value
  path is graduation into gates/rules (hub Lessons 100–109 nearly all became enforcement checks or
  pack rules). AFCL is the inverse: read-mandated in six governance places but **19 of ~20 project
  copies are the identical untouched 1,045-byte scaffold stub** (one shared md5, last commits
  2026-05-03) — every task pays a mandated read that returns an empty template.
- **Adopted fix 1 — graduation-status convention:** every fleet-applicable `docs/LESSONS_LEARNT.md`
  entry dated on/after 2026-08-11 carries a one-line `Ratchet:` status naming where it graduated
  (enforcement check · rule-pack section · `term-coverage` standing recurrence class) or `local-only`
  / `pending — <named next step>`. A weekly WARN-tier sweep flags post-adoption entries missing the
  line. Pre-adoption entries are exempt by date — no retro-fill obligation (LESSONS_LEARNT is a
  shared-append surface outside any plan lock; retro-fill is an optional operator follow-up).
- **Adopted fix 2 — AFCL stub retirement:** delete the never-appended stubs across the fleet
  (dry-run first, exact-match only), retire BOTH scaffolder emission sites and the template, and
  retire the doc-registry row that would otherwise report the deletion as MISSING weekly. Living
  AFCLs (hub 6.4KB/21 entries, brand-identiy-creator 3.5KB) are untouched; the file stays ALLOWED
  (`check_structure.py:42`) and the governance rule "read if exists; append friction findings"
  (`templates/governance/CLAUDE.md:25`) keeps working as create-on-first-friction.
- **Rejected alternative:** making the sweep a per-commit gate — reading 26 repos per commit is a
  time sink against the no-time-loss constraint; the weekly `fleet_doc_audit.py` cron is the home.
- **Cross-repo authorization:** the `--apply` run deletes + commits + pushes `AFCL.md` in ~19
  foreign repos. The CLAUDE.md cross-repo HARD STOP is satisfied by the operator directive above,
  recorded here verbatim; the script's matcher is scope-limited to byte-exact stubs so no living
  content is reachable.

## Shape decision — MONOLITH (2 phases), stated per the command's Phase-2 gate

Two phases, each the smallest unit carrying its own test cycle and worth a fresh `/fabrik-review`.
Projected length ~270 lines (under the ~300 trigger); the largest phase READ set (Phase B:
`scaffold.py` regions + 4 small scripts/tests) is far under `READ_BUDGET_BYTES` (262144,
`check_plan_tickets.py:83`); 2 phases ≤ 3. Phases are logically independent BUT both edit
`.windsurf/rules/core/40-documentation.md` — a named serialization point: **A then B, never
parallel.**

## Context Ledger

| Source | What binds | Grounded ref |
|---|---|---|
| `core/40-documentation.md` (ACTIVE, **EDITED by A §1 + B §3**) | doc rules canonical home; § LESSONS_LEARNT.md is where the Ratchet grammar lands; packs state rules present-tense, never change-history | `.windsurf/rules/core/40-documentation.md:24,128-130` |
| `core/10-python.md` (ACTIVE) | the scripts' typing/env discipline; no logfile sinks (12-Factor XI) | pack § typing |
| `core/45-testing-strategy.md` (ACTIVE) | test-per-behavior, watched-fail-first for the risky rows | pack § Behavior Contract |
| `core/62-using-subagents.md` (ACTIVE) | pool-default dispatch for test authoring + review finders; native non-author closing round | pack § Dispatch policy |
| `scripts/fleet_doc_audit.py` | the weekly mechanical rot detector — probes LAG/STALE/STUBS/MISSING; report to `docs/infrastructure/probe-reports/`; **cron `30 6 * * 1 … fleet_doc_audit.py --commit`** — the sweep's home and its wired consumer | `scripts/fleet_doc_audit.py:1-25`; AFTER-EDIT coupling → `tests/test_fleet_doc_audit.py` (`:2`) |
| `scripts/enforcement/_doc_registry.py` | the SSOT doc registry; `DocRow("AFCL.md", "AFCL_TEMPLATE.md", {"universal"}, "friction hit", "agent")` — feeds fleet_doc_audit's MISSING probe, so it MUST retire with the stubs | `scripts/enforcement/_doc_registry.py:164` |
| `scripts/enforcement/check_doc_stubs.py` | unaffected by the registry-row removal: it checks the intersection of registry × mechanical trigger detectors, and AFCL has no detector ("friction hit" has no code signal) | `check_doc_stubs.py:13,52` |
| `scripts/enforcement/check_structure.py` | AFCL.md is in the root ALLOWLIST (allowed, never required) — absence is legal, entry stays | `check_structure.py:42` |
| `src/fabrik/scaffold.py` | BOTH emission sites: scaffold-time copy + `fix_project` re-creation-if-missing ("Only created if missing") — retiring only one regenerates the stubs | `scaffold.py:1164-1167`, `:5910` (`def fix_project`), `:6056-6060` |
| `scripts/fabrik_synced_manifest.py` | AFCL is NOT synced (scaffolded per-project) — the NOTE gets updated truthfully; ⚠ the manifest file is itself a governance-sync trigger | `fabrik_synced_manifest.py:58` |
| `templates/governance/CLAUDE.md` + hub `CLAUDE.md` | Completion Contract item 4 is the always-loaded LESSONS mandate the convention extends; § Orient 2 "read if exists; append friction" already tolerates AFCL absence | `templates/governance/CLAUDE.md:50,25`; hub `CLAUDE.md` § Completion Contract item 4 |
| `commands/_fragments/term-coverage.md` | the standing recurrence classes — one of the named graduation DESTINATIONS | `term-coverage.md:10` |
| fabrik-lib | **consulted — no applicable module** (no fleet-file-ops / doc-audit module in the README table; both deliverables extend existing hub scripts) — not a new-module candidate (hub-governance-specific) | `/opt/fabrik-lib/README.md` module table |
| `specs/services/*.yaml` `shape:` | **N/A** — no service, DB, cache, metrics, search, or admin surface | — |

## Global Constraints

- **Governance-sync blast radius — know it before staging:** `.windsurf/rules/core/40-documentation.md`,
  `templates/governance/CLAUDE.md`, hub `CLAUDE.md`, `scripts/enforcement/_doc_registry.py`, and
  `scripts/fabrik_synced_manifest.py` are ALL pre-commit governance-sync trigger surfaces — each
  commit touching them distributes fleet-wide (~48 repos). Every edit must be correct for ALL
  projects. `scaffold.py`, `fleet_doc_audit.py`, `cleanup_afcl_stubs.py` and the tests are hub-only.
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

**Interfaces — Consumes:** nothing. **Produces:** the `Ratchet:` grammar (consumed by Phase B's
nothing — phases share only the `40-documentation.md` file, hence the serialization).

Steps:

0. **Toolchain preflight:** `.venv/bin/python -m pytest --version && git --version` — both exist
   hub-side or the phase stops here.
1. **`.windsurf/rules/core/40-documentation.md` § LESSONS_LEARNT.md (`:128-130`) — add the Ratchet
   grammar** (⚠ governance-sync; repo-agnostic prose only):
   - Every entry dated on/after **2026-08-11** ends with one line:
     `Ratchet: scripts/enforcement/<check>.py` · `Ratchet: .windsurf/rules/<pack> § <section>` ·
     `Ratchet: term-coverage standing class "<name>"` · `Ratchet: local-only` ·
     `Ratchet: pending — <named next step>`.
   - One sentence of WHY, present-tense: a lesson helps the fleet only after it graduates into an
     enforced surface; the line makes graduation a definition of done, not a habit.
2. **Completion Contract item 4 — one-sentence extension, BOTH copies**
   (`templates/governance/CLAUDE.md:50` and hub `CLAUDE.md` § Completion Contract item 4, same
   sentence): append `Fleet-applicable entries add a Ratchet: line (graduation target or
   local-only) — grammar in .windsurf/rules/core/40-documentation.md § LESSONS_LEARNT.md.`
3. **`scripts/fleet_doc_audit.py` — probe 5 `UNGRADUATED`** (the wired consumer is the existing
   Monday-06:30 cron — no new invoker needed): for each repo's `docs/LESSONS_LEARNT.md` (and the
   legacy lowercase alias), parse entries as blocks anchored on `**Date:** YYYY-MM-DD` matches;
   entries dated ≥ 2026-08-11 lacking a `Ratchet:` token are WARN rows in the weekly report
   (repo · entry heading · date). Tolerance is fail-soft by design: a file with zero parseable
   dated entries is skipped silently; any per-repo parse error skips that repo, never the audit.
   ⚠ AFTER-EDIT coupling (`fleet_doc_audit.py:2`): `tests/test_fleet_doc_audit.py` must be staged
   in the same commit.
4. **Tests (`tests/test_fleet_doc_audit.py`)** — fixture LESSONS files covering: post-adoption
   entry without `Ratchet:` → flagged; with `Ratchet: local-only` → silent; pre-adoption entry
   without → silent; file with no dated entries → repo skipped, exit 0. Watched-fail-first on the
   flagging row; mutation-kill the date threshold (a `<` vs `<=` mutant must die).

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

Closing sequence: gate A → `python scripts/enforcement/check_doc_sync.py` → **`/fabrik-review` on
Phase A's changed surface to its coverage-adjudicated exit** (pool finders record to the flywheel +
`set_quality` back-fill; the closing round's finders dispatch to fresh NON-AUTHOR subagents per the
role-separation rule adopted in plan-2) → commit with provenance trailers (governance-sync fires —
re-verify the pack edit reads correctly for a project repo before staging).

## Phase B — AFCL stub retirement (cleanup first, then the emitters)

**Interfaces — Consumes:** nothing from A (shared-file serialization only). **Produces:** a fleet
with only living AFCLs; a scaffolder that never emits the stub.

Steps (cleanup BEFORE emitter retirement — the matcher normalizes against the live template, and
no cron invokes `fix_project` between the steps, so nothing regenerates mid-phase):

1. **New `scripts/cleanup_afcl_stubs.py`** (with an `# AFTER-EDIT: tests/test_cleanup_afcl_stubs.py`
   header per the script-coupling rule). Behavior:
   - Scan `/opt/*/AFCL.md`, **excluding `/opt/fabrik`**. A file MATCHES iff its whole-file md5
     equals the measured stub corpus md5 `7521beff3895f7456b0c1981c1632227` OR its content equals
     `templates/scaffold/AFCL_TEMPLATE.md` after stripping the `**Date:**` line from both (catches
     a stub scaffolded on a different date; the template md5 `bbce548e…` differs from the corpus
     only by date substitution).
   - Default = **dry-run**: print the verdict table (repo · md5 · MATCH/KEEP/SKIP-dirty) and exit.
   - `--apply`, per MATCHED repo only: assert `git -C <repo> status --porcelain -- AFCL.md` is
     empty (else SKIP-dirty + report) → `git rm AFCL.md` → `git commit -- AFCL.md` with trailers
     (`Agent-Role: primary`, `Agent-Context: fleet AFCL stub retirement per hub plan
     2026-08-11-plan-1`) → `git push`; push rejection → report and continue (committed state is
     safe), never `--force`. Non-matching files are unreachable by construction.
2. **Run it:** dry-run (expect 19 MATCH rows — the corpus measured 2026-08-11), embed the table in
   the phase's evidence, then `--apply`; re-run dry-run after (expect 0 MATCH rows).
3. **Retire the emitters:** delete the scaffold-time copy (`scaffold.py:1164-1167`) and the
   `fix_project` re-creation block (`scaffold.py:6056-6060`, inside `def fix_project` `:5910`);
   delete `templates/scaffold/AFCL_TEMPLATE.md`; update the manifest NOTE
   (`fabrik_synced_manifest.py:58`) to state present-tense truth: AFCL is optional,
   created-on-first-friction, never scaffolded, never synced.
4. **Retire the registry row** `_doc_registry.py:164` — otherwise `fleet_doc_audit`'s MISSING
   probe reports every cleaned repo weekly. `check_doc_stubs` is unaffected (intersection design,
   no AFCL detector — `check_doc_stubs.py:13,52`); `check_structure.py:42` allowlist stays (the
   file remains legal where it lives or is later created).
5. **`40-documentation.md:24`** — annotate AFCL in the doc-surface list: `(optional — created at
   first friction, never scaffolded)`. Present-tense, fleet-true. (⚠ governance-sync, same file
   Phase A touched — the serialization point.)
6. **Tests:** extend `tests/test_scaffold_doc_seeding.py` (a fresh scaffold contains NO
   `AFCL.md`) and `tests/test_scaffold_fix.py` (`fix_project` does not re-create a missing
   `AFCL.md`; an EXISTING file is left untouched); new `tests/test_cleanup_afcl_stubs.py` on
   tmp-dir fixture repos (exact stub → MATCH; content-modified → KEEP; dirty-AFCL → SKIP-dirty;
   dry-run mutates nothing — assert tree hashes unchanged). Watched-fail-first on the
   fix_project row (it is the regeneration hazard).

Validation gate B (runnable): `python -m pytest tests/test_cleanup_afcl_stubs.py
tests/test_scaffold_doc_seeding.py tests/test_scaffold_fix.py tests/test_fleet_doc_audit.py -q`
green; `.venv/bin/python scripts/cleanup_afcl_stubs.py` (dry-run) exits 0 reporting 0 MATCH rows
post-apply; `.venv/bin/python scripts/fleet_doc_audit.py --stdout` exits 0 with zero AFCL-MISSING
rows.

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
- **Given** `fix_project` on a repo without AFCL, **When** it runs, **Then** it does not re-create
  it (`src/fabrik/scaffold.py:6056`).

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

(The ~19 foreign-repo `AFCL.md` deletions are the script's authorized runtime effect, not owned
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

- The stub monoculture that motivates Phase B — one md5 across 19 repos (captured 2026-08-11):

```
$ for f in /opt/*/AFCL.md; do [ "$(stat -c%s $f)" = "1045" ] && md5sum "$f"; done | awk '{print $1}' | sort | uniq -c
     19 7521beff3895f7456b0c1981c1632227
```

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
corpus read/write-mandate grep) — produced the problem statement; (2) consumer trace of AFCL
(scaffold-time emitter + `fix_project` re-creation + `_doc_registry` row + `check_structure`
allowlist + `check_doc_stubs` intersection + sync-manifest NOTE) — produced Phase B's step set,
including the two non-obvious retirements (fix_project, registry row) without which the cleanup
regenerates or false-alarms; (3) sweep-home trace (`fleet_doc_audit.py` probes + cron + AFTER-EDIT
coupling) — produced Phase A step 3; (4) fabrik-lib table consulted — no applicable module.

**(a) Coverage of "What we already agreed":** graduation convention → Phase A steps 1-2 · weekly
WARN sweep → Phase A steps 3-4 · pre-adoption exemption → A step 3 + BC row 3 · stub cleanup
dry-run-first → B steps 1-2 · emitter retirement (both sites) → B step 3 · registry retirement →
B step 4 · living AFCLs untouched + file stays legal → B matcher + `check_structure` row ·
cross-repo authorization → Global Constraints. No agreed item unassigned.

**(b) Cross-phase signature consistency:** the phases share no Produces/Consumes — only the
`40-documentation.md` file, declared as a serialization point (A then B).

Not a fixed point yet: `/fabrik-plan-review` has not run.

## Residual unknowns

**Resolved:** whether deletion breaks a gate (no — `check_structure` allows, `check_doc_stubs` has
no AFCL detector; the one true consumer, `fleet_doc_audit` MISSING, is retired in B step 4);
whether anything regenerates the stub (`fix_project` does — retired in B step 3); where the sweep
runs (the existing Monday cron — no new invoker).

**Still open:**

1. **Project-local LESSONS formats vary** (hub-style vs loose) — the date-anchored parser is
   deliberately fail-soft; resolution: observe the first weekly reports; a repo that never parses
   simply gets no graduation nudge (acceptable — WARN-tier advisory).
2. **Retro-filling hub Lessons 100–109 with Ratchet lines** — optional operator follow-up, out of
   scope (shared-append surface, exemption-by-date already keeps the sweep quiet on them).
3. **`Ratchet: pending` aging** (should a pending older than N weeks escalate?) — decide with real
   report data, not now.
