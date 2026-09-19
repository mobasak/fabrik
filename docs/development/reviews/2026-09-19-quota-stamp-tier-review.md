# Review — D-306, the fleet-exhausted stamp carries its tier

**Status:** IN-PROGRESS
**Surface:** `HEAD=e9abe0b35f4aeaec9f400937221a1e55c6d5e239` + `git diff HEAD | md5sum = 9675de813cae3603f99a1423dc30760e`
**Surface (the reviewed RANGE, which is what the seats are pinned to):** `623c00cfb..e9abe0b35` over 11 paths; `md5(surface.diff) = 33d803b3df363d3a43ad6f80d498a47c`, 1003 diff lines, 586 insertions / 54 deletions.
**Anchor:** NO prior report matches. The newest reviews in `docs/development/reviews/` are for other scopes (the 2026-09-18 fable-band-clamp review is the adjacent D-295 surface, not this one; `command grep -l 'D-306'` over that directory returned nothing). This run therefore takes the **full WIDE pass 1**, not the verification-and-delta path.

⚠️ The `git diff HEAD` half of the surface hash is **unstable by construction on this tree**: infra is working concurrently and holds ~18 dirty paths, none of them on this surface. The RANGE md5 is the pin every seat receives.

## What is under review

The `fleet-exhausted` stamp is written on two different events — `walled` (a window at/over `ROTATE_THRESHOLD`, its `caps.json` cap, or 100) and `urgent-90` (the session window at `ROTATE_URGENT_DRAIN_PCT` with no VALIDATED successor, up to ten points earlier). `quota_stop.py` read only `.exists()`, so the warning armed the same fleet-wide default-deny as the wall. The change puts the tier the ledger row already carried onto line 2 of the stamp and makes each reader act on it.

## Rubric (verbatim, `python scripts/review_rubric.py --changed <the 11 paths>`)

Full output pinned at `<scratchpad>/review/rubric.txt` (16,811 B). Its class structure:

```
## FLOOR — always injected, regardless of glob (spec L3; TOOLING surface)
### core/10-python.md
### 12-FACTOR (all twelve axes)
## MATCHED — packs whose globs hit the changed paths
### core/40-documentation.md  (hit: CLAUDE.md, docs/workstation/claude-account-rotation.md, docs/workstation/hooks-index.md)
### core/45-testing-strategy.md  (hit: tests/test_claude_fleet.py, tests/test_quota_posture.py, tests/test_quota_stop_hook.py)
# promote-to-check_*: 34 injected mandate(s) look deterministically greppable
```

## Coverage Checklist

| # | class / file | state |
|---|---|---|
| 1 | `.claude/hooks/quota_stop.py` — the fleet-synced hold (tier reader, `decide(tier=…)`, `_nudge`) | UNCHECKED |
| 2 | `scripts/sysadmin/claude_rotate.py` — writer (`_stamp_body`/`_stamp_tier`/`_hold_is_wall`, advisory write, `_rearm_wall_stamp`, `hold.tier`) | UNCHECKED |
| 3 | `scripts/aro-wake/claude_rotate.py` — the byte-identical twin | UNCHECKED |
| 4 | `scripts/sysadmin/quota_posture_hook.py` — `_live_tier`/`_wall_stamp_stands`, the CHECKPOINT clause | UNCHECKED |
| 5 | `CLAUDE.md` — the WALL sentence | UNCHECKED |
| 6 | `templates/governance/CLAUDE.md` — the same, fleet-distributed | UNCHECKED |
| 7 | `docs/workstation/claude-account-rotation.md` | UNCHECKED |
| 8 | `docs/workstation/hooks-index.md` rows 105/106/111 | UNCHECKED |
| 9 | `tests/test_claude_fleet.py` — six new graders + four re-pinned assertions | UNCHECKED |
| 10 | `tests/test_quota_stop_hook.py` — four new graders | UNCHECKED |
| 11 | `tests/test_quota_posture.py` — three new graders | UNCHECKED |
| S1 | STANDING — fail-open vs fail-closed on every gate/guard | UNCHECKED |
| S2 | STANDING — cost/quota/limit accounting edges (unknown≠0, per-call vs batch) | UNCHECKED |
| S3 | STANDING — boundary/sentinel/prefix collisions | UNCHECKED |
| S4 | STANDING — behavior-without-a-test | UNCHECKED |

