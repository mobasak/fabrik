---
description: Generate Behavior-Contract tests for a target (module/dir/file, or a phase's Behavior Contract) with native Claude seats (the pool is OFF, D-181) — suggest (one seat per module/area) → YOU curate → author in parallel (one seat per behavior, self-verified) → YOU review test-quality → git apply survivors. Standalone (backfill a suite), or auto-called by /fabrik-execute-plan per phase (its Execution Loop and dispatcher D4) and cited by /fabrik-plan-review as what a test-light plan owes; /fabrik-review renders the same shared fragment rather than copying it. TRIGGER — EN: "write tests for this", "backfill test coverage"; TR: "bunun için test yaz", "test kapsamını tamamla" — fires for AUTHORING new tests, not reviewing code. SKIP: adversarial code review (→ /fabrik-review) or full phase execution (→ /fabrik-execute-plan). Stage: 4-build.
argument-hint: "<module|dir|file to test — or a phase's Behavior Contract; omit to infer the behaviors from the current diff>"
---

# Behavior-Contract Test Generation — native seats author, you curate

> **Pool OFF (D-181, operator, 2026-09-07; mechanism D-182).** The OpenRouter subagent pool stays off, though its credentials are provisioned and a `fanout` would still SPEND: this text is the control, so every `fanout` / `pick_models` / `set_quality` / `record_agent_run` / `results_table` instruction in this command is SUSPENDED (kept in the re-enable line below). Run every fan-out NATIVELY with Claude Task subagents (`fabrik-reviewer` · `fabrik-researcher` · `fabrik-gui` · general-purpose): same unit split, same author-blind rule, same decide/refute/merge by you; a native seat records nothing, so no flywheel back-fill; `libs/subagents` is not called. Never write `NO-POOL:` for it: `check_subagent_flywheel.py`'s pool-or-declare layer stands down by the same ruling (`_POOL_POLICY_ON = False`, D-182), so no `NO-POOL:` is owed. Canonical: `62-using-subagents.md` § Dispatch policy.
> **Dispatch step (D-191):** run `python3 /opt/fabrik/scripts/sysadmin/dispatch_headroom.py --units <N> [--heavy] [--risky <R>] [--mechanical <M>]` and dispatch exactly the `SEATS:` and mix it prints, all in ONE message, each seat a distinct unit × angle brief with its model token — stamped BEFORE they go out with `python3 scripts/command_run.py dispatch --seats <n>` (what sibling sessions subtract), and closed with `python3 scripts/command_run.py round --seats <n> --findings <n> …` (the tripwire on D-186 is blind without it); the box is the ceiling, the units only the partition.

Turn "test every user-observable behavior" (the Behavior Contract — `CLAUDE.md` Completion Contract + `.windsurf/rules/core/45-testing-strategy.md`) into minutes-not-hours reality: **native seats author the tests; you own WHAT gets tested and the final quality.** Target = `$ARGUMENTS` (a module / dir / file, or a phase's `## Behavior Contract`); if empty, infer the behaviors from the current changed surface (`git diff`). Never author trivia (getters / framework glue / config) — lean-but-complete, one test per behavior.

{{include:run-record}}
{{include:orient}}

{{include:delegated-reads}}
## The loop — suggest → curate → author → review → apply

Context is never a reason to stop: the harness auto-compacts and the run continues — keep going.

{{include:test-generation-loop}}

The `###` sections below are the per-step DETAIL for exactly those five steps, and they live only here. The list renders from the shared fragment `/opt/fabrik/commands/_fragments/test-generation-loop.md`, which `/fabrik-review` renders too — it is the ONE place the shape is defined; edit the fragment, not the copy, or the reviewer's view of this pipeline stops matching it.

### 1. Suggest (one seat per module/area of the target, each briefed from a different angle)
Dispatch **one native Sonnet seat per module/area of the target**, each with a differently-angled brief (the module count is the PARTITION; the dispatch step prints the seats, never a token 2 (D-186) —, to propose the distinct user-observable behaviors of the target, then **union** them — a single suggester is the blind spot.

### 2. Curate (YOU — the anti-bloat + anti-gap gate)
Evaluate the union: ADD missing behaviors, CUT trivia + dupes, RISK-ORDER. You own WHAT gets tested — bloat and gaps stop here, before any authoring spend. Emit a curated list: one behavior per line, each a `Given / When / Then`, mapped to the test file it belongs in.

### 3. Commit the code-under-test FIRST (mandatory)
Tool-enabled authors run in a worktree on committed HEAD (`git worktree add --detach HEAD`), which carries only tracked files, so an UNCOMMITTED `.env`/key never reaches a pool author; a repo with a committed key gets NATIVE authors. So the code the tests target MUST be committed (or fully inlined into the author task) — else they test stale or absent code. Commit it now if it isn't: explicit pathspecs + provenance trailers per CLAUDE.md § EXIT, never `git add -A` on the shared tree (mid-pipeline is exactly when a sibling's WIP gets swept in). Never inline SECRET material into a task text (the corpus-wide carve-out family; a behavior that needs a live credential is authored NATIVE instead) — non-secret code MAY be inlined.

### 4. Author (native, parallel — one seat per curated behavior)
One native `general-purpose` seat per curated behavior (Sonnet), each with a DISJOINT test file, briefed to write ONLY that file — never the code under test — and to run `pytest` on it (activating the project's `.venv` first) before returning. Dispatch them in parallel; a seat that returns without a collecting test is re-dispatched once, then the behavior is yours to author.

### 5. Review test-quality (YOU) → keep the survivors
For each authored test file: would the test FAIL if the behavior broke? Real assertions, no mock-theater, no test that passes if the feature is reverted (`45-testing-strategy.md` + `/fabrik-review`'s test-quality checklist). And: could it fail in THIS environment at all? A test whose environment cannot express the failure (a superuser role for an RLS behavior, one tenant for an isolation behavior) is green for the wrong reason — flag it rather than banking it; never degrade shared or paid infrastructure to make it provable. Then keep each surviving test (the seats wrote them in the tree — delete a rejected one) and fix any weak test yourself. Finally `FABRIK_MUTMUT=1 python scripts/enforcement/check_mutation.py` on the applied code confirms the tests kill mutants (advisory).

## Where this auto-fires (3 call sites — the same loop, different trigger)
- **`/fabrik-execute-plan`, per phase (proactive):** after the phase CODE is committed + the phase gate is green, BEFORE the phase-boundary `/fabrik-review` — author the tests for the phase's `## Behavior Contract` behaviors the implementer did NOT already TDD (the risky ones stay implementer-TDD'd; native seats fill the rest).
- **`/fabrik-review` (reactive):** when a review finds a behavior with NO test, it invokes this loop for it.
- **Standalone (`/fabrik-generate-tests <module>`):** backfill an existing untested suite.

> **Re-enable rules (inert while the pool is OFF, D-181):** Import: `from libs.subagents import fanout, pick_models, set_quality` (vendor `libs/subagents` from `/opt/fabrik-lib/subagents` if absent; rebind the ImportError); if `fanout` is `None` STOP with the stated fail-mode: print the REAL ImportError, then "vendor `libs/subagents` AND install `libs/subagents/requirements.txt`, then re-run" before step 1. `fanout` auto-records UNSCORED, so you never call `record_agent_run` by hand; back-fill `set_quality(r.agent_id, score, project="test-gen", task_type="review"|"code", model=r.model)` for suggesters (step 2) and authors (step 5). Score the AUTHOR'S judgment, never a mechanical output-check. Write mode: `fanout("code", units, mode="write")`, DISJOINT `owned_paths`, `pick_models("code")` 3 distinct families, no hardcoded model IDs, no `prefer="value"`; `AUTHOR_PROMPT` MUST activate the project's `.venv` before `pytest`. Author test quality: your test-quality review is the whole verdict. Housekeeping: prefer the library's startup sweep; manual `.tmp/subagents` sweep ONLY when NO sibling agents are running.

{{include:close-chain}}
