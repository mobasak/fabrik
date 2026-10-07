# T16 — Integration — whole-plan gate, doc receipt, docs review, seam tests

## Scope
Owns the whole-plan `python scripts/final_gate.py --check --json` + `check_convergence.py` run, the `check_doc_sync.py --range <baseline>..HEAD` + `check_doc_stubs.py --range` receipt, `/fabrik-docs-review` over every doc the plan touched, the cross-ticket seam-test run (T05a's fixture tests against T04b's `Epic:` interface; T07a's render test against T06a–c's sources; T15's owner parsing against T03a's field; T09's chain check against the three sources), the merge-time render in the main checkout (render → `--check` → commit, then `ls ~/.claude/skills | grep -c '^fab-'` = 0 and the three new skills present), and the fleet proof: one project (`/opt/transdoc`) synced, `.worktreeinclude` + `.claude/worktrees/` ignore + settings block + both git config keys present, and the spec's probe 3 re-run there (`claude -p --worktree agent-alpha … cat carried.txt`). Its Deltas carry the CHANGELOG/INDEX/docs/README consolidation and the STRATEGIC_BACKLOG row for the out-of-scope cockpit docs (I13). Receipt: `docs/development/reviews/2026-09-03-plan-1-multi-agent-per-repo-review.md`.

Depends: T01a, T01b, T02a, T02b, T03a, T03b, T13, T04a, T04b, T05a, T05b, T06a, T06b, T06c, T07a, T07b, T08a, T08b, T09, T10, T11, T12a, T12b, T14a, T14b, T14c, T14d, T14e, T14f, T14g, T14h, T15
Parallel: ⛓️
Complexity: native
Integration: true
Gate: python scripts/final_gate.py --check --json
Gate: bash -c 'set -e; allow="INDEX.md docs/STRATEGIC_BACKLOG.md tests/test_assemble_orch_retired.py tests/test_epic_order.py tests/test_check_review_coverage_rederivation.py"; got=$(git grep -l "epic-to-ticket-workflow\|_traycer-skills\|fab-mega-0\|fab-ettw-\|traycer_mirror\|traycer-command-wiring" -- ":!docs/orchestrator/_retired/" ":!docs/orchestrator/orchestrator-cockpit-*" ":!docs/development/epics/" ":!docs/CAPABILITIES.md" ":!capabilities.json" ":!docs/workstation/kaizen-shrink-audit.md" ":!docs/workstation/claude-configuration-inventory.md" ":!docs/DECISIONS.md" ":!CHANGELOG.md" ":!docs/LESSONS_LEARNT.md" ":!docs/development/reviews/" ":!docs/superpowers/" ":!docs/archive/" ":!docs/development/plans/" ":!.fabrik/plan-locks/" || true); for f in $got; do case " $allow " in *" $f "*) ;; *) echo "UNOWNED: $f"; exit 1;; esac; done'   # ALLOWLIST, not `| grep -x 0`: see Scope. `|| true` because git grep exits 1 on an empty result under `set -e`; the three test files are the absence-GRADERS that assert the tokens never come back (T07a's RETIRED_TOKEN_RE, T03a's forbidden-token loop, T14e's rederivation graders) — they carry the literals by construction (T14b/T14c round-1 finders, 2026-09-06)   # the TREE-WIDE zero assertion, moved here from T14b: this ticket merges last (Merge Order 33), so every ticket that clears a reference has landed.
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
