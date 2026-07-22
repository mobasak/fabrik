# Review: claude -p first-class scoring — full cumulative surface

Surface: 448a17ebd8d0f22a601d04ae7c7cfb35704a7c34 + bd847e7b621803062b5de2627ad94cee (git diff HEAD md5)
Scope: `scripts/kilo-benchmarks/{build_task_baselines.py, claude_p.py, claude_price_ratios.json,
derive_cost.py, microbench_coding_direct.py, microbench_review.py, rank_task_subagents.py,
tests/test_claude_p*.py, tests/test_derive_cost.py}` + `CHANGELOG.md` — committed `a6b12e73..HEAD`
(Phases A/B/C + 3 rounds of prior chat-only review-fixes, never persisted to a file under the old
contract) + the currently staged, uncommitted diff (resumability `--fresh`/`_measured_review_models`,
and real ② `amortized_cost` token persistence + display).

No prior persisted review report exists for this scope (`docs/development/reviews/` had none matching)
— this is a fresh full review, not a re-adjudication.

## Rubric (verbatim, `python scripts/review_rubric.py --changed <paths>`)

See `/tmp/claude-1000/-opt-fabrik/4e90716e-696b-4ddf-90ab-70e30f51f294/scratchpad/rubric.txt` for the
full captured output. Summary of classes armed: FLOOR (`core/35-security-auth`, `core/25-data-postgres`,
`core/30-ops`, 12-Factor all 12 axes) + MATCHED (`core/10-python`, `core/40-documentation`,
`core/45-testing-strategy`, `core/62-using-subagents`).

## Coverage Checklist

