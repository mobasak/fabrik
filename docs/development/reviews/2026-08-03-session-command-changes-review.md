# /fabrik-review — session command-file changes (HUB, fleet lens)

Surface: HEAD=7b23f649 diff-md5=806b6e2d09ed9f285a60124e26711d19
Scope: `git diff a69ee8f0^..HEAD -- commands/` — the new `_fragments/autonomy-run.md`
+ its wiring (`fabrik-user-test`, `fabrik-service-test`, `fabrik-execute-plan`,
`assemble_commands.py` PARAMS) + the proof-standard changes across the code-fixing
review commands (`fabrik-review`, `fabrik-repo-review`, `fabrik-generate-tests`).
Rubric: `review_rubric.py --changed <the command paths>` (FLOOR injected; code
mandates mostly N/A to governance prose — adjudicated below).

Prior review context (this session, native Opus): autonomy-run fragment through 3
passes (a safety hole caught + fixed); proof-standard through 4 passes; execute-plan
citation wiring reviewed alongside the check_convergence gate (4 passes). This is the
formal confirming pass over the committed result.

## Coverage Checklist (HUB / fleet lens)

| class | verdict |
|---|---|
| cross-fragment contradiction (autonomy-run ↔ term-coverage/questionbar) | FIXED(1) — #1: term-coverage now carves out the safety HARD STOP early-exit |
| fleet backward-compat (a project without feature X; a headless vs GUI command) | FIXED(2) — #2/#3: genericized Playwright/Maestro + mail-catcher surface-leaks in the shared fragment |
| false-positive / cries-wolf on a legitimate pattern | REFUTED(1) — #5: proof-standard is scoped under the FIXED bullet, about reproducing THE finding, not any green test |
| rule-pack / fragment contradiction (one fights another) | FIXED(1) — #4: tightened "exactly two" so a per-finding pause is not read as a whole-run halt |
| render integrity (unexpanded tokens · orphaned include · PARAMS drift) | CLEAN — grep 0 unexpanded tokens; no questionbar orphan; PARAMS supply exactly the used keys (verified by finder + `--check`) |
| fail-open vs fail-closed on every gate/guard the prose describes | CLEAN — autonomy-run fails safe (stop-only-on-absolute-must + HARD-STOP override); no fail-open path |
| HARD STOP preservation (prod data, destructive action, safety > autonomy) | CLEAN — "NEVER run against production" intact in both; autonomy-run reinforces, now reciprocated in term-coverage |
| behavior-without-a-test (assemble_commands PARAMS / render) | CLEAN — render/PARAMS covered by the corpus-match gate + `assemble_commands.py --check` |
| FLOOR: security-auth / data-postgres / ops / 12-factor | CLEAN (N/A) — governance prose changes; no code/auth/data/ops surface touched |

## Pass Ledger

| Pass | found | fixed | note |
|-----:|------:|------:|---|
| 1 | 5 | 4 | native Opus (fleet lens) — #1 term-coverage safety carve-out · #2/#3 surface-leak genericized · #4 exactly-two tightened · #5 refuted (scoped). Pool breadth ran (deepseek-v4-flash) → empty/zero-signal, recorded. |
| 1b | — | 1 | self-review during Pass-2 wait: #4's rewrite had overcorrected into an incoherent "Only ONE thing halts the run" with no referent — fixed to "the safety HARD STOP above is the only mid-loop whole-run halt; the two absolute-musts each act per-finding or pre-loop". |
| 2 | 1 | 1 | native Opus confirming — all fixes hold; one low residual: term-coverage's line-21 absolute "ONLY non-quiet stop" not reconciled with the line-23 safety exception (for the code-review consumers where autonomy-run is absent). Fixed: scoped "ONLY" to "a review FINDING may cause" + back-pointer to the safety exception. |
| 3 | 0 | 0 | native Opus confirming — **CLEAN**. term-coverage 21/23 coherent standalone (code-review) + cross-coherent with autonomy-run; safety-HARD-STOP cross-reference accurate; no new gap from narrowing "ONLY". Nothing to report. |

**CONVERGED** — Pass 3 raised `found: 0, fixed: 0` (a genuine quiet round following the last code-changing
pass). Every Coverage Checklist class is CLEAN / FIXED / REFUTED; every finding terminated FIXED or REFUTED;
mechanical gate green (`final_gate.py --lean --check` → success). Pool breadth ran once (empty/zero-signal on
prose, recorded honestly); the native Opus finder was the authoritative pass across all three rounds.
