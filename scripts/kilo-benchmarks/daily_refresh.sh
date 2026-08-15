#!/bin/bash
# Daily refresh of the AI model catalog. Cron-safe (no PATH assumptions,
# no shell activity required). Runs the full chain:
#   0. gather_envs.py + classify_services.py --apply
#        → refresh secrets/all-envs.env; web-ground + catalog any new external
#          service whose key appeared (no-op at zero cost when nothing is new)
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
#   7. derive_cheapest_gateway.py (preceded on Sundays by microbench_or_models.py
#      + microbench_specialty.py — OR / specialty microbench for rows without
#      Speed data; needs OPENROUTER_API_KEY + specialty-provider keys)
#        → picks the cheapest (gateway, price) per row from
#          gateway_prices + direct price; writes cheapest_gateway +
#          cheapest_gateway_price for the browser to badge
#   8. rank_coding_subagents.py
#        → queries the DB for GLM/Kimi/Minimax/DeepSeek active LLMs,
#          applies a weighted composite score + Doc↔Code letter grade,
#          writes docs/reference/kilo/CODING_SUBAGENT_SELECTION.md
#   8b1. correlated_prior.py
#        → seeds plan/spec cold-start priors (plan←code+review, spec←docs+plan)
#          into model_task_baseline (FREE; paid judged bench is operator-only)
#   8b. rank_task_subagents.py
#        → queries fabrik_analytics.subagent_runs, aggregates per
#          (task_type, model) with 90-day window + min 3 runs, writes
#          docs/reference/kilo/TASK_SUBAGENT_SELECTION.md. Consumed by
#          the subagents module's pick_models (select.py:174).
#   9. export_models_browser.py
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

# ⚠️ BLOCK-SCOPE REDIRECT HAZARD. The whole pipeline body below is one compound command closed
# by `} >> "$LOG_FILE" 2>&1`, and a failed redirection on a COMPOUND command makes bash skip the
# ENTIRE body — not just one line. LOG_FILE lives in $KB/cache/, so if that directory cannot be
# created the refresh silently does nothing AND the "heartbeat cache dir creation FAILED" guard
# inside the block never even evaluates. Line-scope redirects were fixed earlier; this is the
# block-scope instance of the same class, and it is the one that matters.
#
# ⚠️ The probe must be a real APPEND, not `mkdir -p`. `mkdir -p` returns 0 when the directory
# already exists — including when it exists and is NOT WRITABLE — so a `mkdir`-based guard
# passes cleanly while the redirect below still fails and still skips the whole body. Verified:
# `chmod 500` the cache dir and the mkdir guard reports success, the block exits 1, and nothing
# runs. Only appending to the actual target proves the actual redirect can succeed.
_log_usable() { mkdir -p "$(dirname "$1")" 2>/dev/null && : >>"$1" 2>/dev/null; }

if ! _log_usable "$LOG_FILE"; then
  _fallback="/tmp/fabrik_daily_refresh_$(date -u +%Y%m%d).log"
  echo "[daily_refresh] CRITICAL: $LOG_FILE is not writable — falling back to $_fallback" >&2
  # Alert BEFORE the block, while a working redirect still exists.
  bash "$KB/pipeline_alert.sh" \
    "daily_refresh.sh: log file unwritable — pipeline would have silently no-opped" \
    "Could not append to $LOG_FILE. The refresh body is one compound command redirected there, so bash would have skipped ALL of it without running a single step or firing the in-block heartbeat guard. Falling back for this run. Investigate disk/permissions now." \
    || true
  # If even /tmp is unusable, redirect to stderr rather than to a path that fails: a failed
  # redirect skips the entire pipeline, which is strictly worse than logging somewhere odd.
  # There is no configuration in which this script should silently do nothing.
  # /dev/stderr is NOT unconditionally safe: `daily_refresh.sh 2>&-`, or any daemonized
  # invocation with fd 2 closed, makes appending to it fail and reproduces the silent skip on
  # the very branch that exists to be unfailable. Probe it too, then degrade to /dev/null —
  # running with no log is bad; not running at all, with no alert, is what we are preventing.
  if _log_usable "$_fallback"; then LOG_FILE="$_fallback"
  elif : >>/dev/stderr 2>/dev/null; then LOG_FILE="/dev/stderr"
  else LOG_FILE="/dev/null"; fi
