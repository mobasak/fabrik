### The five steps — cheap where cheap works, YOU where judgment matters

Per `.windsurf/rules/core/62-using-subagents.md` § Dispatch policy + `.windsurf/rules/core/45-testing-strategy.md`. **⚠️ POOL OFF — D-181 (2026-09-07):** the pool steps below are SUSPENDED; the same five steps run with NATIVE seats (the pool version is kept commented beneath for re-enable).

1. **Suggest (native — one seat per module/area of the target, 3+ on anything larger than a single file; never a token 2, D-186)** — dispatch one native `general-purpose`/`fabrik-reviewer` subagent per area (Sonnet; the code under test inlined or pointed at by path) to each propose the distinct user-observable behaviors; **union** them. A single suggester is the blind spot — differently-briefed seats catch what one misses.
2. **Curate (YOU)** — evaluate the union: add missing behaviors, cut trivia/dupes, risk-order. You own *what* gets tested (the anti-bloat + anti-gap gate) before any authoring spend.
3. **Author (native, parallel)** — one native `general-purpose` subagent per curated behavior (Sonnet), each with a DISJOINT test file to write, briefed to run `pytest` on its own file and return only when it collects and passes. ⚠️ Native authors work in the live tree: brief each one to touch ONLY its own test file, never the code under test.
4. **Report (no flywheel)** — a native seat produces no `AgentResult`: nothing records, nothing is scored. List the authored files + the per-file pytest result in the run instead.
5. **Fix (YOU)** — review test-quality (would it fail if the behavior broke? real assertions, no mock-theater? could it fail in THIS environment at all?), fix issues, then `FABRIK_MUTMUT=1 python scripts/enforcement/check_mutation.py` on the **applied** code to confirm the tests kill mutants (advisory). You own final quality.

So "test every behavior" (the Behavior Contract) costs **minutes on subscription quota**, not hours of hand-writing — the maintenance-burden objection dissolves.

<!-- POOL OFF (D-181, 2026-09-07) — the pool version of the five steps, kept verbatim for re-enable:
Per `.windsurf/rules/core/62-using-subagents.md` § Dispatch policy + `.windsurf/rules/core/45-testing-strategy.md`:

1. **Suggest (pool, multi-model)** — `fanout("review", units=[<the suggest task, code inlined> ×3], mode="read_only")` (3 UNITS → 3 agents on 3 diverse families — one unit = ONE agent; `k` only sizes the model draw, never the fan-out) to each propose the distinct user-observable behaviors; **union** them. A single suggester is the blind spot — diverse families catch what one misses, for cents.
2. **Curate (YOU)** — evaluate the union: add missing behaviors, cut trivia/dupes, risk-order. You own *what* gets tested (the anti-bloat + anti-gap gate) before any authoring spend. Score the suggesters back (`task_type="review"`) — curating IS your verdict on them.
3. **Author (pool, parallel)** — `fanout("code", units=[{"task":…, "owned_paths":[<test file>]}, …], mode="write")` — one cheap **pool** author per curated behavior, **disjoint `owned_paths`** so each writes its own test file in parallel. ⚠️ Tool-enabled authors see committed **HEAD** (`workspace.py` `worktree add --detach HEAD`) — **commit the code-under-test first** (or inline it), and each author **self-verifies collection** (`pytest` on its new test) before returning.
4. **Report + score** — `fanout` returns `(results, results_table)` and auto-records each author UNSCORED; **back-fill** `set_quality(r.agent_id, <0–5>, project=…, task_type="code", model=r.model)` per author (⚠️ never `record_run`, which no-ops; the flywheel check's Layer 2 warns on UNRECORDED runs, not unscored ones — `fanout` already records at dispatch, so nothing catches a missing score but you).
5. **Fix (YOU)** — review test-quality (would it fail if the behavior broke? real assertions, no mock-theater? could it fail in THIS environment at all?), fix issues, then `FABRIK_MUTMUT=1 python scripts/enforcement/check_mutation.py` on the **applied** code to confirm the tests kill mutants (advisory). You own final quality.

So "test every behavior" (the Behavior Contract) costs **cents + minutes**, not hours of hand-writing — the maintenance-burden objection dissolves. (Proven 2026-07-08: a `pick_models("review")` suggest run proposed the 3 behaviors of a `clamp(x,lo,hi)` for $0.0019 and recorded a flywheel row.)
-->
