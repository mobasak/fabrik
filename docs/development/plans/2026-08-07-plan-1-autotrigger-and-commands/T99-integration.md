# T99 — Integration: parity, seams, receipts

Depends: T01, T02, T03, T04, T05, T06a, T06b, T07, T08
Parallel: ⛓️
Complexity: native
Docs: whole-plan receipts (doc-sync ranges) via Deltas
Gate: python commands/assemble_commands.py --check && python scripts/final_gate.py --check --json && python -m scripts.enforcement.check_convergence
Integration: true

## Scope

The set's closing Board unit. Run: (1) full render — 24 commands + 24 skills (20 existing incl. design-review + 4 new), `--check` clean;
(2) the three seam tests from the spine `## Interfaces`: Stage-line presence/vocabulary across ALL
24 rendered skills (brace glob — a bare fabrik-* skips design-review), assembler wiring parity,
router roster probe sees 23 fabrik-prefixed; (3) whole-plan doc
receipts — `check_doc_sync.py --range <baseline>..HEAD` + `check_doc_stubs.py --range` clean;
(4) cross-ticket consistency spot-checks: the four new commands' TRIGGER/Stage lines match T06's
style; T07's stage table matches the spine taxonomy verbatim; T05's injected directive format
matches T07's escape wording; (5) `bash scripts/dr_claude_backup.sh` (renders changed ~/.claude);
(6) full Tier-2 gate + `check_convergence` green. DO-NOT: write code fixes here — a red routes a
fixup to the owning ticket (the dispatcher's consumer-fixup rule).

## Touches

- docs/reference/receipts-2026-08-07-autotrigger.md

## Behavior Contract

- **Given** all tickets merged, **When** T99 runs, **Then** 24 commands + 24 skills render with `--check` clean, parity + Stage seam tests pass (roster probe: 23 fabrik-prefixed), doc receipts and the full Tier-2 gate are green (commands/assemble_commands.py:1).

## Context Files

- the spine (`## Interfaces` seam tests + `## Global Constraints` taxonomy)
- commands/assemble_commands.py (render + --check)
- scripts/enforcement/check_doc_sync.py (--range receipt mode)
- scripts/dr_claude_backup.sh (config DR after render)