| # | Class | Verdict | Evidence |
|---|---|---|---|
| 1 | core/35-security-auth (auth/JWT/sticky-sessions/CORS) | CLEAN | no auth/JWT/session/CORS surface anywhere in this diff — a local CLI benchmark tool, no FastAPI/web layer |
| 2 | core/25-data-postgres (migrations/FK/sessions) | CLEAN | the only postgres touchpoint is `record_agent_run`→`subagent_runs` (unchanged schema); this diff's own DB work is local sqlite (`model_review_metrics`), not Postgres |
| 3 | core/30-ops (Docker/logs/PID/migrations-at-startup) | CLEAN | no Dockerfile/compose touched; no logfile writes (native Opus + pool both confirmed print()-only); no PID/daemon; the sqlite ALTER runs inside an explicit `persist_metrics()` call, never at import/module-load |
| 4 | 12F-I codebase | CLEAN | single codebase, no cross-app sharing |
| 5 | 12F-II deps | CLEAN | `npx @anthropic-ai/claude-code` is the operator's existing on-box CLI (pre-existing dependency), not newly introduced; no Dockerfile in scope |
| 6 | 12F-III config/secrets | FIXED(1) — `_SUBSCRIPTION_USD_PER_ACCOUNT` now `os.getenv("CLAUDE_MAX_PRICE_USD", "200.0")` (derive_cost.py). REFUTED(1) — `Path.home()/.claude/...` paths: already overridable via optional fn params (`usage_history_path`/`accounts_dir`/`statusline_path`); 3rd-party-tool state discovery, not app config | no hardcoded secrets anywhere (pool-confirmed clean on claude_p.py) |
| 7 | 12F-IV backing services | CLEAN | no DSN/backing-service swap logic touched |
| 8 | 12F-V build/release/run | CLEAN | no release/build process touched |
| 9 | 12F-VI processes/sticky-sessions | CLEAN | no session/process-affinity logic |
| 10 | 12F-VII port binding | CLEAN | no ports/network binding |
| 11 | 12F-VIII concurrency/daemonize | CLEAN + FIXED(1) — no daemon/PID; but a real 2-way account-rotation race in claude-code/* concurrent dispatch (native Opus finding) → tightened `min(concurrency,2)`→`min(concurrency,1)` in BOTH `microbench_review.py:590` and `microbench_coding_direct.py:288` (verified: fixed build never trips `spent` for claude-code/*, so cancellation logic — and thus `test_code_cost_cap_ignores_claude_spend` — is unaffected/strengthened by tighter concurrency) | |
| 12 | 12F-IX disposability/idempotency | CLEAN | `persist_metrics` uses `INSERT OR REPLACE` (idempotent re-persist); this diff's whole point (resumability) is explicit interrupt-safety |
| 13 | 12F-X dev/prod parity | CLEAN | local sqlite `kilo_agents.db` is a pre-existing, established dev-cache pattern for this tool (not a new prod-service substitution) |
| 14 | 12F-XI logs | CLEAN | no `logging.FileHandler`/`*.log` writes; only `print()` + explicit JSON/sqlite data artifacts (not logs) |
| 15 | 12F-XII admin/migrations | FIXED(1) — the `PRAGMA table_info` + conditional `ALTER TABLE ADD COLUMN` in `persist_metrics()` (microbench_review.py:797-800) is check-then-act, not atomic; a genuinely-simultaneous double-invocation could hit `duplicate column name` → wrapped in `try/except sqlite3.OperationalError`, re-raising anything except that specific message | not a startup/import-time migration (runs only inside an explicit persist call, single-operator sequential tool) — native Opus called it "non-issue... justified" but conceded not-impossible; fixed defensively since cheap |
| 16 | core/10-python (secrets/logging/env patterns) | CLEAN | pool-confirmed no secrets/logging violations in claude_p.py; `os.getenv` used correctly post-fix |
| 17 | core/40-documentation (CHANGELOG format) | CLEAN | CHANGELOG entries use `###` headings, fenced/plain prose, no skipped heading levels |
| 18 | core/45-testing-strategy (Behavior Contract, mock policy) | CLEAN + FIXED(1) — pool confirmed no tautological tests, no mock-only assertions; but `report()`'s new `②total$` column had ZERO test coverage (self-verified: `grep` found no test calling `report()` at all) → added `test_report_prints_amortized_column_for_claude_not_for_or` | zero-mock-DB policy targets FastAPI+Postgres backend tests — this tool's local sqlite test fixtures are the pre-existing, established pattern, not that surface |
| 19 | core/62-using-subagents (record_agent_run/flywheel closure) | CLEAN | `record_flywheel`'s claude-code/* skip (microbench_review.py:696, positioned after the error-skip) is the only path calling `record_agent_run` for review; `microbench_coding_direct.py` records nothing (pre-existing); `microbench_judged.py` has zero claude references — no invariant expects 100% coverage of non-pool models in the flywheel; native Opus confirmed no other leak path |
| 20 | fail-open vs fail-closed on every gate/guard | CLEAN + FIXED(5) — Pass 1-3's initial trace held; Passes 6-9 found the coding harness's `--all` batch loop had FOUR uncaught-exception paths that fail-OPEN into a whole-run crash (grade()'s LCB subprocess, persist_metrics/persist_baseline's sqlite writes, plus the resume-gate silently treating a partial write as complete) — all now wrapped fail-closed (try/except + accurate spend accounting + a real intersection-based resume check); Pass 10 re-verified all 5 fixes (incl. Pass 9's break→continue) compose correctly together with no interaction gap | see disposition ledger findings 34/35/37/46/53 |
| 21 | cost/quota/limit accounting edges (unknown≠0, per-call vs batch) | CLEAN + FIXED(6) — Pass 1-3's ①/② accumulation + NULL≠0 + dotdir-skip fixes held; Passes 6-9 added: real OR spend correctly counted even when grading/persisting crashes (computed directly from `gens`, bypassing the never-built `CodingScore`); a fully-OR-priced batch on budget exhaustion no longer silently ends the whole run before a later free claude-code/* batch is reached (5 iterations narrowing to this exact edge); REFUTED(1) theoretical all-zero-tokens edge (unchanged from Pass 1-3) | see disposition ledger findings 34/37/53 |
| 22 | boundary/sentinel/prefix collisions (`claude-code/` literal) | CLEAN | all occurrences confirmed byte-identical by pool finder + native Opus independently across every pass through Pass 10; no real OpenRouter id could collide; an unknown claude-code/* id raises KeyError |
| 23 | behavior-without-a-test | FIXED(6) — see #18 (`report()`'s ②total$ column) + 5 new regression tests added across Passes 6-9 for the batch-loop fixes (each independently proven to fail pre-fix, pass post-fix) + 1 non-hermetic test fixed in Pass 8 (pinned `derive_cost.amortized_rate` instead of reading live machine state) | |

**Out-of-scope residual (bucket a — pre-existing, not introduced by this change):** coding harness's `cost_per_1k` includes billed cost of empty-but-charged OR calls in the numerator while `n_graded` excludes them from the denominator (native Opus finding, `microbench_coding_direct.py` `_bill`/`CodingScore`). Verified via `git show a6b12e73~1` this logic predates plan-2 entirely (Phase B only added the claude-code/* branch inside `_one`, never touched `_bill`/`n_graded`/`cost_per_1k`). Non-claude; fail-closed direction (could wrongly exclude a borderline model, never wrongly admit one). Not fixed here — out of this review's ownership.

## Pass Ledger

Pass 1 — finders: native Opus (fail-open/closed, cost/quota accounting, concurrency, flywheel closure,
migration safety, prefix collisions) + pool fanout (12-Factor breadth on claude_p.py/derive_cost.py,
test-quality audit, prefix-collision cross-check) + self-verification (report() test-coverage gap,
grade()/run_direct call-order trace, is_measured/fail-closed zero-token analysis, git-blame for
pre-existing scope) | found: 11 (6 → FIXED, 4 → REFUTED, 1 → pre-existing/out-of-scope) | fixed: 6 |
→ not done (changed code) — Pass 2 owed.

Pass 2 — finders: native Opus (confirming re-check of all 6 Pass-1 fixes, fresh from the current tree) +
pool fanout (independent re-check of FIX-1/3/5/4) + self-verification (reproduced the malformed-env-var
crash myself before either finder reported it; confirmed the ALTER-failure control-flow makes the
"schema mismatch" scenario impossible) | found: 6 (2 → FIXED [malformed-env-var crash — self-caught
first, confirmed by pool; test env-fragility — caught by native Opus], 1 → FIXED cosmetic [stale
concurrency-2 comment], 3 → REFUTED [schema/insert mismatch; `_measured_review_models` NoneType;
leftover `$/run` false-positive]) | fixed: 3 | → not done (changed code) — Pass 3 owed.

Pass 3 — finders: native Opus (fresh independent re-verification of FIX-A/B/C + a general sweep of the
whole `derive_cost.py` file) + pool fanout (2 units: general sweep of `derive_cost.py`, test-quality
audit of `test_derive_cost.py`) + self-verification (proved gemini's "pathologically tautological"
counter-example would actually be caught, via direct execution) | found: 7 (1 → FIXED [future-dated
key inflating the ② denominator — `k >= cutoff` alone never excludes `k > today`], 6 → REFUTED
[`amortized_cost`'s missing `usage_history_path` passthrough — self-resolved by the finder as
"design, not defect"; stale-but-real account subdirs — out of this tool's knowledge boundary, the
account-rotation system's concern, informational-only ②; "usage_history_path ignored" — self-corrected
by the finder mid-explanation; `AttributeError`-masking — already CLEAN-verified in Pass 1, same
except-tuple, same test; `test_amortized_rate_from_fixture` "tautology risk" — REFUTED, the "200.0 is
correct" property is independently covered by the `_env_float` tests, and gemini's own suggested fix
would reintroduce the Pass-2 regression; `test_amortized_cost_is_rate_times_total_tokens` "pathologically
tautological" — REFUTED, proved via direct execution that the finder's own hypothesized ×0 bug WOULD be
caught (0.000266 ≠ 0.0), contradicting their claim]) | fixed: 1 | → not done (changed code) — Pass 4 owed.

Pass 4 — finders: native Opus (holistic final sweep — verified the future-date fix incl. a UTC-vs-local
timezone edge case against live `usage-history.json`, + explicitly audited coding-vs-review token-capture
parity) + pool fanout (2 units: fresh adversarial read of `microbench_coding_direct.py`'s OR emptiness-check,
fresh read of `rank_task_subagents.py`'s shared preamble) | found: 5 (2 → FIXED [OR-path empty-response
check missing `.strip()` — a whitespace-only OR response was scored a pass@1 FAILURE(0) instead of being
excluded like the claude-code/* and review-harness paths; shared preamble unconditionally references a
`②total$` column the coding table doesn't render], 3 → REFUTED [local-tz future-cap boundary — proven
inert on live data, `keys > local-today: []`; cost-cap batch-resume "eff_cap never reduced for a
claude-only batch" — working as designed, claude ① is deliberately excluded from the real-$ cap;
speculative risk to a hypothetical future third results table — no such table exists]) | fixed: 2 | →
not done (changed code) — Pass 5 owed.

Pass 5 — finders: native Opus (fresh confirming re-verification of both Pass-4 fixes + a full adversarial
re-sweep of all 4 files, full test suite re-run) + pool fanout (2 units: fresh read of `derive_cost.py`,
fresh read of `microbench_review.py`) | found: 4 (0 → FIXED, 4 → REFUTED [`_load_ratios` "silently returns
malformed data" — already-documented fail-loud KeyError on a corrupted config file, not user input, working
as intended; `_is_iso_date`'s filtered keys "could raise uncaught KeyError downstream" — disproved by
direct trace: a non-dict `days` value raises `TypeError` on string-indexing, already inside the existing
`except (OSError, ValueError, TypeError, AttributeError)` tuple; `record_flywheel` "floods the flywheel
with quality-5.0 rows for a broken model" — disproved: it scores per-ITEM correctness (a model that fails
every mutant gets 0.0-scored rows for those, 5.0 only for genuinely-correct control items), which is a
separate concern from the aggregate `is_measured` display gate the finder conflated it with;
`median_latency`'s `s[len(s)//2]` "off-by-one" for even-length samples — a standard nearest-rank p50
convention, and the bias direction is conservative (can only make eligibility *harder* to clear via
`p50 ≤ 10s`, never easier) — not a defect]) | fixed: 0 | → per the termination contract, "found" counts every raised candidate including
later-refuted ones, so this round (found: 4, fixed: 0, all 4 REFUTED) is not yet the quiet exit —
Pass 6 owed.

Pass 6 — finders: native Opus (full fresh adversarial read of all 5 files + full test suite re-run) +
pool fanout (2 units: fresh read of `microbench_coding_direct.py`, fresh read of `rank_task_subagents.py`)
| found: 3 (2 → FIXED [outer `--all` batch loop `break`s the WHOLE run on OR-$ exhaustion, silently
skipping any LATER batch's claude-code/* members even though they cost $0 real OR spend and the same
carve-out is already enforced one level down inside `generate()` — found independently by BOTH native
Opus and the pool (deepseek), same root cause; `grade()`'s LiveCodeBench sandbox subprocess (`check=True`)
can raise uncaught, and `main()`'s batch loop had no try/except around it — a grading crash on one batch
crashed the entire multi-batch run, losing that batch's already-real-money-spent generations and every
later batch's chance to be measured — found by the pool (deepseek), a genuinely new class this round],
1 → REFUTED [gemini's full pass over `rank_task_subagents.py` — genuinely CLEAN, no new candidates]) |
fixed: 2 | → not done (changed code) — Pass 7 owed.

Pass 7 — finders: native Opus (verified Pass-6 fixes 34/35 fresh, hunted for the same crash-class
elsewhere, checked the review harness for parity) + pool fanout (2 units: fresh read of
`microbench_coding_direct.py`'s batch loop, fresh read of `microbench_review.py`'s dispatch/persist path)
| found: 7 (2 → FIXED [persist calls outside the Pass-6 try/except — a DB-lock crash on batch N still
killed the whole run; test-quality gap in the grading-crash regression test — asserted on batches
attempted but never on the `spent` accounting its own docstring claimed], 1 → OUT-OF-SCOPE [generate()
itself uncaught in the loop — low real-world blast radius, deterministic startup-only failure mode], 4 →
REFUTED [resume-skip/sidecar-guard claim — already-documented-correct design, already verified in Pass 5;
`TimeoutExpired` — self-refuted by the finder; `grade()`'s `JSONDecodeError` — already covered by the
Pass-6 fix; `_or_pricing`'s `JSONDecodeError` — repeats an already-disproven Pass-1 claim; review-harness
worker-thread speculation — heavily hedged, no concrete scenario]) | fixed: 2 | → not done (changed code)
— Pass 8 owed.

Pass 8 — finders: native Opus (verified Pass-7 fixes fresh, hunted for anything new across all 5 files) +
pool fanout (2 units: fresh read of `microbench_coding_direct.py`, fresh read of `derive_cost.py`) |
found: 7 (2 → FIXED [resume gate `_measured_models` only checked `model_coding_metrics`, not
`model_task_baseline` — a partial persist (metrics committed, baseline failed) would be silently and
permanently treated as measured on every future resume; a non-hermetic test asserted against the real
machine's live cost-model state instead of a pinned rate], 5 → REFUTED [pool's "derive_cost import could
ImportError" — unrealistic, it's a sibling file in the same repo; pool's "remove the future-date upper
bound" — would revert an already-triple-verified Pass-3 fix, and cited a file that doesn't exist in this
repo; pool's "sidecar collision under concurrent xdist execution" — no realistic concurrent-invocation
path for a manually-run CLI benchmark; pool's `usedPercent`-guard nitpick — self-refuted by the finder;
pool's "UNVERIFIABLE camelCase/snake_case mismatch" — two intentionally-distinct data sources by design,
already documented]) | fixed: 2 | → not done (changed code) — Pass 9 owed.

Pass 9 — finders: native Opus (verified both Pass-8 fixes fresh, full adversarial re-read of all 5 files,
full test suite) + pool fanout (1 unit: fresh read of `microbench_coding_direct.py`) | found: 2 (1 →
FIXED [the cost-cap carve-out's `break` on a fully-OR budget-exhausted batch stopped the whole scan,
starving a claude-code/* model in a later batch — 5th and narrowest fix in this same family across
5 rounds], 1 → REFUTED [pool's pass predated the fix — stale by a parallel-dispatch timing artifact,
plus fabricated line numbers not matching the real file]) | fixed: 1 | → not done (changed code) —
Pass 10 owed.

Pass 10 — finders: native Opus (verified fix 53 fresh, verified all 5 fixes in this batch-loop family
compose correctly together, full adversarial re-read of all 5 files, full test suite) + pool fanout (1
unit: fresh read of `microbench_coding_direct.py` with the current post-fix content, verifying the same
5-fix composition independently) | found: 0 (both native Opus and pool returned genuinely CLEAN — no
candidates raised, none refuted, nothing to adjudicate) | fixed: 0 | → **QUIET ROUND.** Pass 9 fixed
something (finding 53), so per the termination contract Pass 10 had to be a real confirming round, not
the exit itself — it was, and it came back clean on both layers. `found: 0, fixed: 0` on this round,
satisfying the exit condition.

**Pass Ledger summary:** 10 passes, 54 dispositioned findings (19 FIXED + 33 REFUTED + 2 OUT-OF-SCOPE),
every finding terminated FIXED/REFUTED/OUT-OF-SCOPE (none left UNCHECKED or silently dropped). The
last code-changing pass (9) was followed by a confirming round (10) that re-verified its fix plus the
full composition of the 5-fix family spanning passes 6-9, and Pass 10 found nothing new on either the
native or pool layer. Minimum-two-rounds and quiet-final-round both satisfied.

## Per-finding disposition ledger

1. Hardcoded `_SUBSCRIPTION_USD_PER_ACCOUNT` (200.0) not env-overridable — **FIXED**: `os.getenv("CLAUDE_MAX_PRICE_USD", "200.0")` (derive_cost.py).
2. Hardcoded `Path.home()/.claude/...` paths — **REFUTED**: already overridable via optional fn params; 3rd-party tool state discovery, not app config (12F-III targets deploy-varying config, not a fixed known dotfile location).
3. Non-atomic `write_cost_sidecar` write claimed to "crash" the reader — **REFUTED**: `rank_task_subagents.py:453` `except (OSError, ValueError, TypeError, AttributeError): return []` — `json.JSONDecodeError` IS a `ValueError` subclass (verified via `issubclass()`), so a torn write fails soft, never crashes.
4. `_full_review_results_table`/`_claude_p_preamble` "test-only method" exposure — **REFUTED**: both are genuinely called by `render()` in production; direct unit-testing of private-but-production-used helpers is legitimate white-box testing.
5. `report()`'s new `②total$` column has zero test coverage — **FIXED**: added `test_report_prints_amortized_column_for_claude_not_for_or`.
6. Theoretical measured-claude-row-with-all-zero-tokens showing a fabricated `$0` — **REFUTED**: `is_measured` requires ≥3 mutant + ≥1 control successful calls; `claude_p.py` fail-closes on `output_tokens<=0`; every live-verified call this session showed 18k-44k+ cache tokens — practically impossible.
7. `persist_metrics`'s PRAGMA-then-ALTER TOCTOU race under genuinely-simultaneous double-invocation — **FIXED**: wrapped in `try/except sqlite3.OperationalError`, swallowing only `"duplicate column name"`.
8. `②$/run` label beside `①$/1k` invites scale-misreading (~6 orders of magnitude under one loose header) — **FIXED**: renamed to `②total$` in both CLI `report()` and ranker table; strengthened footer/preamble text in both files to state ② is a lump-sum total, not a rate.
9. Coding `cost_per_1k` numerator/denominator asymmetry on chatty-empty OR calls — **OUT-OF-SCOPE** (bucket a): confirmed pre-existing via `git show a6b12e73~1`, predates plan-2, not touched by any commit in this scope.
10. Concurrent `claude -p` subprocess account-rotation race at conc=2 — **FIXED**: tightened to conc=1 for claude-code/* dispatch in both `microbench_review.py` and `microbench_coding_direct.py`; verified `test_code_cost_cap_ignores_claude_spend`'s distinguishing logic is unaffected (the fixed build never trips `spent` for claude-code/*, so no cancellation occurs regardless of concurrency).
11. `manager-accounts` dir-count includes any subdir (stray dotdirs inflate `n_accounts`) — **FIXED**: filter `not p.name.startswith(".")`.

11 findings → 6 FIXED + 4 REFUTED + 1 OUT-OF-SCOPE = 11. ✓

**Pass 2:**

12. Malformed `CLAUDE_MAX_PRICE_USD` env var crashes the whole module at import time (`float(os.getenv(...))` with no guard) — **FIXED**: self-caught during my own fix-verification (before either finder reported it — reproduced `CLAUDE_MAX_PRICE_USD=garbage python -c "import derive_cost"` → `ValueError`), confirmed independently by pool finder deepseek-v4-flash; added `_env_float()` helper (catches `ValueError`/`TypeError`, falls back to default) + 3 regression tests.
13. `persist_metrics` "schema/insert column-count mismatch on ALTER failure" — **REFUTED**: the guard's `raise` (for anything but `"duplicate column name"`) propagates through the outer `try/finally`, exiting `persist_metrics()` entirely — the `for s in scores.values(): ... INSERT` loop is provably unreachable after any real ALTER failure (quoted the exact control flow).
14. `_measured_review_models` "potential NoneType loop" on an empty query result — **REFUTED**: `fetchall()` never returns `None` (only a list, possibly empty); the pool finder that raised this debunked it itself mid-explanation.
15. "Leftover `$/run` reference" at `rank_task_subagents.py:520` after the ② rename — **REFUTED**: that `$/run` is ①'s own distinct, pre-existing column (`REVIEW_MAX_RUN_COST` gate description / `_full_coding_results_table` / shortlist tables) — never the rename's target; only the ②-prefixed `②$/run` was renamed, and it is (verified: repo-wide grep for the old string returns zero hits).
16. `test_amortized_rate_from_fixture`/`test_amortized_rate_ignores_non_date_keys` hardcode `200.0`, but `_SUBSCRIPTION_USD_PER_ACCOUNT` is now env-overridable — a real operator env (`CLAUDE_MAX_PRICE_USD` set) would spuriously fail these tests — **FIXED**: native Opus reproduced live (`CLAUDE_MAX_PRICE_USD=300 pytest` → FAILED); both tests now assert against the live `dc._SUBSCRIPTION_USD_PER_ACCOUNT` constant instead of a hardcoded literal (re-verified: the exact reproduction scenario now passes, 17/17).
17. Stale comment "concurrency capped to 2" / "keep the 2 workers busy" in `test_code_cost_cap_ignores_claude_spend` after the conc 2→1 fix — **FIXED** (cosmetic): updated wording to conc=1 + "5 not-yet-started futures".

17 findings → 9 FIXED + 7 REFUTED + 1 OUT-OF-SCOPE = 17. ✓

**Pass 3:**

18. `amortized_cost` has no `usage_history_path` passthrough (asymmetric with `api_equiv`'s `ratios_path`) — **REFUTED**: self-resolved by the raising finder itself ("design issue, not necessarily a bug... intentional"), the docstring already documents `ratios_path`'s symmetry-only role.
19. Stale-but-real (non-dot, never removed) account subdirectories could inflate `n_accounts` — **REFUTED**: out of this benchmark's knowledge boundary — account lifecycle belongs to the account-rotation system, not this cost model; live-verified 3 real, current account dirs exist (`can`/`mob`/`ob`-ocoron-com-s-organization); low blast radius (②/context-only, never routing).
20. `amortized_rate`'s `usage_history_path` param supposedly ignored — **REFUTED**: self-corrected by the raising finder mid-explanation ("I misread earlier. This is correct.").
21. `AttributeError` in `amortized_rate`'s except-tuple could "mask errors" — **REFUTED**: already CLEAN-verified in Pass 1 (same except-tuple, same guard, same `test_amortized_rate_malformed_history_fails_soft` regression test) — a malformed non-object top level / null day / null byModel entry fails soft to the anchor by design, never masks a real crash.
22. Future-dated key (`2099-01-01`, clock-skew source) inflates the ② denominator — `k >= cutoff` alone never excludes `k > today` — **FIXED**: window now `cutoff <= k <= today_iso`; +1 regression test (`test_amortized_rate_ignores_future_dated_keys`).
23. `test_amortized_rate_from_fixture` "tautology risk" (asserting against the live constant instead of a hardcoded `600.0`) — **REFUTED**: the "200.0 is the correct default" property is independently covered by `test_env_float_falls_back_on_malformed_value`/`test_env_float_parses_real_override` (same file); the finder's own recommended "fix" (hardcode `600.0/1350`) would reintroduce the exact env-fragility regression Pass 2 fixed and Pass 3's native Opus round confirmed correct.
24. `test_amortized_cost_is_rate_times_total_tokens` "pathologically tautological" (claimed it would pass even if `amortized_cost` always returned `amortized_rate()*0`) — **REFUTED**: proved false via direct execution — `dc.amortized_rate()*0 == 0.0` while `expected ≈ 0.000266`, so the test's own assertion (`0.000266 != 0.0`) would fail under that exact hypothesized bug, directly contradicting the finder's claim.

24 findings → 10 FIXED + 13 REFUTED + 1 OUT-OF-SCOPE = 24. ✓

**Pass 4:**

25. `microbench_coding_direct.py`'s OR-path empty-response check (`if r.error or not r.text:`) lacked
`.strip()`, unlike the review harness and the claude-code/* path in the same file — a whitespace-only OR
response slipped past and was scored a pass@1 FAILURE(0) instead of being excluded, biasing OR models
down vs claude-code in the same leaderboard — **FIXED**: `not (r.text or "").strip()`.
26. `rank_task_subagents.py`'s shared `_claude_p_preamble()` unconditionally referenced a `②total$`
column that `_full_coding_results_table()` doesn't render (the coding harness never persists per-row raw
tokens) — **FIXED**: added `has_amortized_col: bool = True` param, coding table's call site passes `False`.
27. `derive_cost.amortized_rate`'s future-date cap uses local-tz `date.today()`, theoretically vulnerable
if a box behind UTC reads a UTC-dated history near midnight — **REFUTED**: proven inert on live data
(`keys > local-today: []`); a genuine boundary condition but not a live defect.
28. Cost-cap batch-resume "`eff_cap` never reduced for a claude-only batch" — **REFUTED**: working as
designed, `_real_spend()` deliberately excludes claude-code/* from the real-$ cap (the whole point of the
①-excluded carve-out); not a bug.
29. Speculative risk that a hypothetical future third results table might reuse the preamble incorrectly —
**REFUTED**: no such table exists; not actionable.

29 findings → 12 FIXED + 16 REFUTED + 1 OUT-OF-SCOPE = 29. ✓

**Pass 5:**

30. `derive_cost._load_ratios` "silently returns malformed data" on a corrupted pricing file — **REFUTED**:
already-documented fail-loud `KeyError` on a corrupted config file (not user input) is the intended
behavior; the docstring already states "Raises KeyError for an unpriced model."
31. `_is_iso_date`'s filtered keys "could raise an uncaught `KeyError`" if `days` were a non-dict —
**REFUTED**: disproved by direct trace — a non-dict `days` value raises `TypeError` on string-indexing,
already inside the existing `except (OSError, ValueError, TypeError, AttributeError)` tuple.
32. `record_flywheel` "floods the flywheel with quality-5.0 rows for a broken model" — **REFUTED**:
disproved — it scores per-ITEM correctness (a model failing every mutant gets 0.0-scored rows for those,
5.0 only for genuinely-correct items), a separate concern from the aggregate `is_measured` display gate
the finder conflated it with.
33. `median_latency`'s `s[len(s)//2]` "off-by-one" for even-length samples — **REFUTED**: a standard
nearest-rank p50 convention; the bias direction is conservative (can only make the `p50 ≤ 10s` eligibility
gate *harder* to clear, never easier) — not a defect.

33 findings → 12 FIXED + 20 REFUTED + 1 OUT-OF-SCOPE = 33. ✓

**Pass 6:**

34. Outer `--all` batch loop `break`s the WHOLE run once OR $ budget is exhausted, silently skipping any
LATER batch's claude-code/* members even though `generate()` already deliberately excludes claude spend
from the cap one level down — found independently by BOTH native Opus and pool (deepseek), same root
cause — **FIXED**: the loop now drops only a batch's OR-priced members once `rem < 0.05`, keeps
dispatching any claude-code/* remainder (with `cost_cap=inf`, since it can't spend anyway), and only
truly `break`s once a batch has no claude-code/* left either. +regression test
`test_all_batch_loop_still_measures_claude_after_or_budget_exhausted` (proven to fail pre-fix).
35. `grade()`'s LiveCodeBench sandbox subprocess (`_run_lcb`, `subprocess.run(..., check=True, timeout=…)`)
can raise `CalledProcessError`/`TimeoutExpired`; `grade()`'s own `try/finally` only cleans up temp files
and re-raises, and `main()`'s batch loop had no wrapper around the `grade()` call — a grading crash on
ONE batch crashed the entire `--all` run, losing that batch's already-real-money-spent generations (never
persisted, since `persist_metrics`/`persist_baseline` come after `grade()`) AND every later batch's chance
to be measured — found by pool (deepseek), a genuinely new class this round — **FIXED**: wrapped the
`grade()` call in `try/except`, logging + `continue`-ing to the next batch on failure, while still
counting that batch's real OR spend (computed directly from `gens`, bypassing the never-built
`CodingScore`) against `spent` so a repeat grader failure can't silently blow past `eff_cap`.
+regression test `test_all_batch_loop_survives_a_grading_crash` (proven to fail pre-fix).
36. gemini's fresh full pass over `rank_task_subagents.py` — **REFUTED (genuinely CLEAN)**: no new
candidates; explicitly checked psql-row parsing, Bayesian shrinkage tier precedence, fail-closed gating,
claude-code/* routing exclusion, and div-by-zero/NaN guards.

36 findings → 14 FIXED + 21 REFUTED + 1 OUT-OF-SCOPE = 36. ✓

**Pass 7:**

37. `persist_metrics`/`persist_baseline`'s raw `sqlite3.connect` calls in the batch loop sat OUTSIDE the
Pass-6 `grade()` try/except — on the shared WSL box (daily pipeline + concurrent agents write the same
DB, per CLAUDE.md), a transient `database is locked` on batch N would still crash the whole `--all` run,
exactly the class Pass 6 set out to close but left one door open on — found by native Opus — **FIXED**:
wrapped both persist calls in their own try/except, logging + continuing to the next batch while still
counting the batch's real spend (`_real_spend(scores)`, since grading already succeeded) against the cap.
+regression test `test_all_batch_loop_survives_a_persist_crash` (proven to fail pre-fix).
38. `test_all_batch_loop_survives_a_grading_crash`'s docstring claimed the crashed batch's spend "must
still count against the cost-cap" but the test only asserted on `graded_batches`, never on `spent` —
would pass even if the spend-counting line were deleted — found by native Opus (test-quality) — **FIXED**:
rewrote to capture each `generate()` call's `cost_cap` and assert batch 2's reflects batch 1's $2.5
already deducted from the $3.0 total (`generate_calls[1][1] == pytest.approx(3.0 - 2.5)`).
39. `generate()` itself (line 780) is also outside any try/except in the batch loop — native Opus noted
this but assessed real-world blast radius as low: `generate()` only raises a deterministic startup guard
(no `_or_run` transport configured), which fails on batch 1 before any spend, not mid-run after partial
spend — **OUT-OF-SCOPE** (bucket b, low-severity/theoretical): the failure mode that makes finding 37 and
Pass-6 finding 35 concrete (a transient runtime exception losing already-spent money) doesn't apply here;
deferring further hardening of this specific line is a reasonable stopping point for this review's scope.
40. Pool + native both confirmed the review harness (`microbench_review.py`) is structurally single-batch
(no per-batch loop) and pure-Python `grade()` (no subprocess) — the "crash loses later batches" class
cannot occur there — **REFUTED (no defect)**: correctly scoped, no fix needed.

40 findings → 16 FIXED + 22 REFUTED + 2 OUT-OF-SCOPE = 40. ✓

41. Pool (deepseek) "resume-skip leaves `models` inconsistent → wrong sidecar guard, claude quota-draw
lost after a resume" — **REFUTED**: this is the exact, already-documented, already-verified-correct
design (comment at `microbench_coding_direct.py:825-826`; independently confirmed correct by native Opus
in Pass 5's ledger) — a resume that skipped every claude tier correctly does NOT overwrite ③ with a ~0
draw; `has_claude`/`q0` (line 713-714) are captured from the PRE-resume-skip list precisely so this
works. Not a bug.
42. Pool (deepseek) "`_run_lcb` `TimeoutExpired` not caught" — **REFUTED**: self-refuted by the finder
mid-explanation ("Actually, this is fine — the exception IS caught").
43. Pool (deepseek) "`grade()`'s `json.loads()` raises uncaught `JSONDecodeError`" — **REFUTED**: it's
inside the SAME `try` block as `_run_lcb` (`microbench_coding_direct.py:382-384`), so it propagates
through the identical path Pass-6 finding 35 already wrapped in `try/except Exception` — already covered.
44. Pool (gemini) "`_or_pricing`'s `json.load()` throws uncaught `JSONDecodeError`, not caught by
`except (urllib.error.URLError, OSError, ValueError, KeyError)`" — **REFUTED**: repeats an already-
disproven claim from Pass 1 finding 3 — `json.JSONDecodeError` IS a `ValueError` subclass (verified via
`issubclass()` in that pass), so it IS caught.
45. Pool (gemini) speculative "`_direct_call`/`_require_key`/worker-thread exception could crash the
whole review run, losing all results" — **REFUTED**: heavily hedged ("could theoretically", "if...
somehow"), no concrete reproducible scenario; matches native Opus's own Pass-7 assessment of this same
file (structurally single-batch, cents-scale, short run, not a regression from the Pass-6 change) —
not actionable.

45 findings → 16 FIXED + 27 REFUTED + 2 OUT-OF-SCOPE = 45. ✓

**Pass 8:**

46. `_measured_models` (the `--all` resume gate) only checked `model_coding_metrics`, not
`model_task_baseline` — if `persist_metrics` commits but `persist_baseline` then fails (both are separate
connections/commits; Pass 7's crash-isolation `except` now swallows this instead of crashing loudly), the
model is silently and PERMANENTLY treated as "measured" on every future resume, even though the routing-
source table (`model_task_baseline`, what `pick_models('code')` actually ranks on) never got its row —
found by native Opus — **FIXED**: `_measured_models` now requires a row in BOTH tables for the
window/date (intersection); existing test `test_measured_models_drives_resume` updated to call
`persist_baseline` too, +new regression test `test_measured_models_requires_both_metrics_and_baseline`.
47. `test_full_table_renders_real_amortized_cost_when_tokens_present` was non-hermetic — it called the
real `derive_cost.amortized_cost()` against the actual machine's live `~/.claude/.claude-manager/` state,
so the assertion `"$0.000" in row or "$0." in row` could fail on a box with genuinely low monthly
throughput (a high real rate would push the rendered figure past `$0.x`) — found by native Opus (test
quality) — **FIXED**: pinned `derive_cost.amortized_rate` to a fixed value via monkeypatch, asserting the
exact deterministic dollar figure instead.
48. Pool (deepseek) "unprotected `import derive_cost` in `main()` could `ImportError`-crash on a run with
no claude-code/* models, if `derive_cost` weren't installed" — **REFUTED**: `derive_cost.py` is a sibling
file in the same directory/repo as `microbench_coding_direct.py`, not a removable external dependency —
this scenario cannot occur in practice; also pre-existing (unrelated to any change in this review's scope).
49. Pool (gemini) "clock-skew underflow — remove the `k <= today_iso` upper bound" — **REFUTED**: this
would REVERT the Pass-3 fix (finding 22), which has since been independently re-verified correct THREE
times (Pass 3's own regression test, Pass 4 native Opus's live UTC-vs-local data check, Pass 5's clean
re-sweep); the finding also cites a file that doesn't exist in this repo (`claude_price_model.py` — the
real file is `derive_cost.py`), a strong signal this candidate isn't grounded in the actual code.
50. Pool (gemini) "sidecar persistence collision under multi-process/xdist execution" — **REFUTED**: no
realistic concurrent-invocation path exists — this is a manually-run operator CLI benchmark, not a
service invoked in parallel; the sidecar is display-only context for the ranker preamble, never a
scoring/routing input, so even a genuine race would only produce a stale ③ percentage in a table footer.
51. Pool (gemini) "`usedPercent: 0` `or 0.0` guard is redundant" — **REFUTED**: self-refuted by the finder
mid-explanation ("This is technically correct... the code is safe").
52. Pool (gemini) "UNVERIFIABLE camelCase (`cacheCreation`) vs snake_case (`cache_creation_input_tokens`)
mismatch" — **REFUTED**: two intentionally-distinct data sources by design — `api_equiv`'s `usage` dict is
the CLI's own per-call snake_case stats, `amortized_rate` reads a wholly separate third-party history file
(`~/.claude/.claude-manager/usage-history.json`) whose camelCase schema is already documented verbatim in
`derive_cost.py`'s own module docstring; neither function reads the other's field names.

52 findings → 18 FIXED + 32 REFUTED + 2 OUT-OF-SCOPE = 52. ✓

**Pass 9:**

53. The cost-cap carve-out's `break` on a fully-OR (empty-after-filter) budget-exhausted batch stopped
the ENTIRE scan, starving any claude-code/* model in a LATER batch — the sorted default doesn't guarantee
every claude id is contiguous with the first exhausted batch, so an intervening all-OR batch must be
skipped, not treated as the run's end — found by native Opus, same family as findings 34/35/37/46,
narrower each time — **FIXED**: `break` → `continue` (a one-time "cap reached" notice printed on first
exhaustion instead of per-batch); +regression test
`test_all_batch_loop_reaches_claude_past_an_intervening_all_or_batch` (3-model scenario: OR, OR, claude —
proven to fail pre-fix, dispatched stopped at batch 1 only).
54. Pool (deepseek) — **REFUTED (not applicable)**: the pool script read the file BEFORE the Pass-9 fix
landed (a parallel-dispatch timing artifact, same as Pass 6/7's earlier pool rounds), so it analyzed the
pre-fix `break` and called it "correct" — stale by construction. Its cited line numbers (1457-1630) also
don't correspond to the real file (863 lines total), a further sign this pass isn't grounded in the
actual current code. No actionable content.

54 findings → 19 FIXED + 33 REFUTED + 2 OUT-OF-SCOPE = 54. ✓
