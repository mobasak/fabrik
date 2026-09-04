# T01a — the manifest declares the worktree artifacts

## Scope
The DECLARATION half of the four adoption artifacts, all inside the synced manifest (spec § Lifecycle). (1) `scripts/fabrik_synced_manifest.py` gains `worktreeinclude_text()` beside `gitignore_block_text()` (`scripts/fabrik_synced_manifest.py:229`): every `gitignore_dest_paths()` entry (`:181`) plus `.env` and `.mcp.json`, minus `.claude/settings.local.json` (approvals stay in the main checkout — worktrees doc § "What worktrees share"). (2) The rendered text lands as a TRACKED file `templates/governance/.worktreeinclude`, listed in the manifest so the sync AND the scaffolder distribute it with zero scaffold edits — `src/fabrik/scaffold.py:539` builds its `.gitignore` block from `gitignore_block_text()` already, so the scaffolder needs no change. (3) `gitignore_block_text()` gains the line `.claude/worktrees/` (absent today: the hub only carries it in `.git/info/exclude:11`). A test asserts the TRACKED file equals the generated text, so the two can never drift. SPLIT NOTE: this was T01 until the breadth check scored it 9 (3 areas × 6 behaviours); T01b takes the ACTING half (what the sync DOES). The seam is declaration-vs-action, and each half is testable alone. DO-NOT: touch `scripts/sync_enforcement_to_projects.py` or `.claude/settings.json` (T01b); touch `src/fabrik/scaffold.py` (278 KB, and it already reads the manifest).

Depends: —
Parallel: ⚡
Complexity: native
Gate: python -m pytest tests/test_synced_manifest.py -q
Gate: python3 -c "import sys; sys.path.insert(0,'scripts'); import fabrik_synced_manifest as m; b=m.gitignore_block_text(); w=m.worktreeinclude_text(); assert '.claude/worktrees/' in b, 'gitignore block missing .claude/worktrees/'; assert '.env' in w and '.mcp.json' in w, 'worktreeinclude missing .env/.mcp.json'; assert 'settings.local' not in w, 'worktreeinclude must exclude .claude/settings.local.json'; print('manifest ok')"
Docs: CHANGELOG.md · INDEX.md (new tracked file) — orchestrator-applied

## Touches
- scripts/fabrik_synced_manifest.py — PRIMARY PATH
- templates/governance/.worktreeinclude
- tests/test_synced_manifest.py

## Behavior Contract
- **Given** the manifest, **When** `worktreeinclude_text()` renders, **Then** it lists every `gitignore_dest_paths()` entry plus `.env` and `.mcp.json`, and never `.claude/settings.local.json` (scripts/fabrik_synced_manifest.py:181)
- **Given** `templates/governance/.worktreeinclude` differs from `worktreeinclude_text()`, **When** the test runs, **Then** it fails naming the regeneration command (scripts/fabrik_synced_manifest.py:229)
- **Given** `gitignore_block_text()`, **When** rendered, **Then** it contains the line `.claude/worktrees/` (scripts/fabrik_synced_manifest.py:229)

## Context Files
- docs/superpowers/specs/2026-09-03-multi-agent-per-repo-design.md
- .windsurf/rules/core/10-python.md
