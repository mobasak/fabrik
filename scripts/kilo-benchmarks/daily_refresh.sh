#!/bin/bash
# Daily refresh of the AI model catalog. Cron-safe (no PATH assumptions,
# no shell activity required). Runs the full chain:
#   1. verify_openrouter_catalog.py --apply --ingest-new
#        → cross-checks the DB against live OpenRouter + Kilo CLI,
#          fixes prices, marks delisted, ingests new
#   2. classify_ai_category.py
#        → re-classifies all models into the 7 LLM packs
#   3. category_route_mapper.py
#        → re-picks today's openrouter:* route winners + history
#   4. category_export_markdown.py
#        → injects OPENROUTER_ROUTES blocks + freshness stamp into
#          .windsurf/rules/ai/*.md
#   5. update_gateway_counts.py
#        → injects GATEWAY_COUNTS blocks (live per-category gateway
#          counts from kilo_agents.db) into the same packs
#   6. fetch_replicate_prices.py / fetch_fal_prices.py
#        → scrape per-model pricing from aggregators; populate
#          agents.gateway_prices JSON (plan-2-aggregator-pricing.md)
#   7. derive_cheapest_gateway.py
#        → picks the cheapest (gateway, price) per row from
#          gateway_prices + direct price; writes cheapest_gateway +
#          cheapest_gateway_price for the browser to badge
#   8. export_models_browser.py
#        → regenerates the single-file models_browser.html
#
# Each step is wrapped in `|| echo "[step] failed (non-fatal)"` so a
# downstream failure can't short-circuit subsequent steps. Output goes
# to scripts/kilo-benchmarks/cache/update.log.
#
# Install (run once):
#   ( crontab -l 2>/dev/null; echo "0 6 * * * /opt/fabrik/scripts/kilo-benchmarks/daily_refresh.sh" ) | crontab -
#
# Manual run:
#   bash /opt/fabrik/scripts/kilo-benchmarks/daily_refresh.sh

set -u
FABRIK_ROOT="/opt/fabrik"
LOG_FILE="$FABRIK_ROOT/scripts/kilo-benchmarks/cache/update.log"
VENV_PY="$FABRIK_ROOT/.venv/bin/python"
KB="$FABRIK_ROOT/scripts/kilo-benchmarks"

# Make `kilo` CLI visible to cron (cron PATH is minimal).
export PATH="/usr/local/bin:/usr/bin:/bin:$PATH"

# Adversarial-review CRITICAL fix (2026-06-30): cron runs with a clean env,
# so the orchestrator + alerting need /opt/fabrik/.env loaded explicitly.
# Each Python script that needs env vars calls load_dotenv() at module entry
# (Python's dotenv library handles malformed lines like the GMAIL_QUERY value
# with parentheses that would break `source` in bash). Documented here so a
# future change to add a new step understands the convention.

