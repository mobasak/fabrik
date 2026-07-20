# Docs-Truth Convergence — purge, relocate, verify, enforce

**Status: IN-PROGRESS** (execution started 2026-07-20 from baseline bfffd769; converged 2026-07-20 via /fabrik-plan-review, 4 invocations, md5-verified no-op rounds)
**Created:** 2026-07-20 · **Source:** operator-approved brainstorm (this chat) + 9 read-only audit agents (5 placement + 4 convergence/adversarial passes, 2026-07-19→20)
**Goal:** every live doc in `/opt/fabrik` is verified-true (claim-level), correctly placed, truthfully named within approved scope, and fully indexed — enforced by new gates so it stays true — as the prerequisite for converging the `docs/orchestrator/` command chains.

## What we already agreed (operator decisions — quoted where theirs)

- Macro goal: *"make command files under orchestrator fully uptodate now. to get there, we first need make all docs fully uptodate and reflect what we have."*
- *"one more deep pass i dont want any residue left"* — convergence bar is a no-op pass, not a fix list.
- Verification depth: **"Full claim-level everywhere"** — every falsifiable claim in all ~190 live docs verified with evidence (the 11-runbook/~300-claim method, repo-wide).
- Structural renames: **"None — defer all renames"** — kilo/→agents/, MD/→prompting/, windsurf/ dissolution, superpowers→development/specs merge are ALL OUT of this plan (recorded as deliberately-deferred residuals, not open questions).
- Relocations: **"All moves + subfoldering"** — the 5 cross-folder moves + the `orchestrator.md → deployment-orchestrator.md` collision rename-in-place + reference/ root subfoldering into `apis/` + `modules/` are IN.
- Dormant items: **"any dormant item. but we must be sure it is really dormant."** — archive requires a recorded dormancy proof (§ Phase A protocol); an item failing proof is marked PARKED, never silently archived.
- Approach B approved: structure first (purge → dismantle → moves → indexes), verification fleet behind it on the stable tree, gates land once the tree passes them, whole-tree no-op pass last.
- Execution model: pool subagents (`fanout`, flywheel-recorded) for gradeable breadth + native Claude subagents for authority/decide — both, never either.
- Cascade zombie dismantle approved as one atomic change (operator saw the daily_refresh breakage analysis).
- No commit/push restrictions: plan executes via `/fabrik-execute-plan` (plan IS the approval; per-phase commits with provenance trailers).

## Global Constraints (every phase inherits; copied verbatim from binding sources)

- **Shared master, sibling AIs live in the tree**: stage explicit paths only; `git commit -- <paths>` (never the index); `git diff --cached --name-only` before every commit; never touch `docs/development/plans/2026-07-19-plan-1-task-subagent-scoring-benchmark.md` (untracked sibling WIP), the staged `docs/reference/kilo/TASK_SUBAGENT_SELECTION.md` (sibling MM), or `docs/superpowers/specs/2026-07-19-task-subagent-scoring-benchmark-design.md`.
- **Moves are `git mv` only** — the sprawl gate allows index-tracked paths (`check_doc_sprawl.py:115-118` uses `git ls-files --error-unmatch`, an index lookup; `:184-185` allows tracked); brand-new .md files only at allowlisted paths (`docs/archive/**`, `docs/development/reviews/*-review.md`, `docs/README.md` scaffold row).
- **Never edit fleet-synced files in a project; hub-side edits are the canonical path** — this plan edits hub copies only; sync propagates. Synced set: `scripts/fabrik_synced_manifest.py`.
- **Archived files' internal links are exempt** from link-integrity fixes (history stays as written). Live-tree links must resolve.
- **No history rewrite, no deletions of operator research** — archive means `git mv` into `docs/archive/`, content byte-identical.
- **12-Factor for the new enforcement scripts**: stdout-only output (XI), stdlib-only (II — no new deps; deps files untouched), no daemons/PID (VIII), granular env/config (III).
- **New enforcement script conventions** (`.windsurf/rules/core/40-documentation.md` § matrix row "New enforcement script"): registered in `final_gate.py` at the correct tier; `# AFTER-EDIT:` header in first ~25 lines; dual-path import of `CheckResult`/`Severity` from `validate_conventions` (pattern: `check_doc_sprawl.py:24-28`).
- **CHANGELOG**: one `## [Unreleased]` entry `### Changed — Docs-truth convergence: purge, relocate, verify, enforce (2026-07-20)`; each phase appends its bullet(s) to THIS entry (never resets the section; append atop, respect sibling entries).
- **Provenance trailers** on every commit (`Agent-Role`/`Agent-Phase`/`Agent-Context`, orchestrator/subagent/review-fix as applicable).
- **Serialization points (a sibling benchmark AI is live in the kilo-benchmarks tree — verified uncommitted WIP 2026-07-20):** `scripts/kilo-benchmarks/daily_refresh.sh`, `docs/reference/kilo/**`, and **`docs/reference/LOCAL_LLM_INFRASTRUCTURE.md`** (the sibling has it modified-uncommitted AND `kilo_agents_db.py` regenerates its auto-blocks daily) may overlap the sibling's scope. Executor protocol per file: at each phase that touches one, FIRST `git status --short -- <file>` — if a sibling has it modified-uncommitted, that phase **waits** (BLOCKED per the lock protocol) rather than editing over live WIP; my Phase-A touch of LOCAL_LLM_INFRASTRUCTURE.md is only two hand-section link fixups (`:760,:762`, outside the `AUTO-GENERATED` blocks) — apply them only once the file is sibling-clean. `libs/subagents/select.py` (sibling also editing) is USED (`fanout`) not owned — no write collision. All other phases are disjoint and proceed.

## Context Ledger

