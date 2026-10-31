# Spec review — /hibernate pauses FULLY and the box resumes itself (W-6e656dac)

**Command:** /fabrik-spec-review
**Artifact:** `docs/superpowers/specs/2026-10-21-hibernate-full-guarantee-design.md` (DRAFT c4a276480)
**Research ledger:** `docs/reference/research/2026-10-21-hibernate-full-guarantee-ledger.md`
**Partition (shape: agent-tool, D-961):** S1 Opus `fabrik-reviewer` — Chosen approach L1-L6, Decisions taken, Validation,
Constraints Digest, Open unknowns; S2 Sonnet `fabrik-reviewer` — every other section; S3 Sonnet `fabrik-researcher` —
External dependencies and the ledger rows the spec uses. `dispatch_headroom.py --slices opus=2,sonnet=2` granted 3 seats
(quota cap); the spec was cut into exactly three disjoint slices, so the union of the three seats IS the full pass.

## Pass Ledger

| Pass | seats · axes re-checked (intake · personas · facts · vendor · approach · completeness · constraints) | counters | method | spec md5 (start → end) |
|-----:|---|---|---|---|
| Pass 1 | opus×1 + sonnet×1 + sonnet×1 researcher (the round-1 slices) · all axes | found: 30, new: 30, confirmed: 27, fixed: 27, unexecuted: 0, edits: 27 | method: citation — full pass; every candidate executed by the lead (code reads at the cited lines, `crontab -l` census of 46 lines, `claude -v` 2.1.305, `date -d @1792574575` 12:22:55, `ls docs/RESILIENCE.md` absent); 2 duplicates; S3-C2 RECORDED — measured (settings `permissions.defaultMode` is `auto`); S2-C7(c) REFUTED on master (D-1092 is a row there); hygiene: 2 false positives (`RESILIENCE.md` inside `58-resilience.md`) | 998b6af1… → 75cc4ae1… |
| Pass 2 | opus×1 + sonnet×1 + sonnet×1 researcher (the round-1 slice owners) · delta over the pass-1 hunks + one hop | found: 11, new: 11, confirmed: 10, fixed: 10, unexecuted: 0, edits: 10 | method: re-derivation — delta over the pass-1 hunks (349-line diff); S3 all three pass-1 candidates FIXED, no in-hunk defect; S1 N1-N5 and S2 NEW-1/NEW-3 confirmed by reading the cited code (`quota_stop.py:717-722`, `selfwatch_check.py:165-200`, `hibernate.py:345-367`, `claude_rotate.py:8803-8821`); three one-hop reader breaks the pass-1 hunks created (Shape, `agents_up.sh:479` `exec tmux attach`, in-process seats) confirmed; S2 NEW-2 RECORDED — by design (I9 discloses its one change; the approval panel weighs it); own-fix: 10 of 10 (round 1's hunks) | 75cc4ae1… → 870b4553… |
| Pass 3 | opus×1 + sonnet×1 (the round-1 slice owners; S3 had no open claim, restated 19/19) · delta over the pass-2 hunks (127-line diff) + one hop | found: 3, new: 3, confirmed: 2, fixed: 2, unexecuted: 0, edits: 2 | method: re-derivation — delta over the pass-2 hunks; S1 P3-1 confirmed by EXECUTION (`quota_stop._bash_allowed` on a copy: `hibernate.py lift/status/woke` → False, `command_run.py line` → True), S2 NEW-A is the same defect; S1 P3-2 confirmed by reading `hibernate.py:345-367` against the new L3; own-fix: 2 of 2 (round 2's hunks) — SCOPE GROWTH stop fired (2 of the last 3 rounds); class rewrite — L2 T-3 hold-escape sentence (rounds 2, 3) | 870b4553… → 3310927d… |
| Pass 4 | opus×1 (round-1 owner of S1, the section holding both fixes; S2 4/4 and S3 19/19 restated, no open claim) · remainder round after the scope-growth stop: the fixed set P3-1, P3-2 alone | found: 2, new: 2, confirmed: 0, fixed: 0, unexecuted: 0, edits: 0 | method: re-derivation — the fixed set only (the 2-hunk pass-3 diff, `quota_stop.py:100-115` re-read against the allow-list sentence); P3-1 and P3-2 FIXED; P4-1 and P4-2 RECORDED — measured (own-fix raised after the stop, routed below, D-355); standing clean since pass 1: intake, vendor; every class clean at pass 2 | 3310927d… → 3310927d… ✓ |
| Pass 5 | opus×1 + sonnet×1 (the round-1 owners of S1, S2; S3 19/19 restated) · the ONE delta round after the design-approval panel, over the panel-fold hunks (169-line diff) | found: 7, new: 7, confirmed: 0, fixed: 0, unexecuted: 0, edits: 0 | method: re-derivation — the panel-fold hunks only; every accepted panel change verified in place (S2: the three dispatchers exist and launch `claude -p`, step budget still 3); S1 N1, N2, N5, N-W1 real and S1 N3, N4, S2 NEW-P5-1 plausible — all own-fix in the panel hunks raised after the scope-growth stop, so RECORDED — measured onto the routed list below (term-edit's stop: they do not hold the flip) | 11e3a381… → 11e3a381… ✓ → **CONVERGED** |

## Routed to the plan (the scope-growth stop's destination)

Own-fix residue and one-hop observations the stop routed instead of hunting; `/fabrik-plan-after-chat` carries each into
a ticket's acceptance criteria:
- `_armed_sids` returns lock-file names after `_selfwatch_safe`, and raises `NotADirectoryError` with no lock dir — check 6
  compares names in that form and treats the raise as BLOCKS (S1, pass 3).
- an outside-`/opt` agent is never ordered to arm (`selfwatch_check.py:186-187`), so check 6 blocks it every time — the
  arm order or the check must cover it (S1, pass 3).
- `hibernate.py brief`'s "Exit 0 means the box slept" wording and `tests/test_hibernate.py`'s resume-wake-alone path
  change with the "RESUME only after the lift" rule (S1, pass 3).
- `hibernate.py` reaches the tick's `_armed_sids` by import or a vendored copy; the stale-tick fail-open is
  `quota_stop.py`'s, so the `scripts/aro-wake/claude_rotate.py` twin changes only for the stamp clearers and the resume
  leg (S2, pass 3).
- the relaunch's restored permission mode follows `permissions.defaultMode` (`auto` today); a change there changes the
  resumed builders' mode (S3, pass 2).
- P4-1 (RECORDED — measured, own-fix after the stop): only the */5 tick writes `resume-wake`
  (`scripts/sysadmin/claude_rotate.py:3390-3391`), while the minute cron (`:7251-7256`) arms at T-3, so after a lid
  closed before T-3 the first minute cron can arm the tier before the tick sees the sleep — the minute cron must judge
  the wall gap itself (`tick-last-end`, `_resume_gap_s()`) and never arm once T has passed (S1, pass 4).
- P4-2 (RECORDED — measured, own-fix after the stop): with no tier standing, the resume leg's O_EXCL `.holdlifted resume`
  can land before the hibernate lift's fan-out in the same tick, which then counts `pending` — the lift must run first,
  suppress the `resume` fan-out, or overwrite a pending `resume` file (S1, pass 4).
- the hub coordinator's Personas row ("never lifts by hand") must name `lift` as its dead-cron escape, and `lift` should
  check its caller (for example the session that ran `mark`) now that the hold lets every held session run it (S1, pass 4).
- L3 bullet 1 reads "lifts the `hibernate` tier"; the plan's wording is "lifts the pause" (the mark), as the every-lift
  bullet states (S1, pass 4).

- N1 (pass 5): the minute cron writes nothing on a healthy run (`scripts/sysadmin/claude_rotate.py:7251-7254`), so `status`'s
  "log has not moved for 3 minutes" test blocks forever — the minute cron writes a heartbeat file and the check reads it.
- N2 (pass 5): a 7-minute gap is under one ordinary slip (10-11 minutes, `claude_rotate.py:7262-7263`) and below the
  12-minute floor — a missed tick during the drain would lift the pause; the short-close test keeps the floor and needs
  the gap to start after the mark and span T-3, applied the same way by the minute cron.
- N3 (pass 5): the self-watch reads the lift kind before its network gate (`~/.claude/bin/claude-selfwatch.sh:51-59`) — it
  re-reads field 2 after the gate so a replaced `hibernate` file keeps its wording.
- N4 (pass 5): the dead-cron escape needs a live hub session; the operator's plain-shell `lift` is the last resort, and
  the merge-owner lookup inside the hook is a subprocess on the held path.
- N5 (pass 5): `agents_up.sh` is every repo's launcher (`scripts/sysadmin/agents_up.sh:3`), so the watchdog set there
  reaches every repo's builders, and the VS Code coordinators get it from no launcher — the plan names where each
  session class gets it.
- N-W1 (pass 5): `:1089` returns 0 only for a `walled` read (`scripts/sysadmin/quota_posture_hook.py:267-272`); a
  `hibernate` tier added to the known tiers changes the order rationale.
- NEW-P5-1 (pass 5): "the review loops" names no file — the plan names the seat dispatchers by path (and `scripts/claude_p_cost.py`),
  or states the posture hook already covers them.

## Ask ↔ spec comparison (built for the approval panel; recomputed on the closing-round text)

| Operator's words | What the spec says | Anchor | Disposition |
|---|---|---|---|
| "mostly is not enough it must be fully." | six layers; every gap enforced, not announced | § Chosen approach | IN |
| one /hibernate reaches every repo's agents, no data loss, no lost in-flight subagent work, proper resume | L2 drain + L3 wake + L4 restore; seats recorded on the close | § Chosen approach L2-L4 | IN |
| gap (1) headless pool and cron workers never paused | `paused` honoured by hub launchers; status row 1; another repo mailed | L2; § Personas (cron row) | IN |
| gap (2) "BLOCK while a live agent still has a live seat child" | status check 2 | L2 check 2 | IN |
| gap (3) "Name the paths in the row, and have the daily pipelines skip writes while a pause is marked" | status check 3; pipelines skip via `paused` | L2 check 3; L2 T-0 | IN |
| gap (4) "A pause with no sleep has no resume signal. Make lift and woke handle it." | three automatic lift paths; `woke` answers after the lift | L3 | IN |
| gap (5) "BLOCK a paused agent with no seed or RESUME note written since the mark, and have woke print the seed" | status check 5; `woke` prints seeds | L2 check 5; L3 | IN |
| "the brief carries a deadline" | `brief --deadline` prints T-3 and T | L2 | IN |
| (B) "/hibernate --deadline 10m ... An abandoned seat goes into the RESUME note ..." | T-0 intake hold, T-3 hard hold, status shows the deadline and abandoned seats | L2 | CHANGED — the abandoned seat is recorded on its parent's run close and seed, because the T-3 hold blocks writing a RESUME note |
| (C) "work-in-progress pushed at every step boundary ... `claude --resume <its session id>` plus its seed" | step-boundary snapshot (skips to the */15 floor when the lock is held); relaunch with a first prompt | L1; L4 | IN |
| (D) "The same design must work on a cloud VM" | the same layers; the hibernate is an API call after SAFE | L6 | IN |
| "the wake must AUTO-resume every agent once the network and Claude answer" | tick lift + self-watch three-answer gate; check 6 blocks an unarmed agent | L3; L2 check 6 | IN |
| "a lid close without /hibernate is the unplanned case the safety net covers" | L1 durability + the resume wake | L1; L3 | IN |
| "A full shutdown is rare; claude --resume plus the seed covers it." | the sweep builds each grid detached; `--resume` with a prompt | L4 | IN |
| "3 is not a limit ... it can be 10 or more per repo" (D-1092) | no count; registered builders only | L4 | IN |
| drop the sweep's autonomous re-export | the sweep no longer re-exports `CLAUDE_MESH_AUTONOMOUS=1` | L4 | IN |
| "limit management must be dynamic not static ... 10gb ... 0.5gb" | one parent ceiling, no per-agent cap | L5 | IN |
| "this must be managed smartly, what do you suggest" (accounting, box ceiling, no per-agent cap, admission, kill order, swap) | per-pane scope, parent ceiling, admission band, `oom_score_adj`; swap is the operator's | L5; U5 | IN (swap: OUT-OF-SCOPE, a named operator gate) |
| "fabrik-agents.slice reads MemoryCurrent=0 ... Verify why." | measured: the 00:47 panes carry no `systemd-run`; cause U7 | § What exists today; U7 | IN |
| "D-1075's 16G slice at 3G per agent fits only 5 builders" | per-agent cap removed | L5; § Rejected alternatives | IN |
| "we have session recall mcp, do you think agents can use it for proper resume?" | the third resume layer | L4 | IN |
| "autoMemoryReclaim ... swap size ... the operator's call" | a `.wslconfig` gate | U5 | OUT-OF-SCOPE (operator gate) |
| (not asked) Personas, Lifecycle, Constraints Digest, fabrik-lib verdict, Documentation landing sites | the spec contract's mandatory sections | § each | ADDED — `/fabrik-spec` mandates them |
| (not asked) U7, U8 build-step measurements | the uncapped-launch cause and the bus wait are measured before L4/L5 change | § Open unknowns | ADDED — an existing code path is unexplained |

## Design-approval panel (D-613)

Both seats read the pin cold (md5 3310927d…, commit 2fa22fbc6).
- Opus: `VERDICT: sound-with-changes — docs/superpowers/specs/2026-10-21-hibernate-full-guarantee-design.md` — 9 concerns,
  all ACCEPTED and applied in ebf0970a8 (`woke` no-pending-resume; only the hub's `lift` passes the hold; (b) after T and
  two slots; short-close lift; boot launches never refuse; watchdog per launcher; foreground subagent return; reboot and
  network-off drills; L6's operator API step).
- Fable: `VERDICT: sound-with-changes — docs/superpowers/specs/2026-10-21-hibernate-full-guarantee-design.md` — 10
  concerns, all ACCEPTED and applied in ebf0970a8 (the minute cron absent, installed and checked; `start` held past T-3;
  short-close lift; `woke` once-only; abandoned-seat states; `done` row; battery-low lift; boot uncapped launch; seat
  dispatchers check `paused`; the cron-order note).
- Executed before folding: `crontab -l | grep -c -- --battery-tick` → 0; `quota_stop.py:107` admits `command_run.py`
  with any subcommand; `quota_posture_hook.py:1089` returns 0 when a stamp stands.
- Panel: opus="VERDICT: sound-with-changes — docs/superpowers/specs/2026-10-21-hibernate-full-guarantee-design.md" fable="VERDICT: sound-with-changes — docs/superpowers/specs/2026-10-21-hibernate-full-guarantee-design.md" → both-approve