mkdir -p "$(dirname "$LOG_FILE")"
{
  echo ""
  echo "=== Fabrik AI catalog refresh — $(date -u +'%Y-%m-%d %H:%M:%S UTC') ==="

  cd "$KB" || { echo "[daily_refresh] cd failed — aborting"; exit 0; }

  # Lockfile coordination with wsl_startup_hook.sh (the bashrc-sourced
  # path). The 2026-06-28 migration commit (1372325e) CLAIMED both paths
  # would share lockfile semantics — but daily_refresh.sh never had the
  # check. Implemented 2026-06-30: now mirrors the bashrc-hook's
  # /tmp/.fabrik_daily_$(date -u +%Y%m%d) convention. Whichever path
  # fires first (typically cron at 03:00 UTC) wins the day; the other
  # path sees the lockfile and skips. Lockfile name uses UTC date so it
  # rolls over cleanly at 00:00 UTC.
  #
  # Manual override: rm /tmp/.fabrik_daily_$(date -u +%Y%m%d) to re-run
  # within the same UTC day.
  LOCK_FILE="/tmp/.fabrik_daily_$(date -u +%Y%m%d)"
  if [ -f "$LOCK_FILE" ]; then
    echo "[daily_refresh] skipping — already ran today (lockfile $LOCK_FILE exists)"
    echo "=== Skipped at $(date -u +'%Y-%m-%d %H:%M:%S UTC') ==="
    exit 0
  fi
  touch "$LOCK_FILE"

  # Per-step timing wrapper (added 2026-06-30). Calls "$@" with timing instrumentation,
  # returns the wrapped command's exit code so `|| echo "..."` chains still trigger.
  # Output format: [timing] <label>: Ns (exit=<rc>). Total time printed before
  # "=== Refresh complete ===" so log scanners can compute per-step + total.
  _step() {
    local label="$1"; shift
    local t0=$SECONDS
    "$@"
    local rc=$?
    printf '[timing] %s: %ds (exit=%d)\n' "$label" "$((SECONDS - t0))" "$rc"
    return $rc
  }
  T0_TOTAL=$SECONDS


  # Heartbeat: check that yesterday's run actually completed. Fires a
  # critical alert if the last-success timestamp is >36h old. First-run
  # condition is silent. Per Plan §"Phase 5 cron-skip heartbeat".
  _step "check_daily_refresh_freshness" "$VENV_PY" "$KB/check_daily_refresh_freshness.py" \
    || echo "[daily_refresh] freshness check errored (non-fatal)"

  _step "verify_openrouter_catalog" "$VENV_PY" "$KB/verify_openrouter_catalog.py" --apply --ingest-new \
    || echo "[daily_refresh] verifier failed (non-fatal)"

  # Kilo CLI catalog sync — writes is_agentic (Kilo flag) + Kilo-only
  # rows + capabilities the OpenRouter verifier doesn't carry. Previously
  # boot-only (wsl_startup_hook.sh) which meant a laptop that doesn't
  # reboot left these stale. Now in cron too. Aggregator-audit 2026-06-29.
  _step "kilo_agents_db" "$VENV_PY" "$KB/kilo_agents_db.py" all \
    || echo "[daily_refresh] kilo_agents_db sync failed (non-fatal)"

  # Migrate aggregator-pricing columns (idempotent — adds gateway_prices,
  # cheapest_gateway, cheapest_gateway_price if missing). Cheap; runs
  # every day so a fresh checkout boots cleanly.
  _step "migrate_aggregator_columns" "$VENV_PY" "$KB/migrate_aggregator_columns.py" \
    || echo "[daily_refresh] aggregator columns migration failed (non-fatal)"

  # Ensure quality_tier/is_ga columns exist (idempotent, schema-only;
  # the actual values are recomputed below via derive_quality_v2).
  _step "migrate_selector_columns" "$VENV_PY" "$KB/migrate_selector_columns.py" \
    || echo "[daily_refresh] selector columns migration failed (non-fatal)"

  # Multi-signal quality scorer: combines existing arena/tbench/coding
  # benchmarks, OpenRouter's `benchmarks.design_arena` + Artificial
  # Analysis, model-family pattern matching, cost-as-proxy, reasoning
  # capability, and context length. Without this, ~85% of models
  # default to T1 and the category selector's `quality_tier>=2` floors
  # silently drop frontier models like claude-opus-4.8 that lack
  # Chatbot Arena ELOs.
  # Mine three public coding leaderboards into the DB (SWE-bench Verified,
  # Aider Polyglot, OpenRouter design_arena coding categories). Free —
  # no inference cost. Must run BEFORE derive_quality_v2 so its new
  # benchmark axes have data.
  _step "scrape_coding_benchmarks" "$VENV_PY" "$KB/scrape_coding_benchmarks.py" \
    || echo "[daily_refresh] coding-benchmarks scrape failed (non-fatal)"

  # Speed metrics + AA Intelligence Index. Without this, output_tokens_per_sec
  # and ttft_ms drift from boot-time to weeks-old. Aggregator-audit 2026-06-29:
  # found rows with speed_updated_at from 2026-05-19 because this script ran
  # only in wsl_startup_hook.sh.
  _step "scrape_artificial_analysis" "$VENV_PY" "$KB/scrape_artificial_analysis.py" \
    || echo "[daily_refresh] artificial-analysis scrape failed (non-fatal)"

  # Terminal Bench + general benchmark scraper.
  _step "update_kilo_benchmarks" "$VENV_PY" "$KB/update_kilo_benchmarks.py" --force \
    || echo "[daily_refresh] kilo benchmark scrape failed (non-fatal)"

  # ── KILO_* + cascade-models catalog regen (deploy-readiness-gaps Phase 3a) ──
  # Regenerate the three synced reference docs that were drifting daily (the
  # check_synced_unmodified gate fired on every project). MUST run AFTER the
  # benchmark scrape above (fresh data) and BEFORE embedding_export_markdown.py
  # below (line ~172), which overwrites only the EMBEDDING_* marker sections of
  # KILO_AGENT_SELECTION_GUIDE.md + KILO_MODEL_CAPABILITIES.md — these generators
  # write the ENTIRE file, so running them after would nuke those marker sections.
  _step "generate_model_capabilities" "$VENV_PY" "$KB/generate_model_capabilities.py" \
    || echo "[daily_refresh] generate_model_capabilities failed (non-fatal)"
  _step "generate_selection_guide_roster" "$VENV_PY" "$KB/generate_selection_guide_roster.py" \
    || echo "[daily_refresh] generate_selection_guide_roster failed (non-fatal)"
  _step "scrape_windsurf_models" "$VENV_PY" "$KB/scrape_windsurf_models.py" \
    || echo "[daily_refresh] scrape_windsurf_models failed (non-fatal)"

  # ============================================================
  # Kilo agent + Traycer registry workflow (ported from wsl_startup_hook.sh
  # on 2026-06-30 — the 2026-06-28 cron migration left these out, so
  # ~/.traycer/cli-agents/ + scripts/kilo_47_agents_final.json only got
  # refreshed when a terminal opened. Now also runs in cron.)
  #
  # Deterministic: pre_filter → selector → post_filter → DB. ~50ms, $0 cost,
  # byte-identical re-runs. No TTY, no interactive prompts → cron-safe.
  # Honors FABRIK_DISABLE_KILO_WORKFLOW=1 like the bashrc-hook does.
  # ============================================================
  if [ "${FABRIK_DISABLE_KILO_WORKFLOW:-0}" = "1" ]; then
    echo "[daily_refresh] kilo agent workflow skipped (FABRIK_DISABLE_KILO_WORKFLOW=1)"
  else
    # 1) Role mapping (deterministic role-winner assignment)
    _step "role_mapper" "$VENV_PY" "$KB/role_mapper.py" \
      || echo "[daily_refresh] role_mapper failed (non-fatal)"
    # 2) Refresh scripts/kilo_47_agents_final.json from the DB
    _step "export_traycer_registry" "$VENV_PY" "$KB/export_traycer_registry.py" \
      || echo "[daily_refresh] export_traycer_registry failed (non-fatal)"
    # 3) Emit Traycer CLI agent scripts to ~/.traycer/cli-agents/
    _step "generate_kilo_agents" "$VENV_PY" "$FABRIK_ROOT/scripts/generate_kilo_agents.py" \
      || echo "[daily_refresh] generate_kilo_agents failed (non-fatal)"
  fi

  # Embedding catalog sync (sibling to kilo_agents_db.py for embedding models).
  _step "embedding_models_db" "$VENV_PY" "$KB/embedding_models_db.py" all \
    || echo "[daily_refresh] embedding catalog sync failed (non-fatal)"

  # Embedding selection pipeline (ported with the kilo-agent workflow above).
  # Mirrors chat pipeline shape: catalog scrape → shortlists → role winners
  # → markdown export.
  _step "embedding_pre_filter" "$VENV_PY" "$KB/embedding_pre_filter.py" \
    || echo "[daily_refresh] embedding_pre_filter failed (non-fatal)"
  _step "embedding_role_mapper" "$VENV_PY" "$KB/embedding_role_mapper.py" \
    || echo "[daily_refresh] embedding_role_mapper failed (non-fatal)"
  _step "embedding_export_markdown" "$VENV_PY" "$KB/embedding_export_markdown.py" \
    || echo "[daily_refresh] embedding_export_markdown failed (non-fatal)"

  # Translation + STT capability seeds. Translation reads the
  # operator-curated bake-off doc in /opt/fabrik-lib/mt-router/docs/;
  # STT seeds direct-API models (Whisper, gpt-4o-transcribe, Deepgram,
  # AssemblyAI) with public WER scores. Idempotent.
  _step "seed_translation_and_stt" "$VENV_PY" "$KB/seed_translation_and_stt.py" \
    || echo "[daily_refresh] translation/STT seed failed (non-fatal)"

  # Direct-vendor specialists (Soniox STT/TTS, Recraft, FLUX, SDXL,
  # ElevenLabs, DeepL Pro) — operator-encoded facts that aren't on
  # OpenRouter / Kilo CLI and therefore aren't picked up by the
  # verifier. Idempotent UPSERT keyed by id.
  _step "seed_direct_vendors" "$VENV_PY" "$KB/seed_direct_vendors.py" \
    || echo "[daily_refresh] direct-vendor seed failed (non-fatal)"

  # Ensure the 3 direct-vendor pricing columns exist on `agents` (idempotent;
  # required by fetch_direct_vendor_prices.py below).
  _step "migrate_direct_vendor_pricing_columns" "$VENV_PY" "$KB/migrate_direct_vendor_pricing_columns.py" \
    || echo "[daily_refresh] direct-vendor pricing migration failed (non-fatal)"

  # Direct-vendor pricing scraper (Phase 1 ships 5 parsers: AssemblyAI,
  # Deepgram, Soniox, Cartesia, Speechmatics). The orchestrator runs in
  # --apply mode here; per-vendor errors don't fail the daily pipeline.
  # Plan: docs/development/plans/2026-06-29-plan-direct-vendor-pricing.md
  _step "fetch_direct_vendor_prices" "$VENV_PY" "$KB/fetch_direct_vendor_prices.py" --apply --quiet \
    || echo "[daily_refresh] direct-vendor pricing scraper had vendor errors (non-fatal)"

  # Phase 4 of the direct-vendor pricing plan: every daily refresh re-infers
  # provider for any rows that came back from the upstream catalogs with
  # provider='unknown' (claude-* models, corethink:free, etc.). Idempotent.
  _step "backfill_unknown_providers" "$VENV_PY" "$KB/backfill_unknown_providers.py" --apply \
    || echo "[daily_refresh] backfill_unknown_providers failed (non-fatal)"

  "$VENV_PY" "$KB/derive_quality_v2.py" \
    || echo "[daily_refresh] quality v2 deriver failed (non-fatal)"

  _step "classify_ai_category" "$VENV_PY" "$KB/classify_ai_category.py" \
    || echo "[daily_refresh] classifier failed (non-fatal)"

  _step "category_route_mapper" "$VENV_PY" "$KB/category_route_mapper.py" \
    || echo "[daily_refresh] route mapper failed (non-fatal)"

  _step "category_export_markdown" "$VENV_PY" "$KB/category_export_markdown.py" \
    || echo "[daily_refresh] markdown export failed (non-fatal)"

  # Aggregator pricing (plan-2-aggregator-pricing.md Phase 5). Fetchers
  # populate agents.gateway_prices JSON; derive picks cheapest gateway.
  # All three steps non-fatal so a transient Replicate/fal outage doesn't
  # nuke the rest of the pipeline.
  _step "fetch_replicate_prices" "$VENV_PY" "$KB/fetch_replicate_prices.py" \
    || echo "[daily_refresh] replicate price fetch failed (non-fatal)"
  if [ -n "${FAL_KEY:-}" ]; then
    _step "fetch_fal_prices" "$VENV_PY" "$KB/fetch_fal_prices.py" \
      || echo "[daily_refresh] fal price fetch failed (non-fatal)"
  fi
  _step "derive_cheapest_gateway" "$VENV_PY" "$KB/derive_cheapest_gateway.py" \
    || echo "[daily_refresh] cheapest gateway derive failed (non-fatal)"

  # Live gateway counts in the ai/ rule packs. Runs AFTER the OR-routes
  # injector + freshness stamp so both marker blocks land in the same
  # daily refresh. The script is idempotent and self-heals around
  # missing/orphaned markers (mirror of category_export_markdown's
  # contract).
  _step "update_gateway_counts" "$VENV_PY" "$KB/update_gateway_counts.py" \
    || echo "[daily_refresh] gateway counts inject failed (non-fatal)"

  _step "export_models_browser" "$VENV_PY" "$KB/export_models_browser.py" \
    || echo "[daily_refresh] models_browser export failed (non-fatal)"

  # ── Push regenerated synced files to all projects (deploy-readiness-gaps Phase 3b) ──
  # The catalog regen above rewrites synced governance files (.windsurf/rules/ai/*.md
  # + the KILO_* / cascade-models reference docs). Without this push, every project's
  # check_synced_unmodified gate fires daily. Runs LAST so it captures every
  # regenerated file. flock serializes against a manual operator run of
  # sync_enforcement_to_projects.py (the script has no internal lock); -w 0 means
  # "skip this run if a sync is already in progress" rather than block the cron.
  # No --quiet flag — it doesn't exist; an honest cron log is preferable.
  flock -w 0 /tmp/fabrik-sync-enforcement.lock \
    _step "sync_enforcement_to_projects" "$VENV_PY" "$FABRIK_ROOT/scripts/sync_enforcement_to_projects.py" \
    || echo "[daily_refresh] sync_enforcement skipped/failed (non-fatal — lock held or error)"

  # Heartbeat: write last-success timestamp so tomorrow's
  # check_daily_refresh_freshness.py knows this run completed.
  # Only written if we reach this line (most steps are non-fatal so we'll
  # get here even with partial failures — that's intentional; the
  # heartbeat catches CATASTROPHIC failures where the script never gets
  # past the early steps, not transient per-step issues which are
  # already covered by per-step Telegram alerts).
  #
  # Adversarial Pass-1 finding (Phase 5 heartbeat review): a silent
  # failure here (disk full, permission denied) would leave tomorrow's
  # check reading a stale or missing timestamp. The next day's heartbeat
  # self-corrects by firing a stale alert (timestamp from 2+ days ago is
  # >36h), but we ALSO log the immediate write failure so the operator
  # sees it in the same daily_refresh log they'd grep for the staleness
  # alert. Two-layer defense.
  mkdir -p "$KB/cache" || echo "[daily_refresh] CRITICAL: heartbeat cache dir creation failed"
  if ! date -u +'%Y-%m-%dT%H:%M:%S+00:00' > "$KB/cache/daily_refresh_last_success.txt" 2>/dev/null; then
    echo "[daily_refresh] CRITICAL: heartbeat timestamp write failed (disk full? permission?)"
  fi

  printf '[timing] TOTAL: %ds\n' "$((SECONDS - T0_TOTAL))"
  echo "=== Refresh complete — $(date -u +'%Y-%m-%d %H:%M:%S UTC') ==="
} >> "$LOG_FILE" 2>&1
