# Review: HARD review corpus (`--hard`) + corpus-filter revert + retest wiring

Surface: f1d8f7bf8aea54d9ec6d008a04f5e710cc81255e + 8c5455ecf96384aefa9b17155df28def (git diff HEAD md5)
Scope: the staged working-tree diff vs HEAD — `scripts/kilo-benchmarks/microbench_review.py`
(HARD_CASES ×10 buggy/clean pairs · `_hard_truth_line` · `build_hard_corpus` · `_TASK_HARD`/`_task_for` ·
`persist_metrics(table=)` · `_measured_review_models(table=)` · `--hard` CLI wiring · the equivalence-filter
REVERT restoring the original 22-mutant corpus), `scripts/kilo-benchmarks/rank_task_subagents.py`
(`_full_review_hard_results_table` · retest-notice status update · resolution caveat),
`scripts/kilo-benchmarks/tests/test_microbench_review.py` (7 hard-corpus soundness tests; filter tests
removed by the revert), `CHANGELOG.md`, `docs/reference/kilo/TASK_SUBAGENT_SELECTION.md` (regenerated).
Callers/callees in scope: `grade()`/`report()`/`persist()`/`record_flywheel` (corpus consumers),
`run()`/`run_direct()` (template dispatch), the ranker's render pipeline.

Prior report `2026-07-21-claude-p-scoring-review.md` covers a DIFFERENT surface (the plan-2 scoring diff,
10 passes, 54 findings) — this is a fresh review of the new hard-corpus work, not a re-adjudication.

## Rubric (verbatim summary, `python scripts/review_rubric.py --changed <paths>`)

Full captured output: `/tmp/claude-1000/-opt-fabrik/4e90716e-696b-4ddf-90ab-70e30f51f294/scratchpad/rubric_hard.txt`.
FLOOR: `core/35-security-auth` · `core/25-data-postgres` · `core/30-ops` · 12-Factor all twelve axes.
MATCHED: `core/10-python` (both scripts + tests) · `core/40-documentation` (CHANGELOG + selection doc) ·
`core/45-testing-strategy` (tests) · `core/62-using-subagents` (rank_task_subagents.py).

## Coverage Checklist

