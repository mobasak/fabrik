# Kaizen — the continuous-improvement loop (daily measurement half + analysis half)

The roles spec (`docs/superpowers/specs/2026-08-12-hub-agent-roles-design.md` § Continuous
improvement) makes the kaizen pass **binding for infra and fleet**. M0 (2026-08-19) shrank the
governance surface it measures; M1 (2026-08-20) replaced the prose-reading weekly meter with a
**typed event stream + a daily collector**: sensors emit one JSON line at the moment a thing
happens, and the collector reads events instead of guessing at transcripts. The stream schema,
emitter laws and the full metric registry live in `docs/workstation/kaizen-event-stream.md`.

## The split: measurement is mechanical, analysis is not

| Half | Who runs it | Cost | What it produces |
|---|---|---|---|
| **Measurement** | `scripts/sysadmin/kaizen_collect_v2.py --daily` + `scripts/sysadmin/kaizen_outcomes.py --sweep`, from cron | stdlib-only, no agent, **no Claude quota** | derived facts + versioned metric series daily, one kaizen-log row per role weekly, a hand-off mail |
| **Analysis** | the infra / fleet agent, ≤90 min timebox | one Claude session | the `Top friction fixed` + `Filed` cells, and the fixes behind them |

The rule that shapes everything here: **never spend Claude quota to produce a number a script
can compute.** The cron measures; the agent thinks.

## What runs, and when (M1 cutover, 2026-08-20)

```
27 * * * * flock -n $HOME/.claude/state/daily-kaizen-collect.lock /opt/fabrik/scripts/sysadmin/weekly_catchup.sh kaizen_collect_v2.py >> $HOME/.claude/kaizen.log 2>&1
41 * * * * flock -n $HOME/.claude/state/daily-kaizen-sweep.lock /opt/fabrik/scripts/sysadmin/weekly_catchup.sh kaizen_outcomes.py >> $HOME/.claude/kaizen-sweep.log 2>&1
53 * * * * flock -n $HOME/.claude/state/daily-kaizen-coroner.lock /opt/fabrik/scripts/sysadmin/weekly_catchup.sh kaizen_coroner.py >> $HOME/.claude/kaizen-coroner.log 2>&1
```

The third line is the **daily coroner sweep** (`kaizen_coroner.py --sweep`): post-hoc
death/revival reconstruction plus closure of run records that can no longer close themselves —
the hole metric and the record TTLs depend on it, and nothing else on the box runs it. Each
job's liveness evidence is its **success stamp** (`~/.claude/state/daily-<job>.stamp`, touched
only on success — the log files are also written by nudges and failures, so they are not
heartbeats); the three surfaces are registered in `.fabrik/liveness-registry.json`.

Both ride the **wake-proof stamp-check runner** (`scripts/sysadmin/weekly_catchup.sh`, M0 shrink
ruling): the cron fires hourly, the runner runs the job only when its success stamp is older than
the job's period (1 day for these two; the sibling audit jobs stay weekly), and the stamp is
touched only on success — a night the box hibernated through is caught up within an hour of
waking, and a failing job retries hourly with every attempt in the log. The retired weekly meter
`kaizen_metrics.py` lives in `scripts/sysadmin/archived/` (operator ruling, M0); its old
`weekly_catchup.sh kaizen_metrics.py` crontab line is replaced by the two lines above.

### The daily collector pass (`kaizen_collect_v2.py --daily`)

One pass per day, default day = **yesterday** (a session is consolidated on the day its record is
complete). In order:

1. **Golden gate** — the hand-labelled corpus (`tests/fixtures/kaizen-golden/`) must derive to
   its expected counts, or the run refuses: exit non-zero, `instrument_alarm` event, NOTHING
   published, the log row rendered all `—`. Instrument health is metric zero.
2. **Derive** — each session file whose mtime date is **at or after the day** (anything still
   alive: the never-quiescing `unknown.jsonl` and still-active sessions included; the keyed
   dedup + the delta seam keep later re-derivations honest) becomes one row in the append-only
   derived-facts store (`~/.claude/state/kaizen/derived-facts.jsonl`, keyed
   `(sid, facts_version, day)`). Torn lines are counted with a reason, never crashed on;
   truncated lines count envelope-only (reason `truncated`).
