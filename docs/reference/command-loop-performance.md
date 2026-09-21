# Command loop performance — what we aim for, what it costs, and the program to fix it

**Status:** DRAFT — awaiting the operator's ruling on § 5.
**Written:** 2026-09-21, by the unnamed hub window, on the operator's directive
("create a full documentation ... for the last month we are working these and it gets worse, not better").
**Nature:** a diagnosis and a program. Every number is measured, with its population named in § 7.
No number in this document is recalled.
**Snapshot:** all ledger figures are one read taken **2026-09-21 12:25 +03**. The ledger is live and
grew by two closes while this document was being written, which is itself an instance of § 4.1 —
re-derive before quoting, never copy a figure forward.

---

## 1. What we aim for

The operator has stated these across 2026-09-07 to 2026-09-21. They are the contract every
`/fabrik-*` command is judged against. The third column is the measured state at the date above.

| # | The aim, in the operator's terms | Source | Holds today |
|---|---|---|---|
| 1 | A demand answered the same session, never a day of waiting | *"i keep waiting 1 day for any demand"* | **No** — the spec chain costs 10.2 h at the median (§ 2.1) |
| 2 | At most three convergence rounds, then park | the three-round ceiling, quoted in `01M2ZDAYX1EHVST1DWG8PV3Z57` | **No** — runs of 44 and 50 rounds are in the record |
| 3 | Tokens spent like money | *"it consumes all my tokens"* | **No** — 43 G tokens over two weeks, and rising week over week (§ 2.2, § 3.2) |
| 4 | The smallest lane that discharges the ask | *"that is why we have created fabrik-task"* | **Yes**, since D-314/D-315 (2026-09-20) |
| 5 | Every count, path and symbol EXECUTED before it is written | aim 12 of the 17; `CLAUDE.md` § read it, don't recall it | **No** — this is the mechanism under 87% of the hours (§ 4.1) |
| 6 | Check what already exists first: the project, fabrik-lib, the ledgers | aims 11, 13 | **Partly** — stated in § Drive 2026-09-20, untested |
| 7 | The fewest review passes that still catch real defects | aim 6 | **No** — 125 of 191 recorded series rise instead of falling |
| 8 | The box used fully, in parallel, nothing read twice | aims 1, 2 | **Partly** — the seat budget is computed; non-duplication is by construction, not by rule |
| 9 | The cheapest model that can do each seat's job | aim 3, the price multipliers | **Yes** — D-190, by rule |
| 10 | Fable drives while its own quota allows, else Opus | aims 4, 17b | **Yes** — D-295 + § Drive |
| 11 | A dead seat re-dispatched, a stuck run handed off | aim 9 | **Partly** — `handoff` works; a hung seat still has no signal |
| 12 | One source per rule, nothing restated | aim 16 | **No** — one rule lives in six files (§ 4.2) |
| 13 | Only hub `infra` or `intel` runs the corpus tools | aim 17a | **Stated, not gated** |
| 14 | Every run makes the next run cheaper | the kaizen loop, aim 5 | **No** — 228 loop verdicts written, 4 ever answered |

One line under all of it, from `CLAUDE.md`: *fast but pro, ship, iterate, no over-engineering.*
What the system delivers instead is **pro but slow**.

---

## 2. What it costs today

### 2.1 The arithmetic of "a day"

A feature-scale demand runs the spec chain. At the median of every recorded close:

| Stage | Runs | Median | p90 |
|---|---:|---:|---:|
| `/fabrik-spec` | 17 | 66 min | 174 min |
| `/fabrik-spec-review` | 28 | 85 min | 728 min |
| `/fabrik-plan-after-chat` | 13 | 95 min | 215 min |
| `/fabrik-plan-review` | 19 | 117 min | 207 min |
| `/fabrik-execute-plan` | 35 | 248 min | 966 min |
| **Chain total (medians)** | | **611 min = 10.2 h** | |
| `/fabrik-task` (the lane, for comparison) | 4 | 41 min | — |

The operator's "a day" is not an impression. It is the sum of the medians.

### 2.2 The whole corpus, two weeks