| Source | What binds | Grounded ref |
|---|---|---|
| `core/40-documentation.md` (ACTIVE) | Doc Sync Matrix; enforcement-script registration; docs/README.md is canonical universal doc; INDEX auto-gen tree via `docs_updater.py` | pack §A/§Matrix (read 2026-07-20) |
| `core/10-python.md` (ACTIVE) | typing/env-handling for the 3 new + 1 edited enforcement scripts | pack header |
| `core/45-testing-strategy.md` (ACTIVE) | test-per-behavior for gate scripts; risk-ordered, TDD for the sprawl-gate fix | pack header |
| `core/62-using-subagents.md` (ACTIVE) | pool-default fan-out (`fanout` → `set_quality`), read-only = parallel; native for authority/decide | pack §Dispatch/§Parallelism |
| `core/55-observability.md` (ACTIVE) | scripts print structured results to stdout, no logfiles | pack header |
| fabrik-lib consult | **No module vendored** — the work is docs governance + stdlib enforcement scripts; `libs/subagents` (already vendored under `scripts/kilo-benchmarks/libs/`) is USED for fan-out, not vendored anew. No new-module candidate (checks are fabrik-hub-specific, fail (a) generic + (b) ≥2 types). | `/opt/fabrik-lib/README.md` module table (checked; nothing covers doc-link/index gating) |
| `agents-fabrik.md` invariants | canonical map rows this plan edits: `:479` (Cascade row), `:483-486` (kilo guide links) | agents-fabrik.md:479,483-486 |
| `specs/services/*.yaml shape:` | **untouched** — no service code changes; no shape flag flips | n/a |
| Sync manifest | `docs/reference/kilo` dir synced (`fabrik_synced_manifest.py:73`); `cascade-models.md` (`:108`); kilo scripts (`:29-30`) | verified 2026-07-20 (grep output in §Evidence) |
| Sprawl gate mechanics | `git mv` passes; staged-add bypass exists (index-based `is_tracked`) | check_doc_sprawl.py:115-118,184-185 + scratch-repo test (§Evidence) |
| `docs/operations/fabrik-lifecycle.md` | not applicable — no deploy/compose/secret steps in this plan | n/a |

## File Scope (owned paths)

Creates: `scripts/enforcement/check_doc_links.py` · `scripts/enforcement/check_doc_index.py` · `scripts/enforcement/check_retired_terms.py` · `tests/enforcement/test_check_doc_links.py` · `tests/enforcement/test_check_doc_index.py` · `tests/enforcement/test_check_retired_terms.py` · `tests/enforcement/test_check_doc_sprawl_newfile.py` · `docs/README.md` · `docs/development/reviews/docs-truth-*-review.md` (one ledger per folder wave) · `docs/archive/**` (mv destinations only).

Modifies: `scripts/enforcement/check_doc_sprawl.py` · `scripts/final_gate.py` (register 3 checks) · `scripts/kilo-benchmarks/daily_refresh.sh` (⚠ serialization point) · `scripts/kilo-benchmarks/update_kilo_benchmarks.py` (`:11` docstring) · `scripts/sync_enforcement_to_projects.py` (orphan list + `:11,:558` stale text) · `scripts/watch_enforcement_changes.sh` · `scripts/docs_updater.py` (comments dict prune + `:40` docstring) · `scripts/kilo_docs_enforcer.py` (`:37` docstring) · `scripts/kilo-benchmarks/audit_pipeline.py` (docstring paths only) · `scripts/fabrik_synced_manifest.py` (remove `:108` cascade row) · `src/fabrik/scaffold.py` (remove KILO_AGENT_NAMING seed/refresh blocks + `:1103-1108` cascade copy block) · `tests/test_scaffold_fix.py` (matching assertions) · `templates/scaffold/gitignore-synced-block.txt` (`:21` cascade line) · `.pre-commit-config.yaml` (`:48` pattern entries) · `INDEX.md` · `CHANGELOG.md` · `agents-fabrik.md` · `docs/**` (the enumerated mv/edit set per phase — full mapping in Phase C table + Phase A/B lists) · `.windsurf/rules/ai/00-ai-model-selection.md` · `.windsurf/rules/saas/60-saas-ui.md` · `.windsurf/rules/core/12-node.md` · `.windsurf/rules/core/67-file-api.md` · `.windsurf/rules/desktop-app/72-desktop.md` · `.windsurf/rules/chrome-ext/70-chrome-ext.md` (dead-link retargets) · `.fabrik/plan-locks/{2026-07-09-plan-3-pool-dispatch-map,2026-07-12-plan-2-fabrik-capability-catalog,2026-07-18-plan-1-external-services-registry,2026-07-19-plan-1-coding-benchmark-livecodebench-direct}.json` (plan-path field only) · `docs/LESSONS_LEARNT.md`.

Retires (mv within repo): `scripts/kilo-benchmarks/scrape_windsurf_models.py` → `scripts/.archive/` · `docs/zed/check_zed_extensions.py` → `scripts/check_zed_extensions.py`.

