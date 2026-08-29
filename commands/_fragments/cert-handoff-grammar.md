**Machine-readable disposition rows (gate-parsed by `check_review_coverage.py` — exact grammar):** every
routed finding appears as one line in the report:
`HANDOFF P<0-3> OPEN <desc> — repro: <path> — route: <command> — evidence: <body/key-set/state one-liner>` ·
`HANDOFF P<0-3> CLOSED <desc> — repro: <path> — proof: <green-run one-liner>` ·
`DESIGN-GAP <desc> — brief: <docs/development/reviews/...-design-gap-*.md>` (operator decision, may stay open).
A CLOSED row without an existing repro path + proof fails the gate; an OPEN row routed to `/fabrik-review`
(the code-wrong route) without an `evidence:` slot fails the gate (the wire/state evidence is what proves
attribution — see Phase 4); any OPEN HANDOFF row requires the final
ledger marked `NOT-QUIET (routes outstanding)` AND a `## RESUME` section; NOT-QUIET requires `## RESUME`.