## Orchestrator round-zero probe (D7/D10 — before any seat returned)

Every production line this change adds was re-read WHOLE. Two candidates, both the author's own:

**F-O1 · MED · CONFIRMED by execution** — `.claude/hooks/quota_stop.py::_nudge` and
`scripts/sysadmin/quota_posture_hook.py::_CHECKPOINT` both assert **"nothing is held"**, and at the very
state they are written for that is FALSE. Driven end to end against a fixture `ROTATE_STATE_DIR` with a
posture whose band is RED (weekly 99% of a 99 cap, no successor) and a stamp at tier `urgent-90`:

```
posture hook stdout: {"hookSpecificOutput": {… "permissionDecision": "deny",
  "permissionDecisionReason": "QUOTA RED fleet-wide — on mob seven_day is 99% (reset in 24:00). Fleet-wide NO ac…
quota_stop stdout: (no deny)
quota_stop stderr says 'Nothing is held yet': True
prompt line: QUOTA: mob · 5h 92% … band RED on 5h and weekly … · ⚠️ CHECKPOINT NOW — the fleet is at the
  urgent-drain line with no account to rotate to; nothing is he…
```

`quota_stop.py` correctly allows; `quota_posture_hook.py` correctly denies `Agent` on the RED band — that
denial is the gap this change deliberately closed. But the two messages the agent reads at that instant say
it is free. The claim to fix is the WORDING, not the behaviour: what is true is that the fleet's hard hold
has not armed, not that nothing is held.

**F-O2 · LOW · CONFIRMED by reading** — `.claude/hooks/quota_stop.py` module docstring, first paragraph:
still reads "written by `claude_rotate.py::_fleet_active_wall_advisory` when the ACTIVE account is walled
and the picker found no successor". The `urgent-90` arm is missing from that sentence; the paragraph below
it introduces both tiers, so the file states two different things about when the stamp is written.

## Fire rate (FIX DIRECTIVE 5) — measured, and re-derived by the orchestrator

The class seat reported it; I re-ran it myself because the same seat's `--numstat` table was garbled
(it listed files outside the slice and printed 0 deletions for every row, against a true 586/54).

```
rows=3567  fleet-active-wall=20  tiers={'<absent>': 4, 'urgent-90': 10, 'walled': 6}
share of stamps that were the WARNING tier: 10/20
```

**Ten of the twenty fleet-exhausted episodes this box has ever recorded were the `urgent-90` warning, not
the wall.** Every one of them armed the full fleet-wide default-deny. Half of all hard holds ever taken
here were premature by up to ten points — that is the defect's measured incidence, not an estimate. The
four tier-less rows predate the ledger field and are exactly the population the fail-closed migration
covers. Denominator: 3,567 ledger rows spanning the file's whole history.

Fleet distribution of the changed synced hook, sampled: 4 of 4 project repos checked
(`youtube`, `transdoc`, `seo`, `web-ecommerce-factory`) carry it byte-identical to the hub;
`fabrik-lib` carries no copy, which is correct — it is sync-excluded. A 5-repo SAMPLE, not the fleet.

`_stamp_exists` (the removed function) survives in 0 main-tree files; its only hits are in four parked
`.claude/worktrees/` copies, which are frozen checkouts and not live code.

Grader counts at both SHAs, so a silent deletion cannot hide: `test_claude_fleet.py` 262 → 268,
`test_quota_posture.py` 37 → 40, `test_quota_stop_hook.py` 36 → 40. No decrease.

## Pass Ledger

| pass | method | counters | finders |
|---|---|---|---|
| Pass 2 (DELTA) | method: re-derivation — every claim in the round-1 fix text re-executed; the fire-rate and numstat figures re-derived by the orchestrator; round-zero probe — the new escalation function re-read WHOLE before dispatch | found: 30, new: 30, confirmed: 26, fixed: 20, unexecuted: 0 | dispatched: 3, returned: 3 — opus×2 (claude_rotate fix hunks + one hop · both hook copies + one hop), sonnet×1 (the four corrected doc/contract files). own-fix: 24 of 26 |
| Pass 1 | method: re-derivation — every claim re-run against the live code, the fire rate re-derived from the ledger by the orchestrator after the class seat's numstat proved garbled; round-zero probe — both hooks driven end to end at band RED + tier `urgent-90` before any seat returned | found: 30, new: 30, confirmed: 26, fixed: 18, unexecuted: 0 | dispatched: 5, returned: 5 — opus×2 (quota_stop+its suite · claude_rotate twins+test_claude_fleet), sonnet×2 (quota_posture_hook+its suite · the 4 contract/doc files), haiku×1 (fire-rate + counted-facts class), plus the orchestrator's own round-zero probe |

