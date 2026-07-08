# Behavior Contract test rule + cheap-pool test generation — Design Spec

Status: CONVERGED
Date: 2026-07-08
Converged: 2026-07-08 (/fabrik-spec-review — 2 passes to an edit-free md5-verified no-op; mutmut + all best-practice citations re-verified live this session and confirmed to support their claims)
Depends on (PARTIAL — only the authoring workflow):
`docs/development/plans/2026-07-08-plan-1-subagent-pool-flywheel-enforcement.md`. The **pool-authoring
workflow** (suggest/author/report — steps 1, 3, 4) needs plan-1's pool + `record_agent_run` live. The **rule**
(Behavior Contract), the **structure gate** (`check_test_proposal.py`), and the **`mutmut` advisory layer**
are **independent of plan-1 and can land first** (Claude can also hand-write the tests until the pool
authoring is live).

## Goal

Replace fabrik's weak test rule — *"1 test for highest-risk path"* (`CLAUDE.md:25`, enforced by
`scripts/enforcement/check_test_proposal.py` + the plan "One-Test Rule") — with a **Behavior Contract**
(every distinct behavior tested, cheaply, via the pool), enforced fleet-wide with **teeth, not prose**. Fix
the two failure modes at once: **under-testing** (one test proves almost nothing) and **junk tests**
(generated tests that pass trivially — the "Test Homogenization Trap": LLM tests cluster on the model's own
blind spots, so a green suite overstates correctness).

## The rule change (Behavior Contract)

- **Now:** "1 test for highest-risk path" — a floor that reads as a ceiling.
- **New:** a **Behavior Contract** — enumerate every **distinct user-observable behavior / acceptance
  criterion** (a `Given / When / Then` each); **one test per behavior**, risk-ordered, TDD for the risky
  ones. Explicitly **skip trivia** (getters, framework glue, config) — **lean-but-complete, NOT
  100%-coverage dogma**. The contract IS the test plan; a behavior with no test is the defect.

## The workflow (operator-approved — cheap where cheap works, Claude where judgment matters)

1. **Suggest** — one cheap **pool** subagent (`run_agents`, `task_type="review"`) reads the changed code +
   proposes the behavior list. Ideation is cheap.
2. **Curate** — **Claude** evaluates the list: adds missing behaviors, cuts trivia/dupes, risk-orders. This
   is the **anti-bloat + anti-gap gate** — Claude owns *what* is tested before any authoring spend.
3. **Author (parallel)** — multiple cheap **pool** subagents (`run_agents`, `task_type="code"`,
   `tools_enabled=True`, worktree), **one per curated behavior**, write the tests. Cheap + fast.
4. **Report** — each returns its test + notes; `results_table` + `record_agent_run` per worker (feeds the
   flywheel).
5. **Fix** — **Claude** reviews (test-quality: would it fail if the behavior broke? real assertions, no
   mock-theater?) and fixes issues. Claude owns final quality.

So "test every behavior" costs **cents + minutes**, not hours of hand-writing — the maintenance-burden
objection dissolves.

## Enforcement — three layers (structure hard, substance human + mechanical)

You cannot mechanically judge "is this a good test" — but you can force the artifact + validate it two ways:

1. **STRUCTURE (hard, mechanical) — `check_test_proposal.py`.** The plan MUST carry a Behavior Contract that
   enumerates a behavior (`Given/When/Then`) per acceptance criterion — not a single "One-Test Rule". A plan
   with one behavior for a multi-behavior change fails the gate. (Extends the existing check; still
   fleet-synced via `scripts/enforcement/`.)
2. **SUBSTANCE — human (adversarial) — the phase-boundary `/fabrik-review` test-quality checklist** (already
   exists): each behavior actually tested; the test would fail if the behavior were reverted; no
   mock-theater / trivially-green.
3. **SUBSTANCE — mechanical (advisory, diff-scoped) — mutation testing (`mutmut`).** Run `mutmut` on the
   **changed functions only** (its incremental mode) to prove the new tests **kill mutants** — the current
   pro-grade way to catch the Test Homogenization Trap that coverage cannot. **ADVISORY, not a per-PR
   blocking gate** (see the cost caveat below): surfaces surviving mutants as a warning / nightly signal, so
   Claude (or the next pass) strengthens the assertions. **[DECISION: include now vs. defer — see below.]**

## Chosen approach (recommended): all three layers, mutation advisory + diff-scoped

The research is decisive that **coverage does not prove fault detection — mutation score does**, and that
generated tests specifically need it (homogenization). But mutation testing is expensive + noisy, so the
low-maintenance form is **diff-scoped + advisory**, never a full-suite per-PR block.

## Rejected alternatives

- **Coverage-threshold enforcement (require N% on new code).** REJECTED by the cited research — "high code
  coverage does not imply strong fault detection" (arxiv 2506.02954); coverage gates cause test-bloat + false
  confidence, exactly the maintenance hell to avoid.
- **Behavior Contract + pool, NO mutation layer (2-layer).** Viable + simplest (no `mutmut` dependency), but
  relies only on manual `/fabrik-review` for substance → weakest against the homogenization trap the operator
  flagged. Kept as the **fallback / phase-1** if `mutmut` is deemed too much now (the DECISION below).
- **Full-suite mutation as a hard per-PR gate.** REJECTED — full runs take hours + >50% equivalent-mutant
  noise (IEEE 2023 Zenseact case study); belongs nightly/post-merge + diff-scoped, advisory.

## External dependencies (grounded live, this session — 2026-07-08)