Explicitly NOT owned: `docs/development/plans/2026-07-19-plan-1-*` (sibling) · `docs/reference/kilo/TASK_SUBAGENT_SELECTION.md`, `CODING_SUBAGENT_SELECTION.md` + all daily-regenerated selection files (writers keep them) · **`docs/reference/LOCAL_LLM_INFRASTRUCTURE.md` (OPERATOR-EXCLUDED 2026-07-20 — live sibling WIP; its two link fixups `:760,:762` are a deferred follow-up applied when the file is sibling-clean; Phase F's `check_doc_links.py` carries a temporary per-file waiver for it, removed with the follow-up)** · `/opt/fabrik-lib/**` (cross-repo HARD STOP — report-only handoff) · the 4 sync-pinned reference docs (convergence-prompts, long-command-monitoring, technology-stack-decision-guide, mobile-responsive-testing-guide — paths frozen).

---

## Phase A — Purge, archive-with-proof, and known-stale hotfixes — ✅ EXECUTED 2026-07-20 (see commit; 58 archives + 2 deletions with A0 receipts; gate CLEAN with 2 sanctioned exclusions: operator-excluded LOCAL_LLM, sibling live claude-p spec)

**Interfaces — Consumes:** current tree. **Produces:** archived set under `docs/archive/`; the CHANGELOG entry; hotfixed `EVALUATION_CHECKLIST_FOR_EPIC_COMMANDS.md` + `mega-epic-breakdown/00-trigger-mega-epic-fabrik.md`; dormancy receipts. Later phases rely on: archived files are at `docs/archive/<basename>` (flat), and the two checklist files contain zero retired-triad language.

**A0 — Dormancy-proof protocol (self-service; run per candidate BEFORE its mv).** A candidate archives only if ALL four checks pass; record the four outputs in the phase ledger + commit body:
1. `git log -1 --format=%cs -- <file>` ≥ 21 days old, OR proven-unexecuted (a named deliverable file does not exist — command template: `test ! -f <deliverable>`; wavespeed: `test ! -f scripts/kilo-benchmarks/add_via_wavespeed_column.py && test ! -f scripts/kilo-benchmarks/scrape_wavespeed_catalog.py`).
2. `grep -rn "$(basename <file>)" --include='*.md' --include='*.py' --include='*.sh' docs scripts src INDEX.md CLAUDE.md agents-fabrik.md | grep -v docs/archive | grep -v CHANGELOG` → only index rows or the enumerated fixup links.
3. `grep -rln "$(basename <file> .md)" docs/development/plans/*.md docs/superpowers/specs/*.md` (active dirs only) → no live successor names it as a dependency.
4. `grep -l "<plan-id>" .fabrik/plan-locks/*.json | xargs grep -h '"status"'` → `released`/`complete` (or no lock).
Any check fails → do NOT archive; instead insert as line 2 of the file: `> PARKED (operator-confirmed 2026-07-20): <which check failed — why it stays>` and list it in the completion report.

**A1 — Archive set (each = `git mv <src> docs/archive/<basename>` + its enumerated link fixups in the same commit):**
- `docs/reference/stack.md` → fixups: `INDEX.md:444` row → archive note; ~~`LOCAL_LLM_INFRASTRUCTURE.md:762`~~ **DEFERRED (operator-excluded file — see File Scope)**.
- Workflows (6): `KILO_REVIEW_WORKFLOW.md` (fixup `docs/workflows/FINAL_GATE_WORKFLOW.md:975`), `KILO_DISPATCH_WORKFLOW.md`, `KILO_CLI_OUTPUT_WORKFLOW.md`, `DOCUMENTATOR_WORKFLOW.md` (fixups: `FINAL_GATE_WORKFLOW.md:977`; update the docstring pointers `scripts/docs_updater.py:40` + `scripts/kilo_docs_enforcer.py:37` to the archived path or drop the doc mention — both are fleet-synced scripts, hub edit is the canonical path; archive banner MUST state "the subject script `docs_updater.py` is LIVE"), `DEV_TRACKER_WORKFLOW.md` (fixup `HEALTH_CHECKER_WORKFLOW.md:189`), `windsurf-triggered-workflows.md`. INDEX rows `:407,:414,:415,:420,:619` updated.
- Traycer (10): `epic-kilo-integration.md`, `mcp-kilo-setup-guide.md`, `QUICKSTART-MCP-KILO.md`, `TRAYCER-KILO-AGENTS-GUIDE.md`, `TRAYCER-KILO-DIRECT-CLI.md`, `traycer-free-tier-agents-testing.md`, `AGENT-TIMEOUT-POLICY.md`, `traycer-yolo-workflow.md`, `TEMPLATE_MAPPING.md` (fixup `docs/traycer/README.md:503`), `traycer-evaluation.md`.
- Reference/kilo prose guides (10): `README.md`, `KILO_CLI_REFERENCE.md`, `KILO_USAGE_GUIDE.md`, `KILO_MODEL_SELECTION.md` (fixup ~~`LOCAL_LLM_INFRASTRUCTURE.md:760`~~ **DEFERRED — operator-excluded file, see File Scope**), `KILO_PERFORMANCE_TUNING.md`, `KILO_TROUBLESHOOTING.md`, `KILO_UPDATE_SCHEDULE.md`, `KILO_REVIEW_GUIDE.md`, `KILO_USE_CASES.md` (fixup `docs/orchestrator/epic-to-ticket-workflow/05-ticket-outline-fabrik.md:90`, which also cites KILO_CLI_REFERENCE), `KILO_AGENT_NAMING.md` — **bundle**: remove `src/fabrik/scaffold.py:1111-1115` (seed) + `:6025-6031` (refresh), the guarded assertions in `tests/test_scaffold_fix.py:171-174,208-209`, and the `.pre-commit-config.yaml:48` pattern entry for it; fixups `agents-fabrik.md:483,485,486` + `docs/traycer/fabrik-workflow.md` (KILO_AGENT_NAMING link). Archive destination `docs/archive/kilo-cli/` (subdir, to avoid basename collisions with existing archive files — `docs/archive/**` any depth is allowlisted, `check_doc_sprawl.py:69-72`). Orphan pruning then removes them from projects automatically (`sync_enforcement_to_projects.py:535-556` — by design, verified).
- Dormant work (A0-gated): `docs/development/plans/2026-07-12-plan-1-wavespeed-integration.md` + `docs/superpowers/specs/2026-07-12-wavespeed-integration-design.md`; `docs/development/plans/2026-06-23-transdoc-converged.md`; `docs/development/plans/2026-07-06-plan-1-universal-watchdog.md` (A0 check 3 MUST grep `docs/development/plans/2026-06-29-plan-watchdog-deploy-side.md` + Tier-D notes — if named as the intended vehicle, PARK, don't archive); `docs/FAQ.md` (**pre-step**: read `scripts/enforcement/check_structure.py` `REQUIRED`-vs-allowlist semantics for `FAQ.md:118` — if presence is REQUIRED for the hub, replace content with a 10-line truthful stub instead of archiving; else archive); the ~18 shipped-work specs in `docs/superpowers/specs/` (enumerated in the 2026-07-20 audit: best-model-suggester, subagent-runs-telemetry, subagent-tool-parity, watchdog-governance-mount, behavior-contract-test-generation, mobile-app-factory, subagent-usage-enforcement, pool-dispatch-map (on-disk filename: `2026-07-09-pool-dispatch-map-and-enhancements-design.md` — archive by THIS name, not the short slug), coding-microbench-runner, coding-microbench-completions-shim, doc-registry-reconciliation, modelscope-new-row-ingest, chrome-ext-wxt-scaffold, converging-doc-maintenance, fabrik-capability-catalog, terminal-bench-runner, external-services-registry, fabrik-factory-architecture, coding-benchmark-livecodebench-direct) → `docs/superpowers/specs/archived/` (precedent: empire-operating-model); `2026-05-28-mobile-deployment-design.md` (superseded by shipped mobile-app-factory); `2026-07-15-subagent-scoring-lanes-benchlm-gui-design.md` (A0 check 1 via `scrape_benchlm.py` existence + check 3 vs the 07-19 benchmark spec); `docs/superpowers/plans/2026-07-16-traycer-fabrik-twins-plan.md` + its spec (Phases 0/A/B/C ✅ with SHAs; D self-declares a future separate cycle).
- Non-md residue: `git rm docs/LESSONS_LEARNT.md.bak.2026-05-12_1650` (a tracked backup dropping — delete, not archive; content is in git history) · `git rm docs/development/plans/archived/fitness-plan.jsx` (zero references) · `git mv docs/infrastructure/vps-captured-state-20260520.txt docs/archive/` (fixup `docs/infrastructure/vps-bootstrap-plan.md:118-120` path) · `git mv docs/reference/coolify-openapi.json docs/reference/coolify-services-compose-dump.txt → docs/archive/`.

**A2 — Known-stale hotfixes (targeted, before the fleet — these are runtime-injected):**
- `docs/orchestrator/epic-to-ticket-workflow/EVALUATION_CHECKLIST_FOR_EPIC_COMMANDS.md:88-94,163` — rewrite the retired-triad supplier language to the current reality (Claude Code Max OAuth agents + the OpenRouter pool; `review_rubric.py:79-83` injects this file — highest blast radius in the plan).
- `docs/orchestrator/mega-epic-breakdown/00-trigger-mega-epic-fabrik.md` lifecycle bullet 2 ("Claude Code, Windsurf Cascade, Kilo CLI") — same rewrite.
- `docs/reference/fabrik-vultr.md`: excise `:64-98` (drill retrospectives → `docs/archive/fabrik-vultr-drill-retros.md`, new file allowlisted under archive) and change the `:5` "ground truth" label to "historical plan (archived)".
- 4 plan-lock JSONs: update `"plan":` to the `plans/archived/` path (cosmetic drift, audit-listed).

**Validation gate (Phase A):**
```bash
# no live references to ANY archived file outside docs/archive + CHANGELOG (expect: no output).
# Search term per file: the basename — EXCEPT generic basenames (README.md), which use their
# path-qualified form (kilo/README.md) or every live README would false-hit.
for old in $(git diff --cached --name-status | awk '$1 ~ /^R/ {print $2}'); do
  case "$(basename "$old")" in README.md) pat="kilo/README.md";; *) pat="$(basename "$old")";; esac
  grep -rn "$pat" --include='*.md' docs CLAUDE.md agents-fabrik.md INDEX.md | grep -v '^docs/archive' | grep -v CHANGELOG | grep -v 'archived'
done
python -c "import ast; ast.parse(open('src/fabrik/scaffold.py').read())"   # expect: silence
python -m pytest tests/test_scaffold_fix.py -q                              # expect: pass
grep -c "Kilo CLI" docs/orchestrator/epic-to-ticket-workflow/EVALUATION_CHECKLIST_FOR_EPIC_COMMANDS.md  # expect: 0 (or only inside an explicit 'retired' sentence — manual read)
```
Then: `python scripts/enforcement/check_doc_sync.py` (resolve in-phase WARNs) → stage code, run `python scripts/doc_reconcile.py` on the staged diff, review+add its patches → commit Phase A (explicit paths, trailers) → **run the full `/fabrik-review` methodology on Phase A's changed surface (pool finders via `fanout("review", …, mode="read_only")` + ≥1 native fabrik-reviewer on Opus), refute → prove-before-fix, loop to a `found: 0, fixed: 0` no-op pass** → re-run gate → mark phase ✅ in this file, stage it in the phase commit.

## Phase B — Cascade zombie dismantle (one atomic commit)

**Interfaces — Consumes:** Phase A's tree. **Produces:** `daily_refresh.sh` with no cascade path in the `git add` block (`:527-541`); `scrape_windsurf_models.py` retired; manifest without `:108`; the orphan-prune entry so project copies of `cascade-models.md` are deleted on next sync. Later phases rely on: `docs/reference/windsurf/` contains only IDE/extension docs + `overview.md`.

Steps (single commit — verified breakage analysis: a missing path in the atomic `git add --` list at `daily_refresh.sh:529-540` exits 128 and stages NOTHING, masked by `|| true`):
1. Remove the scrape invocation (`daily_refresh.sh:228-229` — the `_step "scrape_windsurf_models"` call, re-read 2026-07-20) AND the `docs/reference/windsurf/cascade-models.md` line from the `git add` block AND the two stale comments `daily_refresh.sh:217,:443`.
1b. Remove the scaffold copy block `src/fabrik/scaffold.py:1103-1108` ("Copy cascade-models.md (Windsurf AI model reference)" — `shutil.copy` into every scaffolded project; re-read 2026-07-20). No test edit needed: `grep -n cascade tests/test_scaffold_fix.py` → zero hits (verified).
2. `git mv scripts/kilo-benchmarks/scrape_windsurf_models.py scripts/.archive/` ; fix the docstring mention `update_kilo_benchmarks.py:11`.
3. Remove `fabrik_synced_manifest.py:108` (cascade-models row); add `docs/reference/windsurf/cascade-models.md` to the stale-orphan list in `sync_enforcement_to_projects.py` (~`:643-651`, re-read 2026-07-20) so project copies are pruned; clean that file's own stale mentions (`:11` docstring, `:558` comment); remove `templates/scaffold/gitignore-synced-block.txt:21` (the cascade-models line — else every scaffold keeps emitting a stale synced-file entry).
4. Remove `watch_enforcement_changes.sh:69` watch line; remove the `.pre-commit-config.yaml:48` pattern for it.
5. TWO explicit archives: `git mv docs/reference/windsurf/cascade-models.md docs/archive/` AND `git mv docs/reference/windsurf/cascade-guide.md docs/archive/` (cascade-guide.md is a separate live May-2026 Cascade guide — retired content; its `:289` link to cascade-models becomes archive-internal, exempt). Fixups: `agents-fabrik.md:479` row; `docs/reference/windsurf/overview.md` contents table; `docs/reference/windsurf/windsurf_features.md:288` link; INDEX `:358`; doc mentions `docs/workflows/SYNC_ENFORCEMENT_WORKFLOW.md:54`, `docs/workflows/DATA_SYNC_WORKFLOW.md:127`, `docs/workflows/SCAFFOLD_STRUCTURE.md:73,:162`, `docs/traycer/fabrik-workflow.md:537,:585`.

**Behavior Contract (risk-ordered):** (1) the nightly staging block only lists existing paths — test extracts only path-like tokens (the raw sed range would sweep in `git`/`--`/`2>/dev/null` words): `sed -n '/git add -- /,/|| true/p' scripts/kilo-benchmarks/daily_refresh.sh | grep -oE '(docs|\.windsurf|scripts|capabilities)[^ \\]*' | while read -r p; do compgen -G "$p" >/dev/null || echo "MISSING $p"; done` → expect no output; (2) `bash -n scripts/kilo-benchmarks/daily_refresh.sh` → clean; (3) sync run leaves no error: `python scripts/sync_enforcement_to_projects.py --dry-run 2>&1 | grep -i cascade` → shows prune, no exception. (Trivia skipped: no unit tests for a deleted scraper.)

**Validation gate:** the three commands above + `grep -rn "cascade-models" scripts/ src/ docs --include='*' | grep -v archive` → expect empty. Close with the standard sequence: check_doc_sync → doc_reconcile on staged diff → commit → **full `/fabrik-review` on the phase surface, looped to no-op** → gate green → mark phase ✅ + stage plan file.

## Phase C — Relocations, merges, subfoldering

**Interfaces — Consumes:** Phase A/B tree. **Produces (the path contract every later phase + the fleet cites):**

| Old path | New path |
|---|---|
| docs/EXTERNAL_SYSTEMS.md | docs/reference/apis/EXTERNAL_SYSTEMS.md |
| docs/reference/{glitchtip-api,openrouter-api,modal-api,runpod-api,runpod-hf-models,vast-api}.md | docs/reference/apis/<same>.md |
| docs/reference/{ai,drivers,templates}.md | docs/reference/modules/<same>.md |
| docs/reference/orchestrator.md | docs/reference/modules/deployment-orchestrator.md |
| docs/reference/template_renderer.md | MERGED into docs/reference/modules/templates.md (port the 3-method table; delete file; replace the `templates.md:192` renderer-internals link with the merged section — never leave a link to the deleted file) |
| docs/reference/trueforge-images.md | MERGED into docs/reference/prebuilt-app-containers.md §4 (port: never-trust-static-count rule, check-arch arm64-fix note, 12-row shortlist; delete file) |
| docs/infrastructure/traycer-command-wiring.md | docs/orchestrator/traycer-command-wiring.md |
| docs/infrastructure/WSL2-DNS-FIX.md | docs/workstation/WSL2-DNS-FIX.md |
| docs/operations/MCP_HTTP_TRANSPORT.md | docs/workstation/MCP_HTTP_TRANSPORT.md |
| docs/zed/check_zed_extensions.py | scripts/check_zed_extensions.py |

**After each mv, re-resolve the moved file's OWN relative links** (a file moved between folders breaks its own `](../x)` targets — e.g. traycer-command-wiring.md's outbound links re-based from infrastructure/ to orchestrator/). Citer updates (enumerated by the audits; each executes with its mv): glitchtip driver+test+probe comments (`src/fabrik/drivers/glitchtip.py:4,28,246,295`, `tests/drivers/test_glitchtip.py:427`, `scripts/probes/glitchtip_probe.sh:19`), `src/fabrik/cli.py:3261`, `src/fabrik/drivers/runpod.py:276`, `src/fabrik/drivers/vast_provider.py:229,398`, `scripts/kilo-benchmarks/libs/subagents/_transport.py:14`, `tools.py:354` (comment refs to openrouter-api.md), `docs/operations/gpu-rent.md:7,8,62,370,371`, the ~9 deployment-orchestrator inbound links (`QUICKSTART:183`, `fabrik-cli-reference:494`, `architecture:342`, `templates:189→self`, `drivers:282`, `FABRIK_SCAFFOLD_WORKFLOW:1190`, `health-monitoring:4`, `INDEX:337`, `template_renderer` link dies with the merge), cross-links among the moved api docs, `INDEX.md` rows `:263,:309-354`, `vps-bootstrap-plan`/`docs_updater` basename rows survive for MOVED files (basename-keyed, verified) — but NOT for the two MERGED-and-deleted files: prune `docs_updater.py:743` (`"trueforge-images.md"`) in this phase (template_renderer.md has no docs_updater row — verified). `scaffold.py:1131` (prebuilt copy) and `:1124` (tech-guide copy) paths unchanged — both files stay at reference/ root.

**Behavior Contract:** docs-only phase — no code behavior added; the contract is the two mechanical asserts in the gate (old-path zero-refs; scaffold import intact). Code-comment edits (driver files) are comment-only: `python -c "import fabrik.cli"` must still pass.

**Validation gate:**
```bash
for p in "docs/EXTERNAL_SYSTEMS.md" "docs/reference/orchestrator.md" "docs/reference/template_renderer.md" "docs/reference/trueforge-images.md" "reference/glitchtip-api.md" "infrastructure/WSL2-DNS-FIX"; do \
  grep -rn "$p" --include='*.md' --include='*.py' --include='*.sh' docs src scripts tests INDEX.md CLAUDE.md agents-fabrik.md | grep -v docs/archive | grep -v CHANGELOG; done   # expect: empty
python -c "import fabrik.cli"   # expect: silence
python scripts/enforcement/check_doc_sprawl.py 2>/dev/null; echo $?        # via final_gate lean run below
python scripts/final_gate.py --lean --check --json                          # expect "status":"success"
```
Close with the standard sequence (check_doc_sync → doc_reconcile → commit → **full `/fabrik-review` looped to no-op** → gate → ✅ + plan staged).

## Phase D — Index layer + hub-pack dead-link retargets

**Interfaces — Consumes:** final paths from Phase C's table. **Produces:** `docs/README.md` (the tree charter: one paragraph per folder, its role, what belongs/doesn't); INDEX.md drift-free (the contract Phase F's `check_doc_index.py` enforces); pruned `docs_updater.py` comments dict; retargeted rule packs.

Steps:
1. Create `docs/README.md` (allowlisted scaffold row) — folder charters incl. reference/'s subfolder semantics (apis/ modules/ research/ service-contracts/ fixtures/ kilo/ MD/ windsurf/ — the deferred renames keep truthful *descriptions* even where names are legacy).
2. INDEX.md: fix the 20 dead refs (audit list: `:120,:482,:483,:499,:500,:538,:545,:546,:579,:593,:599-601,:731-735,:757` — the `:731-735` test paths corrected to `scripts/kilo-benchmarks/tests/`; `:757` DB path corrected); `:716`: the INDEX archive paths are CORRECT (re-verified 2026-07-20) — the falsehood is that `audit_pipeline.py`'s docstrings point at nonexistent `docs/development/audits/` (step 4 fixes the script) — after step 4, reword `:716` so prose and script agree; add the `docs/orchestrator/` tree (44 files); add rows for every unindexed live doc — **generate the list mechanically, don't rely on the audit artifact**: `comm -23 <(git ls-files 'docs/**/*.md' | grep -vE '^docs/(archive|development/(plans|epics|reviews)|superpowers)/' | sort) <(grep -oE 'docs/[A-Za-z0-9_./-]+\.md' INDEX.md | sort -u)` → add a row (grouped rows acceptable for uniform sets: audit-prompts/01-08, infrastructure/archive as one line each); refresh manifest line-number citations (`:718,:721,:725` say manifest:69 → 73).
3. `scripts/docs_updater.py` comments dict (`:705`): delete the 25 dead entries; move the 11 archive-only entries' descriptions to nothing (delete — archive needs no live descriptions); add entries for moved paths' new basenames where missing (modal-api, openrouter-api etc. per audit's missing-rows list).
4. `scripts/kilo-benchmarks/audit_pipeline.py:19,448` docstrings: `docs/development/audits/` → `docs/archive/audits/` (match reality).
5. Hub-pack dead links — ONLY these two survive (the four research-files→research retargets were already done by commit 4951789e; re-verified 2026-07-20 that `core/12-node.md:16`, `core/67-file-api.md:17`, `desktop-app/72-desktop.md:17`, `chrome-ext/70` already resolve to `docs/reference/research/` — do NOT touch them): (a) `.windsurf/rules/ai/00-ai-model-selection.md:14` — `AI_TAXONOMY.md` does not exist, so this is a **false prose claim** ("now a redirect stub") to CORRECT, not a link to retarget (there is no successor to point at); (b) `saas/60-saas-ui.md:296` — `docs/reference/multilingual-plan.md` is dead; the real file is `templates/scaffold/i18n-kit/docs/multilingual-plan.md` — retarget there or drop the ref.
6. Real broken links in live docs (audit list): `docs/development/capability-defects.md:8-9` (rn-*-kit rows → point at fabrik-lib paths or mark cross-repo), superpowers specs' plan-pointers → `plans/archived/` paths, `fabrik-cli-reference.md:55,335` (preplan refs — both are illustrative CLI-usage strings, not markdown links (re-verified 2026-07-20): annotate as examples or point at `docs/preplans/README.md`, don't invent targets), `runpod-api.md:277` (archived plan path), `research/Node Backend Practices Research 2026.md:122-123` (pack names → `core/12-node.md`/`core/25-data-postgres.md` actual names), `FABRIK_SCAFFOLD_WORKFLOW.md:402-423` template-doc paths (verify against `templates/scaffold/` reality, retarget), `DATA_SYNC_WORKFLOW.md:135,193`, `vps-complete-inventory.md:780`, `vps-ai-sysadmin.md:351` (space-name research file — verify exact filename), `KILO_BENCHMARK_WORKFLOW.md:89`, `agents-fabrik.md:405` (`docs/preplan.md`), `docs/development/epics/2026-07-14-epic-1*` refs (`:138,:159,:192,:237` — verify each target, fix or annotate), `mega-epic-breakdown/00-trigger:3` + orchestrator files' `docs/traycer/mega-epic-breakdown/` refs, `glitchtip-sdk-integration-setup.md:46`. `scripts/validate_i18n.py` (×5 in orchestrator docs): RESOLVED 2026-07-20 — it exists at `templates/scaffold/i18n-kit/scripts/validate_i18n.py` (a project-side scaffold script, not repo-root `scripts/`); annotate the 5 refs "(project-side scaffold script)", do NOT remove them. `docs/development/PLANS.md`: read its generator marker; regenerate if a generator exists, else replace the dead AUTO-GEN block with a pointer to `docs/development/plans/` + archived/.
7. `README.md:672` (`specs/sites/ocoron.com.yaml`) — verify intent (wordpress deploy example): retarget to an existing example or mark illustrative.

**Behavior Contract:** docs/registry-only phase; contract = gate asserts below (no code behavior). The docs_updater edit is data-only: `python -c "import importlib.util,sys; spec=importlib.util.spec_from_file_location('du','scripts/docs_updater.py'); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)"` must not raise.

**Validation gate:** re-run the Phase-3 audit script (`scratchpad docs_link_audit.py`, now checked into the phase as a throwaway or run via the Phase-F check in `--preview` mode): INDEX dead refs = 0; unindexed live docs = 0; then the standard closing sequence (check_doc_sync → doc_reconcile → commit → **full `/fabrik-review` looped to no-op** → gate → ✅ + plan staged).

## Phase E — Full claim-level verification fleet (all live docs)

**Interfaces — Consumes:** the stable tree (paths final). **Produces:** one evidence ledger per folder-wave at `docs/development/reviews/docs-truth-<wave>-review.md` (allowlisted pattern), each row `claim → proof (path:line | command output | live probe) → verdict (VERIFIED | FIXED | REMOVED)`; all fixes applied. Later phases rely on: zero UNRESOLVED rows.

Method (per wave; waves = `root`, `operations`, `infrastructure`, `reference-apis`, `reference-modules`, `reference-root+subdirs`, `workflows`, `traycer+workstation+zed+preplans`, `orchestrator`, `development+superpowers-active`):
1. **Extract**: pool fan-out — `fanout("docs", units=[one per doc: full doc text inlined + "extract every falsifiable claim as a table"], mode="read_only", …)` (read-only = parallel; auto-records; `set_quality` back-filled after adjudication). Docs >40KB are chunked at H2 boundaries; a file without usable headings falls back to fixed ~20KB slices with 1KB overlap.
2. **Verify**: second pool round — each claim verified against the repo (the unit inlines the claim + the relevant source excerpt gathered by the orchestrator) — plus **native fabrik-researcher/fabrik-reviewer on Opus for every Tier-A doc** (runtime-injected, fleet-synced, command-chain, code-cited — ~25 docs incl. the two EVALUATION_CHECKLISTs, FINAL_GATE_WORKFLOW, deployment.md, disaster-recovery.md, glitchtip-api.md, openrouter-api.md, the orchestrator chain files, agents-fabrik.md, agents-fabrik-core.md).
3. **Adjudicate + fix** (orchestrator, Opus): refute false claims of staleness by quoting the line; apply one systematic fix batch per doc (never incremental); live-system claims get the probe run (e.g. Gatus/Prometheus counts) or a verification-date + re-verify command stamped instead.
4. **Fresh re-verify**: a DIFFERENT agent (pool for Tier-B/C, native for Tier-A) re-reads each FIXED doc cold; any new finding loops step 3.
5. Ledger committed per wave; `set_quality` back-filled for every pool row (`check_subagent_flywheel.py` clean).

**Behavior Contract:** the ledgers themselves (one per wave, zero UNRESOLVED) — risk-ordered: Tier-A waves (`orchestrator`, `root`, `operations`) run first.

**Validation gate (per wave + phase-final):**
```bash
grep -c "UNRESOLVED" docs/development/reviews/docs-truth-*-review.md   # expect: 0 per file
python scripts/enforcement/check_convergence.py                          # expect: pass (evidence format)
```
Close each wave-batch with the standard sequence; the phase-final closing includes **`/fabrik-review` over the cumulative Phase-E diff looped to no-op** → ✅ + plan staged.

## Phase F — Enforcement gates (the durability layer)

**Interfaces — Consumes:** the clean tree (must be green under the new checks before they land in the gate — else the gate is born red). **Produces:** three new checks + one fix, registered in `final_gate.py` (Tier-2 standard; `check_retired_terms` WARN-tier), with tests. Names/CLIs later phases + CLAUDE.md cite: `python scripts/enforcement/check_doc_links.py [--json]`, `check_doc_index.py [--json]`, `check_retired_terms.py [--json]`.

**TDD order (highest-risk first — the sprawl fix guards every future commit):**
1. `tests/enforcement/test_check_doc_sprawl_newfile.py` — write FIRST, watch it fail red, then fix `check_doc_sprawl.py`: a path is "existing" iff present in HEAD (`git cat-file -e HEAD:<path>`) OR its staged status is a rename (`R*` in `git status --porcelain`); otherwise it runs the allowlist even when staged. Behaviors: (a) staged brand-new `docs/operations/x.md` → BLOCKED; (b) `git mv` of a tracked doc into `docs/operations/` → ALLOWED; (c) edit to a tracked doc → ALLOWED; (d) untracked new allowlisted path (`docs/archive/x.md`) → ALLOWED.
2. `check_doc_links.py` (from the audited scratchpad script, hardened): scans tracked .md (sources exclude `docs/archive/**`) + INDEX/CLAUDE/agents-fabrik*/README for repo-path references; resolves repo-root + file-relative; **carries a temporary per-file waiver for `docs/reference/LOCAL_LLM_INFRASTRUCTURE.md` as a SOURCE (operator-excluded from this run; its `:760,:762` links break transiently when their targets archive — waiver removed by the deferred follow-up)**; excludes placeholders and the **project-context allowlist** (the scaffold doc set names referenced from synced/orchestrator docs: `docs/DEPLOYMENT.md`, `docs/OPERATIONS.md`, `docs/README.md`, `docs/RESILIENCE.md`, `docs/data-contract.md`, `docs/ui-design.md`, `docs/design-system.md`, `docs/DATABASE_SCHEMA.md`, `docs/development/plans/00-research.md`, plus example-path heuristics: `my-api`, `myservice`, `my-service`, `foo`, `<...>`, `src/auth.py`, `scripts/long_task.py`). Behaviors: broken ref detected with source:line; clean tree passes; archive-internal links ignored; relative links resolved.
3. `check_doc_index.py`: (a) every `docs/`-path named in INDEX.md exists (dirs allowed); (b) every tracked live `docs/**/*.md` (excluding archive/**, plans|epics|reviews content files, superpowers/**, and the daily-regenerated set — `docs/reference/kilo/*_SELECTION.md` PLUS the explicit names `KILO_MODEL_CAPABILITIES.md`, `KILO_AGENT_SELECTION_GUIDE.md`, `KILO_AGENT_NAMING.md`, and `docs/traycer/kilo_selected_agents.md` — a bare `*_SELECTION.md` glob misses the first three; sourced from `daily_refresh.sh` git-add block, verified 2026-07-20) appears in INDEX.md by path or basename. Behaviors: dead INDEX ref fails; unindexed live doc fails; excluded classes pass.
4. `check_retired_terms.py` (WARN tier): flags `Kilo CLI`, `Windsurf Cascade`, `Coolify`, `Supabase` in live docs when the line/paragraph lacks a retirement marker (`retired|legacy|historical|decommissioned|pre-migration|archive`). **The never-block property comes from the SCRIPT ALWAYS `sys.exit(0)`** (emitting findings to stdout) — NOT from `advisory=True` alone: `final_gate.py:167-168` returns `passed=False` on ANY non-zero exit regardless of the advisory flag, so a WARN-only check must exit 0 like `check_lint_ratchet.py`/`check_mutation.py` do (verified 2026-07-20). Register it with `advisory=True` (preserves its stdout on the gate's exit 0). Behaviors: unmarked retired term prints a WARN with path:line + exits 0; marked mention silent; archive/** ignored.
5. Register all four in `final_gate.py` (pattern: existing check registration; `check_retired_terms` in the WARN band); AFTER-EDIT headers; update `CLAUDE.md`? — NO: CLAUDE.md's check list is generic ("the FULL Tier-2 gate"); no CLAUDE.md edit needed. `docs/workflows/FINAL_GATE_WORKFLOW.md` gets the three new per-check rows (Doc Sync Matrix: the gate's own reference doc).

**Validation gate:**
```bash
.venv/bin/python -c "import pytest"                          # toolchain preflight (verified 2026-07-20: pytest 9.0.2; tests/enforcement/ exists)
python -m pytest tests/enforcement/ -q                       # expect: all pass (new tests included)
python scripts/enforcement/check_doc_links.py --json          # expect: {"status":"success"} on the converged tree
python scripts/enforcement/check_doc_index.py --json          # expect: success
python scripts/enforcement/check_retired_terms.py --json      # expect: success or WARN-only
python scripts/final_gate.py --check --json                   # Tier-2, expect "status":"success" WITH the new checks registered
```
Close with the standard sequence (check_doc_sync → doc_reconcile → commit → **full `/fabrik-review` on the scripts+tests, looped to no-op; this phase's diff includes gate code → include the native Opus finder** → ✅ + plan staged).

## Phase G — Whole-plan convergence + docs review + finish

1. Whole-plan doc-coverage receipt: `python scripts/enforcement/check_doc_sync.py --range <step-8-baseline>..HEAD` + `check_doc_stubs.py --range …` → every fired trigger touched.
2. **`/fabrik-docs-review`** over the tree (the correctness pass on top of touch-on-change), per the executor contract.
3. **Whole-plan `/fabrik-review`** over the cumulative diff, looped to a no-op pass.
4. Final no-op re-scan (the operator's protocol): one fresh audit round (pool sweep + 1 native Opus) over the whole docs tree — must return zero placement/residue/currency findings; its empty findings table is appended to the last ledger.
5. `python scripts/final_gate.py --json` (full Tier-2, not --check — auto-fix allowed, diff-scoped) → `"status":"success"`; `check_convergence.py` green.
6. LESSONS_LEARNT entry (candidate: "a path pin is a one-line edit, not a placement argument — audit verdicts must separate SHOULD-live from COSTS-to-move"); CHANGELOG entry finalized; plan `Status: EXECUTED`, archive plan to `plans/archived/`; release lock; handoff report incl. the **fabrik-lib report-only items** (SEAMS.md ×13 refs, `watchdog/emitter/emitter.py:9` archived-plan docstring, `web-scrape/SPEC.md:6`, `chrome-ext-billing-kit/src/types.ts:4` — that repo's agent's lane) and the deferred-renames list.

---

## Evidence

Phase A/B grounding (verified live this session, 2026-07-20):
```
$ sed -n '525,545p' scripts/kilo-benchmarks/daily_refresh.sh
    git add -- \
      .windsurf/rules/ai/*.md \
      docs/reference/kilo/CODING_SUBAGENT_SELECTION.md \
      docs/reference/kilo/TASK_SUBAGENT_SELECTION.md \
      ...
      docs/reference/windsurf/cascade-models.md \
      docs/traycer/kilo_selected_agents.md \
      2>/dev/null || true
    if git diff --cached --quiet; then
      echo "[auto-commit] nothing regenerated changed — tree already clean"
```
```
$ grep -n "kilo" scripts/fabrik_synced_manifest.py | head -3
29:    "kilo_code_review.py",
30:    "kilo_docs_enforcer.py",
73:    "docs/reference/kilo",
```
- `review_rubric.py:79-83` — both EVALUATION_CHECKLIST paths injected (read this session).
- `check_doc_sprawl.py:115-118` (`git ls-files --error-unmatch` = index lookup) + `:184-185` (tracked → allow); scratch-repo test: staged new file passes rc=0 (the bypass), `git mv` destination tracked rc=0 (moves safe) — 2026-07-20 audit agent, empirical.
- `git add existing missing` → exit 128, stages nothing (scratch-repo, 2026-07-20) — the Phase-B breakage premise.
- `scaffold.py:1053-1059,5962-5971` (kilo copytree), `:1111-1115,6025-6031` (KILO_AGENT_NAMING seed/refresh, `.exists()`-guarded), `tests/test_scaffold_fix.py:171-174,208-209` — read by the adversarial verifier, quoted in its report.
- `sync_enforcement_to_projects.py:535-556` (GOVERNANCE_DIRS orphan-prune), `:559-561` (missing REFERENCE_DOCS source skipped silently, no pruning) — read 2026-07-20.
- Consumer sets per moved/archived file: the five audit reports (link fan-in per file with path:line), incl. `glitchtip.py:246` runtime message, `vast_provider.py:229,398`, `cli.py:3261`, `_transport.py:14` — each re-read by the verifier's spot-check pass.
- Link/index baseline: 668 broken pairs (480 archived-plan sources, 13 live-plan, 175 other), 20 dead INDEX refs, 108 unindexed docs, 25+11 stale docs_updater rows, 29 unresolvable fabrik-lib pins — `scratchpad/docs_link_audit.py` + `task4_out.txt`, 2026-07-20.
- Dormancy pre-evidence: wavespeed deliverables absent (`add_via_wavespeed_column.py`, `scrape_wavespeed_catalog.py` — `test -f` fails, audit run); twins plan phases 0/A/B/C ✅ with SHAs at `:23,:29,:40,:56`; plan-lock statuses all `released`/`complete` (27 locks read).
- Plan-review round 1 (2026-07-20): native Opus grounder re-read items 1-19 (glitchtip/vast/runpod/cli/_transport/tools/kilo_agents_db/sync-vps-sysadmin/probe/INDEX/docs_updater/audit_pipeline/gpu-rent/QUICKSTART/cli-reference/capability-defects/mega-00:105 + cascade-consumer sweep + modules-move code-ref sweep) — 17 CONFIRMED, 2 amended into the plan (cascade extra consumers incl. `gitignore-synced-block.txt:21`; INDEX:716 attribution). Pool round: 3 family-diverse reviewers (deepseek-v3.2-exp, gemini-3-flash-preview, qwen3-max) over plan thirds — 5 accepted findings (A0 command templates, DOCUMENTATOR docstring fixups, all-basenames gate loop, moved-file self-link re-resolution, template_renderer link wording), 1 refuted (gate-grep substring collision — `reference/glitchtip-api.md` is not a substring of `reference/apis/glitchtip-api.md`), rows scored via `set_quality`.

## Self-audit

- **Coverage vs "What we already agreed":** full claim-level everywhere → Phase E (all live docs, tiered only by *ordering*, not depth); no-residue → Phases A–D enumerate every audit finding by file; renames deferred → absent from all phases, listed in Residuals; moves+subfoldering → Phase C table; dormancy proof → A0 protocol, PARKED fallback; Approach B ordering → phase order A→G; pool+native both → Phases E steps 1-4 + every phase's review step; Cascade atomic → Phase B single commit.
- **Cross-phase signatures:** Phase C's path table is cited by D (INDEX rows), E (wave `reference-apis`/`reference-modules`), F (`check_doc_links` scans final paths); Phase F's script names/CLIs are what G step 5's gate runs; no phase references a symbol another phase doesn't produce.
- **Gates runnable from WSL:** every gate is `python`/`bash`/`grep`/`pytest` — zero `fabrik …` shell-outs.
- **Grounding rounds 1-3 complete (2026-07-20):** round 1 corrected the two emit-pass flags + cascade consumer set; round 2 (fresh partition — locks, archive dirs, 24-spec sweep, wave coverage) added the pool-dispatch-map slug-drift + the merged-file docs_updater prune; round 3 (Phase D/F/G partition, native Opus) corrected 4 defects — the 4 already-done research-files retargets DROPPED (commit 4951789e), `check_retired_terms` never-block property tied to `sys.exit(0)` not `advisory=` alone, the index-exclusion glob given explicit names, AI_TAXONOMY reframed as a prose-claim fix, `validate_i18n.py` resolved to a project-side scaffold script. Confirmed safe: the sprawl-gate fix has no existing test to break; `final_gate.py` + `scripts/enforcement/` are hub-synced so hub edits are canonical.

## Residual unknowns

**Resolved in-plan (self-service):** FAQ archive-vs-stub (Phase A pre-step reads check_structure semantics); universal-watchdog archive-vs-park (A0 check 3 against the watchdog-deploy-side plan); `validate_i18n.py` refs (Phase D probe); benchlm spec dormancy (A0 via `scrape_benchlm.py`); PLANS.md generator existence (Phase D step 6).
**Deliberately deferred (operator decision, NOT open):** kilo/→agents/ + MD/→prompting/ renames, windsurf/ dissolution, superpowers→development/specs merge, the 4 sync-pinned reference-doc moves — each needs a coordinated sync cycle (kilo/ additionally a fabrik-lib line); revisit as its own plan.
**Cross-repo (report-only, HARD STOP):** fabrik-lib's 4 own-lane pins (SEAMS refs, emitter docstring, SPEC.md, types.ts) — handed off in Phase G's report.
**Still-open:** none — every execution-blocking question is answered or self-service per above.
