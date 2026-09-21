# Command loop performance — what we aim for, what it costs, and the program to fix it

**Status:** DRAFT § 5 — the revision-3 program (six additive mechanisms, item 1 approved in D-322) is
WITHDRAWN by the author in D-323 as wrong in kind; the replacement program in § 5 is subtractive and
awaits the operator's ruling. §§ 1–4 and 6–7 stand.
**Revision 4 (2026-09-21, on *"i still dont think you understand what is the problem"*):** the root
cause is re-cut one level up, to the system (§ 4.0): the process cannot shrink and its load is its
cost. § 4.1's loop mechanics are now stated as the consequence they are. § 5 is replaced whole. The
three-contract census and the load-vs-cost test are added with their derivations (§ 7.1).
**Revision 2 (2026-09-21, same day):** § 4 and § 5 rewritten. The operator refused the round
cap (*"capping is not a solution"*) and the first draft's root cause (*"you could not find the root
cause properly"*). Both refusals were right; the new root cause is § 4.1, the cap is refused in
§ 5.1, and two claims from revision 1 are withdrawn in § 4.5. The same revision adds § 2.5 (where
the rounds and the hours actually sit), the non-convergence detector's two measured limits inside
§ 4.1, and the full seat arithmetic behind § 4.5's second withdrawal.
**Revision 3 (2026-09-21, on *"be 100% sure first"*):** the document was stress-tested against its
own standard. § 4.1's prose-vs-code test is CORRECTED — the ledger records no surface size, so the
gap is real in direction but overstated in size; § 4.1 gains the positive control it lacked (the one
prose command that already carries an artifact-side terminal condition converges in 2–3 rounds);
§ 4.2 gains the supply side (seats are recall-optimised by design and the confirmed rate decays
from 69% at round 1 to 44% at round 10+); § 4.3 names the generator of the growth; § 7.1 carries
every new derivation.
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
| 2 | At most three convergence rounds, then park | the three-round ceiling, quoted in `01M2ZDAYX1EHVST1DWG8PV3Z57` | **No** — runs of 44 and 47 rounds are in the record, and 71 closes stopped EARLY with defects still confirmed (§ 4.1) |
| 3 | Tokens spent like money | *"it consumes all my tokens"* | **No** — 43 G tokens over two weeks, and rising week over week (§ 2.2, § 3.2) |
| 4 | The smallest lane that discharges the ask | *"that is why we have created fabrik-task"* | **Yes**, since D-314/D-315 (2026-09-20) |
| 5 | Every count, path and symbol EXECUTED before it is written | aim 12 of the 17; `CLAUDE.md` § read it, don't recall it | **No** — this is the mechanism under 87% of the hours (§ 4.1) |
| 6 | Check what already exists first: the project, fabrik-lib, the ledgers | aims 11, 13 | **Partly** — stated in § Drive 2026-09-20, untested |
| 7 | The fewest review passes that still catch real defects | aim 6 | **No** — 94 of 178 multi-round series rise instead of falling (§ 4.2) |
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
| Closes that ran to a quiet round | 78 of 191 (41%) — the rest stopped while still confirming (§ 4.1) |
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
| Confirmed defects found after round 1 | **4,564 of 6,919, 66%** over all 191 closes recording a confirmed series. (Revision 1 printed 85%, from the 11 records that state per-round counts — a true figure over a 687-defect subset, restated here against the whole population.) |
| Own-fix share of confirmed, where stated | median 0.67; at or above two-thirds in 56% of 54 rounds |

A round costs about 22 minutes whatever the diff size, because the seat re-reads the whole pin
regardless. Rounds do not get cheaper as the surface shrinks; they only get fewer, and they have not.

### 2.5 The shape of the distribution — where the rounds actually are

All 265 closes that record a round count, holding 613 h between them:

| Rounds | Runs | % of runs | Hours | % of hours |
|---|---:|---:|---:|---:|
| 1 | 25 | 9% | 24 | 4% |
| 2–3 | 107 | 40% | 91 | 15% |
| 4–9 | 98 | 37% | 240 | 39% |
| 10–19 | 26 | 10% | 139 | 23% |
| **20+** | **9** | **3%** | **120** | **19%** |

Half the runs already close in three rounds or fewer. **The 35 runs of 10+ rounds are 13% of the
population and 42% of the hours** — and § 4.1 is why they and the 3-round runs cannot be told apart
by their round count alone.

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

