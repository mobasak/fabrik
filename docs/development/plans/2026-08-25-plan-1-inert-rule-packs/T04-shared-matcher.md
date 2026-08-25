# T04 — one shared path→pack matcher

Depends: none
Parallel: ⚡
Complexity: simple
Docs: none
Gate: python -m pytest tests/test_rules_match.py -q

## Scope

Extract the path→pack matcher into `scripts/rules_match.py` exposing EXACTLY these two symbols — the
spine's Interfaces block and T02/T03 consume them by name, so do not rename:
`pack_matches_path(path: str, glob: str) -> bool` (moved from `review_rubric.py:183 _glob_matches_path`)
and `packs_for_paths(paths: list[str], root: Path) -> list[str]`. Have `review_rubric.py` and
`select_rules.py` both import them; add `--changed` to `select_rules.py` so plan-stage routing asks the
same question review-time already asks. Collapses transdoc's items 3 and 4. DO-NOT change matching
BEHAVIOR while extracting — a pure move, proven by the existing rubric output being byte-identical
before and after. DO-NOT leave `select_rules.py:47 _GLOBS` in place as a second parser.

## Touches

- scripts/rules_match.py
- scripts/review_rubric.py
- scripts/select_rules.py
- tests/test_rules_match.py

## Behavior Contract

- **Given** a ticket's declared file list, **When** plan-stage pack routing runs, **Then** it returns the same pack set `review_rubric.py --changed` returns for those paths (scripts/rules_match.py:1).

## Context Files

- scripts/review_rubric.py
- scripts/select_rules.py
