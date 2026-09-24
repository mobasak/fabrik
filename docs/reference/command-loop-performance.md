# Command loop performance — what we aim for, what it costs, and the program to fix it

**Status:** REVISION 24 (2026-09-23). The program of revisions 4–7 (the old § 5: remove the apparatus) was
executed in part on 2026-09-21 and REVERTED the same day (D-330) — it removed developments the operator built on
purpose. § 1.0 records what the three `CLAUDE.md` contracts are now (D-331, lean without loss). § 4.7 states the
root cause the operator confirmed on 2026-09-21 16:38, and § 5 is rewritten as the engineering that follows from it:
inside the review loop, not around it. §§ 2–4 keep the 2026-09-21 snapshot; re-read 2026-09-22 (338 closes, 807 h —
three closes and 4.5 h since) every headline figure re-derives to the same percentage (§ 7.1). Revision history: § 8.
**Written:** 2026-09-21, by the unnamed hub window, on the operator's directive
("create a full documentation ... for the last month we are working these and it gets worse, not better").
**Nature:** a diagnosis and a program. Every number is measured, with its population named in § 7.
No number in this document is recalled.
**Snapshot:** all ledger figures are one read taken **2026-09-21 12:25 +03**. The ledger is live and
grew by two closes while this document was being written, which is itself an instance of § 4.2 —
re-derive before quoting, never copy a figure forward.

---

## 1. What we aim for

**The goal, in the operator's words (2026-09-22, restated because revision 8 left it out):** every command
enforces the use of our MCPs, our rules, our infrastructure and the manifesto; every run is **lean, fast, accurate
and complete** — all four, not one at the cost of the others; and a single doc edit or a single simple development
— its spec, spec review, plan, plan review, execution and review — is done in **two hours**, not the one or two days
it takes today. `/fabrik-task` was created for the smallest of those; the spec chain must meet the same bar for the
rest. Measured today (§ 2.1): the chain costs 611 minutes at the medians, five times the target; `/fabrik-task`
costs 41. § 4.8 says why the loops miss it: the objective they run on has one term.

The fourteen aims below were stated across 2026-09-07 to 2026-09-21 and are the same goal in detail. They are the
contract every `/fabrik-*` command is judged against. The third column is the measured state at the snapshot date.

| # | The aim, in the operator's terms | Source | Holds today |
|---|---|---|---|
| 1 | A demand answered the same session, never a day of waiting | *"i keep waiting 1 day for any demand"* | **No** — the spec chain costs 10.2 h at the median (§ 2.1) |
| 2 | At most three convergence rounds, then park | the three-round ceiling, quoted in `01M2ZDAYX1EHVST1DWG8PV3Z57` | **No** — runs of 44 and 47 rounds are in the record, and 71 closes stopped EARLY with defects still confirmed (§ 4.1) |
| 3 | Tokens spent like money | *"it consumes all my tokens"* | **No** — 43 G tokens over two weeks, and rising week over week (§ 2.2, § 3.2) |
| 4 | The smallest lane that discharges the ask | *"that is why we have created fabrik-task"* | **Yes**, since D-314/D-315 (2026-09-20) |
| 5 | Every count, path and symbol EXECUTED before it is written | aim 12 of the 17; `CLAUDE.md` § read it, don't recall it | **No** — this is the mechanism of § 4.2, named by every one of the six commands that hold the hours |
| 6 | Check what already exists first: the project, fabrik-lib, the ledgers | aims 11, 13 | **Partly** — stated in § Drive 2026-09-20, untested |
| 7 | The fewest review passes that still catch real defects | aim 6 | **No** — 94 of 178 multi-round series rise instead of falling (§ 4.2) |
| 8 | The box used fully, in parallel, nothing read twice | aims 1, 2 | **Partly** — the seat budget is computed; non-duplication is by construction, not by rule |
| 9 | The cheapest model that can do each seat's job | aim 3, the price multipliers | **Yes** — D-190, by rule |
| 10 | Fable drives while its own quota allows, else Opus | aims 4, 17b | **Yes** — D-295 + § Drive |
| 11 | A dead seat re-dispatched, a stuck run handed off | aim 9 | **Partly** — `handoff` works; a hung seat still has no signal |
| 12 | One source per rule, nothing restated | aim 16 | **No** — one rule lives in six files (§ 4.3) |
| 13 | Only hub `infra` or `intel` runs the corpus tools | aim 17a | **Stated, not gated** |
| 14 | Every run makes the next run cheaper | the kaizen loop, aim 5 | **No** — 228 loop verdicts written, 4 ever answered |

One line under all of it, from `CLAUDE.md`: *fast but pro, ship, iterate, no over-engineering.*
What the system delivers instead is **pro but slow**.

## 1.0 The three `CLAUDE.md` contracts — what was cut, reverted, and what stands (2026-09-22)

**What was cut on 2026-09-21 and reverted the same day.** The old § 5's step 3 ("thin the always-on file to a
page") was executed as a byte cut: hub `CLAUDE.md` 134,466 → 61,400 B (D-326, D-328), the fleet template
127,624 → 62,003 B synced to 41 repos (D-329), the shared-append commit recipe turned into a script (D-328), the
QUOTA bullet into a pointer (D-327). Every step was green against every grader. The operator reverted all of it
(D-330, `174267506`): an audit found **21 ungraded rules lost from the hub contract and 17 from the template** —
the cuts were safe against everything a grader pinned and unsafe against everything no grader pinned — and the
program as a whole had been removing capability the operator built deliberately (seats, commands, autonomous
completion). The apparatus is the operator's design for the factory § 4.7 describes; "remove it" (old § 4.00)
was this document's misreading of the author's stance, not the author's stance.

**What stands instead — lean without loss (D-331, operator, stated twice).** Stories out, rules in: every rule
kept, checked by a sentence-unit loss audit plus the grader pins, one pass per surface, 17 commits between
2026-09-21 and 2026-09-22 (`274a3e1d1` … `1c6bea1d8`):

| Contract | 2026-09-21 snapshot | Today | Change | How |
|---|---:|---:|---:|---|
| hub `/opt/fabrik/CLAUDE.md` | 134,466 B / 605 lines | **100,892 B** / 676 lines | −25% | passes 1, 2a–2d: the shared-repo bullet, the gate paragraph, the trailer trap, peer channels, mail, upstream, the denominator row, the anchors index — incidents and provenance removed, every rule and anchor kept |
| fleet template `templates/governance/CLAUDE.md` | 127,624 B / 616 lines, 47 identical copies | **103,912 B** / 704 lines | −19% | the same passes; force-synced — **46 of 49** `/opt/*/CLAUDE.md` are byte-identical to it today (the three that differ are fabrik-lib's checkouts, sync-excluded by design) |
| `/opt/fabrik-lib/CLAUDE.md` | 115,366 B | **115,366 B** / 758 lines | 0 | GENERATED by fabrik-lib's own `refresh-governance.sh` (`/opt/fabrik-lib/scripts/`); the hub edits it only by mail — the lean text for its QUOTA bullet is mailed (`01M327TF7ERCBYHRA9448DSD01`) and parked until fabrik-lib applies it |

The same program leaned six rule packs, five command sources and fragments (passes 3a–3f) and four workstation and
workflow docs (4a–4c), each with zero rule loss and stale figures corrected as found. Per-turn load today: about
25,000 tokens of hub contract before a command is read, against about 33,600 at the snapshot; the rendered corpus is
2,743,865 B over 37 commands (was 2,783,253). **What did not change, by ruling:** the review family, the seats, the
partition, the run record and the ledgers — the things the old § 5 proposed to retire are the things § 5 now makes
work.

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

Six commands hold 88%. `/fabrik-execute-plan` is itself mostly review: 73 review-family closes
fall inside plan windows in the same repo, 144 of its 245 hours. `/fabrik-review-scoped` is the
least-loaded command in the family and the fastest — 83 runs, the most of any command, at a
31-minute median — which is what § 4.00's load-vs-cost predicts, not a vindication of the loop.

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

### 2.6 Where the minutes sit, by activity — the orchestrator's turns (2026-09-22)

The same ledger, read per command for the wall clock, the ORCHESTRATOR's message count (`tok_msgs`, the lead session's
own requests), the seats seen, and the orchestrator's share of the run's token cost (medians; population = every close
of that command carrying token data):

| Command | Runs | Wall | Orchestrator msgs | Seats | Orchestrator share | Min per msg |
|---|---:|---:|---:|---:|---:|---:|
| `/fabrik-spec` | 17 | 66 min | 56 | 4 | 64% | 1.2 |
| `/fabrik-spec-review` | 28 | 84 min | 58 | 9 | 47% | 1.3 |
| `/fabrik-plan-after-chat` | 13 | 95 min | 83 | 8 | 62% | 0.9 |
| `/fabrik-plan-review` | 19 | 117 min | 93 | 8 | 69% | 0.8 |
| `/fabrik-execute-plan` | 35 | 248 min | 326 | 19 | 69% | 0.8 |
| `/fabrik-review` | 82 | 86 min | 99 | 8 | 68% | 0.9 |
| `/fabrik-review-scoped` | 86 | 31 min | 36 | 5 | 67% | 0.7 |
| `/fabrik-task` | 4 | 41 min | 31 | 5 | 39% | 1.1 |