### 4.0 The root cause — the process cannot shrink, and its load is its cost

The operator's contract opens with one line: *fast but pro — ship, iterate, no over-engineering.*
The other six hundred lines of the same file violate it, and so does every command built under it.

**What an agent loads before it reads the request.** There are three live `CLAUDE.md` contracts
on this box (census in § 7.1): the hub's at **134,466 bytes / 605 lines**, the project template at
**127,624 bytes / 616 lines** in **47 byte-identical copies** (the template plus 46 synced repos),
and fabrik-lib's hand-kept one at 115,366. Every agent, every turn, starts under **≈30,000–34,000
tokens of contract**. Then it loads the command: the rendered corpus is **2.78 MB across 37
commands**, four of the eleven measured commands exceed 100 KB each.

**The load predicts the cost.** Across the 11 commands with four or more recorded closes, the size
of the rendered command an agent loads correlates with how long the run takes at **r = +0.64**
(log-log). The four smallest commands are the four fastest — 15 to 41 minutes at the median. The
four largest are the four slowest — 93 to 248 minutes:

| Rendered command | Bytes | Runs | Median min |
|---|---:|---:|---:|
| `/fabrik-task` | 27,090 | 4 | 41 |
| `/fabrik-command-improve` | 39,306 | 16 | 34 |
| `/fabrik-review-scoped` | 39,614 | 83 | 31 |
| `/fabrik-doc-converge` | 74,258 | 18 | **15** |
| `/fabrik-docs-review` | 76,600 | 8 | 60 |
| `/fabrik-spec` | 88,059 | 17 | 66 |
| `/fabrik-spec-review` | 91,167 | 28 | 85 |
| `/fabrik-plan-review` | 100,126 | 19 | 117 |
| `/fabrik-plan-after-chat` | 110,360 | 13 | 95 |
| `/fabrik-execute-plan` | 116,120 | 35 | 248 |
| `/fabrik-review` | 123,843 | 75 | 93 |

The one that breaks the pattern in the good direction, `/fabrik-doc-converge`, is the one whose
terminal condition is a single table rather than prose. This is not proof of causation — a bigger
command may govern bigger work — but the direction is unambiguous and it agrees with every other
measurement in this document.

**Why it cannot shrink.** § 4.3 counts it: the contract mandates at least five additions per fix and
not one deletion. A system with an ADD verb on every incident and no DELETE verb grows at the
incident rate — +111% corpus, +232% hub contract in one month (§ 3.1) — and a month of fixes
for the loop were, every one, more text for the loop to load.

**The chain, each link measured elsewhere in this document:**

1. The contract demands large artifacts — a spec with 70 `path:line` citations, evidence blocks,
   self-audits, a denominator on every count.
2. A large prose artifact has no fixed point a review can reach (§ 4.1). **That is real, and it is a
   symptom:** you cannot write a closed acceptance criterion for a 450-line spec; you can for a
   40-line one.
3. So reviews run 30 rounds, each round's fix adds text, and a finder seat that is recall-optimised
   by definition keeps finding (§ 4.2).
4. Each fix for *that* was another rule. Back to 1.

**This document is itself an instance.** It reached revision 4 in one day — three commits, three
decision rows, two CHANGELOG entries — and its revision-3 program proposed six new mechanisms for a
system whose measured problem is addition. § 5.1 withdraws them.

### 4.1 The loop-level consequence — "converged" is a fact about the reviewer, not about the artifact

*What § 4.0 produces inside a single review. Everything measured here holds; what changed in
revision 4 is its rank — this is the mechanism, not the cause.*

Every convergence loop in this corpus terminates on one condition: *a round that swept the class
ledger and confirmed zero defects*. Read that for what it is. It is a statement about **what one
reader did not find on one pass** — not about **what the artifact satisfies**. Nothing is written
down before a review opens saying what the artifact must be true of, and nothing is checked at the
close saying that it is.

So the loop has no fixed point to search for. A prose artifact has unbounded surface: a reader who
keeps reading keeps finding, and a reader who stops is never contradicted. **The round count is
therefore not a measure of the artifact's quality — it is a measure of the agent's stamina, and it
is arbitrary in both directions.** The ledger carries both tails:

