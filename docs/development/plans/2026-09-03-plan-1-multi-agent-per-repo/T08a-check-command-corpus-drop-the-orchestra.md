# T08a — check_command_corpus: drop the orchestrator-wrapper audit path

## Scope
`scripts/enforcement/check_command_corpus.py`: delete `TRAYCER_SKILLS`, `_orch_corpus()` and its call site with the `elif assembler.exists()` "wrapper tree missing in the hub" problem — cited BY SYMBOL, never by line: a sibling grew this file by 355 lines between this plan's grounding and its commit (`_orch_corpus` moved 791 → 895, its call 912 → 1016), so `grep -n 'def _orch_corpus'` is the anchor. With the wrapper path gone, a hub without `docs/orchestrator/_traycer-skills/` is the normal state, not a defect; the three new sources are audited by the existing per-source predicates (run-record close sites, close-feedback, NEXT) with no special case. SPLIT NOTE: this ticket was T08 until the read budget forced the split — check + test together were 258,556 bytes against `READ_BUDGET_BYTES` 262144 while a sibling is actively growing both (rounds 63–64). The test edit is T08b, serialized behind this one. DO-NOT: touch `tests/test_check_command_corpus.py` (T08b); touch the assembler (T07) or delete the wrapper tree (T09).

Depends: T07
Parallel: ⛓️
Complexity: never-route
Gate: python3 scripts/enforcement/check_command_corpus.py
Gate: python3 -c "import importlib.util,sys; s=importlib.util.spec_from_file_location('c','scripts/enforcement/check_command_corpus.py'); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); sys.exit(any(hasattr(m,n) for n in ('_orch_corpus','TRAYCER_SKILLS')))"
Docs: CHANGELOG.md — orchestrator-applied; docs/reference/command-corpus-check.md is T14b's

## Touches
- scripts/enforcement/check_command_corpus.py — PRIMARY PATH

## Behavior Contract
- **Given** a hub tree with no `docs/orchestrator/_traycer-skills/` directory, **When** the check runs, **Then** it reports no wrapper-tree problem and audits the three new sources with the same predicates as every other source (scripts/enforcement/check_command_corpus.py — symbol `_orch_corpus` call site)
- **Given** the module, **When** imported, **Then** it exposes no `_orch_corpus` or `TRAYCER_SKILLS` name (scripts/enforcement/check_command_corpus.py:91 — the `TRAYCER_SKILLS` binding, the one anchor the sibling's 355-line growth did NOT move; `_orch_corpus` is cited by symbol because it did)

## Context Files
- .windsurf/rules/core/10-python.md
- docs/development/reviews/2026-09-03-orchestrator-chains-corpus-review.md
