# T04 — one shared path→pack matcher

Depends: none
Parallel: ⚡
Complexity: simple
Docs: none
Gate: python -m pytest tests/test_rules_match.py -q

## Scope

Extract the path→pack matcher into `scripts/rules_match.py` exposing EXACTLY these three symbols —
the spine's Interfaces block and T02/T03 consume them by name, so do not rename:

- `pack_matches_path(path: str, glob: str, *, empty_matches_all: bool) -> bool` — the single-path
  matcher, moved from `review_rubric.py:183 _glob_matches_path`.
- `any_path_matches(root: Path, glob: str, *, empty_matches_all: bool) -> bool` — the root-scan,
  moved from `select_rules.py:123 _glob_has_match`.
- `packs_for_paths(paths: list[str], root: Path) -> list[str]`.

⚠️ **This is NOT one function with two callers, and the move is NOT behavior-identical for both.**
The two existing matchers differ in TWO ways and both differences are load-bearing:
(a) shape — `_glob_matches_path` matches ONE path (walking its `_prefixes`), `_glob_has_match` scans
the whole tree via `_tree_paths` (files AND directories, `_EXCLUDE`-pruned; the pruned single walk is
what stopped the 2026-07-18 hang, so `any_path_matches` must keep it — never re-walk per glob);
(b) the empty-pattern branch — `review_rubric.py:191-194` returns **True** ("arming errs SAFE") where
`select_rules.py:130-131` returns **False** ("empty = not-ACTIVE"), a divergence its own comment calls
deliberate. That is why `empty_matches_all` is an explicit keyword, not a default: `review_rubric`
passes `True`, `select_rules` passes `False`. Collapsing it silently would change the ACTIVE/AVAILABLE
split in ~46 repos.

Have `review_rubric.py` and `select_rules.py` both import from `rules_match`. **There are THREE call
sites, not two** — `select_rules.py:156` (the ACTIVE/AVAILABLE split), `select_rules.py:177`
(`globs_fired` in the JSON output) and `review_rubric.py:241` (rubric hits); missing `:177` leaves a
dangling reference to the removed private helper. Add `--changed` to
`select_rules.py` so plan-stage routing asks the same question review-time already asks. Collapses
transdoc's items 3 and 4.

DO-NOT change matching BEHAVIOR while extracting — a pure move at each call site, proven by the
existing `review_rubric.py --changed` output AND `select_rules.py` ACTIVE/AVAILABLE output both being
byte-identical before and after. DO-NOT touch `select_rules.py:47 _GLOBS` — it is the FRONTMATTER
parser (`^globs:\s*\[(.*?)\]`), a different concern from path matching and explicitly out of scope
for this ticket.

## Touches

- scripts/rules_match.py
- scripts/review_rubric.py
- scripts/select_rules.py
- tests/test_rules_match.py

## Behavior Contract

- **Given** a ticket's declared file list, **When** plan-stage pack routing runs, **Then** it returns the same pack set `review_rubric.py --changed` returns for those paths (scripts/rules_match.py:1).
- **Given** a wildcard-only glob and the two callers' opposite conventions, **When** the shared matcher runs, **Then** `empty_matches_all=True` matches and `empty_matches_all=False` does not, preserving both call sites unchanged (scripts/review_rubric.py:194).

## Context Files

- scripts/review_rubric.py
- scripts/select_rules.py
