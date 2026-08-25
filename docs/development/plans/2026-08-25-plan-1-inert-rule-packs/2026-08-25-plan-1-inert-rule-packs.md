# Plan: rule packs that cannot reach the code they bind

Status: IN-PROGRESS

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
| T01 | D7 requires one live request | — | ⚡ | 🟡 | |
| T02 | corpus glob audit across all 12 scaffold types | T04 | ⛓️ | 🟡 | |
| T03 | applies_to frontmatter + the non-circular check | T02 | ⛓️ | 🟡 | |
| T04 | one shared path→pack matcher | — | ⚡ | 🟡 | |
| T99 | integration | T01, T03, T04 | ⛓️ | ⬜ | |

## Merge Order

1. T01
2. T04
3. T02
4. T03
5. T99

T04 merges BEFORE T02: T02's Scope consumes T04's matcher, so the original order (T02 then T04) had
the consumer landing first — its Gate could not have passed.

## Interfaces

- **T02 Produces** `scripts/enforcement/pack_layout_audit.py::audit_layout(root, types) -> list[Finding]`
  — the corpus×type matrix. **T03 Consumes** it as the check's engine, so the audit and the standing
  check share one implementation rather than two that can disagree.
- **T04 Produces** THREE symbols in `scripts/rules_match.py` —
  `pack_matches_path(path, glob, *, empty_matches_all) -> bool` (single path, from
  `review_rubric.py:183`), `any_path_matches(root, glob, *, empty_matches_all) -> bool` (root scan,
  from `select_rules.py:123`), and `packs_for_paths(paths, root) -> list[str]`.
  **T02, T03 and `select_rules.py` Consume** them. The two matchers are NOT interchangeable — one
  takes a path, the other a tree — and they disagree deliberately on the empty pattern
  (`review_rubric.py:194` returns True, `select_rules.py:131` returns False), which is why
  `empty_matches_all` is an explicit keyword rather than a collapsed default.

## Global Constraints

- **Everything here is FLEET-SYNCED.** `.windsurf/rules/**` and `scripts/enforcement/**` both sit in
  the governance-sync trigger filter (`.pre-commit-config.yaml`), so every commit distributes to ~46
  repos. A pack edit must be correct for ALL of them, never tuned to one project.
- **No third path matcher.** `review_rubric.py:183 _glob_matches_path` and
  `select_rules.py:123 _glob_has_match` already do this twice. T04 collapses them into
  `rules_match.py`; nothing in this plan may add a third. ⚠️ `select_rules.py:47 _GLOBS` is NOT one
  of them — it is the frontmatter regex (`^globs:\s*\[(.*?)\]`), a different concern, and this plan's
  first draft named it as the second matcher. It is out of scope; do not touch it.