| Of the 191 closes whose rounds record a confirmed count | Runs | Median rounds |
|---|---:|---:|
| Ran to a quiet round — the terminal condition actually met | 78 (41%) | 4 |
| Closed `done` with the last recorded round still confirming defects | **71 (37%)** | **3** |
| Closed `blocked` or `handoff` with defects still confirmed | 42 (22%) | — |

Those 71 `done` closes left **452 confirmed defects standing** at their last recorded round — a
median of 6 each, one of them 25. Such a close *can* be legitimate: the fixes may have been applied
after the last recorded round, or the residue routed to a backlog. **That is precisely the finding.
The record cannot tell the two apart**, because nothing requires the quiet round to exist before
`done` is accepted. The terminal condition is unverifiable from the record it governs.

A 44-round run and a 3-round run can therefore end in the same state, and the ledger cannot say
which artifact is sounder. This is why a round cap is not the fix (§ 5.1): a cap legislates the
round count, and the round count is already the wrong variable.

**And the one instrument aimed at this pathology cannot act, and half the time cannot see.**
`command_run.py` carries a non-convergence detector (`_non_convergence`, `scripts/command_run.py:288`)
that reads the round series and says when a loop is oscillating rather than converging. Two
properties, both read from the source:

- **It is advisory by construction.** Its own output closes *"(Advisory only — nothing is
  blocked.)"*, and the reason sits beside the code at `:399` — *"advisory is deliberately NEVER a
  gate — a heuristic that blocks is a heuristic that gets gamed."* That is the same argument § 5.1
  uses to refuse the round cap, reached independently by whoever wrote the detector, and it
  corroborates the refusal.
- **It looks only at the last three rounds** (`CONVERGENCE_WINDOW = 3`, `:71`) and never speaks
  before round five (`NON_CONVERGENCE_MIN_ROUNDS = 5`, `:65`). A loop grinding slowly downward is
  therefore "converging" by its rule. Replayed over the ledger: of **96 runs of five or more rounds**
  carrying a clean findings series it would have spoken on **47**, and stayed **silent on 49** — one
  of them a **29-round** run — because each one's last three rounds happened to be non-increasing.

So the system watches itself run 20, 30 and 47 rounds, is silent for half of them and powerless on
the rest. That is not a defect in the detector; a heuristic that blocked would be gamed, exactly as
its comment says. It is the shape of the problem — **nothing in the loop can act on the round count,
because the round count is not the thing that is wrong.**

**The falsifying test, and it holds.** If the cause is the absence of a checkable terminal
condition, then artifacts carrying a *partial* external criterion should converge faster than
artifacts carrying none. Split the 242 round-recording closes by what they review:

| Subject | Runs | Median rounds | p90 | Runs of 10+ |
|---|---:|---:|---:|---:|
| **Prose** — terminal is "a reader is satisfied" | 73 | **5** | 13 | 21% |
| **Code with an executable gate** | 169 | **3** | 10 | 12% |

The partition is named in full so it can be disputed. **Prose:** `spec-review`, `plan-review`,
`docs-review`, `doc-converge`, `data-contract`, `flows-review`, `workflow-review`,
`ui-design-review`, `rules-review`, `epics-review`, `features`. **Code with a gate:** `review`,
`review-scoped`, `execute-plan`, `task`, `repo-review`, `generate-tests`, `conformance-review`.
The remaining 23 of the 265 round-recording closes are in neither set and are excluded, not
assigned.

**Corrected in revision 3 — the size of that gap is overstated.** The ledger records no measure of
surface size (no diff lines, no artifact bytes), and the only proxy it offers — output tokens — grows
WITH the round count, so it cannot cleanly separate "bigger surface" from "more rounds". Stratifying
on it anyway, as the best available check:

| Size band (output-token quartile) | Prose median rounds | Code median rounds |
|---|---:|---:|
| smallest quarter | 2 (n=17) | 2 (n=41) |
| second | 4 (n=17) | 3 (n=41) |
| third | 5 (n=22) | 4 (n=36) |
| largest quarter | 10 (n=17) | 8 (n=41) |

The **direction holds in every band** — prose never converges faster than code at the same size —
which is what the terminal-condition theory predicts and what a size-only theory does not. But the
**magnitude is about one round, not two**, and rounds climb steeply with size in BOTH columns. Read
it as: the missing terminal condition is the reason the loop cannot end on evidence; the size of the
artifact is what makes that expensive. § 4.3 is therefore not second-order — it is the multiplier.

