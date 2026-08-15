#!/bin/bash
# WSL Startup Hook - Daily Fabrik Maintenance
# Source this in ~/.bashrc to run daily updates on WSL startup
#
# Add to ~/.bashrc:
#   source /opt/fabrik/scripts/wsl_startup_hook.sh
#
# Pipeline:
# 1. Env watcher: monitors /opt/*/.env changes → runs audit (violations logged, never writes secrets)
# 2. Project registry sync: project.yaml → data/projects.yaml + PROJECT_CATALOG.md + PORTS.md (daily)
# 3. Cascade backup freshness check (daily)
# 4. Health summary (daily)
# 5. Kilo agent workflow (daily, deterministic — no LLM):
#      a. kilo_agents_db.py all              — sync model catalog from Kilo CLI + Ollama
#      b. update_kilo_benchmarks.py --force  — scrape Arena ELO + Terminal-Bench
#      c. scrape_artificial_analysis.py      — scrape throughput (tokens/sec) + TTFT
#      d. role_mapper.py                     — pre_filter → selector → post_filter → DB
#      e. export_traycer_registry.py         — refresh scripts/kilo_47_agents_final.json from DB
#      f. generate_kilo_agents.py            — emit Traycer CLI agent scripts
# 6. OpenRouter category routing (daily, deterministic): classifies models
#      into the 7 ai/NN-*.md packs, ranks per-category, injects OPENROUTER_ROUTES
#      markers + refreshes 'Last content verification:' stamps. Pure SQL, no
#      LLM, no extra network calls beyond what step 5 already made. Per-script
#      `|| echo "..."` failure isolation: a crash here MUST NOT short-circuit
#      steps 7 or 8. Operator kill-switch: `touch /tmp/.openrouter_routing_disabled`.
# 7. AI rule pack freshness check (warn-only): warns in update.log when any
#      .windsurf/rules/ai/*.md 'Last content verification:' line is >90 days old
# 8. Extensions sync: auto-update Windsurf extensions documentation (daily)
# 9. session-recall incremental index: yesterday's Claude Code sessions into the
#      local search DB (bounded: timeout 600; fail-quiet when Postgres is down)
#
# Full reference: docs/workflows/DATA_SYNC_WORKFLOW.md

FABRIK_ROOT="/opt/fabrik"
VENV_PYTHON="$FABRIK_ROOT/.venv/bin/python"
DB_SCRIPT="$FABRIK_ROOT/scripts/kilo-benchmarks/kilo_agents_db.py"
BENCHMARK_SCRIPT="$FABRIK_ROOT/scripts/kilo-benchmarks/update_kilo_benchmarks.py"
AA_SCRAPER_SCRIPT="$FABRIK_ROOT/scripts/kilo-benchmarks/scrape_artificial_analysis.py"
ROLE_MAPPER_SCRIPT="$FABRIK_ROOT/scripts/kilo-benchmarks/role_mapper.py"
TRAYCER_EXPORT_SCRIPT="$FABRIK_ROOT/scripts/kilo-benchmarks/export_traycer_registry.py"
EMBEDDING_DB_SCRIPT="$FABRIK_ROOT/scripts/kilo-benchmarks/embedding_models_db.py"
EMBEDDING_PREFILTER_SCRIPT="$FABRIK_ROOT/scripts/kilo-benchmarks/embedding_pre_filter.py"
EMBEDDING_MAPPER_SCRIPT="$FABRIK_ROOT/scripts/kilo-benchmarks/embedding_role_mapper.py"
EMBEDDING_MARKDOWN_SCRIPT="$FABRIK_ROOT/scripts/kilo-benchmarks/embedding_export_markdown.py"
AGENT_SCRIPT="$FABRIK_ROOT/scripts/generate_kilo_agents.py"
EXTENSIONS_SCRIPT="$FABRIK_ROOT/scripts/sync_extensions.sh"
ENV_WATCHER_SCRIPT="$FABRIK_ROOT/scripts/watch_env_changes.sh"
ENV_WATCHER_LOG="$FABRIK_ROOT/.tmp/env_watcher.log"
SYNC_PROJECTS_SCRIPT="$FABRIK_ROOT/scripts/sync_projects.py"
CASCADE_BACKUP_SCRIPT="$FABRIK_ROOT/scripts/sync_cascade_backup.sh"
HEALTH_SUMMARY_SCRIPT="$FABRIK_ROOT/scripts/health_summary.py"
AI_PACK_FRESHNESS_SCRIPT="$FABRIK_ROOT/scripts/check_ai_pack_freshness.py"
CATEGORY_CLASSIFIER_SCRIPT="$FABRIK_ROOT/scripts/kilo-benchmarks/classify_ai_category.py"
CATEGORY_MAPPER_SCRIPT="$FABRIK_ROOT/scripts/kilo-benchmarks/category_route_mapper.py"
CATEGORY_MARKDOWN_SCRIPT="$FABRIK_ROOT/scripts/kilo-benchmarks/category_export_markdown.py"
GATEWAY_COUNTS_SCRIPT="$FABRIK_ROOT/scripts/kilo-benchmarks/update_gateway_counts.py"
FETCH_REPLICATE_SCRIPT="$FABRIK_ROOT/scripts/kilo-benchmarks/fetch_replicate_prices.py"
FETCH_FAL_SCRIPT="$FABRIK_ROOT/scripts/kilo-benchmarks/fetch_fal_prices.py"
DERIVE_CHEAPEST_SCRIPT="$FABRIK_ROOT/scripts/kilo-benchmarks/derive_cheapest_gateway.py"
MODELS_BROWSER_SCRIPT="$FABRIK_ROOT/scripts/kilo-benchmarks/export_models_browser.py"
OR_VERIFIER_SCRIPT="$FABRIK_ROOT/scripts/kilo-benchmarks/verify_openrouter_catalog.py"
LOG_FILE="$FABRIK_ROOT/scripts/kilo-benchmarks/cache/update.log"
LOCK_FILE="/tmp/.fabrik_daily_$(date -u +%Y%m%d)"