fi
{
  echo ""
  echo "=== Fabrik AI catalog refresh — $(date -u +'%Y-%m-%d %H:%M:%S UTC') ==="

  # cd failure exits 1 (not 0): otherwise cron + the heartbeat would
  # mark a never-ran job as "successful" and tomorrow's freshness check
  # would skip alerting. Better to surface the failure immediately.
  cd "$KB" || { echo "[daily_refresh] cd failed — aborting"; exit 1; }

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

  # ─── DB safety snapshot BEFORE the pipeline mutates kilo_agents.db (added 2026-07-19) ───
  # kilo_agents.db is now gitignored (git no longer versions it — it kept poisoning the tree),
  # so keep a rolling on-disk snapshot here as its safety net. Retain the last 3 (~39MB); backups/
  # is itself gitignored (*.backup.*). Non-fatal: a failed snapshot must not abort the refresh.
  mkdir -p "$KB/backups"
  if [ -f "$KB/kilo_agents.db" ]; then
    cp -p "$KB/kilo_agents.db" "$KB/backups/kilo_agents.db.backup.$(date -u +%Y%m%d-%H%M%S)" \
      && echo "[db-backup] pre-run snapshot taken" \
      || echo "[db-backup] snapshot FAILED (non-fatal)"
    ls -1t "$KB"/backups/kilo_agents.db.backup.* 2>/dev/null | tail -n +4 | xargs -r rm -f
  fi

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

  # Keep the external-service catalog fresh. gather_envs consolidates every
  # /opt/*/.env into secrets/all-envs.env and flags any provider whose key
  # prefix matches no catalog entry as `category=?` (NEEDS-TRIAGE). classify_services
  # then web-grounds ONLY those unknowns via a cheap pool unit and merges them into
  # scripts/service_catalog.json. Both are idempotent and NO-OP at zero cost when
  # nothing new was added (classify prints "nothing to do" and exits 0), so this is
  # cheap every day and self-updates the catalog the day after a new key appears.
  _step "gather_envs" "$VENV_PY" "$FABRIK_ROOT/scripts/gather_envs.py" --apply \
    || echo "[daily_refresh] gather_envs failed (non-fatal)"
  _step "classify_services" "$VENV_PY" "$FABRIK_ROOT/scripts/classify_services.py" --apply --tombstone-unresolved \
    || echo "[daily_refresh] classify_services failed (non-fatal)"

  # Ensure the OR richer-extraction columns (canonical_slug, knowledge_cutoff,
  # cache_read/write_cost_per_m, reasoning_mandatory, reasoning_supported_efforts,
  # max_completion_tokens, is_moderated) exist BEFORE the verifier writes to
  # them. The other migrations below run AFTER the verifier but were added in
  # commits where the verifier didn't depend on them — those effectively take
  # effect on the FOLLOWING day's run. The richer-extraction columns must be
  # available SAME-DAY because verify_openrouter_catalog --apply now populates
  # them in apply_fixes() + ingest_new(). Idempotent.
  _step "migrate_or_richer_extraction" "$VENV_PY" "$KB/migrate_or_richer_extraction.py" \
    || echo "[daily_refresh] OR richer-extraction migration failed (non-fatal)"

  _step "verify_openrouter_catalog" "$VENV_PY" "$KB/verify_openrouter_catalog.py" --apply --ingest-new \
    || echo "[daily_refresh] verifier failed (non-fatal)"

  # Corrective sweep: verify_openrouter_catalog historically over-deprecated
  # direct-vendor rows (Soniox, ElevenLabs, Anthropic-direct claude-* IDs,
  # etc.) because they don't appear in OR's /api/v1/models. The verifier
  # itself is patched (via_openrouter=1 filter), but this restore keeps the
  # DB self-healing against any future verifier-side regression. Idempotent
  # via exact discard_reason match. Plan 2026-07-03-plan-1-full-speed-coverage-close A.7.
  _step "restore_wrongly_deprecated_direct_vendors" "$VENV_PY" "$KB/restore_wrongly_deprecated_direct_vendors.py" --apply \
    || echo "[daily_refresh] restore-direct-vendors failed (non-fatal)"

  # Hidden-route discovery (Phase 2 of operator's "extract all models" ask).
  # Ensures the 7 known openrouter/* meta-routes (auto, fusion, owl-alpha,
  # elephant-alpha, pareto-code, bodybuilder, free) stay active+via_or=1
  # regardless of OR's /api/v1/models curation. Idempotent, no-op when
  # nothing drifted. Does NOT pass --ingest-sitemap by default — the 231
  # sitemap candidates need operator review before bulk-ingest (specialty
  # image/video/audio/embedding models that don't surface via /api/v1/models).
  _step "discover_hidden_openrouter_routes" "$VENV_PY" "$KB/discover_hidden_openrouter_routes.py" --apply \
    || echo "[daily_refresh] hidden-route discovery failed (non-fatal)"

  # OR /rankings scraper (Phase 4 of "extract all models with all columns").
  # Writes weekly_rank + weekly_category for 102 models surfaced on
  # openrouter.ai/rankings/* — the production-usage signal that no other
  # source carries. Carries an embedded snapshot (the rankings pages are
  # React-rendered and SSR doesn't carry the row data); the operator
  # refreshes the snapshot via the puppeteer-MCP sweep.
  _step "scrape_openrouter_rankings" "$VENV_PY" "$KB/scrape_openrouter_rankings.py" --apply \
    || echo "[daily_refresh] OR rankings scrape failed (non-fatal)"

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

  # Groq LPU tokens/sec table. Provider-specific — only realized when
  # provider.only=["Groq"] is pinned in the OR request. Never clobbers
  # higher-precedence sources (AA / own_microbench / manual_override).
  _step "scrape_groq_speeds" "$VENV_PY" "$KB/scrape_groq_speeds.py" \
    || echo "[daily_refresh] groq speeds scrape failed (non-fatal)"

  # Terminal Bench + general benchmark scraper.
  _step "update_kilo_benchmarks" "$VENV_PY" "$KB/update_kilo_benchmarks.py" --force \
    || echo "[daily_refresh] kilo benchmark scrape failed (non-fatal)"

  # ── KILO_* selection-catalog regen (deploy-readiness-gaps Phase 3a) ──
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
  # Fabrik capability catalog regen (plan 2026-07-12-plan-2). Re-derives
  # capabilities.json + docs/CAPABILITIES.md + llms.txt by introspecting the
  # 7 tool surfaces (cli/driver/registrar/script/lib-module/scaffold/rules)
  # and liveness-probing each, so a cold AI agent always reads a current,
  # self-verified tool catalog. Generated-not-hand-curated; fail-soft per
  # probe (a broken probe → status:broken, never crashes the refresh).
  _step "generate_capability_index" "$VENV_PY" "$FABRIK_ROOT/scripts/generate_capability_index.py" \
    || echo "[daily_refresh] generate_capability_index failed (non-fatal)"

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
  # Phase 5 of the direct-vendor pricing plan: write a per-vendor markdown audit
  # alongside the silent --quiet run. Filename includes UTC date so each day's
  # audit is preserved as operator history at cache/direct_vendor_audit_<date>.md.
  _step "fetch_direct_vendor_prices" "$VENV_PY" "$KB/fetch_direct_vendor_prices.py" \
      --apply --quiet \
      --report-md "$KB/cache/direct_vendor_audit_$(date -u +%F).md" \
    || echo "[daily_refresh] direct-vendor pricing scraper had vendor errors (non-fatal)"

  # Phase 4 of the direct-vendor pricing plan: every daily refresh re-infers
  # provider for any rows that came back from the upstream catalogs with
  # provider='unknown' (claude-* models, corethink:free, etc.). Idempotent.
  _step "backfill_unknown_providers" "$VENV_PY" "$KB/backfill_unknown_providers.py" --apply \
    || echo "[daily_refresh] backfill_unknown_providers failed (non-fatal)"

  # Wrapped in _step for per-step timing consistency with every other
  # script above. Pre-fix the timing summary omitted this row.
  _step "derive_quality_v2" "$VENV_PY" "$KB/derive_quality_v2.py" \
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
  # OR per-model /endpoints scrape — fetches the full inference-provider
  # list for every OR-routed model so the "Cheapest" column can surface
  # the raw provider (DeepInfra/Groq/etc.) that beats OR's default routing.
  # ~340 API calls @ 4/s = ~90s. Non-fatal on transient OR outage.
  _step "scrape_openrouter_endpoints" "$VENV_PY" "$KB/scrape_openrouter_endpoints.py" \
    || echo "[daily_refresh] OR endpoints scrape failed (non-fatal)"

  # SiliconFlow catalog scrape — flips via_siliconflow=1 on matched agents.id
  # rows so the browser payload + rank scripts see SF as a real gateway. Fetches
  # the 72-model catalog from https://api.siliconflow.com/v1/models (international
  # endpoint; .cn returns 401 on international keys). Non-fatal on missing key or
  # network failure. Idempotent.
  _step "scrape_siliconflow_catalog" "$VENV_PY" "$KB/scrape_siliconflow_catalog.py" \
    || echo "[daily_refresh] SiliconFlow catalog scrape failed (non-fatal)"

  # ModelScope catalog scrape + new-row auto-ingest.
  # - Flips via_modelscope=1 on matched agents.id rows so the browser payload
  #   + rank scripts see MS as a real gateway.
  # - With --ingest-new (plan-2 follow-up, 2026-07-10): INSERTs previously-
  #   unmatched MS IDs via 3-tier enrichment fallback (HF Hub → MS SPA scrape
  #   via web-scrape → placeholder+blocked=1 with block_reason). Placeholder
  #   rows are visible in the browser MS chip but hidden from rankers.
  # Fetches the 55-model catalog from https://api-inference.modelscope.cn/v1/models
  # (OpenAI-compatible). Non-fatal on missing key or network failure. Idempotent.
  _step "scrape_modelscope_catalog" "$VENV_PY" "$KB/scrape_modelscope_catalog.py" --ingest-new \
    || echo "[daily_refresh] ModelScope catalog scrape failed (non-fatal)"

  # Weekly (Sundays UTC): OR microbench for rows without Speed data.
  # Skipped if OPENROUTER_API_KEY not set. Placed BEFORE derive so the
  # freshly-benched Speed rows feed the derived views on Sundays.
  # `date +%u` returns 1-7 (Mon-Sun) — 7 = Sunday.
  if [ "$(date -u +%u)" = "7" ]; then
    if [ -n "${OPENROUTER_API_KEY:-}" ]; then
      _step "microbench_or_models" "$VENV_PY" "$KB/microbench_or_models.py" \
        || echo "[daily_refresh] microbench failed (non-fatal)"
    else
      echo "[daily_refresh] microbench: SKIP (Sunday but OPENROUTER_API_KEY not set)"
    fi
    # Specialty bench (image_gen/tts/music_gen/stt/translation) — Sundays too.
    # Cost-capped at $10 hard / $2.50 soft. Non-fatal so a provider outage
    # doesn't take down the rest of the pipeline.
    _step "microbench_specialty" "$VENV_PY" "$KB/microbench_specialty.py" \
      || echo "[daily_refresh] microbench_specialty failed (non-fatal)"
  fi

  _step "derive_cheapest_gateway" "$VENV_PY" "$KB/derive_cheapest_gateway.py" \
    || echo "[daily_refresh] cheapest gateway derive failed (non-fatal)"

  # Coding-subagent ranking → docs/reference/kilo/CODING_SUBAGENT_SELECTION.md.
  # Runs AFTER derive_cheapest_gateway so the table reflects today's pricing.
  # Non-fatal — a missing table doesn't take down the rest of the pipeline.
  _step "rank_coding_subagents" "$VENV_PY" "$KB/rank_coding_subagents.py" \
    || echo "[daily_refresh] rank_coding_subagents failed (non-fatal)"

  # Correlated cold-start priors for plan/spec (FREE, no generation): seeds model_task_baseline
  # from today's code+review (+ docs, once benched) metrics, so pick_models("plan"/"spec") shrinks
  # against a non-blind prior. Idempotent; fail-soft. Runs BEFORE rank_task_subagents so the priors
  # are fresh in the regenerated doc. (The PAID judged bench — microbench_judged.py --task
  # research/docs --all — is an OPERATOR step, never run here; it spends money + takes ~an hour.)
  _step "correlated_prior" "$VENV_PY" "$KB/correlated_prior.py" \
    || echo "[daily_refresh] correlated_prior failed (non-fatal)"

  # Task-subagent ranking → docs/reference/kilo/TASK_SUBAGENT_SELECTION.md.
  # Reads fleet-wide subagent_runs on fabrik_analytics; emits per-task ranking.
  # Empty pool (state=ok, 0 rows) → stub file with "No aggregated runs yet"; exits 0.
  # A BROKEN read (state=error: DB down / sudo -n misconfig / timeout) does NOT emit the
  # failure stub and does NOT bump "Last refresh" — the existing good doc is KEPT and the
  # ranker exits 1. That inversion is deliberate (Phase A.0): the stub would be committed
  # and fleet-synced to the 49 vendored pick_models copies, and its fresh date would forge
  # past select.py's 14-day staleness gate. The alert below is the operator signal.
  _step "rank_task_subagents" "$VENV_PY" "$KB/rank_task_subagents.py" \
    || { echo "[daily_refresh] rank_task_subagents FAILED — see above; the existing selection doc was KEPT"; "$VENV_PY" -c "import sys; sys.path.insert(0, '$KB'); from dotenv import load_dotenv; load_dotenv('$FABRIK_ROOT/.env', override=False); from alerting import send_alert; send_alert(title='daily_refresh.sh: rank_task_subagents exited non-zero', body='rank_task_subagents.py exited non-zero. Most likely the flywheel read is BROKEN (state=error) — in that case the previous TASK_SUBAGENT_SELECTION.md was deliberately KEPT rather than overwritten with the failure stub, so the fleet is on yesterday-good, not poisoned. It can also mean render/write failed (disk, permissions). Check the run log, then the postgres/sudo path on this host.', severity='critical')" 2>&1 || true; }

  # Per-task specialty rankers (best-model-suggester Phase B). Emit
  # {TTS,STT,TRANSLATION,IMAGE_GEN}_SELECTION.md via Pareto rank on
  # (cost ↑, quality_elo ↓) over reachable_with_existing_keys=1 rows.
  # Each is non-fatal individually.
  _step "rank_tts" "$VENV_PY" "$KB/rank_tts.py" \
    || echo "[daily_refresh] rank_tts failed (non-fatal)"
  _step "rank_stt" "$VENV_PY" "$KB/rank_stt.py" \
    || echo "[daily_refresh] rank_stt failed (non-fatal)"
  _step "rank_translation" "$VENV_PY" "$KB/rank_translation.py" \
    || echo "[daily_refresh] rank_translation failed (non-fatal)"
  _step "rank_image_gen" "$VENV_PY" "$KB/rank_image_gen.py" \
    || echo "[daily_refresh] rank_image_gen failed (non-fatal)"

  # Phase E — GPU price refresh + candidate signups ranker.
  # scrape_gpu_prices is fail-soft (leaves DB prices intact on network error);
  # rank_candidate_signups emits CANDIDATE_SIGNUPS.md.
  _step "scrape_gpu_prices" "$VENV_PY" "$KB/scrape_gpu_prices.py" \
    || echo "[daily_refresh] scrape_gpu_prices failed (non-fatal)"
  _step "rank_candidate_signups" "$VENV_PY" "$KB/rank_candidate_signups.py" \
    || echo "[daily_refresh] rank_candidate_signups failed (non-fatal)"

  # Live gateway counts in the ai/ rule packs. Runs AFTER the OR-routes
  # injector + freshness stamp so both marker blocks land in the same
  # daily refresh. The script is idempotent and self-heals around
  # missing/orphaned markers (mirror of category_export_markdown's
  # contract).
  _step "update_gateway_counts" "$VENV_PY" "$KB/update_gateway_counts.py" \
    || echo "[daily_refresh] gateway counts inject failed (non-fatal)"

  _step "export_models_browser" "$VENV_PY" "$KB/export_models_browser.py" \
    || echo "[daily_refresh] models_browser export failed (non-fatal)"

  # Cross-source audit — nightly proof that DB values match live OR /
  # OR /endpoints / Kilo CLI. Any drift is logged; non-fatal so a
  # transient upstream outage doesn't nuke the pipeline. Trust anchor
  # for the browser: if this reports drift, the row(s) shown are wrong.
  _step "audit_ui_values" "$VENV_PY" "$KB/audit_ui_values.py" \
    || echo "[daily_refresh] audit_ui_values reported drift or failed (non-fatal)"

  # ─── Contract oracle — did this run still produce everything it is supposed to? ───
  # Placed BEFORE the fleet sync on purpose: run after it, a marker that stopped being
  # injected or a doc collapsed to a husk would be pushed to ~46 project repos and THEN
  # alerted. Advisory either way (it must never abort a healthy refresh), but the operator
  # now sees the alert before the blast radius rather than after it.
  # THE production caller for tests/capture_golden.py --verify. Without this the oracle ran
  # only under pytest, in its permissive mode, so ORACLE_REQUIRE_LOCAL_ARTIFACTS was never
  # set anywhere and the 4 gitignored artifacts (31% of the frozen inventory) stayed exempt
  # from "NO LONGER PRODUCED" in every real execution. This is the box that actually produces
  # them, so absence here means the pipeline stopped emitting them — not an absent checkout.
  # Advisory (|| true): the oracle guards the Phase B-E extraction, and must never be able to
  # abort a healthy nightly refresh. Exit 2 = the golden predates the observer (re-snapshot).
  if ! ORACLE_REQUIRE_LOCAL_ARTIFACTS=1 "$VENV_PY" "$KB/tests/capture_golden.py" --verify; then
    echo "[daily_refresh] contract oracle reported DRIFT or a stale golden — see above"
    "$VENV_PY" -c "import sys; sys.path.insert(0, '$KB'); from dotenv import load_dotenv; load_dotenv('$FABRIK_ROOT/.env', override=False); from alerting import send_alert; send_alert(title='daily_refresh.sh: contract oracle reported drift', body='tests/capture_golden.py --verify did not come back clean on the pipeline host. Either an artifact/marker/query the fleet consumes stopped being produced or collapsed to a husk, or the frozen golden predates the current observer (exit 2 -> re-run --snapshot). Check the run log for the specific contract element.', severity='critical')" 2>&1 || true
  fi

  # ── Push regenerated synced files to all projects (deploy-readiness-gaps Phase 3b) ──
  # The catalog regen above rewrites synced governance files (.windsurf/rules/ai/*.md
  # + the KILO_* reference docs). Without this push, every project's
  # check_synced_unmodified gate fires daily. Runs LAST so it captures every
  # regenerated file. flock serializes against a manual operator run of
  # sync_enforcement_to_projects.py (the script has no internal lock); -w 0 means
  # "skip this run if a sync is already in progress" rather than block the cron.
  # No --quiet flag — it doesn't exist; an honest cron log is preferable.
  #
  # 2026-06-30 audit BUG FIX: previously this line read
  #   `flock -w 0 LOCK _step "label" ...`
  # which fails immediately because `_step` is a bash function (defined in
  # this script) — `flock` invokes execvp() and a function isn't a binary.
  # The result was "flock: failed to execute _step: No such file or
  # directory" on every nightly run, masked by the trailing `|| echo`. The
  # sync step has been silently failing for as long as this line existed
  # — verified by tail -100 update.log showing ZERO sync_enforcement
  # entries. Fixed by inverting the wrap order: `_step` now executes
  # `flock`, which is a real binary, and flock execs $VENV_PY. The lock
  # semantics are preserved and the per-step timing is now emitted.
  _step "sync_enforcement_to_projects" \
    flock -w 0 /tmp/fabrik-sync-enforcement.lock \
      "$VENV_PY" "$FABRIK_ROOT/scripts/sync_enforcement_to_projects.py" \
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
  # Adversarial review M1 (2026-06-30): pre-fix, write failures only landed
  # in update.log — nobody tails it day-to-day, so the disk-full / perm-denied
  # case only surfaced via the NEXT day's stale-heartbeat alert. Now we ALSO
  # fire a direct Telegram alert via the alerting module so the operator sees
  # it within minutes, not 36h later.
  if ! mkdir -p "$KB/cache"; then
    echo "[daily_refresh] CRITICAL: heartbeat cache dir creation failed"
    bash "$KB/pipeline_alert.sh" 'daily_refresh.sh: heartbeat cache dir creation FAILED' "Disk full or permission denied on $KB/cache/. Next-day staleness alert will fire as backup but operator should investigate immediately." || true
  fi
  if ! date -u +'%Y-%m-%dT%H:%M:%S+00:00' > "$KB/cache/daily_refresh_last_success.txt" 2>/dev/null; then
    echo "[daily_refresh] CRITICAL: heartbeat timestamp write failed (disk full? permission?)"
    bash "$KB/pipeline_alert.sh" 'daily_refresh.sh: heartbeat timestamp write FAILED' "Could not write to $KB/cache/daily_refresh_last_success.txt. Tomorrow heartbeat will alert as STALE; please investigate disk / permissions now." || true
  fi

  # ─── Disk hygiene — keep the on-disk footprint BOUNDED (added 2026-07-19) ───
  # gitignoring the caches stopped them poisoning the tree, but they still grew on disk.
  # Prune every run so the WSL box never fills with pipeline trash. All non-fatal. The
  # API-response caches (.microbench_cache / translation_bench/cache) are cost-savers, so
  # prune only by AGE (keep the recent ones); logs + audits + stray pytest caches go by count.
  {
    # 30-day age prune of the response caches (recent kept → re-runs stay cheap)
    find "$KB/.microbench_cache" -type f -mtime +30 -delete 2>/dev/null || true
    find "$KB/translation_bench/cache" -type f -mtime +30 -delete 2>/dev/null || true
    # keep the newest 5 direct-vendor audit files
    ls -1t "$KB"/cache/direct_vendor_audit_* 2>/dev/null | tail -n +6 | xargs -r rm -f
    # cap the rotated logs at the newest 3
    ls -1t "$KB"/cache/update.log.* 2>/dev/null | tail -n +4 | xargs -r rm -f
    # drop stray pytest caches + __pycache__ under kilo-benchmarks (regenerated on demand)
    find "$KB" -type d \( -name .pytest_cache -o -name __pycache__ \) -exec rm -rf {} + 2>/dev/null || true
    # remove stale daily lockfiles from /tmp (keep today's UTC)
    for _lf in /tmp/.fabrik_daily_*; do
      [ -e "$_lf" ] && [ "$_lf" != "/tmp/.fabrik_daily_$(date -u +%Y%m%d)" ] && rm -f "$_lf"
    done 2>/dev/null || true
    echo "[disk-hygiene] pruned caches/logs/audits/backups to bounded limits"
  } || echo "[daily_refresh] disk-hygiene step errored (non-fatal)"

  # ─── Auto-commit the pipeline's OWN regenerated tracked docs ───
  # Extracted to autocommit_pipeline_outputs.sh 2026-08-14 so this entry point and
  # wsl_startup_hook.sh share ONE stage list. Forking the list is what let
  # 65-rag-search.md and embedding_shortlists.json go unstaged; keep the paths there.
  bash "$KB/autocommit_pipeline_outputs.sh" daily_refresh \
    || echo "[daily_refresh] auto-commit step errored (non-fatal)"

  printf '[timing] TOTAL: %ds\n' "$((SECONDS - T0_TOTAL))"
  echo "=== Refresh complete — $(date -u +'%Y-%m-%d %H:%M:%S UTC') ==="
} >> "$LOG_FILE" 2>&1
