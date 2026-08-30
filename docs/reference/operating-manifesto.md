# Operating Manifesto

**Status:** ADOPTED 2026-08-30 (D-043). Original items preserved verbatim; additions marked `+`.
Each phase closes on a **gate** — a checkable condition, not a feeling of thoroughness. The gates
bind through § Binding, not through memory: prose is enforced by memory and mood, and neither
survives a long session.

---

## Phase 0: Triage `+`

* **`+` Irreversibility Triage:** Classify the decision before applying any of it. *Reversible* (cheap to undo, contained blast radius) → skip to Phase 4 and let reality do the analysis — **writing a one-line kill criterion at Phase 4 entry** ("this ships and X within Y days, or it's reverted"): the fast-path stays fast, but an experiment with no failure condition is just a deploy, and Phase 5's gate still needs something to measure against. *One-way* (structural, public, expensive or impossible to unwind) → run the full loop. Rigor scales with irreversibility, never with how interesting the problem is.
* **`+` Decision Budget:** Cap the spend (hours / tokens / €) at classification time. Analysis is a purchase, and an uncapped purchase is how Cost of Delay stays a sentiment.

> **Gate:** the decision is classified, a budget is set, and the depth of everything downstream follows from that classification. Hitting the budget with an unclosed gate forces the default action (Invariant 3).

---

## Phase 1: Investigation & Discovery

* **5W1H Structure:** Map the entire problem space comprehensively by asking Who, What, When, Where, Why, and How before taking action.
* **Factual Root Causes:** Relentlessly dig past surface-level symptoms to isolate the objective, empirical source of the issue.
* **First-Principles Thinking:** Strip problems down to their most fundamental, undeniable truths rather than reasoning by analogy or convention.
* **`+` Ground Before Asserting:** Read the file, query the DB, run the command. Mark every load-bearing premise **verified** or **assumption** and cite the evidence. Assumptions are permitted; unlabeled assumptions are not. A passing check proves format, not correctness.
* **`+` Kill Criterion:** Write down, before starting, the specific observation that would prove this wrong. No kill criterion, no start.

> **Gate:** the problem is a falsifiable claim with one owner-metric, every premise is labeled verified or assumption, and the kill criterion is written.

---

## Phase 2: Logic & Synthesis

* **Deductive Reasoning:** Draw certain, logical conclusions from established premises and absolute rules.
* **Inductive Reasoning:** Observe specific data points meticulously to recognize overarching patterns and formulate generalized rules.
* **Abductive Reasoning:** Formulate the most plausible, logical explanation when faced with incomplete information or ambiguous data.
* **Probabilistic Updating:** Treat conclusions as hypotheses, continuously updating your strategies and confidence levels as new data emerges.

> **Gate:** the conclusion carries a stated confidence level and names the evidence that would move it.

---

## Phase 3: Systemic Analysis & Validation

* **Systemic Thinking:** View the environment holistically, understanding how interconnected parts influence one another within the larger whole.
* **Counterfactual Thinking:** Explore "what if" scenarios and alternate realities to uncover hidden variables, test assumptions, and understand causality.
* **Second-Order Effects:** Anticipate the downstream, cascading impacts of any action before making a move.
* **Steel-Manning & Falsifiability:** Actively construct the strongest possible counter-arguments against your own ideas, ensuring every hypothesis can be objectively tested.
* **`+` Blast Radius:** Ask what breaks if you are wrong, not only what pays off if you are right. Size the damage, not just the upside.

> **Gate:** the strongest counter-argument has been stated and answered, or the plan changed in response to it.

---

## Phase 4: Strategy & Execution

* **Well Researched and Concluded:** Ensure every strategy is backed by deep validation and rigorous scrutiny before moving to execution.
* **Best Proven Practises But Also Innovative:** Anchor operations in established excellence while boldly integrating novel, cutting-edge solutions.
* **Lean Approaches:** Maximize efficiency by eliminating waste and moving with agility and precision.
* **The Pareto Principle & Ockham's Razor:** Focus relentlessly on the 20% of inputs that drive 80% of the outcomes, and always favor the simplest viable solution with the fewest moving parts.
* **`+` Cost of Delay:** Time spent deciding is a cost that appears in the comparison. A slower decision is not automatically a better one, and analysis can consume the value it was protecting.
* **`+` Ship to Learn:** Deploy small, instrumented, and reversible. Deployment is the experiment, not the report on one.