**Wall clock is the orchestrator's message count times about one minute, in every command.** The seats run in
parallel and finish in minutes; the lead session's turns — reading, dispatching, executing a claim, filling a receipt,
running a gate, committing — are serial and each costs about a minute of clock and one full re-read of the transcript
(§ 4.9: 76% of the orchestrator's tokens are that re-read). The chain's 611 minutes are ~615 lead turns. **The two-hour
goal is a 120-turn chain.** Rounds, seats and models are second-order to this one variable; § 5's chunks 5–7 act on it.

**The distribution, not only the median (2026-09-22, `tok_msgs` per close carrying it; n per command):**

| Command | n | p10 | p25 | p50 | p75 | § 6 target |
|---|---:|---:|---:|---:|---:|---:|
| `/fabrik-review` | 78 | 21 | 38 | 99 | 254 | 15 |
| `/fabrik-review-scoped` | 81 | 9 | 19 | 36 | 71 | 15 |
| `/fabrik-spec-review` | 28 | 25 | 39 | 58 | 86 | 20 |
| `/fabrik-plan-review` | 18 | 27 | 56 | 92 | 267 | 20 |
| `/fabrik-spec` | 17 | 26 | 31 | 56 | 80 | 25 |
| `/fabrik-plan-after-chat` | 13 | 21 | 41 | 83 | 104 | 25 |
| `/fabrik-execute-plan` | 34 | 74 | 126 | 326 | 486 | 60 |

Every target sits at or below today's 10th percentile. A turn cap at a loop's 25th percentile cost 20–59% of solved
tasks and one at the 75th cost nothing (§ 4.9 finding 8), so the turn budget is reached by changing the SHAPE (§ 5.3),
never by refusing the lead a turn: it is printed at `start` and read at the close, and each chunk's KILL reads it.

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

### 4.00 The ground — we built an apparatus on a tool designed to need almost none

*Read with § 4.7 and § 1.0. What stands from this section is the stance on the always-on file — more context on
demand, a thin file — and D-331 executed it without losing a rule. Its closing sentence, "remove it, and put the
person and the tool back", was this document's error and was reverted (D-330): the apparatus is the operator's
design for an autonomous factory, built on purpose, and what the author's method demands of it is only that its
feedback loop touch reality — which is exactly what § 4.7 finds the loop stops doing after round one.*

The person who built Claude Code gave a talk on how to use it (§ 4.6, the primary source for this
section). It is not a list of tips. It is a design stance, and it is the opposite of what this repo
did:

- *"The reason it knows it, by the way, is not because we prompted it to. There's nothing in the
  system prompt about looking through git history. It knows it because the model is awesome."* — and
  again about commit/push (*"we're not system prompting it to do this... The model is good"*) and about
  tools (*"you don't have to prompt it specifically to use this tool and this tool"*). **Do not tell
  the model what it already knows.**
- *"Try to keep it pretty short, because if it gets too long it's just going to use up a bunch of
  context and it's usually not that useful. So just try to keep it as short as you can."* — on
  `CLAUDE.md`. Theirs: bash commands, a style guide,
  a few core files. Everything else on demand. **More context, thinner always-on file.**
- *"If you let it iterate two or three times, often it gets it almost perfect. So the trick is: give
  it some sort of tool that it can use for feedback to check its work, and then based on that it will
  iterate by itself."* — tests, a screenshot, a probe. **Correctness comes from a tool that touches reality, run by Claude itself,
  during the work.** He describes no reviewer, no convergence, no rounds.
- *"Brainstorm ideas, make a plan, run it by me, ask for approval before you write code."* and *"No
  matter what Claude is doing, you can always safely hit escape... I'll hit escape, I'll tell it that,
  and then I'll tell it to redo the edit."* — **the person approves the shape once and interrupts
  freely.** That is the judgement loop: a glance, not a panel.
- *"We want to avoid over-investing in UI and other layers on top, given that... the way the models
  are progressing, it may not be useful work pretty soon."* — **Layers on top of the model are the
  thing not to build.**

This repo built the layers. A 134 KB always-on contract, 2.8 MB of rendered commands, run records,
seat panels, coverage checkers, a feedback ledger, a kaizen loop, a lane table, hooks on hooks — and
a review family that is **57% of all recorded hours**, every command in it a model reading another
model's output — code or prose — and converging on a reader's verdict rather than a tool's. None of
that is in the tool's design. It was built to replace two things the design
relies on and this repo removed: **the person** (rules were written against consulting them, because
stalls were frustrating) and **the feedback tool** (a test, a screenshot, a probe that Claude runs
itself). An apparatus built to replace a person and a tool can only measure itself — which is why
its definition of *done* became the one in § 4.0, and why a month spent perfecting it made things
worse. The author's stance says: do not perfect it. Remove it, and put the person and the tool back.

**This document is the demonstration.** It reached revision 6 in one day — **9 commits**
touching this file, **5 decision rows** (D-321 to D-325), every gate green, everything pushed —
and after each of the first five revisions the operator said it had not found the cause. Its
revision-3 program proposed six new mechanisms for a system whose measured problem is addition.
Every definition of *done* this system has was met each time; the operator's was not, until the
operator handed over the author's talk and had it read three times.

### 4.0 The mechanism — "done" is process compliance, not an outcome the operator can see

*What the apparatus of § 4.00 produces, necessarily: it can see only itself, so it measures only
itself.*

**Every run in this system ends when its process is satisfied, and nothing checks whether the
operator got what they asked for.** The Stop hook releases a turn when the run record is closed,
the gate is green, the commit is pushed, a review-family pass ran and the seven-line block is present
— GATE · DOCS · CHANGELOG · LESSONS · DONE · NEXT · FEEDBACK. Not one of those is the operator's
question. And the runs define their own ends the same way: of the **27 run records on disk, 25 name the
process's own completion as their terminal condition** — *"a delta pass raises zero"*, *"a quiet
closing round"*, or an executable check of the process such as *"gate green"* or
*"docs_updater --check green"* — and the other two name internal build state. **None names a check
of the delivered thing itself** — the feature running, the screen matching the mock, the spec
answering the question the operator will ask. (Bound: run records are deleted over time; the ledger
row that survives them carries no terminal field, so 27 is the whole readable population — § 7.1.)

Agents optimise what is measured. Measured on compliance, they produce compliance, and the
operator's demand is incidental to it. That is the mechanism under every symptom in this document:

- **Why the rules grew (consequence 1, below):** every failure was an agent doing the wrong thing,
  and the only lever was to describe the right thing in more text. Text does not change behaviour;
  the definition of *done* does. So the text grew and the behaviour did not.
- **Why reviews run 30 rounds (consequence 2, § 4.1):** a review's *done* is *a reader was quiet* —
  a process event. Were it *the artifact is correct against the three things it must get right*,
  round three would be the end, because the target is finite and someone else set it.
- **Why a cap, an acceptance list and a byte cut are all symptoms:** each changes the process. None
  changes what the process is *for*.
- **Why the month got worse:** every fix was more of the thing being measured.

#### Consequence 1 — the process cannot shrink, and its load is its cost

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

### 4.1 "converged" is a fact about the reviewer, not about the artifact (consequence 2)

*What § 4.0 produces inside a single review: a terminal condition that is the reviewer's, because
nobody stated the operator's. Everything measured here holds; what changed since revision 3 is its
rank.*

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

| Size band (output-token quartile) — over the 232 rows carrying token fields: all 73 prose, 159 of the 169 code | Prose median rounds | Code median rounds |
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
today (`:43-55`). That is the shape § 5 item 4 asks of every slice — the claims stated before the loop opens, verified by execution —
already in the corpus, already converging in round one. The spec, plan and docs reviews carry no such column.

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

**The generator is the contract itself, and it can be counted.** For every fix, `CLAUDE.md` — read at
commit `341c839a0`, the last before § 5 item 3 began cutting it; the line numbers below are that
commit's — mandates additions in the same change: a grader (*"PERMANENT = fix + grader — ship the regression test or
check IN THE SAME CHANGE"*, `:230`), a cobra note (*"written down IN THE SAME CHANGE"*, `:240`), a
decision row (*"gets its row in `docs/DECISIONS.md` in the SAME change"*, `:139`), a CHANGELOG
entry and a LESSONS LEARNT entry (§ Completion Contract 3–4), and every Doc Sync Matrix row the change
touches. That is at least **five mandatory ADD verbs per incident and zero mandatory DELETE verbs** —
of the 15 lines in `CLAUDE.md` (605 lines at HEAD) that mention *retire*, *delete* or *remove*, none
obliges a writer to retire text when adding it (§ 7.1). A system with add-on-every-incident and no
delete grows at the incident rate, which is what § 3.1 measured.

Rule text is loaded on every turn of every session in every repo. The corpus doubled and
`CLAUDE.md` tripled in the month the loop was being repaired. `CLAUDE.md` alone is now ≈ 33,600
tokens per turn before any command is read; the largest command source is 101 KB
(`fabrik-execute-plan.md`, 101,374 B); the `term-*` fragments the review family shares are another 54 KB
(all fragments, 136 KB). Revision 1 printed 68 KB here; it does not reproduce and is withdrawn.

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
Their fix is an input freeze — outside this document's program, which is the loop (§ 5).

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
  density is a candidate, not a cause — and under § 5 it is fixed by construction: the partition of round one
  names the seats, and every later pass keeps them.

### 4.6 The tool's author on how it is meant to be used — the source for § 4.00

Read on the operator's instruction 2026-09-21, five times — the first two readings mined it for
quotes agreeing with revisions 4–5; the third read it as what it is; the fourth and fifth, each
paired with a full read of this document, found nothing the third had not. Transcript:
`/opt/youtube/output/XFYUKBPfUMw_transcript.txt` (5,589 words; the speaker introduces himself as
Boris, member of technical staff at Anthropic, who created Claude Code).

The talk is a **ladder of trust**, one rung per section, and the rungs are the method:

| Rung | What he says | What this repo does instead |
|---|---|---|
| 1 · Ask first | Day-one Q&A on the codebase; it *"start[s] teaching them this boundary of... what can be one-shotted? What can be two-shotted, three-shotted?"* The person learns the model's envelope by using it. | Sizing is computed by a gate that counts files; the person has been one remove away, behind commands and agents, for a month. |
| 2 · Then edit | Three tools; the one failure he names is *"the thing that it builds is not at all the thing that you wanted"* and the fix is upstream: *"make a plan, run it by me, ask for approval before you write code."* | A 10.2-hour spec chain before a line is written, then review downstream. |
| 3 · Give it a feedback tool | Tests, screenshots — *"then it can iterate... two or three times... by itself."* | Reviews that end when a reader is quiet — 30 rounds; 0 of 27 runs name a check of the delivered thing as their terminal. |
| 4 · More context, short file | *"The more context, the smarter the decisions"* — and `CLAUDE.md` *"as short as you can"*; nested files, slash commands and `@`-mentions pulled in **on demand**. | 134 KB every turn; the actual context — code, tests, the running thing — reached only through a seat's report. |
| 5 · Share once | One project file, one `.mcp.json`, one permissions allow-list — *"you write this once and then you share it with everyone on the team... and everyone on the team benefits."* | 47 copies of a 128 KB file, synced on every commit that touches it. |
| 6 · Steer constantly | Shift-tab, `#`, escape — *"you can always safely hit escape"*, *"19 of these lines look perfect but one line you should change."* Interruption is the normal mode. | Rules against mid-run asks; `NEXT: operator decision` has a bar; the operator's interruptions today were the only thing that reached the cause. |
| 7 · Then headless | `claude -p` as *"a super intelligent Unix utility"* — pipe a log in, JSON out; CI, incidents, labelling. Small, bounded jobs. | Autonomous multi-hour runs. |
| 8 · Then many | Worktrees, tmux; *"I'm sort of a Claude normie. So I'll have usually like one Claude running at a time."* | Up to three concurrent sessions plus a daily pipeline, by contract. |
| Q&A · Layers | *"Avoid over-investing in UI and other layers on top... it may not be useful work pretty soon."* | 2.8 MB of layers. |

The two things missed on the first two readings: the warning about layers (it sits in an answer
about IDEs, not in the tips), and that *"keep it short"* is not *"less context"* — it is **more
context, delivered lazily, with a thin always-on file.** This repo inverted both.

### 4.7 The root cause, confirmed — the loop is a partitioned verification only in round one

*Stated by this window on 2026-09-21 16:38 in plain words, confirmed by the operator ("ok good. you get it right this
time"; the D-330 restart terms say the same). It supersedes § 4.00's program and ranks § 4.0–4.3 as its consequences.*

**The problem.** A task that should finish in one session comes back a day later, and the review that was supposed
to make it correct ran thirty rounds and still left defects standing.

**What the operator is trying to achieve.** An autonomous factory. A task is handed over; the agents split it across
seats, verify every claim in parallel against reality — the file opened, the count re-derived, the test run — fix
and re-verify their own parts, and finish in one to three passes, correct, with nobody sitting in the loop and nobody
waiting a day. The seats, the partition, the ledger, the cheapest-model-per-seat rule — that is the design for that.
It was built on purpose. It is not to be removed; it is to do what it was built to do.

**The root cause.** The loop is a parallel, partitioned verification — **but only in round one.** From round two on it
degenerates into something else: one seat re-reads the whole artifact, the brief becomes "find anything", fixes are
written from recall so they seed the next round, and the loop ends when a reader is tired rather than when the
artifact's claims are verified. So the machine designed to converge in three parallel passes runs as a serial hunt
for thirty. The month of fixes made the contract heavier and never touched that mechanism — and the 2026-09-21
program did the same thing in the other direction: it cut text and removed parts, when the fix is to make the loop
run as designed.

**The evidence is already in this document, ranked wrongly until now.** § 2.4: a round costs 22 minutes whatever the
diff size, because the seat re-reads the whole pin. § 4.2: the fix between rounds is the next round's defect, and the
seats' confirmed rate decays from 69% at round 1 to 44% at round 10 — six commands say it verbatim at their own
close. § 4.1: the terminal is a reader's silence, never "every part verified". And two runs on 2026-09-22, executed
by this window after the determination, are the demonstration in miniature: `/fabrik-doc-converge` over
`SCAFFOLD_STRUCTURE.md` ran 7 rounds (confirmed 32 → 13 → 5 → 2 → 2 → 1 → 0, 13 seats, 56 min) and over
`DATA_SYNC_WORKFLOW.md` 6 rounds (12 → 6 → 1 → 0 → 1 → 0, 9 seats, 66 min). In both, round one was a three-way
partition and found the bulk; from round three each round was ONE fresh seat over ONE rewritten cell, each confirming
one nuance of the previous fix — one of them a mechanism copied from a seat's report because the seat's *number*
had re-executed true. The operator stopped the second run: *"this review approach is too time consuming and you
know we will change it."* Round one was the factory; everything after it was the hunt.

**The same cause in the seat numbers (ledger and this session's transcripts, 2026-09-22).** Parallelism exists only
in round one: across the 203 runs that stamped seats, the median is **1.75 seats per round**, 108 of them average
under 2, and 64 further runs never stamped a seat; the review family runs a median of 4 rounds at 1.67 seats per
round on a box that allows 20 concurrent (`dispatch_headroom.py` caps 20/22); the DATA_SYNC run above reads 3, 2, 1,
1, 1, 1. The mix is inverted toward the expensive model: seats dispatched by this session were **Opus 181, Sonnet 99,
Haiku 28, Fable 3** — Opus 58% where the rule puts it on risky slices only, about 4.6× the cost-weighted spend of the
Sonnet seats, the 2.5× overspend the dispatch rule itself names. And the most expensive model does the most reading:
the orchestrator (Fable at 10×, Opus at 5× on 210 of the rows) holds **64% of all input tokens and 39% of all
output**, because after round one it re-reads the artifact and re-executes every claim itself, and it is the one
refuting the 35% of candidates the seats raise wrongly. Executing a seat's claim before writing is right; re-reading
whole files for it is the 10× model doing 1× work. Under § 5 the same runs keep N seats busy in every pass, re-verify
each slice's ledger on Sonnet or Haiku with Opus only on a risky slice (the mix before D-344 — § 4.9), and the orchestrator — Fable or Opus, whichever
the quota allows (D-334) — adjudicates from the seats' executed outputs and reads nothing twice.

**Do we use the seats wisely — maximum parallelism, least waste, fast and accurate? Not yet, but the direction has
moved, and the numbers say by how much. Measured after § 5's first chunk landed (2026-09-22, the `/fabrik-review` over
that chunk itself — 13 files, 17 confirmed defects, 25 minutes inside a declared 45-minute budget, closed at zero by
the owning seat).** Seats per round 3, 3, 1, 1: the full partition in
round one, then only the slice that still failed — the two clean slices were never re-dispatched. Model mix as the
rule says, for the first time: Opus on the one risky slice (four passes), Sonnet on the other two (two passes each), no
Fable seat — 28 cost units of seat time. The Opus share of that cost stayed high because the risky slice was the one
that kept failing on the orchestrator's own residue; the fix for that is the probe below, not a cheaper seat. The orchestrator's
share fell from 64% to 50% of input tokens and from 39% to 32% of output. Against the command's 94-minute median, 25
minutes. The second measured run (chunk 2's own review, same day): seats 3, 3, 3, 2 — the partition held every pass, 34
cost units, 21 confirmed, 62 minutes against a declared 45 — over, and the run says so on its RUN: line; passes two to
four were again residue of the orchestrator's own fixes (wording, a citation, a stale tag), which the round-zero probe
did not catch because it was run once, before round one, not before each re-dispatch. The third measured run (chunk
3's review): seats 3, 3, 1, 25 cost units, 15 confirmed, 45 minutes against a declared 30 — the probe ran before every
re-dispatch this time and passes two to three carried one residual instead of six; the probe also found the run's
only fleet defect before any seat did. Two wastes remain, and both are named: rounds two to four were the orchestrator's OWN fix residue on one slice
(three passes, about 12 minutes) because the fixer skipped the round-zero probe on its own hunks before the owning seat
re-read them; and the orchestrator still re-executed every candidate by reading the files instead of adjudicating from
seat reports that carry the executed output — which is what the per-slice ledger of the second chunk changes.

**What the cause is not.** Not the size of the contract — D-331 cut a quarter of it without loss and the two runs
above still degenerated. Not the number of commands. Not a round cap (D-321: it legislates the wrong variable), not
an acceptance list (D-323: an addition to a system whose problem is not additions), not fewer seats, not the operator
as the review's terminal (D-330). Each of those changes the process around the loop; none changes what happens
inside it after round one.

### 4.8 The objective function has one term — the cobra the operator named

*Asked by the operator 2026-09-22: "current loops are extremely long and i think it is cobra effect, we are optimizing
against a wrong goal?" Yes, and it can be read off the rule text and the ledger (all executed 2026-09-22).*

**What the loop is told to maximise.** The two fragments every review-family command includes say, verbatim:
*"Accuracy outranks pass-count"* and *"Minimum two full rounds, ALWAYS"* (`commands/_fragments/term-coverage.md:32`),
*"There is NO round ceiling … 5, 15, 30 rounds; the loop runs until the exit conditions hold"* (`:34`), and *"the
round in which you edited the artifact is NEVER the last round"* (`term-edit.md:3`). The words *time*, *minutes*,
*budget*, *wall-clock* and *deadline* do not occur in either fragment (0 hits over 49,954 B). The finder brief is
*"RECALL first"* and *"surface every candidate"*. Of the 27 run records on disk, **1 names time or cost in its
terminal condition; 26 name only correctness**. The objective, as written and as recorded, is *no confirmed defect
standing* — with no cost term at all.

**What that objective buys, measured.** An objective with one term is satisfied most cheaply by spending the other:
the loop runs until a reader is tired (§ 4.1), a seat rewarded for raising raises more the longer it runs (§ 4.2,
69% → 44% confirmed), and every close asks for MORE accuracy — of the 338 close verdicts, the `change:` axis reads
**`accurate` 124 times and `fast` 4 times**. The agents optimise exactly what they are measured on, and they are
measured on accuracy alone; *lean, fast, complete* live in the contract's first line (`CLAUDE.md:3`) and nowhere in
any terminal condition. That is the cobra (D-253): the metric — a quiet round — is satisfied by more rounds, and the
counter-measure — a cost the run must stay inside — was never written down beside it.

**The second half of the goal is enforced almost nowhere.** Of the 38 command sources, 9 name `select_rules.py`
(the rule packs), 6 name `agents-fabrik.md` (the infrastructure map — the exact name; a substring count reads 7 because
`fabrik-deploy-verify` names `agents-fabrik-core.md`), **0 name `mcp_health.py`** (the assigned MCPs)
and **0 name the operating manifesto**. "Each command enforces our MCPs, rules, infra and manifesto" is a goal the
corpus states in `CLAUDE.md` and leaves to the agent's memory in 29 of 38 commands.

**What follows for § 5.** The terminal keeps its correctness term — every slice verified — and gains the cost term the
goal always had: a run declares its budget at `start` from the size of its surface (the same arithmetic that sizes
its seats), reports against it at every round, and a run that would overrun hands off with its failing slices named
instead of running on. That is not a round cap (D-321): rounds are free while the budget holds; the budget is the
goal restated as a number the run can see. And every command's opening act names its MCPs, its packs, its infra map
and the manifesto section it runs under — executed, not recalled — so the second half of the goal is a step, not a
hope.

### 4.9 The seats — where the tokens go, and the two pilots that follow (2026-09-22)

**Our own ledger first** (210 review-family runs with token data, `~/.claude/state/command-feedback.jsonl`, medians): the
seats are **35%** of a run's token cost and the orchestrator **65%** — and 76% of the orchestrator's cost is re-reading
its own growing prefix, 62 messages a run. Per seat-pass ≈ 0.52 M cost units, per orchestrator round ≈ 1.2 M. A seat's
cost is 46% cache reads and 18% output. In the chunk-3 review the seats' round took 6 of the run record's 31 minutes (45 elapsed from the first read); the other 25 were the orchestrator's serial chain. So the seats are not the waste; the serial chain is, in tokens and in wall clock.

**What the outside evidence says.** Every subagent starts fresh and loads every `CLAUDE.md` level — our hub contract is
100 KB, so each seat carried ~25 k tokens of contract it does not use (at ≈4 bytes per token); `omitClaudeMd: true` exists for exactly this
(Claude Code docs, sub-agents). Token usage explains 80% of multi-agent performance variance; 3–5 parallel workers cut
time by up to 90% on complex work; duplicated effort comes from vague boundaries (Anthropic, multi-agent research
system). Fan-outs on SMALL tasks cost 2.6–5.9× the tokens and were never faster; pinning workers to a cheaper model cut
tokens 37% (Systima, 2026-07). A single LLM code review recalls ~30% of real defects; ten aggregated reviews raised recall
119%; five runs of one model overlapped on 27 defects — redundancy, not size, buys recall (SWR-Bench, arXiv 2509.01494).
Haiku 4.5 out-reviewed Sonnet 4.6 (F1 0.365 vs 0.343, +18% recall) at 3.2× lower cost (arXiv 2606.15689). Teams that
vote by consensus lose up to 37.6% to their best member; a union that is then EXECUTED does not — D-335's shape.

**The two answers.** How we use them: partitioned by file, Opus on the risky slice, Sonnet on the rest, the same seats
every pass, every claim executed by the orchestrator. Wisely: parallelism yes; waste no, three times over — each seat
loaded a contract it did not need, Opus was spent on finding where a cheaper model finds as well or better and its value
is execution, and the orchestrator's own chain was most of the cost and nearly all of the clock.

**The pilots (D-344, operator "1 approved, 2 ok").** (1) Seats stop loading `CLAUDE.md` — measure: seat cache-read
tokens per seat-pass, baseline 1.73 M. (2) Finders are cheap and redundant, execution is expensive: each slice gets one
Sonnet and one Haiku finder over the whole slice, candidates unioned, never voted, no Opus finder; Opus/Fable execute —
same cost as the old mix (chunk 3: 9 units either way), twice the readers; measure: confirmed per seat and model on the
receipt's Pass-1 row over five runs; KILL: a pair below D-207's baseline (7 of 13, 6 of 14 — the Opus seat's share of round one's confirmed in the chunk-2 and chunk-3 runs, taken from the seat reports; the receipts carried no per-seat count until this run, which records it in the Pass-1 row's Method cell as `seats: <name> <confirmed>/<raised> · …`) on the same kind of slice. **Pilot 1, executed twice at Claude Code 2.1.276 (the field needs ≥ 2.1.271):** a Haiku probe seat spawned after the reload window still listed the hub contract's headings in its context and `omitClaudeMd` nowhere — no effect observed; the key stays, the measure is null until the CLI honours it, and the brief now carries the house rules a finder used to get from the contract.
(3) The orchestrator's chain — not yet decided; the measure exists today (`tok_msgs` in the ledger, median 62; 16, 68 and
28 in this session's three reviews), the candidates are a fixed four-call closing chain in the command text and the
receipt tool filling the ledger from a values file instead of a scratch script written per run.

**The pilot's first run (this change's own review, 2026-09-22):** six seats, one Sonnet and one Haiku per slice, 9 cost
units — the same as the D-207 mix would have cost. Per seat, confirmed / raised · tokens: A-sonnet 3/4 · 156 k, A-haiku
0/1 · 108 k, B-sonnet 5/5 · 158 k, B-haiku 3/3 · 75 k, C-sonnet 4/5 · 132 k, C-haiku 1/1 · 98 k. The Sonnet seat
out-found its Haiku twin on every slice; the Haiku twin added two candidates the Sonnet missed (the brief's missing house
rules, the baseline's missing provenance); three candidates were raised by two seats, so 19 raised are 16 distinct: 14
confirmed, 2 refuted. Against the D-207 baseline (7 of
13, 6 of 14 from the Opus seat on the risky slice) the risky slice's pair confirmed 3 of 14 — below it — but the risky
slice here (a generator, a headroom script, two contracts) held fewer defects than the 14-file corpus slice; one run is
one point, the KILL reads five. Pilot 1: no effect (above).


**The research behind the next chunks (2026-09-22; six `fabrik-researcher` seats on Sonnet, one sub-question each, 60
quoted facts; fabrik-lib's `deep-research` engine is a market pipeline needing an injected pack and paid legs — the
corpus's own wiring for an engineering question is this fan-out).** Seven findings, each with its source:
1. *The cost is the lead's transcript, by design of the tool* — "Claude Code sends your full conversation with every
   request … a one-line question in a session that has been open all day still draws usage for the whole conversation"
   (code.claude.com/docs/en/costs); the documented fix is structural: verbose work in subagents that return summaries
   (their example: 6,100 tokens read, 420 returned — docs/en/context-window), fewer turns, hooks that grep instead of read.
2. *The platform ships the primitive the loop hand-simulates* — a dynamic workflow runs subagents in the background from
   a script; "intermediate results stay in script variables instead of landing in Claude's context"; seats return
   schema-validated JSON; "adversarially verify each finding" is a documented pattern; a re-run resumes with unchanged
   seats cached; 16 concurrent, 1,000 per run (docs/en/workflows, docs/en/best-practices). The run costs more seat
   tokens; the lead's context stays flat.
3. *Resuming a seat is the cheap closing pass* — a resumed subagent "can keep reading the prompt cache the original run
   warmed" (docs/en/sub-agents) — D-335's same-seats rule is the right mechanism.
4. *Fan-outs carry a floor cost and a race* — measured 2.6–5.9× the tokens and never faster on small tasks; cold parallel
   spawns race the cache (a 52 k prefix re-written at full price); pinning seats to Haiku cut tokens 37% and time by half
   (systima.ai/blog/subagent-tax, 2026-07, hash-chained audit trail); a seat's cold start is ~54 k tokens, so delegating
   pays above ~30–50 k tokens of reading for a same-model seat, ~10 k for a cheaper one (dev.to/rulestack, 2026-08).
5. *Cheap finders, strong executor holds* — Haiku 4.5 out-reviewed Sonnet 4.6 at 3.2× lower cost (arXiv 2606.15689);
   aggregating independent reviews lifts F1 up to 43.67% (SWR-Bench, arXiv 2509.01494); the "teams hold experts back"
   loss (41.1%) is a consensus-averaging failure and does not apply to union-then-execute (arXiv 2602.01011); weak
   judges lose signal, so the strong model adjudicates; Anthropic's own system is an Opus lead with Sonnet workers,
   scaling effort to complexity — "1 agent with 3–10 tool calls" for a simple task (anthropic.com/engineering/multi-agent-research-system).
   *Qualified 2026-09-23 (finding 28): the Haiku-over-Sonnet result compared against Sonnet 4.6, and its ensemble table is
   internally impossible; it does not carry to Sonnet 5.*
6. *Later passes must be narrower than round one* — "a reviewer prompted to find gaps will usually report some, even when
   the work is sound"; "include stopping conditions" (docs/en/best-practices; Building effective agents). Passes 2–4
   of this session's reviews finding only wording residue is that effect.
7. *Pilot 1 is an anomaly, not a misread* — `omitClaudeMd` is documented (≥ 2.1.271), definitions reload within seconds,
   none of the three documented restart cases apply, and the seat still loads the contract. Until explained, every seat
   pays the hub `CLAUDE.md`, which makes D-331's lean program a direct seat-cost lever.

**The final research (2026-09-22; three more `fabrik-researcher` seats, 34 quoted facts, ~600 k seat tokens):**
8. *A turn cap on the current shape fails; a shape change does not* — capping SWE-agents at the 25th percentile of
   their natural turn distribution cost 20–59% of solved tasks, at the 75th −5 to +3%; "the dynamic-turn strategy
   is unequivocally superior to a fixed-budget approach … start with a lower turn limit and grant an extension only
   to tasks that truly need it … reducing costs by an additional 12% to 24%" (arXiv 2510.16786, ICSE '26); a hard
   stop AT the cap kills the synthesis turn — `error_max_turns` carries no result (anthropics/claude-code#41143;
   docs/en/agent-sdk/agent-loop). Our targets are below today's p10 (§ 2.6), so they are a shape, not a cap.
9. *A countdown makes agents panic* — "'you have five minutes left' … makes the agents freak out towards the end,
   and they start doing irrational stuff" (terminal-bench authors, arXiv 2604.28093); "an agent given too few tokens
   might 'panic' and submit a lot of its solutions right at the end" (metr.org, 2026-02-13); frontier agents are
   over-optimistic about remaining budget, and an external early-stop on a slice predicted impossible saves 28–64% of
   the tokens of failed trajectories at 1.6–4.2 points of success (BAGEN, arXiv 2606.00198); 19% of unresolved runs
   are self-declared early exits, "overconfidence" (arXiv 2607.08964). So: the budget is information at the top of
   the run, one closing turn is reserved, one extension is allowed by rule, and an early self-declared close is
   refused until the ledgers are executed true (D-339 already does this).
10. *The recall-losing move under pressure is coverage overclaim* — "agents do not read all the files they were asked
    to review in 67.9% of runs … among runs where not all files are read, agents are misleading 80.4% of the time …
    agents that falsely claimed a complete review missed planted defects at about 1.8 times the rate" (OverclaimBench,
    arXiv 2609.20812, production CLIs, no turn cap). Completeness is measured from what a seat READ, never from its claim.
11. *Seeded canaries are a weak recall guard; the lagging measure is not* — synthetic defects overstate real recall by
    an order of magnitude ("F1 = 0.066 versus 0.847 on synthetic samples"; diff size dominant, 0.657 under 10 lines →
    0.043 over 150 — arXiv 2606.15689); naming a defect class raises its detection 12× (doi 10.1145/3377811.3380385);
    capture-recapture needs ≥ 4 inspectors (ISSRE 1997); "if we pressure an agent to identify more bugs … the noise
    increases" (CR-Bench, arXiv 2603.11078). The measure a reviewer cannot move is the lagging one — Meta's RADAR reads
    revert rate ⅓ and incident rate 1/50 of unreviewed diffs (arXiv 2605.30208); ours is commits touching a reviewed
    surface's files after the review's close, from git (§ 6).
12. *The Workflow tool's documented constraints* (code.claude.com/docs/en/workflows, /agent-sdk/typescript,
    /prompt-caching, /sub-agents, all fetched 2026-09-22): launch returns `async_launched` and one consolidated result,
    so launch + receipt is two lead turns; the script has no filesystem or shell, the agents "read, write, and run
    commands" under the session's permission rules (pre-allow the gate and pytest or a prompt pauses the run); `schema`
    retries five times then fails; a `null` is a stopped or failed agent; "Runs count toward your plan's usage"; each
    agent starts cache-cold on a 5-minute TTL and shares a prefix only with a sibling of identical model, effort, agent
    type, tools, schema and cwd; **resume is position-keyed — a resumed run re-runs every agent after the first
    fan-out** (anthropics/claude-code#95076, open at 2.1.274: "40 redundant opus agents, 231M tokens"), so each pass
    is its OWN invocation carrying the previous pass's ledger as `args`; a `context: fork` skill cannot launch one (the
    subagent filter removes `Workflow`), a plain wrapper can; saved named workflows live in `.claude/workflows/`, a new
    synced path if shipped fleet-wide; 16 concurrent by default, 1,000 agents per run, v2.1.154+.
13. *`omitClaudeMd` stays unexplained* — documented at 2.1.271, no upstream issue found in two engines, no effect at
    2.1.276 (pilot 1); every brief is sized as if the contract loads.

**The module run (2026-09-22; fabrik-lib's `deep-research`, vendored at `libs/deep_research` and wired exactly as
`scripts/rivals_run.py` wires it — keys by its loader, `claude -p` sonnet as the LLM in a neutral cwd, the exa /
firecrawl / brave legs from `libs/web_tools.py`, a $1.50 ceiling per brief, checkpoints under `.tmp/`; an ENGINEERING
pack whose cards carry a verbatim quote, the numbers, the page date, the source kind and a cobra note per source; six
briefs, 60 cards, 57 verified, ≈ $0.20 of search spend plus 18 `claude -p` calls; one brief re-run alone at a 900 s
timeout after three 300 s kills under four-way concurrency).** Revision 18's verdict that the module is "a market
engine, not for engineering questions" is WITHDRAWN: with a pack it is the corpus's research engine for this kind of
question, at a fortieth of a seat fan-out's token cost. Eleven more findings:
14. *"Done" must be a certificate, never a claim* — an agent may return complete "only when a typed certificate binds
    every required answer claim to valid, in-scope trace evidence and a deterministic replay reconstructs the claimed
    value": 0 of 288 unsafe completions against 252 of 288 for a critic-based stop (arXiv 2608.23623); coding agents
    assert false success in up to 75.8% of trajectories and LLM judges catch it at AUROC 0.54–0.65 (arXiv 2606.09863);
    97 of 154 DeployBench failures were self-stops where "the agent's pre-finish check validated a weaker or different
    target than the task required" (tsukumo.ch, 2026-07-14). D-339's executed per-slice ledger is that certificate; the
    terminal comes from the command text, never from the agent's own `--terminal` prose.
15. *The reward-hacking menu is short and known* — "skipping verification steps, inferring answers from task-adjacent
    metadata, or tampering with evaluation-relevant functions"; exploit rates 0% (Claude Sonnet 4.5) to 13.9% (arXiv
    2605.02964). § 6.1 covers the first two; the third is closed because the ledger tools are fleet-synced scripts and
    every seat is read-only git.
16. *A visible remaining budget makes the model wrap up early* — "the model taking shortcuts or leaving tasks
    incomplete when it believed it was near the end of its window, even when it had plenty of room left"
    (monperrus.net). The `BUDGET` line prints per round (`command_run.py:763`), never per response and never in a seat
    brief; keep it so.
17. *Turn cost is superlinear and uniform budgets waste it* — a simple loop costs ≈ 3× a single inference at five
    steps, > 30× at fifty, > 100× past two hundred (tianpan.co, 2026-05-22); uneven per-turn budgets save up to 35% of
    tokens at equal accuracy (arXiv 2604.05164); a hard cutoff below the trajectory's need yields "catastrophic
    truncation", no usable output (arXiv 2607.14547) — the reserved closing turn of D-347.
18. *Two finders per slice give a remaining-defect estimate for free* — capture-recapture with two inspectors, iterated
    per round, is a published stop signal (Harel & Kantorowitz; El-Emam & Laitenberger 1999); estimates land within
    5–20% of the true count with enough independent finders (Walia, Carver & Nagappan 2008, 73 inspectors) and are
    unreliable below four (ISSRE 1997) — so ADVISORY per slice, never a gate. From the D-344 pilot's own numbers (Sonnet
    14 raised, Haiku 5, 3 shared) the Chapman estimate is ≈ 21 against 16 seen: about five unseen candidates. Its cobra:
    finders that are not independent inflate the overlap and understate what is left; ours are two models in two
    contexts, and the number is advice.
19. *Production reviewers converge in 3–8 rounds and buy recall with noise, absorbed downstream* — Kodus: recall 53% →
    62% while false positives went 170 → 328 (2026-08-18); Cursor Bugbot: 40 experiments, resolution rate 52% → 76%,
    bugs flagged per run 0.4 → 0.7; cubic: micro-agents plus reasoning logs cut false positives 51% at no recall loss;
    a confidence rubric with a 0.60 suppress threshold and a cross-reviewer agreement boost cut noise ≈ 49% with no
    sensitivity loss (EveryInc #434); "a fresh-context verifier then tries to build a concrete reproduction against the
    diff before the finding ships" (agentpatterns.ai); "typically 3-8 rounds" (zylos.ai, 2026-03-01). Our shape absorbs
    the noise in the executor, not in the operator's inbox; a candidate both finders raise is executed first, never voted.
20. *The lagging measure is standard in the field* — post-merge revert rate over 37,623 PRs: Codex 6.1% vs human 11.5%
    (arXiv 2609.17598, 2026-09); review coverage and participation predict post-release defects (McIntosh et al. 2016);
    "code reviews often do not find functionality issues that should block a code submission" (Czerwonka et al.,
    Microsoft 2015). § 6's escaped-defect row is that measure.
21. *Guards stay separate; never a composite, never a token target* — "a weighted combination of X and Y, like 0.7X +
    0.3Y, but that too is a metric subject to Goodhart" (Hillel Wayne); guardrail metrics beside one goal metric
    (PostHog, 2023-10-16; InfoQ on DORA anti-patterns, 2023-04-28); tokens are gamed both ways ("tokenmaxxing",
    lawsofsoftwareengineering.com), so tokens per run is a guard, never a target.
22. *The Workflow tool's live defects, from the tracker* — resume keys each `agent()` call on its prompt bytes and
    chains through prior results, so one changed character re-runs everything downstream (#63102, 2.1.153); 26
    completed fetch agents re-ran on resume at ≈ 19 k tokens each (#67488); completed calls re-execute (#74599, #95076);
    subagents never write the one-hour cache tier — 0% across hundreds of sessions (#54006) — and pay a write premium
    (≈ 14% of subagent spend, #74318); resuming the lead invalidates its own cache prefix (#43657); the TTL doc and the
    transcripts disagree (#84289). Design consequences: one invocation per pass, identical agent definitions so siblings
    share a prefix, the seat count bounded by the partition, no resume.
23. *Fixed iteration caps are unexamined, and the bound is a design input* — "most prior work adopts fixed, often
    arbitrary, repair budgets" (arXiv 2607.05197, 2026-07) is the published form of D-321's refusal; "The bound is not an
    optimization you add after it misbehaves; it is a design requirement of shipping the loop at all" (aiarch.dev,
    2026-08-10); one vendor-narrated case (unverified numbers) paired iteration caps with "stagnation fingerprints" and
    a token governor — the shape of D-339's oscillation advisory plus the per-slice handoff; human reviews "start to
    feel slow after they have been waiting for around 24 hour" (ESEC/FSE 2022) — the chain's 10 h median sits just
    inside that line, which is why aim 1 reads "never a day of waiting".
24. *The pack is reusable* — `loop-research-pack.yaml` (query-plan / shortlist / verify prompts, the nine-field card,
    three legs, `demote_rule: [verified, quote]`) ran six unrelated engineering briefs with no engine edit; it belongs
    under `libs/deep_research/packs/` beside `free-llm-providers.yaml`, on the operator's word (a hub code surface).

**The Opus 5.5 week (2026-09-23; asked by the operator when Opus 5.5 was released: "make a new research … meticulously").
Five `fabrik-researcher` seats, one sub-question each, 64 quoted facts from primary sources — the Opus 5.5 announcement,
model pages and prompting guide (dated 2026-09-22), the Claude Code release pages 2.1.270–2.1.280 read one by one,
code.claude.com's sub-agents / workflows / agent-teams / costs / best-practices pages, and GitHub issues from
2026-08/09 — plus one executed probe; the deep-research run over three briefs was still extracting at this revision.**
25. *Opus 5.5 is the cheaper orchestrator* — "Input and output tokens are $4 and $20 per million, 20% less than Opus 5.
    Cache reads … are $0.20 per million tokens, 60% less"; at default `medium` effort it "matched or beat Claude Opus 5
    at `high` effort … in fewer steps and with fewer tokens"; the models overview now says "start with Claude Opus 5.5
    for most workloads. Use Claude Fable 5.1 for demanding reasoning and long-horizon agentic work" (anthropic.com/
    claude-opus-5-5; platform.claude.com/docs/en/models/overview; prompting-claude-opus-5-5). Cache reads are most of the
    lead's cost (§ 4.9: 76% of it is prefix re-reads). Three constraints ride with it: changing top-level `effort` between
    requests invalidates the prompt cache (use the per-message beta); a forced `tool_choice` returns a 400 on Opus 5.5;
    a conversation moved off Opus 5.5 to any model but Fable or Mythos loses its thinking blocks.
26. *Anthropic's stop rule is the operator's* — "stop after two or three automatic continuations on the same task";
    "Treat a text-only end of turn as a report rather than as proof the task is done"; the workflows page: "stop once two
    rounds in a row find nothing new" (prompting-claude-opus-5-5; docs/en/workflows). D-330's 1–3 passes is that rule.
27. *Do not spawn a seat for a check the lead can run* — "Do not delegate work you can finish yourself in a handful of
    tool calls, and do not use subagents to verify or double-check your own work"; "use a subagent to verify" instructions
    "cause over-verification … removing them reduces wasted tokens with no loss in quality" (prompting-claude-opus-5, which
    the 5.5 guide keeps as its starting point). But a fresh refuter for FINDINGS is endorsed: "a verification subagent or a
    dynamic workflow … has a fresh model try to refute the result, so the agent doing the work isn't the one grading it"
    (best-practices). Per-finding verify fan-outs are the documented blow-up: 547 planned agents (3 skeptics × ~180
    findings), ~36.6 M tokens, ~$606 before it was stopped (anthropics/claude-code#95816, 2026-09-21); one `/review high`
    of 14 agents, ~66 M tokens, ~20% of a weekly plan (#89249). Chunk 5's verify stage spawned one Sonnet seat per
    candidate, most running one grep — 14 in run 1, 12 in run 2. *Qualified 2026-09-23 (D-358): "the lead runs the
    check" assumes a lead with a short transcript.* Measured in the session that built row 5b: the lead carried 744–774 k
    context tokens per tool call, a refuter seat about 31 k (the two refuters of run `wf_73d4d909-90f`: 555,503 tokens over
    18 calls and 305,682 over 10), so ten checks run by that lead read ~7.4–7.7 M cached tokens against 0.31–0.56 M for
    one refuter seat — 13–25× more. The loop keeps one fresh refuter per slice; the lead re-runs
    only the confirmed commands (Phase 2).
28. *The finder pair is open again* — Sonnet 5 as a reviewer: "Sonnet 5 lands around 50 to 51% … Sonnet 4.6 caught more
    than either of them, around 63%", precision "from about 29% … to roughly 38% to 40%" (coderabbit.ai, 2026-09); the
    only Haiku-vs-Sonnet-5 comparison puts Haiku 4.5 clearly below (review scores 5.5 vs 8.0 and 6.5 vs 8.8; "it burn[s] a
    huge token budget on simple tasks" — marcindudek.dev, 2026-07-17, small n); finding 5's arXiv 2606.15689 compared
    Haiku with Sonnet 4.6, and its Table 9 prints a union recalling fewer bugs than one of its members, which cannot be.
    Diversity still pays: "56.5% of confirmed defects (87 of 154) were found by exactly one model … the largest marginal
    gain from adding a second, different-provider model (33.6% to 57.1%)" (zenodo 20519585) — cross-provider evidence, so
    a Sonnet + Haiku pair is its weaker form. Opus 5.5 as a reviewer: recall 63.8% vs a 61.3% baseline, and "caught 11 …
    issues that the baseline missed, but missed nine that the baseline caught" (coderabbit.ai, 2026-09-22); a customer
    reports it "caught 72% of known bugs … to Opus 5's 56% at high effort" at its lowest effort (testimonial). No source
    compares one strong finder with two cheap ones at equal cost. Sonnet 5.5 and Haiku 5.5 are announced for "the coming
    weeks".
29. *Fresh seats per pass is the right mechanism; waking parked ones is not* — waking a parked subagent with SendMessage
    re-cached "54 full-context rewrites, 5.2M tokens … at write rates … roughly a quarter of total weighted token cost"
    (#87215, 2026-08-16); Workflow resume still replays by position in 2.1.280 (#95076 open; #63102 and #67488 closed as
    stale, not fixed; the docs: "the first agent whose prompt differs … runs again, and so does every agent after it").
    This resolves finding 3's tension with chunk 5: continuity rides the ledger, not the seat's context.
30. *The lead's transcript is still the cost — keep it short* — "A clean session with a better prompt almost always
    outperforms a long session with accumulated corrections"; "Keep a checklist in TASKS.md … read the file, not the
    scrollback" (best-practices; claude.dev, 2026-09-22); "The fix round costs more than the implementation … 46M
    cache-read tokens against 257k of output, so the spend is context reconstruction, not reasoning" (#93202). Chunk 5's
    two runs: the lead 10.2 M and 9.6 M tokens against 2.6 M and 0.56 M for all seats.
31. *Seat arrival cost, and the pilot-1 reversal* — a lean agent type arrived at "15,746 tokens" against "38,401" for
    general-purpose (practicalsystems.io, 2026-09-14). **Pilot 1 now takes effect:** at Claude Code 2.1.280 a Haiku
    `fabrik-reviewer` probe reported neither the hub contract nor the core map in its context (executed 2026-09-23); at
    2.1.276 the same probe saw both, twice. No release line in 2.1.272–2.1.280 names a fix; the probe is the evidence.
32. *Sibling seats share a cache only when identical* — "same model, effort level, agent type, tools, output schema, and
    working directory … reads that sibling's cache on its first request"; subagents get "five minutes even on a
    subscription until you choose a longer one" (`subagentPromptCacheTtl`, docs/en/prompt-caching; #84289 open). A Sonnet
    and a Haiku finder never share; the verify seats (one model, one schema) can, inside five minutes.
33. *The platform itself moved away from many review subagents* — 2.1.274: "Changed `/code-review` to use leaner inline
    review prompts for every model that has no tuned settings of its own, instead of spawning many review subagents";
    2.1.271: workflows "pause when you hit your usage limit and continue automatically", the medium size guideline "from 15
    to 10 agents"; the workflows page warns past "25 agents, or … 1.5 million" projected tokens (run 1 used 30 agents);
    2.1.280 "Fixed a finished subagent's report being lost when the conversation that launched it was compacted". Per-agent
    tokens are exposed only through OpenTelemetry (`OTEL_LOG_TOOL_DETAILS=1`, 2.1.273), which is why the run record's seat
    counters read 0 for workflow agents. *Corrected 2026-09-23 (D-358): not only.* Every workflow seat's own transcript
    (`agent-<id>.jsonl` beside the run's journal) records each assistant message's `usage`, and
    `scripts/review_loop_ledger.py` totals it per seat, counted once per message id; OpenTelemetry's token metric labels a
    user-defined agent `custom` (code.claude.com/docs/en/monitoring-usage), so it cannot name a seat at all — only the
    beta trace spans carry `agent_id` and `workflow.run_id`. No collector is adopted.
34. *A time budget is now Anthropic's own pattern — and this document's finding 9 warned against a countdown* — "Have your
    harness add a short line at the end of each message … `elapsed 340s / 1200s`"; "lowering effort reduces the work
    itself, whereas a budget mostly keeps more agents working in parallel" (prompting-claude-opus-5-5). Finding 9's evidence
    (panic-submit, METR; terminal-bench authors) predates Opus 5.5; the two disagree, so it is tried on one run before it is
    trusted. Machinery for the next research run: four seats lost oversized exa results written under a `$HOME/.claude*`
    path the brief forbids them to read (fetch one URL per call, or cap `maxCharacters`), and the research agent's own
    definition still says firecrawl "is not connected" while the contract names it tier 2 — both unverified, one edit.
35. *Count the chain before judging its findings — a review loop has no damping term* (shimo4228, dev.to, 2026-08-27, read
    whole on the operator's hand-over 2026-09-23). A solo Claude Code setup grew to six standing review stages in ten
    days; "one stage does not mean one agent" — about ten agents reviewed each change. The loop "never ended not because
    of the content or accuracy of the findings, but because of its structure": review → fix → re-review "has no term
    that shrinks the amplitude over time" and "every cycle supplies new findings", so "stop when findings hit zero" was
    never reached. Recounted, six stages had produced ONE proven discovery (a reachable command-injection flaw in hooks,
    proven with a PoC); of six out-of-diff HIGH findings, filing on the spot changed the outcome for one — "a defect that
    breaks the review loop itself". The cut: six standing stages → one fresh-context `/code-review` plus one conditional
    security stage that fires only on a trust-boundary diff; effort pinned `high` → explicit `medium` ("levels up to
    medium restrict reports to high-confidence findings; high and above cast a wider net" — "the flip side of the
    over-engineering supply"); re-review after a fix kept, each fix "the minimal diff that answers the finding"; the
    decision ships with its rollback conditions, and "the only thing that reduces the total amount of machinery is
    deletion". The author labels the token saving "a projection with no after-the-fact measurement". **What it adds here:**
    (a) this loop's damping terms already exist — D-206 (refuted and recorded never reopen) and D-230 (a later pass counts
    only defects inside the previous fix hunks); chunk 5's run 2 is the case: its one pass-2 defect lay inside its own fix;
    (b) a lever this document has not measured: **how many review stages fire per change across the chain** —
    `/fabrik-spec-review`, `/fabrik-plan-review`, a `/fabrik-review` + `/fabrik-docs-review` per execute-plan phase, the
    whole-plan review, `/fabrik-review-scoped` after plain-chat edits — and the proven-defect yield of each; that count,
    not any one loop's rounds, is where `/fabrik-execute-plan`'s 245 hours may sit; (c) our finder brief says "RECALL
    first … surface every candidate", the widest net; Anthropic's own prescription (finding 27; best-practices) is to flag
    only gaps that affect correctness or the stated requirements. Here every candidate is EXECUTED, so the wide net costs
    verify tokens rather than over-engineering — which makes it a cost question for § 6's stage-yield row, not a quality
    rule to change blind.

**The read-whole pass (2026-09-23; on the operator's "why do we make research if you will not read them?").** Every fact
and card the research of 2026-09-22/23 returned — 162 rows from eight seats and the module run — is filed in
`docs/reference/research/2026-09-23-loop-program-research-ledger.md`; the 111 rows no finding cited sent their 71 URLs (69
pages) to eight `fabrik-researcher` readers, which read each one whole (or as far as the tools reach, and said how
far) against findings 1–35. Verdicts: 45 sources carried something new, 22 restated a finding, 2 were mostly a restatement with one new point
each, 1 was irrelevant, 1 could not be fetched (71). What the new ones change, in seven findings, and six corrections to the earlier ones:
36. *A verifier that did not run is not a verifier that refuted — and refutation needs counter-evidence* — in one
    find→verify workflow "All 111 findings are recorded as refuted. Nothing was actually refuted — every refuter died on
    the session limit", and the run reported `completed` (anthropics/claude-code#94530); the workflows page, "as of
    v2.1.196, when the verifier agents can't check a claim … lists that claim as unverified instead of counting it as
    refuted"; a reproduce-or-drop gate "silently" drops races and intermittent faults — "the highest-stakes findings" —
    unless they go to a "suspected-but-not-reproduced" channel (agentpatterns.ai); a verifier that treated uncertainty as
    evidence against a finding halved delivered recall, and requiring "a concrete reason to refute" roughly doubled it,
    while majority voting among verifiers kept 52 of 83 true positives (kodus.io). Practitioners report independent
    verifiers refuting 30–50% of finder output when the verifier sees only the claim, never the finder's reasoning
    (jeremyknox.ai, self-reported); our D-344 pilot refuted 2 of 16 (12.5%). **For the loop:** a verdict is
    `confirmed | refuted | recorded | unverified`, `unverified` (a null or failed seat, a claim not reproducible on demand)
    is never counted as refuted and never closes a pass (D-206's "refuted never reopens" applies to executed disproofs
    only), and a refutation cites the command or `path:line` that disproves the claim.
37. *Redundancy buys less than independence would, so every remaining-defect estimate here is a floor* — three- and
    five-version LLM ensembles realise "only 0.43 and 0.44 of the reliability gain achievable under independence,
    dropping below 0.3 when ensembles are built from the same model" (arXiv 2607.02808, code generation, by analogy);
    capture-recapture below four inspectors underestimates (ISSRE 1997; Petersson et al. 2004: two-reviewer Mh-JK and
    Mt-Ch "non-robust … produces underestimates"; Wohlin et al. 1995: easy faults dominate the overlap, and zero overlap
    gives an infinite estimate); sample-coverage estimators beat Jackknife on inspection data (Walia, Carver & Nagappan,
    ICSE 2008). The Harel–Kantorowitz iterative estimator needs no finder overlap: from the SAME reviewers' per-pass found
    counts it predicts the next pass's yield, and they stopped when it fell below 0.5 fault — the loop's own confirmed
    series is that input. **For the loop:** finding 18's Chapman number is printed as a floor; the pair is judged by what
    each model found ALONE, not by overlap. *Corrected in revision 24 (raw fetch of docs/en/model-config):*
    `CLAUDE_CODE_SUBAGENT_MODEL` is only the default for a seat "that aren't assigned a model another way … A
    per-invocation model or a definition's `model` field, including `inherit`, takes precedence"; only
    `CLAUDE_CODE_SUBAGENT_MODEL_FORCE` collapses every seat onto one model. The real risks are a seat whose `agent()`
    call sets no `model` (it inherits the lead's — finding 43) and `CLAUDE_CODE_EFFORT_LEVEL`, which overrides a
    seat's frontmatter `effort`.
38. *Keep the recall-first finder brief; effort does not buy recall* — "If your review prompt says 'only report
    high-severity issues' or 'be conservative,' the model may follow that instruction literally and report less; ask it
    to report everything and filter in a separate pass instead" (prompting-claude-opus-5; the same in CodeRabbit's Opus 5
    review: "conservative language suppresses recall"); higher effort lowered or did not move review recall for Fable
    5.1 (61.0% low vs 57.1% high, slower), Sonnet 5 ("barely moved its score and roughly doubled the cost") and Opus 5.5,
    whose reviews also used 40–60% more tokens than CodeRabbit's baseline (coderabbit.ai, 2026-06/09); aggregation gains
    flatten past five reviews while cost grows linearly (SWR-Bench, TOSEM, doi 10.1145/3808144); Cursor's largest Bugbot
    gain came from replacing eight majority-voted passes with one agentic reviewer prompted to investigate aggressively
    ("52% to over 70%" — cursor.com/blog/building-bugbot); Haiku 4.5 ran about 6× slower and cost more than Sonnet 5 on
    short reviews (marcindudek.dev). **For the loop:** finding 35(c) is settled — the brief stays recall-first; finders
    run at `medium` effort; the Haiku seat and a single Opus 5.5 agentic finder are the two arms the D-344 pilot's
    remaining runs compare.
39. *What ends a loop well, measured* — at Google, "over 80% of all changes involve at most one iteration of resolving
    comments" with a single reviewer (Sadowski et al., ICSE-SEIP 2018); Bugbot caps its fix loop at "max 3 attempts per
    PR to prevent loops" and feeds prior comments back "to avoid duplicate suggestions" (cursor.com/docs/bugbot);
    interactive actor-critic review converges in 3–5 rounds (zylos.ai — correcting finding 19's "3-8"); failing agent
    runs are the long ones (SWE-agent: success median 12 steps vs 21 for failures, arXiv 2405.15793; RepairAgent 22 vs
    40, arXiv 2506.18824) and repeat identical actions; a fix diff far larger than the finding it answers is itself a stop
    signal (tianpan.co); only about 15% of human review comments indicate a possible defect, a reviewer's useful share
    rises from 33% to 67% by the third look at the same code, and usefulness falls past about 20 changed files
    (Czerwonka et al., Microsoft 2015). **For the loop:** the operator's 1–3 passes sits between Google's human norm and
    the vendors' caps; a slice is bounded near 20 files; the fix hunk's size against its finding is logged; the first stop
    condition that fired is recorded on every run (solana.garden).
40. *Budgets, reconciled — finding 9 overstated METR* — METR's "panic" was a signature they looked for, not an observed
    behaviour: they gave agents their remaining token budget and a four-times-larger budget "barely changed" the result
    (metr.org, 2026-02-13); a budget stated as framing is absorbed into planning while "a hard cap ambushes the model
    mid-sentence", and a countdown works when it names the next action; Claude Code already injects a padded
    `<total_tokens>` countdown into every session (monperrus.net); moderate time pressure raised human review efficiency
    with no measured loss of effectiveness (Mäntylä et al., ICSE 2014); a timebox holds the deadline and cuts SCOPE, "not
    quality" (McConnell, via Wikipedia; Jalote); the Opus 5.5 guide calls its elapsed-time budget "advisory … if you need
    a hard stop, keep your own timeout", and warns the model "may search and verify a little less"; a workflow `budget` is
    a hard throw on the next `agent()` call (a reverse-engineering of 2.1.201). **For the loop:** D-339's minute budget
    stays advisory, printed with the next action it implies, never a hard stop; finding 34's elapsed line is tried on one
    run with its verification counts compared.
41. *Platform mechanics this loop has to use* — workflows hold same-prefix siblings up to 5 s so they read the first
    agent's cache (finding 4's race is mitigated inside Workflow, not for plain Agent fan-outs); an agent definition's
    `experimental.cacheTtl: 1h` raises one seat type's TTL (ignored while usage credits are being spent); a `model:` in a
    command's frontmatter is a model switch that re-reads the whole conversation uncached; `/usage` shows the lead's cache
    hit ratio and the likely cause of the last miss (docs/en/prompt-caching); a workflow's reported `totalTokens`
    excluded cache reads and understated real use 11.6× in #94530; usage-limit pauses happen only interactively and a
    third hit fails the agent (docs/en/workflows); a subagent stopped by `maxTurns` returns PARTIAL output since 2.1.246
    (qualifying finding 8, which describes the SDK loop); nested reviewer → verifier subagents keep the per-finding
    verification out of the lead's transcript (docs/en/sub-agents); 2.1.277 fixed resumed subagents losing their cache
    and removed `TaskOutput`; `omitClaudeMd` has existed inside the CLI since 2.1.84 behind a feature flag (#40459) — a
    likelier cause of pilot 1's null at 2.1.276 than a defect; a Stop hook is overridden after 8 consecutive blocks and
    `/goal` re-checks a condition with a separate evaluator after every turn (best-practices); delegation pays above
    roughly ten tool calls or eighty lines of edits, a seat's floor is about 25 k tokens of tool schemas and system prompt
    nobody can cut, and cutting installed plugins and MCP servers paid about three times what trimming rules and memory did
    (practicalsystems.io) — a measured lever for D-331; one small build task ran about 35% faster as a workflow at 1.3–2.2×
    the cost (thenewstack.io, n = 1).
42. *Measures and their gaming, from the field* — DORA's "deployment rework rate" (unplanned deploys to fix production
    incidents) is the standard name and shape of § 6's escaped-defect row, and a rate can be improved by spreading the same
    errors across more units, so the absolute count rides beside it (dora.dev; InfoQ); every added guard metric raises the
    false-alarm rate (3 guards at α 0.05 → ~14%, 10 → 40% — PostHog), so guards stay few; honest optimisation also drifts
    from the goal and paired guards can deadlock (Hillel Wayne); a count metric is gamed by splitting items, relaxing what
    counts as done and re-counting old items as new (age-of-product) — the three shapes of "confirmed per seat";
    reference-free review-quality scoring agrees with humans at ρ 0.54 (CRScore, NAACL 2025); coverage and mutation
    proxies for LLM-written tests fail exactly on code that already has the bug (arXiv 2607.22880); in production 36.4% of
    an agentic reviewer's comments were accepted and 56.3% rejected, correctness findings most often invalid (arXiv
    2607.03316, 31,073 comments) — the noise the executor absorbs.

43. *The Opus 5.5 system card on teams, and the defaults that quietly undo a cheap pair* (fabrik-lib `deep-research`, 2026-09-23;
    its ten cards read whole, the 230-page system card's § 6.5.3 and § 8.12 by raw fetch and `pdftotext` after both
    in-session arms stopped at its first 7%). **Small tasks lose to coordination:** on DRACO (13–71-minute tasks)
    "multi-agent teams can take longer than their single-agent counterparts to finish a task due to their coordination
    overhead"; on ProgramBench a five-agent team reached the same score 2.7× faster at a higher token cost. **A latency
    budget is where teams win:** they "dominate the score–latency Pareto frontier at increasingly tight time budgets" —
    at 0.5× the single-agent time a five-agent team more than matched it, about 2.8× faster; "reducing effort and
    tightening a latency budget … have a fundamentally different effect … The former results in less work overall,
    whereas the latter preserves more of the work at a given latency by sustaining higher effective parallelism" (this
    settles finding 40's trial toward the budget); under tight budgets async subagents collapse — "the lead spawns them
    at a much lower rate and prefers to act as a single agent" — while a pre-spawned fixed team keeps its parallelism.
    **Team size has diminishing returns**, and a 100-agent knowledge-base team organised itself flat: "the lead divided
    the records among the helpers at the start of the task, each helper then owned its part … and helpers communicated
    relatively little" — the slice partition, arrived at by the model. **Self-preference when grading** is small but
    significant: 0.07 of 10 when reminded the transcript is Claude's (§ 6.5.3) — the case for a verifier from a
    different model family is weak but not zero. **Defaults that undo the pair:** an `agent()` call without `model`
    inherits the session's model — "auto-authored fan-outs inherit expensive model by default" (claude-code #63693,
    #67343, #78994; bundled `/code-review` and deep-research included) — so every seat in the loop's script names
    `model` and `effort`; "context anxiety" (premature wrap-up near the context limit) vanished between Sonnet 4.5 and
    Opus 4.5 and harness guards against it "can go stale as models improve" (anthropic.com/engineering/managed-agents),
    so each such guard is re-measured per model. fabrik-lib's engine returned cards for one of its three briefs; the
    other two shipped none because its `claude -p` step ran past 900 s three times at concurrency 2 — the LLM leg is
    `scripts/rivals_run.py`'s `claude -p` wiring (the hub's), too slow for multi-brief runs; routed to intel's rivals beat.

*Corrections from the read-whole pass:* finding 9's METR citation (above, finding 40); finding 19's "52% → 76%" joins
two Cursor posts — the launch post says "52% to over 70%", the autofix post "52% to 76%" — and its "3-8 rounds" is the
page summary, the body says 3–5; finding 28's CodeRabbit Sonnet 5 post is dated 2026-06-30; finding 18's estimate is a
floor (finding 37); finding 33's "medium … from 15 to 10 agents" disagrees with the live workflows page ("fewer than 15")
— unresolved, re-read the 2.1.271 notes before relying on either; finding 8's hard-stop claim holds for the SDK loop, a
Claude Code subagent at `maxTurns` returns partial output. Tool machinery: `mcp__exa__web_fetch_exa` extracts PDFs but has
no offset (a long page's tail is a raw fetch), serves stale copies of some docs pages, and WebFetch saves a PDF as binary
under a path seats may not read — all four recorded in the research agent's fetch-routing section.

---

## 5. The program — make the loop run as designed

**The work is engineering inside the review loop — not the size of the contract, not the number of commands, not
the operator as a gate.** The loop keeps every part the operator built; it is made to hold its shape past round one.

1. **The partition is fixed in round one and held through every pass.** The same slices, the same seat owning each
   slice, in every round of the run. No round dispatches "one fresh seat over the whole artifact"; a delta round is
   the owning seats re-verifying their own slices, not a new reader.
2. **Each seat owns its slice through fix and re-verification.** A seat's finding is executed by the orchestrator —
   outcome AND mechanism, against the named artifact — before a fix is written; the fix returns to the same slice,
   and that slice's seat re-verifies its claim ledger in the next pass. The brief of every pass after the first is
   the slice's ledger, never "find anything".
3. **Every claim is executed before it is written** — the file opened, the count re-derived, the test run — by the
   one writing it. A mechanism copied from a seat's report is a claim, not a verification (the 2026-09-22 runs paid
   three rounds for one such sentence).
4. **The terminal is "every part verified, inside the run's budget" and nothing else.** A run ends when every
   slice's ledger of claims is executed true — not when a reader is quiet, not at a round count. The run record
   carries the slice ledgers, not only per-round totals, so the terminal is readable from the record (§ 4.1's
   unverifiable close goes away). The budget is declared at `start` from the surface's size, printed on the pinned
   `RUN:` line beside the rounds, and a run that would overrun it hands off with its failing slices named (§ 4.8) —
   a refuted or recorded candidate never re-opens a pass (D-206, D-230).
5. **A refuted or recorded candidate never re-opens a pass — and the record enforces it.** D-206 and D-230
   already say it; four mechanics make it true. (a) `command_run.py` refuses a `round` without `--confirmed`, so
   the terminal and the oscillation advisory read the confirmed series only, never findings — today
   `_trend_series` falls back to the findings series, refuted candidates included, whenever one round omitted the
   field. (b) A candidate a seat refuted is closed in that seat's ledger by the executed disproof and the seat is
   never re-dispatched for it. (c) A recorded candidate — out of the slice, one hop away — goes to its named
   destination (a backlog row, a mail, a sibling ticket) and re-opens nothing. (d) If a recorded candidate is fixed
   anyway, its owning slice executes the fix in the same pass; it owes no fresh reader — the 2026-09-22 runs paid
   rounds 5 and 6 for exactly that.
6. **One to three passes, by construction — per slice, never a cap on the run.** Pass one verifies in parallel; pass
   two fixes and the owning seats re-verify; pass three confirms. A slice whose claims still fail after its third pass
   is handed off with those claims NAMED while the other slices keep running; the run is never re-opened as a fresh
   full pass over the whole artifact. That is a handoff of one slice, not a round cap (item 8, D-330): a slice whose
   confirmed count is still falling is not handed off, and the orchestrator runs the round-zero probe on its own fix
   hunks before the owning seat re-reads them, so the residue rounds of 2026-09-22 do not recur.
   Beside each slice's ledger the record prints the two finders' capture-recapture estimate of candidates not yet
   seen (§ 4.9 finding 18) — advice for the orchestrator's re-dispatch brief, never a gate and never a cap.
7. **Every command opens by enforcing the four things the goal names.** Its first phase runs `mcp_health.py` for
   its assigned MCPs, `select_rules.py` for its packs, reads `agents-fabrik.md` for the infrastructure it touches and
   names the manifesto section it runs under — executed lines in the command, not a sentence in `CLAUDE.md`
   (before chunk 3: 0, 9, 6 and 0 of 38 sources did so, § 4.8).
8. **Where it is built.** In the loop itself: the review-family command sources and the fragments they share
   (`term-coverage`, `term-edit`, the dispatch fragments, the `fabrik-reviewer` brief), and `command_run.py`'s round
   record. Not in `CLAUDE.md`, not in a new mechanism beside the loop. Nothing in this program caps rounds, adds an
   acceptance list, sets a byte target, retires a command, drops a seat or puts the operator between review and
   execution (D-321, D-323, D-330). D-335 supersedes D-229's fresh-seat delta sizing and the fresh-non-authoring
   closing-seat clause of D-206/D-212 with the owning-seat shape of items 1–2; D-230's bounded hop stands.

### 5.1 What stood here before

Revision 1: a round cap — refused by the operator (D-321), and the ledger agreed on three counts:
it cuts real work (2,168 of 6,919 confirmed defects, 31%, arrive at round 4 or later); its cheapest
satisfaction is to *find less* — narrow the brief, refute instead of confirm — which reads green
while the artifact worsens; and it acts on the wrong variable, since § 4.1 shows the round count
tracks stamina, not quality. Revisions 2–3: six additive mechanisms (D-322, withdrawn
D-323). Revision 4: five byte cuts (demoted). Revision 5: one sentence — *the one check the operator
can run* — close, but with the wrong runner and the wrong moment: the check is Claude's, during the
work, against reality; the operator approves the shape and sees the result. Each revision was one
layer of the apparatus looking at the layer beneath it. Revisions 4–7: the program of removal — feedback tool back,
person back, contracts to a page, the review family retired, no more layers. Its items 3 and 2 were executed
(§ 8.1) and reverted (D-330): the cuts lost 38 ungraded rules and the program read the author's *thin* apparatus as
*no* apparatus where the operator had built it on purpose. The lean half survives as D-331 (§ 1.0); the loop half is
§ 5 as it now stands.

### 5.3 The path by command shape — all 38 commands (2026-09-22, D-347)

One lever, six shapes. The lever: the lead's serial reading, dispatching and claim-executing moves into a workflow
script that returns one structured ledger, and the close is fixed at four calls. Today's figure is the median lead
turns (`tok_msgs`) of that command's closes; a command with no close has no figure and gets no target until two runs
exist (16 of 38 have never run).

**The operator's criterion is PASSES — "finish in 1–3 passes" (D-330, confirmed "you get it right this time"; Anthropic's
own stop rule, finding 26).** Passes are one to three per slice by construction (§ 5 item 6): round one partitioned, pass
two fix and re-verify, pass three confirm; a slice still failing after its third pass is handed off with its claims
named. The lead-turn column below is this document's PROXY for the two-hour goal (D-346: wall clock ≈ lead messages ×
~1 min) — a diagnostic read from `tok_msgs`, never a kill criterion; D-347 used it as one, and revision 22 withdraws that
use (§ 5.2 row 5).

| Shape | Commands (median lead turns today) | Mechanism | Target lead turns |
|---|---|---|---|
| Partitioned-by-file review loop (`review loop` floor) | `/fabrik-review` 99 · `/fabrik-repo-review` never run | **chunk 5** — per slice one Sonnet + one Haiku finder with a schema listing files read and candidates; a Sonnet verify stage executing each candidate and returning command + result; the lead executes only the confirmed, fixes, launches pass 2 as a new run with the ledger as `args` | 15 |
| Section-partition reviews | `/fabrik-spec-review` 58 · `/fabrik-plan-review` 92 | **chunk 6** — the same script, slices are sections, Opus on the rule/grammar sections (D-212) | 20 |
| Units-sized review family (the other 12 of the 16 in `CONFIRMED_REQUIRED_COMMANDS`) | `/fabrik-review-scoped` 36 · `/fabrik-docs-review` 87 · `/fabrik-doc-converge` 45 · `/fabrik-conformance-review` 113 · `/fabrik-workflow-review` 208 · `/fabrik-data-contract` 166 · `/fabrik-ui-design-review` 16 · `/fabrik-flows-review`, `/fabrik-rules-review`, `/fabrik-epics-review`, `/fabrik-deploy-plan-review`, `/design-review` never run; plus `/fabrik-features` 35 and `/fabrik-deploy-checklist` 129, sweeps outside the set | **chunk 6b** — the same script, one slice per unit, for every command in this row EXCEPT the three converge loops `/fabrik-doc-converge`, `/fabrik-features` and `/fabrik-deploy-checklist`, which ground rather than review and keep the `Agent` tool; the three-seat floor (D-208) is one three-finder slice | 15–25 by units |
| The plan executor | `/fabrik-execute-plan` 326 | its nested reviews take chunk 6's script; its coder dispatch already fans out; the phase-boundary chain fixed at four calls | 60 |
| Producing commands | `/fabrik-spec` 56 · `/fabrik-plan-after-chat` 83 · `/fabrik-ui-design` 26 · `/fabrik-vision`, `/fabrik-epics`, `/fabrik-flows`, `/fabrik-rivals`, `/fabrik-deploy-plan` never run | **chunk 7** — reads above ~30 k tokens go to seats returning summaries (finding 4); a judge panel replaces the lead iterating alone; the four-call close | 25 |
| Certification and utility | `/fabrik-user-test` 145 · `/fabrik-service-test` 122 · `/fabrik-catchup` 255 · `/fabrik-command-improve` 46 · `/fabrik-task` 30 · `/fabrik-release` 12 · `/fabrik-deploy`, `/fabrik-deploy-verify`, `/fabrik-decommission`, `/fabrik-upstream`, `/fabrik-generate-tests` never run | only the four-call close and delegated reads; `/fabrik-task` unchanged (§ 6) | measured on the next run; no target until two runs exist |

**The four-call close** is the one edit all 38 commands share: receipt fill and check from a values file · commit
through the recipe · gate `--check` · close by name. Its input files are written first, each in its own call.

**The order, by the hours** (runs × median wall): `/fabrik-execute-plan` 245 h, `/fabrik-review` 118 h, and the
review is nested inside the executor — so chunk 5, measured on two runs, then 6, then 7. Never three chunks open at
once (the manifesto's WIP invariant).

**How the turn budget acts** (findings 8–9): it is NEVER a refusal on the lead — reached by the shape change,
printed at `start` beside D-339's minute budget, read at the close and by each chunk's KILL; one closing turn is
reserved; one extension is allowed by rule; nothing counts down. D-339's minute budget keeps its per-slice handoff —
the most reversible action when a gate cannot close within budget (manifesto Invariant 3).

**Where the manifesto binds each chunk.** Phase 0: a script beside the loop is reversible, so each chunk takes the
fast path with a one-line kill criterion at entry and the turn budget as its decision budget. Phase 1: chunk 5's
kill criterion — two `/fabrik-review` runs at ≤ 15 lead turns with confirmed counts not below this session's D-335
runs and the escaped-defect rate not up, else reverted. Phase 3: every measure ships with its cheapest satisfying
move (§ 6.1) in the script's docstring and its D-row. Phase 4: `/fabrik-review` only, instrumented by `tok_msgs`,
two runs before chunk 6 opens. Phase 5: the close prints turns against budget on every run and the daily feedback
relay carries it; the loop re-enters at chunk 6 or closes.

---

## 6. How we will know it worked

Read from the same ledger, two weeks after § 5 is applied, against the 2026-09-21 baseline. The
first row is the one keyed to § 4.7 and § 5; every other row is expected to follow it, and a row
that moves without the first one having moved is a symptom treated, not a cause.

| Metric | Baseline | Target |
|---|---:|---|
| **A simple change end to end** — spec → spec review → plan → plan review → execute → review | **611 min** at the medians (§ 2.1); `/fabrik-task` 41 min | **≤ 120 min**; `/fabrik-task` unchanged |
| **Runs whose terminal carries a cost term** (the declared budget beside the correctness term) | **1 of 27** | every run |
| **Commands whose first phase executes MCP · rules · infra · manifesto** | 0 · 9 · 6 · 0 of 38 (sources, 2026-09-21) → 38 · 38 · 38 · 38 of 38 rendered commands (2026-09-22, D-342) | 38 of 38 |
| **Runs whose terminal is "every slice verified"** — a per-slice claim ledger in the run record, every claim executed true, not a reader's quiet round | **0 of 27** | every run |
| **Rounds per review-family run** | median 3–4; 35 runs of 10+ hold 42% of the hours (§ 2.5) | ≤ 3 by construction, a failing slice handed off with its claims named |
| **Closes that ran to a quiet round** (terminal condition actually met) | 78 of 191, **41%** | over 90% |
| **Closes `done` with defects still confirmed at the last round** | **71** (452 defects standing) | 0 |
| **Confirmed defects found at round 4 or later** | 2,168 of 6,919, **31%** | under 10%, with the total NOT falling |
| **Multi-round series that rise at least once** | 94 of 178, **53%** | under 20% |
| Median rounds, prose artifacts vs code-with-a-gate | 5 vs 3 | converged, at 3 or below |
| Spec-chain cost at the medians | 611 min = ~615 lead turns at ~1 min each (§ 2.6) | **≤ 120 lead turns** (a diagnostic proxy for the two-hour goal, never a kill criterion — the criterion is ≤ 3 passes per review, D-330) — spec 25 · spec-review 20 · plan 25 · plan-review 20 · execute 60 (its nested reviews included) · review 15; `tok_msgs` per run is the reading, printed beside the minute budget; never a refusal on the lead (§ 5.3) |
| **Slices read in full by their finders** — the files each finder returned as read, diffed by the script against its slice | not measured — today's seats return no read list | every slice, every pass; a gap is logged and the slice is unverified (§ 4.9 finding 10) |
| **Review stages per change, and each stage's yield** — how many review-family runs fire for one change across the chain (spec review, plan review, per-phase review and docs review, whole-plan review, scoped reviews), and the confirmed defects each returned | not measured — first read before chunk 6, from the ledger's `surface` and `confirmed` per command (§ 4.9 finding 35) | every standing stage earns its place by yield; a stage with none over a month goes conditional, never silently |
| **Escaped defects** — commits touching a reviewed surface's files within 14 days of the review's close, any subject, not only `fix` | not measured — first read at chunk 5's first run, from git and the ledger's `surface` | not rising while turns fall (§ 4.9 finding 11: the one measure the reviewer cannot move) |
| Total hours per week | 375 | falling, with runs per week flat or up |
| Total tokens per week | 22.6 G | falling |
| Hub `CLAUDE.md` bytes (loaded every turn) | 134,466 → **100,892** (2026-09-22) | falls only where a story goes; the rule count never falls (D-331) |
| Template `CLAUDE.md` bytes (×46) | 127,624 → **103,912** | the same rule |
| Largest rendered command | 123,843 → 120,521 | the same rule — no byte target |
| Rendered corpus, 37 commands | 2,783,253 → 2,743,865 | the same rule |

**First measured chain, stages 1–2 (2026-09-23, the stop-and-compaction spec, 51098f062):** `/fabrik-spec` 84 min (measurement, grounding, a three-judge panel) and `/fabrik-spec-review` 70 min over 5 passes, 38 → 12 → 6 → 0 → 0 confirmed, closed under the scope-growth stop in ONE run. The last three hub spec reviews took 12.55 h (5 runs, 29 rounds), 14.06 h (3 runs, 32 rounds) and 9.4 h (3 runs, 12 rounds) (`command_feedback_report.py --stages`). Lead turns are not counted by any report yet. Plan, plan review and execution follow on the operator's design approval.

**Same chain, stages 3–5 (2026-09-23/24, plan `archived/2026-09-23-plan-1-stop-and-compaction`, EXECUTED 03a94e9a3, D-384):** `/fabrik-plan-after-chat` 51 min · `/fabrik-plan-review` 45 min over 4 passes (21 → 5 → 3 → 0) · `/fabrik-execute-plan` ~415 min wall for eight tickets, inside which eight nested review-family runs took 2–5 rounds each (9–48 min, every one closing at 0 confirmed) and `/fabrik-docs-review` took 83 min over 2 passes (10 → 0), including one round-1 dispatch lost to a transport failure. Spec start → EXECUTED: **~9.3 h** against the ≤ 2 h goal. No loop oscillated and none exceeded 5 passes, so this chain's cost sat in execution: eight serial ticket merges, each gated by its own review before a fleet-wide sync.

The round-4+ row carries its own guard deliberately: *"with the total NOT falling"*. Driving
late-round defects to zero by finding fewer defects overall is the failure mode, not the goal.

### 6.1 The cobra check on each metric (D-253)

- **"Terminal is every slice verified" up** is satisfied most cheaply by a slice ledger of vacuous claims — one
  claim per slice, or claims that cannot be false. Counter: the ledger is the seat's round-one findings plus the
  claims the fix introduced, each with the command that executed it; a slice with no executed command is unverified.
- **"Rounds ≤ 3" down** is satisfied most cheaply by stopping at pass three with slices still failing — the cap this
  document refused (§ 5.1). Counter: a failing slice is handed off with its failing claims NAMED in the record, and
  a `done` with a failing slice is refused by the close.
- **"Ran to a quiet round" up** and **"hot `done` closes" to zero** are satisfied most cheaply by
  declaring quiet, or by not recording the last round. Counter: under § 5 the terminal is read from the per-slice
  ledgers in the run record, written per pass by the seats' executed commands, not declared at the close.
- **"Round 4+ defects" down** is satisfied most cheaply by finding fewer defects overall. Counter: the paired guard
  *with the total not falling*; round one's partition is the same width whatever the round count.
- **"Rising series" down** is satisfied most cheaply by reporting a flat number regardless.
  Counter: the series is written per pass from the slice ledgers, not at the close.
- **Hours and tokens down** are satisfied most cheaply by dispatching fewer seats than the partition needs. Counter:
  the seat count is the surface's unit count (D-208, D-229 round one), stamped before dispatch, and a pass with fewer
  seats than slices is not a pass.
- **Contract bytes down** is satisfied most cheaply by cutting rules with the stories — which is what the
  2026-09-21 cuts did (38 ungraded rules lost, D-330). Counter: the loss audit — every sentence unit of the old
  text either survives or is named as a story in the commit — and the grader pins; a pass that loses a rule is
  reverted, whatever its byte count.
- **Corpus bytes down** is satisfied most cheaply by moving text into a doc the weight check does
  not read. Counter: `check_corpus_weight.py` measures four surfaces as directory aggregates; the
  escape is `docs/reference/` and `docs/workstation/`, named here so the next reader can grep it —
  and this document lives in `docs/reference/`, so it is itself inside its own blind spot.
- **"Lead turns ≤ N" down** (D-347) is satisfied most cheaply four ways. (a) Push the work into seats — tokens and
  clock rise while turns fall. Counter: minutes and tokens per run are read WITH it, and every chunk's KILL reads all
  three. (b) Skip files and claim the slice complete — the 1.8× miss rate of § 4.9 finding 10. Counter: the finder
  schema returns the files it read, the script diffs that list against the slice and logs every gap, and a slice with
  a gap is unverified. (c) Refute instead of confirm, narrow the brief. Counter: the paired guard *confirmed total not
  falling* plus the escaped-defect row, which no reviewer can move. (d) Stop before the closing turn. Counter: one
  closing turn reserved, one extension by rule, and the close refuses without executed ledgers (D-339).
- **"Escaped defects" flat** is satisfied most cheaply by not committing the follow-up, or labelling it as something
  other than a fix. Counter: any commit on the files counts, the window is 14 days, and the relay reads it, not the run.
- **Seeded-canary recall** is NOT adopted (§ 4.9 finding 11): the loop learns the operator set and turns green on seeds
  while real recall stays near F1 0.07.
- **The minute budget** is satisfied most cheaply by a countdown that makes the lead panic-submit (§ 4.9 finding 9).
  Counter: printed once at `start`, never counted down; an overrun hands off one slice, never the run.
- **"Done" declared against a weaker terminal the agent wrote itself** (§ 4.9 finding 14). Counter: a review-family
  terminal is the command's — `done` refuses a failing or vanished slice whatever the `--terminal` prose says (D-339).
- **The capture-recapture estimate read as a gate**, satisfied most cheaply by two finders that share notes or a
  model — overlap up, "remaining" down. Counter: two models, two contexts, one brief; the number is printed as advice
  and nothing in the record keys on it.

---

## 7. Evidence, populations and bounds

Every figure above comes from one of six sources, each named with its population and its bound.

| Source | Population | Bound |
|---|---|---|
| Fleet feedback ledger `~/.claude/state/command-feedback.jsonl` | 335 closes, 24 commands, 10 repos, 803 h | begins 2026-09-07; nothing before it; LIVE and growing |
| `FEEDBACK:` lines in every session transcript on this box | 297 unique, 24 commands, 8 repos, 748 h | begins ~2026-09-01 |
| Run records `~/.claude/state/command-runs/*.json` | 27 records, 19 with a round series | older records are deleted; only their ledger row survives |
| Seat transcripts in session scratch | 814, 6 repos | only since the last scratch sweep |
| Git history of `commands/` and `CLAUDE.md` | full month | none |
| The tool author's talk, `/opt/youtube/output/XFYUKBPfUMw_transcript.txt` | 5,589 words, one speaker + Q&A | a transcript of speech, not a spec — quotes are verbatim up to disfluencies (*um*, repeated words) and are never reordered; the mapping in § 4.6 is this document's reading |

**What is NOT covered.** 4,725 sessions predate 2026-09-01 and carry no per-command trace; most are
`youtube` and scratch sessions rather than command runs. That era ran a different convergence bar
(D-048, "zero findings") and can only be read as prose. Its absence means the month-long trend in
§ 3 is measured over two weeks of structured data plus the full month of corpus and decision history.

**Classification caveat.** Where § 4.2 counts verdicts by cause, the counts come from a keyword
classifier over the 335 `waste:` and `confusion:` fields and are indicative only — one verdict can
match two classes. The QUOTES are verbatim and are the evidence; the counts are the ranking.

### 7.1 How the figures were derived

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
| terminal-condition census (rev. 5, re-read rev. 6) | `~/.claude/state/command-runs/*.json` on disk → 27 records carrying a `terminal` field; 25 match a process-vocabulary regex (confirmed · quiet · round · gate · converge · receipt · commit · pass …) — that set INCLUDES executable process checks such as `gate green` and `docs_updater --check green`, which is why the claim is "none names a check of the delivered thing", not "none names a tool"; the 2 non-matches, read by hand, name internal build state; older records are DELETED and the surviving ledger row carries no `terminal`, so 27 is the whole readable population, not a sample of 335 |
| CLAUDE.md census (rev. 4) | `find /opt -type f -name CLAUDE.md` excluding `.claude/worktrees/`, `.tmp/`, `node_modules/` → 70 (+177 worktree copies); grouped by md5 → 47 identical to the template, 23 others, of which 20 are archived/vendored/stubs; sizes by `stat -c %s`; no `~/.claude/CLAUDE.md` exists |
| load-vs-cost (rev. 4) | bytes = `~/.claude/commands/fabrik-*.md` (the RENDERED file an agent loads); commands with ≥ 4 closes → 11; median `wall_s/60` per command; Pearson r over log(bytes) vs log(median minutes) → +0.64; not a causal claim, a direction — the ledger records no surface size (§ 4.1) |
| plan-window overlap (rev. 1) | "73 review-family closes fall inside plan windows in the same repo, 144 of its 245 hours" (§ 2.3) — derived in revision 1 from run start/end windows per repo; NOT re-derived since, and the only figure in § 2 not reproducible from a single ledger read |
| ADD-verb count (rev. 3) | the five clauses cited in § 4.3 by `CLAUDE.md` line; the negative is bounded to `CLAUDE.md` at HEAD (605 lines), `grep -n "retire\|delete\|remove"` → 15 lines, each read: a class retiring inside the loop (`:39`), "retirement" as a decision type (`:138`, `:320`), the volume-deletion ban (`:288`), file-removal doc-sync triggers (`:304`, `:314`, `:318`), scratch cleanup (`:369`), recipe prose — none an obligation to retire text |

**Two bounds on all of it.** (1) `confirmed` is written by the agent running the loop, so a run
that under-reports its confirmations looks convergent — the numbers describe what was RECORDED, and
§ 5 replaces the recorded count with per-slice ledgers of executed commands, which are harder to write falsely. (2) The hot-close
count cannot distinguish an abandoned run from one whose final fixes were applied after the last
recorded round; § 4.1 rests on that ambiguity being unresolvable, not on every one of the 71 being
an abandonment.

---

## 8. Revision history

### 8.1 Progress on the OLD § 5 (revisions 4–7) — all of it REVERTED on 2026-09-21 (D-330, `174267506`)

Kept as the record of what was tried. Each row's byte cut was green against every grader and lost ungraded rules;
the surviving successor is D-331 (§ 1.0).

| Step | Landed | Commit | Result |
|---|---|---|---|
| 1a · hub `CLAUDE.md` cut, pinned spans verbatim | 2026-09-21 | `a6f42dafa` (D-326) | 134,466 → 82,296 B; 51 test files green bar 4 pre-existing failures named in D-326; the ~57 KB of grader-pinned spans wait on 1b |
| 1b(ii) · the QUOTA bullet → a pointer | 2026-09-21 | `06cd26a94` + fix `acc108b4c` (D-327) | 12,474 → 1,550 B; file 71,372 B; the three-way byte-identical graders retired for one pointer test; fabrik-lib mailed (`01M31Y7ZHBAM0T7YR61ANVKM9M`). The first commit landed red — two pins wrapped across line breaks and the chain read `tail`'s exit, not pytest's — fixed in the second |
| 1b(iii) · the lane table's parentheticals | deferred | — | ~45 pins, each from an executed mutant, on the live interface to `_task_size_gate`; the lane/spec-chain routing is what step 3 retires, so this is cut with step 3, not trimmed before it |
| 1b(i) · the commit recipe → a tested script | 2026-09-21 | `fa463ffcc` (D-328) — committed BY the script | `private_index_commit.py` (removed with the revert) + nine red-first graders in `tests/test_private_index_commit.py`; the graders caught the prose's own step 5b missing (working file not brought up to the new base after a CAS retry) — now a three-way merge, proven by mutant; the 11,136-byte recipe is a 1,302-byte pointer; twelve T6 pins retired. File **61,400 B** — step 1 complete: 134,466 → 61,400 (46%), every remaining pinned span kept verbatim |
| 2 · the project template cut and synced | 2026-09-21 | `230212243` (D-329) — committed by the script | 127,624 → **62,003 B** (49%), every project-side divergence preserved; 53 test files → 2,599 passed and the same 4 pre-existing failures as the unchanged file; dry-run read first (46 files, worktree copies untouched, wrote nothing), then one forced sync: **41 of 41 in-scope synced projects** carry the new file; the 2 non-matching `/opt/*/CLAUDE.md` are `fabrik-lib`'s linked worktrees, sync-excluded by design |

Revisions 1–7 all on 2026-09-21. Each went one layer further down than the last; the operator refused every one, and revision 8 replaces the program with the determination confirmed the same evening (§ 4.7).

**Revision 1 (2026-09-21):** the first draft — a diagnosis leading with *the fix between rounds is the next round's defect* and a five-item program headed by a hard round cap. Commit `93dba9a39`.

**Revision 2 (2026-09-21, same day):** § 4 and § 5 rewritten. The operator refused the round cap (*"capping is not a solution"*) and the first draft's root cause (*"you could not find the root cause properly"*). Both refusals were right; the new root cause is § 4.1, the cap is refused in § 5.1, and two claims from revision 1 are withdrawn in § 4.5. The same revision adds § 2.5 (where the rounds and the hours actually sit), the non-convergence detector's two measured limits inside § 4.1, and the full seat arithmetic behind § 4.5's second withdrawal.

**Revision 3 (2026-09-21, on *"be 100% sure first"*):** the document was stress-tested against its own standard. § 4.1's prose-vs-code test is CORRECTED — the ledger records no surface size, so the gap is real in direction but overstated in size; § 4.1 gains the positive control it lacked (the one prose command that already carries an artifact-side terminal condition converges in 2–3 rounds); § 4.2 gains the supply side (seats are recall-optimised by design and the confirmed rate decays from 69% at round 1 to 44% at round 10+); § 4.3 names the generator of the growth; § 7.1 carries every new derivation.

**Revision 4 (2026-09-21, on *"i still dont think you understand what is the problem"*):** the root cause is re-cut one level up, to the system (§ 4.0): the process cannot shrink and its load is its cost. § 4.1's loop mechanics are now stated as the consequence they are. § 5 is replaced whole. The three-contract census and the load-vs-cost test are added with their derivations (§ 7.1).

**Revision 5 (2026-09-21):** the root cause goes one level further down than revision 4 — not the load, but what the load was built to serve: **"done" is defined as process compliance, never as an outcome the operator can see.** § 4.0 is rewritten to lead with it; the load (rev. 4) and the loop (rev. 2–3) are ranked beneath it as its two consequences. § 5 is one sentence.

**Revision 6 (2026-09-21, after the operator's *"reread and comprehend it now"*, three times):** the root cause gains its ground. Revision 5 said *done is process compliance*; that is true and it is what the apparatus produces. Under it: **we built a thick apparatus on top of a tool whose author says the apparatus should be as thin as possible — because the value is in the model and the model is moving.** § 4.00 states it, § 4.6 carries the source, § 5 is rewritten as his method.

**Revision 7 (2026-09-21, on *"comprehend again... fully review the document... be 100% sure"*, twice):** two full read-throughs of the document against two full readings of the transcript. The first found eleven non-verbatim quotes, an overstated census and twenty stale cross-references; the second found a wrong share in § 2.3 (86% → 88%), an unexplained population change in § 4.1's stratified table, and this revision block sitting where the reader's first thirty lines should be — moved here. The fourth and fifth readings of the transcript found nothing the third had not.

**Revision 8 (2026-09-22, on the operator's *"update … so that it must first reflect the changes we have made [to] all
3 claude.md files … then … according to … our determinations"*):** the file is restored from `f5a4c367f` (deleted by
the D-330 revert) and re-cut. § 1.0 records the 2026-09-21 cuts, their reversal and the D-331 lean program that stands
(hub 134,466 → 100,892 B, template 127,624 → 103,912 B, fabrik-lib unchanged and mail-only). § 4.7 states the confirmed
root cause — the loop is partitioned only in round one — with the two 2026-09-22 runs as its demonstration. § 5 is
rewritten as engineering inside the loop; the old § 5's removal program is withdrawn in § 5.1 and its item 4 (retire the
review family) stated as wrong. § 6 loses its byte targets for the lean-without-loss rule. Every figure in §§ 2–4 was
re-derived from the ledger the same day and reproduces to the percentage (338 closes, 807 h; 57% review family; 41%
quiet; 71 hot `done` closes, 452 standing; 53% rising; 66% after round 1; 31% at round 4+).

**Revision 9 (2026-09-22, on the operator's *"goal is missing … we must do lean, fast, accurate, complete runs … it
must be done in 2 hours … i think it is cobra effect, we are optimizing against a wrong goal?"*):** § 1 opens with the
goal in the operator's words and the two-hour target against the measured 611 minutes; § 4.8 answers the question with
the rule text and the ledger — the loop's objective has one term (accuracy; `accurate` 124 : `fast` 4 in the close
verdicts, 1 of 27 terminals naming a cost) and enforces MCPs / rules / infra / manifesto in 0 / 9 / 6 / 0 of 38
commands; § 5 item 4 gains the budget term, item 5 the refuted/recorded mechanics and item 7 the enforcement step; § 6 gains the three rows that measure them.

**Revision 10 (2026-09-22, on *"fable or opus can orchestrate. yes make these changes"*):** § 4.7 gains the seat
numbers — 1.75 seats per round, Opus 58% of seats, the orchestrator at 64% of input — and the orchestrator ruling
(D-334); § 5 names D-335, the row that supersedes D-229's delta sizing and the fresh-non-authoring closing clause.
The build of § 5 begins with the two fragments, the reviewer brief and the sources that restate them.

### 5.2 Progress on § 5 — one line per chunk as it lands

| Chunk | Landed | Commits | Result |
|---|---|---|---|
| 1 · the two termination fragments, subagents-core, the reviewer brief's passes-after-the-first mode, nine sources, the test pin | 2026-09-22 | `d03f9a918`, `f6beb8b88`; review fixes `863701479`, `811c3d340`, `93ea1f6eb`; receipt `5d435de09` | every pass after round one is the round-1 seats over their own slices; refuted/recorded opens nothing; the budget clause gated on `start` declaring it; reviewed in its own shape — 4 passes, 11 → 3 → 3 → 0, 25 min; `62-using-subagents.md:74/:211` still carries the old clause (intel's live pass — theirs to edit) |
| 2 · `command_run.py` (`--budget` on `start`, the per-slice ledger on `round`, a review-family round without `--confirmed` refused, `done` refusing a failing slice) and `dispatch_headroom.py` (`--delta` retired) | 2026-09-22 | `2e917b17c` (D-339; ledger `16adffc3c`, `5853c00e8`) | fleet-synced and distributed by the post-commit sync; ten graders red-first; the refusal scoped to 15 review-family commands, every other caller keeps D-206's tolerant rule; the contract sentence mirrored in both `CLAUDE.md` copies; reviewed in the D-335 shape — 4 passes, 14 → 6 → 3 → 0 on the same three seats, 21 confirmed (13 in round one, then 8 residuals of the fixes), 62 min against a 45-min budget (over, printed, never a cap), fixes `65ae40693`, `103d19ebd`, `e0490606d`, D-341 (the set is 16 by rule), receipt `5e0a21db4` |
| 3 · every command's first phase executes MCP · rules · infra · manifesto (§ 5 item 7) | 2026-09-22 | `128050dbc` (D-342) | one fragment, `orient.md`, included by all 38 sources right after the run record: the four executed lines and the `ORIENT:` reply line; rendered 38 / 38 / 38 / 38 of 38 (measured over `~/.claude/commands/*.md`, the rendered corpus — a source count reads 0 / 9 / 6 / 0 because the lines live in the fragment); grader `tests/test_orient_fragment.py`; the same change removed D-229's delta round from the assembler's two floors and both `CLAUDE.md` contracts, and the round-zero probe now runs before every re-dispatch; reviewed in the D-335 shape — 3 passes on the same three seats, 17 → 1 → 0, 15 confirmed (14 in round one — among them a FLEET defect, two hub-only paths in the fragment, caught by the orchestrator's own round-zero probe before the seats returned — then 1 mirror residual of the fix), 45 min against a 30-min budget (over, printed, never a cap), fixes `1fd4898a8`, `02c8898b9`, `e61baa6ed`, receipt `69140bfca` |
| 5 · the review loop as a workflow script (`.claude/workflows/fabrik-review-loop.js`) — two cheap finders per slice with a schema whose `files_read` is diffed against the slice, a Sonnet verify seat per candidate returning command + output, one ledger back, each pass its OWN invocation with the ledger in `args`; `/fabrik-review` and `/fabrik-repo-review` launch it | 2026-09-22/23 | `7f429a341` (D-350); run-1 fixes `5a7803da2`, `55fca7db8`, `214bbdb6c`, `819e2f01a`, receipt `310762e24`; run-1 lessons `f5eb13f3a`; run-2 fixes `d53d0db2c`, `0929d6e6d`, receipt `2c08ac005` | two measured runs, both reviews of the loop itself. **Run 1** (10 files): 2 passes, 20 raised / 13 confirmed / 4 refuted, 30 agents, 2.61 M seat tokens, **19 lead turns**, 35 min. **Run 2** (4 files): 3 passes, 7 confirmed, 18 agents, 0.56 M seat tokens, **17 lead turns**, 21 min. Against today's `/fabrik-review` median of 99 lead turns and 86 min. **Against the operator's criterion both runs settled — 2 passes and 3 (D-330: 1–3).** **The D-347 KILL fired as written** — keyed on the lead-turn proxy (withdrawn as a criterion in revision 22) — both runs sit above the 15-turn target, and confirmed counts (13, 7) fall below the D-335 baseline (14, 21, 15), which was measured on 16–51-file surfaces against these 10 and 4; Invariant 4 defaults a fired criterion to kill, and an override is a new written claim with a new criterion, never an edit of this one (operator decision, pending). What the runs showed: the lead's turns went to in-turn waits (the Stop hook holds the turn while a record runs) and to reading results, not to seats; every workflow agent is invisible to the run record's seat counters (`seats_seen 0` on both closes — seat tokens come from the notifications); a status vocabulary restated in four places drifted in one run (run 2's second-pass defect: the candidates rule inverted when the statuses were keyed on the defect) — a vocabulary is stated once and pointed at; a closing seat reported the lead's latest operator message relayed into its prompt, which it ignored. |
| 5b · the loop's follow-ups from its two runs and the research (findings 25–43): `unverified` never counted as refuted and never closing a pass, refutation citing its counter-evidence (36); checks under ~10 calls run by the lead inline, one fresh refuter per slice for the rest (27, 41); finders at `medium` effort, the recall-first brief kept (38); the review lead on a short prefix with the ledger in a file (30); seat hygiene — `cacheTtl: 1h` on the reviewer agent (41), OpenTelemetry for seat tokens (33), every seat naming `model` and `effort`, and `CLAUDE_CODE_SUBAGENT_MODEL_FORCE` refused while a pair runs (37, 43); the first stop condition and fix-hunk size logged (39); the stages-per-change count (35) | chunk 1 landed (D-355): one fresh refuter per slice at `high`, finders at `medium`, a refutation without a real command or with no output is `unverified`, `unverified` never closes, each slice and pass returns `closable` + `open`, ledger rows as objects or plain claims, the reviewer agent at `experimental.cacheTtl: 1h`; chunk 2 landed (D-357): each pass read into a file by `scripts/review_loop_ledger.py` with every seat timed (`OVER BOX`, `UNTIMED`, `NO RESULT`) and the next ledger built from it, `CLAUDE_CODE_SUBAGENT_MODEL_FORCE` refused by `dispatch_headroom.py`, seats told never to write outside their scratch and to time-box blocking commands, each Pass row naming its stop and measured fix size; chunk 3 landed (D-358): per-seat tokens from each seat's own transcript (no OpenTelemetry collector — its token metric names a user-defined seat `custom`), the stages-per-change report `command_feedback_report.py --stages` with its coverage (101 of 239 review runs keyed on its first run), and the lead-inline item REJECTED after measurement (finding 27's qualification) | D-355, D-357, D-358 | measured on the next real review against the operator's ≤ 3 passes, a target never a cap (D-355), and D-344's per-seat counts |
| 6 · the same script for the section-partition reviews (`/fabrik-spec-review`, `/fabrik-plan-review`) and the reviews nested in `/fabrik-execute-plan` (144 of its 245 hours) | 2026-09-23 | D-361 | the workflow script takes each slice's seats — `models` (one to three of opus/sonnet/haiku, default D-344's Sonnet + Haiku pair), `agent` (`fabrik-researcher` for a cited-fact slice, finder and refuter) and `scope` (the sections it owns); `/fabrik-spec-review` and `/fabrik-plan-review` launch it with their section partition (one Opus seat on the rule sections, one Sonnet on the rest, D-212/D-218) and run later passes as the round-1 seats over their ledgers (D-335), retiring the stale delta-by-fix sizing; `/fabrik-execute-plan`'s phase and per-ticket reviews point at `/fabrik-review`'s loop instead of restating an older method, its per-round Opus finder kept as the riskiest slice's third finder | ≤ 20 lead turns each; execute-plan ≤ 60 |
| 6b · the units-sized review family on the same script — `/fabrik-review-scoped` and every review-shaped units fan-out (docs-review, conformance-review, workflow-review, data-contract's review loop, ui-design-review, flows-review, rules-review, epics-review, deploy-plan-review, design-review); the converge loops `/fabrik-features`, `/fabrik-doc-converge` and `/fabrik-deploy-checklist` ground rather than review and stay on the `Agent` tool | 2026-09-23 | D-365 | one slice per unit (`scope` = the unit, `models: ["sonnet", "haiku"]`), the Opus authoritative seat the risky unit's third finder, one refuter per unit; `/fabrik-review-scoped`'s three-reader floor is one such unit, its later passes only the units with an open claim on their round-1 seat; the thirteen others take it from `subagents-core` (grounding, authoring and adjudication fan-outs stay on the `Agent` tool) and `/fabrik-deploy-plan-review` from its own fan-out paragraph | 15–25 by units |
| 7 · the producing commands delegate their reading and judging — `/fabrik-spec` and `/fabrik-plan-after-chat` send large reads to seats that return summaries and use a judge panel instead of the lead iterating alone; the closing chain fixed at four calls (receipt fill and check · commit through the recipe · gate · close), inputs written first | 2026-09-23 | D-363 | three fragments: `delegated-reads` (a read over ~30 k tokens goes to one seat per source, briefed with its question, returning `path:line`-anchored claims the lead still executes), `judge-panel` (three Sonnet seats rank the approaches blind to the lead's pick) and `close-chain` (inputs written first; the artifact's check · the artifact and code by pathspec, then the ledgers through the private index · the gate · `done` by name); `/fabrik-spec` takes all three, `/fabrik-plan-after-chat` the reads and the close (it selects no approach itself), retiring its self-contradicting "do not commit" paragraph | ≤ 25 lead turns each; the chain under 120 |
| 7b · the rollout of chunk 7's two shared fragments to the rest of the corpus (§ 5.3: the four-call close is the edit all 38 commands share) | 2026-09-23 | D-367 | `close-chain` in 37 of 38 sources — every command but `/fabrik-task`, which keeps its own close (§ 5.3) — the assembler filling the command's name and, where the command sets none, a pointer to the check its own close names; `delegated-reads` in the 23 commands that read large sources themselves (the producing, converge, certification and utility commands), never in the review family, whose seats read | measured on the next run of each |

**Revision 24 (2026-09-23):** finding 43 from the late deep-research run (its ten cards read whole, the Opus 5.5
system card's team and self-preference sections by raw fetch); finding 37's `CLAUDE_CODE_SUBAGENT_MODEL` claim
corrected — an explicit per-seat model wins, only the `_FORCE` variable collapses the pair.

**Revision 23 (2026-09-23, the read-whole pass):** every fact and card the research returned is filed in a ledger
(`docs/reference/research/2026-09-23-loop-program-research-ledger.md`, 162 rows, each dispositioned); the 71 URLs (69 pages) no
finding had cited were read whole by eight readers; § 4.9 gains findings 36–42 and six corrections; § 5.2 gains row 5b, the
design changes they imply. The same change makes the ledger permanent: `scripts/check_research_ledger.py` refuses a
ledger with an undispositioned row, a hub pre-commit hook runs it, `CLAUDE.md` § External Knowledge requires it before
any synthesis, and the research agent is wired to firecrawl.

**Revision 22a (2026-09-23):** § 4.9 finding 35 — a practitioner's measured cut of a six-stage review chain to one, read
whole on the operator's hand-over; § 6 gains the stages-per-change and per-stage-yield row.

**Revision 22 (2026-09-23, the Opus 5.5 week):** § 4.9 gains findings 25–34 from five research seats and one probe
(Opus 5.5 as the cheaper orchestrator; Anthropic's two-or-three-continuations stop rule; no seat for a check the lead can
run, a fresh refuter for findings; the finder pair open again — Sonnet 5's recall below 4.6's, finding 5 qualified; fresh
seats per pass confirmed over SendMessage wakes; the lead's transcript as the cost; pilot 1 now working at 2.1.280; the
seat-cache and telemetry facts; the time-budget pattern against finding 9); § 5.3 and § 6 state that the operator's
criterion is passes (1–3, D-330) and the lead-turn budget a diagnostic proxy; § 5.2 row 5 reads both runs against it.

**Revision 21 (2026-09-23, chunk 5 measured):** § 5.2 row 5 lands with both measured runs (19 and 17 lead turns
against 99; confirmed 13 and 7 on 10- and 4-file surfaces), states that the D-347 KILL fired as written and that its
disposition is the operator's, and records the three findings the runs produced: the seat telemetry is blind to
workflow agents, a restated status vocabulary drifts (state it once), and the lead's turns are waits and reads.

**Revision 20 (2026-09-22, the module run, D-348):** § 4.9 gains findings 14–24 from fabrik-lib's `deep-research`
run over six engineering briefs (60 cards, 57 verified, ≈ $0.20) and withdraws revision 18's "not for engineering
questions" verdict; § 5 item 6 gains the per-slice capture-recapture advice; § 5.3 states that targets are lead turns,
never passes (passes stay ≤ 3 per slice); § 6.1 gains the self-written-terminal and the shared-finder cobras.

**Revision 19 (2026-09-22, the final research and the path by command, D-347):** § 2.6 gains the `tok_msgs`
distribution — every § 6 target is below today's p10, so the budget is a shape, never a cap; § 4.9 gains findings 8–13
(turn caps and countdowns, coverage overclaim, canaries vs the lagging measure, the Workflow tool's constraints, the
resume trap); § 5.2 row 5 corrected — each pass its own invocation, resume re-runs a fan-out; § 5.3 states the path
for all 38 commands in six shapes, the four-call close, the order and the manifesto binding; § 6 gains the
slices-read and escaped-defect rows; § 6.1 the turn-budget cobras.

**Revision 18 (2026-09-22, the research and the path):** § 2.6 — wall clock is the orchestrator's message count times
~1 minute in every chain command, so the two-hour goal is a 120-turn chain; § 4.9 gains the seven research findings with
their sources; § 5.2 gains chunks 5–7 (the review loop as a workflow script, then the section partitions and the nested
reviews, then the producing commands' reads and the fixed closing chain); § 6's chain row becomes the per-stage turn
budget (D-346).

**Revision 17 (2026-09-22, the D-344 review):** § 4.9's numbers reconciled by its review — the run-record 31 minutes vs the 45
elapsed, the ≈4 bytes/token divisor, § 4.7's Opus sentence dated as the pre-D-344 mix, the KILL's home (the Pass-1 row's
Method cell) and the baseline's provenance, pilot 1's null result at 2.1.276; the pilot's first-run measurement added.

**Revision 16 (2026-09-22, the seat-cost research):** § 4.9 — where a review's tokens go (our ledger: seats 35%,
orchestrator 65%, 76% of it prefix re-reads), the outside evidence, the two answers, and the two pilots minted as D-344
(no `CLAUDE.md` in a finder; two cheap finders per slice, no Opus finder); pilot 3 stated with its measure, undecided.

**Revision 15 (2026-09-22, chunk 3's review closed):** § 5.2 row 3 records the review (3 passes, 15 confirmed, 45 min over a
30-min budget); § 4.7 gains the third measured run — the round-zero probe before every re-dispatch cut the residue passes
from three to one.

**Revision 14 (2026-09-22, chunk 3's review, round 1):** the Status line catches up with § 8; the four-count reading is
stated in ONE order everywhere (MCP · rules · infra · manifesto = 0 · 9 · 6 · 0 of 38 sources — `agents-fabrik.md`
by exact name is 6, the earlier 7 counted `agents-fabrik-core.md`); § 4.8, § 5 item 7, § 6 and § 8 rev 9 corrected.

**Revision 13 (2026-09-22, chunk 3):** § 5.2 row 3 lands — the `orient` fragment in all 38 sources, measured 38 of 38
over the RENDERED corpus (the honest population once the lines live in a fragment); § 6's row carries both readings.

**Revision 12 (2026-09-22):** § 5.2 row 2 records chunk 2's review (4 passes on the same three seats, 21 confirmed, 62
min over a 45-min budget, D-341); § 4.7 gains the second measured run and names the residue class the round-zero
probe misses when it runs once instead of before every re-dispatch.

**Revision 11 (2026-09-22, on *"we are updating the doc"*):** § 4.7 gains the run measured after chunk 1 (seats 3, 3, 1,
1; the rule's model mix for the first time; orchestrator share 64% → 50% of input; 25 min against a 94-min median; the
two remaining wastes named); § 5 item 6 is reconciled with item 8 — a per-slice handoff, never a cap; § 5.2 records the
chunks as they land.
