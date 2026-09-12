# Kaizen feedback loop — a DELTA on the converged closed-loop v2 spec

Status: DRAFT — BLOCKED: NON-CONVERGENCE twice, both times on the same PROCESS error rather than on the
design: the same session wrote every fix its own fresh seats found (the wording residue of rounds 13–15,
with infra at `01M28VKD807M6QZB31NJ5D9W1T`; then the amendment ledger of rounds 16–23). The design
content has held under execution since round 20. The 1c approach blocker that blocked rounds 6–8 is
CLEARED, and the operator RULED the loop approved on 2026-09-11 (**D-224** — they own the goal, the
mechanism is derived from measurement and is not a menu) and confirmed the re-cut reading of the eight
axes (**D-234**). **The loop resumed at round 24 on 2026-09-12** to close the residue row 23 names
together with three corrections the pieces 3 + 4 work forced, each minted at a different moment of it:
the ratchet's WARN reference, ruled while that plan was being WRITTEN (**D-240**); OWNS-not-HAS with the
six budgeted surfaces, minted at round 2 of its review (**D-241**); and the superseded plan citation,
from that review's close (**D-244**). The fixes were AUTHORED by a separate fixer agent, which is the one
shape both blocks asked for. The round history, the stall-breaker arithmetic and the two foundation errors are in § BLOCKED;
rounds 16+ are in § Amendment review. Nothing in either block changes a build decision.
Date: 2026-09-10 (reviewed 2026-09-11, rounds 1–15; rounds 16 onward are ledgered in § Amendment
review; the R-table records round 1)
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
wrong to. **THIS list is where the approach sources live** — § D4 and § Q4 quote from it; § Approaches
considered carries prose only and no URL, and an earlier draft claimed otherwise, which would have sent
a grounding reviewer to the wrong section. Every figure quoted in § D4 traces to a row here:

- Zhuge et al., *Agent-as-a-Judge* (Meta AI/KAUST) — https://arxiv.org/abs/2410.10934
- Panickssery, Bowman & Feng, *LLM Evaluators Recognize and Favor Their Own Generations*, NeurIPS 2024 — https://arxiv.org/abs/2404.13076
- Feuer et al., *When Judgment Becomes Noise* — https://arxiv.org/html/2509.20293v1 — **factor collapse only**: `>0.93` correlations, `>90%` unexplained variance
- Yagubyan, *The Coin Flip Judge?* — https://arxiv.org/html/2606.13685 — the **13.6%** flip rate, **44.7%** within-question noise, **11 trials** for 95% fidelity. ⚠️ An earlier draft credited all three to Feuer et al., which does **not** contain them (Feuer's own 44.6% unexplained-variance cell for one model is the near-coincidence that produced the misattribution)
- Norman, Rivera & Hughes, *Reliability without Validity* — https://arxiv.org/html/2606.19544v1 — the **33–41 pp** raw-vs-kappa overstatement (not Shankar et al., as an earlier draft had it)
- Shankar et al., *Who Validates the Validators?*, UIST 2024 — https://arxiv.org/abs/2404.12272 — criteria drift, qualitative; carries no kappa figure
- Gao, Schulman & Hilton, *Scaling Laws for Reward Model Overoptimization*, ICML 2023 — https://arxiv.org/abs/2210.10760
- Liu et al., *Lost in the Middle*, TACL 2024 — https://arxiv.org/abs/2307.03172
- Anand & Chattaraj, *Instruction Stacking Collapse* — https://arxiv.org/html/2608.02639 — the **96% → 20%** follow rate and the silent-drop finding
- Vasileva, *Phase Transitions in Compositional Constraint Satisfaction* — https://arxiv.org/html/2608.12426 — the **5–6 simultaneous constraints** breakdown
- Miller, *How Not To Run an A/B Test* (2010) — https://www.evanmiller.org/how-not-to-run-an-ab-test.html — the **26.1%** peeking figure. ⚠️ An earlier draft hung it on the Kohavi frontmatter PDF below, which is a table of contents and cannot carry any figure
- Kohavi, Tang & Xu, *Trustworthy Online Controlled Experiments* (Cambridge 2020) — https://assets.cambridge.org/97811087/24265/frontmatter/9781108724265_frontmatter.pdf — **frontmatter only**; cited for the peeking phenomenon qualitatively, never for a number
- SEC, *In the Matter of Knight Capital Americas LLC*, Release 34-70694 — https://www.sec.gov/files/litigation/admin/2013/34-70694.pdf — the **$460M / 45 minutes** figures and the halt-procedures finding. ⚠️ *"kill switch"* does **not** appear in the order; an earlier draft quoted it as SEC language
- NIST/SEMATECH handbook, Shewhart's minimum-N — https://www.itl.nist.gov/div898/handbook/pmc/section3/pmc32.htm
- Google SRE, *Canarying Releases* — https://sre.google/workbook/canarying-releases/
- Netflix, *The Lifecycle of LLM-as-a-Judge* — https://netflixtechblog.medium.com/the-lifecycle-of-llm-as-a-judge-building-aligning-and-monitoring-at-scale-c95bd8283508 — ⚠️ its *"hundreds of thousands a week"* counts **explanations generated**, not judgments; an earlier draft said judgments
- ESLint, *Introducing bulk suppressions* — https://eslint.org/blog/2025/04/introducing-bulk-suppressions/
- Anthropic, *Building effective agents* — https://www.anthropic.com/engineering/building-effective-agents

⚠️ Vendor docs are labelled as such where cited. No 1a external FACT is relied on: no vendor API,
standard or third-party runtime behaviour determines any mechanism here — **except Q4's**, which the
note at the end of § Q4 states as this spec's one 1a exception rather than leaving this sentence to
cover it.

**SIX citation defects were found and fixed in round 9**, enumerated rather than bucketed (the earlier
tally said "five, three of one kind" and its buckets did not add up):
1. the 13.6% / 44.7% / 11-trials figures credited to Feuer et al., who do not contain them → Yagubyan;
2. the 33–41 pp kappa figure credited to Shankar et al., who carry no kappa figure → Norman et al.;
3. the 26.1% peeking figure hung on a Cambridge **frontmatter** PDF, i.e. a table of contents → Miller;
4. *"the absence of a 'kill switch'"* quoted as SEC language, which the order does not contain → its halt-procedures finding, quoted verbatim;
5. Netflix's *"hundreds of thousands a week"* read as judgments; it counts **explanations generated**;
6. two separate instruction-following preprints cited as one → both named.

They are named rather than silently corrected, because the failure mode — a real number on the wrong
source — survives every check that only asks whether a URL resolves, and eight earlier rounds caught
none of them.

## Reproduce — every load-bearing number in one place

⚠️ **This section exists because the spec had NO fenced probe at all until round 9** (executed: 0 fence
markers across 606 lines), while carrying ~20 live measurements. A figure a reader cannot regenerate is
an ungrounded claim however carefully it was measured. Each command below regenerates the figures cited
against its id; the ledger GROWS, so the row count at the time of measurement is stamped beside every
figure in the text and a re-run is expected to differ.

```
$ L=~/.claude/state/command-feedback.jsonl; wc -l < "$L"
109        # 2026-09-11 18:0x — was 108 forty minutes earlier, and 102 at the Q2 snapshot
```
⚠️ **This probe's output is EXPECTED to differ from the number printed above, and that is the point.**
The ledger is append-only and every hub session writes to it, including the sessions reviewing this
document: it went 102 → 104 → 107 → 108 → 109 during this review. So the number here is a SNAPSHOT with
a timestamp, never an assertion — and every figure below is stamped with the row count it was measured
at. A figure whose stamp you cannot see is a defect; a figure whose stamp differs from today's count is
working as designed. Re-run the recipes, do not re-read the numbers.

- **R1 — the key census** (piece 4's coverage; `nonnull` is what matters, not `present`):
  `python3 -c 'import json,sys;rows=[json.loads(l) for l in open(sys.argv[1])];ks=sorted({k for r in rows for k in r});print(len(rows));[print(k,sum(1 for r in rows if k in r),sum(1 for r in rows if r.get(k) not in (None,"",[]))) for k in ks]' ~/.claude/state/command-feedback.jsonl`
- **R2 — the candidate selector fire rates** (which thresholds can hit 5–10%): compute
  `tok_in+tok_out` and `wall_s` percentiles with `statistics.quantiles(vals, n=10, method="inclusive")[8]`
  over the same rows, then count rows above each, plus `rounds >= 3` and `waste` not matching `/^none\b/i`.
- **R3 — per-command means:** Σ(`tok_in`+`tok_out`) ÷ the command's TOTAL row count (the divisor is the
  claim; dividing by rows-carrying-tokens gives a 10% different answer), and `mean(wall_s)`.
- **R4 — axis mentions:** case-insensitive count of every OCCURRENCE of each axis STEM (not rows
  containing it — rows-containing gives `rule` 23, not 29) across exactly three fields — `confusion`,
  `waste`, `change`. ⚠️ **Both halves of that sentence are load-bearing and an
  earlier draft got both wrong.** The stem is `rule`, not `rules` (1 vs 29). And adding `filed` and
  `surface` does not merely inflate the counts, it **inverts the ranking**: `infra` goes 3 → 63, because
  those two fields carry beat names and surface paths, which are routing metadata, not an agent
  reporting on its own infra-awareness. The three prose fields are the agent's own account of its run;
  the other two are addressing. At 107 rows the three-field stems give rule 29 · token 10 · lean 6 ·
  infra 3 · accuracy 0 · manifesto 0 · continuous 0 (also `improve` 0 — the axis table cites seven
  values against this recipe, so the seventh stem is named here rather than left underivable).
- **R8 — the three-BARE-metric refusal** (piece 4's registry claim; ⚠️ an earlier draft named this
  recipe for an over-claim about odd axis counts that the same round withdrew — arity is never the
  reason for any refusal): build three probe metrics from a REAL `kc.METRIC_DEFS` entry (copy it, then
  override `id`/`counter_metric`/`version`) and pass `kc.METRIC_DEFS + ko.OUTCOME_METRIC_DEFS + probes`
  to `kc.validate_registry`, enumerating `counter_metric` ∈ {absent, p1, p2, p3} for all three probes —
  **64 assignments, 0 of which load**, in three refusal classes (28 *"has no counter_metric"*, 28
  *"names itself as its counter"*, 8 *"counter pairs must be reciprocal"*). Four as two clean pairs
  LOADS at size 20.
  ⚠️ **Build the probe dicts from a real entry, not from scratch.** A hand-built dict missing `formula`
  makes all four refuse with *"version (int) and formula (str) are required"* — four refusals that look
  exactly like confirmation and prove nothing. That near-miss happened while writing this line, which is
  the third time in this review that a check appeared to pass for the wrong reason.
- **R7 — the `change:` field length** (out of id order, with R8 now between it and R4, because it belongs
  with R4 as a character-level statistic over agent prose that was likewise mis-stated twice; they are NOT the same
  scope — R4 spans three fields, R7 only `change` — nor the same error: R4's was predicate scope, R7's
  was row-count stamping)**:** `median` and `mean` of `len(change)` over all rows. At **107**
  rows both are **248** (248 / 248.2). ⚠️ Two earlier drafts got this wrong in the same way and the
  second was written by the round that caught the first: "248 median, mean 247" holds at no row count,
  and "both 248 at 108 rows" is also false — at 108 the median is **248.5** and the mean **248.6**,
  because one appended row splits the middle pair. A statistic this sensitive to a single row must
  carry the row count it was computed at, or it is noise wearing a decimal point.
- **R5 — the manifesto wiring denominators and numerators:**
  `command find commands/_sources -type f -name '*.md' | wc -l` (36) ·
  `command find scripts/enforcement -type f -name '*.py' | wc -l` (77) ·
  `command find .windsurf/rules -type f -name '*.md' | wc -l` (56), then
  `command grep -rlEi 'operating.manifesto|operating-manifesto\.md' <each root> | wc -l` and the same
  with `rg --no-ignore --hidden -l -i`. ⚠️ Plain `grep` here is the ugrep shim and honours `.gitignore`;
  it cannot ground a negative about a synced path.
- **R6 — `feedback_substance`:** the Q2 predicate — `change` longer than 40 characters AND matching
  `/fabrik-[a-z0-9-]+` or a path bearing `.py .md .sh .ya?ml .json .toml` — over all closes. 40/102 at
  the Q2 snapshot; 44/108 at 108 rows; 48/116 at 116. ⚠️ **There is no rule-pack clause**: an earlier draft carried one and it
  matched a two-digit number followed by a hyphenated word ANYWHERE in prose, adding one row and giving
  41/102 — a recipe that did not regenerate its own cited figure, the same defect class as R4.
