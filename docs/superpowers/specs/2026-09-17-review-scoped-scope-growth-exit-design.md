# /fabrik-review-scoped's scope-growth exit — design

Status: CONVERGED
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
| **The next command author** | edits this command or its pack later | inherits ONE maintained source rendered identically at every site — not a set of divergent restatements to keep in step |

**The primary persona's loop, counted — the STEP BUDGET is 5 and this design must not raise it.**
1. classify the surface (step 1) · 2. open the record · 3. run a pass and fix what it confirms ·
4. record the round — **and read the verdict the tool prints back** · 5. close, or take the exit the
verdict named. Step 4 is where this design does its whole work: **no sixth step is created**. ⚠️ But calling it "a
READ" undersells it, and the draft did: D1 makes `--own-fix` MANDATORY, and supplying it is a
classification WRITE — deciding, per confirmed finding, whether it lies in this review's own earlier
fixes. 144 of 185 historical rounds never supplied it. The step COUNT is unchanged; the work inside
step 4 is not, and that is the real cost this design asks of the primary persona.

---

## Goal

Give `/fabrik-review-scoped` a correct exit for the case where a review's remaining findings are its
own fixes — **without** multiplying divergent restatements of an exit rule across a command and its pack, which
already carry nine sites touching, and without making the light pass heavy.

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
two consecutive non-zero rounds — step 5's trigger. In the same window there are 62 `/fabrik-review`
closes, **56 of which recorded a surface at all**, and 4 of those declare `ROUTED-UP: step 5`.**

⚠️ **THE 41 IS CONCENTRATED, AND ONE OF THE CONCENTRATIONS IS THIS SPEC'S OWN SESSION. Stated here
because this repo's denominator-honesty rule binds its own authors first.** The 60 scoped closes come
from just **9 distinct sessions**, and the 41 trigger events are distributed
`12 · 11 · 4 · 3 · 3 · 3 · 3 · 1 · 1` — **the top two sessions are 23 of 41 (56%), and the largest,
with 12, is the very session that wrote this spec.** So 68% is NOT a fleet-wide behavioural rate. What
the data supports is narrower and still sufficient for the design: *within the sessions that run this
command heavily, the trigger fires on most runs and the mandated escalation is taken rarely.* A claim
that the fleet at large behaves this way is NOT established here, and the re-measurement in § Lifecycle
should be run over sessions that exclude this one.

Both figures are bounded and the bounds point the same way. **41 leans UPPER**: the ledger's
`findings` series is the confirmed series only when every round stated `--confirmed`, and the raw
series otherwise, unlabelled — the command says so itself at `:49-55` — so some non-zero entries are
raw candidates that were all refuted, which is not a confirming round. ⚠️ **It is not a CLEAN upper
bound, and an earlier cut claimed it was:** a `blocked` close truncates its series at the interruption
(one such row carries `[1]`), so an interrupted loop that would have tripped the trigger cannot register
it. The two mechanisms push opposite ways; the inflating one is the larger here, which is why the
figure still leans upper. **4 is a LOWER bound**: only a heavy run that closed AND used that exact
surface string is visible, and 6 of the 62 heavy closes recorded no surface at all. ⚠️ **And the two
counts are not event-linked**: 41 is counted over scoped closes and 4 over heavy ones, with nothing in
the ledger tying a specific trigger to a specific escalation — it is a session-level correlation, not
an event-level ratio, though the three sessions behind the 4 escalations do all appear in the
trigger-met population. The honest statement is therefore **a trigger met on most heavy-user runs and
obeyed 4 times fleet-wide** — the rule is not a rule, it is
wallpaper, and FIX DIRECTIVE 5 is explicit that wallpaper is how enforcement dies.

