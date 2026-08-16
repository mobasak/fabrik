# Command run-record protocol — review ledger

Operator complaints 2026-08-16, verbatim: "reviews are still taking 30 rounds" · "i want to
see each commands status pinned in each agents reply, as like total steps, and current step"
· "agents are still stopping without reaching a no ops pass or fully executing the commands
for no valid reason". Fleet-wide change (~46 repos): a per-session run record, a pinned
`RUN:` line, a Stop-hook 5th cause, and a persistent class ledger with a non-convergence
detector.

**The stakes set the review lens:** this decides whether an agent is ALLOWED TO STOP. A bug
traps every agent on the fleet — unable to end a turn, looping, burning the operator's
scarce quota. Fail-open is asymmetric by design: only a fresh, well-formed, positively
`running` record may block.

## Round 1 (2026-08-16)

Surface: commit d5fe8ef7 (13 files, +1056/−27; 103/103 re-verified by the orchestrator).
Finders: pool deepseek+gemini (core diff inline) + native opus (worktree fuzzing, real
concurrent processes, 2 mutants) + the orchestrator's own trap probe against the live hook.

Orchestrator probe first (before dispatch): no-record · corrupt · wrong-shape · `done` ·
`blocked` · stale-with-real-`updated_ts` all fail open; fresh-`running` blocks. One residual
seeded to the finders: a `running` record with no timestamp blocks forever.

| # | Finding | Source | Disposition |
|---|---|---|---|
| 1 | Duplicate `done`/`blocked` closes the RESUMED PARENT mid-plan — nested review pops back, a second `done` closes plan-exec at phase 2/5, `line` goes silent, the hook never blocks again for 3 remaining phases. The exact failure the nested stack was built to prevent, re-entered from another angle | opus CONFIRMED HIGH (probe) | **FIX (F-R1)**: `--command` identity required on close; already-closed = warned no-op |
| 2 | `updated_ts` type confusion — missing · NaN · Infinity · string · far-future ALL skip the staleness check and block forever, indistinguishable from a legitimate block (json.loads accepts NaN/Infinity by default). Generalizes the seeded residual into a class. Plus `COMMAND_RUN_STALE_H=0` disables the escape hatch entirely | opus CONFIRMED + both pool | **FIX (F-R2)**: freshness must be POSITIVELY proven (finite numeric, skew-clamped) else fail open; ≤0 stale-h fails open |
| 3 | Unlocked read-modify-write in `round` — 20 concurrent calls on one session id recorded 6; subagents share the parent session id, so a class opened by one vanishes and a review can read CLEAN with a class unswept | opus CONFIRMED (real processes) | **FIX (F-R3)**: flock every mutating subcommand (assignments.lock idiom) |
| 4 | Session-id sanitization collides distinct raw ids (`abc.xyz` / `abc xyz` → one file) → an innocent session blocked by another's record. ADJACENT pre-existing: `_counter_path`/`_baseline_path` interpolate sid UNSANITIZED — a `/` crashes into the outer except and fails the WHOLE hook open, disabling all five causes | opus CONFIRMED (probe) | **FIX (F-R4)**: hash-suffix on divergence + sanitize the two pre-existing paths (declared) |
| 5 | Mutant survived: dropping `not open_c` from the terminal condition passes all 103 tests — no test pairs findings==0 with an open class | opus (own mutant) | **FIX (F-R5)**: add the pairing test, re-kill the mutant |

Verified correct, no action: the escape hatch/counter budget (5 sequential live Stop
invocations: block 1/3, 2/3, 3/3, warn-through, then a fresh streak — and reset-on-resolve
confirmed) · 3/4/5-slot counter-file tolerance · the trailing-window convergence heuristic
(advisory-only; a false negative cannot block) · empty-ledger-never-terminal (intentional,
already tested).

Round 1 verdict: NOT CLEAN — F-R1..F-R5 dispatched. Round 2 follows.
