# Kilo Agent Benchmark Workflow

**Status:** ENABLED — runs by default in the WSL daily startup pipeline.
**Last Updated:** 2026-07-20 (reconciled the "OpenRouter category routing" table + Files Involved against the live `wsl_startup_hook.sh` — 6 gateway/pricing scripts were undocumented)

This workflow keeps the Traycer CLI agent fleet in sync with current model
benchmark data and assigns each model to a role using a **deterministic Pareto
optimizer** — no LLM, no model calls, ~50 ms, $0, byte-identical on re-run.
It runs once per WSL boot day as part of `wsl_startup_hook.sh` (sourced from
`~/.bashrc`).

> History note: from May 3–May 9 2026 the role-assignment step called the Kilo
> CLI (an LLM) and intermittently hung, so the workflow was disabled. On
> 2026-05-13 the LLM step was replaced with the deterministic algorithm
> described here and the workflow was re-enabled by default. See **History**
> at the bottom.

## What it does

The daily pipeline (`wsl_startup_hook.sh`, step 5) runs two sibling pipelines.

### Chat-model pipeline (the core workflow)

| # | Script (`scripts/kilo-benchmarks/` unless noted) | Purpose |
|---|---|---|
| 5a | `kilo_agents_db.py all` | Rebuild the agent SQLite catalog (`kilo_agents.db`) from the Kilo/OpenRouter model catalog + Ollama. |
| 5b | `update_kilo_benchmarks.py --force` | Scrape Arena ELO (openlm.ai) + Terminal-Bench (tbench.ai) + Windsurf models; update catalog scores. |
| 5c | `scrape_artificial_analysis.py` | Scrape throughput (tokens/sec) + TTFT from artificialanalysis.ai; fill `output_tokens_per_sec`. |
| 5d | `role_mapper.py` | **Deterministic** role assignment: `pre_filter → selector → post_filter → DB`. No LLM. |
| 5e | `export_traycer_registry.py` | Refresh `scripts/kilo_47_agents_final.json` from the new `agent_roles` table. |
| 5f | `generate_kilo_agents.py` (in `scripts/`) | Emit per-agent Traycer CLI wrapper scripts into `~/.traycer/cli-agents/`. |

`role_mapper.py` already runs `export_traycer_registry.py` inline after writing
assignments, so step 5e is belt-and-suspenders to keep the JSON registry from
ever drifting from the DB.

### Embedding pipeline (sibling, runs after the chat block)

Mirrors the chat pipeline shape for embedding models. It runs in its own `&&`
chain so a broken embeddings catalog cannot kill the chat workflow above.

| Script (`scripts/kilo-benchmarks/`) | Purpose |
|---|---|
| `embedding_models_db.py all` | Scrape OpenRouter embeddings catalog into the embedding tables. |
| `embedding_pre_filter.py` | Per-role embedding shortlists → `embedding_shortlists.json`. |
| `embedding_role_mapper.py` | Deterministic winners per role → `embedding_roles` table + `embedding_assignments.json` / `kilo_embeddings_final.json`. |
| `embedding_export_markdown.py` | Marker-based update of the embedding sections in `KILO_AGENT_SELECTION_GUIDE.md` and `KILO_MODEL_CAPABILITIES.md`. |

The output is a working Traycer CLI agent fleet — each generated wrapper invokes
the right model with the right role-specific prompt.

### OpenRouter category routing (sibling, daily)

After the chat + embedding pipelines complete (and before the freshness check),
**9 scripts** run in its own subshell (`scripts/wsl_startup_hook.sh:126-157`) and
inject per-category model picks into the 7 LLM-bearing
`.windsurf/rules/ai/NN-*.md` packs, plus refresh gateway/pricing data consumed
by the models browser:

| Order | Script | What it does |
|---|---|---|
| 1 | `verify_openrouter_catalog.py --apply --ingest-new` | Verifies pricing/capabilities against the LIVE OpenRouter API, auto-fixes discrepancies, marks delisted rows deprecated, ingests new ones. Runs FIRST so the classifier below sees the corrected catalog. |
| 2 | `classify_ai_category.py` | Pure-SQL classifier tags every active model in `agents` against the 7 LLM-bearing packs and writes rows to `agent_categories` (PK `(agent_id, category)`). Multi-category by design — a model that's strong for code AND long-context gets two rows. |
| 3 | `category_route_mapper.py` | For each category in `ai_category_configs.yaml`, calls `category_selector.py` to pick the top-N by configured `sort_key` + floors. Writes pins to `agent_roles` with `role='openrouter:{category}'` + today's snapshot to `agent_roles_history`. Emits `openrouter_routes.json` (full detail) + `kilo_openrouter_routes_final.json` (Traycer-shaped compact form). |
| 4 | `category_export_markdown.py` | Self-heal injection of `<!-- OPENROUTER_ROUTES:START/END -->` marker blocks into each pack + atomic refresh of the `Last content verification: YYYY-MM-DD` stamp. Mirror of `embedding_export_markdown.py:209-247`. |
| 5 | `update_gateway_counts.py` | Injects live gateway counts (how many providers serve each model) into the exported data. |
| 6 | `fetch_replicate_prices.py` | Fetches Replicate pricing for models routed through that gateway. |
| 7 | `fetch_fal_prices.py` | Fetches fal.ai pricing — **conditional on `$FAL_KEY`** being set in the environment; skipped otherwise. |
| 8 | `derive_cheapest_gateway.py` | Derives the cheapest gateway per model across the fetched price sources. |
| 9 | `export_models_browser.py` | Exports the consolidated models-browser data file used by the OpenRouter models browser UI. |

Steps 1-4 are the pack-routing core (documented in the plan below); steps 5-9
are gateway/pricing enrichment added afterward and were previously undocumented
here — reconciled 2026-07-20 against the live `wsl_startup_hook.sh`.

The 7 categories (per `ai_category_configs.yaml`):
`language`, `code`, `vision`, `multimodal`, `agentic`, `long-context`, `speech-audio`.

Failure semantics: per-script `|| echo "[openrouter-routing] X failed (non-fatal)" >> $LOG_FILE`
so a crash here does NOT short-circuit the AI pack freshness check or extensions
sync that run after. Operator kill-switch: `touch /tmp/.openrouter_routing_disabled`
(silences the NEXT scheduled run; in-flight runs complete normally).