### Round 2 (DELTA) — dispositions

⚠️ **24 of 26 confirmed defects lay inside round 1's own fix hunks.** Round 1 was the full pass
(`own-fix 0`), so the D-278 two-of-three window is not tripped — but this round qualifies, and a
third qualifying round ends the hunt on the named set. Recorded here so that decision is visible.

**FIXED (20).**

1. **HIGH — `_upgrade_stamp_tier_to_walled` wrote IN PLACE.** `write_text` truncates first, so a
   mid-write failure left a TORN stamp: `_stamp_tier` still fail-closed to `walled`, but
   `_promised_resume` then read None and the episode's promise-came-due re-arm could never fire,
   stranding the hold on the week timer. Proven by an `RLIMIT_FSIZE` injection against both
   writers — the sibling `_rearm_wall_stamp` survived the identical fault intact, because it
   builds beside and moves in with one `os.replace`. The atomic recipe was two functions away and
   I did not use it. Now it does.
2. **HIGH — a failing `os.utime` left the tier correctly raised with a FRESH mtime** — restarting
   both latches, the exact thing the function's own docstring says it prevents — while stderr
   announced that the raise had failed. Both halves false. Setting the mtime on the temp before
   the move makes the failure unreachable and the message true by construction.
3. **HIGH — the wiring grader did not execute the wiring.** A seat reverted the call site to
   presence-only and 428 of 428 passed, THIS GRADER INCLUDED, because it computed `_hold_is_wall`
   itself. My first repair repeated the same circularity with a spy. It now drives a real
   `_cmd_tick` and captures what the production line passes; proven red on that exact revert.
4. **HIGH — "up to ten points" survived in `quota_posture_hook.py`,** where the phrase WRAPS
   across two lines. My line-based `grep` structurally could not see it, and I had claimed the
   correction was complete in five places. A wrap-aware `re.finditer` over the eleven touched
   files now reports 0.
5. **HIGH — `_nudge`'s DOCSTRING still carried "Nothing is denied while this prints",** the exact
   claim round 1 removed from the message body three lines below it.
6. **HIGH — `is_symlink()` over-reached.** Rejecting a symlink outright turned a symlink pointing
   at a valid `urgent-90` stamp into a full fleet hold — inventing the premature stop this change
   exists to remove. `is_file()` alone is strictly better: it follows to a regular file and
   returns False for a FIFO, device, directory or dangling link. Removed from all three copies.
7. **MED — a bare `\r` in line 1 still shifted the tier read,** because Python's universal-newline
   translation turns it into a line break on read. `.split("\n")` could not help. All three
   readers now open with `newline=""`, and the parity corpus pins the value.
8. **MED — the FIFO graders HUNG under mutation instead of failing** (both suites), which in the
   gate consumes the whole 900 s pytest budget and reports a timeout indistinguishable from a slow
   suite. A signal alarm is no fix either: `TimeoutError` subclasses `OSError` and the subject's
   own handler swallows it. Both now drive a subprocess with a timeout.
9. **MED — the three-way parity grader asserted AGREEMENT, never the VALUE,** so an all-three
   drift back to the defect passed. A seat reverted `.split("\n")` to `.splitlines()` in every
   copy and the grader watched the exact bug it names and said nothing. It now pins expected
   values per shape.
10. **MED — the `CHECKPOINT`/nudge clause asserted what the band was doing** while having no
    access to the band; at GREEN it told the agent work may be held beside a line saying GREEN.
    The nudge now points at the QUOTA line instead of asserting. The grader that pinned the old
    wording was itself the cobra — it made the inaccurate clause mandatory — and now pins
    substance.
11-20. The `--status` renderer still printed "nothing is held" (the third surface, one short);
    `quota_stop.py`'s docstring undercounted the writers (three, not two) and attributed the tier
    raise to the wrong function; `_stamp_tier`'s docstring did not enumerate its new fail-closed
    cases; the one-way claim was absolute where the dwell-clear + re-arm path makes it conditional;
    `_print_picture` called a dict-guarded predicate and an unguarded `.get` on the same value;
    four grader docstrings carried the wrong constant.

