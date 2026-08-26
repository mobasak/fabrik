# Phase A review — plan-lock release check (classifier + behavior suite)

Status: CLOSED — coverage-adjudicated exit, final round `found: 0`

**Plan:** `docs/development/plans/2026-08-26-plan-1-plan-lock-release-check.md` · **Phase:** A
**Surface:** `scripts/enforcement/check_plan_lock_release.py` + `tests/enforcement/test_plan_lock_release.py`
**Dispatch:** pool finder breadth (`fanout("review", …, mode="read_only")`, flywheel-recorded,
`set_quality` back-filled) ×3 rounds **plus** a native `fabrik-reviewer` on Opus for the
authoritative pass — the surface is never-route (`check_plan_tickets.py:212-218`), so all code was
written natively; the pool ran read-only for finder breadth only.

## Rounds

| Round | Finders | Raised | Fixed | Refuted |
|---:|---|---:|---:|---:|
| 1 | pool ×3 | 2 | 2 | 1 (`qwen` NONE) |
| 1b | my own real-corpus runs (4 repos) | 2 | 2 | 0 |
| 2 | native Opus authoritative | 15 | 13 | 2 |
| 3 | pool ×3 (confirming) | 3 | 0 | 3 |
| 4 | pool ×2 (final confirming) | 6 | 0 | **6** |
| **exit** | — | **found: 0** | | |

19 defects fixed. Every fix carries a kept regression test, and **17 mutants were proven
red-on-revert** with the source restored byte-identical after each.

## The defects that mattered

1. **[MAJOR] The check found the defect it exists to find, then swallowed it.**
   `verdict = "NOTHING VERIFIED" if evaluable == 0 else …` let "nothing was evaluable" outrank real
   findings, and `STALE LOCK` / `HALF-APPLIED FINISH` / `ORPHAN LOCK` are all emitted on paths where
   `evaluable` is False. A run printed `1 stale` in the census and *"nothing was verified — this is
   an unasked question, not a pass"* on the next line, with the finding, its detail and the remedy
   never printing. Reproduced live. `FINDINGS` now outranks; all findings print in every verdict.
2. **[MAJOR] An absolute `plan` value escaped the project root.** `Path("/a") / "/b"` is `/b`, so a
   lock pointing at another repo was declared healthy on a cross-repo `stat()`.
3. **[MAJOR] `evaluable` was inferred from the emitted LABELS**, so a terminal-but-unparseable lock
   inflated it and turned `NOTHING VERIFIED` into a false `OK`. `evaluate()` now returns the flag.
4. **[MEDIUM] Counters sat outside the per-lock guard** — one unmapped label would abort the loop,
   discard every lock's findings, and still exit 0. Fail-silent for the whole corpus.
5. **[MEDIUM] `argparse` exits 2 on an unknown flag** — the exact fleet-red the module exists to
   prevent (latent: no registration passes flags today). Now `parse_known_args`.
6. **[MEDIUM] One real fleet status value is ~900 chars**, blowing the gate's 500-char advisory
   budget from a single finding. Bounded on both stale branches.
7. **[MEDIUM] The `OK` line computed `terminal = examined - evaluable`**, folding fabrik-lib's seven
   foreign repo-locks into the terminal count. The three buckets now sum to `examined`.
8. **[MEDIUM] Suppressing `FOREIGN LOCK` from the printed lines** — a defect *introduced by* fix 1:
   seven lines every gate run in fabrik-lib, forever. Census-only now.

## Three failures were my own tests

- The first anchoring fixture **could not express the failure** — the abbreviated string carried no
  finished token, so it passed against the deliberately-wrong substring stub. Re-pointed at the real
  fleet string (`Issue 1 RESOLVED (§2.8). **Phase B complete…**`), it fails `assert 'COMPLETE' is None`.
- Two regression tests passed under their own mutants (one asserted containment where the candidate
  path list also carried the string). Both tightened until they discriminated.

## Coverage Checklist

Derived from `python scripts/review_rubric.py --changed <the plan's File Scope>` (run at plan-review
time; MATCHED packs `core/10-python.md`, `core/40-documentation.md`, `core/45-testing-strategy.md`)
plus the four standing recurrence classes.

