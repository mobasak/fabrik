# Kaizen feedback loop — a DELTA on the converged closed-loop v2 spec

Status: DRAFT — the 1c blocker is CLEARED (see § BLOCKED: NON-CONVERGENCE — LIFTED); D4 added
2026-09-11 and not yet reviewed, so a review round is owed before any flip
Date: 2026-09-10 (round-1 review 2026-09-11)
Author: fleet (Claude, /fabrik-spec) — operator: Özgür
Delta on: `docs/superpowers/specs/2026-08-16-kaizen-closed-loop-v2-design.md` (Status: CONVERGED, 588 lines, author infra)

⚠️ **CITATION CONVENTION — by SYMBOL, not by line.** Three sessions plus a daily pipeline commit to
this tree, and every line number in this spec's first draft had drifted within a day
(`_feedback_ledger_path` 904 → 922, `_surface_hits` 413 → 445, the append site 1008 → 1125). Every
code reference below names the **function or constant**; `grep -n` it. Line numbers appear only where
a file is frozen (an archived plan, a converged spec).

## External facts and the approach floor (1c)

This delta is grounded in-repo, but its APPROACH was researched live on 2026-09-11 by four parallel
`fabrik-researcher` seats, because `check_spec_convergence.py`'s 1c floor is explicit that the
no-external-facts escape *"exists for 1a (facts…); the approach space always exists, and 'purely
internal' is the exact self-exemption"* the floor refuses. An earlier draft claimed the escape and was
wrong to. The approach sources are cited in § Approaches considered and § D4; the load-bearing ones:

- Zhuge et al., *Agent-as-a-Judge* (Meta AI/KAUST) — https://arxiv.org/abs/2410.10934
- Panickssery, Bowman & Feng, *LLM Evaluators Recognize and Favor Their Own Generations*, NeurIPS 2024 — https://arxiv.org/abs/2404.13076
- Feuer et al., *When Judgment Becomes Noise* — https://arxiv.org/html/2509.20293v1
- Shankar et al., *Who Validates the Validators?*, UIST 2024 — https://arxiv.org/abs/2404.12272
- Gao, Schulman & Hilton, *Scaling Laws for Reward Model Overoptimization*, ICML 2023 — https://arxiv.org/abs/2210.10760
- Liu et al., *Lost in the Middle*, TACL 2024 — https://arxiv.org/abs/2307.03172
- Kohavi, Tang & Xu, *Trustworthy Online Controlled Experiments* (Cambridge 2020) — https://assets.cambridge.org/97811087/24265/frontmatter/9781108724265_frontmatter.pdf
- NIST/SEMATECH handbook, Shewhart's minimum-N — https://www.itl.nist.gov/div898/handbook/pmc/section3/pmc32.htm
- Google SRE, *Canarying Releases* — https://sre.google/workbook/canarying-releases/
- Netflix, *The Lifecycle of LLM-as-a-Judge* — https://netflixtechblog.medium.com/the-lifecycle-of-llm-as-a-judge-building-aligning-and-monitoring-at-scale-c95bd8283508
- ESLint, *Introducing bulk suppressions* — https://eslint.org/blog/2025/04/introducing-bulk-suppressions/
- Anthropic, *Building effective agents* — https://www.anthropic.com/engineering/building-effective-agents

⚠️ Vendor docs are labelled as such where cited. No 1a external FACT is relied on: no vendor API,
standard or third-party runtime behaviour determines any mechanism here.

## Personas

| Persona | What they need from this loop |
|---|---|
| **The operator** | To not read dashboards. Every mechanism delivers to an AGENT — the relay's own docstring names this ("the operator does not read dashboards"). The one act reserved for the operator is the M1→M2 variance sign-off, because `docs/workstation/kaizen.md` makes it theirs. |
| **A hub agent closing a run** (1 of 3 concurrent sessions) | To pay nothing extra. The four close-out fields already exist and a close is already refused without them. |
| **An agent in any of the ~46 project repos** | To be unaffected until a change is deliberate. The ledger is already box-wide; no project-side behaviour changes and no fleet-synced file is auto-edited (Constraint 1). |
| **The analyst pass** (the beat-owning session the kaizen mail wakes) | Series it can ADJUDICATE — which today it cannot, because the noise floor is empty. D3 is the finding that blocks this persona. |
| **infra** (owner of kaizen, commands, rules, enforcement) | To not be handed work by default. They carry 64 of 65 `ack=required` items; § Who builds what routes around that. |

## Intake Inventory

| # | Intake | Disposition | Where it landed |
|---|---|---|---|
| I1 | "i want all statistics recorded, evaluated and commands, rules, claude.mds and similar governance files kept optimum to have fast, lean, accurate, permanent, resilient commands/skills/rulepacks" | IN | The whole delta |
| I2 | "now will we collect all feedbacks from the agents into kaizen and act accordingly" | IN | D1 (collect) + D3 (the act half is built and stalled) |
| I3 | "each agents running in the repo submit a feedback record where are they created and stored and connected to our kaizen" | IN | § Ground truth |
| I4 | "do we need to make any changes in commands/skills files?" | IN — answered NO | Constraint 2 |
| I5 | "reconcile your kaizen delta's Q5 canaries against its D6 hygiene classes" | IN — verdict DISJOINT | Q5's closing paragraph |
| I6 | "be 100% sure first" | IN | Every figure carries its producing command; § Self-audit |
| I7 | A change queue designed from scratch | **OUT-OF-SCOPE** — v2's M2 already defines "finding registry + tested selection policy + fix ledger" | Q3 |
| I8 | A new standalone metrics store | **OUT-OF-SCOPE** — would fragment what this delta exists to unify | Q1 · § fabrik-lib verdict |
| I9 | A `waste:`/`confusion:` free-text taxonomy | **OUT-OF-SCOPE (deferred)** — no honest definition yet | Q2 |
| I10 | Four new series including `rounds_to_converge` and a cost-per-round | **OUT-OF-SCOPE — REFUTED BY REVIEW** (R1, R2, R5 below) | Q2, rewritten to two |
| I11 | A disk-BYTES corpus budget as a gap in v2 | **OUT-OF-SCOPE — REFUTED BY REVIEW** (R3); reframed as building what v2 specified | D2, Q4 |
| I12 | Whether seat/model/cost series belong to kaizen or intel's flywheel | **ASK** — mailed intel `01M25E4SRWVYFBC4R48ANW7Z3W`, unanswered | § Open |
| I13 | Sequencing against infra's held forced fleet sync | **ASK** — operator's call | § Open |

