# Plan 2 — The rule-grounding floor (computed read-set + quote-verified digest)

Status: DRAFT
Origin: operator, this turn — *"partially, not the full contract. this is wrong. this is why ai agents
are drifting they dont read relevant rules fully. what do you suggest?"* → proposal accepted verbatim:
*"build it"* (spec skipped on the stated recommendation; mechanical extension of the two floors shipped today).
Shape: MONOLITH — 2 phases; READ set far under budget (fragment 1.2k + plan-review source 30k +
check sibling 9k + final_gate region).

## Intake Inventory

| I# | Item (anchored) | Disposition | Where |
|---|---|---|---|
| I1 | "they dont read relevant rules fully. what do you suggest?" → "build it" | IN — the whole plan | both phases |
| I2 | computed read-set ("FLOOR + packs whose globs hit the planned surfaces") | IN | Phase B step 1 (fragment v2) |
| I3 | quote-verified digest ("you cannot quote a line from a pack you did not open") | IN | Phase A (the check) + Phase B (digest contract text) |
| I4 | advisory first, date-gated, fire rate measured (standing rollout law) | IN | Phase A (warn_only, CUTOFF=2026-08-30) |
| I5 | dogfood: plan-1 is in the date window and must not red | IN | Phase B step 4 |

Intake: 5 items — 5 IN, 0 OUT-OF-SCOPE, 0 ASK.

## What we already agreed (operator-accepted proposal, verbatim scope)

- The MUST-READ-FULL set is COMPUTED: FLOOR + rubric-MATCHED packs for the artifact's surfaces;
  remaining ACTIVE/AVAILABLE packs are judgment reads. Replaces "read every ACTIVE pack".
- The CONSTRAINTS DIGEST becomes a table whose every row carries a VERBATIM mandate quote + `file:line`.
- A new warn_only check grades CONVERGED plans dated >= 2026-08-30: completeness (every MATCHED pack
  named in the digest) + integrity (every quoted string exists in its cited file, whitespace-normalised).
- /fabrik-plan-review gains the audit row (re-derive MATCHED, spot-verify quotes).
- NOT doing: token-count/timer reading proxies (theater); blocking enforcement day one; spec-side
  mechanical grading (specs keep the review-audited digest — revisit after the plan-side fire rate).

## Context Ledger

| Source | What binds | Grounded ref |
|---|---|---|
| the gate block's single home | ONE fragment feeds both commands — edit once, render | commands/_fragments/grounding-rules.md:1 (marker `rule-grounding-gate v1`; included by fabrik-spec.md + fabrik-plan-after-chat.md, grep-verified) |
| companion cite fragment | digest-citation law lives elsewhere and is NOT touched | commands/_fragments/grounding-rules-cite.md:8 (`rule-grounding-cite v1`, inlined into orchestrator docs) |
| Traycer twin | the fragment's marker says an operator-owned Traycer copy exists | grounding-rules.md:1 twin-sync note — NOT editable from here; flagged to operator in close-out |
| warn_only registration model | how the check joins the gate | scripts/final_gate.py:1100-1106 (`run_optional_check("scripts/enforcement/check_spec_convergence.py", "Spec convergence", warn_only=True)`) |
| the sibling check to mirror | guards, ASCII print, budget, date-gate pattern | scripts/enforcement/check_spec_convergence.py (SystemExit/Exception → return 0; `_say`; ADVISORY_BUDGET) |
| rubric MATCHED grammar | the parseable line the check consumes | review_rubric.py output `### <pack>  (hit: <paths>)` under `## MATCHED` (observed 3× today) |
| dogfood target | plan-1's digest is prose, in the date window | docs/development/plans/2026-08-30-plan-1-decision-ledger.md:52 (`Constraints digest: kebab-case…`) |
| core/10-python.md (ACTIVE) | check + test discipline | .windsurf/rules/core/10-python.md |
| core/45-testing-strategy.md (ACTIVE) | red-first for the risky behaviors | .windsurf/rules/core/45-testing-strategy.md |
| fabrik-lib | no module fits (process/enforcement tooling — below the module bar) | /opt/fabrik-lib/README.md table |

## Constraints Digest