3. **Publish** — per-day deltas (a grown file never re-counts earlier days) append to the
   versioned series files (`~/.claude/state/kaizen/series/<metric>@v<N>.jsonl`). **The root
   law:** a delta is only computable against a baseline that MEASURED the same field — a field
   the predecessor row never carried (a `FACTS_VERSION` bump day) is `None` in the delta,
   never 0-baselined, and every metric excludes such a row from numerator AND denominator,
   counting it as a stated **bump-day gap** (the bump day goes honestly quiet per-field). A row
   claiming `runs_noncheck > runs` violates non-check ⊆ all and is warned + unmeasured.
4. **Log row + mail** — the ISO-week row is upserted into both role logs and the metrics mail
   goes to the shared `fabrik` mailbox (fail-soft: a dead mail store costs the notification,
   never the row). **The single-source law (W6-1):** every mechanical weekly cell AGGREGATES
   THE PUBLISHED DAY SERIES — the one already-delta-honest source — never a store-row
   recompute; the human row is thereby provably consistent with the machine series (see § The
   kaizen-log row).

Metric inputs are **event-era only**: T08's backfill shares the store with `era: "transcript"`
rows (every event-only field an honest `—`), and `daily()` excludes them from its day/week
selection and delta baselines (the T09 era filter, applied INSIDE the readers BEFORE the
latest-per-sid collapse — a transcript row that outranks its event-era sibling must not swallow
the sid). Useful flags: `--day <ISO>`, `--no-mail`, `--golden-check`, `--selftest`.

**The one-day forward smear (documented, bounded, honest):** the pass consolidates yesterday
with the mtime>=day selector, so a file still alive when the pass runs is derived with its
CURRENT cumulative content — lines written today (before the pass) land in yesterday's
published day. The smear is bounded to one day forward (the pass runs daily), and cross-day
totals stay honest: the delta seam subtracts the predecessor row, so a smeared line is counted
once — the smear shifts which day it lands in, never how many land.

**Out-of-order refusal + the escape hatch:** an explicit `--day` strictly OLDER than the newest
day already published in the series store is REFUSED (nonzero rc, zero mutation) — under the
mtime>=day selector it would derive every alive file's current cumulative content under the old
day and double-publish into the append-only series. Historical backfill is `kaizen_backfill.py`'s
job. A FUTURE-dated day in the series (a post-resume clock jump) would wedge the hourly cron
permanently on this refusal, so the refusal names the clock-jump diagnosis explicitly when the
newest published day is in the future relative to both the requested day and today, and
**`KAIZEN_ALLOW_BACKPUBLISH=1`** (env, default off) downgrades the refusal to a loud warning and
proceeds — the documented unwedge, accepting the possible double-count it warns about.

### The nightly sweep (`kaizen_outcomes.py --sweep`) — runbook

