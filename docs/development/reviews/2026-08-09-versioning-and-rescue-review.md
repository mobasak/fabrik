# Review round — versioning adoption + pipeline rescue (2026-08-09)

Surface: `9cb3b8c1` (stranded-batch rescue) · `66e0c9da` (daily_refresh stage list) · `504ff900`
(CHANGELOG) · `e2f24eef` (release_cut + /fabrik-release wiring) · `6cf54b8f` (gh-nonfatal self-catch) ·
this round's fixes. Native finder seat (probes in scratchpad repos + fleet-changelog forensics) +
orchestrator adjudication (NO-POOL: enforcement-adjacent scripts + command sources).

## Coverage Checklist

| class | verdict |
|---|---|
| release_cut correctness | FIXED(4): first-cut corruption on template-shaped changelogs (body/tail boundary unified at any-H2 — probed against real fleet changelogs; the flagship path now clean) · case-sensitive BREAKING marker · trailers in one parseable block (`%(trailers:key=Agent-Role)` verified) · `--version` override for artifact-versioned surfaces. Probed-clean: tag ordering v0.10>v0.9, non-semver tags ignored, multi-section splice, no sibling-file bundling (pathspec commit), empty-refusal, gh auth-failure branch |
| /fabrik-release wiring | FIXED(3): Version-cut section de-spliced from inside `## Output` · frontmatter "no agent publishes" reconciled with the sanctioned cut · `VERSION:` tag-only grammar arm + per-surface reconciliation step (extension/mobile pass the artifact version) · Aug-4 compaction sentence's mid-sentence splice repaired (adjacent) |
| Pipeline-rescue attribution truth | CORRECTED: the shared 15:45:44 mtime was the pre-commit stash artifact of a sibling's 15:45:34 commit — not a regeneration pass (refresh ran 10:15); 3 of 16 files were format-sweep residue, not pipeline outputs; the "15:45 mystery" follow-up withdrawn. Content verdict UPHELD: every diff was regenerated content or tool-canonical churn — no agent's authored work was bundled (finder reproduced the ruff-format byte-exactness) |
| Cron staging safety | FIXED(1): `LOCAL_LLM_INFRASTRUCTURE.md` un-staged — MIXED file (hand prose above the auto-block); a cron `git add` stages the whole file = automated bundling. `embedding_models_dump.json` verified single-writer, stays |
| Sync/manifest | CLEAN post-fix: the corrupting first-cut path no longer rides CORE_SCRIPTS to the very repos shaped to trigger it; gh-missing degrades gracefully project-side (verified on current tree) |

## Documented residuals (low, accepted)

- Entries stranded ABOVE `## [Unreleased]` are ignored, never graduated.
- `### Removed`/`Deprecated` map to patch (design choice, documented as built).
- Push-with-no-upstream exits loud after the tag exists (partial state, visible).
- Hardcoded `Co-Authored-By` model name in the cut commit.

## Round ledger

- Round 1 (finder): found: 9 (4 release_cut, 3 wiring, 2 rescue/staging) — plus the mid-review
  self-catch (gh-nonfatal, `6cf54b8f`) it independently verified done.
- Round 2 (fixes): fixed: 8 · corrected-record: 1 (attribution truth — history immutable, ledger
  corrected in CHANGELOG + here).
- Round 3 (confirming, fresh): release_cut suite 11 green (4 new, each seen red) · corpus `--check`
  OK · daily_refresh `bash -n` OK · fresh full gate below: **found: 0 · fixed: 0** — quiet.

## Gate (verbatim, this round)

```
$ python scripts/final_gate.py --check --json
{"status": "success", "tier": 2, "passed": 45, "failed": 0}
```

reviewed — sign-off.
