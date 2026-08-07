# Strategic Backlog

**Last Updated:** YYYY-MM-DD

> **Purpose:** DEFERRED-WORK LEDGER — the parking lot for improvements, refactors, and
> prevention items that are real but NOT now. One honest list, so ideas survive session
> boundaries without derailing the current plan.

<!--
  HOW TO FILL: any agent (or the operator) appends here when work surfaces that is
  out of the current scope — a review finding accepted-not-fixed, a "we should
  eventually X", a fragility observed in production. Every item needs a TRIGGER
  (what makes it become active work), not just a wish. Items with no trigger rot.

  This file feeds planning: /fabrik-spec's duplicate-check reads it, and a plan
  picking up an item should DELETE the row (the plan file is now its record).
-->

---

## Now — Ready for Focus Window

| Effort | Item | Why Priority | Ready When |
| :--- | :--- | :--- | :--- |
| **M** | [Feature/Refactor] | [1-liner value] | [Specific trigger] |
| **S** | [Small hardening/refactor] | [1-liner value] | [Specific trigger] |

<!-- Effort key: S < 2h · M = half-day · L = multi-day (multi-day items usually
     deserve the /fabrik-spec pipeline, not a backlog row). -->

---

## Later

- [ ] **[Item]**: [Brief description]. Blocked by [resource/trigger].
- [ ] **[Item]**: [Brief description]. Blocked by [resource/trigger].

---

## Context — hard-won constraints future work must respect

- ⚠️ **[System X]**: Avoid [Library A]; use [Library B]. Prior attempt failed due to [Z].
- 💡 **[Pattern Insight]**: [Lesson to preserve regarding architecture or logic.]

<!-- Boundary: durable HOW-we-work lessons belong in docs/LESSONS_LEARNT.md; this
     section is only for constraints that shape FUTURE FEATURE choices here. -->

---

## Activation

Items move to active development when:

1. **Focus window opens** — a block of 4+ hours of uninterrupted time is identified.
2. **Resource/budget availability** — external tools, APIs, or budget tiers become accessible.
3. **Measurable failure** — a "functional but fragile" component produces a real incident
   (link the TROUBLESHOOTING.md entry); prevention is promoted to a plan at the second occurrence.
