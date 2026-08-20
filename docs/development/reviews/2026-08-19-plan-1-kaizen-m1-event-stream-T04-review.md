# T04 review — gate_run + rule_activation sensor emitters (final_gate / select_rules / review_rubric)

## Round 1 — acceptance

Finders: pool deepseek/deepseek-v3.2-exp ×1 + google/gemini-3-flash-preview ×1 (errored: region
403) + native fabrik-reviewer (Opus, grounded live in the worktree with byte-compare probes).

Pool: 1 finding, REFUTED with evidence — the claimed `all_results.append` mutation inside the
`--json` block does not exist (single assignment at final_gate.py:1843; the JSON section only
READS it to build `advisory_rows`).

Native: 6 findings — 1 CONFIRMED, 3 fixed, 2 adjudicated no-change:

| # | Verdict | Finding | Disposition |
|---|---|---|---|
| 1 | CONFIRMED | stderr not byte-identical when the store is unwritable (`emit()`'s `_warn` line — none of the three scripts wrote stderr pre-T04); the suite never asserted stderr and two scripts had NO broken-store test | fixed: call-site `redirect_stderr`; stderr equality asserted; the two missing byte-compares added — the piped-fixture test first passed VACUOUSLY (8 KiB print buffer) and was made to genuinely enter the handler before going red |
| 2 | PLAUSIBLE | `BrokenPipeError` in review_rubric skipped the event for a completed `\| head` run | fixed: handler falls through to the sensor |
| 3 | PLAUSIBLE | a missing FLOOR pack still reported as injected (heading emitted before the on-disk check) | fixed: only on-disk packs emitted; the gap named in `packs_missing` |
| 4 | info | ticket wording "after the JSON is composed" vs placement before composition | no-change: same settled source values; after the `--json` print is unreachable (early return) |
| 5 | info | "duration" named in the dispatch brief | brief inaccuracy — the ticket never required it |
| 6 | PLAUSIBLE | first emit runs git probes at 10 s default ahead of script output | fixed: `probe_timeout_s=2.0` at all three sites, asserted via a recording stub |

Classes A–D, F swept clean by the finder (verdict integrity, single-emission dedup incl. the
convergence loop, field honesty — same variables the report is built from, stdout purity,
worktree cwd resolution).

## Round 2 — close

Orchestrator first-hand in the rebased worktree (base 0776ac60, tip 33e67f01): 13/13 sensor tests
green; the flagged `test_select_rules` red REPRODUCED ON MASTER (pre-existing, not T04's);
`--lean --json --check` success in-worktree. **found: 0, fixed: 0 — T04 accepted.** Commits
6a82a5c5 + 33e67f01, squash-applied at merge.