# --- Log rotation (keep logs under 500KB, 1 backup) ---
MAX_LOG_SIZE=512000  # 500KB
for logfile in "$LOG_FILE" "$ENV_WATCHER_LOG"; do
    if [ -f "$logfile" ] && [ "$(stat -c%s "$logfile" 2>/dev/null || echo 0)" -gt "$MAX_LOG_SIZE" ]; then
        mv "$logfile" "${logfile}.1"
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] Log rotated" > "$logfile"
    fi
done

# --- Persistent process: env watcher (runs continuously, not daily) ---
# Start only if not already running
if ! pgrep -f "watch_env_changes.sh" > /dev/null 2>&1; then
    mkdir -p "$FABRIK_ROOT/.tmp"
    nohup bash "$ENV_WATCHER_SCRIPT" >> "$ENV_WATCHER_LOG" 2>&1 &
fi

# --- Daily pipeline (runs once per WSL boot day) ---
# Run update if not already run today
if [ ! -f "$LOCK_FILE" ]; then
    touch "$LOCK_FILE"
    # ⚠️ Same class as daily_refresh.sh's block-scope hazard, in its line-scope form. Every step
    # below redirects `>> $LOG_FILE`, and a failed redirection SKIPS that command — so an
    # unwritable log makes this whole boot pipeline no-op step by step, including the heartbeat
    # write at the end, with NOT ONE alert reachable (the failure only surfaces on the next
    # boot's freshness check). `mkdir -p` cannot detect it: it returns 0 on an existing but
    # unwritable directory. Probe the real append, and fall back rather than run blind.
    if ! { mkdir -p "$(dirname "$LOG_FILE")" 2>/dev/null && : >>"$LOG_FILE" 2>/dev/null; }; then
        _fallback="/tmp/fabrik_daily_pipeline_$(date -u +%Y%m%d).log"
        echo "[wsl_startup_hook] CRITICAL: $LOG_FILE unwritable — falling back to $_fallback" >&2
        bash "$FABRIK_ROOT/scripts/kilo-benchmarks/pipeline_alert.sh" \
            "wsl_startup_hook.sh: pipeline log unwritable — the boot pipeline would have run blind" \
            "Could not append to $LOG_FILE. Every step of the boot pipeline redirects there, so each would have been skipped individually and the heartbeat never written — with no alert reachable from inside. Falling back to $_fallback for this boot. Investigate disk/permissions now." \
            || true
        if { mkdir -p /tmp 2>/dev/null && : >>"$_fallback" 2>/dev/null; }; then
            LOG_FILE="$_fallback"
        elif : >>/dev/stderr 2>/dev/null; then
            LOG_FILE="/dev/stderr"
        else
            LOG_FILE="/dev/null"
        fi
    fi
    # Run full pipeline in background (chained to ensure order)
    # Project sync → Cascade backup check → Health summary → Kilo agents → Extensions
    nohup bash -c "
        echo '' >> $LOG_FILE
        echo '=== Fabrik Daily Pipeline — '$(date '+%Y-%m-%d %H:%M:%S')' ===' >> $LOG_FILE
        cd $FABRIK_ROOT && $VENV_PYTHON $SYNC_PROJECTS_SCRIPT >> $LOG_FILE 2>&1 && \
        cd $FABRIK_ROOT && bash $CASCADE_BACKUP_SCRIPT >> $LOG_FILE 2>&1 ; \
        cd $FABRIK_ROOT && $VENV_PYTHON $HEALTH_SUMMARY_SCRIPT >> $LOG_FILE 2>&1 ;
        # === KILO AGENT BENCHMARK WORKFLOW ===
        # Deterministic role assignment (pre_filter → selector → post_filter)
        # Runs in ~50ms, $0 cost, byte-identical re-runs
        # Re-enabled 2026-05-13 after switching from LLM to deterministic algorithm
        if [ \"\${FABRIK_DISABLE_KILO_WORKFLOW:-0}\" = \"1\" ]; then
            echo \"[\$(date +%H:%M:%S)] kilo benchmark workflow skipped (FABRIK_DISABLE_KILO_WORKFLOW=1)\" >> $LOG_FILE
        else
            $VENV_PYTHON $DB_SCRIPT all >> $LOG_FILE 2>&1 && \
            $VENV_PYTHON $BENCHMARK_SCRIPT --force >> $LOG_FILE 2>&1 && \
            cd $FABRIK_ROOT/scripts/kilo-benchmarks && $VENV_PYTHON $AA_SCRAPER_SCRIPT >> $LOG_FILE 2>&1 && \
            cd $FABRIK_ROOT/scripts/kilo-benchmarks && $VENV_PYTHON $ROLE_MAPPER_SCRIPT >> $LOG_FILE 2>&1 && \
            cd $FABRIK_ROOT/scripts/kilo-benchmarks && $VENV_PYTHON $TRAYCER_EXPORT_SCRIPT >> $LOG_FILE 2>&1 && \
            cd $FABRIK_ROOT && $VENV_PYTHON $AGENT_SCRIPT >> $LOG_FILE 2>&1
            # === EMBEDDING SELECTION WORKFLOW ===
            # Mirrors the chat pipeline shape: catalog scrape → shortlists → role winners.
            # Independent failure: a broken embeddings catalog must NOT kill the chat
            # workflow above, so this runs in its own && chain after the chat block
            # closes (note the closing 'fi' moves below this section).
            cd $FABRIK_ROOT/scripts/kilo-benchmarks && $VENV_PYTHON $EMBEDDING_DB_SCRIPT all >> $LOG_FILE 2>&1 && \
            cd $FABRIK_ROOT/scripts/kilo-benchmarks && $VENV_PYTHON $EMBEDDING_PREFILTER_SCRIPT >> $LOG_FILE 2>&1 && \
            cd $FABRIK_ROOT/scripts/kilo-benchmarks && $VENV_PYTHON $EMBEDDING_MAPPER_SCRIPT >> $LOG_FILE 2>&1 && \
            cd $FABRIK_ROOT/scripts/kilo-benchmarks && $VENV_PYTHON $EMBEDDING_MARKDOWN_SCRIPT >> $LOG_FILE 2>&1
        fi
        # === OPENROUTER CATEGORY ROUTING ===
        # Reads agents + agent_categories, writes openrouter:{category} pins
        # to agent_roles, then injects OPENROUTER_ROUTES markers into the 7
        # ai/NN-*.md packs. Wrapped in a subshell so a crash here cannot
        # short-circuit the freshness check or extensions sync below.
        # Each step's failure is logged loud + non-fatal — partial run is
        # acceptable per plan §11.1 (1-day staleness OK, watchdog at 2-day).
        # Lockfile semantics (Pass A Finding 3 fix): /tmp/.openrouter_routing_disabled
        # is a kill-switch for the NEXT scheduled run, not the in-flight run.
        # Once the subshell has entered, the three scripts run to completion;
        # killing mid-flight would leave the DB updated but packs stale.
        if [ ! -f /tmp/.openrouter_routing_disabled ]; then
            (
                # Pass A Finding 4 fix: defend against FABRIK_ROOT ever
                # being derived/unset; without this, cd silently no-ops and
                # subsequent scripts run from $HOME with mysterious errors.
                cd $FABRIK_ROOT/scripts/kilo-benchmarks || { echo \"[openrouter-routing] cd failed — skipping\" >> $LOG_FILE; exit 0; }
                # Verify pricing + capabilities against live OpenRouter API,
                # auto-fix discrepancies, mark delisted rows deprecated,
                # ingest new ones. Runs BEFORE the classifier so the
                # downstream selector sees the corrected catalog.
                $VENV_PYTHON $OR_VERIFIER_SCRIPT --apply --ingest-new >> $LOG_FILE 2>&1 \
                    || echo \"[openrouter-routing] OpenRouter verifier failed (non-fatal)\" >> $LOG_FILE
                $VENV_PYTHON $CATEGORY_CLASSIFIER_SCRIPT >> $LOG_FILE 2>&1 \
                    || echo \"[openrouter-routing] classifier failed (non-fatal)\" >> $LOG_FILE
                $VENV_PYTHON $CATEGORY_MAPPER_SCRIPT >> $LOG_FILE 2>&1 \
                    || echo \"[openrouter-routing] mapper failed (non-fatal)\" >> $LOG_FILE
                $VENV_PYTHON $CATEGORY_MARKDOWN_SCRIPT >> $LOG_FILE 2>&1 \
                    || echo \"[openrouter-routing] markdown export failed (non-fatal)\" >> $LOG_FILE
                $VENV_PYTHON $GATEWAY_COUNTS_SCRIPT >> $LOG_FILE 2>&1 \
                    || echo \"[openrouter-routing] gateway counts inject failed (non-fatal)\" >> $LOG_FILE
                $VENV_PYTHON $FETCH_REPLICATE_SCRIPT >> $LOG_FILE 2>&1 \
                    || echo \"[openrouter-routing] replicate price fetch failed (non-fatal)\" >> $LOG_FILE
                if [ -n \"\${FAL_KEY:-}\" ]; then
                    $VENV_PYTHON $FETCH_FAL_SCRIPT >> $LOG_FILE 2>&1 \
                        || echo \"[openrouter-routing] fal price fetch failed (non-fatal)\" >> $LOG_FILE
                fi
                $VENV_PYTHON $DERIVE_CHEAPEST_SCRIPT >> $LOG_FILE 2>&1 \
                    || echo \"[openrouter-routing] cheapest gateway derive failed (non-fatal)\" >> $LOG_FILE
                $VENV_PYTHON $MODELS_BROWSER_SCRIPT >> $LOG_FILE 2>&1 \
                    || echo \"[openrouter-routing] models_browser export failed (non-fatal)\" >> $LOG_FILE
            )
        fi
        # === AI RULE PACK FRESHNESS CHECK (warn-only) ===
        # Reports any .windsurf/rules/ai/*.md pack whose
        # 'Last content verification: YYYY-MM-DD' line is >90 days old.
        # Override threshold: AI_PACK_STALE_DAYS=NN
        $VENV_PYTHON $AI_PACK_FRESHNESS_SCRIPT >> $LOG_FILE 2>&1
        cd $FABRIK_ROOT && bash $EXTENSIONS_SCRIPT >> $LOG_FILE 2>&1
        # Postgres MCP tunnel: local 15432 -> hub postgres-main (mesh-bound 10.99.0.1:5432); idempotent
        pgrep -f "15432:10.99.0.1:5432" >/dev/null || nohup ssh -N -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 -o ServerAliveCountMax=3 -L 15432:10.99.0.1:5432 vps >> $LOG_FILE 2>&1 &
        # Command-corpus drift check: installed ~/.claude/commands vs rendered _sources/_fragments (WARN-only in the daily log)
        python3 $FABRIK_ROOT/commands/assemble_commands.py --check >> $LOG_FILE 2>&1 || echo 'WARN: ~/.claude/commands drifted from /opt/fabrik/commands sources — re-render or reconcile' >> $LOG_FILE
        # session-recall incremental index (fail-quiet; initial heavy ingest already done 2026-07-26)
        cd /opt/session-recall && timeout 600 .venv/bin/python -m ingest.reindex >> $LOG_FILE 2>&1 || echo \"[session-recall] incremental index failed (non-fatal)\" >> $LOG_FILE
        # === STEPS THIS HOOK WAS MISSING (added 2026-08-14) ===
        # Both entry points share /tmp/.fabrik_daily_<UTC>, so whichever wins the race, the
        # other SKIPS ENTIRELY. Measured: 7 'Pipeline complete' runs, 0 'Refresh complete' —
        # a workstation booted after the 06:00 UTC cron always wins, so daily_refresh.sh had
        # not run in the whole log window. Its three exclusive steps therefore never ran
        # either, while THIS hook regenerates the same artifacts. Same order daily_refresh
        # uses: ranker -> contract oracle -> (sync) -> auto-commit.
        # ⚠️ The oracle MUST stay above the auto-commit: that commit matches the
        # governance-sync pre-commit filter (^\.windsurf/rules/), so it fans out to ~46 repos.
        # Committing a husk before verifying it is the exact ordering
        # test_the_oracle_runs_before_the_fleet_sync exists to prevent.
        $VENV_PYTHON $FABRIK_ROOT/scripts/kilo-benchmarks/rank_task_subagents.py >> $LOG_FILE 2>&1 \
            || { echo '[wsl_startup_hook] rank_task_subagents FAILED — previous selection doc KEPT, not overwritten' >> $LOG_FILE; env FABRIK_ROOT=$FABRIK_ROOT bash $FABRIK_ROOT/scripts/kilo-benchmarks/pipeline_alert.sh 'wsl_startup_hook: rank_task_subagents exited non-zero' 'The flywheel read is likely BROKEN (state=error). The previous TASK_SUBAGENT_SELECTION.md was deliberately KEPT rather than overwritten with the failure stub, so the fleet is on yesterday-good, not poisoned. Check the postgres/sudo path on this host.'; }
        ORACLE_REQUIRE_LOCAL_ARTIFACTS=1 $VENV_PYTHON $FABRIK_ROOT/scripts/kilo-benchmarks/tests/capture_golden.py --verify >> $LOG_FILE 2>&1 \
            || { echo '[wsl_startup_hook] contract oracle reported DRIFT or a stale golden — see above' >> $LOG_FILE; env FABRIK_ROOT=$FABRIK_ROOT bash $FABRIK_ROOT/scripts/kilo-benchmarks/pipeline_alert.sh 'wsl_startup_hook: contract oracle reported drift' 'capture_golden.py --verify did not come back clean on the pipeline host. Either an artifact/marker/query the fleet consumes stopped being produced or collapsed to a husk, or the frozen golden predates the observer (exit 2 -> re-run --snapshot). The auto-commit below fleet-syncs .windsurf/rules/**, so treat this as blocking.'; }
        $VENV_PYTHON $FABRIK_ROOT/scripts/kilo-benchmarks/check_daily_refresh_freshness.py >> $LOG_FILE 2>&1 \
            || echo '[wsl_startup_hook] freshness check errored (non-fatal)' >> $LOG_FILE
        # Auto-commit the pipeline's OWN regenerated tracked docs (added 2026-08-14).
        # THIS is the daily-dirt fix: this hook regenerates ~14 tracked files every boot and
        # had no git step at all, so the tree was perpetually dirty for the next agent while
        # daily_refresh.sh (which DOES commit) was wrongly blamed. One shared stage list lives
        # in autocommit_pipeline_outputs.sh — never inline a second copy here.
        bash $FABRIK_ROOT/scripts/kilo-benchmarks/autocommit_pipeline_outputs.sh wsl_startup_hook >> $LOG_FILE 2>&1 \
            || echo '[wsl_startup_hook] auto-commit step errored (non-fatal)' >> $LOG_FILE
        # Heartbeat: record that THIS pipeline completed. Without it the freshness check
        # above reads a stamp only daily_refresh.sh ever writes — and daily_refresh.sh loses
        # the lockfile race and never runs — so a perfectly healthy boot fired a CRITICAL
        # "the refresh pipeline is hanging" alert every single time, poisoning the same
        # Telegram channel the oracle/ranker alerts depend on. Written AFTER the work, so the
        # check above still reads the previous run's value.
        mkdir -p $FABRIK_ROOT/scripts/kilo-benchmarks/cache 2>/dev/null || true
        date -u '+%Y-%m-%dT%H:%M:%S+00:00' > $FABRIK_ROOT/scripts/kilo-benchmarks/cache/daily_refresh_last_success.txt 2>/dev/null \
            || echo '[wsl_startup_hook] heartbeat write FAILED — next boot will alert as stale' >> $LOG_FILE
        echo '=== Pipeline complete — '$(date '+%Y-%m-%d %H:%M:%S')' ===' >> $LOG_FILE
    " &
fi
