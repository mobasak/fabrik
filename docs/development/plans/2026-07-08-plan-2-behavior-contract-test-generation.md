# Behavior Contract test rule + cheap-pool test generation

Status: CONVERGED
Spec: `docs/superpowers/specs/2026-07-08-behavior-contract-test-generation-design.md` (CONVERGED)
Date: 2026-07-08
Converged: 2026-07-08 (/fabrik-plan-review — demonstrably-thorough single-pass no-op, md5-verified; all path:line re-grounded live, and the plan confirmed to pass check_test_proposal.py under the CURRENT gate)

Replace fabrik's "1 test for highest-risk path" with a **Behavior Contract** (one test per distinct
user-observable behavior), make **cheap pool subagents author the tests**, and enforce it **fleet-wide** with
teeth: a hard structure gate + `/fabrik-review` substance + `mutmut` diff-scoped advisory mutation testing.

## What we already agreed (from the CONVERGED spec + operator decisions)

- **Rule:** Behavior Contract — enumerate every distinct **user-observable behavior / acceptance criterion**
  (`Given/When/Then`); one test per behavior, risk-ordered, TDD-risky, **skip trivia** (getters/glue) —
  lean-but-complete, NOT 100%-coverage dogma.
- **Workflow:** suggest (**2–3 diverse cheap pool models**, union) → **Claude curate** → **parallel pool
  authors** (one per behavior, `tools_enabled=True`) → report (`results_table` + `record_agent_run`) →
  **Claude review + fix**.
- **3-layer enforcement:** STRUCTURE (`check_test_proposal.py`, hard) + SUBSTANCE-human (`/fabrik-review`
  test-quality) + SUBSTANCE-mechanical (`mutmut` diff-scoped, **advisory**).
- **Operator DECISIONS (locked 2026-07-08):** `mutmut` **IN now, fleet-wide dev dep**; granularity =
  **user-observable / acceptance-criterion** (not per-branch, not per-user-story).
- **Vendor:** pool = VENDOR (`libs/subagents`, re-vendor `ce69478` recommended for `.env` autoload); `mutmut`
  = external dev dep; the check = BUILD glue; the `generate_tests` orchestration = 🆕 fabrik-lib candidate
  (project-local now).
- **Dependency:** the **authoring workflow (Phase D)** needs `2026-07-08-plan-1` (pool + `record_agent_run`
  live). Phases A–C are **independent** of plan-1.

## Behavior Contract (this plan's own tests — dogfoods the new rule; supersedes the One-Test Rule)

**Why:** the plan's risk is the enforcement code — a check that mis-counts behaviors is toothless or a
nuisance; a mutation runner that mis-scopes blocks the merge path. Each is tested as a distinct behavior.

- **Given** a plan whose Behavior Contract enumerates ≥1 `Given/When/Then` per acceptance criterion, **When**
  `check_test_proposal.py` runs, **Then** it PASSES.
- **Given** a plan with fewer contract behaviors than its stated criteria, **When** the check runs, **Then**
  it FAILS naming the shortfall.
- **Given** a plan with no Behavior Contract section, **When** the check runs, **Then** it FAILS (missing
  keywords), and **Given** no plans dir, **Then** it SKIPS (pass) — unchanged from today.
- **Given** a changed Python function with a weak test (a mutant survives), **When** the `mutmut` advisory
  runner runs diff-scoped, **Then** it reports the surviving mutant (advisory, exit 0). **Given** no changed
  Python, **Then** it skips.
- **Mocked:** none — the check + runner are tested against real temp plan files + a real tiny
  function/test pair (mutmut on a 1-function fixture); no mock-theater.

## Global Constraints (verbatim — every phase inherits)

- **Fabrik-synced files** (`CLAUDE.md`, `.windsurf/rules/**`, `scripts/enforcement/**`) are edited in
  `/opt/fabrik` ONLY — they overwrite project copies on sync; never edit a project's copy.
- **Command files are user-level** (`~/.claude/commands/*.md`) — live immediately, NOT repo-committed/gated.
- **`mutmut` is a DEV/CI dependency only** — never in a deployed runtime image; runs on WSL dev / CI.
- **Mutation testing is diff-scoped + ADVISORY** — never a full-suite per-PR blocking gate (hours + >50%
  equivalent-mutant noise).
- **`requirements.txt` / dep-file edits need authorization** (CLAUDE.md) — adding `mutmut` to a dev-deps file
  is such an edit; do it explicitly, never `git add -A`.
- **Gates run from WSL dev** (`python scripts/…`, `pytest`, `ruff`) — never a `fabrik …` shell-out.
- **Explicit-path commits + provenance trailers** on every AI commit.

## Context Ledger

