# Docs-truth verification ledger — waves: workflows + reference + traycer/misc (Tier A/B)

**Plan:** `docs/development/plans/2026-07-20-plan-1-docs-truth-convergence.md` Phase E · **Date:** 2026-07-20
**Method:** claim-level verification (native Sonnet verifiers per wave) → verified defect ledgers (scratchpad `e5/e7/e8-*-ledger.md`) → dedicated fixer agents (re-verify each claim against the repo before writing) → my adjudication of fixer reports. FEATURES/DEPLOYMENT (root slice) fixed by its own fixer from the Opus child-verifier findings.

## Coverage & counts

| Wave | Docs | Claims | FALSE | STALE | Fixer disposition |
|---|---|---:|---:|---:|---|
| workflows (11 live) | 11 | ~180 | 22 | 15 | ALL APPLIED + 6 extra defects the fixer's own grounding surfaced (enforcement 49-count, `--use-orchestrator` backwards claim, DEFAULT_EXCLUDES ×2, BUSINESS_MODEL renames ×3, symlink-list 8 paths); 1 unverifiable ledger row honestly left (run_kilo_workflow comment — flagged plausible-not-proven both rounds) |
| reference (15 incl. modules/, EXTERNAL_SYSTEMS) | 15 | ~404 | 11 | 3 | ALL APPLIED; EXTERNAL_SYSTEMS deduped 84→77 unique systems with programmatic sum verification |
| traycer + preplans + zed + development-misc + active spec | 11 | ~95 | 6 | 17 | ALL APPLIED; capability-defects.md regenerated via its own generator (not hand-edited); README retirement banner + targeted fixes (historical narrative preserved) |
| FEATURES + DEPLOYMENT_ARCHITECTURE (root slice) | 2 | 44 | 4 | 17 | ALL APPLIED; 1 honest amendment — `pick_models("translation")` is not a valid task_type, so the doc states the leaderboard-driven pool route instead |
| **Total this ledger** | **39** | **~723** | **43** | **52** | — |

## Headline fixes

- **FINAL_GATE_WORKFLOW** tier tables reconciled to the real gate (T1=17, T2=29, T3=13 checks); the 5 never-invoked scripts (`check_changelog`, `check_index_md`, `check_configuration_md`, `check_openapi_sync`, `check_docs`) marked present-but-dead; semgrep timeout 30s truth.
- **FABRIK_SCAFFOLD_WORKFLOW**: `SPEC_ENABLED_TYPES` 7→10 (chrome-extension + mobile-app DO get specs — verified scaffold.py:4878-4890, contradicting the doc's "excluded by design"); fictional `deploy` command removed; template dirs 19; python-api-gpu everywhere.
- **12 scaffold types** corrected across 5 docs (python-api-gpu was systematically omitted).
- **EXTERNAL_SYSTEMS.md**: 13 duplicate sections removed; totals now sum (77).
- **architecture.md**: SSHDeployer/ServiceDeployer attribution inverted ×3 → fixed; phantom wordpress drivers dropped; provisioner.py removal recorded.
- **modules/templates.md**: file-api is Node 22 :3000 (not Python); static-site routes through the saas-skeleton scaffolder (no own Dockerfile).
- **Kilo/Cascade retirement** propagated: FEATURES review sections rewritten to /fabrik-review + pool; traycer README banner + fabrik-workflow 5 live-framing sites; preplans lifecycle diagram; KILO_AGENT_MANAGEMENT scrape retirement.
- **health-monitoring / technology-stack-decision-guide**: 17-job prometheus truth; agents-fabrik.md:158 pointer.

## Queued for completion report (found here, outside File Scope)

`specs/infrastructure/{authelia,meilisearch}.yaml` float `:latest` against the pinning policy · `run_kilo_workflow.sh` comment (unproven) · pre-existing EXTERNAL_SYSTEMS "Fully Configured: 28" math (not this plan's defect class).

**UNRESOLVED rows: 0** (1 honestly-unverifiable row recorded as such, not silently dropped).
