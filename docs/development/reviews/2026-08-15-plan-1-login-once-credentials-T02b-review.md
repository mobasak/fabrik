# T02b — Fleet gitignore: per-ticket review ledger

## Round 1 (2026-08-15)

Finders: pool deepseek-v3.2-exp×1 + gemini-3-flash×1 + native opus×1 — round 1
Surface: worktree commit 0f7b6401: fabrik_synced_manifest.py (one tail line + comment),
test_synced_manifest.py (+1 test), CHANGELOG.md (delta).

| # | Finding | Source | Disposition |
|---|---|---|---|
| 1 | saas-skeleton/static-site scaffolders OVERWRITE the block-bearing `.gitignore` (template `rglob` copy; `_SAAS_SKIP_FILES` omits it) — live-proven in 3 repos' Initial commits; those types never get this line at scaffold time | opus CONFIRMED | **OUT-OF-SCOPE defect, RECORDED** — `src/fabrik/scaffold.py` is outside this plan's File Scope; surfaced to the operator in the run report as a follow-up fix (skip-vs-merge needs its own small ticket) |
| 2 | Test is a substring check: a wrong-group mutant (carrier into `AGENT_HOOK_FILES` → becomes a SYNCED file, hub copy would overwrite all ~46 carriers) AND an outside-markers mutant both stay green | opus CONFIRMED + gemini | **FIX at acceptance**: assert exactly one occurrence, positioned before `GITIGNORE_BLOCK_END`, and absent from the synced-pairs iteration |
| 3 | The RENDERED group label still reads `# Synced-files lock` under a "DO NOT EDIT (centrally managed)" banner — wrong twice for local state on a fleet surface; `/fabrik-upstream`'s syncedness test reads the block and could classify the carrier as synced-and-enforced | opus PLAUSIBLE | **FIX at acceptance** (in-scope half): relabel the rendered header to name local state, never-synced. The `fabrik-upstream.md` clarification is out of File Scope — recorded as follow-up |
| 4 | The worktree commit fired no governance-sync; fleet stays unignored until a hub-tree trigger commit | opus PLAUSIBLE | REFUTED-BY-MERGE-MECHANICS: the acceptance commit lands in `/opt/fabrik` main tree touching the manifest → sync fires; verified post-merge (see acceptance note) |
| 5 | seo/trade-intelligence/youtube already carry an untracked `settings.local.json` (permissions content); ignoring it makes a future clobber silent | opus PLAUSIBLE (low) | ROUTED to T02a: its `--new-dir` carrier write must MERGE the env keys into an existing file, never overwrite (added to T02a's briefing) |
| 6 | Leading-slash anchoring | both pool | REFUTED: a pattern with a non-trailing `/` is already anchored (git semantics, `check-ignore -v` proven); consistent with the block's style; nested matches are desirable for local state |
| 7 | Duplicate-entry risk when a project carries the line outside the block | gemini | REFUTED: gitignore duplicates are no-ops; `patched_gitignore` proven idempotent over 3 iterations |

Refuted with executed evidence (opus): marker/bar integrity (index 1775 < END 1867, 3×
idempotent), no block-content parser in `scripts/enforcement/`, safety-floor untouched, no
doc-sync row owed, 39 sibling tests green.

Round 1 verdict: code core CORRECT; 2 in-scope fixes land in the acceptance commit (test
hardening + rendered relabel), which per Merge Order follows T01's merge.
