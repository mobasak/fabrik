# Review — auto-continuation (resume-mesh) full implementation · 2026-08-09

Scope: the complete auto-continuation stack the operator asked to verify as "100% functional and
correctly designed": `~/.claude/bin/{claude-sound.sh, claude-stop-decider.py, claude-autoresume.sh,
claude-selfwatch.sh, claude-mesh-test.sh}` + fleet-synced `.claude/hooks/session_orient.py` (arm
order, commit 50675991) + `tests/test_session_orient_hook.py` + `~/.claude/settings.json` StopFailure
wiring + `docs/workstation/hooks-index.md` rows. Anchored on the prior reviews
`2026-08-09-plan-2-resume-mesh-review.md` and `2026-08-09-session-work-review.md` (surface CHANGED
since: waker-loss bridge, rotation opt-in-OFF, mesh-notify .env fix, ORIENT arm order, first live
production firing this evening).

Surface: 506759916f637371104841bdec0f291de0fa71f0 + working-tree d41d8cd98f00b204e9800998ecf8427e
Out-of-repo surface (md5): sound=3cfdd39f12b34568f80e30f9dca3f6f6 ·
decider=349db1b80ca8d18baf77caa27f3b7e0c · autoresume=c82d4a42175459fbecfa664c3efdd69e ·
selfwatch=498fa949d0b9e0623629b4e84199ca30 · harness=51539039542c8f4a2ab9203cf9ead233

## Rubric (verbatim `review_rubric.py --changed .claude/hooks/session_orient.py tests/test_session_orient_hook.py docs/workstation/hooks-index.md scripts/wip_backup.sh` — floor shown; surface is workstation shell/python, server-only rows adjudicated N/A honestly)

```
FLOOR: core/35-security-auth (fail-closed invariant, no secrets in code, config via env) ·
core/25-data-postgres (N/A — no DB surface) · core/30-ops (immutable releases, stdout logs,
env-layer config) · 12-FACTOR all twelve axes (applicable here: III config-as-env · XI logs-to-
stdout/bounded · V immutability · IX disposability/idempotent re-fire)
Full verbatim floor output retained in session; server-only rows (compose/Traefik/Alembic/
sticky-sessions/SQLite-backing) map to no code in this surface → N/A rows below.
```

## Coverage Checklist

| # | Class | Verdict | Evidence |
|---|---|---|---|
| 1 | Marker lifecycle / state machine (errparked·reviving·attempts·recheck·rungsize·compacting·notified·rotation.last) — stale-state, spurious-fire, deadlock | UNCHECKED | |
| 2 | Fail-open vs fail-closed on every gate/guard (connectivity gate, opt-in gates, decider fail-ring, marker-abort) | UNCHECKED | |
| 3 | Concurrency & races (start.lock mutex, lock supersede, double-arm, sleeper vs live session, two watchers one sid) | UNCHECKED | |
| 4 | Cost/quota/limit accounting edges (attempt counter unknown≠0, cap 2, backoff classes, rotation limiter, quota-wall interplay) | UNCHECKED | |
| 5 | Boundary/sentinel/prefix collisions (sid sanitization, empty sid, marker filename collisions, "-" sentinels, /opt/ prefix gate) | UNCHECKED | |
| 6 | Error-matrix completeness (all 10 enum classes routed correctly at EVERY layer: sound families · rotation gate · 2a spawn gate · autoresume human-only · selfwatch backoff/network-gate · waker_lost) | UNCHECKED | |
| 7 | Behavior-without-a-test (harness 42 fixtures + orient tests + decider self-test vs the real behavior set incl. live-fire shape) | UNCHECKED | |
| 8 | Test quality (would fixtures fail if behavior broke; mock-theatre; vacuous asserts) | UNCHECKED | |
| 9 | Injection/quoting safety (payload → bash -c, env passthrough, jq fallbacks, Telegram token handling) | UNCHECKED | |
| 10 | 12-Factor applicable axes: III config-as-env · XI logs (bounded, stdout-or-bounded-file for hooks) · V immutability · IX idempotent re-fire | UNCHECKED | |
| 11 | Doc truth (hooks-index rows vs shipped behavior; comments vs code; spec vs implementation) | UNCHECKED | |
| 12 | Fleet blast radius of the synced surface (session_orient arm order correct for ALL ~46 projects incl. boxes without the mesh, headless runs, compact-resume) | UNCHECKED | |
| 13 | N/A rows (rubric floor items with no code in this surface): DB/RLS/Alembic · compose/Traefik/ports · sticky sessions · SQLite backing | N/A | no DB, no compose, no server processes in scope |

## Pass Ledger

(filled per pass; VERIFY runs labelled VERIFY, never numbered)

## Disposition ledger

(every candidate raised by any finder — one row each, FIXED or REFUTED)
