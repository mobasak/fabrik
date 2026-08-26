# Phase B review — registration, AST pin, subsystem doc

Status: CLOSED — coverage-adjudicated exit, final round `found: 0`

**Plan:** `docs/development/plans/2026-08-26-plan-1-plan-lock-release-check.md` · **Phase:** B
**Surface:** `scripts/final_gate.py` (registration) · `tests/enforcement/test_final_gate_registration.py`
(the pin) · `docs/reference/plan-lock-lifecycle.md` · `docs/workflows/FINAL_GATE_WORKFLOW.md` · `INDEX.md`
**Dispatch:** pool finder breadth (`fanout("review", …, mode="read_only")`, flywheel-recorded,
`set_quality` back-filled) ×3 rounds. The surface is never-route, so all edits were native.

## Rounds

| Round | Raised | Fixed | Refuted |
|---:|---:|---:|---:|
| 1 | 2 | 0 | 2 |
| 2 | 5 | 1 | 4 |
| 3 | 6 | 1 | 5 |
| **exit** | **0** | | |

## What the pin actually proves

The registration sits above the `# ── Tier 1` marker, outside every `if tier …` block, so the row
appears in `--lean`, default **and** `--systemic` — verified by running all three:

```
--lean     row: True   default    row: True   --systemic row: True
```

The pin asserts the literal has **no `ast.If` ancestor whose test mentions `tier`** — any operator.
A literal mirror of the file's existing `_phase_tests_in_tier2_only` helper would have been
**vacuous**, and this is measured rather than argued:

```
                    Eq-only mirror says every-tier | this pin
_PLR_MUTANT_EQ                              False  |   False
_PLR_MUTANT_IN   (if tier in (1, 2):)        True  |   False   <-- mirror ACCEPTS
_PLR_MUTANT_GE   (if tier >= 2:)             True  |   False   <-- mirror ACCEPTS
```

`if tier in (1, 2):` is four lines below the real insertion point — the likeliest place a later
edit moves the call. The Eq-only form waves it through and the check silently stops running in
`--systemic`; `>= 2` kills it in `--lean`, the mode the plan calls load-bearing. The built-in red
feeds the helper all three.

## Findings

**Fixed (2):**

1. **My own mutant strings were malformed** — a hand-rolled `.replace()` left the first line
   un-indented, so all three mutants died on `IndentationError` and every `assert not …` passed
   *vacuously*. The pin would have looked green while proving nothing. Rebuilt with
   `textwrap.indent`; all three now parse and are rejected on their merits.
2. **The doc forward-referenced the archived plan path**, which resolves in neither state (the plan
   is under `plans/` until Finish moves it). `check_doc_links.py` caught it. Now named, not linked.

**Refuted (11), each by execution:**

- *"`_mentions_tier` matches a string containing 'tier'"* → it tests `isinstance(x, ast.Name)`;
  string constants are `ast.Constant` and comments are not in the AST at all. Proven: an `if` whose
  test has no `tier` Name returns `False`, and the pin still says every-tier.
- *"only one literal need be ungated"* → it is `gated == 0`. Proven: adding a second, tier-gated
  registration alongside the good one is rejected.
- *"`while tier …` / helper-function indirection escapes the pin"* → true and out of scope; the pin
  now **documents that bound** rather than implying total coverage. Every tier branch in
  `final_gate.py` is an `if`, and the registrations are inline.
- **Five claimed line references "do not exist"** — the finder asserted `check_plan_tickets.py`
  ends at line 546, `check_phase_tests.py` at 30, `final_gate_stop.py` at 783. Actual: **1557, 296,
  1331**. It had only the diff, not the repo, and hallucinated the file lengths. Every cited line
  was opened and resolves exactly as documented:

  ```
  check_plan_tickets.py:561  ->     lock = root / ".fabrik" / "plan-locks" / f"{plan_dir.name}.json"
  check_plan_tickets.py:1470 ->     locks = root / ".fabrik" / "plan-locks"
  check_plan_tickets.py:1481 ->                 cand = root / "docs" / "development" / "plans" / lf.stem
  check_phase_tests.py:36    -> LOCK_DIR = PROJECT_ROOT / ".fabrik" / "plan-locks"
  final_gate_stop.py:785     ->             if ".fabrik/plan-locks/" in rel and p.is_file():
  ```

  Recorded because it is the reason the contract says a subagent's claim is not proof.