| rule (verbatim) | where | implication here |
|---|---|---|
| "A non-zero exit from a `warn_only` check is a BLOCKING red across ~46 governance-synced repos." | scripts/enforcement/check_spec_convergence.py:29 | the new check always exits 0; guards mirrored |
| "Watched-fail-first (for tests THIS change adds or modifies): a non-trivial behavior's test must be SEEN RED" | CLAUDE.md § Completion Contract | Phase A step 1 runs the suite red before implementing |
| "NEVER bare-render `commands/assemble_commands.py` from a worktree" | CLAUDE.md § Behavior (Merge-time render only) | Phase B renders from the MAIN checkout only |
| "measured, not vibed — before adding any new rule/check/mechanism, measure its fire rate" | CLAUDE.md § THE FIX DIRECTIVE 5 | date-gate + live fire-rate measurement in Phase B step 4 |

## Global Constraints (both phases inherit)

- NO-POOL (operator standing directive): native/solo, declared per commit.
- The check is a stdlib CLI: stdout only, no deps, always exit 0; `# AFTER-EDIT:` header.
- commands/_fragments/ is corpus source: `--check` render first, bare render from MAIN only.
- Shared tree: explicit pathspecs · numstat before commit · `git reset -q HEAD --` after ·
  fetch+ff push · trailers (`Agent-Role: primary` · `Agent-Name: infra` · `Agent-Phase: A|B`).

## Phase A — the check, red-first

Files: `scripts/enforcement/check_rule_grounding.py` (new) · `tests/enforcement/test_rule_grounding.py`
(new) · `scripts/final_gate.py` (one registration block).

Interfaces — Produces: CLI `check_rule_grounding.py [--root .]`; findings `NO-DIGEST` ·
`PACK-NOT-IN-DIGEST` · `QUOTE-NOT-FOUND`; graded population = CONVERGED plans (monolith `.md` +
set spines) with filename date >= `FLOOR_CUTOFF = "2026-08-30"`; MATCHED derived by subprocess of
`<root>/scripts/review_rubric.py --changed <File Scope paths>` (tests plant a tiny fake rubric
printing controlled `### pack  (hit: …)` lines — hermetic, no glob re-implementation). Consumes: nothing.

1. **Red-first: `tests/enforcement/test_rule_grounding.py`, WATCH IT FAIL** — behaviors:
   (a) Given a CONVERGED in-window plan with NO `## Constraints Digest` section, Then `NO-DIGEST`;
   (b) Given a digest whose rows omit a pack the fake rubric MATCHES for the plan's File Scope,
   Then `PACK-NOT-IN-DIGEST` naming it; (c) Given a row quoting text that does NOT exist in its cited
   file, Then `QUOTE-NOT-FOUND`; (d) Given a quote that exists but line-WRAPPED in the source, Then
   clean (whitespace-normalised match — today's wrapped-HTML lesson); (e) Given a pre-cutoff filename
   (2026-08-27), Then silent; (f) Given DRAFT status in-window, Then silent; (g) bad flag / broken
   stdout, Then exit 0 (the warn_only contract).
   Gate: `python3 -m pytest tests/enforcement/test_rule_grounding.py -q` → red for the right reasons.
2. Implement the check mirroring `check_spec_convergence.py`'s frame (guards, `_say` ASCII print,
   ADVISORY_BUDGET cap, census line with denominator: `N CONVERGED in-window plan(s) examined`).
   Digest row grammar: first cell = the quote (backtick/bold tolerated), second cell `path[:line]`;
   integrity = normalised-whitespace substring of the cited FILE (line drift tolerated by design —
   packs move; the quote is the proof of reading, the line is a courtesy). Gate: suite green.
3. Register in `scripts/final_gate.py` beside the spec-convergence block (:1100 area), same terms:
   `run_optional_check("scripts/enforcement/check_rule_grounding.py", "Rule grounding (plans)",
   warn_only=True)`. Gate: `python scripts/final_gate.py --check --json` → success, and the new
   check's line visible in its output.
4. Closing sequence: gates green → `check_doc_sync.py` (INDEX row lands Phase B with the doc batch) →
   **/fabrik-review on Phase A's changed surface to its coverage-adjudicated exit (BLOCKING)** →
   commit `-- <the 3 paths>` (Agent-Phase: A) + push.

## Phase B — the contract text, the dogfood, the docs

Files: `commands/_fragments/grounding-rules.md` (v1→v2) · `commands/_sources/fabrik-plan-review.md`
(audit row) · `docs/development/plans/2026-08-30-plan-1-decision-ledger.md` (digest table dogfood).

Interfaces — Consumes: Phase A's finding names + the MATCHED grammar (the fragment text names the
exact command and the check by name). Produces: nothing downstream.

