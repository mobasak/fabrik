<!-- rule-grounding-gate v2 · twin-sync required: nine docs/orchestrator/ files inline this block (grep the marker). The Traycer path needs NO separate copy — fab-mega-00-trigger is a thin wrapper (docs/orchestrator/_traycer-skills/) reading the canonical 00-trigger doc, one of the nine (the old server-side "My Workflow" copy is retired wiring; operator-confirmed no paste surface exists, 2026-08-30) -->
## ⚠️ Rule-grounding gate (BINDING — governance is read into an artifact, never into memory)
Before the first architecture, tool, or dependency selection:
- Run `python scripts/select_rules.py` at the PROJECT root for the ACTIVE census. **The MUST-READ-FULL
  set is COMPUTED, not everything:** the FLOOR packs + every pack
  `python scripts/review_rubric.py --changed <the surfaces this artifact will touch>` MATCHES, plus
  the always-AVAILABLE packs named in `agents-fabrik.md` § MANDATORY (they never self-mark ACTIVE —
  e.g. `core/ocoron-design-system.md`). **Fresh full reads of exactly that set** — a 26-pack duty
  where 3 are relevant teaches skimming, and skimming generalizes (operator ruling 2026-08-30);
  remaining ACTIVE/AVAILABLE packs are judgment reads.
- Emit the **CONSTRAINTS DIGEST** as a checkpoint artifact — a table, one row per MUST / BAN /
  anti-pattern relevant to this scope, **every row carrying a VERBATIM quote from the pack +
  `file:line`**: you cannot quote a line from a pack you did not open, which is the whole proof.
  `scripts/enforcement/check_rule_grounding.py` grades the countable subset on CONVERGED plans
  (quote-integrity + MATCHED-pack completeness, advisory); reading QUALITY stays with
  `/fabrik-plan-review`'s audit — the check never claims otherwise.
- Every subsequent selection cites a digest row or states `unconstrained`. A recommendation that
  collides with a digest row is DEAD at intake — external best-practice citations never outrank a row.
- A digest missing a rule a MUST-READ pack contains is an INCOMPLETE-DIGEST finding and blocks the
  exit. Self-assertion of "I read the packs" never counts as grounding.
