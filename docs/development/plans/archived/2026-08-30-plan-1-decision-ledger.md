# Plan 1 — The Decision Ledger (fleet-wide, per the CONVERGED spec)

Status: EXECUTED 2026-08-30 (phases 0d2ca091 · 18e38d9c · b321ea39; whole-plan review PASS — docs/development/reviews/2026-08-30-decision-ledger-plan-review.md; 48 repos seeded; was CONVERGED — /fabrik-plan-review x2: converged at 4d848206; post-flip dogfood edit re-reviewed same day — the quote-table conversion had dropped 3 prose constraints, restored + re-verified to a no-op, check_rule_grounding 0 findings)
Spec: docs/superpowers/specs/2026-08-30-decision-ledger-v2-design.md (CONVERGED, operator-approved
2026-08-30: "go back to the spec you have created and /fabrik-plan-after-chat on it")
Shape: MONOLITH — 3 phases, each independently testable; READ set per phase under 262144
(largest = Phase B, measured: `find CLAUDE.md templates/governance/CLAUDE.md scripts/fabrik_synced_manifest.py
scripts/sync_enforcement_to_projects.py -type f -exec cat {} + | wc -c` → 170198, stderr clean).

## Intake Inventory

| I# | Item (anchored) | Disposition | Where |
|---|---|---|---|
| I1 | "go back to the spec you have created and /fabrik-plan-after-chat on it" | IN — this plan, all 3 phases | whole plan |
| I2 | beat split: templates/scaffold seed "ground from how templates/scaffold/ is owned in practice" | IN — grounded: `git log -5` shows fleet's last 2 + infra's 54685ee6; the TEMPLATE file is a safe in-repo add, the scaffolder WIRING line is fleet's — split accordingly | Phase B step 6 |
| I3 | "new .md allowlist already covers docs/DECISIONS.md? — VERIFY" | IN — verified NO: `_doc_registry.docs_allowlist()` = 16 names, no DECISIONS (probe below); adding it is Phase A step 4 | Phase A |
| I4 | "seed-if-missing must NEVER overwrite an existing ledger" | IN — dest-exists() skip, stronger than PORTS.md's newer-mtime skip (spec § Distribution says "NEVER touches an existing ledger"); red-first test is the phase's highest-risk test | Phase B steps 2–3 |
| I5 | "NO-POOL: run natively" | IN | § Execution Discipline |

Intake: 5 items — 5 IN, 0 OUT-OF-SCOPE, 0 ASK.

## What we already agreed (from the spec — settled, not re-litigated)

- Storage = per-repo `docs/DECISIONS.md` FILE (postgres/JSONL/per-file-ADRs/semantic all rejected with
  grounded reasons); rows immutable, changed decision = new row `supersedes D-NNN`.
