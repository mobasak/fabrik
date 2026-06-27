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
#        → injects route blocks into .windsurf/rules/ai/*.md
#   5. export_models_browser.py
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

mkdir -p "$(dirname "$LOG_FILE")"
{
  echo ""
  echo "=== Fabrik AI catalog refresh — $(date -u +'%Y-%m-%d %H:%M:%S UTC') ==="

  cd "$KB" || { echo "[daily_refresh] cd failed — aborting"; exit 0; }

  "$VENV_PY" "$KB/verify_openrouter_catalog.py" --apply --ingest-new \
    || echo "[daily_refresh] verifier failed (non-fatal)"

  # Ensure quality_tier/is_ga columns exist (idempotent, schema-only;
  # the actual values are recomputed below via derive_quality_v2).
  "$VENV_PY" "$KB/migrate_selector_columns.py" \
    || echo "[daily_refresh] selector columns migration failed (non-fatal)"

  # Multi-signal quality scorer: combines existing arena/tbench/coding
  # benchmarks, OpenRouter's `benchmarks.design_arena` + Artificial
  # Analysis, model-family pattern matching, cost-as-proxy, reasoning
  # capability, and context length. Without this, ~85% of models
  # default to T1 and the category selector's `quality_tier>=2` floors
  # silently drop frontier models like claude-opus-4.8 that lack
  # Chatbot Arena ELOs.
  "$VENV_PY" "$KB/derive_quality_v2.py" \
    || echo "[daily_refresh] quality v2 deriver failed (non-fatal)"

  "$VENV_PY" "$KB/classify_ai_category.py" \
    || echo "[daily_refresh] classifier failed (non-fatal)"

  "$VENV_PY" "$KB/category_route_mapper.py" \
    || echo "[daily_refresh] route mapper failed (non-fatal)"

  "$VENV_PY" "$KB/category_export_markdown.py" \
    || echo "[daily_refresh] markdown export failed (non-fatal)"

  "$VENV_PY" "$KB/export_models_browser.py" \
    || echo "[daily_refresh] models_browser export failed (non-fatal)"

  echo "=== Refresh complete — $(date -u +'%Y-%m-%d %H:%M:%S UTC') ==="
} >> "$LOG_FILE" 2>&1