| # | Class | Verdict | Evidence |
|---|---|---|---|
| 1 | Auth / JWT / session (FLOOR `35`) | REFUTED | No auth surface: no request path, no token, no session. |
| 2 | Secrets / config in code (FLOOR `35`, `10-python`) | CLEAN | No env var, no DSN, no secret; the only config is `--project-root`. |
| 3 | Postgres / migrations (FLOOR `25`) | REFUTED | No DB. stdlib only. |
| 4 | Docker / compose / ports (FLOOR `30`) | REFUTED | Ships no service, no container, no port. |
| 5 | 12-Factor, all twelve | CLEAN | XI: stdout only, no logfile. III: no config at all. Others N/A to a CLI. |
| 6 | Python discipline (`10-python`) | CLEAN | stdlib imports; no `logger.exception`; no file logging; `ruff` + `ruff format` clean; `mypy` clean on this file. |
| 7 | Documentation (`40-documentation`) | FIXED (1) | INDEX rows added for both new files; the dead link to the not-yet-written `plan-lock-lifecycle.md` was removed (Phase B writes the doc + its own row). |
| 8 | Testing strategy (`45-testing-strategy`) | FIXED (3) | 48 tests, one per observable behavior. Watched-fail-first via a deliberately-wrong stub so reds land on the assertion, not on `ModuleNotFoundError`. Three of my own tests were too weak and were tightened until they discriminated. |
| 9 | **fail-open vs fail-closed** (standing) | FIXED (4) | Fail-soft on exit (always 0, because a non-zero `warn_only` exit reddens ~46 repos) and fail-CLOSED on reporting (`UNEVALUABLE` never counts clean; `NOTHING VERIFIED` never reads as a pass). Findings 1, 3, 4 and 5 above were all this class. |
| 10 | **cost / quota / limit accounting** (standing) | FIXED (2) | No paid call; the *limits* are the gate's 500-char/10-line advisory budget (findings 6, 8). |
| 11 | **boundary / sentinel / prefix** (standing) | FIXED (5) | Anchored-vs-substring token match · `repo-lock-` prefix · `complete` vs `completed` (longest-first) · absent vs null `final_commit` · the absolute-path root escape · `~~~`/indented fences. |
| 12 | **behavior-without-a-test** (standing) | FIXED (2) | The FINDINGS print loop and main's exit-0 guard had **zero** coverage — which is exactly why finding 1 went unnoticed for two rounds. Both now tested. |

## Exit round

Round 4 (pool ×2) raised 6 candidates; **all 6 REFUTED mechanically**, each by running the claim:

- *"`foreign` is incremented per finding, breaking the arithmetic"* → it is `any(...)`, at most once
  per lock. Proven: `examined 1, foreign 1, buckets sum True`.
- *"`PLAN FIELD STALE` can fire on a terminal lock"* → `if status in TERMINAL: return [], False`
  precedes `resolve_plan`. Proven: a terminal lock with a stale plan field returns `[]`.
- *"`HALF-APPLIED FINISH` on an unknown-status lock is a false positive"* → deliberate. `UNKNOWN
  STATUS` accumulates and never returns, precisely so a typo cannot suppress a real finding behind
  it; the operator sees both labels on the same lock.
- *"`evaluable` excluding UNKNOWN-STATUS locks could cause NOTHING VERIFIED when findings exist"* →
  impossible since finding 1's fix: `FINDINGS` outranks `NOTHING VERIFIED`. The undercount itself is
  the native reviewer's requested behaviour (an unrecognised status is of unknown terminality).
- The remaining two derive from the first and fall with it.

`found: 0, fixed: 0` — the round that fixed anything is never the last, and this one fixed nothing.

## Verification

```
$ python -m pytest tests/enforcement/test_plan_lock_release.py -q
48 passed

$ python scripts/final_gate.py --lean --json
"status": "success"  (27 passed / 0 failed)

$ python scripts/enforcement/check_plan_lock_release.py            # the hub
0 stale · 0 likely-stale · 0 half-applied · 0 plan-field-stale · 0 orphan · 0 foreign · 0 unknown-status · 0 unevaluable
OK — 0 stale of 51 plan lock(s) examined (1 non-terminal evaluated · 50 terminal/unevaluable · 0 foreign)

$ python scripts/enforcement/check_plan_lock_release.py --project-root /opt/brand-identiy-creator
1 stale · … · 1 plan-field-stale · …
  STALE LOCK: 2026-08-10-plan-1-deep-research.json its plan is ARCHIVED (Status: "✅ EXECUTED …")
  PLAN FIELD STALE: … plan field '…' does not resolve — Finish step 6 repoint missing
```

The hub line is the plan's own self-referential assertion: the check meets **this plan's active
lock** during its own execution, so `OK` with 1 non-terminal is required there and
`NOTHING VERIFIED` would be a bug.
