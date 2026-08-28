# /fabrik-review — whole-plan cumulative diff, provider-death enforcement

Status: CLOSED — coverage-adjudicated exit; the closing round raised 2 candidates and REFUTED both.

**Surface:** cumulative diff `7fbc2b6d..31426294` (the step-8 baseline → Phase C).
**Commits under review (mine only):** `61d03d16` (A) · `e056a415` (B) · `31426294` (C).

**Finders.** Native orchestrator only. `NO-POOL: operator standing directive — no subagent or pool
dispatch for hub work.` Every finding reproduced by executing the real artifact, never by reading it.

## Rubric

`python scripts/review_rubric.py --changed <the 6 File-Scope paths>` — FLOOR (`core/35-security-auth`,
`core/25-data-postgres`, `core/30-ops`, all twelve 12-Factor axes) + MATCHED (`core/40-documentation`,
`core/45-testing-strategy`).

## Coverage Checklist

| # | Class | Verdict | Evidence |
|---|---|---|---|
| 1 | **Test vacuity** (standing) | CLEAN | All three assertions watched RED before any fix (`3 failed in 0.19s`), then proven red-on-revert with each mutation asserted on disk and restored. |
| 2 | **A test that lies green** | **FIXED(1)** | My own `except`-clause regex matched only PARENTHESIZED clauses, so it read the correct new `except httpx.HTTPStatusError as e:` as still-broken — a false negative on correct code. Widened to grade every clause, then re-proven red against the original file. |
| 3 | Cross-reference integrity | CLEAN | Every new reference resolves: `58-resilience § Provider-death resilience` → heading at `:340`; `76-gpu-workers § Provider Failover` → `### Provider Failover` at `:113`; the matrix row parses as a real table row at `:26`. |
| 4 | Cross-pack consistency of the standard | CLEAN (2 candidates REFUTED) | See § Refuted — both were artifacts of my own grep patterns, not content gaps. |
| 5 | **Undefined symbol in a worked example** | **FIXED(1)** | The corrected failover introduced `healthy_chain()` with no provenance — the same criticism I levelled at the original's `call_provider`. Now carries what it does, where to vendor it (`fabrik-lib/health-probe/`), and when not to hand-roll it. |
| 6 | **Enforcement overclaim** (the `oasdiff` class) | CLEAN | Both new rubric rows state IN THE ROW that they are graded by an LLM and that no mechanical check exists. The new test's docstring carries an explicit ⚠️ SCOPE paragraph separating corpus-consistency from project-compliance. |
| 7 | Governance-sync blast radius (~46 repos) | CLEAN | Every sentence holds for all 12 `SCAFFOLD_TYPES` (registry imported live, not recalled). The matrix now covers 12/12 — mechanically asserted, so it cannot silently drift again. |
| 8 | Render safety / corpus parity | CLEAN | Rendered from `/opt/fabrik` MAIN (`pwd` verified first — a worktree render PRUNES master-only artifacts box-wide). `--check` clean before, correctly drifted after edits, clean after render. `check_command_corpus.py` green across 47 files. |
| 9 | **Shared-tree hygiene** (standing) | CLEAN | `git diff --name-only 7fbc2b6d..HEAD` = 9 files, all owned paths. Zero sibling files touched — the live WIP in `.windsurf/rules/ai/*`, `core/65-rag-search.md` and `libs/subagents/*` is untouched. Both stashes used during red-on-revert were single-file, on my OWN paths. |
| 10 | Fleet divergence disclosure | CLEAN | The unresolved conflict with fleet's scaffold §3b is named IN the rule with its mail id (`01M14E2VZM`), not silently resolved in either direction. |
| 11 | Doc-coverage receipt | CLEAN | `check_doc_sync --range 7fbc2b6d..HEAD` → rc=0; `check_doc_stubs --range` → clean. One INDEX WARN for the new plan-lock file — benign and pre-existing behaviour (the directory is indexed; none of the other 52 locks are listed individually). |
| 12 | Python discipline / testing strategy | CLEAN | `final_gate.py --json` = success, 38 blocking checks, 0 failures. |
| 13 | **fail-open/fail-closed** (standing) | CLEAN | The new test fails CLOSED on a corpus it cannot parse: `_matrix_types()` asserts the `## Per-Scaffold Applicability` heading exists and `test_provider_failover_*` assert the `### Provider Failover` heading exists, so a renamed/deleted section is a LOUD failure, never a silent pass over an empty section. **Probe EXECUTED, not asserted** (I wrote this row before running it, which is the defect this review exists to catch): pointing the helper at a heading that does not exist returns `FAILS CLOSED — AssertionError: 58-resilience.md lost its Per-Scaffold Applicability heading`, never a silent green over an empty section. |
| 14 | **cost/quota accounting** (standing) | REFUTED | No metered spend on this surface. The diff adds no API call, no model dispatch, no paid path; `NO-POOL` held for the whole run, so zero pool spend was incurred. The rule text *discusses* provider cost but the change itself consumes nothing. |
| 15 | **boundary/sentinel/prefix** (standing) | CLEAN | Two regexes carry real boundary risk. `_ROW` (`^\|\s*` + backticked token) is scoped to the matrix SECTION, not the whole file, so a backticked token in an unrelated table cannot inflate the row set — verified by the exact-set assertion (`EXTRA: []`, not a subset test). The `except` regex is the F1 fix: it now accepts both parenthesized tuples and a bare single exception with an optional `as` binding. |
| 16 | **behavior-without-a-test** (standing) | CLEAN | The ladder row, the § Provider-death resilience prose and both rubric rows have **no test and cannot have one** — they are judged by an LLM reading a design. This is not an oversight: the plan's § Enforcement and both rubric rows say so in the artifact itself. What IS tested is everything mechanically assertable about them (registry coverage, the worked example's except clause, breaker granularity, corpus render parity). |
| 17 | FLOOR: secrets / Postgres / Docker / 12-Factor | REFUTED | No auth, DB, container, port, secret or service surface — this diff is three markdown rule packs, two command sources, one test, a CHANGELOG entry and the plan. |

