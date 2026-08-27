# Review — the certification-denominator plan (adversarial lens)

Status: CLOSED — coverage-adjudicated exit, final round `found: 0, fixed: 0`

**Surface:** `docs/development/plans/2026-08-27-plan-1-certification-denominator.md` at
`HEAD 48057667`, across commits `fabe92cd · c35a3b0f · d5c85e76 · e2ecf803 · eab6a1a3 · 48057667`.

**Why this ran at all.** The plan had already been through **11 rounds of `/fabrik-plan-review`** and
was `Status: CONVERGED`. `/fabrik-review` is a different lens: `/fabrik-plan-review`'s rubric asks
*"is this plan correct and grounded"*; this one drives the **standing recurrence classes** —
fail-open vs fail-closed, cost/quota/limit, boundary/sentinel/prefix, behavior-without-a-test — which
that rubric never foregrounds. All three findings came from classes eleven prior rounds never swept.

**No agents.** Finders run natively per the operator's standing instruction. Compensating control:
every finding below is reproduced mechanically, not argued.

## Coverage Checklist

| # | Class | Verdict | Evidence |
|---|---|---|---|
| 1 | **fail-open vs fail-closed** | FIXED (1) | The anti-mix-up guard was advisory along with everything else. |
| 2 | **cost / quota / limit** | FIXED (1) | Nothing bounded the board's ticket COUNT at ~1,700 IDs. |
| 3 | **behavior-without-a-test** | FIXED (1) | Phase A3 promised tests for "the nine" rows; the contract had 23. |
| 4 | **boundary / sentinel / prefix** | CLEAN | `TC##` vs `T##` verified by executing the gate's own pattern. |
| 5 | Namespace separation (4 axes) | CLEAN | directory · `TC##` · `## Test Board` · `.fabrik/cert-locks/` all intact. |
| 6 | Runner routing | CLEAN | `Runner:` required and graded; `fix` does not close its test ticket. |

## Findings

**F1 — a SAFETY property was shipped as advisory.** Every check in the plan was `warn_only=True`,
including, implicitly, the guard that stops a cert board being dispatched to coding agents. The
operator's advisory ruling was about **coverage completeness** — nobody's release should freeze
because their real fraction became visible. It was never about a wrong-agent dispatch. A mis-headed
cert board puts CODING agents on a test board holding a lock `final_gate_stop.py:785` believes in;
a warn-only safety guard is one nobody reads until after the damage. Now **blocking from day one**,
with the ruling's scope stated so the distinction survives.

**F2 — nothing bounded the ticket COUNT.** The plan said *"one ticket per touchpoint group, sized so
a single agent can hold it"* — prose, ungraded. At ~1,700 IDs a naive generator emits 1,700 tickets
against a dispatcher that runs 3 at a time: ~570 dispatch cycles, technically "converged",
operationally never finishing. `check_plan_tickets.py:1318` bounds a single ticket's SIZE; nothing
bounds a board's LENGTH. Now a graded row.

**F3 — behavior-without-a-test, inside the plan that mandates it.** Phase A3 read *"the nine Behavior
Contract rows"* while the contract had grown to **23** — 14 rows with no test assigned. A literal
count in prose goes stale the moment the contract grows, so the count is no longer restated: the
phase gate asserts **parity** between contract rows and collected tests mechanically.

**Withdrawn (1).** Round 2 flagged "a literal count still present". It is the ⚠️ explanation
*quoting* the old text in past tense to record what the bug was — a live claim and a historical
quotation are not the same string-match, the identical detector mistake made earlier this session
against `ANTHROPIC_API_KEY` prose. Verified by reading the surrounding two lines before withdrawing.

## Pass Ledger

| Pass | finders | found | new | fixed |
|---:|---|---:|---:|---:|
| Pass 1 (WIDE) | native, all 6 classes | 3 | 3 | 3 |
| **Pass 2 (terminal)** | native, same 6 re-swept | **0** | **0** | **0** |

`found: 0, fixed: 0`. 25 contract rows, 0 ungradeable.

## What this says about the prior 11 rounds

Eleven `/fabrik-plan-review` rounds hardened this plan and none of them swept fail-open,
cost/quota or behavior-without-a-test. That is not a failure of diligence — it is what a rubric
does: it directs attention, and attention it does not direct is attention nobody pays. The standing
recurrence classes exist precisely because they are the ones a task-specific rubric omits.

## Verification

```
$ python scripts/final_gate.py --check --json
"status": "success"  (36 blocking / 0 failures)
```
