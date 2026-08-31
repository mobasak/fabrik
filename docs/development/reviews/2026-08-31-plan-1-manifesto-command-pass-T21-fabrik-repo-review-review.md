# T21 — /fabrik-repo-review: 63b manifesto conformance

Status: DONE

Surface: commands/_sources/fabrik-repo-review.md (187 lines post-fix, wc-derived, read in full; grep-derived anchors) + the RENDERED command `~/.claude/commands/fabrik-repo-review.md` (339 lines at evaluation: run-record :13-46 · term-coverage :47-72 · grounding-code :73-80 · subagents-core :242-245 · close-feedback :246-339 — all 5 spans verifier-confirmed exact; re-rendered at merge).
Outcome: 5 source fixes (secrets carve-out for pool dispatch; security-deferral risk-acceptance routing; stale pre-commit sync claim; backlog append-only semantics; backlog STRATEGIC_BACKLOG routing).

## 63b Verdict Table

| intersection | verdict (grep-derived SOURCE anchors, post-fix) |
|---|---|
| (a) checkable gates | CONFORMS — term-coverage supplies the coverage-adjudicated exit; Phase 4 exits only on every checklist row CLEAN/FIXED/REFUTED with EMBEDDED proof (:147-156); grader-honesty in-source: "No mechanical check reads the scratchpad ledger — the run record's round entries are the only graded trace" (:154-156); `found` counts every RAISED candidate incl. triage-refuted (:159-162); the FanoutBatch orphan-writer docstring claim verifier-confirmed against libs/subagents/agent.py:243-260 (:44-45) |
| (b) ledger routing + one-way field block | FIXED — a CONFIRMED SECURITY finding budgeted OUT of the run was silent triage; it is a risk-acceptance decision: surfaced to the operator, whose disposition (defer/waive) mints its `docs/DECISIONS.md` row in the run's change — the /fabrik-release waiver class; correctness-tier deferrals stay technical triage (:108-112). Migration authorization stays technical (tracked, idempotent, runner-applied — reversible implementation detail). One-way field block N/A — fixes are tested reversible diffs; deploy out of scope (:164-172) |
| (c) rigor scales with irreversibility | FIXED — the secrets carve-out was MISSING while the sibling dispatcher carries it: units touching secret-material paths are now reviewed NATIVE-ONLY, "secret contents never go to pool APIs … a leaked secret cannot be unleaked" (:51-56, mirrors execute-plan D4 — this command HUNTS leaked secrets, so inlining a unit containing one shipped the defect class under review to a third-party model). Otherwise conformed: risk-ranked units (:32-33); native finders for highest blast radius (:49-51); waves by risk tier (:60-62); "exhaustive on money/auth, proportionate on low-blast-radius" (:183-185) |
| (d) labeled verified/assumption evidence | CONFORMS — prove-before-flag with the pool-honesty split (pool findings "arrive unproven and get verified at Phase 2", :96); empty claims without coverage evidence don't count (:101-103); red→green per fix, environment-cannot-express-failure flagged not banked (:120-127); "a green gate is necessary but NOT proof of correctness" (:136-138) |
| (e) captured disorder | FIXED — the deferred backlog now lands as owner-tagged rows APPENDED to `docs/STRATEGIC_BACKLOG.md` in the run's change, append-only ("never rewrite or reflow existing rows — the shared-tree rules govern a file three sessions touch"), per the Doc Sync Matrix's deferred-work row (:176-180); RESIDUAL-RISKS explicit incl. synced-file upstream bugs (:180-182); "log anything you deliberately skip" (:184-185); the stale "pre-commit hook" sync claim corrected to POST-commit-since-2026-08-29 (:131 — the verifier's git-blame traced it to 66cd3eb7a, predating the architecture change) |
| (f) most-reversible default under ambiguity | CONFORMS — Phase 1 READ-ONLY (:40); throwaway repros never committed (:96-98); "never degrade shared or paid infrastructure … say so in the finding instead" (:124-127); synced files never edited locally — upstream or propose (:129-134); deploy stated as RECOMMENDATION (:170-172); "when unsure whether something is a bug, surface it" (:182-183). Wave-cap softness REFUTED as a gap: soft heuristics ("20+ workers", max_concurrency) are corpus-consistent design, not an ambiguity the executor must guess through |

6/6 adjudicated: 3 CONFORMS, 3 FIXED.

## Scoped verification review (nested /fabrik-review)

| round | findings | disposition |
|---|---|---|
| 1 — author-blind fabrik-reviewer verifier | 5 candidates: **2 CONFIRMED** (the source's ":run by the pre-commit hook" sync claim was stale — git-blamed to 66cd3eb7a/2026-08-03, contradicted by CLAUDE.md's post-commit move of 2026-08-29 AND .pre-commit-config.yaml stages, and my (f) cell had cited the containing span as CONFORMS evidence without catching it; the secrets carve-out was absent while execute-plan D4 has it verbatim — a leaked-secret unit's contents shipped to pool APIs by default) · **2 PLAUSIBLE adopted** (security-tier fix-budget deferral is risk acceptance, the T20 waiver class → operator surfacing + row mint :108-112; STRATEGIC_BACKLOG contention → append-only semantics stated :176-180) · **1 PLAUSIBLE REFUTED** (wave-cap softness — corpus-consistent design). Angles CLEAN: all 5 fragment spans exact, both line counts exact, every cited anchor verified, FanoutBatch docstring confirmed, term-coverage fragment confirmed | 4 source edits + artifact re-grounding; anchors re-derived post-edit (+8 net shift absorbed) |
| 2 — closing re-derivation sweep | found: 0, fixed: 0 — all cited anchors re-grepped against the 187-line source (:51-56, :108-112, :131, :176-180 confirmed verbatim) | TERMINAL no-op |

Verifier falsification streak: 21-for-21 — headline: the source carried a claim about the enforcement machinery that the machinery's own 2026-08-29 redesign had falsified, and my initial (f) cell endorsed the span containing it.

## Per-finding disposition ledger

1. Stale pre-commit sync claim (CONFIRMED) → source fix :131 (POST-commit since 2026-08-29).
2. Missing secrets carve-out (CONFIRMED, D4 class) → source fix :51-56, native-only for secret-material units.
3. Security-deferral risk acceptance (PLAUSIBLE→REAL, T20 waiver class) → source fix :108-112, operator surfacing + row mint.
4. STRATEGIC_BACKLOG append semantics (PLAUSIBLE) → source fix :176-180, append-only stated.
5. Wave-cap softness (PLAUSIBLE weak) → REFUTED: corpus-consistent soft heuristic.