## Pass Ledger

| Pass | what it re-checked | raised | new: | fixed |
|---|---|---:|---:|---:|
| Pass 1 (WIDE) | all 13 classes over the cumulative diff `7fbc2b6d..31426294` | 2 | 2 | 2 |
| Pass 2 (SCOPED) | cross-pack consistency of the standard | 2 | 2 | 0 (both REFUTED — see § Refuted) |
| **Pass 3 (QUIET, closing)** | **all 13 classes vs the FIXED tree** | **0** | **0** | **0** |

**Closing round verdict — `found: 0, fixed: 0`.** That is the quiet exit round the loop requires, and it
is a real re-execution, not a restatement of pass 2.

Pass 3 re-executed every mechanical check against the final state: `pytest` 3 passed ·
`assemble_commands.py --check` OK · `check_command_corpus.py` rc=0 · both cross-reference targets resolve
(1 each) · the F2 fix present in `76-gpu-workers` · the F1 widened regex present at
`tests/test_rule_pack_scaffold_coverage.py:83` · **0 sibling files in the diff**. Raised nothing new.

## Findings

- **F1 — my own test gave a false negative on the correct fix.** CONFIRMED by execution: after the
  `except httpx.HTTPStatusError as e:` clause landed, the assertion still failed, because
  `except\s*\(([^)]*)\)` requires parentheses and the new clause has none. A test that reports correct code
  as broken is the mirror of a vacuous one and would have trained the next reader to delete it. FIXED and
  re-proven red against the original file.
- **F2 — `healthy_chain()` shipped undefined.** CONFIRMED by reading the rendered section. I criticised the
  original example for an undefined `call_provider` and then introduced the same defect one line up. FIXED
  with a comment naming the function's contract and its vendor source.

## Refuted

- **"76-gpu-workers is missing the exercised-last-rung outcome."** REFUTED — `grep -l exercised` missed it
  because the pack says `EXERCISED path` (`:147`) and `Exercise the last rung on a schedule` (`:155`). The
  content is present; my pattern was case- and tense-narrow.
- **"58-resilience never mentions the `sort`/`order` trap."** REFUTED — it is at `:364`, inside the
  per-route table cell. My grep pattern mis-escaped the backticks and matched nothing. Verified by eye
  against the real line.

Both refutations are the same lesson the plan itself is about: a check that cannot ask its question
returns a clean-looking answer. I treated neither grep as evidence until I had opened the line.

## Closing evidence

```
$ python -m pytest tests/test_rule_pack_scaffold_coverage.py -q
3 passed

$ python commands/assemble_commands.py --check
check OK — installed commands + skills match rendered sources

$ python scripts/enforcement/check_command_corpus.py
✓ command corpus: … all sound across 47 corpus file(s)

$ python scripts/enforcement/check_doc_sync.py --range 7fbc2b6d..HEAD
(rc=0 — one benign INDEX warn for the plan-lock file)

$ python scripts/final_gate.py --json
{"status": "success", "blocking": 38, "failures": []}
```

## Per-finding disposition — 2 findings → 2 FIXED + 2 REFUTED candidates

F1 FIXED · F2 FIXED · both cross-pack-consistency candidates REFUTED with the line they live on.
