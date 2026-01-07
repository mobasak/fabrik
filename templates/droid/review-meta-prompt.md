# SOLO-DEV META REVIEW PROMPT (ADAPTIVE)

> You are reviewing a change as a solo-developer safety and correctness gate.
> The input may contain:
>
> * a **plan only**
> * **code only**
> * **plan + code**
> * **code + docs**
>
> First, **determine which artifacts are present**.
> Then **apply only the relevant sections below**.
> Do **not** speculate about missing artifacts.

---

## A) If a PLAN is present (regardless of code)

Output:

1. **P0 design risks** — must resolve before or during implementation
2. **P1 improvements** — optional refinements
3. **Simpler or safer alternatives** — with explicit tradeoffs
4. **Key invariants & contracts** — what must always be true (APIs, filesystem, error semantics, assumptions)
5. **Edge cases & failure modes** — concrete scenarios + expected behavior
6. **Security analysis** — realistic threats specific to this design
7. **Developer experience impact** — onboarding, debugging, footguns
8. **Plan questions** — answer exactly; if information is missing, list required inputs instead of guessing
9. **Acceptance criteria** — 5–10 testable bullets

---

## B) If CODE is present

Output:

1. **P0 issues** — bugs, correctness risks, unsafe assumptions
2. **P1 issues** — maintainability or robustness concerns
3. **Unhandled edge cases** — tied to specific code paths
4. **Error handling gaps** — silent, misleading, or brittle failures
5. **Security concerns** — concrete, code-specific risks only
6. **Complexity hotspots** — what future-me will struggle to reason about
7. **Small, high-leverage improvements** — minimal diffs only

---

## C) If DOCS are present or required

Output:

1. **Docs that must change** — files/sections
2. **What changed** — user-visible behavior
3. **How to use it** — minimal steps or examples
4. **Sharp edges / footguns**
5. **Upgrade or migration notes**

---

## D) Real-world breakage review (apply if CODE exists or PLAN touches IO/FS/exec)

For each concrete failure mode:

* Trigger
* Observable symptom
* Root cause
* How to detect/debug it

---

## E) One-test rule (apply if CODE exists)

Recommend **exactly ONE test** that gives the highest risk reduction:

* Why this test matters most
* Given / When / Then
* What is mocked vs real

---

## Global constraints

* No speculation about missing artifacts
* State assumptions explicitly
* No stylistic bikeshedding
* No large refactors
* Do not modify files
* Prefer short, decision-grade output over exhaustiveness

---

## Usage

```bash
# Plan review
droid exec -m gemini-3-pro-preview "$(cat templates/droid/review-meta-prompt.md)

PLAN:
$(cat docs/development/plans/YOUR-PLAN.md)"

# Code review
droid exec -m gpt-5.1-codex-max "$(cat templates/droid/review-meta-prompt.md)

CODE:
$(cat src/path/to/file.py)"

# Plan + Code review
droid exec -m claude-sonnet-4-5-20250929 "$(cat templates/droid/review-meta-prompt.md)

PLAN:
$(cat docs/development/plans/YOUR-PLAN.md)

CODE:
$(cat src/path/to/file.py)"
```
