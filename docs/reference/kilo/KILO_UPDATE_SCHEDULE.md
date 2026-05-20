# Kilo Agent Update Pipeline

**Last Updated:** 2026-05-20

How the model catalog, benchmarks, role assignments, and agent scripts stay current.

---

## Automated (daily — WSL startup)

```bash
# Triggered by scripts/kilo_model_sync_startup.sh (runs once per day on WSL boot)
# Added to ~/.bashrc or systemd user service

python3 scripts/kilo_model_sync.py --sync
```

**What it does:**
- Syncs model catalog from Kilo Gateway
- Updates pricing, context windows, capabilities
- Runs once per day (skips if already ran today via `.kilo_sync_last_run` check)
- Lock file prevents concurrent runs
- Logs to `.droid/kilo_model_sync.log`

---

## Manual Full Refresh

When you need to rebuild everything (new models, benchmark changes, role rebalancing):

```bash
cd /opt/fabrik

# 1. Discover models from Kilo Gateway (requires /usr/local/bin/kilo)
PATH=/usr/local/bin:$PATH python3 scripts/kilo-benchmarks/discover_kilo_agents.py

# 2. Scrape benchmark leaderboards (Arena ELO + TBench accuracy)
python3 scripts/kilo-benchmarks/update_kilo_benchmarks.py

# 3. Recompute role assignments (cheapest model above quality floors)
python3 scripts/kilo-benchmarks/compute_assignments.py

# 4. Regenerate agent scripts + auto-update docs
python3 scripts/generate_kilo_agents.py
#   → writes ~/.traycer/cli-agents/*.sh
#   → updates KILO_AGENT_SELECTION_GUIDE.md roster
#   → regenerates KILO_MODEL_CAPABILITIES.md
```

---

## What Each Step Updates

| Step | Script | Updates | Frequency |
|---|---|---|---|
| Model sync | `kilo_model_sync.py` | Pricing, context windows, capabilities in DB | Daily (auto) |
| Gateway discovery | `discover_kilo_agents.py` | Full model list from Kilo Gateway → `kilo_all_agents.json` | On demand |
| Benchmark scrape | `update_kilo_benchmarks.py` | Arena ELO, TBench accuracy in DB | On demand |
| Role assignment | `compute_assignments.py` | `agent_roles` table, `assignments.json` | On demand |
| Script generation | `generate_kilo_agents.py` | `~/.traycer/cli-agents/*.sh`, selection guide roster, model capabilities doc | On demand |
| Registry export | `export_traycer_registry.py` | `kilo_47_agents_final.json` (live Traycer registry) | After role_mapper.py |

---

## When to Run What

| Trigger | Run |
|---|---|
| WSL boot (daily) | Automatic — `kilo_model_sync_startup.sh` handles it |
| New major model release (GPT-6, Claude 5, etc.) | Full refresh (steps 1-4) |
| Benchmark leaderboard shift (>5% ELO change) | Steps 2-4 |
| Model blocked for poor performance | `manage_blocked.py block "agent/id" "reason"` → step 3-4 |
| Price change by provider | Step 1 (if in Gateway) or manual DB update |
| Agent scripts look wrong | Step 4 only (`generate_kilo_agents.py`) |
| Docs out of date | Step 4 (auto-updates selection guide + capabilities) |

---

## Benchmark Sources

| Source | What it provides | Scraper |
|---|---|---|
| [Chatbot Arena](https://openlm.ai/chatbot-arena/) | Arena ELO (user preference ranking) | `scrape_artificial_analysis.py` |
| [Terminal-Bench](https://www.tbench.ai/leaderboard/terminal-bench/2.0) | TBench accuracy (CLI coding performance) | `scrape_benchlm.py` |
| [Kilo Gateway](https://kilo.ai/models) | Model catalog, pricing, capabilities | `discover_kilo_agents.py` |
| [Windsurf models](https://docs.windsurf.com) | Windsurf-specific model data | `scrape_windsurf_models.py` |

---

## Monitoring

```bash
# Check when DB was last updated
stat -c '%y' scripts/kilo-benchmarks/kilo_agents.db

# Check when sync last ran
cat .droid/.kilo_sync_last_run

# Check sync log
tail -20 .droid/kilo_model_sync.log

# Check benchmark scrape log
tail -20 scripts/kilo-benchmarks/cache/update.log

# Verify agent health
bash scripts/kilo_agent_health.sh
```

**Staleness check:** If `kilo_agents.db` modification date is >48 hours old, the daily sync isn't running. Check `kilo_model_sync_startup.sh` in `~/.bashrc`.

---

## Data Files

| File | Purpose | Freshness |
|---|---|---|
| `scripts/kilo-benchmarks/kilo_agents.db` | **Authoritative** — all models, pricing, benchmarks, roles | Daily (auto-sync) |
| `scripts/kilo-benchmarks/kilo_all_agents.json` | JSON export from Gateway | On `discover_kilo_agents.py` run |
| `scripts/kilo-benchmarks/assignments.json` | Current role → model mapping | On `compute_assignments.py` run |
| `scripts/kilo-benchmarks/role_configs.yaml` | Role definitions, quality floors, cost caps | Manual (rarely changes) |
| `scripts/kilo_47_agents_final.json` | Traycer registry (consumed by Windsurf) | On `export_traycer_registry.py` run |
| `~/.traycer/cli-agents/*.sh` | Agent scripts (consumed by Traycer) | On `generate_kilo_agents.py` run |

---

## See Also

- [KILO_AGENT_SELECTION_GUIDE.md](KILO_AGENT_SELECTION_GUIDE.md) — Selection philosophy, current roster, blocking
- [KILO_AGENT_NAMING.md](KILO_AGENT_NAMING.md) — Script naming convention
- [KILO_MODEL_CAPABILITIES.md](KILO_MODEL_CAPABILITIES.md) — Full model catalog (auto-generated)
