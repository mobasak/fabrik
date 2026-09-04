# T14h — the cert-coverage anchors, a non-relocation fix rescued from a deleted ticket

## Scope
`scripts/enforcement/check_certification_coverage.py:24` and `:258`, and `tests/enforcement/test_certification_coverage.py:176`, all cite `.claude/hooks/final_gate_stop.py:785` when pointing at the mid-run marker. That line is inside `_last_assistant_text`; the real function is `_midrun_marker` at `:856`, with the lock read at `:864`. Cite `_midrun_marker` BY SYMBOL at all three sites, per § Global Constraints' anchors-move rule. ⚠️ **This is anchor rot, not lock work.** It was item 2 of the deleted T05e, and an author-blind pass caught that deleting that ticket dropped it silently — the only NON-relocation item the three deletions took with them. It lives here rather than in T14b because adding these two files to that ticket pushed it to 288,669 B against a 262,144 budget. DO-NOT: change any cert-coverage behaviour; this is three citations.

Depends: —
Parallel: ⚡
Complexity: never-route
Gate: python -m pytest tests/enforcement/test_certification_coverage.py -q
Gate: test -z "$(git grep -n 'final_gate_stop.py:785' -- scripts/enforcement/check_certification_coverage.py tests/enforcement/test_certification_coverage.py)" && test "$(git grep -l '_midrun_marker' -- scripts/enforcement/check_certification_coverage.py tests/enforcement/test_certification_coverage.py | wc -l)" = 2
Docs: CHANGELOG.md — orchestrator-applied

## Touches
- scripts/enforcement/check_certification_coverage.py — PRIMARY PATH
- tests/enforcement/test_certification_coverage.py

## Behavior Contract
- **Given** the three citation sites after this ticket, **When** grepped for `final_gate_stop.py:785`, **Then** the count is 0 and each names `_midrun_marker` by symbol (scripts/enforcement/check_certification_coverage.py:258)
- **Given** the cert-coverage check, **When** its suite runs, **Then** behaviour is unchanged — this ticket edits citations only (tests/enforcement/test_certification_coverage.py:176)

## Context Files
- .claude/hooks/final_gate_stop.py