| Measure | Value |
|---|---|
| Closes recorded | 335, across 24 commands and 10 repos |
| Total wall-clock inside commands | 803 h |
| Review family share (review · review-scoped · spec-review · plan-review · docs-review · data-contract) | 456 h, 57% |
| Median close · p90 · max | 58 min · 331 min · 1,775 min |
| Runs of 8+ rounds | 51 of 335 (15%) holding 311 h of 803 (39%) |
| Tokens | 28 G orchestrator + 16 G seats = 43 G |

### 2.3 Where the hours sit, per command

| Command | Runs | Hours | Share | Median run |
|---|---:|---:|---:|---:|
| `/fabrik-execute-plan` | 35 | 245 | 30% | 248 min |
| `/fabrik-review` | 75 | 222 | 28% | 93 min |
| `/fabrik-spec-review` | 28 | 94 | 12% | 85 min |
| `/fabrik-review-scoped` | 83 | 70 | 9% | 31 min |
| `/fabrik-plan-review` | 19 | 43 | 5% | 117 min |
| `/fabrik-plan-after-chat` | 13 | 29 | 4% | 95 min |
| `/fabrik-spec` | 17 | 26 | 3% | 66 min |
| `/fabrik-data-contract` | 2 | 17 | 2% | 522 min |
| the other 16 commands | 63 | 56 | 7% | — |

Six commands hold 86%. `/fabrik-execute-plan` is itself mostly review: 73 review-family closes
fall inside plan windows in the same repo, 144 of its 245 hours. `/fabrik-review-scoped` is the
counter-example that proves the design works when it is followed — 83 runs, the most of any
command, at a 31-minute median.

### 2.4 Anatomy of one round

| Component | Measured |
|---|---|
| Round to round | median 22 min (p75 34, p90 57) |
| One seat, dispatch to return | median 8.5 min (p90 19.2), over 814 seat transcripts |
| Seats per round | median 2 |
| Confirmed defects found after round 1 | 581 of 687, **85%** (11 records that state per-round counts) |
| Own-fix share of confirmed, where stated | median 0.67; at or above two-thirds in 56% of 54 rounds |

A round costs about 22 minutes whatever the diff size, because the seat re-reads the whole pin
regardless. Rounds do not get cheaper as the surface shrinks; they only get fewer, and they have not.

---

## 3. Did a month of fixes help?

This is the operator's claim, and it is correct at the level they experience. The interventions
worked on the metric they targeted and did not move the outcome.

### 3.1 What was shipped

| Measure, 2026-08-21 → 2026-09-21 | Start | End | Change |
|---|---:|---:|---:|
| `commands/_sources` + `_fragments` bytes | 583,299 | 1,230,048 | **+111%** |
| Command sources | 27 | 38 | +41% |
| `CLAUDE.md` bytes (auto-loaded every turn, every repo) | 40,558 | 134,466 | **+232%** |
| Decision rows minted | — | 321 | 165 of them about the loop |
| Decision rows superseding an earlier row | — | 28 | |

### 3.2 What changed in the outcome

| ISO week | Runs | Total h | Median min | Total tokens |
|---|---:|---:|---:|---:|
| 37 (Sep 8–14) | 148 | 408.9 | 78 | 20.6 G |
| 38 (Sep 15–21) | 186 | 375.1 | 54 | 22.6 G |

Review family alone, same two weeks: runs 111 → 103, median rounds 4 → 3, hours 251 → 186, and
runs of 8+ rounds **35 → 6**.

### 3.3 The verdict

**Per-run, it improved. System-wide, it did not.** Median minutes per run fell 31% (78 → 54) and
the review family's long runs fell from 35 to 6 — both real, both the direct effect of the
convergence work of the last month. But the number of runs rose 26% (148 → 186), total hours fell
only 8% (409 → 375), and **total tokens rose 10%** (20.6 → 22.6 G). The operator experiences
total time and total tokens, not median minutes per run, so the experience did not improve.

