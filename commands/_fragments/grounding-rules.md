<!-- rule-grounding-gate v1 · twin-sync required: Traycer "My Workflow" fab-mega-00-trigger carries a copy of this block -->
## ⚠️ Rule-grounding gate (BINDING — governance is read into an artifact, never into memory)
Before the first architecture, tool, or dependency selection:
- Run `python scripts/select_rules.py` at the PROJECT root. Open every ACTIVE pack **plus** the
  always-AVAILABLE packs named in `agents-fabrik.md` § MANDATORY (they never self-mark ACTIVE —
  e.g. `core/ocoron-design-system.md`). Fresh reads only.
- Emit the **CONSTRAINTS DIGEST** as a checkpoint artifact: one row per MUST / BAN / anti-pattern
  relevant to this scope — `rule | pack:line | implication here`.
- Every subsequent selection cites a digest row or states `unconstrained`. A recommendation that
  collides with a digest row is DEAD at intake — external best-practice citations never outrank a row.
- A digest missing a rule an ACTIVE pack contains is an INCOMPLETE-DIGEST finding and blocks the
  exit. Self-assertion of "I read the packs" never counts as grounding.
