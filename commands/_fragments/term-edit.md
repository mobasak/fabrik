## ⚠️ Termination contract — READ FIRST (the rule agents skip)

This is a LOOP, not a one-shot. It ends — and you may {{DONE_ACT}} — **only when a full, demonstrably-thorough round makes ZERO edits to the {{ARTIFACT}}** (a genuine no-op pass). Fixes open new gaps, so **the pass in which you edited the {{ARTIFACT}} is NEVER the last pass** — it MUST be followed by another full round. **Minimum two passes** whenever pass 1 changes anything.

Anti-cheat (mechanical, not vibes): record the {{ARTIFACT}}'s `md5sum` at the **start and end of the final pass**. Identical hash = a real no-op → {{DONE_WORD}}. Different hash = you edited → run another pass. A no-op asserted without matching hashes does not count.{{EXEMPT_NOTE}}

Maintain a numbered **Pass Ledger** and reproduce it verbatim in your report. You are done **only when the last row reads `edits: 0`** with `md5(start) == md5(end)`. Any last row with `edits > 0` means you owe the next pass — **run it UNPROMPTED, inside THIS invocation**, the moment it is owed; the obligation predates any challenge. Never end the turn on a non-zero row for the operator to re-invoke — **you return control EXACTLY ONCE: at the edit-free, md5-verified no-op.** Three thoughts that each mean *run the next pass now*: "it was already done," "the edit was trivial," "it's obviously clean."

| Pass | axes re-checked ({{AXES}}) | edits made | {{ARTIFACT}} md5 (start → end) |
|-----:|---|---:|---|
| 1 | all | 7 | a1b2… → 9f8e… |
| 2 | all | **0** | 9f8e… → 9f8e… ✓ → **{{DONE_WORD}}** |
