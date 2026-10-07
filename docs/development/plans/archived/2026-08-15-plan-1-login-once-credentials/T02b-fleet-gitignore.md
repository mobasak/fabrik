# T02b — Fleet gitignore: `.claude/settings.local.json` ignored in every project

## Scope
Add `.claude/settings.local.json` to the **local-state tail** of `gitignore_block_text()`
(`scripts/fabrik_synced_manifest.py:208-210` — the `# Synced-files lock` /
`.fabrik/synced.lock` group: "local state, never committed"), so the rendered block ignores
the carrier file fleet-wide. NOT `gitignore_dest_paths()` (`:147`): that dict is built from
synced-file NAME LISTS (docstring `:163-167`) and renders under a "Fabrik-synced files —
DO NOT EDIT (centrally managed)" header — false for a per-project local file; the
`.fabrik/synced.lock` tail is the exact precedent for the carrier's category. No ignore rule
exists anywhere today (adversary finding B3: without this every project would COMMIT a
hardcoded absolute path). ⚠️ `templates/scaffold/gitignore-synced-block.txt` is **DEAD** —
zero references across src/scripts/templates/tests; both live consumers import
`gitignore_block_text` from the manifest (`src/fabrik/scaffold.py:509-511`,
`scripts/sync_enforcement_to_projects.py:51,139`) — do NOT edit it (deletion is out of scope
for this plan). ⚠️ Sync-consciousness: the manifest edit distributes fleet-wide via the
governance-sync pre-commit; the ignore line is correct for ALL ~46 projects. DO-NOT: no other
manifest changes; no scaffolder logic changes; do not touch the dead template.

Depends: —
Parallel: ⚡
Complexity: native
Gate: .venv/bin/python -m pytest tests/test_synced_manifest.py -q
Docs: none

## Touches
- scripts/fabrik_synced_manifest.py — PRIMARY PATH (local-state tail in gitignore_block_text)

## Behavior Contract
- **Given** the manifest's gitignore groups, **When** the synced block text renders, **Then** it contains `.claude/settings.local.json` (scripts/fabrik_synced_manifest.py:208)

## Context Files
- scripts/sync_enforcement_to_projects.py
- tests/test_synced_manifest.py
- docs/superpowers/specs/2026-08-15-login-once-credentials-design.md
