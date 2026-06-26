# Kilo Agent Benchmark Workflow

**Status:** ENABLED — runs by default in the WSL daily startup pipeline.
**Last Updated:** 2026-06-16 (rewritten to current deterministic-pipeline reality; moved from docs/operations/ to docs/workflows/ to match the KILO_*_WORKFLOW convention)

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
| Project sync | `sync_projects.py` | Updates `data/projects.yaml`, `BUSINESS_MODEL.md`, `PORTS.md`. |
| Cascade backup | `sync_cascade_backup.sh` | Verifies Cascade backup freshness. |
| Health summary | `health_summary.py` | Daily system health snapshot. |
| Extensions sync | `sync_extensions.sh` | Auto-updates Windsurf extensions docs. |

## Files involved

| Path | Role |
|---|---|
| `/opt/fabrik/scripts/wsl_startup_hook.sh` | Daily pipeline; kilo workflow guarded by `FABRIK_DISABLE_KILO_WORKFLOW`. |
| `/opt/fabrik/scripts/wsl_startup_hook.sh.before-kilo-disable` | Backup of the pre-2026-05-09 hook. |
| `/opt/fabrik/scripts/run_kilo_workflow.sh` | Manual trigger (4-step subset) with 30-min watchdog. |
| `/opt/fabrik/scripts/kilo-benchmarks/role_mapper.py` | Deterministic role assignment orchestrator. |
| `/opt/fabrik/scripts/kilo-benchmarks/pre_filter.py` | Per-role shortlists (hard filters). |
| `/opt/fabrik/scripts/kilo-benchmarks/selector.py` | "Cheapest above floors" Pareto selection. |
| `/opt/fabrik/scripts/kilo-benchmarks/post_filter.py` | Reviewing-fleet family-diversity rule. |
| `/opt/fabrik/scripts/kilo-benchmarks/kilo_agents_db.py` | Catalog DB rebuild. |
| `/opt/fabrik/scripts/kilo-benchmarks/update_kilo_benchmarks.py` | Arena ELO + Terminal-Bench + Windsurf scraper. |
| `/opt/fabrik/scripts/kilo-benchmarks/scrape_artificial_analysis.py` | Throughput + TTFT scraper. |
| `/opt/fabrik/scripts/kilo-benchmarks/export_traycer_registry.py` | Exports `scripts/kilo_47_agents_final.json` from DB. |
| `/opt/fabrik/scripts/kilo-benchmarks/embedding_models_db.py` | Embedding catalog scraper. |
| `/opt/fabrik/scripts/kilo-benchmarks/embedding_pre_filter.py` | Embedding shortlists. |
| `/opt/fabrik/scripts/kilo-benchmarks/embedding_role_mapper.py` | Embedding role winners. |
| `/opt/fabrik/scripts/kilo-benchmarks/embedding_export_markdown.py` | Updates embedding doc sections. |
| `/opt/fabrik/scripts/generate_kilo_agents.py` | Generates Traycer CLI wrappers into `~/.traycer/cli-agents/`. |
| `/opt/fabrik/scripts/check_ai_pack_freshness.py` | Warn-only: flags `.windsurf/rules/ai/*.md` packs whose `Last content verification:` line is >90d old (`AI_PACK_STALE_DAYS` override). Never modifies packs. |
| `/opt/fabrik/scripts/kilo-benchmarks/cache/update.log` | Daily pipeline log. |
| `/opt/fabrik/scripts/kilo-benchmarks/cache/manual_workflow.log` | Manual trigger log (created on first manual run). |

## Diagnostics

```bash
# Daily pipeline status (look for matched start/complete markers)
tail -100 /opt/fabrik/scripts/kilo-benchmarks/cache/update.log

# Current role assignments
/opt/fabrik/.venv/bin/python /opt/fabrik/scripts/kilo-benchmarks/role_mapper.py --show

# Preview assignments without writing the DB
/opt/fabrik/.venv/bin/python /opt/fabrik/scripts/kilo-benchmarks/role_mapper.py --dry-run
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
