# T01b — the sync emits the worktree artifacts into every project

## Scope
The ACTING half (spec § Lifecycle). (1) `scripts/sync_enforcement_to_projects.py` sets `rerere.enabled true` and `push.autoSetupRemote true` per project, beside the existing `.gitignore` patch site (`scripts/sync_enforcement_to_projects.py:660`), idempotent, printing only under `--dry-run`. (2) It adds the R3 re-copy loop: for each `git worktree list --porcelain` entry under the project's `.claude/worktrees/`, re-copy the manifest's gitignored set and print the count — `.worktreeinclude` copies at CREATION only, so a mid-epic sync otherwise updates the main checkout alone while `check_synced_unmodified.py` stays green against a stale `.fabrik/synced.lock` copied at creation. MEASURE its fire rate on the first fleet run and record it in the ticket's review (FIX DIRECTIVE 5: a loop that fires on zero worktrees costs nothing; keep it only if that holds). (3) The hub's `.claude/settings.json` — the synced SOURCE for every project's settings (`scripts/fabrik_synced_manifest.py:131`, `AGENT_HOOK_FILES`) — gains exactly `{"worktree": {"baseRef": "head", "symlinkDirectories": [".venv"]}}`; inert on the hub, whose adoption of the model stays deferred (spec § Decisions derived (b)). R1 probe (self-service): in a scratch repo whose CLAUDE.md directs `EnterWorktree`, run `claude -p --max-turns 2` and `ls` the worktree for a carried gitignored file; record the answer in the receipt — if `.worktreeinclude` is not applied on that path, the contract line (T14a) already names `--worktree` as the only launch form. SPLIT NOTE: the other half is T01a. DO-NOT: touch the manifest or the tracked `.worktreeinclude` (T01a); touch `templates/governance/CLAUDE.md` (T14a).

Depends: T01a
Parallel: ⛓️
Complexity: native
Gate: python -m pytest tests/test_sync_worktree_adoption.py -q
Gate: python3 -c "import json; d=json.load(open('.claude/settings.json'))['worktree']; assert d == {'baseRef':'head','symlinkDirectories':['.venv']}, d; print('settings ok')"
Docs: CHANGELOG.md · INDEX.md (new test) — orchestrator-applied

## Touches
- scripts/sync_enforcement_to_projects.py — PRIMARY PATH
- .claude/settings.json
- tests/test_sync_worktree_adoption.py

## Behavior Contract
- **Given** a project directory, **When** the sync runs without `--dry-run`, **Then** `git -C <project> config rerere.enabled` prints `true` and `push.autoSetupRemote` prints `true`, and a second run changes nothing (scripts/sync_enforcement_to_projects.py:660)
- **Given** a project with a linked worktree under `.claude/worktrees/`, **When** the sync lands, **Then** the manifest's gitignored set is re-copied into that worktree and the run prints the worktree count (scripts/sync_enforcement_to_projects.py:840)
- **Given** a project with NO worktrees, **When** the sync runs, **Then** the loop performs no copy and the run's output is otherwise unchanged (scripts/sync_enforcement_to_projects.py:840)
- **Given** the hub `.claude/settings.json`, **When** parsed, **Then** `worktree` equals exactly `{"baseRef": "head", "symlinkDirectories": [".venv"]}` and the `hooks`/`permissions` keys are byte-identical to before (scripts/fabrik_synced_manifest.py:131)

## Context Files
- docs/superpowers/specs/2026-09-03-multi-agent-per-repo-design.md
- scripts/enforcement/check_sync_trigger_coverage.py
- scripts/fabrik_synced_manifest.py
