#!/bin/bash
# fabrik's CONSUMER pipeline for the AI model catalog. Cron-safe (no PATH assumptions, no shell
# activity required). `0 6 * * *`.
#
# ⚠️ THIS SCRIPT NO LONGER PRODUCES THE CATALOG. The engine (scrape → normalize → derive → rank →
# export, ~210 modules) was relocated to /opt/ai-model-catalog/engine/ on 2026-08-15 and runs from
# its own cron at `30 5 * * *`, half an hour ahead of this one so the delivered artifacts are fresh
# when generate_kilo_agents reads them. This header used to document a 9-step producer chain
# (verify_openrouter_catalog → classify_ai_category → category_route_mapper → category_export_markdown
# → update_gateway_counts → fetch_*_prices → derive_cheapest_gateway → rank_* → export_models_browser);
# every one of those steps is gone from this file. Rewritten 2026-08-16 after a review found the
# header still describing the pipeline it had stopped running — a stale header on a cron entry point
# is how the next operator debugs the wrong system.
#
# What this file actually does now, in order:
#   1. check_daily_refresh_freshness.py  — heartbeat: alerts if the previous run is >36h stale
#   2. scripts/external_services_chain.sh — gather_envs (+ code-host scan) → classify →
#      gather_envs → registry_sync → gen_dashboard (shared with wsl_startup_hook.sh)
#      (classify, the paid pool pass, is inside that chain — bounded, cursor-walked)
#   3. generate_capability_index.py      — regenerate capabilities.json + docs/CAPABILITIES.md
#   4. generate_kilo_agents.py           — emit the Traycer CLI agent scripts from kilo_agents.db
#   5. sync_enforcement_to_projects.py   — distribute governance + the delivered docs to ~46 repos
#
# ⚠️ The heartbeat measures whether THIS script reached its end. It does NOT measure catalog
# freshness — post-relocation those are different questions, and a green heartbeat here says nothing
# about whether the engine ran. The delivered-doc age is the signal that matters
# (docs/reference/kilo/TASK_SUBAGENT_SELECTION.md mtime; select.py drops a ranking >14 days old).
#
# Install (already in crontab):
#   ( crontab -l; echo "0 6 * * * /opt/fabrik/scripts/kilo-benchmarks/daily_refresh.sh" ) | crontab -
# Manual run:
#   bash /opt/fabrik/scripts/kilo-benchmarks/daily_refresh.sh
# Logs: stdout (12-Factor XI). Redirect at the invocation layer if you want a file.
set -u
FABRIK_ROOT="/opt/fabrik"
export FABRIK_ROOT  # the seven alert-helper calls below inherit it — unexported, the helper fell back to its own default (identical today, silently divergent the day either moves; FD6)
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
_log_usable() { mkdir -p "$(dirname "$1")" 2>/dev/null && : 2>/dev/null >>"$1"; }  # redirections apply LEFT to RIGHT: `>>FILE 2>/dev/null` printed "Permission denied" before fd 2 moved (FD6)