## What round 1 of the review refuted — read this before the deltas

Round 1 (3 seats, disjoint slices, 17 CONFIRMED findings) **damaged two of the three original deltas
at the premise.** They are recorded here rather than quietly rewritten, because the refutations are
more useful than the claims were:

| # | The draft claimed | The truth, executed |
|---|---|---|
| R1 | four new series ship at `@v1` | **All four refuse to LOAD.** `kaizen_collect_v2.py`'s registry validator raises `ValueError` on any metric without a `counter_metric`, on self-pairing, on an unregistered counter, and on non-reciprocal pairing. Probe: `metric command_cost_per_round has no counter_metric — unpaired definitions REFUSE to load`. The live registry is 16 metrics in 8 exclusive reciprocal pairs. |
| R2 | `rounds_to_converge` is new | **It duplicates a live series.** `kaizen_outcomes.py::review_rounds` is docstringed *"Mean max-round per round-carrying session (rework_rate's counter pair)"* and has published daily since 2026-08-22 as `review_rounds@v10`. The draft even cited that series by name as D3 evidence, then proposed the same quantity. And `rework_rate` is already taken as its pair, so it is unavailable. |
| R3 | v2's shrink question is "a *report*"; "nothing ratchets" governance size | **v2 already specifies the ratchet WITH this delta's escape hatch**, at `2026-08-16-…-design.md:310-313`: *"total injected governance tokens per median session — measured from transcripts, not from disk — is a guardrail that must trend flat-to-down; a change that grows it names what it retires."* It was never BUILT (`grep -rc "governance_mass\|governance-mass" scripts/` → 0). So D2 is not a gap; it is unbuilt work, and the draft's Q4 reversed v2's adjudicated UNIT (transcript tokens, attributed to opus-5) in favour of disk bytes **without citing that v2 had decided it**. |
| R4 | the M1→M2 gate reading is "my interpretation" | **The doc states it; the draft's paraphrase dropped the clause.** `kaizen.md` says the window runs *"from the cutover's first daily cron run (the window START date is recorded in the plan spine's completion stamp)"*. The stamp exists — `docs/development/plans/archived/2026-08-19-plan-1-kaizen-m1-event-stream/…md:303-308` — and records a RULE, not a date, because it was written while the cron was still uninstalled. The origin is in `~/.claude/kaizen.log`: first cron-driven run `2026-08-22T15:27:01`. Conclusion unchanged, evidence now provable. |
| R5 | `cost_usd` is a usable numerator | **It is 85% empty.** Of 102 ledger rows, `cost_usd` is missing or null in **87**; 9 of 14 commands sum to zero; 17 rows carry no `rounds`. `Σcost_usd ÷ Σrounds` would render a fabricated `0` for most commands — the exact anti-pattern this spec praises kaizen for refusing. |

Every number in the draft was also stale within a day (R6–R17: ledger 68→102 rows / 34→35 keys, `CLAUDE.md` +3,587 B, `close-feedback.md` +1,108 B, three line anchors drifted, the kaizen-log claims overstated, the byte-delta range misidentified). Corrected throughout, and the citation convention above is the durable fix.

## The delta (as it stands after round 1)

| # | Item | Status after review |
|---|---|---|
| D1 | The D-175 feedback ledger as kaizen series | **SURVIVES, halved** — two reciprocally paired series, not four (Q2) |
| D2 | Governance weight | **REFRAMED** — not a gap in v2 but v2's own unbuilt guardrail; the unit is a supersession question, not a free choice (Q4) |
| D3 | The M1→M2 gate is MET and untriggered | **SURVIVES, strengthened** — condition (a) met 2026-08-29, provable from the cron log |
| D4 | The OBSERVER + per-usage improvement (operator, 2026-09-11) | **ADDED, and reshaped by evidence** — three of the four design choices are contradicted by measured research; see § D4 |

`grep -c` against v2 for `feedback`, `close-out`, `confusion:`, `waste:`, `cost_usd`, `tok_in`,
`seats`, `command-feedback` = **0 each across all 588 lines** (re-run by the review seat). The forward
direction of the delta claim holds: the D-175 ledger shipped 2026-09-07, three weeks after v2
converged, and is uncovered by any spelling. It was the REVERSE direction — does v2 already register
what D1 proposes — that failed, as R1/R2 record.

## D4 — the OBSERVER, as the evidence supports it (operator-requested 2026-09-11)

**The ask, verbatim:** every agent, while working, assigns a subagent as an observer whose duty is to
utilise kaizen/feedback and judge the run on eight axes — lean · fast executable · accurate · no token
waste · continuous improvement · infra aware · rules aware · manifesto aware — recording the verdict so
the hub improves commands and skills **after each usage, not weekly**.

**The pattern has a name:** *Agent-as-a-Judge* — a judge that reads the whole trajectory, not the final
output. Not evaluator-optimizer (that loops back into the same run) and not LLM-as-a-judge (one output).
The specific composition asked for — a judge writing telemetry that later rewrites the agents' own
instruction files — has **no established name**, which is itself a result.

### Three parts of the ask the evidence contradicts, stated plainly

| The ask | What the evidence says | Measured here |
|---|---|---|
| An observer on **every** run | **Nobody runs one at 100%.** Production accounts sample **1–10%** and gate the judge behind free deterministic signals | One seat/close = **7.3%** of all tokens on this ledger (1,390 seats, mean 15,376 tok) — but see the next row |
| **Eight** axes | The exact configuration measured to collapse: *"factor correlations above 0.93 … supposedly distinct criteria behave interchangeably, reducing the evaluation to a near-unidimensional signal"*, with **>90% unexplained variance** | Eight numbers would be one number wearing eight labels |
| Improve **after each usage** | Deming's funnel: adjusting from single readings *increases* variance. Peeking inflates false positives to **26.1%**. DSPy's own optimisers propose on a minibatch and promote only on a **full validation pass** | — |

And one the ask does not mention but the evidence forces: **a single observer call is not a verdict.**
*"pairwise preferences flip on average 13.6% of the time"*, *"44.7% is within-question noise"*, and
*"A single trial achieves only 86.6% consensus fidelity … 95% requires 11 trials."* At 11 trials the
measured 7.3% becomes **~80% overhead**. A one-call observer is cheap and unreliable; a reliable one is
unaffordable. That is the finding that reshapes the design.

Two further hazards, both live for us specifically:
- **Self-preference.** This would be Claude judging Claude: *"an LLM evaluator scores its own outputs
  higher than others' while human annotators consider them of equal quality"*, with a measured linear
  correlation between self-recognition and self-preference.
- **The loop makes the observer a reward model.** Feeding verdicts back into instruction files is
  reward-model optimisation, and *"optimizing its value too much can hinder ground truth performance,
  in accordance with Goodhart's law."* "Lean" is a length metric an agent satisfies by writing **less**.

### What our own ledger says — the half of the ask that is already solved

| Axis | Mentions across all self-reported close-out feedback (107 closes) |
|---|---|
| rules | 29 |
| token / lean / infra | 10 / 6 / 3 |
| **accuracy · manifesto · continuous-improvement** | **0 · 0 · 0** |

**91 of 107 closes already report substantive waste, unprompted** — specifically, e.g. *"two gate runs
red on siblings' in-flight files — ~4 min re-attributing reds that named no file of mine"*. An observer
would not add much there. What agents never report is the three judgement axes — which is exactly what
a self-assessor structurally cannot do.

And the 8th axis is **unwired**: `docs/reference/operating-manifesto.md` is cited by **0 of 36** command
sources, **0 of 77** enforcement checks and **0 of 56** rule packs — only by the two `CLAUDE.md` files.
Its own § Binding is titled *"how the gates become machine-checkable"*, and nothing ever machine-checked it.

### The design the evidence supports

Three tiers, cheapest first — *"Can a script check it? Then don't use an LLM at all."*

1. **DERIVE, never judge** — lean · fast · no-token-waste · continuous-improvement. All four are already
   exact fields in the ledger (`tok_*`, `wall_s`, `rounds`, `cost_usd`, `seats_*`). Judging a number we
   already record is strictly worse than reading it, and *"conflating 'was it right' with 'was it cheap'
   is one of the fastest ways to produce a meaningless number."*
2. **SELF-REPORT, already working** — waste · confusion. 85% coverage, rich and specific, zero marginal cost.
3. **JUDGE, on the flagged minority only** — accuracy · rules · manifesto. Anomaly thresholds on tier 1
   select the runs; the judge sees **5–10%**, uses **2–3 concrete binary criteria each in its own call**,
   and is validated against a small hand-labelled set with **chance-corrected kappa** before any verdict
   is trusted. ⚠️ Raw agreement would overstate discriminative power by **33–41 percentage points**.

**Targeting, measured:** the observer's cost is wildly uneven and inverts in our favour —
`fabrik-execute-plan` 522,376 tok/close → **2.9%**; `fabrik-review` → 4.4%; `fabrik-spec-review`
176,437 → **8.7%**. It is cheapest exactly where runs are longest (477 min mean) and waste densest, and
dearest where a fifth of runs already report no waste at all (`fabrik-review-scoped`, 27 min).
**A flat per-run observer is the worst available policy.** Attach it to expensive runs.

### Cadence: batch-and-gate, never per-usage or auto-applied

*"Improve after each usage"* is not supportable as stated, and the failures are documented, not
hypothetical: **Knight Capital** (~$440–460M in 45 minutes; the SEC cites *"the absence of a 'kill
switch'"*) and **Zillow Offers** (>$500M, a model acting on its own live noisy signal at speed). Google
SRE: *"a majority of incidents are triggered by binary or configuration pushes."* Netflix, at hundreds
of thousands of judgments a week: *"An LLM judge must never operate alone. It has to be anchored in
human judgment"* — and a human approves every rubric change.

So: **propose continuously, promote on a batch, apply through review.** An edit to a fleet-synced
instruction file reaches ~46 repos; Constraint 1 already forbids an agent applying it unreviewed, and
nothing in the research argues for relaxing that.

⚠️ **The N is an engineering choice, not a researched number.** Shewhart's floor (*"not less than
twenty-five samples of size four"*) is for physical process control. **No published work measures
cadence or minimum-N for fleet-distributed agent instruction files** — that composition (fan-out blast
radius × noisy per-repo signal × propagation irreversible until noticed) is unmeasured anywhere. Any N
we pick is ours to defend, and per Q2 it should come from the M1→M2 sign-off, not from this spec.

### Does bloat actually hurt? — the honest strength judgment

**Strong (peer-reviewed):** *Lost in the Middle* — *"performance … significantly degrades when models
must access relevant information in the middle of long contexts, even for explicitly long-context
models."* Directly relevant to appending rules into a growing corpus.
**Suggestive (fresh preprints):** follow rate *"falls from ~96% to as low as 20%"* from 1 to 20 stacked
instructions, and *"no error is raised when an instruction is dropped"*; reliable following *"breaks
down beyond 5–6 simultaneous constraints."*
⚠️ **The limit, quoted so it is not lost:** *"Do not cite these as proof that 22 KB of added rules
measurably degraded this repo's agents — that specific causal claim is NOT evidenced."* The mechanism is
plausible-and-general, not measured-and-specific. D2 is justified as stopping **unmeasured** growth.

## Ground truth (re-derived 2026-09-11)

### The three stores

| Store | Path | Holds | Size |
|---|---|---|---|
| Run record | `~/.claude/state/command-runs/<sid>.json` | `feedback_text` (full prose), `feedback`, `feedback_to`, state/rounds/phases/agent/surface/account/usage | **26** run records (+26 `.lock` files; the 52 in the draft counted both) |
| **Feedback ledger** | `~/.claude/state/command-feedback.jsonl` (path from `command_run.py::_feedback_ledger_path`) | the four prose fields + repo, agent, surface, account, wall_s, rounds, findings, `cost_usd`, `tok_*`, `tok_seat_*`, `seats_*`, `models` | **102 rows, 35 keys** |
| Event stream | `~/.claude/state/events/<sid>.jsonl` | `run_close` with `verdict` + a **one-word** `feedback`. **No prose.** | 38,317 files |

### Who reads what

- `kaizen_collect_v2.py` (143,273 B — **the live collector**; `kaizen_collect.py` at 17,193 B is not
  what the cron runs, per `weekly_catchup.sh`'s `case` dispatch) reads the **event stream** and buckets
  `row.get("feedback")` into `fb_filed`/`fb_none`/`fb_unstated`, counting anything else as
  `unknown-feedback-verdict` — *"an instrument defect, counted, never bucketed."* **It never reads the
  ledger** (`grep -c command-feedback` = 0).
- `feedback_relay.py` reads the **run records**, watermarked, mails one digest to `fabrik`/`infra`;
  rides the kaizen cron slot as a non-fatal rider in `weekly_catchup.sh` (cron `27 * * * *`).
- `command_feedback_report.py` reads the **ledger** and is scheduled by **nothing**
  (`crontab -l | grep -c feedback_report` = 0).

### The instrument is mature — extend it, never rebuild it

`kaizen_collect_v2.py` already provides, and this delta inherits rather than restates: versioned
series (`~/.claude/state/kaizen/series/<metric>@v<N>.jsonl`, 16 live data files, *"a published series is
never overwritten"*); `def_hash`; honest absence (*"unmeasurable renders `—` with its reason … never a
fabricated 0"* — observed live, `death_occurrences` flipping to `[NOT MEASURED]` rather than `0`); the
single-source law; a noise floor (`noise-floor@v1.md`, regenerated by `kaizen_backfill.py --report`);
and — the one R1 exposed — a **registry validator that refuses unpaired metric definitions**.

### D3 — the gate is met, and here is the provable chain

`docs/workstation/kaizen.md`: M2 opens only after (a) **7 days of daily event collection from the
cutover's first daily cron run**, and (b) **variance sign-off**; *"the gate review is a named
operator-triggered follow-up."*

| Condition | Evidence | Verdict |
|---|---|---|
| (a) 7 days from the cron cutover | The archived M1 plan spine records the RULE (the window starts at the first cron-driven run) because it was written pre-cron-restore. `~/.claude/kaizen.log` gives the origin: **first cron-driven run `2026-08-22T15:27:01`**. Series publish every day from 2026-08-25 → 2026-09-09 (16 consecutive; one gap day, 2026-08-23, before that). | **MET — 2026-08-29** on the plain reading, **2026-08-31** if "daily" is read as consecutive-across-all-series. Either way, met before this spec was written. |
| (b) variance sign-off | `noise-floor@v1.md` dated **2026-08-20**, corpus *"0 event-era session(s)"*, 16 rows all `—` at n=0 weeks. | **NEVER RUN** |

Consequence: `premature_stop_rate` has moved **43% (131/304) → 55% (254/463) → 71% (926/1306)** across
09-07/09-08/09-09 and **none of it can be adjudicated**, because the instrument built to say whether a
jump is signal or Tuesday has never been populated. ⚠️ Causality is NOT established — the denominator
quadrupled over three days, which is itself the kind of thing a variance sign-off exists to separate
from a real regression.

### The analyst half

The kaizen logs' `Top friction fixed` column is empty in all **5 infra** rows and in **4 of 6 fleet**
rows — each log's 2026-08-12 row carries the same `(baseline row — first real pass fills metrics)` annotation, which is a placeholder, not a finding. `Filed` is NOT empty —
3 of 5 infra rows carry real counts (`18 filed / 9 none / 17 unstated` … `327 filed / 2059 none / 0
unstated`). Fleet's log carries **two** substantive analyst entries: 2026-08-19 (the crontab-wipe
finding, Lesson 128) and 2026-09-06 (the relief-wake finding, which became D-177/D-178/D-180).

The honest statement: the MECHANICAL cells fill daily, `Filed` fills often, and the **judgement** cell
— `Top friction fixed` — has been filled **exactly twice, both by fleet, and never by infra**.

⚠️ This paragraph is kept as written evidence of a failure mode, because the draft got it wrong twice
in opposite directions: it first claimed "`—` every time / exactly one entry" (overstating absence),
and the round-1 rewrite then ADDED the two correct entries while leaving the old absolute standing and
writing a NEW false one ("never been filled by anyone"). A half-rewrite that corrects by appending is
how a document comes to refute itself in six lines.

### Corpus weight, as supporting evidence (not as the metric)

| Surface | Bytes |
|---|---|
| `CLAUDE.md` | 89,214 — read every session |
| `commands/_sources/` | 1,042,530 over 36 files |
| `.windsurf/rules/` (`.md`) | 1,251,876 over 56 files |
| `commands/_fragments/close-feedback.md` | 10,485 |

Across infra's review-family range `0fcafed5^..a1b2509f` (T01 → Finish; **57** files, not the 52 an earlier draft wrote — 48 is the T03-anchored count, i.e. the range this sentence itself calls wrong), the corpus-surface subset grew **≈ +22.3 KB over 7 files** — not the draft's
"≈ +19 KB", which sampled five files and missed `subagents-core.md` (+2,306) and
`fabrik-repo-review.md` (+1,081). The draft also misidentified the range (it began at T03, not T01) and
its file count (48, not 52). ⚠️ These bytes are EVIDENCE that governance text grows unwatched; they
are **not** the metric v2 specified, which is transcript-injected tokens per median session (R3).

## The six design questions

### Q1 — One store, or a declared derivation?

**Settled: a declared derivation, with the LEDGER canonical for close-out feedback.** Not a migration.
The ledger is already box-wide, already richest, already written atomically at close; the event stream
stays canonical for events; the run record stays live in-flight state. Only ONE reader is added.

Rejected — **unify into one store**: it would rewrite 38,317 event files or 102 ledger rows to
back-fill history never captured, which is the fabrication the instrument's honesty rule forbids.
**Migration answer: none.** Series start the day the reader ships, `era` recorded.

### Q2 — Which series, and the minimum-n rule

**Settled: TWO series, as ONE reciprocal pair** — because the registry validator refuses anything else
(R1), and because two of the draft's four were a duplicate (R2) and a fabricated zero (R5).

| Series | Definition | Role |
|---|---|---|
| `command_tokens_per_round@v1` | Σ(`tok_in`+`tok_out`) ÷ Σ`rounds` **over rounds-carrying rows ONLY** — a row with `rounds == 0` contributes to NEITHER side. Emits `rows_with_numerator` AND `rows_with_denominator` per command; renders `—` per the mass rule in Q5 canary 4 | **driving** — D-203's delta-round rule predicts this FALLS; the loop's first self-test |
| `feedback_substance@v1` | closes whose `change:` is **> 40 characters AND matches `/fabrik-[a-z0-9-]+` or a path bearing a `.py .md .sh .ya?ml .json .toml` extension or a named rule pack** ÷ all closes | **counter** — guards the Goodhart: tokens must not fall because agents said LESS. Measured on the live ledger with THIS predicate: **40 of 102 (39.2%)** |

⚠️ **Both definitions are the round-2 versions, and the round-1 versions were unsound.** They are
recorded because each failure is the spec's own stated defect class reappearing one step to the side:

- **The denominator, not just the numerator.** R5 killed the cost series for a sparse NUMERATOR. The
  round-1 tokens definition then summed tokens over ALL rows while dividing by Σ`rounds` — and
  `command_run.py` writes `rounds` as a count of `round` sub-command calls, so a command that never
  calls `round` records 0 while still burning tokens. Measured: **15 of the 17 zero-round rows carry
  tokens, 24.2% of all token mass** (at 102 rows), and `fabrik-plan-after-chat` rendered **1,139,788 tok/round** off
  Σrounds = 1 — a plausible-looking figure thirty times the well-populated commands, with no `—` and no
  reason. The round-1 guard only fired when a command had *no* rounds-carrying close at all, and
  canary 4 guarded only the numerator. Same anti-pattern, other side of the division bar.
  **And excluding those rows is not sufficient on its own** (which is why Q5's mass rule, not a row
  count, is the guard): `fabrik-plan-after-chat` has four
  zero-round closes (168k/252k/64k/509k tokens, real multi-hour runs) and ONE rounds-carrying row, so
  the exclusion alone would discard **87% of its token mass** (at 102 rows) and publish that single row — 146,223
  tok/round, ~3.6× the best-populated command (`fabrik-review`, 40,434 tok/round — executed at 102 rows) — with the `—` guard unable to fire because 1 ≠ 0. For a
  command whose lifecycle has no round semantics the quantity is **category-inapplicable, not sparse**,
  which is why Q5's mass rule renders `—` instead of a figure from the one exception.
- **A presence predicate is not a substance measure.** The round-1 counter was `change: ≠ none`, which
  an agent satisfies by cutting `change:` from its 248-character median (mean 247) to five characters — the
  *cheapest* response to a token-reduction drive, and invisible. Worse, the 101-of-102 saturation is
  largely an artifact of enforcement: `command_run.py`'s usage-field check refuses a close missing any
  field, so the metric was measuring gate compliance. The self-audit's original explanation ("too
  little variance to detect gaming") was the wrong mechanism — low variance makes a drop in the
  `none`-rate *easier* to see against the floor, not harder. The defect was the predicate.

`counter_metric` is declared **reciprocally** in both definitions, or they do not load. ⚠️ **And the
schema is a floor, not a guard** — the research is explicit that *"a guardrail can veto a launch; it can
never justify one … the moment a guardrail can justify a launch it has become a second primary metric"*.
The registry enforces that a pair EXISTS and is reciprocal; it cannot enforce that the counter actually
guards, nor that its authority is asymmetric. So this spec states what the schema cannot:
**`feedback_substance` may only VETO — it can stop a tokens-per-round improvement from being credited,
and may never on its own justify one.** The pairing is causally coupled (the cheapest way to cut tokens
is to say less, and saying less is exactly what the counter measures), which is the test the literature
applies; whether it holds in practice depends on the substance floor being graded rather than a bare
presence check — the documented failure being a binary completion metric that rose 18 points while the
construct it stood for never moved. Verified by
execution against the live validator: the two ids do not collide with the 16 registered metrics, and
`registry + the new pair` loads at size 18.

DROPPED from the draft, with reasons: `rounds_to_converge` — duplicates `review_rounds@v10`; a
per-command view is a **dimension on that series**, not a new metric id, and belongs in a proposal to
its owner. `command_cost_per_round` — `cost_usd` is missing or null in 87 of 102 rows and sums to zero
for 9 of 14 commands; the D-203 cost prediction is therefore graded in TOKENS, which are present in
89 of 102 rows.

**Minimum-n: UNRESOLVED, and deliberately not invented.** The draft asserted "n ≥ 4 weekly points"
with no derivation; the review confirmed none exists — `kaizen_backfill.py` computes
`statistics.pvariance` for any n ≥ 1, and `n=1 ⇒ variance 0.0` is an algebraic identity, not an
adequacy floor. `grep` for any n-threshold across `kaizen.md` and the kaizen scripts returns nothing.
**The honest rule: a series publishes from day one and fires NOTHING until the noise floor is
regenerated and its variance-vs-n curve inspected.** The threshold is an output of the M1→M2 sign-off
(D3), not an input this spec may guess. Until then every series renders with its n and no verdict.

### Q3 — The change-queue state machine

**Settled: do not build one.** v2's M2 "finding registry + tested selection policy + fix ledger" IS it.
This delta contributes one clause v2 leaves open:

> An applied change declares, **in its fix-ledger row**, the series it expects to move and the
> direction. Once the noise floor exists, the change is graded against that series' variance. A change
> whose series did not move beyond the floor is **REVERTED**, and the revert is itself a fix-ledger
> row, never a silent rollback.

The review's one open point is answered above by naming the location (the fix-ledger row); the
grading threshold is deferred to D3 for the same reason as Q2's n.

### Q4 — Governance weight: v2's unit was RIGHT; adopt it, do not supersede it

**Settled by the research, and against my own earlier draft.** v2 specified the guardrail in
*"total injected governance tokens per median session — **measured from transcripts, not from disk**"*.
An earlier draft of this delta proposed disk BYTES instead and rejected tokens on the merits without
citing that v2 had already adjudicated it. The evidence backs v2:

- Tokenisation is **(request, model)-scoped**: a measured case billed 246,525 vs 196,892 input tokens
  for a body 0.3% *larger* — a 20% swing from model choice alone.
- Content type breaks the byte→token ratio by ~2×: markdown tables and code fences (our corpus) sit at
  the dense end versus prose.
- Prompt caching *"only applies to a leading prefix that is identical byte-for-byte"*, so a mid-file
  byte increase can silently break caching downstream — a cost effect bytes cannot see at all.

**So: no superseding D-row is needed.** The honest resolution is to BUILD v2's guardrail in v2's unit —
tokens counted with the serving model's own tokeniser — and keep **bytes only as the free, CI-native
trend signal**, never as the enforced ceiling. What was genuinely missing is not the design but the
build: `grep -rc "governance_mass" scripts/` = 0.

**The escape hatch needs no new machinery** — this is the other thing the research settled, and it is
simpler than the earlier draft's proposal. Every real ratchet (Betterer, ESLint bulk suppressions,
SonarQube, suppress-ratchet) stores its ceiling as **a single committed number**. Single-use binding
then comes free from git: raising it is one diff, one PR, one review, and the mechanism has no memory
beyond the number currently committed, so it *cannot* grant open-ended future increases. The earlier
draft's worry — that a D-row would permanently authorise growth — was a problem I invented by proposing
prose where the field is a number.

Two documented failure modes to design against, both real:
- **Re-baselining upward.** A live PR exists *specifically* because a single-gate ratchet *"could be
  defeated by a PR that regresses the code AND re-baselines upward"*; the fix was a second gate
  comparing per-rule counts against the base branch. Our check needs that second gate.
- **Baseline drift.** ESLint warns on suppressions that no longer occur and ships `--prune-suppressions`;
  unpruned entries become dead exemption debt.

Expiry (forcing re-justification with age) is a *separate* concern that only compliance-grade tools add;
none of the pure ratchets do. Out of scope here, named so it is not re-derived.

### Q5 — Instrument canaries

Most of this already exists (versioned series, `def_hash`, `—`-with-reason, `unknown-feedback-verdict`).
Three gaps remain, each from a failure hit while grounding this spec, plus a fourth the review added:

1. **Wrong-version-live.** Two collectors exist and only one runs; reading the wrong one produced a
   confidently wrong conclusion. → the collector asserts it is the file `weekly_catchup.sh` dispatches.
2. **A bounded read returning zero silently.** `cat ~/.claude/state/events/*.jsonl` over 38,317 files
   exceeds `ARG_MAX`; the pipeline returned nothing and read as "0 events". → every reader over that
   store reports the file count it actually opened beside any count, so a zero carries its denominator.
3. **Categorical-where-prose-exists.** Kaizen buckets a one-word verdict while prose sits in the
   ledger. → D1 closes it; the canary is `ledger_rows_seen` emitted beside every derived value.
4. **NEW (R5) — a sparse numerator read as a real zero.** A ledger column that is optional per command
   (`cost_usd`: 87 of 102 rows empty) makes a sum look like a measurement. → any ledger-derived series
   emits, per command, the count of rows that carried its **numerator** AND the count that carried its
   **denominator**, so a zero always carries its denominator.
   **THE MASS RULE, and it is the whole rule** — a series renders `—` with its reason unless the rows
   carrying BOTH sides account for **≥ ⅔ of that command's token mass** — and a command whose total
   token mass is 0 renders `—` by the same rule, the ratio being undefined (11 ledger rows carry
   `rounds` with no tokens; for `test_cmd` that is its only row, so a bare ratio raises
   `ZeroDivisionError`). Measured on the live ledger:
   ⚠️ **No per-command percentage is quoted here, on purpose.** Earlier drafts pinned six of them and
   they went stale three times in one review — including from closes the review itself generated: the
   ledger grew 102 → 104 rows mid-run and `fabrik-spec` moved from 66.2% to **54.0%** when one
   non-rounds-carrying close landed. A spec that cites a live-ledger ratio is citing something that
   moves faster than the document. Re-derive instead, per command:
   `q = Σ tokens over rows with rounds>0 AND tokens>0`, `T = Σ tokens over all rows`, publish when
   `q/T ≥ ⅔`, else `—`. A command at `q/T < ⅔` needs one qualifying close of `x ≥ 2T − 3q` to flip —
   **three times the static deficit `(⅔)T − q`**, because a new qualifying close grows BOTH sides.
   Reasoning from the static deficit understates the flip by 3× and is the error this clause replaces.
   **Why ⅔ and not ½ or ¾ — the gap, not the constant.** Executed 2026-09-11 at 104 ledger rows,
   every command's `q/T` is either **≤ 0.540** (3 commands) or **≥ 0.9339** (10), with nothing in
   between: any threshold in `(0.541, 0.933)` yields identical verdicts. ⅔ is a conventional
   supermajority sitting inside that empty gap, so the choice is insensitive — which is the honest
   justification, and the thing to RE-DERIVE is the gap, never the constant. ⚠️ If a later
   re-derivation finds the gap has closed, the threshold becomes a real decision and inherits Q2's
   minimum-n discipline: it is then an output of the M1→M2 sign-off, not a number this spec may keep.
   ⚠️ This ONE rule replaces three that earlier rounds scattered (a zero-numerator guard here, a
   zero-denominator guard here, a row-count MINORITY rule in the Q2 table). Each round added a rule
   and left the others un-updated; worse, the minority rule was ARGUED from discarded token mass and
   IMPLEMENTED on row count, so `fabrik-execute-plan` published while discarding 66.5% of its mass (at 102 rows) and
   `fabrik-spec` was silenced at a smaller loss. Mass is the quantity the argument was always about.
   Constraint 3 makes this section normative, so the rule lives HERE and Q2 cites it — never restated.

**Reconciled against D6 of `2026-09-10-review-family-adoption-design.md` — DISJOINT, no shared
mechanism owed.** D6 extends `check_review_hygiene.py` with `table-parity`; its `_surface_hits` gates
every class on `path.endswith(".md")`, so D6 grades **markdown text**, while these canaries grade
**data**. Neither can run on the other's medium. They share one law — D6's `dead-symbol` and canary 2
are both **denominator honesty**, a zero meaning "not found in N" read as "does not exist". Siblings,
never duplicates to merge.

### Q6 — Fire rate before shipping (FIX DIRECTIVE 5, binding)

Before any weight check moves from ADVISORY to blocking, replay it over the last 30 days of commits
and record what it would have fired on. Partly known already: infra's review-family range would have
fired on at least 7 corpus-surface files. If the measured rate makes it wallpaper, **narrowing or
rejecting it is a valid recorded outcome** — a D-row, not a silent removal. Same discipline for both
series: publish first, fire never, until the floor exists.

## fabrik-lib verdict: BUILD (nothing to vendor), ENHANCE the hub's own collector

Audited against the live module table (`/opt/fabrik-lib/README.md` § Modules — count it with the
producing command, never from this page: an earlier draft wrote "85 modules", which was the table's
last LINE NUMBER read as a count, in a spec whose own banner exists to stop exactly that). `observability/` is logging + Sentry/GlitchTip;
`request-metering/` is per-request live-service telemetry on `db-pool`; `cost-budget/` is spend caps
and reservation; `app-audit-log/` is a hash-chained audit trail; `claude-evaluator/` is scored batch
evaluation; `watchdog/` is a per-project sidecar on SQLite. None implements box-local JSONL→series
analytics with versioned series, `def_hash`, weekly aggregation and a noise floor.

**The correct reuse is internal**: `kaizen_collect_v2.py` already is that engine. D1 is a reader added
to it. A second metrics store beside it would create the fragmentation this delta exists to remove.

## Approaches considered

**A — Activate first, build second (RECOMMENDED).** Trigger the M1→M2 variance sign-off, then ship
D1's paired series and, on the operator's unit ruling, Q4's check — both advisory.

⚠️ **Cost, corrected.** The draft called this "near zero to start"; that was true only of the
activation half and the review was right to confirm it as an overclaim. Honestly: the **sign-off** is
one command plus a review — but the regeneration must cover the **16 registered metrics at their
current versions**, not the 8 at `@v1` the present file holds (`kaizen_backfill.py::_full_registry`
says the floor *"must cover every registered metric"*, and the file on disk predates the outcome tier —
it holds **8** metrics all at `@v1` while the live registry holds **16** at `v1`–`v10`, with the def-hash
differing for all 8 and 8 live metrics absent entirely). ⚠️ The draft attributed this to the
function's fail-open branch; that branch is NOT active (it returns 16 with no warning). The staleness
is chronological, not a degradation. The **build** half — a ledger reader, two paired series with honest-
absence canaries, a new enforcement check, its baseline, a bindable escape hatch, a 30-day replay,
tests and docs — is real, unestimated engineering. Not free because the collector exists.

**B — Build the series first, activate later.** Rejected: it adds unadjudicable series to a loop whose
adjudication half is already stalled — more recorded, still not evaluated, the exact failure named.

**C — A full new closed-loop mechanism.** Rejected on sight once v2 was read: forks a converged design
and re-implements M2.

**Recommendation: A**, and the review strengthens it — the draft's own build half shrank from four
series to two, so activation is now an even larger share of the available value.

## Who builds what

| Item | Owner | Rationale |
|---|---|---|
| M1→M2 variance sign-off (D3) | **operator-triggered** | `kaizen.md` names it a *"named operator-triggered follow-up"* — not an agent's call |
| The Q4 unit ruling (build v2's tokens, or supersede with a D-row) | **operator** | It reverses a converged adjudication; no agent should do that silently |
| D1 — ledger reader + the paired series | **infra** (kaizen is their beat) — **fleet may build it** if infra's queue makes that slower | infra holds 64 of 65 `ack=required` items |
| Q4's check, if the unit ruling is bytes | **fleet**, infra reviews | New file; fleet holds the measurements |
| `rounds_to_converge` as a DIMENSION on `review_rounds@v10` | a proposal to that series' owner | R2 — never a new metric id |
| M2's finding registry / fix ledger | **infra**, per v2 | Already theirs; this delta adds only the verification clause |

## Constraints (binding)

1. **Never auto-edit a fleet-synced governance file.** The loop PROPOSES with evidence; a session
   applies through the normal review path. A bad edit to `CLAUDE.md` or a rules pack reaches ~46 repos
   before anyone reads it.
2. **Zero command-file changes — and the claim is now narrower.** The close-out contract is
   single-sourced in `commands/_fragments/close-feedback.md` (10,485 B), appended to all 36 commands by
   `assemble_commands.py`. Agents already emit the columns these two series read — with `rounds` **present but 0** (never absent **by construction** — `command_run.py` writes `"rounds": len(rec.get("rounds") or [])`, always an int; a builder coding to "absent" writes a branch that never fires) for
   commands whose lifecycle has no round semantics (17 of 102 rows carried `rounds == 0` when measured, 15 of
   them holding 24.2% of all token mass — re-derive, the ledger grows: `rounds == 0` rows ÷ all rows), which Q5's mass rule handles with `—` rather than a fragment edit. The draft's broader
   claim — "everything these series need" — was false for `cost_usd` (R5), which is why that series is
   dropped rather than patched. No fragment edit is required for D1 as scoped.
3. **Every new metric ships with a canary** that fires when its own input goes missing — never a
   silent 0 (Q5).
4. **No series fires anything until the noise floor exists** (Q2); the threshold comes from the
   sign-off, not from this spec.
5. **Nothing in `~/.claude/state/` is written by a review of this spec** — regenerating the noise floor
   IS the operator's M1→M2 sign-off, and an agent running it would forge the evidence.

## Lifecycle

- **D3 first, and it is not code.** Until the sign-off happens, every series is publishable and
  unadjudicable — today's state.
- **D1 then Q4.** D1's series publish from the day the reader ships, `era` recorded, back-filling
  nothing. Q4 waits on the operator's unit ruling.
- **Graded by its own first prediction.** `command_tokens_per_round` exists to test D-203's claim that
  delta rounds lower cost per round. If it does not fall, the prediction was wrong and the series
  earned its keep by saying so.
- **Extends v2, never supersedes it.** A conflict is resolved in v2's favour unless a D-row says
  otherwise — which is exactly what Q4 now requires.

## Open — needs the operator, not derivable here

- **The Q4 unit**: build v2's transcript-token guardrail, or supersede it with a D-row and measure disk
  bytes. (R3 — the draft chose without noticing it was choosing.)
- **Sequencing vs the held fleet sync.** Infra's Finish HELD the one forced
  `sync_enforcement_to_projects.py --force` pending trade-intelligence's receipt repair
  (`01M23G21EBSS4BC187HQ7PS02X`; wef repaired at `edcb7e6d`). `scripts/enforcement/` is a
  governance-sync TRIGGER surface. This spec does not decide it and no run of it will force the sync.
- **Whether seat/model/cost series are kaizen's or intel's.** Asked intel
  (`01M25E4SRWVYFBC4R48ANW7Z3W`); unanswered. Moot for the two series now scoped, live again if a cost
  series returns.

## Self-audit — where this spec could still be wrong

- **Two of three original deltas were refuted at the premise in round 1.** That is recorded in § What
  round 1 refuted rather than smoothed away, and it is the best evidence that the remaining claims
  deserve the same treatment.
- **The pairing of `command_tokens_per_round` with `feedback_substance` is MY judgement, unexecuted.**
  The registry enforces that a pair exists and is reciprocal; it cannot check that the two metrics
  actually guard each other. If tokens-per-round and substance turn out to be uncorrelated, the pair
  satisfies the validator while guarding nothing.
- **`feedback_substance`'s saturation is fixed; its PREDICATE is the residual risk.** Under the old
  presence test the metric sat at 101 of 102 (99.0%) — useless as a counter. Under the Q2 predicate it
  measures **40 of 102 (39.2%)** on the live ledger, so the de-saturation works. What remains is that
  the length floor is nearly inert (it excludes only the single 4-char `none` row) while the
  names-a-file clause does all the work — and a looser or stricter reading of that clause moves the
  published rate materially: requiring a directory separator drops it to **28.4%** (measured). ⚠️ An
  earlier draft cited two further variants (41.2%, 63.7%) that do not reproduce against the ledger and
  were residue of a discarded computation; they are deleted rather than re-derived. Q2 now states
  both halves concretely for that reason. ⚠️ An earlier draft of this bullet blamed "too little
  variance to detect gaming"; that was the wrong mechanism and is recorded in Q2 as such.
- **The D3 conclusion survived but its evidence changed completely.** Condition (a) is met from the
  cron-log origin, not from series line counts. If `~/.claude/kaizen.log` has been rotated or
  truncated, the origin date is unverifiable and the "met 2026-08-29" claim loses its proof while
  remaining probably true.
- **The corpus byte figures will be stale again within a day.** They are supporting evidence, not a
  metric, and the citation convention at the top is the only durable part.

## BLOCKED: NON-CONVERGENCE — LIFTED 2026-09-11

**The blocker was the 1c approach floor, and it is cleared.** Four parallel `fabrik-researcher` seats
grounded the approach space on 2026-09-11; § External facts and the approach floor lists 12 distinct
cited URLs against a floor of 2. The earlier § External facts claim ("this design has no external
facts") was wrong in exactly the way the checker's comment predicts, and is withdrawn.

**The stall series is also explained rather than merely survived.** Confirmed defects ran
`17 · 5 · 5 · 4 · 3 · 1 · 2 · 4` across eight rounds, and rounds 6–8 tripped the breaker. The
foundation error named then still stands and is now fixed at the root: **a static document was carrying
live measurements of a shared, moving system.** Every remaining figure either carries its producing
command, is stamped with the row count it was measured at, or is a past-tense record of an earlier error.

**What the research changed, beyond clearing the floor** — three findings reversed decisions this spec
had already made, which is the strongest argument that the floor was worth enforcing:
1. **Q4's unit**: v2's transcript-tokens adjudication was RIGHT and this delta's disk-bytes proposal was
   weaker. No superseding D-row; adopt v2's unit.
2. **Q4's escape hatch**: needs no new machinery — a committed number gets single-use binding free from git.
3. **Q2's counter**: needs VETO-ONLY authority, which the registry schema cannot express.

Superseded verdict, kept for the record: the spec was BLOCKED at round 8 pending an operator ruling on
whether to do the approach research or exempt the delta. The research was done.

