# T01 — Adoption artifacts — .worktreeinclude, settings worktree block, .claude/worktrees ignore, git config keys

## Scope
Emit the four per-project adoption artifacts the spec § Lifecycle names, from the hub's existing sync paths — no new distribution mechanism. (1) `scripts/fabrik_synced_manifest.py` gains `worktreeinclude_text()` beside `gitignore_block_text()` (`scripts/fabrik_synced_manifest.py:229`): every `gitignore_dest_paths()` entry (`:181`) plus `.env` and `.mcp.json`, minus `.claude/settings.local.json` (approvals stay in the main checkout — worktrees doc § "What worktrees share"); the rendered text is a TRACKED file `templates/governance/.worktreeinclude` listed in the manifest so the sync AND the scaffolder (which mirrors the manifest — `src/fabrik/scaffold.py:539-556` builds its `.gitignore` block from `gitignore_block_text()`, `:1216` mirrors the synced set) distribute it with zero scaffold edits; a test asserts tracked == generated so the file cannot drift. (2) `gitignore_block_text()` gains `.claude/worktrees/` (absent today: the hub only carries it in `.git/info/exclude:11`). (3) The hub's `.claude/settings.json` — the SYNCED SOURCE for every project's settings (`scripts/fabrik_synced_manifest.py:131`, `AGENT_HOOK_FILES`) — gains exactly `{"worktree": {"baseRef": "head", "symlinkDirectories": [".venv"]}}`; the block is inert on the hub (hub sessions do not launch worktrees — spec § Decisions derived (b)), so hub adoption of the MODEL stays deferred while the settings SOURCE carries the block. (4) `scripts/sync_enforcement_to_projects.py` sets `rerere.enabled true` + `push.autoSetupRemote true` per project beside the `.gitignore` patch (`:660-700`), idempotent, dry-run prints only; and adds the R3 re-copy loop — for each `git worktree list --porcelain` entry under the project's `.claude/worktrees/`, re-copy the manifest's gitignored set, printing the count — MEASURED on the first fleet run before it stays (FIX DIRECTIVE 5: a loop that fires on 0 worktrees costs nothing; record the fire rate in the ticket's review). R1 probe (self-service): in a scratch repo with a CLAUDE.md line directing `EnterWorktree`, run `claude -p --max-turns 2` and `ls` the worktree for a carried gitignored file; if `.worktreeinclude` is not applied on `EnterWorktree`, the contract line (T14a) already names `--worktree` as the only launch form — record the result in the receipt. DO-NOT: touch `src/fabrik/scaffold.py` (278 KB, above the read budget, and unnecessary — it reads the manifest); touch `templates/governance/CLAUDE.md` (T14a).

Depends: —
Parallel: ⚡
Complexity: native
Gate: python -m pytest tests/test_synced_manifest.py tests/test_sync_worktree_adoption.py -q
Gate: python3 scripts/sync_enforcement_to_projects.py --dry-run 2>&1 | grep -c 'worktree' ; test "$(git diff --stat -- /opt/transdoc | wc -l)" = 0
Docs: docs/reference/multi-agent-operating-model.md (T15 owns the doc; this ticket supplies its four artifact names) · CHANGELOG.md · INDEX.md (new files) — orchestrator-applied

## Touches
- scripts/fabrik_synced_manifest.py — PRIMARY PATH
- scripts/sync_enforcement_to_projects.py
- templates/governance/.worktreeinclude
- .claude/settings.json
- tests/test_synced_manifest.py
- tests/test_sync_worktree_adoption.py

## Behavior Contract
- **Given** the manifest, **When** `worktreeinclude_text()` renders, **Then** it lists every `gitignore_dest_paths()` entry plus `.env` and `.mcp.json` and never `.claude/settings.local.json` (scripts/fabrik_synced_manifest.py:181)
- **Given** `templates/governance/.worktreeinclude` differs from `worktreeinclude_text()`, **When** `tests/test_synced_manifest.py` runs, **Then** it fails naming the regeneration command (scripts/fabrik_synced_manifest.py:229)
- **Given** `gitignore_block_text()`, **When** rendered, **Then** it contains the line `.claude/worktrees/` (scripts/fabrik_synced_manifest.py:229)
- **Given** a project directory, **When** the sync runs without `--dry-run`, **Then** `git -C <project> config rerere.enabled` prints `true` and `push.autoSetupRemote` prints `true`, and a second run changes nothing (scripts/sync_enforcement_to_projects.py:660)
- **Given** a project with a linked worktree under `.claude/worktrees/`, **When** the sync lands, **Then** the manifest's gitignored set is re-copied into that worktree and the run prints the worktree count (scripts/sync_enforcement_to_projects.py:840)
- **Given** the hub `.claude/settings.json`, **When** parsed, **Then** `worktree` equals exactly `{"baseRef": "head", "symlinkDirectories": [".venv"]}` and the `hooks`/`permissions` keys are byte-identical to before (scripts/fabrik_synced_manifest.py:131)

## Context Files
- docs/superpowers/specs/2026-09-03-multi-agent-per-repo-design.md
- .windsurf/rules/core/10-python.md
- scripts/enforcement/check_sync_trigger_coverage.py