1. `grounding-rules.md` → marker `rule-grounding-gate v2`, body: run `select_rules.py` for the ACTIVE
   census; **the MUST-READ-FULL set is COMPUTED** — FLOOR + every pack
   `python scripts/review_rubric.py --changed <the surfaces this artifact will touch>` MATCHES —
   fresh full reads of exactly that set; other ACTIVE/AVAILABLE packs are judgment reads; the
   CONSTRAINTS DIGEST is a table, one row per MUST/BAN relevant to scope, **every row a VERBATIM
   quote + `file:line`** — "you cannot quote a line from a pack you did not open";
   `check_rule_grounding.py` grades the countable subset on CONVERGED plans (named honestly —
   quote-integrity + pack-completeness; reading QUALITY stays the review's audit — the
   enforcement-overclaim lesson); INCOMPLETE-DIGEST stays a blocking authoring finding. Keep the
   Traycer twin-sync note, bumped to v2.
2. `fabrik-plan-review.md` § high-risk axes: the audit row — re-derive the MATCHED set from the
   plan's File Scope yourself (run the rubric, don't trust the digest's own claim) and spot-verify
   ≥2 digest quotes verbatim in their cited packs; a missing MATCHED pack or an unfindable quote is
   a finding.
3. Render: `--check` (expect DRIFT on exactly the 2 sources that include the fragment + plan-review)
   then bare render from MAIN. Gate: `rendered 32 commands …`.
4. Dogfood + fire-rate measurement: convert plan-1's prose digest (:52) to the quote table (real
   verbatim quotes from its three cited surfaces); then run
   `python3 scripts/enforcement/check_rule_grounding.py` live — expected: plan-1 and THIS plan both
   clean, zero findings on the corpus (the measured landing fire rate; a nonzero result is a finding
   to fix before commit, not to ship).
5. Docs: INDEX.md row for the check · CHANGELOG entry (one, for the whole plan) ·
   `docs/LESSONS_LEARNT.md` entry-or-none.
6. Final: `python scripts/final_gate.py --check --json` → success ·
   `python scripts/enforcement/check_convergence.py` → clean · **/fabrik-docs-review is NOT owed**
   (no reference-doc surface changed; the fragment is corpus, gate-checked by render + drift).
7. Closing sequence: **/fabrik-review on Phase B's changed surface to its adjudicated exit
   (BLOCKING)** → commit (Agent-Phase: B) + push.

## Execution Discipline (binding on /fabrik-execute-plan)

- **Review floor** — each phase runs /fabrik-review on its changed surface to a coverage-adjudicated
  exit before its commit.