- **R9 — the seat cost** (piece 1's price): Σ(`tok_seat_in`+`tok_seat_out`) ÷ Σ`seats_seen` over the rows
  carrying BOTH (55 at 116 rows, Σ`seats_seen` 1,449 → 15,680), cache-read and cache-create tokens
  EXCLUDED on both sides — including them gives 3,967,073 per seat, 253× larger. The per-close means it
  is divided by are R3's (÷ the command's TOTAL row count), so both sides of each ratio exclude cache — ⚠️ unlike the shipped reader: `command_feedback_report.py` publishes a per-command MEDIAN over rows carrying tokens (`median_tok`), and its `_TOK` sums `tok_cache_read`/`tok_cache_create` too — at 116 rows that median is 200–320× R3's mean for the four commands (167,069,998.5 vs 522,376 for `fabrik-execute-plan`), and the seat share against it would read 0.01–0.04%; R3 deliberately excludes cache and divides by TOTAL rows, and piece 4 inherits the divergence as a finding.

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
| I4 | "do we need to make any changes in commands/skills files?" | IN — **NO for D1/Q4; YES for D4** (the observer's dispatch rule is per-run agent behaviour and lives in the corpus). The draft recorded a bare NO and D4 falsified it | Constraint 2 |
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

Every number in the draft was also stale within a day (R6–R17, twelve rows in round 1's own ledger; the headline ones: ledger 68→102 rows / 34→35 keys, `CLAUDE.md` +3,587 B, `close-feedback.md` +1,108 B, three line anchors drifted, the kaizen-log claims overstated, the byte-delta range misidentified). Corrected throughout, and the citation convention above is the durable fix.

## The delta (as it stands after round 15 — the R-table below enumerates round 1 only)

| # | Item | Status after review |
|---|---|---|
| D1 | The D-175 feedback ledger as kaizen series | **SURVIVES, halved** — two reciprocally paired series, not four (Q2) |
| D2 | Governance weight | **REFRAMED** — not a gap in v2 but v2's own unbuilt guardrail; the unit question is CLOSED in v2's favour, so nothing is superseded (Q4) |
| D3 | The M1→M2 gate is MET and untriggered | **SURVIVES, strengthened** — condition (a) met 2026-08-29, provable from the cron log |
| D4 | The OBSERVER + per-usage improvement (operator, 2026-09-11) | **ADDED, then RE-CUT (D-234)** — rounds 9–15 read the eight axes as criteria for grading a RUN and cut the observer down on run-grading research; the operator's confirmed reading is that the axes are properties of the COMMAND TEXT and the loop's gap is that nobody ACTS on the `change:` queue. Four pieces, three of which exist in some form. See § D4 |

`grep -c` against v2 for `feedback`, `close-out`, `confusion:`, `waste:`, `cost_usd`, `tok_in`,
`seats`, `command-feedback` = **0 each across all 588 lines** (re-run by the review seat). The forward
direction of the delta claim holds: the D-175 ledger shipped 2026-09-07, three weeks after v2
converged, and is uncovered by any spelling. It was the REVERSE direction — does v2 already register
what D1 proposes — that failed, as R1/R2 record.

## D4 — the OBSERVER and the loop that acts on it (operator-requested, RULED D-224; RE-CUT on the confirmed reading, D-234)

**The ask, verbatim** (operator, 2026-09-11, recovered by `session-recall`; quoted with line breaks
collapsed and the operator's spellings kept — an earlier draft labelled
its own paraphrase "verbatim", and the paraphrase — *"judge the run on eight axes"* — was the
misreading): *"while working they must assign a subagent as an observer so that, duty will be utilize
kaizen, feedback mechanisms, the goal is to have 1 lean 2 fast executable 3 accurate 4 no token waste
5 continous improvement 6 infra aware 7 rules aware 8 our manifesto aware then record these into
kaizen/feedback. afterwards here in fabrik hub, you(infra) and or intel will read them and make our
commands better and better after each usage, not weeAkly. commands/skills"* — and, when the re-cut
below was read back: *"yes exactly, thx."* The two earlier asks it builds on are quoted in D-234.

**The pattern the first draft matched it to** was *Agent-as-a-Judge* — a judge that reads the whole
trajectory — and that match is where the misreading came from: it made the observer a grader of the
RUN. The composition actually asked for — a reviewer of the INSTRUCTIONS a run is executing, writing
records a hub agent later applies to those instructions — was **not found under any name** in the
sources four `fabrik-researcher` seats searched on 2026-09-11 (arXiv, vendor engineering blogs, the
agent-evaluation literature). That is a bounded absence, not a proof of novelty: we have no prior art
to copy, not that none exists.

### What the run-grading literature measured — KEPT as evidence, RETIRED as design (D-234)

⚠️ **Read this table as a record of what was measured, not as an argument against the ask.** It was
written when the eight axes were misread as criteria for grading a RUN. The figures are real and stay;
the column heading "what the evidence contradicts" does not, because the evidence is about scoring
outputs and the ask is about reviewing instructions. Where a row still bites the four-piece loop, the
loop's own table below says how.

| The ask, as first misread | What the literature says about RUN-grading | Measured here |
|---|---|---|
| An observer on **every** run | **No sampled production account runs one at 100%** — the published accounts sample **1–10%** and gate the judge behind free deterministic signals (not found at 100% in any account searched; an absence over a bounded search) | One seat/close = **7.3%** of all tokens on this ledger — Σ`seats_seen` = 1,390 over the 47 of 107 rows carrying seat data, mean 15,376 tok/seat (at 107 rows) |
| **Eight** axes | The exact configuration measured to collapse: *"factor correlations above 0.93 … supposedly distinct criteria behave interchangeably, reducing the evaluation to a near-unidimensional signal"*, with **>90% unexplained variance** | Eight numbers would be one number wearing eight labels |
| Improve **after each usage** | Deming's funnel: adjusting from single readings *increases* variance. Repeated interim testing inflates the false-positive rate to **26.1%** (Evan Miller, *How Not To Run an A/B Test*, 2010 — https://www.evanmiller.org/how-not-to-run-an-ab-test.html; Kohavi et al. describe the phenomenon, they are **not** the source of this figure). DSPy's optimisers propose on a minibatch and promote only on a **full validation pass** | — |

And one the ask does not mention but the evidence forces: **a single observer call is not a verdict.**
*"pairwise preferences flip on average 13.6% of the time"*, *"44.7% is within-question noise"*, and
*"95% requires 11 trials"* — all three from Yagubyan, *The Coin Flip Judge?* (https://arxiv.org/html/2606.13685),
**not** from the factor-collapse paper the earlier draft credited. At 11 trials the measured 7.3%
becomes **~80% overhead**. A one-call observer is cheap and unreliable; a reliable one is unaffordable.
That is the finding that reshapes the design.

Two further hazards, both live for us specifically:
- **Self-preference.** This would be Claude judging Claude: *"an LLM evaluator scores its own outputs
  higher than others' while human annotators consider them of equal quality"*, with a measured linear
  correlation between self-recognition and self-preference.
- **The loop makes the observer a reward model.** Feeding verdicts back into instruction files is
  reward-model optimisation, and *"optimizing its value too much can hinder ground truth performance,
  in accordance with Goodhart's law."* "Lean" is a length metric an agent satisfies by writing **less**.

### What our own ledger says — the half of the ask that is already solved

| Axis | Mentions across all self-reported close-out feedback (**at 107 rows, 2026-09-11**; `## Reproduce`, R4) |
|---|---|
| rules *(stem `rule` — R4 says why: `rules` gives 1)* | 29 |
| token / lean / infra | 10 / 6 / 3 |
| **accuracy · manifesto · continuous-improvement** | **0 · 0 · 0** — and still 0 · 0 · 0 at 108 and 109 rows. ⚠️ An earlier draft claimed this had already aged to `0 · 1 · 0`, citing this spec's own close. It has not: that close's only use of "the operating manifesto" sits in the **`filed:`** field, which R4 deliberately excludes as routing metadata. A claim about a metric must be computed with that metric's own predicate, and the draft used a different one to make a rhetorical point |

**91 of 107 closes already report substantive waste, unprompted** (85.0% at 107 rows; 91 of 108 = 84.3% now) — specifically, e.g. *"two gate runs
red on siblings' in-flight files — ~4 min re-attributing reds that named no file of mine"*. An observer
would not add much there. What agents never report is **accuracy and manifesto-conformance** — the two
zeros above, and exactly what a self-assessor structurally cannot judge about itself. ⚠️ An earlier
draft said "the three judgement axes" and grouped continuous-improvement with them; the axis table rules
that axis a cross-run TREND that no per-run observer should score at all, so it does not belong in this
sentence. Nor is "never report" true of the other judged axes: `rule` is the most-mentioned of the eight axis stems
inside R4's three fields (29 at 107 rows — and the bound is the whole claim, stated in R4's own
substring convention so the three numbers are comparable: over ALL five fields `infra` overtakes it at
63, and over every string rather than just the axis stems `the` wins at 1,052) and `infra` appears 3 times — mentions, not compliance, which is why they are judged
rather than derived.

And the 8th axis is the one to be careful about. `docs/reference/operating-manifesto.md` is cited by
**0 of 36** command sources (`.md` in `commands/_sources/`), **0 of 77** enforcement checks (`.py` in
`scripts/enforcement/`, excluding 56 `.pyc`) and **0 of 56** rule packs (`.md` under `.windsurf/rules/`,
excluding 2 `.yaml` configs) — confirmed with `command grep` AND `rg --no-ignore --hidden`, since the
shell `grep` is a ugrep shim that honours `.gitignore` and cannot ground a negative here
(`## Reproduce`, R5).

⚠️ **An earlier draft read those three zeros as neglect — "nothing ever machine-checked it" — and
round 10 refuted that with three in-repo facts. The zeros are real; the inference was wrong.**
(a) `docs/development/plans/archived/2026-08-31-plan-1-manifesto-command-pass/` is **`Status: EXECUTED
2026-08-31 — 34/34 Board rows terminal`**: a 34-ticket pass that walked **the 32 command sources that
existed then** (its own stated denominator) against the manifesto, whose § Global Constraints reads *"**Do not inject manifesto vocabulary** into a command
where an intersection is genuinely N/A"*. The zero in `commands/_sources/` is therefore a **designed
outcome of a completed governance pass** for 32 of today's 36 sources — ⚠️ **and an untested absence for
the other four**, which were created after the pass (`fabrik-deploy-checklist` 2026-09-02;
`fabrik-epics`, `fabrik-epics-review`, `fabrik-vision` 2026-09-05) and have never been walked against
the manifesto at all. For 11% of the denominator the zero IS the omission the rest of this note rejects,
and that gap is a backlog row, not a rhetorical inconvenience. (b) `docs/reference/command-evaluation-checklist.md`
item **63b** is the live instrument: six named intersections (a)–(f) — checkable termination gate ·
decisions routed to the ledger with the ONE-WAY field block · rigor scaled to irreversibility · labelled
evidence discipline · disorder captured as data · most-reversible default — with *"N/A because X"* a
valid verdict per item. (c) the manifesto's own § Binding says the gates bind *"through machinery that
already exists and is already enforced — never a parallel system"*, so grepping `scripts/enforcement/`
for its filename is **the wrong probe by the document's own design**; `check_decisions_unique.py` and
`check_review_coverage.py` are the machinery it points at. ⚠️ **Two of the three zeros are disposed of — the first only for 32 of 36 sources, with four untested
(above) — and the third is not at all.** Nothing here explains `0 of 56 rule packs` — no pass ever walked
them against the manifesto, and § Binding's "never a parallel system" argument covers enforcement
scripts, not rule packs. That zero remains an open question, and saying so is cheaper than letting a
three-and-three symmetry imply a mapping that does not hold. **46 TRACKED files cite the manifesto** — `git grep -l`, which is the bound: it excludes the 18 sibling worktrees
under `.claude/worktrees/` and `.git/` (an unbounded `rg --no-ignore --hidden` over the same tree
returns 858, almost all of them worktree copies). The 46 decompose as 2 `CLAUDE.md` + **35** files of
that archived plan set (the directory holds exactly 35) + **9** others — the earlier "only the two `CLAUDE.md`
files" was a whole-repo negative asserted from a three-directory search, this spec's own denominator law
turned on its author.

**What this changes for piece 1's `manifesto` key, concretely:** the manifesto axis does **not** need
criteria invented for it. The observer records against checklist item 63b's six intersections, which are already written, already applied
corpus-wide once, and already admit *"N/A because X"*. That is cheaper and better-grounded than anything
this spec would write, and it is the difference between judging conformance and judging vocabulary.

### The design — RE-CUT 2026-09-11 on the operator's confirmed reading (D-234)

⚠️ **The three-tier design that stood here from round 9 to round 15 was built on a misreading, and the
operator confirmed the correct one on 2026-09-11.** The earlier draft read the eight axes as criteria
for GRADING A RUN, went to the LLM-as-a-judge literature, and cut the observer down on the strength of
research about scoring outputs. **The eight axes are properties of the COMMAND TEXT** — *infra aware*
means "does this command reflect the infra as it is today"; *rules aware* means "does it contradict a
rule pack"; *lean* means "is the instruction text carrying weight it does not need". The observer's duty
is to catch where the command it is running MISLED or OVERCHARGED the agent, and say so, per run. That
is a reviewer of instructions, not a grader of outputs; the factor-collapse and self-preference results
above are real but do not transfer. Likewise *"after each usage, not weeAkly"* was read as a demand for
AUTO-apply and argued against twice — with Knight Capital (a cadence section the re-cut deleted) and, in
the table above, with Deming's funnel and the 26.1% peeking figure; both objections answer a demand that
was never made. The operator never said automate — *"you (infra) and or intel will read them and make
our commands better"* is an agent applying a fix through review, which Constraint 1 already permits, at
the speed of the queue. The measured facts in the two sections above stand; the design drawn from
them did not.

**The loop is FOUR pieces, and three of the four already exist in some form — the gap is at step 2, ACT** (step 3 is the only piece with nothing built at all, but a ratchet is not the loop's answer to the ask; D-234 says the same: *"the loop is open at ACT"*).

| # | Piece | What exists today | What is built |
|---|---|---|---|
| 1 | **OBSERVE** — the `change:` field IS the observer. It already asks *"the ONE concrete edit to the command that would have made the run faster or more accurate"* | every close writes it; **112 of 116 are not `none`, and 48 of 116 name a command or a file (41.4%)** (Q2's `feedback_substance` predicate — the honest "substantive" count; an earlier draft put the `waste:` field's 91 of 107 here) | make it **axis-keyed — SEVEN keys for the seven per-run axes** (`lean` / `fast` / `accurate` / `waste` / `infra` / `rules` / `manifesto`; the operator's axis 5, continuous improvement, is read cross-run and has no per-run key — axis table row 5) so it is routable, and for the expensive commands — **the top four by R3's per-command mean at 116 rows: `fabrik-execute-plan`, `fabrik-review`, `fabrik-plan-review`, `fabrik-plan-after-chat`** (54 of 116 closes = 46.6%, carrying 77.7% of the token mass; an earlier draft named `fabrik-spec-review`, which ranks 7th of 14 by that mean (`fabrik-workflow-review`, n=1, sits 6th) — the list is a RANK CUT, top four by R3, re-derived at the sign-off, never a hand-picked set) have a **subagent** write it rather than the agent grading its own run. ONE fragment edit to `close-feedback.md` — Constraint 2's named exception, infra's beat. **Priced, since rejecting the flat policy on a measured figure and leaving this one unpriced would be the asserted-cost defect** (R9 at 116 rows: mean **15,680 tok/seat** over the 55 rows carrying seat data, Σ`seats_seen` 1,449, cache tokens excluded; the per-close means are R3's): the seat costs **3.0%** of a `fabrik-execute-plan` close (mean 522,376 tok, n=11), **4.6%** of `fabrik-review` (338,382, n=27), **7.0%** of `fabrik-plan-review` (225,468, n=9), **8.5%** of `fabrik-plan-after-chat` (185,303, n=7) — cheapest where runs are longest |
| 2 | **ROUTE + ACT** — the `change:` rows reach a hub agent who edits the command | `feedback_relay.py` already mails the digest to infra **once a day** (the crontab polls `weekly_catchup.sh` at minute 27 of every hour; the wrapper stamps the kaizen jobs `DAILY` — an earlier draft said hourly, reading the crontab line and not the wrapper); **nothing acts** — the queue is unread under 200+ inbox items | a `/fabrik-command-improve <command>` command: read every `change:` row for that command from the ledger, propose the edit, render, review, commit — **and the applied edit is a COMMIT on the command source whose trailer names the ledger rows it answers and carries Q3's declaration** (`Agent-Context: command-improve <command> · rows <ts,…> · expects <series> <direction>`): the ledger has no row id — `ts` is its only per-row handle (`sid` is per session), and a `rid` written by `command_run.py`'s ledger writer is piece 2's one prerequisite if `ts` proves ambiguous. The declaration is Q3's unconditional half (the series the edit expects to move, and the direction); the trailer is what axis 5 reads. When M2's fix ledger exists those commits ARE its rows, already carrying what Q3 requires of a row; until the M1→M2 sign-off no edit is graded against a series — Q3's grading-and-revert clause is what waits, the edit does not, and piece 2 depends on nothing that M2 must build first. Run it whenever a command's queue is non-empty — **that is "after each usage"**. **Holder of the duty: infra** (`commands/_sources/` and `.windsurf/rules/` are that beat); intel may run it too, in the operator's words. The duty lives in the hub `CLAUDE.md`, not in a cron — a NEW command source plus one contract line, both through the normal review path (Constraint 2, as re-cut) |
| 3 | **KEEP LEAN** — the weight ratchet | nothing budgets any governance byte; `CLAUDE.md` 89,214 B read every session, `commands/_sources/` 1,042,530 B, `.windsurf/rules/` 1,251,876 B of `.md` (1,319,036 B for the whole directory) | `scripts/enforcement/check_corpus_weight.py` on the pattern this repo already runs twice (`.fabrik/doc-script-baseline.json`, `.fabrik/lint-baseline.json`), with the two REFERENCES separated — which is what a byte ratchet needs and a count ratchet does not: the **WARN fires on the change's own delta**, the working tree above the BASE branch, per OWNED surface; the committed baseline is the **TREND record** — seeded once at a corpus state someone accepted, tightened on the run that observes a shrink (under `--check` it only reports the tighter floor), raised only by a commit citing the D-row that names what the growth retires — **and that citation is a review convention the check does not read**: `--reseed` writes today's sizes unconditionally, and none of the plan's fifteen Phase A graders tests for a D-row, so the reviewer enforces it and nothing else does. The baseline is never the WARN's reference. A surface with no blob at the base ref reads *base absent — not budgeted*, never a WARN. The split is MEASURED, not preferred: over the 30-day replay at `acb50492` a warn-on-every-rise would have spoken on 16–21 of the 29 day-over-day comparisons on five of the six surfaces and 5 of 29 on `commands/_agents` — mean 16.8 of 29, which is wallpaper (§ Q6's narrowing, **D-240** (b); the replay is the plan's § Evidence). The warning is a gate **WARN, never a red**, because § Q4 rules bytes a trend signal and never the enforced ceiling — it is the **byte TREND signal § Q4 keeps** ("bytes only as the free, CI-native trend signal"), NOT Q4's transcript-token guardrail, which still waits on the M1→M2 sign-off. **Needs no sign-off** — an earlier draft deferred it behind that noise floor, which exists to stop a *metric* firing on noise; a ratchet is one committed number, not a metric. **fleet builds, infra reviews** (`scripts/enforcement/` is infra's beat and a governance-sync trigger surface; the script syncs to ~46 repos and budgets only what a repo OWNS — the six surfaces named in Constraint 2, ownership marked by `commands/_sources/` existing, every write gated on the main checkout so a worktree reports and never writes; **D-241**). § Q4's two documented ratchet failure modes land differently here: **re-baselining upward** is answered by construction, because the base-branch comparison Q4 wanted as a SECOND gate is this check's only gate and no baseline value can defeat it; **baseline drift** (dead ESLint suppressions) has no analogue, because the record is one number per surface that re-seeds downward, not a list of exemptions to prune |
| 4 | **PROVE** — tokens per round per command, behind the mass rule (Q5 canary 4) | tokens per CLOSE exists in `command_feedback_report.py`; per ROUND does not | the addition planned as Phase B of `docs/development/plans/2026-09-12-plan-1-kaizen-corpus-weight-and-tokens-per-round.md`, reviewed to a quiet tenth pass (**D-244**). That plan superseded the never-executed DRAFT this row used to cite, and **D-240** (c) records both the supersession and the removal, with the dead plan's last text at `ad612bc6`. Kept, but LAST: it is the thermometer that shows steps 1–3 working, not the loop. **The quantity, as Phase B defines it:** the numerator is Σ(`tok_in`+`tok_out`) with `tok_cache_read` and `tok_cache_create` EXCLUDED — the divergence from the shipped reader's cache-inclusive `_TOK`, which piece 4 inherits as a finding — and the divisor is Σ`rounds`, a count of `round` calls that has no cache dimension to exclude. Both sums run over the rows carrying BOTH a token pair and `rounds > 0`, so the ROW exclusion and the CACHE exclusion are two separate rules and neither implies the other. Emitted per command beside `rows_with_numerator`, `rows_with_denominator`, `rows_both` and `rows_total`, and published only through Q5 canary 4's mass rule: a command whose token mass `T` is 0 renders `—` with the reason *"zero token mass"*, and one at `q/T < ⅔` renders `—` with its measured ratio as the reason |

**Sequencing against the live tree (2026-09-11):** infra's review-family plan is IN-PROGRESS under an
active lock that owns `commands/assemble_commands.py`, and `commands/_fragments/` is dirty with their
edits. So **pieces 3 and 4 build now** (no lock, no collision — the ratchet's BASELINE is seeded only
after infra's corpus edits land, or it freezes a number they are changing); **pieces 1 and 2 build after
infra's plan closes** — not because their files are locked (`close-feedback.md` is neither locked nor
dirty) but because piece 1's RENDER goes through `assemble_commands.py`, which the lock owns and which
is dirty, and piece 2's duty line lands in `CLAUDE.md` and `templates/governance/CLAUDE.md`, both in the
lock's owned paths.

**THE EIGHT AXES, as properties of the COMMAND TEXT — what the observer records under each key, and the
instrument that already exists for it.** This is the table an earlier re-cut deleted by accident; it is
what makes piece 1's axis keys mean something rather than being labels.

| # | The operator's axis | What it means of the COMMAND being run | What the observer records under this key | Existing instrument |
|---|---|---|---|---|
| 1 | lean | the instruction text carries weight the run never used | the sections the command loaded that the run did not cite or act on | piece 3's ratchet (bytes per surface) |
| 2 | fast executable | the command's steps ran without a stall the text caused — an ask it could have answered, a re-derivation it could have carried | where the run stopped to ask or re-derive something the command should have stated | `wall_s`, `rounds`; the `confusion:` field |
| 3 | accurate | no instruction turned out false — a path, flag, symbol, count or script that does not exist or does not do what the text says | the false instruction, quoted, with the executed disproof | `check_command_corpus.py` (BLOCKING, registered in `final_gate.py`) already grades the EXISTENCE half of this axis over `commands/_sources/` — script paths, chain targets, web-tool names, the advertised close flag. What nothing grades is the SEMANTIC half: whether a path that exists does what the text says, and whether a stated count is true — the observer's own executed disproof (`ls`, `grep -n`, a live probe) and the `confusion:` field cover that residue, which is why this axis is observed, not derived. (`check_citations_resolve.py` is not an instrument here: its globs are specs, plans, reviews and reference docs, never `commands/_sources/`, and it skips a path that does not exist) |
| 4 | no token waste | the command did not make the agent read, dispatch or re-derive what the outcome never needed | the read, seat or round the run could have skipped, and its cost | the `waste:` field (85% populated already); piece 4's tokens-per-round |
| 5 | continuous improvement | the last `change:` filed against this command was applied, and THIS run benefited | **no per-run key** — read cross-run: whether the previous change landed, and whether the next close of the same command hit the same wall anyway | the commit trailer of piece 2's applied edit on the command source (`git log` of that file), joined to the next close — a cross-run check, never scored per run |
| 6 | infra aware | the command names infra as it is TODAY — paths, hosts, services, scripts, flags | the stale or retired infra fact the command relies on, with the live value | `agents-fabrik.md`, `scripts/service_catalog.json`, `mcp_health.py`; a live probe beats the doc |
| 7 | rules aware | the command neither contradicts nor duplicates a rule pack the run activated | the pack and the clause it contradicts or restates | `select_rules.py` ACTIVE set — the observer reads the activated pack against the command text; **no check detects a command contradicting or duplicating a pack today** (`check_rule_grounding.py` grades a CONVERGED plan's constraints digest, not a command) |
| 8 | manifesto aware | the command conforms to the operating manifesto's binding intersections | which of 63b's six intersections (a)–(f) it fails, or *"N/A because X"* | `docs/reference/command-evaluation-checklist.md` item 63b — six criteria already written and applied corpus-wide once; see the manifesto note above |

The observer's output is therefore a short structured record — key, quoted instruction, executed
evidence — not a score. That is what makes it routable (piece 2 groups by key and by command) and what
makes it cheap: it names what was wrong with the text, which is the only thing a hub agent can act on.

**What this supersedes:** the three-tier observer, the "judge 5–10% on 2–3 criteria" selector, the
kappa-validated rubric, the batch-and-gate cadence table, and the deferral of the ratchet — all of them
answers to a question the operator did not ask. The selector keeps its M1→M2
dependency for RE-DERIVATION only, and is RE-AIMED and RE-CUT: it no longer chooses which RUNS a judge scores (R2's per-row
percentile), it is a RANK CUT — the top four commands by R3's per-command MEAN — and no percentile
survives, because a p90 over the 14 commands admits two, never four — by mean or by mass, with or without the `test_cmd` fixture row. The list above is that cut at 116
rows; the sign-off owns when it is re-derived (§ Who builds what, § Constraints 4). § Q2's
series are unchanged and belong to piece 4, which was right for them.


### Does bloat actually hurt? — the honest strength judgment

**Strong (peer-reviewed):** *Lost in the Middle* — *"performance … significantly degrades when models
must access relevant information in the middle of long contexts, even for explicitly long-context
models."* Directly relevant to appending rules into a growing corpus.
**Suggestive (fresh preprints, two of them — an earlier draft cited them as one):** follow rate
*"falls from ∼96% to as low as 20%"* from 1 to 20 stacked instructions, and *"the violations are
silent: no error is raised when an instruction is dropped"* (Anand & Chattaraj, *Instruction Stacking
Collapse*, https://arxiv.org/html/2608.02639); *"Reliable instruction following breaks down beyond 5–6
simultaneous constraints"* (Vasileva, https://arxiv.org/html/2608.12426).
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
series (`~/.claude/state/kaizen/series/<metric>@v<N>.jsonl`, 16 live data files — ⚠️ **that 16 is a
different population from the registry's 16**: the files span only **13 distinct metric ids** (three are
superseded `@v1` files) and **3 registered metrics have never published at all** (`rework_rate`,
`fleet_health`, `sweep_coverage`), so "16 files" must not be read as "one per registered metric" —
*"a published series is
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

Across infra's review-family range `0fcafed5^..a1b2509f` (T01 → Finish): **57** files. An earlier draft wrote 52 and anchored the range at T03 rather than T01; the T03-anchored range is 48 files, so neither half of the draft's claim was right. The corpus-surface subset grew **+22,294 B over 7 nonzero-delta files** (≈22.3 KB decimal, 21.8 KiB
binary — the unit is stated because the two differ by half a KB here). The seven, executed with `git cat-file -s` at both
endpoints: `fabrik-review.md` +9,394 · `62-using-subagents.md` +4,258 · `subagents-core.md` +2,306 ·
`CLAUDE.md` +2,258 · `templates/governance/CLAUDE.md` +2,258 · `fabrik-repo-review.md` +1,081 ·
`fabrik-review-scoped.md` +739. An earlier draft said "≈ +19 KB" from a five-file sample that missed
`subagents-core.md` and `fabrik-repo-review.md`.

⚠️ **Round 13 raised the total as wrong at 20,036 B and was REFUTED by execution** — that count dropped
one of the two `CLAUDE.md` files, and both are corpus surface. The refutation is recorded rather than
silently discarded because a review that only logs what it confirms hides the half of its work that
kept a correct number from being "fixed" into a wrong one (D-206: refuted candidates never count). ⚠️ These bytes are EVIDENCE that governance text grows unwatched; they
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
| `command_tokens_per_round@v1` | Σ(`tok_in`+`tok_out`) ÷ Σ`rounds` **over the rows carrying BOTH a token pair and `rounds > 0`** — a row missing either side contributes to NEITHER, and cache tokens are excluded from the numerator. Emits `rows_with_numerator`, `rows_with_denominator`, `rows_both` and `rows_total` per command; renders `—` per the mass rule in Q5 canary 4. Same quantity as § D4 row 4 and the plan's Phase B | **driving** — D-203's delta-round rule predicts this FALLS; the loop's first self-test |
| `feedback_substance@v1` | closes whose `change:` is **> 40 characters AND matches `/fabrik-[a-z0-9-]+` or a path bearing a `.py .md .sh .ya?ml .json .toml` extension** ÷ all closes. ⚠️ **The "or a named rule pack" clause is REMOVED — round 11 executed it and it is a false-positive generator.** As `\b\d{2}-[a-z][a-z0-9-]*\b` it matches `31-component` inside the ordinary English phrase *"a one-rule fix instead of a 31-component sweep"*, on a row whose `change:` begins with the word **none** — so the counter scored a non-substantive close as substantive, which is the one thing a counter must never do. A rule pack cited the way agents actually cite one (`62-using-subagents.md`) is already caught by the `.md` clause, so the removal costs nothing. It moves the rate 41 → 40 of 102 | **counter** — guards the Goodhart: tokens must not fall because agents said LESS. Measured on the live ledger with THIS predicate: **40 of 102 (39.2%)**; 44 of 108 (40.7%) at 108 rows; 48 of 116 (41.4%) at 116 (`## Reproduce`, R6) |

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
  an agent satisfies by cutting `change:` from a median and mean both of **248 characters** (at 107 rows;
  `## Reproduce`, R7) to five — the
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
execution against the live validator — **and the symbol matters, because the obvious one gives a
different number**: the 16 registered metrics are `kaizen_outcomes.registry()` (= `validate_registry(
kaizen_collect_v2.METRIC_DEFS + OUTCOME_METRIC_DEFS)`, 10 + 6), NOT `kaizen_collect_v2.registry()`,
which is 10. The two new ids collide with neither, and `kaizen_outcomes.registry() + the new pair`
loads at size **18**.

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
  comparing per-rule counts against the base branch. Our check makes that comparison its ONLY gate
  (§ D4 row 3): the tree-above-base delta is what WARNs, and the baseline has no GATE role at all. It is
  not inert — a plain run WRITES it, tightening any surface whose bytes fell and printing that it did —
  but no baseline value raises or suppresses a warning, so there is no baseline a re-baselining commit
  could defeat.
- **Baseline drift.** ESLint warns on suppressions that no longer occur and ships `--prune-suppressions`;
  unpruned entries become dead exemption debt.

⚠️ **Q4 IS THIS SPEC'S ONE 1a EXCEPTION.** The three bullets above are vendor **runtime** facts —
per-(request, model) tokenisation, content-type density, byte-for-byte prefix caching — and they DO
determine a mechanism here: they are why the unit is tokens and not bytes. They were measured during
the 2026-09-11 research and are recorded as a measured case, not as a cited row, so a reader re-testing
Q4 should re-measure them rather than look for them in § External facts' list.

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
   **THE MASS RULE — one rule, TWO clauses, evaluated in this order.** ⚠️ The order is the rule: a
   builder told "it is one comparison" writes the comparison and ships the crash clause 1 exists to
   stop (executed: `q/T` at `T == 0` raises `ZeroDivisionError`; with the guard first it renders `—`).
   1. **Guard.** A command whose total token mass `T` is 0 renders `—` with its reason; the ratio is
      undefined and is never evaluated (**11 of 137 ledger rows** carry `rounds > 0` and no finite
      `tok_in`/`tok_out` — re-derived 2026-09-13 00:25 +03, the predicate stated because a looser one
      that also admits `rounds == 0` rows reads 13; `test_cmd` has exactly one row and it is one of the
      11). `T` is Σ(`tok_in`+`tok_out`) over that command's rows with
      `tok_cache_read`/`tok_cache_create` EXCLUDED — the way the plan's § Evidence computes it, and NOT
      the shipped reader's cache-inclusive `_TOK` — so a reader of this clause and a reader of that
      block compute the same number.
   2. **Ratio.** Otherwise a series renders `—` with its reason unless the rows carrying BOTH sides
      account for **≥ ⅔ of that command's token mass** (`q/T ≥ ⅔`).

   Measured on the live ledger:
   ⚠️ **No per-command percentage is quoted here, on purpose.** Earlier drafts pinned six of them and
   they went stale three times in one review — including from closes the review itself generated: the
   ledger grew 102 → 104 rows mid-run and `fabrik-spec` moved from 66.2% to **54.0%** when one
   non-rounds-carrying close landed. A spec that cites a live-ledger ratio is citing something that
   moves faster than the document. Re-derive instead, per command:
   `q = Σ(tok_in+tok_out) over rows with rounds>0 AND tokens>0`, `T = Σ(tok_in+tok_out) over all rows`
   — cache tokens excluded on BOTH sides, per the plan's § Evidence — publish when
   `q/T ≥ ⅔`, else `—`. A command at `q/T < ⅔` needs one qualifying close of `x ≥ 2T − 3q` to flip —
   **three times the static deficit `(⅔)T − q`**, because a new qualifying close grows BOTH sides.
   Reasoning from the static deficit understates the flip by 3× and is the error this clause replaces.
   **Why ⅔ and not ½ or ¾ — the gap, not the constant.** Executed 2026-09-11 at 104 ledger rows,
   every command with nonzero token mass — **13 of the 14 in the ledger**, `test_cmd` having `T = 0`
   and being caught by clause 1 — has a `q/T` either **≤ 0.540** (3 commands) or **≥ 0.9339** (10), with nothing in
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
mechanism owed.** D6 extends `check_review_hygiene.py` with `table-parity`. ⚠️ **The verdict holds; an earlier draft's
MECHANISM for it did not, and the correction is the "read it, don't recall it" class.** That draft said
`_surface_hits` gates *every* class on `path.endswith(".md")`. Executed: only **three** classes are
`.md`-gated (`template-residue`, `fence-parity`, `table-parity`); `stale-phrase` runs after the gate on
any path and `dead-symbol` is computed outside `_surface_hits` entirely — both fire on a `.py` or `.txt`
surface, proven by running them on one. The reason they are DISJOINT is the SUBJECT, not the file
extension: D6 grades review prose, these canaries grade ledger rows and series cells. Nothing stops
either script running on the other's file; nothing makes its findings mean anything there. They share one law — D6's `dead-symbol` and canary 2
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

⚠️ **A, B and C were written before D4 existed and are framed over D1/Q4/D3 only.** D4 is not an
alternative to them — it is an approved addition (D-224) that runs in parallel (§ Lifecycle), and its
cost is enumerated below rather than folded into A's.

**A — Activate first, build second (RECOMMENDED).** Trigger the M1→M2 variance sign-off, then ship
D1's paired series and Q4's transcript-token guardrail — both advisory.

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

⚠️ **D4's build half, enumerated so it is not omitted by silence** (it was, until round 9; re-cut
under D-234): piece 1 — ONE `close-feedback.md` fragment edit (axis keys + the four-command subagent
condition) · piece 2 — a new command source `/fabrik-command-improve` plus one duty line in the hub
`CLAUDE.md`, each applied edit a commit whose trailer names the ledger rows it answers · piece 3 — `check_corpus_weight.py` with its baseline file
and tests · piece 4 — the tokens-per-round addition to `command_feedback_report.py` behind the mass
rule, with its tests (pieces 3 and 4 are Phases A and B of plan
`2026-09-12-plan-1-kaizen-corpus-weight-and-tokens-per-round.md`, which superseded and removed the
never-executed DRAFT this paragraph used to cite — D-240 (c), D-244). **Four items, and all four
are accounted for:** two are corpus TEXT through the review path (pieces 1 and 2's command source),
two are CODE (pieces 3 and 4), and the only human in the loop is the hub agent who runs piece 2 — no
labelled set, no kappa run, no judge: those were the misread design's costs and are gone with it.
Unestimated, like A's — and no longer larger than A's, but the recommendation below must still not be
read as having priced it.

**B — Build the series first, activate later.** Rejected: it adds unadjudicable series to a loop whose
adjudication half is already stalled — more recorded, still not evaluated, the exact failure named.

**C — A full new closed-loop mechanism.** Rejected on sight once v2 was read: forks a converged design
and re-implements M2.

**Recommendation: A for the series half** — the draft's own build half shrank from four series to two,
so activation is a large share of the available value there. **D4 is not subject to this
recommendation**: it is ruled (D-224) and sequenced in § Lifecycle, and A's "activation is most of the
value" argument does not transfer to it, because none of D4's value comes from a series that is already
collecting.

## Who builds what

| Item | Owner | Rationale |
|---|---|---|
| M1→M2 variance sign-off (D3) | **operator-triggered** | `kaizen.md` names it a *"named operator-triggered follow-up"* — not an agent's call |
| The Q4 unit (transcript tokens vs disk bytes) | **nobody — CLOSED** | § Q4 re-derived it 2026-09-11 in v2's favour: tokenisation is model-scoped, markdown runs ~2× denser than prose, and a mid-file byte change breaks prefix caching. No converged adjudication is reversed, so no ruling and no D-row |
| D1 — ledger reader + the paired series | **infra** (kaizen is their beat) — **fleet may build it** if infra's queue makes that slower | infra holds 64 of 65 `ack=required` items |
| Q4's guardrail (transcript-token mass), when M1→M2 opens | **fleet**, infra reviews | New reader over transcripts, not a new unit; fleet holds the measurements |
| `rounds_to_converge` as a DIMENSION on `review_rounds@v10` | a proposal to that series' owner | R2 — never a new metric id |
| M2's finding registry / fix ledger | **infra**, per v2 | Already theirs; this delta adds only the verification clause; piece 2's applied edits land here as fix-ledger rows once M2 exists — until then the commit trailer on the command source is the record (§ D4) |
| D4 piece 1 — the axis-keyed, subagent-written `change:` field (ONE `close-feedback.md` fragment edit) | **infra** (`commands/_sources/` is their beat) | Constraint 2's named exception; a corpus edit distributes fleet-wide and must not be fleet's unilateral change. Builds AFTER infra's review-family plan closes (§ D4 sequencing) |
| D4 piece 2 — `/fabrik-command-improve <command>` + the CLAUDE.md duty line | **infra**; intel may run the command | The holder of the duty is the beat that owns the surface being edited; a new command source is a corpus change. Same sequencing as piece 1 |
| D4 piece 3 — `check_corpus_weight.py`, the byte ratchet | **fleet builds, infra reviews** | `scripts/enforcement/` is infra's beat and a governance-sync trigger; the pattern (`doc-script-baseline.json`, `lint-baseline.json`) is proven; with its `final_gate.py` registration it is TWO fleet-synced files (Constraint 2). Builds now; the BASELINE seeds only after infra's corpus edits land |
| D4 piece 4 — tokens per round per command behind the mass rule (`command_feedback_report.py`) | **fleet** — Phase B of plan `2026-09-12-plan-1-kaizen-corpus-weight-and-tokens-per-round.md` (D-244; it superseded and removed the DRAFT this row used to cite, D-240 (c)) | Not a series, so not kaizen's registry; it is a reader over the ledger fleet already measures. Builds now, LAST of the four |
| D4 — re-deriving piece 1's four-command list (the rank cut: top four by R3's per-command mean) | **deferred to the M1→M2 sign-off** | Same owner as Q2's minimum-n and for the same reason — when to re-cut is the sign-off's output. The static list runs meanwhile |

## Constraints (binding)

1. **Never auto-edit a fleet-synced governance file.** The loop PROPOSES with evidence; a session
   applies through the normal review path. A bad edit to `CLAUDE.md` or a rules pack reaches ~46 repos
   before anyone reads it.
2. **D1 and Q4 change no command file; D4 changes the corpus in TWO places, adds ONE enforcement
   script and registers it in `final_gate.py` — two fleet-synced files for piece 3, not one.** (The
   headline read "zero command-file changes" flat until D4 falsified it; the re-cut raised the corpus
   count from one to two — piece 1's fragment edit and piece 2's new command source.) `scripts/enforcement/`
   syncs recursively into every project and `final_gate.py` is in the synced manifest, so
   `check_corpus_weight.py` ships to ~46 repos: it must be correct for ALL of them — and what it budgets
   is what a repo **OWNS**, never what it merely HAS. Ownership is the positive marker
   `commands/_sources/` EXISTING: the hub holds it and so does every registered hub worktree; a synced
   project does not (its `CLAUDE.md` and rule packs are byte-identical sync copies, overwritten on the
   next governance commit, that no project agent may fix) and neither does fabrik-lib. In a repo without
   the marker the check prints ONE line and exits 0 — it grades nothing there. In an owner repo it budgets
   **SIX** surfaces, counting every file under each: `CLAUDE.md`, `templates/governance/CLAUDE.md`,
   `commands/_sources/`, `commands/_fragments/`, `commands/_agents/`, `.windsurf/rules/`. And every WRITE
   is gated on the MAIN checkout (`.git` a directory, not a file): a worktree reports and never writes, so
   the check cannot stage a baseline into a sibling session's tree (**D-241**, superseding D-240 (a);
   executable shape at the plan's § Phase A Interfaces — `is_owner`, `is_main_checkout`, `verdict`). The
   close-out contract is
   single-sourced in `commands/_fragments/close-feedback.md` (10,485 B), appended to all 36 commands by
   `assemble_commands.py`. Agents already emit the columns these two series read — with `rounds` **present but 0** (never absent **by construction** — `command_run.py` writes `"rounds": len(rec.get("rounds") or [])`, always an int; a builder coding to "absent" writes a branch that never fires) for
   commands whose lifecycle has no round semantics (17 of 102 rows carried `rounds == 0` when measured, 15 of
   them holding 24.2% of all token mass — re-derive, the ledger grows: `rounds == 0` rows ÷ all rows), which Q5's mass rule handles with `—` rather than a fragment edit. The draft's broader
   claim — "everything these series need" — was false for `cost_usd` (R5), which is why that series is
   dropped rather than patched. No fragment edit is required for D1 or Q4 as scoped. ⚠️ **D4 is the
   exception and it is a real one:** piece 1 — the axis-keyed `change:` field, subagent-written on the
   four named commands — is per-run agent behaviour, and the only fleet-wide place that behaviour can be
   specified is the command corpus: one edit to `close-feedback.md` (single-sourced into all 36
   commands), with the four-command condition expressed there rather than in four sources. Piece 2 is a
   new command source plus one duty line in the hub `CLAUDE.md`. Each goes through the normal review
   path like any other (Constraint 1); what Constraint 2 forbids is the LOOP editing them, not the loop
   needing them.
3. **Every new metric ships with a canary** that fires when its own input goes missing — never a
   silent 0 (Q5).
4. **No series fires anything until the noise floor exists** (Q2); the threshold comes from the
   sign-off, not from this spec. ⚠️ **This binds SERIES — not piece 1's four-command list, not piece 2's edits (reviewed, never series-graded until the sign-off: Q3's grading clause is what waits), and not piece 3's ratchet.** Read any wider,
   this constraint would make D4 — an approved decision (D-224) — unrunnable until an operator-triggered sign-off that § D3
   records as never run, which is not what the constraint is for: the noise floor exists to stop a
   *published metric* firing a verdict on noise. The four-command list publishes no metric; it says
   whose close gets a subagent-written `change:`. The ratchet is one committed number that warns and
   never reds. So none of the three is blocked by this constraint — the build order is § D4's sequencing — and
   only the RE-DERIVATION of the list waits on the sign-off, for the reason § Who builds what
   gives: when to re-cut is an output of the sign-off, like Q2's minimum-n.
5. **Nothing in `~/.claude/state/` is written by a review of this spec** — regenerating the noise floor
   IS the operator's M1→M2 sign-off, and an agent running it would forge the evidence.

## Lifecycle

- **D3 first, and it is not code.** Until the sign-off happens, every series is publishable and
  unadjudicable — today's state.
- **D1 then Q4.** D1's series publish from the day the reader ships, `era` recorded, back-filling
  nothing. Q4's unit is settled (v2's transcript tokens); its guardrail waits on M1→M2, not on a ruling.
- **Graded by its own first prediction.** `command_tokens_per_round` exists to test D-203's claim that
  delta rounds lower cost per round. If it does not fall, the prediction was wrong and the series
  earned its keep by saying so.
- **D4 runs in PARALLEL with D1, and does not wait on D3.** Order inside D4 is set by the live tree,
  not by preference (§ D4 sequencing): pieces 3 and 4 now — the ratchet's script first, its baseline
  seeded only after infra's corpus edits land, and the tokens-per-round report last — then pieces 1
  and 2 once infra's review-family plan releases `assemble_commands.py` and the two `CLAUDE.md` files. Only the re-derivation of
  piece 1's list waits on the sign-off (Constraint 4 as narrowed); Q4's token guardrail waits on it
  separately and is not piece 3. D4 is the largest approved item (D-224) and the one whose absence from
  this section was a real defect until round 9.
- **Extends v2, never supersedes it.** A conflict is resolved in v2's favour unless a D-row says
  otherwise — and Q4 is the worked example: the conflict was real, v2 won, and no D-row was owed.

## Open — needs the operator, not derivable here

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
- **D4's own hazards are residual risks of this spec, not just cited literature — re-cut for the
  four pieces.** (a) **Self-preference** still applies to piece 1: the subagent reviewing the
  instructions is the same model family that executed them. The mitigation is the record's SHAPE — a
  quoted instruction plus executed evidence, never a score — which leaves nothing to prefer; a key
  with no quoted instruction is an empty record, not a verdict. (b) **Piece 2 is a duty, and this
  ledger's own relay proves a duty in prose can sit unread under 200 items.** The risk is that
  `/fabrik-command-improve` never runs. The test is countable: applied-edit commits carrying its trailer on `commands/_sources/` in its
  first fortnight; zero is the finding. (c) **Axis keys can hollow the field.** An agent that writes a
  key and no edit satisfies the format and defeats the purpose; `feedback_substance` (Q2) is the counter
  and it already measures the predicate. (d) **Reward-model drift** — feeding edits back into the
  instruction files is reward-model optimisation, and "lean" is satisfied by writing LESS; `feedback_substance`
  counters that for tokens-per-round, and the byte ratchet has NO counter of its own — a clause deleted
  to satisfy the ratchet is caught only by piece 2's review path, which is why the ratchet warns and never reds.
- **This spec measures a ledger that grows while it is being read.** `feedback_substance` moved
  40/102 → 44/108 → 44/109 during the review, and the `change:` length statistic changes its median with
  a single appended row (`## Reproduce`, R7). ⚠️ **An earlier version of this bullet also claimed the
  `manifesto` count had aged 0 → 1; it had not** — that "1" came from searching two fields R4 excludes.
  The instructive part is the shape of the error, not the number: a figure re-derived with a predicate
  other than the metric's own will drift for reasons that have nothing to do with the system. Every
  LEDGER figure is
  therefore stamped with its row count and `## Reproduce` gives the command; the corpus-byte table is
  dated at its section header instead, because those bytes move with every sibling commit and a per-row
  stamp would be stale faster than it could be written. A ledger figure without both is a defect.

## BLOCKED: NON-CONVERGENCE — the 1c blocker LIFTED, the loop RE-BLOCKED at round 14 (2026-09-11)

**The blocker was the 1c approach floor, and it is cleared.** Four parallel `fabrik-researcher` seats
grounded the approach space on 2026-09-11; § External facts and the approach floor lists **18** distinct
cited URLs against a floor of 2 (12 when this paragraph was written; round 9 added six while correcting
the misattributions and the paragraph had not caught up — a count stated about the document's own list
and never re-counted, which is the banner rule turned on its author). The earlier § External facts claim ("this design has no external
facts") was wrong in exactly the way the checker's comment predicts, and is withdrawn.

**The stall series is also explained rather than merely survived.** Confirmed defects ran
`17 · 5 · 5 · 4 · 3 · 1 · 2 · 4 · 26 · 23 · 13 · 3 · 6 · 7 · 7` across **fifteen** rounds (the
first draft of this sentence printed fourteen values and called them fourteen rounds; round 15's `7`
was in the event stream and cited ten lines below it — infra's correction of 2026-09-12 on mail
`01M28VKD807M6QZB31NJ5D9W1T`). Provenance, because the banner demands the producing artifact: every one
of the fifteen `confirmed` values is a `round` event in `~/.claude/state/events/<sid>.jsonl` — the ONE
artifact that holds them all; the run record this sentence once cited for rounds 9–14 carries
`rounds: []` today. By the spec's own convention (three consecutive rounds whose `confirmed` counts are
non-decreasing and nonzero) the breaker fires at FOUR windows of this series — rounds 6–8
(`1 · 2 · 4`), rounds 7–9 (`2 · 4 · 26`), rounds 12–14 (`3 · 6 · 7`) and rounds 13–15 (`6 · 7 · 7`); the
paragraphs below name the first and the third, the second is the first read one round later, and the
fourth is the third read one round later — two firings, each seen twice, no exception.

⚠️ **Two corrections to this very series, both found by round 14, and the second is the more serious.**
(i) The 11th value was written as **14**, which is round 11's *findings* count; its confirmed count is
**13** — a findings figure sitting inside a sentence that cites the rule forbidding exactly that
(D-206: refuted candidates never count). (ii) An earlier edit **deleted round 12's `3`** and moved round
13's `6` into its slot. The effect was not neutral: with the 3 removed the tail read as monotonically
falling, and the sentence below claimed it was. **It is not.** The tail is 13 → 3 → 6; round 13 ROSE.
The document had been edited into telling a tidier story than the record supports, by its author, in the
section whose subject is exactly that failure.

⚠️ **THE STALL CIRCUIT-BREAKER HAS FIRED, and it fired one round before this sentence admits it.**
The rule is three consecutive rounds whose `confirmed` counts are non-decreasing and nonzero. The
document's own precedent fixes the convention: rounds 6–8 are `1 · 2 · 4` and are recorded above as
having tripped it. By that same convention rounds 12–14 are `3 · 6 · 7` — **the breaker fired at round
14, and round 15 should not have been dispatched.** ⚠️ That verdict binds THIS loop's scope and no other:
rounds 16–23 are the amendment review, a new scope the operator opened on the D-234 re-cut, and round 24
is the residue pass opened on their word after that — so neither is a round this breaker forbade
(§ Amendment review). An earlier draft of this paragraph counted
transitions instead of windows, concluded "two rounds away", and so licensed the very round the rule
forbade. Counting one's own stopping rule loosely, in the paragraph that announces it, is the finding —
not the arithmetic.

**The foundation error, stated as the breaker requires and corrected where the first attempt
over-claimed:** rounds **10–15** each confirmed defects that the PREVIOUS round's fixes — rounds 9–14's — introduced —
two `## Reproduce` recipes that did not regenerate their own figures, a splice, an over-claim about the
registry, and an edit to this very ledger that erased the one round where the count rose. (Round 9 is
NOT in that set: § D4 was new text having its first read, which the paragraph below says plainly.) The
**fixer** was the same agent in every one of those rounds; the **finders** were not — the record stamps
3 seats at round 9 and 2 at round 10. So the invariant is narrower and sharper than the first draft
claimed: *a fresh reader found each defect, and the same author wrote every fix, and that author's fix
seeded the next round.* That is a process property, not a text property. No further round of this shape
closes it — which is why this section ends the loop instead of ordering a round 16.

⚠️ **There are now TWO foundation errors on this document and they must not be confused.** The FIRST,
named at rounds 6–8, still stands and is fixed at the root: **a static document was carrying live
measurements of a shared, moving system** — § Reproduce and the row-count stamps are that fix. The
SECOND is the one above, named at round 14, and it is NOT fixed: it is a property of who writes the
fixes, and no edit to this document can close it.

⚠️ **Why rounds 9–12 were not the stall, even though rounds 12–14 became one.** Rounds 1–8 reviewed
D1/D2/D3; § D4 was written after round 8 and had never been read by anyone but its author when round 9
opened. A first read of new content is not a loop failing to converge — but round 9 also proved that
the fix above had NOT reached the section written last: D4 carried **zero** producing commands and
**zero** row stamps while Q2 and Q5 carried eight between them, and five of its citations named papers
that do not contain the figures credited to them. So the sentence that used to stand here — *"every
remaining figure either carries its producing command or is stamped with the row count"* — was true of
the document round 8 saw and false of the document round 9 read. It is true again now for every LEDGER figure, and § Reproduce is what makes it checkable rather than
asserted. **Round 10 then proved the same lesson one level down:** § Reproduce was itself written by the
round that found the defect, with no reader between, and its R4 recipe did not reproduce the table it
was cited for — naming five fields where three are right, which inverted one axis's ranking 21-fold.
A fix written by the finder is the highest-risk text in any document, and the only thing that catches it
is a fresh reader who EXECUTES the recipe rather than reading it. Round 10 also refuted an inference the
first nine rounds carried unchallenged: three true zeros about the manifesto were read as neglect when
they are the designed outcome of an EXECUTED 34-ticket governance pass.

**What the research changed, beyond clearing the floor** — three findings reversed decisions this spec
had already made, which is the strongest argument that the floor was worth enforcing:
1. **Q4's unit**: v2's transcript-tokens adjudication was RIGHT and this delta's disk-bytes proposal was
   weaker. No superseding D-row; adopt v2's unit.
2. **Q4's escape hatch**: needs no new machinery — a committed number gets single-use binding free from git.
3. **Q2's counter**: needs VETO-ONLY authority, which the registry schema cannot express.

Superseded verdict, kept for the record: the spec was BLOCKED at round 8 pending an operator ruling on
whether to do the approach research or exempt the delta. The research was done.

---

## The ONE operator question the breaker owes you

**Every CONTENT defect this review found is fixed.** What is not fixed, and cannot be fixed by another
round of the same shape, is that **the same agent wrote every fix** — and each fix that agent wrote in rounds 9 through 14 seeded the next
round's defect, six times running (round 15 confirmed round 14's residue and the loop stopped there; rounds 16–23
belong to the amendment review below, a new scope opened on the operator's word). Fresh readers found them all; the author
closed them all; the closing is where the next defect came from.

**THE QUESTION — who writes the residue?**

**RECOMMENDED: nobody, here. Approve the spec as it stands and let `/fabrik-plan-after-chat` absorb the
remainder**, for three reasons that are checkable rather than felt:

1. **The content converged; the process did not.** Rounds 13–15 confirmed 6, 7 and 7 — and every one was
   a wording, arithmetic or round-accounting defect inside a previous fix. Not one was a defect in the
   DESIGN: not the three tiers, not the selector, not the verdict's destination, not the eight axes, not
   the cadence, not a citation, not a ledger figure — the first draft of this list said so and was wrong
   twice: round 13 struck a false claim about what `validate_registry` forbids ("for an odd axis count it
   forbids it outright"), load-bearing for tier 1's rationale, and corrected a word count in § D4 ("the": 956 → 1,052);
   the list was also wrong about the DESIGN itself, as the ⚠️ ANSWERED note below records. What holds is
   narrower: from round 12 the content changed only under rounds 13–15's delta reads (one fresh seat each,
   scoped to the previous fix diff — not three independent re-derivations of the whole).
2. **The plan stage supplies a different surface and its own review loop** — but NOT, by itself, a
   different author: `/fabrik-plan-after-chat` changes no author, and the same session ran it six
   minutes before this amendment was pinned (backlog row `d01a378a`). Only a different SESSION breaks the
   finder-is-fixer identity, which is what the ⚠️ ANSWERED note below records and what happened.
3. **The alternative is measurable and worse.** Fifteen rounds have cost far more than the residue is
   worth. (The residue this sentence first listed — an enumeration saying "four" and a provenance phrase
   naming one artifact — was fixed by the very diff that wrote the list; the nine wording residues that
   actually remained are the ones infra fixed on 2026-09-12 from mail `01M28VKD807M6QZB31NJ5D9W1T`.) None
   changes a build decision.

If instead you want this document closed to zero here, the answer is not another round by me — it is to
hand the residue to **infra** as a scoped fix request, and let a second session's author write the fixes
a first session's seats found. That is the only shape that breaks the loop, and it is yours to call.

⚠️ **ANSWERED 2026-09-11 — and the answer was to the design, not to the question.** The operator did
not choose between the two options above; they said *"i dont think you have understand what i asked
for"*, and the re-read confirmed that reason 1's list — *"not the three tiers, not the selector … not
the cadence"* — named as settled exactly the things that were wrong: the three tiers, the selector and
the cadence were answers to a misread ask (**D-234**). § D4 was re-cut in `ad612bc6`, the eight-axis
table the re-cut had deleted was restored in `df349acd`, and the sections outside § D4 that still
described the tiers were re-cut in the round-zero sweep of the amendment review below. The nine wording
residues remain with infra (`01M28VKD807M6QZB31NJ5D9W1T`, backlog row `d01a378a`). The recommendation
above — let `/fabrik-plan-after-chat` absorb the remainder — does NOT stand as written: backlog row
`d01a378a` records that the same session ran that command six minutes before the amendment was pinned,
so it breaks nothing; only a different SESSION breaks the finder-is-fixer identity, which is why the nine
sit with infra. The design defect was not theirs to absorb either.

⚠️ **RE-BLOCKED 2026-09-12 at round 23 — the ONE operator question, again.** The amendment review
(§ Amendment review) fixed 18 · 13 · 9 · 7 · 1 confirmed defects over rounds 16–20, the design
content holding under execution from round 20 (every count re-derived exact, every mechanism claim
executed, the four-command list re-derived from its own rule). Rounds 21–23 then confirmed 2 · 1 · 3 —
every one a claim in the ledger's own rows about themselves, and round 22's edit was the third patch to
one sentence, which D-231 names as the foundation error. The three-window breaker never fired; the
finder-is-fixer identity did, in the same shape as round 14. **The question is unchanged: who writes
the residue — and the answer is the same: a different session.** The residue is small and named in
row 23 (a `found:` of 6 that is 4, a column the no-fix clause leaves undefined, two wordings, two
out-of-hop notes). Nothing in it changes a build decision; `/fabrik-plan-after-chat` for pieces 3 + 4
proceeds from the content as it stands.

⚠️ **ANSWERED 2026-09-12 (round 24) — and this time by a different AUTHOR, which is what the question
asked for.** Round 23's residue, together with the three corrections the pieces 3 + 4 plan review forced
(the ratchet's WARN reference, **D-240**; Constraint 2's OWNS-not-HAS and the six budgeted surfaces,
**D-241**; the superseded plan citation, **D-244**), was AUTHORED by a separate fixer agent — a fresh
session dispatched by the orchestrating one from the findings and the decisions, not handed the wording
to transcribe. That is the mechanism the plan review MEASURED rather than argued: its residue rounds
stopped once the fixer authored the fixes instead of the orchestrator dictating them (the plan's § Pass
Ledger rows 5–10, D-244 — confirmed 31 → 23 → 13 → 6 → 6 → 1 → 5 → 3 → 1 → 0). The closing round of this
loop is likewise a fresh non-authoring seat. So the finder-is-fixer identity § BLOCKED named at round 14
is broken at the process level here, not talked past in prose — and the pieces 3 + 4 plan, CONVERGED IN
FACT and held only by this spec's `Status`, is what the loop was holding up.

## Amendment review — rounds 16+ over the D-234 re-cut (`/fabrik-spec-review`, amendment-scoped, 2026-09-11)

**Scope, as the operator set it:** the D-234 amendment only — `3639ba6e..df349acd` (2 hunks, 64/151
lines — git's count across those two commits alone, which is a different span from row 16's *11 hunks*:
that figure is pin → pin and includes the round-zero sweep, so the two numbers measure two different
things and neither corrects the other) plus the round-zero class sweep above — and the one-hop sections
whose text cites § D4. The
fifteen earlier rounds' classes stand as the spec's § BLOCKED records them; nothing outside the hop is
re-read. **The author of the amendment is the orchestrator of this review** (the same session, after a
compaction), which is the finder-is-fixer shape § BLOCKED names — so every finder is a fresh native
seat, every verdict is executed by the orchestrator, and a delta round whose confirmed defects sit
inside the previous round's hunks twice running forces a paragraph rewrite (D-231), never a third patch.

**Round zero (orchestrator pre-pin sweep — authoring, not a pass):** `check_review_hygiene.py --surface <spec> --claim <term>`
over `tier 1` · `tier 3` · `judge` · `attach-list` · `percentile` · `cadence` · `selector` listed the
mirror sites; the re-cut had reached § D4 only. Rewritten in ONE batch: the Status line, § The delta's
D4 row, the D4 heading and its "verbatim" ask (which was a paraphrase — the actual words are now
quoted), the four-piece table (the `change:` substance figure had borrowed the `waste:` field's 91 of
107; the four-command share and the seat cost re-derived at 116 rows), § Who builds what (six tier rows
→ five piece rows), § Constraints 2 and 4, § Lifecycle's D4 bullet, § Self-audit's D4 hazards, the R1/R8
labels, and this postscript. `grep -n -i '\btier'` over the spec lists every remaining occurrence, and each is history or another sense — ⚠️ notes, § What this supersedes, the operator question's account of rounds 13–15, this review's own account and ledger rows, and kaizen's registry term *"outcome tier"* in § Approaches — none is live design. (The superseded plan's filename was a sixth category until round 24 re-pointed its three citations at the live plan, whose name carries no `tier`.)

**THE LEDGER CONVENTION — PIN, `edits:` and the md5 cells, defined once.** A round's **pin** is the snapshot its SEATS READ: the md5 in the start half of its `spec md5 (start → end)` cell, and the file of that md5 kept in the review's scratchpad. A round's **`edits:`** is the count of `@@` hunks, at `diff -u`'s default three lines of context, in the diff from its own pin to the NEXT round's pin — counting only the hunks that round's FIXES applied. **A hunk is the unit, and the rule is per hunk:** a hunk is COUNTED if it contains at least ONE of the round's own fixes, and EXCLUDED if it contains none. Three kinds of region can sit inside the span without being a fix — a **sibling's commit** landing in this shared tree between the two pins; a **pre-pass AUTHORING step**, which its own paragraph records and which belongs to no row's `edits:`; and the round's **own record**, its ledger row plus the § BLOCKED postscript and the Status paragraph's restatement of that block — and each is NAMED in the row, never SUBTRACTED from a hunk it shares. Subtracting is what is not executable: at three lines of context a non-fix region coalesces into a neighbouring fix hunk, so the hunk exists either way and there is nothing to take away (round 24's own row sits inside its eighth hunk beside a fix to row 23 — deleting the row line still leaves 8). So the figure is regenerated from the two pins *plus* that attribution, never from the pins alone; and because excluded hunks coalesce with kept ones at three lines of context, a row's legs can sum HIGHER than the span they compose to, which a reader checking the arithmetic must expect rather than treat as an error. Two degenerate shapes: a round whose ONLY edits are its own record is **record-only** and reads `edits: 0 (record-only)`; a round with no next pin at all reads `edits: 0` and carries, in place of an end hash, the note that the working tree equals its start pin. Rows 16–22 reproduce 7 of 7 from their own pins (14 · 8 · 7 · 5 · 4 · 3 · 2, regenerated at round 24); rows 16–20 were restated under this convention at round 21, having counted replacement sites, which no diff reproduces.

**Round 24 residue authoring (2026-09-12, orchestrator's pre-pin step — authoring, not a pass):** the fixes row 23 left unwritten were AUTHORED by a separate Opus fixer agent from the findings and decisions (the plan review's measured remedy, D-244), never dictated by the orchestrating session: Constraint 2 rewritten to OWNS-not-HAS with the six surfaces and the worktree write-gate (D-241); § D4 row 3 to D-240's delta WARN with the measured fire rate; § D4 row 4, § Approaches and § Who builds what re-pointed from the removed plan to `docs/development/plans/2026-09-12-plan-1-kaizen-corpus-weight-and-tokens-per-round.md` with Phase B's tokens-per-round definition; the `edits:`/md5 recipe paragraph rewritten whole (D-231) instead of a fourth patch; two reconciling clauses (the 2-vs-11-hunk measurements, the breaker's scope); the RE-BLOCKED paragraph answered; and the Status paragraph's narrative cut from 15 lines to 12 — one paragraph before and after, with three retellings of one story dropped: the rounds 9–14 confirmed series with its examples, a second statement that the breaker fired at round 14, and a second attribution of the misread ask to D-234. Items (a), (b) and (d) of row 23 were found already applied by infra at a63bda73 and left. Pre-pin sweeps: **0 live sites** for `--claim "surfaces a repo"` and for `--claim "plan-2-kaizen-tier1"` — each term still returns exactly ONE hit, on THIS sentence's own quotation of it, which is the only place either string survives; 14 tables square. This step's diff is `04f2a2e1` → `118eeec8` — **9 hunks** — and it is **no row's `edits:`**. `118eeec8` is round 24's PIN, the snapshot its seats read, so these hunks sit INSIDE row 23's pin → next-pin span and are excluded from it as a pre-pass authoring step (the convention above); `04f2a2e1` is the snapshot this step started from, not any round's pin; and row 24's own `edits: 8` is measured over its pin `118eeec8` → round 25's pin `6291c5ee`.

| Pass | seats · sections re-checked | counters | method | spec md5 (start → end) |
|-----:|---|---|---|---|
| 16 (the amendment's full pass) | opus×1 (rule sections + every count) + sonnet×1 (prose + the document's claims about itself) · the amendment's 11 hunks + one hop (Q2 · Q3 · Q4 · Q5 canary 4 · R3/R6 · D-234) | found: 21, new: 21, confirmed: 18, fixed: 18, unexecuted: 0, edits: 14 | method: citation — full pass over the amendment; every ledger count re-derived at 116 rows (10 exact); 5 orchestrator probes pinned as scripts (`<scratchpad>/kaizen-amendment-review/probes/`: seat cost, relay cadence, report per-round, ratchet pattern, fragment append). Confirmed classes: false instrument facts (relay "hourly" is daily; "blocks nothing" is first-run-only; axes 3 and 7 named checks that grade plans, not commands), design contradictions the round-zero sweep introduced (piece 2 wired to an M2 fix ledger behind the sign-off; the gap named at step 3; the percentile cut in two pieces; seven keys for eight axes; Constraint 2's count low by `final_gate.py` and the ~46-repo blast radius), stale stamps (44/108 in a 116-row cell), the "verbatim" ask silently normalised (`weeAkly`), the sequencing reason not true of the file it names, the hygiene invocation missing `--surface`, a self-claim about `tier` falsified by § What this supersedes, a recommendation the cited backlog row had killed, the `.md`-only byte bound undeclared. RECORDED — measured (wording, one hop): the comma splice in the manifesto note. RECORDED — filed: the Status paragraph's *"Rounds 9–14 confirmed …"* sentence (the nine, `01M28VKD807M6QZB31NJ5D9W1T`). RECORDED — by design: this table empty while the round ran. RECORDED — cross-artifact: D-234's WHY carries the `waste:` figure as `change:` — erratum row D-237, immutable-row discipline. One-hop stamps in R6/Q2 corrected, uncounted · mirrors: 4 read (`Q3 fix-ledger row` sites — 2 rewritten in the batch, 2 caught by the phrase sweep) | 0874225a… → 6d5def1d… (the round-17 pin) |
| 17 (delta) | opus×1 (fresh; rule hunks + counts) + sonnet×1 (fresh; prose hunks + the ledger's self-claims) · round 16's fix diff (84 changed lines, 14 hunks) + one hop (Q3 · Q4 · D3 · D-234/D-237 · the lock JSON · `final_gate.py` · the synced manifest) | found: 14, new: 14, confirmed: 13, fixed: 13, unexecuted: 0, edits: 8 | method: re-derivation — every count re-derived at 117 rows (10 of 10 exact, incl. D-237's `91 of 107` as the `waste:` rate); byte figures, the lock's owned paths, the relay cadence, `Agent-Context` parsing (200 of 200), `check_command_corpus.py`'s registration all executed. Every confirmed defect sat INSIDE round 16's hunks — the second consecutive residue pass, so per D-231 this round's edit is a **class rewrite — the piece-2 and piece-3 cells, the axis-3 cell, Constraint 4's conclusion, § What this supersedes' percentile sentence** — from the seats' executed evidence, not a third patch. Confirmed: a false universal in axis 3 (`check_command_corpus.py` DOES grade existence over the corpus); `rows <ids>` naming a ledger field that does not exist (`ts` is the only per-row handle); "the eighth" for axis 5; "both run now" over a three-item exemption; Constraint 4 deferring the cut on a principle it had just exempted; Q4's two failure modes mis-mapped and a "gate" that only warns; a sentence stating the converse of its intent; "keeps its MECHANISM" across a per-row→per-command change; the seat figure cited to R3, which contains no seat recipe (R9 added); one `[sic]` on a quote that preserves the other typo unmarked; the mirror count 2 where 4 sites were rewritten; "the Status line" for a sentence in the Status paragraph; a self-check whose categories missed kaizen's own "outcome tier". RECORDED — out of hop, destinations named: § Q3's closing "(the fix-ledger row)" location sentence — row 2 now carries Q3's declaration, Q3 itself untouched (next non-delta pass); D-234's WHY quoting `not weekly` — second erratum in D-237, same change; the ledger header's "Append-at-top" vs D-228…D-237 appended at the bottom — filed to infra at close; trade-intelligence's dangling `D-007 supersedes D-048` — mailed to trade-intelligence at close. RECORDED — measured (historical illustration): § Self-audit's `40/102 → 44/108 → 44/109 during the review` | 6d5def1d… → 081b639e… (the round-18 pin) |
| 18 (delta) | opus×1 + sonnet×1 (fresh; the first pair DIED on API timeouts at 97% quota and read nothing — dispatched 4, returned 2) · round 17's class rewrite (35 changed lines, 8 hunks) + one hop | found: 9, new: 9, confirmed: 9, fixed: 9, unexecuted: 0, edits: 7 | method: re-derivation — 19 numeric claims re-derived at their stamps (19 of 19 exact), `check_command_corpus.py`'s eight predicates and its BLOCKING registration read, Q4's re-baselining paragraph quoted, `ts` uniqueness (117 of 117) and `Agent-Context` parsing (200 of 200) executed. Every confirmed defect sat inside round 17's rewrite — the third consecutive residue pass, of falling severity (18 · 13 · 9); the one design defect: the round-17 "per-command token mass" criterion selected a DIFFERENT four commands than the list the same section named (`fabrik-plan-review` outranks `fabrik-spec-review` by R3's mean) — the list now follows its rule as a RANK CUT (top four by R3's per-command mean), re-derived at 116 rows, and "percentile" is retired for the selector because a p90 over 14 commands admits two. Also: "token mass" for R3's MEAN; "all three run now" contradicting § D4's sequencing; the piece-3 cell both conditioning and not conditioning the verdict on a D-row; "the fifth" inside a seven-item list; "next run" for a same-run re-seed; R9 silent about the shipped reader's cache-inclusive `_TOK`; Constraint 4's exclusive reason omitting the row's second reason; the `tier` self-check falsified by the operator question's "three tiers" and a second "outcome tier" in row 17. **The fleet-quota HOLD landed while this batch was being written**: rounds 16–17 were committed at `536a5562` with this round's fixes UNAPPLIED, the record closed BLOCKED, and the batch was applied at relief on a new record before pin 19. RECORDED — out of hop, destinations: § Q3's location sentence (unchanged, next non-delta pass); § Q5's figures stamped at 102 rows beside D4's at 116 (§ Reproduce preamble's discipline, next full pass); `command_feedback_report.py`'s `_TOK` includes cache with no flag, and a `test_cmd` fixture row sits inside every `of 116` denominator — both to piece 4's plan as machinery findings | 081b639e… → 05d717e5… (the round-19 pin) |
| 19 (delta) | opus×1 + sonnet×1 (fresh) · round 18's fix diff (30 changed lines, 7 hunks) + one hop; both seats returned | found: 7, new: 7, confirmed: 7, fixed: 7, unexecuted: 0, edits: 5 | method: re-derivation — 12 of 12 rank-cut figures and 4 of 4 R9 figures exact at 116 rows (ledger live at 122); the contradiction sweep over every site naming the four commands or a percentile executed (0 of 3 / 0 of 6 live). Confirmed, all inside round 18's hunks (the fourth residue pass, still falling: 18 · 13 · 9 · 7): "6th" where `fabrik-spec-review` ranks 7th of 14; R9's clause describing a per-command MEAN and "~400×" for a reader that publishes a MEDIAN over rows-carrying-tokens at 200–320×; Constraint 4's second reason truncated to a non-reason; the selector's lead sentence keeping a dependency the same round's Constraint 4 lifts; the p90 sentence naming neither mean nor mass; the D-row fact stated twice in one cell; the `tier` self-check's categories missing the round-zero paragraph's own search terms. RECORDED — out of hop: the piece-3 cell's "re-baselining upward binds" presupposes a blocking gate the same cell says this one is not (pre-existing text; next full pass); the shipped reader's median-vs-mean and rows-carrying-tokens divisor → piece 4's plan with the `_TOK` finding | 05d717e5… → 713f4e5f… (the round-20 pin) |
| 20 (delta, one seat) | opus×1 (fresh) · round 19's fix diff (17 changed lines, 5 hunks) + one hop; the hygiene script on the pin (0 hits) | found: 3, new: 3, confirmed: 1, fixed: 1, unexecuted: 0, edits: 4 | method: re-derivation — 38 claims re-derived, 37 held: the rank (7th of 14), the reader's `median_tok` at 200–320× and 0.01–0.04%, the p90 in all four variants, the ledger span (4.84 d at 116 rows), the `tier` sweep (17 of 17 covered), the md5 chain and row shapes. CONFIRMED: Constraint 4's second deferral reason cited § Q6's 30-day replay, which runs over COMMITS (2,036 in the window today) and gates an advisory→blocking promotion piece 3 never proposes — deleted at both its sites (the Who-builds row carried it first; corrected in the same batch, uncounted). RECORDED — measured (wording): the reader's median is 167,069,998.5 (the `.5` restored); `edits:` had no recipe (one sentence added above this table). RECORDED — out of hop: `commands/_sources/` 1,042,530 B is exact at HEAD and 1,043,673 B in the live tree with sibling WIP — a byte figure with no as-of stamp (§ Reproduce preamble, next full pass); a comma splice in § What this supersedes' lead sentence (pre-existing context, wording) | 713f4e5f… → 30620591… (the round-21 pin) |
| 21 (delta, one seat) | opus×1 (fresh) · round 20's fix diff (14 changed lines, 4 hunks) + one hop; hygiene 0 hits | found: 7, new: 7, confirmed: 2, fixed: 2, unexecuted: 0, edits: 3 | method: re-derivation — 22 claims re-derived, 20 exact, 2 marginal, 0 false (Q6's characterisation exact against § Q6; the rank cut, `median_tok`, R9, the md5 chain, row shapes, the `tier` sweep 18 of 18). CONFIRMED, both inside round 20's hunks: Constraint 4 said "the reason § Who builds what gives" while that row had been given a second clause in the same batch — the second clause DELETED, one reason at both sites; the `edits:` recipe named replacement sites, which no diff reproduces (row 20 read 5 against 6 sites or 4 hunks) — recipe replaced by the hunk count and rows 16–20 restated. RECORDED — measured (wording): the ledger span re-derived at 123 rows where the claim is stamped at 116 (4.84 d, corrected); "0.01–0.04%" whose low end is 0.0094% (rounds to the stated precision); "2,036 in the window today" with an undeclared ref scope; `fixed:` counting confirmed items only while the round also applied its recorded ones (the receipt grammar's `fixed ≤ confirmed`, kept); drafting history inside a binding Constraint — deleted. RECORDED — out of hop: § Q4's "our check needs that second gate" beside a WARN-only ratchet (recorded at round 19; § Q4/piece-3 cell, next full pass). Series 18 · 13 · 9 · 7 · 1 · 2 — every confirmed item of rounds 17–21 inside the previous round's fix (round 16 was the full pass) | 30620591… → bcdab345… (the round-22 pin) |
| 22 (delta, one seat) | opus×1 (fresh) · round 21's fix diff (19 changed lines, 3 hunks) + one hop | found: 4, new: 4, confirmed: 1, fixed: 1, unexecuted: 0, edits: 2 | method: re-derivation — the one-reason fix at its three sites, the `edits:` recipe executed for all six pinned pairs (6 of 6 exact, regenerated), the md5 chain (7 pins), the `tier` sweep (19 of 19). CONFIRMED: row 21 misstated the spec's breaker rule ("confirms anything" — a count of 1 gives 1 · 2 · 1, not non-decreasing); the sentence deleted. RECORDED — measured: the recipe's context depth and its value for a no-fix round (both added to the recipe); "the rise is on wording" (deleted). RECORDED — out of hop: § BLOCKED's breaker is the spec's own convention, distinct from `command_run.py`'s advisory window (§ BLOCKED, next full pass) | bcdab345… → d0b6a5dd… (the round-23 pin) |
| 23 (delta, one seat) | opus×1 (fresh) · round 22's fix diff (5 changed lines, 2 hunks) + one hop | found: 5, new: 5, confirmed: 3, fixed: 0, unexecuted: 0, edits: 0 (record-only) | method: re-derivation — the `edits:` recipe regenerated from the pins for 7 of 7 rows, the md5 chain 7 of 7, the breaker arithmetic (20·21·22 = 1 · 2 · 1, no trip), the table shape 9 of 9 lines. CONFIRMED and DELIBERATELY UNFIXED: row 22's `found: 6` is 4 by the convention rows 18–21 obey; the recipe's no-fix clause defines `edits:` but not the `spec md5 (start → end)` cell for a round with no next pin; round 22's patch to the recipe sentence was the THIRD patch to one sentence (added at 20, replaced at 21, patched at 22) — the D-231 foundation error. RECORDED — measured (wording): "every item inside the previous fix" read against round 16, which was the full pass; "its" in "at its default 3-line context". RECORDED — out of hop: "2 hunks" (l.~1002, git's count at 3639ba6e..df349acd) beside "11 hunks" (row 16, pin→pin incl. round zero) — two measurements of two things; § BLOCKED's "round 15 should not have been dispatched" beside rounds 16–23 dispatched under a new scope. ⚠️ **`edits: 0 (record-only)` is ACCOUNTED, not asserted** — added at round 24, when this row's original *"no next pin"* reading was found false, and re-derived at round 25 against round 24's real pin: the span from this row's pin `d0b6a5dd` to round 24's pin `118eeec8` is **13 hunks**, and not one of them is a fix this round applied. 3 are this round's own record (at `9b8726be`: this row, the § BLOCKED postscript, and the Status paragraph's restatement of that block); 7 are a SIBLING's work (infra's `a63bda73` + `418f86b0` + `4662aad1`); 9 are the round-24 pre-pass authoring recorded in its own paragraph above. The three legs read 3 + 7 + 9 = 19 and compose to 13 — adjacent regions coalescing, exactly as the convention says to expect. And the wording item this row RECORDED — *"its"* in *"at its default 3-line context"* — was applied by infra at `a63bda73`, not here: round 23 wrote record and nothing else, so no wording edit is counted against it. **The loop stops here**: the series 18 · 13 · 9 · 7 · 1 · 2 · 1 · 3 never trips the three-window rule, but since round 21 every confirmed item is this ledger describing itself, written by the amendment's author — the shape § BLOCKED named at round 14 | d0b6a5dd… → 118eeec8… (round 24's pin; the span is 13 hunks — the accounting is in the method cell) |
| 24 (delta over the residue authoring — opus rule seat + sonnet prose seat) | opus×1 (fresh; Constraint 2, § D4 rows 3–4, the plan citations, the recipe paragraph, row 23, the authoring paragraph; one hop into § Q4, § Q5 canary 4, § Q6, § Lifecycle, § Self-audit and the reviewed plan's Interfaces + Evidence) + sonnet×1 (fresh; the Status paragraph, the ANSWERED note, the two reconciling clauses, the `\btier` category list, the Date line) · delta over the round-24 authoring diff (55 added / 27 removed lines, 9 hunks) + one hop | found: 10 (5 confirmed, 4 refuted on execution, 1 recorded wording in hop), new: 10, confirmed: 5, fixed: 5, unexecuted: 0, edits: 8 | method: re-derivation — ownership (1 of 49 `/opt` dirs with a root `CLAUDE.md` holds `commands/_sources/`; 18 of 18 registered worktrees carry it; `.git` a directory in the main checkout and a file in a worktree; 3 of 3 sampled project templates byte-identical), the 30-row walk at `acb50492` (6 of 6 rise counts, 29 comparisons, mean 16.8), rows 16–22's `edits:` regenerated from their pins (7 of 7 exact), the plan's Phase A/B anchors and `command_feedback_report.py` (`_TOK` :103, the flat lists :170/:195, no per-round reader), 14 tables square. Confirmed: the rewritten recipe's no-fix premise was false for row 23 (a next pin exists and the raw span is 9 hunks measured to the PRE-AUTHORING snapshot `04f2a2e1` — 13 to round 24's actual pin `118eeec8` — with 7 of those hunks a sibling's a63bda73/418f86b0/4662aad1; the convention now counts a hunk only when it carries one of the round's own fixes, names every non-fix region inside a counted hunk, and defines record-only rounds; row 23 reads `edits: 0 (record-only)` with the accounting in its cell); the authoring paragraph's "→ 0" sweeps returned 1 each, on their own quotation (now said, and its pin identifier corrected); row 3 had dropped the disclosure that the D-row citation on a baseline raise is a review convention the check does not read (restored: `--reseed` writes unconditionally, 0 of 15 Phase A graders read a D-row); row 4's "cache excluded on both sides" was vacuous over a divisor of `rounds` and § Q5's `T` was unqualified (both now Σ(`tok_in`+`tok_out`), cache excluded, per the plan's § Evidence); the Status rewrite's comma splice (split, and D-240/D-241/D-244 attributed to their minting moments — the sonnet seat's recorded item, applied). RECORDED — in hop, applied as wording: row 4's dangling clause (inside `found`, never inside `confirmed`). ⚠️ **Three OUT-OF-HOP items were also applied in this batch, which D-230 does not sanction, and saying so is the point** — § Q2's registry row (rows carrying BOTH, four `rows_*` keys), § Q4's "second gate" sentence and the Date line: each was a contradiction of THIS spec's own design, two of them created by the in-hop change itself, so naming them with a destination would have published a document that contradicts itself. Under this ledger's convention (rows 18–23, enforced by row 23 on row 22) out-of-hop items are NOT counted in `found`; they are recorded here with their disposition instead. Machinery: `scripts/final_gate.py` registers `check_corpus_weight.py` before the script exists — the registration's own design (skipped until Phase A lands it), not the missing-optional-check class; the brief's attribution of the recipe-wording fix to round 23 was wrong (infra's a63bda73), recorded as the fixer executed it. Fixes authored by the fixer seat | 118eeec8… → 6291c5ee… (round 25's pin; the span is 8 hunks, each carrying at least one fix — the 8th also carries this round's own row, coalesced with its fix to row 23's restatement, named here and not subtracted) |
| 25 (delta — opus rule seat + sonnet prose seat) | opus×1 (fresh; the recipe paragraph, rows 23–24, row 3's disclosure, row 4's and Q5's `T`, Q4's sentence; one hop into § Reproduce and § Q2) + sonnet×1 (fresh; the Status paragraph, the Date line, the authoring paragraph's prose, § Q2's row) · delta over round 24's fix diff (28 added / 19 removed lines, 8 hunks) + one hop | found: 8 (4 confirmed, 1 refuted on execution, 3 recorded wording in hop), new: 8, confirmed: 4, fixed: 4, unexecuted: 0, edits: 5 | method: re-derivation — rows 16–22's `edits:` 7 of 7 from the pins, row 23's span and legs replayed from the committed blobs (13; 3 + 7 + 9 coalescing), 6 of 6 token-sum recipes cache-excluded with the one cache-inclusive quantity named at 3 sites, the plan's `--reseed` line and 0 of 15 graders reading a D-row, 14 tables square, D-240/D-241/D-244 attributions 3 of 3. Confirmed, all ledger accounting written at round 24: the authoring paragraph assigned the pre-pass authoring diff (9 hunks) to round 24's `edits:` while row 24 read 8; `118eeec8` was labelled the round-25 pin though it is the pin round 24's seats read, and row 24's end cell was a self-reference; two sites credited round 25 with round 24's regeneration; row 24's `found: 13 (… 4 recorded out of hop)` imported the plan ledger's grammar into a ledger whose rows 18–23 exclude out-of-hop items, and three of those four were out-of-hop items applied in the batch. Per D-231 (a fifth touch of the recipe) the convention was rewritten ONCE — pin = the snapshot the seats read; `edits:` = the hunks the round's fixes applied, with sibling commits, a pre-pass authoring step and the round's own record excluded and named; coalescing stated — and rows 23–24 and the authoring paragraph restated under it (row 24 now `found: 10`, its end cell `6291c5ee`). RECORDED — in hop, applied as wording: Q5 canary 4's parenthetical back on the clause it evidences; § Q2's "stated once there" dropped; § Q4's "triggers nothing" corrected (a plain run tightens the baseline; only its gate role is nil). RECORDED — out of hop: § Reproduce's `T` over all rows vs the plan's token-carrying rows (equal today: 0 partial-pair rows of 135); D-240 (b)'s "16–21 of 30 days" predates the 29-comparison re-derivation (rows are immutable — an erratum row when the plan flips). Refuted: canary 4's "compute the same number" (executed equal). Fixes authored by the fixer seat | 6291c5ee… → a586c96c… (round 26's pin; the span is 5 hunks, each carrying at least one fix — the 5th also carries this round's own row, coalesced with its fixes to rows 23–24, named here and not subtracted) |
| 26 (delta — opus rule seat + sonnet prose seat) | opus×1 (fresh; the convention paragraph, rows 23–25, the authoring paragraph, § Q4's bullet, § Q5's parenthetical, § Q2's row) + sonnet×1 (fresh; the prose of every `+` line, the chain against the pins, the forward references) · delta over round 25's fix diff (13 added / 10 removed lines, 5 hunks) + one hop | found: 6 (5 confirmed, 1 refuted on execution), new: 6, confirmed: 5, fixed: 5, unexecuted: 0, edits: 4 | method: re-derivation — 10 of 10 rows' `edits:` from the pins, row 23's three legs replayed from the committed blobs (3 + 7 + 9 → 13), the counters convention 10 of 10 rows, 14 tables square, the plan's graders at `:128`–`:137` against § Q4's bullet. Confirmed, all inside round 25's ledger text: row 23's END cell still named `04f2a2e1` and 9 hunks while its method cell and the authoring paragraph had moved to `118eeec8` and 13 (the one broken link of the chain — now `118eeec8`, 9 of 9 links verified); "EXCLUDED from the count" was not executable when a record coalesces into a fix hunk (round 24's own row sits inside its eighth) and row 24's end cell claimed every hunk was a fix — the rule is now per hunk: counted when it carries one of the round's fixes, every non-fix region inside a counted hunk NAMED, never subtracted; row 24's "9 hunks" narration was unqualified (measured to the pre-authoring snapshot; 13 to the pin); § Q5's "11 ledger rows" carried no stamp (re-derived: 11 of 137 under `rounds > 0`, read 2026-09-13 00:25, the looser predicate's 13 named); the Date line enumerated rounds 16–24 beside row 25 (now "rounds 16 onward"). Refuted: row 25's forward-reference end cell as a self-reference defect (a round cannot stamp its own end hash; the fixer resolved it to `a586c96c` once known). Recorded and not applied: row 24's four refuted items are unenumerated (the fixer held no seat report to recover them from; they stay unenumerated rather than guessed). Fixes authored by the fixer seat | a586c96c… → the round-27 pin's md5, stamped in row 27 |