| # | Class | Verdict | Evidence |
|---|---|---|---|
| 1 | core/35-security-auth | CLEAN | no auth/JWT/session/CORS surface — a local CLI benchmark; the one injection-adjacent surface (f-string SQL table names) adjudicated under #11 → FIXED(1) |
| 2 | core/25-data-postgres | CLEAN | no Postgres surface in this diff; hard persistence is local sqlite (`model_review_hard_metrics`), the established tool-local pattern; the shared-postgres path (`record_agent_run`) is explicitly SKIPPED under `--hard` (finding 2's main()-level test proves it) |
| 3 | core/30-ops | CLEAN | no Docker/compose/ports/logs surface; no logfile writes (print/stderr only); no daemon/PID; no startup migrations (hard table CREATE runs inside an explicit persist call) |
| 4 | 12F (all twelve axes) | CLEAN | Pass 1 native Opus swept all twelve; only touchpoints: III (no new env/config — `_METRICS_TABLES` is code-internal routing, not config), XI (stdout only), X (tool-local sqlite cache, pre-existing pattern, not a backing-service substitution) |
| 5 | core/10-python (secrets/env/logging idiom) | CLEAN | no secrets/getenv changes; `exec()` restricted to fixed in-repo corpus source with S102 noqa + fresh namespace per call (Pass 2 Opus verified no reuse) |
| 6 | core/40-documentation (CHANGELOG/doc format) | CLEAN | CHANGELOG entry appended atop `[Unreleased]` (### heading, no skipped levels); selection doc regenerated via its generator, never hand-edited |
| 7 | core/45-testing-strategy (test quality) | FIXED(4) | findings 2, 5, and Pass-2's 3 test additions — all proven red-on-revert by Pass 2/3 Opus (signature-match for the main()-level isolation test explicitly verified); 15 hard-corpus tests total |
| 8 | core/62-using-subagents (flywheel/routing) | CLEAN + FIXED(1) | `--hard` records NOTHING to the flywheel/routing prior by design (finding 2's test); pool finders dispatched via fanout in Pass 1 (recorded); Pass 2's pool attempt hit HTTP 402 (operator infra) — recorded honestly, native Sonnet substituted |
| 9 | fail-open vs fail-closed on every gate/guard | FIXED(3) | findings 3 (runtime kill-proof — build now fails closed on an unkillable case), 10 (opaque IndexError → contract ValueError), 4/9 (silent-ignore CLI paths → fail-loud `p.error`) |
| 10 | cost/quota/limit accounting edges | FIXED(2) | finding 4 (--hard --smoke would silently dispatch 480 live calls) + finding 11 (falsy-empty --models dispatched the full 24-model pool); no ①/②/③ accounting code touched by this diff |
| 11 | boundary/sentinel/prefix collisions | FIXED(1) + CLEAN | finding 1 (table-name allowlist now enforced, injection-shaped input raises); `hard:` item-id prefix verified consistent for mutants AND controls (finding 5's test); HARD_TABLE constant cross-checked against the ranker's reader (Pass 2 Sonnet column-count match, 16/17 exact) |
| 12 | behavior-without-a-test | FIXED(5) | findings 2, 4, 5, 9, 11 each closed with a dedicated regression test; suite 678 passed (+8 tests across the review) |
| 13 | hard-corpus soundness | CLEAN + FIXED(1) | all 10 pairs kill-proven on declared probes AND Pass-1 Opus fuzz (6–75% divergence, none equivalent); truth_line↔displayed-line 1-based consistency verified twice (Pass 1 + Pass 3); docstring contracts objective (finding 6's line-cite nuance REFUTED with the multi-cite grading proof); finding 3 made killability a BUILD invariant, not just a test |
| 14 | baseline isolation | CLEAN + FIXED(1) | main()'s --hard branch calls persist_metrics(HARD_TABLE) ONLY — persist()/record_flywheel unreachable (finding 2's main()-level test); resume-gate table-scoped both directions (tested); artifact stem separated; ensure_table writes zero rows |
| 15 | revert completeness | CLEAN | self-verified + Pass-1 Opus AST-segment compare: VICTIMS/build_corpus/_mutants_for/_apply_flip/_TASK/grade byte-identical to pre-filter 0c2332ed; zero filter residue symbols; 30-item corpus; only backward-compatible `table=` params differ |

## Pass Ledger

Pass 1 — finders: native Opus (all 6 committed classes: hard-corpus soundness incl. fuzz beyond
declared probes · baseline isolation · revert byte-identity vs 0c2332ed · SQL-injection surface ·
fail-open/closed on build · test quality) + pool fanout (2 units: hard-corpus block · isolation/
injection/revert diff) + self-verification (revert byte-identity independently confirmed: VICTIMS/
build_corpus/_mutants_for identical, zero filter residue, 30-item corpus) | found: 8 (4 → FIXED
[allowlist enforced not advisory; main()-level --hard isolation untested; runtime kill-proof not
enforced at build; --hard --smoke silent cost footgun] + 1 → FIXED [control-template test gap] +
3 → REFUTED [throttle exact-line ambiguity; _apply_flip "residue"; is_expired/smoke empty-corpus
speculation]) | fixed: 5 | → not done (changed code) — Pass 2 owed.

Pass 2 — finders: native Opus (verified all 5 Pass-1 fixes load-bearing: allowlist callers grepped
cross-repo, kill-proven hang/exception analysis, smoke-guard argparse behavior, isolation-test
signature-match confirmed red-on-break) + native Sonnet breadth (pool-substitute — the OpenRouter
pool returned HTTP 402 Insufficient credits on both units this round, an operator-level infra
outage; the mandatory pool layer was ATTEMPTED and is recorded here, with native Sonnet standing in
for differently-biased recall breadth) | found: 5 (3 → FIXED [--hard --report silent misreport;
_kill_proven opaque IndexError; falsy-empty --models dispatching the full pool] + 2 → REFUTED
[HARD_CASES key-schema — already fail-loud at build; filter-removal "regression" — the operator's
explicit recorded directive]) | fixed: 3 | → not done (changed code) — Pass 3 owed.

Pass 3 — finders: native Opus (verified all 3 Pass-2 fixes: --report guard placement, _fn 0-and->1
coverage, _models_or_pool early-exit ordering across all three branches + resume-path intact +
smoke-slice preserved; all 3 new tests confirmed red-on-revert; final fresh sweep of the whole
changed surface) | found: 0 | fixed: 0 | → **QUIET ROUND — EXIT.** Pass 2 changed code, Pass 3 is
its confirming round and raised nothing on either verification or the fresh sweep. Minimum-two-
rounds satisfied (3 rounds), every checklist row adjudicated, last code-change re-checked, ledger
sums (13 findings → 8 FIXED + 5 REFUTED).

## Per-finding disposition ledger

1. (pool·gemini) `# noqa: S608` comments claimed "fixed internal allowlist" but NO allowlist was
enforced — a future caller could interpolate any string into the SQL — **FIXED**: `_METRICS_TABLES`
frozenset + a real membership check raising `ValueError` at the top of both `persist_metrics` and
`_measured_review_models`; +`test_metrics_table_allowlist_is_enforced_not_advisory` (rejects an
injection-shaped table, accepts both legitimate ones).
2. (native Opus) the load-bearing `--hard` isolation guarantee lived only in `main()`'s untested
`if args.hard:` branch — a refactor dropping the guard would contaminate the routing prior/flywheel
with the suite green — **FIXED**: `test_main_hard_never_touches_baseline_or_flywheel` exercises
`main()` itself and asserts persist()=0 calls, record_flywheel()=0 calls, metrics→HARD_TABLE only.
3. (native Opus) `build_hard_corpus` enforced only the TEXTUAL one-line diff at runtime; killability
(the property whose absence invalidated the old corpus) was test-only — a future unkillable case
would dispatch live — **FIXED**: `_kill_proven()` executes every case's probes at BUILD, raising
`ValueError` on an undistinguishable pair; +`test_build_hard_corpus_refuses_unkillable_case`
(injects a semantically-identical fixture, asserts the build refuses it).
4. (native Opus) `--hard --smoke` silently ignored `--smoke` → a full 24-model × 20-item live run
(480 calls) when the operator asked for a cheap slice — **FIXED**: `p.error(...)` fail-loud guard;
+`test_main_hard_rejects_smoke`.
5. (native Opus) template test only covered a mutant item — a template divergence on clean controls
(a mutant-vs-control "tell") would pass — **FIXED**: `test_hard_template_applies_to_clean_controls_too`.
6. (native Opus) throttle case: a reviewer citing line 8 ("the if that should contain the update")
instead of line 10 (the misplaced `last_kept = t`) would be scored a miss — **REFUTED**: (a) the
buggy line is definitionally line 10 — the line whose placement/execution is wrong; line 8 is
correct code, and the prompt asks for lines that ARE buggy; (b) the grading is `truth_line in
flagged` — a reviewer citing BOTH 8 and 10 still scores a catch (extra mutant-item lines carry no
penalty; precision counts only control flags), so only a reviewer citing 8 ALONE misses, and that
cite is genuinely imprecise; (c) identical exact-line semantics grade the whole standard corpus.
7. (pool·gemini) `_apply_flip` is "residue of the removed filter" — **REFUTED**: `_apply_flip` is
the ORIGINAL operator-flip mutator's helper (present in 0c2332ed, called by `_mutants_for` at the
line the finder itself could see) — pre-existing, load-bearing, unrelated to the removed filter.
8. (pool·gemini) "`is_expired` may be missing from VICTIMS → `--smoke` returns an empty corpus" —
**REFUTED**: VICTIMS is byte-identical to the pre-filter commit (self-verified this pass) and
contains `is_expired`; the `--smoke` filter is unchanged original code.

8 findings → 5 FIXED + 3 REFUTED = 8. ✓

**Pass 2:**

9. (native Sonnet breadth) `--hard --report` accepted by argparse but silently ignored —
`report_stored()` reads ONLY the standard tables, so the operator would get standard-corpus numbers
presented as if they answered a --hard ask — **FIXED**: `p.error` fail-loud guard naming where hard
results actually render; +`test_main_hard_rejects_report`.
10. (native Sonnet breadth) `_kill_proven`'s snippet loader crashed with an opaque `IndexError` on a
snippet without exactly one top-level function, violating the module's own fail-loud-with-clear-
message contract — **FIXED**: explicit `ValueError("...exactly ONE top-level function...")`;
+`test_kill_proven_rejects_snippet_without_single_function`.
11. (native Sonnet breadth) `models = args.models or pick_models(...)` — an explicit-but-empty
`--models` ([] is falsy) silently dispatched the FULL 24-model pool; the new --hard branch had
duplicated the pre-existing pattern — **FIXED** at all three call sites via `_models_or_pool()`
(None-check, not truthiness) + an explicit empty-dispatch exit; +`test_main_explicit_empty_models_
dispatches_nothing`.
12. (native Sonnet breadth) HARD_CASES entries lack per-key schema validation (a missing "probes"
key raises a bare KeyError) — **REFUTED**: the failure already satisfies the fail-loud contract —
it raises AT BUILD TIME (never at dispatch) and the KeyError names the exact missing key; converting
the exception type would be cosmetic, not a behavior improvement.
13. (native Sonnet breadth) "the equivalent-mutant filter's removal from the STANDARD corpus is a
removed-behavior regression feeding model_task_baseline" — **REFUTED**: the removal was the
operator's explicit, recorded directive (2026-07-23: "my 57 tests were correct... revert the
filter", "I will not rescore") — comparability of the 61-model baseline REQUIRES the unchanged
corpus; the limitation is documented in the selection doc's resolution caveat, and the hard corpus
is the sanctioned discrimination instrument. Deliberate, documented design decision, not a defect.

13 findings → 8 FIXED + 5 REFUTED = 13. ✓