The clearest single data point is from today, after every one of those fixes landed: one
`/fabrik-review` ran 1,112 minutes on 15 seats and 213 M tokens, and its own close verdict says the
agent read `tail -3` of a checker and repaired the one row it showed, twice, while the full output
carried 24 complaints of that class. The rule that forbids exactly this (`denominator-honesty`) was
loaded in that session, in a `CLAUDE.md` that had tripled in size over the month.

---

## 4. Why

### 4.1 First cause — the fix between rounds is the next round's defect

Every one of the six commands that hold the hours names this at its own close, verbatim:

- `/fabrik-execute-plan` — *"Phase B's review consumed 21 rounds, 7 of them reviewing the review's own fix prose"*
- `/fabrik-review` — *"three exit rounds each burned ~15 min on one narrow item the previous fix introduced"*
- `/fabrik-spec-review` — *"passes 19-43 were mostly precision edits to one regex/grammar paragraph, each costing three seats"*
- `/fabrik-plan-review` — *"passes 6–13 dominated by my OWN fix residue in ONE T02 clause, each round I rewrote a sentence and pinned without re-reading"*
- `/fabrik-data-contract` — *"rounds 4–22, about 60 seats and 16 h: every round's fixes added prose, cites and derived numbers that the next round found defects in"*
- `/fabrik-docs-review` — *"13 of the closing round's 14 confirmed defects were in prose I had just written"*

The mechanism is constant: the orchestrator writes the fix from recall, on prose, without executing
the claims it adds, and the edit shifts the line numbers every citation in the artifact depends on.
A fresh reader then finds the residue. 85% of confirmed defects arrive after round 1, and 125 of
the 191 recorded series rise at least once instead of falling monotonically.

### 4.2 Second cause — the fixes for the first cause are themselves the load

Every fix for cause 4.1 has been **more rule text**, and rule text is loaded on every turn of every
session in every repo. The corpus doubled and `CLAUDE.md` tripled in the month the loop was being
repaired. `CLAUDE.md` alone is now ≈ 33,600 tokens per turn before any command is read; the largest
command source is 101 KB; the review family's shared fragments are another 68 KB.

Three consequences, all measured:

1. **More text is more claims, and every claim is a finding a seat can raise.** The commands that
   grew fastest are the ones whose reviews run longest.
2. **A rule stated in six files is six chances to drift.** Six of the nine fix commits on
   2026-09-20 were unreached mirrors, each found by the next fresh seat.
3. **Prose does not bind at the moment of writing.** Every rule violated in § 3.3's example was
   present, loaded, and had just been enlarged.

### 4.3 The two commands that are slow for a different reason

`/fabrik-plan-after-chat` and `/fabrik-spec` are not convergence loops. They write 400-line
artifacts with 70+ citations while the spec beneath them is still moving
(*"the intake re-derived figures the spec already carried because the spec was mid-amendment"*).
Their fix is an input freeze, not a round cap.

---

## 5. The program

Ordered. Each item names its lane, its size, and the measure it is expected to move.
**Items 1 and 2 are the only two that bind mechanically rather than by being read**, which is the
lesson of § 4.2.

| # | Change | Lane | Size | Moves |
|---|---|---|---|---|
| 1 | **Hard round cap.** `command_run.py round` refuses round 4 without `--operator-extension "<reason>"` and prints the park recipe. | `/fabrik-task` | 1 file, ~40 min | the 311 h in 8+-round runs |
| 2 | **Pin gate.** Seats are not dispatched for round N+1 until every number, `path:line` and `file::symbol` the last fix ADDED carries executed evidence, and the artifact's citations still resolve. | `/fabrik-task` | 1 file, ~40 min | cause 4.1 directly |
| 3 | **One sentence into `commands/_fragments/term-edit.md`** (17 consumers): fix before dispatch; refute a LOW finding in one line rather than fixing it; cite by symbol, never a bare line number. | `/fabrik-command-improve fabrik-review` | ~40 min | makes item 2 legible; answers 61 verdicts |
| 4 | **The delta-round rule into the four freeze commands** (data-contract, docs-review, doc-converge, features), which re-dispatch whole-surface briefs because their own text says *re-sweep the ledger* while the delta rule lives only in the partitioned-loop fragment. | `/fabrik-command-improve` ×4 | ~2 h | whole-surface re-sweeps |
| 5 | **Then, and only then, the instrument.** `/fabrik-command-improve` reads every queue, clusters verdicts by CAUSE across commands rather than by axis within one, targets the fragment or the mechanism owner, and records rounds and hours per command so an edit can be graded. | `/fabrik-spec` | spec-sized | whether items 1–4 held |

