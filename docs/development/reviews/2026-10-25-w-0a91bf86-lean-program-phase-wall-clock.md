# Where the review-family and task runs spend their wall-clock (lean program MEASURE)

Item: W-0a91bf86 — the MEASURE for kaizen's spec W-96f36043, the lean program (D-1216). A measurement only: it
proposes no fix. Measured 2026-10-25 by intel at commit `76a119080` (origin/master).

## Populations

- **Runs:** every `/fabrik-task`, `/fabrik-review` and `/fabrik-review-scoped` run that closed `done` between
  2026-10-06 00:00 UTC and 2026-10-25 ~01:00, box-wide (every repo, every agent).
- **Event stream:** `~/.claude/state/events/<sid>.jsonl`, the `run_open` · `phase` · `dispatch` · `round` · `gate_run`
  · `run_close` rows `command_run.py` and `final_gate.py` write. A run is a `run_open` to its `run_close` in one
  session, nesting tracked. 11,022 runs were parsed box-wide; **1,583** are in scope (task 358 · review 547 · scoped
  678). 7 runs open longer than 6 h (a park or a dead session) are excluded from the event rows.
- **Feedback ledger:** `~/.claude/state/command-feedback.jsonl`, the `wall_s` and token fields each close captures:
  task 361 · review 553 · scoped 678 `done` closes. The ledger rows apply no 6 h filter, so they still hold those
  runs (2 / 4 / 1 of them).
- **Transcripts:** the main transcript of a run (any fleet account) is still on disk for 1,578 of the 1,583 runs.
  Subagent (seat) transcripts survive for only some (pruned after 3 days, D-1182): 71 task · 109 review · 127 scoped
  runs have one. Seat runtime is measured on the 54 · 109 · 126 of those that also have a `dispatch` event.

The medians the request quoted (48 / 32 / 21 min) come from another window. On this window the ledger reads
**50.7 / 29.0 / 16.8 min** and the event stream **50.4 / 28.8 / 16.7 min**. The two are not independent: both are
written by `command_run.py` at the same run's open and close.

## The table

A share is of the summed wall-clock of the row's population; when a cell names no population, it is all runs of
that command in the event stream (358 / 547 / 678). The task phase rows' shares and medians are over all 358 task
runs, zeros included; "k runs" says how many of them record that phase.

