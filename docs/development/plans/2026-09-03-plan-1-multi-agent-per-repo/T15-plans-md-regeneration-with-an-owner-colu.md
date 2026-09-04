# T15 — PLANS.md regeneration with an Owner column, and the dedicated reference doc

## Scope
(1) `scripts/docs_updater.py`: `generate_plans_table()` (`:876`, a tested utility with no live caller) changes THREE columns, not one — today it emits `| Plan | Date | Status | Progress |` (`scripts/docs_updater.py:884,901`) and the spec asks for `| Epic/Plan | Owner | Status | Phase |`: `Date` is dropped, `Owner` is added, and `Progress` is renamed to `Phase`. **`Phase` needs a defined source, which the spec does not give it** — use the epic's `epic_order.phased_order()` position for an epic row and the spine's Board progress (`<checked>/<total>` as today) for a plan row, and say so in the generated block's header comment so the column is never ambiguous. `Owner` is read from a plan's `**Owner:**` line (T04b makes it mandatory at creation), a spine's `Owner:` header, or epic frontmatter `owner` under `docs/development/epics/`; `sync_plans_index()` (`:915`, "Skipped (Traycer-managed)") regenerates the `AUTO-GENERATED:PLANS` block (`PLANS_BLOCK_RE`, `:640`) in `docs/development/PLANS.md` the same Tier-0 way `STRUCTURE` is regenerated (`:1240`); `validate_plans_indexed()` (`:920`) returns a finding when the block is stale (the `--check` path). Untagged epics/plans render `—` in Owner — the sweep at the tail (spec § Personas, agent-1) is where they get filled. (2) **`docs/reference/plan-lock-lifecycle.md`** — the canonical lock doc, which this design makes partly untrue and which no ticket owned after the relocation was withdrawn. Its opening claim (*"the lock is what lets several scoped plan runs share one project without colliding … step 7 scans for an overlapping active lock before starting"*) is per-worktree-blind under this model: add one paragraph saying locks are per working tree, step 7's overlap scan sees only this tree, and cross-tree visibility is R7 and unbuilt. While there, fix its stale `final_gate_stop.py:785` citation (cite `_midrun_marker` by symbol). (3) `docs/reference/multi-agent-operating-model.md` (new, ≤150 lines): the launch recipe per window, the four emitted artifacts (T01a declares them, T01b emits them), the merge protocol (rebase-first, `--no-ff`, phase order, `rerere`), the lock location, the shared-DB caveat, the retirement recipe, the residual probes' results — written from the spec's § Chosen approach / § Lifecycle, cited by section; the hub-vs-project caveat (spec § Decisions derived (b)). DO-NOT: hand-edit the generated block; touch `INDEX.md`/`docs/README.md` (orchestrator Deltas).

Depends: T03a
Parallel: ⛓️
Complexity: complex
Gate: python -m pytest tests/test_docs_updater.py -q
Gate: bash -c 'python3 scripts/docs_updater.py --check 2>&1 | grep -E "PLANS\.md|multi-agent-operating-model|plan-lock-lifecycle" ; test ${PIPESTATUS[1]} -eq 1'   # SCOPED: `--check` is REPO-GLOBAL with no --path/--range flag (`--check-files` only applies with --task-file/--prompt), and it exits 1 today on 123 lines of PRE-EXISTING debt in other plans — 0 of which name PLANS.md or this plan set. An unscoped gate here is unsatisfiable inside this ticket's Touches: the coder would have to fix seven unrelated docs on a shared tree. This form passes only when NONE of this ticket's own three docs is named in the output. The repo-wide green is not this ticket's to deliver and is not gated anywhere in this plan.
Docs: docs/reference/multi-agent-operating-model.md (NEW — the Doc Sync Matrix 'new subsystem' row) · INDEX.md + docs/README.md rows · docs/development/PLANS.md (regenerated block) · CHANGELOG.md — orchestrator-applied except PLANS.md, which this ticket owns

## Touches
- scripts/docs_updater.py — PRIMARY PATH
- tests/enforcement/test_plan_shape_gates.py
- tests/test_docs_updater.py
- docs/development/PLANS.md
- docs/reference/multi-agent-operating-model.md
- docs/reference/plan-lock-lifecycle.md

## Behavior Contract
- **Given** two plans with `**Owner:** alpha` / no owner and one epic with `owner: beta`, **When** `generate_plans_table()` runs, **Then** the rows carry `alpha`, `—`, `beta` in the Owner column, the header reads `| Epic/Plan | Owner | Status | Phase |`, and the two existing call sites in `tests/enforcement/test_plan_shape_gates.py` still pass (scripts/docs_updater.py:884)
- **Given** `docs/development/PLANS.md` with a stale `AUTO-GENERATED:PLANS` block, **When** `docs_updater.py` runs, **Then** the block is regenerated in place and `--check` afterwards reports no PLANS finding (scripts/docs_updater.py:915)
- **Given** the same file untouched, **When** `docs_updater.py --check` runs, **Then** it reports the PLANS block stale (scripts/docs_updater.py:920)
- **Given** the new reference doc, **When** `check_doc_links.py` and the INDEX row check run, **Then** both pass and the doc names the four artifacts, the launch form and the lock path exactly as T01a/T01b and T04a/T04b implement them (scripts/docs_updater.py:640)

## Context Files
- docs/superpowers/specs/2026-09-03-multi-agent-per-repo-design.md
- .windsurf/rules/core/40-documentation.md
- scripts/epic_order.py
