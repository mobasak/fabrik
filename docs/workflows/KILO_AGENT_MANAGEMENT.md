# Kilo Agent Management

**Status:** RETIRED SUBJECT (2026-09-26, W-21f99f3a). The hub runs nothing this page used to describe; the last of it, the retired `kilo_model_sync.py`, was
archived 2026-10-07 to `scripts/archived/` with its 11:59 crontab line removed (mail 01M4AR32) (row below).
The full 1,016-line version is kept in git history: `git show f5cd99172:docs/workflows/KILO_AGENT_MANAGEMENT.md`.

## Where each part went

| Part | Now |
|---|---|
| Catalog sync, benchmark and throughput scrapes, deterministic role assignment (`kilo_agents_db.py`, `update_kilo_benchmarks.py`, `scrape_*`, `role_mapper.py` with `pre_filter`/`selector`/`post_filter`) | `/opt/ai-model-catalog/engine/`, run by its `daily_refresh.sh` (user crontab `0 5 * * *`) since 2026-08-15. The per-role floors, cost caps and fleet sizes live in `engine/role_configs.yaml` and the selection rules in `engine/selector.py` (both the source of truth; that repo's `docs/OPERATIONS.md` only summarises the feed), and the assignments are in the engine's `agent_roles` table, frozen since 2026-08-16 because `role_mapper.py` fails every run (`permission denied for schema public`; ai-model-catalog's to fix) |
| What the hub still consumes from the engine (delivered docs, the ranking, the freshness check) | `docs/workflows/KILO_BENCHMARK_WORKFLOW.md` |
| The boot hook's real steps | `docs/workflows/DATA_SYNC_WORKFLOW.md` |
| Kilo CLI and Traycer CLI agents, `generate_kilo_agents.py` wrappers | Kilo CLI retired 2026-07-19; the Traycer layer retired by D-102 (2026-09-03); `generate_kilo_agents.py` was taken off the scheduler by D-415 |
| `kilo_model_sync.py` | Retired (D-415); archived 2026-10-07 to `scripts/archived/` with its 11:59 crontab line removed (mail 01M4AR32) |
| `kilo_code_review.py` | `scripts/archived/` |

## Archived dead code, and what stays live

`agent_selector.py`, `classify_ticket.py`, `db_models.py`, `kilo_telemetry.py`, `coding-auto.sh`,
`kilo_auto_route.py` and `generate_kilo_agents.py` moved to `scripts/archived/` on 2026-09-27 (W-70653005).
They were kept at the 2026-08-15 extraction only because `kilo_auto_route.py` and `kilo_docs_enforcer.py`
imported the four modules, and both of those were already retired. The retired `kilo_model_sync.py` followed them to
`scripts/archived/` on 2026-10-07, once its crontab line was removed.

`scripts/kilo-benchmarks/kilo_agents.db` stays: it is the engine's delivered snapshot (untracked), and the
ranker `rank_task_subagents.py` reads it (the 06:00 cron in `daily_refresh.sh` skips the ranker while the
pool policy is off, D-181/D-182, but `wsl_startup_hook.sh:256` still runs it on every boot) for quality tiers
and the leaderboards, directly and through `build_task_baselines.py`.
