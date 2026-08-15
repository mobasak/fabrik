# Per-account weekly caps — review ledger

Operator requirement 2026-08-15: ob@'s weekly quota capped at 90% for fleet use — the
remainder reserved for their claude.ai browser sessions. Mechanism: `<fleet_root>/caps.json`
`{"<email>": <weekly-cap>}` on the live pointer-rotation system.

## Round 1 (2026-08-15)

Surface: commit 651dd317 on 1075e97f (branch feat/account-caps, +493/−30, 9 red-first
tests; 220/220 re-run by orchestrator, twins 484fb2be; the coder's original worktree died
with a session-limit kill — recovered clean-slate, zero loss). Finders: pool
deepseek+gemini (diff inline) + native opus (worktree probes incl. the exact live board
scenario + 3 mutants).

| # | Finding | Source | Disposition |
|---|---|---|---|
| 1 | `_validated_pick`'s live re-verify omits the near-threshold churn check the same diff added to the selector — a stale-cached candidate live-verifying to 97% (under cap, under 100) is flipped to, then re-trips flip-away next tick (probe: cached-50/live-97 flipped) | gemini + opus CONFIRMED (independent) | **FIX (F-C1)**: ONE shared predicate `_flip_churn_excluded` consumed by both sites |
| 2 | caps.json keys matched case-sensitively with zero cross-validation — `{"SARP@…": 90}` vs pinned `sarp@…` silently does nothing (violates the loader's never-silent contract) | opus CONFIRMED (probe: no cap, no warning) | **FIX (F-C2)**: lowercase at both boundaries + "matches no account — cap inactive" warning |
| 3 | Cap-tripped flip ledgers `at_pct = max(session, weekly)` — probe 93/91/cap90: printed line says weekly≥cap, ledger says 93 (misattributed audit) | opus PLAUSIBLE | **FIX (F-C3)**: at_pct = the tripping value on a cap trip; legacy hot otherwise |
| 4 | Selector-layer `weekly == cap` boundary unpinned — `>=`→`>` mutant survived all 9 tests | opus NIT (code correct, coverage gap) | **FIX (F-C4)**: boundary tests at both layers, each killing exactly its own mutant |

Refuted: exact-boundary semantics (>= consistent everywhere; reserving AT the cap is the
operator-safe reading of "not more than 90%") · cap > threshold (min() flips EARLIER —
over-reserves, never under; fail-safe) · the near-threshold "lockout" scenario (staying on
a weekly-hot account beats flipping onto a session-hot one that walls mid-dwell; session
windows reset within hours and the tick re-evaluates every 5 min — accepted conservative
behavior) · loader edges all per contract (int truncation is the stricter/safe direction).
Non-interference grep+probe clean (keepalive/identity net/liveness gates take no cap input).

Round 1 verdict: NOT CLEAN — F-C1..F-C4 dispatched.

## Round 2 (2026-08-15) — orchestrator verification, declared

Surface: fixup commit 725788a3 (+311/−57, 6 new tests; 226/226 re-run by orchestrator,
twins 1c26182f). Coder's evidence: each fix red-on-revert vs 651dd317; each F-C4 mutant
killed by exactly its own named test. Orchestrator live probes: the shared predicate
exists and BOTH sites consume it (inspect.getsource); truth-table spot-checks (live-97
excluded, 90==90 excluded, 89.9-under-90 kept); case-normalized loader load verified.
Beyond-brief notes accepted: doubly-loud corrupt-caps warning (fail-direction compliant);
single ROTATE_THRESHOLD read per call.

Round 2 verdict: **CLEAN** — merge.

## CLOSE

2 rounds, 4 fixes, 15 tests added (211 → 226). Final surface: worktree commits
651dd317 + 725788a3 squash-applied to master as ONE commit. Suites at merge re-run on the
MERGED tree. Box activation: `~/.claude-fleet/caps.json` `{"ob@ocoron.com": 90}` written
at rollout, verified live on the status board. Accepted residuals: the conservative
near-threshold selection (documented above) · advisory (85%) independence from caps
(deliberate — the advisory warns approach-to-wall regardless of reserve policy).