| Measure | /fabrik-task | /fabrik-review | /fabrik-review-scoped | Source · population |
|---|---|---|---|---|
| Median wall-clock (mean · p90) | 50.7 min (66.7 · 105.5) | 29.0 min (43.6 · 70.9) | 16.8 min (24.6 · 44.1) | ledger `wall_s` · n 361 / 553 / 678 (runs over 6 h included) |
| Seats running (any seat out), upper bound | **47.1 %** (median 26.9 min; includes the nested review's seats) | **64.3 %** (median 17.4 min) | **73.1 %** (median 9.5 min) | subagent transcripts, union of each seat's first..last timestamp · n 54 / 109 / 126 |
| Seats running, idle gaps over 10 min cut | 42.5 % | 53.4 % | 67.0 % | the same seats, an internal gap over 10 min between two lines of one seat's transcript removed · n 54 / 109 / 126 |
| Dispatch → next event window | 19.9 % (the task's own critique seats) | 63.6 % | 87.5 % | events · n 358 / 547 / 678 |
| Nested run (the review phase-4 opens) | **60.2 %** (median 28.2 min over 358; 28.8 over the 342 runs that nest one) | 0.4 % | 0.5 % | events |
| Before the first `step` (SIZE / start) | 10.9 % (median 2.5 min) | — | — | events; review runs rarely step phases (below) |
| Phase 1 MEASURE | 4.6 % (107 runs record it) | — | — | events |
| Phase 2 DESIGN (incl. the two critique seats) | 11.4 % (median 0.9 min over 358, 2.2 over the 334 runs · mean 7.1) | — | — | events · 334 runs record it |
| Phase 3 BUILD | 6.9 % (median 2.1 min over 358, 3.0 over the 300 runs) | — | — | events · 300 runs record it |
| Phase 4 REVIEW, outside the nested run | 2.7 % | — | — | events · 317 runs record it |
| Phase 5 CLOSE | 3.3 % (median 0.4 min over 358, 0.7 over the 302 runs) | — | — | events · 302 runs record it |
| Open → round 1 recorded | median 32.8 min (9 runs record a round) | median **12.5 min** (543 runs) | median **8.5 min** (676 runs) | events |
| Gap between consecutive rounds | median 6.2 min · mean 6.9 (12 gaps) | median 5.9 min · mean 9.8 (981 gaps) | median 4.1 min · mean 6.7 (1,209 gaps) | events |
| Rounds per run | median 0 · mean 0.06 (own; the nested review carries them) | median 3 · mean 2.86 | median 3 · mean 2.81 | ledger · n 361 / 553 / 678 |
| `final_gate.py` runs | 1,190 in 336 runs (incl. the nested review's) · median 41 s · mean 58 s | 1,434 in 454 runs · median 49 s · mean 68 s | 627 in 384 runs · median 66 s · mean 80 s | transcripts, Bash call to its result · n 356 / 547 / 675 (runs with a main transcript) |
| Gate share of wall | 5.1 % (per run median 2.7 min) | 7.6 % (per run median 2.4 min) | 5.1 % (per run median 0.1 min) | transcripts · n 356 / 547 / 675 |
| Command text, rendered (command file + skill wrapper) | 8,991 words · 55,243 chars · ~13.8k tokens | 27,822 words · 174,275 chars · ~43.6k tokens | 9,811 words · 61,197 chars · ~15.3k tokens | `~/.claude/commands/<cmd>.md` + `SKILL.md` at measure time; tokens = chars / 4, a heuristic, not a tokenizer count |
| Command text × runs (one load each) | ~6.38 M tokens (462 closes) | ~26.79 M tokens (615 closes) | ~10.94 M tokens (715 closes) | all closes since 10-06, every state |
| Command text carried in the cached prefix, per run | median carried 1.23 M tokens · median per-run share **2.7 %** of the run's cache reads (median 89 model calls) | median carried 2.05 M · median share **7.9 %** (median 47 calls) | median carried 0.40 M · median share **2.7 %** (median 26 calls) | ledger: per run, `tok_msgs` × text tokens, and that ÷ `tok_cache_read`; two separate medians · n 360 / 548 / 675 |
| Text load → first act (`run_open`) | median 0.4 min · mean 1.2 (208 runs) | median 0.2 min · mean 0.7 (396 runs) | median 0.3 min · mean 2.4 (374 runs) | transcripts: last Skill or Read of the command text within 30 min before the open; a typed slash command loads the text with no tool call, so those runs are not in n |

## Reading it

- **Review runs are mostly seat time.** Seats are out for 53 to 64 % of a full review's wall-clock and 67 to 73 % of
  a scoped one's (the lower figure cuts a seat's idle gaps over 10 min, the higher counts its whole span). The rest
  goes to adjudication and fixes.
  Round 1 lands at a median 12.5 min (full) and 8.5 min (scoped), then each further round adds about 4 to 6 min.
  Three rounds is the median.
- **A task run is mostly its nested review.** 60 % of a `/fabrik-task` run's wall-clock sits inside the review it
  opens at phase 4. Of the task's own phases, DESIGN is the largest (11.4 %, the two critique seats) and BUILD is
  6.9 %.
- **Gates are a small, steady share:** 5 to 8 % of wall-clock. One gate call takes a median 41 to 66 s; per run the
  gate total is a median 2.7 min (task), 2.4 (review) and 0.1 (scoped).
- **Reading the command text is cheap in wall-clock and modest in tokens.** In the runs that load it through a
  Skill or Read call (208 / 396 / 374), the text lands a median 0.2 to 0.4 min before the first act. Its carried
  cost is a median 2.7 % of a task or scoped run's cache reads and 7.9 % of a full review's: `/fabrik-review`'s
  text is 3.15 times `/fabrik-task`'s and 2.85 times `/fabrik-review-scoped`'s.

## Limits

- The event stream records no seat RETURN and no gate DURATION. Seat time comes from the surviving subagent
  transcripts (54 / 109 / 126 runs, a recency-biased sample: the newest runs). Gate time comes from Bash
  call/result timestamps in the main transcripts.
- Review runs rarely `step` their phases (105 of 547 full reviews record phase 1, 6 of 678 scoped), so their
  per-phase split is not measurable from the events. The seat, round and gate rows stand in for it.
- The "dispatch → next event" window is an approximation, not seat runtime. Seats can outlive it (the next event is
  sometimes the lead's own `round`), so the window and the seat share differ.
- The seat union spans each seat transcript from its first to its last line, so a seat left idle and resumed later
  counts its idle gap as running: 271 of 1,644 seat transcripts in the in-scope sessions hold a gap over 10 min.
  The gap-cut row is the bound from the other side; the 10-min threshold is a choice, not a measured cut-off.
- A run reopened with `--resume-from` (68 of the 1,583 by the `run_close` events' `resumed_from_start`: task 29,
  review 23, scoped 16; the ledger's own `resumed_from` field marks 64 of its done closes: 27 / 23 / 14) is measured from its
  reopening only. Its earlier segment is dropped, and the time in the phase it resumed at lands in "Before the first
  `step`".
- A `final_gate.py` call run in the background returns at once and is paired as about 0 s, which pulls the gate
  rows down: 4,414 of the 42,432 Bash calls naming `final_gate.py` in the in-scope sessions (40,051 of them run it;
  session-wide, not clipped to run windows) ran in the background.
- The token figures are chars / 4 estimates. The carried-cost row multiplies by every model call of the run,
  including the calls before the text loaded, so it slightly overstates.
- The command text was sized once, at measure time. The files changed during the window, so earlier runs carried
  different text.
- A `/fabrik-task` run's gate and seat rows include those of the review nested inside it.

## Reproduce

The scripts and their data are kept, untracked, in
`/opt/fabrik/.tmp/runs/a0df2b3c-ea50-4ba7-83cf-f6750435e49e/w0a91bf86-lean-measure/`:
- `phases.py` (events; writes `rows.json`);
- `transcripts.py` (gates, seats, text load; writes `tx.json`);
- `feedback.py` (ledger medians, text size);
- `carry.py` (carried text cost);
- `subset.py` (seat runtime on runs with seat transcripts).

Run each with `python3`; `phases.py` and `transcripts.py` take the output paths as arguments.

The rows D-1219 carries (wall-clock, seat time, rounds) are reproduced by `scripts/command_time_measure.py`
(W-487e966a): `--start 2026-10-06T00:00:00+00:00 --end 2026-10-25T01:00:00+03:00 --state done` prints this
table's wall-clock row and both seat share rows unchanged.