**The positive control — the prose command that already HAS an artifact-side terminal condition.**
Of the 62 prose reviews with a clean confirmed series, 9 ran dry within three rounds. **Five of
those nine are `/fabrik-doc-converge`** — 2 or 3 rounds each, 3 to 18 minutes, 2 to 5 seats. It
is the one prose command whose source states, per artifact, a closed completeness criterion BEFORE
the loop opens: its Convergence Contract table carries a *"Complete when (the bidirectional
contract)"* column per doc (`commands/_sources/fabrik-doc-converge.md:25-27`), and its Phase 1
opens with *"the doc is the CLAIM, never the source"* — every claim must open to something real
today (`:43-55`). That is the acceptance-list shape of § 5.2 item 1, already in the corpus, already
converging. The spec, plan and docs reviews carry no such column.

### 4.2 The mechanism this produces — the fix between rounds is the next round's defect

**The supply side first, because it is the half nobody measured.** The finder seat is optimised for
recall BY DESIGN — its definition says so in its first line, *"to maximize RECALL over a changed
surface"*, and its brief's step 3 is *"Surface every candidate"*
(`commands/_agents/fabrik-reviewer.md:3`, `:28`). A seat measured on what it raises will raise
things. Over the 248 runs with paired findings/confirmed series: **10,636 raised, 6,919 confirmed
— 35% of what seats raise is refuted or dropped**, identically for prose and code (65% confirmed in
both). And the rate DECAYS with the round: **69% confirmed at round 1, 64% at round 5, 57% at round
7, 44% at round 10 and beyond.** By round 10 more than half of what a seat raises is not a defect
— it is a candidate the orchestrator then spends a round refuting. This is § 4.1 seen from the
seat's side: the seat has no terminal condition either, so late rounds do not find fewer defects,
they manufacture more candidates.

With no criteria list to discharge, a round's only possible output is *what I happened to notice*,
and the fixer mutates the artifact between rounds. Each round therefore searches a **different
artifact**. A search over a space that is perturbed at every step has no fixed point, and the
arithmetic says so: **94 of 178 multi-round confirmed series (53%) rise at least once** instead of
falling; on the raw findings series it is 139 of 240 (58%). **4,564 of 6,919 confirmed defects
(66%) arrive after round 1**, and 2,168 (31%) at round 4 or later.

Every one of the six commands that hold the hours names this at its own close, verbatim:

- `/fabrik-execute-plan` — *"Phase B's review consumed 21 rounds, 7 of them reviewing the review's own fix prose"*
- `/fabrik-review` — *"three exit rounds each burned ~15 min on one narrow item the previous fix introduced"*
- `/fabrik-spec-review` — *"passes 19-43 were mostly precision edits to one regex/grammar paragraph, each costing three seats"*
- `/fabrik-plan-review` — *"passes 6–13 dominated by my OWN fix residue in ONE T02 clause, each round I rewrote a sentence and pinned without re-reading"*
- `/fabrik-data-contract` — *"rounds 4–22, about 60 seats and 16 h: every round's fixes added prose, cites and derived numbers that the next round found defects in"*
- `/fabrik-docs-review` — *"13 of the closing round's 14 confirmed defects were in prose I had just written"*

The orchestrator writes the fix from recall, on prose, without executing the claims it adds, and
the edit shifts the line numbers every citation in the artifact depends on. A fresh reader then
finds the residue — and, having no list to discharge, files it as a new defect rather than as a
re-check of a known criterion.

### 4.3 The multiplier — every fix for § 4.2 has been more rule text, and the contract mandates it

