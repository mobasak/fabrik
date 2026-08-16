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

## Round 2 (2026-08-16) — orchestrator verification, declared

Surface: fixup commit 0fcc112f (11 files, +610/−140; 129/129 re-run by the orchestrator =
103 + 26 new). Because this is the last gate before ~46 repos, the orchestrator re-ran the
decisive probes FIRST-HAND rather than accepting the report.

**Trap matrix — 14 cases that MUST fail open, 1 that must block:**

```
no record · corrupt json · non-dict · no updated_ts · NaN · Infinity · string ts ·
bool ts · far-future (+10d) · stale 30h · STALE_H=0 · STALE_H=-5 · done · blocked
   -> ALL fail open
fresh running record -> BLOCK
TRAPS REMAINING: 0 | legitimate block works: True
```

**F-R1 (the HIGH) re-probed on fixed code:** plan-exec 5 phases → nested review → review
`done --command fabrik-review` pops back (`RUN: /fabrik-execute-plan · phase 2/5`) → a
DUPLICATE `done --command fabrik-review` is REFUSED (rc 1) naming live-vs-passed, and the
parent stays pinned and running. Exit codes: mismatch 1 · correct 0 · already-closed 0
(warned no-op).

**F-R3 re-probed:** 20 real concurrent `round` processes on one session id →
`rounds recorded: 20 | classes recorded: 20` (was 6/20 before the flock).

**F-R4 re-probed:** `abc.xyz` → `abc_xyz-375419f7.json`, `abc xyz` → `abc_xyz-8ec6e4d5.json`
— distinct files; uuid-shaped ids keep plain filenames (no live record renamed). The
pre-existing `_counter_path`/`_baseline_path` unsanitized-sid crash (which failed the WHOLE
hook open, disabling all five causes) is fixed under the same helper, with a cross-file test
asserting the two deliberate `_safe_sid` copies agree.

**F-R5:** the previously-surviving mutant (`not open_c` dropped) now dies on
`test_zero_findings_with_a_still_open_class_is_not_terminal`.

Coder honesty noted and accepted: under the `math.isfinite` mutant the bool/±Infinity shapes
still pass (they trip the staleness/skew branches independently) — only NaN strictly requires
the finite check. The coder reported this rather than manufacturing a test to hide it.

Round 2 verdict: **CLEAN** — merge.

## CLOSE

2 rounds, 5 fixes, 26 tests added (103 → 129). Review yield, all probe-backed: a duplicate
close that silently DISARMED the stop-gate mid-plan (the exact failure the design exists to
prevent, re-entered from another angle) · a five-shape timestamp class that blocked agents
forever with no way to age out · measured ledger data loss under concurrency · a
cross-session record collision · and a pre-existing hook crash that had been failing all five
causes open on odd session ids. Final surface: worktree commits d5fe8ef7 + 0fcc112f
squash-applied to master as ONE commit. Fleet blast radius is intended: the Stop hook, both
CLAUDE.md files and the manifest are governance-sync triggers, so this distributes to ~46
repos on the merge commit; the three edited command sources need a render from MERGED master
(never from a worktree — the renderer prunes).