**RECORDED (6).** The `is_file()` TOCTOU and a hung-mount `stat` (narrow, needs a writer with
access to `ROTATE_STATE_DIR`); the ledger row is not raised with the stamp, so the re-arm path can
restore the softer tier for microseconds; `_urgent_drain_pct`'s docstring still says "five points"
and another comment still says "default 95" (pre-D-201 literals, one hop out); the nudge has no
per-episode latch and prints on every tool call; **2 of 49 on-disk copies of `quota_stop.py` are
pre-D-306** — `/opt/fabrik-lib-account` and `/opt/fabrik-lib-review`, both linked worktrees of the
sync-excluded `/opt/fabrik-lib`, so the hub cannot reach them and the premature-stop defect is
still live there; routed by mail to fabrik-lib.

### Round 1 — dispositions

**FIXED (18).** Most severe first; the top two were found independently by both Opus seats.

1. **HIGH — the tier never ESCALATED within an episode.** The stamp is written once per episode
   and the message latch `return`s before that write, so the tier froze at whichever arm fired
   FIRST — and `urgent` fires eight points before `walled`. An episode opening at the 90-line and
   then reaching a real 100% wall kept saying `urgent-90`, so `quota_stop.py` held NOTHING at that
   wall until the promised resume or, with no relief epoch nameable, a full `_FLEET_WALL_REARM_S`
   week (measured at 167 h). D-306 made a frozen field load-bearing; this is the same class the
   latch's own comment records from Delta 10 seat B F1, where the stamp was absent rather than
   lying. Fixed by `_upgrade_stamp_tier_to_walled`, one-way, preserving line 1 and the mtime.
2. **HIGH — the change's headline behaviour had NO grader.** Reverting the call site to the
   pre-change `hold=_pic.get("hold") is not None` — undoing the entire point of the commit — left
   284 of 284 graders green. `_hold_is_wall` was graded only as a pure function.
