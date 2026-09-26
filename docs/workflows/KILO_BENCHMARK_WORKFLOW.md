# Kilo Benchmark Workflow — the hub's side of the model catalog

**Status:** CONSUMER ONLY. The hub no longer scrapes, scores or ranks models.
**Last Updated:** 2026-09-26 (rewritten from the pre-2026-08-15 producer description, W-0355625c)

The model-catalog pipeline (benchmark scrapes, the `kilo_agents.db` catalog, the deterministic
`role_mapper.py` role assignment, the embedding pipeline, OpenRouter category routing and the
gateway/price fetchers) moved to **`/opt/ai-model-catalog/engine/`** on 2026-08-15 (`73bde59a`).
That repo owns it end to end and documents it in `/opt/ai-model-catalog/docs/OPERATIONS.md`. This page covers
only what the hub still runs, and where to look when the delivered data goes stale.

## Two crons, one hand-off

| When (crontab) | Script | Repo | Role |
|---|---|---|---|
| `0 5 * * *` in the live crontab (2026-09-26); `/opt/ai-model-catalog/docs/RESILIENCE.md` §7 owns the interval and still says `30 5` | `/opt/ai-model-catalog/engine/daily_refresh.sh` | ai-model-catalog | **Producer.** Scrapes, scores, ranks, and writes the catalog and the rendered blocks. Log: `/opt/ai-model-catalog/engine/cache/update.log`. |
| `0 6 * * *` | `scripts/kilo-benchmarks/daily_refresh.sh` | fabrik (hub) | **Consumer.** Pulls the engine's outputs into the hub, re-ranks under hub policy, checks freshness, and syncs the result to the fleet. Log: `scripts/kilo-benchmarks/cache/update.log`. |

The hub cron and the boot hook share one daily lockfile, `/tmp/.fabrik_daily_<UTC date>`. Whichever
runs first that UTC day takes it, and the cron then exits at once with "skipping — already ran today"
(override: `rm /tmp/.fabrik_daily_$(date -u +%Y%m%d)`). So on a day the boot hook wins, none of the
steps below run from the cron.

The hub's steps that touch the catalog, in `daily_refresh.sh` order:

| Step | What it does |
|---|---|
| `deliver_to_fabrik.py --apply` (engine script, run with the engine's venv) | Copies the engine's whole-file docs, injects its marker blocks (`OPENROUTER_ROUTES`, `GATEWAY_COUNTS`, and others) into their host files, including the `.windsurf/rules/ai/*.md` packs and their `Last content verification:` stamp, and copies `kilo_agents.db` into `scripts/kilo-benchmarks/`. That copy is the engine's own SQLite file, frozen since the engine moved to Postgres, because nothing writes the export it looks for first (`deliver_to_fabrik.py` says so beside the fallback). Skipped while the pool evaluation is paused (D-181/D-182). |
| `rank_task_subagents.py` | Re-renders `docs/reference/kilo/TASK_SUBAGENT_SELECTION.md` with the hub's operator deny list and allowlist applied over the delivered ranking. Pages if it fails, because the engine copy carries neither. `daily_refresh.sh` skips it while the pool is paused, but the boot hook re-renders it ungated, so `Last refresh:` keeps moving while the `Evidence age:` line shows the evidence is frozen. |
| `check_ai_pack_freshness.py --delivered-max-age 3` | Exits 1 when any `last-refreshed:` marker in `.windsurf/rules/ai/*.md` (the `GATEWAY_COUNTS` and `OPENROUTER_ROUTES` blocks) is more than 3 days old, or when it finds no marker at all, and the step pages (D-415). Stale blocks have two causes: the engine stopped producing, or the hub skipped delivery because the pool is paused, which has been the case since 2026-09-08. Read the engine log and this log's `POOL EVAL PAUSED` lines before blaming either. The step is not gated on the pause, so it pages daily while paused (W-1a18423a). |
| `tests/capture_golden.py --verify` | The contract oracle. It checks that every artifact and marker the fleet consumes is still produced and not an empty husk. Among other things it snapshots the SQL count queries in the hub's retained `update_gateway_counts.py`. |
| `sync_enforcement_to_projects.py`, then `autocommit_pipeline_outputs.sh` | Distributes governance and the delivered docs to the fleet, then commits the regenerated docs. |

## The boot hook

`scripts/wsl_startup_hook.sh` runs once per WSL boot day. It runs no producer step and never calls
`deliver_to_fabrik`: the six-script Kilo agent workflow it used to run left with the engine, and its
"OpenRouter category routing" block is now a subshell that only `cd`s. It does run the hub ranker
(without the pause gate), the contract oracle, the heartbeat check and the autocommit, under the
shared lockfile above, plus the warn-only pack freshness check below.

### AI rule pack freshness check (warn-only)

`scripts/check_ai_pack_freshness.py` (no flags) scans `.windsurf/rules/ai/*.md` and writes a warning
to `update.log` for any pack whose `Last content verification: YYYY-MM-DD` line is older than
**90 days** (override: `AI_PACK_STALE_DAYS=NN`). It also lists packs that carry no stamp. It never
edits a pack and never gates a commit. In a pack that hosts a delivered routes block, the delivery
rewrites the stamp, so a stale stamp there means delivery stopped (see the two causes above). In any other pack the
stamp is hand-written and records a human re-verification of the model lineup and vendor picks, so
the fix there is a review and a re-stamp. The `--delivered-max-age N` mode above is the direct check
on engine-written blocks.

## Retired (do not look for these)

- `scripts/run_kilo_workflow.sh` (the manual trigger) no longer exists. To re-run the producer, run
  the engine's own `daily_refresh.sh` from `/opt/ai-model-catalog/engine/`.
- `FABRIK_DISABLE_KILO_WORKFLOW` is read by no script. The boot-hook branch it guarded was removed.
- `scripts/generate_kilo_agents.py` (Traycer CLI wrappers) is retired (D-415) and no scheduler runs
  it.

## Diagnostics

```bash
# Did the engine run and deliver? (producer log, then the hub's age check)
tail -100 /opt/ai-model-catalog/engine/cache/update.log
python3 scripts/check_ai_pack_freshness.py --delivered-max-age 3; echo "rc=$?"

# Did the hub consumer run? (look for matched start/complete markers)
tail -100 scripts/kilo-benchmarks/cache/update.log
```

A green hub heartbeat (`check_daily_refresh_freshness.py`) says that the hub's script reached its end
and that the selection doc's `Last refresh:` stamp is recent. Neither says the engine produced fresh
data. For that, read the
`--delivered-max-age` result and the `Evidence age:` line in `TASK_SUBAGENT_SELECTION.md`.

## History

- **2026-05-13**: the LLM-based role assignment was replaced by the deterministic Pareto optimizer
  (`pre_filter → selector → post_filter`).
- **2026-08-15**: the whole producer pipeline moved to `/opt/ai-model-catalog/engine/` (`73bde59a`).
  The hub kept the consumer steps above.
- **2026-09-25**: the remaining Kilo-era daily jobs were retired, and a frozen delivery now pages
  (D-415).
- **2026-09-26**: this page was rewritten to the consumer-only state (W-0355625c).

<!-- BEGIN related-scripts: generated by scripts/render_doc_script_links.py — do not hand-edit -->
## Related scripts

Scripts that declare this document in their `# AFTER-EDIT:` header — editing one of them
means updating this page in the same change. This list is generated from those headers
(`python3 scripts/render_doc_script_links.py`); add the doc to a script's header, not here.

- `scripts/check_ai_pack_freshness.py`
- `scripts/kilo-benchmarks/update_gateway_counts.py`
<!-- END related-scripts -->
