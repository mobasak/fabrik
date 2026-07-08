# Model-Discovery Pipeline Audit — Implementation Plan

**Status:** CONVERGED
**Date:** 2026-07-08
**Owner:** primary (this session)
**Goal:** Systematically audit the daily-refresh model-discovery pipeline end-to-end (external ingest → DB → derivations → emitted docs → browser GUI) and surface every issue / wrong data / missing part / bug / discrepancy. Fix in-scope small issues inline; escalate large ones to their own follow-up plans + a consolidated audit report.

**Converged 2026-07-08 via `/fabrik-plan-review`** — 3 adversarial grounding passes to a genuine md5-verified no-op. Pass Ledger:

| Pass | Axes re-grounded | Edits | Plan md5 (start → end) |
|-----:|---|---:|---|
| 1 | claims (path:line) · gates · interfaces · completeness · environment preflight | 5 | `56051e64d29502929dae6300d92a7ad5` → `14c8f19f97eadaebac051eca0589b572` |
| 2 | Pass 1 edits re-verified + concurrency re-check + spot-check on untouched citations | 3 | `14c8f19f97eadaebac051eca0589b572` → `c7487a2ca54e7802288d74bd12c4d2c0` |
| 3 | all axes (Pass 1+2 edits + every 13 path:line citation re-verified live) | **0** | `c7487a2ca54e7802288d74bd12c4d2c0` → `c7487a2ca54e7802288d74bd12c4d2c0` ✓ → **CONVERGED** |

Pass 1 fixed 5 line-drift defects: `daily_refresh.sh` ingestor range `:111-322` → `:111-331` (microbench_or_models is at :331, outside stated range); `rank_coding_subagents.py:AUTO_OUTPUT_PRICE_CEILING` :74 → :86; `libs/subagents/select.py:def pick_models` :283 → :275; `models_browser_template.html:TAB_DEFAULTS` :937 → :935 (both mentions in Context Ledger + Evidence). Pass 2 fixed 3 concurrency-drift updates: `2026-07-08-plan-1-subagent-pool-flywheel-enforcement.json` flipped `active → released` mid-review; concurrency section in "What we already agreed" + File Scope + Self-audit all updated to "1 active + 1 recently-released, both disjoint." Pass 3 no-op verified: START md5 `c7487a2ca54e7802288d74bd12c4d2c0` == END md5 `c7487a2ca54e7802288d74bd12c4d2c0`.