| Source | What binds | Grounded ref |
|---|---|---|
| `.windsurf/rules/core/45-testing-strategy.md` (ACTIVE) | the testing rule to flip; already has a "When One Test Is Not Enough" section to expand | `:19` "One-Test Rule … exactly one …", `:32` "## When One Test Is Not Enough" |
| `CLAUDE.md` | the Completion-Contract test line to flip | `:25` "1 test for highest-risk path" |
| `scripts/enforcement/check_test_proposal.py` | the structure gate to extend | `:43` `required_keywords = ["One-Test Rule","Given","When","Then"]` (keyword-presence only today) |
| `scripts/fabrik_synced_manifest.py` | propagates the rule + check fleet-wide | `ENFORCEMENT_DIR`, `.windsurf/rules`, `CLAUDE.md` in the sync set |
| `libs/subagents` (VENDORED) | the pool authors — vendor, don't build | `run_agents`/`pick_models`/`record_agent_run`/`results_table`; `workspace.py:87` worktree `--detach HEAD` |
| `libs/subagents` re-vendor `ce69478` | `.env` autoload (authors' env "just works") | `/opt/fabrik-lib` @ `ce69478` `_dotenv.py` + `load_env` |
| **`mutmut` v3.6.0** (external dev dep) | diff-scoped mutation testing | https://pypi.org/project/mutmut (2026-06-06, pytest-native, incremental) |
| `2026-07-08-plan-1` | pool + `record_agent_run` live (Phase D only) | the plan's Phases C/D |

**🆕 fabrik-lib candidate:** `generate_tests(behavior_contract, code_paths) -> test_files` — the
suggest→curate→author→fix orchestration. Generic (any project auto-gens tests from a contract via the pool),
reused by ≥2 project types, small interface. Project-local now; propose to the hub after this ships.

No `shape:`/DB/deploy changes (governance + dev-tooling). No new external API beyond `mutmut`.

---

## Phase A — The RULE: Behavior Contract (fleet-synced; independent of plan-1)

**Files:** `CLAUDE.md` (`:25`), `.windsurf/rules/core/45-testing-strategy.md` (`:19`, `:32`),
`~/.claude/commands/fabrik-plan-after-chat.md` + `~/.claude/commands/fabrik-plan-review.md` (the test-rule
reference). **Responsibility:** state the Behavior Contract rule everywhere the "1 test" rule lives.

**Interfaces — Produces:** the term "Behavior Contract" + its `Given/When/Then`-per-behavior format that
Phase B's check keys on.

**Steps:**
1. `CLAUDE.md:25`: "1 test for highest-risk path" → "a **Behavior Contract**: one test per distinct
   user-observable behavior / acceptance criterion (skip trivia; lean-not-100%-coverage), TDD for the risky."
2. `45-testing-strategy.md:19` + `:32` ("When One Test Is Not Enough"): replace the "exactly one" rule with
   the Behavior Contract; keep the anti-coverage-dogma framing; state the pool test-gen workflow pointer.
3. The two plan commands (`fabrik-plan-after-chat`, `fabrik-plan-review`): rename the "One-Test Rule"
   requirement → "Behavior Contract" (the plan must enumerate a behavior per acceptance criterion).
4. **Gate:** `grep -c "Behavior Contract" CLAUDE.md .windsurf/rules/core/45-testing-strategy.md` → each `≥1`;
   `grep -c "1 test for highest-risk" CLAUDE.md` → `0`.
5. Doc-sync: `CHANGELOG.md`.

**Phase A closing sequence:** (1) gate green; (2) `python scripts/enforcement/check_doc_sync.py` + CHANGELOG;
(3) **`/fabrik-review`** on the diff (rule stated consistently across all 3 repo files; no contradiction) →
loop to no-op; (4) commit `CLAUDE.md` + `.windsurf/rules/core/45-testing-strategy.md` + `CHANGELOG.md`
(explicit paths, provenance). Command files are user-level (no commit).

---

## Phase B — The STRUCTURE gate: extend `check_test_proposal.py` (fleet-synced, HARD)

**Files:** `scripts/enforcement/check_test_proposal.py`, `tests/test_check_test_proposal.py` (new).
**Responsibility:** the plan must carry a Behavior Contract enumerating **a behavior per acceptance
criterion** — not a single test.

**Interfaces — Consumes:** the "Behavior Contract" term/format (Phase A). **Produces:** the extended check.

**Steps (highest-risk test FIRST):**
1. **Write the failing tests** `tests/test_check_test_proposal.py` (the Behavior Contract behaviors above):
   contract-enumerates-per-criterion → pass; fewer-behaviors-than-criteria → fail; no-contract → fail;
   no-plans-dir → skip. **Run red.**
2. Extend `check_test_proposal.py:43`: keyword `"One-Test Rule"` → `"Behavior Contract"` (keep `Given/When/
   Then`); **count** `Given/When/Then` blocks and compare to the plan's stated acceptance criteria (parse the
   contract section) — fail if behaviors < criteria. Keep the fail-safe skips (no dir / no plans). Carry the
   `# AFTER-EDIT:` coupling header.