- **`applies_to:` lives in pack frontmatter.** DECIDED here, not deferred into execution:
  `applies_to: [<scaffold type>, …]` sits beside the `globs:` it cross-checks. A central
  `scaffold-type → packs` registry was the alternative and was rejected — a registry drifts from the
  pack silently, which is the same failure mode this plan exists to close. The cost is a new key in a
  fleet-synced frontmatter across up to 56 packs; it lands incrementally, and T02 seeds the two packs
  it corrects so T03's check is not vacuous on landing.
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
- **Given** the D7 section with its live-request clause deleted, **When** the prose-pin test runs, **Then** it fails — proving the pin observes the clause rather than the file's existence (tests/test_execute_plan_d7.py:1).
- **Given** a ticket's declared file list, **When** plan-stage pack routing runs, **Then** it returns the rubric's MATCHED set UNION any FLOOR pack whose glob fired — NOT plain equality with MATCHED, which suppresses floor packs it has already emitted (scripts/rules_match.py:1).
- **Given** a wildcard-only glob and the two callers' opposite conventions, **When** the shared matcher runs, **Then** `empty_matches_all=True` matches and `empty_matches_all=False` does not, preserving both call sites unchanged (scripts/review_rubric.py:194).
- **Given** the 56-pack corpus and the 12 scaffold types, **When** the layout audit runs, **Then** it emits one row per (pack, type) pair the pack's `applies_to` claims and matches zero emitted paths (scripts/enforcement/pack_layout_audit.py:1).
- **Given** the two known-inert glob-activated packs, **When** their globs are corrected and their `applies_to` seeded, **Then** each matches at least one real file in a scaffolded project of its declared type (.windsurf/rules/core/75-workers-jobs.md:3).
- **Given** a pack whose frontmatter says `activation: manual`, **When** the layout audit runs, **Then** it is excluded from the report entirely rather than counted as inert (.windsurf/rules/saas/00-domain-saas.md:6).
- **Given** a pack whose `applies_to` names a scaffold type it cannot match, **When** the check runs, **Then** it reports that pack and does NOT derive applicability from the globs under test (scripts/enforcement/check_pack_reachability.py:1).
- **Given** a pack with no `applies_to` field, **When** the check runs, **Then** it passes silently rather than failing, so the field can land incrementally across 56 packs (scripts/enforcement/check_pack_reachability.py:1).
- **Given** the corpus as it stands after T02, **When** the check runs, **Then** it reports the count of packs it actually examined, so a corpus where nobody declares `applies_to` reads as "0 examined" rather than as a pass (scripts/enforcement/check_pack_reachability.py:1).
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
| fail-open vs fail-closed on every gate/guard | FIXED | the new check lands ADVISORY via `run_optional_check(..., warn_only=True)` (scripts/final_gate.py:221-248), named concretely in T03 rather than left as "wire it in"; promotion to blocking is a named operator decision |
| check that cannot ask its question (fail-silent-green) | FIXED | round 2: T03 added `applies_to` that NO pack declared, and its own row 2 made an undeclared pack pass silently — the check would have shipped asking nothing. T02 now seeds the field on the two packs it corrects, and T03 row 3 makes the examined-count visible |
| cost/quota/limit accounting edges | CLEAN | no metered call, no LLM dispatch, no quota surface in any ticket |
| boundary/sentinel/prefix collisions | FIXED | round 1: `activation: manual` was the missing sentinel. Round 2: the empty-pattern branch — `review_rubric.py:194` returns True where `select_rules.py:131` returns False, a deliberate divergence T04's "pure move" would have collapsed across ~46 repos; now an explicit `empty_matches_all` keyword |
| behavior-without-a-test | FIXED | round 2: T02's Gate ran a test file T03 creates (proven `exit 4` today) and T01's Gate could not observe its own row. T02 now owns tests/enforcement/test_pack_layout_audit.py, T01 owns tests/test_execute_plan_d7.py, T03 tests/enforcement/test_pack_reachability.py, T04 tests/test_rules_match.py |
| read-set completeness (cold coder reads Scope + Touches + Context Files ONLY) | FIXED | round 2: T02 cited `saas/00-domain-saas.md` and the 12-type registry in its rows with neither in Context Files; T03's format decision had its criteria only in the spine's Residuals. All three now reachable from the tickets themselves |
| Merge Order vs Interfaces direction | FIXED | round 2: T02 consumed T04's matcher while merging BEFORE it. T04 now merges second, T02 third |

## Context Ledger

**Rule packs (ACTIVE, binding on how this is written)** — `python scripts/select_rules.py`:
`core/10-python.md` (the checks are Python), `core/45-testing-strategy.md` (red-first per behavior),
`core/40-documentation.md` (the Doc Sync Matrix), `core/62-using-subagents.md` (dispatch policy).

**Ground truth read this session:**

- `scripts/select_rules.py:148-158` — the ACTIVE/AVAILABLE split, and the circularity.
- `scripts/select_rules.py:123` — `_glob_has_match`, the root-scan matcher (and `:130-131`, its
  empty-pattern `return False`).
- `scripts/select_rules.py:47` — `_GLOBS`, the frontmatter regex — NOT a matcher, and out of scope.
- `scripts/review_rubric.py:183` — `_glob_matches_path`, the single-path matcher (and `:191-194`, its
  empty-pattern `return True`, whose own comment calls the divergence deliberate).
- `scripts/final_gate.py:221-248` — `run_optional_check`, and `warn_only=True`'s contract.
- `scripts/enforcement/check_command_corpus.py:24-45` — the five facts it proves, none of which can
  observe D7's prose.
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
- tests/enforcement/test_pack_layout_audit.py
- tests/test_rules_match.py
- tests/test_execute_plan_d7.py
- docs/reference/rule-pack-reachability.md
- docs/development/plans/2026-08-25-plan-1-inert-rule-packs/

