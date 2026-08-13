# Review — 2026-08-13-plan-1-standby-survivable-sweep

Scope: the whole-plan cumulative surface — repo diff `218734cb..HEAD` (`session_orient.py`
[SYNCED], `ci_fix_dispatcher.py`, both test files, hooks-index, CHANGELOG) + the box surfaces
(`claude-reboot-sweep.sh` REWRITTEN + `claude-mesh-test.sh` §RS — DR-versioned, not git).
Single-phase plan: this step-6 loop is the phase review and the whole-plan review.
Surface: HEAD=50e6cd7fd0200c8b91529b357fdd3fb55b357d07 · git-diff-md5=92cea29f7d4baa089864865d7a31fc5c (box surfaces DR-versioned, hashed by the DR
snapshots cited below).

## Phase A — verdict: CLEAN-CONVERGED ✅

Closing state: **found: 0, fixed: 0** on the production surface — round 7 (Pass 7) verified the
final code edit by independent simulation of all six truth-table rows (verdict verbatim:
"arithmetically confirmed … all six named rows behave as intended"); its two raised items were
FIXTURE-scoped (an uptime-coupled fixture + a missing union-branch pin), fixed in wave 5 and
mechanically verified by the harness (152/152 — the gates' job, per the termination contract's
mechanical-gates clause). Five fix waves total; every load-bearing fix red-on-revert-proven or
watched RED first.

Rubric run (Phase-0 step 2):

```
$ python scripts/review_rubric.py --changed .claude/hooks/session_orient.py scripts/ci_fix_dispatcher.py tests/test_session_orient_hook.py
# FLOOR (always injected): core/35-security-auth · core/25-data-postgres · core/30-ops · 12-Factor.
# MATCHED: core/10-python (hook code) — fail-open discipline, stdout-only, bounded reads.
```

FLOOR auth/postgres classes are CONTEXT (no DB/HTTP surface here); the binding classes are the
standing recurrence set, adjudicated below.

## Coverage Checklist

| Class | Verdict |
|---|---|
| fail-open vs fail-closed (orient marker write, sweep guards, Leg B) | **FIXED(3)→CLEAN** — orient fail-open pinned incl. ORIENT-still-prints (F13); no-claude skips only the marker leg LOUDLY (F7, RS12); flock degrade is loud (F18-adjacent) |
| boundary/sentinel/prefix (glob-break, fd inheritance, /tmp sentinel race) | **FIXED(4)→CLEAN** — gather-list union (F2/F4-pool), lock fd closed in children (F3, RS8c red-on-revert), fresh-boot gate = uptime OR lockdir (confirm-round race finding; RS11/RS11b + neutered-copy probe: 0 notifies reverted, correct notify current), sidecar `! -path` exclusion (F1/F2, RS10d de-vacuized with cwd-bearing sidecars) |
| second-writer safety | **FIXED(3)→CLEAN** — atomic `mv` claim (F5/F6-pool, RS9/RS9c), sweep self-flock (RS8/RS8b), Leg-A-resumed sids excluded from Leg B (F6-closer, RS14/RS14b) |
| behavior-without-a-test | **FIXED(9)→CLEAN** — confirm-round found 6 fixes green-on-revert → pins added: RS11/11b/12/12b/12c/13/14/14b + writer↔sweep default-dir contract test (F12) + stale-both-dirs (F5-confirm) |
| cost/quota/limit accounting | CLEAN — the ≤20-scan budget was the F2 starvation finding (sidecars consumed 19/20 live slots); fixed by exclusion; prune bounds state-dir litter (F16), unconditional after the confirm round |
| doc-truth (hooks-index, CHANGELOG vs live code) | FIXED(2)→CLEAN — sweep clause moved to its own §2b cron section (F20: it is not a StopFailure hook); counts + behaviors re-synced after each wave (135→143 final) |

## Pass Ledger