For each project in `KAIZEN_SWEEP_PROJECTS` (comma list, default `fabrik` — config, never
heuristic discovery), the sweep clones HEAD into a temp dir (`git clone --shared` — the live tree
is never executed in) and runs **install-less** checks under a per-project
`KAIZEN_SWEEP_TIMEOUT_S` budget (default 300 s): `compileall`, pytest via the project's OWN
existing `.venv`, `final_gate.py --check` where synced. Timeout / no venv / no tests / node
project → honest `—` with the reason. Each project emits one `fleet_health` event; the report
line reads `swept n/N — the rest —`. Sibling modes for the analyst: `--rework` (git-mined rework
rate across `/opt/*`, `KAIZEN_REWORK_DAYS` window) and `--stops` (session-level premature-stop).
The store-derived outcome series (`premature_stop`, `stop_block_causes`, `review_rounds`)
additionally publish from the daily collector pass — **DAY-scoped (W7-1): the published day
point is computed over `days=[the published day]` only** (for `review_rounds`: numerator = the
day's summed `rounds_max` over its round-growth sids, denominator = their count), so the weekly
cell weights each session once, never once per derivation-day residency; the trailing window
below is ONLY the on-demand CLI view, never a published day point. All three compute over ONE
window with ONE population (W5-1): the last `KAIZEN_OUTCOMES_WINDOW_DAYS` LOCAL calendar days
including today
(default 7; the store's day stamps are local dates — W6-5 — and under the daily cron the newest
derivable stamp is yesterday), read as day-scoped DELTA rows — every sid's in-window store rows
delta'd against its nearest earlier row (`window_delta_rows`), so a lifetime session
contributes only its in-window growth, never all-time cumulative. A kept row whose baseline
(`delta_of`) predates the window smears derivation-gap growth into it — deliberate (the delta
seam attributes gap growth to the derivation day, both sides) and VISIBLE: the detail counts
`k row(s) whose baseline predates the window (derivation-gap smear)` (W7-5). Attributed-side bootstrap
symmetry (W6-2): a first-ever attributed delta row carrying family mass whose `first_ts`
predates the window dumped lifetime backlog as its "delta" — bootstrap-unmeasurable, excluded
from value AND guard operands and counted (a `first_ts`-proven in-window birth stays: its
lifetime IS in-window growth); the metric dashes with the bootstrap reason when the exclusion
empties the population. Value and attribution guard measure the SAME delta rows: attributed
in-window growth vs the `unknown` accumulator's per-day delta mass, held to the 20% attribution
floor. The guard publishes (share stated) when healthy, dashes when the unknown stream holds
the window's mass, and heals when attribution improves; an unknowable unknown mass dashes with
its TRUE cause — accumulator shrank · pre-v3 rows in window (no `events_unattributed` field —
absent ≠ 0) · bump-day gap · bootstrap window (the accumulator's first derivation carries
pre-window backlog, so the first window after store bootstrap is expected unmeasurable;
family-scoped — a bootstrap row with zero family mass is a knowable 0).
`stop_block_causes` sums causes over VERDICT-BEARING rows only (numerator ⊆ denominator
structurally, W6-3). A window holding no derived delta rows at all dashes "no derivation in
window" naming the MEASURED cause — empty store · transcript-era only · rows exist but none
dated in-window (W6-4) · in-window rows exist but every delta was shrink-suppressed (checked
via `delta_row`'s None returns, W7-4) — never a knowable 0. Never a lifetime ratio (fails open
on a bad week) and never a lifetime-knowability rule (ratchets permanently dead).

## The kaizen-log row — which cells are real now

Same eight columns as before (the daily upsert must not reshape the shipped tables).
**THE SINGLE-SOURCE LAW (W6-1, supersedes W5-5's week recompute):** every mechanical cell
aggregates the ISO week's PUBLISHED DAY SERIES points (current registry version only) — never
a store-row recompute (mixed row semantics fabricated cells: lifetime `rounds_max` under a
growth guard, delta occurrences against point-in-time death classes, per-(sid,day) rows
diluting per-session shares into per-row shares). Ratio cells SUM the week's day
numerators/denominators; the death cell sums occurrences and merges the day class maps; the
rounds cell is the n-weighted weekly mean of `review_rounds`' day points. A day the series
lacks contributes nothing (its honesty gates already spoke at publish time); a week with no
published days for a metric renders `—` ("no published days this week"). **Split weeks (W7-2):**
a mid-week registry version bump leaves the earlier days in the previous version's file —
versions are never mixed in one sum; the cell aggregates current-definition points only,
carries a `*` marker with a stderr note ("k of N week day(s) at the current definition"), and
when zero current-definition days exist the dash reason says "definition changed this week; no
days published at the current definition yet". **The death pair contract (W7-3):** the cell is
measurable only when BOTH halves publish (occurrence day points AND class day points) — a
one-sided week dashes with the pair-contract reason, never `N occ / 0 cls`. **A coroner-quiet
death cell (W7-6)** names WHICH cause via the whole-store universe signal: the coroner has
never run (no death/session_end anywhere in the store) · series file missing at the current
version · every week day gapped/unpublished:

| Column | Status | Source |
|---|---|---|
| Gate first-pass rate | **real** (M1) | `first_attempt_gate_pass` day points, week-summed — sessions whose FIRST attributed **non-check** `gate_run` succeeded (`--check` self-reviews, incl. the Stop hook's automatic run, never define a first attempt). |
| Death-classes /wk | **real** (M1) | the `death_occurrences` ⟂ `death_classes` day series (coroner-reconstructed, delta-honest at publish: the day's NEW deaths/classes only) — `<occurrences> occ / <distinct classes> cls`. A day without coroner evidence (no death/session_end event) publishes nothing — a `0` there would be fabricated (M9, day-scoped). |
| Lesson-class recurrence | `—` | Lessons carry no class tag; recurrence is the analysis half's judgement. |
| Review rounds /plan | **real** (M1) | `review_rounds` day points, n-weighted weekly mean. All windowed honesty (growth-only population, the 20% attribution floor, bootstrap/bump-day/pre-v3/shrink causes) lives at DAY-publish time in `kaizen_outcomes.review_rounds` — an unpublished day simply contributes nothing here. |
| Missed crons | `—` in this row | Not an event-stream metric — the liveness audit owns the answer (`scripts/sysadmin/liveness_audit.py`, `docs/workstation/liveness.md`); the reason rides stderr + mail. |
| Top friction fixed / Filed | **the analyst's** | Never overwritten by a re-run. |

**Idempotence** — the row is keyed by ISO week: a same-week re-run updates that week's row;
mechanical cells always take the newly computed value **including a dash** (a fresh honest `—`
must never republish the previous run's stale number under a new date); only the ANALYST cells
(`Top friction fixed`, `Filed`) yield a `—` to whatever a human/agent put there. On a golden
refusal the mechanical cells are stamped `—` regardless while the analyst cells still survive.
**A wrong metric is worse than an absent one** — unmeasurable renders `—` with its reason on
stderr and in the mail, never a fabricated 0.

## The noise floor and the M1→M2 gate

`scripts/sysadmin/kaizen_backfill.py` walked the pre-event transcript corpus once
(`era: "transcript"` rows in the same store; they carry `TRANSCRIPT_FACTS_VERSION` — the
backfill's own constant, bumped only when transcript derivation changes — as both their
`facts_version` and their skip key, so an event-schema `FACTS_VERSION` bump never re-appends
the corpus) and writes the per-metric variance report —
**`~/.claude/state/kaizen/noise-floor@v1.md`** (regenerate: `kaizen_backfill.py --report`).
M2's adjudication reads the variance column: a change it cannot distinguish from that floor is
Tuesday, not a signal.

**The M1→M2 gate is calendar time, not execution time:** M2 opens only after (a) **7 days of
daily event collection** from the cutover's first daily cron run (the window START date is
recorded in the plan spine's completion stamp), and (b) **variance sign-off** — the noise-floor
report regenerated over those event-era days and reviewed against hand-counts. Neither is
claimable at plan-execution end; the gate review is a named operator-triggered follow-up.

## How the analysis half is triggered

Unchanged from v1 in shape: after the row is on disk — in that order; a mail failure must never
cost the measurement — the collector mails the metrics with every `—` reason to the shared
`fabrik` mailbox (`scripts/mail.py send --to fabrik --kind request`; ack-rename is the claim
lock). The agent's ≤90-min pass opens with its input gathered: analyze (recurrence × blast
radius, evidence-cited), improve (≤30-min fixes land in-pass; larger become a spec or a mailed
handoff), control (every fix ships a regression guard) — then fill `Top friction fixed` and
`Filed`.

## M0 — the shrink audit (2026-08-19)

Before any meter was built, the shrink question ran first: per-artifact invocation census
(structure-keyed, both channels), rule-pack applicability, liveness verdicts —
`scripts/sysadmin/kaizen_shrink_audit.py --report`, immune list in
`kaizen_immune_list.py`, the operator's ruling recorded in
`docs/workstation/kaizen-shrink-audit.md`. The census is final for meter sizing only and
re-opens on M1 activation data.

## Files

| Path | Role |
|---|---|
| `scripts/sysadmin/kaizen_events.py` | the typed event emitter (three laws; schema + vocabulary in `kaizen-event-stream.md`) |
| `scripts/sysadmin/kaizen_collect_v2.py` | the daily collector — derived facts, versioned series, golden gate, log row + mail |
| `scripts/sysadmin/kaizen_coroner.py` | post-hoc death/revival reconstruction + session closure + the hole metric |
| `scripts/sysadmin/kaizen_outcomes.py` | outcome tier: rework miner, fleet-health sweep, premature-stop reader |
| `scripts/sysadmin/kaizen_backfill.py` | one-time transcript-era backfill + the noise-floor report |
| `scripts/sysadmin/weekly_catchup.sh` | wake-proof stamp-check runner (daily kaizen jobs + weekly audits) |
| `scripts/sysadmin/archived/kaizen_metrics.py` | the RETIRED weekly v1 meter (M0 operator ruling) |
| `scripts/sysadmin/kaizen_shrink_audit.py` / `kaizen_immune_list.py` | the M0 census engine + immune registry |
| `scripts/sysadmin/liveness_audit.py` | the `Missed crons` answer + mechanism health (`docs/workstation/liveness.md`) |
| `tests/test_kaizen_{events,collect_v2,coroner,outcomes,backfill,hook_emitters,sensor_emitters}.py` + `tests/test_command_run.py` | the M1 behavior suites |
| `tests/fixtures/kaizen-golden/` | the hand-labelled corpus behind the golden gate |
| `docs/reference/agents/kaizen-log-{infra,fleet}.md` | the role logs — one row per ISO week |
| `~/.claude/state/kaizen/` | derived-facts store, series, `noise-floor@v1.md` |
| `~/.claude/kaizen.log` / `~/.claude/kaizen-sweep.log` | the crons' stdout/stderr, incl. every `—` reason |
