# Whole-plan review — plan-lock release check

Status: CLOSED — coverage-adjudicated exit, final round `found: 0`

**Plan:** `2026-08-26-plan-1-plan-lock-release-check` · **Baseline:** `3b338428` · **Head:** `7ec570cd`
**Scope:** the cumulative diff across BOTH phases — what only appears once they combine.
**Surface:** `HEAD 7ec570cdf7cfcea606b25c0c41a05f71b680c2f8` · diff md5 `9e17e6253d90cc3a489604179f08808a`
(`git diff 3b338428..HEAD -- scripts/enforcement/check_plan_lock_release.py scripts/final_gate.py
tests/enforcement/ docs/reference/plan-lock-lifecycle.md | md5sum`)

**Rubric (armed this run):** `python scripts/review_rubric.py --changed <the plan's File Scope>` was run this turn over all six owned paths; its MATCHED section is reproduced below.
*(Stated outside the fence deliberately — `check_review_coverage.py:364` searches FENCE-STRIPPED text, so a fenced-only invocation does not count. That is the gate stopping a report from satisfying the rubric requirement by quoting a template, and it caught this one.)*

```
$ python scripts/review_rubric.py --changed \
    scripts/enforcement/check_plan_lock_release.py tests/enforcement/test_plan_lock_release.py \
    tests/enforcement/test_final_gate_registration.py scripts/final_gate.py \
    docs/workflows/FINAL_GATE_WORKFLOW.md docs/reference/plan-lock-lifecycle.md
## MATCHED — packs whose globs hit the changed paths
  core/10-python.md           (check_plan_lock_release.py, final_gate.py, test_final_gate_registration.py)
  core/40-documentation.md    (plan-lock-lifecycle.md, FINAL_GATE_WORKFLOW.md)
  core/45-testing-strategy.md (test_final_gate_registration.py, test_plan_lock_release.py)
```

The Coverage Checklist rows below derive from those three MATCHED packs, the FLOOR block, and the
four standing recurrence classes.
Per-phase reviews: [phase A](2026-08-26-plan-1-plan-lock-release-check-phase-A-review.md) ·
[phase B](2026-08-26-plan-1-plan-lock-release-check-phase-B-review.md).

## Why a whole-plan pass exists

The per-phase reviews caught 32 defects between them, all phase-local. This pass looks for the class
they structurally cannot see: a Phase-A contract Phase B violated, an invariant that only breaks in
aggregate, a requirement that fell between the two.

## The aggregate risk this plan actually carries

**The gate now runs the check, and the check reads the lock of the plan being executed.** That
circularity is unique to this deliverable — no other enforcement check audits the machinery of the
command executing it. A finder raised it as a `STALE LOCK`/`PLAN FIELD STALE` self-report race, and
the concern is legitimate: at some point during Finish, the plan's status says EXECUTED while its
lock is still `active`, which is rule 1B's exact signature.

**Refuted by execution, not by reasoning.** The prescribed Finish order closes the window, and each
state was run:

| Point in Finish | Lock | Plan | Check output |
|---|---|---|---|
| step 2 (fresh gate, before release) | `active` | `IN-PROGRESS`, under `plans/` | `OK — 0 stale of 51 … (1 non-terminal evaluated · 50 terminal/unevaluable · 0 foreign)` |
| after step 5 (released, then flipped) | `released` | `EXECUTED` | terminal ⇒ skipped, no finding |
| after step 6 (archived + repointed) | `released` | `EXECUTED`, under `archived/` | terminal ⇒ skipped, no finding |

The one ordering that *would* self-report is releasing **after** flipping the status — which is why
`fabrik-execute-plan.md:955-956` puts the release first, and why both the plan and
`docs/reference/plan-lock-lifecycle.md` record that dependency explicitly rather than leaving it to
be rediscovered.

The step-2 line is also the plan's own predicted self-referential assertion: the hub carries exactly
one non-terminal lock during this run — this plan's — so `OK` with `1 non-terminal evaluated` is
required there, and `NOTHING VERIFIED` would have been a bug.

## Cross-phase contract check

