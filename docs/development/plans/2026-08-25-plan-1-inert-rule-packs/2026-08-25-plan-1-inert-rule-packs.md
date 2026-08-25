# Plan: rule packs that cannot reach the code they bind

Status: CONVERGED

**Origin:** transdoc `01M0WN9RXJJY9SDQTF8183GTYW` + follow-up `01M0WNVKDMYG0G2NTPZTG38XG4`
(proposal: `/opt/transdoc/docs/reference/upstream-proposals/2026-08-25-rule-packs-that-cannot-reach-the-code-they-bind.md`).

**The class, in one sentence:** rule-pack `globs:` were written for a *directory-per-concern* layout
(`workers/`, `jobs/`, `auth/`, `api/`) while the fabrik scaffolds emit a *file-per-concern* layout
(`worker.py`, `billing_routes.py`, `lib/api.ts`), so a pack can be silently inert in every project it
governs — and nothing detects it.

**Measured, not asserted** (this session, 56 packs vs `/opt/transdoc`'s real 4387-file tree):
30 packs match zero files. **Adjudicated at review**: most are correctly irrelevant here
(mobile/desktop/chrome-ext/`ai/*` in a SaaS project), and **four are `activation: manual` and
correctly match nothing by design** — the audit's first cut did not read the `activation:` field at
all. **Two are genuinely inert**:

| pack | why it should have matched |
|---|---|
| `core/75-workers-jobs.md` | the project's entire job queue is `server/src/transdoc/worker.py`; globs have no `**/worker*` |
| `core/app-audit-log.md` | globs are `**/auth/login*`, `**/billing/**/webhook*`; the project has `billing_routes.py` + a vendored `router.py`, both file-shaped |

**What it cost transdoc:** 19 frontend calls to routes that do not exist, 14 built endpoints with no
caller, an empty beat-loop body, `enqueue_system_jobs` called only by tests, retention purge never
run — while `final_gate` was green and 296 tests passed.

**ALREADY LANDED — do not re-plan:** `29194562` added client globs to `core/15-api-contracts.md`
(reproduced before, verified after, blast radius measured at exactly one file across `/opt`).

## Ticket Board

| Ticket | Title | Depends | Parallel | State | Commit |
|---|---|---|---|---|---|
| T01 | D7 requires one live request | — | ⚡ | ⬜ | |
| T02 | corpus glob audit across all 12 scaffold types | — | ⚡ | ⬜ | |
| T03 | applies_to frontmatter + the non-circular check | T02 | ⛓️ | ⬜ | |
| T04 | one shared path→pack matcher | — | ⚡ | ⬜ | |
| T99 | integration | T01, T03, T04 | ⛓️ | ⬜ | |

## Merge Order

1. T01
2. T02
3. T04
4. T03
5. T99

## Interfaces

- **T02 Produces** `scripts/enforcement/pack_layout_audit.py::audit_layout(root, types) -> list[Finding]`
  — the corpus×type matrix. **T03 Consumes** it as the check's engine, so the audit and the standing
  check share one implementation rather than two that can disagree.
- **T04 Produces** `scripts/rules_match.py::pack_matches_path(path, glob) -> bool` and
  `packs_for_paths(paths, root) -> list[str]`. **T02, T03 and `select_rules.py` Consume** them.
  No component re-implements glob matching.

## Global Constraints

- **Everything here is FLEET-SYNCED.** `.windsurf/rules/**` and `scripts/enforcement/**` both sit in
  the governance-sync trigger filter (`.pre-commit-config.yaml`), so every commit distributes to ~46
  repos. A pack edit must be correct for ALL of them, never tuned to one project.
- **No third glob parser.** `review_rubric.py:183 _glob_matches_path` and `select_rules.py:47 _GLOBS`
  already do this twice. T04 collapses them; nothing in this plan may add a third.
- **The new check is ADVISORY (WARN) on landing.** A blocking check that fires on 56 packs across 46
  repos on day one is how a gate gets ignored. Promotion to blocking is a separate operator decision
  once the corpus is clean.
- **Do not widen a glob to make a pack match.** A pack matching a file it does not govern is worse
  than one matching nothing — it trains agents to ignore the rubric.
- **⚠️ `activation: manual` packs are OUT OF SCOPE — never give one a glob.** All four `00-domain-*`
  packs are deliberately manual; `saas/00-domain-saas.md:6-11` carries an explicit *"NOT glob-activated
  ON PURPOSE … Do not re-add one"* with its reasoning (a `**/billing/**` glob would inject 187 lines of
  vision-intake questions into every billing edit). **This plan's own first draft listed that pack as
  inert and would have violated its warning** — caught at review, and the reason the audit MUST filter
  on `activation: glob` before reporting anything.