| Pass | scope | finders | found | new | fixed |
|---|---|---:|---:|---:|---:|
| Pass 1 (impl round) | rewritten sweep vs plan | pool deepseek-v3.2-exp (scored 3) | 7 | 7 | 1 (flock-degrade note; 1 REFUTED empirically — `cut -f2-` preserves spaced paths; rest self-resolved/immaterial) |
| Pass 2 (wide, non-author) | whole delta + docs + fixtures vs live corpus | native Opus fabrik-reviewer | 20 | 20 | 0 |
| — fix wave 1 | sweep F1/F2/F3(fd)/F4(gate)/F6(dedupe)/F7(no-claude)/F14(twins)/F16(prune)/F17 + repo F8(ruff)/F12(contract)/F13(orient-prints) + F20(docs) + 6 pin fixtures watched RED | — | — | — | 15 |
| Pass 3 (confirm, non-author) | the fix wave + surroundings | native Opus fabrik-reviewer | 5 | 5 | 0 (gate RACE, RS10d vacuity, prune coupling, 6 green-on-revert fixes, stale-half unpinned) |
| — fix wave 2 | uptime-leg gate + unconditional prune + corpse-clear + no-claude wording + RS10d de-vacuization + pins RS11-RS14 | — | — | — | 5 |
| VERIFY | red-on-revert: neutered copy (no sidecar filter, lockdir-only gate) vs current on the race scenario | orchestrator probe | — | — | 0 notifies neutered / correct notify current |
| Pass 4 (closing attempt 1, non-author) | whole current sweep + RS fixtures | native Opus fabrik-reviewer | 4 | 4 | 0 (reviver-interlock kill CONFIRMED · uptime set-u death CONFIRMED · false "notified" stamps for non-/opt PLAUSIBLE · fixture gaps) |
| — fix wave 3 | reviver-pending guard + loud no-uptime degrade (boot=0 inert) + /opt pre-gate with honest cut-unnotifiable/cut-no-cwd notes + pins RS15×3/RS16×3 (RS16b watched RED through 3 diagnostic iterations — the head-20 rank trap) | — | — | — | 4 |
| VERIFY | red-on-revert: reviver interlock (neutered: .reviving destroyed + double-spawn / current: survives + 0) | orchestrator probe | — | — | ✓ |
| Pass 5 (closing attempt 2, non-author) | wave-3 edits + boot=0 semantics + regression sweep | native Opus fabrik-reviewer | 3 | 3 | 0 (mesh-notify child DRAINS the scan heredoc — one notify per boot, probe-proven · RS16 first assert non-discriminating · boot=0 reviver residual) |
| — fix wave 4 | `</dev/null` on the notify call + boot-independent 2100s reviver freshness + RS17 multi-notify pin | — | — | — | 3 |
| VERIFY | red-on-revert: stdin drain (neutered: 1-of-3 notified / current: 3-of-3); harness 150/150 | orchestrator probe | — | — | ✓ |
| Pass 6 (closing attempt 3, non-author) | wave-4's two edits + full fd-0 audit of Leg B | native Opus fabrik-reviewer | 1 | 1 | 0 (2100s window narrower than a reviver's real quiet stretch — fail-open mid-uptime) |
| — fix wave 4b | union guard: skip when FRESH (<2100s) OR POST-BOOT; corpse = both dead | — | — | — | 1 |
| Pass 7 (CLOSING, non-author, micro) | the union edit — truth table sim, set-u, RS15/RS17 quality | native Opus fabrik-reviewer | 2 (both FIXTURE-scoped; production rows sim-CONFIRMED correct) | 2 | 0 |
| — fix wave 5 (fixtures only) | R1 boot-relative (was uptime-coupled) + RS15d union-branch pin (uptime-gated) | — | — | — | 2 |
| VERIFY (mechanical) | harness 152/152 fresh; repo suites 23/23 fresh; production surface untouched since Pass 7's sim | harness + pytest | 0 | 0 | — → **quiet close** |

`new:` trend 7→20→5→4→3→1→2(fixture-only) — falling on the production surface to 0, no stall.

## Adjudicated findings (recorded, not fixed — each with its reason)

- **F15 (revived CI-fix worker semantics):** the sweep's `claude -p --resume` carries no
  `--dangerously-skip-permissions`, so a revived CI-fix worker CANNOT use tools — the
  "resurrected stale brief pushes a superseded fix" scenario (F15b) is refuted by the missing
  flag itself; the residual (F15a) is one wasted revival session, minor and bounded by the
  marker consume. Recorded for the dispatcher's owner to improve (a `--resume`-aware brief).
- **F19 (`now` drift):** minutes of drift against a 24h stamp window and a 300s liveness window,
  drift direction conservative (skip-still-live). Immaterial.
- **F18 (exec stderr in sweep.log):** the failure line in the log IS the signal; cosmetic.
- Confirm-round edge (c): `.claimed` orphans from non-fresh boots are pruned at the next genuine
  boot — and an orphaned claim is semantically consumed anyway (the atomic-claim design).

## The decisive proofs

```
$ # red-on-revert (race gate + sidecar filter neutered in a copy; real cut session + sidecar seeded):
NEUTERED (lockdir present, young boot): 0 notifies   <- the incident recurs silently
CURRENT: 💀 ... Resume: claude --resume realsess1    <- exactly the real session, sidecar excluded
```

Harness 114→152 (38 new asserts, every behavioral one watched RED or red-on-revert-proven);
repo tests 23/23 + ruff clean; fleet-sync verified (hub md5 == 48 project copies, closer-probed;
2-project spot check post-commit). DR snapshots: 20260813T103052Z / 110616Z / 112257Z.

## Final gate (verbatim, run in the sealing turn)

```json
{"status": "success", "tier": 2, "passed": 47, "failed": 0}
```

(Repo full suite: 3041 passed; the 12 failures are `tests/test_state.py` — a sibling's surface,
not in this plan's File Scope, left per the shared-tree contract.)
