---
description: Generate Behavior-Contract tests for a target (module/dir/file, or a phase's Behavior Contract) by offloading authoring to cheap pool models — suggest (diverse) → YOU curate → author in parallel (write-mode, sandboxed, self-verified) → YOU review test-quality → git apply survivors. Standalone (backfill a suite), or auto-called by /fabrik-execute-plan per phase and /fabrik-review reactively. TRIGGER — EN: "write tests for this", "backfill test coverage"; TR: "bunun için test yaz", "test kapsamını tamamla" — fires for AUTHORING new tests, not reviewing code. SKIP: adversarial code review (→ /fabrik-review) or full phase execution (→ /fabrik-execute-plan). Stage: 4-build.
argument-hint: "<module|dir|file to test — or a phase's Behavior Contract; omit to infer the behaviors from the current diff>"
---

# Behavior-Contract Test Generation — the pool authors, you curate

Turn "test every user-observable behavior" (the Behavior Contract — `CLAUDE.md` Completion Contract +
`.windsurf/rules/core/45-testing-strategy.md`) from a rule into cheap, minutes-not-hours reality: **cheap pool
models author the tests; you own WHAT gets tested and the final quality.** Target = `$ARGUMENTS` (a module / dir
/ file, or a phase's `## Behavior Contract`); if empty, infer the behaviors from the current changed surface
(`git diff`). Never author trivia (getters / framework glue / config) — lean-but-complete, one test per behavior.

{{include:run-record}}
## Import the VENDORED pool (`from libs.subagents import …`)

`fanout` / `pick_models` / `set_quality` come from the **vendored** `libs/subagents` (copied from canonical
`/opt/fabrik-lib/subagents` per `.windsurf/workflows/subagent-runs-flywheel.md`). `fanout` auto-records each run
(so you never call `record_agent_run` yourself), but records them **UNSCORED** — `set_quality` back-fills the
verdict (step 5). If the project hasn't vendored it yet, vendor first, then import:

```bash
# vendor once (if libs/subagents/ is absent) — see .windsurf/workflows/subagent-runs-flywheel.md
[ -f libs/subagents/__init__.py ] || cp -r /opt/fabrik-lib/subagents/subagents/. ./libs/subagents/
```

```python
try:
    from libs.subagents import fanout, pick_models, set_quality
except ImportError:  # not vendored here → this command's pool test-authoring is unavailable
    fanout = pick_models = set_quality = None
```

## The loop — suggest → curate → author → review → apply

**Context is never a reason to stop:** the harness auto-compacts and the run continues — keep going.

### 1. Suggest (pool, multi-model — diversity is the whole point)
Dispatch **2–3 diverse cheap models** to each propose the distinct user-observable behaviors of the target, then
**union** them (a single suggester is the blind spot — different families catch what one misses):

```python
results, table = fanout("review", units=[SUGGEST_PROMPT] * 3, repo=REPO, project="test-gen",
                        mode="read_only")   # 3 UNITS -> 3 agents (draw defaults to len(units); if the ranking is thin, duplicates share a model) on 3 diverse models (k alone only sizes the model DRAW; one unit = ONE agent). read_only -> inline the target's code into SUGGEST_PROMPT
```

### 2. Curate (YOU — the anti-bloat + anti-gap gate)
Evaluate the union: ADD missing behaviors, CUT trivia + dupes, RISK-ORDER. **You own WHAT gets tested** — bloat
and gaps are stopped here, before any authoring spend. Emit a curated list: one behavior per line, each a
`Given / When / Then`, mapped to the test file it belongs in.

Curating IS your verdict on the suggesters, so **score them back to the flywheel** (the suggest `fanout` recorded
them UNSCORED too — same trap as the authors); this sharpens `pick_models("review")` for behavior-suggesting —
the same record-then-score discipline the authors get:

```python
for r in results:                        # the SUGGEST results from step 1 (before step 4 reuses the name)
    set_quality(r.agent_id, kept_share(r),   # 0 = all trivia/dupes/cut · 5 = mostly kept, high-signal behaviors
                project="test-gen", task_type="review", model=r.model)
```

### 3. Commit the code-under-test FIRST (mandatory)
Tool-enabled authors run in a worktree on **committed HEAD** (`git worktree add --detach HEAD`), so the code the
tests target MUST be committed (or fully inlined into the author task). Commit it now if it isn't — else the
authors test stale/absent code.

### 4. Author (pool, parallel — one author per curated behavior)
```python
units = [{"task": AUTHOR_PROMPT(b), "owned_paths": [test_file_for(b)]} for b in curated]  # DISJOINT paths
results, table = fanout("code", units=units, repo=REPO, project="test-gen", mode="write")
```
- `mode="write"` → `tools_enabled=True`, disjoint `owned_paths` **enforced (raises on overlap)**, pool =
  `pick_models("code")` — 3 **distinct families** (the exact model IDs drift; let `pick_models` pick them and
  read `CODING_SUBAGENT_SELECTION.md` — never hardcode model IDs). `prefer="quality"` (fanout's default) gives
  the family-diverse pick; don't pass `prefer="value"` here (it clusters onto the one cheapest family).
- Each author WRITES its test file, runs `pytest` on it in the **bwrap sandbox**, and **self-verifies collection**
  before returning; `fanout` **captures each diff, never auto-applies it** (review-before-apply) + auto-records
  the flywheel row, and **auto-recovers a zero-output-cap straggler once** (`recover_caps=True` — one fresh
  dispatch of the **SAME model** so OpenRouter's health-aware routing re-routes it to a healthy provider; it's
  NOT a vendor swap. A transient provider stall gets that one honest second chance; a *persistently* flaky model
  is down-ranked by the flywheel **statistically over many runs, not reactively** — so a congested provider
  doesn't silently drop a test, and a genuinely bad model isn't papered over by reactive retries).
- **Deps for self-verify:** the author's worktree must reach the project's deps. If the project's deps live only
  in a non-inherited `.venv`, `AUTHOR_PROMPT` MUST activate it (`source .venv/bin/activate` / the project's
  runner) before `pytest`, or self-verify fails on import.

### 5. Review test-quality (YOU) → score the flywheel → apply the survivors
For each captured `result.diff`: **would the test FAIL if the behavior broke?** Real assertions, no mock-theater,
no test that passes if the feature is reverted (`45-testing-strategy.md` + `/fabrik-review`'s test-quality
checklist). **And: could it fail in THIS environment at all?** A test whose environment cannot express the
failure (a superuser role for an RLS behavior, one tenant for an isolation behavior) is green for the wrong
reason — flag it rather than banking it; never degrade shared or paid infrastructure to make it provable. Then
**`git apply`** each surviving diff into the tree; fix any weak test yourself. Finally
`FABRIK_MUTMUT=1 python scripts/enforcement/check_mutation.py` on the applied code confirms the tests kill
mutants (advisory).

**Back-fill the verdict — the step `fanout` cannot do for you.** `fanout` recorded every author at DISPATCH with
a `NULL` `quality_score`; your review above IS the ground-truth verdict, so feed it back or the flywheel learns
nothing about which code models author good tests:

```python
for r in results:                        # the AgentResults fanout returned (each carries .agent_id + .model)
    set_quality(r.agent_id, score(r),    # score: 0 = mock-theater / passes when the behavior is reverted;
                project="test-gen", task_type="code", model=r.model)   # 5 = real assertion that fails when it breaks
```

Score the AUTHOR'S judgment (did the test genuinely prove the behavior), never a mechanical output-check — a
hallucinated/weak test scored 4/5 poisons `pick_models("code")`. `set_quality` is fail-open + INSERT-only (a
scored delta row keyed on `agent_id`); a capped/errored author auto-coerces to `NULL` (a provider stall is not a
bad model). Skipping this leaves every row `NULL` and `pick_models("code")` never sharpens.

### Housekeeping — prune orphaned author worktrees (before a high-volume run)
A killed author process leaks its `.tmp/subagents/<id>` worktree (`git worktree prune` alone won't remove the
dir). Sweep them first:
```bash
# PREFER the library's own startup sweep (arun_agents runs sweep_stale_worktrees: PID-aware + age-guarded).
# Manual sweep ONLY when NO sibling agents are running anywhere on this repo — age (-mmin +120) is a WEAK
# guard (a live agent's worktree ROOT mtime can be old; only the PID sidecar proves liveness):
git worktree prune; find .tmp/subagents -maxdepth 1 -type d -name 'agent-*' -mmin +120 -exec rm -rf {} + 2>/dev/null || true
```

## Where this auto-fires (3 call sites — the same loop, different trigger)
- **`/fabrik-execute-plan`, per phase (proactive):** after the phase CODE is committed + the phase gate is green,
  BEFORE the phase-boundary `/fabrik-review` — author the tests for the phase's `## Behavior Contract` behaviors
  the implementer did NOT already TDD (the risky behaviors stay implementer-TDD'd; the pool fills the rest).
- **`/fabrik-review` (reactive):** when a review finds a behavior with NO test, it invokes this loop for it.
- **Standalone (`/fabrik-generate-tests <module>`):** backfill an existing untested suite.

## Subagents — flywheel (fanout records; YOU score)
`fanout(record=True, project=…)` records each author automatically — but **UNSCORED** (a `NULL` `quality_score`
at dispatch), so you never call `record_agent_run` by hand (⚠️ and NOT `record_run`, which no-ops on a raw
`AgentResult`). Record and score are **two steps**: `fanout` records at dispatch; YOU back-fill the verdict via
`set_quality` for **every** run it dispatched — the suggesters at curate (step 2, `task_type="review"`) AND the
authors at review (step 5, `task_type="code"`). Skip the score and rows stay `NULL` and `pick_models` never
sharpens for either role. `scripts/enforcement/check_subagent_flywheel.py` BLOCKS the gate on a substantial code
change with ZERO pool runs (pool-or-declare) — running THIS command on a phase's Behavior Contract is exactly how
you satisfy it for test-shaped work.