3. **Run tests green.**
4. **Gate:** `pytest tests/test_check_test_proposal.py -q` green; `python
   scripts/enforcement/check_test_proposal.py` PASSES on this very plan (its Behavior Contract enumerates ≥1
   per criterion) — self-consistency.
5. Doc-sync: `INDEX.md` (new test file), `CHANGELOG.md`.

**Phase B closing sequence:** (1) gates green; (2) `check_doc_sync.py` + INDEX + CHANGELOG; (3)
**`/fabrik-review`** on the check + tests → no-op; (4) commit `scripts/enforcement/check_test_proposal.py` +
`tests/test_check_test_proposal.py` + `INDEX.md` + `CHANGELOG.md`.

---

## Phase C — `mutmut` diff-scoped advisory runner (fleet dev-dep; independent of plan-1)

**Files:** the project's **dev** requirements (e.g. `requirements-dev.txt` / the `[dev]` extra — **authorized
dep edit**), `scripts/enforcement/check_mutation.py` (new), `scripts/final_gate.py` (register advisory),
`tests/test_check_mutation.py` (new). **Responsibility:** prove new tests kill mutants — advisory, diff-scoped.

**Interfaces — Produces:** `check_mutation.py` (advisory) + a `run_optional_check(..., advisory=True)` line.

**Steps (highest-risk test FIRST):**
1. **Preflight:** `python -c "import mutmut; print(mutmut.__version__)"` — if absent, add `mutmut>=3.6` to the
   dev requirements (authorized) + `pip install`. Probe `mutmut version` ≥3.6.
2. **Write the failing test** `tests/test_check_mutation.py`: a 1-function fixture + a deliberately-weak test
   (asserts nothing meaningful) → the runner reports a surviving mutant (advisory); a strong test → clean.
   **Run red.**
3. Implement `check_mutation.py`: determine the **changed Python** (git diff vs the merge base / committed
   HEAD); if none → pass. Run `mutmut` **scoped to the changed functions** (incremental mode). ⚠️ **Sequence:**
   only against **applied, committed** code — never an un-applied worktree diff. Surviving mutants → print
   advisory (exit 0). Guard `mutmut` absence → skip with an actionable message.
4. **Run test green.**
5. Register in `final_gate.py:~628`: `run_optional_check("scripts/enforcement/check_mutation.py", "Mutation
   (advisory)", advisory=True)` — **advisory, never blocking** (the operator-approved diff-scoped form).
6. Doc-sync: `docs/CONFIGURATION.md` (the dev dep + how to run), `INDEX.md`, `CHANGELOG.md`.