| Phase-A contract | Phase-B wiring | Agrees? |
|---|---|---|
| always exits 0, findings included | `warn_only=True` (a non-zero exit would redden ~46 repos) | ✔ verified by running all three tiers |
| prints nothing when there is no lock dir | registered every-tier, so it runs in 30 lock-less repos | ✔ `job-agent` prints nothing |
| census first, then findings | gate ships `output[:500]` / 10 lines | ✔ census is line 1 |
| `--project-root` / `--json` | gate invokes it **bare** | ✔ bare invocation yields the human output |
| eight labels | doc documents eight | ✔ all reachable in code, all documented |

Nothing from Phase A was left dead by Phase B's wiring, and the doc describes no behaviour the code
lacks (every claim re-verified against the source at Phase B's review).

## Rounds

| Pass | axes re-checked | Raised | Fixed | Refuted |
|---:|---|---:|---:|---:|
| 1 | cross-phase contract · aggregate/circular invariant | 1 | 0 | 1 |
| 2 | the seam between the check's contract and the gate that runs it — corrupt lock · mid-plan repo · no `docs/development/plans/` at all | **0** | 0 | 0 |
| **exit** | — | **0** | | ✓ |

Pass 1's single candidate (the self-report race) was refuted by executing all three Finish states.
Pass 2 returned `NONE`, and its three edge states were additionally run by hand — a project with a
lock but **no plans directory at all** exits 0, reports `ORPHAN LOCK` with the four candidate paths
it tried, and prints `NOTHING VERIFIED` because nothing was evaluable. The finding still prints
under that verdict, which is Phase A's most important fix working in aggregate.

## Coverage Checklist

| # | Class | Verdict | Evidence |
|---|---|---|---|
| 1 | Cross-phase contract | CLEAN | The table above; every row executed, not reasoned. |
| 2 | Aggregate/circular invariant | REFUTED | The self-report race is real in principle and closed by the prescribed Finish order; all three states run and recorded. |
| 3 | Requirements coverage | CLEAN | All 14 `Interfaces.Produces` symbols present; CLI contract matches; all 8 labels reachable; all 6 deliverables committed. |
| 4 | **fail-open vs fail-closed** (standing) | CLEAN | Exit-0 contract proven in Phase A; `warn_only` registration verified in Phase B; no aggregate path re-opens it. |
| 5 | **cost / quota / limit** (standing) | CLEAN | The gate's advisory budget is answered by census-first; distribution to ~46 repos verified non-noisy (lock-less repos print nothing). |
| 6 | **boundary / sentinel / prefix** (standing) | CLEAN | Phase A owns the token/status boundaries, Phase B the `if tier` boundary; both pinned by mutant matrices. |
| 7 | **behavior-without-a-test** (standing) | CLEAN | 52 tests. The one behavior that spans phases — the check running inside the gate — is verified by executing all three tiers plus a synced project. |

## Fleet distribution — verified, not assumed

The governance-sync fired because the commit was made from `/opt/fabrik` itself, not a worktree
(`.pre-commit-config.yaml:67` guards on `pwd`):

```
$ ls <project>/scripts/enforcement/check_plan_lock_release.py
transdoc PRESENT · tryton-crm PRESENT · job-agent PRESENT

$ cd /opt/transdoc && python scripts/enforcement/check_plan_lock_release.py
0 stale · 0 likely-stale · … · 0 unevaluable
OK — 0 stale of 3 plan lock(s) examined (1 non-terminal evaluated · 2 terminal/unevaluable · 0 foreign)
```

Presence *and* execution — the distributed copy runs correctly in a project that has never seen this
plan.

## Verification

```
$ python -m pytest tests/enforcement/test_plan_lock_release.py tests/enforcement/test_final_gate_registration.py -q
52 passed

$ python scripts/final_gate.py --check --json          # Tier 2, fresh this turn
"status": "success"  (48 passed / 0 failed)
```

⚠️ **Tier 3 (`--systemic`) is red and it is NOT this plan's.** `Documentation Drift` flags
`2026-06-29-plan-watchdog-deploy-side.md` (COMPLETE, 58 days old) and broken links in
`2026-06-30-plan-fabrik-deploy-readiness-gaps.md` — sibling plan files, outside this plan's File
Scope. The step-8 baseline (`3b338428`, Tier 1) was green; Tier 3 was not baselined, and CLAUDE.md
states Tier 3 is never a completion gate. Left alone under shared-master discipline.

`found: 0, fixed: 0`.
