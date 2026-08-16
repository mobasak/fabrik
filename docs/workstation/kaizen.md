# Kaizen — the weekly continuous-improvement loop (measurement half + analysis half)

The roles spec (`docs/superpowers/specs/2026-08-12-hub-agent-roles-design.md` § Continuous
improvement) makes a weekly kaizen pass **binding for infra and fleet**. It shipped the charters
and the two empty log tables, then left the cadence trigger as an open item — so between
2026-08-12 and 2026-08-16 the pass ran **zero times** and both logs still held only their
baseline row of em-dashes. A binding rule with no mechanism is documentation, not enforcement.

This page describes the mechanism that closes it.

## The split: measurement is mechanical, analysis is not

| Half | Who runs it | Cost | What it produces |
|---|---|---|---|
| **Measurement** | `scripts/sysadmin/kaizen_metrics.py`, from cron | stdlib-only, no agent, **no Claude quota** | one row per role in the kaizen logs + a hand-off mail |
| **Analysis** | the infra / fleet agent, ≤90 min timebox | one Claude session | the `Top friction fixed` + `Filed` cells, and the fixes behind them |

The rule that shapes everything here: **never spend Claude quota to produce a number a script
can compute.** Three of four accounts sit near their weekly wall most weeks; a pass that burns a
session counting review rounds is a pass that will not run. The cron measures; the agent thinks.

## What runs, and when

```
45 6 * * 1 cd /opt/fabrik && .venv/bin/python scripts/sysadmin/kaizen_metrics.py --once >> $HOME/.claude/kaizen.log 2>&1
```

Monday 06:45, chosen to land **after** the existing Monday-morning batch so the row measures a
settled week rather than racing it:

- `20 6 * * 1` — `claude_rotate.py --keepalive` (the weekly account keepalive)
- `30 6 * * 1` — `fleet_doc_audit.py --commit` (writes `docs/infrastructure/probe-reports/`)

06:45 clears both with margin. The measurement window is the **7 days ending on the run date**,
so a Monday run covers the previous Tuesday through that Monday.

## Modes

| Mode | Effect |
|---|---|
| `--once` | measure, upsert one row per role, then mail the analysis half. The cron mode. |
| `--dry-run` | print the row that *would* be written. Touches nothing. |
| `--report` | print both current tables. |

Useful flags: `--date <ISO>` (measure as of another day), `--no-mail` (skip the hand-off),
`--repo-root` / `--sound-log` (redirect the sources; the tests use them).

## The metrics — which are real, which are `—`, and why

The spec pins five. **Only two have a real source today.** The other three are written as `—`
with the reason emitted to stderr (so it lands in `~/.claude/kaizen.log`) and carried in the
hand-off mail.

This is the load-bearing rule of the whole subsystem: **a wrong metric is worse than an absent
one, because it silently ends the investigation it should have started.** There are no
estimates, no proxies wearing another metric's name, and no plausible-looking placeholders.

| Column | Status | Source / reason |
|---|---|---|
| Gate first-pass rate | `—` | **Nothing records gate runs.** `final_gate.py --post-kilo` would write `.droid/gate_issues.jsonl`; that file has never existed, and no hook keeps a pass/fail record. A *rate* also needs a denominator of gate RUNS, which nothing counts — so even if the issues file appeared, it would not suffice. |
| Death-classes /wk | **real** | `~/.claude/sound-debug.log`, `event=StopFailure` lines. Each carries the decider's death class as `error=<class>` (`rate_limit`, `authentication_failed`, `server_error`, `invalid_request`, …). Reported as `<occurrences> occ / <distinct classes> cls`; the per-class breakdown rides the mail. |
| Lesson-class recurrence | `—` | `docs/LESSONS_LEARNT.md` entries carry **no class tag** — the headings are free prose. Recurrence needs semantic clustering, which *is* the analysis half's job. The countable context (entry count, in-window date stamps) goes in the mail instead of the column. |
| Review rounds /plan | **real** | `docs/development/reviews/*.md`, windowed by the filename date. See below. |
| Missed crons | **real** (since 2026-08-16) | `scripts/sysadmin/liveness_audit.py --json`, heartbeat proof — `DEAD/(LIVE+DEAD)` over the registered scheduled surfaces. The spec's cron-miss LOG still does not exist and never will (the per-job logs are untimestamped appends, so run *counts* are not reconstructible), but the question behind the metric is answerable another way: did each registered surface produce evidence inside its own budget? ⚠️ The audit has THREE states, and an **UNKNOWN is an instrument failure, not a miss** — UNKNOWNs are excluded from BOTH halves of the fraction and named in the mail. All-UNKNOWN yields a `—` naming the faults. See `docs/workstation/liveness.md`. |

Each verdict is re-derived at run time, never hardcoded — the day a gate-run ledger starts
existing, the `Gate first-pass rate` reason changes on its own.