## Behavior Contract

- **Given** a plan whose tickets ship HTTP surface, **When** D7 validation runs, **Then** it refuses to reach a terminal state without at least one live request/response pasted into `## Evidence` (commands/_sources/fabrik-execute-plan.md:520).
- **Given** the 56-pack corpus and the 12 scaffold types, **When** the layout audit runs, **Then** it emits one row per (pack, type) pair where the pack declares applicability and matches zero emitted paths (scripts/enforcement/pack_layout_audit.py:1).
- **Given** the two known-inert glob-activated packs, **When** their globs are corrected, **Then** each matches at least one real file in a scaffolded project of its declared type (.windsurf/rules/core/75-workers-jobs.md:3).
- **Given** a pack whose frontmatter says `activation: manual`, **When** the layout audit runs, **Then** it is excluded from the report entirely rather than counted as inert (.windsurf/rules/saas/00-domain-saas.md:6).
- **Given** a pack whose `applies_to` names a scaffold type it cannot match, **When** the check runs, **Then** it reports that pack and does NOT derive applicability from the globs under test (scripts/enforcement/check_pack_reachability.py:1).
- **Given** a pack with no `applies_to` field, **When** the check runs, **Then** it passes silently rather than failing, so the field can land incrementally across 56 packs (scripts/enforcement/check_pack_reachability.py:1).
- **Given** a ticket's declared file list, **When** plan-stage pack routing runs, **Then** it returns the same pack set `review_rubric.py --changed` returns for those paths (scripts/rules_match.py:1).
- **Given** the merged plan, **When** the whole-plan receipts run, **Then** the audit, the check and the matcher all report the same pack set for the same inputs (docs/reference/rule-pack-reachability.md:1).

## Coverage Checklist

Classes derived from `python scripts/review_rubric.py --changed <the File Scope paths>` (FLOOR +
MATCHED) plus the four standing recurrence classes. Every row adjudicated before the CONVERGED flip.

| Class | Verdict | Evidence |
|---|---|---|
| core/10-python.md (FLOOR, matched: the three new checks) | CLEAN | all three are stdlib-only Python reusing existing helpers; no new deps (scripts/review_rubric.py:168) |
| core/40-documentation.md (matched: the pack + command edits) | FIXED | T99 owns the whole-plan doc receipt; docs/reference/rule-pack-reachability.md is in File Scope |
| core/25-data-postgres.md (FLOOR) | REFUTED | no DB surface anywhere in this plan — checks read files, never a database |
| core/35-security-auth.md (FLOOR) | REFUTED | no auth/secret surface; the checks read `.windsurf/rules/**` and `scripts/**` only |
| core/30-ops.md (FLOOR) | REFUTED | no container/deploy surface; nothing here reaches a VPS |
| 12-FACTOR (all twelve axes) | CLEAN | no config/backing-service/process change; the checks are stateless CLI reads |
| fail-open vs fail-closed on every gate/guard | FIXED | the new check lands ADVISORY (WARN) by explicit Global Constraint — 56 packs × 46 repos failing on day one is how a gate gets ignored; promotion to blocking is a named operator decision |
| cost/quota/limit accounting edges | CLEAN | no metered call, no LLM dispatch, no quota surface in any ticket |
| boundary/sentinel/prefix collisions | FIXED | THE defect of this plan — `activation: manual` was the missing sentinel; the audit now filters on it first (.windsurf/rules/saas/00-domain-saas.md:6) |
| behavior-without-a-test | FIXED | every ticket carries a runnable `Gate:`; T02/T03 gate on tests/enforcement/test_pack_reachability.py, T04 on tests/test_rules_match.py |

## Context Ledger

