# Plan review — the command-centre dashboard plan set (W-573fae88)

**Command:** /fabrik-plan-review
**Plan:** `docs/development/plans/2026-10-17-plan-1-command-centre-dashboard/` (spine + T01–T07)
**Spec:** `docs/superpowers/specs/2026-10-16-command-centre-dashboard-design.md` (CONVERGED, D-925; i18n exemption D-926)
**Status:** CONVERGED
**Owner:** infra

## What was reviewed

The whole set — the spine and all seven tickets — partitioned into two disjoint slices (D-212), read by the same two
seats in every round: an Opus seat on the spine's Interfaces, Execution Discipline, Global Constraints, Behavior Contract
roll-up, File Scope and Coverage Checklist plus T02 and T07; a Sonnet seat on T01, T03–T06 and the other spine sections.
Each round's seats read a pinned copy (combined md5 per pass below) beside HEAD copies of every cited file, and every
confirmed candidate was re-run by the orchestrator before it was fixed. The spec is CONVERGED with no `Size: small` line,
so this was the plan-only loop: no joint spec loop and no approval gate (the command's full-size path).

## Pass Ledger

| Pass | Seats | Counters | Method | Hash |
|---|---|---|---|---|
| Pass 1 | opus×1 (spine Interfaces, Execution Discipline, Global Constraints, roll-up, File Scope, Checklist; T02; T07) + sonnet×1 (T01, T03–T06; the other spine sections) · shape: agent-tool | found: 37, new: 37, confirmed: 36, fixed: 36, unexecuted: 0, edits: 7 | method: partitioned full pass; every confirmed candidate re-run by the orchestrator (probe fallback, budget subprocess, sync probe, target eviction, uncached collector, item root, cap/threshold bodies, posture.fleet keys, cites); refuted 1 (sonnet C17 — rule packs are budget-exempt by `check_plan_tickets.py` design) | bf031c20… → 76eb6539… |
| Pass 2 | opus×1 + sonnet×1 (the round-1 owners, own slices over the fix diff 92d945c27 plus one hop) · shape: agent-tool | found: 13, new: 13, confirmed: 13, fixed: 13, unexecuted: 0, edits: 7 | method: re-derivation — 35 of 37 round-1 rows re-executed FIXED, 2 partly fixed and closed by the new rows; new rows re-run by the orchestrator (keys routed to the wrong view, spend key paths, threshold decimals, token-equal tag filter, fail-closed target slices, last-good timestamp, control visibility); 9 of 13 seeded by the round-1 fixes | 27abe834… → cc34cd38… |
| Pass 3 | opus×1 + sonnet×1 (the round-1 owners, own slices over the fix diff e82242c1a plus one hop) · shape: agent-tool | found: 6, new: 6, confirmed: 6, fixed: 6, unexecuted: 0, edits: 5 | method: re-derivation — 13 of 13 pass-2 rows re-executed FIXED; 6 new rows, all seeded by the pass-2 fixes (component attribute reach, typed token filter, T06 filter names, slug/email control rule, last-good time at restart, the restart test the checklist cited); the scope-growth stop fired | 4ad01058… → 83b6e450… |
| Pass 4 | opus×1 + sonnet×1 (the round-1 owners, the six pass-3 rows only — scope-growth remainder round) · shape: agent-tool | found: 1, new: 1, confirmed: 1, fixed: 1, unexecuted: 0, edits: 1 | method: re-derivation — 6 of 6 pass-3 rows re-executed DEFECT_ABSENT (sonnet 4/4, opus 2/2); 1 new row in the same T02 paragraph (the restart test named a rebuild path T07 adds; reworded to today's `_repos_page(fresh=True)`, :2664/:2735) | 95d4e2b5… → 7d458162… |
| Pass 5 | opus×1 (round-1 owner of the only edited paragraph) · sonnet slice re-stated at 4/4, no edit in it since pass 4 · shape: agent-tool | found: 0, new: 0, confirmed: 0, fixed: 0, unexecuted: 0, edits: 0 | method: re-derivation — P4-1 re-executed DEFECT_ABSENT (`_repos_page(fresh=True)` at :2664/:2735 rebuilds both registries; T07 step 3 owns the re-pointed restart test); standing clean since pass 4: every other class | 8d54b4df… → 8d54b4df… ✓ → **CONVERGED** |

## Outcome

- Confirmed and fixed: 36 → 13 → 6 → 1 → 0. Round 1 found the plan's structural gaps (the views could not reach the
  configuration and formatters the old builders used; no ticket owned the widgets' JavaScript; a probe failure never
  reached the views; a request-thread subprocess and probe; target eviction between views; an uncached collector).
  Rounds 2–4 were seeded by the fixes, and the scope-growth stop fired at round 3; round 4 re-verified the fixed set
  alone and round 5 closed quiet.
- Refuted: 1 (round 1, sonnet C17 — rule packs are dropped from the READ budget by `check_plan_tickets.py`'s design).
- Breadth screen: 7 of 7 tickets flagged; all kept, one reason each, in the spine's § Ticket breadth.
- Plan-set gate at the flip: `check_plan_tickets --plan-dir` → graded 7 ticket(s), 32 Touches path(s), 36 Context-Files
  entry(ies); 0 finding(s).
- Combined md5 of the set after the flip: 9c934958ac2a5979b91828ee6b9e274d (before the Status line: 8d54b4df21e6bd55db3cd2d0eab57e73).
- One mechanical edit after the flip: a T02 test bullet's label `Status:` renamed `Probe state:` because
  `check_convergence.py` reads a ticket line starting `Status:` as a ticket status; no meaning changed. Combined md5
  after it: 5b6e9b8f17a74fc5d28edf29bdfcb991.
