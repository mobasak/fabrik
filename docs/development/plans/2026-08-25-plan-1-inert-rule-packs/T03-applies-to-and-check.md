# T03 — applies_to frontmatter + the non-circular check

Depends: T02
Parallel: ⛓️
Complexity: native
Docs: docs/reference/rule-pack-reachability.md
Gate: python -m pytest tests/enforcement/test_pack_reachability.py -q

## Scope

Add a declared `applies_to:` frontmatter field and `scripts/enforcement/check_pack_reachability.py`
that reads it, consuming T02's `audit_layout(root, types)` as its engine and T04's
`pack_matches_path` / `packs_for_paths` for matching — by those exact names, never re-implemented — an INDEPENDENT expectation, never derived from the globs under test. Wire it into
`final_gate.py` as ADVISORY (WARN). Step 1 is the format decision, written down before any pack is
edited. DO-NOT derive applicability from `select_rules`' ACTIVE set: that is computed from the very
globs being tested (`scripts/select_rules.py:156`), so the check would pass forever. DO-NOT land it
blocking — 56 packs across 46 repos failing on day one is how a gate gets ignored.

## Touches

- scripts/enforcement/check_pack_reachability.py
- scripts/final_gate.py
- tests/enforcement/test_pack_reachability.py
- docs/reference/rule-pack-reachability.md

## Behavior Contract

- **Given** a pack whose `applies_to` names a scaffold type it cannot match, **When** the check runs, **Then** it reports that pack and does NOT derive applicability from the globs under test (scripts/enforcement/check_pack_reachability.py:1).
- **Given** a pack with no `applies_to` field, **When** the check runs, **Then** it passes silently rather than failing, so the field can land incrementally across 56 packs (scripts/enforcement/check_pack_reachability.py:1).

## Context Files

- scripts/select_rules.py
- scripts/final_gate.py