### Reading `Review rounds /plan`

Rendered as `4.4 (n=13/16)`: mean 4.4 rounds across the **13 in-window ledgers that carry a
machine-readable round marker**, out of **16 in-window ledgers total**.

Two ledger dialects ship in `docs/development/reviews/`, and both are read:

1. numbered headings — `## Round 3`, `### Round-2 REFUTED`, `## Round 7 (2026-08-15)`
2. a round table — `| Round | Finder | … |` or `| Pass | scope | … |`, one body row per round

Counting only headings would have scored the 16-round `2026-08-11-plan-2-stalled-midstream-resume`
ledger as **0** and dragged the mean toward a comfortable lie. The per-ledger score is the
**highest** round number reached.

A ledger with neither marker is **not** scored as zero rounds — it had rounds, it just did not
machine-mark them. It shrinks `n` instead, which is why the denominator is printed in the cell:
a mean over 13 of 16 ledgers is a different claim from a mean over 16 of 16, and the reader can
see which one they are getting. The measured set also skews toward loops disciplined enough to
keep a ledger, so treat the number as a **floor**.

## Reading a row

```
| Date | Gate first-pass rate | Death-classes /wk | Lesson-class recurrence | Review rounds /plan | Missed crons | Top friction fixed | Filed (spec/mail) |
| 2026-08-17 | — | 430 occ / 4 cls | — | 4.4 (n=13/16) | — | — | — |
```

- `Date` — the run date; the window is the 7 days ending there.
- The five metric cells — the script's, rewritten on every same-week run.
- `Top friction fixed` / `Filed (spec/mail)` — **the analyst's**. The script only ever writes `—`
  there, and a re-run never stamps your text back to `—` (see idempotence).

## Idempotence

The row is keyed by **ISO week**. Monday's cron appends; any further run in the same ISO week
**updates that week's row** rather than appending a second one, so a manual re-run cannot
double-count a week.

On a same-week update, mechanical cells are recomputed and win — but a cell the script would
write as `—` yields to whatever is already there. If the analyst hand-counted a gate rate, or
filled `Top friction fixed`, the Monday-plus-one re-run preserves it. The mechanical half must
never destroy the analytical half's output.

## How the analysis half is triggered

After the row is on disk — **in that order; a mail failure must never cost the measurement** —
the script sends one fabrik-mail per role:

```
python scripts/mail.py send --to fabrik --kind request
```

The body carries that week's row, the **deltas vs the previous row**, the grounding behind each
measured cell, and every `—` with its reason. So the agent's ≤90-min pass opens with its input
already gathered: it analyzes (recurrence × blast radius, evidence-cited), improves (≤30-min
fixes land in-pass; larger become a spec or a mailed handoff), controls (every fix ships a
regression guard) — then fills `Top friction fixed` and `Filed`.

The mail is best-effort. A dead mail store costs the notification, not the row: the failure is
reported on stderr with `ROW IS RECORDED` and the script exits 0.

The three sessions share ONE `fabrik` mailbox, so `--to fabrik` reaches whichever session claims
it first (ack-rename is the lock). Both role mails land in the same inbox; the body names the
role in its title.

## The `—` cells are the backlog

They are not cosmetic gaps — each names a piece of missing instrumentation, and closing one is
exactly the kind of ≤30-minute improvement the loop exists to produce:

1. **Gate first-pass rate** needs `final_gate.py` (or the Stop hook) to append one line per run:
   timestamp, mode, verdict. Then the rate is a two-line computation.
2. **Lesson-class recurrence** needs a class tag on `docs/LESSONS_LEARNT.md` entries. Until then
   it stays the analyst's judgement, and that is the correct home for it.

**`Missed crons` closed on 2026-08-16** — not by building the cron-miss log the spec asked for (that
one is genuinely unbuildable from untimestamped appends), but by asking the answerable version of the
question. The liveness layer's heartbeat proof supplies it, and the mail now also carries mechanism
health: inert gate checks, stale doc claims, and surfaces present on the box but absent from the
registry. See `docs/workstation/liveness.md`.

## Files

| Path | Role |
|---|---|
| `scripts/sysadmin/kaizen_metrics.py` | the measurement half |
| `scripts/sysadmin/liveness_audit.py` | supplies `Missed crons` + the mail's mechanism-health context (`docs/workstation/liveness.md`) |
| `tests/test_kaizen_metrics.py` | behavior tests, incl. the honesty rule and idempotence |
| `docs/reference/agents/kaizen-log-infra.md` | infra's log — one row per pass |
| `docs/reference/agents/kaizen-log-fleet.md` | fleet's log — one row per pass |
| `docs/reference/agents/{infra,fleet}.md` § Kaizen | the binding charter rule this implements |
| `~/.claude/kaizen.log` | the cron's stdout/stderr, incl. every `—` reason |