**The generator is the contract itself, and it can be counted.** For every fix, `CLAUDE.md` mandates
additions in the same change: a grader (*"PERMANENT = fix + grader — ship the regression test or
check IN THE SAME CHANGE"*, `:230`), a cobra note (*"written down IN THE SAME CHANGE"*, `:240`), a
decision row (*"gets its row in `docs/DECISIONS.md` in the SAME change"*, `:139`), a CHANGELOG
entry and a LESSONS LEARNT entry (§ Completion Contract 3–4), and every Doc Sync Matrix row the change
touches. That is at least **five mandatory ADD verbs per incident and zero mandatory DELETE verbs** —
of the 15 lines in `CLAUDE.md` (605 lines at HEAD) that mention *retire*, *delete* or *remove*, none
obliges a writer to retire text when adding it (§ 7.1). A system with add-on-every-incident and no
delete grows at the incident rate, which is what § 3.1 measured.

Rule text is loaded on every turn of every session in every repo. The corpus doubled and
`CLAUDE.md` tripled in the month the loop was being repaired. `CLAUDE.md` alone is now ≈ 33,600
tokens per turn before any command is read; the largest command source is 101 KB; the review
family's shared fragments are another 68 KB.

Three consequences, all measured:

1. **More text is more claims, and every claim is a finding a seat can raise.** The commands that
   grew fastest are the ones whose reviews run longest. Under § 4.1 this is not a coincidence —
   with no closed criteria list, artifact size *is* the search space.
2. **A rule stated in six files is six chances to drift.** Six of the nine fix commits on
   2026-09-20 were unreached mirrors, each found by the next fresh seat.
3. **Prose does not bind at the moment of writing.** Every rule violated in § 3.3's example was
   present, loaded, and had just been enlarged.

### 4.4 The two commands that are slow for a different reason

`/fabrik-plan-after-chat` and `/fabrik-spec` are not convergence loops. They write 400-line
artifacts with 70+ citations while the spec beneath them is still moving
(*"the intake re-derived figures the spec already carried because the spec was mid-amendment"*).
Their fix is an input freeze, not anything in § 5.

### 4.5 Two claims from this document's first draft, withdrawn

Recorded rather than quietly deleted, because both were produced by the very failure this document
is about.

- **"Round 1 finds only 1–10% of the defects" — WITHDRAWN.** That was read off the five longest
  runs. Over the 98 runs with four or more rounds, round 1's median share of its run's confirmed
  defects is **33%** (quartiles 20% and 51%), and only **12 of 98** fall under 10%. A tail was read
  as the population — the `denominator-honesty` rule, broken in the course of writing the document
  that invokes it.
- **"The loop is under-seated, and that is the root cause" — DEMOTED to contributing, unproven.**
  The under-seating is real and worth its own row in a later program: **64 of 265** round-recording
  runs declared no seats at all — 9 of those ran 10+ rounds, 132 rounds between them with no seat
  ever stamped — and the 26 long runs that did stamp seats averaged **2.43 per round**, against a
  contract floor of 3 for round 1 alone and 7 for a 3-unit surface. But the direction is not
  established: runs at under 2 seats per round take a median of 4 rounds against 2 for runs at 4 or
  more (n=106 vs 21), and surface size drives both numbers, so the comparison is confounded. Seat
  density is a candidate, not a cause, and this document does not spend a program item on it until
  items 1–3 have moved the metrics they target.

---

## 5. The program — subtract

### 5.1 What stood here before, and why it is withdrawn

Revision 1 led with a hard round cap; the operator refused it (D-321) and the ledger agreed — it
cuts real work, its cheapest satisfaction is to find less, and it acts on a variable that is already
the wrong one. Revisions 2–3 replaced it with six **additive** mechanisms — an acceptance list, a
close assertion, a fixer rule, a pin gate, a reason log, an instrument — and the operator approved
the first (D-322). **The author withdraws all six (D-323).** § 4.0 is the reason: a system whose
measured problem is that it can only add cannot be repaired by six additions, however well-aimed.
The acceptance-list idea survives inside item 2 below as a *shape for what stays*, not as a new
layer.

### 5.2 The items — every one ends smaller than it started

| # | Cut | What stays | Before → target |
|---|---|---|---|
| 1 | **The contract.** Every incident narrative, every *"executed 2026-09-xx"* paragraph, every restatement of a rule that lives elsewhere, every mechanism explanation that belongs beside its code. Three edits: the hub file, the template (reaches 46 repos on one sync), a mail to fabrik-lib for theirs. | The lane table · the HARD STOPS table · the universal anchors (verbatim — detectors key on them) · the FINAL OUTPUT block · the commit recipe **as a pointer to a script**, not as prose · the `@` import. Every executable guard — hooks, gates, `command_run.py` — is untouched: prose never bound anyway (Lesson 116), the checks do. | 134,466 → **≤ 25,000 B** (hub) · 127,624 → ≤ 25,000 (template) |
| 2 | **The commands.** Each cut to its spine: what it does · its terminal condition as ONE table in `/fabrik-doc-converge`'s shape (*ground truth to sweep · complete when*) · its NEXT. The fragments the same. | The run record · the seat stamp · the fixer-never-closes rule (the one loop rule the ledger proves — 53% rising series) as the terminal table's last row, not a new mechanism. | no rendered command over **30 KB** (today 4 of 11 exceed 100 KB); corpus 2.78 MB → ≤ 1 MB |
| 3 | **The artifacts.** The demand that a spec carry 70 citations, evidence blocks and a self-audit. A spec is a page; a plan is a list and its tickets; a review receipt is its ledger and its verdict. | `path:line` grounding for a claim that names code; the D-row for a decision. | spec ≤ 150 lines · plan spine ≤ 100 · receipt ≤ 60 — stated in each command's terminal table, no new check |
| 4 | **The five mandatory additions per fix** (§ 4.3). | A D-row for a DECISION — not for every fix. A CHANGELOG line. A grader for a CODE fix. | LESSONS per ticket, the cobra note per mechanism, and the grader-for-prose become optional; the contract says so in one sentence and deletes the five that said otherwise |
| 5 | **The dead copies.** 14 `CLAUDE.md` under `/opt/archived/`, two 11-byte stubs, the two drifted fabrik-lib siblings. | — | 70 → 52 files on disk; the fabrik-lib siblings by mail |

### 5.3 How it is done — not through the loop

Direct edits, in one session, by hand. Each cut is read ONCE by a fresh non-authoring seat with a
single question — *did anything that binds get cut?* — and the answer is checked against the hooks
and gates, which are the things that bind. No spec chain. No partitioned review. One forced sync
for the template. **This is the operator's word overriding the contract's own ceremony, and the
D-row for the cut says so**, because the alternative — running the cut through the process it is
cutting — is the month again.

### 5.4 The budget rule, inverted

Revision 3 said *retire at least as many bytes as you add*. Revision 4 says **every item ends
smaller than it started, and the D-row carries the before and after in bytes.** An item that ends
larger has failed, whatever else it achieved.

---

## 6. How we will know it worked

Read from the same ledger, two weeks after § 5.2 item 1 lands, against the 2026-09-21 baseline. The
size rows are the ones keyed to § 4.0; the round rows are how we know the size rows mattered.

| Metric | Baseline | Target |
|---|---:|---|
| **Closes that ran to a quiet round** (terminal condition actually met) | 78 of 191, **41%** | over 90% |
| **Closes `done` with defects still confirmed at the last round** | **71** (452 defects standing) | 0 |
| **Confirmed defects found at round 4 or later** | 2,168 of 6,919, **31%** | under 10%, with the total NOT falling |
| **Multi-round series that rise at least once** | 94 of 178, **53%** | under 20% |
| Median rounds, prose artifacts vs code-with-a-gate | 5 vs 3 | converged, at 3 or below |
| Spec-chain cost at the medians | 611 min | under 300 min |
| Total hours per week | 375 | falling, with runs per week flat or up |
| Total tokens per week | 22.6 G | falling |
| **Hub `CLAUDE.md` bytes** (loaded every turn) | **134,466** | **≤ 25,000** |
| **Template `CLAUDE.md` bytes** (×47) | **127,624** | **≤ 25,000** |
| **Largest rendered command** | 123,843 | ≤ 30,000 |
| Rendered corpus, 37 commands | 2,783,253 | ≤ 1,000,000 |
| `commands/_sources` + `_fragments` bytes | 1,230,048 | falling (§ 5.4) |

The third row carries its own guard deliberately: *"with the total NOT falling"*. Driving
late-round defects to zero by finding fewer defects overall is the failure mode, not the goal.

### 6.1 The cobra check on each metric (D-253)

- **"Ran to a quiet round" up** is satisfied most cheaply by declaring a round quiet without
  sweeping — the cheapest quiet round is the one nobody ran. Counter: item 3, the terminal round
  requires a fresh non-authoring seat, and the close records its id.
- **"Hot `done` closes" to zero** is satisfied most cheaply by not RECORDING the last round's
  confirmations. Counter: item 2 asserts per criterion, so an undischarged criterion refuses the
  close whether or not a round was written down.
- **"Round 4+ defects" down** is satisfied most cheaply by stopping at round 3 — which is the cap
  this program just refused. Counter: the paired guard in the row above, plus item 5, which makes a
  long loop legal and visible rather than something to hide.
- **"Rising series" down** is satisfied most cheaply by reporting a flat or falling number
  regardless. Counter: the series is written per round by the tool, not at the close.
- **Hours and tokens down** are satisfied most cheaply by skipping probes. Counter: item 4 refuses
  the dispatch when the evidence is absent, so a skipped probe costs a round rather than saving one.
- **Corpus bytes flat** is satisfied most cheaply by moving text into a doc the weight check does
  not read. Counter: `check_corpus_weight.py` measures four surfaces as directory aggregates; the
  escape is `docs/reference/` and `docs/workstation/`, named here so the next reader can grep it —
  and this document lives in `docs/reference/`, so it is itself inside its own blind spot.

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

**Classification caveat.** Where § 4.2 counts verdicts by cause, the counts come from a keyword
classifier over the 335 `waste:` and `confusion:` fields and are indicative only — one verdict can
match two classes. The QUOTES are verbatim and are the evidence; the counts are the ranking.

### 7.1 How § 4.1's figures were derived (revision 2)

Reproducible against the same snapshot, so the root cause can be refuted rather than believed.

| Figure | Derivation |
|---|---|
| 191 closes with a usable confirmed series | rows where `confirmed` is a list, non-empty, and every element an `int` — 144 of the 335 closes are excluded because the field is absent or carries `null` for some rounds |
| ran dry / stopped hot | the sign of `confirmed[-1]`; `state` splits the hot ones into `done` 71, `blocked` 27, `handoff` 15 |
| 452 defects standing | `sum(confirmed[-1])` over the 71 `done` rows |
| prose vs code medians | commands partitioned by the artifact each reviews; the partition is a JUDGEMENT and is listed member by member under § 4.1's table; 23 closes fall in neither set and are excluded |
| round-1 share, median 33% | `confirmed[0] / sum(confirmed)` over the 98 rows with 4+ rounds and a non-zero total |
| seat density | `seats_declared / rounds`; 64 of 265 round-recording rows carry no seat stamp at all and are excluded from the density comparison, not counted as zero |
| size-stratified prose vs code (rev. 3) | size proxy = `tok_out + tok_seat_out`, quartiles over the 232 prose+code rows carrying it; ⚠️ the proxy grows with rounds, so this bounds the confound rather than removing it — the ledger records no surface size |
| noise rate and its decay (rev. 3) | the 248 rows whose `findings` and `confirmed` lists are equal-length and all-int; per-round rate = Σ confirmed / Σ findings at that round index, rounds 10+ pooled |
| positive control (rev. 3) | prose rows with a clean confirmed series (62), `len ≤ 3` and `confirmed[-1] == 0` → 9; the command of each read off the row |
| CLAUDE.md census (rev. 4) | `find /opt -type f -name CLAUDE.md` excluding `.claude/worktrees/`, `.tmp/`, `node_modules/` → 70 (+177 worktree copies); grouped by md5 → 47 identical to the template, 23 others, of which 20 are archived/vendored/stubs; sizes by `stat -c %s`; no `~/.claude/CLAUDE.md` exists |
| load-vs-cost (rev. 4) | bytes = `~/.claude/commands/fabrik-*.md` (the RENDERED file an agent loads); commands with ≥ 4 closes → 11; median `wall_s/60` per command; Pearson r over log(bytes) vs log(median minutes) → +0.64; not a causal claim, a direction — the ledger records no surface size (§ 4.1) |
| ADD-verb count (rev. 3) | the five clauses cited in § 4.3 by `CLAUDE.md` line; the negative is bounded to `CLAUDE.md` at HEAD (605 lines), `grep -n "retire\|delete\|remove"` → 15 lines, each read: a class retiring inside the loop (`:39`), "retirement" as a decision type (`:138`, `:320`), the volume-deletion ban (`:288`), file-removal doc-sync triggers (`:304`, `:314`, `:318`), scratch cleanup (`:369`), recipe prose — none an obligation to retire text |

**Two bounds on all of it.** (1) `confirmed` is written by the agent running the loop, so a run
that under-reports its confirmations looks convergent — the numbers describe what was RECORDED, and
§ 5's items 2 and 3 exist partly to make the record harder to write falsely. (2) The hot-close
count cannot distinguish an abandoned run from one whose final fixes were applied after the last
recorded round; § 4.1 rests on that ambiguity being unresolvable, not on every one of the 71 being
an abandonment.