- **Dispatch policy** — NO-POOL: operator standing directive; every phase native/solo, declared per
  commit (the flywheel check's sanctioned escape).
- **Parallelism + merge** — none: B consumes A's finding names and check name in its prose. Two
  serial phases, one session.

## File Scope (owned paths)

- scripts/enforcement/check_rule_grounding.py
- tests/enforcement/test_rule_grounding.py
- scripts/final_gate.py
- commands/_fragments/grounding-rules.md
- commands/_sources/fabrik-plan-review.md
- docs/development/plans/2026-08-30-plan-1-decision-ledger.md

(CHANGELOG.md, INDEX.md, docs/LESSONS_LEARNT.md are shared-append surfaces outside the scope/lock;
Phase B names their rows.)

## Coverage Checklist

| Class | Source | Verdict (adjudicated by /fabrik-plan-review over the PLAN) |
|---|---|---|
| security-auth floor (35) | rubric FLOOR | CLEAN — no auth surface; check is read-only stdlib |
| data-postgres floor (25) | rubric FLOOR | CLEAN — no DB |
| ops floor (30) | rubric FLOOR | CLEAN — no deploy surface |
| 12-Factor | rubric FLOOR | CLEAN — stdout-only CLI, no service |
| python discipline (10) | rubric MATCHED | CLEAN — sibling-mirrored frame, AFTER-EDIT header planned |
| testing strategy (45) | rubric MATCHED | CLEAN — 7 red-first behaviors incl. the fail-open guards |
| documentation rules (40) | rubric MATCHED | CLEAN — INDEX/CHANGELOG owned by B5; fragment is present-tense rule text |
| fail-open vs fail-closed | standing | CLEAN — warn_only always-0 with sibling guards; date-gate fails toward NOT grading |
| enforcement-overclaim | standing | CLEAN — fragment names the check's countable subset only; quality stays review-audited (B1 wording is explicit) |
| boundary/sentinel/prefix | standing | CLEAN — cutoff boundary tested both sides (e/f); whitespace-normalised match kills the wrapped-line false-fabricated inverse |
| behavior-without-a-test | standing | CLEAN — every check behavior has a G/W/T row; corpus text adjudicated by B's phase review |
| cost/limit edges | standing | CLEAN — subprocess is local + bounded; no spend |

```
$ python scripts/review_rubric.py --changed scripts/enforcement/check_rule_grounding.py tests/enforcement/test_rule_grounding.py scripts/final_gate.py commands/_fragments/grounding-rules.md commands/_sources/fabrik-plan-review.md
# REVIEW RUBRIC — inject into EVERY finder prompt (generated by review_rubric.py)
## FLOOR — always injected, regardless of glob (spec L3)
### core/35-security-auth.md
### core/25-data-postgres.md
### core/30-ops.md
### 12-FACTOR (all twelve axes)
## MATCHED — packs whose globs hit the changed paths
### core/10-python.md  (hit: scripts/enforcement/check_rule_grounding.py, scripts/final_gate.py, tests/…)
### core/40-documentation.md  (hit: commands/_fragments/grounding-rules.md, commands/_sources/fabrik-plan-review.md)
### core/45-testing-strategy.md  (hit: tests/enforcement/test_rule_grounding.py)
```

## Behavior Contract

- **Given** a CONVERGED plan dated in-window with no Constraints-Digest section, **When** the check runs, **Then** NO-DIGEST fires (tests/enforcement/test_rule_grounding.py)
- **Given** the fake rubric MATCHES a pack absent from the digest, **When** the check runs, **Then** PACK-NOT-IN-DIGEST names it (tests/enforcement/test_rule_grounding.py)
- **Given** a digest row quoting text absent from its cited file, **When** the check runs, **Then** QUOTE-NOT-FOUND fires (tests/enforcement/test_rule_grounding.py)
- **Given** a true quote that is line-wrapped in the source, **When** the check runs, **Then** no finding (whitespace-normalised) (tests/enforcement/test_rule_grounding.py)
- **Given** a pre-cutoff plan filename, **When** the check runs, **Then** it is not graded (tests/enforcement/test_rule_grounding.py)
- **Given** a DRAFT in-window plan, **When** the check runs, **Then** it is not graded (tests/enforcement/test_rule_grounding.py)
- **Given** a bad flag or broken stdout, **When** invoked, **Then** exit is 0 (tests/enforcement/test_rule_grounding.py)

## Evidence

- Phase A: sibling frame read this session (`check_spec_convergence.py` guards at :198-208, `_say` at
  :101, budget at :223-237); registration model:

```
$ grep -n "check_spec_convergence" scripts/final_gate.py
1102:            "scripts/enforcement/check_spec_convergence.py",
```

- Phase B: the fragment is the single home — grep proof:

```
$ grep -rln "rule-grounding-gate" commands/
commands/_fragments/grounding-rules.md
$ grep -rln "grounding-rules" commands/_sources/*.md
commands/_sources/fabrik-plan-after-chat.md
commands/_sources/fabrik-spec.md
```

- Dogfood target read: plan-1:52 is a prose `Constraints digest:` paragraph; the MATCHED grammar
  `### <pack>  (hit: …)` observed verbatim in three rubric runs today.

## Self-audit

- (a) Coverage: I2→B1 (computed set), I3→A+B1 (quote contract + grader), I4→A (warn_only+cutoff)
  +B4 (fire rate), I5→B4 (dogfood). No gaps.
- (b) Cross-phase signatures: finding names (NO-DIGEST/PACK-NOT-IN-DIGEST/QUOTE-NOT-FOUND) and the
  check filename appear identically in A2 and B1; the MATCHED grammar string is quoted once and
  consumed by both A2 (parser) and B2 (audit row).
- Fixed point: /fabrik-plan-review owes the independent convergence.

## Review Pass Ledger (/fabrik-plan-review, solo native — NO-POOL)

| Pass | scope | method | raised | edits | plan md5 |
|---|---|---|---:|---:|---|
| Pass 1 | (to be run) | citation | | | |

## Residual unknowns

- Resolved: the block's single home (fragment, grep-proven) · registration model (:1102) · dogfood
  in-window (plan-1 dated today).
- Open, non-blocking: the Traycer "My Workflow" fab-mega-00-trigger copy of the v1 block is
  operator-owned — resolution: named in this plan's close-out + the v2 marker keeps the twin-sync
  note so the drift is visible; the operator updates Traycer at their convenience.
- Open, non-blocking: spec-side mechanical grading deliberately deferred — resolution: revisit after
  the plan-side fire rate has two weeks of data (backlog note in CHANGELOG entry).
