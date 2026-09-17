# /fabrik-review-scoped's scope-growth exit — design

Status: DRAFT
Profile: delta

Owner: infra (the unnamed hub window) · Emitted by `/fabrik-spec` 2026-09-17 · Routed from
`docs/STRATEGIC_BACKLOG.md` § "[infra] /fabrik-review-scoped's missing scope-growth exit" (191c51e1c),
itself the output of a `/fabrik-command-improve` attempt that wrote this change, reviewed it three
times (confirmed 7 → 5 → 13, the count RISING) and REVERTED it.

**Profile verdict — `delta`, and it holds.** Every Intake Inventory item below maps to text or code
that exists today: `commands/_sources/fabrik-review-scoped.md`, `.windsurf/rules/core/50-code-review.md`,
`scripts/command_run.py`, `scripts/enforcement/check_review_coverage.py`. No new component. Under the
profile, `## Personas`, `## Lifecycle`, the fabrik-lib verdict, the constraints digest and
`## Rejected alternatives` collapse to their heading plus the minimum that is true; the six
interrogatives are still answered, in fewer sections.

---

## Personas

Every duty this design creates names the role that holds it.

| Persona | What they do here | The duty this design gives them |
|---|---|---|
| **The reviewing agent** (PRIMARY) | runs `/fabrik-review-scoped` after a spontaneous code change — the pass the Stop hook mandates when code was edited with no run record | reads the verdict the tool prints at `round`, and takes the exit it names |
| **The fleet agent in a project repo** | runs the same command in one of 44 repos that have no `commands/_fragments/` | gets the same verdict, from the same tool, without any hub-only path |
| **`scripts/command_run.py`** (AUTOMATED) | already computes a scope-growth advisory and prints it inside the `round` verb | becomes the single evaluator of the bar, and names WHICH of the two exits applies |
| **`check_review_coverage.py`** (AUTOMATED) | grades the heavy command's review REPORTS | unchanged here; it is inert for this command, which emits no report |
| **The operator** | reads the close, pays for the rounds | sees a light pass that closes light, instead of escalating to the heavy pass ~2/3 of the time |
| **The next command author** | edits this command or its pack later | inherits ONE normative statement plus pointers, not seven restatements to keep in step |

**The primary persona's loop, counted — the STEP BUDGET is 5 and this design must not raise it.**
1. classify the surface (step 1) · 2. open the record · 3. run a pass and fix what it confirms ·
4. record the round — **and read the verdict the tool prints back** · 5. close, or take the exit the
verdict named. Step 4 is where this design does its whole work: it adds a READ, never a sixth step.

---

## Goal

Give `/fabrik-review-scoped` a correct exit for the case where a review's remaining findings are its
own fixes — **without** adding a seventh restatement of an exit rule to a command that already carries
six, and without making the light pass heavy.

## Why this exists

Step 5 sends a review to the heavy `/fabrik-review` after "the SECOND consecutive round that confirms
defects" (`commands/_sources/fabrik-review-scoped.md:62-69`). That sentence describes two different
situations and prescribes one remedy:

- **(A) the surface outgrew the light pass** — more or riskier code than the light process provisioned
  for. Escalating is right.
- **(B) the loop is reviewing its own fixes** — each fix creates surface, the next round finds it. Here
  escalation is exactly wrong: it hands a bigger, more expensive reviewer to a surface whose only
  remaining defects the review itself authored. D-278 (superseding D-252) calls this the scope-growth
  stop, and its remedy is the opposite of escalation — suspend hunting, fix what is still open, close.

Because the command cannot tell A from B, it prescribes A for both. **Measured on the feedback ledger
(`~/.claude/state/command-feedback.jsonl`, window 2026-09-07 → 2026-09-17, 266 rows across all
commands): of 64 `/fabrik-review-scoped` closes, 60 carry a round series; 41 of those 60 (68%) contain
two consecutive non-zero rounds — step 5's trigger. In the same window 62 `/fabrik-review` closes
carry a surface, and 4 of them declare `ROUTED-UP: step 5`.**

Both figures are bounded and the bounds point the same way. **41 is an UPPER bound**: the ledger's
`findings` series is the confirmed series only when every round stated `--confirmed`, and the raw
series otherwise, unlabelled — the command says so itself at `:49-55` — so some non-zero entries are
raw candidates that were all refuted, which is not a confirming round. **4 is a LOWER bound**: only a
heavy run that closed AND used that exact surface string is visible. The honest statement is therefore
**a trigger met on the order of tens of runs and obeyed 4 times** — the rule is not a rule, it is
wallpaper, and FIX DIRECTIVE 5 is explicit that wallpaper is how enforcement dies.

The two sub-populations of those 41 are what make the conflation concrete: **12 of 41 converged to a
final round of 0 anyway** (e.g. `17 → 14 → 2 → 1 → 0`) — healthy reviews the rule would have escalated
— and **12 of 41 end on a round that rose or held above its predecessor and was non-zero** (`4 → 12 →
26`, `2 → 5 → 11 → 18`, `1 → 3 → 8`) — the pathological shape. One symptom, two populations, opposite
correct remedies, no discriminator.

**The discriminator already ships and nothing reads it.** Step 4's round template gained `--own-fix`
at 191c51e1c this morning (`:48`). The counter is collected; no branch in this command consumes it.
A counter with no consumer is the measurement half of a Cobra pair with the intervention half missing.

## What exists today (grounded)

**The exit rule is stated in EIGHT places, not six.** The routed brief said six; re-derived here, with
the two the brief missed marked `+`:

