# /fabrik-review-scoped — `_pick_flip_target`'s weekly reset through the one validator (RESUMED and ROUTED UP 2026-09-17)

The Delta 24 seat of the quota-posture Finish review (`2026-09-16-plan-1-quota-posture-review.md`,
Round 24) RECORDED that `_pick_flip_target` still converted a candidate row's `seven_day.resets_at_epoch`
bare, so a giant JSON int in that one field raised `OverflowError` out of the picker and out of
`_fleet_picture` after every other reset read had been routed through `_usable_ts`. Per infra's ask
(01M2QFQEG06E76908J1Y831JGS) it gets a fresh record over the current diff rather than a further round of
that loop.

## What is done

- `scripts/sysadmin/claude_rotate.py::_pick_flip_target` — `reset = _usable_ts(reset)`, then
  `reset_at = reset if reset is not None and reset > _now() else far`; the `scripts/aro-wake/` twin
  `cp`'d (`test_twin_copies_are_byte_identical`).
- `tests/test_claude_fleet.py::test_a_candidate_row_with_a_giant_weekly_reset_does_not_raise_out_of_the_picker`
  — on the `_fleet_two_accounts` fixture with a live-chained credentialed `seo` dir, so the row IS a
  candidate; red on HEAD (`OverflowError: int too large to convert to float`), green with the fix, both
  `source` values. The earlier vacuous `!= "c@x"` assertion in
  `test_a_giant_int_in_the_usage_cache_does_not_raise_out_of_the_relief_writer_or_the_window_reader`
  now reads the returned tuple's email.
- Suites and `final_gate.py --check --json` green at the commit named in the record's handoff.

## Open rows

| Round | Seats | Result |
|---|---|---|
| 1 | 3 `fabrik-reviewer` seats on one brief (pin `1621c4ae`) | 12 candidates, 5 confirmed, 0 own-fix — fixed at `175c6cff0` (+ CHANGELOG `0b4df223e`) |
| 2 (delta) | 3 fresh seats (pin `e1c17e97`) | 8 candidates, 7 confirmed, 5 own-fix — fixed at `e96386725` (+ CHANGELOG `dd1309b6a`) |
| — | — | two consecutive confirming rounds: the scoped record closed by name and the surface ROUTED UP to `/fabrik-review` (its step-5 rule); the heavy review's receipt is `2026-09-17-review-scoped-pick-flip-target-review.md` (round zero `639caf855`, rounds 1–4 `12066600b` · `5b8452da0` · `d11f83883` · `1d9f5c2fc`; PAUSED after round 4 on the operator's word — its § RESUME carries the path) |

## RESUME (executed 2026-09-17 — kept as the record of the path taken)

1. Re-read `~/.claude/commands/fabrik-review-scoped.md` (infra's edit will have landed) — the rule that
   binds the resumed passes is the rendered file, not this note.
2. `python3 scripts/command_run.py start --command fabrik-review-scoped --phases 1 --surface "<this
   file's title> — resumed"` naming this artifact as the surface.
3. Pin: `git diff <commit before the fix>..<the fix commit> -- scripts/sysadmin/claude_rotate.py
   tests/test_claude_fleet.py` under the scratchpad, md5 in every brief; readers read the pin with
   `sed -n`, never a bare `cat`; `--basetemp` under the seat's scratch; no `~/.claude*` path.
4. Round 1: `command_run.py dispatch --seats 3`, three `fabrik-reviewer` seats on ONE brief (the armed
   rubric classes: fail-open/fail-closed · cost/limit edges · boundary/sentinel · behaviour-without-a-test),
   `round --seats 3 --findings … --confirmed … --own-fix 0`. Then a delta pass sized by
   `dispatch_headroom.py --units 1 --delta <changed lines>` with a fresh reader; `--own-fix` stated.
5. Close BY NAME with the four-field feedback; commit and push any fix; update the Open rows above.