Output shape in `cache/update.log` on success (per-category counts shown are live 2026-06-27 — actual counts vary with each category's `slots` / `min_quality_tier` / `allow_free` floors in `ai_category_configs.yaml`):

```text
[category_route_mapper] language: 3 routes → [...]
[category_route_mapper] code: 3 routes → [...]
[category_route_mapper] vision: 2 routes → [...]
[category_route_mapper] multimodal: 2 routes → [...]
[category_route_mapper] agentic: 3 routes → [...]
[category_route_mapper] long-context: 2 routes → [...]
[category_route_mapper] speech-audio: 1 routes → [...]
[category_route_mapper] wrote 16 pins across 7 categories (0 skipped)
[category_export_markdown] language: {'status': 'wrote', 'marker': 'replaced', 'stamp': 'replaced'}
...
```

Cross-links:

- Plan: [`docs/development/plans/archived/2026-06-27-plan-openrouter-routing.md`](../development/plans/archived/2026-06-27-plan-openrouter-routing.md)
- Benchmark-source rationale (esp. the `:free` model coverage gap): [`docs/reference/kilo/BENCHMARK_SOURCES.md`](../reference/kilo/BENCHMARK_SOURCES.md) §4.5
- Pack freshness consumer: [`scripts/check_ai_pack_freshness.py`](../../scripts/check_ai_pack_freshness.py) (regex contract at lines 25-26)

### AI rule pack freshness check (sibling, warn-only)

After both chat and embedding pipelines complete, `check_ai_pack_freshness.py`
scans `.windsurf/rules/ai/*.md` and prints warnings to `update.log` for any
pack whose `Last content verification: YYYY-MM-DD` line is older than
**90 days** (override via `AI_PACK_STALE_DAYS=NN`). Unstamped packs are also
reported. The script never modifies pack content — the daily pipeline generates
*data* (model scores, embedding catalogs); AI rule packs encode *policy* (vendor
routing, model lineup) and refresh on model-launch events under human review.

Output shape in `cache/update.log`:

```text
[ai-pack-freshness] 11 packs scanned (threshold: 90d) on 2026-06-27
[ai-pack-freshness] ⚠️  1 STALE pack(s):
  - 00-ai-model-selection.md: verified 95 days ago (>90d threshold) — re-verify model lineup / vendor picks
[ai-pack-freshness] ℹ️  10 unstamped pack(s):
  - 10-speech-audio.md: no `Last content verification:` line — consider stamping to track refresh cadence
  ...
```

> Note: only `00-ai-model-selection.md` carries the canonical `Last content
> verification:` stamp today; the other packs (incl. `25-3d-generation.md`,
> which uses `Last reviewed:`) read as *unstamped* until stamped with the exact
> phrase. The check is warn-only and never gates a commit.

## How role assignment works (deterministic, no LLM)

`role_mapper.py` assigns models to roles
(`coding_simple`, `coding_complex`, `reviewing`, `fixing`, `documentation`,
`testing`) using a three-stage mathematical pipeline:

1. **`pre_filter.py`** — per-role shortlists via hard filters (quality/speed/
   capability gates), narrowing ~117 catalog models to a few dozen candidates.
2. **`selector.py`** — "cheapest above floors": quality and speed are
   constraints, cost is the objective. P1 = cheapest qualified model;
   P2..PN = next-cheapest fallbacks.
3. **`post_filter.py`** — family-diversity rule for the reviewing fleet
   (≥2 providers, ≥1 not in coding P1–P2; max 2 slots per provider).

No model is invoked at any point; the step is pure SQLite + arithmetic and
finishes in roughly 50 ms. Re-runs on unchanged data are byte-identical.

(The current model roster, where named at all, is Opus 4.8 / Sonnet 4.6 /
Haiku 4.5 / Fable 5 — but the optimizer is data-driven and doesn't hardcode a
roster.)

## How to disable it

The workflow is opt-OUT. Set `FABRIK_DISABLE_KILO_WORKFLOW=1` to skip both
pipelines (the rest of the daily pipeline still runs).

```bash
# One-off for the current WSL session:
FABRIK_DISABLE_KILO_WORKFLOW=1 source /opt/fabrik/scripts/wsl_startup_hook.sh

# Permanent — edit ~/.bashrc and export before sourcing:
export FABRIK_DISABLE_KILO_WORKFLOW=1
source /opt/fabrik/scripts/wsl_startup_hook.sh
```

When skipped, the hook logs
`kilo benchmark workflow skipped (FABRIK_DISABLE_KILO_WORKFLOW=1)` to
`update.log`.

## Manual trigger

```bash
/opt/fabrik/scripts/run_kilo_workflow.sh
```

This is a **4-step subset** of the chat pipeline (DB rebuild → benchmark scrape
→ `role_mapper.py` → `generate_kilo_agents.py`); it does not run the AA
throughput scrape, the Traycer-registry export step, or the embedding pipeline
— the daily hook is broader. It wraps `role_mapper.py` in a Linux `timeout`
watchdog (30-minute hard cap); on overrun it `pkill`s any stray processes and
aborts before agent generation. The watchdog is a leftover guardrail from the
old LLM-hang era; the deterministic mapper finishes in well under a second, so
the timeout never fires in practice. Logs to `cache/manual_workflow.log`
(created on first run).

> The inline comments in `run_kilo_workflow.sh` still describe step 3 as
> "AI role assignment via Kilo CLI" — that's stale text; the script invokes the
> current deterministic `role_mapper.py`.

## What also stays enabled in the daily pipeline

Non-kilo steps in `wsl_startup_hook.sh`:

| Step | Script | Purpose |
|---|---|---|
| Env watcher | `watch_env_changes.sh` | Monitors `/opt/*/.env` changes (persistent background process). |
| Project sync | `sync_projects.py` | Updates `data/projects.yaml`, `docs/PROJECT_CATALOG.md` (renamed from `BUSINESS_MODEL.md` 2026-07-11), `PORTS.md`. |
| Cascade backup | `sync_cascade_backup.sh` | Verifies Cascade backup freshness. |
| Health summary | `health_summary.py` | Daily system health snapshot. |
| Extensions sync | `sync_extensions.sh` | Auto-updates Windsurf extensions docs. |

## Files involved

| Path | Role |
|---|---|
| `/opt/fabrik/scripts/wsl_startup_hook.sh` | Daily pipeline; kilo workflow guarded by `FABRIK_DISABLE_KILO_WORKFLOW`. |
| `/opt/fabrik/scripts/wsl_startup_hook.sh.before-kilo-disable` | Backup of the pre-2026-05-09 hook. |
| `/opt/fabrik/scripts/run_kilo_workflow.sh` | Manual trigger (4-step subset) with 30-min watchdog. |
| `/opt/fabrik/engine/role_mapper.py` | Deterministic role assignment orchestrator. |
| `/opt/fabrik/engine/pre_filter.py` | Per-role shortlists (hard filters). |
| `/opt/fabrik/engine/selector.py` | "Cheapest above floors" Pareto selection. |
| `/opt/fabrik/engine/post_filter.py` | Reviewing-fleet family-diversity rule. |
| `/opt/fabrik/engine/kilo_agents_db.py` | Catalog DB rebuild. |
| `/opt/fabrik/engine/update_kilo_benchmarks.py` | Arena ELO + Terminal-Bench + Windsurf scraper. |
| `/opt/fabrik/engine/scrape_artificial_analysis.py` | Throughput + TTFT scraper. |
| `/opt/fabrik/engine/export_traycer_registry.py` | Exports `scripts/kilo_47_agents_final.json` from DB. |
| `/opt/fabrik/engine/embedding_models_db.py` | Embedding catalog scraper. |
| `/opt/fabrik/engine/embedding_pre_filter.py` | Embedding shortlists. |
| `/opt/fabrik/engine/embedding_role_mapper.py` | Embedding role winners. |
| `/opt/fabrik/engine/embedding_export_markdown.py` | Updates embedding doc sections. |
| `/opt/fabrik/scripts/generate_kilo_agents.py` | Generates Traycer CLI wrappers into `~/.traycer/cli-agents/`. |
| `/opt/fabrik/scripts/check_ai_pack_freshness.py` | Warn-only: flags `.windsurf/rules/ai/*.md` packs whose `Last content verification:` line is >90d old (`AI_PACK_STALE_DAYS` override). Never modifies packs. |
| `/opt/fabrik/engine/verify_openrouter_catalog.py` | Verifies pricing/capabilities vs the live OpenRouter API before category routing runs. |
| `/opt/fabrik/engine/classify_ai_category.py` | Pure-SQL classifier, models → the 7 categories. |
| `/opt/fabrik/engine/category_route_mapper.py` | Per-category top-N selection → `agent_roles` pins. |
| `/opt/fabrik/engine/category_export_markdown.py` | Injects `OPENROUTER_ROUTES` markers into the 7 packs. |
| `/opt/fabrik/scripts/kilo-benchmarks/update_gateway_counts.py` | Injects gateway counts into exported routing data. |
| `/opt/fabrik/engine/fetch_replicate_prices.py` | Fetches Replicate pricing. |
| `/opt/fabrik/engine/fetch_fal_prices.py` | Fetches fal.ai pricing (conditional on `$FAL_KEY`). |
| `/opt/fabrik/engine/derive_cheapest_gateway.py` | Derives cheapest gateway per model. |
| `/opt/fabrik/engine/export_models_browser.py` | Exports the consolidated models-browser data file. |
| `/opt/fabrik/scripts/kilo-benchmarks/cache/update.log` | Daily pipeline log. |
| `/opt/fabrik/scripts/kilo-benchmarks/cache/manual_workflow.log` | Manual trigger log (created on first manual run). |

## Diagnostics

```bash
# Daily pipeline status (look for matched start/complete markers)
tail -100 /opt/fabrik/scripts/kilo-benchmarks/cache/update.log

# Current role assignments
/opt/fabrik/.venv/bin/python /opt/fabrik/engine/role_mapper.py --show

# Preview assignments without writing the DB
/opt/fabrik/.venv/bin/python /opt/fabrik/engine/role_mapper.py --dry-run
```

A healthy daily run writes a
`=== Fabrik Daily Pipeline — <DATE> ===` header followed by a matching
`=== Pipeline complete — <DATE> ===` footer in `update.log`.

## History

- **2026-05-03 – 2026-05-09** — The role-assignment step (`role_mapper.py`)
  called the Kilo CLI (an LLM, max-thinking modes) via `subprocess` and
  intermittently hung past its per-model timeout, leaving stuck pipelines and
  orphan agent processes. The workflow was disabled and a manual trigger with a
  `timeout` watchdog was added as the safe pattern.
- **2026-05-13** — The LLM assignment step was replaced with the deterministic
  Pareto optimizer (`pre_filter → selector → post_filter`). The hang root cause
  no longer exists, so the workflow was **re-enabled by default**, gated by the
  opt-out flag `FABRIK_DISABLE_KILO_WORKFLOW=1`. The 30-min watchdog in
  `run_kilo_workflow.sh` was kept as a harmless leftover.
- **2026-06-16** — Doc rewritten to current state and moved from
  `docs/operations/` to `docs/workflows/`.