**Rule packs (ACTIVE, binding on how this is written)** — `python scripts/select_rules.py`:
`core/10-python.md` (the checks are Python), `core/45-testing-strategy.md` (red-first per behavior),
`core/40-documentation.md` (the Doc Sync Matrix), `core/62-using-subagents.md` (dispatch policy).

**Ground truth read this session:**

- `scripts/select_rules.py:148-158` — the ACTIVE/AVAILABLE split, and the circularity.
- `scripts/select_rules.py:47` — `_GLOBS`, the second independent frontmatter parser.
- `scripts/review_rubric.py:183` — `_glob_matches_path`, the first matcher.
- `scripts/review_rubric.py:168` — `_packs()`, the corpus loader reused by the audit.
- `commands/_sources/fabrik-execute-plan.md:520` — D7, "Final validation + terminal states".
- `src/fabrik/scaffold.py:138` — `SCAFFOLD_TYPES`, the 12-type registry (ground enumerations here, never from memory).
- `.windsurf/rules/core/15-api-contracts.md:3` — the frontmatter shape all packs share.

**Hub invariant:** `CLAUDE.md` § HARD STOPS — a synced-surface edit is a fleet-wide change; ground
enumerations from the live registry.

## File Scope (owned paths)

- scripts/rules_match.py
- scripts/enforcement/pack_layout_audit.py
- scripts/enforcement/check_pack_reachability.py
- scripts/select_rules.py
- scripts/review_rubric.py
- scripts/final_gate.py
- commands/_sources/fabrik-execute-plan.md
- .windsurf/rules/core/75-workers-jobs.md
- .windsurf/rules/core/app-audit-log.md
- tests/enforcement/test_pack_reachability.py
- tests/test_rules_match.py
- docs/reference/rule-pack-reachability.md
- docs/development/plans/2026-08-25-plan-1-inert-rule-packs/

## Execution Discipline (binding on /fabrik-execute-plan)

- **Review floor** — every ticket, on the coder's return, runs `/fabrik-review` on its changed surface
  to a coverage-adjudicated exit BEFORE its merge; no ticket merges on a first-pass green.
- **Dispatch policy** — pool-default (`fanout("review", …)`, auto-records to the flywheel, wants the
  `set_quality` back-fill) for the gradeable fan-out, native Opus ADDED on top for the
  authoritative/high-risk pass — here, T03's check semantics and every `.windsurf/rules/**` edit,
  because those distribute to ~46 repos. Never pool-only, never Opus-only.
- **Parallelism + merge** — T01, T02, T04 fan out concurrently (disjoint Touches). T03 serializes
  behind T02 (consumes its audit engine). T99 merges last. Results merge in Merge Order.

## Evidence

**Phase T01** — `commands/_sources/fabrik-execute-plan.md:520` is D7 "Final validation + terminal
states"; its body mandates "a full run of every ticket's Behavior-Contract tests and every seam test"
and never a live request.

**Phase T02/T03** — the circularity, read at `scripts/select_rules.py:156`:

```
            if any(_glob_has_match(root, g) for g in globs):
                active.append(entry)
            else:
                available.append(entry)
```

Measured consequence — all three inert packs land in AVAILABLE, never ACTIVE, so
"ACTIVE ∧ matches-zero" is empty by construction:

```
$ cd /opt/transdoc && python scripts/select_rules.py | grep -A40 '^AVAILABLE' | grep -E '75-workers|app-audit|00-domain-saas'
  • core/75-workers-jobs.md — Workers & jobs discipline — PG queue, retry/backoff, dead-l
  • core/app-audit-log.md — Tamper-evident audit log for sensitive operations — canonical
  • saas/00-domain-saas.md — SaaS domain — PLANNING layer. Vision-intake dimensions (ICP,
```

**Phase T04** — two independent parsers exist today:

```
$ grep -n "_GLOBS\|_glob_matches_path" scripts/select_rules.py scripts/review_rubric.py
scripts/select_rules.py:47:_GLOBS = re.compile(r"^globs:\s*\[(.*?)\]", re.MULTILINE | re.DOTALL)
scripts/review_rubric.py:183:def _glob_matches_path(changed: str, glob: str) -> bool:
```

**Phase T99** — the corpus audit harness, run this session against a real tree:

