# T03b — the disjointness check becomes a real one

## Scope
`--check` has always been CREDITED with proving parallel-set `owned_paths` disjointness, and spec r11 (D-117) proved by execution that it does not. `check_integrity` (`scripts/epic_order.py:108-124`) intersects `owned_paths` as SETS OF GLOB STRINGS, and only for pairs that each name the other in `parallel_with`. Two epics owning `src/app/**` and `src/app/models/**`, declared parallel, raise NO finding though they share every file under `models/`; two epics with the byte-identical glob and an EMPTY `parallel_with` raise none either, while `phased_order()` places them in the SAME phase — i.e. dispatched together. Replace both halves: compare epics by PHASE (the output of `phased_order()`, which is what actually determines concurrency) rather than by the author-declared `parallel_with`, and test real path overlap rather than string equality — normalise each glob to its literal directory prefix and flag a finding when one prefix contains another. Keep the single-migration-owner check, re-keyed to phases the same way. This is a smoke test becoming a real one, so the two cases above are the watched-red ones. ⚠️ **Shares `check_integrity` with T03a** — the Depends edge serialises them. DO-NOT: touch `--assign` or the schema/checklist docs (T03a).

Depends: T03a
Parallel: ⛓️
Complexity: complex
Gate: python -m pytest tests/test_epic_order_disjointness.py -q
Docs: docs/superpowers/specs/2026-09-03-multi-agent-per-repo-design.md § Assignment already states the corrected claim; CHANGELOG.md · INDEX.md (new test) — orchestrator-applied

## Touches
- scripts/epic_order.py — PRIMARY PATH
- tests/test_epic_order_disjointness.py

## Behavior Contract
- **Given** two epics in the same `phased_order()` phase whose paths overlap — either as different globs (`src/app/**` vs `src/app/models/**`) or as identical globs with an EMPTY `parallel_with` — **When** `--check` runs, **Then** each case reports the overlap; today the first raises nothing and the second is never compared at all (scripts/epic_order.py:115)
- **Given** two epics in DIFFERENT phases with overlapping paths, **When** `--check` runs, **Then** no finding is raised — they never run concurrently (scripts/epic_order.py:127)
- **Given** two epics in one phase that both own migration globs, **When** `--check` runs, **Then** the single-migration-owner finding still fires, now keyed on the phase rather than on `parallel_with` (scripts/epic_order.py:119)

## Context Files
- .windsurf/rules/core/10-python.md
- docs/superpowers/specs/2026-09-03-multi-agent-per-repo-design.md
