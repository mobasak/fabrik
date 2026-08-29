# Review — cmd 25/31 corpus audit of /fabrik-repo-review + the harvest-blackout fix (2026-08-29)

**Status:** CONVERGED
**Surface:** commits `093d0a6c` + `3418284a` + `dd326a4b` (hooks, router, command source, docs, tests)
**Scope:** the 23-surface checklist audit of `commands/_sources/fabrik-repo-review.md` and the
Stop-hook thread-anchor harvest blackout that opened the turn. Rubric armed via
`review_rubric.py --changed` over the three code surfaces; classes hunted per its injected mandates
plus the audit's own fixed ledger.

**Finder mechanism:** single-context under the operator's standing `NO-POOL:` directive — no pool
breadth, no independent native finder. Class-partitioned rounds over a fixed ledger; stated, not
implied.

---

## Coverage Checklist

| # | Class | Verdict | Evidence |
|---|---|---|---|
| C1 | API-RECIPE — the command's dispatch recipe matches the live module | FIXED(1) | `fanout` at HEAD requires keyword-only `repo:` (`libs/subagents/agent.py:899-912`) and records NOTHING when `project=None` (`FanoutBatch` docstring, `agent.py:220-224`); repo-review's recipe omitted both while teaching a `set_quality` back-fill — the exact orphan shape the docstring documents 7 live rows of. Recipe aligned to the `/fabrik-review` shape (`fabrik-review.md:150`). `set_quality` signature (`pg_ledger.py:486-497`) and `(results, table)` unpack verified live. |
| C2 | ROUTER-STEM — advertised triggers reach their own command | FIXED(1) | All four advertised phrases returned None at HEAD and "full project code review" mis-routed to `fabrik-review` (probed on the HEAD router). Totality-worded stem added above `review`; 15-phrase collision matrix green; "review the full project plan"→`review` pinned as pre-existing (byte-identical at HEAD). 3 regression tests in `tests/test_skill_router_hook.py` (suite 160 green). |
| C3 | GRADER-HONESTY — unread artifacts declared, not implied | FIXED(1) | No mechanical check reads repo-review's scratchpad ledger; Phase 4 now states it plainly and names the run record's round entries as the graded trace (checklist items 34/37). |
| C4 | HOOK-SEAM — the harvest blackout's root cause, fixed red-first | FIXED(1) | Harvest sat below the `final_gate.py` eligibility return and resolved only from payload cwd; one post-compact Stop blacked out the register 26m with zero trace. Moved above the return + `__file__` fallback + `anchor_harvest` kaizen event. `tests/test_stop_hook_harvest_resilience.py` fires the REAL hook via synthetic Stop payloads: drifted-cwd case watched RED at HEAD, green after; normal-shape regression guard green. Pre-existing hook-suite reds unchanged at 13+4 (copy-based revert comparison, not stash). |
| C5 | ENUMERATIONS — canonical values in the command match the live registry | CLEAN | `SCAFFOLD_TYPES` = 12 incl. wordpress (imported live, matches the command's list verbatim); compose claim verified per-type in `scaffold.py` (gpu delegates to `_scaffold_python_api`, static-site→`_scaffold_saas_skeleton` with `compose.yaml` in required files at `scaffold.py:389`, desktop-app alone compose-less). |
| C6 | REFUTED/N-A — checklist items checked and cleared | CLEAN | SKIP semantics ✓ (inline → /fabrik-review); NEXT map ✓ (`assemble_commands.py:72`); run-record fragment closes by name with `--feedback` ✓; injection fragment absence matches `/fabrik-review`'s roster (identical fragment lists, corpus ruling); evidence discipline (prove-before-flag, red→green, embedded proof, full suite) present in the source; corpus gate green across 54 files. |
| C7 | STALE-COMPANION — docs the fixes made stale | FIXED(2) | `docs/reference/thread-anchors.md` harvest row + `docs/workstation/hooks-index.md` row updated with the reorder, fallback and `anchor_harvest` event, same change. |
| C8 | fail-open/fail-closed | FIXED(1) | This IS C4's class: every harvest failure path was fail-SILENT (skip with no trace); the `anchor_harvest` event now distinguishes "never ran" from "ran, found nothing", while the block itself stays fail-open by design (a harvest failure must never block a turn). |
| C9 | cost/quota accounting | CLEAN | No cost, quota or limit edge in the diff; the harvest's 5s subprocess cap and the hook's fail-open posture are unchanged. |
| C10 | boundary/sentinel/prefix | CLEAN | The stem's boundary edges probed in the 15-phrase matrix (the `(?!\s*plan)` lookahead added after "full project plan" over-fired); `Path(__file__).resolve().parents[2]` verified to name the hook's repo root from `<repo>/.claude/hooks/`. |
| C11 | behavior-without-a-test | CLEAN | Every behavior change shipped its grader in the same commits: 2 harvest tests (drifted RED-first + normal-shape guard), 3 router tests; suites 160 + 2 green this turn. |

---

## Pass Ledger

- Pass 1 (WIDE) — all 23 surfaces vs the checklist — classes api-recipe, router-stem, grader-honesty: found: 3, fixed: 3
- Pass 2 (SCOPED) — fresh re-read of every fixed hunk + companions — class stale-companion-docs: found: 1, fixed: 1
- Pass 3 (WIDE) — full ledger re-sweep, fresh; the no-op round (TERMINAL verdict printed by `command_run.py`): found: 0, fixed: 0

## Gate

Verbatim `python3 scripts/final_gate.py --json` top-level, run this turn after the final commit:

```json
{"status": "success", "tier": 2, "passed": 55, "failed": 0, "failures": []}
```

Advisories (16) are pre-existing fleet/sibling debt (fabrik-lib vendored drift, old committed
reviews, a sibling's untracked `libs/subagents/` files) — none from this diff.
