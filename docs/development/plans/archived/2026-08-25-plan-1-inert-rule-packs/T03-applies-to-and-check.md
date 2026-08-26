# T03 — applies_to frontmatter + the non-circular check

Depends: T02
Parallel: ⛓️
Complexity: native
Docs: docs/reference/rule-pack-reachability.md
Gate: python -m pytest tests/enforcement/test_pack_reachability.py -q

## Scope

Build `scripts/enforcement/check_pack_reachability.py`, which reads the declared `applies_to:`
frontmatter field and reports any pack that claims a scaffold type it cannot reach. Consume T02's
`audit_layout(root, types)` as the engine and T04's `pack_matches_path` / `any_path_matches` for
matching — by those exact names, never re-implemented.

**The format is DECIDED, not an open question:** `applies_to: [<scaffold type>, …]` lives in each
pack's own frontmatter, beside the `globs:` it cross-checks. Chosen over a central
`scaffold-type → packs` registry because the declaration and the thing it contradicts must be
readable in one place — a registry drifts from the pack silently, which is the same failure this
plan exists to close. The cost is honest and accepted: `applies_to` is a new key in a fleet-synced
frontmatter across up to 56 packs, landing incrementally (T02 seeds the two it corrects).

Wire it into `final_gate.py` with
`run_optional_check("scripts/enforcement/check_pack_reachability.py", "Rule-pack reachability",
warn_only=True)` — `warn_only=True` implies `advisory` and marks the row non-blocking in every
output mode while still failing the gate if the check itself breaks
(`scripts/final_gate.py:221-248`).

DO-NOT derive applicability from `select_rules`' ACTIVE set: that is computed from the very globs
being tested (`scripts/select_rules.py:156`), so the check would pass forever. DO-NOT land it
blocking — 56 packs across 46 repos failing on day one is how a gate gets ignored. DO-NOT edit any
pack here; T02 owns the pack corpus.

## Touches

- scripts/enforcement/check_pack_reachability.py
- scripts/final_gate.py
- tests/enforcement/test_pack_reachability.py
- docs/reference/rule-pack-reachability.md

## Behavior Contract

- **Given** a pack whose `applies_to` names a scaffold type it cannot match, **When** the check runs, **Then** it reports that pack and does NOT derive applicability from the globs under test (scripts/enforcement/check_pack_reachability.py:1).
- **Given** a pack with no `applies_to` field, **When** the check runs, **Then** it passes silently rather than failing, so the field can land incrementally across 56 packs (scripts/enforcement/check_pack_reachability.py:1).
- **Given** the corpus as it stands after T02, **When** the check runs, **Then** it reports the count of packs it actually examined, so a corpus where nobody declares `applies_to` reads as "0 examined" rather than as a pass (scripts/enforcement/check_pack_reachability.py:1).

## Context Files

- scripts/select_rules.py
- scripts/final_gate.py
- scripts/enforcement/pack_layout_audit.py