> **Gate:** one plan — simplest viable, trade-off named — running in the real environment where someone other than you can observe it.

---

## Phase 5: Longevity & Adaptability

* **Permanent Solutions and Implementations:** Design structural fixes that cure the underlying disease once and for all, rather than continually treating the symptoms.
  * **`+` Permanence belongs to contracts and constraints; disposability belongs to implementations.** A system whose parts cannot be thrown away is not durable — it is brittle with good documentation.
* **Full Resilience:** Build frameworks capable of withstanding immense stress, shocks, and failures while reliably returning to baseline.
* **Antifragility:** Evolve past resilience by designing systems that actually learn, adapt, and grow stronger from volatility and disorder.
  * **`+` Capture the disorder or none of this happens.** Failures must be recorded as data. Disorder you do not instrument teaches nothing, and antifragility without instrumentation is a slogan.
* **`+` Close the Loop:** Compare the outcome to the Phase 1 kill criterion. Commit one durable artifact. Then re-enter Phase 1 or explicitly close it out. Lessons that stay in Phase 5 die in Phase 5.
  * **`+` Armed Tripwires:** Where the kill criterion is measurable, wire it to alerting before closing the loop. A closed loop with an armed tripwire is *forgotten*; one without is merely *abandoned*. On this stack that means Prometheus/Gatus → Alertmanager → Telegram: the criterion pages you instead of you re-reviewing.

> **Gate:** outcome measured against the kill criterion, one durable artifact committed, the measurable criterion armed as a tripwire, loop re-entered or closed.

---

## Invariants `+`

Hold across all phases. First to decay under time pressure.

1. **Verified or assumption, always labeled.** Confidence is a claim about evidence, not a tone.
2. **Ratchet, don't reset.** Every cycle leaves the system measurably harder to break the same way twice. This is the mechanism Antifragility actually runs on.
3. **`+` Default action under ambiguity.** When a gate cannot close within budget, the most reversible option wins by default. Stalling is impossible by construction — the system is fast, not merely careful.
4. **`+` A fired kill criterion defaults to kill.** Overriding it requires a new written claim with a new criterion — never an edit to the old one. This is the guard against sunk cost, the failure mode most likely to survive everything else in this document.
5. **`+` WIP limit (the portfolio invariant).** No new Phase 0 entry while **3** loops sit open past Phase 4. New ideas get a one-line parking entry (`docs/STRATEGIC_BACKLOG.md`), not a phase. The manifesto is per-decision; the portfolio is where days actually die.

---

## Binding `+` — how the gates become machine-checkable

A manifesto agents can read is not yet one they can obey. The gates bind through machinery that
already exists and is already enforced — never a parallel system:

- **Every decision, reversible or not → its row in `docs/DECISIONS.md`** (the fleet decision
  ledger: what/why/where, rows immutable, supersede-by-new-row — which is Invariant 4 in
  mechanism form: an override IS a new row citing the old, never an edit).
- **A ONE-WAY decision → its row grows the manifesto fields**, appended in the same change,
  using this template inside the row's where-cell target (a plan, spec, or the row itself):

  ```text
  CLASS: one-way · BUDGET: <h/tokens/€> · KILL: <the observation that proves this wrong>
  CONFIDENCE: <level + the evidence that would move it> · COUNTER: <strongest counter-argument + answer>
  TRIPWIRE: <alert ref | "not measurable — reviewed at close-out"> · CLOSE-OUT: <due / done>
  ```

- **Tripwires** are Gatus endpoints / Prometheus alerts routed through Alertmanager→Telegram —
  the existing fleet path; a tripwire that pages nobody is a comment.
- **The parking entry** is a `docs/STRATEGIC_BACKLOG.md` row — one line, no phase, no loop.
- **Enforcement grows by the standing rollout law:** advisory first, fire rate measured, promoted
  to a blocking check only on evidence. Candidate checks, in order: (1) a CONVERGED one-way plan
  whose decision row lacks KILL/BUDGET fields; (2) the WIP limit — count open past-Phase-4 rows in
  the ledger and warn past 3 (today the only invariant enforced by the operator noticing).

What this document deliberately does NOT add: more reasoning modes, more phases, more
counterfactual machinery. Phases 2–3 are at diminishing returns; every gain left is in binding,
budgeting, and instrumentation.