**Handoff:** User runs `/fabrik-execute-plan docs/development/plans/2026-07-08-plan-3-model-pipeline-audit.md`. See "Residual unknowns → still-open" for non-blocking follow-ups the executor should surface for operator approval (only Residual #1, `microbench_or_models` real-cost re-run — the other two are self-handling).

## What we already agreed (Phase 0)

- **Goal (operator-quoted, 2026-07-08).** "Create a plan to test all pipeline of model discovery and pushing them in gui and dbs and files. The plan should find all issues/wrong data/missing parts/bugs/discrepancies."
- **Approach: AUDIT-first, not build-first.** This plan produces (a) one consolidated findings report at `docs/development/audits/2026-07-08-model-pipeline-audit.md`, (b) in-scope small fixes (≤ 50 LOC each, single-file, no schema change), and (c) escalation stubs for large-scope bugs (each carries a named `/fabrik-spec` topic for a future plan). It does NOT rewrite the pipeline.
- **Scope (grounded from `scripts/kilo-benchmarks/daily_refresh.sh:111-331`, verified this turn).** 30+ pipeline steps across 5 stages:
  1. **Ingest** — 13 scripts (`verify_openrouter_catalog`, `restore_wrongly_deprecated_direct_vendors`, `discover_hidden_openrouter_routes`, `scrape_openrouter_rankings`, `scrape_openrouter_endpoints`, `scrape_coding_benchmarks`, `scrape_artificial_analysis`, `scrape_groq_speeds`, `scrape_windsurf_models`, `fetch_replicate_prices`, `fetch_fal_prices`, `fetch_direct_vendor_prices`, `microbench_or_models`).
  2. **Derive** — 7 scripts (`derive_quality_v2`, `derive_cheapest_gateway`, `classify_ai_category`, `category_route_mapper`, `role_mapper`, `embedding_role_mapper`, `backfill_unknown_providers`).
  3. **Aggregate/Rank** — 7 scripts (`rank_coding_subagents`, `rank_task_subagents`, `rank_tts`, `rank_stt`, `rank_translation`, `rank_image_gen`, `rank_candidate_signups`).
  4. **Emit** — 8 emitters + 12 docs + 1 HTML browser: `category_export_markdown`, `embedding_export_markdown`, `generate_model_capabilities`, `generate_selection_guide_roster`, `generate_kilo_agents`, `update_gateway_counts`, `export_traycer_registry`, `export_models_browser`.
  5. **Persist** — `scripts/kilo-benchmarks/kilo_agents.db` (SQLite, 87 cols on `agents`, 806 rows; 7 `gpu_providers` rows; 26 `embedding_models` rows) + `fabrik_analytics.subagent_runs` on `postgres-main`.
- **Read-heavy, no schema migrations.** The audit runs the pipeline in isolated / cached / dry-run modes where possible. Any real DB write from a fixer step is limited to `UPDATE agents SET …` on ≤ 20 explicit rows, or `INSERT OR IGNORE` — never `ALTER TABLE` (that's a follow-up plan).
- **Findings shape: 4 severities per finding.** `CONFIRMED` (reproducible failure, wrong data) → **fix inline if ≤ 50 LOC**. `PLAUSIBLE` (real-if-rare) → **prove impossible OR add regression test**. `STYLE` (cosmetic) → noted, not shipped. `ESCALATE` (structural — needs its own plan) → named follow-up `/fabrik-spec` topic; NOT fixed here.
- **Reporting output.** `docs/development/audits/2026-07-08-model-pipeline-audit.md` (created by Phase F) carries: (a) per-stage findings ledger with severity, (b) commit hash for each inline fix, (c) escalation table for `ESCALATE`-severity items, (d) coverage table (which pipeline steps got audited, which were skipped and why).
- **Concurrency (verified 2026-07-08, `.fabrik/plan-locks/*.json`, re-verified during Pass 2 of /fabrik-plan-review).** 1 active sibling lock — `2026-07-07-plan-1-sysadmin-claude-rotation` (owns `scripts/sysadmin/**`, disjoint from this plan). Previously `2026-07-08-plan-1-subagent-pool-flywheel-enforcement` was active (owned `libs/subagents/`) but flipped to `status=released` mid-review; its scope was disjoint from this plan anyway (`libs/subagents/` is consumed READ-ONLY here, never mutated). This plan's owned scope is `scripts/kilo-benchmarks/**` + `docs/reference/kilo/**` + `docs/development/audits/**` — disjoint from every current or recent lock.

**Branch: RICH.** The operator's ask names the goal (test all pipeline stages) and pins the approach (find issues + fix small ones + escalate large ones). No brainstorming needed — the pipeline shape is known from `daily_refresh.sh` and the archived plans that built each stage.

## Global Constraints

Verbatim from binding sources — every phase inherits these:

- **Python 3.11+**, stdlib-first (`sqlite3`, `argparse`, `pathlib`, `re`, `subprocess`, `tempfile`). No new pip deps for the audit itself.
- **Explicit `git add <path>` only** — never `git add -A`, `git add .`, or `git commit -a` (CLAUDE.md HARD STOP).
- **DB path**: `scripts/kilo-benchmarks/kilo_agents.db` (SQLite, hub-side). No `postgres-main:5432` calls from this plan (audit runs on the hub's local DB copy). VPS `subagent_runs` is only READ for the pool-flywheel dogfood record — never mutated.
- **Sync-manifest awareness.** `docs/reference/kilo/**` is governance-synced to every project via `scripts/fabrik_synced_manifest.py:69`. Audit findings that recommend doc changes update the hub source (`/opt/fabrik/docs/reference/kilo/*.md`); sync propagates.
- **Provenance trailers on every commit** — `Agent-Role: subagent | orchestrator | review-fix`, `Agent-Phase: A|B|C|D|E|F`, `Agent-Task: N` for subagent commits, `Agent-Context:` one-liner.
- **No `alter table` in-scope.** A finding that needs a schema migration is `ESCALATE` and becomes a follow-up plan.
- **No live vendor API calls that spend money.** Ingestors that would hit paid APIs (`fetch_replicate_prices`, `fetch_fal_prices`, `microbench_or_models` non-dry, `fetch_direct_vendor_prices`) run in `--dry-run` / cache-only / `--limit 0` mode for this audit. Real-cost re-runs only if the audit finds a cache-vs-live drift that needs proving (operator-approved per-step).
- **Fail-soft is the pipeline invariant.** Every ingestor uses `_step "…" … || echo "… failed (non-fatal)"` in `daily_refresh.sh`; audit steps preserve this by never `raise`-ing on transient network errors.
- **Provenance for pool subagent runs.** Every pool dispatch made by the audit calls `record_agent_run(spec, result, quality_score=<0-5>, project="fabrik-hub")` after evaluation; `SUBAGENT_RUNS_DSN` is autoloaded from `/opt/fabrik/.env` (peer-auth via unix socket; wired 2026-07-08 at `394dbc82`). This dogfoods the very flywheel the emitters consume.

## Context Ledger

Binding sources — the cold executor inherits all of these.

| Source | What binds | Grounded ref |
|---|---|---|
| ACTIVE rule pack `core/10-python.md` | Python 3.11 typing (`from __future__ import annotations`), no bare `except`, no `print` in libraries (advisory) | `.windsurf/rules/core/10-python.md` (19 ACTIVE packs total per `select_rules.py`) |
| ACTIVE rule pack `core/25-data-postgres.md` | Nullability + idempotency discipline (applies to SQLite too) — new columns must specify `NULL` behavior; migrations idempotent | `.windsurf/rules/core/25-data-postgres.md` |
| ACTIVE rule pack `core/40-documentation.md` | Doc Sync Matrix per CLAUDE.md; INDEX.md + CHANGELOG.md on file add | `.windsurf/rules/core/40-documentation.md` |
| ACTIVE rule pack `core/45-testing-strategy.md` | 1 test for the highest-risk path per phase | `.windsurf/rules/core/45-testing-strategy.md` |
| ACTIVE rule pack `core/62-using-subagents.md` | Pool-default for gradeable fan-out; `record_agent_run` (not `record_run`); `results_table` per dispatch; ≤ $1.5/Mtok cap self-enforced by `pick_models`; `allow_ungrounded=True` OR `tools_enabled=True` for single-shot workers | `.windsurf/rules/core/62-using-subagents.md § Dispatch policy` |
| `libs/subagents` (vendored — canonical `d1928e6`, re-vendored 2026-07-08) | `record_agent_run(spec, result, *, quality_score, project, dsn, connect) -> bool` at `pg_ledger.py:132`; `pick_models(task_type, n=1, *, max_cost_per_mtok=None, allow_above_cap=False, …) -> list[str]` at `select.py:275` with hard cap `_MAX_POOL_PRICE_PER_MTOK = 1.5` at `:67`; `run_agents(specs, repo=<path>) -> list[AgentResult]` at `agent.py`; `results_table(results) -> str` at `agent.py` | `libs/subagents/pg_ledger.py:132`; `libs/subagents/select.py:67,275`; `libs/subagents/agent.py` |
| `scripts/kilo-benchmarks/daily_refresh.sh` (30+ steps) | Canonical step ordering + fail-soft `\|\| echo … non-fatal` convention. Audit MUST run steps in the same order so downstream-derived rows aren't stale-compared | `scripts/kilo-benchmarks/daily_refresh.sh:111-331` (verified this turn) |
| `scripts/kilo-benchmarks/kilo_agents.db` schema | 87 cols on `agents` (806 rows); `gpu_providers` 11 cols (7 rows); `embedding_models` (26 rows); `subagent_runs` on `postgres-main` (13 cols, INSERT-only role fabric-hub granted 2026-07-08) | `sqlite3 kilo_agents.db "PRAGMA table_info(agents)"` verified this turn |
| `docs/reference/kilo/**` (10 emitted docs + 2 hand-authored) | Governance-synced to every project; audit findings that touch these go to the hub source | `docs/reference/kilo/AI_VENDOR_ACCESS.md` (hand), `BENCHMARK_SOURCES.md`, `CANDIDATE_SIGNUPS.md`, `CODING_SUBAGENT_SELECTION.md`, `IMAGE_GEN_SELECTION.md`, `KILO_AGENT_NAMING.md`, `KILO_AGENT_SELECTION_GUIDE.md`, `KILO_CLI_REFERENCE.md`, `KILO_MODEL_CAPABILITIES.md`, `KILO_MODEL_SELECTION.md`, `STT_SELECTION.md`, `TRANSLATION_SELECTION.md`, `TTS_SELECTION.md`, `TASK_SUBAGENT_SELECTION.md` |
| `scripts/kilo-benchmarks/models_browser.html` + `models_browser_template.html` | 11 tabs (`overview`, `reasoning`, `coding`, `translation`, `transcription`, `voice`, `image`, `video`, `ocr`, `rent-gpu`, `candidates`); `TAB_DEFAULTS` in template `:935` with `altTbody` keys for the 2 new tabs; `setTab` swap logic; server-rendered rows for `rows-gpu` + `rows-candidates` (this session, `8eaf6a95`) | `scripts/kilo-benchmarks/models_browser_template.html:660-661` (chip decls); `:704-708` (alt tbodies); `:935` (TAB_DEFAULTS) |
| `fabrik-lib/README.md` verdict | No new capability introduced by this audit → no vendor/enhance decision. `libs/subagents/` already vendored (canonical `d1928e6` synced this turn); consumed READ-ONLY for `record_agent_run` from pool workers. No fresh module built | `/opt/fabrik-lib/README.md` (checked) |
| AGENTS.md invariants | **N/A for this plan** — no deployed service, no `compose.yaml`, no `postgres-main` write path from hub-side, no Traefik routing, no memory limits, no ports. Hub-side tooling audit only | `AGENTS.md` (no infra invariants touched) |
| `shape:` flag | **N/A** — no `specs/services/*.yaml` touched. Confirmed via file scope | Spec inspection |

**fabrik-lib consult record:** Verified `libs/subagents/` (only module the audit imports) at canonical `d1928e6` this turn (only `agent.py` was drifted → resynced). Every other capability is stdlib. No `🆕 fabrik-lib candidate` in scope.

---

## Phase A — Ingestor audit (13 scripts, parallel fan-out)

**Goal.** For each of the 13 ingestor scripts in `daily_refresh.sh:111-322`, verify: (a) runs without crashing in `--dry-run`/cache mode; (b) DB writes are conservative (only `INSERT OR IGNORE` + explicit `UPDATE` on tagged rows — no unexpected `DELETE`/`TRUNCATE`); (c) `speed_source` / `last_verified` / `status` / `discard_reason` tags are consistent with plan spec (`docs/reference/kilo/BENCHMARK_SOURCES.md`); (d) fail-soft on network error (never `raise`).

### Interfaces

**Consumes:** nothing (Phase A is the root of the audit chain).

**Produces:**

- **File** `docs/development/audits/phase-a-ingestor-findings.md` — one row per ingestor with columns: `script | ran | dry-run supported | writes tagged correctly | fail-soft on network error | finding-severity | finding-summary | fix-commit`. Emitted by the orchestrator after subagent merge. Header: `Generated: 2026-07-08 · Phase A of docs/development/plans/2026-07-08-plan-3-model-pipeline-audit.md`.
- **Function** `_load_ingestor_findings(path: Path) -> list[dict]` in a new helper `scripts/kilo-benchmarks/audit_pipeline.py` — returns the parsed per-row findings. Consumed by Phase F for the consolidated report.
- **Signal**: any `CONFIRMED` finding blocks Phase F's final gate until the inline fix ships or the item is `ESCALATE`d with a named follow-up-plan topic.

### Subagent Mandates (Phase A is parallelizable — 13 independent scripts)

**Pool-default per `62-using-subagents.md § Dispatch policy`.** Fan out **13 pool subagents (one per ingestor)** via `run_agents(specs)` where each `AgentSpec` carries:

- `task_type = "review"` (this IS a code review of the ingestor's shape + tag consistency + fail-soft contract).
- `model = pick_models("review", n=1)[0]` — module's `_MAX_POOL_PRICE_PER_MTOK = 1.5` cap self-enforces at `libs/subagents/select.py:67`; do NOT pass `max_cost_per_mtok` unless a tighter project budget is intended.
- `tools_enabled = False` (single-shot ingestor-file grounding — the file gets inlined into `task`), with `allow_ungrounded = True` since the audit prompt inlines the ingestor source verbatim; the fail-closed guard at `libs/subagents/agent.py` refuses ungrounded single-shot review/docs otherwise.
- `owned_paths = []` (read-only review; no file mutation from subagents).
- `body = None`.

Each subagent returns `AgentResult`. Orchestrator (Opus) evaluates + calls `record_agent_run(spec, result, quality_score=<0-5>, project="fabrik-hub")` per subagent (recording feeds the flywheel — dogfood). Orchestrator emits `results_table(all_results)` for human-readable summary. Guard the import with `try: from libs.subagents import record_agent_run / except ImportError: record_agent_run = None` per `62-using-subagents.md` rollout safety.

Merge sequentially into master by ascending script name so conflict resolution is deterministic. Zero code conflicts expected — each subagent inspects one file, all writes go to the shared findings MD (append-safe with unique row keys).

### Steps

**A.1 — TDD: write the highest-risk-path test FIRST** (`scripts/kilo-benchmarks/tests/test_audit_pipeline.py`).

The risky path: the audit's own findings-MD builder — if it silently drops a subagent's row, the whole pipeline's audit coverage would be under-reported. Test:

```python
def test_load_ingestor_findings_preserves_every_row(tmp_path):
    md = tmp_path / "phase-a-ingestor-findings.md"
    md.write_text(
        "Generated: 2026-07-08\n\n"
        "| script | ran | dry-run | writes-tagged | fail-soft | severity | summary | fix-commit |\n"
        "|---|---|---|---|---|---|---|---|\n"
        "| verify_openrouter_catalog | yes | yes | yes | yes | STYLE | note-only | — |\n"
        "| scrape_groq_speeds | yes | partial | yes | yes | CONFIRMED | HTTP timeout unhandled | pending |\n"
        "| microbench_or_models | no | yes | n/a | yes | ESCALATE | needs its own plan | — |\n"
    )
    from audit_pipeline import _load_ingestor_findings
    rows = _load_ingestor_findings(md)
    assert len(rows) == 3
    assert rows[0]["script"] == "verify_openrouter_catalog"
    assert rows[1]["severity"] == "CONFIRMED"
    assert rows[2]["severity"] == "ESCALATE"
```

**Gate A.1 (must FAIL RED):**

```bash
cd scripts/kilo-benchmarks && python -m pytest tests/test_audit_pipeline.py::test_load_ingestor_findings_preserves_every_row -x 2>&1 | tail -6
# Expected: FAILED (ModuleNotFoundError: No module named 'audit_pipeline') — red for the right reason.
```

**A.2 — Implement `scripts/kilo-benchmarks/audit_pipeline.py`** with the helpers this plan uses across all 6 phases:

- `_load_ingestor_findings(path: Path) -> list[dict]` — parses the phase-A MD.
- `_load_findings_generic(path: Path) -> list[dict]` — same shape reader for phase-B/C/D/E findings (accept variable column set via the header row).
- `_dispatch_pool_audit(scripts: list[Path], task: str, task_type: str = "review") -> list[dict]` — thin wrapper: builds `AgentSpec` list, calls `run_agents`, calls `record_agent_run` per result. Guards the import. Handles `record_agent_run = None` gracefully.
- `_render_findings_md(phase: str, rows: list[dict], out: Path) -> None` — emits the standard 8-column table.

Header: `# AFTER-EDIT: scripts/kilo-benchmarks/tests/test_audit_pipeline.py`

**Gate A.2:**

```bash
cd scripts/kilo-benchmarks && python -m pytest tests/test_audit_pipeline.py -x 2>&1 | tail -5
# Expected: 1 passed
```

**A.3 — Dispatch 13 pool subagents in a single message** (per `62-using-subagents.md § Dispatch policy`). Each subagent's `AgentSpec`:

- `task` — verbatim: "Audit `<script_path>`. Report: (1) does it support a `--dry-run` / cache-only mode? (2) does every write path use `INSERT OR IGNORE` or explicit `UPDATE …WHERE id=?`? (3) are `speed_source` / `last_verified` / `status` / `discard_reason` tags set per the shape at `docs/reference/kilo/BENCHMARK_SOURCES.md`? (4) does every network call catch `httpx.HTTPError` (or equivalent) and non-fatally return? Emit findings as a single Markdown table row: `\| <script> \| <ran> \| <dry-run> \| <writes-tagged> \| <fail-soft> \| <severity> \| <summary> \| — \|`. Severity ∈ {STYLE, CONFIRMED, PLAUSIBLE, ESCALATE}." + the FULL ingestor source file inlined below.
- `model = pick_models("review", n=1)[0]`.
- `tools_enabled = False`, `allow_ungrounded = True` (source is inlined).
- `owned_paths = []`.

The 13 scripts:

```python
INGESTORS = [
    "scripts/kilo-benchmarks/verify_openrouter_catalog.py",
    "scripts/kilo-benchmarks/restore_wrongly_deprecated_direct_vendors.py",
    "scripts/kilo-benchmarks/discover_hidden_openrouter_routes.py",
    "scripts/kilo-benchmarks/scrape_openrouter_rankings.py",
    "scripts/kilo-benchmarks/scrape_openrouter_endpoints.py",
    "scripts/kilo-benchmarks/scrape_coding_benchmarks.py",
    "scripts/kilo-benchmarks/scrape_artificial_analysis.py",
    "scripts/kilo-benchmarks/scrape_groq_speeds.py",
    "scripts/kilo-benchmarks/scrape_windsurf_models.py",
    "scripts/kilo-benchmarks/fetch_replicate_prices.py",
    "scripts/kilo-benchmarks/fetch_fal_prices.py",
    "scripts/kilo-benchmarks/fetch_direct_vendor_prices.py",
    "scripts/kilo-benchmarks/microbench_or_models.py",
]
```

**Gate A.3:**

```bash
python -c "
import sys, pathlib
sys.path.insert(0, 'scripts/kilo-benchmarks')
sys.path.insert(0, '.')
from audit_pipeline import _dispatch_pool_audit
INGESTORS = [pathlib.Path(p) for p in [
    'scripts/kilo-benchmarks/verify_openrouter_catalog.py',
    'scripts/kilo-benchmarks/scrape_groq_speeds.py',
    'scripts/kilo-benchmarks/fetch_direct_vendor_prices.py',
]]  # sub-cohort smoke test — 3 scripts, not the full 13
rows = _dispatch_pool_audit(INGESTORS, task='ingestor audit', task_type='review')
assert len(rows) == 3, f'expected 3 findings rows, got {len(rows)}'
print('A.3 sub-cohort gate OK — 3 rows returned')
"
# Expected: A.3 sub-cohort gate OK — 3 rows returned
```

The full 13-script dispatch runs in a subagent-driven mandate below (Subagent Mandates section above). Only the 3-script smoke gates the code path.

**A.4 — Merge subagent results + emit `phase-a-ingestor-findings.md`.** Orchestrator (Opus) reads all 13 `AgentResult` values, extracts each subagent's finding row, calls `_render_findings_md("A", rows, Path("docs/development/audits/phase-a-ingestor-findings.md"))`.

**Gate A.4:**

```bash
test -f docs/development/audits/phase-a-ingestor-findings.md && \
  head -1 docs/development/audits/phase-a-ingestor-findings.md | grep -qE "^# Phase A" && \
  grep -cE "^\| " docs/development/audits/phase-a-ingestor-findings.md | awk '$1 >= 13 { print "row count OK:", $1; exit 0 } { print "TOO FEW rows:", $1; exit 1 }'
# Expected: row count OK: 13 (or higher, if header rows counted)
```

**A.5 — Inline fixes for CONFIRMED (≤ 50 LOC each).** For every `CONFIRMED` finding in `phase-a-ingestor-findings.md`:

- If the fix is ≤ 50 LOC in a single file (typical: an `except httpx.HTTPError` addition, a `.get()` swap for indexed access, an `INSERT OR IGNORE` swap for plain `INSERT`) → apply inline this phase, commit as `fix(kilo-benchmarks): Phase A audit — <script> <one-line summary>`, update the finding's `fix-commit` cell with the commit hash.
- If the fix is > 50 LOC OR touches multiple files OR needs a schema change → mark `severity = ESCALATE` and add a row to the escalation table (created in Phase F). Do NOT fix here.

**Gate A.5:**

```bash
# Every CONFIRMED row must have a non-"pending" fix-commit OR be re-tagged ESCALATE.
python -c "
import re, pathlib
md = pathlib.Path('docs/development/audits/phase-a-ingestor-findings.md').read_text()
open_confirmed = 0
for line in md.splitlines():
    if not line.startswith('| ') or 'severity' in line.lower() or set(line.strip().replace('|','').replace(' ','')) <= set('-:'):
        continue
    cells = [c.strip() for c in line.strip('|').split('|')]
    if len(cells) < 8: continue
    sev = cells[5].upper()
    fix = cells[7]
    if sev == 'CONFIRMED' and (fix == 'pending' or fix == '—'):
        print(f'  UNRESOLVED CONFIRMED: {cells[0]}')
        open_confirmed += 1
assert open_confirmed == 0, f'{open_confirmed} CONFIRMED findings remain unresolved (fix or ESCALATE)'
print('A.5 gate OK — every CONFIRMED is fixed or ESCALATEd')
"
```

**A.6 — Doc-sync + review + commit.**

1. `python scripts/enforcement/check_doc_sync.py` → any WARNING whose trigger file is in Phase A's diff must be resolved.
2. **BLOCKING gate:** invoke `/fabrik-review` on Phase A's diff (`docs/development/audits/phase-a-ingestor-findings.md` + `scripts/kilo-benchmarks/audit_pipeline.py` + `scripts/kilo-benchmarks/tests/test_audit_pipeline.py` + any inline-fixed ingestor files). Full adversarial methodology — parallel `fabrik-reviewer` finder subagents, refute false positives, prove-before-fix each CONFIRMED finding with a kept regression test. Loop until one full pass returns zero CONFIRMED OR PLAUSIBLE findings.
3. Commit (explicit paths):

   ```bash
   git add docs/development/audits/phase-a-ingestor-findings.md \
           scripts/kilo-benchmarks/audit_pipeline.py \
           scripts/kilo-benchmarks/tests/test_audit_pipeline.py \
           [any inline-fixed ingestor files from A.5]
   git commit -m "$(cat <<'EOF'
   audit(kilo-benchmarks): Phase A — ingestor audit + inline CONFIRMED fixes

   Merged-From: 13 pool subagents, one per ingestor script.
   Agent-Role: orchestrator
   Agent-Phase: A
   Agent-Context: pool-fanned 13 ingestor audits; emitted phase-a-ingestor-findings.md; inline-fixed <N> CONFIRMED; escalated <M> to follow-up plans.
   Conflicts-Resolved: 0

   Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
   EOF
   )"
   ```

---

## Phase B — Derivation audit (7 scripts, parallel fan-out)

**Goal.** For each of the 7 derivation scripts (`derive_quality_v2`, `derive_cheapest_gateway`, `classify_ai_category`, `category_route_mapper`, `role_mapper`, `embedding_role_mapper`, `backfill_unknown_providers`), verify: (a) runs deterministically on the current DB — same input → same output (2 back-to-back runs produce zero diff on the affected columns); (b) no NULL propagation (a NULL upstream doesn't overwrite a valid downstream value); (c) no dependency cycle (deriver order in `daily_refresh.sh` is topologically sound); (d) consistency across derivers — e.g. `derive_cheapest_gateway` and `classify_ai_category` must not disagree on which rows are "active".

### Interfaces

**Consumes from Phase A:**

- `_dispatch_pool_audit`, `_render_findings_md`, `_load_findings_generic` from `scripts/kilo-benchmarks/audit_pipeline.py` (Phase A output — MUST be importable). No re-declaration; a subagent inlines the same source verbatim.

**Produces:**

- **File** `docs/development/audits/phase-b-derivation-findings.md` — one row per deriver with columns: `script | deterministic | no-null-propagation | in-order | cross-consistent | severity | summary | fix-commit`.

### Subagent Mandates (Phase B is parallelizable — 7 independent derivers)

**Pool-default.** Fan out **7 pool subagents (one per deriver)** — identical dispatch pattern to Phase A but with `task_type = "review"` still (derivers are inspected structurally, same review shape). Each subagent inspects one deriver source + the DB view its output populates (SELECT snippet inlined).

### Steps

**B.1 — TDD: write the highest-risk determinism test FIRST** (`scripts/kilo-benchmarks/tests/test_audit_derivation_determinism.py`).

The risky path: a deriver that produces different output on a second run against the same DB — silent non-determinism corrupts every downstream ranker.

```python
def test_derivation_second_run_is_no_op(tmp_path, monkeypatch):
    """Run any deriver TWICE against a snapshot; the second-run diff must be empty.

    Uses a scratch copy of the real DB to avoid corrupting the live pipeline state.
    """
    import shutil, sqlite3, subprocess, sys
    src = "scripts/kilo-benchmarks/kilo_agents.db"
    scratch = tmp_path / "kilo_agents.db"
    shutil.copy(src, scratch)
    monkeypatch.setenv("KILO_DB", str(scratch))
    # derive_cheapest_gateway is the canonical determinism smoke — it reads
    # gateway_prices JSON and writes cheapest_gateway* cols.
    subprocess.run([sys.executable, "scripts/kilo-benchmarks/derive_cheapest_gateway.py"], check=True)
    conn = sqlite3.connect(scratch)
    snap1 = conn.execute("SELECT id, cheapest_gateway, cheapest_gateway_price FROM agents ORDER BY id").fetchall()
    conn.close()
    subprocess.run([sys.executable, "scripts/kilo-benchmarks/derive_cheapest_gateway.py"], check=True)
    conn = sqlite3.connect(scratch)
    snap2 = conn.execute("SELECT id, cheapest_gateway, cheapest_gateway_price FROM agents ORDER BY id").fetchall()
    conn.close()
    assert snap1 == snap2, "derive_cheapest_gateway is non-deterministic (second run mutated rows)"
```

**Gate B.1 (must FAIL RED if any deriver is non-deterministic; PASS if all clean):**

```bash
cd scripts/kilo-benchmarks && python -m pytest tests/test_audit_derivation_determinism.py -x 2>&1 | tail -6
# Expected: 1 passed (deriver IS deterministic today; the test guards regressions)
```

**B.2 — Dispatch 7 pool subagents in a single message** (Phase B derivation cohort). AgentSpec.task inlines each deriver source + a `SELECT DISTINCT <affected-column> FROM agents LIMIT 20` snapshot for reference.

**Gate B.2:**

```bash
python -c "
import sys, pathlib
sys.path.insert(0, 'scripts/kilo-benchmarks')
sys.path.insert(0, '.')
from audit_pipeline import _dispatch_pool_audit
DERIVERS = [pathlib.Path(p) for p in [
    'scripts/kilo-benchmarks/derive_cheapest_gateway.py',
    'scripts/kilo-benchmarks/classify_ai_category.py',
    'scripts/kilo-benchmarks/role_mapper.py',
]]  # sub-cohort smoke — 3 of 7
rows = _dispatch_pool_audit(DERIVERS, task='deriver audit', task_type='review')
assert len(rows) == 3
print('B.2 sub-cohort gate OK')
"
```

**B.3 — Emit findings + inline CONFIRMED fixes + escalate large-scope items.** Same shape as Phase A.5.

**B.4 — Doc-sync + review + commit.** Same closing sequence as Phase A.6 — including `/fabrik-review` on Phase B's diff (LOOP until zero CONFIRMED / PLAUSIBLE) — no exceptions.

---

## Phase C — Aggregator / ranker audit (7 rankers, parallel fan-out)

**Goal.** For each of the 7 rankers (`rank_coding_subagents`, `rank_task_subagents`, `rank_tts`, `rank_stt`, `rank_translation`, `rank_image_gen`, `rank_candidate_signups`), verify: (a) tier / filter contracts hold — `rank_coding_subagents` MUST produce `### code` + `### code-onrequest` with ≤ $1.5/Mtok in the former (per `.windsurf/rules/core/62-using-subagents.md § Approved pool models`); (b) Pareto correctness — a row surfaced in the emitted MD is not dominated on (lower cost, higher quality) by another row in the same table; (c) header contract — every emitted MD has the correct `Last refresh: YYYY-MM-DD` / `Generated: YYYY-MM-DD` header shape the reader (`libs/subagents/select.py:load_task_ranking`) expects; (d) row-count sanity — emitted rows ≤ DB rows that pass the filter.

### Interfaces

**Consumes from Phase B:**

- `_dispatch_pool_audit`, `_render_findings_md` from `scripts/kilo-benchmarks/audit_pipeline.py`.

**Produces:**

- **File** `docs/development/audits/phase-c-aggregator-findings.md` — one row per ranker with columns: `ranker | tier-contract | pareto-correct | header-contract | row-count-sane | severity | summary | fix-commit`.
- **Function** `_verify_tier_split(md_path: Path) -> tuple[int, int]` in `audit_pipeline.py` — returns `(auto_rows_with_out_M_gt_1_5, onrequest_rows_with_out_M_le_1_5)`. Both must be `0` for the tier contract to hold.

### Subagent Mandates (Phase C is parallelizable — 7 independent rankers)

**Pool-default.** Fan out **7 pool subagents (one per ranker)**. Each subagent inlines the ranker source + its emitted MD.

### Steps

**C.1 — TDD: highest-risk tier-contract regression test FIRST** (`scripts/kilo-benchmarks/tests/test_audit_ranker_tier_split.py`).

The risky path: a future edit to `rank_coding_subagents._render` that promotes a > $1.5/Mtok row into `### code`. This test catches the regression on the LIVE emitted doc.

```python
def test_live_coding_selection_tier_split_holds():
    """Verify docs/reference/kilo/CODING_SUBAGENT_SELECTION.md — every row under
    `### code` has Out $/M ≤ 1.5; every row under `### code-onrequest` has > 1.5.
    """
    import sys
    sys.path.insert(0, "scripts/kilo-benchmarks")
    from audit_pipeline import _verify_tier_split
    from pathlib import Path
    auto_violations, onreq_violations = _verify_tier_split(
        Path("docs/reference/kilo/CODING_SUBAGENT_SELECTION.md")
    )
    assert auto_violations == 0, f"{auto_violations} rows in `### code` have Out $/M > $1.5 — tier split broken"
    assert onreq_violations == 0, f"{onreq_violations} rows in `### code-onrequest` have Out $/M ≤ $1.5 — misplaced Auto row"
```

**Gate C.1 (must PASS — live doc is tier-clean per the 2026-07-08 tier-split ship at `b70bb29f`):**

```bash
cd scripts/kilo-benchmarks && python -m pytest tests/test_audit_ranker_tier_split.py -x 2>&1 | tail -5
# Expected: 1 passed
```

**C.2 — Dispatch 7 pool subagents in a single message.** Each subagent inlines: (a) the ranker source, (b) the emitted `docs/reference/kilo/<X>_SELECTION.md`, (c) the DB SELECT that produces the source rows.

**Gate C.2:**

```bash
python -c "
import sys, pathlib
sys.path.insert(0, 'scripts/kilo-benchmarks')
sys.path.insert(0, '.')
from audit_pipeline import _dispatch_pool_audit
RANKERS = [pathlib.Path(p) for p in [
    'scripts/kilo-benchmarks/rank_coding_subagents.py',
    'scripts/kilo-benchmarks/rank_task_subagents.py',
    'scripts/kilo-benchmarks/rank_tts.py',
]]  # sub-cohort
rows = _dispatch_pool_audit(RANKERS, task='ranker audit', task_type='review')
assert len(rows) == 3
print('C.2 sub-cohort gate OK')
"
```

**C.3 — Emit findings + inline CONFIRMED fixes + escalate large-scope items.** Same shape as Phase A.5.

**C.4 — Doc-sync + review + commit.** Same closing sequence as Phase A.6 including `/fabrik-review` LOOP.

---

## Phase D — Emitter audit (docs + browser, parallel fan-out)

**Goal.** For each emitted artifact: (a) hand-authored docs (`AI_VENDOR_ACCESS.md`, `BENCHMARK_SOURCES.md`, `KILO_AGENT_NAMING.md`, `KILO_CLI_REFERENCE.md`, `KILO_MODEL_SELECTION.md`) — verify referenced scripts / DB tables actually exist; (b) auto-generated docs (`KILO_AGENT_SELECTION_GUIDE.md`, `KILO_MODEL_CAPABILITIES.md`, `CODING_SUBAGENT_SELECTION.md`, `TASK_SUBAGENT_SELECTION.md`, `TTS/STT/TRANSLATION/IMAGE_GEN_SELECTION.md`, `CANDIDATE_SIGNUPS.md`) — verify freshness (header date ≥ 7 days) + row counts match DB + no invalid model IDs; (c) `models_browser.html` — verify all 11 tabs render, altTbody swap works, filter/sort correct, no JS errors on load.

### Interfaces

**Consumes from Phase C:**

- `_dispatch_pool_audit`, `_render_findings_md`, `_verify_tier_split` from `audit_pipeline.py`.

**Produces:**

- **File** `docs/development/audits/phase-d-emitter-findings.md` — one row per artifact with columns: `artifact | referenced-code-exists | fresh | row-count-matches-db | no-invalid-ids | severity | summary | fix-commit`.
- **File** `docs/development/audits/phase-d-browser-findings.md` — one row per browser tab (11 tabs) with columns: `tab | renders | column-visibility-correct | row-count | filter-works | sort-works | severity | summary | fix-commit`.

### Subagent Mandates (Phase D is parallelizable — 14 doc artifacts + 11 browser tabs = 25 units)

**Pool-default.** Two parallel fan-outs:

1. **Doc-audit fan-out** (14 subagents, one per emitted doc). Each subagent inlines the doc file (or a `head -100 tail -50` slice if too large) + the emitter source + the DB `SELECT COUNT(*) FROM <source-table> WHERE <filter>`.
2. **Browser-tab audit fan-out** — HEADFULL browser probe requires the **native `fabrik-gui` Task subagent** (Playwright MCP screenshot + tab-click + JS-console read), NOT the pool. Dispatch 1 native `fabrik-gui` subagent that visits every one of the 11 tabs in the emitted `models_browser.html` and reports per-tab findings. (The pool has no browser MCP equivalent per `62-using-subagents.md § NEVER route to the pool`.)

### Steps

**D.1 — TDD: highest-risk "emitted doc row count matches DB" test FIRST** (`scripts/kilo-benchmarks/tests/test_audit_emitter_row_counts.py`).

The risky path: an emitter that drops rows silently (e.g. `_atomic_write` fails partway, or a filter regex loses a decimal). Snapshot-check `TTS_SELECTION.md` row count vs `SELECT COUNT(*) FROM agents WHERE service_type='tts' AND reachable_with_existing_keys=1 AND status='active'`.

```python
def test_tts_selection_row_count_matches_db():
    import sqlite3
    from pathlib import Path
    md = Path("docs/reference/kilo/TTS_SELECTION.md")
    if not md.exists():
        return  # emitter never ran on this checkout; skip is a valid audit signal
    text = md.read_text()
    # Table rows start with "| " and lead with a decimal rank.
    md_rows = sum(1 for line in text.splitlines()
                  if line.startswith("| ") and line.strip().strip("|").split("|")[0].strip().isdecimal())
    conn = sqlite3.connect("scripts/kilo-benchmarks/kilo_agents.db")
    try:
        db_count = conn.execute(
            "SELECT COUNT(*) FROM agents WHERE service_type='tts' "
            "AND reachable_with_existing_keys=1 AND status='active'"
        ).fetchone()[0]
    finally:
        conn.close()
    # The emitted doc caps at top-10 (per rank_tts.py). Not equality; ≤ 10 AND ≤ db_count.
    assert md_rows <= 10, f"TTS_SELECTION.md has {md_rows} rows (>10 cap violated)"
    assert md_rows <= db_count, f"TTS_SELECTION.md has {md_rows} rows but DB only has {db_count} accessible TTS rows"
```

**Gate D.1:**

```bash
cd scripts/kilo-benchmarks && python -m pytest tests/test_audit_emitter_row_counts.py -x 2>&1 | tail -5
# Expected: 1 passed
```

**D.2 — Dispatch 14 pool subagents (doc audit) in a single message.**

**Gate D.2:**

```bash
python -c "
import sys, pathlib
sys.path.insert(0, 'scripts/kilo-benchmarks')
sys.path.insert(0, '.')
from audit_pipeline import _dispatch_pool_audit
DOCS = [pathlib.Path(p) for p in [
    'docs/reference/kilo/AI_VENDOR_ACCESS.md',
    'docs/reference/kilo/CODING_SUBAGENT_SELECTION.md',
    'docs/reference/kilo/TTS_SELECTION.md',
]]  # sub-cohort
rows = _dispatch_pool_audit(DOCS, task='doc emitter audit', task_type='docs')
assert len(rows) == 3
print('D.2 sub-cohort gate OK')
"
```

**D.3 — Dispatch 1 native `fabrik-gui` subagent (browser tab probe).** The `fabrik-gui` agent (per `62-using-subagents.md § Which subagent_type per command`) has browser MCPs (Playwright); pool workers do NOT. Assignment: visit `file:///opt/fabrik/scripts/kilo-benchmarks/models_browser.html` in a headless Chromium (Playwright MCP `browser_navigate`); click each of the 11 tab chips in order (`overview`, `reasoning`, `coding`, `translation`, `transcription`, `voice`, `image`, `video`, `ocr`, `rent-gpu`, `candidates`); for each: (a) screenshot at 1440px; (b) read console messages; (c) count visible `<tr>` in the active `<tbody>`; (d) verify default sort column matches `TAB_DEFAULTS`; (e) exercise 1 filter chip + verify row count decreases; (f) click 1 column header and verify sort direction toggles. Return findings as `phase-d-browser-findings.md`.

**Gate D.3:**

```bash
test -f docs/development/audits/phase-d-browser-findings.md && \
  grep -cE "^\| " docs/development/audits/phase-d-browser-findings.md | awk '$1 >= 11 { print "browser tab rows OK:", $1; exit 0 } { print "TOO FEW rows:", $1; exit 1 }'
# Expected: browser tab rows OK: 11 (or 12 if header counted)
```

**D.4 — Emit findings + inline CONFIRMED fixes + escalate large-scope items.**

**D.5 — Doc-sync + review + commit.** Same closing sequence as A.6.

---

## Phase E — Cross-consistency audit (serial — depends on Phases A/B/C/D data)

**Goal.** Three-way consistency check across the pipeline artifacts:

1. **DB ↔ emitted docs.** For each ranker's emitted `<X>_SELECTION.md`, verify EVERY listed model id EXISTS in `agents` (or `gpu_providers` for `CANDIDATE_SIGNUPS.md`) with matching `status='active'` and the source filter (e.g. `reachable_with_existing_keys=1`). Every model in DB that would qualify but is MISSING from the doc is a bug too (top-N truncation is fine; unexpected drop is not).
2. **Emitted docs ↔ browser.** For each emitted doc row, verify the SAME `agents.id` appears in the browser's JSON payload. If a doc says a model is in the "top 5" but the browser JSON's `agents` list doesn't have it, it's a bug.
3. **Doc ↔ doc.** For every `agents.id` that appears in ≥ 2 emitted docs (e.g. `google/gemini-3-pro-image` in both `IMAGE_GEN_SELECTION.md` and `TASK_SUBAGENT_SELECTION.md`), verify the emitted `In $/M`, `Out $/M`, `quality_elo`, `Ctx`, `SWE` columns AGREE. Disagreement means one deriver has drifted; escalate.

### Interfaces

**Consumes from Phases A/B/C/D:**

- `docs/development/audits/phase-a-ingestor-findings.md`, `phase-b-derivation-findings.md`, `phase-c-aggregator-findings.md`, `phase-d-emitter-findings.md`, `phase-d-browser-findings.md`.
- `_load_findings_generic` from `audit_pipeline.py`.

**Produces:**

- **File** `docs/development/audits/phase-e-cross-consistency-findings.md` — one row per (source1, source2, id) mismatch triple with columns: `source1 | source2 | model_id | field | source1_value | source2_value | severity | summary | fix-commit`.

### Subagent Mandates (Phase E — sequential + 1 pool subagent for the cross-check itself)

Serial after A-D. The cross-check itself is 1 pool subagent's worth of work: dispatch 1 `run_agents` call with `task_type = "review"`. The subagent's task inlines: (a) the 4 findings MDs, (b) the DB SELECTs for every emitted doc's source rows, (c) the browser JSON payload (base64-encoded slice). It returns the mismatch triples as one MD table.

### Steps

**E.1 — TDD: highest-risk 3-way ID consistency test FIRST** (`scripts/kilo-benchmarks/tests/test_audit_cross_consistency.py`).

```python
def test_every_coding_selection_row_exists_in_agents_and_browser():
    """Every model id in CODING_SUBAGENT_SELECTION.md `### code` MUST exist in
    (a) `agents` table with status='active', and (b) the browser JSON payload.
    A gap in either direction is a bug the audit MUST catch."""
    import re, sqlite3, json
    from pathlib import Path
    coding_md = Path("docs/reference/kilo/CODING_SUBAGENT_SELECTION.md").read_text()
    # Extract model ids under `### code` (auto tier only — On-request rows are
    # opt-in by contract, browser doesn't have to list them).
    in_code = False
    ids: list[str] = []
    for line in coding_md.splitlines():
        s = line.strip()
        if s.startswith("### "):
            in_code = (s == "### code")
            continue
        if in_code and s.startswith("| ") and "|" in s.strip("|"):
            cells = [c.strip() for c in s.strip("|").split("|")]
            if len(cells) >= 2 and cells[0].isdecimal():
                m = re.match(r"^`(.+?)`$", cells[1])
                if m: ids.append(m.group(1))
    conn = sqlite3.connect("scripts/kilo-benchmarks/kilo_agents.db")
    try:
        db_ids = {r[0] for r in conn.execute("SELECT id FROM agents WHERE status='active'").fetchall()}
    finally:
        conn.close()
    missing_from_db = [i for i in ids if i not in db_ids]
    assert not missing_from_db, f"IDs in `### code` but missing from agents.active: {missing_from_db}"
    browser = Path("scripts/kilo-benchmarks/models_browser.html").read_text()
    payload_match = re.search(r'<script type="application/json" id="payload">(.+?)</script>', browser, re.S)
    assert payload_match, "browser payload script tag missing"
    payload = json.loads(payload_match.group(1))
    browser_ids = {r["id"] for r in payload.get("chat_models", [])}
    missing_from_browser = [i for i in ids if i not in browser_ids]
    assert not missing_from_browser, f"IDs in `### code` but missing from browser JSON: {missing_from_browser}"
```

**Gate E.1:**

```bash
cd scripts/kilo-benchmarks && python -m pytest tests/test_audit_cross_consistency.py -x 2>&1 | tail -5
# Expected: 1 passed — OR fails with a concrete list of missing IDs (audit finding).
```

**E.2 — Dispatch 1 pool subagent (cross-consistency)** via `run_agents([spec])`. Task inlines the 4 findings MDs + 6 DB SELECTs + browser JSON slice. Returns 1 MD table of mismatch triples.

**Gate E.2:**

```bash
python -c "
import sys, pathlib
sys.path.insert(0, 'scripts/kilo-benchmarks')
sys.path.insert(0, '.')
from audit_pipeline import _dispatch_pool_audit
rows = _dispatch_pool_audit([pathlib.Path('docs/development/audits/phase-a-ingestor-findings.md')], task='cross-consistency smoke', task_type='review')
assert len(rows) == 1
print('E.2 sub-cohort gate OK')
"
```

**E.3 — Emit findings + inline CONFIRMED fixes + escalate large-scope items.**

**E.4 — Doc-sync + review + commit.** Same closing sequence as A.6 — `/fabrik-review` LOOP to no-op.

---

## Phase F — Consolidated audit report + final gate

**Goal.** Produce ONE consolidated audit report `docs/development/audits/2026-07-08-model-pipeline-audit.md` that stitches Phases A-E findings into a single table + severity summary + escalation list. Run the FULL final gate (Tier 2). Update CHANGELOG + INDEX. Flip plan Status to EXECUTED.

### Interfaces

**Consumes from Phases A-E:**

- `docs/development/audits/phase-a-ingestor-findings.md`
- `docs/development/audits/phase-b-derivation-findings.md`
- `docs/development/audits/phase-c-aggregator-findings.md`
- `docs/development/audits/phase-d-emitter-findings.md`
- `docs/development/audits/phase-d-browser-findings.md`
- `docs/development/audits/phase-e-cross-consistency-findings.md`
- `_load_findings_generic` from `audit_pipeline.py`.

**Produces:**

- **File** `docs/development/audits/2026-07-08-model-pipeline-audit.md` — the operator-facing consolidated report. Sections: (1) Summary — total-findings-by-severity table (CONFIRMED / PLAUSIBLE / STYLE / ESCALATE / no-op counts per phase); (2) Findings ledger — every row from every phase MD, with a `phase` column added; (3) Escalation table — every `ESCALATE` row with a proposed follow-up `/fabrik-spec` topic; (4) Coverage — table of pipeline steps audited vs skipped; (5) Reproducibility — the exact commit hash / DB size / GPU providers count / agents active count.
- **Function** `_render_consolidated_report(phase_mds: list[Path], out: Path) -> None` in `audit_pipeline.py`.

### Steps

**F.1 — Assemble the report.** Read the 6 phase MDs; render the consolidated report.

```bash
python -c "
import sys, pathlib
sys.path.insert(0, 'scripts/kilo-benchmarks')
from audit_pipeline import _render_consolidated_report
phase_mds = [pathlib.Path(p) for p in [
    'docs/development/audits/phase-a-ingestor-findings.md',
    'docs/development/audits/phase-b-derivation-findings.md',
    'docs/development/audits/phase-c-aggregator-findings.md',
    'docs/development/audits/phase-d-emitter-findings.md',
    'docs/development/audits/phase-d-browser-findings.md',
    'docs/development/audits/phase-e-cross-consistency-findings.md',
]]
_render_consolidated_report(phase_mds, pathlib.Path('docs/development/audits/2026-07-08-model-pipeline-audit.md'))
print('F.1 report written')
"
```

**F.2 — Update CHANGELOG + INDEX.**

Append to `CHANGELOG.md` under `## [Unreleased]`:

```
### Added — Model-discovery pipeline audit (Phases A-E) + consolidated report (2026-07-08)
Systematic audit of the daily_refresh.sh pipeline (13 ingestors + 7 derivers + 7 rankers + 14 emitted docs + 11 browser tabs). Findings: <N> CONFIRMED fixed inline; <M> ESCALATE'd to follow-up plans; <K> PLAUSIBLE guarded with regression tests. Full report at docs/development/audits/2026-07-08-model-pipeline-audit.md.
```

Append to `INDEX.md` under the kilo-benchmarks section:

```
- `scripts/kilo-benchmarks/audit_pipeline.py` - **Model-discovery pipeline audit helpers.** _dispatch_pool_audit() + _load_findings_generic() + _render_consolidated_report() + _verify_tier_split(). Consumed by the 6 phase MDs at docs/development/audits/phase-{a,b,c,d,e}-*-findings.md and the consolidated docs/development/audits/2026-07-08-model-pipeline-audit.md. Landed 2026-07-08 as Phase A-F of the audit plan.
```

**F.3 — Run `/fabrik-docs-review`** on the audit report + INDEX + CHANGELOG. Fix anything it surfaces.

**F.4 — Run the FULL final gate** (Tier 2, NOT `--lean`):

```bash
python scripts/final_gate.py --json 2>&1 | tail -20
# Expected: {"status": "success", "tier": 2, ...}
```

Fix any failures. **Cross-check the step-8 baseline**: any check that was already-red at the audit's start is a sibling's (not mine); only newly-red is mine.

**F.5 — Run `check_convergence.py`:**

```bash
python scripts/enforcement/check_convergence.py 2>&1 | tail -10
# Expected: no errors on this plan file
```

**F.6 — Doc-sync + review + commit.** Same closing sequence as A.6. `/fabrik-review` LOOP on the consolidated report + `audit_pipeline.py` cumulative diff.

**F.7 — Flip plan Status.** Edit this plan file: `**Status:** IN-PROGRESS` → `**Status:** EXECUTED 2026-07-08 (<commit-sha>)`.

**F.8 — Release scope lock.** Update `.fabrik/plan-locks/2026-07-08-plan-3-model-pipeline-audit.json` → `status:"released"`.

**F.9 — Archive the plan.** `git mv docs/development/plans/2026-07-08-plan-3-model-pipeline-audit.md docs/development/plans/archived/2026-07-08-plan-3-model-pipeline-audit.md`. Repoint the lock's `plan` field to the archive path. Commit with `Agent-Role: orchestrator, Agent-Phase: F, Agent-Context: audit plan EXECUTED — final gate green + report shipped + escalations listed`.

---

## File Scope (owned paths)

This plan owns these files. `/fabrik-execute-plan` will refuse to start if any overlap another active plan-lock.

```
scripts/kilo-benchmarks/audit_pipeline.py                                  [CREATE, Phase A]
scripts/kilo-benchmarks/tests/test_audit_pipeline.py                       [CREATE, Phase A]
scripts/kilo-benchmarks/tests/test_audit_derivation_determinism.py         [CREATE, Phase B]
scripts/kilo-benchmarks/tests/test_audit_ranker_tier_split.py              [CREATE, Phase C]
scripts/kilo-benchmarks/tests/test_audit_emitter_row_counts.py             [CREATE, Phase D]
scripts/kilo-benchmarks/tests/test_audit_cross_consistency.py              [CREATE, Phase E]
docs/development/audits/phase-a-ingestor-findings.md                       [CREATE, Phase A]
docs/development/audits/phase-b-derivation-findings.md                     [CREATE, Phase B]
docs/development/audits/phase-c-aggregator-findings.md                     [CREATE, Phase C]
docs/development/audits/phase-d-emitter-findings.md                        [CREATE, Phase D]
docs/development/audits/phase-d-browser-findings.md                        [CREATE, Phase D]
docs/development/audits/phase-e-cross-consistency-findings.md              [CREATE, Phase E]
docs/development/audits/2026-07-08-model-pipeline-audit.md                 [CREATE, Phase F]
CHANGELOG.md                                                                [APPEND, Phase F]
INDEX.md                                                                    [APPEND, Phase F]
docs/development/plans/2026-07-08-plan-3-model-pipeline-audit.md           [MODIFY Status, Phase F; then git mv → archived/, Phase F.9]
.fabrik/plan-locks/2026-07-08-plan-3-model-pipeline-audit.json             [CREATE, execute-plan step 7; MODIFY status: released, Phase F.8]
```

**Optional writes (only if Phase A.5 / B.3 / C.3 / D.4 / E.3 CONFIRMED findings surface fixable bugs):** individual ingestor / deriver / ranker / emitter source files under `scripts/kilo-benchmarks/**`. Each such write is ≤ 50 LOC and single-file per the Global Constraints; larger fixes are `ESCALATE`d.

**Concurrency check (2026-07-08 — re-verified during Pass 2 of /fabrik-plan-review).** 1 active sibling lock — `2026-07-07-plan-1-sysadmin-claude-rotation.json` (owns `scripts/sysadmin/**`). Previously `2026-07-08-plan-1-subagent-pool-flywheel-enforcement.json` was active (owned `libs/subagents/`) but flipped to `status=released` during review; its scope was disjoint from this plan anyway. This plan's scope is **disjoint from every current or recent lock**; `libs/subagents/` is imported READ-ONLY (never mutated). `CHANGELOG.md` + `INDEX.md` are shared serialization points across all plans; every Phase F commit stages them explicitly and appends (never rewrites `[Unreleased]`).

**Serialization points:** `CHANGELOG.md`, `INDEX.md`.

---

## Evidence

### Phase A evidence
- **`path:line`**: `scripts/kilo-benchmarks/daily_refresh.sh:111-331` — 30+ `_step` invocations verified this turn via `grep -nE '^\s*_step\s*"'`. Ingestor cohort (13) grounded from lines 111, 125, 134, 144, 153, 160, 185, 192, 198, 216, 273, 283, 291, 312, 315, 322.
- **Command output** (this turn):
  ```
  $ sqlite3 scripts/kilo-benchmarks/kilo_agents.db "SELECT COUNT(*) FROM pragma_table_info('agents')"
  87
  $ sqlite3 scripts/kilo-benchmarks/kilo_agents.db "SELECT COUNT(*) FROM agents"
  806
  ```

### Phase B evidence
- **`path:line`**: `scripts/kilo-benchmarks/derive_cheapest_gateway.py:2,64` — reads `gateway_prices` JSON, writes `cheapest_gateway` + `cheapest_gateway_price`. Deriver source of truth for the tier-B determinism test.

### Phase C evidence
- **`path:line`**: `scripts/kilo-benchmarks/rank_coding_subagents.py:86` — `AUTO_OUTPUT_PRICE_CEILING = 1.5` constant; `libs/subagents/select.py:67` — module `_MAX_POOL_PRICE_PER_MTOK = 1.5` (both must agree per `.windsurf/rules/core/62-using-subagents.md § Approved pool models`).
- **`path:line`**: `docs/reference/kilo/CODING_SUBAGENT_SELECTION.md:13,39` — `### code` header at :13, `### code-onrequest` at :39 (tier split, shipped 2026-07-08 at `b70bb29f`).

### Phase D evidence
- **`path:line`**: `scripts/kilo-benchmarks/models_browser_template.html:660-661` — `data-tab="rent-gpu"` + `data-tab="candidates"` chips landed 2026-07-08 (`8eaf6a95`). `:704-708` — `<tbody id="rows-gpu">` + `<tbody id="rows-candidates">` populated by `export_models_browser.py` at export time. `:935` — `TAB_DEFAULTS` with `altTbody` keys for the 2 new tabs.
- **Command output** (this turn):
  ```
  $ ls docs/reference/kilo/*.md | wc -l
  14
  ```

### Phase E evidence
- **`path:line`**: `libs/subagents/select.py:load_task_ranking` — the reader consumes ranker MDs and scopes rows to level-3 `### <TaskKind>` headers; a mismatch between what the MD says and what the DB has surfaces immediately.
- **`path:line`**: `scripts/kilo-benchmarks/export_models_browser.py:_build_payload` — emits the browser's `chat_models`, `embedding_models`, `gpu_providers`, `candidates` JSON keys the Phase E cross-check joins against.

### Phase F evidence
- **`path:line`**: `scripts/final_gate.py:1` — Tier-2 gate entrypoint (`--check --json` mode; mypy + bandit + semgrep, never `--lean`).
- **`path:line`**: `scripts/enforcement/check_convergence.py:39` — the `PROOF` regex `[\w./-]+\.(?:py|ts|tsx|js|sql|md|csv|ya?ml|sh|json):\d+` that enforces "≥1 file:line citation per phase". Verified via `grep -n "PROOF = re.compile"`.

---

## Self-audit

### Grounding passes run this turn

1. **Pass 1** — read the fabrik-plan-after-chat skill instructions + `select_rules.py` output (19 ACTIVE packs) + `daily_refresh.sh` full step list + DB schema (87 cols on `agents`, 806 rows) + emitted-doc set (14 files) + browser template state (11 tabs, `TAB_DEFAULTS` at :935) + `libs/subagents/` version (canonical `d1928e6`, re-vendored this turn) + concurrency (1 active + 1 recently-released sibling lock, both disjoint).
2. **Pass 2** — structural check: every phase carries `Interfaces` (Consumes + Produces); every phase ends with the same 4-step closing sequence (gate → doc-sync → `/fabrik-review` → commit); Phase A/B/C/D each start with a RED-first TDD test.

### Coverage check ("What we already agreed" ↔ phases)

- Test ingest → Phase A (13 ingestors).
- Test DB writes / derivations → Phase B (7 derivers) + Phase A.3 (writes-tagged column).
- Test rankers → Phase C (7 rankers).
- Test emitted docs → Phase D docs cohort (14 files).
- Test browser GUI → Phase D browser cohort (11 tabs).
- Test cross-consistency (DB↔doc↔GUI) → Phase E.
- Find issues + wrong data + bugs + discrepancies → every phase emits a `severity`-tagged findings MD.
- Fix in-scope small issues inline → Phase A.5 / B.3 / C.3 / D.4 / E.3.
- Escalate large-scope issues → Phase F escalation table with named `/fabrik-spec` topic.
- One consolidated report → Phase F.1 → `docs/development/audits/2026-07-08-model-pipeline-audit.md`.

**No gap found.** Every commitment maps to a phase's step or gate.

### Cross-phase signature consistency

- `_dispatch_pool_audit(scripts: list[Path], task: str, task_type: str = "review") -> list[dict]` — Phase A produces (A.2); Phase B / C / D / E consume identically. ✓
- `_render_findings_md(phase: str, rows: list[dict], out: Path) -> None` — Phase A produces; Phase B / C / D / E consume. ✓
- `_load_findings_generic(path: Path) -> list[dict]` — Phase A produces; Phase F consumes for the consolidated report. ✓
- `_verify_tier_split(md_path: Path) -> tuple[int, int]` — Phase C produces + consumes (test C.1); no downstream consumer. ✓
- `_render_consolidated_report(phase_mds: list[Path], out: Path) -> None` — Phase F produces; no downstream. ✓

### Fixed-point claim

This is a DRAFT. `/fabrik-plan-review` will run the adversarial convergence pass and either flip to CONVERGED or surface remaining issues. Do NOT claim CONVERGED here.

---

## Residual unknowns

### Resolved during this plan

- **Which pipeline steps count as "in scope".** Resolved: 30+ `_step` invocations in `daily_refresh.sh:111-322` grouped into 5 stages (ingest / derive / aggregate / emit / persist); the audit covers all of Ingest+Derive+Aggregate+Emit; Persist (Postgres `subagent_runs`) is covered indirectly via the Phase A/B/C pool-subagent `record_agent_run` dogfood.
- **Whether to use pool subagents or native.** Resolved per `62-using-subagents.md § Dispatch policy`: pool-default for the 13/7/7/14 gradeable review fan-outs; native `fabrik-gui` for the browser tab probe (only surface with a browser MCP).
- **How to score subagent runs into the flywheel.** Resolved: orchestrator (Opus) evaluates each subagent's finding row + calls `record_agent_run(spec, result, quality_score=<0-5>, project="fabrik-hub")` — quality_score = the value the orchestrator assigns based on whether the subagent surfaced a real defect (5) vs a false positive (0-1) vs a no-op review (2-3).

### Still-open (each carries a named resolution step)

1. **`microbench_or_models.py` real-cost re-run.** The audit runs this ingestor in `--limit 0` / dry-run mode by default. If Phase A finds cache-vs-live drift (an ingestor caches stale prices), the CONFIRMED finding needs a real-cost re-run to prove the drift. **Resolution:** operator approval per-step; run `microbench_or_models.py --limit 5` (~ $2 est spend, well under the plan's Global Constraints "no unauthorized money" bar) only after operator green-lights via the audit report.
2. **Native `fabrik-gui` availability.** The Phase D.3 browser probe relies on the `fabrik-gui` native Task subagent — its browser MCPs (Playwright) need to be installed and running on the host. **Resolution:** the pre-flight in `/fabrik-execute-plan` checks Playwright is installed (`python -c "import playwright"`); if absent, Phase D.3 falls back to a curl-based smoke (`curl -s file:///opt/fabrik/scripts/kilo-benchmarks/models_browser.html | grep -cE 'class="tab"'`) which still catches missing chips but NOT JS console errors — flagged as reduced-fidelity gate in the report.
3. **`ESCALATE`-tagged large-scope bugs.** Each such finding names a `/fabrik-spec` topic in the Phase F escalation table; operator decides whether to spec each. **Resolution:** Phase F emits the table; no follow-up plan is written by THIS plan.

---

## Handoff

- `/fabrik-plan-review docs/development/plans/2026-07-08-plan-3-model-pipeline-audit.md` (invoked automatically at the end of this turn) → adversarial grounding to fixed-point → flips `Status: DRAFT` → `Status: CONVERGED`.
- **User approval gate.**
- `/fabrik-execute-plan docs/development/plans/2026-07-08-plan-3-model-pipeline-audit.md` — user-triggered, runs Phase A → B → C → D → E → F autonomously with per-phase `/fabrik-review` gates + pool-flywheel `record_agent_run` per subagent dispatch.

**Expected spend:** ~$0 for the pool subagents (models under $1.5/Mtok output cap; total input ≈ 100 KB × 42 subagents; total est. cost $0.30–$0.80). Real-money `microbench_or_models.py` re-run (Residual #1) only if operator approves.

**Expected wall clock:** Phase A/B/C/D parallel fan-outs cut each phase to the slowest single subagent (~30-60s per pool worker). Total ~15-30 minutes for A+B+C+D; +10-20 min for E's cross-check; +5-10 min for F's report + gate. Total 30-60 minutes end-to-end.
