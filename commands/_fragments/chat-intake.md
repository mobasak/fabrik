## ⚠️ Intake Inventory — the conversation IS a denominator (build it before you design anything)

This run was invoked ON a conversation. That conversation surfaced items — issues found, goals
stated, features requested, constraints named, exclusions declared — and every one of them is part
of this run's denominator, exactly as a route inventory is a gauntlet's. The live defect this block
exists to kill (operator, 2026-08-29): *a session finds 10 issues, the operator says spec it, the
agent specs some of them, tells no one, and the operator chases the rest.* Silent subsetting.

**First act after the run record — enumerate, before you design:**

1. **Re-read the conversation** — the WHOLE session, not your memory of it (post-compact, use
   `session-recall` to recover what the summary dropped; if the operator referenced an earlier
   discussion, `search_chats` for it). Extract every distinct item the operator stated or the
   session surfaced: each issue/finding, each goal, each requested feature, each constraint, each
   explicit exclusion.
2. **Number them `I1…In`, each anchored to the operator's own words** — a short verbatim quote per
   item, so the mapping is checkable against the transcript rather than against your paraphrase.
3. **The artifact carries `## Intake Inventory`** — one row per item:

   | I# | Item (anchored) | Disposition | Where |
   |---|---|---|---|

   Disposition is EXACTLY one of: **IN** (the section of this artifact that covers it) ·
   **OUT-OF-SCOPE** (the one-line why + a NAMED destination that now exists: a backlog row you
   wrote, a separate spec you named, a mail you sent — "later" with no destination is a silent
   drop wearing a label) · **ASK** (it joins the batched question set, per the question bar).

**Zero silent drops.** An item you noticed but left off the table is THE defect — worse than a
wrong disposition, because a wrong disposition can be argued and a missing row cannot be seen.
OUT-OF-SCOPE is legitimate and often right; UNDECLARED out-of-scope is what turns the operator
into your coverage checker.

**Say the split when you finish.** The close-out states the fraction in one line —
`Intake: N items — X IN, Y OUT-OF-SCOPE (each named above), Z ASK` — so the operator sees the
subsetting instead of discovering it. A run that ends without this line has hidden its denominator.