## Execution Discipline (binding on /fabrik-execute-plan)

- **Review floor** — every ticket, on the coder's return, runs `/fabrik-review` on its changed surface
  to a coverage-adjudicated exit BEFORE its merge; no ticket merges on a first-pass green.
- **Dispatch policy** — pool-default (`fanout("review", …)`, auto-records to the flywheel, wants the
  `set_quality` back-fill) for the gradeable fan-out, native Opus ADDED on top for the
  authoritative/high-risk pass — here, T03's check semantics and every `.windsurf/rules/**` edit,
  because those distribute to ~46 repos. Never pool-only, never Opus-only.
- **Parallelism + merge** — T01 and T04 fan out concurrently (disjoint Touches). T02 serializes behind
  T04 (consumes its matcher), T03 behind T02 (consumes its audit engine). T99 merges last. Results
  merge in Merge Order.
- **Ticket breadth (adjudicated, `check_ticket_breadth.py --plan-dir`)** — T02 and T03 both score 5
  (T02) and 6 (T03) and both are KEPT WHOLE, with reasons. **T02**: the suggested peel is `scripts/`
  from `.windsurf/`, but the audit and the two corrected globs prove each other — the audit's verdict
  on those packs flipping from inert to reachable IS the glob fix's only evidence, so a split would
  spread one invariant across two tickets. **T03**: two peels are suggested and both are refused —
  `docs/reference/rule-pack-reachability.md` is the check's Doc Sync Matrix receipt and must land in
  the same change as the check, and peeling the `final_gate.py` wiring would separate the check from
  its only production consumer, which is precisely the stored-and-never-read defect the wired-consumer
  rule exists to stop. The tool's own footer measures precision at 0.50 (n=14) — it is a screen, and
  this is the LOOK it asked for.

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

Measured consequence — every zero-matching pack lands in AVAILABLE, never ACTIVE, so
"ACTIVE ∧ matches-zero" is empty by construction. The probe below makes the point sharper than the
original framing did: the two genuinely-broken packs and the one that is correctly manual are
**indistinguishable** in this output. A check reading this split cannot tell a defect from a design
choice, which is exactly why the expectation must be declared independently:

```
$ cd /opt/transdoc && python scripts/select_rules.py | grep -A40 '^AVAILABLE' | grep -E '75-workers|app-audit|00-domain-saas'
  • core/75-workers-jobs.md — Workers & jobs discipline — PG queue, retry/backoff, dead-l
  • core/app-audit-log.md — Tamper-evident audit log for sensitive operations — canonical
  • saas/00-domain-saas.md — SaaS domain — PLANNING layer. Vision-intake dimensions (ICP,
```

**Phase T04** — two independent path matchers exist today, with THREE call sites between them
(round 1 cited `_GLOBS` here, which is the frontmatter regex, not a matcher — corrected):