- **`mutmut` v3.6.0** (PyPI, released 2026-06-06 — actively maintained: 3.4.0 Nov 2025, 3.5.0 Feb 2026,
  3.6.0 Jun 2026). Python mutation tester, **pytest-native**, **incremental/diff-scoped** ("only re-tests
  mutants in functions whose source changed", "knows which tests to execute"), parallel, BSD-3, "strong
  focus on ease of use". Source: https://pypi.org/project/mutmut/ · https://github.com/boxed/mutmut (fetched
  2026-07-08). **Chosen over** `cosmic-ray` v8.4.6 (Beta, heavier distributed model) and `mutatest2` v4.0.1
  (a fork) — mutmut is the leanest maintained pytest-native diff-scoped option.
- **Best-practice grounding (the 1c gate):** mutation-score > coverage for test effectiveness —
  https://arxiv.org/html/2506.02954v1; Meta's mutation-guided LLM test generation (ACH) —
  https://arxiv.org/html/2501.12862 (Jan 2025) + https://engineering.fb.com/2025/09/30/security/llms-are-the-key-to-mutation-testing-and-better-compliance/;
  the "Test Homogenization Trap" + the diff-scoped/advisory/not-per-PR maintenance caveat —
  https://agentpatterns.ai/verification/mutation-testing-quality-gate/ (all fetched 2026-07-08).
- **OpenRouter pool** — the test-authoring workers; real costs proven this session (dogfood ~$0.0014/3-model
  review). No new external API beyond `mutmut`.

## fabrik-lib vendor → enhance → build verdict

| Capability | Verdict | Note |
|---|---|---|
| Pool runtime (`run_agents`/`pick_models`/`record_agent_run`/`results_table`) — the test-authoring workers | **VENDOR as-is** | `libs/subagents` @ `90e0d0d6`; no fabrik-lib test/mutation module exists (checked `/opt/fabrik-lib/README.md`) |
| `mutmut` mutation testing | **external pip dep** (not fabrik-lib) | added to the project's `requirements.txt` (per CLAUDE.md, deps edits need authorization); dev-only |
| Behavior-Contract check (`check_test_proposal.py` extension) | **BUILD (glue, fleet-synced)** | governance-specific; distributed via `scripts/enforcement/` sync |
| The suggest→curate→author→fix **test-gen orchestration** | **BUILD** — **🆕 fabrik-lib candidate** | generic (any project could auto-gen tests from a behavior contract via the pool), reused by ≥2 project types, small interface (`generate_tests(contract, code) -> tests`). Propose as a fabrik-lib module later; **project-local for now**, do NOT write into `/opt/fabrik-lib` |

## Shape / infra implications

- No new scaffold type; no deployed service. Governance + tooling. Touches the fleet-sync set (`CLAUDE.md`,
  `scripts/enforcement/`) + the user-level plan/review command files.
- `mutmut` is a **dev/CI dependency** only (not runtime) — belongs in the dev requirements, run on WSL
  dev/CI, never in the deployed image.

## Success criteria (testable)

1. `CLAUDE.md` **and the fleet-synced testing pack `.windsurf/rules/core/45-testing-strategy.md`** state the
   **Behavior Contract** rule (behavior-per-criterion, skip-trivia, lean-not-100%); the "1 test for
   highest-risk path" framing is gone from both.
2. `check_test_proposal.py` **fails** a plan that carries fewer behaviors than its acceptance criteria (a
   single-test plan for multi-behavior work); **passes** a plan whose contract enumerates each behavior.
3. The plan/review commands (`fabrik-plan-after-chat`, `fabrik-plan-review`) require a **Behavior Contract**
   (not a One-Test Rule); `/fabrik-review`'s test-quality checklist is the substance-human gate.
4. The test-gen **workflow** dispatches pool authors (`record_agent_run` rows land per author) — a real run
   produces N tests for N behaviors for cents.
5. (If the mutation layer is included) `mutmut` runs **diff-scoped** on the changed functions and reports
   surviving mutants **advisory** (non-blocking); a deliberately-weak test leaves a mutant alive → surfaced.

## Constraints

- **Lean, not dogma:** behaviors = user-observable/acceptance-level, risk-ordered; never one-per-method /
  getter / framework glue. The operator's hard line: 8 real tests beat 200 brittle ones.
- **Mutation testing is advisory + diff-scoped** — never a full-suite per-PR blocking gate (hours + noise).
- Depends on `2026-07-08-plan-1` (pool + `record_agent_run` live) for the authoring workflow to record.
- `requirements.txt` edit (adding `mutmut`) needs the authorization CLAUDE.md requires.

## Open / blocking unknowns

- **[DECISION — for approval]** include the **mutation (`mutmut`) advisory layer now** (recommended — it's
  the researched anti-junk-test mechanism, and diff-scoped keeps it lean) **vs. ship the 2-layer version
  first** (rule + pool workflow + structure gate + `/fabrik-review`) and add mutation as a fast-follow.
- **[DECISION — for approval]** behavior granularity — "user-observable behavior / acceptance criterion" is
  the default line; confirm it's not "every branch" (bloat) nor "every user story" (too coarse).
- **[OPEN — resolution step]** how `check_test_proposal.py` counts "behaviors vs acceptance criteria"
  mechanically (parse the Behavior Contract's `Given/When/Then` blocks vs the plan's stated criteria) —
  resolve in `/fabrik-plan-after-chat` against the check's real parsing model.
- **[OPEN — coordination]** the test-gen orchestration as a 🆕 fabrik-lib candidate — propose to the hub after
  this ships project-local.