- *"the CLI does not use `parse_known_args`"* → `grep -c` → 1. The finder had no access to the file.
- *"advisory + never-auto-reclaim contradicts the deletion trigger"* → unrelated: one is what the
  check does to locks, the other is when to stop running the check.

**Fair, and applied (1):** the doc stated fleet measurements without saying where they were taken.
A `## Where the measurements come from` section now points at the spec's Evidence and the plan's
Pass Ledger, and says plainly that the counts are snapshots of a corpus other sessions mutate — so
re-measure rather than quote.

## Coverage Checklist

| # | Class | Verdict | Evidence |
|---|---|---|---|
| 1 | Registration correctness | CLEAN | Row present in all three tiers, verified by running each. |
| 2 | Pin discriminating power | FIXED (1) | Three mutants, all rejected; the Eq-only mirror measured accepting two of them. The malformed-mutant defect made the asserts vacuous and was caught here. |
| 3 | Doc truth (citations) | CLEAN | All 10 `path:line` citations opened and verified; `check_doc_links` clean; `check_doc_index` clean. |
| 4 | Doc truth (provenance) | FIXED (1) | Measurement provenance section added. |
| 5 | Doc Sync Matrix | CLEAN | `FINAL_GATE_WORKFLOW.md` row (both tier sections), `INDEX.md` rows, own `CHANGELOG` entry. `docs/README.md` indexes DIRECTORIES, not files — the existing `reference/` row already covers it, so no per-file row (the plan assumed one; the file's real convention wins). |
| 6 | **fail-open vs fail-closed** (standing) | CLEAN | The registration is `warn_only=True`; the check's exit-0 contract was proven in Phase A. |
| 7 | **cost / quota / limit** (standing) | CLEAN | The gate's 500-char advisory budget is answered by the census-first line (Phase A). |
| 8 | **boundary / sentinel / prefix** (standing) | CLEAN | The `if tier` boundary IS this phase's risk class, and the three-mutant matrix is its proof. |
| 9 | **behavior-without-a-test** (standing) | CLEAN | The registration position is the only new behavior and it is pinned; the live-fleet assertion is proven red-on-revert against a resolver that drops the archived branches. |

## Exit round

Round 3 raised 6; **1 applied (measurement provenance), 5 refuted by execution** — including five
hallucinated line-existence claims disproved by opening every file. No candidate survived.

`found: 0, fixed: 0` on the final look.

## Verification

```
$ python -m pytest tests/enforcement/test_plan_lock_release.py tests/enforcement/test_final_gate_registration.py -q
52 passed

$ python scripts/final_gate.py --check --json          # Tier 2
"status": "success"  (49 passed / 0 failed)

$ python scripts/enforcement/check_doc_links.py | grep plan-lock-lifecycle   -> (clean)
$ python scripts/enforcement/check_doc_index.py | grep plan-lock             -> (clean)
$ python scripts/enforcement/check_doc_sync.py                               -> exit 0
```

**Docs convergence** was done by running the checks the docs-review converges against —
`check_doc_links`, `check_doc_index`, `check_doc_sync`, plus opening every cited `path:line` — all
green. Recorded plainly rather than claiming the full `/fabrik-docs-review` command was invoked.

⚠️ **`--systemic` (Tier 3) is red, and it is NOT this plan's**: `Documentation Drift` flags
`2026-06-29-plan-watchdog-deploy-side.md` (COMPLETE, 58 days old) and broken links in
`2026-06-30-plan-fabrik-deploy-readiness-gaps.md`. Neither file is in this plan's File Scope, and
Tier 3 is explicitly not a completion gate (CLAUDE.md § Completion Contract). Left alone under
shared-master discipline.