The two sub-populations of those 41 are what make the conflation concrete: the 41 partition **exactly** into four shapes, and
naming only two of them would have been the same selective reading this spec criticises elsewhere:
**12 converged to a final round of 0** (e.g. `17 → 14 → 2 → 1 → 0`) — healthy reviews the rule would
have escalated; **12 end on a round that ROSE above its predecessor** (`4 → 12 → 26`, `2 → 5 → 11 →
18`, `1 → 3 → 8`) — the pathological shape; **3 end on a tie**; and **14 end DECLINING but not yet
zero** — converging, simply not finished. (An earlier cut said "rose or held" and reported 12; "or
held" is 15. The prose now matches the arithmetic: 12 rose, 3 held, 12 + 3 + 12 + 14 = 41.)
So the largest single bucket is neither of the two the argument turns on. **What the partition
establishes is the discrimination problem, not a majority-pathology claim**: one symptom covers at
least a healthy population (12) and a pathological one (12) of the same size, with opposite correct
remedies and nothing in the command able to tell them apart.

**The discriminator already ships and nothing reads it.** Step 4's round template gained `--own-fix`
at 191c51e1c this morning (`:48`). The counter is collected; no branch in this command consumes it.
A counter with no consumer is the measurement half of a Cobra pair with the intervention half missing.

## What exists today (grounded)

**NINE sites touch the exit rule; two of them STATE it.** The routed brief said six and an earlier cut
of this spec said eight — both undercounts, and the correction history is kept because it is the
evidence for D3. Re-derived below, with the three the routed brief missed marked `+`:

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
| M9 `+` | `commands/_sources/fabrik-review-scoped.md:131` (the `Next command:` footer) | "resume what you were doing — this is a gate, not a stage (**escalations go to /fabrik-review**)" — found by a review seat AFTER this spec asserted its own enumeration was exhaustive |

⚠️ **The counts, honestly — and this spec's own first enumeration was ALSO incomplete, which is
itself the finding.** The routed brief said six; the draft said eight and asserted exhaustiveness; a
review seat then found M9. **Two SITES state the condition — M5 and M8 — and because M8 holds two
statements, that is THREE STATEMENTS. The units are named because the draft asked in sites and answered
in statements.** M1 paraphrases the condition in frontmatter; M7 restates it for the `Profile: small` case;
M4 collects the counter but this spec's own text says it has no consumer, so it states no condition;
M6 and M9 are procedural consequences that reference the decision made at M5; M2 is a pre-start
classification and M3 an explicit negation of exit-hood. ⚠️ **Units, stated because the draft mixed them:** counting SITES (table rows), nine touch the exit
and **two** state the condition — M5 and M8. Counting STATEMENTS, M8 holds two, so **three statements**
state it. **Nine sites touch the exit; two sites (three statements) state it;
one (M5) is operative.** That a careful enumeration was wrong twice in one day is the strongest
argument in this document for D3: a rule whose sites cannot be reliably counted cannot be reliably
edited, which is precisely why the previous attempt's six-site simultaneous patch never converged.

**The pack already diagnoses the failure mode and cannot act on it.**
`.windsurf/rules/core/50-code-review.md:111-127` describes the oscillating loop — "fixer applies a
local workaround, next reviewer flags the workaround, forever. That is what `ROUTED` is for. ⚠️ It is
scoped to ANOTHER REPO only" — so the pack names the exact pathology, offers a mechanism, and then
scopes that mechanism out of the case at hand. Twenty lines later (`:147`) it prescribes escalation for
the same symptom. The pack is not silent on this; it is self-contradictory on it.

**The verdict channel exists, is live for this command, and fires at the decision point.**
`scripts/command_run.py::scope_growth_warning` (`:365-412`) computes a scope-growth advisory;
`_round_report` emits it and is printed by the `round` verb at `:2947`. `PER_UNIT_ROUND_COMMANDS`
(`:274-276`) is `{fabrik-execute-plan, fabrik-repo-review}` — `fabrik-review-scoped` is **not** in it,
so the advisory already reaches this command. It fired unprompted on the reverted attempt's own review.

**But the channel computes a superseded bar, three ways.** `SCOPE_GROWTH_ROUNDS = 2` (`:327`) and the
predicate is `o == c > 0` for every round in the window (`:397`): **two** rounds not three,
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
  against the source's **16,559 B**. ⚠️ **State that unambiguously, because "+155%" alone is read two
ways and both a previous cut and a review seat read it the wrong one:** the fragment is 55% LARGER than
the source; INCLUDING it would grow the source BY 155%, from 16,559 B to 42,256 B — a 2.55× file. The
second is the load-bearing figure. In rendered terms the light command is **34,543 B** and
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
| `scripts/command_run.py:396-400` | `_count` returns `None`, the `all(...)` is False, so **the scope-growth advisory never fires** — one omission silences the STOP for two rounds. ⚠️ It does not silence the tool: `:2765` prints a NOTE naming the omission on that very round. The tool therefore SEES the omission and declines to act on it, which is a fourth behaviour again, not silence |
| `check_review_coverage.py:441-443` | own-fix is **invisible** — not a ledger column; the exit rests on a declared header phrase plus two consecutive confirming rounds |

D-278's row and the fragment it names as its Where are **opposite on every round that confirms
anything** — and the scope matters. Substituting the row's reading (`own_fix := confirmed`) into the
predicate: on a round with `confirmed > 0` it qualifies, where the fragment says it can never qualify;
on a `confirmed == 0` round the `confirmed > 0` guard fails under BOTH readings, so they agree. D-280
says "opposite" flatly and is immutable; this is the precise scope. The row describes the fail-closed
arm that was written during authoring, refuted four ways in review, and deliberately NOT shipped; the
row was minted with that text and rows are immutable.

**RULING 1 — the fragment's reading is canonical.** An omitted round occupies its window slot and can
never qualify. Three reasons stand, in order — a fourth was withdrawn below once the review found it
attributed a consequence to the wrong provision — and the last is external, unavailable to the attempt: it is what actually ships to agents in 22 rendered commands;
it is the only reading that never invents a number the agent did not state (the row's "read as
own-fix == confirmed" fabricates the worst case, and fabricating data to trip a stop is the
over-classification mirror the fragment's own COBRA note forbids); and the row's arm was refuted on
the merits before shipping — deadlocking every review whose round 1 legitimately omits the counter. ⚠️ **Precisely: the deadlock is
produced by provision (c), the close-bar, not by (b) — under (b) alone an omitting round merely
qualifies spuriously.** The draft used (c)'s consequence to reject the row and then preserved (c), which
does not cohere. The rejection of (b) stands on its own two reasons above; (c) is preserved because
nothing contradicts it, and the cheapest anti-omission measure is (a), the plain mandate to state the
flag every round. And **(iv)** it is the
conservative direction under G5: the fragment's reading errs toward one more round (bounded, cheap,
visible), the row's reading errs toward a false "converged" (unbounded, and invisible afterwards).

**RULING 2 — D-278's row needed an erratum row, not an edit — and that row is `D-280`, already minted
and committed by this run.** ⚠️ Written prospectively in the draft, which would have had a reader mint
a SECOND erratum. ⚠️ **And D-280's own text needs its own correction, which this spec must schedule
rather than perform:** its RULING 2 says the flag is required "on a delta round of a review-family
command" — the selector D1 refutes below. Rows are immutable, so the build mints a further row naming
D-280's phrasing as loose and binding the `PER_UNIT_ROUND_COMMANDS` selector. Recording that here is the
point: an erratum that itself needs an erratum is exactly the shape this spec is about. Rows are immutable (CLAUDE.md § the
decision ledger). A new row records that D-278's omitted-round clause describes an unshipped
mechanism and that the fragment's text governs.
⚠️ **The clause has THREE provisions and only ONE is contradicted** — the draft said two, a bounded
enumeration short by one in the paragraph that exists to get enumerations right. D-278 says (a)
"stating `--own-fix` every round is mandatory", (b) an omitting round is "READ AS own-fix ==
confirmed", which the fragment genuinely contradicts, and (c) "with the loop barred from closing while
any round omitted it" — a CLOSE condition the fragment is silent on and therefore does not contradict.
**(a) and (c) are PRESERVED; only (b) falls.** ⚠️ Note D-280 quotes the clause as a single unit before
ruling "the fragment's text governs", so this split is a READING of an immutable row that reads
otherwise on its face — stated openly rather than asserted as settled. It is the cheapest
anti-omission measure available and it binds every command, including the ones Ruling 3's selector
cannot reach; repealing it as collateral of (i) would have been a silent loss.

**RULING 3 — the disagreement is about a state that should not exist.** Measured across the 27 run
records on disk: **41 of 185 recorded rounds (22%) state `--own-fix`** — `fabrik-spec-review` 4 of 54,
`fabrik-review` 9 of 49, `fabrik-execute-plan` 12 of 46, `fabrik-review-scoped` 4 of 8 (n=8 is small:
records are per-session and are reaped, so treat the per-command splits as indicative and the 22%
aggregate as the figure; the four named commands account for 157 of the 185 rounds and 29 of the 41
stated — the remainder sits in commands not broken out here, and the counting convention that
reproduces every figure is TOP-LEVEL rounds only, with "stated" meaning the `own_fix` KEY IS PRESENT,
an explicit 0 included). D-278 measured 21% computable on a different population and reached the same
place. **Any design that rests on the agent volunteering this counter is designing on a 22% base
rate.** So the durable fix is not to adjudicate the four readings — it is to make omission
unreachable: `command_run.py` REQUIRES `--own-fix` on a delta round of **every command the stop can
fire on** — the selector `_tokish(command) not in PER_UNIT_ROUND_COMMANDS` that the omission NOTE
already uses, NOT the 2-member `REVIEW_FAMILY` set, which is bound to unrelated auth and quota
contracts and would leave `fabrik-spec-review` — 54 rounds, the largest population and the worst
offender at 4 stated — omittable forever. The
fragment already routes exactly this ("Making the flag required on a delta round is
`command_run.py`'s job and is routed there by D-278"). When the state cannot occur, the four-way
disagreement has no referent, and Ruling 1 governs only the records written before that lands.

## ⚠️ The defect, demonstrated on this spec's own review (executed, not argued)

This review's three rounds produced the series below. It is the cleanest evidence in the document,
because it was generated by the machinery under discussion while that machinery was being specified.

| round | confirmed | own-fix | ratio | D-278 (shipped rule) | D-252 (what `command_run.py` computes) |
|---|---|---|---|---|---|
| 1 (full pass) | 29 | 0 | 0% | does not qualify | no |
| 2 | 15 | 13 | **86%** | **qualifies** | no — `13 != 15` |
| 3 | 6 | 4 | **66%** | **qualifies** | no — `4 != 6` |

**Two of the last three qualify, so the shipped rule says STOP — and `command_run.py` printed nothing.**
Its equality bar needs `own_fix == confirmed` on two CONSECUTIVE rounds; a review can sit at 86% and 66%
own-fix, be unmistakably reviewing its own corrections, and never trip it. The stop was taken here
because a human-readable rule in a fragment said so, not because the tool said so — which is exactly
what fleet reported on 2026-09-17 after taking the stop by hand: *"I read the rendered command, not
`command_run.py`'s printed equality."*

**This is D1's whole case.** The counter is collected, the bar is shipped, the two disagree, and the
disagreement is silent. It also validates the design's shape: the stop fired on a review that had
already extracted real value (29 original-surface defects in round 1) and was, by round 3, correcting
its own corrections — 4 of 6 defects inside text round 2 had written. Stopping there was right, and the
exit taken was the one D-278 prescribes: name and fix everything still open in the window, route
genuine own-fix residue, close on the original delta's state.

## Approach grounding (1c) — what the field actually does

Four native `fabrik-researcher` seats, dispatched in one message (1 Opus authoritative + 3 Sonnet
breadth, `--mechanical 0` per the judgement-surface rule), Exa + Brave + WebFetch, all fetched
2026-09-17. Three findings decided this design; one refuted a framing I was about to ship.

**(G1) Restating one rule in many places is the worst-predicted pattern, not a way to add emphasis.**
PRIME (https://arxiv.org/abs/2606.22470, fetched 2026-09-17) on near-duplicate and contradictory
instructions in one document — the two halves below are a SPLICE across the paper's introduction and
its abstract, each verbatim, joined here for brevity: *"Typically, models do not identify such contrasts. They mainly follow
one command, none, or give irrelevant outcomes... conflict type is more significant in affecting
behavior than model scale."* IHEval (NAACL 2025, https://arxiv.org/abs/2502.08745, fetched
2026-09-17) measures the cost: *"All evaluated models experience a sharp performance decline when
facing conflicting instructions... the most competitive open-source model only achieves 48% accuracy
in resolving such conflicts."* **This is the measured 41-vs-4 gap's most likely mechanism, and it
predicts that one more restatement IN A NEW WORDING makes it worse.** No vendor guidance found in this
search endorses repetition-with-different-wording as a reliability technique.
⚠️ **Read G1 together with G8, or the two read as opposites.** Both of G1's sources measure CONFLICT —
PRIME on "near-duplicate and contradictory instructions", IHEval on conflicting ones. **The operative
variable is divergent wording, not the number of occurrences**, which is exactly why G8's
"one maintained source, any number of visible occurrences" does not contradict this item and why D3 can
restate at every site: identical text rendered from one source presents no conflict surface. An earlier
cut of this spec keyed its Goal on the COUNT of restatements; the count was never the problem.

**(G2) A sliding-window condition is the constraint shape that degrades fastest, and writing it more
carefully does not fix it.** *Large Language Models Can Follow Instructions, But Not Many at Once*
(https://arxiv.org/abs/2608.12426, fetched 2026-09-17, deterministic rule-based verifiers, no
LLM judge): *"Reliable instruction following breaks down beyond 5-6 simultaneous constraints"* and
*"a model passing individual constraints at ~41% at k=8 succeeds on all eight just 5.7% of the
time."* Decisively for this design: *"pre-generation planning does not move the threshold at all,
while post-hoc self-correction and best-of-5 retries delay it by only one to two constraints. Only
raising the per-constraint pass rate helps."* ⚠️ **The paper's constraints are SIMULTANEOUS within a single
generation — it says so explicitly ("require simultaneous adherence to multiple explicit constraints…
within a single response") — NOT constraints tracked across rounds.** Reading a two-of-the-last-three
condition as "exactly the class the paper measured" would be a category error, and an earlier cut of
this bullet made it. What the paper licenses is narrower and still sufficient: composing several
conditions in one act of reading degrades sharply, and the mitigations an author reaches for first
(plan harder, re-read, retry) are measured as nearly useless. **That a multi-ROUND condition is at
least as hard is this spec's own extrapolation, labelled as such rather than borrowed.**
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
Earned Value Management replaces subjective percent-complete with objective earning rules. ⚠️ **Three of those four answer the same way; the fourth answers
differently and the difference matters.** SOX, ISO 9001 and 42 CFR §93 all KEEP the self-report and
refuse to let it stand alone as the gate. **EVM does something else: it ELIMINATES the self-report,
replacing subjective percent-complete with an objective earning rule.** An earlier cut folded all four
into one "consistent" answer, which bought authority the sources do not jointly give. And EVM's move is
available here — `commands/_fragments/term-coverage.md:36` already prescribes exactly that earning rule:
*"own-fix is EVIDENCED, never asserted: each finding's row cites the round whose fix hunk contains the
line (`own-fix: round k`), checkable against that round's md5 pair."* See § COBRA for why this command
cannot host it today and what that costs.
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
⚠️ **G5 and G9 pull in opposite directions and the spec says so rather than choosing quietly.** G5
argues for erring toward another round; G9's cost is a raised FALSE-ALARM rate, and a false alarm here
is a spurious "SCOPE GROWTH" — which stops the loop early, the very error G5 says to avoid. The design
resolves it by keeping the stop ADVISORY rather than gating, so a false alarm costs a judgement call
and not a close, and by preserving the duty to fix every open defect at the stop. § Lifecycle's
re-measurement is what would show that resolution failing.

**(G6) A collected counter with no consumer has no sanctioned resting state.** Google SRE Workbook
(https://sre.google/workbook/monitoring/, fetched 2026-09-17): *"Each exposed metric should serve a
purpose. Resist the temptation of exporting a handful of metrics just because they are easy to
generate."* There is no "harmless and ignored" category — wire it to a decision or stop collecting
it. `--own-fix` has been collected in this command since 191c51e1c and read by nothing.

**(G8) ⚠️ THE AUTHORITATIVE SEAT REFUTED THIS SPEC'S FIRST DESIGN. The choice is not "one statement
plus pointers" versus "restate everywhere" — the field separates two things that framing fuses:** how
many places a rule is **VISIBLE** (a rendering question) and how many places it is **MAINTAINED** (a
sourcing question). The consensus is *one maintained source, any number of visible occurrences*, and
**no source found REQUIRES "state it once and make the reader chase a pointer".** ⚠️ The stronger form
of that sentence — "no source SAYS" — was in an earlier cut and is falsified by the very next bullet:
ISO § 5.7 does say *"by reference, not by repetition"*. What rescues the claim is the modal, not the
absence: ISO says it as a `should`, and a recommendation is still a saying.
- ISO/IEC Directives Part 2 (9th ed. 2021, https://www.iso.org/sites/directives/current/part2/index.xhtml,
  fetched 2026-09-17) § 5.7 — **all three sentences are in § 5.7, which merely points forward to
  Clause 10; an earlier cut of this bullet attributed the third to § 10.1 and that anchor was wrong**:
  *"If it is necessary to invoke a requirement that appears elsewhere, this should be done by reference,
  not by repetition… As far as possible, the requirements for one item or subject should be confined to
  one document."* But the verbal forms matter and the seat read them: reference-not-repetition is a
  **`should`**, while *"its source shall be referenced precisely"* is a **`shall`** — confirmed against
  Clause 7 itself (§ 7.2 requirement → "shall"; § 7.3 recommendation → "should"), not assumed.
  **ISO permits repetition and forbids UNATTRIBUTED repetition.**
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
  https://www.acus.gov/sites/default/files/Recommendation-2011-5-Incorporation-by-Reference.pdf):
  *"Ensuring that regulated and other interested parties have **reasonable access** to incorporated
  materials is perhaps the **greatest challenge** agencies face…"* Pointer CHAINS compound the cost —
  item 4(c) counts *"the **cumulative cost** to obtain incorporated material that itself incorporates
  further materials"* — and a pointer used to dodge maintenance is an abuse: item 8, *"Agencies should
  not address difficulties with updating by confining incorporations by reference to non-binding
  guidance documents."*
  ⚠️ **An earlier cut of this bullet quoted ACUS as saying incorporation by reference "has the potential
  to impede access to the law". That sentence is NOT in the Recommendation** — it is a law-review
  commentary on it (Bremer, *Incorporation by Reference in an Open-Government Age*). The verification
  seat raw-fetched four independent copies of the Recommendation, including the Federal Register text
  itself, and found it absent. Real words, wrong source; the three quotes above are the primary text and
  the claim they support is unchanged. ANSI Z535.6 goes further for safety text,
  architecting **four co-existing message types** — supplemental directives, grouped, section and
  **embedded** — so the same hazard is addressed at several granularities at once: redundancy by design,
  because the reader may enter at a different point, which is our case. ⚠️ **Provenance, stated because a
  design decision rests on it:** the four-type architecture is corroborated across five independent
  sources spanning the 2006, 2011 and 2023 editions, including ANSI's own blog. The stronger
  *placement* sentence — that an embedded message be "included as a step or part of a step in the
  procedure" — was found in exactly ONE unauthenticated third-party reproduction of the paywalled 2006
  edition, so **this spec relies on the architecture claim only** and treats the placement wording as
  unconfirmed.
- And the drift cost is measured: *Detecting Near Duplicates in Software Documentation*
  (https://arxiv.org/abs/1711.04705, fetched 2026-09-17) — documentation accumulates *"near duplicate
  fragments, i.e. chunks of text that were copied from a single source and were later modified in
  different ways… **hard to detect manually due to their fuzzy nature**"*, across 19 projects. **An exact
  duplicate is greppable; a paraphrase is not.** That is why these drifted and why no check could see it.

**(G9) The sliding window carries a measured false-alarm cost, and a naive one over an oscillating
series may never fire at all.** "Two of the last three" is verbatim a **Western Electric rule**. NIST/
SEMATECH e-Handbook § 6.3.2 (https://www.itl.nist.gov/div898/handbook/pmc/section3/pmc32.htm, fetched
2026-09-17) publishes the price: a plain Shewhart chart false-alarms *"every 371 points on the average"*;
*"**Adding the WECO rules increases the frequency of false alarms to about once in every 91.75 points**…
The user has to decide whether this price is worth paying (some users add the WECO rules, but take them
**'less seriously'**)."* ⚠️ **Read the plural inside that quote: 91.75 is the combined price of adding
ALL FOUR WECO rules, not of the single run rule this design's bar resembles.** An earlier cut of this
bullet attributed the whole degradation to the two-of-three rule alone, which its own quotation falsifies. ⚠️ **The ~4× ratio does NOT transfer to a review loop, and an earlier cut of this
bullet implied it did.** Both figures are Average Run Lengths — the mean number of *points plotted*
before a false signal, derived as `1/p` under a **stationary, independent** in-control process. A review
loop's round series violates both by construction: each round is a fix applied *in response to* the
previous round's findings (serial dependence), and the process is deliberately CHANGING — the whole
point is convergence. **What transfers is the QUALITATIVE finding, not the arithmetic:** adding window
rules to a detector raises its false-signal rate, and the recorded human response is to keep the rule
and take it *"less seriously"* — wallpaper, documented. The number is quoted for provenance, never as a
prediction about rounds. Separately, Google's SRE Workbook § Alerting on SLOs
(https://sre.google/workbook/alerting-on-slos/, fetched 2026-09-17) warns about the naive
sustain-condition shape: *"**If the metric even momentarily returns to a level within SLO, the duration
timer resets. An SLI that fluctuates between missing SLO and passing SLO may never alert**"* — and
*"we do not recommend using durations as part of your SLO-based alerting criteria."* That is the
`43 → 11 → 30 → 13 → 22` oscillation shape exactly. ⚠️ **Google's remedy is a change of STATISTIC, not of who evaluates
it** — in both arms of that discussion the condition is evaluated by Prometheus and no human reads it,
so the source cannot speak to D1's reader-versus-tool question, and an earlier cut claimed it did. What
it DOES support, and all this spec claims from it, is **"do not use a consecutive/duration sustain
condition"** — genuine support for a sliding two-of-three over two-consecutive. The compute-it-in-the-
tool half stands on G3's programmatic-gate quote alone. ⚠️ D-278's bar
is CARRY for this run and is not re-litigated here, but **this cost is now on the record** and
§ Lifecycle's re-measurement is what would catch it.

**(G7) What the field does NOT have — and this is the finding that makes the design novel rather than
late.** Across AI code-review products (Sourcery, CodeRabbit, Qodo, Graphite/Diamond, Amazon
CodeGuru), automated-program-repair research, the reliability-growth stopping-rule literature and the
DORA/GitClear churn work, **not found, in what four seats searched on 2026-09-17: any published
process that distinguishes "escalate, the surface is bigger than provisioned" from "stop, the loop is
now generating its own findings."** ⚠️ **The bound is stated because this repo's denominator-honesty
rule binds its own specs first: a bounded search returns "not found in N", never "does not exist".** N
here is five named products, three literatures and one community harness — not a survey. Every grounded stopping
mechanism is either a flat cap that terminates regardless of cause, or a diagnostic statistic that
says inspection has plateaued without attributing why. The closest artifact found — a community
review-loop harness with an explicit circuit-breaker table including *"Stale findings | 2 consecutive
… | Escalate to /review-decide"* (https://github.com/gosha70/code-copilot-team/blob/master/shared/skills/review-loop/SKILL.md,
fetched 2026-09-17) — DETECTS the self-referential loop and then routes it to the same
escalate-to-human action as every other breaker. **So the field has the DETECTOR; what was not found is the
bifurcated RESPONSE** — an earlier cut said the detector was missing too, which its own next sentence
falsified. Within that bound there is no off-the-shelf shape to copy, which is why this design is
built rather than adopted.

## The delta

**One MAINTAINED statement, at the point where the symptom is diagnosed; the same condition-free
sentence rendered at every other site — never a bare pointer, which G8 refuted; the
verdict computed by the tool that already prints at that moment.**

**D1 — `command_run.py` becomes the single evaluator, and names WHICH exit applies.**
⚠️ **Precisely what the tool can and cannot diagnose, because the draft overclaimed this.** The tool
sees only the round series — `confirmed`, `own_fix`, `findings`, the command name. It does NOT see file
count, risk class or mechanism novelty, so it cannot independently diagnose cause A. What it CAN do is
decide **B, or not-B-as-far-as-it-can-see** — and that is sufficient for a two-way verdict only because
cause A's own evidence was already collected at step 1: **B detected → print the stop; the second
consecutive confirming round with no B → print the escalate line.** ⚠️ **Silence is NOT evidence of
not-B, and the spec does not treat it as such:** the advisory returns `""` for at least SEVEN distinct
reasons — fewer rounds than the window; a window round that omitted a counter; a malformed counter (a
bool, a non-integral float, a non-dict row); the command sitting in `PER_UNIT_ROUND_COMMANDS`; the
ratio genuinely unmet, which is the only one that means A; a TERMINAL round, where `_round_report`
returns early before the advisory is ever computed; and a REFUSED round, which never reaches the report
at all. So the honest verdict space is **"B" or "unknown"**, which is
exactly why D1 requires the escalate line to be COMPUTED from the round series rather than inferred
from the stop's silence. A reading on which the tool "detects that the surface outgrew the light pass"
is wrong. Raise the window
to three rounds and the predicate to the two-of-three two-thirds ratio (D-278); keep it ADVISORY
(a heuristic must not trap — its own docstring); and change the emitted text from one diagnosis to a
two-way verdict: **SCOPE GROWTH → stop hunting, name and fix what is still open, close on the original
delta's state** versus **the escalate case, unchanged**. Correct the `--own-fix` help string off the
superseded equality.
⚠️ **Emit THREE verdicts, not two — and the third is what makes D3 honest.** The draft said "two-way";
the closing round proved silence is not one-valued, so a two-way verdict forces D3's sentence to read
every silence as "not the scope-growth case", which on the 78% of rounds that omit the counter is the
exact fail-open § COBRA names as the cheapest dodge. The three: **`⚠ SCOPE GROWTH`** (ratio met);
**`↗ ESCALATE`** (a second consecutive confirming round with the ratio COMPUTED and unmet); and
**`? UNCOMPUTABLE`** (a window round omitted or malformed a counter) — which
names what is missing and is never read as either exit. ⚠️ **A refusal-created gap is deliberately NOT
on that list**, though an earlier cut put it there: a refused `round` returns before the report is
built, so nothing prints at all and no verdict can carry the case. That cause is covered by D3's third
arm ("if it printed nothing at all"), which is the only place it CAN be covered.
⚠️ **Emit a SECOND verdict line, or D2 has nothing to read in the escalate case.** "The escalate case,
unchanged" means the tool says NOTHING there — `scope_growth_warning` returns `""` and no other line in
`_round_report` computes an escalate verdict. A two-way verdict therefore requires a new `↗ ESCALATE`
line on a second consecutive confirming round that does NOT meet the ratio. Without it the "two-way
verdict" is one branch plus silence, and D2's read-it-off trigger is false in half its cases.
⚠️ **The required-flag half keys on the selector the code ALREADY uses, NOT on `REVIEW_FAMILY`.**
`REVIEW_FAMILY` (`scripts/command_run.py:803`) is a 2-member set bound to *different* contracts — the
Stop hook's "may exempt code it did not author" and the RED-band start allowance — so widening it to
close this would silently change behaviour for every command added. ⚠️ **Three contracts, not two** —
the draft named two: `final_gate_stop.py:811-813` ("Only these may exempt code they did not author"),
`quota_posture_hook.py:669` (the RED-band start allowance), and — the one the draft missed and the most
consequential — `command_run.py:3398`, the done-time coverage REACH-BACK, whose own comment calls the
alternative "an honest BLOCKED exit turned into a laundering hatch". ⚠️ **And "20 commands" was a
figure with no derivable population and is withdrawn:** 37 command sources exist, 22 render a
scope-growth fragment, and `fabrik-review-scoped` is not among those 22 — no natural set yields 20. The
argument needs no count: widening a set bound to three unrelated contracts is wrong at any width. The right selector is the
inverse one the omission NOTE already uses: `_tokish(command) not in PER_UNIT_ROUND_COMMANDS`
(`:2762`). This matters concretely: a committed grader,
`tests/test_command_run.py::test_the_own_fix_note_covers_every_command_the_stop_can_fire_on` (`:4949`),
exists **because this exact mistake was made and reverted** — its docstring records that gating on
`REVIEW_FAMILY` left eight stop-eligible commands never told the flag exists. Keying on `REVIEW_FAMILY`
would also make Ruling 3 only ~31% true: `fabrik-spec-review` is the largest population at 54 rounds
and the worst offender at 4 stated, and it is not in that set.
⚠️ **Land the requirement as a NOTE-then-refuse RATCHET, never a refusal on day one.** A refused
`round` returns before the append (the refusals return at `:2717`, `:2720`, `:2727`, `:2734` and
`:2747`; the append is at `:2866`) — ⚠️ **the draft cited `:2749`, which is the omission NOTE's `print(`
and does not return at all**, so a refusal an agent does not retry leaves a
GAP in `rounds` — and `scope_growth_warning`'s own docstring warns that a gap makes non-adjacent rounds
read as adjacent, which is the hole its round-1 fix closed. The script also reaches its sync targets
ahead of the rendered corpus, so a refusal can land against text that never mentions the flag.
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

- **The rule that is restated contains nothing that can DRIFT — but it must still be TRUE where it
  sits, and the draft's version was not.** The sentence *"the round you just recorded printed which
  exit applies — take it"* is false wherever no verdict printed, and meaningless at M1, which runs
  **before any record exists** (`fabrik-review-scoped.md:29-30`: "the route-up classification already
  ran BEFORE the record"). So the sentence carries its one unavoidable disjunction, which is
  exhaustive and still contains no number: ***"take the exit the round you just recorded printed. If it printed
  `? UNCOMPUTABLE`, supply the missing counter and re-record before deciding. If it printed nothing at
  all, the stop was never computed — do not read that as a verdict."***
  ⚠️ **The draft ended "if it printed none, this is not the scope-growth case" and that was FALSE in the
  dominant case.** The advisory is silent for at least SEVEN reasons — too few rounds; an omitted
  counter; a malformed counter; the command sitting in `PER_UNIT_ROUND_COMMANDS`; the ratio genuinely
  unmet; a TERMINAL round returning early before the advisory is computed; and a REFUSED round that
  never reached the report, **a cause D1's own ratchet creates**. One of the seven means "not the
  scope-growth case". Reading silence as that one re-creates the fail-open this design exists to close,
  and it would have shipped to the pack — where, for `/fabrik-repo-review` and `/fabrik-execute-plan`,
  the advisory can NEVER print and the old sentence would have been permanently false in ~46 repos. ⚠️ **The exclusion set is M1, M2 and M3 — the draft excluded only M1 and cited M2's evidence for it.**
  `fabrik-review-scoped.md:29-30` ("the route-up classification already ran BEFORE the record") is
  step 1's text, which is M2, while M1 is the `description:` frontmatter at `:2`. All three are
  non-exits — frontmatter, a pre-start classification, and an explicit negation of exit-hood — and
  injecting a loop-exit sentence into M3, which exists to deny being one, would have been the worse
  outcome of the two.
- **Each occurrence names where it is maintained.** ISO's one `shall` is precisely this — *"its source
  shall be referenced precisely"* — and G8's whole argument rests on that modal, so a design that
  extracts the requirement and then omits it fails its own grounding. Each rendered occurrence ends
  with its source (`— /opt/fabrik/commands/_fragments/<name>.md`), the absolute form that resolves from
  every repo. Without it, an author at M6 in three months sees an unattributed sentence, cannot tell it
  is a render, and edits it in place — recreating the exact paraphrase drift this design removes.
- **A sentence with no condition in it cannot contradict another copy of itself**, which is why it is
  safe to repeat at every remaining site and why this design does not recreate the drift it is fixing.
- **One MAINTAINED source, many visible occurrences.** That sentence lives in a new small fragment
  under `commands/_fragments/` and is `{{include:}}`-ed, so the occurrences are renders of one
  string — the corpus already has the transclusion mechanism DITA calls `conref`. This is what makes
  the copies *provably* identical instead of conventionally identical, and it satisfies Write the Docs'
  *Unique* (no parallel maintenance) without violating *ARID* (repetition in the rendered text is fine).
  Size: one sentence, so the size refusal that killed `term-coverage` here does not apply.
- **Kill the PARAPHRASES — that is the actual defect and the cheapest half of the fix.** ISO 5.6:
  *"Identical wording should be used to express identical provisions. The use of synonyms should be
  avoided."* Today M1, M5 and M7 say the same thing in three wordings; the near-duplicate literature
  says a paraphrase is undetectable by any tool, which is precisely why they drifted with every
  gate green.
- **Mark the binding site so the marking is GREPPABLE.** Following RFC 8174 and W3C: the canonical
  statement at step 5 is the only one written in the marked normative form, and a check can then assert
  "exactly one marked occurrence per command" — a check, not a convention. This is the piece that makes
  the design hold against the NEXT author, who will otherwise add one more sentence in good faith.

**D4 — the pack gets ONE self-contained paragraph and loses its self-contradiction.**
⚠️ **The draft's premise was wrong and this command's own text refutes it.** A project agent CAN read
the hub fragment: `fabrik-review-scoped.md:50` says so and relies on it — *"the fragment is not
installed — the hub path resolves from every repo"* — and reading another repo is not the cross-repo
HARD STOP, which governs create/edit/commit. The true and weaker premise is that a project agent will
not ENCOUNTER the fragment unprompted, because it is not rendered into that repo's corpus; the pack is.
⚠️ **And the weaker premise does NOT by itself force the strong conclusion** — an agent that will not
encounter the fragment but CAN read it is served by a pointer, so the draft kept a conclusion its own
corrected premise had stopped supporting. The warrant that does carry it is D3's, not proximity: ANSI
Z535.6's embedded-message principle — the reader must learn AT the point of action that they are bound,
without leaving it — plus ACUS's measured cost of a pointer and the fact that the pack is the only one
of the two rendered into the repo the agent is standing in. On THAT warrant the pack states the bar and
the own-fix term itself, in full, once — and it carries the FIX-AND-RE-VERIFY duty in the same breath, because shipping the
halt without the duty licenses stopping a loop whose rounds still confirm defects (this exact defect
was caught in round 3 of the reverted attempt and would have reached ~46 repos). `:147`'s
"escalate, don't stop" is corrected to name both causes; ⚠️ **And `:111-127`'s ROUTED paragraph KEEPS its absolute
guard.** The draft proposed giving it "the same-repo case it currently scopes out"; that guard —
*"cross-service findings inside this repo are fix-or-refute, never routed away"* — is what blocks the
mirror dodge of calling an original-surface defect own-fix and routing it to a backlog row. Opening it
in ~46 governance-synced repos at the moment § COBRA concedes the per-finding evidence counter is
unavailable here would ship the licence without its counter-measure. The pack's `:147` contradiction is
corrected by naming both causes; the routing guard is left alone.

**What this design does NOT do:** it does not add a new prose branch for the agent to evaluate. The
two-of-three sliding window is COMPUTED and read off, never applied from memory — which is the
difference between this and the reverted attempt, whose fatal round-2 defect was precisely that a
single-evaluation prose branch cannot express a sliding window (round 1 is the full pass at
`--own-fix 0` and permanently occupies a slot it can never qualify in, so a one-shot evaluation
degenerates to a consecutive bar — the shape the COBRA note measured as dodgeable).

**D5 — round zero's executable obligation widens from MECHANISM claims to ANY claim the FIX
introduces.** ⚠️ **ADDED AFTER CONVERGENCE, on the operator's direction (2026-09-17), and marked as
such so a reader can tell it apart from the converged text.** It was not reviewed by the five rounds
above; it is carried by the build's own review.

**The rule today** (`commands/_fragments/term-edit.md` and `term-coverage.md`, round zero rule (1)):
*"THE MECHANISM IS A SCRIPT, NOT PROSE — a claim about what a verb, a window or a reach-back does is
executed at round 1 as a probe script…"* — scoped to MECHANISM claims, and everything else a fix
introduces is covered only by round zero's opening duty to **re-read** every added line
*"(length, citations, claims)"*.

**Why that is the wrong scope, measured on this spec's own review.** Rounds 2, 3 and 4 confirmed 19
own-fix defects — defects inside text an earlier round's FIX had written. Classified (the
classification is mine, the instances are in the Pass Ledger): the large majority were **counts and
enumerations** ("four consistent domains" when one was the opposite; "two contracts" when there were
three; "TWO provisions" when there were three; "20 commands" with no derivable population), **negatives
stated without a bound** ("no source found *says*", falsified by the citation two lines below it), and
**line anchors cited without resolving them** (`:2749` cited for a return that does not return). Only
two were mechanism or logic claims — the class rule (1) already covers.
**The asymmetry is the cause:** the original draft passed four grounding seats, the rule-grounding gate,
a constraints digest and six review seats. The fix text passed nothing, and round zero asks for a
RE-READ — which is precisely what the `proxy-never-evidence` HARD STOP says is never evidence. A count
is not checked by looking at it again.

**The change:** rule (1) becomes *any claim the fix introduces that has a checkable referent* — a count,
an enumeration, a line anchor, a negative — **executed before the pin, never re-read**. ⚠️ **It must be
written TWICE, not copy-pasted:** the two fragments are deliberately NOT byte-identical here —
`term-edit` says "pinned beside the `{{ARTIFACT}}` … never re-derived by a **seat**", `term-coverage`
says "pinned beside the **receipt** … never re-derived by a **finder**". A single shared wording would
be wrong in one of the two.

**COBRA (D-253), in the same change.** The cheapest way to satisfy "execute every claim your fix
introduces" WITHOUT doing it is to introduce no checkable claims — write vaguer corrections with no
numbers in them. **Counter-measure, stated in the rule itself:** the obligation is discharged by
DELETING an unverifiable claim just as well as by executing it, so the honest cheap path and the
compliant path are the same one; and `denominator-honesty` already forbids a count without its
population, so vagueness is not free either.

**Blast radius:** 22 command sources render one of the two fragments (`/fabrik-review-scoped` renders
neither, which is the whole reason this spec exists). `commands/` is not a governance-sync trigger, so
this distributes by render, not by sync.

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

- **Restate the branch at every site** — the reverted attempt, which patched the six it knew of.
  Rejected on
  measurement, not taste: 3 rounds, confirmed 7 → 5 → 13 with the count RISING, rounds 2 and 3 both
  100% own-fix, D-278's own bar firing on the review. Each restatement was a fresh contradiction
  surface.
- **Render `term-coverage.md` into the command** — rejected on the measured size above (including it grows a
  16,559 B source by 155%, to 42,256 B — a
  16,559 B source whose identity is lightness).
- **A CWD-relative pointer to the fragment** — rejected: dead in 44 of 45 repos.
- **Bare pointers at the five non-canonical sites** (this spec's own first design) — rejected by G8
  on evidence: ACUS 2011-5 measures the access cost a pointer imposes and the compounding cost of
  pointer chains; ANSI Z535.6 mandates the message at the point of action in addition to the grouped
  one; and no source found endorses making a bound reader leave the site to learn they are bound.
  Replaced by a condition-free restatement rendered from one fragment (D3).
- **Delete step 5's escalation trigger entirely** and rely on step 1's classification plus the stall
  circuit-breaker — rejected: it discards cause A, which is real and correctly handled today. The 4
  observed `ROUTED-UP: step 5` closes are evidence the path is USED. ⚠️ They are NOT evidence it was
  used correctly: the 4 come from a string match, which cannot show any of them was a genuine cause-A
  case rather than a cause-B misroute — the conflation this spec exists to name. The same 4 carries the
  "wallpaper" load in § Why this exists; both readings hold at once, and neither licenses a claim about
  the judgement behind them.
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
  fetched 2026-09-17); community harnesses over CodeRabbit and Qodo are reported to hardcode the same 5, though the only
  such harness this run examined in depth uses a different shape (a 2-consecutive stale-findings
  breaker) — so "5" is the VENDOR pattern, not a community consensus. Rejected: the
  fragment states "**There is NO round ceiling**" by design, a cap terminates regardless of cause —
  the exact conflation this spec exists to remove — and it would stop cause-A reviews that are
  converging honestly.

## COBRA (D-253)

**The cheapest way to satisfy a scope-growth stop without producing the outcome** is to omit
`--own-fix` so nothing computes. Measured at **22% stated across 185 rounds** — the dodge is not
hypothetical, it is the default behaviour. **Counter-measure, in the same change:** D1 makes the flag
REQUIRED on a delta round of every command the stop can fire on (the `PER_UNIT_ROUND_COMMANDS`
selector, not `REVIEW_FAMILY` — see D1), so the cheapest dodge stops being available
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
- the **attestation** is D-206's close condition, which this command STATES at `:61` and `:124-125`:
  a delta pass with a **fresh non-authoring reader** that CONFIRMS ZERO, whose evidence must name the
  reader and what it returned — *"confirmed 0 with no reader named is the self-certified close this
  floor exists to refuse."*
  ⚠️ **But that attestation is PROSE in this command, and the review of this spec proved it. Three
  executed reads, because the draft asserted the opposite:** (i) the rule that grades a closing seat,
  `check_review_coverage.py`'s V11, reads a finders cell in a review REPORT — and this command
  persists none (`:55-58`), so V11 can never fire for it; (ii) `fabrik-review-scoped` is **absent**
  from `command_run.py`'s done-time report floor (`:3031-3048`, which lists `fabrik-review`,
  `fabrik-repo-review`, `fabrik-user-test`, `fabrik-service-test`, `fabrik-epics-review` and
  `fabrik-conformance-review`), so its `done` runs no artifact check and its `--evidence` is only
  fingerprinted; (iii) a sweep of `scripts/` and `.claude/hooks/` for "non-authoring" returns only
  advisory strings and comments — **nothing verifies that a reader was NON-AUTHORING.** ⚠️ **The draft
  said "nothing verifies that a reader was dispatched" and that was too strong, refuted by a wider
  sweep than one literal phrase** — the bounded-search shape this repo's own rule names.
  `command_run.py:2795-2826` reads seat TRANSCRIPTS off disk (`_seat_transcripts`, `_transcript_path`),
  counts those newer than the previous round, and nudges when seats ran with no `dispatch --seats`
  stamp. That is a mechanical observation of dispatch, not a self-report — advisory and one-directional,
  but real. **It also makes the successor item CHEAPER than the draft claimed:** the machinery for
  reading seat evidence already lives in the file D1 is editing. And on independence itself: §404(b)'s attestor is engaged by the audit committee
  and externally inspected, whereas this one is a subprocess the audited party spawns, briefs, slices,
  and whose output only the audited party reads and then summarises into a free-text string it also
  writes. That is management's internal audit function — the thing §404(b) exists because it does not
  accept.
  ⚠️ **And it attests a different proposition.** §404(b) attests the SAME assertion management made.
  D-206's reader confirms zero defects on the delta; it never examines the own-fix CLASSIFICATION. An
  agent that mislabels an original-surface defect as own-fix, trips the stop, fixes it, and dispatches
  the reader gets a green from a seat that never looked at the mislabelling. **The mirror dodge passes
  the attestation.**;
- and the stop is **ADVISORY** — `command_run.py` never blocks on it (its own docstring: "a heuristic
  must not trap") — so a wrong self-report changes a judgement call, never a gate;
- and the stop **suspends HUNTING, never the close**, so an over-classifier still owes every open
  confirmed defect, named and fixed.

**So the honest statement is the one the draft would not make.** This command does NOT have the
404(b) shape today. It has the 404(a) half — a self-report — plus a stated duty that no check reads.
The two bounds that do hold are real but weaker than the draft claimed: the stop is **ADVISORY**
(`scope_growth_warning`'s own docstring: "NEVER blocks — a heuristic must not trap"), so a wrong
self-report changes a judgement call rather than passing a gate; and the stop **suspends HUNTING, never
the close**, so the duty to name and fix every still-open confirmed defect survives the stop *as an
instruction*. ⚠️ **That second bound is prose too** — nothing refuses a `done` on a non-terminal round
for this command — and the draft leaned on it as though it were enforcement.
**The disposition, stated rather than dressed up:** the counter is a bare self-report, its stated
attestation is unenforced for this command, and closing that gap means either persisting a report
(which makes the light pass heavy — **refused**) or adding the evidence to the record. ⚠️ **The second
is NOT impossible, and the draft's claim that "there is nowhere for a per-finding citation to live" was
a preference wearing a structural argument:** `command_run.py` stores `own_fix` as a bare integer on
the round row, and D1 is already editing that file, so an evidence field costs what the required-flag
change costs. **Recorded as the successor item, with a named destination** — the backlog row this spec
routes — rather than argued away. A finding that re-raises the unfalsifiable integer is answered by
this paragraph; a finding that the attestation is unenforced is CONFIRMED and is why this paragraph
was rewritten.

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
too** — G9 records that adding Western-Electric-style window rules to a detector raises its false-signal
rate and that the documented human response is to keep the rule and take it "less seriously". ⚠️ G9's
control-chart ARL figures do NOT transfer to a round series (stationarity and independence both fail
here), so there is no borrowed number to predict with — which is exactly why this has to be MEASURED on
our own series rather than argued from theirs. A stop that fires on healthy reviews will be ignored
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
5. **(D5)** the two fragments diffed against each other at the edited clause, asserting the
   per-fragment vocabulary survived (`{{ARTIFACT}}`/`seat` vs `receipt`/`finder`) — a copy-paste that
   flattened them would be the defect D5 itself warns about.
6. `.venv/bin/python scripts/final_gate.py --check --json` → `success` (read-only; the tree is shared).
7. `sync_enforcement_to_projects.py --dry-run` clean before the one forced sync for D4.

## Cost

`Profile: small` for the build (D-169): ~6 files — `scripts/command_run.py`, its graders,
`commands/_sources/fabrik-review-scoped.md`, `.windsurf/rules/core/50-code-review.md`, and (D5)
`commands/_fragments/term-edit.md` + `term-coverage.md` — so the plan is INLINE: no `/fabrik-plan-after-chat`, no `/fabrik-plan-review`. Three phases: A `command_run.py` +
graders (HEAVY surface — fleet-synced to 49 dirs and the Stop hook reads its records — so a full
`/fabrik-review`), B the command text AND D5's two fragments (render, `--check`,
`/fabrik-review-scoped`; D5 rides here because it is the same render), C the pack + the one forced
sync.

## Defects found IN THE SURFACE during this review (the build fixes them)

A closing seat found two stale line citations in `commands/_sources/fabrik-review-scoped.md`. **Sweeping
the CLASS rather than the instances — every code line-citation in that file — found the class is
FIVE members and ALL FIVE are stale.** Resolved against `scripts/command_run.py` at HEAD:

| Cited | The command says it is | What the line actually is |
|---|---|---|
| `:338` | where the raw findings series prints unlabelled | a comment about a `bool` being refused as a counter |
| `:384` | where a MIXED record refuses to close on the raw count | a comment about per-unit ticket rounds |
| `:398-404` | the same refusal | inside `scope_growth_warning` — `return ""` and its advisory text |
| `:2288` | the persisted-report tuple | the `--own-fix` argparse help string (the tuple begins at `:3032`) |
| `:2585` | the `done`-verb reach-back | `target = max(1, args.phase)` in the `step` verb (the real logic is `AGENT_CLOSED_STATES` at `:799-803` and the reach-back at `:2460-2485`) |

**Every underlying CLAIM is true; every POINTER has drifted** — `command_run.py` grew and the citations
did not move. This is the spec's own thesis arriving as evidence rather than as argument: a paraphrase
is undetectable and a line anchor rots silently, which is why D3 keeps the restated sentence
condition-free and names its source rather than its line. The build corrects all five in the same change
that edits this file, and a `check_citations_resolve.py --changed` run over the corpus is the cheap
sweep that would have caught them — it examines `docs/` roots today, and widening it to
`commands/_sources/` is the routed successor.

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
| I2 | "the step-5 branch across six mirror sites plus the synced pack" | IN | § What exists today (re-derived as NINE sites across two files, of which two state the condition) and § The delta D2–D4 |
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