if ! _log_usable "$LOG_FILE"; then
  _fallback="/tmp/fabrik_daily_refresh_$(date -u +%Y%m%d).log"
  _broken="$LOG_FILE"
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
  # ⚠️ Announce AFTER the ladder has chosen, or the alert names a destination the log did not
  # go to. Alert here, while a working redirect still exists — the block below cannot.
  echo "[daily_refresh] CRITICAL: $_broken is not writable — logging to $LOG_FILE" >&2
  bash "$KB/pipeline_alert.sh" \
    "daily_refresh.sh: log file unwritable — pipeline would have silently no-opped" \
    "Could not append to $_broken. The refresh body is one compound command redirected there, so bash would have skipped ALL of it without running a single step or firing the in-block heartbeat guard. Now logging to $LOG_FILE for this run. Investigate disk/permissions now." \
    || true
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

  # A1 — replay every repo's stranded subagent rows into the flywheel. `pg_ledger.flush_outbox` was
  # DESIGNED to be run from here ("run from a machine WITH the DSN (the hub, e.g. wired into
  # daily_refresh.sh next to the ranking regen)", pg_ledger.py:855-858) and nothing ever called it:
  # `crontab -l` and a grep over scripts/ both returned ZERO callers, so rows piled up on disk in
  # every repo that dispatches subagents — 3,578 across 10 outbox dirs when this step was written,
  # and GROWING while unflushed. Fail-open by construction: it exits 0 on every path, so a sink
  # outage can never red the refresh. It must run BEFORE the ranking regen below, or the ranking
  # reads a table missing the day's rows.
  _step "flush_subagent_outboxes" "$VENV_PY" "$KB/flush_subagent_outboxes.py" \
    || echo "[daily_refresh] outbox flush errored (non-fatal, fail-open by design)"

  # A5 — regenerate the subagent ranking. ⚠️ This step DID NOT EXIST until 2026-09-02, which is a
  # larger finding than the step: `rank_task_subagents.py` appeared exactly once in this file's 493
  # lines, inside a COMMENT, so the ranking that drives `pick_models` FLEET-WIDE was regenerated only
  # when a human ran it by hand. `TASK_SUBAGENT_SELECTION.md` read "Last refresh: <recent>" purely
  # because someone had. Ordered AFTER the flush so each day's recovered rows are in the table the
  # ranking reads.
  _step "rank_task_subagents" "$VENV_PY" "$KB/rank_task_subagents.py" \
    || echo "[daily_refresh] ranking regen errored (non-fatal — the previous doc stands)"

  # The external-services chain (gather_envs → classify → gather_envs → registry_sync →
  # gen_dashboard) lives in ONE script shared with wsl_startup_hook.sh — both entry points race
  # for the daily lock, so a step defined in only one of them silently never runs on the days
  # the other wins (the 2026-08-14 back-port lesson). It alerts on its own failures and writes
  # the dashboard (the liveness heartbeat) only when every DATA step succeeded.
  _rc=0
  _step "external_services_chain" env LOG_FILE="$LOG_FILE" FABRIK_ROOT="$FABRIK_ROOT" bash "$FABRIK_ROOT/scripts/external_services_chain.sh" || _rc=$?
  # `$?` inside `if ! cmd; then` is the NEGATION's status (always 0) — the round-60 branch was dead (EY7/EZ2)
  if [ "$_rc" -ne 0 ]; then
    case "$_rc" in 126|127)  # bash could not START the chain (missing / unreadable): none of its own alerts ever ran
      bash "$KB/pipeline_alert.sh" 'daily_refresh.sh: external-services chain did NOT start' "bash exited $_rc — scripts/external_services_chain.sh missing or unreadable, or its cd to FABRIK_ROOT failed (the log says: cannot cd to); nothing inside the chain ran, so its own step alerts never fired. Log: $LOG_FILE" || true ;;
      129|1[3-8][0-9]|19[0-2])  # the chain PROCESS died on a SIGNAL (128+N, N in 1..64 — 124/125/128 and 193-255 are plain exits and read "signal 0/127" before, FF1; SIGHUP/INT/QUIT/ABRT/KILL/SEGV/PIPE/TERM …) — the chain's own exits are only 0/1; five enumerated codes missed SIGQUIT/ABRT/SEGV/PIPE (FE6)
      bash "$KB/pipeline_alert.sh" 'daily_refresh.sh: external-services chain was KILLED' "exit $_rc (signal $((_rc - 128))) took the chain process; its own step alerts never ran. Log: $LOG_FILE" || true ;;
    esac
    echo "[daily_refresh] external-services chain failed (exit $_rc; a step failure is alerted by the chain, a 126/127 or a kill by this caller, non-fatal)"
  fi

  # Ensure the OR richer-extraction columns (canonical_slug, knowledge_cutoff,
  # cache_read/write_cost_per_m, reasoning_mandatory, reasoning_supported_efforts,
  # max_completion_tokens, is_moderated) exist BEFORE the verifier writes to
  # them. The other migrations below run AFTER the verifier but were added in
  # commits where the verifier didn't depend on them — those effectively take
  # effect on the FOLLOWING day's run. The richer-extraction columns must be
  # available SAME-DAY because verify_openrouter_catalog --apply now populates
  # them in apply_fixes() + ingest_new(). Idempotent.


  # Corrective sweep: verify_openrouter_catalog historically over-deprecated
  # direct-vendor rows (Soniox, ElevenLabs, Anthropic-direct claude-* IDs,
  # etc.) because they don't appear in OR's /api/v1/models. The verifier
  # itself is patched (via_openrouter=1 filter), but this restore keeps the
  # DB self-healing against any future verifier-side regression. Idempotent
  # via exact discard_reason match. Plan 2026-07-03-plan-1-full-speed-coverage-close A.7.

  # Hidden-route discovery (Phase 2 of operator's "extract all models" ask).
  # Ensures the 7 known openrouter/* meta-routes (auto, fusion, owl-alpha,
  # elephant-alpha, pareto-code, bodybuilder, free) stay active+via_or=1
  # regardless of OR's /api/v1/models curation. Idempotent, no-op when
  # nothing drifted. Does NOT pass --ingest-sitemap by default — the 231
  # sitemap candidates need operator review before bulk-ingest (specialty
  # image/video/audio/embedding models that don't surface via /api/v1/models).

  # OR /rankings scraper (Phase 4 of "extract all models with all columns").
  # Writes weekly_rank + weekly_category for 102 models surfaced on
  # openrouter.ai/rankings/* — the production-usage signal that no other
  # source carries. Carries an embedded snapshot (the rankings pages are
  # React-rendered and SSR doesn't carry the row data); the operator
  # refreshes the snapshot via the puppeteer-MCP sweep.

  # Kilo CLI catalog sync — writes is_agentic (Kilo flag) + Kilo-only
  # rows + capabilities the OpenRouter verifier doesn't carry. Previously
  # boot-only (wsl_startup_hook.sh) which meant a laptop that doesn't
  # reboot left these stale. Now in cron too. Aggregator-audit 2026-06-29.

  # Migrate aggregator-pricing columns (idempotent — adds gateway_prices,
  # cheapest_gateway, cheapest_gateway_price if missing). Cheap; runs
  # every day so a fresh checkout boots cleanly.

  # Ensure quality_tier/is_ga columns exist (idempotent, schema-only;
  # the actual values are recomputed below via derive_quality_v2).

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

  # Speed metrics + AA Intelligence Index. Without this, output_tokens_per_sec
  # and ttft_ms drift from boot-time to weeks-old. Aggregator-audit 2026-06-29:
  # found rows with speed_updated_at from 2026-05-19 because this script ran
  # only in wsl_startup_hook.sh.

  # Groq LPU tokens/sec table. Provider-specific — only realized when
  # provider.only=["Groq"] is pinned in the OR request. Never clobbers
  # higher-precedence sources (AA / own_microbench / manual_override).

  # Terminal Bench + general benchmark scraper.

  # ── KILO_* selection-catalog regen (deploy-readiness-gaps Phase 3a) ──
  # Regenerate the three synced reference docs that were drifting daily (the
  # check_synced_unmodified gate fired on every project). MUST run AFTER the
  # benchmark scrape above (fresh data) and BEFORE embedding_export_markdown.py
  # below (line ~172), which overwrites only the EMBEDDING_* marker sections of
  # KILO_AGENT_SELECTION_GUIDE.md + KILO_MODEL_CAPABILITIES.md — these generators
  # write the ENTIRE file, so running them after would nuke those marker sections.
  # Fabrik capability catalog regen (plan 2026-07-12-plan-2). Re-derives
  # capabilities.json + docs/CAPABILITIES.md + llms.txt by introspecting the
  # 7 tool surfaces (cli/driver/registrar/script/lib-module/scaffold/rules)
  # and liveness-probing each, so a cold AI agent always reads a current,
  # self-verified tool catalog. Generated-not-hand-curated; fail-soft per
  # probe (a broken probe → status:broken, never crashes the refresh).
  # ─── DELIVER: pull the produced bundle from the ai-model-catalog engine ───
  # The MISSING LEG. The plan's produce -> deliver -> sync contract had `deliver_to_fabrik` in D.1's
  # allow-list but no phase ever added the step, so after the cutover fabrik produced nothing AND
  # received nothing: the delivered docs would simply age until select.py's 14-day staleness gate
  # dropped them and ~47 vendored pick_models copies fell back to the hardcoded _TABLE. Found
  # 2026-08-16 by the E.closing review; wired here.
  #
  # Non-fatal by design: a delivery failure must leave YESTERDAY's good docs in place rather than
  # half-write today's. deliver_to_fabrik writes atomically (tmp + os.replace) for the same reason.
  if [ -x /opt/ai-model-catalog/engine/.venv/bin/python ]; then
    _step "deliver_to_fabrik" \
      /opt/ai-model-catalog/engine/.venv/bin/python \
      /opt/ai-model-catalog/engine/deliver_to_fabrik.py --apply --target-root "$FABRIK_ROOT" \
      || echo "[daily_refresh] deliver_to_fabrik failed (non-fatal — yesterday's delivered docs are kept)"
  else
    echo "[daily_refresh] WARNING: ai-model-catalog engine venv missing — nothing delivered today"
  fi

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
    # 2) Refresh scripts/kilo_47_agents_final.json from the DB
    # 3) Emit Traycer CLI agent scripts to ~/.traycer/cli-agents/
    _step "generate_kilo_agents" "$VENV_PY" "$FABRIK_ROOT/scripts/generate_kilo_agents.py" \
      || echo "[daily_refresh] generate_kilo_agents failed (non-fatal)"
  fi

  # Embedding catalog sync (sibling to kilo_agents_db.py for embedding models).

  # Embedding selection pipeline (ported with the kilo-agent workflow above).
  # Mirrors chat pipeline shape: catalog scrape → shortlists → role winners
  # → markdown export.

  # Translation + STT capability seeds. Translation reads the
  # operator-curated bake-off doc in /opt/fabrik-lib/mt-router/docs/;
  # STT seeds direct-API models (Whisper, gpt-4o-transcribe, Deepgram,
  # AssemblyAI) with public WER scores. Idempotent.

  # Direct-vendor specialists (Soniox STT/TTS, Recraft, FLUX, SDXL,
  # ElevenLabs, DeepL Pro) — operator-encoded facts that aren't on
  # OpenRouter / Kilo CLI and therefore aren't picked up by the
  # verifier. Idempotent UPSERT keyed by id.

  # Ensure the 3 direct-vendor pricing columns exist on `agents` (idempotent;
  # required by fetch_direct_vendor_prices.py below).

  # Direct-vendor pricing scraper (Phase 1 ships 5 parsers: AssemblyAI,
  # Deepgram, Soniox, Cartesia, Speechmatics). The orchestrator runs in
  # --apply mode here; per-vendor errors don't fail the daily pipeline.
  # Plan: docs/development/plans/2026-06-29-plan-direct-vendor-pricing.md
  # Phase 5 of the direct-vendor pricing plan: write a per-vendor markdown audit
  # alongside the silent --quiet run. Filename includes UTC date so each day's
  # audit is preserved as operator history at cache/direct_vendor_audit_<date>.md.

  # Phase 4 of the direct-vendor pricing plan: every daily refresh re-infers
  # provider for any rows that came back from the upstream catalogs with
  # provider='unknown' (claude-* models, corethink:free, etc.). Idempotent.

  # Wrapped in _step for per-step timing consistency with every other
  # script above. Pre-fix the timing summary omitted this row.




  # Aggregator pricing (plan-2-aggregator-pricing.md Phase 5). Fetchers
  # populate agents.gateway_prices JSON; derive picks cheapest gateway.
  # All three steps non-fatal so a transient Replicate/fal outage doesn't
  # nuke the rest of the pipeline.
  # OR per-model /endpoints scrape — fetches the full inference-provider
  # list for every OR-routed model so the "Cheapest" column can surface
  # the raw provider (DeepInfra/Groq/etc.) that beats OR's default routing.
  # ~340 API calls @ 4/s = ~90s. Non-fatal on transient OR outage.

  # SiliconFlow catalog scrape — flips via_siliconflow=1 on matched agents.id
  # rows so the browser payload + rank scripts see SF as a real gateway. Fetches
  # the 72-model catalog from https://api.siliconflow.com/v1/models (international
  # endpoint; .cn returns 401 on international keys). Non-fatal on missing key or
  # network failure. Idempotent.

  # ModelScope catalog scrape + new-row auto-ingest.
  # - Flips via_modelscope=1 on matched agents.id rows so the browser payload
  #   + rank scripts see MS as a real gateway.
  # - With --ingest-new (plan-2 follow-up, 2026-07-10): INSERTs previously-
  #   unmatched MS IDs via 3-tier enrichment fallback (HF Hub → MS SPA scrape
  #   via web-scrape → placeholder+blocked=1 with block_reason). Placeholder
  #   rows are visible in the browser MS chip but hidden from rankers.
  # Fetches the 55-model catalog from https://api-inference.modelscope.cn/v1/models
  # (OpenAI-compatible). Non-fatal on missing key or network failure. Idempotent.

  # Weekly (Sundays UTC): OR microbench for rows without Speed data.
  # Skipped if OPENROUTER_API_KEY not set. Placed BEFORE derive so the
  # freshly-benched Speed rows feed the derived views on Sundays.
  # `date +%u` returns 1-7 (Mon-Sun) — 7 = Sunday.


  # Coding-subagent ranking → docs/reference/kilo/CODING_SUBAGENT_SELECTION.md.
  # Runs AFTER derive_cheapest_gateway so the table reflects today's pricing.
  # Non-fatal — a missing table doesn't take down the rest of the pipeline.

  # Correlated cold-start priors for plan/spec (FREE, no generation): seeds model_task_baseline
  # from today's code+review (+ docs, once benched) metrics, so pick_models("plan"/"spec") shrinks
  # against a non-blind prior. Idempotent; fail-soft. Runs BEFORE rank_task_subagents so the priors
  # are fresh in the regenerated doc. (The PAID judged bench — microbench_judged.py --task
  # research/docs --all — is an OPERATOR step, never run here; it spends money + takes ~an hour.)

  # Task-subagent ranking → docs/reference/kilo/TASK_SUBAGENT_SELECTION.md.
  # Reads fleet-wide subagent_runs on fabrik_analytics; emits per-task ranking.
  # Empty pool (state=ok, 0 rows) → stub file with "No aggregated runs yet"; exits 0.
  # A BROKEN read (state=error: DB down / sudo -n misconfig / timeout) does NOT emit the
  # failure stub and does NOT bump "Last refresh" — the existing good doc is KEPT and the
  # ranker exits 1. That inversion is deliberate (Phase A.0): the stub would be committed
  # and fleet-synced to the 49 vendored pick_models copies, and its fresh date would forge
  # past select.py's 14-day staleness gate. The alert below is the operator signal.

  # Per-task specialty rankers (best-model-suggester Phase B). Emit
  # {TTS,STT,TRANSLATION,IMAGE_GEN}_SELECTION.md via Pareto rank on
  # (cost ↑, quality_elo ↓) over reachable_with_existing_keys=1 rows.
  # Each is non-fatal individually.

  # Phase E — GPU price refresh + candidate signups ranker.
  # scrape_gpu_prices is fail-soft (leaves DB prices intact on network error);
  # rank_candidate_signups emits CANDIDATE_SIGNUPS.md.

  # Live gateway counts in the ai/ rule packs. Runs AFTER the OR-routes
  # injector + freshness stamp so both marker blocks land in the same
  # daily refresh. The script is idempotent and self-heals around
  # missing/orphaned markers (mirror of category_export_markdown's
  # contract).


  # Cross-source audit — nightly proof that DB values match live OR /
  # OR /endpoints / Kilo CLI. Any drift is logged; non-fatal so a
  # transient upstream outage doesn't nuke the pipeline. Trust anchor
  # for the browser: if this reports drift, the row(s) shown are wrong.

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
    bash "$KB/pipeline_alert.sh" 'daily_refresh.sh: contract oracle reported drift' 'tests/capture_golden.py --verify did not come back clean on the pipeline host. Either an artifact/marker/query the fleet consumes stopped being produced or collapsed to a husk, or the frozen golden predates the current observer (exit 2 -> re-run --snapshot). Check the run log for the specific contract element.' || true  # through the helper: its return value was discarded here — a silent no-op FB10 closed everywhere else (FC6)
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
  # ⚠️ Do NOT stamp success when the log ladder bottomed out at /dev/null. That run really
  # executed — it committed and PUSHED, fleet-syncing to ~46 repos — but every line of its
  # output was destroyed, so there is no forensic trail and nothing to review. Leaving the
  # stamp un-written lets tomorrow's freshness check raise it, which is the only remaining
  # signal; stamping green over it is how a blind run becomes an invisible one.
  if [ "$LOG_FILE" = "/dev/null" ]; then
    echo "[daily_refresh] NOT stamping success: this run's output was discarded to /dev/null"
    bash "$KB/pipeline_alert.sh" 'daily_refresh.sh: ran BLIND — heartbeat deliberately NOT stamped' "The log ladder fell through to /dev/null, so this run produced no reviewable output. The success stamp was withheld on purpose so the staleness check raises it. Investigate disk / permissions." || true
  elif ! date -u +'%Y-%m-%dT%H:%M:%S+00:00' > "$KB/cache/daily_refresh_last_success.txt" 2>/dev/null; then
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
    # cap the rotated logs at the newest 3 (the hook rotates .2 ← .1 ← log, so three can exist — FC6)
    # FILES only, never a `*.notalog.*` directory's contents (`ls -1t dir` listed the squatter's files, never the squatter — FF1); the squatters themselves go after a week
    find "$KB/cache" -maxdepth 1 -type f -name 'update.log.*' -printf '%T@ %p\n' 2>/dev/null | sort -rn | tail -n +4 | cut -d' ' -f2- | xargs -r rm -f
    find "$KB/cache" -maxdepth 1 -name 'update.log.*.notalog.*' -mtime +7 -exec rm -rf {} + 2>/dev/null || true
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