- Row = `| id | when | who | what | why | where |` (the operator's W5); append-at-top; D-000 records adoption.
- Write duty (rulings, adoptions/retirements, Status flips, "built X at Y") + query duty (ledger-grep
  BEFORE answering "where is X / did we decide Y") in both CLAUDE.md files + Doc Sync Matrix row +
  close-feedback line; subagents/pipeline never hold the pen.
- Enforcement advisory-first; ONE mechanical row: supersede pointers must resolve (in the helper).
- Distribution: scaffolder seeds new repos; existing ~46 seeded-IF-MISSING via the sync; hub ledger
  seeded with this week's real decisions. No backfill beyond that.
- Docs land at `docs/reference/decision-ledger.md` (+ INDEX/docs-README rows); `DECISIONS.md` joins
  the naming exceptions.

## Context Ledger

| Source | What binds | Grounded ref |
|---|---|---|
| spec (CONVERGED) | the whole design; this plan builds it verbatim | docs/superpowers/specs/2026-08-30-decision-ledger-v2-design.md |
| core/10-python.md (ACTIVE) | stdlib CLI discipline for the helper; typing; no new deps | .windsurf/rules/core/10-python.md |
| core/40-documentation.md (ACTIVE) | doc shapes; Doc Sync Matrix floor | .windsurf/rules/core/40-documentation.md |
| core/45-testing-strategy.md (ACTIVE) | behavior-per-test, red-first for the risky path | .windsurf/rules/core/45-testing-strategy.md |
| doc registry (SSOT for docs/ allowlist) | DECISIONS.md must be ADDED or 46 gates red the seeded file | scripts/enforcement/_doc_registry.py:194 area (docs names set); probe: `docs_allowlist()` → 16, no DECISIONS |
| synced manifest | SEEDED_NOT_ENFORCED + pair legs are the distribution grammar | scripts/fabrik_synced_manifest.py:137 (`SEEDED_NOT_ENFORCED = {"PORTS.md"}`), :93 (GOVERNANCE_TEMPLATES leg), :146 (PORTS pair) |
| sync copier | where the exists()-skip lands | scripts/sync_enforcement_to_projects.py:347 (`if not destination.exists()` branch of `_sync_file`) |
| scaffolder template map | template→emitted-doc mapping is enumerated CODE (fleet's) | src/fabrik/scaffold.py:270,274 (`docs/RESILIENCE_TEMPLATE.md: docs/RESILIENCE.md`) |
| corpus wiring points | ledger joins the derivation/query surfaces | commands/_fragments/chat-intake.md:29 (ASK-bar sources); commands/_sources/fabrik-spec.md § Phase 0 episodic-memory step; commands/_fragments/close-feedback.md (before-done duty) |
| governance sync triggers | CLAUDE.md + templates/governance/ + fragments distribute fleet-wide on commit | .pre-commit-config.yaml governance-sync files-filter |
| fabrik-lib README | no module fits (grep: 1 irrelevant hit); helper is process tooling below the module bar — spec verdict table | /opt/fabrik-lib/README.md |

## Constraints Digest

| rule (verbatim) | where | implication here |
|---|---|---|
| "Use type hints for all function signatures" | .windsurf/rules/core/10-python.md:150 | `decisions.py` fully typed |
| "a non-trivial behavior's test proves something only if it has been SEEN RED" | .windsurf/rules/core/45-testing-strategy.md:21 | A1/B1 red-first, watched |
| "🔴 = the gate **hard-blocks the commit** if it's stale (`check_doc_sync` ERROR-tier)." | .windsurf/rules/core/40-documentation.md:21 | INDEX/CHANGELOG rows land same-change, never deferred |
| "explicit pathspecs only" | CLAUDE.md | every phase commit; never bundle sibling files |
| "Merge-time render only: NEVER bare-render `commands/assemble_commands.py` from a worktree" | CLAUDE.md | Phase C renders from the MAIN checkout |
| "kebab-case" | CLAUDE.md | naming; `DECISIONS.md` joins the named exceptions in B4 |
| "new `.md` outside allowlist" | CLAUDE.md:191 | `docs/DECISIONS.md` needs the registry add (A4) or 46 gates red the seed |
| "modify deps files (`pyproject.toml`/`requirements.txt`/`package.json`/`uv.lock`/`package-lock.json`)" | CLAUDE.md:180 | HARD STOP — no new deps anywhere in this plan (stdlib helper) |
| "commands are rules, not changelogs" | docs/superpowers/specs/2026-08-30-decision-ledger-v2-design.md:302 | Phase C fragment/source edits stay present-tense rule text |

(Converted from the original prose digest by plan-2's rule-grounding floor; the post-flip review
round restored the three prose constraints the first conversion dropped.)

## Global Constraints (every phase inherits)

- NO-POOL (operator standing directive): all work native/solo; declared in every commit body.
- Governance-sync consciousness: CLAUDE.md, templates/governance/**, commands/_fragments/** are
  trigger surfaces — every sentence correct for all 12 SCAFFOLD_TYPES; know the blast radius before staging.
- Corpus render: `python3 commands/assemble_commands.py --check` first, then the bare render, ONLY
  from /opt/fabrik MAIN checkout.
- The helper is a stdlib CLI: stdout only (XI), env-free config (its one root `/opt` is positional-arg
  overridable for tests), no daemon/PID (VIII), no new deps (II); nothing else in this plan runs as a service —
  the remaining 12-Factor axes are structurally untouched.
- Shared tree: explicit pathspecs · `git diff --cached --numstat` pre-commit · `git reset -q HEAD -- <paths>`
  post-commit · fetch+ff push with the rejection ladder · trailers (`Agent-Role: primary`, `Agent-Name: infra`,
  `Agent-Phase: A|B|C`) as their own paragraph.
- The hub ledger's seed rows state only decisions PROVEN this session (each row's `where` cites a real
  sha/path) — no archaeology.

## Phase A — the helper, its teeth, and the hub ledger

✅ EXECUTED 2026-08-30 (Phase-A commit; CHANGELOG entry moved here from C step 5 by the ERROR-tier same-change law — C now verifies it)

Files: `scripts/decisions.py` (new) · `tests/test_decisions_helper.py` (new) · `docs/DECISIONS.md`
(new, hub) · `scripts/enforcement/_doc_registry.py` (add one DocRow) ·
`templates/scaffold/docs/DECISIONS_TEMPLATE.md` (new — the DocRow's template field is test-enforced
to exist, so it lands here, not in Phase B).

Interfaces — Produces: `decisions.py` CLI `python3 scripts/decisions.py <term> [--root /opt] [--check]`,
output lines `repo · D-NNN · when · who · what · where`; exit 0 always on query, `--check` exits 1 on a
dangling `supersedes D-NNN` pointer (the ONE mechanical row). Registry DocRow for `docs/DECISIONS.md`
(+ its scaffold template file). Consumes: nothing upstream.

1. **Red-first (highest-risk first): write `tests/test_decisions_helper.py` and WATCH IT FAIL** — behaviors:
   (a) Given two tmp repos with ledgers, When queried for a term in one, Then that repo's row prints with
   repo/id/what/where fields; (b) Given a row `supersedes D-004` with no D-004 in that file, When `--check`,
   Then it names the file+id and exits 1; (c) Given the pointer resolves, Then `--check` exits 0;
   (d) Given a repo dir without a ledger, Then it is silently skipped (no stderr noise).
   Gate: `python3 -m pytest tests/test_decisions_helper.py -q` → 4 failed (red), collection clean.
2. Implement `scripts/decisions.py` (~60 lines stdlib: argparse, `Path(root).glob("*/docs/DECISIONS.md")`
   + the hub's own; case-insensitive substring match over data rows; `# AFTER-EDIT: tests/test_decisions_helper.py,
   docs/reference/decision-ledger.md` header). Gate: same pytest → 4 passed.
3. Create hub `docs/DECISIONS.md` per the spec's frozen template (header with append/immutability/query
   rules + rows newest-first): D-000 adoption · D-001 storage-decision (FILE, postgres rejected —
   spec sha) · context7 retirement (74ad8a06) · volume-prune withdrawal + never-offer HARD STOP (025cbb20)
   · cache-prune _npx gate (7862d8a2) · ASK-bar (5f07370a) · 1c APPROACH-FLOOR (21f37809) · interrogative
   floor (730a1af5) · governance-sync post-commit move (2026-08-29) · adoption-forces reference (8760e000).
   Gate: `python3 scripts/decisions.py context7` → prints the hub row; `python3 scripts/decisions.py --check` → exit 0.
4. Add the full **DocRow** to `scripts/enforcement/_doc_registry.py`, mirroring the LESSONS_LEARNT row
   shape (:194 area): `DocRow("docs/DECISIONS.md", "docs/DECISIONS_TEMPLATE.md", frozenset({"universal"}),
   "decision made or received", "agent")` — the `template` field is relative to `templates/scaffold/`
   (:112) and **its existence is enforced by hub-side tests** (:20, `tests/test_doc_registry.py`), so
   **create `templates/scaffold/docs/DECISIONS_TEMPLATE.md` in THIS step** (header + append/immutability/
   query rules + a generic D-000 adoption row — inert until fleet wires the scaffolder map, Phase B6).
   Gate: `python3 -c "import sys; sys.path.insert(0,'scripts/enforcement'); import _doc_registry as r; assert any('DECISIONS' in p for p in r.docs_allowlist())"` → silent;
   `python3 -m pytest tests/test_doc_registry.py -q` → green;
   `python3 scripts/enforcement/check_structure.py` on the hub → no DECISIONS finding.
5. Closing sequence: phase gate green → `python scripts/enforcement/check_doc_sync.py` + INDEX.md row for
   `scripts/decisions.py` + `docs/DECISIONS.md` → **/fabrik-review on Phase A's changed surface, run to its
   coverage-adjudicated exit (BLOCKING)** → commit `-- <the 5 paths>` + trailers (Agent-Phase: A) + push.

## Phase B — distribution (seed-if-missing) + governance duties

✅ EXECUTED 2026-08-30 (deviations recorded: tests/test_governance_template_split.py contract pin extended — adjacent fix outside File Scope, owned by no other plan; operator's mid-phase three-CLAUDE.md catch handled via the `decision-ledger` UNIVERSAL marker + fabrik-lib heads-up mail 01M19GPWBV — the sync-excluded third copy is reached by the drift contract, never by a cross-repo edit; fleet wiring mail 01M19GPW7Q)

Files: `templates/governance/DECISIONS.md` (new — the SEED template: header + one generic D-000
"decision ledger adopted (governance-sync seed)" row) · `scripts/fabrik_synced_manifest.py` ·
`scripts/sync_enforcement_to_projects.py` · `tests/test_sync_seed_if_missing.py` (new) · `CLAUDE.md` ·
`templates/governance/CLAUDE.md`. (The scaffold TEMPLATE file already landed in Phase A step 4,
test-coupled to the DocRow; this phase only mails its wiring — step 6.)

Interfaces — Produces: manifest constant `SEED_IF_MISSING` (dest-relpath set) + pair
(`templates/governance/DECISIONS.md` → `docs/DECISIONS.md`) added to `iter_synced_pairs`'s template leg;
copier behavior: a dest in SEED_IF_MISSING with `destination.exists()` → SKIP, no hash compare, no
overwrite, ever. Consumes: Phase A's registry add (the seeded file must be allowlisted BEFORE any
project receives it — Depends edge: B after A).

1. **Red-first (the phase's highest-risk behavior): `tests/test_sync_seed_if_missing.py`, WATCH IT FAIL** —
   (a) Given a tmp project WITHOUT `docs/DECISIONS.md`, When the sync runs, Then the template seed is
   copied; (b) Given a tmp project WITH a ledger containing a local row, When the sync runs (with and
   without `--force`), Then the file is BYTE-IDENTICAL after — the never-overwrite invariant; (c) Given
   PORTS.md, Then its existing newer-mtime behavior is unchanged (regression guard on the neighbor).
   Gate: `python3 -m pytest tests/test_sync_seed_if_missing.py -q` → red for the right reason.
2. `scripts/fabrik_synced_manifest.py`: add `SEED_IF_MISSING = {"docs/DECISIONS.md"}` beside
   `SEEDED_NOT_ENFORCED` (:137) and add `docs/DECISIONS.md` to `SEEDED_NOT_ENFORCED` too (excluded from
   the unmodified-gate like PORTS.md:316); add the template pair to the GOVERNANCE_TEMPLATES leg (:93).
3. `scripts/sync_enforcement_to_projects.py`: in `_sync_file` (the `destination.exists()` region, :347),
   short-circuit SEED_IF_MISSING dests: exists → `SyncResult("SKIP", …, "seed-if-missing: project-owned")`,
   including under `--force` (--force's own docstring :333 says overwrite — the seed class is the documented
   exception; write it into both docstrings). Gate: the step-1 suite → green; full sync suite if present → green.
4. Hub `CLAUDE.md`: (a) § Behavior gains the write/query duty clause (decision made/received this run →
   its row same-change; ledger-grep before answering where-is/did-we-decide — with `scripts/decisions.py`
   named); (b) Doc Sync Matrix row `| Decision made or received | docs/DECISIONS.md |`; (c) naming
   exception `DECISIONS.md` at :287; (d) the session-recall mandate gains "ledger first: structured
   beats lexical". Gate: `grep -c "DECISIONS.md" CLAUDE.md` ≥ 3; `python scripts/final_gate.py --check --json` stays green.
5. `templates/governance/CLAUDE.md`: the same duties in project-facing wording (write duty · query duty ·
   matrix row · naming exception), correct for all 12 SCAFFOLD_TYPES (type-independent, like CHANGELOG).
   Gate: `grep -c "DECISIONS" templates/governance/CLAUDE.md` ≥ 3.
6. Scaffold wiring hand-off (beat-respecting, grounded — the map at `src/fabrik/scaffold.py:265-278`
   is an ENUMERATED dict, no auto-glob, so the Phase-A template stays inert until wired): send
   `python scripts/mail.py send --to fabrik --to-agent fleet --kind request` citing this plan + the map
   line, asking fleet to add `"docs/DECISIONS_TEMPLATE.md": "docs/DECISIONS.md"` (+ their
   PROJECT_CATALOG note). Do NOT edit scaffold.py here.
   Gate: mail id captured in the commit body.
7. Closing sequence: phase gates green → `check_doc_sync.py` + doc steps (`.env.example` n/a; CHANGELOG in
   Phase C) → **/fabrik-review on Phase B's changed surface to its adjudicated exit (BLOCKING)** — this is
   the enforcement+governance surface: hunt fail-open/fail-closed on the exists()-skip and the --force
   exception hardest → commit `-- <paths>` (Agent-Phase: B) + push (the post-commit governance-sync
   distributes CLAUDE.md + the seed pair fleet-wide — this IS the rollout moment).

## Phase C — corpus wiring, reference doc, docs convergence

✅ EXECUTED 2026-08-30 (CHANGELOG verified — landed in A per the recorded deviation; /fabrik-docs-review converged the 7-doc set with 1 fix: the scaffold template's {{date}} placeholder had no substitution mechanism)

Files: `commands/_fragments/chat-intake.md` · `commands/_fragments/close-feedback.md` ·
`commands/_sources/fabrik-spec.md` · `docs/reference/decision-ledger.md` (new) · CHANGELOG/INDEX/docs-README
rows (governance surfaces, edited directly — monolith shape).

Interfaces — Consumes: Phase A's helper (named in the query-duty texts) + hub ledger (the episodic step
greps it). Produces: nothing downstream.

1. `commands/_fragments/chat-intake.md:29`: `docs/DECISIONS.md` joins the ASK-bar derivation sources
   (before FEATURES.md — decisions outrank features for "did we decide").
2. `commands/_sources/fabrik-spec.md` § Phase 0 episodic-memory step: ledger first — grep
   `docs/DECISIONS.md` + `python3 /opt/fabrik/scripts/decisions.py <term>` BEFORE session-recall
   (structured beats lexical), then session-recall as today.
3. `commands/_fragments/close-feedback.md`: one line added to the before-done block — "did this run make
   or receive a DECISION? → its `docs/DECISIONS.md` row appended same-change, or state `none`" (the
   feedback-duty model; present-tense rule, no changelog prose).
4. Render: `python3 commands/assemble_commands.py --check` → expected DRIFT on exactly the 3 edited
   sources; then the bare render from MAIN → `rendered 32 commands … + 4 agents`.
5. `docs/reference/decision-ledger.md` per the spec's § Documentation landing sites: how to query, how to
   append, the supersede rule, escalation triggers, the one box-topology line (the /opt-wide helper);
   INDEX.md rows (doc + already-added script row check) + `docs/README.md` reference-dir row untouched
   (directory-level index — verified this session) + CHANGELOG entry for the whole plan.
6. Final: `python scripts/enforcement/check_doc_sync.py` → clean; **/fabrik-docs-review over the plan's
   doc set, converged to a truthful no-op** ; `python scripts/final_gate.py --check --json` →
   `"status":"success"` ; `python scripts/enforcement/check_convergence.py` → green (necessary, not
   sufficient — the Evidence section is the proof).
7. Closing sequence: **/fabrik-review on Phase C's changed surface to its adjudicated exit (BLOCKING)** →
   commit `-- <paths>` (Agent-Phase: C) + push.

## Execution Discipline (binding on /fabrik-execute-plan)

- **Review floor** — every phase, before its commit, runs /fabrik-review on its changed surface to a
  coverage-adjudicated exit; no phase merges on a first-pass green.
- **Dispatch policy** — **NO-POOL: operator standing directive supersedes the pool-default for hub
  work; every phase runs native/solo, declared in each commit body** (the flywheel check's sanctioned escape).
- **Parallelism + merge** — none: A→B is a real Depends edge (registry before seed), B→C names the
  helper in corpus text. Three serial phases, one session.

## File Scope (owned paths)

- scripts/decisions.py
- tests/test_decisions_helper.py
- docs/DECISIONS.md
- scripts/enforcement/_doc_registry.py
- templates/governance/DECISIONS.md
- templates/governance/CLAUDE.md
- templates/scaffold/docs/DECISIONS_TEMPLATE.md
- scripts/fabrik_synced_manifest.py
- scripts/sync_enforcement_to_projects.py
- tests/test_sync_seed_if_missing.py
- CLAUDE.md
- commands/_fragments/chat-intake.md
- commands/_fragments/close-feedback.md
- commands/_sources/fabrik-spec.md
- docs/reference/decision-ledger.md

(CHANGELOG.md, INDEX.md, docs/README.md, docs/FEATURES.md, docs/LESSONS_LEARNT.md stay outside the
scope/lock per the shared-append rule; Phase steps name their rows.)

## Coverage Checklist

| Class | Source | Verdict (adjudicated by /fabrik-plan-review over the PLAN) |
|---|---|---|
| security-auth floor (35) | rubric FLOOR | CLEAN — no auth surface planned; helper is read-only stdlib |
| data-postgres floor (25) | rubric FLOOR | CLEAN — no DB anywhere (the spec's own storage decision) |
| ops floor (30) | rubric FLOOR | CLEAN — no deploy/compose surface planned |
| 12-Factor | rubric FLOOR | CLEAN — helper is a stdout-only CLI; § Global Constraints carries the non-negotiables verbatim |
| python discipline (10) | rubric MATCHED | CLEAN — helper/manifest/sync steps cite pack + AFTER-EDIT header planned |
| documentation rules (40) | rubric MATCHED | CLEAN — every Doc Sync Matrix trigger mapped to an owning step (B4-5, C5) |
| testing strategy (45) | rubric MATCHED | CLEAN — red-first mandated at A1 and B1 with watch-it-fail gates written into the steps |
| fail-open vs fail-closed | standing | FIXED(1) — pass 1 moved the template to Phase A so the DocRow's test-enforced template field cannot red A's own gate; the exists()-skip + --force exception is B's hunt focus, named in B7 |
| cost/limit edges | standing | CLEAN — no spend surface in any phase |
| boundary/sentinel/prefix | standing | CLEAN — supersede-pointer regex + SEED_IF_MISSING dest-relpath keying both carry contract rows |
| behavior-without-a-test | standing | CLEAN — 7 G/W/T rows cover every A/B behavior; C is docs/corpus, adjudicated by its phase review |

```
$ python scripts/review_rubric.py --changed scripts/decisions.py scripts/sync_enforcement_to_projects.py scripts/fabrik_synced_manifest.py scripts/enforcement/_doc_registry.py CLAUDE.md templates/governance/CLAUDE.md commands/_sources/fabrik-spec.md commands/_fragments/chat-intake.md commands/_fragments/close-feedback.md docs/reference/decision-ledger.md
# REVIEW RUBRIC — inject into EVERY finder prompt (generated by review_rubric.py)
## FLOOR — always injected, regardless of glob (spec L3)
### core/35-security-auth.md
### core/25-data-postgres.md
### core/30-ops.md
### 12-FACTOR (all twelve axes)
## MATCHED — packs whose globs hit the changed paths
### core/10-python.md  (hit: scripts/decisions.py, scripts/enforcement/_doc_registry.py, scripts/fabrik_synced_manifest.py)
### core/40-documentation.md  (hit: CLAUDE.md, commands/_fragments/chat-intake.md, commands/_fragments/close-feedback.md)
```

## Behavior Contract

- **Given** two repos with ledgers under a root, **When** `decisions.py <term>` matches one row, **Then** that row prints as `repo · id · when · who · what · where` (tests/test_decisions_helper.py)
- **Given** a row citing `supersedes D-004` with no `D-004` row in that file, **When** `decisions.py --check`, **Then** the file+id are named and exit is 1 (tests/test_decisions_helper.py)
- **Given** every supersede pointer resolves, **When** `--check`, **Then** exit 0 (tests/test_decisions_helper.py)
- **Given** a repo without a ledger, **When** queried, **Then** it is skipped silently (tests/test_decisions_helper.py)
- **Given** a project without `docs/DECISIONS.md`, **When** the sync runs, **Then** the template seed is copied (tests/test_sync_seed_if_missing.py)
- **Given** a project WITH a ledger carrying a local row, **When** the sync runs with or without `--force`, **Then** the file is byte-identical after (tests/test_sync_seed_if_missing.py)
- **Given** PORTS.md's existing seed behavior, **When** the suite runs, **Then** it is unchanged (tests/test_sync_seed_if_missing.py)

## Evidence

- Phase A: `scripts/enforcement/_doc_registry.py` read at the :194 area (`DocRow("docs/LESSONS_LEARNT.md",
  "docs/LESSONS_LEARNT_TEMPLATE.md", frozenset({"universal"}), …)` — the row shape to mirror), :112
  (template path relative to `templates/scaffold/`), :20 (template existence enforced by hub-side
  tests — `tests/test_doc_registry.py`); probe run this session:

```
$ python3 -c "import sys; sys.path.insert(0,'scripts/enforcement'); import _doc_registry as r; al=r.docs_allowlist(); print(len(al), [p for p in al if 'DECISIONS' in p.upper()])"
16 []
```

- Phase B: `scripts/fabrik_synced_manifest.py:137` (`SEEDED_NOT_ENFORCED = {"PORTS.md"}`), :93
  (`GOVERNANCE_TEMPLATES = [("templates/governance/CLAUDE.md", "CLAUDE.md")]`), :146 (PORTS pair);
  `scripts/sync_enforcement_to_projects.py:347` (`if not destination.exists():` — the seed branch);
  scaffold wiring grounded:

```
$ grep -rn "FEATURES_TEMPLATE\|RESILIENCE_TEMPLATE" src/fabrik/scaffold.py | head -3
src/fabrik/scaffold.py:270:    "docs/RESILIENCE_TEMPLATE.md": "docs/RESILIENCE.md",
src/fabrik/scaffold.py:274:    "docs/FEATURES_TEMPLATE.md": "docs/FEATURES.md",
$ git log -5 --format='%h %(trailers:key=Agent-Name,valueonly) %s' -- templates/scaffold/ | head -3
e505c20d fleet fix(scaffold): RESILIENCE §3b reframed as three provider-death OUTCOMES
2ec405d4 fleet feat(scaffold): RESILIENCE.md template mandates provider-death resilience (§3b)
```

- Phase C: `commands/_fragments/chat-intake.md:29` (the ASK-bar derivation-sources line, read);
  `commands/_fragments/close-feedback.md` tail read (the before-done block); `templates/scaffold/docs/`
  listing confirms the `*_TEMPLATE.md` convention; docs/README.md indexes `reference/` at directory
  level (verified this session — no per-file row owed).

## Self-audit

- (a) Coverage: every "What we already agreed" item maps — storage/rows/seed → A3+B; write/query duties →
  B4-5 + C1-3; mechanical row → A1-2; distribution → B2-3+B6; reference doc + naming + matrix → B4 + C5;
  no gaps found.
- (b) Cross-phase signatures: `SEED_IF_MISSING` (B2) is consumed only by B3's copier edit; `decisions.py`'s
  CLI shape (A) is quoted verbatim in B4/C2's governance text — one name, checked.
- Grounding passes: registry probe (16, no DECISIONS) · manifest/copier lines read · scaffold map lines
  read · fragment line numbers read · fabrik-lib no-fit re-confirmed via the spec's verdict table.
- Not yet a fixed point: /fabrik-plan-review owes the independent convergence.

## Review Pass Ledger (/fabrik-plan-review, solo native — NO-POOL)

| Pass | scope | method | raised | edits | plan md5 |
|---|---|---|---:|---:|---|
| Pass 1 | full read + the 7 dispatched seams (registry DocRow shape/:20/:112 · copier :347/:354 · never-overwrite test · scaffold map enumerated-not-glob · corpus wiring lines · File Scope exclusion · read budget) | citation | 2 | 2 | 7d31a9e6 → … |
| Pass 2 | scoped: the template-move cascade + budget number, cross-refs | citation | 0 | 0 | … |
| Pass 3 | closing full sweep — every count re-derived (intake 5, behavior 7, 3 phase-review steps, budget 170198 re-measured, governance-file absence grepped 0) | method: re-derivation | 0 | 0 | 8e787ecd |
| Pass 4 | gate: check_convergence at the flip demanded VERDICT cells in the Coverage Checklist (had "planned adjudication" prose) — rows re-stamped with the review's actual CLEAN/FIXED verdicts | gate | 1 | 1 | → 39e7c040 |
| Pass 5 | confirm: gate re-run → 0 findings for this plan; md5 39e7c040 stable | method: re-derivation | 0 | 0 | 39e7c040 stable → CONVERGED |
| Pass 6 (round 2, post-flip) | operator-prompted re-review of the dogfood delta: the quote-table conversion DROPPED 3 prose constraints (allowlist · no-new-deps · commands-are-rules) — restored as quote rows | citation | 1 | 1 | 7c11f4e3 → … |
| Pass 7 (round 2 closing) | check_rule_grounding re-run (1 examined / 0 findings) + 3 quotes spot-grepped verbatim myself + 9 digest rows counted + check_convergence 0 | method: re-derivation | 0 | 0 | 236faeee → re-CONVERGED |

## Residual unknowns

- Resolved: allowlist gap (I3, probe above) · seed semantics (I4, exists()-skip) · scaffold beat split
  (I2, template-in-repo + wiring-by-mail).
- Open, non-blocking: fleet's timing on the scaffolder wiring line — resolution: the B6 mail (ack
  required); new repos meanwhile get ledgers on their first governance-sync (the B pair covers them).
- Open, non-blocking: adoption rate post-rollout — resolution: the spec's 2-week kaizen measurement
  (spec § Enforcement); not this plan's gate.