| # | Site | What it says |
|---|---|---|
| M1 | `commands/_sources/fabrik-review-scoped.md:2` (`description:` frontmatter) | "SKIP/ESCALATE to the full /fabrik-review: … or a second consecutive confirming round" |
| M2 `+` | same, `:15` (pre-record classification) | the step-1 route-up triggers — "open NO record here" |
| M3 `+` | same, `:44-47` (step 3) | "**This adds no exit and is not a route-up trigger** … Routing up happens on the triggers in steps 1 and 5, never because a finding was called architectural" |
| M4 | same, `:48` (step 4's round template) | collects `--own-fix`, cites D-278 — **no consumer** |
| M5 | same, `:62-69` (step 5) | "After the SECOND consecutive round that confirms defects the surface outgrew this command … escalate in the SAME turn and in ONE shell line" |
| M6 | same, `:116-125` (step 6) | the close under step 5's path (ii); a second `done` naming this command is refused |
| M7 | same, `:30-34` (`Profile: small` carve-out) | "Step 5's escalation trigger still escalates: a phase that keeps finding has outgrown the profile's light layer" |
| M8 | `.windsurf/rules/core/50-code-review.md:76-78` **and `:147`** | TWO statements, not one: the escalate-to list, and "Rounds that keep finding mean the surface outgrew the scoped command — escalate to `/fabrik-review`, don't stop" |

Counting only sites that state a LOOP-EXIT condition (M1, M4, M5, M6, M7 + the pack's two) gives
**seven**; counting every site that decides "leave the light pass" gives **nine statements across two
files**. Either count is larger than the six the attempt tried to patch, which is part of why patching
them one at a time never reached a fixed point.

**The pack already diagnoses the failure mode and cannot act on it.**
`.windsurf/rules/core/50-code-review.md:111-127` describes the oscillating loop — "fixer applies a
local workaround, next reviewer flags the workaround, forever. That is what `ROUTED` is for. ⚠️ It is
scoped to ANOTHER REPO only" — so the pack names the exact pathology, offers a mechanism, and then
scopes that mechanism out of the case at hand. Forty lines later (`:147`) it prescribes escalation for
the same symptom. The pack is not silent on this; it is self-contradictory on it.

**The verdict channel exists, is live for this command, and fires at the decision point.**
`scripts/command_run.py::scope_growth_warning` (`:365-412`) computes a scope-growth advisory;
`_round_report` emits it and is printed by the `round` verb at `:2947`. `PER_UNIT_ROUND_COMMANDS`
(`:274-276`) is `{fabrik-execute-plan, fabrik-repo-review}` — `fabrik-review-scoped` is **not** in it,
so the advisory already reaches this command. It fired unprompted on the reverted attempt's own review.

**But the channel computes a superseded bar, three ways.** `SCOPE_GROWTH_ROUNDS = 2` (`:327`) and the
predicate is `o == c > 0` for every round in the window (`:399`): **two** rounds not three,
**equality** not two-thirds, **consecutive** not sliding. Its `--own-fix` help (`:2287-2290`) still
reads "two consecutive rounds where every confirmed defect is own-fix trips the scope-growth stop
(omitted = not stated, which asserts nothing)". So an agent reading `round --help` is told the D-252
rule, and an agent reading the rendered command is told D-278. Fleet closed a 14-round review on the
stop this morning and said which one it trusted: *"I read the rendered command, not `command_run.py`'s
printed equality."*

**`check_review_coverage.py::_scope_growth_exit` (`:430-451`) is inert here and on the old bar.** It
grades a review REPORT's header zone plus its ledger, and this command deliberately writes no report
(`:55-58`). Its own docstring states the structural limit: "What the ledger CANNOT show is the own-fix
half (`own_fix` is a run-record counter, not a ledger column), so that part stays declarative."

**Two claims from the failed attempt, re-verified with better denominators.**
- Rendering `term-coverage.md` into this command is refused on size: the fragment is **25,697 B**
  against the source's **16,559 B** (+155%). In rendered terms the light command is **34,543 B** and
  the heavy `/fabrik-review` is **121,127 B**; the light pass is 28.5% of the heavy one, and the
  fragment would take it to roughly half. The lightness IS the command's identity.
- A CWD-relative `commands/_fragments/…` pointer is dead off-hub: of **45 git repos under `/opt`,
  exactly 1 carries `commands/_fragments/`** — the hub. (The brief said "5 of 5 checked"; the full
  denominator is 44 of 45 blind.) Absolute `/opt/fabrik/…` with step 4's own caveat is the only form
  that survives, and step 4 already uses it.

## The four answers — and the ruling

The brief named a three-answer contradiction for a round that omits `--own-fix`. There are **four**,
and the one the brief did not have is inside D-278's own ledger row.

| Source | What an omitted round does |
|---|---|
| `commands/_fragments/term-coverage.md:36` and `term-edit.md` (byte-identical) | **"a round that did not state it OCCUPIES its slot in the three-round window and can never be one of the two qualifying rounds"** — it counts AGAINST the stop |
| `docs/DECISIONS.md` **D-278's own row** | "an omitting round is **READ AS own-fix == confirmed (worst case)**, with the loop barred from closing while any round omitted it" — it counts FOR the stop |
| `scripts/command_run.py:396-400` | `_count` returns `None`, the `all(...)` is False, **no advisory at all** — one omission silences the channel for two rounds |
| `check_review_coverage.py:441-443` | own-fix is **invisible** — not a ledger column; the exit rests on a declared header phrase plus two consecutive confirming rounds |

D-278's row and the fragment it names as its Where are **opposite**. The row describes the fail-closed
arm that was written during authoring, refuted four ways in review, and deliberately NOT shipped; the
row was minted with that text and rows are immutable.

**RULING 1 — the fragment's reading is canonical.** An omitted round occupies its window slot and can
never qualify. Four reasons, in order (the fourth is external and was not available to the attempt): it is what actually ships to agents in 22 rendered commands;
it is the only reading that never invents a number the agent did not state (the row's "read as
own-fix == confirmed" fabricates the worst case, and fabricating data to trip a stop is the
over-classification mirror the fragment's own COBRA note forbids); and the row's arm was refuted on
the merits before shipping — deadlocking every review whose round 1 legitimately omits the counter. And **(iv)** it is the
conservative direction under G5: the fragment's reading errs toward one more round (bounded, cheap,
visible), the row's reading errs toward a false "converged" (unbounded, and invisible afterwards).

**RULING 2 — D-278's row needs an erratum row, not an edit.** Rows are immutable (CLAUDE.md § the
decision ledger). A new row records that D-278's omitted-round clause describes an unshipped
mechanism and that the fragment's text governs.

**RULING 3 — the disagreement is about a state that should not exist.** Measured across the 27 run
records on disk: **41 of 185 recorded rounds (22%) state `--own-fix`** — `fabrik-spec-review` 4 of 54,
`fabrik-review` 9 of 49, `fabrik-execute-plan` 12 of 46, `fabrik-review-scoped` 4 of 8 (n=8 is small:
records are per-session and are reaped, so treat the per-command splits as indicative and the 22%
aggregate as the figure). D-278 measured 21% computable on a different population and reached the same
place. **Any design that rests on the agent volunteering this counter is designing on a 22% base
rate.** So the durable fix is not to adjudicate the four readings — it is to make omission
unreachable: `command_run.py` REQUIRES `--own-fix` on a delta round of a review-family command. The
fragment already routes exactly this ("Making the flag required on a delta round is
`command_run.py`'s job and is routed there by D-278"). When the state cannot occur, the four-way
disagreement has no referent, and Ruling 1 governs only the records written before that lands.

## Approach grounding (1c) — what the field actually does

Four native `fabrik-researcher` seats, dispatched in one message (1 Opus authoritative + 3 Sonnet
breadth, `--mechanical 0` per the judgement-surface rule), Exa + Brave + WebFetch, all fetched
2026-09-17. Three findings decided this design; one refuted a framing I was about to ship.

**(G1) Restating one rule in many places is the worst-predicted pattern, not a way to add emphasis.**
PRIME (https://arxiv.org/html/2606.22470, fetched 2026-09-17) on near-duplicate and contradictory
instructions in one document: *"Typically, models do not identify such contrasts. They mainly follow
one command, none, or give irrelevant outcomes... conflict type is more significant in affecting
behavior than model scale."* IHEval (NAACL 2025, https://arxiv.org/abs/2502.08745, fetched
2026-09-17) measures the cost: *"All evaluated models experience a sharp performance decline when
facing conflicting instructions... the most competitive open-source model only achieves 48% accuracy
in resolving such conflicts."* **This is the measured 41-vs-4 gap's most likely mechanism, and it
predicts that a SEVENTH restatement makes it worse.** No vendor guidance found anywhere endorses
repetition-with-different-wording as a reliability technique.

**(G2) A sliding-window condition is the constraint shape that degrades fastest, and writing it more
carefully does not fix it.** *Large Language Models Can Follow Instructions, But Not Many at Once*
(https://arxiv.org/abs/2608.12426, fetched 2026-09-17, deterministic rule-based verifiers, no
LLM judge): *"Reliable instruction following breaks down beyond 5-6 simultaneous constraints"* and
*"a model passing individual constraints at ~41% at k=8 succeeds on all eight just 5.7% of the
time."* Decisively for this design: *"pre-generation planning does not move the threshold at all,
while post-hoc self-correction and best-of-5 retries delay it by only one to two constraints. Only
raising the per-constraint pass rate helps."* A two-of-the-last-three condition is a sustained
multi-round tracking constraint — exactly the class the paper reports degrading fastest.
**So the remedy is not better prose. It is to stop asking the reader to evaluate the condition.**

**(G3) The sanctioned remedy is a programmatic gate whose verdict is handed to the model.** Anthropic,
*Building effective agents* (https://www.anthropic.com/research/building-effective-agents, fetched
2026-09-17): *"You can add programmatic checks (see 'gate' in the diagram below) on any intermediate
steps to ensure that the process is still on track."* And on placement, Anthropic's live
prompt-engineering guidance (https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices,
fetched 2026-09-17): *"Queries at the end can improve response quality by up to 30 percent in tests,
especially with complex, multidocument inputs"* — the operative instruction belongs nearest the point
of action. `command_run.py` printing the verdict INSIDE the `round` verb is both at once: a
programmatic gate, delivered at the moment the agent decides whether to continue. That is D1.

**(G4) The self-reported counter: the field's answer is "an input, never the sole gate".** This
scenario is formally Adversarial Goodhart / Campbell's law — Manheim & Garrabrant's taxonomy
(https://arxiv.org/abs/1803.04585, fetched 2026-09-17) defines the Campbell's-law case as agents
selecting a metric *knowing* the regulator's metric. Strathern (1997), quoting Power, gives the
sharpest description of the exact failure (https://gwern.net/doc/statistics/decision/1997-strathern.pdf,
fetched 2026-09-17): *"audit becomes a formal 'loop' by which the system observes itself."* The
practice answer is consistent across four unrelated domains: Sarbanes-Oxley §404 keeps management's
self-assessment as a REQUIRED INPUT and puts an independent attestation on top of it (§404(b));
ISO 9001 permits self-inspection in production and draws the independence line at the AUDIT function;
research-misconduct policy under 42 CFR §93 makes a self-report the TRIGGER and never the VERDICT;
Earned Value Management replaces subjective percent-complete with objective earning rules. **None of
them adjusts the self-report statistically; all of them refuse to let it stand alone as the gate.**
⚠️ This REFRAMED § COBRA below: the honest statement is not "accept an unfalsifiable counter" but
"this command already has the SOX-404(b) shape, and the spec should say which part is the attestation."

**(G5) Which way to bias a two-sided gameable threshold.** Self-reported status is gamed in BOTH
directions in the field — Kaufmann & Kock, *The Performance Effects of Project Status Misreporting*
(Academy of Management Proceedings 2020, doi:10.5465/ambpp.2020.20408abstract, fetched 2026-09-17)
measured optimistic and pessimistic biasing across **46,474 status reports on 1,229 projects** with
opposite performance correlations. No cross-domain doctrine exists for which side to bias; the
closest principle is accounting conservatism's *"anticipate no profit, but anticipate all losses"* —
prefer the error that is cheaper to reverse. Here, one extra round costs one round; a false
"converged" is unbounded and hard to detect afterwards. **That independently supports Ruling 1** (see
below): the fragment's reading biases AGAINST stopping early, D-278's row's reading biases FOR it.

**(G6) A collected counter with no consumer has no sanctioned resting state.** Google SRE Workbook
(https://sre.google/workbook/monitoring/, fetched 2026-09-17): *"Each exposed metric should serve a
purpose. Resist the temptation of exporting a handful of metrics just because they are easy to
generate."* There is no "harmless and ignored" category — wire it to a decision or stop collecting
it. `--own-fix` has been collected in this command since 191c51e1c and read by nothing.

**(G8) ⚠️ THE AUTHORITATIVE SEAT REFUTED THIS SPEC'S FIRST DESIGN. The choice is not "one statement
plus pointers" versus "restate everywhere" — the field separates two things that framing fuses:** how
many places a rule is **VISIBLE** (a rendering question) and how many places it is **MAINTAINED** (a
sourcing question). The consensus is *one maintained source, any number of visible occurrences*, and
**no source found says "state it once and make the reader chase a pointer".**
- ISO/IEC Directives Part 2 (9th ed. 2021, https://www.iso.org/sites/directives/current/part2/index.xhtml,
  fetched 2026-09-17) § 5.7: *"If it is necessary to invoke a requirement that appears elsewhere, this
  should be done by reference, not by repetition… As far as possible, the requirements for one item or
  subject should be confined to one document."* But the verbal forms matter and the seat read them:
  reference-not-repetition is a **`should`**, while *"its source shall be referenced precisely"* is a
  **`shall`**. **ISO permits repetition and forbids UNATTRIBUTED repetition.**
- ISO § 5.6, and this is the sentence that names our actual defect: *"**Identical wording should be used
  to express identical provisions.** The same terminology should be used throughout. **The use of
  synonyms should be avoided.**"* Three sites that state one rule in three wordings are three rules.
- RFC 8174 (https://www.rfc-editor.org/rfc/rfc8174.html, fetched 2026-09-17): *"The words have the
  meanings specified herein **only when they are in all capitals**… When these words are not
  capitalized, they have their normal English meanings and are not affected by this document."* So
  "one binding site + five non-binding restatements" is a **standardised** shape — the binding force is
  marked TYPOGRAPHICALLY, not positionally. W3C does the same mechanically (WAI-ARIA normative section,
  https://www.w3.org/TR/wai-aria-1.0/normative, fetched 2026-09-17): binding keywords carry
  `class="rfc2119"`, and unmarked uses *"do not convey formal information in the RFC 2119 sense"* —
  which makes "which occurrence binds" a **greppable property rather than a reading judgement.**
- Write the Docs (https://www.writethedocs.org/guide/writing/docs-principles/, fetched 2026-09-17)
  states both halves explicitly. **ARID**: *"**Accept (some) Repetition In Documentation.** If you want
  to write good code, Don't Repeat Yourself. **But if you adhere strictly to this DRY principle when
  writing documentation, you won't get far.**"* **Unique**: *"Eliminate content overlap between separate
  sources… **prevent any parallel maintenance (or worse — lack of maintenance) of the same information
  across multiple sources.**"* The target of elimination is the second copy of the EDIT, not of the TEXT.
- The case AGAINST bare pointers is evidenced, not folklore. ACUS Recommendation 2011-5 (77 FR 2257,
  https://www.acus.gov/sites/default/files/Recommendation-2011-5-Incorporation-by-Reference.pdf): *"While
  incorporation by reference can make the CFR shorter and more readable, **it also has the potential to
  impede access to the law**"*; pointer CHAINS compound the cost (¶17, ¶4(c) "cumulative cost"); and a
  pointer used to dodge maintenance is an abuse (¶8). ANSI Z535.6 goes further for safety text,
  mandating **embedded** messages at the point of action *in addition to* grouped and section messages —
  redundancy prescribed precisely because the reader may enter at a different point, which is our case.
- And the drift cost is measured: *Detecting Near Duplicates in Software Documentation*
  (https://arxiv.org/abs/1711.04705, fetched 2026-09-17) — documentation accumulates *"near duplicate
  fragments, i.e. chunks of text that were copied from a single source and were later modified in
  different ways… **hard to detect manually due to their fuzzy nature**"*, across 19 projects. **An exact
  duplicate is greppable; a paraphrase is not.** That is why our six drifted and why no check could see it.

**(G9) The sliding window carries a measured false-alarm cost, and a naive one over an oscillating
series may never fire at all.** "Two of the last three" is verbatim a **Western Electric rule**. NIST/
SEMATECH e-Handbook § 6.3.2 (https://www.itl.nist.gov/div898/handbook/pmc/section3/pmc32.htm, fetched
2026-09-17) publishes the price: a plain Shewhart chart false-alarms *"every 371 points on the average"*;
*"**Adding the WECO rules increases the frequency of false alarms to about once in every 91.75 points**…
The user has to decide whether this price is worth paying (some users add the WECO rules, but take them
**'less seriously'**)."* A ~4× false-alarm increase, and the recorded human response is to downgrade the
rule — **wallpaper arriving by measurement.** Separately, Google's SRE Workbook § Alerting on SLOs
(https://sre.google/workbook/alerting-on-slos/, fetched 2026-09-17) warns about the naive
sustain-condition shape: *"**If the metric even momentarily returns to a level within SLO, the duration
timer resets. An SLI that fluctuates between missing SLO and passing SLO may never alert**"* — and
*"we do not recommend using durations as part of your SLO-based alerting criteria."* That is the
`43 → 11 → 30 → 13 → 22` oscillation shape exactly. Google's remedy is our remedy: materialise the
window as a COMPUTED value the reader reads off, never a condition the reader evaluates. ⚠️ D-278's bar
is CARRY for this run and is not re-litigated here, but **this cost is now on the record** and
§ Lifecycle's re-measurement is what would catch it.

**(G7) What the field does NOT have — and this is the finding that makes the design novel rather than
late.** Across AI code-review products (Sourcery, CodeRabbit, Qodo, Graphite/Diamond, Amazon
CodeGuru), automated-program-repair research, the reliability-growth stopping-rule literature and the
DORA/GitClear churn work, **no published process distinguishes "escalate, the surface is bigger than
provisioned" from "stop, the loop is now generating its own findings."** Every grounded stopping
mechanism is either a flat cap that terminates regardless of cause, or a diagnostic statistic that
says inspection has plateaued without attributing why. The closest artifact found — a community
review-loop harness with an explicit circuit-breaker table including *"Stale findings | 2 consecutive
| … | Escalate to /review-decide"* (https://github.com/gosha70/code-copilot-team/blob/master/shared/skills/review-loop/SKILL.md,
fetched 2026-09-17) — DETECTS the self-referential loop and then routes it to the same
escalate-to-human action as every other breaker. **One detector, one universal response, no
bifurcation by cause. That is precisely the gap this spec closes, and it means there is no
off-the-shelf shape to copy.**

## The delta

**One normative statement, at the point where the symptom is diagnosed; pointers everywhere else; the
verdict computed by the tool that already prints at that moment.**

**D1 — `command_run.py` becomes the single evaluator, and names WHICH exit applies.** Raise the window
to three rounds and the predicate to the two-of-three two-thirds ratio (D-278); keep it ADVISORY
(a heuristic must not trap — its own docstring); and change the emitted text from one diagnosis to a
two-way verdict: **SCOPE GROWTH → stop hunting, name and fix what is still open, close on the original
delta's state** versus **the escalate case, unchanged**. Correct the `--own-fix` help string off the
superseded equality. Require `--own-fix` on a delta round of a review-family command (Ruling 3).
⚠️ **Sequencing is load-bearing: this lands BEFORE the command text points at it.** Until it does, the
tool prints the D-252 equality, and a command that says "read the verdict" would be pointing at a
wrong answer — which is precisely the trap fleet stepped around by hand this morning.

**D2 — step 5 (M5) becomes the ONE normative site.** Its trigger stops being "the second consecutive
round that confirms defects → escalate" and becomes: at the second such round, the symptom has two
causes; the round you just recorded printed which one applies; take that exit. Escalation keeps its
existing one-shell-line form unchanged — it is correct for cause A and nothing here weakens it.

**D3 — every other site carries the SAME SENTENCE, and that sentence contains no condition.**
⚠️ **This replaces the draft's "make them pointers", which G8 refuted.** Bare pointers are the wrong
answer: a reader entering at site M6 must learn THAT THEY ARE BOUND without leaving M6 (ANSI Z535.6's
embedded-message rule; ACUS's measured access cost). The resolution is the seat's, and it is better
than either option this spec started with:

- **The rule that is restated contains nothing that can drift.** Every non-canonical site says one
  sentence of the shape *"the round you just recorded printed which exit applies — take it"*. It
  carries no window, no ratio, no round count, no arithmetic. **A sentence with no condition in it
  cannot contradict another copy of itself**, which is why it is safe to repeat at all six sites and
  why this design does not recreate the drift it is fixing.
- **One MAINTAINED source, many visible occurrences.** That sentence lives in a new small fragment
  under `commands/_fragments/` and is `{{include:}}`-ed, so the six occurrences are six renders of one
  string — the corpus already has the transclusion mechanism DITA calls `conref`. This is what makes
  the copies *provably* identical instead of conventionally identical, and it satisfies Write the Docs'
  *Unique* (no parallel maintenance) without violating *ARID* (repetition in the rendered text is fine).
  Size: one sentence, so the size refusal that killed `term-coverage` here does not apply.
- **Kill the PARAPHRASES — that is the actual defect and the cheapest half of the fix.** ISO 5.6:
  *"Identical wording should be used to express identical provisions. The use of synonyms should be
  avoided."* Today M1, M5 and M7 say the same thing in three wordings; the near-duplicate literature
  says a paraphrase is undetectable by any tool, which is precisely why six sites drifted with every
  gate green.
- **Mark the binding site so the marking is GREPPABLE.** Following RFC 8174 and W3C: the canonical
  statement at step 5 is the only one written in the marked normative form, and a check can then assert
  "exactly one marked occurrence per command" — a check, not a convention. This is the piece that makes
  the design hold against the NEXT author, who will otherwise add a seventh sentence in good faith.

**D4 — the pack gets ONE self-contained paragraph and loses its self-contradiction.** A project agent
cannot read the hub fragment (44 of 45 repos), so the pack states the bar and the own-fix term itself,
in full, once — and it carries the FIX-AND-RE-VERIFY duty in the same breath, because shipping the
halt without the duty licenses stopping a loop whose rounds still confirm defects (this exact defect
was caught in round 3 of the reverted attempt and would have reached ~46 repos). `:147`'s
"escalate, don't stop" is corrected to name both causes; `:111-127`'s ROUTED paragraph gains the
same-repo case it currently scopes out.

**What this design does NOT do:** it does not add a new prose branch for the agent to evaluate. The
two-of-three sliding window is COMPUTED and read off, never applied from memory — which is the
difference between this and the reverted attempt, whose fatal round-2 defect was precisely that a
single-evaluation prose branch cannot express a sliding window (round 1 is the full pass at
`--own-fix 0` and permanently occupies a slot it can never qualify in, so a one-shot evaluation
degenerates to a consecutive bar — the shape the COBRA note measured as dodgeable).

## Contract deltas

None. No data-contract or ui-design surface; no schema, no field, no screen. The rendered command
corpus changes, which is a render-and-`--check`, not a contract version bump.

## External dependencies

One line: **none.** No 3rd-party API, SDK, vendor, pricing or rate limit is touched — which waives the
1a facts gate and waives nothing else. The 1c approach gate was run in full (§ Approach grounding).

## Documentation landing sites

| What | Where it is written down |
|---|---|
| the two-way exit and its bar | `commands/_sources/fabrik-review-scoped.md` step 5 (the ONE normative site) — rendered to `~/.claude/commands/` |
| the self-contained pack copy | `.windsurf/rules/core/50-code-review.md`, distributed to ~46 repos by the post-commit governance sync |
| the computed verdict + the required flag | `scripts/command_run.py` docstrings, beside the code that cannot go stale against them |
| the rulings | `docs/DECISIONS.md` (new rows, incl. the D-278 erratum) |
| the change itself | `CHANGELOG.md`; this spec is the design record and `INDEX.md` gains its row |
| the run's own lesson | `docs/LESSONS_LEARNT.md` at the build's Finish, if the build produces one |

## Constraints digest

| Rule | Verbatim | Where | Binds this design |
|---|---|---|---|
| Link it or it is decoration | "**⚠️ Link it or it is decoration.** *Measured:* requests for files that do NOT exist came ~zero" | `.windsurf/rules/core/40-documentation.md:224` | **The load-bearing one.** Agents do not go looking. It is why the verdict is PUSHED by the tool at `round` rather than PULLED through a pointer — and why D4 restates in the pack instead of linking the hub fragment |
| No skipped heading levels | "**No skipped heading levels** — `##` to `###`, never `##` to `####`" | ibid `:240` | the artifact's own headings |
| Fenced code blocks only | "**Fenced code blocks only** — never indented code (AI treats it inconsistently)" | ibid `:242` | any shell in the command text |
| Review iterates to a fixed point | "Rounds that keep finding mean the surface outgrew the scoped command — escalate to `/fabrik-review`, don't stop." | `.windsurf/rules/core/50-code-review.md:147` | this is the line D4 corrects — quoted here so the change is visible against its source |

## fabrik-lib verdict

One line: **no capability here.** This is command text plus a branch in a hub-only script; no module
vendors, enhances or builds anything. `/opt/fabrik-lib/README.md`'s table offers nothing for "decide
which of two exits a review loop takes", and a new module would fail the candidate bar on (b) — no
second project type consumes it.

## Shape / infra implications

One line: none. No scaffold type, no `shape:` flag, no deployed service. `commands/` is not a
governance-sync trigger; `.windsurf/rules/` IS, so D4 distributes fleet-wide on the post-commit sync.

## Rejected alternatives

- **Restate the branch at all six (really eight) sites** — the reverted attempt. Rejected on
  measurement, not taste: 3 rounds, confirmed 7 → 5 → 13 with the count RISING, rounds 2 and 3 both
  100% own-fix, D-278's own bar firing on the review. Each restatement was a fresh contradiction
  surface.
- **Render `term-coverage.md` into the command** — rejected on the measured size above (+155% on a
  16,559 B source whose identity is lightness).
- **A CWD-relative pointer to the fragment** — rejected: dead in 44 of 45 repos.
- **Bare pointers at the five non-canonical sites** (this spec's own first design) — rejected by G8
  on evidence: ACUS 2011-5 measures the access cost a pointer imposes and the compounding cost of
  pointer chains; ANSI Z535.6 mandates the message at the point of action in addition to the grouped
  one; and no source found endorses making a bound reader leave the site to learn they are bound.
  Replaced by a condition-free restatement rendered from one fragment (D3).
- **Delete step 5's escalation trigger entirely** and rely on step 1's classification plus the stall
  circuit-breaker — rejected: it discards cause A, which is real and correctly handled today. The 4
  observed `ROUTED-UP: step 5` closes are evidence the path is used when an agent judges it right.
- **A RATE criterion instead of the ratio** — the software-reliability literature's standard stopping
  rule is a rate ("(1) when the reliability has reached a given threshold, and (2) when the gain in
  reliability cannot justify the testing cost", IEEE, *Reliability-estimation and stopping-rules for
  software testing*, https://ieeexplore.ieee.org/document/387388/, fetched 2026-09-17), and a 2026
  paper argues specifically against fixed-round caps for LLM verify-repair loops in favour of the sign
  of the true marginal gain (*Verify, Repair, Repeat, or Stop?*, https://arxiv.org/html/2607.17641,
  2026-07-20, fetched 2026-09-17: "+60.6 percentage points over fixed five-round repair at an average
  cost of 0.72 repair rounds"). Rejected **for this change**, not on the merits: D-278 is settled and
  named CARRY for this run, and a rate and a ratio answer different questions — a rate asks *is another
  round still worth it*, the ratio asks *whose surface are these findings on*, and only the second
  distinguishes cause A from cause B. Recorded as a backlog candidate for whoever revisits the bar.
- **Fixed round cap (the industry default)** — Sourcery caps automatic re-reviews at five per pull
  request ("Automatic re-reviews are capped at five per pull request. Past the cap, Sourcery stops
  re-reviewing automatically and the check reports Skipped", https://docs.sourcery.ai/reviews/anatomy-of-a-review.md,
  fetched 2026-09-17); community harnesses over CodeRabbit and Qodo hardcode the same 5. Rejected: the
  fragment states "**There is NO round ceiling**" by design, a cap terminates regardless of cause —
  the exact conflation this spec exists to remove — and it would stop cause-A reviews that are
  converging honestly.

## COBRA (D-253)

**The cheapest way to satisfy a scope-growth stop without producing the outcome** is to omit
`--own-fix` so nothing computes. Measured at **22% stated across 185 rounds** — the dodge is not
hypothetical, it is the default behaviour. **Counter-measure, in the same change:** D1 makes the flag
REQUIRED on a delta round of a review-family command, so the cheapest dodge stops being available
rather than being scolded.

**The MIRROR dodge** is to over-classify — call an original-surface defect own-fix, which both trips
the stop sooner and buys the backlog exit. D-278's counter is that own-fix is EVIDENCED per finding
(`own-fix: round k`, checkable against that round's md5 pair).

⚠️ **That counter is NOT available in this command, and the spec states it rather than hiding it.**
`/fabrik-review-scoped` persists no report (`:55-58`) — the round ledger IS its artifact — so there is
nowhere for a per-finding citation to live, and the `--own-fix` integer here is a bare self-report by
the party that benefits from stopping. Formally this is Adversarial Goodhart: the reporter and the
optimised party are the same actor (G4), and Strathern's *"audit becomes a formal 'loop' by which the
system observes itself"* describes it exactly.

**Disposition — and the grounding CHANGED it.** The draft of this section said "accept the weakness."
That was wrong, and G4 is why. Across four unrelated domains the field's answer to an unverifiable
self-report is identical and structural: **keep it as a required input, never let it alone satisfy the
gate.** Sarbanes-Oxley §404 is the cleanest instance — §404(a) mandates management's own assessment,
§404(b) puts an independent attestation on top of it, and the gate is the attestation. **This command
already has that shape and the spec's job is to NAME it rather than apologise for it:**

- the **self-report** is `--own-fix`, which by D1 becomes required rather than optional;
- the **attestation** is D-206's close condition, which this command already enforces at `:61` and
  `:123-124`: a delta pass with a **fresh non-authoring reader** that CONFIRMS ZERO, whose evidence
  must name the reader and what it returned — *"confirmed 0 with no reader named is the self-certified
  close this floor exists to refuse."* The over-classifying agent does not control that seat;
- and the stop is **ADVISORY** — `command_run.py` never blocks on it (its own docstring: "a heuristic
  must not trap") — so a wrong self-report changes a judgement call, never a gate;
- and the stop **suspends HUNTING, never the close**, so an over-classifier still owes every open
  confirmed defect, named and fixed.

So the honest statement is not that the counter is unfalsifiable and we live with it. It is that
**the counter never stands alone**: it steers the loop, and an independent reader still has to return
zero before anything closes. Making the integer itself falsifiable would require this command to
persist a report, which would make it the heavy command — **that trade is refused**, and it is refused
knowingly, because the 404(b) half is already in place. A finding that re-raises the unfalsifiable
integer without engaging the attestation half is answered by this paragraph.

**The third dodge, which the grounding named and the draft missed (G6):** leave `--own-fix` collected
and wired to nothing — which is the status quo since 191c51e1c, and is what D1 ends. Google SRE's rule
is that this state has no sanctioned form: *"Each exposed metric should serve a purpose."* Wire it to a
decision or stop collecting it; there is no harmless middle.

## Lifecycle

**Adoption** — D1 lands first and is inert until an agent records a third round; D2–D4 then point at
it. No migration: existing run records simply do not qualify.
**Growth** — the window is fixed at three rounds, so cost does not grow with round count. The pack
paragraph grows the pack by ~10 lines in 46 repos; `50-code-review.md` is 13,472 B today.
**Degradation** — every leg fails OPEN by construction: the advisory returns `""` on any unreadable
row, and `/fabrik-review-scoped` behaves exactly as today if the tool prints nothing.
**Retirement** — superseded when the bar changes again (a new D-row supersedes D-278); the pointers
survive a bar change untouched, which is the point of the design. Re-measure the 41/4 ratio after one
month: if the trigger is still met on ~2/3 of runs and the named exit still is not taken, the
diagnosis in this spec was wrong and the artifact should say so. **Re-measure the FALSE-ALARM side
too** — G9 puts a number on the shape D-278 chose (adding Western-Electric-style window rules moved a
control chart from one false alarm per 371 points to one per 91.75), and the documented human response
to that is to take the rule "less seriously". A stop that fires on healthy reviews will be ignored
exactly as step 5's trigger is ignored today, and this spec will have moved the wallpaper rather than
removed it. The measurable signature: qualifying rounds whose review then closes with further
ORIGINAL-surface defects found.

## Validation

1. `assemble_commands.py --check` green after the render (render → `--check` → commit, from the main
   checkout; `commands/` is not a sync trigger).
2. `check_command_corpus.py` and `check_corpus_weight.py` green — the second is the one that would
   catch a light pass becoming heavy.
3. A red-first grader per code change in D1: the three-round two-thirds predicate (including the
   `confirmed > 0` guard, without which a quiet `0/0` round qualifies vacuously), the required-flag
   refusal, and the two-way verdict text. Each seen RED on a copy before the fix.
4. The rendered command re-measured: `own-fix` occurrences and total bytes, against 1 and 34,543 B.
4a. **The greppable-marking check (D3's last bullet):** exactly ONE marked normative occurrence of the
   exit rule per command, and every other occurrence byte-identical to the fragment's rendered string.
   This is the check that replaces the convention, and it is what a seventh well-meant sentence trips.
5. `.venv/bin/python scripts/final_gate.py --check --json` → `success` (read-only; the tree is shared).
6. `sync_enforcement_to_projects.py --dry-run` clean before the one forced sync for D4.

## Cost

`Profile: small` for the build (D-169): ~4 files — `scripts/command_run.py`, its graders,
`commands/_sources/fabrik-review-scoped.md`, `.windsurf/rules/core/50-code-review.md` — so the plan is
INLINE: no `/fabrik-plan-after-chat`, no `/fabrik-plan-review`. Three phases: A `command_run.py` +
graders (HEAVY surface — fleet-synced to 49 dirs and the Stop hook reads its records — so a full
`/fabrik-review`), B the command text (render, `--check`, `/fabrik-review-scoped`), C the pack + the
one forced sync.

## Out of scope

- **The three enforcement halves filed as `01M2QCJBYV9F8ZKPR9KMNVV6FC`** are not built by this spec.
  D1 *is* the `command_run.py` half and this spec RULES what it must compute; the mail's other halves
  (both `CLAUDE.md` copies' `advisory`-vs-`skipped_checks` key, `final_gate.py`'s undiscoverable
  remedies) are unrelated surfaces and stay in that mail. The spec rules; the fix executes the ruling,
  so no fourth answer is baked in.
- **`check_review_coverage.py::_scope_growth_exit`** — inert for this command and correct for the one
  it grades. Re-keying it to D-278 belongs with the heavy command's receipt grammar, and is already a
  backlog row.
- **Changing D-278's bar.** CARRY: settled, not re-litigated here.

## Open / blocking unknowns

- **Does requiring `--own-fix` on a delta round break a live run?** Not established. `command_run.py`
  is fleet-synced to 49 dirs and a refusal at `round` would be felt immediately. Resolution step: the
  build measures the refusal against the 27 records on disk before arming it, and lands it as a NOTE
  first if the fire rate is not near-zero for compliant rounds (FIX DIRECTIVE 5).
- **Whether 41 is materially above the true trigger count.** The ledger cannot separate raw from
  confirmed series. Resolution step: re-derive from the run records' per-round `confirmed` field
  rather than the close's series, on a population large enough to be worth it.

## Decisions taken

To be minted with the artifact's commit: the three rulings above (canonical omitted-round reading; the
D-278 erratum; required-flag-over-adjudication), and the rejection of the rate criterion and the fixed
round cap with their citations.

## Intake Inventory

| I# | Item (anchored) | Disposition | Where |
|---|---|---|---|
| I1 | "give the fleet's most-run review command the scope-growth stop it has never had" | IN | § The delta, D1–D4 |
| I2 | "the step-5 branch across six mirror sites plus the synced pack" | IN | § What exists today (re-derived as eight sites + two pack statements) and § The delta D2–D4 |
| I3 | "`command_run.py`'s superseded equality is the same unlock" | IN | D1 |
| I4 | "the three enforcement halves … are ALL unlocked now and are the cheaper wins" | IN (one) / OUT-OF-SCOPE (two) | D1 is the `command_run.py` half; the `CLAUDE.md` and `final_gate.py` halves stay in mail `01M2QCJBYV9F8ZKPR9KMNVV6FC` — § Out of scope |
| I5 | the spec must RULE the three-answer contradiction | IN — and it was FOUR | § The four answers, Rulings 1–3 |
| I6 | the synced pack must carry the stop's FIX-and-re-verify duty | IN | D4 |
| I7 | the pack defines neither "own-fix" nor the arithmetic | IN | D4 (self-contained paragraph) |
| I8 | (f) the `--own-fix` integer is unfalsifiable here — state it openly | IN | § COBRA, with the disposition and the refused trade |
| I9 | re-verify (a) the size refusal, (b) the dead CWD pointer, (c) the inert checker, (d) the sliding-window failure, (e) the zero-confirming round | IN | § What exists today (a,b,c) · § The delta (d) · the `confirmed > 0` guard in § Validation item 3 (e) |
| I10 | COBRA for this command's own branch | IN | § COBRA |
| I11 | CAP: one `/fabrik-spec-review` pass | IN | the run's own method; recorded here so the reviewer sees the cap |
| I12 | "the previous attempt's revert is settled" | IN as CARRY | § Rejected alternatives, first row |

**Intake: 12 items — 11 IN, 1 split (I4: one half IN, two halves OUT-OF-SCOPE with a named mail), 0 ASK.**