```
$ grep -n "_glob_matches_path\|_glob_has_match" scripts/select_rules.py scripts/review_rubric.py
scripts/select_rules.py:123:def _glob_has_match(root: Path, glob: str) -> bool:
scripts/select_rules.py:156:            if any(_glob_has_match(root, g) for g in globs):
scripts/select_rules.py:177:            {"pack": e["pack"], "globs_fired": [g for g in e["globs"] if _glob_has_match(root, g)]}
scripts/review_rubric.py:183:def _glob_matches_path(changed: str, glob: str) -> bool:
scripts/review_rubric.py:241:        hits = [c for c in changed if any(_glob_matches_path(c, g) for g in globs)]
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
exact name. T04 produces `pack_matches_path` / `any_path_matches` / `packs_for_paths`; T02, T03 and
`select_rules.py` consume those exact names, and T04 merges before both consumers. Checked by name
AND by merge position, not by intent.

**What was verified vs assumed** — VERIFIED by execution: the circularity, the two inert packs, the
two matchers and their divergence, D7's text and its gate's actual five checks, the 12-type registry,
`run_optional_check`'s `warn_only` contract, and that T02's original Gate exits 4 today. Nothing
material is carried as an assumption: the `applies_to` format is now a DECISION recorded in Global
Constraints, not an open question.

**Convergence receipt** — the combined-set md5 is recorded in the review report's Pass Ledger, not in
this file. Writing the hash into the plan changes the plan, so an in-file hash can never equal the
state it claims to certify: the round-1 receipt recorded `9305b792…` and no reachable state of this
set reproduces it (the committed set hashed `9d7501a1…`, the spine alone `d5a180a1…`). Reproduce the
current hash with
`find <plan-dir> -name '*.md' -print0 | sort -z | xargs -0 md5sum | md5sum`.

**Round 1** found three defects. The material one: `saas/00-domain-saas.md` is `activation: manual`
with an explicit *"NOT glob-activated ON PURPOSE … Do not re-add one"* (`:6-11`) — it matches zero
source files BY DESIGN, the first draft called it inert, and T02 would have added a glob the pack
forbids. Removed; the audit now filters on `activation: glob` first, which is why "30 zero-match" was
inflated by four correctly-manual `00-domain-*` packs. transdoc's two findings stand unchanged.

**Round 2 — a second, independently-armed review found TWELVE more defects in the set round 1 had
declared converged.** The dominant class was seams between tickets, invisible to a per-ticket read:

1. **T02's Gate ran a test file T02 does not own**, created by T03, which merges after it — proven
   `exit 4` today. T02 now owns `tests/enforcement/test_pack_layout_audit.py`.
2. **T02 consumed T04's matcher while merging BEFORE T04.** Merge Order corrected.
3. **T04's "pure move, byte-identical" was false.** `_glob_matches_path` takes a path,
   `_glob_has_match` takes a tree, and they disagree deliberately on the empty pattern — collapsing
   them would have silently changed the ACTIVE/AVAILABLE split in ~46 repos.
4. **The "no third glob parser" constraint named the wrong file.** `select_rules.py:47 _GLOBS` is the
   frontmatter regex, not a matcher; the real second matcher is `select_rules.py:123`. A coder
   obeying the DO-NOT literally would have deleted the frontmatter parser.
5. **T03's check would have shipped asking nothing** — it added `applies_to` that no pack declared,
   and its own contract made an undeclared pack pass silently. Exactly the fail-silent-green class
   this plan exists to close, authored INTO the plan that closes it.
6. **T01's Gate could not observe its own Behavior row** — `check_command_corpus.py` proves five
   mechanical facts and none of them reads D7's prose. A prose-pin test now does.
7–12. Read-set gaps (T02 cited two files absent from its Context Files; T03's decision criteria lived
   only in the spine), the deferred format decision, the unspecified `final_gate` hook, and the
   unrun-until-now `check_ticket_breadth` advisory — now adjudicated in Execution Discipline.

**Method note carried into execution:** across both rounds, six of my own probes were wrong before the
artifact was — line-anchored greps over wrapped markdown, an off-by-one `sed`, and a hash that could
not be reproduced. Verify the probe before believing its verdict.

## Residual unknowns

**RESOLVED**

- *Spec, plan or direct implementation?* — plan. No external unknowns (rules out a spec); the check
  needs an artifact that does not exist (rules out direct implementation).
- *Is transdoc's proposed check usable as filed?* — no, it is circular; proven at `select_rules.py:156`.
  Reported back to them rather than silently redesigned.
- *Sequence by effort or by class-coverage?* — coverage. D7 is first because it is the only item that
  catches the class regardless of which of the six verification layers fails.

- *Where `applies_to` lives* — **per-pack frontmatter**, decided at round 2 and recorded in Global
  Constraints. A central `scaffold-type → packs` registry was the alternative; rejected because a
  registry drifts from the pack silently, which is the failure this plan exists to close. Round 1
  carried this as "T03 step 1 decides it in writing" — a deferred question wearing a resolution
  step's clothes: the ticket named no criteria and no default, so the executor would have stalled or
  guessed. Deciding it here IS the fix.

**STILL OPEN — each with its resolution step**

1. **Whether the audit needs a real scaffold per type** — the honest denominator is "paths the
   scaffolder actually emits", which may require scaffolding each of the 12 types to a temp dir rather
   than reading templates. **Resolution: T02 step 2 runs `fabrik scaffold --type <t>` into a
   throwaway dir for ONE type and compares against the template-derived list; if they diverge, the
   scaffold path is the denominator.** Self-service, no operator input needed.
2. **Promotion of the new check from WARN to blocking** — deliberately out of scope. **Resolution:
   operator decision after the corpus is clean; recorded in `docs/reference/rule-pack-reachability.md`
   as the explicit next gate.**