```
packs in corpus: 56
files in /opt/transdoc: 4387
MATCH >=1 file : 26
MATCH ZERO     : 30
```

## Self-audit

**Coverage** — walking "what we already agreed": D7 live request → T01. Corpus audit across all 12
types → T02. `applies_to` + non-circular check → T03. Shared matcher (transdoc items 3+4 collapsed) →
T04. Already-landed `15-api-contracts` glob fix → explicitly excluded above. Withdrawn `final_gate`
proposals → excluded in T01's DO-NOT. No gap found.

**Cross-phase signature consistency** — T02 produces `audit_layout(root, types)`; T03 consumes that
exact name. T04 produces `pack_matches_path` / `packs_for_paths`; T02, T03 and `select_rules.py`
consume those exact names. Checked by name, not by intent.

**What was verified vs assumed** — VERIFIED by execution: the circularity, the three inert packs, the
two parsers, D7's text, the 12-type registry. ASSUMED and carried as a decision, not a fact: that
`applies_to` belongs in pack frontmatter rather than a central registry (see Residual unknowns).

**CONVERGED** — `/fabrik-plan-review`, 2 rounds, edit-free round md5-verified
(`9305b79235f7a5bd8d69c262ff387dda` before == after over the combined set).

**Round 1 found three defects, one of them mine and material:**

1. **REFUTED my own headline finding.** `saas/00-domain-saas.md` is `activation: manual` and carries
   an explicit *"NOT glob-activated ON PURPOSE … Do not re-add one"* (`:6-11`). It matches zero source
   files BY DESIGN. The first draft listed it as inert and T02 would have added a glob the pack
   forbids. Removed; the audit now filters on `activation: glob` first — a filter the original harness
   never applied, which is why "30 zero-match" was inflated by four correctly-manual `00-domain-*`
   packs. transdoc's two findings stand unchanged.
2. **Unnamed produced symbols.** The spine's Interfaces named `pack_matches_path` / `packs_for_paths`
   but T04 never mentioned them, so a dispatched coder would have invented names. Both tickets now
   name them explicitly.
3. **Signature/deferral seams clean** — READ budget 0 findings across all five tickets, zero
   `[OPEN → resolve at Phase N]` landmines, and Residual #1 verified as a real in-ticket decision gate
   at `T03:14`, not a disguised deferral.

**Four of my own probes were wrong before the artifact was** — a `grep -c` on a line-wrapped phrase,
an off-by-one `sed` line, and two earlier in the audit. Each was corrected against the file rather
than believed. The pattern is worth carrying into execution: a line-anchored probe over wrapped
markdown is a false negative generator.

## Residual unknowns

**RESOLVED**

- *Spec, plan or direct implementation?* — plan. No external unknowns (rules out a spec); the check
  needs an artifact that does not exist (rules out direct implementation).
- *Is transdoc's proposed check usable as filed?* — no, it is circular; proven at `select_rules.py:156`.
  Reported back to them rather than silently redesigned.
- *Sequence by effort or by class-coverage?* — coverage. D7 is first because it is the only item that
  catches the class regardless of which of the six verification layers fails.

**STILL OPEN — each with its resolution step**

1. **Where `applies_to` lives** — per-pack frontmatter (this plan's inclination) vs a central
   `scaffold-type → packs` registry. Frontmatter keeps the declaration beside the globs it
   cross-checks; a registry avoids touching 56 synced files. **Resolution: T03 step 1 decides it in
   writing, with the format's blast radius stated, BEFORE any pack is edited.** Not deferred into
   execution — T03 cannot start its edits until the decision line exists in the ticket.
2. **Whether the audit needs a real scaffold per type** — the honest denominator is "paths the
   scaffolder actually emits", which may require scaffolding each of the 12 types to a temp dir rather
   than reading templates. **Resolution: T02 step 2 runs `fabrik scaffold --type <t>` into a
   throwaway dir for ONE type and compares against the template-derived list; if they diverge, the
   scaffold path is the denominator.** Self-service, no operator input needed.
3. **Promotion of the new check from WARN to blocking** — deliberately out of scope. **Resolution:
   operator decision after the corpus is clean; recorded in `docs/reference/rule-pack-reachability.md`
   as the explicit next gate.**