**Phase C closing sequence:** (1) gates green (advisory WARN doesn't fail); (2) `check_doc_sync.py` +
CONFIGURATION + INDEX + CHANGELOG; (3) **`/fabrik-review`** on the runner + registration + test → no-op;
(4) commit the dev-reqs + `check_mutation.py` + `final_gate.py` + `tests/test_check_mutation.py` + docs.

---

## Phase D — The test-gen WORKFLOW (DEPENDS on plan-1's pool being live)

**Files:** `~/.claude/commands/fabrik-review.md` (+ a shared workflow note, or a `scripts/gen_tests.py`
helper — project-local, the 🆕 candidate). **Responsibility:** wire suggest(multi-model)→curate→author→fix
using the pool, per the runtime map.

**Interfaces — Consumes:** plan-1's pool (`run_agents` + `record_agent_run` live) + Phase A's Behavior
Contract + Phase C's `mutmut` runner.

**Steps:**
1. **Gate on plan-1:** `python -c "from libs.subagents import run_agents, record_agent_run, pick_models"` →
   exits 0 (pool live). If not, this phase is BLOCKED on plan-1 execution — stop, do not proceed.
2. Document/wire the workflow: **suggest** = `run_agents` with 2–3 diverse cheap models
   (`pick_models("review")`, `tools_enabled=False`, diff in the task) → union behaviors; **curate** = Claude;
   **author** = `run_agents` `task_type="code"`, `tools_enabled=True`, disjoint `owned_paths`, one per
   behavior, **code committed first** (worktree=`HEAD`), each self-verifies collection (`pytest`); **report**
   = `results_table` + `record_agent_run`; **fix** = Claude → then `check_mutation.py` on the applied code.
3. **Gate:** `grep -c "run_agents\|record_agent_run\|Behavior Contract" ~/.claude/commands/fabrik-review.md`
   → `≥1`; a real smoke: generate tests for one small real function via the pool → N tests for N behaviors,
   rows land in `subagent_runs` (superuser SELECT), `mutmut` advisory on the applied result.
4. Doc-sync: `CHANGELOG.md` (note); user-level command files (no commit).

**Phase D closing sequence:** (1) gates green; (2) CHANGELOG; (3) **`/fabrik-review`** on the workflow wiring
(consistent with 62 pool-vs-native + the runtime map; native curate/fix, pool suggest/author) → no-op;
(4) commit `CHANGELOG.md` (+ `scripts/gen_tests.py` if built); command files user-level (no commit).

## Final phase gate (after D)

- `python scripts/final_gate.py --check --json` → `"status":"success"`; `python
  scripts/enforcement/check_convergence.py` → pass; `python scripts/enforcement/check_test_proposal.py` →
  PASS on this plan (dogfood).
- `/fabrik-docs-review` — converge the testing docs (45-testing-strategy, CLAUDE.md, CONFIGURATION) to the
  Behavior-Contract reality to a no-op.

## File Scope (owned paths)

- `CLAUDE.md`, `.windsurf/rules/core/45-testing-strategy.md`
- `scripts/enforcement/check_test_proposal.py`, `scripts/enforcement/check_mutation.py` (new),
  `scripts/final_gate.py`
- the dev requirements file (`requirements-dev.txt` or the `[dev]` extra — grounded at Phase C start)
- `tests/test_check_test_proposal.py` (new), `tests/test_check_mutation.py` (new)
- `docs/CONFIGURATION.md`, `INDEX.md`, `CHANGELOG.md`
- **user-level (not repo):** `~/.claude/commands/{fabrik-plan-after-chat,fabrik-plan-review,fabrik-review}.md`
- **DISJOINT from `2026-07-08-plan-1`** — plan-1 owns `62-using-subagents.md` + `check_subagent_flywheel.py`
  + `scaffold.py`; this plan owns the testing files. Both touch `scripts/final_gate.py` + `CHANGELOG.md` +
  `INDEX.md` → **serialization points** (don't run Phase B/C concurrently with plan-1's Phase D; append,
  don't clobber).

## Evidence

- **A:** `45-testing-strategy.md:19` "One-Test Rule … exactly one" + `:32` "When One Test Is Not Enough";
  `CLAUDE.md:25` "1 test for highest-risk path".
- **B:** `check_test_proposal.py:43` `required_keywords = ["One-Test Rule","Given","When","Then"]` (presence
  only; no per-criterion count today — the gap this phase closes).
- **C:** `mutmut` v3.6.0 real + incremental — https://pypi.org/project/mutmut (2026-06-06); the
  advisory/diff-scoped best practice — https://agentpatterns.ai/verification/mutation-testing-quality-gate/;
  `final_gate.py:140 run_optional_check(advisory=)`, registration `:628`.
- **D:** pool live-proven (dogfood 2026-07-08: 3 `subagent_runs` rows); `workspace.py:87` worktree `--detach
  HEAD` (commit-before-author).

## Self-audit

- Coverage: rule → A; structure gate → B; mutmut → C; workflow → D; the LOCKED decisions (mutmut fleet-wide
  → C dev-dep; granularity → A+B behavior-per-criterion). No gap.
- Cross-phase signatures: "Behavior Contract" term (A.Produces) == B.Consumes (the check keys on it);
  `check_mutation.py` (C) invoked by D's fix step. Consistent.
- Grounding: all `path:line` + `mutmut`/best-practice URLs read live this session.

## Residual unknowns

- **[BLOCKING → Phase D only]** the authoring workflow needs `2026-07-08-plan-1`'s pool live. Resolution:
  execute plan-1 first (Phases A–C here are independent + can land before). Phase D gates on the import probe.
- **[OPEN → Phase B]** the exact parse of "acceptance criteria" the check counts behaviors against (the
  plan's stated criteria vs the contract's `Then`-clauses). Resolution: define the count as `Given/When/Then`
  triples in the `## Behavior Contract` section ≥ the plan's enumerated criteria; finalize against
  `check_test_proposal.py`'s real parse in execution.
- **[OPEN — coordination]** the `generate_tests` orchestration as a 🆕 fabrik-lib candidate — propose to the
  hub after project-local ship.
- **[OPEN → Phase C]** which dev-deps file the project uses (`requirements-dev.txt` vs a `[dev]` extra) —
  resolve by inspection at Phase C start.
