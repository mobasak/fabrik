# Plan review — the /hibernate full-guarantee plan set (W-6e656dac)

**Command:** /fabrik-plan-review
**Plan:** `docs/development/plans/2026-10-21-plan-1-hibernate-full-guarantee/` (spine + T01a, T01b, T02, T03a, T03b, T04, T05, T06; DRAFT at 4d70c3095)
**Spec:** `docs/superpowers/specs/2026-10-21-hibernate-full-guarantee-design.md` (CONVERGED, D-1095)
**Shape:** agent-tool (D-961: the Workflow tool is never called)
**Status:** CONVERGED

## Pass Ledger

| Pass | seats · scope | counters | method | set md5 (start → end) |
|-----:|---|---|---|---|
| Pass 1 | opus×1 (T01-T02-T06 + the spine's rule sections) + sonnet×1 (T03a-T03b-T04-T05 + the rest) · shape: agent-tool (D-961) · full pass | found: 34, new: 34, confirmed: 33, fixed: 33, unexecuted: 0, edits: 33 | method: citation — full pass; the lead executed the decisive claims (`grep oom_score` → 0 in the plan; `final_gate_stop.py:4849-4854` requires `_tick.exists()`; `quota_posture_hook.py:1089` returns before `decide`; `claude-mesh-test.sh:10` defaults SRC to `~/.claude/bin` and `:19` copies two untracked files); S2-C11 REFUTED (conftest pins `ROTATE_STATE_DIR` per test, `tests/conftest.py:275`); fixes: T01 split into T01a/T01b, T04 after T05, 17 rows added, the docs moved to T06 | 42e5208a… → f29f29ad… |
| Pass 2 | the round-1 seats on their own slices over the fix diff · shape: agent-tool (D-961) · delta | found: 21, new: 21, confirmed: 18, fixed: 18, unexecuted: 0, edits: 18 | method: re-derivation — S1 EXECUTED its N1 (a scratch `claude_rotate.py` tick turned `0 hibernate` into `0 walled` under the `battery_held` fix); the lead read `hibernate.py:186-194` (8-hop, agents-only walk), `agents_up.sh:16` (the `pane <name> <sid>` line) and `claude-selfwatch.sh:55` (the kind read); fixes: the advisory returns before `_touch_stamp`, `_clear_stamp` re-reads under the flock, the lift walk goes to pid 1 and needs a terminal, (a) spans T-3, the migration is a gated step with `lifted_at`=`paused_at`, the harness reads `$PWD`, Leg B skips `.boot-relaunched`, the CI worker is armed, the slice rename's docs are in T06; RECORDED: S2-R1 (a sub-8G box keeps the old ceiling — the stated choice), S2-R2 (whether `--print` refuses uncapped — T05's coder), S2-R3 (review loops dispatch through the Agent tool, which T02 denies) | f29f29ad… → c693e103… |
| Pass 3 | the round-1 seats on their own slices over `fix-p2.diff` · shape: agent-tool (D-961) · delta | found: 3, new: 3, confirmed: 2, fixed: 2, recorded: 1, unexecuted: 0, edits: 2 | method: re-derivation — S2 quiet (every N/R item FIXED, anchors opened); S1 EXECUTED its N1 re-probe (`0 hibernate` survives all three ages) and NEW-A (a second `LOCK_EX` in one process blocks); fixes: every clear runs after `update_marker` returns, an `sdk-*` caller is refused before the name check, a plain-shell lift writes a `hibernate-lift-shell` row (the tmux gap recorded in § Residual unknowns) | c693e103… → f1f004fb… |
| Pass 4 | opus×1 (S1's round-1 owner; S2 verified 41/41 at its pass-3 zero) · `fix-p3.diff` + one hop · shape: agent-tool (D-961) · closing | found: 0, new: 0, confirmed: 0, fixed: 0, unexecuted: 0, edits: 0 | method: re-derivation — NEW-A and NEW-B(1) re-read FIXED, the NEW-B(2) residual text checked accurate; anchors opened (`hibernate.py:511` `if a.verb == "lift":`, `claude_rotate.py:7437` `def _wake_held_sessions(`); every Coverage Checklist row adjudicated; `check_plan_tickets` 0 findings on the pin; the only edit since the p4 pin is the pass-3 row's counters (fixed 3 → 2, recorded 1), a ledger correction | f1f004fb… → d452eb21… |

## Findings

| Id | Pass | Anchor | Verdict |
|---|---|---|---|
| S1-C1 | 1 | T06 — no clear of a lifted mark's tier; arm/lift race across two locks | FIXED r1 (the arm under `update_marker`'s flock with a re-read; the tick clears a hub-lifted tier) — part (ii) FIXED r2 |
| S1-C2 | 1 | T06 — the wall advisory would rewrite the hibernate stamp | FIXED r2 (r1's `battery_held` fix rewrote it to `walled`, probed; the advisory now returns before `_touch_stamp`, re-probed r3 over three ages) |
| S1-C3 | 1 | T06 — the Stop hook's hold on a MISSING tick log | FIXED r1 |
| S1-C4 | 1 | T02 — the posture check placed after the :1089 return | FIXED r1 |
| S1-C5 | 1 | T06 — receipt N2 (the gap starts after the mark and spans T-3) | FIXED r1 (start) + r2 (spans T-3) |
| S1-C6 | 1 | T06 — lift leg vs resume leg order | FIXED r1 |
| S1-C7/C8 | 1 | missing Behavior Contract rows (paths b/c, walled→hibernate, hand-back, battery_lift, episode skip, heartbeat; checks 3-5, double read, woke 24 h, seat states, brief deadline) | FIXED r1 (17 rows) + r2 (the `_battery_lift` row) |
| S1-C9 | 1 | test_hibernate.py :345, :432 need armed-lock and heartbeat fixtures | FIXED r1 |
| S1-C10 | 1 | marker_path vs the Box fixture's home | FIXED r1 |
| S1-C11 | 1 | `lift --self` fakeable; sid→name mapping unstated | FIXED r1 (ancestor walk) → opened N2 |
| S1-C12 | 1 | the stale 12:22 marker would fan RESUME out to all | FIXED r1 (migration) → opened N3, N4 |
| S1-C13 | 1 | crontab line without redirect; gate 3 not capped | FIXED r1 |
| S1-C14 | 1 | twin/aro-wake fail-open on a missing hub path | FIXED r1 (lift leg) + r2 (arm) |
| S2-C1/C2 | 1 | T04 gate ran the live ~/.claude/bin copies; the untracked mesh files | FIXED r1 (`MESH_TEST_SRC`) → opened S2-N1 |
| S2-C3 | 1 | no `<why>` source for the wake line | FIXED r1 (`lift_path` read from the marker) |
| S2-C4 | 1 | `agents_bat.py --list` name vs path; the `--print` probe at boot | FIXED r1 |
| S2-C5/C6 | 1 | MemTotal guard and rounding; the admission band's unknown inputs and default | FIXED r1 |
| S2-C7 | 1 | the child slice nests only by its dashed name | FIXED r1 (`fabrik-agents-tests.slice`) → opened S2-N3 |
| S2-C8 | 1 | the `oom_score_adj` kill order in no ticket | FIXED r1 (panes, seats) + r2 (the CI fix worker) |
| S2-C9/C15 | 1 | AFTER-EDIT docs not in any ticket | FIXED r1 |
| S2-C10 | 1 | test_agents_up.py pins unnamed | FIXED r1 |
| S2-C11 | 1 | launcher tests would read the real marker | REFUTED (conftest pins `ROTATE_STATE_DIR` per test, `tests/conftest.py:275`) |
| S2-C12/C14 | 1 | launcher fail direction; dispatcher watchdog env | FIXED r1 |
| S2-C13 | 1 | other `claude -p` spawners unnamed | FIXED r1 (each named with its reason) |
| S2-C16/C17/C18/C19/C20 | 1 | sink and bus-wait default; T04 merging before T05; the live-file orient test; Leg B notice; hygiene and anchors | FIXED r1 |
| S1-N1 | 2 | the r1 advisory fix itself rewrote the stamp | FIXED r2 (see S1-C2) |
| S1-N2 | 2 | the lift walk: 8 hops, agents only | FIXED r2 (to pid 1, any claude session, a terminal for a plain shell) |
| S1-N3/N4 | 2 | `lift_path=migration` outside Interface M; the hand write ungated | FIXED r2 (value added, `lifted_at`=`paused_at`, `woke` ignores it, the fourth gated step) |
| S1-N5 | 2 | § Breadth decisions T03a wording | FIXED r2 |
| S2-N1 | 2 | T04 gate hard-coded the infra worktree | FIXED r2 (`$PWD`) |
| S2-N2 | 2 | the CI fix worker unarmed | FIXED r2 |
| S2-N3 | 2 | the slice rename's docs unowned | FIXED r2 (T06) |
| S2-N4 | 2 | Leg B had no sid list | FIXED r2 (`.boot-relaunched` from `agents_up.sh --print`) |
| S2-N5/N6 | 2 | T04 row anchors; the stale Evidence paste | FIXED r2 |
| S2-R4/R5/R6 | 2 | `paused` exit 2 vs `read_marker`; harness line; Self-audit L1/L5 | FIXED r2 |
| S2-R1 | 2 | a sub-8G box keeps the 16G ceiling | RECORDED — the stated design choice |
| S2-R2 | 2 | does `--print` refuse an uncapped start | RECORDED — T05's coder |
| S2-R3 | 2 | the review loops among seat dispatchers | RECORDED — they dispatch through the Agent tool, which T02's posture deny covers |
| S1-NEW-A | 3 | a clear inside `update_marker`'s callback self-deadlocks the tick | FIXED r3 (every clear after it returns; probed) |
| S1-NEW-B(1) | 3 | an `sdk-*` seat inherits the merge owner's CLAUDE_AGENT | FIXED r3 (refused before the name check) |
| S1-NEW-B(2) | 3 | a lift from a fresh tmux window reads as the operator's shell | RECORDED — accepted residual, made auditable (`hibernate-lift-shell` row; spine § Residual unknowns) |
| S2-p3 | 3 | `.boot-relaunched` recreates the lockdir before Leg B's freshness signal | RECORDED — T04's coder: evaluate `lockdir_missing` before writing the file |

**Carried to /fabrik-execute-plan (builder notes, not defects):** S2-R2 (T05 — whether `agents_up.sh --print` refuses an
uncapped box during `.bat` generation) and S2-p3 (T04 — read `lockdir_missing` before creating `.boot-relaunched`).

## Gates at the flip

```
$ .venv/bin/python -m scripts.enforcement.check_plan_tickets --plan-dir docs/development/plans/2026-10-21-plan-1-hibernate-full-guarantee
✓ [plan_tickets] /opt/fabrik/.claude/worktrees/infra/docs/development/plans/2026-10-21-plan-1-hibernate-full-guarantee: graded 8 ticket(s), 53 Touches path(s), 37 Context-Files entry(ies); READ budget measured against /opt/fabrik/.claude/worktrees/infra; 0 finding(s)
```

The breadth advisory flags T01a, T01b, T02, T03a, T04, T05 and T06 (score ≥ 5); each is kept with its reason in the spine's
§ Breadth decisions. No approval panel: a full-size spec's plan review carries no approval gate (`fabrik-plan-review.md`
§ Phase 0, "fully autonomous").
