# T16 — Integration — whole-plan gate, doc receipt, docs review, seam tests

## Scope
Owns the whole-plan `python scripts/final_gate.py --check --json` + `check_convergence.py` run, the `check_doc_sync.py --range <baseline>..HEAD` + `check_doc_stubs.py --range` receipt, `/fabrik-docs-review` over every doc the plan touched, the cross-ticket seam-test run (T05's fixture tests against T04's `Epic:` interface; T07's render test against T06a–c's sources; T15's owner parsing against T03's field; T09's chain check against the three sources), the merge-time render in the main checkout (render → `--check` → commit, then `ls ~/.claude/skills | grep -c '^fab-'` = 0 and the three new skills present), and the fleet proof: one project (`/opt/transdoc`) synced, `.worktreeinclude` + `.claude/worktrees/` ignore + settings block + both git config keys present, and the spec's probe 3 re-run there (`claude -p --worktree agent-alpha … cat carried.txt`). Its Deltas carry the CHANGELOG/INDEX/docs/README consolidation and the STRATEGIC_BACKLOG row for the out-of-scope cockpit docs (I13). Receipt: `docs/development/reviews/2026-09-03-plan-1-multi-agent-per-repo-review.md`.

Depends: T01a, T01b, T02, T05a, T05b, T09, T10, T11, T12a, T12b, T13, T14a, T14b, T14c, T15
Parallel: ⛓️
Complexity: native
Integration: true
Gate: python scripts/final_gate.py --check --json
Gate: python3 scripts/enforcement/check_convergence.py
Docs: the whole-plan Doc Sync Matrix receipt (`check_doc_sync.py --range` + `check_doc_stubs.py --range`) · /fabrik-docs-review · CHANGELOG/INDEX/docs/README consolidation via Deltas

## Touches
- docs/development/reviews/2026-09-03-plan-1-multi-agent-per-repo-review.md

## Behavior Contract
- **Given** every work ticket merged, **When** the whole-plan gate and `check_convergence.py` run, **Then** both are green and the receipt embeds the verbatim `"status": "success"` block
- **Given** `/opt/transdoc` after one sync, **When** the four artifacts and both git config keys are probed, **Then** all are present and `claude -p --worktree agent-alpha` prints `worktree-agent-alpha` and the carried file's content
- **Given** the merge-time render, **When** `ls ~/.claude/skills` is listed, **Then** it holds `fabrik-vision`, `fabrik-epics`, `fabrik-epics-review` and 0 `fab-*` entries

## Context Files
- docs/superpowers/specs/2026-09-03-multi-agent-per-repo-design.md
