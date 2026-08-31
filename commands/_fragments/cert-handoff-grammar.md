**Machine-readable disposition rows (gate-parsed by `check_review_coverage.py` — exact grammar):** every
routed finding appears as one line in the report:
`HANDOFF P<0-3> OPEN <desc> — repro: <path> — route: <command> — evidence: <body/key-set/state one-liner>` ·
`HANDOFF P<0-3> CLOSED <desc> — repro: <path> — proof: <green-run one-liner>` ·
`DESIGN-GAP <desc> — brief: <docs/development/reviews/...-design-gap-*.md>` (operator decision, may stay open).
A CLOSED row without an existing repro path + proof fails the gate; an OPEN row routed to `/fabrik-review`
(the code-wrong route) without an `evidence:` slot fails the gate (the wire/state evidence is what proves
attribution — see Phase 4); any OPEN HANDOFF row requires the final
ledger marked `NOT-QUIET (routes outstanding)` AND a `## RESUME` section; NOT-QUIET requires `## RESUME`.
**Severity is ASSIGNED by blast radius, not vibes** (`/fabrik-release` BLOCKS on P0/P1 and
operator-WARNs P2/P3, so the digit has teeth): **P0** = data loss / tenant-crossing / auth bypass /
money mischarged · **P1** = a journey a real consumer cannot complete, or a fail-open on system truth ·
**P2** = degraded-but-workaroundable behavior, latency-budget breaches, error-shape drift ·
**P3** = doc-drift, cosmetic payload issues. When torn between two tiers, take the HIGHER —
the operator can waive down (their waiver mints its ledger row); nobody catches a silent under-tier
(the grader parses the digit, never validates it). Only the two `HANDOFF` forms carry the digit —
`DESIGN-GAP` rows have NO severity slot in the parsed grammar; never write `DESIGN-GAP P1`, it
matches nothing and vanishes from the OPEN-row obligations (`/fabrik-release` blocks on an
operator-untouched DESIGN-GAP regardless).
