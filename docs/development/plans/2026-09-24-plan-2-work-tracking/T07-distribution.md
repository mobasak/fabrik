# T07 — distribution: `work.py` rides the governance sync; the Task-tools env

## Scope

Implements the "fleet-synced" half of spec § The CLI — `scripts/work.py` (stdlib only, fleet-synced),
spec § Lifecycle adoption step 2 (the fleet gets `work.py` through the governance sync), and the
settings half of spec § The native Task list (D-392 ruling 1).

1. `scripts/fabrik_synced_manifest.py`: append `"work.py"` to `CORE_SCRIPTS`
   (`scripts/fabrik_synced_manifest.py:37-62`), right after `thread_anchor.py`, with a one-line comment
   saying `thread_anchor.py` imports it by path. The generated projects' `.gitignore` "Fabrik-synced"
   block follows from the list.
2. `.pre-commit-config.yaml`: add `work` to the `scripts/(…)\.py$` alternation of the
   `governance-sync` files-filter (`.pre-commit-config.yaml:164`), which today matches
   `scripts/thread_anchor.py` and not `scripts/work.py` (grounded with Python `re`, 2026-09-24).
   ⚠️ Write the edited file into the tree ONLY in the staging step: an unstaged
   `.pre-commit-config.yaml` makes pre-commit refuse every session's commit.
3. `.claude/settings.json` (fleet-synced, `scripts/fabrik_synced_manifest.py:261`): add a top-level
   `"env": {"CLAUDE_CODE_ENABLE_TASKS": "1", "CLAUDE_CODE_ENABLE_TODO_TOOLS": "1"}`. Grounded at plan
   time (2026-09-24, headless `claude -p --output-format stream-json`, the `system/init` event's
   `tools`): with this block in a project's `.claude/settings.json`, a run started with
   `CLAUDE_CODE_ENABLE_TASKS=0` in its environment — what the VS Code extension forces — lists
   `TaskCreate`, `TaskGet`, `TaskList`, `TaskUpdate` (106 tools); without it only `Task`, `TaskStop`
   (102). The Task list stays an in-session checklist, never the record (spec § The native Task list).

This ticket merges only after T03, so the synced copy of `work.py` is complete when it first reaches
the fleet. Every path here is a governance-sync trigger: the merge distributes to ~46 repos.

DO-NOT: `scripts/work.py`; the per-account `tasks/` link (T10 — `scripts/sysadmin/claude_rotate.py`).

Depends: T03
Parallel: ⛓️
Complexity: simple
Gate: .venv/bin/python -m pytest tests/test_synced_manifest.py tests/test_work_distribution.py -q
Docs: none here — docs/reference/work-tracking.md (T09) names the distribution

## Touches
- scripts/fabrik_synced_manifest.py — PRIMARY PATH
- .pre-commit-config.yaml
- .claude/settings.json
- tests/test_synced_manifest.py
- tests/test_work_distribution.py (new — all three rows: `CORE_SCRIPTS` and the generated gitignore block, the filter regex read back out of the YAML the way `scripts/governance_sync_postcommit.sh` reads it, and the settings `env`)

## Behavior Contract
- **Given** the merged manifest, **When** `CORE_SCRIPTS` and the generated gitignore block are read, **Then** both name `work.py` and `thread_anchor.py` together (spec § The CLI)
- **Given** the merged `.pre-commit-config.yaml`, **When** its `governance-sync` files regex is applied, **Then** it matches `scripts/work.py` and still matches `scripts/thread_anchor.py`, and it matches no other path it did not match before, over every path `git ls-files` lists (spec § Shape / infra)
- **Given** the merged `.claude/settings.json`, **When** it is parsed, **Then** its `env` sets `CLAUDE_CODE_ENABLE_TASKS` and `CLAUDE_CODE_ENABLE_TODO_TOOLS` to `"1"` and every existing key is unchanged (spec § The native Task list)

## Context Files
- docs/superpowers/specs/2026-09-24-work-tracking-design.md
- .windsurf/rules/core/45-testing-strategy.md
- scripts/governance_sync_postcommit.sh — how the filter regex is read back out of the YAML (the enforcer)
