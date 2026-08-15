# T02b — Fleet gitignore: `.claude/settings.local.json` ignored in every project

## Scope
Add `.claude/settings.local.json` to `gitignore_dest_paths()`
(`scripts/fabrik_synced_manifest.py:147`) so the rendered Fabrik-synced block (`:183-211`)
ignores the carrier file fleet-wide — no ignore rule exists anywhere today (adversary finding
B3: without it every project would COMMIT a hardcoded absolute path). Ground first whether
`templates/scaffold/gitignore-synced-block.txt` is generated from the manifest or
hand-maintained (the manifest header at `scripts/sync_enforcement_to_projects.py:37` says the
manifest is the single source shared with `scaffold.py`) and update whichever is real — never
both blindly. ⚠️ Sync-consciousness: the manifest edit distributes fleet-wide via the
governance-sync pre-commit; the ignore line is correct for ALL ~46 projects (untracked local
state must never be committed). DO-NOT: no other manifest group changes; no scaffolder logic
changes (T02a's file is out of scope here).

Depends: —
Parallel: ⚡
Complexity: native
Gate: .venv/bin/python -m pytest tests/ -q -k "manifest or gitignore"
Docs: none

## Touches
- scripts/fabrik_synced_manifest.py — PRIMARY PATH (gitignore_dest_paths)
- templates/scaffold/gitignore-synced-block.txt — only if grounded as hand-maintained

## Behavior Contract
- **Given** the manifest's gitignore groups, **When** the synced block text renders, **Then** it contains `.claude/settings.local.json` (scripts/fabrik_synced_manifest.py:183)

## Context Files
- scripts/sync_enforcement_to_projects.py
- docs/superpowers/specs/2026-08-15-login-once-credentials-design.md