**Why item 5 is last.** It is the measurement machinery, and measurement built before the thing it
measures has changed is measurement of the old system. Yesterday's single-section edit to that
command took seven rounds precisely because it was made under the loop it was meant to improve.

**Not in this program, and why.** A seat-liveness signal (a hung seat is indistinguishable from a
slow one) lives in the Claude Code harness, not in anything this repo owns. Single-sourcing the
mirrored rules is a build change of spec size and is deferred until items 1–4 are measured.

### 5.1 The budget rule this program accepts

Every item above must **retire at least as many bytes as it adds**, or state in its D-row what the
growth buys. § 3.1 is the reason: a program that fixes the loop by growing the corpus has already
failed once.

---

## 6. How we will know it worked

Read from the same ledger, four weeks after item 1 lands, against the 2026-09-21 baseline:

| Metric | Baseline | Target |
|---|---:|---|
| Spec-chain cost at the medians | 611 min | under 300 min |
| Total hours per week | 375 | falling, with runs per week flat or up |
| Total tokens per week | 22.6 G | falling |
| Runs of 8+ rounds (review family) | 6 per week | 0 without an operator extension |
| Confirmed defects found after round 1 | 85% | under 50% |
| Series that rise at least once | 125 of 191 | under a quarter |
| `commands/_sources` + `_fragments` bytes | 1,230,048 | flat or falling |

### 6.1 The cobra check on each metric (D-253)

- **Rounds down** is satisfied most cheaply by closing before the quiet round. Counter: item 1's
  extension flag makes a legitimate long loop legal and visible, so hiding rounds is never necessary.
- **Hours down** is satisfied most cheaply by skipping probes. Counter: item 2 refuses the dispatch
  when the evidence is absent, so a skipped probe costs a round rather than saving one.
- **Tokens down** is satisfied most cheaply by not dispatching the closing fresh seat. Counter:
  D-206 already requires it, and the close records the seat count.
- **Corpus bytes flat** is satisfied most cheaply by moving text into a doc the weight check does not
  read. Counter: `check_corpus_weight.py` measures four surfaces as directory aggregates; the
  escape is `docs/reference/` and `docs/workstation/`, named here so the next reader can grep it.

---

## 7. Evidence, populations and bounds

Every figure above comes from one of five sources, each named with its population and its bound.

| Source | Population | Bound |
|---|---|---|
| Fleet feedback ledger `~/.claude/state/command-feedback.jsonl` | 335 closes, 24 commands, 10 repos, 803 h | begins 2026-09-07; nothing before it; LIVE and growing |
| `FEEDBACK:` lines in every session transcript on this box | 297 unique, 24 commands, 8 repos, 748 h | begins ~2026-09-01 |
| Run records `~/.claude/state/command-runs/*.json` | 27 records, 19 with a round series | older records are deleted; only their ledger row survives |
| Seat transcripts in session scratch | 814, 6 repos | only since the last scratch sweep |
| Git history of `commands/` and `CLAUDE.md` | full month | none |

**What is NOT covered.** 4,725 sessions predate 2026-09-01 and carry no per-command trace; most are
`youtube` and scratch sessions rather than command runs. That era ran a different convergence bar
(D-048, "zero findings") and can only be read as prose. Its absence means the month-long trend in
§ 3 is measured over two weeks of structured data plus the full month of corpus and decision history.

**Classification caveat.** Where § 4.1 counts verdicts by cause, the counts come from a keyword
classifier over the 335 `waste:` and `confusion:` fields and are indicative only — one verdict can
match two classes. The QUOTES are verbatim and are the evidence; the counts are the ranking.