3. **MED — an unhashable ledger `tier` raised TypeError out of `_rearm_wall_stamp`,** whose
   docstring promises it never raises, wedging every statement after the advisory on every tick
   until the row aged out. `_STAMP_TIERS` is a frozenset, so a bare `in` hashes its operand;
   `_open_wall_rows` validates `ts` and `account`, never `tier`. The identical class is guarded
   eight lines above in that same reader (Delta 12 A #7) and a new field reintroduced it.
4. **MED — a FIFO at the stamp path hung the hook forever.** The tier reader added a blocking
   `read_text` where the old code called only `.exists()`; a hang is not an `OSError`, so the
   handler never fired and a PreToolUse hook that never returns stalls every tool call in the
   session (executed: exit 124 under `timeout 5`, against exit 0 pre-change).
5. **LOW→MED — `splitlines()` breaks on VT/FF/FS/GS/RS/NEL/U+2028,** none of which any writer
   treats as a line end, so a control byte in the PROMISE shifted line 2 and a `walled` stamp read
   as `urgent-90` — lenient, the one direction this reader must never be. Now `.split("\n")`.
6. **MED — `_fleet_picture`'s `except OSError` tier arm was ungraded;** flipping it to fail-open
   passed 284 of 284. The first cut of my own grader for it used a directory at the stamp path and
   took the SUCCESS branch instead, staying green under the mutant — caught by the battery, not by
   reading, and re-aimed to raise from inside the `try`.
7. **MED — `--status` printed `HELD` on mere truthiness,** so at `urgent-90` the operator read
   HELD while nothing was held, in the command the contract names as the authority on the hold.
8. **MED — both hooks told the agent "nothing is held yet"** at exactly the state `urgent-90`
   describes, while `quota_posture_hook.py` denies `Agent` there on band RED — which is that
   tier's own precondition. Found by three seats and by the orchestrator's round-zero probe.
9. **HIGH (doc) — "up to ten points" is wrong: it is EIGHT,** and fewer when a `caps.json` cap
   binds first. `ROTATE_THRESHOLD` is 98 and `claude_rotate.py` says "eight points" twice in its
   own comments. Corrected in five places.
10. **HIGH (doc) — "those govern when the POINTER moves, never what an agent is told" became
    FALSE** in the same paragraph that made it so: `ROTATE_URGENT_DRAIN_PCT` now decides whether an
    agent gets the CHECKPOINT nudge. Corrected in all three copies that carry the sentence.
11-18. The four re-pinned assertions were **circular** against `_stamp_body` (three mutations of
    the composer left them green) — one restored to literal bytes; `quota_stop.py`'s first
    docstring sentence named only the walled arm and claimed "no other reader with authority";
    `quota_posture_hook.py`'s deliberate fail-CLOSED reader contradicted that file's own
    "FAIL-OPEN, ALWAYS" doctrine with the reason stated only in a sibling doc; the parity corpus
    covered none of the shapes three hand-written copies actually diverge on; two code comments
    and the `--status` one-liner still stated the coupling this change breaks.

**REFUTED (4), with the proof.** `_promised_resume`'s migration is SAFE — 8 divergences over 31
regular-file inputs, 7 in the intended direction, and the single dropped-promise input
(`b"\n<num>"`) is unproducible by either writer. The new `IndexError` arm is REACHABLE, not dead
(a zero-byte stamp; the advisory's `write_text` truncates before writing). `_stamp_exists` has 0
live references — its only hits are four parked `.claude/worktrees/` checkouts, not on any
runtime path. The CHECKPOINT clause being UserPromptSubmit-only is by design, not an omission.

**RECORDED (8) — named destinations, not silently passed.**

| # | finding | destination |
|---|---|---|
| R1 | `.claude/hooks/final_gate_stop.py:1888`'s D-158 yield reads a bare `.exists()`, so the Stop hook still stands all six causes down at the harmless `urgent-90` tier, where nothing is denied and there is no deadlock to yield against | `docs/STRATEGIC_BACKLOG.md` — **I am contractually forbidden to edit that file**; routed to the operator in this run's report |
| R2 | an unreadable or malformed `caps.json` makes `walled` False for an account genuinely past its operator reserve, and since D-306 that writes `urgent-90` and drops the hold — executed on the real ob@ shape | `docs/STRATEGIC_BACKLOG.md`; the fix needs a "caps unknown" signal, which is a new mechanism, not a review fix |
| R3 | the advisory's `stamp.write_text` is non-atomic while `_rearm_wall_stamp` uses tmp+`os.replace`; a concurrent reader or ENOSPC sees a zero-byte stamp | `docs/STRATEGIC_BACKLOG.md` |
| R4 | a broken symlink at the stamp path allows silently — `Path.exists()` follows it, so the hook never reaches the reader (pre-existing, unchanged by this diff) | `docs/STRATEGIC_BACKLOG.md` |
| R5 | `tests/test_governance_template_split.py`'s two GFM-rendering graders have been failing on this box for a missing `linkify_it`, undeclared in any manifest here — the hub's own contract-rendering guard is wallpaper | `docs/STRATEGIC_BACKLOG.md`; fixing it edits `pyproject.toml`, which needs operator authorisation |
| R6 | `_promised_resume` bypasses `_usable_ts`, the file's self-declared ONE validator, which the ledger latch applies to the same field — `"1e400"` returns `inf` (benign today, contradicts the docstring) | `docs/STRATEGIC_BACKLOG.md` |
| R7 | `_hold_is_wall` fails OPEN on a non-dict; unreachable from `claude_rotate.py` (all three producers emit dict-or-None) but `quota_posture_hook.py` re-derives from the posture JSON | `docs/STRATEGIC_BACKLOG.md` |
| R8 | the new D-306 sentences are in neither `_SHARED_SPANS` nor `QUOTA_CLAIMS`, so nothing grades them three-way; pinning them now would red the third-file check until `/opt/fabrik-lib/CLAUDE.md` lands | blocked on the cross-repo edit; pin in the same change |


## Gate

Re-measured in the closing pass, never inherited.

## Known, not defects (stated at dispatch so no seat spends a round on them)

- `tests/test_governance_template_split.py::test_the_lane_table_renders_as_a_table_for_every_gfm_reader` and its template twin FAIL on this box for a missing `linkify_it` module — proven pre-existing at 623c00cfb in a throwaway worktree at HEAD.
- `tests/test_claude_fleet.py` carries two pre-existing `ruff format` hunks swept in by formatting this change's own additions in that file. The format debt in `quota_stop.py` (:456/:564/:596) and `claude_rotate.py` (:4563) is pre-existing and was deliberately left.
- `/opt/fabrik-lib/CLAUDE.md` has NOT received the new WALL wording — cross-repo, unapproved this turn. Named as OWED, not as a defect of this diff.
